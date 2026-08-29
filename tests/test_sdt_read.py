"""Tests for verification/probes/sdt_read.py.

The packs this reads are not in the repo — they live on the author's machine,
two of them, and only for PDFs opened in Zotero's reader. So the fixture is
synthetic: a pack built here byte by byte from the layout in the module
docstring. That is the point rather than a compromise. A test against a real
pack would prove the reader works on one file from one processor version; a
built pack lets the malformed cases be constructed, and those are what the
reader has to refuse.

The load-bearing test is `test_future_pack_version_is_refused`. The format is
undocumented and has already moved once, so the failure that costs is not a
crash on a new layout, it is a *silent misparse* producing plausible blocks
from bytes that mean something else.
"""
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verification" / "probes"))

from sdt_read import (  # noqa: E402
    MAGIC,
    SDTError,
    block_page,
    block_text,
    read_pack,
)


def _deflate(raw: bytes) -> bytes:
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(raw) + compressor.flush()


def build_pack(metadata: dict, catalog: dict, chunks: list[list[dict]],
               pack_version: int = 1, schema: tuple[int, int, int] = (1, 1, 0)) -> bytes:
    """Assemble a valid SDT pack from blocks grouped into content chunks."""
    meta_bytes = _deflate(json.dumps(metadata).encode())
    catalog_bytes = _deflate(json.dumps(catalog).encode())

    compressed_chunks, byte_offsets, block_starts = [], [0], [0]
    for blocks in chunks:
        payloads = [json.dumps(b).encode() for b in blocks]
        offsets, running = [], 0
        for payload in payloads:
            offsets.append(running)
            running += len(payload)
        table = b"".join(struct.pack("<I", o) for o in offsets)
        compressed = _deflate(table + b"".join(payloads))
        compressed_chunks.append(compressed)
        byte_offsets.append(byte_offsets[-1] + len(compressed))
        block_starts.append(block_starts[-1] + len(blocks))

    index = (
        struct.pack("<I", len(meta_bytes))
        + struct.pack("<I", len(catalog_bytes))
        + b"".join(struct.pack("<I", o) for o in byte_offsets)
        + b"".join(struct.pack("<I", s) for s in block_starts)
    )
    header = (
        MAGIC
        + bytes([pack_version, schema[0], schema[1], schema[2]])
        + struct.pack("<I", len(index))
    )
    return header + index + meta_bytes + catalog_bytes + b"".join(compressed_chunks)


METADATA = {
    "processor": {"type": "pdf", "version": 3},
    "source": {"hash": "abc123", "properties": {"Title": "Turnpike Theory"}},
}
CATALOG = {"pages": [{"label": "1"}, {"label": "2"}]}
BLOCKS = [
    {"type": "heading", "anchor": {"pageRects": [[0, 36, 731, 136, 743]]},
     "content": [{"text": "TURNPIKE THEORY"}]},
    {"type": "paragraph", "anchor": {"pageRects": [[0, 36, 711, 212, 723]]},
     "content": [{"text": "Author(s):"}, {"text": "Lionel W. McKenzie"}]},
    {"type": "math", "anchor": {"pageRects": [[1, 40, 500, 300, 520]]},
     "content": [{"text": "V(x) = sup(u(x,y) + V(y))"}]},
]


def _write(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / ".zotero-sdt-cache"
    path.write_bytes(data)
    return path


def test_round_trip_recovers_metadata_catalog_and_blocks(tmp_path):
    path = _write(tmp_path, build_pack(METADATA, CATALOG, [BLOCKS[:2], BLOCKS[2:]]))
    pack = read_pack(path)

    assert pack["header"] == {"packVersion": 1, "schemaVersion": "1.1.0"}
    assert pack["metadata"] == METADATA
    assert pack["catalog"] == CATALOG
    assert pack["blocks"] == BLOCKS


def test_blocks_are_ordered_across_chunk_boundaries(tmp_path):
    # Block order is the document's reading order, and it has to survive the
    # split into chunks -- a reader that concatenated chunks out of order would
    # still return the right count.
    path = _write(tmp_path, build_pack(METADATA, CATALOG, [[BLOCKS[0]], [BLOCKS[1]], [BLOCKS[2]]]))
    kinds = [b["type"] for b in read_pack(path)["blocks"]]
    assert kinds == ["heading", "paragraph", "math"]


def test_future_pack_version_is_refused(tmp_path):
    # The defect that costs is a silent misparse of a layout that changed, not
    # a crash. A pack version this reader does not know must raise.
    path = _write(tmp_path, build_pack(METADATA, CATALOG, [BLOCKS], pack_version=2))
    with pytest.raises(SDTError, match="pack version 2"):
        read_pack(path)


def test_non_pack_bytes_are_refused(tmp_path):
    with pytest.raises(SDTError, match="bad magic"):
        _write(tmp_path, b"%PDF-1.6\n" + b"\x00" * 64)
        read_pack(tmp_path / ".zotero-sdt-cache")


def test_truncated_pack_is_refused(tmp_path):
    full = build_pack(METADATA, CATALOG, [BLOCKS])
    path = _write(tmp_path, full[:-20])
    with pytest.raises(SDTError, match="file length"):
        read_pack(path)


@pytest.mark.parametrize("cut", [16, 20, 24, 28, 36])
def test_truncation_inside_the_index_region_raises_sdterror(tmp_path, cut):
    # Every count below the header derives from the index, so a slice that ran
    # off the end used to shorten silently and surface as struct.error or
    # IndexError -- outside the error contract a caller can catch.
    full = build_pack(METADATA, CATALOG, [BLOCKS])
    path = _write(tmp_path, full[:cut])
    with pytest.raises(SDTError):
        read_pack(path)


def _patch_u32(pack: bytes, offset: int, value: int) -> bytes:
    return pack[:offset] + struct.pack("<I", value) + pack[offset + 4:]


# The index sits at byte 16: metadataLength, catalogLength, then the two u32
# series. With one content chunk each series has two entries.
_BYTE_OFFSETS_AT = 16 + 8
_BLOCK_STARTS_AT = _BYTE_OFFSETS_AT + 4 * 2


def test_block_starts_that_report_no_blocks_are_refused(tmp_path):
    # THE defect this reader exists to prevent. Flattening the block series
    # makes every chunk hold zero blocks: the pack parses, raises nothing, and
    # returns an empty document. A probe reading zero would mean nothing, which
    # is the failure the ticket log records this project already having hit.
    clean = build_pack(METADATA, CATALOG, [BLOCKS])
    assert len(read_pack(_write(tmp_path, clean))["blocks"]) == 3

    path = _write(tmp_path, _patch_u32(clean, _BLOCK_STARTS_AT + 4, 0))
    with pytest.raises(SDTError, match="strictly increasing"):
        read_pack(path)


def test_index_series_must_start_at_zero(tmp_path):
    clean = build_pack(METADATA, CATALOG, [BLOCKS])
    with pytest.raises(SDTError, match="first chunk block start"):
        read_pack(_write(tmp_path, _patch_u32(clean, _BLOCK_STARTS_AT, 1)))
    with pytest.raises(SDTError, match="first chunk offset"):
        read_pack(_write(tmp_path, _patch_u32(clean, _BYTE_OFFSETS_AT, 4)))


def test_zero_length_metadata_or_catalog_is_refused(tmp_path):
    clean = build_pack(METADATA, CATALOG, [BLOCKS])
    with pytest.raises(SDTError, match="metadata length"):
        read_pack(_write(tmp_path, _patch_u32(clean, 16, 0)))
    with pytest.raises(SDTError, match="catalog length"):
        read_pack(_write(tmp_path, _patch_u32(clean, 20, 0)))


def test_block_text_joins_runs_and_block_page_reads_the_rectangle():
    assert block_text(BLOCKS[1]) == "Author(s): Lionel W. McKenzie"
    assert block_page(BLOCKS[0]) == 0
    assert block_page(BLOCKS[2]) == 1
    assert block_page({"type": "paragraph"}) is None
