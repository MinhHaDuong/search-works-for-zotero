# Golden fixture corpus — document assembly

Ticket 0029. This directory holds the *documents* half of the fixture
corpus: plain text, page-delimited (form-feed `\f` between pages, matching
`pdftotext`'s own convention), with per-document provenance and licensing
recorded in `manifest.json`. It does not yet hold the query set, the
Zotero-free index-build harness, or the golden-gate wiring — see "What
remains" below.

## Selection method

Every document here is genuinely public domain, not merely openly licensed.
Two independent bases were used, and each document's `manifest.json` entry
states which:

- **Age.** Published before 1931, which is the current (2026) US 95-year
  bright-line: anything published in 1930 or earlier is unconditionally
  public domain in the US regardless of the author's death date. All five
  MUST/SHOULD-tier classics below clear this by a wide margin (1838–1926),
  and each author's death year is also recorded, so the entry is clear even
  under a life+70 reading — except Soddy (1877–1956), whose UK/EU term runs
  to 31 Dec 2026; flagged in his entry.
- **Statutory exclusion.** Vietnam's Law on Intellectual Property (No.
  50/2005/QH11, as amended), Article 15.2, excludes legal normative
  documents (văn bản quy phạm pháp luật), administrative documents, and
  their official translations from copyright protection outright, with no
  age requirement. A government Decision or Circular is such a document
  regardless of its year, which is why the Vietnamese items below are 2016
  and 2017 rather than pre-1931.

The library queried is the author's own (Zotero userID 95318, 7,541
top-level items, publicly readable without a key) — "preferably from my
lib" per the ticket's directive. Every document below was found there; no
external sourcing was needed for the languages it covers.

## What's here

| id | language | tier | year | pages | chars | facet |
|---|---|---|---|---|---|---|
| cournot-1838-recherches | fr | MUST | 1838 | 230 | 250 144 | core |
| walras-1900-elements | fr | MUST | 1900 | 270 | 955 830 | core |
| soddy-1926-wealth-virtual-wealth-and-debt | en | MUST | 1926 | 324 | 605 628 | core |
| neurath-1919-durch-die-kriegswirtschaft | de | SHOULD | 1919 | 251 | 887 724 | core |
| vn-decision-11-2017-qdttg-solar-fit | vi | MUST | 2017 | 10 | 17 720 | core |
| vn-circular-25-2016-ttbct-transmission | vi | MUST | 2016 | 106 | 232 452 | core |

Total: 1 191 pages, 2 949 498 chars, 3,1 MB as committed plain text.

**The two Vietnamese items are a real cross-lingual anchor.** Decision
11/2017 (solar FIT) exists in the library as an official bilingual pair —
the Vietnamese decision and its official English translation, both
published by the same government portal. The English text is kept
alongside as `cross-lingual-reference-en.txt`, *not* as an indexable
document — R29 forbids query-time translation — but as the tool a human (or
a later pinning pass) uses to verify that an EN/FR query's intended answer
really is this Vietnamese entry, before pinning it. This is the seed for
the golden gate's cross-lingual slice.

**OCR quality varies and is recorded per document, not hidden.** Cournot
(BnF/Gallica) and the Vietnamese Circular are clean digital-native or
well-OCR'd text. Walras (Google Books-era scan) and Neurath (Fraktur title
page) are noisier — real scanner noise, not hand-cleaned prose, which is
arguably a feature for a fixture meant to stand in for a real library.
Decision 11/2017's body carried no text layer at all (only the e-signature
certificate block was digital-native); it was OCR'd page-by-page with
tesseract 5 + the `vie` traineddata (fetched to a scratch `tessdata` dir for
this run — Vietnamese is not part of this machine's default tesseract
install, only `eng`/`fra`). `ocrmypdf --language vie` itself silently
produced an empty text layer on this signed PDF even with
`--invalidate-digital-signatures`; direct per-page `tesseract -l vie` on
`pdftoppm`-rendered pages worked and is what produced the committed text —
worth knowing if a later pass re-OCRs anything here.

**Reproducibility is contingent on the library not changing underneath
it.** Each document is fetched by Zotero item/attachment key from the
author's live library, not from a pinned snapshot. `manifest.json` records
`source_pdf_sha256` per document precisely so a future re-run that fetches
different bytes (a corrected scan, a replaced attachment) is visible as a
hash diff rather than a silent content change under the same doc id — the
hash detects drift, it does not prevent it.

## What remains (ticket 0029's other exit criteria — not attempted this pass)

- **SHOULD-tier languages set aside, with reasons**, per the ticket's own
  rule ("a SHOULD language whose corpus cannot be assembled is set aside
  with a stated reason"):
  - **Russian.** One old candidate exists in the library — Kantorovich
    1939, *Математические методы организации и планирования
    производства* — but Kantorovich died in 1986, so it is not public
    domain under any reading (life+70 runs to 2056); its 1930s date does
    not help since the US bright-line is about *publication*, not
    discovery, and even so 1939 already misses the pre-1931 cutoff. No
    other library candidate carries an explicit PD or CC0 marker. Set
    aside.
  - **Chinese, Spanish, Hindi.** Zero items in the library are tagged with
    these languages at all (`zh`/`es`/`hi` prefix match on the `language`
    field, checked against all 7,541 items). Not "no PD candidate found" —
    no candidate of any kind. Set aside; would need external sourcing.
  - **Arabic.** Four items tagged, all modern UNFCCC/CBD documents, none
    public domain. Set aside.
- **Group-library slice.** This Zotero account has zero group
  memberships (`/users/95318/groups` returns `[]`). The "group" facet
  cannot be sourced from "my lib" at all under the current account; it
  needs either a group the author joins or a synthetic fixture. Not
  attempted.
- **Notes facet.** Not attempted — a standalone note's public-domain status
  would rest on the author's own dedication of his own text, which is his
  call to make, not this session's.
- **A monster document in a non-Latin script**, per the intersections
  requirement (a 15 000-page-class document, non-Latin script). The
  Vietnamese Circular here (106 pages) is the longest document assembled
  this pass but is Latin-script (with diacritics); it does not satisfy the
  non-Latin-script half of the intersection. No non-Latin-script PD
  candidate of that scale turned up among the SHOULD-tier searches above.
- **Passage-length distribution pinning** (SPEC.md §5.2.8/§5.2.9,
  R32's rate-transfer clause). What's recorded per document here is
  page-count and per-page char-length quantiles (`manifest.json`), which is
  a proxy — the real passage-length distribution is a property of the
  *chunker's* output (ticket 0028's segmenter), not of raw pages, and that
  chunker doesn't exist yet.
- **~40 pinned queries with answer sets, re-pin procedure, R33's three
  probe shapes, R34's absolute reading** — none of this is built; it needs
  a working index over this corpus first (next bullet).
- **The Zotero-free index-build harness** (`bench/` driving
  `putItem`/`putPassage`/`putVector` directly, per `bench/issue30_build_index.mjs`'s
  existing pattern for a different fixture) — not built. Without it this
  corpus cannot yet be queried, so R33/R34/the golden gate stay unopened.
- **The golden gate wiring in `make check`** (ticket 0026) — blocked on the
  harness and the query set above.
- **No standing guard checks `manifest.json` against a fresh run of `DOCS`**,
  unlike `bench/models.json`/`registry.py`'s `check_models.py`. A hand-edit
  to `manifest.json`, or `DOCS` drifting from it, would go undetected —
  the repo's own "one statement per fact" convention names this as its most
  expensive recurring defect class. Worth a `check_corpus.py` once the
  corpus is queried by something that would actually notice a drift.

None of the unmet items block what this pass delivers: a real, licensed,
page-addressable multilingual document set an index harness can be pointed
at once it exists.
