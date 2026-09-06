# The Multilingual Menagerie: a principled construction

Date: 2026-09-06
Status: Proposed, not ratified
Owner: ticket 0029
Supersedes: the ten-principle draft of 2026-09-05 in this file's history

## Purpose

The author asked for a deep review of the 2026-09-05 draft, not a
rubber stamp, and for the construction of the Menagerie and of its
retrieval questions to be principled rather than accreted. This note does
both. Part A reviews the ten candidate principles and says which survive.
Part B rebuilds the design from three questions a fixture must answer:
what does the system see, what must come back, and how is the answer
read. Part C lists what needs ratification.

Everything here is proposed. `SPEC.md` changes only after a ruling in
`DECISIONS.md`. Every number quoted was executed on this host on
2026-09-06 unless a source is named.

## Part A. Review of the ten principles

| # | principle of 2026-09-05 | verdict | reason |
|---|---|---|---|
| 1 | SPEC owns the contract, `bench/fixtures/` owns instances | amend | right, and the defect it names is already present: §5.2.8's golden-gate paragraph is sixty lines of inventory (Gutenberg, the 157 twin records) around ten lines of contract, and it still says "~40 queries" against a ruled soft tally of 200 |
| 2 | Internet-user language shares as evidence | replace | wrong population, wrong instrument; see B.2.3 |
| 3 | representative core plus adversarial reserve | keep, extend | the strongest principle; it needs a third stratum for the scale surrogates SPEC already carries, and a statement of what "representative" is claimed on |
| 4 | pathology ledger from forums and trackers | amend | begin with this repository's own real-run findings, and say which ledger rows become questions and which become convergence assertions |
| 5 | development and acceptance question sets | amend | the draft's own rationale disclaims itself; the real risk is tuning, and in a public repository the split can only be procedural |
| 6 | graded relevance and no-answer questions | replace | grades must be stated in item terms, because the result list is items after entry collapse; a no-answer question has no meaning in semantic mode without an abstention rule the specification does not have |
| 7 | pinned run identity | keep | already the specification's posture; make it a `run` block of the gate's input schema |
| 8 | scorecard with cell floors | keep, sharpen | the cells are the lane matrix of B.2.3 crossed with strata and modes |
| 9 | fixture lifecycle | keep | tie each event to what it invalidates, per the 2026-08-31 rate-invalidation ruling |
| 10 | workshop derived from the fixture | keep, extend | the workshop's questions need beasts, and the recipe holds none; topic becomes a design axis, B.2.4 |

Two things the draft did not address at all, and which decide whether the
question bank measures anything: the unit of an answer (B.3.1) and where
the answer key is read from (B.3.4).

## Part B. The construction

### B.1 Three layers, three questions

| layer | artifact | the question it answers |
|---|---|---|
| library | recipe, injection into group 6659303, committed export | what does the system see |
| question bank | records with graded answer sets and locators | what must come back |
| scorecard | readings, cells, floors | how the answer is read |

Every reported number binds to one version of each layer. That is the
whole content of principles 7 and 9, stated once.

### B.2 The library as a population

#### B.2.1 Three strata, each with its own cells

- **Representative core.** Documents drawn from admitted archives to match
  the marginals of a real research library. It carries the stability
  reading and the bulk of the need-driven questions.
- **Adversarial reserve.** Members enumerated from two ledgers: the
  coverage ledger (ticket 0029's exit criteria) and the pathology ledger
  (B.5). Each member names the mechanism it carries, its expected
  behaviour, and whether it joins any answer set. Oversampled on purpose.
- **Scale surrogates.** The synthetic document the RSS gate uses at
  44 906 152 characters, and the 15 000-page PDF of R8. They cannot be
  committed and are not part of the export. They carry a fidelity claim
  that only the library level can renew, exactly as §5.2.8 already says
  for the RSS gate. Naming them a stratum stops the export from being
  asked to prove R8.

The intersections the 2026-08-31 ruling demands live in the reserve: a
monster in a non-Latin script, a scale run at the multilingual default.

#### B.2.2 The sampling frame is a census

The core's marginals come from a read-only census of the author's library,
reachable this morning at 7 553 top-level items and 9 309 attachments. The
marginals: item types; attachments per parent; attachment content type and
link mode; notes and annotations per item; language of items; full-text
coverage by content type; page and character quantiles and the fraction
at the stock caps; collection membership; group versus personal; trash
and feed items counted apart because the perimeter excludes them.

Representativeness is claimed on those marginals and on nothing else. The
census gives the shape; the archives give the documents. The 2026-09-02
ruling that a personal library is not a provenance stands untouched. What
the core cannot represent is content: the author's library is climate
economics and Vietnamese studies, and the Menagerie is whatever its theme
makes it (B.2.4).

#### B.2.3 A lane matrix replaces a language share

Principle 2 proposed Internet-user language distributions as evidence for
the fixture's language mix. Drop it. The population of interest is
research libraries, not Internet users; the statistic varies by what is
counted; and it is dominated by English, which is the one language whose
coverage was never in doubt. Two legitimate sources exist and both are
already in hand: R7's tiers, and the census.

The design object is a matrix of query language by document language.

| query \ document | EN | FR | VI | AR RU ZH DE HI ES |
|---|---|---|---|---|
| EN | MUST | reported | MUST (R29) | reported |
| FR | reported | MUST | MUST (R29) | reported |
| VI | reported | reported | MUST | reported |
| AR RU ZH DE HI ES | reported | reported | reported | SHOULD, diagonal only |

A MUST cell has a floor. A SHOULD cell is reported and may be set aside
with a stated reason, which is what R7 says a tier means. A "reported"
cell is measured when its questions exist and never gates. Macro-average
by cell is reported beside any weighted aggregate; a zero in a MUST cell
is a failure whatever the aggregate says.

#### B.2.4 The beasts are a design axis

The workshop note of 2026-09-05 lists its demonstrator questions: jaguar
as animal, brand and software; crane as bird and machine; bat, octopus,
wolf, whale; dragon as a mythic negative control. Those need documents
about animals, across senses and across languages. The recipe holds
twenty-six records of economics, Vietnamese classics, physics and one
constitution, and not one beast. The name says menagerie; the content
does not.

So topic is a declared axis, not an accident of what was easy to source.
The core keeps the census's shape. The reserve and the cross-lingual
anchors adopt the animal theme, because it is the theme that makes the
ambiguity and false-friend questions possible at all. Whether the core
also leans toward the theme is the author's call; nothing in the
marginals decides it.

#### B.2.5 Sourcing: the admission test stands, Wikipedia carries the SHOULD tier

The five-part admission test of 2026-09-04 is right and is not reopened.
The ticket's log calls the SHOULD tier "work nobody has done yet": a
public-domain Devanagari or Arabic set with tables, captions and
footnotes. The Wikipedia constellation, admitted the same day, does most
of that work. Every one of the nine languages has articles on the same
beasts; each article is pinned by permanent revision id under CC BY-SA;
an infobox is a table, an image caption is a caption, a reference list is
a set of footnotes; and interlanguage links are typed translation
relations, which is the separate-record translation pair the coverage
ledger asks for. The lost des Michels pair, the FR–VN anchor, has a
candidate replacement in a Wikisource original beside a public-domain
French translation; that is a candidate to verify, not a fact.

Two limits, stated so they are not discovered. Wikipedia is HTML or
wikitext, never PDF, so it can carry none of the PDF pathologies and the
core must stay archive PDF. And an article is not an article of research;
the SHOULD tier is proved on encyclopaedic prose until an admitted
archive supplies a scholarly document in that script.

### B.3 The question as an instrument

#### B.3.1 The unit of an answer

The author asked whether grading means where the best chunk lands in the
list. Yes, with one precision. The list the user sees is a list of items
after entry collapse: each row is a work, scored as the maximum over its
chunks, and R24 says one entry gives one hit. So the rank of the best
chunk is the rank of the row whose evidence chunk is the pinned passage.

A question therefore pins two things. The **work identity** of each
answer, which R34 reads. And the **locator** of the answer passage:
attachment key, page or section, and a character span in the export,
which R24 reads and which diagnosis needs. Pinning the span is what makes
a hit on the right item for the wrong reason visible, such as a title
match on a document whose body was never extracted. Until entries exist
the gate reads item projections and says so, as §5.2.8 already states.

#### B.3.2 Grades, in item terms

| grade | meaning | how R34 reads it |
|---|---|---|
| 2, primary | an item whose export text contains the pinned span | must be in the first ten |
| 1, acceptable | a related item: a declared rendering, a translation twin, the book of a chapter | counts neither for nor against |
| 0 | everything else | not gated; the count in the first ten is a reported cell |

A question may carry several grade-2 items, which is what a duplicate
pair produces; the set is what is pinned, and D11 keeps order ungated.
Precision is deliberately not gated, which is the specification's
choice; the grade-0 count is reported so the choice stays visible.

#### B.3.3 No-answer questions, narrowed

A retrieval system without an abstention rule always returns k rows. The
specification has no abstention threshold for semantic or hybrid mode, so
"no answer present" cannot be a pass criterion there without inventing
one. Two forms survive. A lexical no-answer question: a rare string
absent from the corpus must return empty, with R18's reason. A scope
no-answer question: a collection with nothing indexed must say so rather
than answer from elsewhere. Whether semantic mode should abstain is a
system design question for `SPEC.md`, raised here and not decided.

#### B.3.4 The answer key is read from the export

The one-off probe of 2026-09-02 measured word-set Jaccard between
Zotero's extraction and `pdftotext` at 0,39 to 0,61 on three documents,
with a 100-page cap and no page breaks. An answer located in the PDF may
not exist in the text the system indexes. So the rule: a pinned span is
located in the committed export. A question whose answer is in the PDF
and not in the export is filed as a failure control with its mechanism
named, cap, missing text layer or DjVu, and not as a retrieval question.
Exact-string questions quote the export. Paraphrase questions are written
from the page by a person and checked mechanically for zero content-word
overlap with the span.

This is why the export precedes every question, and why child 0632 is
the critical path.

#### B.3.5 Two generators, one soft quota

**Need-driven.** An information need is written in prose first, before a
document is opened, in the shapes the workshop names: cross-language,
scientific against common names, cultural senses, lexical false
positives, indirect description. Then the answer is located. Writing the
need first is what stops the question being a paraphrase of a passage
already chosen, the circularity this repository's memory warns about.

**Hazard-driven.** One question per mechanism of the reserve and per
sub-case of the tally. These are the rows of ticket 0029's table.

The 200-row tally is a soft quota over both, as ruled on 2026-09-06, and
the reuse floor of five questions per document stays a coverage rule.

One record shape for every question: identifier; the need in prose; query
text; query language; document language or languages; signal, exact or
paraphrase or agreement; mode expectation, lexical or semantic or hybrid;
facet, core or notes or group or deep-body; mechanism identifiers; the
graded set; locators; stratum; and provenance, who wrote it, from which
page, on which date.

#### B.3.6 Judging

With at most about forty documents, item-level judging is exhaustive by
construction: every item has a grade for every question, grade 0 by
default and explicit for twins and renderings. Passage-level candidates
are pooled from the top ten of the lexical, semantic and hybrid arms, and
the author adjudicates; disagreements between arms are recorded because
they are the interesting cases. This is the pooling construction of
shared IR evaluations scaled to a corpus small enough to judge whole.

#### B.3.7 Development and acceptance, split by procedure

Nothing in a public repository is hidden, so the draft's frozen set cannot
be frozen in the sense it meant. The real risk is tuning: fusion weights,
query prefixes, chunk geometry and stopword lists adjusted against the
pinned set until it passes. The split is therefore procedural. Tuning
changes cite development-set deltas only. The acceptance set runs on the
golden gate and at release, not in the development loop. Both sets are
stratified so every cell of B.2.3 and every stratum appears in each. A
re-pin of an acceptance question is a lifecycle event of B.6, reviewed as
a set diff like any other re-pin.

### B.4 Readings and the scorecard

- **R34, absolute.** Every grade-2 item in the first ten, per question,
  no tolerance. Reported per MUST cell as a floor of 100 %.
- **Stability.** The Jaccard thresholds §5.2.8 already owns, run against
  the previous run, over the core.
- **Passage fidelity, R24.** The fraction of grade-2 hits whose shown
  evidence overlaps the pinned span.
- **Failure controls.** Expected degradation observed through status and
  R18, never counted under R34.
- **Cells.** Lane by stratum by mode. MUST cells have floors; SHOULD cells
  are reported; no aggregate decides acceptance.

### B.5 The pathology ledger, seeded from this repository

The draft proposed searching forums and trackers. Start nearer home. This
repository has already found, in real runs and not in mocks, a ledger's
worth of mechanisms: linked-file attachments refused in every group
library; `extra` rejected on attachment items; DjVu never eligible for
extraction; un-OCR'd scans with no text layer, three of them in the
current group; a reindex that never settles on an unindexable item; the
100-page and 500 000-character caps; extractor generations without page
breaks, mojibake and raw ligatures in surviving caches (ticket 0480); and
the 1 200-character chunk that overruns a 498-token budget in a
one-character-per-token script (scoping brief §5).

Each row records source, mechanism, symptom, severity, the fixture member
carrying it, and its expected behaviour. Not every row becomes a question.
Indexing pathologies map to convergence-harness assertions, quarantined
or metadata-only with reason; retrieval pathologies map to questions. The
row says which. The external campaign over Zotero's forum and the issue
trackers of the five targets then runs with the draft's saturation rule,
two consecutive passes finding no new mechanism, and a dated cutoff.

### B.6 Run identity and lifecycle

The gate's input schema gains a `run` block: recipe hash and export hash
as the fixture version; extraction configuration; the embedder
fingerprint of §5.2.7; chunker key; index schema; retrieval mode. A result
without the block is not-run.

| event | what it invalidates |
|---|---|
| compatible addition: a new question or document, existing answers unmoved | nothing |
| re-pin: the export changes | answer locators, and every rate measured against the old passage distribution (ruling of 2026-08-31) |
| major version: the lane matrix or the grades change | historical comparison |
| archive: results move to `verification/` with their run block | nothing; they stop being current |

### B.7 The workshop

Principle 10 stands. The demonstrator subset is a list of question
identifiers, a view on the bank, never a copy that can drift.

## Part C. For ratification

1. Three strata, with the scale surrogates named as one and kept out of
   the export.
2. The lane matrix of B.2.3 replaces any language share; Internet-user
   distributions are dropped as a design input.
3. The animal theme is a declared axis for the reserve and the anchors.
4. The Wikipedia constellation carries the SHOULD tier and the translation
   twins, within the two limits stated.
5. Grades in item terms; R34 reads grade 2 only; the grade-0 count is a
   reported cell.
6. No-answer questions narrowed to lexical and scope controls; semantic
   abstention is referred to `SPEC.md` as an open design question.
7. The answer key is read from the export, never from the PDF.
8. The development and acceptance split is procedural and stratified.
9. `SPEC.md` gains a section owning the fixture contract; the §5.2.8
   golden-gate paragraph keeps the thresholds and readings and loses its
   inventory, and its "~40 queries" is corrected to the soft tally.
10. The pathology ledger is seeded from this repository's own findings
    before any external campaign.
