# What upstream's hardcoded `mean` pooling costs

*Ticket 0612. Measured 2026-09-03 on doudou against upstream `76bbb07`; the
framing re-checked the same evening against `b0e0bc8`.*

## The question

On 2026-09-03 upstream closed issue #43 by making `ZOTEUS_EMBEDDING_MODEL` reach
the local provider: the on-device pipeline now loads any transformers.js
feature-extraction model the user names, and `docs/semantic-search.md` says so in
those words, with a link to the Hub's filtered list. The pipeline call did not
change with it. `src/features/search/embeddings.ts` still reads

```ts
const tensor = await extractor(input, { pooling: 'mean', normalize: true });
```

for every model.

**Upstream moved again while this was being measured, and one of the two framing
claims did not survive it.** At `76bbb07`, when the ablation started, `dtype`
appeared nowhere in that file. At 13:18 the same afternoon upstream shipped
`ZOTEUS_EMBEDDING_DTYPE` and put the precision into the embedder identity as
`local:<model>@<dtype>` (`230183d`, merged as `b0e0bc8`) — the quantized build
Michael-Logies had asked for that morning, and the precondition the maintainer had
himself named for it. The dtype half of this report's original argument is
therefore delivered, by him, and is struck rather than defended.

What survives is the measurement, and the change sharpens it. Of the three
vector-affecting properties a named model brings with it, input prefixes are now
inferred per model and precision is selectable and carried in the identity.
Pooling is the one still written as a literal at the call site — one occurrence in
the whole `src` tree, applied to every model the knob can name.

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
else: same driver, same corpus, same `fp32` weights, same input template, same
batch size, same machine.

The control arm is not re-derived. Each model's `cls` cell is the one already
committed under `bench/results/0266-cross-lingual/`, measured on 2026-08-30 for
R29.

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

The cross-lingual negative control carries nothing here: `granite-97m` goes from
1/4 clean to 0/4 under `mean`, `gte` from 2/4 to 3/4, the wrong way. At n = 4 and
moving in both directions it is noise, and the MRR and hit@k columns are the
finding.

The spread is wide. `granite-97m` loses more than a quarter of its MRR, the two
base-sized models between a tenth and an eighth. So the cost is not a constant
that could be absorbed as a known tax, and a user cannot predict which of their
candidate models is the one that falls off the cliff.

## Why a `pooling` setting is the wrong remedy

The correct value cannot be read from the repository the code loads.
`1_Pooling/config.json` is a sentence-transformers artifact, and the ONNX mirrors
that the docs point users at do not republish it. Probed against the Hub API on
2026-09-03:

| repository | `1_Pooling/config.json` |
|---|---|
| `Xenova/all-MiniLM-L6-v2` | absent |
| `Xenova/multilingual-e5-small` | absent |
| `onnx-community/gte-multilingual-base` | absent |
| `onnx-community/granite-embedding-97m-multilingual-r2-ONNX` | absent |
| `Alibaba-NLP/gte-multilingual-base` (the original) | present |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | present |

Four of six absent, and the four are exactly the mirrors a transformers.js user
loads. So the auto-detection route that upstream took for the `e5` prefixes —
infer from the id — has nothing to read here, and the alternatives are a curated
value per model or a user-facing setting. A setting is worse than the defect it
fixes: choosing wrong produces no error, only worse retrieval, and the user has
no more access to the right value than the code does.

That is this repository's 2026-08-29 ruling reached from the other end. The
ruling withdrew a precision knob because precision cannot travel alone; the
measurement here shows the axis beside it cannot travel alone either, and for the
same reason. Both are properties of a curated record.

## The remedy, now that dtype has landed

The dtype work upstream shipped this afternoon is the argument for this one, made
by the maintainer in his own code. He would not let precision be selectable until
it entered the identity, because two indexes at different precisions are
otherwise indistinguishable. Pooling is that same sentence one axis over, with a
difference that cuts the other way: precision is something a user chooses, so a
wrong choice is at least the user's own, while pooling is something nobody
chooses, and the wrong value arrives silently with a model the docs invited them
to try.

Pooling also needs less than dtype needed. Because the correct mode is a property
of the model rather than of the user's configuration, the model id determines it,
and the identity already carries the id — so no identity change is required and
no new knob. A curated map from model id to pooling mode, with an unlisted id
keeping today's behaviour exactly, is the whole repair, and it is small enough to
review in one sitting.

The fuller entry stays worth having, and the branch `pr43-minilm-e5-registry` on
the author's fork has its shape: `EmbedderEntry` pins model, a 40-character
revision SHA, dtype, graph file, pooling, normalize, query and passage templates,
window and dimension, and every executed field enters the fingerprint that becomes
vector identity. That branch predates everything upstream shipped today and
touches the file it rewrote, so it is material to mine rather than a change to
send: the rebuild goes onto the new seam, staged, pooling first.

One thing the measurement changes about how the ask is put. The registry does not
need its own selector. `ZOTEUS_EMBEDDING_MODEL` can keep the spelling and the
meaning it has: an id that names a curated record gets the record's fields, an id
that does not behaves as it does today. That is the maintainer's own stated
objection to a second variable, applied to our own proposal.

## A third field, same class

`ZOTEUS_EMBEDDING_PREFIXES` changes the vectors and is excluded from the identity
by explicit design (the docstring in `embeddings.ts` and the docs both say so).
Build an index with `off`, then unset it: the queries carry `query: `, the stored
passages carry nothing, the identity is unchanged, and no rebuild notice fires.
It needs the user to move that setting between a build and a query, so it is
narrower than the pooling case — but it is the identity-completeness argument in a
third instance, which is what makes the argument structural rather than a
complaint about one field.

## Reproducing

```bash
node bench/cross_lingual_probe.mjs --pkg-root <tjs> \
  --pool  ~/data/projets/zoteus-bench/0266/pool.jsonl \
  --queries ~/data/projets/zoteus-bench/0266/queries.jsonl \
  --model gte-multilingual-base --dtype fp32 --force-pooling mean \
  --out-prefix <out>/gte-multilingual-base-fp32-forced-mean
python3 bench/cross_lingual_score.py --prefix <out>/gte-multilingual-base-fp32-forced-mean \
  --pool ~/data/projets/zoteus-bench/0266/pool.jsonl \
  --queries ~/data/projets/zoteus-bench/0266/queries.jsonl \
  --output <out>/gte-multilingual-base-fp32-forced-mean.score.json
python3 bench/pooling_ablation_summary.py \
  --control-dir bench/results/0266-cross-lingual \
  --ablation-dir bench/results/0612-pooling-ablation \
  --output bench/results/0612-pooling-ablation/SUMMARY.json
```

Cells: `bench/results/0612-pooling-ablation/` (forced) against
`bench/results/0266-cross-lingual/` (correct). Vectors:
`~/data/projets/zoteus-bench/0266-pooling/`.
