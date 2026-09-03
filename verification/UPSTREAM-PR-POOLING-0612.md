# Pooling follows the model, the way prefixes and dtype now do

*Draft PR body, ticket 0612. Not sent. Written against upstream `b0e0bc8`.*

Since #43 the local provider loads any transformers.js feature-extraction model
the user names, and the docs invite exactly that. Two of the three properties a
named model brings with it now follow it: input prefixes are inferred from the
id, and `ZOTEUS_EMBEDDING_DTYPE` selects the precision and carries it into the
identity. Pooling does not. There is one occurrence in the whole `src` tree,

```ts
const tensor = await extractor(input, { pooling: 'mean', normalize: true });
```

and it applies to every model. `mean` is right for `all-MiniLM-L6-v2` and for
`multilingual-e5-small`, which is why nothing has shown up: those were the models
that could reach it. Of 23 sentence-embedding models I have pooling for, read
from each model's own `1_Pooling/config.json`, 10 want `cls` and one
`last_token`.

A wrong pooling mode does not fail. It loads, embeds, returns the right shape and
retrieves worse, so it reads to the user as the model being bad.

## What it costs

Measured on a 257-passage, 68-query cross-lingual set (English, French, German,
Vietnamese and Russian queries against passages in the target language, with
declared relevant passages). Same driver, same corpus, same `fp32` weights, same
input template; the pooling mode is the only thing that differs between the two
arms of each row.

| model | declares | MRR `cls` | MRR `mean` | MRR | hit@1 | hit@5 |
|---|---|---|---|---|---|---|
| `onnx-community/granite-embedding-97m-multilingual-r2-ONNX` | `cls` | 0,5301 | 0,3842 | **-27,5%** | -34,6% | -12,2% |
| `onnx-community/gte-multilingual-base` | `cls` | 0,7255 | 0,6331 | **-12,7%** | -10,3% | -19,6% |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | `cls` | 0,6560 | 0,5887 | **-10,3%** | -14,7% | -11,3% |

For the two `onnx-community` models neither id carries `e5` as a segment and
neither wants a prefix, so the `mean` column is not a hypothetical configuration:
it is what Zoteus produces for those model ids today. The Snowflake row holds its
`query: ` prefix constant across both arms, which Zoteus would not apply, so that
row understates the loss.

Before reading any of those deltas I re-ran one untouched cell through the
patched harness and confirmed it reproduced the previously committed result field
for field, so the harness change is not the source of the difference.

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

Pooling also needs less than dtype needed on one point. Precision is chosen by
the user and so had to enter the identity; pooling is a property of the model, the
id determines it, and the identity already carries the id — so the table changes
no identities, and the override sits exactly where `ZOTEUS_EMBEDDING_PREFIXES`
sits.

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

## What this does not change

The default model, the identity format, the prefix logic, the dtype logic.
`ZOTEUS_EMBEDDING_MODEL` keeps its spelling and its meaning, and the new override
carries no weight in the embedder identity, in the same position
`ZOTEUS_EMBEDDING_PREFIXES` occupies.

---

*Implementation detail, test evidence and diffstat are filled in from the built
branch before this is sent.*
