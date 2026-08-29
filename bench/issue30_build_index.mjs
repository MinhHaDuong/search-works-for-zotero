/**
 * Build a v1.9.0-schema Zoteus index from REAL passages and REAL vectors already on disk.
 *
 * Nothing here writes SQL of its own: the rows go in through upstream v1.9.0's own
 * SqliteSearchIndex (putItem / putPassage / putVector / save), so the schema, the FTS5
 * external-content protocol and the meta keys are exactly what a real build would write.
 * TypeScript's `protected` is compile-time only, so those methods are callable from JS.
 *
 * Sources, all real:
 *  - passages, item keys, titles, source: the 93 022-passage index at vec-real/, exported
 *    from the author's own Zotero library.
 *  - vectors: mrl/minilm384.f32, 93 022 x 384 float32, produced by all-MiniLM-L6-v2 --
 *    the same model zoteus's LocalEmbeddingProvider runs (verified: cosine 1.000000 on
 *    five sampled rows against Xenova/all-MiniLM-L6-v2 through transformers.js).
 */
import { createRequire } from 'node:module';
import { openSync, readSync, closeSync } from 'node:fs';

const require = createRequire(import.meta.url);
const { DatabaseSync } = require('node:sqlite');

const [, , outPath, distDir] = process.argv;
if (!outPath || !distDir) {
  console.error('usage: build_index.mjs <out.sqlite> <path-to-v190-dist>');
  process.exit(2);
}

const { SqliteSearchIndex } = await import(`${distDir}/features/search/sqlite-index.js`);

const SRC = '/home/haduong/data/projets/zoteus-bench/vec-real/search-index.sqlite';
const SLAB = '/home/haduong/data/projets/zoteus-bench/mrl/minilm384.f32';
const DIM = 384;
const MODEL = 'Xenova/all-MiniLM-L6-v2';

// A provider that never embeds: the vectors already exist. Its identity is what the index
// stamps as embedderId, and it must be byte-identical to what the running server reports,
// or reconcileVectorProvenance drops every vector on open.
const embedder = { name: 'local', model: MODEL, embed: async () => [] };

const idx = new SqliteSearchIndex({ path: outPath, embedder });
await idx.open();

const src = new DatabaseSync(`file:${SRC}?mode=ro`, { readOnly: true });
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
