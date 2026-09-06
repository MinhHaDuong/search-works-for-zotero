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
await test('the document title reaches pending and active info for the UI', async () => {
  const f = fixture();
  f.host.inspect = async id => ({ status: f.cached.has(id) ? 'current' : 'missing-pack',
    identity: String(id), title: `Titre ${id}` });
  const active = [], queued = [];
  const ensure = f.host.ensure;
  f.host.ensure = (id, progress) => {
    active.push(f.api.state.activeInfo.title);
    queued.push(f.api.state.pending.map(item => item.title).join(','));
    return ensure(id, progress);
  };
  await f.api.sweep();
  assert.deepEqual(active, ['Titre 1', 'Titre 2']);
  assert.equal(queued[0], 'Titre 1,Titre 2');
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
vm.runInNewContext(fs.readFileSync('bench/sdt-sitter/bootstrap.js', 'utf8'), ui);
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
