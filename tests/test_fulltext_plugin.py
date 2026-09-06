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
  console.log(JSON.stringify({
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
    assert before["prefs"] == {"pdfMaxPages": 100, "textMaxLength": 500000}
    assert after["lastReindexMode"] == "uncapped"
    # The preference moved between the two reads; a cached value would still say 100.
    assert after["prefs"] == {"pdfMaxPages": 7, "textMaxLength": 500000}
    assert after["items"][0]["key"] == "ATTACH01" and after["items"][0]["state"] == "indexed"


def test_manifest_version_matches_the_documented_contract():
    manifest = json.loads((PLUGIN / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.3.0"
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
