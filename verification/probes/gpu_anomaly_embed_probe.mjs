// Ticket 0481. A minimal, instrumentable sibling of quant_fidelity.mjs: embeds a fixed-stride
// sample of a corpus at one (model, dtype, device, batch), optionally with ONNX Runtime session
// profiling turned on. It exists because none of the five committed drivers expose ORT's
// per-node profile or let the caller vary batch size independently of the fidelity/cost split —
// this ticket's Actions need both, isolated from quantization scoring and from the query-cost
// batch-1 assumption.
//
//   node verification/probes/gpu_anomaly_embed_probe.mjs --pkg-root <dir> --corpus <passages.txt> \
//     --model multilingual-e5-small --dtype q8 --device cuda --rows 200 --batch 8 \
//     --out /tmp/out.json [--profile]
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, readdirSync, copyFileSync, unlinkSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { hostname } from 'node:os';
import { resolve as pathResolve } from 'node:path';
import { resolveModel } from '../../bench/registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    corpus: { type: 'string' },
    model: { type: 'string', default: 'multilingual-e5-small' },
    dtype: { type: 'string' },
    device: { type: 'string' },
    rows: { type: 'string', default: '200' },
    batch: { type: 'string', default: '8' },
    out: { type: 'string' },
    profile: { type: 'boolean', default: false },
    'profile-dir': { type: 'string', default: '.' },
  },
});
if (!opt['pkg-root'] || !opt.corpus || !opt.out) {
  console.error(
    'usage: node gpu_anomaly_embed_probe.mjs --pkg-root <dir> --corpus <passages.txt> --out <o.json> ' +
      '[--model M] [--dtype q8] [--device cuda] [--rows 200] [--batch 8] [--profile] [--profile-dir DIR]',
  );
  process.exit(2);
}
const ROWS = Number(opt.rows);
const BATCH = Number(opt.batch);

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const { pipeline } = await import(pathToFileURL(require.resolve('@huggingface/transformers')).href);

const all = readFileSync(opt.corpus, 'utf8').split('\n').filter(Boolean);
const step = Math.max(1, Math.floor(all.length / ROWS));
const rowIndex = Array.from({ length: ROWS }, (_, i) => i * step).filter((i) => i < all.length);
const texts = rowIndex.map((i) => all[i]);

const { id: modelId, repo: modelRepo, pooling } = resolveModel(opt.model);
if (!pooling) {
  throw new Error(`[pooling] ${opt.model} declares no pooling. Add it to models.json before measuring.`);
}

const pipelineOpts = {};
if (opt.dtype) pipelineOpts.dtype = opt.dtype;
if (opt.device) pipelineOpts.device = opt.device;
if (opt.profile) {
  pipelineOpts.session_options = { enableProfiling: true, profileFilePrefix: 'ort-profile' };
}

// Snapshot cwd contents before, so a profile file (ORT writes it with an internal,
// undocumented name to the process cwd) can be identified by set-difference after.
const before = opt.profile ? new Set(readdirSync(opt['profile-dir'])) : null;

const t0 = performance.now();
const extractor = await pipeline('feature-extraction', modelRepo, pipelineOpts);
const loadMs = performance.now() - t0;

const t1 = performance.now();
let dim = 0;
let vec = null;
for (let i = 0; i < texts.length; i += BATCH) {
  const batch = texts.slice(i, i + BATCH);
  const tensor = await extractor(batch, { pooling, normalize: false });
  dim = tensor.data.length / batch.length;
  if (vec === null) vec = Float32Array.from(tensor.data.slice(0, dim));
}
const embedMs = performance.now() - t1;

let profilePath = null;
if (opt.profile) {
  const session = extractor.model.sessions['model'];
  session.endProfiling();
  const after = readdirSync(opt['profile-dir']);
  const created = after.filter((f) => !before.has(f) && /profile/i.test(f));
  if (created.length === 1) {
    const dest = `${opt.out}.profile.json`;
    // copy+unlink, not renameSync: the profile is written under --profile-dir (often
    // /tmp, a different filesystem than --out) and rename() cannot cross devices.
    copyFileSync(pathResolve(opt['profile-dir'], created[0]), dest);
    unlinkSync(pathResolve(opt['profile-dir'], created[0]));
    profilePath = dest;
  } else {
    console.error(`[profile] expected exactly one new profile file, found: ${JSON.stringify(created)}`);
  }
}

const summary = {
  model: modelRepo,
  model_id: modelId,
  dtype: opt.dtype ?? '(runtime default)',
  device: opt.device ?? '(runtime default)',
  dim,
  rows: texts.length,
  batch: BATCH,
  stride: step,
  corpus: opt.corpus,
  load_ms: Number(loadMs.toFixed(1)),
  embed_ms: Number(embedMs.toFixed(1)),
  ms_per_passage: Number((embedMs / texts.length).toFixed(3)),
  first_vec_head: vec ? Array.from(vec.slice(0, 8)) : null,
  profile_path: profilePath,
  host: hostname(),
  when: new Date().toISOString(),
};
writeFileSync(opt.out, `${JSON.stringify(summary, null, 2)}\n`);
console.error(
  `${modelId} ${opt.dtype ?? 'default'} ${opt.device ?? 'default'} batch=${BATCH}: ` +
    `${texts.length} rows in ${(embedMs / 1000).toFixed(2)}s (${(embedMs / texts.length).toFixed(1)} ms/passage)`,
);
