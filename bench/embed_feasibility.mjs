// Can a Zotero user actually run this model? Throughput in the runtime zoteus ships.
//
// Every recall figure in bench/results/0025-x1-recall/ is worthless to a user who cannot
// afford to compute the vectors. That is not a hypothetical: the strongest model measured
// there, Qwen3-Embedding-0.6B, is 600M parameters and would take days on a laptop. It is
// the CPU cost that makes its 0,9973 impractical, not the model — the same vectors were
// built on an A4000, a projected 1,58 h for 255 703 passages
// (bench/results/0025-x1-recall/gpu-feasibility.json), so a user with a GPU is the
// counter-example. This driver measures the other half of the trade.
//
// Two properties make the measurement mean something:
//
//   - **The right runtime.** zoteus embeds through `@huggingface/transformers` — ONNX in
//     Node, on the CPU. Timing PyTorch instead would measure a stack nobody ships, and
//     would understate these models, since ONNX Runtime is the faster of the two here.
//   - **The right text.** Passages are sampled across the real corpus at a fixed stride,
//     not taken from the head. The corpus is stored in item order, so its first N lines are
//     one topic at one length — and length is what an embedder's cost tracks.
//
// The package is resolved from a directory the caller names, the way vec_real_measure.mjs
// resolves sqlite-vec from the fork checkout, so the repo takes on no npm dependency:
//
//   mkdir -p /tmp/tjs && cd /tmp/tjs && npm init -y && npm i @huggingface/transformers
//   node bench/embed_feasibility.mjs --pkg-root /tmp/tjs --corpus <passages.txt> --output f.json
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { cpus, hostname, loadavg, totalmem } from 'node:os';
import { resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    corpus: { type: 'string' },
    output: { type: 'string' },
    // Registry ids, resolved through bench/models.json. A literal owner/name still
    // works and warns, so an ad-hoc run stays possible without a record.
    models: {
      type: 'string',
      default: 'all-minilm-l6-v2,bge-small-en-v15,nomic-embed-text-v15',
    },
    rows: { type: 'string', default: '200' },
    batch: { type: 'string', default: '8' },
    scale: { type: 'string', default: '255703' },
  },
});
if (!opt['pkg-root'] || !opt.corpus || !opt.output) {
  console.error(
    'usage: node bench/embed_feasibility.mjs --pkg-root <dir with @huggingface/transformers> ' +
      '--corpus <passages.txt> --output <f.json>',
  );
  process.exit(2);
}
const ROWS = Number(opt.rows);
const BATCH = Number(opt.batch);
const SCALE = Number(opt.scale);

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const { pipeline } = await import(
  pathToFileURL(require.resolve('@huggingface/transformers')).href
);

const all = readFileSync(opt.corpus, 'utf8').split('\n').filter(Boolean);
const step = Math.max(1, Math.floor(all.length / ROWS));
const texts = Array.from({ length: ROWS }, (_, i) => all[i * step]).filter(Boolean);
const meanChars = Math.round(texts.reduce((a, t) => a + t.length, 0) / texts.length);

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

  const t0 = performance.now();
  const extractor = await pipeline('feature-extraction', model);
  const loadMs = performance.now() - t0;

  // One warm batch before timing: the first call pays graph initialisation, which a user
  // pays once per session rather than once per passage.
  await extractor(texts.slice(0, BATCH), { pooling, normalize: true });

  const t1 = performance.now();
  let dim = 0;
  for (let i = 0; i < texts.length; i += BATCH) {
    const out = await extractor(texts.slice(i, i + BATCH), { pooling, normalize: true });
    dim = out.dims[out.dims.length - 1];
  }
  const perRow = (performance.now() - t1) / texts.length;

  const row = {
    // The repository is what was loaded; the registry id is what the run was asked
    // for. They differ whenever a model is loaded from a mirror.
    model,
    model_id: token,
    dim,
    load_ms: +loadMs.toFixed(0),
    ms_per_passage: +perRow.toFixed(1),
    passages_per_min: Math.round(60000 / perRow),
    hours_to_index: +((SCALE * perRow) / 3600000).toFixed(2),
  };
  models.push(row);
  console.error(
    `${model.padEnd(38)} dim ${String(row.dim).padStart(4)}  ${String(row.ms_per_passage).padStart(6)} ms/passage  ` +
      `${String(row.passages_per_min).padStart(4)}/min  ${row.hours_to_index} h`,
  );
}

writeFileSync(
  opt.output,
  `${JSON.stringify(
    {
      what: 'local embedding throughput in the runtime zoteus ships (@huggingface/transformers, ONNX, CPU)',
      when: new Date().toISOString(),
      why: 'a recall figure is worthless to a user who cannot afford to compute the vectors',
      sample: { rows: texts.length, mean_chars: meanChars, batch: BATCH, corpus: opt.corpus },
      hours_to_index_is_for: SCALE,
      models,
      caveats: [
        'Wall clock on one machine with the CPUs below. A laptop has fewer and will be slower.',
        'ONNX Runtime chooses its own thread count here; this is the out-of-the-box behaviour ' +
          'a user gets, not a tuned one.',
        'Load time is a one-off per session and is reported apart from the per-passage cost.',
        'Cost, not quality. Read it beside the recall artifacts, never instead of them.',
      ],
      machine: {
        host: hostname(),
        cpus: cpus().length,
        cpu_model: cpus()[0]?.model ?? null,
        total_mem_bytes: totalmem(),
        loadavg: loadavg(),
        node: process.version,
      },
    },
    null,
    2,
  )}\n`,
);
console.error(`\nwrote ${opt.output}`);
