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
// Current generation, as written by `sqlite-index.ts` (SCHEMA_VERSION 1, unbumped since
// v1.7.0 and still 1 at v1.12.0):
//
//   passages(pid INTEGER PRIMARY KEY, id, item_key, title, text, source, vector)
//   passages_fts USING fts5(text, content='passages', content_rowid='pid')
//   items(item_key, title), meta(key, value)
//
// Pre-rename generation, which the two repaired drivers used to target:
//
//   passages USING fts5(body, ...)        -- the FTS5 table itself
//   passage_meta(rowid, item, id, title)  -- the columns now folded into `passages`

/** Columns of `passages` a driver may rely on. `vector` is deliberately not among them. */
export const REQUIRED_PASSAGE_COLUMNS = ['pid', 'id', 'item_key', 'title', 'text'];

/** The FTS5 table name of the current generation. */
export const FTS_TABLE = 'passages_fts';

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
 * Name the generation, when it can be named. Used only to make the error actionable —
 * never to branch the measurement, because a driver that quietly adapts to whatever it
 * finds is the thing this module refuses to be.
 */
function diagnose(schema) {
  const hasMeta = schema.tables.includes('passage_meta');
  const passagesIsVirtual = schema.virtualTables.includes('passages');
  if (hasMeta || (passagesIsVirtual && schema.passageColumns.includes('body'))) {
    return (
      'this is the PRE-RENAME schema (upstream before the passages/passages_fts split): ' +
      '`passages` is the FTS5 table and the per-passage metadata lives in `passage_meta`. ' +
      'Rebuild the index with a current fork, or point --db at a current-schema index.'
    );
  }
  if (!schema.tables.length) return 'the file contains no tables — is this a search index at all?';
  return 'this is neither the current nor the pre-rename zoteus schema.';
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
  throw new Error(
    `${dbPath}: not a current-schema zoteus index.\n` +
      `  expected but absent: ${missing.join('; ')}\n` +
      `  found: ${describeIndexSchema(schema)}\n` +
      `  diagnosis: ${diagnose(schema)}`,
  );
}
