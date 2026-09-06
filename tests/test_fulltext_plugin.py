"""The full-text control plugin reindexes under the stock limits by default and
reports what it did.

Ticket 0721, from ticket 0632's real run (2026-09-06): the plugin passed
``complete: true`` to ``Zotero.FullText.indexItems`` unconditionally, so the
export's recorded ``fulltext.pdfMaxPages`` / ``textMaxLength`` never bounded the
captured text and nothing in the harness could tell.  The plugin now takes
``complete`` on the request (default false = stock limits), echoes the mode it
queued, and its status carries the plugin version, the mode of the last
reindex and both preferences read live.  No Zotero client runs here: the
bootstrap is loaded into a node vm against a mock ``Zotero`` global that records
the ``indexItems`` options it was handed, which is the one fact the defect hid.
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "bench" / "zotero-fulltext-plugin"

DRIVER = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const [bootstrapPath, body] = process.argv.slice(1);
const calls = [];
const imports = [];
const prefs = { 'fulltext.pdfMaxPages': 100, 'fulltext.textMaxLength': 500000 };
const items = { ATTACH01: { id: 11, isFileAttachment: () => true }, PARENT01: { id: 12, isFileAttachment: () => false } };
const Zotero = {
  debug() {},
  initializationPromise: Promise.resolve(),
  Server: { Endpoints: {} },
  Libraries: { getAll: () => [{ libraryID: 1, libraryType: 'group' }] },
  Items: { getByLibraryAndKeyAsync: async (_lib, key) => items[key] ?? null },
  FullText: {
    indexItems: async (ids, options) => { calls.push({ ids, options }); },
    getIndexedState: async () => 3,
    getIndexStats: async () => ({ indexed: 1, partial: 0, unindexed: 0, words: 1 }),
  },
  DB: { rowQueryAsync: async () => ({ indexedPages: 3, totalPages: 3, indexedChars: null, totalChars: null, version: 0 }) },
  Prefs: { get: (name) => prefs[name] },
  File: { pathToFile: (p) => ({ path: p }) },
  Translate: { Import: class {
    setLocation(file) { this.file = file; }
    async getTranslators() { return this.file.path.endsWith('.ris') ? [{ label: 'RIS' }] : []; }
    setTranslator(t) { this.translator = t; }
    async translate(options) {
      imports.push({ path: this.file.path, options });
      return [{ key: 'NEWITEM1', itemType: 'book', getField: () => 'Imported', isNote: () => false, getAttachments: () => [77] }];
    }
  } },
};
Zotero.Libraries.userLibraryID = 1;
const syncCalls = [];
Zotero.Libraries.getAll = () => [
  { libraryID: 1, libraryType: 'user', libraryVersion: 25, lastSync: 1, storageVersion: 2 },
  { libraryID: 3, libraryType: 'group', groupID: 6659303, name: 'Fixture', libraryVersion: 140, lastSync: 9, storageVersion: 0 },
];
Zotero.DB.valueQueryAsync = async (_sql, libraryID) => (libraryID === 3 ? 232 : 0);
const keysSet = [];
Zotero.Sync = { Runner: {
  enabled: true, syncInProgress: false, lastSyncStatus: 'idle',
  set apiKey(value) { keysSet.push(value); },
  sync: async (options) => { syncCalls.push(options); },
} };
Zotero.Items.get = (id) => ({ key: 'ATT' + id, attachmentLinkMode: 2, attachmentContentType: 'application/pdf', attachmentPath: 'attachments/x.pdf', fileExists: async () => true });
const context = vm.createContext({ Zotero, console });
vm.runInContext(fs.readFileSync(bootstrapPath, 'utf8'), context, { filename: 'bootstrap.js' });
(async () => {
  await context.startup({ version: '9.9.9-test' });
  const Reindex = context.Zotero.Server.Endpoints['/search-works/fulltext/reindex'];
  const Status = context.Zotero.Server.Endpoints['/search-works/fulltext/status'];
  const status0 = await new Status().init({ searchParams: new URLSearchParams('') });
  const reindex = await new Reindex().init({ data: JSON.parse(body) });
  prefs['fulltext.pdfMaxPages'] = 7;  // changed after startup: status must read live
  const status1 = await new Status().init({ searchParams: new URLSearchParams('keys=ATTACH01') });
  const Import = context.Zotero.Server.Endpoints['/search-works/fulltext/import'];
  const imported = await new Import().init({ data: { path: '/tmp/menagerie.ris' } });
  const relative = await new Import().init({ data: { path: 'menagerie.ris' } });
  const unmatched = await new Import().init({ data: { path: '/tmp/menagerie.xyz' } });
  const Sync = context.Zotero.Server.Endpoints['/search-works/fulltext/sync'];
  const syncBefore = await new Sync().init({ method: 'GET' });
  const syncStart = await new Sync().init({ method: 'POST', data: { groupID: 6659303 } });
  const syncNoLibrary = await new Sync().init({ method: 'POST', data: { groupID: 1 } });
  const syncNoBody = await new Sync().init({ method: 'POST', data: {} });
  Zotero.Sync.Runner.enabled = false;
  const syncDisabled = await new Sync().init({ method: 'POST', data: { libraryID: 3 } });
  const syncWithKey = await new Sync().init({ method: 'POST', data: { libraryID: 3, apiKey: 'sekrit' } });
  await new Promise((resolve) => setTimeout(resolve, 5));
  const syncAfterKey = await new Sync().init({ method: 'GET' });
  console.log(JSON.stringify({
    sync: { before: JSON.parse(syncBefore[2]), start: [syncStart[0], JSON.parse(syncStart[2])],
            noLibrary: syncNoLibrary[0], noBody: syncNoBody[0], disabled: syncDisabled[0], calls: syncCalls,
            withKey: [syncWithKey[0], syncWithKey[2]], afterKey: syncAfterKey[2], keysSet },
    before: JSON.parse(status0[2]), reindex: [reindex[0], JSON.parse(reindex[2])],
    after: JSON.parse(status1[2]), calls, imports,
    imported: [imported[0], JSON.parse(imported[2])], relative: relative[0], unmatched: unmatched[0],
  }));
})().catch((error) => { console.error(error.stack); process.exit(3); });
"""


def drive(body: dict) -> dict:
    done = subprocess.run(
        ["node", "--eval", DRIVER, "--", str(PLUGIN / "bootstrap.js"), json.dumps(body)],
        cwd=REPO, text=True, capture_output=True, timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.integration
def test_reindex_applies_the_stock_limits_unless_asked_to_ignore_them():
    stock = drive({"keys": ["ATTACH01"]})
    assert stock["calls"] == [{"ids": [11], "options": {"complete": False, "ignoreErrors": True}}]
    assert stock["reindex"] == [202, {"queued": [{"key": "ATTACH01", "libraryID": 1}], "missing": [],
                                      "notAttachments": [], "mode": "stock", "complete": False}]
    uncapped = drive({"keys": ["ATTACH01"], "complete": True})
    assert uncapped["calls"][0]["options"] == {"complete": True, "ignoreErrors": True}
    assert uncapped["reindex"][1]["mode"] == "uncapped"
    explicit_false = drive({"keys": ["ATTACH01"], "complete": False})
    assert explicit_false["calls"][0]["options"]["complete"] is False


@pytest.mark.integration
def test_reindex_refuses_a_non_boolean_complete_flag():
    result = drive({"keys": ["ATTACH01"], "complete": "yes"})
    assert result["reindex"][0] == 400 and result["calls"] == []


@pytest.mark.integration
def test_status_reports_version_last_mode_and_live_preferences():
    result = drive({"keys": ["ATTACH01"], "complete": True})
    before, after = result["before"], result["after"]
    assert before["version"] == "9.9.9-test" and before["lastReindexMode"] is None
    assert before["codeVersion"] == "0.4.0", "the code reports its own version beside the registered one"
    assert before["prefs"] == {"pdfMaxPages": 100, "textMaxLength": 500000}
    assert after["lastReindexMode"] == "uncapped"
    # The preference moved between the two reads; a cached value would still say 100.
    assert after["prefs"] == {"pdfMaxPages": 7, "textMaxLength": 500000}
    assert after["items"][0]["key"] == "ATTACH01" and after["items"][0]["state"] == "indexed"


def test_manifest_version_matches_the_documented_contract():
    manifest = json.loads((PLUGIN / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.4.0"
    source = (PLUGIN / "bootstrap.js").read_text(encoding="utf-8")
    assert "const CODE_VERSION = '0.4.0';" in source, "the code version the status reports equals the manifest's"
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    assert '"complete"' in readme and "lastReindexMode" in readme and "stock" in readme
    source = (PLUGIN / "bootstrap.js").read_text(encoding="utf-8")
    assert "indexItems(ids, { complete: true" not in source, "the mode is the caller's, never a literal"
    assert "indexItems(ids, { complete, ignoreErrors: true })" in source


@pytest.mark.integration
def test_import_targets_the_user_library_links_files_and_reports_what_zotero_made():
    """Ticket 0721, the RIS package check: the endpoint imports an absolute path through
    Zotero's own translators into the user library only, with files linked (not copied),
    and reports item types and whether each linked file exists. A relative path and a
    file no translator matches are refused."""
    out = drive({"keys": ["ATTACH01"]})
    status, body = out["imported"]
    assert status == 200 and body["translator"] == "RIS" and body["libraryID"] == 1
    assert body["items"][0]["itemType"] == "book"
    assert body["items"][0]["attachments"][0] == {
        "key": "ATT77", "linkMode": 2, "contentType": "application/pdf",
        "path": "attachments/x.pdf", "exists": True,
    }
    imports = out["imports"]
    assert imports == [{"path": "/tmp/menagerie.ris", "options": {"libraryID": 1, "saveAttachments": True, "linkFiles": True}}]
    assert out["relative"] == 400 and out["unmatched"] == 422


@pytest.mark.integration
def test_sync_starts_one_library_through_the_runner_and_reports_where_it_stands():
    """Ticket 0721: a headless client never auto-syncs, so the endpoint asks the
    Sync.Runner for one library by group id and reports per-library version and
    unsynced count; it refuses an unknown library, an empty body, and a profile
    with no sync set up."""
    out = drive({"keys": ["ATTACH01"]})["sync"]
    assert out["before"]["enabled"] is True and out["before"]["inProgress"] is False
    group = [row for row in out["before"]["libraries"] if row["libraryType"] == "group"][0]
    assert group == {"libraryID": 3, "libraryType": "group", "groupID": 6659303, "name": "Fixture",
                     "libraryVersion": 140, "lastSync": 9, "storageVersion": 0, "unsynced": 232}
    assert out["start"] == [202, {"started": True, "libraryID": 3, "groupID": 6659303, "apiKeyOverride": False}]
    assert out["calls"] == [{"background": False, "libraries": [3]}] * 2, "the plain run and the key run both reach the runner"
    assert out["noLibrary"] == 404 and out["noBody"] == 400 and out["disabled"] == 409
    # A key handed in for one run goes through the runner's in-memory setter, is never
    # echoed, and is cleared once the run ends.
    assert out["withKey"][0] == 202 and "sekrit" not in out["withKey"][1] and "sekrit" not in out["afterKey"]
    assert '"apiKeyOverride":true' in out["withKey"][1] and '"apiKeyOverride":false' in out["afterKey"]
    assert out["keysSet"] == ["sekrit", None]
