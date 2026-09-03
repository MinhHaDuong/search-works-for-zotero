# Pooling follows the model, from a curated table

*Draft PR body, ticket 0612. Not sent. Written against upstream `b0e0bc8`, after
issue #51.*

Fixes #51.

Your issue reaches the conclusion this branch was built on, from the other side
and independently: the pooling has to be curated, because the file that declares
it is not in the repository the weights are loaded from and the mirror-to-source
mapping is not derivable across organisations. The branch was written before #51
was filed, so read it as a second arrival at the same place rather than as a
response to it, and it follows the identity rule your issue specifies for step 2
exactly: `mean` stays unsuffixed, so no existing index is declared stale by the
arrival of the field.

On the ordering, one observation rather than an argument. Step 1 as you describe
it — keep `mean`, name the assumption — needs a known-pooling set to decide what
to warn about, and that set is the same curated object as step 2 minus its
values. Once the list exists, carrying `cls` beside a name costs nothing more
than carrying the name.

`mean` is right for `all-MiniLM-L6-v2` and for `multilingual-e5-small`, which is
why it has cost nothing so far: those were the models that could reach the call.
Across the sentence-embedding models whose `1_Pooling/config.json` I have read,
`cls` is about half the multilingual field.

**One correction to #51's sampling, and it is the reason a family name cannot
stand in for a lookup.** The proposed known-pooling set lists `gte` among the
mean-pooled families. The family is split:

| repository | `1_Pooling/config.json` |
|---|---|
| `thenlper/gte-small` | `mean` |
| `thenlper/gte-base` | `mean` |
| `Alibaba-NLP/gte-multilingual-base` | **`cls`** |

Read on each repository on 2026-09-03. A known-good set keyed on the family would
therefore assert `mean` confidently for `gte-multilingual-base`, which is the one
gte model measured below and the one that loses most. The table in this PR is
keyed on the full model id for that reason, and lists both the `mean` and the
`cls` rows so a reader can tell a value that was read from one that was
defaulted.

## What it costs

Measured on a 257-passage, 68-query cross-lingual set (English, French, German,
Vietnamese and Russian queries against passages in the target language, with
declared relevant passages). Same driver, same corpus, same `fp32` weights, same
input template; the pooling mode is the only thing that differs between the two
arms of each row.

| model | declares | MRR `cls` | MRR `mean` | MRR | hit@1 | hit@5 |
|---|---|---|---|---|---|---|
| `onnx-community/granite-embedding-97m-multilingual-r2-ONNX` | `cls` | 0.5301 | 0.3842 | **-27.5%** | -34.6% | -12.2% |
| `onnx-community/gte-multilingual-base` | `cls` | 0.7255 | 0.6331 | **-12.7%** | -10.3% | -19.6% |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | `cls` | 0.6560 | 0.5887 | **-10.3%** | -14.7% | -11.3% |

For the two `onnx-community` models neither id carries `e5` as a segment and
neither wants a prefix, so the `mean` column is not a hypothetical configuration:
it is what Zoteus produces for those model ids today. The Snowflake row holds its
`query: ` prefix constant across both arms, which Zoteus would not apply, so that
row understates the loss.

It is a different corpus from your German/English probe and a different task, so
read it as a second opinion rather than as a replacement for one. I will post the
driver and the corpus manifest to the #43 thread so the numbers are checkable
rather than asserted, the way the probe in that thread is. The one thing I
did guard against is the harness: before reading any delta I re-ran an untouched
cell and confirmed it reproduced the previously recorded result field for field,
so the instrument is not the source of the difference.

## Why this is a table under a setting, not a setting alone

The value cannot be looked up from the repository the code loads.
`1_Pooling/config.json` is a sentence-transformers artifact, and the ONNX mirrors
do not republish it:

| repository | `1_Pooling/config.json` |
|---|---|
| `Xenova/all-MiniLM-L6-v2` | absent |
| `Xenova/multilingual-e5-small` | absent |
| `onnx-community/gte-multilingual-base` | absent |
| `onnx-community/granite-embedding-97m-multilingual-r2-ONNX` | absent |
| `Alibaba-NLP/gte-multilingual-base` (the original) | present |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | present |

The `Xenova/*` and `onnx-community/*` mirrors publish no pooling config, so the
id-inference that works for the E5 prefixes has nothing to read. Snowflake ships
both in one repository, which does not help: transformers.js never reads that
file, it pools however the caller says. A setting on its own
would therefore not repair anything for the user it is meant to help — someone
who picks `gte-multilingual-base` because the docs invite them to has no way to
learn it wants `cls`, and would keep the loss above.

This follows the shape `ZOTEUS_EMBEDDING_PREFIXES` already has: a layer that gets
it right by default, and an override for the checkpoint that layer cannot speak
for. The only difference is the oracle. For prefixes the default layer is an
inference from the id; for pooling an inference is impossible, so it is a curated
table instead.

## What this changes

A curated map from model id to pooling mode, consulted at the pipeline call. An
id that is not in the map keeps today's behaviour exactly, so no existing install
moves and nobody is blocked from an unlisted model. Each entry carries the
repository its value was read from, so the table can be checked rather than
trusted.

`ZOTEUS_EMBEDDING_POOLING` overrides it, for a mirrored or renamed checkpoint the
table cannot speak for. Unset, the table decides. Set, the user decides — and the
docs say plainly that a wrong value degrades retrieval silently, the same warning
the dtype hint gives about a repository that does not publish the file it names.

A pooling that is not the default joins the embedder identity, on the same terms
the precision does: `local:<model>#cls`. Adversarial review found the omission
reachable as a corrupt index rather than as a missing notice, and the prefixes
precedent does not cover it. Set the override against the table, then run
`zotero_index action:"update"`: the blocker compares identity, sees no change, and
appends vectors pooled the other way into the index. One index, two vector spaces,
one stamp, and no path that can detect it, because mean and cls share a dimension
and the width check cannot tell them apart. Measured on MiniLM the two readings of
one text sit at cosine 0.53, where a prefix mismatch on a non-E5 model costs
nothing.

## The four models #51's own sample names

`BAAI/bge-small-en-v1.5`, `BAAI/bge-base-en-v1.5`, `mixedbread-ai/mxbai-embed-large-v1`
and `Snowflake/snowflake-arctic-embed-s` are in the table, each read against its
own source repository today. `mxbai` and `arctic-embed-s` publish their own ONNX
graph, the way the arctic-m/l checkpoints do, so each is one id rather than a
`Xenova/` mirror pair.

**One honest result before you read this as "the fix helps every model in the
table."** The cross-lingual figures above are real and reproduced, but the
adversarial review that found them also found the sign inverts on a monolingual
English probe — so I checked what forcing the wrong pooling costs on this
project's own task-comparable metric (0265: a passage is a query whose relevant
set is the other passages of its own Zotero item, gap-excluded so the chunker's
own overlap cannot answer it) rather than trust either corpus alone. Two English
models, four arms: `all-MiniLM-L6-v2` forced from its trained `mean` to `cls`
drops recall@30 7.3% and MRR 2.9% (0.8880→0.8230, 0.9559→0.9285) — the expected
direction, confirming the harness. `bge-small-en-v1.5` forced from its trained
`cls` to `mean` costs **nothing measurable** on the same metric — recall@30 and
MRR both move fractionally positive (0.8620→0.8696, 0.9444→0.9452).

So this is not a claim that fixing pooling improves retrieval for BGE, mxbai or
arctic-embed-s specifically — on this metric it may not, for reasons the review
already surfaced and I have not chased further. The table's job is a correctness
record of what each model was trained with, independent of whether the retrieval
consequence is large on any one task; that is the position the docs already
state ("a record of what each model was trained with, not a list of models this
project recommends") and this result is the reason that sentence has to be taken
literally rather than as a hedge.

## What this does not change

The default model, the prefix logic, the dtype logic, and the identity of every
model pooled the default way, which is every model that could reach the pipeline
before this change. `ZOTEUS_EMBEDDING_MODEL` keeps its spelling and its meaning.

## What is in the diff

`MODEL_POOLING` in `embeddings.ts`: 24 ids — the ONNX repository the pipeline
loads and the source repository it mirrors, since either can be put in
`ZOTEUS_EMBEDDING_MODEL` — each group commented with the repository its value was
read from and when. `mean` rows are listed too, so a reader can tell "known to be
mean" from "unlisted, so mean by default", which the code alone cannot. Then
`poolingFor(model, mode)`, a `pooling` getter on the provider, and the pipeline
call taking it.

`ZOTEUS_EMBEDDING_POOLING` (`auto|mean|cls`) is plumbed the way
`ZOTEUS_EMBEDDING_PREFIXES` is, warning and falling back on an unrecognised
value.

```
 .env.example                             |   8 +
 CHANGELOG.md                             |  31 ++++
 docs/configuration.md                    |   1 +
 docs/semantic-search.md                  |  24 +++
 src/config.ts                            |  35 ++++-
 src/features/search/embeddings.ts        | 121 ++++++++++++++-
 tests/features/embedding-pooling.test.ts | 243 +++++++++++++++++++++++++++++++
```

## Evidence

- `npm test`: 107 files, 1062 passed, 7 skipped — the 7 are the live-credential
  e2e tests, which skip without credentials on `main` too. `npm run typecheck`
  and `npm run lint` clean.
- **The default model's vectors do not move.** Four texts embedded in both roles
  with `Xenova/all-MiniLM-L6-v2` at fp32 through the real
  `@huggingface/transformers`, before the change and after: byte-identical,
  sha256 `3cd53591486a8a25c2707a61b72e40041a419c85216d68e04b67454f609f7f70`.
- **The tests fail against the old code.** Restoring the literal at the call site
  reds exactly three of the sixteen, and only those three.

## One thing to flag rather than bury

An index built with one of the `cls` models between the release that let a model
be named and this one holds mean-pooled vectors, and its queries become
`cls`-pooled against them under an identity that did not change, so nothing warns.
The CHANGELOG and the docs say so and say to rebuild once. Forcing it through the
identity would declare every unaffected index stale to reach a handful that want
rebuilding anyway — and that index is the degraded one this change exists to
prevent, so the rebuild is the repair rather than its price.

The override sits outside the identity for the same reason
`ZOTEUS_EMBEDDING_PREFIXES` does, and inherits the same property: setting it
against the table changes the vectors under an unchanged stamp.

The one judgement call I made rather than leaving to you is that suffix, and I
made it the compatible way on purpose: `fp32`'s rule, applied unchanged. If you
would rather pooling stayed out of the identity, it is one commit to remove.
