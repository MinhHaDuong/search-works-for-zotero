// X1, the timing half (ticket 0025): what does a full vector scan cost, per layout,
// at the sizes the design must survive?
//
// Three layouts, same top-30 selection, same stored-norm dot product (norms kept beside
// the vectors so cosine needs no renormalization pass):
//   rows    — per-row BLOBs read out of SQLite, the layout upstream has today;
//   slab    — one contiguous Float32Array, the derived-sidecar layout DESIGN §2 commits to;
//   int8    — the same slab quantized to Int8 with per-vector scales, integer dot.
// The rule this feeds (DESIGN.md §3, X1): int8 ships only if recall@30 >= 0.98, pool <=
// 32x topK, AND scan+rerank <= 400 ms at 650k; the float32 slab is the permanent
// fallback. This driver measures the timing clause for all three layouts; the RECALL
// clause is deliberately not measured here — synthetic isotropic vectors cannot exhibit
// the anisotropy that decides it (bench/results/0008-real-vectors/real-93022.json says
// why), so that half runs on the workstation's 93,022 real vectors.
//
// Synthetic unit vectors, deterministic seed, dim 384 (the shipped embedder's width).
//
//   node bench/slab_scan.mjs > bench/results/0025-x1-timing/slab-vs-rows.json
import { DatabaseSync } from 'node:sqlite';
import { existsSync, unlinkSync } from 'node:fs';
import { execSync } from 'node:child_process';

const DIM = 384;
const K = 30;
const Ns = [100_000, 650_000];
const PROBES = 15;
const DBPATH = '/tmp/x1-slab-bench.sqlite';

// mulberry32 — see census_parse.mjs for why not a bare LCG.
let seed = 20260827;
function rnd() {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
function fillUnit(a, off) {
  let n = 0;
  for (let i = 0; i < DIM; i++) {
    const v = rnd() - 0.5;
    a[off + i] = v;
    n += v * v;
  }
  n = Math.sqrt(n) || 1;
  for (let i = 0; i < DIM; i++) a[off + i] /= n;
  return 1; // unit norm, stored anyway: the layout must carry it for real vectors
}

/** Keep the K best (score, id) pairs; small K makes a linear insert cheaper than a heap. */
function topK(best, score, id) {
  if (best.length === K && score <= best[K - 1].score) return;
  let i = best.length;
  while (i > 0 && best[i - 1].score < score) i--;
  best.splice(i, 0, { score, id });
  if (best.length > K) best.pop();
}

const quantiles = (times) => {
  const s = [...times].sort((a, b) => a - b);
  const at = (q) => s[Math.min(s.length - 1, Math.floor(s.length * q))];
  return { median_ms: +at(0.5).toFixed(1), p95_ms: +at(0.95).toFixed(1) };
};

const rows = [];
for (const N of Ns) {
  // The slab, its norms, and the int8 twin with per-vector scales.
  const slab = new Float32Array(N * DIM);
  const norms = new Float32Array(N);
  for (let r = 0; r < N; r++) norms[r] = fillUnit(slab, r * DIM);
  const i8 = new Int8Array(N * DIM);
  const scales = new Float32Array(N);
  for (let r = 0; r < N; r++) {
    let m = 0;
    for (let i = 0; i < DIM; i++) m = Math.max(m, Math.abs(slab[r * DIM + i]));
    const s = m / 127 || 1;
    scales[r] = s;
    for (let i = 0; i < DIM; i++) i8[r * DIM + i] = Math.round(slab[r * DIM + i] / s);
  }

  // The per-row layout: the same vectors as BLOB rows in SQLite, upstream's shape.
  for (const f of [DBPATH, `${DBPATH}-wal`, `${DBPATH}-shm`]) if (existsSync(f)) unlinkSync(f);
  const db = new DatabaseSync(DBPATH);
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('CREATE TABLE v (pid INTEGER PRIMARY KEY, norm REAL NOT NULL, vector BLOB NOT NULL)');
  const ins = db.prepare('INSERT INTO v (pid, norm, vector) VALUES (?, ?, ?)');
  db.exec('BEGIN');
  const rowBuf = Buffer.from(slab.buffer);
  for (let r = 0; r < N; r++) {
    ins.run(r, norms[r], rowBuf.subarray(r * DIM * 4, (r + 1) * DIM * 4));
    if (r % 50_000 === 0) {
      db.exec('COMMIT');
      db.exec('BEGIN');
    }
  }
  db.exec('COMMIT');

  const probes = [];
  for (let p = 0; p < PROBES + 3; p++) {
    const q = new Float32Array(DIM);
    fillUnit(q, 0);
    probes.push(q);
  }

  const scanSlab = (q) => {
    const best = [];
    for (let r = 0; r < N; r++) {
      let d = 0;
      const off = r * DIM;
      for (let i = 0; i < DIM; i++) d += q[i] * slab[off + i];
      topK(best, d / norms[r], r);
    }
    return best;
  };
  const scanInt8 = (q) => {
    const qi = new Int8Array(DIM);
    let qm = 0;
    for (let i = 0; i < DIM; i++) qm = Math.max(qm, Math.abs(q[i]));
    const qs = qm / 127 || 1;
    for (let i = 0; i < DIM; i++) qi[i] = Math.round(q[i] / qs);
    const best = [];
    for (let r = 0; r < N; r++) {
      let d = 0;
      const off = r * DIM;
      for (let i = 0; i < DIM; i++) d += qi[i] * i8[off + i];
      topK(best, (d * qs * scales[r]) / norms[r], r);
    }
    return best;
  };
  const rowStmt = db.prepare('SELECT pid, norm, vector FROM v');
  const scanRows = (q) => {
    const best = [];
    for (const row of rowStmt.iterate()) {
      const v = new Float32Array(row.vector.buffer, row.vector.byteOffset, DIM);
      let d = 0;
      for (let i = 0; i < DIM; i++) d += q[i] * v[i];
      topK(best, d / row.norm, Number(row.pid));
    }
    return best;
  };

  const variants = { rows: scanRows, slab: scanSlab, int8: scanInt8 };
  const result = { N };
  for (const [name, scan] of Object.entries(variants)) {
    for (let w = 0; w < 3; w++) scan(probes[w]); // warm
    const times = [];
    for (let p = 3; p < probes.length; p++) {
      const t = performance.now();
      scan(probes[p]);
      times.push(performance.now() - t);
    }
    result[name] = quantiles(times);
  }
  // Agreement is a sanity check on the harness, not the recall measurement.
  const a = scanSlab(probes[3]).map((b) => b.id);
  const b = scanRows(probes[3]).map((b) => b.id);
  result.slab_rows_top30_identical = JSON.stringify(a) === JSON.stringify(b);
  rows.push(result);
  db.close();
  for (const f of [DBPATH, `${DBPATH}-wal`, `${DBPATH}-shm`]) if (existsSync(f)) unlinkSync(f);
}

const out = {
  probe: 'ticket 0025 X1 (timing half) — full-scan top-30 cost per vector layout',
  rule: 'DESIGN.md §3 X1 timing clause: scan+rerank <= 400 ms at 650k; float32 slab is the permanent fallback',
  not_measured_here:
    'the recall clause (int8 recall@30 >= 0.98 at pool <= 32x topK) — synthetic isotropic ' +
    'vectors cannot exhibit the anisotropy that decides it; it runs on the workstation ' +
    'against the 93,022 real vectors (bench/results/0008-real-vectors).',
  substrate: 'SYNTHETIC unit vectors, dim 384, deterministic seed; stored-norm dot in all layouts',
  host: 'session container (weaker substrate than the workstation: a pass here is conservative)',
  cpu: execSync('grep -m1 "model name" /proc/cpuinfo').toString().split(':')[1].trim(),
  node: process.version,
  timestamp_utc: new Date().toISOString(),
  k: K,
  probes_per_variant: PROBES,
  rows,
};
console.log(JSON.stringify(out, null, 2));
