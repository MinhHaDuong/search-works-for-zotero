// Embed a fixed cross-lingual probe pool and query set for one (model, dtype).
//
// Ticket 0266: does an EN or FR query retrieve the relevant non-English passage at the
// deployed dtype? This driver does the embedding half only — it applies the registry's
// per-model input template (query: / passage: prefixes) and pooling, embeds the pool once
// and the queries once, and writes raw float32 vectors plus an id-ordered manifest. A
// separate scorer (cross_lingual_score.py) computes cosine similarity, ranks the pool for
// each query, and reports hit@k per (query_lang, target_lang) pair.
//
// Why a new driver rather than reusing quant_fidelity.mjs: that driver deliberately skips
// the input template (it is comparing dtypes on the SAME raw text, so a constant offset
// cancels) and has no separate query set — it treats the one corpus sample as both "queries"
// and "answers" via leave-one-out. This probe needs the template applied for real, because a
// wrong prefix under- or over-states retrieval quality exactly the way it would for a real
// user (see models.json's registry note and tracker 0240's e5-prefix finding). It also needs
// two distinct, hand-curated text sets (queries with known relevant pool passages) rather
// than a stride sample.
//
// One process per (model, dtype) cell, as the rest of the 0240 study does.
//
//   node bench/cross_lingual_probe.mjs --pkg-root <dir> \
//     --pool /home/haduong/data/projets/zoteus-bench/0266/pool.jsonl \
//     --queries /home/haduong/data/projets/zoteus-bench/0266/queries.jsonl \
//     --model multilingual-e5-small --dtype q8 \
//     --out-prefix /home/haduong/data/projets/zoteus-bench/0266/vectors/multilingual-e5-small-q8
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { cpus, hostname } from 'node:os';
import { resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    pool: { type: 'string' },
    queries: { type: 'string' },
    'out-prefix': { type: 'string' },
    model: { type: 'string', default: 'nomic-embed-text-v15' },
    dtype: { type: 'string' },
    device: { type: 'string' },
    batch: { type: 'string', default: '8' },
  },
});
if (!opt['pkg-root'] || !opt.pool || !opt.queries || !opt['out-prefix']) {
  console.error(
    'usage: node bench/cross_lingual_probe.mjs --pkg-root <dir> --pool <pool.jsonl> ' +
      '--queries <queries.jsonl> --out-prefix <path> [--model M] [--dtype q8] [--device cpu] [--batch 8]',
  );
  process.exit(2);
}
const BATCH = Number(opt.batch);

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const { pipeline } = await import(
  pathToFileURL(require.resolve('@huggingface/transformers')).href
);

function readJsonl(path) {
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

const pool = readJsonl(opt.pool);
const queries = readJsonl(opt.queries);

const { id: modelId, repo: modelRepo, template, pooling } = resolveModel(opt.model);
if (!pooling) {
  throw new Error(
    `[pooling] ${opt.model} declares no pooling. Add it to models.json before measuring.`,
  );
}
if (!template) {
  throw new Error(`[template] ${opt.model} declares no input_template.`);
}

const pipelineOpts = {};
if (opt.dtype) pipelineOpts.dtype = opt.dtype;
if (opt.device) pipelineOpts.device = opt.device;

const t0 = performance.now();
const extractor = await pipeline('feature-extraction', modelRepo, pipelineOpts);
const loadMs = performance.now() - t0;

async function embedAll(texts, prefix, label) {
  let dim = 0;
  const chunks = [];
  const t1 = performance.now();
  for (let i = 0; i < texts.length; i += BATCH) {
    const batch = texts.slice(i, i + BATCH).map((t) => `${prefix}${t}`);
    const tensor = await extractor(batch, { pooling, normalize: false });
    const data = tensor.data;
    dim = data.length / batch.length;
    chunks.push(Float32Array.from(data));
  }
  const embedMs = performance.now() - t1;
  const flat = new Float32Array(texts.length * dim);
  let at = 0;
  for (const c of chunks) {
    flat.set(c, at);
    at += c.length;
  }
  console.error(
    `${label}: ${texts.length}x${dim} in ${(embedMs / 1000).toFixed(1)}s ` +
      `(${(embedMs / texts.length).toFixed(0)} ms/item, prefix=${JSON.stringify(prefix)})`,
  );
  return { flat, dim, embedMs };
}

const poolTexts = pool.map((p) => p.text);
const queryTexts = queries.map((q) => q.text);

const poolEmb = await embedAll(poolTexts, template.passage ?? '', `${modelId} ${opt.dtype} pool`);
const queryEmb = await embedAll(queryTexts, template.query ?? '', `${modelId} ${opt.dtype} queries`);
if (poolEmb.dim !== queryEmb.dim) {
  throw new Error(`pool dim ${poolEmb.dim} != query dim ${queryEmb.dim}`);
}

writeFileSync(`${opt['out-prefix']}.pool.f32`, Buffer.from(poolEmb.flat.buffer, 0, poolEmb.flat.byteLength));
writeFileSync(`${opt['out-prefix']}.query.f32`, Buffer.from(queryEmb.flat.buffer, 0, queryEmb.flat.byteLength));
writeFileSync(
  `${opt['out-prefix']}.json`,
  `${JSON.stringify(
    {
      model: modelRepo,
      model_id: modelId,
      dtype: opt.dtype ?? '(runtime default)',
      device: opt.device ?? '(runtime default)',
      pooling,
      template,
      dim: poolEmb.dim,
      pool_ids: pool.map((p) => p.pool_id),
      query_ids: queries.map((q) => q.query_id),
      pool_rows: pool.length,
      query_rows: queries.length,
      normalized: false,
      load_ms: Number(loadMs.toFixed(1)),
      pool_embed_ms: Number(poolEmb.embedMs.toFixed(1)),
      query_embed_ms: Number(queryEmb.embedMs.toFixed(1)),
      runtime: '@huggingface/transformers in Node (ONNX)',
      machine: { host: hostname(), cpus: cpus().length, node: process.version },
    },
    null,
    2,
  )}\n`,
);
console.error(
  `${modelRepo} ${opt.dtype ?? 'default'}: done, pool=${pool.length} queries=${queries.length}`,
);
