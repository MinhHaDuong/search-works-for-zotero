// What every semantic query pays to embed the query string.
//
// embed_feasibility.mjs measures the BUILD side: passages per minute, batch 8, the cost a
// user pays once. This measures the other end of the same model choice — the cost paid on
// every query, forever, at batch 1, on whatever machine serves. The two are not the same
// question and they do not have the same answer: a GPU erases the build cost and leaves the
// query cost untouched, because at batch 1 there is nothing left to parallelise.
//
// Both numbers matter, and the second one is the one SPEC.md §5.2.9 budgets: "embed 20–50 ms"
// inside a 300–700 ms typical query, and "~120 MB of query model" inside the ratified 300 MB
// server RSS of SPEC.md C3. A model that misses either bound is unshippable on the
// default path no matter how well it retrieves.
//
// Two properties make the measurement mean something:
//
//   - **Batch 1, real query strings.** A query is ~10-20 tokens, not a 1 130-character
//     passage, and it arrives alone. Timing a batch of passages measures the build path.
//   - **Marginal RSS.** Reported as the delta across the load of each model, measured in one
//     process, so later models see an allocator arena the earlier ones warmed. That is the
//     safe direction for a ceiling check — it never flatters a model — but read it as a
//     ceiling, not a precise resident cost.
//
// `--dtype` is the lever worth sweeping: upstream's LocalEmbeddingProvider passes none, so
// the shipped path gets full precision. `--device` likewise: @huggingface/transformers 4.x
// accepts auto|cpu|gpu|cuda|webgpu|coreml|dml|webnn, and upstream passes nothing.
//
// The package is resolved from a directory the caller names, as embed_feasibility.mjs does,
// so the repo takes on no npm dependency:
//
//   mkdir -p /tmp/tjs && cd /tmp/tjs && npm init -y && npm i @huggingface/transformers
//   node bench/query_embed_cost.mjs --pkg-root /tmp/tjs --output q.json
//   node bench/query_embed_cost.mjs --pkg-root /tmp/tjs --dtype q8 --output q8.json
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { cpus, hostname, loadavg, totalmem } from 'node:os';
import { resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    output: { type: 'string' },
    // Registry ids, resolved through bench/models.json. A literal owner/name still
    // works and warns, so an ad-hoc run stays possible without a record.
    models: {
      type: 'string',
      default: 'all-minilm-l6-v2,bge-small-en-v15,nomic-embed-text-v15',
    },
    dtype: { type: 'string' },
    device: { type: 'string' },
    reps: { type: 'string', default: '12' },
  },
});
if (!opt['pkg-root'] || !opt.output) {
  console.error(
    'usage: node bench/query_embed_cost.mjs --pkg-root <dir with @huggingface/transformers> ' +
      '--output <q.json> [--dtype q8] [--device auto] [--models a,b,c] [--reps 12]',
  );
  process.exit(2);
}
const REPS = Number(opt.reps);

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const { pipeline } = await import(
  pathToFileURL(require.resolve('@huggingface/transformers')).href
);

// Five real queries, not one: query length drives the cost and a single probe hides its
// spread. Natural-language and keyword shapes, mixed deliberately.
const QUERIES = [
  'what did Nordhaus say about the social cost of carbon',
  'inventing climate finance',
  'heterogeneous agent models of the energy transition',
  'coal phase-out Vietnam',
  'discount rate intergenerational equity',
];

const mb = (bytes) => Number((bytes / 1048576).toFixed(1));
const pipelineOpts = {};
if (opt.dtype) pipelineOpts.dtype = opt.dtype;
if (opt.device) pipelineOpts.device = opt.device;

const models = [];
for (const token of opt.models.split(',').map((s) => s.trim())) {
  const { repo: model, pooling } = resolveModel(token);
  if (!pooling) {
    // Never silently 'mean': that default is wrong for four of the six
    // candidates, and wrong pooling reads as the model being worse.
    throw new Error(
      `[pooling] ${token} declares no pooling. Add it to models.json (read it from ` +
        `the model's own 1_Pooling/config.json) before measuring with it.`,
    );
  }

  const rssBefore = process.memoryUsage().rss;
  const t0 = performance.now();
  const extractor = await pipeline('feature-extraction', model, pipelineOpts);
  const loadMs = performance.now() - t0;

  // One warm call before timing and before reading RSS: the first call pays graph
  // initialisation and allocates the arena, both of which a user pays once per session.
  const warm = await extractor(QUERIES[0], { pooling, normalize: true });
  const rssAfter = process.memoryUsage().rss;

  const times = [];
  for (let rep = 0; rep < REPS; rep++) {
    for (const query of QUERIES) {
      const t = performance.now();
      await extractor(query, { pooling, normalize: true });
      times.push(performance.now() - t);
    }
  }
  times.sort((a, b) => a - b);
  const at = (q) => Number(times[Math.min(times.length - 1, Math.floor(times.length * q))].toFixed(1));

  models.push({
    // The repository is what was loaded; the registry id is what the run was asked
    // for. They differ whenever a model is loaded from a mirror, and a cell that
    // records only the first cannot be traced back to its record.
    model,
    model_id: token,
    dim: warm.data.length,
    dtype: opt.dtype ?? '(runtime default)',
    device: opt.device ?? '(runtime default)',
    load_ms: Number(loadMs.toFixed(1)),
    rss_before_mb: mb(rssBefore),
    rss_after_load_mb: mb(rssAfter),
    rss_delta_mb: mb(rssAfter - rssBefore),
    query_ms_min: at(0),
    query_ms_median: at(0.5),
    query_ms_p95: at(0.95),
    n: times.length,
  });
  console.error(`done ${model}`);
}

writeFileSync(
  opt.output,
  `${JSON.stringify(
    {
      what: 'query-time embedding cost at batch 1 — the cost every semantic query pays',
      when: new Date().toISOString(),
      why: 'SPEC.md §5.2.9 budgets 20–50 ms and ~120 MB for the query model; a model that misses either bound is unshippable on the default path however well it retrieves',
      runtime: '@huggingface/transformers in Node (ONNX), the runtime zoteus ships',
      batch: 1,
      reps: REPS,
      queries: QUERIES.length,
      models,
      caveats: [
        'RSS is a marginal delta measured in one process, models loaded in sequence, so later models see a warmed allocator arena. Read it as a ceiling on the resident cost, not as a precise figure.',
        'Wall clock on one machine. A laptop has fewer cores and will be slower.',
        'Cost, not quality. Read it beside the recall artifacts in 0025-x1-recall/, never instead of them.',
        'Load time is a one-off per session and is reported apart from the per-query cost.',
      ],
      machine: {
        host: hostname(),
        cpus: cpus().length,
        cpu_model: cpus()[0]?.model,
        total_mem_bytes: totalmem(),
        loadavg: loadavg(),
        node: process.version,
      },
    },
    null,
    2,
  )}\n`,
);
console.error(`wrote ${opt.output}`);
