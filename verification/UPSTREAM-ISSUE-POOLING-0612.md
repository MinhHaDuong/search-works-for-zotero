# `ZOTEUS_EMBEDDING_MODEL` reaches the local path, but pooling does not follow the model

Since #43 the local provider loads any transformers.js feature-extraction model
the user names, and the docs invite exactly that. The pipeline call underneath
it is still

```ts
const tensor = await extractor(input, { pooling: 'mean', normalize: true });
```

`mean` is a property of a model, not of the pipeline. It is right for
`all-MiniLM-L6-v2`, which is why nothing has shown up until now: the default was
the only model that could reach this line. The knob makes the line reachable for
models that pool differently, and roughly half the multilingual field does — of
23 sentence-embedding models I have pooling for, 10 declare `cls` and one
`last_token`, read from each model's own `1_Pooling/config.json`.

A wrong pooling mode does not fail. It loads, embeds, returns the right shape,
and retrieves worse, so it reads to the user as the model being bad.

## What it costs

Measured on a 257-passage, 68-query cross-lingual set (English, French, German,
Vietnamese, Russian queries against passages in the target language, with
declared relevant passages). Same driver, same corpus, same `fp32` weights, same
input template; the pooling mode is the only thing that differs between the two
arms of each row.

| model | declares | MRR `cls` | MRR `mean` | MRR | hit@1 | hit@5 |
|---|---|---|---|---|---|---|
| `onnx-community/granite-embedding-97m-multilingual-r2-ONNX` | `cls` | 0,5301 | 0,3842 | **-27,5%** | -34,6% | -12,2% |
| `onnx-community/gte-multilingual-base` | `cls` | 0,7255 | 0,6331 | **-12,7%** | -10,3% | -19,6% |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | `cls` | 0,6560 | 0,5887 | **-10,3%** | -14,7% | -11,3% |
