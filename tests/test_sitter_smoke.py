"""The parts of the real-Zotero smoke test that do not need a Zotero.

Ticket 0784. The smoke test's own value is only provable against a live
process (see the ticket's log for the red/green pair that proves it), which
this suite cannot reproduce in `make check` -- there is no Zotero binary and no
display on the machine that gate has to stay green on. What IS checkable here,
fast and without a Zotero, is the part most likely to silently rot: the fixture
generator (does it still write three valid, linkable attachments), and the
setup helpers that refuse to reuse throwaway state.
"""

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

from fixtures.smoke_library import write_smoke_library  # noqa: E402
from sitter_smoke_test import (  # noqa: E402
    SDT_MAGIC,
    NotRunError,
    SmokeFailure,
    check_cache_rows,
    check_packs,
    find_zotero_bin,
    read_pack_metadata,
    setup_profile,
)


def test_write_smoke_library_writes_three_linkable_items(tmp_path):
    ris_path = write_smoke_library(tmp_path)
    text = ris_path.read_text(encoding="utf-8")
    linked = [line.split("-", 1)[1].strip()
             for line in text.splitlines() if line.startswith("L1  -")]
    assert len(linked) == 3
    for relative in linked:
        attachment = ris_path.parent / relative
        assert attachment.exists(), attachment
        # Genuinely a PDF, not merely named one -- the same discipline
        # `bench/fixtures/make_attachment_fixtures.py`'s own docstring states:
        # a fixture that only looks like its format measures nothing.
        assert attachment.read_bytes().startswith(b"%PDF-")


def test_write_smoke_library_refuses_to_overwrite(tmp_path):
    write_smoke_library(tmp_path)
    with pytest.raises(FileExistsError):
        write_smoke_library(tmp_path)


def test_find_zotero_bin_refuses_a_missing_launcher(tmp_path):
    with pytest.raises(NotRunError):
        find_zotero_bin(tmp_path / "no-such-zotero")


def test_find_zotero_bin_refuses_a_launcher_with_no_binary_beside_it(tmp_path):
    launcher = tmp_path / "zotero"
    launcher.write_text("#!/bin/sh\n")
    with pytest.raises(NotRunError):
        find_zotero_bin(launcher)


def test_setup_profile_pins_the_data_directory_and_its_gating_pref(tmp_path):
    """Ticket 0782's actual mechanism, established while first running this
    script against a real Zotero: `dataDirectory.js` only honours the `dataDir`
    pref when `useDataDir` is ALSO true. `bench/sitter_volume_experiment.py`'s
    `SEED_PREFS`, reused here, sets `dataDir` alone -- so this asserts the
    companion pref this file adds on top is still there, since its absence is
    exactly what let a smoke run open the real default data directory."""
    profile, data_dir = setup_profile(tmp_path, port=6100)
    prefs = (profile / "prefs.js").read_text(encoding="utf-8")
    assert f'"extensions.zotero.dataDir", "{data_dir}"' in prefs
    assert 'user_pref("extensions.zotero.useDataDir", true);' in prefs


# --- ticket 0785: the on-disk assertions, against synthetic packs ------------
#
# These need no Zotero. The container is reproduced from a real 10.0.1 pack:
# magic, a four-byte version block, three little-endian uint32, then a
# raw-deflate metadata section. The drill that proves the assertions against
# REAL packs is in ticket 0785's log; this suite keeps them from rotting.

FIXTURE_MD5 = "c28ebc2294e92415647827bfeb9d567f"


class _Log:
    def __init__(self):
        self.lines = []

    def write(self, message):
        self.lines.append(message)


def _pack_bytes(source_hash=FIXTURE_MD5, processor_version=3, created="2026-09-13T18:27:27.611Z"):
    meta = {
        "processor": {"type": "pdf", "version": processor_version},
        "dateCreated": created,
        "source": {"contentType": "application/pdf", "hash": source_hash,
                   "properties": {"PDFFormatVersion": "1.4"}},
    }
    body = zlib.compressobj(9, zlib.DEFLATED, -15)
    blob = body.compress(json.dumps(meta).encode()) + body.flush()
    header = SDT_MAGIC + bytes([1, 1, 1, 0]) + struct.pack("<III", 24, len(blob), 84)
    return header + blob


def _library(tmp_path, count=3, pdf_bytes=b"%PDF-1.4 fixture", **pack_kwargs):
    """A data dir with `count` packs and a fixture dir whose PDFs they name."""
    data = tmp_path / "data"
    fixture = tmp_path / "fixture" / "attachments"
    fixture.mkdir(parents=True)
    digest = hashlib.md5(pdf_bytes).hexdigest()
    for n in range(count):
        (fixture / f"smoke-{n}.pdf").write_bytes(pdf_bytes)
        key = data / "storage" / f"KEY{n:05d}"
        key.mkdir(parents=True)
        (key / ".zotero-sdt-cache").write_bytes(
            _pack_bytes(source_hash=digest, created=f"2026-09-13T18:27:2{n}.000Z",
                        **pack_kwargs))
    return data, tmp_path / "fixture"


def _cache_file(path, count=3, empty=False, pages=1, versions=None):
    stamp = json.dumps(versions or {"SDT_SCHEMA_VERSION": "1.1.0", "SDT_PACK_VERSION": 1})
    rows = []
    for n in range(count):
        rows.append(json.dumps({
            "format": 1, "versions": stamp, "key": f"1/KEY{n:05d}",
            "record": {"signature": f"sig{n}", "fingerprint": "[1,2]",
                       "pages": pages, "sourceBytes": 590, "empty": empty},
        }))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_read_pack_metadata_round_trips_a_real_shaped_container(tmp_path):
    pack = tmp_path / ".zotero-sdt-cache"
    pack.write_bytes(_pack_bytes())
    meta = read_pack_metadata(pack)
    assert meta["source"]["hash"] == FIXTURE_MD5
    assert meta["processor"] == {"type": "pdf", "version": 3}


def test_read_pack_metadata_refuses_a_file_without_the_magic(tmp_path):
    pack = tmp_path / ".zotero-sdt-cache"
    pack.write_bytes(b"GARBAGE" + _pack_bytes()[7:])
    with pytest.raises(SmokeFailure, match="does not carry the SDT magic"):
        read_pack_metadata(pack)


def test_check_packs_accepts_one_pack_per_attachment(tmp_path):
    data, fixture = _library(tmp_path)
    result = check_packs(data, fixture, 3, _Log())
    assert result == {"count": 3, "processors": [{"type": "pdf", "version": 3}]}


def test_check_packs_refuses_a_missing_pack(tmp_path):
    data, fixture = _library(tmp_path)
    sorted(data.glob("storage/*/.zotero-sdt-cache"))[0].unlink()
    with pytest.raises(SmokeFailure, match="expected 3"):
        check_packs(data, fixture, 3, _Log())


def test_check_packs_refuses_a_pack_naming_bytes_we_did_not_write(tmp_path):
    data, fixture = _library(tmp_path)
    # The fixture changed under the run; the packs still name the old bytes.
    for pdf in (fixture / "attachments").glob("*.pdf"):
        pdf.write_bytes(b"%PDF-1.4 something else")
    with pytest.raises(SmokeFailure, match="not the MD5 of any fixture PDF"):
        check_packs(data, fixture, 3, _Log())


def test_check_packs_reports_the_processor_version_it_saw(tmp_path):
    # The 10.0.2 carry-over arm reads this number to tell a re-preparation from
    # stale rows reused; it must reach the caller, not just the log.
    data, fixture = _library(tmp_path, processor_version=4)
    assert check_packs(data, fixture, 3, _Log())["processors"] == [
        {"type": "pdf", "version": 4}]


def test_check_cache_rows_accepts_one_live_record_per_attachment(tmp_path):
    result = check_cache_rows(_cache_file(tmp_path / "c.jsonl"), 3, _Log())
    assert result["records"] == 3
    assert result["versions"]["SDT_PACK_VERSION"] == 1


def test_check_cache_rows_refuses_records_marked_empty(tmp_path):
    # The defect this whole check exists for: the sitter ran and produced
    # nothing, and the old existence-only assertion called that a pass.
    with pytest.raises(SmokeFailure, match="marked empty"):
        check_cache_rows(_cache_file(tmp_path / "c.jsonl", empty=True), 3, _Log())


def test_check_cache_rows_refuses_an_undercount(tmp_path):
    with pytest.raises(SmokeFailure, match="expected 3"):
        check_cache_rows(_cache_file(tmp_path / "c.jsonl", count=1), 3, _Log())


def test_check_cache_rows_refuses_a_record_with_no_pages(tmp_path):
    with pytest.raises(SmokeFailure, match="pages="):
        check_cache_rows(_cache_file(tmp_path / "c.jsonl", pages=0), 3, _Log())


def test_check_cache_rows_refuses_mixed_version_stamps(tmp_path):
    # One run cannot straddle two SDT versions. If it does, the cache is being
    # read across a Zotero upgrade and the counts mean nothing.
    path = tmp_path / "c.jsonl"
    _cache_file(path, count=2)
    rows = path.read_text().splitlines()
    other = json.dumps({"format": 1, "versions": json.dumps({"SDT_PACK_VERSION": 2}),
                        "key": "1/KEY00002",
                        "record": {"signature": "s", "pages": 1, "empty": False}})
    path.write_text("\n".join(rows + [other]) + "\n", encoding="utf-8")
    with pytest.raises(SmokeFailure, match="mixes 2 version stamps"):
        check_cache_rows(path, 3, _Log())
