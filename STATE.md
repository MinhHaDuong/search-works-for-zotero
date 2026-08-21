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
| build | 337 s | **339 s** | 46,6 s |
| RSS peak during build | 6,48 GB | **2 085 MiB** | — |
| RSS at rest / serving | 5 370 MB | **121–135 MiB** | 162 MB |
| on disk | 546 MB (write fails) | **949,5 MiB** | 762 MB |
| reload | OOM on stock Node | **opens the file, stock Node** | opens the file |
| query | 0,37–0,5 s | **27–339 ms** (MCP round trip) | 1–76 ms (bare SQLite) |

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
user experiences; the middle column's 27–339 ms is. Of that, 200–300 ms on a
cold query is 0006's Zotero freshness probe, not FTS5: with
`ZOTEUS_INDEX_AUTO_REFRESH=false` the best query measured 26,9 ms.

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
wrong about Zotero. Whether it is *reachable* is open: zero packs exist, and
the one path known not to produce them is the post-install bulk full-text
re-index. No PDF has been opened in the reader since the 2026-08-21 14:26
install, so the reader path is untested rather than ruled out — one PDF opened
in Zotero decides it. Ticket 0007 carries the correction and the experiment.

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

Two behavioural divergences from upstream, both deliberate and both tested:
FTS5 **out-recalls** the JS index on accented queries (`remove_diacritics 2`
folds the document side), and the SQLite backend refuses `toJSON`/`loadFromJSON`
rather than materialising 408 628 passages into the heap.

## Migration, measured 2026-08-21

The 463 MB index no longer exists, so two real ones were built from the live
library instead — 153 MB and 321 MB — because the claim under test is that
migration memory *does not scale with file size*, and one point cannot show it.

| | 153 MB JSON | 321 MB JSON |
|---|---|---|
| migration, isolated | 17,0 s | 28,4 s |
| **peak RSS migrating** | **94 MiB** | **96 MiB** |
| same index into the JSON backend | 1 896 MB | **3 786 MB** |
| resulting database | 236 MB | 499 MB (1,55×) |

File ×2,10, migration memory ×1,02. Flat, on real and messy text. The backend
it replaces is linear at roughly 11,8× the file. Startup is 45 s including the
one-off migration and **0,97 s on every later start**, against 30,8 s every
time for JSON. Passage counts match exactly on both sides, `integrity_check`
ok, source JSON byte-identical afterwards, no WAL residue.

Two corrections: the database/JSON ratio is **1,55×**, not the 1,34× budgeted
from the synthetic fixture — so a full-size migration needs ~715 MB, not 620.
And the 463 MB criterion **stays open**; 321 MB is 69% of it.

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
path alone is broken, and a shared NFD fold in front of `tokenize()` closes it.

## Next action

**The author's own library is the remaining gate.** Four exit criteria across
0001, 0003, 0004 and 0005 need the real 7 540-item corpus and cannot be
fabricated; the commands are in each ticket. In order:

1. Migrate the existing `search-index.json` (0005) — watch peak RSS, which
   should *not* scale with file size.
2. Full build on the sqlite backend (0003) — build time, peak RSS, on-disk
   size, and that the server serves with no `--max-old-space-size`.
3. Embedding pass (0004) — bytes/passage and semantic query latency.
   `bench/build_index.py` hardcodes `ZOTEUS_EMBEDDINGS: "off"`; that one key
   needs changing first.
4. Old-vs-new result comparison on the same corpus (0001), then the findings
   go on oscardvs/zoteus#10.

Then commit the fork branch, and consider 0008 (binary quantization: measured
13x faster, 24x smaller) before the #10 writeup, since it changes the numbers
that writeup would quote.

## Gates

Upstream's own: `npx vitest run`, `tsc --noEmit`, `eslint`. This project's
Python and prose rules do not apply to a TypeScript repo. The load-bearing
check is not the suite but **same corpus in, same results out** against the
current index — a green suite passes on a refactor that quietly changed
ranking.
