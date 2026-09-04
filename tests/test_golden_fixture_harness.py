"""The golden corpus can be injected once, exported from Zotero, and replayed offline.

The tests use invented one-item API responses.  They prove the machinery without
pretending those responses are ticket 0029's still-unavailable live export.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import copy
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "bench" / "fixtures"


def load_python_fixture():
    spec = importlib.util.spec_from_file_location("golden_fixture", FIXTURES / "golden_fixture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gf = load_python_fixture()


def load_run_build():
    spec = importlib.util.spec_from_file_location("run_build", REPO / "bench" / "run_build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recipe_for(payload: bytes) -> list[dict]:
    return [
        {
            "id": "invented-1900-control",
            "title": "Invented control",
            "author": "Fixture Author",
            "year": 1900,
            "language": "en",
            "tier": "MUST",
            "facet": "core",
            "archive": "internet-archive",
            "identifier": "invented-control",
            "bytes_url": "https://archive.org/download/invented-control/control.pdf",
            "bytes_format": "pdf",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "license_basis": "Invented by this test.",
        }
    ]


def representative_recipe(payloads: tuple[bytes, bytes]) -> list[dict]:
    sources = []
    for name, payload, fmt, role in (
        ("invented-pdf", payloads[0], "pdf", "primary"),
        ("invented-html", payloads[1], "html", "alternate-format"),
    ):
        sources.append({
            "id": name, "language": "en", "role": role,
            "relation": "same-text-different-format",
            "selection_expectation": "indexed" if role == "primary" else "skipped-first-with-text",
            "cap_expectations": {"pages": "does-not-cross", "chars": "does-not-cross",
                                 "combined": "neither", "locators": {}},
            **({} if role == "primary" else {"skip_reason": "same-language sibling suppressed by first-with-text"}),
            "archive": "internet-archive",
            "identifier": "invented-control", "bytes_url": f"https://archive.org/download/invented-control/{name}.{fmt}",
            "bytes_format": fmt, "sha256": hashlib.sha256(payload).hexdigest(),
            "license_basis": "Invented by this test.",
        })
    return [{
        "id": "invented-work", "title": "Invented work", "author": "Fixture Author",
        "year": 1900, "language": "en", "tier": "MUST", "facet": "core",
        "item_type": "journalArticle", "type_fidelity": "correct",
        "work_id": "invented-work", "work_relations": [], "structural_features": [], "attachments": sources,
    }]


class MemoryZotero:
    def __init__(self):
        self.items = {}
        self.fulltexts = {}
        self.writes = []
        self.next_key = 1
        self.library_version = 0
        self.reindexes = []
        self.uploads = []

    def list_top_items(self):
        return [item for item in self.items.values() if not item["data"].get("parentItem")]

    def get_children(self, parent_key):
        return [item for item in self.items.values() if item["data"].get("parentItem") == parent_key]

    def write_items(self, payloads):
        out = []
        for payload in payloads:
            data = dict(payload)
            key = data.pop("key", None) or f"ZZ{self.next_key:06d}"
            self.next_key += 1
            data.pop("version", None)
            self.library_version += 1
            wrapped = {"key": key, "version": self.library_version,
                       "data": {**data, "key": key, "version": self.library_version}}
            self.items[key] = wrapped
            self.writes.append(payload)
            out.append(wrapped)
        return out

    def fulltext_since(self, since=0):
        return {key: body.get("version", 0) for key, body in self.fulltexts.items()
                if since == 0 or body.get("version", 0) > since}

    def get_fulltext(self, key):
        return self.fulltexts[key]

    def reindex_fulltext(self, keys):
        self.reindexes.append(list(keys))

    def upload_file(self, key, path, content_type, *, previous_md5=None):
        self.uploads.append((key, path, content_type, previous_md5))
        self.items[key]["data"]["md5"] = hashlib.md5(path.read_bytes()).hexdigest()


def test_injection_is_idempotent_and_recipe_owned(tmp_path):
    payload = b"%PDF-1.4\ninvented control\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()

    first = gf.inject(recipe, cache, zotero, collection_key="COLLECT1")
    writes_after_first = len(zotero.writes)
    second = gf.inject(recipe, cache, zotero, collection_key="COLLECT1")

    assert first == {"created_parents": 1, "updated_parents": 0,
                     "created_attachments": 1, "updated_attachments": 0}
    assert second == {"created_parents": 0, "updated_parents": 0,
                      "created_attachments": 0, "updated_attachments": 0}
    assert len(zotero.writes) == writes_after_first
    parent = next(item["data"] for item in zotero.items.values() if item["data"]["itemType"] == "document")
    attachment = next(item["data"] for item in zotero.items.values() if item["data"]["itemType"] == "attachment")
    assert parent["title"] == recipe[0]["title"]
    assert parent["archiveLocation"] == recipe[0]["identifier"]
    assert parent["collections"] == ["COLLECT1"]
    assert attachment["linkMode"] == "linked_file"
    assert Path(attachment["path"]) == (cache / "invented-1900-control.pdf").resolve()
    assert "extra" not in attachment  # Zotero's own schema rejects extra on attachment items
    assert zotero.reindexes == [[next(
        key for key, item in zotero.items.items()
        if item["data"]["itemType"] == "attachment"
    )]]


def test_group_injection_uploads_bytes_instead_of_linking(tmp_path):
    """Zotero refuses linked-file attachments in any group library outright (400
    "Linked files can only be added to user library", verified 2026-09-04 against
    the real local API -- a permanent Zotero limitation, not a config issue). A
    group injection must instead upload the bytes and write an imported_file
    attachment carrying no machine path at all."""
    payload = b"%PDF-1.4\ninvented control\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()

    counts = gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")

    assert counts == {"created_parents": 1, "updated_parents": 0,
                      "created_attachments": 1, "updated_attachments": 0}
    attachment = next(item["data"] for item in zotero.items.values() if item["data"]["itemType"] == "attachment")
    assert attachment["linkMode"] == "imported_file"
    assert attachment["filename"] == "invented-1900-control.pdf"
    assert "path" not in attachment
    assert len(zotero.uploads) == 1
    uploaded_key, uploaded_path, uploaded_content_type, previous_md5 = zotero.uploads[0]
    assert uploaded_path == (cache / "invented-1900-control.pdf").resolve()
    assert uploaded_content_type == "application/pdf"
    assert previous_md5 is None
    # The upload must precede reindexing: extraction needs the bytes to already be there.
    assert zotero.reindexes == [[uploaded_key]]


def test_group_injection_reuploads_when_attachment_metadata_is_unchanged(tmp_path):
    payload = b"%PDF-1.4\ninvented control\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()

    gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")
    uploads_after_first = len(zotero.uploads)
    reindexes_after_first = len(zotero.reindexes)
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")

    assert len(zotero.uploads) == uploads_after_first + 1
    assert len(zotero.reindexes) == reindexes_after_first + 1
    assert zotero.uploads[-1][3] == hashlib.md5(payload).hexdigest()


def test_group_injection_retries_upload_after_metadata_creation_succeeds(tmp_path):
    payload = b"%PDF-1.4\ninvented control\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    attempts = 0
    original_upload = zotero.upload_file

    def fail_first_upload(key, path, content_type, *, previous_md5=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise gf.GoldenFixtureError("upload control failure")
        original_upload(key, path, content_type, previous_md5=previous_md5)

    zotero.upload_file = fail_first_upload
    with pytest.raises(gf.GoldenFixtureError, match="upload control failure"):
        gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")

    # The item write committed before the failed upload. A retry must not mistake
    # matching metadata for proof that the attachment bytes are already present.
    attachment_writes = len(zotero.writes)
    counts = gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")
    assert counts == {"created_parents": 0, "updated_parents": 0,
                      "created_attachments": 0, "updated_attachments": 0}
    assert len(zotero.writes) == attachment_writes
    assert len(zotero.uploads) == 1
    assert len(zotero.reindexes) == 1


def test_representative_parent_reconciles_multiple_attachments_independently(tmp_path):
    payloads = (b"%PDF-1.4\npdf body\n", b"<html>same body</html>")
    recipe = representative_recipe(payloads)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-pdf.pdf").write_bytes(payloads[0])
    (cache / "invented-html.html").write_bytes(payloads[1])
    zotero = MemoryZotero()

    first = gf.inject(recipe, cache, zotero, collection_key="COLLECT1")
    second = gf.inject(recipe, cache, zotero, collection_key="COLLECT1")

    assert first["created_parents"] == 1 and first["created_attachments"] == 2
    assert second == {"created_parents": 0, "updated_parents": 0,
                      "created_attachments": 0, "updated_attachments": 0}
    parent = next(item["data"] for item in zotero.items.values()
                  if item["data"]["itemType"] != "attachment")
    assert parent["itemType"] == "journalArticle"
    children = [item["data"] for item in zotero.items.values()
                if item["data"]["itemType"] == "attachment"]
    assert {gf._tag_values(child)[0] for child in children} == {
        gf.attachment_tag("invented-pdf"), gf.attachment_tag("invented-html")}
    assert {Path(child["path"]).name for child in children} == {"invented-pdf.pdf", "invented-html.html"}
    assert len(zotero.reindexes[0]) == 2


def test_injection_refuses_unpinned_or_changed_source_bytes_before_writing(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    cache = tmp_path / "cache"
    cache.mkdir()
    path = cache / "invented-1900-control.pdf"
    path.write_bytes(payload + b"changed")
    zotero = MemoryZotero()

    with pytest.raises(gf.GoldenFixtureError, match="sha256 mismatch"):
        gf.inject(recipe_for(payload), cache, zotero, collection_key="COLLECT1")
    unpinned = recipe_for(payload)
    unpinned[0]["sha256"] = None
    with pytest.raises(gf.GoldenFixtureError, match="not pinned"):
        gf.inject(unpinned, cache, zotero, collection_key="COLLECT1")
    assert zotero.writes == []


def test_duplicate_managed_marker_is_refused_instead_of_multiplying_items(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    marker = gf.source_tag("invented-1900-control")
    for key in ("DUP00001", "DUP00002"):
        zotero.items[key] = {"key": key, "version": 1, "data": {
            "key": key, "version": 1, "itemType": "document", "tags": [{"tag": marker}]
        }}

    with pytest.raises(gf.GoldenFixtureError, match="duplicate parent"):
        gf.inject(recipe_for(payload), cache, zotero, collection_key="COLLECT1")


@pytest.mark.parametrize("markers", [
    ["zoteus-golden-source:invented-1900-control"] * 2,
    ["zoteus-golden-source:invented-1900-control", "zoteus-golden-attachment:invented-1900-control"],
])
def test_injection_compares_raw_cross_role_marker_multiset(tmp_path, markers):
    payload = b"%PDF-1.4\ncontrol\n"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    zotero.items["PARENT01"] = {"key": "PARENT01", "version": 1, "data": {
        "key": "PARENT01", "version": 1, "itemType": "document",
        "tags": [{"tag": marker} for marker in markers],
    }}
    with pytest.raises(gf.GoldenFixtureError, match="managed marker|managed markers"):
        gf.inject(recipe_for(payload), cache, zotero, collection_key="COLLECT1")
    assert zotero.writes == []


def test_injection_refuses_an_unmarked_item_in_the_target_collection(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    zotero.items["PERSONAL1"] = {"key": "PERSONAL1", "version": 1, "data": {
        "key": "PERSONAL1", "version": 1, "itemType": "document", "tags": [],
    }}
    with pytest.raises(gf.GoldenFixtureError, match="not dedicated"):
        gf.inject(recipe_for(payload), cache, zotero, collection_key="COLLECT1")
    assert zotero.writes == []


def test_a_user_library_repin_with_no_local_hash_mismatch_is_not_yet_redetected(tmp_path):
    """Known gap, ticketed (0641, filed 2026-09-04): a correct re-pin -- the source
    file AND recipe[0]["sha256"] updated together, so verify_source_bytes sees no
    mismatch -- is not detected as attachment drift, and does not force a re-upload
    or re-extraction, because nothing in _desired_attachment's payload depends on
    the pinned hash any more. It used to: the sha256 lived in the attachment's
    `extra` field, which real Zotero rejects outright for the `attachment` item
    type (verified against its live schema, 2026-09-04) -- ticket 0632's log has
    the full story. verify_source_bytes still catches an actual mismatch between
    the recipe and the file on disk (test_injection_refuses_unpinned_or_changed_
    source_bytes_before_writing); what it cannot yet catch is a CORRECT re-pin
    silently not propagating to a stale live attachment."""
    original = b"%PDF-1.4\nfirst\n"
    changed = b"%PDF-1.4\nsecond\n"
    recipe = recipe_for(original)
    cache = tmp_path / "cache"
    cache.mkdir()
    source = cache / "invented-1900-control.pdf"
    source.write_bytes(original)
    zotero = MemoryZotero()
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1")
    attachment = next(key for key, item in zotero.items.items()
                      if item["data"]["itemType"] == "attachment")
    zotero.fulltexts[attachment] = {
        "content": "old extraction", "indexedPages": 1, "totalPages": 1, "version": 1,
    }
    reindexes_after_first = len(zotero.reindexes)

    source.write_bytes(changed)
    recipe[0]["sha256"] = hashlib.sha256(changed).hexdigest()
    counts = gf.inject(recipe, cache, zotero, collection_key="COLLECT1")

    # This is the gap, pinned down rather than asserted-away: a correct re-pin is
    # currently invisible to inject()'s reconciliation.
    assert counts == {"created_parents": 0, "updated_parents": 0,
                      "created_attachments": 0, "updated_attachments": 0}
    assert len(zotero.reindexes) == reindexes_after_first


def test_export_forces_fresh_extraction_when_hash_and_metadata_are_unchanged(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")
    attachment = next(key for key, item in zotero.items.items()
                      if item["data"]["itemType"] == "attachment")
    zotero.fulltexts[attachment] = {
        "content": "stale extraction", "indexedPages": 1, "totalPages": 1, "version": 1,
    }
    original_reindex = zotero.reindex_fulltext

    def refresh(keys):
        original_reindex(keys)
        zotero.fulltexts[attachment] = {
            "content": "fresh extraction from pinned bytes",
            "indexedPages": 1, "totalPages": 1, "version": 2,
        }

    zotero.reindex_fulltext = refresh
    destination = tmp_path / "fresh"
    export_again(recipe, zotero, cache, destination)

    assert zotero.reindexes[-1] == [attachment]
    assert len(zotero.reindexes) == 2
    exported = json.loads((destination / "fulltext" / f"{attachment}.json").read_text())
    assert exported["content"] == "fresh extraction from pinned bytes"


def test_failed_reindex_leaves_attachment_pending_and_unexportable(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()

    def fail_reindex(_keys):
        raise gf.GoldenFixtureError("reindex control failure")

    zotero.reindex_fulltext = fail_reindex
    with pytest.raises(gf.GoldenFixtureError, match="reindex control failure"):
        gf.inject(recipe, cache, zotero, collection_key="COLLECT1")
    # inject() still fails loud on a reindex error (unchanged) -- the operator knows
    # the run did not complete. What this test used to also prove is now a known,
    # ticketed gap (0641, filed 2026-09-04): the attachment item's own fields no
    # longer carry a "pending" marker (extra was the only place it lived, and real
    # Zotero rejects extra on attachment items -- verified against its live schema),
    # so a SEPARATE export attempt against this same half-failed state would no
    # longer be caught by _managed_equal the way it was before. Not exercised or
    # asserted here on purpose, rather than leaving a false-passing assertion.


def test_local_client_verifies_plugin_reindex_completion(monkeypatch):
    client = gf.ZoteroLocalClient(
        library_type="group", library_id=4321, collection_key="COLLECT1"
    )
    idle_indexed = {"busy": False, "running": 0, "lastError": None, "items": [{
        "key": "ATTACH01", "state": "indexed", "indexedPages": 2,
        "totalPages": 2, "version": 9,
    }]}
    responses = [
        {"queued": [{"key": "ATTACH01", "libraryID": 2}], "missing": [], "notAttachments": []},
        idle_indexed,
        idle_indexed,
    ]
    monkeypatch.setattr(client, "_plugin_request", lambda *_args, **_kwargs: responses.pop(0))
    client.reindex_fulltext(["ATTACH01"], poll=0, max_wait=1)


@pytest.mark.parametrize("previous_md5, header, value", [
    (None, "If-none-match", "*"),
    ("0123456789abcdef0123456789abcdef", "If-match", "0123456789abcdef0123456789abcdef"),
])
def test_local_upload_uses_the_correct_file_precondition(
    tmp_path, monkeypatch, previous_md5, header, value,
):
    source = tmp_path / "control.pdf"
    source.write_bytes(b"%PDF-1.4\ncontrol\n")
    client = gf.ZoteroLocalClient(
        library_type="group", library_id=4321, collection_key="COLLECT1", api_key="test-key"
    )
    client.server_id = "test-server"
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"exists":1}'

    def urlopen(request, **_kwargs):
        requests.append(request)
        return Response()

    monkeypatch.setattr(gf.urllib.request, "urlopen", urlopen)
    client.upload_file("ATTACH01", source, "application/pdf", previous_md5=previous_md5)

    assert len(requests) == 1
    assert requests[0].get_header(header) == value
    opposite = "If-match" if header == "If-none-match" else "If-none-match"
    assert requests[0].get_header(opposite) is None


def test_reindex_accepts_a_genuinely_settled_unindexed_state(monkeypatch):
    """A document with no extractable text (an un-OCR'd scan, an unsupported
    container) never reaches 'indexed' -- and that is real ground truth for
    the export to capture, one of ticket 0029's declared failure-control
    cases, not a timeout. Once Zotero has genuinely finished trying (idle
    across two consecutive polls), reindex_fulltext must return rather than
    burn the full max_wait waiting for a state that will never arrive."""
    client = gf.ZoteroLocalClient(
        library_type="group", library_id=4321, collection_key="COLLECT1"
    )
    idle_unindexed = {"busy": False, "running": 0, "lastError": None, "items": [{
        "key": "ATTACH01", "state": "unindexed", "indexedPages": 0,
        "totalPages": 0, "version": 9,
    }]}
    responses = [
        {"queued": [{"key": "ATTACH01", "libraryID": 2}], "missing": [], "notAttachments": []},
        idle_unindexed,
        idle_unindexed,
    ]
    monkeypatch.setattr(client, "_plugin_request", lambda *_args, **_kwargs: responses.pop(0))
    client.reindex_fulltext(["ATTACH01"], poll=0, max_wait=1)


def test_reindex_still_times_out_when_genuinely_never_idle(monkeypatch):
    """The idle-settle relaxation must not become a blank check: a plugin that
    never stops reporting busy (a real hang, not a settled failure-control
    case) still exhausts max_wait and raises."""
    client = gf.ZoteroLocalClient(
        library_type="group", library_id=4321, collection_key="COLLECT1"
    )
    responses = [
        {"queued": [{"key": "ATTACH01", "libraryID": 2}], "missing": [], "notAttachments": []},
    ]

    def still_busy(*_args, **_kwargs):
        return responses.pop(0) if responses else {
            "busy": True, "running": 1, "lastError": None, "items": [{
                "key": "ATTACH01", "state": "queued", "indexedPages": 0,
                "totalPages": 0, "version": None,
            }],
        }

    monkeypatch.setattr(client, "_plugin_request", still_busy)
    with pytest.raises(gf.GoldenFixtureError, match="timed out"):
        client.reindex_fulltext(["ATTACH01"], poll=0, max_wait=0.05)


def test_reindex_idle_must_hold_across_two_polls_not_one(monkeypatch):
    """A single idle-looking read the instant after queuing is not evidence
    Zotero has started, let alone finished -- idleness must be observed on
    two consecutive polls before it is trusted. A response sequence that
    flips busy/idle every poll must never satisfy that and must time out."""
    client = gf.ZoteroLocalClient(
        library_type="group", library_id=4321, collection_key="COLLECT1"
    )
    busy = {"busy": True, "running": 1, "lastError": None, "items": [{
        "key": "ATTACH01", "state": "queued", "indexedPages": 0,
        "totalPages": 0, "version": None,
    }]}
    idle = {"busy": False, "running": 0, "lastError": None, "items": [{
        "key": "ATTACH01", "state": "unindexed", "indexedPages": 0,
        "totalPages": 0, "version": 9,
    }]}
    responses = [
        {"queued": [{"key": "ATTACH01", "libraryID": 2}], "missing": [], "notAttachments": []},
    ]
    status_calls = [0]

    def flipping(*_args, **_kwargs):
        if responses:
            return responses.pop(0)
        status_calls[0] += 1
        return idle if status_calls[0] % 2 else busy

    monkeypatch.setattr(client, "_plugin_request", flipping)
    with pytest.raises(gf.GoldenFixtureError, match="timed out"):
        client.reindex_fulltext(["ATTACH01"], poll=0, max_wait=0.05)


def exported_snapshot(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")
    attachment = next(key for key, item in zotero.items.items()
                      if item["data"]["itemType"] == "attachment")
    zotero.fulltexts[attachment] = {
        "content": "offline golden control body",
        "indexedPages": 2,
        "totalPages": 3,
        "version": 17,
    }
    dest = tmp_path / "snapshot"
    gf.export_snapshot(
        recipe,
        zotero,
        collection_key="COLLECT1",
        destination=dest,
        library={"type": "group", "id": 4321},
        zotero_client_version="10.0.0-test",
        pdf_max_pages=100,
        text_max_length=500000,
        index_max_chars=40000,
        cache_dir=cache,
    )
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    return recipe, dest, attachment, zotero, cache, recipe_path


def test_export_is_raw_complete_atomic_and_bound_to_recipe(tmp_path):
    recipe, dest, attachment, zotero, cache, _ = exported_snapshot(tmp_path)
    manifest = json.loads((dest / "manifest.json").read_text())
    items = json.loads((dest / "items.json").read_text())
    fulltext = json.loads((dest / "fulltext" / f"{attachment}.json").read_text())

    assert manifest["recipe_sha256"] == gf.recipe_digest(recipe)
    assert manifest["zotero"] == {
        "client_version": "10.0.0-test",
        "fulltext.pdfMaxPages": 100,
        "fulltext.textMaxLength": 500000,
    }
    assert manifest["index_fulltext_max_chars"] == 40000
    assert manifest["attachments"] == [{
        "recipe_id": "invented-1900-control",
        "parent_key": manifest["attachments"][0]["parent_key"],
        "attachment_key": attachment,
        "fulltext_file": f"fulltext/{attachment}.json",
        "fulltext_version": 17,
        "indexed_pages": 2,
        "total_pages": 3,
        "indexed_chars": None,
        "total_chars": None,
    }]
    assert manifest["parent_item_count"] == 1
    assert manifest["attachment_count"] == 1
    assert manifest["source_byte_count"] == len(b"%PDF-1.4\ncontrol\n")
    assert len(items) == 2
    assert fulltext["content"] == "offline golden control body"
    assert str(tmp_path) not in json.dumps(items)
    linked = next(item["data"] for item in items if item["data"]["itemType"] == "attachment")
    # A stored (imported_file) group attachment carries no path at all -- Zotero owns the
    # bytes under its own storage directory, so there is nothing machine-specific to leak
    # or normalize, unlike a user-library linked_file attachment's absolute local path.
    assert linked["linkMode"] == "imported_file"
    assert linked["filename"] == "invented-1900-control.pdf"
    assert "path" not in linked
    assert manifest["normalizations"]["linked_file_path"].startswith("absolute API path")
    assert json.loads((dest / gf.EXPORT_SENTINEL).read_text()) == {
        "schema": gf.EXPORT_SENTINEL_SCHEMA,
    }

    old = (dest / "manifest.json").read_bytes()
    with pytest.raises(gf.GoldenFixtureError, match="no /fulltext"):
        client = zotero
        client.fulltexts.clear()
        gf.export_snapshot(
            recipe, client, collection_key="COLLECT1", destination=dest,
            library={"type": "group", "id": 4321}, zotero_client_version="10.0.0-test",
            pdf_max_pages=100, text_max_length=500000, index_max_chars=40000,
            cache_dir=cache,
        )
    assert (dest / "manifest.json").read_bytes() == old


def test_representative_export_binds_two_attachments_and_their_semantics(tmp_path):
    payloads = (b"%PDF-1.4\npdf body\n", b"<html>same body</html>")
    recipe = representative_recipe(payloads)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-pdf.pdf").write_bytes(payloads[0])
    (cache / "invented-html.html").write_bytes(payloads[1])
    zotero = MemoryZotero()
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")
    for key, item in zotero.items.items():
        if item["data"]["itemType"] == "attachment":
            zotero.fulltexts[key] = {"content": f"body {key}", "indexedPages": 1,
                                     "totalPages": 1, "version": 17}
    snapshot = export_again(recipe, zotero, cache, tmp_path / "representative")
    recipe_path = tmp_path / "representative-recipe.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest["attachments"]) == 2
    assert {row["attachment_id"] for row in manifest["attachments"]} == {
        "invented-pdf", "invented-html"}
    assert {row["parent_key"] for row in manifest["attachments"]}.__len__() == 1
    assert run_loader(snapshot, recipe_path).returncode == 0

    manifest["attachments"][0]["role"] = "presentation"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rejected = run_loader(snapshot, recipe_path)
    assert rejected.returncode == 7
    assert "semantics do not match" in rejected.stderr


def test_export_refuses_broad_symlink_and_unowned_destinations_without_touching_them(tmp_path):
    recipe, _, _, zotero, cache, _ = exported_snapshot(tmp_path)
    unowned = tmp_path / "unowned"
    unowned.mkdir()
    keepsake = unowned / "keep.txt"
    keepsake.write_text("mine", encoding="utf-8")
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)

    for destination, message in [
        (unowned, "unowned"),
        (alias, "symlink"),
        (Path(tempfile.gettempdir()), "broad"),
    ]:
        with pytest.raises(gf.GoldenFixtureError, match=message):
            export_again(recipe, zotero, cache, destination)
    assert keepsake.read_text(encoding="utf-8") == "mine"
    assert list(target.iterdir()) == []


def test_export_public_allowlists_drop_nested_zotero_private_fields(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")
    for item in zotero.items.values():
        item["private"] = {"token": "TOP-SECRET"}
        item["data"]["relations"] = {"private-path": "/home/person/library"}
        item["links"] = {"enclosure": {"href": "file:///home/person/document.pdf"}}
    attachment = next(key for key, item in zotero.items.items()
                      if item["data"]["itemType"] == "attachment")
    zotero.fulltexts[attachment] = {
        "content": "public extraction", "indexedPages": 1, "totalPages": 1,
        "version": 3, "private": {"api_key": "FULLTEXT-SECRET"},
    }
    destination = tmp_path / "allowlisted"
    export_again(recipe, zotero, cache, destination)
    serialized = "".join(path.read_text(encoding="utf-8") for path in destination.rglob("*.json"))
    assert "TOP-SECRET" not in serialized
    assert "FULLTEXT-SECRET" not in serialized
    assert "/home/person" not in serialized


def test_offline_route_replay_has_build_routes_and_fails_closed(tmp_path):
    _, snapshot, attachment, _, _, recipe_path = exported_snapshot(tmp_path)
    probe = """
      import { loadGoldenExport, goldenReplayResponse } from './bench/fixtures/make_index_fixture.mjs';
      const fx = loadGoldenExport(process.argv[1], { recipePath: process.argv[3] });
      const base = `/api/groups/4321`;
      const top = goldenReplayResponse(fx, 'GET', `${base}/items/top?start=0&limit=100`);
      const census = goldenReplayResponse(fx, 'GET', `${base}/fulltext?since=0`);
      const full = goldenReplayResponse(fx, 'GET', `${base}/items/${process.argv[2]}/fulltext`);
      const ping = goldenReplayResponse(fx, 'GET', `/api/users/0/items?limit=1`);
      const groups = goldenReplayResponse(fx, 'GET', `/api/users/0/groups?limit=100&start=0`);
      const miss = goldenReplayResponse(fx, 'GET', `${base}/not-a-build-route`);
      console.log(JSON.stringify({
        total: top.headers['total-results'], items: top.body.length,
        census: census.body, content: full.body.content, ping: ping.status,
        fulltextVersion: full.headers['last-modified-version'],
        groups: groups.body.map((group) => group.id), miss: miss.status,
      }));
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(snapshot), attachment, str(recipe_path)],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["total"] == "1"
    assert result["items"] == 1
    assert result["census"] == {attachment: 17}
    assert result["content"] == "offline golden control body"
    assert result["fulltextVersion"] == "17"
    assert result["ping"] == 200
    assert result["groups"] == [4321]
    assert result["miss"] == 404


def test_replay_rejects_tampered_or_incomplete_snapshot(tmp_path):
    _, snapshot, attachment, _, _, recipe_path = exported_snapshot(tmp_path)
    (snapshot / "fulltext" / f"{attachment}.json").unlink()
    probe = """
      import { loadGoldenExport } from './bench/fixtures/make_index_fixture.mjs';
      try { loadGoldenExport(process.argv[1], { recipePath: process.argv[2] }); process.exit(0); }
      catch (error) { console.error(error.message); process.exit(7); }
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(snapshot), str(recipe_path)],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )
    assert done.returncode == 7
    assert "missing fulltext" in done.stderr


@pytest.mark.parametrize("relative", ["manifest.json", "items.json", "fulltext-body"])
def test_replay_rejects_symlinked_manifest_items_and_fulltext(tmp_path, relative):
    _, snapshot, attachment, _, _, recipe_path = exported_snapshot(tmp_path)
    path = (snapshot / "fulltext" / f"{attachment}.json"
            if relative == "fulltext-body" else snapshot / relative)
    outside = tmp_path / f"outside-{relative.replace('/', '-')}.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)

    done = run_loader(snapshot, recipe_path)
    assert done.returncode == 7
    assert "real file" in done.stderr


def test_replay_rejects_a_snapshot_from_another_recipe(tmp_path):
    recipe, snapshot, _, _, _, _ = exported_snapshot(tmp_path)
    recipe[0]["title"] = "A later recipe title"
    changed = tmp_path / "changed-recipe.json"
    changed.write_text(json.dumps(recipe), encoding="utf-8")
    probe = """
      import { loadGoldenExport } from './bench/fixtures/make_index_fixture.mjs';
      try { loadGoldenExport(process.argv[1], { recipePath: process.argv[2] }); process.exit(0); }
      catch (error) { console.error(error.message); process.exit(7); }
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(snapshot), str(changed)],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )
    assert done.returncode == 7
    assert "does not match" in done.stderr


def export_again(recipe, zotero, cache, destination):
    return gf.export_snapshot(
        recipe, zotero, collection_key="COLLECT1", destination=destination,
        library={"type": "group", "id": 4321}, zotero_client_version="10.0.0-test",
        pdf_max_pages=100, text_max_length=500000, index_max_chars=40000,
        cache_dir=cache,
    )


def run_loader(snapshot, recipe_path):
    probe = """
      import { loadGoldenExport } from './bench/fixtures/make_index_fixture.mjs';
      try { loadGoldenExport(process.argv[1], { recipePath: process.argv[2] }); }
      catch (error) { console.error(error.message); process.exit(7); }
    """
    return subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(snapshot), str(recipe_path)],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )


def test_export_rehashes_source_after_capture_and_preserves_previous_snapshot(tmp_path):
    recipe, snapshot, _, zotero, cache, _ = exported_snapshot(tmp_path)
    old = (snapshot / "manifest.json").read_bytes()
    (cache / "invented-1900-control.pdf").write_bytes(b"different source bytes")

    with pytest.raises(gf.GoldenFixtureError, match="sha256 mismatch"):
        export_again(recipe, zotero, cache, snapshot)
    assert (snapshot / "manifest.json").read_bytes() == old


def test_export_refuses_item_or_fulltext_mutation_during_capture(tmp_path):
    recipe, snapshot, _, zotero, cache, _ = exported_snapshot(tmp_path)
    original = zotero.fulltext_since
    calls = 0

    def unstable_census(since=0):
        nonlocal calls
        calls += 1
        census = original(since)
        if calls >= 2:
            return {key: version + 1 for key, version in census.items()}
        return census

    zotero.fulltext_since = unstable_census
    with pytest.raises(gf.GoldenFixtureError, match="fulltext changed"):
        export_again(recipe, zotero, cache, snapshot)


def test_export_requires_one_item_sequence_and_matching_fulltext_body_version(tmp_path):
    recipe, snapshot, _, zotero, cache, _ = exported_snapshot(tmp_path)
    original_list = zotero.list_top_items
    calls = 0

    def moving_items():
        nonlocal calls
        calls += 1
        rows = original_list()
        # Export's forced refresh performs one opening read before the snapshot's
        # own opening/closing pair; mutate on the latter's closing read.
        if calls == 3:
            zotero.library_version += 1
        return rows

    zotero.list_top_items = moving_items
    with pytest.raises(gf.GoldenFixtureError, match="items changed"):
        export_again(recipe, zotero, cache, snapshot)

    zotero.list_top_items = original_list
    original_fulltext = zotero.get_fulltext

    def mismatched_body_version(key):
        body = original_fulltext(key)
        zotero.last_fulltext_version = body["version"] + 1
        return body

    zotero.get_fulltext = mismatched_body_version
    with pytest.raises(gf.GoldenFixtureError, match="body version"):
        export_again(recipe, zotero, cache, snapshot)


def test_export_rereads_version_zero_fulltext_and_refuses_a_changed_body(tmp_path):
    recipe, snapshot, attachment, zotero, cache, _ = exported_snapshot(tmp_path)
    zotero.fulltexts[attachment]["version"] = 0
    original = zotero.get_fulltext
    calls = 0

    def moving_body(key):
        nonlocal calls
        calls += 1
        body = copy.deepcopy(original(key))
        if calls == 2:
            body["content"] += " changed"
        return body

    zotero.get_fulltext = moving_body
    with pytest.raises(gf.GoldenFixtureError, match="version-zero fulltext changed"):
        export_again(recipe, zotero, cache, snapshot)


def test_export_rereads_all_zero_version_bodies_after_the_complete_first_pass(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    recipe = recipe_for(payload)
    second = copy.deepcopy(recipe[0])
    second.update({"id": "invented-1901-control", "title": "Second control", "year": 1901})
    recipe.append(second)
    cache = tmp_path / "cache"
    cache.mkdir()
    for doc in recipe:
        (cache / f"{doc['id']}.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1", library_type="group")
    attachments = [
        key for key, item in zotero.items.items()
        if item["data"]["itemType"] == "attachment"
    ]
    for index, key in enumerate(attachments):
        zotero.fulltexts[key] = {
            "content": f"body {index}", "indexedPages": 1, "totalPages": 1, "version": 0,
        }
    original = zotero.get_fulltext
    first_reads = set()

    def mutate_earlier_body_on_later_first_read(key):
        if key not in first_reads:
            first_reads.add(key)
            if key == attachments[1]:
                zotero.fulltexts[attachments[0]]["content"] = "mutated after its first read"
        return copy.deepcopy(original(key))

    zotero.get_fulltext = mutate_earlier_body_on_later_first_read
    with pytest.raises(gf.GoldenFixtureError, match="version-zero fulltext changed"):
        export_again(recipe, zotero, cache, tmp_path / "snapshot-two")


def test_export_refuses_extra_child_empty_content_and_invalid_pages(tmp_path):
    recipe, snapshot, attachment, zotero, cache, _ = exported_snapshot(tmp_path)
    parent = next(key for key, item in zotero.items.items() if item["data"]["itemType"] == "document")
    zotero.items["EXTRA001"] = {"key": "EXTRA001", "version": zotero.library_version, "data": {
        "key": "EXTRA001", "version": zotero.library_version, "itemType": "note", "parentItem": parent,
    }}
    with pytest.raises(gf.GoldenFixtureError, match="extra child"):
        export_again(recipe, zotero, cache, snapshot)
    zotero.items.pop("EXTRA001")

    for body, message in [
        ({"content": "   ", "indexedPages": 1, "totalPages": 1, "version": 17}, "malformed"),
        ({"content": "body", "indexedPages": -1, "totalPages": 1, "version": 17}, "relation"),
        ({"content": "body", "indexedPages": 2, "totalPages": 1, "version": 17}, "relation"),
    ]:
        zotero.fulltexts[attachment] = body
        with pytest.raises(gf.GoldenFixtureError, match=message):
            export_again(recipe, zotero, cache, snapshot)


#: A "source_attestation" mutation case (a stale sha256 forged into an attachment's
#: `extra` field) lived here and was dropped 2026-09-04: real Zotero rejects `extra`
#: on attachment items outright, so no export ever carries one to tamper with any
#: more, and there is nothing left for the loader to catch on this axis (ticket 0641).
@pytest.mark.parametrize("mutation, message", [
    ("recipe_id", "not present in the source recipe"),
    ("parent_marker", "expected only managed marker"),
    ("attachment_marker", "expected only managed marker"),
    ("duplicate_parent_marker", "expected only managed marker"),
    ("parent_cross_role_marker", "expected only managed marker"),
    ("attachment_cross_role_marker", "expected only managed marker"),
    ("metadata", "title does not match"),
    ("orphan_item", "not consumed"),
    ("empty_content", "malformed fulltext"),
    ("bad_pages", "invalid indexedPages/totalPages"),
])
def test_loader_rejects_binding_and_fulltext_mutants(tmp_path, mutation, message):
    _, snapshot, attachment, _, _, recipe_path = exported_snapshot(tmp_path)
    manifest_path = snapshot / "manifest.json"
    items_path = snapshot / "items.json"
    fulltext_path = snapshot / "fulltext" / f"{attachment}.json"
    manifest = json.loads(manifest_path.read_text())
    items = json.loads(items_path.read_text())
    parent = next(item for item in items if item["data"]["itemType"] == "document")
    child = next(item for item in items if item["data"]["itemType"] == "attachment")
    if mutation == "recipe_id":
        manifest["attachments"][0]["recipe_id"] = "different-recipe-id"
    elif mutation == "parent_marker":
        parent["data"]["tags"].append({"tag": "zoteus-golden-source:wrong"})
    elif mutation == "attachment_marker":
        child["data"]["tags"].append({"tag": "zoteus-golden-attachment:wrong"})
    elif mutation == "duplicate_parent_marker":
        parent["data"]["tags"].append(copy.deepcopy(parent["data"]["tags"][0]))
    elif mutation == "parent_cross_role_marker":
        parent["data"]["tags"].append({"tag": "zoteus-golden-attachment:invented-1900-control"})
    elif mutation == "attachment_cross_role_marker":
        child["data"]["tags"].append({"tag": "zoteus-golden-source:invented-1900-control"})
    elif mutation == "metadata":
        parent["data"]["title"] = "tampered"
    elif mutation == "orphan_item":
        items.append({"key": "ORPHAN01", "data": {"key": "ORPHAN01", "itemType": "note"}})
    elif mutation == "empty_content":
        body = json.loads(fulltext_path.read_text())
        body["content"] = ""
        fulltext_path.write_text(json.dumps(body), encoding="utf-8")
    elif mutation == "bad_pages":
        body = json.loads(fulltext_path.read_text())
        body["indexedPages"] = body["totalPages"] + 1
        fulltext_path.write_text(json.dumps(body), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    items_path.write_text(json.dumps(items), encoding="utf-8")

    done = run_loader(snapshot, recipe_path)
    assert done.returncode == 7
    assert message in done.stderr


@pytest.mark.parametrize("duplicate", ["parent", "attachment"])
def test_loader_requires_unique_parent_and_attachment_keys(tmp_path, duplicate):
    recipe, snapshot, _, _, _, recipe_path = exported_snapshot(tmp_path)
    second = copy.deepcopy(recipe[0])
    second.update({"id": "invented-1901-control", "title": "Second invented control", "year": 1901})
    recipe.append(second)
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    manifest_path = snapshot / "manifest.json"
    items_path = snapshot / "items.json"
    manifest = json.loads(manifest_path.read_text())
    items = json.loads(items_path.read_text())
    row = copy.deepcopy(manifest["attachments"][0])
    row["recipe_id"] = second["id"]
    if duplicate == "attachment":
        parent = copy.deepcopy(next(item for item in items if item["data"]["itemType"] == "document"))
        parent["key"] = parent["data"]["key"] = "SECOND01"
        parent["data"].update({
            "title": second["title"], "date": "1901",
            "extra": f"ticket-0029 recipe id: {second['id']}",
            "tags": [{"tag": f"zoteus-golden-source:{second['id']}"}],
        })
        items.append(parent)
        row["parent_key"] = "SECOND01"
    manifest["attachments"].append(row)
    manifest["recipe_sha256"] = gf.recipe_digest(recipe)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    items_path.write_text(json.dumps(items), encoding="utf-8")

    done = run_loader(snapshot, recipe_path)
    assert done.returncode == 7
    assert f"duplicate or empty {duplicate} key" in done.stderr


def test_offline_environment_is_a_reviewed_allowlist_and_scrubs_unknown_secrets():
    probe = """
      import { offlineBuildEnvironment } from './bench/fixtures/make_index_fixture.mjs';
      console.log(JSON.stringify(offlineBuildEnvironment({
        PATH: '/bin', CUDA_VISIBLE_DEVICES: '2', ZOTERO_API_KEY: 'library-secret',
        ZOTEUS_OAUTH_PASSCODE: 'oauth-secret', OPENAI_API_KEY: 'provider-secret',
        GEMINI_API_KEY: 'provider-secret-2', HF_TOKEN: 'model-host-secret',
        CUSTOM_LOADER_PATH: '/models', PRIVATE_CORPUS_TOKEN: 'unknown-secret'
      })));
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe], cwd=REPO,
        text=True, capture_output=True, timeout=30, check=True,
    )
    env = json.loads(done.stdout)
    assert env["PATH"] == "/bin"
    assert env["CUDA_VISIBLE_DEVICES"] == "2"
    assert env["ZOTEUS_UPDATE_CHECK"] == "false"
    assert env["ZOTEUS_OAUTH_ENABLED"] == "false"
    assert not ({
        "ZOTERO_API_KEY", "ZOTEUS_OAUTH_PASSCODE", "OPENAI_API_KEY", "GEMINI_API_KEY", "HF_TOKEN",
        "CUSTOM_LOADER_PATH", "PRIVATE_CORPUS_TOKEN",
    } & env.keys())


@pytest.mark.parametrize("provider", ["local", "openai", "gemini"])
def test_replay_cli_rejects_every_nonoffline_embedding_provider_before_starting(provider):
    done = subprocess.run([
        "node", "bench/fixtures/make_index_fixture.mjs", "--replay-export", "unused",
        "--recipe", "unused", "--server", "unused", "--data-dir", "unused",
        "--embeddings", provider,
    ], cwd=REPO, text=True, capture_output=True, timeout=30)
    assert done.returncode == 2
    assert "must be off" in done.stderr


def test_fresh_build_directory_rejects_nonempty_broad_and_symlink_paths(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "search-index.sqlite").write_text("user index", encoding="utf-8")
    alias = tmp_path / "alias"
    alias.symlink_to(empty, target_is_directory=True)
    probe = """
      import { requireFreshBuildDirectory } from './bench/fixtures/make_index_fixture.mjs';
      for (const value of process.argv.slice(1)) {
        try { console.log(`OK:${requireFreshBuildDirectory(value)}`); }
        catch (error) { console.log(`NO:${error.message}`); }
      }
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(empty), str(occupied), "/", str(alias)],
        cwd=REPO, text=True, capture_output=True, timeout=30, check=True,
    )
    lines = done.stdout.splitlines()
    assert lines[0].startswith("OK:")
    assert "not empty" in lines[1]
    assert "broad" in lines[2]
    assert "symlink" in lines[3]


def test_claimed_build_directory_gets_exclusive_recipe_bound_sentinel(tmp_path):
    target = tmp_path / "dedicated"
    target.mkdir()
    probe = """
      import { claimFreshBuildDirectory } from './bench/fixtures/make_index_fixture.mjs';
      const fixture = { root: '/fixture/export', manifest: { recipe_sha256: 'a'.repeat(64) } };
      console.log(claimFreshBuildDirectory(process.argv[1], fixture));
    """
    subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(target)], cwd=REPO,
        text=True, capture_output=True, timeout=30, check=True,
    )
    sentinel = json.loads((target / ".zoteus-golden-build.json").read_text())
    assert sentinel == {
        "schema": "zoteus-golden-build/v1",
        "recipe_sha256": "a" * 64,
        "export_root": "/fixture/export",
    }
    second = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(target)], cwd=REPO,
        text=True, capture_output=True, timeout=30,
    )
    assert second.returncode != 0
    assert "not empty" in second.stderr


def test_build_result_requires_done_counts_index_and_complete_successful_routes(tmp_path):
    _, snapshot, attachment, _, _, recipe_path = exported_snapshot(tmp_path)
    data_dir = tmp_path / "build"
    data_dir.mkdir()
    (data_dir / "search-index.sqlite").write_bytes(b"sqlite-control")
    probe = """
      import { loadGoldenExport, validateGoldenBuildResult } from './bench/fixtures/make_index_fixture.mjs';
      const fx = loadGoldenExport(process.argv[1], { recipePath: process.argv[2] });
      const data = process.argv[3]; const attachment = process.argv[4];
      const prefix = '/api/groups/4321';
      const good = { status: { state: 'done', itemsFetched: 1, passages: 2, fulltextPassages: 1 },
                     files: { 'search-index.sqlite': 14 } };
      const routes = [
        '/api/users/0/items?limit=1', '/api/users/0/groups?limit=100', `${prefix}/items/top?limit=100`,
        `${prefix}/fulltext?since=0`, `${prefix}/items/${attachment}/fulltext`,
      ].map((url) => ({ method: 'GET', url, status: 200 }));
      const cases = [
        [good, routes],
        [{ ...good, status: { ...good.status, state: 'error' } }, routes],
        [{ ...good, status: { ...good.status, state: 'done', status: 'error' } }, routes],
        [{ ...good, status: { ...good.status, state: 'error', status: 'done' } }, routes],
        [{ ...good, status: { ...good.status, passages: 0 } }, routes],
        [good, routes.slice(0, -1)],
        [good, routes.map((row, i) => i === 3 ? { ...row, status: 404 } : row)],
      ];
      for (const [result, requests] of cases) {
        try { validateGoldenBuildResult(fx, result, requests, data); console.log('OK'); }
        catch (error) { console.log(`NO:${error.message}`); }
      }
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(snapshot), str(recipe_path),
         str(data_dir), attachment],
        cwd=REPO, text=True, capture_output=True, timeout=30, check=True,
    )
    lines = done.stdout.splitlines()
    assert lines[0] == "OK"
    assert all(line.startswith("NO:") for line in lines[1:])


def test_run_golden_build_wires_offline_env_and_refuses_local_before_replay_or_spawn(tmp_path):
    _, snapshot, attachment, _, _, recipe_path = exported_snapshot(tmp_path)
    data_dir = tmp_path / "wired-build"
    data_dir.mkdir()
    probe = r"""
      import { EventEmitter } from 'node:events';
      import { mkdirSync, writeFileSync } from 'node:fs';
      import { join } from 'node:path';
      import { loadGoldenExport, runGoldenBuild } from './bench/fixtures/make_index_fixture.mjs';
      const fx = loadGoldenExport(process.argv[1], { recipePath: process.argv[2] });
      const dataDir = process.argv[3]; const attachment = process.argv[4];
      const prefix = '/api/groups/4321';
      const requests = [
        '/api/users/0/items?limit=1', '/api/users/0/groups?limit=100', `${prefix}/items/top?limit=100`,
        `${prefix}/fulltext?since=0`, `${prefix}/items/${attachment}/fulltext`,
      ].map((url) => ({ method: 'GET', url, status: 200 }));
      let observed;
      const spawnImpl = (python, args, options) => {
        observed = { python, args, env: options.env };
        const resultPath = args[args.indexOf('--result-json') + 1];
        const target = args[args.indexOf('--data-dir') + 1];
        writeFileSync(join(target, 'search-index.sqlite'), 'sqlite-control');
        writeFileSync(resultPath, JSON.stringify({
          status: { state: 'done', itemsFetched: 1, passages: 2, fulltextPassages: 1 },
          files: { 'search-index.sqlite': 14 },
        }));
        const child = new EventEmitter();
        queueMicrotask(() => child.emit('exit', 0, null));
        return child;
      };
      process.env.PRIVATE_CORPUS_TOKEN = 'do-not-forward';
      const result = await runGoldenBuild(fx, {
        server: '/real/dist/index.js', dataDir, embeddings: 'off', python: '/python-control',
        spawnImpl, startReplay: async () => ({ port: 23199, requests, close: async () => {} }),
      });
      let started = false; let spawned = false;
      try {
        await runGoldenBuild(fx, {
          server: 'unused', dataDir: process.argv[5], embeddings: 'local',
          startReplay: async () => { started = true; throw new Error('must not start'); },
          spawnImpl: () => { spawned = true; throw new Error('must not spawn'); },
        });
      } catch (error) {
        console.log(JSON.stringify({ observed, result, rejection: error.message, started, spawned }));
      }
    """
    blocked_dir = tmp_path / "blocked-build"
    blocked_dir.mkdir()
    done = subprocess.run([
        "node", "--input-type=module", "--eval", probe, str(snapshot), str(recipe_path),
        str(data_dir), attachment, str(blocked_dir),
    ], cwd=REPO, text=True, capture_output=True, timeout=30,
       env={**os.environ, "PRIVATE_CORPUS_TOKEN": "parent-secret"})
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["observed"]["python"] == "/python-control"
    assert result["observed"]["env"]["ZOTERO_LOCAL_PORT"] == "23199"
    assert result["observed"]["env"]["ZOTEUS_LOCAL"] == "on"
    assert "PRIVATE_CORPUS_TOKEN" not in result["observed"]["env"]
    args = result["observed"]["args"]
    assert args[args.index("--embeddings") + 1] == "off"
    assert result["result"]["exit_code"] == 0
    assert "must be off" in result["rejection"]
    assert not result["started"]
    assert not result["spawned"]


@pytest.mark.skipif(
    not os.environ.get("ZOTEUS_GOLDEN_REAL_SERVER"),
    reason="set ZOTEUS_GOLDEN_REAL_SERVER to an already-built Zoteus dist/index.js",
)
def test_real_zoteus_build_runs_only_through_the_captured_api(tmp_path):
    _, snapshot, _, _, _, recipe_path = exported_snapshot(tmp_path)
    data_dir = tmp_path / "real-build"
    data_dir.mkdir()
    report = tmp_path / "real-build.json"
    done = subprocess.run(
        [
            "node", "bench/fixtures/make_index_fixture.mjs", "--replay-export", str(snapshot),
            "--recipe", str(recipe_path), "--server", os.environ["ZOTEUS_GOLDEN_REAL_SERVER"],
            "--data-dir", str(data_dir), "--embeddings", "off", "--report", str(report),
            "--max-wait", "30",
        ],
        cwd=REPO, text=True, capture_output=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    result = json.loads(report.read_text())
    assert result["build"]["status"]["state"] == "done"
    assert all(request["status"] == 200 for request in result["replay_requests"])


@pytest.mark.parametrize("final, max_wait, error", [
    ({"state": "error"}, 1, RuntimeError),
    ({"state": "running"}, 0, TimeoutError),
    ({"state": "error", "status": "done"}, 1, RuntimeError),
    ({"state": "done", "status": "error"}, 1, RuntimeError),
])
def test_run_build_fails_closed_and_reaps_server(tmp_path, monkeypatch, final, max_wait, error):
    rb = load_run_build()
    processes = []

    class Process:
        pid = os.getpid()
        terminated = False
        waited = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            self.waited = True
            return 0

        def kill(self):
            raise AssertionError("a cooperative child should not need kill")

    class FakeServer:
        def __init__(self, *_):
            self.p = Process()
            processes.append(self.p)

        def handshake(self):
            return {}

        def call(self, _method, params):
            return final if params["arguments"]["action"] == "status" else {"state": "running"}

    monkeypatch.setattr(rb, "Server", FakeServer)
    monkeypatch.setattr(rb, "vmhwm_kb", lambda _pid: 1)
    monkeypatch.setattr(rb.time, "sleep", lambda _seconds: None)
    args = SimpleNamespace(server="fake.mjs", max_wait=max_wait, build=True, poll=0,
                           data_dir=str(tmp_path), result_json="")
    with pytest.raises(error):
        rb.drive_server(args, {})
    assert processes[0].terminated
    assert processes[0].waited


def test_run_build_kills_an_uncooperative_child_even_when_handshake_fails(tmp_path, monkeypatch):
    rb = load_run_build()

    class Process:
        pid = os.getpid()
        waits = 0
        killed = False

        def terminate(self):
            pass

        def wait(self, timeout):
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("fake", timeout)
            return 0

        def kill(self):
            self.killed = True

    process = Process()

    class BrokenServer:
        def __init__(self, *_):
            self.p = process

        def handshake(self):
            raise RuntimeError("handshake failed")

    monkeypatch.setattr(rb, "Server", BrokenServer)
    args = SimpleNamespace(server="fake.mjs", max_wait=1, build=True, poll=0,
                           data_dir=str(tmp_path), result_json="")
    with pytest.raises(RuntimeError, match="handshake failed"):
        rb.drive_server(args, {})
    assert process.killed
    assert process.waits == 2


@pytest.mark.parametrize("build, status", [
    (True, {"state": "done", "itemsFetched": 1}),
    (False, {"state": "error", "message": "status-only control"}),
])
def test_run_build_positive_done_and_nonbuild_controls(tmp_path, monkeypatch, build, status):
    rb = load_run_build()

    class Process:
        pid = os.getpid()
        terminated = False
        waited = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            self.waited = True
            return 0

        def kill(self):
            raise AssertionError("positive control child should terminate cooperatively")

    process = Process()

    class FakeServer:
        def __init__(self, *_):
            self.p = process

        def handshake(self):
            return {}

        def call(self, _method, params):
            if params["arguments"]["action"] == "build":
                return {"state": "running"}
            return status

    monkeypatch.setattr(rb, "Server", FakeServer)
    monkeypatch.setattr(rb, "vmhwm_kb", lambda _pid: 7)
    monkeypatch.setattr(rb.time, "sleep", lambda _seconds: None)
    result_path = tmp_path / "result.json"
    args = SimpleNamespace(server="fake.mjs", max_wait=1, build=build, poll=0,
                           data_dir=str(tmp_path), result_json=str(result_path))
    rb.drive_server(args, {})
    assert json.loads(result_path.read_text())["peak_rss_kb"] == 7
    assert process.terminated and process.waited
