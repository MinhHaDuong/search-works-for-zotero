# Bench infra: upstream v1.9.0 → v1.10.0 semantic-query latency (issue #30)

Six drivers, meant to land in `bench/` of the tracking repo beside `mcp_drive.py`
(which `issue30_arms.py` imports by that name, unchanged). Every path is an
environment override with the 2026-08-29 run's value as its default, so nothing
here carries a scratch directory in its source:

| variable | meaning | default used on 2026-08-29 |
|---|---|---|
| `ISSUE30_ROOT` | holds `v190/dist`, `v1100/dist`, `embed/` (a bare npm project with `@huggingface/transformers`) | `~/.claude/jobs/upstream30-latency` |
| `ISSUE30_MASTER` | the one index both versions open | `…/zoteus-bench/issue30/master/search-index.sqlite` |
| `ISSUE30_SRC` | the PRE-RENAME index the passages come from (`--db`) | `…/zoteus-bench/vec-real/search-index.sqlite` |
| `ISSUE30_SLAB` | the raw float32 vector slab, in the source's row order (`--slab`) | `…/zoteus-bench/mrl/minilm384.f32` |
| `ISSUE30_ARMS_DIR` | where the per-arm **copies** are made | `…/zoteus-bench/issue30` |
| `ISSUE30_TRANSFORMERS` | directory `ZOTEUS_TRANSFORMERS_PATH` points at | `$ISSUE30_ROOT/embed` | <!-- model-id-literal: a filesystem path, not a model -->

## The drivers, in the order they run

1. **`issue30_slab_provenance.mjs`** — the control that had to fire before anything
   else. Re-embeds five sampled passages of `vec-real/passages.txt` through
   `Xenova/all-MiniLM-L6-v2` (the model zoteus's own `LocalEmbeddingProvider` <!-- model-id-literal: documentation -->
   loads) and reports cosine against the stored row of `mrl/minilm384.f32`. All
   five read 1.000000, which is what licenses calling the vectors real and the
   query space the same space. Without it the slab's model was an assumption.

2. **`issue30_build_index.mjs`** — builds a v1.9.0-schema index from real passages
   and real vectors already on disk. It writes no SQL of its own: rows go in
   through upstream v1.9.0's `SqliteSearchIndex` (`putItem` / `putPassage` /
   `putVector` / `save`), so the schema, the FTS5 external-content protocol and
   the meta keys are exactly what a real build writes. `protected` is
   compile-time only in TypeScript, which is what makes this possible from JS.
   20 s for 93 022 passages. Its source index (`--db`) is of the PRE-RENAME
   generation and is asserted to be, before the dist is loaded — see
   `bench/index_schema.mjs` and ticket 0101. The source and the vector slab are
   flags rather than the absolute paths this used to hardcode.

3. **`issue30_arms.py`** — the measurement. Three arms (v1.9.0, v1.10.0 with
   `ZOTEUS_INDEX_ANN=false`, v1.10.0 stock), each on its own **copy** of the
   master, interleaved query by query, one cold pass reported apart from five
   warm ones, and `zotero_index action:"status"` read after **every** query so
   `vectorScan` is recorded per sample rather than assumed.
   `--mode semantic|auto`, `--repeat N`, `--out`.

4. **`issue30_codebuild_agreement.py`** — the two things the arm table cannot say.
   (a) the code build isolated from v1.10.0's model download, by measuring the
   same first query twice: on a fresh index, then after a restart on the file
   that now carries the codes; (b) whether the fast answer is the same answer —
   top-10 item lists, v1.9.0 exact against v1.10.0 two-stage.

5. **`issue30_embed_cost.mjs`** — the fixed floor under every arm: what embedding
   the query string costs, through upstream's own `LocalEmbeddingProvider`, on
   the same twenty queries. At a two-stage p50 of 21,7 ms it is a quarter of the
   whole query, so it is the reason the arm ratios understate the scan's gain.

6. **`issue30_assemble.py`** — folds the three result files into the artifact.

## Reproducing

```bash
export ISSUE30_ROOT=…                                    # checkouts
node issue30_slab_provenance.mjs                         # control first
node issue30_build_index.mjs --db "$ISSUE30_SRC" --slab "$ISSUE30_SLAB" \
  --output "$ISSUE30_MASTER" --dist "$ISSUE30_ROOT/v190/dist"
python3 issue30_arms.py --mode semantic --repeat 5 --out results-semantic.json
python3 issue30_arms.py --mode auto     --repeat 5 --out results-auto.json
python3 issue30_codebuild_agreement.py --out results-codebuild-agreement.json
node issue30_embed_cost.mjs "$ISSUE30_ROOT/v1100/dist" bench/queries-x2.txt "$ISSUE30_TRANSFORMERS"
python3 issue30_assemble.py
```

## Substrate this depends on, and its one weakness

`vec-real/search-index.sqlite` (93 022 real passages, 2 100 items) and
`mrl/minilm384.f32` (93 022 × 384 float32). Both are on doudou and neither is in
the repo. The weakness is width and count, not realism: issue #30 was reported at
255 703 × 3 072, which is 3,1 GB of vectors read per query against our 143 MB.
Growing this substrate needs the rest of the library embedded with
`all-MiniLM-L6-v2` — 477 512 passages exist in `x2-rebuild`, but doudou has no
GPU and no torch, so that is a CPU-hours job, not a same-session one.
