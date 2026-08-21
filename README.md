# zoteus-fts5

Work tracking for a storage-layer prototype in [zoteus](https://github.com/oscardvs/zoteus),
an MCP server over a local Zotero library.

zoteus holds its search index resident in JS objects and snapshots it with one
`JSON.stringify`. On a 7 541-item library that costs gigabytes of RAM, fails to
serialise past V8's string limit, and cannot be reloaded by a stock Node. The
same corpus in SQLite/FTS5 serves from about 128 MiB of process memory and
reloads on a stock Node — which is the point. It does **not** build faster:
measured at the same chunk geometry, through the same Zotero API, the build
takes about as long either way, because it is bound by fetching from Zotero
rather than by indexing.

Measured over **one corpus of 360 811 passages read by both backends** — the
same crawl's `search-index.json`, migrated in place, rather than two crawls that
ought to agree: **5 759,6 MiB against 128,0 MiB** resident, and **90,87 s
against 3,86 s** to first answer.

Read `STATE.md` before quoting any of that. The memory figure excludes the
kernel page cache holding the database file, where the JS heap figure has no
such remainder; charge SQLite the whole file and the win is 6,8x rather than
45x. Both numbers are measured and both belong in any external claim.

- `tickets/` — the work, tracked with [git-erg](https://github.com/MinhHaDuong/git-erg)
- `bench/` — the measurement harness (below)
- `bench/results/` — committed raw artifacts behind the figures in `STATE.md`
- `fork/` — a checkout of the fork; git-ignored, cloned by hand

See `STATE.md` for current status and `tickets/0001-*` for the plan.

## Bench

Drivers take `--server` / `--data-dir` and record `VmHWM` (the kernel
high-water mark, which cannot miss a peak between samples) rather than sampled
RSS. None defaults `--node-options` to a heap flag: whether the server survives
on a stock heap is itself an exit criterion, so the flag under test is never
the default.

```bash
# full-library build, then serve and query it
python3 bench/run_build.py  --server fork/dist/index.js --data-dir <dir>
python3 bench/run_serve.py                       # restart, open, query
python3 bench/run_serve2.py                      # same, auto-refresh off

# JSON -> SQLite migration, isolated, with the environment recorded
node bench/migrate_measure.mjs <index.json> <out.sqlite>
node bench/slice_index.mjs <big.json> <small.json> <n-chunks>

# query both backends and compare result sets
python3 bench/query.py   --server fork/dist/index.js --data-dir <dir> --backend json
python3 bench/compare.py --a res_json.json --b res_sqlite.json

# vector benchmarks (need sqlite-vec)
node bench/vec_scaling.mjs        # is vec0 KNN sub-linear? it is not
node bench/vec_quantize.mjs       # float32 vs int8 vs binary
cd fork && npx tsx ../bench/vec_recall.ts   # recall of two-stage vs exact

# standalone FTS5 prototype, and resting memory
node bench/fts5_bench.mjs ~/data/Zotero/storage bench/data/keys.txt bench/index.sqlite
python3 bench/measure_resting.py --server fork/dist/index.js --data-dir <dir>

# probes behind specific tickets
python3 bench/fulltext_sequence.py --output <f.json>          # 0012: the two version sequences
node bench/fold_sweep.mjs --output <f.json>                   # 0009: JS fold vs what FTS5 indexes
node bench/index_concentration.mjs --db <index.sqlite> --output <f.json>   # 0013: concentration and ranking
node bench/bm25_idf_effect.mjs                                # 0013, superseded by the above
bash bench/results/json-baseline/rung.sh <label> <items> <chars>   # the JSON memory ladder
```

Three of these read the LIVE Zotero local API or a real index rather than a
fixture, so their output is a record of one library at one moment; each writes
its own provenance into its artifact. `fold_sweep.mjs` is the exception and is
fully deterministic — it builds its own in-memory FTS5 table.

`bench/run_serve.py` and `run_serve2.py` still carry hardcoded paths from the
run that produced `bench/results/0003-full-build/`; they need editing before
reuse elsewhere. `rung.sh` used to be in that category and no longer is: every
path it uses is overridable and defaults into the committed tree.
