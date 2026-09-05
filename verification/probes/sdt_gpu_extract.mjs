import './scripts/pdfjs-setup.js';
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { getStructure } from './src/pdf/index.js';
import { stats, endProfiles } from './src/pdf/structure/model/onnx/runtime.js';
const [pdf, output, repeats='3'] = process.argv.slice(2);
const workload = process.env.SDT_MANIFEST
 ? JSON.parse(fs.readFileSync(process.env.SDT_MANIFEST)).map(pdf => ({pdf, warmup:false}))
 : Array.from({length:Number(repeats)+1}, (_,i) => ({pdf, warmup:i===0}));
const dataProvider = name => fs.readFileSync(`build/${name}`);
const results = [];
for (let i = 0; i < workload.length; i++) {
 const {pdf, warmup} = workload[i];
 const buf = fs.readFileSync(pdf);
 const sourceHash = createHash('md5').update(buf).digest('hex');
 stats.calls.length=0; stats.creates.length=0; stats.errors.length=0;
 const start = performance.now();
 const result = await getStructure(buf, '', dataProvider, {sourceHash});
 const wallMs = performance.now()-start;
 if (stats.errors.length || !stats.calls.length) throw new Error(`Invalid extraction: ${JSON.stringify(stats.errors)}, ${stats.calls.length} inference calls`);
 if (result.metadata) result.metadata.dateCreated = 'NORMALIZED';
 const serialized = JSON.stringify(result);
 const row = {iteration:i, warmup, sourceHash, wallMs, inferenceMs:stats.calls.reduce((n,c)=>n+c.ms,0), calls:stats.calls.slice(), creates:stats.creates.slice(), errors:stats.errors.slice(), structureSha256:createHash('sha256').update(serialized).digest('hex'), topKeys:Object.keys(result), pageCount:result.catalog?.pages?.length, blockCount:result.content?.length, layoutFallbacks:result.metadata?.layoutFallbacks ?? result.layoutFallbacks ?? null};
 results.push(row);
 fs.writeFileSync(output, JSON.stringify({backend:stats.mode, threads:Number(process.env.SDT_THREADS || 1), maxRssKiB:process.resourceUsage().maxRSS, results},null,2));
 fs.writeFileSync(`${output}.structure.json`, serialized);
 console.log(JSON.stringify({...row,calls:row.calls.length}));
}
await endProfiles();
