// X7 (ticket 0025): what does one census tick cost, at the sizes that decide the cadence?
//
// The design's freshness loop re-fetches the local full-text census whole every tick
// (DESIGN.md §2.4: the mixed sequence must never be cursored) and diffs it against the
// previous one. The rule (DESIGN.md §3): local census every tick, unless the parse
// exceeds 50 ms at 30k entries — then every 5th tick.
//
// "Parse" here is the whole per-tick CPU cost the rule is guarding: JSON.parse of the
// serialized census plus the diff against the previous tick's map (changed / new /
// removed). The bytes are synthetic — realistic 8-char Zotero keys and version integers
// in the measured real shape (ticket 0012's census is a flat {key: version} object,
// 8 037 entries ≈ 120–200 KB) — because the census SHAPE is fixed by the API and the
// cost is structural in it; no library content enters the number.
//
//   node bench/census_parse.mjs > bench/results/0025-x7-census/parse-cost.json
import { execSync } from 'node:child_process';

const SIZES = [8037, 30000, 100000];
const TICKS = 50; // measured ticks per size, after warmup

// mulberry32: Math.imul keeps every product in 32 bits — a bare `seed * k` overflows the
// 2^53 float mantissa and collapses the sequence into a short cycle, which turns the
// fill-to-n-unique-keys loop below into an infinite one.
let seed = 424242;
function rnd() {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const KEYCHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ23456789';
function key() {
  let k = '';
  for (let i = 0; i < 8; i++) k += KEYCHARS[Math.floor(rnd() * KEYCHARS.length)];
  return k;
}

/** A census: flat {itemKey: version}, versions spread like the measured 0..25036 range. */
function census(n) {
  const c = {};
  let filled = 0;
  while (filled < n) {
    const k = key();
    if (c[k] === undefined) {
      c[k] = Math.floor(rnd() * 25036);
      filled++;
    }
  }
  return c;
}

/** The successor census one tick later: ~0.5% bumped, ~0.1% new, ~0.1% removed. */
function nextTick(prev) {
  const c = { ...prev };
  const keys = Object.keys(prev);
  const bump = Math.max(1, Math.floor(keys.length * 0.005));
  for (let i = 0; i < bump; i++) c[keys[Math.floor(rnd() * keys.length)]] += 1;
  const churn = Math.max(1, Math.floor(keys.length * 0.001));
  for (let i = 0; i < churn; i++) delete c[keys[Math.floor(rnd() * keys.length)]];
  for (let i = 0; i < churn; i++) c[key()] = Math.floor(rnd() * 25036);
  return c;
}

/** One tick: parse the wire bytes, diff against the previous map. Returns the new map. */
function tick(serialized, prevMap) {
  const parsed = JSON.parse(serialized);
  const nextMap = new Map(Object.entries(parsed));
  const changed = [];
  const removed = [];
  for (const [k, v] of nextMap) {
    const was = prevMap.get(k);
    if (was === undefined || was !== v) changed.push(k);
  }
  for (const k of prevMap.keys()) if (!nextMap.has(k)) removed.push(k);
  return { nextMap, changed, removed };
}

const rows = [];
for (const n of SIZES) {
  let prev = census(n);
  let prevMap = new Map(Object.entries(prev));
  // Pre-serialize the tick bodies so the measured region is parse+diff, not generation.
  const bodies = [];
  for (let i = 0; i < TICKS + 5; i++) {
    prev = nextTick(prev);
    bodies.push(JSON.stringify(prev));
  }
  for (let i = 0; i < 5; i++) prevMap = tick(bodies[i], prevMap).nextMap; // warm
  const times = [];
  for (let i = 5; i < bodies.length; i++) {
    const t = performance.now();
    const r = tick(bodies[i], prevMap);
    times.push(performance.now() - t);
    prevMap = r.nextMap;
  }
  times.sort((a, b) => a - b);
  const at = (q) => times[Math.min(times.length - 1, Math.floor(times.length * q))];
  rows.push({
    entries: n,
    serialized_bytes: bodies[bodies.length - 1].length,
    ticks_measured: TICKS,
    median_ms: +at(0.5).toFixed(2),
    p95_ms: +at(0.95).toFixed(2),
    max_ms: +times[times.length - 1].toFixed(2),
  });
}

const out = {
  probe: 'ticket 0025 X7 — census parse+diff cost per tick, at the sizes that decide the cadence',
  rule: 'DESIGN.md §3: local census every tick unless parse > 50 ms at 30k entries, then every 5th tick',
  substrate:
    'SYNTHETIC census bodies in the measured wire shape (flat {key: version}, 8-char keys, ' +
    'versions 0..25036 per bench/results/0012-fulltext-sequence). The shape is fixed by the ' +
    'API and the cost structural in it; no library content is needed for this number.',
  tick_definition: 'JSON.parse of the serialized census + full diff against the previous map (changed/new/removed)',
  host: 'session container (weaker substrate than the workstation: a pass here is conservative)',
  cpu: execSync('grep -m1 "model name" /proc/cpuinfo').toString().split(':')[1].trim(),
  node: process.version,
  timestamp_utc: new Date().toISOString(),
  rows,
};
console.log(JSON.stringify(out, null, 2));
