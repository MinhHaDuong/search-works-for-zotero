import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const context = {};
vm.runInNewContext(fs.readFileSync('bench/sdt-sitter/scheduler.js', 'utf8'), context);
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function fixture() {
  const cached = new Set(), calls = [], updates = [];
  let clock = 0;
  const host = {
    list: async () => [1, 2],
    inspect: async id => ({ status: cached.has(id) ? 'current' : 'missing-pack', identity: String(id) }),
    blocked: async () => null, yield: async () => {}, now: () => ++clock,
    changed: state => updates.push(JSON.stringify(state)),
    ensure: async (id, progress) => { calls.push(id); progress(90); cached.add(id); return true; },
  };
  const api = context.createSDTSitter(host);
  return { api, host, cached, calls, updates };
}
const results = [];
async function test(name, body) { await body(); results.push(name); }
await test('census precedes generation; cache hit is read-only', async () => {
  const f = fixture();
  const ensure = f.host.ensure;
  f.host.ensure = (...args) => { assert.equal(f.api.state.scanned, 2); return ensure(...args); };
  await f.api.sweep(); await f.api.sweep();
  assert.deepEqual(f.calls, [1, 2]); assert.equal(f.api.state.completed, 2);
  assert.equal(f.api.state.counts.current, 2);
});
await test('resource or native queue blockage admits nothing', async () => {
  for (const reason of ['low-memory', 'low-disk', 'native-worker-busy', 'resources-unavailable']) {
    const f = fixture(); f.host.blocked = async () => reason;
    await f.api.sweep(); assert.equal(f.calls.length, 0); assert.equal(f.api.state.phase, reason);
    f.host.blocked = async () => null; await f.api.sweep(); assert.equal(f.calls.length, 2);
  }
});
await test('unresolved native promise and concurrent sweeps do not multiply admissions', async () => {
  const f = fixture(), entered = deferred(), finish = deferred();
  f.host.ensure = async id => { f.calls.push(id); entered.resolve(); await finish.promise; f.cached.add(id); return true; };
  const running = f.api.sweep(); await entered.promise;
  await f.api.sweep(); assert.deepEqual(f.calls, [1]);
  f.api.stop(); finish.resolve(); await running; assert.deepEqual(f.calls, [1]);
});
await test('disable during ensure leaves completion but no UI callbacks or next admission', async () => {
  const f = fixture(), entered = deferred(), finish = deferred(); let callback;
  f.host.ensure = async (id, progress) => { f.calls.push(id); callback = progress; entered.resolve(); await finish.promise; f.cached.add(id); return true; };
  const running = f.api.sweep(); await entered.promise;
  f.api.stop(); const count = f.updates.length; callback(100); finish.resolve(); await running;
  assert.equal(f.updates.length, count); assert.deepEqual(f.calls, [1]); assert(f.cached.has(1));
});
await test('disable during census or admission resource await prevents submission', async () => {
  for (const name of ['inspect', 'blocked']) {
    const f = fixture(), entered = deferred(), finish = deferred(); const original = f.host[name];
    f.host[name] = async (...args) => { entered.resolve(); await finish.promise; return original(...args); };
    const running = f.api.sweep(); await entered.promise; f.api.stop(); finish.resolve(); await running;
    assert.equal(f.calls.length, 0);
  }
});
await test('failure suppresses same source for session but changed source retries', async () => {
  const f = fixture(); f.host.ensure = async id => { f.calls.push(id); return false; };
  await f.api.sweep(); await f.api.sweep(); assert.deepEqual(f.calls, [1, 2]);
  f.host.inspect = async id => ({ status: 'missing-pack', identity: `${id}/changed` });
  await f.api.sweep(); assert.deepEqual(f.calls, [1, 2, 1, 2]);
});
await test('native success without current persisted cache counts as failure', async () => {
  const f = fixture(); f.host.ensure = async () => true;
  await f.api.sweep(); assert.equal(f.api.state.failed, 2); assert.equal(f.api.state.completed, 0);
});
await test('both the file and its reference title reach pending and active info', async () => {
  const f = fixture();
  f.host.inspect = async id => ({ status: f.cached.has(id) ? 'current' : 'missing-pack',
    identity: String(id), title: `Fichier ${id}`, parentTitle: `Référence ${id}` });
  const active = [], queued = [];
  const ensure = f.host.ensure;
  const describe = item => `${item.parentTitle}/${item.title}`;
  f.host.ensure = (id, progress) => {
    active.push(describe(f.api.state.activeInfo));
    queued.push(f.api.state.pending.map(describe).join(','));
    return ensure(id, progress);
  };
  await f.api.sweep();
  assert.deepEqual(active, ['Référence 1/Fichier 1', 'Référence 2/Fichier 2']);
  assert.equal(queued[0], 'Référence 1/Fichier 1,Référence 2/Fichier 2');
});
await test('a file with no parent reference threads null, never undefined', async () => {
  const f = fixture();
  f.host.inspect = async id => ({ status: f.cached.has(id) ? 'current' : 'missing-pack',
    identity: String(id), title: `Fichier ${id}` });
  const seen = [];
  const ensure = f.host.ensure;
  f.host.ensure = (id, progress) => { seen.push(f.api.state.activeInfo.parentTitle); return ensure(id, progress); };
  await f.api.sweep();
  assert.deepEqual(seen, [null, null]);
});
await test('unsupported, missing and future-version packs are never overwritten', async () => {
  for (const status of ['unsupported', 'missing-source', 'unsupported-pack', 'excluded']) {
    const f = fixture(); f.host.inspect = async () => ({ status });
    await f.api.sweep(); assert.equal(f.calls.length, 0);
  }
});
console.log(JSON.stringify({ tests: results, result: 'pass' }));

const samples = [1, 2, 3].map(n => ({ milliseconds: n * 1000, pages: 10, sourceBytes: 100 }));
assert.equal(context.estimateSDTDuration(samples.slice(0, 2), { pages: 10 }), null);
let prediction = context.estimateSDTDuration(samples, { pages: 20 });
assert.equal(prediction.low, 2200); assert.equal(prediction.median, 4000); assert.equal(prediction.high, 5800);
prediction = context.estimateSDTDuration(samples, { sourceBytes: 200 });
assert.equal(prediction.median, 4000); assert.equal(prediction.basis, 'sourceBytes');
assert.equal(context.estimateSDTDuration(samples, {}), null);

const ui = {};
const bootstrapSource = fs.readFileSync('bench/sdt-sitter/bootstrap.js', 'utf8');
const schedulerSource = fs.readFileSync('bench/sdt-sitter/scheduler.js', 'utf8');
vm.runInNewContext(bootstrapSource, ui);

/* The tooltip is the only zero-click view of the sitter. Drive it with real
   state: a blocked or failed sitter must never read like a healthy idle one,
   and no internal phase name may reach it. */
const literals = (source, pattern) => [...source.matchAll(pattern)].map(match => match[1]);
const blockedBody = bootstrapSource.slice(bootstrapSource.indexOf('async function blocked(info)'),
  bootstrapSource.indexOf('sitter = createSDTSitter'));
const phases = new Set([
  ...literals(blockedBody, /return '([^']+)'/g),
  ...literals(schedulerSource, /state\.phase = '([^']+)'/g),
  ...literals(schedulerSource, /phase: '([^']+)'/g),
  ...literals(bootstrapSource, /sitter\.state\.phase = '([^']+)'/g),
]);
// Guard the extraction itself: a regex that matched nothing would pass vacuously.
assert(phases.size >= 12, `phase enumeration failed: ${[...phases].join(' | ')}`);
for (const phase of phases) {
  assert(phase in ui.SDT_PHASE_LABELS, `phase '${phase}' has no decided tooltip`);
}

const idle = ui.describeSDTTooltip({ phase: 'waiting', completed: 3 });
assert.equal(idle, '3 fichiers indexés');
assert.equal(ui.describeSDTTooltip({ phase: 'ready', completed: 1 }), '1 fichier indexé');
assert.equal(ui.describeSDTTooltip({ phase: 'waiting', completed: 0 }), '0 fichier indexé');
assert.equal(ui.describeSDTTooltip({ phase: 'census', completed: 2 }), 'Recensement — 2 fichiers indexés');
// A bare count is reserved for the two healthy idle phases. Mapping any other
// phase to null would silence it exactly as the raw-name removal once did.
const silent = [...phases].filter(phase => !ui.SDT_PHASE_LABELS[phase]).sort();
assert.deepEqual(silent, ['ready', 'waiting'],
  `only healthy idle phases may render a bare count: ${silent.join(' | ')}`);
const stalled = [...phases].filter(phase => !silent.includes(phase) && phase !== 'census');
const rendered = new Set();
for (const phase of stalled) {
  const tooltip = ui.describeSDTTooltip({ phase, completed: 3 });
  assert(tooltip !== idle, `'${phase}' is indistinguishable from a healthy idle sitter`);
  assert(!tooltip.includes(phase), `'${phase}' leaks its internal name: ${tooltip}`);
  assert(!/[a-z]-[a-z]/.test(tooltip), `'${phase}' reads as an identifier, not a sentence: ${tooltip}`);
  assert(tooltip.endsWith(idle), `'${phase}' dropped the count: ${tooltip}`);
  rendered.add(tooltip);
}
assert.equal(rendered.size, stalled.length, 'two blocking phases share one tooltip');
// An unlisted phase degrades to the bare count instead of leaking its name.
assert.equal(ui.describeSDTTooltip({ phase: 'a-brand-new-phase', completed: 3 }), idle);

/* Zotero auto-names attachments, so the reference must lead. A line reading
   only 'Full Text PDF' identifies nothing, which is the whole point of
   carrying a title at all. */
assert.equal(ui.describeSDTActiveFile({ active: 7,
  activeInfo: { parentTitle: 'Sen 1999', title: 'Full Text PDF' } }), 'Sen 1999 — Full Text PDF');
assert.equal(ui.describeSDTActiveFile({ active: 7,
  activeInfo: { parentTitle: null, title: 'rapport.pdf' } }), 'rapport.pdf');
assert.equal(ui.describeSDTActiveFile({ active: 7,
  activeInfo: { parentTitle: 'Sen 1999', title: null } }), 'Sen 1999');
assert.equal(ui.describeSDTActiveFile({ active: 7, activeInfo: { parentTitle: null, title: null } }),
  'fichier n° 7');
assert.equal(ui.describeSDTActiveFile({ active: 7, activeInfo: null }), 'fichier n° 7');

let coverage = ui.getSDTCoverage({ total: 10, scanned: 10, phase: 'waiting',
  counts: { current: 4, excluded: 2, unsupported: 1, 'failed-session': 1, 'missing-source': 2 } });
assert.equal(coverage.current, 4); assert.equal(coverage.total, 7); assert.equal(coverage.known, true);
coverage = ui.getSDTCoverage({ total: 10, scanned: 4, phase: 'census', counts: { current: 4 } });
assert.equal(coverage.known, false);

const cache = context.createSDTCache(null, 'v');
cache.remember('1/a', 'source-v', 'pack-stamp', { sourceBytes: 100, pages: 2 });
cache.observe('1/a', 'source-v', { sourceBytes: 100, pages: 2, milliseconds: 500 });
const restoredCache = context.createSDTCache(JSON.parse(JSON.stringify(cache.data())), 'v');
assert.equal(restoredCache.samples().length, 1);
assert(restoredCache.check('1/a', 'source-v', 'pack-stamp'));
assert.equal(restoredCache.check('1/a', 'source-v', 'changed-pack'), null);
assert.equal(restoredCache.check('1/a', 'changed-source', 'pack-stamp'), null);
assert.equal(restoredCache.samples().length, 0);
assert.equal(context.createSDTCache(cache.data(), 'new-version').samples().length, 0);
assert.equal(context.createSDTCache({ records: { broken: true } }, 'v').samples().length, 0);
assert.equal(cache.changes().length, 1); cache.saved(cache.changes()); assert.equal(cache.changes().length, 0);
cache.prune(new Set()); assert.equal(cache.samples().length, 0);
