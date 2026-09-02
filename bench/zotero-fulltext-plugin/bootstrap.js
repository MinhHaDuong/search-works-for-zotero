/*
 * Full-text control: two endpoints on Zotero's local server, for the machine the
 * segmenter experiment runs on. Nothing here leaves the machine: Zotero binds its
 * server to the loopback interface and refuses any Host header that is not
 * localhost, and browser-shaped requests are refused unless they carry the
 * Zotero-Allowed-Request header, both by Zotero's own server code.
 *
 *   POST /search-works/fulltext/reindex   {"keys": ["ABCD1234", ...]}
 *     Queues a complete re-extraction of each named attachment, page and
 *     character limits ignored, in whichever library holds it. Returns at once.
 *
 *   GET  /search-works/fulltext/status?keys=ABCD1234,EFGH5678
 *     Per key: library, indexing state, indexed and total pages or characters.
 *     Plus the library-wide statistics and whether a reindex this plugin queued
 *     is still running. Without keys: the statistics and the busy flag only.
 *
 * The ask this stands in for belongs upstream, on Zotero's local API: nothing
 * stock lets a consumer request extraction or see that one is in progress.
 */

const PREFIX = '/search-works/fulltext/';
const STATE_NAMES = ['unavailable', 'unindexed', 'partial', 'indexed', 'queued'];

let running = 0;
let lastError = null;

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
    if (!keys || keys.length === 0) return json(400, { error: 'body must be {"keys": [...]}' });
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
      Zotero.FullText.indexItems(ids, { complete: true, ignoreErrors: true })
        .catch((e) => {
          lastError = String(e?.message ?? e);
          log(`reindex failed: ${lastError}`);
        })
        .finally(() => {
          running -= 1;
        });
    }
    return json(202, { queued, missing, notAttachments });
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
    return json(200, { busy: running > 0, running, lastError, stats, items });
  },
};

function install() {
  log('installed');
}

async function startup({ version }) {
  await Zotero.initializationPromise;
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
