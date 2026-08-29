// What a semantic query costs at upstream #30's geometry, by representation.
//
// #30 reports 90-105 s per query over 255 703 passages at 3 072 dimensions. Every figure
// here is measured at THAT geometry on one Linux machine, so the ratios transfer and the
// absolute numbers do not — and the gap between this machine's exact scan and the reported
// 95 s is left as an open question rather than attributed to a cause nothing here measured.
//
// Vectors are synthetic, deliberately. Scan time depends on the SHAPE of the data (how many
// vectors, how many bytes each, what arithmetic per byte) and not on what the numbers mean,
// so synthetic vectors measure latency honestly. They would NOT measure recall honestly,
// which is why recall lives in vec_mrl_recall.mjs against real embeddings and never here.
//
// The shapes, in the order the argument needs them:
//
//   sqlite_float32   what v1.9.0 does: one BLOB per row out of SQLite, decoded to a
//                    Float32Array, cosine with the row norm recomputed every query.
//   sqlite_prenorm   the same, with the row norm stored instead of recomputed. The
//                    difference is one full pass over 3 072 floats per row, per query,
//                    over a value that cannot change.
//   memory_float32   issue #30's option 2: the same exact arithmetic with the vectors
//                    already decoded and contiguous in RAM. Exact, no recall cost, and it
//                    is the upper bound on what "cache the vectors" alone can buy.
//   binary_3072      1-bit codes at full width, Hamming by SWAR popcount over Uint32Array.
//   binary_768       1-bit codes over a Matryoshka 768-prefix: both axes at once.
//
// The BigInt shape is measured too, and it is not a strawman: it is the obvious way to
// write a Hamming distance in JavaScript, and writing it that way makes the whole approach
// SLOWER than the exact scan it replaces. That result is the reason this file exists
// separately from the recall driver — a correct design lost by an implementation detail is
// still lost.
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync, rmSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { cpus, hostname, loadavg, totalmem, freemem } from 'node:os';

const { values: opt } = parseArgs({
  options: {
    n: { type: 'string', default: '255703' },
    dim: { type: 'string', default: '3072' },
    mrl: { type: 'string', default: '768' },
    reps: { type: 'string', default: '9' },
    db: { type: 'string' },
    output: { type: 'string' },
    shapes: { type: 'string', default: 'sqlite_float32,sqlite_prenorm,binary_3072,binary_768,bigint_3072' },
  },
});
if (!opt.output || !opt.db) {
  console.error('usage: node bench/vec_scan_shapes.mjs --db <scratch.sqlite> --output <f.json> [--shapes ...]');
  process.exit(2);
}
const N = Number(opt.n);
const DIM = Number(opt.dim);
const MRL = Number(opt.mrl);
const REPS = Number(opt.reps);
const WANT = new Set(opt.shapes.split(',').map((s) => s.trim()));

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
const queryArr = Array.from(query); // upstream hands cosine() a number[], not a typed array
let qn = 0;
for (let i = 0; i < DIM; i++) qn += query[i] * query[i];
qn = Math.sqrt(qn);

function popcount32(x) {
  x -= (x >>> 1) & 0x55555555;
  x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
  x = (x + (x >>> 4)) & 0x0f0f0f0f;
  return (Math.imul(x, 0x01010101) >>> 24);
}

const candidates = [];
const bytes = {};

// ---- the SQLite shapes ----------------------------------------------------------------
if (WANT.has('sqlite_float32') || WANT.has('sqlite_prenorm')) {
  rmSync(opt.db, { force: true });
  const db = new DatabaseSync(opt.db);
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('CREATE TABLE passages(id TEXT PRIMARY KEY, vector BLOB, norm REAL)');
  const ins = db.prepare('INSERT INTO passages VALUES(?,?,?)');
  const row = new Float32Array(DIM);
  db.exec('BEGIN');
  for (let r = 0; r < N; r++) {
    // A fresh pattern per row, cheaply: a constant blob would let the page cache and the
    // branch predictor see a corpus no real library has.
    let s = 0;
    for (let i = 0; i < DIM; i++) {
      const v = ((r * 2654435761 + i * 40503) % 2048) / 2048 - 0.5;
      row[i] = v;
      s += v * v;
    }
    ins.run(`p${r}`, Buffer.from(row.buffer.slice(0)), Math.sqrt(s));
  }
  db.exec('COMMIT');
  // Both SQLite shapes read the whole vector column; name each one, because a shape that
  // reports null for bytes it demonstrably reads is only marginally better than the
  // neighbour's figure this used to substitute.
  bytes.sqlite_float32 = N * DIM * 4;
  bytes.sqlite_prenorm = N * DIM * 4;

  // The misaligned branch must copy THIS row's bytes, not the whole backing buffer:
  // `buf.slice()` on a Uint8Array view is a copy of the view, but `.buffer` on the result
  // of the older `Buffer.prototype.slice` is the shared pool, so spelling it out is what
  // keeps the fallback decoding the same bytes the fast path does.
  const toFloats = (buf) =>
    buf.byteOffset % 4 === 0
      ? new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
      : new Float32Array(
          buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength),
        );

  if (WANT.has('sqlite_float32')) {
    const st = db.prepare('SELECT id, vector FROM passages WHERE vector IS NOT NULL');
    candidates.push({
      name: 'sqlite_float32',
      note: 'v1.9.0 shape: BLOB per row, row norm recomputed every query',
      run: () => {
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
    });
  }
  if (WANT.has('sqlite_prenorm')) {
    const st = db.prepare('SELECT id, vector, norm FROM passages WHERE vector IS NOT NULL');
    candidates.push({
      name: 'sqlite_prenorm',
      note: 'the same, with the row norm stored rather than recomputed per query',
      run: () => {
        let best = -2;
        for (const r of st.iterate()) {
          const b = toFloats(r.vector);
          let d = 0;
          for (let i = 0; i < DIM; i++) d += queryArr[i] * b[i];
          const c = d / (qn * r.norm);
          if (c > best) best = c;
        }
        return best;
      },
    });
  }
}

// ---- the in-memory float32 arena --------------------------------------------------------
if (WANT.has('memory_float32')) {
  const arena = new Float32Array(N * DIM);
  const norms = new Float64Array(N);
  for (let r = 0; r < N; r++) {
    let s = 0;
    const o = r * DIM;
    for (let i = 0; i < DIM; i++) {
      const v = ((r * 2654435761 + i * 40503) % 2048) / 2048 - 0.5;
      arena[o + i] = v;
      s += v * v;
    }
    norms[r] = Math.sqrt(s);
  }
  bytes.memory_float32 = arena.byteLength;
  candidates.push({
    name: 'memory_float32',
    note: 'issue #30 option 2: exact arithmetic, vectors already decoded and contiguous',
    run: () => {
      let best = -2;
      for (let r = 0; r < N; r++) {
        const o = r * DIM;
        let d = 0;
        for (let i = 0; i < DIM; i++) d += queryArr[i] * arena[o + i];
        const c = d / (qn * norms[r]);
        if (c > best) best = c;
      }
      return best;
    },
  });
}

// ---- the binary codes -------------------------------------------------------------------
function makeCodes(width) {
  if (width % 32 !== 0) {
    console.error(`width ${width} is not a multiple of 32; sign bits pack into 32-bit words`);
    process.exit(2);
  }
  const words = width >> 5;
  const codes = new Uint32Array(N * words);
  for (let r = 0; r < N; r++) {
    const o = r * words;
    for (let i = 0; i < width; i++) {
      if (((r * 2654435761 + i * 40503) % 2048) / 2048 - 0.5 > 0) codes[o + (i >> 5)] |= 1 << (i & 31);
    }
  }
  const qc = new Uint32Array(words);
  for (let i = 0; i < width; i++) if (query[i] > 0) qc[i >> 5] |= 1 << (i & 31);
  return { codes, qc, words };
}
for (const [flag, width] of [['binary_3072', DIM], ['binary_768', MRL]]) {
  if (!WANT.has(flag)) continue;
  const { codes, qc, words } = makeCodes(width);
  bytes[flag] = codes.byteLength;
  candidates.push({
    name: flag,
    note: `1-bit codes at width ${width}, SWAR popcount over Uint32Array`,
    run: () => {
      let best = 1e9;
      for (let r = 0; r < N; r++) {
        const o = r * words;
        let h = 0;
        for (let i = 0; i < words; i++) h += popcount32(codes[o + i] ^ qc[i]);
        if (h < best) best = h;
      }
      return best;
    },
  });
}
if (WANT.has('bigint_3072')) {
  const words = DIM / 64;
  const codes = new BigUint64Array(N * words);
  bytes.bigint_3072 = codes.byteLength;
  for (let r = 0; r < N; r++) codes[r * words] = BigInt(r % 65536);
  const qc = new BigUint64Array(words);
  for (let i = 0; i < words; i++) qc[i] = 0x0f0f0f0f0f0f0f0fn;
  const pc = (x) => {
    let c = 0n;
    while (x) { x &= x - 1n; c++; }
    return c;
  };
  candidates.push({
    name: 'bigint_3072',
    note: 'the OBVIOUS JS Hamming implementation — measured because it loses',
    run: () => {
      let best = 1e9;
      for (let r = 0; r < N; r++) {
        const o = r * words;
        let h = 0n;
        for (let i = 0; i < words; i++) h += pc(codes[o + i] ^ qc[i]);
        const hh = Number(h);
        if (hh < best) best = hh;
      }
      return best;
    },
  });
}

// ---- timed round robin, order shuffled per pass ----------------------------------------
// Ticket 0008's lesson: timing candidates in consecutive blocks puts any transient wholly
// inside whichever candidate is running, where it reads as that candidate's property.
for (const c of candidates) c.run();
const samples = candidates.map(() => []);
for (let rep = 0; rep < REPS; rep++) {
  const order = candidates.map((_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  for (const i of order) {
    const t = performance.now();
    candidates[i].run();
    samples[i].push(performance.now() - t);
  }
}
const q = (a, p) => a.slice().sort((x, y) => x - y)[Math.floor(a.length * p)];
const results = candidates.map((c, i) => ({
  name: c.name,
  note: c.note,
  median_ms: +q(samples[i], 0.5).toFixed(1),
  iqr_pct_of_median: +(((q(samples[i], 0.75) - q(samples[i], 0.25)) / q(samples[i], 0.5)) * 100).toFixed(1),
  bytes_scanned: bytes[c.name] ?? null,
}));
const base = results.find((r) => r.name === 'sqlite_float32') ?? results[0];
for (const r of results) r.speedup_vs_baseline = +(base.median_ms / r.median_ms).toFixed(2);

writeFileSync(
  opt.output,
  `${JSON.stringify(
    {
      what: "scan cost per semantic query at upstream #30's geometry, by representation",
      when: new Date().toISOString(),
      geometry: { vectors: N, dim: DIM, mrl_prefix: MRL },
      baseline: base.name,
      vectors_are: 'SYNTHETIC — scan latency depends on shape, not on meaning. Recall is ' +
        'measured on real embeddings in bench/vec_mrl_recall.mjs and never here.',
      results,
      open_question:
        'Issue #30 reports 90-105 s. The exact scan here is far below that on this machine, ' +
        'and nothing measured here explains the difference. The experiment that would settle ' +
        'it costs one minute on the reporter’s machine: run the same query twice in a row. ' +
        'Much faster the second time means the cost is getting the bytes off disk; the same ' +
        'both times means it is arithmetic. Until then the gap is unattributed.',
      machine: {
        host: hostname(),
        cpus: cpus().length,
        cpu_model: cpus()[0]?.model ?? null,
        total_mem_bytes: totalmem(),
        free_mem_bytes_at_start: freemem(),
        loadavg: loadavg(),
        node: process.version,
      },
      reps: REPS,
    },
    null,
    2,
  )}\n`,
);
for (const r of results) {
  console.error(
    `${r.name.padEnd(16)} ${String(r.median_ms).padStart(9)} ms  (IQR ${r.iqr_pct_of_median}%)  ` +
      `${r.speedup_vs_baseline}x`,
  );
}
console.error(`\nwrote ${opt.output}`);
