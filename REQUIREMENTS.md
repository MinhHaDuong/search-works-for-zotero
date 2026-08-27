# REQUIREMENTS — what the system promises

## Intro

This document lists the user requirements, R1 to R28. Each is written as a
testable property: something the test harness, or a careful reader, can
check. They were agreed with the author and consolidated on 2026-08-26.

Authority works like this: the author's rulings are recorded in DECISIONS.md
first, and this document is then edited to match. Any line here can still be
vetoed by the author on a later reading — the veto lands in DECISIONS.md,
then this document follows. Constraints (what the world imposes) are in
CONSTRAINTS.md. The design that honors all of this is DESIGN.md.

## The three rulings that shape everything

1. **The unit of answer is the entry.** A dictionary or encyclopedia is one
   Zotero item but many entries. Retrieval and deduplication therefore work
   on the **section**, not the item. An encyclopedic item may legitimately
   give several distinct hits; a focused article gives one. Where an entry
   heading is known, it is the citation locator.

2. **The record is the semantic core.** Title, abstract, and keywords are
   the main semantic targets. Every item's record is indexed before any body
   text. Fields keep their identity for ranking: a tag match must not score
   like a title match. Notes, annotations, and body text extend the core;
   they never dilute it.

3. **Chunking respects entry boundaries; context is prepended.** Where
   document structure is detectable, chunk boundaries align to section and
   entry boundaries — a chunk never straddles two entries. Each chunk's
   embedded text starts with its context: the entry heading, the outline
   path, and the item title.

## Requirements

### Coverage and convergence

- **R1 — eventually the whole library is indexed.** With no further edits,
  coverage reaches 100 % without anyone asking. No state ever needs a manual
  rebuild.
- **R2 — most recent first.** Coverage grows newest-first; the crawler works
  through a priority order, not a page cursor. Recency orders *coverage*,
  not answers — see "Out of scope".
- **R4 — something partial is better than nothing.** The index answers
  queries at every moment of its life, including during the first build.
  This obliges honest coverage reporting — otherwise a partial index is
  indistinguishable from a complete one.
- **R14 — no text is a terminal state.** An attachment that yields no text
  is *done*, not retried forever. It counts as covered ("metadata-only"),
  the reason is recorded, and the coverage report says so. (Per D8, OCR is
  out for now, but the stage keys leave room for a future extractor.)
- **R17 — coverage in one sentence.** "How much of my library is
  searchable?" gets a human answer: N of M **items** (per D1), per stage,
  with the most-recent-covered date. Metadata-only items count toward the
  denominator, with their reason.
- **R26 — convergence is watched, not trusted.** Starting from an empty
  index and touching nothing but the status endpoint, the harness sees
  coverage reach 100 % unattended, and at every poll the indexed set is a
  most-recent-first prefix. (The granularity at which "prefix" is asserted
  is a design reading — DESIGN.md §2.3 — flagged for author veto.)

### Change and cost

- **R3 — avoid unnecessary rebuild.** The cost of staying current is
  proportional to the change, not to the library. Recompute exactly what is
  downstream of a changed input; the unit of invalidation is (item × stage).
- **R11 — counter churn is not change.** A resync or extractor upgrade that
  advances version counters over identical bytes re-embeds nothing. (This
  project itself once shipped a defect that re-marked 92,7 % of the library
  as changed, forever — the cautionary example.)
- **R27 — edit one, count one.** Every stage reports what it processed and
  which input triggered it. One edited item shows up as one.

### Corpus

- **R8 — 10k documents is not much.** The design point is at least 10 000
  documents with full text. Known red zone: a full vector scan approaches
  1 s at that size.
- **R9 — 15 000-page documents are included.** Monster documents are
  first-class input, not an outlier to cap away (the 44.9 MB dictionary is
  the living example). Under ruling 1, a monster is a collection of entries
  among peers.
- **R16 — my own words.** Notes *and* annotations are part of the corpus
  (per D7), not just the papers.

### Query

- **R5 — filters are good to have.** Scoping by collection, tag, item type,
  or date is enforced before any answer is truncated — never by
  post-filtering a top-k list that claims to be complete. One correction
  from the scouts: "pushed into SQL" must not be read as constraining the
  FTS5 MATCH operator itself, which measures at seconds per query at library
  scale. The obligation is on the honesty of the result, not on which
  operator enforces it.
- **R6 — a sufficient reply in 3 s beats the optimum in 3 min.** Freshness
  work on the query path is limited to O(1) requests; anything bigger is
  scheduled, never awaited.
- **R18 — an empty result says which.** "Nothing matches" or "this scope is
  not indexed yet" — stated for the scope the query asked about, not for the
  library as a whole.
- **R24 — a citeable page in one step.** A full-text hit leads to its page,
  and an estimated page number says it is an estimate (per D10). The primary
  locator is the entry heading (ruling 1).
- **R25 — one entry, one hit.** As amended by ruling 1 (D9 dissolved):
  deduplication is per section, and no single document may crowd other items
  out of the candidate pool before that deduplication happens. Concentration
  is disclosed.

### Multilingual

- **R7 — multilingual by default.** The default path works for French,
  German, Vietnamese, Greek and Russian with no configuration. The default
  embedder is multilingual. The English stopword list is a known ranking
  bias whose deletion is already decided (the move is ratified into the
  plan). Any CJK ambition is decided explicitly, never silently. (Arabic and
  Hebrew ride the default path untested — see "Out of scope".)

### Custody and lifecycle

- **R10 — local by default.** Without an explicit opt-in, no library text
  and no query text leaves the machine. The default build and query path
  make zero external calls; the one-time model-weight download is the sole
  exception, and it is named.
- **R15 — deleted means gone.** Deleting an item in Zotero removes its text
  from every stage's store and from the queues between them — not merely
  from search results.
- **R22 — pause stays paused.** There is one obvious way to stop all
  background work, and it holds across restarts.
- **R23 — upgrade and downgrade.** A zoteus with a different schema version
  opens the old file and ends up serving, in either direction, without
  anyone deleting files by hand.
- **R28 — uninstall.** Deleting the data directory is the whole uninstall.
  No index state, queue, watermark, or downloaded model survives anywhere
  else.

### Multi-library and multi-process

- **R12 — group libraries.** Group libraries are searchable like my own, and
  indexing one library never erases another. (Per D4: one merged index, with
  the library as an R5 filter facet.)
- **R13 — second process.** Two zoteus processes on one data directory both
  answer queries, neither corrupts the index, and no passage is extracted or
  embedded twice. (Honest restatement accepted in DESIGN.md §2.5: never
  *committed* twice; duplicate *compute* is bounded at one micro-batch per
  failover.)

### Operator gates

- **R19 — the fold sweep is a gate.** No query token may point where the
  index cannot hold. The 1 301-codepoint sweep runs on every check, not once
  in a closed ticket.
- **R20 — RAM budgets are gates.** The C3 budgets are asserted by the
  harness against the 44.9 MB dictionary on every check, not measured once.
  (Two readings of this letter — every-check versus slow-suite cadence, and
  a committable synthetic surrogate versus the copyrighted dictionary itself
  — are on DECISIONS.md's awaiting-ratification list; DESIGN.md §2.8 states
  the deviations.)
- **R21 — same corpus in, same answers out.** A pinned query set with golden
  answers gates every change. (Per D11, the golden set pins the answer
  **set**, not the order.)

## The resolved decisions (ratified by delegation, 2026-08-26)

| | resolution |
|---|---|
| D1 denominator | Coverage counts **items**; metadata-only items count, with their reason. |
| D2 hosted mode | **Out.** The redesign binds the desktop; the four contingent privacy lines stay dead. |
| D3 embedder change | **Serve-stale.** Yesterday's vectors keep answering, labeled, until re-embedding overtakes them newest-first; semantic coverage never drops to zero at open. |
| D4 group shape | One **merged** index; the library is a filter facet. |
| D5 query semantics | A quoted **phrase** matches as a phrase, and AND/NOT are honored, on both backends; bare terms stay recall-friendly. |
| D6 twin attachments | **First-with-text.** Per item, one attachment is indexed for body text; skipped ones get a recorded reason. |
| D7 own-words scope | **Both** notes and annotations. |
| D8 image-only PDFs | **Leave room** (OCR is out today). |
| D9 monster weight | **Dissolved** by the entry ruling. |
| D10 page fidelity | **Labeled estimate.** |
| D11 what the golden pins | The answer **set**, not the order. |

## Out of scope, said out loud

So that silence does not read as a promise, seven declarations stand:

- **Work does not travel.** The index is per-machine; a second machine
  re-earns it unattended via R1. Vector export and sync are out of scope.
- **The rebuild is the backup.** The index is derived data, exempt from
  backup; no snapshot tooling.
- **Recency orders coverage, not answers.** R2 is an indexing frontier;
  ranking stays relevance-only.
- **OCR is out.** Image-only attachments converge as metadata-only.
- **Hosted mode is out.** The redesign binds the desktop; the OAuth server
  keeps today's behavior.
- **Arabic and Hebrew are untested.** Expected to ride the default path,
  outside R7's tested matrix.
- **No enumeration.** Semantic search returns a bounded page; exhaustiveness
  is the job of R5 narrowing, not of paging.
