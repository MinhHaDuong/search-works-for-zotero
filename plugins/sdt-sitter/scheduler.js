/* The census's whole status vocabulary, partitioned by what each status means for
   the author's library. Every attachment lands in exactly one class, and that is
   what makes the two numbers on screen add up: `indexed + failed + queued` is the
   coverage denominator, `outOfScope` is the rest of the library. One owner —
   admission, the failure banner and the coverage line all read this list, so a
   status added to one of them cannot be forgotten by the others.

   Ticket 0699. `inspection-error`, `unsupported-pack` and `missing-source` used to
   belong to no class at all: outside the admission whitelist, outside the failure
   tally, inside the coverage denominator. The dialog could read "0 fichiers n'ont
   pas pu être indexés" over a library where none of them was indexed, and coverage
   could not reach 100 % with nothing on screen saying why. */
var SDT_STATUS_CLASSES = {
  indexed: ['current'],
  // A verified native pack with no non-whitespace text stays in the coverage
  // denominator but is neither searchable nor an extraction candidate. Ticket 0760.
  unindexed: ['empty-pack'],
  // Not indexed, and not admissible: nothing this sweep does changes them. Named
  // for `state.failed`, the banner it feeds, and deliberately NOT `blocked` —
  // `host.blocked()` in the same codebase answers a different question (whether
  // resources allow an admission right now), and one word for both invites the
  // reader to take a stalled sitter for a library full of failures.
  //
  // `failed-session` is held for the session and no longer (ticket 0740). The
  // span is the author's ruling of 2026-09-08 and it is also native SDT's own:
  // its service retries a generic extraction failure on every new call, so a
  // verdict that outlived the session would override the contract this repo
  // verified rather than extend it. A failure stays in this class while it is
  // held — the author's "could not be indexed" figure must not shrink because
  // the sitter stopped asking within the session.
  //
  // `unusable-source` is a file that is there and cannot be what its label says:
  // empty, or a web page recorded as a PDF (ticket 0825). Like `missing-source`
  // it is library state the author can repair and a retry cannot, so it is held
  // here rather than resubmitted every session as `failed-session` was.
  failed: ['failed-session', 'inspection-error', 'unsupported-pack', 'missing-source',
    'unusable-source'],
  // Not indexed yet. Exactly the statuses admission accepts, and nothing else.
  queued: ['missing-pack', 'stale-source', 'stale-processor', 'invalid-pack'],
  // Not the sitter's business: trashed or not an attachment, or no processor exists.
  outOfScope: ['excluded', 'unsupported'],
};

/* How long one pass of the drain may hold the pump before the candidate search
   below it gets a turn. Ticket 0796: the loop had no bound at all, so any
   notification source faster than it held control below it indefinitely and
   admission was never reached.

   DESIGN-NOTES.md owns every fact about the value and this comment restates
   none of them: why the bound is wall clock rather than a count of ids -- the
   thing about this line a later reader is most likely to undo -- how the number
   is set against bootstrap.js's heartbeat, why it is a cadence knob and not a
   correctness gate, the incident it answers, and the open question it is an
   instance of (6, whether the indexing consumers should share one budget). */
var SDT_DRAIN_BUDGET_MS = 5000;

/* Host-independent admission loop. Native ensure owns extraction and persistence. */
var createSDTSitter = function (host) {
  // `busy` is on the state rather than a closure variable because the heartbeat
  // reads it: a hang in census or in the admission check leaves `active` null,
  // and a heartbeat gated on `active` is silent for exactly the phases ticket
  // 0703 needed a trace of. Phase cannot stand in for it — after stop() aborts a
  // sweep mid-extraction the phase fixup is skipped and `phase` stays stale at
  // 'extracting', where `busy` goes false the instant sweep() truly exits.
  const state = { enabled: true, busy: false, phase: 'ready', active: null, progress: null,
    lastProgressAt: null, startedAt: null, completed: 0, failed: 0,
    scanned: 0, total: 0, counts: {}, serviceMS: 0, samples: [], activeInfo: null,
    fittedSamples: [], pending: [], candidates: 0, error: null, cacheWarning: null,
    censusSnapshot: null, censusBuilding: false, unattached: [],
    // Ticket 0792: the drain's remaining backlog, so the window can count it
    // down. Distinct from `candidates`, which is the census queue and does not
    // move during a drain at all.
    draining: 0 };
  const failed = new Set();
  // Publish one complete census generation at a time. `state.counts` is rebuilt
  // from empty on every sweep and remains useful as live diagnostics, but no UI
  // total may combine that half-filled generation with a total held from the last
  // one. The copied object is one atomic assignment; after the census closes, each
  // admission settlement refreshes it so the next sweep holds the latest complete
  // state rather than the pre-admission census. Ticket 0718.
  const publish = () => {
    if (state.scanned === state.total && !state.censusBuilding) {
      const counts = { ...state.counts };
      const members = [...observed].map(([id, info]) => ({ id, ...info }));
      state.censusSnapshot = { counts, total: state.total, members, unattached: state.unattached.slice() };
      state.failed = SDT_STATUS_CLASSES.failed
        .reduce((n, key) => n + (counts[key] || 0), 0);
    }
    // Not gated on `enabled`: an in-flight job left to finish gracefully after
    // the switch is thrown must still be seen finishing, progress tick and
    // completion both -- a window that stops repainting is not what "the file
    // under way finishes" promises (found live, testing v0.3.17). Whether
    // anything actually redraws from this is the host's call: bootstrap.js's
    // own `render()` is gated on `alive`, which is what stays correct across a
    // real shutdown, where nothing should update because the window is gone.
    host.changed(state);
  };
  // Only this pump mutates the observed map. Notifier callbacks enqueue work and
  // return synchronously, including while Zotero is committing a transaction.
  const observed = new Map(), dirty = new Set();
  let reconciliationPending = true, epoch = 0;
  const interval = host.reconciliationIntervalMS ?? 60 * 60 * 1000;
  state.lastReconciliationAt = null;
  state.nextReconciliationAt = null;
  const classify = info => SDT_STATUS_CLASSES.queued.includes(info.status) &&
    info.identity && failed.has(info.identity) ? 'failed-session' : info.status;
  const inspect = async id => {
    try { return await host.inspect(id); }
    catch (error) {
      let errorClass = 'Error';
      try {
        if (typeof error?.name === 'string' && /^[\w.$-]{1,64}$/.test(error.name)) errorClass = error.name;
      } catch (_error) { errorClass = '<unreadable error>'; }
      return { status: 'inspection-error', itemID: id, title: null, errorClass };
    }
  };
  const refreshQueue = () => {
    state.pending = [...observed].filter(([, info]) => SDT_STATUS_CLASSES.queued.includes(info.status))
      .map(([id, info]) => ({ id, title: info.title ?? null, parentTitle: info.parentTitle ?? null,
        sourceBytes: info.sourceBytes, pages: info.pages }));
  };
  const record = (id, info) => {
    const previous = observed.get(id);
    if (previous) state.counts[previous.status]--;
    const status = classify(info);
    if (info.absent) observed.delete(id);
    else {
      observed.set(id, { ...info, status });
      state.counts[status] = (state.counts[status] || 0) + 1;
    }
    state.total = state.scanned = observed.size;
    refreshQueue();
    if (host.samples) {
      state.samples = host.samples();
      // Invalidation removes old observations immediately; newly collected ones
      // join the fit only at the normal completion cadence below.
      const validSamples = new Set(state.samples);
      state.fittedSamples = state.fittedSamples.filter(sample => validSamples.has(sample));
    }
  };
  const api = {
    state,
    stop() { state.enabled = false; epoch++; },
    start() {
      state.enabled = true; reconciliationPending = true;
      if (state.phase === 'switched-off') state.phase = 'ready';
    },
    invalidate(ids) { for (const id of ids) dirty.add(id); },
    // Explicit callers retain the census API; ordinary wakeups use pump().
    async sweep() { reconciliationPending = true; return api.pump(); },
    async pump() {
      if (!state.enabled || state.busy) return;
      state.busy = true;
      const token = epoch;
      const attempted = new Map();
      const current = () => state.enabled && token === epoch;
      if (host.emit) host.emit('sweep-start', {}, 'trace');
      try {
        while (current()) {
          if (state.nextReconciliationAt !== null && host.now() >= state.nextReconciliationAt)
            reconciliationPending = true;
          if (reconciliationPending) {
            reconciliationPending = false;
            if (state.total > 0 && state.scanned !== state.total)
              state.censusSnapshot ??= { counts: { ...state.counts }, total: state.total };
            state.phase = 'census'; state.scanned = 0; state.counts = {}; state.censusBuilding = true;
            const ids = await host.list();
            if (!current()) return;
            const unattached = host.unattached ? await host.unattached() : [];
            if (!current()) return;
            state.total = ids.length; publish();
            const next = new Map();
            for (const id of ids) {
              await host.yield();
              if (!current()) return;
              const info = await inspect(id);
              if (!current()) return;
              const status = classify(info);
              next.set(id, { ...info, status });
              state.scanned++;
              state.counts[status] = (state.counts[status] || 0) + 1;
              publish();
            }
            if (host.censusComplete) {
              state.samples = await host.censusComplete();
              if (!current()) return;
              state.fittedSamples = state.samples.slice();
            }
            observed.clear(); for (const entry of next) observed.set(...entry);
            state.unattached = Array.isArray(unattached) ? unattached.slice() : [];
            state.censusBuilding = false;
            state.lastReconciliationAt = host.now();
            // A delayed or long scan is one reconciliation, never a catch-up loop.
            state.nextReconciliationAt = state.lastReconciliationAt + interval;
            refreshQueue(); state.candidates = state.pending.length; publish();
            // Ticket 0792. The census is OVER here, and until this line the
            // phase said otherwise for the whole of what follows: `'census'`
            // is assigned once above and the next assignment is admission's,
            // so the drain, the candidate search and `blocked()` all inherited
            // it. Six minutes of post-census work read as a census on the
            // author's own library (2026-09-15, v0.4.15), and the heartbeat
            // that should have caught it repeated the same false word.
            //
            // `'ready'` and not a new label for the admission gap itself: that
            // gap recurs between every pair of documents, so a labelled phase
            // there would flip on every file and put the switch line on the
            // announcement channel each time -- the 10 Hz defect in slower
            // clothes, which is the one thing this may not buy. `'ready'` is
            // silent by design and the transition hold absorbs it.
            state.phase = 'ready'; publish();
          }
          // Ticket 0792: the drain is the one post-census stretch that is long
          // on its own account, so it gets a name and two records, where it had
          // neither. What made it long was a library-wide `unattached()` per id;
          // ticket 0810 replaced that with one targeted refresh per pass, and
          // the drain is still the stretch a bulk sync fills, one inspection per
          // notified id.
          if (dirty.size && current()) {
            state.phase = 'draining'; state.draining = dirty.size; publish();
            if (host.emit) host.emit('drain-start', { pending: dirty.size }, 'trace');
          }
          const hadBacklog = dirty.size > 0;
          // Ticket 0796, and the two halves are not redundant. The deadline is
          // what returns control to the outer loop under a source that refills
          // `dirty` faster than this retires it -- without it the loop below
          // exits only on an empty set, which such a source never allows, and
          // the candidate search and admission underneath are never reached.
          // `retired` is what guarantees the converse: the deadline is read
          // against a clock an `unattached()` slower than the whole budget can
          // already have run past, so a bare deadline check would break before
          // retiring anything and the drain would livelock, spending every
          // outer pass on an id it never removes. At least one id leaves
          // `dirty` per pass, always; the set still empties, only later.
          const deadline = host.now() + SDT_DRAIN_BUDGET_MS;
          let retired = 0;
          /* Ticket 0810. The no-attachment view is refreshed from the records
             this pass could have changed — the record an event named, and the
             old and new parent of every attachment it touched — and never from
             a library-wide walk, which is the cost ticket 0796's budget could
             bound but not remove.

             The coalescing unit is the published generation, which is one
             retired id. Within it a record named twice is read once; across
             generations it is read again, because the event that names it the
             second time is exactly the kind that may have changed its
             membership — an attachment leaves P, the generation publishes, and
             another joins P later in the same pass. Deduping across the whole
             pass suppressed that second read and published "P has no file" over
             P's new file. What the reads still never scale with is the library:
             they are the records the events themselves named, summed over the
             generations that named them.

             Publishing the view only after the loop was cheaper by nothing and
             left each intermediate generation quoting a stale view to
             `collectSDTNotIndexed`, which reads `censusSnapshot.unattached` on
             every render. */
          let reconcileNeeded = false;
          while (dirty.size && current()) {
            if (retired > 0 && host.now() >= deadline) break;
            let changed = false;
            const id = dirty.values().next().value;
            dirty.delete(id); // BEFORE awaits: a new event for this ID survives.
            const ids = host.affected ? await host.affected(id) : [id];
            if (!current()) { dirty.add(id); return; }
            // Fully determined by `ids` before the loop runs.
            const sawSelf = ids.has ? ids.has(id) : Array.from(ids).includes(id);
            /* What this generation has to read. A falsy candidate is no id:
               Zotero's own `_getParentID()` answers `false` for "no parent",
               and item ids are positive integers, so one test covers `false`,
               `null` and `undefined` alike. */
            const candidates = new Set();
            const consider = candidate => { if (candidate) candidates.add(candidate); };
            // Per affected id, never shared across them: a sibling's parent
            // says nothing about whether THIS id is covered, and a flag hoisted
            // out of the loop let one suppress the other's reconciliation.
            const unplaceable = new Set();
            for (const affected of ids) {
              // Before inspect(), never after: inspect() is what overwrites the
              // parent map, so a read taken afterwards can no longer name the
              // parent an attachment has just left.
              const previousParent = host.parentOf ? host.parentOf(affected) : undefined;
              const info = await inspect(affected);
              if (!current()) { dirty.add(id); return; }
              record(affected, info); changed = true;
              consider(previousParent);
              consider(info.parentItemID);
              // Neither this module's map nor Zotero can say anything about an
              // id that is gone and was never tracked. It may still be covered
              // — by a child that names it as a parent — so the verdict waits
              // until every affected id has had its say.
              if (previousParent === undefined && info.absent) unplaceable.add(affected);
            }
            // A bibliographic-record notification carries no attachment ids of
            // its own: `affected()` answers with its children, and the record
            // the event named is then the candidate whose membership may have
            // moved.
            if (!sawSelf) consider(id);
            /* An erased record IS covered when the children that still name it
               put it in the candidate set; what nothing names, no targeted read
               can reach, so ask for the one full reconciliation the ticket
               allows rather than claim the view is current. Membership of the
               candidate set is the whole test, which is why it is asked after
               the loop and per affected id. */
            for (const orphan of unplaceable) if (!candidates.has(orphan)) reconcileNeeded = true;
            if (candidates.size && host.refreshUnattached) {
              const { list } = await host.refreshUnattached(candidates);
              if (!current()) { dirty.add(id); return; }
              if (Array.isArray(list)) state.unattached = list;
              changed = true;
            }
            if (!current()) { dirty.add(id); return; }
            state.draining = dirty.size;
            retired++;
            if (changed) publish();
          }
          if (reconcileNeeded) reconciliationPending = true;
          if (hadBacklog && current()) {
            // Ticket 0796 moved both fields off constants the budget made false.
            // `state.draining` used to be zeroed here because the loop above
            // could only exit on an empty set; a budgeted exit leaves a real
            // backlog, and the window's "draining N" line reads this (0759: the
            // totals stay live and disclosed, so it must not read 0 over 6000
            // outstanding ids). The record's `drained` used to be fed the backlog
            // at the START of the pass, which equalled what the pass retired only
            // because the pass always ran to empty; `retired` is that count
            // directly, so the field keeps meaning what its name says across a
            // budgeted exit, and `pending` beside it is what is left for the next
            // pass. The local that carried it is now `hadBacklog`, which is all
            // it was ever read for.
            state.draining = dirty.size;
            if (host.emit) host.emit('drain-end', { drained: retired, pending: dirty.size }, 'trace');
          }
          /* Ticket 0810. An unresolvable event asked for a full reconciliation,
             and the census that answers it sits at the TOP of this loop — while
             the candidate search below exits by `break` as soon as the queue is
             empty. Returning to the top now is what makes the fallback a repair
             rather than a note left for the hourly deadline. The flag is cleared
             by the census itself, and the drain retired every id before it, so
             this is one extra turn and not a cycle. */
          if (reconciliationPending && current()) continue;
          if (!current()) return;
          const candidate = state.pending.find(item => !attempted.has(item.id) ||
            attempted.get(item.id) !== observed.get(item.id)?.identity);
          // Ticket 0796: `continue` while events are still waiting, which is the
          // rule the `host.blocked()` gate below has always applied, for the same
          // reason. The budgeted drain above can hand this line a real
          // backlog, where before the drain could only exit on an empty set and
          // this `break` was reached with nothing outstanding. Leaving with one
          // is worse than it looks: `nextSweepDelayMS` in bootstrap.js reads
          // `pending.length`, `phase`, `busy` and `nextReconciliationAt` and
          // never `state.draining`, so with no candidate and no blocked phase its
          // retry is Infinity and the next sweep is the reconciliation deadline,
          // up to an hour out; and `wakeSDTSitter()` does not cover it either,
          // since it returns early while `busy` -- exactly when these
          // notifications arrived. The drain retires at least one id per pass, so
          // this terminates as soon as the source does.
          if (!candidate) {
            if (dirty.size) continue;
            state.phase = 'waiting'; break;
          }
          const id = candidate.id;
          let before = observed.get(id);
          const gated = before;
          await host.yield();
          if (!current()) return;
          const reason = await host.blocked(before);
          if (!current()) return;
          if (reason && host.emit) {
            const idle = reason === 'native-worker-busy';
            host.emit(idle ? 'worker-idle-wait' : 'refuse', { reason }, idle ? 'trace' : 'state');
          }
          if (reason) {
            state.phase = reason; publish();
            if (dirty.size) continue; // A resource wait must not delay discovery.
            break;
          }
          // Resources may have taken time to read. Inspect again at admission so
          // a removed source or a pack another consumer just produced wins.
          before = await inspect(id);
          if (!current()) return;
          record(id, before); publish();
          // Ticket 0792, both lines. These `continue`s return to the top of the
          // OUTER loop, three lines above `attempted.set(id, ...)`, so the item
          // was never marked tried and `state.pending.find()` could re-pick it
          // on the very next turn. While the re-inspect keeps disagreeing with
          // the census -- a file being written, a memoized hash turning over --
          // that is an unbounded spin, each turn costing two /proc reads, a
          // stat, a DB query and possibly an MD5, with the phase stuck on
          // whatever preceded it. Recording the identity just observed keeps
          // the retry: `find()` re-picks an item whose identity has CHANGED
          // since the attempt, which is exactly the case worth retrying, and
          // skips it while it has not.
          if (!SDT_STATUS_CLASSES.queued.includes(observed.get(id)?.status)) {
            attempted.set(id, before.identity); continue;
          }
          // A MOVED source is re-gated at once and deliberately NOT recorded as
          // an attempt: the resource reading `blocked()` just took was for a
          // directory this attachment no longer lives in, and the loop must
          // come straight back to it and read the new one. The directory is
          // Zotero's own storage layout rather than anything the file's bytes
          // decide, so it does not churn.
          if (before.directory !== gated.directory) continue;
          // Identity alone is the churn case, and the one that span: a file
          // being written or a memoized hash falling out of its re-verify
          // window changes it on every inspect, and with no record of the
          // attempt `find()` re-picks the same item forever.
          if (before.identity !== gated.identity) {
            attempted.set(id, before.identity); continue;
          }
          const admissionReason = host.beforeSubmit?.();
          if (admissionReason) { state.phase = admissionReason; publish(); break; }
          attempted.set(id, before.identity);
          if (host.emit) host.emit('admit', { id, sourceBytes: before.sourceBytes, pages: before.pages });
          state.active = id; state.startedAt = host.now();
          state.activeInfo = { title: before.title ?? null, parentTitle: before.parentTitle ?? null,
            sourceBytes: before.sourceBytes, pages: before.pages };
          state.lastProgressAt = state.startedAt; state.progress = null;
          state.phase = 'extracting'; publish();
          if (host.emit) host.emit('submit', { id });
          // The duration sample's own clock, and deliberately not state.startedAt,
          // which the UI's elapsed line, the overrun check and the prediction math
          // all read as "since submission" and must keep reading that way. Between
          // the two, ensure() hashes the file, validates any existing pack, and
          // queues behind whatever native work is already running — none of it a
          // property of this document, all of it booked as its extraction time
          // (ticket 0704). With three samples the 95th percentile IS the maximum,
          // so one inflated observation sets the upper bound for every later
          // estimate, and the cache keeps it until a processor version bump.
          let extractingSince = null;
          try {
            // No `enabled` checks from here to this document's own settlement:
            // once handed to the native worker, this ONE item's outcome always
            // reaches the census, success or failure, whatever the switch does
            // while it runs. The worker cannot be told to stop, and the ruling
            // this graceful stop implements is that it "may finish and persist
            // its native pack" — a persisted pack the census never learns about
            // is a completion invisible until some later sweep stumbles on it,
            // which is not what that promise says (found live, testing
            // v0.3.17: the bar froze mid-job and never reached 100%). The
            // OUTER loops above and below this one still gate on `enabled`, so
            // no further document is ever admitted while off.
            const ok = await host.ensure(id, progress => {
              const at = host.now();
              extractingSince ??= at;
              state.progress = progress; state.lastProgressAt = at;
              if (host.emit) host.emit('progress', { id, progress }, 'trace');
              publish();
            });
            const after = await host.inspect(id);
            // Thrown, and nothing else: the catch below adds the identity to the
            // session's `failed` set, which is the whole of the suppression
            // ticket 0740 asks for. Native returning without a pack and native
            // throwing are the same span here on purpose — a worker that ran out
            // of memory and a photograph that holds no text are indistinguishable
            // from this side, and only one of them is permanent.
            if (!ok || !['current', 'empty-pack'].includes(after.status) || after.identity !== before.identity) throw new Error('Native SDT did not persist a verified pack');
            state.completed++; state.serviceMS += host.now() - state.startedAt;
            // No progress tick means no observed start, and the window from
            // submission is not a stand-in for one: it IS ensure()'s hash, pack
            // validation and queue wait, the quantity this ticket exists to stop
            // booking as extraction. The first fix fell back to it, which quietly
            // reinstated the whole defect for every document that finishes without
            // a single tick — the small, fast, already-cached case, and so
            // proportionally the one it distorts hardest.
            //
            // The duration is therefore withheld rather than guessed, and the
            // guess it refuses includes the flattering one: stamping the clock at
            // settle would record about zero, which is no more measured than the
            // inflated figure and outlives the session in the cache exactly as
            // that one did. SPEC.md already lets an estimate be unavailable for
            // want of observations; it does not let one be invented. Everything
            // else about the document still settles — the count, the journal
            // record, the bucket — only the number nobody measured is missing.
            const measured = extractingSince === null ? null
              : { sourceBytes: before.sourceBytes, pages: before.pages,
                milliseconds: host.now() - extractingSince };
            if (measured) state.samples.push(measured);
            if (host.emit) host.emit('settle',
              { id, ok: true, ms: measured ? measured.milliseconds : null });
            // Contained on purpose. `inspect()` has just verified a current pack, so
            // the attachment IS indexed; the observation that follows only writes a
            // duration into a store SPEC.md calls derived and disposable. Letting it
            // reach the catch below turned a verified success into a failure and
            // blacklisted the source by identity, so no later sweep retried it either.
            if (measured && host.observed) {
              try { await host.observed(before, measured); }
              // Contained, not silent: a swallow with no surface at all is how a
              // cache that has stopped recording durations looks exactly like one
              // that is working. No detail travels — the throw can come from the
              // platform, and a platform message names whatever it failed on
              // (bootstrap.js's classifyError carries the argument in full).
              catch (_error) { if (host.emit) host.emit('observe-failed', { id }, 'trace'); }
            }
            if (measured && state.samples.length % 3 === 0) state.fittedSamples = state.samples.slice();
            record(id, after);
          } catch (error) {
            const after = await inspect(id);
            if (SDT_STATUS_CLASSES.queued.includes(after.status) && after.identity === before.identity) {
              if (before.identity) failed.add(before.identity);
            }
            if (after.status === 'inspection-error' ||
                (SDT_STATUS_CLASSES.queued.includes(after.status) && after.identity === before.identity)) {
              state.error = host.describeError ? host.describeError(before, error) : String(error);
              if (host.reportError) await host.reportError(before, error);
            } else if (host.emit) {
              host.emit('settle', { id, ok: false, status: after.status });
            }
            record(id, after);

          } finally {
            state.active = null;
            refreshQueue();
          }
          publish();
        }
        if (current() && state.phase === 'extracting') state.phase = 'waiting';
      } catch (error) {
        if (current()) { state.phase = 'error'; state.error = String(error); }
        reconciliationPending = true;
      } finally {
        state.busy = false;
        if (host.emit) host.emit('sweep-end',
          { phase: state.phase, scanned: state.scanned, completed: state.completed,
            failed: state.failed, pending: state.pending.length }, 'trace');
        publish();
      }
    },
  };
  return api;
};

/* Disposable derived records, without paths, text, failures or active jobs. */
var createSDTCache = function (raw, versions) {
  const records = Object.create(null);
  const dirty = new Set();
  const validSample = s => s && Number.isFinite(s.milliseconds) && s.milliseconds > 0 &&
    Number.isFinite(s.sourceBytes) && s.sourceBytes > 0 &&
    (s.pages == null || (Number.isFinite(s.pages) && s.pages > 0));
  if (raw?.format === 1 && raw.versions === versions && raw.records && typeof raw.records === 'object') {
    for (const [key, r] of Object.entries(raw.records)) {
      if (!r || typeof r.signature !== 'string') continue;
      records[key] = { signature: r.signature };
      if (typeof r.fingerprint === 'string' && Number.isFinite(r.sourceBytes) && r.sourceBytes > 0 &&
          (r.pages == null || (Number.isFinite(r.pages) && r.pages > 0))) {
        Object.assign(records[key], { fingerprint: r.fingerprint, sourceBytes: r.sourceBytes, pages: r.pages });
      }
      if (r.empty === true) records[key].empty = true;
      if (validSample(r.sample)) records[key].sample = {
        milliseconds: r.sample.milliseconds, sourceBytes: r.sample.sourceBytes, pages: r.sample.pages ?? null };
    }
  }
  return {
    drop(key) { if (records[key]) dirty.add(key); delete records[key]; },
    check(key, signature, fingerprint) {
      const record = records[key];
      if (record?.signature !== signature) { if (record) dirty.add(key); delete records[key]; return null; }
      return record.fingerprint === fingerprint ? record : null;
    },
    remember(key, signature, fingerprint, info) {
      const previous = records[key];
      records[key] = { signature, fingerprint, pages: info.pages, sourceBytes: info.sourceBytes,
        empty: info.status === 'empty-pack' };
      dirty.add(key);
      if (previous?.signature === signature && previous.sample) records[key].sample = previous.sample;
    },
    observe(key, signature, sample) {
      if (records[key]?.signature === signature && validSample(sample)) { records[key].sample = sample; dirty.add(key); }
    },
    prune(keys) { for (const key of Object.keys(records)) if (!keys.has(key)) { delete records[key]; dirty.add(key); } },
    changes(all = false) { return [...(all ? new Set([...Object.keys(records), ...dirty]) : dirty)].map(key => ({ key, record: records[key] || null })); },
    saved(changes) { for (const { key } of changes) dirty.delete(key); },
    samples() { return Object.values(records).filter(r => validSample(r.sample)).map(r => r.sample); },
    data() { return { format: 1, versions, records }; },
  };
};

/* The source MD5, remembered against the file's (path, size, mtime).

   The sitter's cache key embeds the source hash, so `inspect()` had to hash the
   file before it could consult the cache — and `sweep()` inspects the whole
   library every time. Net effect: a full-library MD5 read every 30 seconds, all
   night, from a plugin whose stated design is a quiet supervisor with a minimal
   footprint (ticket 0701). Native Zotero's own SDT code keys a fingerprint on
   exactly these three values for exactly this reason.

   In memory only, and derived: it is not a claim about job state, and the worst
   a stale entry costs is one recomputed identity. Nothing here is persisted, so
   the disposable-cache-only ruling stands untouched.

   The fingerprint is a proxy for the bytes, not the bytes, and it has a blind
   spot: a file rewritten in place at the same length with its mtime restored is
   invisible to it. So the author ruled that no entry is trusted forever — past
   `maxAgeMS` the real MD5 is read again whether or not the three values still
   match, which bounds how long such a rewrite can go unnoticed. A per-restart
   bound would have been free, since this Map is built in initialize() and a
   disable/re-enable already discards it, and it would also have been worth
   nothing: the case that needs a bound is the session that runs for weeks. */
var createSDTSourceHashes = function (maxAgeMS = 24 * 60 * 60 * 1000) {
  const records = new Map();
  return {
    async hash(key, path, stat, now, compute) {
      // The path is in the fingerprint because a file moved between attachments
      // can carry a byte-identical size and mtime.
      const fingerprint = JSON.stringify([path, stat.size, stat.lastModified]);
      const known = records.get(key);
      // Age outside [0, maxAgeMS) re-verifies, so a clock stepped backwards by
      // NTP shortens the trust window instead of extending it.
      const age = known ? now - known.verifiedAt : Infinity;
      if (known && known.fingerprint === fingerprint && age >= 0 && age < maxAgeMS) return known.hash;
      const hash = await compute();
      records.set(key, { fingerprint, hash, verifiedAt: now });
      return hash;
    },
    prune(keys) { for (const key of records.keys()) if (!keys.has(key)) records.delete(key); },
    drop(key) { records.delete(key); },
    size() { return records.size; },
  };
};

/* Volatile ring of state transitions. Never written to disk: SPEC.md's sitter
   section suppresses failures for the session "without a private durable ledger",
   and Zotero's own debug output is not durable either. What the ring buys is a
   hang readable after the fact, within the session that suffered it. */
var createSDTJournal = function (limit = 2000) {
  const records = [];
  return {
    push(record) { records.push(record); if (records.length > limit) records.shift(); },
    tail(n = limit) { return records.slice(Math.max(0, records.length - n)); },
  };
};

/* Quantiles of normalized observed durations, not calibrated prediction bounds. */
var sdtDurationFits = new WeakMap();
var estimateSDTDuration = function (samples, item) {
  if (samples.length < 3) return null;
  let fits = sdtDurationFits.get(samples);
  if (!fits) {
    fits = {};
    for (const field of ['pages', 'sourceBytes']) fits[field] = samples
      .filter(sample => sample[field] > 0 && sample.milliseconds > 0)
      .map(sample => sample.milliseconds / sample[field]).sort((a, b) => a - b);
    sdtDurationFits.set(samples, fits);
  }
  let key = 'pages';
  if (!(item.pages > 0) || fits.pages.length < 3) {
    key = 'sourceBytes';
  }
  const rates = fits[key];
  if (!(item[key] > 0) || rates.length < 3) return null;
  const q = p => {
    const offset = (rates.length - 1) * p, low = Math.floor(offset), high = Math.ceil(offset);
    return (rates[low] + (rates[high] - rates[low]) * (offset - low)) * item[key];
  };
  return { low: q(0.05), median: q(0.5), high: q(0.95), observations: rates.length, basis: key };
};
