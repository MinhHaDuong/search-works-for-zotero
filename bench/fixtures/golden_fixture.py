#!/usr/bin/env python3
"""Inject ticket 0029's source recipe into Zotero and export its API snapshot.

This module owns no corpus content.  The recipe remains authoritative, source bytes
must already match its hashes, and an export is always read from a running Zotero.  The
small in-memory objects in the test suite are controls for this machinery, not a golden
export and are never written under ``bench/fixtures``.

Injection is an idempotent reconciliation.  Stable, namespaced tags associate Zotero
items with recipe ids; a second run updates drift and creates nothing.  Export fails
closed unless every recipe record has exactly one linked attachment with indexed text.
The client version and both extraction preferences are required inputs: silently using
defaults would make two exports from different Zotero profiles look like one corpus.
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
import urllib.parse
import urllib.request
from pathlib import Path


SOURCE_TAG_PREFIX = "zoteus-golden-source:"
ATTACHMENT_TAG_PREFIX = "zoteus-golden-attachment:"
EXPORT_SENTINEL = ".zoteus-golden-export.json"
EXPORT_SENTINEL_SCHEMA = "zoteus-golden-export/v1"
API_HEADERS = {
    "Zotero-API-Version": "3",
    "x-zotero-connector-api-version": "3",
}
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "djvu": "image/vnd.djvu",
    "html": "text/html",
    "wikitext": "text/plain",
    "txt": "text/plain; charset=utf-8",
    "epub": "application/epub+zip",
}


class GoldenFixtureError(RuntimeError):
    """A fixture invariant failed; no partial result may be trusted."""


def source_tag(recipe_id: str) -> str:
    return SOURCE_TAG_PREFIX + recipe_id


def attachment_tag(recipe_id: str) -> str:
    return ATTACHMENT_TAG_PREFIX + recipe_id


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


def _tag_values(data: dict) -> list[str]:
    return [
        entry.get("tag")
        for entry in data.get("tags", [])
        if isinstance(entry, dict) and isinstance(entry.get("tag"), str)
    ]


def _managed_markers(data: dict) -> list[str]:
    return [
        tag for tag in _tag_values(data)
        if tag.startswith(SOURCE_TAG_PREFIX) or tag.startswith(ATTACHMENT_TAG_PREFIX)
    ]


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
    desired = {
        "itemType": doc.get("item_type", "document"),
        "title": doc["title"],
        "creators": [{"creatorType": "author", "name": doc["author"]}],
        "date": str(doc["year"]),
        "language": doc["language"],
        "extra": "\n".join([
            f"ticket-0029 recipe id: {doc['id']}",
            f"ticket-0029 work id: {doc.get('work_id', doc['id'])}",
            f"ticket-0029 type fidelity: {doc.get('type_fidelity', 'unreviewed')}",
            "ticket-0029 work relations: " + canonical_json(doc.get("work_relations", [])),
        ]),
        "tags": [{"tag": source_tag(doc["id"])}],
        "collections": [collection_key],
    }
    if "attachments" not in doc:
        desired.update(url=doc["bytes_url"], archive=doc["archive"], archiveLocation=doc["identifier"])
    return desired


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
    fmt = doc.get("bytes_format", "pdf")
    common = {
        "itemType": "attachment",
        "parentItem": parent_key,
        "title": doc.get("title", parent["title"]),
        "contentType": CONTENT_TYPES.get(fmt, "application/octet-stream"),
        "tags": [{"tag": attachment_tag(doc["id"])}],
    }
    if library_type == "group":
        common.update(linkMode="imported_file", filename=path.name)
    else:
        common.update(linkMode="linked_file", path=str(path))
    return common


def _managed_equal(item: dict, desired: dict) -> bool:
    data = _data(item)
    return all(data.get(field) == value for field, value in desired.items())


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


def inject(
    recipe: list[dict], cache_dir: Path, client, *, collection_key: str, library_type: str = "user"
) -> dict[str, int]:
    """Reconcile recipe parents and attachments; return mutation counts.

    A group library needs its attachment bytes uploaded (client.upload_file) before
    reindex_fulltext has anything to extract from -- a user-library linked_file
    attachment needs no such step, since its bytes are already reachable by path.
    Group uploads are deliberately repeated even when item metadata already matches:
    Zotero commits the attachment item before its three-phase file upload, so metadata
    cannot attest that a previous upload completed or that its bytes match the recipe.
    """
    source_paths = verify_source_bytes(recipe, cache_dir)
    parents = client.list_top_items()
    wanted_ids = {doc["id"] for doc in recipe}
    if len(wanted_ids) != len(recipe):
        raise GoldenFixtureError("source recipe contains duplicate ids")
    doc_by_id = {doc["id"]: doc for doc in recipe}
    parent_by_id = {}
    attachment_by_id = {}
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
            raise GoldenFixtureError(f"stale managed parent {recipe_id} is not in the source recipe")
        if recipe_id in parent_by_id:
            raise GoldenFixtureError(
                f"duplicate parent for managed marker {source_tag(recipe_id)}"
            )
        parent_by_id[recipe_id] = item
        expected_attachment_ids = {source["id"] for source in _sources(doc_by_id[recipe_id])}
        for attachment in client.get_children(_key(item)):
            markers = _managed_markers(_data(attachment))
            if len(markers) != 1 or not markers[0].startswith(ATTACHMENT_TAG_PREFIX):
                raise GoldenFixtureError(f"{recipe_id}: managed parent has an unowned child")
            attachment_id = markers[0][len(ATTACHMENT_TAG_PREFIX):]
            _require_only_managed_marker(
                _data(attachment), attachment_tag(attachment_id), f"attachment {_key(attachment)}"
            )
            if attachment_id not in expected_attachment_ids or attachment_id in attachment_by_id:
                raise GoldenFixtureError(f"{recipe_id}: stale or duplicate attachment {attachment_id}")
            attachment_by_id[attachment_id] = attachment
    counts = {
        "created_parents": 0,
        "updated_parents": 0,
        "created_attachments": 0,
        "updated_attachments": 0,
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
                content_type = CONTENT_TYPES.get(source.get("bytes_format", "pdf"), "application/octet-stream")
                client.upload_file(
                    _key(attachment), source_path, content_type,
                    previous_md5=existing_md5 if isinstance(existing_md5, str) else None,
                )
                pending_reindex.append(_key(attachment))
            elif changed:
                pending_reindex.append(_key(attachment))
    if pending_reindex:
        client.reindex_fulltext(pending_reindex)
    return counts


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


def _snapshot_rows(
    recipe: list[dict], client, source_paths: dict[str, Path], collection_key: str,
    *, library_type: str = "user",
) -> tuple[list[dict], list[dict], int]:
    parents = client.list_top_items()
    opening_versions = _last_item_page_versions(client)
    if not opening_versions or len(set(opening_versions)) != 1:
        raise GoldenFixtureError("Zotero item pages did not share one library version")
    starting_item_version = opening_versions[0]
    items = []
    attachments = []
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
        if len(children) != len(sources):
            raise GoldenFixtureError(f"{doc['id']}: injected parent does not have exactly its recipe attachments")
        parent_key = _key(parent)
        if parent_key in seen_item_keys:
            raise GoldenFixtureError(f"duplicate exported Zotero item key {parent_key}")
        seen_item_keys.add(parent_key)
        items.append(parent)
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
            if attachment_key not in census:
                raise GoldenFixtureError(f"{source['id']}: attachment has no /fulltext census entry")
            try:
                fulltext = client.get_fulltext(attachment_key)
            except (KeyError, LookupError) as error:
                raise GoldenFixtureError(f"{source['id']}: attachment has no /fulltext response") from error
            if not isinstance(census[attachment_key], int) or census[attachment_key] < 0:
                raise GoldenFixtureError(f"{source['id']}: invalid /fulltext census version")
            if not isinstance(fulltext, dict) or not isinstance(fulltext.get("content"), str) or not fulltext["content"].strip():
                raise GoldenFixtureError(f"{source['id']}: malformed /fulltext response")
            response_version = getattr(client, "last_fulltext_version", fulltext.get("version", None))
            if response_version != census[attachment_key]:
                raise GoldenFixtureError(f"{source['id']}: fulltext body version does not match its census")
            if not isinstance(fulltext.get("indexedPages"), int) or not isinstance(fulltext.get("totalPages"), int):
                raise GoldenFixtureError(f"{source['id']}: /fulltext lacks integer indexedPages/totalPages")
            indexed_pages, total_pages = fulltext["indexedPages"], fulltext["totalPages"]
            if indexed_pages < 0 or total_pages < 0 or indexed_pages > total_pages:
                raise GoldenFixtureError(f"{source['id']}: invalid indexedPages/totalPages relation")
            if census[attachment_key] == 0:
                version_zero_bodies[attachment_key] = (source["id"], fulltext)
            items.append(child)
            row = {
                "recipe_id": doc["id"], "parent_key": parent_key,
                "attachment_key": attachment_key,
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
    return items, attachments, starting_item_version


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _refresh_fulltext_from_pinned_sources(
    recipe: list[dict], client, source_paths: dict[str, Path], collection_key: str,
    cache_dir: Path, *, library_type: str = "user",
) -> None:
    """Force the export's extraction from the bytes verified around this operation.

    reindex_fulltext (the plugin call) is what forces the actual re-extraction; no
    item write is needed to trigger it, and the metadata equality check just above
    already proves the live item matches what the recipe wants."""
    parents = client.list_top_items()
    keys = []
    for doc in recipe:
        parent = _one_marked(parents, source_tag(doc["id"]), "parent")
        if parent is None or not _managed_equal(parent, _desired_parent(doc, collection_key)):
            raise GoldenFixtureError(f"{doc['id']}: parent metadata drifted from the source recipe")
        children = client.get_children(_key(parent))
        if len(children) != len(_sources(doc)):
            raise GoldenFixtureError(f"{doc['id']}: injected parent has a missing or extra child")
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

    client.reindex_fulltext(keys)
    # A linked file can change while Zotero is reading it.  Do not attest or export
    # unless the complete source set still has the recipe hashes after extraction.
    verify_source_bytes(recipe, cache_dir)


def _portable_item(item: dict) -> dict:
    """Emit only fields reviewed as inputs to the replay/index build."""
    data = _data(item)
    common = {"key", "version", "itemType", "title", "tags"}
    if data.get("itemType") == "attachment":
        allowed = common | {"parentItem", "linkMode", "contentType", "path", "filename", "extra"}
    else:
        allowed = common | {
            "creators", "date", "language", "url", "archive", "archiveLocation",
            "extra", "collections",
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


def export_snapshot(
    recipe: list[dict],
    client,
    *,
    collection_key: str,
    destination: Path,
    library: dict,
    zotero_client_version: str,
    pdf_max_pages: int,
    text_max_length: int,
    index_max_chars: int,
    cache_dir: Path,
) -> Path:
    """Capture raw items/fulltext into an atomically replaced snapshot directory."""
    if library.get("type") not in {"user", "group"} or not isinstance(library.get("id"), int):
        raise GoldenFixtureError("the fixture export must identify its public Zotero library")
    if not zotero_client_version.strip():
        raise GoldenFixtureError("Zotero client version must be recorded")
    for name, value in (
        ("fulltext.pdfMaxPages", pdf_max_pages),
        ("fulltext.textMaxLength", text_max_length),
        ("index fulltext max chars", index_max_chars),
    ):
        if not isinstance(value, int) or value <= 0:
            raise GoldenFixtureError(f"{name} must be recorded as a positive integer")

    source_paths = verify_source_bytes(recipe, cache_dir)
    _refresh_fulltext_from_pinned_sources(
        recipe, client, source_paths, collection_key, cache_dir, library_type=library["type"]
    )
    items, attachment_rows, library_version = _snapshot_rows(
        recipe, client, source_paths, collection_key, library_type=library["type"]
    )
    # This is deliberately after the API capture and immediately before staging the
    # snapshot: extraction must still be attributable to the exact pinned source bytes.
    verify_source_bytes(recipe, cache_dir)
    destination, destination_owned = _safe_export_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    backup = Path(tempfile.mkdtemp(prefix=f".{destination.name}-previous-", dir=destination.parent))
    backup.rmdir()
    try:
        (temp / "fulltext").mkdir()
        public_rows = []
        for row in attachment_rows:
            body = row.pop("body")
            _write_json(temp / row["fulltext_file"], _portable_fulltext(body))
            public_rows.append(row)
        manifest = {
            "schema_version": 1,
            "parent_item_count": len(recipe),
            "attachment_count": len(public_rows),
            "source_byte_count": sum(path.stat().st_size for path in source_paths.values()),
            "recipe_sha256": recipe_digest(recipe),
            "library": {
                "type": library["type"], "id": library["id"],
                "collection_key": collection_key,
            },
            "zotero": {
                "client_version": zotero_client_version,
                "fulltext.pdfMaxPages": pdf_max_pages,
                "fulltext.textMaxLength": text_max_length,
            },
            "index_fulltext_max_chars": index_max_chars,
            "items_file": "items.json",
            "normalizations": {
                "linked_file_path": "absolute API path replaced by attachments:<filename>",
                "linked_file_enclosure": "file: enclosure removed if present",
            },
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
        self, key: str, path: Path, content_type: str, *, previous_md5: str | None = None,
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

        authorize_body = urllib.parse.urlencode({
            "md5": md5, "filename": path.name, "filesize": str(path.stat().st_size),
            "mtime": str(int(path.stat().st_mtime * 1000)), "contentType": content_type,
        }).encode("utf-8")
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
        result, headers = self._request(f"/items/{urllib.parse.quote(key, safe='')}/fulltext")
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

    def reindex_fulltext(self, keys: list[str], *, poll: float = 1.0, max_wait: float = 3600) -> None:
        """Force extraction to run and settle; accept whatever terminal state results.

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
        """
        wanted = set(keys)
        queued = self._plugin_request("reindex", {"keys": keys})
        if not isinstance(queued, dict):
            raise GoldenFixtureError("the full-text plugin returned a malformed reindex response")
        queued_keys = {
            row.get("key") for row in queued.get("queued", []) if isinstance(row, dict)
        }
        if queued_keys != wanted or queued.get("missing") or queued.get("notAttachments"):
            raise GoldenFixtureError("the full-text plugin did not queue every fixture attachment")
        started = time.monotonic()
        query = "status?keys=" + urllib.parse.quote(",".join(keys), safe=",")
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
                    return
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
    parser.add_argument("--library-id", type=int, required=True)
    parser.add_argument("--collection-key", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    inject_parser = commands.add_parser("inject")
    inject_parser.add_argument("--cache-dir", type=Path, required=True)
    export_parser = commands.add_parser("export")
    export_parser.add_argument("--cache-dir", type=Path, required=True)
    export_parser.add_argument("--destination", type=Path, required=True)
    export_parser.add_argument("--zotero-client-version", required=True)
    export_parser.add_argument("--pdf-max-pages", type=int, required=True)
    export_parser.add_argument("--text-max-length", type=int, required=True)
    export_parser.add_argument("--index-max-chars", type=int, required=True)
    args = parser.parse_args()
    recipe = _load_recipe(args.recipe)
    if args.command == "inject":
        result = inject(
            recipe, args.cache_dir, _client(args, writes=True),
            collection_key=args.collection_key, library_type=args.library_type,
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
                    pdf_max_pages=args.pdf_max_pages,
                    text_max_length=args.text_max_length,
                    index_max_chars=args.index_max_chars,
                    cache_dir=args.cache_dir,
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
