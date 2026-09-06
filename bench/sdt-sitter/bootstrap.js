/* Experimental native SDT warmer. No endpoints, private ledger, or worker patch. */
var createSDTSitter;
var estimateSDTDuration;
var createSDTCache;
var createSDTJournal;
// `var`, not `let`: the journal and the sitter are the state the scheduler test
// drives this file's emit/heartbeat/shutdown against, and only `var` reaches the
// script global a sandboxed load exposes.
var sitter, journal, alive = false;
let timer, pulse, heartbeat, timers;
const buttons = new Set(), dialogs = new Set(), closeJournalled = new WeakSet();
const BUTTON = 'sdt-pack-sitter-button';
const DEBUG_PREF = 'extensions.sdt-pack-sitter.debug';
// Bootstrap reason constants are numeric here and named elsewhere; accept both.
const SHUTDOWN_REASONS = { 2: 'app-shutdown', 3: 'enable', 4: 'disable',
  5: 'install', 6: 'uninstall', 7: 'upgrade', 8: 'downgrade' };
let generation = 0;
let lastCompleted = 0;
let completionBlinkUntil = 0;

/* The sitter's whole diagnostic channel. The ring always records; Zotero.debug()
   is the readable one and carries everything but trace unless the pref is set. */
function emit(kind, detail, level = 'state') {
  journal?.push({ at: Date.now(), kind, level, ...detail });
  try {
    // Fully qualified pref name: `true` stops Zotero prepending `extensions.zotero.`.
    if (level === 'trace' && !Zotero.Prefs.get(DEBUG_PREF, true)) return;
    Zotero.debug(`SDT sitter ${kind} ${JSON.stringify(detail ?? {})}`);
  } catch (_error) { /* Diagnostics must never throw into the sitter loop. */ }
}

function heartbeatTick() {
  if (!alive || !sitter || sitter.state.active === null) return;
  const s = sitter.state;
  emit('heartbeat', { id: s.active, phase: s.phase, progress: s.progress,
    elapsedMS: Date.now() - s.startedAt, sinceProgressMS: Date.now() - s.lastProgressAt,
    pending: s.pending.length }, 'trace');
}

/* The failure half of settle. It goes to the session ring and Zotero.debug(),
   never to a file, for the reason createSDTJournal carries. The identity is the
   opaque cache key, never the attachment's title. */
function reportSettleFailure(info, error) {
  emit('settle', { id: info.cacheKey ?? null, ok: false, error: String(error) }, 'error');
}

function noteDialogClose(dialog) {
  // `close()` may dispatch unload after shutdown has run; record it once, in order.
  if (closeJournalled.has(dialog)) return;
  closeJournalled.add(dialog);
  emit('dialog-close', {});
}

function getSDTCoverage(state) {
  return { known: state.scanned === state.total && state.phase !== 'ready',
    current: state.counts.current || 0,
    total: Math.max(0, state.total - (state.counts.excluded || 0) - (state.counts.unsupported || 0)) };
}

function render() {
  if (!alive || !sitter) return;
  const s = sitter.state;
  const coverage = getSDTCoverage(s);
  const coverageLabel = coverage.total > 0
    ? ` ${Math.floor((coverage.current / coverage.total) * 100)} %` : '';
  for (const button of buttons) {
    const working = s.phase === 'census' || s.active !== null;
    const now = Date.now();
    if (s.completed > lastCompleted) {
      lastCompleted = s.completed;
      completionBlinkUntil = now + 1400;
    }
    const spinning = s.active !== null;
    const blinking = !working && now < completionBlinkUntil;
    button.setAttribute('label', spinning
      ? `${['◐', '◓', '◑', '◒'][Math.floor(now / 140) % 4]} SDT${coverageLabel}` : `SDT${coverageLabel}`);
    const opacity = s.phase === 'census'
      ? 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(now / 450))
      : blinking ? ((Math.floor(now / 180) % 2) ? 0.2 : 1) : 1;
    button.style.setProperty('opacity', String(opacity), 'important');
    button.setAttribute('tooltiptext', `${s.phase === 'census' ? 'Recensement' : s.phase} — ${s.completed} packs créés`);
  }
  for (const dialog of dialogs) {
    if (dialog.closed) { dialogs.delete(dialog); continue; }
    const doc = dialog.document;
    const status = doc.getElementById('sdt-status');
    if (!status) continue;
    const elapsed = s.active === null ? null : Math.round((Date.now() - s.startedAt) / 1000);
    const silence = s.active === null ? null : Math.round((Date.now() - s.lastProgressAt) / 1000);
    const remaining = ['missing-pack', 'stale-source', 'stale-processor', 'invalid-pack']
      .reduce((n, key) => n + (s.counts[key] || 0), 0);
    const formatDuration = ms => {
      const minutes = Math.max(1, Math.round(ms / 60000));
      return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
    };
    const formatDocumentDuration = ms => {
      const seconds = Math.max(0, Math.round(ms / 1000));
      if (seconds < 60) return `${seconds} s`;
      return `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, '0')} s`;
    };
    const format = prediction => prediction ?
      `Durée estimée : ${formatDuration(prediction.median)} (entre ${formatDuration(prediction.low)} et ${formatDuration(prediction.high)})` : '';
    const activePrediction = s.active === null ? null : estimateSDTDuration(s.fittedSamples, s.activeInfo);
    const total = { low: 0, median: 0, high: 0 };
    const overrun = activePrediction && Date.now() - s.startedAt > activePrediction.high;
    const finishAt = ms => new Date(Date.now() + ms).toLocaleString('fr-FR',
      { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    let unknown = 0;
    for (const item of s.pending) {
      const prediction = estimateSDTDuration(s.fittedSamples, item);
      if (!prediction) { unknown++; continue; }
      const spent = item.id === s.active ? Date.now() - s.startedAt : 0;
      for (const key of ['low', 'median', 'high']) total[key] += Math.max(0, prediction[key] - spent);
    }
    if (unknown && s.fittedSamples.length >= 3) {
      const durations = s.fittedSamples.map(sample => sample.milliseconds).sort((a, b) => a - b);
      const quantile = fraction => durations[Math.min(durations.length - 1,
        Math.floor((durations.length - 1) * fraction))];
      total.low += unknown * quantile(0.05);
      total.median += unknown * quantile(0.5);
      total.high += unknown * quantile(0.95);
    }
    const globalProgress = doc.getElementById('sdt-global-progress');
    globalProgress.max = Math.max(1, coverage.total);
    if (coverage.known) globalProgress.value = coverage.current;
    else globalProgress.removeAttribute('value');
    status.textContent = coverage.known ? `Packs à jour : ${coverage.current} / ${coverage.total}` : `Packs à jour : ${coverage.current}`;
    const documentMessage = s.active === null ? 'Aucun document en cours' :
      `Document ${s.active} — ${s.progress ?? '?'} % — ${formatDocumentDuration(elapsed * 1000)} écoulées`;
    const quietMessage = s.active !== null && Number(s.progress) >= 90 && silence >= 60
      ? (Number(s.progress) >= 95 ? 'Finalisation…' : 'Analyse des références…') : '';
    doc.getElementById('sdt-document-status').textContent = [documentMessage, quietMessage].filter(Boolean).join('\n');
    doc.getElementById('sdt-document-estimate').textContent = activePrediction
      ? `Durée estimée : ${formatDocumentDuration(activePrediction.median)} (entre ${formatDocumentDuration(activePrediction.low)} et ${formatDocumentDuration(activePrediction.high)})` : '';
    const globalEstimate = !overrun && s.scanned === s.total && s.fittedSamples.length >= 3
      ? `Fin estimée vers ${finishAt(total.median)} (entre ${finishAt(total.low)} et ${finishAt(total.high)})` : '';
    doc.getElementById('sdt-global-estimate').textContent = globalEstimate;
    doc.getElementById('sdt-diagnostics').textContent = [
      `État : ${s.phase}`, `Recensement : ${s.scanned} / ${s.total}`,
      ...Object.entries(s.counts).map(([key, n]) => `${key} : ${n}`),
      `Créés cette session : ${s.completed} ; échecs : ${s.failed}`,
      s.error ? `Erreur : ${s.error}` : '',
    ].filter(Boolean).join('\n');
    const progress = doc.getElementById('sdt-progress');
    progress.hidden = s.active === null;
    if (s.active !== null && Number.isFinite(s.progress)) progress.value = s.progress;
    else progress.removeAttribute('value');
  }
}

function openDialog(window) {
  for (const existing of dialogs) {
    if (!existing.closed) {
      existing.focus();
      emit('dialog-open', { reused: true });
      render();
      return existing;
    }
    dialogs.delete(existing);
  }
  const dialog = window.openDialog('about:blank', 'sdt-pack-sitter-status',
    'chrome,dialog=no,resizable,width=700,height=650');
  emit('dialog-open', { reused: false });
  dialog.addEventListener('unload', () => { dialogs.delete(dialog); noteDialogClose(dialog); }, { once: true });
  const populate = async () => {
    if (!alive || dialog.closed) return;
    const doc = dialog.document;
    doc.title = 'SDT Pack Sitter';
    const body = doc.body || doc.documentElement;
    body.replaceChildren();
    // A bare chrome about:blank window does not inherit Zotero's opaque surface.
    doc.documentElement.style.cssText = 'background: Canvas; color: CanvasText; color-scheme: light dark; min-height: 100%;';
    body.style.cssText = 'background: Canvas; color: CanvasText; margin: 0; padding: 16px; box-sizing: border-box; min-height: 100vh; font: menu;';
    const element = (tag, id) => {
      const node = doc.createElementNS('http://www.w3.org/1999/xhtml', tag);
      node.id = id;
      if (tag === 'progress') { node.max = 100; node.style.width = '100%'; }
      else node.style.cssText = 'white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.5;';
      return node;
    };
    const section = (id, title, children) => {
      const group = element('fieldset', id);
      group.style.cssText = 'border: 1px solid GrayText; border-radius: 6px; padding: 12px; margin: 0 0 16px; min-width: 0;';
      const legend = element('legend', `${id}-title`);
      legend.textContent = title; legend.style.fontWeight = 'bold';
      group.append(legend);
      for (const [tag, childID] of children) {
        const node = element(tag, childID);
        if (tag === 'progress') node.setAttribute('aria-labelledby', legend.id);
        group.append(node);
      }
      body.append(group);
    };
    section('sdt-global-section', 'Progression globale — bibliothèque', [
      ['pre', 'sdt-status'], ['progress', 'sdt-global-progress'], ['pre', 'sdt-global-estimate']]);
    section('sdt-document-section', 'Document en cours', [
      ['pre', 'sdt-document-status'], ['progress', 'sdt-progress'], ['pre', 'sdt-document-estimate']]);
    const details = element('details', 'sdt-details');
    const summary = element('summary', 'sdt-details-title');
    summary.textContent = 'Détails';
    details.append(summary, element('pre', 'sdt-diagnostics'));
    const indexDetails = element('details', 'sdt-index-details');
    const indexSummary = element('summary', 'sdt-index-title');
    indexSummary.textContent = 'Index texte natif';
    indexDetails.append(indexSummary, element('pre', 'sdt-fulltext'));
    details.append(indexDetails); body.append(details);
    dialogs.add(dialog); render();
    try {
      const stats = await Zotero.Fulltext.getIndexStats();
      if (alive && !dialog.closed) doc.getElementById('sdt-fulltext').textContent =
        `Index texte natif (distinct des packs SDT) :\n${JSON.stringify(stats, null, 2)}`;
    } catch (error) {
      if (alive && !dialog.closed) doc.getElementById('sdt-fulltext').textContent = `Statistiques indisponibles : ${error}`;
    }
  };
  if (dialog.document.readyState === 'complete') populate();
  else dialog.addEventListener('load', populate, { once: true });
}

function onMainWindowLoad({ window }) {
  if (!alive || window.document.getElementById(BUTTON)) return;
  const toolbar = window.document.getElementById('zotero-items-toolbar');
  if (!toolbar) return;
  const button = window.document.createXULElement('toolbarbutton');
  button.id = BUTTON;
  // Zotero's toolbar styles otherwise constrain this to an icon-sized square.
  button.style.setProperty('min-width', '80px', 'important');
  button.style.setProperty('width', 'auto', 'important');
  button.style.setProperty('max-width', 'none', 'important');
  button.style.setProperty('flex-shrink', '0', 'important');
  button.style.setProperty('padding-inline', '8px', 'important');
  button.addEventListener('command', () => openDialog(window));
  toolbar.append(button); buttons.add(button); render();
}
function onMainWindowUnload({ window }) {
  for (const button of buttons) if (button.ownerDocument === window.document) {
    button.remove(); buttons.delete(button);
  }
}

function startup({ rootURI }) {
  const token = ++generation;
  timers = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  // Addon startup is serialized. Never hold it on UI readiness or a modal prompt.
  timer = timers.setTimeout(() => initialize(rootURI, token).catch(error => Zotero.logError(error)), 0);
}
async function initialize(rootURI, token) {
  await Zotero.initializationPromise;
  await Zotero.uiReadyPromise;
  if (token !== generation) return;
  Services.scriptloader.loadSubScript(rootURI + 'scheduler.js', globalThis);
  journal = createSDTJournal();
  const win = Zotero.getMainWindow();
  if (!win || typeof Zotero.SDT?.ensure !== 'function') throw new Error('Zotero 10 native SDT unavailable');
  const SDT = win.require('resource://zotero/document-worker/structured-document-text.js');
  const pako = win.require('pako');
  const versions = JSON.parse(await Zotero.File.getContentsFromURLAsync('resource://zotero/document-worker/metadata.json'));
  if (token !== generation) return;
  const cachePath = PathUtils.join(Zotero.DataDirectory.dir, 'sdt-sitter-cache.jsonl');
  await Zotero.SDTPackSitterCacheWrite?.catch(() => {});
  const raw = { format: 1, versions: JSON.stringify(versions), records: Object.create(null) };
  try {
    for (const line of (await IOUtils.readUTF8(cachePath)).split('\n')) {
      try {
        const row = JSON.parse(line);
        if (row.versions !== raw.versions || typeof row.key !== 'string') continue;
        if (row.record) raw.records[row.key] = row.record;
        else delete raw.records[row.key];
      } catch (error) { /* Ignore incomplete/corrupt cache rows. */ }
    }
  } catch (error) { /* Disposable cache. */ }
  const cache = createSDTCache(raw, JSON.stringify(versions));
  emit('cache-load', { records: Object.keys(raw.records).length });
  let seen = new Set();
  let compact = true;
  const saveCache = async () => {
    const previous = Zotero.SDTPackSitterCacheWrite || Promise.resolve();
    const write = previous.catch(() => {}).then(async () => {
      if (!alive || token !== generation) return;
      const changes = cache.changes(compact);
      if (!compact && !changes.length) return;
      const bytes = new TextEncoder().encode(changes.map(change => JSON.stringify({ versions: raw.versions, ...change })).join('\n') + '\n');
      try {
        // Compact once per activation; subsequent writes contain changed rows only.
        await IOUtils.write(cachePath, bytes, compact ? { tmpPath: `${cachePath}.tmp` } : { mode: 'append' });
        cache.saved(changes);
        emit('cache-write', { rows: changes.length, compact });
        compact = false;
      }
      catch (error) { if (alive) sitter.state.cacheWarning = `Cache non enregistré : ${error}`; }
    });
    Zotero.SDTPackSitterCacheWrite = write;
    await write;
  };
  if (token !== generation) return;

  const getItemTitle = async item => {
    if (!item) return null;
    try {
      if (typeof item.loadData === 'function') await item.loadData();
      return item.getField('title') || item.getDisplayTitle?.() || null;
    } catch (_error) {
      return null;
    }
  };

  async function inspect(id) {
    const item = await Zotero.Items.getAsync(id);
    if (!item?.isAttachment() || item.deleted) return { status: 'excluded' };
    const parent = item.parentItemID ? await Zotero.Items.getAsync(item.parentItemID) : null;
    if (parent?.deleted) return { status: 'excluded' };
    const processor = item.isPDFAttachment() ? 'pdf' : item.isEPUBAttachment() ? 'epub' : item.isSnapshotAttachment() ? 'snapshot' : null;
    if (!processor) return { status: 'unsupported' };
    const sourcePath = await item.getFilePathAsync();
    if (!sourcePath || !(await IOUtils.exists(sourcePath))) return { status: 'missing-source' };
    const hash = await item.attachmentHash;
    const directory = Zotero.Attachments.getStorageDirectory(item).path;
    const path = PathUtils.join(directory, '.zotero-sdt-cache');
    const [title, parentTitle] = await Promise.all([getItemTitle(item), getItemTitle(parent)]);
    const result = { status: 'missing-pack', directory,
      title: title || sourcePath.split(/[\\/]/).pop(),
      parentTitle: parentTitle || null,
      identity: `${item.libraryID}/${item.key}/${hash}/${JSON.stringify(versions)}` };
    result.cacheKey = `${item.libraryID}/${item.key}`;
    seen.add(result.cacheKey);
    result.sourceBytes = (await IOUtils.stat(sourcePath)).size;
    result.pages = processor === 'pdf' ? await Zotero.DB.valueQueryAsync(
      'SELECT totalPages FROM fulltextItems WHERE itemID = ?', [id]) : null;
    if (!(await IOUtils.exists(path))) { cache.drop(result.cacheKey); return result; }
    try {
      const stat = await IOUtils.stat(path);
      const fingerprint = JSON.stringify([stat.size, stat.lastModified]);
      const cached = cache.check(result.cacheKey, result.identity, fingerprint);
      if (cached) return { ...result, status: 'current', cached: true };
      const reader = await SDT.openStructuredDocumentTextPack({ byteLength: stat.size,
        read: async (offset, length) => {
          const bytes = await IOUtils.read(path, { offset, maxBytes: length });
          return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        },
      }, { inflate: bytes => pako.inflateRaw(bytes) });
      const metadata = await reader.getMetadata();
      const packVersionMismatch = reader.header.packVersion !== versions.SDT_PACK_VERSION ||
        String(reader.header.schemaVersion).split('.')[0] !== versions.SDT_SCHEMA_VERSION.split('.')[0];
      const sourceMismatch = metadata.source?.hash !== hash;
      const processorMismatch = metadata.processor?.type !== processor ||
        metadata.processor?.version !== versions.SDT_PROCESSOR_VERSIONS[processor];
      if (packVersionMismatch) result.status = 'unsupported-pack';
      else if (sourceMismatch) result.status = 'stale-source';
      else if (processorMismatch) result.status = 'stale-processor';
      else result.status = 'current';
      if (result.status === 'current') cache.remember(result.cacheKey, result.identity, fingerprint, result);
      else cache.drop(result.cacheKey);
    } catch (error) { result.status = 'invalid-pack'; }
    return result;
  }

  const workerBusy = () => Zotero.PDFWorker?._processingQueue !== false || Zotero.PDFWorker?._queue?.length !== 0;
  async function blocked(info) {
    if (!alive) return 'disabled';
    if (workerBusy()) return 'native-worker-busy';
    try {
      // procfs reports a zero stat size. Read its tiny generated streams, not
      // IOUtils' regular-file size-based path. No library file uses this sync path.
      const memory = Zotero.File.getContents('/proc/meminfo');
      const available = Number(memory.match(/^MemAvailable:\s+(\d+) kB$/m)?.[1]) * 1024;
      if (!Number.isFinite(available)) return 'resources-unavailable';
      if (available < 4 * 1024 ** 3) return 'low-memory';
      const load = Number(Zotero.File.getContents('/proc/loadavg').split(' ')[0]);
      const cpus = win.navigator.hardwareConcurrency;
      if (!Number.isFinite(load) || !cpus) return 'resources-unavailable';
      if (load >= cpus) return 'cpu-busy';
      let directory = info.directory;
      while (!(await IOUtils.exists(directory))) {
        const parent = PathUtils.parent(directory);
        if (parent === directory) return 'storage-unavailable';
        directory = parent;
      }
      const file = Zotero.File.pathToFile(directory);
      if (!file.isWritable()) return 'storage-unavailable';
      if (file.diskSpaceAvailable < 8 * 1024 ** 3) return 'low-disk';
    } catch (error) {
      if (alive && sitter) sitter.state.error = `Lecture des ressources : ${error}`;
      return 'resources-unavailable';
    }
    // Recheck after async resource reads; never deliberately queue behind native work.
    if (!alive) return 'disabled';
    if (workerBusy()) return 'native-worker-busy';
    return null;
  }

  sitter = createSDTSitter({
    list: () => { seen = new Set(); return Zotero.DB.columnQueryAsync('SELECT itemID FROM itemAttachments ORDER BY itemID'); },
    censusComplete: async () => { cache.prune(seen); await saveCache(); return cache.samples(); },
    observed: async (info, sample) => { cache.observe(info.cacheKey, info.identity, sample); await saveCache(); },
    inspect, blocked, now: () => Date.now(), changed: render,
    describeError: (info, error) => {
      const parent = info.parentTitle ? ` — élément : « ${info.parentTitle} »` : '';
      return `Échec de « ${info.title || 'pièce jointe inconnue'} »${parent} : ${String(error)}`;
    },
    reportError: reportSettleFailure,
    emit,
    yield: () => new Promise(resolve => timers.setTimeout(resolve, 0)),
    ensure: (id, onProgress) => Zotero.SDT.ensure(id, { isPriority: false, onProgress }),
  });
  alive = true;
  Zotero.SDTPackSitter = { state: sitter.state, inspect, blocked, journal };
  for (const window of Zotero.getMainWindows()) onMainWindowLoad({ window });
  const launch = Services.prompt.confirm(win, 'SDT Pack Sitter — expérimental',
    'Préparer les packs SDT de toute la bibliothèque cette nuit ?\n\n' +
    'Un document à la fois, avec au moins 4 Gio de RAM disponible et 8 Gio de disque libre. ' +
    'Les PDF et les préférences d’indexation texte restent inchangés.\n\n' +
    'Le worker partagé ne peut être interrompu ni recevoir une priorité système indépendante. ' +
    'Un gros document peut retarder un travail natif arrivé ensuite. Les seuils ne plafonnent pas sa consommation.\n\n' +
    'Désactiver l’extension arrête les admissions ; le document en cours finit. ' +
    'Les erreurs restent propres à la session. Un cache local jetable conserve les vérifications et durées ; il ne contient ni texte ni tâche active.');
  if (token !== generation) return;
  if (!launch) { sitter.state.phase = 'launch-declined; disable/re-enable to launch'; render(); return; }
  const sweep = async () => {
    await sitter.sweep();
    if (alive && token === generation) timer = timers.setTimeout(sweep, 30000);
  };
  pulse = timers.setInterval(render, 100);
  heartbeat = timers.setInterval(heartbeatTick, 60000);
  timer = timers.setTimeout(sweep, 0);
}
function shutdown(data, reason) {
  ++generation; alive = false; sitter?.stop();
  if (timers) { timers.clearTimeout(timer); timers.clearInterval(pulse); timers.clearInterval(heartbeat); }
  for (const button of buttons) button.remove();
  buttons.clear();
  for (const dialog of dialogs) if (!dialog.closed) { noteDialogClose(dialog); dialog.close(); }
  dialogs.clear();
  delete Zotero.SDTPackSitter;
  emit('shutdown', { reason: typeof reason === 'number' ? SHUTDOWN_REASONS[reason] || `reason-${reason}`
    : reason ? String(reason).toLowerCase().replace(/^addon[_-]/, '').replace(/_/g, '-') : 'unknown' });
}
function install() {}
function uninstall() {}
