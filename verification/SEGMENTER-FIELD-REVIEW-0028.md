# SEGMENTER FIELD REVIEW — prior art for seg/1 (ticket 0028)

## Intro

This document surveys the state of the art for seg/1's actual problem:
detecting structural units (dictionary headwords, book chapters,
proceedings/collection chapters) from **flat, already-extracted plain
text** — hard-wrapped, no font size, no bounding boxes, no PDF outline.
That constraint is not incidental: ticket 0028's own 2026-08-30 checkpoint
established that the local API exposes only `/fulltext` flat text, so
whatever the field does with PDF layout (GROBID, Docling, LayoutParser,
…) is foreclosed here regardless of tool quality.

This is a different survey from `verification/FIELD-REVIEW.md`, which
inventories competing Zotero retrieval tools. This one inventories
segmentation *techniques and datasets*, spanning classic text-segmentation
literature, book-structure-extraction competitions, chapterizer tools, and
citation-parsing tools whose text-only feature sets are separable from the
layout signal they usually run on. It owns no design number, no
requirement, and no threshold — where a finding bears on seg/1's design,
it is a candidate for a `DECISIONS.md` ruling, not an edit made here.

**Provenance is visible**, per the discipline `FIELD-REVIEW.md` set: a
source marked "read" was actually fetched and read (by the researching
agent); "secondary" or "(secondary/unverified)" means only a search
summary or a citing source was seen, not the primary text. A negative
result ("no source found for X") is reported as a negative result, not
silence — three of the most load-bearing findings below are exactly that
shape.

**Dates are attached.** Research conducted 2026-09-01 via two parallel
web-search passes; sources carry their own publication dates where known.
The field moves — MUDIDI (arXiv 2606.09435) is a 2026 paper, current as of
this writing but unread beyond its abstract.

---

## 1. Heading/entry candidate detection from flat text

**Chapter Captor** (Pethe, Kim & Skiena, EMNLP 2020,
[arxiv 2011.04163](https://arxiv.org/abs/2011.04163); code:
`sbu-dsl/chapter-captor`) — read (abstract + search summaries), not the
full PDF. The closest published analogue to seg/1: a 9,126-novel Project
Gutenberg dataset for book segmentation from plain text, built with a
**hybrid neural + rule-based header recognizer** (F1 0.77 finding heading
lines) and a separate, much harder task of predicting chapter breaks with
headings *stripped* (F1 0.453, cut-based and neural methods). This
validates seg/1's two-stage shape — pattern-based candidate detection,
then a separate accept/reject decision — as the field's own working
architecture, and its own numbers say the pattern-detection half is doing
most of the real work: content-only statistical segmentation is markedly
weaker than heading-pattern recognition, even with neural methods thrown
at it.

**chapterize** (`JonathanReeve/chapterize`, GitHub) — read. A pure
regex splitter for Gutenberg-style novels ("Chapter N" / numeral /
spelled-out forms), no acceptance-confidence layer, no TOC, no byline
handling. A strict subset of what seg/1's numbering/case-shape stage
already does. Language ports (`fi-chapterize`, `It-Chapterize`) add
nothing beyond locale regex variants.

**Calibre**'s `ebook-convert` chapter-detection heuristic (read,
documentation) wraps candidate headings via pattern/format heuristics but
for plain `.txt` input its own recommended path is user-inserted markers —
it largely declines the genuinely-unstructured-text case rather than
solving it.

## 2. Topic/cohesion segmentation (TextTiling family) — orthogonal, not a substitute

TextTiling (Hearst 1997), C99 (Choi 2000), TopicTiling (Riedl & Biemann,
ACL 2012 SRW), GraphSeg (Glavaš et al., *SEM 2016) — all secondary
(search-summary level). All answer "where does subject matter drift" via
lexical cohesion or embedding similarity between prose windows — a
different question from "where is a structural break marked by a
formatted heading line." None is heading-aware; none has documented
precedent for hybridizing with a regex/pattern candidate front end. They
are speculative as a secondary corroborating signal (e.g., confirming a
weak heading candidate sits at a cohesion valley) but no source describes
that combination — **not recommended for the current scope.**

## 3. Neural/supervised segmentation — domain mismatch, mostly GPU-scale

Wiki-727K (Koshorek et al., NAACL 2018, [arxiv 1803.09337](https://arxiv.org/abs/1803.09337),
read) trains on Wikipedia articles auto-labeled from their own clean TOC
markup; Cross-Segment BERT (Lukasik et al., EMNLP 2020, secondary) and
SECTOR (Arnold et al., TACL 2019, secondary) are the same family.
All three target markup-clean source and topic/TOC-shaped boundaries, not
noisy hard-wrapped flat text with irregular entry sizes — adopting one
would carry a real domain-adaptation cost, not a drop-in gain, and the
larger models are GPU-oriented by default. **Not recommended for the
current scope**; flagged only as a future option if precision remains
short after the text-pattern techniques below are exhausted.

## 4. The median/MAD regularity filter — no precedent found (negative result)

Neither research pass found the "median gap / MAD over candidate
spacing" technique — seg/1's acceptance filter for the dictionary case —
documented anywhere in text-segmentation, OCR post-processing, or
lexicographic-digitization literature, under any name. The nearest
generic analogues are (a) a periodicity-detection statistic in general
sequence-mining work ([arxiv 1507.01685](https://arxiv.org/pdf/1507.01685),
secondary/unverified) confirming median/MAD is an established *general*
statistical tool, and (b) a patent on page-construct detection via
"sequential regularities" ([US9672195](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9672195),
secondary/unverified) applying the same "regularity implies structural
role" logic to recurring per-page zones (headers/footers), not to
within-document entry spacing.

Read plainly: **this looks like an unpublished, project-specific
combination of a known general statistic with this specific problem, not
an adopted or validated technique.** That is not a defect — ticket 0028's
own diagnosis (2026-08-31 note) already treats the dictionary's
near-constant entry size as the load-bearing assumption and explicitly
expects it not to transfer to irregular-length book chapters. This review
corroborates that diagnosis from the literature side: nothing published
validates the MAD filter for irregular units, and X5's dictionary-scoped
ground truth (SPEC.md §5.3) is the right — and currently the only —
test of it. **Do not extend the MAD acceptance filter to the book/
proceedings primary class without separate validation**, consistent with
the ticket's existing scope note.

## 5. TOC alignment — the field has a defined task and public data for this

**ICDAR Book Structure Extraction competitions** (2009, 2011, 2013;
Doucet et al., read via search summaries and the fetched 2013 paper) are
a direct match: given an OCR'd/scanned book, produce a hyperlinked TOC
into the body, evaluated on 527 (2009) / 513 (2011) hand-annotated public
books.

**"Table of Contents Recognition and Extraction for Heterogeneous Book
Documents"** (Chen, Giles et al., ICDAR 2013,
[PDF](https://clgiles.ist.psu.edu/pubs/ICDAR2013-ToC.pdf), read) matches
TOC entries into body text via fuzzy string matching on normalized
titles, a page-number-as-prior, and (where available) font/indentation —
the last foreclosed here, the first two directly usable on flat text.
Load-bearing detail: TOC entries are an **ordered, monotonic sequence**,
which lets a matcher search forward-only from the last confirmed anchor
rather than scanning the whole document per entry — this both narrows the
search space and rejects out-of-order false positives for free.

This is the single most actionable finding for the book/proceedings
primary class: it upgrades the TOC from ticket 0028's 2026-08-31 note
("a table of contents … to validate the cut set against rather than only
scoring it") to an **active search-space constraint**, not just a
post-hoc validator.

## 6. Author-byline detection — solved for flat text, just not by seg/1 yet

**ParsCit** ([parscit.comp.nus.edu.sg](https://parscit.comp.nus.edu.sg/),
ACL L08-1291, read via search summaries) is the closest fit: explicitly
designed for **plain text**, no PDF layout — a semi-Markov CRF over
token-level lexical features (capitalization run, punctuation, name-form
dictionaries, sentence position, absence of a verb) to label header lines
including the author line. This is direct, citable proof that byline
detection from flat text (no bounding boxes) is an established, working
technique, not a research gap.

GROBID and CERMINE solve the same sub-problem but their published feature
sets mix layout (font, bounding box, whitespace geometry) with lexical
features inseparably in the public write-ups found; their *lexical*
feature ideas (short line, title-case tokens, no verb, position
immediately under a heading) are reusable in principle but were not
independently confirmed layout-free the way ParsCit's are.

No source evaluates byline presence as a **chapter-boundary confirmation
signal** (all three tools use it only for their own header-extraction
task) — using it as an accept-signal for seg/1's heading candidates, as
the ticket's 2026-08-31 note proposes, would be a novel application of an
established sub-technique, not an import of a published one.

## 7. Layout-based tools (GROBID, CERMINE, PDFAct, LayoutParser, Docling, Marker, Nougat, pdf-struct) — for contrast only

Briefly, since ticket 0028's own checkpoint already forecloses this path
(the local API never exposes structured extraction, independent of
whether upstream #6012 merges): all of these use font-size jumps,
whitespace geometry, or page-image bounding boxes to find headings and
bylines, and `pdf-struct`'s reported paragraph-boundary F1 (0.953 with
layout vs. 0.739 for plain `pdftotext`) quantifies roughly what layout
buys when available. None of it is recoverable from flat text; this
confirms rather than changes the existing design constraint.

## 8. Dictionary/lexicographic segmentation

**GROBID-Dictionaries** (`MedKhem/grobid-dictionaries`; Ortiz Suárez on
OCR-quality impact; a 2025 arXiv paper applying vision-enabled LLMs to
Estonian-German dictionaries; MUDIDI, arXiv 2606.09435, 2026, abstract
only) — all read via search summaries. Cascading CRF or LLM models label
entry/headword boundaries using typographic and lexical cues (bold
headword, POS-abbreviation pattern, sense-number markers). **None of the
sources found use entry-length regularity or spacing periodicity as a
signal** — reinforcing finding 4: seg/1's MAD filter is not a documented
lexicographic technique, just one that happens to fit this corpus's
near-uniform entry size.

## 9. Multilingual robustness — the corpus is not English-only

Prompted by the author's 2026-09-01 acceptance-test statement (logged on
ticket 0028): the acceptance corpus is his own Zotero library, which
includes French sources and a French thesis, not just English technical
and reference works. A third research pass checked whether the building
blocks above transfer.

**Title-Case detection does not transfer to French, and the failure is
structural, not a tuning gap.** French headings normally follow sentence
case (only the first word and proper nouns capitalized), not English-style
Title Case — style guides disagree on the exact rule, but agree there is
no French analogue to "capitalize every major word." Run against French
text, seg/1's case-shape heuristic will mostly find nothing, since French
headings look like ordinary sentence-initial-cap prose. ALL CAPS partially
transfers (used for some heading levels in French academic publishing,
e.g. thesis chapter titles) but no source confirms this as a stable,
corpus-general rule rather than a per-publisher convention —
(secondary/unverified), needs empirical calibration rather than a
hardcoded assumption.

**Unicode segmentation (UAX #29, `Intl.Segmenter`) is a cleanup layer, not
a heading detector, and is only partly script-agnostic.** Read directly
against the spec: UAX #29 states plainly that "it is not possible to
provide a uniform set of rules that resolves all issues across
languages." Word/grapheme boundaries need no special tailoring for
space-delimited Latin-script languages — French included — so
`Intl.Segmenter` at word granularity genuinely generalizes there, backing
up the ticket's 2026-08-31 note that it is "script-agnostic." *Sentence*
boundaries do not generalize the same way: they depend on a locale's
abbreviation list (French "M.", "Mme", "Dr" behave like, but are distinct
from, English "Mr.", "Dr."), which is exactly why `Intl.Segmenter`/ICU
BreakIterator take a locale parameter. Either way, a heading is typically
not a well-formed sentence, so this segmentation finds prose seams, not
heading starts — it belongs under a heading detector, not in place of one.

**TOC fuzzy-matching needs an explicit accent-fold step it does not yet
have.** Uncontested standard IR practice (Manning, Raghavan & Schütze,
*Introduction to Information Retrieval*, Stanford NLP, read directly):
NFKD decomposition followed by stripping combining marks, paired with
case-folding, before any edit-distance or N-gram comparison — otherwise
accented text (French diacritics, and OCR accent-drift on any language)
produces spurious distance penalties against clean TOC-entry strings.
Cheap, standard, and currently absent from finding 5's ICDAR-derived
technique as described here.

**FinTOC** (FNP workshop shared task, ACL Anthology, 2020–2022, read at
abstract level) is the closest published multilingual precedent for the
book/proceedings TOC-alignment finding above: explicit English/French
(and from 2022, Spanish) TOC/title extraction from financial documents.
One system (Taxy.io, FinTOC-2020) reports a single transfer-learning model
handling English and French title detection via character-level features
rather than language-specific regex, evidence that a script-general
front end is achievable for this task family — but the full
methodology, and any measured English-vs-French performance gap, could
not be confirmed from the abstract and needs a direct read of the paper
before it changes seg/1's design.

## 10. A third structural class: irregular, signed, multi-author encyclopedia entries

One of the acceptance-test documents (author's statement, 2026-09-01,
ticket 0028 log — no specific title recorded here, this is a public
repository) is a signed, multi-author encyclopedia despite carrying
"dictionary" in its conventional name: entries of widely varying length,
the same shape ticket 0028's 2026-08-31 note already worried the MAD
regularity filter would misfire on for book chapters. This is a
structural class the current book-vs-dictionary binary does not name.

Two precedents, one in each language:

**EB1911 on Wikisource** (English, read) confirms the exact problem —
contributor initials appear bracketed at each article's end,
cross-referenced to a per-volume table of contributors, several articles
per scanned page — but the project's actual solution was manual curation,
not an algorithm. An existence proof of the problem, not a technique.

**ARTFL's *Encyclopédie*** (Diderot & d'Alembert, French, 74,000
articles by 130+ contributors, irregular entry lengths, read directly)
is the strongest match: French-language, the exact "irregular signed
multi-author entries" shape, and a published lesson directly applicable
to seg/1 — "light, automatically generated tagging is preferable to
extensive manual mark-up," built from the corpus's own clear typographic
conventions (a discipline seg/1 already follows for the dictionary case,
just not yet stated for this one). Its modern NER companion (EDDA corpus,
[arXiv 2506.02872](https://arxiv.org/pdf/2506.02872)) does span
classification on top of an *already-segmented* version of the corpus and
does not itself address entry-boundary detection — the segmentation
problem was solved once, upstream, and not published as a reusable
method.

One more lead, unconfirmed: "Logical segmentation for article extraction
in digitized old encyclopedias" ([ACM DL,
10.1145/2361354.2361383](https://dl.acm.org/doi/10.1145/2361354.2361383))
is on-topic by title but returned 403 on fetch — worth obtaining through
institutional access before relying on it further.

---

## Mapping to the author's acceptance-test corpus

The 2026-09-01 acceptance test names document classes this review can
place directly against the findings above, none of them exercised by
X5's single 44,9 MB dictionary sample. No specific titles are recorded
here — this is a public repository, and the acceptance test names actual
holdings of the author's private Zotero library; the ticket 0028 log
carries the author's original statement in his own words, not this
document.

- **A signed, multi-author encyclopedia** — the irregular-signed-entry
  class, §10. Neither the dictionary MAD filter nor the plain book-chapter
  design is validated for it; ARTFL is the nearest technique precedent,
  and it is French besides.
- **An edited-collection handbook** — the byline + TOC class the
  2026-08-31 note already named (findings 3–4), now with a concrete
  acceptance-test document to validate against instead of a hypothetical.
- **A long, heavily numbered technical report** — strong front-matter TOC;
  closest in shape to the ICDAR/FinTOC TOC-alignment task family (§5, §9),
  and likely to exercise the numbering-pattern candidate detector hardest,
  since this class's section numbering runs deep (e.g. "7.4.2.1").
- **A single-author thesis** — its own TOC and chapter structure; no
  byline signal needed (only one author), a clean test of TOC-alignment
  alone, and — per the author's own note — likely to be the
  French-language test case that exercises §9's Title-Case finding
  directly.

None of these four is covered by the exit criteria ticket 0028 currently
carries (the 44,9 MB dictionary fixture, confidence, and the chunker
identity string). This review does not resolve that gap — it names it, so
whoever writes the acceptance-test ruling has the evidence assembled
rather than starting from the abstract "books, proceedings, dicts,
handbooks, encyclopedia" list alone.

---

## Most actionable findings

1. **Keep the numbering/case-shape candidate front end as the strong
   half of the problem.** Chapter Captor's own numbers (0.77 heading-F1
   vs. 0.453 content-only-F1) say pattern detection, not statistical or
   neural content analysis, is where the field's accuracy actually comes
   from — this is a validation of seg/1's existing architecture, not a
   call to change it.

2. **The MAD regularity filter has no literature precedent and should
   stay scoped to the dictionary case.** This is a negative result, not
   an oversight in the search — it corroborates, from the outside, the
   scope limit the ticket's own 2026-08-31 note already argued for on
   internal grounds (near-constant entry size vs. wildly unequal chapter
   lengths).

3. **TOC alignment can do more than validate — it can constrain the
   search.** The ICDAR 2013 approach (fuzzy title match + page-number
   prior + forward-only search over the TOC's own monotonic order) is
   directly portable to flat text and turns the TOC into an active
   anchor sequence, closing the "validate only" limitation the ticket
   log flagged for the book/proceedings primary class.

4. **Byline detection is layout-free and citable (ParsCit), but using it
   as a chapter-boundary accept-signal is new, not adopted.** Worth
   building, but state it as this project's own extension rather than an
   imported, validated technique.

5. **No open tool combines heading-regex + TOC alignment + byline
   detection for edited-collection segmentation on flat text.** Seg/1's
   book/proceedings mode, once built, fills a real gap rather than
   duplicating something adoptable off the shelf — and the neural/
   embedding segmentation families (§§2–3) are not worth chasing for this
   scope; they solve a different problem (topic drift, not structural
   heading detection) and carry a domain-adaptation and compute cost this
   design has no measured need for.

6. **The Title-Case candidate signal needs a French-aware gate, not just a
   parameter tweak.** It is close to non-signal on French headings, which
   follow sentence case; running it unguarded on French text will silently
   suppress real heading candidates rather than merely miss some. Cheap
   and uncontested to fix (accent-fold + case-fold before any string
   comparison, per §9); whether ALL-CAPS reliably substitutes for French
   needs corpus-specific calibration, not an assumption.

7. **Signed, irregular-length encyclopedia entries are a third
   structural class, not a dictionary or a book** — one of the
   acceptance-test documents is exactly this shape (§10, no title
   recorded). Irregular, signed, multi-author entries break the MAD
   filter's regularity assumption the same way irregular book chapters
   do, for a different underlying reason (varying author length, not
   varying subject depth). ARTFL's *Encyclopédie* is the nearest
   published precedent and is worth reading in full before this class is
   designed for.

8. **A long numbered technical report and a single-author thesis are the
   concrete acceptance-test cases the TOC-alignment finding (3) and
   FinTOC precedent (§9) should be checked against first** — deep numbered
   sections and a strong front-matter TOC in one case, a monograph with no
   byline signal in the other, and the thesis is the first real
   French-language test of this design.

## Scope note

Findings 3, 4, 6, 7 and 8 describe capability seg/1's current exit
criteria do not name. Findings 3 and 4 (TOC alignment, byline detection)
belong to the book/proceedings primary class ruled 2026-08-31; finding 7
(the encyclopedia class) and the multilingual findings in §9 surface from
the author's broader 2026-09-01 acceptance-test statement (logged on
ticket 0028), which itself has not yet been reconciled with that ruling
or with X5's single-corpus decision rule. Per this repo's chain
discipline, extending seg/1's design to use any of them is a `SPEC.md`
§5.2.2 change and therefore a `DECISIONS.md` ruling first — not made
here. This review, together with the ticket 0028 log entry recording the
acceptance test verbatim, is the evidence such a ruling would cite. One
narrower exception: accent/case-folding before TOC fuzzy-matching (part
of finding 6) is uncontested standard practice with no design trade-off
attached, and could reasonably ship as an implementation detail inside
whatever TOC-alignment work a ruling authorizes, without needing its own
separate ruling.
