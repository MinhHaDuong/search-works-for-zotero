# REQUIREMENTS — what the system promises

## Intro

This document lists the user requirements. Numbering runs to R34 with gaps:
eleven items were retired on 2026-08-31, either because what verifies a promise
is not itself a promise or because they were clauses of another item, and a
retired number is never reused (DECISIONS.md). Each is written as a
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

Every R-item carries a force. The one that did not — R26, rejected as written on
2026-08-29 — was retired on 2026-08-31 rather than rewritten: it described this
repository's convergence harness, and what verifies a promise is not itself a
promise (DECISIONS.md). Ticket 0080 still owns the tier-priority change that
replaces the machinery it described.

## The four rulings that shape everything

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

## Requirements

Each item is a name, one sentence, and a paragraph. The **sentence** is the
promise, written so it can be read alone and tested by someone who has read
nothing else here. The **paragraph** unpacks it: what the sentence implies, what
was decided about it, and which document owns any number it depends on. The
one-word name is the handle the rest of the chain cites.

### Coverage and convergence

**R1. Coverage.** Every item in the search perimeter MUST become searchable
without anyone asking for it, and no state MUST ever need a manual rebuild.

Coverage MUST grow in ruling 2's class order, newest-first inside each class:
the crawler works a priority order, not a page cursor, and recency orders
*coverage*, not answers. An attachment that yields no
text MUST be treated as done rather than retried forever — it counts as covered,
marked metadata-only, its reason recorded and reported — so full coverage stays
reachable and honest at once. Per D8 below, OCR is out for now and the stage keys
leave room for a future extractor.

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
the arithmetic from the measured passage count, are DESIGN.md §2.8's. Finishing
today is a property of the configuration rather than of the hardware, which is
why this is its own promise and not a clause of one about GPUs. A full build and
not only the first, ruled 2026-08-31: a rebuild from nothing is the same work on
the same machine, and a user whose index was abandoned under a foreign schema
stamp waits exactly as long as one who has just installed. What these bounds are
not is a library already in service, where R3 bounds the cost of staying current
and R35 the delay before a change is noticed.

### Change and cost

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

### Corpus

**R8. Scale.** A 15k library and a 15k-page PDF MUST both be ordinary input.

The design point is at least 10 000 documents with full text and the system MUST
work at that size; the known red zone is that a full vector scan approaches 1 s
there. A 15 000-page PDF MUST be first-class too, not an outlier to cap away —
the 44.9 MB dictionary is the one in hand — and under ruling 1 it is a
collection of entries among peers. The two sizes are one promise because a
library is large in both directions at once.

**R16. Notes.** My own notes and annotations MUST be searchable, not only the
papers I collected.

Per D7 both are in: a note written in the reader and an annotation anchored to a
page are the reader's own words about the corpus, and a search that cannot find
them searches somebody else's library. They are child items, which is what makes
them easy to miss in a crawl that asks only for top-level items.

### Query

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
probe, embed, keyword search, the scan, the fusion — is DESIGN.md §2.9.

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
1. As that ruling amends it — D9 dissolved — deduplication is per section, and a
single document MUST NOT crowd other items out of the candidate pool before
deduplication happens. When many returned hits come from one document, the
result says so.

**R33. Modes.** Exact-word search, meaning-based search, and the two combined
MUST each work.

A query naming a rare exact string MUST return the item carrying it. A query
that paraphrases its answer without sharing a content word MUST return that
answer. Where both signals are present but weak, the combined answer MUST rank
the document they agree on above one that only a single signal favours — the
case that catches a fusion which has quietly dropped a side. Where the interface
offers a retrieval mode, the mode selected MUST be the mode served. The
combination rule belongs to DESIGN.md §2.6.

**R34. Recall.** For every query of the pinned set, the answer MUST come back
within the first ten results.

The pinned set's answers are known-correct and known to be in the corpus, so
this is a floor on what comes back rather than a score. Per D11 it fixes the
answer set and not its order: order inside those ten is unconstrained. Re-pinning
the set is a commit whose set diff is the review artifact, per DESIGN.md §2.8,
which is what stops a failing query being deleted instead of fixed.

### Multilingual

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

### Embedding configurations

**R31. Validation.** A search configuration offered to me MUST prove it works on
my machine before it is used, or fail loudly there.

Before it creates or queries an index on a concrete machine it MUST pass the
bundled automatic validation there or fail explicitly, and that failure MUST NOT
silently select another configuration. What identifies such a configuration —
every field that changes its vectors, carried as one versioned entry — is
DESIGN.md's. Sharing a content-free validation attestation MAY be offered only
by explicit opt-in, and library text, query text and Zotero identifiers MUST NOT
enter it.

### Custody and lifecycle

**R10. Locality.** Without an explicit opt-in, my library text and my queries
MUST NOT leave this machine.

The default build and query path make zero external calls. The one-time
model-weight download is the sole exception, and it is named rather than
discovered: an exception a user has to find out about is not an exception, it is
a surprise.

**R15. Deletion.** Deleting an item MUST remove its text everywhere, and
deleting the data directory MUST be the whole uninstall.

Deleting an item removes its text from every stage's store and from the queues
between them, not merely from search results — text that survives in a queue
comes back. At the other scale, index state, queues, watermarks and downloaded
models MUST NOT survive anywhere outside the data directory, so removing that
directory removes the system.

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

### Multi-library and multi-process

**R12. Libraries.** Group libraries MUST be searchable exactly like my own, and
indexing one library MUST NOT erase another.

Per D4 there is one merged index, with the library as one more R5 filter
alongside collection and tag. The second clause is the sharper one: a build for
one library that meets an index belonging to another MUST refuse rather than
overwrite it or append to its rows, because the failure is silent data loss
reported as success.

**R13. Concurrency.** Two server processes on one data directory MUST both
answer queries without corrupting the index or doing the same work twice.

The honest restatement accepted in DESIGN.md §2.5: no passage is ever
*committed* twice, and duplicate *compute* is bounded at one embed batch plus
one in-flight document's re-fetch and re-segmentation per failover. Two processes is the ordinary case rather than the exotic one — one
per client application — so the index has to expect company.

### Normalization

**R19. Normalization.** Every token the query side produces MUST be one the
index side can also produce.

Otherwise that query term can never match anything, in any language, and the
failure is invisible: the search returns nothing and looks like an honest miss.
The character-folding sweep that checks the agreement over 1 301 codepoints is a
gate rather than a promise, and DESIGN.md §2.8 owns it with every other gate.

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
| D9 long-document weight | **Dissolved** by the entry ruling. |
| D10 page fidelity | **Labeled estimate.** |
| D11 what the golden pins | The answer **set**, not the order. |

## Out of scope, said out loud

These seven things are deliberately not promised, so that silence does not
read as a promise:

- **Work does not travel.** The index is per-machine; a second machine
  re-earns it unattended via R1. Vector export and sync are out of scope.
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

## The goals ladder

The sheet is one flat list of promises. The ladder is the order they are made
true in: **five goals, numbered from the cheapest to assert to the most
expensive to earn**, each a bundle of these requirements named in the user's own
words. Every requirement here sits on exactly one rung.

| | the goal, in the user's words | why it sits there |
|---|---|---|
| 1 | **I can install it and take it off again.** Nothing leaves this machine unasked, one switch stops the work, deleting the data directory is the whole uninstall, and a configuration proves it runs here before it is used | its assertions need no corpus, no build and no library — they are decidable the moment the system is installed |
| 2 | **It does not lose or corrupt what it built.** Staying current costs what changed, two processes on one data directory neither corrupt nor duplicate, and an index under another schema version ends up served | needs a built index but not a good one, and a build that cannot survive its own second day never reaches the rungs above |
| 3 | **It answers, and it is honest about what it has.** Coverage converges unattended and finishes inside its bounds, the index answers while still filling, and it says how much is behind an answer and which emptiness an empty one is | the first rung a user can actually use, and the last one that can be judged without asking whether the answers are any good |
| 4 | **It finds the right thing, in my languages, and I can open it.** Three modes, the pinned answer inside the first ten, three languages with the lanes connected, and a hit that opens at its page | where it stops being an index and becomes search; every promise here is about the answer rather than the corpus |
| 5 | **All of my library.** A 15k library and a 15k-page PDF as ordinary input, group libraries in and never erasing one another, one's own notes and annotations, and a new item noticed unasked | the word *all* in the promise, and the expensive rung |

**The number is the build order and nothing else.** It says which bundle to make
true first, never which matters most and never how much of one is true. Each
rung is a conjunction: kept when every one of its members holds and at no state
before that, so a lower goal kept does not make a higher one partly kept.

**The method is tests first, bottom-up.** Write the assertions for the lowest
rung, make them pass, then climb. Until a rung's assertions exist its rows can
only be read from the source or inferred — a claim about nobody rather than
about the system — which is why a rung cannot be declared before its tests run.

**Which requirements sit on which rung is not repeated here.** The rosters are
on [README.md](README.md), where `bench/check_progress.py` holds each of them to
the ruling in [DECISIONS.md](DECISIONS.md) and fails the build when a
requirement sits on no rung, on two, or when the page and the ledger disagree. A
second copy in this document would drift from that one, which is this
repository's most expensive recurring defect.

**Above the top**, unnamed and unruled, sits the bundle this repository exists
to reach eventually: *works for someone who is not me* — R7's SHOULD tier, R24's
entry-heading and dedup clauses behind the segmenter, a pinned set that is not
the author's own questions, and the harness offered upstream. It is named here
so its absence does not read as an oversight.
