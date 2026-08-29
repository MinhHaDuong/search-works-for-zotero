/**
 * What one semantic query pays before any vector is touched: embedding the query string.
 *
 * It is inside every latency in the arm table, so at 21,7 ms it is most of what the
 * two-stage arm reports and none of what the exact arms report. Measured through upstream
 * v1.10.0's OWN LocalEmbeddingProvider, on the same twenty queries, so it is the same code
 * path the server runs rather than a re-implementation of it.
 */
import { readFileSync } from 'node:fs';

const [, , distDir, queriesFile, transformersPath] = process.argv;
const { LocalEmbeddingProvider } = await import(`${distDir}/features/search/embeddings.js`);

const queries = readFileSync(queriesFile, 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith('#'));

const p = new LocalEmbeddingProvider(undefined, undefined, { transformersPath });

const t0 = performance.now();
await p.embed([queries[0]]);
const firstMs = performance.now() - t0;

const samples = [];
for (let pass = 0; pass < 5; pass++) {
  for (const q of queries) {
    const t = performance.now();
    await p.embed([q]);
    samples.push(performance.now() - t);
  }
}
samples.sort((a, b) => a - b);
const at = (pc) => samples[Math.max(0, Math.ceil((pc / 100) * samples.length) - 1)];
console.log(
  JSON.stringify(
    {
      what: 'query-embedding cost alone, upstream LocalEmbeddingProvider, Xenova/all-MiniLM-L6-v2',
      first_call_ms_includes_model_load: Math.round(firstMs * 10) / 10,
      warm: {
        n: samples.length,
        min_ms: Math.round(samples[0] * 10) / 10,
        p50_ms: Math.round(at(50) * 10) / 10,
        p95_ms: Math.round(at(95) * 10) / 10,
        max_ms: Math.round(samples[samples.length - 1] * 10) / 10,
      },
    },
    null,
    2,
  ),
);
