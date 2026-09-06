/* bootstrap.js's own closure, driven against a real host rather than reasoned about.
 *
 * Ticket 0695. `initialize()` builds `inspect`, `blocked`, `saveCache` and the
 * sweep wrapper inside one closure and hands them to the scheduler, and until
 * this file existed nothing reached any of them: `tests/sdt_sitter_scheduler.mjs`
 * supplies its own host, so it exercises the admission CONTRACT and never the
 * implementations the plugin actually passes. The difference is not academic —
 * `blocked: async () => 'low-disk'` cannot fail the way reading `/proc/meminfo`
 * fails, and a cache the test writes by hand cannot be half-written by a quit.
 *
 * Every scenario here starts from the real `startup()`, over the mock host in
 * `tests/sdt_sitter_zotero_mock.mjs`, and asserts through the two channels the
 * author reads: ticket 0689's journal ring, and the dialog the plugin builds.
 *
 * The mutants probe `verification/probes/sdt_sitter_bootstrap_mutants.py` is the
 * other half of this file: it breaks bootstrap.js one edit at a time and reports
 * which of these tests notice, so "the test is red against a broken
 * implementation" is a fact this repository can re-derive rather than a claim
 * made once in a merge request.
 */
import assert from 'node:assert/strict';

import { CACHE_PATH, ROOT_URI, VERSIONS_JSON, createHarness, deferred }
  from './sdt_sitter_zotero_mock.mjs';

const results = [];
async function test(name, body) { await body(); results.push(name); }

const pdf = (id, key, extra = {}) => ({ id, key, kind: 'pdf', pages: 12, sourceBytes: 4096, ...extra });

/* Wait for a document to reach the extractor, bounded.
 *
 * `await entered.promise` is the obvious way to write this and it is wrong under
 * a probe: a mutant that stops the sitter admitting anything leaves that await
 * unsettled, node exits 13, and the run reads as "the harness crashed" rather
 * than as "this test caught it" -- which is exactly the silence the mutants
 * probe is built to refuse. A bounded wait turns the same defect into a named
 * failure. Discovered by mutant M21, which makes ChromeUtils.now() throw out of
 * the admission gate and so refuses every document. */
async function admitted(harness, entered, label) {
  let arrived = false;
  entered.promise.then(() => { arrived = true; });
  for (let n = 0; n < 60 && !arrived; n++) await harness.turn(1);
  assert(arrived, `${label}: no document ever reached the extractor`);
}

/* --------------------------------------------------------------------------
   The real blocked(): what happens when the readings it is built on are gone.

   Distinct from `resource or native queue blockage admits nothing` in
   tests/sdt_sitter_scheduler.mjs, which fakes `host.blocked` outright: that one
   pins what the SWEEP does with a refusal and can say nothing about how a
   refusal is reached. Everything below — the /proc reads, the storage probe,
   the readings kept beside the verdict — lives in bootstrap.js and had no test.
   -------------------------------------------------------------------------- */
await test('an unreadable resource refuses admission once, records the reason, and keeps the readings it did take', async () => {
  const arms = [
    // `errored` separates the two ways `blocked()` reaches the same verdict, and
    // they are not interchangeable: a read that THREW leaves the author a line
    // saying so, a read that came back unparseable is refused on its own value
    // and leaves the tooltip to carry the phase alone.
    { label: 'the memory reading throws', errored: true,
      options: { meminfo: () => { throw new Error('/proc/meminfo is unreadable'); } },
      reading: admission => assert.equal(admission, null,
        'a reading was recorded before the read that failed') },
    { label: 'the memory reading is unparseable', errored: false,
      options: { meminfo: () => 'SwapTotal: 0 kB\n' },
      reading: admission => assert(Number.isNaN(admission.memoryAvailableBytes),
        'an unparseable reading was published as a number') },
    { label: 'the load average is unparseable', errored: false,
      options: { loadavg: () => 'unavailable' },
      reading: admission => {
        assert.equal(admission.memoryAvailableBytes, 8_000_000 * 1024);
        assert(Number.isNaN(admission.load));
        assert.equal(admission.diskAvailableBytes, undefined,
          'a disk reading was taken after the gate had already refused');
      } },
    { label: 'the storage volume cannot be described', errored: true,
      options: { pathToFileThrows: true },
      reading: admission => {
        assert.equal(admission.memoryAvailableBytes, 8_000_000 * 1024);
        assert.equal(admission.load, 0.42);
        assert.equal(admission.diskAvailableBytes, undefined);
      } },
  ];
  for (const arm of arms) {
    const attachments = [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')];
    const options = { attachments, ...arm.options };
    if (arm.options.pathToFileThrows) {
      delete options.pathToFileThrows;
      options.pathToFile = () => { throw new Error('the volume is gone'); };
    }
    const harness = createHarness(options);
    await harness.start();
    const state = harness.context.sitter.state;

    assert.deepEqual(harness.calls.ensure, [], `${arm.label}: a document was admitted anyway`);
    assert.equal(state.phase, 'resources-unavailable', arm.label);
    // One reading per admission attempt, and the sweep halts on a refusal — so
    // two candidates cost ONE look at /proc, not two and not a poll. A gate that
    // re-read on a timer, or one hoisted out of the candidate loop and retried,
    // both show up here and nowhere else.
    assert.equal(harness.calls.meminfo, 1, `${arm.label}: /proc/meminfo was read ${harness.calls.meminfo} times`);
    const refusals = harness.records('refuse');
    assert.equal(refusals.length, 1, arm.label);
    assert.equal(refusals[0].reason, 'resources-unavailable', arm.label);
    assert.equal(refusals[0].level, 'state', `${arm.label}: a refusal was filed as trace`);
    if (arm.errored) assert(state.error.startsWith('Lecture des ressources'), `${arm.label}: ${state.error}`);
    else assert.equal(state.error, null, `${arm.label}: ${state.error}`);
    arm.reading(harness.context.admission);
    // The panel says how long ago the reading was taken; with the whole read
    // thrown there is nothing to say, and it says that rather than printing zeros.
    assert.equal(harness.context.describeSDTAdmission().startsWith('Aucune mesure'),
      harness.context.admission === null, arm.label);
  }
});

await test('the sitter recovers on the next sweep once the readings come back', async () => {
  let readable = false;
  const harness = createHarness({
    attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')],
    meminfo: () => {
      if (!readable) throw new Error('/proc/meminfo is unreadable');
      return 'MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\n';
    },
  });
  await harness.start();
  assert.equal(harness.context.sitter.state.phase, 'resources-unavailable');
  // A halted sweep still has work waiting, so the sitter looks again in 30 s
  // rather than backing off to the idle cadence — and this fires that timer
  // through bootstrap.js's own wrapper, which is where the reschedule lives.
  readable = true;
  await harness.nextSweep();
  assert.deepEqual(harness.calls.ensure, [1, 2]);
  assert.equal(harness.context.sitter.state.phase, 'waiting');
  assert.equal(harness.context.sitter.state.completed, 2);
});

/* --------------------------------------------------------------------------
   The cache file, as the next session finds it.
   -------------------------------------------------------------------------- */
await test('a corrupt cache row is dropped and its attachment re-inspected natively', async () => {
  // Four attachments, all with a pack on disk, so every one of them comes out
  // `current` and the ONLY difference between them is what the cache file says.
  // That isolates the loader: a status moving here would be about the pack.
  const attachments = [pdf(1, 'AAAA1111', { pack: { lastModified: 900 } }),
    pdf(2, 'BBBB2222', { pack: { lastModified: 900 } }),
    pdf(3, 'CCCC3333', { pack: { lastModified: 900 } }),
    pdf(4, 'DDDD4444', { pack: { lastModified: 900 } })];
  const shape = createHarness({ attachments });
  const record = key => ({ signature: shape.identity(key), fingerprint: shape.fingerprint(key),
    sourceBytes: 4096, pages: 12 });
  const good = { ...record('AAAA1111'), sample: { milliseconds: 12000, sourceBytes: 4096, pages: 12 } };
  // Kept, but its duration is not: a zero-millisecond observation is not a
  // measurement, and the store must not fit an estimate on it.
  const unusable = { ...record('CCCC3333'), sample: { milliseconds: 0, sourceBytes: 4096, pages: 12 } };
  const truncated = shape.cacheLine('BBBB2222', record('BBBB2222')).slice(0, -18);
  const wrongVersions = JSON.stringify({ versions: '{"SDT_PACK_VERSION":"0"}',
    key: '1/DDDD4444', record: record('DDDD4444') });
  // The truncated row sits in the MIDDLE, not at the end: a loader that stopped
  // at the first bad line instead of skipping it would lose the two below.
  const cache = [shape.cacheLine('AAAA1111', good), truncated, wrongVersions,
    shape.cacheLine('CCCC3333', unusable), ''].join('\n');

  const harness = createHarness({ attachments, cache });
  await harness.start();
  const state = harness.context.sitter.state;

  assert.equal(state.counts.current, 4, 'a malformed cache row changed a verdict');
  // Two rows survived the load; the truncated one and the one stamped with
  // another pack version did not.
  assert.equal(harness.records('cache-load')[0].records, 2);
  // Falling back to native inspection is what "dropped" MEANS here, and it is
  // observable as the packs actually opened: A and C were answered from the
  // cache, B and D were re-read from disk.
  assert.deepEqual(harness.calls.openPack, ['BBBB2222', 'DDDD4444']);
  // The usable-observation count, not an invented "rows dropped" counter: of
  // the two rows that loaded, only one carried a duration worth fitting on.
  assert.equal(state.samples.length, 1);
  assert.equal(state.samples[0].milliseconds, 12000);
});

await test('a quit halfway through a cache append leaves a partial line the next session drops', async () => {
  let writes = 0;
  const first = createHarness({
    attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')],
    // The process dies during the LAST append of the session. The compact write
    // that opens an activation goes through a temporary file and is atomic by
    // construction, so a scenario that killed the first write would be asserting
    // about a path that cannot tear (ticket 0695).
    write: (_path, text) => {
      writes++;
      return writes === 3
        ? { persist: text.slice(0, -18), fail: new Error('the process is gone') } : {};
    },
  });
  await first.start();
  const persisted = first.files.text(CACHE_PATH);

  // The positive control, and it comes first: without it the assertions below
  // pass whether or not a partial line was ever written.
  const lines = persisted.split('\n').filter(Boolean);
  assert.throws(() => JSON.parse(lines[lines.length - 1]),
    'nothing partial reached the file, so the next session has nothing to drop');
  assert.doesNotThrow(() => JSON.parse(lines[lines.length - 2]),
    'the whole write was lost, not just its tail');

  // Which of the two acceptable outcomes this implementation has: a partial line
  // IS persisted, and IS dropped when the file is next read. Recorded here
  // rather than left to the reader, since the ticket allowed either.
  const second = createHarness({
    attachments: [pdf(1, 'AAAA1111', { pack: { lastModified: 950 } }),
      pdf(2, 'BBBB2222', { pack: { lastModified: 950 } })],
    cache: persisted,
  });
  await second.start();
  assert.equal(second.records('cache-load')[0].records, 1);
  assert.equal(second.context.sitter.state.counts.current, 2, 'a partial line cost an attachment');
  assert.deepEqual(second.calls.openPack, ['BBBB2222'],
    'the row that survived the quit was not believed');
  assert.equal(second.context.sitter.state.samples.length, 1);
});

await test('an unwritable data directory is journalled once per episode, and the estimates survive it', async () => {
  const attachments = [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')];
  const unwritable = createHarness({
    attachments,
    write: () => { throw new Error('read-only file system'); },
  });
  await unwritable.start();
  const state = unwritable.context.sitter.state;

  // Three writes were attempted in that sweep — one closing the census and one
  // per settled duration — and the ring holds one record for the episode. A
  // record per attempt would evict the ring on a library of any size, which is
  // the same reasoning render()'s latch carries.
  assert.equal(unwritable.calls.writes.length, 3);
  const errors = unwritable.records('cache-error');
  assert.equal(errors.length, 1);
  assert.equal(errors[0].level, 'error');
  // The class travels and the message does not: a platform write error names
  // the path it failed on.
  assert.equal(errors[0].error, 'Error');
  assert(!JSON.stringify(errors).includes('read-only'));
  assert(state.cacheWarning.startsWith('Cache non enregistré'));

  // And the session is not degraded by it. The durations were recorded in the
  // in-memory cache, so the next census still hands the estimator its samples —
  // the cache file is derived and disposable, and this is what that means.
  assert.equal(state.samples.length, 2);
  await unwritable.nextSweep();
  assert.equal(unwritable.context.sitter.state.samples.length, 2,
    'a failed write cost the session its observations');

  // The latch releases, so a second, later episode is still reported. Without
  // this arm an implementation that simply never records twice passes above.
  let attempt = 0;
  const intermittent = createHarness({
    attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')],
    write: () => { attempt++; if (attempt === 2) return {}; throw new Error('read-only file system'); },
  });
  await intermittent.start();
  assert.equal(intermittent.calls.writes.length, 3);
  assert.equal(intermittent.records('cache-error').length, 2);
  assert.equal(intermittent.records('cache-write').length, 1);
});

/* --------------------------------------------------------------------------
   The dialog, and the two windows the plugin can be started into.
   -------------------------------------------------------------------------- */
await test('a dialog closed and reopened mid-job is one instance, one listener, and the same state', async () => {
  const entered = deferred(), finish = deferred();
  const harness = createHarness({
    attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')],
    ensure: async (id, onProgress) => {
      onProgress(40);
      entered.resolve();
      await finish.promise;
      harness.persistPack(id);
      onProgress(100);
      return true;
    },
  });
  await harness.startHanging();
  await admitted(harness, entered, 'the reopened dialog');

  const window = harness.windows[0];
  harness.context.openDialog(window);
  await harness.turn();
  const first = window.dialogs[0];
  assert.equal(window.dialogs.length, 1);
  assert.equal(harness.context.dialogs.size, 1);
  assert.equal(first.listeners.get('unload').length, 1);
  const active = first.document.getElementById('sdt-document-status').textContent;
  assert(active.includes('Sen 1999 — Full Text PDF'), active);
  assert(active.includes('40 %'), active);
  const counts = first.document.getElementById('sdt-diagnostics').textContent;

  // Asked again while it is open, the plugin raises the window it has. A second
  // instance is the visible defect; a second `unload` listener is the invisible
  // one, and it is what leaves a dead dialog being redrawn at 10 Hz.
  harness.context.openDialog(window);
  assert.equal(window.dialogs.length, 1, 'a second dialog was opened over the first');
  assert.equal(first.focused, 1);
  assert.equal(first.listeners.get('unload').length, 1, 'the reused dialog gained a listener');
  assert.deepEqual(harness.records('dialog-open').map(record => record.reused), [false, true]);

  // Closed the way the platform closes it: the window goes, then unload fires.
  first.closed = true;
  first.fire('unload');
  assert.equal(harness.context.dialogs.size, 0);
  assert.equal(harness.records('dialog-close').length, 1);

  harness.context.openDialog(window);
  await harness.turn();
  assert.equal(window.dialogs.length, 2);
  const second = window.dialogs[1];
  assert.equal(harness.context.dialogs.size, 1, 'the closed dialog is still being rendered into');
  assert.equal(second.listeners.get('unload').length, 1);
  // The state is the sitter's, not the window's, so the cycle costs nothing:
  // the same job, the same progress, the same census.
  assert.equal(second.document.getElementById('sdt-document-status').textContent, active);
  assert.equal(second.document.getElementById('sdt-diagnostics').textContent, counts);

  finish.resolve();
  await harness.quiet();
  assert.equal(harness.context.sitter.state.completed, 2);
  // A closed dialog is dropped from the render set rather than accumulating.
  assert.equal(harness.context.dialogs.size, 1);
});

await test('two windows and two startups leave one sitter, one launch prompt and two toolbars', async () => {
  const harness = createHarness({ attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')], windows: 2 });
  // Zotero serializes add-on startup, but a second main window opening while
  // the first initialize() is still on `uiReadyPromise` puts two of them in
  // flight. The generation token is what makes the second win and the first
  // stand down; everything below is what "stand down" has to mean.
  harness.context.startup({ rootURI: ROOT_URI });
  harness.context.startup({ rootURI: ROOT_URI });
  await harness.quiet();

  // The self-check is emitted before the guard, deliberately: a startup that
  // never got as far as the guard is exactly what it exists to record. So two
  // reach the debug log, and only one of them goes on to build anything.
  assert.equal(harness.debugged.filter(line => line.startsWith('SDT sitter startup ')).length, 2);
  assert.equal(harness.records('cache-load').length, 1, 'the cache was loaded twice');
  assert.equal(harness.calls.prompt, 1, 'the author was asked to launch twice');

  assert.equal(harness.Zotero.SDTPackSitter.state, harness.context.sitter.state);
  assert.deepEqual(harness.calls.ensure, [1, 2], 'a document was submitted more than once');
  assert.equal(harness.records('admit').length, 2);
  assert.equal(harness.context.sitter.state.completed, 2);

  // Both toolbars carry a button, and both were rendered into — the button is
  // added per window and the render loop walks the whole set.
  assert.equal(harness.context.buttons.size, 2);
  for (const window of harness.windows) {
    const button = window.document.getElementById('sdt-pack-sitter-button');
    assert(button, 'a main window has no toolbar button');
    assert.equal(button.parentNode, window.toolbar);
    assert.equal(button.getAttribute('label'), 'Index 100 %');
    assert(button.getAttribute('tooltiptext').includes('2 fichiers indexés'));
  }
});

/* --------------------------------------------------------------------------
   The two clocks.
   -------------------------------------------------------------------------- */
await test('a document past its empirical upper bound withdraws the finish time, not the estimate', async () => {
  // Three attachments already indexed with a recorded duration, so the estimator
  // has the three observations it requires, and a fourth to work on. Identical
  // samples make the 5th and 95th percentiles equal, so the bound is exact and
  // the arms below sit on either side of one number rather than near it.
  const attachments = [pdf(1, 'AAAA1111', { pack: { lastModified: 900 } }),
    pdf(2, 'BBBB2222', { pack: { lastModified: 900 } }),
    pdf(3, 'CCCC3333', { pack: { lastModified: 900 } }),
    pdf(4, 'DDDD4444')];
  const shape = createHarness({ attachments });
  const cached = key => shape.cacheLine(key, {
    signature: shape.identity(key), fingerprint: shape.fingerprint(key),
    sourceBytes: 4096, pages: 12,
    sample: { milliseconds: 720_000, sourceBytes: 4096, pages: 12 },
  });

  const entered = deferred(), finish = deferred();
  const harness = createHarness({
    attachments,
    cache: `${['AAAA1111', 'BBBB2222', 'CCCC3333'].map(cached).join('\n')}\n`,
    ensure: async (_id, onProgress) => { onProgress(20); entered.resolve(); await finish.promise; return false; },
  });
  await harness.startHanging();
  await admitted(harness, entered, 'the empirical upper bound');
  const state = harness.context.sitter.state;
  assert.equal(state.fittedSamples.length, 3, 'the estimator was not given its three observations');
  assert.equal(state.active, 4);

  harness.context.openDialog(harness.windows[0]);
  await harness.turn();
  const doc = harness.windows[0].dialogs[0].document;
  const perDocument = doc.getElementById('sdt-document-estimate').textContent;
  assert.equal(perDocument, 'Durée estimée : 12 min 00 s (entre 12 min 00 s et 12 min 00 s)');

  // Inside the bound: the window says when the library should be done.
  harness.advance(1000);
  harness.context.render();
  assert(doc.getElementById('sdt-global-estimate').textContent.startsWith('Fin estimée vers '),
    doc.getElementById('sdt-global-estimate').textContent);

  // Past it, the projection is withdrawn. The fallback is the empty string —
  // no line at all — and not a sentence saying so; asserted against the code
  // rather than against any wording a ticket once proposed.
  harness.advance(720_000);
  harness.context.render();
  assert.equal(doc.getElementById('sdt-global-estimate').textContent, '');
  // Only the projection goes. The per-document estimate is still the honest
  // reading of three observations, and the elapsed line still runs.
  assert.equal(doc.getElementById('sdt-document-estimate').textContent, perDocument);
  assert(doc.getElementById('sdt-document-status').textContent.includes('12 min 01 s écoulées'),
    doc.getElementById('sdt-document-status').textContent);

  finish.resolve();
  await harness.quiet();
});

await test('a wall clock stepped backwards mid-job never produces a negative duration', async () => {
  const entered = deferred(), finish = deferred();
  const fixture = () => ({
    attachments: [pdf(1, 'AAAA1111')],
    ensure: async (_id, onProgress) => { onProgress(30); entered.resolve(); await finish.promise; return false; },
  });

  const harness = createHarness(fixture());
  await harness.startHanging();
  await admitted(harness, entered, 'the backwards clock step');
  harness.context.openDialog(harness.windows[0]);
  await harness.turn();
  const doc = harness.windows[0].dialogs[0].document;
  assert(doc.getElementById('sdt-document-status').textContent.includes('0 s écoulées'));

  // Five seconds of work, during which the author's clock is corrected an hour
  // backwards. Three implementations are distinguishable here and only one is
  // right: the wall clock reads -3595 s, a wall clock ratcheted to its own
  // high-water mark freezes at 0 s, and the monotonic source says 5 s.
  harness.clock.mono += 5000;
  harness.clock.wall -= 60 * 60 * 1000;
  harness.context.render();
  assert(doc.getElementById('sdt-document-status').textContent.includes('5 s écoulées'),
    doc.getElementById('sdt-document-status').textContent);

  harness.context.heartbeatTick();
  const beat = harness.records('heartbeat').at(-1);
  assert.equal(beat.elapsedMS, 5000);
  assert.equal(beat.sinceProgressMS, 5000);

  // The record's own timestamp is NOT monotonic and must not be: it is a point
  // on the calendar, which the ring renders as a time of day.
  assert.equal(beat.at, harness.clock.wall);

  finish.resolve();
  await harness.quiet();
});

/* The clock has three tiers and the test above exercises the first and the
   last. The middle one is not decoration: `ChromeUtils` is Gecko-specific, and
   the guards around each tier are exactly the code that decides which one
   answers — a `Number.isFinite` check dropped, or a `catch` removed, changes
   which clock the sitter runs on and nothing else moves. Each arm below fixes
   one host shape and asserts the reading that shape must produce. */
await test('the clock falls through its tiers: ChromeUtils, then performance, then the wall clock', async () => {
  const arms = [
    // The web API is present and runs at double rate, so this arm fails if the
    // two tiers are consulted in the other order — a constant offset would not
    // have discriminated them, since a span cancels it.
    { label: 'ChromeUtils.now answers', reading: '5 s',
      host: (context, clock) => { context.performance = { now: () => clock.mono * 2 }; } },
    // A host with no ChromeUtils.now at all: the web API is the same clock, and
    // it is the only source left before the fallback.
    { label: 'performance.now answers', reading: '5 s',
      host: (context, clock) => {
        delete context.ChromeUtils.now;
        context.performance = { now: () => clock.mono };
      } },
    // A reading that is not a number is not a clock. The tier is skipped rather
    // than believed, which is the difference between 5 s and NaN on screen.
    { label: 'ChromeUtils.now returns something that is not a reading', reading: '5 s',
      host: (context, clock) => {
        context.ChromeUtils.now = () => 'soon';
        context.performance = { now: () => clock.mono };
      } },
    // And a source that THROWS is not the same as one that is absent: a
    // torn-down compartment can throw from a call this file makes ten times a
    // second, and the guard is what keeps that out of the render loop.
    { label: 'ChromeUtils.now throws', reading: '5 s',
      host: (context, clock) => {
        context.ChromeUtils.now = () => { throw new Error('the compartment is gone'); };
        context.performance = { now: () => clock.mono };
      } },
    { label: 'no monotonic source at all', reading: '0 s',
      host: context => { delete context.ChromeUtils.now; } },
  ];
  for (const arm of arms) {
    const entered = deferred(), finish = deferred();
    const harness = createHarness({
      attachments: [pdf(1, 'AAAA1111')],
      ensure: async (_id, onProgress) => { onProgress(30); entered.resolve(); await finish.promise; return false; },
    });
    arm.host(harness.context, harness.clock);
    await harness.startHanging();
    await admitted(harness, entered, arm.label);
    harness.context.openDialog(harness.windows[0]);
    await harness.turn();
    const doc = harness.windows[0].dialogs[0].document;

    // Five seconds of work across an hour-long backwards correction. Every arm
    // but the last has a monotonic source and must read 5 s; the last has none
    // and must read 0 s rather than a negative.
    harness.clock.mono += 5000;
    harness.clock.wall -= 60 * 60 * 1000;
    harness.context.render();
    assert(doc.getElementById('sdt-document-status').textContent.includes(`${arm.reading} écoulées`),
      `${arm.label}: ${doc.getElementById('sdt-document-status').textContent}`);
    finish.resolve();
    await harness.quiet();
  }
});

await test('with no platform monotonic clock the wall clock is ratcheted, never read backwards', async () => {
  const entered = deferred(), finish = deferred();
  const harness = createHarness({
    attachments: [pdf(1, 'AAAA1111')],
    ensure: async (_id, onProgress) => { onProgress(30); entered.resolve(); await finish.promise; return false; },
  });
  // A host with neither ChromeUtils.now() nor performance.now(). Removed before
  // startup, so the whole session runs on the fallback rather than crossing
  // between two clocks with different origins.
  delete harness.context.ChromeUtils.now;
  assert.equal(typeof harness.context.performance, 'undefined',
    'the sandbox has a second monotonic source, so this arm proves nothing');

  await harness.startHanging();
  await admitted(harness, entered, 'the ratcheted fallback');
  harness.context.openDialog(harness.windows[0]);
  await harness.turn();
  const doc = harness.windows[0].dialogs[0].document;

  harness.clock.wall -= 60 * 60 * 1000;
  harness.context.render();
  // It cannot say how long the step lasted — nothing without a monotonic clock
  // can — but it refuses to answer a negative duration, which is the failure
  // the fallback exists to stop.
  assert(doc.getElementById('sdt-document-status').textContent.includes('0 s écoulées'),
    doc.getElementById('sdt-document-status').textContent);
  harness.context.heartbeatTick();
  assert.equal(harness.records('heartbeat').at(-1).elapsedMS, 0);

  // And it is a ratchet, not a freeze: the clock catching back up resumes.
  harness.clock.wall += 60 * 60 * 1000 + 7000;
  harness.context.render();
  assert(doc.getElementById('sdt-document-status').textContent.includes('7 s écoulées'),
    doc.getElementById('sdt-document-status').textContent);

  finish.resolve();
  await harness.quiet();
});

/* The two spans a reader never sees as a stopwatch, and so the two most likely
   to drift back to the calendar. Both are asserted through a divergence between
   the clocks rather than through a value, which is the only way to tell them
   apart at all. */
await test('the memoized source hash is re-verified on running time, not on the calendar', async () => {
  const attachments = [pdf(1, 'AAAA1111', { pack: { lastModified: 900 } }),
    pdf(2, 'BBBB2222', { pack: { lastModified: 900 } })];
  const harness = createHarness({ attachments });
  await harness.start();
  assert.deepEqual(harness.calls.hash, ['AAAA1111', 'BBBB2222'],
    'the census did not hash the library it had never seen');
  await harness.nextSweep();
  assert.equal(harness.calls.hash.length, 2, 'an untouched library was re-hashed on the next sweep');

  // The author corrects his clock 25 hours backwards. On the calendar the
  // memoized entry's age goes negative, falls outside [0, 24 h), and every
  // attachment in the library is re-read and re-hashed; on the running clock
  // nothing has aged at all. Ticket 0701's whole point was to stop that pass.
  harness.clock.wall -= 25 * 60 * 60 * 1000;
  await harness.nextSweep();
  assert.equal(harness.calls.hash.length, 2, 'a clock correction cost a full-library re-hash');

  // And it is still a bound: 24 hours of running time expires it, which is what
  // ticket 0701's ruling bought and what this must not quietly undo.
  harness.clock.mono += 24 * 60 * 60 * 1000;
  await harness.nextSweep();
  assert.deepEqual(harness.calls.hash,
    ['AAAA1111', 'BBBB2222', 'AAAA1111', 'BBBB2222']);
});

await test('the admission panel ages its reading on running time too', async () => {
  const harness = createHarness({ attachments: [pdf(1, 'AAAA1111')] });
  await harness.start();
  assert(harness.context.admission, 'no reading was taken, so the age says nothing');
  // One second, which is what the extractor's own clock step cost between the
  // reading and now.
  assert(harness.context.describeSDTAdmission().startsWith('Dernière mesure il y a 1 s '),
    harness.context.describeSDTAdmission());
  harness.clock.mono += 120_000;
  harness.clock.wall -= 60 * 60 * 1000;
  assert(harness.context.describeSDTAdmission().startsWith('Dernière mesure il y a 2 min '),
    harness.context.describeSDTAdmission());
});

/* One arm nothing above would notice: the manifest and the pack metadata are
   read from `rootURI` and from Zotero's own resource URL, and the identity every
   cache row is keyed on embeds the second. A version bump that did not reach the
   identity would silently keep every stale pack. */
await test('the pack versions reach the cache identity, so a bump invalidates the whole store', async () => {
  const attachments = [pdf(1, 'AAAA1111', { pack: { lastModified: 900 } })];
  const shape = createHarness({ attachments });
  assert(shape.identity('AAAA1111').endsWith(VERSIONS_JSON),
    'the pack versions are not part of the cache identity');
  const harness = createHarness({
    attachments,
    cache: `${shape.cacheLine('AAAA1111', { signature: 'from-an-older-format',
      fingerprint: shape.fingerprint('AAAA1111'), sourceBytes: 4096, pages: 12,
      sample: { milliseconds: 12000, sourceBytes: 4096, pages: 12 } })}\n`,
  });
  await harness.start();
  // The row loads — it is well formed — and is then refused by `check`, which
  // is the difference between a corrupt row and a stale one.
  assert.equal(harness.records('cache-load')[0].records, 1);
  assert.deepEqual(harness.calls.openPack, ['AAAA1111']);
  assert.equal(harness.context.sitter.state.samples.length, 0,
    'a duration measured under another pack version was kept');
});

console.log(JSON.stringify({ tests: results, result: 'pass' }));
