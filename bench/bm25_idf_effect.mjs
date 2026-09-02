// Ticket 0013, the hand-rolled arm: does removing the index's dominant item change the
// ranking, when BM25 is computed here rather than by FTS5?
//
// `index_concentration.mjs` answers the same question through FTS5's own `bm25()`, which
// is the function the shipped code calls and therefore the authority. This driver stays
// because a re-implementation that agrees is evidence the first result is not an artefact
// of one ranker; it is a second arm, not a substitute. Where the two disagree, believe
// FTS5.
//
// Repaired for ticket 0100 (2026-09-02). Three defects, all in what used to be its first
// four lines: it opened a hardcoded path under the author's home, it read the pre-rename
// schema (`passage_meta`, `passages.body`, `passages MATCH`), and it hardcoded the excluded
// item key `DH8EXSVA` — a key that names the dominant item of ONE library. The path is now
// a required `--db`, the schema is asserted rather than assumed, and the excluded item
// defaults to whichever item the index at hand is actually dominated by.
import { DatabaseSync } from 'node:sqlite';
import { parseArgs } from 'node:util';
import { writeFileSync } from 'node:fs';
import { assertIndexSchema, describeIndexSchema } from './index_schema.mjs';

const { values: opt } = parseArgs({
  options: {
    db: { type: 'string' },
    output: { type: 'string' },
    exclude: { type: 'string' },
    topk: { type: 'string', default: '10' },
  },
});
if (!opt.db) {
  console.error(
    'usage: node bench/bm25_idf_effect.mjs --db <search-index.sqlite> [--output <f.json>] [--exclude <item-key>]\n' +
      '  --db       required, and deliberately without a default: a measurement whose substrate\n' +
      '             is baked into the source cannot be reproduced on another machine\n' +
      '  --exclude  item key to remove from the second regime; defaults to the index\'s own\n' +
      '             dominant item, which is what the question is about',
  );
  process.exit(2);
}
const TOPK = Number(opt.topk);

const STOP = new Set([
  'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with', 'is', 'are', 'was',
  'were', 'be', 'by', 'as', 'at', 'that', 'this', 'it', 'from', 'we', 'our', 'their', 'its',
  'these', 'those',
]);
const tok = (t) => (t.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter((x) => x.length > 1 && !STOP.has(x));

const d = new DatabaseSync(opt.db, { readOnly: true });
const schema = assertIndexSchema(d, opt.db);

// The dominant item, unless the caller names one. Reading it from the index is the repair
// for the hardcoded key: the question "does the dominant item's mass distort the ranking"
// has to be asked of whatever dominates THIS index.
// Key and count, never title: documents are addressed by Zotero item key here (ruling of
// 2026-08-31, DECISIONS.md; guard `bench/check_names.py`).
const dominant = d
  .prepare('SELECT item_key, count(*) AS passages FROM passages GROUP BY item_key ORDER BY passages DESC LIMIT 1')
  .get();
const OUT = opt.exclude ?? dominant.item_key;
if (opt.exclude) {
  const n = d.prepare('SELECT count(*) AS n FROM passages WHERE item_key = ?').get(OUT).n;
  if (n === 0) throw new Error(`--exclude ${OUT}: no passage carries that item key in ${opt.db}`);
}

const sel = d.prepare(
  `SELECT p.item_key AS item, p.id AS id, p.text AS text
     FROM passages_fts JOIN passages p ON p.pid = passages_fts.rowid
    WHERE passages_fts MATCH ?`,
);

// ---- corpus statistics, in both regimes -------------------------------------------
const N = d.prepare('SELECT count(*) AS n FROM passages').get().n;
const Nx = d.prepare('SELECT count(*) AS n FROM passages WHERE item_key <> ?').get(OUT).n;
const avg = d.prepare('SELECT avg(length(text)) AS a FROM passages').get().a / 5.5; // rough tokens
const avgx = d.prepare('SELECT avg(length(text)) AS a FROM passages WHERE item_key <> ?').get(OUT).a / 5.5;
const dfq = d.prepare('SELECT count(*) AS n FROM passages_fts WHERE passages_fts MATCH ?');
const dfqx = d.prepare(
  `SELECT count(*) AS n FROM passages_fts JOIN passages p ON p.pid = passages_fts.rowid
    WHERE passages_fts MATCH ? AND p.item_key <> ?`,
);

const k1 = 1.5;
const b = 0.75;

function rank(terms, { excl }) {
  const N_ = excl ? Nx : N;
  const avg_ = excl ? avgx : avg;
  const df = {};
  for (const t of terms) df[t] = (excl ? dfqx.get(`"${t}"`, OUT) : dfq.get(`"${t}"`)).n;
  const rows = sel.all(terms.map((t) => `"${t}"`).join(' OR ')).filter((r) => !excl || r.item !== OUT);
  const hits = rows
    .map((r) => {
      const ts = tok(r.text);
      const len = ts.length;
      const tf = {};
      for (const t of ts) tf[t] = (tf[t] ?? 0) + 1;
      let s = 0;
      for (const t of terms) {
        const f = tf[t];
        if (!f) continue;
        const n = df[t] ?? 0;
        const idf = Math.log(1 + (N_ - n + 0.5) / (n + 0.5));
        s += idf * ((f * (k1 + 1)) / (f + k1 * (1 - b + (b * len) / avg_)));
      }
      return { item: r.item, s };
    })
    .filter((h) => h.s > 0)
    .sort((a, b2) => b2.s - a.s);
  const seen = new Set();
  const out = [];
  for (const h of hits) {
    if (seen.has(h.item)) continue;
    seen.add(h.item);
    out.push(h.item);
    if (out.length >= TOPK) break;
  }
  return out;
}

const QUERIES = [
  'walras general equilibrium',
  'keynes uncertainty expectations',
  'carbon tax revenue recycling',
  'cournot duopoly competition',
];

const rows = QUERIES.map((q) => {
  const terms = tok(q);
  const withAll = rank(terms, { excl: false });
  const without = rank(terms, { excl: true });
  const overlap = withAll.filter((x) => without.includes(x)).length;
  const samePosition = withAll.filter((x, i) => without[i] === x).length;
  console.log(`\n"${q}"`);
  console.log('  with dominant   :', withAll.slice(0, 5).join(' '));
  console.log('  without         :', without.slice(0, 5).join(' '));
  console.log(
    `  top-${TOPK} overlap ${overlap}/${TOPK}   same position ${samePosition}/${TOPK}   ` +
      `top-1 ${withAll[0] === without[0] ? 'SAME' : 'CHANGED'}`,
  );
  return {
    query: q,
    with_dominant: withAll,
    without_dominant: without,
    overlap,
    same_position: samePosition,
    top1_changed: withAll[0] !== without[0],
  };
});

if (opt.output) {
  writeFileSync(
    opt.output,
    JSON.stringify(
      {
        probe: 'ticket 0013 — hand-rolled BM25 arm, second opinion on the FTS5 bm25() result',
        db: opt.db,
        db_schema: describeIndexSchema(schema),
        excluded_item: OUT,
        excluded_is_dominant: OUT === dominant.item_key,
        dominant_item: { item: dominant.item_key, passages: dominant.passages },
        redaction:
          'Documents are addressed by Zotero item key and never by title or filename ' +
          '(ruling of 2026-08-31, DECISIONS.md; guard: bench/check_names.py).',
        passages_total: N,
        passages_without_excluded: Nx,
        topk: TOPK,
        note:
          'BM25 is re-implemented here (k1=1.5, b=0.75) over passage text; `index_concentration.mjs` ' +
          'asks the same question through FTS5\'s own bm25(). Where the two disagree, FTS5 is the ' +
          'authority — it is the ranker the shipped code calls.',
        rows,
      },
      null,
      1,
    ),
  );
}
d.close();
