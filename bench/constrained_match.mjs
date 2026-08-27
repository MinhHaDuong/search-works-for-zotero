// X4 (ticket 0025): what does a rowid-constrained MATCH cost, at the scopes the ladder
// would step through?
//
// The query-semantics ladder (scoped issue A's territory) wants to run FTS5 MATCH inside
// a bounded rowid set — an entry, an item, a collection — via `json_each`, the mechanism
// that actually exists. The rule (DESIGN.md §3, X4): the ladder step sits at the largest
// measured scope whose constrained-MATCH p95 <= 150 ms (the filter allowance inside the
// 300-700 ms typical budget); if even 1k exceeds it, no constrained step ships and the
// ladder ends at the honest R18 give-up.
//
// HONESTLY RESCOPED to a synthetic corpus (substrate map, ticket 0025): the real 477k
// index lives on the workstation. The corpus here matches the real one in what the cost
// curve is structural in — passage count (477,512), passages per query term (a Zipfian
// vocabulary, so terms span rare to ubiquitous), the schema (external-content FTS5,
// unicode61 remove_diacritics 2), and the OR-of-quoted-terms query shape upstream
// builds — and in nothing else. The artifact says so; the workstation re-run on the real
// corpus confirms before any ladder constant is pinned.
//
//   node bench/constrained_match.mjs > bench/results/0025-x4-constrained-match/synthetic-477k.json
import { DatabaseSync } from 'node:sqlite';
import { existsSync, unlinkSync, statSync } from 'node:fs';
import { execSync } from 'node:child_process';

const N = 477_512; // the measured real corpus size (bench/results/0013-concentration)
const WORDS_PER_PASSAGE = 60;
const VOCAB = 50_000;
const SCOPES = [1_000, 5_000, 20_000, 100_000];
const PROBES = 20;
const DBPATH = '/tmp/x4-constrained-bench.sqlite';

// mulberry32 — see census_parse.mjs for why not a bare LCG.
let seed = 47751247;
function rnd() {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

// A Zipf(1.0) vocabulary: word w0 appears in a large fraction of passages, w49999 in a
// handful — the df spread the constrained-MATCH cost depends on.
const cum = new Float64Array(VOCAB);
{
  let s = 0;
  for (let i = 0; i < VOCAB; i++) {
    s += 1 / (i + 1);
    cum[i] = s;
  }
  for (let i = 0; i < VOCAB; i++) cum[i] /= s;
}
function zipfWord() {
  const u = rnd();
  let lo = 0;
  let hi = VOCAB - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (cum[mid] < u) lo = mid + 1;
    else hi = mid;
  }
  return `w${lo}`;
}
function passage() {
  const parts = new Array(WORDS_PER_PASSAGE);
  for (let i = 0; i < WORDS_PER_PASSAGE; i++) parts[i] = zipfWord();
  return parts.join(' ');
}

for (const f of [DBPATH, `${DBPATH}-wal`, `${DBPATH}-shm`]) if (existsSync(f)) unlinkSync(f);
const db = new DatabaseSync(DBPATH);
db.exec('PRAGMA journal_mode = WAL');
db.exec('PRAGMA synchronous = NORMAL');
db.exec(`
  CREATE TABLE passages (pid INTEGER PRIMARY KEY, text TEXT NOT NULL);
  CREATE VIRTUAL TABLE passages_fts USING fts5(
    text,
    content='passages',
    content_rowid='pid',
    tokenize='unicode61 remove_diacritics 2'
  );
`);
const insP = db.prepare('INSERT INTO passages (pid, text) VALUES (?, ?)');
const insF = db.prepare('INSERT INTO passages_fts (rowid, text) VALUES (?, ?)');
const tBuild = performance.now();
db.exec('BEGIN');
for (let pid = 1; pid <= N; pid++) {
  const t = passage();
  insP.run(pid, t);
  insF.run(pid, t);
  if (pid % 20_000 === 0) {
    db.exec('COMMIT');
    db.exec('BEGIN');
  }
}
db.exec('COMMIT');
db.exec("INSERT INTO passages_fts(passages_fts) VALUES ('optimize')");
const build_s = +((performance.now() - tBuild) / 1000).toFixed(1);

// Upstream's query shape: quoted terms, OR-ed. Probes mix document frequencies the way a
// real query does — one common word, one mid, one rare.
function probeQuery() {
  const common = `w${Math.floor(rnd() * 20)}`;
  const mid = `w${200 + Math.floor(rnd() * 2000)}`;
  const rare = `w${10_000 + Math.floor(rnd() * 40_000)}`;
  return `"${common}" OR "${mid}" OR "${rare}"`;
}
function rowidSet(size) {
  const set = new Set();
  while (set.size < size) set.add(1 + Math.floor(rnd() * N));
  return JSON.stringify([...set]);
}

const quantiles = (times) => {
  const s = [...times].sort((a, b) => a - b);
  const at = (q) => s[Math.min(s.length - 1, Math.floor(s.length * q))];
  return { median_ms: +at(0.5).toFixed(1), p95_ms: +at(0.95).toFixed(1) };
};

const unconstrained = db.prepare(
  'SELECT rowid, bm25(passages_fts) AS score FROM passages_fts WHERE passages_fts MATCH ? ORDER BY score LIMIT 30',
);
const constrained = db.prepare(
  'SELECT rowid, bm25(passages_fts) AS score FROM passages_fts WHERE passages_fts MATCH ? ' +
    'AND rowid IN (SELECT value FROM json_each(?)) ORDER BY score LIMIT 30',
);

const rows = [];
{
  for (let w = 0; w < 3; w++) unconstrained.all(probeQuery());
  const times = [];
  for (let p = 0; p < PROBES; p++) {
    const q = probeQuery();
    const t = performance.now();
    unconstrained.all(q);
    times.push(performance.now() - t);
  }
  rows.push({ scope: 'unconstrained', ...quantiles(times) });
}
for (const scope of SCOPES) {
  const sets = Array.from({ length: PROBES + 3 }, () => rowidSet(scope));
  for (let w = 0; w < 3; w++) constrained.all(probeQuery(), sets[w]);
  const times = [];
  for (let p = 3; p < sets.length; p++) {
    const q = probeQuery();
    const t = performance.now();
    constrained.all(q, sets[p]);
    times.push(performance.now() - t);
  }
  rows.push({ scope, ...quantiles(times) });
}

const db_mb = +(statSync(DBPATH).size / 2 ** 20).toFixed(0);
db.close();
for (const f of [DBPATH, `${DBPATH}-wal`, `${DBPATH}-shm`]) if (existsSync(f)) unlinkSync(f);

const out = {
  probe: 'ticket 0025 X4 — json_each-constrained MATCH cost by rowid-set scope, on a synthetic 477k corpus',
  rule:
    'DESIGN.md §3 X4: ladder step at the largest scope with constrained-MATCH p95 <= 150 ms; ' +
    'if even 1k exceeds it, no constrained step ships',
  substrate:
    'SYNTHETIC corpus: 477,512 passages of 60 Zipf(1.0)-distributed words over a 50k ' +
    'vocabulary, external-content FTS5, unicode61 remove_diacritics 2, OR-of-quoted-terms ' +
    'probes mixing common/mid/rare df. The cost curve SHAPE is structural in these; the ' +
    'absolute numbers are indicative until the workstation re-runs this on the real index.',
  host: 'session container (weaker substrate than the workstation: a pass here is conservative)',
  cpu: execSync('grep -m1 "model name" /proc/cpuinfo').toString().split(':')[1].trim(),
  node: process.version,
  timestamp_utc: new Date().toISOString(),
  passages: N,
  db_mb,
  build_s,
  probes_per_scope: PROBES,
  rows,
};
console.log(JSON.stringify(out, null, 2));
