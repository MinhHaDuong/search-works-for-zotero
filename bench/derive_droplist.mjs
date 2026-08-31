#!/usr/bin/env node
/**
 * Derive a library's query droplist on an existing Zoteus SQLite index, and time the scan.
 *
 * Ticket 0091. Two things this answers that no unit test can, because both are properties
 * of a real library rather than of the code: what the `fts5vocab` scan actually costs at
 * 477k passages (the number the whole cadence argument rests on), and which terms a real
 * library puts on the list.
 *
 * It calls the SAME method a build calls, on the built `dist/`, rather than re-implementing
 * the SQL here: a measurement of a reimplementation would measure the reimplementation.
 * `refreshDroplist` is `protected`, which is a TypeScript-only construct — the emitted
 * JavaScript has an ordinary method, and calling it is what makes this the real path.
 *
 * Usage:
 *   node bench/derive_droplist.mjs --dist <fork>/dist --data-dir <dir> --out <file.json>
 */
import { parseArgs } from 'node:util';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const { values } = parseArgs({
  options: {
    dist: { type: 'string' },
    'data-dir': { type: 'string' },
    out: { type: 'string' },
    'cold-only': { type: 'boolean', default: false },
  },
});
for (const k of ['dist', 'data-dir', 'out']) {
  if (!values[k]) {
    console.error(`missing --${k}`);
    process.exit(2);
  }
}

const factory = await import(pathToFileURL(join(values.dist, 'features/search/factory.js')).href);
const silent = { debug() {}, info() {}, warn(m) { console.error(m); }, error(m) { console.error(m); } };

const jsonPath = join(values['data-dir'], 'search-index.json');
const index = await factory.createSearchIndex({
  embedder: null,
  logger: silent,
  backend: 'sqlite',
  jsonPath,
});

const status = await index.status();
// Two timings, because the cadence argument distinguishes them: a cold scan pays the page
// cache and the FTS5 segment first touch, a warm one is what a build would actually pay
// straight after writing every one of those pages.
const t0 = process.hrtime.bigint();
index.refreshDroplist(true);
const coldMs = Number(process.hrtime.bigint() - t0) / 1e6;

let warmMs = null;
if (!values['cold-only']) {
  const t1 = process.hrtime.bigint();
  index.refreshDroplist(true);
  warmMs = Number(process.hrtime.bigint() - t1) / 1e6;
}

await index.save();

// Read the stored value back through SQLite rather than off the object, so what is
// reported is what a later process will actually load.
const { createRequire } = await import('node:module');
const { DatabaseSync } = createRequire(import.meta.url)('node:sqlite');
const db = new DatabaseSync(factory.sqliteIndexPath(jsonPath));
const stored = db.prepare("SELECT value FROM meta WHERE key = 'droplist'").get()?.value ?? '';
const at = db.prepare("SELECT value FROM meta WHERE key = 'droplistPassages'").get()?.value ?? '';
db.exec("CREATE VIRTUAL TABLE IF NOT EXISTS temp.v USING fts5vocab('main', 'passages_fts', 'row')");
const terms = db.prepare('SELECT count(*) AS n FROM temp.v').get().n;
db.close();

const droplist = stored ? stored.split(' ') : [];
const out = {
  probe: 'ticket 0091 — the droplist derivation on a real library, through the shipped code path',
  data_dir: values['data-dir'],
  passages: status.documents ?? status.passages ?? null,
  vocabulary_terms: terms,
  droplist_terms: droplist.length,
  droplist_bytes: Buffer.byteLength(stored, 'utf8'),
  droplist: droplist,
  numerals_on_the_list: droplist.filter((t) => /^\p{N}+$/u.test(t)),
  derived_at_passages: Number(at) || null,
  scan_ms: { cold: Math.round(coldMs), warm: warmMs === null ? null : Math.round(warmMs) },
};
writeFileSync(values.out, `${JSON.stringify(out, null, 2)}\n`);
console.error(`wrote ${values.out}`);
await index.close();
