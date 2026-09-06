#!/usr/bin/env python3
"""Inject ticket 0029's source recipe into Zotero and export its API snapshot.

This module owns no corpus content.  The recipe remains authoritative, source bytes
must already match its hashes, and an export is always read from a running Zotero.  The
small in-memory objects in the test suite are controls for this machinery, not a golden
export and are never written under ``bench/fixtures``.

Injection is an idempotent reconciliation.  Stable, namespaced tags associate Zotero
items with recipe ids; a second run updates drift and creates nothing.  Export fails
closed unless every recipe attachment either carries indexed text or is a declared
failure control (``failure_control`` on the recipe record) that the reindex of this very
run watched Zotero leave at the declared state -- a document Zotero cannot extract (a
DjVu container, an un-OCR'd scan) is real ground truth the fixture exists to carry, and
is exported with no full text, its expected degradation, and no answer-set part.
The client version is a required input; the two extraction preferences and the reindex
mode are read from the control plugin's status, never typed: an export records what the
client actually ran under (ticket 0721, after ticket 0632's run recorded the stock
preferences beside a limits-ignored reindex and nothing could tell).
"""

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


SOURCE_TAG_PREFIX = "zoteus-golden-source:"
ATTACHMENT_TAG_PREFIX = "zoteus-golden-attachment:"
NOTE_TAG_PREFIX = "zoteus-golden-note:"
MANAGED_TAG_PREFIXES = (SOURCE_TAG_PREFIX, ATTACHMENT_TAG_PREFIX, NOTE_TAG_PREFIX)
EXPORT_SENTINEL = ".zoteus-golden-export.json"
EXPORT_SENTINEL_SCHEMA = "zoteus-golden-export/v1"
API_HEADERS = {
    "Zotero-API-Version": "3",
    "x-zotero-connector-api-version": "3",
}
#: Bare MIME types per recipe bytes_format.  The charset of a text format is a
#: separate Zotero field (`charset`), written from the recipe, and travels on the
#: upload's Content-Type as a parameter -- never inside contentType, which Zotero
#: stores bare.  The office, image and archive formats are the 9,2 % of files the
#: extractor never reads (census, ticket 0711): failure controls by construction.
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "djvu": "image/vnd.djvu",
    "html": "text/html",
    "wikitext": "text/plain",
    "txt": "text/plain",
    "md": "text/markdown",
    "epub": "application/epub+zip",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "jpg": "image/jpeg",
    "png": "image/png",
    "zip": "application/zip",
    "tgz": "application/gzip",
}
#: The formats Zotero reads as text: their attachment item carries an explicit
#: charset from the recipe, so Zotero never guesses (ticket 0632's real run: bare
#: text/plain, Zotero guessed windows-1252 for UTF-8 Vietnamese, one character
#: per byte indexed).
TEXT_FORMATS = frozenset({"html", "wikitext", "txt", "md"})
#: A text attachment whose decoded body is shorter than this is a transclusion
#: skeleton or an empty page, not a document (two Wikisource work pages carried
#: only header templates on the real run); the recipe may set `min_body_chars`
#: per attachment, and a declared failure control is exempt.
DEFAULT_MIN_BODY_CHARS = 2000
#: What the control plugin is asked for, by name: `stock` passes complete:false so
#: Zotero applies fulltext.pdfMaxPages / textMaxLength as it would to its own
#: extraction; `uncapped` passes complete:true and both limits are ignored.
REINDEX_MODES = {"stock": False, "uncapped": True}
ITEM_FIELDS_FILE = Path(__file__).with_name("zotero-item-fields.json")
ZOTERO_SCHEMA_URL = "https://api.zotero.org/schema"
#: The WHATWG Encoding Standard labels Zotero canonicalises on write
#: (Zotero.CharacterSets.toCanonical, item.js `set charset`): the value written
#: is the canonical name so the item reads back equal to what the recipe meant.
#: Labels not listed pass through lowercased.
CHARSET_LABELS = {
    **{label: "utf-8" for label in ("utf8", "utf-8", "unicode-1-1-utf-8")},
    **{label: "windows-1252" for label in (
        "ascii", "us-ascii", "iso-8859-1", "iso8859-1", "iso_8859-1", "latin1", "l1", "cp1252",
        "x-cp1252", "windows-1252", "ansi_x3.4-1968", "cp819", "ibm819", "iso-ir-100", "csisolatin1",
    )},
    **{label: "gbk" for label in ("gb2312", "gbk", "gb_2312", "gb_2312-80", "chinese", "csgb2312", "x-gbk", "iso-ir-58")},
    **{label: "big5" for label in ("big5", "big5-hkscs", "cn-big5", "csbig5", "x-x-big5")},
    **{label: "koi8-r" for label in ("koi8-r", "koi", "koi8", "koi8_r", "cskoi8r")},
    **{label: "windows-1251" for label in ("windows-1251", "cp1251", "x-cp1251")},
    **{label: "windows-1256" for label in ("windows-1256", "cp1256", "x-cp1256")},
    **{label: "windows-1258" for label in ("windows-1258", "cp1258", "x-cp1258")},
    **{label: "shift_jis" for label in ("shift_jis", "shift-jis", "sjis", "x-sjis", "ms_kanji", "csshiftjis")},
    **{label: "euc-kr" for label in ("euc-kr", "cseuckr", "korean", "ks_c_5601-1987", "windows-949")},
    **{label: "iso-8859-2" for label in ("iso-8859-2", "latin2", "l2", "iso8859-2", "csisolatin2")},
    **{label: "iso-8859-15" for label in ("iso-8859-15", "latin9", "l9", "iso8859-15")},
}
#: The content types whose extracted text Zotero's local API serves on
#: /items/<key>/fulltext: exactly Zotero.Fulltext.isCachedMIMEType (fulltext.js),
#: which server_localAPI.js's ItemFullText handler answers 404 for everything
#: else.  A text/plain attachment Zotero has indexed (census row, char counts)
#: is therefore never served -- found on the real run, padme, 2026-09-06.
SERVED_CONTENT_TYPES = frozenset({"application/pdf", "text/html", "application/epub+zip"})
NOT_SERVED_REASON = (
    "Zotero's local API serves /items/<key>/fulltext only for cached MIME types "
    "(application/pdf, text/html, application/epub+zip; Zotero.Fulltext.isCachedMIMEType); "
    "this content type is indexed from the file and its fulltext route answers 404"
)


class GoldenFixtureError(RuntimeError):
    """A fixture invariant failed; no partial result may be trusted."""


def source_tag(recipe_id: str) -> str:
    return SOURCE_TAG_PREFIX + recipe_id


def attachment_tag(recipe_id: str) -> str:
    return ATTACHMENT_TAG_PREFIX + recipe_id


def note_tag(note_id: str) -> str:
    return NOTE_TAG_PREFIX + note_id


def canonical_charset(label: str) -> str:
    """The name Zotero stores for a charset label (Encoding Standard canonical)."""
    key = label.strip().lower()
    return CHARSET_LABELS.get(key, key)


def _content_type(source: dict) -> str:
    """The bare MIME type the attachment item carries: the recipe's declared lie
    (`content_type_declared`, the lying-MIME failure control) or the format's own."""
    declared = source.get("content_type_declared")
    if isinstance(declared, str) and declared:
        return declared
    return CONTENT_TYPES.get(source.get("bytes_format", "pdf"), "application/octet-stream")


def _attachment_charset(source: dict) -> str | None:
    """The canonical charset a text attachment is written with; None for a non-text
    format.  A text format with no declared charset is refused: Zotero guesses when
    the item carries none, which is the defect this field exists to close."""
    if source.get("bytes_format", "pdf") not in TEXT_FORMATS:
        return None
    charset = source.get("charset")
    if not isinstance(charset, str) or not charset.strip():
        raise GoldenFixtureError(
            f"{source.get('id', '<no id>')}: a {source.get('bytes_format')} attachment must declare its charset"
        )
    return canonical_charset(charset)


def _notes(doc: dict) -> list[dict]:
    notes = doc.get("notes", [])
    return notes if isinstance(notes, list) else []


_ITEM_FIELDS: dict[str, list[str]] | None = None


def _item_schema(path: Path = ITEM_FIELDS_FILE) -> dict:
    global _ITEM_FIELDS
    if _ITEM_FIELDS is None:
        try:
            _ITEM_FIELDS = json.loads(path.read_text(encoding="utf-8"))
            _ITEM_FIELDS["item_types"]
        except (OSError, KeyError, json.JSONDecodeError) as error:
            raise GoldenFixtureError(f"cannot read Zotero item fields from {path}: {error}") from error
    return _ITEM_FIELDS


def item_fields(path: Path = ITEM_FIELDS_FILE) -> dict[str, list[str]]:
    """Zotero's item types and their field names, from the committed reduction of
    https://api.zotero.org/schema (`golden_fixture.py item-fields` regenerates it)."""
    return _item_schema(path)["item_types"]


def type_field(item_type: str, base_field: str) -> str:
    """The field name this item type stores a base field under: a statute keeps its
    title in nameOfAct and its date in dateEnacted, and Zotero rewrites the base name
    on write, so the desired item must name the type's field (padme, 2026-09-06)."""
    return _item_schema().get("base_fields", {}).get(item_type, {}).get(base_field, base_field)


def primary_creator_type(item_type: str) -> str:
    """The creator type Zotero stores a plain author under for this item type: 'author'
    for most, 'presenter' for a presentation, 'cartographer' for a map. Zotero rewrites
    the creator type on write, so writing 'author' on a presentation and expecting it
    back reads as drift (padme, 2026-09-06)."""
    return _item_schema().get("primary_creators", {}).get(item_type, "author")


#: Recipe citation key -> (Zotero field name, the Extra line label Zotero's own
#: convention uses when the item type lacks the field).
CITATION_TARGETS = {"doi": ("DOI", "DOI"), "isbn": ("ISBN", "ISBN"), "url": ("url", "URL")}


def _citation_placement(item_type: str, citation: dict) -> tuple[dict, list[str]]:
    """Split a recipe citation into the fields this item type has and Extra lines
    for the rest (Zotero reads `DOI: ...` / `ISBN: ...` from Extra itself)."""
    fields = item_fields()
    if item_type not in fields:
        raise GoldenFixtureError(f"item type {item_type!r} is not in Zotero's schema (zotero-item-fields.json)")
    placed, extra = {}, []
    for key, value in citation.items():
        if key not in CITATION_TARGETS:
            raise GoldenFixtureError(f"citation key {key!r} is not one of {sorted(CITATION_TARGETS)}")
        field, label = CITATION_TARGETS[key]
        if field in fields[item_type]:
            placed[field] = value
        else:
            extra.append(f"{label}: {value}")
    return placed, extra


def write_item_fields(destination: Path = ITEM_FIELDS_FILE, schema_path: Path | None = None) -> dict:
    """Regenerate zotero-item-fields.json from Zotero's public schema (a local copy
    or a fresh GET), keeping only itemType -> field names."""
    if schema_path is not None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(ZOTERO_SCHEMA_URL, timeout=60) as response:
            schema = json.load(response)
    reduced = {
        "_source": f"{ZOTERO_SCHEMA_URL} (GET, unauthenticated), reduced to itemType -> field names, base-field map and primary creator type; "
                   f"fetched {time.strftime('%Y-%m-%d')}. Regenerate with "
                   "`python3 bench/fixtures/golden_fixture.py item-fields [--schema <schema.json>]` "
                   "when Zotero's schema version moves.",
        "schema_version": schema["version"],
        "item_types": {entry["itemType"]: [field["field"] for field in entry["fields"]] for entry in schema["itemTypes"]},
        "base_fields": {
            entry["itemType"]: {field["baseField"]: field["field"] for field in entry["fields"] if "baseField" in field}
            for entry in schema["itemTypes"]
            if any("baseField" in field for field in entry["fields"])
        },
        "primary_creators": {
            entry["itemType"]: next(c["creatorType"] for c in entry["creatorTypes"] if c.get("primary"))
            for entry in schema["itemTypes"] if entry.get("creatorTypes")
        },
    }
    _write_json(destination, reduced)
    return reduced


def recipe_digest(recipe: list[dict]) -> str:
    """Hash a canonical rendering, so the snapshot is bound to recipe content."""
    body = json.dumps(recipe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sources(doc: dict) -> list[dict]:
    return doc.get("attachments", [doc])


def _source_path(doc: dict, cache_dir: Path) -> Path:
    root = cache_dir.resolve(strict=True)
    path = root / f"{doc['id']}.{doc.get('bytes_format', 'pdf')}"
    if path.is_symlink():
        raise GoldenFixtureError(f"{doc['id']}: source file must not be a symlink")
    resolved = path.resolve()
    if resolved.parent != root:
        raise GoldenFixtureError(f"{doc['id']}: source file escapes the cache directory")
    return resolved


def verify_source_bytes(recipe: list[dict], cache_dir: Path) -> dict[str, Path]:
    """Resolve and verify every input before the first Zotero write."""
    found = {}
    for parent in recipe:
        for doc in _sources(parent):
            if doc.get("id") in found:
                raise GoldenFixtureError(f"duplicate attachment id {doc.get('id')}")
            pinned = doc.get("sha256")
            if not isinstance(pinned, str) or len(pinned) != 64:
                raise GoldenFixtureError(f"{doc.get('id', '<no id>')}: source bytes are not pinned")
            path = _source_path(doc, cache_dir)
            if not path.is_file():
                raise GoldenFixtureError(f"{doc['id']}: source file is missing: {path}")
            actual = _sha256(path)
            if actual != pinned:
                raise GoldenFixtureError(
                    f"{doc['id']}: sha256 mismatch: recipe {pinned}, source file {actual}"
                )
            found[doc["id"]] = path
    return found


def _body_text(raw: bytes, fmt: str, charset: str) -> str:
    """The text a reader would see: HTML with scripts, styles and tags stripped and
    entities decoded; wikitext with templates, comments, noinclude blocks and
    category links stripped; txt and md as they are.  Whitespace collapsed."""
    import html as html_module

    text = raw.decode(charset, errors="replace")
    if fmt == "html":
        text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", text)
        text = re.sub(r"(?s)<!--.*?-->", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html_module.unescape(text)
    elif fmt == "wikitext":
        text = re.sub(r"(?s)<!--.*?-->", " ", text)
        text = re.sub(r"(?is)<noinclude\b.*?</noinclude\s*>", " ", text)
        # Templates nest ({{header | notes = {{small|...}} }}): peel from the inside out.
        previous = None
        while previous != text:
            previous = text
            text = re.sub(r"(?s)\{\{[^{}]*\}\}", " ", text)
        text = re.sub(r"\[\[(?:Category|Thể loại|Catégorie|Kategorie)\s*:[^\]]*\]\]", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(text.split())


def verify_text_bodies(recipe: list[dict], source_paths: dict[str, Path]) -> dict[str, int]:
    """Refuse a text attachment whose decoded body is under its `min_body_chars`
    (default DEFAULT_MIN_BODY_CHARS) unless it declares a failure control: a
    Wikisource work page that is only header templates, an empty page, a
    redirect.  Returns the body length per text attachment id."""
    lengths = {}
    for parent in recipe:
        for source in _sources(parent):
            fmt = source.get("bytes_format", "pdf")
            if fmt not in TEXT_FORMATS:
                continue
            charset = _attachment_charset(source)
            body = _body_text(source_paths[source["id"]].read_bytes(), fmt, charset)
            lengths[source["id"]] = len(body)
            floor = source.get("min_body_chars", DEFAULT_MIN_BODY_CHARS)
            if len(body) < floor and "failure_control" not in source:
                raise GoldenFixtureError(
                    f"{source['id']}: decoded body is {len(body)} characters, under min_body_chars {floor}: "
                    "a transclusion skeleton or an empty page, not the document; re-source it or declare a failure control"
                )
    return lengths


def _tag_values(data: dict) -> list[str]:
    return [
        entry.get("tag")
        for entry in data.get("tags", [])
        if isinstance(entry, dict) and isinstance(entry.get("tag"), str)
    ]


def _managed_markers(data: dict) -> list[str]:
    return [tag for tag in _tag_values(data) if tag.startswith(MANAGED_TAG_PREFIXES)]


def _require_only_managed_marker(data: dict, expected: str, label: str) -> None:
    """Compare the raw marker multiset; sets would hide duplicate identical tags."""
    if _managed_markers(data) != [expected]:
        raise GoldenFixtureError(f"{label}: expected only managed marker {expected}")


def _data(item: dict) -> dict:
    value = item.get("data", item)
    if not isinstance(value, dict):
        raise GoldenFixtureError("Zotero item has no object-valued data")
    return value


def _key(item: dict) -> str:
    data = _data(item)
    key = item.get("key") or data.get("key")
    if not isinstance(key, str) or not key:
        raise GoldenFixtureError("Zotero item has no key")
    return key


def _desired_parent(doc: dict, collection_key: str) -> dict:
    """The parent item the recipe wants.  `language_field` is the exact string
    written to Zotero's language field -- "" or a malformed spelling on purpose,
    the census's own distribution -- and defines nothing for the lane; the recipe's
    `language` is the fallback when the record carries no language_field.  The
    citation goes to the fields the item type has and to Extra otherwise; topic,
    stratum, mechanisms and retained_reason are recorded in Extra beside the
    ticket-0029 lines when the record carries them."""
    item_type = doc.get("item_type", "document")
    extra_lines = [
        f"ticket-0029 recipe id: {doc['id']}",
        f"ticket-0029 work id: {doc.get('work_id', doc['id'])}",
        f"ticket-0029 type fidelity: {doc.get('type_fidelity', 'unreviewed')}",
        "ticket-0029 work relations: " + canonical_json(doc.get("work_relations", [])),
    ]
    if "topic" in doc:
        extra_lines.append(f"ticket-0029 topic: {doc['topic']}")
    if "stratum" in doc:
        extra_lines.append(f"ticket-0029 stratum: {doc['stratum']}")
    if "mechanisms" in doc:
        extra_lines.append("ticket-0029 mechanisms: " + canonical_json(doc["mechanisms"]))
    if "retained_reason" in doc:
        extra_lines.append(f"ticket-0029 retained reason: {doc['retained_reason']}")
    placed, citation_extra = _citation_placement(item_type, doc.get("citation", {}))
    desired = {
        "itemType": item_type,
        type_field(item_type, "title"): doc["title"],
        "creators": [{"creatorType": primary_creator_type(item_type), "name": doc["author"]}],
        type_field(item_type, "date"): str(doc["year"]),
        "language": doc["language_field"] if "language_field" in doc else doc["language"],
        "extra": "\n".join(extra_lines + citation_extra),
        "tags": [{"tag": source_tag(doc["id"])}],
        "collections": [collection_key],
    }
    if "attachments" not in doc:
        desired.update(url=doc["bytes_url"], archive=doc["archive"], archiveLocation=doc["identifier"])
    desired.update(placed)
    return desired


def _desired_note(note: dict, parent_key: str) -> dict:
    return {
        "itemType": "note",
        "parentItem": parent_key,
        "note": note["html"],
        "tags": [{"tag": note_tag(note["id"])}],
    }


def _desired_attachment(
    parent: dict, doc: dict, parent_key: str, path: Path, *, library_type: str = "user",
) -> dict:
    """A group library refuses linked-file attachments outright (Zotero's own local
    API: 400 "Linked files can only be added to user library" -- verified 2026-09-04,
    not a configuration issue on any one group). Only the user library keeps
    linked_file; a group needs a stored attachment, whose bytes this module uploads
    separately (see ZoteroLocalClient.upload_file) before the item can be reindexed.

    No `extra` field: verified against Zotero's own live schema (GET /api/schema,
    2026-09-04) that the `attachment` item type accepts only title/accessDate/url --
    `extra` is rejected outright, 400 "'extra' is not a valid field for type
    'attachment'". A previous version of this function wrote source sha256, role,
    relation, language, selection, skip reason, and a pending/reindexed extraction
    marker there; none of it was ever validated against real Zotero before today,
    since the mocked test client enforces no field-legality rules at all. The
    provenance content is not load-bearing for the export (see_snapshot_rows reads
    role/relation/etc. straight from the recipe, never from the live item); the
    pending/reindexed marker's crash-recovery value is real but narrower than this
    fix restores -- see ticket 0641 (filed 2026-09-04) for giving a real
    interrupted-reindex recovery marker its own reviewed change, since the earlier
    two-phase pending/final write only differed by this now-removed field, so a
    single write suffices."""
    common = {
        "itemType": "attachment",
        "parentItem": parent_key,
        "title": doc.get("title", parent["title"]),
        "contentType": _content_type(doc),
        "tags": [{"tag": attachment_tag(doc["id"])}],
    }
    charset = _attachment_charset(doc)
    if charset is not None:
        common["charset"] = charset
    if library_type == "group":
        common.update(linkMode="imported_file", filename=path.name)
    else:
        common.update(linkMode="linked_file", path=str(path))
    return common


def _managed_equal(item: dict, desired: dict) -> bool:
    """Zotero's API omits a field written as the empty string (a deliberately empty
    language field comes back absent, padme 2026-09-06), so an absent field equals a
    desired empty string; every other difference is drift."""
    data = _data(item)
    return all(
        data.get(field, "" if isinstance(value, str) else None) == value
        for field, value in desired.items()
    )


def _update_payload(item: dict, desired: dict) -> dict:
    data = _data(item)
    payload = {**desired, "key": _key(item)}
    version = item.get("version", data.get("version"))
    if isinstance(version, int):
        payload["version"] = version
    return payload


def _one_marked(items: list[dict], marker: str, kind: str) -> dict | None:
    matches = [item for item in items if marker in _managed_markers(_data(item))]
    if len(matches) > 1:
        raise GoldenFixtureError(f"duplicate {kind} for managed marker {marker}")
    return matches[0] if matches else None


def _classify_children(children: list[dict], recipe_id: str) -> tuple[dict[str, dict], dict[str, dict]]:
    """Split a managed parent's children into attachments and notes by marker; any
    other child is unowned and refused.  Zotero's /children lists both kinds."""
    attachments, notes = {}, {}
    for child in children:
        markers = _managed_markers(_data(child))
        if len(markers) != 1:
            raise GoldenFixtureError(f"{recipe_id}: managed parent has an unowned child")
        marker = markers[0]
        if marker.startswith(ATTACHMENT_TAG_PREFIX):
            child_id = marker[len(ATTACHMENT_TAG_PREFIX):]
            _require_only_managed_marker(_data(child), attachment_tag(child_id), f"attachment {_key(child)}")
            if child_id in attachments:
                raise GoldenFixtureError(f"{recipe_id}: duplicate attachment {child_id}")
            attachments[child_id] = child
        elif marker.startswith(NOTE_TAG_PREFIX):
            child_id = marker[len(NOTE_TAG_PREFIX):]
            _require_only_managed_marker(_data(child), note_tag(child_id), f"note {_key(child)}")
            if _data(child).get("itemType") != "note":
                raise GoldenFixtureError(f"{recipe_id}: note marker on a non-note item {_key(child)}")
            if child_id in notes:
                raise GoldenFixtureError(f"{recipe_id}: duplicate note {child_id}")
            notes[child_id] = child
        else:
            raise GoldenFixtureError(f"{recipe_id}: managed parent has an unowned child")
    return attachments, notes


def inject(
    recipe: list[dict], cache_dir: Path, client, *, collection_key: str, library_type: str = "user",
    reindex_mode: str = "stock",
) -> dict[str, int]:
    """Reconcile recipe parents, attachments and child notes; return mutation counts.

    A group library needs its attachment bytes uploaded (client.upload_file) before
    reindex_fulltext has anything to extract from -- a user-library linked_file
    attachment needs no such step, since its bytes are already reachable by path.
    Group uploads are deliberately repeated even when item metadata already matches:
    Zotero commits the attachment item before its three-phase file upload, so metadata
    cannot attest that a previous upload completed or that its bytes match the recipe.
    A record-only parent (``record_only: true``, ``attachments: []``) gets no
    attachment and no reindex.  Text attachments are refused before the first write
    when their decoded body is under ``min_body_chars`` (verify_text_bodies).
    """
    if reindex_mode not in REINDEX_MODES:
        raise GoldenFixtureError(f"reindex mode {reindex_mode!r} is not one of {sorted(REINDEX_MODES)}")
    source_paths = verify_source_bytes(recipe, cache_dir)
    verify_text_bodies(recipe, source_paths)
    parents = client.list_top_items()
    wanted_ids = {doc["id"] for doc in recipe}
    if len(wanted_ids) != len(recipe):
        raise GoldenFixtureError("source recipe contains duplicate ids")
    doc_by_id = {doc["id"]: doc for doc in recipe}
    parent_by_id = {}
    attachment_by_id = {}
    note_by_id = {}
    for item in parents:
        markers = _managed_markers(_data(item))
        if not markers:
            raise GoldenFixtureError(
                f"fixture collection is not dedicated: top-level item {_key(item)} is unmarked"
            )
        if len(markers) != 1 or not markers[0].startswith(SOURCE_TAG_PREFIX):
            raise GoldenFixtureError(f"parent {_key(item)} carries invalid managed markers")
        recipe_id = markers[0][len(SOURCE_TAG_PREFIX):]
        _require_only_managed_marker(_data(item), source_tag(recipe_id), f"parent {_key(item)}")
        if recipe_id not in wanted_ids:
            raise GoldenFixtureError(
                f"stale managed parent {recipe_id} is not in the source recipe (retire it with `retire --ids`)"
            )
        if recipe_id in parent_by_id:
            raise GoldenFixtureError(
                f"duplicate parent for managed marker {source_tag(recipe_id)}"
            )
        parent_by_id[recipe_id] = item
        expected_attachment_ids = {source["id"] for source in _sources(doc_by_id[recipe_id])}
        expected_note_ids = {note["id"] for note in _notes(doc_by_id[recipe_id])}
        attachments, notes = _classify_children(client.get_children(_key(item)), recipe_id)
        for attachment_id, attachment in attachments.items():
            if attachment_id not in expected_attachment_ids or attachment_id in attachment_by_id:
                raise GoldenFixtureError(f"{recipe_id}: stale or duplicate attachment {attachment_id}")
            attachment_by_id[attachment_id] = attachment
        for note_id, note in notes.items():
            if note_id not in expected_note_ids or note_id in note_by_id:
                raise GoldenFixtureError(f"{recipe_id}: stale or duplicate note {note_id}")
            note_by_id[note_id] = note
    counts = {
        "created_parents": 0,
        "updated_parents": 0,
        "created_attachments": 0,
        "updated_attachments": 0,
        "created_notes": 0,
        "updated_notes": 0,
    }
    pending_reindex = []
    for doc in recipe:
        parent_want = _desired_parent(doc, collection_key)
        parent = parent_by_id.get(doc["id"])
        if parent is None:
            parent = client.write_items([parent_want])[0]
            counts["created_parents"] += 1
        elif not _managed_equal(parent, parent_want):
            parent = client.write_items([_update_payload(parent, parent_want)])[0]
            counts["updated_parents"] += 1

        for source in _sources(doc):
            source_path = source_paths[source["id"]]
            attach_want = _desired_attachment(
                doc, source, _key(parent), source_path, library_type=library_type
            )
            attachment = attachment_by_id.get(source["id"])
            existing_md5 = _data(attachment).get("md5") if attachment is not None else None
            changed = False
            if attachment is None:
                attachment = client.write_items([attach_want])[0]
                counts["created_attachments"] += 1
                changed = True
            elif not _managed_equal(attachment, attach_want):
                attachment = client.write_items([_update_payload(attachment, attach_want)])[0]
                counts["updated_attachments"] += 1
                changed = True
            if library_type == "group":
                client.upload_file(
                    _key(attachment), source_path, _content_type(source),
                    charset=_attachment_charset(source),
                    previous_md5=existing_md5 if isinstance(existing_md5, str) else None,
                )
                pending_reindex.append(_key(attachment))
            elif changed:
                pending_reindex.append(_key(attachment))

        for note in _notes(doc):
            note_want = _desired_note(note, _key(parent))
            existing = note_by_id.get(note["id"])
            if existing is None:
                client.write_items([note_want])
                counts["created_notes"] += 1
            elif not _managed_equal(existing, note_want):
                client.write_items([_update_payload(existing, note_want)])
                counts["updated_notes"] += 1
    if pending_reindex:
        client.reindex_fulltext(pending_reindex, complete=REINDEX_MODES[reindex_mode])
    return counts


def retire(recipe_ids, client, *, collection_key: str) -> dict[str, list[str]]:
    """Move managed parents out of the fixture collection, children following;
    nothing is deleted or trashed.  A parent is found by its source marker among
    the collection's top items; one already outside is reported as absent, so a
    second run changes nothing."""
    wanted = list(dict.fromkeys(recipe_ids))
    if not wanted:
        raise GoldenFixtureError("retire needs at least one recipe id")
    retired = []
    for item in client.list_top_items():
        markers = _managed_markers(_data(item))
        if len(markers) != 1 or not markers[0].startswith(SOURCE_TAG_PREFIX):
            continue
        recipe_id = markers[0][len(SOURCE_TAG_PREFIX):]
        if recipe_id not in wanted:
            continue
        collections = _data(item).get("collections", [])
        if not isinstance(collections, list) or collection_key not in collections:
            continue
        remaining = [key for key in collections if key != collection_key]
        # The full item data goes back, not a partial object: Zotero's local API applies
        # a write through Item.fromJSON, which clears every field the JSON omits, so a
        # bare {collections} would blank the retired record's title and creators.
        client.write_items([_update_payload(item, {**_data(item), "collections": remaining})])
        retired.append(recipe_id)
    return {"retired": retired, "absent": [recipe_id for recipe_id in wanted if recipe_id not in retired]}


def _observed_item_version(client) -> int:
    value = getattr(client, "item_library_version", None)
    if value is None:
        value = getattr(client, "library_version", None)
    if not isinstance(value, int) or value < 0:
        raise GoldenFixtureError("Zotero did not report a valid item library version")
    return value


def _last_item_page_versions(client) -> list[int]:
    versions = getattr(client, "last_item_page_versions", None)
    return list(versions) if versions is not None else [_observed_item_version(client)]


def _fulltext_or_none(client, key: str):
    """The /fulltext body, or None when Zotero has none to serve (404; the in-memory
    control raises a lookup error).  Any other failure still propagates."""
    try:
        return client.get_fulltext(key)
    except (KeyError, LookupError):
        return None


def _control_row(
    doc: dict, source: dict, parent_key: str, attachment_key: str, observed: dict,
    census_version: int | None,
) -> dict:
    """The export row of a declared failure control: no full text, its declared
    expectation copied from the recipe, the state the reindex just observed, and
    the census version Zotero listed it at (0 for an empty missing-marked row,
    None when it has no row), so the replay answers the census as Zotero did."""
    row = {
        "recipe_id": doc["id"], "parent_key": parent_key, "attachment_key": attachment_key,
        "terminal_state": "unindexed", "fulltext_file": None, "fulltext_version": census_version,
        "body": None, "failure_control": copy.deepcopy(source["failure_control"]),
        "observed_state": observed.get("state"),
    }
    if "attachments" in doc:
        row.update(attachment_id=source["id"], role=source["role"],
                   relation=source["relation"], language=source["language"],
                   bytes_format=source.get("bytes_format", "pdf"),
                   selection_expectation=source["selection_expectation"],
                   cap_expectations=source["cap_expectations"],
                   skip_reason=source.get("skip_reason", ""))
    row.update(indexed_pages=None, total_pages=None, indexed_chars=None, total_chars=None)
    return row


def _not_served_row(
    doc: dict, source: dict, parent_key: str, attachment_key: str, observed: dict, census_version: int,
) -> dict:
    """The export row of an attachment Zotero indexed but the local API never serves."""
    row = {
        "recipe_id": doc["id"], "parent_key": parent_key, "attachment_key": attachment_key,
        "terminal_state": "indexed-not-served", "fulltext_file": None,
        "fulltext_version": census_version, "body": None,
        "observed_state": observed.get("state"), "not_served_reason": NOT_SERVED_REASON,
    }
    if "attachments" in doc:
        row.update(attachment_id=source["id"], role=source["role"],
                   relation=source["relation"], language=source["language"],
                   bytes_format=source.get("bytes_format", "pdf"),
                   selection_expectation=source["selection_expectation"],
                   cap_expectations=source["cap_expectations"],
                   skip_reason=source.get("skip_reason", ""))
    row.update(indexed_pages=None, total_pages=None,
               indexed_chars=observed.get("indexedChars"), total_chars=observed.get("totalChars"))
    return row


def _snapshot_rows(
    recipe: list[dict], client, source_paths: dict[str, Path], collection_key: str,
    *, library_type: str = "user", settled: dict[str, dict] | None = None,
) -> tuple[list[dict], list[dict], list[dict], int]:
    """Capture every recipe parent, child note and attachment from the live API.

    ``settled`` is what ``reindex_fulltext`` observed per attachment key once Zotero
    went idle in this very run (``state``, the plugin's counters, ``version`` and
    ``previous_version``).  It is the only evidence on which an attachment may be
    exported without full text, and only when the recipe declares it a failure
    control expecting exactly that state.  ``None`` means no observation was made,
    which keeps the strict behaviour: every attachment must carry indexed text.
    """
    parents = client.list_top_items()
    opening_versions = _last_item_page_versions(client)
    if not opening_versions or len(set(opening_versions)) != 1:
        raise GoldenFixtureError("Zotero item pages did not share one library version")
    starting_item_version = opening_versions[0]
    items = []
    attachments = []
    parent_rows = []
    version_zero_bodies = {}
    census = client.fulltext_since(0)
    seen_recipe_ids = set()
    seen_item_keys = set()
    for doc in recipe:
        if doc["id"] in seen_recipe_ids:
            raise GoldenFixtureError(f"duplicate recipe id {doc['id']}")
        seen_recipe_ids.add(doc["id"])
        parent = _one_marked(parents, source_tag(doc["id"]), "parent")
        if parent is None:
            raise GoldenFixtureError(f"{doc['id']}: no injected parent in Zotero")
        _require_only_managed_marker(_data(parent), source_tag(doc["id"]), doc["id"])
        if not _managed_equal(parent, _desired_parent(doc, collection_key)):
            raise GoldenFixtureError(f"{doc['id']}: parent metadata drifted from the source recipe")
        children = client.get_children(_key(parent))
        if any(version != starting_item_version for version in _last_item_page_versions(client)):
            raise GoldenFixtureError("Zotero items changed while the fixture snapshot was captured")
        sources = _sources(doc)
        notes = _notes(doc)
        if len(children) != len(sources) + len(notes):
            raise GoldenFixtureError(f"{doc['id']}: injected parent does not have exactly its recipe attachments and notes")
        parent_key = _key(parent)
        if parent_key in seen_item_keys:
            raise GoldenFixtureError(f"duplicate exported Zotero item key {parent_key}")
        seen_item_keys.add(parent_key)
        items.append(parent)
        note_keys = []
        for note in notes:
            child = _one_marked(children, note_tag(note["id"]), "note")
            if child is None:
                raise GoldenFixtureError(f"{doc['id']}: no child note {note['id']} in Zotero")
            _require_only_managed_marker(_data(child), note_tag(note["id"]), note["id"])
            if not _managed_equal(child, _desired_note(note, parent_key)):
                raise GoldenFixtureError(f"{note['id']}: note drifted from the source recipe")
            note_key = _key(child)
            if note_key in seen_item_keys:
                raise GoldenFixtureError(f"duplicate exported Zotero item key {note_key}")
            seen_item_keys.add(note_key)
            items.append(child)
            note_keys.append(note_key)
        parent_rows.append({
            "recipe_id": doc["id"], "parent_key": parent_key,
            "record_only": bool(doc.get("record_only", False)) or not sources,
            "note_keys": note_keys, "attachment_count": len(sources),
        })
        for source in sources:
            child = _one_marked(children, attachment_tag(source["id"]), "linked attachment")
            if child is None:
                raise GoldenFixtureError(f"{doc['id']}: no linked attachment {source['id']} in Zotero")
            _require_only_managed_marker(_data(child), attachment_tag(source["id"]), source["id"])
            child_data = _data(child)
            if library_type == "group":
                if child_data.get("linkMode") != "imported_file":
                    raise GoldenFixtureError(f"{source['id']}: attachment is not a stored file")
                filename = child_data.get("filename")
                if not isinstance(filename, str) or filename != source_paths[source["id"]].name:
                    raise GoldenFixtureError(f"{source['id']}: stored attachment does not name its pinned source")
            else:
                if child_data.get("linkMode") != "linked_file":
                    raise GoldenFixtureError(f"{source['id']}: attachment is not a linked file")
                linked_path = child_data.get("path")
                if not isinstance(linked_path, str) or Path(linked_path).resolve() != source_paths[source["id"]]:
                    raise GoldenFixtureError(f"{source['id']}: linked attachment does not name its pinned source")
            if not _managed_equal(
                child,
                _desired_attachment(doc, source, parent_key, source_paths[source["id"]], library_type=library_type),
            ):
                raise GoldenFixtureError(f"{source['id']}: attachment metadata drifted from the source recipe")
            attachment_key = _key(child)
            if attachment_key in seen_item_keys:
                raise GoldenFixtureError(f"duplicate exported Zotero item key {attachment_key}")
            seen_item_keys.add(attachment_key)
            control = source.get("failure_control")
            observed = None if settled is None else settled.get(attachment_key)
            if control is not None:
                # A declared failure control is accepted without full text only on
                # evidence from THIS run: the reindex just watched Zotero finish and
                # leave the attachment at the declared state, and the /fulltext census
                # has no row for it.  Mere absence from the census is refused below,
                # because absence also describes previously indexed text that vanished
                # (test_export_is_raw_complete_atomic_and_bound_to_recipe).
                if observed is None:
                    raise GoldenFixtureError(
                        f"{source['id']}: declared failure control has no settled reindex "
                        "observation from this run"
                    )
                if observed.get("state") != control["expected_state"]:
                    raise GoldenFixtureError(
                        f"{source['id']}: failure control expected {control['expected_state']}, "
                        f"the reindex settled at {observed.get('state')!r}"
                    )
                # Zotero records a PDF it found no text in through recordMissingContent
                # (fulltext.js): an empty fulltextItems row at version 0, marked missing,
                # listed by the census at 0 while the fulltext route answers 404.  A
                # container it never dispatches (DjVu) gets no row at all.  Both are
                # unindexed; a census version above 0, or a body served, is not.
                census_version = census.get(attachment_key)
                if census_version is not None and census_version != 0:
                    raise GoldenFixtureError(
                        f"{source['id']}: failure control has a /fulltext census entry at "
                        f"version {census_version}; it is not unindexed"
                    )
                if _fulltext_or_none(client, attachment_key) is not None:
                    raise GoldenFixtureError(
                        f"{source['id']}: failure control serves full text; it is not unindexed"
                    )
                items.append(child)
                attachments.append(
                    _control_row(doc, source, parent_key, attachment_key, observed, census_version)
                )
                continue
            if observed is not None:
                # `partial` is a stock reindex stopping at a cap (100 pages, 500 000 characters):
                # Zotero serves the truncated text and the counters record where it stopped.
                if observed.get("state") not in ("indexed", "partial"):
                    raise GoldenFixtureError(
                        f"{source['id']}: the reindex settled at {observed.get('state')!r}; only a "
                        "declared failure control may be exported without full text"
                    )
                previous = observed.get("previous_version")
                if isinstance(previous, int) and previous > 0 and observed.get("version") == previous:
                    raise GoldenFixtureError(
                        f"{source['id']}: the reindex left the fulltext version at {previous}; "
                        "nothing was re-extracted (is the file present on this client?)"
                    )
            if attachment_key not in census:
                raise GoldenFixtureError(f"{source['id']}: attachment has no /fulltext census entry")
            fulltext = _fulltext_or_none(client, attachment_key)
            if fulltext is None:
                content_type = _content_type(source)
                if observed is not None and content_type not in SERVED_CONTENT_TYPES:
                    # Indexed by Zotero (the reindex just saw it, the census lists it) yet
                    # never served by the local API: the product indexes such an item from
                    # metadata only.  Captured as what it is, not as vanished text -- which
                    # is what a 404 on a served content type still means.
                    if not isinstance(census[attachment_key], int) or census[attachment_key] < 0:
                        raise GoldenFixtureError(f"{source['id']}: invalid /fulltext census version")
                    items.append(child)
                    attachments.append(
                        _not_served_row(doc, source, parent_key, attachment_key, observed, census[attachment_key])
                    )
                    continue
                raise GoldenFixtureError(f"{source['id']}: attachment has no /fulltext response")
            if not isinstance(census[attachment_key], int) or census[attachment_key] < 0:
                raise GoldenFixtureError(f"{source['id']}: invalid /fulltext census version")
            if not isinstance(fulltext, dict) or not isinstance(fulltext.get("content"), str) or not fulltext["content"].strip():
                raise GoldenFixtureError(f"{source['id']}: malformed /fulltext response")
            response_version = getattr(client, "last_fulltext_version", fulltext.get("version", None))
            if response_version != census[attachment_key]:
                raise GoldenFixtureError(f"{source['id']}: fulltext body version does not match its census")
            # A PDF answers with page counters, a served text format (HTML, EPUB) with
            # character counters and no pages; either pair is the binding record.
            pages = (fulltext.get("indexedPages"), fulltext.get("totalPages"))
            chars = (fulltext.get("indexedChars"), fulltext.get("totalChars"))
            has_pages = all(isinstance(v, int) for v in pages)
            has_chars = all(isinstance(v, int) for v in chars)
            if not has_pages and not has_chars:
                raise GoldenFixtureError(
                    f"{source['id']}: /fulltext lacks integer indexedPages/totalPages or indexedChars/totalChars"
                )
            for name, (indexed, total), present in (("Pages", pages, has_pages), ("Chars", chars, has_chars)):
                if present and (indexed < 0 or total < 0 or indexed > total):
                    raise GoldenFixtureError(f"{source['id']}: invalid indexed{name}/total{name} relation")
            indexed_pages, total_pages = pages if has_pages else (None, None)
            if census[attachment_key] == 0:
                version_zero_bodies[attachment_key] = (source["id"], fulltext)
            items.append(child)
            row = {
                "recipe_id": doc["id"], "parent_key": parent_key,
                "attachment_key": attachment_key, "terminal_state": "indexed",
                "observed_state": (observed or {}).get("state", "indexed"),
                "fulltext_file": f"fulltext/{attachment_key}.json",
                "fulltext_version": census[attachment_key], "body": fulltext,
            }
            if "attachments" in doc:
                row.update(attachment_id=source["id"], role=source["role"],
                           relation=source["relation"], language=source["language"],
                           bytes_format=source.get("bytes_format", "pdf"),
                           selection_expectation=source["selection_expectation"],
                           cap_expectations=source["cap_expectations"],
                           skip_reason=source.get("skip_reason", ""))
            row.update(indexed_pages=indexed_pages, total_pages=total_pages,
                       indexed_chars=fulltext.get("indexedChars"), total_chars=fulltext.get("totalChars"))
            attachments.append(row)
    # Version zero carries no change signal.  Re-read every such body only after all
    # first-pass bodies have been captured, so a later response cannot mutate an earlier
    # zero-version body without detection.
    for attachment_key, (recipe_id, original) in version_zero_bodies.items():
        repeated = client.get_fulltext(attachment_key)
        repeated_version = getattr(client, "last_fulltext_version", repeated.get("version", None))
        if repeated_version != 0 or canonical_json(repeated) != canonical_json(original):
            raise GoldenFixtureError(f"{recipe_id}: version-zero fulltext changed during capture")
    exported_parent_keys = {_key(item) for item in items if not _data(item).get("parentItem")}
    all_parent_keys = {_key(item) for item in parents}
    if exported_parent_keys != all_parent_keys:
        extras = sorted(all_parent_keys - exported_parent_keys)
        raise GoldenFixtureError(
            f"fixture collection contains item(s) outside the source recipe: {', '.join(extras)}"
        )
    ending_parents = client.list_top_items()
    ending_versions = _last_item_page_versions(client)
    ending_census = client.fulltext_since(0)
    if (
        not ending_versions
        or any(version != starting_item_version for version in ending_versions)
        or canonical_json(ending_parents) != canonical_json(parents)
    ):
        raise GoldenFixtureError("Zotero items changed while the fixture snapshot was captured")
    if ending_census != census:
        raise GoldenFixtureError("Zotero fulltext changed while the fixture snapshot was captured")
    return items, attachments, parent_rows, starting_item_version


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _refresh_fulltext_from_pinned_sources(
    recipe: list[dict], client, source_paths: dict[str, Path], collection_key: str,
    cache_dir: Path, *, library_type: str = "user", reindex_mode: str = "stock",
) -> dict[str, dict] | None:
    """Force the export's extraction from the bytes verified around this operation.

    reindex_fulltext (the plugin call) is what forces the actual re-extraction; no
    item write is needed to trigger it, and the metadata equality check just above
    already proves the live item matches what the recipe wants.  Returns the per-key
    settled state the reindex observed, or None when the client reports none; an
    empty dict when the recipe has no attachment to reindex (record-only parents)."""
    parents = client.list_top_items()
    keys = []
    for doc in recipe:
        parent = _one_marked(parents, source_tag(doc["id"]), "parent")
        if parent is None or not _managed_equal(parent, _desired_parent(doc, collection_key)):
            raise GoldenFixtureError(f"{doc['id']}: parent metadata drifted from the source recipe")
        children = client.get_children(_key(parent))
        if len(children) != len(_sources(doc)) + len(_notes(doc)):
            raise GoldenFixtureError(f"{doc['id']}: injected parent has a missing or extra child")
        for note in _notes(doc):
            child = _one_marked(children, note_tag(note["id"]), "note")
            if child is None or not _managed_equal(child, _desired_note(note, _key(parent))):
                raise GoldenFixtureError(f"{note['id']}: note drifted from the source recipe")
        for source in _sources(doc):
            attachment = _one_marked(children, attachment_tag(source["id"]), "linked attachment")
            if attachment is None:
                raise GoldenFixtureError(f"{doc['id']}: no linked attachment {source['id']} in Zotero")
            final = _desired_attachment(
                doc, source, _key(parent), source_paths[source["id"]], library_type=library_type
            )
            if not _managed_equal(attachment, final):
                raise GoldenFixtureError(f"{source['id']}: attachment metadata drifted from the source recipe")
            keys.append(_key(attachment))

    if not keys:
        return {}
    settled = client.reindex_fulltext(keys, complete=REINDEX_MODES[reindex_mode])
    # A linked file can change while Zotero is reading it.  Do not attest or export
    # unless the complete source set still has the recipe hashes after extraction.
    verify_source_bytes(recipe, cache_dir)
    if settled is None:
        return None
    if not isinstance(settled, dict) or set(settled) != set(keys):
        raise GoldenFixtureError("the reindex did not report a settled state for every attachment")
    return settled


def _portable_item(item: dict) -> dict:
    """Emit only fields reviewed as inputs to the replay/index build."""
    data = _data(item)
    common = {"key", "version", "itemType", "title", "tags"}
    if data.get("itemType") == "attachment":
        allowed = common | {"parentItem", "linkMode", "contentType", "charset", "path", "filename", "extra"}
    elif data.get("itemType") == "note":
        allowed = common | {"parentItem", "note"}
    else:
        item_type = str(data.get("itemType", "document"))
        allowed = common | {
            "creators", "date", "language", "url", "archive", "archiveLocation",
            "extra", "collections", "DOI", "ISBN",
            # the item type's own names for title and date (a statute's nameOfAct, dateEnacted)
            type_field(item_type, "title"), type_field(item_type, "date"),
        }
    public_data = {key: copy.deepcopy(data[key]) for key in allowed if key in data}
    if public_data.get("linkMode") == "linked_file" and isinstance(public_data.get("path"), str):
        public_data["path"] = f"attachments:{Path(public_data['path']).name}"
    portable = {"key": _key(item), "data": public_data}
    version = item.get("version", data.get("version"))
    if isinstance(version, int):
        portable["version"] = version
    return portable


def _portable_fulltext(body: dict) -> dict:
    allowed = {"content", "indexedPages", "totalPages", "indexedChars", "totalChars"}
    return {key: copy.deepcopy(body[key]) for key in allowed if key in body}


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_export_destination(destination: Path) -> tuple[Path, bool]:
    lexical = Path(os.path.abspath(destination))
    parent = lexical.parent.resolve()
    candidate = parent / lexical.name
    if candidate != lexical:
        raise GoldenFixtureError(f"fixture export destination must not traverse a symlink: {lexical}")
    broad = {
        Path(candidate.anchor), Path.home().resolve(), Path(tempfile.gettempdir()).resolve(),
        Path(__file__).resolve().parents[2],
    }
    if candidate in broad:
        raise GoldenFixtureError(f"refusing broad fixture export destination {candidate}")
    if candidate.is_symlink():
        raise GoldenFixtureError(f"fixture export destination must not be a symlink: {candidate}")
    if not candidate.exists():
        return candidate, False
    if not candidate.is_dir():
        raise GoldenFixtureError(f"fixture export destination is not a directory: {candidate}")
    sentinel = candidate / EXPORT_SENTINEL
    if sentinel.is_symlink() or not sentinel.is_file():
        raise GoldenFixtureError(f"refusing unowned fixture export destination {candidate}")
    try:
        owner = json.loads(sentinel.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GoldenFixtureError(f"invalid fixture export ownership marker in {candidate}") from error
    if owner != {"schema": EXPORT_SENTINEL_SCHEMA}:
        raise GoldenFixtureError(f"refusing unowned fixture export destination {candidate}")
    return candidate, True


def _reindex_record(mode: str | None, observed: dict | None) -> dict:
    """The manifest's reindex block: the mode as the plugin reported it, never as typed."""
    if mode is None:
        return {"mode": None, "limits": "not applicable: no attachment was reindexed",
                "binding_record": "per-attachment indexed_pages/total_pages and indexed_chars/total_chars"}
    return {
        "mode": mode,
        "limits": "applied" if mode == "stock" else "ignored",
        "complete_flag": REINDEX_MODES[mode],
        "observed_from": "the control plugin's status lastReindexMode after the reindex settled",
        "plugin_version": (observed or {}).get("codeVersion") or (observed or {}).get("version"),
        "source": "bench/zotero-fulltext-plugin/bootstrap.js: Zotero.FullText.indexItems(ids, "
                  "{complete, ignoreErrors: true}); fulltext.js indexPDF(filePath, itemID, allPages)",
        "binding_record": "per-attachment indexed_pages/total_pages and indexed_chars/total_chars",
    }


def _plugin_status(client) -> dict:
    """The plugin's status as the export's provenance: version, the mode of the last
    reindex, and both extraction preferences read live from the client."""
    read = getattr(client, "plugin_status", None)
    if read is None:
        raise GoldenFixtureError("the client cannot read the control plugin's status; the reindex mode "
                                 "and the extraction preferences must be observed, not typed")
    status = read()
    if not isinstance(status, dict):
        raise GoldenFixtureError("the control plugin returned a malformed status")
    prefs = status.get("prefs")
    if not isinstance(prefs, dict):
        raise GoldenFixtureError("the control plugin reports no extraction preferences (install 0.2.0 or later)")
    for name in ("pdfMaxPages", "textMaxLength"):
        value = prefs.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise GoldenFixtureError(f"the control plugin reports fulltext.{name} as {value!r}, not a positive integer")
    version = status.get("codeVersion") or status.get("version")
    if not isinstance(version, str) or not version.strip():
        raise GoldenFixtureError("the control plugin reports no version")
    mode = status.get("lastReindexMode")
    if mode is not None and mode not in REINDEX_MODES:
        raise GoldenFixtureError(f"the control plugin reports an unknown reindex mode {mode!r}")
    return {"version": version, "lastReindexMode": mode,
            "pdfMaxPages": prefs["pdfMaxPages"], "textMaxLength": prefs["textMaxLength"]}


def _refuse_counters_over_caps(rows: list[dict], pdf_max_pages: int, text_max_length: int) -> None:
    """In stock mode a captured counter must agree with the recorded preference: an
    attachment indexed past the cap, or one over the cap that was not cut exactly
    at it, means the limits were not the ones recorded (C.7: the export refuses
    itself when a captured counter contradicts a recorded setting)."""
    for row in rows:
        label = row.get("attachment_id", row["recipe_id"])
        for indexed_name, total_name, cap, setting in (
            ("indexed_pages", "total_pages", pdf_max_pages, "fulltext.pdfMaxPages"),
            ("indexed_chars", "total_chars", text_max_length, "fulltext.textMaxLength"),
        ):
            indexed, total = row.get(indexed_name), row.get(total_name)
            if not isinstance(indexed, int) or not isinstance(total, int):
                continue
            if indexed > cap:
                raise GoldenFixtureError(
                    f"{label}: {indexed_name} {indexed} exceeds the recorded {setting} {cap}; the reindex did not "
                    "run under the stock limits"
                )
            if total > cap and indexed != cap:
                raise GoldenFixtureError(
                    f"{label}: {total_name} {total} is over the recorded {setting} {cap} but {indexed_name} is "
                    f"{indexed}, not the cap; the captured counters contradict the recorded setting"
                )


def _detected_defects(
    items: list[dict], attachment_rows: list[dict], source_paths: dict[str, Path], sources_by_id: dict[str, dict],
) -> list[dict]:
    """Defects the export can see for itself.  Today one: a text attachment indexed
    one character per byte although the item carries its declared charset --
    indexed_chars equals the byte length while decoding under that charset is
    shorter.  An explicitly set charset that Zotero holds unchanged is no defect
    (drift is refused earlier, by the metadata equality check)."""
    by_key = {_key(item): _data(item) for item in items}
    found = []
    for row in attachment_rows:
        source_id = row.get("attachment_id", row["recipe_id"])
        source = sources_by_id.get(source_id, {})
        if source.get("bytes_format", "pdf") not in TEXT_FORMATS:
            continue
        data = by_key.get(row["attachment_key"], {})
        charset = str(data.get("charset") or "") or _attachment_charset(source)
        raw = source_paths[source_id].read_bytes()
        try:
            decoded_chars = len(raw.decode(charset, errors="replace"))
        except LookupError:
            decoded_chars = len(raw.decode("utf-8", errors="replace"))
        indexed = row.get("indexed_chars")
        if isinstance(indexed, int) and indexed == len(raw) and decoded_chars < len(raw):
            found.append({
                "recipe_id": row["recipe_id"], "attachment_key": row["attachment_key"],
                "defect": f"indexed one character per byte although the item declares charset {charset}: "
                          "the indexed text is the file's bytes decoded one per character (mojibake for "
                          "non-ASCII text)",
                "evidence": {"indexed_chars": indexed, "source_bytes": len(raw), "decoded_chars": decoded_chars,
                             "charset": charset},
                "remedy": "check the charset Zotero stored against the bytes, re-inject and re-pin",
            })
    return found


def export_snapshot(
    recipe: list[dict],
    client,
    *,
    collection_key: str,
    destination: Path,
    library: dict,
    zotero_client_version: str,
    index_max_chars: int,
    cache_dir: Path,
    reindex_mode: str = "stock",
    pdf_max_pages: int | None = None,
    text_max_length: int | None = None,
    known_defects: list[dict] | None = None,
) -> Path:
    """Capture raw items/notes/fulltext into an atomically replaced snapshot directory.

    ``reindex_mode`` is what the plugin is asked for; the manifest records the mode
    the plugin reports having run, and refuses when the two disagree.  The two
    extraction preferences are read from the plugin's status; ``pdf_max_pages`` /
    ``text_max_length``, when given, are cross-checks that refuse on mismatch.  In
    stock mode every captured counter is checked against the recorded preference.
    ``known_defects`` are declared by the operator (recipe id and a description a
    reader can check against the bytes); the export adds the defects it detects
    itself.  Both are recorded, never repaired: the export is what Zotero holds."""
    if library.get("type") not in {"user", "group"} or not isinstance(library.get("id"), int):
        raise GoldenFixtureError("the fixture export must identify its public Zotero library")
    if not zotero_client_version.strip():
        raise GoldenFixtureError("Zotero client version must be recorded")
    if reindex_mode not in REINDEX_MODES:
        raise GoldenFixtureError(f"reindex mode {reindex_mode!r} is not one of {sorted(REINDEX_MODES)}")
    if not isinstance(index_max_chars, int) or index_max_chars <= 0:
        raise GoldenFixtureError("index fulltext max chars must be recorded as a positive integer")
    for name, value in (("--pdf-max-pages", pdf_max_pages), ("--text-max-length", text_max_length)):
        if value is not None and (not isinstance(value, int) or value <= 0):
            raise GoldenFixtureError(f"{name} must be a positive integer when given")

    source_paths = verify_source_bytes(recipe, cache_dir)
    verify_text_bodies(recipe, source_paths)
    settled = _refresh_fulltext_from_pinned_sources(
        recipe, client, source_paths, collection_key, cache_dir, library_type=library["type"],
        reindex_mode=reindex_mode,
    )
    observed = _plugin_status(client)
    reindexed_any = settled is None or bool(settled)
    observed_mode = observed["lastReindexMode"] if reindexed_any else None
    if reindexed_any and observed_mode != reindex_mode:
        raise GoldenFixtureError(
            f"reindex mode typed {reindex_mode!r} but the plugin reports its last reindex ran {observed_mode!r}"
        )
    for name, typed, read in (
        ("fulltext.pdfMaxPages", pdf_max_pages, observed["pdfMaxPages"]),
        ("fulltext.textMaxLength", text_max_length, observed["textMaxLength"]),
    ):
        if typed is not None and typed != read:
            raise GoldenFixtureError(f"{name} typed as {typed} but the client reports {read}")
    items, attachment_rows, parent_rows, library_version = _snapshot_rows(
        recipe, client, source_paths, collection_key, library_type=library["type"], settled=settled,
    )
    if observed_mode == "stock":
        _refuse_counters_over_caps(attachment_rows, observed["pdfMaxPages"], observed["textMaxLength"])
    # This is deliberately after the API capture and immediately before staging the
    # snapshot: extraction must still be attributable to the exact pinned source bytes.
    verify_source_bytes(recipe, cache_dir)
    destination, destination_owned = _safe_export_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    backup = Path(tempfile.mkdtemp(prefix=f".{destination.name}-previous-", dir=destination.parent))
    backup.rmdir()
    sources_by_id = {source["id"]: source for doc in recipe for source in _sources(doc)}
    try:
        (temp / "fulltext").mkdir()
        public_rows = []
        for row in attachment_rows:
            body = row.pop("body")
            if row["terminal_state"] == "indexed":
                _write_json(temp / row["fulltext_file"], _portable_fulltext(body))
            public_rows.append(row)
        manifest = {
            "schema_version": 2,
            "parent_item_count": len(recipe),
            "attachment_count": len(public_rows),
            "indexed_attachment_count": sum(row["terminal_state"] == "indexed" for row in public_rows),
            "indexed_not_served_count": sum(row["terminal_state"] == "indexed-not-served" for row in public_rows),
            "failure_control_count": sum(row["terminal_state"] == "unindexed" for row in public_rows),
            "note_count": sum(len(row["note_keys"]) for row in parent_rows),
            "record_only_count": sum(row["record_only"] for row in parent_rows),
            "strata": _counts(doc.get("stratum", "unspecified") for doc in recipe),
            "topic_counts": _counts(doc.get("topic", "unspecified") for doc in recipe),
            "format_counts": _counts(_content_type(source) for doc in recipe for source in _sources(doc)),
            "language_counts": _counts(
                source.get("language", doc.get("language", "unspecified")) for doc in recipe for source in _sources(doc)
            ),
            "source_byte_count": sum(path.stat().st_size for path in source_paths.values()),
            "recipe_sha256": recipe_digest(recipe),
            "library": {
                "type": library["type"], "id": library["id"],
                "collection_key": collection_key,
            },
            "zotero": {
                "client_version": zotero_client_version,
                "fulltext.pdfMaxPages": observed["pdfMaxPages"],
                "fulltext.textMaxLength": observed["textMaxLength"],
                "preferences_are": "read live from the client through the control plugin's status; "
                                   + ("a bound on this extraction (stock reindex), checked against every "
                                      "captured counter" if observed_mode == "stock" else
                                      "profile provenance only, not a bound on this extraction (see reindex)"),
                "plugin_version": observed.get("codeVersion") or observed["version"],
            },
            "reindex": _reindex_record(observed_mode, observed),
            "known_defects": [dict(defect) for defect in (known_defects or [])]
                             + _detected_defects(items, public_rows, source_paths, sources_by_id),
            "index_fulltext_max_chars": index_max_chars,
            "items_file": "items.json",
            "normalizations": {
                "linked_file_path": "absolute API path replaced by attachments:<filename>",
                "linked_file_enclosure": "file: enclosure removed if present",
            },
            "parents": parent_rows,
            "attachments": public_rows,
            "library_version": library_version,
        }
        _write_json(temp / "items.json", [_portable_item(item) for item in items])
        _write_json(temp / "manifest.json", manifest)
        _write_json(temp / EXPORT_SENTINEL, {"schema": EXPORT_SENTINEL_SCHEMA})
        if destination_owned:
            destination.rename(backup)
        temp.rename(destination)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if destination.exists() and backup.exists():
            shutil.rmtree(destination)
            backup.rename(destination)
        elif not destination.exists() and backup.exists():
            backup.rename(destination)
        raise
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return destination


def _counts(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return dict(sorted(out.items()))


class ZoteroLocalClient:
    """Small local-API transport for this one reproducible maintenance job."""

    def __init__(
        self,
        *,
        library_type: str,
        library_id: int,
        collection_key: str,
        port: int = 23119,
        api_key: str | None = None,
    ):
        scope = f"groups/{library_id}" if library_type == "group" else "users/0"
        self.prefix = f"http://127.0.0.1:{port}/api/{scope}"
        self.collection_key = collection_key
        self.api_key = api_key
        self.server_id = None
        self.library_version = 0
        self.item_library_version = 0
        self.last_item_page_versions = []
        self.last_fulltext_version = None
        self.plugin_base = f"http://127.0.0.1:{port}/search-works/fulltext/"

    def _request(self, path: str, *, method: str = "GET", body=None):
        headers = dict(API_HEADERS)
        if body is not None:
            headers["Content-Type"] = "application/json"
        if method != "GET":
            if not self.api_key:
                raise GoldenFixtureError(
                    "injection needs ZOTEUS_LOCAL_API_KEY from a Zotero 10 local grant"
                )
            self._probe()
            headers["Zotero-API-Key"] = self.api_key
            headers["Zotero-Server-ID"] = self.server_id
        request = urllib.request.Request(
            self.prefix + path,
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
                server_id = response.headers.get("Zotero-Server-ID")
                version = response.headers.get("Last-Modified-Version")
                if server_id:
                    self.server_id = server_id
                if version and version.isdigit():
                    self.library_version = int(version)
                return (json.loads(raw) if raw else None), response.headers
        except Exception as error:
            raise GoldenFixtureError(f"Zotero local API {method} {path} failed: {error}") from error

    def _probe(self):
        if self.server_id is None:
            self._request("/items?limit=1")
        if self.server_id is None:
            raise GoldenFixtureError("Zotero 10 local API did not return Zotero-Server-ID")

    def _paged(self, path: str) -> list[dict]:
        out = []
        start = 0
        versions = []
        while True:
            separator = "&" if "?" in path else "?"
            page, headers = self._request(f"{path}{separator}limit=100&start={start}")
            if not isinstance(page, list):
                raise GoldenFixtureError(f"Zotero local API {path} did not return an item array")
            out.extend(page)
            version = headers.get("Last-Modified-Version")
            if version and version.isdigit():
                self.item_library_version = int(version)
                versions.append(int(version))
            else:
                raise GoldenFixtureError(f"Zotero local API {path} omitted Last-Modified-Version")
            total = int(headers.get("Total-Results", len(out)))
            if not page or len(out) >= total:
                self.last_item_page_versions = versions
                return out
            start += len(page)

    def list_top_items(self):
        key = urllib.parse.quote(self.collection_key, safe="")
        return self._paged(f"/collections/{key}/items/top")

    def get_children(self, parent_key):
        return self._paged(f"/items/{urllib.parse.quote(parent_key, safe='')}/children")

    def write_items(self, payloads):
        response, _ = self._request("/items", method="POST", body=payloads)
        failed = response.get("failed", {})
        if failed:
            raise GoldenFixtureError(f"Zotero rejected fixture item(s): {failed}")
        out = []
        for index, payload in enumerate(payloads):
            result = response.get("successful", {}).get(str(index))
            if result is None and str(index) in response.get("unchanged", {}):
                result = {"key": payload.get("key"), "version": payload.get("version", 0)}
            if not result or not result.get("key"):
                raise GoldenFixtureError(f"Zotero returned no key for write item {index}")
            data = {key: value for key, value in payload.items() if key not in {"key", "version"}}
            data.update({"key": result["key"], "version": result.get("version", 0)})
            out.append({"key": result["key"], "version": result.get("version", 0), "data": data})
        return out

    def upload_file(
        self, key: str, path: Path, content_type: str, *, charset: str | None = None,
        previous_md5: str | None = None,
    ) -> None:
        """Store a file on a stored (imported_file) attachment: the local API's own
        3-phase upload flow -- authorize, POST bytes, register. A group library has no
        other way to receive attachment bytes (verified 2026-09-04: linked_file is
        refused outright, 400 "Linked files can only be added to user library").
        Mirrors the upstream product's own proven flow (fork/src/api/local-writes.ts,
        LocalWriteClient.uploadFile), library-scoped through self.prefix rather than
        upstream's hardcoded personal-library-only path."""
        if not self.api_key:
            raise GoldenFixtureError("file upload needs ZOTEUS_LOCAL_API_KEY from a Zotero 10 local grant")
        self._probe()
        digest = hashlib.md5()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        md5 = digest.hexdigest()
        key_quoted = urllib.parse.quote(key, safe="")
        item_url = f"{self.prefix}/items/{key_quoted}/file"
        if previous_md5 is not None and not re.fullmatch(r"[0-9a-f]{32}", previous_md5):
            raise GoldenFixtureError(f"{key}: existing attachment has an invalid md5")
        common_headers = dict(API_HEADERS)
        common_headers.update({
            "If-Match" if previous_md5 else "If-None-Match": previous_md5 or "*",
            "Zotero-API-Key": self.api_key,
            "Zotero-Server-ID": self.server_id,
        })

        # A bare MIME type here: Zotero copies the authorization's contentType onto the
        # attachment item verbatim, so a "type; charset=x" value becomes the item's content
        # type (padme, 2026-09-06: 'text/plain;+charset=windows-1252'). The charset travels
        # in its own parameter, which is also what the web API's upload authorization takes.
        if ";" in content_type:
            raise GoldenFixtureError(f"upload contentType must be a bare MIME type, got {content_type!r}")
        authorize_fields = {
            "md5": md5, "filename": path.name, "filesize": str(path.stat().st_size),
            "mtime": str(int(path.stat().st_mtime * 1000)), "contentType": content_type,
        }
        if charset:
            authorize_fields["charset"] = charset
        authorize_body = urllib.parse.urlencode(authorize_fields).encode("utf-8")
        authorize_headers = {**common_headers, "Content-Type": "application/x-www-form-urlencoded"}
        request = urllib.request.Request(item_url, data=authorize_body, headers=authorize_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                auth = json.loads(response.read() or b"{}")
        except Exception as error:
            raise GoldenFixtureError(f"{key}: upload authorization failed: {error}") from error
        if auth.get("exists"):
            return  # identical bytes already stored under this key

        upload_url, upload_key = auth.get("url"), auth.get("uploadKey")
        if not upload_url or not upload_key:
            raise GoldenFixtureError(f"{key}: Zotero did not return an upload URL")
        upload_request = urllib.request.Request(
            upload_url, data=path.read_bytes(),
            headers={"Content-Type": "application/octet-stream"}, method="POST",
        )
        try:
            with urllib.request.urlopen(upload_request, timeout=600):
                pass
        except Exception as error:
            raise GoldenFixtureError(f"{key}: file-bytes upload failed: {error}") from error

        register_body = urllib.parse.urlencode({"upload": upload_key}).encode("utf-8")
        register_headers = {**common_headers, "Content-Type": "application/x-www-form-urlencoded"}
        register_request = urllib.request.Request(item_url, data=register_body, headers=register_headers, method="POST")
        try:
            with urllib.request.urlopen(register_request, timeout=120):
                pass
        except Exception as error:
            raise GoldenFixtureError(f"{key}: upload registration failed: {error}") from error

    def fulltext_since(self, since=0):
        result, _ = self._request(f"/fulltext?since={since}")
        if not isinstance(result, dict):
            raise GoldenFixtureError("Zotero /fulltext census is not an object")
        return result

    def get_fulltext(self, key):
        """The /fulltext body, or None on Zotero's 404 for an attachment with no
        content (an empty missing-marked row, or no row).  Other failures raise."""
        try:
            result, headers = self._request(f"/items/{urllib.parse.quote(key, safe='')}/fulltext")
        except GoldenFixtureError as error:
            cause = error.__cause__
            if isinstance(cause, urllib.error.HTTPError) and cause.code == 404:
                return None
            raise
        version = headers.get("Last-Modified-Version")
        if not version or not version.isdigit():
            raise GoldenFixtureError("Zotero fulltext response omitted Last-Modified-Version")
        self.last_fulltext_version = int(version)
        return result

    def _plugin_request(self, path: str, body=None):
        request = urllib.request.Request(
            self.plugin_base + path,
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers={} if body is None else {"Content-Type": "application/json"},
            method="GET" if body is None else "POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except Exception as error:
            raise GoldenFixtureError(
                "the full-text control plugin is required to reindex fixture attachments: "
                f"{error}"
            ) from error

    def plugin_status(self) -> dict:
        """The plugin's own status: version, the mode of its last reindex, the two
        extraction preferences read live.  Provenance for the export manifest."""
        return self._plugin_request("status")

    def reindex_fulltext(
        self, keys: list[str], *, complete: bool = False, poll: float = 1.0, max_wait: float = 3600,
    ) -> dict[str, dict]:
        """Force extraction to run and settle; return the terminal state of every key.

        ``complete`` is handed to the plugin as the reindex mode: False (stock) lets
        Zotero apply its page and character limits, True ignores them.  The plugin
        must echo the mode it queued, or the request is refused as running on a
        plugin that ignores the flag (every version before 0.2.0 did).

        A forced reindex is not guaranteed to reach ``indexed``: a document with
        no extractable text (an un-OCR'd scan) or an unsupported container
        (DjVu) settles at ``unindexed`` once Zotero has genuinely finished
        trying, and that is real ground truth for the export to capture -- one
        of ticket 0029's own declared failure-control cases, not a failure to
        wait past. Requiring ``state == "indexed"`` for every key made this
        hang the full ``max_wait`` and then raise, for any recipe containing
        such a document -- the two Vietnamese volumes ruled to stay in the
        fixture on 2026-09-04 (DECISIONS.md) trigger it every time.

        What this still enforces: the reindex actually *ran* -- queued, then
        the plugin's own ``busy``/``running`` counters idle -- before any state
        is trusted. A state read the instant after queuing, before Zotero has
        started, is not evidence of anything, so idleness must hold across two
        consecutive polls before it is accepted.

        The returned rows are what the export trusts: ``state`` and the plugin's
        page/character counters as observed once idle, ``version`` after the run
        and ``previous_version`` before it.  Zotero resets ``fulltextItems.version``
        to 0 on every local extraction (fulltext.js, ``setFulltextItem``), so a
        synced version surviving the reindex unchanged means the file was never
        read -- on a client that holds the item but not its bytes, ``indexItems``
        logs "No file to index" and moves on, and nothing else would notice.
        """
        wanted = set(keys)
        query = "status?keys=" + urllib.parse.quote(",".join(keys), safe=",")
        before = self._plugin_request(query)
        previous_versions = {
            row.get("key"): row.get("version")
            for row in (before.get("items", []) if isinstance(before, dict) else [])
            if isinstance(row, dict)
        }
        queued = self._plugin_request("reindex", {"keys": keys, "complete": bool(complete)})
        if not isinstance(queued, dict):
            raise GoldenFixtureError("the full-text plugin returned a malformed reindex response")
        expected_mode = "uncapped" if complete else "stock"
        if queued.get("mode") != expected_mode:
            raise GoldenFixtureError(
                f"the full-text plugin queued mode {queued.get('mode')!r}, not {expected_mode!r}; "
                "install plugin 0.2.0 or later, which honours the complete flag and echoes the mode"
            )
        queued_keys = {
            row.get("key") for row in queued.get("queued", []) if isinstance(row, dict)
        }
        if queued_keys != wanted or queued.get("missing") or queued.get("notAttachments"):
            raise GoldenFixtureError("the full-text plugin did not queue every fixture attachment")
        started = time.monotonic()
        idle_since = None
        while time.monotonic() - started < max_wait:
            status = self._plugin_request(query)
            if not isinstance(status, dict):
                raise GoldenFixtureError("fixture attachment reindex returned malformed status")
            rows = status.get("items", [])
            by_key = {
                row.get("key"): row for row in rows
                if isinstance(row, dict) and isinstance(row.get("key"), str)
            }
            if status.get("lastError") or any(row.get("error") for row in by_key.values()):
                raise GoldenFixtureError("fixture attachment reindex reported an error")
            idle = (
                set(by_key) == wanted
                and not status.get("busy")
                and not status.get("running")
                and all(isinstance(by_key[key].get("state"), str) for key in wanted)
            )
            if idle:
                if idle_since is None:
                    idle_since = time.monotonic()
                elif time.monotonic() - idle_since >= poll:
                    return {
                        key: {
                            "state": by_key[key].get("state"),
                            "indexedPages": by_key[key].get("indexedPages"),
                            "totalPages": by_key[key].get("totalPages"),
                            "indexedChars": by_key[key].get("indexedChars"),
                            "totalChars": by_key[key].get("totalChars"),
                            "version": by_key[key].get("version"),
                            "previous_version": previous_versions.get(key),
                        }
                        for key in keys
                    }
            else:
                idle_since = None
            time.sleep(poll)
        raise GoldenFixtureError("fixture attachment reindex timed out")


def _load_recipe(path: Path) -> list[dict]:
    from fetch_recipe import load_recipe

    return load_recipe(path)


def _client(args, *, writes: bool) -> ZoteroLocalClient:
    if not args.library_id:
        raise GoldenFixtureError(
            "ticket 0029 injection/export requires the public library's --library-id"
        )
    return ZoteroLocalClient(
        library_type=args.library_type,
        library_id=args.library_id,
        collection_key=args.collection_key,
        port=args.port,
        api_key=os.environ.get("ZOTEUS_LOCAL_API_KEY") if writes else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", type=Path, default=Path(__file__).with_name("recipe.json"))
    parser.add_argument("--port", type=int, default=23119)
    parser.add_argument("--library-type", choices=("user", "group"), default="group")
    parser.add_argument("--library-id", type=int)
    parser.add_argument("--collection-key")
    commands = parser.add_subparsers(dest="command", required=True)
    inject_parser = commands.add_parser("inject")
    inject_parser.add_argument("--cache-dir", type=Path, required=True)
    inject_parser.add_argument("--reindex-mode", choices=sorted(REINDEX_MODES), default="stock",
                               help="stock: Zotero's own page/character limits apply; uncapped: both ignored")
    export_parser = commands.add_parser("export")
    export_parser.add_argument("--cache-dir", type=Path, required=True)
    export_parser.add_argument("--destination", type=Path, required=True)
    export_parser.add_argument("--zotero-client-version", required=True)
    export_parser.add_argument("--reindex-mode", choices=sorted(REINDEX_MODES), default="stock",
                               help="recorded as the plugin reports it, refused if the two disagree")
    export_parser.add_argument("--pdf-max-pages", type=int, default=None,
                               help="optional cross-check against the client's fulltext.pdfMaxPages")
    export_parser.add_argument("--text-max-length", type=int, default=None,
                               help="optional cross-check against the client's fulltext.textMaxLength")
    export_parser.add_argument("--index-max-chars", type=int, required=True)
    export_parser.add_argument(
        "--known-defect", action="append", default=[], metavar="RECIPE_ID: DESCRIPTION",
        help="a defect of the injected fixture to record in the manifest, never repaired (repeatable)",
    )
    retire_parser = commands.add_parser("retire", help="move managed parents out of the collection; no deletion")
    retire_parser.add_argument("--ids", required=True, help="comma-separated recipe ids")
    fields_parser = commands.add_parser("item-fields", help="regenerate zotero-item-fields.json from Zotero's schema")
    fields_parser.add_argument("--schema", type=Path, default=None, help="a downloaded schema.json; fetched when absent")
    fields_parser.add_argument("--output", type=Path, default=ITEM_FIELDS_FILE)
    args = parser.parse_args()
    if args.command == "item-fields":
        reduced = write_item_fields(args.output, args.schema)
        print(json.dumps({"schema_version": reduced["schema_version"], "item_types": len(reduced["item_types"]),
                          "output": str(args.output)}, indent=2))
        return 0
    if not args.collection_key:
        parser.error("--collection-key is required")
    known_defects = []
    for entry in getattr(args, "known_defect", []):
        recipe_id, separator, description = entry.partition(":")
        if not separator or not recipe_id.strip() or not description.strip():
            raise GoldenFixtureError(f"--known-defect must read 'RECIPE_ID: DESCRIPTION', got {entry!r}")
        known_defects.append({"recipe_id": recipe_id.strip(), "defect": description.strip(), "declared_by": "operator"})
    if args.command == "retire":
        ids = [value.strip() for value in args.ids.split(",") if value.strip()]
        result = retire(ids, _client(args, writes=True), collection_key=args.collection_key)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    recipe = _load_recipe(args.recipe)
    if args.command == "inject":
        result = inject(
            recipe, args.cache_dir, _client(args, writes=True),
            collection_key=args.collection_key, library_type=args.library_type,
            reindex_mode=args.reindex_mode,
        )
    else:
        result = {
            "snapshot": str(
                export_snapshot(
                    recipe,
                    _client(args, writes=True),
                    collection_key=args.collection_key,
                    destination=args.destination,
                    library={"type": args.library_type, "id": args.library_id},
                    zotero_client_version=args.zotero_client_version,
                    index_max_chars=args.index_max_chars,
                    cache_dir=args.cache_dir,
                    reindex_mode=args.reindex_mode,
                    pdf_max_pages=args.pdf_max_pages,
                    text_max_length=args.text_max_length,
                    known_defects=known_defects,
                )
            )
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GoldenFixtureError as error:
        raise SystemExit(f"golden fixture refused: {error}") from error
