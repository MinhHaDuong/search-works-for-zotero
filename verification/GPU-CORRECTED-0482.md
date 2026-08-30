<!-- last-reviewed: 2026-08-30 -->
# The GPU-corrected fidelity, X8, and throughput campaign

Evidence for ticket 0482, spending ticket 0481's fix (`bench/sweep.py` now forwards
`--device` to `quant_fidelity.mjs`). Same host, same corpus, same probes as 0264:
padme, `CUDA_VISIBLE_DEVICES=0` (RTX A4000 pinned, RTX 3060 present but unused), driver
580.159.04, CUDA 12.8, cuDNN 9.25.1.1 user-local, `@huggingface/transformers` 4.2.0 /
`onnxruntime-node` 1.24.3 / `onnxruntime-web` 1.26.0-dev.20260416-b7804b056c /
`onnxruntime-common` 1.24.3. Repo at commit `604635d` (origin/main, includes PR #102's
device fix and PR #103's 0481 housekeeping) pulled onto padme's existing clone before this
campaign. Corpus hash-verified identical to the CPU arm's: sha256
`949d5af1…eec0ca4`, 93 022 lines, `~/data/zoteus-bench/vec-real/passages.txt` on padme.

`padme`'s manual `llama-server` process (pid 76589, ~14 + 11 GiB across both GPUs) was
stopped before any measurement (`kill -TERM`, GPU confirmed quiet at 89/2 MiB on the A4000,
2 MiB on the 3060) and restarted afterward with the exact `ExecStart` line from
`/etc/systemd/system/llama-server.service`, run manually as the user — the same procedure
0264 and 0481 used, still not under systemd supervision. Post-restart: healthy
(`{"status":"ok"}`), GPU memory back to 14171 + 11456 MiB, matching its pre-campaign
footprint.

## Deviation from the ticket's device-per-model split, stated

0481 found that `auto` reliably crashes both granite candidates (a mixed CUDA/WebGPU
partitioning bug, ticket 0264) while genuinely selecting CUDA for other candidates under
`auto` too. Rather than split the campaign into an `auto` pass for four candidates and a
`cuda` pass for two, this campaign used **explicit `cuda` for all six candidates**,
uniformly. Reasoning: 0481 already showed explicit `cuda` produces genuine GPU execution
for every candidate it tried (granite via `cuda`, e5-small via `auto` — both busy per
`nvidia-smi dmon`), `cuda` is unambiguous evidence for the per-cell device-assertion this
ticket requires, and a single device value removes any risk of the WebGPU-partitioning
crash contaminating a chunked, resumable campaign. Every cell's `device_requested` and
`device_selected` fields, and every persisted vector's `device` field, read `cuda` — none
read `(runtime default)` (checked mechanically over all 24 result cells and all 18
measured vector-metadata files before scoring).

`resolve()`'s fp16-loadability probe was run with `--probe-device cuda` (not the default
`cpu`) so the probe reflects the device actually requested — the first run of this
campaign used the CLI default and was discarded and re-run before any other cell, because
a CPU-probed fp16 unloadable verdict would have been exactly the kind of device-mislabeled
result this ticket exists to eliminate.

## Fidelity cells: fp32/q8/uint8 measured for all 6 candidates; fp16 attempted for all 6

24 cells planned (6 candidates × 4 dtypes), device `cuda`: 18 measured, 6 unloadable, 0
failed. Full table: `bench/results/0482-gpu-corrected/SUMMARY.json`.

| model | fp32 ms/passage | q8 ms/passage | uint8 ms/passage | fp16 |
|---|---:|---:|---:|---|
| granite-97m-multilingual-r2 | 6,57 | 54,14 | 53,67 | unloadable — deterministic type-mismatch (below) |
| granite-311m-multilingual-r2 | 17,30 | 188,68 | 178,92 | unloadable — deterministic type-mismatch (below) |
| arctic-embed-m-v2 | 11,29 | 159,24 | 155,74 | unloadable — session-init failure |
| gte-multilingual-base | 11,11 | 156,27 | 153,24 | unloadable — session-init failure |
| multilingual-e5-small | 22,27 | 51,62 | 51,79 | unloadable — session-init failure |
| multilingual-e5-base | 13,14 | 117,45 | 115,39 | unloadable — session-init failure |

**fp16 reliability, per 0264/0240's known cases, reproduced.** Both granite candidates
fail with the exact same device-independent signature 0264 first recorded (a genuine
type mismatch in the exported graph: `Type (tensor(float16)) of output arg
(.../rotary_emb/Cast_1_output_0) ... does not match expected type (tensor(float))`) — a
real bug in the fp16 export, unrelated to device. The other four fail with the
CPU-provider session-init signature (`SimplifiedLayerNormFusion`/`InsertedPrecisionFree
Cast_`) that 0264 found to be *nondeterministic* on this host under a GPU-bearing device
(same bytes, same device, sometimes loads). `multilingual-e5-small`'s fp16 cell was
attempted twice under `--probe-device cuda` (once after discarding the CPU-probed run) —
both attempts failed at the identical signature; not retried further, consistent with
"a failed load is a recorded result" and the tracker's own established nondeterminism.

**Cross-check against the CPU arm's own fp32-vs-quantized fidelity.** `granite-97m`'s q8
cell here scores cos_mean 0,74296 against its own fp32 reference (not X8 — this is the
in-arm quantization-fidelity control) — a strikingly low number, but it is not a device
artifact: 0263's CPU-arm cell for the same (model, rung) records 0,743121, effectively
identical. This candidate's q8 rung genuinely loses fidelity against fp32 on both
providers; uint8 recovers most of it (0,947308 here, 0,948132 on the CPU arm).

## X8: cross-provider fidelity, full coverage, genuine this time

`verification/probes/x8_cross_provider_fidelity.py` (this ticket added a refusal check:
a GPU-side vector recording no resolved device is not scored — none triggered it here,
every one of the 18 pairs below is on genuine `cuda` vectors) scored against 0263's CPU
vectors, same (model, rung), same 600 rows:

| model | rung | cos_mean | clears 0,999 bar |
|---|---|---:|---|
| arctic-embed-m-v2 | fp32 | 1,000000 | yes |
| arctic-embed-m-v2 | q8 | 0,984295 | **no** |
| arctic-embed-m-v2 | uint8 | 0,984262 | **no** |
| granite-311m-multilingual-r2 | fp32 | 1,000000 | yes |
| granite-311m-multilingual-r2 | q8 | 0,998141 | **no** |
| granite-311m-multilingual-r2 | uint8 | 0,998166 | **no** |
| granite-97m-multilingual-r2 | fp32 | 1,000000 | yes |
| granite-97m-multilingual-r2 | q8 | 0,999680 | yes |
| granite-97m-multilingual-r2 | uint8 | 0,976706 | **no** |
| gte-multilingual-base | fp32 | 1,000000 | yes |
| gte-multilingual-base | q8 | 0,985395 | **no** |
| gte-multilingual-base | uint8 | 0,985465 | **no** |
| multilingual-e5-base | fp32 | 0,999994 | yes |
| multilingual-e5-base | q8 | 0,970582 | **no** |
| multilingual-e5-base | uint8 | 0,971993 | **no** |
| multilingual-e5-small | fp32 | 1,000000 | yes |
| multilingual-e5-small | q8 | 0,998178 | **no** |
| multilingual-e5-small | uint8 | 0,998166 | **no** |

**7 of 18 clear the bar — every fp32 cell, plus one 8-bit exception
(granite-97m/q8).** This reverses 0264's original "18/18 all-clear" verdict, which was an
artifact of both arms silently running on CPU (`verification/GPU-ANOMALY-0481.md`). With
genuine cross-provider vectors: fp32 stays provider-free by DESIGN §3's rule for every
candidate, but the two 8-bit rungs — the deployable ones on cost grounds — mostly do NOT
clear the bar. Per DESIGN §3 and DECISIONS.md's "the ruling waits for X8 — if X8 fails the
bar, the question answers itself": the adopt-a-foreign-index path (embed on padme, query
on doudou) is evidenced-open only for an fp32-embedded corpus; at q8/uint8 the execution
provider would need to enter the embedder key, or the copy path stays unsupported for
those rungs. This is evidence for the author's ratification, not a ruling made here.

granite-97m/q8's exception is notable, not an error: its cross-provider agreement is high
even though its OWN in-arm fp32-vs-q8 fidelity is poor (0,743, above) — quantization
appears to execute near-identically across providers for this model/rung, while the
*information lost to quantization itself* is large and provider-independent. The two
questions (does quantization on this rung agree across providers? does this rung retain
fidelity against fp32?) are separate axes, and this candidate answers them oppositely.

## Deployable-rung throughput: fp32 vs the better 8-bit rung, repeated

Fresh-process repeats (n=3 unless noted), 600 rows, batch 8, device `cuda`, median +
spread (max − min). Scratch-measured (`bench/measure_throughput_reps.py`), never
overwriting the X8 vectors. Full data: `bench/results/0482-gpu-corrected/throughput/`.

| model | rung | median ms/passage | spread | projected minutes (93 022 rows) |
|---|---|---:|---:|---:|
| granite-97m-multilingual-r2 | fp32 | 6,55 | 0,03 | 10,2 |
| granite-97m-multilingual-r2 | uint8 | 53,16 | 6,14 | 82,4 |
| granite-311m-multilingual-r2 | fp32 | 17,33 | 0,17 | 26,9 |
| granite-311m-multilingual-r2 | uint8 | 186,34 | 14,44 | 288,9 |
| arctic-embed-m-v2 | fp32 | 11,20 | 0,29 | 17,4 |
| arctic-embed-m-v2 | uint8 | 141,33 | 42,82 | 219,1 |
| gte-multilingual-base | fp32 | 11,20 | 0,05 | 17,4 |
| gte-multilingual-base | uint8 | 155,50 | 5,44 | 241,1 |
| multilingual-e5-base | fp32 | 13,24 | 0,22 | 20,5 |
| multilingual-e5-base | uint8 | 113,10 | 1,75 | 175,3 |
| multilingual-e5-small | fp32 | 21,65 | 0,22 | 33,6 |
| multilingual-e5-small | q8 | 52,68 | 0,35 | 81,7 |
| multilingual-e5-small | uint8 | 51,69 | 0,77 | 80,1 |

**fp32 is faster than the 8-bit rungs for every one of the 6 candidates**, confirming
0481's single-candidate finding generalizes: the quantized `MatMulInteger` op has no CUDA
kernel on this stack and falls back to CPU, so fp32 (no quantization ops at all) wins.
The margin varies widely by candidate: 2,4× for multilingual-e5-small, 8–14× for the
other five.

**"The better 8-bit rung" — uint8, for every candidate including e5-small, decided by
the repeats.** `bench/summarize_0482.py`'s single-sample comparison (from the main
fidelity sweep, one rep) called multilingual-e5-small's rung as q8 (51,62 vs 51,79
ms/passage) — the wrong answer at that margin. The 3-rep measurement resolves it cleanly:
q8's three reps (52,47/52,82/52,68) and uint8's (51,07/51,84/51,69) do not overlap, uint8
median 51,69 < q8 median 52,68. A single-sample comparison is not reliable at a ~2 %
margin; this is exactly why the ticket asked for repeats.

**Spread varies by an order of magnitude across candidates** — from 0,03 ms
(granite-97m/fp32, essentially noiseless) to 42,82 ms (arctic-embed-m-v2/uint8, ~30 % of
its own median). No host-side cause was isolated (concurrent sessions on padme are
possible during a multi-hour campaign); reported as observed, not attributed.

## Batch-size spot-check: does 0481's flatness generalize?

0481 found multilingual-e5-small's per-passage rate flat across batch 1–128 (both q8 and
fp32). Spot-checked on a different candidate, granite-97m-multilingual-r2/uint8/cuda,
128 rows:

| batch | ms/passage |
|---:|---:|
| 1 | 39,29 |
| 8 | 53,16 (median of the deployable-rung repeats table, above) |
| 32 | 82,56 |
| 128 | 91,90 |

**Does not generalize.** granite-97m's per-passage rate roughly doubles from batch 1 to
batch 128 (39,29 → 91,90 ms), a genuine batch-size sensitivity 0481's own candidate did
not show. Batch-8 remains the figure this campaign and 0481 both report (matching
`quant_fidelity.mjs`'s own default and DESIGN's deployed batch), but the flat-across-batch
property is model-specific, not a stack-wide fact — a caution for anyone tempted to read
0481's single-candidate flatness as general.

## What this settles, and what it does not

It settles the GPU-corrected fidelity, X8, and deployable-rung throughput figures for
every registry candidate, superseding `bench/results/0264-gpu-arm/`'s fidelity/recall/X8
figures (`bench/results/0264-gpu-arm/SUPERSEDED.md`). It does not pin R30's wall-clock
bound or rule on the adopt-a-foreign-index question — both wait on ticket 0267/the
author's ratification (DECISIONS.md), per `spec/README.md`'s R30 row. It does not measure
the `recall` kind (same-item retrieval) — out of this ticket's scope; 0264's cost table
(batch-1 query latency) is unaffected by the bug this ticket corrects and is not
re-measured here.
