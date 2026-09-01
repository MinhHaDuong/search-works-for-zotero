# Golden fixture corpus — document assembly

Ticket 0029. This directory holds the *documents* half of the fixture
corpus: plain text, page-delimited where the source has real pagination
(form-feed `\f` between pages), with per-document provenance and licensing
recorded in `manifest.json`. It does not yet hold the query set, the
Zotero-free index-build harness, or the golden-gate wiring — see "What
remains" below, which also names the next-phase design correction this
pass identified but didn't implement.

## No OCR by default (2026-09-01 policy)

Every document here has a real, pre-existing text layer, extracted as-is
with `pdftotext`/`pandoc` — nothing in this pipeline runs OCR unless a
document's `DOCS` entry sets `"allow_ocr": True` explicitly. There is
exactly one such document: **vn-decision-11-2017-qdttg-solar-fit**, whose
e-signed scan carries no text layer at all over its body (only the
certificate-stamp block is digital-native), so without OCR its committed
text would be almost entirely empty rather than merely sparse.

This is a direct, explicit author decision, and it reverses two mechanisms
built earlier in this same session: a whole-document OCR fallback for a
missing text layer, and a per-page rescue pass that re-OCR'd individual
failed-extraction pages inside otherwise-dense documents (confirmed real
on Porte 1770's page 72, sandwiched between flowing content). Both still
exist in `build_corpus.py` — gated behind `allow_ocr`, not deleted — but
neither runs by default. **A real corpus is a dirty corpus**: pages that
extracted sparse or empty stay exactly as `pdftotext` produced them.
Five documents below (Cournot, Walras, Porte, Minkowski, Neurath) have a
handful of such pages; that's disclosed here, not hidden or patched over.

## Selection method

Every document here is genuinely public domain, statutorily excluded from
copyright, openly licensed by the rightsholder, or directly author-owned —
never merely "looks old enough." Four independent bases were used, and
each document's `manifest.json` entry states which:

- **Age.** Published before 1931 (the current, 2026, US 95-year
  bright-line for unconditional public domain regardless of author's death
  date) or clear under life+70 from the author's death where publication
  came later or was posthumous. Nine documents below rest on this basis.
- **Statutory exclusion.** Vietnam's Law on Intellectual Property (No.
  50/2005/QH11, as amended), Article 15.2, excludes legal normative
  documents, administrative documents, and their official translations
  from copyright protection outright, with no age requirement. Four
  Vietnamese government Decisions/Circulars rest on this basis.
- **Open licence grant.** The UK Highway Code is Crown Copyright,
  published under the Open Government Licence v3.0 — a genuine licence the
  rightsholder grants (worldwide, royalty-free, perpetual, non-exclusive,
  covering commercial and non-commercial reuse, conditioned only on
  attribution), not an absence of copyright or a statutory carve-out.
  Confirmed directly against gov.uk's own OGL text, not inferred from the
  "government document" pattern the Vietnamese items follow, which rests
  on a different legal mechanism entirely.
- **Author-owned, direct authorization.** The author's own 2005
  Habilitation is not public domain at all — Minh Ha-Duong holds its
  copyright and is this corpus's own commissioning author; he authorized
  its inclusion directly in the session that assembled it.

The library queried is the author's own (Zotero userID 95318, 7 541
top-level items, publicly readable without a key) — "preferably from my
lib" per the ticket's directive. Twelve of the nineteen documents below
were found there; the other seven (the Habilitation, and six items added
on the author's direct request for further variety: a dictionary, a
poetry collection, a chapterless novel, two Nobel-laureate-connected
papers, and the Highway Code) were sourced externally, each checked for
provenance the same way as everything from the library.

**A scan's own container can carry a separate, later copyright even when
the underlying text is old enough to be free of one** — the risk the
author named directly mid-assembly ("recent reeditions of classic books,
e.g. Dover still has rights"). Checked for every document by reading each
PDF's embedded metadata and front matter for a reprint publisher, modern
date, or "reprint" wording, not just trusting the cited work's publication
year. This caught one real case: **Soddy 1926**, in this corpus's first
assembly pass, was removed after its embedded metadata read "George Allen
& Unwin Ltd., London. 1983 reprint" — a scan of a 1983 reissue, not the
original. Re-checking an independent archive.org upload of the same title
turned out to be the identical scan laundered through a re-upload, not a
cleaner source; no replacement was found.

## What's here

| id | language | tier | year | pages | chars | facet |
|---|---|---|---|---|---|---|
| cournot-1838-recherches | fr | MUST | 1838 | 230 | 250 144 | core |
| walras-1900-elements | fr | MUST | 1900 | 270 | 955 830 | core |
| porte-1770-science-des-negocians | fr | MUST | 1770 | 788 | 842 279 | core |
| depitre-1908-oeuvres-cournot | fr | MUST | 1908 | 10 | 23 077 | core |
| ha-duong-2005-modeles-de-precaution-hdr | fr | MUST | 2005 | 180 | 466 312 | core |
| baudelaire-1857-fleurs-du-mal | fr | MUST | 1857 | 262 | 123 441 | core |
| curie-1904-recherches-substances-radioactives | fr | MUST | 1904 | 176 | 264 239 | core |
| malynes-1622-lex-mercatoria-extrait | en | MUST | 1622 | 45 | 110 725 | core |
| ramsey-1926-truth-and-probability | en | MUST | 1926 | 41 | 109 131 | core |
| johnson-1785-dictionary | en | MUST | 1785 | 1 104 | 10 035 965 | core |
| stein-1925-making-of-americans | en | MUST | 1925 | 940 | 2 745 627 | core |
| einstein-minkowski-1920-principle-of-relativity | en | MUST | 1920 | 260 | 318 894 | core |
| uk-highway-code | en | MUST | (2026 fetch) | 30 | 255 697 | core |
| neurath-1919-durch-die-kriegswirtschaft | de | SHOULD | 1919 | 251 | 887 724 | core |
| minkowski-1896-geometrie-der-zahlen | de | SHOULD | 1896 | 274 | 571 192 | core |
| vn-decision-11-2017-qdttg-solar-fit | vi | MUST | 2017 | 10 | 17 720 | core |
| vn-circular-25-2016-ttbct-transmission | vi | MUST | 2016 | 106 | 232 451 | core |
| vn-circular-41-2010-btnmt-emissions | vi | MUST | 2010 | 1 | 16 897 | core |
| vn-circular-42-2010-btnmt-emissions | vi | MUST | 2010 | 1 | 43 333 | core |

Total: 19 documents, 4 979 pages, 18 270 678 chars, 18 MB as committed
plain text.

## Variety dimensions

- **Topic/subject.** Value theory (Cournot, Walras), bookkeeping (Porte),
  commercial law (Malynes), probability philosophy (Ramsey), pure
  mathematics with no economics content at all (Minkowski, deliberately
  off-topic), Cournot historiography (Depitre), war economy (Neurath),
  imprecise probabilities (the Habilitation), lexicography (Johnson),
  poetry (Baudelaire), a chapterless novel (Stein), foundational physics
  (Curie, Einstein/Minkowski), and road-traffic law (the Highway Code).
- **Genre/register.** Treatise, ledger manual, statute excerpt, philosophy
  essay, journal article, war pamphlet, dissertation, dictionary, verse,
  continuous narrative prose, physics papers, government guidance pages —
  the corpus no longer reads as one genre in five languages.
- **Vietnamese agency spread.** BCT (energy, the original pair) and MONRE
  (environment, added this pass) — two ministries, two topics.
- **Item type.** Book, journal article, book section, legal instrument,
  and (for the six externally-sourced additions) works with no Zotero item
  type at all.
- **Document length.** 1 page (the DOCX-sourced VN circulars, committed
  whole since DOCX carries no fixed print pagination) to 1,104 pages
  (Johnson's dictionary) — three orders of magnitude.
- **Source format.** PDF (most documents), DOCX (two MONRE circulars, via
  `pandoc`), and live HTML (the Highway Code — 30 gov.uk guidance pages,
  each becoming one committed page, with the `<main>` element isolated
  before conversion so cookie banners and navigation chrome don't drown
  out the actual rules on every page).
- **Structural extremes, requested directly by the author for segmenter
  testing**: Baudelaire is verse (short lines, stanza breaks, no paragraph
  structure); Stein's *The Making of Americans* is 940 pages of continuous
  narrative with no chapter divisions at all, offering a segmenter no
  section boundary to key on, unlike every other document here.
- **Cross-lingual anchor**, still just the one pair (Decision 11/2017's
  official VN/EN bilingual text) — not expanded this pass.

**Considered and rejected: an IPCC report and IPCC presentations.**
Checked the IPCC's own copyright/permissions notice directly: it
authorizes free reproduction of "limited numbers of figures or short
excerpts" for personal, non-commercial use — not full reports, and
nothing found suggests presentations/outreach material carry different,
looser terms. Even granting this corpus's use is non-commercial, a full
report or deck would exceed that permission; committing one would need
explicit written permission this session doesn't have. The clean
alternative for climate-topic PD content, if wanted later, is a **US
government climate report** — a work of the US government carries no
copyright at all, unlike an IGO's own copyrighted-with-permission report.

## Johnson's Dictionary: a source swap, and why

The first candidate (Bayerische Staatsbibliothek's 1755 first-edition
scan, `10495836bsb`, 1.2 GB) turned out to have a scrambled reading order
in its own text layer — confirmed directly, not assumed: both its main
PDF and its archive.org-generated `djvu.txt` extract as garbled
letter-by-letter fragments, not real prose. Re-OCRing it wasn't
attempted, both because OCR is now out by policy and because a fresh
full-document OCR pass at 1,187 pages from a 1.2 GB source is a scale
this pipeline isn't tuned for regardless. Swapped for a University of
Toronto scan of the 1785 sixth edition, Volume 1 (1,104 pages), whose text
layer reads correctly on inspection. Same author, same work, a different,
usable printing — checked, not assumed, exactly like the Soddy case above.

## OCR-affected documents (before this pass's no-OCR policy)

The following carry a small number of sparse or empty pages, extracted
exactly as `pdftotext` produced them, per the no-OCR-by-default policy:
Cournot, Walras, Porte, Minkowski, and Neurath. Per-page char-length
minimums are recorded in `manifest.json` (`page_length_chars_min`) for
anyone who wants to find them. Decision 11/2017 is the sole exception,
OCR'd in full via its `allow_ocr: True` opt-in, because without OCR its
committed text would be almost entirely empty rather than merely sparse —
described in detail in `build_corpus.py`'s own `DOCS` entry for it.

## Reproducibility

Every Zotero-sourced document is fetched by item/attachment key from the
author's live library; six documents are fetched from a direct URL or a
set of live web pages instead. Both are mutable, live locations —
`manifest.json` records `source_attachment_sha256` per document so a
future re-run that fetches different bytes surfaces as a visible hash
diff rather than a silent content change under the same doc id. The UK
Highway Code is the most exposed to this: it is *itself* a living,
government-maintained document, not a fixed historical artifact, so a
re-run may commit different text under the same doc id if a rule has been
updated since — exactly what the hash exists to surface.

## What remains (ticket 0029's other exit criteria — not attempted this pass)

- **The correct next-phase sourcing design, identified but not
  implemented this pass**: the author pointed out, after this corpus was
  built, that the proper way to assemble it is to create a real Zotero
  collection, add each document as a genuine Zotero item with an uploaded
  attachment, and let Zotero's own server-side fulltext extraction produce
  the text — not a custom `pdftotext`/`pandoc`/OCR pipeline reinventing
  what the actual target system already does. This is the right design:
  it gives the corpus fidelity to what a real Zotero-indexed library
  actually produces, which a hand-rolled extraction script cannot
  guarantee. Not implemented this pass — it needs the write-access API
  key, per-item metadata entry, attachment upload, and waiting on Zotero's
  own indexing before text is even retrievable, which is a genuinely
  larger task than this session's remaining time allowed. `build_corpus.py`
  as it stands should be treated as a stopgap that produced real, usable,
  provenance-checked text — not the final architecture.
- **The author's PhD thesis** was requested alongside the Habilitation but
  is not included. It's deposited on HAL (`tel-00003505`, confirmed via
  HAL's own API), but the web frontend sits behind an Anubis anti-bot
  proof-of-work challenge this session's tools couldn't clear.
- **SHOULD-tier languages set aside, with reasons**, per the ticket's own
  rule:
  - **Russian.** The one old candidate in the library — Kantorovich 1939 —
    is not public domain (Kantorovich died 1986; life+70 runs to 2056).
  - **Chinese, Spanish, Hindi.** Zero items in the library are tagged with
    these languages at all. Set aside; would need external sourcing.
  - **Arabic.** Four items tagged, all modern UNFCCC/CBD documents, none
    public domain.
- **Group-library slice.** This Zotero account has zero group
  memberships. Not attempted.
- **Notes facet.** Not attempted.
- **A monster document in a non-Latin script.** Johnson's dictionary
  (1,104 pages) is now the longest document, but is Latin-script; no
  non-Latin-script PD candidate of that scale turned up.
- **Passage-length distribution pinning** — a property of the future
  chunker's output, not of raw pages.
- **~40 pinned queries, R33's three probe shapes, R34's absolute reading,
  the Zotero-free index-build harness, and the golden gate wiring** — none
  of this is built yet; all wait on the harness (and, per the point above,
  probably on the Zotero-collection sourcing redesign too).
- **No standing guard checks `manifest.json` against a fresh run of
  `DOCS`.** A hand-edit or drift would go undetected.

None of the unmet items block what this pass delivers: nineteen real,
licensed, page-addressable documents spanning five languages, four
licensing bases, and genuine structural extremes, an index harness can be
pointed at once it exists — with the correct long-term sourcing design
now identified in writing for whoever builds that harness next.
