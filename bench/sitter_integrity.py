"""The sitter changes the SDT cache and nothing else: the check (ticket 0816).

Narrow on purpose. This serves the sitter's own ladder drivers
(`bench/sitter_smoke_test.py`, `bench/sitter_menagerie_test.py`) and nothing
else: no CLI, no generic Zotero-directory tool. Three steps, each a function --

    before = settled_snapshot(data_dir)      # every *.sqlite by row content,
    ...                                      # every other file by hash
    after = settled_snapshot(data_dir)
    assert_permitted(diff(before, after), edit=LibraryEdit(...))

`plugins/sdt-sitter/TESTING.md` states the permitted set and the excluded
housekeeping files, each with its reason; `PERMITTED` and `EXCLUDED` below are
the executable copy of that statement and must agree with it.

## How the databases are read, and why not the obvious way

Zotero 10 keeps `zotero.sqlite` in WAL mode and, on Linux, opens it with SQLite's
exclusive open and `PRAGMA main.locking_mode=EXCLUSIVE` for the life of its
connection (`chrome/content/zotero/xpcom/db.js`, `DB_LOCK_EXCLUSIVE = true`).
The WAL index then lives in Zotero's heap and no `-shm` exists. Two readers
suggest themselves and both are wrong:

- a plain `mode=ro` URI on the live path is refused -- `database is locked` --
  for as long as Zotero runs (tests/test_sitter_integrity.py reproduces it with
  SQLite's `unix-excl` VFS);
- `mode=ro&immutable=1`, the `bench/library_census.py` pattern, answers without
  error and reads the main file alone, so every row still in the WAL is
  invisible. That is a false PASS, the worst outcome this check can have.

So each database is copied together with its `-wal` into a private temporary
directory, and the copy is opened: SQLite rebuilds the WAL index from the WAL
file and replays every committed frame, so uncheckpointed rows are visible. A
main-file-only copy would be the immutable reader's blindness again, and is not
done. The copy can tear if Zotero writes mid-copy, which is why callers take
`settled_snapshot()` -- two consecutive reads that agree -- and never a single
read of a directory that may still be moving.

Each table is summarised as its row count and an order-independent content
hash (the sum, modulo 2**256, of one SHA-256 per row), streamed off a cursor:
an in-place `UPDATE` changes the hash with the count unchanged, and nothing is
held in memory but the running sum. `sqlite_master` is hashed the same way, so
a new index or table with no rows is still a change.
"""

import fnmatch
import hashlib
import os
import shutil
import sqlite3
import stat
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

#: Zotero's own churn, never the sitter's, and never evidence either way. Each
#: is a view of a database that is itself read by content, or a backup Zotero
#: rotates on its own schedule (precedent: `bench/smoke_upstream.py`).
EXCLUDED = {
    "*.sqlite-wal": "the WAL of a database read by content; its bytes move on "
                    "every checkpoint with no logical change, and its committed "
                    "frames are read through the copy",
    "*.sqlite-shm": "SQLite's shared-memory index for a WAL; derived state",
    "*.sqlite.tmp-wal": "a transient WAL beside a database copy Zotero makes",
    "*.sqlite*.bak": "Zotero's rotating automatic database backups",
}

#: What the sitter may do to the data directory, glob -> actions. `*` matches
#: within one path segment only. Read from `plugins/sdt-sitter/bootstrap.js`
#: and `Zotero.SDT.ensure()`; the measured run is what TESTING.md records.
#: `fulltext.sqlite` and every table of `zotero.sqlite` are in no allow-list:
#: a change to either fails closed.
PERMITTED = {
    # Written by Zotero's document worker when the sitter calls ensure().
    "storage/*/.zotero-sdt-cache": frozenset({"appear", "change"}),
    # The sitter's own cache; bootstrap.js removes it on uninstall.
    "sdt-sitter-cache.jsonl": frozenset({"appear", "change", "disappear"}),
    # Beside the cache while it is compacted, then renamed over it.
    "sdt-sitter-cache.jsonl.tmp": frozenset({"appear", "disappear"}),
    # The shutdown record, written when diagnostics are on.
    "sdt-sitter-last-shutdown.json": frozenset({"appear", "change"}),
}

MAIN_DB = "zotero.sqlite"


class IntegrityViolation(Exception):
    """The data directory changed outside the permitted set."""


class NotQuiesced(Exception):
    """The data directory would not hold still long enough to be read."""


@dataclass(frozen=True)
class LibraryEdit:
    """A library edit the scenario itself makes, declared before it is checked.

    `tables` maps a table of `zotero.sqlite` (or `"<db>:<table>"` for another
    database) to the row-count delta the driver tracks, or to None where the
    edit is allowed to touch the table but the driver keeps no count of it.
    Any table not named here must be unchanged. `files` widens the permitted
    set by glob for this edit alone -- the storage directory an erase removes,
    the stored file a re-attach adds.
    """

    tables: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# snapshot
# --------------------------------------------------------------------------

def _excluded(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pat) for pat in EXCLUDED)


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table_summary(con: sqlite3.Connection, sql: str) -> dict:
    acc, rows = 0, 0
    for row in con.execute(sql):
        acc = (acc + int.from_bytes(hashlib.sha256(repr(row).encode()).digest(), "big")) % (1 << 256)
        rows += 1
    return {"rows": rows, "hash": f"{acc:064x}"}


def _dump_database(path: Path) -> dict:
    """{table: {rows, hash}} for one database, read through a private copy."""
    with tempfile.TemporaryDirectory(prefix="sitter-integrity-") as tmp:
        copy = Path(tmp) / "db.sqlite"
        shutil.copyfile(path, copy)
        wal = path.with_name(path.name + "-wal")
        if wal.exists():
            shutil.copyfile(wal, copy.with_name(copy.name + "-wal"))
        con = sqlite3.connect(copy)
        try:
            tables = {"sqlite_master": _table_summary(
                con, "SELECT type, name, tbl_name, sql FROM sqlite_master")}
            for name, sql in con.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall():
                if (sql or "").upper().startswith("CREATE VIRTUAL TABLE"):
                    # Its rows live in ordinary shadow tables, dumped on their
                    # own; the module itself may not be compiled in here.
                    continue
                tables[name] = _table_summary(con, f"SELECT * FROM {_quote(name)}")
            return tables
        finally:
            con.close()


def snapshot(data_dir: Path) -> dict:
    """{"sqlite": {rel: {table: {rows, hash}}}, "files": {rel: sha256 | kind}}.

    Every `*.sqlite` is read by content, every other regular file by hash,
    the root included, `EXCLUDED` aside. A FIFO or socket is recorded by kind
    and never opened -- Zotero keeps integration pipes under the data
    directory, and opening one blocks -- and a symlink by its target.
    """
    data_dir = Path(data_dir)
    out = {"sqlite": {}, "files": {}}
    for root, dirs, files in os.walk(data_dir):
        dirs.sort()
        for name in sorted(files):
            if _excluded(name):
                continue
            path = Path(root) / name
            rel = path.relative_to(data_dir).as_posix()
            mode = os.lstat(path).st_mode
            if stat.S_ISLNK(mode):
                out["files"][rel] = "symlink:" + os.readlink(path)
            elif stat.S_ISFIFO(mode):
                out["files"][rel] = "fifo"
            elif stat.S_ISSOCK(mode):
                out["files"][rel] = "socket"
            elif name.endswith(".sqlite"):
                out["sqlite"][rel] = _dump_database(path)
            else:
                out["files"][rel] = _file_digest(path)
    return out


def settled_snapshot(data_dir: Path, *, settle: float = 5.0, timeout: float = 180.0,
                     sleep=time.sleep) -> dict:
    """A snapshot equal to the one taken `settle` seconds before it.

    A single read of a directory Zotero or the sitter is still writing records
    the clock, and a copy of a database taken mid-write can tear. Raises
    NotQuiesced, naming what kept moving, when no two reads agree in `timeout`.
    """
    deadline = time.monotonic() + timeout
    previous = snapshot(data_dir)
    while True:
        sleep(settle)
        current = snapshot(data_dir)
        if current == previous:
            return current
        if time.monotonic() >= deadline:
            moving = diff(previous, current)
            raise NotQuiesced(
                f"{data_dir} still changing after {timeout:.0f}s: "
                f"files {sorted(moving.files)}, tables {sorted(moving.tables)}")
        previous = current


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

@dataclass
class Diff:
    #: rel -> "appear" | "change" | "disappear"
    files: dict
    #: "<db>:<table>" -> {"before": rows, "after": rows}
    tables: dict

    @property
    def empty(self) -> bool:
        return not self.files and not self.tables


def _action(before, after) -> str | None:
    if before is None:
        return "appear"
    if after is None:
        return "disappear"
    return "change" if before != after else None


def diff(before: dict, after: dict) -> Diff:
    files = {}
    for rel in sorted(set(before["files"]) | set(after["files"])):
        action = _action(before["files"].get(rel), after["files"].get(rel))
        if action:
            files[rel] = action
    tables = {}
    for db in sorted(set(before["sqlite"]) | set(after["sqlite"])):
        b, a = before["sqlite"].get(db, {}), after["sqlite"].get(db, {})
        for table in sorted(set(b) | set(a)):
            if b.get(table) != a.get(table):
                tables[f"{db}:{table}"] = {
                    "before": (b.get(table) or {}).get("rows", 0),
                    "after": (a.get(table) or {}).get("rows", 0)}
    return Diff(files=files, tables=tables)


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------

def _glob_match(rel: str, pattern: str) -> bool:
    """fnmatch per path segment, so `*` never crosses a `/`."""
    parts, pats = rel.split("/"), pattern.split("/")
    return len(parts) == len(pats) and all(
        fnmatch.fnmatchcase(p, q) for p, q in zip(parts, pats))


def _allowed(rel: str, action: str, *sets) -> bool:
    return any(action in actions
               for allow in sets for pattern, actions in allow.items()
               if _glob_match(rel, pattern))


def _qualified(name: str) -> str:
    return name if ":" in name else f"{MAIN_DB}:{name}"


def check(d: Diff, permitted: dict = PERMITTED, edit: LibraryEdit | None = None) -> list[str]:
    """Every change outside the permitted set, one line each; [] is a PASS."""
    edit = edit or LibraryEdit()
    problems = []
    for rel, action in d.files.items():
        if not _allowed(rel, action, permitted, edit.files):
            problems.append(f"{rel}: {action} is not permitted")
    declared = {_qualified(k): v for k, v in edit.tables.items()}
    for name, rows in d.tables.items():
        if name not in declared:
            problems.append(
                f"{name}: changed with no declared edit "
                f"(rows {rows['before']} -> {rows['after']})")
            continue
        want = declared[name]
        moved = rows["after"] - rows["before"]
        if want is not None and moved != want:
            problems.append(
                f"{name}: row count moved by {moved}, the declared edit says {want}")
    for name, want in declared.items():
        if want not in (None, 0) and name not in d.tables:
            problems.append(f"{name}: the declared edit says {want} and the table did not change")
    return problems


def assert_permitted(d: Diff, permitted: dict = PERMITTED,
                     edit: LibraryEdit | None = None) -> None:
    problems = check(d, permitted, edit)
    if problems:
        raise IntegrityViolation("; ".join(problems))


def record(segment: str, d: Diff, permitted: dict = PERMITTED,
           edit: LibraryEdit | None = None) -> dict:
    """The verdict as a run record carries it: what changed and whether it may."""
    problems = check(d, permitted, edit)
    return {"segment": segment, "verdict": "FAIL" if problems else "PASS",
            "violations": problems, "files": d.files, "tables": d.tables,
            "declared": None if edit is None else {
                # Qualified like the diff's own keys, "<db>:<table>".
                "tables": {_qualified(k): v for k, v in edit.tables.items()},
                "files": {k: sorted(v) for k, v in edit.files.items()}}}


# --------------------------------------------------------------------------
# the scenario's own edits, as the drivers declare them
# --------------------------------------------------------------------------
#
# Each allow-list below is what clean-room runs on Zotero 10.0.3 MEASURED the
# edit to write (ticket 0816's log), not what the code was read to write: the
# import with no sitter installed at all, erase and re-attach in the rung-3
# scenario, where the edit-free segments around them showed the sitter writing
# nothing but its cache and packs. Tables whose count the driver tracks carry
# it; the rest carry None -- the edit may touch them, nothing counts them.
# Zotero indexes a document it is handed, so the full-text tables and the
# `.zotero-ft-cache` beside each attachment belong to the edit.

#: Zotero's own index of a document it was handed or lost. The three
#: `fulltextContent_*` tables are one FTS5 index's shadow tables, whose rows
#: move with its segment merges rather than per document, so they are allowed
#: as a unit: `_idx` was measured moving on import and re-attach, not on erase.
_INDEXING_TABLES = {
    "fulltextItems": None,
    "fulltext.sqlite:fulltextContent_data": None,
    "fulltext.sqlite:fulltextContent_docsize": None,
    "fulltext.sqlite:fulltextContent_idx": None,
    "fulltext.sqlite:fulltextIndexState": None,
}


def import_edit(items: int, attachments: int) -> LibraryEdit:
    """An RIS import of `items` parents with `attachments` linked files."""
    return LibraryEdit(
        tables={"items": items + attachments, "itemAttachments": attachments,
                "itemData": None, "itemDataValues": None, "creators": None,
                "itemCreators": None, "libraries": None, **_INDEXING_TABLES},
        files={"storage/*/.zotero-ft-cache": {"appear"}})


def erase_edit(storage_keys: list[str], parents: int) -> LibraryEdit:
    """`eraseTx()` of the attachments stored under `storage_keys`, and of
    `parents` parent items with them. Their storage directories go whole."""
    tables = {"items": -(len(storage_keys) + parents),
              "itemAttachments": -len(storage_keys),
              "itemData": None, "libraries": None, "syncDeleteLog": None,
              **_INDEXING_TABLES}
    if parents:
        # A parent carries the creators; an attachment has none. The creators
        # themselves stay, orphaned, until Zotero purges them.
        tables["itemCreators"] = None
    return LibraryEdit(
        tables=tables,
        files={f"storage/{key}/*": {"disappear"} for key in storage_keys})


def attach_edit(filename: str) -> LibraryEdit:
    """`Zotero.Attachments.importFromFile()` of one file: a stored copy."""
    return LibraryEdit(
        tables={"items": 1, "itemAttachments": 1, "itemData": None,
                "itemDataValues": None, "libraries": None, **_INDEXING_TABLES},
        files={f"storage/*/{filename}": {"appear"},
               "storage/*/.zotero-ft-cache": {"appear"}})


class Ledger:
    """One driver's run, cut into segments, each checked as it closes.

    `start()` takes the first settled snapshot; each `segment()` takes the
    next, checks the difference against the permitted set and the edit
    declared for that segment, keeps the record, and raises
    IntegrityViolation on a FAIL -- after recording it, so the run record
    still names what broke.
    """

    def __init__(self, data_dir: Path, log=print, *, settle: float = 5.0,
                 timeout: float = 180.0):
        self.data_dir, self.log = Path(data_dir), log
        self.settle, self.timeout = settle, timeout
        self.records: list[dict] = []
        self.last: dict | None = None

    def _snap(self) -> dict:
        return settled_snapshot(self.data_dir, settle=self.settle, timeout=self.timeout)

    def start(self) -> None:
        self.last = self._snap()
        self.log(f"integrity baseline taken over {self.data_dir}")

    def segment(self, name: str, edit: LibraryEdit | None = None) -> dict:
        if self.last is None:
            raise RuntimeError("Ledger.segment() before start()")
        after = self._snap()
        rec = record(name, diff(self.last, after), edit=edit)
        self.records.append(rec)
        self.last = after
        self.log(f"integrity {name}: {rec['verdict']} files={rec['files']} "
                 f"tables={sorted(rec['tables'])} violations={rec['violations']}")
        if rec["violations"]:
            raise IntegrityViolation(f"{name}: " + "; ".join(rec["violations"]))
        return rec
