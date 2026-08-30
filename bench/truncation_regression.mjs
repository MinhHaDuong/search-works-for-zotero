// The truncation regression (ticket 0140): does the settled chunk geometry keep
// every embedded sequence inside what the embedder actually reads?
//
// Two arms over the same text, head topic A (~600 tokens) + tail topic B:
//
// - The 768 arm emits the whole text as one chunk, as cycle 2's geometry would.
//   The embedder reads its first 512 tokens — pure A — so the chunk's vector is
//   IDENTICAL to the head's, and the tail leaves no trace. That is the defect,
//   demonstrated: against a 768-token cap this regression is red.
// - The settled arm packs sentences under the resolved budget, as structural
//   chunking would. Every chunk fits the window, so the seam chunk's vector
//   moves when its tail differs — the same comparison comes out non-identical.
//
// Two constructions of this test give false answers (both were hit while
// producing the ticket's evidence): a repeated single word makes mean-pooling
// length-invariant, so the test passes vacuously; and a head shorter than the
// window means the two arms never share a full-length prefix. The artifact
// therefore records its own positive control — head and tail must be
// dissimilar — and the guard test refuses the artifact without it.
//
//   node bench/truncation_regression.mjs --pkg-root <dir> --budget 498 \
//     --output bench/results/0140-truncation-regression/regression.json
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'pkg-root': { type: 'string' },
    output: { type: 'string' },
    // A registry id (bench/models.json). Default: the model zoteus loads today.
    model: { type: 'string', default: 'all-minilm-l6-v2' },
    // The resolved budget, from the construction in bench/geometry.py
    // (DESIGN.md §2.2). Passed in rather than recomputed here so the
    // construction stays stated in one place; the guard test cross-checks
    // this artifact's value against that construction.
    budget: { type: 'string' },
    // The 768 arm's cap: cycle 2's ceiling-used-as-target, kept explicit so
    // the artifact says what the red arm actually exercised.
    'old-cap': { type: 'string', default: '768' },
  },
});
if (!opt['pkg-root'] || !opt.output || !opt.budget) {
  console.error(
    'usage: node bench/truncation_regression.mjs --pkg-root <dir> --budget <tokens> ' +
      '--output <regression.json> [--model all-minilm-l6-v2] [--old-cap 768]',
  );
  process.exit(2);
}
const BUDGET = Number(opt.budget);
const OLD_CAP = Number(opt['old-cap']);

const require = createRequire(`${opt['pkg-root'].replace(/\/?$/, '/')}package.json`);
const tjs = await import(pathToFileURL(require.resolve('@huggingface/transformers')).href);
const tjsVersion = JSON.parse(readFileSync(
  `${opt['pkg-root'].replace(/\/?$/, '/')}node_modules/@huggingface/transformers/package.json`,
  'utf8',
)).version;

const { id: modelId, repo: modelRepo, pooling, template } = resolveModel(opt.model);
if (!pooling) {
  throw new Error(`[pooling] ${opt.model} declares no pooling. Add it to models.json.`);
}
const passagePrefix = template?.passage ?? '';

const tok = await tjs.AutoTokenizer.from_pretrained(modelRepo);
const extractor = await tjs.pipeline('feature-extraction', modelRepo);
const ntok = (s) => tok(s).input_ids.dims.at(-1); // includes the special tokens
const specialTokens = ntok('');

// Sentence repetition, never single-word repetition, and never a decode
// round-trip: chunks are built by packing whole sentences, which is both
// faithful to structural chunking and free of tokenizer re-encoding drift.
const A = 'Carbon pricing policy and emissions trading schemes in European industrial sectors. ';
const B = 'Arctic tern migration routes, breeding colonies, plumage and feeding behaviour at sea. ';

const perA = ntok(A) - specialTokens;
const perB = ntok(B) - specialTokens;
// Head comfortably past the 512-token window, whole text inside the old cap,
// so the 768 arm emits it as a single chunk.
const nA = Math.ceil(600 / perA);
const headSentences = Array(nA).fill(A);
const bodyBudget = OLD_CAP - specialTokens - nA * perA;
const nB = Math.floor(bodyBudget / perB);
const tailSentences = Array(nB).fill(B);
const long = headSentences.join('') + tailSentences.join('');
const head = headSentences.join('');
const tail = tailSentences.join('');

async function embed(s) {
  const r = await extractor([passagePrefix + s], { pooling, normalize: true });
  return Array.from(r.data);
}
const cos = (a, b) => a.reduce((d, v, i) => d + v * b[i], 0);

// Settled arm: pack sentences under the budget.
const chunks = [];
let current = [];
let filled = 0;
for (const s of [...headSentences, ...tailSentences]) {
  const n = s === A ? perA : perB;
  if (filled && filled + n > BUDGET) {
    chunks.push(current.join(''));
    current = [];
    filled = 0;
  }
  current.push(s);
  filled += n;
}
if (current.length) chunks.push(current.join(''));

// The seam chunk is the one holding the topic switch; its A-part is its own
// leading A-sentences, so the comparison is within-chunk, not against `head`.
const seam = chunks.find((c) => c.includes(B) && c.includes(A));
const seamAPart = seam.slice(0, seam.indexOf(B));

const vLong = await embed(long);
const vHead = await embed(head);
const vTail = await embed(tail);
const vSeam = await embed(seam);
const vSeamA = await embed(seamAPart);

const artifact = {
  ticket: 'tickets/0140-cap-the-chunker-below-the-embedder-limit.erg',
  probe: 'bench/truncation_regression.mjs',
  run_utc: new Date().toISOString(),
  model: { id: modelId, repo: modelRepo, pooling, passage_prefix: passagePrefix,
           transformers_js: tjsVersion },
  budget: BUDGET,
  old_cap: OLD_CAP,
  special_tokens: specialTokens,
  tokens: {
    head: ntok(head), tail: ntok(tail), long: ntok(long),
    seam_chunk: ntok(seam), seam_a_part: ntok(seamAPart),
    settled_chunks: chunks.map((c) => ntok(c)),
  },
  cosines: {
    // Positive control: without this well below 1, neither arm can discriminate.
    head_vs_tail: cos(vHead, vTail),
    // Old arm: 768-cap chunk versus its head alone. Identity here IS the defect.
    old_arm_long_vs_head: cos(vLong, vHead),
    // Settled arm: the seam chunk versus its own A-part. Identity here would
    // mean the tail still leaves no trace at the settled budget.
    settled_arm_seam_vs_a_part: cos(vSeam, vSeamA),
  },
};
mkdirSync(dirname(opt.output), { recursive: true });
writeFileSync(opt.output, `${JSON.stringify(artifact, null, 2)}\n`);
console.log(JSON.stringify(artifact.cosines, null, 2));
