#!/usr/bin/env python3
"""Fetch the fixture corpus's source bytes from the archives the recipe names,
and check each against its pinned hash.

The recipe (`recipe.json`, beside this script) is the first of the fixture's
three layers (DECISIONS.md, 2026-09-02, "The golden fixture corpus"): one
record per document naming a public archive, a persistent identifier, the
address of the bytes, and their sha256. This script turns that record into
files on disk and says, per document, whether the archive still serves the
bytes the recipe pinned. It extracts nothing. Text enters the fixture only as
the export of Zotero's own extraction, the third layer, which is a later
script's job.

Why a hash and not just an address: an identifier can be persistent while the
bytes behind it move. Gutenberg revises texts in place, Commons files are
overwritten with history kept, arXiv regenerates a version's PDF from source,
and an unversioned database of record can replace a corrected translation
under the same id. The hash makes each of those a visible mismatch in this
script's report rather than a silent change in the corpus. A mismatch is
something to inspect, never something to fix by editing the hash: re-pinning
is a commit whose diff is the review artifact.

The cache lives outside `bench/` (default `corpus-cache/` at the repo root,
git-ignored) so that scanned PDFs never land where `check_models.py` scans for
text. A truncated download must never be trusted on the next run, so every
fetch goes to a `.partial` file and is renamed only after the size and magic
bytes look right.
"""

import argparse
import codecs
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

log = logging.getLogger("fetch_recipe")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_RECIPE = HERE / "recipe.json"
DEFAULT_CACHE = REPO / "corpus-cache"

#: Some archive front ends answer 403 to a bare urllib agent while serving the
#: same bytes to a browser. A browser-shaped agent string is the difference
#: between "blocked" and "fetched" on FAOLEX and Gallica.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0"

#: First bytes each format must open with. An HTML error page served with a
#: 200 fails this check instead of poisoning the cache. The office formats,
#: ODT and a plain zip all open as a ZIP container (`PK`); a gzip'd tarball
#: opens with the gzip magic. Text formats (wikitext, txt, md, html) carry no
#: magic; their charset is declared on the recipe and checked by decoding.
MAGIC = {
    "pdf": b"%PDF", "djvu": b"AT&T", "wikitext": None, "txt": None, "html": None, "md": None,
    "epub": b"PK", "docx": b"PK", "xlsx": b"PK", "odt": b"PK", "zip": b"PK",
    "rtf": b"{\\rtf", "jpg": b"\xff\xd8", "png": b"\x89PNG", "tgz": b"\x1f\x8b",
}
#: The formats Zotero reads as text, and for which the recipe must declare the
#: file's charset (ticket 0721): Zotero guesses when the attachment carries none,
#: and guessed windows-1252 for UTF-8 Vietnamese on ticket 0632's real run.
TEXT_FORMATS = frozenset({"txt", "wikitext", "html", "md"})


def validate_download_format(path: Path, fmt: str, charset: str | None = None) -> str | None:
    """Return a native-format defect, or ``None`` when the bytes are plausible.

    Prefix magic is sufficient for PDF and DjVu. Text must decode under the
    charset the recipe declares (UTF-8 when it declares none: the legacy
    encodings of the 1990s are a corpus dimension, and an authentic
    windows-1258 or koi8-r file is checked against its own declaration, never
    converted), HTML must contain HTML markup rather than arbitrary text, and
    an EPUB is a ZIP whose first, uncompressed member declares the EPUB media
    type.
    """
    codec = "utf-8-sig" if charset is None or charset.lower() in {"utf-8", "utf8"} else charset
    shown = "UTF-8" if codec == "utf-8-sig" else charset
    if fmt in {"txt", "wikitext", "md"}:
        try:
            decoder = codecs.getincrementaldecoder(codec)()
        except LookupError:
            return f"unknown charset {charset!r}"
        try:
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    if b"\x00" in chunk:
                        return f"expected {shown} text, got NUL bytes"
                    decoder.decode(chunk)
                decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            return f"expected {shown} text"
    elif fmt == "html":
        try:
            head = path.read_bytes()[:16_384].decode(codec, errors="strict" if codec == "utf-8-sig" else "replace")
        except LookupError:
            return f"unknown charset {charset!r}"
        except UnicodeDecodeError:
            return f"expected {shown} HTML"
        if not re.search(r"<!doctype\s+html|<html(?:\s|>)", head, re.IGNORECASE):
            return "expected HTML document markup"
    elif fmt == "epub":
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if (not members or members[0].filename != "mimetype" or
                        members[0].compress_type != zipfile.ZIP_STORED or
                        archive.read(members[0]) != b"application/epub+zip"):
                    return "expected EPUB mimetype as first uncompressed member"
        except (OSError, zipfile.BadZipFile):
            return "expected EPUB ZIP container"
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_atomic(url: str, dest: Path, timeout: float, magic: bytes | None, min_size: int,
                    fmt: str | None = None, charset: str | None = None) -> None:
    """Fetch `url` to `dest` through a temp file and a rename."""
    tmp = dest.with_suffix(dest.suffix + ".partial")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    size = tmp.stat().st_size
    if size < min_size:
        tmp.unlink()
        raise RuntimeError(f"{url}: {size} bytes, expected at least {min_size}")
    if magic is not None:
        with open(tmp, "rb") as fh:
            head = fh.read(len(magic))
        if head != magic:
            tmp.unlink()
            raise RuntimeError(f"{url}: expected {magic!r} at file start, got {head!r}")
    defect = validate_download_format(tmp, fmt, charset) if fmt else None
    if defect:
        tmp.unlink()
        raise RuntimeError(f"{url}: {defect}")
    os.replace(tmp, dest)


#: HTTP answers that mean "not for scripts", as opposed to "not now".
CHALLENGE_CODES = frozenset({401, 403, 405, 429})


def classify_failure(exc: Exception) -> str:
    """`blocked` when the archive refused a scripted client, `unfetched` otherwise.

    The two need different actions and share no remedy: a challenge page (HAL's
    Anubis, Gallica's ALTCHA, a WAF captcha) is fetched once in a browser and
    pinned by hand, while a timeout or a 5xx is retried. A challenge shows up
    either as one of `CHALLENGE_CODES` or as an HTML page served with a 200 where
    a PDF was expected, which is what the magic-byte check turns into a
    RuntimeError.
    """
    if isinstance(exc, urllib.error.HTTPError) and exc.code in CHALLENGE_CODES:
        return "blocked"
    if isinstance(exc, RuntimeError) and "at file start" in str(exc):
        return "blocked"
    return "unfetched"


def fetch_one(doc: dict, cache_dir: Path, timeout: float) -> dict:
    """Fetch one recipe entry and compare its hash. Returns a report row."""
    fmt = doc.get("bytes_format", "pdf")
    dest = cache_dir / f"{doc['id']}.{fmt}"
    row = {"id": doc["id"], "archive": doc["archive"], "path": str(dest)}
    if doc["archive"] in DROPPED_ARCHIVES and not dest.exists():
        # Not fetched: the archive fails the admission test, and the bytes are not
        # in hand. Reported as its own status so a run never counts it as an outage.
        row["status"] = "dropped-archive"
        row["reason"] = DROPPED_ARCHIVES[doc["archive"]]
        return row
    if not dest.exists():
        log.info("fetching %s from %s", doc["id"], doc["bytes_url"])
        try:
            download_atomic(doc["bytes_url"], dest, timeout, MAGIC.get(fmt), doc.get("min_size", 1_000), fmt,
                            doc.get("charset"))
        except Exception as exc:  # noqa: BLE001 — one dead archive must not stop the others
            row["status"] = classify_failure(exc)
            row["reason"] = str(exc)
            return row
    got = sha256_of(dest)
    row["sha256"] = got
    if doc.get("sha256") is None:
        row["status"] = "unpinned"
    elif got == doc["sha256"]:
        row["status"] = "match"
    else:
        row["status"] = "MISMATCH"
        row["pinned"] = doc["sha256"]
    return row


#: The archives a fixture document may come from are data, not code
#: (`archives.json`, beside this script): each entry carries its hosts, its
#: identifier form, its version rule and the admission probe under the five-part
#: test ratified 2026-09-04 (robot-open, licence-open, reputable, byte-exact
#: identifier, ten years old). A new archive is admitted by recording a real
#: probe there, never by editing a set here. The module-level names below are
#: derived views, kept because the tests and the README read them by name.
ARCHIVES_FILE = HERE / "archives.json"


def load_archives(path: Path = ARCHIVES_FILE) -> dict[str, dict]:
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)["archives"]
    archives: dict[str, dict] = {}
    for entry in entries:
        name = entry["name"]
        assert name not in archives, f"{path}: duplicate archive {name}"
        assert entry.get("hosts"), f"{path}: {name} names no host"
        assert entry.get("dropped") or entry.get("admission"), f"{path}: {name} records no admission probe"
        if entry.get("dropped"):
            assert entry.get("dropped_reason"), f"{path}: {name} is dropped with no reason"
        archives[name] = entry
    return archives


ARCHIVES = load_archives()
ADMITTED_ARCHIVES = frozenset(name for name, entry in ARCHIVES.items() if not entry.get("dropped"))
#: Dropped archives, by name, with the ruling that dropped them: an attachment
#: naming one is refused, and `fetch_recipe.py` never fetches from it.
DROPPED_ARCHIVES = {name: entry["dropped_reason"] for name, entry in ARCHIVES.items() if entry.get("dropped")}
VERSIONED_ARCHIVES = frozenset(name for name, entry in ARCHIVES.items() if entry.get("version_rule") == "vN")
UNVERSIONED_ARCHIVES = frozenset(name for name, entry in ARCHIVES.items() if entry.get("version_rule") == "unversioned")
#: A version on an open-archive identifier is `vN`, the form HAL and arXiv print
#: and Zenodo's version DOIs stand in for; "final" or "latest" names a lineage.
VERSION = re.compile(r"^v\d+$")
#: The host each archive serves bytes from. A URL under an admitted archive's
#: label but on some other host is the closed PR's defect in miniature — a
#: personal or unaudited host wearing an archive's name — so the host must
#: belong to the archive declared. Matched on the hostname's suffix, lowercased.
ARCHIVE_HOSTS = {name: tuple(entry["hosts"]) for name, entry in ARCHIVES.items()}
IDENTIFIER_PATTERNS = {
    name: re.compile(entry["identifier_pattern"])
    for name, entry in ARCHIVES.items() if entry.get("identifier_pattern")
}
IDENTIFIER_ALLOWLISTS = {
    name: frozenset(entry["identifier_allowlist"])
    for name, entry in ARCHIVES.items() if entry.get("identifier_allowlist")
}
#: FAOLEX is admitted for one document by the ruling of 2026-09-02, not as an
#: archive in general; a second FAOLEX record needs its own ruling.
FAOLEX_ADMITTED = IDENTIFIER_ALLOWLISTS.get("faolex", frozenset())
#: Hosts that are publishers or personal sites, never archives. Listed because
#: each one appeared as a source in the closed PR #151. Compared lowercased.
REFUSED_HOSTS = ("minh.haduong.com", "zotero.org", "www.gov.uk", "chinhphu.vn", "vbpl.vn", "thuvienphapluat.vn")
LEGACY_REQUIRED = ("id", "title", "author", "year", "language", "tier", "facet", "archive", "identifier", "bytes_url", "sha256", "license_basis")
PARENT_REQUIRED = ("id", "title", "author", "year", "language", "tier", "facet", "item_type", "type_fidelity", "work_id", "work_relations", "structural_features", "attachments", "topic", "stratum")
ATTACHMENT_REQUIRED = ("id", "language", "role", "relation", "selection_expectation", "cap_expectations", "archive", "identifier", "bytes_url", "sha256", "license_basis")
LANGUAGES = frozenset({"en", "fr", "de", "vi", "zh", "ar", "ru", "hi", "es", "la", "pt"})
TIERS = frozenset({"MUST", "SHOULD"})
FACETS = frozenset({"core", "notes", "group", "deep-body"})
TYPE_FIDELITY = frozenset({"correct", "intentionally-wrong"})
ATTACHMENT_RELATIONS = frozenset({"primary", "same-text-different-format", "translation", "article", "presentation"})
ATTACHMENT_ROLES = frozenset({"primary", "article", "presentation", "translation", "alternate-format"})
#: `same-subject` is a Wikipedia interlanguage link (ruling 2026-09-06): the same
#: subject in another language is never recorded as a translation.
WORK_RELATIONS = frozenset({"translation", "same-work", "near-duplicate-publication", "book-chapter", "metadata-conflicting-duplicate", "same-subject"})
#: The author's library's topics (ruling 2026-09-06); a record kept off-topic
#: says why in `retained_reason`.
TOPICS = frozenset({"economics", "uncertainty", "energy", "environment", "development", "sts", "hss"})
#: The two sampled strata: a representative core following the census
#: marginals, an adversarial reserve whose members each name their mechanisms.
STRATA = frozenset({"core", "reserve"})
CITATION_FIELDS = frozenset({"doi", "isbn", "url"})
EXTRACTION_EXPECTATIONS = frozenset({"indexed", "skipped-first-with-text"})
CAP_RESULTS = frozenset({"crosses", "does-not-cross"})
COMBINED_CAP_RESULTS = frozenset({"both", "page-only", "char-only", "neither"})
STRUCTURAL_FEATURES = frozenset({"table", "figure-caption", "annex", "appendix", "footnote", "endnote", "multi-column", "equation-heavy-prose"})
STRUCTURAL_EXPECTATIONS = frozenset({"present", "absent"})
#: A declared failure control (DECISIONS.md, 2026-09-03: every failure control
#: declares its expected terminal or degradation state and whether it takes part
#: in golden answers). `unindexed` is Zotero's own state name for an attachment
#: it finished trying and left without full text; the export accepts such an
#: attachment only when its reindex observed exactly that state.
FAILURE_CONTROL_FIELDS = frozenset({"expected_state", "expected_degradation", "answer_set_participation"})
FAILURE_CONTROL_STATES = frozenset({"unindexed"})
HEX64 = frozenset("0123456789abcdef")
#: An id is one path component, because it names the cache file: `../x` or a
#: slash would write outside the cache directory.
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def validate(recipe: list[dict]) -> list[str]:
    """Every way a recipe entry can break the provenance rulings, by entry id.

    Returns the list of offences; an empty list is a valid recipe. Kept as data
    rather than exceptions so a test can assert on the whole set at once and the
    script can print them all before refusing.
    """
    found: list[str] = []
    seen: set[str] = set()
    seen_attachment_ids: set[str] = set()
    seen_note_ids: set[str] = set()
    for doc in recipe:
        did = doc.get("id", "<no id>")
        legacy = "attachments" not in doc
        for key in LEGACY_REQUIRED if legacy else PARENT_REQUIRED:
            if key not in doc:
                found.append(f"{did}: missing {key}")
        if did in seen:
            found.append(f"{did}: duplicate id")
        seen.add(did)
        if not SLUG.match(str(did)):
            found.append(f"{did}: id is not a lowercase slug (one path component)")
        for key in doc:
            if key.startswith("zotero_"):
                found.append(f"{did}: {key} names a personal library")
        if doc.get("language") not in LANGUAGES:
            found.append(f"{did}: language {doc.get('language')!r} unknown")
        if doc.get("tier") not in TIERS:
            found.append(f"{did}: tier {doc.get('tier')!r} unknown")
        if doc.get("facet") not in FACETS:
            found.append(f"{did}: facet {doc.get('facet')!r} unknown")
        if not legacy:
            if not isinstance(doc.get("item_type"), str) or not doc.get("item_type"):
                found.append(f"{did}: item_type is empty")
            if doc.get("type_fidelity") not in TYPE_FIDELITY:
                found.append(f"{did}: type_fidelity {doc.get('type_fidelity')!r} unknown")
            if doc.get("type_fidelity") == "intentionally-wrong" and not doc.get("type_fidelity_reason"):
                found.append(f"{did}: intentionally-wrong type has no type_fidelity_reason")
            if not SLUG.match(str(doc.get("work_id", ""))):
                found.append(f"{did}: work_id is not a lowercase slug")
            if not isinstance(doc.get("work_relations"), list):
                found.append(f"{did}: work_relations must be a list")
            else:
                for relation in doc["work_relations"]:
                    if not isinstance(relation, dict):
                        found.append(f"{did}: each work relation must be an object")
                        continue
                    if set(relation) != {"type", "target"}:
                        found.append(f"{did}: work relation must contain only type and target")
                    if relation.get("type") not in WORK_RELATIONS:
                        found.append(f"{did}: work relation type {relation.get('type')!r} unknown")
                    if not SLUG.match(str(relation.get("target", ""))):
                        found.append(f"{did}: work relation target is not a lowercase slug")
            record_only = doc.get("record_only", False)
            if not isinstance(record_only, bool):
                found.append(f"{did}: record_only must be a boolean")
            if not isinstance(doc.get("attachments"), list):
                found.append(f"{did}: attachments must be a list")
            elif not doc["attachments"] and not record_only:
                found.append(f"{did}: attachments must be a non-empty list unless the record is record_only")
            elif doc["attachments"] and record_only:
                found.append(f"{did}: a record_only record carries no attachments")
            if doc.get("topic") not in TOPICS:
                found.append(f"{did}: topic {doc.get('topic')!r} is not one of {sorted(TOPICS)}")
            if doc.get("stratum") not in STRATA:
                found.append(f"{did}: stratum {doc.get('stratum')!r} is not one of {sorted(STRATA)}")
            mechanisms = doc.get("mechanisms", [])
            if not isinstance(mechanisms, list) or any(not isinstance(m, str) or not m.strip() for m in mechanisms):
                found.append(f"{did}: mechanisms must be a list of non-empty strings")
            elif doc.get("stratum") == "reserve" and not mechanisms:
                found.append(f"{did}: a reserve member names the mechanisms it carries")
            if "language_field" in doc and not isinstance(doc["language_field"], str):
                found.append(f"{did}: language_field is the exact string written to Zotero, so it must be a string")
            if "retained_reason" in doc and (not isinstance(doc["retained_reason"], str) or not doc["retained_reason"].strip()):
                found.append(f"{did}: retained_reason is empty")
            citation = doc.get("citation", {})
            if not isinstance(citation, dict) or not set(citation) <= CITATION_FIELDS:
                found.append(f"{did}: citation must be an object with keys among {sorted(CITATION_FIELDS)}")
            elif any(not isinstance(value, str) or not value.strip() for value in citation.values()):
                found.append(f"{did}: citation values must be non-empty strings")
            notes = doc.get("notes", [])
            if not isinstance(notes, list):
                found.append(f"{did}: notes must be a list")
            else:
                for note in notes:
                    if not isinstance(note, dict) or set(note) != {"id", "html"}:
                        found.append(f"{did}: each note is an object with exactly id and html")
                        continue
                    if not SLUG.match(str(note["id"])):
                        found.append(f"{did}: note id {note['id']!r} is not a lowercase slug")
                    elif note["id"] in seen_note_ids:
                        found.append(f"{did}: note id {note['id']!r} is not globally unique")
                    seen_note_ids.add(note["id"])
                    if not isinstance(note["html"], str) or not note["html"].strip():
                        found.append(f"{did}: note {note['id']!r} has no html")
            features = doc.get("structural_features")
            if not isinstance(features, list):
                found.append(f"{did}: structural_features must be a list")
            else:
                attachment_names = {a.get("id") for a in doc.get("attachments", []) if isinstance(a, dict)}
                for feature in features:
                    if not isinstance(feature, dict) or set(feature) != {"feature", "attachment_id", "locator", "extraction_expectation"}:
                        found.append(f"{did}: structural feature must contain feature, attachment_id, locator, and extraction_expectation")
                        continue
                    if feature["feature"] not in STRUCTURAL_FEATURES:
                        found.append(f"{did}: structural feature {feature['feature']!r} unknown")
                    if feature["attachment_id"] not in attachment_names:
                        found.append(f"{did}: structural feature names an unknown attachment")
                    if not isinstance(feature["locator"], str) or not feature["locator"].strip():
                        found.append(f"{did}: structural feature locator is empty")
                    if feature["extraction_expectation"] not in STRUCTURAL_EXPECTATIONS:
                        found.append(f"{did}: structural extraction expectation unknown")
        sources = [doc] if legacy else doc.get("attachments", [])
        sources = sources if isinstance(sources, list) else []
        attachment_ids: set[str] = set()
        for source in sources:
            if not isinstance(source, dict):
                found.append(f"{did}: attachment must be an object")
                continue
            aid = source.get("id", did)
            label = f"{did}/{aid}"
            for key in () if legacy else ATTACHMENT_REQUIRED:
                if key not in source:
                    found.append(f"{label}: missing {key}")
            if aid in attachment_ids:
                found.append(f"{label}: duplicate attachment id")
            attachment_ids.add(aid)
            if aid in seen_attachment_ids:
                found.append(f"{label}: attachment id is not globally unique")
            seen_attachment_ids.add(aid)
            if not SLUG.match(str(aid)):
                found.append(f"{label}: attachment id is not a lowercase slug")
            if not legacy and source.get("relation") not in ATTACHMENT_RELATIONS:
                found.append(f"{label}: attachment relation {source.get('relation')!r} unknown")
            if not legacy and source.get("role") not in ATTACHMENT_ROLES:
                found.append(f"{label}: attachment role {source.get('role')!r} unknown")
            if not legacy and source.get("selection_expectation") not in EXTRACTION_EXPECTATIONS:
                found.append(f"{label}: selection_expectation {source.get('selection_expectation')!r} unknown")
            if source.get("selection_expectation") == "skipped-first-with-text" and not source.get("skip_reason"):
                found.append(f"{label}: skipped attachment has no skip_reason")
            if not legacy:
                caps = source.get("cap_expectations")
                if not isinstance(caps, dict) or set(caps) != {"pages", "chars", "combined", "locators"}:
                    found.append(f"{label}: cap_expectations must contain pages, chars, combined, and locators")
                else:
                    if caps["pages"] not in CAP_RESULTS or caps["chars"] not in CAP_RESULTS or caps["combined"] not in COMBINED_CAP_RESULTS:
                        found.append(f"{label}: cap crossing expectation unknown")
                    crosses_page = caps["pages"] == "crosses"
                    crosses_chars = caps["chars"] == "crosses"
                    expected_combined = (
                        "both" if crosses_page and crosses_chars else
                        "page-only" if crosses_page else
                        "char-only" if crosses_chars else "neither"
                    )
                    if caps["combined"] != expected_combined:
                        found.append(f"{label}: combined cap expectation contradicts page/char expectations")
                    locators = caps["locators"]
                    if not isinstance(locators, dict):
                        found.append(f"{label}: cap locators must be an object")
                    else:
                        for boundary, result in (("page", caps["pages"]), ("char", caps["chars"])):
                            required = {f"before_{boundary}_cap", f"after_{boundary}_cap"} if result == "crosses" else set()
                            if any(not isinstance(locators.get(key), str) or not locators[key].strip() for key in required):
                                found.append(f"{label}: crossing {boundary} cap needs before/after locators")
            fmt = source.get("bytes_format", "pdf")
            if fmt not in MAGIC:
                found.append(f"{label}: bytes_format {source.get('bytes_format')!r} is not one of {sorted(MAGIC)}")
            charset = source.get("charset")
            if charset is not None and (not isinstance(charset, str) or not charset.strip()):
                found.append(f"{label}: charset must be a non-empty string when given")
            elif charset is not None and not _known_charset(charset):
                found.append(f"{label}: charset {charset!r} is not a codec Python knows")
            elif not legacy and fmt in TEXT_FORMATS and charset is None:
                found.append(f"{label}: a {fmt} attachment declares its charset (Zotero guesses when the item carries none)")
            if "content_type_declared" in source and (
                    not isinstance(source["content_type_declared"], str) or "/" not in source["content_type_declared"]):
                found.append(f"{label}: content_type_declared must be a MIME type")
            if "min_body_chars" in source and (
                    not isinstance(source["min_body_chars"], int) or isinstance(source["min_body_chars"], bool)
                    or source["min_body_chars"] < 0):
                found.append(f"{label}: min_body_chars must be a non-negative integer")
            if "encoding_note" in source and not isinstance(source["encoding_note"], str):
                found.append(f"{label}: encoding_note must be a string")
            if "failure_control" in source:
                control = source["failure_control"]
                if not isinstance(control, dict) or set(control) != FAILURE_CONTROL_FIELDS:
                    found.append(f"{label}: failure_control must contain exactly {sorted(FAILURE_CONTROL_FIELDS)}")
                else:
                    if control["expected_state"] not in FAILURE_CONTROL_STATES:
                        found.append(f"{label}: failure_control expected_state {control['expected_state']!r} unknown")
                    if not isinstance(control["expected_degradation"], str) or not control["expected_degradation"].strip():
                        found.append(f"{label}: failure_control expected_degradation is empty")
                    if control["answer_set_participation"] != "none":
                        found.append(f"{label}: a failure control takes no part in golden answer sets")
            if source.get("language", doc.get("language")) not in LANGUAGES:
                found.append(f"{label}: language {source.get('language')!r} unknown")
            _validate_source(source, label, found, legacy=legacy)
        if not legacy:
            by_language: dict[str, list[dict]] = {}
            for source in sources:
                if isinstance(source, dict):
                    by_language.setdefault(source.get("language"), []).append(source)
            for language, renderings in by_language.items():
                indexed = [source for source in renderings if source.get("selection_expectation") == "indexed"]
                if len(indexed) != 1 or (indexed and indexed[0] is not renderings[0]):
                    found.append(f"{did}: language {language!r} must index exactly the first attachment with text")
    return found


def _known_charset(charset: str) -> bool:
    try:
        codecs.lookup(charset)
    except LookupError:
        return False
    return True


def _validate_source(source: dict, label: str, found: list[str], *, legacy: bool = False) -> None:
    archive = source.get("archive")
    if archive in DROPPED_ARCHIVES:
        # A legacy-shape record (no `attachments`) on a dropped archive is tolerated
        # until the recipe lane retires it; it is never fetched (see fetch_one).
        if not legacy:
            found.append(f"{label}: archive {archive!r} was dropped: {DROPPED_ARCHIVES[archive]}")
    elif archive not in ADMITTED_ARCHIVES:
        found.append(f"{label}: archive {archive!r} is not admitted")
    if archive in VERSIONED_ARCHIVES and not VERSION.match(str(source.get("version") or "")):
        found.append(f"{label}: {archive} identifier carries no version of the form vN")
    if archive in UNVERSIONED_ARCHIVES and source.get("version") is not None:
        found.append(f"{label}: {archive} identifier is unversioned")
    pattern = IDENTIFIER_PATTERNS.get(archive)
    if pattern is not None and not pattern.match(str(source.get("identifier") or "")):
        found.append(f"{label}: {archive} identifier {source.get('identifier')!r} does not match {pattern.pattern}"
                     + (" (Project Gutenberg identifier is not a numeric ebook number)" if archive == "project-gutenberg" else ""))
    allowlist = IDENTIFIER_ALLOWLISTS.get(archive)
    if allowlist is not None and source.get("identifier") not in allowlist:
        found.append(f"{label}: {archive.upper()} is admitted for {sorted(allowlist)} only, not {source.get('identifier')!r}")
    url = source.get("bytes_url") or ""
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in REFUSED_HOSTS):
        found.append(f"{label}: bytes_url {url} is a publisher or personal host, not an archive")
    allowed = ARCHIVE_HOSTS.get(archive, ())
    if url and not any(host == h or host.endswith("." + h) for h in allowed):
        found.append(f"{label}: bytes_url host {host!r} does not belong to archive {archive!r}")
    digest = source.get("sha256")
    if digest is None and not source.get("sha256_reason"):
        found.append(f"{label}: sha256 is null with no sha256_reason")
    elif digest is not None and (len(digest) != 64 or not set(digest) <= HEX64):
        found.append(f"{label}: sha256 is not 64 hex characters")
    if not source.get("license_basis"):
        found.append(f"{label}: license_basis is empty")


def load_recipe(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        recipe = json.load(fh)
    assert isinstance(recipe, list), f"{path}: the recipe is a JSON array of documents"
    offences = validate(recipe)
    if offences:
        for line in offences:
            log.error("%s", line)
        raise SystemExit(f"{path}: {len(offences)} provenance offence(s); nothing fetched")
    return recipe


def run(recipe: list[dict], cache_dir: Path, timeout: float, only: set[str] | None) -> list[dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for doc in recipe:
        sources = doc.get("attachments", [doc])
        for source in sources:
            if only and only.isdisjoint((source["id"], doc["id"])):
                continue
            if source.get("bytes_url") is None:
                rows.append({"id": source["id"], "archive": source["archive"], "status": "no-bytes-url"})
                continue
            rows.append(fetch_one(source, cache_dir, timeout))
    return rows


#: Statuses that mean the run failed to do its job. `blocked` is expected for
#: the archives that refuse scripts, and `unpinned` is a recipe entry that has
#: not been hashed yet; neither is a failure of this run.
FAILING = frozenset({"MISMATCH", "unfetched"})


def exit_status(rows: list[dict]) -> int:
    """1 when any document mismatched its pin or could not be fetched, else 0."""
    return 1 if any(r["status"] in FAILING for r in rows) else 0


def report(rows: list[dict]) -> None:
    """One line per document, then a count per status."""
    width = max((len(r["id"]) for r in rows), default=8)
    for r in rows:
        extra = r.get("reason") or (f"pinned {r['pinned'][:12]}" if "pinned" in r else "")
        print(f"{r['id']:<{width}}  {r['status']:<11} {r.get('sha256', '')[:12]:<12} {extra}")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("summary:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE, help="recipe.json to read")
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="where fetched bytes land (git-ignored)")
    ap.add_argument("--only", action="append", default=None, metavar="ID", help="fetch only this document id (repeatable)")
    ap.add_argument("--timeout", type=float, default=600.0, help="seconds per download")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    rows = run(load_recipe(args.recipe), args.cache_dir, args.timeout, set(args.only) if args.only else None)
    report(rows)
    sys.exit(exit_status(rows))


if __name__ == "__main__":
    main()
