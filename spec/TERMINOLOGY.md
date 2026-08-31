# TERMINOLOGY — the vocabulary of the specification chain

## Intro

Every term of art in this chain is glossed where it first appears. That serves
a reader going through a document from the top, and nobody reads a
specification that way twice: tickets, reviews and forge threads all enter in
the middle. This document is the entry point for that reader. It defines, in
one alphabetical place, the words `REQUIREMENTS.md`, `CONSTRAINTS.md` and
`DESIGN.md` use as if they were already understood.

Three buckets, marked because a newcomer cannot otherwise tell which words this
project coined. **Ours** are this design's own vocabulary. **Inherited,
Zotero** are the platform's, and mean here exactly what they mean there.
**Inherited, SQLite** are the storage engine's. A short historical section at
the end covers words that appear in git history and in closed tickets but name
nothing in the current design.

Each entry gives the term, one sentence, and where it is authoritative.

**This document owns no numbers.** A definition names the document that holds a
threshold, a budget or a cadence; it never restates the figure. Two copies of a
design number is this repository's most expensive recurring defect, and a
glossary is the most tempting place to make the second one. The rule is
mechanical rather than a matter of care: `bench/check_terminology.py` fails on
any digit here that is not an address — a commit, a date, a reference code, a
section mark, a version, a ticket. A citation beside a number does not excuse
it. What the guard cannot see is a threshold restated in words, so that stays a
matter of review.

The glossary also never decides. Where a term's meaning is still open, the
entry points at the question rather than settling it; rulings land in
`DECISIONS.md` first, and every other document, this one included, follows.

---

## Ours

- **band 0 / band 1** — the two lanes of the body-text frontier: each item's
  first K passages ride the newest-first frontier, and its remaining passages
  queue behind them, so one monster document cannot monopolise the pipeline.
  Authoritative: DESIGN.md §2.3, which derives K.
- **cache-lost** — the stored warning state of passages whose item answers
  not-found on the full-text content endpoint while every version signal is
  unmoved: the derived cache is gone, the source is not, so the passages stay
  served and counted rather than evicted, and the user's Reindex is the
  healing path. Authoritative: DESIGN.md §2.4 (ruling: DECISIONS.md
  2026-08-30).
- **census** — a full listing fetched whole rather than paged, every item or
  every full-text version in one response, compared against stored state by
  equality. Authoritative: DESIGN.md §2.4.
- **conductor** — the one query-serving server, elected through a lease row,
  that runs the reconcile tick and owns the single background worker, so the
  pipeline budget does not multiply with the number of servers running.
  Authoritative: DESIGN.md §2.5, which owns the lease timing.
- **coverage** — how much of the library is searchable, counted in items per
  stage, with metadata-only items in the denominator and their reason
  recorded. Authoritative: REQUIREMENTS.md R1 and R17; the coverage sentence
  and its counters are DESIGN.md §2.8.
- **cross-lingual** — the property that a query in one language retrieves
  documents in another: an English or French query finding Vietnamese content.
  Stronger than *multilingual* and routinely confused with it — multilingual is
  each language working in its own lane, cross-lingual is the lanes connecting.
  Only the embedding space crosses languages; the keyword path cannot.
  Authoritative: REQUIREMENTS.md R29 (ruling: DECISIONS.md 2026-08-31); the
  mechanism is DESIGN.md §2.6.
- **custody string** — the one-line statement, carried on every reply, of where
  the query text and the library text went. Authoritative: REQUIREMENTS.md
  R10; the mechanism is DESIGN.md §2.7.
- **entry** — the unit of answer: a section of a document rather than the
  document, so an encyclopedia is one item and many entries. Authoritative:
  REQUIREMENTS.md, the first ruling; the storage layer is DESIGN.md §2.2.
- **entry collapse** — reducing a document's matching passages to one ranked
  hit per entry, scored as the maximum over its chunks, before either engine
  assigns ranks. Authoritative: DESIGN.md §2.6.
- **embedder entry** — one indivisible curated configuration whose complete
  vector-affecting fields produce its fingerprint. Authoritative:
  REQUIREMENTS.md R31 and DESIGN.md §2.5.
- **embedding service** — the shareable local endpoint toward which the
  transport-neutral query/passage interface can evolve; whether zoteus should
  provide, bundle or merely consume one remains open. Authoritative: DESIGN.md
  §3 and ticket 0491.
- **the four gates** — the standing checks that hold the promises the design
  cannot prove by reading: the fold gate, the RSS gate, the golden gate and the
  soak gate. Authoritative: DESIGN.md §2.8, which owns every threshold; the
  requirements they serve are R13, R19, R20 and R21.
- **fraction-RRF** — fraction-weighted reciprocal-rank fusion, the rule that
  merges the keyword and semantic ranked lists into one. Authoritative:
  DESIGN.md §2.6, which owns the constant, the seam invariant and the ship
  gate.
- **first-with-text** — the rule that per item exactly one attachment is
  indexed for body text, the deterministic first appearing in the full-text
  census, with a stored reason for each attachment skipped. Authoritative:
  REQUIREMENTS.md D6; the choice function is DESIGN.md §2.3.
- **key** — the recorded identity of the inputs that produced a piece of
  derived data, so that work is stale exactly when the stored key differs from
  the current one (contrast *signal*). Authoritative: CONSTRAINTS.md C1; the
  per-stage keys are DESIGN.md §2.1.
- **the ledger** — the durable table of item-by-stage rows, each claimed under
  a lease, computed, then committed, where all background work is scheduled and
  all of its state survives a restart. Authoritative: DESIGN.md §1 and §2.5.
- **the locator** — what a hit hands back so the reader can cite it: the entry
  heading path first, exact character offsets, and for body hits a page number
  explicitly labelled an estimate. Authoritative: REQUIREMENTS.md R24; the
  shape per hit kind is DESIGN.md §2.6.
- **metadata-only** — the terminal state of an attachment that yields no text:
  covered rather than failed, with its reason recorded and counted in the
  denominator. Authoritative: REQUIREMENTS.md R14 and R17.
- **multilingual** — the property that the default path works in each of the
  tested languages on its own terms and with no configuration, which is what
  makes a multilingual default embedder a requirement rather than a preference.
  Not the same claim as *cross-lingual*: a system can answer a Vietnamese query
  over Vietnamese content and still have no path from an English one.
  Authoritative: REQUIREMENTS.md R7.
- **P0 / pipeline workers** — the query-serving zoteus server may have several
  instances; the conductor owns one run-to-drain worker of each pipeline kind:
  extract, chunk, embed. Authoritative: DESIGN.md §2.5.
- **passage** — a stored reference into a slab rather than a copy of text, and
  the chunk-sized unit both engines index. Authoritative: DESIGN.md §2.2.
- **prefix** — the coverage-order property: at every moment the indexed set is
  the newest items with no gap in the middle. Authoritative: REQUIREMENTS.md R2
  and R26; the granularity at which the design asserts it, per phase rather
  than over the library, is DESIGN.md §2.3.
- **probe-don't-fix** — the freshness posture of the query path: when the tick
  is stale, one bounded probe reports and nudges rather than blocking the
  answer. Authoritative: DESIGN.md §2.4, which owns the deadline.
- **quarantine** — the state of an input that has failed persistently: work
  stops, status says so, and it clears on a change in the content signal chain
  rather than on counter movement. Authoritative: DESIGN.md §1 and §2.8.
- **reconcile tick** — the conductor's periodic pass over each library: items
  by watermark, full text by census equality, deletions by census subtraction.
  Authoritative: DESIGN.md §2.4, which owns the cadence and the backoff.
- **the record** — an item's own metadata as an indexed unit (title, abstract,
  keywords, creators, venue, date), indexed before any body text and held in
  per-field columns so that a tag match does not score like a title match.
  Authoritative: REQUIREMENTS.md, the second ruling; the column layout is
  DESIGN.md §2.2.
- **segmenter (seg/1)** — the heuristic that finds entry boundaries in flat
  extracted text, classifying lines, collecting heading candidates from
  numbering, case shape and headword rhythm, cutting at accepted headings, and
  falling back to labelled synthetic entries below its confidence threshold.
  Authoritative: DESIGN.md §2.2 for the spec and the threshold; ticket 0028
  builds it and experiment X5 gates what depends on it.
- **sideline-never-delete** — the response to an index file a binary cannot
  safely read: move it aside and build fresh, never remove it, so the evidence
  of the skew survives. Authoritative: REQUIREMENTS.md R23; the protocol, and
  who may perform it, is DESIGN.md §2.7.
- **signal** — a Zotero version counter, scoped by server identity and only
  ever compared for equality, whose mismatch schedules verification rather than
  recomputation (contrast *key*). Authoritative: DESIGN.md §2.1.
- **slab** — a compressed span of source text, stored by us and cut on entry
  boundaries, from which every snippet is re-derived instead of refetched from
  Zotero. Authoritative: DESIGN.md §2.2, which owns the size ceiling.
- **stage** — one step of the indexing pipeline: record, extract, chunk, embed.
  Each carries its own key, its own ledger rows and its own counters.
  Authoritative: REQUIREMENTS.md, intro; the keys are DESIGN.md §2.1.
- **validation attestation** — an optional content-free report that one exact
  embedder entry passed the automatic compatibility fixture on a stated runtime
  shape; it is not a retrieval-quality judgement. Authoritative:
  REQUIREMENTS.md R31 and DESIGN.md §2.6.
- **watermark** — a resume cursor stored per origin and library, legitimate
  only where the underlying version sequence is genuinely monotonic; the local
  full-text sequence is mixed, so no watermark column exists for it.
  Authoritative: CONSTRAINTS.md C1; its use is DESIGN.md §2.4.

## Inherited, Zotero

These mean here what they mean in the platform. Each entry says where the chain
relies on it, because that is the part a reader of our documents needs.

- **attachment** — the child object holding a file, from which body text is
  extracted; an item itself has none. Zotero's; our use of it is DESIGN.md
  §2.3.
- **`dateAdded`** — an item's creation timestamp, which is what "newest" means
  throughout this design's ordering. Zotero's; the total-order key built on it
  is DESIGN.md §2.8.
- **`/fulltext` census endpoint** — the local API route listing every
  attachment's full-text version in one unpaginated response. Zotero's; how the
  design diffs it is DESIGN.md §2.4, and why it must never be cursored on the
  local transport is CONSTRAINTS.md C1.
- **item** — the platform's unit of bibliography, one record with zero or more
  child attachments and notes. It is deliberately *not* this design's unit of
  answer. Zotero's; the entry ruling is REQUIREMENTS.md, the first ruling.
- **`Last-Modified-Version`** — the response header carrying the library
  version a read observed, and the value a client stores to resume from.
  Zotero's; the watermark built on it is DESIGN.md §2.4.
- **library / `libraryVersion`** — a personal or group collection of items, and
  its version counter; item keys are unique only within a library. Zotero's;
  the merged-index consequence is REQUIREMENTS.md D4 and DESIGN.md §2.2.
- **local API** — the HTTP interface the desktop application serves on
  loopback, unpaginated and unthrottled, and the transport this design uses.
  Zotero's; the politeness rules that apply to the web transport and not to
  this one are CONSTRAINTS.md.
- **`?since=` version cursor** — the query parameter asking for everything
  changed after a given version. Zotero's; it is a legitimate cursor on the
  item sequence and not on the local full-text sequence, per CONSTRAINTS.md C1.
- **`Zotero-Server-ID`** — the response header identifying which database
  answered, within which alone versions and keys are comparable. Zotero's; the
  partition it forces on stored state is CONSTRAINTS.md C1 and DESIGN.md §2.2.

## Inherited, SQLite

- **`bm25`** — the ranking function the full-text engine exposes, scoring a row
  against a query under per-column weights. SQLite's; the weights, and when
  they are tuned, are DESIGN.md §2.2.
- **FTS5** — SQLite's full-text search extension, the keyword half of this
  design's retrieval. SQLite's; the table layout, the tokenizer and the
  contentless mode are DESIGN.md §2.2, and the measured cost of constraining a
  match to a row set is CONSTRAINTS.md C2.
- **`unicode61`** — the tokenizer the full-text index uses, configurable for
  diacritic folding; the query and index normalizers must agree on it or a term
  can never match. SQLite's; the configuration is DESIGN.md §2.2 and the
  agreement check is REQUIREMENTS.md R19.
- **WAL** — write-ahead logging, the journal mode under which readers answer
  while a writer commits, which is what makes several servers on one file
  possible. SQLite's; the connection settings are DESIGN.md §2.2.

## Historical

Words a reader meets in git history, in closed tickets, or in the panel record,
and which name nothing in the current design. They are listed so that finding
one dates the text rather than sending the reader hunting.

- **corpus-critic M4** — a panel-era label for one of the cycle-two critique
  seats. Historical: it named a session role, never a component.
- **graft** — a panel-era word for attaching new machinery onto an existing
  pipeline stage. Historical: removed from the chain by ticket 0036's rewrite,
  which required every term of art to be defined where it first appears.
- **kill 9** — a panel-era shorthand for the abrupt process termination the
  soak gate exercises. Historical as a phrase; the property it named survives
  as the soak gate's assertions in DESIGN.md §2.8.
- **`panel/cycle2/`** — the cycle-two design panel's verbatim session record:
  memos, critiques, and the political and implementation reviews. Deleted from
  the tree and last present at commit `e32afe3`. It was never authoritative,
  and where it disagrees with DESIGN.md, DESIGN.md is the record.
- **The Settled Ledger (v1)** — the cycle-one design, superseded by the current
  "Instrumented Ledger". Historical: what changed and why is DESIGN.md §1, and
  the document itself lives only in git history.
