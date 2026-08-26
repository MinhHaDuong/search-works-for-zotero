# CRITIQUE — design-query memo (cycle 2, QUERY & RANKING lens)

*Adversarial review, 2026-08-26. Every file:line citation independently re-read against
`/home/user/oscardvs/zoteus` at `edf2748`; the FTS5 sign question settled by running
`node:sqlite` directly; bench numbers re-read from `bench/results/0013-concentration/`.*

**Verdict in one line: 0 FATAL, 4 MAJOR, 5 MINOR. The memo's citation discipline is the
best I have audited in this project — every line I checked was exact — but three of its four
MAJOR holes sit inside the very mechanisms it presents as verified-and-closed, and none of
them is in the confessions.**

---

## MAJOR findings

### M1 — D5's strict semantics are defined at the wrong granularity, and the entry ruling is what breaks them

b.2's contract: "A hit must contain every phrase, every AND-ed term, and no excluded term."
b.4's ruling-driven redefinition: a hit is a **section**. But `MATCH_strict` evaluates
phrase/AND/NOT per **passage** (FTS5 row = chunk), and the ruling's own boundary-chunking
consequence means a section is *routinely* multiple chunks (FULLTEXT_CHUNK_SIZE=1200 today;
Zotero's own geometry splits paragraphs). Concrete wrong-answer state: query
`general AND equilibrium` where a dictionary entry contains "general" in its chunk 2 and
"equilibrium" in its chunk 5 but never both in one chunk → no passage satisfies the AND →
the section is excluded → the user gets b.7's message "no passage contains … 37 items match
the words separately", which is **true of passages and false of the hit unit the sheet just
ratified**. NOT has the mirror failure: a passage without the excluded term survives even
when its section contains it — the exclusion contract silently weakens from "hit contains
no excluded term" to "snippet-chunk contains no excluded term". The memo discloses the
chunk-straddling hole for the *vector* engine's phrase check and never notices the same
hole is structural in its own keyword compiler for AND and NOT.

**Cheapest repair:** decide the granularity out loud. Either (a) stipulate passage-scope
strict semantics in the contract (one sentence, matches FTS5 proximity intuition, zero
code) — honest but user-surprising; or (b) evaluate AND/NOT at section scope: issue one
MATCH per hard term, join the id-lists on `section_id` (AND = every term hits ≥1 passage of
the section; NOT = no passage of the section hits) — a few id-set operations over lists the
design already fetches. (b) is the ruling-consistent answer and costs one MATCH per hard
term, still trivially inside R6.

### M2 — the memory-backend parity claim stands on the wrong token stream

b.2 ("Verified hook: `BM25Index` retains each doc's token array, bm25.ts:44") is a correct
citation with a fatal omission: those arrays are `tokenize(text)` output, and `tokenize`
**filters stopwords and 1-char tokens** (tokenize.ts:8-10; v1 §3.3's replacement tokenizer,
which the memo endorses as SURVIVES, still drops 1-char tokens). FTS5's document
tokenization (`unicode61`, sqlite-index.ts:144-149) drops nothing. So the two backends'
phrase semantics diverge exactly where phrases contain a stopword or 1-char token:
`"war and peace"` — FTS5 requires the literal three-token sequence; the memory backend's
consecutive-subsequence check over `[war, peace]` also matches "war peace" and "war versus
peace" after their stopwords vanish. `"vitamin a deficiency"` diverges the other way. D5's
own words — "the contract for both backends" — are violated by the mechanism offered to
satisfy them. Second, smaller misread at the same seam: "since `search()` already scores
every doc (bm25.ts:68), escalation is free — the filter runs over the full ranked list, not
a pool" — false as cited: `search()` slices to topK at **bm25.ts:84** before returning, so
a post-filter applied to its result filters a pool after all. The design intent survives
only if the predicate is pushed *inside* `search()` before the slice.

**Cheapest repair:** run the phrase/AND/NOT check against a fold-only, unfiltered token
stream (re-tokenize the stored passage text with a no-stopword/no-length-filter fold — the
text is retained; the filtered arrays are a red herring), and pass the predicate into
`search()` pre-slice. Both are PR-A-internal changes; the memo's PR-A description should be
amended before anyone writes the failing test against the wrong invariant.

### M3 — the calibration block has no data source and no fallback

b.5 adopts #6012's per-model calibration (mean centering, noise floor = p99 of *unrelated
pairs*, ceiling = median of *matched pairs*, reject if matched-median ≤ null-p99) as the
scale for `frac_vec`. #6012 can compute this platform-side; zoteus cannot compute it from
nothing: **matched pairs require labeled relevant query-passage pairs per embedder, and the
memo never says where they come from**, when the (install-time?) computation runs, what it
costs, or what `frac_vec` is before calibration exists. As written, the vector half of the
adopted fusion is undefined at first run — the exact minute-zero state R4 binds. The
"reject at install" rule is similarly unexecutable without the data.

**Cheapest repair:** default `frac_vec` to list-local max-normalization (the same rule the
keyword list uses — one line), ship fraction-RRF on that, and split calibration into its
own ticket with a stated pair-generation protocol (e.g. title↔abstract of the same item as
matched pairs, cross-item as unrelated — the library itself is the corpus). Until that
ticket lands, the reject-bad-models rule is aspiration, not machinery.

### M4 — the section-diversity refetch is a hidden second 650k scan, and §2.9's SURVIVES verdict doesn't survive it

b.4 step 3: if an engine's collapsed list holds fewer than S = max(4×limit, 64) distinct
sections, "refetch its passage pool once at 4×". For the keyword engine that is one more
MATCH — fine. For the **vector engine** a refetch is a second full scan of the sidecar:
v1's own arithmetic (121 ms/100k, §3.1's 250–500 ms contiguous target at 650k) prices it at
~0.5–1 s, and the trigger is not exotic — it is precisely the dictionary-heavy query where
one item's sections dominate the top-P passages. Yet §2.9 is verdicted SURVIVES with "the
query-path additions below are id-set operations and one extra MATCH on the empty path only
— noise against the 3s budget." That sentence is false for b.4 step 3; the memo's arithmetic
missed its own design.

**Cheapest repair:** collapse **during** the scan: section score is MAX over passages, so
the scan can maintain a section-keyed top-S heap directly in its single pass (the section_id
is in the row; the heap is S entries). One pass, no refetch, and the keyword-side refetch
stays as designed. This is strictly better and deletes the pool-guarantee machinery's worst
case rather than bounding it.

---

## MINOR findings

- **m1.** b.3's constrained MATCH uses `rowid IN carray(...)` — verified unavailable in
  `node:sqlite` ("no such table: carray"; carray is an unshipped extension). `json_each`
  works (verified) and a temp table works. One-line repair, but the memo names the
  mechanism, so name a real one — and let X4 measure the one that will actually run.
- **m2.** b.6's claim that the "off by hundreds of pages" estimate error "is mostly an
  artifact of concatenation plus whole-item totals" is unsupported: the 44.9 MB dictionary
  is the single-attachment case where concatenation contributes nothing, and char→page
  density variance persists per attachment. The design stays honest only because
  `pageIsEstimate: true` is unconditional — keep that load-bearing, drop the excuse.
- **m3.** The stated invariant `frac ∈ (0,1]` is violated by the memo's own
  `frac_vec = clamp(…, 0, 1)`: below-floor vector hits get frac = 0 (contribution 0).
  Intended noise suppression, but the boundedness prose and the formula disagree; say
  `[0,1]` and note that 0 means dropped.
- **m4.** b.1's `field` enum has five values (`title|abstract|keywords|creators|note`) but
  the FTS column list has four (`title, abstract, keywords, body`); creators' column is
  unspecified, and `date`/`publicationTitle`/`bookTitle` — indexed today via `itemText()`
  (index-manager.ts:61-67, verified) — silently vanish from the record. A query for a
  journal name would regress against v1.7.0. Specify the mapping (creators+venue+date →
  body-weight or a fifth column) before ISSUE-α ships the schema.
- **m5.** §2.5's "same request count as v1's sweep at tick cadence" elides response size:
  census-intersect is `/fulltext?since=0` — the full attachment→version map, O(library)
  bytes per tick, versus v1's delta-sized response. Correctness forces it (the mixed
  sequence is real, per SCOUTS and SYNC §4), but state the cost and back the cadence off;
  don't launder it under "same request count".

---

## SURVIVED ATTACK (tried hard, could not break)

- **The sign-trap closure.** I attacked the "strictly positive" invariant with FTS5's raw
  Robertson IDF (negative for df > N/2 — plausible post-STOPWORDS-deletion with "the"/"de").
  Empirical test: 9-of-10-docs term ranks at −9.7e-7 — SQLite clamps idf at 1e-6, bm25()
  stays strictly negative, `-r.rank` strictly positive. All four seams verified
  (sqlite-index.ts:424, 443; bm25.ts:82; vector-store.ts:57 — the memo missed citing the
  fourth, which also holds). Confession 3 is stronger than the memo believes.
- **The boundedness overturn of v1's fraction-RRF rejection.** frac ∈ (0,1] ⇒ contribution
  ≤ plain RRF everywhere; single-hit list gets exactly plain RRF's rank-1 weight. I probed
  whether the bound contradicts #6012's "no longer caps at half" rationale — it doesn't:
  the benefit arrives by *relative* shrinkage of weak agreed hits (fracs 0.2/0.2 at rank 30:
  0.0044 < a lone frac-1 top hit's 0.0164). v1 §2.7's arithmetic was wrong; the memo's is
  right.
- **The R5 inversion.** Unconstrained MATCH + JS bitmap matches both the verified upstream
  shape (sqlite-index.ts:178-184) and #6012's measurement; no path post-filters a *top-k*;
  the step-3 give-up is disclosed in `scope{}`. I could not construct an undisclosed wrong
  answer, only the disclosed-incomplete one.
- **2-gram over trigram.** Decisive: a two-character query term is unrepresentable as an
  exact trigram. #6012's shipped geometry, correctly transposed.
- **The citation audit itself.** Every one of ~20 file:line claims checked out, including
  the load-bearing ones (421 OR-join, 424 negation, 61-67 itemText, 878 pool, 904-914
  itemKey dedup, 128-129/141-145 concatenation, 26/153 vs 210-224 schema-version,
  pdf-pages.ts:7, passages.ts:23-34) and the 0013 artifact (42,963/477,512 = 9.0%; next
  largest 1,450). Zero misreads. In this project's history that is rare and worth stating.
- **Section-collapse per the entry ruling, and PR6's death into ISSUE-α.** Coherent with
  the binding ruling; the residual "dictionary fills top-10 with ten legitimate entries"
  is exactly what the ruling accepts, so I record it as a consequence, not a defect.

## Confessions audit

Confession 1 (unmeasured segmenter) is genuinely the biggest single risk — everything in
b.4 and b.6 inherits it — and it is honestly stated. But the confession list is
incomplete in the memo's own lens: M1, M2, and M3 are holes of comparable size *inside
mechanisms the memo presents as verified* ("Verified hook", "adopted with the sign trap
named and closed"), and none is confessed. Confession 2 (the 20k adjective) is real and
correctly handled by X4 — extend X4 to test the mechanism that actually exists (m1).
Confession 3 is over-modest (see SURVIVED). Net: the confessions are real, not decoys, but
they are not where the amendment work is.

## Disposition

No FATAL: the memo's three headline moves — section-collapse, the R5 inversion, and the
fraction-RRF adoption — all survive attack on their core reasoning. The four MAJORs are
amendments inside b.2, b.4, and b.5, each with a named cheap repair; M1 must be settled
(granularity, out loud) before PR-A's contract is written, and M2 before its tests are.
