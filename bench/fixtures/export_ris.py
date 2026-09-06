#!/usr/bin/env python3
"""Write the Menagerie as a RIS file a colleague imports into their own Zotero.

Ticket 0721. The committed export (`export/items.json`, `fulltext/`,
`manifest.json`) is what the harness replays; it is not something a person can
hand to Zotero. This module writes the fourth deliverable beside them: one RIS
record per recipe parent, carrying the parent's metadata, its managed tag, its
Extra lines, its child notes, and one `L1` file link per verified attachment,
as a path relative to the RIS file (`attachments/<attachment id>.<ext>`). With
`--package` it also assembles the zip that lays the attachment bytes out at
those paths, taking each file from the recipe's fetch cache only after its
sha256 matches the recipe, and refusing the whole package on any mismatch or
missing file. The RIS is committed; the bytes never are (Malynes alone is
352 MB).

Every mapping below was read off Zotero's own RIS translator (zotero/translators,
RIS.js, lastUpdated 2026-01-05) and the import path in Zotero's translate_item.js
and fileInterface.js, in the *import* direction, since that is the gesture this
file exists for:

- `TY` comes from RIS.js's `exportTypeMap`, and the type Zotero creates on import
  is `importTypeMap[TY]`, which is the inverse of that map except for the
  degenerate entries: `document` has no RIS type of its own, exports as `GEN`,
  and `GEN` imports as `journalArticle` (RIS.js's DEFAULT_IMPORT_TYPE). A type
  RIS.js does not know at all (`preprint`, `standard`) also falls to `GEN`.
  `ris_type()` returns both the tag and what it imports as; the CLI logs every
  parent whose type will not survive the round trip.
- `AU`: RIS.js splits on the first comma into lastName / firstName and, when
  there is no comma, stores a single-field (institutional) creator. The recipe's
  `author` is one free-text string and the harness injects it as exactly such a
  single-field creator, so it is emitted as given, never inverted: an inversion
  would be wrong for Vietnamese names and would make the imported library differ
  from the fixture Zotero holds.
- `LA` maps to `language`, and RIS.js drops an empty value. The recipe's
  `language_field` is the exact string the fixture writes to Zotero, empty or
  malformed on purpose for about half the core (the census's own distribution),
  so it is emitted verbatim when non-empty and omitted when empty: the import
  then leaves the field empty, as the fixture has it.
- `M2` maps to `extra` unconditionally on import (RIS.js's degenerate map; `M1`
  would land in `issue` on a journal article), and repeated `M2` lines are joined
  with newlines, so one `M2` per Extra line reproduces the parent's Extra field
  exactly. `N1` maps to a child note, one note per tag; a value that already
  carries HTML tags is stored as-is, so the recipe's note `html` goes through on
  one line, unwrapped.
- `L1` maps to `attachments/PDF`: the path is handed to Zotero's item saver,
  which resolves it as a URI relative to the RIS file first
  (`_parsePathURI(path, baseURI = the file)`) and as a path under the file's
  directory second (`_parseRelativePath`), then stores a copy (default) or a
  linked file (the import dialog's "Link to files in original location"). The
  content type is sniffed from the file, so `L1` serves every format; the
  attachment's title becomes the file name without its extension.
- `ID` is `__ignore` on import (RIS.js `degenerateImportFieldMap`), so the
  fixture's Zotero key rides along for a reader without touching the import.
- `KW` lines become tags, one per line. Only the parent's managed marker is
  emitted. Note that RIS.js splits a *single* tag on commas; the marker has none.
- Encoding: UTF-8 with a BOM and CRLF line endings. Zotero's reader
  (translate_firefox.js) locks the charset on a BOM and ignores the dialog's
  charset override; Zotero's own RIS export writes `\\r\\n`, "from spec".

What RIS cannot carry, and this module therefore does not pretend to: the
collection (Zotero's import dialog puts everything in a new collection named
after the file, so the file name is the collection name), the managed tags on
attachments and notes, an attachment's explicit charset, the attachment title,
and a parent type that only exists on Zotero's side of the map.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FIXTURES = Path(__file__).resolve().parent
DEFAULT_RECIPE = FIXTURES / "recipe.json"
DEFAULT_EXPORT = FIXTURES / "export"
DEFAULT_RIS = DEFAULT_EXPORT / "menagerie.ris"
#: Same convention as fetch_recipe.py's DEFAULT_CACHE; on the author's machine the
#: contract of 2026-09-06 puts the bytes at ~/data/golden-fixture-cache.
DEFAULT_CACHE = REPO / "corpus-cache"

SOURCE_TAG_PREFIX = "zoteus-golden-source:"
ATTACHMENT_DIR = "attachments"
BOM = "\ufeff"
NEWLINE = "\r\n"

log = logging.getLogger("export_ris")


class ExportRisError(Exception):
    pass


#: RIS.js `exportTypeMap`: the tag Zotero writes for each of its item types, and
#: the one it reads back into that same type.
EXPORT_TYPE_MAP = {
    "artwork": "ART",
    "audioRecording": "SOUND",
    "bill": "BILL",
    "blogPost": "BLOG",
    "book": "BOOK",
    "bookSection": "CHAP",
    "case": "CASE",
    "computerProgram": "COMP",
    "conferencePaper": "CONF",
    "dictionaryEntry": "DICT",
    "encyclopediaArticle": "ENCYC",
    "email": "ICOMM",
    "dataset": "DATA",
    "film": "MPCT",
    "hearing": "HEAR",
    "journalArticle": "JOUR",
    "letter": "PCOMM",
    "magazineArticle": "MGZN",
    "manuscript": "MANSCPT",
    "map": "MAP",
    "newspaperArticle": "NEWS",
    "patent": "PAT",
    "presentation": "SLIDE",
    "report": "RPRT",
    "statute": "STAT",
    "thesis": "THES",
    "videoRecording": "VIDEO",
    "webpage": "ELEC",
}

#: RIS.js `degenerateExportTypeMap`: exported under a tag that imports as another
#: type. `document` is the one the fixture uses.
DEGENERATE_EXPORT_TYPE_MAP = {
    "interview": "PCOMM",
    "instantMessage": "ICOMM",
    "forumPost": "ICOMM",
    "tvBroadcast": "MPCT",
    "radioBroadcast": "SOUND",
    "podcast": "SOUND",
    "document": "GEN",
}

DEFAULT_EXPORT_TYPE = "GEN"
DEFAULT_IMPORT_TYPE = "journalArticle"

#: What each tag imports as: the inverse of EXPORT_TYPE_MAP, plus the degenerate
#: entries RIS.js lists in `importTypeMap` for the tags above.
IMPORT_TYPE_MAP = {tag: item_type for item_type, tag in EXPORT_TYPE_MAP.items()}
IMPORT_TYPE_MAP["GEN"] = DEFAULT_IMPORT_TYPE

#: Formats whose bytes are already compressed: stored in the zip, not deflated.
STORED_FORMATS = frozenset({"pdf", "djvu", "epub", "docx", "xlsx", "odt", "jpg", "png", "zip", "tgz"})


def ris_type(item_type: str) -> tuple[str, str]:
    """(RIS `TY`, the Zotero type the import creates from it)."""
    tag = EXPORT_TYPE_MAP.get(item_type) or DEGENERATE_EXPORT_TYPE_MAP.get(item_type) or DEFAULT_EXPORT_TYPE
    return tag, IMPORT_TYPE_MAP.get(tag, DEFAULT_IMPORT_TYPE)


def source_tag(recipe_id: str) -> str:
    return SOURCE_TAG_PREFIX + recipe_id


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Recipe shapes
# ---------------------------------------------------------------------------

def is_legacy(doc: dict) -> bool:
    """The flat shape: the parent record is its own single attachment."""
    return "attachments" not in doc


def attachments_of(doc: dict) -> list[dict]:
    """The attachment records of a parent, in either shape; empty for record-only."""
    if is_legacy(doc):
        return [doc]
    sources = doc.get("attachments") or []
    return sources if isinstance(sources, list) else []


def is_pinned(source: dict) -> bool:
    pinned = source.get("sha256")
    return isinstance(pinned, str) and len(pinned) == 64


def attachment_relpath(source: dict) -> str:
    """Where the bytes sit relative to the RIS file, and the `L1` value."""
    ident = source["id"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", ident) or ".." in ident:
        raise ExportRisError(f"attachment id {ident!r} is not a safe file name")
    return f"{ATTACHMENT_DIR}/{ident}.{source.get('bytes_format', 'pdf')}"


def cache_path(source: dict, cache_dir: Path) -> Path:
    return cache_dir / f"{source['id']}.{source.get('bytes_format', 'pdf')}"


def child_notes(doc: dict) -> list[dict]:
    """The `{id, html}` child notes of the ruled shape. The legacy shape's `notes`
    is a prose string about the record, not a Zotero note, and is not one."""
    notes = doc.get("notes")
    if not isinstance(notes, list):
        return []
    return [note for note in notes if isinstance(note, dict) and isinstance(note.get("html"), str)]


def language_value(doc: dict) -> str:
    """The exact string the fixture writes to Zotero's language field."""
    if "language_field" in doc:
        value = doc["language_field"]
        return value if isinstance(value, str) else ""
    return doc.get("language", "") or ""


def extra_lines(doc: dict) -> list[str]:
    """The parent's Extra field, line by line, as golden_fixture.py writes it."""
    lines = [
        f"ticket-0029 recipe id: {doc['id']}",
        f"ticket-0029 work id: {doc.get('work_id', doc['id'])}",
        f"ticket-0029 type fidelity: {doc.get('type_fidelity', 'unreviewed')}",
        "ticket-0029 work relations: " + canonical_json(doc.get("work_relations", [])),
    ]
    if "topic" in doc:
        lines.append(f"ticket-0029 topic: {doc['topic']}")
    if "stratum" in doc:
        lines.append(f"ticket-0029 stratum: {doc['stratum']}")
    if "mechanisms" in doc:
        lines.append("ticket-0029 mechanisms: " + canonical_json(doc["mechanisms"]))
    if "retained_reason" in doc:
        lines.append(f"ticket-0029 retained reason: {doc['retained_reason']}")
    return lines


def parent_date(doc: dict) -> tuple[str, str | None]:
    """(`PY`, `DA` or None). `DA` only when the record carries a fuller `date`
    than the year, in RIS's YYYY/MM/DD/ form."""
    year = str(doc["year"])
    date = doc.get("date")
    if isinstance(date, str):
        match = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", date.strip())
        if match:
            return year, f"{match.group(1)}/{match.group(2)}/{match.group(3) or ''}/"
    return year, None


# ---------------------------------------------------------------------------
# The export, for keys and ordering
# ---------------------------------------------------------------------------

def load_export_keys(export_dir: Path | None) -> dict[str, str]:
    """recipe id -> Zotero key of the exported parent, in the export's item order
    (dict order). Empty when there is no export to read."""
    if export_dir is None:
        return {}
    items_file = export_dir / "items.json"
    if not items_file.is_file():
        log.warning("no export at %s; records carry no Zotero key and follow recipe order", items_file)
        return {}
    keys: dict[str, str] = {}
    for item in json.loads(items_file.read_text(encoding="utf-8")):
        data = item.get("data", item)
        if data.get("itemType") in {"attachment", "note"}:
            continue
        for entry in data.get("tags", []):
            tag = entry.get("tag") if isinstance(entry, dict) else None
            if isinstance(tag, str) and tag.startswith(SOURCE_TAG_PREFIX):
                key = item.get("key", data.get("key"))
                if isinstance(key, str):
                    keys.setdefault(tag[len(SOURCE_TAG_PREFIX):], key)
    return keys


def ordered(recipe: list[dict], keys: dict[str, str]) -> list[dict]:
    """Exported parents first, in the export's order; the rest in recipe order."""
    by_id = {doc["id"]: doc for doc in recipe}
    head = [by_id[rid] for rid in keys if rid in by_id]
    seen = {doc["id"] for doc in head}
    return head + [doc for doc in recipe if doc["id"] not in seen]


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

def _one_line(value: str) -> str:
    """RIS values are one line: RIS.js joins continuation lines with a space (or a
    newline, by a length heuristic), so newlines are folded here deterministically."""
    return re.sub(r"\s*[\r\n]+\s*", " ", value).strip()


def record_tags(doc: dict, key: str | None = None) -> list[tuple[str, str]]:
    """The (tag, value) pairs of one parent, `TY` first, `ER` excluded."""
    item_type = doc.get("item_type", "document")
    tag, _ = ris_type(item_type)
    pairs: list[tuple[str, str]] = [("TY", tag)]
    if key:
        pairs.append(("ID", key))
    pairs.append(("TI", _one_line(doc["title"])))
    pairs.append(("AU", _one_line(doc["author"])))
    year, full_date = parent_date(doc)
    pairs.append(("PY", year))
    if full_date:
        pairs.append(("DA", full_date))
    language = language_value(doc)
    if language.strip():
        pairs.append(("LA", language))
    citation = doc.get("citation") if isinstance(doc.get("citation"), dict) else {}
    if citation.get("doi"):
        pairs.append(("DO", citation["doi"]))
    if citation.get("isbn"):
        pairs.append(("SN", citation["isbn"]))
    url = citation.get("url") or (doc.get("bytes_url") if is_legacy(doc) else None)
    if url:
        pairs.append(("UR", url))
    if is_legacy(doc):
        if doc.get("archive"):
            pairs.append(("DB", doc["archive"]))
        if doc.get("identifier"):
            pairs.append(("AN", doc["identifier"]))
    pairs.append(("KW", source_tag(doc["id"])))
    for line in extra_lines(doc):
        pairs.append(("M2", _one_line(line)))
    for note in child_notes(doc):
        pairs.append(("N1", _one_line(note["html"])))
    if not doc.get("record_only"):
        for source in attachments_of(doc):
            if is_pinned(source):
                pairs.append(("L1", attachment_relpath(source)))
            else:
                log.info("%s: attachment %s is unpinned, no L1", doc["id"], source.get("id"))
    return pairs


def format_record(pairs: list[tuple[str, str]]) -> str:
    lines = [f"{tag}  - {value}" for tag, value in pairs]
    lines.append("ER  - ")
    return NEWLINE.join(lines) + NEWLINE + NEWLINE


def render(recipe: list[dict], keys: dict[str, str] | None = None) -> str:
    """The whole RIS text: BOM, one record per parent, CRLF."""
    keys = keys or {}
    body = "".join(format_record(record_tags(doc, keys.get(doc["id"]))) for doc in ordered(recipe, keys))
    return BOM + body


def write_ris(text: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


# ---------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------

def packaged_attachments(recipe: list[dict]) -> list[dict]:
    """Every pinned attachment of a parent that is not record-only."""
    found = []
    for doc in recipe:
        if doc.get("record_only"):
            continue
        found.extend(source for source in attachments_of(doc) if is_pinned(source))
    return found


def verify_package_inputs(recipe: list[dict], cache_dir: Path) -> list[tuple[dict, Path]]:
    """Resolve and hash every attachment before a byte is copied; the first
    mismatch or missing file refuses the package."""
    root = cache_dir.resolve()
    if not root.is_dir():
        raise ExportRisError(f"cache directory is missing: {cache_dir}")
    verified = []
    for source in packaged_attachments(recipe):
        path = cache_path(source, root)
        if path.is_symlink() or path.resolve().parent != root:
            raise ExportRisError(f"{source['id']}: cache file must be a regular file inside the cache")
        if not path.is_file():
            raise ExportRisError(f"{source['id']}: cache file is missing: {path}")
        actual = sha256_of(path)
        if actual != source["sha256"]:
            raise ExportRisError(
                f"{source['id']}: sha256 mismatch: recipe {source['sha256']}, cache file {actual}"
            )
        verified.append((source, path))
    return verified


IMPORT_NOTE = """Menagerie -- import into Zotero
================================

1. Unzip this archive somewhere on your disk (keep {ris} and attachments/ side by side).
2. In Zotero: File > Import... > "A file (BibTeX, RIS, Zotero RDF, etc.)" > choose {ris}.
3. Leave "Place imported collections and items into new collection" checked: the items
   land in a collection named after the file.
4. File handling: "Copy files to the Zotero storage folder" (default) makes your library
   self-contained; "Link to files in original location" keeps them here as linked files.
5. Finish. Each parent carries the tag zoteus-golden-source:<recipe id>; each L1 link
   became a child attachment.
"""


def build_package(recipe: list[dict], ris_text: str, ris_name: str, cache_dir: Path, destination: Path) -> int:
    """Write the zip: the RIS at the root, verified bytes under attachments/, and
    an import note. Written to a temporary sibling and renamed, so a refused
    package leaves nothing behind. Returns the number of attachments packaged."""
    verified = verify_package_inputs(recipe, cache_dir)
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".part", dir=destination.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr(ris_name, ris_text.encode("utf-8"))
            archive.writestr("IMPORT.txt", IMPORT_NOTE.format(ris=ris_name))
            for source, path in verified:
                compress = zipfile.ZIP_STORED if source.get("bytes_format", "pdf") in STORED_FORMATS else zipfile.ZIP_DEFLATED
                archive.write(path, attachment_relpath(source), compress_type=compress)
        shutil.move(str(temp), str(destination))
    finally:
        if temp.exists():
            temp.unlink()
    return len(verified)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_recipe(path: Path) -> list[dict]:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(recipe, list) or not all(isinstance(doc, dict) and "id" in doc for doc in recipe):
        raise ExportRisError(f"{path}: a recipe is a list of records with an id")
    return recipe


def type_losses(recipe: list[dict]) -> dict[str, tuple[str, str, int]]:
    """item type -> (TY, the type it imports as, record count), for the types the
    RIS round trip changes."""
    losses: dict[str, tuple[str, str, int]] = {}
    for doc in recipe:
        item_type = doc.get("item_type", "document")
        tag, imports_as = ris_type(item_type)
        if imports_as != item_type:
            _, _, count = losses.get(item_type, (tag, imports_as, 0))
            losses[item_type] = (tag, imports_as, count + 1)
    return losses


def report_type_losses(recipe: list[dict]) -> None:
    for item_type, (tag, imports_as, count) in type_losses(recipe).items():
        log.warning("%d record(s) of type %s: no RIS type of its own, TY %s imports as %s",
                    count, item_type, tag, imports_as)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE, help="recipe.json, either shape")
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT,
                    help="the committed export; supplies Zotero keys (ID) and item order when present")
    ap.add_argument("--no-export", action="store_true", help="ignore the export even if present")
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="the recipe's verified fetch cache (for --package)")
    ap.add_argument("--ris", type=Path, default=DEFAULT_RIS, help="where the RIS file is written")
    ap.add_argument("--package", type=Path, default=None,
                    help="also assemble this zip: the RIS beside attachments/<id>.<ext>, each verified against the recipe")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try:
        recipe = load_recipe(args.recipe)
        keys = load_export_keys(None if args.no_export else args.export)
        report_type_losses(recipe)
        text = render(recipe, keys)
        write_ris(text, args.ris)
        linked = sum(1 for doc in recipe if not doc.get("record_only")
                     for source in attachments_of(doc) if is_pinned(source))
        log.info("wrote %s: %d records (%d with a Zotero key), %d attachment links",
                 args.ris, len(recipe), sum(1 for doc in recipe if doc["id"] in keys), linked)
        if args.package is not None:
            count = build_package(recipe, text, args.ris.name, args.cache_dir, args.package)
            log.info("wrote %s: %d attachments verified and packaged", args.package, count)
    except ExportRisError as error:
        log.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
