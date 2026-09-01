// X4 (ticket 0025): what does a rowid-constrained MATCH cost, at the scopes the ladder
// would step through?
//
// The query-semantics ladder (scoped issue A's territory) wants to run FTS5 MATCH inside
// a bounded rowid set — an entry, an item, a collection — via `json_each`, the mechanism
// that actually exists. The rule (SPEC.md §5.3, X4): the ladder step sits at the largest
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
//   node bench/constrained_match.mjs <existing.sqlite>   # probe an already-built corpus
//
// No `optimize` after the build, deliberately: upstream never issues one, so the index
// under test is the incrementally-built shape a real library actually has — and the merge
// of a 28.6M-token index is an hour of single-threaded work that measures nothing the
// rule asks about.
import { DatabaseSync } from 'node:sqlite';
import { existsSync, unlinkSync, statSync } from 'node:fs';
import { execSync } from 'node:child_process';

const N = 477_512; // the measured real corpus size (bench/results/0013-concentration)
const WORDS_PER_PASSAGE = 60;
const VOCAB = 50_000;
// The rule turns on the SMALLEST scope — "if even 1k exceeds the allowance, no constrained
// step ships" — and the larger rungs only draw the curve. On the real index a rung can cost
// minutes per probe, so the ladder is overridable: measure the verdict first, extend after.
const SCOPES = (process.env.X4_SCOPES ?? '1000,5000,20000,100000')
  .split(',')
  .map((s) => Number(s.trim()))
  .filter((n) => Number.isInteger(n) && n > 0);
const PROBES = Number(process.env.X4_PROBES ?? 20);
const DBPATH = process.argv[2] ?? '/tmp/x4-constrained-bench.sqlite';
const PROBE_ONLY = process.argv[2] !== undefined;

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

// Upstream's query shape: quoted terms, OR-ed. Probes mix document frequencies the way a
// real query does — one common word, one mid, one rare.
//
// The df mix is the cost model, not decoration, and it is why the synthetic vocabulary
// cannot be carried onto a real index. `w5` and its siblings are not ABSENT from a real
// library — OCR debris and variable names put a handful in — so a probe-only run against
// one neither errors nor returns empty: it matches almost nothing, answers in about a
// millisecond, and reads as a pass. X4's rule being an UPPER BOUND on latency, that
// vacuous arm satisfies the 150 ms allowance and inverts the verdict. Measured on the real
// 477 512-passage index, 2026-08-29: synthetic 1,0 ms against 379,3 ms for a query drawn
// from the same three bands (verification/probes/x4_probe_vocabulary.py).
//
// So probe-only mode draws its terms from the index under test. The synthetic path is
// untouched, byte for byte, so synthetic-477k.json stays reproducible.
const SYNTHETIC_BANDS = () => {
  const common = `w${Math.floor(rnd() * 20)}`;
  const mid = `w${200 + Math.floor(rnd() * 2000)}`;
  const rare = `w${10_000 + Math.floor(rnd() * 40_000)}`;
  return [common, mid, rare];
};

/** df bands as fractions of the corpus, matching the synthetic vocabulary's intent. */
const REAL_BANDS = [
  ['common', 0.1, 1.01],
  ['mid', 0.001, 0.01],
  ['rare', 1e-5, 1e-3],
];

/**
 * Term pools for a real index, read once from fts5vocab.
 *
 * fts5vocab is a view over the existing index — no migration, nothing stored — but it is
 * ordered by term, not by document count, so a df threshold costs a full scan. That is
 * seconds, paid once per run, and it is the reason this is hoisted out of probeQuery().
 */
function realTermPools(db, n) {
  db.exec('CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, passages_fts, row)');
  const pools = [];
  for (const [name, lo, hi] of REAL_BANDS) {
    const rows = db
      .prepare('SELECT term FROM temp.v WHERE doc >= ? AND doc < ? ORDER BY doc DESC LIMIT 400')
      .all(Math.floor(lo * n), Math.floor(hi * n))
      .map((r) => r.term)
      // FTS5 bareword syntax: a term carrying a quote or backslash would need escaping, and
      // a term that is all digits is a legitimate token here ('095') but not a useful probe.
      .filter((t) => /^[\p{L}\p{N}]+$/u.test(t) && /\p{L}/u.test(t));
    if (rows.length === 0) throw new Error(`no usable terms in the ${name} df band`);
    pools.push(rows);
  }
  return pools;
}

let TERM_POOLS = null;
function probeQuery() {
  const terms = TERM_POOLS
    ? TERM_POOLS.map((pool) => pool[Math.floor(rnd() * pool.length)])
    : SYNTHETIC_BANDS();
  return terms.map((t) => `"${t}"`).join(' OR ');
}

let db;
let build_s = null;
let vocab_scan_s = null;
if (PROBE_ONLY) {
  db = new DatabaseSync(DBPATH);
  const have = db.prepare('SELECT count(*) AS n FROM passages').get().n;
  if (Number(have) !== N) throw new Error(`corpus at ${DBPATH} holds ${have} passages, expected ${N}`);
  const tVocab = performance.now();
  TERM_POOLS = realTermPools(db, Number(have));
  vocab_scan_s = +((performance.now() - tVocab) / 1000).toFixed(1);
  console.error(
    `probe-only: reusing ${DBPATH}; real-vocabulary probes from ` +
      `${TERM_POOLS.map((p) => p.length).join('/')} terms per df band (${vocab_scan_s} s)`,
  );
} else {
  for (const f of [DBPATH, `${DBPATH}-wal`, `${DBPATH}-shm`]) if (existsSync(f)) unlinkSync(f);
  db = new DatabaseSync(DBPATH);
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
      console.error(`built ${pid}/${N}`);
    }
  }
  db.exec('COMMIT');
  build_s = +((performance.now() - tBuild) / 1000).toFixed(1);
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
    console.error(`unconstrained probe ${p + 1}/${PROBES}: ${times[times.length - 1].toFixed(0)} ms`);
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
    console.error(`scope ${scope} probe ${p - 2}/${PROBES}: ${times[times.length - 1].toFixed(0)} ms`);
  }
  rows.push({ scope, ...quantiles(times) });
}

const db_mb = +(statSync(DBPATH).size / 2 ** 20).toFixed(0);
db.close();
// Probe-only keeps the corpus for the next rerun; a fresh build cleans up after itself.
if (!PROBE_ONLY) for (const f of [DBPATH, `${DBPATH}-wal`, `${DBPATH}-shm`]) if (existsSync(f)) unlinkSync(f);

const out = {
  probe: 'ticket 0025 X4 — json_each-constrained MATCH cost by rowid-set scope, on a synthetic 477k corpus',
  rule:
    'SPEC.md §5.3 X4: ladder step at the largest scope with constrained-MATCH p95 <= 150 ms; ' +
    'if even 1k exceeds it, no constrained step ships',
  substrate: PROBE_ONLY
    ? `REAL corpus at ${DBPATH}: ${N} passages of the author's own library, probed with terms ` +
      'drawn from ITS OWN vocabulary via fts5vocab, one per df band (>=10%, 0,1-1%, <0,1%). ' +
      'The synthetic vocabulary is NOT used here: its terms are near-absent from a real index, ' +
      'so they would answer in about a millisecond and, X4 being an upper bound, read as a pass.'
    : 'SYNTHETIC corpus: 477,512 passages of 60 Zipf(1.0)-distributed words over a 50k ' +
      'vocabulary, external-content FTS5, unicode61 remove_diacritics 2, OR-of-quoted-terms ' +
      'probes mixing common/mid/rare df. The cost curve SHAPE is structural in these; the ' +
      'absolute numbers are indicative until the workstation re-runs this on the real index.',
  host: PROBE_ONLY
    ? 'workstation doudou, the real library'
    : 'session container (weaker substrate than the workstation: a pass here is conservative)',
  vocabulary: PROBE_ONLY
    ? {
        source: 'fts5vocab(main, passages_fts, row) on the index under test',
        scan_s: vocab_scan_s,
        terms_per_band: TERM_POOLS.map((pool) => pool.length),
        sample_per_band: TERM_POOLS.map((pool) => pool[0]),
      }
    : { source: 'synthetic Zipf(1.0) vocabulary generated with the corpus' },
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
