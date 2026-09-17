# The affected rows read at upstream v1.20.2

*Evidence, not authority. Read 2026-09-17 for the v1.20.2 re-baseline (no
ticket; `DECISIONS.md` entry of the same day). Where this report touches design,
`SPEC.md` remains the record.*

## Subject and method

The subject is `oscardvs/zoteus` at
`c386e835a2ef90b539b611168130c8540cd55fe5`, which is the v1.20.2 tag itself
and `main`'s tip on the day of the read (2026-09-16 for the tag). The
comparison base is the previous reviewed tip
`446766320867f1a0a2c6c55ab63b3df734a05c69`, v1.16.0 plus one README commit.

The tree was read from `fork/`, recreated at the new SHA by `make
upstream-checkout` and built (`npm ci && npm run build`, tsc clean). The old
side was read by `git show` out of the bare mirror `upstream.git/`. The watched
diff (`src/features/`, `src/tools/`, `src/config.ts`, `src/router/`,
`src/lib/update-check.ts`) is 8 139 lines over 53 files, +5 406/−611, out of
170 files and +15 978/−903 in the whole range: 73 commits, 8 merges, six
releases (v1.17.0 `356cfc7`, v1.18.0 `87122d4`, v1.19.0 `9c0e39c`, v1.20.0
`3bf2637`, v1.20.1 `692df02`, v1.20.2 `c386e83`). The delta review
`verification/UPSTREAM-1.20.2-REVIEW.md` maps every changed file and every
named upstream item to the local tickets; this report takes it as evidence and
re-derives what it relies on, and it disagrees with it in four places, each
named where it arises.

The rows below were read by two readers on disjoint sets (R1, R3, R4, R16,
R17, R22, R32, R35 by one; R5, R7, R8, R10, R12, R15, R18, R19, R23, R24, R33
by the other), each opening the hunks and the checkout rather than the review,
and the verdicts were then checked by a third reader of a different model
against the same checkout. R6 is added below because the smoke re-measures it.

**One thing about the page this report used to update.** The recipe printed by
`make upstream-rebaseline` still says the README's standing rows, bars and
tallies must be re-read. That standing report was dissolved on 2026-09-04
(`DECISIONS.md`, "the README stops tracking completed design work"): the
README carries the three deliverables and nothing per requirement, and
`bench/check_progress.py` has run in its deliverables mode since, so `make
check` no longer fails when the baseline moves past the page. The nineteen
rows the recipe names were re-read all the same. Each row below therefore
states its *previous* verdict, taken from the last standing report
(`git show b1311ead~1:README.md`, read at v1.14.0) as amended by
`verification/UPSTREAM-1.16.0-REREAD.md`, and its verdict now. This file is the
record of standing at v1.20.2; there is no other.

**A live run was made this time, and it is bounded.** Unlike the v1.16.0 read,
the checkout was built and driven: `bench/smoke_upstream.py` and the acceptance
layer both ran against it (§ Smoke and acceptance below). No desktop Zotero
runs on this host, so the library transport was the Zotero Web API and the
index under test is a 40-item metadata-only build made by the run itself.
That re-measures the four smoke-backed rows on their own narrow clauses and
nothing wider; every other verdict below is a source reading, and the words
`measured` and `code` are used accordingly.

## Delta

The material changes, by mechanism rather than by release note:

- **the full-text attachment map is rebuilt (#78, `8e8e700`, `0c4ba3b`,
  `2bddf4c`).** Deep-offset paging is gone; the map is keyed `itemKey=` batches
  of 50 with 3 attempts and 3 sweeps, a map that never reached the end sets
  `incomplete` on the source, the build cursor is withheld over an incomplete
  map, and a persisted `fulltextPartial` with `FULLTEXT_RECOVERY_ATTEMPTS = 3`
  bounds the recovery;
- **a failed body read no longer passes as coverage (#67, `d916aa1`).**
  `textFor` throws on a read failure and on a miss under an incomplete map;
  `fulltextRecords()` → `restorePassages()` keeps the item's existing body
  text, and `fulltextGap` withholds the library version stamp so the next
  update retries;
- **two processes on one index stop clobbering each other's stamp (#68,
  `484257c`).** `writeMeta()` merges instead of rewriting the row,
  `readDataVersion()` reads `PRAGMA data_version`, `refreshFromStore()`
  re-reads the file before `updateBlocker` decides, and `MemorySearchIndex.save()`
  skips a rewrite when its signature is unchanged and the file moved under it;
- **the library router gains a pending-cloud-write overlay (#80, #81) and four
  newly routed reads (#64, #74):** every routed read goes through `route()`,
  `noteCloudWrite` and `desktopHasCaughtUp` hold a read on the cloud until the
  desktop shows the written object, `servesLocally` ignores the override so a
  crawl never flips backend; `listTags`, `versions`, `deleted` and
  `listSearches` join the routed set, and stock exports go through
  `router.exportItems` (#75, `9f32cc4`);
- **every tool declares an `outputSchema` and per-argument descriptions
  (`00bb05e`, v1.20.0)**, which exposed #83 (`c386e83` itself: schemas declare
  no JSON Schema dialect); `zotero_pdf_images` is a new tool (31 in all);
- **pdf.js has one import site (`910d211`, `pdfjs-loader.ts`)**, masking
  `process.type` under Electron so the import no longer throws `DOMMatrix is
  not defined`, and `pdfjs-dist` is pinned exactly at 5.6.205 (#69, `b899aa5`);
- **`mode:"semantic"` refuses without vectors or an embedder** (this
  repository's PR #73, `987d072` + `1278091`), and vector codes are invalidated
  with the passages they encode (our PR #72, `050c320`); both rebased in under
  new SHAs with identical code;
- upstream **withdrew** the `zotero/zotero#6012 modelCalibration.meanVector`
  citation from the `MEAN_SAMPLE` comment as unsourceable (`3a1e942`, v1.17.0);
  the same claim still stands on `packCode()`'s docstring
  (`sqlite-index.ts:2298-2302`), so the withdrawal is partial.

### Schema

**Generation 2, and it did not move; the DDL is byte-identical.** `const
SCHEMA_VERSION = 2;` stands at `sqlite-index.ts:63` at both `4467663` and
`c386e83`. The whole `createSchema` body was extracted from both trees and
compared: 50 lines on each side, `diff` exit 0, so `meta`, `items`, `passages`,
its two indexes, `vector_codes`, `passages_fts` and `accent_variants` are the
same text. `SCHEMA_MIGRATIONS` is at `:175` on both sides and still carries its
one rung, `to: 2`, the tokenizer re-index. `reconcileSchema` — the routine that
decides current, upgradable or foreign, and that sidelines what it cannot read —
is byte-identical across the move as well (`sqlite-index.ts:613-728` new against
`:585-700` old, `diff` exit 0); it has moved 28 lines down the file and changed
in nothing else.

The only storage-format change is two new key/value rows in `meta`,
`fulltextPartial` and `fulltextRecoveryAttempts`, read back at
`sqlite-index.ts:1135` and `:1138` and written through `writeMeta` at `:1197`.
A key/value table needs no bump for a new key, which is why the ladder did not
grow a rung. The delta review's § 3 is right on every one of these points, and
this reading is independent of it: it read `bench/upstream_catchup.schema_at()`,
this one read the two files.

What did change in that file, around the unchanged schema machinery, is the
meta write path: `metaRow()` at `:1163`, the merge in `writeMeta` at `:1197`,
`PRAGMA data_version` at `:1227` and `refreshFromStore` after it (#68). That is
transaction and staleness control, not table shape — but it is executable code
between "an older index is opened" and "it serves", which is what R23's
measurement was about.

## Affected requirement rows

### Coverage, availability and reporting

- **R1 — the release lands on the row's own coverage clause, and the verdict
  does not move (`partial`/`code`).** The clause at stake is that every item in
  the perimeter becomes searchable without anyone asking and without a manual
  rebuild. Before this delta the attachment map behind the full-text pass paged
  `itemType=attachment` through the whole library, and a deep page could take
  longer than the per-request budget and end the map; the build then indexed the
  items it had reached, stamped the cursor of the *whole* census, and the items
  it never mapped were named by no `?since=` on either sequence, forever. Three
  mechanisms replace that. The map is now keyed batches of fifty with three
  attempts, three sweeps and a consecutive-failure cut-off
  (`fulltext-source.ts:25`, `:28`, `:38`, `:47`, `:267-291`); a map that came
  back short sets `incomplete` (`:306-312`) and one that resolved nothing at all
  returns an inert source that *throws* on every read (`:294-305`, `:117-134`).
  The build then withholds the full-text cursor whenever the map was incomplete
  (`index-manager.ts:1623`) and records the damage durably as `fulltextPartial`
  (`:1632`), which the next catch-up reads to re-ask Zotero's sequence from zero
  rather than from the stored cursor (`:2203-2205`, `:2229`). What the row still
  does not get: the crawl is still a page cursor and not a priority order, so
  ruling 2's newest-first class order remains unimplemented — the build pages
  the library at `:1250` and narrows the full-text worklist by a census key set
  (`:1500-1507`), neither of which orders anything by recency; and an attachment
  that yields no text is still not recorded as done-with-a-reason. The recovery
  is bounded rather than terminal: `FULLTEXT_RECOVERY_ATTEMPTS = 3`
  (`index-manager.ts:118`) stops re-buying the whole-body crawl after three
  failed passes, with the mark and the withheld cursor left standing
  (`:2239`, `:2286-2298`). So upstream chose retry-with-withheld-stamp where
  ticket 0019 asks for a terminal, reported no-text state; the two are not the
  same design and the row's second clause is untouched by this delta.

- **R4 — the honesty seam moves again; verdict unchanged (`partial`/`code`).**
  The promise is that the index answers at every moment of its life, including
  during its first build, which obliges the honest coverage reporting R17
  carries. Two things in this delta bear on it. A `textFor` that now throws
  could in principle abort a filling build; it does not, because both callers
  catch per item and record the key in a `failed` map
  (`index-manager.ts:2595-2605`, `:2630-2637`), and the build's own comment
  states the pass "ALWAYS reaches its end" (`:1527-1528`). And a partial index
  now says what it is *after the process that built it has gone*:
  `fulltextPartial` is persisted in the sqlite meta row (`sqlite-index.ts:1174`) and in the JSON snapshot (`index-manager.ts:3358`, `:3403`), and
  `status()` emits it plus a two-sentence `partialCoverageNotice()` when no pass
  in this process has left a reason (`:934`, `:940`, `:955-983`). That is the
  first coverage signal on this row that survives a restart. What the row still
  does not get is coverage per stage: `status()` reports `fulltextItems`,
  `fulltextPassages`, `ownWordsItems`, `ownWordsPassages` (`:910-916`) as
  absolute counts against no denominator and with no date, so a reader still
  cannot place a partial index in the pipeline.

- **R17 — one clause gains a durable field, two gaps stand, and one new gap
  appears in the declared surface; verdict unchanged (`partial`/`code`).** The
  clause is a human answer per stage with a date. The gain: an index whose body
  text is partial now says so as a fact about the index rather than as a job's
  reason, with the remedy and its cost priced in the sentence — one whole body
  crawl, or, past the bound, only the empty items (`index-manager.ts:955-983`),
  and `zotero_index`'s description gained a `fulltextPartial` paragraph saying
  the same to the caller (`index-tool.ts:22`). Three things the row still does
  not get. There is no date on any stage: the only timestamp on the status
  object is `localApiDegradedAt` (`backend.ts:359`), which times a degradation,
  not coverage. The work counters on trigger and outcome are still absent, and
  the v1.16.0 finding on `duplicatePassages` is unchanged at this SHA — five
  occurrences, at `index-manager.ts:444`, `:1156`, `:1658`, `:1661`, `:2743`,
  and none of them in `status()` (`:899`) or `buildStatus()` (`:841`). And the
  new declared output schema is short of the surface it declares: `indexStatus`
  in `common-output.ts:81-106` names `fulltextEnabled` and `fulltextVersion` but
  not `fulltextPartial`, `fulltextReason`, `fulltextItems`, `fulltextPassages`,
  `ownWordsItems`, `ownWordsPassages` or `ownWordsReason`. Nothing breaks,
  because `index-tool.ts:64-72` spreads it into a `.passthrough()` object, but
  the review's reading of that file — "`indexStatus` is now a declared
  description of the status surface SPEC reasons about" — is too generous: the
  declaration omits every per-stage coverage field R17 is about, including the
  one this very release added. Status cost is unchanged and still O(1):
  `status()` reads `counts()` only, and the new `refreshFromStore()` pragma is
  called from `updateBlocker` (`:1696`), never from the status path.

- **R32 — the build gains request-shaped cost the row's rate does not cover;
  `measured` stands on its narrow embed term only.** The row is a rate per
  passage over the whole pipeline. The delta does not touch the embed term:
  there is no hunk in `embeddings.ts`, `chunker.ts` or `tokenize.ts` in the
  watched diff, so `bench/results/0025-x1-recall/embed-feasibility.json` still
  speaks for the term it always spoke for. What moved is the fetch term, which
  was an allocation and not a measurement: upstream states its own trade in the
  source — "on a 9k-attachment library the map now costs about 180 keyed
  requests where the old crawl cost 90 deep-offset pages"
  (`fulltext-source.ts:17-18`) — and adds, on the failure path, up to three
  attempts per batch with 200 ms and 400 ms backoffs (`:28`, `:31`, `:250-257`)
  and up to three sweeps (`:38`, `:267`). Upstream's argument is that a keyed
  lookup is answered out of Zotero's index while a deep page makes the app walk
  the library, so the direction is plausibly favourable per request and
  unfavourable per request count; neither number is measured anywhere I can
  reach, and doubling the request count is exactly the kind of quantity that
  must not be divided out of the 180-vs-90 sentence. A second, larger cost lands
  on the *update* path rather than the build: while `fulltextPartial` stands,
  every update asks the census from zero and re-opens the attachment map
  (`index-manager.ts:2203-2205`, `:2298-2322`), and a recovery pass re-reads the
  body text of every item the census names (`:2265-2290`). That is a build's
  worth of work charged to an update, bounded three times over but not priced.
  R32 therefore keeps its grade and gains a named experiment: time the keyed map
  against the old paging on a large library, which is measurable in
  `bench/fulltext_quality_census.py`'s territory.

### Change, cost and freshness

- **R3 — the release both tightens and loosens the row, and the verdict does not
  move (`partial`/`code`).** The clause is that staying current costs what
  changed, never the size of the library. Tightening: a delta whose attachment
  reads failed no longer loses the body text it held — the item's existing
  full-text passages are read back and put back after the upsert
  (`index-manager.ts:1869`, `:1926`, `fulltextRecords` at `:2844-2857`,
  `restorePassages` at `:2863-2870`), and `restorePassages` calls `adoptVector`
  before queueing anything, so a restored passage is re-embedded only where the
  store cannot answer its vector (`:2866-2867`). Nothing whose bytes are
  unchanged is bought from the embedder again through that path. Loosening, and
  it is deliberate: `fulltextGap` withholds the library stamp (`:2044`) exactly
  as `ownWordsGap` does, so the next update repeats the delta; and while
  `fulltextPartial` stands, `from = 0` (`:2204`) makes every update take the
  whole census back and re-open the attachment map, which upstream prices in its
  own comments as "a listing crawl and not a body crawl" (`:2200-2201`) that
  "pays that listing crawl every time rather than once" (`:2320-2321`). That is a per-update cost
  proportional to the library, not to what changed, standing until a pass earns
  the cursor back or the bound at `:2239` runs out. It is the right trade for
  honesty and it is still a breach of this row's letter while it lasts, and it
  is the strongest argument this delta gives for the row staying `partial`. The
  grade was `code` since 1.14.0 and no acceptance measurement crosses this: the
  update path that would be timed is the one that was rewritten.

- **R16 — checked, nothing moved (`shipped`/`code`).** Notes and annotations are
  still a second library-wide crawl, and the watched diff has no hunk in
  `own-words-source.ts` at all — the file appears in none of the 53
  `diff --git` headers. The own-words *consumers* in `index-manager.ts` are
  unchanged in substance: `ownWordsGap` still withholds the stamp (`:2044`),
  `ownWordsRecords`/`restorePassages` still put a degraded census's kept
  passages back (`:1897-1900`, `:1922`), and `build.ts:614-624` still routes a
  census that opened `unavailable` or `incomplete` through
  `noteOwnWordsUnavailable`. The one thing this delta did to the own-words
  design is copy it: the full-text side now has the same gap flag, the same
  restore and the same withheld stamp, written in the comments as the same rule
  (`index-manager.ts:1806-1811`). The row's promise is unchanged in what it
  delivers, and it is still a source reading, never a measurement.

- **R35 — no changed mechanism; verdict unchanged (`partial`/`code`).** The
  clause is that a new, changed or deleted item is noticed within a minute
  without anyone asking. There is still no timer, watcher, event stream or
  startup hook that invokes index work: `setInterval` occurs three times in the
  whole of `src/`, twice in `lib/usage/rollup.ts` (a comment at `:108` and the
  `unref`'d telemetry maintenance timer at `:113`) and once in
  `transports/stdio.ts:93` (a shutdown-flush keep-alive), and neither touches the index. Everything this release added to
  freshness is about what an update does when it runs, not about when one runs.
  One adjacent knob is worth naming because it is easy to misread as a freshness
  dial: `ZOTEUS_ZOTERO_DEADLINE_MS` (`config.ts:233-238`, wired at `:481`) is a
  per-request budget for the desktop API, bounded `min(5000).max(600000)` and
  optional, and it bounds one read rather than any interval between reads. The
  one-minute cadence remains ours and unmeasured.

### Query

- **R5 — previous `partial`/`measured`; verdict does not move, and the honesty
  clause gains a real mechanism.** R5 forbids filtering a top-k list after the
  fact and presenting it as complete, and its ladder ends at an honest refusal.
  Two readings. First, the ranking path is untouched: the candidate-pool loop and
  `distinctHits` are byte-identical across the span (`index-manager.ts:2916-2948`
  and `:2958-2989` at `c386e83` against `:2380-2500` at `4467663`, a 120-line
  window extracted from both trees, `diff` exit 0), and `distinctHits` still
  dedupes by `rec.itemKey` with no facet, no scope predicate and no bitmap, so
  truncation to `limit` still happens after fusion with nothing to enforce
  beforehand. Second, the Zotero-query side gains the refusal R5's ladder names:
  `refuseUnknownCollection` (`collection-guard.ts:21-52`), called by
  `zotero_search_items` before the read (`search-items.ts:106-110`), because the
  desktop answers `/collections/<unknown>/items` with the whole library —
  upstream's own measurement, 723 items for a key that does not exist against 14
  for one that does (`collection-guard.ts:8-14`). That was the worst possible
  shape of this row's defect, a scope silently not enforced and the whole library
  returned as the scoped answer, and it is now refused. What R5 still does not
  get: `zotero_semantic_search` takes no scope argument at all
  (`semantic-search.ts:22-35`: `q`, `limit`, `mode`, `auto_build`), so on the
  index path there is still nothing to enforce and nothing to refuse.
- **R8 — previous `partial`/`code`; verdict does not move, both failing clauses
  fail identically.** The item cap is still `DEFAULT_INDEX_MAX_ITEMS = 5000`
  (`limits.ts:13`), below the design point of 10 000, and `limits.ts` has no hunk
  in the watched diff. The long-document clause still fails the same way:
  `DEFAULT_FULLTEXT_MAX_CHARS = 40_000` at `fulltext-source.ts:11`, unchanged, so
  a 15 000-page PDF is still indexed by its opening pages. Two scale-sensitive
  constructs entered and both are bounded. The attachment map was rebuilt (#78):
  deep-offset paging is gone, replaced by keyed `itemKey=` batches of 50
  (`KEY_BATCH`, `fulltext-source.ts:25`) with three attempts per batch (`:28`)
  and a three-consecutive-failure stop (`:47`) — more requests per library than
  90-item pages, each of them cheap, and the trade is measurable but not measured
  here. The new `zotero_pdf_images` is capped at 4 pages per call and 8 hard
  (`pdf-images.ts:49-50`), 16 images and 40 hard (`:51-52`), with a pixel-bounded
  canvas pool, so the 15k-page PDF is viewable eight pages at a time rather than
  refused. `ZOTEUS_ZOTERO_DEADLINE_MS` (`config.ts:233`, and the field at `:26-32`)
  is unset by default, so no default budget moved.
- **R18 — previous `none`/`inferred`; verdict does not move, and one new notice
  narrows the gap at the library level, not the scope level.** The row wants the
  empty answer to say, *for the scope asked about*, which of the two cases it is.
  The span adds `fulltextPartial`, persisted and reported as a fact about the
  index rather than as one job's reason (`index-manager.ts:304`, `:934`), with
  `partialCoverageNotice()` at `:955-981` supplying the sentence when no pass in
  this process left one; it reaches the searcher through `fulltextNotice`
  (`build.ts:89-94`) appended to the summary of every semantic search
  (`semantic-search.ts:205`). So "no matches" over an index whose body text was
  gathered over a truncated attachment map now says so. That is the same class of
  repair as `ownWordsReason` and `truncationNotice` before it, and it is still
  library-wide: nothing in the delta distinguishes "nothing matched in this
  collection" from "this collection is not indexed yet", and the tool has no
  collection to ask about. The `mode:"semantic"` refusal below removes another
  cause of a blank that is not an honest empty, which is R33's clause rather than
  this one.
- **R24 — previous `partial`/`code`; verdict does not move; the locator half
  gains the most it has gained in a release, the dedup half gains nothing.** The
  page-fidelity clause is served by `locatePassages`, and until this span it
  imported pdfjs directly and returned null when the import threw
  (`pdf-locate.ts:245-250` at `4467663`). Under Claude Desktop that import always
  threw: Electron sets `process.type = "utility"`, pdfjs concludes it is in a
  browser and touches `DOMMatrix` while its module body runs, so the import failed
  before a byte of PDF was read (`pdfjs-loader.ts:1-27`, with upstream's
  measurement on Electron 44.2.0: the same 1.8 MB PDF, the same pdfjs 5.6.205,
  14 pages under plain Node and no import at all with `process.type` set). Every
  hit in that environment therefore fell to the labeled estimate branch
  (`get-fulltext.ts:293`, "the PDF was read but not parsed … pageApprox is an
  estimate"). `loadPdfjs()` masks `process.type` across the import and restores
  the descriptor in a `finally` (`pdfjs-loader.ts:42-60`), and `pdf-locate.ts`
  now calls it (`:290-293`). So inside the client most users run, an exact page
  replaces a labeled estimate. The honesty of the label was never the defect and
  is unchanged. `pageHeights()` (`pdf-locate.ts:239-269`) reads viewports only
  and gives a caller-supplied rect a real `annotationSortIndex`, which is a
  write-side locator rather than a search-side one. The dedup half is exactly
  where it was: `distinctHits` collapses on `itemKey` (`index-manager.ts:2965-2989`),
  so deduplication is still per item and not per section, declared renderings of
  one work do not collapse to one row, and no answer says when many hits came
  from one document.
- **R33 — previous `partial`/`measured`; verdict does not move; the
  mode-served clause gains its first upstream mechanism.** R33 requires that
  where the interface offers a retrieval mode, the mode selected is the mode
  served. Until this span `mode:"semantic"` with no vectors or no embedder
  returned an empty hit list, which reads as "your library has nothing on this".
  It now refuses and names the cause (`semantic-search.ts:157-196`), keyed on
  `embedderId !== undefined` rather than `embedderActive` so one rate-limit blip
  does not kill the mode until a rebuild (`:146-156`). That is this repository's
  PR #73, rebased in under new SHAs. The `auto` branch is untouched, and so is
  the fusion: `keywordOpen` from `mode !== 'semantic'` and `vectorOpen` from
  whether a query vector exists are byte-identical at `index-manager.ts:2930-2931`.
  The sharp clause — where both signals are weak, the combined answer ranks the
  document they agree on above one a single signal favours — still has no gate
  upstream. On evidence: this row's served-ranking measurement was already
  historical after v1.16.0 rewrote `search()`; this span does not restore it and
  does not void it further, because it changes none of that code.
- **R6 — previous `partial`/`measured`; the query path is untouched and the
  smoke re-measures it (`partial`/`measured`).** The clause is a warm answer
  inside 3 s, never waiting on freshness work larger than one request. The
  whole of `search()` at `c386e83` — the candidate-pool loop, `distinctHits`,
  `keywordOpen`/`vectorOpen` — is byte-identical to `4467663`
  (`index-manager.ts:2901-3021`, see the search-loop control under Focused
  verification), so the v1.16.0 read's open question stands unchanged: up to
  `log2(passages / (3 * limit))` extra rounds on a concentrated ranking, whose
  worst case on a full-size index is still not measured. What the delta adds
  on the query path is one branch: `mode:"semantic"` now refuses before ranking
  when the index has no vectors or no embedder (`semantic-search.ts:157-196`),
  which costs nothing on the answering path and removes a silent empty. The
  1.20.2 smoke answered three semantic queries on a 40-passage index at 5,7 and
  5,6 ms warm, 3 198 ms cold with the model download inside it; that is the
  path answering, not a latency figure at scale, and it is carried as such.

### Multilingual

- **R7 — previous `partial`/`measured`; verdict does not move, and nothing in
  the span touches the mechanism.** The default embedder is still
  `DEFAULT_LOCAL_MODEL = 'Xenova/all-MiniLM-L6-v2'` (`embeddings.ts:55`), so the
  MUST tier still fails by default rather than for lack of configuration, and
  upstream's own comment beside it still says an otherwise multilingual library
  wants `Xenova/multilingual-e5-small` and that the default stands because
  changing it under an existing index is the cost (`embeddings.ts:51-54`).
  `src/features/search/embeddings.ts` and `src/features/search/limits.ts` have no
  hunk anywhere in the 8 139-line watched diff. The three new environment
  variables are a desktop request budget, an OpenAlex key and a bulk-write
  confirmation count (`config.ts:233`, `:296`, `:299`); none of them selects an
  embedder or moves an existing default.
- **R19 — previous `none`/`inferred`; verdict does not move; the substrate is
  byte-identical.** `src/features/search/tokenize.ts` is the same file at both
  SHAs (`diff` exit 0 on the whole file), so `normalizeForSearch` (`:63`),
  `foldMarks` and the query-side expansion (`:126`) are unchanged, and
  `deriveAccentVariants` and the `accent_variants` table come through the
  unchanged `createSchema`. The row still rests on reasoning and on nothing that
  ran, and the fold sweep still measures a tokenizer upstream no longer ships.
  The only occurrences of `normalizeForSearch` in the diff are two call sites in
  the FTS delete path (`sqlite-index.ts`, deleting a row's tokens), which change
  no normalization rule.

### Custody, libraries and lifecycle

- **R22 — the delta touches this row, which the review did not notice, and the
  verdict does not move (`none`/`code`).** The clause has two halves: one
  obvious way to stop all background work, and a hold that survives restarts.
  The first half is unchanged — the action enum still reads
  `['build', 'refresh', 'update', 'status', 'stop', 'pause', 'resume']`
  (`index-tool.ts:25`), `pause` and `resume` are handled at `:89` and `:102`,
  and `refuseIfPaused` (`index-manager.ts:835`) still gates the three write
  paths, at `:1019`, `:1119` and `:1737`. So there is still
  no *single* switch: `stop` and `pause` are two, as the row's previous verdict
  says. The second half improves, and by a mechanism the review filed under #68
  and R13 alone. At `4467663`, the sqlite backend's `writeMeta(paused = this.paused)`
  wrote the whole meta row including `paused` on every flush
  (old `sqlite-index.ts:1112`, `:1126`), so an idle handle sharing a data dir
  put its own stale `paused` back over a hold another process had just set. At
  `c386e83` the row is merged rather than replaced — only keys this handle
  changed since it read the row are written (`sqlite-index.ts:1197-1223`), and
  `persistPaused` writes the one flag and nothing else, updating the baseline in
  step (`:2202-2214`). The JSON backend gets the same protection from the other
  side: `paused` is part of `stateSignature()` (`index-manager.ts:3078`,
  `:3093`), and `save()` skips the whole-file rewrite when this handle has
  changed nothing and the file has been replaced under it (`:3312-3320`), while
  `persistPaused` republishes the signature and the file stamp (`:3285-3290`).
  `refreshFromStore()` deliberately refuses to re-read while a pause transition
  is in flight (`sqlite-index.ts:1245`). That is the "holds across restarts"
  half getting materially harder to lose on a shared data dir. It does not move
  the grade, because the row is `none` on the first half and nothing gave it a
  second switch. Evidence stays `code`: the acceptance checks this row rests on,
  `R22-pause-stops-background-work` and `R22-pause-holds-across-restart`, are
  measurements of the pause persistence path, and that path is exactly what
  changed — `persistPaused` has a different body on both backends — so no prior
  run crosses it, and `bench/results/smoke-1.20.2/acceptance-zoteus.json` was then
  produced and both checks report `not-run` there, for want of the
  counters the harness needs to see work created (§ Smoke and acceptance).

- **R10 — previous `shipped`/`measured`; the promise holds and nothing adds a
  default-path egress; the measurement is historical and the evidence falls to
  `code`.** Three checks, done by reading. First, the new tool: `pdf-images.ts`
  and `features/fulltext/pdf-images.ts` contain no `fetch` and no URL — the
  rendering is local pdfjs plus `@napi-rs/canvas`, and the bytes arrive through
  the same `fetchAttachmentBytes` the text tool uses
  (`features/attachments/resolve.ts:132`, whose sources are the desktop app, the
  local Zotero storage folder, then Zotero cloud storage, `:156-157`). That last
  leg is the pre-existing attachment path, unchanged, and it is reached only for
  a file the local sources cannot produce. Second, OpenAlex and Crossref: the two
  base URLs live at `scholar/openalex.ts:37` and `scholar/crossref.ts:4`, and the
  only callers of `ScholarGraph` are `zotero_scholar` (`tools/scholar.ts`) and
  `zotero_import action:"by_identifier"` — both explicit user calls, neither on
  the build or query path. `ZOTEUS_OPENALEX_API_KEY` (`config.ts:296`) is a
  credential for a path that was already explicit, and dropping `mailto` removes
  a parameter rather than adding a destination. Third, the routing overlay: after
  a cloud write, reads of that library go to `api.zotero.org` until the desktop
  can be shown to hold the written object (`library-router.ts:153-176`, `:185-195`,
  `:203-224`). That is a new condition under which a read that would have been
  local crosses the network — but it arises only after a write the user made
  through a configured cloud key, and it is deliberately kept off the search
  path: `servesLocally` answers the standing rule and ignores the override
  (`:107-115`), which is what the index build pins its whole crawl on
  (`build.ts:414`). So the build and the query never flip backend because of a
  write. Net: no new default-path egress, and the four newly routed reads narrow
  in R10's direction as #64 did before them. On evidence: the smoke-1.14.0 arms
  `R10-local-by-default` and `R10-no-egress` were taken two baselines back, and
  the egress arm's executable path — `LibraryRouter`'s read routing — is exactly
  what changed (+274/−10). The old measurement does not cross it, so this row
  falls to `code` at the move.
  **Superseded by the 1.20.2 run** (§ Smoke and acceptance): `R10-local-embedder`
  passes on this build, and the acceptance layer's `R10-local-by-default` passes
  while `R10-no-egress` is red on four DNS lookups and zero off-machine
  attempts. Evidence stays `measured` for the locality clause, on this baseline.
- **R12 — previous `shipped`/`measured`; verdict does not move; the guard is
  byte-identical and group reach widens.** The sharp clause is that a build for
  one library meeting another library's index must refuse rather than overwrite.
  That guard is unchanged text: `if (opts.library) this.assertLibrary(opts.library);`
  ahead of everything `buildIncremental` clears (`index-manager.ts:1120-1123`),
  with the same comment, and the 21-line window around it compares byte-identical
  to `4467663` (`diff` exit 0); the update path keeps its twin at `:1738`. So the
  measurement behind this row's `shipped`/`measured` — PR #32's ten tests —
  crosses unchanged code, and the row keeps its evidence. Two changes widen the
  first clause favourably. `useLocal` is byte-identical (`library-router.ts:87-99`
  against the same block at `4467663`), so a group the desktop holds is still
  served locally and `users/0` still maps to the desktop's personal library; and
  `zotero_groups` now lists desktop-held groups with no cloud key at all
  (`groups.ts:34-49`, rows marked `source: "local"`), so the id a user needs to
  point `library_id` at a group is discoverable key-free. What the row still does
  not get: the default library is still `defaultLibrary()` (`library-router.ts:80-85`),
  which returns `users/0` on a keyless install, so reaching a group still means
  setting `ZOTEUS_LIBRARY_ID`, and one merged index with the library as an R5
  facet remains unbuilt.
- **R15 — previous `partial`/`measured`; verdict does not move, and the span
  adds a derived-state location the standing declaration covers only at
  directory granularity.** The deletion clause has no changed mechanism:
  removal still reconciles against the key set, and #67's `fulltextRecords()` /
  `restorePassages()` keep an item's *existing* body text when a read fails, which
  is a no-replacement rule for items still in the library rather than a deletion
  path. Read, not exercised. The declaration clause is where this span lands.
  `zotero_pdf_images` writes files: `SAVE_SUBDIR = 'pdf-images'`
  (`pdf-images.ts:55-56`), `saveDir = join(ctx.config.dataDir, SAVE_SUBDIR, basename(key))`
  (`:295`), `mkdir` and `writeFile` at `:333-340` for pages and `:406-413` for
  figures, with `save` defaulting on for `mode:"figures"` on a local install
  (`:256`) and refused outright for a shared-server caller (`:251-255`). Two new
  persisted `meta` keys join it (`sqlite-index.ts:1135`, `:1138`). The root
  declaration holds — everything derived goes into `ZOTEUS_DATA_DIR`
  (`README.md:109`, `docs/uninstall.md:3-4`) and `ctx.config.dataDir` is that
  directory — so no residue lands outside the declared root. The item-level
  enumeration does not: `docs/uninstall.md:50-56` names the index and its
  sidecars, `models`, `update-check.json`, `local-api-key.json`, `usage.sqlite`
  and `oauth-store.json`, and does not name `pdf-images/`. **The delta review
  misses this.** Its § 1 labels `src/features/fulltext/pdf-images.ts` "NONE for
  search" and `src/tools/pdf-images.ts` "DOC (any row enumerating the tool
  surface)"; neither row notes that the new tool is a writer of derived state
  under the data directory, which is the one thing about it R15 cares about. The
  consequence for evidence is sharper than staleness: the smoke-1.14.0
  `R15-residue-inventory` arm swept a target that had no such writer, so it is
  not merely old, its coverage is incomplete against the current surface — a
  re-run must exercise `zotero_pdf_images` with `save` on, or it will report a
  clean inventory for a directory it never caused to be written.
  `R15-model-cache-under-declared-roots` is unaffected in substance
  (`embeddings.ts` unchanged) and equally historical. The row falls to `code` at
  the move.
  **Superseded by the 1.20.2 run** (§ Smoke and acceptance): `R15-model-in-data-dir`
  passes (the weights were downloaded into the data directory by this run), and
  the acceptance layer's residue inventory and model-cache checks pass on a run
  that never drove `zotero_pdf_images`. Evidence stays `measured` on those
  clauses; the `pdf-images/` writer is a declaration gap the sweep has not yet
  looked at.
- **R23 — previous `partial`/`measured`; the schema verdict is confirmed
  independently at generation 2; the migration measurement does not cross
  cleanly and the evidence falls to `code`.** The schema reading is stated first
  and stands on its own: see § Schema above — `SCHEMA_VERSION` 2 at
  `sqlite-index.ts:63` on both sides, `createSchema` byte-identical (50 lines,
  `diff` exit 0), `SCHEMA_MIGRATIONS` at `:175` with its single `to: 2` rung,
  `reconcileSchema` byte-identical. So the ladder is still forward-only — a newer
  build meets an older index and migrates, an older build meets a newer index and
  sidelines it before serving a fresh one — and that is what keeps this row
  `partial` rather than `shipped`, unchanged by this span. On evidence: the
  smoke-1.14.0 arms drove both paths against real SQLite files, and the code they
  drove is not entirely the same code. The *deciding* half is byte-identical, but
  the "ends up serving" half now runs through a meta write path that did not
  exist at v1.14.0 — `metaRow()` at `:1163`, the merge in `writeMeta` at `:1197`,
  `readDataVersion()` on `PRAGMA data_version` at `:1227` and `refreshFromStore`
  after it — introduced so an idle handle stops clobbering another process's
  stamp (#68). A measurement of "the migrated index then serves" crosses that.
  Historical, not void, and the row falls to `code` at the move.
  **Superseded by the 1.20.2 run** (§ Smoke and acceptance): both smoke arms pass
  on this build — the ladder walked 1 → 2 in place with 40 vectors kept, through
  the new `writeMeta` path, and the foreign stamp was sidelined byte-identical.
  The migrate-in-place input was a restamped copy of this build's own index,
  which `provenance.json` records. Evidence stays `measured`.

## Where this read disagrees with the delta review

1. **`src/tools/pdf-images.ts`, impact `DOC`, "any row enumerating the tool
   surface"** understates it. The tool creates target-derived state on disk
   under the data directory (`pdf-images.ts:295`, `:333`, `:406`), which is an
   R15 declaration question and a gap in `docs/uninstall.md:50-56`, not a tool
   count. Evidence above.
2. **`src/features/fulltext/pdfjs-loader.ts`, impact `TICKET` (the #62 failure
   class; 0613's install half)** is right and incomplete. The same commit moves
   `locatePassages` onto the loader (`pdf-locate.ts:290-293`), which is R24's
   page-fidelity clause changing state inside Electron: exact pages where the
   answer used to be a labeled estimate. That is a requirement row, not only a
   ticket.
3. Everything else this part relied on in the review — § 3's schema reading,
   the `semantic-search.ts` refusal, the four newly routed reads, the
   `MEAN_SAMPLE` citation withdrawal — was re-derived from the two trees and
   agrees.

3. **`src/tools/common-output.ts`, impact `DOC` ("`indexStatus` is now a declared
   description of the status surface SPEC reasons about")** is too generous: the
   declaration omits every per-stage coverage field R17 is about, `fulltextPartial`
   included (R17 above).
4. **#68 is filed under R13 and ticket 0035 only.** It also lands on R22's
   restart-hold clause: `persistPaused` changed on both backends (R22 above).

## Focused verification

What was run, and the control for each negative claim.

Reader one (R1, R3, R4, R16, R17, R22, R32, R35):

1. `fulltext-source.ts` read whole at `c386e83` (372 lines), and
   `index-manager.ts` read at `:100-130`, `:295-330`, `:460-480`, `:835-1015`,
   `:1240-1260`, `:1470-1650`, `:1685-1720`, `:1800-1950`, `:1995-2090`,
   `:2150-2440`, `:2840-2890`, `:3040-3110`, `:3280-3345`. Every line cited
   above was opened, not taken from the review.
2. **`duplicatePassages` does not reach status**: `grep -n` over
   `index-manager.ts` gives five occurrences (`:444`, `:1156`, `:1658`,
   `:1661`, `:2743`), none inside `status()` at `:899` or `buildStatus()` at
   `:841`. Positive control: the neighbouring `fulltextPartial` *does* appear in
   the status builder, at `:934` and `:940`, so the same grep over the same file
   finds a status-resident field when there is one.
3. **`fulltextPartial` is not in the declared output schema**:
   `grep -c fulltextPartial tools/common-output.ts` returns 0. Positive control:
   `fulltextVersion` is there at `common-output.ts:102`, so the file does
   declare full-text fields — it declares the wrong ones.
4. **No scheduler for R35**: `grep -rn setInterval src/` returns three hits in
   two files, `lib/usage/rollup.ts` and `transports/stdio.ts`, both read in
   context (a telemetry maintenance interval and a shutdown keep-alive). The
   grep is a live probe rather than a silence: it returned non-zero and the two
   call sites were read before being dismissed.
5. **The embed term did not change**: `grep '^diff --git' watched.diff` lists 53
   files and none of them is `embeddings.ts`, `chunker.ts`, `tokenize.ts` or
   `own-words-source.ts`. Positive control: the same grep prints 53 headers, so
   it is reading the file, and `fulltext-source.ts` and `index-manager.ts` are
   among them.
6. **The pause persistence really changed**: the old side was read directly,
   `git -C upstream.git show 4467663:src/features/search/sqlite-index.ts | grep
   -n 'persistPaused\|writeMeta\|paused'`, which shows
   `writeMeta(paused = this.paused)` at old `:1112` and `set.run('paused', …)`
   at old `:1126`; the new side has no `paused` parameter on `writeMeta`
   (`:1197`) and a one-key `persistPaused` (`:2202`). The negative — "the pause
   *surface* did not change" — has its own control: the action enum is
   byte-identical at `index-tool.ts:25` on both sides while the persistence
   lines differ, so the same method distinguishes the two halves of the row.


Reader two (R5, R7, R8, R10, R12, R15, R18, R19, R23, R24, R33):

1. **Schema.** `createSchema` extracted from both trees and `diff`ed: exit 0, 50
   lines each. `reconcileSchema` likewise: exit 0. Control for the method: the
   same `diff` on the whole of `sqlite-index.ts` reports the files differ, and
   the two new `meta` keys are visible at `:1135`/`:1138`, so the two exit-0
   results are a discriminating negative rather than a comparison that could not
   fail.
2. **The search loop.** `index-manager.ts:2901-3021` at `c386e83` `diff`ed
   against `:2380-2500` at `4467663`: exit 0, so the candidate-pool loop and
   `distinctHits` are unchanged in this span. Two independent controls: `diff` on
   the whole file reports it differs (+648/−27 of change elsewhere), and grepping
   the watched diff for `distinctHits`, `keywordOpen`, `vectorOpen` and
   "candidate pool" returns nothing while the same grep for `fulltextPartial`
   returns sixteen hits in the same file's hunks.
3. **The library guard.** `index-manager.ts:1115-1135` `diff`ed against
   `:996-1016`: exit 0. Same whole-file control as above.
4. **The tokenizer.** `diff` on the whole of `tokenize.ts` at both SHAs: exit 0.
   Control: the same whole-file `diff` on `pdf-locate.ts` returns the
   `pageHeights` and loader hunks, so the comparison can report a difference.
5. **No hunk in the diff for `limits.ts` and `embeddings.ts`.** `grep -c` on the
   8 139-line watched diff: 0 and 0. Control: `grep -c 'fulltext-source.ts'` on
   the same file returns 3.
6. **No network in the image path.** `grep` for `fetch(`, `http`, `https` over
   `src/tools/pdf-images.ts` and `src/features/fulltext/pdf-images.ts`: the tool
   matches only `writeFile`/`mkdir`/`save`, the feature file matches nothing.
   Control: the same grep pattern over `scholar/openalex.ts` and
   `scholar/crossref.ts` returns the two base URLs and both `fetch` call sites,
   and a repository-wide grep for `openalex|crossref` returns callers only in
   `tools/scholar.ts`, `tools/import.ts`, `features/resolve/resolve.ts` and
   `features/scholar/*` — none in `features/search/`.
7. **`pdf-images` absent from the uninstall enumeration.** `grep -rl` for
   `pdf-images|pdf_images` over `fork/docs/` and `fork/README.md` returns
   `README.md` and `docs/grounding.md` and not `docs/uninstall.md`; the
   enumeration itself was then read at `docs/uninstall.md:40-56`. Control: the
   same grep finds `models` and `update-check.json` in that file, so the file is
   reachable by the pattern-and-read method that found the absence.
8. **Files opened in full or in the cited region at `c386e83`:**
   `sqlite-index.ts`, `index-manager.ts` (status, guard, search), `tokenize.ts`,
   `library-router.ts:55-230`, `pending-writes.ts`, `config.ts:1-120` and the env
   block, `semantic-search.ts`, `search-items.ts`, `collection-guard.ts`,
   `groups.ts`, `tools/pdf-images.ts`, `features/fulltext/pdf-images.ts`,
   `pdfjs-loader.ts`, `pdf-locate.ts`, `pdf-pages.ts`, `get-fulltext.ts`,
   `fulltext-source.ts`, `limits.ts`, `embeddings.ts`, `build.ts`,
   `attachments/resolve.ts`, `scholar/*.ts`, `index-tool.ts`,
   `docs/uninstall.md`, `README.md`.
9. **Not done, and named:** no upstream test was run, no query was executed, no


## Smoke and acceptance at 1.20.2

`bench/results/smoke-1.20.2/checks.json`, produced 2026-09-17 by
`bench/smoke_upstream.py` against `fork/dist/index.js` at `c386e83`, with
`bench/results/smoke-1.20.2/provenance.json` beside it saying how. Five checks,
five pass, none observed:

| check | result | what ran |
|---|---|---|
| `R10-local-embedder` | pass | `whoami.embeddings.effective = local`, `status.embedder = local`, `embedderActive = true`, model `Xenova/all-MiniLM-L6-v2`. `cloud: true` in the detail is the *library* transport this host forced (`ZOTEUS_LOCAL=off`, no desktop Zotero), not the embedder |
| `R6-query-answers` | pass | three semantic queries on the 40-passage index, 5 hits each, every score `1/(60+rank)`; cold 3 198 ms (the first query pays the model download and ONNX start), warm 5,7 and 5,6 ms. A 40-passage index says nothing about latency at scale; it says the path answers |
| `R15-model-in-data-dir` | pass | no `models/` under the data directory at server start, one after the queries: this run downloaded the weights, there |
| `R23-previous-schema-migrates-in-place` | pass | schema 1 → 2 at the original path, 40 passages and 40 vectors before, 40 and 40 served after, 5 hits on the probe query, `storageNotice` reads "upgraded in place". The input was a copy of this build's own index restamped to 1 by hand, because no schema-1 index carrying vectors survives on this host: the ladder's one rung was walked on a file of the current shape, which is a positive control on the ladder and the `writeMeta` path behind it, not a v1.12-era artifact |
| `R23-foreign-schema-sidelined` | pass | restamped to 0 and to 9999: sidelined byte-identical, an empty index served, the build's own stamp 2 |

`bench/results/smoke-1.20.2/acceptance-zoteus.json`, the acceptance layer
under the account posture (`untrusted-runner`, the sudoers rule working), seeded
with the same 40-item index: 4 pass, 1 fail, 1 not-offered, 6 not-run.

| check | result | reading |
|---|---|---|
| `R10-local-by-default` | pass | |
| `R10-no-egress` | **fail** | under bwrap with the network unshared, zero off-machine connect attempts and four `connect()` calls to the local stub resolver `127.0.0.53:53`, which the harness counts; the server log shows the local embedder failing to fetch its model on the fresh, empty data directory. The 1.13.0 artifact has the same shape (eight DNS calls, zero off-machine). Observation, not diagnosis: the one candidate cause this run shows is the declared model acquisition on a data directory that holds no weights, and whether the harness should score a lookup for the declared exception as egress is a question for the `R10-no-egress` assertion, not for this row |
| `R15-residue-inventory`, `R15-model-cache-under-declared-roots` | pass | nothing created outside the declared root; note that the sweep drove `install`, `configure`, `resume`, `query` and never `zotero_pdf_images`, so the new `pdf-images/` writer (R15 below) was not exercised |
| `R15-uninstall-removes-declared-state` | not-offered | the target has no uninstall verb; unchanged |
| `R22-*`, `R3-*`, `R13-two-processes-do-not-duplicate-work` | not-run | the target reports no `work.<stage>.<trigger>.<outcome>` counters, so the clauses are undecidable here, as at 1.13.0 |
| `R13-two-processes-both-answer` | pass | 5 hits from each of two live processes on one data directory, and after both stopped |
| `R23-foreign-stamp-ends-up-serving` | not-run | the harness's own restamp raised `OperationalError: attempt to write a readonly database` before a verdict; an instrument fault under the account posture (the operator restamping a file the target account wrote), not a fact about the target. The smoke covers both directions of this clause |

Consequence for the evidence column: R6, R10, R15 and R23 keep `measured`,
re-taken at this baseline on the clauses above; the readers' "falls to `code`
at the move" in the R10, R15 and R23 rows below is the verdict *before* this
run and is superseded by it. R13's both-answer clause has a fresh green and
its duplicate-work clause a fresh not-run; R3 and R22 stay `code`, for want of
counters upstream and not for want of a run.

## Stale `SPEC.md` citations

The recipe reported seven drifted `file:line` anchors. Each was resolved at
`c386e83` by reading the construct it names, and re-pinned in `SPEC.md`; the
line at the new anchor is quoted so the negative is readable.

| `SPEC.md` (new line) | anchor as written | corrected anchor | what stands there at `c386e83` |
|---|---|---|---|
| 1040 | `index-manager.ts:672` | `index-manager.ts:734` | `protected dropStaleVectors(cause: string): void {` |
| 1041 | `index-manager.ts:881` | `index-manager.ts:992` | `this.clearStore();` inside `reset()` |
| 1046 | `sqlite-index.ts:499` and `:590` | `sqlite-index.ts:527` and `:618` | the two `PRAGMA busy_timeout = ${BUSY_TIMEOUT_MS}` statements, writable handle and read-only probe |
| 1047, 2650 | `sqlite-index.ts:585` | `sqlite-index.ts:613` | `private async reconcileSchema(): Promise<void> {` |
| 1614 | `build.ts:631-633` | `build.ts:656-658` | `fulltextConcurrency:` and its two-line ternary over `DEFAULT_FULLTEXT_CONCURRENCY_LOCAL` / `_CLOUD` |
| 1615-1618 | `build.ts:617-620`, `:627-629` | demoted to prose | those two ranges are claims about `5a81cee`, not anchors; at `c386e83` `:617-620` holds the own-words source creation. Leaving them backticked would flag them at every future bump for a fact about the past |
| 3663 | `library-router.ts:72`, `:80-81` | `library-router.ts:84`, `:92-93` | `return { type: 'user', id: 0 };` and `const def = this.defaultLibrary();` plus its comment; the routing decision itself is at `:94` |

Unchanged and re-verified: `fulltext-source.ts:11`
(`export const DEFAULT_FULLTEXT_MAX_CHARS = 40_000;`, though #78 rewrote the
rest of that file around it), `tokenize.ts:221`, `own-words-source.ts:145` and
`:179`, `limits.ts:69`. The six Zotero-core citations (`embeddings.js`,
`sdt.js`, `fulltext.js`) are outside the mirror and were left alone.

Three prose passages moved with the anchors. The §5 premise paragraph now
states the seven upstream facts against `c386e83` and appends what
v1.17.0–v1.20.2 did to four of them (#78, #67, #68, #80/#81), each verified in
the code. The calibration passage near `SPEC.md:2150` no longer sources mean
centering to `#6012`, records the withdrawal and its partial reach. The §6
read-transport enumeration gains the four newly routed reads and the routed
stock export.

**Positive control.** `bench/upstream_catchup.py`'s `citation_drift` now runs
with base equal to head, so its `0 DRIFTED` after the re-pin is an all-clear
indistinguishable from not looking. Run by hand against the real old base
(`4467663` → `c386e83`) it fires on exactly the anchors moved above and on the
new ones (`index-manager.ts:734`, `:992`, `sqlite-index.ts:527`, `:613`,
`:1197`, `:216-222`, `fulltext-source.ts:25`, `index-manager.ts:118`,
`library-router.ts:153`, `:84`), so the method discriminates. The substantive
check is the quoted-line column.

`tests/test_upstream_catchup.py::test_citations_in_reads_the_real_spec_md`
pins two real anchors and went red on the re-pin, as it did at the 0738 bump;
the fixture now names `734` and `656-658`.

## Consequence

The reviewed baseline moves to v1.20.2 with the index schema unchanged at
generation 2 (two new `meta` keys, no rung), so no fixture, driver or mirror is
invalidated.

No delivered verdict moves. Three rows gain real source improvement in the
direction of their promise: R1 and R4 (a truncated attachment map can no
longer pass as coverage, and a partial index says so across restarts), R24
(exact pages where Claude Desktop used to get a labeled estimate), R33 (the
selected mode is the mode served, or a refusal). R22's restart-hold half is
harder to lose on a shared data directory. R3 both tightens (a failed read
costs no re-embedding) and loosens (while `fulltextPartial` stands every update
pays a listing crawl proportional to the library), and stays `partial`.

Evidence: R6, R10, R15, R23 re-measured on their narrow clauses at this
baseline; R13's both-answer clause re-measured; R3, R22 and the duplicate-work
clause remain undecidable until the target reports work counters. R32's
`measured` rests on its embed term only, and the fetch term gained an
unmeasured request-count trade (≈180 keyed requests against 90 pages, by
upstream's own sentence).

Two gaps are new. `zotero_pdf_images` writes `<dataDir>/pdf-images/<key>/`,
inside the declared root but absent from upstream's uninstall enumeration, and
the residue sweep never drove it. The declared `indexStatus` output schema
omits every per-stage coverage field, `fulltextPartial` included. Both are
below the ticket floor and are recorded here and in the tickets' re-triage
notes, not filed.

## What I could not check, and why

- **The desktop local-API path, the full-text pass, own words and the keyed
  attachment map (#78) were not exercised.** No desktop Zotero runs on this
  host; the run used the Web API and a metadata-only 40-item build. The
  mechanisms this release is mostly about were read, not driven.
- **The R23 migrate-in-place input was manufactured.** A copy of the current
  build restamped to 1, because no schema-1 index carrying vectors exists here
  and the 984 MB vector-less one would have met the `mode:"semantic"` refusal
  before the ladder. The ladder ran; the artifact it ran on is not a historical
  one, and `provenance.json` says so.
- **`R10-no-egress` is red on DNS lookups alone.** Whether that is a target
  fact or an assertion that scores the declared model acquisition is not
  settled here; the observation is recorded with both artifacts.
- **`R23-foreign-stamp-ends-up-serving` did not run** in the acceptance layer:
  the harness's restamp hit a read-only database under the account posture.
  An instrument defect, unfixed here.
- **The upstream test suite was not run.** `npm ci && npm run build` is the
  extent of it; the 70-odd new upstream tests were read as intent.
- **The recipe's README instructions were not executed**, because the page
  they name no longer exists; `bench/upstream_catchup.py --rebaseline` still
  prints them and was left as it is.
