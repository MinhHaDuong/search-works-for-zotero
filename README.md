# zoteus-fts5

Work tracking for the search redesign of [zoteus](https://github.com/oscardvs/zoteus),
an MCP server over a local Zotero library. The TypeScript under discussion
lives upstream and in the author's fork, not in this repo.

Upstream ships its own SQLite/FTS5 backend since v1.7.0 (closing
[#10](https://github.com/oscardvs/zoteus/issues/10), which this repo argued).
The storage-layer prototype this repo was started for is therefore superseded,
and the live work is the redesign — four documents and the tickets:
`REQUIREMENTS.md` (what the system promises), `CONSTRAINTS.md` (what the world
imposes), `DESIGN.md` (the current design), `DECISIONS.md` (the append-only
ratification ledger), and tickets `0014`–`0035` (the work train as re-formed
by the panel reviews; closed tickets in `tickets/closed/`).
`panel/cycle2/` holds the raw panel record behind the design; `SYNC.md` says
where things stand against upstream. Superseded documents live in git history,
not in the tree.

- `tickets/` — the work, tracked with [git-erg](https://github.com/MinhHaDuong/git-erg)
- `bench/` — the measurement harness (below)
- `bench/results/` — committed raw artifacts behind the figures in `STATE.md`
- `fork/` — a checkout of the fork; git-ignored, cloned by hand

## The prototype phase, kept as the record of the argument

Before v1.7.0, zoteus held its search index resident in JS objects and
snapshotted it with one `JSON.stringify`. On a 7 541-item library that cost
gigabytes of RAM, failed to serialise past V8's string limit, and could not be
reloaded by a stock Node. The same corpus in SQLite/FTS5 served from about
128 MiB of process memory and reloaded on a stock Node — which was the point.
It did **not** build faster: measured at the same chunk geometry, through the
same Zotero API, the build took about as long either way, because it is bound
by fetching from Zotero rather than by indexing.

Measured over **one corpus of 360 811 passages read by both backends** — the
same crawl's `search-index.json`, migrated in place, rather than two crawls that
ought to agree: **5 759,6 MiB against 128,0 MiB** resident, and **90,87 s
against 3,86 s** to first answer.

Read `STATE.md` (the prototype phase's measurement record) before quoting any
of that. The memory figure excludes the kernel page cache holding the database
file, where the JS heap figure has no such remainder; charge SQLite the whole
file and the win is 6,8x rather than 45x. Both numbers are measured and both
belong in any external claim. The figures are measurements of the fork's
prototype, not of upstream's backend.

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
