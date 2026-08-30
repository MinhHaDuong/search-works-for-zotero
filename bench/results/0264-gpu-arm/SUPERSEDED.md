<!-- last-reviewed: 2026-08-30 -->
# This directory's fidelity, recall, and X8 figures are superseded

Ticket 0481 found the mechanism: `bench/sweep.py`'s `_measure_fidelity`/`_measure_recall`
never forwarded `--device` to `quant_fidelity.mjs`, so every fidelity/recall cell in this
campaign silently ran on CPU regardless of the requested device (`auto`/`cuda`) — confirmed
directly from these cells' own vector metadata, which records `"device": "(runtime
default)"` for every rung. `verification/GPU-ANOMALY-0481.md` has the full mechanism.

Two consequences for anything read out of this directory:

- **Every `ms_per_passage` figure under a `*fidelity*` or `*recall*` filename here is a CPU
  rate**, not a GPU rate, despite the `cuda`/`auto` device label in the filename.
- **`x8-cross-provider-fidelity.json`'s "18/18 all-clear, cosine 1,000000" verdict reflects
  CPU-vs-CPU byte-identity**, not genuine cross-provider agreement — both arms ran the same
  code path.

The cost cells (`*fixed-queries-v1*`, batch-1 query latency) are unaffected —
`_measure_cost` always forwarded `--device` correctly, and this is confirmed by the
0264-gpu-arm cost table `granite`/`cuda` entries actually differing from a CPU rate.

Ticket 0482 re-ran the fidelity/recall campaign with the fix, on the same host, every
registry candidate, every loadable rung: `bench/results/0482-gpu-corrected/`. Its X8 verdict
differs sharply by rung — fp32 clears DESIGN §3's 0,999 bar for every candidate, but the
8-bit rungs (q8/uint8) mostly do not (see `bench/results/0482-gpu-corrected/SUMMARY.json` and
`verification/GPU-CORRECTED-0482.md`). Read the numbers there, not here.
