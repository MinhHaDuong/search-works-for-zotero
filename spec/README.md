# The specification chain

This is the entry point to the chain, and it owns one thing the other
documents do not: **where each of the thirty-two promises actually
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

`●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●○○` &nbsp; 30 ratified · 2 still open

**Delivered** — the promise holds on stock upstream today.

`●◐◐◐◐◐◐◐◐◐◐◐◐◐◐◐◐○○○○○○○○○○○○○○○` &nbsp; 1 shipped · 16 partial · 15 not yet

`●` shipped &nbsp;·&nbsp; `◐` partial &nbsp;·&nbsp; `○` not yet

**How each verdict was established**, since a verdict is only worth its
evidence:

12 measured · 11 read in the source · 9 inferred

**The requirements are objectively testable; these verdicts are not yet
tests.** Every requirement is a set of MUST clauses a harness could check, so
where a row is soft the fault is this repository's and never the sheet's. Of
the thirty-two, twelve rest on an experiment or a test that ran, eleven on
opening the upstream source at the reviewed baseline, and nine on nothing
executed at all — merged pull requests, design documents, reasoning. The
`evidence` column says which, per row, so a reader can tell a verdict that
was checked from one that was argued.

Only the arithmetic is mechanical: every bar and every tally is recomputed
from the rows, never a row from a measurement. Closing the gap is tracked in
ticket 0400, whose unit is the MUST clause rather than the requirement, and
whose first children already exist: the fixture corpus in ticket 0029 and the
gates in ticket 0026, two of which — R19 and R20 — demand a check that runs.

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
|---|---|---|
| Coverage and convergence | `●●●●●●○○` | `◐◐◐◐○○○○` |
| Change and cost | `●●●` | `◐◐○` |
| Corpus | `●●●` | `◐○○` |
| Query | `●●●●●` | `◐◐◐○○` |
| Multilingual | `●●` | `◐○` |
| Embedding configurations | `●` | `○` |
| Custody and lifecycle | `●●●●●` | `●◐◐◐○` |
| Multi-library and multi-process | `●●` | `◐○` |
| Operator gates | `●●●` | `◐○○` |

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
only when every one of the eleven rows below holds at once. Any single one of them failing falsifies it, whatever the
other ten do.

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

`◐◐◐◐◐◐◐○○` &nbsp; 9 in the bundle · 4 rest on something that ran

That bar shows where the terms stand. It is not a progress bar: under the
conjunction the goal is kept at all-shipped and at no state before it.

**Read as test-driven development, this bundle has no failing tests. It has nine
unwritten ones.** The `evidence` column is the test column: `measured` says an
assertion ran, `code` and `inferred` say none exists. A row in those two states
is not red — red is a claim about the system, and an unwritten test is a claim
about nobody — which is why the four that rest on something that ran are counted
separately above, and why not one of the nine is yet a check that runs on every
build.

So what goal 1 asks for is not upstream code. It is nine assertions, each
carrying the way it can fail. Most go red on the reviewed baseline the day they
are written, for the reasons their rows already give. Two or three arrive green
— R6's property holds already, and the fold sweep passes — and a test never seen
to fail is a test nobody has checked, which is why ticket 0026's fold gate keeps
a red classification for a tree that lacks the fold. Green on arrival is a
result. Green with no way to be red is a decoration.

**Terms.** What the user meets. Each row gives the clause goal 1 binds and the
address where its assertion would live; the status is not repeated here, and the
bar above is recomputed from these requirements' own rows further down.

| | the clause goal 1 binds | where its test would live |
|---|---|---|
| R1 | the whole library is covered unattended, a text-less attachment ending covered with its reason (R14, folded in) | ticket 0026 |
| R6 | the query path waits for no freshness work | ticket 0026 |
| R7 | the default path serves French, German, Vietnamese, Greek and Russian, unconfigured | ticket 0029 |
| R8 | the design-point library is answered, not approached | ticket 0025 |
| R9 | a monster is indexed whole, never by its opening pages | ticket 0029 |
| R16 | my own notes and annotations are in the corpus at all | ticket 0022 |
| R17 | how much is searchable, answered per stage in one sentence | ticket 0026 |
| R19 | every token the query normalizer makes, the index normalizer can make too | ticket 0026 |
| R32 | records searchable today and the body behind them, on the reference machine | ticket 0026 |

**Instruments.** Not terms, and not lesser: these decide whether the terms hold,
and a term whose instrument is missing cannot be settled at all. They are named
here rather than counted in the bar, because a promise the user meets is not
made truer or falser by what this repository runs in its own build.

| | what it decides | where it is built |
|---|---|---|
| R19 | the sweep runs on every check — the cadence clause, deciding R19's own property and R7's keyword half | ticket 0026 |
| R26 | convergence is watched from an empty index rather than trusted — deciding R1 | ticket 0026 |

Binding is per clause, which is why R19 is in both tables: goal 1 binds its
property, and its cadence is what decides that property. R21 joins the
instruments when the recall term exists, and R30 is no longer here at all —
finishing today turned out to be a property of the configuration rather than of
the hardware, so it left R30 and became R32.

None of those addresses is new work. The fixture corpus, the gates and the
acceptance harness offered upstream were scoped before this goal existed; goal 1
names which of their assertions this one promise hangs on, and ticket 0400 keeps
the count. Membership is a ruling, not a page edit:
[`bench/check_progress.py`](../bench/check_progress.py) reads both rosters from
[DECISIONS.md](DECISIONS.md) and fails the build when the page and the ledger
disagree, because a bundle that can quietly lose a member is a milestone that
reports itself kept when it is not.

---

## The thirty-two

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
| R1 | eventually the whole library is indexed | ratified | partial | code | Incremental update, build resume and the coverage-gap catch-up all landed upstream. That convergence actually reaches every item, unattended, is unmeasured: the harness that would watch it is ticket 0026. |
| R2 | most recent first | open | none | code | The crawl pages the library; it does not work a priority order. The requirement's own wording is under revision in ticket 0080, which also reworks the frontier that justified it. |
| R4 | something partial is better than nothing | ratified | partial | code | A capped or interrupted build answers queries and says it was capped. What it does not yet do is report coverage per stage, which is what makes a partial index distinguishable from a complete one. |
| R14 | no text is a terminal state | ratified | none | inferred | An attachment that yields no text is not recorded as done-with-a-reason, so it is re-examined and counted as missing. Held in reserve as ticket 0019. |
| R17 | coverage in one sentence | ratified | partial | code | Build status carries counters, not the sentence: N of M items, per stage, with the most-recent-covered date. Ticket 0120, ticket 0140. |
| R26 | convergence is watched, not trusted | ratified | none | inferred | No harness polls an empty index to completion. Ticket 0026, and the requirement's prefix clause is being rewritten in ticket 0080. |
| R30 | capable hardware is used | open | none | measured | The local path still passes no execution device on stock upstream, so the runtime's CPU default still serves there — unchanged from the reviewed baseline. The device mechanism is observed rather than read from source (`verification/DEVICE-AUTO-0264.md`), and ticket 0264's throughput anomaly is explained as a harness defect rather than a GPU fact (`verification/GPU-ANOMALY-0481.md`: the fidelity cells never received a device and ran on CPU). The design stays open on the per-model shape of the guarded fallback — the mixed-provider path crashes per model, not per machine — and on the per-device optimal rung, since the quantized matmul has no CUDA kernel. Time to coverage left this row on 2026-08-31 and is R32's. |
| R32 | the build finishes today | ratified | partial | measured | The timing half holds and the contract half does not exist. In the runtime zoteus ships, on a laptop CPU, the incumbent model reaches an overnight build of a design-point library, and so do the two small multilingual candidates R7 will choose between, while the base-sized ones do not (`bench/results/0025-x1-recall/embed-feasibility.json`, sampled and projected; the CPU cells ticket 0481 recovered from `bench/results/0264-gpu-arm/`; genuine GPU figures in `bench/results/0482-gpu-corrected/`). What is absent upstream is the whole contract: no reference machine, no bound of either kind, and no record-first phase order for the record bound to be measured against — the crawl pages the library rather than working a priority order, which is R2's finding. Bounds are pinned in the change that first asserts them, and the constraint this puts on which embedder may be the default lands in ticket 0495, the ticket that decides what ships. |

### Change and cost

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R3 | avoid unnecessary rebuild | ratified | partial | code | Updates ride a version watermark, so a resync no longer rebuilds the library. Invalidation is still per item, not per item and stage. |
| R11 | counter churn is not change | ratified | partial | code | The full-text sequence is read as its own cursor, which removes the defect's known cause. Nothing yet proves the absence, because the counters that would prove it are R27's. |
| R27 | edit one, count one | ratified | none | inferred | Per-stage work counters naming the input that triggered each unit of work do not exist upstream. Scoped issue A, ticket 0033. |

### Corpus

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R8 | 10k documents is not much | ratified | partial | code | The item cap is configurable and says when it truncates, and the two-stage vector search retired the full-scan red zone. The default cap still sits below the design point. |
| R9 | 15 000-page documents are included | ratified | none | code | Full text is capped per item by default, so a monster is indexed by its opening pages. This is the one place where a default contradicts a promise outright; ticket 0024 carries the filing. |
| R16 | my own words | ratified | none | code | Verified nil at v1.10.0: every crawl asks for top-level items, and neither a child note nor an annotation is one, so `zotero_annotate` writes what search can never find. Filed upstream as issue #33 with a working prototype; ticket 0022. |

### Query

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R5 | filters are good to have | ratified | partial | measured | Scoping exists, but experiment X4 measured the constrained path and it lost to ranking everything, superlinearly. Confirmed on the real corpus, where scoping costs more than ranking the whole library: ticket 0025. The design answer is settled and negative: no constrained step ships, and the ladder ends at R18's honest refusal. |
| R6 | a sufficient reply in 3 s beats the optimum in 3 min | ratified | partial | measured | The query path does no freshness work, and the two-stage search brought the scan well inside the budget. Nothing gates it, so the property is true and unwatched. |
| R18 | an empty result says which | ratified | none | inferred | An empty answer does not yet distinguish "nothing matches" from "this scope is not indexed yet". The decision it waited on is now made and negative — experiment X4 ran and no constrained step ships, so the `scope{}` block stops being the last resort and becomes the answer whenever a narrow scope outruns the deeper refetch. The ladder edit that follows is awaiting ratification in DECISIONS.md; ticket 0025. |
| R24 | a citeable page in one step | ratified | partial | code | Local extraction now yields real page ranges and a document's own outline. The primary locator is meant to be the entry heading, which waits on the segmenter: ticket 0028, gated by experiment X5. |
| R25 | one entry, one hit | ratified | none | inferred | Deduplication is per item, not per section, because sections do not exist yet. Same dependency as R24. |

### Multilingual

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R7 | multilingual by default | ratified | partial | measured | Accent folding merged, and the default embedder is local — but local is not multilingual: stock upstream hardcodes the English-tuned MiniLM construction, so R7's second MUST fails outright at the reviewed baseline, read in the source rather than measured. The English stopword list is still in place: experiment X2 measured its deletion and the deletion failed, so a library-derived droplist became a precondition rather than a follow-up. Ticket 0240 measured the replacement field and closed with a recommendation that sets no default; ticket 0495 decides what ships. Ticket 0090, ticket 0091. |
| R29 | the query language is not the document language | ratified | none | measured | Stock upstream embeds with the incumbent English MiniLM chain, which `verification/SMOKE-1.10.0.md` names as observed on a running server, so no cross-lingual channel exists at the reviewed baseline. That a multilingual embedder supplies one is measured rather than assumed: ticket 0266 ran EN and FR queries against Vietnamese, German and Russian content at every deployed dtype (`bench/results/0266-cross-lingual/SUMMARY.json`), and its negative control clears at every dtype for only two candidates of the six. The promise is a gate criterion for whichever entry the registry ships: ticket 0037, ticket 0495. |

### Embedding configurations

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R31 | selectable embedders are complete and proven locally | ratified | none | inferred | Stock upstream hardcodes the local MiniLM construction and has no complete entry-level validation. The invariant-first implementation is ticket 0488. |

### Custody and lifecycle

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R10 | local by default | ratified | shipped | measured | The default embedder is local, the model cache sits under the data directory, and the one API key that used to travel in a URL now travels in a header. Asserted against a running server rather than read: `bench/smoke_upstream.py` checks that effective embeddings resolve local and the embedder is active. Closed as ticket 0017. |
| R15 | deleted means gone | ratified | partial | inferred | Deletion reconciles against the key set, so a deleted item loses its rows. That every queue and every stage lose it too is design, not yet code. |
| R22 | pause stays paused | ratified | none | code | Verified absent at v1.10.0: there is no pause. Scoped issue A, ticket 0033. |
| R23 | upgrade and downgrade | ratified | partial | measured | The schema stamp is read before the file is opened writable, which is the half that prevents damage, and that half now holds under test: `bench/smoke_upstream.py` restamps a copy of a real index in both directions and finds the original preserved byte-for-byte and never served. Serving in both directions is still design — an older stamp is abandoned rather than migrated, which is filed upstream as issue #34. |
| R28 | uninstall | ratified | partial | measured | The downloaded model no longer escapes the data directory — observed on a build that actually downloaded one, not read off the source. Nothing has yet swept for other survivors. The known one was ticket 0017. |

### Multi-library and multi-process

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R12 | group libraries | ratified | partial | measured | Group libraries are served locally and merged into one index. The second clause fails today: a build for one library against an interrupted index appends to another's rows. Ten tests, all red on stock v1.10.0; the guard is in flight as pull request #32, ticket 0016. |
| R13 | second process | ratified | none | inferred | Two processes on one data directory are undesigned in the code and unsoaked here. Scoped issue C, ticket 0035. |

### Operator gates

These three requirements are unusual: each demands that a check *run*, not
merely that a property hold. So a green property with an unwired gate is a
half-kept promise, and the table says so.

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R19 | the fold sweep is a gate | ratified | partial | measured | The property holds — the fold merged upstream, and the sweep passed when it ran. The gate does not run: the sweep sits in `bench/` and `make check` does not call it, which is the state R19's own sentence forbids. Ticket 0026. |
| R20 | RAM budgets are gates | ratified | none | measured | Peak build memory was measured once, in a closed ticket, which is again what the requirement forbids. The fixture that would let it run on every check awaits a ruling, and experiment X3a is unrun. Ticket 0026. |
| R21 | same corpus in, same answers out | ratified | none | inferred | No pinned query set gates changes. The corpus is ticket 0029, the gate is ticket 0026. |

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
the ticket, pull request or issue it names, and those carry the evidence.
