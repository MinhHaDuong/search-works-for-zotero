// Is a small embedding model good enough? A model-independent retrieval task.
//
// bench/vec_mrl_recall.mjs cannot answer that question, and it is worth being explicit
// about why: it scores an approximation against the exact ranking OF THE SAME MODEL. That
// is the right question for a quantizer — it measures what the shortcut costs — but every
// model is its own reference there, so a model that ranks badly and a model that ranks well
// both score 1,0 against themselves. Comparing two models needs a target outside both.
//
// The target here is the library's own structure: **passages of one Zotero item are about
// the same thing.** So a passage drawn from item X is a query whose relevant set is the
// OTHER passages of item X. No human labels, no second model, identical for every embedder.
//
// Adjacent chunks are excluded from both the relevant set and the candidate list, by
// `--gap`. They are the reason a naive version of this task is worthless: the chunker
// overlaps by 150 characters, so chunk i and chunk i+1 share text outright and any
// embedder retrieves them. That would measure near-duplicate detection, saturate near 1,0,
// and rank a bag-of-characters above a language model. Requiring a gap of several chunks
// asks the real question instead: does this model recognise two DIFFERENT parts of one
// document as belonging together?
//
// What this proxy is not: it is document-level topical relatedness, not query-to-answer
// relevance. A model could score well here and still answer a user's question poorly. It
// is a floor — it can show a model is too weak, and it cannot certify one is good enough.
import { openSync, readSync, fstatSync, closeSync, readFileSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { cpus, hostname, totalmem } from 'node:os';

const { values: opt } = parseArgs({
  options: {
    f32: { type: 'string', multiple: true },
    dim: { type: 'string', multiple: true },
    name: { type: 'string', multiple: true },
    widths: { type: 'string', multiple: true },
    items: { type: 'string' },
    ords: { type: 'string' },
    output: { type: 'string' },
    probes: { type: 'string', default: '400' },
    topk: { type: 'string', default: '30' },
    gap: { type: 'string', default: '3' },
    seed: { type: 'string', default: '20260829' },
  },
});
if (!opt.f32 || !opt.dim || !opt.items || !opt.ords || !opt.output) {
  console.error(
    'usage: node bench/vec_task_recall.mjs --f32 <a.f32> --dim <D> [--name <label>] ' +
      '[--widths 1024,512] (repeat the four per model) --items <f> --ords <f> --output <json>',
  );
  process.exit(2);
}
if (opt.f32.length !== opt.dim.length) {
  console.error('--f32 and --dim must be repeated the same number of times');
  process.exit(2);
}
const TOPK = Number(opt.topk);
const PROBES = Number(opt.probes);
const GAP = Number(opt.gap);

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const items = readFileSync(opt.items, 'utf8').split('\n').filter(Boolean);
const ords = readFileSync(opt.ords, 'utf8').split('\n').filter(Boolean).map(Number);
const N = items.length;
if (ords.length !== N) {
  console.error(`items (${N}) and ords (${ords.length}) disagree`);
  process.exit(2);
}

// Group passages by item once: the relevant set and the exclusion set both come from here.
const byItem = new Map();
for (let i = 0; i < N; i++) {
  if (!byItem.has(items[i])) byItem.set(items[i], []);
  byItem.get(items[i]).push(i);
}

/**
 * Probes that CAN be answered, drawn once and shared by every model.
 *
 * A passage whose item has no chunk `--gap` away has an empty relevant set: it scores zero
 * for every model, and averaging it in would dilute every figure by the same constant
 * while making the numbers depend on the corpus's document-length distribution rather than
 * on the embedder. Such probes are excluded from the draw, and their count is reported —
 * a metric whose denominator is silently chosen is a metric that can be tuned.
 */
const rnd = mulberry32(Number(opt.seed));
const eligible = [];
for (let i = 0; i < N; i++) {
  const sibs = byItem.get(items[i]);
  if (sibs.some((j) => j !== i && Math.abs(ords[j] - ords[i]) >= GAP)) eligible.push(i);
}
const probeIdx = [];
const seen = new Set();
while (probeIdx.length < Math.min(PROBES, eligible.length)) {
  const p = eligible[Math.floor(rnd() * eligible.length)];
  if (!seen.has(p)) {
    seen.add(p);
    probeIdx.push(p);
  }
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
  while (off < bytes) off += readSync(fd, buf, off, Math.min(1 << 24, bytes - off), off);
  closeSync(fd);
  const all = new Float32Array(buf.buffer, buf.byteOffset, bytes / 4);
  return Array.from({ length: n }, (_, i) => all.subarray(i * dim, (i + 1) * dim));
}

/** Recall@TOPK and MRR of the same-item, non-adjacent passages, at one width. */
function score(vecs, w) {
  let recall = 0;
  let mrr = 0;
  const norms = vecs.map((v) => {
    let s = 0;
    for (let i = 0; i < w; i++) s += v[i] * v[i];
    return Math.sqrt(s) || 1;
  });
  for (const p of probeIdx) {
    const q = vecs[p];
    const qn = norms[p];
    const mine = items[p];
    const myOrd = ords[p];
    // Near chunks are removed from the CANDIDATES, not merely from the relevant set: left
    // in, they would occupy the top slots with text they literally share, and the score
    // would read as retrieval success.
    const relevant = new Set(
      byItem.get(mine).filter((j) => j !== p && Math.abs(ords[j] - myOrd) >= GAP),
    );
    const top = [];
    for (let i = 0; i < N; i++) {
      if (items[i] === mine && !relevant.has(i)) continue;
      const v = vecs[i];
      let d = 0;
      for (let k = 0; k < w; k++) d += q[k] * v[k];
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
    const hits = top.filter((t) => relevant.has(t.i)).length;
    recall += hits / Math.min(relevant.size, TOPK);
    const rank = top.findIndex((t) => relevant.has(t.i));
    if (rank >= 0) mrr += 1 / (rank + 1);
  }
  return {
    width: w,
    bytes_per_vector: w * 4,
    recall_at_topk: +(recall / probeIdx.length).toFixed(4),
    mrr: +(mrr / probeIdx.length).toFixed(4),
  };
}

const models = [];
for (let m = 0; m < opt.f32.length; m++) {
  const dim = Number(opt.dim[m]);
  const label = opt.name?.[m] ?? opt.f32[m];
  const widths = (opt.widths?.[m] ? opt.widths[m].split(',').map(Number) : [dim]).filter(
    (w) => w <= dim,
  );
  const vecs = loadVectors(opt.f32[m], dim);
  const at = widths.map((w) => {
    const r = score(vecs, w);
    console.error(
      `${label.padEnd(34)} width ${String(w).padStart(5)}  recall@${TOPK} ${r.recall_at_topk.toFixed(4)}  MRR ${r.mrr.toFixed(4)}`,
    );
    return r;
  });
  models.push({ name: label, file: opt.f32[m], full_dim: dim, at });
}

writeFileSync(
  opt.output,
  `${JSON.stringify(
    {
      what: 'same-item retrieval quality: a model-independent target for comparing embedders',
      when: new Date().toISOString(),
      task: {
        relevant: `other passages of the probe's own Zotero item, at least ${GAP} chunks away`,
        excluded_from_candidates: `the probe's own item's passages within ${GAP} chunks of it`,
        why_the_gap:
          'the chunker overlaps by 150 characters, so adjacent chunks share text outright ' +
          'and any embedder retrieves them; without the gap this measures near-duplicate ' +
          'detection and saturates',
        topk: TOPK,
      },
      corpus: { passages: N, items: byItem.size, eligible_probes: eligible.length },
      probes: { count: probeIdx.length, seed: Number(opt.seed) },
      models,
      caveats: [
        'Same-item relatedness is document-level topical coherence, not query-to-answer ' +
          'relevance. This proxy can show a model is too weak; it cannot certify one is ' +
          'good enough for a user’s real questions.',
        'Recall is divided by min(relevant, topk), so an item with more than topk eligible ' +
          'siblings is not penalised for the ones that cannot fit.',
        'Comparing two DIFFERENT models here conflates dimension with architecture, size ' +
          'and training data. Only the widths WITHIN one Matryoshka model isolate dimension.',
      ],
      machine: { host: hostname(), cpus: cpus().length, mem: totalmem(), node: process.version },
    },
    null,
    2,
  )}\n`,
);
console.error(`\nwrote ${opt.output}`);
