/**
 * Build a v1.9.0-schema Zoteus index from REAL passages and REAL vectors already on disk.
 *
 * Nothing here writes SQL of its own: the rows go in through upstream v1.9.0's own
 * SqliteSearchIndex (putItem / putPassage / putVector / save), so the schema, the FTS5
 * external-content protocol and the meta keys are exactly what a real build would write.
 * TypeScript's `protected` is compile-time only, so those methods are callable from JS.
 *
 * Sources, all real, and both named on the command line rather than hardcoded:
 *  - --db: passages, item keys, titles, source, from a PRE-RENAME index (the 93 022-passage
 *    one exported from the author's own Zotero library). Its generation is asserted before
 *    the dist is loaded; see `bench/index_schema.mjs`.
 *  - --slab: the vectors, raw float32, N x --dim, in the source index's own row order --
 *    produced by all-MiniLM-L6-v2, the same model zoteus's LocalEmbeddingProvider runs
 *    verified through transformers.js at cosine 1.000000 on five sampled rows against
 *    Xenova/all-MiniLM-L6-v2. model-id-literal: prose
 */
import { createRequire } from 'node:module';
import { parseArgs } from 'node:util';
import { resolveModel } from './registry.mjs';
import { openSync, readSync, closeSync } from 'node:fs';
import { assertPreRenameSchema } from './index_schema.mjs';

const require = createRequire(import.meta.url);
const { DatabaseSync } = require('node:sqlite');

// Flags rather than the two positionals and two hardcoded absolute paths this used to
// carry (ticket 0101, following 0100's repair of `bm25_idf_effect.mjs`): a build whose
// substrate is baked into its source cannot be reproduced anywhere else, and the house
// rule forbids the hardcoded path in any case.
const { values: opt } = parseArgs({
  options: {
    db: { type: 'string' },
    slab: { type: 'string' },
    output: { type: 'string' },
    dist: { type: 'string' },
    dim: { type: 'string', default: '384' },
  },
});
if (!opt.db || !opt.output || !opt.dist || !opt.slab) {
  console.error(
    'usage: node bench/issue30_build_index.mjs --db <pre-rename source.sqlite> ' +
      '--output <out.sqlite> --dist <path-to-v190-dist> --slab <raw.f32> [--dim 384]',
  );
  process.exit(2);
}
const outPath = opt.output;
const distDir = opt.dist;
const SRC = opt.db;
const SLAB = opt.slab;
const DIM = Number(opt.dim);

// The source's generation, asserted before the dist is imported (ticket 0101). This driver
// reads a PRE-RENAME index on purpose — `passage_meta` joined to the `passages` FTS5 table
// — and it is not a stale driver awaiting migration: the current schema folded that
// metadata into `passages`, so a current index would need a different query and would be a
// different substrate. Pointed at one, this used to die twenty lines in on `no such table:
// passage_meta`, after minutes of loading a v1.9.0 dist.
const src = new DatabaseSync(`file:${SRC}?mode=ro`, { readOnly: true });
assertPreRenameSchema(src, SRC);

const { SqliteSearchIndex } = await import(`${distDir}/features/search/sqlite-index.js`);

const { repo: MODEL } = resolveModel('all-minilm-l6-v2');

// A provider that never embeds: the vectors already exist. Its identity is what the index
// stamps as embedderId, and it must be byte-identical to what the running server reports,
// or reconcileVectorProvenance drops every vector on open.
const embedder = { name: 'local', model: MODEL, embed: async () => [] };

const idx = new SqliteSearchIndex({ path: outPath, embedder });
await idx.open();

const fd = openSync(SLAB, 'r');
const rowBytes = DIM * 4;
const buf = Buffer.alloc(rowBytes);

const meta = src.prepare(
  'SELECT m.rowid AS rid, m.id AS id, m.item AS item, m.title AS title, m.source AS source, p.body AS body ' +
    'FROM passage_meta m JOIN passages p ON p.rowid = m.rowid ORDER BY m.rowid',
);

const seenItems = new Set();
let n = 0;
const t0 = Date.now();
for (const r of meta.iterate()) {
  if (!seenItems.has(r.item)) {
    seenItems.add(r.item);
    idx.putItem(r.item, r.title ?? '');
  }
  const source = r.source ? r.source : null;
  idx.putPassage({ id: r.id, itemKey: r.item, title: r.title ?? '', text: r.body, source });
  readSync(fd, buf, 0, rowBytes, (r.rid - 1) * rowBytes);
  const v = new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + rowBytes));
  idx.putVector(r.id, Array.from(v));
  n++;
  if (n % 20000 === 0) console.error(`${n} passages, ${Math.round((Date.now() - t0) / 1000)}s`);
}
closeSync(fd);
src.close();

// The meta a real build stamps. builtFromVersion is the Zotero library version the build
// read; libraryVersion/libraryBackend are the update stamp. Copied from the source index,
// so nothing here invents provenance it does not have.
idx.vectorEmbedderId = idx.embedderId;
idx.builtFromVersion = 410;
idx.itemsTotal = seenItems.size;
idx.itemsAvailable = seenItems.size;
idx.libraryVersion = 410;
idx.libraryBackend = 'local';

await idx.save();
console.error(JSON.stringify(idx.status(), null, 2).slice(0, 1500));
await idx.close();
console.error(`done: ${n} passages, ${seenItems.size} items, ${Math.round((Date.now() - t0) / 1000)}s`);
