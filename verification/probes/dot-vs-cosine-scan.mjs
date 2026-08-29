#!/usr/bin/env node
// What would the scan save by trusting stored vectors to be unit length?
//
// The shipped `cosine(a, b, an)` fuses two accumulators into one traversal: the dot
// product, and the row's own squared length, so it can divide by `an * bn` at the end.
// If every stored vector were known to be normalised, `bn` is 1 and the whole `sq`
// accumulator plus the sqrt and one divide disappear — the scan becomes a bare dot
// product. That is a real option (transformers.js is already asked for
// `normalize: true`), so the question is what it buys.
//
// This measures the ARITHMETIC AND MEMORY of the scan alone: no SQLite, no BLOB decode,
// no row iteration. That makes it an UPPER BOUND on the achievable gain rather than an
// estimate of it — in situ those costs are paid per row either way and dilute whatever
// this shows. A small number here is therefore conclusive downward, which is the
// direction worth being sure about.
//
// Two traps inherited from bench/cosine_fusion.mjs, whose discipline this follows:
//
//   * Each variant gets its OWN scan loop. Running both through one higher-order call
//     site makes that site polymorphic and blocks inlining for both, which reads as a
//     smaller difference than either variant really has.
//   * Single runs on this workload disagree by well over 10%. Repetitions are
//     INTERLEAVED so drift hits both variants alike, and the spread is reported beside
//     the median so a reader can see the noise rather than take the ratio on faith.
//
// Usage:
//   node dot-vs-cosine-scan.mjs [--dim 3072] [--rows 20000] [--reps 9]

const argv = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i === -1 ? fallback : argv[i + 1];
};

const DIM = Number(opt('dim', 3072));
const ROWS = Number(opt('rows', 20000));
const REPS = Number(opt('reps', 9));

/** Deterministic source, so a re-run measures the same numbers rather than new ones. */
function lcg(seed) {
  let s = seed >>> 0;
  return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
}

function stat(times) {
  const t = [...times].sort((x, y) => x - y);
  const at = (q) => t[Math.min(t.length - 1, Math.floor(t.length * q))];
  return {
    median_ms: Number(at(0.5).toFixed(3)),
    min_ms: Number(t[0].toFixed(3)),
    max_ms: Number(t[t.length - 1].toFixed(3)),
    spread_pct: Number((((t[t.length - 1] - t[0]) / at(0.5)) * 100).toFixed(1)),
  };
}

const rnd = lcg(7);
const query = Array.from({ length: DIM }, () => rnd() - 0.5);
// Unit rows, because that is the premise the dot-only variant runs on. Normalising them
// also keeps the two variants numerically comparable rather than merely time-comparable.
const rows = Array.from({ length: ROWS }, () => {
  const v = Float32Array.from({ length: DIM }, () => rnd() - 0.5);
  let s = 0;
  for (let i = 0; i < v.length; i++) s += v[i] * v[i];
  const n = Math.sqrt(s);
  for (let i = 0; i < v.length; i++) v[i] /= n;
  return v;
});
let qn = 0;
for (const x of query) qn += x * x;
qn = Math.sqrt(qn);

// --- the two scans, each with its own call site -----------------------------------

/** The shipped shape: one traversal, two accumulators, then the division. */
function scanCosine() {
  let acc = 0;
  for (const b of rows) {
    let dot = 0;
    let sq = 0;
    for (let i = 0; i < b.length; i++) {
      const x = b[i];
      dot += query[i] * x;
      sq += x * x;
    }
    const bn = Math.sqrt(sq);
    acc += bn === 0 ? 0 : dot / (qn * bn);
  }
  return acc;
}

/** The variant that trusts the rows: dot product only, no sq, no sqrt, one divide saved. */
function scanDot() {
  let acc = 0;
  for (const b of rows) {
    let dot = 0;
    for (let i = 0; i < b.length; i++) dot += query[i] * b[i];
    acc += dot / qn;
  }
  return acc;
}

// --- interleaved measurement -------------------------------------------------------

for (let w = 0; w < 3; w++) {
  scanCosine();
  scanDot();
}

const tCos = [];
const tDot = [];
let sink = 0;
for (let r = 0; r < REPS; r++) {
  let t0 = process.hrtime.bigint();
  sink += scanCosine();
  tCos.push(Number(process.hrtime.bigint() - t0) / 1e6);

  t0 = process.hrtime.bigint();
  sink += scanDot();
  tDot.push(Number(process.hrtime.bigint() - t0) / 1e6);
}
if (!Number.isFinite(sink)) throw new Error('non-finite accumulator');

const cos = stat(tCos);
const dot = stat(tDot);
const perRow = (ms) => Number(((ms * 1000) / ROWS).toFixed(3));

console.log(
  JSON.stringify(
    {
      probe: 'dot-vs-cosine-scan',
      what: 'upper bound on what the vector scan saves by trusting stored vectors to be unit length',
      caveat: 'arithmetic and memory only — no SQLite, no BLOB decode, no row iteration',
      dim: DIM,
      rows: ROWS,
      reps: REPS,
      node: process.version,
      bytes_scanned_mb: Number(((ROWS * DIM * 4) / 1048576).toFixed(1)),
      cosine: { ...cos, us_per_row: perRow(cos.median_ms) },
      dot_only: { ...dot, us_per_row: perRow(dot.median_ms) },
      speedup: Number((cos.median_ms / dot.median_ms).toFixed(3)),
    },
    null,
    1,
  ),
);
