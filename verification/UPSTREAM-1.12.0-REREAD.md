# The twenty-four rows read at upstream v1.12.0

*Evidence, not authority. The first four rows (R10, R23, R12, R16) were read
2026-08-31 for ticket 0504, before the bump trigger fired. The remaining
twenty were read 2026-09-01 for ticket 0520, once ticket 0505 ruled and
ticket 0506 repaired the smoke script — the two blockers on the bump's
evidence half. Where anything here touches the design, the owning document in
`CLAUDE.md`'s document set is the record.*

**Subject:** upstream `oscardvs/zoteus` at `b05ed69a88e3a0c1ef874f57f97a0e11ddf7ec3c`,
tag `v1.12.0`, which was also `main`'s tip when the clone was taken. Every
`file:line` below addresses that tree.

**Substrate:** a fresh read-only clone in a scratch directory. Not `fork/` — a
parallel session held that checkout, and this read must not move a branch under
it.

**Method:** source read only. No server was started, no library was touched, and
the smoke was **not** re-run: ticket 0504 requires `bench/smoke_upstream.py`
repaired first, because its check 2 asserts R28, a requirement the sheet no
longer carries (ticket 0506). So every verdict below is `code` evidence, and
none of them can upgrade a row to `measured`.

The rows were read in rung order, cheapest last: R10 on goal 1, R23 on goal 2,
R12 and R16 on goal 5.

---

## R10 — my library text and my queries stay on this machine without an opt-in

*Goal 1. The row reads `shipped` / `measured`. The question ticket 0504 put to
this read, shared with ticket 0505: does #39's silent local-API-to-Web-API
fallback touch "MUST NOT leave this machine"?*

**It does not reach the index build, which is the path that carries library
text.** The changelog's wording — the fallback "drops every read and write onto
the Zotero Web API for the rest of the session" — is true of the router's
general surface and false of a running crawl, and the difference is deliberate
and documented upstream.

A build decides its API **once** and forces it on every subsequent read:

- `src/features/search/build.ts:315` — `const backend: VersionBackend =
  ctx.router.servesLocally(lib) ? 'local' : 'cloud'`, with the reasoning at
  `:310-314`: "If the API chosen here goes away mid-crawl the page fetch fails
  and the build ends in `error` with no stamp written, which is the right
  outcome."
- `src/router/library-router.ts:78` — `if (pinned) return pinned === 'local'`.
  A pinned read never consults `capabilities.localApi`, so the degradation flag
  cannot re-route it.
- Every read in the build path carries the pin: the item crawl
  (`build.ts:322`), the version census (`:406`), the full-text cursor (`:480`),
  and both new sources — `fulltext-source.ts:105,133-135,176` and
  `own-words-source.ts:89-91,152-154,203-205`.

So a local-pinned build whose desktop app stops answering **fails**. It does not
continue over the cloud.

**What the fallback does reach** is every read the router routes live, which is
the rest of the tool surface: `getItem`, `getItemChildren` and
`listCollections` take no pin (`library-router.ts:116-133,156-163`). That is the
router's ordinary local-preferred rule, and it predates v1.12.0 — the release
did not add a path, it added a *cause* and a *report*.

**It cannot fire at all without a cloud key.** `build.ts:177` says so in the
notice it emits — the Web API is "slower, rate-limited, and needing a cloud API
key" — and `library-router.ts:129-130` records the same fact from the other
side: local-only mode has no cloud fallback, because `api.zotero.org` answers
user id 0 with "Invalid user ID". On a keyless install the read fails; nothing
leaves.

**What is genuinely new in v1.12.0** is that the system's own full-text pass can
be what saturates the local API, and that the resulting degradation is now
visible instead of silent: `src/router/local-status.ts:225-232` sets
`degradedAt` on the down edge and logs that "reads and writes fall back to the
Zotero Web API"; `build.ts:167-181` turns it into `localApiDegradedAt` on
`zotero_index action:"status"`. The build subscribes only when it is itself
pinned local (`build.ts:354-355`).

**The three facts the row's own evidence rests on all still hold at v1.12.0:**
the default embedder is local (`embeddings.ts:384-402`, the `default:` case),
the model cache sits under the data directory (`:397`,
`modelCacheDir: join(config.dataDir, 'models')`), and the API key travels in a
header (`:325`, `x-goog-api-key`). The embedder also still has **no** silent
fallback: a missing local runtime yields keyword-only search
(`embeddings.ts:386-392`), never an API embedder.

**Verdict: R10 does not move on this evidence.** The row stays as written.

**But the read exposes what the row's `measured` does and does not cover.** The
smoke asserted the *embedder* axis — that effective embeddings resolve local and
the embedder is active. Read transport is a second axis, and nothing asserts it.
That is not a defect in the row; it is the coverage gap ticket 0505 poses to the
author, and this read supplies its factual half: the transport fallback exists,
it is real, it needs a cloud key, and it does not reach a running build.

---

## R23 — an index under another schema version ends up served

*Goal 2. The row reads `partial` / `measured`. Issue #34 was built by the
maintainer as PR #35 and shipped in v1.11.0.*

Split the verdict by direction, because the two directions now differ:

**Older stamp — the mechanism exists and has never fired.** A migration ladder
carries an older index forward in place: `SchemaMigration` at
`sqlite-index.ts:71-78`, the runner `migrationPath()` at `:446-457`, and
`runMigrations()` at `:470-501`, whose transaction boundary is the load-bearing
part — every rung and the new stamp share one `BEGIN IMMEDIATE` / `COMMIT`, and
a rung that throws rolls back and falls through to the sideline (`:481-494`,
`:429-437`).

And then the fact that decides how much this is worth today:
**`SCHEMA_MIGRATIONS` is the empty array** (`sqlite-index.ts:87`) and
`SCHEMA_VERSION` is still 1 (`:49`). Verified directly, not taken from the
changelog. The ladder has never carried a real index, because upstream has
never bumped past its first schema. It is exercised only by tests that inject a
fake version pair (`tests/features/search-schema-migration.test.ts`). So the
mechanism is real, tested, and untested in anger — which is the same shape as a
guard with no positive control, and worth saying plainly rather than reading the
ladder's existence as the promise kept.

**Newer stamp — still not served.** `migrationPath()` refuses when the stored
version is at or above this build's (`sqlite-index.ts:449`: "Only forwards"),
and `reconcileSchema()` sidelines unconditionally (`:437`). `sideline()`
(`:520-552`) renames the file and its sidecars to `${file}.incompatible-<stamp>`
and opens a fresh empty index at the original path. The replacement serves
nothing until an explicit `action:"build"` completes. Under R23's own wording, a
sideline plus a rebuild is not "serving".

**No file must be deleted by hand for a schema mismatch** — R23's operative
clause. `sideline()` moves the file itself and its notice says nothing was
deleted (`sqlite-index.ts:547`). Hand-deletion language survives only in the
unrelated corruption-repair path (`store-faults.ts:95-96`, `repair.ts:67`),
reachable from a schema mismatch only through a compound failure: the rename
fails, escalating to a corruption fault, and the later unlink fails too.

**What the sideline now buys:** the moved-aside file becomes a read-only vector
source. `vector-salvage.ts:80-94` returns a stored vector for a passage whose id
and text match exactly, refused unless the embedder identity matches
(`sqlite-index.ts:572`, `:617`); non-matching passages are re-embedded, not
dropped. And `priceOf()` (`sqlite-index.ts:565-591`) prices the rebuild it
prescribes before the user commits to it, with `finalizeVectors()` (`:1541-1546`)
reporting the realized reuse as the rebuild runs.

**What is now false in the row's standing sentence:** "an older stamp is
abandoned rather than migrated" is false as a statement of mechanism. What
should replace it must keep the empty ladder in view, and must keep the
newer-stamp direction unkept.

**The read-before-write half is intact.** `sqlite-index.ts:299-305` still
examines an existing file's stamp through a separate read-only handle before any
DDL touches it — PR #25's contribution, unchanged by the migration work.

---

## R12 — group libraries are searchable like my own, and one never erases another

*Goal 5. The row reads `partial` / `measured`. PR #32 was merged as `daf576b`
into v1.11.0.*

**Second clause, both documented shapes: kept.** The guard is `assertLibrary`
(`index-manager.ts:300-309`): it refuses when the store holds a stamped library
identity different from the requested one and is non-empty. It is called
synchronously at the tool boundary (`build.ts:294-295`, `:378-379`) and again
inside the engine (`index-manager.ts:789`, `:1234`), and the engine call sits
*above* the branch where `buildIncremental` chooses between clearing and
resuming — so both the `clearStore()` erasure and the resume-append shape
v1.10.0 introduced are refused before either branch is reachable. Ten cases in
`tests/features/search-library-guard.test.ts` assert it.

**First clause: no source-level asymmetry found.** The crawl, the own-words
pass, the full-text pass and the query path all take a `LibraryRef` and branch
on serving backend (local against cloud), never on library type. The v1.12.0
additions are backend-keyed too: the Electron full-text refusal
(`build.ts:303-306`) and the local-API throttle apply identically to a group and
to the personal library.

**A third seam the guard does not reach, reported as an observation and not as
an alarm.** `vector-salvage.ts` contains no occurrence of the word *library* at
all — verified by grep over the whole file — and `vectorFor(id, text)`
(`:80-94`) matches on passage id and exact text, with embedder identity checked
by the caller. Passage ids are built from Zotero item keys
(`index-manager.ts:708`, `:1785`, `:109-110`), which are unique within a library
rather than globally. Salvage is armed inside `sideline()`, at file open, before
any `assertLibrary` call exists in the stack; and the fresh replacement file is
deliberately unstamped, which is precisely the state `assertLibrary` exempts by
design (`index-manager.ts:296-298`, "An empty store or a pre-stamp index guards
nothing").

So the two gates are independent and only one of them knows about libraries.
Reaching a wrong vector needs a schema-triggered sideline of one library's file,
a build for a different library against the fresh file that replaced it, the same
embedder, an item-key collision, and byte-identical passage text. That
conjunction is remote, and none of it is a row erasure — the shape PR #32 fixed
is unaffected. What is accurate to say is narrower and still worth recording:
**library scoping does not reach the salvage path, and no test in the tree
exercises it.** Every case in the salvage block rebuilds the same library it
sidelined.

---

## R16 — my own notes and annotations are searchable

*Goal 5. The row reads `none` / `code`. Issue #33 was built by the maintainer as
PR #36 and shipped in v1.11.0.*

**Kept.** `own-words-source.ts:132-192` crawls the library for
`itemType: 'note || annotation'`, extracts note HTML to text and an annotation's
highlighted passage and comment (`:108-115`), and resolves each annotation to
its owning item through its parent attachment (`:196-232`). It is wired into
both build and update (`build.ts:487-508`; `index-manager.ts:1762-1769`,
`:1574-1667`).

Four properties worth recording, because a replacement sentence has to carry
them:

- **On by default**, which is the opposite of full text: `config.ts:185`
  `ZOTEUS_INDEX_OWN_WORDS: bool(true)` against `:181`
  `ZOTEUS_INDEX_FULLTEXT: bool(false)`. Verified directly.
- **One result slot per item.** One passage record per note or annotation, each
  carrying the parent item's key (`index-manager.ts:109-111`), with `query()`
  deduplicating hits by item (`:1886-1889`). A hit is labelled `source:"note"`
  or `source:"annotation"` (`:1893`).
- **A pre-#33 index fills its gap once**, on its first update, and reports the
  work (`index-manager.ts:1630-1637`, `:1421-1423`).
- **Deletion is found by census, not by `?since=`** — the case the issue said no
  delta could report. The full child key census is compared against the keys the
  index holds (`index-manager.ts:1566-1568`, `:1660-1661`).

**Neither v1.12.0 addition gates it.** The Electron refusal keys on the
full-text flag alone (`build.ts:303-306`), and the throttle applies only to the
full-text pass (`build.ts:169-170`: claiming it on a metadata-only build "would
be a fiction").

**What is now false in the row's standing sentence:** "every crawl asks for
top-level items, and neither a child note nor an annotation is one, so
`zotero_annotate` writes what search can never find". All of it.

---

## The remaining twenty — read 2026-09-01, for ticket 0520

*Method: source read only, same substrate discipline as above — a fresh
read-only clone, not `fork/`. The diff between the reviewed baseline and
v1.12.0 is bounded exhaustively first, then each row is checked against it,
rather than read row-by-row against an unbounded diff.*

**The window, bounded.** `git log --no-merges b132f2d..b05ed69` names 13
commits (7 merge commits wrap them, 20 total); `git diff --stat` over the same
range, excluding docs and tests, touches 27 files, every one under
`src/{api,config.ts,features/search,features/fulltext,lib,router,tools}` or a
top-level manifest. The 13 commits resolve to six upstream issues: #32
(cross-library guard), #33 (own words), #34 (schema migration and vector
salvage), #37 (Electron full-text refusal), #38 (transformers install path and
diagnostics), #39 (local-API throttle). Four are already read above —
#32→R12, #33→R16, #34→R23, #39→R10. Two are new: #37 and #38.

**#37 — refuse a full-text index build under Electron.** Adds
`src/features/search/electron.ts`. It gates one thing: `startIndexBuild`
throws before crawling when full text is requested and the host runtime is
Electron's `UtilityProcess`, working around a native-layer crash the commit
message says is unreproduced and unattributed. It touches no clause of any
row below — not R22's pause (this refuses to *start* one job on one host, it
does not stop running work), not R31's configuration validation (it is a
runtime-crash mitigation, not a proof a search configuration works), not
R13's multi-process contract.

**#38 — transformers install path and failure diagnostics.** Touches
`config.ts` and `embeddings.ts`, plus install instructions. It bears on one
row, R31, below, and nothing else — the manifest and doc changes are install
instructions, not behavior.

**The other eighteen rows are unchanged by this window: R1, R3, R4, R5, R6,
R7, R8, R13, R17, R18, R19, R22, R24, R29, R32, R33, R34, R35.** None of
their promises names a file this diff touches, and the diffstat above is
exhaustive, not sampled. Every one of these rows' standing sentences rests on
this repository's own tickets, experiments, and `bench/results/`
measurements, none of which depend on upstream's version. Re-reading them
against v1.12.0 confirms the same absence, presence or partial state the row
already recorded; nothing in their standing text changes.

### R31 — a search configuration proves it works, or fails loudly

*The row read `none` / `inferred`.*

Stock upstream still hardcodes the local MiniLM construction with no
entry-level validation before an index is created or queried — that half of
the row's finding is unchanged. What #38 (shipped in v1.11.0) adds is
diagnostic detail on one existing, reactive failure: when
`@huggingface/transformers` will not resolve or import, `embeddings.ts` now
names the configured `ZOTEUS_TRANSFORMERS_PATH` directory and, for a package
that resolves and then throws on import, the Node version, platform and
architecture it loaded under. Read directly at `embeddings.ts` and
`config.ts` in the v1.12.0 tree.

Two things this does not do. It does not validate **before** an index is
created or queried — the message fires when the embedder is first invoked,
inside a build or a query, after the promise's "before it is used" clause.
And it covers one failure class, a transformers package that will not load,
not the general promise that a search configuration proves itself on this
machine (a wrong device pinning or an unreachable API embedder are not
covered).

**Verdict: `delivered` stays `none`.** `evidence` moves `inferred` → `code`:
the specific failure path is now read at source, where nothing here had
looked before. The standing sentence updates to name what #38 did and did
not close; ticket 0488 is unchanged as the row's exit.

---

## What this read does not establish

- **Nothing above this line was run.** Every verdict in the sections above is a
  source read at one SHA. A source read cannot see a runtime behaviour, and it
  cannot upgrade a row to `measured` by itself.
- **The test counts are static reads.** Test names and case counts were read
  from the files; the upstream suite was not executed.
- **No positive control, except where the bump's own smoke re-run supplied
  one.** The seams reported above — the pinned crawl failing rather than
  falling back, the empty ladder, the unscoped salvage — were read from code
  that says what it does, not provoked into doing it, at the time of the
  source read. `bench/results/smoke-1.12.0/checks.json` (below) is the
  exception: a real server, a real cloud-served library, and a real restamped
  index file.
- **This settled two questions the ledger owns; the rest is settled now.**
  R10's transport gap was ticket 0505's question for the author, ruled
  2026-09-01 (`DECISIONS.md`); the smoke repair was ticket 0506's, done the
  same day. Both blockers cleared, so ticket 0520 bumped `UPSTREAM` to
  v1.12.0 the same session — this document's title and every row above
  reflect that bump, not a pending one.

## The smoke re-run at v1.12.0 — ticket 0520

`bench/smoke_upstream.py`, repaired (ticket 0506), was run twice against the
built fork at `b05ed69`: once with no `--index`, to get R10 and R15 without
needing a pre-existing index file; once with `--index` pointing at a 1-item
index built for the purpose (`action:"build"`, `limit:1`, metadata only,
against the real cloud-served library, `ZOTEUS_LOCAL=off` since no desktop
Zotero runs on this host), to exercise the schema-restamp checks. Output:
`bench/results/smoke-1.12.0/checks.json`.

- **R10-local-embedder: PASS.** Effective embeddings resolve `local`, the
  embedder is active, `cloud: true` / `localApi: false` on `zotero_whoami` —
  confirming directly what the source read already established: the Zotero
  API transport (cloud here, for lack of a local desktop app on this host) is
  independent of the embedder transport, which stayed local throughout.
- **R15-model-in-data-dir: PASS.** The model cache (`Xenova/all-MiniLM-L6-v2`)
  landed under the fresh data directory.
- **R23-foreign-schema-sidelined: PASS**, both directions. A copy of the
  1-item index restamped to schema `0` and to `9999` is moved aside byte-
  identical and never served.
- **R23-no-migration-path: OBSERVED**, and the observation itself was
  falsified and repaired mid-run: the check's hardcoded `consequence` string
  ("every passage must be re-embedded after any SCHEMA_VERSION change") is
  wrong at v1.12.0, and this run is what caught it. The live
  `storageNotice` on the older-stamp open states that a rebuild against the
  sidelined file salvages vectors for unchanged text rather than
  re-embedding — issue #34's vector-salvage feature, working, on a real
  restamp. `bench/smoke_upstream.py` now reports the salvage-aware
  consequence and carries the raw `storageNotice` in its detail instead of a
  fixed string that predates salvage.
- **R6-query-answers: FAIL**, expected and out of scope — no real index was
  built (the fixture is 1 metadata-only item with no embeddable content
  matching the smoke's stock queries), and R6's row does not cite this
  script.
