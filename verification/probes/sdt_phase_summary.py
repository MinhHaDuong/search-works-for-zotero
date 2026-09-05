#!/usr/bin/env python3
"""Derive phase/memory summaries from isolated run arenas; emit no document text."""
import argparse
import hashlib
import json
from pathlib import Path

from sdt_read import read_pack


def summarize(arena):
    run = json.loads((arena / 'run.json').read_text())
    report = run.get('report') or {}
    phases = {row['phase']: row for row in report.get('phases', [])}
    durations = {name[:-6]: (phases[name[:-6] + ':end']['time'] - row['time']) / 1000
                 for name, row in phases.items() if name.endswith(':start')
                 and name[:-6] + ':end' in phases}
    if 'pages:end' in phases and 'pack:start' in phases:
        durations['globalAfterPages'] = (phases['pack:start']['time'] - phases['pages:end']['time']) / 1000
    progress = report.get('progress', [])
    gaps = [(b['time'] - a['time']) / 1000 for a, b in zip(progress, progress[1:])]
    packs = list((arena / 'data/storage').glob('*/.zotero-sdt-cache'))
    semantic_hash = None
    if report.get('ok') and len(packs) == 1:
        pack = read_pack(packs[0])
        pack['metadata'].pop('dateCreated', None)
        canonical = json.dumps(pack, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        semantic_hash = hashlib.sha256(canonical).hexdigest()
    return {
        'key': run['key'], 'pageCount': run['pageCount'],
        'control': run['provenance'].get('control', False),
        'inputSHA256': run['provenance']['inputSHA256'],
        'ok': report.get('ok'), 'stopReason': run['stopReason'],
        'sourceUnchanged': run['sourceUnchanged'], 'limits': run['limits'],
        'ensureSeconds': (report['persisted'] - report['dispatched']) / 1000
        if 'persisted' in report else None,
        'phaseSeconds': durations, 'maximumProgressGapSeconds': max(gaps, default=None),
        'scopePeakBytes': max((row.get('memory.peak', 0) for row in run['samples']), default=0),
        'minimumHostAvailableBytes': min((row['hostAvailableBytes'] for row in run['samples']), default=None),
        'referenceRuns': phases.get('referenceIndex:end', {}).get('runs'),
        'pack': report.get('pack'), 'packSHA256IgnoringCreationDate': semantic_hash,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arenas', type=Path, nargs='+')
    args = parser.parse_args()
    rows = [summarize(arena) for arena in args.arenas]
    controls = []
    for row in rows:
        if row['control']:
            for other in rows:
                if not other['control'] and row['inputSHA256'] == other['inputSHA256']:
                    controls.append({'pageCount': row['pageCount'], 'identicalInput': True,
                                     'equalPackIgnoringCreationDate': bool(row['packSHA256IgnoringCreationDate'])
                                     and row['packSHA256IgnoringCreationDate'] == other['packSHA256IgnoringCreationDate']})
    print(json.dumps({'scope': 'cold isolated native SDT; cgroup memory includes process tree and charged cache',
                      'runs': rows, 'controls': controls}, indent=2))


if __name__ == '__main__':
    main()
