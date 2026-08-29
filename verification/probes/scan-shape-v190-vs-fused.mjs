// Which shape does `sqlite_float32` in bench/vec_scan_shapes.mjs actually measure?
//
// That candidate is labelled "what v1.9.0 does", and the figure derived from it — 4 088,7 ms
// — is what upstream issue #30's comment D quoted as the 1x baseline, and what the "more
// than twenty" gap to the reporter's ~95 s was computed against. But its loop accumulates
// the dot product and the row norm in ONE traversal, with no `norm()` function to share
// between the query side and the row side. That is the shape upstream PR #31 CREATED. What
// v1.9.0 ran was two traversals per row through a `norm()` whose call site saw a number[]
// from the query and a Float32Array from every row, and so stayed polymorphic for the life
// of the process — the defect #31 removed, measured at 2,19x in ticket 0070.
//
// Two committed artifacts therefore disagree about the same quantity (4,9 s in
// 0025-x1-recall/scan-shapes-255703x3072.json, 8,6 s in 0070-cosine-fusion/insitu-255703.json),
// and they were produced by different drivers on different fixtures, so neither settles it
// against the other. This probe measures all three shapes in ONE process over ONE SQLite
// table, so the ratio is a measurement rather than a division across runs.
//
// Ratios transfer, absolutes do not: N is reduced so this costs a minute, and per-row cost
// is what is being compared.
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync, rmSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { cpus, hostname, loadavg, totalmem, freemem } from 'node:os';

const { values: opt } = parseArgs({
  options: {
    n: { type: 'string', default: '40000' },
    dim: { type: 'string', default: '3072' },
    reps: { type: 'string', default: '5' },
    db: { type: 'string' },
    output: { type: 'string' },
  },
});
if (!opt.output || !opt.db) {
  console.error('usage: node verification/probes/scan-shape-v190-vs-fused.mjs --db <scratch.sqlite> --output <f.json>');
  process.exit(2);
}
const N = Number(opt.n);
const DIM = Number(opt.dim);
const REPS = Number(opt.reps);

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(20260829);

const query = new Float32Array(DIM);
for (let i = 0; i < DIM; i++) query[i] = rnd() - 0.5;
// Upstream hands cosine() a number[], never a typed array. That is half the defect.
const queryArr = Array.from(query);

/**
 * v1.9.0's norm(), shared by both call sites. Reached with a number[] once per query and a
 * Float32Array once per row, which is what keeps it polymorphic.
 */
function sharedNorm(v) {
  let s = 0;
  for (let i = 0; i < v.length; i++) s += v[i] * v[i];
  return Math.sqrt(s);
}

/** The same arithmetic, never reached with anything but a Float32Array. */
function monoNorm(v) {
  let s = 0;
  for (let i = 0; i < v.length; i++) s += v[i] * v[i];
  return Math.sqrt(s);
}

rmSync(opt.db, { force: true });
rmSync(`${opt.db}-wal`, { force: true });
rmSync(`${opt.db}-shm`, { force: true });
const db = new DatabaseSync(opt.db);
db.exec('PRAGMA journal_mode = WAL');
db.exec('CREATE TABLE passages(id TEXT PRIMARY KEY, vector BLOB)');
const ins = db.prepare('INSERT INTO passages(id, vector) VALUES (?, ?)');
const row = new Float32Array(DIM);
db.exec('BEGIN');
for (let r = 0; r < N; r++) {
  for (let i = 0; i < DIM; i++) row[i] = rnd() - 0.5;
  ins.run(`p${r}`, Buffer.from(row.buffer.slice(0)));
}
db.exec('COMMIT');

const toFloats = (buf) =>
  buf.byteOffset % 4 === 0
    ? new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
    : new Float32Array(buf.slice().buffer);

const st = db.prepare('SELECT id, vector FROM passages WHERE vector IS NOT NULL');

const candidates = [
  {
    name: 'v190_two_pass_shared_norm',
    note: 'what v1.9.0 ran: two traversals per row, norm() shared with the query-side call',
    run: () => {
      const qn = sharedNorm(queryArr);
      let best = -2;
      for (const r of st.iterate()) {
        const b = toFloats(r.vector);
        let d = 0;
        for (let i = 0; i < DIM; i++) d += queryArr[i] * b[i];
        const c = d / (qn * sharedNorm(b));
        if (c > best) best = c;
      }
      return best;
    },
  },
  {
    name: 'two_pass_monomorphic_norm',
    note: 'two traversals still, but norm() sees only Float32Array — isolates polymorphism',
    run: () => {
      const qn = sharedNorm(queryArr);
      let best = -2;
      for (const r of st.iterate()) {
        const b = toFloats(r.vector);
        let d = 0;
        for (let i = 0; i < DIM; i++) d += queryArr[i] * b[i];
        const c = d / (qn * monoNorm(b));
        if (c > best) best = c;
      }
      return best;
    },
  },
  {
    name: 'fused_inline',
    note: "what bench/vec_scan_shapes.mjs measures and labels 'v1.9.0 shape', and what PR #31 shipped",
    run: () => {
      const qn = sharedNorm(queryArr);
      let best = -2;
      for (const r of st.iterate()) {
        const b = toFloats(r.vector);
        let d = 0;
        let s = 0;
        for (let i = 0; i < DIM; i++) {
          const v = b[i];
          d += queryArr[i] * v;
          s += v * v;
        }
        const c = d / (qn * Math.sqrt(s));
        if (c > best) best = c;
      }
      return best;
    },
  },
];

// Round robin, so a transient cannot land inside one candidate.
const times = new Map(candidates.map((c) => [c.name, []]));
const values = new Map();
for (const c of candidates) c.run();
for (let rep = 0; rep < REPS; rep++) {
  for (const c of candidates) {
    const t0 = performance.now();
    const v = c.run();
    times.get(c.name).push(performance.now() - t0);
    values.set(c.name, v);
  }
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

const results = candidates.map((c) => {
  const ts = times.get(c.name);
  return {
    name: c.name,
    note: c.note,
    median_ms: Number(median(ts).toFixed(1)),
    min_ms: Number(Math.min(...ts).toFixed(1)),
    max_ms: Number(Math.max(...ts).toFixed(1)),
    us_per_row: Number(((median(ts) * 1000) / N).toFixed(3)),
  };
});
const base = results.find((r) => r.name === 'v190_two_pass_shared_norm').median_ms;
for (const r of results) r.speedup_vs_v190 = Number((base / r.median_ms).toFixed(2));

// Every shape computes the same cosine, so a divergence here would invalidate the timings.
const distinct = new Set([...values.values()].map((v) => v.toFixed(9)));

writeFileSync(
  opt.output,
  JSON.stringify(
    {
      what: "which shape bench/vec_scan_shapes.mjs's sqlite_float32 candidate actually measures",
      when: new Date().toISOString(),
      geometry: { vectors: N, dim: DIM },
      reps: REPS,
      vectors_are: 'SYNTHETIC — scan latency depends on shape, not on meaning',
      equivalence: { distinct_results: distinct.size, agree: distinct.size === 1 },
      results,
      machine: {
        host: hostname(),
        cpus: cpus().length,
        cpu_model: cpus()[0]?.model,
        total_mem_bytes: totalmem(),
        free_mem_bytes_at_start: freemem(),
        loadavg: loadavg(),
        node: process.version,
      },
    },
    null,
    2,
  ) + '\n',
);
for (const r of results) {
  console.log(r.name.padEnd(28), String(r.median_ms).padStart(9), 'ms', String(r.us_per_row).padStart(8), 'us/row', `${r.speedup_vs_v190}x`);
}
console.log('equivalence:', distinct.size === 1 ? 'all shapes agree' : `DIVERGED (${distinct.size} distinct)`);
db.close();
rmSync(opt.db, { force: true });
rmSync(`${opt.db}-wal`, { force: true });
rmSync(`${opt.db}-shm`, { force: true });
