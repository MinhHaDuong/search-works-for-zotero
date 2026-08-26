# CRITIQUE — cycle-2 custody & lifecycle memo (adversarial)
*Critic assignment: break design-custody.md. All code re-verified against `/home/user/oscardvs/zoteus` HEAD edf2748 (v1.7.0). Every file:line the memo leans on was independently read; the verification results are at the end. Verdict counts: 1 FATAL, 5 MAJOR, 5 MINOR.*

---

## FATAL

### F1 — The census-intersect replacement (b.5) carries the same silent-loss defect it was built to kill: version 0 equals version 0.

The memo's headline kill of v1's `fulltext_watermark` rests on the scout finding that the local `/fulltext?since=` sequence is mixed — "web stamps / local client versions / **0 for local extraction**" — and its replacement compares per-attachment versions "by `≠`, never `>`", adding: "Version 0 (local extraction) is a real value that compares like any other."

That sentence is the hole. For a locally-extracted attachment the stored version is 0. When Zotero **re-extracts** it — the user replaces the PDF, Zotero re-indexes the file — the census version is **0 again**. `0 ≠ 0` is false; the equality census reports "unchanged"; the index serves the old text forever. For a non-syncing local user — the exact population the local-API design exists for — *every* attachment sits at 0, so after the first build the extract stage is structurally blind to every re-extraction for the life of the index. This is precisely "silently loses locally-extracted text", the class the memo's §2.5 verdict declares closed. The replacement is better than v1's cursor (which lost these rows too, plus more), but the memo claims the class is fixed, and it is not: the failure state — **stale text served indefinitely after local re-extraction, coverage reporting 100% current** — is constructible on the commonest local configuration.

**Cheapest repair:** widen the extract-stage key from the fulltext counter alone to `(fulltext version, attachment item md5/version)`. A file replacement bumps the attachment item's md5 and its version *in the item sequence*, which the item-side delta already sweeps — so file-driven re-extraction is caught for free. The residue (re-extraction with no file change: processor upgrade, manual reindex) stays invisible until rebuild — which is exactly the residue Zotero's own embeddings layer accepts (SCOUTS.md: "vectors stay derived from the older extraction until the file changes or the index is rebuilt"). Disclose it in the same sentence. One key column, platform-aligned, and the FATAL degrades to a documented residue.

---

## MAJOR

### M1 — Dual-embed (b.4) busts the ratified 300 MB server budget for the entire migration window, and R20 turns that into a failing gate.

b.4 requires the query path to embed with **both** models during migration ("the old model stays loadable until migration completes"), and query embedding lives in P0 at normal priority (v1 §2.3, which the memo SURVIVES). Two resident models: 2 × ~112–120 MB (v1's own honest q8 figure) ≈ 240 MB, plus Node ~70 MB, plus SQLite page cache 32–64 MB → **~340–375 MB steady**, against the ratified "server steady-state RSS ≤ ~300 MB". The migration window is not a blip: re-embedding 650k passages at nice-19 idle priority is days-to-weeks. The memo carefully bounds the *disk* cost of two generations (2 × 250 MB int8 = 500 MB — arithmetic checks out) and never mentions the *RAM* cost of two models — while its own §2.9 verdict celebrates R20 making the budgets harness gates. As designed, the design fails its own gate the first time D3 fires, which the sheet says fires with certainty (R7's default differs from today's).

**Cheapest repair:** the old model is lazy-loaded only when old-generation rows are in the candidate pool and evicted after ~60 s idle (accepting a cold-load latency spike, disclosed as a degradation), with the memo's own already-specified fallback — old-generation vectors serve via keyword-anchored fusion, labeled — as the no-RAM default when eviction pressure is on. Either keeps ≤300 MB honest.

### M2 — R13 (second process) is silently dropped by the one memo whose lens owns it, and every new mechanism the memo adds is unsafe under it.

R13 is tagged *(lifecycle)* in the ratified delta: "two zoteus on one data dir both answer, neither corrupts the index, and no passage is extracted or embedded twice" — and the delta stresses it is "not an edge case: stdio spawns one zoteus per MCP client on one fixed default dataDir." The memo — lens PRIVACY & LIFECYCLE — never mentions it. That would be a coverage gap on its own; it is worse because the memo's *new* machinery is exactly where R13 bites:

- **Sidecar compaction** (b.2 item 6) "rewrites the sidecar" — mechanics unspecified. Process A compacting in place while process B scans it shifts the rowid array under B's offsets: B silently ranks the **wrong vectors** and serves a wrong answer. Named state: *torn sidecar scan under concurrent compaction*. (Single-process it is accidentally safe — scan and compaction share P0's event loop — which is presumably why nobody noticed.)
- **Sideline-rename** (b.6 step 2): A renames `search-index.sqlite` → `.incompatible-*` while B holds an open handle. POSIX: B keeps writing to the sidelined inode — split-brain, two live indexes, B's work lost. Windows: the rename fails outright and the protocol has no branch for that.
- **purge** (VACUUM) and the JSON 30-day sweep race a second process's open transactions.

**Cheapest repair:** one dataDir-scoped advisory lock/lease file deciding a single *maintenance owner* (compaction, sideline, purge, sweep); compaction writes a temp file and atomically renames, with a generation stamp in the sidecar header that scans verify. Leases already make the ledger's double-processing half of R13 safe; the memo just has to say so and close the file-level half.

### M3 — Pause blocks deletion: the paused index serves deleted text indefinitely (R15 vs R22, uncaught).

b.3: paused gates "the reconcile tick's *write* side." b.2: the R15 deletion trigger **is** the reconcile tick's census-diff — a write. Compose them: a user pauses indexing (R22), then deletes a sensitive item in Zotero (R15); the census-diff never runs, queries are explicitly *not* gated by pause (R4), so zoteus keeps serving the deleted item's text for as long as the pause lasts — months. The memo notices and adjudicates the R1-vs-R22 tension in the user's favor and walks straight past the R15-vs-R22 collision three paragraphs away. R15's plain words ("removes its text from every stage's store") have no pause carve-out, and both requirements are privacy-lens property of *this memo*.

**Cheapest repair:** classify deletion propagation as removal, not derivation — pause halts work that *builds*, never work that *removes*. One sentence in b.3, one branch in the tick.

### M4 — The downgrade story (b.6) ignores the old binary's write path; "stale-but-correct keyword search" is only true for a binary that never writes, and v1.7.0 writes.

The additive-only mitigation claims a ≤1.7.0 binary opening a generation-2 file "finds every column it prepares against and serves stale-but-correct keyword search." Verified true for the *read* path. But the old binary also: re-stamps `schemaVersion=1` (memo concedes); and on any ordinary `build`/`refresh` runs `clearStore()` — verified `sqlite-index.ts:307–316`: delete-all on FTS, `DELETE FROM passages`, `DELETE FROM items` — knowing nothing of the ledger, slabs, facets, or tombstone bitmap. On `update` it deletes and reinserts passages with **new pids**. Either way the gen-2 tables now reference rows that no longer exist. Then the user upgrades back: the gen-2 binary reads `schemaVersion=1`, takes b.6 step 3 — "older than mine → run versioned migration steps" — and migrates a file that is *not* a v1 file but a mutated gen-2 hybrid: the ledger says items are `done` whose slabs and sidecar rows point at dead pids. Coverage now lies (the exact sin the sheet's C2 forbids: "never silently wrong"). Named state: *ping-pong downgrade desync*. Confession 3 confesses the crash-and-restamp half and calls additive-only a softener; the write-path half is worse than what was confessed.

**Cheapest repair:** the gen-2 open protocol treats `stamp==1 && gen-2 tables present` as evidence of old-binary contact — not "older, migrate" but "touched: reconcile-heal" (mark all derived stages stale, census-diff, let R1 re-earn). The old binary's re-stamp, uniquely, makes this tamper-evident — the defect becomes the detector.

### M5 — The idle-window byte-residue drain is a no-op as specified: `incremental_vacuum` requires `auto_vacuum=INCREMENTAL`, which nobody sets.

b.2 item 9 promises "the idle tick runs `wal_checkpoint(TRUNCATE)` + `PRAGMA incremental_vacuum` so residue drains within the idle window." SQLite's `incremental_vacuum` does nothing on a database whose `auto_vacuum` is `NONE` — the default, which must be set **before the first table is created** (or applied via a full VACUUM). Verified: no `auto_vacuum` pragma anywhere in upstream `src/` and none specified by the memo or v1. So the R15 byte-window bound the memo negotiates in Confession 2 ("I bounded the window") is unbounded on the free-page axis between purges; only the explicit `purge` (full VACUUM) actually works. **Repair:** one line — `PRAGMA auto_vacuum=INCREMENTAL` in `createSchema` before any table, plus a note that the migration of an existing file needs one VACUUM to activate it.

---

## MINOR

1. **The R15 grep acceptance test is blind on slabs.** Slabs are *gzipped*; `strings ... slabs | grep phrase` cannot find a phrase in deflate output whether it is present or not — the "honest version of gone" passes trivially for exactly one store. Test must decompress slabs (or assert at the slab-store API).
2. **Deletion must tombstone every live sidecar generation.** During a b.4 migration two `vectors-<key>` files exist; b.2 item 6 speaks of "the sidecar," singular. One sentence.
3. **The MATCH-unconstrained refetch loop (§2.7) is unbounded.** A 1%-selective collection filter under a common term needs ~100× pool inflation to fill limit=10; "refetching a deeper pool" inside the 3 s budget needs a cap and an honest underfill answer (R18 gives the vocabulary).
4. **The pause row dies with the file it lives in.** Sideline (b.6) or corruption recovery creates a fresh db without the `paused` meta-row → `auto_build` resumes against an explicit veto, silently. Carry the row forward, or keep pause in a one-byte sentinel file beside the db.
5. **The fulltext census fetch is O(library) per tick and the memo never prices it** — cadence unstated in b.5 (b.2's deletion census gets an explicit N=10/≤10 min bound; the same discipline is owed here, especially with the F1 repair adding hash work).

Confessions audit: all three are real but the set is a decoy in aggregate — the confessed cache-dir uncertainty (low stakes, robust fix) sits beside the unconfessed budget bust (M1) and the unconfessed R13 absence (M2). Confession 2 ("bounded the window") is actively undermined by M5.

---

## SURVIVED ATTACK

- **b.6's load-bearing defect claim** — verified letter-perfect: `createSchema` re-stamps via `INSERT OR REPLACE` (sqlite-index.ts:151–153) before `loadMeta` (:114/:118), and grep confirms `schemaVersion`/`SCHEMA_VERSION` appear only at :26 and :153 — written, never read. PR-A's premise stands.
- **b.1's custody verification** — default `local` (config.ts:115), exactly two opt-in exfiltration paths (embeddings.ts:248, :257–258), no silent fallback (:302–319), Gemini key genuinely in the URL query string (:258). All accurate; PR-C is real and cheap.
- **b.2's ten-copy census** — I hunted an eleventh copy (persistent logs: loggers write no files; request-logger strips query strings) and found none; the FTS5 delete-protocol praise matches :344–361 exactly.
- **b.4's verified drop-on-open indictment** — index-manager.ts:286–293/300–308, :889–892, flush at sqlite-index.ts:401–404 all check out.
- **b.3's citations** — `semantic-search.ts:48` auto_build-on-any-query and `index-tool.ts:21` (no pause verb, only `stop`) both verified.
- **§2.4 Phase R** — correctly implements the record-first ruling and D1-items; the smallest-first rejection is properly framed as the composition decision the scouts flagged.
- **Arithmetic** — N=10 × 60 s → ≤10 min; 2 × 250 MB = 500 MB disk; K=64 ≈ measured 63/item; 650k-bit tombstone bitmap ≈ 81 KB. All recomputed clean.
- **The R11-rides-free argument** (slab-hash keying stops counter churn before embed) — attacked, holds: R11 forbids re-*embedding*, and the hash gate stops the cascade at the fetch.
