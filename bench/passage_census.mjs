// Tokenization pass of the §5.2.9 passage census (ticket 0140): paragraph token
// counts for every fulltext cache, measured with the embedder's own tokenizer.
//
// Measure, do not divide: the ~1,35 tokens-per-word figure in the ticket was a
// labeled approximation, and the max rarely binds under structural chunking,
// so arithmetic on a ratio overstates any correction. This pass writes one
// JSONL row per cache file — attachment kind and the token count of each
// paragraph — and bench/passage_census.py turns those into passage counts with
// the geometry stated in bench/geometry.py. The split keeps the chunk-counting
// rule in one implementation, the tested Python one, instead of a JS twin
// that could drift.
//
// Tokenizer only — no ONNX session, no embedding: this pass counts, it does
// not time or embed, so its numbers cannot be corrupted by CPU contention
// (the run can still slow a concurrent TIMED measurement, which is a
// scheduling constraint, not a validity one).
//
//   node bench/passage_census.mjs --pkg-root <dir> \
//     --storage-root /path/to/Zotero/storage --output <paragraphs.jsonl> \
//     [--model all-minilm-l6-v2] [--sample 200] [--seed 0]
import { createRequire } from 'node:module';
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    'storage-root': { type: 'string' },
    output: { type: 'string' },
    model: { type: 'string', default: 'all-minilm-l6-v2' },
    // 0 = the whole corpus. A sample is for validating the pass, and its
    // artifact says so; §5.2.9 quotes only a full run.
    sample: { type: 'string', default: '0' },
    seed: { type: 'string', default: '0' },
  },
});
if (!opt['pkg-root'] || !opt['storage-root'] || !opt.output) {
  console.error(
    'usage: node bench/passage_census.mjs --pkg-root <dir> --storage-root <Zotero/storage> ' +
      '--output <paragraphs.jsonl> [--model M] [--sample N] [--seed S]',
  );
  process.exit(2);
}

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const tjs = await import(pathToFileURL(require.resolve('@huggingface/transformers')).href);

const { id: modelId, repo: modelRepo } = resolveModel(opt.model);
const tok = await tjs.AutoTokenizer.from_pretrained(modelRepo);
const ntok = (s) => tok(s).input_ids.dims.at(-1);
const specialTokens = ntok('');

// Same attachment-kind rule as verification/probes/paragraph-size-distribution.py,
// because a third of the store is HTML snapshots whose extraction is chrome.
function kindOf(dir) {
  const exts = new Set(
    readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.isFile() && !e.name.startsWith('.'))
      .map((e) => e.name.replace(/^.*(\.[^.]*)$/, '$1').toLowerCase()),
  );
  if (exts.has('.pdf')) return 'pdf';
  if (exts.has('.html') || exts.has('.htm') || exts.has('.mht')) return 'html';
  return 'other';
}

// Mulberry32: a seeded shuffle so a sample is reproducible.
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

let caches = readdirSync(opt['storage-root'], { withFileTypes: true })
  .filter((e) => e.isDirectory())
  .map((e) => join(opt['storage-root'], e.name, '.zotero-ft-cache'))
  .filter((p) => existsSync(p));

const population = caches.length;
const sampleSize = Number(opt.sample);
if (sampleSize > 0 && sampleSize < caches.length) {
  const random = rng(Number(opt.seed));
  for (let i = caches.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [caches[i], caches[j]] = [caches[j], caches[i]];
  }
  caches = caches.slice(0, sampleSize);
}

mkdirSync(dirname(opt.output), { recursive: true });
const header = {
  meta: true,
  probe: 'bench/passage_census.mjs',
  run_utc: new Date().toISOString(),
  model: { id: modelId, repo: modelRepo },
  special_tokens: specialTokens,
  storage_root: opt['storage-root'],
  population,
  sampled: caches.length,
  seed: Number(opt.seed),
};
writeFileSync(opt.output, `${JSON.stringify(header)}\n`);

let done = 0;
for (const cache of caches) {
  let text;
  try {
    text = readFileSync(cache, 'utf8');
  } catch {
    continue;
  }
  const key = dirname(cache).split('/').at(-1);
  const paragraphs = text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => ntok(p) - specialTokens);
  appendFileSync(
    opt.output,
    `${JSON.stringify({ key, kind: kindOf(dirname(cache)), paragraphs })}\n`,
  );
  done += 1;
  if (done % 500 === 0) console.error(`${done}/${caches.length}`);
}
console.log(JSON.stringify({ population, processed: done, output: opt.output }));
