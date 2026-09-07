import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';


const context = {};
// One read, reused by the phase enumeration below: a second literal copy of this
// path would give verification/probes/sdt_sitter_scheduler_mutants.py two anchors
// where it requires exactly one, and its mutants could no longer be loaded.
const schedulerSource = fs.readFileSync('plugins/sdt-sitter/scheduler.js', 'utf8');
vm.runInNewContext(schedulerSource, context);
// The host half of the journal (emit, heartbeat, shutdown) lives in bootstrap.js;
// loading it here lets the ring be driven by the real scheduler rather than by hand.
// Read once for the same reason, and reused by the phase enumeration below.
const ui = {};
const bootstrapSource = fs.readFileSync('plugins/sdt-sitter/bootstrap.js', 'utf8');
// The plugin loads scheduler.js into bootstrap's own global before it renders
// anything (`Services.scriptloader.loadSubScript(..., globalThis)`), so the census
// classification is in scope there. Two vm contexts are two realms, so the load
// order has to be reproduced by hand or the dialog's own reading of the census
// would be exercised against a binding the runtime has and the test does not.
ui.SDT_STATUS_CLASSES = context.SDT_STATUS_CLASSES;
vm.runInNewContext(bootstrapSource, ui);
// Ticket 0692: every string below now comes from `locale/fr/sdt-pack-sitter.ftl`
// rather than from a literal in bootstrap.js, so the French assertions in this
// file are assertions about the French translation AND about the plugin's own
// loader — which is the pairing that keeps them meaningful.
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
    ['sweep-start', 'admit', 'submit', 'progress', 'settle', 'admit', 'submit', 'settle', 'sweep-end']);
  for (const record of seen) assert(Number.isFinite(record.at));
  assert.deepEqual({ ...seen[1], at: 0 }, { at: 0, kind: 'admit', level: 'state', id: 1, sourceBytes: 100, pages: 1 });
  assert.deepEqual({ ...seen[2], at: 0 }, { at: 0, kind: 'submit', level: 'state', id: 1 });
  assert.deepEqual({ ...seen[3], at: 0 }, { at: 0, kind: 'progress', level: 'trace', id: 1, progress: 90 });
  assert.equal(seen[4].kind, 'settle'); assert.equal(seen[4].ok, true);
  assert.equal(seen[4].id, 1); assert(Number.isFinite(seen[4].ms));
  assert.equal(seen[7].level, 'error'); assert.equal(seen[7].ok, false);
  assert.equal(seen[7].id, '1/2'); assert.equal(seen[7].error, 'Error');
  // The sweep closes on the ring saying how it ended, so a sweep that stopped
  // being scheduled is distinguishable from one that never came back.
  assert.equal(seen[8].level, 'trace'); assert.equal(seen[8].phase, 'waiting');
  assert.equal(seen[8].scanned, 2); assert.equal(seen[8].completed, 1); assert.equal(seen[8].failed, 1);
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
    // The sweep boundaries bracket it; the reason itself still appears exactly once.
    assert.deepEqual(seen.map(record => record.kind), ['sweep-start', kind, 'sweep-end']);
    assert.deepEqual(seen[1], { kind, level, reason });
    assert.equal(seen[2].phase, reason);
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
    assert.equal(record.error, 'Error');
  }
  assert.deepEqual(settled.map(record => record.id), ['1/1', '1/2']);
  assert(!JSON.stringify(Array.from(ring.tail(50))).includes('Secret'));
});
await test('a platform error reaches the journal as its class, never its message', async () => {
  // The second inspect(), after extraction, reaches IOUtils and attachmentHash
  // minutes after the source was last known to exist. Its throw is the realistic
  // failure, and its message names whatever it happened to fail on. Every case
  // below is one a reviewer reproduced against a scrubbing implementation.
  const thrown = [
    [Object.assign(new Error(
      'Could not open the file at /home/haduong/Zotero/storage/ABCD2345/Secret Title.pdf'),
    { name: 'NotFoundError' }), 'NotFoundError'],
    [new Error('Access denied to file:///home/haduong/Zotero/storage/ABCD2345/Secret.epub'), 'Error'],
    [new Error('Unable to read C:\\Users\\Minh Ha Duong\\Zotero\\ABCD2345\\Secret Report.pdf'), 'Error'],
    // The case no token-wise scrub can reach: prose, no path, several words.
    [new Error('Failed to parse Secret - 2019 - A Very Revealing Working Paper.pdf'), 'Error'],
    [Object.assign(new Error('nsresult'), { name: 'NS_ERROR_FILE_UNRECOGNIZED_PATH' }),
      'NS_ERROR_FILE_UNRECOGNIZED_PATH'],
    // A name that is really a message wearing a name's clothes.
    [Object.assign(new Error('x'), { name: 'failed on /home/haduong/Secret.pdf' }), 'Error'],
    ['a thrown string naming /home/haduong/Secret.pdf', 'Error'],
  ];
  for (const [error, expected] of thrown) {
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
    assert.equal(settled[0].error, expected);
    const written = `${JSON.stringify(settled)} ${debugged.join(' ')}`;
    for (const leak of ['Secret', 'haduong', 'ABCD2345', '.pdf', '.epub', 'Revealing', 'Ha ']) {
      assert(!written.includes(leak), `${leak} reached the channel: ${written}`);
    }
    assert(debugged.some(line => line.includes('settle')));
  }
});
await test('a hostile error object neither escapes nor truncates the sweep', async () => {
  // A torn-down compartment can throw from a getter. classifyError runs as an
  // argument to emit(), outside emit()'s own guard, so it carries its own.
  const f = fixture();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  f.host.emit = ui.emit; f.host.reportError = ui.reportSettleFailure;
  f.host.inspect = async id => ({ status: 'missing-pack', identity: String(id), cacheKey: `1/${id}` });
  f.host.ensure = async id => {
    f.calls.push(id);
    throw { get name() { throw new Error('compartment gone'); },
      get message() { throw new Error('compartment gone'); } };
  };
  await f.api.sweep();
  // Both candidates were tried: an escaping throw would abort the loop at the first.
  assert.deepEqual(f.calls, [1, 2]);
  assert.equal(f.api.state.failed, 2);
  const settled = Array.from(ring.tail(50)).filter(record => record.kind === 'settle');
  assert.deepEqual(settled.map(record => record.error), ['<unreadable error>', '<unreadable error>']);
});
await test('a shutdown that throws still seals the channel and records itself', async () => {
  const f = fixture();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true }, SDTPackSitter: {} };
  // Standing in for dialog.close() during app teardown: something in the body
  // throws before the seal is reached.
  ui.sitter = { state: f.api.state, stop() { throw new Error('teardown failed'); } };
  assert.throws(() => ui.shutdown(null, 4), /teardown failed/);
  assert.deepEqual(Array.from(ring.tail(50), record => record.kind), ['shutdown']);
  assert.equal(ring.tail(1)[0].reason, 'disable');
  ui.emit('cache-write', { rows: 1 });
  assert.equal(ring.tail(50).length, 1);
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
    ['sweep-start', 'admit', 'submit', 'progress', 'heartbeat', 'heartbeat', 'heartbeat']);
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
/* Ticket 0704. The sample's clock used to start before ensure(), which hashes the
   file, validates any existing pack, and queues behind whatever native work is
   already running. None of that is a property of the document, and all of it was
   booked as its extraction time. With three samples the 95th percentile IS the
   maximum, so one inflated observation sets the upper bound for every later
   estimate — and the cache keeps only the latest observation per attachment,
   which is now `current` and never re-measured, so the poisoned number outlives
   the session. The injected clock separates the two windows by two orders of
   magnitude, because a sample that split the difference would pass a looser one. */
await test('the queue wait before the first progress tick is not booked as extraction', async () => {
  const f = fixture();
  let clock = 0;
  f.host.now = () => clock;
  f.host.list = async () => [1];
  f.host.ensure = async (id, progress) => {
    clock += 100000;                 // hash, pack validation, and the native queue
    progress(10); clock += 400;
    progress(90); clock += 600;      // the extraction itself: 1000 ms
    f.cached.add(id); return true;
  };
  await f.api.sweep();
  assert.equal(f.api.state.samples.length, 1);
  assert.equal(f.api.state.samples[0].milliseconds, 1000);
  // state.startedAt is untouched, and serviceMS still answers the other question
  // — how long the sitter held the slot — which the UI and the overrun check read.
  assert.equal(f.api.state.startedAt, 0);
  assert.equal(f.api.state.serviceMS, 101000);
});
/* The same timeline as the test above, minus the progress ticks — and it is a
   separate test because the first fix passed the one above and failed this one.
   Falling back to state.startedAt when nothing ever ticked reinstated the whole
   defect for every document that finishes without a callback, which is the
   small, fast, already-cached case. The earlier version of this test asserted
   only `< 60 s` against a clock stepping 10 ms per read, where the poisoned
   value and the honest one are both small: it could not see the defect it was
   standing over. Real numbers, and no sample at all rather than a guessed one. */
await test('a slow queue and no progress tick yields no sample, not a poisoned one', async () => {
  const f = fixture();
  let clock = 1_700_000_000_000;
  f.host.now = () => clock;
  f.host.list = async () => [1];
  f.host.observed = async () => { assert.fail('an unmeasured duration reached the cache'); };
  f.host.ensure = async id => {
    clock += 5000;                      // hash, pack validation and the native queue
    clock += 50;                        // the extraction itself, reporting nothing
    f.cached.add(id); return true;
  };
  await f.api.sweep();
  // Everything else about the document still settles; only the number nobody
  // measured is absent. A 5050 ms sample here is the defect, and so is a 0 ms
  // one — neither was observed.
  assert.equal(f.api.state.completed, 1);
  assert.equal(f.api.state.counts.current, 1);
  // Lengths, not deepEqual against a literal: these arrays come from the sandbox
  // realm and never compare equal to one built here, as the ring test notes.
  assert.equal(f.api.state.samples.length, 0);
  assert.equal(f.api.state.fittedSamples.length, 0);
});
await test('the settle record says the duration is unknown rather than inventing one', async () => {
  const f = fixture(), seen = [];
  let clock = 1_700_000_000_000;
  f.host.now = () => clock;
  f.host.list = async () => [1, 2];
  f.host.emit = (kind, detail, level = 'state') => seen.push({ kind, level, ...detail });
  f.host.ensure = async (id, progress) => {
    clock += 5000;
    if (id === 2) { progress(50); clock += 40; }
    clock += 10;
    f.cached.add(id); return true;
  };
  await f.api.sweep();
  const settled = seen.filter(record => record.kind === 'settle');
  assert.deepEqual(settled.map(record => record.ok), [true, true]);
  // Both succeeded; only one was measurable, and the record says which.
  assert.equal(settled[0].ms, null);
  assert.equal(settled[1].ms, 50);
  assert.equal(f.api.state.samples.length, 1);
});
/* Ticket 0701. The census hashed every attachment on every 30 s sweep, because
   the cache key embeds the source MD5 and so the hash had to be taken before the
   cache could be consulted. Counted across two consecutive sweeps of a library
   nothing has touched, and then across a third where one file has changed — the
   third arm is what separates "skips the hash" from "never hashes again". */
await test('an unchanged library is not re-hashed, a changed file still is', async () => {
  const hashes = context.createSDTSourceHashes();
  const stats = { 1: { size: 10, lastModified: 5 }, 2: { size: 20, lastModified: 7 } };
  const clock = 1_700_000_000_000;
  let hashed = 0;
  const f = fixture();
  f.host.inspect = async id => ({
    status: 'current',
    identity: await hashes.hash(`1/${id}`, `/store/${id}/file.pdf`, stats[id], clock,
      async () => { hashed++; return `md5-${id}-${stats[id].lastModified}`; }),
  });
  await f.api.sweep();
  assert.equal(hashed, 2);
  await f.api.sweep();
  assert.equal(hashed, 2, 'an untouched library was hashed again on the second sweep');
  stats[2] = { size: 20, lastModified: 9 };
  await f.api.sweep();
  assert.equal(hashed, 3, 'a changed file must be hashed again');
  assert.equal(f.api.state.counts.current, 2);
  // Same bytes, different file: the path is in the fingerprint because an
  // attachment can be repointed at a byte-identical size and mtime.
  await hashes.hash('1/1', '/store/1/other.pdf', stats[1], clock, async () => { hashed++; return 'x'; });
  assert.equal(hashed, 4);
  assert.equal(hashes.size(), 2);
  hashes.prune(new Set(['1/1']));
  assert.equal(hashes.size(), 1, 'a deleted attachment keeps its hash forever');
});
/* The author's ruling on ticket 0701 (DECISIONS.md, 2026-09-06): keep the fast
   path, but re-verify on a cadence, so no memoized hash is trusted forever. The
   case it bounds is the one the fingerprint structurally cannot see — a file
   rewritten in place at the same length with its mtime restored, where (path,
   size, mtime) are all still equal and only the bytes have moved. */
await test('a memoized hash expires, so a silent in-place rewrite is caught within the bound', async () => {
  const day = 24 * 60 * 60 * 1000;
  // Two bounds, and the six-hour one is not decoration: run this only at the
  // default and a factory that ignored its argument entirely would pass, since
  // the test's clock would be stepping by exactly the hardcoded window.
  for (const [label, bound, hashes] of [
    ['the shipped default', day, context.createSDTSourceHashes()],
    ['a caller-set bound', 6 * 60 * 60 * 1000, context.createSDTSourceHashes(6 * 60 * 60 * 1000)],
  ]) {
    const stat = { size: 10, lastModified: 5 };
    const t0 = 1_700_000_000_000;
    let content = 'before';
    let hashed = 0;
    const read = now => hashes.hash('1/1', '/store/1/file.pdf', stat, now,
      async () => { hashed++; return `md5-${content}`; });
    assert.equal(await read(t0), 'md5-before');
    content = 'after';                  // rewritten in place; the fingerprint cannot tell
    assert.equal(await read(t0 + bound - 1), 'md5-before', `${label}: the fast path stopped working`);
    assert.equal(hashed, 1, label);
    assert.equal(await read(t0 + bound), 'md5-after', `${label}: a stale hash was trusted past the bound`);
    assert.equal(hashed, 2, label);
    // The re-verify restarts the window rather than hashing on every later call:
    // a bound that collapsed into "always re-hash" would undo the ticket.
    assert.equal(await read(t0 + bound + 1), 'md5-after');
    assert.equal(hashed, 2, label);
    // A clock stepped backwards shortens the window instead of extending it.
    assert.equal(await read(t0), 'md5-after');
    assert.equal(hashed, 3, label);
  }
});
await test('an idle library backs off; anything left to do keeps the 30 s cadence', async () => {
  const idle = fixture();
  idle.host.inspect = async () => ({ status: 'current' });
  await idle.api.sweep();
  assert.equal(idle.api.state.phase, 'waiting'); assert.equal(idle.api.state.candidates, 0);
  assert(ui.nextSweepDelayMS(idle.api.state) >= 30000 * 10,
    `an idle census still polls every ${ui.nextSweepDelayMS(idle.api.state)} ms`);
  // A sweep that did work ends 'waiting' with an empty queue too — pending
  // cannot tell the two apart, which is why `candidates` exists.
  const worked = fixture();
  await worked.api.sweep();
  assert.equal(worked.api.state.phase, 'waiting');
  assert.equal(worked.api.state.pending.length, 0);
  assert.equal(worked.api.state.candidates, 2);
  assert.equal(ui.nextSweepDelayMS(worked.api.state), 30000);
  // And a sweep halted by a resource gate has work waiting: look again soon.
  const held = fixture(); held.host.blocked = async () => 'low-disk';
  await held.api.sweep();
  assert.equal(ui.nextSweepDelayMS(held.api.state), 30000);
  // A census that threw also found no candidate, and it is the case the count
  // alone cannot tell from a finished library. Only the phase separates them,
  // and a broken census must be retried in seconds, not in ten minutes.
  const broken = fixture();
  broken.host.list = async () => { throw new Error('the item table is unreadable'); };
  await broken.api.sweep();
  assert.equal(broken.api.state.phase, 'error');
  assert.equal(broken.api.state.candidates, 0);
  assert.equal(ui.nextSweepDelayMS(broken.api.state), 30000);
});
/* Ticket 0702's trigger, reproduced rather than described: a dialog whose window
   has gone, so one getElementById comes back null halfway through the render.
   render() is reached from publish(), which the scheduler calls from inside its
   own finally, so before the guard this throw rejected sweep() itself and the
   wrapper that reschedules the next sweep never ran — the sitter stopped for the
   session with `phase` still reading 'waiting'. */
await test('a torn-down dialog cannot throw out of render, and says so once', async () => {
  const f = fixture();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  ui.renderFailing = false;
  ui.dialogs.clear();
  ui.dialogs.add({ closed: false,
    document: { getElementById: id => (id === 'sdt-status' ? {} : null) } });
  ui.render(); ui.render(); ui.render();
  const errors = () => Array.from(ring.tail(50)).filter(record => record.kind === 'render-error');
  // Once, not three times: the pulse renders at 10 Hz, and a record per tick
  // would evict the whole ring in minutes — losing the evidence 0703 keeps.
  assert.equal(errors().length, 1);
  assert.equal(errors()[0].level, 'error');
  assert.equal(errors()[0].error, 'TypeError');
  // The latch releases on a render that works, so a second, later episode is
  // still reported. Without this arm a guard that simply never records twice
  // passes everything above — and the arm is also what proves the reset above
  // reaches the sandbox at all, which as a `let` it silently did not.
  ui.dialogs.clear();
  ui.render();
  assert.equal(errors().length, 1);
  ui.dialogs.add({ closed: false,
    document: { getElementById: id => (id === 'sdt-status' ? {} : null) } });
  ui.render(); ui.render();
  assert.equal(errors().length, 2);
  ui.dialogs.clear();
});
/* The scheduler still rejects when the UI it publishes to throws — that is by
   design, and it is why the guard belongs in bootstrap.js rather than here. What
   this pins is that the ring records how the sweep ended even then: sweep-end is
   emitted before the last publish, so the record cannot be lost to the very call
   that ends the sweep. */
await test('the sweep-end record survives a publish that throws', async () => {
  const f = fixture(), seen = [];
  f.host.emit = (kind, detail, level = 'state') => seen.push({ kind, level, ...detail });
  f.host.list = async () => [];
  f.host.changed = () => { throw new Error('render died'); };
  await assert.rejects(() => f.api.sweep(), /render died/);
  assert.deepEqual(seen.map(record => record.kind), ['sweep-start', 'sweep-end']);
  assert.equal(seen[1].phase, 'error');
  // And the loop is left re-entrant: a sweep that threw must not lock the sitter
  // out of every later sweep as well.
  assert.equal(f.api.state.busy, false);
});
/* The other half of the heartbeat, and the half ticket 0703 filed. The test above
   hangs the worker, where `active` names a document; this one hangs the census,
   where it does not — the phase the author's own morning hang most plausibly sat
   in, and the phase the previous `active === null` gate emitted nothing for. The
   final silence assertion is the discriminating arm: a beat that fires whenever
   the sitter merely exists would pass everything above it and fail here. */
await test('a hang in census beats too, naming the phase and no document', async () => {
  const f = fixture(), entered = deferred(), finish = deferred();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true } };
  f.host.emit = ui.emit;
  const inspect = f.host.inspect;
  f.host.inspect = async id => { entered.resolve(); await finish.promise; return inspect(id); };
  const running = f.api.sweep();
  await entered.promise;
  for (let tick = 0; tick < 2; tick++) ui.heartbeatTick();
  const beats = Array.from(ring.tail(50)).filter(record => record.kind === 'heartbeat');
  assert.equal(beats.length, 2);
  assert.equal(beats[0].level, 'trace');
  assert.equal(beats[0].phase, 'census');
  assert.equal(beats[0].id, null);
  // There is no document, so there is no document age. Null, never NaN: a
  // subtraction from a null startedAt would have published NaN as a duration.
  assert.equal(beats[0].elapsedMS, null);
  assert.equal(beats[0].sinceProgressMS, null);
  f.api.stop(); finish.resolve(); await running;
  const settled = ring.tail(50).length;
  ui.heartbeatTick();
  assert.equal(ring.tail(50).length, settled, 'the beat outlived the sweep that justified it');
});
await test('the ring outlives the disable used to recover from a hang', async () => {
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true;
  ui.sitter = { state: { enabled: true }, stop() {} };
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true }, SDTPackSitter: { journal: ring } };
  ui.shutdown(null, 4);
  // Disable is the natural first move against a hang, and it took the only
  // handle on the evidence with it. The second name is never deleted.
  assert.equal(ui.Zotero.SDTPackSitter, undefined);
  assert.equal(ui.Zotero.SDTPackSitterJournal, ring);
  assert.deepEqual(Array.from(ui.Zotero.SDTPackSitterJournal.tail(50), record => record.kind),
    ['shutdown']);
  assert.equal(ui.Zotero.SDTPackSitterJournal.tail(1)[0].reason, 'disable');
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
  /* The other half of shutdown, and until ticket 0695 the untested one. Every
     assertion below the seal reads the RING — what was written — and the ring
     cannot say that the sitter has stopped being able to write anything. Three
     handles and one token do that:

       * `timer` is the armed next sweep, `pulse` the 100 ms redraw, `heartbeat`
         the 60 s beat. A handle left armed keeps firing against a torn-down
         sitter for the rest of the Zotero session — silently, because the seal
         is what stops those callbacks producing records.
       * `generation` is the other half, and it is not redundant with them: the
         sweep wrapper in bootstrap.js re-arms `timer` from inside its own
         `finally`, so a sweep already in flight schedules the next one AFTER
         shutdown has cleared the handle. `token === generation` is the only
         thing that stops it, which is why the bump is asserted here rather
         than taken for granted.

     Substituted here rather than driven through `startup()`: this file has no
     Zotero host, and what is under test is shutdown's own bookkeeping. */
  const cleared = [];
  ui.timers = { clearTimeout: id => cleared.push(['timeout', id]),
    clearInterval: id => cleared.push(['interval', id]) };
  ui.timer = 'next-sweep'; ui.pulse = 'render-pulse'; ui.heartbeat = 'beat';
  const generation = ui.generation;
  ui.shutdown(null, 4);
  assert.deepEqual(cleared,
    [['timeout', 'next-sweep'], ['interval', 'render-pulse'], ['interval', 'beat']],
    'shutdown left a timer armed against a torn-down sitter');
  assert.equal(ui.generation, generation + 1,
    'the generation token was not burned, so an in-flight sweep re-arms itself');
  ui.timers = undefined;
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
  // sweep-end is absent by the seal, not by omission: the sweep it belongs to
  // finishes on the far side of shutdown, which is where nothing may land.
  assert.deepEqual(tail.map(record => record.kind),
    ['sweep-start', 'admit', 'submit', 'dialog-close', 'shutdown']);
  assert.equal(tail[tail.length - 1].reason, 'disable');
  assert.equal(ui.Zotero.SDTPackSitter, undefined);
});
/* Ticket 0699, the acceptance property — and it is deliberately NOT the
   conservation law. `sum(counts[*]) === scanned` holds in any version of this file
   that decrements one bucket for every bucket it increments, unfixed ones
   included, so it cannot tell right totals from wrong ones. What discriminates is
   the *split*: the two numbers a reader actually sees — the coverage line and the
   failure banner — have to account between them for every attachment that is not
   currently indexed, and three whole statuses used to belong to neither.
   `inspection-error` never became a candidate and never touched `state.failed`;
   `unsupported-pack` and `missing-source` sat in the coverage denominator and in
   no user-facing tally at all, so 100 % was unreachable with nothing on screen
   saying why.

   The fixture is messy in the one way that matters. The census enumerates
   `itemAttachments` rows, so the unit is the attachment and not the reference:
   here one reference carries two supported attachments (SPEC.md D6 twins), one
   carries none, and one attachment has no parent at all. A reconciliation keyed
   on a count of references passes on a 1:1 fixture and is wrong on any real
   library. */
await test('every attachment that is not indexed lands in exactly one user-facing total', async () => {
  // Written as references owning attachment rows, because that asymmetry is the
  // point; the sitter only ever sees the flattened rows.
  const references = [
    { reference: 'twins', rows: [{ id: 11, status: 'current' },
      { id: 12, status: 'missing-pack', ensure: 'persists' }] },
    { reference: 'no attachment at all', rows: [] },
    { reference: 'a book nobody scanned', rows: [] },
    { reference: 'unreadable', rows: [{ id: 21, inspectThrows: true }] },
    { reference: 'pack from a newer Zotero', rows: [{ id: 22, status: 'unsupported-pack' }] },
    { reference: 'file gone from disk', rows: [{ id: 23, status: 'missing-source' }] },
    { reference: 'trashed', rows: [{ id: 24, status: 'excluded' }] },
    { reference: 'a video', rows: [{ id: 25, status: 'unsupported' }] },
    { reference: 're-saved source', rows: [{ id: 26, status: 'stale-source', ensure: 'throws' }] },
    { reference: null, rows: [{ id: 27, status: 'invalid-pack', ensure: 'lies' }] },
    { reference: 'older processor', rows: [{ id: 28, status: 'stale-processor' }] },
  ];
  const attachments = references.flatMap(entry => entry.rows);
  // Non-vacuity guards for the cardinality itself: without these three the
  // reconciliation below could be keyed on references and still come out green.
  assert(references.some(entry => entry.rows.length === 2), 'no reference carries twin attachments');
  assert(references.some(entry => entry.rows.length === 0), 'no reference carries zero attachments');
  assert.notEqual(attachments.length, references.length);

  const rows = new Map(attachments.map(row => [row.id, { ...row }]));
  let clock = 0, checks = 0;
  const api = context.createSDTSitter({
    list: async () => [...rows.keys()],
    inspect: async id => {
      const row = rows.get(id);
      if (row.inspectThrows) throw new Error('attachment unreadable');
      return { status: row.status, identity: `id-${id}` };
    },
    // Falls below the threshold for the fourth admission, so the last candidate
    // is still queued when the sweep ends — the bucket a reconciliation that only
    // ever ran a library to completion would never see populated.
    blocked: async () => (++checks > 3 ? 'low-disk' : null),
    yield: async () => {}, now: () => ++clock, changed: () => {},
    ensure: async id => {
      const row = rows.get(id);
      if (row.ensure === 'throws') throw new Error('native worker died');
      // 'lies': native reports success and the re-inspection still shows no
      // current pack. Ticket 0699 keeps that counted as a failure on purpose.
      if (row.ensure === 'persists') row.status = 'current';
      return true;
    },
  });
  await api.sweep();

  const counts = api.state.counts;
  const classes = context.SDT_STATUS_CLASSES;
  const sum = keys => keys.reduce((n, key) => n + (counts[key] || 0), 0);
  // The conservation law, stated as the floor it is rather than as the property.
  assert.equal(Object.values(counts).reduce((a, b) => a + b, 0), attachments.length);
  assert.equal(api.state.total, attachments.length);

  // Every status the fixture set out to exercise really occurred: a classification
  // that silently dropped one would otherwise reconcile against a smaller library.
  for (const status of ['current', 'inspection-error', 'unsupported-pack', 'missing-source',
    'excluded', 'unsupported', 'failed-session', 'stale-processor']) {
    assert(counts[status] > 0, `${status} never occurred: ${JSON.stringify(counts)}`);
  }

  const coverage = ui.getSDTCoverage(api.state);
  assert.equal(coverage.known, true);
  assert.equal(coverage.total, attachments.length - sum(classes.outOfScope));
  assert.equal(coverage.current, sum(classes.indexed));
  // The property. `failed` is the banner; `queued` is work the sitter still owes.
  assert.equal(api.state.failed, sum(classes.failed));
  assert.equal(coverage.current + api.state.failed + sum(classes.queued), coverage.total);
  // And the same reconciliation written out in numbers, so a classification that
  // moved a status from one class to another cannot satisfy it by symmetry.
  assert.equal(coverage.total, 8);
  assert.equal(coverage.current, 2);
  assert.equal(api.state.failed, 5);
  assert.equal(sum(classes.queued), 1);
});
/* Acceptance box 1 on its own, at the smallest size that shows it: `inspect()`
   throwing was mapped to a status outside the admission whitelist, so the
   attachment became no candidate, reached no `ensure()`, and touched no total —
   visible only as one line inside the collapsed diagnostics. */
await test('an attachment whose inspection throws reaches the failure total, not only the diagnostics', async () => {
  const f = fixture();
  f.host.inspect = async id => {
    if (id === 2) throw new Error('attachment unreadable');
    return { status: 'current', identity: String(id) };
  };
  await f.api.sweep();
  assert.equal(f.api.state.counts['inspection-error'], 1);
  assert.equal(f.api.state.failed, 1);
  assert.equal(f.calls.length, 0);
});
/* `state.counts` is rebuilt at the head of every sweep and `state.failed` used to
   be a running total incremented beside it, so the banner grew by one sweep's
   failures every thirty seconds while the library did not change. Suppression by
   identity hid it whenever it held; a source whose identity moves — a re-saved
   PDF, a processor upgrade — is the case where it did not. Derivation from the
   census is what makes the two agree by construction rather than by discipline. */
await test('the failure total is this census, not every census since startup', async () => {
  const f = fixture();
  let generation = 0;
  f.host.ensure = async id => { f.calls.push(id); return false; };
  f.host.inspect = async id => ({ status: 'missing-pack', identity: `${id}/${generation}` });
  for (let sweep = 0; sweep < 3; sweep++) {
    await f.api.sweep();
    assert.equal(f.api.state.failed, 2, `after sweep ${sweep + 1}`);
    assert.equal(f.api.state.counts['failed-session'], 2);
    generation++;
  }
  assert.deepEqual(f.calls, [1, 2, 1, 2, 1, 2]);
});
/* The half of the derivation that only a mid-census observer can see, and the
   reason every other test here is blind to it: they all assert after `sweep()`
   resolves, which is the one moment the numbers are guaranteed whole. The census
   rebuilds `state.counts` from empty and publishes once per attachment — and
   `changed: render`, plus a 100 ms repaint, makes every one of those publishes a
   frame the author can read. Recomputed ungated, the banner would empty at the
   top of each sweep and climb back as the scan ran, every thirty seconds: the
   silence this ticket removed, returning periodically. The reading is sampled
   from inside `inspect()`, i.e. from within the census that has not closed. */
await test('the failure banner holds the last complete census while the next one runs', async () => {
  const f = fixture();
  f.host.list = async () => [1, 2, 3];
  f.host.inspect = async id => {
    if (id === 3) throw new Error('attachment unreadable');
    return { status: 'current', identity: String(id) };
  };
  await f.api.sweep();
  assert.equal(f.api.state.failed, 1);
  const midCensus = [], settled = f.host.inspect;
  f.host.inspect = async id => { midCensus.push(f.api.state.failed); return settled(id); };
  await f.api.sweep();
  // One reading per attachment, taken before that attachment has been counted.
  assert.deepEqual(midCensus, [1, 1, 1]);
  assert.equal(f.api.state.failed, 1);
});
/* Ticket 0718. Holding `failed` alone is not enough: `getSDTCoverage()` used to
   keep reading the live `counts` object after the scheduler reset it, so its
   current and out-of-scope tallies fell to zero and its denominator changed while
   the failure banner still named the preceding generation. Sample from inside
   inspect(), before each attachment joins the new generation, because every
   assertion after sweep() resolves is blind to that recurring window. */
await test('the whole coverage snapshot holds one generation throughout the next census', async () => {
  const statuses = new Map([[1, 'current'], [3, 'missing-pack'],
    [4, 'excluded'], [5, 'unsupported']]);
  let clock = 0;
  const host = {
    list: async () => [1, 2, 3, 4, 5],
    inspect: async id => {
      if (id === 2) throw new Error('attachment unreadable');
      return { status: statuses.get(id), identity: String(id) };
    },
    blocked: async () => 'low-disk', yield: async () => {}, now: () => ++clock,
    changed: () => {}, ensure: async () => { throw new Error('blocked work was admitted'); },
  };
  const api = context.createSDTSitter(host);
  await api.sweep();
  const expected = { known: true, current: 1, failed: 1, queued: 1,
    outOfScope: 2, total: 3, stateFailed: 1, identityHolds: true,
    populationHolds: true };
  assert.deepEqual({ ...ui.getSDTCoverage(api.state) },
    { known: true, current: 1, failed: 1, queued: 1, outOfScope: 2, total: 3 });

  const samples = [], settled = host.inspect;
  host.inspect = async id => {
    const coverage = ui.getSDTCoverage(api.state);
    samples.push({ ...coverage, stateFailed: api.state.failed,
      identityHolds: coverage.current + api.state.failed + coverage.queued === coverage.total,
      populationHolds: coverage.total + coverage.outOfScope === 5 });
    return settled(id);
  };
  await api.sweep();
  assert.equal(samples.length, 5);
  for (const sample of samples) assert.deepEqual(sample, expected);
});
/* A pack `inspect()` has just verified as current IS indexed. What follows is
   disposable cache bookkeeping — a duration written into a store SPEC.md calls
   derived — and letting it throw into the per-candidate catch turned a verified
   success into a failure and, worse, blacklisted the source by identity so no
   later sweep would retry it either. The second sweep is what shows the second
   half; the counters alone would let a fix that only silenced the tally pass. */
await test('a verified pack stays a success when the duration observation throws', async () => {
  const f = fixture(), traced = [];
  f.host.observed = async () => { throw new Error('cache unwritable'); };
  f.host.emit = (kind, detail, level = 'state') => traced.push({ kind, level, ...detail });
  await f.api.sweep();
  assert.equal(f.api.state.completed, 2);
  assert.equal(f.api.state.failed, 0);
  assert.equal(f.api.state.counts.current, 2);
  assert.equal(f.api.state.counts['failed-session'], undefined);
  assert.equal(f.api.state.error, null);
  // Contained is not silent. A cache that has stopped recording durations must
  // not look exactly like one that is working, and the record carries the id
  // only — a platform message names whatever file it failed on.
  const observe = traced.filter(record => record.kind === 'observe-failed');
  assert.deepEqual(observe, [{ kind: 'observe-failed', level: 'trace', id: 1 },
    { kind: 'observe-failed', level: 'trace', id: 2 }]);
  f.cached.clear();
  await f.api.sweep();
  assert.deepEqual(f.calls, [1, 2, 1, 2]);
});
/* Ticket 0696. The end-of-sweep toast, and above all its silence.

   `announceSDTSweep` is driven here with the same snapshot the sweep wrapper
   takes; that the wrapper takes one, and takes it before the await, is asserted
   on the source in tests/test_sdt_sitter.py, because the wrapper closes over
   initialize()'s generation token and its timers and cannot be reached from a
   sandbox load.

   The second arm is the one the ticket exists for. The wrapper reschedules on a
   fixed timer for the life of the plugin, so a caught-up library goes on sweeping
   every thirty seconds all night; a toast fired on the call rather than on the
   work would arrive every thirty seconds with it. The fourth arm is what stops
   that assertion being satisfied by a gate welded shut. */
function recordingProgressWindow(shown) {
  return class {
    constructor() { this.lines = []; this.headline = null; this.closeMS = null; }
    changeHeadline(text) { this.headline = text; }
    addDescription(text) { this.lines.push(text); }
    show() { shown.push(this); }
    startCloseTimer(ms) { this.closeMS = ms; }
  };
}
await test('a sweep announces the work it did, and an idle one announces nothing', async () => {
  const f = fixture(), shown = [];
  ui.journal = context.createSDTJournal(50); ui.sealed = false;
  ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true },
    ProgressWindow: recordingProgressWindow(shown) };
  const announce = async () => {
    const before = { completed: f.api.state.completed, failed: f.api.state.failed };
    await f.api.sweep();
    return ui.announceSDTSweep(before);
  };
  assert.equal(await announce(), true, 'a sweep that indexed two files said nothing');
  assert.equal(shown.length, 1);
  assert.equal(shown[0].headline, 'Indexing assistant');
  assert.deepEqual(shown[0].lines, ['2 files indexed']);
  assert(shown[0].closeMS > 0, 'the toast is never dismissed');
  for (let tick = 0; tick < 5; tick++) {
    assert.equal(await announce(), false, `a caught-up library announced on tick ${tick}`);
  }
  assert.equal(shown.length, 1, 'the caught-up library produced a toast storm');
  // A file added to the library is work, and work is announced again. Without
  // this arm a gate that never opens twice would pass everything above.
  f.host.list = async () => [1, 2, 3];
  assert.equal(await announce(), true, 'a newly added file was indexed in silence');
  assert.deepEqual(shown[1].lines, ['3 files indexed']);
  // And a sitter that has been disabled announces nothing at all: shutdown()
  // clears `alive` while a sweep may still be settling.
  ui.alive = false;
  f.host.list = async () => [1, 2, 3, 4];
  assert.equal(await announce(), false, 'a disabled sitter still toasts');
  assert.equal(shown.length, 2);
  ui.alive = true;
});
await test('a changed failure total is announced, in the words the dialog uses', async () => {
  const f = fixture(), shown = [];
  f.host.ensure = async () => false;          // no pack becomes current
  ui.journal = context.createSDTJournal(50); ui.sealed = false;
  ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true },
    ProgressWindow: recordingProgressWindow(shown) };
  const before = { completed: f.api.state.completed, failed: f.api.state.failed };
  await f.api.sweep();
  // The count the toast shows is the census-derived one of ticket 0699, not a
  // tally accumulated beside it: nothing was indexed, and both files failed.
  assert.equal(f.api.state.failed, 2);
  assert.equal(ui.announceSDTSweep(before), true, 'two failures went unannounced');
  assert.deepEqual(shown[0].lines[1], '2 files could not be indexed');
  // The same two files fail again on the next sweep. Nothing changed, so nothing
  // is said — the failure half of the storm the gate exists to stop.
  const again = { completed: f.api.state.completed, failed: f.api.state.failed };
  await f.api.sweep();
  assert.equal(ui.announceSDTSweep(again), false, 'a repeated failure was re-announced');
  assert.equal(shown.length, 1);
});
await test('a toast that cannot be shown is journalled, not thrown into the sweep loop', async () => {
  const f = fixture();
  const ring = context.createSDTJournal(50);
  ui.journal = ring; ui.sealed = false; ui.alive = true; ui.sitter = f.api;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true },
    ProgressWindow: class { constructor() { throw new Error('no window to attach to'); } } };
  const before = { completed: f.api.state.completed, failed: f.api.state.failed };
  await f.api.sweep();
  assert.equal(f.api.state.completed, 2, 'the arm needs the gate to open to mean anything');
  assert.equal(ui.announceSDTSweep(before), false);
  const records = Array.from(ring.tail(50)).filter(record => record.kind === 'toast-error');
  assert.equal(records.length, 1, 'a toast failed with no record of it');
  assert.equal(records[0].level, 'error');
  // The class alone, as everywhere else in this channel: a platform message
  // names whatever it happens to name.
  assert.equal(records[0].error, 'Error');
});
/* Ticket 0696, review round 1. Two panel seats reproduced the same race, and it
   is a race no assertion in this file could have seen, because nothing here ran
   the sweep loop: the arms above drive announceSDTSweep with a snapshot built by
   hand, and the Python side compares substring positions. Red team demonstrated
   the hole by welding the gate permanently shut — `const before = sitter.state`,
   one object compared with itself — and watching all forty arms stay green.

   So the loop is hoisted out of initialize() and driven here, whole: the real
   snapshot, the real await, the real generation check, the real reschedule.

   THE DEFECT. `sitter` is a module-level binding that initialize() reassigns and
   shutdown() never clears, so `alive` and `sitter` can both be truthy while
   naming a different sitter than the one whose counters filled `before`. The
   plugin's own launch prompt advertises the way in — disabling stops admissions
   but the file in flight finishes — so a disable during an uninterruptible
   ensure() and a prompt re-enable leave this closure suspended while a second
   sitter is installed and `alive` goes back to true. Before the guard, the
   resumed closure diffed one sitter's snapshot against another's counters and
   announced the subtraction: three files indexed, then none.

   The third phase is the control, and the arm is worthless without it: it stages
   the identical suspend-and-resume with no generation change, and requires the
   toast. Without it every assertion here is satisfied by a loop that never
   announces at all — which is exactly the mutation red team used. */
await test('a sweep loop left over from a previous generation announces nothing', async () => {
  const shown = [], scheduled = [];
  ui.journal = context.createSDTJournal(50); ui.sealed = false;
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true },
    ProgressWindow: recordingProgressWindow(shown) };
  ui.timers = { setTimeout: (fn, ms) => scheduled.push({ fn, ms }),
    clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {} };
  // A sitter that has already done work, so its snapshot is not the zeros a
  // freshly built one carries — the two must be distinguishable for the
  // misattribution to have anything to misattribute.
  const suspendMidExtraction = (f, entered, finish) => {
    f.host.list = async () => [1, 2, 3];
    f.host.ensure = async (id, progress) => {
      f.calls.push(id); entered.resolve(); await finish.promise;
      progress(90); f.cached.add(id); return true;
    };
  };
  const stale = fixture();
  await stale.api.sweep();
  assert.equal(stale.api.state.completed, 2, 'the fixture sweep did not run');
  const entered = deferred(), finish = deferred();
  suspendMidExtraction(stale, entered, finish);
  ui.generation = 7; ui.alive = true; ui.sitter = stale.api;
  const running = ui.createSDTSweepLoop(7)();
  await entered.promise;
  // Disable, then re-enable. initialize() installs the new sitter and restores
  // `alive` before its modal confirm, so this needs no click to happen.
  stale.api.stop();
  ui.generation = 8;
  const current = fixture();
  ui.sitter = current.api; ui.alive = true;
  finish.resolve();
  await running;
  assert.equal(shown.length, 0,
    'a stale sweep announced against a sitter it never swept');
  assert.equal(scheduled.length, 0, 'a stale sweep rescheduled itself');
  // The control. Same suspension, same resume, one generation throughout.
  const live = fixture();
  await live.api.sweep();
  const enteredAgain = deferred(), finishAgain = deferred();
  suspendMidExtraction(live, enteredAgain, finishAgain);
  ui.generation = 9; ui.alive = true; ui.sitter = live.api;
  const alive = ui.createSDTSweepLoop(9)();
  await enteredAgain.promise;
  finishAgain.resolve();
  await alive;
  assert.equal(shown.length, 1, 'the loop announces nothing at all');
  // Three, not the two the snapshot held: the copy is a copy. A `before` bound
  // to sitter.state by reference would read this same number twice and never
  // open the gate.
  assert.deepEqual(shown[0].lines, ['3 files indexed']);
  assert.equal(scheduled.length, 1, 'the live loop stopped rescheduling itself');
  assert.equal(scheduled[0].ms, 30000);
  ui.timers = undefined;
});
console.log(JSON.stringify({ tests: results, result: 'pass' }));

const samples = [1, 2, 3].map(n => ({ milliseconds: n * 1000, pages: 10, sourceBytes: 100 }));
assert.equal(context.estimateSDTDuration(samples.slice(0, 2), { pages: 10 }), null);
let prediction = context.estimateSDTDuration(samples, { pages: 20 });
assert.equal(prediction.low, 2200); assert.equal(prediction.median, 4000); assert.equal(prediction.high, 5800);
prediction = context.estimateSDTDuration(samples, { sourceBytes: 200 });
assert.equal(prediction.median, 4000); assert.equal(prediction.basis, 'sourceBytes');
assert.equal(context.estimateSDTDuration(samples, {}), null);

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

/* Ticket 0710: the tooltip also carries the scope the coverage figure is
   measured over, because the button sits in a per-library, per-collection
   toolbar while the census reads the whole database. The library names are
   supplied here, never written into bootstrap.js, so a hardcoded "Ma
   bibliothèque" could not satisfy these assertions. */
const withLibraries = getAll => {
  ui.Zotero = { debug: () => {}, Prefs: { get: () => true }, Libraries: { getAll } };
};
const named = (...names) => withLibraries(() => names.map(name => ({ name })));
// scanned === total, and of the 10 attachments 2 are excluded and 1 unsupported,
// leaving 7 in the denominator, so the composer has a real percentage: 4 of 7.
const tooltipCounts = { current: 4, excluded: 2, unsupported: 1 };
const tooltip = state => ui.describeSDTTooltip({ total: 10, scanned: 10,
  counts: tooltipCounts, censusSnapshot: { counts: tooltipCounts, total: 10 }, ...state });

named('Ma bibliothèque');
const scope = 'Library: Ma bibliothèque — Index 57 % — ';
const idle = tooltip({ phase: 'waiting', completed: 3 });
assert.equal(idle, `${scope}3 files indexed`);
assert.equal(tooltip({ phase: 'ready', completed: 1 }), `${scope}1 file indexed`);
assert.equal(tooltip({ phase: 'census', completed: 2 }),
  `${scope}Census — 2 files indexed`);
// A group library reads as itself. This is the assertion a "My Library" literal
// would fail, and the reason the test supplies the names rather than grepping.
named('Ma bibliothèque', 'Groupe Climat');
assert.equal(tooltip({ phase: 'waiting', completed: 3 }),
  'Libraries: Ma bibliothèque, Groupe Climat — Index 57 % — 3 files indexed');
// A feed is in the library cache getAll() enumerates and holds no attachment, so
// it is outside the set the census measures. Naming it would state a scope the
// figure was never measured over — the failure the prefix exists to end.
withLibraries(() => [{ name: 'Ma bibliothèque' },
  { name: 'Nature News', libraryType: 'feed' }]);
assert.equal(tooltip({ phase: 'waiting', completed: 3 }), idle);
// Past three the enumeration stops informing and the count does.
named('Ma bibliothèque', 'Groupe Climat', 'Groupe Énergie', 'Groupe Transport');
assert.equal(tooltip({ phase: 'waiting', completed: 3 }),
  'All libraries (4) — Index 57 % — 3 files indexed');
// A group library is loaded lazily and its record can throw from the name getter
// after a restart. One unreadable record must cost its own name, not the prefix:
// without the per-record guard the outer guard catches instead and the whole
// prefix goes, leaving the unscoped tooltip below.
withLibraries(() => [{ name: 'Ma bibliothèque' },
  { get name() { throw new Error('library not loaded'); } }]);
assert.equal(tooltip({ phase: 'waiting', completed: 3 }), idle);
const unscoped = 'Index 57 % — 3 files indexed';
// And when nothing at all can be read, the tooltip degrades to the unscoped
// form rather than throwing into the render loop.
withLibraries(() => { throw new Error('libraries unavailable'); });
assert.equal(tooltip({ phase: 'waiting', completed: 3 }), unscoped);
// The iteration is inside the guard too, not only the call: `render` and the
// pulse timer have no try of their own, so a getAll() returning something truthy
// and not iterable would throw ten times a second for the life of the sitter.
withLibraries(() => ({ 0: { name: 'Ma bibliothèque' }, length: 1 }));
assert.equal(tooltip({ phase: 'waiting', completed: 3 }), unscoped);
named('Ma bibliothèque');
// Before the first census there is no percentage. The segment goes rather than
// leaving a bare "Index" between two em dashes; the scope stays, because which
// libraries the sitter is about is true before any figure exists.
assert.equal(ui.describeSDTTooltip({ total: 0, scanned: 0, counts: {},
  phase: 'waiting', completed: 3 }), 'Library: Ma bibliothèque — 3 files indexed');
// getSDTCoverage defaults `counts` rather than dereferencing it: the tooltip
// began reading coverage only with the scope prefix, so this shape reaches the
// render path, where nothing above it catches.
assert.equal(ui.describeSDTTooltip({ total: 0, scanned: 0, phase: 'waiting', completed: 3 }),
  'Library: Ma bibliothèque — 3 files indexed');
// An unlabelled count is reserved for the two healthy idle phases. Mapping any
// other phase to null would silence it exactly as the raw-name removal once did.
const silent = [...phases].filter(phase => !ui.SDT_PHASE_LABELS[phase]).sort();
assert.deepEqual(silent, ['ready', 'waiting'],
  `only healthy idle phases may render an unlabelled count: ${silent.join(' | ')}`);
const stalled = [...phases].filter(phase => !silent.includes(phase) && phase !== 'census');
const rendered = new Set();
// Driven under a HYPHENATED library name on purpose. The identifier check below
// reads a hyphen as the tell of a leaked internal phase name ('low-memory',
// 'cpu-busy'), which it was until library names began flowing into the same
// string; a hyphen is ordinary in a name the user chose. Running this loop under
// "Ma bibliothèque" would leave the check's new scoping unexercised and green by
// accident of the fixture -- which is what it was before this line.
named('Groupe socio-technique');
const hyphenated = 'Library: Groupe socio-technique — Index 57 % — ';
const hyphenatedIdle = tooltip({ phase: 'waiting', completed: 3 });
assert.equal(hyphenatedIdle, `${hyphenated}3 files indexed`);
for (const phase of stalled) {
  const text = tooltip({ phase, completed: 3 });
  assert(text !== hyphenatedIdle, `'${phase}' is indistinguishable from a healthy idle sitter`);
  assert(!text.includes(phase), `'${phase}' leaks its internal name: ${text}`);
  assert(text.endsWith('3 files indexed'), `'${phase}' dropped the count: ${text}`);
  assert(text.startsWith(hyphenated), `'${phase}' dropped the library scope: ${text}`);
  // The hyphen heuristic that used to sit here read `a-b` as the tell of a
  // leaked internal phase name. It worked only while the labels were French:
  // English says "add-on", which matches it and is not an identifier. The
  // assertion above checks the same invariant directly and in any language.
  rendered.add(text);
}
assert.equal(rendered.size, stalled.length, 'two blocking phases share one tooltip');
// An unlisted phase degrades to the scoped count instead of leaking its name.
assert.equal(tooltip({ phase: 'a-brand-new-phase', completed: 3 }), hyphenatedIdle);
named('Ma bibliothèque');
assert.equal(tooltip({ phase: 'waiting', completed: 3 }), idle);

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
  'file no. 7');
assert.equal(ui.describeSDTActiveFile({ active: 7, activeInfo: null }), 'file no. 7');
// The error line names a file through the same composer, so it cannot drift
// back to leading with Zotero's auto-generated attachment title.
assert.equal(ui.describeSDTFile({ parentTitle: 'Sen 1999', title: 'Full Text PDF' }, 'unknown file'),
  'Sen 1999 — Full Text PDF');
assert.equal(ui.describeSDTFile({}, 'unknown file'), 'unknown file');
assert.equal(ui.describeSDTFile(null, 'unknown file'), 'unknown file');

let coverage = ui.getSDTCoverage({ total: 10, scanned: 10, phase: 'waiting',
  counts: { current: 4, excluded: 2, unsupported: 1, 'failed-session': 1, 'missing-source': 2 } });
assert.equal(coverage.current, 4); assert.equal(coverage.total, 7); assert.equal(coverage.known, true);
coverage = ui.getSDTCoverage({ total: 10, scanned: 4, phase: 'census', counts: { current: 4 } });
assert.equal(coverage.known, false);
assert.equal(coverage.current, 0); assert.equal(coverage.total, 0);

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
