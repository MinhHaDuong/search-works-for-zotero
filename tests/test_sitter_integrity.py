"""The sitter's integrity check (ticket 0816), over synthetic data directories.

Each red control names the bad payload it stands for: a tag written to the
library, a direct UPDATE of one row, a stray file at the data-directory root, a
file touched beside a pack. Each must fail the check, and the unmodified shape
of a run -- packs appearing, the sitter's own cache written and later removed --
must pass it.

The reading tests are the ones the ticket insists on. Zotero keeps
`zotero.sqlite` in WAL mode and, on Linux, holds it under an exclusive lock for
the life of its connection (`PRAGMA main.locking_mode=EXCLUSIVE`, and the
exclusive open that keeps the WAL index in heap memory -- Zotero 10's
`xpcom/db.js`). The writer below reproduces that with SQLite's own `unix-excl`
VFS, so the tests hold the snapshot to the conditions it meets in a live run:
an uncheckpointed row must be visible, a plain `mode=ro` reader on the live path
is refused, and an `immutable=1` reader answers without error while missing the
row -- the false PASS.
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location(
        "sitter_integrity", REPO / "bench" / "sitter_integrity.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["sitter_integrity"] = module
    spec.loader.exec_module(module)
    return module


si = load()


# --------------------------------------------------------------------------
# a synthetic data directory, shaped like the one a clean-room run leaves
# --------------------------------------------------------------------------

def zotero_writer(path: Path) -> sqlite3.Connection:
    """A connection that holds the database the way Zotero 10 does on Linux:
    exclusive open, exclusive locking mode, WAL, and no automatic checkpoint so
    written rows stay in the WAL."""
    con = sqlite3.connect(f"file:{path}?vfs=unix-excl", uri=True, isolation_level=None)
    con.execute("PRAGMA locking_mode=EXCLUSIVE")
    assert con.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    con.execute("PRAGMA wal_autocheckpoint=0")
    return con


def make_data_dir(root: Path) -> Path:
    data = root / "data"
    (data / "storage" / "AAAA1111").mkdir(parents=True)
    (data / "storage" / "BBBB2222").mkdir(parents=True)
    (data / "translators").mkdir()
    (data / "translators" / "RIS.js").write_text("// translator\n")
    lib = sqlite3.connect(data / "zotero.sqlite")
    lib.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT);
        CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, path TEXT);
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE itemTags (itemID INT, tagID INT);
        INSERT INTO items VALUES (1, 'P1'), (2, 'AAAA1111'), (3, 'BBBB2222');
        INSERT INTO itemAttachments VALUES (2, 'attachments:a.pdf'), (3, 'attachments:b.pdf');
    """)
    lib.close()
    ft = sqlite3.connect(data / "fulltext.sqlite")
    ft.executescript("""
        CREATE TABLE fulltextItems (itemID INTEGER PRIMARY KEY, indexedPages INT);
        CREATE TABLE fulltextWords (wordID INTEGER PRIMARY KEY, word TEXT);
    """)
    ft.close()
    return data


def sitter_ran(data: Path) -> None:
    """What the unmodified build leaves: one pack per attachment, its cache."""
    for key in ("AAAA1111", "BBBB2222"):
        (data / "storage" / key / ".zotero-sdt-cache").write_bytes(b"\x89SDT\r\n\x1a\n" + key.encode())
    (data / "sdt-sitter-cache.jsonl").write_text('{"key": "AAAA1111"}\n')


def verdict(before, after, **kw):
    return si.check(si.diff(before, after), **kw)


# --------------------------------------------------------------------------
# the unmodified build passes
# --------------------------------------------------------------------------

def test_the_permitted_writes_pass(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    sitter_ran(data)
    (data / "sdt-sitter-last-shutdown.json").write_text("{}")
    after = si.snapshot(data)
    assert verdict(before, after) == []
    si.assert_permitted(si.diff(before, after))  # does not raise


def test_an_unchanged_directory_diffs_empty(tmp_path):
    data = make_data_dir(tmp_path)
    assert si.diff(si.snapshot(data), si.snapshot(data)).empty


def test_the_housekeeping_files_are_excluded(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    for name in ("zotero.sqlite-wal", "zotero.sqlite-shm", "zotero.sqlite.tmp-wal",
                 "zotero.sqlite.bak", "zotero.sqlite.1.bak"):
        (data / name).write_bytes(b"churn")
    assert si.diff(before, si.snapshot(data)).empty


def test_the_cache_may_disappear_on_uninstall(tmp_path):
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    (data / "sdt-sitter-cache.jsonl.tmp").write_text("x")
    before = si.snapshot(data)
    (data / "sdt-sitter-cache.jsonl").unlink()
    (data / "sdt-sitter-cache.jsonl.tmp").unlink()
    assert verdict(before, si.snapshot(data)) == []


# --------------------------------------------------------------------------
# the four red controls the ticket names
# --------------------------------------------------------------------------

def test_red_a_payload_that_adds_a_tag(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    sitter_ran(data)
    con = sqlite3.connect(data / "zotero.sqlite")
    con.execute("INSERT INTO tags VALUES (1, 'sdt-sitter')")
    con.execute("INSERT INTO itemTags VALUES (2, 1)")
    con.commit()
    con.close()
    problems = verdict(before, si.snapshot(data))
    assert any("tags" in p for p in problems)
    assert any("itemTags" in p for p in problems)
    with pytest.raises(si.IntegrityViolation):
        si.assert_permitted(si.diff(before, si.snapshot(data)))


def test_red_a_direct_update_of_one_row(tmp_path):
    """Same row count, different content: a row-count diff alone would pass."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    con = sqlite3.connect(data / "zotero.sqlite")
    con.execute("UPDATE itemAttachments SET path = 'attachments:evil.pdf' WHERE itemID = 2")
    con.commit()
    con.close()
    problems = verdict(before, si.snapshot(data))
    assert len(problems) == 1 and "itemAttachments" in problems[0]


def test_red_a_stray_file_at_the_root(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    sitter_ran(data)
    (data / "sdt-sitter-notes.txt").write_text("stray")
    problems = verdict(before, si.snapshot(data))
    assert problems == ["sdt-sitter-notes.txt: appear is not permitted"]


def test_red_a_file_touched_beside_a_pack(tmp_path):
    data = make_data_dir(tmp_path)
    (data / "storage" / "AAAA1111" / ".zotero-ft-cache").write_text("original text")
    before = si.snapshot(data)
    sitter_ran(data)
    (data / "storage" / "AAAA1111" / ".zotero-ft-cache").write_text("rewritten")
    problems = verdict(before, si.snapshot(data))
    assert problems == ["storage/AAAA1111/.zotero-ft-cache: change is not permitted"]


def test_red_a_new_file_beside_a_pack(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    sitter_ran(data)
    (data / "storage" / "AAAA1111" / ".zotero-ft-cache").write_text("new")
    assert verdict(before, si.snapshot(data)) == [
        "storage/AAAA1111/.zotero-ft-cache: appear is not permitted"]


def test_a_fulltext_change_is_caught(tmp_path):
    """fulltext.sqlite is in no allow-list until measured: fail closed."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    con = sqlite3.connect(data / "fulltext.sqlite")
    con.execute("INSERT INTO fulltextWords VALUES (1, 'sitter')")
    con.commit()
    con.close()
    problems = verdict(before, si.snapshot(data))
    assert problems and "fulltext.sqlite" in problems[0] and "fulltextWords" in problems[0]


def test_a_new_database_is_caught(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    sqlite3.connect(data / "sdt.sqlite").execute("CREATE TABLE x (y)").connection.commit()
    problems = verdict(before, si.snapshot(data))
    assert any(p.startswith("sdt.sqlite") for p in problems)


def test_a_schema_change_with_no_rows_is_caught(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    con = sqlite3.connect(data / "zotero.sqlite")
    con.execute("CREATE INDEX evil ON items(key)")
    con.commit()
    con.close()
    assert any("sqlite_master" in p for p in verdict(before, si.snapshot(data)))


def test_pack_disappearance_without_a_declared_edit_is_caught(tmp_path):
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    (data / "storage" / "AAAA1111" / ".zotero-sdt-cache").unlink()
    assert verdict(before, si.snapshot(data)) == [
        "storage/AAAA1111/.zotero-sdt-cache: disappear is not permitted"]


# --------------------------------------------------------------------------
# declared library edits: row-count deltas on an allow-listed set of tables
# --------------------------------------------------------------------------

def erase_attachment(data: Path, key: str, item_id: int) -> None:
    con = sqlite3.connect(data / "zotero.sqlite")
    con.execute("DELETE FROM items WHERE itemID = ?", (item_id,))
    con.execute("DELETE FROM itemAttachments WHERE itemID = ?", (item_id,))
    con.commit()
    con.close()
    for f in (data / "storage" / key).iterdir():
        f.unlink()


def test_a_declared_erase_passes_with_its_exact_delta(tmp_path):
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    erase_attachment(data, "AAAA1111", 2)
    edit = si.LibraryEdit(tables={"items": -1, "itemAttachments": -1},
                          files={"storage/AAAA1111/*": {"disappear"}})
    assert verdict(before, si.snapshot(data), edit=edit) == []


def test_a_wrong_declared_delta_is_caught(tmp_path):
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    erase_attachment(data, "AAAA1111", 2)
    edit = si.LibraryEdit(tables={"items": -2, "itemAttachments": -1},
                          files={"storage/AAAA1111/*": {"disappear"}})
    problems = verdict(before, si.snapshot(data), edit=edit)
    assert problems == ["zotero.sqlite:items: row count moved by -1, the declared edit says -2"]


def test_an_undeclared_table_change_during_a_declared_edit_is_caught(tmp_path):
    """The edit cannot launder a write it did not declare."""
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    erase_attachment(data, "AAAA1111", 2)
    con = sqlite3.connect(data / "zotero.sqlite")
    con.execute("INSERT INTO tags VALUES (9, 'smuggled')")
    con.commit()
    con.close()
    edit = si.LibraryEdit(tables={"items": -1, "itemAttachments": -1},
                          files={"storage/AAAA1111/*": {"disappear"}})
    problems = verdict(before, si.snapshot(data), edit=edit)
    assert len(problems) == 1 and "tags" in problems[0]


def test_an_allow_listed_table_with_no_tracked_count_may_change(tmp_path):
    """None: the edit is allowed to touch it, the driver does not count it."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    con = sqlite3.connect(data / "zotero.sqlite")
    con.execute("INSERT INTO tags VALUES (1, 'imported')")
    con.commit()
    con.close()
    edit = si.LibraryEdit(tables={"tags": None})
    assert verdict(before, si.snapshot(data), edit=edit) == []


def test_an_edit_cannot_widen_a_file_it_does_not_name(tmp_path):
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    erase_attachment(data, "AAAA1111", 2)
    (data / "storage" / "BBBB2222" / ".zotero-sdt-cache").unlink()
    edit = si.LibraryEdit(tables={"items": -1, "itemAttachments": -1},
                          files={"storage/AAAA1111/*": {"disappear"}})
    assert verdict(before, si.snapshot(data), edit=edit) == [
        "storage/BBBB2222/.zotero-sdt-cache: disappear is not permitted"]


def test_a_glob_star_does_not_cross_a_directory(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "storage" / "AAAA1111" / "nested").mkdir()
    (data / "storage" / "AAAA1111" / "nested" / ".zotero-sdt-cache").write_bytes(b"x")
    assert verdict(before, si.snapshot(data)) == [
        "storage/AAAA1111/nested/.zotero-sdt-cache: appear is not permitted"]


# --------------------------------------------------------------------------
# the read: WAL rows visible under Zotero's exclusive lock
# --------------------------------------------------------------------------

def test_positive_control_an_uncheckpointed_row_is_visible(tmp_path):
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        before = si.snapshot(data)
        writer.execute("INSERT INTO tags VALUES (7, 'in the wal only')")
        assert (data / "zotero.sqlite-wal").stat().st_size > 0
        after = si.snapshot(data)
        assert after["sqlite"]["zotero.sqlite"]["tags"]["rows"] == 1
        assert any("tags" in p for p in verdict(before, after))
    finally:
        writer.close()


def test_a_plain_read_only_reader_is_refused_under_the_exclusive_lock(tmp_path):
    """Why the snapshot does not open the live path: Zotero's lock refuses it."""
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        writer.execute("INSERT INTO tags VALUES (7, 'x')")
        # timeout=0: the refusal is immediate; the default would wait 5 s for it.
        reader = sqlite3.connect(f"file:{data / 'zotero.sqlite'}?mode=ro", uri=True, timeout=0)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            reader.execute("SELECT count(*) FROM tags").fetchone()
        reader.close()
    finally:
        writer.close()


def test_an_immutable_reader_misses_the_wal_row_the_false_pass(tmp_path):
    """The `bench/library_census.py` pattern: no error, and the row is not there."""
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        writer.execute("INSERT INTO tags VALUES (7, 'x')")
        immutable = sqlite3.connect(
            f"file:{data / 'zotero.sqlite'}?mode=ro&immutable=1", uri=True)
        assert immutable.execute("SELECT count(*) FROM tags").fetchone()[0] == 0
        immutable.close()
        assert si.snapshot(data)["sqlite"]["zotero.sqlite"]["tags"]["rows"] == 1
    finally:
        writer.close()


def test_the_snapshot_leaves_the_live_files_untouched(tmp_path):
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        writer.execute("INSERT INTO tags VALUES (7, 'x')")
        names = sorted(p.name for p in data.iterdir())
        wal = (data / "zotero.sqlite-wal").read_bytes()
        si.snapshot(data)
        assert sorted(p.name for p in data.iterdir()) == names
        assert (data / "zotero.sqlite-wal").read_bytes() == wal
    finally:
        writer.close()


def test_a_fifo_is_recorded_not_opened(tmp_path):
    """Zotero keeps integration pipes under the data directory; opening one blocks."""
    data = make_data_dir(tmp_path)
    (data / "pipes").mkdir()
    import os
    os.mkfifo(data / "pipes" / "zotero-pipe")
    snap = si.snapshot(data)
    assert snap["files"]["pipes/zotero-pipe"] == "fifo"


# --------------------------------------------------------------------------
# quiescence and the run record
# --------------------------------------------------------------------------

def test_settled_snapshot_waits_for_two_equal_reads(tmp_path):
    data = make_data_dir(tmp_path)
    ticks = iter(range(3))

    def sleep(_s):
        n = next(ticks, None)
        if n is not None and n < 2:
            (data / "sdt-sitter-cache.jsonl").write_text(f"{n}\n")

    snap = si.settled_snapshot(data, settle=0, timeout=60, sleep=sleep)
    assert snap["files"]["sdt-sitter-cache.jsonl"] == si.snapshot(data)["files"]["sdt-sitter-cache.jsonl"]


def test_settled_snapshot_gives_up_on_a_directory_that_never_settles(tmp_path):
    data = make_data_dir(tmp_path)
    counter = iter(range(10_000))

    def sleep(_s):
        (data / "sdt-sitter-cache.jsonl").write_text(f"{next(counter)}\n")

    with pytest.raises(si.NotQuiesced, match="sdt-sitter-cache.jsonl"):
        si.settled_snapshot(data, settle=0, timeout=0.2, sleep=sleep)


def test_the_record_carries_the_verdict_and_the_changes(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    sitter_ran(data)
    (data / "stray.txt").write_text("x")
    record = si.record("smoke", si.diff(before, si.snapshot(data)))
    assert record["verdict"] == "FAIL"
    assert record["violations"] == ["stray.txt: appear is not permitted"]
    assert record["files"]["storage/AAAA1111/.zotero-sdt-cache"] == "appear"


# --------------------------------------------------------------------------
# the declared edits the drivers use, and the ledger
# --------------------------------------------------------------------------

def test_the_import_edit_counts_parents_and_attachments_together():
    edit = si.import_edit(items=3, attachments=3)
    assert edit.tables["items"] == 6 and edit.tables["itemAttachments"] == 3
    assert "tags" not in edit.tables and "itemTags" not in edit.tables


def test_an_attachment_erase_does_not_open_the_creator_tables():
    """Measured: erasing an attachment leaves itemCreators alone; a parent does not."""
    assert "itemCreators" not in si.erase_edit(["AAAA1111"], parents=0).tables
    assert si.erase_edit(["AAAA1111"], parents=1).tables["itemCreators"] is None
    assert si.erase_edit(["AAAA1111"], parents=1).tables["items"] == -2


def test_the_attach_edit_permits_only_its_own_file(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "storage" / "CCCC3333").mkdir()
    (data / "storage" / "CCCC3333" / "restore-AAAA1111.pdf").write_bytes(b"%PDF")
    (data / "storage" / "CCCC3333" / "other.pdf").write_bytes(b"%PDF")
    con = sqlite3.connect(data / "zotero.sqlite")
    con.execute("INSERT INTO items VALUES (4, 'CCCC3333')")
    con.execute("INSERT INTO itemAttachments VALUES (4, 'storage:restore-AAAA1111.pdf')")
    con.commit()
    con.close()
    assert verdict(before, si.snapshot(data), edit=si.attach_edit("restore-AAAA1111.pdf")) == [
        "storage/CCCC3333/other.pdf: appear is not permitted"]


def test_the_ledger_records_a_failing_segment_before_raising(tmp_path):
    data = make_data_dir(tmp_path)
    lines = []
    ledger = si.Ledger(data, lines.append, settle=0, timeout=5)
    ledger.start()
    sitter_ran(data)
    assert ledger.segment("prepare")["verdict"] == "PASS"
    (data / "stray.txt").write_text("x")
    with pytest.raises(si.IntegrityViolation, match="stray.txt"):
        ledger.segment("after")
    assert [r["verdict"] for r in ledger.records] == ["PASS", "FAIL"]
    assert any("integrity after: FAIL" in line for line in lines)


def test_the_record_qualifies_declared_tables_like_the_diff(tmp_path):
    """One spelling per table in a run record: `<db>:<table>`, never bare --
    a bare `creators` key also reads to the names guard as a document name."""
    data = make_data_dir(tmp_path)
    snap = si.snapshot(data)
    rec = si.record("import", si.diff(snap, snap), edit=si.import_edit(1, 1))
    assert all(":" in name for name in rec["declared"]["tables"])
    assert rec["declared"]["tables"]["zotero.sqlite:items"] == 2
