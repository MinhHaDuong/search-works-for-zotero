# The specification chain

This is the entry point to the chain, and it owns one thing the other
documents do not: **where each of the twenty-three promises actually
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
[FIELD-REVIEW.md](FIELD-REVIEW.md), the survey of prior art. What each document
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

`●●●●●●●●●●●●●●●●●●●●●●●` &nbsp; 23 ratified · 0 still open

**Delivered** — the promise holds on stock upstream today.

`●◐◐◐◐◐◐◐◐◐◐◐◐◐◐◐○○○○○○○` &nbsp; 1 shipped · 15 partial · 7 not yet

`●` shipped &nbsp;·&nbsp; `◐` partial &nbsp;·&nbsp; `○` not yet

**How each verdict was established**, since a verdict is only worth its
evidence:

10 measured · 8 read in the source · 5 inferred

**The requirements are objectively testable; these verdicts are not yet
tests.** Every requirement is a set of MUST clauses a harness could check, so
where a row is soft the fault is this repository's and never the sheet's. Of
the twenty-three, ten rest on an experiment or a test that ran, eight on
opening the upstream source at the reviewed baseline, and five on nothing
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
| Change and cost | `●` | `◐` |
| Corpus | `●●` | `◐○` |
| Query | `●●●●●●` | `◐◐◐◐○○` |
| Multilingual | `●●` | `◐○` |
| Embedding configurations | `●` | `○` |
| Custody and lifecycle | `●●●●` | `●◐◐○` |
| Multi-library and multi-process | `●●` | `◐○` |
| Normalization | `●` | `◐` |

---

## Goal 1 — the README's opening promise, made strong

Goal 1 is not the first thing to be done and says nothing about what is: the
number names the bundle, it does not rank it. What the bundle is, is a
**conjunction**. Its subject is the search half of the opening line of the
upstream README — *find anything in your own work*: hybrid keyword and semantic
search across the library, and, with full-text indexing turned on, the body of
every PDF as well. The same line goes on to promise the matching passage with
its page number, and that clause is deliberately not goal 1's, so the subject
here is the line minus its locator. What remains is already published upstream,
so nothing about it has to be argued before it can be tested; and it is kept
only when every one of the eleven rows below holds at once. Any single one of
them failing falsifies it, whatever the other ten do.

That is the whole reason to name the bundle. Eleven separate rows can be
reported as ten-elevenths done, and a promise cannot.

**Made strong** is four strengthenings, and each was already a promise here:
every document, including the monsters, at a library size worth the name; every
language on the default path, whose keyword half can only match if the two
normalizers agree; everything searchable **today** rather than eventually —
records first, body text behind them, on ordinary hardware — with one's own
notes in the corpus at all and the whole of it legible, per stage, in one
sentence; and an answer back inside the budget the query path is held to.
Searchable at an older extraction, chunking or embedder version still counts;
indexed by its opening pages does not. The bundle and its exclusions were ruled
on 2026-08-31 ([DECISIONS.md](DECISIONS.md)).

`◐◐◐◐◐◐◐◐◐○○` &nbsp; 11 in the bundle · 6 rest on something that ran

That bar shows where the terms stand. It is not a progress bar: under the
conjunction the goal is kept at all-shipped and at no state before it.

**Read as test-driven development, this bundle has no failing tests. It has
eleven unwritten ones.** The `evidence` column is the test column: `measured`
says an assertion ran, `code` and `inferred` say none exists. A row in those two states
is not red — red is a claim about the system, and an unwritten test is a claim
about nobody — which is why the six that rest on something that ran are counted
separately above, and why not one of the eleven is yet a check that runs on
every build.

So what goal 1 asks for is not upstream code. It is eleven assertions, each
carrying the way it can fail. Most go red on the reviewed baseline the day they
are written, for the reasons their rows already give. Two or three arrive green
— R6's property holds already, and the fold sweep passes — and a test never seen
to fail is a test nobody has checked, which is why ticket 0026's fold gate keeps
a red classification for a tree that lacks the fold. Green on arrival is a
result. Green with no way to be red is a decoration.

**Terms.** What the user meets. Each row gives the clause goal 1 binds, where it
is decided, and the address where its assertion would live; the status is not
repeated here, and the bar above is recomputed from these requirements' own rows
further down.

*Decided at* is the two levels and the relation between them. `fixture` is the
committable corpus, which runs wherever the gate runs; `library` is the author's
real library or a disclosed machine, which cannot be committed; `both` is a
fixture assertion standing in for something real, whose fidelity the library
level has to re-earn — the pattern the RSS gate's revalidation clause follows.
The assignment is a reading, and a vetoable one: it says where each assertion
can be *decided*, not where it happens to have run.

| | the clause goal 1 binds | decided at | where its test would live |
|---|---|---|---|
| R1 | the whole library is covered unattended and newest-first, a text-less attachment ending covered with its reason | fixture | ticket 0026 |
| R6 | the query path waits for no freshness work | fixture | ticket 0026 |
| R7 | the default path serves French, German, Vietnamese, Greek and Russian, unconfigured | fixture | ticket 0029 |
| R8 | the design-point library is answered, and a monster is indexed whole | both | ticket 0029 |
| R12 | a subscribed group library is searchable, and indexing one library never erases another | both | ticket 0016 |
| R16 | my own notes and annotations are in the corpus at all | library | ticket 0022 |
| R17 | how much is searchable, per stage, in one sentence, naming the device serving | fixture | ticket 0026 |
| R19 | every token the query normalizer makes, the index normalizer can make too | fixture | ticket 0026 |
| R32 | records searchable today and the body behind them, on the reference machine | both | ticket 0026 |
| R33 | the exact string, the paraphrase, and the document both signals agree on | fixture | ticket 0029 |
| R34 | every pinned answer comes back within the first ten results | fixture | ticket 0029 |

R19 is a term by its property clause alone. Its cadence — that the sweep runs
on every check — is not a promise to anyone and left the sheet on 2026-08-31,
with R20, R21 and R26, on the same criterion: what verifies a promise is not
itself a promise, so it belongs to the gates in DESIGN.md §2.8. R30 left too,
dissolved into R32 and R17.

None of those addresses is new work. The fixture corpus, the gates and the
acceptance harness offered upstream were scoped before this goal existed; goal 1
names which of their assertions this one promise hangs on, and the tally above
keeps the count. Membership is a ruling, not a page edit:
[`bench/check_progress.py`](../bench/check_progress.py) reads the roster from
[DECISIONS.md](DECISIONS.md) and fails the build when the page and the ledger
disagree, because a bundle that can quietly lose a member is a milestone that
reports itself kept when it is not.

---

## The twenty-three

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
| R1 | eventually the whole library is indexed | ratified | partial | code | Incremental update, build resume and the coverage-gap catch-up all landed upstream. That convergence actually reaches every item, unattended, is unmeasured: the harness that would watch it is ticket 0026. Two clauses arrived by merge on 2026-08-31 and neither holds — the crawl pages the library rather than working a priority order, and an attachment yielding no text is not recorded as done-with-a-reason, so it is re-examined and counted as missing (ticket 0019). |
| R4 | something partial is better than nothing | ratified | partial | code | A capped or interrupted build answers queries and says it was capped. What it does not yet do is report coverage per stage, which is what makes a partial index distinguishable from a complete one. |
| R17 | coverage in one sentence | ratified | partial | code | Build status carries counters, not the sentence: N of M items, per stage, with the most-recent-covered date. Ticket 0120, ticket 0140. Two clauses merged in on 2026-08-31 and neither holds either: per-stage counters naming the input that triggered each unit of work do not exist upstream (scoped issue A, ticket 0033), and the local path passes no execution device, so nothing names the one actually serving (`verification/DEVICE-AUTO-0264.md`). |
| R32 | the build finishes today | ratified | partial | measured | The timing half holds and the contract half does not exist. In the runtime zoteus ships, on a laptop CPU, the incumbent model reaches an overnight build of a design-point library, and so do the two small multilingual candidates R7 will choose between, while the base-sized ones do not (`bench/results/0025-x1-recall/embed-feasibility.json`, sampled and projected; the CPU cells ticket 0481 recovered from `bench/results/0264-gpu-arm/`; genuine GPU figures in `bench/results/0482-gpu-corrected/`). What is absent upstream is the whole contract: no reference machine, no bound of either kind, and no record-first phase order for the record bound to be measured against — the crawl pages the library rather than working a priority order, which is R1's newest-first clause going unmet. Bounds are pinned in the change that first asserts them, and the constraint this puts on which embedder may be the default lands in ticket 0495, the ticket that decides what ships. |

### Change and cost

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R3 | avoid unnecessary rebuild | ratified | partial | code | Updates ride a version watermark, so a resync no longer rebuilds the library. Invalidation is still per item, not per item and stage. The counter-churn clause merged in on 2026-08-31 is the better-off half: the full-text sequence is read as its own cursor, which removes the known cause, and nothing yet proves the absence because the counters that would prove it are R17's. |

### Corpus

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R8 | size does not disqualify | ratified | partial | code | The item cap is configurable and says when it truncates, and the two-stage vector search retired the full-scan red zone; the default cap still sits below the design point. The monster clause merged in on 2026-08-31 fails outright: full text is capped per item by default, so a monster is indexed by its opening pages, which is the one place a default contradicts a promise. Ticket 0024 carries the filing. |
| R16 | my own words | ratified | none | code | Verified nil at v1.10.0: every crawl asks for top-level items, and neither a child note nor an annotation is one, so `zotero_annotate` writes what search can never find. Filed upstream as issue #33 with a working prototype; ticket 0022. |

### Query

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R5 | filters are good to have | ratified | partial | measured | Scoping exists, but experiment X4 measured the constrained path and it lost to ranking everything, superlinearly. Confirmed on the real corpus, where scoping costs more than ranking the whole library: ticket 0025. The design answer is settled and negative: no constrained step ships, and the ladder ends at R18's honest refusal. |
| R6 | a sufficient reply in 3 s beats the optimum in 3 min | ratified | partial | measured | The query path does no freshness work, and the two-stage search brought the scan well inside the budget. Nothing gates it, so the property is true and unwatched. |
| R18 | an empty result says which | ratified | none | inferred | An empty answer does not yet distinguish "nothing matches" from "this scope is not indexed yet". The decision it waited on is now made and negative — experiment X4 ran and no constrained step ships, so the `scope{}` block stops being the last resort and becomes the answer whenever a narrow scope outruns the deeper refetch. The ladder edit that follows is awaiting ratification in DECISIONS.md; ticket 0025. |
| R24 | a citeable page in one step, and one entry per hit | ratified | partial | code | Local extraction now yields real page ranges and a document's own outline. The primary locator is meant to be the entry heading, which waits on the segmenter: ticket 0028, gated by experiment X5. The dedup clause merged in on 2026-08-31 waits on the same thing — deduplication is per item, not per section, because sections do not exist yet. |
| R33 | lexical, semantic and hybrid each work | ratified | partial | measured | Three of the four clauses have something behind them and the load-bearing one does not. Upstream serves a hybrid default, and our own measurement of it drove the two sides apart — the vector side moved while the keyword side stayed put (`verification/issue-30-thread.md`), which is evidence that both paths exist and are separately live. Nothing tests the agreement clause: no check asks whether a document both signals rank mid comes back above one that only a single signal favours, which is the defect shape `spec/FIELD-REVIEW.md` records open in a neighbouring project. The mode-served clause is unread at the reviewed baseline. Ticket 0029 carries the probes. |
| R34 | if it is in my library, I find it | ratified | none | inferred | No pinned set exists upstream and nothing asserts one, so the promise is unmeasured rather than shown unmet. The adjacent evidence is not this: ticket 0265 scored a synthetic task — relevance being other passages of the same item — on a subsample of the real corpus, which measures retrieval strength and not whether a research question finds its answer. The corpus is ticket 0029, the gate is ticket 0026. |

### Multilingual

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R7 | multilingual by default | ratified | partial | measured | Accent folding merged, and the default embedder is local — but local is not multilingual: stock upstream hardcodes the English-tuned MiniLM construction, so R7's second MUST fails outright at the reviewed baseline, read in the source rather than measured. The English stopword list is still in place: experiment X2 measured its deletion and the deletion failed, so a library-derived droplist became a precondition rather than a follow-up. Ticket 0240 measured the replacement field and closed with a recommendation that sets no default; ticket 0495 decides what ships. Ticket 0090, ticket 0091. |
| R29 | the query language is not the document language | ratified | none | measured | Stock upstream embeds with the incumbent English MiniLM chain, which `verification/SMOKE-1.10.0.md` names as observed on a running server, so no cross-lingual channel exists at the reviewed baseline. That a multilingual embedder supplies one is measured rather than assumed: ticket 0266 ran EN and FR queries against Vietnamese, German and Russian content at every deployed dtype (`bench/results/0266-cross-lingual/SUMMARY.json`), and its negative control clears at every dtype for only two candidates of the six. The promise is a gate criterion for whichever entry the registry ships: ticket 0037, ticket 0495. |

### Embedding configurations

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R31 | a configuration offered to me works here | ratified | none | inferred | Stock upstream hardcodes the local MiniLM construction and has no complete entry-level validation, so nothing validates before an index is created or queried and nothing fails explicitly. The invariant-first implementation is ticket 0488. |

### Custody and lifecycle

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R10 | local by default | ratified | shipped | measured | The default embedder is local, the model cache sits under the data directory, and the one API key that used to travel in a URL now travels in a header. Asserted against a running server rather than read: `bench/smoke_upstream.py` checks that effective embeddings resolve local and the embedder is active. Closed as ticket 0017. |
| R15 | deleted means gone, at both scales | ratified | partial | inferred | Deletion reconciles against the key set, so a deleted item loses its rows; that every queue and every stage lose it too is design, not yet code. The uninstall clause merged in on 2026-08-31 is measured and partial: the downloaded model no longer escapes the data directory, observed on a build that actually downloaded one, and nothing has swept for other survivors. Ticket 0017. |
| R22 | pause stays paused | ratified | none | code | Verified absent at v1.10.0: there is no pause. Scoped issue A, ticket 0033. |
| R23 | upgrade and downgrade | ratified | partial | measured | The schema stamp is read before the file is opened writable, which is the half that prevents damage, and that half now holds under test: `bench/smoke_upstream.py` restamps a copy of a real index in both directions and finds the original preserved byte-for-byte and never served. Serving in both directions is still design — an older stamp is abandoned rather than migrated, which is filed upstream as issue #34. |

### Multi-library and multi-process

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R12 | group libraries | ratified | partial | measured | Group libraries are served locally and merged into one index. The second clause fails today: a build for one library against an interrupted index appends to another's rows. Ten tests, all red on stock v1.10.0; the guard is in flight as pull request #32, ticket 0016. |
| R13 | second process | ratified | none | inferred | Two processes on one data directory are undesigned in the code and unsoaked here. Scoped issue C, ticket 0035. |

### Normalization

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R19 | the query and index normalizers agree | ratified | partial | measured | The property holds: the fold merged upstream, and the sweep passed when it ran. The cadence clause — that the sweep runs on every check — left the sheet on 2026-08-31, because what verifies a promise is not itself a promise. It is a gate in DESIGN.md §2.8, and ticket 0026 wires it. |

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
