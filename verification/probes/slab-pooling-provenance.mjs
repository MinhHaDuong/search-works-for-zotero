#!/usr/bin/env node
// Which pooling produced a committed float32 slab?
//
// Ticket 0421 found the transformers.js drivers hardcode `pooling: 'mean'` while pooling
// is a per-model property. That makes any slab produced through them suspect for a model
// that wants something else — but only if it WAS produced through them. `embed_corpus.py`
// drives sentence-transformers, which reads the model's own `1_Pooling/config.json` and
// pools correctly, and it writes a `<name>.meta.json` beside its output. Two slabs in
// `mrl/` have that sibling and two do not, which is suggestive and settles nothing:
// an absent file is not a provenance record.
//
// This settles it from the vectors themselves. Embed the first N passages of the same
// corpus, in the same order, at each candidate pooling, and see which one the slab's rows
// actually match. The two answers are not close together — a CLS vector and a mean vector
// of the same text are different vectors, not neighbours — so the verdict does not rest on
// a threshold. It rests on a gap.
//
// Library differences do not confound it. sentence-transformers (PyTorch) and
// transformers.js (ONNX) at the SAME pooling agree to within float noise, far closer than
// two poolings ever come, so this identifies the pooling whichever library wrote the slab.
//
//   node slab-pooling-provenance.mjs --pkg-root <dir> --slab <f32> --dim 384 \
//        --passages <passages.txt> --model Xenova/bge-small-en-v1.5 [--rows 8]
import { createRequire } from 'node:module';
import { openSync, readSync, closeSync, createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    slab: { type: 'string' },
    passages: { type: 'string' },
    model: { type: 'string' },
    dim: { type: 'string', default: '384' },
    rows: { type: 'string', default: '8' },
    'cache-dir': { type: 'string' },
    poolings: { type: 'string', default: 'mean,cls' },
  },
});
for (const k of ['pkg-root', 'slab', 'passages', 'model']) {
  if (!opt[k]) {
    console.error(`missing --${k}`);
    process.exit(2);
  }
}
const DIM = Number(opt.dim);
const ROWS = Number(opt.rows);

/** The first ROWS rows of the slab, each DIM float32s, read without loading the file. */
function readSlab(path) {
  const fd = openSync(path, 'r');
  const buf = Buffer.allocUnsafe(ROWS * DIM * 4);
  readSync(fd, buf, 0, buf.length, 0);
  closeSync(fd);
  const out = [];
  for (let r = 0; r < ROWS; r++) {
    out.push(Array.from(new Float32Array(buf.buffer, buf.byteOffset + r * DIM * 4, DIM)));
  }
  return out;
}

async function readPassages(path) {
  const out = [];
  const rl = createInterface({ input: createReadStream(path), crlfDelay: Infinity });
  for await (const line of rl) {
    out.push(line);
    if (out.length >= ROWS) break;
  }
  return out;
}

const cos = (a, b) => {
  let d = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i++) {
    d += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return na && nb ? d / Math.sqrt(na * nb) : 0;
};

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const transformers = await import(pathToFileURL(require.resolve('@huggingface/transformers')).href);
const { pipeline, env } = transformers;
if (opt['cache-dir']) env.cacheDir = opt['cache-dir'];

const slab = readSlab(opt.slab);
const texts = await readPassages(opt.passages);
if (texts.length < ROWS) {
  console.error(`only ${texts.length} passages available`);
  process.exit(2);
}

const extractor = await pipeline('feature-extraction', opt.model);
const result = { probe: 'slab-pooling-provenance', slab: opt.slab, model: opt.model, dim: DIM, rows: ROWS, per_pooling: {} };

for (const pooling of opt.poolings.split(',').map((s) => s.trim())) {
  const scores = [];
  for (let i = 0; i < ROWS; i++) {
    const t = await extractor(texts[i], { pooling, normalize: true });
    scores.push(cos(slab[i], Array.from(t.data)));
  }
  scores.sort((a, b) => a - b);
  result.per_pooling[pooling] = {
    min: Number(scores[0].toFixed(6)),
    median: Number(scores[Math.floor(scores.length / 2)].toFixed(6)),
    max: Number(scores[scores.length - 1].toFixed(6)),
  };
}

const ranked = Object.entries(result.per_pooling).sort((a, b) => b[1].median - a[1].median);
result.verdict = ranked[0][0];
result.margin = Number((ranked[0][1].median - ranked[1][1].median).toFixed(6));
console.log(JSON.stringify(result, null, 1));
