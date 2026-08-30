# The GPU throughput anomaly: a missing `--device` flag, not a device fallback

Evidence for ticket 0481. Ticket 0264 found two jointly-suspicious observations on the GPU
arm: every candidate's sustained embedding throughput was 58–256 ms/passage — one to two
orders of magnitude slower than the superseded PyTorch projections, and dtype-independent
(fp32 as slow as q8) — and X8 found the CPU arm's (0263) and GPU arm's (0264) fidelity
vectors byte-identical at every shared rung. Neither had a cause. This report names one.

Host: padme, same GPU/driver/cuDNN/engine versions as 0264 (`CUDA_VISIBLE_DEVICES=0`,
RTX A4000, driver 580.159.04, CUDA 12.8, cuDNN 9.25.1.1 user-local, `@huggingface/transformers`
4.2.0 / `onnxruntime-node` 1.24.3). `padme`'s manual `llama-server` process (pid 63671, ~14 GiB
on the A4000) was stopped before any measurement (`kill -TERM`, GPU confirmed quiet at
89/2 MiB) and restarted afterward with the exact `ExecStart` line from
`/etc/systemd/system/llama-server.service`, run manually as the user — the same procedure
0264 used, still not under systemd supervision.

## The mechanism

`bench/sweep.py`'s `RealExecutor._measure_cost` builds its `query_embed_cost.mjs` subprocess
command with:

```python
if device != "(runtime default)":
    cmd += ["--device", device]
```

`_measure_fidelity` and `_measure_recall` — the two methods behind every `quant_fidelity.mjs`
invocation, which is what produced every fidelity/recall figure in 0264, including the
sustained-throughput `ms_per_passage` numbers that fed the R30 anomaly and the vectors X8
scored — had **no such line at all**, on either branch, until this ticket's fix. The `device`
plan parameter was accepted and echoed into `MeasureResult.device_selected` for bookkeeping,
but never reached the subprocess command line.

`quant_fidelity.mjs` passes `pipelineOpts.device` straight through to
`@huggingface/transformers`'s `pipeline()`. When that option is `undefined` (no `--device`
flag), `session.js`'s `getSession` calls `selectDevice(undefined, ...)`
(`src/utils/devices.js`):

```js
const DEFAULT_DEVICE = apis.IS_NODE_ENV ? 'cpu' : 'wasm';
...
export function selectDevice(deviceConfig, fileName, { warn } = {}) {
    if (!deviceConfig) return DEFAULT_DEVICE;
    ...
```

On Node, the default is `'cpu'`. So every fidelity/recall cell in the 0264 campaign — labelled
`auto` or `cuda` in its result filename purely as sweep-plan bookkeeping — silently ran on
CPU, regardless of what device the plan requested.

## Confirmed directly from the original campaign's own artifacts

Every per-rung vector metadata file the 0264 campaign persisted
(`/home/haduong/data/0264-vectors/*.json` on padme, `quant_fidelity.mjs`'s own output,
`device: opt.device ?? '(runtime default)'`) records the literal string:

```json
{ "model": "Xenova/multilingual-e5-small", "dtype": "fp32", "device": "(runtime default)", ... "ms_per_passage": 59.32 }
```

for all three rungs measured (fp32 59.32, q8 60.74, uint8 57.63 ms/passage) — this is the
driver's own honest record that no device was requested, not an inference.

## This explains both observations in one stroke

1. **The throughput anomaly.** Every fidelity `ms_per_passage` figure in 0264 is a CPU rate
   on padme's CPU, not a GPU rate. With `--device` correctly forwarded, the identical
   (model, dtype, rows, batch) on the identical host is far faster (below).
2. **The byte-identity.** X8 found the CPU arm (0263) and "GPU arm" (0264) fidelity vectors
   byte-identical because both arms computed on CPU, through the identical code path — not
   because of any cross-provider floating-point invariance. Section "Byte-identity
   discrimination" below is the direct contrast: a run that genuinely executes on CUDA does
   **not** reproduce the CPU vector byte-for-byte.

VRAM starvation is not an alternative explanation: `llama-server` was stopped before any
0264 cell ran and restarted only after the last one, with the GPU confirmed quiet throughout
(0264's own log). The missing flag is the whole explanation.

## Positive control

`nvidia-smi dmon -s u` sampled at 1 Hz across a real `llama-server` `/completion` call
(`n_predict=300`), before stopping the process for the rest of this session:

```
sm%   0  0 42 39 46 51 56 53 44 32 42 37 31  0
```

Idle at 0%, rising to 31–57% during generation, back to 0% after. The instrumentation
discriminates busy from idle. Raw log: `bench/results/0481-gpu-anomaly/dmon/dmon_control_busy.txt`.

## GPU utilization during an embed run

Two embed runs, `--device` forwarded explicitly (the corrected code path, via
`verification/probes/gpu_anomaly_embed_probe.mjs`), sampled with `nvidia-smi dmon -s um`
throughout:

- `granite-97m-multilingual-r2`, `device:cuda`, q8, batch 8: sm% 21–29%, framebuffer memory
  rising to 2 329 MiB, for the ~17 s duration of the call. Idle (89 MiB, 0%) before and after.
- `multilingual-e5-small`, `device:auto`, q8, batch 8: sm% 3–25% (noisier, lower peak),
  framebuffer rising to 793 MiB, for the ~16 s duration.

Both genuinely busy — GPU utilization measured, not inferred from provider assignment.
Raw logs: `bench/results/0481-gpu-anomaly/dmon/dmon_embed_granite_cuda.txt`,
`.../dmon_embed_e5small_auto.txt`.

## ORT profiling: where the milliseconds go

Session profiling enabled (`session_options: { enableProfiling: true, profileFilePrefix:
'ort-profile' }`), one run each, `multilingual-e5-small`, `device:cuda`, 80 rows, batch 8:

**q8** — total node time 2 570.6 ms: 1 927.0 ms (75%) on `CPUExecutionProvider`, 643.6 ms
(25%) on `CUDAExecutionProvider`. The dominant op is `MatMulInteger` at 1 773.4 ms (69% of
node time), entirely on CPU — CUDA registers no int8 matmul kernel for this op (confirming
`DEVICE-AUTO-0264.md` Result 1's independent finding: "CUDA kernel not found in registries
for Op type: MatMulInteger"). `CUDAExecutionProvider` handles far more nodes (6 640 vs 1 220)
but a small fraction of the time — many cheap ops, one expensive CPU-bound one.

**fp32** — total node time 145.2 ms: 145.1 ms (99.9%) on `CUDAExecutionProvider`, 0.17 ms on
CPU. No quantization ops exist at this rung, so nothing forces a CPU fallback; the kernel
time itself is small.

Summaries: `bench/results/0481-gpu-anomaly/step3_profile_summary.json` (q8),
`step3_profile_summary_fp32.json` (fp32).

## Batch-size sweep

`multilingual-e5-small`, `device:cuda` explicit, 128 rows, same passages across batch sizes:

| batch | q8 ms/passage | fp32 ms/passage |
|---:|---:|---:|
| 1 | 53.31 | 23.33 |
| 8 | 51.92 | 22.20 |
| 32 | 57.28 | 23.22 |
| 128 | 65.73 | 25.00 |

Flat across batch 1–128 for both dtypes, once `--device` is correctly forwarded. Batch-1
per-call overhead — the ticket's own "boring candidate" — is not the mechanism: it was never
tested against genuine GPU execution before, only against the CPU-default path, where it
would have looked the same for the wrong reason. fp32 is consistently ~2.3× faster than q8
on this host, the direct consequence of q8's CPU-bound `MatMulInteger`.

## Byte-identity discrimination

Same 20-row stride sample (corpus sha256 `949d5af1…eec0ca4`, verified identical on both
machines), embedded with `multilingual-e5-small`/fp32:

- **Locally, on doudou** (no GPU present), `device:cpu` explicit: first vector head
  `[0.24527722597122192, -0.025651840493083, -0.3844181001186371, ...]`.
- **On padme**, `device:cuda` explicit, with profiling: first vector head
  `[0.245431050658226, -0.02558455802500248, -0.3843628466129303, ...]`.

The padme run's profile confirms it genuinely executed on CUDA: 106.13 of 106.19 ms total
node time (99.9%) on `CUDAExecutionProvider`. The two vectors are **not** byte-identical —
they diverge from the fourth significant digit onward. Cosine over the compared dimensions:
0.9999999283; max absolute difference: 1.78×10⁻⁴. This is the expected signature of a
genuine cross-provider floating-point computation (different reduction order / FMA usage),
and it is the direct contrast case for 0264's X8 verdict: a run that actually uses the GPU
does not reproduce the CPU vector exactly, unlike every fidelity cell in the 0264 campaign.

## The harness fix

`bench/sweep.py`: `_measure_fidelity` (both the fp32 reference-rung call and the dtype-rung
call) and `_measure_recall` now forward `--device` when the plan's device is not
`"(runtime default)"`, mirroring `_measure_cost`'s existing, always-correct behaviour.
Regression test `tests/test_sweep_real_executor_device.py` — command-list construction only,
no model download or ONNX load, consistent with `RealExecutor`'s stated test-exemption
rationale. Verified red against the unfixed code (two of six cases failed, exactly the two
this fix addresses) before being verified green against the fix — the positive-control
discipline this ticket itself asks for, applied to the harness bug as well as the GPU
measurement.

## What this settles, and what it does not

It settles the mechanism behind both of 0264's anomalous observations as one bug, confirmed
both by direct reproduction and by the original campaign's own surviving artifacts. It does
not re-run the six-candidate × four-dtype fidelity/recall campaign under the corrected
harness — that is ticket 0267's work, blocked on this one, and it should not trust any
`bench/results/0264-gpu-arm/*fidelity*` or `*recall*` `ms_per_passage` figure as a GPU number
before doing so. The cost cells (batch-1 query latency) were never in question — `_measure_cost`
always forwarded `--device` correctly.
