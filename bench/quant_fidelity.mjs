// Embed one fixed passage sample at one dtype, so the quantization ladder can be scored.
//
// query_embed_cost.mjs prices a dtype. It cannot say whether the cheaper dtype still
// retrieves, and a cost curve without a quality curve recommends the cheapest point on it.
// This driver produces the other axis: the same passages, embedded at each rung, written as
// raw float32 so a scorer can compare rungs against fp32.
//
// One property makes the comparison mean something, and it is the reason this does not read
// the vectors already on disk. The committed corpora in zoteus-bench/mrl/ were built with
// sentence-transformers on PyTorch (`max_seq_length: 512`, per their meta), while zoteus
// embeds through ONNX. Scoring a dtype against those would conflate quantization damage with
// the PyTorch-versus-ONNX stack difference and attribute the sum to quantization. So fp32
// here means *ONNX fp32, produced by this same driver*, and every rung is compared against
// that. The cross-stack question is real and separate; --reference-f32 measures it.
//
// One process per dtype, deliberately: a cold ONNX Runtime arena per run, and no chance of
// an 8-rung sweep holding eight models resident.
//
//   node bench/quant_fidelity.mjs --pkg-root /tmp/tjs --corpus <passages.txt> \
//     --dtype q4 --rows 400 --out-prefix /tmp/fid/nomic-q4
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { cpus, hostname } from 'node:os';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    corpus: { type: 'string' },
    'out-prefix': { type: 'string' },
    model: { type: 'string', default: 'nomic-ai/nomic-embed-text-v1.5' },
    dtype: { type: 'string' },
    device: { type: 'string' },
    rows: { type: 'string', default: '400' },
    batch: { type: 'string', default: '8' },
  },
});
if (!opt['pkg-root'] || !opt.corpus || !opt['out-prefix']) {
  console.error(
    'usage: node bench/quant_fidelity.mjs --pkg-root <dir> --corpus <passages.txt> ' +
      '--out-prefix <path> [--model M] [--dtype q4] [--rows 400] [--batch 8]',
  );
  process.exit(2);
}
const ROWS = Number(opt.rows);
const BATCH = Number(opt.batch);

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const { pipeline } = await import(
  pathToFileURL(require.resolve('@huggingface/transformers')).href
);

// Fixed stride, not the head: the corpus is stored in item order, so its first N lines are
// one topic at one length. The stride is a function of ROWS alone, so every dtype sees the
// identical sample and the rungs are comparable row by row.
const all = readFileSync(opt.corpus, 'utf8').split('\n').filter(Boolean);
const step = Math.max(1, Math.floor(all.length / ROWS));
const rowIndex = Array.from({ length: ROWS }, (_, i) => i * step).filter((i) => i < all.length);
const texts = rowIndex.map((i) => all[i]);

const pipelineOpts = {};
if (opt.dtype) pipelineOpts.dtype = opt.dtype;
if (opt.device) pipelineOpts.device = opt.device;

const t0 = performance.now();
const extractor = await pipeline('feature-extraction', opt.model, pipelineOpts);
const loadMs = performance.now() - t0;

// Raw vectors, not normalised: the scorer computes its own norms, matching the convention of
// the committed corpora (see their meta: "the recall driver computes its own norms").
// Progress to stderr every ~10%: an fp32 rung over a few hundred passages runs for many
// minutes, and a driver that prints nothing until it finishes cannot be told apart from one
// that has hung. The ETA is a linear extrapolation of the batches done so far, which is
// honest for a uniform sample and would mislead on a skewed one.
const t1 = performance.now();
let dim = 0;
const chunks = [];
const reportEvery = Math.max(1, Math.floor(texts.length / BATCH / 10));
let batchNo = 0;
for (let i = 0; i < texts.length; i += BATCH) {
  const batch = texts.slice(i, i + BATCH);
  const tensor = await extractor(batch, { pooling: 'mean', normalize: false });
  const data = tensor.data;
  dim = data.length / batch.length;
  chunks.push(Float32Array.from(data));
  if (++batchNo % reportEvery === 0) {
    const done = Math.min(i + BATCH, texts.length);
    const elapsed = (performance.now() - t1) / 1000;
    const eta = (elapsed / done) * (texts.length - done);
    console.error(
      `  ${done}/${texts.length} in ${elapsed.toFixed(0)}s (${((elapsed * 1000) / done).toFixed(0)} ms/passage, ~${eta.toFixed(0)}s left)`,
    );
  }
}
const embedMs = performance.now() - t1;

const flat = new Float32Array(texts.length * dim);
let at = 0;
for (const c of chunks) {
  flat.set(c, at);
  at += c.length;
}

writeFileSync(`${opt['out-prefix']}.f32`, Buffer.from(flat.buffer, 0, flat.byteLength));
writeFileSync(
  `${opt['out-prefix']}.json`,
  `${JSON.stringify(
    {
      model: opt.model,
      dtype: opt.dtype ?? '(runtime default)',
      device: opt.device ?? '(runtime default)',
      dim,
      rows: texts.length,
      stride: step,
      row_index: rowIndex,
      corpus: opt.corpus,
      batch: BATCH,
      load_ms: Number(loadMs.toFixed(1)),
      embed_ms: Number(embedMs.toFixed(1)),
      ms_per_passage: Number((embedMs / texts.length).toFixed(2)),
      mean_chars: Math.round(texts.reduce((a, t) => a + t.length, 0) / texts.length),
      normalized: false,
      runtime: '@huggingface/transformers in Node (ONNX)',
      machine: { host: hostname(), cpus: cpus().length, node: process.version },
    },
    null,
    2,
  )}\n`,
);
console.error(
  `${opt.model} ${opt.dtype ?? 'default'}: ${texts.length}x${dim} in ${(embedMs / 1000).toFixed(1)}s ` +
    `(${(embedMs / texts.length).toFixed(0)} ms/passage)`,
);
