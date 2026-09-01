/**
 * What the droplist derivation costs, measured rather than inherited.
 *
 * Two numbers were circulating for this scan — ~3,4 s and ~2,0 s — and one of them was
 * labelled "cold" while having been taken against a page cache the preceding work had
 * already warmed. A figure that appears in a code comment and in an upstream PR body has
 * to be one number, taken one way, with the warmth stated.
 *
 * Cold is NOT measured here and is not measurable without dropping the page cache, which
 * needs root. Every figure below is warm, and the first call is reported separately from
 * the rest precisely so the reader can see how little the "first" call means once the file
 * has been read at all.
 */
import { DatabaseSync } from 'node:sqlite';

const dbPath = process.argv[2];
const runs = Number(process.argv[3] ?? 5);
const out = { index: dbPath, runs: [], warmth: 'warm — the page cache is not dropped; cold is unmeasured' };

for (let i = 0; i < runs; i++) {
  const db = new DatabaseSync(dbPath, { readOnly: true });
  const passages = db.prepare('SELECT count(*) AS n FROM passages').get().n;
  db.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main', 'passages_fts', 'row')");
  const floor = Math.ceil(passages * 0.3);
  const t0 = performance.now();
  const rows = db.prepare('SELECT term FROM temp.v WHERE doc >= ?').all(floor);
  const ms = performance.now() - t0;
  const t1 = performance.now();
  const total = db.prepare('SELECT count(*) AS n FROM temp.v').get().n;
  const msAll = performance.now() - t1;
  const terms = rows.map((r) => r.term).sort();
  const stored = terms.join(' ');
  out.runs.push({ run: i, scanMs: +ms.toFixed(1), countAllMs: +msAll.toFixed(1), vocabTerms: total, passages, droplist: terms.length, storedBytes: Buffer.byteLength(stored, 'utf8') });
  if (i === 0) out.terms = terms;
  db.close();
}
const scans = out.runs.map((r) => r.scanMs);
out.summary = { first: scans[0], median: scans.slice().sort((a, b) => a - b)[Math.floor(scans.length / 2)], min: Math.min(...scans), max: Math.max(...scans) };
console.log(JSON.stringify(out, null, 2));
