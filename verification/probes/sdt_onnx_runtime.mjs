import * as wasm from 'onnxruntime-web/wasm';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import { serialize } from 'node:v8';
import { performance } from 'node:perf_hooks';
import { Mutex } from '../../../mutex.js';
export const onnxMutex = new Mutex();
const mode = process.env.SDT_BACKEND || 'wasm';
const native = mode === 'wasm' ? null : createRequire(import.meta.url)(process.env.SDT_ORT_PATH);
export const stats = { mode, creates: [], calls: [], errors: [] };
const sessions = [];
const captured = [];
let createQueue = Promise.resolve();
const threads = Number(process.env.SDT_THREADS || 1);
export async function endProfiles() { if (process.env.SDT_CAPTURE) fs.writeFileSync(process.env.SDT_CAPTURE, serialize(captured)); for (const s of sessions) { if (process.env.SDT_PROFILE) s.endProfiling(); await s.release(); } }
export async function getRuntime(provider) {
 const ort = native || wasm;
 if (!native) { ort.env.wasm.simd = true; ort.env.wasm.numThreads = 1; ort.env.wasm.proxy = false; ort.env.wasm.wasmBinary = await provider(); ort.env.wasm.wasmPaths = undefined; }
 return { Tensor: ort.Tensor, InferenceSession: { async create(bytes, options) {
  const hash = createHash('sha256').update(bytes).digest('hex');
  const opts = { ...options, executionProviders: [mode === 'wasm' ? 'wasm' : mode], ...(native ? { intraOpNumThreads: threads, interOpNumThreads: 1, ...(process.env.SDT_PROFILE ? {enableProfiling:true, profileFilePrefix: `${process.env.SDT_PROFILE}/${hash}`} : {}) } : {}) };
  const start = performance.now();
  let session;
  try { const creation = createQueue.then(() => ort.InferenceSession.create(bytes, opts)); createQueue = creation.catch(() => {}); session = await creation; }
  catch(e) { stats.errors.push(String(e)); throw e; }
  sessions.push(session); stats.creates.push({hash, ms:performance.now()-start});
  return { async run(...args) {
   const begin = performance.now();
   try { const out = await session.run(...args); stats.calls.push({hash, ms:performance.now()-begin});
    if (process.env.SDT_CAPTURE) captured.push({hash, feeds:Object.fromEntries(Object.entries(args[0]).map(([k,t])=>[k,{type:t.type,dims:t.dims,data:t.data}])), outputNames:args[1], outputs:Object.fromEntries(Object.entries(out).map(([k,t])=>[k,{type:t.type,dims:t.dims,data:t.data}]))});
    return out; }
   catch(e) { stats.errors.push(String(e)); throw e; }
  }, release: () => session.release() };
 } } };
}
