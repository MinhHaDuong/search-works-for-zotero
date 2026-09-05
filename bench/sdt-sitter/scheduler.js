/* Host-independent admission loop. Native ensure owns extraction and persistence. */
var createSDTSitter = function (host) {
  const state = { enabled: true, phase: 'ready', active: null, progress: null,
    lastProgressAt: null, startedAt: null, completed: 0, failed: 0,
    scanned: 0, total: 0, counts: {}, serviceMS: 0, samples: [], activeInfo: null,
    fittedSamples: [], pending: [], error: null };
  const failed = new Set();
  let busy = false;
  const publish = () => { if (state.enabled) host.changed(state); };
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
          if (!['missing-pack', 'stale-source', 'stale-processor', 'invalid-pack'].includes(status)) continue;
          candidates.push({ id, before, status });
        }
        state.pending = candidates.map(({ id, before }) => ({ id, sourceBytes: before.sourceBytes, pages: before.pages }));
        publish();
        for (const { id, before, status } of candidates) {
          await host.yield();
          if (!state.enabled) break;
          const reason = await host.blocked(before);
          if (!state.enabled) break;
          if (reason) { state.phase = reason; publish(); break; }
          state.active = id; state.startedAt = host.now();
          state.activeInfo = { sourceBytes: before.sourceBytes, pages: before.pages };
          state.lastProgressAt = state.startedAt; state.progress = null;
          state.phase = 'extracting'; publish();
          try {
            const ok = await host.ensure(id, progress => {
              if (!state.enabled) return;
              state.progress = progress; state.lastProgressAt = host.now(); publish();
            });
            if (!state.enabled) break;
            const after = await host.inspect(id);
            if (!state.enabled) break;
            if (!ok || after.status !== 'current') throw new Error('Native SDT did not persist a current pack');
            state.completed++; state.serviceMS += host.now() - state.startedAt;
            state.samples.push({ sourceBytes: before.sourceBytes, pages: before.pages,
              milliseconds: host.now() - state.startedAt });
            if (state.samples.length % 3 === 0) state.fittedSamples = state.samples.slice();
            state.counts[status]--; state.counts.current = (state.counts.current || 0) + 1;
          } catch (error) {
            if (!state.enabled) break;
            failed.add(before.identity); state.failed++; state.error = String(error);
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

/* Quantiles of normalized observed durations, not calibrated prediction bounds. */
var estimateSDTDuration = function (samples, item) {
  if (samples.length < 3) return null;
  let key = 'pages';
  let usable = samples.filter(sample => sample.pages > 0 && sample.milliseconds > 0);
  if (!(item.pages > 0) || usable.length < 3) {
    key = 'sourceBytes';
    usable = samples.filter(sample => sample.sourceBytes > 0 && sample.milliseconds > 0);
  }
  if (!(item[key] > 0) || usable.length < 3) return null;
  const rates = usable.map(sample => sample.milliseconds / sample[key]).sort((a, b) => a - b);
  const q = p => {
    const offset = (rates.length - 1) * p, low = Math.floor(offset), high = Math.ceil(offset);
    return (rates[low] + (rates[high] - rates[low]) * (offset - low)) * item[key];
  };
  return { low: q(0.05), median: q(0.5), high: q(0.95), observations: usable.length, basis: key };
};
