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

## The failure a user sees

Nothing, until they look at the timings.

After the first incremental catch-up over an index that holds codes,
`vector_codes` carries one row per replaced passage whose passage is gone.
`refreshCodes` (`:1772`) only writes codes for vectors that carry none
(`uncodedPids`), so nothing later removes them: the surplus is permanent.
`loadCodes` (`:1821`) counts one code per stored vector, finds more codes than
vectors, and returns

> There are more binary codes than the 1200 stored vectors they must describe.

`codesFor` then declines, and **every** semantic query falls back to the exact
float scan the codes exist to avoid — the 42x the feature was landed for — on
every query, for the life of the index, until someone runs a full
`action:"build"`. The only trace is the `vectorScanNotice` on `zotero_index
action:"status"`; a user who does not read it sees a semantic search that was
fast after the build and is slow ever after.

I reproduced this end to end through the public API before writing anything —
see the red run below. The consequence is the silent fallback, not wrong
results: every score still comes from a real float32 vector, so the ranking a
declined query returns is correct, just slow.

## The fix, and why that shape

Two source-scoped statements, mirroring the existing `deleteFulltext` /
`deleteOwnWords` pair one for one, run at the top of each clear before the
passages go:

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

**Why `invalidateCodes()` as well.** It is not a table wipe (that is
`dropCodes()`, `:1889`); it drops the *resident* `codeCache` and any verdict
about it, and every other path that removes or replaces a vector calls it —
`putVector` (`:1416`), `adoptVector` (`:898`), `deleteItem` (`:1317`),
`dropCodes` (`:1895`). The clears were the only vector-removing paths that did
not. Concretely: the catch-up loop awaits the embedder between the clear and the
update's own `finalizeVectors`, and `codesFor` only consults `isBuilding` when
the cache is *absent* — so a query arriving in that window is answered from a
cache naming rowids that no longer exist, and stage one picks candidates on the
sign bits of text the index no longer holds. Cost is nil: the cache is rebuilt
lazily on the next query, and `putVector` already invalidates once per embedded
passage.

## What the tests assert, and that they were seen red

Two cases in `tests/features/search-two-stage.test.ts`, under the existing
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
   assertions.

The fixture is built through the public build/update API with the documented
options; nothing reaches into internals beyond the existing `rank()` cast the
file already uses, and the index is over the code-building floor honestly rather
than by lowering it.

**Red step, on the committed unfixed tree** (tests committed alone at
`98bbb5b`, source untouched, working tree clean):

```
 × the codes stay level with the vectors > takes the codes with the body passages a full-text catch-up replaces
   → expected 1201 to be 1200 // Object.is equality
 × the codes stay level with the vectors > takes the codes with the own words an update rewrites
   → expected 602 to be 601 // Object.is equality

 Test Files  1 failed (1)
      Tests  2 failed | 14 passed (16)
```

Full suite on that tree: **1250 passed, 2 failed (these two), 7 skipped, 1259
total**. After the fix: **1252 passed, 7 skipped, 1259 total, 0 failed**.
`npm run typecheck`, `npm run typecheck:tests`, `npm run lint` and `npm run
build` are all clean. (Prettier reports all three touched files as unformatted,
but it reports each of them unformatted on `4467663` too, so it is not a gate
here and I left formatting alone.)

## A third case I wrote and dropped, and why

I also wrote a case for the sharper hazard the `deleteItemCodes` comment warns
about: run the catch-up on the **last** item indexed, whose passage holds the
largest rowid, which SQLite hands straight back to the next insert. The
replacement then inherits its predecessor's code, the count of codes still
matches the count of vectors, and `loadCodes` cannot see anything wrong — stage
one would silently rank the new passage by the old text's sign bits.

**That case passes without this change**, so I removed it rather than ship a
test that proves nothing. The reason it passes: `putVector` (`:1407-1416`)
resolves a passage id to its rowid and deletes whatever code sits there before
storing the new vector, so any re-embedded replacement cleans up an inherited
code by itself. The reuse hazard is real only for a passage that is cleared and
never re-embedded — and that case shows up as an ordinary orphan and is caught
by the count check like any other.

I mention it because it is the one place my reading revised the defect
description: the durable consequence is the silent exact-scan fallback, and *not*
silently wrong candidate selection on a healthy-looking index.

## What I could not verify

- **The resident-cache half of the fix is not covered by a test.** The
  `invalidateCodes()` calls rest on the reasoning above (consistency with every
  other vector-removing path, plus the await window inside the catch-up loop). I
  could not find a public-API observation that distinguishes a stale resident
  cache from a fresh one: after a normal update the cache is dropped anyway by
  `refreshCodes`, and during one the difference shows up only as recall wobble on
  a query racing the update, which no deterministic assertion I could write
  pins down. Stated plainly rather than papered over with a test that would pass
  either way.
- **No measurement on a real library.** The 42x figure is the maintainer's own,
  from the 1.9.0 CHANGELOG entry for #30; I did not re-measure it, and the tests
  assert the coded path is *taken*, not how fast it is.
- The fix touches the SQLite backend only. The JSON backend
  (`index-manager.ts:2614/2630`) and the corrupt-store stub
  (`corruption.ts:133/139`) hold no codes and need nothing.
