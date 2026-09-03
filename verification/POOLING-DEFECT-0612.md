# What upstream's hardcoded `mean` pooling costs

*Ticket 0612. Measured 2026-09-03 on doudou against upstream `76bbb07`.*

## The question

On 2026-09-03 upstream closed issue #43 by making `ZOTEUS_EMBEDDING_MODEL` reach
the local provider: the on-device pipeline now loads any transformers.js
feature-extraction model the user names, and `docs/semantic-search.md` says so in
those words, with a link to the Hub's filtered list. The pipeline call did not
change with it. `src/features/search/embeddings.ts` still reads

```ts
const tensor = await extractor(input, { pooling: 'mean', normalize: true });
```

for every model, and `dtype` appears nowhere in the file.

Ticket 0421 established the class in 2026-08 from the model cards: pooling is a
property of a model, and `bench/models.json` records 10 `cls` and one
`last_token` against 10 `mean` across 23 entries, each read from that model's own
`1_Pooling/config.json`. What nobody had was a number. A maintainer told "your
code applies the wrong pooling" is entitled to ask what it costs, and until this
ticket the answer was an inference from a config file.

## Method

One driver, one corpus, one flag. `bench/cross_lingual_probe.mjs` embeds the
ticket 0266 cross-lingual set — 257 pool passages, 68 queries in English,
French, German, Vietnamese and Russian with declared relevant passages — and
`bench/cross_lingual_score.py` ranks the pool for each query and reports MRR
and hit@k. The two arms of each pair differ in the pooling mode and in nothing
else: same driver, same corpus, same `fp32` dtype, same input template, same
batch size, same machine.

The control arm is not re-derived. Each model's `cls` cell is the one already
committed under `0266/vectors/`, measured on 2026-08-30 for R29.

**Positive control.** Before any delta was read, the patched driver re-ran one
committed cell with no flag — `gte-multilingual-base` at fp32, declared `cls`.
The result is field-for-field identical to the committed cell, `pair_summary`
included. That is what licenses reusing the committed `cls` cells as control
arms rather than re-running them, and it is what rules out the patch itself as
the source of any difference below.

**What the forced arm is.** For `gte-multilingual-base` and
`granite-97m-multilingual-r2` the registry declares an empty input template on
both sides, and neither id carries `e5` as a segment, so upstream applies no
prefix either. For those two models the forced-`mean` arm is not a hypothetical
configuration: it is exactly what upstream produces today for that model id.
`arctic-embed-m-v2` declares a `query: ` prefix that upstream would not apply,
so its cell holds the template fixed and therefore *understates* what upstream
loses.

Cells and vectors: `~/data/projets/zoteus-bench/0266-pooling/`. Every forced
cell records `declared_pooling` and `pooling_forced: true` in both its manifest
and its score file, so it cannot later be read as a measurement of the model.

## Result

Every model degrades, and the direction is the same in all three.

| model | declares | MRR `cls` | MRR `mean` | MRR | hit@1 | hit@5 |
|---|---|---|---|---|---|---|
| `onnx-community/granite-embedding-97m-multilingual-r2-ONNX` | `cls` | 0,5301 | 0,3842 | **-27,5%** | -34,6% | -12,2% |
| `onnx-community/gte-multilingual-base` | `cls` | 0,7255 | 0,6331 | **-12,7%** | -10,3% | -19,6% |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | `cls` | 0,6560 | 0,5887 | **-10,3%** | -14,7% | -11,3% |
