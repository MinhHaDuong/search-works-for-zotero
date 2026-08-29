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
directory. No NVIDIA runtime is present on this machine.

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
fails with it. `onnxruntime-node` bundles the CUDA provider binary on linux-x64
unconditionally, so this is not an exotic install — it is what a Linux user without an
NVIDIA driver gets from `npm install`.

The ticket anticipated this shape and set it aside: "ORT's fallback covers 'provider
unavailable'; it does not cover 'provider present, registers, and then misbehaves' — a
broken CUDA install. With no knob there is no manual override for that case. Do not add
one speculatively: if that failure is ever observed in the wild, it is the evidence that
earns the knob." That case is not the rare one. On linux-x64 the provider is always
present, because the package ships it, and it always registers. The ordinary Linux desktop
IS the failing case.

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

The user-facing residue is that a typo in `ZOTEUS_EMBEDDING_DTYPE` is silent: the user
believes they are running quantised and are not. The branch does not add a local allowlist
to catch it — the ticket forbids one, rightly, since it would rot against the runtime's
enum and its failure mode is refusing a value that works. What it does instead is keep the
embedder identity truthful, so `zotero_index action:"status"` reports the precision
actually in use, and say plainly in the documentation that an unrecognised value is
ignored rather than implying a safety that is not there.

## Reproducing

```bash
PKG_ROOT=<dir whose node_modules has @huggingface/transformers> \
CACHE_DIR=<transformers.js cache> \
  bash bench/results/0220-device-dtype/run.sh
python3 bench/results/0220-device-dtype/summarize.py
```
