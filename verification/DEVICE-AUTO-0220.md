# `device: 'auto'` does not fall back — it fails

Evidence for ticket 0220. Settles one factual question: what happens when the local
embedder's pipeline is constructed with `device: 'auto'` on a machine with no GPU.

Artifacts: `bench/results/0220-device-dtype/` (per-variant JSON, `summary.json`,
`run.sh`). Probe: `verification/probes/device-auto-probe.mjs`.

## The question, and why it needed executing

Ticket 0220 ruled the device always `auto` and never configurable, on this ground:

> `auto` does not resolve to one device. It hands ONNX Runtime the whole ordered provider
> list and lets ORT's own execution-provider fallback walk it. That is why no escape hatch
> is needed for the ordinary failure — an absent or unusable provider is skipped by the
> runtime, not by our code.

The ticket also recorded, honestly, that every GPU claim in it was read from
`@huggingface/transformers`' `src/backends/onnx.js` rather than observed, this machine
having no GPU. What went unnoticed is that the *cheap half* was unobserved too. Whether
`auto` is safe where nothing but a CPU exists needs no GPU to answer, and it is the half
that governs the shipped default path for most users.

## Method

One process per variant: a failed session init leaves ORT state behind, so comparing
variants inside one process would let a failure contaminate the run after it. Each run
constructs the pipeline, embeds one sentence with `{pooling: 'mean', normalize: true}`,
and prints the vector. The vectors are L2-normalised, so a dot product between two runs is
their cosine.

The baseline is `no-options` — `pipeline('feature-extraction', model)` with no options
object at all, which is exactly what shipped. An absent flag produces an ABSENT key rather
than an undefined one: `{device: undefined}` is a third call shape that nobody ships, and
probing it would measure something no user can reach.

Measured on `@huggingface/transformers` 4.2.0, linux-x64, node v22.23.1, model
`Xenova/all-MiniLM-L6-v2`, against a clean `npm install` of that exact version in an empty
directory. No NVIDIA runtime is present on this machine. One further variant,
`skipinstall-device-auto`, uses a second clean install made with
`--onnxruntime-node-install=skip`; see Mechanism for what it settles.

## Result

| variant | options | outcome | cosine vs baseline |
|---|---|---|---|
| no-options | *(none)* | loads | 0,9999996 |
| device-cpu | `{device: 'cpu'}` | loads | 0,9999996 |
| device-auto | `{device: 'auto'}` | **throws** | — |
| device-auto-q8 | `{device: 'auto', dtype: 'q8'}` | **throws** | — |
| dtype-q8 | `{dtype: 'q8'}` | loads | 0,992652 |
| dtype-fp16 | `{dtype: 'fp16'}` | **throws** | — |
| dtype-q7 | `{dtype: 'q7'}` | loads | 0,9999996 |

The baseline scored against itself is 0,9999996 rather than 1, which is the float32
normalisation floor and therefore the resolution of this column. Two rows reproduce that
value exactly, meaning their vectors are identical bit for bit, not merely close.

`device: 'auto'` fails with:

```
OrtSessionOptionsAppendExecutionProvider_Cuda: Failed to load shared library
```

and, on stderr from the native binding:

```
Failed to load library .../onnxruntime-node/bin/napi-v6/linux/x64/libonnxruntime_providers_cuda.so
with error: libcublasLt.so.12: cannot open shared object file: No such file or directory
```

The control discriminates. `no-options` and `device-cpu` are the same call in every
respect but the option under test, and both load and serve. This is not a probe that could
only have come out one way.

## Mechanism

`supportedDevices` is built per platform in `src/backends/onnx.js`, and on linux-x64 it
begins with `cuda` — pushed on `process.platform` and `process.arch` alone, with nothing
consulted about whether CUDA is usable. `deviceToExecutionProviders('auto')` returns that
whole list. `createInferenceSession` then passes it straight to
`InferenceSession.create` with no try/catch and no per-provider loop.

So the fallback the ruling relied on is not in transformers.js. Whatever tolerance exists
belongs to ONNX Runtime, and ORT-node does not skip a listed provider whose shared library
will not load: it registers CUDA, the load of `libcublasLt.so.12` fails, and the session
fails with it.

**The failure does not depend on the CUDA binaries being there.** They are not in the npm
tarball — too large for the registry — but `onnxruntime-node`'s `postinstall` fetches them
by default on linux/x64, which is the only platform whose install manifest requires
anything (`cuda12`; every other platform's list is empty). A user opts out with
`npm install --onnxruntime-node-install=skip`, and the tempting inference is that such an
install has nothing to register and would therefore fall back cleanly.

It does not. Measured on a second clean install made with that flag, whose `bin/` holds
only `libonnxruntime.so.1` and the binding, `device: 'auto'` fails exactly as before —
`OrtSessionOptionsAppendExecutionProvider_Cuda: Failed to load shared library` — this time
because `libonnxruntime_providers_shared.so` is absent
(`skipinstall-device-auto.json`). Only the name of the missing library changes.

So on linux-x64 without a working CUDA runtime, `auto` fails whichever way the package was
installed. This is what an ordinary Linux desktop gets, not an exotic install, and the
315 MB download is a side issue rather than the cause.

The ticket anticipated this shape and set it aside: "ORT's fallback covers 'provider
unavailable'; it does not cover 'provider present, registers, and then misbehaves' — a
broken CUDA install. With no knob there is no manual override for that case. Do not add
one speculatively: if that failure is ever observed in the wild, it is the evidence that
earns the knob." That case is not the rare one. On linux-x64 the provider is always
*attempted*, whether or not its binaries were fetched, and the attempt is what fails. The
ordinary Linux desktop IS the failing case.

## Consequence for the ruling

Shipping `device: 'auto'` unconditionally would end semantic search for every Linux user
without a CUDA runtime, on the default local path, at the first embed. The ruling's
premise is void — not its intent, which was to reach CoreML on macOS and DirectML on
Windows for free, and which nothing here contradicts.

Three shapes remain, and the choice among them belongs to the author:

1. **Pass no device** (what the branch does). Behaviour-preserving everywhere; the
   runtime's Node default is already `['cpu']`. Costs the free accelerator on macOS and
   Windows.
2. **Pass `auto`, catch the failure, retry without it.** Recovers the intent and is
   testable. Costs every Linux user without CUDA a failed session init and a native ORT
   error splashed on stderr at each cold start — stderr being the log channel under stdio
   transport, that noise is user-visible, and it would likely be enough on its own to sink
   the change upstream.
3. **Pass `device: 'cpu'` explicitly.** Measured bit-identical to today, and it removes
   the "reached by omission" complaint that opens the ticket. Costs the ability of the
   runtime to ever improve its own default under us.

The branch takes 1 because it is the only one of the three that ships today without either
a measured regression or a decision the author has not made. A knob is still not proposed:
nothing here is evidence that the device should become configurable, only that `auto` is
not a safe unconditional value.

## What the knob buys on the model that actually ships

The ladder in ticket 0220 is nomic-768 and Qwen3-0.6B. Neither is the default, and the
default is a much smaller model, where a fixed overhead is a larger share of the total —
so the ladder's ratios cannot simply be carried across. Measured here on
`Xenova/all-MiniLM-L6-v2` (`minilm-fp32.json`, `minilm-q8.json`, same driver as the
ladder, 12 reps over 5 queries, one process each):

| | fp32 (default) | q8 |
|---|---|---|
| resident after load | 230,6 MB | 165,6 MB |
| resident added by the load | 143,7 MB | 69,1 MB |
| load | 415,2 ms | 191,1 ms |
| query median | 4,2 ms | 2,3 ms |

**Both runs are warm.** A first, cold pair read 170,5 MB against 104,3 MB of added
resident and 3 523,6 ms against 1 291,3 ms to load — those load figures are the download,
not the load, and the resident figures carry the download's buffers. The cold pair is
discarded rather than reported, which is the whole reason to name the warmth.

The direction matches the ladder and the magnitude does not: q8 halves the resident cost
of the load here (2,1x) where it cut nomic's by 3,8x. That is what a smaller model should
do, and it is the number a reader on the default path needs.

Latency is the one column to hold loosely. A single warm run of this driver moves by more
than the gap between some of these cells — the discarded cold pair put fp32 at 3,5 ms and
q8 at 3,3 ms, against 4,2 and 2,3 warm — so the honest reading is that q8 is not slower,
not that it is 1,8x faster. The memory column is large enough to survive that spread; the
latency column is not, and at batch 1 a 384-dimension encoder has little arithmetic left
to save.

## A second correction, smaller

Ticket 0220's verification list expects an invalid dtype to abort, and names `q7` as the
value that would prove the degradation path: "An invalid dtype (`ZOTEUS_EMBEDDING_DTYPE=q7`,
which exists in no runtime) warns and serves, rather than aborting."

`q7` does not abort. It loads, and its vectors are bit-identical to the default — the
runtime ignores an unrecognised value and serves full precision, with no error to catch
and no warning to emit. Written against `q7`, the degradation test would have passed
against an implementation that had no degradation path at all.

`fp16` is the value that actually throws, reproducing the graph-fusion failure the ticket
documents on other models, and it is what the shipped test uses.

**Why it is silent, read from the runtime rather than inferred from the one probe.**
`dtype` selects a filename suffix — `DEFAULT_DTYPE_SUFFIX_MAPPING` maps q8 to `_quantized`,
int8 to `_int8`, fp32 to the empty string — and `selectDtype` resolves the requested value
first. Its final branch is unconditional: a string that is not a key of `DATA_TYPES` falls
through to `DEFAULT_DEVICE_DTYPE_MAPPING[device] ?? fp32`, with no error and no return
value distinguishing it from an explicit request for the default. `session.js` does carry
`throw new Error('Invalid dtype: …')`, but it tests the value `selectDtype` already
returned, so a bad user string can never reach it — by then it has been coerced to a valid
one. And the function's `warn` callback fires for exactly one other case, a per-file dtype
*object* missing the current file; an unrecognised string never sets it.

So the absence of a warning is a property of the code, not of this machine or this probe,
and the documentation's "ignored silently, with no signal at all" is exact. It also means
no catch on our side could ever detect the case: there is nothing to catch.

The user-facing residue is that a typo in `ZOTEUS_EMBEDDING_DTYPE` is silent: the user
believes they are running quantised and are not. The branch does not add a local allowlist
to catch it — the ticket forbids one, rightly, since it would rot against the runtime's
enum and its failure mode is refusing a value that works. What it does instead is keep the
embedder identity truthful, so `zotero_index action:"status"` reports the precision
actually in use, and say plainly in the documentation that an unrecognised value is
ignored rather than implying a safety that is not there.

## A third correction, from review rather than measurement

Ticket 0220's action 5 says an unloadable dtype should "fall back to the runtime default
with a warning rather than taking the server down". That was implemented, and adversarial
review of the branch found it unsafe — not in the abstract, but through a call chain that
is easy to check and was not checked when it was written.

`SearchIndexBase.build` sets `vectorEmbedderId` from the provider's identity while the
records are still unembedded (`index-manager.ts:550`, and the incremental path at `:687`),
and the first `embed()` comes later (`:570`). A provider that downgraded its precision
inside that first load therefore stamped one identity and produced vectors of another. The
index ends up labelled with a precision its vectors do not have, and nothing downstream can
notice: quantisation leaves the vector width unchanged, so the dimension check on the query
path sees nothing wrong, and the identity string is the only defence there is.

Two consequences, and the second outlives the session. In-session, `updateBlocker` compares
the live identity against the stamped one, finds a mismatch, and refuses every incremental
update with a message that has the story backwards. Across sessions the mislabel is
persisted, so if that dtype ever does load later — a newer runtime, other hardware — the
stale label now *matches* a genuinely quantised identity, and the old default-precision
rows are ranked against new quantised queries with nothing objecting. The degradation
designed to protect the user was corrupting the one record that protects the index.

The fix removes the substitution rather than reordering around it: the precision is
constant for a provider's life, and a value that will not load throws. That is still a
degradation and not an abort — the throw reaches `noteEmbedFailure` like any other embedder
failure, so the index falls back to keyword-only and reports the value, the model and the
remedy, which is the path a missing `@huggingface/transformers` already takes. Action 5's
intent survives; its mechanism does not.

Confirmed by reinstating the downgrade behind a temporary flag: the new integration test
fails with `expected 1 to be +0`, that 1 being a vector written under a label the index
cannot honour. Without that control the test would have been an assertion nobody had seen
fail.

## Reproducing

```bash
PKG_ROOT=<dir whose node_modules has @huggingface/transformers> \
CACHE_DIR=<transformers.js cache> \
  bash bench/results/0220-device-dtype/run.sh
python3 bench/results/0220-device-dtype/summarize.py
```
