# CYCLE 2 — QUERY & RANKING MEMO: the answer path under sheet v2

*One architect's lens on design cycle 2. Incumbent: DESIGN-V1 ("The Settled Ledger"). Inputs: DESIGN.md as amended by the ratification log, DESIGN-DELTA.md (R10–R28, C4, D1–D11 resolved), SCOUTS.md, SYNC.md. All load-bearing code claims re-verified this session against upstream v1.7.0 at `/home/user/oscardvs/zoteus` (HEAD `edf2748`); DESIGN-V1's `/home/user/zoteus-ci/...` citations map to the same tree.*

---

## (a) VERDICTS ON V1

**§1 The skeleton (item×stage ledger, two planes).** SURVIVES, with one amendment forced by the entry ruling: the ledger's unit of *invalidation* stays (item × stage), but the chunk stage's output is now keyed by (slab hash, chunker key **including segmenter identity**) — the ruling folds the heuristic segmenter into the chunker key, so a segmenter change is an ordinary key bump, not a schema event. Nothing in sheet v2 touches the frame otherwise.

**§2.1 Storage.** AMEND, twice, both from the ratification log. (1) The two-column FTS split `meta_text`/`body_text` is DEAD: the record ruling says *fields keep their identity for ranking* — verified today that upstream flattens `[title, abstract, creators, tags, date, publication, book, note]` into one joined string (`itemText()`, index-manager.ts:61-67) chunked at fixed stride, exactly the defect the ruling names. Replacement schema in (b). (2) Passages must carry section identity and char offsets — the entry ruling makes the section the retrieval unit, and R24 needs a locator; today's schema has neither (passages: `id, item_key, title, text, source, vector` — sqlite-index.ts:130-138) and the hit contract has no locator at all (`SearchHit` = itemKey/title/snippet/score/source?, backend.ts:22-29).

**§2.2 Discovery (census-seeded newest-first frontier).** SURVIVES; not my lens; note only that SCOUTS obliges Server-ID partitioning of all stored versions (two local profiles share the "local" label and share nothing else) — v1's `libraryBackend ∈ {local, cloud}` label (backend.ts:20) is insufficient as-is.

**§2.3 Topology (two processes).** SURVIVES.

**§2.4 Fairness (two-band, K=64).** AMEND: the record ruling fixes the *phase* order above the band order — record passages for every item, newest-first, before any body text ("record for everyone, newest first — body text after"). Bands survive *within* the body-text phase. #6012's smallest-first-within-attachments is prior art that composes with newest-first; I leave the composition choice to the pipeline lens but flag that band 0 (first K passages of each item) already approximates smallest-first's goal.

**§2.5 Freshness.** AMEND on a scout finding that kills a v1 sentence: v1's "`/fulltext?since=` ascending completed-version-group sweep" cursors a counter that on the local API is a MIXED sequence (web stamps / local client versions / 0 for local extraction) — equality-comparable per item, never a monotonic cursor. Any cursoring silently loses locally-extracted text. The fix is census-intersect: `/fulltext?since=0` (one request, item→version map), equality-compare per attachment against the stored per-attachment version, re-extract on inequality. Same request count as v1's sweep at tick cadence; watermark becomes a per-attachment version map keyed by Zotero-Server-ID, not a single scalar.

**§2.6 Failure policy.** SURVIVES untouched.

**§2.7 Query path and ranking.** DEAD — this is my lens, and sheet v2 breaks all three of its pillars.
1. *"the FTS statement joins the predicate down"* — contradicted by #6012's measurement: constraining FTS5 MATCH to a rowid set makes FTS5 evaluate the expression per row, seconds at library scale. R5's "pushed into SQL" is now read as *pushed out of the top-k post-filter*, not into MATCH. Verified upstream shape: the keyword statement is an unconstrained MATCH with LIMIT (sqlite-index.ts:178-184), matching #6012's practice.
2. *"collapsed to items before ranks are assigned"* — contradicted by the entry ruling: the unit of answer is the SECTION; an encyclopedic item legitimately yields several distinct hits. Verified upstream: dedup is by `itemKey` after fusion (index-manager.ts:904-914, `seen.has(rec.itemKey)`), over a pool of `limit*3` passages (index-manager.ts:878) that the 42,963-passage dictionary can fill (bench/results/0013-concentration/uncapped-477512.json: dictionary 42,963 of 477,512 passages; next largest 1,450).
3. *"fraction-weighted RRF … deferred behind measurement (sign trap)"* — the trap is real for raw `bm25()` but is already neutralized at the verified seam: `keywordSearch` returns `-r.rank` (sqlite-index.ts:424), the memory BM25 filters to `score > 0` (bm25.ts:82), the vector scan drops `score <= 0` (sqlite-index.ts:443). All lists are higher-better and strictly positive. #6012 ships the variant; v1's remaining objection ("hands full weight to degenerate single-hit lists") is wrong arithmetic — see (b).
Also absent from v1 entirely: D5 phrase/AND/NOT semantics (verified: quoted phrases are shredded to OR'd terms — tokenize.ts:8 regex, then `terms.map(ftsTerm).join(' OR ')` sqlite-index.ts:421; the memory backend sums per-term tf, bm25.ts:68-77), R24's answer-time locator, R18's scope-aware empty result. Full replacement in (b).

**§2.8 Contract.** AMEND: hits gain a locator block (R24) and empty results gain scope coverage (R18); typed blocks, verbs, counters all survive.

**§2.9 Budgets.** SURVIVES; the query-path additions below are id-set operations and one extra MATCH on the empty path only — noise against the 3s budget.

**§3.1 Semantic path (X1 gate).** SURVIVES. Section-collapse slightly changes rerank pool composition (collapse before fusion), no arithmetic changes.

**§3.2 CJK.** AMEND: trigram → **2-gram**, on #6012's shipped geometry (dedicated FTS5 2-gram twin tables for Han/Kana/Hangul beside the unicode61 tables, boundaries via Intl.Segmenter). The decisive fact: the modal Chinese word is two characters; a trigram table cannot match a 2-char query term as an exact gram at all. Keep v1's good parts — companion table populated only for CJK-bearing passages, script-sniff query routing, typed degradation during backfill. Inherit #6012's embed-path caution: SentencePiece tokenizers are quadratic in input length; cap encode segments (~1,000 chars).

**§3.3 STOPWORDS.** SURVIVES, and is partly *landed*: PR #19 (open, hardened, head `4c4c2ef`) carries the query-tokenizer chokepoint. The STOPWORDS deletion rides that file or follows it; no new competing PR.

**§3.4/§3.5.** As §2.4 / SURVIVES.

**§3.6 Schema self-description.** AMEND small: the meta key set gains segmenter id (inside the chunker key), the per-attachment fulltext version map, Zotero-Server-ID, and the calibration block (below).

**§3.7 Coverage sentence.** AMEND to D1's ratified denominator (items, with metadata-only items counting) and R17's per-stage phrasing; structure survives.

**§4 Increment sequence.** Restructured — see (c).

---

## (b) THE DESIGN — replacement for v1 §2.7 (+ new machinery)

### b.1 Schema deltas the answer path needs

`passages` gains: `attachment_key TEXT` (NULL for record passages), `section_id TEXT NOT NULL`, `section_path TEXT`, `char_start INT`, `char_end INT`, `field TEXT` (record passages only: `title|abstract|keywords|creators|note`). `section_id = itemKey ⊕ ':' ⊕ (attachmentKey|'record'|'note:'+noteKey) ⊕ ':' ⊕ sectionOrdinal`; ordinal from the heuristic segmenter whose identity is in the chunker key. Index on `(section_id)`.

`attachments` (new small table): `attachment_key PK, item_key, total_chars INT, total_pages INT NULL, ft_version INT, server_id TEXT`. Verified gap this fixes: upstream fetches `/fulltext` per attachment and keeps only `content` (fulltext-source.ts:128-129), discarding Zotero's page/char totals, then concatenates all of an item's attachments into one string (fulltext-source.ts:141-145) — which simultaneously destroys the offset→attachment mapping R24 needs, breaks D6 (first-with-text needs per-attachment identity), and mis-scales any proportional page estimate. Extraction records totals per attachment; concatenation dies.

Record indexing (the record-is-the-core ruling): each item emits field-identified record passages (`field` set, `section_id = key:record:0`), FTS5 as separate columns `title, abstract, keywords, body` with `bm25(fts, 4.0, 2.0, 3.0, 1.0)` weights — a tag match no longer scores like a body match, and a long abstract can no longer separate tags from their title. Notes and annotations (D7: both) are their own sections, never appended to the record string.

### b.2 D5: the query contract — phrase, AND, NOT

**Grammar.** A query parses into units: `"quoted phrase"` (hard), `A AND B` (hard, explicit uppercase AND), `-term` / `NOT term` (hard exclusion), bare terms (soft, OR — today's recall-friendly default, kept deliberately: the upstream comment at sqlite-index.ts:412-416 is right that implicit AND answers far fewer queries).

**Semantics.** Hard units are *filters*; soft units are *ranking*. A hit must contain every phrase, every AND-ed term, and no excluded term. Soft terms broaden and order the survivors.

**FTS5 compilation.** Two statements, both unconstrained MATCH:
- `MATCH_strict` = `("phrase one" AND term_a) NOT excluded` — FTS5-native phrase/AND/NOT syntax; phrase strings pass through *whole* (internal spaces intact, quotes doubled) so FTS5 tokenizes them with the table's own `unicode61 remove_diacritics 2` — folding is symmetric by construction, and this path depends on PR #19's folded query tokenizer only for the soft terms.
- `MATCH_soft` = `t1 OR t2 OR …` (today's statement, unchanged).
When hard units exist: candidates = strict list; if soft terms also exist, fuse the strict and soft ranked lists, then intersect against the strict id-set in JS (id-set membership, microseconds). When no hard units: exactly today's behavior.

**Memory-backend parity.** Verified hook: `BM25Index` retains each doc's token array (`this.docs.set(id, { id, tokens, … })`, bm25.ts:44). Phrase = consecutive-subsequence check over folded tokens; AND/NOT = set membership. Applied as a post-filter over the scored candidates; since `search()` already scores every doc (bm25.ts:68), escalation is free — the filter runs over the full ranked list, not a pool. Both backends therefore honor the same contract, which D5 requires ("the contract for both backends").

**Semantic engine under hard units.** Vector candidates pass the same predicate, checked against the passage's folded, whitespace-normalized text — the phrase constraint holds over the *fused* answer, not just the keyword list. Known limit, disclosed in the contract: a phrase straddling two chunks of one section can false-negative on the vector side beyond the overlap window; the keyword side (FTS5 positional) does not have this hole for strict candidates.

### b.3 R5 corrected: where the bitmap actually applies

Filters (collection expanded recursively, tags, itemType, year, library — D4's facet) compile once per query to an allowed set at **section** granularity, materialized as a pid bitmap.

- **Vector scan:** bitmap consulted *before* the dot product, inside our own loop — genuine pushdown; a filtered scan is cheaper than an unfiltered one. (This half of v1 survives; the loop is ours, not FTS5's.)
- **Keyword:** MATCH runs **unconstrained** (the #6012-verified economics), pool `P = max(8×limit, 256)` passages, bitmap applied in JS to the returned ids. Escalation ladder when survivors < limit:
  1. one refetch at `P₂ = 4096` (one more MATCH, tens of ms);
  2. if the scope is small — `|scope passages| ≤ ~20k` — issue a *constrained* MATCH (`AND rowid IN carray(...)`). Arithmetic: #6012's "seconds" is at library scale (their per-row evaluation over ~10⁵–10⁶ rows); cost is proportional to the constraint set, so 20k rows ≈ 3% of 650k ≈ 60–150 ms if 650k costs 2–5 s. The threshold is a constant to be measured, not trusted — experiment X4 below;
  3. else stop and answer honestly via R18 (below). No path ever post-filters a *top-k*; what is post-filtered is a deliberately overfetched candidate pool, and the reply's `scope{}` block says when the ladder was exhausted.
- Plain column predicates (itemType, year) may live in SQL as WHERE on the joined content table — that is SQLite filtering MATCH *results*, which is fine; the measured trap is only the rowid constraint *inside* the FTS expression.

### b.4 Section-collapse ranking (the entry ruling; R25 recomposed)

Replaces v1's item-collapse end to end:

1. Each engine produces passage candidates (pool per b.3).
2. **Collapse per engine to sections before ranks are assigned**: section score = MAX over its passages (#6012's item-score-is-MAX, transposed to the ratified unit); best passage id retained for the snippet. A 40-passage entry takes one rank per engine.
3. If an engine's collapsed list holds fewer than `S = max(4×limit, 64)` distinct sections, refetch its passage pool once at 4× — the pool guarantee is now stated in *sections*, which is R25's crowding fix under D9-dissolved: the dictionary can occupy many slots only by matching with many genuinely distinct entries, which the ruling declares legitimate; it can no longer occupy them by passage multiplicity within one entry.
4. Fuse the two section lists (b.5). Limit applies over sections.
5. Presentation groups hits by item — an item with three matching entries renders as one item block carrying three section hits, each with its own locator. Grouping is display; ranking never re-collapses to items.

### b.5 Fusion: fraction-weighted RRF, adopted with the sign trap named and closed

Within each engine's collapsed list: `frac_i = score_i / score_max` (list-local; all scores strictly positive at the verified seam — sqlite negates `bm25()` at sqlite-index.ts:424, memory filters `> 0` at bm25.ts:82, cosine clamps `≤ 0` at sqlite-index.ts:443). Contribution `= frac_i / (60 + rank_i + 1)`; section total = sum over engines. Item relevance for display = MAX over its sections.

Why v1's two objections fail: (1) the sign trap is a property of *raw* `bm25()`, and no list crosses the seam raw — the invariant "every RankedId list is higher-better positive" becomes a unit-tested contract, not an assumption; (2) "full weight to degenerate single-hit lists" — a single-hit list gives its hit `frac = 1`, i.e. *exactly plain RRF's* rank-1 contribution; since `frac ∈ (0,1]`, fraction-weighting is bounded above by plain RRF everywhere and can only *shrink* the contribution of weak-scored deep ranks. It cannot inflate anything. #6012's rationale (a strong single-engine match no longer caps at half) plus this bound settles who is right: they are.

The vector list's fracs use the **calibration block** (new machinery, from #6012 via SCOUTS, per embedder key in meta): mean-vector centering; noise floor = p99 cosine of unrelated pairs; ceiling = median of matched pairs; model rejected at install if matched-median ≤ null-p99. `frac_vec = clamp((score − floor)/(ceiling − floor), 0, 1)` — a principled scale instead of list-max, and the reject rule keeps a bad model from indexing at all.

**Gate (D11):** the golden query set pins the answer SET; fraction-weighted ships only if Jaccard ≥ 0.9 against the plain-RRF baseline on the pinned corpus, both fusions behind one flag for the comparison. Order shifts are expected and permitted — that is exactly what D11 chose set over order for.

### b.6 R24: the citeable locator, honestly labeled

Every hit carries:
```
locator: {
  itemKey, attachmentKey?,            // which file
  section?: string,                   // entry heading / outline path — PRIMARY, per the ruling
  charStart, charEnd,                 // exact, recorded at chunk time
  pageEstimate?: int, pageIsEstimate: true,   // approxPage(charStart, att.total_chars, att.total_pages)
  page?: int                          // only when a verified exact mapping exists; never awaited
}
```
The estimate is computed **within its attachment** (b.1's per-attachment totals), not over a concatenated corpus — on the 44.9MB dictionary the proportional error that made v1's cited "off by hundreds of pages" is mostly an artifact of concatenation plus whole-item totals, and the entry heading is the primary locator anyway (the ruling's own words). Exact pages stay off the 3s path: `precise_pages` refuses > 20MB by design (pdf-pages.ts:7) so the monster never gets one; when a background pass has recorded page break offsets for an attachment, `page` appears and `pageIsEstimate` drops. The label is always truthful: D10's labeled-estimate is the default state, not the fallback.

### b.7 R18: the empty result names its scope

Only on an empty result (zero marginal cost on the happy path):
1. Coverage of the ASKED scope from the ledger: `N of M items in <scope> keyword-indexed, V semantic` — one indexed aggregate over the scope's item set. Three sentences, disjoint: "this scope is not indexed yet (0 of 947)"; "partial: 812 of 947 — the miss may be coverage"; "fully covered — nothing matches".
2. Under a strict (phrase/AND/NOT) query: one relaxed `MATCH_soft` count, reported as "no passage contains the phrase; 37 items match the words separately — drop the quotes to see them." One extra MATCH, empty path only, inside C4's spirit (counters for status; this is a query-path answer, budgeted under R6).

### b.8 CJK: 2-gram twin tables (amended v1 §3.2)

Per b-verdict §3.2: a second FTS5 table, 2-gram tokenization, rows only for passages containing Han/Kana/Hangul runs (script-sniffed at chunk time; backfilled from slabs as background work); query router sends CJK-bearing queries to both tables and fuses as a third list in b.5; typed `CJK_KEYWORD_DEGRADED` until backfill covers the scope. Non-CJK libraries pay a per-passage regex sniff and nothing else.

---

## (c) INCREMENT IMPACT on v1 §4

PR #19 (accent fold) and #20 (corruption path) are open; SYNC.md's form rule stands: contained defect → PR; design-sized → issue he implements.

- **v1 PR1** (Unicode tokenizer + STOPWORDS delete): *partially superseded by #19.* The STOPWORDS deletion becomes a follow-up commit on #19 or a one-file PR after it merges. Do not open a parallel tokenizer PR.
- **v1 PR4** (schema check + sideline-never-delete): *half landed as #20*; the never-read `SCHEMA_VERSION` (written sqlite-index.ts:26,153, compared nowhere in `loadMeta` :210-224 — re-verified) remains a tiny separate PR.
- **NEW PR-A — D5 query compiler.** One new file (parser + FTS5 compiler) + memory-backend post-filter + tests proving `"general equilibrium"` currently retrieves either-word (the failing test is the reproduction — the twice-merged shape). Sequenced after #19 so soft terms reuse the folded tokenizer.
- **NEW PR-B — fraction-weighted RRF behind a flag.** Diff is index-manager.ts:88-94 plus the seam-invariant test; body carries the boundedness argument and the golden-set Jaccard from our harness. Small and merge-shaped.
- **NEW PR-C — per-attachment fulltext.** Stop concatenating attachments and discarding totals (fulltext-source.ts:128-145): keep per-attachment segments + `totalChars`/`totalPages`. Contained, testable, and it is the load-bearing prerequisite for R24 and D6 — worth sending before any locator talk.
- **NEW ISSUE-α — section identity + fielded record + locator contract.** The schema-sized cluster (b.1, b.4, b.6): section_id columns, field-identified record passages replacing `itemText()` flattening (index-manager.ts:61-67), the locator block. This is exactly #10-shaped: a documented design decision, our measurements (0013 concentration; the dictionary-as-entries argument), no code he must accept. Expect him to build it his way; our contract survives that outcome — which is where C2 says the value must live. v1's **PR6 (item-collapse)** dies into this issue: shipping item-collapse now would be shipping the ruling's rejected framing.
- **v1 PR5** (facets/filters): survives renumbered, rewritten to b.3's honest mechanism (bitmap post-filter + ladder), and its FTS "two-column split" is replaced by the fielded columns from ISSUE-α — so PR5 sequences *after* α is answered, not before.
- **X-experiments:** X1–X3 survive. **NEW X4:** constrained-MATCH cost vs rowid-set size (1k/5k/20k/100k/650k) on the 477k corpus — turns b.3's 20k threshold from extrapolation into measurement. Half a day on the existing bench.
- Everything else in v1 §4 (PR2, PR3, PR7–PR13) is outside this lens and stands, with PR13 amended trigram→2-gram.

---

## (d) CONFESSIONS

1. **The whole ranking redesign stands on an unmeasured segmenter.** Section-collapse, section-diverse pools, and the entry-heading locator all inherit the heuristic segmenter's error rate on flat `/fulltext` text — and that rate on the actual 44.9MB dictionary is unmeasured. Over-merge collapses distinct entries back into item-dedup behavior; over-split floods results with near-duplicate hits from one entry. The `findSection` heuristic upstream (passages.ts:23-34) is a 200-line lookback regex — thin prior art. This needs its own bench ticket before ISSUE-α claims numbers.
2. **The 20k constrained-MATCH threshold is arithmetic on someone else's adjective.** "Seconds at library scale" from #6012, linearly rescaled, is the entire basis for step 2 of the filter ladder. X4 exists because I do not believe my own constant yet; until it runs, the ladder's honest description is "overfetch, then apologize."
3. **The seam invariant guarding fraction-RRF is a test, not a type.** The boundedness argument requires every RankedId list to be higher-better and strictly positive; that holds today at three verified lines (sqlite-index.ts:424,443; bm25.ts:82) and nothing but a unit test stops a future backend from returning raw negative `bm25()` and silently re-opening the exact sign trap v1 rejected the variant over. A branded score type at the `RankedId` boundary would close it structurally; I did not spend the contract-complexity budget on it.
