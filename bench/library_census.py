#!/usr/bin/env python3
"""Ticket 0711 — read-only census of a real Zotero library, over the local API.

The Multilingual Menagerie's representative core has to *match* something, and
until now nothing said what. This measures the marginal distributions of the
author's own library — item types, attachments per item, attachment formats,
notes, languages, collections, full-text coverage and document lengths — so the
fixture can be quota-sampled against a real profile and claim representativeness
(conception/0029-golden-fixture-structure-review.md §3).

    python3 bench/library_census.py \\
        --output bench/results/0029-library-census/census.json \\
        --include-group 305258 --sqlite ~/data/Zotero/zotero.sqlite

**Read-only, and provably so.** Every request is a GET; the only network call
site is `http_fetch`, and `tests/test_library_census.py` asserts that no other
method is ever built. The optional SQLite supplement opens the database with
`mode=ro&immutable=1`, which never takes a lock and never writes a journal.

**Aggregate-only.** The artifact carries counts and quantiles. No item key, no
title, no file name, no creator, no note text leaves this process: titles are
read only to classify their script, notes only to measure their length, and
neither is retained.

Sources, and what each can and cannot see
-----------------------------------------

- **Local API** (`/api/users/0/…`, `/api/groups/<id>/…`): items with their
  data, the trash, and the `{key: version}` full-text census. It exposes no
  annotation items, no collections endpoint and no feed library — probed
  2026-09-06 on Zotero 10.0.1: `itemType=annotation` answers 0 against 38 rows
  in the database, `/collections` and `/feeds` answer 404.
- **Full-text counters** — `indexedPages / totalPages / indexedChars /
  totalChars` per attachment. Preferred source is the repo's own control
  plugin (`bench/zotero-fulltext-plugin/`, `GET …/status?keys=`), which
  returns the counters and Zotero's own indexed-state without the text.
  Fallback is the API's `/items/<key>/fulltext`, which returns the text too;
  the text is discarded on arrival and never written anywhere.
- **SQLite supplement** (`--sqlite`), for the two marginals the API is blind
  to: annotation items by type, and feed libraries and items. Opened
  immutable, so rows still in an un-checkpointed WAL are invisible; a census
  is not a ledger and the lag is noted in the artifact.
"""

import argparse
import json
import logging
import math
import platform
import re
import socket
import sqlite3
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_BASE_URL = "http://localhost:23119/api/"
DEFAULT_STATUS_URL = "http://localhost:23119/search-works/fulltext/status"

#: Zotero's stock extraction limits (`extensions.zotero.fulltext.pdfMaxPages` and
#: `extensions.zotero.fulltext.textMaxLength`). A cache whose indexed counter sits
#: exactly on the limit while the total exceeds it was truncated by that limit.
STOCK_PAGE_CAP = 100
STOCK_CHAR_CAP = 500_000

QUANTILES = ((0.0, "min"), (0.10, "p10"), (0.25, "p25"), (0.50, "p50"),
             (0.75, "p75"), (0.90, "p90"), (0.99, "p99"), (1.0, "max"))

#: Item types that are not bibliographic records.
NON_RECORD_TYPES = frozenset({"attachment", "note", "annotation"})

#: Attachment link modes that carry a file Zotero could index. `linked_url` is a
#: bare bookmark and `embedded_image` is a note's inline picture.
FILE_LINK_MODES = frozenset({"imported_file", "imported_url", "linked_file"})

#: `itemAnnotations.type` in zotero.sqlite (chrome/content/zotero/xpcom/data/item.js).
ANNOTATION_TYPES = {1: "highlight", 2: "note", 3: "image", 4: "ink", 5: "underline", 6: "text"}

#: Language field values seen in the wild, folded to ISO 639-1. The map carries
#: ISO 639-2 bibliographic and terminological codes and the English and native
#: names; a two-letter value not listed here passes through as itself.
LANGUAGE_CODES = {
    "en": "en", "eng": "en", "english": "en", "anglais": "en",
    "fr": "fr", "fre": "fr", "fra": "fr", "french": "fr", "français": "fr", "francais": "fr",
    "de": "de", "ger": "de", "deu": "de", "german": "de", "deutsch": "de", "allemand": "de",
    "es": "es", "spa": "es", "spanish": "es", "español": "es", "espanol": "es", "espagnol": "es",
    "it": "it", "ita": "it", "italian": "it", "italiano": "it", "italien": "it",
    "vi": "vi", "vie": "vi", "vietnamese": "vi", "vietnamien": "vi", "tiếng việt": "vi",
    # Country codes the author has used for the language, mapped on his own reading.
    "vn": "vi", "gb": "en", "cn": "zh", "sp": "es",
    "pt": "pt", "por": "pt", "portuguese": "pt", "português": "pt", "portugais": "pt",
    "nl": "nl", "dut": "nl", "nld": "nl", "dutch": "nl", "nederlands": "nl",
    "ru": "ru", "rus": "ru", "russian": "ru", "русский": "ru",
    "zh": "zh", "chi": "zh", "zho": "zh", "chinese": "zh", "中文": "zh",
    "ja": "ja", "jpn": "ja", "japanese": "ja", "日本語": "ja",
    "ko": "ko", "kor": "ko", "korean": "ko",
    "la": "la", "lat": "la", "latin": "la",
    "el": "el", "gre": "el", "ell": "el", "greek": "el",
    "ar": "ar", "ara": "ar", "arabic": "ar",
    "pl": "pl", "pol": "pl", "polish": "pl",
    "sv": "sv", "swe": "sv", "swedish": "sv",
    "da": "da", "dan": "da", "danish": "da",
    "no": "no", "nor": "no", "norwegian": "no",
    "fi": "fi", "fin": "fi", "finnish": "fi",
    "cs": "cs", "cze": "cs", "ces": "cs", "czech": "cs",
    "hu": "hu", "hun": "hu", "hungarian": "hu",
    "tr": "tr", "tur": "tr", "turkish": "tr",
    "ca": "ca", "cat": "ca", "catalan": "ca",
    "id": "id", "ind": "id", "indonesian": "id",
    "th": "th", "tha": "th", "thai": "th",
    "hi": "hi", "hin": "hi", "hindi": "hi",
}

Fetch = Callable[[str], tuple[dict[str, str], bytes]]


# ---------------------------------------------------------------- transport


def http_fetch(url: str, timeout: float = 600.0) -> tuple[dict[str, str], bytes]:
    """The one network call site. GET, and nothing else, ever."""
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {k.lower(): v for k, v in response.headers.items()}, response.read()


class Library:
    """One Zotero library behind the local API: `users/0` or `groups/<id>`."""

    def __init__(self, fetch: Fetch, base_url: str, prefix: str, page_size: int = 100):
        self.fetch = fetch
        self.base_url = base_url.rstrip("/") + "/"
        self.prefix = prefix.strip("/")
        self.page_size = page_size
        self.last_headers: dict[str, str] = {}

    def url(self, path: str, **params) -> str:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return f"{self.base_url}{self.prefix}/{path.lstrip('/')}" + (f"?{query}" if query else "")

    def get_json(self, path: str, **params):
        headers, body = self.fetch(self.url(path, **params))
        self.last_headers = headers
        return json.loads(body)

    def total(self, path: str, **params) -> int:
        """`Total-Results` for a listing, without fetching the listing."""
        headers, _ = self.fetch(self.url(path, limit=1, format="keys", **params))
        self.last_headers = headers
        return int(headers["total-results"])

    def items(self, path: str = "items", **params) -> Iterator[dict]:
        """Every item of a listing, page by page, as `{**data, "_meta": meta}`."""
        start = 0
        while True:
            page = self.get_json(path, limit=self.page_size, start=start, **params)
            for item in page:
                yield {**item["data"], "_meta": item.get("meta", {})}
            if len(page) < self.page_size:
                return
            start += self.page_size

    def fulltext_entries(self) -> dict[str, int]:
        """`{attachment key: version}` for every attachment with a full-text row."""
        return self.get_json("fulltext", since=0)


# ---------------------------------------------------------------- helpers


def quantiles(values: list[int | float]) -> dict:
    """Nearest-rank quantiles, with the count they were taken over."""
    xs = sorted(values)
    if not xs:
        return {"n": 0}
    out: dict = {"n": len(xs)}
    for q, name in QUANTILES:
        rank = 0 if q == 0 else min(len(xs), max(1, math.ceil(q * len(xs)))) - 1
        out[name] = xs[rank]
    out["mean"] = round(sum(xs) / len(xs), 2)
    return out


def histogram(counter: Counter) -> dict:
    """A Counter keyed by integers, rendered as `{"0": n, "1": n, ...}` in order."""
    return {str(k): counter[k] for k in sorted(counter)}


#: A raw language value longer than this, or carrying a path separator, is free
#: text (a sentence, a URL pasted in the wrong field) and is binned rather than
#: quoted: the artifact carries no file name and no URL.
RAW_LANGUAGE_MAX_CHARS = 40


def raw_language(raw: str) -> str:
    value = raw.strip()
    if len(value) > RAW_LANGUAGE_MAX_CHARS or "/" in value or "\\" in value:
        return "(free text, binned)"
    return value


def normalise_language(raw: str) -> str:
    """One ISO 639-1 code per raw value, or `unmapped` when nothing recognises it."""
    value = raw.strip().lower().replace("_", "-")
    if not value:
        return "empty"
    first = re.split(r"[-,;/ ]", value, maxsplit=1)[0]
    if value in LANGUAGE_CODES:
        return LANGUAGE_CODES[value]
    if first in LANGUAGE_CODES:
        return LANGUAGE_CODES[first]
    if re.fullmatch(r"[a-z]{2}", first):
        return first
    return "unmapped"


def title_script(title: str) -> str:
    """Which writing systems a title uses. The title itself is not retained."""
    scripts: set[str] = set()
    non_ascii_latin = False
    for ch in title:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        script = name.split(" ", 1)[0] if name else "UNKNOWN"
        if script in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL"):
            script = "CJK"
        scripts.add(script)
        if script == "LATIN" and ord(ch) > 0x7F:
            non_ascii_latin = True
    if not scripts:
        return "no_letters"
    if scripts == {"LATIN"}:
        return "latin_with_diacritics" if non_ascii_latin else "latin_ascii"
    if "LATIN" in scripts:
        return "latin_plus_" + "+".join(sorted(s.lower() for s in scripts - {"LATIN"}))
    return "+".join(sorted(s.lower() for s in scripts))


def decade(meta: dict) -> str:
    parsed = str(meta.get("parsedDate", "") or "")
    m = re.match(r"(\d{4})", parsed)
    if not m:
        return "undated"
    return f"{int(m.group(1)) // 10 * 10}s"


# ---------------------------------------------------------------- item marginals


def item_marginals(items: list[dict]) -> dict:
    """Every marginal that the item listing alone can answer. Pure; no I/O."""
    by_key = {it["key"]: it for it in items}
    children: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        if it.get("parentItem"):
            children[it["parentItem"]].append(it)

    records = [it for it in items if not it.get("parentItem") and it["itemType"] not in NON_RECORD_TYPES]
    attachments = [it for it in items if it["itemType"] == "attachment"]
    notes = [it for it in items if it["itemType"] == "note"]
    # A child whose parent is not in the listing (parent in the trash, say) is
    # counted as an orphan rather than folded into a record it does not have.
    orphans = sum(1 for it in items if it.get("parentItem") and it["parentItem"] not in by_key)

    item_types = Counter(it["itemType"] for it in records)

    att_per_item = Counter()
    pdf_per_item = Counter()
    notes_per_item = Counter()
    collections_per_item = Counter()
    type_by_pdf: dict[str, Counter] = defaultdict(Counter)
    for rec in records:
        kids = children.get(rec["key"], [])
        n_att = sum(1 for k in kids if k["itemType"] == "attachment")
        n_pdf = sum(1 for k in kids if k["itemType"] == "attachment" and k.get("contentType") == "application/pdf")
        n_notes = sum(1 for k in kids if k["itemType"] == "note")
        att_per_item[n_att] += 1
        pdf_per_item[n_pdf] += 1
        notes_per_item[n_notes] += 1
        collections_per_item[len(rec.get("collections") or [])] += 1
        t = type_by_pdf[rec["itemType"]]
        t["items"] += 1
        t["with_any_attachment"] += n_att > 0
        t["with_pdf"] += n_pdf > 0
        t["with_note"] += n_notes > 0

    content_types = Counter(it.get("contentType") or "" for it in attachments)
    link_modes = Counter(it.get("linkMode") or "" for it in attachments)
    ct_by_lm: dict[str, Counter] = defaultdict(Counter)
    for it in attachments:
        ct_by_lm[it.get("contentType") or ""][it.get("linkMode") or ""] += 1

    languages_raw = Counter(raw_language(str(it.get("language") or "")) for it in records)
    languages_norm = Counter(normalise_language(str(it.get("language") or "")) for it in records)

    return {
        "items_total": len(items),
        "top_level_total": sum(1 for it in items if not it.get("parentItem")),
        "top_level_records": len(records),
        "standalone_attachments": sum(1 for it in attachments if not it.get("parentItem")),
        "standalone_notes": sum(1 for it in notes if not it.get("parentItem")),
        "orphan_children": orphans,
        "item_types": dict(item_types.most_common()),
        "attachments_per_record": histogram(att_per_item),
        "attachments_per_record_quantiles": quantiles(list(att_per_item.elements())),
        "pdf_attachments_per_record": histogram(pdf_per_item),
        "records_by_type_and_attachment": {t: dict(c) for t, c in sorted(type_by_pdf.items())},
        "attachments": {
            "total": len(attachments),
            "child": sum(1 for it in attachments if it.get("parentItem")),
            "content_type": dict(content_types.most_common()),
            "link_mode": dict(link_modes.most_common()),
            "content_type_by_link_mode": {ct: dict(c) for ct, c in sorted(ct_by_lm.items())},
        },
        "notes": {
            "total": len(notes),
            "child": sum(1 for it in notes if it.get("parentItem")),
            "standalone": sum(1 for it in notes if not it.get("parentItem")),
            "per_record": histogram(notes_per_item),
            "records_with_notes": sum(v for k, v in notes_per_item.items() if k > 0),
            "length_chars_quantiles": quantiles([len(it.get("note") or "") for it in notes]),
        },
        "language": {
            "records_with_language": sum(1 for it in records if it.get("language")),
            "raw": dict(languages_raw.most_common()),
            "normalised": dict(languages_norm.most_common()),
        },
        "collections": {
            "records_in_collections": sum(1 for it in records if it.get("collections")),
            "records_in_no_collection": sum(1 for it in records if not it.get("collections")),
            "collections_per_record": histogram(collections_per_item),
        },
        "records": {
            "with_abstract": sum(1 for it in records if it.get("abstractNote")),
            "abstract_length_chars_quantiles": quantiles(
                [len(it["abstractNote"]) for it in records if it.get("abstractNote")]),
            "with_tags": sum(1 for it in records if it.get("tags")),
            "tags_per_record_quantiles": quantiles([len(it.get("tags") or []) for it in records]),
            "with_date": sum(1 for it in records if it.get("date")),
            "decade": dict(Counter(decade(it["_meta"]) for it in records).most_common()),
            "title_script": dict(Counter(title_script(it.get("title") or "") for it in records).most_common()),
        },
    }


# ---------------------------------------------------------------- full text


def counters_from_plugin(fetch: Fetch, status_url: str, keys: list[str], batch: int = 100) -> dict[str, dict]:
    """Per-attachment counters from the control plugin's status endpoint (GET)."""
    out: dict[str, dict] = {}
    for i in range(0, len(keys), batch):
        chunk = keys[i:i + batch]
        _, body = fetch(status_url + "?keys=" + ",".join(chunk))
        for row in json.loads(body).get("items", []):
            if "error" in row:
                continue
            out[row["key"]] = {
                "state": row.get("state"),
                "indexedPages": row.get("indexedPages"),
                "totalPages": row.get("totalPages"),
                "indexedChars": row.get("indexedChars"),
                "totalChars": row.get("totalChars"),
            }
        logging.info("fulltext counters: %d / %d", min(i + batch, len(keys)), len(keys))
    return out


def counters_from_api(lib: Library, keys: list[str]) -> dict[str, dict]:
    """Per-attachment counters from `/items/<key>/fulltext`. The content field is
    dropped as soon as the response is parsed and is never written anywhere."""
    out: dict[str, dict] = {}
    for n, key in enumerate(keys, 1):
        try:
            doc = lib.get_json(f"items/{key}/fulltext")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        out[key] = {
            "state": None,
            "indexedPages": doc.get("indexedPages"),
            "totalPages": doc.get("totalPages"),
            "indexedChars": doc.get("indexedChars"),
            "totalChars": doc.get("totalChars"),
        }
        if n % 500 == 0:
            logging.info("fulltext counters: %d / %d", n, len(keys))
    return out


def derived_state(row: dict | None, has_entry: bool = False) -> str:
    """The plugin's state when it gave one; otherwise the state the counters imply.

    An attachment with a full-text row but no counters is `unindexed` — Zotero
    registered it and extracted nothing yet — and must not read as `no_entry`,
    which the API fallback would otherwise report because `/fulltext` answers
    404 on a version-0 row."""
    if row is None:
        return "unindexed" if has_entry else "no_entry"
    if row.get("state"):
        return row["state"]
    for indexed, total in (("indexedPages", "totalPages"), ("indexedChars", "totalChars")):
        if row.get(indexed) is not None and row.get(total) is not None:
            return "indexed" if row[indexed] >= row[total] else "partial"
    return "unindexed"


def fulltext_marginals(attachments: list[dict], entries: dict[str, int], counters: dict[str, dict],
                       page_cap: int = STOCK_PAGE_CAP, char_cap: int = STOCK_CHAR_CAP) -> dict:
    """Coverage by content type, length distributions, and the cap hits. Pure."""
    files = [it for it in attachments if it.get("linkMode") in FILE_LINK_MODES]
    by_ct: dict[str, dict] = {}
    for ct in sorted({it.get("contentType") or "" for it in files}):
        group = [it for it in files if (it.get("contentType") or "") == ct]
        states = Counter(derived_state(counters.get(it["key"]), it["key"] in entries) for it in group)
        by_ct[ct] = {
            "file_attachments": len(group),
            "with_entry": sum(1 for it in group if it["key"] in entries),
            "without_entry": sum(1 for it in group if it["key"] not in entries),
            "entry_version_zero": sum(1 for it in group if entries.get(it["key"]) == 0),
            "state": dict(states.most_common()),
        }

    rows = [counters[it["key"]] for it in files if it["key"] in counters]
    pages = [(r["indexedPages"], r["totalPages"]) for r in rows
             if r.get("indexedPages") is not None and r.get("totalPages") is not None]
    chars = [(r["indexedChars"], r["totalChars"]) for r in rows
             if r.get("indexedChars") is not None and r.get("totalChars") is not None]
    return {
        "file_attachments": len(files),
        "non_file_attachments": len(attachments) - len(files),
        "entries_in_census": len(entries),
        "entries_version_zero": sum(1 for v in entries.values() if v == 0),
        "counters_measured": len(rows),
        "by_content_type": by_ct,
        "quantiles": {
            "totalPages": quantiles([t for _, t in pages]),
            "indexedPages": quantiles([i for i, _ in pages]),
            "totalChars": quantiles([t for _, t in chars]),
            "indexedChars": quantiles([i for i, _ in chars]),
        },
        "caps": {
            "stock_page_cap": page_cap,
            "stock_char_cap": char_cap,
            "with_page_counters": len(pages),
            "pages_over_stock_cap": sum(1 for _, t in pages if t > page_cap),
            "pages_truncated_at_stock_cap": sum(1 for i, t in pages if i == page_cap and t > page_cap),
            "pages_indexed_beyond_stock_cap": sum(1 for i, _ in pages if i > page_cap),
            "pages_partial": sum(1 for i, t in pages if i < t),
            "with_char_counters": len(chars),
            "chars_over_stock_cap": sum(1 for _, t in chars if t > char_cap),
            "chars_truncated_at_stock_cap": sum(1 for i, t in chars if i == char_cap and t > char_cap),
            "chars_indexed_beyond_stock_cap": sum(1 for i, _ in chars if i > char_cap),
            "chars_partial": sum(1 for i, t in chars if i < t),
        },
    }


# ---------------------------------------------------------------- trash, groups, sqlite


def trash_marginals(lib: Library) -> dict:
    items = list(lib.items("items/trash"))
    return {
        "items": len(items),
        "top_level": sum(1 for it in items if not it.get("parentItem")),
        "children": sum(1 for it in items if it.get("parentItem")),
        "item_types": dict(Counter(it["itemType"] for it in items).most_common()),
    }


def group_counts(lib: Library) -> dict:
    """The group-vs-personal marginal only: sizes, not the full profile."""
    items = list(lib.items())
    attachments = [it for it in items if it["itemType"] == "attachment"]
    return {
        "items_total": len(items),
        "top_level_records": sum(1 for it in items if not it.get("parentItem") and it["itemType"] not in NON_RECORD_TYPES),
        "attachments": len(attachments),
        "attachment_link_mode": dict(Counter(it.get("linkMode") or "" for it in attachments).most_common()),
        "notes": sum(1 for it in items if it["itemType"] == "note"),
        "fulltext_entries": len(lib.fulltext_entries()),
        "trash_items": lib.total("items/trash"),
    }


def sqlite_uri(path: Path) -> str:
    """Read-only and immutable: no lock is taken and no journal is written."""
    return f"file:{urllib.parse.quote(str(Path(path).resolve()))}?mode=ro&immutable=1"


def sqlite_marginals(path: Path) -> dict:
    """The marginals the local API cannot expose, read from an immutable handle."""
    con = sqlite3.connect(sqlite_uri(path), uri=True)
    try:
        library_types = dict(con.execute("SELECT libraryID, type FROM libraries").fetchall())
        annotations: dict[str, Counter] = defaultdict(Counter)
        for library_id, kind, n in con.execute(
            "SELECT i.libraryID, a.type, COUNT(*) FROM itemAnnotations a JOIN items i ON i.itemID = a.itemID "
            "LEFT JOIN deletedItems d ON d.itemID = i.itemID WHERE d.itemID IS NULL GROUP BY 1, 2"
        ):
            annotations[library_types.get(library_id, "unknown")][ANNOTATION_TYPES.get(kind, str(kind))] += n
        annotations_in_trash = con.execute(
            "SELECT COUNT(*) FROM itemAnnotations a JOIN deletedItems d ON d.itemID = a.itemID").fetchone()[0]
        collections: dict[str, int] = {}
        for library_id, n in con.execute("SELECT libraryID, COUNT(*) FROM collections GROUP BY 1"):
            kind = library_types.get(library_id, "unknown")
            collections[kind] = collections.get(kind, 0) + n
        return {
            "libraries_by_type": dict(Counter(library_types.values())),
            "feed_libraries": sum(1 for t in library_types.values() if t == "feed"),
            "feed_items": con.execute("SELECT COUNT(*) FROM feedItems").fetchone()[0],
            "annotations_by_library_type": {k: dict(v) for k, v in annotations.items()},
            "annotations_in_trash": annotations_in_trash,
            "collections_by_library_type": collections,
            "note": "immutable read: rows still in an un-checkpointed WAL are not visible",
        }
    finally:
        con.close()


# ---------------------------------------------------------------- driver


def provenance(args: argparse.Namespace, headers: dict[str, str], counters_source: str) -> dict:
    return {
        "host": socket.gethostname(),
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "base_url": args.base_url,
        "zotero_version": headers.get("x-zotero-version"),
        "zotero_api_version": headers.get("zotero-api-version"),
        "zotero_schema_version": headers.get("zotero-schema-version"),
        "library_last_modified_version": headers.get("last-modified-version"),
        "fulltext_counters_source": counters_source,
        "sqlite": str(args.sqlite) if args.sqlite else None,
        "groups": list(args.include_group or []),
    }


def run(args: argparse.Namespace, fetch: Fetch = http_fetch) -> dict:
    personal = Library(fetch, args.base_url, "users/0", page_size=args.page_size)
    logging.info("listing the personal library")
    items = list(personal.items())
    headers = dict(personal.last_headers)
    logging.info("%d items listed", len(items))
    marginals = item_marginals(items)

    attachments = [it for it in items if it["itemType"] == "attachment"]
    entries = personal.fulltext_entries()
    file_keys = [it["key"] for it in attachments if it.get("linkMode") in FILE_LINK_MODES]
    counters: dict[str, dict] = {}
    source = args.fulltext_counters
    if source == "auto":
        try:
            fetch(args.status_url + "?keys=")
            source = "plugin"
        except (urllib.error.URLError, OSError):
            source = "api"
        logging.info("fulltext counters source: %s", source)
    if source == "plugin":
        counters = counters_from_plugin(fetch, args.status_url, file_keys)
    elif source == "api":
        counters = counters_from_api(personal, sorted(k for k in file_keys if k in entries))
    marginals["fulltext"] = fulltext_marginals(attachments, entries, counters, args.page_cap, args.char_cap)
    marginals["trash"] = trash_marginals(personal)

    groups = {}
    for gid in args.include_group or []:
        logging.info("listing group %s", gid)
        groups[str(gid)] = group_counts(Library(fetch, args.base_url, f"groups/{gid}", page_size=args.page_size))

    doc = {
        "ticket": "0711",
        "provenance": provenance(args, headers, source),
        "personal": marginals,
        "groups": groups,
        "sqlite": sqlite_marginals(args.sqlite) if args.sqlite else None,
    }
    return doc


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Zotero local API root")
    ap.add_argument("--output", type=Path, help="write the JSON artifact here (default: stdout)")
    ap.add_argument("--include-group", action="append", type=int, metavar="GROUP_ID",
                    help="also count a group library (sizes only; repeatable)")
    ap.add_argument("--fulltext-counters", choices=["auto", "plugin", "api", "none"], default="auto",
                    help="where the page/char counters come from (auto: plugin if it answers, else api)")
    ap.add_argument("--status-url", default=DEFAULT_STATUS_URL, help="the control plugin's status endpoint")
    ap.add_argument("--sqlite", type=Path, help="zotero.sqlite, opened immutable, for annotations and feeds")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--page-cap", type=int, default=STOCK_PAGE_CAP)
    ap.add_argument("--char-cap", type=int, default=STOCK_CHAR_CAP)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    doc = run(args)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.output.with_suffix(args.output.suffix + ".tmp")
        tmp.write_text(text)
        tmp.replace(args.output)
        logging.info("wrote %s", args.output)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
