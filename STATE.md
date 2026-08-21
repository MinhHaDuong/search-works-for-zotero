# STATE — zoteus-fts5

Prototype work: replace zoteus's resident JS search index with SQLite/FTS5.

## What this repo is

Ticket store, measurement harness, and notes for a chantier whose code lives in
a **fork of someone else's project**. `fork/` is a plain checkout of
`MinhHaDuong/zoteus` (upstream `oscardvs/zoteus`) and is git-ignored here — it
has its own history, and a `tickets/` directory must never appear in it, or it
would show up in any diff sent upstream.

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

No current setting both writes and reads this library back: 40 000 chars/item
fits but discards 61% of the text, 200 000 writes but needs
`--max-old-space-size=12288` to reload, uncapped will not write at all.

## Next action

**Ticket 0002 — schema and keyword-only `SqliteSearchIndex`.** Its design
decisions were reviewed with the author on 2026-08-21 and are settled in the
ticket body; no code written yet. Start by implementing the schema and the
query-sanitisation piece, then point upstream's existing search tests at the
new class.

0002 is the only child carrying design risk; 0003–0006 follow from it.

## Gates

Upstream's own: `npx vitest run`, `tsc --noEmit`, `eslint`. This project's
Python and prose rules do not apply to a TypeScript repo. The load-bearing
check is not the suite but **same corpus in, same results out** against the
current index — a green suite passes on a refactor that quietly changed
ranking.
