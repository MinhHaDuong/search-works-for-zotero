# SYNC — the fork against upstream v1.13.0

*Written 2026-08-26 against upstream `edf2748` (v1.7.0); updated 2026-08-27
against `309204b` (v1.8.0); updated 2026-08-28 against `bb414df`
(v1.9.0); updated 2026-08-29 against `b132f2d` (`oscardvs/zoteus`,
v1.10.0), which drained the tracker: every open issue closed, all three of
our PRs merged verbatim, and the two-stage vector search built by the
maintainer in the same 45 minutes (see the status table); updated
2026-08-30 with no upstream movement — recording issue #34, the post-close
end-to-end measurement on #30, and the #24/#26 closes the v1.10.0 sweep
already implied; updated 2026-08-31 against `b05ed69` (v1.12.0), which
drained it a second time — PR #32 merged, issues #33 and #34 both built by
the maintainer and closed, two releases shipped in one day; updated
2026-09-01 with the stopword series' first filing — **PR #45 (degenerate
query) is in flight**, the only item of ours that is, spending the held
stopwords-follow-up slot under the one-slot-per-PR ruling (`DECISIONS.md`
2026-09-01); updated 2026-09-01 again with the author's grant of the two
remaining slots — PRs 2 (diacritics + optional gated expansion,
`pr2-expansion` `6a201fa`) and 3 (library-derived droplist,
`pr3-droplist-r5` `11385a2`) file next, bodies as drafted under
`verification/`, filing recorded here once each PR page is verified —
**filed the same day and verified on their pages: PR #46 (diacritics +
optional expansion, head `6a201fa`) and PR #47 (droplist, head `11385a2`),
both OPEN**; with #45 that is the whole 0091 series in flight, all three
granted slots spent, and #47's head stacks on `6b7c152` (pre-flag), so it
carries #46's substance minus the flag commit until #46 merges and #47
rebases; updated 2026-09-01 a third time — ticket 0505 ruled (disclosure,
not a new requirement), ticket 0506 repaired the smoke script, and ticket
0520 bumped the baseline: `UPSTREAM` now names v1.12.0, all twenty-four
rows re-read (`verification/UPSTREAM-1.12.0-REREAD.md`, extended from the
four ticket 0504 read), and the smoke re-run against a fresh 1-item build
over the cloud API (`bench/results/smoke-1.12.0/checks.json`) keeps R10
and R23 at `measured` rather than letting the bump silently demote them.
The reviewed baseline in `UPSTREAM` was v1.12.0 through the events below, then
bumped a second time by ticket 0618, described after them; updated 2026-09-03 —
**the whole 0091 series merged** (PRs #45, #46 and #47, all at 07:58, no changes
asked for), which empties every in-flight slot; one minute later the maintainer
**closed issue #43 by building local model selection himself**, the same shape
as the storage layer and as #33/#34. What he shipped, verified at `76bbb07`:
`ZOTEUS_EMBEDDING_MODEL` reaches the local provider as a raw Hugging Face id, E5
prefixes are applied by a regex on that id with `ZOTEUS_EMBEDDING_PREFIXES` as
override, and identity becomes `local:<model>`. Two vector-affecting properties
stayed behind. `pooling: 'mean'` is still hardcoded for every model the new knob
can name, and `dtype` is absent from the file. Ticket 0612 measured the first
and drafted a filing for both (`verification/POOLING-DEFECT-0612.md`). In the
same thread, after the close, **Michael-Logies asked for a quantized entry** for
ChromeOS-class machines and named dtype-in-identity as its precondition, which
is the registry entry by another route. The `pr43-minilm-e5-registry` branch
offered on #43 is now 14 ahead and 33 behind and touches the file he rewrote:
it needs rebuilding onto his seam, not rebasing onto it. **He then shipped the
dtype work the same afternoon** (`230183d` at 13:18, merged `b0e0bc8`):
`ZOTEUS_EMBEDDING_DTYPE` selects the weight precision and enters the identity as
`local:<model>@<dtype>`, which is Michael-Logies' quantized entry delivered
within hours of the ask and the precondition the maintainer had named for it.
It is also the knob ticket 0220 proposed and this repo withdrew on 2026-08-29 —
shipped by him, soundly, with the identity fix that withdrawal said a knob could
not travel without. Pooling was now the one vector-affecting property still
written at the call site, one occurrence in the whole `src` tree; updated
2026-09-03 a further time — **the pooling fix filed and merged**. Rebuilt on a
fork review station (`MinhHaDuong/zoteus#10`, base pinned at `b0e0bc8`) through
two adversarial review rounds and a decorrelated seat, then **filed as
`oscardvs/zoteus#51`-fixing PR #52** (a curated `MODEL_POOLING` table,
`ZOTEUS_EMBEDDING_POOLING` override, and the pooling suffixed into the embedder
identity on `fp32`'s own rule) after the maintainer opened #51 himself,
credited the finding, and said on #43 he was holding the release for it. A
comment on #43 carried the size of the loss and pointed at #52. **He merged #52
verbatim, nineteen minutes after filing, no review comments** — the thirteenth
of thirteen PRs from this fork, none rejected, none rebuilt. #51 closed with it.
Ticket 0612's own close is still ours to do.

In the same window, on `b0e0bc8` (v1.13.0 plus four commits), the maintainer
drained the tracker a third time: closing #37, #43, #44, #48 and #49, and moving
the index schema stamp for the first time since v1.7.0 — our #46 changed the FTS
tokenizer, so upstream now carries a real migration ladder and its first rung is
ours. Ticket 0618 bumped the baseline and re-read all twenty-three rows
(`verification/UPSTREAM-1.13.0-REREAD.md`). The reviewed baseline in `UPSTREAM`
now names v1.13.0 and is current with `main`; it pins main's TIP rather than the
v1.13.0 tag, four commits earlier, because `upstream-status` compares against
`main` and a tag pin is red on the day it is written. The
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
| Aug 29 | **#31** opens from here at 07:59 and merges at 11:30. In 45 minutes he merges **#31**, **#27**, **#28** — all three verbatim, no follow-up commit on any — then ships local extraction (#29), build resume and the full-text cursor (#24, #26), and the **two-stage vector search** (#30), closing every open issue in the tracker and releasing **v1.10.0**. **#32** (the wipe guard) opens from here the same afternoon, followed by issues **#33** (own words) and **#34** (no schema-migration path) and by a post-close end-to-end measurement on #30: v1.9.0 against v1.10.0 on a real 93 022-passage index, about 49x on the median |
| Aug 31 | he merges **#32** (`daf576b`, our commit verbatim, no follow-up), then **builds both open issues himself** — own words (#33) and the index migration path (#34) — and ships **v1.11.0**. Two hours later he files, fixes and ships **#37**, **#38**, **#39** of his own (Electron full-text crash, local-embeddings install instructions, local-API throttle) as **v1.12.0**. Two releases in one day, and for the second time in three days the tracker is drained: nothing of ours is open upstream. The pattern holds and sharpens — contained patches merge, design-sized work is built by him from an issue, now seven for seven |

#13 and #14 are, in substance, the issues for #11 and #12 — filed by someone else,
four days later, describing the same two problems from the user side. He works in
batches, and the batch was triggered by demand rather than by our patches. So an
issue is not a gate, and silence is not rejection; expect days, and expect them to
end all at once. The Aug 27 row is the pattern's second confirmation — again
third-party demand (#22/#23) triggering the sweep that carried our PRs with it.
The Aug 28 row is the first counterexample on latency: #25, a lone contained
fix with no third-party trigger and no batch, filed and merged inside four
hours. Silence still is not rejection, but days are no longer the floor.

**The asymmetry that should decide the form of each contribution.** Both
directions have held every time they have been tested; the live count is the
status table's, not this section's, and it has only grown.

- A **contained defect with a PR** — #11, #12, #19, #20, #25, and later #27,
  #28, #31, #32 — gets reviewed and merged as ours (from #19 onward without a
  single line changed; the earliest pair corrected in review).
- A **design-sized problem as an issue** — #10, #21, and later #24, #26, #29,
  #30, #33, #34 — gets him to build it himself. #21 is the strongest form of the
  pattern: he filed the follow-up to our own PR *himself* and shipped the fix the
  same day, still crediting the finding ("#21, thanks @MinhHaDuong").

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

*Withdrawn 2026-08-30 (ruling in `DECISIONS.md`): I-2 is not filed —
noise, once upstream adopted the sqlite backend and `docs/semantic-search.md`
at v1.10.0 came to name the JSON ceiling's mechanism and carry measured
figures of its own. The trunk re-measurement that was to carry the filing
stays as repo-side evidence (`bench/results/trunk-1.10.0/`, ticket 0025's
log), and ticket 0460 holds the source-level inventory of the ceiling's
mechanism at the reviewed SHA.*

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
  arrived 2026-08-28 as #30 and was **spent** on it 2026-08-29: the retired
  measurement supplied the recall table, the mean-centring result and the
  BigInt warning that the maintainer's own two-stage implementation cites and
  reproduces. The retirement decision is now closed as vindicated — a negative
  result kept for a reader who did not exist yet, and who turned up five days
  later. Nothing further is owed to it; it can be retired outright.
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

**Status, 2026-09-03** (one table; earlier states are in git history).

| | |
|---|---|
| PR #19 accent fold | **merged** 2026-08-27 as `4f61b2a` (squash, authorship + co-author trailer preserved, zero maintainer edits); shipped in v1.7.2, credited "thanks @MinhHaDuong" |
| PR #20 corrupt index | **merged** 2026-08-27 as `6e4637b`, same form; final head `331b037` (rebased onto v1.7.1's `busy_timeout` work — supersedes the `dd1605a` recorded earlier) |
| #21 his follow-up | filed by **him**, off #20's review questions; fixed same day in `2f453d6` with #22/#23 (@StianOby) and shipped as **v1.8.0** (`309204b`). The two swallowed-error holes are closed upstream — closed from our side per the sunset rule (DECISIONS.md 2026-08-27) |
| #24 local-API resume | **closed COMPLETED** 2026-08-29 in the v1.10.0 sweep, with a closing comment from the maintainer; filed 2026-08-27 by @StianOby: stopping a local-only build leaves no usable resume stamp, so the next run starts from zero. He built the resume himself (see the Aug 29 timeline row); the thread stays the reference for 0033's resume slice |
| PR #25 schema read-before-write | **merged** 2026-08-28, the same day it was filed: `fd51659` is in upstream `main` verbatim — SHA, authorship and committer date preserved, zero maintainer edits. He wrote the changelog entry himself (`84eeade`, "the fix landed without its entry"; credit "#25, thanks @MinhHaDuong") and shipped it in v1.9.0. Ticket 0015 closed |
| PRs #27 + #28 custody pair | **merged verbatim** 2026-08-29 (`5ae398a`, `b2b8598`), filed 2026-08-28 — ticket 0017's PR-4/PR-5, closed. [#27](https://github.com/oscardvs/zoteus/pull/27) pins the `@huggingface/transformers` model cache under the data directory (uninstall-by-deleting-dataDir made true); [#28](https://github.com/oscardvs/zoteus/pull/28) moves the Gemini API key from the URL query string to the `x-goog-api-key` header. Neither carried a maintainer follow-up commit: the merge commits' file lists match the fork commits' exactly, which is the first time a contributed pair landed unmodified (#11 and #12 each drew one review follow-up, #25 was hardened in review) |
| #29 + #30 third-party demand | **both closed COMPLETED** 2026-08-29, filed 2026-08-28 by @Michael-Logies (a 10k-item library, running zoteus as primary). [#29](https://github.com/oscardvs/zoteus/issues/29) (extract full text locally from any PDF/EPUB): built as `f1d93cf` — three file sources in order (running desktop app, local storage folder, cloud download), EPUB via `node:zlib` and the spine, a PDF outline, and real page ranges. [#30](https://github.com/oscardvs/zoteus/issues/30) (`zotero_semantic_search` at ~100 s per query on a 255k-passage index, self-diagnosed as the per-row JS vector scan): **he built the two-stage search himself** (`ad7c434`) — one sign bit per dimension after subtracting the corpus mean, Hamming-scanned with XOR and a SWAR popcount over `Uint32Array`s, then an exact float32 rescore of the pooled candidates. His own comment credits this thread's measurements for three specific choices: the mean-centring (citing zotero/zotero#6012's `modelCalibration.meanVector`, as our comment did), the SWAR popcount **explicitly against BigInt** ('per the measurements in this thread'), and the default oversample of 16x, whose 0.986 recall figure is ours — `limits.ts`'s doc-comment reproduces the 4x/8x/16x table (0.884 / 0.953 / 0.986) verbatim. The residue the reporter named at close — none of it touches bytes-per-vector — is half right: the codes do cut the bytes *scanned* (94 MB beside 3.1 GB), while the Matryoshka prefix lever, the second multiplier in comment D, is not implemented and would cut them again. Two comments were posted from here before the close (2026-08-29): the 0008 evidence pack, and [issuecomment-5461657828](https://github.com/oscardvs/zoteus/issues/30#issuecomment-5461657828) carrying the cost-model frame, the real-vector two-stage tables, the Matryoshka results, the local-embedder feasibility tables, the BigInt trap, and the 4,1 s-versus-95 s gap left open with the one-minute experiment that settles it. The reporter answered that experiment 18 seconds after the close: **five sequential queries, 93,3 s on the first and 93–105 s throughout, no cold-start penalty** — so on his machine the cost is not I/O, and the gap stays open. He also confirmed `text-embedding-3-large` is MRL-trained, which is what the Matryoshka lever needs. His 'Reopening' comment did not reopen the issue (no reopen event on the timeline; it is still CLOSED), so that datapoint sits under a closed issue. A third comment from here, post-close ([issuecomment-5463253062](https://github.com/oscardvs/zoteus/issues/30#issuecomment-5463253062), 2026-08-29 15:28), measured the released pair end to end on a real index — v1.9.0 `bb414df` against v1.10.0 `b132f2d`, 93 022 passages at 384 dims, 20 queries, 5 warm passes per arm on separate copies of the file: `mode:"semantic"` p50 1 069,1 ms → 21,7 ms, **about 49x on the median**, reproduced independently (49,18x then 49,11x; the p95 ratio does not reproduce as tightly, so quote the median). Of that, #31's fused loop contributes 1,31x end to end and the two-stage the remaining 37,5x — consistent with #31's own 2,19x at 3 072 dims, since the fusion saves width-proportional arithmetic atop a per-row fetch cost that does not shrink. The fast answer is the same answer: same first hit 20/20, mean top-10 overlap 9,65/10, and `vectorScan` read after every query shows `codes` 100/100 on stock against `exact` 100/100 with `ZOTEUS_INDEX_ANN=false`. `mode:"auto"` is 1 136,0 → 93,1 ms; the residual ~70 ms is BM25, untouched by either change. At 384 dims the arms read 143 MB per query where the reporter's index reads 3,1 GB, so these ratios are a floor for his shape, not a promise about it |
| PR #31 cosine fusion | **merged verbatim** 2026-08-29 as `bba43f2`, 13 hours after filing, on the third in-flight slot granted once (DECISIONS.md 2026-08-29); ticket 0070 closed. `cosine` walked every stored vector twice, and its `norm` was shared with the query-side call — `number[]` there, `Float32Array` per row — so that call site stayed polymorphic for the process's life. Fusing the two traversals measures **2,19x** on a 255 703-row index at 3072 dims (`bench/cosine_fusion.mjs`); scores bit-identical. The merge commit closed **#30** by reference (`999cb1c` names it), which is what put the issue in COMPLETED before the two-stage work landed and 18 seconds before the reporter's cold-start datapoint arrived. The filed body was the commit message rather than the prepared one, so it carried neither the driver/results links nor the equivalence-test description, and it carried a `Claude-Session:` line into a public repo |
| upstream | **v1.13.0** (`8f16efe`, 2026-09-03), and `main` four commits past it at `b0e0bc8` carrying the #43 dtype work upstream files under `[Unreleased]`. `b05ed69..b0e0bc8` is 34 commits and 10 merges over 67 files, +4912/-524, of which the watched search layer is +1830/-198 over fifteen files with `query-terms.ts` new — and the index schema stamp moved for the first time since v1.7.0, to a generation whose one migration rung rebuilds the keyword index in place and re-computes no vector. Ticket 0618 re-read the standing against it. Before that: **v1.11.0** (`ee50cea`) and **v1.12.0** (`b05ed69`), both shipped 2026-08-31. v1.11.0 carries PR #32 (`daf576b`) and his own builds of issues #33 and #34; v1.12.0 carries #37, #38 and #39, all three filed and fixed by him — a full-text build refused under Electron, corrected local-embeddings install instructions, and full-text read concurrency chosen by the serving API. This is the first release pair since the prototype began that rewrites the search layer under us: `git diff --stat v1.10.0..main -- src/features/search/` is +1738/-57 over ten files, three of them new (`own-words-source.ts`, `vector-salvage.ts`, `electron.ts`), against PR #25's single file in v1.9.0. So the reviewed baseline is stale in the way that matters — `README.md`'s standing was read against v1.10.0 source and cannot answer for this one. Ticket 0504 read the four rows worth reading at `b05ed69` from a clone and found the page stale in the under-reporting direction: R16 is kept where the page says `none`, and R12's second clause is kept where the page says it fails and names #32 as in flight (`verification/UPSTREAM-1.12.0-REREAD.md`). Re-basing `UPSTREAM` and re-reading the other twenty rows is ticket 0520, held until its trigger is ratified. Earlier: **v1.9.0** (`bb414df`, 2026-08-28): the #25 fix plus `zotero_annotate` placing highlights from the passage text itself (`87e06c0` — `pdf-locate.ts` on optional `pdfjs-dist`, files read via the local API's `/file` 302 to `file://`, nothing written on a doubtful match). That feature left the search layer alone; the release's only changes under `src/features/search/` and to `docs/semantic-search.md` were PR #25's own, and every measurement claim I-2 targeted was untouched. Earlier still: v1.7.1–v1.8.0, four releases 2026-08-26/27 |
| PR #32 wipe guard | **merged** 2026-08-31 as `daf576b`, filed 2026-08-29 from `cross-library-guard` (`ae6b043`) — ticket 0016's PR-3, closed. Merged as a **merge commit rather than a squash**, so `ae6b043` sits in upstream `main` under its own authorship and committer date, with no maintainer follow-up commit: the fourth contributed item to land unmodified, after #25, #27 and #28. His merge message records that he **reproduced both shapes on `main` before merging** — the `clearStore()` erasure and the resume-append v1.10.0 added — which is the first time the tracker sees him re-derive a contributed defect rather than review the patch that fixes it. One asymmetry worth recording without reading anything into it: the v1.11.0 changelog describes this fix under **Fixed** with no item number and no contributor credit, where #19, #20 and #25 each carried "thanks @MinhHaDuong" and where #33 and #34 in the same release do carry their numbers. Nor is there a closing comment on the PR, or on #33 or #34 — where #24 and #26 each drew one in the v1.10.0 sweep. Recorded because this file tracks the form each landing takes; the code landed verbatim, which is the part that mattered. Read again at v1.12.0 (ticket 0504): the guard holds for both shapes, and the same release that carried it added a seam the guard does not reach — `vector-salvage.ts` names no library at all, matching a reused vector on passage id and byte-identical text, and it is armed at file open inside `sideline()`, before any `assertLibrary` call exists in the stack, against a replacement index that is deliberately unstamped and therefore exempt. Reaching a wrong vector needs a sideline, a build for a different library against the fresh file, the same embedder, an item-key collision and identical text, so this is an observation and not an alarm; what is accurate is that library scoping does not reach salvage and no test exercises it. Not filed: below the bar the reserve is spent on |
| issue #33 own words | **closed as completed** 2026-08-31 by his own **PR #36** (verified on the issue page) — **built by him** and shipped in v1.11.0 (`a605680` merging `d8266f7`, plus `c3bdc19` letting own-words passages reuse salvaged vectors). Ticket 0022 closed. Filed 2026-08-29 as an issue rather than as PR-10 because the build came out design-sized, and the form was chosen on the measured asymmetry: it held, and the asymmetry now reads **seven for seven** on design-sized work built by him (the SQLite backend, incremental updates, local extraction, resume, the two-stage search, and now own words and the migration path). What shipped is the design the issue argued, including the parts that were ours to get wrong — passages keyed to the **parent item** so an item with forty annotations takes one result slot, `source:"note"` / `source:"annotation"` labels, notes stripped of HTML, one paged crawl plus one batched lookup per fifty annotated attachments, and the deletion case no `?since=` can report because deleting a note moves no version anywhere. He settled the two product questions the issue said were his: own words are **on by default** (`ZOTEUS_INDEX_OWN_WORDS`, `own_words:false` per build) where full text is opt-in, and an index built before the feature fills its gap on its first update, once, and says so. The fork branch `own-words-notes-annotations` (`50245d3`) was a prototype pointed at, never offered, and is now superseded |
| issue #34 migration path | **closed as completed** 2026-08-31 by his own **PR #35** (verified on the issue page) — **built by him** and shipped in v1.11.0 (`d26f090` merging `3341844`). Filed 2026-08-29 from here, spending no slot. The issue proposed three graduated remedies and he took all three, joined. A **ladder of upgrade steps** carries an older index forward in place, each step inside the one transaction that stamps the new version, so a database is either fully upgraded or fully untouched and a step that throws rolls back and falls through to the sideline. Where a sideline is still the right answer — a newer build's database, an unstamped file, a gap in the ladder — the moved-aside index becomes a **read-only vector source** for the rebuild that replaces it, so a passage returning with the same id and byte-identical text keeps its stored vector instead of being embedded again; reuse is refused when provider or model differs, which is the `embedderId` condition the issue named. And `storageNotice` now **prices** the rebuild it prescribes — how many passages, how many vectors, whether they must be paid for — which was the third remedy, the fallback. Ticket 0441 loses its precondition: a facet-column schema change can now land *with* a migration rather than wait for one |
| #37 / #38 / #39 his own | filed by **him** 2026-08-31 — the first items on this tracker that are entirely his, raised against his own build. #38 and #39 were fixed and shipped in v1.12.0 the same day; #37 shipped a mitigation and stayed open. PRs #40, #41 and #42 carry the documentation half; the fixes themselves came in on `issue-NN-` branches merged direct. States read on the issue pages 2026-08-31: **#38 and #39 are closed as completed; #37 is OPEN** — and #37 **closed in v1.13.0** (`def17d1`, 2026-09-03) by inverting the answer: the refusal and its `ZOTEUS_ALLOW_ELECTRON_FULLTEXT` override are both deleted, and the local embedder's batch is capped under Electron instead. The diagnosis he attached is worth keeping: SIGTRAP from Chromium's allocator on one attention tensor, which is why there was no stack and no OOM report. **#37**: a full-text `action:"build"` inside Claude Desktop takes the server process down partway through — Electron's embedded Node, no thrown error, no stack, no OOM report, just `Server transport closed unexpectedly` in the host log — while the identical build over the identical library runs to completion under standalone Node. He states **the cause is not known**, calls the fix a mitigation rather than a fix, and refuses the one pass known to kill the process (`ZOTEUS_ALLOW_ELECTRON_FULLTEXT` overrides; the refusal happens before anything is cleared, so a headless index survives being asked for). **#38**: the local-embeddings install instructions named a global npm root that Claude Desktop's built-in Node never reads, and the size warning priced the native binaries rather than the resolved tree. **#39**: the full-text pass fetched four attachment bodies at a time whichever API served it, and the desktop local API is a single process shared with Zotero's UI, its sync engine and its own PDF indexer — enough to stop it answering on port 23119, which drops every read and write onto the Web API session-wide. Concurrency is now chosen by the serving API, with back-off to one on observed degradation and `localApiDegradedAt` reported by `zotero_index action:"status"`. That fallback is silent by his own account and sends library reads to a cloud service by a path the user did not pick for that build — an axis `SPEC.md`'s egress paragraph (§6) does not cover, since it is scoped to embedder egress. Posed as a question, not answered, in ticket 0505. All three land on surfaces this repo reasons about: 0019's terminal no-text state, 0480's staleness class, and the full-text cap questions in 0483. **#37 is the only live item on the whole tracker, and it is his.** The release calls the refusal a mitigation and says in terms that the cause is not known; branch `fix/stdio-no-process-exit` (`bf1f654`) carries work on it with no PR — the same no-PR blindness the Zotero-extraction row exists to name |
| issue #44 courtesy filing | **filed 2026-09-01** from here, **built by the maintainer and merged in v1.13.0** (`77ee511`): the sidelined file's own library stamp is read at open and a salvage across libraries is refused, naming both, with an unstamped file left permissive on purpose — the first courtesy filing under the norm, and it was built rather than merely acknowledged. Originally recorded here as OPEN, verified on the issue page — the first filing under GOVERNANCE.md § The courtesy filing (ratified 2026-09-01): the `vector-salvage.ts` library-scoping observation this table's PR #32 row records, addressed to the maintainer as its own short issue rather than left as a row about him. Observation framing preserved (remote five-condition conjunction, no test exercises the cross-library case); the salvage code is **his** (#34 was our issue, his build — our issue named the embedder condition and no library condition, so the seam sits in his implementation of a design our sketch left incomplete). Spends no slot: the volume bound counts pull requests |
| issue #49 typecheck seam | **filed 2026-09-02** from here as [#49](https://github.com/oscardvs/zoteus/issues/49), **built and merged in v1.13.0** (`e80bc8b`): a second TypeScript project `tsconfig.test.json` compiles `src/` and `tests/` together, `npm run typecheck:tests` runs it, and it is a blocking step in both CI workflows and the contribution bar. 89 real errors were fixed across 19 test files. Originally recorded here as OPEN, verified on the issue page — measured the same day, body drafted at [`verification/ISSUE-DRAFT-0530.md`](verification/ISSUE-DRAFT-0530.md) and sent verbatim from its `## Body` heading down, the internal preamble stripped. Upstream `tsconfig.json` at `b05ed69` carries `"include": ["src/**/*"]` (line 18) *and* `"exclude": [..., "tests"]` (line 19), so `npm run typecheck` (`package.json:44`, run at `ci.yml:23` and `deploy.yml:15`, and named as the contribution bar at `CONTRIBUTING.md:33`) compiles none of the suite's 100 test files. Positive control both ways: a ghost import in `tests/config.test.ts` leaves typecheck at exit 0 with no output and leaves `npm test` green — under vite's SSR transform a missing export is `undefined`, not an import-time throw, so it fails only when *called* — and yields `TS2305` + `TS2322` the moment tests are compiled. The lock is double: each single-line fix compiles **zero** test files, and both together with `rootDir: "src"` (line 8) gives 100 x TS6059 and no type errors at all. Blast radius **204 errors across 37 of 101 test files, zero in `src/`**, against a runtime-green suite (923 passing): 115 are `noUncheckedIndexedAccess` on test idiom, 53 untyped `res.json()`/`vi.fn()`, 10 point at `SearchIndex` lacking the `toJSON`/`loadFromJSON` its own class and `persistence.ts` declare (`backend.ts:524`), and **5 are our own drift returning** — `Capabilities.localGroupIds`, added by #12's `116b4aa`, never reached four fixtures explicitly annotated with the interface, and nothing noticed for four releases. No `@types` is missing. Form ruled **issue, not PR** on the measured asymmetry: no one-line fix exists, a contained PR would be a 37-file diff carrying a policy choice in every file, and one category is a question about his interface. Ticket 0530 closed on the measurement; filed at 18:35Z under the author's explicit per-action authorization. What is open now is his answer — chiefly the `SearchIndex` question, which the form ruling put to him rather than patching |
| #48 OpenAI 429 kills the embedding pass | filed 2026-09-02 by @Michael-Logies (the #29/#30 reporter, ~10k items, `text-embedding-3-small` on an OpenAI tier admitting 1M tokens a minute); **closed 2026-09-03 with all four requests built and merged in v1.13.0** (`28367ea`), including the embed-phase resume this repository's comment specified: a build whose embedder gave up keeps its checkpoint, withholds the library version stamp, and a resume asks the store for committed passages carrying no vector — one query on the nullable `passages.vector` column, which is the mechanism we proposed. Not ours, spends no slot; recorded here as OPEN with no comment at reading time. Six builds ended `embedder=none` on a 429 at 53k–84k vectors and every resume re-embedded the full-text pass from zero; four requests: retry with backoff, incremental embed-phase progress, documented throttle dials, the rate arithmetic in status. Read against v1.12.0's source, three of the four are half-right. `ApiEmbeddingProvider.embedBatch` throws on any non-2xx (`embeddings.ts:313`) and `embedPending` swallows the throw into `embedderError` and empties the queue (`index-manager.ts:1745-1753`), so the build does not die: it finishes keyword-only, with every passage stored and no vector after the failure — and nothing records which passages lack one, so the only retry is `build`, which re-embeds all; `VectorSalvage` is armed only on a schema-mismatch sideline (`sqlite-index.ts:579`), never on a plain rebuild. The retry loop he asks for already exists for the Zotero web API (`RateLimitedFetcher`, `http.ts:81-87`) and is simply not on the embedder's path. The dials ARE documented (`docs/configuration.md:18-19`, `docs/semantic-search.md:638-653`) and the default batch is 32, not the 500 the report calls "default". This is the seam `DECISIONS.md` 2026-09-02 named in terms ("upstream's provider today throws on any non-2xx and takes the build down with it") — so a comment here is also the courtesy filing that entry owes, made for us by a third party. The thread is the second third-party carrier of ticket 0033's resume slice after #24, and a draft comment carrying the embed-phase resume contract, the reuse of `RateLimitedFetcher`, and the token-budget sizing is at `verification/ISSUE-48-COMMENT-DRAFT.md` — **posted 2026-09-02 as [issuecomment-5507982796](https://github.com/oscardvs/zoteus/issues/48#issuecomment-5507982796)** after the author read the text, verified on the page (his account, body intact, no trailer). Under the sunset rule from its posting date. The four-role topology does NOT ride this thread: it lands in scoped issue C (ticket 0035, ruled 2026-09-02); the draft states only the invariant that makes the pass separable (a passage without a vector is pending work, a provider failure is a property of one request) |
| PR #45 degenerate query | **filed 2026-09-01, MERGED 2026-09-03** (`6d0d98e`, then in the stack merge `8f6d50b`), shipped in v1.13.0; verified on the PR page when filed — the stopword series' first PR (ticket 0091, series 1/3), from fork branch `degenerate-query` at `47461b7`, one commit atop v1.12.0, body sent verbatim from `verification/UPSTREAM-PR-0091-DEGENERATE.md` (series branch). `to be or not to be` answered on what the user typed: `not` joins the 29-word list, a query that prunes to nothing runs as typed if it was a phrase, the fallback never fires while a term survives, and the list comes off the in-memory backend's document side. Gates re-verified on the exact commit before filing (typecheck, lint, 939 tests). Spends the held stopwords-follow-up slot under the one-slot-per-PR ruling; PR 2 (diacritics) awaits the query-expansion measurement its design ruling ordered, PR 3 (droplist) awaits a review panel — each needs its own grant to file (`DECISIONS.md` 2026-09-01) |
| PR #46 diacritics + query expansion | **filed 2026-09-01, MERGED 2026-09-03** (`f3c5fc8`, then `8f6d50b`), shipped in v1.13.0 — the 0091 series' second PR, from `pr2-expansion` at `6a201fa`, body sent verbatim from [`verification/UPSTREAM-PR-0091-DIACRITICS.md`](verification/UPSTREAM-PR-0091-DIACRITICS.md). This is the one that moved upstream's index schema: `passages_fts` is now declared `remove_diacritics 0`, so the index keeps each word as written, an unaccented query reaches the accented spellings through an `accent_variants` map, and the expansion fires only where those spellings' summed document frequency exceeds the typed spelling's own. Because the tokenizer changed, `SCHEMA_VERSION` moved off 1 for the first time since v1.7.0 and upstream's `SCHEMA_MIGRATIONS` ladder gained its first rung — ours by consequence, his by construction. The maintainer bounded the expansion group during review before merging. |
| PR #47 library-derived droplist | **filed 2026-09-01, MERGED 2026-09-03** (`fb91231`, then `8f6d50b`), shipped in v1.13.0 — the 0091 series' third PR, from `pr3-droplist-r5` at `11385a2`, body sent verbatim from [`verification/UPSTREAM-PR-0091-DROPLIST.md`](verification/UPSTREAM-PR-0091-DROPLIST.md). The 29-word English stopword list is deleted; a query is pruned against a droplist derived from the library it is searching, with a corpus floor below which nothing is pruned and a refusal to store a list naming the whole vocabulary. The list came off the in-memory backend's *document* side too, which is where it had been silently deleting words from the index. |
| #43 local embedding model and dtype | filed by **him**; **built and merged in v1.13.0 and after** — `aeb3244` lets `ZOTEUS_EMBEDDING_MODEL` name the LOCAL model, with input prefixes derived from the model id for instruction-tuned families and deliberately kept out of the embedder identity; `b0e0bc8`, four commits past the tag and still under `[Unreleased]`, adds `ZOTEUS_EMBEDDING_DTYPE` over twelve precisions and puts it in the identity **above full precision only**, so every local index ever built stays valid and any other precision declares itself a different vector space. Not ours and spends no slot, but it is the lever ticket 0495 was going to have to ask for: the embedder study's candidates are now reachable on stock upstream without a fork. |
| #54 update check default egress | filed by **us**, 2026-09-04, after the author's explicit go-ahead: [oscardvs/zoteus#54](https://github.com/oscardvs/zoteus/issues/54). `ZOTEUS_UPDATE_CHECK` defaults `true` (`src/config.ts:237`) and phones home to `api.github.com` (`src/lib/update-check.ts`) on a manual install's first tool call, with no prior notice and no opt-in — our acceptance harness's R10-no-egress rule (`bench/acceptance/`, ticket 0613's goal-1 gap A) treats this as a second silent exception beside the one-time model-weight download. Not a contained one-line fix by our own read (a default is a product decision, not a defect with one correct answer), so per `GOVERNANCE.md`'s measured-asymmetry rule it goes as an issue, spends no PR-budget slot. Two shapes proposed, neither demanded: default `ZOTEUS_UPDATE_CHECK` to `false`, or ask once on first run and persist the answer. Drafted at `verification/ISSUE-DRAFT-0634.md` (ticket 0634), OPEN with no comment at filing time. |
| PR #55 uninstall docs | filed by **us**, 2026-09-04, after the author's explicit go-ahead: [oscardvs/zoteus#55](https://github.com/oscardvs/zoteus/pull/55). Publishes a `README.md` `## Uninstall` section (pairing the existing `## Install`) plus a new `docs/uninstall.md` naming `ZOTEUS_DATA_DIR` and its per-OS defaults, with the pre-v1.10.0 case (model weights that used to live outside the data directory, before PR #27's cache-under-data-dir fix) as a worked example. Contained docs form, the shape that merged verbatim twice (#27, #28) — spends no slot against the six-PR budget. Ticket 0613's goal-1 gap B (R15); content drafted, red-then-green proven end to end (`bench/results/0630-gap-b/`), at `verification/UNINSTALL-DRAFT-0630.md` (ticket 0630, closed). Branched off live `upstream/main` tip (`7de4a2f`), not the stale reviewed-baseline checkout, since a docs-only diff has nothing to gain from pinning to the older SHA. OPEN with no comment at filing time. |
| #56 durable pause | filed by **us**, 2026-09-04, after the author's explicit go-ahead: [oscardvs/zoteus#56](https://github.com/oscardvs/zoteus/issues/56). `action:"stop"` durably cancels the currently running job (checkpoint intact, nothing auto-resumes on its own) but does not gate a subsequent EXPLICIT `action:"build"` call — measured directly (ticket 0643): `stop` → idle → `build` again → resumes, `work.embed.build.done` +109. Not framed as a bug — the current behavior is reasonable for the common case and may be intentional — offered as a soft proposal, same shape as #54: a persisted `paused` flag, or a distinct `resume` action separate from `build`'s current resume/rebuild/repair overload. Ticket 0613's goal-1 gap C; the actual measured cause of `R22`'s FAIL once ticket 0642's counters made the clause decidable at all. Ticket 0644, closed same day. OPEN with no comment at filing time. |
| the train | **the whole 0091 series merged 2026-09-03**: PRs #45, #46 and #47 all landed in v1.13.0, so the budget's live remainder stays zero and nothing of ours is in flight. Recorded below as it stood while #45 was open, because the budget arithmetic is the part that survives. **PR #45 in flight** (degenerate query, filed 2026-09-01), one of the volume bound's two slots. GOVERNANCE.md sets the budget at six *beyond* the merged #19 and #20, so the six are PR-2, #25, #27, #28, #32 and the stopwords follow-up — standing now at **four merged** (#25, #27, #28, #32), one sunset-closed (PR-2, overtaken by v1.7.1's `80f8aa0`) and one **spent 2026-09-01 as PR #45**: the stopwords follow-up (0014) that X2's failure had held (warm p95 1 773,0 ms stopword-less against 392,3 ms on stock, so per SPEC.md §5.3 the deletion does not ship alone) files instead as the measured redesign's first PR, the degenerate-query fix, under the one-slot-per-PR ruling — PRs 2 and 3 of the 0091 series each need a fresh grant when ready (`DECISIONS.md` 2026-09-01). The budget's live remainder is therefore zero, and the reserve is the only source of further candidates: 0022 was spent as issue #33 and is now closed, leaving 0019 (terminal no-text state) as the one reserve item still unspent — its warn-once was verified live at `fulltext-source.ts:180`, but #29's local extraction, #37's Electron refusal and #39's throttle have all moved the population under it since, so its evidence needs re-deriving against v1.12.0 before it is argued — and against v1.13.0 now, which deleted #37's refusal outright, so the population moved a fourth time |
| §2 migration | skipped by decision — see §2's head note |
| §4 delta / I-1 | filed 2026-08-28 as **#26** (see §4's tail notes). **Closed COMPLETED** 2026-08-29 in the v1.10.0 sweep, like #24 — the maintainer answered both in one pass (a closing comment on each at 12:14) and built the work: build resume and the full-text version cursor (see the Aug 29 timeline row). Ticket 0024 carries the response |
| §5 measurements / I-2 | untouched by `2f453d6` (see §5's head note); drafted FINAL. Reconcile before filing: the author's 2026-08-27 ruling (ticket 0024) requires trunk-measured numbers, not fork-prototype figures — trunk re-measured 2026-08-30 (`bench/results/trunk-1.10.0/`, ticket 0025's log) unblocks the redraft. Upstream numbers #21–#23 are consumed — I-labels stay internal |
| gates | fold-gate waiver retired with #19's merge (0026, SPEC.md §5.2.8); stock ≥v1.7.2 carries `normalizeForSearch`, so the fold gate was expected to run green against it. It does not, and as of v1.13.0 the disagreement is a different disagreement: the gate measured red against v1.12.0 on twenty-five codepoints (`bench/results/0578-fold-sweep/codepoints.json`, unratified entry in `DECISIONS.md`), and our own PR #46 has since changed the tokenizer the gate probes, so that artifact measures a substrate upstream no longer ships. Ticket 0619 owns the re-measure; nothing may cite the red as a fact about current upstream until it runs |
| fork | `main` at `bb414df`, now **six releases behind** upstream `b0e0bc8`, and the whole 0091 stack is merged upstream so every branch of it joins the deletable list — re-align when convenient; `cross-library-guard` (`ae6b043`) is **merged upstream** in v1.11.0 and joins `fuse-cosine-loop` (`999cb1c`), `model-cache-under-datadir` (`998865e`) and `gemini-key-header` (`b6312e4`) as deletable by the author (session proxies cannot delete branches — 403 — so this step is always his); `own-words-notes-annotations` (`50245d3`) was never offered as a PR and is **superseded** by his own build of #33, so it goes the same way; `stopwords-follow-up` (`ab89bbc`, correcting the `94d994d` this row carried since 2026-08-28 — ticket 0014 superseded it on 2026-08-29) is now **superseded a second time** by the 0091 series, rebuilt on v1.12.0 as the round-3 stack `pr1-degenerate-r3` (`47461b7`) → `pr2-diacritics-r3` (`f80d860`) → `pr3-droplist-r3` (`bb5bb4c`) on `base-v1.12.0`, with `degenerate-query` (`47461b7` again, the clean name) filed upstream as PR #45; the earlier round branches (`pr1`/`pr2`/`pr3` bare, `-v2`, `pr-a-degeneracy`, `t0091-droplist`, `droplist-df-pruning`) are review vehicles, deletable by the author once the series lands; historical storage tree preserved as `archive/fts5-storage-2026-08-21` at `bae82a7` |
| Zotero core | tracked as a surface per DECISIONS.md 2026-08-28. [zotero/zotero#6012](https://github.com/zotero/zotero/pull/6012) — dstillman's **draft** semantic-search PR (opened 2026-08-05, last activity 2026-08-26): local ONNX models via Firefox's runtime, RRF hybrid ranking, **sqlite-vec** for vectors — the same extension #30 proposes for zoteus. Added to the watch 2026-08-29 at the author's request: [zotero/zotero#1610](https://github.com/zotero/zotero/issues/1610) — dstillman's issue (2018-12-19, **closed**), "Undelete and overwrite items in target library trash for repeat cross-library copy", part of the cross-library overhaul around zotero#140; trash/undelete behavior on repeat cross-library copies sits under what the local API serves group-library indexing (#12). The rendered page does not surface the close date or closing commit — verify before citing either. **Checkpoint read at source 2026-08-30** (clone of `zotero/zotero`, PR head fetched as `refs/pull/6012/head`), discharging the political-review gate carried by tickets 0025, 0028, 0034 and 0024's I-3: #6012 is still a draft at head `77e2c4b` — the same commit `SPEC.md` read on 2026-08-29, so it has not moved — and is not an ancestor of `main` (tip `bccaf46`), merge-base `3af8cea`. It adds `embeddings.js`, `lexical.js`, `bestMatch.js` and `ml.js` and modifies `fulltext.js` and `sdt.js`, and **touches no `server/`, API or connector file at all**, which confirms at source what FIELD-REVIEW established by page fetch. The load-bearing fact is separate from the PR: `sdt.js` already ships on `main`, so structured extraction is in the application today, yet `server_localAPI.js` carries zero `sdt`/`structured` references — the only text surface is flat `/fulltext`, read from `Zotero.Fulltext.getItemCacheFile()`. Structured extraction therefore does not reach the consumer zoteus is, merge or no merge. One mechanism confirmed for `SPEC.md` C2's last bullet: the PR adds a `bestMatch` search *condition*, and the local API already serves `/searches/:searchKey/items`, so on merge a saved search carrying that condition is the first place platform semantic results reach the API, with no new endpoint. Re-open the checkpoint on a structured-text endpoint, not merely on a merge. **Drift signal, added 2026-09-02 (ticket 0060): `fulltext.js` and `resource/schema/userdata.sql` on `main`, not the PR.** Zotero 10's largest recent move inside our own problem area — dropping `fulltextWords`/`fulltextItemWords` at userdata step 127 and splitting the keyword index into a separate attached `fulltext.sqlite` of four contentless FTS5 tables — shipped **unannounced**: the 10.0 changelog says only "Much faster full-text content searches", and it reached this repository through a third party's draft PR rather than through any release note. Both files carried it (`7c2a1d1`, 2026-06-30), so watching them would have fired on that date; watching releases did not fire at all. **#6012 HAS MOVED since the 2026-08-30 checkpoint, read on the PR's commit page 2026-09-03**: four commits dated **2026-09-02** — `cb27b75` "run all sdt extraction before any embedding begins", `fbb0495` "approximate chunk token sizes instead of tokenizer", `19e7962` "more polite memory and cpu usage", `cb178d9` "minor fixes" (and `d1f1391`, 2026-08-28, "use sqlite_vec extension to speed up vector search"). The "last activity 2026-08-26" and "has not moved" statements above are the readings of their own dates and are left standing; this sentence supersedes them. `cb27b75` is the load-bearing one: it makes SDT extraction a phase that completes **before** any embedding begins, which is the mechanism that would make packs library-wide — ticket 0572's deferral checkpoint — so that checkpoint is nearer than 0572's text assumes, and `19e7962` puts their extraction scheduling under active change. Read on the rendered commit list, not at source: the head SHA, the draft state and whether `server_localAPI.js` is still untouched are **not** re-verified here, and the 2026-08-30 at-source checkpoint remains the last verified one |
| Zotero extraction | tracked as a surface 2026-08-29, on the standing of Zotero core above. Added because the SDT pack is the strongest candidate substrate for the entry-level unit of answer (ticket 0120's third note) and nothing here watched it. [zotero/document-worker](https://github.com/zotero/document-worker) produces the pack, through an ONNX block-segmentation pipeline (clusterer, repair model, classifier) run under ONNX Runtime WASM: 108 commits in 2026, a steady 15/month through July and August, last push 2026-08-19. Its August run targets what looked weak on this machine — "Recover outlines from printed contents" (08-14), then a reference and citation-parsing series — though "weak" rests on **two packs**, which is a probe and not a benchmark: heading recall was 7 of 7 sections on a 1976 scan and 4 headings on a modern 24-page paper, and those two disagree. [zotero/structured-document-text](https://github.com/zotero/structured-document-text) is the pack format itself, a submodule of the first; quiet since 2026-07-29 (2 commits in July, none since), so the schema is settling while the extractor keeps improving, which is the good shape for a reader. **Drift signal: the three version constants in `resource/document-worker/metadata.json`** — `SDT_PACK_VERSION` 1, `SDT_SCHEMA_VERSION` 1.1.0, `SDT_PROCESSOR_VERSIONS` pdf 3 / epub 1 / snapshot 1, read from installed build 20260817151751. A bump in the first two changes what a reader must handle; a bump in the third silently re-extracts existing packs in the background (`sdt.js` returns the stale pack and regenerates), so quality moves under us without any signal at all. The installed build is current: 2 document-worker commits behind, 0 schema commits. Neither repo publishes release notes or a roadmap, and its 11 open issues are stale dependabot bumps from 2022–2023, so commit cadence is the only available signal. That is the same blindness that hid the FTS5 split, and the reason this row exists |
| next | GOVERNANCE.md's increment train as ratified (DECISIONS.md 2026-08-26, event record 2026-08-27); live state in tickets 0014–0037 — `erg ready` is the queue |

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

**§5 resolved — withdrawn, not filed.** The correction issue was ruled noise on
2026-08-30 (`DECISIONS.md`): upstream adopted the sqlite backend and its
doc carries the ceiling's mechanism and figures. See §5 above for what stands
as repo-side evidence.

**Order of operations**: superseded — the plan of record is GOVERNANCE.md's
increment train as ratified in DECISIONS.md, executed through tickets
0014–0035. The original seven-step list is in git history.

**The gate.** 757 tests here were green against a tree that no longer exists. His
suite was 594 passed / 7 skipped at the cycle-2 baseline and has grown since
(86 test files at v1.8.0; `2f453d6` alone added three). Every ported test runs
against *his* tree before it is sent, and the count that matters from now on is
his — re-counted there at send time, never quoted from here.
