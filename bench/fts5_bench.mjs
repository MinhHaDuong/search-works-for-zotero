// Same corpus, same chunking as zoteus (1200 chars, no cap): FTS5 instead of a
// resident JS index. Measures build time, disk, resident memory and query latency.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, statSync, readdirSync, existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';

const STORAGE = process.argv[2];
const KEYS = process.argv[3]; // file of user-library attachment keys, one per line
const DB = process.argv[4];
const CHUNK = 1200;

const rss = () => {
  const s = readFileSync('/proc/self/status', 'utf8');
  const g = (k) => Number(/^Vm\w+:\s+(\d+)/m.exec(s.split(k)[1] ? k + s.split(k)[1] : 'x: 0')?.[1] ?? 0);
  const line = (k) => Number(s.match(new RegExp(`^${k}:\\s+(\\d+)`, 'm'))?.[1] ?? 0) / 1024;
  return { rss: line('VmRSS'), swap: line('VmSwap') };
};

if (existsSync(DB)) rmSync(DB);
const db = new DatabaseSync(DB);
db.exec('PRAGMA journal_mode=WAL');
db.exec('PRAGMA synchronous=NORMAL');
db.exec(`CREATE VIRTUAL TABLE passages USING fts5(
           body, item UNINDEXED, ord UNINDEXED,
           tokenize='unicode61 remove_diacritics 2')`);

const wanted = new Set(readFileSync(KEYS, 'utf8').split('\n').filter(Boolean));
const ins = db.prepare('INSERT INTO passages(body, item, ord) VALUES (?,?,?)');

const t0 = performance.now();
let docs = 0, passages = 0, chars = 0;
db.exec('BEGIN');
for (const key of readdirSync(STORAGE)) {
  if (!wanted.has(key)) continue;
  const p = join(STORAGE, key, '.zotero-ft-cache');
  let text;
  try { text = readFileSync(p, 'utf8'); } catch { continue; }
  if (text.length < 32) continue;
  docs++; chars += text.length;
  for (let i = 0, n = 0; i < text.length; i += CHUNK, n++) {
    ins.run(text.slice(i, i + CHUNK), key, n);
    passages++;
  }
  if (docs % 500 === 0) { db.exec('COMMIT'); db.exec('BEGIN'); }
}
db.exec('COMMIT');
const build = (performance.now() - t0) / 1000;
db.exec("INSERT INTO passages(passages) VALUES('optimize')");

const size = statSync(DB).size / 2 ** 20;
console.log(`ingestion   ${docs} documents, ${passages} passages, ${(chars / 1e9).toFixed(2)} Go de texte`);
console.log(`build       ${build.toFixed(1)} s`);
console.log(`disque      ${size.toFixed(1)} Mo`);
console.log(`mémoire     RSS ${rss().rss.toFixed(0)} Mo, swap ${rss().swap.toFixed(0)} Mo`);

const q = db.prepare(`SELECT item, ord, bm25(passages) s, snippet(passages,0,'[',']','…',12) x
                      FROM passages WHERE passages MATCH ? ORDER BY s LIMIT 3`);
for (const query of ['cout social du carbone', 'equilibre general walrasien',
                     'transhumance rennes laponie sami']) {
  const t = performance.now();
  const rows = q.all(query);
  console.log(`requête "${query}" -> ${rows.length} hits en ${(performance.now() - t).toFixed(1)} ms` +
              (rows[0] ? `, top score ${rows[0].s.toFixed(3)}` : ''));
}
console.log(`mémoire après requêtes  RSS ${rss().rss.toFixed(0)} Mo`);
