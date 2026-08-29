#!/usr/bin/env node
// Does `device: 'auto'` actually run on a CPU-only machine, and does it change the vectors?
//
// Ticket 0220 rules that the device is never configurable and that `auto` is passed
// unconditionally, on the ground that ONNX Runtime's execution-provider fallback skips a
// provider it cannot use. That ground was READ from @huggingface/transformers'
// src/backends/onnx.js, never executed. This probe executes it.
//
// One variant per process: a failed session init leaves ORT state behind, and comparing
// variants inside one process would let that contaminate the next.
//
//   node device-auto-probe.mjs --pkg-root <dir-with-node_modules> [--device auto] [--dtype q8]
//
// With neither flag it makes today's call — pipeline() with no options object at all.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    label: { type: 'string' },
    device: { type: 'string' },
    dtype: { type: 'string' },
    model: { type: 'string', default: 'Xenova/all-MiniLM-L6-v2' },
    'cache-dir': { type: 'string' },
  },
});
if (!opt['pkg-root']) {
  console.error('usage: device-auto-probe.mjs --pkg-root <dir> [--device auto|cpu] [--dtype q8] [--label name]');
  process.exit(2);
}

// An absent flag means an ABSENT key, never an undefined one: `{device: undefined}` is a
// third call shape that neither the current code nor the patch produces, and probing it
// would measure something nobody ships.
const pipelineOpts = {};
if (opt.device) pipelineOpts.device = opt.device;
if (opt.dtype) pipelineOpts.dtype = opt.dtype;
const passedOptions = Object.keys(pipelineOpts).length > 0;

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const entry = require.resolve('@huggingface/transformers');
const transformers = await import(pathToFileURL(entry).href);
const { pipeline, env } = transformers;
if (opt['cache-dir']) env.cacheDir = opt['cache-dir'];

/** The package's `exports` map hides ./package.json, so walk up to it from the entry. */
function packageVersion(entryPath) {
  for (let dir = dirname(entryPath); dir !== dirname(dir); dir = dirname(dir)) {
    try {
      const pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'));
      if (pkg.name === '@huggingface/transformers') return pkg.version;
    } catch {
      /* keep walking up */
    }
  }
  return 'unknown';
}

const SENTENCE = 'what did Nordhaus say about the social cost of carbon';
const out = {
  label: opt.label ?? (passedOptions ? JSON.stringify(pipelineOpts) : 'no-options'),
  model: opt.model,
  options: passedOptions ? pipelineOpts : null,
  transformers: packageVersion(entry),
  platform: `${process.platform}-${process.arch}`,
  node: process.version,
};

try {
  const t0 = performance.now();
  const extractor = passedOptions
    ? await pipeline('feature-extraction', opt.model, pipelineOpts)
    : await pipeline('feature-extraction', opt.model);
  out.load_ms = Number((performance.now() - t0).toFixed(1));
  const tensor = await extractor(SENTENCE, { pooling: 'mean', normalize: true });
  out.ok = true;
  out.dim = tensor.data.length;
  // Already normalised, so a dot product against another run IS the cosine.
  out.vector = Array.from(tensor.data);
} catch (e) {
  out.ok = false;
  out.error = e instanceof Error ? e.message : String(e);
}
console.log(JSON.stringify(out));
