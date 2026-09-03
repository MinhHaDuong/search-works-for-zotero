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
            cache_dir=cache,
        )
    assert (dest / "manifest.json").read_bytes() == old


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
        if calls == 2:
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


@pytest.mark.parametrize("mutation, message", [
    ("recipe_id", "not present in the source recipe"),
    ("parent_marker", "expected only managed marker"),
    ("attachment_marker", "expected only managed marker"),
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


def test_offline_environment_scrubs_credentials_but_preserves_runtime_settings():
    probe = """
      import { offlineBuildEnvironment } from './bench/fixtures/make_index_fixture.mjs';
      console.log(JSON.stringify(offlineBuildEnvironment({
        PATH: '/bin', CUDA_VISIBLE_DEVICES: '2', ZOTERO_API_KEY: 'library-secret',
        ZOTEUS_OAUTH_PASSCODE: 'oauth-secret', OPENAI_API_KEY: 'provider-secret',
        GEMINI_API_KEY: 'provider-secret-2', HF_TOKEN: 'model-host-secret',
        CUSTOM_LOADER_PATH: '/models'
      })));
    """
    done = subprocess.run(
        ["node", "--input-type=module", "--eval", probe], cwd=REPO,
        text=True, capture_output=True, timeout=30, check=True,
    )
    env = json.loads(done.stdout)
    assert env["PATH"] == "/bin"
    assert env["CUDA_VISIBLE_DEVICES"] == "2"
    assert env["CUSTOM_LOADER_PATH"] == "/models"
    assert env["ZOTEUS_UPDATE_CHECK"] == "false"
    assert env["ZOTEUS_OAUTH_ENABLED"] == "false"
    assert not ({
        "ZOTERO_API_KEY", "ZOTEUS_OAUTH_PASSCODE", "OPENAI_API_KEY", "GEMINI_API_KEY", "HF_TOKEN",
    } & env.keys())


def test_replay_cli_rejects_network_embedding_providers_before_starting():
    done = subprocess.run(
        [
            "node", "bench/fixtures/make_index_fixture.mjs", "--replay-export", "unused",
            "--recipe", "unused", "--server", "unused", "--data-dir", "unused",
            "--embeddings", "openai",
        ],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )
    assert done.returncode == 2
    assert "off or local" in done.stderr


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
