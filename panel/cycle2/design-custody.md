# CYCLE 2 — CUSTODY & LIFECYCLE MEMO
*Design panel, cycle 2, 2026-08-26. Lens: custody of text; the index's life from install to uninstall. Upstream verified at `/home/user/oscardvs/zoteus` (HEAD edf2748 = v1.7.0). All `file:line` citations are into `src/features/search/` or `src/` of that tree unless prefixed.*

---

## (a) VERDICTS ON V1

**§1 Skeleton (the ledger, two planes).** SURVIVES. The (item × stage) ledger is exactly the machinery R15 and R22 need — a deletion or a pause is one row-state transition that every loop already consults — and R27's work-performed counters are ledger rows by construction. One note: every path v1 cites (`/home/user/zoteus-ci/...`) is dead; all claims re-verified against `oscardvs/zoteus` below, and all the ones my lens leans on held.

**§2.1 Storage.** AMEND, three ways. (1) The "backend label" on the watermarks is insufficient under the scout finding that version validity is scoped by `Zotero-Server-ID` — "two local profiles share the label and share nothing else." All versioned state is keyed by server ID (schema below). (2) The slab store and the sidecar are two new persistent copies of library text/derivatives that v1 creates and never gives a deletion path; R15 (which cycle 1 never saw) obliges the full enumeration in §b.2. (3) Upstream's migration leaves `search-index.json` in place forever as a "downgrade fallback" (sqlite-index.ts:255–257, 297–299) — a plaintext copy of the whole library that no delete ever reaches. R15 kills it; §b.2 item 10.

**§2.2 Discovery (census-seeded, newest-first).** SURVIVES. Census-diff is now *confirmed* as the only deletion route (scout: no `/deleted` on the local API), which promotes v1's "every Nth tick" subtraction from an optimization to the R15 trigger — so its cadence becomes a disclosed deletion-latency bound (§b.2).

**§2.3 Topology (two processes).** SURVIVES, with one graft from #6012's pacing prior art: the embed engine is *shut down the moment the queue drains* (scout), which is also what makes R22's paused state cost zero RSS — a paused pipeline is a worker that does not exist, not a sleeping one.

**§2.4 Fairness.** AMEND. Two sheet-v2 inputs cycle 1 never saw: the record-is-the-semantic-core ruling fixes the *phase order* (record for everyone, newest first — body text after), and #6012's own fairness is smallest-first-within-attachments, which the scouts flag as composable with newest-first but *a decision, not an assumption*. Replacement: **Phase R** — every item's record (fields keeping identity), strictly newest-first; this is D1's first 100% and it is cheap (no attachment fetch). **Phase B** — body text, v1's two-band K=64 recency-major frontier kept; smallest-first is *rejected* inside band 0 (R2 is our sheet's promise; #6012's ordering serves their UX, not our ratified one) but its effect is achieved anyway, because band 0 caps the monster at K passages. Chunk boundaries per the entry ruling: never straddling entries, context prepended.

**§2.5 Freshness.** PARTIALLY DEAD. v1's `fulltext_watermark` swept as "the `/fulltext?since=` ascending completed-version-group sweep" is broken by the sharpest scout finding: the local sequence is **mixed** (web stamps / local client versions / **0 for local extraction**) and is equality-comparable per item, *never a monotonic cursor* — any design cursoring it silently loses locally-extracted text, exactly the class of the shipped 0012 defect. Replacement in §b.5: census-intersect. The reconcile tick, probe-don't-fix, and the two-plane split all survive.

**§2.6 Failure policy.** SURVIVES. R14's terminal `empty` tombstone was already in v1; D8 leave-room is honored because the extract stage sits behind an extractor key (an OCR extractor is a new key, and #6012's `textSource:'ocr'` / `extractionDegraded` flags give the quality field a name in advance).

**§2.7 Query & ranking.** AMEND, two ways. (1) The entry ruling dissolves v1's "collapsed to items before ranks" — the unit of answer is the **section/entry**: collapse to entry, score = MAX over its chunks (also #6012's shape), an encyclopedic item legitimately yields several hits, and R25's crowding concern is dissolved (thousands of peer entries), so the limit×3 pool inflates to pool = limit×8 with entry-dedup inside it. (2) R5's "pushed into SQL" is now ruled WRONG if read as constraining MATCH: #6012 measured that a rowid-constrained MATCH costs seconds at library scale. Replacement: MATCH runs **unconstrained** with an inflated LIMIT; the allowed-entry bitmap (still compiled item/facet-side in SQL — that half of R5 stands) filters the candidate list *after* MATCH, refetching a deeper pool if the filtered survivors underfill. Bitmap-before-the-dot-product on the vector scan survives unchanged — the finding is about FTS5's evaluator, not about filtering.

**§2.8 Contract.** SURVIVES; gains a custody block and a persistent pause verb (§b.3, §b.4).

**§2.9 Budgets.** SURVIVES. R20 turns them into harness gates (asserted against the 44.9 MB dictionary every check — the repo's own 0003-said-hundreds/0011-measured-1,848 MiB history is the reason).

**§3.1 vector path / §3.3 stopwords / §3.5 topology.** SURVIVE (X1/X2 gates unchanged). **§3.2 CJK**: AMEND the v2 line from trigram to **2-gram twin tables** — #6012 ships exactly that (dedicated FTS5 2-gram tables for Han/Kana/Hangul beside unicode61, `Intl.Segmenter` boundaries), so v2 is now platform-aligned prior art, not invention; the SentencePiece-is-quadratic warning (cap encode segments ~1,000 chars) transfers to our embed tokenizer. **§3.4**: amended as §2.4 above. **§3.6 schema self-description**: AMEND — v1 specified the sideline protocol but not the *write ordering*, and upstream shows why ordering is the whole defect: see §b.6. **§3.7 coverage sentence**: SURVIVES, re-based on D1 (items, metadata-only counting) and the record phase.

**§4 increments.** AMEND throughout — PR #19 and #20 are already open and absorb/reshape the head of the sequence; see (c).

---

## (b) THE DESIGN — custody & lifecycle machinery, full replacement text

### b.1 R10 — local by default, verified, and the one honest exception

Verified: `ZOTEUS_EMBEDDINGS` defaults to `local` (config.ts:115) and the `local`/default arm builds `LocalEmbeddingProvider` on `Xenova/all-MiniLM-L6-v2` via `@huggingface/transformers` (embeddings.ts:320–334, :145). Passage text leaves the machine on exactly two code paths, both requiring an explicit env opt-in **and** an API key: `fetch('https://api.openai.com/v1/embeddings', ...)` (embeddings.ts:248) and the Gemini `batchEmbedContents` call (embeddings.ts:257–258). Query text follows the same provider at query time (index-manager.ts:884 `embedder.embed([q])`). There is no silent fallback: a missing key degrades to keyword-only with a reason (embeddings.ts:303–319), and the missing-transformers hint discloses "your library text leaves the machine" before naming the API route (embeddings.ts:120–121). So R10's *custody* clause holds today by default.

Its *zero-external-calls* clause does not, in one place: the first local embed downloads model weights from huggingface.co (the `pipeline()` call at embeddings.ts:182 passes no cache/offline option). Design:

- **The weight fetch is the sole permitted external call on the default path.** It carries no user text, it happens once, it is named in status while in flight (`degradation: MODEL_DOWNLOADING`), and its failure degrades to keyword-only — never, under any error, to an API embedder. That invariant gets a test.
- **Custody line in every status/coverage block**: `custody: "no text leaves this machine"` or `custody: "passage and query text sent to openai:text-embedding-3-small (opted in <date>)"`. One string, always present, so an agent relaying answers can quote it.
- **Consent gate** (kept from v1 §2.8): auto-build is default-on only for the local embedder; API embedders quote item count and cost and require one explicit go-ahead per index generation.
- **Hygiene**: the Gemini call puts the API key in the URL query string (embeddings.ts:258) — keys in URLs land in proxy and server logs. Move it to the `x-goog-api-key` header. One line, upstream-shaped.

### b.2 R15 — deleted means gone: the census of copies, and the path through each

Deletion trigger: census-diff on the reconcile tick (scout-confirmed as the only local deletion route). **Deletion latency is therefore a disclosed bound**: the census runs every Nth tick (N=10 at 60 s cadence → ≤ ~10 min), and a `sync` verb forces it. Every copy the cycle-2 design creates, and its path:

| # | copy | where | deletion path |
|---|------|-------|---------------|
| 1 | item + facet rows | `search-index.sqlite` | `DELETE` in the deletion transaction |
| 2 | FTS5 rows | external-content index | the delete protocol *before* the text rows go — hand back exact rowid+text (upstream does this correctly today: sqlite-index.ts:344–361; keep that discipline, it is load-bearing: a bare DELETE leaves rankable ghosts) |
| 3 | passage text rows | `passages` | `DELETE`, same transaction |
| 4 | vector blobs | `passages.vector` / vectors table | die with their rows |
| 5 | **slabs** (gzipped extracted text) | slab store | slab segments are per-attachment; the deletion transaction deletes the attachment's segments. Slabs are never shared across items, by construction, so this is a keyed delete, not a scan |
| 6 | **sidecar vectors** | `vectors-<embedderKey>.i8`, append-ordered contiguous | a delete **cannot rewrite** an append-ordered file in-place. Path: a tombstone bitmap in SQLite (`sidecar_dead(rowid)`), written in the deletion transaction; every scan consults it (one bitmap test per row, noise); **compaction** rewrites the sidecar when dead > 10% of rows or on the idle tick's weekly slot, whichever first. The masked row is search-invisible immediately; its bytes persist until compaction — disclosed, and `purge` (below) forces compaction now. The sidecar is derived (C1), so this residue is derivative data, not text — but embedding inversion is real enough that the window is bounded, not indefinite |
| 7 | **ledger rows + queue state** | ledger table | deletion transaction removes the item's stage rows; the commit guard (v1's `claimed_input`) is extended: a worker holding a lease on a deleted item **fails its commit** — the guard checks the item row still exists — so in-flight work on deleted text is discarded, never written |
| 8 | in-flight worker memory | P1 RSS | bounded by one micro-batch; cleared at the failed commit above |
| 9 | WAL + SQLite free pages | `-wal`, free list | logical deletes leave bytes. Posture: `secure_delete` stays OFF (write cost); the idle tick runs `wal_checkpoint(TRUNCATE)` + `PRAGMA incremental_vacuum` so residue drains within the idle window; the **`purge` verb** = checkpoint + `VACUUM` + sidecar compaction, for the user who wants bytes gone *now* |
| 10 | **legacy `search-index.json`** | dataDir | upstream leaves it forever as a downgrade fallback (sqlite-index.ts:255–257). R15 overrules R23 here: a plaintext library copy that deletes never reach is not a fallback, it is a leak. After the first successful post-migration save, the JSON is renamed `.migrated-<ts>` with a notice and removed by the next `purge` or 30-day idle sweep. The downgrade story it served moves to §b.6: **the rebuild is the backup** (ratified out-of-scope line 2) |

**The R15 acceptance test**: delete an item in Zotero; after the next census tick, assert zero rows/segments/bitmap-live-entries for its keys across all of 1–7, and assert a search for its distinctive phrase returns nothing in both engines. After `purge`, assert `strings search-index.sqlite* sidecar slabs | grep phrase` is empty. That last grep is the honest version of "gone."

### b.3 R22 — pause stays paused

Persisted where: **one meta row `paused = 1|0` in `search-index.sqlite`**, written synchronously by the `pause` verb, read at open *before* any scheduling decision. Semantics:

- Paused gates: worker spawn (P1 is not started — with #6012's drain-then-shutdown graft, a paused pipeline is zero processes, zero RSS); the reconcile tick's *write* side; and `auto_build` — verified today, `semantic-search.ts:48` starts a build on any query against an empty index unless `auto_build:false`, and the only stop verb cancels one job (index-tool.ts:21 — actions are `build|refresh|update|status|stop`; there is no pause). Under pause, the empty-index query answers with coverage 0 and "indexing is paused; `resume` to continue" instead of spawning work.
- Paused does **not** gate: queries (R4 — serve what exists), the read-only freshness probe (foreground, O(1)), or explicit user verbs (`build` while paused asks: "indexing is paused — resume?").
- `resume` clears the row; the ledger's frontier resumes exactly where it stood (leases expired, nothing lost).
- Stated tension, resolved in the user's favor: a library paused forever never reaches R1's 100%. R1's "without anyone asking" is subordinate to C3's "the machine belongs to the user" — coverage reports "paused since <date>" so the state is honest, and honesty is what R1's convergence promise actually protects.

### b.4 D3 — serve-stale mechanics (replacing drop-on-open)

Verified today: `reconcileVectorProvenance` → `dropStaleVectors` clears **every** vector at open on any embedder change (index-manager.ts:286–293, 301–308), committed immediately (sqlite-index.ts:401–404); a mid-query dimension mismatch does the same (index-manager.ts:889–892). D3 ratifies the opposite. Replacement:

- Vectors carry per-row `embedder_key` (v1 §2.1). On a model switch nothing is dropped; the ledger marks embed-stage rows stale; re-embedding proceeds newest-first through the normal frontier.
- Queries **dual-embed** during the window (old + new model — the old model stays loadable until migration completes); each row is scored in its own space, lists fused. Semantic coverage never dips to zero; it reports the split: "semantic: 64% current model, 36% previous (re-embedding, newest first)."
- Per-item swap is atomic: an item's old vectors are deleted in the same transaction that commits its new ones. At most **two** embedder generations exist; a third switch mid-migration drops the oldest generation with a notice (bounded storage: worst case 2× the sidecar, ~500 MB at the int8 design point — disclosed).
- If the old model cannot load (uninstalled runtime), old-generation vectors serve *labeled* via keyword-anchored fusion only — degraded, named, never silently wrong.

### b.5 Freshness without a full-text cursor (the mixed-sequence repair)

The extract stage's staleness check is **census-intersect, per item, by equality**: the tick fetches `/fulltext?since=0` as a census of `(attachmentKey → version)` (unpaginated on local, scout-confirmed no rate limits; on the web transport: ≤4 concurrent, honor `Backoff` on any response, 429/`Retry-After` — the politeness constraint is transport-scoped), and compares each stored per-attachment version by `≠`, never `>`. Version 0 (local extraction) is a real value that compares like any other. Stored state partition key: **`(Zotero-Server-ID, libraryID)`** — every watermark, per-attachment version, and census result is stored under the server ID it came from (scout: clients "should partition it by server ID"); a profile switch is detected as a different partition, answered by census-diff healing, never by trusting a number across partitions. This replaces both v1's `fulltext_watermark` cursor and its two-meta-row transposition guard — the partition key is the guard. R11 rides on this for free: an equality census over content hashes (slab hash keys the chunk stage, C1) means counter churn on identical bytes stops at the cheapest stage, never reaching embed.

### b.6 R23 — upgrade AND downgrade, with the verified defect named

The defect: `open()` runs `createSchema()` — which **unconditionally re-stamps** `meta.schemaVersion` with its own value (`INSERT OR REPLACE`, sqlite-index.ts:151–153) — *before* `loadMeta()` runs (sqlite-index.ts:114–118), and nothing ever reads the stamp (SCHEMA_VERSION written at :26, compared nowhere). So today, DOWNgrading to an older zoteus over a newer file does the worst thing available: the older binary silently overwrites the newer file's version stamp with its own, then either crashes preparing statements against columns it doesn't know, or — worse — runs, half-understanding a shape it just relabeled as its own. The evidence of skew is destroyed at the moment it matters.

Open protocol, replacing v1 §3.6's version and shaping the first custody PR:

1. Open the handle; **read `meta.schemaVersion` first**, with a raw statement, before any DDL or write. A missing meta table = version 0 (pre-versioning file).
2. Newer than mine → **sideline**: rename `search-index.sqlite` → `.incompatible-v<N>-<ts>` (plus `-wal`/`-shm`), never delete; create fresh; stamp; one notice; R1 rebuilds unattended. The rebuild is the backup.
3. Older than mine → run versioned, transactional migration steps in order; stamp only in the final step's transaction.
4. Equal → proceed; stamp is written only on *create*, never re-stamped on open.

Honesty clause: this protects **from the version that ships it forward**. Binaries ≤ v1.7.0 will still re-stamp and crash over newer files — unreachable retroactively. Mitigation for the transition: cycle-2's schema keeps every v1-schema table and column intact through the first schema generation (additive-only: new tables — ledger, slabs, facets — new meta keys), so a ≤1.7.0 binary opening a generation-2 file finds every column it prepares against and serves stale-but-correct keyword search; the sidecar and slab files are separate paths an old binary never opens. Additive-only lapses at generation 3, by which point the read-before-write check is a year old in the field.

### b.7 R28 — uninstall is `rm -rf dataDir`

Verified inventory of what lives where today: all index state lands under `defaultDataDir()` (paths.ts:5–10 — XDG/AppData/Application Support) — `search-index.json`, `search-index.sqlite` + `-wal`/`-shm` (factory.ts:20–22 puts the db beside the json). Cycle 2 adds slabs and sidecar **inside dataDir** by construction. The break R28 predicts: the local embedder's `pipeline('feature-extraction', model)` call (embeddings.ts:182) passes no cache directive, so weights land at transformers.js's default cache — which its documentation places *inside the installed package directory* (`node_modules/@huggingface/transformers/.cache`), i.e., outside dataDir, in the global npm tree for the `.mcpb` escape-hatch install the hint itself recommends (embeddings.ts:126–128). I could not verify that default on disk — the optional package is not installed in this checkout — so the fix is written to be robust to my being wrong about the default: **set the cache explicitly**. Before constructing the pipeline, set `env.cacheDir = join(dataDir, 'models')` (the transformers module is already in hand at embeddings.ts:168–178). One line plus a test asserting no writes outside dataDir during a model load. Then: uninstall = delete dataDir, gigabytes included; and `purge`+uninstall = byte-clean.

### b.8 Hosted is OUT — what that deletes

D2's ruling lets cycle 2 delete, explicitly: any per-tenant keying in the contract (the "keyed by the user" clause in factory.ts:12–14 remains upstream's, untouched); per-user consent bookkeeping beyond the single opt-in of §b.1; encryption-at-rest (killed line stands — it's the user's own library on the user's own disk); multi-tenant quota arithmetic in the C3 budgets; and the four returned privacy lines stay dead. The custody line, the consent gate, and R15/R28 are all *simpler* for it: one user, one dataDir, one answer.

---

## (c) INCREMENT IMPACT

Against v1 §4, under SYNC.md's form rules (contained defect + PR merges; design-sized ask as issue → he builds it), with #19/#20 open:

- **v1 PR1 is half-landed as open PR #19** (accent fold, hardened, head 4c4c2ef). Do not refile; the STOPWORDS deletion + full Unicode split becomes a *follow-up* small PR after #19 merges, carrying X2's number. One chokepoint file, same shape.
- **v1 PR4 splits.** The corruption half is open PR #20 (dd1605a). The schema half becomes **new PR-A: read-before-write version check + sideline protocol** (§b.6) — sqlite-index.ts `open()` only, failing test = open a `schemaVersion=99` fixture, assert not re-stamped and sidelined. Same family as #20 (both are "opening a bad file must not destroy evidence"); reference #20 in the body, don't couple the branches.
- **New tiny PRs from this lens, both merge-shaped:** **PR-B** pin `env.cacheDir` under dataDir (§b.7; one line + test + a sentence in docs/semantic-search.md); **PR-C** Gemini key to header (§b.1). Ship early — they're the cheapest custody wins and build merge history before the RFCs.
- **v1 PR7 (freshness) is rewritten** by §b.5 and *converges with the already-drafted §4 issue* (SYNC.md: "census-intersect is the only safe close on local"). File that issue as drafted — it now carries cycle-2 design authority, and it is exactly the #10-shaped input that gets him building.
- **Retiring the migrated JSON (§b.2 item 10) is an issue, not a PR** — it reverses his documented left-in-place decision (sqlite-index.ts:255–257); a patch reversing a documented decision unannounced is a patch that sits. The R15 argument is the body.
- **v1 PR8 (verbs) gains `pause`/`resume`-persisted and `purge`** (§b.2, §b.3); the pause meta-row + auto_build gate is small enough to land *before* the ledger RFC and is the piece users feel first.
- **v1 PR9–13 (RFCs) stand**, amended: PR9's ledger carries the deletion-transaction contract and the commit-guard-on-deleted-item; PR11 (worker) carries drain-then-shutdown; PR12 (sidecar) carries the tombstone bitmap + compaction; PR6's collapse unit becomes the entry, and its MATCH-unconstrained candidate flow replaces the joined-predicate wording before anyone benchmarks the wrong thing.

Revised head of the sequence: #19 → #20 → PR-B → PR-C → PR-A → tokenizer follow-up → freshness issue + JSON-retirement issue → v1 PR2/3/5/6 (amended) → pause PR → RFCs.

---

## (d) CONFESSIONS

1. **The transformers cache claim is documentation-cited, not disk-verified.** The optional package isn't installed in this checkout, so "weights land outside dataDir today" rests on transformers.js's documented default, not an observed write. The fix (pin `env.cacheDir`) is correct regardless — but if the default already lands somewhere benign, PR-B's urgency claim overstates, and I've spent credibility on it.
2. **"Deleted means gone" is eventual at the byte level, and I chose the cheap default.** Between the deletion transaction and the next checkpoint/compaction, deleted text persists in the WAL, SQLite free pages, and sidecar tombstone rows. I bounded the window and gave `purge` — but `secure_delete` stays off by my call, and a reader of R15's plain words ("removes its text from every stage's store") could fairly say the requirement means bytes, now, always, and that I've negotiated it down to a disclosed window.
3. **Downgrade protection cannot reach the binaries that most need it.** Every zoteus ≤ v1.7.0 in the field will re-stamp or crash over a cycle-2 file; my additive-only generation-2 schema softens this to "stale but serving" for one generation only, and the real answer — sideline + rebuild — costs a full re-crawl and re-embed that a user will experience as their index being eaten. I am calling "the rebuild is the backup" a design principle when, for the downgrade case, it is also the least-bad apology available.
