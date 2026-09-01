// Provenance control: is mrl/minilm384.f32 the same vector space as the model
// zoteus's LocalEmbeddingProvider uses (Xenova/all-MiniLM-L6-v2)? model-id-literal: prose
// Embeds a handful of real passages with transformers.js and reports cosine
// against the stored slab row. A match near 1 says same model; anything else says no.
import { pipeline, env } from '@huggingface/transformers';
import { resolveModel } from './registry.mjs';
import { openSync, readSync, closeSync, readFileSync } from 'node:fs';

env.cacheDir = '/home/haduong/data/cache/transformersjs';

const SLAB = '/home/haduong/data/projets/zoteus-bench/mrl/minilm384.f32';
const TXT = '/home/haduong/data/projets/zoteus-bench/vec-real/passages.txt';
const DIM = 384;

const rows = [0, 1, 1000, 50000, 93021];
const lines = readFileSync(TXT, 'utf8').split('\n');
console.log('lines in passages.txt:', lines.length, '(last empty:', lines[lines.length-1] === '', ')');

const fd = openSync(SLAB, 'r');
function slabRow(i) {
  const buf = Buffer.alloc(DIM * 4);
  readSync(fd, buf, 0, DIM * 4, i * DIM * 4);
  return new Float32Array(buf.buffer, buf.byteOffset, DIM);
}
function cos(a, b) {
  let d = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { d += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]; }
  return d / Math.sqrt(na*nb);
}

const { repo: MODEL, pooling: POOLING, normalize: NORMALIZE } = resolveModel('all-minilm-l6-v2');
if (NORMALIZE === null) {
  throw new Error('[normalize] the incumbent declares no normalize in models.json.');
}
const extractor = await pipeline('feature-extraction', MODEL);
for (const r of rows) {
  const text = lines[r];
  const t = await extractor([text], { pooling: POOLING, normalize: NORMALIZE });
  const v = Array.from(t.data.slice(0, DIM));
  const s = slabRow(r);
  console.log(`row ${r}: chars=${text.length} cosine=${cos(v, s).toFixed(6)}  head="${text.slice(0,60).replace(/\s+/g,' ')}"`);
}
closeSync(fd);
