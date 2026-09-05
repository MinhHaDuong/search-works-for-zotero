#!/usr/bin/env python3
"""Run the diagnostic addons in a fresh, filesystem/network-isolated Zotero.

No HOME override, production profile, source attachments or production endpoint.
Generated fixture/profile/package/report files live in a fresh mkdtemp arena.
The host filesystem is read-only inside bwrap; only that arena is writable.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application', type=Path, required=True)
    parser.add_argument('--deadline', type=float, default=240)
    parser.add_argument('--sitter', action='store_true', help='Test the production sitter with a private UI driver')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    arena_parent = repo / 'corpus-cache' if args.sitter else None
    if arena_parent:
        arena_parent.mkdir(exist_ok=True)
    arena = Path(tempfile.mkdtemp(prefix='sdt-diagnostic-', dir=arena_parent))
    for name in ('profile/extensions', 'data', 'fixtures', 'runtime', 'cache', 'config'):
        (arena / name).mkdir(parents=True, exist_ok=True)
    (arena / 'runtime').chmod(0o700)
    prefs = {
        'extensions.autoDisableScopes': 0, 'extensions.enabledScopes': 15,
        'extensions.zotero.httpServer.enabled': False,
        'extensions.zotero.firstRun': False,
    }
    (arena / 'profile/prefs.js').write_text('\n'.join(
        f'user_pref({json.dumps(key)}, {json.dumps(value)});' for key, value in prefs.items()
    ) + '\n')
    source_digests = {}
    folders = [repo / 'verification/probes' / name
               for name in ('sdt-diagnostic-plugin', 'sdt-diagnostic-harness')]
    if args.sitter:
        folders = [repo / 'bench/sdt-sitter', repo / 'verification/probes/sdt-sitter-harness']
    for folder in folders:
        name = folder.name
        manifest = json.loads((folder / 'manifest.json').read_text())
        addon_id = manifest['applications']['zotero']['id']
        with zipfile.ZipFile(arena / 'profile/extensions' / f'{addon_id}.xpi', 'x',
                             compression=zipfile.ZIP_DEFLATED) as package:
            for file in sorted(folder.iterdir()):
                if file.is_file():
                    package.write(file, file.name)
                    source_digests[f'{name}/{file.name}'] = hashlib.sha256(file.read_bytes()).hexdigest()
    for kind in ('pdf', 'epub'):
        subprocess.run([sys.executable, str(repo / 'bench/fixtures/make_attachment_fixtures.py'),
                        '--fixture', kind, '--output', str(arena / f'fixtures/input.{kind}')],
                       check=True, capture_output=True)
    subprocess.run(['pdfunite', *([str(arena / 'fixtures/input.pdf')] * 128),
                    str(arena / 'fixtures/multipage.pdf')], check=True, capture_output=True)
    output = arena / 'integration.json'
    marker_name = 'sdt-sitter-smoke.json' if args.sitter else 'sdt-diagnostic.json'
    (arena / 'data' / marker_name).write_text(json.dumps({
        'allowDiagnostic': True, 'dataDir': str(arena / 'data'),
        'pdf': str(arena / 'fixtures/input.pdf'),
        'epub': str(arena / 'fixtures/input.epub'), 'output': str(output),
        'multipage': str(arena / 'fixtures/multipage.pdf'),
    }))
    argv = ['bwrap', '--ro-bind', '/', '/', '--unshare-net', '--unshare-pid',
            '--die-with-parent', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
            '--bind', str(arena), str(arena), '--chdir', str(arena),
            '--setenv', 'XDG_RUNTIME_DIR', str(arena / 'runtime'),
            '--setenv', 'XDG_CACHE_HOME', str(arena / 'cache'),
            '--setenv', 'XDG_CONFIG_HOME', str(arena / 'config'),
            'xvfb-run', '-a', str(args.application.resolve()),
            '-profile', str(arena / 'profile'), '-datadir', str(arena / 'data'),
            '-no-remote', '-ZoteroDebugText']
    print(json.dumps({'arena': str(arena), 'argv': argv}), flush=True)
    began = time.monotonic()
    with (arena / 'application.log').open('w') as log:
        process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=args.deadline)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            # Exact process group started above, never a name-based Zotero kill.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    summary = {'arena': str(arena), 'returncode': process.returncode,
               'deadlineReached': timed_out, 'wallSeconds': time.monotonic() - began,
               'pluginSourceSHA256': source_digests,
               'network': 'unshared', 'filesystem': 'host read-only, arena writable',
               'report': json.loads(output.read_text()) if output.exists() else None}
    (arena / 'run.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    report = summary['report']
    return 0 if process.returncode == 0 and not timed_out and report and report.get('tests') \
        and not report.get('fatal') and report.get('finished') and all(
        test['result'] == 'pass' for test in report['tests']) else 1


if __name__ == '__main__':
    sys.exit(main())
