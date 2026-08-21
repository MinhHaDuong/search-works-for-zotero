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
  },
});
if (!opt.db || !opt.output) {
  console.error('usage: node bench/vec_real_measure.mjs --db <search-index.sqlite> --output <f.json>');
  process.exit(2);
}
const TOPK = Number(opt.topk);
const PROBES = Number(opt.probes);

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
function cosine(a, b) {
  let d = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { d += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
  return d / (Math.sqrt(na) * Math.sqrt(nb) || 1);
}
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
 * Recall@topK of a binary-first pool reranked exactly, against the exact ranking.
 *
 * **Leave-one-out.** The probe is a real passage drawn from the corpus, which is the
 * point — its embedding has the distribution under test, where a synthesised query would
 * not. But it is also IN the index, so without excluding it every ranking begins with a
 * cosine of 1,0 against itself, at Hamming distance 0, in both regimes. That self-match
 * is free recall, it is free in exactly the same amount for the coarse and the exact
 * pass, and it therefore hides the degradation this driver exists to detect. At topK=30
 * it would inflate every figure by up to 1/30 and mask a first-pass failure at pool 1x
 * almost entirely. The forge review seat caught this before the run landed.
 */
function recallAt(pool, codes, centre) {
  let hit = 0;
  for (const p of probeIdx) {
    const q = vecs[p];
    const exact = vecs
      .map((v, i) => [cosine(q, v), i])
      .filter((x) => x[1] !== p)
      .sort((a, b) => b[0] - a[0])
      .slice(0, TOPK)
      .map((x) => x[1]);
    const qc = bits(q, centre);
    const coarse = codes
      .map((c, i) => [hamming(qc, c), i])
      .filter((x) => x[1] !== p)
      .sort((a, b) => a[0] - b[0])
      .slice(0, pool)
      .map((x) => x[1]);
    const reranked = coarse
      .map((i) => [cosine(q, vecs[i]), i])
      .sort((a, b) => b[0] - a[0])
      .slice(0, TOPK)
      .map((x) => x[1]);
    const want = new Set(exact);
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
    const q = vecs[p];
    const mine = itemOf.get(rowids[p]);
    const exact = vecs
      .map((v, i) => [cosine(q, v), i])
      .filter((x) => x[1] !== p)
      .sort((a, b) => b[0] - a[0])
      .slice(0, TOPK);
    share += exact.filter(([, i]) => itemOf.get(rowids[i]) === mine).length / TOPK;
  }
  return +(share / probeIdx.length).toFixed(4);
}

const POOLS = [TOPK, TOPK * 2, TOPK * 4, TOPK * 8, TOPK * 16];
const recall = POOLS.map((pool) => ({
  pool,
  multiple: pool / TOPK,
  recall_threshold_zero: recallAt(pool, codesZero, null),
  recall_mean_centred: recallAt(pool, codesCentred, mean),
}));

// ---- latency, through the shipped SQL ------------------------------------------------
const toBlob = (v) => Buffer.from(new Float32Array(v).buffer);
const exactStmt = db.prepare(
  'SELECT v.rowid FROM passage_vectors v WHERE v.embedding MATCH ? AND v.k = ? ORDER BY v.distance',
);
const binStmt = db.prepare(
  'SELECT v.rowid FROM passage_vectors_bin v WHERE v.embedding MATCH vec_quantize_binary(?) AND v.k = ? ORDER BY v.distance',
);
function timeIt(fn, reps = 20) {
  fn();
  const t = [];
  for (let i = 0; i < reps; i++) { const s = performance.now(); fn(); t.push(performance.now() - s); }
  t.sort((a, b) => a - b);
  return { median_ms: +t[t.length >> 1].toFixed(2), min_ms: +t[0].toFixed(2), max_ms: +t[t.length - 1].toFixed(2) };
}
const q = toBlob(vecs[probeIdx[0]]);
const latency = {
  exact_k30: timeIt(() => exactStmt.all(q, 30)),
  binary_k30: timeIt(() => binStmt.all(q, 30)),
  binary_k480: timeIt(() => binStmt.all(q, 480)),
  binary_k960: timeIt(() => binStmt.all(q, 960)),
};

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
    `\nlatency exact k=30 ${latency.exact_k30.median_ms} ms, binary k=30 ${latency.binary_k30.median_ms} ms, ` +
    `k=480 ${latency.binary_k480.median_ms} ms, k=960 ${latency.binary_k960.median_ms} ms`,
);
