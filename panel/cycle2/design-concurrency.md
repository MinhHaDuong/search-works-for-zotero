# CYCLE 2 — MULTI-LIBRARY & CONCURRENCY MEMO
*Architect lens: many libraries, many processes, one data dir. Against sheet v2 (DESIGN.md + ratified DESIGN-DELTA.md + SCOUTS.md), upstream verified at `/home/user/oscardvs/zoteus` HEAD `edf2748`.*

## Verified facts this memo stands on

1. **One fixed default data dir.** `defaultDataDir()` resolves to one platform path unless `ZOTEUS_DATA_DIR` overrides (src/lib/paths.ts:5-10). stdio spawns one zoteus per MCP client, so two clients means two servers on the same files.
2. **One store, keyed by context, not by library — documented as a feature.** The build doc-comment says it in as many words: "the index store is keyed by the context (dataDir …), never by the routed library id" (src/features/search/build.ts:185-188). `startIndexBuild(ctx, lib?)` pages *any* library into that one store (build.ts:199-227).
3. **The clearStore hazard is real, verified end-to-end.** `buildIncremental` calls `this.reset()` (index-manager.ts:467); `reset()` calls `clearStore()` (index-manager.ts:387-388); `SqliteSearchIndex.clearStore()` runs `DELETE FROM passages` and `DELETE FROM items` (sqlite-index.ts:307-313). A build over group X erases the personal index first. `zotero_semantic_search` takes no library argument at all (src/tools/semantic-search.ts — no `library` input), so the query side cannot even ask which library it is searching.
4. **The schema cannot hold two libraries.** `items (item_key TEXT PRIMARY KEY, title TEXT NOT NULL)` (sqlite-index.ts:129); Zotero item keys are unique *per library*, so even without clearStore, two libraries silently merge and collide on the 8-char keyspace. Deletes are `WHERE item_key = ?` (sqlite-index.ts:172-173) — unscoped.
5. **No busy_timeout, no SQLITE_BUSY handling, anywhere.** `grep -rn 'busy_timeout\|SQLITE_BUSY' src/` returns zero hits. The driver is the synchronous `DatabaseSync` (sqlite-index.ts:16,105), WAL + `synchronous=NORMAL` (sqlite-index.ts:109,113).
6. **Upstream holds one write transaction from first mutation until `save()`.** `BEGIN` on the first mutating call, `COMMIT` only in save (sqlite-index.ts:192-201, 469-476); a build persists every 200 items / 10 s (index-manager.ts:472-473). So a second process's *first write* during that window throws SQLITE_BUSY immediately (no timeout to wait it out), unhandled.
7. **The only mutual-exclusion guard is process-local memory.** `if (this.isBuilding) throw` (index-manager.ts:447-448) — invisible to a second process. Meta state (`libraryVersion`, `libraryBackend`) is loaded once at open (sqlite-index.ts:217-219) and cached in JS; another process's commits are never re-read.

Facts 1–7 together are R13's indictment: today, two zoteus on one data dir is a coin-flip between an unhandled crash and two builds interleaving `DELETE FROM passages` on each other. And R12's: a group build is not additive, it is destructive, by verified code path.

---

## (a) VERDICTS ON V1

**§1 skeleton (SQLite ledger, lease claim/commit, two planes).** SURVIVES — and better than v1 knew. The lease-based (item × stage) ledger is exactly the structure that makes multi-*process* claims safe, not just multi-loop claims; v1 argued it for crash-safety, sheet v2's R13 makes it load-bearing for correctness. AMEND: every ledger row gains the library key (below), and the claim statement's assumption "one worker exists" is replaced by an election (below).

**§2.1 storage.** AMEND, three ways. (i) R12/D4-merged obliges a `lib` column on every row; fact 4 shows the current PK cannot express it and fact 3 shows what happens without it. (ii) The **fulltext watermark is DEAD as designed.** V1 wrote "two watermarks — item_watermark and fulltext_watermark … the 0012 defect class becomes unwritable." SCOUTS.md's C1 sharpening kills the second one: local `/fulltext?since=` versions are a mixed sequence (web stamps / local client versions / 0 for local extraction), equality-comparable per item, *never* a monotonic cursor. A stored fulltext high-water mark on the local transport silently loses every locally-extracted text (version 0 < any watermark). Replaced by a per-attachment version map + census-intersect (§b.2). (iii) The record ruling amends the two-column FTS split: `meta_text` flattening title+abstract+tags into one weighted column repeats upstream's field-identity loss the ruling names; fields keep identity (§b.4). The slab store, the derived sidecar, and same-transaction watermark stamping all SURVIVE.

**§2.2 discovery (census-seeded newest-first frontier).** SURVIVES per-library; AMEND to run per `(origin, library)` with a cross-library merge defining what "newest first" *means* under D4-merged (§b.3). The politeness constraint (≤4 concurrent, honor `Backoff:` even on 2xx) binds the web transport only — new, from SCOUTS.

**§2.3 topology (P0 server + P1 nice-19 worker, two planes).** AMEND — this is my lens's center. V1's "two OS processes" quietly assumed one zoteus. Fact 1 says N servers is the *normal* deployment. So: N × P0, and exactly one elected conductor owning the single P1 (§b.5). V1's pipe-based pause also fails across processes — a query arriving at server B cannot pipe-pause server A's worker; replaced by the activity-touch protocol (§b.5.4). The in-server query embedder, write-free query path, and micro-batch commits SURVIVE — the last two are now load-bearing for N-process safety, not just latency.

**§2.4 fairness (recency-major, two bands, K=64).** SURVIVES within one library; AMEND for the cross-library frontier and for the ratified phase order (record for everyone, newest first — body after), which happens to compose with Zotero #6012's own smallest-first-within-attachments exactly as SCOUTS says a ratification decision must state. Stated in §b.3.

**§2.5 freshness (tick owns the clock; probe-don't-fix).** SURVIVES in shape; AMEND: the tick sweeps per-library item watermarks and does the fulltext *census-intersect* instead of a `?since=` cursor sweep (fact from SCOUTS; SYNC.md §4 reached the same conclusion independently: "census-intersect is the only safe close on local"). The tick runs in the conductor, not in every server (§b.5).

**§2.6 failure policy.** SURVIVES. ADD: SQLITE_BUSY-after-timeout is a named *transient* class (retry, never quarantine); lease theft is a normal event, not a failure; the `empty` tombstone is now ratified ground (R14/D8), not a graft.

**§2.7 query path and ranking.** AMEND, twice, on sheet-v2 material v1 never saw. (i) **"Collapsed to items before ranks are assigned" is DEAD**: the unit-of-answer ruling makes the retrieval and dedup unit the section/entry, so collapse is to `(item, entry)` — an encyclopedic item legitimately yields several hits; D9 dissolved with it. (ii) **R5's "joins the predicate down" is half-DEAD**: SCOUTS' #6012 finding — constraining FTS5 MATCH to a rowid set makes FTS5 evaluate per row, seconds at library scale — means filters push into SQL for *metadata* columns and the bitmap is applied to MATCH *candidates after* unconstrained evaluation, never inside the MATCH. V1's bitmap survives; where it is applied changes. The `library` facet joins the bitmap (R12). Plain RRF k=60 SURVIVES (the deferral of fraction-weighting stands; note #6012 uses fraction-weighted + MAX-over-chunks — MAX-over-*entry* now, and the experiment stays deferred).

**§2.8 contract.** SURVIVES; AMEND: coverage blocks become per-library × per-stage (R17 under D4-merged), scoped coverage answers R18 for the library facet too, `pause` becomes durable state (R22 — v1's pipe pause did not survive restart), and C4 is now ratified: every count from materialized counters, never a scan (v1 already complied; now it is a gate, with 0013's 374 ms cold GROUP BY as the cited violation, bench/results/0013-concentration/).

**§2.9 budgets.** AMEND: the arithmetic must be per-process and multiplied (§b.6). V1's "server ≤300MB" silently assumed one server.

**§3.1 vectors, §3.2 CJK, §3.3 stopwords.** SURVIVE (other lenses own quality); my amendment: sidecar writes are conductor-only, generation-numbered, atomic-rename (§b.5.5). #6012's 2-gram twin tables are new prior art *for* v1's §3.2 v2 plan.

**§3.6 schema self-description.** SURVIVES; AMEND for R23 under concurrency: two servers of different zoteus versions share the file, so "sideline the incompatible file" is wrong while another process serves from it — replaced by read-compatibility gating (§b.7).

**§3.7 coverage sentence.** AMEND: per-library clause (§b.8).

**§4 increments.** Reworked in (c): v1's PR1 *is already open* as PR #19; #20 overlaps PR4/PR8.

**§5 Risk 3 (synchronous driver under concurrency).** PROMOTED from risk to requirement: the soak becomes a multi-process gate (§b.9), per R20's "budgets are gates" logic applied to R13.

---

## (b) THE DESIGN — replacement text

### b.1 Identity and schema keying

Every library is `(origin, kind, id)`. `origin` is the **Zotero-Server-ID** partition SCOUTS mandates ("clients that store data between runs should partition it by server ID" — two local profiles share the label 'local' and share nothing else). Interned once:

```sql
CREATE TABLE origins (oid INTEGER PRIMARY KEY, server_id TEXT UNIQUE NOT NULL);
CREATE TABLE libraries (
  lib INTEGER PRIMARY KEY,
  oid INTEGER NOT NULL REFERENCES origins,
  kind TEXT NOT NULL CHECK (kind IN ('user','group')),
  remote_id INTEGER NOT NULL,          -- userID or groupID
  name TEXT,
  item_watermark INTEGER NOT NULL DEFAULT 0,
  watermark_backend TEXT,              -- 'local' | 'cloud', per stamp
  UNIQUE (oid, kind, remote_id)
);
```

Every row downstream carries `lib`: `items (lib, item_key, version, date_added, …, PRIMARY KEY (lib, item_key))`; passages, slabs, vectors, and the ledger key by `(lib, item_key, …)`. All deletes are `WHERE lib = ?` scoped. **`clearStore()` is abolished from the build path entirely**: "rebuild" is `UPDATE ledger SET status='pending', input_key=NULL WHERE lib=?` — a per-library state, never a `DELETE FROM passages` (this is R12's "indexing one never erases another" made unwritable, the same move v1 made for the 0012 watermark transposition). Fulltext state is per-attachment, not a watermark:

```sql
CREATE TABLE attachments (
  lib INTEGER, att_key TEXT, parent_key TEXT,
  fulltext_version INTEGER,            -- last version seen in census; NULL = never seen
  content_hash TEXT,                   -- guards R11: same bytes => no re-derive
  PRIMARY KEY (lib, att_key)
);
```

`content_hash` (hash of extracted text) is what makes counter churn not change (R11): a census says the version moved; the extract stage re-fetches; if the hash matches, the chain stops there — chunk and embed keys are downstream of the hash, not the counter.

### b.2 Freshness without a fulltext cursor

Per library, the reconcile tick does: (i) `?since=item_watermark` item delta (monotonic, safe — library versions are one sequence); (ii) every Nth tick, a `/fulltext?since=0` **census** (key→version map, cheap: pairs only) intersected against `attachments`: any key whose census version ≠ stored `fulltext_version` (including stored NULL, including census 0 for local extraction) re-enters the extract queue; any stored key absent from item census is a delete. Equality-compare, never order-compare — the mixed-sequence trap (SCOUTS C1) is then unrepresentable in the schema: there is no column a monotonic cursor could live in. Deletion (R15) rides the same census subtraction and cascades: ledger rows, slabs, passages, vectors, sidecar tombstones (compacted next generation).

### b.3 What "newest first" means across libraries

One **global frontier**, ordered by `date_added DESC` interleaved across all libraries — recency is the researcher's notion and it is library-blind; a paper added to a group yesterday outranks my own from 2019. Phase-major, per the record ruling:

- **Phase 0 — records**: title/abstract/keywords/notes/annotations (D7) for every item of every library, globally newest-first. This is D1's first 100% and it composes with #6012's own scheduling exactly as SCOUTS frames the choice: metadata for all libraries first, then attachments — we take newest-first where they take smallest-first *within* attachments, and we state that composition as a decision: **ratified order = newest-first, both phases; the depth cap (band K=64) does the anti-monopoly work smallest-first does for them.**
- **Phase 1 — body text**: v1's two bands survive per item, ordered globally by recency.

Discovery cannot itself interleave (censuses are per-library HTTP), so ordering lives in the ledger, not the crawl: run all `?format=versions` censuses first (complete universes, ~20 bytes/item), then metadata sweeps as a k-way merge on page heads — each library's sweep is `sort=dateAdded&direction=desc`, so taking the library whose next unfetched page-head is newest yields a globally newest-first fill. Web-served group libraries obey the politeness constraint (≤4 concurrent, `Backoff:` honored on any response); a backoff'd library drops out of the merge without stalling the others — its absence is disclosed in coverage, because R26's "newest-first prefix" is otherwise false during backoff (see Confession 3).

### b.4 Record fields keep identity

The FTS table carries one column per semantic field: `title, abstract, keywords, creators, notes, body` with `bm25(fts, w_t, w_a, w_k, w_c, w_n, w_b)` — a tag match no longer scores like a title match (the record ruling's exact complaint against upstream's joined string). Chunk boundaries never straddle entries; embedded text is prefixed with entry heading / outline path / item title (ratified; #6012 prior art). Passages carry `(lib, item_key, entry_ord, entry_heading)` — `entry_ord` is the dedup unit at ranking (verdict on §2.7).

### b.5 The multi-process protocol (R13)

**Rule 0 — every connection**: `PRAGMA busy_timeout = 5000` on open; WAL; `synchronous=NORMAL`; **no transaction spans an await, and no write transaction exceeds one micro-batch** (~500 passages / ≤50 ms). Upstream's BEGIN-at-first-mutation-COMMIT-at-save (fact 6) is replaced by commit-per-micro-batch; the ledger makes partial progress durable, so the long transaction bought nothing but the write lock.

**1. Conductor election, not process exclusion.** Every server answers queries (WAL readers, write-free query path). Exactly one server at a time is *conductor*: it runs the reconcile tick and owns the single P1 worker. Election by lease row, seeded at schema creation:

```sql
CREATE TABLE leases (name TEXT PRIMARY KEY, holder TEXT, expires_at INTEGER);
-- claim/renew, one statement, atomic under SQLite's write lock:
UPDATE leases SET holder=:me, expires_at=:now+30
 WHERE name='conductor' AND (holder=:me OR expires_at < :now);
```

`holder` is a per-process UUID (pid is recyclable). Heartbeat renews every 10 s; two missed beats and any server's next tick steals the lease and spawns its own worker. A lockfile is rejected: lockfiles go stale exactly when the holder dies, which is the case that matters; the DB row expires by clock and its claim is atomic under the same lock discipline everything else already uses.

**2. Correctness never depends on the singleton.** The conductor lease is an *efficiency* device (don't run two embedders on one core budget). Safety lives one level down, in v1's per-row leases, now cross-process: claim = `UPDATE ledger SET status='leased', lease_until=…, worker=:me WHERE lib=:l AND item_key=:k AND stage=:s AND status='pending'` (one statement, atomic); commit guarded by `claimed_input` — if the input key changed underneath, the commit is discarded. A zombie worker surviving a stolen lease can therefore waste at most one micro-batch of compute and can never double-commit or commit against stale input. R13's "no passage extracted or embedded twice" is met as: **never committed twice; recomputed at most one micro-batch per failover.** Stated honestly, because the strict letter is unachievable without distributed consensus SQLite cannot host.

**3. Durable pause (R22).** `CREATE TABLE control (key TEXT PRIMARY KEY, value TEXT)`; `paused=1` written by any server's `pause` verb, checked by the worker between micro-batches and by would-be conductors before spawning P1. Survives restart by construction; `auto_build` defers to it.

**4. Foreground-beats-background across processes.** V1's stdio pipe only reaches the conductor's own worker. Generalized: each P0, on query arrival, touches `<dataDir>/activity` (utimes — a filesystem op, no DB lock, so the query path stays write-free even in the DB sense). The worker stats it between micro-batches and idles 2 s when mtime is fresher than 2 s. The conductor's own pipe remains as the low-latency fast path; the touch file is the floor for everyone else. `nice 19` remains the OS-level floor beneath both.

**5. Sidecar and checkpoint discipline.** The vector sidecar is written only by the conductor, as `vectors-<embedderKey>.g<N>` + fsync + atomic rename, current generation named in `meta`; readers open by name and hold the fd (POSIX keeps unlinked old generations readable; on Windows the previous generation file is retained until the next compaction). The conductor runs `PRAGMA wal_checkpoint(TRUNCATE)` at idle; queries are single statements, never long read transactions, so readers cannot pin the WAL indefinitely.

**6. Two profiles, one dir.** A profile switch is a different `Zotero-Server-ID`, i.e. a different `oid` partition in the same file. Nothing is cleared; coverage and freshness report per-origin, and status names which origin is currently reachable. (See Confession 2 on obtaining the ID.)

### b.6 Budgets, multiplied honestly

Per-process, N servers: idle P0 ≈ Node ~70 MB + SQLite cache ≤32 MB ≈ ~100 MB; a P0 that has served a semantic query adds the ~120 MB query model (loaded lazily, on first semantic query only — never at startup). Two active clients: 2 × (70+32+120) = 444 MB total, each ≤ 300 MB — **C3's server budget is per-process and the docs say so.** Exactly one P1 regardless of N (conductor-owned): steady ~250 MB, monster transient ≤ 500 MB hard-kill — the pipeline budget does *not* multiply, which is the concrete payoff of election over laissez-faire (N workers would be N × 500 MB and N cores). Background ≤ ~1 nice'd core total, held by the same singleton.

### b.7 Version skew (R23) under shared files

Meta carries `schema_version` + `min_reader_version`. A server too old to read serves everything that never touches the index (the 29 tools PR #20 rescued) and answers search with typed `SCHEMA_NEWER {remedy: upgrade}` — it must **not** sideline or rewrite a file a newer sibling is actively serving. Sidelining (`.incompatible-<ts>`, never delete) is reserved for the conductor, holding the lease, on a file no reader can use. Downgrade-after-upgrade heals the same way: the old server serves degraded until the newer one (or a rebuild) restores compatibility. This replaces v1 §3.6's unconditional sideline-on-unknown-schema, which under N processes is a denial-of-service one stale install can inflict on a fresh one.

### b.8 The coverage sentence, per-library

> "Searched 4,120 of 9,313 items across 3 libraries (My Library 2,940/7,541; Climate-Group 1,102/1,600; Methods-Group 78/172 — web-backed, backing off 40 s), newest first — records complete everywhere; body text keyword-complete since 2021-06-10, semantic since 2021-09-01. Building in background (this window's conductor: pid 4711), ~35 min at idle priority. Paused: no."

All figures from counters maintained in the mutating transactions (C4); the per-library rows are the R17 vector under D4-merged, and the backoff disclosure is what keeps R26 honest during web politeness stalls.

### b.9 The soak is a gate

Extending v1 Risk 3 into the harness (R20 logic applied to R13): three P0 processes on one dataDir; full drain of the 10k corpus; 1 query/s per server; kill -9 the conductor twice mid-drain. Assert: reply p95 ≤ 1.5 s; zero SQLITE_BUSY reaching any reply; WAL ≤ 256 MB with checkpoints landing; conductor lease migrates < 30 s; ledger audit shows zero double-commits and duplicate compute ≤ 1 micro-batch per failover; every status poll's indexed set is a newest-first prefix per library (R26). Runs on every check beside the fold sweep (R19) and the RSS gate (R20).

---

## (c) INCREMENT IMPACT

- **PR #19 (accent fold) — open.** It *is* v1's PR1. Unchanged; the STOPWORDS deletion rides its follow-up, not a new lane.
- **PR #20 (corruption) — open.** Absorbs part of v1 PR4/PR8. The residue (schema version actually read; `min_reader_version`; conductor-only sideline) becomes **PR4′**, filed *after* #20 lands since they touch the same files — per SYNC, his batching means sequencing beats piling commits onto an open PR.
- **NEW PR-A [PR, small]: `busy_timeout` + short transactions.** Failing test: two `DatabaseSync` handles, one mid-build (write txn open per sqlite-index.ts:192-201), second write throws SQLITE_BUSY today. The pragma is one line; converting BEGIN-until-save to commit-per-persist-batch is ~20 lines in save()/ensureTxn. Defect-with-repro shape — the shape merged twice (#11, #12).
- **NEW PR-B [PR, small]: stop the silent cross-library wipe.** Minimal honest fix inside his current schema: a build for a library other than the one stamped refuses with a notice naming both, instead of `clearStore()` destroying the other's index (build.ts:220 → index-manager.ts:467 → sqlite-index.ts:312-313 is the repro). This is the guard, not the feature.
- **NEW ISSUE-C [issue, design-sized]: multi-library schema + second-process story.** The `lib`-column redesign and the conductor protocol are exactly #10-shaped: a documented behavior (build.ts:185-188 says keyed-by-context on purpose), a reproduction, measurements, no code he must accept. History says he builds these himself; the issue carries b.1/b.5 as the proposal.
- **SYNC §4 fulltext-delta issue (drafted FINAL): file it first.** It is the evidence base for b.2's census-intersect; b.2 depends on its answer only in degree, not in kind.
- V1's PR2, PR3, PR5–PR8 survive re-based on #19/#20; PR3 (newest-first) and PR7 (freshness) pick up the per-library watermark and census-intersect amendments. PR9–PR13 [RFC] stand, with the RFC issue now bundling ISSUE-C's protocol — one design conversation, not two.

## (d) CONFESSIONS

1. **I weakened R13 to meet it.** "No passage extracted or embedded twice" becomes "never committed twice; at most one duplicated micro-batch per conductor failover." I believe the claimed_input guard makes the embed stage's commit idempotent, but I verified the guard's *design* in v1's text, not an implementation — and a strict reading of R13 has no implementation on any single-file SQLite substrate. If the author means the letter, this design cannot deliver it and says so only in a subclause.
2. **The origin partition key is asserted, not verified.** SCOUTS says version validity is scoped by Zotero-Server-ID; I did not verify that the *local* API sends that header on every response, nor what an unsynced, never-logged-in profile reports. If it is absent there, `origins` needs a locally-fabricated profile fingerprint, which is unspecified and is exactly the kind of identity improvisation that produced the 0012 class of bug.
3. **The activity-touch yield is folklore until soaked.** Filesystem mtime granularity is 1 s on some filesystems and utimes behavior differs on network mounts; the 2 s yield window may quantize to 0–2 s of jitter, and the cross-library k-way merge's newest-first guarantee already bends under web backoff. Both are asserted testable in b.9's soak, but today I have no measurement — and this repo's own history (0011: "a few hundred MB" vs 1,848.8 MiB measured, bench/results/0011-rss/) is the standing proof of what unmeasured claims are worth here.
