# Pooling follows the model, the way prefixes and dtype now do

*Draft PR body, ticket 0612. Not sent. Written against upstream `b0e0bc8`.*

This is the correctness fix you named on #43 — `{ pooling: 'mean', normalize:
true }` applied whatever model is loaded. It is deliberately only that. I had
said on that thread I would re-propose the whole curated registry; the dtype
release answered the part of it that was urgent, so what is left of the registry
is separable and can follow on its own merits. This PR is the part that blocks a
release, and nothing else.

`mean` is right for `all-MiniLM-L6-v2` and for `multilingual-e5-small`, which is
why it has cost nothing so far: those were the models that could reach the call.
Across the sentence-embedding models whose `1_Pooling/config.json` I have read,
`cls` is about half the multilingual field.

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

It is a different corpus from your German/English probe and a different task, so
read it as a second opinion rather than as a replacement for one. The one thing I
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

## What is in the diff

`MODEL_POOLING` in `embeddings.ts`: 24 ids — the ONNX repository the pipeline
loads and the source repository it mirrors, since either can be put in
`ZOTEUS_EMBEDDING_MODEL` — each group commented with the repository its value was
read from and when. `mean` rows are listed too, so a reader can tell "known to be
mean" from "unlisted, so mean by default", which the code alone cannot. Then
`poolingFor(model, mode)`, a `pooling` getter on the provider, and the pipeline
call taking it.

`ZOTEUS_EMBEDDING_POOLING` (`auto|mean|cls`) is plumbed the way
`ZOTEUS_EMBEDDING_PREFIXES` is, down to warning and falling back on an
unrecognised value rather than refusing — `refuse()` in this codebase is for
settings where guessing is dangerous, and this one has a correct value to fall
back to.

```
 .env.example                             |   8 +
 CHANGELOG.md                             |  33 ++++
 docs/configuration.md                    |   1 +
 docs/semantic-search.md                  |  25 +++
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
against the table changes the vectors under an unchanged stamp. Happy to move
both into the identity if you would rather, but that is a larger change than this
defect needs and it would touch every existing index.
