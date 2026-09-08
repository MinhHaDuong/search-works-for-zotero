# Zoteus v1.16.0 (910310b) — correctness seat

Read-only review of `src/features/search/*` (index-manager, sqlite-index, own-words-source, backend, build, corruption, vector-salvage, query-terms, limits, bm25, embeddings identity) and the tools `zotero_semantic_search` / `zotero_index`, against the tests under `tests/features/search-*.test.ts` and `tests/tools/`. Nothing was executed: `node_modules` is absent, so every "this test would / would not fail" below is by reading the assertion, not by running it.

## Verdict

No release-blocking defect. The two changes that define v1.16.0 — the candidate-pool widening for #65 and the shifting-page dedupe for #59 — are correct on every path I traced, and their tests assert the exact quantities (pool sizes `[15, 30, 42]`, one indexed copy, six whole items after a mid-item failure) that a regression would move. The #63 stamp withholding is also right. What I found instead are two should-fix defects in the machinery those changes lean on, both pre-existing, both made more likely by this release's own themes (a library edited while it is crawled; a large SQLite index that must stay fast): the update's own-words and full-text catch-ups delete passages without deleting their binary codes, which turns every later semantic query on a coded index into the full vector scan #30 exists to avoid, and a deletion or trash during a crawl shifts the page boundary the opposite way from #59 and drops one item that no `action:"update"` will ever revisit. Then one silent-empty-result path in the tool, one lost re-parented note, one build-side twin of #63, and two nits. Every finding names a red state a test could pin.

## Findings, most severe first

### F1. Own-words and full-text catch-ups orphan `vector_codes`; the first such update turns every semantic query on a large SQLite index into the exact scan, permanently

**Severity:** should-fix (high). Search stays correct; the two-stage path (#30) is lost until a full `action:"build"`, and status tells the user to run exactly that — a full re-crawl and re-embed to repair a cache.

**Evidence.** `deleteItem` removes an item's codes before its passages, and says why:

```ts
// src/features/search/sqlite-index.ts:1312-1317
protected deleteItem(itemKey: string): void {
  this.begin();
  // Before the passages go: the codes are keyed by their rowids, and after the delete
  // there is nothing left to name them by.
  if (this.hasCodes) this.stmts.deleteItemCodes.run(itemKey);
  this.invalidateCodes();
```

Its two halves do not:

```ts
// src/features/search/sqlite-index.ts:1360-1370 (clearFulltext) and 1378-1388 (clearOwnWords)
protected clearOwnWords(itemKey: string): void {
  this.begin();
  const rows = this.stmts.itemOwnWords.all(itemKey) as Array<{ pid: number; text: string; has_vector: number }>;
  for (const row of rows) {
    this.stmts.deleteFts.run(row.pid, normalizeForSearch(row.text));
    this.c.documents--;
    this.c.ownWordsPassages--;
    if (row.has_vector) this.c.vectors--;
  }
  this.stmts.deleteOwnWords.run(itemKey);
  if (this.ownWordsKeys.delete(itemKey)) this.c.ownWordsItems--;
}
```

No `DELETE FROM vector_codes`, no `invalidateCodes()`. Both are called by the update path only: `this.clearFulltext(group[j]!.key)` at index-manager.ts:1922 (fulltextCatchUp, #26) and `this.clearOwnWords(key)` at index-manager.ts:2089 (ownWordsCatchUp, #33). The code loader then refuses on the count:

```ts
// src/features/search/sqlite-index.ts:1846-1847
if (i > n) return `There are more binary codes than the ${n} stored vectors they must describe.`;
if (i !== n) return `The binary codes cover ${i} of the ${n} stored vectors.`;
```

and `buildCodes` (1749) makes that verdict sticky as `codesUnusable`, which nothing clears except a write, after which the next query re-derives the same verdict from the same table. Only `dropCodes()` empties the table, and it is reached from `clearStore()` (a build or refresh) or from `refreshCodes` when the stored mean is missing.

**Execution trace.** SQLite backend, embedder on, index of more than `DEFAULT_ANN_MIN_CANDIDATES` = 500 vectors (limits.ts). Build finishes → `finalizeVectors` → `refreshCodes` writes one code per vector, `hasCodes = true`. Item A holds three annotation passages at pids 700–702, coded. The reader edits one annotation. `action:"update"`:

1. Page loop: no top-level item changed → empty page.
2. Deletion pass: nothing.
3. `ownWordsCatchUp`: `live.get(ANN) > since` → `targets = {A}` → `clearOwnWords(A)` deletes passages 700–702 (`c.vectors -= 3`); rows 700–702 of `vector_codes` remain.
4. `addOwnWords` inserts three new passages at pids 1001–1003; `embedPending` → `putVector` → `deletePassageCode(newId)` is a no-op; `finalizeVectors` → `refreshCodes` (mean stored) → `uncodedPids` codes 1001–1003.
5. Table: N vectors, N+3 codes. Commit.

Next semantic query: `codesFor` (1675) → `codeCache` is undefined (the writes invalidated it) → `buildCodes` → `refreshCodes` writes 0 → `loadCodes` walks N+3 rows → `i > n` → `codesUnusable = "There are more binary codes than the N stored vectors they must describe. Every stored vector is being scanned instead; zotero_index action:"build" rebuilds the codes."` → `vectorScan = 'exact'`. Every later query, forever. On the shape #30 measured (255,703 × 3072) that is the 90–105 s per query the codes were built to remove; the #59 reporter's 97,000-passage index is on the same curve.

The rowid-reuse case (the deleted passages were the tail, so the new inserts reuse their pids) does **not** produce a wrong ranking: `putVector` (1415) deletes the code at the reused pid before `refreshCodes` recodes it. It does still leave the count mismatch when a reused-pid passage gets no vector (embedder failed mid-update), so the outcome is the same exact-scan fallback.

**Tests.** `tests/features/search-two-stage.test.ts` "keeps codes level through an update" exercises additions and the deletion pass (`deleteItem`), and "scans exactly when more codes exist than vectors" plants the stray code by hand with raw SQL. No test runs an own-words or full-text catch-up over a coded index, so the suite is green with this defect: it is a coverage hole, not a change detector. A test that goes red today: build `corpus({ count: 600 })` with an `ownWords` access whose `textsFor` returns one note for one item; run `updateIncremental` whose `childVersions` reports that note at a version past the stamp; assert `codeRows(db).codes === codeRows(db).vectors` (today N+1 vs N) and that `rank(index, …)` reports `vectorScan === 'codes'` (today `'exact'`).

**Fix.** Two prepared statements mirroring `deleteItemCodes` with the `source` predicate (`DELETE FROM vector_codes WHERE pid IN (SELECT pid FROM passages WHERE item_key = ? AND source = 'fulltext')`, and the `IN ('note','annotation')` twin), run at the top of `clearFulltext` / `clearOwnWords` under `if (this.hasCodes)`, followed by `this.invalidateCodes()`. About ten lines; the comment on `deleteItemCodes` (1041) already states the invariant.

### F2. An item deleted or trashed while the library is being paged is skipped, and no update ever comes back for it

**Severity:** should-fix (high). Silent and permanent; the only remedy is `action:"refresh"`, and nothing says so.

**Evidence.** The crawl asks for no sort (build.ts `fetchPage`: `searchItems({ library: lib, limit: PAGE_SIZE, start, top: true, backend })`), so both APIs page newest-modified first — the premise of #59, restated by its test fixture ("Newest-modified first: the order Zotero pages in when no sort is asked for"). The #59 fix covers the boundary served twice:

```ts
// src/features/search/index-manager.ts:1322-1325
if (key && indexed.has(key)) {
  duplicateItems++;
  continue;
}
```

Nothing covers the boundary served zero times. The library total is read once, on the first page, and never compared again:

```ts
// src/features/search/index-manager.ts:1297-1300
if (!this.itemsTotal && page.totalResults) {
  this.itemsAvailable = page.totalResults;
  this.itemsTotal = maxItems !== undefined ? Math.min(page.totalResults, maxItems) : page.totalResults;
}
…
// :1341, :1345
start += consumed;
if (start >= page.totalResults) break;
```

`offsetStillHolds` (the total-mismatch check) runs only on a resume. The children census in own-words-source.ts:204–205 has the same shape (`start += items.length; if (res.totalResults && start >= res.totalResults) break;`).

**Execution trace,** using the fixture the #59 test already ships (`ShiftingLibrary`, `tests/features/search-shifting-pages.test.ts`): 250 items K000–K249, newest first is K249…K000. Page 1 (`start 0`) indexes K249–K150. Between pages, another client trashes K200 (already indexed). The list is now 249 rows: K249…K201, K199…K000. Page 2 (`start 100`) is rows 100–199 of that list — K148…K049 — where before the trash it would have been K149…K050. K149 is at row 99 now and is never fetched. Page 3 (rows 200–248) finishes. Result: `items = 248`; K149 absent; K200 present though gone.

Afterwards: `crawlVersion` was taken from page 1, K149's version is at or below it, so `action:"update"`'s `?since=` never lists it; the deletion diff only removes keys `known` holds that `live` lacks (K200 goes, correctly), it adds nothing; `ownWordsCatchUp` targets only `known` items. The status says `done`; `progressLine` reads "248 of 250 items indexed", and `truncationNotice` stays silent because `itemsAvailable (250) <= itemsTotal (250)`. The same holds for a permanent delete, a sync that pulls a deletion made elsewhere, and for a note or annotation deleted during the census (that child stays unindexed because `ownWordsCatchUp` considers unheld children only when `version > since`, index-manager.ts:2048).

**Tests.** The #59 test injects `lib.touch('K010')` and asserts 249 items with the comment that the edited item "belongs to the next update" — true for an edit, false for a deletion. A sibling with `lib.rows.delete('K200')` in `beforePage` and `expect(s.items).toBe(249)` is red today (248).

**Fix (minimal).** Remember the previous page's total; when a page reports fewer, the rows above `start` shifted up by the difference, so re-fetch from `start - d` and let `indexed` (and `seen` in the census) absorb the re-served items:

```ts
if (this.itemsAvailable && page.totalResults && page.totalResults < this.itemsAvailable) {
  const d = this.itemsAvailable - page.totalResults;
  this.itemsAvailable = page.totalResults;
  this.itemsTotal = maxItems !== undefined ? Math.min(page.totalResults, maxItems) : page.totalResults;
  start = Math.max(0, start - d);
  continue; // one extra page; items already indexed are stepped over by key
}
```

Same two lines in `createOwnWordsSource`. This closes every case the count can see; a delete and an add between the same two pages cancel in the count and remain invisible, which is worth one sentence in the #59 warning line ("anything deleted during the crawl…"). A maintainer would have to believe nobody trashes an item during a build to leave this; #59 was a user editing during a build.

### F3. `mode:"semantic"` answers a bare "No matches" when the index holds vectors but no embedder is configured

**Severity:** should-fix (medium). It is the #7 defect class the tool's own description promises to refuse: "when the configured embedder is not running … it returns an error naming the cause instead of an empty result set".

**Evidence.** The refusal is gated on vectors alone:

```ts
// src/tools/semantic-search.ts:102
if (args.mode === 'semantic' && !ctx.search.hasVectors && !ctx.search.storeFault) {
```

Vectors survive a load with no embedder configured (index-manager.ts:690: `if (current && this.vectorEmbedderId && …)` — `current` is undefined, so nothing is dropped, by design: "their provenance is unknown, not known-wrong"). Then in `query()`:

```ts
// src/features/search/index-manager.ts:2375, 2409-2410
if (mode !== 'keyword' && this.opts.embedder && this.counts().vectors) { … }   // embedder null → qv stays undefined
let keywordOpen = mode !== 'semantic';                                        // false
let vectorOpen = qv !== undefined;                                            // false
```

Both rankers closed, `distinctHits(rrf([[], []]))` → `[]`. Back in the tool the summary is `No matches for "q".` plus `embedderNotice(after)`, which is empty by construction:

```ts
// src/features/search/build.ts:70
if (s.embedderActive || s.embedderConfigured === 'off') return '';
```

`staleVectorsNotice` and `unembeddedNotice` are empty too (no stale reason; `passagesWithoutVectors` is only computed with an `embedderId`).

**Execution trace.** Build with `ZOTEUS_EMBEDDINGS=local` (vectors stored, `embedderId` stamped). Restart the server with `ZOTEUS_EMBEDDINGS` unset or `off` — a shared data dir, a second host profile, a `.env` edit. `zotero_semantic_search { q, mode: "semantic" }` → `hasVectors` is true → the guard falls through → `[]` → `No matches for "q".` and nothing else. The `configured = local, runtime missing` variant is *not* affected: there `embedderNotice` prints the reason. Only `off` is silent.

**Tests.** `tests/tools/search-tools.test.ts` builds every semantic case on `new MemorySearchIndex({ embedder: null })` with no vectors, so the `hasVectors` branch is the one exercised. A red test: `loadFromJSON` a snapshot with one vector into an `embedder: null` index, call the handler with `mode: 'semantic'`, expect `isError`.

**Fix.** Gate on the embedder as well: `args.mode === 'semantic' && (!ctx.search.hasVectors || !ctx.search.hasEmbedder) && !ctx.search.storeFault`, with a `why` for the new branch ("ZOTEUS_EMBEDDINGS is off, so the query cannot be embedded and the N stored vectors cannot be ranked against it"). The structured content already carries `vectors`, so the sentence can quote it.

### F4. A note or annotation re-parented to another item is dropped from the old item and never indexed under the new one

**Severity:** should-fix (low). Rare action, permanent effect, one-line fix.

**Evidence.**

```ts
// src/features/search/index-manager.ts:2046-2049
const gapFill = stored.size === 0;
const unheld = [...live.entries()]
  .filter(([key, version]) => !held.has(key) && (gapFill || version > since))
  .map(([key]) => key);
```

**Execution trace.** Note N is indexed under item A (`stored`: A → {N}). The reader drags N onto item B in Zotero; N's version moves, A's and B's do not. `action:"update"`: the page loop is empty; in `ownWordsCatchUp`, the walk over `stored` sees `live.get(N) > since` → `targets = {A}`; `textsFor(A)` no longer lists N → `clearOwnWords(A)` (correct). But N is in `held`, so it is excluded from `unheld`; `itemsFor` is never asked about it; B is never targeted. Next update: N's version is at or below the new stamp, `stored.size > 0` so no gap-fill → never. `search-own-words.test.ts` moves nothing between parents.

**Fix.** Drop `!held.has(key)` from the filter. A held child whose version moved already targets its old item and opens the census through `textsFor`, so asking `itemsFor` about it as well adds the new parent at no extra request.

### F5. A build whose own-words census was incomplete stamps a complete version; the reason is cleared by the next update and by a restart

**Severity:** should-fix (low). The build-side twin of #63, which this release fixed for updates only.

**Evidence.** The build's stamp condition has no own-words term:

```ts
// src/features/search/index-manager.ts:1455
if (!token.cancelled && crawlVersion && !fulltextPassFailed && !this.embedderError) {
```

The update clears the reason unconditionally at its start (`:1591-1593`, `this.ownWordsUnavailable = undefined`), the field is in neither `toJSON()` nor `writeMeta()`, and the catch-up's gap-fill runs only for an index holding no own words at all (`:2046`).

**Execution trace.** `createOwnWordsSource` throws on page 4 of the census after 300 parents → `incomplete` → `noteOwnWordsUnavailable` → the build indexes those 300, stamps V, and reports "…so the index holds each item's metadata but not all of the reader's own words. Re-run zotero_index action:"build" to try again." The tool description tells users `update` "should be the default"; they run it. `ownWordsUnavailable` is cleared; `stored.size > 0` so `unheld` is narrowed to `version > V`; the 600 uncensused parents' children (all at or below V) are never considered; status is clean. A restart alone has the same effect. The `incomplete` verdict is unrecoverable by any update, and the one notice that said so is gone.

**Fix.** Either withhold the build's stamp when `this.ownWordsUnavailable` is set (three tokens on line 1455; the next update then rebuilds, which is the remedy the reason already prescribes), or persist a "children not fully considered" flag that forces `gapFill` on the next catch-up. The first is smaller; the second is cheaper for the user.

### F6. A resumed build ignores the checkpoint's item cap, so a raised `ZOTEUS_INDEX_MAX_ITEMS` inherits a stale `itemsTotal` and the truncation notice lies

**Severity:** nit. `BuildCheckpoint.maxItems` is recorded for exactly this comparison and never read.

**Evidence.** `resumeFrom` (`:953-961`) compares only `embedderId`; `:1062` sets `this.itemsTotal = resume.itemsTotal`; `:1297` re-derives only when `!this.itemsTotal`. Trace: a build capped at 5,000 on a 12,000-item library is stopped at 3,000; the user raises the cap to 20,000 and runs `action:"build"`; the offset holds; the crawl runs to 12,000 items (the loop cap is the new `maxItems`) while `itemsTotal` stays 5,000; `truncationNotice` then reports "Only the first 5000 of 12000 items were indexed, so 7000 are NOT searchable" over a complete index. Fix: when `resume.maxItems !== (maxItems ?? 0)`, zero `itemsTotal`/`itemsAvailable` so the first page recomputes them (one line), or treat a cap change as a non-resume.

### F7. A pause during an update commits the half-applied delta; a later failure then reports "rolled back: the index is unchanged"

**Severity:** nit. The on-disk state is the documented stopped-update state (old stamp kept, some items refreshed, no deletions), so only the sentence is wrong.

**Evidence.** SQLite `persistPaused` (`sqlite-index.ts:2060`) is `begin(); writeMeta(paused); commit()`, which commits the update's single open transaction; `updateIncremental`'s catch (`index-manager.ts:1847-1850`) then calls `rollback()`, which can only discard the post-commit part, and prints "The update failed and was rolled back: the index is unchanged". Fix: say "the update was stopped by a pause and then failed; items refreshed before the pause are kept, the stamp did not move", keyed on whether a pause transition ran during the job.

## Verified correct (positive controls fired)

- **#65 widening loop** (`index-manager.ts:2404-2434`): terminates because `pool` strictly doubles up to `total` and `pool >= total` returns; a ranker that returns fewer than asked is closed and its last list reused; `limit: 0` from a direct caller returns at once. `search-candidate-pool.test.ts` asserts the pool sequence `[15, 30, 42]` against `Math.min(pool * 2, total)` and `[15]` for the closed keyword ranker — both would move under a fixed pool, an unbounded one, or a ranker re-asked after exhaustion. The interaction with the coded path is only cost: `codesFor` declines once `pool * 16 >= vectors`, which at `limit: 50` needs a pool that only a page short of 50 distinct items among tens of thousands of passages reaches.
- **#59 dedupe and savepoint**: `indexed` set, `INSERT OR IGNORE`, `putPassage → false`, `atomically` with `ROLLBACK TO item` + `refreshCounts()`; the "never leaves a half-written item" test asserts six whole items and no hit on the half item, which fails without the savepoint. Note `OR IGNORE` also swallows a `NOT NULL` violation as a "duplicate"; unreachable today (every caller supplies a title and non-empty chunk text), worth knowing when the row shape changes.
- **#63 stamp withholding**: `ownWordsGap` reaches `:1778` on every failure path (versions request, degraded census, `textsFor` throw, attribution failure); the `kept` path re-puts an upserted item's own words with their old text. The full-text cursor deliberately advances anyway (`:1786`), correct since the sequences are independent.
- **Embedder identity** (`embeddings.ts:246-268`): a pure function of `(name, model, dtype ≠ fp32, pooling ≠ mean)`; a model the pooling table moves to `cls` re-embeds once, an unchanged space is unsuffixed and never re-embeds; no cloud provider exposes a `dimensions` knob (grep: none), so the query-width check covers the remaining way a same-identity space could shift.
- **Migration ladder** (`sqlite-index.ts:112-177, 690-800`): contiguity is checked (`migrationPath`), rungs and stamp share one `BEGIN IMMEDIATE`, corruption is sidelined and anything else refused in place with an empty repair file list; schema 1 already carried the `source` column (`git log -S"source TEXT"` → `eee1000`, the backend's first commit), so rung 2's re-tokenization reads a shape it understands; `vector_codes` and `accent_variants` are `CREATE IF NOT EXISTS` and so genuinely not bumps.
- **Catch blocks**: `keywordSearch` narrows its swallow to `isQuerySyntaxError`; `passage()` and `passagesMissingVectors` re-raise corruption as the typed fault; `fulltextCatchUp` swallows the probe failure but leaves the cursor; the own-words census never throws but reports `unavailable`/`incomplete`. F3 is the one silent-empty path found.
- **Concurrency**: queries during a build read the same connection and see its transaction; `buildCodes`/`dropStaleVectors` flush mid-query only when `!isBuilding` / on a width mismatch a running build cannot produce; a pause's commit cannot land inside `atomically` because that block is synchronous; `saveTail` orders JSON writes.

## What I could not check, and why

- **Nothing ran.** No `node_modules`; every "would fail" above is read off the assertion. F1 and F2 in particular deserve the ten-line test each before filing, since both claim a green suite hides them.
- **Zotero API behaviours taken on trust from the code's own comments and fixtures**: default sort `dateModified desc` when no `sort` is sent; `Total-Results` reflecting a trash on the next request; `includeTrashed` defaulting to 0 on `/items/top` (the search paths never set it — `web-client.ts:55` is the only mention); the desktop local API honouring `itemType: 'note || annotation'` and `?format=versions`. F2's fix depends on the first two.
- **Whether the desktop app ever sends `Last-Modified-Version`.** `local-client.ts:118` falls back to 0 and the #59 fixture models the desktop as 0; if that is the live behaviour, every `action:"update"` on the local path is a full rebuild (`updateBlocker`: "no version stamp"), and F4/F5 only bite cloud-served indexes. Not verified against a running Zotero.
- **Out of lens, unread**: the worker-thread embedder (`0cea766`), the per-OS MCPB packaging, the library-router rewrites for #61/#64, `fulltext-source.ts` (read only through its consumer), `repair.ts`, the HTTP transport.
