# Critique — cycle-2 memo, DERIVATION & FRESHNESS lens

*Adversarial critic, 2026-08-26. Verified against `/home/user/oscardvs/zoteus` HEAD `edf2748` (v1.7.0), sheet v2 (DESIGN.md + DESIGN-DELTA.md + SCOUTS.md), DESIGN-V1.md, and `bench/results/0012-fulltext-sequence/sequences.json`.*

**Verdict in one line: the signals-vs-keys split survives every attack I mounted; the freshness half of the memo has one scope-boundary hole big enough to kill its flagship claim as stated, and its top confession is a decoy standing in front of a worse branch of the same hole.**

---

## FATAL

### F1 — "No fulltext watermark exists in the schema at all" dies at the cloud scope the memo itself defines

b.2 defines `scope_id = cloud:<userID|groupID>` for the web API, so the design claims to cover the cloud transport (upstream serves it today; D2's "hosted out" excludes the multi-tenant OAuth server, not a desktop user on a cloud API key). b.4 then makes the census the *only* fulltext freshness mechanism — "`/fulltext?since=0` — the full census, every tick, by design… There is no fulltext watermark anywhere in the schema, so the mixed-sequence trap is unwritable."

The trap the census exists to dodge is **local-only**. SCOUTS is explicit: the mixed sequence (web stamps / local client versions / 0) is a property of the *local* `/fulltext?since=` endpoint; the *web* API's fulltext versions ride the ordinary monotonic library-version sequence — a legitimate cursor. Meanwhile SCOUTS' politeness candidate binds the web transport: ≤4 concurrent, honor `Backoff` on any response, 429/`Retry-After` with exponential fallback. A full fulltext census fired at api.zotero.org **every 60-second tick, forever**, is exactly the request pattern that constraint exists to forbid, and it re-imports the R3 disease (cost ∝ library per tick, not ∝ change) on the one transport where requests are actually expensive. As stated, the design either hammers zotero.org or silently has no fulltext freshness story for a scope it names in its own schema.

The structural boast makes it worse, not better: "no watermark exists in the schema **at all**" is presented as the same unwritability move v1 used for the 0012 defect. But the unwritability argument only holds where the sequence is actually non-monotonic. Banning the watermark schema-wide converts a correct local rule into a cloud cost violation.

**Cheapest repair (cheap, and it exists):** make the no-watermark rule per-scope. Local scope: census-equality every tick, no watermark column can exist for it — the memo's design, unchanged, where the trap lives. Cloud scope: an ordinary `?since=` cursor on the monotonic web sequence, at a politeness-bounded cadence. The purity sentence becomes "no fulltext watermark exists *for any local scope*" — slightly less quotable, actually true.

---

## MAJOR

### M1 — Confession 1 is a decoy; the worse branch of the version-0 hole is the never-synced library

The confessed risk is "the sweep may be dead weight" (if local re-extraction bumps the version) or "the hour horizon is a guess." The unconfessed branch is the opposite tail. The memo sizes the sweep "at the design point (≲2k local-only attachments)" — a number asserted from nothing. The memo's own cited artifact (0012 `sequences.json`) shows 584 of 8,037 fulltext entries at version 0 (7.3%) **on a synced library**. A user who never enables Zotero sync — precisely the R10 local-by-default user this sheet privileges — plausibly has *every* entry at 0 (whether local extraction writes 0 or a local client version is exactly the unmeasured dynamic of confession 1). In that world:

- the census equality-diff is permanently blind (0 = 0 for everything), so the "bounded idle re-verify" is not a residue patch, it is **the entire freshness mechanism**;
- its cycle time is O(corpus): 10k docs / M=32 per tick ≈ 313 idle ticks ≈ 5+ hours per full pass, forever, with each verify a full text fetch + hash — the 44.9 MB dictionary re-fetched as one JSON string every cycle (and the memo never says which process eats that O(document) transient; if the P0 tick does, the 300 MB server RSS budget is breached hourly);
- R3's "cost of staying current ∝ the change, not the library" is violated in perpetuity, at zero change.

**Cheapest repair:** the memo already names the experiment — run it *first*, as confession 1 demands, but extend it to the never-synced case. If extraction stays 0 there too, the fallback with a real signal is the attachment's own **item** version (attachments are items in the item census; whether re-extraction bumps it is SYNC §4's question — one more measurement). If both signals stay flat, no cheap repair is visible: the design must then disclose a staleness horizon that scales with library size, which is an honest but ugly amendment to b.4.

### M2 — The R26 argument is self-refuting: the observable is enforced against #6012 and waived for the memo's own band-1

b.6 rejects #6012's smallest-first-within-attachments because "R26's observable is 'every poll's indexed set is a most-recent-first prefix,' and smallest-first breaks that observable by construction." Ten lines earlier, b.5 quietly waives that same observable for the memo's own design: "The record stage is where the prefix property is asserted — body text follows the two-band frontier." It must be waived, because the retained two-band K=64 cap breaks the strict prefix property by construction too: while band 1 drains, a monster's tail completes long after older, smaller items are fully indexed — the fully-indexed set is not a newest-first prefix. So either the observable binds body text (and band-1 stands convicted alongside smallest-first) or it does not (and the stated ground for rejecting smallest-first evaporates). One standard, applied twice, differently.

The *conclusion* survives — R2's own text ("coverage grows newest-first; the crawl frontier is a priority order") binds all stages and smallest-first genuinely violates first-touch recency at any granularity, while two-band preserves it at band-0 granularity. **Cheapest repair:** two sentences. State the granularity R26 is asserted at (record coverage: strict prefix; body: band-0 coverage is a newest-first prefix, band-1 is disclosed residue), and rest the smallest-first rejection on R2 plus that band-0 observable, not on the strict reading the memo's own design cannot pass.

### M3 — The "NEW small PR: D3 serve-stale" is design-sized wearing a small PR's clothes

Verified: `reconcileVectorProvenance` → `dropStaleVectors` → `clearVectors()` at open (index-manager.ts:286–308; sqlite flush override at :401) — the violation is real and live. But the proposed contained fix — "stop `clearVectors()` … and let `updateBlocker`'s embedder branch (index-manager.ts:594) trigger background re-embed instead of a rebuild demand" — cannot be contained in upstream's schema. Upstream holds **one global** `embedderId` meta key (sqlite-index.ts loadMeta/writeMeta) and no per-row embedder key. Keep the old vectors, re-embed in the background, and mid-migration the store holds vectors from two models under one identity: either the ranking mixes incomparable spaces (the "plausible nonsense" upstream's own comment at index-manager.ts:283–284 exists to prevent — a served wrong answer, worse than the drop-to-zero disease), or the PR grows per-vector provenance, dual query embedding, and per-space scoring — i.e., the memo's own b.3 table row, i.e., the RFC. The memo's b.3 machinery is right; the increment mislabels its cost.

**Cheapest repair:** rescope the small PR to what one global key can support honestly: keep vectors, label stale, **pin the query-side embedder to the stored `vectorEmbedderId`** until a rebuild switches both together. One behavior, no mixed spaces, D3's serve-stale letter honored; the dual-embed migration stays in the RFC where it belongs.

---

## MINOR

**m1 — Census arithmetic contradicts the memo's own artifact, twice.** b.4 says the census map is "tens of KB"; 0012 measures 8,037 entries → ~120–200 KB serialized. Confession 3 fears "3–5× the attachments" per item; measured is 8,037 entries against 7,541 items ≈ **1.07×**. One error optimistic, one pessimistic, both answerable from the file the memo cites. The parse-cost conclusion probably still holds — as confessed, unmeasured.

**m2 — The upstream body-geometry jab is a misread.** b.2/S3 repeats SCOUTS: "upstream's 512-char fixed stride, chunker.ts:7, sits below Zotero's own minimum." chunker.ts:7's 512 default is real but applies to **metadata** chunks (index-manager.ts:848, :418); body text chunks at `FULLTEXT_CHUNK_SIZE = 1200` chars (index-manager.ts:58, used :862) ≈ 250–300 tokens — *inside* Zotero's 120–768 token band. Not a kill: the move to token-budget structural chunking stands on the boundary-chunking ruling, not on this line. But in a memo whose genre is exact citation, a repeated-from-SCOUTS claim contradicted by a constant 790 lines from the cited one should have been caught.

**m3 — b.5's clean R27 test contradicts b.2's prefix rule.** A title edit re-embeds record passages *and* flips `embed_hash` on every headingless body chunk (marked prefix-stale, re-embedded at tail priority). So "embed:content-change = n_record_chunks, extract/segment = 0" is false for any item with headingless chunks, and `prefix-stale` is not in the cause vocabulary `{new, signal-noop, content-change, key-bump, retry, delete}`. Add the cause code; fix the test's expected counts.

**m4 — "Prefix-stale chunks keep serving" needs one missing sentence.** The queue rule ("embed_hash present with no vector row under the current embedder_key") makes a changed `embed_hash` orphan its old vector instantly; serving it requires retaining the previously-embedded hash per passage. The ledger's input_key/output_key columns already carry this pattern — say so.

**m5 — Citation slack.** `loadMeta` is at sqlite-index.ts:210–224, not "217–233" (the `libraryBackend` lines :218–219 and `SCHEMA_VERSION` :26/:153 are exact). Substance — six meta keys read, `schemaVersion` written and never read — verified. Flagged only because a misread line is this memo's own declared kill condition.

---

## SURVIVED ATTACK

- **The signals-vs-keys split**: every b.3 table row recomputed under resync, restore-both-directions, extractor upgrade, and server-ID change — holds; R11 satisfied structurally, verify cost is fetches-and-hashes only, as claimed.
- **build.ts:256** (`const since = ctx.search.buildStatus().libraryVersion`) and **index-manager.ts:686–687** (`deleteItem`/`addOneItem` per changed item): character-exact; the update/extraction-blindness finding is real — `fulltextForPage` runs only over `?since=`-changed items, so post-build extraction is invisible to `action:"update"`. SYNC §4 legitimately upgraded from question to finding.
- **The kill of V1 §2.5**: the "ascending completed-version-group sweep" is verbatim in V1, SCOUTS' mixed-sequence finding stands, and 584 measured zeros prove the loss is non-empty. The census replacement is not worse than the disease *on the local transport* (F1 is about the other transport).
- **The live D3 violation** (index-manager.ts:286–308, sqlite-index.ts:401): verified, including upstream's own rationale comment.
- **Server-ID lift point**: `Zotero-Server-ID` machinery confirmed at local-writes.ts:48/:100, confirmed absent from all of `src/features/search/`.
- **Sweep arithmetic on the measured library**: 584/32 ≈ 18 idle minutes — better than the claimed hour (the claim fails only in M1's unmeasured worst case).
- **Entry-level collapse**: item-level dedup would indeed re-flatten the dictionary into one hit against the section-unit ruling's explicit text; the amendment is compelled, not chosen.
- **Rejection of item-granularity smallest-first**: the conclusion survives on R2 — only its stated R26 ground fails (M2).

**Tally: 1 FATAL, 3 MAJOR, 5 MINOR.** The memo's code verification is the best of any document in this project — and its freshness mechanism still needed a critic, which is the point of having one.
