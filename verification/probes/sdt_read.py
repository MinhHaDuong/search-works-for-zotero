#!/usr/bin/env python3
"""Read a Zotero SDT pack (`.zotero-sdt-cache`) and report its structure.

Zotero 10 extracts structured document text into a per-attachment pack beside
the file in `storage/<KEY>/.zotero-sdt-cache`, produced by an ONNX block
segmentation pipeline in `zotero/document-worker`. The pack is what ticket 0120
weighs as a substrate: unlike the contentless FTS5 index, every block carries
`anchor.pageRects` and every text run a per-glyph `textMap`, so it locates a
passage on the page rather than only naming the item that holds it.

Nothing here writes. The format is undocumented and versioned by three
constants (`SDT_PACK_VERSION`, `SDT_SCHEMA_VERSION`, `SDT_PROCESSOR_VERSIONS`,
in the app's `resource/document-worker/metadata.json`); SYNC.md carries the
watch. This reader targets pack version 1 and refuses anything else rather than
guessing, because a silent misparse of a changed layout would produce
plausible blocks rather than an error.

Layout, read from the shipped `structured-document-text.js`:

    magic(8) | packVersion(1) | schema major,minor,patch(3) | indexLength(u32)
    index    : metadataLength(u32) catalogLength(u32)
               chunkByteOffsets(u32 * n) chunkBlockStarts(u32 * n)
    metadata : deflate -> JSON
    catalog  : deflate -> JSON
    content  : per chunk, deflate -> blockOffsets(u32 * count) then block JSON

Usage:
    python3 verification/probes/sdt_read.py PACK                    # metadata + block summary
    python3 verification/probes/sdt_read.py PACK --headings         # every block typed heading
    python3 verification/probes/sdt_read.py PACK --blocks 5         # dump the first 5 blocks
    python3 verification/probes/sdt_read.py PACK --json             # whole pack as JSON
"""
import argparse
import collections
import json
import logging
import struct
import zlib
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sdt")

MAGIC = bytes([137, 83, 68, 84, 13, 10, 26, 10])
HEADER_SIZE = 16
INDEX_FIXED_SIZE = 8
U32 = 4
SUPPORTED_PACK_VERSION = 1


class SDTError(Exception):
    """The bytes are not a pack this reader understands."""


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _inflate(buf: bytes) -> bytes:
    # The app supplies its own inflate; the ranges are raw deflate in the packs
    # observed, but accept a zlib wrapper too rather than depend on that.
    for wbits in (-15, 15):
        try:
            return zlib.decompress(buf, wbits)
        except zlib.error:
            continue
    raise SDTError("range is not deflate-compressed")


def _validate_index(path: Path, metadata_length: int, catalog_length: int,
                    byte_offsets: list[int], block_starts: list[int]) -> None:
    """Mirror `validateIndexShape` from the shipped module.

    Without this a corrupt index does not raise — it *under-reports*. Zeroing
    `block_starts[0]`'s successor yields a pack that parses cleanly and returns
    no blocks, which is the one failure this reader exists to prevent: a probe
    that reads zero and means nothing.
    """
    if metadata_length <= 0:
        raise SDTError(f"{path}: invalid metadata length {metadata_length}")
    if catalog_length <= 0:
        raise SDTError(f"{path}: invalid catalog length {catalog_length}")
    if not byte_offsets or len(byte_offsets) != len(block_starts):
        raise SDTError(f"{path}: invalid chunk index shape")
    if byte_offsets[0] != 0:
        raise SDTError(f"{path}: first chunk offset is {byte_offsets[0]}, not 0")
    if block_starts[0] != 0:
        raise SDTError(f"{path}: first chunk block start is {block_starts[0]}, not 0")
    for name, series in (("chunkByteOffsets", byte_offsets), ("chunkBlockStarts", block_starts)):
        if len(series) > 1 and any(b <= a for a, b in zip(series, series[1:])):
            raise SDTError(f"{path}: {name} is not strictly increasing")


def read_pack(path: Path) -> dict:
    """Parse a pack into {header, metadata, catalog, blocks}."""
    raw = path.read_bytes()
    if len(raw) < HEADER_SIZE or raw[:8] != MAGIC:
        raise SDTError(f"{path}: not an SDT pack (bad magic)")
    pack_version = raw[8]
    if pack_version != SUPPORTED_PACK_VERSION:
        raise SDTError(
            f"{path}: pack version {pack_version}, this reader handles "
            f"{SUPPORTED_PACK_VERSION} — check SYNC.md's version watch"
        )
    index_length = _u32(raw, 12)
    if index_length < INDEX_FIXED_SIZE + U32 * 2 or (index_length - INDEX_FIXED_SIZE) % (U32 * 2):
        raise SDTError(f"{path}: invalid index length {index_length}")
    # Guard before slicing, not after. A slice past the end shortens silently,
    # and every count below derives from the index, so a truncated file would
    # otherwise escape as struct.error or IndexError instead of SDTError.
    if len(raw) < HEADER_SIZE + index_length:
        raise SDTError(f"{path}: truncated inside the index region")

    index = raw[HEADER_SIZE:HEADER_SIZE + index_length]
    metadata_length, catalog_length = _u32(index, 0), _u32(index, 4)
    n = (index_length - INDEX_FIXED_SIZE) // (U32 * 2)
    byte_offsets = [_u32(index, INDEX_FIXED_SIZE + U32 * i) for i in range(n)]
    block_starts = [_u32(index, INDEX_FIXED_SIZE + U32 * n + U32 * i) for i in range(n)]
    _validate_index(path, metadata_length, catalog_length, byte_offsets, block_starts)

    meta_at = HEADER_SIZE + index_length
    catalog_at = meta_at + metadata_length
    content_at = catalog_at + catalog_length
    if content_at > len(raw) or content_at + byte_offsets[-1] != len(raw):
        raise SDTError(f"{path}: declared layout does not match file length")

    metadata = json.loads(_inflate(raw[meta_at:catalog_at]))
    catalog = json.loads(_inflate(raw[catalog_at:content_at]))

    blocks = []
    for i in range(n - 1):
        chunk = _inflate(raw[content_at + byte_offsets[i]:content_at + byte_offsets[i + 1]])
        count = block_starts[i + 1] - block_starts[i]
        table = count * U32
        for j in range(count):
            start = _u32(chunk, j * U32)
            end = _u32(chunk, (j + 1) * U32) if j + 1 < count else len(chunk) - table
            blocks.append(json.loads(chunk[table + start:table + end]))

    return {
        "header": {
            "packVersion": pack_version,
            "schemaVersion": f"{raw[9]}.{raw[10]}.{raw[11]}",
        },
        "metadata": metadata,
        "catalog": catalog,
        "blocks": blocks,
    }


def block_text(block: dict) -> str:
    """Concatenate a block's text runs."""
    return " ".join(
        run.get("text", "")
        for run in block.get("content", [])
        if isinstance(run, dict)
    )


def block_page(block: dict) -> int | None:
    """The zero-based page a block's first rectangle sits on."""
    rects = block.get("anchor", {}).get("pageRects") or []
    return rects[0][0] if rects and rects[0] else None


def _report(pack: dict, args: argparse.Namespace) -> None:
    meta, blocks = pack["metadata"], pack["blocks"]
    processor = meta.get("processor", {})
    source = meta.get("source", {})
    log.info(
        "pack v%s schema %s — %d blocks over %d pages",
        pack["header"]["packVersion"],
        pack["header"]["schemaVersion"],
        len(blocks),
        len(pack["catalog"].get("pages", [])),
    )
    log.info("processor: %s v%s", processor.get("type"), processor.get("version"))
    log.info("title: %s", source.get("properties", {}).get("Title") or "(none)")

    log.info("\nblock types:")
    for kind, count in collections.Counter(b.get("type") for b in blocks).most_common():
        log.info("  %-12s %d", kind, count)

    if args.headings:
        log.info("\nblocks typed 'heading':")
        for block in blocks:
            if block.get("type") == "heading":
                log.info("  p%-3s %s", block_page(block), block_text(block)[:90])

    for block in blocks[:args.blocks]:
        log.info("\n%s", json.dumps(block, ensure_ascii=False)[:600])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pack", type=Path, help="path to a .zotero-sdt-cache file")
    parser.add_argument("--headings", action="store_true", help="list every heading block")
    parser.add_argument("--blocks", type=int, default=0, help="dump the first N blocks")
    parser.add_argument("--json", action="store_true", help="emit the whole pack as JSON")
    args = parser.parse_args()

    pack = read_pack(args.pack)
    if args.json:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
        return
    _report(pack, args)


if __name__ == "__main__":
    main()
