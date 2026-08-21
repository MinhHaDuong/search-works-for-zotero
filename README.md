# zoteus-fts5

Work tracking for a storage-layer prototype in [zoteus](https://github.com/oscardvs/zoteus),
an MCP server over a local Zotero library.

zoteus holds its search index resident in JS objects and snapshots it with one
`JSON.stringify`. On a 7 540-item library that costs 5,4 GB of RAM, fails to
serialise past V8's 512 MiB string limit, and cannot be reloaded by a stock
Node. The same corpus in SQLite/FTS5 costs 162 MB resident and builds seven
times faster.

- `tickets/` — the work, tracked with [git-erg](https://github.com/MinhHaDuong/git-erg)
- `bench/` — the measurement harness: an MCP stdio driver, build timing, resting
  memory, and a standalone FTS5 prototype
- `fork/` — a checkout of the fork; git-ignored, cloned by hand

See `STATE.md` for current status and `tickets/0001-*` for the plan.

## Bench

```bash
node bench/fts5_bench.mjs ~/data/Zotero/storage bench/data/keys.txt bench/index.sqlite
python3 bench/measure_resting.py --server fork/dist/index.js --data-dir <dir>
```
