# REQUIREMENTS — what the system promises, consolidated

*The user-requirements memo: R1–R28 in their current form, with the ratified
decisions applied and the rulings folded in. Consolidated 2026-08-26 from the
ratified sheet and its delta (superseded, in git history); the rulings
themselves are recorded in DECISIONS.md, which is the authority on what was
ratified. This memo is the readable current statement. Any line here remains
vetoable by the author on later reading — a veto lands in DECISIONS.md first,
then this memo follows. Constraints live in CONSTRAINTS.md; the design that
honors all of this is DESIGN.md.*

## The three rulings that shape everything

1. **The unit of answer is the entry.** The monster document is encyclopedic —
   a collection of entries — so retrieval and dedup work on the **section**,
   not the Zotero item. An encyclopedic item may legitimately yield several
   distinct hits; a focused article yields one. The citeable locator is the
   entry heading where one is known.
2. **The record is the semantic core.** Title, abstract, and keywords are the
   key semantic targets: every item's record is indexed before any body text,
   fields keep their identity for ranking (a tag match must not score like a
   title match), and notes, annotations and body text extend the core, never
   dilute it.
3. **Chunking respects entry boundaries; context is prepended.** Chunk
   boundaries align to section/entry boundaries where structure is detectable —
   never straddling two entries — and each chunk's embedded text is prefixed
   with its context (entry heading / outline path / item title).

## Requirements

Each stated as the testable property the harness or a reader can check.

**Coverage and convergence**

- **R1 — eventually all the lib is indexed.** With no further edits, coverage
  reaches 100% without anyone asking; no state needs a manual rebuild.
- **R2 — most recent first.** Coverage grows newest-first; the crawl frontier
  is a priority order, not a page cursor. (Recency orders *coverage*, not
  answers — see out-of-scope.)
- **R4 — something partial is better than nothing.** The index serves at every
  moment of its life, first build included — which obliges honest coverage
  reporting, or partial is indistinguishable from complete.
- **R14 — no text is a terminal state.** An attachment that yields none is
  *done*, not retried forever: counted covered as metadata-only, reason
  recorded, coverage report says so. (D8: OCR is out today, but the stage keys
  leave room for a future extractor.)
- **R17 — coverage in one sentence.** "How much of my library is searchable?"
  gets a human answer: N of M **items** (D1), per stage, most-recent-covered
  date. Metadata-only items count toward the denominator, with their reason.
- **R26 — convergence is watched, not trusted.** From empty, touching nothing
  but status, the harness sees 100% arrive unattended, and every poll's indexed
  set is a most-recent-first prefix. (The granularity at which prefix-ness is
  asserted is a design reading — DESIGN.md §2.3 — flagged for author veto.)

**Change and cost**

- **R3 — avoid unnecessary rebuild.** Cost of staying current ∝ the change,
  not the library; recompute exactly what is downstream of a changed input —
  the unit of invalidation is (item × stage).
- **R11 — counter churn is not change.** A resync or extractor upgrade that
  advances versions on identical bytes re-embeds nothing whose content is
  unchanged. (The 92.7%-changed-forever defect this project itself shipped is
  the cautionary artifact.)
- **R27 — edit one, count one.** Every stage reports what it processed and
  which input triggered it; one edited item shows as one.

**Corpus**

- **R8 — 10k docs is not much.** Design point ≥ 10k docs with full text; known
  red zone: the vector full scan near 1 s there.
- **R9 — 15k-page docs are included.** Monster documents are first-class input,
  not an outlier to cap away (the 44.9 MB dictionary is the living example).
  Under ruling 1 they are collections of entries among peers.
- **R16 — my own words.** Notes *and* annotations are in the corpus (D7), not
  just papers.
- **D6 (shape of the corpus) — twin attachments resolve first-with-text.** Per
  item, one attachment is indexed for body text; skipped ones get a recorded
  reason.

**Query**

- **R5 — filters are good to have.** Collection / tag / itemType / date scoping
  enforced before any answer is truncated — never post-filtering a top-k that
  claims completeness. *Scout correction applied:* "pushed into SQL" must not
  be read as constraining FTS5 MATCH itself (measured at seconds per query at
  library scale); the obligation is on the result's honesty, not on the
  operator used.
- **R6 — sufficient reply in 3 s beats optimum in 3 min.** Freshness work on
  the query path is O(1) requests; anything bigger is scheduled, never awaited.
- **R18 — an empty result says which.** "Nothing matches" or "this scope is not
  indexed yet", for the scope the query asked, not the library as a whole.
- **R24 — a citeable page in one step.** A fulltext hit leads to its page, and
  an estimated page number says it is an estimate (D10: labeled-estimate). The
  primary locator is the entry heading (ruling 1).
- **R25 — one *entry*, one hit.** As amended by ruling 1 (D9 dissolved): dedup
  is per section, and no single document may crowd other items out of the
  candidate pool before that dedup happens; concentration is disclosed.
- **D5 (query semantics) — a quoted phrase matches as a phrase**, and AND/NOT
  are honored, on both backends; bare terms stay recall-friendly.

**Multilingual**

- **R7 — multilingual by default.** The default path works for FR/DE/VI/EL/RU
  without configuration; the default embedder is multilingual; the English
  STOPWORDS list is a known ranking bias whose deletion is decided (candidate
  move ratified into the plan); CJK ambition is decided explicitly, never
  silent. (AR/HE ride the default path untested — see out-of-scope.)

**Custody and lifecycle**

- **R10 — local by default.** With no explicit opt-in, no library text and no
  query text leaves the machine; the default build and query path make zero
  external calls (the one-time model-weight download excepted and named).
- **R15 — deleted means gone.** Deleting an item in Zotero removes its text
  from every stage's store and the queues between, not merely from search
  results.
- **R22 — pause stays paused.** One obvious way to stop all background work,
  and it holds across restarts.
- **R23 — upgrade and downgrade.** A zoteus with a different schema opens the
  old file and ends up serving, in either direction, without anyone deleting
  files by hand.
- **R28 — uninstall.** Deleting the data dir is the whole uninstall; no index
  state, queue, watermark, or downloaded model survives anywhere else.
- **D3 (embedder change) — serve-stale.** Yesterday's vectors keep answering,
  labeled, until re-embedding overtakes newest-first; semantic coverage never
  drops to zero at open.

**Multi-library and multi-process**

- **R12 — group libraries.** My groups are searchable like my own, and indexing
  one library never erases another. (D4: one merged index, library as an R5
  facet.)
- **R13 — second process.** Two zoteus on one data dir both answer, neither
  corrupts the index, and no passage is extracted or embedded twice. (Honest
  restatement accepted in DESIGN.md §2.5: never committed twice; duplicate
  *compute* bounded at one micro-batch per failover.)

**Operator gates**

- **R19 — the fold sweep is a gate.** No query token may point where the index
  cannot hold; the 1,301-codepoint sweep runs on every check, not in a closed
  ticket.
- **R20 — RAM budgets are gates.** C3's numbers are asserted by the harness
  against the 44.9 MB dictionary on every check, not measured once.
- **R21 — same corpus in, same answers out.** A pinned query set with golden
  answers gates every change. (D11: the golden pins the answer **set**, not the
  order.)

## The resolved decisions (ratified by delegation, 2026-08-26)

| | resolution |
|---|---|
| D1 denominator | **items**; metadata-only items count, with reason |
| D2 hosted mode | **out** — the redesign binds the desktop; the four contingent privacy lines stay dead |
| D3 embedder change | **serve-stale** |
| D4 group shape | **merged** index, library as a facet |
| D5 phrases | **phrase** (and AND/NOT) semantics |
| D6 twin attachments | **first**-with-text |
| D7 own-words scope | **both** notes and annotations |
| D8 image-only PDFs | **leave-room** (OCR out today) |
| D9 monster weight | **dissolved** by the entry ruling |
| D10 page fidelity | **labeled-estimate** |
| D11 what the golden pins | **set** |

## Out of scope, said out loud

So silence does not read as promise (all seven declarations stand):

- **Work does not travel** — the index is per-machine; a second machine
  re-earns it unattended via R1; vector export/sync is out of scope.
- **The rebuild is the backup** — the index is derived and backup-exempt; no
  snapshot tooling.
- **Recency orders coverage, not answers** — R2 is an indexing frontier;
  ranking stays relevance-only.
- **OCR is out** — image-only attachments converge as metadata-only.
- **Hosted mode is out** — the redesign binds the desktop; the OAuth server
  keeps today's behavior.
- **AR/HE untested** — expected to ride the default path, outside R7's tested
  matrix.
- **No enumeration** — semantic search returns a bounded page; exhaustiveness
  is R5 narrowing's job, not paging's.
