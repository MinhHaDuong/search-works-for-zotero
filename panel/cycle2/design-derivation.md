# Cycle 2 memo — DERIVATION & FRESHNESS lens

*Panel architect, design cycle 2, 2026-08-26. Against sheet v2 = DESIGN.md (with ratification log) + DESIGN-DELTA.md (R10–R28, C4, D1–D11 resolved) + SCOUTS.md sharpenings. Incumbent: DESIGN-V1.md ("The Settled Ledger"). Code verified at `/home/user/oscardvs/zoteus` (HEAD edf2748, v1.7.0).*

The one-sentence thesis of this memo: **version counters are signals, content hashes are keys.** V1 conflated them — its extract stage is keyed "only by the per-attachment `/fulltext?since=` counter" and its freshness tick cursors that counter — and sheet v2 (R11, the SCOUTS mixed-sequence finding, Server-ID scoping) makes both of those the shipped defect class, not a nuance.

---

## (a) VERDICTS ON V1

**§1 The skeleton (ledger frame, claim/commit leases, two planes).** SURVIVES. Nothing in R10–R28 or the rulings touches the frame; R27's work counters and R22's persistent pause actually *want* a durable ledger. The rows' key columns change (below), the table does not.

**§2.1 Storage & derivation keys.** AMEND — this is the section my lens overturns most.
- "The extract stage is keyed *only* by the per-attachment `/fulltext?since=` counter" — DEAD as the invalidation key. R11 says counter churn is not change; the counter is a *signal* that schedules a fetch-and-hash, never the key that authorizes downstream recompute. The project already shipped this exact defect once (fork bae82a7, 92.7% "changed" forever).
- "Metadata-chunk stage keyed by `item_version` + chunker key" — DEAD for the same reason: a resync that renumbers item versions on identical metadata would re-chunk and re-embed every record. R11 forbids it. Upstream today is worse still — verified: `updateIncremental` does `this.deleteItem(key); this.addOneItem(item, ...)` for every version-changed item (index-manager.ts:686–687), so *any* version bump re-embeds the whole item.
- Watermarks "with a backend label" — AMEND: SCOUTS is explicit that a local/cloud label is not enough; validity is scoped by `Zotero-Server-ID`. Verified: upstream's `libraryBackend` is only `'local'|'cloud'` (sqlite-index.ts:218–219, backend.ts:102–103) and no file under `src/features/search/` mentions the server ID at all — though `src/api/local-writes.ts:48,100` already probes `Zotero-Server-ID` for writes, so the machinery exists to lift.
- Two-column FTS (`meta_text`/`body_text`) — AMEND: the record ruling says *fields keep their identity for ranking*. Two columns still flatten title/abstract/keywords into one (upstream flattens harder: one joined string, index-manager.ts:62–66). Per-field columns, below.
- Slabs, vectors-per-embedder-key, external-content FTS, sidecar-as-derived — SURVIVE. The entry ruling makes slabs *more* valuable: a segmenter change is now CPU-only.

**§2.2 Discovery (census-seeded newest-first frontier).** SURVIVES, with the watermark re-scoped by server ID and one addition: the census-diff healing must also cover the case where *our* stamps are ahead (Zotero restored from backup under the same server ID).

**§2.3 Topology.** SURVIVES. Outside my lens; no v2 input touches it.

**§2.4 Fairness (recency-major, two-band K=64).** AMEND. The record ruling fixes the phase order v1 never had: **record passages for every item, newest first, before any body text.** The two-band body frontier survives on top of that. SCOUTS' #6012 smallest-first-within-attachments composition is explicitly REJECTED at item granularity: R26's observable is "every poll's indexed set is a most-recent-first prefix," and smallest-first breaks that observable by construction. Within one item, D6 (first-with-text) mostly dissolves the question.

**§2.5 Freshness.** DEAD as written. V1's tick runs "the `/fulltext?since=` ascending completed-version-group sweep" — that is *cursoring the mixed sequence*, the precise trap SCOUTS names: local versions are web stamps / local client versions / **0 for locally-extracted text**, so an ascending cursor permanently skips every version-0 attachment. Any design cursoring that counter silently loses locally-extracted text. Upstream, for what it's worth, does not cursor it — `createFulltextSource` always censuses `fullTextSince(0)` (fulltext-source.ts:65) — but its *update* path only fetches text for items whose **item** version moved (build.ts:256 keys the delta on `libraryVersion` alone), so newly extracted text on unchanged items is invisible to `action:"update"` (SYNC §4's open question, now answered by inspection). Replacement in (b): census-equality tick, never a cursor.

**§2.6 Failure policy.** SURVIVES. One amendment: quarantine auto-clear keys on the *content* signal chain (record hash / text hash change), not raw counter movement — otherwise a resync mass-clears quarantines and replays every poison input at once.

**§2.7 Query/ranking.** AMEND (mostly other lenses, but the entry ruling lands here): "collapsed to items before ranks are assigned" becomes "collapsed to **entries**" — the ruling says the unit of answer is the section/entry; D9 dissolved into that. Item-level dedup would re-flatten the dictionary into one hit, which the ruling rejects by name. Score per entry = MAX over its chunks (#6012 prior art). The embedder-migration dual-embed machinery SURVIVES and is now *obligatory*: D3 resolved serve-stale, and upstream verifiedly does the opposite — `reconcileVectorProvenance` calls `dropStaleVectors`, which `clearVectors()` on any embedder mismatch at load (index-manager.ts:301–308, 286–293; sqlite-index.ts:401), semantic coverage to zero at open.

**§2.8 Contract.** AMEND: add R27 work-performed counters (per stage, per cause), R22 persistent pause flag, record-vs-body coverage split, and the version-0 residue disclosure. C4 is satisfied by v1's materialized counters — keep.

**§2.9 Budgets.** SURVIVES unchanged (arithmetic unaffected by key redesign; hashes are SHA-256 over streams already in memory).

**§3.1 vectors / §3.2 CJK / §3.3 stopwords / §3.5 topology / §3.6 self-description.** SURVIVE. §3.6 amended to add the segmenter id+version to the chunker key (the entry ruling folds it there explicitly) and the server-scope rows to the meta set. §3.1 gains the R15 masking rule (below). §3.3's PR1 is now largely *shipped* as open PR #19 — see (c).

**§3.4 / §3.7.** AMEND per §2.4 / §2.8 above. The coverage sentence gains the record clause: "Records of all 7,541 items searchable; body text of 2,340…"

---

## (b) THE DESIGN — derivation graph v2

### b.1 Two kinds of stored state

Every stage row stores **signals** and **keys**, and they never mix:

- A **signal** is a Zotero version counter, scoped by server identity, only ever **equality-compared** (never `>`). A signal mismatch schedules *verification*, costing one fetch + one hash. Signals are disposable: losing them costs a re-verify pass, never a recompute.
- A **key** is `(content hash, tool identity)`. Keys authorize downstream recompute: work is stale iff stored key ≠ current key. Keys survive resync, restore, and server-ID change untouched.

R11 falls out structurally: a resync/extractor upgrade on identical bytes flips signals, the verify pass re-hashes, hashes match, nothing downstream moves. R3's "unit of invalidation is (item × stage)" refines to (object × stage) with the hash as the equality test.

### b.2 The stage table (schemas as key contracts)

**Scope.** `scope_id` = `Zotero-Server-ID` header for the local API (probed as `local-writes.ts` already does), `cloud:<userID|groupID>` for the web API. Every signal column and both watermarks are partitioned by `scope_id`; hashes and derived artifacts are not. Meta rows: `item_watermark@<scope_id>`, `no fulltext watermark exists` (deliberately — see b.4).

**S0 DISCOVER** — inputs: `?format=versions` item census; `/fulltext?since=0` attachment census. Stored per object: `(scope_id, key) → version_signal`. The item census also drives R15 deletions by subtraction (no `/deleted` locally — SCOUTS confirmed).

**S1 RECORD** — trigger: item `version_signal` mismatch → fetch item JSON. Key: `record_hash` = SHA-256 of the canonicalized, **field-tagged** record (`title:…\x1fabstract:…\x1fkeywords:…\x1fcreators:…\x1fdate:…\x1fcontainer:…`). Field tags in the hashed form mean a value migrating between fields is a change (ranking weights differ per the record ruling). Output: per-field record passages into per-field FTS columns (`title`, `abstract`, `keywords`, `creators`, `body`), weighted `bm25(fts, 8, 4, 4, 2, 1)` (weights are a starting point gated by R21's golden set, not a claim). If `record_hash` unchanged: update signal, count `signal-noop`, stop.

**S2 EXTRACT** — trigger: attachment `ft_version_signal` inequality (including 0 vs non-0 transitions). Action: streamed fetch → gzip slabs (≤1 MiB) + running SHA-256 → `text_hash`. If `text_hash` equals stored: discard slabs, update signal, count `signal-noop` — one local fetch, zero downstream work; this is R11's letter ("re-embeds nothing") honored while still verifying. If changed: replace slabs, propagate. No text: `empty` tombstone, metadata-only coverage, reason recorded (R14/D8).

**S3 SEGMENT+CHUNK** — key: `(text_hash, segmenter_id+version, chunker_id+geometry)` — the segmenter is folded into the chunker key exactly as the entry ruling directs. Output: `entries(attachment_key, seq, heading, char_span)` and `passages(entry_id, ord, text, context_prefix)`; chunk boundaries never straddle entries; geometry moves to token-budget structural chunking (SCOUTS: Zotero's 120 min / 768 max / 48 overlap; upstream's 512-**char** fixed stride, chunker.ts:7, sits below Zotero's own minimum). A chunker/segmenter upgrade is CPU-only over slabs: zero Zotero requests.

**S4 EMBED** — key per passage: `embed_hash` = SHA-256(`context_prefix + "\n" + chunk_text`) — the hash of the *actual embedded bytes*, because the ruling prepends context to embedded text. Vector rows: `(embed_hash, embedder_key) → vector`; the NULL-vector-is-the-queue idea survives as "embed_hash present with no vector row under the current embedder_key."

**Context-prefix rule (the title-edit trap).** Prefix = entry heading / outline path where the segmenter found one; item title only for record passages and headingless chunks. Consequence: a title edit re-embeds the record passages (small, honest R3) but *not* the monster's 42k entry-headed chunks. Chunks whose prefix *did* use the title are marked `prefix-stale`: they keep serving (D3's spirit), re-embed at band-1 tail priority, and the residue is disclosed in status. Zotero itself accepts an analogous residue (SCOUTS: a processor bump without a file change is deliberately not chased).

### b.3 What survives what (the decision table the lens demands)

| event | signals | hashes/artifacts | work performed |
|---|---|---|---|
| resync renumbering versions, identical bytes | all mismatch | untouched | N verify fetches + hashes; **0 chunks, 0 vectors** (R11's test) |
| extractor upgrade, identical text | ft signals move | untouched | fetch+hash per flagged attachment; 0 downstream |
| extractor upgrade, better text | ft signals move | `text_hash` changes | that attachment's chain only |
| restore Zotero from backup, same server ID | our stamps *ahead*; census exposes it | untouched | watermark reset to census version; per-object equality repair; ~0 recompute |
| restore our index from backup | stamps behind | valid | ordinary delta; hash-verify makes it ∝ real change |
| **server-ID change** (new profile/db) | all demoted to *unverified hints* | untouched | full census + verify sweep; recompute ∝ actual content difference — near zero for the same library |
| embedder change (D3) | untouched | vectors under old `embedder_key` **keep serving, labeled stale**; dual-embedded queries score each row in its own space | re-embed drains newest-first; old sidecar deleted only at zero remaining rows |
| item deleted (R15) | census subtraction | one transaction removes item, record passages, entries, slabs, passages, vectors, ledger + quarantine rows | sidecar rowids masked immediately (unreachable to any scan); bytes physically reclaimed at next compaction, forced at >10% masked or 24 h — the disclosed bound |

`dropStaleVectors` semantics (verified live at index-manager.ts:286 and its sqlite override at sqlite-index.ts:401) are dead: D3 resolved serve-stale, and the code's drop-at-open is the exact violation.

### b.4 Freshness: the census-equality tick

The reconcile tick (P0, 60 s idle cadence, backoff when unreachable) does, per tick:

1. **Items:** `?since=item_watermark@scope` — legitimate cursor; the item library-version sequence *is* monotonic per backend, and the stamp is scoped.
2. **Full text:** `/fulltext?since=0` — the **full census, every tick, by design**. One request, a key→version JSON map (measured 0..25,036 at 7.5k items — tens of KB), equality-diffed in memory against stored `ft_version_signal`s. There is no fulltext watermark anywhere in the schema, so the mixed-sequence trap is *unwritable*, the same move v1 used for the 0012 transposition defect. Cost is O(attachments) per tick in memory, not O(library) in requests, and C4 is untouched (status reads counters, never this map).
3. **Deletions:** item-census subtraction every Nth tick, disclosed as the one honestly O(library) cost.

**The version-0 residue.** A locally-extracted attachment stamps 0; if Zotero re-extracts and it *stays* 0, equality shows nothing. Bounded idle re-verify: M=32 version-0 attachments per idle tick, oldest-verified-first, fetch+hash only. At the design point (≲2k local-only attachments) every one is re-verified within ~an hour of idle ticks; the `lastVerified` horizon is reported in status. This is a disclosed residue, not a silent one.

Query path unchanged from v1: probe-don't-fix, one memoized probe, 500 ms deadline, `probedMsAgo` in replies.

### b.5 R26/R27: convergence watched, work counted

New ledger journal, materialized in the same transactions that change state (C4):

`work_counters(stage, cause, count)` with `cause ∈ {new, signal-noop, content-change, key-bump, retry, delete}` plus a small ring of `(stage, object_key, cause, at)` for the last ~200 events.

- **R27 test:** edit one title → `record:content-change=1`, `embed:content-change=n_record_chunks`, extract/segment `=0`. One edited item shows as one.
- **R11 test:** force a resync → thousands of `signal-noop`s, **zero** `content-change` downstream. The counter that once hid the 92.7% defect now *proves its absence*.
- **R26 test:** harness polls status from empty; asserts monotone coverage to 100% (D1: items, metadata-only counting) and that each poll's record-covered set is a newest-first prefix. The record stage is where the prefix property is asserted — body text follows the two-band frontier.

### b.6 Frontier composition (R2 × ruling × #6012)

Phase order: **(1)** record passages for *all* items, strictly newest-first (the ruling's "record for everyone, newest first — body text after"; also #6012's own metadata-first phase — the one part of their fairness we adopt). **(2)** body text: newest-first across items, two-band depth cap K=64 within an item (v1 §2.4 kept). #6012's smallest-first-within-attachments is **rejected at item granularity** with a reason on the record: it optimizes queue economics at the price of R26's observable, and our sheet ratified the observable. Within one item, D6 first-with-text picks the attachment; order among the rest is immaterial to any stated property.

---

## (c) INCREMENT IMPACT on v1 §4

All paths re-rooted at `/home/user/oscardvs/zoteus/src/features/search/`. SYNC.md's form rule (contained defect → PR; design-sized → issue he builds) governs.

- **v1 PR1 (tokenizer/stopwords) — superseded**: PR **#19** is open and hardened; nothing to re-send. X2 still runs, its number goes into #19's thread if asked.
- **v1 PR8's corruption half — superseded** by open PR **#20**. The recovery-verbs remainder (confirm-token `reset`, `rebuild` cost quote, `pause`/`resume` with R22's persisted flag) stays a small PR, after #20 lands so it builds on the typed error.
- **PR4 (schema check) — unchanged and now first in line**: `SCHEMA_VERSION` is verifiedly written and never read (sqlite-index.ts:26,153; `loadMeta` at 217–233 reads six meta keys, not that one). Tiny, R23's foundation.
- **NEW small PR (this lens): D3 serve-stale.** Replace `dropStaleVectors`-at-open with keep-and-label: vectors already carry `embedderId` in meta; the change is to stop `clearVectors()` in `reconcileVectorProvenance` (index-manager.ts:301–308), tag staleness in status, and let `updateBlocker`'s embedder branch (index-manager.ts:594) trigger background re-embed instead of a rebuild demand. Contained, one behavior, failing test = open a db with a different `ZOTEUS_EMBEDDING_MODEL` and watch semantic search drop to zero.
- **NEW issue (this lens): the update/extraction blindness**, upgrading SYNC §4 from question to finding: `startIndexUpdate` keys the crawl on `libraryVersion` alone (build.ts:256) and only fetches text for version-changed items, so text extracted after a build never reaches `action:"update"`; census-intersect (`/fulltext?since=0` equality-diff) is the only safe close on the local API given the mixed sequence. This is design-sized (it restructures his delta) — issue with the 0012 artifact attached, per the #10 precedent.
- **NEW small PR: Server-ID partitioning of the stamp.** Add `scope_id` beside `libraryBackend` in meta, probed the way `local-writes.ts` already does; `updateBlocker` refuses a delta across scope change. Small, merge-shaped, and it protects *his* incremental updates from the two-profiles trap, not just ours.
- **v1 PR2, PR3, PR5, PR6, PR7** survive with amendments: PR6's collapse unit becomes the entry (needs PR-sized care: entries don't exist upstream — may fold into the RFC instead); **PR7 must ship the census-equality tick, not the cursor sweep** — the one v1 increment that would have shipped the SCOUTS trap.
- **RFC (PR9–11 merged into one issue): the ledger with signal/key separation, slabs, entries, and the record-first frontier.** Sheet v2 made the key redesign load-bearing enough that sending machinery PRs piecemeal invites a half-adopted graph; per SYNC's asymmetry the RFC issue is the form that gets it built by the person who maintains it. Our PRs above are its down payment of credibility.

## (d) CONFESSIONS

1. **The version-0 re-verify sweep is a patch on an unmeasured hole.** I do not actually know whether local re-extraction keeps version 0 or bumps it — SCOUTS establishes 0 exists, not its dynamics. If re-extraction *does* bump even locally, the sweep is dead weight; if it doesn't, my hour-scale horizon is a guess at an acceptable staleness window with no user evidence. The falsifier is cheap (re-extract a local attachment, watch the census) and should run before the sweep is built — I designed machinery ahead of the measurement I'm demanding elsewhere.
2. **Field-tagged record hashing freezes canonicalization forever.** Any change to the canonical form (a new field, a delimiter fix, Unicode normalization choice) flips every `record_hash` and re-embeds every record — a self-inflicted R11 violation by key-bump, "honest" in the graph but indistinguishable from the defect to the user. I mitigate by folding a `record_canon_v` into the tool-identity side so it's at least *labeled* a key bump, but the first canonicalization bug will still cost a full record re-embed.
3. **The full fulltext census every 60 s tick is asserted cheap, not measured cheap.** Tens of KB at 7.5k items, but R8's design point is 10k docs and the census is O(attachments-with-text) — at 3–5× the attachments, with gzip off and a slow local API under load, a per-minute JSON parse on P0 could nibble the very query-path budget C4 protects. It needs a measured number (parse time at 30k entries) and a fallback cadence rule before it is a design fact rather than a design hope.
