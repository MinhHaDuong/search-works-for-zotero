# Comment D — the Matryoshka + binary measurement for upstream #30

Draft, not posted. For [oscardvs/zoteus#30](https://github.com/oscardvs/zoteus/issues/30),
following Comment C (posted 2026-08-29). A comment, not a PR — it spends no in-flight slot.

Numbers transcribed from `bench/results/0038-mrl-binary/`. Written in upstream's decimal
style (period), so the figure guard deliberately does not cover this file. After posting:
record on SYNC.md's #29/#30 row and delete this file.

---

Following up on my last comment with numbers rather than opinions. I re-ran the question on
a real library — 93,022 passages out of a working Zotero collection, three embedding models,
same passages and same probes throughout. Drivers and raw JSON are linked at the bottom.

Short version: **one of your three options is much cheaper than it looks, there is a fourth
option nobody has mentioned, and the two combine.**

## The frame that made the rest make sense

The cost of one semantic query is roughly

> number of vectors × bytes per vector × cost per byte

Your three proposals each move a different factor, which is why they are not really
alternatives:

- **an in-memory cache** moves *where the bytes live* — same bytes, same arithmetic
- **sqlite-vec** moves *cost per byte* — the same linear scan, in C instead of JS
- **an HNSW sidecar** moves *number of vectors* — the only one that changes the asymptotics

The factor none of them touches is **bytes per vector**, and at 3,072 dimensions that is
where your problem is: 12,288 bytes per passage, about 3.1 GB for your index, moved and
multiplied on every query. Two independent levers act on it, and they multiply.

## Lever 1: 1-bit codes are nearly free, and get better as vectors get wider

Store each vector a second time as one bit per dimension (the sign), scan those by Hamming
distance, keep a pool of candidates, then rerank the pool exactly against the real float32
vectors. Only the codes are scanned; the float vectors are touched for a few hundred rows.

Measured on real embeddings, recall@30 against the exact ranking, pool of 8× the result set:

| vector width | bits per code | recall@30 |
|---|---|---|
| 384 (all-MiniLM-L6-v2) | 384 | 0.953 |
| 768 (nomic-embed-text-v1.5) | 768 | 0.971 |
| 1024 (Qwen3-Embedding-0.6B) | 1024 | **0.997** |

The trend is the useful part: **binary quantization gets more accurate as the vectors get
wider**, because a wider vector gives a longer code. This is the opposite of the usual
worry, and it means the technique suits your 3,072 dimensions better than it suited the
384-dimension case where I first measured it. Your codes would be 3,072 bits — 384 bytes a
passage, about 98 MB for your whole index, against 3.1 GB.

At 1024 dimensions on my machine that scan ran 212.5 ms exact against 12.9 ms binary, a
16.4× speedup at 0.997 recall.

## Lever 2: Matryoshka truncation — free dimensions, if your model is trained for it

Most current embedding models are trained with Matryoshka Representation Learning, which
means a *prefix* of the vector is itself a valid embedding. You can keep the first 768 of
3,072 dimensions and still have a working vector — no retraining, no re-embedding, no API
calls. You almost certainly have such a model: at 3,072 dimensions you are on
`text-embedding-3-large` or `gemini-embedding-001`, and both are MRL-trained.

This one needs care, because how expensive it looks depends entirely on what you measure it
against, and the two answers differ by a factor of ten.

Measured as rank agreement — does the truncated vector reproduce the full vector's exact
top-30 — halving the width looks costly: 1.000 → 0.864.

Measured as retrieval quality on a task with an answer key, it is cheap. I used the
library's own structure: a passage from a given document is a query, and the other passages
of that same document are the relevant results (excluding neighbouring chunks, which
overlap textually and would make the task trivial). 400 probes:

| model | width | recall@30 | MRR |
|---|---|---|---|
| Qwen3-0.6B | 1024 | 0.4935 | 0.7742 |
| Qwen3-0.6B | 512 | 0.4821 | 0.7690 |
| Qwen3-0.6B | 384 | 0.4781 | 0.7657 |
| Qwen3-0.6B | 256 | 0.4699 | 0.7542 |
| all-MiniLM-L6-v2 | 384 | 0.4389 | 0.7305 |

**Quartering the width costs 4.8% of retrieval quality** (0.4935 → 0.4699), where the rank
metric implied a 22-point collapse. Both numbers are correct; they answer different
questions. Rank agreement counts every reshuffle among near-equivalent neighbours as a
loss, and a user does not experience a reshuffle among equivalents as a loss.

A side result that may interest you more than the main one: **at equal width, which model
you use matters more than how many dimensions you keep.** Qwen truncated to 384 scores
0.478 against MiniLM's native 384-dimension 0.439 — 9% better on the same width and the
same probes. Truncated all the way to 128 it still matches MiniLM. So a big model cut down
beats a small model trained narrow, which is worth knowing before anyone concludes the fix
is a smaller embedder.

## Put together, at your geometry

I built a 255,703 × 3,072 index to measure the scan itself, keeping the float32 vectors for
reranking and scanning only the codes. Same machine for every row, timed round-robin so a
transient cannot land inside one candidate:

| representation | bytes scanned | median per query | vs today |
|---|---|---|---|
| float32 out of SQLite, one row at a time — what v1.9.0 does | 3.1 GB | 4,088.7 ms | 1x |
| 1-bit codes at 3,072 dims | 98 MB | 97.2 ms | **42x** |
| 1-bit codes on a 768-dim Matryoshka prefix | 24 MB | 26.7 ms | **153x** |

The speedup is larger here than the 16x I measured at 1,024 dimensions, and for the reason
above: the wider the vectors, the more binarization saves.

## Two things that will bite

**You cannot delete the float32 column.** The rerank is what buys the accuracy back. At half
width, reranking against the full vectors scores 0.972; reranking against only the narrow
ones scores 0.860. So this makes queries fast, it does not reclaim the 3 GB.

**Do not write the Hamming distance with BigInt.** It is the obvious way to do it in
JavaScript, and I measured it at your geometry alongside everything else: 18,635 ms, against
97 ms for the same codes in a `Uint32Array` with a SWAR popcount, and against 4,089 ms for
the exact float scan it was supposed to replace. The right design implemented the obvious
way is 4.6 times slower than doing nothing. That one detail decides whether any of this is a
speedup.

One smaller finding: subtracting the corpus mean before taking the sign bits buys accuracy,
and buys more the narrower you go — nothing at full width, +2.7 points at a quarter width,
+4.5 points at an eighth. Zotero's own semantic-search work does the same thing
([zotero/zotero#6012](https://github.com/zotero/zotero/pull/6012)'s
`modelCalibration.meanVector`).

## One thing I could not measure, and the one-minute experiment that would settle it

An exact scan of your shape — 255,703 vectors at 3,072 dimensions, decoded one BLOB per row
out of SQLite the way v1.9.0 does it — takes 4.1 s on my machine, against the 90 to 105 s
you report. That is a factor of more than twenty I cannot account for from here, and I would
rather leave it open than pick a plausible cause and dress it up as a finding.

The experiment costs you a minute: **run the same semantic query twice in a row.** If the
second is much faster, the cost is getting bytes off disk, and shrinking the bytes is
exactly the fix. If both take the same time, it is arithmetic, and shrinking the bytes is
still the fix but for a different reason. Either answer is useful; guessing is not.

## Caveats

Recall is measured against the exact *vector* ranking, not against relevance — and your
search fuses keyword and vector with RRF, so vector recall does not translate one-to-one
into answer quality in either direction. The relevance task is document-level topical
relatedness, which can show a model is too weak but cannot certify one is good enough for
real questions. Probes are indexed passages, leave-one-out; with chunk overlap a passage
neighbours its own siblings, which makes the task easier than a real query.

The two kinds of measurement have different reach, and it matters which is which. Every
**recall** figure comes from real embeddings of a real library, 93,022 passages at 384, 768
and 1,024 dimensions — not at your 3,072, so read the trend rather than the row. Every
**timing** figure at 255,703 × 3,072 uses synthetic vectors, which is legitimate because
scan time depends on how many bytes there are and what arithmetic runs over them, not on
what the numbers mean. All of it is Linux, and none of it is Windows.

Drivers and artifacts, if useful:
[`bench/vec_mrl_recall.mjs`](https://github.com/MinhHaDuong/search-works-for-zotero/blob/main/bench/vec_mrl_recall.mjs),
[`bench/vec_task_recall.mjs`](https://github.com/MinhHaDuong/search-works-for-zotero/blob/main/bench/vec_task_recall.mjs),
[`bench/vec_scan_shapes.mjs`](https://github.com/MinhHaDuong/search-works-for-zotero/blob/main/bench/vec_scan_shapes.mjs),
[`bench/results/0038-mrl-binary/`](https://github.com/MinhHaDuong/search-works-for-zotero/tree/main/bench/results/0038-mrl-binary).
The recall driver reproduces my earlier 384-dimension figures exactly as a self-check, and
it also detects the damage when truncating a model that is *not* Matryoshka-trained, so it
is not blind in either direction.
