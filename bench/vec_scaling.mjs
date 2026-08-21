// Does sqlite-vec's vec0 KNN scale sub-linearly? It does not: this sweep is what
// established the flat ~141 ms per 100 000 vectors behind ticket 0008. Synthetic
// unit-norm vectors, deterministic seed, file-backed, warm, median of 25 probes.
//
//   npm i sqlite-vec && node bench/vec_scaling.mjs
//
// Needs Node >= 22.5 for node:sqlite. Writes and deletes bench.sqlite in cwd.
import { DatabaseSync } from 'node:sqlite';
import * as sv from 'sqlite-vec';
import { existsSync, unlinkSync, statSync } from 'node:fs';

const DIM = 384;
const K = 30;
const Ns = [10000, 25000, 50000, 100000, 200000, 400000];

// deterministic unit vectors
let seed = 12345;
const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff - 0.5; };
function vec() {
  const a = new Float32Array(DIM);
  let n = 0;
  for (let i = 0; i < DIM; i++) { a[i] = rnd(); n += a[i] * a[i]; }
  n = Math.sqrt(n);
  for (let i = 0; i < DIM; i++) a[i] /= n;
  return a;
}
const blob = (a) => new Uint8Array(a.buffer.slice(0));

const path = 'bench.sqlite';
console.log(`dim=${DIM} k=${K}`);
console.log('N\tinsert_s\tdb_MB\tmedian_ms\tp90_ms\tms_per_100k');

for (const N of Ns) {
  for (const f of [path, path + '-wal', path + '-shm']) if (existsSync(f)) unlinkSync(f);
  const db = new DatabaseSync(path, { allowExtension: true });
  db.enableLoadExtension(true); sv.load(db); db.enableLoadExtension(false);
  db.exec('PRAGMA journal_mode=WAL');
  db.exec(`CREATE VIRTUAL TABLE v USING vec0(embedding float[${DIM}])`);
  const ins = db.prepare('INSERT INTO v(rowid, embedding) VALUES (?,?)');
  const t0 = performance.now();
  db.exec('BEGIN');
  for (let i = 1; i <= N; i++) {
    ins.run(BigInt(i), blob(vec()));
    if (i % 20000 === 0) { db.exec('COMMIT'); db.exec('BEGIN'); }
  }
  db.exec('COMMIT');
  const insert = (performance.now() - t0) / 1000;

  const q = db.prepare(`SELECT rowid, distance FROM v WHERE embedding MATCH ? AND k = ${K} ORDER BY distance`);
  const probes = Array.from({ length: 25 }, () => blob(vec()));
  for (let i = 0; i < 5; i++) q.all(probes[i]);       // warm
  const times = [];
  for (const p of probes) { const t = performance.now(); q.all(p); times.push(performance.now() - t); }
  times.sort((a, b) => a - b);
  const med = times[Math.floor(times.length / 2)];
  const p90 = times[Math.floor(times.length * 0.9)];
  const mb = statSync(path).size / 2 ** 20;
  console.log(`${N}\t${insert.toFixed(1)}\t${mb.toFixed(0)}\t${med.toFixed(2)}\t${p90.toFixed(2)}\t${(med / N * 100000).toFixed(2)}`);
  db.close();
}
for (const f of [path, path + '-wal', path + '-shm']) if (existsSync(f)) unlinkSync(f);
