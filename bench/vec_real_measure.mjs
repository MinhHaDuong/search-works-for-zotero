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
import { cpus, hostname, totalmem } from 'node:os';

const { values: opt } = parseArgs({
  options: {
    db: { type: 'string' },
    output: { type: 'string' },
    fork: { type: 'string', default: new URL('../fork/', import.meta.url).pathname },
    probes: { type: 'string', default: '100' },
    topk: { type: 'string', default: '30' },
    seed: { type: 'string', default: '20260822' },
    reps: { type: 'string', default: '100' },
    runs: { type: 'string', default: '4' },
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
const RUNS = positiveInt('runs', opt.runs);

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(Number(opt.seed));

const toBlobEarly = (v) => Buffer.from(new Float32Array(v).buffer);
const db = new DatabaseSync(opt.db, { allowExtension: true });
// The same loader the server uses, so this measures the shipped extension rather than
// whatever happens to be on the system.
const { createRequire } = await import('node:module');
const require = createRequire(`${opt.fork}package.json`);
db.enableLoadExtension(true);
require('sqlite-vec').load(db);
db.enableLoadExtension(false);
const sqliteVecVersion = (() => {
  try {
    return db.prepare('SELECT vec_version() AS v').get().v;
  } catch {
    return null;
  }
})();
// Read before the run rather than after: what the machine was doing when timing started
// is the number that explains a contended result.
const { loadavg } = await import('node:os');

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
const pagesOf = (predicate, pool = tables) => {
  const names = pool.filter(predicate);
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
// Indexes are their own pages and are NOT charged to the table they index. Left out of
// the first version, whose comment then blamed the residual on freelist and page slack —
// measured, the indexes were 6 602 752 B of a 6 610 944 B residual, so the comment named
// the wrong cause for 99,9% of it. An accounting that does not close is a hypothesis.
const indexNames = db
  .prepare("SELECT name FROM sqlite_master WHERE type = 'index'")
  .all()
  .map((r) => r.name);
const idx = pagesOf((t) => indexNames.includes(t), indexNames);
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
  index_bytes: idx.bytes,
};
const accounted = [f32.bytes, bin.bytes, fts.bytes, meta.bytes, idx.bytes].reduce(
  (a, b) => a + (b ?? 0),
  0,
);
sizes.accounted_bytes = accounted || null;
// What is left after every table AND every index: the freelist, the schema, page slack.
// Naming the residual is what turns "some numbers" into an accounting that can be checked.
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
//
// Magnitude is measured beside it, and that pairing is what makes the number mean
// anything. A dimension the model never activates has values scattered in the last bits
// of the float around zero: its sign is then arbitrary, it can read as 100% one-sided,
// and it says nothing whatever about the corpus being off-centre. Counting such a
// dimension as evidence of anisotropy would be reading noise as geometry.
const posFrac = new Float64Array(dim);
const absMean = new Float64Array(dim);
for (const v of vecs) {
  for (let i = 0; i < dim; i++) {
    if (v[i] > 0) posFrac[i]++;
    absMean[i] += Math.abs(v[i]);
  }
}
for (let i = 0; i < dim; i++) {
  posFrac[i] /= vecs.length;
  absMean[i] /= vecs.length;
}
const medianMag = [...absMean].sort((a, b) => a - b)[dim >> 1];
// "Live" = carrying at least a thousandth of the median dimension's magnitude. The two
// this excludes on the measured corpus are 1,4e-6 and 1,4e-31 of it, so no threshold in
// that range changes the answer.
const LIVE = medianMag / 1000;
const perDim = Array.from({ length: dim }, (_, i) => ({
  dim: i,
  one_sided: +Math.max(posFrac[i], 1 - posFrac[i]).toFixed(4),
  mean_abs: absMean[i],
  live: absMean[i] > LIVE,
}));
const bias = perDim.map((d) => d.one_sided).sort((a, b) => b - a);
const deadBits = bias.filter((b) => b > 0.95).length;
const nearDead = bias.filter((b) => b > 0.9).length;
const liveDims = perDim.filter((d) => d.live);
const oneSidedButDead = perDim.filter((d) => d.one_sided > 0.95 && !d.live);
const worstLive = liveDims.reduce((a, b) => (b.one_sided > a.one_sided ? b : a));

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

/**
 * The same recall, but with the coarse pool taken from **vec0 itself** rather than from
 * the JS Hamming ranking above.
 *
 * The JS pass exists so both regimes see identical inputs, and it is a reimplementation:
 * `bits()` matches `vec_quantize_binary`, but Hamming distances tie in large groups and
 * two implementations need not break those ties the same way. So "the same pool" is a
 * claim, and this is the check on it — the shipped `stmtVecBinSearch` selects the pool,
 * everything downstream is unchanged, and the difference in recall is what the caveat is
 * allowed to say.
 *
 * Necessarily zero-threshold only: vec0 quantizes internally and has no mean-centred mode.
 */
const binStmt = db.prepare(
  'SELECT v.rowid AS rowid FROM passage_vectors_bin v' +
    ' WHERE v.embedding MATCH vec_quantize_binary(?) AND v.k = ? ORDER BY v.distance',
);

function recallViaVec0(pool) {
  let hit = 0;
  for (const p of probeIdx) {
    const { top, scored } = exactTop.get(p);
    const want = new Set(top);
    const ids = binStmt
      .all(toBlobEarly(vecs[p]), pool + 1)
      .map((r) => r.rowid)
      .filter((rid) => rid !== rowids[p])
      .slice(0, pool);
    const byRowid = new Map(rowids.map((rid, i) => [rid, i]));
    const reranked = ids
      .map((rid) => byRowid.get(rid))
      .filter((i) => i !== undefined)
      .sort((a, b) => scored[b] - scored[a])
      .slice(0, TOPK);
    hit += reranked.filter((i) => want.has(i)).length / TOPK;
  }
  return +(hit / probeIdx.length).toFixed(4);
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
/**
 * Repeat the whole timing block `--runs` times and keep every run.
 *
 * The claim this exists to support is that the ordering survives run-to-run variation,
 * and the previous version could not support it *by construction*: it wrote one artifact
 * to a fixed path, so run N's numbers were destroyed by run N+1 and "four runs agree" was
 * archaeology across git commits rather than anything a reader could check. A review
 * caught the claim before it caught the structure; the structure was the real defect.
 *
 * Runs are separated in time by nothing in particular, which is the point — they sample
 * whatever the machine is doing.
 */
function timingRuns(candidates, reps, runs) {
  const out = [];
  for (let r = 0; r < runs; r++) {
    out.push({
      // Read per run, immediately before the timings it describes. The first version
      // captured it once, minutes earlier, next to a recall computation it did not
      // describe at all.
      loadavg_1min_at_start: +loadavg()[0].toFixed(2),
      timings: interleavedTimings(candidates, reps),
    });
  }
  return out;
}

const candidates = {
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
};

const runs = timingRuns(candidates, REPS, RUNS);
// The headline block is the LAST run; every run is kept beside it under `latency_runs`.
const latency = runs[runs.length - 1].timings;

/** Ordered only where the interquartile ranges do not overlap, in every run. */
const separated = (a, b) =>
  runs.every(
    ({ timings: t }) => t[a].p75_ms < t[b].p25_ms || t[b].p75_ms < t[a].p25_ms,
  );

/** The spread actually present in the artifact, so the prose can quote it rather than recall it. */
const iqrPct = (t, k) => ((t[k].p75_ms - t[k].p25_ms) / t[k].median_ms) * 100;
const allIqr = runs.flatMap(({ timings: t }) => Object.keys(t).map((k) => iqrPct(t, k)));
const twoStageKeys = ['two_stage_pool_4x', 'two_stage_pool_8x', 'two_stage_pool_16x'];
const twoStageIqr = runs.flatMap(({ timings: t }) => twoStageKeys.map((k) => iqrPct(t, k)));
const range = (a) => [+Math.min(...a).toFixed(1), +Math.max(...a).toFixed(1)];

const out = {
  probe: 'ticket 0008 — binary quantization on the REAL vector index',
  db: opt.db,
  /**
   * The environment, recorded by the driver rather than by whoever writes it up.
   *
   * Omitted from the first version of this file, which was written to satisfy exactly the
   * rule it broke. It matters more here than in most artifacts: two of the findings on
   * this branch turn on machine contention and candidate ordering, and neither is
   * interpretable without knowing what the machine was.
   */
  environment: {
    node: process.version,
    sqlite_vec: sqliteVecVersion,
    sqlite: db.prepare('SELECT sqlite_version() AS v').get().v,
    host: hostname(),
    cpus: cpus().length,
    totalmem_gib: +(totalmem() / 1024 ** 3).toFixed(1),
    node_options: process.env.NODE_OPTIONS ?? '',
  // Passed in rather than read from a clock: Date.now() at write time is the honest
  // stamp for when the run happened.
    finished_utc: new Date().toISOString(),
  },
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
    highest_one_sidedness_values: bias.slice(0, 10).map((x) => +x.toFixed(4)),
  // The refinement that decides how the counts above should be read.
    median_dimension_mean_abs: +medianMag.toExponential(3),
    live_dimension_threshold: +LIVE.toExponential(3),
    dimensions_one_sided_but_dead: oneSidedButDead.map((d) => ({
      dim: d.dim,
      one_sided: d.one_sided,
      mean_abs: +d.mean_abs.toExponential(2),
      ratio_to_median: +(d.mean_abs / medianMag).toExponential(1),
    })),
    most_one_sided_LIVE_dimension: {
      dim: worstLive.dim,
      one_sided: worstLive.one_sided,
      mean_abs: +worstLive.mean_abs.toExponential(2),
    },
    reading:
      'On THIS corpus every dimension above 95% one-sided is one the model never ' +
      'activates — mean magnitude a millionth or less of the median dimension, so its ' +
      'sign is float noise rather than corpus geometry — and among dimensions that carry ' +
      'signal one-sidedness tops out at most_one_sided_LIVE_dimension. Nothing forces that ' +
      'coincidence: a corpus could be genuinely one-sided in a live dimension, and the ' +
      'two fields are reported separately so a future run shows it rather than inheriting ' +
      'this sentence. Here, a sign-threshold quantizer has nothing to fear, which is the ' +
      'risk 0008 was held open for.',
  },
  recall,
  coarse_pool_fidelity: {
    question:
      'The recall column takes its coarse pool from a JS Hamming ranking so both regimes ' +
      'see identical inputs. That is a reimplementation of what vec0 does, and Hamming ' +
      'distances tie in large groups, so the two need not select the same pool. This is ' +
      'the check on the word "same".',
    recall_via_vec0_pool: POOLS.map((pool) => ({
      multiple: pool / TOPK,
      via_js_pool: recall.find((r) => r.pool === pool).recall_threshold_zero,
      via_vec0_pool: recallViaVec0(pool),
    })),
  },
  latency_ms: latency,
  latency_runs: runs,
  latency_run_agreement: {
    runs: runs.length,
    note:
      'Every run is kept, in this one artifact, because the claim being made is that the ' +
      'ordering survives run-to-run variation. An earlier version wrote one artifact to a ' +
      'fixed path, so each run destroyed the last and the agreement could only be ' +
      'reconstructed from git history — a claim its own evidence could not hold.',
    speedup_vs_exact_per_run: Object.fromEntries(
      twoStageKeys.map((k) => [
        k,
        runs.map(({ timings: t }) => +(t.exact_k30.median_ms / t[k].median_ms).toFixed(2)),
      ]),
    ),
    iqr_pct_range_all_candidates: range(allIqr),
    iqr_pct_range_two_stage: range(twoStageIqr),
  },
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
    `mean norm ${out.anisotropy.corpus_mean_norm}; ${deadBits} dims >95% one-sided but all dead ` +
    `(worst LIVE dimension ${worstLive.one_sided})\n` +
    recall.map((r) => `  pool ${r.multiple}x: zero-threshold ${r.recall_threshold_zero}, mean-centred ${r.recall_mean_centred}`).join('\n') +
    `\nexact k=30 ${latency.exact_k30.median_ms} ms  |  two-stage: ` +
    `4x ${latency.two_stage_pool_4x.median_ms} ms, 8x ${latency.two_stage_pool_8x.median_ms} ms, ` +
    `16x ${latency.two_stage_pool_16x.median_ms} ms`,
);
