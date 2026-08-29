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

## Provenance and honest gaps

- The queried index was built at library version 410 while the live library is
  at 418, so results reflect an index eight versions stale.
- Every latency here is n=1 in one session on a fanless i5-8250U, the machine
  whose thermal drift ticket 0025 recorded. They locate an order of magnitude
  and nothing finer.
- The five subjects were chosen by the agent from the library's evident
  domains, and relevance was judged by reading the hits. That is a smoke test,
  not a recall measurement.
- A fresh build from the live library was started under
  `ZOTEUS_INDEX_MAX_ITEMS=30` to exercise the path end to end. It had not
  finished when this report was written, holding 2,02 GiB resident — the
  RSS class ticket 0011 recorded for the uncapped monster document, reached
  here at a 30-item cap. Unfinished, so no verdict; the observation is
  recorded because the cap was expected to bound it.
