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
 */
import { DatabaseSync } from 'node:sqlite';
import { existsSync, unlinkSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';

import { SCHEMA_VERSION } from '../index_schema.mjs';

export const GENERATIONS = ['current', 'prerename'];

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
      tokenize='unicode61 remove_diacritics 2'
    );
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
    },
  });
  if (opt.both) {
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
        '   or: node bench/fixtures/make_index_fixture.mjs --both <dir>',
    );
    process.exit(2);
  }
}
