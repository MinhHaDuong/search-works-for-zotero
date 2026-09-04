#!/usr/bin/env node
/**
 * Write a TINY search-index fixture of a named schema generation (ticket 0101).
 *
 * The guard in `bench/index_schema.mjs` (ticket 0100) refuses an index of the wrong
 * generation. A refusal nobody has ever seen fire is not a guard, so this writes the two
 * substrates that make it fire in each direction — a positive control for the accept path
 * and one for the refuse path — in about a tenth of a second, from a committed script
 * rather than from a 939 MB index nobody can commit.
 *
 * Two generations, both transcribed from indexes that exist on disk rather than from
 * memory of them:
 *
 *   current    — `sqlite-index.ts` at UPSTREAM_REVIEWED_SHA. DDL copied verbatim from
 *                `createSchema()`; verified against the x2-rebuild index.
 *   prerename  — the generation before the passages/passages_fts split, transcribed from
 *                the `sqlite_master` of the vec-real index, which that fork generation
 *                actually built. `passages` IS the FTS5 table, its column is `body`, and
 *                the per-passage metadata lives in `passage_meta`.
 *
 * What the prerename fixture deliberately omits: the `passage_vectors` /
 * `passage_vectors_bin` vec0 tables a vector-experiment index of that generation also
 * carries. They need the sqlite-vec extension loaded to create, and they are orthogonal to
 * the question the gate asks — whether the per-passage metadata lives in `passages` or in
 * `passage_meta` is what separates the generations; whether an index carries vectors is a
 * separate property within one. A fixture faking them with plain tables of the same name
 * would lie in exactly the direction this module family exists to refuse.
 *
 * Content is synthetic and deterministic — a fixed LCG, invented item keys, invented
 * titles. Real titles are document names, which the naming ruling keeps out of anything
 * committed, and a fixture whose bytes change between runs cannot be a control.
 *
 * Usage:
 *   node bench/fixtures/make_index_fixture.mjs --generation current   --output f.sqlite
 *   node bench/fixtures/make_index_fixture.mjs --generation prerename --output f.sqlite
 *   node bench/fixtures/make_index_fixture.mjs --both <dir>     # writes both, named
 *   node bench/fixtures/make_index_fixture.mjs --replay-export <snapshot> --recipe <json>
 *        --server <dist/index.js> --data-dir <dir> --embeddings off
 */
import { DatabaseSync } from 'node:sqlite';
import {
  existsSync, unlinkSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync,
  realpathSync, rmSync, statSync, writeFileSync,
} from 'node:fs';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { homedir, tmpdir } from 'node:os';
import { join, parse, resolve, sep } from 'node:path';
import { parseArgs } from 'node:util';

import { SCHEMA_VERSION } from '../index_schema.mjs';

export const GENERATIONS = ['current', 'prerename'];
const SOURCE_TAG_PREFIX = 'zoteus-golden-source:';
const ATTACHMENT_TAG_PREFIX = 'zoteus-golden-attachment:';
const EXPORT_SENTINEL = '.zoteus-golden-export.json';
const EXPORT_SENTINEL_SCHEMA = 'zoteus-golden-export/v1';
const CONTENT_TYPES = {
  pdf: 'application/pdf', djvu: 'image/vnd.djvu', html: 'text/html', wikitext: 'text/plain',
  txt: 'text/plain; charset=utf-8', epub: 'application/epub+zip',
};

function tagValues(data) {
  return (data.tags ?? []).filter((tag) => tag && typeof tag.tag === 'string').map((tag) => tag.tag);
}

function requireOnlyManagedMarker(data, expected, label) {
  const managed = tagValues(data).filter((tag) =>
    tag.startsWith(SOURCE_TAG_PREFIX) || tag.startsWith(ATTACHMENT_TAG_PREFIX));
  if (managed.length !== 1 || managed[0] !== expected) {
    throw new Error(`${label}: expected only managed marker ${expected}`);
  }
}

function expectedParent(doc, collectionKey) {
  const expected = {
    itemType: doc.item_type ?? 'document',
    title: doc.title,
    creators: [{ creatorType: 'author', name: doc.author }],
    date: String(doc.year),
    language: doc.language,
    extra: [
      `ticket-0029 recipe id: ${doc.id}`,
      `ticket-0029 work id: ${doc.work_id ?? doc.id}`,
      `ticket-0029 type fidelity: ${doc.type_fidelity ?? 'unreviewed'}`,
      `ticket-0029 work relations: ${JSON.stringify(canonicalJson(doc.work_relations ?? []))}`,
    ].join('\n'),
    collections: [collectionKey],
  };
  if (!doc.attachments) Object.assign(expected, {
    url: doc.bytes_url, archive: doc.archive, archiveLocation: doc.identifier,
  });
  return expected;
}

function sources(doc) { return doc.attachments ?? [doc]; }

function requireFields(data, expected, label) {
  for (const [field, value] of Object.entries(expected)) {
    if (JSON.stringify(canonicalJson(data[field])) !== JSON.stringify(canonicalJson(value))) {
      throw new Error(`${label}: ${field} does not match the source recipe`);
    }
  }
}

/**
 * Read and prove the shape of a ticket-0029 Zotero export before serving a byte.
 *
 * There is deliberately no built-in export.  The committed snapshot does not exist yet;
 * tests make an invented one in a temporary directory, while a real run points this at
 * the output of `golden_fixture.py export`.  That separation prevents a synthetic body
 * from quietly acquiring the standing of Zotero's extraction.
 */
export function loadGoldenExport(directory, options = {}) {
  if (!options.recipePath) throw new Error('golden export validation requires recipePath');
  const root = resolve(directory);
  if (!existsSync(root) || lstatSync(root).isSymbolicLink() || !lstatSync(root).isDirectory()) {
    throw new Error(`golden export root must be a real directory: ${root}`);
  }
  const realRoot = realpathSync(root);
  if (realRoot !== root) throw new Error(`golden export root must not traverse a symlink: ${root}`);
  const readJson = (relative, label) => {
    const path = resolve(root, relative);
    if (path !== root && !path.startsWith(`${root}${sep}`)) throw new Error(`${label} escapes the export directory`);
    if (!existsSync(path)) throw new Error(`missing ${label}: ${relative}`);
    const info = lstatSync(path);
    if (info.isSymbolicLink() || !info.isFile() || realpathSync(path) !== path) {
      throw new Error(`${label} must be a real file inside the export directory`);
    }
    if (!realpathSync(path).startsWith(`${realRoot}${sep}`)) {
      throw new Error(`${label} escapes the export directory through a symlink`);
    }
    try {
      return JSON.parse(readFileSync(path, 'utf8'));
    } catch (error) {
      throw new Error(`malformed ${label} ${relative}: ${error.message}`);
    }
  };
  const ownership = readJson(EXPORT_SENTINEL, 'export ownership marker');
  if (JSON.stringify(ownership) !== JSON.stringify({ schema: EXPORT_SENTINEL_SCHEMA })) {
    throw new Error('golden export has an invalid ownership marker');
  }
  const manifest = readJson('manifest.json', 'manifest');
  if (manifest.schema_version !== 1) throw new Error(`unsupported golden export schema ${manifest.schema_version}`);
  if (!/^[0-9a-f]{64}$/.test(manifest.recipe_sha256 ?? '')) throw new Error('manifest has no recipe sha256');
  if (!['user', 'group'].includes(manifest.library?.type) ||
      !Number.isInteger(manifest.library?.id) || manifest.library.id <= 0) {
    throw new Error('manifest must identify the public Zotero library');
  }
  if (!manifest.library.collection_key) throw new Error('manifest has no collection key');
  if (!manifest.zotero?.client_version ||
      !Number.isInteger(manifest.zotero?.['fulltext.pdfMaxPages']) ||
      !Number.isInteger(manifest.zotero?.['fulltext.textMaxLength'])) {
    throw new Error('manifest lacks the Zotero version or extraction preferences');
  }
  if (!Number.isInteger(manifest.index_fulltext_max_chars) || manifest.index_fulltext_max_chars <= 0) {
    throw new Error('manifest lacks a positive index_fulltext_max_chars');
  }
  if (manifest.items_file !== 'items.json') throw new Error('manifest items_file must be items.json');
  if (!manifest.normalizations?.linked_file_path || !manifest.normalizations?.linked_file_enclosure) {
    throw new Error('manifest does not declare linked-file path normalization');
  }
  const items = readJson(manifest.items_file, 'items');
  if (!Array.isArray(items)) throw new Error('items export is not an array');
  const itemByKey = new Map();
  for (const item of items) {
    const data = item?.data ?? item;
    const key = item?.key ?? data?.key;
    if (!key) throw new Error('items export contains an item without a key');
    if (item?.key && data?.key && item.key !== data.key) {
      throw new Error(`items export wrapper/data key mismatch for ${item.key}`);
    }
    if (itemByKey.has(key)) throw new Error(`items export contains duplicate key ${key}`);
    itemByKey.set(key, item);
  }
  if (!Array.isArray(manifest.attachments) || manifest.attachments.length === 0) {
    throw new Error('manifest has no attachment exports');
  }
  let recipe;
  try {
    const recipePath = resolve(options.recipePath);
    if (!existsSync(recipePath) || lstatSync(recipePath).isSymbolicLink() ||
        !lstatSync(recipePath).isFile() || realpathSync(recipePath) !== recipePath) {
      throw new Error('source recipe must be a real file');
    }
    recipe = JSON.parse(readFileSync(recipePath, 'utf8'));
  } catch (error) {
    throw new Error(`malformed source recipe ${options.recipePath}: ${error.message}`);
  }
  if (!Array.isArray(recipe) || recipe.length === 0) throw new Error('source recipe must be a non-empty array');
  const recipeById = new Map();
  const sourceById = new Map();
  for (const doc of recipe) {
    if (!doc || typeof doc.id !== 'string' || !/^[a-z0-9][a-z0-9-]*$/.test(doc.id) || recipeById.has(doc.id)) {
      throw new Error(`source recipe has duplicate or empty id ${doc?.id ?? ''}`);
    }
    const requiredStrings = ['title', 'author', 'language'];
    if (requiredStrings.some((field) => typeof doc[field] !== 'string' || !doc[field])) {
      throw new Error(`${doc.id}: source recipe lacks required provenance metadata`);
    }
    if (!Number.isInteger(doc.year)) throw new Error(`${doc.id}: source recipe has invalid year`);
    if (doc.attachments && (typeof doc.item_type !== 'string' || !doc.item_type ||
        !['correct', 'intentionally-wrong'].includes(doc.type_fidelity) ||
        typeof doc.work_id !== 'string' || !Array.isArray(doc.work_relations) ||
        !Array.isArray(doc.structural_features))) {
      throw new Error(`${doc.id}: source recipe lacks parent identity/type metadata`);
    }
    for (const source of sources(doc)) {
      if (!source || typeof source.id !== 'string' || sourceById.has(source.id)) {
        throw new Error(`${doc.id}: duplicate or empty attachment id ${source?.id ?? ''}`);
      }
      if (['archive', 'identifier', 'bytes_url', 'license_basis'].some(
        (field) => typeof source[field] !== 'string' || !source[field]) ||
          !/^[0-9a-f]{64}$/.test(source.sha256 ?? '') ||
          !Object.hasOwn(CONTENT_TYPES, source.bytes_format ?? 'pdf')) {
        throw new Error(`${source.id}: source recipe has invalid provenance, sha256, or bytes_format`);
      }
      if (doc.attachments && (typeof source.language !== 'string' || !source.language ||
          typeof source.role !== 'string' || !source.role ||
          typeof source.relation !== 'string' || !source.relation ||
          !['indexed', 'skipped-first-with-text'].includes(source.selection_expectation) ||
          !source.cap_expectations ||
          (source.selection_expectation === 'skipped-first-with-text' && !source.skip_reason))) {
        throw new Error(`${source.id}: source recipe lacks attachment semantics`);
      }
      sourceById.set(source.id, { parent: doc, source });
    }
    recipeById.set(doc.id, doc);
  }
  const canonical = JSON.stringify(canonicalJson(recipe));
  const actual = createHash('sha256').update(canonical).digest('hex');
  if (actual !== manifest.recipe_sha256) {
    throw new Error(`snapshot recipe sha256 ${manifest.recipe_sha256} does not match ${options.recipePath} (${actual})`);
  }

  const recipeIds = new Set();
  const parentByRecipe = new Map();
  const parentKeyOwners = new Map();
  const attachmentKeys = new Set();
  const attachmentIds = new Set();
  const consumedItemKeys = new Set();
  const fulltext = new Map();
  const expectedAttachmentOrder = recipe.flatMap((doc) => sources(doc).map((source) => source.id));
  const observedAttachmentOrder = [];
  for (const row of manifest.attachments) {
    const { recipe_id: recipeId, parent_key: parent, attachment_key: key } = row;
    if (!recipeId) throw new Error('empty recipe id');
    if (!recipeById.has(recipeId)) throw new Error(`${recipeId}: attachment is not present in the source recipe`);
    if (!parent || attachmentKeys.has(parent) ||
        (parentKeyOwners.has(parent) && parentKeyOwners.get(parent) !== recipeId) ||
        (parentByRecipe.has(recipeId) && parentByRecipe.get(recipeId) !== parent)) {
      throw new Error(`${recipeId}: duplicate or empty parent key ${parent ?? ''}`);
    }
    if (!key || attachmentKeys.has(key) || parentKeyOwners.has(key)) {
      throw new Error(`${recipeId}: duplicate or empty attachment key ${key ?? ''}`);
    }
    recipeIds.add(recipeId);
    parentByRecipe.set(recipeId, parent);
    parentKeyOwners.set(parent, recipeId);
    attachmentKeys.add(key);
    const parentItem = itemByKey.get(parent);
    if (!parentItem) throw new Error(`${recipeId}: missing parent item ${parent}`);
    const parentData = itemData(parentItem);
    if (parentData.parentItem) throw new Error(`${recipeId}: declared parent ${parent} is itself a child`);
    requireOnlyManagedMarker(parentData, `${SOURCE_TAG_PREFIX}${recipeId}`, recipeId);
    requireFields(parentData, expectedParent(recipeById.get(recipeId), manifest.library.collection_key), recipeId);
    const attachment = itemByKey.get(key);
    if (!attachment) throw new Error(`${recipeId}: missing attachment item ${key}`);
    const data = attachment.data ?? attachment;
    // A group library refuses linked-file attachments outright (Zotero's own local API:
    // 400 "Linked files can only be added to user library", verified 2026-09-04), so a
    // group export's attachments are stored (imported_file) instead.
    const expectedLinkMode = manifest.library.type === 'group' ? 'imported_file' : 'linked_file';
    if (data.parentItem !== parent || data.linkMode !== expectedLinkMode) {
      throw new Error(`${recipeId}: ${key} is not the declared ${expectedLinkMode} child of ${parent}`);
    }
    const doc = recipeById.get(recipeId);
    const attachmentId = doc.attachments ? row.attachment_id : doc.id;
    const sourceEntry = sourceById.get(attachmentId);
    if (!sourceEntry || sourceEntry.parent.id !== recipeId || attachmentIds.has(attachmentId)) {
      throw new Error(`${recipeId}: duplicate, empty, or foreign attachment id ${attachmentId ?? ''}`);
    }
    attachmentIds.add(attachmentId);
    observedAttachmentOrder.push(attachmentId);
    const source = sourceEntry.source;
    if (doc.attachments && (row.role !== source.role || row.relation !== source.relation ||
        row.language !== source.language || row.bytes_format !== (source.bytes_format ?? 'pdf') ||
        row.selection_expectation !== source.selection_expectation ||
        JSON.stringify(canonicalJson(row.cap_expectations)) !== JSON.stringify(canonicalJson(source.cap_expectations)) ||
        row.skip_reason !== (source.skip_reason ?? ''))) {
      throw new Error(`${attachmentId}: manifest attachment semantics do not match the recipe`);
    }
    if (expectedLinkMode === 'linked_file') {
      const expectedPath = `attachments:${source.id}.${source.bytes_format ?? 'pdf'}`;
      if (data.path !== expectedPath || !/^attachments:[^/\\]+$/.test(data.path)) {
        throw new Error(`${recipeId}: linked-file path is not portable`);
      }
    } else {
      // A stored attachment carries no machine path at all -- Zotero manages the bytes
      // under its own storage directory, keyed by attachment key, not by client host.
      const expectedFilename = `${source.id}.${source.bytes_format ?? 'pdf'}`;
      if (data.filename !== expectedFilename) {
        throw new Error(`${recipeId}: stored attachment filename does not match its pinned source`);
      }
    }
    requireOnlyManagedMarker(data, `${ATTACHMENT_TAG_PREFIX}${source.id}`, source.id);
    requireFields(data, {
      itemType: 'attachment', title: source.title ?? doc.title,
      contentType: CONTENT_TYPES[source.bytes_format ?? 'pdf'] ?? 'application/octet-stream',
      extra: `ticket-0029 source sha256: ${source.sha256}; role: ${source.role ?? 'primary'}; relation: ${source.relation ?? 'primary'}; language: ${source.language ?? ''}; selection: ${source.selection_expectation ?? 'indexed'}; skip reason: ${source.skip_reason ?? ''}; fulltext: reindexed`,
    }, source.id);
    if (String(attachment.links?.enclosure?.href ?? '').startsWith('file:')) {
      throw new Error(`${recipeId}: linked-file enclosure discloses a machine path`);
    }
    const expectedFile = `fulltext/${key}.json`;
    if (row.fulltext_file !== expectedFile) throw new Error(`${recipeId}: fulltext locator must be ${expectedFile}`);
    if (!Number.isInteger(row.fulltext_version) || row.fulltext_version < 0) {
      throw new Error(`${recipeId}: invalid fulltext version`);
    }
    const body = readJson(row.fulltext_file, `fulltext for ${key}`);
    if (typeof body?.content !== 'string' || !body.content.trim() || !Number.isInteger(body.indexedPages) ||
        !Number.isInteger(body.totalPages)) {
      throw new Error(`${recipeId}: malformed fulltext for ${key}`);
    }
    if (body.indexedPages < 0 || body.totalPages < 0 || body.indexedPages > body.totalPages) {
      throw new Error(`${recipeId}: invalid indexedPages/totalPages relation`);
    }
    for (const [field, bodyField] of [['indexed_pages', 'indexedPages'], ['total_pages', 'totalPages']]) {
      if (row[field] !== body[bodyField]) throw new Error(`${source.id}: manifest ${field} does not match fulltext`);
    }
    for (const [field, bodyField] of [['indexed_chars', 'indexedChars'], ['total_chars', 'totalChars']]) {
      if (row[field] !== (body[bodyField] ?? null)) throw new Error(`${source.id}: manifest ${field} does not match fulltext`);
    }
    fulltext.set(key, { body, version: row.fulltext_version });
    consumedItemKeys.add(parent);
    consumedItemKeys.add(key);
  }
  if (recipeIds.size !== recipeById.size || [...recipeById.keys()].some((id) => !recipeIds.has(id)) ||
      attachmentIds.size !== sourceById.size || [...sourceById.keys()].some((id) => !attachmentIds.has(id))) {
    throw new Error(`manifest attachments are not an exact bijection with the ${sourceById.size}-attachment recipe`);
  }
  if (JSON.stringify(observedAttachmentOrder) !== JSON.stringify(expectedAttachmentOrder)) {
    throw new Error('manifest attachment order does not match the recipe');
  }
  if (manifest.parent_item_count !== recipe.length ||
      manifest.attachment_count !== sourceById.size ||
      !Number.isInteger(manifest.source_byte_count) || manifest.source_byte_count <= 0) {
    throw new Error('manifest parent, attachment, or source-byte count does not match the recipe');
  }
  if (consumedItemKeys.size !== itemByKey.size || [...itemByKey.keys()].some((key) => !consumedItemKeys.has(key))) {
    throw new Error('items export contains a row not consumed by the recipe attachment mapping');
  }
  return { root, manifest, items, itemByKey, fulltext };
}

/** Sort object keys recursively to match `golden_fixture.py`'s canonical recipe hash. */
function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalJson(value[key])]));
  }
  return value;
}

function itemData(item) {
  return item.data ?? item;
}

function itemKey(item) {
  return item.key ?? itemData(item).key;
}

function itemVersion(item) {
  return Number(item.version ?? itemData(item).version ?? 0);
}

function sendJson(response, status, body, headers = {}) {
  const encoded = Buffer.from(JSON.stringify(body));
  response.writeHead(status, {
    'content-type': 'application/json',
    'content-length': String(encoded.length),
    ...headers,
  });
  response.end(encoded);
}

/** Resolve one request without a socket; also the replay server's only route table. */
export function goldenReplayResponse(fixture, method, rawUrl) {
  const library = fixture.manifest.library;
  const prefix = library.type === 'group' ? `/api/groups/${library.id}` : '/api/users/0';
  const url = new URL(rawUrl, 'http://127.0.0.1');
  const commonHeaders = {
    'last-modified-version': String(fixture.manifest.library_version ?? 0),
    'zotero-server-id': 'ticket-0029-offline-replay',
  };
  const answer = (status, body, headers = commonHeaders) => ({ status, body, headers });
  // Capability discovery is always rooted at users/0, including when the build target is
  // a group.  Without these two routes Zoteus sees a dead desktop, or sees no local
  // groups, and silently routes the corpus to the cloud instead of this replay.
  if (method === 'GET' && library.type === 'group' && url.pathname === '/api/users/0/items') {
    return answer(200, [], { ...commonHeaders, 'total-results': '0' });
  }
  if (method === 'GET' && library.type === 'group' && url.pathname === '/api/users/0/groups') {
    const start = Math.max(0, Number(url.searchParams.get('start') ?? 0));
    const groups = start === 0 ? [{ id: library.id, data: { id: library.id } }] : [];
    return answer(200, groups, { ...commonHeaders, 'total-results': '1' });
  }
  if (method !== 'GET' || !url.pathname.startsWith(prefix)) {
    return answer(404, { error: 'golden replay: route not captured' }, {});
  }
  const route = url.pathname.slice(prefix.length);
  if (route === '/fulltext') {
    const since = Number(url.searchParams.get('since') ?? 0);
    const body = {};
    for (const [key, value] of fixture.fulltext) {
      if (since === 0 || value.version > since) body[key] = value.version;
    }
    return answer(200, body);
  }
  const fulltextMatch = route.match(/^\/items\/([^/]+)\/fulltext$/);
  if (fulltextMatch) {
    const found = fixture.fulltext.get(decodeURIComponent(fulltextMatch[1]));
    return found
      ? answer(200, found.body, { ...commonHeaders, 'last-modified-version': String(found.version) })
      : answer(404, { error: 'no full text' });
  }
  const childrenMatch = route.match(/^\/items\/([^/]+)\/children$/);
  if (childrenMatch) {
    const parent = decodeURIComponent(childrenMatch[1]);
    const children = fixture.items.filter((item) => itemData(item).parentItem === parent);
    return answer(200, children, { ...commonHeaders, 'total-results': String(children.length) });
  }
  const oneItemMatch = route.match(/^\/items\/(?!top$)([^/]+)$/);
  if (oneItemMatch) {
    const found = fixture.itemByKey.get(decodeURIComponent(oneItemMatch[1]));
    return found ? answer(200, found) : answer(404, { error: 'no such item' });
  }
  const collection = library.collection_key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const listMatch = route.match(new RegExp(`^(?:/collections/${collection})?/items(/top)?$`));
  if (listMatch) {
    let rows = [...fixture.items];
    if (listMatch[1]) rows = rows.filter((item) => !itemData(item).parentItem);
    const itemType = url.searchParams.get('itemType');
    if (itemType) rows = rows.filter((item) => itemData(item).itemType === itemType);
    const since = Number(url.searchParams.get('since') ?? 0);
    if (since > 0) rows = rows.filter((item) => itemVersion(item) > since);
    const sort = url.searchParams.get('sort');
    if (sort) {
      rows.sort((a, b) => String(itemData(a)[sort] ?? '').localeCompare(String(itemData(b)[sort] ?? '')));
      if (url.searchParams.get('direction') === 'desc') rows.reverse();
    }
    const total = rows.length;
    const headers = { ...commonHeaders, 'total-results': String(total) };
    if (url.searchParams.get('format') === 'versions') {
      return answer(200, Object.fromEntries(rows.map((item) => [itemKey(item), itemVersion(item)])), headers);
    }
    const start = Math.max(0, Number(url.searchParams.get('start') ?? 0));
    const limit = Math.max(0, Number(url.searchParams.get('limit') ?? 100));
    return answer(200, rows.slice(start, start + limit), headers);
  }
  return answer(404, { error: 'golden replay: route not captured' });
}

/**
 * Serve the captured export as Zotero's read-only local API on an ephemeral port.
 * Unknown routes are 404 and recorded, so the caller cannot mistake an incomplete fake
 * for an empty Zotero result.
 */
export async function startGoldenReplay(fixture, options = {}) {
  const requests = [];
  const server = createServer((request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1');
    const result = goldenReplayResponse(fixture, request.method ?? 'GET', request.url);
    requests.push({ method: request.method ?? 'GET', url: `${url.pathname}${url.search}`, status: result.status });
    sendJson(response, result.status, result.body, result.headers);
  });
  await new Promise((resolveListen, reject) => {
    server.once('error', reject);
    server.listen(options.port ?? 0, '127.0.0.1', resolveListen);
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('golden replay did not obtain a TCP port');
  return {
    port: address.port,
    requests,
    close: () => new Promise((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose())),
  };
}

/** A reviewed runtime allowlist: unknown parent variables may themselves be secrets. */
export function offlineBuildEnvironment(source = process.env) {
  const allowed = new Set([
    'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
    'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT',
    'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'NODE_PATH', 'PYTHONPATH', 'VIRTUAL_ENV',
    'CUDA_VISIBLE_DEVICES', 'ROCR_VISIBLE_DEVICES', 'HIP_VISIBLE_DEVICES',
  ]);
  const clean = {};
  for (const [key, value] of Object.entries(source)) {
    if (allowed.has(key) && typeof value === 'string') clean[key] = value;
  }
  clean.ZOTEUS_UPDATE_CHECK = 'false';
  clean.ZOTEUS_OAUTH_ENABLED = 'false';
  return clean;
}

/** Refuse a user's existing index and paths too broad to be a dedicated build target. */
export function requireFreshBuildDirectory(directory) {
  if (!directory) throw new Error('golden replay needs a dedicated data directory');
  const candidate = resolve(directory);
  if (!existsSync(candidate) || !statSync(candidate).isDirectory()) {
    throw new Error(`golden replay data directory must already exist and be empty: ${candidate}`);
  }
  const actual = realpathSync(candidate);
  if (candidate !== actual) throw new Error(`golden replay data directory must not be a symlink: ${candidate}`);
  const broad = new Set([
    parse(actual).root, resolve(homedir()), resolve(import.meta.dirname, '..', '..'), resolve(tmpdir()),
  ]);
  if (broad.has(actual)) throw new Error(`golden replay refuses broad data directory ${actual}`);
  if (readdirSync(actual).length !== 0) throw new Error(`golden replay data directory is not empty: ${actual}`);
  return actual;
}

export function claimFreshBuildDirectory(directory, fixture) {
  const dataDirectory = requireFreshBuildDirectory(directory);
  const sentinelName = '.zoteus-golden-build.json';
  writeFileSync(join(dataDirectory, sentinelName), `${JSON.stringify({
    schema: 'zoteus-golden-build/v1',
    recipe_sha256: fixture.manifest.recipe_sha256,
    export_root: fixture.root,
  }, null, 2)}\n`, { flag: 'wx' });
  if (readdirSync(dataDirectory).some((name) => name !== sentinelName)) {
    throw new Error(`golden replay data directory changed while it was claimed: ${dataDirectory}`);
  }
  return dataDirectory;
}

function successfulRequest(requests, predicate) {
  return requests.some((request) => request.method === 'GET' && request.status === 200 && predicate(new URL(request.url, 'http://replay')));
}

/** Prove the real driver built this fixture and exercised every required API surface. */
export function validateGoldenBuildResult(fixture, result, requests, dataDirectory) {
  const status = result?.status;
  const explicitState = String(status?.state ?? '').trim().toLowerCase();
  const genericStatus = String(status?.status ?? '').trim().toLowerCase();
  if (explicitState && genericStatus && explicitState !== genericStatus) {
    throw new Error(`golden replay build reported conflicting state=${explicitState} and status=${genericStatus}`);
  }
  const state = explicitState || genericStatus;
  if (state !== 'done') {
    throw new Error(`golden replay build did not finish successfully (${state || 'missing state'})`);
  }
  const expectedItems = fixture.manifest.parent_item_count;
  const builtItems = status.itemsFetched ?? status.items;
  if (!Number.isInteger(builtItems) || builtItems !== expectedItems) {
    throw new Error(`golden replay built ${builtItems ?? 'no'} items; expected ${expectedItems}`);
  }
  if (!Number.isInteger(status.passages) || status.passages < expectedItems ||
      !Number.isInteger(status.fulltextPassages) || status.fulltextPassages < expectedItems) {
    throw new Error('golden replay produced no complete item/fulltext passage result');
  }
  const indexSize = result.files?.['search-index.sqlite'];
  const indexPath = join(dataDirectory, 'search-index.sqlite');
  if (!Number.isInteger(indexSize) || indexSize <= 0 || !existsSync(indexPath) || statSync(indexPath).size <= 0) {
    throw new Error('golden replay did not produce a non-empty search-index.sqlite');
  }
  const failed = requests.find((request) => request.status !== 200);
  if (failed) throw new Error(`golden replay received ${failed.status} for ${failed.method} ${failed.url}`);
  const library = fixture.manifest.library;
  const prefix = library.type === 'group' ? `/api/groups/${library.id}` : '/api/users/0';
  const required = [
    ['local capability probe', (url) => url.pathname === '/api/users/0/items'],
    ['library item listing', (url) => url.pathname.startsWith(`${prefix}/`) && /\/items(?:\/top)?$/.test(url.pathname)],
    ['fulltext census', (url) => url.pathname === `${prefix}/fulltext`],
  ];
  if (library.type === 'group') {
    required.push(['local group discovery', (url) => url.pathname === '/api/users/0/groups']);
  }
  for (const row of fixture.manifest.attachments) {
    required.push([
      `fulltext body ${row.attachment_key}`,
      (url) => url.pathname === `${prefix}/items/${encodeURIComponent(row.attachment_key)}/fulltext`,
    ]);
  }
  for (const [label, predicate] of required) {
    if (!successfulRequest(requests, predicate)) throw new Error(`golden replay did not exercise ${label}`);
  }
  return result;
}

/** Run the real MCP build driver against the replay, never a hand-written indexer. */
export async function runGoldenBuild(fixture, options) {
  if (options.embeddings !== 'off') {
    throw new Error('golden replay embeddings must be off for true offline replay');
  }
  const dataDirectory = claimFreshBuildDirectory(options.dataDir, fixture);
  const resultDirectory = mkdtempSync(join(tmpdir(), 'zoteus-golden-result-'));
  let replay;
  try {
    replay = await (options.startReplay ?? startGoldenReplay)(fixture);
  } catch (error) {
    rmSync(resultDirectory, { recursive: true, force: true });
    throw error;
  }
  const topItems = fixture.items.filter((item) => !itemData(item).parentItem).length;
  const resultPath = join(resultDirectory, 'build.json');
  const args = [
    'bench/run_build.py',
    '--server', options.server,
    '--data-dir', dataDirectory,
    '--backend', 'sqlite',
    '--poll', String(options.poll ?? 0.2),
    '--max-wait', String(options.maxWait ?? 3600),
    '--max-items', String(topItems),
    '--max-chars', String(fixture.manifest.index_fulltext_max_chars),
    '--embeddings', options.embeddings,
    '--result-json', resultPath,
    '--build',
  ];
  const env = {
    ...offlineBuildEnvironment(),
    ZOTERO_LOCAL_PORT: String(replay.port),
    ZOTEUS_LOCAL: 'on',
    ZOTERO_LIBRARY_TYPE: fixture.manifest.library.type,
    ZOTERO_LIBRARY_ID: String(fixture.manifest.library.id),
  };
  try {
    const exitCode = await new Promise((resolveExit, reject) => {
      const child = (options.spawnImpl ?? spawn)(options.python ?? process.env.PYTHON ?? 'python3', args, {
        cwd: resolve(import.meta.dirname, '..', '..'), env, stdio: 'inherit',
      });
      child.once('error', reject);
      child.once('exit', (code, signal) => resolveExit(code ?? (signal ? 128 : 1)));
    });
    if (exitCode !== 0) throw new Error(`golden replay build exited ${exitCode}`);
    if (!existsSync(resultPath)) throw new Error('golden replay driver wrote no result JSON');
    const buildResult = JSON.parse(readFileSync(resultPath, 'utf8'));
    validateGoldenBuildResult(fixture, buildResult, replay.requests, dataDirectory);
    const result = {
      exit_code: exitCode,
      recipe_sha256: fixture.manifest.recipe_sha256,
      replay_requests: replay.requests,
      build: buildResult,
    };
    if (options.report) writeFileSync(options.report, `${JSON.stringify(result, null, 2)}\n`);
    return result;
  } finally {
    await replay.close();
    rmSync(resultDirectory, { recursive: true, force: true });
  }
}


/**
 * How many passages a fixture carries.
 *
 * Not as small as it could be, and the reason is a real failure of an earlier draft. At a
 * dozen passages every driver's *gate* fires correctly, and every driver that then tries
 * to MEASURE something falls over on arithmetic — `index_concentration.mjs` picks its
 * sampling pool from terms whose document frequency lies between `max(20, 0.0002 N)` and
 * `0.05 N`, an empty band below N = 400. A fixture that can only ever exercise the refusal
 * path is half a control. Six hundred rows cost about a tenth of a second and 300 KB, and
 * they let two drivers run end to end.
 */
const PASSAGES = 600;

/** Vocabulary size. Zipf over this many terms puts real df spread in the fts5vocab scan. */
const VOCAB = 400;

/** Terms per passage. */
const TERMS_PER_PASSAGE = 24;

/** Deterministic pseudo-randomness: the same fixture on every machine, every run. */
function lcg(seed) {
  let s = seed >>> 0;
  return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
}

/**
 * A Zipf-shaped vocabulary: rank 1 in most passages, the tail in one or two.
 *
 * Flat sampling was the first attempt and it is worthless here — every term lands in one
 * df band, so a driver that selects probe terms BY band finds an empty pool and either
 * throws or, worse, measures nothing while reporting a clean run. The synthetic terms are
 * `w0000`-shaped rather than word-shaped so nobody mistakes fixture output for a finding,
 * and they are over four characters because that is the length filter the concentration
 * driver applies to its pool.
 */
function vocabulary() {
  const weights = [];
  let total = 0;
  for (let i = 0; i < VOCAB; i++) {
    const w = 1 / (i + 1);
    weights.push(w);
    total += w;
  }
  return { terms: Array.from({ length: VOCAB }, (_, i) => `w${String(i).padStart(4, '0')}`), weights, total };
}

/**
 * Synthetic passages over that vocabulary, with an uneven item distribution.
 *
 * One item holds 45% of the passages: that is the shape `index_concentration.mjs` and
 * `bm25_idf_effect.mjs` both look for (a dominant item to exclude), and a fixture where
 * every item is the same size would let a driver report a dominant item that is an
 * artefact of the ORDER BY tie-break rather than of the corpus.
 */
function corpus() {
  const rnd = lcg(20260902);
  const { terms, weights, total } = vocabulary();
  const pick = () => {
    let r = rnd() * total;
    for (let i = 0; i < weights.length; i++) {
      r -= weights[i];
      if (r <= 0) return terms[i];
    }
    return terms[terms.length - 1];
  };
  const rows = [];
  for (let i = 0; i < PASSAGES; i++) {
    const words = [];
    for (let w = 0; w < TERMS_PER_PASSAGE; w++) words.push(pick());
    const frac = i / PASSAGES;
    // Invented keys, and recognisably invented: nothing here names a document.
    const item = frac < 0.45 ? 'ZZFIXT01' : frac < 0.75 ? 'ZZFIXT02' : frac < 0.92 ? 'ZZFIXT03' : 'ZZFIXT04';
    rows.push({
      pid: i + 1,
      id: `${item}#${i}`,
      item,
      title: `fixture item ${item}`,
      text: words.join(' '),
      source: i % 3 === 0 ? 'fulltext' : null,
      ord: i,
    });
  }
  return rows;
}

function fresh(path) {
  for (const f of [path, `${path}-wal`, `${path}-shm`]) if (existsSync(f)) unlinkSync(f);
  return new DatabaseSync(path);
}

/** The current generation, DDL copied from upstream `createSchema()`. */
export function writeCurrent(path) {
  const db = fresh(path);
  db.exec(`
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS items (item_key TEXT PRIMARY KEY, title TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS passages (
      pid INTEGER PRIMARY KEY,
      id TEXT NOT NULL UNIQUE,
      item_key TEXT NOT NULL,
      title TEXT NOT NULL,
      text TEXT NOT NULL,
      source TEXT,
      vector BLOB
    );
    CREATE INDEX IF NOT EXISTS passages_item ON passages(item_key);
    CREATE INDEX IF NOT EXISTS passages_source ON passages(source);
    CREATE TABLE IF NOT EXISTS vector_codes (pid INTEGER PRIMARY KEY, code BLOB NOT NULL);
    CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
      text,
      content='passages',
      content_rowid='pid',
      tokenize='unicode61 remove_diacritics 0'
    );
    -- Schema 2's one new table (v1.13.0). The fixture carries it because the fixture
    -- stamps schemaVersion 2, and a file stamped 2 whose shape is 1 is the exact lie
    -- this generator exists to keep out of a driver's hands. Upstream derives it from
    -- the FTS vocabulary; here it is written by hand, small, from the corpus below.
    CREATE TABLE IF NOT EXISTS accent_variants (
      folded TEXT NOT NULL,
      term TEXT NOT NULL,
      df INTEGER NOT NULL,
      PRIMARY KEY (folded, term)
    ) WITHOUT ROWID;
  `);
  const rows = corpus();
  const insItem = db.prepare('INSERT OR IGNORE INTO items(item_key, title) VALUES (?, ?)');
  const insP = db.prepare(
    'INSERT INTO passages(pid, id, item_key, title, text, source) VALUES (?, ?, ?, ?, ?, ?)',
  );
  // External content: the FTS5 side is fed by rowid, exactly as upstream's putPassage does.
  const insF = db.prepare('INSERT INTO passages_fts(rowid, text) VALUES (?, ?)');
  db.exec('BEGIN');
  for (const r of rows) {
    insItem.run(r.item, r.title);
    insP.run(r.pid, r.id, r.item, r.title, r.text, r.source);
    insF.run(r.pid, r.text);
  }
  db.exec('COMMIT');
  const setMeta = db.prepare('INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)');
  // schemaVersion is the row this fixture exists to give a consumer: UPSTREAM declares the
  // generation the drivers target, and the standing test compares the two.
  setMeta.run('schemaVersion', String(SCHEMA_VERSION));
  setMeta.run('libraryBackend', 'local');
  setMeta.run('libraryVersion', '1');
  setMeta.run('builtFromVersion', '1');
  setMeta.run('itemsTotal', '3');
  setMeta.run('itemsAvailable', '3');
  setMeta.run('droplist', 'index passage');
  setMeta.run('droplistPassages', String(rows.length));
  // Schema 2's expansion map is derived state with a cadence, and its cadence marker is a
  // meta row. `accent_variants` itself stays EMPTY here and that is faithful rather than
  // lazy: the corpus is ASCII by the naming ruling, every term folds to itself, and
  // upstream's derivation stores a row only where a folded form has an accented spelling
  // to expand to. A fixture inventing accented rows the corpus does not contain would be
  // the same class of lie as stamping 2 on a schema-1 shape.
  setMeta.run('accentVariantsPassages', String(rows.length));
  db.close();
  return path;
}

/** The pre-rename generation, DDL transcribed from a real index of that generation. */
export function writePrerename(path) {
  const db = fresh(path);
  db.exec(`
    CREATE TABLE index_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE passage_meta(
      rowid INTEGER PRIMARY KEY,
      id TEXT NOT NULL UNIQUE,
      item TEXT NOT NULL,
      ord INTEGER NOT NULL,
      title TEXT,
      source TEXT
    );
    CREATE VIRTUAL TABLE passages USING fts5(
      body, tokenize='unicode61 remove_diacritics 2');
  `);
  const rows = corpus();
  const insM = db.prepare(
    'INSERT INTO passage_meta(rowid, id, item, ord, title, source) VALUES (?, ?, ?, ?, ?, ?)',
  );
  const insP = db.prepare('INSERT INTO passages(rowid, body) VALUES (?, ?)');
  db.exec('BEGIN');
  for (const r of rows) {
    insM.run(r.pid, r.id, r.item, r.ord, r.title, r.source);
    insP.run(r.pid, r.text);
  }
  db.exec('COMMIT');
  const setMeta = db.prepare('INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)');
  setMeta.run('indexBackend', 'local');
  setMeta.run('builtFromVersion', '1');
  // The key the vector drivers read. 8 rather than 384: this fixture carries no vectors,
  // and a plausible-looking dimension would invite a reader to believe it does.
  setMeta.run('vectorDim', '8');
  db.close();
  return path;
}

const WRITERS = { current: writeCurrent, prerename: writePrerename };

/** Both fixtures in one directory, under the names the standing test expects. */
export function writeBoth(dir) {
  mkdirSync(dir, { recursive: true });
  return {
    current: writeCurrent(join(dir, 'index-current.sqlite')),
    prerename: writePrerename(join(dir, 'index-prerename.sqlite')),
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { values: opt } = parseArgs({
    options: {
      generation: { type: 'string' },
      output: { type: 'string' },
      both: { type: 'string' },
      'replay-export': { type: 'string' },
      recipe: { type: 'string' },
      server: { type: 'string' },
      'data-dir': { type: 'string' },
      embeddings: { type: 'string' },
      report: { type: 'string' },
      'max-wait': { type: 'string' },
    },
  });
  if (opt['replay-export']) {
    const missing = ['recipe', 'server', 'data-dir', 'embeddings'].filter((key) => !opt[key]);
    if (missing.length) {
      console.error(`golden replay requires ${missing.map((key) => `--${key}`).join(', ')}`);
      process.exit(2);
    }
    if (opt.embeddings !== 'off') {
      console.error('--embeddings must be off for true offline replay');
      process.exit(2);
    }
    const fixture = loadGoldenExport(opt['replay-export'], { recipePath: opt.recipe });
    await runGoldenBuild(fixture, {
      server: opt.server,
      dataDir: opt['data-dir'],
      embeddings: opt.embeddings,
      report: opt.report,
      maxWait: opt['max-wait'] ? Number(opt['max-wait']) : undefined,
    });
  } else if (opt.both) {
    console.log(JSON.stringify(writeBoth(opt.both), null, 2));
  } else if (opt.generation && opt.output) {
    if (!WRITERS[opt.generation]) {
      console.error(
        `unknown generation ${opt.generation}; expected one of ${GENERATIONS.join(', ')}`,
      );
      process.exit(2);
    }
    WRITERS[opt.generation](opt.output);
    console.log(opt.output);
  } else {
    console.error(
      'usage: node bench/fixtures/make_index_fixture.mjs --generation current|prerename ' +
        '--output <f.sqlite>\n' +
        '   or: node bench/fixtures/make_index_fixture.mjs --both <dir>\n' +
        '   or: node bench/fixtures/make_index_fixture.mjs --replay-export <snapshot> ' +
        '--recipe <recipe.json> --server <dist/index.js> --data-dir <dir> --embeddings off',
    );
    process.exit(2);
  }
}
