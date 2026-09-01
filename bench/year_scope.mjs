// Can a query be scoped by YEAR at an affordable cost? (ticket 0025, after X4)
//
// X4 measured ONE mechanism — `rowid IN (SELECT value FROM json_each(?))`, an arbitrary
// rowid set shipped as JSON — and found it dominated: constraining to a thousand rowids
// cost more than ranking the whole 477 512-passage corpus. That is the mechanism a
// COLLECTION or a TAG needs, because their membership is an arbitrary set the index does
// not store.
//
// A YEAR is not that. It is a stored attribute of an item, so it can be a column with an
// index on it, and the filter becomes an ordinary SQL predicate the planner can push into
// the scan. Reading X4's verdict as "scoping is dead" would be reading a result about one
// mechanism as a result about the whole space — so this measures the other mechanism
// rather than assuming either way.
//
// THE CONTROL IS THE POINT. Each year scope is run twice against the SAME set of items:
// once as an indexed predicate, once through X4's json_each blob. If the predicate is
// cheap where the blob is not, the mechanism is the cause and scoping itself is affordable.
// If BOTH are slow, the pessimistic reading was right and this reports that instead.
//
//   node bench/year_scope.mjs --db <index.sqlite> --years <years.json> --output <out.json>
//
// `years.json` maps item_key -> year, harvested from the Zotero local API by
// bench/harvest_years.py, because the index itself stores no date — which is the finding
// that comes before any of these numbers.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, writeFileSync, copyFileSync, existsSync, unlinkSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { execSync } from 'node:child_process';

const { values: opt } = parseArgs({
  options: {
    db: { type: 'string' },
    years: { type: 'string' },
    output: { type: 'string' },
    work: { type: 'string', default: '/tmp/x-year-scope.sqlite' },
    probes: { type: 'string', default: '12' },
    topk: { type: 'string', default: '30' },
  },
});
if (!opt.db || !opt.years || !opt.output) {
  console.error('usage: node bench/year_scope.mjs --db <index> --years <map.json> --output <f.json>');
  process.exit(2);
}
const PROBES = Number(opt.probes);
const TOPK = Number(opt.topk);

// A working COPY: this adds a column, and the measurement substrate is not ours to mutate.
for (const f of [opt.work, `${opt.work}-wal`, `${opt.work}-shm`]) if (existsSync(f)) unlinkSync(f);
copyFileSync(opt.db, opt.work);
const db = new DatabaseSync(opt.work);

const N = db.prepare('SELECT count(*) AS n FROM passages').get().n;

// ---- give the index the date it does not have -----------------------------------------
const years = JSON.parse(readFileSync(opt.years, 'utf8'));
db.exec('ALTER TABLE items ADD COLUMN year INTEGER');
db.exec('BEGIN');
const setYear = db.prepare('UPDATE items SET year = ? WHERE item_key = ?');
let stamped = 0;
for (const [key, y] of Object.entries(years)) {
  if (Number.isInteger(y)) stamped += setYear.run(y, key).changes;
}
db.exec('COMMIT');
// The index that makes the predicate a seek rather than a scan. Cost is reported: it is
// part of what adopting this would cost, not a free assumption.
const tIdx = performance.now();
db.exec('CREATE INDEX items_year ON items(year)');
db.exec('CREATE INDEX passages_item_key ON passages(item_key)');
const index_build_ms = +(performance.now() - tIdx).toFixed(1);

const withYear = db.prepare('SELECT count(*) AS n FROM items WHERE year IS NOT NULL').get().n;
const span = db.prepare('SELECT min(year) AS lo, max(year) AS hi FROM items WHERE year IS NOT NULL').get();

// ---- probe vocabulary, from the index's own terms (the X4 lesson) ----------------------
db.exec('CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, passages_fts, row)');
const band = (lo, hi) =>
  db
    .prepare('SELECT term FROM temp.v WHERE doc >= ? AND doc < ? ORDER BY doc DESC LIMIT 200')
    .all(Math.floor(lo * N), Math.floor(hi * N))
    .map((r) => r.term)
    .filter((t) => /^[\p{L}\p{N}]+$/u.test(t) && /\p{L}/u.test(t));
const POOLS = [band(0.1, 1.01), band(0.001, 0.01), band(1e-5, 1e-3)];

let seed = 20260829;
function rnd() {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const query = () => POOLS.map((p) => `"${p[Math.floor(rnd() * p.length)]}"`).join(' OR ');

const quant = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const at = (q) => s[Math.min(s.length - 1, Math.floor(s.length * q))];
  return { median_ms: +at(0.5).toFixed(1), p95_ms: +at(0.95).toFixed(1), max_ms: +Math.max(...s).toFixed(1) };
};

// ---- the three shapes ------------------------------------------------------------------
const unconstrained = db.prepare(
  `SELECT p.rowid, bm25(passages_fts) AS s FROM passages_fts
     JOIN passages p ON p.pid = passages_fts.rowid
    WHERE passages_fts MATCH ? ORDER BY s LIMIT ${TOPK}`,
);
// The predicate shape: the filter is a join on an indexed column, applied while ranking,
// so truncation happens after the filter — which is what R5 requires.
const byYear = db.prepare(
  `SELECT p.rowid, bm25(passages_fts) AS s FROM passages_fts
     JOIN passages p ON p.pid = passages_fts.rowid
     JOIN items i ON i.item_key = p.item_key
    WHERE passages_fts MATCH ? AND i.year BETWEEN ? AND ?
    ORDER BY s LIMIT ${TOPK}`,
);
// X4's mechanism, on the SAME items — the control that decides whether the cost is the
// scoping or the way it is expressed.
const byBlob = db.prepare(
  `SELECT rowid, bm25(passages_fts) AS s FROM passages_fts
    WHERE passages_fts MATCH ? AND rowid IN (SELECT value FROM json_each(?))
    ORDER BY s LIMIT ${TOPK}`,
);

const rowidsForYears = (lo, hi) =>
  JSON.stringify(
    db
      .prepare('SELECT p.pid FROM passages p JOIN items i ON i.item_key = p.item_key WHERE i.year BETWEEN ? AND ?')
      .all(lo, hi)
      .map((r) => r.pid),
  );

function arm(label, run, probes = PROBES) {
  for (let w = 0; w < 3; w++) run(query());
  const times = [];
  let rows = 0;
  for (let i = 0; i < probes; i++) {
    const q = query();
    const t = performance.now();
    rows += run(q).length;
    times.push(performance.now() - t);
    console.error(`  ${label} ${i + 1}/${probes}: ${times[times.length - 1].toFixed(0)} ms`);
  }
  return { arm: label, probes, ...quant(times), mean_rows_returned: +(rows / probes).toFixed(1) };
}

// X4 measured the json_each arm as superlinear in scope size, reaching minutes per query.
// Running it on a decade would cost hours and would only re-measure X4's own curve, so the
// control runs where it can finish and is recorded as SKIPPED, with the reason, elsewhere.
// A skipped control is stated, never quietly dropped: the comparison it supports is the
// whole argument of this probe.
const CONTROL_MAX_ROWIDS = 20_000;
const CONTROL_PROBES = 5;

const SCOPES = [
  ['one year (2020)', 2020, 2020],
  ['five years (2016-2020)', 2016, 2020],
  ['a decade (2011-2020)', 2011, 2020],
];

const rows = [arm('unconstrained (whole corpus)', (q) => unconstrained.all(q))];
const scopes = [];
for (const [label, lo, hi] of SCOPES) {
  const blob = rowidsForYears(lo, hi);
  const inScope = JSON.parse(blob).length;
  console.error(`scope ${label}: ${inScope} passages`);
  const predicate = arm(`year predicate — ${label}`, (q) => byYear.all(q, lo, hi));
  const control =
    inScope <= CONTROL_MAX_ROWIDS
      ? arm(`json_each blob — ${label}`, (q) => byBlob.all(q, blob), CONTROL_PROBES)
      : {
          arm: `json_each blob — ${label}`,
          skipped: `scope holds ${inScope} rowids, above the ${CONTROL_MAX_ROWIDS} cap this probe ` +
            'runs the control at. X4 measured that arm superlinear in scope size, so running it here ' +
            'would cost hours and would re-measure X4 rather than test anything new.',
        };
  scopes.push({ scope: label, passages_in_scope: inScope, predicate, json_each_control: control });
}

const out = {
  probe: 'ticket 0025 — is a YEAR-scoped query affordable, where X4 found a rowid-set scope was not?',
  why: (
    'X4 measured rowid-set scoping via json_each and found it dominated by not scoping at all. That is the ' +
    'mechanism a collection or tag needs. A year is a stored attribute, so it can be an indexed predicate ' +
    'instead — a different mechanism, and X4 says nothing about it. Each scope below is run BOTH ways ' +
    'against the same items, so the comparison isolates the mechanism from the scoping.'
  ),
  finding_before_any_number: (
    'The shipped index stores NO date: `items` is (item_key, title) and `passages` carries no date either, ' +
    'so year scoping is not slow today, it is impossible. The years here were harvested from the Zotero ' +
    'local API and added to a COPY of the index. Adding the column is therefore a precondition of the ' +
    'capability, and its cost is reported below rather than assumed away.'
  ),
  db: opt.db,
  passages: N,
  items_total: db.prepare('SELECT count(*) AS n FROM items').get().n,
  items_with_year: withYear,
  year_span: span,
  column_and_index_build_ms: index_build_ms,
  items_stamped: stamped,
  probes_per_arm: PROBES,
  topk: TOPK,
  rule: 'SPEC.md §5.3 X4: the filter allowance is p95 <= 150 ms inside the 300-700 ms typical budget',
  baseline: rows,
  scopes,
  host: execSync('hostname').toString().trim(),
  node: process.version,
  timestamp_utc: new Date().toISOString(),
};
db.close();
writeFileSync(opt.output, JSON.stringify(out, null, 2));
console.log(JSON.stringify({ baseline: rows, scopes }, null, 2));
