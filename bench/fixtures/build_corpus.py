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
text under the same doc id. `source_pdf_sha256` in manifest.json exists to
make that visible -- a re-run whose hash for an id changed is a signal to
review the diff before trusting it, not proof nothing changed.
"""
import argparse
import hashlib
import json
import logging
import os
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

# tesseract/tessdata use ISO 639-2/T three-letter codes; DOCS uses the
# two-letter codes the rest of this repo (and Zotero's own `language` field)
# uses. Only the languages DOCS actually needs are mapped.
TESSERACT_LANG = {"fr": "fra", "en": "eng", "de": "deu", "vi": "vie"}

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
    result = subprocess.run(["pandoc", "-t", "plain", str(docx_path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"pandoc failed on {docx_path} (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout


def ensure_tessdata(tess_lang: str, cache_dir: Path, timeout: float) -> Path:
    """Return a tessdata dir containing `tess_lang`, fetching it if this
    machine's system tesseract install doesn't already have it (e.g. only
    eng/fra here)."""
    system_check = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
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


def ocr_pdf(pdf_path: Path, lang: str, cache_dir: Path, timeout: float) -> str:
    tess_lang = TESSERACT_LANG.get(lang)
    if tess_lang is None:
        raise SystemExit(f"no tesseract language mapping for {lang!r} -- add one to TESSERACT_LANG")
    tessdata_dir = ensure_tessdata(tess_lang, cache_dir, timeout)
    env = {"TESSDATA_PREFIX": str(tessdata_dir)} if tessdata_dir != Path() else {}
    pages_dir = cache_dir / f"{pdf_path.stem}-pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", "300", str(pdf_path), str(pages_dir / "p")], check=True
    )
    chunks = []
    for png in sorted(pages_dir.glob("p-*.png")):
        result = subprocess.run(
            ["tesseract", str(png), "-", "-l", tess_lang],
            capture_output=True,
            text=True,
            env={**os.environ, **env},
        )
        if result.returncode != 0:
            raise SystemExit(
                f"tesseract failed on {png} (exit {result.returncode}): {result.stderr.strip()}"
            )
        chunks.append(result.stdout)
    return "\f".join(chunks) + "\f"


def extract_text(src_path: Path, lang: str, cache_dir: Path, timeout: float, fmt: str = "pdf") -> str:
    if fmt == "docx":
        return unicodedata.normalize("NFC", extract_docx_text(src_path))
    pdf_path = src_path
    result = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"pdftotext failed on {pdf_path} (exit {result.returncode}): {result.stderr.strip()}")
    text = result.stdout
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages = pages[:-1]
    density = len(text) / max(len(pages), 1)
    if density < MIN_CHARS_PER_PAGE:
        log.info(
            "%s: %.0f chars/page over %d pages looks like a missing text layer -- OCR'ing",
            pdf_path.name,
            density,
            len(pages),
        )
        text = ocr_pdf(pdf_path, lang, cache_dir, timeout)
    # NFC, not whatever pdftotext/tesseract happened to emit -- so a future
    # re-run (different tesseract build, a replaced Zotero attachment) can't
    # silently commit NFD text under the same doc id that looks identical
    # rendered but fails exact/substring matches against NFC query text.
    return unicodedata.normalize("NFC", text)


def build_one(doc: dict, out_dir: Path, cache_dir: Path, timeout: float) -> dict:
    src_path = fetch_attachment(doc, cache_dir, timeout)
    fmt = doc.get("attachment_format", "pdf")
    text = extract_text(src_path, doc["language"], cache_dir, timeout, fmt=fmt)

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
            # The source (a Zotero attachment, or a direct URL) is a live,
            # mutable location -- someone could replace it with a different
            # scan or a correction. This hash is recorded so a future re-run
            # that gets different bytes surfaces as a manifest diff (a
            # committed-text change with no corresponding DOCS edit) rather
            # than silently overwriting "reproducible" text with new content.
            # Hashed on the fetched source file, not the docx->pdf conversion
            # output, so it tracks what was actually fetched from the source.
            "source_attachment_sha256": hashlib.sha256(src_path.read_bytes()).hexdigest(),
            "page_count": len(pages),
            "char_count": len(text),
            "page_length_chars_min": min(page_lengths),
            "page_length_chars_median": sorted(page_lengths)[len(page_lengths) // 2],
            "page_length_chars_max": max(page_lengths),
        }
    )

    if "cross_lingual_pair" in doc:
        pair = doc["cross_lingual_pair"]
        pair_pdf = fetch_attachment(pair, cache_dir, timeout)
        pair_text = extract_text(pair_pdf, pair["language"], cache_dir, timeout)
        pair_text_path = doc_dir / "cross-lingual-reference-en.txt"
        pair_text_path.write_text(pair_text, encoding="utf-8")
        meta["cross_lingual_pair"] = {
            **pair,
            "text_path": str(pair_text_path.relative_to(out_dir.parent)),
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
