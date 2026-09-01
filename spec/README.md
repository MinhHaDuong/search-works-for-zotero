# The specification chain

This is the entry point to the chain, and it owns one thing the other
documents do not: **where each of the twenty-four\* promises actually
stands**, designed and delivered.

It owns no threshold, no budget and no decision rule. Every number in this
repository lives in exactly one document, and a status page is the most
inviting place in a repository to leave a second copy of one. So the rows
below carry status and addresses, nothing else, and
[`bench/check_progress.py`](../bench/check_progress.py) fails the build on any
digit here that is not an address.

Read them in this order:
[REQUIREMENTS.md](REQUIREMENTS.md), [CONSTRAINTS.md](CONSTRAINTS.md),
[DESIGN.md](DESIGN.md), [DECISIONS.md](DECISIONS.md). Beside them sit
[TERMINOLOGY.md](TERMINOLOGY.md), the glossary, and
[FIELD-REVIEW.md](../verification/FIELD-REVIEW.md), the survey of prior art. What each document
owns, and how authority passes between them, is stated once in the repository's
[README](../README.md) — this page does not restate it.

Live state lives outside the chain: [`../SYNC.md`](../SYNC.md) tracks upstream,
[`../STATE.md`](../STATE.md) holds the prototype phase's measurement record, and
[`../GOVERNANCE.md`](../GOVERNANCE.md) states how this repo conducts itself
upstream. `../RUNBOOK.md` self-sunset 2026-08-30 once its measurements
executed; its durable state lives in ticket 0014, ticket 0016, ticket 0024
and ticket 0025. The work train is the tickets.

---

## Where the promises stand

Measured against upstream **v1.10.0**, the reviewed baseline in
[`../UPSTREAM`](../UPSTREAM). The implementation is not in this repository: it
is [`oscardvs/zoteus`](https://github.com/oscardvs/zoteus), so "delivered"
always means *holds on stock upstream*, never *we wrote it*.

**Designed** — the promise has a settled design behind it.

`●●●●●●●●●●●●●●●●●●●●●●●●` &nbsp; 24 ratified · 0 still open

**Delivered** — the promise holds on stock upstream today.

`●◐◐◐◐◐◐◐◐◐◐◐◐◐◐◐◐○○○○○○○` &nbsp; 1 shipped · 16 partial · 7 not yet

`●` shipped &nbsp;·&nbsp; `◐` partial &nbsp;·&nbsp; `○` not yet

**How each verdict was established**, since a verdict is only worth its
evidence:

10 measured · 8 read in the source · 6 inferred

**The requirements are objectively testable; these verdicts are not yet
tests.** Every requirement is a set of MUST clauses a harness could check, so
where a row is soft the fault is this repository's and never the sheet's. Of
the twenty-four\*, ten\* rest on an experiment or a test that ran, eight\* on
opening the upstream source at the reviewed baseline, and six\* on nothing
executed at all — merged pull requests, design documents, reasoning. The
`evidence` column says which, per row, so a reader can tell a verdict that
was checked from one that was argued.

Only the arithmetic is mechanical: every bar and every tally is recomputed
from the rows, never a row from a measurement. Closing the gap is the work
itself rather than a tracker over it: the fixture corpus in ticket 0029, the
gates in ticket 0026, which is where a check that runs now lives —
and the acceptance harness in ticket 0032. Their unit is the MUST clause rather
than the requirement, because a compound requirement graded as one token is
what made `partial` ambiguous before the evidence column split it.

One instrument already moves rows: [`../bench/smoke_upstream.py`](../bench/smoke_upstream.py)
drives the reviewed baseline over MCP against a real Zotero library, and each of
its checks names the clause it exercises and what would falsify it. It is not a
requirements suite and does not pretend to be — a check exercises one clause of
one requirement, once, against one library, which is exactly what separates
`measured` from `code` and nothing more. Its run is
[`../bench/results/smoke-1.10.0/checks.json`](../bench/results/smoke-1.10.0/checks.json)
and the session it grew out of is
[`../verification/SMOKE-1.10.0.md`](../verification/SMOKE-1.10.0.md). Where a
check cannot decide, it says `observed` and the row keeps its weaker word.

Nothing recomputes a status when upstream ships, so the page is invalidated
instead: the moment the reviewed baseline in [`../UPSTREAM`](../UPSTREAM)
names a release this page does not, `make check` fails and stays failing
until each row has been read again. A judgement is not allowed to outlive
the release it was made about.

The two bars disagree on purpose, and the gap between them is the shape of
the project rather than a backlog. What this repository produces is a
specification, a measurement harness, and a small number of contained
patches; the machinery itself is built upstream. A single bar would average
those two facts into one number describing neither. What has actually gone
upstream, and on what terms, is [`../SYNC.md`](../SYNC.md) and
[`../GOVERNANCE.md`](../GOVERNANCE.md).

| section | designed | delivered |
|---|---|---|---|
| Coverage and convergence | `●●●●` | `◐◐◐◐` |
| Change and cost | `●●` | `◐◐` |
| Corpus | `●●` | `◐○` |
| Query | `●●●●●●` | `◐◐◐◐○○` |
| Multilingual | `●●` | `◐○` |
| Embedding configurations | `●` | `○` |
| Custody and lifecycle | `●●●●` | `●◐◐○` |
| Multi-library and multi-process | `●●` | `◐○` |
| Normalization | `●` | `◐` |

---

## The goals ladder

Five goals, numbered in the order the work is done. The number is the build
order and nothing else: goal 1 is what to make true first, not what matters
most. Every requirement the sheet declares sits on exactly one rung, the rungs
run from the cheapest to assert to the most expensive to earn, and
[`bench/check_progress.py`](../bench/check_progress.py) fails the build when a
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

Nothing leaves this machine unasked, one obvious switch stops the work, deleting
the data directory is the whole uninstall, and a configuration proves it runs
here before it is used. Lowest rung because its assertions need no corpus, no
build and no library: they are decidable the moment the system is installed.

`●◐○○` &nbsp; 4 in the bundle · 1 rest on something that ran

| | the clause goal 1 binds | decided at | where its test would live |
|---|---|---|---|
| R10 | my library text and my queries stay on this machine without an opt-in | both | [`../bench/smoke_upstream.py`](../bench/smoke_upstream.py) |
| R15 | deleting the data directory is the whole uninstall | both | ticket 0017 |
| R22 | one obvious way to stop all background work, holding across restarts | both | ticket 0033 |
| R31 | a configuration offered to me proves it works on my machine, or fails loudly there | both | ticket 0488 |

## Goal 2 — it does not lose or corrupt what it built

The cost of staying current is what changed, two server processes on one data
directory do not corrupt or duplicate, and an index under another schema version
ends up served. Second because these need a built index but not a good one, and
because a build that cannot survive its own second day never reaches the rungs
above.

`◐◐○` &nbsp; 3 in the bundle · 1 rest on something that ran

| | the clause goal 2 binds | decided at | where its test would live |
|---|---|---|---|
| R3 | what staying current costs is what changed, never the size of the library | both | ticket 0026 |
| R13 | two server processes on one data directory, no corruption and no duplicated work | both | ticket 0035 |
| R23 | an index under another schema version ends up serving, either direction, no file deleted by hand | both | ticket 0026 |

## Goal 3 — it answers, and it is honest about what it has

Coverage converges unattended and the build finishes inside its bounds, the
index answers while it is still filling, the query path waits for no freshness
work, the two normalizers agree, and it says how much is behind an answer and
which emptiness an empty one is.

`◐◐◐◐◐◐○` &nbsp; 7 in the bundle · 3 rest on something that ran

| | the clause goal 3 binds | decided at | where its test would live |
|---|---|---|---|
| R1 | the whole library is covered unattended and newest-first, a text-less attachment ending covered with its reason, coverage returning the same way after a schema-version flip, and superseded work draining to the latest chain unattended | both | ticket 0026 |
| R4 | the index answers while it is still filling, its first build included | both | ticket 0026 |
| R6 | the query path waits for no freshness work | both | ticket 0026 |
| R17 | how much is searchable, per stage, in one sentence, naming the device serving | both | ticket 0026 |
| R18 | an empty answer says which it is: nothing matched, or this scope is not indexed yet | both | ticket 0026 |
| R19 | every token the query normalizer makes, the index normalizer can make too | both | ticket 0026 |
| R32 | records searchable today and the body behind them, on the reference machine | both | ticket 0026 |

## Goal 4 — it finds the right thing, in my languages, and I can open it

All three modes, the pinned answer inside the first ten, scoping enforced before
truncation, three languages served unconfigured with the lanes connected, and a
hit that opens at the page it came from. Which pinned queries this rung binds is
faceted by the corpus each answer needs; the rule is DESIGN.md §2.8's
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

`◐◐◐○` &nbsp; 4 in the bundle · 1 rest on something that ran

| | the clause goal 5 binds | decided at | where its test would live |
|---|---|---|---|
| R8 | a 15k library is answered, and a 15k-page PDF is indexed whole | both | ticket 0029 |
| R12 | a subscribed group library is searchable, and indexing one library never erases another | both | ticket 0016 |
| R16 | my own notes and annotations are in the corpus at all | library | ticket 0022 |
| R35 | a new, changed or deleted item is noticed without anyone asking | both | ticket 0503 |

## What the ladder does not say

Three terms bind a clause rather than an item. R19 is in by its property alone:
its cadence — that the sweep runs on every check — is not a promise to anyone
and left the sheet on 2026-08-31, on the criterion that what verifies a promise
is not itself a promise, so it belongs to the gates in DESIGN.md §2.8. R24 is in
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

## The twenty-four

`designed` is `ratified` or `open`; `delivered` is `shipped`, `partial` or
`none`; `evidence` is `measured` (something ran), `code` (the source was
opened at the reviewed baseline) or `inferred` (neither). The standing column
cites the ticket, pull request or issue that carries the remainder — never a
threshold, which belongs to DESIGN.md.

Read `delivered` and `evidence` together. `partial` with `inferred` is a
guess about a half-kept promise; `none` with `measured` is a failure someone
demonstrated. They are not the same kind of statement.

### Coverage and convergence

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R1 | Every item in the search perimeter MUST become searchable without anyone asking for it, and the system MUST NOT need a manual rebuild, whatever state it is in | ratified | partial | code | Incremental update, build resume and the coverage-gap catch-up all landed upstream. That convergence actually reaches every item, unattended, is unmeasured: the harness that would watch it is ticket 0026. Two clauses arrived by merge on 2026-08-31 and neither holds — the crawl pages the library rather than working a priority order, and an attachment yielding no text is not recorded as done-with-a-reason, so it is re-examined and counted as missing (ticket 0019). The convergence-to-latest-chain clause of 2026-09-01 postdates the reviewed baseline and is unassessed here. |
| R4 | The index MUST answer queries at every moment of its life, including during its first build | ratified | partial | code | A capped or interrupted build answers queries and says it was capped. What it does not yet do is report coverage per stage, which is what makes a partial index distinguishable from a complete one. |
| R17 | "How much of my library is searchable?" MUST get a human answer, per stage, with a date | ratified | partial | code | Build status carries counters, not the sentence: N of M items, per stage, with the most-recent-covered date. Ticket 0120, ticket 0140. Two clauses merged in on 2026-08-31 and neither holds either: per-stage counters naming the input that triggered each unit of work do not exist upstream (scoped issue A, ticket 0033), and the local path passes no execution device, so nothing names the one actually serving (`verification/DEVICE-AUTO-0264.md`). |
| R32 | On a laptop-class machine with no GPU, a full build with the default configuration MUST index at 150 ms per passage or better, which for a 15k library means records searchable within one hour and body text within a day. It SHOULD reach 75 ms per passage, which halves both figures | ratified | partial | measured | The timing half holds and the contract half does not exist. In the runtime zoteus ships, on a laptop CPU, the incumbent model reaches an overnight build of a design-point library, and so do the two small multilingual candidates R7 will choose between, while the base-sized ones do not (`bench/results/0025-x1-recall/embed-feasibility.json`, sampled and projected; the CPU cells ticket 0481 recovered from `bench/results/0264-gpu-arm/`; genuine GPU figures in `bench/results/0482-gpu-corrected/`). What is absent upstream is the whole contract: no reference machine, no bound of either kind, and no record-first phase order for the record bound to be measured against — the crawl pages the library rather than working a priority order, which is R1's newest-first clause going unmet. The bound is now pinned and it is a rate — per passage, over the whole pipeline, on a disclosed laptop-class machine (DESIGN.md §2.8), with the wall-clock promise derived from it through the measured census. Only the embed term of that rate rests on measurement; extract and chunk are an allocation until ticket 0500 measures them. A time bound with no machine attached is not a bound, and a wall-clock one alone silently fixes the library size; this row was unfalsifiable without both halves. The constraint that puts on which embedder may be the default lands in ticket 0495, the ticket that decides what ships. |

### Change and cost

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R3 | The cost of staying current MUST be proportional to what changed, never to the size of the library | ratified | partial | code | Updates ride a version watermark, so a resync no longer rebuilds the library. Invalidation is still per item, not per item and stage. The counter-churn clause merged in on 2026-08-31 is the better-off half: the full-text sequence is read as its own cursor, which removes the known cause, and nothing yet proves the absence because the counters that would prove it are R17's. |
| R35 | The system MUST notice a new, changed or deleted item within one minute, without anyone asking | ratified | partial | inferred | The machinery to notice a change exists upstream: incremental updates ride a library version cursor (SYNC.md records the commit that added them), and deletion reconciles against the key set. What does not exist is the minute. Nothing here has established how often the update path runs, and no latency has been measured or read at source, which is why this row is `inferred` where R3's neighbouring row is `code`. Ticket 0503 settles it. On our side the reconcile tick's cadence is what delivers the minute, and deletion subtraction moved from every tenth tick to every tick to meet it (DESIGN.md §2.4). |

### Corpus

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R8 | A 15k library and a 15k-page PDF MUST both be ordinary input | ratified | partial | code | The item cap is configurable and says when it truncates, and the two-stage vector search retired the full-scan red zone; the default cap still sits below the design point. The long-document clause merged in on 2026-08-31 fails outright: full text is capped per item by default, so a 15 000-page PDF is indexed by its opening pages, which is the one place a default contradicts a promise. Ticket 0024 carries the filing. |
| R16 | My own notes and annotations MUST be searchable, not only the papers I collected | ratified | none | code | Verified nil at v1.10.0: every crawl asks for top-level items, and neither a child note nor an annotation is one, so `zotero_annotate` writes what search can never find. Filed upstream as issue #33 with a working prototype; ticket 0022. |

### Query

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R5 | Scoping a search by collection, tag, item type or date MUST be enforced before any answer is truncated | ratified | partial | measured | Scoping exists, but experiment X4 measured the constrained path and it lost to ranking everything, superlinearly. Confirmed on the real corpus, where scoping costs more than ranking the whole library: ticket 0025. The design answer is settled and negative: no constrained step ships, and the ladder ends at R18's honest refusal. |
| R6 | A warm query MUST answer within 3 seconds and SHOULD answer inside 700 ms, and MUST never wait on freshness work bigger than a single request | ratified | partial | measured | The query path does no freshness work, and the two-stage search brought the scan well inside the budget. Nothing gates it, so the property is true and unwatched. |
| R18 | An empty answer MUST say whether nothing matched or the scope is not indexed yet | ratified | none | inferred | An empty answer does not yet distinguish "nothing matches" from "this scope is not indexed yet". The decision it waited on is now made and negative — experiment X4 ran and no constrained step ships, so the `scope{}` block stops being the last resort and becomes the answer whenever a narrow scope outruns the deeper refetch. The ladder edit that follows is awaiting ratification in DECISIONS.md; ticket 0025. |
| R24 | A hit MUST lead to the page it came from, and one entry MUST give one hit | ratified | partial | code | Local extraction now yields real page ranges and a document's own outline. The primary locator is meant to be the entry heading, which waits on the segmenter: ticket 0028, gated by experiment X5. The dedup clause merged in on 2026-08-31 waits on the same thing — deduplication is per item, not per section, because sections do not exist yet. |
| R33 | Exact-word search, meaning-based search, and the two combined MUST each work | ratified | partial | measured | Three of the four clauses have something behind them and the load-bearing one does not. Upstream serves a hybrid default, and our own measurement of it drove the two sides apart — the vector side moved while the keyword side stayed put (`verification/issue-30-thread.md`), which is evidence that both paths exist and are separately live. Nothing tests the agreement clause: no check asks whether a document both signals rank mid comes back above one that only a single signal favours, which is the defect shape `spec/FIELD-REVIEW.md` records open in a neighbouring project. The mode-served clause is unread at the reviewed baseline. Ticket 0029 carries the probes. |
| R34 | For every query of the pinned set, the answer MUST come back within the first ten results | ratified | none | inferred | No pinned set exists upstream and nothing asserts one, so the promise is unmeasured rather than shown unmet. The adjacent evidence is not this: ticket 0265 scored a synthetic task — relevance being other passages of the same item — on a subsample of the real corpus, which measures retrieval strength and not whether a research question finds its answer. The corpus is ticket 0029, the gate is ticket 0026. |

### Multilingual

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R7 | The default path MUST work in English, French and Vietnamese with no configuration, and SHOULD work in Arabic, Chinese, German, Hindi, Russian and Spanish | ratified | partial | measured | Accent folding merged, and the default embedder is local — but local is not multilingual: stock upstream hardcodes the English-tuned MiniLM construction, so the MUST tier fails at English alone and the SHOULD tier is not reachable at all, read in the source rather than measured. The English stopword list is still in place: experiment X2 measured its deletion and the deletion failed, so a library-derived droplist became a precondition rather than a follow-up. The two tiers were ruled on 2026-08-31 and do not move the verdict; every candidate the study measured declares both tiers, so the filter's field is unchanged. Ticket 0240 measured the replacement field and closed with a recommendation that sets no default; ticket 0495 decides what ships. Ticket 0090, ticket 0091. |
| R29 | A query in English or French MUST retrieve relevant Vietnamese content without the user translating anything | ratified | none | measured | Stock upstream embeds with the incumbent English MiniLM chain, which `verification/SMOKE-1.10.0.md` names as observed on a running server, so no cross-lingual channel exists at the reviewed baseline. That a multilingual embedder supplies one is measured rather than assumed: ticket 0266 ran EN and FR queries against Vietnamese, German and Russian content at every deployed dtype (`bench/results/0266-cross-lingual/SUMMARY.json`), and its negative control clears at every dtype for only two candidates of the six. The promise is a gate criterion for whichever entry the registry ships: ticket 0037, ticket 0495. |

### Embedding configurations

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R31 | A search configuration offered to me MUST prove it works on my machine before it is used, or fail loudly there | ratified | none | inferred | Stock upstream hardcodes the local MiniLM construction and has no complete entry-level validation, so nothing validates before an index is created or queried and nothing fails explicitly. The invariant-first implementation is ticket 0488. |

### Custody and lifecycle

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R10 | Without an explicit opt-in, my library text and my queries MUST NOT leave this machine | ratified | shipped | measured | The default embedder is local, the model cache sits under the data directory, and the one API key that used to travel in a URL now travels in a header. Asserted against a running server rather than read: `bench/smoke_upstream.py` checks that effective embeddings resolve local and the embedder is active. Closed as ticket 0017. |
| R15 | Deleting an item MUST remove its text everywhere, and deleting the data directory MUST be the whole uninstall | ratified | partial | inferred | Deletion reconciles against the key set, so a deleted item loses its rows; that every queue and every stage lose it too is design, not yet code. The uninstall clause merged in on 2026-08-31 is measured and partial: the downloaded model no longer escapes the data directory, observed on a build that actually downloaded one, and nothing has swept for other survivors. Ticket 0017. |
| R22 | There MUST be one obvious way to stop all background work, and it MUST hold across restarts | ratified | none | code | Verified absent at v1.10.0: there is no pause. Scoped issue A, ticket 0033. |
| R23 | An index written under a different schema version MUST end up serving, in either direction, without anyone deleting files by hand | ratified | partial | measured | The schema stamp is read before the file is opened writable, which is the half that prevents damage, and that half now holds under test: `bench/smoke_upstream.py` restamps a copy of a real index in both directions and finds the original preserved byte-for-byte and never served. Serving in both directions is still design — an older stamp is abandoned rather than migrated, which is filed upstream as issue #34. |

### Multi-library and multi-process

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R12 | Group libraries MUST be searchable exactly like my own, and indexing one library MUST NOT erase another | ratified | partial | measured | Group libraries are served locally and merged into one index. The second clause fails today: a build for one library against an interrupted index appends to another's rows. Ten tests, all red on stock v1.10.0; the guard is in flight as pull request #32, ticket 0016. |
| R13 | Two server processes on one data directory MUST both answer queries without corrupting the index or doing the same work twice | ratified | none | inferred | Two processes on one data directory are undesigned in the code and unsoaked here. Scoped issue C, ticket 0035. |

### Normalization

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R19 | Every token the query side produces MUST be one the index side can also produce | ratified | partial | measured | The property holds: the fold merged upstream, and the sweep passed when it ran. The cadence clause — that the sweep runs on every check — left the sheet on 2026-08-31, because what verifies a promise is not itself a promise. It is a gate in DESIGN.md §2.8, and ticket 0026 wires it. |

---

## How this page stays true

Three failures would make it worse than nothing, and each has a guard in
[`bench/check_progress.py`](../bench/check_progress.py), run by `make check`:

- **A promise with no standing.** A requirement added to the sheet and never
  given a row here would leave the page quietly incomplete. The guard reads
  the sheet, not this file, and fails on any requirement missing, duplicated,
  invented, or filed under the wrong section.
- **A bar that stopped matching its table.** The bars are recomputed from the
  rows and compared against what is written above, so a status can never be
  edited in one place alone.
- **A second copy of a number.** Every digit here must be an address — a
  requirement, a ticket, an upstream item, a version. A threshold or a
  measurement restated here is a finding, on the same rule TERMINOLOGY.md
  lives under.

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
