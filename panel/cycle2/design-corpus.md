# DESIGN CYCLE 2 — CORPUS & THE ENTRY RULING
*Architect memo, 2026-08-26. Lens: what gets indexed, and in what unit. Against sheet v2 = DESIGN.md (R1–R9, C1–C3, the four rulings in the ratification log) + DESIGN-DELTA.md (R10–R28, C4, D1–D11 resolved) + SCOUTS.md sharpenings. Upstream verified at /home/user/oscardvs/zoteus @ edf2748 (v1.7.0). All file:line citations below were re-read this session.*

## Ground truth verified up front

The corpus-shaped facts of v1.7.0, checked against the tree:

- The record is flattened today: `itemText()` joins `[title, abstractNote, creators, tags, date, publicationTitle, bookTitle, note]` with `'. '` into one string (`index-manager.ts:61-67`), then chunks it at a fixed 512-char/64-overlap stride (`index-manager.ts:848` → `chunker.ts:7`). The record ruling condemns exactly this.
- Body text is a per-item blob: `fulltext-source.ts` concatenates **all** attachments' text with `'\n\n'` (`:124-145`), silently truncated at `DEFAULT_FULLTEXT_MAX_CHARS = 40_000` chars (`:10`, sliced at `:141`) — the 44.9 MB Palgrave is cut to ~13 pages today, an R9 violation live in the release. Chunking is char-stride 1200/150 (`index-manager.ts:58-59,862`) over that blob, so chunks straddle attachment boundaries, never mind entry boundaries.
- An unreadable attachment is skipped and logged once (`fulltext-source.ts:131-137`) — re-encountered forever, no terminal state: the R14 evidence line, confirmed.
- Builds crawl `top: true` only (`build.ts:214,260`) — notes and annotations invisible: the R16 evidence line, confirmed.
- The FTS table is a **single** `text` column, external-content over `passages` (`sqlite-index.ts:144-149`); dedup is by `itemKey` after fusion over a `limit*3` pool (`index-manager.ts:878,906`); the hit contract is `{itemKey, title, snippet, score, source?}` (`backend.ts:22-29`) — no section, no locator.
- One fact that *helps*: upstream's keyword statement already runs `MATCH` **unconstrained** with `ORDER BY rank LIMIT ?` (`sqlite-index.ts:178-184`) — accidentally on the right side of the scout's R5 finding. V1's plan to "join the predicate down" into the FTS statement would have been a regression.

---

## (a) VERDICTS ON V1

**§1 The skeleton (ledger, leases, two planes).** SURVIVES. Nothing in the rulings, delta, or scouts touches the (item × stage) ledger frame; R13/R22/R27 in fact strengthen it (leases answer R13's second process; the ledger's counters are R27's instrument). Out of my lens beyond that.

**§2.1 Storage.** AMEND, in four places, three of them fatal under sheet v2.
1. *The two-column FTS (`meta_text`/`body_text`, bm25 2:1) is DEAD.* The record ruling says fields keep their identity for ranking; a `meta_text` column re-flattens title, abstract, and tags into one bag where a tag match scores like a title match — the exact defect the ruling names, one join coarser. And D5 (phrase) is violated at every field seam: with fields joined by `'. '`, the quoted phrase `"smith climate"` can match creator *Smith* + tag *climate* across the join. Replacement in (b): per-field record columns.
2. *Byte-sliced slabs are AMENDED.* v1 cuts ≤1 MiB gzip slabs while streaming and chunks "slab-at-a-time with an overlap tail" — chunk boundaries are then slab-boundary artifacts and can straddle entries, which the third ruling forbids. Slabs survive but become entry-aligned (b).
3. *Stored passage text is AMENDED toward #6012's references.* v1 stores body text twice: in the `passages` content table (FTS external-content requires it in v1's schema) *and* in slabs. Sheet v2's R15 (delete from every store) and the disk budget both prefer one copy. But #6012's re-derive-from-pack does **not** transplant whole: their source is a local random-access pack they own; ours over the local API is Zotero itself, and a snippet that needs a `/fulltext` GET stalls when Zotero is closed — violating serve-anytime (R4/D3) at display time. The answer is the hybrid in (b): *our slabs are the pack*. Store references into our own slab store; re-derive snippets locally; keep #6012's fingerprint-verify ("null text rather than the wrong words"). Re-derive never touches Zotero.
4. *The extract key is DEAD as written.* v1 keys extraction "only by the per-attachment `/fulltext?since=` counter" and §2.5 sweeps it as an "ascending completed-version-group" — but the scout finding is that this sequence is **mixed** (web stamps / local client versions / 0 for local extraction), equality-comparable per item and *never* a monotonic cursor. Any ascending sweep silently loses locally-extracted text (version 0). Replacement: census-intersect with per-key equality, partitioned by `Zotero-Server-ID` (b).

**§2.2 Discovery.** SURVIVES, with two riders: the census/watermark state is partitioned by `Zotero-Server-ID` (scout: two local profiles share the "local" label and share nothing else), and the crawl gains a notes+annotations pass (R16/D7) that v1 lacks entirely — `top:true` is verified at `build.ts:214,260`.

**§2.3 Topology.** SURVIVES (out of lens), except the monster-streaming detail inherits §2.1's fix: the segmenter runs *inside* the streaming pass, and slab cuts land on entry boundaries, not byte counts.

**§2.4 Fairness (recency-major, K=64 band).** AMEND. The record ruling fixes a phase order v1 never had: **records for everyone, newest-first, before any body text** — D1's first 100% is record coverage. v1's band-0 ("first 64 passages of every item") mixes record and body passages in one frontier. The band machinery survives but moves entirely into the body phase, and the sheet's newest-first is retained *against* #6012's smallest-first-within-attachments — a deliberate, now-documented divergence (scout says the composition is a design decision; I decide it: R2 is the ratified user meaning, and the band cap already does the fairness work smallest-first does for them).

**§2.5 Freshness.** AMEND: the tick's clock-driven sweep of both sequences survives, but the fulltext half becomes census-intersect equality (see §2.1 item 4). This is the one place v1 would have shipped the 0012 defect's mirror image.

**§2.6 Failure policy.** SURVIVES, plus one distinction it blurred: R14's **terminal states are not failures**. `no-text` is a *done* state (covered, metadata-only, reason recorded), not a quarantine; it sits in the coverage denominator (D1: items, metadata-only counts), and D8's leave-room means it auto-clears when the extractor identity in the key changes (an OCR extractor someday) — same mechanism as quarantine auto-clear, different bookkeeping and different sentence to the user.

**§2.7 Query & ranking.** AMEND, twice. (1) *Collapse-to-item is DEAD*: the unit of answer is the section/entry. Dedup collapses passages to **entries**; an encyclopedic item legitimately yields several distinct hits (the ruling's own words; D9 dissolved). Entry score = MAX over its chunks (#6012 prior art), item grouping is presentation. (2) *"The FTS statement joins the predicate down" is DEAD*: the scout finding (constraining MATCH to a rowid set makes FTS5 evaluate per-row, seconds at library scale) and upstream's own unconstrained `MATCH … LIMIT` (`sqlite-index.ts:178-184`) both say: run MATCH unconstrained with an enlarged pool, filter against the allowed-pid bitmap in JS. R5's "pushed into SQL" binds the *facet resolution* (SQL builds the bitmap), not the MATCH.

**§2.8 Contract.** AMEND: hits carry entry identity and a locator (b); coverage counts per D1; R24's labeled-estimate page joins the hit shape. The verbs and typed blocks survive.

**§2.9 Budgets.** AMEND the disk line: dropping the duplicated body text (§2.1 item 3) takes v1's ~2.3 GB to ~1.7 GB (arithmetic in b).

**§3.1 semantic path, §3.2 CJK, §3.3 STOPWORDS.** SURVIVE (out of lens). One note: #6012's CJK prior art is 2-gram twin tables, not trigram — worth checking before v1's PR13 is written. §3.3's tokenizer fix is already substantially landed as open PR #19.

**§3.4–3.7.** As amended above (§3.4 by the phase order; §3.7's coverage sentence gains the record/body split and the R14 count).

---

## (b) THE DESIGN — replacement text

### B1. The corpus model: record → own-words → body, entries throughout

Three corpus classes, indexed in this phase order, each 100%-complete before the next starts consuming the embedder (extraction/chunking may run ahead; embedding priority is strictly phased):

**Phase A — records** (the ruling: "indexed before any body text, for everyone"). One record per item, fields kept apart. Cost arithmetic: a record (title + abstract + keywords + creators) is almost always ≤ 768 tokens → 1–2 chunks; 10k items ≈ ~12–15k record chunks. At an assumed 25 passages/s on one nice'd core (local e5-small q8; assumption, labeled), phase A ≈ **8–10 minutes** — D1's first 100% arrives while body extraction is still crawling. Newest-first by `dateAdded`.

**Phase A′ — own words** (R16/D7 both). Notes and annotations: small, the user's own text, semantically dense. Crawled as child items (drop `top:true` in a second pass; annotations via the local API's annotation items, colors/comments included). Each note is one **entry** of its parent item (heading = note title or first line, HTML stripped); each annotation is one passage with a page locator, grouped under an entry per attachment. Newest-first.

**Phase B — body text**, entry-segmented, band-capped (B4).

### B2. The entry layer: schema

The unit of answer, storage, and dedup is the entry. New tables (schema v2):

```
entries(eid INTEGER PK, item_key TEXT, attachment_key TEXT,
        ordinal INT,             -- position within the attachment
        heading TEXT,            -- '' when synthetic
        path TEXT,               -- outline path 'Part I › Ch. 3' when detectable
        kind TEXT,               -- record | note | annotation | body | synthetic
        char_start INT, char_end INT,   -- span in the attachment's extracted text
        page_est INT, page_est_kind TEXT, -- 'exact'|'estimate' (D10: labeled-estimate)
        seg_confidence REAL)
slabs(sid INTEGER PK, attachment_key TEXT, first_eid INT, last_eid INT,
      char_start INT, char_end INT, bytes BLOB /* gzip */, content_hash TEXT)
passages(pid INTEGER PK, eid INT, item_key TEXT,
         sid INT, off_start INT, off_end INT,   -- reference, not text
         fp TEXT /* 8-hex fingerprint of the slice */)
```

**Passages store references, not text** (#6012's discipline, re-based onto our own slab store so re-derive never needs Zotero). Snippet render: gunzip one ≤1 MiB slab (milliseconds), slice, verify `fp`; on mismatch, null the snippet and mark the chain stale — never the wrong words. FTS becomes contentless (`content=''`, `contentless_delete=1`, requires SQLite ≥ 3.43 — probed at open; fallback is v1's external-content layout with text retained, chosen once and recorded in meta). R15 delete = one transaction over `entries`/`slabs`/`passages`/vectors/FTS, single text copy to purge.

Disk arithmetic at the design point (650k passages × ~1,050 chars ≈ 680 MB raw body text): v1 = FTS index (~0.5 GB) + passages text (~0.68 GB) + gzip slabs (~0.23 GB at 3:1) + vectors sidecar (0.25 GB) + metadata ≈ 2.3 GB (v1 §2.9's own figure). Removing the duplicated passages text: **≈ 1.6–1.7 GB**. The ~0.65 GB saved is the price v1 was paying to have FTS external-content and slabs both hold the bytes.

### B3. FTS schema: field identity and phrase semantics

One FTS5 table, per-field columns, all `unicode61 remove_diacritics 2`:

```
fts(title, abstract, creators, tags, pub, ctx, own, body,
    content='', contentless_delete=1)
```

- **Record rows** (one per item): `title/abstract/creators/tags/pub` filled, others empty. Fields are separate columns, so bm25 column weights rank a title hit above a tag hit — proposed weights `title 4, abstract 2, creators 2, tags 1.5, pub 1, ctx 1, own 2, body 1`, tuned against R21's golden set, not asserted. A phrase can never match across a field seam, because the seam is a column boundary: D5 satisfied structurally, not by escaping.
- **Body rows** (one per chunk): `body` = chunk text; `ctx` = heading path + item title. The context lives in its own column so heading terms don't pollute `body`'s df or phrase positions, yet still match (weighted) — and the *embedded* text is `«item title» › «heading path» ¶ «chunk text»` with the prefix charged to the token budget, exactly Zotero's prior art.
- **Own-words rows**: `own` column.
- Phrases within `body`: chunks overlap 48 tokens (B4), so any phrase ≤ 48 tokens survives a chunk boundary inside an entry; a phrase can never match across an entry boundary — which is correct, because text straddling two entries is not real text of either. The ruling gives us the right failure mode for free.

Filters: SQL resolves facets into an allowed-pid bitmap; `MATCH` runs **unconstrained** with pool enlarged when a filter is active; the bitmap filters the candidate stream in JS (scout's R5 correction; upstream already does the unconstrained half at `sqlite-index.ts:178-184`).

### B4. The heuristic segmenter (new machinery; the chunker key grows)

Input is flat `/fulltext` text — no structure served. The segmenter, `seg/1`, runs streaming over one attachment's text:

1. **Line reconstruction**: split on newlines preserved by extraction; classify lines.
2. **Heading candidates**: short lines (≤ 80 chars), no terminal `.;,`, and any of: numbering patterns (`1.`, `1.2`, `IV.`, `Chapter|Part|Appendix|§`), ALL-CAPS or Title Case with ≥ 60% capitalized tokens, or — the dictionary pattern that matters for Palgrave — a short line followed by a paragraph block, *recurring at similar intervals* (headword rhythm: median gap and MAD over candidate spacing; accept the rhythm when MAD/median < 0.5).
3. **Entry cut** at accepted headings; `heading` = the line, `path` = stack of numbered ancestors when the numbering nests.
4. **Confidence**: fraction of text inside rhythm- or number-confirmed entries. Below 0.5, fall back to **synthetic entries** of ~6k tokens cut at paragraph boundaries, `kind='synthetic'`, `heading=''`, locator = char-offset + estimated page — labeled, per D10.

Chunking *within* an entry only, by **tokens on structural boundaries** — Zotero's geometry adopted verbatim: 120 min / 768 max / 48 overlap, overlap only within a split paragraph, never across entries (SCOUTS: "splitting text into fragments inflates the score without adding information" — upstream's 512-**char** metadata stride sits below Zotero's 120-token *minimum*). Palgrave arithmetic: 44.9 MB / ~1,850 entries ≈ 24 KB ≈ 6k tokens/entry ≈ 8–9 chunks — the monster becomes ~1,850 first-class peers, which is the entry ruling's whole point.

**Keys** (R3/R11 at this layer): chunker key = `(seg/1, tok/<model-tokenizer>, 120-768-48, ctx/1)`. Vectors are **content-addressed**: keyed `(chunk_content_hash, embedder_key)`. So a segmenter bump re-chunks (CPU-only, from slabs — no Zotero traffic), but every chunk whose bytes are reproduced re-embeds **nothing** — R11 honored at the expensive stage even across heuristic churn. Slabs are cut at entry boundaries (`first_eid..last_eid`); an entry larger than 1 MiB spans slabs (the reference tuple `(sid, off)` doesn't care).

### B5. Twin attachments (D6 first-with-text) and terminal states (R14/D8)

Upstream concatenates every attachment (`fulltext-source.ts:124-145`). Under D6, per item exactly one attachment is indexed for body text: the **first that has text**, where *first* is deterministic — ascending `dateAdded`, tie-break attachment key — and *has text* is decided by presence in the `/fulltext` census. "Same text" is **not detected**: first-with-text is positional, not similarity-based. We store `content_hash` per candidate attachment anyway, purely for the report: the skipped attachment's line says "identical text, suppressed (D6)" or "different text, not indexed under first-with-text" — honesty without reopening the decision. If a later extraction gives an *earlier* attachment text, the choice function's output changes, the extract key changes, and the chain re-derives — convergent by construction.

R14 terminal states, distinct from quarantine: `no-attachment`, `no-text` (in census with version but empty content, or absent while siblings are present), `unsupported-type`. All are **done**: the item counts covered as metadata-only (D1: items + metadata-only count), the reason is stored on the entry-less item row, and the coverage sentence carries the count. D8 leave-room: the extract key includes the extractor identity (today: `zotero-fulltext/<census-version>@<server-id>`); a future OCR path is a new extractor id, and every `no-text` tombstone whose key predates it re-enters the frontier automatically — terminal today, not forever.

### B6. Extraction freshness: census-intersect, server-partitioned

The mixed-sequence scout finding kills any cursor. The tick's fulltext half: one `/fulltext?since=0` census per tick (one request, key→version map — the same call upstream already makes per build, `fulltext-source.ts:65`), then per-key **equality** against stored `(attachment_key → version)` under the current `Zotero-Server-ID`; changed or new keys enqueue extract. All watermarks, censuses, and extract keys are rows in a `server_partitions`-scoped namespace; a different server ID is a different world (scout: "clients should partition by server ID") — profile switches can't cross-contaminate, and version 0 (local extraction) is just a value that either equals the stored one or doesn't.

### B7. Query path: entry collapse, grouped answers

Both engines return passage candidates (pool = `limit × 6`, doubled from upstream's ×3 at `index-manager.ts:878` because collapse now happens at two levels). Collapse: passage → **entry** (entry score = MAX over its chunks, #6012's fusion note), fuse per engine at entry level, RRF k=60. The answer page lists entries; entries of one item are visually grouped under it, each hit shaped:

```
{ itemKey, title, entry: { heading, path, kind, ordinal },
  attachmentKey, locator: { page, pageKind: 'exact'|'estimate', charStart },
  snippet, score }
```

No per-item cap in the pool or the page (D9 dissolved; ranking decides), but the concentration disclosure survives: status reports the top item's entry share. R18: an empty result names whether the queried scope has entry coverage. R24: `page` is the estimate `char_start/total_chars × page_count` labeled `estimate` until an exact source exists — and the estimate is now per-*entry*, which shrinks its error from "hundreds of pages over the whole dictionary" to the span of one 24 KB entry.

---

## (c) INCREMENT IMPACT on v1 §4

Already open: **PR #19** (accent fold) subsumes most of v1's PR1 (Unicode tokenizer; the stopword deletion rides it or follows as a one-liner). **PR #20** (corruption path) covers the corruption half of v1's PR4/PR8. Neither is disturbed by this memo.

Resequenced under SYNC.md's form rules (small defect + PR = merged; design-sized = issue he builds):

- **PR-a (small)** — first-with-text + per-attachment skip reasons: `fulltext-source.ts` stops concatenating (`:124-145`), picks the deterministic first, records reasons. ~40 lines + tests; defect-shaped (the 0013 idf evidence is the body).
- **PR-b (small)** — R14 terminal recording: the log-once at `fulltext-source.ts:131-137` becomes a stored reason surfaced by `statusSummary` (`build.ts:135-163`); metadata-only counts enter the status. Merge-shaped.
- **PR-c (small)** — notes+annotations crawl behind `ZOTEUS_INDEX_NOTES` (default on): a second non-`top` pass in `build.ts`. Contained; cite #6012's eligibility as precedent.
- **PR-d (small)** — read back `schemaVersion` (written-never-read, `sqlite-index.ts:26,153`): v1's PR4, unchanged.
- **Issue-1** — the 40k cap vs R9: `DEFAULT_FULLTEXT_MAX_CHARS=40_000` truncates the living example 1000-fold; attach 0013's concentration JSON. Design-sized (streaming): #10's history says he builds it.
- **Issue-2** — the mixed-sequence/census-intersect question: already drafted per SYNC §4; this memo's B6 is its design annex.
- **RFC/fork-first** — v1's PR9 (ledger) unchanged; v1's PR5+PR10 merge into one **entries schema** RFC (record columns per B3, entry layer + slab references per B2, segmenter per B4) — one re-index event, because the FTS shape, the passage shape, and the slab shape all change together and users must not re-embed twice. Content-addressed vectors (B4) make even that re-index embed-cheap for unchanged chunks.

---

## (d) CONFESSIONS

**1. The segmenter is unmeasured.** The headword-rhythm heuristic (B4) has never touched the Palgrave text; its failure mode is *silent plausible-looking entries* — wrong headings become wrong citeable locators and wrong dedup units, which is worse than honest synthetic entries. The confidence gate is a guess (0.5) with no ROC behind it. Cheapest falsifier: run `seg/1` over the 44.9 MB extraction and hand-check 50 random cut points before the entries RFC is written.

**2. The contentless-FTS/reference-passage path doubles the storage code.** `contentless_delete` needs SQLite ≥ 3.43, so the open-time probe keeps v1's external-content layout alive as a fallback — two snippet paths, two delete protocols, and a per-hit gunzip whose latency I have asserted ("milliseconds") but not measured at answer-page fan-out (10 hits × possibly 10 distinct slabs, cold page cache).

**3. Entry-collapse breaks the golden set's comparability.** D11 pins the answer SET, but the pinned sets predate the entry ruling and are item-denominated; entry-level answers are a different type. The bridge (compare item-projections of entry answers) weakens exactly the regression class the ruling creates — two hits from one item swapping which *entry* surfaces is invisible to an item-projected Jaccard. The golden set needs re-pinning at entry granularity, which is manual work this memo schedules but cannot do.
