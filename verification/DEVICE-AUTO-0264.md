# `device: 'auto'` on a GPU host: it runs on the GPU, and it can crash

Evidence for ticket 0264, the GPU-side sequel to `verification/DEVICE-AUTO-0220.md`. That
report settled what `auto` does with no GPU present (fails outright on CUDA-provider-load
failure, on the ordinary Linux desktop). This settles the question ticket 0220 could not
even attempt: what `auto` does when a GPU genuinely is present. The claim that it selects a
GPU provider has been asserted from source since ticket 0220 and had never been executed
anywhere until this report.

Host: padme, Ubuntu 24.04.4, NVIDIA RTX A4000 16 GB (`CUDA_VISIBLE_DEVICES=0`) + RTX 3060
12 GB present and unused, driver 580.159.04, CUDA 12.8, cuDNN 9.25.1.1 (installed
user-locally for this report — absent by default, and the CUDA provider fails to load
without it: `libcudnn.so.9: cannot open shared object file`). Engine versions identical to
the CPU arm: `@huggingface/transformers` 4.2.0, `onnxruntime-node` 1.24.3,
`onnxruntime-web` 1.26.0-dev.20260416-b7804b056c, `onnxruntime-common` 1.24.3.

## Method

Same probe as 0220, `verification/probes/device-auto-probe.mjs`, one process per variant.
For the mechanism question — not merely success/failure but which execution provider a
node actually ran on — a second, one-off script (not committed; the public pipeline API
gives no provider introspection, `RealExecutor`'s own docstring in `bench/sweep.py` records
this limitation) set `env.logLevel = LogLevel.DEBUG` before constructing the pipeline and
captured ONNX Runtime's own verbose session-init and node-placement log.

## Result 1: `auto` genuinely runs on the GPU, with per-node CPU offload

`deviceToExecutionProviders('auto')` (`src/backends/onnx.js`) resolves on Linux x64 to
`['cuda', 'webgpu', 'cpu']` and hands that whole list to `InferenceSession.create`. For
`Xenova/all-MiniLM-L6-v2` at q8, ORT's verbose log shows:

```
Node(s) placed on [CPUExecutionProvider]. Number of nodes: 62
Node(s) placed on [CUDAExecutionProvider]. Number of nodes: 340
```

340 of 402 nodes ran on CUDA. The 62 CPU nodes are two ORT cost-heuristic placements
(`/embeddings/Gather`, `/embeddings/Unsqueeze` — "the CPU execution path is deemed faster
than overhead involved with execution on other EPs") plus every `DynamicQuantizeLinear` and
`MatMulInteger` node in the graph: q8's quantization ops, for which CUDA registers no
kernel ("CUDA kernel not found in registries for Op type: MatMulInteger", repeated per
layer). `WebGpuExecutionProvider` was registered and a Dawn device context was created
(hence the `maxDynamicUniformBuffersPerPipelineLayout` warning printed on every run in this
report, `auto` or not) but received zero node placements — present in the session, inert
for this model.

So the answer to the load-bearing question is not a single word. `auto` does select a GPU
provider, genuinely, for the majority of the graph; it also silently offloads a real
minority of nodes (here, the quantization ops a q8 model is full of) to CPU inside the same
session, and it always pays the cost of initializing a WebGPU context whether or not any
node ends up running there.

## Result 2: for some models, the mixed provider list crashes instead of degrading

`granite-97m-multilingual-r2` at fp32, `device: 'auto'`, reproducibly aborts mid-execution
(exit -6, `SIGABRT`, no output written):

```
Non-zero status code returned while running Sqrt node. Name:'/layers.0/attn/Sqrt'
Status Message: .../webgpu_context.cc:185 ... All inputs must be tensors on WebGPU buffers.
```

ORT's partitioner assigned this model's `Sqrt` node to `WebGpuExecutionProvider` while
feeding it a tensor that was still located on CPU — a genuine mixed-CUDA/WebGPU
partitioning bug in this ONNX Runtime build, not a graceful "provider unavailable, try the
next one" fallback. The same model with `device: 'cuda'` explicit (`deviceToExecutionProviders`
maps that to `['cuda']` alone, no WebGPU registered) loads and measures cleanly:

| | fp32, `device: 'cuda'` |
|---|---|
| load | 1 940,3 ms |
| RSS delta | 907,4 MB |
| query median (batch 1) | 3,3 ms |

So `auto`'s GPU-bearing provider list is real (Result 1) and its failure genuinely is
caught by ORT's own fallback machinery for the ordinary case of a provider being
unavailable (0220's finding, reconfirmed on this host for a missing CUDA library) — but for
at least one candidate in this study's field, the failure is a hard process crash from a
provider-placement bug, not a same-session fallback to the next provider in the list. This
matters directly for the device-shape ruling DECISIONS.md made on 2026-08-30: passing a
GPU-bearing list "with the failure caught" is necessary but the crash observed here is not
caught inside the process — it has to be caught by whatever calls the process, the same way
`bench/sweep.py`'s harness had to be fixed to do (below).

Which combinations crash under `auto` and which do not, across the full candidate field, is
the sweep in `bench/results/0264-gpu-arm/` — see that directory for the per-(model, dtype)
outcome, not this report, which exists to explain the mechanism once rather than restate
which cells hit it.

## Result 3: a second, unrelated crash — on exit, after the work is done

Independent of Result 2, this ORT/WebGPU-Dawn native binding on this host crashes the
Node process on exit (`SIGSEGV` or `SIGABRT`) after a run has already produced its full,
valid output. Confirmed both with `device: 'cuda'` alone (no WebGPU registered at all — so
this is not a WebGPU-specific defect) and with `device: 'auto'` on the working all-MiniLM
case. In every instance observed, the driver's own `writeFileSync` (or equivalent) had
already completed: the JSON on disk is complete and valid, only the process's own shutdown
sequence dies afterward — consistent with a native-binding teardown-order bug (one capture
showed `terminate called after throwing an instance of 'onnxruntime::OnnxRuntimeException'
... Attempt to use DefaultLogger but none has been registered`, the signature of a static
logger destroyed before something still using it during process exit).

**Consequence for the harness.** `bench/sweep.py`'s `RealExecutor` originally treated any
nonzero subprocess return code as a failed cell, and captured only the last 4 000 characters
of stderr for diagnosis. Both were wrong on this host: the first discarded good,
already-written measurements behind a crash that happens strictly after the work is done;
the second lost the actual diagnostic under noise for Result-2-style crashes, where the
real error line prints early and is followed by hundreds of routine per-op warning lines —
exactly what buried the "Sqrt node" message above on the first attempt at this campaign.
Fixed in this branch (`bench/sweep.py`, ticket 0264): `_measure_cost` and `_measure_fidelity`
now check the driver's own output file for validity *before* consulting the return code —
salvaging a Result-3 crash as a measured cell (annotated `process_exit_note`) while still
correctly reporting a Result-2 crash as failed, with head-and-tail stderr rather than
tail-only.

## Result 4: q4f16 and the WebGPU path, standalone

Probed on the idle RTX 3060, so as not to contend with the A4000 campaign. q4f16 — unlike
fp16, which fails outright on the CPU provider (0240's tracker) — loads and runs under
every GPU-bearing device value tried: `device: 'cuda'` explicit (load 7 127,3 ms, first
download) and `device: 'auto'` (load 874,7 ms, cached). Explicit `device: 'webgpu'` also
loads and runs cleanly (load 660,4 ms) for `Xenova/all-MiniLM-L6-v2` at q8. The WebGPU path
is therefore usable from Node on this host, standalone — Result 2's crash is a
mixed-provider partitioning defect for particular models, not evidence that WebGPU itself
is broken here.

## What this settles, and what it does not

It settles the load-bearing claim as an observation rather than a reading of source: `auto`
on a real GPU host runs the bulk of a graph on CUDA, offloads specific unsupported ops to
CPU inside the same session, always pays a WebGPU-context initialization cost, and — for at
least one architecture in this study's candidate field — can crash outright rather than
degrade. It does not settle which candidates are safe to ship under `auto` in production;
that is the per-cell sweep this report points at, not this report.
