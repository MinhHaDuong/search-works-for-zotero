/**
 * The feature's whole point, verified on the real 477 512-passage index: an unaccented
 * query must still reach the accented documents. Stock reaches them by folding the index;
 * arm B must reach them by expansion. For each unaccented query, compare arm B's hits
 * (and arm A's) against stock's — and check directly that the accented spelling occurs in
 * the passages arm B returns. Also runs PR 1's degenerate cases through each arm.
 */
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';

const silent = { debug() {}, info() {}, warn() {}, error() {} };
const arms = [
  { arm: 'stock', dist: './dists/stock', index: './idx-stock.sqlite' },
  { arm: 'armA', dist: './dists/armA', index: './idx-armA.sqlite' },
  { arm: 'armB', dist: './dists/armB', index: './idx-armB2.sqlite' },
];
for (const a of arms) {
  const { SqliteSearchIndex } = await import(`${a.dist}/features/search/sqlite-index.js`);
  a.idx = new SqliteSearchIndex({ embedder: null, logger: silent, path: a.index });
  await a.idx.open();
}

// Unaccented spellings of accented content, FR and VI. Each names a term whose accented
// form dominates this library (probe_df) — the population expansion exists for.
const reachQueries = [
  { q: 'theorie generale', accented: 'théorie' },
  { q: 'modele d equilibre', accented: 'modèle' },
  { q: 'developpement durable', accented: 'développement' },
  { q: 'nang luong tai tao', accented: 'năng lượng' },
  { q: 'phat trien ben vung', accented: 'phát triển' },
  { q: 'dien luc viet nam', accented: 'điện lực' },
  { q: 'marche de l electricite', accented: 'marché' },
  { q: 'cout social du carbone', accented: 'coût' },
  { q: 'eleve applique', accented: 'élève' },
  { q: 'economie de l energie', accented: 'économie' },
];
const degenerate = ['to be or not to be', 'the', 'thé', 'of the'];

const text = new DatabaseSync('./idx-armB2.sqlite', { readOnly: true });
const passagesOf = text.prepare('SELECT text FROM passages WHERE item_key = ?');

const out = { reach: [], degenerate: [] };
for (const rq of reachQueries) {
  const row = { query: rq.q, accented: rq.accented };
  for (const a of arms) {
    const hits = await a.idx.query(rq.q, { limit: 10, mode: 'keyword' });
    row[a.arm] = hits.map((h) => h.itemKey);
  }
  const inter = row.armB.filter((k) => row.stock.includes(k)).length;
  row.armB_stock_overlap10 = inter;
  // Direct evidence: how many of arm B's top-10 items actually carry the accented form.
  row.armB_hits_with_accented_form = row.armB.filter((k) =>
    passagesOf.all(k).some((p) => p.text.toLowerCase().normalize('NFC').includes(rq.accented)),
  ).length;
  out.reach.push(row);
}
for (const q of degenerate) {
  const row = { query: q };
  for (const a of arms) {
    const t0 = performance.now();
    const hits = await a.idx.query(q, { limit: 20, mode: 'keyword' });
    row[a.arm] = { n: hits.length, ms: +(performance.now() - t0).toFixed(1), top3: hits.slice(0, 3).map((h) => h.itemKey) };
  }
  out.degenerate.push(row);
}
text.close();
for (const a of arms) await a.idx.close();
writeFileSync('reach.json', JSON.stringify(out, null, 1));
for (const r of out.reach)
  console.log(r.query.padEnd(28), 'overlap', r.armB_stock_overlap10, '/10  accented-in-hits', r.armB_hits_with_accented_form, '/10');
for (const r of out.degenerate) console.log(r.query.padEnd(28), JSON.stringify(Object.fromEntries(['stock', 'armA', 'armB'].map((k) => [k, [r[k].n, r[k].ms]]))));
