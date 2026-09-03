# SPEC — search-works-for-zotero

- **Status:** DRAFT
- **Author:** Minh Ha-Duong (CNRS)
- **Date:** 2026-09-03

## 1. Introduction

This document specifies search that works over a local Zotero library: what
any implementation must promise its users (§3), what the world imposes on it
(§4), and a design that answers both (§5). The promises bind the capability,
not a vehicle. Integration into Zotero itself comes first among possible
homes; zoteus, an MCP server over the local library, is the vehicle the
design is currently stated against and measured on.

§2 defines the vocabulary the rest of this document uses. §3 states what any
implementation promises its users, one testable requirement per row (R1 to R35).
§4 states what the world — Zotero, the upstream project, the user's machine —
imposes on any design that would keep those promises (C1 to C3). §5 is the
design that answers both. §6 is where it can leak.

Rulings are ratified in `DECISIONS.md` first, and this document is edited to
match. Where each promise stands today, against the reviewed upstream
baseline, is `README.md`'s.

## 2. Terminology

### Intro

Every term of art is glossed where it first appears in this document, in one
alphabetical place, so a reader who enters mid-document has somewhere to look
a word up. Three buckets, marked because a newcomer cannot otherwise tell
which words this project coined. **Ours** is this design's own vocabulary.
**Inherited, Zotero** is the platform's, and means here exactly what it means
there. **Inherited, SQLite** is the storage engine's.

Each entry gives the term, one sentence, and where it is authoritative. A
definition names the section that holds a threshold, a budget or a cadence
rather than restating the figure, and where a term's meaning is still open,
the entry points at the question rather than settling it.

---

### Ours

- **band 0 / band 1** — the two lanes of the body-text frontier: each item's
  first K passages ride the newest-first frontier, and its remaining passages
  queue behind them, so one 15 000-page PDF cannot monopolise the pipeline.
  Authoritative: SPEC.md §5.2.3, which derives K.
- **cache-lost** — the stored warning state of passages whose item answers
  not-found on the full-text content endpoint while every version signal is
  unmoved: the derived cache is gone, the source is not, so the passages stay
  served and counted rather than evicted, and the user's Reindex is the
  healing path. Authoritative: SPEC.md §5.2.4 (ruling: DECISIONS.md
  2026-08-30).
- **calibration header** — the fixed, public set of chunks that opens a vector
  file, embedded by the same chain in the same run as the corpus behind it, so
  the file certifies its own embedding chain and a reader verifies it locally
  rather than trusting declared metadata. It lives in the manifest, never in the
  slab's row space, so no consumer can return a calibration chunk as a hit.
  Authoritative: SPEC.md §5.2.2 (rulings: DECISIONS.md 2026-08-31).
- **calibration probe** — the projected copy of the calibration header carried
  beside it, each vector multiplied by a matrix drawn from a seed published with
  the format, read first because it fails fast and carries no corpus. It is a
  cheap read and never the decision: the ratified comparison is the per-vector
  cosine and the rank agreement over the header itself. Authoritative:
  SPEC.md §5.2.2, which owns its width and its bound (ruling: DECISIONS.md
  2026-08-31).
- **census** — a full listing fetched whole rather than paged, every item or
  every full-text version in one response, compared against stored state by
  equality. Authoritative: SPEC.md §5.2.4.
- **conductor** — the writer process: a process of its own rather than a role
  a query-serving server takes on, elected through a lease row, that is the
  sole writer of derived state and the segmenter, runs the reconcile tick, and
  owns the single pipeline worker, so the pipeline budget does not multiply
  with the number of servers running. Authoritative: SPEC.md §5.2.5, which owns the lease timing
  (ruling: DECISIONS.md 2026-09-02).
- **embedding service** — the one process on the machine that holds an
  embedder, called by every server for queries and by the pipeline worker for
  passages, so the model is resident once per generation rather than once per
  process; under the API execution mode it holds the key and the provider's
  quota instead of a model. Authoritative: SPEC.md §5.2.5, which owns its
  shape, its degradation rule and the API mode's constants (rulings:
  DECISIONS.md 2026-09-02); which process hosts it is open, and SPEC.md §5.3
  owns that question.
- **coverage** — how much of the library is searchable, counted in items per
  stage, with metadata-only items in the denominator and their reason
  recorded. Authoritative: SPEC.md R1 and R17; the coverage sentence
  and its counters are SPEC.md §5.2.8.
- **cross-lingual** — the property that a query in one language retrieves
  documents in another: an English or French query finding Vietnamese content.
  Stronger than *multilingual* and routinely confused with it — multilingual is
  each language working in its own lane, cross-lingual is the lanes connecting.
  Only the embedding space crosses languages; the keyword path cannot.
  Authoritative: SPEC.md R29 (ruling: DECISIONS.md 2026-08-31); the
  mechanism is SPEC.md §5.2.6.
- **custody string** — the one-line statement, carried on every reply, of where
  the query text and the library text went. Authoritative: SPEC.md
  R10; the mechanism is SPEC.md §5.2.7.
- **droplist** — the terms a particular library's own document frequencies put
  out of a query, derived from its keyword index at build time and applied on
  the query side only. Not a stoplist and not a translation of one: a stoplist
  is a fixed list of one language's function words, which cannot be right in a
  token space holding every language at once, where a homograph is one string.
  What a term costs in *this* corpus has a single answer, and that is what is
  asked. Authoritative: SPEC.md §5.3, which sets the threshold and the rule for
  a query that loses too many terms to it; the implementation is ticket 0091.
- **entry** — the unit of answer: a section of a document rather than the
  document, so an encyclopedia is one item and many entries. Authoritative:
  SPEC.md, the first ruling; the storage layer is SPEC.md §5.2.2.
- **entry collapse** — reducing a document's matching passages to one ranked
  hit per entry, scored as the maximum over its chunks, before either engine
  assigns ranks. Authoritative: SPEC.md §5.2.6.
- **embedder entry** — one indivisible curated configuration whose complete
  vector-affecting fields produce its fingerprint. Authoritative:
  SPEC.md §5.2.5.
- **the four gates** — the standing checks that hold the promises the design
  cannot prove by reading: the fold gate, the RSS gate, the golden gate and the
  soak gate. Authoritative: SPEC.md §5.2.8, which owns every threshold; the
  only requirement they serve is R13; the fold, RAM and golden gates serve no
  requirement of their own — the fold gate since 2026-09-03, when R19 became a
  promise about what a user sees that a source-reading sweep cannot decide, the
  other two since 2026-08-31 — a gate being apparatus rather than a promise.
- **fraction-RRF** — fraction-weighted reciprocal-rank fusion, the rule that
  merges the keyword and semantic ranked lists into one. Authoritative:
  SPEC.md §5.2.6, which owns the constant, the seam invariant and the ship
  gate.
- **first-with-text** — the rule that per item and detected language exactly
  one attachment is indexed for body text, the deterministic first appearing
  in the full-text census, with a stored reason for each same-language
  attachment skipped. Authoritative: SPEC.md D6; the choice function is
  SPEC.md §5.2.3.
- **goals ladder / rung** — the order the sheet's promises are made true in:
  five goals, each a bundle of requirements named in the user's own words. A
  rung is one of them. An implementation strategy rather than a promise about
  the system, so nothing about it is specified here. Authoritative: README.md
  for the order, the rules it runs under, and each rung's roster; the membership
  and the ordering were ruled in DECISIONS.md (2026-08-31).
- **rendering** — one language expression of a work. Declared renderings may
  be twin attachments under one item or explicitly related items; similarity
  alone never declares the relation. Authoritative: SPEC.md R24 and
  SPEC.md §5.2.6.
- **key** — the recorded identity of the inputs that produced a piece of
  derived data, so that work is stale exactly when the stored key differs from
  the current one (contrast *signal*). Authoritative: SPEC.md C1; the
  per-stage keys are SPEC.md §5.2.1.
- **fixture level / library level** — where an assertion is decided. The
  fixture level is the committable corpus, running wherever the gate runs; the
  library level is the author's real library or a disclosed machine, which
  cannot be committed. Not two suites over the same ground: the fixture level
  is where assertions run, and the library level is what re-earns the fidelity
  of every fixture standing in for something real. Authoritative: SPEC.md
  §5.2.8 for the gates, README.md in this directory for which level decides each
  term of goal 1 (ruling: DECISIONS.md 2026-08-31).
- **the ledger** — the durable table of item-by-stage rows, computed and then
  committed by the conductor behind the commit guard, where all background
  work is scheduled and all of its state survives a restart. Authoritative:
  SPEC.md §5.1 and §5.2.5.
- **the locator** — what a hit hands back so the reader can cite it: the entry
  heading path first, exact character offsets, and for body hits a page number
  explicitly labelled an estimate. Authoritative: SPEC.md R24; the
  shape per hit kind is SPEC.md §5.2.6.
- **metadata-only** — the terminal state of an attachment that yields no text:
  covered rather than failed, with its reason recorded and counted in the
  denominator. Authoritative: SPEC.md R1 and R17.
- **micro-batch quantum** — the time budget one micro-batch targets, from
  which the batch size is derived per device rather than fixed, so the yield
  interval holds across hardware; the local engine's constant, which the API
  execution mode replaces. Authoritative: SPEC.md §5.2.5 (ruling: DECISIONS.md
  2026-09-01).
- **multilingual** — the property that the default path works in each of the
  tested languages on its own terms and with no configuration, which is what
  makes a multilingual default embedder a requirement rather than a preference.
  Not the same claim as *cross-lingual*: a system can answer a Vietnamese query
  over Vietnamese content and still have no path from an English one.
  Authoritative: SPEC.md R7.
- **P0 / pipeline worker** — P0 is the query-serving zoteus server, of which
  several instances run: each is a reader, and what it writes is control rows
  only. The *pipeline worker* is the single run-to-drain worker the *conductor*
  owns, which fetches text, calls the *embedding service*, and writes nothing.
  Authoritative: SPEC.md §5.2.5.
- **passage** — a stored reference into a slab rather than a copy of text, and
  the chunk-sized unit both engines index. Authoritative: SPEC.md §5.2.2.
- **priority tree** — the single ordering the conductor schedules by, from
  foreground preemption down through the discovery classes, the
  fresh-against-backfill arbitration inside body text, and the two bands. A
  tree rather than flat lanes, and re-evaluated between micro-batches.
  Authoritative: SPEC.md §5.2.5.
- **probe-don't-fix** — the freshness posture of the query path: when the tick
  is stale, one bounded probe reports and nudges rather than blocking the
  answer. Authoritative: SPEC.md §5.2.4, which owns the deadline.
- **quarantine** — the state of an input that has failed persistently: work
  stops, status says so, and it clears on a change in the content signal chain
  rather than on counter movement. Authoritative: SPEC.md §5.1 and §5.2.8.
- **reconcile tick** — the conductor's periodic pass over each library: items
  by watermark, full text by census equality, deletions by census subtraction.
  Authoritative: SPEC.md §5.2.4, which owns the cadence and the backoff.
- **the record** — an item's own metadata as an indexed unit (title, abstract,
  keywords, creators, venue, date), indexed before any body text and held in
  per-field columns so that a tag match does not score like a title match.
  Authoritative: SPEC.md, the second ruling; the column layout is
  SPEC.md §5.2.2.
- **search perimeter** — what the index is obliged to cover: every item
  visible in the user's Zotero, the group libraries they subscribe to
  included. The trash is outside it and feeds are outside it; an item whose
  attachments cannot be fetched is inside it, with its body text absent for a
  recorded reason. Ours, not Zotero's — the platform word `library` is glossed
  separately below. Authoritative: SPEC.md's fourth ruling (ledger:
  DECISIONS.md 2026-08-31).
- **segmenter (seg/1)** — the heuristic that finds entry boundaries in flat
  extracted text, classifying lines, collecting heading candidates from
  a table of contents, chapter and section numbering, and case
  shape, cutting at accepted headings, and
  falling back to labelled synthetic entries below its confidence threshold.
  Authoritative: SPEC.md §5.2.2 for the spec and the threshold; experiment X5
  gates what depends on it.
- **sideline-never-delete** — the response to an index file a binary cannot
  safely read: move it aside and build fresh, never remove it, so the evidence
  of the skew survives. Authoritative: SPEC.md R23; the protocol, and
  who may perform it, is SPEC.md §5.2.7.
- **signal** — a Zotero version counter, scoped by server identity and only
  ever compared for equality, whose mismatch schedules verification rather than
  recomputation (contrast *key*). Authoritative: SPEC.md §5.2.1.
- **slab** — a compressed span of source text, stored by us and cut on entry
  boundaries, from which every snippet is re-derived instead of refetched from
  Zotero. Authoritative: SPEC.md §5.2.2, which owns the size ceiling.
- **stage** — one step of the indexing pipeline: record, extract, chunk, embed.
  Each carries its own key, its own ledger rows and its own counters.
  Authoritative: SPEC.md, intro; the keys are SPEC.md §5.2.1.
- **term** — a property the user meets, and what a goal's conjunction runs
  over. Binding is per clause rather than per requirement, so one item can be
  in by one clause and out by another. Sorted by one question per clause: if
  this clause fails and nothing else changes, is what the user can know or do
  any different? Its retired counterpart, *instrument*, is in the historical
  section. Authoritative: DECISIONS.md (2026-08-31).
- **validation attestation** — an optional content-free report that one exact
  embedder entry passed the automatic compatibility fixture on a stated runtime
  shape; it is not a retrieval-quality judgement. Authoritative:
  SPEC.md §5.2.6.
- **warm** — describes a query answered with the embedder already resident and
  the store already open: nothing loads and nothing builds when the clock
  starts, which is the state R6's latency bounds are stated for; the first
  query after a start is not one. Authoritative: SPEC.md R6; what the
  time is spent on is SPEC.md §5.2.9.
- **watermark** — a resume cursor stored per origin and library, legitimate
  only where the underlying version sequence is genuinely monotonic; the local
  full-text sequence is mixed, so no watermark column exists for it.
  Authoritative: SPEC.md C1; its use is SPEC.md §5.2.4.

- **works for me** — the acceptance standard for the ladder's top three rungs
  taken together: the user is the author, the languages are his, the pinned set
  is his questions, and the deciding level is his own library rather than a
  fixture standing in for it. Authoritative: DECISIONS.md (2026-08-31).

### Inherited, Zotero

These mean here what they mean in the platform. Each entry says where this
document relies on it.

- **attachment** — the child object holding a file, from which body text is
  extracted; an item itself has none. Zotero's; our use of it is SPEC.md
  §5.2.3.
- **`dateAdded`** — an item's creation timestamp, which is what "newest" means
  throughout this design's ordering. Zotero's; the total-order key built on it
  is SPEC.md §5.2.8.
- **`/fulltext` census endpoint** — the local API route listing, for one
  library and in one unpaginated response, the full-text version of every
  attachment that already carries one. Zotero's; how the
  design diffs it is SPEC.md §5.2.4, and why it must never be cursored on the
  local transport is SPEC.md C1.
- **item** — the platform's unit of bibliography, one record with zero or more
  child attachments and notes. It is deliberately *not* this design's unit of
  answer. Zotero's; the entry ruling is SPEC.md, the first ruling.
- **`Last-Modified-Version`** — the response header carrying the library
  version a read observed, and the value a client stores to resume from.
  Zotero's; the watermark built on it is SPEC.md §5.2.4.
- **library / `libraryVersion`** — a personal or group collection of items, and
  its version counter; item keys are unique only within a library. Zotero's;
  the merged-index consequence is SPEC.md D4 and SPEC.md §5.2.2.
- **local API** — the HTTP interface the desktop application serves on
  loopback, unpaginated and unthrottled, and the transport this design uses.
  Zotero's; the politeness rules that apply to the web transport and not to
  this one are SPEC.md.
- **`?since=` version cursor** — the query parameter asking for everything
  changed after a given version. Zotero's; it is a legitimate cursor on the
  item sequence and not on the local full-text sequence, per SPEC.md C1.
- **`Zotero-Server-ID`** — the response header identifying which database
  answered, within which alone versions are comparable. Zotero's; the
  partition it forces on stored state is SPEC.md C1 and SPEC.md §5.2.2.

### Inherited, SQLite

- **`bm25`** — the ranking function the full-text engine exposes, scoring a row
  against a query under per-column weights. SQLite's; the weights, and when
  they are tuned, are SPEC.md §5.2.2.
- **FTS5** — SQLite's full-text search extension, the keyword half of this
  design's retrieval. SQLite's; the table layout, the tokenizer and the
  contentless mode are SPEC.md §5.2.2. The cost of constraining a match to a
  row set is C2's constraint, on upstream's stated rationale; the figure under
  it is X4's to measure and is not measured yet (SPEC.md §5.3).
- **`unicode61`** — the tokenizer the full-text index uses, configurable for
  diacritic folding; the query and index normalizers must agree on it or a term
  can never match. SQLite's; the configuration is SPEC.md §5.2.2 and the
  agreement check is the fold gate in SPEC.md §5.2.8.
- **WAL** — write-ahead logging, the journal mode under which readers answer
  while a writer commits, which is what makes several servers on one file
  possible. SQLite's; the connection settings are SPEC.md §5.2.2.

## 3. Requirements

### Intro

This section lists the user requirements, numbered R1 to R35\* with gaps — a
retired number is never reused. Each is written as a testable property:
something the test harness, or a careful reader, can check. A "stage" below
is one step of the indexing pipeline: record, extract, chunk, embed.

**Normative language.** The R-items below follow RFC 2119. MUST, and its
synonym SHALL, marks a firm requirement. SHOULD marks a preference that may be
set aside for a stated reason. MAY marks something optional. These words bind
only in upper case. The same words in lower case are ordinary prose and carry
no such force, which is what lets the surrounding narrative use them freely.

### The four foundational rules

1. **The unit of answer is the entry.** A dictionary or encyclopedia is one
   Zotero item but many entries, so retrieval and deduplication work on the
   section, not the item. An encyclopedic item may legitimately give several
   distinct hits where a focused article gives one, and where an entry
   heading is known, the heading is the citation locator.

2. **The record is the semantic core.** Title, abstract, and keywords are
   the main semantic targets, and indexing works three priority classes in
   this order: an item's record, then its notes and annotations, then its
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
   body text is not, which is the metadata-only state R1 and R17 already carry.
   This is the perimeter R1, R8, R12 and R16 each presuppose and none of them
   states.

### Requirements

Each item is a name, one sentence, and a paragraph. The **sentence** is the
promise, written so it can be read alone and tested by someone who has read
nothing else here. The **paragraph** unpacks it: what the sentence implies, what
was decided about it, and which document owns any number it depends on. The
one-word name is the handle the rest of this document cites.

#### Coverage and convergence

**R1. Coverage.** Every item in the search perimeter MUST become searchable
without anyone asking for it, and the system MUST NOT need a manual rebuild,
whatever state it is in.

Coverage MUST grow in ruling 2's class order, newest-first inside each class:
the crawler works a priority order, not a page cursor, and recency orders
*coverage*, not answers. An attachment that yields no
text MUST be treated as done rather than retried forever — it counts as covered,
marked metadata-only, its reason recorded and reported — so full coverage stays
reachable and honest at once. Per D8 below, OCR is out for now and the stage keys
leave room for a future extractor.

Upgrading the machinery is one of those states. When an upgrade anywhere in
the chain — extractor, segmenter, embedding model — supersedes work already
done, full coverage SHOULD converge to the latest chain: the superseded items
are reprocessed unattended, newest-first in the same class order, so a library
of 5 000 documents extracted old-style refreshes itself with nobody asking.
Until overtaken, the old results keep answering, labeled as such — an upgrade
never empties the index and never demands a rebuild, and at most two
generations coexist, so this is a migration promise, not a fleet of resident
models.

**R4. Availability.** The index MUST answer queries at every moment of its life,
including during its first build.

An index that goes dark while it works is worse than a partial one, so partial
answers ship from the first passage indexed. This obliges honest coverage
reporting, which R17 carries: without it, a partial index is indistinguishable
from a complete one and the user cannot tell a gap from an absence.

**R17. Reporting.** "How much of my library is searchable?" MUST get a human
answer, per stage, with a date.

The answer is N of M items — items per D1 — for each stage, with the
most-recent-covered date, and metadata-only items counted in the denominator
with their reason. Every stage MUST also report what it processed and which
input triggered it, so one edited item shows up as one unit of work rather than
as a wave. Status MUST name the execution device actually serving, on every
machine, since a user who cannot see that cannot explain the speed they get.
And it MUST stay fast enough to be asked: status is the only window into R1's
coverage, agents poll it every few seconds forever, and it MUST answer while all
three queues run at a cost that does not grow with the size of the library. The
rate rather than a wall clock, for R32's reason — a flat millisecond figure
silently fixes the library size, and the promise is that asking costs the same
at 1k items and at 60k. What the band is, and what the time is spent on, is
SPEC.md §5.2.9.

**R32. Buildtime.** On a laptop-class machine with no GPU, a full build with
the default configuration MUST index at 150 ms per passage or better, which for
a 15k library means records searchable within one hour and body text within a
day. It SHOULD reach 75 ms per passage, which halves both figures.

The rate is the promise and the wall clock is what it means. A wall-clock number
alone would silently fix the library size — "inside a day" promises a 15k
library something and a 60k library nothing — and the rate holds at any size.
Per passage rather than per item, because R8 makes items deliberately
non-uniform: a per-item rate measured on short papers says nothing about a
15 000-page PDF. Records land inside the hour while body text is still arriving,
which is ruling 2's class order seen from the clock. The machine is named
because a time bound with no machine attached is not a bound; which laptop, and
the arithmetic from the measured passage count, are SPEC.md §5.2.8's. Finishing
today is a property of the configuration rather than of the hardware, which is
why this is its own promise and not a clause of one about GPUs. A full build,
not only the first: a rebuild from nothing is the same work on
the same machine, and a user whose index was abandoned under a foreign schema
stamp waits exactly as long as one who has just installed. What these bounds are
not is a library already in service, where R3 bounds the cost of staying current
and R35 the delay before a change is noticed.

#### Change and cost

**R3. Proportionality.** The cost of staying current MUST be proportional to
what changed, never to the size of the library.

Recompute exactly what is downstream of a changed input; the unit of
invalidation is (item × stage). A resync or an extractor upgrade that advances
version counters MUST re-embed nothing whose bytes are unchanged. This project
once shipped a defect that re-marked 92,7 % of a library as changed, forever,
and that is the cautionary example the clause exists for.

**R35. Discovery.** The system MUST notice a new, changed or deleted item
within one minute, without anyone asking.

Noticing is not indexing. A new or edited item is queued inside the minute and
becomes searchable in its class's turn, so a 15 000-page PDF is noticed as fast
as a note and indexed a great deal slower. Deleting is the strict case, because
removing text costs nothing: text the user deleted MUST stop being served
inside the same minute. When Zotero is not running there is nothing to notice,
and the minute starts when it comes back. This is the other half of staying
current — R3 bounds what it costs, this bounds how long it takes — and they
fail apart, since a library can be re-indexed at exactly the right cost and
still take a day to notice a deletion. R1 says an item becomes searchable and
never says when the system learns it exists; R15 says deleting removes text
everywhere and never says when; R32's bounds are a full build's, not those
of a library already in service.

#### Corpus

**R8. Scale.** A 15k library and a 15k-page PDF MUST both be ordinary input.

The design point is at least 10 000 documents with full text and the system MUST
work at that size; the known red zone is that a full vector scan approaches 1 s
there. A 15 000-page PDF MUST be first-class too, not an outlier to cap away —
the 44,9 MB dictionary is the one in hand — and under ruling 1 it is a
collection of entries among peers. The two sizes are one promise because a
library is large in both directions at once.

**R16. Notes.** My own notes and annotations MUST be searchable, not only the
papers I collected.

Per D7 both are in: a note written in the reader and an annotation anchored to a
page are the reader's own words about the corpus, and a search that cannot find
them searches somebody else's library. They are child items, which is what makes
them easy to miss in a crawl that asks only for top-level items.

#### Query

**R5. Scoping.** Scoping a search by collection, tag, item type or date MUST be
enforced before any answer is truncated.

Never by filtering a top-k list after the fact — the k best-scoring results —
and then presenting it as complete. One correction from the pre-design
code-reading and measurement passes: "pushed into SQL" MUST NOT be read as
constraining the MATCH operator of SQLite's FTS5 engine, which measures at
seconds per query at library scale. The obligation is on the honesty of the
result, not on which operator enforces it.

**R6. Latency.** A warm query MUST answer within 3 seconds and SHOULD answer
inside 700 ms, and MUST never wait on freshness work bigger than a single
request.

Freshness work on the query path is limited to O(1) requests; anything larger is
scheduled and never awaited. The three seconds are the escape and the 700 ms is
where a warm query lands when nothing is wrong: a sufficient reply now beats an optimal
one later, which is the trade this promise names. What the time is spent on —
probe, embed, keyword search, the scan, the fusion — is SPEC.md §5.2.9.

**R18. Emptiness.** An empty answer MUST say whether nothing matched or the
scope is not indexed yet.

Stated for the scope the query asked about, never for the library as a whole: a
user who searched one collection is owed the truth about that collection. The
two cases call for opposite actions — rephrase, or wait — so collapsing them
into one blank result wastes the user's next move.

**R24. Locator.** A hit MUST lead to the page it came from, and one entry MUST
give one hit.

A full-text hit leads to its page; an estimated page number MUST say it is an
estimate, per D10; and the primary locator MUST be the entry heading, per ruling
1. Where the text came from Zotero's structured-text pack (§5.2.4), the page is
the block's own anchor and is not an estimate; the answer says which kind it
is. As that ruling amends it — D9 dissolved — deduplication is per section,
and a single document MUST NOT crowd other items out of the candidate pool
before deduplication happens. When many returned hits come from one document, the
result says so. Declared renderings of one work MUST collapse to one answer row
before the cut to k; an inferred similarity MUST NOT collapse rows.

**R33. Modes.** Exact-word search, meaning-based search, and the two combined
MUST each work.

A query naming a rare exact string MUST return the item carrying it. A query
that paraphrases its answer without sharing a content word MUST return that
answer. Where both signals are present but weak, the combined answer MUST rank
the document they agree on above one that only a single signal favours — the
case that catches a fusion which has quietly dropped a side. Where the interface
offers a retrieval mode, the mode selected MUST be the mode served. The
combination rule belongs to SPEC.md §5.2.6.

**R34. Recall.** For every query of the pinned set, the answer MUST come back
within the first ten results.

The pinned set's answers are known-correct and known to be in the corpus, so
this is a floor on what comes back rather than a score. Per D11 it fixes the
answer set and not its order: order inside those ten is unconstrained. Re-pinning
the set is a commit whose set diff is the review artifact, per SPEC.md §5.2.8,
which is what stops a failing query being deleted instead of fixed.

#### Multilingual

**R7. Languages.** The default path MUST work in English, French and
Vietnamese with no configuration, and SHOULD work in Arabic, Chinese, German,
Hindi, Russian and Spanish.

The default embedder MUST be multilingual. Setting a second-tier language aside
is allowed and MUST be stated, which is what separates a tier from a wish. The
second tier names one language per script and morphology class and never one per
community: right-to-left, Cyrillic, no word boundaries, compounding, abugida,
and Latin-with-diacritics, which Spanish stands for. Chinese in that tier is the
explicit CJK decision this item used to defer, and it carries the keyword half
with it — the two-gram geometry the platform ships is what a Chinese query term
has to survive. The English stopword list is a known ranking bias whose deletion
is already decided. Every other language rides the default path untested; see
"Out of scope".

**R29. Crosslingual.** A query in English or French MUST retrieve relevant
Vietnamese content without the user translating anything.

R7 promises each language its own lane; this promises the lanes connect. The
cross-lingual property MUST be gated separately from the monolingual one, so a
regression names which promise it broke. When the semantic path is unavailable
the reply MUST say that cross-language matching is down, rather than return a
silent miss that reads as an honest empty. Query translation is not the
mechanism; see "Out of scope".

#### Custody and lifecycle

**R10. Locality.** Without an explicit opt-in, my library text and my queries
MUST NOT leave this machine.

The default build and query path make zero external calls. The one-time
model-weight download is the sole exception, and it is named rather than
discovered: an exception a user has to find out about is not an exception, it is
a surprise.

**R15. Deletion.** Deleting an item MUST remove its text everywhere. The target MUST declare every location in which it creates derived state. After uninstall, none of that state may remain, and no target-created derived state may exist outside the declaration.

Deleting an item removes its text from every stage's store and from the queues
between them, not merely from search results — text that survives in a queue
comes back. Deleting means what the platform shows: an item moved to the trash
has left the search perimeter, per ruling 4, so removal fires at trashing, and
emptying the trash later changes nothing the index can see; R35's minute starts
at the same event. At the other scale, index state, queues, watermarks,
downloaded models and generated caches are target-created derived state. Every
location in which they can exist is declared, the target's real uninstall
surface removes them, and a residue inventory checks that the declaration is
complete. User-authored library data and externally supplied configuration are
not derived state.

**R22. Pause.** There MUST be one obvious way to stop all background work, and
it MUST hold across restarts.

One way, because a user hunting for a second switch has already lost the machine
they were trying to quiet. Holding across restarts, because background work that
resumes on its own after a reboot was never stopped, only interrupted.

**R23. Migration.** An index written under a different schema version MUST end
up serving, in either direction, without anyone deleting files by hand.

Either direction: a newer build meeting an older index, and an older build
meeting a newer one, which is the case every user hits the day a version is
rolled back. The clause is about ending up serving — abandoning the file and
rebuilding silently is a failure of this promise, not a way of keeping it.

#### Multi-library and multi-process

**R12. Libraries.** Group libraries MUST be searchable exactly like my own, and
indexing one library MUST NOT erase another.

Per D4 there is one merged index, with the library as one more R5 filter
alongside collection and tag. The second clause is the sharper one: a build for
one library that meets an index belonging to another MUST refuse rather than
overwrite it or append to its rows, because the failure is silent data loss
reported as success.

**R13. Concurrency.** Two server processes on one data directory MUST both
answer queries without corrupting the index or doing the same work twice.

The honest restatement accepted in SPEC.md §5.2.5: no passage is ever
*committed* twice, and duplicate *compute* is bounded at one embed batch plus
one in-flight document's re-fetch and re-segmentation per failover. Two processes is the ordinary case rather than the exotic one — one
per client application — so the index has to expect company.

#### Normalization

**R19. Normalization.** In semantic and hybrid search, when a document and a
query write the same word in different but equivalent forms, the query MUST
still find the document. Lexical search is exempt: there the user has asked for
the string as typed, and matching it literally is the promise.

Otherwise that query term can never match anything, in any language, and the
failure is invisible: the search returns nothing and looks like an honest miss.
Which forms count as equivalent is pinned by the fixture corpus, per script
class, and R7 names the classes; this clause does not enumerate them.

The character-folding sweep is a gate over our own tree, not evidence for this
requirement: it reads a normalizer's source, and a promise is kept or broken
where a user can see it. SPEC.md §5.2.8 owns it with every other gate.

### The resolved decisions

| | resolution |
|---|---|
| D1 denominator | Coverage counts **items**; metadata-only items count, with their reason. |
| D2 hosted mode | **Out.** The redesign binds the desktop; the four privacy requirements that only applied to hosted mode are dropped. |
| D3 embedder change | **Serve-stale.** The old model's vectors keep answering, labeled, until re-embedding overtakes them newest-first; semantic coverage never drops to zero at the moment the new embedder is adopted. |
| D4 group shape | One **merged** index; the library is a filter facet. |
| D5 query semantics | A quoted **phrase** matches as a phrase, and AND/NOT are honored, on both backends (keyword and semantic); bare terms stay recall-friendly. |
| D6 twin attachments | **First-with-text per language.** Per item, the deterministic first attachment in each detected language is indexed for body text; same-language siblings get a recorded skip reason. |
| D7 own-words scope | **Both** notes and annotations. |
| D8 image-only PDFs | **Leave room** (OCR is out today). |
| D9 long-document weight | **Dissolved** by the entry ruling. |
| D10 page fidelity | **Labeled estimate.** |
| D11 what the golden pins | The answer **set**, not the order. |

### Out of scope, said out loud

These nine\* things are deliberately not promised, so that silence does not
read as a promise:

- **Work does not travel by itself — but it may arrive by copy.** The index
  is per-machine, and vector export and sync stay out of scope; a second
  machine re-earns its own index unattended via R1. What is admitted is
  one-shot adoption: a data directory copied whole from
  another machine proves its own embedding chain before a row serves and is
  adopted rather than rebuilt, its foreign change signals count for nothing
  until re-earned, and R1 converges the difference. Never a shared live file.
- **The rebuild is the backup.** The index is derived data, exempt from
  backup; no snapshot tooling.
- **Recency orders coverage, not answers.** R1's newest-first clause is an
  indexing frontier; ranking stays relevance-only.
- **OCR is out.** Image-only attachments converge as metadata-only.
- **Hosted mode is out.** The redesign binds the desktop; the OAuth server
  keeps today's behavior.
- **Untested languages are named, not implied.** Everything outside R7's two
  tiers rides the default path and is expected to work there, but nothing
  measures it, and a language nobody measured is not a language anybody
  promised. Portuguese and Italian sit in the class Spanish represents, so they
  are covered by argument and not by measurement, which is the weaker thing and
  is said as one. Greek and Hebrew are in no tier's class at all.
- **Query translation is out.** R29 rides the embedding space, which is the
  only channel that crosses languages. No translation service and no local
  translation model joins the default path.
- **No enumeration.** Semantic search returns a bounded page; exhaustiveness
  is the job of R5 narrowing, not of paging.
- **The library is read, never curated.** Zoteus does not tag, link, split,
  merge or translate the user's records; it reads what Zotero holds and
  reports what it finds, candidate relations included. Managing a
  multilingual library is a separate question from searching one.

### The goals ladder

The sheet is one flat list of promises. The order they are made true in is an
implementation strategy rather than a statement about the system: two efforts
could hold these same requirements and climb them in a different order without
either being wrong here. So it is not specified in this document.

[README.md](README.md)'s "The goals ladder" owns it — the five goals in the
user's words, each rung's roster, the build order, and what the ladder does
not say. The rosters themselves are ruled in [DECISIONS.md](DECISIONS.md) and
checked against it.

---

\* A hand-maintained count: re-verify it whenever the sheet changes.

## 4. Constraints

### Intro

This section lists the constraints, C1 to C3: facts about Zotero, the
upstream project, and the user's machine that the design must operate under.
A retired constraint number is never reused, as for the requirements: C4 was
dissolved on 2026-09-03 because it stated a mechanism rather than a fact, and
its pieces are named in `DECISIONS.md`.

### C1 — everything the index stores is derived data

The index stores derived data only, in a chain of three links:

1. extracted text derives from (attachment file, extractor), where the
   extractor is one of two identities: Zotero's flat extraction, or its
   structured-text pack, which names its own processor version and source
   hash in its metadata (§5.2.4);
2. chunks derive from (extracted text *or* item metadata, chunker identity
   and geometry), where the heuristic segmenter's identity folds into the
   chunker key, per the boundary ruling (§3's third foundational rule);
3. vectors derive from (chunks, the complete embedder-entry fingerprint and
   model). The fingerprint includes every registry field that can change a
   vector; a display label and aggregate validation standing do not. Execution
   provider enters it only where SPEC.md §5.3's cross-provider rule requires
   that distinction.

A "key" is the recorded identity of the inputs that produced a piece of
derived data. Work is stale exactly when a stored key no longer equals the
current key, and invalidation propagates downstream only.

The extractor's identity is visible only in-process. Over HTTP, the
observable proxy is the `/fulltext?since=` counter. It carries a *sync*
version: the server stamps it, and re-extraction is not what moves it.
Does a purely local re-extraction re-stamp version 0, which would make it
invisible to this counter? Experiment X6 owns the answer, and a source read
now bears on it (`fulltext.js` at `9e28eb0`, ticket 0180, with the author on
`DECISIONS.md`'s awaiting list); SPEC.md §5.2.4 is
designed to work under either answer. Items and full-text extractions are
numbered on two unrelated sequences (measured: 410 versus 0..25 036).

This constraint is sharpened on three points:

- The local `/fulltext?since=` sequence is mixed. Web stamps, local client
  versions, and 0 for local extraction all appear in one column, so the
  correct filter is `since=0 OR version>since`. Versions can be compared
  for equality per item, but they are never a monotonic cursor: any design
  that uses this counter as a resume cursor on the local transport will
  silently miss locally-extracted text. (Measured: 584 of 8 037 fulltext
  entries at version 0 on the reference library.)
- Version validity is scoped by the `Zotero-Server-ID` header. A different
  server ID means a different database and different versions; item keys are
  *not* a distinguisher, being sync keys unique per library and identical
  across two installs of the same account (`userdata.sql:169`, `9e28eb0`).
  Versions alone carry the requirement:
  stored state MUST therefore be partitioned by server ID. A local/cloud
  label is not enough, because two local profiles share the label and share
  nothing else. Corroboration, read from source rather than measured: Zotero's
  own full-text index keys by local `itemID`, stamps itself with
  `localUserKey`, and rebuilds on mismatch — the same requirement, arrived at
  independently, for the same reason and with the same remedy (`DECISIONS.md`
  2026-08-29).
- This residue is ours alone, and the platform is not a precedent for it.
  Zotero's embeddings layer *does* chase a processor bump with no file
  change: the attachment staleness key is
  `md5(path|size|lastModified|processorVersion)` where the version is the
  current processor's, and the consumer waits for regeneration rather than
  reading a stale pack — `getSections(…, { allowStale: false })`
  (`embeddings.js:2352-2360` and `:2428`, `sdt.js:298-308`, PR head
  `77e2c4b`, read 2026-09-02). A comment fifteen lines above the key still
  describes the older behaviour; the commit that closed the gap
  (`57b30b17e`, 2026-08-20, inside the pull request) did not delete it, and
  the code folds the processor version into the staleness key regardless.
  Cite the key, not the comment.

### C2 — the platform and the upstream project are both moving

Three facts about the terrain:

- zotero/zotero#6012, the draft pull request in which Zotero is building
  its own semantic search, is active and exposes nothing over the local API
  yet.
- The upstream maintainer (oscardvs/zoteus) merges small contained PRs and
  reimplements design-sized proposals himself; the asymmetry is measured in
  both directions, and SYNC.md carries the live count.
- Some twenty other AI plugins are evolutionary pressure, not a runtime
  concern.

The consequence for the design: every pipeline stage (extract, chunk,
embed) is a swappable component, an adapter, identified by its key. The
lasting value is the contract — the MCP tools, coverage honesty, the
freshness protocol, and the filters, all defined in SPEC.md. The
machinery behind the contract is replaceable. Anything sent upstream
decomposes into small PRs the maintainer will actually merge. The index
describes itself (schema version plus artifact keys), so it is openable or
cleanly rebuildable, never silently wrong.

This constraint is sharpened on five points:

- The local API documentation states that "only one API version will ever
  be supported at a time", so a client reads the `Zotero-API-Version` and
  `Zotero-Schema-Version` headers rather than assuming a version.
- The local API has no `/deleted` endpoint; the deletion route left to a
  client is a key-set diff (`format=versions`, unpaginated). Documented as
  such nowhere — the route works and the inference is ours, which is a
  weaker footing than "documented" and is stated as the weaker one.
- Constraining FTS5 MATCH to a rowid set makes FTS5 evaluate the expression
  per row, which costs seconds at library scale. That is #6012's stated
  rationale rather than a measurement of theirs, and the distinction is the
  correction: read at PR head `77e2c4b`, `lexical.js`
  says exactly this in a source comment and cites no figure, then reaches
  our own conclusion in the lines beneath it — the MATCH runs unconstrained
  and the candidate filter is applied after it. The numbers under the claim
  are ours, from X4, and are SPEC.md §5.3's to state.
  MATCH therefore runs unconstrained on the general path, with scoping
  enforced elsewhere. SPEC.md §5.2.6 owns the conditional fallback and the
  threshold experiment X4 measures; it is never the default path.
- The SDT pack (the pack format `structured-document-text`, produced by
  `zotero/document-worker`) is the structured
  extraction the extract stage reads when one exists (§5.2.4). The local API
  neither serves nor creates it; it is read from disk beside the attachment,
  a random-access container with a reader contract
  `{byteLength, read(offset,length)}`, describing itself with exactly the
  key shape of C1. In the shipped 10.0 build only the reader writes one, so
  a pack exists for what the user has opened, 2 of 13 630 attachments on the
  reference library (`bench/results/0007-sdt-probe.txt`); the platform's own
  embedding branch generates one per embedded attachment, which is when
  coverage becomes library-wide. Zotero's own chunker splits on structural boundaries,
  measured in tokens, and embeds the heading path with the text. Two details
  of it are easy to state wrongly, and both were, so they are stated here in
  the platform's terms (read at PR head `77e2c4b`, 2026-08-29).

  The geometry is 120 minimum, 48 overlap, and a maximum of 768 that is
  **a ceiling, not a chunk size**. The source says so in as many words:
  "A ceiling rather than a target: chunks come out paragraph-sized, so this
  decides only how long a text has to be before it's split at all, and how
  far a single oversized paragraph is split." The
  effective budget is a minimum against the live model, not the constant —
  `Math.min(CHUNK_MAX_TOKENS, getModelMaxTokens()) - specialTokens -
  count(prefix)` (`embeddings.js:1642`). Six of the eight registered models
  declare `maxTokens: 512`; the two at 8 192 (`jina-embeddings-v2-small-en`,
  `bge-m3`) are labelled `test:`. So 768 never binds today, and exists to
  stop a future long-window model from emitting 8 000-token chunks. A
  consumer that copies 768 without the minimum copies a ceiling and uses it
  as a target, which is the opposite of what the number is for.

  The chunker also **does not** never cross a section: it merges sections
  below the 120-token minimum forward into their neighbour, asserted by
  #6012's own tests. It never merges two sections each able to stand alone.
  Our boundary ruling is therefore stricter than the platform's: a
  deliberate divergence, not an alignment.
- Once #6012's `bestMatch` saved-search condition merges, it will be the first
  place platform semantic results appear in the local API. The mechanism is
  verified at source (PR head `77e2c4b`, read 2026-08-30): the
  pull request adds a `bestMatch` search *condition* in `searchConditions.js`,
  and the local API already serves `/api/users/:userID/searches/:searchKey/items`
  on `main`. So the crack opens with no new endpoint, and without upstream
  deciding to open one — a saved search carrying that condition is enough.

Zotero 10 moved its keyword index. Verified on 2026-08-29 against the
author's own installation (10.0, build 20260817151751) and the shipped
`fulltext.js` of that build; the evidence is in
`verification/VERIFY-FULLTEXT-SQLITE.md`. Read that report for what it covers
before citing it for more: the schema, the CJK vocabulary and `journal_mode`
are in it, while the main-index vocabulary counts and the `.zotero-ft-cache`
census below are quoted here from no committed artifact and are undeclared to
the figure guard (ticket 0180; the anchors are ticket 0060's action 6).

- The index left `zotero.sqlite`. Userdata step 127 dropped `fulltextWords`
  and `fulltextItemWords` and moved the keyword index into a separate
  attached database, `fulltext.sqlite`. Upstream commit `7c2a1d1`,
  2026-06-30, tagged in 10.0.0 and 10.0.1 only.
- The schema is four contentless FTS5 tables plus their bookkeeping:
  `fulltextContent` (unicode61), `fulltextContentCJK` (ascii, fed
  overlapping 2-grams), `fulltextNotes` (trigram), `fulltextNotesCJK`,
  with `fulltextIndexState`, `noteText` and `fulltextIndexMeta`. On the
  author's library: 13 090 content documents, 386 CJK, 1 200 notes.
- A row identifies an item directly. `fulltextContent.rowid` is the local
  `itemID`, joined 13 090 of 13 090 against `fulltextIndexState`.
- Contentless means the source text is discarded, not that the index is
  opaque. The stored column and `snippet()` both return nothing, measured,
  so a document cannot be printed back. What survives is the whole inverted
  index, and `fts5vocab` reads it: 670 680 distinct terms, 19 139 711
  (term, document) pairs, 135 973 731 occurrences with their positions.
  Constrained by term, `fts5vocab(…, 'instance')` returns the pair
  `(itemID, token offset)` in under a millisecond; constrained by document
  it is a 7,0 s full scan, so reconstructing a document works but is not a
  route. The bound is weaker than "which items, never which passage": a
  query term locates itself inside an item. Turning that token offset into
  a character position means reproducing Zotero's own tokenization, which
  an approximation did not — occurrence counts matched exactly on three
  documents while token indices drifted +13, +2 and 0.
- The extracted text lives in `.zotero-ft-cache`, one file per indexed
  attachment: 13 631 files, 819,4 MiB, plain UTF-8 carrying no markup. It
  is two extractor generations. Of 8 590 PDF caches, 4 708 carry form-feed
  page separators and 3 882 do not, split by mtime at roughly 2024, and the
  form-feed count equals `fulltextItems.indexedPages` for 4 471 of the
  4 708. The current path is `Zotero.PDFWorker.getFullText` writing straight
  through; nothing in the shipped app writes the older `.zotero-ft-info`
  sidecars, of which 2 788 survive on disk. What is observed is that caches
  written between 2019 and 2024 are still present on a machine now running
  10.0, so upgrading did not rewrite them; that no upgrade ever re-extracts
  is an inference from it, untested here. `rebuildIndex()` in `fulltext.js`
  would re-extract and has no caller in the shipped app. Either way both
  generations are live today, so page boundaries cannot be assumed.
- Whether it is readable while Zotero runs is **not established here**. The
  cited report tested the opposite case on purpose — "Zotero was not
  running, deliberately" — and lists the live read as an open question; the
  absence of `locking_mode=EXCLUSIVE` is PR #100's assertion. What is
  measured is `journal_mode`: `delete`, not WAL, so a writer takes an
  exclusive lock and a reader is cheap but not guaranteed available. A
  read-only open with the application up would settle the rest, and nothing
  here has run it.
- Nothing documents any of this. The 10.0 changelog says only "Much faster
  full-text content searches", naming neither the file, nor FTS5, nor the
  split. This is an internal implementation file that has already moved
  once without announcement, which is the C2 risk in its purest form.
- Zoteus does not read it. It reaches full text over the local API
  (`/items/<key>/fulltext` and `/fulltext?since=`), so the move did not
  break it, and the platform's finished keyword index currently goes
  unused. Whether to depend on it is an open design question.

### C3 — the machine belongs to the user

Background work runs at leftover priority. The RAM ceiling is independent
of library and document size: extraction and chunking stream, so peak
memory is proportional to a section batch, not to the document. The embed
stage is the core-hog and MUST be isolatable. One scheduling rule covers
everything: foreground always beats background.

#### Budgets

- background ≤ ~1 core, low priority
- server steady-state RSS ≤ ~750 MB (the original figure was against an
  English-embedder picture, and R7 outranks it)
- pipeline worker peak ≤ ~750 MB regardless of document size (the original
  figure predates the multilingual requirement, and the worker's peak is now one
  token-budget batch plus the streamed decode, the model residing in the
  embedding service, so the ceiling awaits re-pin per SPEC.md §5.2.9)
- pipeline worker killable/restartable at any time with zero index damage

The server ceiling binds per process, the scope its gate can assert; SPEC.md
§5.2.9 states the whole-machine arithmetic alongside it.

Whether an ONNX entry actually loads and preserves its declared geometry is an
environment fact, not a property of the model name alone. Runtime version,
operating system, architecture and execution provider can turn the same entry
into a working, degraded or unloadable one. A remote attestation can establish
that another installation saw a shape; it cannot replace the local check on the
machine that will create or query the index.

### Politeness (network transports, from each provider's official docs)

One clause binds every network transport the design admits: a concurrency
cap per provider, a 429's `Retry-After` honored with exponential fallback,
and a refusal or a timeout surfacing as a labeled state rather than as a
build that dies (DECISIONS.md 2026-09-02). Toward the Zotero web API the cap
is 4 concurrent requests, and `Backoff: <seconds>` is honored on ANY
response, including 2xx. Both come from the web API's own documentation,
where the concurrency figure is a recommendation to clients rather than an
enforced ceiling. The local API's data endpoints have no rate limits and are
unpaginated by default, so the clause never binds on the transport this
design uses; `/api/local/authorize` is the one exception, capped at 5 per
60 s, and the pipeline never calls it. The API embedder of §5.2.5 is
bound at its provider's own cap.

### The concurrency hint

Three asynchronous processes (extract, chunk, embed), independently paced,
with queues between them, for two reasons: keyword availability never waits
on embedding, and an OS process can be nice'd, observed, and restarted. The
design realizes this as two OS processes and three ledger-paced loops
(§5.2.5).

## 5. Design

### Intro

The design below is stated in terms of the zoteus codebase, because that is
where it was measured; its mechanisms are this specification's answer
wherever the capability lands.

This is the current design. It owns every design number: the gate
thresholds (§5.2.8), the experiment decision rules (§5.3), and the budgets
(§5.2.9). The predecessor design ("The Settled Ledger", called v1 below) is
superseded.

Seven facts about upstream shaped the design below. They were read at v1.7.0
(`c5d25aa`), where all seven were exact; five have since been repaired, four
of those by the maintainer acting on this repository's own filings. They are
therefore stated against the reviewed baseline `b0e0bc8` (v1.13.0), because a
reader takes a premise as current unless told otherwise. Every line number
below was re-read there rather than carried: the v1.13.0 diff moved all but
one of them without changing a single mechanism, which is the reason a
citation is re-opened at each bump instead of retyped.

Still true there. `DEFAULT_FULLTEXT_MAX_CHARS = 40_000`
(`fulltext-source.ts:11`) truncates the 44,9 MB living example roughly
1 100-fold — the one citation the bump left where it was, in the one file the
release did not touch. Changing embedder drops every vector at open
(`dropStaleVectors` → `clearVectors()`, `index-manager.ts:638`).
`clearStore()` sits in the build path (`index-manager.ts:800`).

Repaired since. The query tokenizer folds Unicode — `normalizeForSearch` then
`/[\p{L}\p{N}]+/gu` (`tokenize.ts:221`, `4f61b2a`, v1.7.2). `busy_timeout` is
set to 10 s on both the writable handle and the read-only probe
(`sqlite-index.ts:499` and `:590`, `80f8aa0`, v1.7.1). `SCHEMA_VERSION` is read
before any DDL, through `reconcileSchema()` (`sqlite-index.ts:585`, `fd51659`,
v1.9.0). Builds no longer crawl `top:true` alone: a second pass indexes child
notes and annotations, on by default (`own-words-source.ts:132`, `d8266f7`,
v1.11.0). The fifth is this repository's own, merged as PR #46 and #47 in
v1.13.0: the 29-word English stopword set is deleted, so no word is dropped
from any document on either backend, and what a query prunes is a droplist
derived from the library it is searching. What the design owes each of the
five is unchanged; what has changed is that none of them is a live defect, so
none may be cited as one.

---

### 5.1 What changed since v1

v1's skeleton survived every lens and every critique with one amendment:
durable (item × stage) ledger rows in SQLite — compute → guarded commit, the
per-row lease claim retired by the sole-writer ruling (§5.2.5) — control
through a pipe and durable work through the database, a
write-free query path, and two OS processes. R13 (second process), R22 (durable pause)
and R17's work counters each turn out to *want* that skeleton: every one is
a one-row concern on a substrate that already exists. Also carried over:
census-seeded newest-first discovery (a census is a full listing, every
item or every fulltext version, fetched whole rather than paged),
micro-batch commits, the int8 vector plan with its X1 gate, the stored-norm
dot product, slabs, the derived vector sidecar (vectors live in a file
beside the database, derived from it), probe-don't-fix,
sideline-never-delete (an unreadable index file is moved aside, never
deleted), the recovery-verb grammar, and the failure policy. The failure
policy
(transient/persistent split, bisection quarantine, reachability gating,
backpressure counted in items; mechanism spec unchanged from v1) carries two
amendments. Quarantine auto-clear now keys on the
*content* signal chain, not on raw counter movement, so a resync cannot
mass-replay every poison input. And R1's terminal states (`empty`) are
*done*, not failures: different bookkeeping, different sentence in status.
The stopwords/tokenizer fix stopped being a plan: it is PR #19, merged
upstream 2026-08-27 (`4f61b2a`).

Three forces changed the rest.

1. **The rulings changed the units.** The unit of answer is the entry, not
   the item; the record is the semantic core and indexes first; chunks
   respect entry boundaries and carry their context. This killed v1's
   two-column FTS layout (FTS: SQLite's full-text search engine; replaced by
   per-field columns, §5.2.2), its
   collapse-to-items ranking (replaced by entry collapse, §5.2.6), and its
   single-figure coverage (replaced by the coverage sentence and counters,
   §5.2.8).

2. **Observability became the requirement.** v1 designed an engine whose
   promises (convergence, newest-first, budgets, edit costs, custody) were
   mostly unobservable. Sheet v2, the consolidated requirements and
   constraints now in this document's Requirements and Constraints
   sections, makes
   observability itself the requirement, so v2 designs the instrument panel
   and the gates beside the engine.

3. **Two measured facts killed v1 machinery.** The local `/fulltext`
   sequence is mixed and must never be cursored: v1's ascending-sweep
   freshness would have silently lost locally-extracted text (the 584
   measured version-0 entries prove the loss non-empty), and
   census-equality replaces it (§5.2.4). And constraining FTS5 MATCH costs
   seconds at library scale (FTS5 evaluates a rowid-constrained MATCH once
   per row), so v1's filter pushdown dies as worded. Unconstrained MATCH
   plus a guaranteed-fill bitmap filter replaces it (§5.2.6).

Other reversals worth naming, each with its reason. Extract is no longer
keyed by the version counter alone, because R3's counter-churn clause and the shipped
92,7 %-changed-forever defect killed that reading: signals and keys are now
separate (§5.2.1). Fraction-weighted reciprocal-rank fusion (RRF) is adopted
behind the golden gate (§5.2.6): v1's rejection rested on wrong arithmetic,
verified empirically. Pause is a durable row, not a pipe message, because
today's `stop` was verified to cancel one job while `auto_build` restarts
on the next query (§5.2.7). Unknown-schema handling is read-compatibility
gating plus a new filename (`search-index-v2.sqlite`), because no protocol
can bind binaries that predate it: a v1.7.0 sibling reaching `clearStore()`
against an in-place upgraded file would erase every library (§5.2.7). And
v1's item-collapse PR is folded into the entries conversation: shipping
item-collapse now would ship exactly the framing the entry ruling rejected.

---

### 5.2 The architecture

#### 5.2.1 Signals vs keys

Every stage row stores *signals* and *keys*, never mixed.

- A *signal* is a Zotero version counter, scoped by server identity, and
  only ever compared for equality. A signal mismatch schedules
  *verification*, one fetch plus one hash, never recomputation.
- A *key* is `(content hash, tool identity)`. Work is stale exactly when the
  stored key differs from the current key.

R3's counter-churn clause falls out structurally: a resync flips
signals, the verify pass re-hashes, the hashes match, and nothing downstream
moves. R17's counters record thousands of `resync.noop` and zero
`resync.done`, so the counter that once hid the 92,7 % defect now proves
its absence.

The stage keys:

- **record**: a field-tagged `record_hash`. The canonicalization version
  folds into the tool identity, so a canonicalization fix is a labeled key
  bump.
- **extract**: `text_hash` over the streamed bytes.
- **chunk**: `(text_hash, segmenter id+version, chunker id+geometry)`. The
  segmenter lives inside the chunker key, exactly as the boundary ruling
  directs.
- **embed**: `embed_hash`, the hash of the full embedded text including the
  context prefix, with an EXISTS guard on deletes, so removing one row
  never removes a vector another row with the same hash still references.
  Hashing the chunk text alone would let a vector computed under an old
  heading silently keep serving under a new one.

Honest restatement of that benefit: *unchanged regions never re-embed*,
and a segmenter bump re-embeds only what it actually touched. And one
disclosed R3 residue: a counter-churning resync still costs
O(changed-attachments) local fetches before the hashes stop the chain.
Fetch-and-hash is the price of verification, stated rather than hidden.

#### 5.2.2 Storage: one file, one schema, every row library-keyed

The store is `search-index-v2.sqlite`: `busy_timeout=5000` on every
connection, then `PRAGMA auto_vacuum=INCREMENTAL`, and only then WAL mode
and `synchronous=NORMAL`. That order is the specification, not a
preference. auto_vacuum is a no-op once anything has written the database
header, and `PRAGMA journal_mode=WAL` writes it — so setting auto_vacuum
after WAL loses it with no table in the file yet, which is a stricter rule
than "before the first table" and the one an implementer has to follow.
The failure is silent either way: the idle `incremental_vacuum` promised
in §5.2.7 would never reclaim a page, and nothing would say so.

**Identity.** `origins(oid, server_id)` is the `Zotero-Server-ID` partition
C1 mandates, and `libraries(lib, oid, kind, remote_id, item_watermark, …)`
hangs libraries under origins. Every downstream row carries `lib`, and
every delete is `WHERE lib = ?`: Zotero keys are unique only per library,
so a merged index without the column would turn R15's delete into an R12
violation. `clearStore()` is abolished from the build path: "rebuild"
is a ledger state (`UPDATE … SET status='pending' WHERE lib=?`), never a
`DELETE FROM passages`. That makes an R12 violation unwritable for
protocol-aware binaries; the new filename (§5.1) fences the binaries that are
not.

**The entry layer.**

- `entries(eid, lib, item_key, attachment_key, ordinal, heading, path,
  kind ∈ record|note|annotation|body|synthetic, char_start, char_end,
  page_est, page_est_kind)`.
- `slabs(sid, lib, source ∈ attachment|record|note|annotation, source_key,
  char range, gzip bytes ≤ 1 MiB, content_hash)`. Record and own-words text
  is slabbed too, because otherwise the first 100 % (phase A) would ship
  hits whose snippets cannot be re-derived.
- `passages(pid, eid, lib, item_key, sid, off_start, off_end, fp)` are
  references, not text. Snippets re-derive from our own slab store,
  never from Zotero: gunzip one slab, slice, verify the fingerprint, and
  return null rather than wrong words on a mismatch, and slab cuts land on
  entry boundaries, not byte counts. The slab range is also the **dispatch
  address**: an embed work order for body text carries
  an entry-sized run of these ranges (§5.2.5), so text already stored never
  crosses the pipe again.

**FTS.** FTS5 with per-field columns, tokenizer `unicode61
remove_diacritics 2`: `fts(title, abstract, creators, tags, pub, ctx, own,
body)`. Per-field columns replace v1's two joined columns for two reasons.
Fields keep their identity for ranking: a tag match no longer scores like a
title match, the record ruling's exact complaint. And joined fields break
phrase search: with `'. '`-joined fields, unicode61 treats `.` as a
separator, so a quoted phrase can falsely match across the seam between two
fields. Body rows put
chunk text in `body` and the heading path plus item title in `ctx`, so
context matches count (weighted) without polluting `body`'s document
frequencies or phrase positions. The *embedded* text is
`«title» › «heading path» ¶ «chunk»`, with the prefix charged to the token
budget, Zotero's own prior art. Creators, venue, and date have a stated
column mapping (the creators and pub columns; date goes into the record
row's `pub`), so no field indexed today silently vanishes. The bm25 column
weights ship as a starting point and are tuned against the golden set once
it is re-pinned at entry granularity, not before. Contentless FTS
(`content=''`, `contentless_delete=1`) where SQLite ≥ 3.43. v1's
external-content layout is the probed fallback, chosen once and recorded in
meta.

**Chunking.** Tokens on structural boundaries: 120 minimum / 48 overlap,
never across entries, with overlap only inside a split paragraph. The maximum
is not a constant but a budget, resolved once per model:

    budget = min(500, modelMax) − specialTokens − count(passagePrefix)

and the resolved budget is recorded in the chunker key, so a model change that
moves it invalidates chunks explicitly rather than silently. The construction
is the platform's; the ceiling is ours, and the difference is deliberate.
Zotero uses 768 as a ceiling rather than a chunk size and bounds that ceiling
against the model window. Its 120 minimum is a flat constant, compared with no
window value. Cycle 2 copied the ceiling, used it as a target, and dropped the
minimum — which is what left a 768-token chunk unreadable by a 512-token
embedder with nothing raised.

The ceiling is 500 because it sits below every window in play. Across the nine
candidate embedders plus the one zoteus loads today, the tightest declared
window is 512 tokens, so the minimum never binds: the budget resolves to the
same number under every candidate, which is what keeps the chunk key stable
across a model swap. Measured, not assumed
(`verification/probes/model-window-census.py`, artifact
`bench/results/0140-model-windows/candidate-windows.json`). A ceiling of 768
would bind at each model's own window instead, giving roughly half again as
much text per vector under a long-window model. That is not free capacity: one
vector is a fixed-size summary, and averaging more text into it degrades
retrieval whatever window the model advertises.

`modelMax` means the minimum over every position-limit field the model
declares. The fields disagree: one candidate declares four of them spanning a
factor of four, the largest being extrapolation past what it was trained on,
and another declares different limits in its config and its tokenizer config.
A construction naming no field is therefore underspecified. At this ceiling the
ambiguity never bites, and the rule is stated so it stays that way should the
ceiling ever move.

The unit is the authored paragraph; the budget is a guard, not a target. Real paragraphs measure roughly 130–390 tokens across
both tokenizer families in play — inside the budget with room to spare — so
the cap binds only on extraction artifacts: glued paragraphs, reference
lists, mangled layout. Splitting those loses nothing an author wrote.

The heading path is charged to this budget, and dropped entirely rather than
truncated when it would cost more than a quarter of it — a deeply nested entry
should not yield a chunk that is mostly breadcrumb. Ordering matters: the
budget bounds the whole embedded sequence, path included, so
`min(500, width) − affordances` is not `min(width − affordances, 500)`.

The embed call is part of this contract. Seg/1's embed path asserts the cap
before embedding — an over-length chunk is a bug and surfaces loudly — and
declares its truncation behaviour explicitly on the call, rather than
inheriting whatever the runtime does in silence (measured: the incumbent
embeds the first 512 tokens and discards the rest without a word). The guard
ships inside the seg/1 upstream change, the change that creates the exposure
— never as a standalone filing.

(For the record: the claim that upstream chunks below Zotero's minimum holds
only for its 512-char *metadata* stride; its 1 200-char body chunks are roughly 250–300 tokens,
inside the band. The move to token-structural chunking rests on the boundary
ruling, not on that comparison.)

**The calibration header's cheap read: a projected vector at a published seed**. Every vector file certifies its own chain by carrying a
fixed calibration set its chain produced, and a reader decides locally by
embedding the same chunks and comparing. That comparison is two tests — per-vector
cosine, and rank agreement over the set's own similarity matrix — and both want
the full fp32 vectors. Beside them the header carries the same vectors under a
random projection to **32 dims**, `R` drawn from a seed published with the format,
as the cheap first read that fails fast before the full comparison runs.

The projection is admissible where a data-derived basis is not, for three
reasons. Its matrix carries no corpus, so a file handed to a stranger discloses
nothing about the library it was built from; both machines derive the same `R`
from the seed, so no basis travels; and its guarantee is distribution-free, so it
does not depend on the geometry of any one model. What it preserves is the ratio
the decision reads — the distance to the nearest other chain over the distance
this chain moves when only the provider changes — at **8 192 bytes per header,
24,0x smaller than the full fp32 header**, keeping a worst case of **29,68x**
against the narrowest unprojected **31,67x**
(`bench/results/0499-chain-identifier/`).

Two bounds ship with it. The threshold this distance is compared against is not
set here: it waits on X8's successor question (§5.3) and must be sized
from measured distributions rather than simulation. And the read is meaningful at
fp32 only — at the 8-bit rungs the same chain read on another execution provider
already moves further than the nearest different chain does, which is the same
boundary §5.2.5's device rule reaches from the cosine side. A hash of any kind is
ruled out cross-machine, sign bits included, and the ledger records why.

*Owed here, and not by this entry:* the header itself, its never-mix invariant and
its fixed 64-chunk set are ratified and this section
still has to carry them, along with §5.2.1's stage keys and the per-file
`embed_hash` guard that ruling reshapes.

**Adopting a foreign index**. A data directory copied
whole from another machine — one-shot, never a shared live file — is opened,
not rebuilt. The copy registers under a new origin row: versions scope by
`Zotero-Server-ID`, so every change signal it carries is foreign on arrival
and is marked stale. Its calibration header is verified locally before any
row serves, and that decides adoptability per file: fp32 rungs travel, an
8-bit rung whose chain includes the device does not, and fp16 has no CPU
provider to land on. Keys are content hashes, so the verify sweep converges
the copy by fetch-and-hash — re-embedding nothing whose content matches — and
R1 re-earns the delta from there. The intended use is embed on the GPU host,
retrieve on the laptop; the remote-embedder alternative stays out of the
design and inside the execution-mode comparison (§5.2.5).

**The segmenter's interface.** The segmenter takes the document's extracted
text and a list of structure signals, each a set of candidate boundaries with
a provenance: pack blocks, the PDF's outline page targets, layout headings,
markup headings, form feeds, a parsed contents list. It returns entries, each
carrying a title, a character range in the text, an optional page range, a
confidence, and the tier that produced the cut. Discovery runs before the
extractor and the cut runs after it: a tier reads structure from the PDF or
the pack, the segmenter cuts the extracted text, and Zotero stays the
extractor. seg/1 is the implementation for the empty signal list and the
fall-through for every tier that comes up empty or low.

**The segmenter, seg/1** is new machinery; the spec lives here. Its primary
target class is **books and proceedings**; the dictionary is a rare case
(ruled 2026-08-31). The clauses below are written for the primary class, and
the dictionary's own machinery is named where it survives as a special case.

- Classify lines, and collect heading candidates from a table of contents
  where the document carries one, chapter and section numbering, and case
  shape.
- Validate the cut set against the table of contents rather than only scoring
  against it: a front-matter contents list names the cuts the document itself
  claims, so a candidate set is checked against a declared answer key.
- A byline-shaped line under a heading may serve as an accept hint where it
  is cheap to recognize. Nothing depends on it: the locator carries no author
  (the byline paragraph below).
- Exploit chapter starts on page boundaries — form feeds — where the
  extraction carries them. They are present in the newer extractor generation
  only (ticket 0120), so this signal is exploited where present and never
  required.
- *Rare case, the dictionary only:* the headword *rhythm*, the median gap and
  median absolute deviation (MAD) over candidate spacing. It is a uniformity
  statistic and it accepts headings only because a dictionary's entries are
  near-uniform in length; a book's chapters and a proceedings' papers are
  unequal by nature, so it measures a property the primary class does not
  have. Kept for the class it fits, never applied to the primary one.
- Cut entries at accepted headings.
- Confidence = the fraction of text inside confirmed entries.
- Below confidence 0.5, fall back to synthetic entries cut at paragraph
  boundaries, ~12k tokens each for every class, labeled as synthetic — see
  the fallback paragraph below.

Entry arithmetic. A book's entry is a **chapter**: tens per item, not
hundreds. A proceedings' entry is a paper, on the same order. That is the
scale the design's entry-collapse, locator and dedup machinery serves.

The dictionary is the illustration of the rare case, not the point (input
assumption labeled, unmeasured): 44,9 MB across ~1 850 entries ≈ 24 KB ≈ 6k
tokens ≈ 8–9 chunks each, so it becomes ~1 850 first-class peers. Under the
primary class the same ruling gives an item tens of peers rather than
hundreds, which is the entry ruling working, not a weaker version of it.

The passage count is not recomputed here: §5.2.9's 567 829 is measured over
the corpus's total text, which segmentation does not change, and it already
carries the one correction segmentation makes — entry boundaries add chunk
closures, so the census errs low by that margin, and by less under chapters
than under headwords since a chapter closes fewer chunks. What moves is
*entry collapse*: fewer and larger entries mean
fewer collapsed hits per item, and a chapter-sized entry answers with a
coarser locator than a dictionary headword does.

The synthetic fallback (ruling 2026-09-02). Below the confidence gate the
fallback cuts at paragraph boundaries into synthetic entries of ~12k tokens,
about twenty chunks or a short chapter, for every class, the dictionary
included, each labeled synthetic. One constant rather than a per-class size,
because the fallback fires on exactly the documents whose class the segmenter
could not read. The dictionary's separate ~6k calibration is retired with it.

The figure is an input assumption, labeled and unmeasured. No experiment
measures it and none could: X5 samples accepted boundaries, and the fallback
fires where there are none. Nothing downstream bounds an entry's size: chunks
stop at entry boundaries, the embed work order packs its own token budget, and
entry collapse yields one hit per entry whatever its length. So the constant
is what sets a structureless document's share of the candidate pool, a
100k-token book contributing at most eight entries, and a synthetic entry's
honest promise is its label.

**The PDF path.** For an attachment at or above a page threshold, the
segmenter reaches for the PDF file itself, through the local API's file-view
redirect, and hands it to a vendored `pdf.js` segmenter returning a title
and a page range per entry, front and back matter included. Two tiers, in
order: the embedded outline — the
bookmark tree — which returns page targets directly and needs no fuzzy
matching; absent that, a layout heuristic on `pdf.js`'s own positioned text,
font size, weight and position per run,
which does not depend on a language's capitalization convention and so is
expected to generalize past English where seg/1's case-shape signal does not.
There is no third, PDF-side fixed-size fallback: when both tiers come up
empty, and whenever the PDF cannot be reached — a linked attachment whose
target moved, a permission error, a file the local API cannot serve — control
falls through to seg/1 above, which owns the confidence-gated synthetic
entries. The length trigger is itself a fallback chain: Zotero's
`totalPages` first, from the per-item full-text response. When that value is
absent and the PDF is reachable, loading it through the vendored pdf.js path
gives `PDFDocumentProxy.numPages`, the source PDF's total, without extracting
page text. Only when the PDF cannot be opened do cache-derived signals apply:
`indexedPages`, literal page-break count, then a labelled character-count
estimate. Each is a lower bound because the historical extraction cap is
unknown. A value at or above the threshold proves long; a value below it never
proves short. If no source total is available and no lower bound proves long,
the length is unknown and takes the long-document-safe path, with the signal
and certainty reported. This errs toward extra structure work, never toward
feeding an undetected monster to the ordinary path.

**The byline.** No tier carries who wrote an entry. Under the synthetic
fallback there is none to find, and under structured segmentation it is
delicate to find; a hit links to its page, so a reader who needs the author
of a chapter, a talk or an entry follows the link. An entry's locator is its
title and its page range. Byline detection is deferred enrichment, not a
requirement.

The segmenter is the design's biggest unmeasured bet — the layout tier and
seg/1 alike; experiment X5 measures both (§5.4, risk 1).

#### 5.2.3 Discovery order: three priority classes, newest first inside each

Three priority classes, in this order: **metadata**, then **notes and
annotations**, then **body text**. Within each class, newer first. That is the
whole ordering rule, and it is checkable at any instant: no item's body text is
indexed before its record.

Ordering is not the only promise. New and deleted data in any class must be
discovered in reasonable time, which is the reconcile tick's job and is stated
in §5.2.4 rather than here.

This section states the classes and the bands. Where they sit relative to
foreground preemption and to the fresh-against-backfill arbitration — the whole
priority order, named once — is §5.2.5.

What the order buys: within minutes a user can find any item by its title,
author or abstract, and body text fills in behind that for hours.

- **Phase A — records.** Every item's record, its fields kept apart. Each
  library is swept `date_added DESC` and the sweeps are merged k-way, so the
  order is newest-first across all libraries at once — recency is the
  researcher's notion of priority and does not stop at a library boundary. A
  record is 1–2 chunks, so 10k items make ≈ 12–15k record chunks; at an assumed
  (labeled) 25 passages/s that is ≈ 8–10 minutes to D1's first 100 %.

- **Phase A′ — own words** (R16; D7 = both). Child notes and annotations
  follow, in a second pass filtered by item type. Upstream did not do this
  when the phase was designed; it does now, and on by default — a second
  crawl on `itemType: 'note || annotation'` with no `top` filter
  (`own-words-source.ts:157`, `d8266f7`, v1.11.0, read at `b05ed69`). What
  remains ours is the ordering: the pass is a *phase* here, after records and
  before body text, which is a discovery-order claim and not a coverage one.

- **Phase B — body text.** Entry-segmented. Each item's first K passages ride
  the main frontier (band 0) and the rest queue behind it (band 1), so one
  15 000-page PDF cannot monopolize the pipeline. Under the sole-writer
  topology the bands are a dispatch policy, not machinery: band 0 is the first
  K ranges of each item in the conductor's dispatch order, band 1 the rest
  (§5.2.5). K is derived from this corpus
  rather than transplanted: K = ceil(median passages per item), floor 16,
  stated in meta.

  Where K lands, and why the number moved. Under the old char-stride chunking
  the measured median was 63 passages/item, giving K = 64. Under the token
  geometry the median attachment measures 18 passages —
  35 for PDFs, 5 for HTML snapshots, whose extraction is mostly chrome —
  so K lands near the floor instead. The census counts per attachment cache, the closest measurable proxy
  for the item until seg/1 exists
  (`bench/results/0140-passage-census/census.json`).

**What is checked, and what is not.** The harness asserts the class order
above, per item, and it asserts that discovery keeps up. It does not assert a
position. The reading that record coverage is a strict
newest-first prefix is rejected:
items enter and leave the library while the build runs, so an invariant over a
positional prefix is asserted over a set that has already moved. The two bands
stay, as anti-monopoly machinery rather than as an observable.

**The band cap is the last fairness rule inside body text.** No per-item round
robin and no recurring passage quantum sits below it, and that is a decision
rather than an omission. Three facts carry it. The class order gives every item
its record and its own words before any body passage is dispatched, so a
monster delays no item's discoverability. The band cap then gives every item
its first K passages before any item's tail, and K sits at the median
attachment's own passage count, so band 1 is not ordinary items queued behind a
monster: it is the tails of the documents longer than the median. And the
fresh-against-backfill interleave one level up (§5.2.5) already splits the body
class three micro-batches to one, so a monster in either lane leaves the other
its share. What stays unbounded is one long document's tail against another's,
inside one lane, and recency is the order this design commits to there.

Both alternatives cost more than that is worth. A **recurring band**
generalizes this cap — band n carrying passages [nK, (n+1)K) of every item —
and holds no new state. It bounds the wait, and pays by finishing no long
document early: every book completes near the end of the body tier instead of
one completing first, while the worker returns to each slab once per round
instead of draining it. A **per-item round robin** is either that same shape
under another name, served statelessly by fewest-passages-indexed-first, or it
holds a rotation cursor over the item set. A cursor is a position over a set
that changes while the build runs, which is the shape vetoed on 2026-08-29 and
declined again by the interleave above it, whose ruling holds no counter for
that reason (DECISIONS.md, 2026-09-01).

Doing nothing costs a visible delay rather than a silent one, since R4 and R17
report partial coverage per item and a tail that waits says so. If a corpus
ever shows the tail contest biting, the repair is the recurring band, which
removes a `min()` from an expression the dispatch order already computes.

Zotero's own draft PR #6012 (SPEC.md C2) orders attachments smallest-first, and
that rejection stands on a different ground than it used to. Smallest-first
buys its anti-monopoly property by ordering the whole body queue on document
length, so the newest long book waits behind every short one. The band cap buys
the same property blind to length: every item's head goes first, and short
documents still finish early because they are band 0 outright. Recency survives
here and cannot survive there, which is the comparison the class order makes
available. The older ground — that neither ordering is asserted as an invariant
over a moving set — defended the retired prefix observable and settles nothing
now that nobody asserts one.

**D6, first-with-text per language.** Per item, exactly one attachment in each
detected language carries body text: the first — ascending `dateAdded`, key
tie-break — that appears in the fulltext census. Language is detected from the
extracted attachment text by a small license-clean detector and stored only as
derived data; the item's language field cannot identify which attachment is
which. A same-language sibling gets a stored reason, "identical text,
suppressed" or "different text, not indexed under first-with-text", which is
honesty without reopening the decision. If a later extraction gives an earlier
attachment text or changes its detected language, the choice function's output
changes and the chain re-derives from there.

#### 5.2.4 Freshness: how the index finds out what changed

The reconcile tick asks Zotero what changed and queues the work. It does not
extract anything itself. It is conductor-owned (§5.2.5), runs every 60 s when
idle, backs off when Zotero is unreachable, and writes work orders. **No
document fetch happens inside the tick**: the
whole-document GET has no micro-batch boundary inside it, and a tick that
performs one does not run for as long as the document takes, which is where
R35's minute would go — the tick dispatches, the pipeline worker fetches
(§5.2.5). The 60 s cadence is what delivers R35's one-minute
promise, so the worst case is one full tick: a change landing just after a tick
waits for the next. Backing off is not a violation — a Zotero that is not
answering has nothing to report, and R35 starts its minute when it comes back.
The **extract shim** — the stage adapter that talks to Zotero only — splits
along the write line: its bookkeeping is the conductor's, since all of it is
writing — the item cursor, the full-text census, extractor-version staleness,
and per-attachment truncation flags — while its one
reading duty, the whole-document GET, is the worker's, arriving back as
windows. The worker paces that GET on observed latency (DECISIONS.md,
2026-09-01): a rising local-API latency median inserts a delay between
document fetches, decaying on recovery, reported on the instrument panel —
reacting to degradation before an error, since the serving process is
Zotero's own. Upstream's #39 answered the same pressure differently, and not
with a fallback: it sets the crawl's concurrency from whichever API serves it,
2 for the desktop app against 4 for the cloud, and backs off to one on
degradation (`c859407`, and re-read at `b0e0bc8` where the rule has moved out
of the router into `limits.ts:69` and `build.ts:617-620`, unchanged in
substance). That is not adopted (ticket 0505). The stage keeps its key: `text_hash` (§5.2.1) is computed over the
stream as it passes, so nothing has to hold the document to identify it.
Three things per library.

1. **Items.** Fetch `?since=item_watermark`, the watermark scoped to
   (oid, lib). A cursor is legitimate here because library versions are
   monotonic per backend, and scoping by server ID is what makes that true —
   the local/cloud label was verified insufficient, and the header machinery to
   lift already exists upstream at `local-writes.ts`.

2. **Full text, local scope.** Fetch the whole `/fulltext?since=0` census and
   diff it per attachment against the stored versions. No cursor, and no
   fulltext watermark column exists for any local scope, because the local
   sequence is mixed: one attachment's version may be a web sync stamp, a local
   client version, or 0 for locally extracted text (C1). The schema makes that
   trap unrepresentable rather than documenting it. Cloud scopes are different
   — the web sequence really is monotonic — so they use an ordinary `?since=`
   cursor, under the web politeness constraint SPEC.md states once. The
   census is cheap: ~8 037 entries ≈ 120–200 KB serialized per tick,
   O(attachments) in memory, no extra requests. If X7 measures the parse above
   50 ms at 30k entries, the cadence backs off to every 5th tick — a decision
   rule, not a hope.

   The stored census is a completion record, not an enqueue record. The tick
   leaves an attachment's stored versions unchanged when it creates a work
   order; the conductor writes them only after extraction completes, including
   D1's settled empty-text outcome. A failed extraction therefore remains a
   diff and is offered again by the next tick without waiting for Zotero's
   version to change. The worker returns the completion result across the
   boundary, but the conductor remains the sole census writer.

3. **Deletions.** Subtract the item census every tick, because R35 gives
   deleting a one-minute bound and the tick is what delivers it — an earlier
   every-10th-tick cadence disclosed ≤ ~10 min and no longer meets the
   promise. The `sync` verb still forces it immediately. The local API has no
   `/deleted` endpoint (C2), so census subtraction is the only local route.
   What the item census costs per tick is unmeasured, unlike the full-text one
   above — open, and if it proves too expensive to run every
   minute the finding is about the cadence, never about the bound.

The shim passes Zotero's bytes through unchanged. The local API serves the
cache bytes as they are, blank lines and form-feed page boundaries included
(`verification/probes/api-vs-cache-probe.py`; ruling 2026-08-30), so structure
is lost in today's chunker rather than in transport, and the extract stage
carries those signals through from day one. A later extractor can replace the
shim without moving the ledger boundary or touching the stages downstream.

**Two sources, pack first (ruling 2026-09-02).** Per attachment the shim
first looks for Zotero's structured-text pack, `.zotero-sdt-cache` beside the
file, located through the same `/file/view/url` route the segmenter uses to
reach the PDF — which answers with the local file URL as a plain-text body,
where `/file` and `/file/view` answer with a 302 to it
(`server_localAPI.js:1264-1276`, `9e28eb0`). A pack of a known pack version is the source: its blocks are the
text, excluded flows (running heads, page numbers) dropped, joined so a
passage's extent maps back to its blocks; its block types and page anchors go
to the segmenter as the first structure signal; its metadata's source hash and
processor version are the C1 key, so a processor bump is a visible staleness
event. No pack, or a pack version the reader does not know, or a pack cut
short, and the source is the flat text over `/fulltext` exactly as above,
never a direct read of `.zotero-ft-cache`. The pack never overlays the flat
text; one attachment has one source, recorded in the ledger and counted in
R17's report, so the mixture the reader-only trigger produces today is
disclosed rather than discovered. The pack's format is internal and unversioned
in any public sense (C2), which is why the fallback is structural: a format
move degrades that attachment to the flat path, never to a failure.

This is the permanent source-selection contract, not the current deployment
state. The reader is deferred until Zotero #6012 makes packs library-wide; the
measured 2 packs among 13 630 flat caches do not justify maintaining an
internal-format reader before then. Until that checkpoint the shim uses the
flat path for every attachment. When the checkpoint is met, enabling pack-first
selection changes no interface or downstream stage: the source identity,
reporting, tier-0 structure signal and fallback are already fixed above.

**The version-0 residue.** 584 of 8 037 measured fulltext entries sit at
version 0. A local re-extraction that stamps 0 again is invisible to an
equality comparison, and on a never-synced library that could be *every* entry.
The resolution has four parts.

(i) Widen the extract signal to `(fulltext version, attachment item
md5/version)`. Replacing a file bumps the attachment item in the item sequence
the tick already sweeps, so file-driven re-extraction is caught for free.

(ii) What remains — re-extraction with no file change — is disclosed in the
contract as accepted staleness: "version-0 text refreshes on file change or
rebuild".

(iii) A bounded idle re-verify sweep is built. X6 used Zotero's real
re-extraction queue and observed a nonzero full-text census value become 0 while
the attachment item version remained 0; a second 0-valued arm remained 0. The
sweep is ticket 0592's and reports its horizon rather than pretending the blind
class is current between visits.

(iv) A **content-presence probe** at verify time, on X6's
decoupling finding (`bench/results/0025-x6-version-dynamics/`). A derived cache
can vanish — content 404 — with every version signal and the source md5
unmoved, so nothing in (i)–(iii) sees it. A 404 on an item whose passages are
indexed marks them **cache-lost**: a stored warning state, counted, its reason
in the terminal-state vocabulary. Never an eviction, because the source did not
change and the passages remain faithful; the healing path is the user's
Reindex, surfaced as a count. The probe rides the extract shim's bounded verify
walk — part (iii)'s sweep if X6 forces it, otherwise its own slow walk — and
its cadence is pinned when the machinery lands.

**The query path** is unchanged from v1: no Zotero requests at all when the
tick ran within ~30 s, otherwise one memoized probe with a 500 ms deadline that
reports and nudges rather than blocks, with `probedMsAgo` in replies.

#### 5.2.5 Embedder registry, topology and concurrency

**The registry is configuration, not a menu of model names.** One indivisible,
versioned entry owns the model repository and revision, graph and dtype,
pooling, normalization, query and passage templates, model window, output
dimension and registry-schema revision. Those vector-affecting fields produce
the embedder fingerprint in C1. Display text and validation standing do not.
The public selector accepts an entry id, never a bag of raw overrides; an
unknown id is an error. During the invariant stages an unset selector resolves
to the singleton incumbent MiniLM entry and must reproduce its old vectors and
keys byte for byte.

**Embedding has one transport-neutral interface.** Both
`embed_query(text, entry)` and `embed_passages(batch, entry)` return vectors
with a handshake naming the requested and actual fingerprints, dimension,
runtime, execution provider and local-validation result. The client rejects a
mismatch before reading or writing a vector. The model is resident once on the
machine, per generation: a single **embedding service** answers every server's
queries and the pipeline worker's passages, so `provider: local_endpoint` is
the installation default rather than a later option. The count it replaces was
never two — a P0 loaded the query embedder on first semantic use and the worker
loaded the same model for passages, so two clients and a running build held
three copies. The service is spawned on demand, by a server and only by a
server — a service the `nice 19` worker spawned would embed every query at
idle priority — at normal priority, inside the data directory, so no daemon,
supervisor or OS facility enters the registry contract, becomes a prerequisite
for curated entries, or changes the fast-install path. **It acquires its
singleton before it loads a model, never after**: N servers starting together
must not each start a load and then learn they lost. It never opens the
database; it counts its connections and exits after holding none for a stated
interval, which makes its lifetime the servers' lifetime rather than an idle
clock — §5.2.7's ~60 s eviction is for the old generation inside it, and a
service that exited on that clock would reload the model for anyone who
queries every two minutes. It listens on a Unix domain socket inside the data
directory carrying the file's permissions, not a localhost port, because any
local process could otherwise impersonate it to a server while echoing the
expected fingerprint (§6). The execution choice does not alter the selected
entry.

**Two lanes, queries first.** One model serves queries and passage batches,
so a query arriving mid-batch would otherwise wait up to one quantum during a
build. Queries preempt passages at batch boundary; the quantum bounds the
wait, and §5.2.9's warm-query band carries that term. A server embeds *before*
it opens its read transaction, never across the call — a read held through a
cold load pins the WAL for the whole of it, during a build, silently.

**Degradation is labeled, never silent, and never permanent in disguise**: a
service unavailable or still loading yields keyword-only search, exactly as a
missing local runtime does under R10, and never an API embedder. A service
that dies on load — the install-failure class of upstream's #38 — is not
re-spawned by every semantic query: spawn backs off and then quarantines, the
shape the extraction quarantine already has, and status distinguishes
`loading`, `absent` and `failed` with a count, so the keyword-only label
cannot read as a transient forever. Two
generations may be resident across a model switch (§5.2.7); the service holds
both under one idle-eviction rule instead of each process holding its own. The actual execution provider contributes to
the vector fingerprint only when §5.3's X8 rule says its vectors are not
interchangeable. Endpoint syntax and discovery stay out of the registry —
open, no owner yet.

**Device selection is evidence-driven, never blind `auto`.** The service uses
a GPU only after a positive usability probe and passes that specific provider.
If initialization still fails it falls back cleanly to passing no device. With
no positively usable GPU it passes no device from the start, preserving the
runtime's functioning Node default; it does not force `cpu`, and device is not
a user knob. Status records the provider actually serving. This avoids the
measured CPU-only Linux failure in which `auto` registers CUDA from platform
shape alone and dies on absent libraries.

**The API execution mode** (`provider: api`, ruled 2026-09-02) is the third
execution mode, beside `in_process` (the embedder inside the server's own
process) and `local_endpoint` (the embedding service above): the opt-in path
R10 counts and §5.2.7's consent gate prices, over the network to a commercial
provider. It changes the constants, not the topology. The request is sized by
the provider's per-request cap and its per-minute token budget, not by the
quantum: a round trip is nearly flat in the batch size, so the duration
controller has no gradient there. The row claim's TTL is derived from the
retry budget, above the longest backoff §4's politeness clause permits, since
one honored `Retry-After` crosses the local engine's 30 s and every expiry is
a re-embed paid twice. The embedding service holds no model in this mode and
is not bypassed: it holds the key and meters the quota, one process for N
servers and the worker, queries first, with the round trip as the lane
boundary. Identity is provider, model name and requested dimension, because
revision, dtype, pooling and local validation have no referent at a provider,
and the provider can change the model behind the name without notice; the
calibration header is the detector, its sentinel re-embedded at session start.
A refusal or a timeout degrades to labeled keyword-only inside R6's 3 s and
never falls back to the local embedder, which would be a provider change
mid-corpus. The providers' asynchronous batch endpoints are out: they save at
most half of a one-off cost the ledger prices in tens of dollars, and they
would cost a claim class with day-long TTLs, library text parked at the
provider for up to a day, and partial-job reconciliation.

A future `provider: zotero` is the preferred reuse probe: #6012 already runs
native ONNX inference in Firefox's separate memory-gated process, but its
`Zotero.ML` and `Zotero.Embeddings` calls are internal at the reviewed head.
Whether an official local bridge can expose query and batched
passage embedding with the same fingerprint handshake is open. Sharing Zotero's stored
embedding database or depending on private in-process symbols is not that bridge.

**Process topology** (sole-writer form; the proposal and
its review are `verification/SOLE-WRITER-0507.md`, whose F2 named the
separation this section now states). Four process roles appear below: P0, a
query-serving zoteus server; the *conductor*, the writer; one *pipeline
worker*, which fetches, drives the embedding service, and writes nothing; and
the *embedding service* above.
The conductor is the sole writer of derived state: slabs, entries,
passages, vectors, the ledger. A server writes control rows and nothing else.

The normal deployment is N × P0: one zoteus per MCP client, all on one fixed
default data directory (verified). Every P0 answers queries, as a WAL reader on
a write-free query path, and the write role is not compiled into it: what a
server writes is **control state and nothing else** — the pause row, intent
rows, its own liveness row — in a table of its own, outside the commit guard,
never derived. The conductor is a process of its own, not a P0 wearing a
second hat. It is spawned by whichever server finds the lease unheld, and it
lives while any server lives, because it owns the tick: each P0 keeps a
liveness row in the same `leases` table on the same TTL, and the conductor
exits when none is live — not when its queue empties, which would have the
next election check re-spawn it ten seconds later, N times over, forever. It
holds its role through a lease row:

    UPDATE leases SET holder=:uuid, expires_at=…
    WHERE name='conductor' AND (holder=:uuid OR expires_at < :now)

The holder is a UUID, not a recyclable pid. A lockfile was rejected because
lockfiles go stale exactly when their holder dies. Lease timing: TTL = 2×
heartbeat (20 s), an election-check cadence of 10 s in every server, and a
migration gate < TTL + cadence = 30 s. The constants satisfy their own
gate. On a fresh install the lease
lives in a file that does not yet exist and no server creates the schema: the
first conductor writes an empty schema to a temporary file, renames it into
place, and only then takes the lease and only then works, so two conductors
racing on a fresh install lose nothing — neither has written a row before the
rename decides. The conductor runs the reconcile tick and owns at most one
pipeline worker (`nice 19`), so the pipeline does not multiply with N. The
worker is the one run-to-drain role: spawned when the ledger queues hold
work, it drains them and exits, so steady state contains no pipeline worker
and does contain the conductor. The worker runs under a heap limit at minimum
and a cgroup where the platform has one, because a process boundary isolates
memory only if something bounds the process — otherwise a runaway decode eats
the machine from a different pid, and F5's clause stays an instruction. The queues are ledger
queues still — keyed, idempotent derivations — but the boundary between chunk
and embed survives as a **write ordering** rather than a process boundary:
the conductor segments, and an item's slabs, entries and passages are durable
before any vector for it is computed. Keyword availability never waits on
embedding, and a worker death loses only the vectors in flight, never the
segmentation of a 15 000-page book. The two-band frontier is a dispatch
policy over ranges (§5.2.3), not machinery of its own.

**The conductor is the only writer, and the segmenter.** Every durable
artifact — ledger rows, slabs, entries, passages, FTS, the vector sidecar —
is written by the conductor and by nothing else. It runs seg/1 (§5.2.2) as a
streaming state machine over the text windows the worker forwards: it closes
entries at structural boundaries — a book into chapters, the dictionary into
entries, proceedings into presentations — taking its structure signals in
order: the pack's block types and page anchors when the source is a pack
(§5.2.4), the PDF's own outline and layout otherwise, seg/1's heuristic last —
cuts the passages inside each entry
as deterministic token windows over text it is already holding, and commits
slab, entry and passage rows as entries close. Peak memory is one window plus
the segmenter's own state, which is the streaming property C3 already
asserts. **The conductor never materializes a whole document**: the local API
answers with the text inside one JSON object, and the convenient read puts a
44,9 MB attachment whole inside the one process that may write — §5.2.9's
arithmetic says that does not fit, and it does not fit any better now that the
writer no longer also answers queries, because the ceiling is per process and
the document is the term that grows. The fetch is
therefore the worker's, §5.2.4 states the same clause as the tick's
prohibition, and §5.2.8's transport clause on the RSS gate is its instrument.

**The worker writes nothing.** No lease, no write handle, no file of its own;
a WAL reader like any sibling P0, which is what makes C3's
killable-at-any-time bullet structural rather than argued. It does two jobs.
It streams one attachment's extracted text from Zotero's local API and
forwards it to the conductor in bounded windows, deciding nothing and
accumulating nothing — the incremental decode of the one-JSON-object answer
is written here, once, in the process whose failure costs a restart rather
than a breached ceiling. And it embeds: an embed order for a small input
(record, note, annotation) carries its text outright; for body text it
carries an entry-sized range — the slab addresses §5.2.2 gives every passage —
which the worker reads back read-only, slices, embeds and streams home. A
book crosses the pipe once as text and never again; a re-embed after a model
change, a band-1 backfill and a resumed run all dispatch ranges over text
already stored. The worker packs each engine call to a token budget, ranges
sorted by length first because the runtime pads every member of a batch to
its longest sequence; the batch is the memory dial, the duplicate-compute
unit and the yield grain, and nothing is bought by making it large
(`verification/GPU-ANOMALY-0481.md`, `verification/GPU-CORRECTED-0482.md`;
the CPU sweep at the deployed rung is open).

**The priority tree.** The activity file, the discovery classes and the two
bands compose into one priority order, shaped as a tree. Read it top down; the
schedulable unit at every level is one micro-batch.

1. **Foreground preempts everything.** A fresh activity file idles the worker
   and the conductor's write loop, so a query in flight beats all indexing.
2. **Strict class priority orders discovery**: metadata, then notes and
   annotations, then body text (§5.2.3). Strict priority carries no
   arbitration constant here, and the reason is a rate, not a theorem. Upper-
   class work is cheap per item and its arrival is bounded by how fast a human
   edits the library, so in ordinary use the upper classes drain and the body
   tier runs. Under sustained upper-class churn — a long annotation session, a
   sync storm refilling metadata every tick — body-text progress is deferred
   for as long as the churn lasts. That is the accepted trade, stated rather
   than argued away: the same order delivers cross-class freshness for
   nothing, since a changed record beats every queued body range without a
   dedicated lane.
3. **A weighted interleave splits the body class**, freshly changed items
   against the initial backfill. This is the one level that needs a weighted arbitration: no
   single queue order serves both freshness and completeness, and strict
   fresh-first starves the backfill under sustained arrival. The arbitration
   is stateless weighted round robin at r = 3 — three fresh micro-batches per
   one backfill (DECISIONS.md, 2026-09-01). The drain bound it buys is an
   expected time over a snapshot of the fresh lane rather than a promise to a
   user.
4. **Band 0 precedes band 1**, per item (§5.2.3), which is what keeps one
   15 000-page PDF from monopolizing the body tier. It is the last level:
   §5.2.3 says why no per-item round robin and no recurring passage quantum
   sits below it, and names the repair if a corpus ever shows the tail
   contest biting.

Levels 3 and 4 bind the pipe as well as the queue: one worker serializes fetch
and embed, so a fetch order for a newly changed item goes ahead of queued
band-1 embed ranges and an embed backlog yields at batch granularity.
Without that, a band-1 drain would starve every fresh item's fetch and
reintroduce at the worker the monopolization the bands exist to prevent.

Order is re-evaluated between micro-batches and nowhere else, which is what
makes preemption and the band cap effective rather than nominal. The
micro-batch is therefore a time quantum, ratified at about 1 s, its size
derived per device rather than fixed (DECISIONS.md, 2026-09-01).
The pipeline yields at about the quantum on any hardware whose fixed-cost
floor sits below it, and at the floor's cost where it does not. The quantum
guards slowness, not death: a worker stuck inside a batch is recovered by
claim expiry, the row claim's TTL being 30 × the quantum — above an honest
stall, below the reconcile tick — at the cost of at most one duplicated
micro-batch. Both constants are the local engine's; the API execution mode
above replaces them.

Two units escape that interval, and both are named rather than solved. The
extract stage's whole-document GET has no boundary inside it (§5.2.4): its
worst case is the corpus's largest attachment at the local API's measured
throughput, and it sits outside the slot accounting the level-3 bound is
counted in. And a memory ceiling that moves under the process — a GPU shared
with another tenant — can make the autotuner's clamp wrong after it converged;
what the retry costs then is open, owned by the quantum's ledger entry.

The tree promises no completeness and is not asked to. Completeness comes from
the reconcile tick, which re-derives what should exist and re-queues whatever
is missing (§5.2.4).

**Orphan repair and flow control.** Two repairs, on two sides, because the
failure they cover is a parent that is wedged rather than dead. The worker
exits on stdin EOF (parent death), and it also polls `leases.holder ==
parent-uuid` on its own timer between micro-batches, exiting on mismatch —
the worker-side check of the three-worker design kept, not moved, since a
SIGSTOP'd or thrashing conductor closes no pipe and runs no cleanup, and
only a check scheduled in the worker's own process fires then. The
conductor-side half is the complement: a writer that observes it no longer
holds the lease kills its worker before anything else, because an orphaned worker,
though harmless to a store it never opens, pins the WAL as a long-lived
reader while the new conductor spawns its own. Both together enforce the
one-worker bound; either alone has a hole. Lease renewal stays on a timer
decoupled from stage progress, renewed immediately before any long unit of
work. And the pipe pair is full-duplex, which is a deadlock shape: the
conductor drains arriving windows and records before blocking on any write
of work orders, in both directions — returning records drain into the same
bounded append-fsync-commit loop that bounds the windows, never into a
queue ahead of it.

**The handshake crosses the pipe** (§5.2.5). The model is resident in the
embedding service, which answers every embed call with the requested and actual
fingerprint, dimension, runtime, execution provider and local-validation
standing; the worker carries that answer home with the first record of every
dispatch, and the conductor rejects a mismatch before writing a vector.

Safety never depends on the singleton: during a handover two P0s can each
believe they are conductor, so every record commit carries the guard **in the
same transaction as the write** — a conditional `UPDATE … WHERE
holder = :uuid AND key = :computed_key`, the CAS idiom the lease acquisition
above already uses, never a separate read followed by a separate write. Two
deposed-but-running conductors then cannot both pass: SQLite serializes the
transactions, and the loser's condition reads the winner's committed state
and writes nothing. A check-then-write in two steps would re-open exactly
the race the guard exists for, which is why the atomicity is stated here
rather than left to the implementer. R13's letter is restated honestly: never
committed twice, and duplicate compute bounded by one embed batch plus one
in-flight document's re-fetch and re-segmentation per failover, since the
conductor computes too. The strict letter has no implementation on a
single-file SQLite substrate, and the design says so rather than implying
otherwise.

Foreground beats background across processes, which is the only place it now
has to hold: each P0 touches `<dataDir>/activity` on query arrival (a
filesystem operation, so the query path stays write-free even in the database
sense), and both the worker and the conductor's write loop stat that file
between micro-batches and idle 2 s while it is fresh. The clause that had to
run *inside* the conductor is gone with the process that carried it — it
existed because one process both served and drained, and no process does both
now. §5.2.8's conductor-latency soak clause survives it, as a confirmation on a
writer that no longer answers queries rather than as the trigger for splitting
one that did. The conductor's stdio pipes remain the low-latency fast path;
`nice 19` remains the OS floor — minimum CPU priority, portable through the
runtime's cross-platform call — joined, where the platform exposes one, by a
background I/O class (idle I/O on Linux, the background policy on macOS,
background mode on Windows), best effort elsewhere (DECISIONS.md,
2026-09-01). Upstream's BEGIN-at-first-mutation transaction is repaired
surgically: the build path commits per page (its 200-item/10 s persist
cadence already exists; the hold window shrinks below the busy_timeout),
while the update path keeps its single-transaction rollback. Upstream's
own comment is right that a half-applied delta is a wrong index, not a
partial one.

Sidecar discipline collapses to an ordering: the conductor appends the vector
bytes, fsyncs, then commits the row that references them, so a crash between
the two leaves bytes nothing points at — dead weight the compaction rule
collects. The files stay generation-numbered (`vectors-<embedderKey>.g<N>`,
the generation stamped in meta) for atomic replacement at compaction, and
compaction itself carries the same ordering across its two atomic domains:
write `g<N+1>` whole and fsync it, switch every row reference and the meta
stamp in one SQLite transaction, and only after that commit delete `g<N>`.
A crash on either side of the switch leaves one complete, referenced
generation — before the commit the new file is unreferenced dead weight,
after it the old one is — so the split state a filesystem rename plus a
database commit could otherwise produce is unrepresentable. That is what
lets the scan-and-verify half of the old protocol go: its other purpose,
keeping the sidecar consistent with rows another process wrote, has no
subject with one writer. Deletion tombstones cover every live generation.
Compaction runs at >10 % dead rows or in the idle weekly slot.

#### 5.2.6 Query path and ranking

**Query semantics (D5), granularity decided out loud.** Hard units (quoted
phrases, explicit AND, NOT) are filters, while bare terms are soft: they
rank, OR'd, which is today's recall-friendly default, kept deliberately. Phrases
evaluate per passage (FTS5-native, positions intact; a phrase straddling
two entries is correctly dead text). AND and NOT evaluate at entry scope:
one MATCH per hard term, id-lists joined on `eid`. AND means every term
hits at least one passage of the entry; NOT means no passage of the entry
hits. That is a few id-set operations over lists the design already
fetches, one extra MATCH per hard term, trivially inside R6. Passage-scope
AND on a multi-chunk entry would silently exclude legitimate hits (proved
by construction during the critique). Until entries exist upstream, hard
predicates ship at item scope, entry scope's conservative projection at
today's granularity, and any upstream filing of this work says so out
loud. Memory-backend parity: the phrase/AND/NOT check runs against a
fold-only, unfiltered token stream re-tokenized from stored text, because
the retained `tokenize()` arrays are stopword-stripped and would make
`"war and peace"` match "war versus peace". The predicate is pushed inside
`search()` before its top-k slice.

**Filters (R5).** Facets compile in SQL to an allowed-entry bitmap, and on
the vector scan the bitmap applies before the dot product: genuine
pushdown, since that loop is ours. On the keyword side, MATCH runs unconstrained
(C2's measured economics, and upstream already does this) with pool
`max(8×limit, 256)`, and the bitmap filters the candidate stream. A ladder
first refetches deeper (4 096), then stops and answers honestly through R18's
`scope{}` block when the filtered stream still cannot fill k. X4 removed the
former constrained-MATCH middle rung: `json_each` was dominated by searching
the whole corpus even at its smallest measured scope. Ticket 0590 measures how
often realistic collection and tag scopes reach the disclosure; it commissions
no replacement unless partial answers prove common. No path ever post-filters a top-k and *claims
completeness*; the give-up is disclosed, which is what R5 and R18 jointly
demand.

Year/date and item type take a distinct stored-attribute path: both are columns
on the item row with ordinary indexes, populated from metadata the crawl already
has, and their predicates apply during ranking before truncation. They do not
use `json_each` and do not wait for the arbitrary-scope frequency experiment.
An exhausted filtered stream is still disclosed through R18. Collections and
tags remain arbitrary-set facets under the ladder below; creator and title are
not admitted by this rule.

**Entry collapse.** Each engine collapses passages to entries *before ranks
are assigned*: the entry score is the MAX over its chunks (#6012's rule,
transposed to the ratified unit). The vector scan does the collapse in a
single pass with an entry-keyed top-S heap, because a refetch variant would
hide a second 650k scan, ~0.5–1 s, on exactly the dictionary-heavy queries
that trigger it. Presentation groups entries under items; ranking never
re-collapses. D9 dissolves as the ruling says, and R24 absorbed the dedup clause: the dictionary earns
many slots only with many genuinely distinct entries, and concentration is
still disclosed in status.

**Rendering collapse.** After entry collapse and before the cut to k, entries
whose attachments are declared renderings of one work collapse to one answer
row. Twin attachments under one item and explicit relations between items are
declarations; similarity is not. The best-scoring rendering supplies the hit
and its relevance rank. Other renderings are structured alternates carrying
language and key, rendered as `also in: <lang> (<key>)` where text is needed.
An unlinked record remains its own row, and the query language never replaces
the best-scoring rendering.

**Fusion.** The fusion rule is fraction-weighted RRF at k=60. The seam invariant, that every
ranked list crossing the fusion seam is higher-is-better and strictly
positive, is a unit-tested contract at the four verified lines (SQLite
clamps idf; `-r.rank` stays positive). `frac ∈ [0,1]` bounds every
contribution above by plain RRF, and frac = 0 is noise-suppressed, stated.
`frac_vec` defaults to list-local max-normalization. #6012-style
registry introduces two deliberately separate checks. First, every selected
entry must pass the bundled public compatibility fixture on the actual local
runtime and provider before it creates or queries an index. That check covers
loadability, declared dimension, finite values, normalization, application of
query and passage templates, determinism within the provider, and basic
matched-over-unmatched discrimination. Its cached result is keyed by the full
entry fingerprint plus engine version, runtime, operating system, architecture
and execution provider. A remote result can inform the UI but never substitutes
for this local gate. A vector passes the normalization arm when its L2 norm is
finite and `|norm - 1| ≤ 0,00001`.

Second, #6012-style library calibration (mean centering, noise floor = p99,9 of
unrelated pairs, ceiling = median of matched pairs, reject bad models outright)
remains deferred. One item's title and abstract form a matched
pair, cross-item pairs are unrelated, and the private library is the corpus.
Those texts and scores never enter a shared attestation. An optional,
content-free compatibility attestation may report only pass/fail, exact entry
fingerprint and runtime shape, after explicit opt-in; it is evidence that a
configuration executes, not that it retrieves well. Ship gate (D11): golden-set
Jaccard at or above §5.2.8's thresholds against plain RRF, both behind one flag.

**The locator (R24)** is discriminated by the hit's entry kind: a record or
note hit has no attachment and no page, and the reply never fabricates
either.

- A **body** hit carries `{itemKey, attachmentKey, entry heading/path,
  charStart/End, pageEstimate, pageIsEstimate: true}`. The heading path is
  the primary locator (per the ruling); the char offsets are exact. The
  page is estimated within its attachment, from per-attachment totals that
  extraction now records instead of discarding (verified: upstream keeps
  only `content` and concatenates, destroying the offset→attachment
  mapping). `pageIsEstimate` stays true until a verified exact mapping
  exists; the label is the honesty mechanism.
- A **record** hit carries `{itemKey, field}`.
- A **note/annotation** hit carries `{itemKey, sourceKey}`; the
  annotation's parent attachment and page, when Zotero supplies them, pass
  through as exact.

**Empty results (R18).** An empty result names its scope in one of three
disjoint sentences ("not indexed yet (0 of 947)", "partial: 812 of 947 —
the miss may be coverage", "fully covered — nothing matches"), computed at
query time from facet tables joined to ledger terminal states, deliberately
*not* a materialized counter (R17 governs the status path; R6 governs this
one). Under a strict query, one relaxed soft-MATCH count offers the
drop-the-quotes alternative.

**Cross-lingual (R29).** Keyword search cannot cross languages: FTS5 and
`bm25()` have no path from "hydropower" or "hydroélectricité" to "thủy điện",
whatever the tokenizer folds. The embedding space is the only channel, so the
promise stands or falls on the embedder and rides the semantic path with no new
query-side machinery. On such a query the keyword list is empty or noise, so
fusion has to let a semantic hit surface without keyword confirmation — the
open `frac_vec` question, with the cross-lingual slice as its
hardest case. When the semantic path is unavailable the reply carries a typed
`CROSS_LINGUAL_DEGRADED` disclosure beside R18's sentences, the CJK posture
below transposed. Alignment is a property of the embedder's training and varies
by language pair, so it is measured per candidate at the deployed dtype rather
than read off a model card, and R29 is a
conformance criterion in the registry's ship gate.

**CJK.** The multilingual embedder is the CJK path, with a typed
`CJK_KEYWORD_DEGRADED` disclosure meanwhile. The companion's geometry is
settled and the build is ours: 2-gram twin tables (shipped Zotero 10's
geometry, not the draft PR's — `getCJKBigrams()` at `fulltext.js:2144`,
build 20260817151751, C2's shipped-schema bullet — and decisive on its own
terms: the modal Chinese word is two characters, unrepresentable as an
exact trigram), backfilled from slabs for CJK-bearing passages only,
query-routed, fused as a third list. SentencePiece quadratic-encode caution
inherited: cap encode segments at ~1 000 chars.

*Fusing is ours, and it is where we leave the platform.* Zotero routes CJK
**exclusively**: `getWordMatchClause()` (`fulltext.js:2361`) sends a pure-CJK
run of two characters or more to the CJK table alone as one contiguous bigram
phrase, and returns `null` in the other two states — a single CJK character,
which has no 2-gram, and any mixed-script term, because the CJK index would
drop the non-CJK characters. `null` means the index cannot answer, and the
caller falls back to scanning cached text. Those two dead ends are exactly
what a third fused list answers, which is the argument for the divergence:
the geometry is copied, the routing is not. Ratified `DECISIONS.md`
2026-08-29; evidence `verification/VERIFY-FULLTEXT-SQLITE.md` §2.6.

#### 5.2.7 Custody and lifecycle

**R10 — local by default.** Verified: exactly two opt-in exfiltration paths,
no silent fallback. The sole permitted external call on the default path is
the one-time model-weight download, named in status, degrading to
keyword-only and *never* to an API embedder; that invariant gets a test.
Every reply carries the one-line custody string. The consent gate:
auto-build defaults on only for the free local embedder; API embedders
quote a cost and require an explicit go-ahead per index generation. One
hygiene PR: the Gemini key moves from the URL query string to a header.

**R15 — deleted means gone.** Deletion rides the census tick, and every copy
of the text has a named removal path:

- item and entry rows
- the FTS index, via its delete protocol (upstream's correct discipline,
  kept)
- passages
- vectors
- slabs (keyed per attachment/source, never shared)
- sidecar tombstone bitmaps, across *all* generations
- ledger rows (the conductor committing on a deleted item fails its own
  commit guard, §5.2.5 — workers write nothing)
- WAL and free pages: `auto_vacuum=INCREMENTAL` actually set (§5.2.2), plus
  idle checkpoint, plus the `purge` verb = checkpoint + VACUUM + compaction
- the legacy `search-index.json`, which upstream leaves in place forever,
  renamed `.migrated-<ts>` after the first post-migration save and swept at
  30 days or on `purge` (an *issue*, not a PR, because it reverses his
  documented decision)

Pause never gates removal: deletion propagation is classified as removal,
not derivation (one branch in the tick), because otherwise a paused index
serves deleted text for months. The acceptance test decompresses slabs
before grepping (`strings` on gzip proves nothing). Byte-level "gone" is
eventual, with a disclosed bound, stated as the negotiated reading of R15,
for the author to veto.

**R22 — pause stays paused.** One meta row, written by `pause`, read before
any scheduling decision. It gates worker spawn (a paused pipeline is zero
workers — drain, then shut down, a #6012 pattern — while the conductor stays
for the tick's removal branch, which pause never gates), the tick's build
side, and `auto_build`
(verified: today any query against an empty index starts a build). It does
not gate queries, the probe, deletions, or explicit verbs (`build` while
paused asks). It survives restart by construction, and survives *sideline*
by being carried into the fresh file. R1-versus-R22 resolves in the user's
favor, disclosed: "paused since <date>".

**D3 — serve-stale.** The verified violation (`dropStaleVectors` →
`clearVectors()` at open) dies. Vectors carry per-row embedder keys: on a
model switch nothing drops, re-embedding drains newest-first, and during
the window queries dual-embed, each row scored in its own space. The old
model is lazy-loaded only while old-generation rows are in the pool, and
evicted after ~60 s idle. Under memory pressure, queries fall back to
labeled keyword-anchored fusion. Two resident models (~240 MB + 70 +
32–64) would bust the ratified ceiling for a days-long window, so
lazy-loading keeps the budget honest — and it is now paid once for the
machine rather than once per process, since both generations are resident in
the one embedding service (§5.2.5). The cold-load spike this rule discloses
is correspondingly a spike the machine takes once per service lifetime — the
servers' lifetime, §5.2.5 — not one every server takes on its own first
semantic query, and not one per idle minute. At most two generations coexist; worst-case
storage is 2× the sidecar, disclosed.
The *small PR* version of D3 is narrower: upstream's one global
`embedderId` cannot support mixed spaces, so the contained fix is
keep-vectors plus pinning the query-side embedder to the stored id until a
rebuild switches both. Dual-embed itself is not built here; the contract
survives even if it is built upstream instead.

**R23 — upgrade and downgrade.** The open protocol: read
`meta.schemaVersion` before any DDL or write (upstream's own rule since
`fd51659`, v1.9.0: `reconcileSchema()` reads the stamp through a read-only
probe at `sqlite-index.ts:585`, before the `INSERT OR REPLACE` in
`createSchema` can re-stamp a file written by a newer build. That ordering
defect is fixed upstream; the protocol below is what the fix leaves open). A
newer file → sideline (never delete), fresh build, notice. Only the
conductor may sideline, because under N processes an unconditional
per-server sideline would let one stale install repeatedly sideline a fresh
one's index. An older file → versioned migrations. `min_reader_version`
lets a too-old-but-aware server keep serving everything that never touches
the index, and answer search with a typed `SCHEMA_NEWER {remedy}`. The
ping-pong-downgrade hybrid state carries its own tamper evidence:
`stamp==1 && v2 tables present` means an old binary wrote here, and the
response is not "migrate" but reconcile-heal: mark derived stages stale,
census-diff, let R1 re-earn. The retroactive limit is stated plainly:
binaries that predate the protocol (every release through v1.8.0; v1.9.0
ships the read-before-write + sideline slice via PR #25, and v1.13.0 the
older-file half — a contiguous `SCHEMA_MIGRATIONS` ladder whose first rung
rebuilds the keyword index in place inside the transaction that stamps the
new version, re-computing no vector — but neither ships the conductor rule or
`min_reader_version`) are unreachable by it; the new filename (§5.1) is what
actually protects against them. What the ladder does NOT answer is the newer
file: `migrationPath` refuses to walk backwards, so the newer-stamp direction
is still sidelined, which is where R23 stays open.

**R15's uninstall clause.** The zoteus adapter declares its data directory as
derived state and pins `env.cacheDir` under it before constructing the pipeline
(the transformers default lands outside it, per its documentation:
documentation-cited, not disk-verified, and the fix is correct regardless).
Until zoteus offers a real uninstall surface, the adapter reports
`not-offered`; `purge` is maintenance, not a substitute the harness may call to
manufacture a clean result. D2 hosted-out deletes, explicitly: per-tenant
contract keying, multi-tenant consent bookkeeping, encryption-at-rest,
quota arithmetic; the four returned privacy lines stay dead.

#### 5.2.8 The instrument panel

**The target-neutral acceptance harness.** One assertion layer runs against
thin adapters for zoteus, Zotero core #6012, ZotSeek, 54yyyu/zotero-mcp and
Beaver. The interface is `install`, `uninstall`, `configure`, `query`,
`status`, `pause`, `resume`. Pause and resume are the two transitions of one
durable background-work control; resume is idempotent and never forces a
rebuild, refresh, repair or sync. Starting and stopping a target process are
adapter-declared harness setup, not indexing controls. The harness changes its
fixture library and observes convergence through status; it never commands or
nudges convergence, since that cannot prove R1's unattended clause.

An adapter declares every derived-state location, the query transport, process
startup and shutdown, the target's default configuration and unsupported
interface verbs. It contains only the minimal transport needed to invoke those
surfaces: no patch or workaround, non-default option, access unavailable to the
target's users, or result scoring. An unsupported verb reports `not-offered`,
distinct from pass, fail and not-run. ZotSeek's seat stays assigned to the
in-process-plugin architecture class if that project becomes uninspectable or
unrunnable. Beaver runs at a pinned AGPL plugin revision in its normal
configuration; an unavailable service or permitted account reports not-run.
A deterministic egressing stub is R10's fail-control.

Meaning is judged only for R17's human status answer, R18's two kinds of empty
answer, golden relevance and R24's page attribution; every mechanically
decidable clause stays mechanical. For each judged clause the harness emits an
immutable question carrying the clause, a versioned rubric, target output,
evidence and a blinded fail-control. The schema-checked answer records verdict,
rationale, judge and model identities, runtime, timestamp and rubric hash, and
is valid only if the judge rejects the control. The supervising agent is the
default interactive driver; hosted APIs with operator-local credentials and
padme's Qwen 3.8 are unattended drivers. Credentials never enter the repository
or result artifact. `bench/models.json` remains exclusively the embedder
registry.

**The coverage sentence** (D1 denominator = items; metadata-only covered
with reason; sections only ever the partial qualifier). The partially
embedded item in the example below is the dictionary, the rare case:

> "All 7,541 items are record-searchable (titles, abstracts, keywords —
> 100%, newest first). Body text: 5,561 of 6,100 items with attachments
> extracted and keyword-searchable back to 2016-04-11; 538 covered as
> metadata-only (no extractable text). Semantic: 2,101 items fully embedded
> back to 2019-09-02, newest first; 1 partially embedded (record + 214 of
> ~1,850 entries — item DH8EXSVA). Building in background at idle
> priority; not paused. 1 quarantined: BHT7Q2 — extraction failed 3×;
> retries when its content changes."

The example's arithmetic is deliberately consistent (5 561 extracted + 538
metadata-only + 1 quarantined = 6 100, the states disjoint), and "covered
at extract" is defined once: items with no attachments are vacuously
covered, the "of 6 100" clause scopes the with-attachments subset, so
`covered.embed == items.total` is stateable on a real library. Beyond the
sentence, status carries per-library rows, the pause line ("paused since
<date>"), the custody string, the record/body coverage split, and the
version-0 residue disclosure (§5.2.4).

**Counters (R17).** `counters(name, value)`, updated in the same
transaction as the ledger transition each one describes. Per stage:
`covered / empty / partial / outOfBand / quarantined`. Work counters on two
axes: `work.<stage>.<trigger>.<outcome>`, with trigger ∈ `{new, edit,
re-extract, resync, key-bump, prefix-stale, retry, delete}` (R17's "which
input") and outcome ∈ `{noop, done}`. Here `noop` means signals moved, keys
verified unchanged, nothing recomputed; `done` means recomputed. R17 needs
both what triggered work and what became of it, and one flat vocabulary
cannot say both. Idle reconciliation recomputes the counters with real
COUNTs, fixes them, and increments a surfaced `drift` counter the harness
fails on, because if the counters can drift silently, every status answer
built on them is suspect. Status point reads are sub-ms, against the
measured 374 ms cold scan.

The boundary cursor is where the crawl resumes, not an invariant anyone
asserts. It is the total-order key `(dateAdded, lib, itemKey)`, never the bare
date, because several items can share a `dateAdded` and the boundary MUST be
able to stop partway through such a tie group. It passes settled states
(`done | empty | quarantined | band0-done`). `outOfBand` is pure set
membership: covered items older than the boundary, decremented as the
boundary sweeps past them. Edit work counts only under the `edit` trigger,
and the record stage counts its own edits.

**The convergence harness.** Apparatus for R1 and R17, and no requirement of
its own since 2026-08-31. A fixture library, an empty data
directory, status polls at 1 Hz touching nothing else (R1 needs no asking).
It asserts four things.

- Status answers in ≤ 50 ms.
- Coverage is monotone.
- The class order §5.2.3 states holds, per item: nothing has body passages
  indexed before its record. A positional prefix is not asserted — the reading
  that it should be was vetoed on 2026-08-29, and the counter arithmetic
  written to check one (`covered == |{(dateAdded, lib, itemKey) ≥ boundary}| −
  partial − quarantined + outOfBand`) retires with it. Its left side is defined
  by the boundary's position, so the identity restates the vetoed claim in
  arithmetic and would report the library's churn as a coverage fault. What
  checks the counters instead is stated one paragraph above: idle
  reconciliation recomputes them with real COUNTs and the harness fails on the
  drift counter, which holds them to the ledger rather than to a position.
  `outOfBand` outlives the identity it was introduced to balance, because
  items covered before the sweep reaches them are a real thing to report
  under R4 — an edit covers an item the crawl has not arrived at.
- The terminal state arrives: all stages at total, drift 0, `pipeline: idle`,
  work counters stationary. The observable is ours: #6012's nearest analogue
  is `getStatus().phase`, which reaches `idle` on the branch that shuts the
  engine down *and* on the branch that leaves it up for more work
  (`embeddings.js:2782`, `:2998`), so it reports a loop at rest and not an
  engine down. Ours must assert both, which is why the counters ride beside it.

Phase 2: edit
one title → exactly `work.record.edit.done == 1`, `work.embed.edit.done ==
sections(record)`, everything else 0; then a simulated identical-bytes
resync → zero recompute: every `*.done` delta 0, the touched items
appearing only under `work.*.resync.noop` (§5.2.1 says verification runs, and
the gate MUST permit exactly that and nothing downstream of it). This is
R3's counter-churn clause measured by R17's own counters, the test that would have caught the
shipped 92,7 % defect. Phase 3 is the hostile fixture: one quarantine, one
a 15 000-page PDF, dateAdded ties. The harness MUST fail on the corpus that exercises
its subtraction terms, not only pass on the gentle one.

Phase 4 is the schema flip, which goal 1's fold added on 2026-08-31: restamp the
built index to a foreign schema version, in either direction, restart, and
assert that the terminal state above returns unattended — nothing asked for, no
file deleted by hand — inside R32's bounds. This is R1's clause and not R23's:
what it asserts is that coverage comes back, never that it was never lost. Where
a build serves the foreign stamp rather than abandoning it, which is R23's own
promise and filed upstream, the same terminal state MUST arrive with the embed
counters flat, and it is those counters rather than the elapsed time that tell
the two outcomes apart.

**The gates** (Makefile: `check: lint figures fold-gate golden check-fast`;
`check-slow: check rss-gate convergence soak`):

- **The fold gate.** `fold_sweep.mjs`, repointed at the tree under
  test. It compares the two shipped normalizers against each other on that
  tree, which makes it apparatus over our own source rather than evidence for
  R19: since 2026-09-03 that requirement is a promise about what a user sees,
  and a promise is kept or broken where a user can see it. The query side falls
  back to `tokenize`-only when
  `normalizeForSearch` is absent, so against a pre-fold tree the gate is red
  *by classification* (a recorded miss count), not red by crash. The waiver
  keyed to PR #19's URL retired with its merge (2026-08-27): stock ≥v1.7.2
  ships `normalizeForSearch`, so against current upstream the gate runs
  green by right.
- **The RSS gate**, over constraint C3. A deterministic synthetic document at the measured
  44 906 152 chars, entry-structured (~43k headings) so the segmenter and
  the band cap are exercised. Assert: the kill of the one run-to-drain pipeline
  worker at its memory bound rather than a pipeline-worker peak ≤ 750 MB, the
  peak figure awaiting the re-pin §5.2.9 owns, server p95 ≤ 750 MB, the
  budgets verbatim, against the document class whose
  uncapped build once measured 2 084,9 MiB. The surrogate is a flagged
  deviation from the budgets' letter ("against the 44,9 MB dictionary", content
  that cannot be committed to a public repo). The
  real-document X3a run revalidates it at each release on the author's machine.
  **The transport clause**, same gate: resident memory across a fetch of the
  library's largest attachment, measured on both processes of the fetch path
  — the worker across the streamed fetch and its incremental decode, and the
  conductor, the one process that may write, across
  the same ingest — because the clause it instruments is that no process on
  the path ever holds the document whole (§5.2.5's no-materialize clause,
  otherwise an instruction rather than a verified property; finding F5,
  `verification/SOLE-WRITER-0507.md`). The two thresholds above name process
  roles that the 2026-09-02 topology re-cut, and the model they were priced
  against is now resident in neither of them: what each role's ceiling becomes
  is §5.2.9's to re-derive, and this gate asserts whatever that section says
  for all four roles rather than carrying its own copy. The embedding service
  is the class the gate did not have, and it is the only one that holds a
  model; its ceiling is sized for two resident generations, since the
  dual-embed window is days long and a ceiling at one model rules D3 out by
  arithmetic. And for the worker the gate asserts the **kill**, not the peak:
  a decode driven past the bound must end the worker, not the machine.
Every gate below is decided at one of two levels, and the relation between them
is calibration rather than coverage. The **fixture
level** runs wherever the gate runs, on the committable corpus. The **library
level** runs against the author's real library or a disclosed machine and cannot
be committed. A fixture that stands in for something real — the synthetic
synthetic document, the reference machine, a scaled corpus — carries a fidelity
claim, and
the library level is the only thing that can renew it: the RSS gate's revalidation clause
is the pattern, and it binds every surrogate here, not only that one.

- **The golden gate (D11 = set)**, which decides R34. A pinned multilingual fixture
  corpus, ~40 queries, answer *sets* at k=10. The corpus represents a real
  library rather than an ideal catalogue: it preserves declared, intentional
  item-type errors beside correct types; uses authentic source formats rather
  than converted format specimens; and identifies translations, alternate
  publications, book/chapter relations and metadata-conflicting duplicates as
  relations between records. It also carries multi-attachment items for the
  same text in different formats, the same text in different languages, and an
  article with its presentation; retrieval remains item-level and evidence
  identifies the attachment that supplied or skipped a passage under D6's
  deterministic per-language selection. The fixture pins attachment order,
  detected languages, selected keys and sibling skip reasons; same-language
  siblings do not imply that both bodies are indexed. Representative failure
  controls cover malformed, missing, textless, mislabeled, stale and
  parent-inconsistent attachments beside a metadata- or note-only item; each
  declares its expected degradation and whether it belongs to an answer set.
  Fixture size follows its pinned passage distribution and evidence needs, not
  a fixed parent-item tally. Pinned structural examples cover answer-bearing
  table cells, a figure caption, an annex or appendix, a footnote or endnote,
  multi-column text, and equation-heavy prose; each names its attachment and
  locator and says whether text or visual structure is under test. Annotation
  fixtures distinguish PDF-embedded, Zotero-database and note-copied content;
  preserve annotation and page locators, note block structure and source
  lineage; and cover textual, image and ink shapes without treating identical
  text as identical provenance. Project Gutenberg is an admitted source for
  authentic same-work UTF-8 text, HTML and EPUB siblings; each official file
  is pinned separately because the ebook identifier does not freeze bytes. The corpus
  crosses Zotero's stock extraction limits of 100 pages and 500 000 characters
  independently and together, recording total and indexed values for both and
  placing answer-bearing text on each side of each boundary. Thresholds derive from the
  stability artifact: the measured per-query Jaccard minimum under
  legitimate perturbation is 0.25, so a 0.5 floor would flag legitimate
  churn. The thresholds: mean Jaccard ≥ 0.8, at most 5 % of queries below
  0.35, and a hard floor of 0.2, below the observed legitimate minimum and
  far above the failure class's measured 0.00. Order is deliberately ungated
  (`identical_ordered` was 22/60 under legitimate perturbation; an order
  gate flakes, gets turned off, and that is how a past defect
  happened). Re-pins are commits
  whose set diff is the review artifact, and the golden set is re-pinned at
  entry granularity when entries exist; until then it gates item
  projections and says so. Each pinned query records, at pinning, which corpus
  its answer needs — core, notes, group, or deep-body — and the facet rides the
  same review artifact as the set. Rung evaluation binds the queries whose
  facet the corpus already covers: goal 4 closes on the covered subset, and
  the rest join goal 5's evaluation when their corpus lands. The corpus carries a cross-lingual slice — EN and
  FR queries whose answer sets are Vietnamese entries — gated separately from
  the monolingual queries, so a regression names which of R7 and R29 it broke.
  Beside it, never replacing it, a body-only parallel slice uses the 157
  English–Vietnamese twin records in both directions. Shared record fields are
  masked; it reports document- and passage-level hit@10 separately for en→vi
  and vi→en. It measures embedding-space alignment on equivalent text, not
  relevance to a user's question.
  The same pinned set decides R34, and the two readings of it are opposite on
  purpose: the stability reading compares one run against the last and
  tolerates legitimate drift, which is what the thresholds above are for, while
  R34 compares the run against the pinned answers and tolerates none. A corpus that
  can be stable and wrong is exactly why both readings exist, and its
  intersections — a 15 000-page PDF in a non-Latin script, a
  scale
  run at the multilingual default — are where terms that look independent fail
  together.
- **R13, the soak gate.** Three P0s, a full 10k drain, 1 query/s each,
  kill -9 the conductor twice, and freeze it once (SIGSTOP through a
  migration) — the wedged-not-dead case: the frozen parent closes no pipe
  and runs no cleanup, so only the worker's own lease poll can retire the
  orphan, and the gate asserts it does within the migration gate. Assert:
  p95 ≤ 1.5 s, zero SQLITE_BUSY
  surfacing, WAL ≤ 256 MB, lease migration < 30 s, zero double-commits,
  and duplicate compute ≤ 1 embed batch plus one in-flight document's
  re-fetch and re-segmentation per failover. **The conductor-latency
  clause** is now a confirmation rather than an acceptance gate: query p95
  measured on a P0 while the conductor drains beside it, against §5.2.9's
  warm-query band. What it used to gate — whether the writer needed a process
  of its own — was ruled on other evidence (DECISIONS.md 2026-09-02), and the
  clause could not have gated it in any case, since it needs a built conductor
  and the boundary is written before one exists. It keeps its subject: the
  writer and the queries are on separate processes and this measures that the
  separation delivers, against a machine whose cores they still share. A
  confirmation is not optional: a failure here is no longer explicable by the
  topology, which makes it more serious than it was, not less.
  **The service clause**, added with that topology: the same p95 while the
  embedding service is cold, so the degradation §5.2.5 states — labeled
  keyword-only, never a silent wait — is measured rather than asserted.
- **The disclosure gate**, over R17's device clause. Status names the execution device actually
  serving, and that clause gates everywhere, on every machine. The throughput
  half moved to R32, so this gate no longer
  carries a wall-clock threshold.
- **R32, the build-time gate.** Two bounds on any full build with the default
  configuration — the first, and equally a rebuild from nothing after an index
  is abandoned — and **a time bound with no machine attached
  is not a bound**, so each is stated on disclosed hardware and nowhere else.

  *The reference machine*: a laptop-class x86-64 CPU, four cores, no GPU, in
  the ONNX runtime the implementation ships — the class the feasibility run
  used (`bench/results/0025-x1-recall/embed-feasibility.json`, an Intel i5-8250U
  at 1,6 GHz). It is deliberately modest: a bound met only on the author's
  desktop would promise nothing to anyone else.

  *The bound is a rate*, because a wall-clock number silently fixes the library
  size: "inside twelve hours" promises a 15k-library user something and a
  60k-library user nothing. Per **passage**, not per item — R8 makes items
  deliberately non-uniform, so a per-item rate measured on short papers says
  nothing about a 15k-page PDF and one loose enough to admit that PDF is absurd
  for papers. The passage is the unit the work is done in and the unit every
  artifact already measures.

  *The bound is on the pipeline, not on one stage.* A build finishes when
  extract, chunk and embed have all finished, so a bound on embed alone is not a
  bound on the build. R32 states the rate the gate asserts — **≤ 150 ms per
  passage**, **≤ 75 ms** as the SHOULD — and this section supplies the machine
  it is measured on and the arithmetic behind the wall-clock figures it quotes.
  A rate is assertable from a few hundred passages, per stage, so a regression
  surfaces in a minute instead of at the end of a build.

  *The allocation across stages is provisional, and the total is not.* Embed is
  the dominant term: **≤ 145 ms** at the MUST and **≤ 73 ms** at the SHOULD,
  leaving **5 ms** and **2 ms** for extract, chunk and the record write
  together. The allocation may be re-cut in any proportion so long as the total
  holds, because the total is what the user feels and the split is an
  engineering convenience; R32's own 150 ms and 75 ms are untouched by any such
  re-cut.

  Extract and chunk are no longer unpinned. Ticket 0500 measured them on the
  reference machine over **22 562 passages** of the real library, five
  repetitions on disjoint slices: extract **0,142 ms** per passage, chunk
  **0,022 ms**, **0,164 ms** together serially and **0,122 ms** at the build's own
  local-API concurrency of 2
  (`bench/results/0500-extract-chunk/extract-chunk-throughput.json`). That is
  about half a percent of the 30 ms the two carried before, which is why the
  re-cut moves nearly all of it to embed and still leaves the record write — the
  third term, not isolated by that ticket — more than an order of magnitude of
  room.

  What the measurement also settled is the mix. Extraction is not *usually* a
  cache read: in the shipped build it is *always* one. The full-text source can
  serve only what `/fulltext?since=0` names, so an attachment the platform has not
  extracted is invisible to the build and is never parsed by it. The expensive
  path is real — forced re-extraction cost **10,08 ms per passage** median on the
  same machine — but the platform pays it when a file is first opened, outside
  this bound.

  The fixed term is the one to watch instead. Before a passage is read, the source
  walks the attachment pages to map extracted attachments to their parents:
  **80,6 s** on a **9 302**-attachment library, one-time per build. That is
  21,8 ms per passage on a 60-item sample and 0,17 ms on a full-library build, so
  here a *sample* is the pessimistic measurement and a rate taken on one can fail
  a bound the real build meets.

  *The wall clock is the promise*, and it is this rate against the measured
  census of §5.2.9 — the census is the bridge, and the arithmetic is shown rather
  than folded in, so a reader with a different library can do their own. At the
  design point's 567 829 passages the two rates land at 23,7 h and 11,8 h, which
  is where R32's **day** and its half come from — "indexed today", written down.
  A 15k library is roughly 22 500 record chunks, so the same bracket puts
  records inside R32's **hour**, and no separate rate is needed for them.

  The two small multilingual candidates and the incumbent sit in the SHOULD
  band on this machine; the base-sized candidates clear neither, and the largest
  is outside the MUST outright. That is the throughput constraint applied at
  the registry's ship gate (the CPU cells recovered from
  `bench/results/0264-gpu-arm/`, beside the feasibility run).

  Two costs of stating it as a rate, named rather than left to be discovered.
  A rate hides fixed and non-linear work — model load, compaction, WAL
  checkpoints, the frontier's own bookkeeping — so a sample can pass while a
  full build does not; the gate therefore asserts the rate on every run and the
  wall clock whenever a full build is available, and a disagreement between
  them is a finding about the non-linear part rather than noise. And a rate
  measured on one passage-length distribution does not transfer to another,
  which is why the fixture's distribution is pinned with the corpus.

  *Second configuration*: the disclosed GPU host, where the same bounds hold
  with room to spare. It is a second place the gate may run, never a substitute
  for the first — the promise is to the user with a laptop.

  Both bounds are design numbers this section owns, pinned here from the
  measurements cited rather than before them. A machine slower than the reference is not a
  failure of the promise; it is outside the disclosure, and the gate reports
  the machine it ran on so a reader can tell which case they are looking at.

**R13 observability**: a server reports the pipeline's state as it reads it
from the file rather than as something it is doing, since 2026-09-02 no
server ever runs the pipeline. `pipeline: "held-by-other"` keeps its meaning
with the conductor as the process that holds it: a server reads the conductor's
lease and liveness rows and reports the pipeline as held elsewhere, rather than
reading its own idleness as an idle pipeline.

#### 5.2.9 Budgets, recomputed and honestly scoped

**Disk** at the design point, under the token geometry (both counts stated).
**The passage count is measured, not derived**: 567 829 passages at the
resolved budget of 498 tokens, counted over all 13 630 fulltext caches
(211 342 921 tokens through the embedder's own tokenizer;
`bench/results/0140-passage-census/census.json`). The earlier
≈ 250–300k figure was arithmetic at a 768-token maximum and understated the
count by nearly half — the measurement, not a rescaling, was necessary,
and it was right to insist: under structural chunking the
maximum rarely binds, so no ratio could have produced this number. One stated
approximation: the census chunks each cache as one paragraph sequence (seg/1
does not exist yet), and entry boundaries only add chunk closures, so the
count errs low by that margin. The same corpus yields 650k under the old
1 200-char stride, coherently above the token count since 498 tokens is
roughly 2 000 characters; bench comparability keeps the old count. FTS
~0.3–0.4 GB + gzip slabs ~0.23 GB (680 MB raw at ~3:1) + int8 sidecar
~0.22 GB (567 829 × 384) + metadata/ledger ~0.1 GB ≈ ~0.9–1.0 GB, under
v1's 2.3 GB, because passage text is no longer stored twice (passages are
references into slabs) and the chunks are fewer. The float32 fallback adds
~0.87 GB.

**RAM**, by process class rather than by server, since 2026-09-02 the model
is resident once for the machine (§5.2.5). A P0 idles at ≈ 70 MB (Node) +
32 MB (cache) ≈ ~100 MB **and holds no model**: the ≈ 570–660 MB of
multilingual query model at its 8-bit rung (the measured range across
candidates) is the embedding service's, paid once per generation on first
semantic use wherever it comes from. The conductor adds a Node process plus one
text window and the segmenter's own state; the pipeline worker adds transient
residency only — run-to-drain, at most one, its peak now one token-budget batch
and the streamed decode rather than a model plus a batch (§5.2.5's dial).

The aggregate this replaces was ≈ 2×700 ≈ ~1,4 GB at two clients, which
assumed each server carried its own copy. Two clients now cost ≈ 2×100 plus one
service ≈ ~770–860 MB across the range, and the model term stops scaling with
the number of clients altogether — the single largest change this topology
makes to C3's exposure.

Three ceilings are left needing a re-pin rather than re-pinned here, because a
ceiling is a ratified number and the arithmetic above is only a derivation. The
server ceiling was priced on a process that loaded the query model and no longer
does. The pipeline ceiling was priced on a worker that loaded the passage model
and no longer does — which is also why finding F1's collision between that
ceiling and the multilingual candidates may dissolve rather than be ruled, a
re-check and not yet a claim. And the embedding service has no ceiling at all,
being a class C3 did not have. One term stays honestly unmeasured through all
of it: the residency of a live batch — every sweep on disk priced batch size in
latency, not RSS — so what the heaviest candidates actually cost is a claim
§5.2.8's RSS gate and a further sweep verify, that sweep recording RSS with a
real batch in flight rather than at rest. The
sole-writer topology confines the long-document RSS risk to the worker's
streaming fetch; it does not buy wall-clock. Whether
the server ceiling scopes per process is settled: it does, because that is the
scope the gate can assert; the two-client whole-machine arithmetic above keeps
the aggregate visible. Dual-embed no longer threatens
the budget (the lazy-load rule, §5.2.7).

**Status, the observation path**, which R17 promises and which is budgeted
apart from the query path because it is polled rather than asked. Two figures
are measured and one is not. The rejected implementation, a GROUP BY over the
table a stage is writing, cost 374 ms with a cold cache and grows with the
table; the maintained counters answer point reads sub-millisecond and do not
(§5.2.8). What is NOT measured is the band under load — status while all three
queues run, which is the condition R17 states and the only one a user meets.
The convergence harness polls status at 1 Hz for the length of a build (§5.2.8)
and touches nothing else, so the *occasions* to measure are already specified
and need no run of their own — but the series does not exist yet, and saying it
comes free would be wrong. A poller that sleeps between calls records the
build's wall clock, not the latency of the call: measured 2026-09-03 on
`bench/run_build.py`, whose elapsed is the true build time rounded up to the
next poll boundary, so two distinct scale points both reported 140,3 s at
`--poll 20` — the quantum, not the build. Recording the latency of each status
round trip is therefore a driver change, and that change is the work this band
waits on. Until the series exists no number is stated here, because a bound
nobody measured is a bound nothing can fail.

**Warm query**: probe 0–1 request + embed 20–50 ms + FTS tens of ms + a
single-pass sidecar scan (X1) + fusion, which is where R6's two numbers go —
≈ 300–700 ms in the ordinary case, against the 3 s it promises never to exceed.
Without the hidden second scan (§5.2.6), and with one term the shared model
adds during a build: up to one quantum of wait behind a passage batch, bounded
by the query lane's preemption at batch boundary (§5.2.5) — the contention the
one-copy rule bought with the RAM it saved, named so the soak measures it
rather than discovers it. Under the API execution mode the embed term is a
network round trip, hundreds of milliseconds to seconds, and no provider
documents a p50 or a tail: the 700 ms band is not expected to hold there, and
the 3 s bound is kept by the timeout that degrades to labeled keyword-only
(§5.2.5).

---

### 5.3 Open decisions: committed, or experiments with decision rules

- **Semantic path at scale — X1.** int8 ships if recall@30 ≥ 0.98, pool ≤
  32×topK, and scan+rerank ≤ 400 ms at 650k; the float32 slab is the
  permanent fallback. The single-pass entry heap makes the pool guarantees
  free. The measured 1-bit arm is the leading narrower candidate, with its
  candidate-specific pool recorded, but remains provisional until its
  scan-plus-rerank cost is measured on this 650k substrate; it does not amend
  the int8 rule before then.
- **CJK — committed.** 2-gram twin tables, CJK-bearing passages only,
  backfilled from slabs; typed degradation meanwhile.
- **Stopwords — committed.** PR #19 merged (`4f61b2a`); the deletion itself
  ships in its follow-up (0014, now the train's head). X2 rejects the former
  ~50 % rule: only 9 terms drop and p95 remains 820,7 ms against the ~500 ms
  allowance. Prune query terms at df ≥ 30 %, the working point inside the
  measured ~25–35 % window: above that window the budget is not recovered;
  below it content terms begin to disappear. At the working point pruning
  alone reaches 463,5 ms p95. If fewer than two terms survive, send the raw
  token set: `to be or not to be` otherwise retains only `not`, so an
  empty-set fallback does not fire. The cutoff is justified by cost — each
  dropped term avoids walking a posting list — never by ranking quality;
  BM25 already down-weights common terms continuously, while a hard cutoff
  can only approximate that signal.
- **Fairness — committed.** The three discovery classes, then two-band body
  with derived K, and nothing below the band cap inside the body tier
  (§5.2.3); smallest-first rejected on the record, and re-argued there once
  the class order changed what separates it from ours.
- **Fraction-RRF — conditional.** Ships behind the golden gate; calibration
  deferred to its own ticket with the library-derived pair protocol (§5.2.6).
- **Version-0 freshness residue — X6 decided.** Live re-extraction through
  Zotero's own queue changed a nonzero full-text census value to 0 without
  moving the attachment item version, and a 0-valued arm remained 0. Build the
  bounded re-verify sweep (ticket 0592), with its horizon reported. The residue
  remains disclosed as ours alone: C1's reading that the platform accepts the
  same residue was refuted at source, so nothing here is platform-aligned.
- **Census cadence — X7 decides.** Local census every tick, unless the parse
  exceeds 50 ms at 30k entries; then every 5th tick.
- **Constrained-MATCH threshold — X4 decided.** The smallest real-corpus arm
  exceeded the rule, so no `json_each` constrained step ships: the ladder
  refetches deeper and then ends at the honest R18 give-up. Ticket 0590
  measures how often realistic collection and tag scopes reach that outcome;
  it commissions no replacement unless partial answers prove common.
- **The 15 000-page PDF's RSS — X3, split in two.** X3a, runnable before any new code,
  baselines stock upstream, uncapped via
  `ZOTEUS_INDEX_FULLTEXT_MAX_CHARS=0`, on the 44,9 MB document (the 2 084,9 MiB
  class) and feeds the rss-gate fixture. X3b, the streamed-slab measurement
  against C3's pipeline rule, travels with the entries machinery (scoped issue
  B).
- **Segmenter — X5 gates scoped issue B.** X5 measures the segmenter as
  shipped, both paths, and its ground truth is held out of the thing it
  scores. Corpus: the real library, one arm per document class — books and
  proceedings, the primary class; the dictionary, the rare case; and the
  signed encyclopedia, the edited handbook, the numbered technical report and
  the thesis, the classes the acceptance test names. The reference classes —
  dictionary, encyclopedia, handbook — are measured on their own because
  retrieval from reference material matters at least as much as retrieval
  from articles. Each arm samples 50 cut points uniformly
  at random (seeded, recorded) from that arm's accepted entry boundaries.
  Ground truth: where a document carries an embedded outline, the outline's
  page targets. The segmenter runs with its outline tier disabled on such a
  document, so the layout tier and seg/1 are what get scored; seg/1 keeps its
  contents-list signal, because parsing the list is necessary but not
  sufficient — the cut must land on the outline's page, and the scorer locates
  a cut's page through `pdf.js` independently of the segmenter's own page
  estimate. Where a document carries no outline — the scanned books, the
  dictionary — a human scores the cut against the book. What is *not* ground
  truth: the document's own printed table of contents, which seg/1 consumes, so
  a score against it would certify parsing the list rather than finding the
  boundaries. Rule, per arm: ≥ 45/50 correct ships the entry story for that
  class; 40–44 raises the confidence gate and re-runs; < 40 means synthetic
  entries carry that class, labeled. Verdicts are never pooled. The primary
  class and the dictionary gate scoped issue B; the other four arms are
  measured and reported, not gating.
- **Cross-provider fidelity — X8 decides where the device lives.** Same model,
  same rung, the GPU provider's vectors scored against the CPU provider's over
  the fidelity probe corpus; the cells ride the 0264 GPU arm, at every rung
  both providers load, and the CPU side is the 0263 artifacts already on disk.
  Rule: at mean cosine ≥ 0,999 (the field's vector-compatibility bar,
  verification/FIELD-REVIEW.md) the execution provider stays out of the embedder key —
  device is an execution detail recorded in results, never in vector identity,
  and an index embedded on one machine can serve on another; below the bar,
  the provider enters the key and the adopt-a-foreign-index path (the copy
  shape) dies on the evidence at that rung. Either way fp16
  is a single-machine rung: the CPU provider cannot load it, so no CPU
  query-side embedder can match an fp16-embedded corpus, and cross-rung mixing
  is a measured failure.
- **Budget scoping under N processes** — the scope is settled in §5.2.9: each
  ceiling binds per process, which is the scope its gate can assert, and the
  model's residency is machine-scoped now that one service holds it. What stays
  open there is the re-pin of the three ceilings the topology re-cut.
- **Autonomous embedding service — architectural direction, open ownership.**
  The out-of-process service and its `local_endpoint` mode are ruled in §5.2.5;
  which process hosts it is not. Under comparison: Zotero #6012 runtime reuse
  (probe 0496), a bundled child, a per-user service, an external
  OS/community facility, and the two network candidates — the GPU-host
  remote embedder (DECISIONS.md 2026-09-01) and the commercial API
  (DECISIONS.md 2026-09-02).
  The decision rule includes install time, cross-platform packaging, custody
  and uninstall behavior, single- and multi-P0 RAM, failure semantics, quota
  and key custody, and whether this responsibility belongs in zoteus at all.
  The experiment is parallel to, and never a blocker for, registry entries or
  validation.

#### Rejected alternatives

Each killed by a verified fact or a critique: cursoring any fulltext sequence
on the local transport, a universal fulltext census across transports (it
would hammer api.zotero.org), passage-scope AND/NOT, the stopword-filtered
token stream for phrase parity, the always-resident dual model, the 0.5
golden floor (artifact-refuted), item-granularity smallest-first, trigram CJK
(the modal Chinese word is two characters — corroborated by the platform,
which tried trigram for content and reverted to `unicode61` three weeks later,
`0ce289a`, 2026-07-17, forcing a rebuild, and now reserves trigram for notes
alone), `carray` (not shipped in
`node:sqlite`), an in-place v2 schema under the old filename, pause gating
deletions, and the "contained" D3 PR as first proposed.

---

### 5.4 The biggest remaining risks, and the cheapest falsifiers

**Risk 1 — the segmenter is unmeasured, and everything downstream inherits
it.** Entry collapse, locators, dedup, the golden re-pin, and the long-document
arithmetic all stand on the segmenter's error rate — the PDF path's layout
tier and seg/1's flat-text heuristic alike — and neither has touched a real
extraction of its primary class, books and proceedings. Its failure mode is
*silent plausible-looking entries*: wrong citeable locators and wrong dedup
units, worse than honest synthetic ones. *Falsifier:* X5, scoring cuts against
each document's embedded outline with the outline tier held out — mechanical
where an outline exists, human where it does not — one arm per class, before
scoped issue B claims numbers. Below acceptable
precision the design degrades gracefully to labeled synthetic entries: the
contract survives; the chapter-as-peer story does not.

**Risk 2 — the version-0 freshness residue could be the whole story, not
the residue.** On a never-synced library the census may be structurally
blind to every re-extraction. The md5 widening catches file-driven changes,
but if X6 shows re-extraction bumps nothing observable, "coverage: current"
is a lie the design can only disclose, not fix: an honest but ugly
amendment to the freshness contract. *Falsifier:* X6, an afternoon, and I-1
is already drafted to carry the answer upstream.

**Risk 3 — upstream ships its own core before the design conversation
completes.** Sharpened since v1: he built #10's answer himself in days, the
risk materialized a second time on 2026-08-27, when he filed and fixed
his own follow-up to PR #20 (#21, with #22/#23) inside one day, and
#6012's `bestMatch` saved-search condition is the first crack through which platform
semantic results will leak into the local API. *Falsifier:* the harness
offer and the scoped issues themselves, after the PR train; those threads
settle fork-versus-upstream for the cost of writing them. The hedge is
structural: every stage behind a key; the contract, counters, and harness
are ours whoever writes the machinery.

**Risk 4 — N-process reality diverges from the protocol on exactly the
edges the soak must catch.** The conductor election, the activity-file
yield, and the lease timing are designed against named failure states
(orphaned worker, a steal mid-document, torn sidecar) but unmeasured, and
filesystem mtime granularity and WAL growth are folklore until soaked.
*Falsifier:* the §5.2.8 soak gate: scripted, 30 minutes, kill -9 twice. Its
assertions are constants the protocol can arithmetically meet, so a failure
is information, not noise.

**Risk 5 — gate decay.** The fold gate's waiver retired with #19's merge
(2026-08-27), the rss and convergence gates sit in `check-slow`, and a
14-day-stale WARN is advisory. This is the normalization-of-deviance
channel that produced a past defect, reintroduced at a slower time
constant with better signage: designed around, not away, and named so the
author can choose to tighten it. *Falsifier:* none needed, because the risk
is organizational. The mitigation is that every gate threshold cites the
artifact that justifies it, so re-pins and waivers leave evidence.

**Risk 6 — the writer split rests on a child spawn nobody has verified.** A
server hosted under Electron, which is the shape of the host population, sees
`process.execPath` as Electron, and a spawn without `ELECTRON_RUN_AS_NODE` or
its equivalent launches a GUI instead of a Node process. The isolation the
separate conductor and worker buy exists only if that spawn works, and nothing
has verified it on the hosts that matter. *Falsifier:* a spawn probe on the
host application, an hour, before the process boundary is committed in code;
the probe is also the mitigation, since its answer is either an environment
flag that works or a topology that needs no child.

---

The bet: the ledger keeps failures boring, and the contract keeps answers
honest. This design adds four things over its predecessor: the units are the
ones ratified (entries, records, items), the freshness protocol can no longer be
fooled by the counter it watches, N processes are a designed state rather
than an accident, and every promise is either watched by a gate whose
threshold cites its artifact or named as an experiment with a decision rule
(§5.3), each falsifiable in under a day, before the expensive code exists.

## 6. Security Considerations

### Intro

This section describes what the system stores, where that data can be read,
changed, or sent off the machine, and what the design currently says about each
point. It decides nothing. Where an answer below is a gap, closing it is a new
obligation, and a new obligation is a ruling: `DECISIONS.md` first, then
`SPEC.md`. This document only reports the gap.

The scope is local-only. Hosted mode is closed (D2, `SPEC.md`) and
nothing here reopens it. See "Out of scope" at the end.

Two words are used throughout. An *asset* is something a user would mind losing
or having read by someone else. A *surface* is a place where an asset can be
read, changed, or leave the machine.

Silence reads the same as "considered and found safe" — to a reviewer, to the
upstream maintainer, and to the author in six months. This section exists to
end the silence, not to assert that anything is mishandled.

### Assets

**The derived index.** `search-index-v2.sqlite` (`SPEC.md` §5.2.2) is not a
set of pointers into the Zotero library. It is a working copy of it. The slabs
table holds the source text itself, compressed, cut on entry boundaries;
passages are references into that text. The design slabs record and own-words
text for the same reason it slabs body text — otherwise a hit could not show
what it found.

So an attacker who reads this one file, without touching Zotero at all,
recovers titles, abstracts, keywords, creators, tags, the text of notes and
annotations (R16), and body-text passages for every attachment the pipeline has
reached, each with its heading path and character offsets. The right way to
think about the index file is as a second copy of the library, not as metadata
about one.

**Vectors.** Once semantic indexing has run, the index also holds a dense
embedding for each passage. Whether those numbers can be turned back into the
words that produced them is not established anywhere in this document. They are not
stored as compressed text and they are not designed to be reversible, but that
is a design intent, not a proof: published work on embedding inversion has
recovered short passages from vectors alone. This document does not resolve the
question. It lists vectors as an asset rather than assuming they are safe
because they look like numbers.

**Credentials for opt-in providers.** A user who turns on an API embedder
configures a key for it (`SPEC.md` §5.2.7 names one, Gemini). The key is
worth whatever unauthorized use of the paying account is worth.

**Query text.** What a user searches for says something about what they are
working on, whether or not the index itself ever leaks.

**Coverage and status.** Less sensitive alone, but it describes the shape of a
library: how large, how current, how much is annotated.

### Surfaces

**The local database file.** One file, WAL mode (`SPEC.md` §5.2.2). File
permissions: none yet. Nothing here states the mode the file is created
with, or whether another account on a shared machine can read it. C3
(`SPEC.md`) treats the machine as the user's; it does not say the
file is unreadable by anyone else with an account on it.

**The processes on the machine, and what passes between them.** Four classes
since 2026-09-02 (§5.2.5): N query-serving servers, one writer, one pipeline
worker, one embedding service. Three of them are new as a surface, because a
role that used to live inside a server now answers another process. Query text
reaches the embedding service on every semantic query and passage text reaches
it on every batch; work orders and intent pass between the servers and the
writer through the database file. Two hops are named: the stdio pipe between
the conductor and its worker, and the embedding service's Unix domain socket
inside the data directory, chosen over a localhost port because a port lets
any local process impersonate the service to a server while echoing the
expected fingerprint (§5.2.5). What that socket inherits is the file's
permissions, which is the same "none yet" as the database file's, now on a
live endpoint. A second property of that choice is disclosed and not decided:
macOS caps the length of a Unix domain socket path, and the default data
directory is long enough that the cap is a known hazard for where the socket
can be placed. What is not stated: any authentication beyond that, and the
whole of the Windows answer, since `nice`, `SIGSTOP`, stdin-EOF and Unix
sockets are POSIX assumptions and the host population is Claude Desktop on
macOS and Windows.

**Query and status tools.** These are MCP tools. The only transport the design
names is a stdio pipe between the conductor and its worker, with one zoteus per
MCP client (`SPEC.md` §5.2.5). No line here says zoteus opens a
network port for these tools, and no line says it never will. This is silence,
reported as silence, not a verified negative.

**Egress to remote providers.** R10 gives the count directly: two opt-in
exfiltration paths, no silent fallback (`SPEC.md` §5.2.7). One is the
one-time model-weight download the default local embedder needs, named in
status, degrading to keyword-only and never to an API embedder. The other is
passage text sent to a configured API embedder, which quotes a cost and requires
an explicit go-ahead per index generation; it crosses under §5.2.5's API
execution mode, synchronously, and never through a provider's batch endpoint,
which that section rules out. The default path sends nothing.

**Read-transport fallback, a narrower and separate gap.** The two paths above
are the only ones R10 counts, and both stay accurate. Item-metadata reads —
`getItem`, `getItemChildren`, `listCollections` — are a different surface: the
router prefers the local Zotero API and falls back to the cloud Web API when
the local one is unreachable, a rule that predates this design's review and is
not gated on a per-call opt-in. It cannot fire without a cloud API key already
configured. A keyless install fails such a read, but it fails *at the server*:
there is no pre-flight refusal in the code, so the request is dispatched to
`api.zotero.org` under user id 0 and rejected there (`library-router.ts:72`
for the address and `:80-81` for the routing, re-read at `b0e0bc8`; the file
moved to `src/router/` and the line numbers with it, the rule unchanged). No library content crosses, which is the substantive point; a
request does reach `api.zotero.org`. Where a key is configured, the
fallback is silent — nothing asks again at the moment it fires. It does not reach an index build: a build pins
its transport once and fails rather than re-routing, so no passage or
full-text content crosses this way. Ratified as disclosure rather than a
requirement (`DECISIONS.md`, 2026-09-01, ticket 0505): the gap is real,
metadata-only, and narrower than what R10 covers.

**Credential storage at rest.** None yet. This document records one fix — the Gemini
key moves out of the URL query string and into a header (`SPEC.md` §5.2.7)
— but not where the key is read from or kept between runs. No file, environment
variable, or OS keychain is named.

**Logs.** None yet. Nothing here says whether queries, passage text, or
errors are written anywhere, and if so where, for how long, or who can read
them.

**Local Zotero traffic.** The pipeline reads items, records, and full text from
Zotero's own local API on the same machine (`SPEC.md` §5.2.3, §5.2.4). The
conversation splits by process (`SPEC.md` §5.2.5): the conductor runs the
item and full-text census ticks, any query-serving process may issue the query
path's one bounded freshness probe (§5.2.4), and the pipeline worker alone
performs the whole-document text fetch. Bulk text reaches the conductor only
as bounded windows, never resident as a whole document — that, not "never
reaches a query-serving process", is the isolation the design provides.
None of this leaves the machine and
none of it counts against R10's two paths. It crosses the process boundary
between zoteus and the Zotero application. Whatever access control exists on
Zotero's own local API belongs to Zotero, not to this design.

**This repository.** The one surface that is not the system's. Measuring a real
library produces artifacts about real documents, and this repository is public,
so a measurement record is an egress path with no opt-in and no delete. It ran
that way: committed artifacts named documents from the author's library in
thousands of provenance fields until a ruling confined identification to
Zotero item keys and stopped the two drivers that wrote titles. Names
published before that ruling remain in the git log by the same ruling, which
declines to rewrite history. Two disclosures the ruling does not reach stay
open here: committed artifacts hold
`passage` and `snippet` text drawn from the library, and the benchmark query
sets are the author's own research questions.

### Current answers, gaps included

| Surface | Current answer |
|---|---|
| Database file permissions | None yet |
| Query and status transport | stdio per client (§5.2.5); no stated network listener, absence not verified |
| Egress to remote providers | Two opt-in paths, both named (§5.2.7); the default path sends nothing |
| Read-transport fallback (item metadata) | Falls back to cloud when a key is configured and local degrades; disclosed, not opt-in per call — ratified 2026-09-01, ticket 0505 |
| API-embedder credential storage at rest | None yet |
| Logs (queries, passage text, errors) | None yet |
| Local Zotero API traffic | Crosses a process boundary, stays on the machine; Zotero's own surface |
| This repository's committed artifacts | Item keys only; passage text and query sets still open |
| Inter-process transport and authorization | Conductor/worker stdio pipe; embedding service on a Unix socket in the data directory with the file's permissions, no further authentication; Windows unanswered (§5.2.5) |

Three of the nine rows answer "None yet" outright, and three more state an
answer carrying a named gap inside it: the unverified absence of a network
listener, the still-open question of passage text and query sets in this
repository, and the missing authentication and Windows answers for the
inter-process hops. That is the honest state of the design,
and stating it is this section's purpose. Each is a candidate ruling, not a
defect to fix here.

### Out of scope

Hosted mode is closed. D2 (`SPEC.md`) dropped the four privacy
requirements that applied only to it, and `SPEC.md` §5.2.7 confirms they
stay dropped: per-tenant contract keying, multi-tenant consent bookkeeping,
encryption-at-rest, and quota arithmetic. That ruling is not reopened here.

This section does not evaluate Zotero's own local API as a security surface,
only the point where this design's pipeline touches it.
