# SYNC — the fork against upstream v1.9.0

*Written 2026-08-26 against upstream `edf2748` (v1.7.0); updated 2026-08-27
against `309204b` (v1.8.0); updated 2026-08-28 against `bb414df`
(`oscardvs/zoteus`, v1.9.0); tracker pass 2026-08-29 — code unmoved at
`bb414df`, the movement is all in the tracker (#27–#31, see the status
table). Fork `main` is re-aligned at the same SHA. The
superseded implementation is preserved at `bae82a7` on
`archive/fts5-storage-2026-08-21`. `UPSTREAM` is the machine-readable review
baseline.*

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

`fts5-base` is retired and deleted — both its ingredients are in upstream
`main`. The fork's `main` was re-aligned with upstream at `309204b`, and
again at `bb414df` after v1.9.0 (see the status table). The historical
storage tree remains reachable only through
`archive/fts5-storage-2026-08-21` (`bae82a7`, merge-base `40bccc5`).

**A rebase is not the operation.** Upstream rewrote `index-manager.ts` (474 lines)
into an interface plus a base class; this branch rewrote the same file (609 lines)
to put a `PassageStore` port under the one existing `SearchIndex`. Two seams for
one problem, on the same lines, for the same reasons. The conflict is total inside
the storage layer and close to zero outside it — which is also the shape of the
answer: **retire the storage layer, port the residue.**

The prototype was not wasted; it was the argument. But the code that carried the
argument is now the code upstream already has, written by the person who maintains
it, and that is the better outcome for everything except our diff.

## How upstream takes contributions

`CONTRIBUTING.md` asks for no issue first: fork, topic branch, change with tests
and docs, `npm run typecheck && npm run lint && npm test` green, then "open a PR
describing the change and the motivation". Issues are listed separately, for
reporting bugs and features. There is no PR template and no linked-issue
requirement. Conventional-commit prefixes are "appreciated"; the house rules are
tests-first Vitest, `.js` on relative ESM imports, and consolidated `zotero_*`
tools over thin endpoint mirrors.

**The history says more than the rule does.** Both PRs sent from here carried no
issue and were merged with authorship preserved. What they did do is sit for four
days:

| | |
|---|---|
| Aug 21 | we open **#10** (issue) and **#11**, **#12** (PRs) — then silence |
| Aug 25 | **#13** "MAX_ITEMS = 5000" and **#14** "Multiple groups" filed by another user |
| Aug 25 | he sweeps **#9, #13, #14, #15, #16** *and* both our PRs into integration PR #17 |
| Aug 26 | **#19**, **#20** open from here; v1.7.1 ships (#18) without touching either |
| Aug 27 | **#22**, **#23** filed by @StianOby; he merges **#19** and **#20** (v1.7.2), files **#21** himself off #20's review questions, fixes #21+#22+#23 in `2f453d6`, ships v1.7.3 and **v1.8.0** — three releases in one day |
| Aug 27 | @StianOby files **#24**: a stopped local-API build cannot resume and starts again from zero — direct third-party demand for the resume slice of scoped issue A (0033) |
| Aug 28 | **#25** opens from here at 10:21 and is merged **the same day**, before 14:49, `fd51659` in `main` verbatim; he writes the changelog entry himself (`84eeade`), builds passage-anchored highlights (`87e06c0`), ships **v1.9.0** |
| Aug 28 | **#27**, **#28** open from here — ticket 0017's custody pair, both in-flight slots spent; **#29** (local fulltext-extraction fallback) and **#30** (semantic search ~100 s per query, the per-row JS vector scan) filed by @Michael-Logies — the third third-party demand wave, this time aimed at the extraction seam and the vector scan |

#13 and #14 are, in substance, the issues for #11 and #12 — filed by someone else,
four days later, describing the same two problems from the user side. He works in
batches, and the batch was triggered by demand rather than by our patches. So an
issue is not a gate, and silence is not rejection; expect days, and expect them to
end all at once. The Aug 27 row is the pattern's second confirmation — again
third-party demand (#22/#23) triggering the sweep that carried our PRs with it.
The Aug 28 row is the first counterexample on latency: #25, a lone contained
fix with no third-party trigger and no batch, filed and merged inside four
hours. Silence still is not rejection, but days are no longer the floor.

**The asymmetry that should decide the form of each contribution.** Now five for
five and two for two:

- A **contained defect with a PR** — #11, #12, #19, #20, and now #25 — gets
  reviewed and merged as ours (#19/#20/#25 without a single line changed; the
  earlier pair corrected in review).
- A **design-sized problem as an issue** — #10, and now #21 — gets him to build
  it himself. #21 is the strongest form of the pattern: he filed the follow-up
  to our own PR *himself* and shipped the fix the same day, still crediting the
  finding ("#21, thanks @MinhHaDuong").

That is not a complaint: #10 is his call to make, and his backend is a good one.
It is a fact about what each form produces, and it is why the recommendations
below name a form for every item.

## What is still ours, and still missing upstream

### 1. Accent folding on the query side — a live defect in v1.7.0

*Fixed 2026-08-27: PR #19 squash-merged as `4f61b2a`, authorship and co-author
trailer preserved, not one contributed line altered (the only head-vs-merge
diffs are base drift from v1.7.1's #18 work). `tokenize.ts` and
`accent-folding.test.ts` are byte-identical at v1.8.0 HEAD. The parity-test
rewrite flagged below was accepted as "what the case should have said in the
first place". v1.7.2 changelog: "Accented queries reach the passages they name
(#19, thanks @MinhHaDuong)". The remainder below describes the v1.7.0 defect for the record.*

At `edf2748` (v1.7.0), upstream's `tokenize.ts` was byte-identical to the version this branch replaced:
`text.toLowerCase().match(/[a-z0-9]+/g)`. `SqliteSearchIndex.keywordSearch` fed
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

**Form: a PR, no issue.** A defect with a one-file fix whose failing test is
itself the reproduction — the shape that was merged twice.

**The one thing he has to agree to:** the fix changes the JSON backend too (both
its sides shred today, so it is symmetrically degraded rather than wrong), which
makes the last assertion of his parity test — `expect(await memory.query('Bronte',
{mode:'keyword'})).toEqual([])` — obsolete. That test currently pins the JSON
backend's inability to fold as intended behaviour. Say so in the PR body rather
than quietly rewriting it.

### 2. Streaming migration past 200 MB

*Settled 2026-08-26: **skipped by decision** — not worth reversing his
documented 200 MB cap. The section stands as the record of the measurement.*

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
swapped from `PassageStore` to his insert path.

### 3. No corruption path

*Merged 2026-08-27: PR #20 squash-merged as `6e4637b` 51 seconds after #19,
same form, zero maintainer edits. The final head was `331b037` — the PR was
rebased onto v1.7.1 to reconcile `open()` with its new `busy_timeout`/WAL
handling — not the `dd1605a` the earlier status recorded. v1.7.2 changelog:
"A damaged search index no longer stops the server from starting (#20, thanks
@MinhHaDuong)", closing with his own forward reference: "Repairing it
automatically is deliberately not in this release (#21)." He then filed #21
himself and extended the work in `2f453d6` (v1.8.0) — see the corruption-work
notes under Mechanics for what that closed. The section stands as the record
of the defect; the swallowed-error holes it names are now fixed upstream.*

`grep -rn "corrupt\|SQLITE_" src/features/search/` upstream returns two comments
and no handler. `SQLITE_CORRUPT` propagates out of the constructor as SQLite's own
sentence, and the server does not survive it — though item lookups and
bibliographies never touch the index and could. `corruption.ts` (146) +
`search-corruption.test.ts` (181) do this, and the typed error names the file, its
sidecars and the command to run. Small and uncontroversial; check the sidecar list
against his single-file layout before sending. **Form: a PR, no issue** — same
shape as the accent fold.

### 4. A question about his delta, with an artifact attached

`action:"update"` narrows the item crawl by library version, while full text is
resolved through a `/fulltext?since=0` census of what already has text. Ticket
0012 measured, on the live local API, **library version 410 against full-text
versions 0..25 036** — two independently numbered sequences.

So: does a Zotero re-extraction bump the parent item's version? If it does not, an
update never sees newly extracted text until someone forces a full rebuild. We
have not measured that direction — 0012 was the mirror-image bug, this branch
handing an item-sequence number to a full-text-sequence endpoint. **Form: an
issue.** Upgraded from question to finding in cycle 2: `startIndexUpdate` keys
on `libraryVersion` alone, so post-build extraction is invisible to
`action:"update"` — I-1 in ticket 0024 carries it, X6 its empirical annex.

*Re-verified standing at v1.8.0: the update path still keys `since` on
`buildStatus().libraryVersion` (`build.ts:280`). #23's metadata-first rework
withholds the version stamp from interrupted crawls and counts unreadable
attachments, but never revisits an unchanged item whose text Zotero extracted
after the build — the finding survives his closest work to it, and I-1's text
should say so, citing #22/#23 as its neighbors.*

*2026-08-28: [#24](https://github.com/oscardvs/zoteus/issues/24) (@StianOby,
2026-08-27) asks to resume an interrupted local-API build instead of full
rebuilding — "no valid library version stamp was recorded". Third-party demand
on the same versioning seam, the trigger his batches respond to (#13/#14,
#22/#23). #24 is the resume symptom; I-1 is the distinct defect on the same
seam (a completed build never sees post-build extraction). Cite #24 as a
neighbor in I-1's text; whether I-1 is filed standalone or folded into #24's
thread is the author's call — ticket 0024 carries it.*

*2026-08-28, later: a comment from here now sits on #24, scoped to #24's own
defect and verified accurate at `309204b`: `buildIncremental` calls `reset()`
unconditionally (`index-manager.ts:546`) then crawls from `start = 0` (`:578`);
proposal, a separate build checkpoint (phase + progress identity) beside the
committed rows instead of `libraryVersion` doing double duty as freshness stamp
and resume cursor, with a seven-point regression test bounding redone work by
the persistence cadence (200 items/10 s metadata, 500/60 s full text —
`index-manager.ts:551-552`, `build.ts:362`). The comment deliberately leaves
`libraryVersion` as the freshness signal and does not surface I-1 — the
checkpoint/freshness separation it proposes is precisely what leaves I-1
standing as its own issue once resume is fixed.*

*Filed 2026-08-28 as
[#26](https://github.com/oscardvs/zoteus/issues/26): the finding wording,
the 0012 artifact linked, the unmeasured direction offered as a verification
protocol, #23 and #24's checkpoint separation cited as the stamp's other
duties. The I-label stays internal.*

### 5. The measurements

*Still open at v1.8.0: `2f453d6` rewrote the repair and metadata-first
sections of `docs/semantic-search.md` and left every measurement claim
untouched (the 337 s build row, the memory ratio, "past roughly 250k
passages"). I-2 stands, ready to file — ticket 0024.*

`docs/semantic-search.md` upstream now makes ceiling and memory claims with no
numbers behind them. Ours are on a real 7 541-item library: 5 759,6 MiB against
128,0 MiB resident and 90,87 s against 3,86 s to first answer, on **one** corpus
of 360 811 passages read by both backends — and 6,8x rather than 45x if SQLite is
charged the whole file against a JS heap that has no such remainder. Plus the wall
itself: 477 512 passages built, held, and unwritable, `Invalid string length`,
three times.

Both numbers belong in any claim, which is the discipline this repo imposed on
itself and the reason the figures are worth offering at all. Low effort, and it is
the one place this work becomes visible upstream.

## What to retire, deliberately

- **The `PassageStore` port**, `fts5-store.ts`, `sqlite-index.ts` and the parity,
  batching and modes suites. Superseded. They stay in git history and in the
  archive tag, not in a PR.
- **Two-stage binary vectors (0008).** A negative result: vec0's k-best structure
  costs more than linearly in k (7,7 / 18,2 / 83,6 / 216,8 ms at k=30/120/480/960
  against 121 ms for the exact float32 scan at k=30), and recall@30 runs 0,256
  binary-only to 0,998 only at a 16x pool costing 272 ms against 110. Upstream
  scans `Float32` BLOBs linearly in JS, which is the right thing at this size.
  Keep the measurement for the day someone opens an ANN issue — which
  arrived 2026-08-28 as #30 (see the status table).
- **Chunk-geometry stamping (0007).** Not applicable: his `chunker.ts` still takes
  hardcoded defaults (`size = 512, overlap = 64`; `800, 100`) and `config.ts` has
  no chunk knob, so there is no geometry to mismatch. `c0bfae6` surfaced the item
  cap and the embedding dials in desktop settings, not this. Re-file if that
  changes.
- **The concentration ceiling (0013).** Decided no-cap here; upstream unaffected.

## Mechanics

**Before quoting a single number about v1.7.0 or anything after it.** The five
bench drivers (`query.py`, `run_build.py`, `run_serve.py`, `run_serve2.py`, and
the recorded env in `results/json-baseline/emit.py`) used the fork's old knob,
`ZOTEUS_SEARCH_BACKEND=json|sqlite`; upstream's is
`ZOTEUS_INDEX_BACKEND=auto|sqlite|memory`. *Landed 2026-08-27 (ticket 0030):
all five now set `ZOTEUS_INDEX_BACKEND` explicitly — `memory` is the JSON
backend's upstream name — and `--backend` refuses anything outside
`sqlite|memory`, because upstream's v1.7.3 config warn-and-defaults an unknown
value to `auto` and the harness would silently measure it.* The database path
agrees (`search-index.sqlite` beside the JSON) so `--data-dir` needs nothing.

**Status, 2026-08-29** (one table; earlier states are in git history).

| | |
|---|---|
| PR #19 accent fold | **merged** 2026-08-27 as `4f61b2a` (squash, authorship + co-author trailer preserved, zero maintainer edits); shipped in v1.7.2, credited "thanks @MinhHaDuong" |
| PR #20 corrupt index | **merged** 2026-08-27 as `6e4637b`, same form; final head `331b037` (rebased onto v1.7.1's `busy_timeout` work — supersedes the `dd1605a` recorded earlier) |
| #21 his follow-up | filed by **him**, off #20's review questions; fixed same day in `2f453d6` with #22/#23 (@StianOby) and shipped as **v1.8.0** (`309204b`). The two swallowed-error holes are closed upstream — closed from our side per the sunset rule (DECISIONS.md 2026-08-27) |
| #24 local-API resume | **open**, filed 2026-08-27 by @StianOby: stopping a local-only build leaves no usable resume stamp, so the next run starts from zero. Existing upstream thread for 0033's resume slice; contribute a resume contract there rather than file a duplicate |
| PR #25 schema read-before-write | **merged** 2026-08-28, the same day it was filed: `fd51659` is in upstream `main` verbatim — SHA, authorship and committer date preserved, zero maintainer edits. He wrote the changelog entry himself (`84eeade`, "the fix landed without its entry"; credit "#25, thanks @MinhHaDuong") and shipped it in v1.9.0. Ticket 0015 closed |
| PRs #27 + #28 custody pair | **open**, both filed 2026-08-28 — ticket 0017's PR-4/PR-5. [#27](https://github.com/oscardvs/zoteus/pull/27) pins the `@huggingface/transformers` model cache under the data directory (uninstall-by-deleting-dataDir made true); [#28](https://github.com/oscardvs/zoteus/pull/28) moves the Gemini API key from the URL query string to the `x-goog-api-key` header. Fork branches `model-cache-under-datadir` (`998865e`) and `gemini-key-header` (`b6312e4`); CI green on both, Copilot-reviewed, **no maintainer response at 2026-08-29** — inside the observed latency, where silence is not rejection |
| #29 + #30 third-party demand | **open**, both filed 2026-08-28 by @Michael-Logies (a 10k-item library, running zoteus as primary). [#29](https://github.com/oscardvs/zoteus/issues/29): extract full text locally from any PDF/EPUB instead of only Zotero-indexed attachments — demand on the extraction seam, neighbor to #24/#26. [#30](https://github.com/oscardvs/zoteus/issues/30): `zotero_semantic_search` at ~100 s per query on a 255k-passage index, correctly self-diagnosed as the per-row JS vector scan, proposing sqlite-vec/`vec0`, an in-memory vector cache, or an HNSW sidecar — **the ANN issue the retired 0008 measurement was kept for** ("What to retire" below): `vec0`'s worse-than-linear k-best cost and the binary-only recall floor are measured answers to his first proposal. Demand-triggered batches followed such filings twice (#13/#14, #22/#23); no maintainer response on either yet. A comment carrying the 0008 evidence now sits on #30 (posted 2026-08-29 on the author's instruction, via a dedicated sibling session per the #26 technique; the poster re-verified it through the API — the rendered issue page does not expose comment sections to this session's fetcher, on any issue): the `vec0` O(N) sweep, the real-vector two-stage table with the 4x/8x/16x honest pairs, the mean-centring and rerank-batching results, provenance and caveats stated, artifacts linked. A second comment (D) followed 2026-08-29, [issuecomment-5461657828](https://github.com/oscardvs/zoteus/issues/30#issuecomment-5461657828), posted from this session with the forge CLI and verified through the API: the cost-model frame (vectors x bytes-per-vector x cost-per-byte, and all three of his proposals move a factor that is not the bottleneck), binary codes plus an exact rerank measured on real vectors, Matryoshka truncation as the second multiplying lever, the scan measured at his own geometry, the local-embedder feasibility tables, the BigInt trap, and the 4,1 s-versus-95 s gap left as an open question with the one-minute experiment that settles it. Ticket 0025's X1 recall half and PR #26 carry the evidence. Two paragraphs were edited in place minutes after posting, on the author's instruction, to depersonalize a design observation that addressed the reporter while asking for a decision only the maintainer can make. Edited again 2026-08-29 to add the GPU case, which the first version omitted: it presented local embedding as CPU-only and concluded the strongest model measured was "a configuration no ordinary user can run", which is false — the same vectors were built on an A4000, where bge-small/nomic/Qwen3-0.6B project to roughly 7 min / 20 min / 1,6 h for 255 703 passages (`bench/results/0025-x1-recall/gpu-feasibility.json`, derived from the run logs, upper bounds). The retraction matters to the argument: with a GPU the local path keeps the best quality AND the widest vectors AND zero egress, so "local" is not a synonym for "small". The artifacts moved to `bench/results/0025-x1-recall/` and the comment's two links were repaired in place: `0038` named a ticket that does not exist, on the contended frontier. Note the comment's driver links point at `main` and resolve only once PR #26 lands. A comment spends no in-flight slot |
| PR #31 cosine fusion | **open**, filed 2026-08-29 by the author from `fuse-cosine-loop` (`999cb1c`), on a third in-flight slot granted once (DECISIONS.md 2026-08-29). Came out of reading #30's scan rather than from the contained-PR budget, which it does not draw on. `cosine` walked every stored vector twice, and its `norm` was shared with the query-side call — `number[]` there, `Float32Array` per row — so that call site stayed polymorphic for the process's life. Fusing the two traversals measures **2,19x** on a 255 703-row index at 3072 dims (ticket 0070, `bench/cosine_fusion.mjs`); scores bit-identical, verified over a whole store, no dependency and no rebuild. **The filed body is the commit message, not the prepared one** — so it carries neither the driver/results links nor the equivalence-test description, and the author replaced the closing paragraph with his own reading: that the change buys 5–10% overall because I/O dominates. That reading is not what the measurement here shows (the row fetch is 10,01 of 33,66 µs/row, so arithmetic is the majority on this machine) and the gap it explains away is the one #30 leaves open; it is his call to make, recorded here as made. The body also carries a `Claude-Session:` line into a public repo |
| upstream | **v1.9.0** (`bb414df`, 2026-08-28): the #25 fix plus `zotero_annotate` placing highlights from the passage text itself (`87e06c0` — `pdf-locate.ts` on optional `pdfjs-dist`, files read via the local API's `/file` 302 to `file://`, nothing written on a doubtful match). His new feature leaves the search layer alone; the release's only changes under `src/features/search/` and to `docs/semantic-search.md` are PR #25's own (`sqlite-index.ts` plus a nine-line sideline section in the doc), and every measurement claim I-2 targets is untouched, so I-2 stands. Earlier: v1.7.1–v1.8.0, four releases 2026-08-26/27 |
| the train | **three in flight** (#27/#28 filed 2026-08-28, #31 filed 2026-08-29 on the granted third slot); the contained-PR budget's live remainder is two (of the five counted at DECISIONS.md 2026-08-27 — #25 merged, #27/#28 in flight). PR-3 (0016, the wipe guard alone — `busy_timeout` overtaken by v1.7.1's `80f8aa0`) is **built and validated** on fork branch `cross-library-guard`, pre-filled form in RUNBOOK.md (PR B), queued behind a free slot; STOPWORDS follow-up (0014) still waits on X2; the reserve's warm-batch condition (0019/0022) is live |
| §2 migration | skipped by decision — see §2's head note |
| §4 delta / I-1 | filed 2026-08-28 as **#26** (see §4's tail notes); open and unanswered at v1.9.0, like #24 — neither thread shows a maintainer reply (re-checked 2026-08-29). Ticket 0024 carries the response when it lands |
| §5 measurements / I-2 | untouched by `2f453d6` (see §5's head note); drafted FINAL. Reconcile before filing: the author's 2026-08-27 ruling (ticket 0024) requires trunk-measured numbers, not fork-prototype figures — RUNBOOK.md step 4 is that measurement. Upstream numbers #21–#23 are consumed — I-labels stay internal |
| gates | fold-gate waiver retired with #19's merge (0026, DESIGN.md §2.8); stock ≥v1.7.2 carries `normalizeForSearch`, so the fold gate runs green against it |
| fork | `main` **re-aligned to `bb414df`** 2026-08-28, fast-forward pushed; `schema-read-before-write` deleted by the author the same day (its one commit is `main`'s own `fd51659`; session proxies cannot delete branches — 403 — so this step is always the author's); `stopwords-follow-up` (`94d994d`, amended 2026-08-28) stays one commit atop `309204b`, now one release behind `main`; `cross-library-guard` (`61a0e38`, 2026-08-28) is one commit atop `bb414df` — ticket 0016's PR-3, unopened; `fuse-cosine-loop` (`999cb1c`, 2026-08-29) is one commit atop `bb414df` and carries PR #31; `model-cache-under-datadir` (`998865e`) and `gemini-key-header` (`b6312e4`) carry PRs #27/#28; historical storage tree preserved as `archive/fts5-storage-2026-08-21` at `bae82a7` |
| Zotero core | tracked as a surface per DECISIONS.md 2026-08-28. [zotero/zotero#6012](https://github.com/zotero/zotero/pull/6012) — dstillman's **draft** semantic-search PR (opened 2026-08-05, last activity 2026-08-26): local ONNX models via Firefox's runtime, RRF hybrid ranking, **sqlite-vec** for vectors — the same extension #30 proposes for zoteus. Added to the watch 2026-08-29 at the author's request: [zotero/zotero#1610](https://github.com/zotero/zotero/issues/1610) — dstillman's issue (2018-12-19, **closed**), "Undelete and overwrite items in target library trash for repeat cross-library copy", part of the cross-library overhaul around zotero#140; trash/undelete behavior on repeat cross-library copies sits under what the local API serves group-library indexing (#12). The rendered page does not surface the close date or closing commit — verify before citing either |
| next | the train of DESIGN.md §4 as ratified (DECISIONS.md 2026-08-26, event record 2026-08-27); live state in tickets 0014–0037 — `erg ready` is the queue |

Two things the corruption work changed about §3's own description above. The defect is worse
than "no corruption path": the server **fails to start at all**, so the 29 tools that never
read the search index die with it. And the fix turned up two adjacent holes worth their own
entries — `keywordSearch`'s catch swallows `disk I/O error` and `no such table` into an empty
result set, and the JSON backend's `loadIndex(...).catch(() => false)` does the same for a
truncated artifact. Both are in the PR as questions rather than in the diff.

*Superseded 2026-08-27: he took both questions himself — issue #21, filed by him
the day he merged #20 — and closed them in `2f453d6` (v1.8.0), still crediting
the finding ("#21, thanks @MinhHaDuong"). What #21 built, in his idiom but on
#20's seams: the error vocabulary moved verbatim from `corruption.ts` into a new
`store-faults.ts` (breaking an import cycle; `CorruptSearchIndex` stays);
`repair.ts` lets an explicit `action:"build"` — and only that call, never
startup, never a query, one attempt never a loop — delete exactly the files the
refusal named (sidecars first, database last) behind a new
`ToolContext.reopenSearchIndex` seam; the `keywordSearch` catch narrowed to true
FTS5 syntax errors, so disk I/O, `no such table`, locked and interrupted now
propagate, and mid-query corruption sticks via `noteStoreFault`; the JSON parse
failure throws a typed `SearchIndexUnreadableError` with the artifact left
exactly as found — plus a third hole he found beyond the questions: valid JSON
that is not a Zoteus index loaded as empty and was written back over the file on
the next clean shutdown. The contributed corruption test survives at HEAD except
one assertion string (the remedy text now leads with the tool call).*

**§5 is a correction, not a contribution.** `docs/semantic-search.md` already carries the
JSON-side figures, cited to issue #10 — which is ours. What is left to offer is three
corrections rather than new numbers: the build column reads as a 7x speedup where the build
is API-bound (our own uncapped SQLite build took 371.6 s against the 337 s the JSON row
reports); the memory ratio omits that RSS excludes the page cache holding the database file,
which is 45x against 6.8x depending on which question is asked; and "past roughly 250k
passages" understates a build that completes and then cannot write its artifact at 477,512.

The SQLite figures cannot be offered as measurements of *his* backend — they are the fork's
prototype — so the issue says so in as many words. That is also why §5 stopped being a docs
PR: editing his prose with numbers measured on other code is not something to do quietly.

**Order of operations**: superseded — the plan of record is DESIGN.md §4 as
ratified in DECISIONS.md, executed through tickets 0014–0035. The original
seven-step list is in git history.

**The gate.** 757 tests here were green against a tree that no longer exists. His
suite was 594 passed / 7 skipped at the cycle-2 baseline and has grown since
(86 test files at v1.8.0; `2f453d6` alone added three). Every ported test runs
against *his* tree before it is sent, and the count that matters from now on is
his — re-counted there at send time, never quoted from here.
