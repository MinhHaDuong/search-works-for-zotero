// Ticket 0013: how concentrated is the index, and does that concentration move the ranking?
//
// Written because a review found the ticket's numbers — "42 962 of 477 511", the df/idf
// table, the order comparison — asserted with no artifact behind them, and the only driver
// (bm25_idf_effect.mjs) hand-rolled BM25 in JS over four hand-picked queries. Two things
// are different here:
//
//   1. Ranking is compared through **FTS5's own bm25()**, the function the shipped code
//      calls, not a re-implementation of it. The two regimes are the real index and a copy
//      of it with the dominant item's rows deleted — deleting rows is what makes SQLite
//      recompute its own document frequencies, so the re-weighting is genuine.
//   2. The query set is 12 purposive domain queries PLUS a seeded random sample of term
//      pairs drawn from the index's own mid-frequency vocabulary, reported separately. A
//      purposive sample chosen to probe a hypothesis cannot also be the evidence that the
//      hypothesis is general.
//
// Read-only with respect to the real index: the deletion happens in a copy.
//
// Repaired for ticket 0100 (2026-09-02). Every query below used to name `passages` as the
// FTS5 table and read its metadata from `passage_meta`; upstream now stores the metadata
// in `passages` itself and keeps the FTS5 index in `passages_fts` beside it. The driver
// asserts that shape before its first query rather than discovering it at the third —
// see `bench/index_schema.mjs` for why the assertion reports what it found.
import { DatabaseSync } from 'node:sqlite';
import { constants as fsConstants, copyFileSync, existsSync, rmSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { assertIndexSchema, describeIndexSchema } from './index_schema.mjs';

const { values: opt } = parseArgs({
  options: {
    db: { type: 'string' },
    output: { type: 'string' },
    top: { type: 'string', default: '10' },
    topk: { type: 'string', default: '10' },
    sample: { type: 'string', default: '60' },
    seed: { type: 'string', default: '20260822' },
  },
});
if (!opt.db || !opt.output) {
  console.error('usage: node bench/index_concentration.mjs --db <search-index.sqlite> --output <file.json>');
  process.exit(2);
}
const TOP = Number(opt.top);
const TOPK = Number(opt.topk);

/** Deterministic PRNG: the sample must be the same one on a re-run, or it is not evidence. */
function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Top-K ITEM keys for one query, best first, de-duplicated.
 *
 * Items rather than passages, because that is what a user sees: a document contributing
 * forty passages to the top forty still occupies one line of the answer. That
 * de-duplication is also most of why the concentration turns out not to matter, so it has
 * to be in the measurement rather than argued around it.
 */
function rank(db, query, topK) {
  const terms = query.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  if (!terms.length) return [];
  const match = terms.map((t) => `"${t}"`).join(' OR ');
  const rows = db
    .prepare(
      `SELECT p.item_key AS item, bm25(passages_fts) AS score
         FROM passages_fts JOIN passages p ON p.pid = passages_fts.rowid
        WHERE passages_fts MATCH ? ORDER BY score ASC LIMIT ?`,
    )
    .all(match, topK * 40);
  const seen = [];
  for (const r of rows) {
    if (!seen.includes(r.item)) seen.push(r.item);
    if (seen.length >= topK) break;
  }
  return seen;
}

/**
 * Agreement between two top-K item lists — and the distinction the whole measurement
 * turns on.
 *
 * Removing the dominant item changes the list twice over, and only one of those changes
 * is the idf question. It leaves the list *by construction* wherever it appeared, and
 * everything below it shifts up a rank to fill the hole; that is arithmetic, not a
 * ranking effect, and a raw jaccard or a raw position-diff counts it as one. The first
 * version of this comparison did exactly that and reported an effect four times larger
 * than the real one.
 *
 * So two verdicts are reported. `jaccard` / `identical_ordered` describe the whole list,
 * including the trivial half. `rest_*` strips the dominant item out of the before-list
 * first and asks the question actually at issue: with the idf of `keynes` and `walras`
 * restored by 20-28%, do the OTHER documents change places?
 */
function compare(a, b, dominantKey) {
  const sa = new Set(a);
  const sb = new Set(b);
  const inter = [...sa].filter((x) => sb.has(x));

  const aRest = a.filter((x) => x !== dominantKey);
  const common = aRest.filter((x) => sb.has(x));
  // Relative order of the survivors, which is what a reader of the result list perceives.
  const orderInB = common.map((x) => b.indexOf(x));
  const restOrderPreserved = orderInB.every((v, i) => i === 0 || v > orderInB[i - 1]);

  return {
    overlap: inter.length,
    jaccard: sa.size || sb.size ? +(inter.length / new Set([...a, ...b]).size).toFixed(4) : 1,
    identical_ordered: a.length === b.length && a.every((x, i) => x === b[i]),
    rest_size: aRest.length,
    rest_retained: common.length,
    rest_retention: aRest.length ? +(common.length / aRest.length).toFixed(4) : 1,
    rest_relative_order_preserved: restOrderPreserved,
  };
}

const db = new DatabaseSync(opt.db, { readOnly: true });
// Before anything is counted. `SELECT count(*) FROM passages` answers in both schema
// generations and means something different in each, so an unasserted run against a
// pre-rename index would not error — it would report.
const schema = assertIndexSchema(db, opt.db);

// ---- concentration ---------------------------------------------------------------
const total = db.prepare('SELECT count(*) AS n FROM passages').get().n;
// Key, never title. The committed artifact of this very driver had to be redacted by hand
// on 2026-08-31 when the naming ruling landed (`bench/check_names.py` is the guard); a
// driver that keeps emitting names re-creates the offence on the next run, and the guard
// only reads what is already committed. So the name never enters the artifact at all.
const top = db
  .prepare('SELECT item_key AS item, count(*) AS passages FROM passages GROUP BY item_key ORDER BY passages DESC LIMIT ?')
  .all(TOP);
const dominant = top[0];
const share = +(dominant.passages / total).toFixed(4);

// ---- a copy, where every write below happens; the real index is only ever read ------
const copyPath = `${opt.output}.without-dominant.sqlite`;
for (const f of [copyPath, `${copyPath}-wal`, `${copyPath}-shm`]) if (existsSync(f)) rmSync(f);
// FICLONE where the filesystem offers it (the index is ~1 GB and `/home/haduong/data` is
// btrfs), silently falling back to a byte copy elsewhere. This is a footprint choice, not
// a semantic one: the copy is independent either way, since a reflink is copy-on-write.
copyFileSync(opt.db, copyPath, fsConstants.COPYFILE_FICLONE);
const db2 = new DatabaseSync(copyPath);
db2.exec('PRAGMA journal_mode = DELETE');

// ---- document frequency for the vocabulary the dominant item saturates -------------
// df from FTS5's own vocabulary table — the count the ranker's idf term actually uses,
// not one recomputed here. Built on the copy because the real index is opened read-only
// and `fts5vocab` is a table that has to be created somewhere; the copy is byte-identical
// at this point, so the "before" figures are the real index's.
const vocabTable = 'bench_vocab';
// Two arguments, not three: the three-argument form (`main, passages_fts, 'row'`) is what
// upstream writes because it creates its vocab table in `temp`, and the schema name is
// only accepted when the vocab table lives outside the schema it reads. Created here in
// `main`, the same call is a "wrong number of vtable arguments" error.
db2.exec(`CREATE VIRTUAL TABLE IF NOT EXISTS ${vocabTable} USING fts5vocab(passages_fts, 'row')`);
const dfOf = db2.prepare(`SELECT doc FROM ${vocabTable} WHERE term = ?`);
const idf = (df) => Math.log(1 + (total - df + 0.5) / (df + 0.5));

const PROBE_TERMS = [
  'keynes', 'walras', 'cournot', 'ricardo', 'marshall', 'equilibrium', 'utility',
  'carbon', 'climate', 'emissions', 'discount', 'welfare',
];
const dfTable = PROBE_TERMS.map((term) => {
  const row = dfOf.get(term);
  return { term, df: row ? row.doc : 0, idf: row ? +idf(row.doc).toFixed(4) : null };
});

// The sampling pool, taken before any deletion so it describes the index as it stands.
const lo = Math.max(20, Math.floor(total * 0.0002));
const hi = Math.floor(total * 0.05);
const pool = db2
  .prepare(`SELECT term FROM ${vocabTable} WHERE doc BETWEEN ? AND ? AND length(term) > 4`)
  .all(lo, hi)
  .map((r) => r.term);

// ---- now remove the dominant item from the copy ------------------------------------
// `passages_fts` is an external-content FTS5 table over `passages`, so removing a row is
// two statements in a fixed order, and the order is load-bearing. The FTS5 'delete'
// command needs the row's OLD text to unwind the posting lists; deleting the content row
// first would leave the index holding postings that point at nothing, and the df figures
// below — the whole point of the regime — would not move. This mirrors `deleteFts` in
// upstream's `sqlite-index.ts` rather than inventing a second way to do it.
const doomed = db2.prepare('SELECT pid, text FROM passages WHERE item_key = ?').all(dominant.item);
db2.exec('BEGIN');
const delFts = db2.prepare("INSERT INTO passages_fts(passages_fts, rowid, text) VALUES('delete', ?, ?)");
const delRow = db2.prepare('DELETE FROM passages WHERE pid = ?');
for (const row of doomed) {
  delFts.run(row.pid, row.text);
  delRow.run(row.pid);
}
db2.exec('COMMIT');
const total2 = db2.prepare('SELECT count(*) AS n FROM passages').get().n;
if (total2 !== total - doomed.length) {
  throw new Error(`deletion did not land: ${total} - ${doomed.length} != ${total2}`);
}

// df AFTER removal, to show the ranker really did re-weight rather than the copy being inert.
const dfOf2 = db2.prepare(`SELECT doc FROM ${vocabTable} WHERE term = ?`);
const idf2 = (df) => Math.log(1 + (total2 - df + 0.5) / (df + 0.5));
for (const row of dfTable) {
  const r2 = dfOf2.get(row.term);
  row.df_without_dominant = r2 ? r2.doc : 0;
  row.idf_without_dominant = r2 ? +idf2(r2.doc).toFixed(4) : null;
  row.idf_shift_pct = row.idf && row.idf_without_dominant ? +(((row.idf_without_dominant - row.idf) / row.idf) * 100).toFixed(1) : null;
}

// ---- query sets --------------------------------------------------------------------
const PURPOSIVE = [
  'walras general equilibrium', 'keynes uncertainty expectations', 'cournot duopoly competition',
  'ricardo comparative advantage', 'marshall partial equilibrium', 'utility maximisation consumer',
  'carbon tax revenue recycling', 'climate damage function', 'emissions trading permits',
  'discount rate intergenerational', 'welfare economics compensation', 'monetary policy inflation',
];

// A seeded random sample from the index's OWN mid-frequency vocabulary (`pool`, taken
// above before any deletion). Mid-frequency because the extremes answer nothing: a term in
// one document ranks one document however it is weighted, and a term in nearly every
// document is flattened by any idf at all.
const rnd = mulberry32(Number(opt.seed));
const sampled = [];
for (let i = 0; i < Number(opt.sample) && pool.length > 1; i++) {
  const a = pool[Math.floor(rnd() * pool.length)];
  const b = pool[Math.floor(rnd() * pool.length)];
  if (a !== b) sampled.push(`${a} ${b}`);
}

function run(queries, label) {
  const rows = queries.map((q) => {
    const before = rank(db, q, TOPK);
    const after = rank(db2, q, TOPK);
    return { query: q, ...compare(before, after, dominant.item), dominant_in_top: before.includes(dominant.item) };
  });
  const withDominant = rows.filter((r) => r.dominant_in_top);
  return {
    label,
    queries: rows.length,
    queries_where_dominant_appears: withDominant.length,
    mean_jaccard: +(rows.reduce((s, r) => s + r.jaccard, 0) / (rows.length || 1)).toFixed(4),
    identical_ordered: rows.filter((r) => r.identical_ordered).length,
    // The two figures that answer the ticket: of the non-dominant results, how many stay,
    // and do they stay in the same relative order once idf is no longer depressed.
    mean_rest_retention: +(rows.reduce((s, r) => s + r.rest_retention, 0) / (rows.length || 1)).toFixed(4),
    rest_relative_order_preserved: rows.filter((r) => r.rest_relative_order_preserved).length,
    rows,
  };
}

const out = {
  probe: 'ticket 0013 — index concentration and its effect on ranking, through FTS5 bm25()',
  db: opt.db,
  // What the numbers were measured against. A figure whose substrate is not recorded
  // cannot be compared with the next one: that is exactly how the pre-rename artifact
  // became unrefutable rather than merely old (ticket 0100).
  db_schema: describeIndexSchema(schema),
  redaction:
    'Documents are addressed by Zotero item key and never by title or filename ' +
    '(ruling of 2026-08-31, DECISIONS.md; guard: bench/check_names.py). This driver no ' +
    'longer reads a title, so no redaction pass is needed on its output.',
  passages_total: total,
  top_items_by_passages: top,
  dominant_item: { ...dominant, share_of_index: share },
  next_largest_passages: top[1]?.passages ?? null,
  passages_after_removing_dominant: total2,
  document_frequency: dfTable,
  note:
    'Ranking regimes are the real index and a copy with the dominant item deleted; deleting rows ' +
    'is what makes FTS5 recompute its own document frequencies, so bm25() genuinely re-weights. ' +
    'Top-K is over ITEMS, de-duplicated, which is what a user sees.',
  purposive: run(PURPOSIVE, 'purposive (chosen to probe the hypothesis — not evidence that it generalises)'),
  random_sample: run(sampled, `seeded random term pairs from mid-frequency vocabulary (seed ${opt.seed})`),
};
writeFileSync(opt.output, JSON.stringify(out, null, 1));
db2.close();
db.close();
for (const f of [copyPath, `${copyPath}-wal`, `${copyPath}-shm`]) if (existsSync(f)) rmSync(f);

console.log(
  `passages ${total}; dominant ${dominant.item} ${dominant.passages} (${(share * 100).toFixed(1)}%), ` +
    `next ${out.next_largest_passages}\n` +
    `purposive: rest retention ${out.purposive.mean_rest_retention}, rest order kept ` +
    `${out.purposive.rest_relative_order_preserved}/${out.purposive.queries} (whole-list jaccard ${out.purposive.mean_jaccard})\n` +
    `random:    rest retention ${out.random_sample.mean_rest_retention}, rest order kept ` +
    `${out.random_sample.rest_relative_order_preserved}/${out.random_sample.queries} (whole-list jaccard ${out.random_sample.mean_jaccard})`,
);
