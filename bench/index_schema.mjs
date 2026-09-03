// The shape of a zoteus search index, asserted rather than assumed.
//
// Written for ticket 0100. Two bench drivers had been pinned to a schema upstream no
// longer writes, and the way that surfaced is the reason this module exists: not as a
// failed assertion, but as an hour lost mid-measurement to `no such table`. Upstream owns
// the schema, this repo owns the drivers, and nothing connected them.
//
// The failure mode worth engineering against is not the loud one. A driver that dies on a
// missing table is annoying; a driver that finds a table of the right NAME and the wrong
// content, and reports a number, is the defect this file exists for. `passages` is exactly
// that trap: it used to be the FTS5 virtual table and is now a plain table beside
// `passages_fts`, so `SELECT count(*) FROM passages` answers in both generations and means
// something different in each.
//
// So every driver that opens a real index calls `assertIndexSchema` before its first
// query, and the assertion reports the schema it FOUND — not merely that it disliked it.
// A reader of the error has to be able to tell "this index is a generation old" from "this
// file is not an index at all", and neither of those from "the driver is looking in the
// wrong place".
//
// Current generation, as written by `sqlite-index.ts` (SCHEMA_VERSION 2, bumped in
// v1.13.0 after five releases at 1):
//
//   passages(pid INTEGER PRIMARY KEY, id, item_key, title, text, source, vector)
//   passages_fts USING fts5(text, content='passages', content_rowid='pid',
//                           tokenize='unicode61 remove_diacritics 0')
//   accent_variants(folded, term, df) WITHOUT ROWID
//   items(item_key, title), meta(key, value), vector_codes(pid, code)
//
// What the 1 -> 2 bump did, and did not do. It did NOT touch `passages`: the DDL is
// byte-identical across the bump, so every column below is exactly as reliable as it was.
// It changed the FTS tokenizer from `remove_diacritics 2` to `0` — the index now stores
// each word as written and buys the unaccented spelling query-side by expansion — and
// added `accent_variants` to carry that expansion map. Upstream's own migration rung
// rebuilds `passages_fts` from `passages.text` in place and re-computes no vector.
//
// Two consequences for a driver, neither of which the assertion below can enforce and
// both of which a measurement can be wrong about. First, `passages_fts` no longer holds
// `passages.text` verbatim: upstream inserts `normalizeForSearch(text)`, so anything
// reconstructing or diffing the FTS content must apply that function. Second, every
// committed keyword measurement in `bench/` was taken against `remove_diacritics 2`, a
// tokenizer upstream no longer ships — those artifacts are history, not current fact.
// Ticket 0619.
//
// Pre-rename generation, transcribed from an index that fork generation actually built:
//
//   passages USING fts5(body, ...)                  -- the FTS5 table itself
//   passage_meta(rowid, id, item, ord, title, source)  -- now folded into `passages`
//   index_meta(key, value)                          -- now `meta`
//   passage_vectors USING vec0(...)                 -- sqlite-vec; never shipped upstream
//
// Ticket 0101 added the mirror image, `assertPreRenameSchema`, and the reason is a finding
// rather than a symmetry. Three drivers do not target a STALE version of the current
// schema — they target the pre-rename generation on purpose, because their measurements
// are of sqlite-vec `passage_vectors` KNN, which the current schema has no equivalent of.
// Migrating them would replace a measurement, not repair a driver. So a driver declares
// the generation it targets, and the guard holds it to that declaration in both
// directions: it must accept its own generation and refuse the other, loudly, before it
// loads an extension or a dist. A guard that only ever refuses is untested in the
// direction that matters; one that only ever accepts is not a guard.

/** Columns of `passages` a driver may rely on. `vector` is deliberately not among them. */
export const REQUIRED_PASSAGE_COLUMNS = ['pid', 'id', 'item_key', 'title', 'text'];

/** The FTS5 table name of the current generation. */
export const FTS_TABLE = 'passages_fts';

/**
 * The value upstream stamps into `meta.schemaVersion`, mirrored from `sqlite-index.ts`.
 *
 * A constant that stood at 1 from v1.7.0 to v1.12.0 and moved to 2 in v1.13.0, and
 * mirroring it here would be decoration if nothing consumed it. Two things do: the fixture generator
 * stamps it into the current-generation fixture, and the standing test asserts that stamp
 * equals `UPSTREAM_INDEX_SCHEMA_VERSION` in `UPSTREAM` and (when a fork checkout is
 * present) upstream's own `const SCHEMA_VERSION`. So the day upstream bumps it, the
 * declaration and the mirror disagree with the source and the suite says so, which is the
 * only reason to write a constant down twice.
 *
 * That day was 2026-09-03, and the third leg did not say so: it requires a `fork/`
 * checkout, `fork/` is gitignored and absent on a fresh clone, and the leg SKIPPED while
 * the other two — declaration against mirror against fixture stamp — agreed with each
 * other and with nothing upstream. Two numbers this repository wrote down cannot check a
 * third it did not. Ticket 0620 gives the leg a source it can always reach.
 */
export const SCHEMA_VERSION = 2;

/**
 * Tables that identify the pre-rename generation, transcribed from an index that fork
 * generation built rather than from memory of it.
 *
 * `passage_meta` is the discriminator, not `passages`: `passages` exists in both
 * generations under the same name, which is the whole trap.
 */
export const PRERENAME_TABLES = ['passages', 'passage_meta', 'index_meta'];

/** The single column of the pre-rename `passages` FTS5 table. */
export const PRERENAME_PASSAGE_COLUMN = 'body';

/**
 * What the file actually contains: table names, whether each is virtual, and the columns
 * of `passages`. Cheap — two catalogue queries — and safe on a file that is not an index.
 */
export function readIndexSchema(db) {
  const objects = db
    .prepare("SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name")
    .all();
  const tables = objects.map((o) => o.name);
  const virtualTables = objects
    .filter((o) => typeof o.sql === 'string' && /CREATE\s+VIRTUAL\s+TABLE/i.test(o.sql))
    .map((o) => o.name);
  const passageColumns = tables.includes('passages')
    ? db.prepare('PRAGMA table_info(passages)').all().map((c) => c.name)
    : [];
  return { tables, virtualTables, passageColumns };
}

/**
 * One line a human can read out of an error message without opening the database.
 *
 * FTS5 shadow tables are stripped: every virtual table brings five of them, and a message
 * whose useful content is buried under `*_data`, `*_idx`, `*_content`, `*_docsize` and
 * `*_config` is a message nobody reads to the end.
 */
export function describeIndexSchema(schema) {
  const shadow = new Set(
    schema.virtualTables.flatMap((v) =>
      ['data', 'idx', 'content', 'docsize', 'config'].map((s) => `${v}_${s}`),
    ),
  );
  const named = schema.tables
    .filter((t) => !t.startsWith('sqlite_') && !shadow.has(t))
    .map((t) => (schema.virtualTables.includes(t) ? `${t} (virtual)` : t));
  const cols = schema.passageColumns.length
    ? schema.passageColumns.join(', ')
    : '(no passages table)';
  return `tables: ${named.join(', ') || '(none)'}; passages columns: ${cols}`;
}

/**
 * Which generation this file is, when it can be named. Used only to make an error
 * actionable — never to branch a measurement, because a driver that quietly adapts to
 * whatever it finds is the thing this module refuses to be.
 */
function detect(schema) {
  const hasMeta = schema.tables.includes('passage_meta');
  const passagesIsVirtual = schema.virtualTables.includes('passages');
  if (hasMeta || (passagesIsVirtual && schema.passageColumns.includes('body'))) return 'prerename';
  if (schema.tables.includes('passages') && schema.tables.includes(FTS_TABLE)) return 'current';
  if (!schema.tables.length) return 'empty';
  return 'unknown';
}

/** The diagnosis line, phrased for the generation the refusing driver wanted. */
function diagnose(schema, wanted) {
  const found = detect(schema);
  if (found === 'prerename') {
    return (
      'this is the PRE-RENAME schema (upstream before the passages/passages_fts split): ' +
      '`passages` is the FTS5 table and the per-passage metadata lives in `passage_meta`. ' +
      'Rebuild the index with a current fork, or point --db at a current-schema index.'
    );
  }
  if (found === 'current') {
    return (
      'this is the CURRENT schema (the passages/passages_fts split, with the per-passage ' +
      'metadata folded into `passages`). This driver targets the pre-rename generation, ' +
      'whose vectors live in sqlite-vec `passage_vectors` tables upstream never shipped — ' +
      'so a current index is not a substrate it can be pointed at. Its measurement would ' +
      'have to be rewritten, not re-run; point --db at a pre-rename index instead.'
    );
  }
  if (found === 'empty') return 'the file contains no tables — is this a search index at all?';
  return `this is neither the current nor the pre-rename zoteus schema (wanted: ${wanted}).`;
}

/** One refusal, phrased alike whichever generation was wanted. */
function refuse(dbPath, wanted, missing, schema) {
  const label = wanted === 'current' ? 'current-schema' : 'pre-rename';
  throw new Error(
    `${dbPath}: not a ${label} zoteus index.\n` +
      `  expected but absent: ${missing.join('; ')}\n` +
      `  found: ${describeIndexSchema(schema)}\n` +
      `  diagnosis: ${diagnose(schema, wanted)}`,
  );
}

/**
 * Refuse to measure an index whose shape the driver does not target, naming what it found.
 *
 * Returns the schema on success so a caller can record it in its artifact: what a number
 * was measured against belongs beside the number.
 *
 * @param {import('node:sqlite').DatabaseSync} db an open handle
 * @param {string} dbPath the path, for the message — a driver pointed at the wrong file is
 *   as common as an index of the wrong generation, and the two errors must read differently
 */
export function assertIndexSchema(db, dbPath) {
  const schema = readIndexSchema(db);
  const missing = [];
  if (!schema.tables.includes('passages')) missing.push('table `passages`');
  if (!schema.tables.includes(FTS_TABLE)) missing.push(`table \`${FTS_TABLE}\``);
  if (schema.virtualTables.includes('passages')) {
    // The trap this whole module exists for, stated as the error a reader will act on.
    missing.push('`passages` is a VIRTUAL table here; the current schema has it as a plain table');
  }
  for (const c of REQUIRED_PASSAGE_COLUMNS) {
    if (schema.tables.includes('passages') && !schema.passageColumns.includes(c)) {
      missing.push(`column \`passages.${c}\``);
    }
  }
  if (!missing.length) return schema;
  refuse(dbPath, 'current', missing, schema);
}

/**
 * The mirror image: refuse an index that is NOT of the pre-rename generation.
 *
 * Three drivers legitimately target that generation and cannot be migrated off it.
 * `vec_real_measure.mjs` and `vec_mrl_recall.mjs` measure sqlite-vec `passage_vectors`
 * KNN, and `issue30_build_index.mjs` reads the 93 022-passage substrate those tickets were
 * measured on. None of that exists in the current schema — upstream keeps vectors in a
 * `passages.vector` BLOB and never shipped sqlite-vec — so "repairing" them to the current
 * generation would replace the measurement rather than restore it, and would silently
 * invalidate the ticket-0008 artifacts they produced.
 *
 * Leaving them unguarded was the alternative, and it is worse than it looks. Pointed at a
 * current index today, `vec_real_measure.mjs` loads an extension, then dies on `no such
 * table: index_meta` — a message that names neither generation, arriving after the load.
 * A driver that targets an older shape is fine; a driver that does not SAY SO is the
 * defect, and this is how it says so.
 *
 * @param {import('node:sqlite').DatabaseSync} db an open handle
 * @param {string} dbPath the path, for the message
 */
export function assertPreRenameSchema(db, dbPath) {
  const schema = readIndexSchema(db);
  const missing = [];
  for (const t of PRERENAME_TABLES) {
    if (!schema.tables.includes(t)) missing.push(`table \`${t}\``);
  }
  if (schema.tables.includes('passages') && !schema.virtualTables.includes('passages')) {
    // The same trap, seen from the other side: `passages` is present under the same name
    // in both generations, and answering `SELECT count(*)` in each is what makes it a trap.
    missing.push('`passages` is a PLAIN table here; the pre-rename schema has it as the FTS5 table');
  } else if (
    schema.tables.includes('passages') &&
    !schema.passageColumns.includes(PRERENAME_PASSAGE_COLUMN)
  ) {
    missing.push(`column \`passages.${PRERENAME_PASSAGE_COLUMN}\``);
  }
  if (!missing.length) return schema;
  refuse(dbPath, 'prerename', missing, schema);
}
