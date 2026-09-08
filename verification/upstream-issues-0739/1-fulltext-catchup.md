# A transient attachment read during `action:"update"` drops an item's body passages, then advances the stamp (#63's full-text sibling)

Read on `main` at `910310b3979aaad9d314087ffd043eaf59eb023a` (the v1.16.0 release commit). Source reading only: I did not install `node_modules` and ran no test here, so what follows is a trace through the code and the existing fixtures, not a measurement.

This is the same defect #63 closed, one lane over. #63 fixed the notes and annotations census: a failed read no longer replaces indexed text with nothing, and `ownWordsGap` withholds the version stamp so the next update repeats the delta. The full-text lane has the same cursor and the same failure mode, and did not get the same treatment.

### Actual behaviour

An index built with `fulltext:true` holds body passages for item K. The user edits K's tags in Zotero, so K enters the next `?since=` delta. `action:"update"` runs while the desktop app is saturated (#39) or the Web API is rate-limiting past the budget, and the read of K's attachment throws.

`fulltextForPage` catches per item and returns `undefined` ([index-manager.ts:2116-2121](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L2116-L2121)), and below it `createFulltextSource().textFor` catches per attachment and returns `undefined` when nothing was read ([fulltext-source.ts:167-194](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/fulltext-source.ts#L167-L194)). That is the same value both return for "this item has no extracted text". The update then upserts K wholesale:

```ts
this.deleteItem(key);
this.addOneItem(item, pending, texts?.[i], own?.[i]);
```

[index-manager.ts:1688-1689](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1688-L1689). `deleteItem` removes every passage the item holds, body text included ([sqlite-index.ts:1312-1335](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L1312-L1335)), and `addOneItem` re-adds body text only `if (fulltext)` ([index-manager.ts:2204](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L2204)). K is left indexed from metadata alone.

The stamp then advances anyway. It is withheld on an own-words gap and on nothing else ([:1777-1783](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1777-L1783)), and the full-text cursor advances on `reconciled` alone ([:1788](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1788)). K's attachment did not change in Zotero, so K appears in no later item delta, and `fullTextSince(cursor)` will not return it either because its extraction version is older than the cursor. K's body is unsearchable until an `action:"refresh"`. On a saturated library this happens to every changed item on the page at once, and `status` shows only `fulltextItems` one lower than before.

The catch-up pass has the matching gap for items nothing else touched. `fulltextCatchUp` computes `const version = Math.max(since, answer.version)` before any read ([:1895](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1895)), skips unreadable items with `if (!text) continue;` ([:1917](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1917)) and returns the advanced cursor regardless ([:1929](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1929)). Nothing is destroyed there, but the newly extracted text is stepped over for good.

The contrast with the lane #63 fixed is visible in the same loop. Own words that cannot be trusted are read back from the index and re-inserted after the upsert ([:1669-1672](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1669-L1672) and [:1694-1698](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1694-L1698)), and the gap holds the stamp back. There is no equivalent for `source = 'fulltext'`.

The signal needed to detect this is already wired into the update. `crawlOptions` supplies `fulltextFailures` from `opened.readFailures()` ([build.ts:566](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/build.ts#L566)) and is spread into `updateIncremental` at [build.ts:524](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/build.ts#L524). Only `buildIncremental` reads it ([:1412-1413](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1412-L1413), [:1462](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1462)); `updateIncremental` never consults it. The build lane already handles what the update lane does not.

### What is already covered, so the gap is legible

`tests/features/search-fulltext-cursor.test.ts:304-323` covers the `fullTextSince` probe throwing, and that path is correct: the catch at [:1885-1893](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1885-L1893) returns `since` and the delta carries on. `:220-238` covers a failed deletion census holding the cursor. What no test exercises is one attachment's `getFullText` throwing while its item is in the delta, or while the catch-up loop is reading it.

### Expected behaviour

A transient full-text read failure must leave the affected items eligible for the next successful update, and must not remove body text the index already holds. Distinguish "this item has no extracted text" from "this item's text could not be read", exactly as #63 distinguished a degraded census from an empty one.

### Smallest fix shape

Have `textFor` signal failure rather than folding it into `undefined` (throw, return `{ text?, failed: true }`, or snapshot `readFailures()` around each page). When a read fails for an item the index already holds body text for, do not `deleteItem` it: replace metadata only, or read the body rows back the way `ownWordsRecords` does and re-insert them. Set a `fulltextGap` that withholds the stamp exactly as `ownWordsGap` does at `:1777`, and report it in `status` next to `ownWordsReason`. In `fulltextCatchUp`, return `since` rather than `answer.version` whenever any read in the loop failed.

### Acceptance criteria

- With an item K holding body passages, put K in the delta and fail its `getFullText` once. The phrase that only occurs in K's body is still findable after the update, and the stamp has not advanced. Mirrors `tests/features/search-own-words-retry.test.ts:296-318`.
- The next update, with the read restored, re-reads K and leaves the index current.
- In the catch-up path, fail one item's read and assert `fulltextVersion` stayed put, so the next update asks again.
- An update where every read succeeds still advances both the stamp and the cursor, and an idle update stays idle.

Related: #63 is the same defect in the notes and annotations lane; #26 is why the full-text cursor is a separate sequence; #39 is the saturation that makes the transient failure ordinary rather than exotic.
