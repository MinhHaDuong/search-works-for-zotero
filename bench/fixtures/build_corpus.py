#!/usr/bin/env python3
"""Assemble ticket 0029's golden-fixture corpus from the author's Zotero library.

Fetches each pinned document's PDF attachment from the public Zotero Web API
(userID 95318 is a publicly readable library, so no key is needed for read
access), extracts page-delimited plain text, and writes bench/fixtures/corpus/
plus its manifest.json. Every document is picked for a documented public-domain
basis -- see MANIFEST.md for the selection rationale and what's still missing.

Re-run this to refresh the corpus (e.g. after DOCS gains an entry). Raw PDFs
and OCR language data are cached under corpus-cache/ at the repo root
(gitignored, same convention as fork/ and upstream.git/) so a re-run does not
re-fetch or re-download tessdata unless the cache is cleared.

Reproducibility is contingent, not guaranteed: each attachment is fetched by
Zotero item/attachment key from a live, mutable library. If the author
replaces an attachment (a corrected scan, a different edition), a re-run
against a cleared cache will fetch different bytes and commit different
text under the same doc id. `source_attachment_sha256` in manifest.json exists to
make that visible -- a re-run whose hash for an id changed is a signal to
review the diff before trusting it, not proof nothing changed.
"""
import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import unicodedata
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build-corpus")

ZOTERO_USER = "95318"
ZOTERO_FILE_URL = f"https://api.zotero.org/users/{ZOTERO_USER}/items/{{key}}/file"
TESSDATA_FAST_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"

# Minimum plausible OCR density; below this a "text layer" is assumed absent
# (e.g. only a certificate-stamp overlay was digital-native) and the page is
# re-extracted via tesseract instead of trusted as-is.
MIN_CHARS_PER_PAGE = 50

# Per-page floor for rescue_sparse_pages(): below this, a page inside an
# otherwise-dense document is re-OCR'd individually rather than trusted as a
# genuine blank leaf. Lower than MIN_CHARS_PER_PAGE deliberately -- this is a
# per-page check, not the whole-document average MIN_CHARS_PER_PAGE guards.
MIN_CHARS_PER_SPARSE_PAGE = 20

# tesseract/tessdata use ISO 639-2/T three-letter codes; DOCS uses the
# two-letter codes the rest of this repo (and Zotero's own `language` field)
# uses. Only the languages DOCS actually needs are mapped.
TESSERACT_LANG = {"fr": "fra", "en": "eng", "de": "deu", "vi": "vie"}

# A ceiling for local tool invocations (pandoc/tesseract/pdftoppm/pdftotext),
# separate from --timeout (which bounds network requests only): a pathological
# input (a decompression-bomb XObject, a font-subsetting trap) can make one of
# these tools spin or balloon memory forever with no recovery otherwise.
# Generous because pdftoppm renders a whole document in one call -- Porte's
# 788 pages need real wall-clock, not a per-page budget.
SUBPROCESS_TIMEOUT = 300.0

DOCS = [
    {
        "id": "cournot-1838-recherches",
        "title": "Recherches sur les principes mathématiques de la théorie des richesses",
        "author": "Antoine-Augustin Cournot",
        "year": 1838,
        "language": "fr",
        "facet": "core",
        "zotero_item_key": "W4925VVD",
        "zotero_attachment_key": "DRKJ5I24",
        "source": "Bibliothèque nationale de France (Gallica) digitization",
        "license_basis": (
            "Public domain everywhere: author died 1877 (life+70 expired 1947); "
            "also clear under the US pre-1931-publication bright-line."
        ),
    },
    {
        "id": "walras-1900-elements",
        "title": "Éléments d'économie politique pure, ou Théorie de la richesse sociale (4e éd.)",
        "author": "Léon Walras",
        "year": 1900,
        "language": "fr",
        "facet": "core",
        "zotero_item_key": "J7B6FQ86",
        "zotero_attachment_key": "W835BEDK",
        "source": "Internet Archive digitization",
        "license_basis": (
            "Public domain everywhere: author died 1910 (life+70 expired 1980); "
            "also clear under the US pre-1931-publication bright-line. OCR is noisy "
            "in mathematical passages (period typeface); prose passages are legible."
        ),
    },
    # Soddy 1926 "Wealth, Virtual Wealth and Debt" was dropped from this
    # corpus (was here in the first assembly pass): the only attachment
    # found, in the author's library and re-checked via an independent
    # archive.org upload, is a scan of the 1983 George Allen & Unwin
    # REPRINT ("1983 reprint" appears in the PDF's own embedded metadata),
    # not the 1926 original. A reprint edition can carry its own separate
    # copyright over its specific typesetting even when the underlying text
    # is public domain -- exactly the Dover-reissue risk. No verified
    # original-edition scan turned up in the time available; if one is
    # found later, this is the slot to re-add it to.
    {
        "id": "malynes-1622-lex-mercatoria-extrait",
        "title": "Consuetudo, vel Lex Mercatoria, or The Ancient Law-Merchant (excerpt: Of Exchanges)",
        "author": "Gerard de Malynes",
        "year": 1622,
        "language": "en",
        "facet": "core",
        "zotero_item_key": "DPJEV5DK",
        "zotero_attachment_key": "AHXHAQZ3",
        "source": "scanned attachment in the author's Zotero library",
        "license_basis": (
            "Public domain everywhere: published 1622, author died c. 1641 "
            "(life+70 expired centuries ago); clear under any reading."
        ),
        "notes": (
            "A 45-page excerpt of the full work (the chapter on foreign "
            "exchange), not the complete c. 500-page treatise -- title "
            "reflects that. Early-modern typography (long s, black-letter "
            "passages) makes for noisier OCR than the 18th/19th-century items."
        ),
    },
    {
        "id": "ramsey-1926-truth-and-probability",
        "title": 'Truth and Probability',
        "author": "Frank P. Ramsey",
        "year": 1926,
        "language": "en",
        "facet": "core",
        "zotero_item_key": "X2T4QRRG",
        "zotero_attachment_key": "E72C73RG",
        "source": "scanned attachment in the author's Zotero library",
        "license_basis": (
            "Public domain everywhere: author died 1930 (life+70 expired "
            "2000). NOT via the pre-1931 US bright-line -- the essay was "
            "written in 1926 but only published posthumously in 1931, in "
            "Ramsey's Foundations of Mathematics, so the publication date "
            "sits right on the wrong side of that heuristic. Age (life+70) "
            "carries this one instead, cleanly."
        ),
        "notes": (
            "The committed file's own first page identifies itself as an "
            "'Electronic Edition... adapted from Chapter VII' of the 1931 "
            "posthumous collection -- a transcription prepared for open "
            "teaching use, not a scan of the original book. Read as a "
            "faithful reproduction (no added commentary found), but flagged "
            "since it isn't a facsimile like the rest of this corpus."
        ),
    },
    {
        "id": "porte-1770-science-des-negocians",
        "title": "La Science des négocians et teneurs de livres",
        "author": "Mathieu de La Porte",
        "year": 1770,
        "language": "fr",
        "facet": "core",
        "zotero_item_key": "UUU5NQ2D",
        "zotero_attachment_key": "43IKDWRP",
        "source": "Internet Archive digitization",
        "license_basis": (
            "Public domain everywhere: published 1770, author died 18th "
            "century (exact date unattested but centuries past life+70 "
            "under any reading); clear under the US bright-line too."
        ),
        "notes": (
            "788 pages -- a bookkeeping/accounting manual, not economic "
            "theory: genre variety against the Cournot/Walras value-theory "
            "pair, and currently the longest single document in the corpus."
        ),
    },
    {
        "id": "depitre-1908-oeuvres-cournot",
        "title": "Note sur les œuvres économiques d'Augustin Cournot",
        "author": "Edgard Depitre",
        "year": 1908,
        "language": "fr",
        "facet": "core",
        "zotero_item_key": "UKVXPC5P",
        "zotero_attachment_key": "E6I9MXB3",
        "source": "scanned attachment in the author's Zotero library",
        "license_basis": (
            "Public domain everywhere: published 1908, pre-1931 US "
            "bright-line; author's dates place life+70 long expired too."
        ),
        "notes": "10-page journal article -- historiography of Cournot, a genre this corpus otherwise lacks entirely.",
    },
    {
        "id": "minkowski-1896-geometrie-der-zahlen",
        "title": "Geometrie der Zahlen",
        "author": "Hermann Minkowski",
        "year": 1896,
        "language": "de",
        "facet": "core",
        "tier": "SHOULD",
        "zotero_item_key": "4574EQ7I",
        "zotero_attachment_key": "CK7UC6EI",
        "source": "Internet Archive digitization",
        "license_basis": (
            "Public domain everywhere: Minkowski died 1909 (life+70 "
            "expired 1979); the digitized copy is the 1910 second printing, "
            "still within his lifetime's copyright term either way, and "
            "pre-1931 under the US bright-line regardless of printing."
        ),
        "notes": (
            "274 pages of pure mathematics (number theory), not economics "
            "at all -- deliberately off-topic within the German slot, "
            "useful for testing that unrelated-subject documents don't "
            "falsely dominate an economics query."
        ),
    },
    # Westergaard 1890 was considered (a single-page excerpt) but dropped:
    # its Zotero attachment is tagged contentType application/pdf but is
    # actually a raw JPEG (magic bytes ffd8ffe0) -- a mislabeled image, not
    # a PDF. Caught by fetch_attachment's magic-byte check. Not worth
    # building one-off image-OCR handling for a single marginal page.
    {
        "id": "vn-circular-41-2010-btnmt-emissions",
        "title": "Thông tư 41/2010/TT-BTNMT quy chuẩn kỹ thuật quốc gia về khí thải lò đốt chất thải công nghiệp",
        "author": "Bộ Tài nguyên và Môi trường (Ministry of Natural Resources and Environment of Vietnam)",
        "year": 2010,
        "language": "vi",
        "facet": "core",
        "zotero_item_key": "KDED28A7",
        "zotero_attachment_key": "GFBQ4ISC",
        "attachment_format": "docx",
        "source": "scanned/digital attachment in the author's Zotero library",
        "license_basis": (
            "Public domain under Vietnamese law: Luật Sở hữu trí tuệ, "
            "Article 15.2 -- a Circular issued by a ministry is a legal "
            "normative document, excluded from copyright protection."
        ),
        "notes": (
            "Ministry of Natural Resources and Environment (MONRE), not "
            "Industry and Trade (BCT) like the other VI documents here -- "
            "agency and topic variety (industrial-emissions technical "
            "standards, not energy-market regulation)."
        ),
    },
    {
        "id": "vn-circular-42-2010-btnmt-emissions",
        "title": "Thông tư 42/2010/TT-BTNMT quy chuẩn kỹ thuật quốc gia về môi trường",
        "author": "Bộ Tài nguyên và Môi trường (Ministry of Natural Resources and Environment of Vietnam)",
        "year": 2010,
        "language": "vi",
        "facet": "core",
        "zotero_item_key": "VY23EJ37",
        "zotero_attachment_key": "JU8GBECQ",
        "attachment_format": "docx",
        "source": "scanned/digital attachment in the author's Zotero library",
        "license_basis": (
            "Public domain under Vietnamese law: Luật Sở hữu trí tuệ, "
            "Article 15.2 -- a Circular issued by a ministry is a legal "
            "normative document, excluded from copyright protection."
        ),
        "notes": "Companion MONRE circular to 41/2010, same agency and topic class.",
    },
    {
        "id": "ha-duong-2005-modeles-de-precaution-hdr",
        "title": "Modèles de précaution en économie : introduction aux probabilités imprécises",
        "author": "Minh Ha-Duong",
        "year": 2005,
        "language": "fr",
        "facet": "core",
        "source_url": "https://minh.haduong.com/files/HaDuong-20051223-ModelesDePrecautionEnEconomieIntroductionAuxProbabilitesImprecises.pdf",
        "source": "the author's own homepage (minh.haduong.com)",
        "license_basis": (
            "Author-owned, not public domain: this is Minh Ha-Duong's own "
            "Habilitation à diriger des recherches (HDR), and he is this "
            "corpus's commissioning author -- he holds copyright and "
            "authorized its inclusion directly (2026-09-01). Recorded here "
            "as a distinct basis from the public-domain items above, since "
            "it rests on the rightsholder's own permission rather than "
            "expired or excluded copyright."
        ),
        "notes": "His PhD thesis (1998, EHESS) was requested alongside this but is not yet included -- see MANIFEST.md.",
    },
    {
        "id": "neurath-1919-durch-die-kriegswirtschaft",
        "title": "Durch die Kriegswirtschaft zur Naturalwirtschaft",
        "author": "Otto Neurath",
        "year": 1919,
        "language": "de",
        "facet": "core",
        "tier": "SHOULD",
        "zotero_item_key": "MYH839NE",
        "zotero_attachment_key": "3ABCR92V",
        "source": "scanned attachment in the author's Zotero library",
        "license_basis": (
            "Public domain everywhere: author died 1945 (life+70 expired 2015); "
            "also clear under the US pre-1931-publication bright-line. Fraktur "
            "title page OCRs poorly; body text (Antiqua) is legible."
        ),
    },
    {
        "id": "vn-decision-11-2017-qdttg-solar-fit",
        "title": "Quyết định 11/2017/QĐ-TTg về cơ chế khuyến khích phát triển các dự án điện mặt trời tại Việt Nam",
        "author": "Thủ tướng Chính phủ (Prime Minister of Vietnam)",
        "year": 2017,
        "language": "vi",
        "facet": "core",
        "zotero_item_key": "BBC3AWPR",
        "zotero_attachment_key": "JXZEX4KX",
        # The one explicit OCR opt-in in this corpus (2026-09-01 policy: no
        # OCR by default, everywhere else). Structurally necessary here --
        # this scan's body has no text layer at all, only the certificate
        # stamp does, so without OCR the committed text would be almost
        # entirely empty rather than merely sparse.
        "allow_ocr": True,
        "source": "Cổng Thông tin điện tử Chính phủ (Vietnam Government Portal), official e-signed PDF",
        "license_basis": (
            "Public domain under Vietnamese law: Luật Sở hữu trí tuệ (Law on "
            "Intellectual Property No. 50/2005/QH11, as amended), Article 15.2 -- "
            "legal normative documents (văn bản quy phạm pháp luật), administrative "
            "documents, and their official translations are excluded from copyright "
            "protection. A Decision issued by the Prime Minister is such a document."
        ),
        "notes": (
            "The e-signed scan carries no text layer over the body (only the "
            "certificate-stamp page is digital-native), so this entry is OCR'd "
            "page-by-page with the vie tessdata pack, triggered automatically "
            "by extract_text()'s chars-per-page density check. "
            "ocrmypdf itself (even with --invalidate-digital-signatures) produced "
            "an empty text layer on this file; direct per-page tesseract on "
            "pdftoppm-rendered pages is what works, which is the path this script "
            "takes automatically once density falls under the threshold."
        ),
        "cross_lingual_pair": {
            "language": "en",
            "zotero_item_key": "BBC3AWPR",
            "zotero_attachment_key": "NY82JVHH",
            "note": (
                "Official English translation of the same decision, kept as a "
                "reference for verifying the semantic content of cross-lingual "
                "EN/FR-query -> VI-answer pins (R29). Not itself indexed as an "
                "answer document -- the pinned answer is the Vietnamese text."
            ),
        },
    },
    {
        "id": "vn-circular-25-2016-ttbct-transmission",
        "title": "Thông tư 25/2016/TT-BCT quy định hệ thống điện truyền tải",
        "author": "Bộ Công Thương (Ministry of Industry and Trade of Vietnam)",
        "year": 2016,
        "language": "vi",
        "facet": "core",
        "zotero_item_key": "5XE6WL29",
        "zotero_attachment_key": "AXP4AV7G",
        "source": "scanned/digital attachment in the author's Zotero library",
        "license_basis": (
            "Public domain under Vietnamese law: Luật Sở hữu trí tuệ, Article 15.2 -- "
            "a Circular issued by a ministry is a legal normative document, excluded "
            "from copyright protection."
        ),
        "notes": "106 pages -- the longest MUST-tier document in this pass, useful for R24 page-locator coverage.",
    },
    # --- Round 3: dictionary, poetry, a chapterless long-form work, two
    # Nobel-laureate-connected papers, and a UK statute-adjacent document,
    # all requested directly by the author for further variety. Every
    # non-Vietnamese, non-Zotero item below is sourced from archive.org and
    # checked the same way as everything above: real institutional scanner/
    # operator/collection metadata (not an anonymous "opensource" upload,
    # the exact category that turned out to be Soddy's problem), read
    # directly rather than inferred from the archive.org search result.
    {
        "id": "johnson-1785-dictionary",
        "title": "A Dictionary of the English Language, Vol. 1 (6th ed.)",
        "author": "Samuel Johnson",
        "year": 1785,
        "language": "en",
        "facet": "core",
        "source_url": "https://archive.org/download/dictionaryofengl01johnuoft/dictionaryofengl01johnuoft.pdf",
        "source": "University of Toronto (Kelly Library) digitization, via archive.org",
        "license_basis": (
            "Public domain everywhere: published 1785 (author died 1784, "
            "the year before -- this sixth edition was posthumous); "
            "life+70 from his death expired 1854 regardless. Clear under "
            "the US pre-1931-publication bright-line too."
        ),
        "notes": (
            "1,104 pages -- the largest document in this corpus by a wide "
            "margin (the author explicitly wanted size, not a trimmed "
            "excerpt). A dictionary's entry-per-headword structure is "
            "unlike every other document here (all continuous prose or "
            "legal-instrument text), which is the point: it tests whatever "
            "later segmenter work does with a reference work rather than a "
            "narrative or an argument. Swapped in for this edition after "
            "the Bavarian State Library's 1755-first-edition scan turned "
            "out to have a scrambled reading order in its own text layer "
            "(garbled letter-by-letter, both in its main PDF and its "
            "archive.org-generated djvu.txt) -- a 1.2 GB source that would "
            "also have needed a full re-OCR pass at a scale this pipeline "
            "isn't tuned for. Read on inspection, not assumed clean because "
            "it came from a named library the way the rest of this corpus's "
            "provenance checks work."
        ),
    },
    {
        "id": "baudelaire-1857-fleurs-du-mal",
        "title": "Les Fleurs du Mal (1re éd.)",
        "author": "Charles Baudelaire",
        "year": 1857,
        "language": "fr",
        "facet": "core",
        "source_url": "https://archive.org/download/lesfleursdum00baud/lesfleursdum00baud.pdf",
        "source": "University of Toronto (Kelly Library) digitization, via archive.org",
        "license_basis": (
            "Public domain everywhere: published 1857, author died 1867 "
            "(life+70 expired 1937); clear under the US pre-1931-publication "
            "bright-line too. (The 1857 first edition was itself prosecuted "
            "for obscenity -- six poems banned in France until 1949 -- which "
            "is orthogonal to its copyright status but a genuine feature of "
            "this exact edition, confirmed by archive.org's own 'bannedbooks' "
            "collection tag on this scan.)"
        ),
        "notes": (
            "Verse, not prose -- short lines, stanza breaks, no paragraph "
            "structure. Requested by the author specifically for segmenter "
            "testing: a chunker tuned on prose/legal text needs a poetry "
            "case to know whether it's actually generalizing."
        ),
    },
    {
        "id": "stein-1925-making-of-americans",
        "title": "The Making of Americans",
        "author": "Gertrude Stein",
        "year": 1925,
        "language": "en",
        "facet": "core",
        "source_url": "https://archive.org/download/makingofamerican0000unse_j2t9/makingofamerican0000unse_j2t9.pdf",
        "source": "Internet Archive digitization (internetarchivebooks collection)",
        "license_basis": (
            "Public domain everywhere: published 1925 (Contact Editions, "
            "Paris), author died 1946 (life+70 expired 2016); clear under "
            "the US pre-1931-publication bright-line too."
        ),
        "notes": (
            "940 pages of continuous narrative with no chapter divisions -- "
            "requested by the author to test how a segmenter handles a long "
            "document that offers it no section boundaries to key on at "
            "all, unlike everything else in this corpus (which has "
            "chapters, articles, dictionary headwords, or legal-instrument "
            "clauses)."
        ),
    },
    {
        "id": "curie-1904-recherches-substances-radioactives",
        "title": "Recherches sur les substances radioactives",
        "author": "Marie Curie",
        "year": 1904,
        "language": "fr",
        "facet": "core",
        "source_url": "https://archive.org/download/recherchessurles00curi/recherchessurles00curi.pdf",
        "source": "University of Toronto (Thomas Fisher Rare Book Library) digitization, via archive.org",
        "license_basis": (
            "Public domain everywhere: published 1904 (Gauthier-Villars, "
            "Paris), author died 1934 (life+70 expired 2004); clear under "
            "the US pre-1931-publication bright-line too."
        ),
        "notes": (
            "Curie's doctoral thesis, the basis of her 1903 Physics Nobel "
            "(shared with Pierre Curie and Becquerel) and her 1911 "
            "Chemistry Nobel -- a seminal-research-article addition, "
            "requested by the author, and the corpus's second Nobel-linked "
            "document alongside the Einstein/Minkowski entry below."
        ),
    },
    {
        "id": "einstein-minkowski-1920-principle-of-relativity",
        "title": "The Principle of Relativity: Original Papers by A. Einstein and H. Minkowski",
        "author": "Albert Einstein and Hermann Minkowski, translated by M. N. Saha and S. N. Bose",
        "year": 1920,
        "language": "en",
        "facet": "core",
        "source_url": "https://archive.org/download/theprincipleofre00einsuoft/theprincipleofre00einsuoft.pdf",
        "source": "University of Toronto (Robarts Library) digitization, via archive.org",
        "license_basis": (
            "Public domain in the US via the pre-1931-publication "
            "bright-line -- this translation was published in 1920 "
            "(University of Calcutta), which is what carries it, NOT "
            "life+70: translator S. N. Bose died in 1974, so life+70 for "
            "the translation itself would not expire until 2044. Einstein's "
            "original 1905 German papers and Minkowski's (d. 1909) are "
            "separately clear either way. Read the two bases apart, the "
            "same trap the Ramsey entry above flags."
        ),
        "notes": (
            "Requested by the author as a seminal, Nobel-connected paper "
            "(Einstein, Physics 1921) in English. Translated by Meghnad "
            "Saha and Satyendra Nath Bose -- the same Bose of Bose-Einstein "
            "statistics -- with a historical introduction by P. C. "
            "Mahalanobis; a historically notable translation in its own "
            "right, not an anonymous one."
        ),
    },
    {
        "id": "uk-highway-code",
        "title": "The Highway Code",
        "author": "Department for Transport (United Kingdom)",
        "year": 2026,
        "language": "en",
        "facet": "core",
        "page_urls": [
            "https://www.gov.uk/guidance/the-highway-code/introduction",
            "https://www.gov.uk/guidance/the-highway-code/rules-for-pedestrians-1-to-35",
            "https://www.gov.uk/guidance/the-highway-code/rules-for-users-of-powered-wheelchairs-and-mobility-scooters-36-to-46",
            "https://www.gov.uk/guidance/the-highway-code/rules-about-animals-47-to-58",
            "https://www.gov.uk/guidance/the-highway-code/rules-for-cyclists-59-to-82",
            "https://www.gov.uk/guidance/the-highway-code/rules-for-motorcyclists-83-to-88",
            "https://www.gov.uk/guidance/the-highway-code/rules-for-drivers-and-motorcyclists-89-to-102",
            "https://www.gov.uk/guidance/the-highway-code/general-rules-techniques-and-advice-for-all-drivers-and-riders-103-to-158",
            "https://www.gov.uk/guidance/the-highway-code/using-the-road-159-to-203",
            "https://www.gov.uk/guidance/the-highway-code/road-users-requiring-extra-care-204-to-225",
            "https://www.gov.uk/guidance/the-highway-code/driving-in-adverse-weather-conditions-226-to-237",
            "https://www.gov.uk/guidance/the-highway-code/waiting-and-parking-238-to-252",
            "https://www.gov.uk/guidance/the-highway-code/motorways-253-to-273",
            "https://www.gov.uk/guidance/the-highway-code/breakdowns-and-incidents-274-to-287",
            "https://www.gov.uk/guidance/the-highway-code/road-works-level-crossings-and-tramways-288-to-307",
            "https://www.gov.uk/guidance/the-highway-code/light-signals-controlling-traffic",
            "https://www.gov.uk/guidance/the-highway-code/signals-to-other-road-users",
            "https://www.gov.uk/guidance/the-highway-code/signals-by-authorised-persons",
            "https://www.gov.uk/guidance/the-highway-code/traffic-signs",
            "https://www.gov.uk/guidance/the-highway-code/road-markings",
            "https://www.gov.uk/guidance/the-highway-code/vehicle-markings",
            "https://www.gov.uk/guidance/the-highway-code/other-information",
            "https://www.gov.uk/guidance/the-highway-code/annex-1-you-and-your-bicycle",
            "https://www.gov.uk/guidance/the-highway-code/annex-2-motorcycle-licence-requirements",
            "https://www.gov.uk/guidance/the-highway-code/annex-3-motor-vehicle-documentation-and-learner-driver-requirements",
            "https://www.gov.uk/guidance/the-highway-code/annex-4-the-road-user-and-the-law",
            "https://www.gov.uk/guidance/the-highway-code/annex-5-penalties",
            "https://www.gov.uk/guidance/the-highway-code/annex-6-vehicle-maintenance-safety-and-security",
            "https://www.gov.uk/guidance/the-highway-code/annex-7-first-aid-on-the-road",
            "https://www.gov.uk/guidance/the-highway-code/annex-8-safety-code-for-new-drivers",
        ],
        "source": "gov.uk, live guidance pages (~30 sections, one per committed page)",
        "license_basis": (
            "NOT public domain -- Crown Copyright, published under the Open "
            "Government Licence v3.0. This is a fourth, distinct basis from "
            "the other three in this corpus: OGL is a genuine open licence "
            "the rightsholder (the Crown) grants, not an absence of "
            "copyright (unlike age) or a statutory exclusion (unlike the "
            "Vietnamese items). OGL grants a worldwide, royalty-free, "
            "perpetual, non-exclusive licence to copy, adapt, and "
            "redistribute, commercially or not, conditioned only on "
            "attribution -- confirmed directly against gov.uk's own OGL "
            "text, not assumed from the 'government document' pattern of "
            "the Vietnamese entries, which rests on a different legal "
            "mechanism (copyright exclusion, not a license grant)."
        ),
        "notes": (
            "Requested by the author (\"UK Code for driving\"). Sourced "
            "directly from gov.uk (~30 separate guidance pages, one per "
            "committed page) rather than any of the several third-party "
            "PDF mirrors search turned up, whose fidelity to the current "
            "official text isn't independently verifiable. `year` is this "
            "session's date, not a fixed publication year: the Code is "
            "live-maintained on gov.uk, so a re-run may commit different "
            "text under the same doc id if a rule has been updated -- "
            "exactly what source_attachment_sha256 exists to surface."
        ),
    },
]


def _download_atomic(
    url: str, dest: Path, timeout: float, magic: bytes | None = None, min_size: int = 0
) -> None:
    """Fetch `url` to `dest` via a temp file + rename, so a mid-transfer
    failure (network drop, timeout) never leaves a truncated file sitting at
    `dest` for a later run to trust unconditionally. `magic`, if given, is
    checked against the first bytes before the rename; `min_size` rejects an
    implausibly small response (e.g. an HTML error page served with a 200) --
    either failing loud here beats silently poisoning the cache. tessdata
    files have no stable magic-byte prefix to check (inspected one directly:
    it opens with a version/count header, not fixed bytes), which is why
    `ensure_tessdata` below uses `min_size` instead of `magic`."""
    tmp = dest.with_suffix(dest.suffix + ".partial")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    size = tmp.stat().st_size
    if size < min_size:
        tmp.unlink()
        raise SystemExit(f"{url}: got {size} bytes, expected at least {min_size} -- download corrupt")
    if magic is not None:
        head = tmp.read_bytes()[: len(magic)]
        if head != magic:
            tmp.unlink()
            raise SystemExit(f"{url}: expected {magic!r} at file start, got {head!r} -- download corrupt")
    os.replace(tmp, dest)


def fetch_html_page(url: str, cache_dir: Path, timeout: float) -> Path:
    """Fetch one HTML page, keyed by a hash of its URL (there is no
    attachment key the way a Zotero source has one). Used for a document
    that only exists as a set of live web pages (e.g. gov.uk's Highway
    Code, published as ~30 separate guidance pages, not one PDF)."""
    dest = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.html"
    if dest.exists():
        return dest
    log.info("fetching %s", url)
    _download_atomic(url, dest, timeout, min_size=500)
    return dest


def extract_html_text(html_path: Path) -> str:
    """A full gov.uk page is mostly chrome (cookie banner, nav menu,
    footer) identical across every page of a multi-page document -- fed
    straight to pandoc it would dominate every committed page equally.
    Isolate the <main> element (gov.uk's own content wrapper, confirmed
    present and consistent across the pages this pipeline fetches) before
    conversion; fall back to the whole document if a source ever lacks
    one, rather than fail outright on a page pandoc could still handle."""
    html = html_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
    content = match.group(1) if match else html
    result = subprocess.run(
        ["pandoc", "-f", "html", "-t", "plain"],
        input=content,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        raise SystemExit(f"pandoc failed on {html_path} (exit {result.returncode}): {result.stderr.strip()}")
    return unicodedata.normalize("NFC", result.stdout)


def fetch_attachment(doc: dict, cache_dir: Path, timeout: float) -> Path:
    """Fetch a document's source file -- a Zotero attachment by key, or a
    direct URL for a document that isn't in Zotero at all (e.g. a PDF
    hosted on the author's own homepage). PDF and DOCX are the two formats
    DOCS uses; each gets its own magic-byte check (DOCX is a zip archive,
    so `PK`) and size floor."""
    fmt = doc.get("attachment_format", "pdf")
    magic = {"pdf": b"%PDF", "docx": b"PK"}[fmt]
    min_size = {"pdf": 1_000, "docx": 5_000}[fmt]
    if "zotero_attachment_key" in doc:
        key = doc["zotero_attachment_key"]
        dest = cache_dir / f"{key}.{fmt}"
        url = ZOTERO_FILE_URL.format(key=key)
    else:
        url = doc["source_url"]
        dest = cache_dir / f"{doc['id']}.{fmt}"
    if dest.exists():
        return dest
    log.info("fetching %s", url)
    _download_atomic(url, dest, timeout, magic=magic, min_size=min_size)
    return dest


def extract_docx_text(docx_path: Path) -> str:
    """DOCX has no fixed print pagination the way a scanned PDF's original
    artifact does -- a docx->pdf conversion's page breaks are the renderer's
    opinion, not the source's. Extract with pandoc and treat the whole
    document as one page (no \\f) rather than manufacture a fake one.
    (soffice --headless --convert-to pdf was tried first and used for the
    docx->pdf route; it failed outright on one of the two docx sources here
    with 'source file could not be loaded' while pandoc extracted both
    cleanly, so pandoc is the primary path, not a fallback.)"""
    result = subprocess.run(
        ["pandoc", "-t", "plain", str(docx_path)], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT
    )
    if result.returncode != 0:
        raise SystemExit(f"pandoc failed on {docx_path} (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout


def ensure_tessdata(tess_lang: str, cache_dir: Path, timeout: float) -> Path:
    """Return a tessdata dir containing `tess_lang`, fetching it if this
    machine's system tesseract install doesn't already have it (e.g. only
    eng/fra here)."""
    system_check = subprocess.run(
        ["tesseract", "--list-langs"], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT
    )
    if system_check.returncode != 0:
        raise SystemExit(f"tesseract --list-langs failed (exit {system_check.returncode}): {system_check.stderr.strip()}")
    if tess_lang in system_check.stdout.splitlines():
        # Empty string tells tesseract to use its own default search path.
        return Path()
    local = cache_dir / "tessdata"
    local.mkdir(parents=True, exist_ok=True)
    dest = local / f"{tess_lang}.traineddata"
    if not dest.exists():
        url = TESSDATA_FAST_URL.format(lang=tess_lang)
        log.info("fetching tessdata for %r (not in system tesseract) from %s", tess_lang, url)
        # 100 KB floor: the smallest tessdata_fast files are several hundred
        # KB; anything under this is an error page or a truncated transfer.
        _download_atomic(url, dest, timeout, min_size=100_000)
    return local


def _tesseract_env(lang: str, cache_dir: Path, timeout: float) -> tuple[str, dict]:
    tess_lang = TESSERACT_LANG.get(lang)
    if tess_lang is None:
        raise SystemExit(f"no tesseract language mapping for {lang!r} -- add one to TESSERACT_LANG")
    tessdata_dir = ensure_tessdata(tess_lang, cache_dir, timeout)
    env = {"TESSDATA_PREFIX": str(tessdata_dir)} if tessdata_dir != Path() else {}
    return tess_lang, env


def _tesseract_page(png: Path, tess_lang: str, env: dict) -> str:
    result = subprocess.run(
        ["tesseract", str(png), "-", "-l", tess_lang],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        timeout=SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        raise SystemExit(f"tesseract failed on {png} (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout


def ocr_pdf(pdf_path: Path, lang: str, cache_dir: Path, timeout: float) -> str:
    tess_lang, env = _tesseract_env(lang, cache_dir, timeout)
    pages_dir = cache_dir / f"{pdf_path.stem}-pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", "300", str(pdf_path), str(pages_dir / "p")],
        check=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    chunks = [_tesseract_page(png, tess_lang, env) for png in sorted(pages_dir.glob("p-*.png"))]
    return "\f".join(chunks) + "\f"


def ocr_single_page(pdf_path: Path, page_num: int, lang: str, cache_dir: Path, timeout: float) -> str:
    """OCR one 1-indexed page, to rescue a page pdftotext extracted as
    near-empty inside an otherwise-dense document -- confirmed directly
    (Porte 1770, page 72) to more often be a failed OCR pass in the
    source scan than a genuine blank leaf."""
    tess_lang, env = _tesseract_env(lang, cache_dir, timeout)
    rescue_dir = cache_dir / f"{pdf_path.stem}-rescue"
    rescue_dir.mkdir(parents=True, exist_ok=True)
    stem = rescue_dir / f"p{page_num}"
    subprocess.run(
        ["pdftoppm", "-png", "-r", "300", "-f", str(page_num), "-l", str(page_num), str(pdf_path), str(stem)],
        check=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    pngs = sorted(rescue_dir.glob(f"{stem.name}*.png"))
    if not pngs:
        return ""
    return _tesseract_page(pngs[0], tess_lang, env)


def rescue_sparse_pages(pdf_path: Path, pages: list[str], lang: str, cache_dir: Path, timeout: float) -> list[str]:
    """Re-OCR any page under MIN_CHARS_PER_SPARSE_PAGE, individually, and
    keep the OCR result only if it found more than what pdftotext already
    had -- so a page that really is blank stays blank rather than picking
    up OCR noise from a scan artifact. This is the per-page counterpart to
    extract_text's whole-document density check, which averages over every
    page and so cannot see a handful of failed pages inside an otherwise
    dense document (a mid-document average stays well above the floor)."""
    rescued = list(pages)
    for i, page_text in enumerate(pages):
        if len(page_text.strip()) >= MIN_CHARS_PER_SPARSE_PAGE:
            continue
        ocr_text = ocr_single_page(pdf_path, i + 1, lang, cache_dir, timeout)
        if len(ocr_text.strip()) > len(page_text.strip()):
            log.info(
                "%s page %d: rescued %d chars via per-page OCR (pdftotext had %d)",
                pdf_path.name,
                i + 1,
                len(ocr_text.strip()),
                len(page_text.strip()),
            )
            rescued[i] = ocr_text
    return rescued


def extract_text(
    src_path: Path, lang: str, cache_dir: Path, timeout: float, fmt: str = "pdf", allow_ocr: bool = False
) -> str:
    if fmt == "docx":
        return unicodedata.normalize("NFC", extract_docx_text(src_path))
    pdf_path = src_path
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT
    )
    if result.returncode != 0:
        raise SystemExit(f"pdftotext failed on {pdf_path} (exit {result.returncode}): {result.stderr.strip()}")
    text = result.stdout
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages = pages[:-1]
    density = len(text) / max(len(pages), 1)
    if not allow_ocr:
        # No OCR by default -- an explicit author decision (2026-09-01):
        # a document either has a real text layer or it isn't used here.
        # The one exception (vn-decision-11-2017, whose body has no text
        # layer at all) opts in explicitly via DOCS' allow_ocr: True; every
        # other document, sparse pages included, is committed exactly as
        # pdftotext extracted it -- "a real dirty corpus" was the direction,
        # not a cleaned-up one.
        pass
    elif density < MIN_CHARS_PER_PAGE:
        log.info(
            "%s: %.0f chars/page over %d pages looks like a missing text layer -- OCR'ing",
            pdf_path.name,
            density,
            len(pages),
        )
        text = ocr_pdf(pdf_path, lang, cache_dir, timeout)
    else:
        # The whole-document average above cannot see a handful of failed
        # pages inside an otherwise dense document -- confirmed directly on
        # Porte 1770 (page 72, sandwiched between flowing content). Rescue
        # those individually rather than trust the average.
        pages = rescue_sparse_pages(pdf_path, pages, lang, cache_dir, timeout)
        text = "\f".join(pages) + "\f"
    # NFC, not whatever pdftotext/tesseract happened to emit -- so a future
    # re-run (different tesseract build, a replaced Zotero attachment) can't
    # silently commit NFD text under the same doc id that looks identical
    # rendered but fails exact/substring matches against NFC query text.
    return unicodedata.normalize("NFC", text)


def build_one(doc: dict, out_dir: Path, cache_dir: Path, timeout: float) -> dict:
    if "page_urls" in doc:
        # A document that exists only as a set of live web pages (no single
        # PDF/DOCX attachment) -- one page_url becomes one committed page,
        # a natural boundary rather than an arbitrary one.
        html_paths = [fetch_html_page(u, cache_dir, timeout) for u in doc["page_urls"]]
        text = "\f".join(extract_html_text(p) for p in html_paths) + "\f"
        source_hash = hashlib.sha256(b"".join(p.read_bytes() for p in html_paths)).hexdigest()
    else:
        src_path = fetch_attachment(doc, cache_dir, timeout)
        fmt = doc.get("attachment_format", "pdf")
        text = extract_text(
            src_path, doc["language"], cache_dir, timeout, fmt=fmt, allow_ocr=doc.get("allow_ocr", False)
        )
        source_hash = hashlib.sha256(src_path.read_bytes()).hexdigest()

    doc_dir = out_dir / doc["facet"] / doc["language"] / doc["id"]
    doc_dir.mkdir(parents=True, exist_ok=True)
    text_path = doc_dir / "text.txt"
    text_path.write_text(text, encoding="utf-8")

    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages = pages[:-1]
    page_lengths = [len(p) for p in pages] or [0]

    meta = dict(doc)
    meta.update(
        {
            "text_path": str(text_path.relative_to(out_dir.parent)),
            # The source (a Zotero attachment, a direct URL, or a set of
            # web pages) is a live, mutable location -- someone could
            # replace it with a different scan, edition, or edit. This hash
            # is recorded so a future re-run that gets different bytes
            # surfaces as a manifest diff (a committed-text change with no
            # corresponding DOCS edit) rather than silently overwriting
            # "reproducible" text with new content. Hashed on the fetched
            # source bytes, not a docx->pdf conversion output that no
            # longer exists in this pipeline.
            "source_attachment_sha256": source_hash,
            "page_count": len(pages),
            "char_count": len(text),
            "page_length_chars_min": min(page_lengths),
            "page_length_chars_median": sorted(page_lengths)[len(page_lengths) // 2],
            "page_length_chars_max": max(page_lengths),
        }
    )

    if "cross_lingual_pair" in doc:
        pair = doc["cross_lingual_pair"]
        pair_src = fetch_attachment(pair, cache_dir, timeout)
        pair_text = extract_text(pair_src, pair["language"], cache_dir, timeout)
        pair_text_path = doc_dir / "cross-lingual-reference-en.txt"
        pair_text_path.write_text(pair_text, encoding="utf-8")
        pair_pages = pair_text.split("\f")
        if pair_pages and pair_pages[-1] == "":
            pair_pages = pair_pages[:-1]
        meta["cross_lingual_pair"] = {
            **pair,
            "text_path": str(pair_text_path.relative_to(out_dir.parent)),
            # Same fields as the main document's meta, for the same reason:
            # this file is fetched and committed too, so it deserves the
            # same drift-detection and size record, not just a path.
            "page_count": len(pair_pages),
            "char_count": len(pair_text),
            "source_attachment_sha256": hashlib.sha256(pair_src.read_bytes()).hexdigest(),
        }
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out-dir",
        default=str(Path(__file__).parent / "corpus"),
        help="where to write text + manifest.json (default: bench/fixtures/corpus)",
    )
    ap.add_argument(
        "--cache-dir",
        default=str(Path(__file__).parents[2] / "corpus-cache"),
        help=(
            "scratch cache for downloaded PDFs and OCR page renders (repo root, "
            "gitignored, same convention as fork/ and upstream.git/) -- kept "
            "outside bench/ so its binaries don't reach check_models.py's scan"
        ),
    )
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()

    out_dir = Path(a.out_dir)
    cache_dir = Path(a.cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    manifest = [build_one(doc, out_dir, cache_dir, a.timeout) for doc in DOCS]
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for m in manifest:
        log.info("%s: %d pages, %d chars", m["id"], m["page_count"], m["char_count"])


if __name__ == "__main__":
    main()
