# STATE — zoteus-fts5

Prototype work: replace zoteus's resident JS search index with SQLite/FTS5.

## What this repo is

Ticket store, measurement harness, and notes for a chantier whose code lives in
a **fork of someone else's project**. `fork/` is a plain checkout of
`MinhHaDuong/zoteus` (upstream `oscardvs/zoteus`) and is git-ignored here — it
has its own history, and a `tickets/` directory must never appear in it, or it
would show up in any diff sent upstream.

## The fork checkout

`fork/` sits on branch **`fts5-base`** = PR #11 ⊕ PR #12 merged, not upstream
`main`. Both are prerequisites for measuring anything: without #11's
configurable cap the library never indexes past 5 000 items, and without #12
the ASEAN group library is invisible. 477 tests green on that base. 0002's work
branches from `fts5-base`, and it is pushed to the fork so the base is
reproducible.

## Posture

The maintainer has not yet answered. Work proceeds as a **prototype in the
fork, with no merge request opened** for the storage layer — the posture stated
in the comment on oscardvs/zoteus#10. If he picks direction (d), this becomes
the PR; if he picks (a) or declines, it is a usable fork.

## Upstream, as of 2026-08-21

| | state |
|---|---|
| [oscardvs/zoteus#10](https://github.com/oscardvs/zoteus/issues/10) | open — persistence ceiling, + comment proposing SQLite as direction (d) |
| [#11](https://github.com/oscardvs/zoteus/pull/11) | open, no review — item cap configurable + `truncationNotice` |
| [#12](https://github.com/oscardvs/zoteus/pull/12) | open, no review — group libraries served locally on Zotero 10 |

Both branches were force-pushed on 2026-08-21 to drop a stray executable bit:
an `install -D` used while splitting the patches had marked every touched
`.ts` file 100755, which showed in the diffs as `old mode / new mode` noise.
`scripts/backup-store.sh` is executable upstream and stays so.

## The measurements that motivate this

Zotero library of 7 540 top-level items, 0,86 GB of text already extracted by
Zotero into `.zotero-ft-cache`.

| | zoteus (resident JS) | FTS5, same geometry | FTS5 prototype bench |
|---|---|---|---|
| passages | 477 511 | **477 511** | 408 628 |
| build | 337 s | **339–374 s** | 46,6 s |
| RSS peak during build | 6,48 GB | **1 892–2 085 MiB** | — |
| RSS at rest / serving | 5 370 MB | **121–135 MiB** | 162 MB |
| on disk | 546 MB (write fails) | **949,5 MiB** | 762 MB |
| reload | OOM on stock Node | **opens the file, stock Node** | opens the file |
| query | 0,37–0,5 s | **33–339 ms** (MCP round trip) | 1–76 ms (bare SQLite) |

**Two caveats on the memory column, both raised at review and both load-bearing
for anything quoted externally.** The FTS5 figure is process RSS, and SQLite
uses default buffered I/O with no `mmap_size` — so the kernel page cache
holding up to 949,5 MiB of database file is *not* in it. The resident-JS
figure has no such hidden remainder: every byte it needs is JS heap, which RSS
sees. Read as total memory implicated, the win is nearer 5x than 40x. And the
5 370 MB baseline itself **was never measured by this repo** — it predates the
first commit, with no recorded instrument or method, while every FTS5 number
here comes from `VmHWM`. One half of the ratio is reproducible from committed
artifacts and the other is inherited. Re-measuring the JSON backend with the
same instrument would close it; until then the *direction* is solid (the
write-fails and reload-OOM walls are structural) and the *ratio* is not
quotable.

Measured 2026-08-21 on the 7 540-item library, uncapped, full text on, no
`--max-old-space-size` at any point. Raw artifacts in
`bench/results/0003-full-build/`; drivers are `bench/run_build.py`,
`run_serve.py`, `run_serve2.py`. Two runs, byte-identical in every content
figure. Also recorded: `fulltextItems` 5 562, `fulltextPassages` 465 110,
`fulltextPendingItems` 429 (attachments Zotero has not extracted yet, which
bounds the corpus).

**Read the columns carefully — only the first two are comparable.** The middle
column runs the server's own chunker at zoteus's geometry (512/64 metadata plus
1200/150 full text), which is why its passage count lands on 477 511 exactly,
to the unit. The third column is `bench/fts5_bench.mjs`, a direct SQLite
benchmark at 1200-no-overlap over attachment text only — a different corpus and
no MCP framing, no RRF, no snippet extraction. Its 1–76 ms is not the number a
user experiences; the middle column's 33–339 ms is. Of that, 200–300 ms on a
cold query is 0006's Zotero freshness probe, not FTS5: with
`ZOTEUS_INDEX_AUTO_REFRESH=false` the fastest query measured 32,7 ms.

**Two claims not to overstate.** Peak RSS *during the build* is ~2 GB, not the
"few hundred MB" ticket 0003 anticipated — reproduced across both runs, filed
as ticket 0011. The at-rest figure, which is the one the chantier turns on, is
unaffected at 121–135 MiB. And the build is API-bound, not SQLite-bound: run 2
spent 113 s of its 339 s on the first page of full text.

Three things to settle before the #10 writeup, all established 2026-08-21.

**Zotero 10 already runs FTS5 itself** (`fulltext.sqlite`, attached as
`ftindex`: `fulltextContent USING fts5(text, tokenize='unicode61',
content='')`), but the tables are *contentless* — matchable, not readable. That
is why zoteus keeps its own copy of the text, and it forecloses "just reuse
Zotero's index" before someone proposes it. Their release notes make the
rewrite sound more reusable than it is.

**Zotero is building semantic search** — zotero/zotero#6012, draft, two core
developers, active daily, superseding its own predecessor #5984. It does
**not** expose anything over the local API: no file under `xpcom/server/` is
touched and no endpoint is contemplated, so zoteus cannot delegate and the
vector work here stands. Notably they *declined* `sqlite-vec` and score with
brute-force JS dot products, which puts this prototype's `vec0` KNN ahead of
theirs rather than behind. They fuse keyword and vector with RRF at `k = 60` —
the same constant this prototype picked independently.

**Zotero ships structure extraction we did not know about.** `Zotero.SDT`
(`sdt.js` + `structured-document-text.js`, in the installed build) writes a
per-attachment `.zotero-sdt-cache` pack carrying page labels, outline paths,
reader positions and running-head exclusion. An earlier finding here said
Zotero exposes no in-text structure; that was true of `.zotero-ft-cache` and
wrong about Zotero. It is **not reachable on a stock install**: a PDF opened
in Zotero on 2026-08-22 reported `Indexed: yes` and wrote its
`.zotero-ft-cache` post-install, and no pack appeared — the library-wide count
is still zero. Extraction runs; SDT does not. One residual path (open in a
reader *tab*, not just the item pane) is narrowed but not formally closed.
Ticket 0007 carries it, with `bench/results/0007-sdt-probe.txt`.

No current setting both writes and reads this library back: 40 000 chars/item
fits but discards 61% of the text, 200 000 writes but needs
`--max-old-space-size=12288` to reload, uncapped will not write at all.

## What has landed

All five children of 0001 are implemented in the fork and gate-verified.
Upstream's suite went **477 → 668 tests**, `tsc --noEmit` and `eslint` clean at
every wave. Committed on the fork's **`fts5-storage`** branch (off `fts5-base`)
as `b2fd0f0`, 36 files, +4 738/−139, pushed to `origin/fts5-storage`.

One commit rather than five: the waves overlapped on `index-manager.ts` and a
faithful per-ticket split is not reconstructible from the result. The
consequence is that **only the final 668 is checkable against the tree** — the
per-wave counts below are as reported wave to wave, with no commit boundary to
verify them against.

| ticket | what | suite after |
|---|---|---|
| 0002 | `PassageStore` port, `Fts5PassageStore`, MATCH sanitiser, `SqliteSearchIndex` | 581 |
| 0003 | transaction boundaries on the port, `ZOTEUS_SEARCH_BACKEND`, `persistence.ts` off the SQLite path | 592 |
| 0005 | streaming JSON → SQLite migration, no dependency, atomic rename | 612 |
| 0004 | vectors in `vec0` via `sqlite-vec` (optional dep), KNN in C | 652 |
| 0006 | library-version watermark, `?since=` deltas, deletion by key-set reconcile | 668 |

Design decisions taken on the way, each recorded in its ticket: a store port
rather than a duplicated class (0002); the `engines` floor left at `>=20.19`
with a lazy `node:sqlite` import (0002); "match" defined as top-k item-set
overlap, since FTS5 and the JS BM25 cannot agree on scores (0002); and the
`sqlite-vec` ruling in 0004 **reversed on evidence** — `node:sqlite` does load
extensions, and zoteus already carries two optional dependencies on the same
graceful-degradation pattern.

One deliberate divergence from upstream: the SQLite backend refuses
`toJSON`/`loadFromJSON` rather than materialising 477 511 passages into the
heap. A second was recorded here as deliberate — "FTS5 out-recalls the JS index
on accented queries" — and **that was wrong**. Measurement on the real library
showed accented queries returning confident noise, not extra recall; it is a
correctness defect, ticket 0009, and the section below carries the evidence.

## Migration, measured 2026-08-21

The 463 MB index no longer exists. Two points were measured on real data,
because the claim under test is how migration memory grows with file size and
one point cannot show that. Both are re-runs: the figures first published here
came from an agent's uncaptured stdout and were not reproducible from any
committed artifact — a review caught it, and these replace them.

| | 105 MB JSON | 321 MB JSON |
|---|---|---|
| migration, isolated | 13,7 s | 42,7 s |
| **peak RSS** (`VmHWM`) | **80,7 MiB** | **97,0 MiB** |
| resulting database | 162,3 MB | 498,7 MB |
| ratio to JSON | 1,5416 | 1,5522 |

**File ×3,05, memory ×1,20 — strongly sublinear, not flat.** Linear would have
been ×3,05. An earlier reading claimed flat (×2,10 file, ×1,02 memory); that
was the unbacked one. The streaming scanner does bound memory well, and there
is a real size-dependent component on top of it.

Artifacts `bench/results/0005-migration/migrate_{105,321}MB.json`, driver
`bench/migrate_measure.mjs`, which records `NODE_OPTIONS`, Node version, both
file sizes and `VmHWM` into its own output so this cannot recur. The smaller
index was cut from the larger with `bench/slice_index.mjs` — real passages,
fewer of them.

For comparison, the JSON backend loading the same indexes cost 1 896 MB and
3 786 MB (`res_json.json`, `res5k_json.json`), roughly 11,8× the file and
linear in it. Startup is 45 s including the one-off migration and 0,97 s on a
later start at the 153 MB scale — that 0,97 s is a single warm-cache reading
at one size, not a measured property of every start.

The database/JSON ratio is **1,55×**, not the 1,34× budgeted from the synthetic
fixture — confirmed at both sizes — so a full-size migration needs ~715 MB, not
620. The 463 MB criterion **stays open**; 321 MB is 69% of it.

## Accented queries are broken on the SQLite backend

Found by that comparison and now ticket 0009, raised from enhancement to
defect. `toMatchQuery` tokenises with `/[a-z0-9]+/g`, so `théorie` becomes the
fragments `"th" OR "orie"` while FTS5 has folded the document side to
`theorie`. The two never meet, and `"th"` matches English prose:

    SQLITE  "théorie" -> 20 hits: Do conservation contests work? / Graphical Economics / …
    JSON    "théorie" -> 14 hits: Théorie économique… / Éléments d'économie politique pure… / Cournot

Jaccard 0,00. Twenty confident, plausible, entirely wrong results — worse than
an empty answer, because a user cannot tell. Across the accented set: 0,00 to
0,50, against 0,48–1,00 for every ASCII query. The index is fine; the query
path alone is broken.

Zotero was checked for the same defect and does not have it, which gave a
better fix than the one first filed. It pre-tokenises in JS exactly as we do,
and avoids the bug by keeping the fold **in JS, applied to both sides by one
function**, with a Unicode-aware token class `/[\p{L}\p{N}]+/u`. Our fold sits
inside SQLite where only the document side passes through it. Widening the
token class matters as much as folding: it fixes non-Latin scripts, Vietnamese
`đ` and the CJK blind spot in one change, and would alone have prevented this
defect by keeping `théorie` a single token. Once the fold is in JS the FTS5
`remove_diacritics` setting stops mattering — which is why Zotero can run
`unicode61` for content and `trigram` for notes, with opposite defaults, and
neither is wrong.

Quantified on the real index: the fragments our regex produces, `th` and
`orie`, match 1 904 and 13 documents — `th` alone about eleven times the
correct answer set.

## Binary quantization: measured, and rejected for now

Ticket 0008 proposed it on a measured 13x speedup. That figure was taken at
`k=30` and does not survive being asked for a *pool*: vec0's k-best structure
costs more than linearly in `k` (7,7 ms at k=30, 83,6 at k=480, 216,8 at
k=960, against 121 ms for the whole exact float32 scan). So the pool that
preserves the ranking is slower than the scan it would replace.

Recall@30 at N=100 000, dim 384, clustered fixture: 0,256 binary-only, 0,628
at a 4x pool, 0,862 at 8x, 0,998 at 16x — and the 16x pool costs 272 ms
against 110 ms exact. Recall was the acceptance criterion, so the two-stage
path ships **off by default**. Both columns are maintained on every insert, so
enabling it later is a one-line flip, not a reindex. float32 stays mandatory.

The lesson is the same one this chantier keeps paying for: a ratio measured at
one operating point is not a property of the system. The real-library
re-measure stays open, and the risk to test there is anisotropy —
`vec_quantize_binary` thresholds at zero, real sentence embeddings are not
zero-mean, and the first pass could be worse on real data than on these
fixtures. Centring on the corpus mean is the remedy, and is what
zotero/zotero#6012 already does.

## What "the whole library" actually means

Established 2026-08-22, and it qualifies every corpus figure above.

**Zotero's own indexing is heterogeneous, and zoteus inherits it.** Zotero
reports 12 242 attachments indexed, **1 072 partially indexed**, 749 with no
text available, 1 216 notes. Three sampled attachments stop at exactly 100
pages (100/262, 100/148, 100/116) — the page cap firing. Yet the largest
document in the library is complete: the New Palgrave Dictionary, 15 497 pages,
`indexedPages == totalPages`, 44 906 152 characters returned by the API.
Neither the 500 000-char nor the 100-page cap bound it. So per-item state
varies, upstream bounds nothing reliably, and zoteus records none of it —
`fulltext-source.ts` takes `content` and never reads `indexedPages` /
`totalPages`, which the API supplies precisely so a client can tell.

**One item is 9% of the index.** That dictionary contributes **42 962 of
477 511 passages**; the next largest item contributes 1 449, a 30× gap. Ticket
0013 carries it. Three consequences: BM25's `idf` and `avgdl` are corpus-wide,
so a tenth of the corpus being one reference work shifts the statistics for
exactly the vocabulary this library is about; a single 44,9 MB string live in
the build's page loop is a far more specific suspect for the ~2 GB peak than
ticket 0011's original "100 uncapped texts" hypothesis, and a cheaper
experiment; and every per-passage average quoted here is computed over a
population containing a 30× outlier.

Cache files on disk total 859 219 358 bytes across 13 631 attachments, which is
where the 0,86 GB figure comes from.

## Next action

**The chantier's code is complete** — fork `bac5d62` on `fts5-storage`, 679
tests, tsc and eslint clean. 0002–0006 are closed; 0007–0012 are open.

The measurement work that needed the real library is now done: the full build
(0003) and the migration (0005) are both measured and their artifacts
committed. What remains is not more measurement but three decisions.

1. **Fix the accented-query defect (0009).** It is the only known way the
   SQLite backend returns *wrong* answers, and the fix is small and known:
   fold in JS on both sides, widen the token class to `/[\p{L}\p{N}]+/u`.
   Nothing should be quoted upstream while this is live.
2. **Decide what the #10 report may claim about memory.** The at-rest ratio is
   not currently quotable — see the caveats on the table above: the FTS5 side
   excludes page cache, and the 5 370 MB baseline was never measured by this
   repo. Re-measuring the JSON backend with `VmHWM` closes it, and it is the
   number most likely to be lifted verbatim.
3. ~~Settle 0007 with one PDF.~~ **Done 2026-08-22: no pack.** Structure-aware
   chunking is a future option, not a present one, so 0007 proceeds on
   configuration and measurement. One residual check (reader tab rather than
   item pane) would close the last path.

Two criteria remain open and are not blockers: the 463 MB migration at full
size (0005 — 321 MB reached, 69%), and 0008's re-measure on the real vector
index, where the anisotropy risk is the thing to test.


## Gates

Upstream's own: `npx vitest run`, `tsc --noEmit`, `eslint`. This project's
Python and prose rules do not apply to a TypeScript repo. The load-bearing
check is not the suite but **same corpus in, same results out** against the
current index — a green suite passes on a refactor that quietly changed
ranking.
