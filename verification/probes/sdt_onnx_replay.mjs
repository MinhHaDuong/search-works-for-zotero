// Run from the isolated document-worker checkout; capture tensors first.
import fs from 'node:fs';
import { deserialize } from 'node:v8';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
const ort = createRequire(import.meta.url)(process.env.SDT_ORT_PATH);
const calls = deserialize(fs.readFileSync(process.argv[2]));
const backend = process.env.SDT_BACKEND;
const models = ['clusterer/model.onnx','clusterer/repair.onnx','classifier/model.onnx'];
const sessions = new Map();
for (const model of models) {
 const bytes = fs.readFileSync(`build/block-seg/${model}`);
 const hash = createHash('sha256').update(bytes).digest('hex');
 sessions.set(hash, await ort.InferenceSession.create(bytes, {executionProviders:[backend],intraOpNumThreads:1,interOpNumThreads:1,graphOptimizationLevel:'all',...(process.env.SDT_PROFILE ? {enableProfiling:true,profileFilePrefix:`${process.env.SDT_PROFILE}/${hash}`} : {})}));
}
const rows = [];
for (let i=0;i<6;i++) {
 let maxAbsError=0, sumMs=0; const byModel={};
 for (const call of calls) {
  const feeds=Object.fromEntries(Object.entries(call.feeds).map(([k,t])=>[k,new ort.Tensor(t.type,t.data,t.dims)]));
  const start=performance.now();
  const out=await sessions.get(call.hash).run(feeds,call.outputNames);
  const ms=performance.now()-start; sumMs+=ms; byModel[call.hash]=(byModel[call.hash]||0)+ms;
  for (const [key,tensor] of Object.entries(out)) {
   const expected=call.outputs[key].data;
   if (tensor.data.length!==expected.length) throw new Error('Output shape changed');
   for(let j=0;j<expected.length;j++) {
    const error=Math.abs(Number(tensor.data[j])-Number(expected[j]));
    if (!Number.isFinite(error)) throw new Error('Nonfinite output difference');
    maxAbsError=Math.max(maxAbsError,error);
   }
   tensor.dispose();
  }
 }
 rows.push({iteration:i,warmup:i===0,sumMs,byModel,maxAbsError});
}
for (const session of sessions.values()) { if(process.env.SDT_PROFILE)session.endProfiling(); await session.release(); }
fs.writeFileSync(process.argv[3],JSON.stringify({backend,calls:calls.length,rows},null,2));
console.log(JSON.stringify(rows));
