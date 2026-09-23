# Testing the sitter: the ladder

A build climbs these rungs in order, and a failure stops the climb. Every rung
below the last runs outside the author's Zotero. The ruling is `DECISIONS.md`
2026-09-23; the tracker is ticket 0815.

| Rung | Library | Runs on | Instrument |
|---|---|---|---|
| 1. Unit | none | every commit | `make check` |
| 2. Smoke | three Menagerie documents, clean room | every change | `bench/sitter_smoke_test.py` |
| 3. Menagerie | the whole Menagerie, clean room | every build meant for the author | `bench/sitter_menagerie_test.py`, widened by 0817 |
| 4. Clone | a reflink copy of the author's library | every live install | 0818 |
| 5. Dogfood | the author's own Zotero | before any release | the author |

**Clean room** means a fresh profile and a throwaway data directory, with the
run's own log confirming Zotero opened that directory and not the author's.

**Integrity, from rung 2 up.** The sitter promises to change the SDT cache and
nothing else. Each rung compares the data directory across segments of its
run — every table of every `*.sqlite` by row count and row content, every
other file in the tree by hash, the root included — and fails on any
difference outside the permitted set. The instrument is
`bench/sitter_integrity.py`; each segment's verdict is logged and carried in
the driver's run record. Rung 2 closes one segment (install, import,
preparation); rung 3 closes ten, and one of them — resume to indexed — holds
no library edit at all, so it alone says whether `Zotero.SDT.ensure()` writes
anything besides the pack.

The permitted set, as measured by ticket 0816 on Zotero 10.0.3 (a run with the
import done before the sitter was installed, then rung 3 end to end):

| Path | May | Why |
|---|---|---|
| `storage/*/.zotero-sdt-cache` | appear, change | the pack Zotero writes when the sitter calls `ensure()` — measured |
| `sdt-sitter-cache.jsonl` | appear, change, disappear | the sitter's own cache; `bootstrap.js` removes it on uninstall — measured |
| `sdt-sitter-cache.jsonl.tmp` | appear, disappear | beside the cache while it is compacted — from the code; no snapshot caught one |
| `sdt-sitter-last-shutdown.json` | appear, change | the shutdown record when diagnostics are on — from the code; no measured segment spans a shutdown with diagnostics on |

Nothing else. `ensure()` was measured writing no table of `zotero.sqlite` or
`fulltext.sqlite` and no file but the pack: no `.zotero-ft-cache`, no index
row. Both databases stay in no allow-list, so a change to either fails closed.

Excluded from the comparison, as Zotero's own churn and never evidence, and
only beside the database they belong to (`zotero.sqlite.bak` next to
`zotero.sqlite`; the same suffix anywhere else is an ordinary file):

| Pattern | Why |
|---|---|
| `*.sqlite-wal` | not hashed whole: its committed frames are read through the copy, and Zotero's idle handler vacuums and truncates it with no logical change. The frames past the last committed one are compared byte for byte instead, so a write there still fails |
| `*.sqlite-shm` | SQLite's shared-memory index of a WAL; derived state |
| `*.sqlite.tmp-wal` | a transient WAL beside a database copy Zotero makes |
| `*.sqlite*.bak` | Zotero's rotating automatic database backups |

Where the scenario itself edits the library — the import, erasing an
attachment or a whole item, re-attaching the file — the edit is declared
before its segment is checked. The tables whose row count the driver tracks
(`items`, `itemAttachments`) must move by exactly that count; the other tables
the edit was measured to write may change, uncounted; every other table must
not. Zotero indexes a document it is handed or loses, so the full-text tables
and the `.zotero-ft-cache` beside each attachment belong to the edit. The
per-edit table lists live in `bench/sitter_integrity.py` beside the functions
that declare them. The limit this buys: inside a declared edit, a table the
edit may touch is not read row by row, so a write there that keeps the counts
right would pass. Rung 2 runs the import with the sitter live, so its one
segment cannot tell an index write the sitter caused from the import's own;
rung 3's edit-free segment is what can. And a database is read through
SQLite, so the bytes SQLite never reads in the main file — its free pages,
anything past its declared page count — are outside the check; hashing the
file whole instead would fail on every idle vacuum.

**How the databases are read.** Zotero 10 on Linux holds `zotero.sqlite`
under an exclusive lock for the life of its connection, with the WAL index in
its own memory and no `-shm`, and `fulltext.sqlite` with it. A plain
read-only open of the live file is refused for as long as Zotero runs, and an
`immutable=1` open answers without error while reading the main file alone —
in the measured run it saw none of the library, all of which was still in the
WAL. So each database is copied with its `-wal` and the copy is opened, which
replays every committed frame; each snapshot is taken only once two
consecutive reads agree, so a copy torn by a write in flight is never
compared.

**Red control.** A payload built from `plugins/sdt-sitter/` with one change —
after every `ensure()`, tag the attachment `sdt-sitter-red-control` — passed
through each driver's `--xpi`, fails the check at both rungs, naming `tags`
and `itemTags`; the unmodified build passes both. The run records are in
`bench/results/0816-sitter-integrity/`. The unit suite (`tests/test_sitter_integrity.py`) holds the
same check red on a tag write, a direct `UPDATE` of one row, a stray file at
the root, and a file touched beside a pack, and since review, on bytes
appended to a WAL past its last committed frame and on a storage directory
swapped for a symlink inside a declared erase.

**Rung 3 is the whole Menagerie, wild documents included.** The corpus is
where the extremes belong — the plates volume and the 3 666-page EIS arrive
through ticket 0794 — so size and wildness are one rung, not two. The behaviour
scenario runs over it, and lifecycle is part of that scenario rather than a
rung of its own: pause (including mid-document), the attachment and item
invalidation cycles, replace, disable and re-enable, restart, uninstall.

**Rung 5 comes before release.** The author installs on his live Zotero only
after rung 4 passes, with a reflink snapshot of the data directory taken first,
and a build is released only after he has used it himself.

**The bar** for rung 3 and above reads the author's values — Excellence,
Integrity, Care — as measured criteria: every eligible attachment ends with a
pack or a named reason, a pass repeats, the interface stays responsive, the
status tells the truth. Ticket 0819 measures and proposes the numbers;
`SPEC.md` will own them once ratified.
