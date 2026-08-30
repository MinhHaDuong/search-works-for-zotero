// The vector arm and the fused RRF arm of ticket 0265's same-item retrieval measurement,
// for ONE (candidate, dtype) cell -- scored against the SAME probe set and the SAME keyword
// ranklists bench/fts5_keyword_arm.mjs already computed once for the whole campaign.
//
// Fusion rule: fraction-weighted RRF at k=60 (spec/DESIGN.md §2.6). The calibration that
// sets frac_vec (#6012-style mean-centering against a noise floor / ceiling) is deferred to
// ticket 0031 -- it has no data source yet, and DESIGN §2.6 says so itself ("as first
// adopted it had no data source and left frac_vec undefined at minute zero"). This driver
// therefore runs the rule at its own stated upper bound, frac=1 for both arms, which
// DESIGN §2.6 defines as recovering PLAIN RRF ("frac in [0,1] bounds every contribution
// above by plain RRF"). That is a scope decision, not an approximation of convenience:
// plain RRF is the one point on the fraction-weighted family that needs no calibration
// data, and it is exactly the family's own upper bound, so nothing here disagrees with the
// design at a higher frac -- it just does not yet know what a lower one should be.
//
//   score(doc) = sum over each arm this doc appears in of 1 / (60 + rank_in_that_arm)
//              (rank is 0-indexed: the best hit in an arm contributes 1/60)
//
// A doc absent from one arm contributes 0 from that arm, not a penalty -- standard RRF.
//
//   node bench/fused_recall.mjs --f32 <candidate-dtype.f32> --dim 384 \
//     --items subsample-items.txt --ords subsample-ords.txt \
//     --keyword-arm keyword-arm.json --name granite-97m-multilingual-r2-q8 \
//     --output out.json
import { openSync, readSync, fstatSync, closeSync, readFileSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { drawProbes } from './recall_probes.mjs';

const { values: opt } = parseArgs({
  options: {
    f32: { type: 'string' },
    dim: { type: 'string' },
    items: { type: 'string' },
    ords: { type: 'string' },
    'keyword-arm': { type: 'string' },
    name: { type: 'string' },
    output: { type: 'string' },
    topk: { type: 'string', default: '30' },
    gap: { type: 'string', default: '3' },
    probes: { type: 'string', default: '400' },
    seed: { type: 'string', default: '20260830' },
    'rrf-k': { type: 'string', default: '60' },
  },
});
for (const req of ['f32', 'dim', 'items', 'ords', 'keyword-arm', 'output']) {
  if (!opt[req]) {
    console.error(`usage: node bench/fused_recall.mjs --f32 f --dim D --items f --ords f ` +
      `--keyword-arm keyword-arm.json --output out.json [--name label]`);
    process.exit(2);
  }
}
const TOPK = Number(opt.topk);
const GAP = Number(opt.gap);
const RRF_K = Number(opt['rrf-k']);
const DIM = Number(opt.dim);

const items = readFileSync(opt.items, 'utf8').split('\n').filter(Boolean);
const ords = readFileSync(opt.ords, 'utf8').split('\n').filter(Boolean).map(Number);
const N = items.length;

const { byItem, eligible, probeIdx } = drawProbes({
  items, ords, gap: GAP, probes: Number(opt.probes), seed: opt.seed,
});

const kwArm = JSON.parse(readFileSync(opt['keyword-arm'], 'utf8'));
// The seam invariant this fusion depends on: the keyword arm was drawn from the SAME
// items/ords/seed/gap/probes, so its probe_idx is this run's probe_idx verbatim. Assert
// it rather than silently fusing mismatched probe sets.
if (JSON.stringify(kwArm.probe_idx) !== JSON.stringify(probeIdx)) {
  console.error(
    'FATAL: keyword-arm probe_idx does not match this run\'s probe draw -- re-run ' +
    'fts5_keyword_arm.mjs with the same --items/--ords/--seed/--gap/--probes as this cell',
  );
  process.exit(1);
}

function loadVectors(path, dim) {
  const fd = openSync(path, 'r');
  const bytes = fstatSync(fd).size;
  if (bytes % (dim * 4) !== 0) {
    console.error(`${path}: ${bytes} bytes is not a multiple of ${dim * 4}`);
    process.exit(2);
  }
  const n = bytes / (dim * 4);
  if (n !== N) {
    console.error(`${path}: ${n} vectors, but ${N} item keys`);
    process.exit(2);
  }
  const buf = Buffer.allocUnsafe(bytes);
  let off = 0;
  while (off < bytes) {
    const got = readSync(fd, buf, off, Math.min(1 << 24, bytes - off), off);
    if (got === 0) {
      closeSync(fd);
      console.error(`${path}: file ended after ${off} of ${bytes} bytes`);
      process.exit(2);
    }
    off += got;
  }
  closeSync(fd);
  const all = new Float32Array(buf.buffer, buf.byteOffset, bytes / 4);
  return Array.from({ length: n }, (_, i) => all.subarray(i * dim, (i + 1) * dim));
}

const vecs = loadVectors(opt.f32, DIM);
const norms = vecs.map((v) => {
  let s = 0;
  for (let i = 0; i < DIM; i++) s += v[i] * v[i];
  return Math.sqrt(s) || 1;
});

/** Cosine top-K for probe p, same candidate-exclusion rule as bench/vec_task_recall.mjs:
 * same-item passages that are NOT in the relevant set (self, or nearer than `gap`) are
 * removed from the candidate pool entirely, not merely from the scored relevant set. */
function vectorTopK(p) {
  const q = vecs[p];
  const qn = norms[p];
  const mine = items[p];
  const myOrd = ords[p];
  const relevant = new Set(byItem.get(mine).filter((j) => j !== p && Math.abs(ords[j] - myOrd) >= GAP));
  const top = [];
  for (let i = 0; i < N; i++) {
    if (items[i] === mine && !relevant.has(i)) continue;
    const v = vecs[i];
    let d = 0;
    for (let k = 0; k < DIM; k++) d += q[k] * v[k];
    const s = d / (qn * norms[i]);
    if (top.length >= TOPK && s <= top[top.length - 1].s) continue;
    let j = top.length < TOPK ? top.length : TOPK - 1;
    while (j > 0 && top[j - 1].s < s) {
      top[j] = top[j - 1];
      j--;
    }
    top[j] = { i, s };
    if (top.length > TOPK) top.length = TOPK;
  }
  return { top: top.map((t) => t.i), relevant };
}

function scoreSet(rankedIds, relevant) {
  const hits = rankedIds.filter((id) => relevant.has(id)).length;
  const recall = hits / Math.min(relevant.size, TOPK);
  const rank = rankedIds.findIndex((id) => relevant.has(id));
  const mrr = rank >= 0 ? 1 / (rank + 1) : 0;
  return { recall, mrr };
}

/** Fraction-weighted RRF at frac=1 for both arms == plain RRF (DESIGN §2.6's own stated
 * upper bound; see header). Rank is 0-indexed within each arm's own list. */
function fuse(vectorIds, keywordIds) {
  const score = new Map();
  vectorIds.forEach((id, rank) => score.set(id, (score.get(id) ?? 0) + 1 / (RRF_K + rank)));
  keywordIds.forEach((id, rank) => score.set(id, (score.get(id) ?? 0) + 1 / (RRF_K + rank)));
  return [...score.entries()].sort((a, b) => b[1] - a[1]).slice(0, TOPK).map(([id]) => id);
}

let recallVec = 0, mrrVec = 0, recallFused = 0, mrrFused = 0;
for (const p of probeIdx) {
  const { top: vecTop, relevant } = vectorTopK(p);
  const kwTop = kwArm.ranklists[String(p)] ?? [];
  const fused = fuse(vecTop, kwTop);
  const sv = scoreSet(vecTop, relevant);
  const sf = scoreSet(fused, relevant);
  recallVec += sv.recall; mrrVec += sv.mrr;
  recallFused += sf.recall; mrrFused += sf.mrr;
}
const n = probeIdx.length;
const vectorArm = { recall_at_topk: Number((recallVec / n).toFixed(4)), mrr: Number((mrrVec / n).toFixed(4)) };
const fusedArm = { recall_at_topk: Number((recallFused / n).toFixed(4)), mrr: Number((mrrFused / n).toFixed(4)) };
const keywordArm = { recall_at_topk: kwArm.recall_at_topk, mrr: kwArm.mrr };

const result = {
  what: `same-item retrieval, vector arm and fused RRF arm, ${opt.name ?? opt.f32}`,
  fusion_rule: 'fraction-weighted RRF, k=60, frac=1 for both arms (plain RRF -- the '
    + 'family\'s own upper bound; #6012-style calibration is ticket 0031\'s, deferred)',
  topk: TOPK, gap: GAP, rrf_k: RRF_K,
  corpus: { passages: N, items: byItem.size, eligible_probes: eligible.length },
  probes: { count: n, seed: opt.seed },
  keyword_arm: keywordArm,
  vector_arm: vectorArm,
  fused_arm: fusedArm,
  vector_arm_gain_over_keyword: Number((vectorArm.recall_at_topk - keywordArm.recall_at_topk).toFixed(4)),
  fused_gain_over_keyword: Number((fusedArm.recall_at_topk - keywordArm.recall_at_topk).toFixed(4)),
};
writeFileSync(opt.output, `${JSON.stringify(result, null, 2)}\n`);
console.error(
  `${opt.name ?? opt.f32}: keyword ${keywordArm.recall_at_topk} vector ${vectorArm.recall_at_topk} `
  + `fused ${fusedArm.recall_at_topk} (vec gain ${result.vector_arm_gain_over_keyword}, `
  + `fused gain ${result.fused_gain_over_keyword}) -> ${opt.output}`,
);
