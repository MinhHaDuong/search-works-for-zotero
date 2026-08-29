# The specification chain

This is the entry point to the chain, and it owns one thing the other
documents do not: **where each of the twenty-eight promises actually
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
[`../STATE.md`](../STATE.md) holds the prototype phase's measurement record,
[`../RUNBOOK.md`](../RUNBOOK.md) says how to run the measurements, and
[`../GOVERNANCE.md`](../GOVERNANCE.md) states how this repo conducts itself
upstream. The work train is the tickets.

---

## Where the promises stand

Measured against upstream **v1.10.0**, the reviewed baseline in
[`../UPSTREAM`](../UPSTREAM). The implementation is not in this repository: it
is [`oscardvs/zoteus`](https://github.com/oscardvs/zoteus), so "delivered"
always means *holds on stock upstream*, never *we wrote it*.

**Designed** — the promise has a settled design behind it.

`●●●●●●●●●●●●●●●●●●●●●●●●●●●○` &nbsp; 27 ratified · 1 still open

**Delivered** — the promise holds on stock upstream today.

`●◐◐◐◐◐◐◐◐◐◐◐◐◐◐◐○○○○○○○○○○○○` &nbsp; 1 shipped · 15 partial · 12 not yet

`●` shipped &nbsp;·&nbsp; `◐` partial &nbsp;·&nbsp; `○` not yet

**These statuses are read, not run.** No suite tests a release against the
requirements, so each one was assigned by reading the upstream source at the
reviewed baseline and the ticket that carries the remainder. Only the
arithmetic is mechanical: the bars are recomputed from the rows, never the
rows from a measurement. Some rows do rest on something executed — the
experiments, and the ten tests that fail on stock upstream under R12 — and
those say so. Ticket 0026 is what would make this column derived rather than
judged, by wiring the gates R19, R20 and R21 already demand.

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
| Coverage and convergence | `●●●●●○` | `◐◐◐○○○` |
| Change and cost | `●●●` | `◐◐○` |
| Corpus | `●●●` | `◐○○` |
| Query | `●●●●●` | `◐◐◐○○` |
| Multilingual | `●` | `◐` |
| Custody and lifecycle | `●●●●●` | `●◐◐◐○` |
| Multi-library and multi-process | `●●` | `◐○` |
| Operator gates | `●●●` | `◐○○` |

---

## The twenty-eight

`designed` is `ratified` or `open`; `delivered` is `shipped`, `partial` or
`none`. The standing column cites the ticket, pull request or issue that
carries the remainder — never a threshold, which belongs to DESIGN.md.

### Coverage and convergence

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R1 | eventually the whole library is indexed | ratified | partial | Incremental update, build resume and the coverage-gap catch-up all landed upstream. That convergence actually reaches every item, unattended, is unmeasured: the harness that would watch it is ticket 0026. |
| R2 | most recent first | open | none | The crawl pages the library; it does not work a priority order. The requirement's own wording is under revision in ticket 0080, which also reworks the frontier that justified it. |
| R4 | something partial is better than nothing | ratified | partial | A capped or interrupted build answers queries and says it was capped. What it does not yet do is report coverage per stage, which is what makes a partial index distinguishable from a complete one. |
| R14 | no text is a terminal state | ratified | none | An attachment that yields no text is not recorded as done-with-a-reason, so it is re-examined and counted as missing. Held in reserve as ticket 0019. |
| R17 | coverage in one sentence | ratified | partial | Build status carries counters, not the sentence: N of M items, per stage, with the most-recent-covered date. Ticket 0120, ticket 0140. |
| R26 | convergence is watched, not trusted | ratified | none | No harness polls an empty index to completion. Ticket 0026, and the requirement's prefix clause is being rewritten in ticket 0080. |

### Change and cost

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R3 | avoid unnecessary rebuild | ratified | partial | Updates ride a version watermark, so a resync no longer rebuilds the library. Invalidation is still per item, not per item and stage. |
| R11 | counter churn is not change | ratified | partial | The full-text sequence is read as its own cursor, which removes the defect's known cause. Nothing yet proves the absence, because the counters that would prove it are R27's. |
| R27 | edit one, count one | ratified | none | Per-stage work counters naming the input that triggered each unit of work do not exist upstream. Scoped issue A, ticket 0033. |

### Corpus

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R8 | 10k documents is not much | ratified | partial | The item cap is configurable and says when it truncates, and the two-stage vector search retired the full-scan red zone. The default cap still sits below the design point. |
| R9 | 15 000-page documents are included | ratified | none | Full text is capped per item by default, so a monster is indexed by its opening pages. This is the one place where a default contradicts a promise outright; ticket 0024 carries the filing. |
| R16 | my own words | ratified | none | Verified nil at v1.10.0: every crawl asks for top-level items, and neither a child note nor an annotation is one, so `zotero_annotate` writes what search can never find. Filed upstream as issue #33 with a working prototype; ticket 0022. |

### Query

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R5 | filters are good to have | ratified | partial | Scoping exists, but experiment X4 measured the constrained path and it lost to ranking everything, superlinearly. The design answer is settled and negative: no constrained step ships, and the ladder ends at R18's honest refusal. |
| R6 | a sufficient reply in 3 s beats the optimum in 3 min | ratified | partial | The query path does no freshness work, and the two-stage search brought the scan well inside the budget. Nothing gates it, so the property is true and unwatched. |
| R18 | an empty result says which | ratified | none | An empty answer does not yet distinguish "nothing matches" from "this scope is not indexed yet". The decision it depends on sits in ticket 0025. |
| R24 | a citeable page in one step | ratified | partial | Local extraction now yields real page ranges and a document's own outline. The primary locator is meant to be the entry heading, which waits on the segmenter: ticket 0028, gated by experiment X5. |
| R25 | one entry, one hit | ratified | none | Deduplication is per item, not per section, because sections do not exist yet. Same dependency as R24. |

### Multilingual

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R7 | multilingual by default | ratified | partial | Accent folding merged, and the default embedder is local. The English stopword list is still in place: experiment X2 measured its deletion and the deletion failed, so a library-derived droplist became a precondition rather than a follow-up. Ticket 0090, ticket 0091, ticket 0240. |

### Custody and lifecycle

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R10 | local by default | ratified | shipped | The default embedder is local, the model cache sits under the data directory, and the one API key that used to travel in a URL now travels in a header. Closed as ticket 0017. |
| R15 | deleted means gone | ratified | partial | Deletion reconciles against the key set, so a deleted item loses its rows. That every queue and every stage lose it too is design, not yet code. |
| R22 | pause stays paused | ratified | none | Verified absent at v1.10.0: there is no pause. Scoped issue A, ticket 0033. |
| R23 | upgrade and downgrade | ratified | partial | The schema stamp is read before the file is opened writable, which is the half that prevents damage. Serving in both directions is still design. |
| R28 | uninstall | ratified | partial | The downloaded model no longer escapes the data directory. Nothing has yet swept for other survivors. The known one was ticket 0017. |

### Multi-library and multi-process

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R12 | group libraries | ratified | partial | Group libraries are served locally and merged into one index. The second clause fails today: a build for one library against an interrupted index appends to another's rows. Ten tests, all red on stock v1.10.0; the guard is in flight as pull request #32, ticket 0016. |
| R13 | second process | ratified | none | Two processes on one data directory are undesigned in the code and unsoaked here. Scoped issue C, ticket 0035. |

### Operator gates

These three requirements are unusual: each demands that a check *run*, not
merely that a property hold. So a green property with an unwired gate is a
half-kept promise, and the table says so.

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R19 | the fold sweep is a gate | ratified | partial | The property holds — the fold merged upstream, and the sweep passed when it ran. The gate does not run: the sweep sits in `bench/` and `make check` does not call it, which is the state R19's own sentence forbids. Ticket 0026. |
| R20 | RAM budgets are gates | ratified | none | Peak build memory was measured once, in a closed ticket, which is again what the requirement forbids. The fixture that would let it run on every check awaits a ruling, and experiment X3a is unrun. Ticket 0026. |
| R21 | same corpus in, same answers out | ratified | none | No pinned query set gates changes. The corpus is ticket 0029, the gate is ticket 0026. |

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
