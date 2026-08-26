# SYNC — the fork against upstream v1.7.0

*Written 2026-08-26, against upstream `edf2748` (`oscardvs/zoteus`, v1.7.0 released
2026-08-25) and fork `bae82a7` (`MinhHaDuong/zoteus`, branch `fts5-storage`).*

## What happened upstream

The maintainer answered on 2026-08-25 — not in the thread, in the tree. He merged
both contributed PRs, reviewed them, and then **built the SQLite/FTS5 backend
himself**.

| | |
|---|---|
| [#11](https://github.com/oscardvs/zoteus/pull/11) item cap configurable | **merged** 2026-08-25 as `5230c03` (`40bccc5` authored here), + his review follow-up `58943ef` |
| [#12](https://github.com/oscardvs/zoteus/pull/12) group libraries served locally | **merged** 2026-08-25 as `5a0659c` (`116b4aa` authored here), + his review follow-up `8dead91` |
| [#10](https://github.com/oscardvs/zoteus/issues/10) the 512 MB persistence ceiling | **closed** by `eee1000`, "Closes #10" |
| [#17](https://github.com/oscardvs/zoteus/pull/17) his integration PR | merged — carries #11, #12, their follow-ups, the SQLite backend, incremental updates, embedding config, desktop settings |

Both merges preserve authorship, and #17 credits this work as co-author on those
two commits. He called #12 "a carefully argued PR". Neither #11 nor #12 was
merged as sent: he found real defects in both.

**What his review caught in our code, which is the part worth reading twice.**
In #12, `listLocalGroupIds` parsed the unwrapped JSON shape only, so against the
real data-wrapped response every id parsed as `NaN` — `localGroupIds` was always
empty and the whole feature was a silent no-op. Shipped, tested, and inert. He
also paged `/users/0/groups` (we asked for one 100-item page), defaulted a
missing `capabilities.localGroupIds` to `[]` for published-interface callers, and
re-probed on late Zotero start. In #11 he made the truncation notice name *both*
bounds (`limit` and `ZOTEUS_INDEX_MAX_ITEMS`, since the cap in force is their
min), carried it into `zotero_semantic_search` results, and persisted
`itemsTotal`/`itemsAvailable` so the warning survives a reload. He wrote the
tests those units did not have.

**The storage direction he took is his own.** `eee1000` makes `SearchIndex` an
interface (`backend.ts`) with everything non-storage in `SearchIndexBase`, adds
`SqliteSearchIndex` on `node:sqlite`, and selects with
`ZOTEUS_INDEX_BACKEND=auto|sqlite|memory` — `auto` by default, SQLite wherever
the runtime provides it. Then `0013425` added incremental updates via library
version deltas. No dependency added, same as here. There is no citation of this
prototype, of its measurements, or of the (d) comment on #10 — and there is also
no sign he read them: the seams differ, and where they agree they agree on things
FTS5 forces (`unicode61 remove_diacritics 2`, `bm25()`, OR-ed terms, WAL).

## What that costs this repo

`fts5-base` is dead — both its ingredients are in upstream `main`. The fork's
`main` is 0 ahead / 14 behind; `fts5-storage` is 5 ahead / 12 behind, merge-base
`40bccc5`.

**A rebase is not the operation.** Upstream rewrote `index-manager.ts` (474 lines)
into an interface plus a base class; this branch rewrote the same file (609 lines)
to put a `PassageStore` port under the one existing `SearchIndex`. Two seams for
one problem, on the same lines, for the same reasons. The conflict is total inside
the storage layer and close to zero outside it — which is also the shape of the
answer: **retire the storage layer, port the residue.**

The prototype was not wasted; it was the argument. But the code that carried the
argument is now the code upstream already has, written by the person who maintains
it, and that is the better outcome for everything except our diff.

## What is still ours, and still missing upstream

### 1. Accent folding on the query side — a live defect in v1.7.0

Upstream's `tokenize.ts` is byte-identical to the version this branch replaced:
`text.toLowerCase().match(/[a-z0-9]+/g)`. `SqliteSearchIndex.keywordSearch` feeds
it straight into `MATCH`. The document side is folded by SQLite. Run against
upstream's own function:

```
"théorie"   -> ["th","orie"]     "Brontë"   -> ["bront"]
"Étude"     -> ["tude"]          "naïveté"  -> ["na","vet"]
"économie politique" -> ["conomie","politique"]
"Đại Việt"  -> ["vi"]
```

Every one of those goes to a token the index does not hold, and the terms are
OR-ed, so the answer is not "no results" but whichever documents happen to contain
`th`, `vi`, `tude`. Ticket 0009 measured that at jaccard 0,00 against the JSON
backend on a real French query.

His parity suite has an accent test — `matches across diacritics, which the JSON
backend cannot` — and it asserts the *other* direction: `Bronte` → `Brontë`,
unaccented query against a folded document. That direction works. The accented
query is untested and broken.

**Port:** `tokenize.ts` (148 lines) + `accent-folding.test.ts` (223), plus the
1 301-codepoint sweep in `bench/results/0009-fold-sweep/` as the evidence that the
fold emulates `unicode61 remove_diacritics 2` rather than Zotero's harder
`normalizeForSearch`. One chokepoint, both backends, no other file touched.

**The one thing he has to agree to:** the fix changes the JSON backend too (both
its sides shred today, so it is symmetrically degraded rather than wrong), which
makes the last assertion of his parity test — `expect(await memory.query('Bronte',
{mode:'keyword'})).toEqual([])` — obsolete. That test currently pins the JSON
backend's inability to fold as intended behaviour. Say so in the PR body rather
than quietly rewriting it.

### 2. Streaming migration past 200 MB

`sqlite-index.ts` sets `MAX_MIGRATION_BYTES = 200 * 1024 * 1024` and refuses to
parse above it — "that parse is the OOM" — reporting `storageNotice` and asking
for a rebuild. The reasoning is right and the conclusion is avoidable: the parse
is only the OOM if you parse the whole file.

`migrate-json.ts` here reads the file as a stream and hands `JSON.parse` one
top-level `chunks` element at a time, deliberately with no whole-file fast path
("a fast path that works on every fixture and fails on the only file anyone will
ever point at it is worse than no path at all"). Measured, three points, driver
`bench/migrate_measure.mjs`:

| | 105 MB | 321 MB | **463 MB** |
|---|---|---|---|
| migration, isolated | 13,7 s | 42,7 s | **55,5 s** |
| peak RSS (`VmHWM`) | 80,7 MiB | 97,0 MiB | **93,2 MiB** |

The library this exists for is the 463 MB one. Upstream's answer to it today is a
full re-crawl and re-embed — ten-plus minutes and real API spend by his own
account of it in `0013425`.

**Port:** `migrate-json.ts` (522) + `search-migrate-json.test.ts` (385), sink
swapped from `PassageStore` to his insert path. **Form: an issue with the table
first, not a PR.** The 200 MB cap is a deliberate, documented decision of his; a
patch that reverses it before he has seen the measurement is a patch that sits.

### 3. No corruption path

`grep -rn "corrupt\|SQLITE_" src/features/search/` upstream returns two comments
and no handler. `SQLITE_CORRUPT` propagates out of the constructor as SQLite's own
sentence, and the server does not survive it — though item lookups and
bibliographies never touch the index and could. `corruption.ts` (146) +
`search-corruption.test.ts` (181) do this, and the typed error names the file, its
sidecars and the command to run. Small and uncontroversial; check the sidecar list
against his single-file layout before sending.

### 4. A question about his delta, with an artifact attached

`action:"update"` narrows the item crawl by library version, while full text is
resolved through a `/fulltext?since=0` census of what already has text. Ticket
0012 measured, on the live local API, **library version 410 against full-text
versions 0..25 036** — two independently numbered sequences.

So: does a Zotero re-extraction bump the parent item's version? If it does not, an
update never sees newly extracted text until someone forces a full rebuild. We
have not measured that direction — 0012 was the mirror-image bug, this branch
handing an item-sequence number to a full-text-sequence endpoint. **File it as a
question with the artifact, not as a finding.**

### 5. The measurements

`docs/semantic-search.md` upstream now makes ceiling and memory claims with no
numbers behind them. Ours are on a real 7 541-item library: 5 759,6 MiB against
128,0 MiB resident and 90,87 s against 3,86 s to first answer, on **one** corpus
of 360 811 passages read by both backends — and 6,8x rather than 45x if SQLite is
charged the whole file against a JS heap that has no such remainder. Plus the wall
itself: 477 512 passages built, held, and unwritable, `Invalid string length`,
three times.

Both numbers belong in any claim, which is the discipline this repo imposed on
itself and the reason the figures are worth offering at all. Low effort, and it is
the one place the chantier becomes visible upstream.

## What to retire, deliberately

- **The `PassageStore` port**, `fts5-store.ts`, `sqlite-index.ts` and the parity,
  batching and modes suites. Superseded. They stay in git history and in the
  archive tag, not in a PR.
- **Two-stage binary vectors (0008).** A negative result: vec0's k-best structure
  costs more than linearly in k (7,7 / 18,2 / 83,6 / 216,8 ms at k=30/120/480/960
  against 121 ms for the exact float32 scan at k=30), and recall@30 runs 0,256
  binary-only to 0,998 only at a 16x pool costing 272 ms against 110. Upstream
  scans `Float32` BLOBs linearly in JS, which is the right thing at this size.
  Keep the measurement for the day someone opens an ANN issue.
- **Chunk-geometry stamping (0007).** Not applicable: his `chunker.ts` still takes
  hardcoded defaults (`size = 512, overlap = 64`; `800, 100`) and `config.ts` has
  no chunk knob, so there is no geometry to mismatch. `c0bfae6` surfaced the item
  cap and the embedding dials in desktop settings, not this. Re-file if that
  changes.
- **The concentration ceiling (0013).** Decided no-cap here; upstream unaffected.

## Mechanics

**Before quoting a single number about v1.7.0.** Five bench drivers hardcode
`ZOTEUS_SEARCH_BACKEND=json|sqlite` (`query.py`, `run_serve.py`, `run_serve2.py`,
and the recorded env in `results/json-baseline/emit.py`). Upstream's knob is
`ZOTEUS_INDEX_BACKEND=auto|sqlite|memory`. It is a one-line change per driver and
it must land before any re-measurement, or the harness will silently measure
`auto` and report it as whatever the flag said. The database path agrees
(`search-index.sqlite` beside the JSON) so `--data-dir` needs nothing.

**Order of operations.**

1. `fork/`: `git fetch up && git checkout main && git merge --ff-only up/main`.
   Tag the prototype `archive/fts5-storage-20260826`, delete `fts5-base`, and stop
   developing on `fts5-storage`.
2. Re-point the bench drivers at `ZOTEUS_INDEX_BACKEND`, then re-measure v1.7.0
   stock. His tree, his seam, our harness — that is the first honest number about
   the shipped implementation, and everything in §5 depends on it.
3. Branch `accent-fold` off `up/main` → PR. Smallest, live, self-contained, and it
   is the one that pays for itself while the rest is being discussed.
4. Issue: the migration ceiling, with the three-point table. PR only if he says
   yes.
5. PR: the corruption path.
6. Issue: the full-text delta question.
7. Docs PR: the measurements, both numbers.

**The gate.** 757 tests here were green against a tree that no longer exists. His
suite is 594 passed / 7 skipped. Every ported test runs against *his* tree before
it is sent, and the count that matters from now on is his.
