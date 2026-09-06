import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const context = {};
vm.runInNewContext(fs.readFileSync('bench/sdt-sitter/scheduler.js', 'utf8'), context);
// The host half of the journal (emit, heartbeat, shutdown) lives in bootstrap.js;
// loading it here lets the ring be driven by the real scheduler rather than by hand.
const ui = {};
vm.runInNewContext(fs.readFileSync('bench/sdt-sitter/bootstrap.js', 'utf8'), ui);
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
/* Distinct from 'failure suppresses same source for session': that one returns false, never
   rejects, and never reaches host.reportError. A rejection thrown out of the per-candidate
   try must stay inside it — escaping to the outer catch would end the sweep in 'error' with
   candidate 2 unadmitted and the host never told. The state assertions carry the rest of the
   catch block, which the UI reads: the tooltip text, the bucket the document moves out of, and
   the finally that releases the spinner. Each is dropped by a plausible edit on its own. */
await test('native rejection mid-job is reported once and the next document is still admitted', async () => {
  const f = fixture(), reportCalls = [], ensure = f.host.ensure;
  f.host.reportError = async (before, error) => { reportCalls.push({ before, error }); };
  f.host.ensure = async (id, progress) => {
    if (id !== 1) return ensure(id, progress);
    f.calls.push(id); progress(30); progress(60); progress(90);
    throw new Error('native worker died');
  };
  await f.api.sweep();
  assert.deepEqual(f.calls, [1, 2]);
  assert.equal(reportCalls.length, 1);
  assert.equal(reportCalls[0].before.identity, '1');
  assert.equal(reportCalls[0].error.message, 'native worker died');
  assert.equal(f.api.state.failed, 1); assert.equal(f.api.state.completed, 1);
  assert.equal(f.api.state.error, 'Error: native worker died');
  assert.equal(f.api.state.counts['failed-session'], 1); assert.equal(f.api.state.counts.current, 1);
  assert.equal(f.api.state.counts['missing-pack'], 0);
  assert.equal(f.api.state.samples.length, 1);
  assert.equal(f.api.state.active, null); assert.equal(f.api.state.pending.length, 0);
  assert.equal(f.api.state.phase, 'waiting');
});
/* Distinct from 'resource or native queue blockage admits nothing': that one holds blocked()
   constant for a whole sweep, so it cannot tell a per-candidate check from a single check
   hoisted before the loop — both refuse everything. Here the reading dips for one admission
   and recovers, over three candidates, which separates three implementations that the two-
   candidate shape cannot: a hoisted check runs all three, `continue` on the blocked branch
   skips only the blocked one and runs the third, and the real `break` halts the sweep. The
   third candidate is what makes the halt observable; with two, refusing the last one and
   halting look identical. */
await test('resources crossing the threshold halt the sweep, they do not skip one document', async () => {
  const f = fixture(); let checks = 0;
  f.host.list = async () => [1, 2, 3];
  f.host.blocked = async () => (++checks === 2 ? 'low-disk' : null);
  await f.api.sweep();
  assert.deepEqual(f.calls, [1]);
  assert(f.cached.has(1));
  assert.equal(f.api.state.completed, 1); assert.equal(f.api.state.failed, 0);
  assert.equal(f.api.state.samples.length, 1);
  assert.equal(f.api.state.active, null);
  assert.deepEqual([...f.api.state.pending].map(item => item.id), [2, 3]);
  assert.equal(f.api.state.phase, 'low-disk');
});
await test('unsupported, missing and future-version packs are never overwritten', async () => {
  for (const status of ['unsupported', 'missing-source', 'unsupported-pack', 'excluded']) {
    const f = fixture(); f.host.inspect = async () => ({ status });
    await f.api.sweep(); assert.equal(f.calls.length, 0);
  }
});
await test('the journal ring keeps its last records and evicts the oldest', async () => {
  const ring = context.createSDTJournal(3);
  for (const kind of ['a', 'b', 'c', 'd']) ring.push({ kind });
  // Array.from: the ring's arrays come from the sandbox realm and never compare equal.
  assert.deepEqual(Array.from(ring.tail(10), record => record.kind), ['b', 'c', 'd']);
  assert.deepEqual(Array.from(ring.tail(2), record => record.kind), ['c', 'd']);
  assert.deepEqual(Array.from(ring.tail(), record => record.kind), ['b', 'c', 'd']);
});
await test('one sweep journals admit, submit, progress and settle, carrying no title', async () => {
  const f = fixture();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  // The real host callbacks, not stand-ins: a spy the test writes itself would
  // only re-prove the test's own three lines.
  f.host.emit = ui.emit; f.host.reportError = ui.reportSettleFailure;
  f.host.inspect = async id => ({ status: f.cached.has(id) ? 'current' : 'missing-pack',
    identity: String(id), cacheKey: `1/${id}`, sourceBytes: 100 * id, pages: id,
    title: 'Secret Title', parentTitle: 'Secret Parent', directory: '/secret/storage' });
  f.host.ensure = async (id, progress) => {
    f.calls.push(id);
    if (id !== 1) return false;
    progress(90); f.cached.add(id); return true;
  };
  await f.api.sweep();
  const seen = Array.from(ring.tail(50));
  assert.deepEqual(seen.map(record => record.kind),
    ['admit', 'submit', 'progress', 'settle', 'admit', 'submit', 'settle']);
  for (const record of seen) assert(Number.isFinite(record.at));
  assert.deepEqual({ ...seen[0], at: 0 }, { at: 0, kind: 'admit', level: 'state', id: 1, sourceBytes: 100, pages: 1 });
  assert.deepEqual({ ...seen[1], at: 0 }, { at: 0, kind: 'submit', level: 'state', id: 1 });
  assert.deepEqual({ ...seen[2], at: 0 }, { at: 0, kind: 'progress', level: 'trace', id: 1, progress: 90 });
  assert.equal(seen[3].kind, 'settle'); assert.equal(seen[3].ok, true);
  assert.equal(seen[3].id, 1); assert(Number.isFinite(seen[3].ms));
  assert.equal(seen[6].level, 'error'); assert.equal(seen[6].ok, false);
  assert.equal(seen[6].id, '1/2'); assert(seen[6].error.includes('did not persist'));
  // The whitelist is the privacy rule: spreading `before` wholesale would leak these.
  assert(!JSON.stringify(seen).includes('Secret'));
  assert(!JSON.stringify(seen).includes('/secret/storage'));
});
await test('a blocked gate journals its reason once, idle waits at trace level', async () => {
  for (const [reason, kind, level] of [['native-worker-busy', 'worker-idle-wait', 'trace'],
    ['low-memory', 'refuse', 'state'], ['low-disk', 'refuse', 'state']]) {
    const f = fixture(), seen = [];
    f.host.emit = (emitted, detail, emittedLevel = 'state') => seen.push({ kind: emitted, level: emittedLevel, ...detail });
    f.host.blocked = async () => reason;
    await f.api.sweep();
    assert.deepEqual(seen, [{ kind, level, reason }]);
  }
});
await test('Zotero.debug and pref failures never reach the sitter loop', async () => {
  const ring = context.createSDTJournal(10);
  ui.journal = ring; ui.sealed = false;
  ui.Zotero = { debug: () => { throw new Error('debug output unavailable'); },
    Prefs: { get: () => { throw new Error('prefs unavailable'); } } };
  ui.emit('admit', { id: 7 });
  assert.deepEqual(ring.tail(1)[0].kind, 'admit');
  assert.equal(ring.tail(1)[0].id, 7);
  assert.equal(ring.tail(1)[0].level, 'state');
  assert(Number.isFinite(ring.tail(1)[0].at));
  // The invariant is the whole channel, not the half after the ring: a detail the
  // ring itself rejects must not reach the loop either.
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  ui.emit('probe', { get hostile() { throw new Error('a detail that will not be read'); } });
  assert.equal(ring.tail(50).length, 1);
  ui.emit('admit', { id: 8 });
  assert.equal(ring.tail(1)[0].id, 8);
});
await test('a failed candidate journals settle without the attachment title', async () => {
  const f = fixture();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  f.host.emit = ui.emit; f.host.reportError = ui.reportSettleFailure;
  f.host.inspect = async id => ({ status: 'missing-pack', identity: String(id), cacheKey: `1/${id}`,
    title: 'Secret Title', parentTitle: 'Secret Parent', directory: '/secret/storage' });
  f.host.ensure = async id => { f.calls.push(id); return false; };
  await f.api.sweep();
  const settled = Array.from(ring.tail(50)).filter(record => record.kind === 'settle');
  assert.equal(settled.length, 2);
  for (const record of settled) {
    assert.equal(record.level, 'error'); assert.equal(record.ok, false);
    assert(record.error.includes('did not persist'));
  }
  assert.deepEqual(settled.map(record => record.id), ['1/1', '1/2']);
  assert(!JSON.stringify(Array.from(ring.tail(50))).includes('Secret'));
});
await test('a platform IO error reaches the journal without the path it names', async () => {
  // The second inspect(), after extraction, reaches IOUtils and attachmentHash
  // minutes after the source was last known to exist. Its throw is the realistic
  // failure, and its message embeds the file it failed on.
  const thrown = [
    Object.assign(new Error(
      'Could not open the file at /home/haduong/Zotero/storage/ABCD2345/Secret Title.pdf'),
    { name: 'NotFoundError' }),
    new Error('Access denied to file:///home/haduong/Zotero/storage/ABCD2345/Secret.epub'),
    new Error('Unable to read C:\\Users\\haduong\\Zotero\\storage\\ABCD2345\\Secret.pdf'),
  ];
  for (const error of thrown) {
    const f = fixture();
    const ring = context.createSDTJournal(50);
    const debugged = [];
    ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
    ui.Zotero = { debug: line => debugged.push(line), Prefs: { get: () => true } };
    f.host.emit = ui.emit; f.host.reportError = ui.reportSettleFailure;
    f.host.list = async () => [1];
    f.host.inspect = async id => {
      if (f.calls.length) throw error;
      return { status: 'missing-pack', identity: String(id), cacheKey: `1/${id}` };
    };
    f.host.ensure = async id => { f.calls.push(id); return true; };
    await f.api.sweep();
    const settled = Array.from(ring.tail(50)).filter(record => record.kind === 'settle');
    assert.equal(settled.length, 1);
    // The opaque cache key is identity the journal is meant to carry, and it holds
    // a separator; the error text is what must carry no filesystem identity at all.
    for (const leak of ['Secret', 'haduong', 'ABCD2345', '.pdf', '.epub', '/', '\\']) {
      assert(!settled[0].error.includes(leak), `${leak} reached the record: ${settled[0].error}`);
    }
    const written = debugged.join(' ');
    for (const leak of ['Secret', 'haduong', 'ABCD2345', '.pdf', '.epub']) {
      assert(!written.includes(leak), `${leak} reached Zotero.debug: ${written}`);
    }
    // Scrubbed, not silenced: the failure's shape still has to be readable.
    assert(settled[0].error.startsWith(error.name));
    assert(settled[0].error.includes('<path>') || settled[0].error.includes('<file>'));
    assert(debugged.some(line => line.includes('settle')));
  }
});
await test('a late dialog unload is recorded once, never twice', async () => {
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  const dialog = {};
  ui.noteDialogClose(dialog); ui.noteDialogClose(dialog);
  assert.deepEqual(Array.from(ring.tail(50), record => record.kind), ['dialog-close']);
});
await test('after a hang the ring names the active document, its last progress and every heartbeat', async () => {
  const f = fixture(), entered = deferred(), finish = deferred();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  f.host.emit = ui.emit; f.host.now = () => Date.now();
  let callback;
  f.host.ensure = async (id, progress) => {
    f.calls.push(id); callback = progress; entered.resolve(); await finish.promise; return true;
  };
  const running = f.api.sweep();
  await entered.promise;
  callback(42);
  for (let tick = 0; tick < 3; tick++) ui.heartbeatTick();
  const tail = Array.from(ring.tail(50));
  assert.deepEqual(tail.map(record => record.kind),
    ['admit', 'submit', 'progress', 'heartbeat', 'heartbeat', 'heartbeat']);
  const beat = tail[tail.length - 1];
  assert.equal(beat.level, 'trace'); assert.equal(beat.id, 1); assert.equal(beat.progress, 42);
  assert.equal(beat.phase, 'extracting'); assert(beat.elapsedMS >= 0); assert(beat.sinceProgressMS >= 0);
  assert(beat.pending >= 1);
  f.api.stop(); finish.resolve(); await running;
  // The heartbeat is silent with no document under the worker.
  const settled = ring.tail(50).length;
  ui.heartbeatTick();
  assert.equal(ring.tail(50).length, settled);
});
await test('shutdown is the last record even with a submission still in flight', async () => {
  const f = fixture(), entered = deferred(), finish = deferred();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true }, SDTPackSitter: { state: f.api.state } };
  f.host.emit = ui.emit; f.host.now = () => Date.now();
  let callback;
  f.host.ensure = async (id, progress) => {
    f.calls.push(id); callback = progress; entered.resolve(); await finish.promise;
    progress(100); f.cached.add(id); return true;
  };
  const running = f.api.sweep();
  await entered.promise;
  const dialog = {};
  ui.noteDialogClose(dialog);
  ui.shutdown(null, 4);
  const closed = ring.tail(50).length;
  const updates = f.updates.length;
  // Everything that resumes after an await outlives disable and must find the
  // channel sealed: a cache write in flight, a second unload, the native promise.
  ui.emit('cache-write', { rows: 3, compact: false });
  ui.emit('dialog-open', { reused: false });
  ui.noteDialogClose(dialog);
  callback(50); finish.resolve(); await running;
  ui.heartbeatTick();
  // The seal keeps records off the far side of shutdown, so it would also hide a
  // shutdown that never removed the callbacks. These read the sitter, not the ring.
  assert.equal(f.api.state.enabled, false);
  assert.equal(f.updates.length, updates);
  assert.deepEqual(f.calls, [1]);
  const tail = Array.from(ring.tail(50));
  assert.equal(tail.length, closed);
  assert.deepEqual(tail.map(record => record.kind),
    ['admit', 'submit', 'dialog-close', 'shutdown']);
  assert.equal(tail[tail.length - 1].reason, 'disable');
  assert.equal(ui.Zotero.SDTPackSitter, undefined);
});
console.log(JSON.stringify({ tests: results, result: 'pass' }));

const samples = [1, 2, 3].map(n => ({ milliseconds: n * 1000, pages: 10, sourceBytes: 100 }));
assert.equal(context.estimateSDTDuration(samples.slice(0, 2), { pages: 10 }), null);
let prediction = context.estimateSDTDuration(samples, { pages: 20 });
assert.equal(prediction.low, 2200); assert.equal(prediction.median, 4000); assert.equal(prediction.high, 5800);
prediction = context.estimateSDTDuration(samples, { sourceBytes: 200 });
assert.equal(prediction.median, 4000); assert.equal(prediction.basis, 'sourceBytes');
assert.equal(context.estimateSDTDuration(samples, {}), null);

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
