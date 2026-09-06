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
  failed: ['failed-session', 'inspection-error', 'unsupported-pack', 'missing-source'],
  // Not indexed yet. Exactly the statuses admission accepts, and nothing else.
  queued: ['missing-pack', 'stale-source', 'stale-processor', 'invalid-pack'],
  // Not the sitter's business: trashed or not an attachment, or no processor exists.
  outOfScope: ['excluded', 'unsupported'],
};

/* Host-independent admission loop. Native ensure owns extraction and persistence. */
var createSDTSitter = function (host) {
  const state = { enabled: true, phase: 'ready', active: null, progress: null,
    lastProgressAt: null, startedAt: null, completed: 0, failed: 0,
    scanned: 0, total: 0, counts: {}, serviceMS: 0, samples: [], activeInfo: null,
    fittedSamples: [], pending: [], error: null, cacheWarning: null };
  const failed = new Set();
  let busy = false;
  // Derived from the census, never accumulated beside it. `state.counts` is rebuilt
  // at the head of every sweep, so a counter incremented alongside it drifts by one
  // sweep's failures every pass and the banner slowly overstates a library that
  // never changed. Recomputed on every publish, which is every counts mutation.
  //
  // And only once the census is whole. A total read from a half-filled `counts`
  // counts only what has been scanned so far, so an ungated derivation would blank
  // the banner at the top of every sweep and refill it as the scan ran — the same
  // silence this ticket removed, arriving every thirty seconds instead of
  // permanently. Until the scan closes, the last complete census's figure stands;
  // it is the last thing actually known. This is the predicate `getSDTCoverage`
  // already publishes as `known`, and the reason the coverage line carries it.
  const publish = () => {
    if (state.scanned === state.total) {
      state.failed = SDT_STATUS_CLASSES.failed
        .reduce((n, key) => n + (state.counts[key] || 0), 0);
    }
    if (state.enabled) host.changed(state);
  };
  return {
    state,
    stop() { state.enabled = false; },
    async sweep() {
      if (!state.enabled || busy) return;
      busy = true;
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
          try {
            const ok = await host.ensure(id, progress => {
              if (!state.enabled) return;
              state.progress = progress; state.lastProgressAt = host.now();
              if (host.emit) host.emit('progress', { id, progress }, 'trace');
              publish();
            });
            if (!state.enabled) break;
            const after = await host.inspect(id);
            if (!state.enabled) break;
            if (!ok || after.status !== 'current') throw new Error('Native SDT did not persist a current pack');
            state.completed++; state.serviceMS += host.now() - state.startedAt;
            state.samples.push({ sourceBytes: before.sourceBytes, pages: before.pages,
              milliseconds: host.now() - state.startedAt });
            if (host.emit) host.emit('settle',
              { id, ok: true, ms: state.samples[state.samples.length - 1].milliseconds });
            // Contained on purpose. `inspect()` has just verified a current pack, so
            // the attachment IS indexed; the observation that follows only writes a
            // duration into a store SPEC.md calls derived and disposable. Letting it
            // reach the catch below turned a verified success into a failure and
            // blacklisted the source by identity, so no later sweep retried it either.
            if (host.observed) {
              try { await host.observed(before, state.samples[state.samples.length - 1]); }
              // Contained, not silent: a swallow with no surface at all is how a
              // cache that has stopped recording durations looks exactly like one
              // that is working. No detail travels — the throw can come from the
              // platform, and a platform message names whatever it failed on
              // (bootstrap.js's classifyError carries the argument in full).
              catch (_error) { if (host.emit) host.emit('observe-failed', { id }, 'trace'); }
            }
            if (state.samples.length % 3 === 0) state.fittedSamples = state.samples.slice();
            state.counts[status]--; state.counts.current = (state.counts.current || 0) + 1;
          } catch (error) {
            if (!state.enabled) break;
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
      } finally { busy = false; publish(); }
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
