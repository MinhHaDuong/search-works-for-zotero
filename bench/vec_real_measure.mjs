// Ticket 0008 on REAL vectors: latency, on-disk size, and the anisotropy risk.
//
// The recall figures that decided 0008 came from a synthetic fixture — a mixture of 200
// centroids. The ticket left one criterion open and named the risk to test here:
// `vec_quantize_binary` thresholds each dimension at ZERO, and real sentence embeddings
// are not zero-mean, so the binary first pass can be worse on real data than on a fixture
// built symmetrically around the origin. A fixture cannot answer that about itself.
//
// Everything below runs against an index built by the server from the real library, with
// the real embedder. Nothing is generated here.
import { DatabaseSync } from 'node:sqlite';
import { statSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';

const { values: opt } = parseArgs({
  options: {
    db: { type: 'string' },
    output: { type: 'string' },
    fork: { type: 'string', default: new URL('../fork/', import.meta.url).pathname },
    probes: { type: 'string', default: '100' },
    topk: { type: 'string', default: '30' },
    seed: { type: 'string', default: '20260822' },
    reps: { type: 'string', default: '100' },
  },
});
if (!opt.db || !opt.output) {
  console.error('usage: node bench/vec_real_measure.mjs --db <search-index.sqlite> --output <f.json>');
  process.exit(2);
}
/**
 * Validate before anything expensive runs.
 *
 * The recall computation costs about two minutes on this corpus, and it happens before
 * the first timing. A bad `--reps` used to surface as a TypeError from the quantile
 * arithmetic *after* that was already paid, on an empty sample array. Cheap to check, and
 * the failure it prevents is a wasted run rather than a wrong number.
 */
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

const db = new DatabaseSync(opt.db, { allowExtension: true });
// The same loader the server uses, so this measures the shipped extension rather than
// whatever happens to be on the system.
const { createRequire } = await import('node:module');
const require = createRequire(`${opt.fork}package.json`);
db.enableLoadExtension(true);
require('sqlite-vec').load(db);
db.enableLoadExtension(false);

const dim = Number(db.prepare("SELECT value FROM index_meta WHERE key = 'vectorDim'").get().value);
const n = db.prepare('SELECT count(*) AS n FROM passage_vectors').get().n;
const passages = db.prepare('SELECT count(*) AS n FROM passage_meta').get().n;

// ---- on disk -----------------------------------------------------------------------
// Page counts per table rather than a guess from dim x 4: vec0 stores its vectors in
// chunk tables and the overhead is what the ticket asked about.
/**
 * Bytes for a logical component, summed over EVERY shadow table it owns.
 *
 * Both `vec0` and `fts5` spread one logical table across several physical ones — chunks,
 * rowids, info, and for FTS5 the content/idx/docsize/config set. Charging a component
 * only its `*_vector_chunks00` or `*_data` table undercounts it, and the components then
 * cannot be checked against the file size, which is the one arithmetic that catches a
 * miscount. So each pattern is matched against `sqlite_master` and the accounting is
 * reported with its own residual.
 */
const tables = db
  .prepare("SELECT name FROM sqlite_master WHERE type = 'table'")
  .all()
  .map((r) => r.name);
const pagesOf = (predicate) => {
  const names = tables.filter(predicate);
  if (names.length === 0) return { bytes: null, tables: [] };
  try {
    const q = db.prepare(
      `SELECT sum(pgsize) AS b FROM dbstat WHERE name IN (${names.map(() => '?').join(',')})`,
    );
    return { bytes: q.get(...names)?.b ?? null, tables: names };
  } catch {
    // dbstat is a compile-time option; absent is a gap in the report, not a failure.
    return { bytes: null, tables: names };
  }
};
const isBin = (t) => t.startsWith('passage_vectors_bin');
const f32 = pagesOf((t) => t.startsWith('passage_vectors') && !isBin(t));
const bin = pagesOf(isBin);
const fts = pagesOf((t) => t === 'passages' || t.startsWith('passages_'));
const meta = pagesOf((t) => t === 'passage_meta' || t === 'index_meta');
const sizes = {
  file_bytes: statSync(opt.db).size,
  page_size: db.prepare('PRAGMA page_size').get().page_size,
  float32_bytes: f32.bytes,
  float32_tables: f32.tables,
  binary_bytes: bin.bytes,
  binary_tables: bin.tables,
  fts5_bytes: fts.bytes,
  fts5_tables: fts.tables,
  meta_bytes: meta.bytes,
};
const accounted = [f32.bytes, bin.bytes, fts.bytes, meta.bytes].reduce((a, b) => a + (b ?? 0), 0);
sizes.accounted_bytes = accounted || null;
// Freelist, the schema itself and page slack are not any component's; naming the residual
// is what turns "these four numbers" into an accounting that can be checked.
sizes.unaccounted_bytes = accounted ? sizes.file_bytes - accounted : null;
if (f32.bytes) sizes.float32_bytes_per_vector = +(f32.bytes / n).toFixed(1);
if (bin.bytes) sizes.binary_bytes_per_vector = +(bin.bytes / n).toFixed(1);
if (f32.bytes && bin.bytes) sizes.float32_over_binary = +(f32.bytes / bin.bytes).toFixed(2);

// ---- read the vectors out, for the distribution questions ---------------------------
const rows = db.prepare('SELECT rowid, embedding FROM passage_vectors').all();
const vecs = rows.map((r) => new Float32Array(r.embedding.buffer ?? r.embedding, r.embedding.byteOffset ?? 0, dim));
const rowids = rows.map((r) => r.rowid);

// ---- anisotropy: how far from zero-mean is this corpus? ------------------------------
// The question the fixture could not ask of itself. `vec_quantize_binary` sets bit i from
// sign(x_i), so a dimension whose values sit almost entirely on one side of zero carries
// almost no information in the binary code — every vector agrees there.
const mean = new Float64Array(dim);
for (const v of vecs) for (let i = 0; i < dim; i++) mean[i] += v[i];
for (let i = 0; i < dim; i++) mean[i] /= vecs.length;
let meanNorm = 0;
for (let i = 0; i < dim; i++) meanNorm += mean[i] * mean[i];
meanNorm = Math.sqrt(meanNorm);

// Per-dimension sign balance: 0,5 is perfectly informative, 1,0 is a dead bit.
const posFrac = new Float64Array(dim);
for (const v of vecs) for (let i = 0; i < dim; i++) if (v[i] > 0) posFrac[i]++;
for (let i = 0; i < dim; i++) posFrac[i] /= vecs.length;
const bias = Array.from(posFrac, (p) => Math.max(p, 1 - p)).sort((a, b) => b - a);
const deadBits = bias.filter((b) => b > 0.95).length;
const nearDead = bias.filter((b) => b > 0.9).length;

// ---- exact and binary rankings, computed here so both see identical inputs ------------
/** Sign bits, the way vec_quantize_binary does it: threshold at zero. */
function bits(v, centre) {
  const out = new Uint8Array(v.length >> 3);
  for (let i = 0; i < v.length; i++) {
    const x = centre ? v[i] - centre[i] : v[i];
    if (x > 0) out[i >> 3] |= 1 << (i & 7);
  }
  return out;
}
const POP = new Uint8Array(256);
for (let i = 0; i < 256; i++) POP[i] = (i & 1) + POP[i >> 1];
function hamming(a, b) {
  let d = 0;
  for (let i = 0; i < a.length; i++) d += POP[a[i] ^ b[i]];
  return d;
}

const probeIdx = [];
for (let i = 0; i < PROBES; i++) probeIdx.push(Math.floor(rnd() * vecs.length));

const codesZero = vecs.map((v) => bits(v, null));
const codesCentred = vecs.map((v) => bits(v, mean));

/**
 * Per-probe rankings, computed ONCE.
 *
 * The exact ranking depends only on the probe, and the coarse Hamming ranking only on the
 * probe and the thresholding regime — neither depends on the pool size. Recomputing them
 * inside the pool loop cost ten full scans of the corpus per probe, which at N = 93 022
 * and 384 dimensions is the difference between a run of minutes and a run of an hour.
 *
 * **Leave-one-out.** The probe is a real passage drawn from the corpus, which is the
 * point — its embedding has the distribution under test, where a synthesised query would
 * not. But it is also IN the index, so without excluding it every ranking begins with a
 * cosine of 1,0 against itself, at Hamming distance 0, in both regimes. That self-match is
 * free recall, free in the same amount for the coarse and the exact pass, and it therefore
 * hides the degradation this driver exists to detect. The forge review seat caught it
 * before the run landed.
 */
const norms = vecs.map((v) => {
  let s = 0;
  for (let i = 0; i < v.length; i++) s += v[i] * v[i];
  return Math.sqrt(s) || 1;
});
function dot(a, b) {
  let d = 0;
  for (let i = 0; i < a.length; i++) d += a[i] * b[i];
  return d;
}

const exactTop = new Map();
for (const p of probeIdx) {
  const q = vecs[p];
  const nq = norms[p];
  const scored = new Float64Array(vecs.length);
  for (let i = 0; i < vecs.length; i++) scored[i] = dot(q, vecs[i]) / (nq * norms[i]);
  const order = Array.from({ length: vecs.length }, (_, i) => i).filter((i) => i !== p);
  order.sort((a, b) => scored[b] - scored[a]);
  exactTop.set(p, { top: order.slice(0, TOPK), scored });
}

/** Coarse Hamming order for every probe under one thresholding regime. */
function coarseOrders(codes, centre) {
  const out = new Map();
  for (const p of probeIdx) {
    const qc = bits(vecs[p], centre);
    const d = new Int32Array(vecs.length);
    for (let i = 0; i < vecs.length; i++) d[i] = hamming(qc, codes[i]);
    const order = Array.from({ length: vecs.length }, (_, i) => i).filter((i) => i !== p);
    order.sort((a, b) => d[a] - d[b]);
    out.set(p, order);
  }
  return out;
}
const coarseZero = coarseOrders(codesZero, null);
const coarseCentred = coarseOrders(codesCentred, mean);

/** Recall@topK of a binary-first pool reranked exactly, against the exact ranking. */
function recallAt(pool, coarse) {
  let hit = 0;
  for (const p of probeIdx) {
    const { top, scored } = exactTop.get(p);
    const want = new Set(top);
    const reranked = coarse
      .get(p)
      .slice(0, pool)
      .sort((a, b) => scored[b] - scored[a])
      .slice(0, TOPK);
    hit += reranked.filter((i) => want.has(i)).length / TOPK;
  }
  return +(hit / probeIdx.length).toFixed(4);
}

/**
 * How much of a probe's exact top-K comes from its OWN item.
 *
 * Reported rather than filtered. Chunk overlap is 150 characters, so a passage's nearest
 * neighbours are genuinely its own siblings — that is the corpus, not an artifact, and
 * removing it would measure a corpus nobody has. But it does make the retrieval task
 * easier than a real query's, so the number belongs beside the recall figures rather than
 * inside them.
 */
function sameItemShare() {
  const itemOf = new Map(
    db.prepare('SELECT rowid, item FROM passage_meta').all().map((r) => [r.rowid, r.item]),
  );
  let share = 0;
  for (const p of probeIdx) {
    const mine = itemOf.get(rowids[p]);
    const { top } = exactTop.get(p);
    share += top.filter((i) => itemOf.get(rowids[i]) === mine).length / TOPK;
  }
  return +(share / probeIdx.length).toFixed(4);
}

const POOLS = [TOPK, TOPK * 2, TOPK * 4, TOPK * 8, TOPK * 16];
const recall = POOLS.map((pool) => ({
  pool,
  multiple: pool / TOPK,
  recall_threshold_zero: recallAt(pool, coarseZero),
  recall_mean_centred: recallAt(pool, coarseCentred),
}));

// ---- latency, through the shipped SQL ------------------------------------------------
const toBlob = (v) => Buffer.from(new Float32Array(v).buffer);

// The three statements below are `Fts5PassageStore`'s own, copied verbatim rather than
// paraphrased. An earlier version dropped the `JOIN passage_meta` from the exact search
// and the rerank, on the reasoning that a join on an INTEGER PRIMARY KEY is free. Even if
// it is nearly free, dropping it was not symmetric: the exact path pays ONE join over its
// k rows, while the two-stage path pays one per pooled rowid, so the omission scaled with
// the pool on exactly the arm under test and flattered it. A review seat caught it.
// Measuring a paraphrase of the shipped query measures the paraphrase.
const exactStmt = db.prepare(
  'SELECT m.id AS id, 1.0 - v.distance AS score' +
    ' FROM passage_vectors v JOIN passage_meta m ON m.rowid = v.rowid' +
    ' WHERE v.embedding MATCH ? AND v.k = ? ORDER BY v.distance',
);
const binStmt = db.prepare(
  'SELECT v.rowid AS rowid FROM passage_vectors_bin v' +
    ' WHERE v.embedding MATCH vec_quantize_binary(?) AND v.k = ? ORDER BY v.distance',
);
/**
 * Time several candidates by INTERLEAVING their repetitions, not by running each in a
 * block.
 *
 * The first version ran 20 consecutive reps per candidate, and its spreads came back at
 * 25-137% of the median — wide enough that the ordering it reported was not supported by
 * it. Consecutive blocks are the reason: any transient on this machine (a page-cache
 * eviction, another process waking) lands wholly inside whichever candidate happened to
 * be running, so it appears as a property of that candidate rather than as noise. Round
 * robin spreads every transient across all of them, which is what makes the *comparison*
 * meaningful even while the absolute numbers stay noisy.
 *
 * Reported as median with an interquartile range, plus the minimum. Min is the closest
 * thing to an uncontended reading and is the honest "how fast can this go"; the IQR is
 * what says whether two candidates can be ordered at all. Max is dropped — on a shared
 * machine it measures the worst thing that happened to the OS, not the query.
 */
function interleavedTimings(candidates, reps) {
  const names = Object.keys(candidates);
  const samples = Object.fromEntries(names.map((k) => [k, []]));
  for (const k of names) candidates[k](); // warm every one before any is timed
  for (let r = 0; r < reps; r++) {
    // Order is shuffled per pass, not just interleaved. Round robin at a FIXED order
    // spreads transients but not position: every candidate would always see the same
    // predecessor's cache state, and the first would always follow the largest pool.
    // That residual cannot explain a 3x, but an order effect is a defect class this
    // chantier has already been bitten by once (0013), and the guard belongs in the
    // harness rather than in a note saying it probably does not matter.
    const order = names.slice();
    for (let i = order.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      [order[i], order[j]] = [order[j], order[i]];
    }
    for (const k of order) {
      const t0 = performance.now();
      candidates[k]();
      samples[k].push(performance.now() - t0);
    }
  }
  const q = (a, p) => a[Math.min(a.length - 1, Math.floor(a.length * p))];
  return Object.fromEntries(
    names.map((k) => {
      const a = samples[k].sort((x, y) => x - y);
      return [
        k,
        {
          median_ms: +q(a, 0.5).toFixed(2),
          min_ms: +a[0].toFixed(2),
          p25_ms: +q(a, 0.25).toFixed(2),
          p75_ms: +q(a, 0.75).toFixed(2),
          reps: a.length,
        },
      ];
    }),
  );
}

const q = toBlob(vecs[probeIdx[0]]);
// The rerank the shipped two-stage path performs: one exact cosine per pooled rowid,
// through the same prepared statement `Fts5PassageStore.vectorSearch` uses.
const rerankStmt = db.prepare(
  'SELECT m.id AS id, 1.0 - vec_distance_cosine(v.embedding, ?) AS score' +
    ' FROM passage_vectors v JOIN passage_meta m ON m.rowid = v.rowid WHERE v.rowid = ?',
);
/** End to end: binary first pass at `pool`, then exact rerank of what it returned. */
const twoStage = (pool) => () => {
  const ids = binStmt.all(q, pool);
  for (const r of ids) rerankStmt.get(q, r.rowid);
};
const latency = interleavedTimings(
  {
    // The baseline the two-stage path has to beat.
    exact_k30: () => exactStmt.all(q, 30),
    // First pass alone, to show where the cost sits.
    binary_first_pass_k30: () => binStmt.all(q, 30),
    binary_first_pass_k120: () => binStmt.all(q, 120),
    binary_first_pass_k240: () => binStmt.all(q, 240),
    binary_first_pass_k480: () => binStmt.all(q, 480),
    // Kept because it is the point where vec0's superlinear k-best cost is unmistakable,
    // which is the observation 0008 was filed on.
    binary_first_pass_k960: () => binStmt.all(q, 960),
    // What a caller actually waits for, at the pools whose recall is measured above.
    // Measured rather than interpolated: this chantier's recurring mistake is reading a
    // curve off two of its points, and the operating point that matters is 8x.
    two_stage_pool_4x: twoStage(TOPK * 4),
    two_stage_pool_8x: twoStage(TOPK * 8),
    two_stage_pool_16x: twoStage(TOPK * 16),
  },
  REPS,
);

/** Ordered only where the interquartile ranges do not overlap. */
const separated = (a, b) =>
  latency[a].p75_ms < latency[b].p25_ms || latency[b].p75_ms < latency[a].p25_ms;

const out = {
  probe: 'ticket 0008 — binary quantization on the REAL vector index',
  db: opt.db,
  corpus: { vectors: n, passages, dim, probes: PROBES, topk: TOPK, seed: opt.seed },
  on_disk: sizes,
  anisotropy: {
    question:
      'vec_quantize_binary thresholds at zero. If the corpus mean is far from the origin, ' +
      'dimensions sit mostly on one side of it and their bits carry little information — ' +
      'the risk 0008 named and a symmetric fixture cannot exhibit.',
    corpus_mean_norm: +meanNorm.toFixed(4),
    note_on_scale: 'Embeddings are unit-normalised, so a mean norm near 1 would mean the corpus barely spreads at all; near 0 means it is centred.',
    dimensions_over_95pct_one_sided: deadBits,
    dimensions_over_90pct_one_sided: nearDead,
    most_one_sided_dimensions: bias.slice(0, 10).map((x) => +x.toFixed(4)),
  },
  recall,
  latency_ms: latency,
  latency_method:
    'Candidates are timed round robin, one repetition each per pass, so a transient on ' +
    'the machine is spread across all of them instead of landing inside one. Median with ' +
    'p25/p75; min is the closest reading to uncontended. Two candidates are only ordered ' +
    'where their interquartile ranges do not overlap — see latency_ordering.',
  latency_ordering: Object.fromEntries(
    ['two_stage_pool_4x', 'two_stage_pool_8x', 'two_stage_pool_16x'].map((k) => [
      k,
      {
        speedup_vs_exact_median: +(latency.exact_k30.median_ms / latency[k].median_ms).toFixed(2),
        separated_from_exact: separated(k, 'exact_k30'),
      },
    ]),
  ),
  probe_design: {
    note:
      'Probes are real indexed passages, leave-one-out: a probe never retrieves itself. ' +
      'Without that exclusion every ranking starts with a free self-match, identical in ' +
      'both regimes, which inflates recall and hides the degradation under test.',
    exact_topk_from_the_probe_own_item: sameItemShare(),
    note_on_that:
      'Chunk overlap is 150 characters, so a passage neighbours its own siblings. Reported ' +
      'rather than filtered: it is the corpus, but it makes retrieval easier than a real ' +
      "query's, so the recall figures should be read next to it.",
  },
};
writeFileSync(opt.output, JSON.stringify(out, null, 1));
db.close();

console.log(
  `${n} real vectors, dim ${dim}\n` +
    `mean norm ${out.anisotropy.corpus_mean_norm}; ${deadBits} dims >95% one-sided, ${nearDead} >90%\n` +
    recall.map((r) => `  pool ${r.multiple}x: zero-threshold ${r.recall_threshold_zero}, mean-centred ${r.recall_mean_centred}`).join('\n') +
    `\nexact k=30 ${latency.exact_k30.median_ms} ms  |  two-stage: ` +
    `4x ${latency.two_stage_pool_4x.median_ms} ms, 8x ${latency.two_stage_pool_8x.median_ms} ms, ` +
    `16x ${latency.two_stage_pool_16x.median_ms} ms`,
);
