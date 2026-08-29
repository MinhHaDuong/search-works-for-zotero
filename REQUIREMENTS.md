# REQUIREMENTS — what the system promises

## Intro

This document lists the user requirements, R1 to R28. Each is written as a
testable property: something the test harness, or a careful reader, can
check. They were agreed with the author and consolidated on 2026-08-26; the
documents they were consolidated from are superseded and live only in git
history. A "stage" below is one step of the indexing pipeline: record,
extract, chunk, embed.

Authority works like this: the author's rulings are recorded in DECISIONS.md
first, and this document is then edited to match. Any line here can still be
vetoed by the author on a later reading: the veto lands in DECISIONS.md, and
this document then follows. Constraints (what the world imposes) are in
CONSTRAINTS.md. The design that honors all of this is DESIGN.md.

## The three rulings that shape everything

1. **The unit of answer is the entry.** A dictionary or encyclopedia is one
   Zotero item but many entries, so retrieval and deduplication work on the
   section, not the item. An encyclopedic item may legitimately give several
   distinct hits where a focused article gives one, and where an entry
   heading is known, the heading is the citation locator.

2. **The record is the semantic core.** Title, abstract, and keywords are
   the main semantic targets, and every item's record is indexed before any
   body text. Fields keep their identity for ranking: a tag match must not
   score like a title match. Notes, annotations, and body text are added on
   top of the core; they must not weaken the ranking weight of the record
   fields.

3. **Chunking respects entry boundaries; context is prepended.** Where
   document structure is detectable, chunk boundaries align to section and
   entry boundaries, so a chunk never straddles two entries. Each chunk's
   embedded text starts with its context: the entry heading, the outline
   path, and the item title.

## Requirements

### Coverage and convergence

- **R1 — eventually the whole library is indexed.** With no further edits,
  coverage reaches 100 % without anyone asking, and no state ever needs a
  manual rebuild.
- **R2 — most recent first.** Coverage grows newest-first: the
  crawler works through a priority order, not a page cursor, and recency
  orders *coverage*, not answers (see "Out of scope").
- **R4 — something partial is better than nothing.** The index answers
  queries at every moment of its life, including during the first build.
  This obliges honest coverage reporting; otherwise a partial index is
  indistinguishable from a complete one.
- **R14 — no text is a terminal state.** An attachment that yields no text
  is *done*, not retried forever. It counts as covered ("metadata-only"),
  the reason is recorded, and the coverage report says so. (Per D8, in the
  resolved decisions tabled below, OCR is out for now, but the stage keys
  leave room for a future extractor.)
- **R17 — coverage in one sentence.** "How much of my library is
  searchable?" gets a human answer: N of M items (per D1), per stage, with
  the most-recent-covered date. Metadata-only items count toward the
  denominator, with their reason.
- **R26 — convergence is watched, not trusted.** The harness starts from an
  empty index and only polls the status endpoint. Coverage must reach 100 %
  with no other intervention, and at every poll the indexed set must be a
  most-recent-first prefix: the newest N items, never a gap in the middle.
  (The granularity at which "prefix" is asserted is a design reading,
  DESIGN.md §2.3, flagged for author veto.)

### Change and cost

- **R3 — avoid unnecessary rebuild.** The cost of staying current is
  proportional to the change, not to the library. Recompute exactly what is
  downstream of a changed input; the unit of invalidation is (item ×
  stage).
- **R11 — counter churn is not change.** A resync or extractor upgrade that
  advances version counters re-embeds nothing whose bytes are unchanged.
  (This project itself once shipped a defect that re-marked 92,7 % of the
  library as changed, forever; it is the cautionary example.)
- **R27 — edit one, count one.** Every stage reports what it processed and
  which input triggered it, and one edited item shows up as one.

### Corpus

- **R8 — 10k documents is not much.** The design point is at least 10 000
  documents with full text, and the known red zone is that a full vector
  scan approaches 1 s at that size.
- **R9 — 15 000-page documents are included.** Monster documents are
  first-class input, not an outlier to cap away (the 44.9 MB dictionary is
  the living example). Under ruling 1, a monster is a collection of entries
  among peers.
- **R16 — my own words.** Notes *and* annotations are part of the corpus
  (per D7), not just the papers.

### Query

- **R5 — filters are good to have.** Scoping by collection, tag, item type,
  or date is enforced before any answer is truncated, never by filtering
  after the fact a top-k list (the k best-scoring results) that claims to
  be complete. One correction from the scouts (the pre-design code-reading
  and measurement passes): "pushed into SQL" must not be read as
  constraining the MATCH operator of SQLite's FTS5 full-text engine, which
  measures at seconds per query at library scale. The obligation is on the
  honesty of the result, not on which operator enforces it.
- **R6 — a sufficient reply in 3 s beats the optimum in 3 min.** Freshness
  work on the query path is limited to O(1) requests; anything bigger is
  scheduled, never awaited.
- **R18 — an empty result says which.** The answer is "nothing matches" or
  "this scope is not indexed yet", stated for the scope the query asked
  about, not for the library as a whole.
- **R24 — a citeable page in one step.** A full-text hit leads to its page,
  an estimated page number says it is an estimate (per D10), and the
  primary locator is the entry heading (ruling 1).
- **R25 — one entry, one hit.** As amended by ruling 1 (D9 dissolved):
  deduplication is per section, and no single document may crowd other
  items out of the candidate pool before that deduplication happens. When
  many of the returned hits come from one document, the result says so.

### Multilingual

- **R7 — multilingual by default.** The default path works for French,
  German, Vietnamese, Greek and Russian with no configuration, and the
  default embedder is multilingual. The English stopword list is a known
  ranking bias whose deletion is already decided (the move is ratified into
  the plan). Any Chinese/Japanese/Korean (CJK) ambition is decided
  explicitly, never silently. (Arabic and Hebrew use the default path but
  are not tested; see "Out of scope".)

### Custody and lifecycle

- **R10 — local by default.** Without an explicit opt-in, no library text
  and no query text leaves the machine. The default build and query path
  make zero external calls; the one-time model-weight download is the sole
  exception, and it is named.
- **R15 — deleted means gone.** Deleting an item in Zotero removes its text
  from every stage's store and from the queues between them, not merely
  from search results.
- **R22 — pause stays paused.** There is one obvious way to stop all
  background work, and it holds across restarts.
- **R23 — upgrade and downgrade.** A zoteus with a different schema version
  opens the old file and ends up serving, in either direction, without
  anyone deleting files by hand.
- **R28 — uninstall.** Deleting the data directory is the whole uninstall;
  no index state, queue, watermark, or downloaded model survives anywhere
  else.

### Multi-library and multi-process

- **R12 — group libraries.** Group libraries are searchable like my own,
  and indexing one library never erases another. (Per D4: one merged index,
  with the library as one more R5 filter, like collection or tag.)
- **R13 — second process.** Two zoteus processes on one data directory both
  answer queries, neither corrupts the index, and no passage is extracted
  or embedded twice. (Honest restatement accepted in DESIGN.md §2.5: never
  *committed* twice; duplicate *compute* is bounded at one micro-batch per
  failover.)

### Operator gates

- **R19 — the fold sweep is a gate.** Every token the query normalizer
  produces must be one the index normalizer can also produce; otherwise
  that query term can never match anything. The character-folding sweep
  that checks this agreement, over 1 301 codepoints, runs on every check,
  not once in a closed ticket.
- **R20 — RAM budgets are gates.** The RAM budgets of constraint C3
  (CONSTRAINTS.md) are asserted by the harness against the 44.9 MB
  dictionary on every check, not measured once. (This rule can be read two
  ways: run on every check, or only in the slow suite; and test against the
  real copyrighted dictionary, or a synthetic stand-in that can be
  committed. Both questions await the author's ruling in DECISIONS.md;
  DESIGN.md §2.8 says what the design currently does.)
- **R21 — same corpus in, same answers out.** A pinned query set with
  golden (known-correct) answers gates every change. (Per D11, the golden
  set pins the answer set, not the order.)

## The resolved decisions (ratified by delegation, 2026-08-26)

| | resolution |
|---|---|
| D1 denominator | Coverage counts **items**; metadata-only items count, with their reason. |
| D2 hosted mode | **Out.** The redesign binds the desktop; the four privacy requirements that only applied to hosted mode are dropped. |
| D3 embedder change | **Serve-stale.** The old model's vectors keep answering, labeled, until re-embedding overtakes them newest-first; semantic coverage never drops to zero at the moment the new embedder is adopted. |
| D4 group shape | One **merged** index; the library is a filter facet. |
| D5 query semantics | A quoted **phrase** matches as a phrase, and AND/NOT are honored, on both backends (keyword and semantic); bare terms stay recall-friendly. |
| D6 twin attachments | **First-with-text.** Per item, one attachment is indexed for body text; skipped ones get a recorded reason. |
| D7 own-words scope | **Both** notes and annotations. |
| D8 image-only PDFs | **Leave room** (OCR is out today). |
| D9 monster weight | **Dissolved** by the entry ruling. |
| D10 page fidelity | **Labeled estimate.** |
| D11 what the golden pins | The answer **set**, not the order. |

## Out of scope, said out loud

These seven things are deliberately not promised, so that silence does not
read as a promise:

- **Work does not travel.** The index is per-machine; a second machine
  re-earns it unattended via R1. Vector export and sync are out of scope.
- **The rebuild is the backup.** The index is derived data, exempt from
  backup; no snapshot tooling.
- **Recency orders coverage, not answers.** R2 is an indexing frontier;
  ranking stays relevance-only.
- **OCR is out.** Image-only attachments converge as metadata-only.
- **Hosted mode is out.** The redesign binds the desktop; the OAuth server
  keeps today's behavior.
- **Arabic and Hebrew are untested.** Expected to work on the default path,
  but outside R7's tested matrix.
- **No enumeration.** Semantic search returns a bounded page; exhaustiveness
  is the job of R5 narrowing, not of paging.
