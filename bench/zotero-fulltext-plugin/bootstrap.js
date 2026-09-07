/*
 * Full-text control: two endpoints on Zotero's local server, for the machine the
 * segmenter experiment runs on. Nothing here leaves the machine: Zotero binds its
 * server to the loopback interface and refuses any Host header that is not
 * localhost, and browser-shaped requests are refused unless they carry the
 * Zotero-Allowed-Request header, both by Zotero's own server code.
 *
 *   POST /search-works/fulltext/reindex   {"keys": ["ABCD1234", ...], "complete": false}
 *     Queues a re-extraction of each named attachment in whichever library holds
 *     it and returns at once. `complete` defaults to false: the stock limits
 *     (fulltext.pdfMaxPages, fulltext.textMaxLength) apply, exactly as Zotero's
 *     own extraction would. `complete: true` asks Zotero to ignore both limits
 *     (fulltext.js: indexPDF gets null for maxPages when allPages is set). The
 *     response echoes the mode it queued, `stock` or `uncapped`.
 *
 *   GET  /search-works/fulltext/status?keys=ABCD1234,EFGH5678
 *     Per key: library, indexing state, indexed and total pages or characters.
 *     Plus the library-wide statistics, whether a reindex this plugin queued is
 *     still running, the plugin version, the mode of the last reindex it queued
 *     (`stock`, `uncapped`, or null before any), and the two extraction
 *     preferences read live from the client. Without keys: all of that, no rows.
 *
 * The ask this stands in for belongs upstream, on Zotero's local API: nothing
 * stock lets a consumer request extraction or see that one is in progress.
 */

const PREFIX = '/search-works/fulltext/';
const STATE_NAMES = ['unavailable', 'unindexed', 'partial', 'indexed', 'queued'];

let running = 0;
let lastError = null;
let lastReindexMode = null;
let pluginVersion = null;
//: The version of this file, kept equal to manifest.json's. The add-on manager hands
//: startup() the version it REGISTERED, which lags a replaced xpi until the profile
//: re-reads the manifest (padme, 2026-09-06: new code ran under a 0.1.1 label).
const CODE_VERSION = '0.5.0';

function reindexMode(complete) {
  return complete ? 'uncapped' : 'stock';
}

function log(msg) {
  Zotero.debug(`fulltext-control: ${msg}`);
}

/**
 * Asynchronous on purpose: after a restart a group library is not loaded until
 * something touches it, and the synchronous getter throws on an unloaded
 * library, which surfaced as a 500 on every call naming a group item.
 */
async function findAttachment(key) {
  for (const library of Zotero.Libraries.getAll()) {
    const item = await Zotero.Items.getByLibraryAndKeyAsync(library.libraryID, key);
    if (item) return { item, library };
  }
  return null;
}

function json(status, body) {
  return [status, 'application/json', JSON.stringify(body)];
}

function Reindex() {}
Reindex.prototype = {
  supportedMethods: ['POST'],
  supportedDataTypes: ['application/json'],
  init: async function ({ data }) {
    const keys = Array.isArray(data?.keys) ? data.keys.filter((k) => typeof k === 'string') : null;
    if (!keys || keys.length === 0) return json(400, { error: 'body must be {"keys": [...], "complete"?: boolean}' });
    if (data.complete !== undefined && typeof data.complete !== 'boolean') {
      return json(400, { error: '"complete" must be a boolean when given' });
    }
    // Stock limits unless asked otherwise: the default arm of the fixture is what
    // Zotero itself would have indexed, and a limits-ignored pass is the exception.
    const complete = data.complete === true;
    const mode = reindexMode(complete);
    const queued = [];
    const missing = [];
    const notAttachments = [];
    const ids = [];
    for (const key of keys) {
      const found = await findAttachment(key);
      if (!found) {
        missing.push(key);
        continue;
      }
      if (!found.item.isFileAttachment()) {
        notAttachments.push(key);
        continue;
      }
      ids.push(found.item.id);
      queued.push({ key, libraryID: found.library.libraryID });
    }
    if (ids.length > 0) {
      running += 1;
      lastReindexMode = mode;
      Zotero.FullText.indexItems(ids, { complete, ignoreErrors: true })
        .catch((e) => {
          lastError = String(e?.message ?? e);
          log(`reindex failed: ${lastError}`);
        })
        .finally(() => {
          running -= 1;
        });
    }
    return json(202, { queued, missing, notAttachments, mode, complete });
  },
};

function Status() {}
Status.prototype = {
  supportedMethods: ['GET'],
  init: async function ({ searchParams }) {
    const raw = searchParams.get('keys') ?? '';
    const keys = raw.split(',').map((k) => k.trim()).filter(Boolean);
    const items = [];
    for (const key of keys) {
      const found = await findAttachment(key);
      if (!found) {
        items.push({ key, error: 'not found' });
        continue;
      }
      const { item, library } = found;
      const state = item.isFileAttachment() ? await Zotero.FullText.getIndexedState(item) : null;
      const row = await Zotero.DB.rowQueryAsync(
        'SELECT indexedPages, totalPages, indexedChars, totalChars, version FROM fulltextItems WHERE itemID=?',
        item.id,
      );
      items.push({
        key,
        libraryID: library.libraryID,
        libraryType: library.libraryType,
        state: state === null ? null : (STATE_NAMES[state] ?? state),
        indexedPages: row?.indexedPages ?? null,
        totalPages: row?.totalPages ?? null,
        indexedChars: row?.indexedChars ?? null,
        totalChars: row?.totalChars ?? null,
        version: row?.version ?? null,
      });
    }
    const stats = await Zotero.FullText.getIndexStats();
    // Read live, never cached: the harness records these beside its export and
    // must see the value the extraction actually ran under.
    const prefs = {
      pdfMaxPages: Zotero.Prefs.get('fulltext.pdfMaxPages'),
      textMaxLength: Zotero.Prefs.get('fulltext.textMaxLength'),
    };
    return json(200, {
      busy: running > 0, running, lastError, stats, items,
      version: pluginVersion, codeVersion: CODE_VERSION, lastReindexMode, prefs,
    });
  },
};

/**
 * Import a bibliographic file (RIS, BibTeX, Zotero RDF) into the USER library of the
 * running profile, as File -> Import would: Zotero's own import translators, file
 * attachments linked rather than copied, so a relative L1 path in a RIS resolves
 * beside the file. A verification aid for the Menagerie's RIS package (ticket 0721):
 * the fixture's group library is never a permitted target, only the user library of a
 * scratch profile, and the response reports what Zotero made of the file -- item
 * types, and whether each linked attachment's file exists.
 *
 *   POST /search-works/fulltext/import   {"path": "/abs/menagerie.ris"}
 */
function Import() {}
Import.prototype = {
  supportedMethods: ['POST'],
  supportedDataTypes: ['application/json'],
  init: async function ({ data }) {
    const path = typeof data?.path === 'string' && data.path.startsWith('/') ? data.path : null;
    if (!path) return json(400, { error: 'body must be {"path": "/absolute/path/to/file"}' });
    const libraryID = Zotero.Libraries.userLibraryID;
    const translation = new Zotero.Translate.Import();
    translation.setLocation(Zotero.File.pathToFile(path));
    const translators = await translation.getTranslators();
    if (!translators || translators.length === 0) return json(422, { error: 'no import translator matched the file' });
    translation.setTranslator(translators[0]);
    let imported;
    try {
      imported = await translation.translate({ libraryID, saveAttachments: true, linkFiles: true });
    } catch (e) {
      return json(500, { error: String(e?.message ?? e) });
    }
    const items = [];
    for (const item of imported) {
      const attachments = [];
      for (const id of item.getAttachments ? item.getAttachments() : []) {
        const a = Zotero.Items.get(id);
        attachments.push({
          key: a.key, linkMode: a.attachmentLinkMode, contentType: a.attachmentContentType,
          path: a.attachmentPath, exists: await a.fileExists(),
        });
      }
      items.push({
        key: item.key, itemType: item.itemType, title: item.getField('title'),
        isNote: item.isNote(), attachments,
      });
    }
    return json(200, { translator: translators[0].label, libraryID, itemCount: items.length, items });
  },
};

/**
 * Sync one library with zotero.org, as the toolbar button would, and report where
 * the sync stands. A headless client has no pane, and the pane is what runs the
 * automatic sync at startup, so items the harness writes headless stay local until
 * something asks (padme, 2026-09-06: 103 parents at local version 484 while the
 * server still held 17 at version 140). Data and, when storage sync is enabled,
 * files, through Zotero's own Sync.Runner; nothing here writes an item.
 *
 *   POST /search-works/fulltext/sync   {"libraryID": 3, "apiKey": "..."} or {"groupID": 6659303, "apiKey": "..."}
 *     Starts Zotero.Sync.Runner.sync for that library and returns at once. The key is
 *     required on every call, whether or not the profile already has sync set up.
 *   GET  /search-works/fulltext/sync
 *     Whether sync is set up and in progress, the last status and error, and per
 *     library: type, group id, version, last sync, unsynced item count.
 */
let syncRuns = 0;
let lastSyncError = null;
let lastSyncStarted = null;
let lastSyncFinished = null;
let apiKeyOverride = false;

function findLibrary({ libraryID, groupID }) {
  for (const library of Zotero.Libraries.getAll()) {
    if (libraryID !== undefined && library.libraryID === libraryID) return library;
    if (groupID !== undefined && library.libraryType === 'group' && library.groupID === groupID) return library;
  }
  return null;
}

async function libraryRows() {
  const rows = [];
  for (const library of Zotero.Libraries.getAll()) {
    const unsynced = await Zotero.DB.valueQueryAsync(
      'SELECT COUNT(*) FROM items WHERE libraryID=? AND synced=0', library.libraryID,
    );
    rows.push({
      libraryID: library.libraryID, libraryType: library.libraryType,
      groupID: library.groupID ?? null, name: library.name ?? null,
      libraryVersion: library.libraryVersion ?? null, lastSync: library.lastSync ?? null,
      storageVersion: library.storageVersion ?? null, unsynced,
    });
  }
  return rows;
}

function Sync() {}
Sync.prototype = {
  supportedMethods: ['GET', 'POST'],
  supportedDataTypes: ['application/json'],
  init: async function ({ method, data }) {
    const runner = Zotero.Sync.Runner;
    if (method === 'POST') {
      const libraryID = Number.isInteger(data?.libraryID) ? data.libraryID : undefined;
      const groupID = Number.isInteger(data?.groupID) ? data.groupID : undefined;
      if (libraryID === undefined && groupID === undefined) {
        return json(400, { error: 'body must be {"libraryID": n} or {"groupID": n}' });
      }
      const library = findLibrary({ libraryID, groupID });
      if (!library) return json(404, { error: 'no such library', libraryID, groupID });
      // The stored key sits behind the OS key store, which a headless client cannot
      // unlock (padme: "User canceled OS unlock entry" with the login keyring locked).
      // The key for this run goes through the runner's own in-memory setter, is never
      // written anywhere, never echoed, and is cleared when the run ends.
      //
      // The caller supplies it on EVERY call. The earlier guard was `!runner.enabled &&
      // !apiKey`, so a profile that already had sync set up could push a library to
      // zotero.org with no caller secret at all: the endpoint listens on the client's
      // local HTTP port, and reaching that port was the whole authorisation. Requiring
      // the key unconditionally makes the secret the authorisation, and costs a headless
      // caller nothing — it already has to pass one (ticket 0722, review round 1).
      const apiKey = typeof data?.apiKey === 'string' && data.apiKey.length > 0 ? data.apiKey : null;
      if (!apiKey) return json(401, { error: 'apiKey is required on every sync call' });
      if (runner.syncInProgress) return json(409, { error: 'a sync is already in progress' });
      syncRuns += 1;
      lastSyncError = null;
      lastSyncStarted = new Date().toISOString();
      lastSyncFinished = null;
      if (apiKey) {
        runner.apiKey = apiKey;
        apiKeyOverride = true;
      }
      runner.sync({ background: false, libraries: [library.libraryID] })
        .catch((e) => {
          lastSyncError = String(e?.message ?? e);
          log(`sync failed: ${lastSyncError}`);
        })
        .finally(() => {
          if (apiKey) {
            runner.apiKey = null;
            apiKeyOverride = false;
          }
          lastSyncFinished = new Date().toISOString();
        });
      return json(202, {
        started: true, libraryID: library.libraryID, groupID: library.groupID ?? null, apiKeyOverride,
      });
    }
    return json(200, {
      enabled: Boolean(runner.enabled), inProgress: Boolean(runner.syncInProgress),
      lastSyncStatus: runner.lastSyncStatus ?? null, syncRuns, lastSyncError, apiKeyOverride,
      lastSyncStarted, lastSyncFinished, libraries: await libraryRows(),
    });
  },
};

function install() {
  log('installed');
}

async function startup({ version }) {
  await Zotero.initializationPromise;
  pluginVersion = version ?? null;
  Zotero.Server.Endpoints[`${PREFIX}reindex`] = Reindex;
  Zotero.Server.Endpoints[`${PREFIX}status`] = Status;
  Zotero.Server.Endpoints[`${PREFIX}import`] = Import;
  Zotero.Server.Endpoints[`${PREFIX}sync`] = Sync;
  log(`started ${version}: endpoints registered under ${PREFIX}`);
}

function shutdown() {
  delete Zotero.Server.Endpoints[`${PREFIX}reindex`];
  delete Zotero.Server.Endpoints[`${PREFIX}status`];
  delete Zotero.Server.Endpoints[`${PREFIX}import`];
  delete Zotero.Server.Endpoints[`${PREFIX}sync`];
  log('shut down: endpoints removed');
}

function uninstall() {
  log('uninstalled');
}
