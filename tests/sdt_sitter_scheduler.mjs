import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const context = {};
// One read, reused by the phase enumeration below: a second literal copy of this
// path would give verification/probes/sdt_sitter_scheduler_mutants.py two anchors
// where it requires exactly one, and its mutants could no longer be loaded.
const schedulerSource = fs.readFileSync('bench/sdt-sitter/scheduler.js', 'utf8');
vm.runInNewContext(schedulerSource, context);
// The host half of the journal (emit, heartbeat, shutdown) lives in bootstrap.js;
// loading it here lets the ring be driven by the real scheduler rather than by hand.
// Read once for the same reason, and reused by the phase enumeration below.
const ui = {};
const bootstrapSource = fs.readFileSync('bench/sdt-sitter/bootstrap.js', 'utf8');
vm.runInNewContext(bootstrapSource, ui);
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
await test('a document that never reports progress still yields a sample', async () => {
  const f = fixture();
  // An epoch clock, as host.now() really is. It has to be one: a missing start
  // subtracts as zero rather than as NaN, so against a clock counting from zero
  // the absent fallback and the present one agree, and the arm proves nothing.
  let clock = 1_700_000_000_000;
  f.host.now = () => (clock += 10);
  f.host.list = async () => [1];
  f.host.ensure = async id => { f.cached.add(id); return true; };
  await f.api.sweep();
  assert.equal(f.api.state.samples.length, 1);
  const [sample] = f.api.state.samples;
  assert(sample.milliseconds > 0);
  assert(sample.milliseconds < 60000,
    `a silent extraction recorded ${sample.milliseconds} ms — it measured the epoch`);
});
/* Ticket 0701. The census hashed every attachment on every 30 s sweep, because
   the cache key embeds the source MD5 and so the hash had to be taken before the
   cache could be consulted. Counted across two consecutive sweeps of a library
   nothing has touched, and then across a third where one file has changed — the
   third arm is what separates "skips the hash" from "never hashes again". */
await test('an unchanged library is not re-hashed, a changed file still is', async () => {
  const hashes = context.createSDTSourceHashes();
  const stats = { 1: { size: 10, lastModified: 5 }, 2: { size: 20, lastModified: 7 } };
  let hashed = 0;
  const f = fixture();
  f.host.inspect = async id => ({
    status: 'current',
    identity: await hashes.hash(`1/${id}`, `/store/${id}/file.pdf`, stats[id],
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
  await hashes.hash('1/1', '/store/1/other.pdf', stats[1], async () => { hashed++; return 'x'; });
  assert.equal(hashed, 4);
  assert.equal(hashes.size(), 2);
  hashes.prune(new Set(['1/1']));
  assert.equal(hashes.size(), 1, 'a deleted attachment keeps its hash forever');
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
  ui.dialogs.clear();
  const failures = Array.from(ring.tail(50)).filter(record => record.kind === 'render-error');
  // Once, not three times: the pulse renders at 10 Hz, and a beat per tick would
  // evict the whole ring in minutes — losing the evidence 0703 exists to keep.
  assert.equal(failures.length, 1);
  assert.equal(failures[0].level, 'error');
  assert.equal(failures[0].error, 'TypeError');
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
  // sweep-end is absent by the seal, not by omission: the sweep it belongs to
  // finishes on the far side of shutdown, which is where nothing may land.
  assert.deepEqual(tail.map(record => record.kind),
    ['sweep-start', 'admit', 'submit', 'dialog-close', 'shutdown']);
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
// The error line names a file through the same composer, so it cannot drift
// back to leading with Zotero's auto-generated attachment title.
assert.equal(ui.describeSDTFile({ parentTitle: 'Sen 1999', title: 'Full Text PDF' }, 'fichier inconnu'),
  'Sen 1999 — Full Text PDF');
assert.equal(ui.describeSDTFile({}, 'fichier inconnu'), 'fichier inconnu');
assert.equal(ui.describeSDTFile(null, 'fichier inconnu'), 'fichier inconnu');

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
