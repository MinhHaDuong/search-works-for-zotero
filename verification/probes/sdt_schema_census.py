#!/usr/bin/env python3
"""Census the on-disk SDT pack population by header stamp, and diff shapes across schemas.

SYNC.md's drift watch reads three constants out of the installed build's
`resource/document-worker/metadata.json`. That answers what the *next* pack will
be written as. It does not answer what is on disk, and the two diverge for as
long as a drain runs — or permanently, for a processor whose version did not
move (2026-09-11: `snapshot` stayed at 1 while `pdf` went 3 -> 14, so snapshot
packs keep whatever schema they were written under).

This probe reads the population instead:

  census    pack version and schema version of every pack, grouped by attachment
            kind, so a mixed-schema cache is visible as a fact rather than
            inferred from the constants.
  outline   presence of the outline-entry keys that moved between schema 1.1.0
            and 1.2.0 (`level` -> `source`/`target`), per schema bucket. The
            control is built in: a key that appears in one bucket and never in
            the other is a structural change; a mixture is sampling noise.

Nothing here writes, and nothing here opens Zotero. It reads pack bytes only.

Usage:
    python3 verification/probes/sdt_schema_census.py census
    python3 verification/probes/sdt_schema_census.py outline --per-bucket 400
    python3 verification/probes/sdt_schema_census.py census --json
"""
import argparse
import collections
import json
import logging
import pathlib
import struct
import zlib

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sdt-census")

MAGIC = bytes([137, 83, 68, 84, 13, 10, 26, 10])
DEFAULT_STORAGE = pathlib.Path.home() / "data" / "Zotero" / "storage"
# The keys that moved between 1.1.0 and 1.2.0; extend as later bumps are read.
OUTLINE_WATCHED_KEYS = ("level", "source", "target")


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def read_header(path: pathlib.Path) -> tuple[int, str] | None:
    """Pack version and schema version from the 12-byte header, or None."""
    with path.open("rb") as handle:
        head = handle.read(12)
    if len(head) < 12 or head[:8] != MAGIC:
        return None
    return head[8], f"{head[9]}.{head[10]}.{head[11]}"


def read_catalog(path: pathlib.Path) -> dict:
    raw = path.read_bytes()
    if raw[:8] != MAGIC:
        raise ValueError("not a pack")
    index_len = _u32(raw, 12)
    index = raw[16:16 + index_len]
    meta_len, cat_len = _u32(index, 0), _u32(index, 4)
    body = raw[16 + index_len:]
    return json.loads(zlib.decompress(body[meta_len:meta_len + cat_len], -15))


def attachment_kind(pack: pathlib.Path) -> str:
    """Classify by the attachment sitting beside the pack, not by pack content."""
    suffixes = {child.suffix.lower() for child in pack.parent.iterdir() if child.is_file()}
    if ".pdf" in suffixes:
        return "pdf"
    if ".epub" in suffixes:
        return "epub"
    return "snapshot/other"


def iter_packs(storage: pathlib.Path):
    yield from storage.glob("*/.zotero-sdt-cache")


def census(storage: pathlib.Path) -> dict:
    counts: collections.Counter = collections.Counter()
    unreadable = 0
    for pack in iter_packs(storage):
        try:
            header = read_header(pack)
        except OSError:
            unreadable += 1
            continue
        if header is None:
            unreadable += 1
            continue
        pack_version, schema = header
        counts[(attachment_kind(pack), pack_version, schema)] += 1
    return {
        "rows": [
            {"kind": kind, "pack_version": pv, "schema": schema, "count": n}
            for (kind, pv, schema), n in sorted(counts.items(), key=lambda kv: -kv[1])
        ],
        "total": sum(counts.values()),
        "unreadable": unreadable,
    }


def _outline_keys(entries, acc: set) -> None:
    for entry in entries or []:
        if isinstance(entry, dict):
            acc.update(entry.keys())
            _outline_keys(entry.get("children"), acc)


def outline_shapes(storage: pathlib.Path, per_bucket: int) -> dict:
    stats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    seen: collections.Counter = collections.Counter()
    for pack in iter_packs(storage):
        header = read_header(pack)
        if header is None:
            continue
        _, schema = header
        if seen[schema] >= per_bucket:
            continue
        try:
            catalog = read_catalog(pack)
        except (ValueError, zlib.error, json.JSONDecodeError, OSError):
            continue
        seen[schema] += 1
        bucket = stats[schema]
        outline = catalog.get("outline")
        if not outline:
            bucket["no-outline"] += 1
            continue
        bucket["has-outline"] += 1
        keys: set = set()
        _outline_keys(outline, keys)
        for watched in OUTLINE_WATCHED_KEYS:
            if watched in keys:
                bucket[f"with-{watched}"] += 1
    return {
        schema: {"packs_read": seen[schema], **dict(bucket)}
        for schema, bucket in sorted(stats.items())
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("census", "outline"))
    parser.add_argument("--storage", type=pathlib.Path, default=DEFAULT_STORAGE,
                        help=f"Zotero storage directory (default: {DEFAULT_STORAGE})")
    parser.add_argument("--per-bucket", type=int, default=400,
                        help="packs to read per schema bucket in outline mode")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args()

    if not args.storage.is_dir():
        parser.error(f"storage directory not found: {args.storage}")

    result = census(args.storage) if args.mode == "census" else \
        outline_shapes(args.storage, args.per_bucket)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.mode == "census":
        log.info("%-16s %4s %8s %7s", "kind", "pack", "schema", "count")
        for row in result["rows"]:
            log.info("%-16s %4d %8s %7d", row["kind"], row["pack_version"],
                     row["schema"], row["count"])
        log.info("\ntotal packs read: %d, unreadable/not-a-pack: %d",
                 result["total"], result["unreadable"])
        return

    for schema, bucket in result.items():
        log.info("schema %s: packs read %d, with outline %d, no outline %d",
                 schema, bucket["packs_read"], bucket.get("has-outline", 0),
                 bucket.get("no-outline", 0))
        for watched in OUTLINE_WATCHED_KEYS:
            log.info("    outline entries carrying %-8s %d", f"'{watched}':",
                     bucket.get(f"with-{watched}", 0))


if __name__ == "__main__":
    main()
