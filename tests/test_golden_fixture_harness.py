"""The golden corpus can be injected once, exported from Zotero, and replayed offline.

The tests use invented one-item API responses.  They prove the machinery without
pretending those responses are ticket 0029's still-unavailable live export.
"""

import hashlib
import importlib.util
import json
import subprocess
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


class MemoryZotero:
    def __init__(self):
        self.items = {}
        self.fulltexts = {}
        self.writes = []
        self.next_key = 1
        self.library_version = 0

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


def exported_snapshot(tmp_path):
    payload = b"%PDF-1.4\ncontrol\n"
    recipe = recipe_for(payload)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented-1900-control.pdf").write_bytes(payload)
    zotero = MemoryZotero()
    gf.inject(recipe, cache, zotero, collection_key="COLLECT1")
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
    )
    return recipe, dest, attachment, zotero


def test_export_is_raw_complete_atomic_and_bound_to_recipe(tmp_path):
    recipe, dest, attachment, zotero = exported_snapshot(tmp_path)
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
    }]
    assert len(items) == 2
    assert fulltext["content"] == "offline golden control body"
    assert str(tmp_path) not in json.dumps(items)
    linked = next(item["data"] for item in items if item["data"]["itemType"] == "attachment")
    assert linked["path"] == "attachments:invented-1900-control.pdf"
    assert manifest["normalizations"]["linked_file_path"].startswith("absolute API path")

    old = (dest / "manifest.json").read_bytes()
    with pytest.raises(gf.GoldenFixtureError, match="no /fulltext"):
        client = zotero
        client.fulltexts.clear()
        gf.export_snapshot(
            recipe, client, collection_key="COLLECT1", destination=dest,
            library={"type": "group", "id": 4321}, zotero_client_version="10.0.0-test",
            pdf_max_pages=100, text_max_length=500000, index_max_chars=40000,
        )
    assert (dest / "manifest.json").read_bytes() == old


def test_offline_route_replay_has_build_routes_and_fails_closed(tmp_path):
    _, snapshot, attachment, _ = exported_snapshot(tmp_path)
    probe = """
      import { loadGoldenExport, goldenReplayResponse } from './bench/fixtures/make_index_fixture.mjs';
      const fx = loadGoldenExport(process.argv[1]);
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
        groups: groups.body.map((group) => group.id), miss: miss.status,
      }));
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(snapshot), attachment],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["total"] == "1"
    assert result["items"] == 1
    assert result["census"] == {attachment: 17}
    assert result["content"] == "offline golden control body"
    assert result["ping"] == 200
    assert result["groups"] == [4321]
    assert result["miss"] == 404


def test_replay_rejects_tampered_or_incomplete_snapshot(tmp_path):
    _, snapshot, attachment, _ = exported_snapshot(tmp_path)
    (snapshot / "fulltext" / f"{attachment}.json").unlink()
    probe = """
      import { loadGoldenExport } from './bench/fixtures/make_index_fixture.mjs';
      try { loadGoldenExport(process.argv[1]); process.exit(0); }
      catch (error) { console.error(error.message); process.exit(7); }
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe, str(snapshot)],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )
    assert done.returncode == 7
    assert "missing fulltext" in done.stderr


def test_replay_rejects_a_snapshot_from_another_recipe(tmp_path):
    recipe, snapshot, _, _ = exported_snapshot(tmp_path)
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
