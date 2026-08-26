# Implementation review — cycle 2's design and work train audited against edf2748

*Feasibility audit, 2026-08-26. Distinct from the design-quality critiques: every hook
point below was opened at upstream `oscardvs/zoteus` HEAD `edf2748` (v1.7.0,
`/home/user/oscardvs/zoteus`), every driver opened in `bench/`, every artifact opened in
`bench/results/`. Verdicts: FEASIBLE-AS-SCOPED / NEEDS-RESCOPE / BLOCKED. Effort assumes
the house rules (tests-first Vitest, `.js` relative ESM imports, contained diffs).*

## Verdict table

| Item | Verdict | Effort | One-line reason |
|---|---|---|---|
| 0014 shepherd #19/#20 + stopwords | FEASIBLE | hours + 1 d PR | but the follow-up's X2 number needs the author's 650k corpus |
| 0015 PR-1 schema read-before-write | FEASIBLE | 0.5–1 d | hook verified: `sqlite-index.ts:114` calls `createSchema` (stamp at :151–153) before `loadMeta` (:118) |
| 0016 PR-2 busy_timeout + per-page commit | FEASIBLE (caveat) | 1 d | cadence exists (`index-manager.ts:472–473`), but fulltext builds override it to 500 items / 60 s (`build.ts:321`) — above the 5 s timeout |
| 0016 PR-3 cross-library wipe guard | NEEDS-RESCOPE | 1–2 d | no library identity is stamped in meta today; `users/0`↔cloud aliasing makes "different library" undefined (`build.ts:185–197`) |
| 0017 PR-4 cacheDir / PR-5 Gemini key | FEASIBLE | 0.5 d + 2 h | both hooks exact (`embeddings.ts:158–184`, `:258`) |
| 0018 PR-6 per-attachment fulltext | NEEDS-RESCOPE | 3–4 d | schema + `ChunkRecord` contract ripple through both backends; split in two |
| 0019 PR-7 no-text terminal state | FEASIBLE | 1–2 d | needs a small new store for reasons; independent of PR-6 at item granularity |
| 0020 PR-8 pause + verbs | NEEDS-RESCOPE | 1 d + 2 d | pause+auto_build gate is contained; `purge`/`reset`/confirm-tokens are new tool surface, not a rider |
| 0021 PR-9 keep-vectors, pin embedder | FEASIBLE (caveat) | 1–2 d | two drop sites, and "pin" implies reconstructing a provider from the stored id string |
| 0022 PR-10 own-words crawl | FEASIBLE | 1–2 d | local client passes `itemType` through, non-top crawl exists (`local-client.ts:99–101`) |
| 0023 PR-11 query compiler | NEEDS-RESCOPE | 3–5 d | "entry scope" cannot exist upstream pre-RFC — the hit unit is the item (`index-manager.ts:906`) |
| 0023 PR-12 fraction-RRF | FEASIBLE | 1 d | fusion site is 7 lines (`index-manager.ts:88–94`); golden numbers gated on the unbuilt fixture corpus |
| 0024 four issues | FEASIBLE | hours | drafted FINAL per SYNC.md |
| 0025 X1–X7 | NEEDS-RESCOPE | see below | five of seven need the author's machine; the ticket never says which |
| 0026 gates | NEEDS-RESCOPE / partly BLOCKED | see below | fold gate buildable now; golden lacks its corpus; convergence + soak presuppose post-RFC machinery |
| 0027 RFC | FEASIBLE | 2–4 d writing | X5-gated, and X5 is author-machine + unbuilt code |

PR-level: 8 FEASIBLE, 4 NEEDS-RESCOPE, 0 BLOCKED. Ticket-level: 8 / 6 / 0, with two of
0026's five gates unbuildable before the RFC's machinery exists.

## 1. The upstream train, PR by PR

**PR-1 (0015).** Verified exactly as claimed: `SCHEMA_VERSION = 1` at `sqlite-index.ts:26`,
re-stamped by `createSchema` via `INSERT OR REPLACE` at :151–153, and `open()` (:101–119)
runs `createSchema` → `prepareStatements` → `loadMeta` — the stamp is written before it is
ever read, and `loadMeta` (:210–224) never reads `schemaVersion` at all. The fix is
contained: `open()` already computes `existed` (:104) before creating the handle, so the
read-check-sideline can slot in before any DDL. One wrinkle the ticket should absorb: on a
fresh file there is no `meta` table, so the read must probe `sqlite_master` first. Test
surface is good — `tests/features/search-backends.test.ts` family exists, `:memory:` and
fixture-path constructors both supported. ~100-line diff. FEASIBLE.

**PR-2 (0016).** Zero `busy_timeout` confirmed (`grep` over `src/`: nothing), and the
BEGIN-at-first-mutation/commit-at-save shape is exactly as the design describes
(`sqlite-index.ts:192–203`, :470–472). The per-page claim is *already mostly true*:
`maybePersist` runs after every page (`index-manager.ts:545`) with defaults 200 items /
10 s (:472–473). What the ticket misses: `crawlOptions` overrides the cadence to **500
items / 60 s on every fulltext build** (`build.ts:321`) — precisely the build that holds
the write lock longest — so a 5 s `busy_timeout` alone leaves a 60 s hold window on the
path that matters. The PR must also lower that override or it fails its own repro under
fulltext. The update path's single transaction (persist once at `index-manager.ts:731`,
rollback at :766) is correctly left alone. FEASIBLE with that one-line addition, ~1 day.

**PR-3 (0016).** The chain is real: `buildIncremental` → `this.reset()`
(`index-manager.ts:467`) → `clearStore()` (:387–396; SQLite impl `sqlite-index.ts:307–316`
deletes everything). But the guard as ticketed — "a build for a different library than
stamped refuses" — has nothing to compare against: **no library identity is persisted**.
Meta holds `libraryVersion`/`libraryBackend` (:226–234), never a library id, and
`build.ts:185–197` documents *deliberately* not keying the store by routed library id
because the personal library is `users/0` locally and `users/<id>` on cloud — the same
library under two names. The PR therefore has to (a) invent and stamp a canonical identity
and (b) not refuse legitimate rebuilds across the local/cloud seam. That is a small design
decision, not just a guard. NEEDS-RESCOPE: stamp `{type,id}` with personal-library
normalized to one token, and say so in the PR body. 1–2 days once decided.

**PR-4/PR-5 (0017).** Both exact. `LocalEmbeddingProvider.ensure()`
(`embeddings.ts:158–184`) imports transformers and calls `pipeline()` without ever touching
`env` — no `cacheDir` is set anywhere, so the default cache lands outside dataDir as
claimed. `config.dataDir` exists (`config.ts:36`) and `createEmbeddingProvider` receives
the full config (:291), so threading it into the provider opts is trivial; the only care
point is that the loaded module's `env` may sit under `.default` (same dance as `pipeline`
at :178). Testable via the existing `loadExtractor` injection plus a stub package dir.
PR-5 is `embeddings.ts:258`: `?key=${this.apiKey}` in the URL, verbatim — move to
`x-goog-api-key` header, one test asserting no key in any thrown URL. Hours each. FEASIBLE.

**PR-6 (0018).** Concatenation verified: `textFor` joins attachment slices with `'\n\n'`
(`fulltext-source.ts:119–146`) and returns a single string; `addFulltext` chunks it with
ids `#f<n>` (`index-manager.ts:861–873`) — per-attachment totals and the offset→attachment
mapping are destroyed exactly as claimed. But the fix is not confined to fulltext-source:
per-attachment provenance must travel through `ChunkRecord` (`backend.ts:32–39`, currently
`{id,itemKey,title,text,source?}`), through `putPassage` in **both** backends, into the
`passages` table (a new column ⇒ the first real `SCHEMA_VERSION` bump — which only means
anything after PR-1 lands, so the train's ordering is right and load-bearing), into the
memory backend's JSON snapshot, and skip-reasons need a store that doesn't exist. This is
the largest pre-query PR in the train, plausibly 600+ lines with tests against a
maintainer whose merged PRs are contained. NEEDS-RESCOPE: split into (a) per-attachment
records + totals, (b) first-with-text policy + stored skip reasons. 3–4 days total.
**Conflict warning: PR-7 rewrites the same `textFor`/warn-once region
(`fulltext-source.ts:130–138`); 0018 and 0019 must be sequenced, not sent concurrently.**

**PR-7 (0019).** The warn-once is real (`failures++ === 0` at `fulltext-source.ts:132`),
and the no-text case (item absent from the `/fulltext?since=0` census) currently just
yields `undefined` forever. Terminal state at *item* granularity needs no PR-6: a small
`fulltext_state(item_key, reason)` table (SQLite) / snapshot map (memory) plus a status
line. Feasible independently, 1–2 days — but see the conflict warning above.

**PR-8 (0020).** Hooks verified: `stop` cancels one job (`index-tool.ts:56–65`,
`requestStop` at `index-manager.ts:345–349`), and `auto_build` defaults on
(`semantic-search.ts:48–65`) — any query against an empty index starts a build, exactly
the R22 violation. The pause row + gate is contained (~1 day: one meta row, read in
`index-tool` build/update and in `semantic-search` auto_build). The **verbs residue is
not a rider**: `reset` is not in today's action enum (`index-tool.ts:21` —
`build|refresh|update|status|stop`), `purge` and confirm-tokens are new tool-contract
surface, and "purge = checkpoint + VACUUM + compaction" references a sidecar that doesn't
exist upstream. NEEDS-RESCOPE: ship pause+gate as the PR; verbs as a follow-up PR (or fold
into the RFC conversation). 1 day + ~2 days.

**PR-9 (0021).** The violation is verified at *two* sites, not one:
`reconcileVectorProvenance` → `dropStaleVectors` → `clearVectors()` on open
(`index-manager.ts:301–308`, :286–293; SQLite `clearVectors` at `sqlite-index.ts:390–394`),
plus the query-time dimension check that drops again (`index-manager.ts:889–892`). Both
must be neutered. "Pin the query embedder to the stored id" means constructing a provider
from the stored identity string (`embedderIdentity` = `name:model`, `embeddings.ts:29–31`)
instead of the configured one — parseable, and same-provider model pins (the ticket's own
failing test: a different `ZOTEUS_EMBEDDING_MODEL`) are clean; a cross-provider pin needs
the old provider still constructible (key present, package installed), so the PR must
specify the degradation when it isn't (serve keyword + typed reason, not drop). FEASIBLE
with that branch written down. 1–2 days.

**PR-10 (0022).** Gap verified: builds crawl `top: true` only (`build.ts:214`, :260), and
the local client routes `top` to `/items/top` vs `/items` and passes `itemType` through
(`local-client.ts:99–101`; `fulltext-source.ts:87–92` already does an
`itemType: 'attachment'` crawl — the exact pattern to copy). One scope correction: the
exit criterion "own field/column" cannot mean an FTS column upstream — the schema has one
`text` column; it can only mean a `source: 'note'|'annotation'` label extending the
existing `source: 'fulltext'` pattern (`backend.ts:38` widens). Feasible so scoped,
1–2 days.

**PR-11 (0023).** The tokenizer defects are exactly as cited (`tokenize.ts:1–11`:
`/[a-z0-9]+/g` + 29 stopwords; OR-joined MATCH at `sqlite-index.ts:418–430`; memory BM25
tokenizes through the same filter, `bm25.ts:40,64`). The `Blocked-by: 0014` is correct and
real — `normalizeForSearch` does not exist anywhere in `src/` at edf2748; it arrives with
PR #19. But the ticket's own words — "AND and NOT evaluate at ENTRY scope … joined on the
hit unit" — collide with the tree: **upstream has no entries; the hit unit is the item**
(`query()` collapses on `seen.has(rec.itemKey)`, `index-manager.ts:906`). Pre-RFC, the PR
can only join hard predicates at item scope (or passage scope, which the critique killed).
That is fine — item scope is entry scope's conservative projection at today's granularity
— but the PR body must say it, or it re-ships the framing v1's PR6 died for. Also the X4
ladder constant it waits on is measured "on the 477k corpus", which lives at
`/home/haduong/...` (see §2) — the declared `Blocked-by: 0025` makes 0023 author-gated in
practice. NEEDS-RESCOPE (wording + an honest item-scope statement), 3–5 days: it is the
largest PR in the train (parser, two backends, parity stream, fill ladder, tests).

**PR-12 (0023).** `rrf()` is seven lines at `index-manager.ts:88–94`, fusing exactly two
lists at :901. The flagged variant + seam-invariant unit test is ~1 day. Its "golden
Jaccard in the body" depends on the golden fixture corpus that no ticket builds (§3).

**Ordering across the train**: PR-1 before PR-6 (schema bump needs a reader) — present and
correct. PR-2/PR-3 same file family — correctly bundled. The one missing edge: 0018↔0019
touch the same forty lines of `fulltext-source.ts` and carry no ordering between them.

## 2. Experiments X1–X7: what can run *here*, and what cannot

The critical fact the ticket omits: **the corpora are not in the repo.**
`bench/results/0008-real-vectors/` holds two JSON *summaries* (13 KB + 1.7 KB); the actual
93,022 real vectors (dim 384) live in a 343 MB SQLite file at
`/home/haduong/data/projets/zoteus-bench/vec-real/search-index.sqlite` on host `doudou`
(`real-93022.json` "db" field). The 477k-passage index behind 0011/0013 likewise
(`uncapped-477512.json` "db" field). The 44.9 MB Palgrave extraction is only reachable
through the author's live Zotero. Per experiment:

- **X1** — SPLIT. Drivers exist (`vec_quantize.mjs`, `vec_scaling.mjs`,
  `vec_real_measure.mjs`, `vec_recall.ts`) and `vec_scaling.mjs` is fully synthetic
  (deterministic seed, needs only `npm i sqlite-vec`) — the *layout/scan-timing* half runs
  in this container at 100k/650k. The *int8 recall@30* half cannot: `real-93022.json`'s
  own anisotropy section states why a symmetric synthetic fixture cannot exhibit the risk,
  and the real vectors are on the author's disk, capped at 93k (650k real vectors would be
  ~7,500 s × 7 of embedding). **Author's machine for the recall gate.**
- **X2** (stopword-less OR at 650k) — **author's machine** (needs the 477k/650k FTS
  index; nothing committed is an index).
- **X3** (monster RSS with streamed slab chunking) — **author's machine** for the real
  44.9 MB doc, *and* it measures code — the streamed slab chunker — that no ticket
  writes. A synthetic 44.9M-char monster can proxy in-container for the RSS *fixture*
  (0026 wants exactly that), but X3 as worded is both machine- and code-gated.
- **X4** (json_each cost curve) — as worded ("on the 477k corpus"), **author's machine**.
  Honestly rescopable: the cost curve's *shape* is structural, and a synthetic 477k-row
  FTS5 corpus is an hour of container work; the decision rule (turn ~20k into a constant)
  survives the substitution if the artifact says so.
- **X5** (segmenter over the real extraction, 50 hand-checked cuts) — **author's
  machine**, plus a human, plus **seg/1 does not exist and no ticket builds it** (§4/§5).
  DESIGN §5's "half a day" prices the run, not the segmenter.
- **X6** (version-0 dynamics) — **author's machine only**: two live Zotero profiles
  (synced and never-synced) and manual re-extraction in the app. `fulltext_sequence.py`
  is the right probe to extend and is read-only, but nothing here can host Zotero.
- **X7** (census parse at 30k entries) — **runs in this container today**: synthesize
  30k-entry JSON, time the parse. Hours.

Also binding, from SYNC.md §Mechanics and unticketed: five drivers hardcode the wrong
env var (`ZOTEUS_SEARCH_BACKEND` vs upstream's `ZOTEUS_INDEX_BACKEND`) and "it must land
before any re-measurement" — X2/X4 re-measurement silently measures `auto` until that
one-line-per-driver fix lands. No ticket carries it. 0025 must annotate each X with its
required substrate, or the exit criterion "each X has a committed artifact" is
unsatisfiable from this repo alone. NEEDS-RESCOPE.

## 3. The gates (0026)

**Fold gate** — `fold_sweep.mjs` exists but is currently a *measurement*, not a gate: it
writes JSON, prints a WARNING on `misses > 0`, and **always exits 0** (:155–161). It also
imports `{ tokenize, normalizeForSearch }` from `${fork}dist/...` (:34) — against stock
upstream, `normalizeForSearch` is `undefined` and line 70 throws: today it is red **by
crash**, exactly what the operator-critic's M2 repair forbids, and the repair is real work
(fallback + classification + nonzero exit). "Repointed at the tree under test" further
requires a buildable checkout: the default `--fork ../fork/` path does not exist in this
repo, and `/home/user/oscardvs/zoteus` is read-only with no `dist/`. So the gate needs: a
writable clone, `npm ci && tsc`, the fallback, and exit-code semantics. All feasible
in-container (~1 day). FEASIBLE.

**Golden gate** — the thresholds are properly re-derived (0.8 mean / 0.35 / 0.2 floor,
matching the recomputed 0.25 minimum in `uncapped-477512.json`), but **no pinned fixture
corpus exists anywhere in this repo**: `bench/queries.txt` is 16 queries, not ~40, and
every answer-set artifact was measured against the author's private library, which cannot
be committed or reproduced. Creating the multilingual fixture corpus — documents, ~40
queries, pinned answer sets, and the harness that builds an index over it (drivable
without Zotero by loading the fork's backend classes directly and calling `putPassage`) —
is an **unticketed prerequisite**, 2–3 days. Until it exists the gate cannot go into
`make check` as DESIGN §2.8's target line demands. NEEDS-RESCOPE.

**RSS gate** — the synthetic monster generator is feasible here (deterministic 44,906,152
chars, ~43k headings; the measured numbers to reproduce are in
`0011-rss/capped-vs-uncapped.json`). But the assertion pair "worker VmHWM ≤ 500 MB,
server p95 ≤ 300 MB" presupposes a **P1 worker process that does not exist** — upstream
embeds in-process on the server event loop (`embedPending`, `index-manager.ts:810–839`).
Pre-RFC the gate can only assert single-process RSS against stock upstream (which it will
fail, per 0011's 2,084.9 MiB — informative, but a permanently red gate is Risk-5 decay by
another name). NEEDS-RESCOPE: state the pre-RFC form (server-only, waivered) and the
post-RFC form separately.

**Convergence harness and soak** — these are the ordering error of the cycle. The harness
asserts per-stage counters, prefix arithmetic, `drift`, `pipeline: idle`; the soak asserts
lease migration < 30 s and zero double-commits. **Every one of those observables is
ledger/conductor machinery that exists only after the RFC's design is built** — upstream
at edf2748 has no ledger, no stages, no counters, no leases, no second process. Yet 0026
carries no `Blocked-by:` at all (0023 and 0027 both declare theirs), and its exit criteria
demand "phases 1–3 runnable" and "soak scripted with the five assertions". As ticketed,
these two are BLOCKED until post-RFC implementation — which is not even 0027 (0027 is the
*issue*, not the build). Additionally the harness's "fixture library" needs a mock Zotero
local API server; every driver in `bench/` talks to a live Zotero, and no mock exists —
another unticketed prerequisite (~2–3 days). The honest fix: split 0026 into
gates-buildable-now (fold; golden-after-corpus; RSS-server-only) and gates-that-are-the-
RFC's-acceptance-spec, the latter Blocked-by the RFC outcome.

## 4. The load-bearing mechanisms (DESIGN §2) under the real architecture

**Conductor election + worker lifecycle under MCP stdio** — implementable, and the design's
crash-only assumptions are *more* right than it knows: on the stdio path
(`src/index.ts:73–76`) **no shutdown handlers are installed at all**
(`installShutdownHandlers` is called only inside the `--http` branch, :63–72), so a stdio
zoteus dies by SIGKILL-or-EOF with no flush — lease-TTL expiry and the worker's
stdin-EOF/holder-check repairs are the only mechanisms that *can* work, and they need no
cooperation from upstream's lifecycle code. Spawning a `nice 19` child from a stdio MCP
server is unproblematic. All RFC-scope, all buildable. FEASIBLE.

**Contentless FTS5 (`contentless_delete=1`, SQLite ≥ 3.43)** — verified in this container:
`node:sqlite` on Node 22.22.2 reports SQLite **3.51.2**; the author's artifacts record
3.51.3 (`real-93022.json`), and the earliest Node that ships `node:sqlite` at all (22.5)
carried 3.46 — every runtime that can reach the SQLite backend clears 3.43. The "probed
fallback, chosen once, recorded in meta" is cheap insurance that will essentially never
fire. FEASIBLE.

**New-filename migration** — naming verified: `sqliteIndexPath()` strips `.json` →
`search-index.sqlite` beside `search-index.json` (`factory.ts:20–22`), path built at
`server.ts:89–92`. One gap the design never mentions: multi-tenant mode keys the file as
`search-index-<zoteroUserId>.json` — `search-index-v2.sqlite` must mirror that suffix or
N tenants share one v2 file. One line in the RFC, but it should be there. FEASIBLE.

**Per-field FTS vs the SearchIndex interface** — the seam is real and the design
underprices one corner. `ChunkRecord` is `{id, itemKey, title, text, source?}`
(`backend.ts:32–39`) and `itemText()` joins all fields with `'. '`
(`index-manager.ts:61–67`) — the D5 field-seam claim checks out. Per-field columns require
a new ingestion record and touch every `putPassage` implementation. The unaddressed
corner: **the memory backend**. DESIGN §2.6 demands memory-backend parity for phrase/AND/
NOT, but says nothing about what `BM25Index` (one flat token stream per doc, `bm25.ts`)
does under an eight-column schema — per-field BM25 with column weights is a rewrite, and
"sqlite-only for v2" is a decision nobody has made out loud. RFC must decide it. FEASIBLE
with that decision named.

## 5. Missing work — obliged by the design, carried by no ticket

1. **seg/1 itself.** X5 gates the RFC on the segmenter's measured precision, and the
   segmenter (line classification, heading rhythm, confidence gate — DESIGN §2.2) has no
   implementation ticket. Days of new code standing between 0025 and 0027, priced nowhere.
2. **The golden fixture corpus** (§3): documents, queries, pinned sets, the Zotero-free
   index-loading harness. 0026 consumes it; nothing produces it.
3. **A mock Zotero local API server** for the convergence harness and soak. Everything in
   `bench/` requires live Zotero.
4. **The bench-driver env-var fix** (SYNC §Mechanics): five drivers measure `auto` until
   `ZOTEUS_SEARCH_BACKEND` → `ZOTEUS_INDEX_BACKEND` lands. Precondition for X2/X4.
5. **The frac_vec calibration ticket.** DESIGN §2.6 defers calibration "to its own ticket
   with a stated pair-generation protocol" — no such ticket exists in 0014–0027.
6. **The streamed slab chunker** X3 measures (and the RSS gate's post-RFC fixture needs).
7. **The memory-backend decision** under the per-field schema (§4).
8. **Multi-tenant suffix** for `search-index-v2.sqlite` (§4) — one RFC line.

## The one-paragraph verdict

The train's diagnosis is impeccable — every claimed hook point in tickets 0015–0023 exists
at the cited file and line, and eight of twelve PRs are honestly contained. The four
rescopes share one root: the tickets occasionally borrow RFC-era vocabulary (entries, a
stamped library identity, verbs, a worker) for a tree that doesn't have those nouns yet.
The genuinely wrong ordering is confined to 0026, which schedules the convergence harness
and soak — assertions over a ledger and conductor that exist only after the RFC's
machinery is built — with no Blocked-by and exit criteria demanding they run; and 0025's
worst omission is silence about substrate: X2, X3, X5, X6 and half of X1 cannot produce
artifacts from this repo, because the corpora they need live on `doudou` under
`/home/haduong/`, not in `bench/results/`. The single most consequential missing ticket is
seg/1: the design's self-declared biggest bet gates the RFC on an experiment over code
nobody is scheduled to write.
