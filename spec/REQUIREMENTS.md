# REQUIREMENTS — what the system promises

## Intro

This document lists the user requirements, R1 to R34. Each is written as a
testable property: something the test harness, or a careful reader, can
check. They were agreed with the author and consolidated on 2026-08-26; the
documents they were consolidated from are superseded and live only in git
history. A "stage" below is one step of the indexing pipeline: record,
extract, chunk, embed.

The authority chain — how this document relates to DECISIONS.md,
CONSTRAINTS.md, and DESIGN.md — is stated once, in README.md. Read it before
treating a line here as final.

**Normative language.** The R-items below follow RFC 2119. MUST, and its
synonym SHALL, marks a firm requirement. SHOULD marks a preference that may be
set aside for a stated reason. MAY marks something optional. These words bind
only in upper case. The same words in lower case are ordinary prose and carry
no such force, which is what lets the surrounding narrative use them freely.

One R-item carries no keyword yet. R26 was rejected as written on 2026-08-29
(DECISIONS.md) and ticket 0080 owns its rewrite; giving it a force now would
record rejected text as contract.

## The four rulings that shape everything

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

4. **The search perimeter is what Zotero shows.** Every item visible in the
   user's Zotero is in scope, the group libraries they subscribe to included.
   What Zotero does not show as library content is out: the trash is outside
   the perimeter, and R15 owns the transition into it; feeds are outside it
   altogether, being neither owned nor curated. Where a group is readable but
   its attachments are not fetchable, the item is inside the perimeter and its
   body text is not, which is the metadata-only state R14 and R17 already
   carry. This is the perimeter R1, R8, R9, R12 and R16 each presuppose and
   none of them states.

## Requirements

### Coverage and convergence

- **R1 — eventually the whole library is indexed.** With no further edits,
  coverage MUST reach 100 % without anyone asking, and the system MUST NOT
  require a manual rebuild of any state.
- **R2 — most recent first.** Coverage MUST grow newest-first: the
  crawler works through a priority order, not a page cursor, and recency
  orders *coverage*, not answers (see "Out of scope").
- **R4 — something partial is better than nothing.** The index MUST answer
  queries at every moment of its life, including during the first build.
  This obliges honest coverage reporting; otherwise a partial index is
  indistinguishable from a complete one.
- **R14 — no text is a terminal state.** An attachment that yields no text
  MUST be treated as *done*, not retried forever. It counts as covered
  ("metadata-only"), the reason is recorded, and the coverage report says so. (Per D8, in the
  resolved decisions tabled below, OCR is out for now, but the stage keys
  leave room for a future extractor.)
- **R17 — coverage in one sentence.** "How much of my library is
  searchable?" MUST get a human answer: N of M items (per D1), per stage,
  with the most-recent-covered date. Metadata-only items count toward the
  denominator, with their reason.
- **R26 — convergence is watched, not trusted.** The harness starts from an
  empty index and only polls the status endpoint. Coverage must reach 100 %
  with no other intervention, and at every poll the indexed set must be a
  most-recent-first prefix: the newest N items, never a gap in the middle.
  (The granularity at which "prefix" is asserted is a design reading,
  DESIGN.md §2.3, flagged for author veto.)
- **R30 — capable hardware is used.** Where a supported GPU is usable by the
  embed stage, the system MUST use it, and status MUST name the execution
  device actually serving, on every machine — GPU or not. The ruling and its
  rationale — the native process reaches a GPU where the in-app runtime
  cannot — are in DECISIONS.md (2026-08-30). Time to coverage was part of this
  item until 2026-08-31, when it was split out as R32 on the measured ground
  that finishing today is a property of the configuration rather than of the
  hardware (DECISIONS.md).
- **R32 — the build finishes today.** On the reference machine DESIGN.md §2.8
  names, an initial build with the default configuration MUST reach record
  coverage of the whole library inside the record bound, and body-text
  coverage inside the build bound. Both bounds' values belong to DESIGN.md
  §2.8 and are pinned from measurement, never before it — the pattern R30's
  own gate and C3's replacement ceiling already follow.

### Change and cost

- **R3 — avoid unnecessary rebuild.** The cost of staying current MUST be
  proportional to the change, not to the library. Recompute exactly what is
  downstream of a changed input; the unit of invalidation is (item ×
  stage).
- **R11 — counter churn is not change.** A resync or extractor upgrade that
  advances version counters MUST re-embed nothing whose bytes are unchanged.
  (This project itself once shipped a defect that re-marked 92,7 % of the
  library as changed, forever; it is the cautionary example.)
- **R27 — edit one, count one.** Every stage MUST report what it processed
  and which input triggered it, and one edited item MUST show up as one.

### Corpus

- **R8 — 10k documents is not much.** The design point is at least 10 000
  documents with full text, and the system MUST work at that size. The known
  red zone is that a full vector scan approaches 1 s there.
- **R9 — 15 000-page documents are included.** Monster documents MUST be
  first-class input, not an outlier to cap away (the 44.9 MB dictionary is
  the living example). Under ruling 1, a monster is a collection of entries
  among peers.
- **R16 — my own words.** Notes *and* annotations MUST be part of the
  corpus (per D7), not just the papers.

### Query

- **R5 — filters are good to have.** Scoping by collection, tag, item type,
  or date MUST be enforced before any answer is truncated, never by filtering
  after the fact a top-k list (the k best-scoring results) that claims to
  be complete. One correction from the scouts (the pre-design code-reading
  and measurement passes): "pushed into SQL" MUST NOT be read as
  constraining the MATCH operator of SQLite's FTS5 full-text engine, which
  measures at seconds per query at library scale. The obligation is on the
  honesty of the result, not on which operator enforces it.
- **R6 — a sufficient reply in 3 s beats the optimum in 3 min.** Freshness
  work on the query path MUST be limited to O(1) requests; anything bigger
  MUST be scheduled, never awaited. A warm query MUST answer inside the hard
  budget, whose value belongs to DESIGN.md §2.9 — the same section that owns
  the distinction between that budget and the typical figure it is not.
- **R18 — an empty result says which.** The answer MUST be "nothing matches"
  or "this scope is not indexed yet", stated for the scope the query asked
  about, not for the library as a whole.
- **R24 — a citeable page in one step.** A full-text hit MUST lead to its
  page, an estimated page number MUST say it is an estimate (per D10), and
  the primary locator MUST be the entry heading (ruling 1).
- **R25 — one entry, one hit.** As amended by ruling 1 (D9 dissolved):
  deduplication is per section, and a single document MUST NOT crowd other
  items out of the candidate pool before that deduplication happens. When
  many of the returned hits come from one document, the result says so.

- **R33 — lexical, semantic and hybrid each work.** A query naming a rare
  exact string MUST return the item carrying it; a query that paraphrases its
  answer without sharing a content word MUST return that answer; and where
  both signals are present but weak, the combined answer MUST rank the
  document they agree on above one that only a single signal favours. Where
  the interface offers a retrieval mode, the mode selected MUST be the mode
  served. The combination rule belongs to DESIGN.md §2.6.
- **R34 — if it is in my library, I find it.** For every query of the pinned
  set, whose answers are known-correct and known to be in the corpus, the
  default configuration MUST return the pinned answer within the first ten
  results. Per D11 this fixes the answer set and not its order: order inside
  those ten is unconstrained. Re-pinning the set is a commit whose set diff is
  the review artifact (DESIGN.md §2.8).
### Multilingual

- **R7 — multilingual by default.** The default path MUST work for French,
  German, Vietnamese, Greek and Russian with no configuration, and the
  default embedder MUST be multilingual. The English stopword list is a known
  ranking bias whose deletion is already decided (the move is ratified into
  the plan). Any Chinese/Japanese/Korean (CJK) ambition is decided
  explicitly, never silently. (Arabic and Hebrew use the default path but
  are not tested; see "Out of scope".)

- **R29 — the query language is not the document language.** A query in
  English or French MUST retrieve relevant Vietnamese content without the
  user translating anything. R7 promises each language its own lane; this
  promises the lanes connect. The cross-lingual property MUST be gated
  separately from the monolingual one, so a regression names which promise it
  broke. When the semantic path is unavailable, the reply MUST say that
  cross-language matching is down rather than return a silent miss. Query
  translation is not the mechanism; see "Out of scope".

### Embedding configurations

- **R31 — selectable embedders are complete and proven locally.** Every local
  embedding configuration offered to a user MUST be one versioned, curated
  registry entry containing every field that changes its vectors. Before an
  entry creates or queries an index on a concrete runtime and execution
  provider, it MUST pass the bundled automatic validation there or fail
  explicitly. Failure MUST NOT silently select another entry. Sharing a
  content-free validation attestation MAY be offered only by explicit opt-in;
  library text, query text and Zotero identifiers MUST NOT enter it.

### Custody and lifecycle

- **R10 — local by default.** Without an explicit opt-in, library text and
  query text MUST NOT leave the machine. The default build and query path
  make zero external calls; the one-time model-weight download is the sole
  exception, and it is named.
- **R15 — deleted means gone.** Deleting an item in Zotero MUST remove its
  text from every stage's store and from the queues between them, not merely
  from search results.
- **R22 — pause stays paused.** There MUST be one obvious way to stop all
  background work, and it MUST hold across restarts.
- **R23 — upgrade and downgrade.** A zoteus with a different schema version
  MUST open the old file and end up serving, in either direction, without
  anyone deleting files by hand.
- **R28 — uninstall.** Deleting the data directory MUST be the whole
  uninstall. Index state, queues, watermarks, and downloaded models MUST NOT
  survive anywhere else.

### Multi-library and multi-process

- **R12 — group libraries.** Group libraries MUST be searchable like my
  own, and indexing one library MUST NOT erase another. (Per D4: one merged index,
  with the library as one more R5 filter, like collection or tag.)
- **R13 — second process.** Two zoteus processes on one data directory MUST
  both answer queries, MUST NOT corrupt the index, and MUST NOT extract or
  embed any passage twice. (Honest restatement accepted in DESIGN.md §2.5: never
  *committed* twice; duplicate *compute* is bounded at one micro-batch per
  failover.)

### Operator gates

- **R19 — the fold sweep is a gate.** Every token the query normalizer
  produces MUST be one the index normalizer can also produce; otherwise
  that query term can never match anything. The character-folding sweep
  that checks this agreement, over 1 301 codepoints, MUST run on every
  check, not once in a closed ticket.
- **R20 — RAM budgets are gates.** The RAM budgets of constraint C3
  (CONSTRAINTS.md) MUST be asserted by the slow harness against the
  deterministic synthetic surrogate, not measured once; the fast harness
  MUST assert that the cap mechanism engages. The surrogate MUST be
  revalidated against the real dictionary at each release (DECISIONS.md,
  2026-08-29; DESIGN.md §2.8).
- **R21 — same corpus in, same answers out.** A pinned query set with
  golden (known-correct) answers MUST gate every change. (Per D11, the golden
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
- **Query translation is out.** R29 rides the embedding space, which is the
  only channel that crosses languages. No translation service and no local
  translation model joins the default path.
- **No enumeration.** Semantic search returns a bounded page; exhaustiveness
  is the job of R5 narrowing, not of paging.
