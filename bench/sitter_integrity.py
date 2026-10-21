"""The sitter changes the SDT cache and nothing else: the check (ticket 0816).

Narrow on purpose. This serves the sitter's own ladder drivers
(`bench/sitter_smoke_test.py`, `bench/sitter_menagerie_test.py`) and nothing
else: no CLI, no generic Zotero-directory tool. Three steps, each a function --

    before = settled_snapshot(data_dir)      # every *.sqlite by row content,
    ...                                      # every other file by hash
    after = settled_snapshot(data_dir)
    assert_permitted(diff(before, after), edit=LibraryEdit(...))

`plugins/sdt-sitter/TESTING.md` states the permitted set and the excluded
housekeeping files, each with its reason, and must agree with this module:
`PERMITTED` is what `check()` consumes; `EXCLUDED` describes, for the record,
what `_HOUSEKEEPING` and `_is_housekeeping()` admit.

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

## The bytes SQLite does not read

Reading through SQLite sees only what SQLite reads. In the WAL, that stops at
the last committed frame: anything written past it is invisible to the content
layer, and hashing the whole WAL instead would go red every time Zotero idles,
since its idle handler vacuums and truncates the WAL with no logical change
(`db.js`, `observe('idle')`). So the WAL is kept as one hash per frame, SQLite's
own recovery on the copy says how many frames it replayed, and every frame past
those must be byte-identical to what sat at the same offset before. A reset
over stale frames and a truncation both pass; bytes appended or rewritten past
the last committed frame do not (review of PR #618). The main file's free pages
and any bytes past its declared page count are still unread: see TESTING.md.
"""

import fnmatch
import hashlib
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

#: Zotero's own churn, never the sitter's, and kept out of the verdict -- not
#: out of the record: each is hashed into the snapshot's `housekeeping` map and
#: any change to it is listed in the run record (review of PR #618, round 3).
#: `<db>` is a `*.sqlite` present in the same directory: a name is excluded
#: only beside its own database, never because a stray file elsewhere shares
#: the suffix. The names are the ones Zotero writes (`db.js`: backups rotate as
#: `<db>.bak` and `<db>.<n>.bak`), and each must be what its name says --
#: otherwise it is an ordinary file and judged like one. No `-shm` is
#: excluded: Zotero 10 on Linux keeps the WAL index in its heap, and no
#: measured run left one.
EXCLUDED = {
    "<db>-wal": "the WAL of a database read by content; its committed frames "
                "are read through the copy, and the frames past them are "
                "checked byte for byte instead of hashed whole, since Zotero "
                "truncates the WAL at idle with no logical change",
    "<db>.tmp-wal": "the WAL of the temporary copy Zotero's backup writes; "
                    "must be empty (measured beside every automatic backup) "
                    "or begin with the WAL magic",
    "<db>.bak, <db>.<n>.bak": "Zotero's rotating automatic backups; must be an "
                              "SQLite database with its database's own schema",
}

_HOUSEKEEPING = re.compile(r"^(?P<db>.+\.sqlite)(?P<kind>-wal|\.tmp-wal|\.bak|\.\d+\.bak)$")
_SQLITE_HEADER = b"SQLite format 3\x00"
_WAL_MAGICS = (b"\x37\x7f\x06\x82", b"\x37\x7f\x06\x83")

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
}
# Not permitted until a run measures them, though bootstrap.js can write both:
# `sdt-sitter-cache.jsonl.tmp` (compaction) and `sdt-sitter-last-shutdown.json`
# (shutdown with diagnostics on). A run that produces one fails closed.

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

def _schema(path: Path) -> dict | None:
    """The `sqlite_master` summary of a database file, or None if it is not one."""
    with tempfile.TemporaryDirectory(prefix="sitter-integrity-") as tmp:
        copy = Path(tmp) / "db.sqlite"
        shutil.copyfile(path, copy)
        try:
            con = sqlite3.connect(copy)
            try:
                return _table_summary(con, "SELECT type, name, tbl_name, sql FROM sqlite_master")
            finally:
                con.close()
        except sqlite3.DatabaseError:
            return None


def _is_housekeeping(path: Path, kind: str, db_schema: dict | None) -> bool:
    """Whether a file already named like Zotero's churn, beside its database,
    is what that name says: a temporary WAL begins with the WAL magic; a backup
    is an SQLite database carrying its database's own schema, so neither a
    header on a payload nor another database's file passes for one."""
    with open(path, "rb") as f:
        head = f.read(len(_SQLITE_HEADER))
    if kind == ".tmp-wal":
        # Empty is admitted (author, 2026-09-23): Zotero's backup leaves one
        # beside every `.bak` it writes, and zero bytes can carry nothing.
        return head == b"" or head[:4] in _WAL_MAGICS
    return (head == _SQLITE_HEADER and db_schema is not None
            and _schema(path) == db_schema)


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


#: A WAL starts with a 32-byte header; each frame is a 24-byte header and a page.
_WAL_HEADER = 32
_FRAME_HEADER = 24


def _wal_chunks(blob: bytes) -> list[str]:
    """One SHA-256 for the header, then one per frame-sized chunk, the last
    one possibly short. Frame k (1-based) is chunk k."""
    if len(blob) < _WAL_HEADER:
        return [hashlib.sha256(blob).hexdigest()] if blob else []
    page_size = int.from_bytes(blob[8:12], "big") or 65536
    step = _FRAME_HEADER + page_size
    chunks = [hashlib.sha256(blob[:_WAL_HEADER]).hexdigest()]
    for start in range(_WAL_HEADER, len(blob), step):
        chunks.append(hashlib.sha256(blob[start:start + step]).hexdigest())
    return chunks


def _dump_database(path: Path) -> tuple[dict, dict | None]:
    """({table: {rows, hash}}, WAL layout or None), read through a private copy."""
    with tempfile.TemporaryDirectory(prefix="sitter-integrity-") as tmp:
        copy = Path(tmp) / "db.sqlite"
        shutil.copyfile(path, copy)
        wal = path.with_name(path.name + "-wal")
        wal_blob = None
        # A regular file only: a FIFO under the WAL's name would block or
        # raise here, and the walk records it by kind instead.
        if wal.exists() and stat.S_ISREG(os.lstat(wal).st_mode):
            copy_wal = copy.with_name(copy.name + "-wal")
            shutil.copyfile(wal, copy_wal)
            wal_blob = copy_wal.read_bytes()
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
            layout = None
            if wal_blob is not None:
                # SQLite's own recovery decides which frames count: the second
                # field is the number of frames in the WAL it replayed, up to
                # the last committed one; -1 when the copy is not in WAL mode.
                frames = con.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()[1]
                layout = {"frames": max(frames, 0), "chunks": _wal_chunks(wal_blob)}
            return tables, layout
        finally:
            con.close()


def snapshot(data_dir: Path) -> dict:
    """{"sqlite": {rel: {table: {rows, hash}}}, "wal": {rel: {frames, chunks}},
    "files": {rel: sha256 | kind}, "housekeeping": {rel: sha256}, "dirs": [rel]}.

    Every `*.sqlite` is read by content, every other regular file by hash,
    the root included. Zotero's housekeeping files (`EXCLUDED`) are hashed
    into their own map -- out of the verdict, never out of the record. A FIFO
    or socket is recorded by kind and never opened -- Zotero keeps integration
    pipes under the data directory, and opening one blocks -- and a symlink by
    its target, a symlinked directory included: the walk lists one among
    directories and does not descend it, so it would otherwise go unrecorded.
    """
    data_dir = Path(data_dir)
    out = {"sqlite": {}, "wal": {}, "files": {}, "housekeeping": {}, "dirs": []}
    # onerror raises: by default the walk skips a directory it cannot list --
    # one removed mid-walk, say -- and the snapshot would read short in silence.
    for root, dirs, files in os.walk(data_dir, onerror=_raise):
        dirs.sort()
        for name in dirs:
            path = Path(root) / name
            rel = path.relative_to(data_dir).as_posix()
            if path.is_symlink():
                out["files"][rel] = "symlink:" + os.readlink(path)
            else:
                # Kept to catch a file turning into a directory; a directory
                # appearing on its own is not judged (review of PR #618, round 3).
                out["dirs"].append(rel)
        siblings = set(files)
        # Named like Zotero's churn beside a database: judged after the pass,
        # once that database's schema has been read.
        deferred = []
        for name in sorted(files):
            path = Path(root) / name
            rel = path.relative_to(data_dir).as_posix()
            mode = os.lstat(path).st_mode
            match = _HOUSEKEEPING.match(name) if stat.S_ISREG(mode) else None
            if match and match["db"] in siblings:
                deferred.append((path, rel, match))
            elif stat.S_ISLNK(mode):
                out["files"][rel] = "symlink:" + os.readlink(path)
            elif stat.S_ISFIFO(mode):
                out["files"][rel] = "fifo"
            elif stat.S_ISSOCK(mode):
                out["files"][rel] = "socket"
            elif name.endswith(".sqlite"):
                out["sqlite"][rel], layout = _dump_database(path)
                if layout is not None:
                    out["wal"][rel] = layout
            else:
                out["files"][rel] = _file_digest(path)
        for path, rel, match in deferred:
            if match["kind"] == "-wal":
                continue  # read through its database's copy, frame by frame
            db_rel = rel[:len(rel) - len(path.name)] + match["db"]
            db_schema = out["sqlite"].get(db_rel, {}).get("sqlite_master")
            kind = ".tmp-wal" if match["kind"] == ".tmp-wal" else ".bak"
            target = "housekeeping" if _is_housekeeping(path, kind, db_schema) else "files"
            out[target][rel] = _file_digest(path)
    return out


def _raise(error: OSError) -> None:
    raise error


def _read(data_dir: Path) -> tuple[dict | None, str | None]:
    """A snapshot, or None and why, when a file vanished mid-walk or a copy
    tore badly enough that SQLite would not open it -- both are a directory
    still moving, not a verdict."""
    try:
        return snapshot(data_dir), None
    except (FileNotFoundError, sqlite3.DatabaseError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def settled_snapshot(data_dir: Path, *, settle: float = 5.0, timeout: float = 180.0,
                     sleep=time.sleep) -> dict:
    """A snapshot equal to the one taken `settle` seconds before it.

    A single read of a directory Zotero or the sitter is still writing records
    the clock, and a copy of a database taken mid-write can tear. Raises
    NotQuiesced, naming what kept moving, when no two reads agree in `timeout`.
    """
    deadline = time.monotonic() + timeout
    previous, why = _read(data_dir)
    while True:
        sleep(settle)
        current, why = _read(data_dir)
        if current is not None and current == previous:
            return current
        if time.monotonic() >= deadline:
            if current is None or previous is None:
                raise NotQuiesced(f"{data_dir} could not be read whole after "
                                  f"{timeout:.0f}s: {why}")
            moving = diff(previous, current)
            raise NotQuiesced(
                f"{data_dir} still changing after {timeout:.0f}s: "
                f"files {sorted(moving.files)}, tables {sorted(moving.tables)}")
        previous = current


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

#: The file action for bytes past a WAL's last committed frame that were not
#: there before: read by no layer, so never permitted.
WAL_TAIL = "write past the last committed frame"


@dataclass
class Diff:
    #: rel -> "appear" | "change" | "disappear", suffixed " as symlink" (fifo,
    #: socket) when either side is not a regular file; "change as directory"
    #: when a file and a directory traded places; or WAL_TAIL
    files: dict
    #: "<db>:<table>" -> {"before": rows, "after": rows}
    tables: dict
    #: rel -> action, for Zotero's housekeeping files: recorded, never judged
    housekeeping: dict = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not self.files and not self.tables


def _action(before, after) -> str | None:
    if before is None:
        return "appear"
    if after is None:
        return "disappear"
    return "change" if before != after else None


def _special(entry: str | None) -> str | None:
    """The kind of a non-regular entry, or None for a regular file or absence."""
    if entry is None:
        return None
    if entry.startswith("symlink:"):
        return "symlink"
    return entry if entry in ("fifo", "socket") else None


def _actions(before: dict, after: dict) -> dict:
    out = {}
    for rel in sorted(set(before) | set(after)):
        b, a = before.get(rel), after.get(rel)
        action = _action(b, a)
        if action:
            # A non-regular entry never matches an allow-list: a symlink landing
            # on the pack's name is not the pack (review of PR #618, round 3).
            kind = _special(a) or _special(b)
            out[rel] = f"{action} as {kind}" if kind else action
    return out


def diff(before: dict, after: dict) -> Diff:
    files = _actions(before["files"], after["files"])
    # A file replaced by a directory, or the reverse, is not the disappearance
    # or appearance the allow-list may permit at that name.
    before_dirs, after_dirs = set(before.get("dirs", [])), set(after.get("dirs", []))
    for rel in (set(before["files"]) & after_dirs) | (set(after["files"]) & before_dirs):
        if " as " not in files.get(rel, ""):  # "as symlink" already says more
            files[rel] = "change as directory"
    tables = {}
    for db in sorted(set(before["sqlite"]) | set(after["sqlite"])):
        b, a = before["sqlite"].get(db, {}), after["sqlite"].get(db, {})
        for table in sorted(set(b) | set(a)):
            if b.get(table) != a.get(table):
                tables[f"{db}:{table}"] = {
                    "before": (b.get(table) or {}).get("rows", 0),
                    "after": (a.get(table) or {}).get("rows", 0)}
    for db, layout in after.get("wal", {}).items():
        old = before.get("wal", {}).get(db, {}).get("chunks", [])
        for k in range(layout["frames"] + 1, len(layout["chunks"])):
            if k >= len(old) or old[k] != layout["chunks"][k]:
                files[f"{db}-wal"] = WAL_TAIL
                break
    return Diff(files=files, tables=tables, housekeeping=_actions(
        before.get("housekeeping", {}), after.get("housekeeping", {})))


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


def check(d: Diff, edit: LibraryEdit | None = None) -> list[str]:
    """Every change outside PERMITTED and the declared edit, one line each;
    [] is a PASS."""
    edit = edit or LibraryEdit()
    problems = []
    for rel, action in d.files.items():
        if not _allowed(rel, action, PERMITTED, edit.files):
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


def assert_permitted(d: Diff, edit: LibraryEdit | None = None) -> None:
    problems = check(d, edit)
    if problems:
        raise IntegrityViolation("; ".join(problems))


def record(segment: str, d: Diff, edit: LibraryEdit | None = None) -> dict:
    """The verdict as a run record carries it: what changed and whether it may."""
    problems = check(d, edit)
    return {"segment": segment, "verdict": "FAIL" if problems else "PASS",
            "violations": problems, "files": d.files, "tables": d.tables,
            "housekeeping": d.housekeeping,
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
#: The three `fulltextContentCJK_*` tables are the same index's CJK twin: four
#: Latin-script PDFs never touched them, and ticket 0821's first wider import
#: (50 Menagerie files, the sitter paused, no pack written) moved all three.
#: They belong to a declared library edit only; the edit-free segment still
#: fails on any change to them.
_INDEXING_TABLES = {
    "fulltextItems": None,
    "fulltext.sqlite:fulltextContent_data": None,
    "fulltext.sqlite:fulltextContent_docsize": None,
    "fulltext.sqlite:fulltextContent_idx": None,
    "fulltext.sqlite:fulltextContentCJK_data": None,
    "fulltext.sqlite:fulltextContentCJK_docsize": None,
    "fulltext.sqlite:fulltextContentCJK_idx": None,
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


def relaunch_edit() -> LibraryEdit:
    """Zotero starting again over a library it already holds (ticket 0822).

    Not a library edit the scenario makes, but a write the host makes on its
    own after a launch, measured on the whole Menagerie on Zotero 10.0.3:
    Zotero's keyword indexer catches up on documents whose
    `.zotero-ft-cache` the import left unprocessed, one `fulltextItems` and
    one `fulltextIndexState` row each. Over the same library the sitter's
    own segments -- resume to indexed, where it did all its work, and
    disable and re-enable -- moved neither, and after the relaunch it
    finished no document. Only those tables: the FTS content tables did not
    move, so they stay unpermitted here.

    The `version` table is NOT admitted (author, 2026-09-24). Its
    `repository` and `lastcheck` rows move only with Zotero's automatic
    repository check, which the rung-3 profile turns off
    (`automaticScraperUpdates`); with it on, the relaunch segment fails.
    """
    return LibraryEdit(tables={"fulltextItems": None,
                               "fulltext.sqlite:fulltextIndexState": None})


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
                 f"tables={sorted(rec['tables'])} housekeeping={rec['housekeeping']} "
                 f"violations={rec['violations']}")
        if rec["violations"]:
            raise IntegrityViolation(f"{name}: " + "; ".join(rec["violations"]))
        return rec
