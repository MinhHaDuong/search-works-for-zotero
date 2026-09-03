# Search Works for Zotero

*An independent open workshop for advancing semantic retrieval in Zotero.*

Search should work across a whole scholarly library: records, notes,
annotations, articles, books, and very large reference works. It should find
meaning rather than merely matching strings, while remaining inspectable,
resource-bounded, current, and honest about what has and has not been indexed.

This repository is a public statement of that direction and a place to do the
work. It develops requirements, constraints, designs, executable experiments,
acceptance tests, and upstream contributions. It is not the home of a single
product and it does not assume that one implementation should win.

## The proposition

The lasting result should be a retrieval contract that the Zotero ecosystem can
implement in more than one way. Success may mean a change in Zotero itself, a
change in an independent server or plugin, a reusable test harness, or evidence
that causes a design to be abandoned. Shipping code here is one means, not the
definition of success.

Three work surfaces therefore have equal standing:

1. **Zotero itself.** [zotero/zotero#6012](https://github.com/zotero/zotero/pull/6012)
   and its successors are first-class design and influence points. Their result
   locations, saved-search representation, lifecycle, local-API surface, and
   retrieval semantics may decide which machinery outside Zotero remains
   necessary.
2. **Independent implementations.** [zoteus](https://github.com/oscardvs/zoteus)
   is the current working vehicle and upstream contribution target, not the
   project identity. Other servers, plugins, and future adapters are legitimate
   implementations of the same contract.
3. **The implementation-neutral workshop.** Requirements, measurements,
   fixtures, gates, and decision records live here so that claims can survive a
   change of implementation.

## What is already decided

The current design begins from three ratified rulings:

- **The unit of answer is the entry or section**, not necessarily the Zotero
  item. A dictionary is one item and many legitimate answers.
- **The bibliographic record is the semantic core.** Title, abstract, keywords,
  notes, annotations, and body text retain their identities rather than being
  flattened into an undifferentiated string.
- **Chunking respects document structure and carries context.** A chunk does not
  cross a detectable entry boundary; its heading path and item title travel
  with it.

Around those rulings, the system must converge without manual rebuilds, expose
honest coverage, avoid recomputing unchanged content, filter before truncating
answers, survive very large documents, and operate within explicit CPU and
memory budgets. These are testable requirements, not branding claims.

## How the workshop is organised

The specification is one document, [`SPEC.md`](SPEC.md), in RFC section order
(Introduction, Terminology, Requirements, Constraints, Design, Security
Considerations). This page is both the repository's public landing page and the
chain's entry point, the one place that says where each promise stands at the
reviewed baseline — durable status, not a live session handoff. What changes
week to week stays outside SPEC.md, at the top level alongside it, and
[`AGENTS.md`](AGENTS.md) indexes every document and directory with its role.

---

## Where the promises stand

This section owns one thing the rest of this page does not:
**where each of the twenty-three\* promises actually stands**, designed and
delivered. It owns no threshold, no budget and no decision rule. Every
number in this repository lives in exactly one document, and a status page
is the most inviting place in a repository to leave a second copy of one. So
the rows below carry status and addresses, nothing else, and
[`bench/check_progress.py`](bench/check_progress.py) fails the build on any
digit here that is not an address.

Measured against upstream **v1.13.0**, the reviewed baseline in
[`UPSTREAM`](UPSTREAM). The implementation is not in this repository: it
is [`oscardvs/zoteus`](https://github.com/oscardvs/zoteus), so "delivered"
always means *holds on stock upstream*, never *we wrote it*.

**Designed** — the promise has a settled design behind it.

`●●●●●●●●●●●●●●●●●●●●●●●` &nbsp; 23 ratified · 0 still open

**Delivered** — the promise holds on stock upstream today.

`●●●◐◐◐◐◐◐◐◐◐◐◐◐◐◐◐○○○○○` &nbsp; 3 shipped · 15 partial · 5 not yet

`●` shipped &nbsp;·&nbsp; `◐` partial &nbsp;·&nbsp; `○` not yet

**How each verdict was established**, since a verdict is only worth its
evidence:

12 measured · 8 read in the source · 3 inferred

**The requirements are objectively testable; these verdicts are not yet
tests.** Every requirement is a set of MUST clauses a harness could check, so
where a row is soft the fault is this repository's and never the sheet's. Of
the twenty-three\*, twelve\* rest on an experiment or a test that ran, eight\* on
opening the upstream source at the reviewed baseline, and three\* on nothing
executed at all — merged pull requests, design documents, reasoning. One row
crossed that line at this baseline: R15's residue inventory was swept around a
real target for the first time rather than only against fail-controls. The
`evidence` column says which, per row, so a reader can tell a verdict that
was checked from one that was argued.

Only the arithmetic is mechanical: every bar and every tally is recomputed
from the rows, never a row from a measurement. Closing the gap is the work
itself rather than a tracker over it: the fixture corpus in ticket 0029, the
gates in ticket 0026, which is where a check that runs now lives —
and the acceptance harness in ticket 0032. Their unit is the MUST clause rather
than the requirement, because a compound requirement graded as one token is
what made `partial` ambiguous before the evidence column split it.

One instrument already moves rows: [`bench/smoke_upstream.py`](bench/smoke_upstream.py)
drives the reviewed baseline over MCP against a real Zotero library, and each of
its checks names the clause it exercises and what would falsify it. It is not a
requirements suite and does not pretend to be — a check exercises one clause of
one requirement, once, against one library, which is exactly what separates
`measured` from `code` and nothing more. Its run at the reviewed baseline is
[`bench/results/smoke-1.13.0/checks.json`](bench/results/smoke-1.13.0/checks.json);
the session the instrument grew out of is
[`verification/SMOKE-1.10.0.md`](verification/SMOKE-1.10.0.md), which is history and
named here as history. Where a check cannot decide, it says `observed` and the row
keeps its weaker word. A run older than the reviewed baseline is not evidence about
it: until 2026-09-03 this paragraph pointed at one anyway, and nothing caught it,
because the baseline guard reads version strings and an artifact directory carries
none (ticket 0622).

Nothing recomputes a status when upstream ships, so the page is invalidated
instead: the moment the reviewed baseline in [`UPSTREAM`](UPSTREAM)
names a release this page does not, `make check` fails and stays failing
until each row has been read again. A judgement is not allowed to outlive
the release it was made about.

The two bars disagree on purpose, and the gap between them is the shape of
the project rather than a backlog. What this repository produces is a
specification, a measurement harness, and a small number of contained
patches; the machinery itself is built upstream. A single bar would average
those two facts into one number describing neither. What has actually gone
upstream, and on what terms, is [`SYNC.md`](SYNC.md) and
[`GOVERNANCE.md`](GOVERNANCE.md).

| section | designed | delivered |
|---|---|---|---|
| Coverage and convergence | `●●●●` | `◐◐◐◐` |
| Change and cost | `●●` | `◐◐` |
| Corpus | `●●` | `●◐` |
| Query | `●●●●●●` | `◐◐◐◐○○` |
| Multilingual | `●●` | `◐○` |
| Custody and lifecycle | `●●●●` | `●◐◐○` |
| Multi-library and multi-process | `●●` | `●◐` |
| Normalization | `●` | `○` |

---

## The goals ladder

Five goals, numbered in the order the work is done. The number is the build
order and nothing else: goal 1 is what to make true first, not what matters
most. Every requirement the sheet declares sits on exactly one rung, the rungs
run from the cheapest to assert to the most expensive to earn, and
[`bench/check_progress.py`](bench/check_progress.py) fails the build when a
requirement sits on none, on two, or when a rung's roster here disagrees with
the ruling in [DECISIONS.md](DECISIONS.md).

**Each rung is a conjunction.** It is kept when every one of its members holds
and at no state before that, so a bar below shows where a rung's members stand
and never how much of it is kept. Sequencing gives no partial credit: a lower
goal kept does not make a higher one partly kept.

**The method is tests first, bottom-up.** Build the assertions for the lowest
rung, then make them pass, then climb. Until a rung's tests exist, its rows can
only be `code` or `inferred` — a claim about nobody — which is why the evidence
column is the test column and why no rung can be declared before its assertions
run. The bundle and its ordering were ruled on 2026-08-31
([DECISIONS.md](DECISIONS.md)).

*Decided at* is the two levels and the relation between them. `fixture` is the
committable corpus, which runs wherever the gate runs; `library` is the author's
real library or a disclosed machine, which cannot be committed; `both` is a
fixture assertion standing in for something real, whose fidelity the library
level has to re-earn — the pattern the RSS gate's revalidation clause follows.
Under the MVP frame the **library decides and the fixture stands in for it**: a
conjunction of fixture-only assertions could go all-green while the author's own
library had never been searched, which is the one result *works for me* cannot
accept.

## Goal 1 — I can install it and take it off again

Nothing leaves this machine unasked, one obvious switch stops the work, and
uninstall removes every declared piece of derived state and leaves no
undeclared residue. Lowest rung because its assertions need no corpus, no
build and no library: they are decidable the moment the system is installed.

`●◐○` &nbsp; 3 in the bundle · 2 rest on something that ran

**Every clause of the rung is asserted**, which is what the method asks
for before anything on it is made to work: seven checks in
[`bench/acceptance/assertions.py`](bench/acceptance/assertions.py), each with a
fail-control of its own, driven red by `make acceptance-fixtures`. That is not
the rung being kept, and the evidence column below says so: an assertion no
target has been run through decides nothing about a target. What it ends is the
state where a row could not be anything but a claim about nobody. The caveat
this paragraph carried until 2026-09-03 is discharged. The committed artifact
of the previous baseline predated the two newest checks and listed assertions
that had never been seen red, and it was left standing rather than overwritten
by a partial run, because an artifact measured where half the instrument is
missing is worse than one that is visibly older. The re-baseline had the
missing half — an isolation mechanism, which this rung's own R10 clause needs
and nothing else here does — so
[`bench/results/smoke-1.13.0/acceptance-fixtures.json`](bench/results/smoke-1.13.0/acceptance-fixtures.json)
covers every assertion, both R22 clauses included, and its list of assertions
never seen red is empty.

**Both R22 clauses need a positive control, and a target that cannot be given one
reports `not-run` rather than green.** The control is a second, never-stopped
instance of the same target, and it has to resolve state of its own: sharing a
derived-state root would put its work in the counters the clause reads, and
sharing a library would have it consume the very change the clause is about. A
target the harness cannot hand a separate library is therefore undecided here —
truthfully, since its clause was never tested — and ticket 0033 carries what
closing that would take.

**The rung had a fourth term until 2026-09-03, and what retired it was this
layer failing three times to assert it.** R31 asked that a configuration prove it
works here before it is used, or fail loudly. Three assertions were written for
it — reading exceptions, then reading status, then comparing entry identity — and
each one's red condition turned out to be another requirement's, R10's. A
requirement whose every reachable falsifier belongs to a neighbour has no
extension of its own, which is the apparatus test that retired R20, R21 and R26
on 2026-08-31, measured rather than judged. It is retired, its mechanism kept in
SPEC.md §5.2.5 and §5.2.6, and its user-facing residue is where R21's already
went: R17 and R18 say what answered, R34 holds the floor
([DECISIONS.md](DECISIONS.md), 2026-09-03).

| | the clause goal 1 binds | decided at | where its test lives |
|---|---|---|---|
| R10 | my library text and my queries stay on this machine without an opt-in | both | `R10-local-by-default`, `R10-no-egress` |
| R15 | uninstall removes every declared piece of derived state and leaves no undeclared residue | both | `R15-residue-inventory`, `R15-model-cache-under-declared-roots`, `R15-uninstall-removes-declared-state` |
| R22 | one obvious way to stop all background work, holding across restarts | both | `R22-pause-stops-background-work`, `R22-pause-holds-across-restart`; the implementation is ticket 0033 |

## Goal 2 — it does not lose or corrupt what it built

The cost of staying current is what changed, two server processes on one data
directory do not corrupt or duplicate, and an index under another schema version
ends up served. Second because these need a built index but not a good one, and
because a build that cannot survive its own second day never reaches the rungs
above.

`◐◐◐` &nbsp; 3 in the bundle · 3 rest on something that ran

| | the clause goal 2 binds | decided at | where its test would live |
|---|---|---|---|
| R3 | what staying current costs is what changed, never the size of the library | both | ticket 0579 |
| R13 | two server processes on one data directory, no corruption and no duplicated work | both | ticket 0579 |
| R23 | an index under another schema version ends up serving, either direction, no file deleted by hand | both | ticket 0579 |

## Goal 3 — it answers, and it is honest about what it has

Coverage converges unattended and the build finishes inside its bounds, the
index answers while it is still filling, the query path waits for no freshness
work, the two normalizers agree, and it says how much is behind an answer and
which emptiness an empty one is.

`◐◐◐◐◐○○` &nbsp; 7 in the bundle · 2 rest on something that ran

| | the clause goal 3 binds | decided at | where its test would live |
|---|---|---|---|
| R1 | the whole library is covered unattended and newest-first, a text-less attachment ending covered with its reason, coverage returning the same way after a schema-version flip, and superseded work draining to the latest chain unattended | both | ticket 0580 |
| R4 | the index answers while it is still filling, its first build included | both | ticket 0580 |
| R6 | the query path waits for no freshness work | both | ticket 0580 |
| R17 | how much is searchable, per stage, in one sentence, naming the device serving | both | ticket 0580 |
| R18 | an empty answer says which it is: nothing matched, or this scope is not indexed yet | both | ticket 0580 |
| R19 | a document and a query writing the same word in equivalent forms still find each other, lexical search excepted | both | ticket 0029, ticket 0580 |
| R32 | records searchable today and the body behind them, on the reference machine | both | ticket 0580 |

## Goal 4 — it finds the right thing, in my languages, and I can open it

All three modes, the pinned answer inside the first ten, scoping enforced before
truncation, three languages served unconfigured with the lanes connected, and a
hit that opens at the page it came from. Which pinned queries this rung binds is
faceted by the corpus each answer needs; the rule is SPEC.md §5.2.8's
(DECISIONS.md 2026-08-31).

`◐◐◐◐○○` &nbsp; 6 in the bundle · 4 rest on something that ran

| | the clause goal 4 binds | decided at | where its test would live |
|---|---|---|---|
| R5 | a scope is enforced before any answer is truncated, or the refusal is honest | both | ticket 0029 |
| R7 | the default path serves English, French and Vietnamese unconfigured, and should serve one language per script class | both | ticket 0029 |
| R24 | a hit leads to the page it came from, an estimated page saying it is one | both | ticket 0029 |
| R29 | a query in English or French finds the Vietnamese content, nothing translated | both | ticket 0029 |
| R33 | the exact string, the paraphrase, and the document both signals agree on | both | ticket 0029 |
| R34 | every pinned answer comes back within the first ten results | both | ticket 0029 |

## Goal 5 — all of my library

A 15k library and a 15k-page PDF as ordinary input, group libraries searchable
and never erasing one another, one's own notes and annotations in the corpus,
and a new item noticed without anyone asking. The top rung, and the expensive
one: this is the word *all* in the promise.

`●●◐◐` &nbsp; 4 in the bundle · 1 rest on something that ran

| | the clause goal 5 binds | decided at | where its test would live |
|---|---|---|---|
| R8 | a 15k library is answered, and a 15k-page PDF is indexed whole | both | ticket 0029 |
| R12 | a subscribed group library is searchable, and indexing one library never erases another | both | ticket 0016 |
| R16 | my own notes and annotations are in the corpus at all | library | ticket 0022 |
| R35 | a new, changed or deleted item is noticed without anyone asking | both | ticket 0503 |

## What the ladder does not say

Three terms bind a clause rather than an item. R19 is in by its matching clause alone:
its cadence — that the sweep runs on every check — is not a promise to anyone
and left the sheet on 2026-08-31, on the criterion that what verifies a promise
is not itself a promise, so it belongs to the gates in SPEC.md §5.2.8. R24 is in
by its page clause alone, its entry-heading and dedup clauses waiting on the
segmenter behind experiment X5. R15 is in by its uninstall clause: its
item-deletion clause is asserted with goal 2's built-index tests, as
event-then-state — after a delete is noticed and the tick completes, no store
or queue holds the text — and its clock is R35's, on goal 5 (DECISIONS.md
2026-08-31).

*Works for me* is the acceptance standard for the top three rungs together — the
promise stated in the user's own terms, *search all of my library*: every
document it holds, in every language it is written in, indexed today and
answered in reasonable time, by meaning and by exact words alike. The two rungs
below are what make trying it and keeping it possible at all.

**Above the top**, unnamed and unruled, sits the bundle this repository exists
to reach eventually: *works for someone who is not me*. R7's SHOULD tier, R24's
entry-heading and dedup clauses behind the segmenter, a pinned set that is not
the author's own questions, and the harness offered upstream. It is named here
so its absence does not read as an oversight.

None of those addresses is new work. The fixture corpus, the gates and the
acceptance harness offered upstream were scoped before this ladder existed; the
ladder says which of their assertions comes first, and the guard keeps the
count.

---

## The twenty-three

`designed` is `ratified` or `open`; `delivered` is `shipped`, `partial` or
`none`; `evidence` is `measured` (something ran), `code` (the source was
opened at the reviewed baseline) or `inferred` (neither). The standing column
cites the ticket, pull request or issue that carries the remainder — never a
threshold, which belongs to SPEC.md.

Read `delivered` and `evidence` together. `partial` with `inferred` is a
guess about a half-kept promise; `none` with `measured` is a failure someone
demonstrated. They are not the same kind of statement.

### Coverage and convergence

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R1 | Every item in the search perimeter MUST become searchable without anyone asking for it, and the system MUST NOT need a manual rebuild, whatever state it is in | ratified | partial | code | Incremental update, build resume and the coverage-gap catch-up all landed upstream, and v1.13.0 finished the resume where it had been half done: a build whose embedder gave up keeps its checkpoint instead of clearing it, withholds the library version stamp so `action:"update"` cannot run a delta across a half-embedded index, and a resumed build buys vectors for exactly the committed passages carrying none — no page re-fetched, no document re-read, no passage re-embedded (upstream #48, whose contract this repository supplied). That convergence actually reaches every item, unattended, is still unmeasured: the harness that would watch it is ticket 0026. Two clauses were re-read at v1.13.0 and neither moved — the crawl pages the library rather than working a priority order, and an attachment yielding no text is not recorded as done-with-a-reason, so it is re-examined and counted as missing (ticket 0019). The convergence-to-latest-chain clause now sits inside the reviewed baseline and is still unassessed, for want of the harness rather than for want of a release. |
| R4 | The index MUST answer queries at every moment of its life, including during its first build | ratified | partial | code | A capped or interrupted build answers queries and says it was capped, and v1.13.0 gave that answer one honest coverage signal: status names how many committed passages carry no vector, and a search over an index short of vectors says so in its own summary. What is still absent is coverage per stage, which is what would let a reader place a partial index in the pipeline rather than merely know it is partial. |
| R17 | "How much of my library is searchable?" MUST get a human answer, per stage, with a date | ratified | partial | code | Build status carries counters, not the sentence: N of M items, per stage, with the most-recent-covered date. Ticket 0120, ticket 0140. Both clauses were re-read at v1.13.0 and neither holds. Per-stage counters naming the input that triggered each unit of work still do not exist upstream: the release added a count of unembedded passages and a measured embed rate, which are per-job state on one build rather than a work counter, and upstream's whole metric registry is untouched by the release and carries a handful of names, none of them per stage, per trigger or per outcome (scoped issue A, ticket 0033). And the local path passes no execution device, so nothing names the one actually serving (`verification/DEVICE-AUTO-0264.md`). |
| R32 | On a laptop-class machine with no GPU, a full build with the default configuration MUST index at 150 ms per passage or better, which for a 15k library means records searchable within one hour and body text within a day. It SHOULD reach 75 ms per passage, which halves both figures | ratified | partial | measured | The timing half holds and the contract half does not exist. In the runtime zoteus ships, on a laptop CPU, the incumbent model reaches an overnight build of a design-point library, and so do the two small multilingual candidates R7 will choose between, while the base-sized ones do not (`bench/results/0025-x1-recall/embed-feasibility.json`, sampled and projected; the CPU cells ticket 0481 recovered from `bench/results/0264-gpu-arm/`; genuine GPU figures in `bench/results/0482-gpu-corrected/`). What is absent upstream is the whole contract: no reference machine, no bound of either kind, and no record-first phase order for the record bound to be measured against — the crawl pages the library rather than working a priority order, which is R1's newest-first clause going unmet. The bound is now pinned and it is a rate — per passage, over the whole pipeline, on a disclosed laptop-class machine (SPEC.md §5.2.8), with the wall-clock promise derived from it through the measured census. Only the embed term of that rate rests on measurement; extract and chunk are an allocation until ticket 0500 measures them. A time bound with no machine attached is not a bound, and a wall-clock one alone silently fixes the library size; this row was unfalsifiable without both halves. The constraint that puts on which embedder may be the default lands in ticket 0495, the ticket that decides what ships. |

### Change and cost

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R3 | The cost of staying current MUST be proportional to what changed, never to the size of the library | ratified | partial | measured | Updates ride a version watermark, so a resync no longer rebuilds the library. Invalidation is still per item, not per item and stage. The counter-churn clause is the better-off half: the full-text sequence is read as its own cursor, which removes the known cause, and nothing yet proves the absence because the counters that would prove it are R17's. That absence was re-earned at the reviewed baseline rather than carried, and earned twice over: the target's index status was read live on a running server in the layer's own default configuration and carries no `work` or `counters` object among its top-level keys, and the read came with a positive control — vectors were removed from the seeded index until the coverage key that reports a shortfall appeared, so the probe is known to be able to see a key arrive. Both assertions that would decide this clause therefore report `not-run` rather than a verdict (`bench/acceptance/durability.py`, `bench/results/smoke-1.13.0/acceptance-zoteus.json`). What the artifact alone cannot establish, and this row will not pretend it does: the adapter writes that nil down as a constant rather than deriving it from the reply, so it would answer the same on a target that had counters — ticket 0624, filed by this re-read. The instruments themselves have been driven red, every one of them this time, including against a fixture that recomputes nothing because it verified nothing, which is the arm a check reading only the `done` outcome reports as green (`bench/results/smoke-1.13.0/acceptance-fixtures.json`, whose list of assertions never seen red is empty). One thing the release moved in this row's favour without deciding it: a build whose embedder failed now withholds the library version stamp, so the next update cannot run a cheap delta across an index that is not current. Ticket 0579. |
| R35 | The system MUST notice a new, changed or deleted item within one minute, without anyone asking | ratified | partial | code | The machinery to notice a change exists upstream: incremental updates ride a library version cursor (SYNC.md records the commit that added them), and deletion reconciles against the key set. What does not exist is the clock, and that is now read rather than guessed. Upstream's whole update path has a single entry point and a single call site, reached only when an MCP caller passes `action:"update"`; no timer, Zotero event, watcher, stream, startup hook or deployment schedule starts it, and a query starts a first build on an empty index but never an update on a populated one. Every file and line is in `verification/UPSTREAM-DISCOVERY-0503.md`, where each nil is earned against a control that fired; re-read at v1.13.0, where the single call site is still single and the only timer anywhere in the search feature is the delay between embedding batches. So the clause "without anyone asking" is met by nobody upstream: the mechanism is there and the cadence is ours. The minute rests entirely on our reconcile tick, where deletion subtraction moved from every tenth tick to every tick to meet it (SPEC.md §5.2.4). The row stays `code` and not `measured` because neither latency has been measured on the reference machine yet; ticket 0503 stays open for that half. |

### Corpus

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R8 | A 15k library and a 15k-page PDF MUST both be ordinary input | ratified | partial | code | The item cap is configurable and says when it truncates, and the two-stage vector search retired the full-scan red zone; the default cap still sits below the design point. The long-document clause fails outright, re-read at v1.13.0 in a file the release does not touch: full text is capped per item by default, so a 15k-page PDF is indexed by its opening pages, which is the one place a default contradicts a promise. Ticket 0024 carries the filing. |
| R16 | My own notes and annotations MUST be searchable, not only the papers I collected | ratified | shipped | code | Issue #33, filed with a working prototype, was built by the maintainer and shipped: every child note and PDF annotation (highlighted passage plus comment) is crawled as its own passage carrying the parent item's key, on by default, opposite full text's off. One result slot per item; a hit is labelled `source:"note"` or `source:"annotation"`. Wired into both build and update — an index built before this existed fills its gap once, on its first update, and a note or annotation's deletion is found by census. Read in the source rather than measured, and re-read at v1.13.0, which does not touch it; ticket 0022. |

### Query

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R5 | Scoping a search by collection, tag, item type or date MUST be enforced before any answer is truncated | ratified | partial | measured | Scoping exists, but experiment X4 measured the constrained path and it lost to ranking everything, superlinearly. Confirmed on the real corpus, where scoping costs more than ranking the whole library: ticket 0025. The design answer is settled and negative: no constrained step ships, and the ladder ends at R18's honest refusal. |
| R6 | A warm query MUST answer within 3 seconds and SHOULD answer inside 700 ms, and MUST never wait on freshness work bigger than a single request | ratified | partial | measured | The query path does no freshness work, and the two-stage search brought the scan well inside the budget. Nothing gates it, so the property is true and unwatched — and v1.13.0 gave the query side work it did not have before: every query is pruned against a droplist derived from the library, and an unaccented term whose accented spellings outweigh it is expanded into a bounded group of them. Neither costs anything this repository has measured, so what is unwatched is larger than it was. |
| R18 | An empty answer MUST say whether nothing matched or the scope is not indexed yet | ratified | none | inferred | An empty answer does not yet distinguish "nothing matches" from "this scope is not indexed yet". v1.13.0 removed one cause of an unexplained empty answer without supplying the distinction: a query of nothing but common words is now answered on the words the user typed rather than pruned away to nothing (upstream #45, ours). The decision this row waited on is made and negative — experiment X4 ran and no constrained step ships, so the `scope{}` block stops being the last resort and becomes the answer whenever a narrow scope outruns the deeper refetch. The ladder edit that follows is awaiting ratification in DECISIONS.md; ticket 0025. |
| R24 | A hit MUST lead to the page it came from, and one entry MUST give one hit | ratified | partial | code | Local extraction now yields real page ranges and a document's own outline. The primary locator is meant to be the entry heading, which waits on the segmenter: ticket 0028, gated by experiment X5. The dedup clause waits on the same thing — deduplication is per item, not per section, because sections do not exist yet. v1.13.0 rewrote how a snippet is cut and left the locator where it was. |
| R33 | Exact-word search, meaning-based search, and the two combined MUST each work | ratified | partial | measured | Three of the four clauses have something behind them and the load-bearing one does not. Upstream serves a hybrid default, and our own measurement of it drove the two sides apart — the vector side moved while the keyword side stayed put (`verification/issue-30-thread.md`), which is evidence that both paths exist and are separately live. That last observation is dated in one direction now: v1.13.0 moved the keyword side too, by three of this repository's own merged pull requests — the hardcoded English stopword set is gone, the index keeps diacritics rather than folding them, and an unaccented query reaches accented spellings by expansion. Nothing tests the agreement clause: no check asks whether a document both signals rank mid comes back above one that only a single signal favours, which is the defect shape `verification/FIELD-REVIEW.md` records open in a neighbouring project. The mode-served clause is unread at the reviewed baseline. Ticket 0029 carries the probes. |
| R34 | For every query of the pinned set, the answer MUST come back within the first ten results | ratified | none | inferred | No pinned set exists upstream and nothing asserts one, so the promise is unmeasured rather than shown unmet. The adjacent evidence is not this: ticket 0265 scored a synthetic task — relevance being other passages of the same item — on a subsample of the real corpus, which measures retrieval strength and not whether a research question finds its answer. The corpus is ticket 0029, the gate is ticket 0026. |

### Multilingual

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R7 | The default path MUST work in English, French and Vietnamese with no configuration, and SHOULD work in Arabic, Chinese, German, Hindi, Russian and Spanish | ratified | partial | measured | Accent folding merged, and the default embedder is local. Two of this row's clauses were wrong rather than dated, and v1.13.0 is why. `ZOTEUS_EMBEDDING_MODEL` now names the LOCAL model, with the input prefixes an instruction-tuned model wants derived from its own id and deliberately kept out of the embedder identity, and a weight-precision selector sits beside it: upstream no longer hardcodes the English-tuned MiniLM construction, it defaults to it. So the MUST tier still fails at English alone on the default path, which is the verdict, and it now fails by a default rather than by a wall — read in the source rather than measured. The English stopword list is gone as well: experiment X2 measured its deletion and the deletion failed, which made a library-derived droplist a precondition rather than a follow-up, and that droplist is what shipped (ours, upstream #47). The two tiers were ruled and do not move the verdict; every candidate the study measured declares both tiers, so the filter's field is unchanged. Ticket 0240 measured the replacement field and closed with a recommendation that sets no default; ticket 0495 decides what ships. Ticket 0090, ticket 0091. |
| R29 | A query in English or French MUST retrieve relevant Vietnamese content without the user translating anything | ratified | none | measured | Stock upstream embeds with the incumbent English MiniLM chain on the default path, re-read in the source at v1.13.0 — where the local model became selectable, so the absence is a default's and no longer the construction's — and no cross-lingual channel exists there. That a multilingual embedder supplies one is measured rather than assumed: ticket 0266 ran EN and FR queries against Vietnamese, German and Russian content at every deployed dtype (`bench/results/0266-cross-lingual/SUMMARY.json`), and its negative control clears at every dtype for only two candidates of the six. Upstream's own precision selector now makes those deployments reachable without a fork, which moves the cost of the answer and not the verdict. The promise is a gate criterion for whichever entry the registry ships: ticket 0037, ticket 0495. |

### Custody and lifecycle

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R10 | Without an explicit opt-in, my library text and my queries MUST NOT leave this machine | ratified | shipped | measured | The default embedder is local, the model cache sits under the data directory, and the one API key that used to travel in a URL now travels in a header. Asserted against a running server rather than read: `bench/smoke_upstream.py` checks that effective embeddings resolve local and the embedder is active (`bench/results/smoke-1.13.0/checks.json`). A build pins its own transport once and fails rather than re-routing, so this stays about the embedder — see the neighbouring read-transport-fallback paragraph in `SPEC.md` §6 for the narrower, separate gap on the live-routed metadata surface. Closed as ticket 0017. The acceptance layer's `R10-no-egress` clause is red again at the reviewed baseline, and this run read the system calls rather than trusting the count: every attempt is a name lookup to this machine's own stub resolver, none goes off the machine, and the names asked for are **two** — the release-update endpoint the server contacts at startup, still enabled by default and unchanged in this release, and the model-weight host, because the isolated arm starts with no cache and the permitted one-time download reaches for it and fails. So the update check did not stop firing, and attributing the whole red to it would be wrong in both directions (`bench/results/smoke-1.13.0/acceptance-zoteus.json`; the assertion is `bench/acceptance/assertions.py`, the sandbox and its control arm `bench/acceptance/sandbox.py`; pull request #216). Both of the layer's own egress controls tripped both detectors on this host, so the instrument is known to work here. No library text and no query crosses, so the promise quoted in this row is untouched and the verdict is unchanged. What the red contradicts is the stricter clause `SPEC.md` §5.2.7 and §6 both state — that the default path makes no external call but the one-time model-weight download. Whether the clause moves or the code does is the author's; the question is in DECISIONS.md. |
| R15 | Deleting an item MUST remove its text everywhere. The target MUST declare every location in which it creates derived state. After uninstall, none of that state may remain, and no target-created derived state may exist outside the declaration | ratified | partial | measured | Deletion reconciles against the key set, so a deleted item loses its rows; that every queue and every stage lose it too is design, not yet code. The declaration half is no longer a claim about nobody. The target-neutral residue inventory (`bench/acceptance/assertions.py`) swept a harness-owned arena around a real target at the reviewed baseline and found every location it created accounted for by the declaration, with nothing outside it, and the model cache under the declared roots (`bench/results/smoke-1.13.0/acceptance-zoteus.json`). The smoke agrees from the other side and for the first time with a control that could have failed: the data directory held no model cache when the server started and held one after the queries, so the run downloaded it there rather than finding it there (`bench/results/smoke-1.13.0/checks.json`). The uninstall clause is still `not-offered` — the target declares no uninstall surface, and `purge` is maintenance rather than a substitute the harness may call to manufacture a clean result — so the promise is kept in part and this row stays `partial`. Ticket 0578. |
| R22 | There MUST be one obvious way to stop all background work, and it MUST hold across restarts | ratified | none | code | Verified absent, and re-verified at v1.13.0 where the index tool's action list is unchanged: there is no pause. Scoped issue A, ticket 0033. |
| R23 | An index written under a different schema version MUST end up serving, in either direction, without anyone deleting files by hand | ratified | partial | measured | One direction is now kept, measured, and the other is not. An index written under the previous schema version ends up serving **in place**: the reviewed baseline is the first release to carry a non-empty migration ladder, its one rung rebuilds the keyword index from the passages themselves inside the transaction that stamps the new version, and it was driven against a real library-sized index rather than a fixture — same path, nothing moved aside, every passage and every vector still there afterwards, the probe query answering, and the server naming the upgrade in its own notice (`bench/results/smoke-1.13.0/checks.json`). That is the positive control this ladder had never had. A stamp the build cannot reach — below it with no contiguous ladder up, or above it, since the ladder is forwards-only — is still detected before anything writes, moved aside byte-identical, never deleted, and answered from a fresh empty index; both stamps behave alike and the notice says a rebuild will salvage the vectors of every passage whose text is unchanged. So `abandoned` describes what is served for the unreachable stamps — nothing, until a rebuild — not what a rebuild then costs. The acceptance layer's serving clause reports `not-run` rather than red at this baseline, and the cause is now isolated and is the harness's rather than the target's: the arm that puts the index back before changing the stamp replaces the database file and leaves the previous run's write-ahead log beside it, so the empty index's log is recovered over the copy and the arm starts from nothing. Three arms on one seed separate it, and the layer's own guard is what caught it — it saw the arm start empty and reported not decided rather than a red, which is the behaviour the clause documents. Ticket 0623 owns the repair, and also the second half of the same finding: the older arm is parameterized two versions below the build, off the contiguous ladder, so as written it cannot observe the capability this release added. Ticket 0579. |

### Multi-library and multi-process

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R12 | Group libraries MUST be searchable exactly like my own, and indexing one library MUST NOT erase another | ratified | shipped | measured | Pull request #32 merged: the store now stamps the canonical identity of the library it holds and refuses a build or update for a different one, both at the tool boundary and again inside the engine, above the branch that used to clear or silently append. Ten tests assert it, all red before the fix. The one narrow seam this row reported as beyond the guard's reach is now inside it: `vector-salvage.ts` used to match a reused vector on passage id and text alone, and v1.13.0 scopes the salvage to the library that wrote the sidelined file, refusing across libraries and naming both in the refusal, with an unstamped file left permissive on purpose. That is upstream #44, this repository's own courtesy filing, built by the maintainer. Ticket 0016. |
| R13 | Two server processes on one data directory MUST both answer queries without corrupting the index or doing the same work twice | ratified | partial | measured | The first clause holds under test, re-run at the reviewed baseline. Two processes were started on one data directory with their lifecycles nested — a second process that only ever ran after the first exited is not company — and both answered while the other was live; a third process opened the same index afterwards and returned the identical hits (`bench/results/smoke-1.13.0/acceptance-zoteus.json`). That third process is the detector, because a pair can answer perfectly and leave the file unreadable behind it, and it has been driven red against a fixture that does exactly that. The second clause is `not-run` on the same absence R3's clauses rest on, re-earned by the same live read and subject to the same caveat about how the adapter supplies it (ticket 0624): duplicate work is invisible in a reply and readable only from work counters the reviewed baseline does not report. Two processes remain undesigned in the code and unsoaked. Scoped issue C, ticket 0035 and ticket 0579. |

### Normalization

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R19 | In semantic and hybrid search, when a document and a query write the same word in different but equivalent forms, the query MUST still find the document. Lexical search is exempt: there the user has asked for the string as typed, and matching it literally is the promise | ratified | none | inferred | No test, and the row says so. The clause was reworded on 2026-09-03 (DECISIONS.md) from an agreement between two normalizers — a property of our own source, decidable only by reading it — into a promise about what a user sees, decidable through the query verb alone against any target. Nothing of that shape has been executed, so this verdict rests on reasoning and on nothing that ran. The character-folding sweep is not this row's evidence under this wording and cannot become it: it reads a normalizer's source, and a promise is kept or broken where a user can see it. The sweep survives as a gate in SPEC.md §5.2.8, red against stock at the previous baseline on twenty-five misses (`bench/results/0578-fold-sweep/codepoints.json`, verdict red) — and that artifact is history rather than current fact now, because v1.13.0 changed the substrate under it: the index keeps diacritics instead of folding them, and the unaccented spelling is reached query-side by expansion, in one direction only, so the sweep measures a tokenizer upstream no longer ships and must be re-measured before it is cited again (ticket 0619). Which forms count as equivalent is now a property of the fixture corpus, per script class, so a pair nobody pins is a pair nobody checks — the narrowing the ruling accepts, and the same trade R34 already makes. The corpus is ticket 0029; the rung's assertion is ticket 0580. |

---

## How this page stays true

Three failures would make it worse than nothing, and each has a guard in
[`bench/check_progress.py`](bench/check_progress.py), run by `make check`:

- **A promise with no standing.** A requirement added to the sheet and never
  given a row here would leave the page quietly incomplete. The guard reads
  the sheet, not this file, and fails on any requirement missing, duplicated,
  invented, or filed under the wrong section.
- **A bar that stopped matching its table.** The bars are recomputed from the
  rows and compared against what is written above, so a status can never be
  edited in one place alone.
- **A second copy of a number.** Every digit here must be an address — a
  requirement, a ticket, an upstream item, a version. A threshold or a
  measurement restated here is a finding, on the same rule the glossary
  (SPEC.md §2) lives under.

The guard cannot check that a row is *honest*. Each standing sentence rests on
the ticket, pull request or issue it names, and those carry the evidence. One
rule about that is review's rather than the guard's, and it is the one this
page would rot by first: **a row is not upgraded to `measured` without the
artifact that measured it**, and an upgrade is a claim about one release, so it
is read again when the reviewed baseline moves. The guard fails the build on
the second half; only a reader can hold the first.

---

\* Marks a count maintained by hand — the guard recomputes the bars and the
evidence tally, never these spelled-out words (DECISIONS.md 2026-09-01).

## How work leaves this repository

This is a personal working repository, made public so that its intentions,
evidence, and unfinished reasoning can be inspected. It is not organised as a
community project and no contribution workflow is implied.

The deliverables land where they belong: as focused pull requests and issues in
Zotero, Zoteus, or another affected repository. This repository keeps the
longer argument, experiments, acceptance criteria, and decision record behind
those upstream interventions. A proposal need not use Zoteus, SQLite, FTS5, or
the current vector machinery; implementation-specific choices should not be
smuggled into the implementation-neutral contract.

## Current posture

Zoteus has shipped its own SQLite/FTS5 backend since v1.7.0, closing
[#10](https://github.com/oscardvs/zoteus/issues/10), which the prototype and
measurements here helped argue. The original storage-layer experiment is
complete. Its code is archived as evidence; the live work is the broader
retrieval design, its acceptance harness, scoped upstream contributions, and
the checkpoint against Zotero PR #6012.

[`tickets/`](tickets/) contains the current work train; completed work is under
`tickets/closed/`. [`UPSTREAM`](UPSTREAM) pins the reviewed zoteus SHA, and the
`upstream-status`, `upstream-catchup` and `upstream-checkout` targets report
movement against it and recreate the git-ignored `fork/`; `AGENTS.md` says when
to run which.

This is an independent project and is not affiliated with or endorsed by the
Zotero project.

## The prototype phase, kept as the record of the argument

Before v1.7.0, zoteus held its search index resident in JS objects and
snapshotted it with one `JSON.stringify`. On a 7 541-item library that cost
gigabytes of RAM, failed to serialise past V8's string limit, and could not be
reloaded by a stock Node. The same corpus in SQLite/FTS5 served from about
128 MiB of process memory and reloaded on a stock Node — which was the point.
It did **not** build faster: measured at the same chunk geometry, through the
same Zotero API, the build took about as long either way, because it is bound
by fetching from Zotero rather than by indexing.

Measured over **one corpus of 360 811 passages read by both backends** — the
same crawl's `search-index.json`, migrated in place, rather than two crawls that
ought to agree: **5 759,6 MiB against 128,0 MiB** resident, and **90,87 s
against 3,86 s** to first answer.

Read the cited bench artifacts and their owning tickets before quoting any of
that. The memory figure excludes the kernel page cache holding the database
file, where the JS heap figure has no such remainder; charge SQLite the whole
file and the win is 6,8x rather than 45x. Both numbers are measured and both
belong in any external claim. The figures are measurements of the fork's
prototype, not of upstream's backend.

## Bench

Two dependency sets, declared apart because they are needed apart. The gate is
`python3 -m pip install -r requirements-check.txt`, and `make check` runs from
there; the drivers below want `requirements-drivers.txt` on top of it.

Drivers take `--server` / `--data-dir` and record `VmHWM` (the kernel
high-water mark, which cannot miss a peak between samples) rather than sampled
RSS. None defaults `--node-options` to a heap flag: whether the server survives
on a stock heap is itself an exit criterion, so the flag under test is never
the default.

```bash
# full-library build, then serve and query it
python3 bench/run_build.py  --server fork/dist/index.js --data-dir <dir>
python3 bench/run_serve.py                       # restart, open, query
python3 bench/run_serve2.py                      # same, auto-refresh off

# JSON -> SQLite migration, isolated, with the environment recorded
node bench/migrate_measure.mjs <index.json> <out.sqlite>
node bench/slice_index.mjs <big.json> <small.json> <n-chunks>

# query both backends and compare result sets
python3 bench/query.py   --server fork/dist/index.js --data-dir <dir> --backend json
python3 bench/compare.py --a res_json.json --b res_sqlite.json

# vector benchmarks (need sqlite-vec)
node bench/vec_scaling.mjs        # is vec0 KNN sub-linear? it is not
node bench/vec_quantize.mjs       # float32 vs int8 vs binary
cd fork && npx tsx ../bench/vec_recall.ts   # recall of two-stage vs exact

# standalone FTS5 prototype, and resting memory
node bench/fts5_bench.mjs ~/data/Zotero/storage bench/data/keys.txt bench/index.sqlite
python3 bench/measure_resting.py --server fork/dist/index.js --data-dir <dir>

# probes behind specific tickets
python3 bench/fulltext_sequence.py --output <f.json>          # 0012: the two version sequences
node bench/fold_sweep.mjs --output <f.json>                   # 0009: JS fold vs what FTS5 indexes
node bench/index_concentration.mjs --db <index.sqlite> --output <f.json>   # 0013: concentration and ranking
node bench/bm25_idf_effect.mjs                                # 0013, superseded by the above
bash bench/results/json-baseline/rung.sh <label> <items> <chars>   # the JSON memory ladder
```

Three of these read the LIVE Zotero local API or a real index rather than a
fixture, so their output is a record of one library at one moment; each writes
its own provenance into its artifact. `fold_sweep.mjs` is the exception and is
fully deterministic — it builds its own in-memory FTS5 table.

`bench/run_serve.py` and `run_serve2.py` still carry hardcoded paths from the
run that produced `bench/results/0003-full-build/`; they need editing before
reuse elsewhere. `rung.sh` used to be in that category and no longer is: every
path it uses is overridable and defaults into the committed tree.
