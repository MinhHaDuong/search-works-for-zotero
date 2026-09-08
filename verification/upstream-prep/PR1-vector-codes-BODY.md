# fix(search): take an item's binary codes with the passages a catch-up clears (#30)

Based on `4467663` (main at v1.16.0 + the README commit).

## What breaks

`SqliteSearchIndex` has three ways to remove passages, and only one of them
maintains the `vector_codes` cache the two-stage vector path (#30) reads.

`deleteItem` drops the item's codes before its passages go
(`src/features/search/sqlite-index.ts:1316-1317`), because codes are keyed by
rowid and after the delete there is nothing left to name them by — the comment
on `deleteItemCodes` (`:1041`) states the invariant.

Its two partial siblings do neither:

- `clearFulltext(itemKey)` at `:1360` removes the item's `source = 'fulltext'`
  passages, decrementing `c.vectors` for each one that carries a vector, and
  removes no codes.
- `clearOwnWords(itemKey)` at `:1378` does the same for
  `source IN ('note', 'annotation')`.

Those two are exactly the catch-up passes an `action:"update"` runs:
`index-manager.ts:1922` calls `clearFulltext` from the full-text catch-up (#26 —
opening a PDF makes Zotero extract its text and touches no item version), and
`index-manager.ts:2089` calls `clearOwnWords` from the own-words catch-up (#33 —
writing a note versions the child, never the parent). Both replace the item's
passages wholesale.

## The failures a user sees

**Every semantic query goes back to the exact scan, permanently.**

After the first incremental catch-up over an index that holds codes,
`vector_codes` carries one row per replaced passage whose passage is gone.
`refreshCodes` (`:1772`) only writes codes for vectors that carry none
(`uncodedPids`), so nothing later removes them: the surplus is permanent.
`loadCodes` (`:1821`) counts one code per stored vector, finds more codes than
vectors, and returns

> There are more binary codes than the 1200 stored vectors they must describe.

`codesFor` then declines, and every semantic query falls back to the exact float
scan the codes exist to avoid — the 42x this path was landed for — for the life
of the index, until someone runs a full `action:"build"`. The only trace is the
`vectorScanNotice` on `zotero_index action:"status"`; a user who does not read it
sees a semantic search that was fast after the build and slow ever after.

**And a query that arrives during the catch-up throws.**

`zotero_semantic_search` (`src/tools/semantic-search.ts:32-34`) declines during a
running job only when the index is empty, so on a populated index queries and an
update overlap by design. The catch-up clears the item's passages, inserts their
replacements with no vector yet, and awaits the embedder. A resident `codeCache`
that outlived the clear still names the freed rowid; SQLite has just handed that
rowid back to one of the new rows; and `rescoreStatement` (`:1656`) selects
candidates by rowid — `SELECT id, vector FROM passages WHERE pid IN (…)`, with no
`vector IS NOT NULL` filter — so `toFloats` (`:2205`) dereferences null:

```
TypeError: Cannot read properties of null (reading 'byteOffset')
```

Both are reproduced end to end through the public API by the tests below.
Neither produces *wrong* results: every score still comes from a real float32
vector, so a query that returns at all returns the correct ranking.

## The fix, and why that shape

Two source-scoped statements, mirroring the existing `deleteFulltext` /
`deleteOwnWords` pair one for one, plus `invalidateCodes()`, at the top of each
clear:

```sql
DELETE FROM vector_codes WHERE pid IN
  (SELECT pid FROM passages WHERE item_key = ? AND source = 'fulltext')
DELETE FROM vector_codes WHERE pid IN
  (SELECT pid FROM passages WHERE item_key = ? AND source IN ('note', 'annotation'))
```

**Why not reuse `deleteItemCodes`.** It takes every code of the item, and
`clearFulltext` deliberately leaves the item's metadata passages (and the item
row) exactly where they are. Stripping their codes would exchange a surplus for
a shortfall — `loadCodes` would report "the binary codes cover N of the M stored
vectors" and decline the coded path just the same, for rows nothing touched.
Scoping the delete by `source` is what keeps the two halves of the item
independent.

**Why before the delete, not after.** The subquery names the doomed rows through
`passages`; run after `deleteFulltext`, it selects nothing and the statement is a
no-op. This is the ordering `deleteItem` already uses, for the same reason.

**Why `invalidateCodes()` as well.** It is not housekeeping and it is not a table
wipe (that is `dropCodes()`, `:1889`): it drops the *resident* `codeCache`, and
it is what turns the `TypeError` above into the ordinary refusal — with no cache,
`codesFor` sees a job running and declines to build one over rows the update is
still writing, so the query scans exactly and says so. Every other path that
removes or replaces a vector already calls it — `putVector` (`:1416`),
`adoptVector` (`:898`), `deleteItem` (`:1317`), `dropCodes` (`:1895`); the two
clears were the only ones that did not.

Both halves are independently necessary, and that is measured rather than
asserted: with the two scoped deletes in place and only the two
`this.invalidateCodes();` lines removed, the third test below fails with the same
`TypeError` while the other two pass.

## What the tests assert, and that they were seen red

Three cases in `tests/features/search-two-stage.test.ts`, under the existing
`the codes stay level with the vectors` block:

1. **`takes the codes with the body passages a full-text catch-up replaces`** —
   a 600-item index built through `buildIncremental` with body text and a stored
   full-text cursor (1200 vectors, above the default 500-candidate floor, so
   `finalizeVectors` really writes codes), then one `updateIncremental` whose
   `fulltextCatchUp` names one item. Asserts codes == vectors, zero codes naming
   an absent passage, and that the next semantic query is still served by the
   codes (`vectorScan === 'codes'`, no notice).
2. **`takes the codes with the own words an update rewrites`** — the same over
   the own-words pass: 600 metadata passages plus one note (601 vectors), then an
   update whose `ownWords` census reports a newer note version. Same three
   assertions. Its comment records the one thing its redness depends on: the note
   must not hold the largest rowid, which holds because `indexItem`
   (`index-manager.ts:2216`) interleaves own words per item during the build.
3. **`forgets the resident codes a catch-up clears, so a query racing it cannot
   read a cleared row`** — the crash. Warm the cache with one query, then run a
   catch-up on the **last** item indexed with a semantic query fired from inside
   the embedder, i.e. during the await between the clear and the first
   `putVector`. Asserts the query does not throw, that it scanned exactly with
   the build-running notice, and that it still returned its ten hits.

The fixtures are built through the public build/update API with the documented
options; nothing reaches into internals beyond the existing `rank()` cast the
file already uses, and each index is over the code-building floor honestly rather
than by lowering it.

**Red step, on the committed unfixed tree** (tests committed alone, source
untouched, working tree clean):

```
 × ... takes the codes with the body passages a full-text catch-up replaces
   → expected 1201 to be 1200 // Object.is equality
 × ... takes the codes with the own words an update rewrites
   → expected 602 to be 601 // Object.is equality
 × ... forgets the resident codes a catch-up clears, so a query racing it cannot read a cleared row
   → expected TypeError: Cannot read properties of null… to be undefined
     Received: [TypeError: Cannot read properties of null (reading 'byteOffset')]

 Test Files  1 failed (1)
      Tests  3 failed | 14 passed (17)
```

Full suite on that tree: **1250 passed, 3 failed (these three), 7 skipped, 1260
total**. After the fix: **1253 passed, 7 skipped, 1260 total, 0 failed**.
`npm run typecheck`, `npm run typecheck:tests`, `npm run lint` and `npm run
build` are all clean. (Prettier reports all three touched files as unformatted,
but it reports each of them unformatted on `4467663` too, so it is not a gate
here and I left formatting alone.)

## A fourth case written and dropped, and why

I also wrote a case for the hazard the `deleteItemCodes` comment warns about:
after a catch-up on the last item indexed, assert the replacement does not keep
its predecessor's code at the reused rowid.

**That case passes without this change**, so I removed it rather than ship a test
that proves nothing. `putVector` (`:1407-1416`) resolves a passage id to its
rowid and deletes whatever code sits there before storing the new vector, and
`refreshCodes` then writes a fresh one — so a re-embedded replacement never keeps
a stale code. The reuse hazard is real only for a passage that is cleared and
never re-embedded, and that case shows up as an ordinary orphan, caught by the
count check like any other. What the reuse *does* cause is the crash in case 3,
where the inherited rowid is read before the vector is written.

## What I could not verify

- **No measurement on a real library.** The 42x figure is the maintainer's own,
  from the 1.9.0 CHANGELOG entry for #30; I did not re-measure it. The tests
  assert the coded path is *taken*, not how fast it is.
- The fix touches the SQLite backend only. The JSON backend
  (`index-manager.ts:2614/2630`) and the corrupt-store stub
  (`corruption.ts:133/139`) hold no codes and need nothing.
