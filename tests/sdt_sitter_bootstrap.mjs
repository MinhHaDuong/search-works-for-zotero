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
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';

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
    if (arm.errored) assert(state.error.startsWith('Reading resources'), `${arm.label}: ${state.error}`);
    else assert.equal(state.error, null, `${arm.label}: ${state.error}`);
    arm.reading(harness.context.admission);
    // The panel says how long ago the reading was taken; with the whole read
    // thrown there is nothing to say, and it says that rather than printing zeros.
    assert.equal(harness.context.describeSDTAdmission().startsWith('No resource reading'),
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
  // A resource refusal backs off to the idle cadence (not the 30 s active one)
  // -- this fires that timer through bootstrap.js's own wrapper, which is where
  // the reschedule lives, regardless of which cadence it armed.
  readable = true;
  await harness.nextSweep();
  assert.deepEqual(harness.calls.ensure, [1, 2]);
  assert.equal(harness.context.sitter.state.phase, 'waiting');
  assert.equal(harness.context.sitter.state.completed, 2);
});

await test('a resource refusal backs off to the idle cadence, not the active one', async () => {
  // Found live, never ticketed: two full censuses eight minutes apart, both
  // correctly refused cpu-busy, neither one backed off -- the sitter was
  // busiest exactly when it had just decided the machine was too busy.
  const harness = createHarness({
    attachments: [pdf(1, 'AAAA1111')],
    loadavg: () => '99.00 99.00 99.00 1/200 12345',
  });
  await harness.start();
  assert.equal(harness.context.sitter.state.phase, 'cpu-busy');
  const [id] = harness.timers.ids('timeout');
  assert.equal(harness.timers.pending.get(id).ms, 10 * 60 * 1000,
    'a refused sweep rescheduled on the 30 s active cadence instead of backing off');
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
  assert(state.cacheWarning.startsWith('Cache not saved'));

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
   What the sitter refuses to hand the extractor, and what it remembers refusing.

   Ticket 0740. Both halves are about the same 39 documents on the author's
   library: submitted every session, failing in 50-90 ms every session, counted
   as failures every session, and unable to succeed in any of them.

   Both scenarios below hold a MIXED population on purpose. A fixture made only
   of the failing documents cannot tell a fix that stops submitting them from
   one that has stopped submitting anything, and stopping the sitter altogether
   would pass every assertion an all-failures fixture can carry. So each
   scenario asserts the whole census: which documents were handed to the
   extractor, which were not, and that the classes still sum to what was
   scanned.
   -------------------------------------------------------------------------- */
const JPEG = [0xFF, 0xD8, 0xFF, 0xE0];
const PNG = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
const ZIP = [0x50, 0x4B, 0x03, 0x04];
const PDF_MAGIC = [0x25, 0x50, 0x44, 0x46];
// '<!DOCTYPE ' — a real snapshot's opening bytes, which name no format at all.
const DOCTYPE = [0x3C, 0x21, 0x44, 0x4F, 0x43, 0x54, 0x59, 0x50, 0x45];

await test('a file whose bytes contradict its declared type is classified, not submitted', async () => {
  const harness = createHarness({
    attachments: [
      // The eleven page scans of the live journal, in one row: Zotero holds it
      // with `attachmentContentType == 'text/html'` — nothing else could have
      // satisfied `isSnapshotAttachment()` — and the file is a JPEG.
      { id: 1, key: 'AAAA1111', kind: 'snapshot', pages: null, sourceBytes: 4096, magic: JPEG },
      // The genuine snapshot beside it. Ticket 0740 keeps this case explicitly
      // out of the image story, and here it is what proves the fix did not
      // simply stop admitting snapshots.
      { id: 2, key: 'BBBB2222', kind: 'snapshot', pages: null, sourceBytes: 4096, magic: DOCTYPE },
      { id: 3, key: 'CCCC3333', kind: 'pdf', pages: 12, sourceBytes: 4096, magic: PDF_MAGIC },
      // No signature at all. HTML has none either, so an unrecognised head must
      // leave the label standing — the arm that fails if the check is inverted
      // into "admit only what the table recognises".
      { id: 4, key: 'DDDD4444', kind: 'pdf', pages: 12, sourceBytes: 4096 },
      { id: 5, key: 'EEEE5555', kind: 'epub', pages: null, sourceBytes: 4096, magic: ZIP },
      // The mismatch in the other direction: a known format that a REAL
      // processor handles, declared as a different one. Without this arm an
      // implementation that only ever looks for images passes.
      { id: 6, key: 'FFFF6666', kind: 'pdf', pages: 12, sourceBytes: 4096, magic: PNG },
    ],
  });
  await harness.start();
  const state = harness.context.sitter.state;

  // The whole population, in one assertion: four documents reached the
  // extractor and two did not. `deepEqual` rather than a membership test — a
  // fix that stopped submitting the two mislabelled files by submitting nothing
  // is the failure this scenario exists to catch.
  assert.deepEqual(harness.calls.ensure, [2, 3, 4, 5],
    'the extractor was handed the wrong set of documents');
  assert.deepEqual(harness.records('submit').map(record => record.id), [2, 3, 4, 5],
    'a document was submitted that the census had already ruled out');

  assert.equal(state.counts.unsupported, 2, 'a byte/label mismatch was not classified');
  assert.equal(state.counts.current, 4, 'a document that extracts fine stopped being admitted');
  assert.equal(state.failed, 0, 'a mismatch was counted as a failure rather than classified');
  // The census still adds up, which is the property the whole status vocabulary
  // exists to hold (ticket 0699): every attachment landed in exactly one class.
  const classes = harness.context.SDT_STATUS_CLASSES;
  const tally = keys => keys.reduce((n, key) => n + (state.counts[key] || 0), 0);
  assert.equal(Object.values(classes).reduce((n, keys) => n + tally(keys), 0), state.scanned);
});

await test('a document that yields no pack is asked once a session, and again after a restart', async () => {
  const attachments = [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222'), pdf(3, 'CCCC3333')];
  const hooks = {};
  const first = createHarness({ attachments, ensure: (id, onProgress) => hooks.ensure(id, onProgress) });
  // Native SDT's own behaviour on the failing documents: it returns, promptly
  // and without complaint, having persisted nothing. The plugin's `Native SDT
  // did not persist a current pack` is its own sentence about that silence.
  hooks.ensure = async (id, onProgress) => {
    onProgress(10);
    first.advance(1000);
    if (id !== 2) first.persistPack(id);
    onProgress(100);
    return true;
  };
  await first.start();

  // The positive control for everything below: the later assertions say nothing
  // unless this sweep really did admit the document and really did fail on it.
  assert.deepEqual(first.calls.ensure, [1, 2, 3], 'the failing document was never admitted at all');
  assert.equal(first.context.sitter.state.counts['failed-session'], 1);
  assert.equal(first.context.sitter.state.counts.current, 2);

  // The second sweep of the SAME session, through the timer the sitter armed for
  // itself. Nothing new was written to disk and nothing needs to have been: the
  // failure is held in memory for the life of the activation, which is the span
  // the author ruled for on 2026-09-08.
  await first.nextSweep();
  const held = first.context.sitter.state;
  // `deepEqual` on the whole call list, not a count of new calls: a sitter that
  // stopped sweeping altogether also never resubmits anything, and that outcome
  // must not pass. The two documents that carry packs are `current` and were
  // never candidates, so a correct second sweep calls `ensure` for nobody.
  assert.deepEqual(first.calls.ensure, [1, 2, 3],
    'the failure was resubmitted inside the session that had just recorded it');
  assert.equal(held.counts['failed-session'], 1);
  assert.equal(held.counts.current, 2, 'a document that can be indexed stopped being admitted');
  // Still a failure the author is told about. A suppression that dropped out of
  // the "could not be indexed" figure would trade a repeated submission for a
  // silently shrinking count.
  assert.equal(held.failed, 1);
  // The census still adds up, which is the property the whole status vocabulary
  // exists to hold (ticket 0699): every attachment landed in exactly one class.
  const heldClasses = first.context.SDT_STATUS_CLASSES;
  const heldTally = keys => keys.reduce((n, key) => n + (held.counts[key] || 0), 0);
  assert.equal(Object.values(heldClasses).reduce((n, keys) => n + heldTally(keys), 0), held.scanned);

  // Nothing about the failure reached the cache file. Asserted on the bytes
  // rather than on behaviour, because the behaviour below would look identical
  // if a refusal were written and then ignored — and a row nobody reads is
  // exactly the orphaned disk state the author's ruling forbids.
  assert.equal((first.files.text(CACHE_PATH) || '').includes('refused'), false,
    'a failure verdict was written to the disposable cache');
  const persisted = first.files.text(CACHE_PATH);

  // A new session over the same cache file — the plugin restarted, or Zotero
  // did. The suppression is gone with the memory that held it, and the document
  // is asked again. This is the accepted cost of the 2026-09-08 ruling, not an
  // oversight: it is also what native SDT's own service does with a generic
  // failure, which it retries on every new call
  // (verification/SDT-PLUGIN-PREREQUISITES.md).
  const second = createHarness({
    attachments: [pdf(1, 'AAAA1111', { pack: { lastModified: 950 } }), pdf(2, 'BBBB2222'),
      pdf(3, 'CCCC3333', { pack: { lastModified: 950 } })],
    cache: persisted,
    // Native answers the same way it did last session, so the retry costs a real
    // failure rather than quietly succeeding: the assertions below are about a
    // document that is still unextractable, not about one that got better.
    ensure: (id, onProgress) => hooks.ensure(id, onProgress),
  });
  hooks.ensure = async (id, onProgress) => {
    onProgress(10);
    second.advance(1000);
    if (id !== 2) second.persistPack(id);
    onProgress(100);
    return true;
  };
  await second.start();
  const state = second.context.sitter.state;

  assert.deepEqual(second.calls.ensure, [2],
    'a restart did not re-open the question, or it re-opened documents that were current');
  assert.deepEqual(second.records('submit').map(record => record.id), [2]);
  assert.equal(state.counts['failed-session'], 1, 'the retried failure was not classified as one');
  assert.equal(state.counts.current, 2, 'a document that can be indexed stopped being admitted');
  assert.equal(state.failed, 1);
  const classes = second.context.SDT_STATUS_CLASSES;
  const tally = keys => keys.reduce((n, key) => n + (state.counts[key] || 0), 0);
  assert.equal(Object.values(classes).reduce((n, keys) => n + tally(keys), 0), state.scanned);
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
    assert(button.getAttribute('tooltiptext').includes('2 files indexed'));
  }
});

/* --------------------------------------------------------------------------
   Ticket 0686: the toolbar under assistive technology.

   `verification/SDT-SITTER-UI-PANEL.md` records the accessibility reviewer's
   two findings about this button — the spinner rewrites the accessible name,
   and nothing here reads `prefers-reduced-motion`. Both are behaviour of the
   render loop, so both are testable against the mock host rather than only in
   a live window, which is where the sitter harness probe had to leave them.
   -------------------------------------------------------------------------- */
await test('the spinner does not rename the button, and reduced motion stops it spinning', async () => {
  // The frame is `floor(now / 140) % 4`, so pinning the monotonic clock pins
  // the glyph: both arms are rendered at the same instant and the preference is
  // the only thing that differs between them.
  const SPIN = ['◐', '◓', '◑', '◒'];
  const arm = async reducedMotion => {
    const entered = deferred(), finish = deferred();
    const harness = createHarness({
      attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')],
      reducedMotion,
      ensure: async (_id, onProgress) => { onProgress(40); entered.resolve(); await finish.promise; return false; },
    });
    await harness.startHanging();
    await admitted(harness, entered, 'the toolbar spinner');
    assert.equal(harness.context.sitter.state.active, 1,
      'no document is being indexed, so there would be nothing to spin either way');
    harness.clock.mono = 140 * 4 * 1000 + 140;    // frame 1, whatever the run did before
    harness.context.render();
    return harness.windows[0].document.getElementById('sdt-pack-sitter-button');
  };

  // The positive control. Without the preference the glyph really is in the
  // label, so the arm below measures suppression and not absence.
  const animated = await arm(false);
  assert.equal(animated.getAttribute('label'), `${SPIN[1]} Index 0 %`);
  assert.equal(animated.getAttribute('aria-label'), 'Index 0 %',
    'the spinner frame reached the accessible name, which then changes every 140 ms');

  const still = await arm(true);
  assert.equal(still.getAttribute('label'), 'Index 0 %',
    'the spinner runs under prefers-reduced-motion: reduce');
  assert.equal(still.getAttribute('aria-label'), 'Index 0 %');
});

await test('reduced motion stops the completion blink', async () => {
  const arm = async reducedMotion => {
    const harness = createHarness({ attachments: [pdf(1, 'AAAA1111')], reducedMotion });
    await harness.start();
    // Land inside the 1400 ms blink window, on a frame the animation dims:
    // `floor(now / 180)` odd. Read from the clock the sweep left, so the window
    // is the one the plugin actually armed.
    let target = harness.clock.mono + 200;
    while (Math.floor(target / 180) % 2 !== 1) target += 180;
    assert(target < harness.clock.mono + 1400, 'the chosen frame is outside the blink window');
    harness.clock.mono = target;
    harness.context.render();
    return harness.windows[0].document.getElementById('sdt-pack-sitter-button');
  };

  const animated = await arm(false);
  assert.equal(animated.style.properties.get('opacity'), '0.2',
    'the completion blink does not dim, so the arm below would pass against anything');

  const still = await arm(true);
  assert.equal(still.style.properties.get('opacity'), '1',
    'the button is blinked under prefers-reduced-motion: reduce');
});

await test('reduced motion stops the census pulse', async () => {
  // The third animation, and the one the other two scenarios structurally
  // cannot see: `spinning` and `blinking` are each gated on the preference
  // separately, so deleting the census arm of the opacity expression leaves
  // both of them green. Driven by putting the state in the census phase, which
  // is what the pulse is keyed on.
  const arm = async reducedMotion => {
    const harness = createHarness({ attachments: [pdf(1, 'AAAA1111')], reducedMotion });
    await harness.start();
    harness.context.sitter.state.phase = 'census';
    // sin(now / 450) at a quarter turn: the pulse is at its trough, which is a
    // value no other branch of the expression can produce.
    harness.clock.mono = Math.round(450 * (3 * Math.PI / 2));
    harness.context.render();
    return harness.windows[0].document.getElementById('sdt-pack-sitter-button');
  };

  const animated = await arm(false);
  assert.equal(Number(animated.style.properties.get('opacity')).toFixed(2), '0.55',
    'the census pulse does not fade, so the arm below would pass against anything');

  const still = await arm(true);
  assert.equal(still.style.properties.get('opacity'), '1',
    'the button is pulsed under prefers-reduced-motion: reduce');
});

await test('a window that throws from matchMedia leaves the render loop running', async () => {
  // The guard in prefersSDTReducedMotion, held to a throw rather than assumed
  // to hold against one. A docshell going away throws from matchMedia, and this
  // is read once per button on every one of the loop's ten passes a second: an
  // escape here is not a stuttering animation, it is the sitter stopping.
  const harness = createHarness({ attachments: [pdf(1, 'AAAA1111')] });
  await harness.start();
  const window = harness.windows[0];
  window.matchMedia = () => { throw new Error('the docshell is going away'); };
  harness.context.render();

  const button = window.document.getElementById('sdt-pack-sitter-button');
  assert.equal(button.getAttribute('aria-label'), 'Index 100 %', 'the render pass did not complete');
  // Defaulting to motion, not to stillness: a reading that could not be taken
  // is not a preference expressed, and the render() wrapper stays silent
  // because nothing escaped it. The completion blink is running at this exact
  // render, so the opacity value is the one thing that actually depends on
  // which way the guard defaulted -- a build that flipped the fallback to
  // "reduce" would pass every assertion above this one.
  assert.equal(button.style.properties.get('opacity'), '0.2',
    'the guard defaulted to reduced motion instead of to motion');
  assert.equal(harness.records('render-error').length, 0,
    'the throw reached the render loop, which then records it and stops re-trying');
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
  assert.equal(perDocument, 'Estimated duration: 12 min 00 s (between 12 min 00 s and 12 min 00 s)');

  // Inside the bound: the window says when the library should be done.
  harness.advance(1000);
  harness.context.render();
  assert(doc.getElementById('sdt-global-estimate').textContent.startsWith('Estimated finish around '),
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
  assert(doc.getElementById('sdt-document-status').textContent.includes('12 min 01 s elapsed'),
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
  assert(doc.getElementById('sdt-document-status').textContent.includes('0 s elapsed'));

  // Five seconds of work, during which the author's clock is corrected an hour
  // backwards. Three implementations are distinguishable here and only one is
  // right: the wall clock reads -3595 s, a wall clock ratcheted to its own
  // high-water mark freezes at 0 s, and the monotonic source says 5 s.
  harness.clock.mono += 5000;
  harness.clock.wall -= 60 * 60 * 1000;
  harness.context.render();
  assert(doc.getElementById('sdt-document-status').textContent.includes('5 s elapsed'),
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
    assert(doc.getElementById('sdt-document-status').textContent.includes(`${arm.reading} elapsed`),
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
  assert(doc.getElementById('sdt-document-status').textContent.includes('0 s elapsed'),
    doc.getElementById('sdt-document-status').textContent);
  harness.context.heartbeatTick();
  assert.equal(harness.records('heartbeat').at(-1).elapsedMS, 0);

  // And it is a ratchet, not a freeze: the clock catching back up resumes.
  harness.clock.wall += 60 * 60 * 1000 + 7000;
  harness.context.render();
  assert(doc.getElementById('sdt-document-status').textContent.includes('7 s elapsed'),
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
  assert(harness.context.describeSDTAdmission().startsWith('Last reading 1 s '),
    harness.context.describeSDTAdmission());
  harness.clock.mono += 120_000;
  harness.clock.wall -= 60 * 60 * 1000;
  assert(harness.context.describeSDTAdmission().startsWith('Last reading 2 min '),
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

/* --------------------------------------------------------------------------
   Ticket 0696's end-of-sweep toast, through the real wrapper and a real
   disable/re-enable — the sequence, not an equivalent of it.

   Two review seats reproduced the same race by hand and both were right, and
   the more expensive half of the finding was that no suite could have caught it:
   tests/sdt_sitter_scheduler.mjs supplies its own snapshot and its own sitter, so
   it exercises the toast's GATE and never the wrapper that feeds it. This file
   already had the one thing that could — the real `startup()`, the real
   `initialize()`, and `nextSweep()` firing the timer the sitter armed for itself.

   THE SEQUENCE. `sitter` is a module-level binding that `initialize()` reassigns
   and `shutdown()` never clears, and the plugin's own launch prompt advertises
   the way in: "turning the add-on off stops new admissions; the file under way
   finit". So a disable while the extractor holds a file leaves the first sitter's
   sweep suspended, a re-enable installs a second sitter and puts `alive` back to
   true — before the modal confirm, so no click is needed — and when the first
   closure resumes it holds one sitter's snapshot and reads another's counters.

   The two counts must be visibly different for the misattribution to have
   anything to misattribute, so the second sitter indexes two files while the
   first is still suspended holding a snapshot of zero. The assertion is a
   count, not a silence: the second sitter's own toast is legitimate and must
   arrive, and only the stale closure's must not.
   -------------------------------------------------------------------------- */
await test('a disable, a re-enable, and the suspended sweep announces nothing', async () => {
  const entered = deferred(), release = deferred();
  let held = 0;
  const harness = createHarness({
    attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222'), pdf(3, 'CCCC3333')],
    // The second attachment holds the extractor exactly once. Everything else
    // settles the way the mock's own extractor does, so the second sitter has
    // real work to do and real counters to be misread.
    ensure: async (id, onProgress) => {
      if (id === 2 && held++ === 0) {
        entered.resolve();
        await release.promise;
        return false;
      }
      onProgress(10);
      harness.advance(1000);
      harness.persistPack(id);
      onProgress(100);
      return true;
    },
  });
  harness.context.startup({ rootURI: ROOT_URI });
  await admitted(harness, entered, 'the suspended sweep');
  const suspended = harness.context.sitter;
  assert.equal(suspended.state.completed, 1, 'the first sitter never indexed anything');
  assert.deepEqual(harness.toasts, [], 'a toast arrived before any sweep ended');

  // Disable. The file in flight is not cancelled — that is the documented
  // behaviour, and it is what leaves the closure alive.
  harness.context.shutdown(null, 4);
  assert.equal(harness.context.alive, false);

  // Re-enable, and let the second sitter work. `quiet()` would wait on the
  // suspended extractor, so the loop is turned by hand.
  harness.context.startup({ rootURI: ROOT_URI });
  for (let n = 0; n < 80 && harness.context.sitter === suspended; n++) await harness.turn(1);
  assert.notEqual(harness.context.sitter, suspended, 'the re-enable built no second sitter');
  assert.equal(harness.context.alive, true, 'the re-enable left the plugin disabled');
  const current = harness.context.sitter;
  // Waited on the outcome, not on `busy`: a sweep not yet armed is not busy
  // either, and a wait on the negative would fall straight through and assert
  // against a sitter that had not started.
  for (let n = 0; n < 200 && current.state.completed < 2; n++) await harness.turn(1);
  assert.equal(current.state.completed, 2, 'the second sitter indexed nothing');
  // Its own toast is legitimate: that sweep really did index two files. What is
  // asserted below is that nothing is ADDED to this.
  assert.equal(harness.toasts.length, 1, 'the second sitter announced its own work wrongly');
  assert.deepEqual(harness.toasts[0].lines, ['2 files indexed']);
  // Its own reschedule is legitimate too, so the staleness assertion below is
  // against this set rather than against an empty one.
  const armed = harness.timers.ids('timeout');
  assert.equal(armed.length, 1, `the live sitter armed ${armed.length} sweeps`);

  // Now the stale closure wakes into a live plugin it never knew. Before the
  // generation check it diffed a snapshot of zero against the two files above
  // and announced them as its own.
  release.resolve();
  await harness.turn(30);
  assert.equal(harness.toasts.length, 1,
    `a sweep from a dead generation announced ${JSON.stringify(harness.toasts.at(-1)?.lines)}`);
  // And it did not re-arm itself either — the same staleness, in the half of the
  // wrapper that already carried the check. A second entry here would be two
  // sweeps per interval for the rest of the session.
  assert.deepEqual(harness.timers.ids('timeout'), armed,
    'a sweep from a dead generation rescheduled itself');
});

/* Ticket 0730, generalised by ticket 0741. Loading a bootstrap.js twice into one
 * scope used to throw at parse time -- `SyntaxError: Identifier 'closeJournalled'
 * has already been declared` -- because `var`/`function` tolerate redeclaration
 * and `const`/`let`/`class` do not, and the file mixed both. Whether Zotero ever
 * re-runs a bootstrap.js into a scope it has already used stays open on the
 * upgrade path (0727's arm 3 saw a fresh scope there), but disable/re-enable is a
 * different Gecko path and nothing has measured it; the guard makes every file
 * safe regardless, the same way the sitter's top-level bindings are already `var`
 * for the sandbox-exposure reason ticket 0695 recorded.
 *
 * The discovery is the point, and it is why this is no longer one hard-coded
 * path: a hand-listed guard covers the files someone remembered, and the next
 * plugin added is exactly the one it will not cover. A minimal context is
 * deliberate -- the failure is a parse-time SyntaxError, and a full mock host
 * would only obscure it behind its own setup cost. Nothing here executes plugin
 * behaviour beyond the two loads.
 */

/* Directories the walk refuses to enter, and why each one: they are the
 * gitignored checkouts and caches this repository does not ship. `fork`,
 * `fork-*` and `upstream.git` are upstream's own source -- a bootstrap.js
 * appearing there would redden a gate over code we neither wrote nor may
 * change, and walking a full Zotero checkout on every test run is not free.
 * Dot-directories are skipped as a class, which is what keeps the walk out of
 * `.git` and out of `.claude/worktrees/`, where every parallel session's copy of
 * this same tree lives. Everything else IS walked, so a plugin added under a
 * directory nobody has thought of yet is still covered.
 *
 * Two shapes, because .gitignore has two. `UNSHIPPED` is matched on the
 * directory's own name and covers the ignores that sit at the repository root;
 * `UNSHIPPED_PATHS` is matched on the path relative to the walk root, and is
 * what reaches a nested ignore like `bench/data/`, whose bare name is far too
 * common to refuse everywhere. */
const UNSHIPPED = new Set(['node_modules', 'fork', 'upstream.git', 'corpus-cache', '__pycache__']);
const UNSHIPPED_PATHS = new Set(['bench/data']);

function discoverBootstraps(root) {
  const found = [];
  const walk = dir => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name.startsWith('.') || entry.name.startsWith('fork-')
          || UNSHIPPED.has(entry.name)
          || UNSHIPPED_PATHS.has(path.relative(root, full).split(path.sep).join('/'))) continue;
        walk(full);
      } else if (entry.isFile() && entry.name === 'bootstrap.js') {
        found.push(full);
      }
    }
  };
  walk(root);
  return found.sort();
}

/* --------------------------------------------------------------------------
   Ticket 0742: the launch answer is a persisted switch, not a startup ritual.

   The three arms below are the ticket's own red fixtures, and each one was red
   against the code this ticket replaced: the prompt fired at every Zotero
   start, at every disable/re-enable (ticket 0727 arm 4 measured that live), and
   declining left a sitter with a dead toolbar button whose only recovery was
   four clicks into Tools -> Add-ons.

   `calls.prompt` is the load-bearing counter. The prompt is synchronous and its
   only trace is that number, so a test that asserted on the sitter's behaviour
   alone would pass against a plugin that asked the question every single time
   and then ignored the answer.
   -------------------------------------------------------------------------- */
await test('the launch question is asked once and never again, and the answer persists', async () => {
  const harness = createHarness({ attachments: [pdf(1, 'AAAA1111')] });
  await harness.start();
  assert.equal(harness.calls.prompt, 1, 'a fresh profile was not asked');
  assert.equal(harness.Zotero.Prefs.get('extensions.sdt-pack-sitter.enabled'), true,
    'the answer reached no pref, so nothing could hold across a restart');
  // The buttons are labelled to the question. OK/Cancel do not answer "Index
  // attachments in the background, from now on?", which is defect 4 of the
  // ticket's list; a `confirm` reverted here would not reach this assertion at
  // all, since the mock no longer serves one.
  assert.deepEqual(harness.calls.prompts[0].buttons, ['Start indexing', 'Not now']);
  assert(!harness.calls.prompts[0].text.includes('tonight'),
    'the prompt still says "tonight" for a loop that runs for as long as Zotero is open');

  // The disable/re-enable of ticket 0727 arm 4, which re-asked every time.
  harness.context.shutdown(null, 4);
  harness.context.startup({ rootURI: ROOT_URI });
  await harness.quiet();
  assert.equal(harness.calls.prompt, 1, 'the re-enable asked the question again');
  assert.equal(harness.context.alive, true, 'the re-enable left the plugin down');
});

await test('a profile that answered no runs switched off: no census, and a way back', async () => {
  const harness = createHarness({ attachments: [pdf(1, 'AAAA1111')], launch: false });
  await harness.start();
  const s = harness.context.sitter.state;
  assert.equal(s.phase, 'switched-off');
  // The census hashes files, so R22's "all background work" covers it. Nothing
  // ran: no attachment was inspected, none was submitted.
  assert.equal(s.total, 0, 'the census walked the library with indexing off');
  assert.deepEqual(harness.calls.ensure, [], 'a file was submitted with indexing off');
  assert.equal(harness.timers.ids('timeout').length, 0, 'a sweep is armed with indexing off');

  // Off is DISCOVERABLE, which is the half declining never had: the button is
  // installed and says so, rather than reading "Index" over a sitter that will
  // never index anything.
  const button = harness.windows[0].document.getElementById('sdt-pack-sitter-button');
  assert(button, 'no toolbar button, so "off" is reachable only from the Add-ons manager');
  assert.equal(button.getAttribute('label'), 'Indexing off');

  // And it holds. A second session does not ask again and does not start.
  harness.context.shutdown(null, 4);
  harness.context.startup({ rootURI: ROOT_URI });
  await harness.quiet();
  assert.equal(harness.calls.prompt, 1, 'a declined launch was asked again next session');
  assert.equal(harness.context.sitter.state.phase, 'switched-off');
  assert.deepEqual(harness.calls.ensure, []);
});

await test('an answered profile is never asked, and the toolbar is installed after the question', async () => {
  const harness = createHarness({ attachments: [pdf(1, 'AAAA1111')],
    prefs: { 'extensions.sdt-pack-sitter.enabled': true } });
  await harness.start();
  assert.equal(harness.calls.prompt, 0, 'a profile that already answered was asked again');
  assert.deepEqual(harness.calls.ensure, [1], 'the persisted yes did not start the sitter');

  /* The ordering race, defect 6. `alive = true` and the toolbar button used to
     be installed BEFORE the confirm, so the button appeared in the window under
     a modal still asking whether the sitter should run — a promise made to the
     user before he had answered, and the same class of defect ticket 0696 had
     to guard against. Observed the only way it can be: a hook that reads the
     window while the modal is up.

     Both halves are asserted. `underTheModal` proves the hook actually ran —
     without it a plugin that never asked at all would leave `seen` at its
     initial value and this arm would pass by never looking. */
  let seen = null;
  const staged = createHarness({ attachments: [pdf(2, 'BBBB2222')],
    onPrompt: windows => {
      seen = windows.map(window => !!window.document.getElementById('sdt-pack-sitter-button'));
    } });
  await staged.start();
  assert.deepEqual(seen, [false],
    'the toolbar button was installed under the modal that was still asking');
  assert.equal(staged.calls.prompt, 1, 'the ordering hook never ran; nothing was observed');
  // And it arrives once the answer is in.
  assert(staged.windows[0].document.getElementById('sdt-pack-sitter-button'),
    'the button never arrived after the question was answered');
});

/* The half of the switch the three arms above could not see, found by review
   rather than by them and worth recording as such: each of those drives the
   switch from a RESTING sitter, and the defect only exists while a sweep is
   suspended inside `ensure()`.

   `disarmSDTSitter` clears the three timer handles, but the suspended sweep
   closure holds none of them — it reschedules from its own `finally`, gated on
   `alive` and `generation`, and the user's switch moves neither. So the zombie
   rearmed itself, and the next arm added a second loop beside it: two sweeps per
   interval for the rest of the session, which is precisely what the `pulse`
   guard exists to prevent and precisely the path that guard cannot see.

   Both assertions are load-bearing and neither implies the other. The first is
   about the off state honouring what SPEC.md's R22 paragraph claims for it; the
   second is about the count after a round trip, which a fix that merely stopped
   the zombie announcing would leave broken. */
await test('turning indexing off mid-extraction leaves no zombie sweep, and re-enabling arms one', async () => {
  const entered = deferred(), finish = deferred();
  const harness = createHarness({ attachments: [pdf(1, 'AAAA1111'), pdf(2, 'BBBB2222')],
    ensure: async (id, onProgress) => {
      onProgress(10);
      entered.resolve();
      await finish.promise;
      onProgress(100);
      return true;
    } });
  harness.context.startup({ rootURI: ROOT_URI });
  await admitted(harness, entered, 'the switch fixture');

  harness.context.toggleSDTSwitch();
  assert.equal(harness.context.sitter.state.phase, 'switched-off');
  // The file in flight is not cancelled — the graceful semantics the 2026-09-05
  // ruling gave disable, and unchanged by this switch. It settles, and its
  // settlement is what carries the suspended closure into its `finally`.
  finish.resolve();
  await harness.quiet();
  assert.equal(harness.timers.ids('timeout').length, 0,
    'a sweep is still scheduled after indexing was turned off mid-extraction');

  harness.context.toggleSDTSwitch();
  await harness.quiet();
  assert.equal(harness.timers.ids('timeout').length, 1,
    'two independent sweep loops are running after an off/on cycle during an extraction');
});

/* PASS / FAIL / NOT-RUN, rather than a boolean. A guard that greens because it
 * found nothing to check is the failure this repository keeps meeting, so the
 * empty set gets a verdict of its own and the caller has to say what it does
 * with it. */
function doubleLoadReport(root) {
  const files = discoverBootstraps(root);
  const failures = [];
  for (const file of files) {
    const source = fs.readFileSync(file, 'utf8');
    const context = vm.createContext({ Zotero: {}, Services: {}, ChromeUtils: {} });
    vm.runInContext(source, context);
    try {
      vm.runInContext(source, context);
    } catch (error) {
      failures.push(`${file}: ${error.message}`);
    }
  }
  return { verdict: files.length === 0 ? 'NOT-RUN' : failures.length ? 'FAIL' : 'PASS', files, failures };
}

await test('every bootstrap.js this tree ships loads twice into one scope without throwing', async () => {
  const report = doubleLoadReport('.');
  assert.notEqual(report.verdict, 'NOT-RUN',
    'the walk found no bootstrap.js at all -- the tree moved, not the plugins');
  assert.deepEqual(report.failures, [],
    `a second load threw; a top-level const/let/class is declared in:\n${report.failures.join('\n')}`);
});

/* The control for the discovery step, and it is two-sided on purpose. A walk
 * that always returned nothing would satisfy the empty half alone, and the guard
 * above would then be green over an empty set forever -- which is the exact
 * shape this file exists to refuse. So: a tree with a decoy file and a nested
 * directory reports NOT-RUN, and the SAME tree with one real bootstrap.js
 * reaches a verdict. The planted file is deliberately broken in the way the
 * guard is about, so the positive half also proves the assertion fires and not
 * merely that discovery counted to one. */
await test('an empty discovery set reports NOT-RUN, and a planted file proves the walk can see one', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sdt-bootstrap-walk-'));
  try {
    fs.mkdirSync(path.join(root, 'plugin', 'nested'), { recursive: true });
    fs.writeFileSync(path.join(root, 'plugin', 'not-bootstrap.js'), 'const x = 1;\n');
    const empty = doubleLoadReport(root);
    assert.equal(empty.verdict, 'NOT-RUN', `an empty tree was reported ${empty.verdict}`);
    assert.deepEqual(empty.files, []);

    fs.writeFileSync(path.join(root, 'plugin', 'nested', 'bootstrap.js'), 'const planted = 1;\n');
    const planted = doubleLoadReport(root);
    assert.equal(planted.verdict, 'FAIL',
      'a planted double-load failure was not seen -- the walk or the assertion is blind');
    assert.equal(planted.files.length, 1);
    assert(planted.failures[0].includes('planted'), planted.failures[0]);

    // And the refusals refuse. Both shapes are exercised, since a name match and
    // a path match are different code: `node_modules` by name, `bench/data` by
    // its position under the root. Without this the skip list is a branch no run
    // ever takes, and a typo in either would read as green forever.
    for (const ignored of ['node_modules', path.join('bench', 'data')]) {
      fs.mkdirSync(path.join(root, ignored), { recursive: true });
      fs.writeFileSync(path.join(root, ignored, 'bootstrap.js'), 'const ignored = 1;\n');
    }
    const withIgnored = doubleLoadReport(root);
    assert.deepEqual(withIgnored.files, planted.files,
      'the walk entered a directory this repository does not ship');
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

console.log(JSON.stringify({ tests: results, result: 'pass' }));
