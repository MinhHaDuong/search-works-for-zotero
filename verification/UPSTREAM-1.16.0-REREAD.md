# The affected rows read at upstream v1.16.0

*Evidence, not authority. Read 2026-09-08 for ticket 0738. Where this report
touches design, `SPEC.md` remains the record.*

## Subject and method

The subject is `oscardvs/zoteus` at
`446766320867f1a0a2c6c55ab63b3df734a05c69`, current `main`, one README-only
commit past the v1.16.0 tag `910310b3979aaad9d314087ffd043eaf59eb023a`. The
comparison base is the previous reviewed tip
`5a81cee88be6d979e9ca1e99e897b6b6df25beef`, v1.15.0 plus two registry commits.

The tree was read from a fresh clone of my own, taken for this report so that no
other agent's checkout was disturbed; its `HEAD` is `4467663` without a
checkout, because that is what `main` points at. All fourteen commit subjects
and the whole 54-file path inventory were listed, and every changed file under
`src/` was read in full diff. The review follows the delta-bounded rule: source
was read broadly enough to catch mechanisms the release notes omit, and a
requirement row was reconsidered only where a changed mechanism can move its
verdict or invalidate its evidence.

**No live acceptance run was admitted, and none was attempted.** This clone has
no `node_modules` and none was installed, so the upstream suite was not run,
nothing was built, and no query was executed. Every verdict below is a source
reading. Nothing is promoted to `measured` on that basis, and the four rows that
carried a smoke measurement — R6, R10, R15, R23, from
`bench/results/smoke-1.14.0/checks.json` — are treated below on the rule that a
measurement does not cross a changed executable path.

## Delta

Fourteen commits, all authored by the maintainer except the two of PR #60, which
are ours and were merged verbatim under a merge commit (`ed12d83`, from
`MinhHaDuong/fix/vitest-tmpdir-teardown`) rather than squashed. Fifty-four files
changed, +3 489/−177; under `src/` that is 21 files, +715/−117, of which
`index-manager.ts` alone is +338/−55.

**The index schema is generation 2 and did not move.** `const SCHEMA_VERSION =
2;` stands at `src/features/search/sqlite-index.ts:63` at both `5a81cee` and
`4467663` — the same file, the same line number, the same text. The `createSchema`
DDL is byte-identical and at identical line numbers on both sides (`meta` at
:928, `items` at :929, `passages` at :930, its two indexes at :939–940,
`vector_codes` at :948, `passages_fts` at :953, `accent_variants` at :964), and
`SCHEMA_MIGRATIONS` is untouched at :175. The repository's own two mirrors agree:
`UPSTREAM_INDEX_SCHEMA_VERSION=2` and `bench/index_schema.mjs:85`.

The material changes:

- **the candidate pool between ranking and de-duplication is no longer fixed
  (#65).** `search()` embedded the query once and ranked into a pool of
  `limit * 3`; it now loops, doubling the pool until the page holds `limit`
  distinct items, both rankers exhaust, or the pool reaches the passage count
  (`index-manager.ts:2405-2429`). The query vector is computed once, outside the
  loop, and hydrated passages are memoized across rounds;
- **a build no longer aborts on a duplicate passage id (#59).** The crawl keeps
  an `indexed` key set and steps over an item a shifted page boundary serves
  twice (`index-manager.ts:1046-1056`, `:1319-1325`, `:1333`); the own-words census
  dedupes children by key (`own-words-source.ts:159-165`, `:192-193`); and the
  SQLite insert became `INSERT OR IGNORE` (`sqlite-index.ts:982-986`) with
  `putPassage` returning a boolean the caller reads. Each item's writes run under
  a savepoint inside the build transaction (`sqlite-index.ts:1286-1300`,
  `index-manager.ts:440`, `:2217-2233`), so a failure between an item's first and
  last passage rolls that item back whole;
- **an update that cannot catch up notes and annotations withholds the version
  stamp (`821629a`, #63).** `ownWordsGap` is set wherever own-words work fails or
  the census opens degraded, and the stamp is written only `&& !ownWordsGap`
  (`index-manager.ts:1632`, `:1762-1775`, `:1777`). A degraded census replaces
  nothing: the page's existing own-words passages are read back and re-put
  (`ownWordsRecords`, `:2329-2348`). The full-text cursor is deliberately *not*
  held back, on the stated ground that the two sequences are independent;
- **the effective library is resolved once per tool call (#61).**
  `requireCloudLibrary` split into `resolveLibrary` (`registry.ts:147`),
  `isPersonalLibrary` (`:161`) and `requireCloud` (`:170`); the desktop
  shortcuts in `annotate`, `attach-file`, `delete-items`, `trash-items` and
  `import` are now gated on the library being personal rather than on the
  absence of a per-call `library_id`, and `bytes.ts:79` lets the desktop serve
  an explicitly named personal library;
- **item-key bibliographies and CSL-JSON exports go through the router (#64).**
  `LibraryRouter` gains `exportItems` (`library-router.ts:171`) and
  `getBibliography` (`:192`), backed by a new `getRaw` text read in
  `src/api/local-client.ts` (+80/−0);
- **the tool context now logs through the server's logger (#59)**, so
  `ZOTEUS_LOG_FILE` receives index build lines and not only HTTP requests
  (`server.ts:63`, `:90`);
- **`action:"build"` says when it replaces an existing index (#59)**, with the
  size of what is replaced, read before the build's prologue clears the store
  (`index-tool.ts:175-183`);
- **three per-OS `.mcpb` bundles** replace the single one, with
  `scripts/mcpb-bundle.ts` (+339) staging each tree via `npm ci --os --cpu` and
  a release gate that refuses to publish an archive missing a `.node` binary for
  a CPU its manifest promises (`.github/workflows/deploy.yml`);
- **`SECURITY.md`** (#66) and the vitest global temp-directory teardown (our
  PR #60, `tests/global-setup.ts`, `vitest.config.ts`).

One correction to the brief that framed this read. Six issues closed here were
filed from this repository (#61, #62, #63, #64, #65, #66 — verified on the forge:
all `MinhHaDuong`, all opened 2026-09-07). A seventh thread accounts for three of
the fourteen commits and for most of the `index-manager.ts` change:
**issue #59 is Michael-Logies', opened 2026-09-06** — the duplicate-passage build
abort, the logger threading and the rebuild notice are all filed against it. It
is the largest single mechanism in the delta and it is not ours.

## Affected requirement rows

### Coverage, availability and reporting

- **R1 — source improves materially; grade stays `code`.** The row's hard clause
  is that the system "MUST NOT need a manual rebuild, whatever state it is in".
  Until this release a library edited while it was being paged produced a second
  copy of the boundary item, and the plain `INSERT` refused it: upstream's own
  account is a build ending "some 1,300 items into a 10,500-item library"
  (`index-manager.ts:1046-1054`). That failure mode is removed at three levels —
  crawl, census and insert — and the savepoint closes the resume hole it left,
  since "an item row with half its chunks would be stepped over as if it were
  finished" (`sqlite-index.ts:1276-1284`). What the row still does not get: the
  crawl has no priority order, so ruling 2's newest-first class order remains
  unimplemented upstream, and the items served twice are skipped and deferred to
  the next update rather than re-indexed in place.
- **R4 — source improves at the honesty seam; verdict unchanged.** The partial
  index was always searchable from the first passage; what was missing is that a
  `build` over a populated index destroys it at its first commit. That is now
  said before it happens, with the count of what is being replaced, and
  `action:"update"` is named as the path that leaves a complete index in place
  (`index-tool.ts:177-183`). R4's own promise is unmoved; the change removes a
  way for a user to lose availability without being told.
- **R17 — one clause improves, one gap is newly visible; verdict unchanged
  (`partial`/`code`).** `ownWordsReason` now covers "not current" and not only
  "not indexed", and carries the reason plus the remedy the job actually has
  (`backend.ts:187-193`, `index-manager.ts:868`, `:1768-1774`). Against that, the
  duplicate counters do **not** reach status: `duplicatePassages` and
  `duplicateItems` are reported once, to the logger, at the end of the build
  (`index-manager.ts:1490-1496`), and `buildStatus()` never reads them
  (`duplicatePassages` occurs at :396, :1037, :1490, :1493, :2256 and nowhere in
  the status builder at :867-868). So a build that silently skipped work leaves
  no trace in the surface R17 is about. The work counters on trigger and outcome
  that the row asks for are still absent.
- **R32 — source adds a small per-item cost; unmeasured, no promotion.** Every
  item now costs a `SAVEPOINT`/`RELEASE` pair on SQLite and every passage an
  `INSERT OR IGNORE` in place of an `INSERT`. The requirement's rate is per
  passage and the added cost is per item, so the direction is favourable and the
  magnitude is unknown. Nothing here measures it, and no build-rate figure is
  carried across this change.

### Change, cost and freshness

- **R3 — source improves; grade stays `code`.** The withheld stamp means the
  next update repeats the same delta rather than skipping past it
  (`index-manager.ts:1777`). That keeps cost proportional to what changed and not
  to the library, which is the clause; the delta does grow while the census
  keeps failing, which is the intended trade and is bounded by the failure, not
  by library size. The re-put of kept own-words passages goes through
  `adoptVector` first (`:1694-1698`), so a vector the store can already produce
  is not bought from the embedder again — the clause about re-embedding nothing
  whose bytes are unchanged holds through the new path.
- **R16 — source improves; verdict unchanged.** Notes and annotations are still
  indexed by a second library-wide crawl on `itemType: 'note || annotation'`. Two
  new failure modes are handled rather than swallowed: a census that stops
  partway now reports `incomplete` and is treated exactly like `unavailable`
  (`own-words-source.ts:73-80`, `:211-216`, `:261-266`; `build.ts:595-599`), and
  a degraded census may no longer answer "no own words for this item" over text
  the index already holds. The row's own promise — that the reader's own words
  are searchable — is unchanged in what it delivers.

### Query

The whole of `search()` was rewritten in this delta. Every row below whose
evidence was taken by running a query against upstream is therefore reading a
path that no longer exists, and no such measurement is carried forward.

- **R24 — the delta lands directly on this row's dedup clause; grade stays
  `code`.** R24 says in terms that "a single document MUST NOT crowd other items
  out of the candidate pool before deduplication happens" (`SPEC.md:520-521`).
  That is the exact defect #65 reports and this release fixes: upstream's own
  comment describes "an item whose forty annotations all rank first (#33)"
  filling a pool of fifteen by itself, so that `limit:5` returned one paper where
  `limit:20` returned five (`index-manager.ts:2394-2404`). The remedy is an
  adaptive pool, not a larger fixed one — which is the right shape, since a
  larger constant only moves the point of failure. What R24 still does not get
  from upstream: entry-level collapse, rendering collapse, and the disclosure
  clause that says so when many hits come from one document. On the locator half
  of the row, `bytes.ts:79` lets the desktop app serve PDF bytes for an
  explicitly named personal library, where before an explicit `library_id` forced
  the cloud; that widens where a hit can be resolved to its page without a key.
- **R33 — source improves; any prior served-ranking measurement is historical.**
  The pool widening applies to all three modes: `keywordOpen` is set from
  `mode !== 'semantic'` and `vectorOpen` from whether a query vector exists
  (`index-manager.ts:2409-2410`), and each ranker is closed independently once it
  returns fewer candidates than asked. So the defect was mode-independent and so
  is the fix. The row's sharp clause — that where both signals are weak the
  combined answer must rank the document they agree on above one favoured by a
  single signal — remains ungated upstream. Whatever run backs this row's grade
  was taken through the previous `search()`; it cannot speak for this one.
- **R34 — source improves in the row's direction; nothing measurable.** The
  requirement is a floor: the known answer inside the first ten. The precise
  failure #65 describes is the answer being cut before de-duplication by another
  item's passages, which is how a pinned query silently drops out of the top ten.
  No pinned set exists upstream, so there is still nothing to run.
- **R6 — no promotion, and a new unmeasured exposure.** This row's smoke
  measurement was already historical after v1.15.0 moved query embedding across
  a worker boundary; v1.16.0 makes it historical a second time and for an
  independent reason. The new loop re-runs both rankers at each doubled pool.
  Upstream states the bound itself: "at most `log2(passages / (3 * limit))` extra
  rounds" (`index-manager.ts:2403`). Against `SPEC.md` §5.2.9's measured 567 829
  passages and a `limit` of 10, that is up to fifteen rounds, and — by the loop's
  own condition — the worst case falls exactly on the concentrated ranking that
  #65 is about. Whether fifteen rounds of `keywordSearch` plus `vectorSearch` fit
  the requirement's 3 s escape on the target machine is **not established here**;
  it cannot be settled by reading source, and §5.2.8's 374 ms cold-scan figure is
  our own scan, not upstream's two-stage `vectorSearch`, so it must not be
  multiplied into an answer. This is an open question with a named experiment,
  not a finding. The row's other clause — never waiting on freshness work larger
  than one request — is untouched: the loop does no freshness work and embeds
  once.
- **R8 — checked, verdict unchanged.** Two scale-sensitive constructs entered
  the delta and both are bounded. The pool loop is capped by
  `this.counts().documents` and grows logarithmically (`:2405`, `:2428`). The
  per-item savepoint holds one item's writes, and a body-text item's chunk count
  is bounded by `DEFAULT_FULLTEXT_MAX_CHARS = 40_000` (`fulltext-source.ts:11`),
  so the 15 000-page PDF does not produce an unbounded savepoint.

### Custody, libraries and lifecycle

- **R10 — the default path's egress narrows; the smoke measurement is
  historical.** Two reads that previously went to `api.zotero.org`
  unconditionally are now routed: `zotero_bibliography item_keys` and the
  library half of `zotero_format_bibliography` (`bibliography.ts:23-27`,
  `format-bibliography.ts:31-38`, `library-router.ts:171-200`). On a
  desktop-served library those calls now cross nothing. The routing decision is
  the same `useLocal` predicate as every other read, so it is a capability
  choice, not a per-call opt-in — the disclosure §6 already carries, extended by
  two methods. `bytes.ts:79` narrows in the same direction. Nothing in the delta
  adds an egress path. The v1.14 `R10-local-embedder` check remains valid on its
  own terms (it reads configuration and status, not the query path), but it was
  taken at a different baseline and is not re-run here.
- **R12 — checked; verdict does not move.** `resolveLibrary` repairs a real
  wrong-library defect, but it repairs it for *writes* and for annotation reads,
  not for the index. The index build still takes its library from
  `router.defaultLibrary()`, and `useLocal`'s treatment of groups and of
  `users/0` is unchanged (`library-router.ts:75-87`, byte-identical across the
  delta). The row's sharp clause — a build for one library meeting another
  library's index must refuse rather than overwrite — has no changed mechanism.
- **R13 — source improves on the row's own restatement; grade stays `code`.**
  The accepted restatement is that "no passage is ever *committed* twice". The
  store now enforces that itself: `INSERT OR IGNORE` makes a duplicate id answer
  with zero changes instead of aborting (`sqlite-index.ts:982-986`), the memory
  backend refuses a duplicate before it can overwrite a record and double-count
  the BM25 document (`index-manager.ts:2552-2555`), and the savepoint makes an
  item's writes all-or-nothing so a crash cannot leave a half-item that a resume
  reads as whole. That is the "without corrupting the index" half of R13 getting
  stronger. It is still single-process reasoning: nothing about two servers on
  one data directory changed, and the acceptance layer that would grade this row
  `measured` was not run.
- **R15 — no new declared location; verdict unchanged (`partial`).** The one
  storage-adjacent change is that a context built without the server's logger
  now attaches `config.logFile` itself (`server.ts:88-90`). That writes to a
  location v1.15.0's uninstall documentation already declares; it does not create
  a new one. Nothing in the delta deletes derived state or changes the uninstall
  surface. The #63 work is explicitly *not* deletion — its rule is that a
  degraded read replaces nothing — so it does not bear on the row's first clause.
  The v1.14 `R15-model-in-data-dir` check is unaffected in substance but was
  taken at an earlier baseline.
- **R23 — schema verdict confirmed at generation 2, independently.** Stated
  first because it is the loudest thing that could have happened and did not.
  `SCHEMA_VERSION` reads 2 at `sqlite-index.ts:63` on both sides; the DDL and the
  migration ladder are byte-identical at identical line numbers; the two
  repository mirrors agree. The `INSERT OR IGNORE` change is to a prepared
  statement, not to a table shape, and the savepoint is transaction control. So
  the v1.14 migration checks are not invalidated by a schema move — but they were
  taken against a different build and no migration was exercised here.

### Unaffected rows

**R5, R7, R18, R19, R22, R29, R35 and R36** have no changed mechanism in this
range, and each was checked rather than assumed:

- **R5** — the delta's loop de-duplicates by item key; it adds no facet, no
  bitmap and no scope predicate, and truncation to `limit` still happens after
  fusion with nothing to enforce beforehand. `distinctHits` is a dedup, not a
  filter (`index-manager.ts:2437-2468`).
- **R18** — the loop can still return fewer than `limit` hits and says nothing
  about why; no emptiness distinction was added or removed.
- **R7, R19, R29** — nothing in the delta touches the embedder, the tokenizer,
  normalization or model selection. `tokenize.ts:221` is byte-identical.
- **R22** — the pause flag, its persistence and the gates it holds are untouched;
  `index-tool.ts`'s action enum is byte-identical at line 22.
- **R35** — still no timer, watcher, event stream or startup hook. #63 changes
  what an update does when it cannot finish, not when one is triggered.
- **R36** — the three per-OS bundles change how the software is delivered, not
  what it costs to run; no paid service, credential or metered provider enters
  the default path.

The `SECURITY.md` addition and the bundle split are adjacent product work rather
than requirement mechanisms.

## Stale `SPEC.md` citations

`SPEC.md` carries eleven `file:line` anchors into upstream source. Each was read
at `5a81cee` and at `4467663` and compared on content. Five moved.

| `SPEC.md` | anchor as written | what stands there at `4467663` | corrected anchor |
|---|---|---|---|
| 1035 | `index-manager.ts:641` for `dropStaleVectors` → `clearVectors()` | `noteFulltextUnavailable(reason: string): void {` | `index-manager.ts:672` (`protected dropStaleVectors(cause: string): void {`); the `this.clearVectors()` call is at `:677` |
| 1036 | `index-manager.ts:850` for `clearStore()` in the build path | `fulltextPassages: c.fulltextPassages,` (inside `buildStatus`) | `index-manager.ts:881` (`this.clearStore();`, inside `protected reset()` at `:880`) |
| 1044 | `own-words-source.ts:132` for the second pass over notes and annotations | a doc-comment line ("off, so a build can index the reader's own words … (#33)") | `own-words-source.ts:145` (`export async function createOwnWordsSource(`) |
| 1478 | `own-words-source.ts:157` for the crawl on `itemType: 'note || annotation'` with no `top` filter | `/** The attachment keys that turned up as annotation parents, awaiting their own parents. */` | `own-words-source.ts:179` — **and there are now two occurrences**: `:105` is the keys-only `childVersions` crawl, `:179` the body crawl the SPEC sentence means |
| 1585 | `build.ts:617-620` for the #39 full-text concurrency rule | `fulltextVersion,` / `fulltextCatchUp,` / the two conditional spreads | `build.ts:631-633` (`fulltextConcurrency: …`), with its explanatory comment at `:625-630` |

The `build.ts` row needs a second sentence, because the drift there is not only
this delta's. At `5a81cee` the concurrency rule already sat at `627-629`, while
`617-620` held the embed-batch dials — so the anchor was pointing at the wrong
construct before this release, and the v1.15.0 report's statement that this range
"was re-read and remains the correct anchor" is wrong on content. The delta then
shifted it four further lines. Both facts belong in the correction.

Six anchors did not move, and their current content is quoted so the negative is
readable: `fulltext-source.ts:11` is still
`export const DEFAULT_FULLTEXT_MAX_CHARS = 40_000;`; `tokenize.ts:221` is still
the `normalizeForSearch(…).match(/[\p{L}\p{N}]+/gu)` line; `sqlite-index.ts:499`
and `:590` are still the two `PRAGMA busy_timeout` statements, on the writable
handle and the read-only probe; `sqlite-index.ts:585` (cited twice, at 1042 and
2352) is still `private async reconcileSchema(): Promise<void> {`; and
`library-router.ts:72` is still `return { type: 'user', id: 0 };`. Two remarks on
the last one. Its companion `:80-81`, cited for "the routing", holds
`const def = this.defaultLibrary();` and a comment; the routing decision actually
spans `:79-86`. That imprecision is identical on both sides of the delta, so it
is not drift — it is a pre-existing one-line-off citation, and correcting it is
optional. Second, the router additions all land after `:161`, which is why
nothing in this file moved despite +37 lines.

**Positive control.** This sweep's method is content comparison at both SHAs,
and it fired: five of eleven anchors came back with visibly different text, in
three different files, and the correct new line was located for each. So the six
"unchanged" verdicts are a discriminating negative, not a silence.

Two staleness findings that are not line anchors, and that a `file:line` grep
cannot see:

- **`SPEC.md:1022-1025`** states the seven upstream premises "against the
  reviewed baseline `037bba8` (v1.15.0)". That name and SHA are now the previous
  baseline, and the paragraph at `:1046-1052` that appends v1.15.0's mechanisms
  needs v1.16.0's beside them.
- **`SPEC.md:3353-3354`** (§6, the read-transport disclosure) enumerates the
  routed item-metadata reads as "`getItem`, `getItemChildren`, `listCollections`".
  The delta adds two more tool-facing reads of exactly that class —
  `exportItems` and `getBibliography` — so the enumeration is now short by two.
  The paragraph's substance survives and in fact improves: those two reads
  previously went to `api.zotero.org` unconditionally, so the surface that can
  reach the cloud without a per-call opt-in grew by two methods while the surface
  that *must* reach it shrank.

`DECISIONS.md` was swept with the same method as a spillover check: it carries
seven anchors (`index-tool.ts:22`, `repair.ts:54`, `library-router.ts:78`,
`:116-133`, `:129-130`, `build.ts:177`, `build.ts:315`) and all seven hold
byte-identical content at both SHAs. That negative rests on the same control as
above.

## Focused verification

What was verified, and how:

1. `SCHEMA_VERSION` read directly out of both trees by `git show`, not from a
   summary: `const SCHEMA_VERSION = 2;` at `sqlite-index.ts:63` on both. The
   whole `createSchema` DDL and `SCHEMA_MIGRATIONS` compared line-by-line and
   found identical. The repository's `UPSTREAM` pin and `bench/index_schema.mjs`
   both read 2, so the three-way mirror is consistent and no fixture regeneration
   is implied by this bump.
2. The forge was queried for the seven item numbers in play. #60 is our merged
   pull request; #61 through #66 are ours as issues, all opened 2026-09-07 and
   all closed; **#59 is Michael-Logies', opened 2026-09-06**, and is the thread
   three of this delta's commits are filed against.
3. Every changed file under `src/` was read as a full diff — twenty-one files —
   plus `CHANGELOG.md`, `README.md`, `vitest.config.ts`, `tests/global-setup.ts`,
   `mcpb/manifest.json` and `.github/workflows/deploy.yml`.
4. The eleven `SPEC.md` anchors and the seven `DECISIONS.md` anchors were
   resolved at both SHAs, as above.
5. The status surface was checked against the two new counters by grepping the
   whole of `index-manager.ts` for `duplicatePassages`: five occurrences, none in
   `buildStatus()`. That is the evidence behind the R17 finding, and it is a
   grep whose positive control is the neighbouring `ownWordsReason`, which *does*
   appear in the status builder at `:868`.

No test was run, no build was made, and no query was executed. See the closing
note.

## Consequence

The reviewed baseline moves to v1.16.0 with the index schema unchanged at
generation 2, so no fixture, driver or mirror is invalidated by the bump.

No row is promoted. Three rows gain real source improvement in the direction
their promise points — R1 (a build can no longer be aborted by an ordinary
concurrent edit), R24 (the dedup clause's exact defect is fixed, and with the
right shape), R13 (the store now refuses a double commit itself). Two rows gain
a fuller account of a gap rather than a better verdict: R17's `ownWordsReason`
widens while its new duplicate counters stay off the status surface, and R3
holds through a path that now deliberately repeats a delta.

Two evidence positions become historical. The whole of `search()` was rewritten,
so any measurement of the served ranking — R6, R33, R34 and R24's ordering half —
was taken on a path that no longer exists. R6 in particular is now historical on
two independent counts, the v1.15.0 worker boundary and this release's widening
loop, and that loop introduces a latency exposure whose worst case falls on
exactly the concentrated query the fix is for. That is the one thing in this
delta that would repay a measurement, and it is the natural next acceptance
target: a `limit:10` query against a concentrated ranking on a full-size index,
timed.

Five `SPEC.md` anchors need re-pointing, one of which was already wrong before
this release. Two prose passages need a baseline name and a two-item extension.
None of them changes a design claim's substance.

## What I could not check, and why

- **The upstream test suite was not run.** This clone has no `node_modules`, and
  installing one was out of scope for this read. So every statement above about
  behaviour is a reading of source, and the 60-odd new upstream tests in this
  delta (`search-candidate-pool`, `search-own-words-retry`,
  `search-shifting-pages`, `library-routing`, `bibliography-routing`,
  `local-client`, `mcpb-bundle`, `index-rebuild-notice`, `context-logger`) were
  read as intent, not executed. A green suite would not promote a row in any
  case, but its absence means I cannot say the new code runs.
- **No live acceptance run, and none manufactured.** The R6 arithmetic above
  stops at a round count deliberately: the per-round cost of upstream's
  two-stage `vectorSearch` on a full-size index is not measured anywhere I can
  reach, and multiplying our own 374 ms scan figure by fifteen would be a number
  divided out of someone else's aggregate rather than one measured. It is stated
  as an open question with the experiment named.
- **The per-OS bundle gate was not exercised.** `scripts/mcpb-bundle.ts` and the
  release workflow were read; upstream itself records that verification was by
  archive inspection and loader simulation on Linux, and that "a run on a native
  macOS or Windows machine is still owed". I add nothing to that.
- **I did not re-derive which stored artifact backs each row's `partial`/`none`
  and `code`/`measured` pair.** The standing ledger owns that mapping; this
  report says which paths changed and therefore which measurements cannot be
  carried, and leaves the bookkeeping to whoever applies it.
- **The savepoint's interaction with the build's outer transaction was read, not
  exercised.** Upstream's own comment says `begin()` must precede the savepoint
  "a savepoint outside a transaction would open one of its own"
  (`sqlite-index.ts:1283-1284`), and the code does call it first at `:1287`. That
  ordering is asserted from source; no crash was staged to see the rollback fire.
- **`SPEC.md` was not edited.** The corrections above are a table for the author
  to apply.
