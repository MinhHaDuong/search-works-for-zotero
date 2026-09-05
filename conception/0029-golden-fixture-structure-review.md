# Structural review of the golden fixture and workshop

Date: 2026-09-05
Status: Proposed, not ratified
Owner: ticket 0029

## Purpose

This note reviews the author's proposals for the Multilingual Menagerie as a
golden test library, question bank, and workshop source. It records candidate
design principles without changing `SPEC.md`; normative language belongs there
only after ratification through `DECISIONS.md`.

## 1. Give the golden fixture a normative contract

Add a dedicated `SPEC.md` section for the golden test library and its request
or question bank. The section should define the stable contract rather than
the current document inventory:

- the layers: Zotero items, attachments, extraction export, passages, queries,
  relevance judgements, and expected locators;
- mandatory dimensions and required sub-scores;
- sampling and weighting rules;
- provenance and reproducibility requirements;
- versioning, re-pin conditions, and comparison validity.

Concrete manifests, measured distributions, and individual questions remain
under `bench/fixtures/`. Replacing one source document should not itself require
a normative specification change.

## 2. Use Internet language distributions as evidence, not a sole quota

Relate document and query languages empirically to Internet-user language
distributions, but do not make the fixture mechanically proportional to a
single global statistic. Such a statistic varies with the measured population
(users, content, traffic, or search), is not a direct proxy for Zotero users,
and would let English volume dominate failures in smaller language cells.

Use three layers:

1. a minimum coverage layer preserving the MUST and SHOULD language/script/
   morphology commitments unless a later ruling supersedes them;
2. a realistic document and query profile informed by Internet use and, where
   defensible, Zotero-relevant use;
3. balanced evaluation that reports a macro-average by language beside any
   usage-weighted aggregate.

Suggested normative sense: the language distribution is empirically related
to Internet-user distributions, not mechanically proportional to them.

## 3. Separate representative and adversarial strata

Derive the representative core from the author's existing real library:

- library and document sizes;
- Zotero item-type distribution;
- attachment file-type distribution;
- attachments per item;
- document and passage lengths;
- languages, group items, notes, and annotations.

Record the census or sampling method and the comparison between the real
library and fixture. Do not let that profile eliminate rare but important
conditions. Add an explicitly oversampled adversarial reserve for malformed
files, conflicting duplicates, difficult scripts, many-attachment parents,
extraction boundaries, and other low-frequency/high-consequence cases.

Report the representative-core and adversarial-reserve results separately
before any aggregation. A strong score on ordinary documents must not conceal
failure of a mandatory adversarial condition.

## 4. Turn reports into a traceable pathology ledger

Search relevant mailing lists, forums, issue trackers, and support discussions.
Do not promise one fixture per post: several reports often instantiate the same
failure mechanism, while an open-ended requirement to cover every future post
can never close.

For every distinct, reproducible mechanism within scope, record:

- source and date;
- affected product and version;
- observable symptom;
- suspected or confirmed mechanism;
- failure class;
- reproducibility, severity, and recurrence evidence;
- fixture item and question that cover it;
- expected behavior and pinned result.

Define a dated search campaign and a saturation rule, such as two consecutive
passes over the selected sources finding no new failure class. The target is
coverage of mechanisms, not duplication of reports.

## 5. Add development and acceptance question sets

Keep a public, explanatory development set for implementation work and a frozen
acceptance set used sparingly for final comparison. This reduces adjustment to
the known 200 questions even though the evaluated systems are retrieval
pipelines rather than models trained on this corpus.

## 6. Admit graded relevance and no-answer questions

The oracle should distinguish at least:

- primary answer;
- acceptable answer;
- useful context;
- false positive;
- no answer present in the library.

No-answer questions test whether a system can avoid manufacturing relevance.
Multi-answer and partial-answer cases should have explicit adjudication rules.

## 7. Pin the identity of every run

Every reported result should bind to:

- fixture and export versions;
- document hashes;
- extraction configuration;
- embedding model, precision, pooling, normalization, and query/document
  prefixes;
- segmentation parameters;
- index schema;
- lexical, semantic, or hybrid retrieval mode.

This is necessary for comparisons to survive changes such as the already
observed pooling correction.

## 8. Publish a scorecard, not one score

Report separate cells for language, monolingual versus cross-lingual retrieval,
format, internal structure, annotations, pathology class, and lexical,
semantic, and hybrid modes. Keep retrieval quality, rank, coverage, build time,
query latency, and resource cost distinct.

Use floors for mandatory cells as well as macro and usage-weighted aggregates.
No overall average should compensate for a zero in a required cell.

## 9. Define the fixture lifecycle

Specify what counts as:

- a compatible addition;
- a change requiring re-pinning;
- a major version that invalidates historical comparison;
- an archived historical result;
- the source-search cutoff for a pathology-ledger release.

## 10. Derive the workshop from the golden fixture

The workshop is a projection of the real golden fixture, not a second toy
corpus. Select roughly 10–20 demonstrator questions from the library and its
question bank for the proposed 90-minute semantic-search safari. This keeps the
pedagogical examples connected to the evidence and prevents a second fixture
from drifting.

## Candidate principles for ratification

1. `SPEC.md` owns the normative fixture contract; `bench/fixtures/` owns its
   concrete instances.
2. Language selection combines observed use with script and morphology risk.
3. Macro language scores and usage-weighted scores are both reported.
4. The fixture contains a representative core and a separately scored
   adversarial reserve.
5. Every distinct, reproducible, in-scope pathology mechanism is traceable to
   a source and a covering fixture/question; collection is versioned and
   saturation-bounded.
6. Development and acceptance questions are separated.
7. Graded relevance and no-answer queries are first-class.
8. Every run records a complete, reproducible identity.
9. Mandatory cells have floors; no single aggregate decides acceptance.
10. The workshop is derived from the golden fixture and question bank.
