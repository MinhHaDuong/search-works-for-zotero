#!/usr/bin/env python3
"""Account for the 0818 clone run's two open findings, read-only.

(a) the sitter ended with `failed` 391; (b) 8 035 existing `.zotero-sdt-cache`
packs were rewritten on the first run. The sitter's census counts were never
recorded, so this reconstructs them from three sources and prints JSON:

- the pristine library copy (as it was before the run) and the post-run copy,
  both opened `mode=ro&immutable=1` so SQLite writes nothing, not even a -shm;
- Zotero's stdout log of the run, for the sitter's `settle` and `cache-load`
  events;
- each pack's own header and raw-deflated metadata (layout from Zotero's
  `resource/document-worker/structured-document-text.js`: 16-byte header,
  index, then metadata), set against the file's MD5 and the processor
  versions the run's Zotero declared.

`failed` is `failed-session + inspection-error + unsupported-pack +
missing-source` (`plugins/sdt-sitter/scheduler.js`, SDT_STATUS_CLASSES).
`missing-source` is reconstructed here the way `inspect()` decides it: an
in-scope attachment (pdf, epub, or an imported-url text/html snapshot, not
trashed, parent not trashed) whose file does not exist.

Usage: clone_findings_0818.py --pristine DIR --run DIR --log FILE
"""

import argparse
import collections
import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import zlib

# What the run's Zotero (10.0.3) declares in resource/document-worker/metadata.json.
PROCESSOR_VERSIONS = {'pdf': 14, 'epub': 2, 'snapshot': 1}
SITTER_EVENT = re.compile(r'SDT sitter (settle|cache-load|toast) (\{.*\})')


def connect(root):
    return sqlite3.connect(f'file:{root}/zotero.sqlite?mode=ro&immutable=1', uri=True)


def processor_of(link_mode, content_type):
    if link_mode in (3, 4):
        return None
    if content_type == 'application/pdf':
        return 'pdf'
    if content_type == 'application/epub+zip':
        return 'epub'
    if link_mode == 1 and content_type == 'text/html':
        return 'snapshot'
    return None


def source_path(root, key, path):
    if path is None:
        return None
    if path.startswith('storage:'):
        return os.path.join(root, 'storage', key, path[len('storage:'):])
    return path  # linked file, absolute (no base-relative paths occur here)


def in_scope(db, root):
    """Every attachment the census inspects past `excluded`/`unsupported`."""
    rows = db.execute('''
        SELECT i.libraryID, i.key, a.linkMode, a.contentType, a.path, a.syncState
        FROM items i JOIN itemAttachments a USING (itemID)
        WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
          AND (a.parentItemID IS NULL
               OR a.parentItemID NOT IN (SELECT itemID FROM deletedItems))''')
    for lib, key, lm, ct, path, sync in rows:
        proc = processor_of(lm, ct)
        if proc:
            yield lib, key, lm, proc, path, sync


def missing_sources(db, root):
    tally = collections.Counter()
    for lib, key, lm, _proc, path, sync in in_scope(db, root):
        where = source_path(root, key, path)
        if where and os.path.exists(where):
            continue
        storage = os.path.join(root, 'storage', key)
        shape = ('linked-absent' if lm == 2 else 'no-path' if where is None
                 else 'no-storage-dir' if not os.path.isdir(storage)
                 else 'dir-without-file')
        tally[f'library {lib} | {shape} | syncState {sync}'] += 1
    return sum(tally.values()), dict(sorted(tally.items()))


def sitter_events(log):
    events = collections.defaultdict(list)
    with open(log, errors='replace') as fh:
        for line in fh:
            m = SITTER_EVENT.search(line)
            if m:
                events[m.group(1)].append(json.loads(m.group(2)))
    return events


def sniff(path):
    try:
        with open(path, 'rb') as fh:
            head = fh.read(8)
    except OSError:
        return 'unreadable'
    if not head:
        return 'empty'
    if head.startswith(b'%PDF'):
        return 'pdf'
    if head.startswith(b'PK\x03\x04'):
        return 'zip'
    if b'<!' in head.lower() or b'<html' in head.lower():
        return 'html'
    return 'other'


def settle_failures(db, root, events, pristine_errors):
    known = set()
    with open(pristine_errors) as fh:
        for line in fh:
            m = re.search(r'\b(\d+/[A-Z0-9]{8})\b', line)
            if m:
                known.add(m.group(1))
    tally = collections.Counter()
    failed = [e['id'] for e in events['settle'] if not e.get('ok')]
    for ident in failed:
        lib, key = ident.split('/')
        lm, path = db.execute('''SELECT a.linkMode, a.path FROM items i
            JOIN itemAttachments a USING (itemID) WHERE i.libraryID=? AND i.key=?''',
                              (int(lib), key)).fetchone()
        had_pack = os.path.exists(os.path.join(root, 'storage', key, '.zotero-sdt-cache'))
        tally[(f'content {sniff(source_path(root, key, path))}',
               'pack before' if had_pack else 'no pack before',
               'in the 2026-09-06 error history' if ident in known else 'new')] += 1
    return len(failed), {' | '.join(k): v for k, v in sorted(tally.items())}


def pack_metadata(path):
    b = open(path, 'rb').read()
    index_len = struct.unpack_from('<I', b, 12)[0]
    meta_len = struct.unpack_from('<I', b, 16)[0]
    meta = json.loads(zlib.decompress(b[16 + index_len:16 + index_len + meta_len], -15))
    return f'{b[9]}.{b[10]}.{b[11]}', b[8], meta


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def packs(db, pristine, run):
    legacy = set()
    with open(os.path.join(pristine, 'sdt-sitter-cache.jsonl')) as fh:
        for line in fh:
            if line.strip():
                legacy.add(json.loads(line)['key'])
    paths = {}
    for lib, key, lm, ct, path in db.execute('''SELECT i.libraryID, i.key, a.linkMode,
            a.contentType, a.path FROM items i JOIN itemAttachments a USING (itemID)'''):
        paths[key] = (lib, source_path(pristine, key, path))
    tally = collections.Counter()
    for key in sorted(os.listdir(os.path.join(pristine, 'storage'))):
        before = os.path.join(pristine, 'storage', key, '.zotero-sdt-cache')
        if not os.path.exists(before):
            continue
        after = os.path.join(run, 'storage', key, '.zotero-sdt-cache')
        rewritten = os.stat(before).st_mtime_ns != os.stat(after).st_mtime_ns
        schema, _pack_version, meta = pack_metadata(before)
        proc = meta.get('processor') or {}
        lib, src = paths.get(key, (None, None))
        verdicts = []
        if proc.get('version') != PROCESSOR_VERSIONS.get(proc.get('type')):
            verdicts.append(f"processor {proc.get('type')}@{proc.get('version')}")
        if src and os.path.exists(src) and (meta.get('source') or {}).get('hash') != md5(src):
            verdicts.append('source hash differs')
        if src and os.path.exists(src) and proc.get('type') == 'pdf' and sniff(src) == 'zip':
            verdicts.append('pdf label on a zip file')
        tally[(('rewritten' if rewritten else 'kept'), f'schema {schema}',
               ', '.join(verdicts) or 'current',
               'in legacy cache' if f'{lib}/{key}' in legacy else 'not in legacy cache')] += 1
    return {' | '.join(k): v for k, v in sorted(tally.items(), key=lambda kv: -kv[1])}, len(legacy)


def legacy_cache_formats(pristine):
    tally = collections.Counter()
    with open(os.path.join(pristine, 'sdt-sitter-cache.jsonl')) as fh:
        for line in fh:
            if line.strip():
                tally['format %s' % json.loads(line).get('format', 'absent')] += 1
    return dict(tally)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--pristine', required=True, help='library copy as it was before the run')
    ap.add_argument('--run', required=True, help='the same library after the run')
    ap.add_argument('--log', required=True, help="Zotero's stdout log of the run")
    args = ap.parse_args()
    pristine, run = os.path.expanduser(args.pristine), os.path.expanduser(args.run)
    db = connect(pristine)
    events = sitter_events(os.path.expanduser(args.log))
    missing_total, missing = missing_sources(db, pristine)
    missing_after, _ = missing_sources(connect(run), run)
    settle_total, settle = settle_failures(db, pristine, events,
                                           os.path.join(pristine, 'sdt-sitter-errors.jsonl'))
    pack_tally, _ = packs(db, pristine, run)
    settings = dict(((k, v) for _s, k, v in db.execute(
        "SELECT setting, key, value FROM settings WHERE setting='client'")))
    out = {
        'zotero_last_version_on_source': settings.get('lastVersion'),
        'toast': events['toast'],
        'a_failed': {
            'missing_source_pristine': missing_total,
            'missing_source_after_run': missing_after,
            'missing_source_by_shape': missing,
            'failed_session_settles': settle_total,
            'failed_session_by_kind': settle,
            'sum': missing_total + settle_total,
        },
        'b_packs': {
            'cache_load': events['cache-load'],
            'legacy_cache_rows': legacy_cache_formats(pristine),
            'packs': pack_tally,
        },
    }
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
