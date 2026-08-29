#!/usr/bin/env node
// Ticket 0070 — what the vector scan pays for walking each stored vector twice.
//
// Upstream's `cosine` calls `norm(b)` and then loops again for the dot product, and the
// `norm` it calls is shared with the query-side call in `vectorSearch`, which passes a
// `number[]` where every row passes a `Float32Array`. One `number[]` observation makes
// that call site polymorphic for the life of the process.
//
// Two measurements, because they answer different questions:
//
//   --shapes   the arithmetic alone, no SQLite, no I/O. Separates the two causes: a
//              monomorphic-but-still-two-pass variant sits between the two ends.
//   --insitu   the real scan, calling the SHIPPED function out of a built dist/, against
//              the two-pass implementation it replaces. This is the number to quote.
//
// Two traps this driver exists to avoid, both of which produced wrong numbers first:
//
//   * Running both implementations through one `scan(f)` call site makes THAT site
//     polymorphic and blocks inlining for both — it read 1,61x where two direct call
//     sites read 2,48x. Each variant here gets its own scan.
//   * Single runs disagree by ±15% on this workload, which is enough to invent a
//     speedup. Repetitions are interleaved so drift hits both alike, and the spread is
//     reported alongside the median so a reader can see the noise.
//
// Usage:
//   node bench/cosine_fusion.mjs --shapes [--dim 3072] [--rows 20000]
//   node bench/cosine_fusion.mjs --insitu --dist <fork>/dist --db <path> [--build --rows N]
//
// The in-situ mode needs a fixture database of float32 BLOBs shaped like a real index;
// `--build` writes one (about 13 KB per row at 3072 dimensions) and reuses it after.

import { DatabaseSync } from 'node:sqlite';
import { existsSync, statSync } from 'node:fs';

const argv = process.argv.slice(2);
const flag = (name) => argv.includes(`--${name}`);
const opt = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i === -1 ? fallback : argv[i + 1];
};

const DIM = Number(opt('dim', 3072));
const ROWS = Number(opt('rows', flag('insitu') ? 255703 : 20000));
const REPS = Number(opt('reps', 5));

/** A small LCG, so a rerun on another machine measures the same vectors. */
function lcg(seed) {
  let s = seed >>> 0;
  return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
}

function norm(v) {
  let s = 0;
  for (let i = 0; i < v.length; i++) s += v[i] * v[i];
  return Math.sqrt(s);
}

/** The implementation as it stood before the fusion. Both modes measure against this. */
function twoPass(a, b, an) {
  const bn = norm(b);
  if (bn === 0) return 0;
  let dot = 0;
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) dot += a[i] * b[i];
  return dot / (an * bn);
}

function stat(times) {
  const s = [...times].sort((x, y) => x - y);
  return { median_ms: s[Math.floor(s.length / 2)], min_ms: s[0], max_ms: s[s.length - 1] };
}

const perRow = (ms, n) => (ms * 1000) / n;

// ---------------------------------------------------------------- --shapes

function shapes() {
  const rnd = lcg(7);
  const q = Array.from({ length: DIM }, () => rnd() - 0.5);
  const rows = Array.from({ length: ROWS }, () => Float32Array.from({ length: DIM }, () => rnd() - 0.5));
  const qn = norm(q);

  // Monomorphic twin of `norm`: only ever sees Float32Array. The isolation that separates
  // the polymorphic call site from the redundant traversal.
  function normF32(v) {
    let s = 0;
    for (let i = 0; i < v.length; i++) s += v[i] * v[i];
    return Math.sqrt(s);
  }
  function twoPassMono(a, b, an) {
    const bn = normF32(b);
    if (bn === 0) return 0;
    let dot = 0;
    const len = Math.min(a.length, b.length);
    for (let i = 0; i < len; i++) dot += a[i] * b[i];
    return dot / (an * bn);
  }
  function fused(a, b, an) {
    let dot = 0;
    let sq = 0;
    for (let i = 0; i < b.length; i++) {
      const x = b[i];
      dot += a[i] * x;
      sq += x * x;
    }
    const bn = Math.sqrt(sq);
    return bn === 0 ? 0 : dot / (an * bn);
  }
  norm(q); // the number[] observation that makes `norm` polymorphic, as upstream does

  const run = (f) => {
    for (let w = 0; w < 2; w++) for (const b of rows) f(q, b, qn);
    const t = [];
    for (let r = 0; r < REPS; r++) {
      const t0 = process.hrtime.bigint();
      let acc = 0;
      for (const b of rows) acc += f(q, b, qn);
      t.push(Number(process.hrtime.bigint() - t0) / 1e6);
      if (!Number.isFinite(acc)) throw new Error('non-finite accumulator');
    }
    return stat(t);
  };

  const a = run(twoPass), b = run(twoPassMono), c = run(fused);
  return {
    mode: 'shapes',
    dim: DIM,
    rows: ROWS,
    reps: REPS,
    node: process.version,
    two_pass_shared_norm: { ...a, us_per_row: perRow(a.median_ms, ROWS) },
    two_pass_monomorphic_norm: { ...b, us_per_row: perRow(b.median_ms, ROWS) },
    fused: { ...c, us_per_row: perRow(c.median_ms, ROWS) },
    speedup_total: a.median_ms / c.median_ms,
    speedup_from_monomorphism: a.median_ms / b.median_ms,
    speedup_from_fusion: b.median_ms / c.median_ms,
  };
}

// ---------------------------------------------------------------- --insitu

function buildFixture(path) {
  const db = new DatabaseSync(path);
  db.exec('PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF');
  // The real schema: `vector` is the last column, after the passage text.
  db.exec(`CREATE TABLE passages (pid INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE,
           item_key TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
           source TEXT, vector BLOB)`);
  const ins = db.prepare('INSERT INTO passages (id, item_key, title, text, source, vector) VALUES (?,?,?,?,?,?)');
  const rnd = lcg(13);
  const body = 'the quick brown fox considers the epistemic status of its own embedding '.repeat(12).slice(0, 800);
  db.exec('BEGIN');
  const v = new Float32Array(DIM);
  for (let r = 0; r < ROWS; r++) {
    for (let i = 0; i < DIM; i++) v[i] = rnd() - 0.5;
    ins.run(`p${r}`, `IT${r % 10000}`, `title ${r}`, `${r} ${body}`, 'fulltext', Buffer.from(v.buffer.slice(0)));
  }
  db.exec('COMMIT');
  db.close();
}

/** Float32 view over a BLOB, copying only when unaligned — upstream's own `toFloats`. */
function toFloats(buf) {
  return buf.byteOffset % 4 === 0
    ? new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
    : new Float32Array(buf.slice().buffer);
}

async function insitu() {
  const dist = opt('dist', null);
  const dbPath = opt('db', null);
  if (!dist || !dbPath) throw new Error('--insitu needs --dist <fork>/dist and --db <path>');
  if (!existsSync(dbPath)) {
    if (!flag('build')) throw new Error(`no fixture at ${dbPath}; pass --build to write one`);
    buildFixture(dbPath);
  }
  const { cosine } = await import(`${dist}/features/search/sqlite-index.js`);

  const db = new DatabaseSync(dbPath);
  const stmt = db.prepare('SELECT id, vector FROM passages WHERE vector IS NOT NULL');
  const rnd = lcg(31);
  const q = Array.from({ length: DIM }, () => rnd() - 0.5);
  const qn = norm(q);
  const topK = 15;

  // Equivalence over the whole store, not a fixture: the change claims bit-identity.
  let checked = 0, mismatches = 0;
  for (const row of stmt.iterate()) {
    const b = toFloats(row.vector);
    if (!Object.is(cosine(q, b, qn), twoPass(q, b, qn))) mismatches++;
    checked++;
  }

  const push = (top, id, score) => {
    if (score <= 0) return;
    if (top.length >= topK && score <= top[top.length - 1].score) return;
    let i = top.length;
    while (i > 0 && top[i - 1].score < score) i--;
    top.splice(i, 0, { id, score });
    if (top.length > topK) top.pop();
  };
  // Two scans, each with ONE callee at its call site. See the header.
  const scanBefore = () => { const t = []; for (const r of stmt.iterate()) push(t, r.id, twoPass(q, toFloats(r.vector), qn)); return t; };
  const scanAfter = () => { const t = []; for (const r of stmt.iterate()) push(t, r.id, cosine(q, toFloats(r.vector), qn)); return t; };
  // The marshalling floor: iterate and decode, no arithmetic at all.
  const scanFloor = () => { let a = 0; for (const r of stmt.iterate()) a += toFloats(r.vector)[0]; return a; };

  scanBefore(); scanAfter(); scanFloor();
  const tb = [], ta = [];
  for (let r = 0; r < REPS; r++) {
    let t0 = process.hrtime.bigint(); scanBefore(); tb.push(Number(process.hrtime.bigint() - t0) / 1e6);
    t0 = process.hrtime.bigint(); scanAfter(); ta.push(Number(process.hrtime.bigint() - t0) / 1e6);
  }
  const tf = [];
  for (let r = 0; r < REPS; r++) { const t0 = process.hrtime.bigint(); scanFloor(); tf.push(Number(process.hrtime.bigint() - t0) / 1e6); }

  const before = stat(tb), after = stat(ta), floor = stat(tf);
  const rb = scanBefore(), ra = scanAfter();
  const rankingIdentical = rb.length === ra.length && rb.every((h, i) => h.id === ra[i].id && Object.is(h.score, ra[i].score));

  return {
    mode: 'insitu',
    dim: DIM,
    rows: ROWS,
    reps: REPS,
    node: process.version,
    fixture_bytes: statSync(dbPath).size,
    equivalence: { rows_checked: checked, mismatches, top15_ranking_identical: rankingIdentical },
    two_pass: { ...before, us_per_row: perRow(before.median_ms, ROWS) },
    fused: { ...after, us_per_row: perRow(after.median_ms, ROWS) },
    marshalling_floor: { ...floor, us_per_row: perRow(floor.median_ms, ROWS) },
    speedup_median: before.median_ms / after.median_ms,
    speedup_worst_case: before.min_ms / after.max_ms,
  };
}

const result = flag('insitu') ? await insitu() : shapes();
console.log(JSON.stringify(result, null, 2));
