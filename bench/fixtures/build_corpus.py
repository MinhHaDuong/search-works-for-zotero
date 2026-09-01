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
    {
        "id": "soddy-1926-wealth-virtual-wealth-and-debt",
        "title": "Wealth, Virtual Wealth and Debt: The Solution of the Economic Paradox",
        "author": "Frederick Soddy",
        "year": 1926,
        "language": "en",
        "facet": "core",
        "zotero_item_key": "QTXB5WHP",
        "zotero_attachment_key": "M42ES9TQ",
        "source": "scanned attachment in the author's Zotero library",
        "license_basis": (
            "Public domain in the US: published 1926, pre-1931 bright-line. "
            "UK/EU term (life+70; Soddy died 1956) runs to 31 Dec 2026 -- note this "
            "if the corpus is ever redistributed under UK/EU law specifically."
        ),
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


def fetch_pdf(attachment_key: str, cache_dir: Path, timeout: float) -> Path:
    dest = cache_dir / f"{attachment_key}.pdf"
    if dest.exists():
        return dest
    url = ZOTERO_FILE_URL.format(key=attachment_key)
    log.info("fetching %s", url)
    # 1 KB floor: PDF structural overhead (xref table, trailer, at least one
    # object) puts even a near-empty real PDF above this.
    _download_atomic(url, dest, timeout, magic=b"%PDF", min_size=1_000)
    return dest


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


def extract_text(pdf_path: Path, lang: str, cache_dir: Path, timeout: float) -> str:
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
    pdf_path = fetch_pdf(doc["zotero_attachment_key"], cache_dir, timeout)
    text = extract_text(pdf_path, doc["language"], cache_dir, timeout)

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
            # The Zotero attachment behind zotero_attachment_key is a live,
            # mutable source -- someone could replace it with a different
            # scan or a correction. This hash is recorded so a future re-run
            # that gets a different PDF surfaces as a manifest diff (a
            # committed-text change with no corresponding DOCS edit) rather
            # than silently overwriting "reproducible" text with new content.
            "source_pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "page_count": len(pages),
            "char_count": len(text),
            "page_length_chars_min": min(page_lengths),
            "page_length_chars_median": sorted(page_lengths)[len(page_lengths) // 2],
            "page_length_chars_max": max(page_lengths),
        }
    )

    if "cross_lingual_pair" in doc:
        pair = doc["cross_lingual_pair"]
        pair_pdf = fetch_pdf(pair["zotero_attachment_key"], cache_dir, timeout)
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
