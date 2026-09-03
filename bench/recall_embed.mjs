// Embed EVERY passage of ticket 0265's recall subsample at one (candidate, dtype), so
// bench/vec_task_recall.mjs can score same-item retrieval on vectors the deployed dtype
// actually produced -- not on fp32 vectors standing in for a quantized configuration.
//
// Why this is not bench/quant_fidelity.mjs run with a bigger --rows. Two contract
// differences, both load-bearing for recall and both irrelevant to fidelity:
//
//   1. quant_fidelity.mjs takes a FIXED STRIDE SAMPLE of --rows passages out of
//      whatever corpus it is given (a fidelity cell only ever needs "the same 600
//      passages every rung sees", never the whole file). A recall cell needs every
//      row of the subsample embedded, aligned 1:1 with the items/ords files ticket
//      0265 built, or vec_task_recall.mjs's positional pairing goes silently wrong.
//   2. quant_fidelity.mjs drops the registry's `input_template` entirely (resolveModel
//      returns it; the driver never reads it) -- so the 0263 fidelity numbers this
//      campaign reuses as-is were measured WITHOUT the query-role/passage-role prefixes
//      e5-family models declare they need. That is an accepted, documented limitation
//      of the already-committed fidelity numbers (ticket 0240's tracker: an
//      unprefixed e5 under-measures itself). This campaign's OWN recall vectors are
//      new measurements, not a reuse of committed numbers, so the same shortcut is not
//      free here and this driver does not take it.
//
// Every text is embedded with the model's PASSAGE-role prefix (never the query-role
// prefix), uniformly, whether it is later used as a probe or as a candidate. This task
// is document-to-document topical relatedness, not a short user query against a
// passage corpus (bench/vec_task_recall.mjs's own header states the same caveat) -- so
// treating every text as a "passage" for template purposes is the semantically correct
// choice, not a simplification of convenience, and it also means a probe's query-time
// embedding and its candidate-time embedding are the SAME vector, which is what the
// same-item task already assumes (one embedding per passage, used both ways).
//
//   node bench/recall_embed.mjs --pkg-root /tmp/tjs --corpus subsample-passages.txt \
//     --model multilingual-e5-small --dtype q8 --out-prefix /tmp/recall/e5-small-q8
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { cpus, hostname } from 'node:os';
import { loadRegistry, resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    corpus: { type: 'string' },
    'out-prefix': { type: 'string' },
    model: { type: 'string' },
    dtype: { type: 'string' },
    device: { type: 'string' },
    batch: { type: 'string', default: '8' },
    // MEASURES A DEFECT; NEVER USE FOR A RECALL CELL THAT STANDS FOR A MODEL. Runs the
    // wrong pooling on purpose, so the cost of upstream's one hardcoded mode can be read on
    // the task metric rather than on a cross-lingual probe -- which matters because the two
    // do not agree in sign for every model. The cell records `pooling_forced` and the
    // declared value, so no downstream reader can mistake it for a measurement of the model.
    'force-pooling': { type: 'string' },
  },
});
if (!opt['pkg-root'] || !opt.corpus || !opt['out-prefix'] || !opt.model || !opt.dtype) {
  console.error(
    'usage: node bench/recall_embed.mjs --pkg-root <dir> --corpus <passages.txt> ' +
      '--out-prefix <path> --model M --dtype q8 [--device cpu] [--batch 8]',
  );
  process.exit(2);
}
const BATCH = Number(opt.batch);

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const { pipeline } = await import(
  pathToFileURL(require.resolve('@huggingface/transformers')).href
);

const texts = readFileSync(opt.corpus, 'utf8').split('\n').filter(Boolean);

const { id: modelId, repo: modelRepo, pooling: declaredPooling, normalize, template } =
  resolveModel(opt.model);
if (!declaredPooling) {
  throw new Error(`[pooling] ${opt.model} declares no pooling. Add it to models.json before measuring.`);
}
// The declared value stays required even when it is overridden: an ablation is readable
// only against a model whose correct pooling is known, and the cell records both.
const POOLING_MODES = [
  ...new Set(loadRegistry().models.map((entry) => entry.pooling).filter(Boolean)),
].sort();
if (opt['force-pooling'] && !POOLING_MODES.includes(opt['force-pooling'])) {
  throw new Error(
    `[pooling] --force-pooling ${opt['force-pooling']} is not one of ${POOLING_MODES.join(', ')}`,
  );
}
const pooling = opt['force-pooling'] ?? declaredPooling;
if (opt['force-pooling']) {
  console.error(
    `[ablation] ${modelId} declares pooling=${declaredPooling}; running ${pooling} on purpose. ` +
      'This cell measures a defect, not the model.',
  );
}
const prefix = template?.passage ?? '';
const prefixed = prefix ? texts.map((t) => prefix + t) : texts;

const pipelineOpts = { dtype: opt.dtype };
if (opt.device) pipelineOpts.device = opt.device;

const t0 = performance.now();
const extractor = await pipeline('feature-extraction', modelRepo, pipelineOpts);
const loadMs = performance.now() - t0;


// One warm batch before the clock, matching embed_feasibility.mjs. Without it the first
// batch pays graph initialisation — and, on a model the cache has never seen, the
// download — inside the window that becomes ms_per_passage. Ticket 0260: that protocol
// error put 45 to 49 MB of error into a set of RSS figures, in BOTH directions, four
// times larger than the 11,7 MB difference they were being used to argue about, and the
// mechanism built on them reached the ratification ledger before a re-measurement
// retracted it. The cost is one batch; the alternative is a number nobody can audit.
const tWarm = performance.now();
await extractor(prefixed.slice(0, BATCH), { pooling, normalize: false }); // raw-geometry: the consumer chooses, not this driver
const warmMs = performance.now() - tWarm;

const t1 = performance.now();
let dim = 0;
const chunks = [];
const reportEvery = Math.max(1, Math.floor(prefixed.length / BATCH / 20));
let batchNo = 0;
for (let i = 0; i < prefixed.length; i += BATCH) {
  const batch = prefixed.slice(i, i + BATCH);
  // raw-geometry: the vectors are written for downstream scorers that normalise as
  // they choose. Baking it in here would fix a decision belonging to the consumer.
  // Ticket 0486.
  const tensor = await extractor(batch, { pooling, normalize: false }); // raw-geometry: the consumer chooses, not this driver
  const data = tensor.data;
  dim = data.length / batch.length;
  chunks.push(Float32Array.from(data));
  if (++batchNo % reportEvery === 0) {
    const done = Math.min(i + BATCH, prefixed.length);
    const elapsed = (performance.now() - t1) / 1000;
    const eta = (elapsed / done) * (prefixed.length - done);
    console.error(
      `  ${done}/${prefixed.length} in ${elapsed.toFixed(0)}s ` +
        `(${((elapsed * 1000) / done).toFixed(0)} ms/passage, ~${eta.toFixed(0)}s left)`,
    );
  }
}
const embedMs = performance.now() - t1;

const flat = new Float32Array(prefixed.length * dim);
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
      model: modelRepo,
      model_id: modelId,
      dtype: opt.dtype,
      device: opt.device ?? '(runtime default)',
      dim,
      rows: prefixed.length,
      corpus: opt.corpus,
      input_template_role: 'passage',
      input_template_prefix: prefix,
      pooling,
      declared_pooling: declaredPooling,
      pooling_forced: Boolean(opt['force-pooling']),
      batch: BATCH,
      // One-time costs apart from the per-unit rate — see quant_fidelity.mjs and
      // ticket 0260. This driver carried the same defect and the ticket named only
      // its sibling; the adherence test is what found it.
      warm: true,
      load_ms: Number(loadMs.toFixed(1)),
      warm_ms: Number(warmMs.toFixed(1)),
      embed_ms: Number(embedMs.toFixed(1)),
      ms_per_passage: Number((embedMs / prefixed.length).toFixed(2)),
      // The registry's declared value, beside the value this run APPLIED. They differ
      // on purpose here (see the raw-geometry line above), and an artifact that
      // recorded only one of them could not say whether the difference was a choice
      // or the class recurring. Ticket 0486.
      normalize_declared: normalize,
      normalized: false,
      runtime: '@huggingface/transformers in Node (ONNX)',
      machine: { host: hostname(), cpus: cpus().length, node: process.version },
    },
    null,
    2,
  )}\n`,
);
console.error(
  `${modelRepo} ${opt.dtype}: ${prefixed.length}x${dim} in ${(embedMs / 1000).toFixed(1)}s ` +
    `(${(embedMs / prefixed.length).toFixed(0)} ms/passage, prefix ${JSON.stringify(prefix)})`,
);
