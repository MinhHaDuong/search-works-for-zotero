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

| | zoteus (resident JS) | FTS5 via `node:sqlite` |
|---|---|---|
| passages | 477 511 | 408 628 |
| build | 337 s | 46,6 s |
| RSS at rest | 5 370 MB | 162 MB |
| on disk | 546 MB (write fails) | 762 MB |
| reload | OOM on stock Node | opens the file |
| query | 0,37–0,5 s | 1–76 ms |

**The `passages` row is not like-for-like** and should not be read as one:
`bench/fts5_bench.mjs` chunks attachment full text only, at 1200 with no
overlap, while zoteus indexes metadata at 512/64 *plus* full text at 1200/150.
Three independent differences before storage enters the picture. Build time,
disk and RSS still hold — the resident-JS column is measuring a larger corpus,
which if anything understates the win. Ticket 0007 carries the fix.

Also worth knowing before the #10 writeup: **Zotero 10 already runs FTS5
itself** (`fulltext.sqlite`: `fulltextContent USING fts5(text,
tokenize='unicode61', content='')`), but the table is *contentless* — matchable,
not readable — which is why zoteus reads the cache and why "just reuse Zotero's
index" is not available.

No current setting both writes and reads this library back: 40 000 chars/item
fits but discards 61% of the text, 200 000 writes but needs
`--max-old-space-size=12288` to reload, uncapped will not write at all.

## What has landed

All five children of 0001 are implemented in the fork and gate-verified.
Upstream's suite went **477 → 668 tests**, `tsc --noEmit` and `eslint` clean at
every wave. Nothing is committed in `fork/` yet — the author owns those commits.

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
