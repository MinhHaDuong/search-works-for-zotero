/**
 * Run the schema-2 migration against a real 477,512-passage index, and time it.
 *
 * The rung's claim is that a tokenizer change costs a re-index of text and not a re-embed.
 * A unit test can assert the embedder was not called; only a real library can say what the
 * re-index actually costs, and that number is what decides whether the rung is a kindness
 * or a trap. It also produces the index every later measurement needs, since a droplist
 * derived from a folded corpus is derived from merged vocabulary.
 */
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const silent = { debug() {}, info() {}, warn() {}, error() {} };

const before = new DatabaseSync(args.index, { readOnly: true });
const stats = (db) => ({
  schemaVersion: db.prepare("SELECT value AS v FROM meta WHERE key='schemaVersion'").get()?.v,
  passages: db.prepare('SELECT count(*) AS n FROM passages').get().n,
  vectors: db.prepare('SELECT count(*) AS n FROM passages WHERE vector IS NOT NULL').get().n,
});
const was = stats(before);
before.close();

/** An embedder that would make itself heard if the migration called it. */
let embedCalls = 0;
const loudEmbedder = {
  name: 'must-not-be-called',
  dimension: 8,
  async embed(texts) {
    embedCalls += texts.length;
    return texts.map(() => new Array(8).fill(0));
  },
};

const { SqliteSearchIndex } = await import(`${args.dist}/features/search/sqlite-index.js`);
const index = new SqliteSearchIndex({ embedder: loudEmbedder, logger: silent, path: args.index });
const t0 = performance.now();
await index.open();
const ms = performance.now() - t0;
const notice = index.buildStatus?.().storageNotice;
await index.close();

const after = new DatabaseSync(args.index, { readOnly: true });
const now = stats(after);
after.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main', 'passages_fts', 'row')");
const vocabulary = after.prepare('SELECT count(*) AS n FROM temp.v').get().n;
after.close();

const out = {
  index: args.index,
  migration_ms: +ms.toFixed(0),
  before: was,
  after: { ...now, vocabulary_terms: vocabulary },
  embedder_texts: embedCalls,
  storage_notice: notice ?? null,
};
writeFileSync(args.out, JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
