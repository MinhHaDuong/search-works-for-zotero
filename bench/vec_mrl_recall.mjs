// Matryoshka truncation x binary quantization: what each axis costs, measured separately.
//
// Ticket 0008 measured ONE axis — precision, 32 bits per dimension down to 1 — and left
// the other untouched: how many dimensions there are. A Matryoshka-trained model (MRL)
// is trained so that a PREFIX of its embedding is itself a valid embedding, so truncating
// 3072 -> 768 is a second, independent lever on bytes per vector, and the two multiply.
//
// This driver measures both axes on the same corpus and the same probes, and reports the
// decomposition rather than only the end-to-end number:
//
//   (a) truncation alone   — exact cosine over the W-prefix, ranked against the exact
//                            FULL-width ranking. What the prefix costs before any bits
//                            are dropped.
//   (b) truncation + binary — Hamming pool over the W-prefix's sign bits, then an exact
//                            rerank of that pool against the FULL-width float32 vectors.
//                            What a user would actually receive.
//
// Both are scored against the exact full-width ranking, because that is what the user
// gets today and what a change would take away. Scoring (b) against (a) would measure
// the quantizer against a baseline nobody ships.
//
// **The W = full row is a positive control**, not a data point: it must reproduce ticket
// 0008's published recall (0,592 / 0,776 / 0,884 / 0,953 / 0,986 at pools 1/2/4/8/16x,
// zero-threshold, on this corpus at 384 dims) or the driver is wrong and nothing else it
// prints means anything. A recall harness that has never been checked against a known
// answer reports its own bugs as findings.
//
// Truncation here is the RAW prefix, not the renormalized one. Renormalizing is a positive
// per-vector scaling: it changes neither the cosine ranking nor the zero-threshold sign
// bits, and leaving it out is what makes the control row byte-comparable with 0008. It
// would shift only the mean-centred variant, and only through the corpus mean.
import { DatabaseSync } from 'node:sqlite';
import { openSync, readSync, fstatSync, closeSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { cpus, hostname, loadavg, totalmem } from 'node:os';

const { values: opt } = parseArgs({
  options: {
    db: { type: 'string' },
    f32: { type: 'string' },
    dim: { type: 'string' },
    output: { type: 'string' },
    fork: { type: 'string', default: new URL('../fork/', import.meta.url).pathname },
    widths: { type: 'string' },
    probes: { type: 'string', default: '100' },
    topk: { type: 'string', default: '30' },
    seed: { type: 'string', default: '20260822' },
    reps: { type: 'string', default: '25' },
    label: { type: 'string', default: '' },
  },
});
if (!opt.output || (!opt.db && !opt.f32)) {
  console.error(
    'usage: node bench/vec_mrl_recall.mjs (--db <search-index.sqlite> | --f32 <raw.f32> --dim N) --output <f.json>',
  );
  process.exit(2);
}

function positiveInt(name, raw) {
  const v = Number(raw);
  if (!Number.isInteger(v) || v < 1) {
    console.error(`--${name} must be a positive integer, got ${JSON.stringify(raw)}`);
    process.exit(2);
  }
  return v;
}
const TOPK = positiveInt('topk', opt.topk);
const PROBES = positiveInt('probes', opt.probes);
const REPS = positiveInt('reps', opt.reps);

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(Number(opt.seed));

// ---- the vectors ---------------------------------------------------------------------
// Two sources, one shape. The vec0 path reads the prototype index that ticket 0008 built
// and is what the positive control needs; the flat-float32 path takes vectors from any
// embedder without requiring them to be in a database first.
let DIM;
let vecs;
let itemOf = null;
let source;

if (opt.db) {
  const db = new DatabaseSync(opt.db, { allowExtension: true });
  const { createRequire } = await import('node:module');
  const require = createRequire(`${opt.fork}package.json`);
  db.enableLoadExtension(true);
  require('sqlite-vec').load(db);
  db.enableLoadExtension(false);
  DIM = Number(db.prepare("SELECT value FROM index_meta WHERE key = 'vectorDim'").get().value);
  const rows = db.prepare('SELECT rowid, embedding FROM passage_vectors').all();
  vecs = rows.map(
    (r) => new Float32Array(r.embedding.buffer ?? r.embedding, r.embedding.byteOffset ?? 0, DIM),
  );
  const rowids = rows.map((r) => r.rowid);
  const byRowid = new Map(
    db.prepare('SELECT rowid, item FROM passage_meta').all().map((r) => [r.rowid, r.item]),
  );
  itemOf = rowids.map((r) => byRowid.get(r));
  source = { kind: 'vec0', path: opt.db };
  db.close();
} else {
  DIM = positiveInt('dim', opt.dim);
  const fd = openSync(opt.f32, 'r');
  const bytes = fstatSync(fd).size;
  const rowBytes = DIM * 4;
  if (bytes % rowBytes !== 0) {
    console.error(`--f32 file is ${bytes} bytes, not a multiple of ${rowBytes} (--dim ${DIM})`);
    process.exit(2);
  }
  const n = bytes / rowBytes;
  const buf = Buffer.allocUnsafe(bytes);
  let off = 0;
  while (off < bytes) off += readSync(fd, buf, off, Math.min(1 << 24, bytes - off), off);
  closeSync(fd);
  const all = new Float32Array(buf.buffer, buf.byteOffset, bytes / 4);
  vecs = Array.from({ length: n }, (_, i) => all.subarray(i * DIM, (i + 1) * DIM));
  source = { kind: 'float32-file', path: opt.f32 };
  // A sibling `.items` file, one item key per line, enables the same-item share below.
  try {
    const { readFileSync } = await import('node:fs');
    const keys = readFileSync(`${opt.f32}.items`, 'utf8').split('\n').filter(Boolean);
    if (keys.length === n) itemOf = keys;
  } catch {
    /* optional */
  }
}
const N = vecs.length;
if (N < TOPK + 1) {
  console.error(`only ${N} vectors; need more than --topk ${TOPK}`);
  process.exit(2);
}

// The Matryoshka ladder. Halving from the full width is the shape both OpenAI and Google
// document for their MRL models; a width that is not a multiple of 32 cannot be packed into
// whole 32-bit words and is refused rather than silently rounded.
const WIDTHS = (opt.widths ? opt.widths.split(',').map((s) => positiveInt('widths', s.trim())) : [])
  .filter((w) => w <= DIM);
if (WIDTHS.length === 0) {
  for (let w = DIM; w >= 64; w = Math.floor(w / 2)) WIDTHS.push(w);
}
for (const w of WIDTHS) {
  if (w % 32 !== 0) {
    console.error(`width ${w} is not a multiple of 32; sign bits are packed into 32-bit words`);
    process.exit(2);
  }
}

// ---- probes, and the exact full-width ranking they are scored against -----------------
const probeIdx = [];
for (let i = 0; i < PROBES; i++) probeIdx.push(Math.floor(rnd() * N));

/**
 * Bounded top-k selection, ascending, with the tie-breaking of a STABLE sort by index.
 *
 * The full sort this replaces cost N log N per probe per width, which at five widths and
 * two thresholding regimes is the difference between a run of minutes and a run of hours.
 * Ties are the reason it needs care rather than a heap: Hamming distances over 93 000
 * vectors tie in very large groups, so which tied candidate lands inside the pool is a
 * real choice and not a rounding detail. Scanning i ascending and rejecting a candidate
 * that merely EQUALS the current worst reproduces exactly what a stable sort keeps —
 * the lowest indices among the tied — so this selection and that sort return the same pool.
 */
function selectAscending(dist, cap, exclude) {
  const idx = new Int32Array(cap);
  const val = new Float64Array(cap);
  let size = 0;
  for (let i = 0; i < N; i++) {
    if (i === exclude) continue;
    const d = dist[i];
    if (size === cap && d >= val[size - 1]) continue;
    let j = size < cap ? size : size - 1;
    while (j > 0 && val[j - 1] > d) {
      val[j] = val[j - 1];
      idx[j] = idx[j - 1];
      j--;
    }
    val[j] = d;
    idx[j] = i;
    if (size < cap) size++;
  }
  return idx.subarray(0, size);
}

const norms = vecs.map((v) => {
  let s = 0;
  for (let i = 0; i < v.length; i++) s += v[i] * v[i];
  return Math.sqrt(s) || 1;
});
/** Cosine of every vector against `q` over the first `w` dimensions, as a DISTANCE. */
function cosineDistances(q, w) {
  const out = new Float64Array(N);
  let qn = 0;
  for (let i = 0; i < w; i++) qn += q[i] * q[i];
  qn = Math.sqrt(qn) || 1;
  for (let r = 0; r < N; r++) {
    const v = vecs[r];
    let d = 0;
    let s = 0;
    for (let i = 0; i < w; i++) {
      const b = v[i];
      d += q[i] * b;
      s += b * b;
    }
    out[r] = -d / (qn * (Math.sqrt(s) || 1));
  }
  return out;
}

const MAXPOOL = TOPK * 16;
/** The exact full-width answer: what the user gets today, and the target every row scores against. */
const exact = new Map();
for (const p of probeIdx) {
  const dist = cosineDistances(vecs[p], DIM);
  exact.set(p, { top: new Set(selectAscending(dist, TOPK, p)), dist });
}

// ---- sign bits, packed, and the popcount that scans them ------------------------------
/**
 * Sign bits over the first `w` dimensions, packed into 32-bit words.
 *
 * Ticket 0008 packed into bytes and scanned with a 256-entry lookup table. Words and the
 * SWAR popcount below are the same codes read four bytes at a time, and the difference is
 * not cosmetic: measured at this corpus's geometry a BigInt popcount runs 4x SLOWER than
 * the exact float scan it is supposed to replace, so the implementation choice decides
 * whether the whole approach is a speedup at all.
 */
function bitsPacked(v, w, centre) {
  const words = w >> 5;
  const out = new Uint32Array(words);
  for (let i = 0; i < w; i++) {
    const x = centre ? v[i] - centre[i] : v[i];
    if (x > 0) out[i >> 5] |= 1 << (i & 31);
  }
  return out;
}
function popcount32(x) {
  x -= (x >>> 1) & 0x55555555;
  x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
  x = (x + (x >>> 4)) & 0x0f0f0f0f;
  return (Math.imul(x, 0x01010101) >>> 24);
}

/** Corpus mean over the first `w` dimensions — the centre `vec_quantize_binary` does not use. */
function meanPrefix(w) {
  const m = new Float64Array(w);
  for (const v of vecs) for (let i = 0; i < w; i++) m[i] += v[i];
  for (let i = 0; i < w; i++) m[i] /= N;
  return m;
}

const POOLS = [TOPK, TOPK * 2, TOPK * 4, TOPK * 8, TOPK * 16];

/** Recall@TOPK of a coarse pool reranked exactly against the FULL-width vectors. */
function recallFromCoarse(coarseByProbe) {
  return POOLS.map((pool) => {
    let hit = 0;
    for (const p of probeIdx) {
      const { top, dist } = exact.get(p);
      const pooled = Array.from(coarseByProbe.get(p).subarray(0, pool));
      pooled.sort((a, b) => dist[a] - dist[b]);
      hit += pooled.slice(0, TOPK).filter((i) => top.has(i)).length / TOPK;
    }
    return { pool, multiple: pool / TOPK, recall: +(hit / PROBES).toFixed(4) };
  });
}

const perWidth = [];
for (const w of WIDTHS) {
  const words = w >> 5;

  // (a) truncation alone: the exact ranking the prefix produces, no bits dropped.
  let truncHit = 0;
  for (const p of probeIdx) {
    const { top } = exact.get(p);
    const got = selectAscending(cosineDistances(vecs[p], w), TOPK, p);
    for (const i of got) if (top.has(i)) truncHit++;
  }
  const truncationOnly = +(truncHit / (PROBES * TOPK)).toFixed(4);

  // (b) truncation + binary, both thresholding regimes.
  const mean = meanPrefix(w);
  const regimes = {};
  for (const [name, centre] of [['threshold_zero', null], ['mean_centred', mean]]) {
    const codes = new Uint32Array(N * words);
    for (let r = 0; r < N; r++) codes.set(bitsPacked(vecs[r], w, centre), r * words);
    const coarse = new Map();
    for (const p of probeIdx) {
      const qc = bitsPacked(vecs[p], w, centre);
      const d = new Float64Array(N);
      for (let r = 0; r < N; r++) {
        const o = r * words;
        let h = 0;
        for (let i = 0; i < words; i++) h += popcount32(codes[o + i] ^ qc[i]);
        d[r] = h;
      }
      coarse.set(p, selectAscending(d, MAXPOOL, p));
    }
    regimes[name] = recallFromCoarse(coarse);
  }

  perWidth.push({
    width: w,
    bytes_per_vector: { float32: w * 4, binary: w / 8 },
    corpus_bytes: { float32: w * 4 * N, binary: (w / 8) * N },
    truncation_only_recall: truncationOnly,
    binary_recall: regimes,
  });
  console.error(
    `width ${String(w).padStart(5)}  truncation-only ${truncationOnly.toFixed(4)}  ` +
      `binary@4x ${regimes.threshold_zero[2].recall.toFixed(4)}  ` +
      `binary@8x ${regimes.threshold_zero[3].recall.toFixed(4)}`,
  );
}

// ---- what a scan of each representation costs -----------------------------------------
/**
 * Timed round robin, one repetition of each candidate per pass, order shuffled per pass.
 *
 * Ticket 0008 learned this the expensive way: timing each candidate in a consecutive block
 * puts any transient on the machine wholly inside whichever candidate was running, where
 * it presents as a property of that candidate rather than as noise. Interquartile spreads
 * fell from 25-137% of the median to under 10% when the same measurements were interleaved.
 */
function timeScans() {
  const cands = [{ name: 'exact_float32_full', run: () => cosineDistances(vecs[probeIdx[0]], DIM) }];
  for (const w of WIDTHS) {
    const words = w >> 5;
    const codes = new Uint32Array(N * words);
    for (let r = 0; r < N; r++) codes.set(bitsPacked(vecs[r], w, null), r * words);
    const qc = bitsPacked(vecs[probeIdx[0]], w, null);
    cands.push({
      name: `binary_${w}bit_swar`,
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
  const samples = cands.map(() => []);
  for (const c of cands) c.run(); // warm
  for (let rep = 0; rep < REPS; rep++) {
    const order = cands.map((_, i) => i);
    for (let i = order.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      [order[i], order[j]] = [order[j], order[i]];
    }
    for (const i of order) {
      const t = performance.now();
      cands[i].run();
      samples[i].push(performance.now() - t);
    }
  }
  const q = (a, p) => a.slice().sort((x, y) => x - y)[Math.floor(a.length * p)];
  return cands.map((c, i) => ({
    name: c.name,
    median_ms: +q(samples[i], 0.5).toFixed(2),
    iqr_pct_of_median: +(((q(samples[i], 0.75) - q(samples[i], 0.25)) / q(samples[i], 0.5)) * 100).toFixed(1),
  }));
}
const timings = timeScans();

/** How much of a probe's exact top-K is its own item's other chunks. Reported, not filtered. */
function sameItemShare() {
  if (!itemOf) return null;
  let share = 0;
  for (const p of probeIdx) {
    const mine = itemOf[p];
    share += [...exact.get(p).top].filter((i) => itemOf[i] === mine).length / TOPK;
  }
  return +(share / PROBES).toFixed(4);
}

const out = {
  what: 'Matryoshka truncation x binary quantization, decomposed, on real vectors',
  when: new Date().toISOString(),
  label: opt.label || null,
  source,
  corpus: { vectors: N, full_dim: DIM, widths: WIDTHS },
  probes: { count: PROBES, topk: TOPK, seed: Number(opt.seed), leave_one_out: true },
  scored_against: 'the exact full-width float32 cosine ranking, which is what ships today',
  per_width: perWidth,
  scan_timings: timings,
  same_item_share_of_exact_topk: sameItemShare(),
  machine: {
    host: hostname(),
    cpus: cpus().length,
    cpu_model: cpus()[0]?.model ?? null,
    total_mem_bytes: totalmem(),
    loadavg_at_start: loadavg(),
    node: process.version,
  },
  caveats: [
    'Recall is against the exact VECTOR ranking, not against relevance. The shipped path ' +
      'fuses keyword and vector with RRF, so a vector recall of 0,95 does not become 0,95 ' +
      'of the answer quality a user sees, in either direction.',
    'Probes are indexed passages, leave-one-out. With chunk overlap a passage neighbours ' +
      'its own siblings, so the same-item share above belongs beside every recall figure — ' +
      'it makes the retrieval task easier than a real query.',
    'Truncation is the raw prefix. Renormalizing is a positive per-vector scaling and ' +
      'changes neither the cosine ranking nor the zero-threshold sign bits; it would shift ' +
      'only the mean-centred variant, through the corpus mean.',
    'The W = full row is a positive control against ticket 0008, not a finding.',
  ],
};
writeFileSync(opt.output, `${JSON.stringify(out, null, 2)}\n`);
console.error(`\nwrote ${opt.output}`);
