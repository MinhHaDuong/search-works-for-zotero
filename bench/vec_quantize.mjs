// float32 vs int8 vs binary quantization at a fixed N, for ticket 0008. Binary is
// ~13x faster and ~24x smaller; int8 buys only ~1,6x against 3,8x less data,
// which is what says the scan is not I/O-bound. A SEPARATE run from
// vec_scaling.mjs with its own seed, so float32 differs by a few percent between
// the two -- run-to-run spread, not a transcription error.
//
//   npm i sqlite-vec && node bench/vec_quantize.mjs
//
// Needs Node >= 22.5 for node:sqlite. Writes and deletes q.sqlite in cwd.
import { DatabaseSync } from 'node:sqlite';
import * as sv from 'sqlite-vec';
import { existsSync, unlinkSync, statSync } from 'node:fs';

const DIM = 384, K = 30, N = 400000;
let seed = 999;
const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff - 0.5; };
function vec(){ const a=new Float32Array(DIM); let n=0; for(let i=0;i<DIM;i++){a[i]=rnd(); n+=a[i]*a[i];} n=Math.sqrt(n); for(let i=0;i<DIM;i++)a[i]/=n; return a; }
const blob = a => new Uint8Array(a.buffer.slice(0));
const path = 'q.sqlite';
const clean = () => { for (const f of [path,path+'-wal',path+'-shm']) if (existsSync(f)) unlinkSync(f); };

function run(label, decl, insSql, bindFn, qSql) {
  clean();
  const db = new DatabaseSync(path,{allowExtension:true});
  db.enableLoadExtension(true); sv.load(db); db.enableLoadExtension(false);
  db.exec('PRAGMA journal_mode=WAL');
  db.exec(decl);
  const ins = db.prepare(insSql);
  db.exec('BEGIN');
  for (let i=1;i<=N;i++){ ins.run(BigInt(i), bindFn(vec())); if(i%20000===0){db.exec('COMMIT');db.exec('BEGIN');} }
  db.exec('COMMIT');
  const q = db.prepare(qSql);
  const probes = Array.from({length:15},()=>vec());
  for (let i=0;i<4;i++) q.all(bindFn(probes[i]));
  const t=[]; for(const p of probes){const s=performance.now(); q.all(bindFn(p)); t.push(performance.now()-s);}
  t.sort((a,b)=>a-b);
  const mb = statSync(path).size/2**20;
  console.log(`${label.padEnd(28)} ${mb.toFixed(0).padStart(5)} MB   ${t[Math.floor(t.length/2)].toFixed(1).padStart(7)} ms   ${(mb*2**20/N).toFixed(0).padStart(5)} B/vec`);
  db.close();
}

console.log(`N=${N} dim=${DIM} k=${K}`);
console.log('variant                       size        median      per-vector');
run('float32 (current)', `CREATE VIRTUAL TABLE v USING vec0(embedding float[${DIM}])`,
    'INSERT INTO v(rowid,embedding) VALUES (?,?)', blob,
    `SELECT rowid FROM v WHERE embedding MATCH ? AND k=${K} ORDER BY distance`);
run('int8 quantized', `CREATE VIRTUAL TABLE v USING vec0(embedding int8[${DIM}])`,
    'INSERT INTO v(rowid,embedding) VALUES (?,vec_quantize_int8(?,\'unit\'))', blob,
    `SELECT rowid FROM v WHERE embedding MATCH vec_quantize_int8(?,'unit') AND k=${K} ORDER BY distance`);
run('binary quantized', `CREATE VIRTUAL TABLE v USING vec0(embedding bit[${DIM}])`,
    'INSERT INTO v(rowid,embedding) VALUES (?,vec_quantize_binary(?))', blob,
    `SELECT rowid FROM v WHERE embedding MATCH vec_quantize_binary(?) AND k=${K} ORDER BY distance`);
clean();
