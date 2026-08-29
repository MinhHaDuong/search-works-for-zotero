# Smoke test — zoteus v1.10.0 against the author's real Zotero library

*Evidence, not authority. Run 2026-08-29 on host doudou, at the author's
request. Where anything here touches the design, the owning document in
`CLAUDE.md`'s document set is the record. Artifact:
`bench/results/smoke-1.10.0/queries.json`.*

**Subject:** upstream `oscardvs/zoteus` at `b132f2d`, tag `v1.10.0` — the
reviewed baseline in `UPSTREAM`. A fresh clone, not the author's `fork/`, which
was left untouched on `stopwords-follow-up`.

**Substrate:** the live Zotero desktop library on doudou
(`/home/haduong/data/Zotero`), Zotero running throughout. Every server ran with
`ZOTEUS_READ_ONLY=true`; nothing wrote to the library.

**Driver:** `bench/mcp_drive.py` over stdio JSON-RPC.

## What was established

**It installs and builds from the tag.** `npm ci && npm run build` on `b132f2d`
produced `dist/index.js` with no errors.

**The MCP handshake succeeds and the server advertises 31 tools**, among them
`zotero_semantic_search`, `zotero_index`, and `zotero_search_items`.

**It sees the live library.** `zotero_whoami` reports `localApi: true`,
`localApiWatched: true`, default library user/0, and the local embedder active
(`configured: local`, `effective: local`). `zotero_search_items` with
`qmode=everything` for *carbon tax* returned **1 479 results** at library
version **418** — the live number, read through the running desktop app.

**The index it queried holds 93 022 passages** with as many vectors, over
2 100 items, of which 1 531 carry full text contributing 89 674 passages;
embedder `Xenova/all-MiniLM-L6-v2`.

**Semantic search answers, and the answers are relevant.** Ten queries (five
subjects, each in `semantic` and `auto` mode) all returned hits, judged by
reading them: a French query on adaptation cost surfaced the author's own
Dumas & Ha-Duong 2002 first; a permafrost query surfaced the tipping-elements
paper's `PFAT Boreal Permafrost (abrupt thaw)` row.

**Cross-lingual, one datapoint worth keeping (ticket 0037's territory).** The
Vietnamese query was typed *without diacritics* — `nang luong tai tao o Viet
Nam` — and retrieved correctly-diacriticised Vietnamese documents (`năng lượng
tái tạo`, `Việt Nam`) in both modes. One query is a probe, not a benchmark, and
nothing here separates the embedder's doing from `remove_diacritics 2`'s.

## Three findings

### 1. The pre-rename indexes are unusable, and the server says so well

Pointed at `vec-real`, the 93 022-vector index this repo built before the
schema rename, v1.10.0 refused it:

> The search index … carries tables but no schema stamp — an interrupted
> creation, or not a Zoteus index at all. It was moved aside to
> `search-index.sqlite.incompatible-2026-08-29T15-43-22-683Z` (nothing was
> deleted) and a fresh index was created.

It then answered every semantic query with a zeroed status block rather than an
error. The refusal is the right behaviour and the message is honest about what
it did. The operational consequence is the one already recorded on ticket 0025:
`vec-real` and its pre-rename siblings carry `index_meta` and an FTS-virtual
`passages`, where v1.9.0 and later want `meta`, a plain `passages`, and
`passages_fts`. The index that works is
`/home/haduong/data/projets/zoteus-bench/issue30/master/search-index.sqlite`
(`schemaVersion` 1).

**Read the zeroed status block as a failure, not as an empty library.** A
caller that checks only `hits` sees an empty result and no error — the
all-clear and the could-not-look, again, being the same output.

**This is not an upstream migration problem, and the check is worth stating
because it looks like one.** Read from upstream history rather than inferred:
`index_meta` appears in **no upstream commit, ever**, while `passages_fts` and
the `schemaVersion` stamp both arrive together in `eee1000`, the first commit of
the SQLite backend, released in **v1.7.0**. `SCHEMA_VERSION` was introduced as 1
there and has never been bumped in the three releases since. The schema this
repo tripped over is its own archived prototype
(`archive/fts5-storage-2026-08-21`), which no user ever ran. Users predating the
SQLite backend are unaffected for a separate reason: that index persisted as
`search-index.json`, a different filename, so it is never inspected by this
path.

**What the episode does expose is prospective, and it is structural.** There is
no migration code, and none is contemplated by the shape of the check:

```ts
if (stored === 'fresh' || stored === SCHEMA_VERSION) return;
// …everything else is renamed aside and rebuilt from zero
```

Sideline-and-rebuild is the *only* behaviour on any schema that is not exactly
the current one — an older stamped version included. So the day
`SCHEMA_VERSION` becomes 2, every user's index is discarded and rebuilt, and the
rebuild's cost is dominated by re-embedding, which is the expensive half and is
not measured here. The 263,7 s this repo records for a 477 512-passage rebuild
is the FTS half alone. Sidelining rather than deleting is the right call and the
notice is honest; what is missing is any path that reads an old index instead of
abandoning it.

Whether that deserves an upstream issue is the author's call and the budget is
currently spent (both slots on #27 and #28). It is recorded here, not filed.

### 2. In `semantic` mode the returned score is a rank, not a similarity

Three of the five `semantic` queries returned byte-identical top-5 scores, and
they are exactly 1/(60+rank):

| rank | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| observed | 0,016393 | 0,016129 | 0,015873 | 0,015625 | 0,015385 |
| 1/(60+rank) | 1/61 | 1/62 | 1/63 | 1/64 | 1/65 |

That is reciprocal-rank fusion with k=60 over a single ranked list, so the
score is position relabelled. The other two queries show gaps in the sequence
(1/61, 1/64, 1/66 …), meaning candidates were dropped between pool and result,
and one returned four hits where five were asked for. In `auto` mode the top
scores differ per query, being a sum over two lists — still ranks, still not
similarities.

**Consequence for an MCP client, which is the point of the interface:** the
score cannot be thresholded. A perfect match and the least-bad of a bad pool
both score 1/61, so an agent consuming these results has no signal for *found
nothing good*. This bears on the coverage-honesty requirements (R4, R17); it is
recorded here as an observation, and the owning document decides what follows.

### 3. Warm semantic latency is in tens of milliseconds; the first query is not

Wall time through MCP, so these include JSON-RPC and tool dispatch, n=1 per
cell:

| mode | first query | later queries |
|---|---|---|
| `semantic` | 5 641,2 ms | 17,4 ms to 24,4 ms |
| `auto` | — | 50,0 ms to 154,5 ms |

The first figure is the local embedder's model load plus the ANN code build,
not query cost, and must never be quoted as latency. `auto` costs several times
`semantic` because BM25 runs beside the vector path — the shape ticket 0025
measured, where `auto` improves 12,2x against `semantic`'s 49,3x.

## The end-to-end path, built fresh from the live library

The queries above ran against a pre-built index. To close that gap a second
server built one from scratch under `ZOTEUS_INDEX_MAX_ITEMS=30`, against the
live library at version 418. It completed: 30 of 30 items, **671 passages** and
671 vectors, of which 619 passages came from the 18 items carrying full text,
in roughly three minutes. A semantic query then answered in 36,0 ms and an
`auto` query in 17,5 ms. So install, index, and query all work against the
author's own library, not only against an index this repo had lying around.

Two observations, neither a verdict:

- Peak resident memory reached **2 245 MiB** (`VmHWM`) for a thirty-item build.
  That is the class ticket 0011 recorded for the uncapped 44,9 MB document,
  reached here under a cap that was expected to bound it. Whether one large
  attachment in the first thirty items explains it is untested; X3a is the
  step that would settle it.
- The build reports `builtFromVersion: 30` while the library is at 418 — the
  item cap appearing where a library version belongs. Read once, not chased.

**A correction worth recording, because it was nearly published as a finding
about zoteus.** This report first said the fresh build had stalled: no CPU, no
database growth, zero passages. It had in fact finished. The driver's poll loop
waited for `state == "idle"` where the server reports `state == "done"`, so it
spun to its own timeout on completed work, and the flat database file was a
build that had already written. The predicate folded two states the server
distinguishes — the trap `rules/coding-bash.md` names for `is-active`, here in
Python. The lesson is the general one: before reporting that a process is
stuck, check that your liveness test can express the state it actually reached.

## Provenance and honest gaps

- The queried index was built at library version 410 while the live library is
  at 418, so results reflect an index eight versions stale.
- Every latency here is n=1 in one session on a fanless i5-8250U, the machine
  whose thermal drift ticket 0025 recorded. They locate an order of magnitude
  and nothing finer.
- The five subjects were chosen by the agent from the library's evident
  domains, and relevance was judged by reading the hits. That is a smoke test,
  not a recall measurement.
