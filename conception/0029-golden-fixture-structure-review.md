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
read. Part C is the record of the five-seat panel the author asked for,
which decided Part B's ten points. Part D is the ratification list as
the panel amended it, sixteen items.

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

## Part C. Panel record

The author asked for the ten points to be decided in a panel. Five seats
read Parts A and B, the requirements, the ratified rulings, the census
and the tally, each from its own discipline, on a model decorrelated
from the one that wrote Part B. The seats:

- **A**, evaluation methodology: Cranfield and TREC practice, pooling,
  graded relevance, statistical power.
- **B**, the Zotero platform: what the client, its extractor and its APIs
  do; B ran read-only probes against the live group and the client's
  own source.
- **C**, the specification and bench owner: what can be gated, what it
  costs to keep green, the guard budget.
- **D**, the researcher and workshop leader: realism, pedagogy, fairness
  to Vietnamese and second-tier scholarship.
- **E**, red team: how each point is gamed, satisfied vacuously, or
  contradicts a ruling.

For each point: the seats' verdicts, the disagreement that mattered, and
the moderator's verdict with the amendment text that survives the
objections. Amendment text is what goes to ratification.

### C.1 Three strata

Verdicts: A amend, B amend, C ratify, D amend, E amend.

The disagreement. C ratifies because the point removes an obligation
and costs no gate. The other four each found a hole. A: a surrogate
drawn from no frame is not a stratum, and any unweighted average over
core plus reserve is biased by design. B: the surrogates are outside
the export because no stock Zotero can serve them at all, its caps
topping out near one million characters per attachment, not merely
because they cannot be committed. D: the census shows a real library is
already pathological, with 13,0 % of PDFs past the page cap and 9,2 % of
files in formats never extracted, so a core scrubbed of those rates is
a library nobody works in. E: Part B put the ruled non-Latin monster
intersection in the reserve and declared monsters uncommittable in the
same paragraph, and the reuse floor of five questions per document
collides with the 14,8 % of records that have no attachment.

**Verdict: AMEND.** Two sampled strata and a non-sampled appendix. The
representative core is quota-sampled against the census marginals,
defect marginals included: cap truncation, unindexable formats, empty
or malformed language fields. The adversarial reserve holds only
conditions the census cannot supply. Scale surrogates are an appendix
outside the export and outside every average, committed as a
deterministic generator plus output hash, so the monster-by-script and
scale-by-multilingual intersections run wherever the gate runs and only
their fidelity claim defers to library level. No score is reported over
core plus reserve unweighted. Representativeness is claimed only on
cells whose expected count exceeds one document. The reuse floor binds
documents with body text; record-only items carry record questions.

### C.2 The lane matrix

Verdicts: A ratify, B amend, C amend, D amend, E amend.

A ratifies: this is CLEF's own construction. The amendments do not
contradict it, they harden it. B: document language cannot be read from
Zotero, whose field is free text, parent-only, and empty on half the
census; the matrix needs an undeclared-language column. C: the matrix
must cite R7 and R29 for which cells bind, never restate them, and must
keep one row per language, since a bag of six hides a zero in Hindi
behind Spanish. E: a cell with no questions must print not-measured,
and each MUST cell needs a minimum count fixed before authoring, or the
hard questions get parked where nothing gates. D's hill: Vietnamese is
MUST as a document language and only reported as a query language, which
is backwards for the scholar it claims to serve; the three queries D
would type are Vietnamese, one without diacritics, one with a decimal
comma, and none needs a document the recipe lacks.

**Verdict: AMEND.** The matrix is the reporting layout of the fixture
contract: one row and one column per language, plus an
undeclared-language document column. Document language is the recipe's
declared per-attachment language, never Zotero's field. Which cells bind
is R7's and R29's, cited. Every cell prints its question count beside
its rate and prints not-measured at zero. Each MUST cell carries a
minimum count fixed before authoring. D's point is referred as its own
ratification item, D.11: widening R29 so that VI to EN and VI to FR bind,
which is a requirement change and not a fixture decision.

### C.3 The animal theme

Verdicts: A amend, B amend, C amend, D amend, E amend.

The real disagreement is between A and E. A wants the theme across every
sampled stratum, the core included: in a forty-item collection,
discriminative power comes from confusability, and a corpus of disjoint
topics lets a title-reading ranker pass ten-of-forty. E wants it
confined to the workshop subset and the ambiguity families, because
theming the anchors overrides ruling 5 of 2026-09-02 without naming it,
and an all-animal reserve moves the grade-0 count with no system
change. B adds that in the reserve the mechanism must govern and the
theme yield, or mechanism coverage is traded for subject. C asks that
concentration be visible: distinct archives per MUST cell. D corrects a
fact: the dragon is Lạc Long Quân in the Vietnamese chronicles and fails
as a mythic negative control; and Johnson 1785 and Bonet 1899 already
carry beast entries with pinned pages.

**Verdict: AMEND.** A's argument is right about confusability and wrong
about the remedy. A real library is clustered, and the census-shaped
core is sampled in clusters, several documents per subject, so that the
ten-of-forty cut discriminates; the beasts are one cluster among them.
The theme is a declared axis for the ambiguity, sense and false-friend
question families and for the workshop subset. In the reserve the
mechanism governs. The cross-lingual anchors keep the shapes ruling 5
pinned and gain beast pairs beside them, never instead. Every negative
control is verified absent against the corpus. The scorecard reports,
per MUST cell, how many distinct archives serve it.

### C.4 Wikipedia

Verdicts: A amend, B amend, C amend, D amend, E reject.

Unanimous on the half that fails: an interlanguage link joins two
independently written articles, not a translation and its original. As
a translation twin it would put same-topic text into a slice whose
stated purpose is alignment on equivalent text, and the number would
still print. Four seats keep a narrowed Wikipedia; E withdraws it,
because the SHOULD tier exists to reach script-specific PDF extraction
and HTML cannot. B measured the mechanics: a permanent revision id pins
wikitext only, since MediaWiki renders old revisions with current
templates; infoboxes, captions and references arrive as template calls
and markup, so no structural mark is proved; text attachments report
characters and never pages, so no page locator and no page cap is
crossed. B also found the live defect: the three wikitext attachments
were injected without a charset, Zotero wrote windows-1252 onto them,
and their indexed text is mojibake. A adds contamination: every
multilingual embedder was trained on Wikipedia and on bitext mined from
it.

**Verdict: AMEND, narrowly.** Wikipedia is admitted for the SHOULD tier's
script, normalisation and ranking probes and for the beasts, reported
and never gated, with the contamination caveat beside each number. Each
article is pinned by raw wikitext at a revision id, with charset set
explicitly on the attachment and a check that the bytes carry body text
rather than a transclusion skeleton. Interlanguage links are recorded as
same-subject, never as translation, and no Wikipedia pair enters the
parallel slice or satisfies the ledger's translation pair. Each SHOULD
language's extraction sub-case stays not-measured until an archive PDF
in that script lands; a language with none is set aside with its reason,
per R7.

### C.5 Grades

Verdicts: A amend, B amend, C amend, D amend, E amend.

Five amendments, converging. A: a grade that counts neither way is not a
grade, it is bpref's treatment of unjudged documents; and converting a
rank to a boolean discards the sensitivity the author asked for. E and
A together: grade 2 must be a judgement that the item answers the need,
not string presence. D: on a cross-lingual question, returning the
English translation instead of the Vietnamese decision is the miss R29
exists to catch, and a neutral grade 1 scores it as a pass. E: replace
the neutral grade with a directional assertion per relation type, which
R24's collapse rule then reads. B: bind grade 2 to a selected
attachment, since a span in a sibling the ruled selection skips is
unretrievable however good retrieval is, and declared renderings
collapse to one row. C: the scorer today has one flat list, so a grade-1
item placed in it gates; the input schema must go to v2 and a primary
set larger than k must be refused at authoring.

**Verdict: AMEND.** Grade 2 is an item judged to answer the stated need
whose pinned span sits in the export text of a selected attachment.
There is no neutral grade. Each related item carries a directional
assertion naming its relation and the required outcome: collapsed into
the answer row, present as a distinct row, or absent. R24 reads those
assertions and a violated one fails the question; on a cross-lingual
question the target-language document is primary and its other-language
twin is asserted distinct. A primary set never exceeds k. R34 reads the
primary set alone and tolerates no miss. Reported beside it, never
gating: the rank of the primary answer per question, mean reciprocal
rank per cell, and the count of returned items outside every list. The
gate's input schema becomes v2 and refuses v1. The graded set is frozen
at authoring; a change is a re-pin with its set diff as the review
artifact.

### C.6 No-answer questions

Verdicts: A amend, B ratify, C amend, D amend, E amend.

B ratifies because the platform supplies both controls in real form:
816 office, image and archive attachments at zero indexed, 446 bookmarks
refused by link mode, and two attachments in the live group whose
full-text route answers 404. The amendments add rather than subtract.
A and D: an unanswerable topic is scorable without an abstention rule
as score separation, the top score on absent concepts against matched
present ones, and referring the question to the specification with no
measurement guarantees it arrives with nothing to read. C: the
specification has no place for an open design question; §5.3 carries
experiments with decision rules, and R18 is already a MUST that
semantic mode cannot meet, which is a conflict to file. E: a third
gated form exists today, the degraded-mode disclosure of R29 and
§5.2.5, and the deferral needs an owner and a date.

**Verdict: AMEND.** Three gated forms: lexical absence, unindexed scope,
and degraded-mode disclosure. One reported form: a semantic absence
probe read as top-score separation against a matched present probe.
Semantic abstention is filed as a §5.3 experiment with a decision rule
and as a ticket with an owner; until it decides, R18 is recorded as
untested in semantic and hybrid mode, and those cells report not-run.

### C.7 The answer key

Verdicts: A amend, B amend, C ratify, D amend, E amend.

C ratifies because this is the one point that becomes a check that runs
today with no Zotero and no author's hours. A's hill runs the other way
and is the deeper argument: judging against the index makes the
collection non-reusable, and R1 promises the extraction chain will
improve, so the day the cap moves every question filed as a failure
control silently becomes a retrieval question nobody re-derives. E
adds that the rule retires the ruled beyond-boundary questions of
2026-09-03 without naming the ruling. D: it empties the deep-body facet.
B found the fact that changes the point: the control plugin forces
extraction with the flag that ignores both limits, so the export the
harness produces is uncapped while recording stock caps as its
settings; measured, every PDF in the live group sits at all pages
indexed.

**Verdict: AMEND.** Relevance is judged against the source document, with
page and verbatim quote read on the page. Reachability is a separate
mechanical attribute of each pinned answer, computed against the
committed export and stamped with the extraction configuration that
produced it. Reachable answers are retrieval questions; unreachable ones
stay in the bank as expected-miss questions naming their mechanism,
gated as such, never deleted. A re-export recomputes the attribute and
never reopens the judgement. The export is produced at the settings it
records: the forced reindex runs at stock limits by default, an uncapped
reindex is a separately declared arm for the cap-crossing questions,
both preferences are read from the client and not typed, and the export
refuses itself when a captured counter contradicts a recorded setting.
Locators are stored as attachment key, page or section, and quoted span
text, with the character offset resolved at load time, so a
re-extraction relocates spans mechanically and only lost answers come
back red.

### C.8 Development and acceptance

Verdicts: A reject, B ratify, C amend, D reject, E reject.

B ratifies because the split is free on the platform side. Three seats
reject it. A: the specification already has a held-out instrument, the
library level, which cannot be tuned against by construction; halving a
soft 200 empties cells that are already near-empty. D: the defence
against tuning is provenance, not partition, and the workshop supplies
questions authored by people who never saw a fusion weight. E: the
golden gate already runs inside the development loop per the
specification's own gate list, tuner and judge are one person, and a
stratified halving is arithmetically impossible on the tally's thinnest
rows. C keeps a set field and strikes the stratification clause.

**Verdict: REJECT as drafted, replace.** No halving. Every question
carries a set field and provenance: author, date, and whether it was
authored after the tuning it judges. The acceptance set is time-held-back,
questions authored after a tuning change, the workshop cohort being one
source, and it runs from its own target outside the development gate, so
a violation shows as a target that ran rather than a broken promise. The
MUST floors read on the whole bank in the gate. Fixture-level gains are
confirmed at library level, which stays the held-out instrument.

### C.9 The SPEC section

Verdicts: A amend, B amend, C amend, D amend, E amend.

C, whose section it is, supplies the mechanics: the scorer parses its
thresholds from four literal sentences between two markers in §5.2.8, so
any reflow turns the gate red for a prose edit; "~40 queries" is parsed
by nothing and should be deleted, not renumbered, since a soft count
gates nothing. A: the stability thresholds were calibrated on the old
corpus and its sixty queries and must be re-derived before they gate the
new one. E: the total stays soft but a hard minimum per MUST cell belongs
in the specification, since R34's non-vacuity rides on the query count;
and a sentence stays in the specification if a gate reads it, moves
otherwise, with a ratchet asserting both ends of the move. B: three
sentences must be corrected in transit, not relocated: no single
attachment can cross both caps, since the page cap binds PDFs and the
character cap binds text and EPUB, so "together" needs two attachments
on one parent; annotations have no export path through the local API,
which exposes none; and formats outside the extraction dispatch are
failure controls by construction. D: the README promise of an answer in
a table on page 240 must be kept or reworded in the same pass.

**Verdict: AMEND.** A new §5.2.10 owns the fixture contract: the three
layers and the rule that the gate reads the export; the strata and a
pointer to §5.2.8's fidelity clause; the question record as the gate's
input contract, with closed vocabularies, the directional assertions,
and the primary-set bound; the run block; the invalidation table; and a
hard minimum question count per MUST cell. §5.2.8 keeps, verbatim
between its markers, only the sentences the scorer reads, and a change
to them moves the scorer's markers in the same commit with a test that
the text parses. "~40 queries" is deleted. The caps sentence is
corrected as B states, as a ruling to record. The stability thresholds
are marked as calibrated on the superseded corpus and re-derived on the
new one before they gate. Everything else moves to its owner with a
ratchet, and README's Menagerie paragraph is reconciled.

### C.10 The pathology ledger

Verdicts: A ratify, B ratify, C ratify, D amend, E amend.

Three ratify. B enlarges the seed with four rows found on the live group
this morning: the windows-1252 charset on the wikitext attachments, two
transclusion skeletons where whole works were expected, the uncapped
forced reindex, and file routes answering 404 for every group attachment,
so the group is not a distributable artifact. D adds a metadata section:
78 spellings of the language field, half the records with none, dates
parsed out of range, 584 full-text rows at version zero, 446 bookmarks
with no bytes; language first, since it selects the embedding lane. E
sets two conditions: each row names the assertion or question that
consumes it and is shown red once against a build broken on purpose,
and the external campaign is a ticket with an owner and a dated cutoff,
or "before" becomes "instead of". A: saturation is counted over the
external campaign alone.

**Verdict: RATIFY, with conditions.** The ledger is seeded from this
repository's findings and from the census's measured metadata defects,
each row naming its consuming assertion or question and demonstrated
red once. The external campaign is filed as a ticket with an owner and a
dated cutoff, and the saturation rule counts it alone.

### C.11 What the panel found missing

Four seats raised gaps the ten points do not cover. They become items
D.12 to D.16.

- **Discrimination and occupancy** (A, E). Collection size and k are
  derived from authoring economics, not from a discrimination target;
  at k equal to ten over forty items the system returns a quarter of
  the collection per query. The scorecard as drawn has near a hundred
  cells over a soft 200 questions, so the modal cell holds one or two.
  The contract must fix a minimum occupancy, declare a MUST cell below
  it not-evaluated under R7's set-aside, and separate readings that are
  gates from readings that are comparisons, which need a paired test
  and an effect size.
- **A red state for the bank** (E, C). Nothing requires the bank to be
  shown capable of failing. It is accepted only after each MUST cell
  has gone red on a deliberately broken build: keyword-only fallback, an
  English-only embedder, a cut character cap, entry collapse disabled,
  a shuffled ranker; and each R33 probe shape red on the arm that targets
  it. The golden target must exist in the Makefile, which today has none,
  and its first committed bundle is a red one.
- **Re-pin cost and the export path** (C, E, B). The export can only be
  produced on the author's machine through the plugin, every lifecycle
  event fires a re-pin, and nothing states who re-resolves 200 spans or
  what a half-authored bank buys. The quoted-span locator of C.7 is the
  mechanical half; an hours budget is the other. And the export carries
  parents and file attachments only: no child note, no annotation, no
  bookmark, no trashed item, while the notes facet and the annotation
  ruling assume them; annotations need the web API, since the local one
  exposes none.
- **The queries were never censused** (D). Every marginal measured is a
  marginal of documents. Real searches are short, often known-item,
  often unaccented. The document census has a twin nobody ran: sample
  real searches, record length, language, diacritic state and whether
  the searcher knew the target.
- **Governance and licence of a public fixture** (D). The group is
  linked from README and a workshop puts twenty people in it; nothing
  states membership rights, what a participant's edit does to a pinned
  export, or the bank's own licence when it quotes CC BY-SA spans.

## Part D. For ratification, as amended by the panel

1. Two sampled strata and a non-sampled appendix of scale surrogates
   committed as generators, per C.1; the core carries the census's
   defect marginals; no unweighted aggregate over core plus reserve.
2. The lane matrix per C.2: one row per language, an undeclared column,
   binding cells cited from R7 and R29, counts printed per cell,
   minimum counts per MUST cell fixed before authoring.
3. The animal theme per C.3: a clustered core, the theme an axis for the
   ambiguity families and the workshop, mechanism governing the reserve,
   anchors keeping ruling 5's shapes.
4. Wikipedia per C.4: script and ranking probes and beasts only, raw
   wikitext pinned with explicit charset, same-subject never translation,
   SHOULD extraction not-measured until an archive PDF lands.
5. Grades per C.5: judged grade 2 bound to a selected attachment,
   directional assertions instead of a neutral grade, primary set within
   k, rank and reciprocal rank reported, schema v2.
6. No-answer per C.6: three gated forms and one reported probe; semantic
   abstention as a §5.3 experiment with a ticket and an owner.
7. The answer key per C.7: relevance judged on the document, reachability
   computed on the export, expected-miss questions kept, the export
   produced at the settings it records with the forced reindex at stock
   limits by default, quoted-span locators.
8. The development and acceptance split rejected as drafted and replaced
   by provenance and a time-held-back set on its own target, per C.8.
9. §5.2.10 per C.9, with the scorer's four sentences protected, the
   thresholds re-derived on the new corpus, the caps sentence corrected,
   and README reconciled.
10. The pathology ledger per C.10, each row consumed and shown red once,
    the external campaign ticketed.
11. R29 widened so that Vietnamese queries against English and French
    content bind, or the asymmetry stated as a deliberate limit with its
    reason.
12. Minimum cell occupancy in the contract; a MUST cell below it is
    not-evaluated; gate readings and comparison readings named apart.
13. The bank is accepted only after a red state per MUST cell on broken
    builds, and the golden target exists with a red first bundle.
14. A re-pin owner and hours budget; the export path extended to notes,
    annotations, bookmarks and trashed items, naming the API each needs.
15. A query census beside the document census.
16. Governance and licence terms for the public group and the bank.

Two defects found on the live group during the panel are not ratification
items but work owed to child 0632 before the export closes: the charset on
the three wikitext attachments, and the forced reindex ignoring the stock
limits it records.

## Part E. Rulings of 2026-09-06

The author ruled on Part D point by point; the ledger entry of 2026-09-06
in `DECISIONS.md` is the record. In brief: 1 ratified as amended; 2 the
language requirement was ill-formed and the lane matrix is set aside for
the chain question → document → answer paragraph, with multilingual
documents and legacy encodings as corpus dimensions; 3 the animal theme is
dropped, the topics are the author's library's own; 4 Wikipedia is an
ordinary admitted source, relations labelled truthfully; 6 no-answer
questions carry an empty pinned set and several are expected-miss; 7 an
answer is a paragraph in a page in a file, and a perfect reply carries the
full citation chain down to the printed page number and the byline of a
compound document's part; 9 §5.2.10 stands with no prose guards; 10 an
agent builds library and bank in one shot and review rounds converge it,
with checklists and no automatic guard. Points 5 and 8 wait on a clearer
explanation. Part D's items 12 and 13 become review-round checks under
ruling 10; item 11, Vietnamese as a query language, is subsumed by ruling 2.

Second round, same day: 2 confirmed; 4 the format mix follows the census
(PDF 56,9 %, HTML 33,0 %, other 9,2 %); 5 a reply scores win, near-win or
miss on the rank of the answer paragraph and the completeness of its
citation chain, the other-language twin being a near-win; 8 the workshop
is the artisan's own and holds no participants, and the held-out
instrument becomes a fifth deliverable, an on-the-fly question generator
over the author's real library, ticketed separately. All ten points are
now ruled; the one-shot build of ruling 10 starts.
