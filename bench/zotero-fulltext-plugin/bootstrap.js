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
      version: pluginVersion, lastReindexMode, prefs,
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
  log(`started ${version}: endpoints registered under ${PREFIX}`);
}

function shutdown() {
  delete Zotero.Server.Endpoints[`${PREFIX}reindex`];
  delete Zotero.Server.Endpoints[`${PREFIX}status`];
  log('shut down: endpoints removed');
}

function uninstall() {
  log('uninstalled');
}
