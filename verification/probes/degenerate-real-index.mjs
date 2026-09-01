/**
 * Does the fallback actually retrieve the right document on a real index, and what does a
 * bare common word now cost?
 *
 * Two questions a ten-item fixture cannot answer, both raised in review of the split PR.
 *
 * **The outcome, not the plumbing.** The fixture asserts that the raw token set reaches
 * MATCH. It does not assert that the right document wins, and at N = 10 it cannot: FTS5
 * clamps a term's idf once its document frequency passes half the corpus, so on a real
 * index the terms the fallback adds may carry so little weight that the accidental
 * survivor still dominates the ranking. If that happens the fix is cosmetic — the query
 * stops being a one-term OR and goes on returning the same wrong page.
 *
 * **The bare word.** Stock returns `[]` instantly for a query of one listed word, because
 * tokenize emptied it before the guard. Falling back to the raw set replaces that free
 * empty answer with a full posting-list walk over the most common term in the corpus, and
 * the fold makes it reachable from real words in other languages: `thé` folds to `the`.
 *
 * Both are measured here against the real index, per arm, through each arm's own build.
 */
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const silent = { debug() {}, info() {}, warn() {}, error() {} };
const arms = (args.arms ?? 'stock,fallback,droplist,none').split(',');

const meta = new DatabaseSync(args.index, { readOnly: true });
const passages = meta.prepare('SELECT count(*) AS n FROM passages').get().n;
meta.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main', 'passages_fts', 'row')");
const dfStmt = meta.prepare('SELECT doc FROM temp.v WHERE term = ?');
const df = (t) => dfStmt.get(t)?.doc ?? 0;

const PROBES = [
  { id: 'soliloquy', q: 'to be or not to be', why: 'the motivating query: every word common, one accidental survivor' },
  { id: 'bare-the', q: 'the', why: 'one listed word alone — stock answers [] for free' },
  { id: 'bare-the-accented', q: 'thé', why: 'French for tea; folds to `the`, so it reaches the same path' },
  { id: 'of-the', q: 'of the', why: 'two listed words — must still fall back' },
  { id: 'the-brain', q: 'the brain', why: 'one common word, one rare content word — the over-fire case' },
  { id: 'of-energy', q: 'of energy', why: 'one common word, one COMMON content word (26,2%)' },
  { id: 'etre-ou-ne-pas-etre', q: 'être ou ne pas être', why: 'the French degenerate query — no English list touches it' },
];

const out = { index: args.index, passages, probes: [], df: {} };
for (const p of PROBES) {
  for (const t of new Set((p.q.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []))) {
    if (t.length > 1) out.df[t] = { doc: df(t), pct: +((100 * df(t)) / passages).toFixed(2), idfClamped: df(t) > passages / 2 };
  }
}
meta.close();

for (const arm of arms) {
  const root = `${args.dists}/${arm}/features/search`;
  const { SqliteSearchIndex } = await import(`${root}/sqlite-index.js`);
  const index = new SqliteSearchIndex({ embedder: null, logger: silent, path: args.index });
  await index.open();
  for (const p of PROBES) {
    // Two passes; the first warms whatever this query touches, the second is reported.
    await index.query(p.q, { limit: 10, mode: 'keyword' });
    const t0 = performance.now();
    const hits = await index.query(p.q, { limit: 10, mode: 'keyword' });
    const ms = +(performance.now() - t0).toFixed(1);
    out.probes.push({
      arm,
      id: p.id,
      query: p.q,
      why: p.why,
      ms,
      n: hits.length,
      // Item keys only. A committed artifact addresses a library document, it does not
      // name it or quote it (spec/DECISIONS.md, 2026-08-31) — and a probe that records a
      // title is how that rule gets broken by accident.
      top: hits.slice(0, 5).map((h) => h.itemKey),
    });
  }
  await index.close();
}

writeFileSync(args.out, JSON.stringify(out, null, 1));
for (const p of PROBES) {
  console.log(`\n### ${p.id}  "${p.q}"  — ${p.why}`);
  for (const r of out.probes.filter((x) => x.id === p.id)) {
    console.log(`  ${r.arm.padEnd(9)} ${String(r.ms).padStart(7)} ms  n=${String(r.n).padStart(2)}  top: ${r.top.slice(0, 3).join(' ')}`);
  }
}
console.log('\n### document frequency of the probe terms');
for (const [t, v] of Object.entries(out.df).sort((a, b) => b[1].doc - a[1].doc)) {
  console.log(`  ${t.padEnd(10)} ${String(v.doc).padStart(7)}  ${String(v.pct).padStart(6)}%  ${v.idfClamped ? 'idf CLAMPED (df > N/2)' : ''}`);
}
