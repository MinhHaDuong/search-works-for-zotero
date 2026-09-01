Thanks for filing this — configurable local embeddings is a real gap, and multilingual-e5-small is a reasonable model to reach for. I spent a while benchmarking local ONNX embedders for a related reason (multilingual retrieval quality generally), and want to share what fell out of that, because the literal proposal here (`ZOTEUS_LOCAL_EMBEDDING_MODEL=<any hf id>`) has a correctness trap that isn't visible from the outside, plus some measured evidence that might save re-deriving it.

## Why a bare model-id swap is riskier than it looks

`LocalEmbeddingProvider.embed()` currently calls the pipeline with a hardcoded
`{ pooling: 'mean', normalize: true }` regardless of `this.model`
(`src/features/search/embeddings.ts:258`), and applies no input-template prefix
to the text at all. `all-MiniLM-L6-v2` happens to want mean pooling, L2
normalization, and no prefix, so this has never been visible as a bug — it's
baked into the one model that's ever been used.

That stops being true the moment the model is configurable. Across a set of
ONNX sentence-embedding models I surveyed on Hugging Face for a multilingual
comparison, a majority declare `cls` pooling in their own `1_Pooling/config.json`,
not `mean` — silently applying mean pooling to a cls-pooling model doesn't error,
it just returns a vector that's subtly wrong, and everything downstream (cosine
similarity, ranking) degrades without any signal that something's off. The E5
family (including `multilingual-e5-small`) is the second half of the same
problem, and this issue already names it correctly: skip the `"query: "` /
`"passage: "` prefixes and retrieval quality drops noticeably, again with no
error.

There's a third trap specific to *which* repo hosts the ONNX weights.
`intfloat/multilingual-e5-small` (the model's own repo) publishes only a plain
`onnx/model.onnx`, plus two files whose names don't match the suffix pattern
transformers.js expects for its other dtypes (int8, uint8, fp16, and so on).
The community ONNX mirror, `Xenova/multilingual-e5-small`, publishes all eight
of the usual suffixed variants. So the same model name resolves very
differently depending on which of the two repos it's paired with, and a user
who reasonably reaches for the model's own repo id gets a narrower, less
predictable set of working dtypes than one pointed at the mirror — a
difference that has nothing to do with the model itself.

None of these three are hard to handle. They just aren't handled by changing
one string. `config.embeddingModel` (parsed from `ZOTEUS_EMBEDDING_MODEL`,
`config.ts:329`) is already threaded to the API providers' options object, but
never reaches `LocalEmbeddingProvider`: `createEmbeddingProvider()`
constructs it with `new LocalEmbeddingProvider(undefined, undefined, {...})`,
model always `undefined`, always falling through to the constructor's own
`'Xenova/all-MiniLM-L6-v2'` default (`embeddings.ts:186`, `:394`). So today,
setting `ZOTEUS_EMBEDDING_MODEL` with `ZOTEUS_EMBEDDINGS=local` is silently a
no-op for the local provider — narrower than "add a passthrough," but the
actual gap.

## What a vector-affecting model record needs

`embedderIdentity()` (`embeddings.ts:29`) already does the right thing at the
level it operates on — it names the model in the persisted vector identity, so
the index refuses to rank stored vectors against a query embedded by a
different model. What it doesn't yet capture is that "different model" needs a
few more fields than a display string, if the goal is for two configurations
to be safely interchangeable:

- the HF repo that actually serves an addressable ONNX file (not necessarily
  the model's canonical repo, per the trap above), plus which dtype variants
  it serves
- pooling mode, and where it was read from (the model's own config, not
  assumed from a sibling model) — plus the normalize flag
- the input template, if any (`query: ` / `passage: ` for E5-style models,
  empty for most others — empty is a fact about the model, not an unset
  default)
- output dimension and a max sequence length, since a model's positional
  capacity and the length a driver should actually truncate to aren't always
  the same number
- the language set the model itself declares support for, if the goal is to
  let a German-speaking user pick correctly rather than by trial and error

A raw `<hf-id>` string can't carry any of that, which is why I'd suggest a
small **registry of complete, pinned records**, each carrying all of the
above, with `ZOTEUS_LOCAL_EMBEDDING_MODEL` (or `ZOTEUS_EMBEDDING_MODEL`,
already parsed) selecting a record by a short id, rather than naming an
arbitrary HF repo directly. An unrecognized id fails loudly before touching
the index, rather than resolving to something partially wrong. This costs a
small amount of flexibility (you can't try literally any HF model without a
code change) in exchange for every offered option being known to load, pool,
and normalize correctly — which for a local-first, no-telemetry tool matters
more than it would for something with usage data to catch regressions.

This shape already exists one layer down. Zotero's own `#6012` (still an open
PR at the time of writing, not yet merged) adds native ONNX inference in
Firefox's own ML runtime, in its own memory-gated process, and its
`Zotero.Embeddings` module owns a curated model registry with role-aware
`embedQuery()` / `embedPassages()` calls, rather than an open model string —
the same curated-registry, role-aware shape suggested above.

## Measured evidence, for whatever it's worth in picking the first entries

I benchmarked six multilingual ONNX candidates (all in the 384–768 dimension
range: `multilingual-e5-small`/`-base`, two IBM Granite multilingual sizes,
Snowflake `arctic-embed-m-v2`, and Alibaba `gte-multilingual-base`) against a
hand-built cross-lingual probe: 20 cross-lingual topics (8 Vietnamese, 8
German, 4 Russian — the Russian lane is thin and I'd weight it less), each
with an English query, a French query, and a native-language query, scored
for hit@10 against a fixed 257-passage pool.

The instructive part is the controls, not just the headline numbers. A query
topically unrelated to anything in the pool (four of them: e.g. Japanese
tea-ceremony ritual) should retrieve none of the non-English gold passages
into its top 10. That negative control came back clean at every quantization
level for the E5 family only (`multilingual-e5-small`, `multilingual-e5-base`).
The other four candidates leaked 1–4 of 4 negative probes at every dtype
measured, concentrated on a handful of "hub" passages that rank near the top
for unrelated queries regardless of topic — a known effect in
high-dimensional nearest-neighbor retrieval, not a probe artifact; an
English-only contrast model run through the identical harness leaked too. So
several of those models' raw hit@10 numbers look competitive or better, but
aren't trustworthy as clean cross-lingual signal without that caveat attached.

For what it's worth, `multilingual-e5-small`'s own hit@10 at fp32 (deployed
dtype, negative control clean): en→vi 0.62, fr→vi 0.25, en→de 0.50, fr→de
0.50, en→ru 0.75, fr→ru 0.75, and it stays close under 8-bit or uint8
quantization: every lane moves by 0.12 or less except fr→ru, which drops to
0.50 (the Russian lane is thin, n=4 topics, so its scores move in 0.25 steps
and carry less confidence than Vietnamese or German). `granite-97m`
does not degrade gracefully the same way: fp32 is respectable (0.62–1.00
across the same lanes), but 8-bit collapses on several lanes to 0.00–0.25.
That's worth flagging on its own, since int8/q8 is often assumed a safe
default speed/size tradeoff, and here it specifically isn't for that model.
`multilingual-e5-base` scores meaningfully higher than `-small` on every
clean lane at fp32 (e.g. en→vi 1.00 vs 0.62), though the gap narrows or
disappears under quantization (e.g. en→de ties at q8, fr→de inverts in
`-small`'s favor at uint8) — at roughly double the parameter count and vector
width, a real quality-vs-cost tradeoff, not a strict improvement.

On throughput: measured together on one CPU host (no GPU acceleration, single
runs rather than a dedicated throughput benchmark, so read these as
approximate), per-passage embedding time was `multilingual-e5-small` ≈60 ms,
`granite-97m-multilingual-r2` ≈70 ms, `multilingual-e5-base` ≈140 ms,
`gte-multilingual-base` ≈150 ms, `arctic-embed-m-v2` ≈170 ms,
`granite-311m-multilingual-r2` ≈230 ms. On an ordinary laptop CPU, an initial
build over a large library is roughly 2–4x longer for the four larger
candidates than for the two smaller ones. (A MiniLM figure of 77.6 ms/passage
exists too, but from a different host and a different measurement pass, so
it's only useful as an order-of-magnitude anchor, not a precise point of
comparison against the six above.)

Net: of the six, only the E5 family passed the negative control cleanly at
every quantization level I tested, and within that family `-small` is the
closer size match for the current MiniLM default (same 384 dimensions) and
the fastest of the six candidates benchmarked together, while `-base` trades
roughly 2x the build time and storage for a consistent quality gain at fp32.
I'm not suggesting a specific default, just flagging that these two are the
ones whose cross-lingual numbers I'd actually trust, and why the other four's
better-looking numbers come with an asterisk.

## A staging sketch, since the wiring isn't quite a one-line change

Given the hardcoded pooling/normalize/template point above, I'd split this
into stages rather than landing the config surface and the correctness fixes
in one change:

1. **No behavior change.** Move the current MiniLM configuration (repo,
   dtype, `pooling: 'mean'`, `normalize: true`, no template) into one declared
   record the code reads from, instead of literals split between the
   constructor default and the pipeline call. A vector-fingerprint test
   before/after proves this step changes nothing.
2. **Make every one of those fields actually drive construction and the
   vector fingerprint** — today pooling and normalize are hardcoded
   independent of which model is loaded, so simply making the model string
   configurable without this step reproduces the exact silent-degradation
   problem described above. A test that perturbs each field independently and
   observes either a construction change or a different fingerprint would
   catch a regression here.
3. **Add a small curated set of additional records** (not an open string) —
   each one pinned to a verified-addressable ONNX repo, correct pooling read
   from the model's own config, and its template, selectable by id via
   `ZOTEUS_EMBEDDING_MODEL`. An unrecognized id fails before touching the
   index.
4. **A small runtime check on first use of a newly selected record**: load,
   output shape, finite values, correct dimension, template applied, compared
   against a small set of published reference vectors by cosine distance, not
   by hash. A byte- or sign-bit hash of the embedding doesn't survive ordinary
   cross-provider floating-point noise (CPU vs. GPU, different BLAS) even for
   a correct, identical config, so an exact-match check will false-negative on
   working setups. This only works at full precision; nothing rescues the
   comparison once the model is 8-bit quantized. Cache the result against the
   entry id *and* the runtime shape that actually ran (transformers.js /
   onnxruntime version, OS/arch, and the resolved execution provider if one
   is ever added beyond CPU), not only against the configured model id. That
   way a runtime upgrade forces a fresh check on the next start, without
   re-running the full comparison on every identical restart. Independent of
   retrieval-quality benchmarking, to catch an ONNX file that resolves but
   misbehaves on the machine actually running it.

None of this needs new migration machinery: `embedderIdentity()` already
refuses to mix vector spaces across model changes and reports that a rebuild
is needed, which is exactly the mechanism a model swap should trigger.

One more axis, worth naming separately: per-library calibration. Everything
above is about whether an entry is wired correctly and produces the vectors
it should, a property of the model, portable across every install. Whether a
chosen model actually separates relevant from irrelevant results *on a given
library* is a different question, and Zotero's own `#6012` already answers it
under `Zotero.Embeddings.Calibration`: mean-center the vectors, take a noise
floor from the p99 of unrelated query/passage pairs, a ceiling from the
median of matched pairs, and reject a model whose matched-median doesn't
clear the floor. I'd keep this out of the registry record and the four stages
above. The numbers it produces are corpus-specific, so a threshold calibrated
on one library is the wrong threshold for another, the same way a hardcoded
stopword list is wrong for a corpus in a different language. It belongs as a
later step that runs against the user's own index, consuming the model's
registry entry as an input rather than being baked into it.

Happy to share the raw probe results (pool, queries, per-cell scores) if
useful — they're not attached here since this got long enough already.
