# The embedder recommendation: evidence and a decision rule (ticket 0267)

Written 2026-08-30 for ticket 0240's tracker. This report recommends; it does
not set a default. Which entry ships is the maintainer's choice, and this
document exists to equip it: a decision rule stated in the open, the evidence
each clause rests on, and the named conditions that would overturn the
outcome. Where it touches the design it points at the owning document
(DESIGN.md for thresholds and rules, DECISIONS.md for rulings); this file is
evidence, not authority.

The evidence base is five measured campaigns on the author's real library and
machines: CPU cost and fidelity (ticket 0263, `bench/results/0263-cpu-arm/`),
the corrected GPU campaign (ticket 0482, `bench/results/0482-gpu-corrected/`,
superseding the device-mislabeled fidelity cells of
`bench/results/0264-gpu-arm/` — ticket 0481 carries the mechanism), recall at
the deployed dtype plus the fused delta (ticket 0265,
`bench/results/0265-recall-fusion/`), and the cross-lingual probe (ticket
0266, `bench/results/0266-cross-lingual/`). The earlier campaign in
`bench/results/0025-x1-recall/` benchmarked a candidate field R7 already
excludes — every model in it is English-only or English-centric — so its
recall column selects nothing here; its artifacts stay as a valid record of
an invalid field, and its dtype-ladder methodology is what the present
campaigns inherited.

## The decision rule

Applied in this order; each clause names its evidence.

1. **R7 is a filter, not a tiebreak.** Only models whose own declared language
   list covers French, German, Vietnamese, Greek and Russian were measured as
   candidates; English models appear only as labeled contrast cells. Checked
   mechanically against the registry (`bench/models.json`).
2. **Reliability at the deployed rung is a gate.** A (model, rung) pair whose
   deployed-rung retrieval collapses is excluded before any ranking. One pair
   fails it: granite-97m at q8, condemned three independent ways — the worst
   8-bit fidelity of the CPU campaign, a cross-lingual collapse to zero on
   two lanes, and task recall falling from 0,9025 at its own fp32 to 0,5895
   (against a keyword-alone baseline of 0,8092, so the broken rung is worse
   than having no vectors). uint8 partially recovers it (0,8644), which is
   why the model survives as a candidate while the pair does not.
3. **Rank on task recall at the rung that ships, not on fidelity to fp32.**
   Fidelity is a cheap second signal and a poor ranker: gte-multilingual-base
   holds mediocre fidelity yet ranks mid-field on recall, and the one genuine
   collapse (clause 2) is visible in both. The recall column is the deciding
   one.
4. **Control cleanliness ranks above raw recall where they conflict.** The
   cross-lingual probe's negative control — topically remote queries must not
   surface gold passages — is passed cleanly by the e5 family alone; every
   other candidate leaks into hub passages. A leaky model converts R18's
   honest "nothing matches" into confident noise, which is precision damage
   no recall number offsets. This clause is the one a reader is most likely
   to weigh differently, and the overturn conditions below say exactly what
   would relax it.
5. **Cross-lingual capability breaks ties.** R7 promises per-language lanes;
   ticket 0037 proposes the stronger cross-lingual property. Measured in
   ticket 0266 while the vectors existed.
6. **Memory and cost are reported, never ranked.** Ruled 2026-08-29
   (DECISIONS.md): R7 is hard and the memory ceiling gives way, so RSS
   informs C3's replacement value (ticket 0268) and ranks nothing here.

## The two shapes

The CPU and GPU arms are two shapes, not one table, and the difference is now
a measured fact rather than a presentation choice: **the optimal rung is
per-device.**

**CPU shape (doudou).** The deployed rung is 8-bit — it halves resident
memory (the cheapest candidate loads at 406,6 MB median; the recommended one
at 572,6 MB, both q8, five fresh processes each) and costs nothing
measurable in task recall outside clause 2's excluded pair. Which 8-bit
variant is better is per-model and must be measured, never assumed: the
uint8-over-q8 ordering that motivated sweeping both does **not** generalise —
granite-97m is the only candidate that reproduces it, in the extreme, and
every other candidate ties within noise or slightly favours q8. Quantization
robustness is therefore a real selection criterion, and it is exactly what
condemned granite-97m.

**GPU shape (padme, RTX A4000, CUDA 12.8).** Full precision is both the fast
rung and the safe one. The quantized matmul has no CUDA kernel and falls back
to CPU, so the 8-bit rungs run several times slower than fp32 there;
measured per candidate at fp32, batch 8, three fresh-process repetitions:

| model | ms/passage, fp32, cuda |
|---|---|
| granite-97m-multilingual-r2 | 6,55 |
| gte-multilingual-base | 11,2 |
| arctic-embed-m-v2 | 11,2 |
| multilingual-e5-base | 13,24 |
| granite-311m-multilingual-r2 | 17,33 |
| multilingual-e5-small | 21,65 |

At the recommended candidate's rate the full 93 022-passage corpus embeds in
20,5 minutes, which is what R30's wall-clock bound derives from once the
choice is ratified (the bound itself is DESIGN §2.8's, pinned there and not
here).

**Cross-provider compatibility (experiment X8, DESIGN §3).** At full
precision every candidate clears the 0,999 vector-compatibility bar against
the CPU arm's vectors; at the 8-bit rungs most do not (7 of 18 scored cells
clear; arctic's 8-bit rungs sit near 0,9843). Consequence: the
embed-on-GPU, retrieve-on-CPU path (the adopt-by-copy question awaiting
ratification in DECISIONS.md) is supported by this evidence at fp32 and not,
as the bar is written, at 8-bit. The bar is a field-borrowed proxy; whether a
0,98 cross-provider cosine moves task recall is a measurable question, and
answering it would be a child ticket, not an estimate here.

## Recall at the deployed dtype, and what fusion keeps

Task recall@30 on a seeded whole-item subsample of the real corpus
(1 533 passages, 33 items, 400 probes; keyword arm alone stands at 0,8092):

| model | fp32 | q8 | uint8 |
|---|---|---|---|
| granite-97m-multilingual-r2 | 0,9025 | 0,5895 | 0,8644 |
| granite-311m-multilingual-r2 | 0,9249 | 0,9208 | 0,9195 |
| arctic-embed-m-v2 | 0,9294 | 0,9278 | 0,9273 |
| gte-multilingual-base | 0,9158 | 0,9164 | 0,9123 |
| multilingual-e5-small | 0,9049 | 0,9058 | 0,9036 |
| multilingual-e5-base | 0,9093 | 0,896 | 0,9001 |

The fused arm — RRF over the keyword and vector lists, the surface a user
actually sees — was measured here for the first time. On average 0,7352 of
the vector arm's isolated gain survives fusion, confirming the tracker's
concern that a vector-arm improvement washes out against an unchanged
keyword arm. The sharpest fusion fact is negative: at the excluded
granite-97m/q8 pair the fused result lands -0,0638 *below* keyword-alone — a
broken embedder does not merely fail to help, it drags the whole search
under the no-vectors baseline. That is the strongest argument this study
produced for pinning the rung inside a curated entry rather than exposing
any knob.

## What the rule selects

Under the rule as ordered, **multilingual-e5-base** comes out best balanced:
clean negative controls (clause 4), the strongest caveat-free cross-lingual
lanes — en→vi hit@10 of 0,88 at q8, where the English contrast model scores
0,12 — recall within two points of the leader at every rung, stable across
dtypes, and cross-provider behaviour at fp32 that supports the adopt-by-copy
path. multilingual-e5-small is the same profile at lower cost and lower
cross-lingual scores — the right entry where memory matters more than lane
quality. **arctic-embed-m-v2** wins raw recall at every rung and is the pick
if clause 4 is priced differently — its leak is a hubness effect the probe
could not separate from the model's geometry, and the overturn conditions
below name the experiment that would settle it. granite-311m-multilingual-r2
ranks second on recall with the same caveat and roughly twice e5-base's
resident cost. granite-97m is the cheapest and fastest model in the field
and the rule excludes its q8 rung outright; shipping it means shipping
uint8, at the weakest healthy recall in the table.

One convergence worth naming without leaning on it: Zotero core's own
multilingual entry is multilingual-e5-small, the small sibling of the
selection here, with the same pooling, template and per-entry-pinned shape
this repo's registry uses.

## What would overturn this

Named, checkable conditions — not hedges:

- **The hubness discrimination.** A re-probe whose negative control varies
  the gold-pool composition (so a hub passage cannot absorb remote queries by
  construction) showing arctic's leak to be a probe artifact would promote
  arctic-embed-m-v2 to the rule's selection on clauses 3 and 5.
- **The golden gate at entry granularity** (R21, ticket 0029/0026) reversing
  the fused-arm ordering between e5-base and arctic on the pinned query set.
- **transformers.js#945 landing** (open at last check, unchanged since
  2024-09-26): CUDA-by-default with its claimed speedup changes what the
  default path means, and every CPU baseline here needs re-reading.
- **An 8-bit CUDA matmul kernel** appearing in ONNX Runtime: the per-device
  rung split collapses, and the GPU shape re-ranks on a rung that no longer
  exists as a penalty.
- **A task-metric check on the X8 bar** showing 0,98-class cross-provider
  cosine costs no recall: the adopt-by-copy path widens to the 8-bit rungs.
- **Zotero core shipping its model registry** with a different multilingual
  default: convergence with the platform is worth more than two points of
  recall on this corpus, and the comparison should be re-run on their entry.

## Provenance

Engine, identical across arms and recorded per result file:
`@huggingface/transformers` 4.2.0, `onnxruntime-node` 1.24.3,
`onnxruntime-web` 1.26.0-dev, `onnxruntime-common` 1.24.3; Node v22 on both
hosts. The runtime's own support matrix (`src/backends/onnx.js`) is the
authority on what each device can reach and is versioned — re-read it rather
than citing this report. Device handling per cell is recorded as resolved,
not requested, after ticket 0481 showed what the difference costs. Costs,
spreads, and the full per-cell record live in the four campaign directories
named above; every figure quoted here is declared in
`bench/check_figures.py` with an anchor.
