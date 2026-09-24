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
    after = si.snapshot(data)
    assert verdict(before, after) == []
    si.assert_permitted(si.diff(before, after))  # does not raise


def test_an_unchanged_directory_diffs_empty(tmp_path):
    data = make_data_dir(tmp_path)
    assert si.diff(si.snapshot(data), si.snapshot(data)).empty


#: The first four bytes of a WAL file (big-endian checksum variant).
WAL_MAGIC = b"\x37\x7f\x06\x83"


def test_the_housekeeping_files_are_excluded(tmp_path):
    """Zotero's own names, beside their database, each with its own header:
    `db.js` rotates backups as `<db>.bak` and `<db>.<n>.bak`."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    backup = (data / "zotero.sqlite").read_bytes()
    (data / "zotero.sqlite.bak").write_bytes(backup)
    (data / "zotero.sqlite.12.bak").write_bytes(backup)
    (data / "zotero.sqlite.tmp-wal").write_bytes(WAL_MAGIC + b"\x00" * 28)
    d = si.diff(before, si.snapshot(data))
    assert d.empty and si.check(d) == []
    # Excluded from the verdict, never from the record (review round 3).
    assert d.housekeeping == {"zotero.sqlite.12.bak": "appear", "zotero.sqlite.bak": "appear",
                              "zotero.sqlite.tmp-wal": "appear"}


def test_the_cache_may_disappear_on_uninstall(tmp_path):
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    (data / "sdt-sitter-cache.jsonl").unlink()
    assert verdict(before, si.snapshot(data)) == []


@pytest.mark.parametrize("name", ["sdt-sitter-cache.jsonl.tmp", "sdt-sitter-last-shutdown.json"])
def test_red_an_unmeasured_sitter_file_fails_closed(tmp_path, name):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / name).write_text("{}")
    assert verdict(before, si.snapshot(data)) != []


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


def _rows(before, after):
    return {"before": before, "after": after}


def test_the_relaunch_edit_admits_what_a_relaunch_was_measured_writing():
    measured = si.Diff(files={}, tables={
        "zotero.sqlite:version": _rows(10, 10),
        "zotero.sqlite:fulltextItems": _rows(101, 104),
        "fulltext.sqlite:fulltextIndexState": _rows(101, 104)})
    assert si.check(measured, si.relaunch_edit()) == []
    # The same diff with no declared edit is the live run's first FAIL.
    assert len(si.check(measured)) == 3


@pytest.mark.parametrize("table,rows,problem", [
    ("zotero.sqlite:version", _rows(10, 11), "row count moved by 1"),
    ("fulltext.sqlite:fulltextContent_data", _rows(5, 6), "no declared edit"),
    ("zotero.sqlite:itemTags", _rows(0, 1), "no declared edit"),
])
def test_the_relaunch_edit_admits_nothing_more(table, rows, problem):
    diff = si.Diff(files={}, tables={table: rows})
    assert problem in si.check(diff, si.relaunch_edit())[0]


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


# --------------------------------------------------------------------------
# review round 1 (PR #618): bytes no reader reads, and paths the walk skipped
# --------------------------------------------------------------------------

def test_red_bytes_appended_to_the_wal_past_its_last_frame(tmp_path):
    """SQLite stops at the first invalid frame, so the SQL layer never sees
    them, and the file layer excluded the WAL by name: a blind spot."""
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        writer.execute("INSERT INTO tags VALUES (7, 'x')")
        before = si.snapshot(data)
        with open(data / "zotero.sqlite-wal", "ab") as f:
            f.write(b"payload" * 700)
        assert verdict(before, si.snapshot(data)) == [
            "zotero.sqlite-wal: write past the last committed frame is not permitted"]
    finally:
        writer.close()


def test_a_committed_wal_write_under_a_declared_edit_passes(tmp_path):
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        writer.execute("INSERT INTO tags VALUES (7, 'x')")
        before = si.snapshot(data)
        writer.execute("INSERT INTO tags VALUES (8, 'y')")
        assert verdict(before, si.snapshot(data), edit=si.LibraryEdit(tables={"tags": 1})) == []
    finally:
        writer.close()


def test_a_wal_reset_over_stale_frames_passes(tmp_path):
    """After a RESTART checkpoint SQLite writes from the top again and leaves
    the old frames behind, unread and unchanged: legitimate."""
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        for n in range(40):
            writer.execute("INSERT INTO tags VALUES (?, ?)", (100 + n, "z" * 2000))
        before = si.snapshot(data)
        writer.execute("PRAGMA wal_checkpoint(RESTART)")
        writer.execute("INSERT INTO tags VALUES (9, 'after reset')")
        after = si.snapshot(data)
        layout = after["wal"]["zotero.sqlite"]
        assert layout["frames"] < before["wal"]["zotero.sqlite"]["frames"]
        # Not vacuous: stale frames really do sit past the committed ones.
        assert len(layout["chunks"]) > layout["frames"] + 1
        assert verdict(before, after, edit=si.LibraryEdit(tables={"tags": 1})) == []
    finally:
        writer.close()


def test_zoteros_idle_truncate_checkpoint_passes(tmp_path):
    """Zotero's idle handler runs `PRAGMA wal_checkpoint(TRUNCATE)` (db.js):
    the WAL empties with no change to the content."""
    data = make_data_dir(tmp_path)
    writer = zotero_writer(data / "zotero.sqlite")
    try:
        writer.execute("INSERT INTO tags VALUES (7, 'x')")
        before = si.snapshot(data)
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        assert (data / "zotero.sqlite-wal").stat().st_size == 0
        assert verdict(before, si.snapshot(data)) == []
    finally:
        writer.close()


def test_red_a_directory_swapped_for_a_symlink_inside_a_declared_erase(tmp_path):
    """The walk lists a symlinked directory among directories, never files."""
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    erase_attachment(data, "AAAA1111", 2)
    (data / "storage" / "AAAA1111").rmdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "payload.bin").write_bytes(b"x")
    (data / "storage" / "AAAA1111").symlink_to(elsewhere, target_is_directory=True)
    edit = si.LibraryEdit(tables={"items": -1, "itemAttachments": -1},
                          files={"storage/AAAA1111/*": {"disappear"}})
    assert verdict(before, si.snapshot(data), edit=edit) == [
        "storage/AAAA1111: appear as symlink is not permitted"]


def test_red_a_housekeeping_name_away_from_its_database(tmp_path):
    """The exclusions cover Zotero's churn beside a database, not any file
    that happens to share the suffix."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "storage" / "AAAA1111" / "exfil.sqlite-evil.bak").write_bytes(b"x")
    (data / "zotero.sqlite.bak").write_bytes((data / "zotero.sqlite").read_bytes())
    assert verdict(before, si.snapshot(data)) == [
        "storage/AAAA1111/exfil.sqlite-evil.bak: appear is not permitted"]


def test_settled_snapshot_retries_a_read_torn_by_a_vanishing_file(tmp_path, monkeypatch):
    data = make_data_dir(tmp_path)
    real = si.snapshot
    calls = []

    def flaky(d):
        calls.append(1)
        if len(calls) == 2:
            raise FileNotFoundError("vanished mid-walk")
        return real(d)

    monkeypatch.setattr(si, "snapshot", flaky)
    assert si.settled_snapshot(data, settle=0, timeout=60, sleep=lambda _s: None) == real(data)
    assert len(calls) >= 3


# --------------------------------------------------------------------------
# review round 2 (PR #618): an excluded name must be what Zotero writes
# --------------------------------------------------------------------------

def test_red_an_open_wildcard_backup_name_beside_the_database(tmp_path):
    """`*.sqlite*.bak` let any `zotero.sqlite-<anything>.bak` hide beside the
    one database that is always there; Zotero only writes `.bak`, `.<n>.bak`."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite-EXFIL.bak").write_bytes((data / "zotero.sqlite").read_bytes())
    assert verdict(before, si.snapshot(data)) == [
        "zotero.sqlite-EXFIL.bak: appear is not permitted"]


def test_red_a_backup_name_that_is_not_a_database(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite.bak").write_bytes(b"ARBITRARY PAYLOAD" * 100)
    assert verdict(before, si.snapshot(data)) == [
        "zotero.sqlite.bak: appear is not permitted"]


def test_red_a_tmp_wal_name_that_is_not_a_wal(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite.tmp-wal").write_bytes(b"ARBITRARY PAYLOAD" * 100)
    assert verdict(before, si.snapshot(data)) == [
        "zotero.sqlite.tmp-wal: appear is not permitted"]


def test_an_empty_tmp_wal_beside_a_backup_is_housekeeping(tmp_path):
    """Measured in every whole-Menagerie run (0821): Zotero's automatic backup
    writes `<db>.bak` and a zero-byte `<db>.tmp-wal` beside it."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite.bak").write_bytes((data / "zotero.sqlite").read_bytes())
    (data / "zotero.sqlite.tmp-wal").write_bytes(b"")
    d = si.diff(before, si.snapshot(data))
    assert si.check(d) == []
    assert d.housekeeping == {"zotero.sqlite.bak": "appear", "zotero.sqlite.tmp-wal": "appear"}


def test_red_a_one_byte_tmp_wal_is_not_empty(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite.tmp-wal").write_bytes(b"\x00")
    assert verdict(before, si.snapshot(data)) == [
        "zotero.sqlite.tmp-wal: appear is not permitted"]


def test_red_a_shm_file_zotero_on_linux_never_writes(tmp_path):
    """Measured: Zotero 10 on Linux keeps the WAL index in its heap, and no run
    left a `-shm`; one appearing is not Zotero's churn."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite-shm").write_bytes(b"\x00" * 32768)
    assert verdict(before, si.snapshot(data)) == [
        "zotero.sqlite-shm: appear is not permitted"]


def test_a_directory_vanishing_mid_walk_raises_rather_than_reads_short(tmp_path, monkeypatch):
    """os.walk skips an unlistable directory silently unless told otherwise, and
    a snapshot missing a subtree would compare as a disappearance or not at all."""
    import os
    data = make_data_dir(tmp_path)
    real = os.scandir

    def scandir(path="."):
        if str(path).endswith("AAAA1111"):
            raise FileNotFoundError(path)
        return real(path)

    monkeypatch.setattr(os, "scandir", scandir)
    with pytest.raises(FileNotFoundError):
        si.snapshot(data)


def test_a_dangling_symlink_is_recorded(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "storage" / "ZZZZ9999").symlink_to(tmp_path / "nowhere", target_is_directory=True)
    assert verdict(before, si.snapshot(data)) == ["storage/ZZZZ9999: appear as symlink is not permitted"]


# --------------------------------------------------------------------------
# review round 3 (PR #618): a permitted name must still be a regular file,
# and an excluded one must still be recorded
# --------------------------------------------------------------------------

def test_red_a_symlink_where_a_pack_may_appear(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (tmp_path / "elsewhere.bin").write_bytes(b"x")
    (data / "storage" / "AAAA1111" / ".zotero-sdt-cache").symlink_to(tmp_path / "elsewhere.bin")
    assert verdict(before, si.snapshot(data)) == [
        "storage/AAAA1111/.zotero-sdt-cache: appear as symlink is not permitted"]


def test_red_the_cache_swapped_for_a_symlink(tmp_path):
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    (data / "sdt-sitter-cache.jsonl").unlink()
    (data / "sdt-sitter-cache.jsonl").symlink_to(tmp_path / "anywhere")
    assert verdict(before, si.snapshot(data)) == [
        "sdt-sitter-cache.jsonl: change as symlink is not permitted"]


def test_red_a_fifo_where_the_cache_may_appear(tmp_path):
    import os
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    os.mkfifo(data / "sdt-sitter-cache.jsonl")
    assert verdict(before, si.snapshot(data)) == [
        "sdt-sitter-cache.jsonl: appear as fifo is not permitted"]


def test_a_rewritten_backup_body_is_recorded(tmp_path):
    """A name and header that pass let the file out of the verdict, not out of
    the record: a body rewritten between segments shows as a change."""
    data = make_data_dir(tmp_path)
    (data / "zotero.sqlite.bak").write_bytes((data / "zotero.sqlite").read_bytes())
    before = si.snapshot(data)
    con = sqlite3.connect(data / "zotero.sqlite.bak")
    con.execute("INSERT INTO tags VALUES (99, 'hidden in the backup')")
    con.commit()
    con.close()
    d = si.diff(before, si.snapshot(data))
    assert si.check(d) == []
    assert d.housekeeping == {"zotero.sqlite.bak": "change"}
    assert si.record("seg", d)["housekeeping"] == {"zotero.sqlite.bak": "change"}


def test_red_a_backup_that_is_another_databases(tmp_path):
    """Cross-database disguise: a real SQLite file, but not a backup of the
    database it is named after -- its schema says so."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite.bak").write_bytes((data / "fulltext.sqlite").read_bytes())
    assert verdict(before, si.snapshot(data)) == ["zotero.sqlite.bak: appear is not permitted"]


def test_red_a_backup_with_a_header_and_a_garbage_body(tmp_path):
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "zotero.sqlite.3.bak").write_bytes(b"SQLite format 3\x00" + b"\xff" * 5000)
    assert verdict(before, si.snapshot(data)) == ["zotero.sqlite.3.bak: appear is not permitted"]


# --------------------------------------------------------------------------
# review round 3 (PR #618, comment tier): the WAL path's own FIFO guard, and
# a directory standing where a file was allowed to vanish
# --------------------------------------------------------------------------

def test_red_a_fifo_named_as_the_wal_is_recorded_not_opened(tmp_path):
    """The database's copy read `<db>-wal` with no type check, bypassing the
    walk's own refusal to open a FIFO."""
    import os
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    os.mkfifo(data / "zotero.sqlite-wal")
    assert verdict(before, si.snapshot(data)) == [
        "zotero.sqlite-wal: appear as fifo is not permitted"]


def test_red_a_directory_where_the_cache_was_allowed_to_vanish(tmp_path):
    """The cache may disappear; a directory in its place is not a disappearance."""
    data = make_data_dir(tmp_path)
    sitter_ran(data)
    before = si.snapshot(data)
    (data / "sdt-sitter-cache.jsonl").unlink()
    (data / "sdt-sitter-cache.jsonl").mkdir()
    assert verdict(before, si.snapshot(data)) == [
        "sdt-sitter-cache.jsonl: change as directory is not permitted"]


def test_a_new_storage_directory_alone_is_not_a_change(tmp_path):
    """Directories are recorded to catch a file turning into one, not to judge
    the storage directories Zotero makes for every pack."""
    data = make_data_dir(tmp_path)
    before = si.snapshot(data)
    (data / "storage" / "CCCC3333").mkdir()
    (data / "storage" / "CCCC3333" / ".zotero-sdt-cache").write_bytes(b"pack")
    assert verdict(before, si.snapshot(data)) == []
