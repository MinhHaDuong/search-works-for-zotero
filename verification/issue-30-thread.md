# Upstream issue #30, read end to end

*Written 2026-08-29, after the issue closed and v1.10.0 shipped. Evidence, not
authority: where this touches the design, the owning document is the record.*

Issue #30 ran five days from a user's performance report to a shipped
implementation. This reads the thread for two things: what our evidence
actually bought, and whether what we told him was true.

## What the thread did

@Michael-Logies reported `zotero_semantic_search` at 90–105 s per query over
255 703 passages at 3 072 dimensions, correctly self-diagnosed as the per-row
JS vector scan, and proposed three fixes: sqlite-vec's `vec0`, an in-memory
vector cache, or an HNSW sidecar. Two comments went from here — the retired
0008 evidence pack, then comment D with the cost-model frame. The maintainer
then built the answer himself (`ad7c434`) and shipped it in v1.10.0.

## What he adopted, and it is more than a citation

Five distinct findings from our two comments are in his implementation, four of
them named in his own words:

| Finding | Where it landed |
|---|---|
| Mean-centring before taking sign bits | `packCode()`, citing zotero/zotero#6012's `modelCalibration.meanVector` — the same reference our comment made |
| SWAR popcount over `Uint32Array`, **not** BigInt | `nearestByHamming()`, commented "not BigInt, per the measurements in this thread", quoting our 18 635 ms against 97 ms |
| The 4x/8x/16x recall table (0,884 / 0,953 / 0,986) | `limits.ts`'s doc-comment, reproduced verbatim, with our "rises with the width of the vectors" trend |
| Batching the rescore into one statement per pool | `RESCORE_BATCH` + `rescoreStatement()`, commented "issuing a statement per candidate was about half the cost of the entire two-stage query" — our 30,4-of-61,5 ms finding |
| The float32 column cannot be deleted | The second stage is mandatory; his doc-comment carries our binary-only 0,592 |

Two design choices of his own are better than what we proposed. He selects the
candidate pool with a **counting sort over a Hamming histogram** rather than a
heap — which answers, structurally, the one caveat our first comment raised
about `vec0` (its k-best cost growing worse than linearly in k). And he made
`vector_codes` **not** a schema bump, so an existing index gains codes from its
next query instead of charging its owner a re-embed.

His defaults hold up on inspection. The 16x oversample carries a 500-candidate
floor, codes are not built below that size at all, and any doubt about their
coverage routes the query back to the exact scan. I checked for the failure
mode where an adopted constant loses the mechanism around it — a small or
narrow index where a 16x pool costs more than scanning everything — and did not
find one.

## Where we were wrong

**The baseline row in comment D is mislabelled, and it is the row everything
else was measured against.**

`bench/vec_scan_shapes.mjs`'s `sqlite_float32` candidate is described, in the
driver, in the artifact, and in the public comment, as "what v1.9.0 does". It
is not. Its loop accumulates the dot product and the row norm in **one**
traversal, with no `norm()` function shared between the query side and the row
side. That is the shape PR #31 *created*. What v1.9.0 ran was two traversals
per row through a `norm()` reached with a `number[]` from the query and a
`Float32Array` from every row — polymorphic for the life of the process, which
is precisely the defect #31 removed.

Two committed artifacts disagreed about the same quantity — 4 893,9 ms in
`0025-x1-recall/scan-shapes-255703x3072.json`, 8 606,1 ms in
`0070-cosine-fusion/insitu-255703.json` — and being from different drivers on
different fixtures, neither could settle it against the other. So the ratio was
measured directly instead, all three shapes in one process over one SQLite
table (`verification/probes/scan-shape-v190-vs-fused.mjs` →
`bench/results/0025-x1-recall/scan-shape-attribution.json`):

| shape | µs/row | vs v1.9.0 |
|---|---|---|
| `v190_two_pass_shared_norm` — what v1.9.0 ran | 80,826 | 1x |
| `two_pass_monomorphic_norm` — isolates the polymorphism | 56,889 | 1,42x |
| `fused_inline` — what `scan_shapes` measures, what #31 shipped | 35,360 | **2,29x** |

Of the 2,29x, 1,42x is the polymorphic call site alone and the remainder is the
second traversal. All three return the same cosine to nine decimals, so the
timings compare one thing. The 2,29x agrees with ticket
0070's 2,19x, measured independently in situ on the real 3,4 GB store, which is
the ratio #31 shipped on.

**What that changes.** Comment D told him an exact scan of his shape "takes
4.1 s on my machine, against the 90 to 105 s you report. That is a factor of
more than twenty." Like for like — he was running v1.9.0 when he measured
95 s — our own v1.9.0-shape number is 2,29 × 4 088,7 ≈ 9,4 s, or 8,6 s by
ticket 0070's independent in-situ run. **The gap is about 10x, not "more than
twenty."** The maintainer carried the larger figure into his closing comment as
an open mystery: "a factor of ~20 between your machine and the measured scans
remains unexplained and may be I/O on Windows." Roughly half of that factor was
never his machine. It was our own two drivers being quoted interchangeably.

**What it does not change.** The 42x speedup figure is measured fused-against-
binary, so it is the correct number to quote against **v1.10.0**, which is
fused — his codebase doc-comments are right. Against v1.9.0 the true figure
would have been ~88x. The error is confined to the size of the unexplained gap;
it did not propagate into his code, and the recall figures are untouched by it.

This is the `adopted constants carry mechanisms` failure in its cleanest form.
Every value here was correct, declared to the figure guard, anchored, and
reconciled across three runs — the guard checks that a number matches its
artifact, and cannot check that the artifact measures what its label claims.

## v1.9.0 against v1.10.0, measured here

The issue was closed on a prediction — "a few hundred ms" — that nobody had
tested. Measured on a real index of the author's library (93 022 passages,
384 dimensions, real vectors from `all-MiniLM-L6-v2`, provenance controlled by
re-embedding five sampled rows and getting cosine 1,000000 against the stored
row), three arms interleaved, 100 warm samples each
(`bench/results/0025-upstream-v190-vs-v1100/`):

| arm | p50 | p95 | `vectorScan` |
|---|---|---|---|
| v1.9.0 `bb414df` | 1 069,1 ms | 1 363,5 ms | field does not exist |
| v1.10.0, `ZOTEUS_INDEX_ANN=false` | 814,6 ms | 1 084,7 ms | `exact` ×100 |
| v1.10.0 stock | **21,7 ms** | **39,1 ms** | `codes` ×100 |

**49,3x on the median**, reproduced independently at 49,3x a second time. The
`vectorScan` field reads `codes` on every warm sample of the default arm and
`exact` on every sample of the `ANN=false` arm, so it is a control that can come
out the other way rather than a reading taken once.

The decomposition is the part worth keeping. **#31's fused loop contributes
1,31x; the two-stage contributes the remaining 37,5x.** #31's own commit
measured 2,19x at 255 703 × 3 072, and the gap is consistent with the model that
commit states — a width-proportional arithmetic saving sitting on a per-row
fetch cost that does not shrink with it, and these vectors are eight times
narrower. Consistent, not established: this run did not isolate it.

The approximation is close to free at this size. Same first hit on 20 of 20
queries, identical top-10 order on 17 of 20, mean overlap 9,65 of 10. The
one-time code build costs about 1,5 s, measured apart from the model download
that confounded it in the first attempt.

**The absolutes are soft and the ratio is not.** Every arm is slower warm than
cold — v1.9.0 963,8 → 1 069,7 ms, the exact arm 692,7 → 815,0, the two-stage
20,6 → 21,8 — and the same drift appears in the second run. That is the opposite
of cache warming, so something degrades across a ten-minute run; a fanless 15 W
i5-8250U throttling is the obvious candidate and nothing here measured CPU
frequency, so it stays a candidate. What matters is that it moves all three arms
the same way: the median ratio reproduced at 49,18x and 49,11x, while the p95
ratio did not (34,9x then 40,0x, the exact arm's tail moving). Quote the median
ratio; treat the absolute latencies as this machine's, and do not quote a p95
ratio at all.

Two things this does **not** license. `mode:"auto"`, the hybrid default a user
actually gets, improves 12,2x rather than 49x — the BM25 side is untouched by
either change and the residual is about 70 ms. And nothing here bridges to the
reporter's 95 s: this machine's v1.9.0 baseline is 1,07 s where his is ~95 s,
his index reads 3,1 GB of vectors per query against our 143 MB, and the
difference between the two machines is the same open question `999cb1c`
flagged. 49x is a floor for his geometry rather than a ceiling, and it is not a
prediction of what he will see.

## What the thread leaves open

**The remaining gap, now roughly 10x.** The reporter answered the two-run
experiment 18 seconds after the close, and his answer is a real result: five
sequential queries at 93,3 s then 93–105 s, no cold-start penalty, on an index
that should have been file-cached after the first pass. That rules out
first-read I/O on his machine. His environment is unusual in ways that could
still matter (Windows 11 host, VMs on Veracrypt-encrypted container disks,
Primocache, 15-minute Macrium images) and nothing measured here can attribute
the residue, so it stays an open question rather than a residual.

There is now a sharper experiment than the one we proposed, and v1.10.0 ships
it: **`ZOTEUS_INDEX_ANN=false`**. The same query, same process, same machine,
run once each way, separates the two candidate explanations cleanly — the
two-stage path scans 94 MB where the exact path scans 3,1 GB, so if his cost
tracks bytes moved it must fall by more than an order of magnitude, and if it
does not, the cost is per-row overhead that has nothing to do with the vectors.
He is going to run v1.10.0 anyway; this costs him one environment variable.

**The Matryoshka prefix.** The second multiplying lever, and the one thing from
comment D he did not build: the committed artifact reads 195,8x for codes over
a 768-prefix against 55,9x for full-width codes. He has since confirmed from
his side that `text-embedding-3-large` is MRL-trained, so it applies directly
to the setup that produced this issue. Not a contained change and not ours to
send.

## Recommendation

Post one short correction on #30. It is our error, it is in the direction that
made our own evidence look better than it is, and it retires half of a mystery
the maintainer has written into his closing comment and will otherwise chase.
Pair it with the `ZOTEUS_INDEX_ANN=false` experiment, which is the useful half
of the same message.
