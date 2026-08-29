## The defect

`cosine` in `sqlite-index.ts` walks every stored vector twice — once inside `norm(b)`,
once for the dot product. And the `norm` it calls is the same one `vectorSearch` calls
with the query's `number[]`, while every row passes a `Float32Array`: one `number[]`
observation is enough to make that call site polymorphic for the life of the process,
and it never recovers. The `ArrayLike<number>` signature was the tell.

## The fix

Accumulate the dot product and the row's squared norm in one pass, and narrow `norm` to
`number[]` so its call site sees one shape. `vector-store.ts` carries the same two-pass
shape and gets the same treatment; its `norm` was already monomorphic, so it gains the
traversal half only.

## Measured

255 703 rows at 3072 dimensions, calling the built function over a real scan, five
interleaved repetitions:

| | median | µs/row |
|---|---|---|
| two-pass (before) | 8 606 ms | 33,66 |
| fused (after) | 3 933 ms | 15,38 |
| iterate + decode, no arithmetic | 2 559 ms | 10,01 |

**2,19x**, and 2,16x comparing the fastest run before against the slowest after. The row
fetch underneath does not move, which is why the whole scan gains less than the
arithmetic does: isolated from SQLite the arithmetic alone is 3,77x, of which 2,01x is
the traversal and 1,87x the polymorphic call site.

Driver and raw results:
[`bench/cosine_fusion.mjs`](https://github.com/MinhHaDuong/search-works-for-zotero/blob/main/bench/cosine_fusion.mjs),
[`bench/results/0070-cosine-fusion/`](https://github.com/MinhHaDuong/search-works-for-zotero/tree/main/bench/results/0070-cosine-fusion).

## Bit-identical, and checked as such

The same products are summed in the same order, so no index needs rebuilding and no
ranking moves. Verified over a whole 255 703-row store rather than a fixture: zero
mismatches, top-15 ids and scores identical. `tests/features/vector-cosine-equivalence.test.ts`
runs the previous implementation beside the current one over non-unit vectors spanning
eight orders of magnitude, zero rows, both directions of width mismatch, and NaN
propagation, comparing with `Object.is` so a sign-of-zero difference would fail.

The width-mismatch path is what makes bit-identity unconditional, and it is kept out of
line so the hot function stays small: the old code summed the norm over all of `b` while
stopping the product at the shorter operand. Nothing reaches it through `query()`, which
drops stale vectors on a width change, but an index holding two generations of vectors
does.

Existing suite unchanged: 752 passed, 7 skipped; `tsc --noEmit` and `eslint` clean.

## What this does not claim

It does not fix #30. The scan measured here is 8,6 s where that issue reports ~95, and
nothing measured here explains the gap on Windows / Node 24 — which is also what decides
what this change is worth there. If the gap is a uniform CPU-side slowdown the ratio
carries; if it is I/O, most of the ~95 s is untouched by anything in this diff. One line
would tell: whether a second identical query, run immediately after the first, is faster.

Alternatives considered. Precomputing each row's norm at index time would beat this, but
it needs a schema column and a rebuild to populate, and every embedder in use returns
normalized vectors — which would make the stored norm a constant 1, and the column dead
weight the day one does not. Reading the norm as 1 outright was rejected for the same
reason: true of every embedder shipped today, and not a property `cosine` can assume.
