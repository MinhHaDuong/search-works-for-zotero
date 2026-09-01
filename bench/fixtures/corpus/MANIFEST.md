# Golden fixture corpus — document assembly

Ticket 0029. This directory holds the *documents* half of the fixture
corpus: plain text, page-delimited where the source has real pagination
(form-feed `\f` between pages, matching `pdftotext`'s own convention; a
DOCX source has none, so it's committed as one page — see "Formats and
extraction" below), with per-document provenance and licensing recorded in
`manifest.json`. It does not yet hold the query set, the Zotero-free
index-build harness, or the golden-gate wiring — see "What remains" below.

## Selection method

Every document here is genuinely public domain or explicitly
author-authorized — never merely openly licensed. Three independent bases
were used, and each document's `manifest.json` entry states which:

- **Age.** Published before 1931, which is the current (2026) US 95-year
  bright-line: anything published in 1930 or earlier is unconditionally
  public domain in the US regardless of the author's death date. Six
  documents below clear this comfortably (1622–1919), and each author's
  death year is also recorded so the entry is clear under a life+70 reading
  too. One item (Ramsey) needs life+70 specifically rather than the
  bright-line — see its own entry.
- **Statutory exclusion.** Vietnam's Law on Intellectual Property (No.
  50/2005/QH11, as amended), Article 15.2, excludes legal normative
  documents (văn bản quy phạm pháp luật), administrative documents, and
  their official translations from copyright protection outright, with no
  age requirement. A government Decision or Circular is such a document
  regardless of its year, which is why the Vietnamese items below are
  2010–2017 rather than pre-1931. Unaddressed: whether the issuing portal's
  own site terms of use could still restrict redistribution of the file as
  a file, separately from the text's copyright status, and whether a scan's
  non-text elements (national emblem, e-signature certificate block) fall
  under a different, non-copyright regime. Neither is a copyright question,
  so Article 15.2 doesn't settle either — flagged rather than resolved.
- **Author-owned, direct authorization.** One document (the author's own
  Habilitation) is not public domain at all — Minh Ha-Duong holds its
  copyright as author, and he is this corpus's own commissioning author. He
  authorized its inclusion directly in the session that assembled this
  corpus (2026-09-01). Recorded as a distinct basis, not folded into the
  other two: it rests on the rightsholder's permission, not on expired or
  excluded copyright, and that distinction matters if this corpus is ever
  redistributed by someone who isn't him.

The library queried is the author's own (Zotero userID 95318, 7 541
top-level items, publicly readable without a key) — "preferably from my
lib" per the ticket's directive. Twelve of the thirteen documents below
were found there; the thirteenth (the Habilitation) has no Zotero
attachment and was fetched from the author's own homepage instead, at his
direction.

**A scan's own container can carry a separate, later copyright even when
the underlying text is old enough to be free of one** — the risk named
directly by the author mid-assembly ("recent reeditions of classic books,
e.g. Dover still has rights"). Checked for every document below by reading
each PDF's embedded metadata and front matter for a reprint publisher,
modern date, or "reprint" wording, not just trusting the original work's
publication year. This caught one real case: **Soddy 1926**, originally
included in this corpus's first pass, was removed after its embedded
metadata read "George Allen & Unwin Ltd., London. 1983 reprint" — the
committed file was a scan of a 1983 reissue, not the 1926 original, and no
verified original-edition scan was found in the time available. See "What
remains" for the open slot.

## Formats and extraction

Two source formats: PDF (the default) and DOCX (two Vietnamese circulars,
`attachment_format: "docx"` in `DOCS`). DOCX is extracted with `pandoc -t
plain` directly, committed as a single page — `soffice --headless
--convert-to pdf` was tried first, to reuse the PDF page-splitting
pipeline, but failed outright ("source file could not be loaded") on one
of the two files while pandoc extracted both cleanly; and a docx has no
fixed print pagination to preserve in the first place, so treating it as
one page is honest rather than a fallback compromise.

## What's here

| id | language | tier | year | pages | chars | facet |
|---|---|---|---|---|---|---|
| cournot-1838-recherches | fr | MUST | 1838 | 230 | 250 144 | core |
| walras-1900-elements | fr | MUST | 1900 | 270 | 955 830 | core |
| porte-1770-science-des-negocians | fr | MUST | 1770 | 788 | 842 279 | core |
| depitre-1908-oeuvres-cournot | fr | MUST | 1908 | 10 | 23 077 | core |
| ha-duong-2005-modeles-de-precaution-hdr | fr | MUST | 2005 | 180 | 466 312 | core |
| malynes-1622-lex-mercatoria-extrait | en | MUST | 1622 | 45 | 110 725 | core |
| ramsey-1926-truth-and-probability | en | MUST | 1926 | 41 | 109 131 | core |
| neurath-1919-durch-die-kriegswirtschaft | de | SHOULD | 1919 | 251 | 887 724 | core |
| minkowski-1896-geometrie-der-zahlen | de | SHOULD | 1896 | 274 | 571 192 | core |
| vn-decision-11-2017-qdttg-solar-fit | vi | MUST | 2017 | 10 | 17 720 | core |
| vn-circular-25-2016-ttbct-transmission | vi | MUST | 2016 | 106 | 232 451 | core |
| vn-circular-41-2010-btnmt-emissions | vi | MUST | 2010 | 1 | 16 897 | core |
| vn-circular-42-2010-btnmt-emissions | vi | MUST | 2010 | 1 | 43 333 | core |

Total: 2 207 pages, 4 526 815 chars, 5,2 MB as committed plain text.

## Variety dimensions, and what each addition buys

Six documents in the first assembly pass were thin for a fixture meant to
back roughly 40 pinned queries — all treatises on nearly one subject
(value theory) in EN/FR, one in DE. This pass targeted variety on several
independent axes rather than just adding more of the same shape:

- **Topic/subject.** Alongside the value-theory pair (Cournot, Walras):
  a bookkeeping/accounting manual (Porte, 1770), commercial law (Malynes,
  1622), philosophy of probability (Ramsey, 1926), historiography of
  Cournot (Depitre, 1908), pure mathematics with no economics content at
  all (Minkowski — deliberately off-topic, to test that an unrelated
  subject doesn't falsely dominate an economics query), and the author's
  own work on imprecise probabilities (the Habilitation).
- **Vietnamese agency/topic spread.** The first pass had two BCT
  (Ministry of Industry and Trade) energy circulars. This pass adds two
  MONRE (Ministry of Natural Resources and Environment) circulars on
  industrial-emissions technical standards — a different ministry and a
  different topic (environment, not energy-market regulation), closer to
  the repo's own climate/environment domain.
- **Item type / genre.** The first pass was all `book`-type Zotero items
  (plus the two VI legal instruments). This pass adds `journalArticle`
  (Depitre) and excerpts of larger works (Malynes, Ramsey), plus two
  `document`-type DOCX circulars.
- **Document length.** Porte (788 pages) is now the longest single
  document in the corpus by a wide margin, alongside genuinely short items
  (the two MONRE circulars at 1 page each in this pipeline's convention,
  Depitre at 10). The length spread runs from single digits to nearly 800.
- **Cross-lingual anchor**, still just the one pair (Decision 11/2017's
  official VN/EN bilingual text) — not expanded this pass; see "What
  remains".

**Considered and rejected: an IPCC report.** Checked the IPCC's own
copyright/permissions notice directly (`ipcc.ch/copyright`, via search
since the page 403s to a plain fetch): it authorizes free, no-permission
reproduction of "limited numbers of figures **or short excerpts**" for
personal, non-commercial use with attribution — not full reports or full
chapters. Even granting that this corpus's use is non-commercial (it is),
committing a full Summary for Policymakers would exceed what that blanket
permission actually covers; it would need explicit written permission from
the IPCC, which this session doesn't have. Noted for the record since it
was raised directly: if climate-topic PD content is wanted, the clean
equivalent is a **US government climate report** (a National Climate
Assessment, a NOAA report) — a work of the US government carries no
copyright at all, unlike an IGO's own copyrighted-with-permission report.
Not sourced this pass; flagged as an option for later.

## OCR and extraction quality, varies and is recorded per document

Cournot (BnF/Gallica), Depitre, and the Vietnamese Circular 25/2016 are
clean digital-native or well-OCR'd text. Walras (Google Books-era scan),
Porte and Minkowski (older Internet Archive OCR passes), and Neurath
(Fraktur title page, Antiqua body) are noisier — real scanner noise, not
hand-cleaned prose, arguably a feature for a fixture meant to stand in for
a real library. Malynes (1622 typography — long s, black-letter passages)
is the noisiest deliberately-kept item.

Decision 11/2017's body carried no text layer at all (only the
e-signature certificate block was digital-native); OCR'd page-by-page with
tesseract 5 + the `vie` traineddata (fetched to a scratch `tessdata` dir —
Vietnamese is not part of this machine's default tesseract install, only
`eng`/`fra`). `ocrmypdf --language vie` itself silently produced an empty
text layer on this signed PDF even with `--invalidate-digital-signatures`;
direct per-page `tesseract -l vie` on `pdftoppm`-rendered pages worked and
is what `extract_text()`'s automatic density-fallback path now does.

**One Zotero attachment turned out to be mislabeled entirely**, not just
noisy: Westergaard 1890 (`AAIDIRUF`, `contentType: application/pdf`) is
actually a raw JPEG (`ffd8ffe0` magic bytes) — a genuine image with a
wrong content-type tag, not a corrupt or unusual PDF. `fetch_attachment`'s
magic-byte check caught it; the item was dropped rather than building
one-off image-OCR handling for a single marginal page.

**Ramsey's text isn't a facsimile like the rest of this corpus.** The
committed file's own first page identifies itself as an "Electronic
Edition... adapted from Chapter VII" of Ramsey's 1931 posthumous
*Foundations of Mathematics* — a transcription prepared for open teaching
use, not a scan. Read as a faithful reproduction (no added commentary
found in it), but flagged as a different kind of source than everything
else here, which is all a scan of something.

**Reproducibility is contingent on the library not changing underneath
it.** Every Zotero-sourced document is fetched by item/attachment key from
the author's live library, not from a pinned snapshot; the Habilitation is
fetched from a live URL on the author's homepage. `manifest.json` records
`source_attachment_sha256` per document precisely so a future re-run that
fetches different bytes (a corrected scan, a replaced attachment) is
visible as a hash diff rather than a silent content change under the same
doc id — the hash detects drift, it does not prevent it.

## What remains (ticket 0029's other exit criteria — not attempted this pass)

- **The author's PhD thesis was requested alongside the Habilitation but
  is not yet included.** It has no Zotero attachment (bibliographic record
  only, like the Habilitation had). It's deposited on HAL
  (`https://theses.hal.science/tel-00003505`), confirmed via HAL's own API
  (`api.archives-ouvertes.fr`, which returns the correct record and an
  author-authorization license), but the HAL web frontend sits behind an
  Anubis proof-of-work anti-bot challenge that this session's plain HTTP
  tools (`curl`, `WebFetch`) cannot clear — every fetch of the actual PDF
  bytes returned the challenge page, not the file. Not attempted further;
  needs either a copy from the author directly, a mirror this session
  hasn't found, or a fetch from an environment that can solve the
  challenge.
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
    field, checked against all 7 541 items). Not "no PD candidate found" —
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
  call to make, not this session's. (The Habilitation shows the pattern —
  author-owned, directly authorized — that a notes-facet addition would
  likely also need.)
- **A monster document in a non-Latin script**, per the intersections
  requirement (a 15 000-page-class document, non-Latin script). Porte
  (788 pages) is now the longest document assembled, but is Latin-script;
  it does not satisfy the non-Latin-script half of the intersection. No
  non-Latin-script PD candidate of that scale turned up among the
  SHOULD-tier searches above.
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
page-addressable multilingual document set, now with genuine topical and
structural variety, an index harness can be pointed at once it exists.
