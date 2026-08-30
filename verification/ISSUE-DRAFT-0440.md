# Draft of the upstream issue for ticket 0440 — NOT FILED

Status: awaiting the author's review; nothing is sent until he approves the
text below, as written. The figures are copies of values guarded in
`verification/EMBEDDER-RECOMMENDATION-0267.md` (figure guard key `v0267`);
they use decimal points because the draft is upstream text, sent as-is. The
links assume PR #110 (the recommendation report) has merged. Every code
claim was re-verified against the reviewed baseline `b132f2d` (v1.10.0) on
2026-08-30.

---

**Title: The local path cannot serve a non-English library — a curated model
registry, keyed by entry id**

## The defect

`ZOTEUS_EMBEDDING_MODEL` names the model of whichever *API* provider is
active. On the local path it never applies: `createEmbeddingProvider`'s
`case 'local'` constructs `LocalEmbeddingProvider(undefined, …)`, so the
constructor default `Xenova/all-MiniLM-L6-v2` always wins
(`src/features/search/embeddings.ts`, v1.10.0). That model is English-only —
Zotero core's own registry files it under "Models for testing". So a French,
German or Vietnamese library gets an English embedder on the only path that
keeps text local, and the sole recourse is sending the library to an API.

## Why the fix is one registry entry, not more env vars

Model choice cannot travel alone; we measured what each companion axis costs
when it is silently wrong:

- **dtype** resolves through the transformers.js filename convention, and
  some upstream repos publish nothing that convention can address except
  fp32 (`intfloat/multilingual-e5-small` is one).
- **pooling** is per-model: four of the six multilingual candidates we
  probed declare `cls` in their own `1_Pooling/config.json`, where the code
  hardcodes `pooling: 'mean'` at the extractor call — a mean-pooled cls
  model just scores worse, and it reads as a bad model rather than a bug.
- **input templates** are per-model: the e5 family without its
  `query: `/`passage: ` prefixes measures below an English model that needs
  none.
- **normalize** is per-model: several candidate pipelines carry a Normalize
  module and several do not.
- **precision has to be pinned per entry**: on our test library, one
  candidate's q8 rung drops task recall@30 from 0.9025 (its own fp32) to
  0.5895 — and once fused with BM25, below the 0.8092 keyword-only
  baseline, so the broken rung makes hybrid search worse than no vectors at
  all. Every other candidate is dtype-stable. No user can be expected to
  know which is which from a knob.

Zotero core converged on the same shape independently (zotero/zotero#6012):
`dtype`, `pooling`, `queryPrefix`, `passagePrefix` and `maxTokens` are
fields of a curated model entry, the preference names the entry, and no
per-axis knob is exposed anywhere.

## The ask

A small curated registry — each entry pinning
`{model id, revision, dtype, pooling, queryPrefix, passagePrefix, normalize,
maxTokens, languages}` — with the configuration surface being the entry id.
What it should not be is an untyped options bag: every field above degrades
retrieval silently when wrong.

Two measured facts may be worth reflecting in the entry design. The optimal
dtype differs by device — ONNX Runtime registers no CUDA kernel for the
quantized matmul, so fp32 is the fast rung on a GPU while 8-bit halves
resident memory on CPU. And an entry whose usable rung needs a GPU deserves
a label saying so.

## Evidence, if useful

We enumerated the open multilingual candidates with usable ONNX and measured
six of them under `@huggingface/transformers` 4.2.0 (CPU and CUDA arms:
cost, fidelity per dtype, task recall at each deployed dtype, cross-lingual
probes) on a real 93k-passage library. The registry format we used and the
full measurements are public:

- registry: `bench/models.json` in
  https://github.com/MinhHaDuong/search-works-for-zotero
- the measurement report:
  https://github.com/MinhHaDuong/search-works-for-zotero/blob/main/verification/EMBEDDER-RECOMMENDATION-0267.md

Happy to distill whichever table helps. Which entries to curate, and what
the default becomes, is of course your call.
