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
  failed: ['failed-session', 'inspection-error', 'unsupported-pack', 'missing-source'],
  // Not indexed yet. Exactly the statuses admission accepts, and nothing else.
  queued: ['missing-pack', 'stale-source', 'stale-processor', 'invalid-pack'],
  // Not the sitter's business: trashed or not an attachment, or no processor exists.
  outOfScope: ['excluded', 'unsupported'],
};

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
    censusSnapshot: null };
  const failed = new Set();
  // Publish one complete census generation at a time. `state.counts` is rebuilt
  // from empty on every sweep and remains useful as live diagnostics, but no UI
  // total may combine that half-filled generation with a total held from the last
  // one. The copied object is one atomic assignment; after the census closes, each
  // admission settlement refreshes it so the next sweep holds the latest complete
  // state rather than the pre-admission census. Ticket 0718.
  const publish = () => {
    if (state.scanned === state.total) {
      const counts = { ...state.counts };
      state.censusSnapshot = { counts, total: state.total };
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
  return {
    state,
    stop() { state.enabled = false; },
    /* stop()'s twin, for the user's own switch (ticket 0742). Before it, the
       only way back from a stopped sitter was a fresh createSDTSitter() — which
       throws away the census, the counters and the fitted samples, so turning
       indexing off and on again would have re-walked the whole library and lost
       every duration observed in the session.

       The phase is reset only from 'switched-off', the state this switch itself
       sets. A sitter stopped mid-extraction leaves `phase` stale at
       'extracting' (see `busy` above), and overwriting that here would erase
       the one trace of how it stopped; the next sweep sets the phase anyway. */
    start() {
      state.enabled = true;
      if (state.phase === 'switched-off') state.phase = 'ready';
    },
    async sweep() {
      if (!state.enabled || state.busy) return;
      state.busy = true;
      // The sweep's own boundaries. Without them a sweep that died silently and a
      // sweep that never started again look identical in the ring, which is the
      // trace ticket 0702's failure mode left behind: none at all.
      if (host.emit) host.emit('sweep-start', {}, 'trace');
      try {
        state.phase = 'census'; state.scanned = 0; state.counts = {};
        const ids = await host.list();
        if (!state.enabled) return;
        state.total = ids.length; publish();
        const candidates = [];
        for (const id of ids) {
          if (!state.enabled) break;
          await host.yield();
          if (!state.enabled) break;
          let before;
          try { before = await host.inspect(id); }
          catch (error) { before = { status: 'inspection-error', error: String(error) }; }
          if (!state.enabled) break;
          state.scanned++;
          let status = before.status;
          if (before.identity && failed.has(before.identity)) status = 'failed-session';
          state.counts[status] = (state.counts[status] || 0) + 1;
          publish();
          if (!SDT_STATUS_CLASSES.queued.includes(status)) continue;
          candidates.push({ id, before, status });
        }
        // Both titles travel with the queue. The attachment's own title is usually
        // auto-generated ('Full Text PDF'), so the UI needs the parent reference to
        // name anything a reader recognises.
        // Kept apart from state.pending, which drains as documents settle. What
        // the caller's poll interval needs is what this census FOUND, and by the
        // end of the sweep pending says nothing about it (ticket 0701).
        state.candidates = candidates.length;
        state.pending = candidates.map(({ id, before }) => ({ id, title: before.title ?? null,
          parentTitle: before.parentTitle ?? null, sourceBytes: before.sourceBytes, pages: before.pages }));
        if (state.enabled && host.censusComplete) {
          state.samples = await host.censusComplete();
          state.fittedSamples = state.samples.slice();
        }
        publish();
        for (const { id, before, status } of candidates) {
          await host.yield();
          if (!state.enabled) break;
          const reason = await host.blocked(before);
          if (!state.enabled) break;
          // Journalled beside the halt rather than inside it, so the halt stays the
          // one line verification/probes/sdt_sitter_scheduler_mutants.py anchors M4
          // on. Queueing behind the native worker is the designed resting state,
          // not a refusal; it repeats every sweep, so it is trace and never state.
          if (reason && host.emit) {
            const idle = reason === 'native-worker-busy';
            host.emit(idle ? 'worker-idle-wait' : 'refuse', { reason }, idle ? 'trace' : 'state');
          }
          if (reason) { state.phase = reason; publish(); break; }
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
            if (!ok || after.status !== 'current') throw new Error('Native SDT did not persist a current pack');
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
            state.counts[status]--; state.counts.current = (state.counts.current || 0) + 1;
          } catch (error) {
            failed.add(before.identity);
            state.error = host.describeError ? host.describeError(before, error) : String(error);
            if (host.reportError) await host.reportError(before, error);
            state.counts[status]--; state.counts['failed-session'] = (state.counts['failed-session'] || 0) + 1;
          } finally {
            state.active = null;
            state.pending = state.pending.filter(item => item.id !== id);
          }
          publish();
        }
        if (state.enabled && state.phase === 'extracting') state.phase = 'waiting';
        else if (state.enabled && state.phase === 'census') state.phase = 'waiting';
      } catch (error) {
        if (state.enabled) { state.phase = 'error'; state.error = String(error); }
      // sweep-end goes out BEFORE the last publish, because publish is the one
      // call in this finally that can still throw out of sweep(): the record of
      // how the sweep ended must not be lost to the thing that ended it.
      } finally {
        state.busy = false;
        if (host.emit) host.emit('sweep-end',
          { phase: state.phase, scanned: state.scanned, completed: state.completed,
            failed: state.failed, pending: state.pending.length }, 'trace');
        publish();
      }
    },
  };
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
      records[key] = { signature, fingerprint, pages: info.pages, sourceBytes: info.sourceBytes };
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
