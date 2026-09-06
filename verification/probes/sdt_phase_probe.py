#!/usr/bin/env python3
"""Instrument installed SDT in a private app overlay and resource-capped profile.

The installed archive/source are never edited. bwrap overlays a modified copy
for this process only. Resource values are experiment arguments, not sitter policy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import zipfile


def instrument(worker):
    helper = '''\nfunction __sdtProbe(phase, detail = {}) {
  self.postMessage({sdtProbe: {phase, time: Date.now(), ...detail}});
}\n'''
    worker += helper
    changes = []

    def replace(old, new):
        nonlocal worker
        if worker.count(old) != 1:
            raise ValueError(f'Instrumentation anchor not unique: {old[:90]}')
        worker = worker.replace(old, new)
        changes.append(old)

    anchor = 'async function getFullStructure(pdfDocument, onnxRuntimeProvider, modelProvider, options = {}) {\n\tconst pageCount = pdfDocument.numPages;'
    replace(anchor, anchor + "\n\t__sdtProbe('pages:start', {pages: pageCount});")
    replace('\t// Block transformations\n\twrapListItems(structure);',
            "\t__sdtProbe('pages:end', {pages: pageCount, blocks: structure.content.length});\n"
            '\t// Block transformations\n\twrapListItems(structure);')
    stages = [
        ('structureIndex', 'let structureIndex = createStructureIndex(structure, options.structureIndex);'),
        ('annotationLinks', 'let annotLinkRefs = getAnnotLinkRefs(structure, linkMap, structureIndex);'),
        ('parsedLinks', 'let parsedLinkRefs = getParsedLinkRefs(structure, structureIndex);'),
        ('candidateLists', 'let candidateReferenceLists = getReferenceLists(structure, regularWordsSet);'),
        ('candidateIndex', 'let candidateReferenceIndex = getReferenceIndex(candidateReferenceLists, regularWordsSet);'),
        ('supportedLists', 'let referenceLists = getSupportedReferenceLists(structure, candidateReferenceIndex, structureIndex);'),
        ('referenceIndex', 'let referenceIndex = getReferenceIndex(referenceLists, regularWordsSet);'),
        ('citations', 'let citationRefs = getCitationRefs(structure, referenceIndex, annotLinkRefs, structureIndex);'),
        ('figures', 'let figures = getFigures(structure);'),
        ('math', 'let mathBlocks = getMathBlocks(structure);'),
        ('figureMathCandidates', 'getFigureAndMathCandidates(structure, candidateGroups, figures, mathBlocks, structureIndex);'),
        ('applyRefs', 'applyRefs(structure, citationRefs);'),
        ('outline', 'let outline = await getOutline(structure.content, referenceTitleRefs, pdfDocument);'),
    ]
    for name, statement in stages:
        detail = ', {runs: referenceIndex.runs.length}' if name == 'referenceIndex' else ''
        replace('\t' + statement, f"\t__sdtProbe('{name}:start');\n\t{statement}\n"
                f"\t__sdtProbe('{name}:end'{detail});")
    replace('\tcleanupBlockMetrics(structure);', "\t__sdtProbe('cleanup:start');\n\tcleanupBlockMetrics(structure);")
    replace('\tensureBlockPageRects(structure);', "\tensureBlockPageRects(structure);\n\t__sdtProbe('cleanup:end');")
    replace('\tonProgress(95);\n\tlet buffer = packStructuredDocumentText(structure, {',
            "\tonProgress(95);\n\t__sdtProbe('pack:start', {blocks: structure.content.length});\n"
            '\tlet buffer = packStructuredDocumentText(structure, {')
    replace('\tonProgress(100);\n\treturn { buf: buffer };',
            "\t__sdtProbe('pack:end', {bytes: buffer.byteLength});\n\tonProgress(100);\n\treturn { buf: buffer };")
    return worker, changes


def meminfo():
    return {line.split(':')[0]: int(line.split()[1]) * 1024
            for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line}


def command(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--pages', required=True, help='mutool page ranges, or all')
    parser.add_argument('--expected-pages', type=int, required=True)
    parser.add_argument('--memory-mib', type=int, required=True)
    parser.add_argument('--min-host-available-mib', type=int, required=True)
    parser.add_argument('--deadline', type=float, required=True)
    parser.add_argument('--control', action='store_true', help='Use the unmodified worker as a control')
    args = parser.parse_args()
    if not args.source.is_file() or args.memory_mib <= 0 or args.deadline <= 0:
        raise ValueError('Invalid source or experiment limits')
    repo = Path(__file__).resolve().parents[2]
    parent = repo / 'corpus-cache'
    parent.mkdir(exist_ok=True)
    arena = Path(tempfile.mkdtemp(prefix='sdt-phase-', dir=parent))
    for name in ('profile/extensions', 'data', 'fixtures', 'runtime', 'cache', 'config'):
        (arena / name).mkdir(parents=True, exist_ok=True)
    (arena / 'runtime').chmod(0o700)
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    pdf = arena / 'fixtures/input.pdf'
    if args.pages == 'all':
        subprocess.run(['cp', '--reflink=auto', str(args.source), str(pdf)], check=True)
    else:
        command(['mutool', 'merge', '-o', str(pdf), str(args.source), args.pages])
    info = command(['pdfinfo', str(pdf)])
    pages = int(re.search(r'^Pages:\s+(\d+)', info, re.M)[1])
    if pages != args.expected_pages:
        raise ValueError('Subset has unexpected page count')
    archive = args.application.resolve().parent / 'app/omni.ja'
    overlay = arena / 'instrumented-omni.ja'
    member = 'resource/document-worker/worker.js'
    with zipfile.ZipFile(archive) as original:
        source_worker = original.read(member)
        patched, anchors = (source_worker.decode(), []) if args.control else instrument(source_worker.decode())
        with zipfile.ZipFile(overlay, 'x') as target:
            for entry in original.infolist():
                target.writestr(entry, patched.encode() if entry.filename == member else original.read(entry))
    def sha(data):
        return hashlib.sha256(data).hexdigest()
    provenance = {'control': args.control, 'sourceSHA256': source_hash, 'inputSHA256': sha(pdf.read_bytes()),
                  'workerOriginalSHA256': sha(source_worker), 'workerInstrumentedSHA256': sha(patched.encode()),
                  'anchors': anchors, 'pluginSourceSHA256': {}}
    for name in ('sdt-diagnostic-plugin', 'sdt-phase-harness'):
        folder = repo / 'verification/probes' / name
        manifest = json.loads((folder / 'manifest.json').read_text())
        addon_id = manifest['applications']['zotero']['id']
        with zipfile.ZipFile(arena / 'profile/extensions' / f'{addon_id}.xpi', 'x',
                             compression=zipfile.ZIP_DEFLATED) as package:
            for file in sorted(folder.iterdir()):
                if file.is_file():
                    package.write(file, file.name)
                    provenance['pluginSourceSHA256'][f'{name}/{file.name}'] = sha(file.read_bytes())
    prefs = {'extensions.autoDisableScopes': 0, 'extensions.enabledScopes': 15,
             'extensions.zotero.httpServer.enabled': False, 'extensions.zotero.firstRun': False,
             'extensions.zotero.fulltext.pdfMaxPages': 0}
    (arena / 'profile/prefs.js').write_text('\n'.join(
        f'user_pref({json.dumps(k)}, {json.dumps(v)});' for k, v in prefs.items()) + '\n')
    output = arena / 'phases.json'
    (arena / 'data/sdt-diagnostic.json').write_text(json.dumps({
        'allowDiagnostic': True, 'phaseProbe': True, 'dataDir': str(arena / 'data'),
        'input': str(pdf), 'output': str(output), 'key': args.key, 'pages': args.pages,
        'expectedPages': args.expected_pages,
    }))
    unit = arena.name
    argv = ['systemd-run', '--user', '--scope', '--quiet', '--unit', unit,
            '-p', f'MemoryMax={args.memory_mib}M', '-p', 'MemorySwapMax=0',
            'bwrap', '--ro-bind', '/', '/', '--unshare-net', '--unshare-pid',
            '--die-with-parent', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
            '--bind', str(arena), str(arena), '--ro-bind', str(overlay), str(archive),
            '--chdir', str(arena), '--setenv', 'XDG_RUNTIME_DIR', str(arena / 'runtime'),
            '--setenv', 'XDG_CACHE_HOME', str(arena / 'cache'),
            '--setenv', 'XDG_CONFIG_HOME', str(arena / 'config'),
            'xvfb-run', '-a', str(args.application.resolve()), '-profile', str(arena / 'profile'),
            '-datadir', str(arena / 'data'), '-no-remote', '-ZoteroDebugText']
    print(json.dumps({'arena': str(arena), 'pages': pages, 'scope': unit}), flush=True)
    began = time.monotonic()
    samples, reason, limits = [], None, None
    cgroup = None
    with (arena / 'application.log').open('w') as log:
        process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                host = meminfo()
                if cgroup is None:
                    result = subprocess.run(['systemctl', '--user', 'show', unit + '.scope',
                                             '-p', 'ControlGroup', '-p', 'MemoryMax', '-p', 'MemorySwapMax'],
                                            capture_output=True, text=True)
                    properties = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
                    if properties.get('ControlGroup'):
                        limits = properties
                        if properties.get('MemoryMax') != str(args.memory_mib * 1024**2) or properties.get('MemorySwapMax') != '0':
                            reason = 'resource-limit-verification-failed'
                            break
                        cgroup = Path('/sys/fs/cgroup') / properties['ControlGroup'].lstrip('/')
                row = {'time': time.time(), 'hostAvailableBytes': host.get('MemAvailable')}
                if cgroup is not None:
                    for file in ('memory.current', 'memory.peak', 'memory.events'):
                        try:
                            data = (cgroup / file).read_text().strip()
                            row[file] = dict(line.split() for line in data.splitlines()) if file.endswith('events') else int(data)
                        except FileNotFoundError:
                            pass
                samples.append(row)
                if int(row.get('memory.events', {}).get('oom_kill', 0)):
                    reason = 'cgroup-oom'
                    break
                if host.get('MemAvailable', 0) < args.min_host_available_mib * 1024**2:
                    reason = 'host-memory-pressure'
                    break
                if time.monotonic() - began >= args.deadline:
                    reason = 'observation-deadline'
                    break
                time.sleep(1)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    report = json.loads(output.read_text()) if output.exists() else None
    summary = {'key': args.key, 'pages': args.pages, 'pageCount': pages,
               'provenance': provenance, 'limits': limits, 'stopReason': reason,
               'returncode': process.returncode, 'wallSeconds': time.monotonic() - began,
               'samples': samples, 'report': report,
               'sourceUnchanged': sha(args.source.read_bytes()) == source_hash}
    (arena / 'run.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'arena': str(arena), 'stopReason': reason, 'returncode': process.returncode,
                      'report': report}, indent=2), flush=True)
    return 0 if limits and reason is None and process.returncode == 0 and report and \
        report.get('ok') and report.get('finished') and not report.get('error') else 1


if __name__ == '__main__':
    raise SystemExit(main())
