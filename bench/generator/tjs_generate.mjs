// One question per paragraph, on a local model through transformers.js (the
// on-device runtime zoteus itself embeds with), ONNX on CPU. Nothing leaves the
// machine: the only network use is the one-time model download into --cache-dir,
// the same exception R10 names for embedding weights.
//
//   node tjs_generate.mjs --transformers-path <dir> --model <id> --cache-dir <dir> [--dtype q4]
//
// stdin:  one JSON object per line {id, paragraph, language}
// stdout: one JSON object per line {id, question, elapsed_ms}
// stderr: progress and the model's load time.
import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
if (!args['transformers-path'] || !args.model || !args['cache-dir']) {
  console.error('usage: --transformers-path DIR --model ID --cache-dir DIR [--dtype q4] [--max-new-tokens 48]');
  process.exit(2);
}

const entry = pathToFileURL(join(args['transformers-path'], 'dist', 'transformers.node.mjs')).href;
const { pipeline, env } = await import(entry);
env.cacheDir = args['cache-dir'];
env.allowLocalModels = true;

const LANGUAGE = { en: 'English', fr: 'French', vi: 'Vietnamese', de: 'German', es: 'Spanish',
  zh: 'Chinese', ru: 'Russian', ar: 'Arabic', hi: 'Hindi', it: 'Italian', pt: 'Portuguese' };
const SYSTEM = 'You write one short search question a researcher would type into a library search box to find the passage. The question must be answerable from the passage alone and must not copy a sentence of it. Answer with the question only, no preamble, no quotes.';

const t0 = Date.now();
const gen = await pipeline('text-generation', args.model, { dtype: args.dtype || 'q4' });
console.error(`model ${args.model} loaded in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
const maxNew = Number(args['max-new-tokens'] || 48);

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
let n = 0;
for await (const line of rl) {
  if (!line.trim()) continue;
  const row = JSON.parse(line);
  const lang = LANGUAGE[row.language] || row.language;
  const messages = [
    { role: 'system', content: SYSTEM },
    { role: 'user', content: `Passage:\n${row.paragraph}\n\nWrite the question in ${lang}.` },
  ];
  const t1 = Date.now();
  let question = '';
  try {
    const out = await gen(messages, { max_new_tokens: maxNew, do_sample: false, return_full_text: false });
    const reply = out[0].generated_text;
    question = typeof reply === 'string' ? reply : (reply.at(-1)?.content ?? '');
  } catch (e) {
    console.error(`row ${row.id}: ${e.message}`);
  }
  process.stdout.write(JSON.stringify({ id: row.id, question, elapsed_ms: Date.now() - t1 }) + '\n');
  n += 1;
  if (n % 10 === 0) console.error(`${n} questions written`);
}
