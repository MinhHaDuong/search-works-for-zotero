/* Experimental native SDT warmer. No endpoints, private ledger, or worker patch. */
var createSDTSitter;
var estimateSDTDuration;
var createSDTCache;
var createSDTJournal;
var createSDTSourceHashes;
// `var`, not `let`: the journal and the sitter are the state the scheduler test
// drives this file's emit/heartbeat/shutdown against, and only `var` reaches the
// script global a sandboxed load exposes.
var sitter, journal, alive = false, sealed = false;
// Same reason: the render guard's test drives a torn-down dialog through this
// set and resets the latch between cases, and neither a `const` nor a `let` at
// script top level reaches the sandbox global — the assignment silently lands on
// an unrelated property instead, and the reset reads as though it worked.
var buttons = new Set(), dialogs = new Set(), renderFailing = false;
let timer, pulse, heartbeat, timers;
const closeJournalled = new WeakSet();
const BUTTON = 'sdt-pack-sitter-button';
const SWEEP_INTERVAL_MS = 30000;
const IDLE_SWEEP_INTERVAL_MS = 10 * 60 * 1000;
const DEBUG_PREF = 'extensions.sdt-pack-sitter.debug';
// Bootstrap reason constants are numeric here and named elsewhere; accept both.
const SHUTDOWN_REASONS = { 2: 'app-shutdown', 3: 'enable', 4: 'disable',
  5: 'install', 6: 'uninstall', 7: 'upgrade', 8: 'downgrade' };
let generation = 0;
let lastCompleted = 0;
let completionBlinkUntil = 0;

/* The sitter's whole diagnostic channel. Until the seal, the ring takes
   everything; Zotero.debug() takes everything but trace, which waits on the
   pref. The whole body is guarded: the invariant is that no diagnostic ever
   throws into the sitter loop, and a `detail` the ring rejects must not
   either. */
function emit(kind, detail, level = 'state') {
  // Sealed at shutdown, so nothing can land behind the shutdown record — an
  // invariant of the channel rather than a guard each call site has to remember.
  // Anything that resumes after an await outlives disable: the cache write, the
  // native promise, a dialog's unload.
  if (sealed) return;
  try {
    journal?.push({ at: Date.now(), kind, level, ...detail });
    // Fully qualified pref name: `true` stops Zotero prepending `extensions.zotero.`.
    if (level === 'trace' && !Zotero.Prefs.get(DEBUG_PREF, true)) return;
    Zotero.debug(`SDT sitter ${kind} ${JSON.stringify(detail ?? {})}`);
  } catch (_error) { /* Diagnostics must never throw into the sitter loop. */ }
}

/* The error's class reaches the journal; its message never does. Message text is
   free prose written by the platform, and it carries whatever it happens to name:
   a Gecko IO failure carries the file's full path, a parse failure carries the
   attachment's title. Zotero's debug output is submittable to Zotero's servers,
   so this is not session-confined. Three successive attempts to scrub that prose
   token by token each leaked — a stored filename is "Author - Year - Title.pdf",
   several whitespace-separated words of which a pattern anchored on runs of
   non-whitespace can only ever redact the one touching the extension. Prose and
   filenames are not separable by pattern, so the message is not carried at all.
   describeError still shows the author everything, on screen, locally, where it
   is his own library he is reading. The name is validated rather than trusted:
   a name with a space or a separator in it is a message wearing a name's clothes,
   and the whole body is guarded because a torn-down compartment can throw from
   a getter — this runs outside emit()'s guard, as its argument. */
function classifyError(error) {
  try {
    const name = error && error.name;
    return typeof name === 'string' && /^[\w.$-]{1,64}$/.test(name) ? name : 'Error';
  } catch (_error) {
    return '<unreadable error>';
  }
}

/* A beat for every phase the sitter can hang in, not only the one with a document
   under the worker. Ticket 0703: the census, host.list() and the whole blocked()
   admission check all run with `active` null, so the previous `active === null`
   gate was silent for precisely the phases whose hang left no trace after
   `cache-load`. `busy` is the scheduler's own outer-finally flag, so it goes
   false the instant sweep() exits — including the abort path, where `phase`
   stays stale at 'extracting'. The two ages are null-guarded because they are
   the age of a document, and during census there is none. */
function heartbeatTick() {
  if (!alive || !sitter) return;
  const s = sitter.state;
  if (!s.busy && s.active === null) return;
  const age = since => (since == null ? null : Date.now() - since);
  emit('heartbeat', { id: s.active, phase: s.phase, progress: s.progress,
    elapsedMS: age(s.startedAt), sinceProgressMS: age(s.lastProgressAt),
    pending: s.pending.length }, 'trace');
}

/* How long before the next census. Ticket 0701: a library with nothing left to
   index was re-censused every 30 seconds, all night, and every census walked the
   whole item table. A sweep that ended `waiting` having found no candidate found
   nothing to react to, so the next look is a floor poll rather than a work queue.

   A floor rather than a notifier subscription, deliberately: the poll is the
   robust half either way, and 10 minutes is 20x fewer wake-ups while still
   picking up a newly added attachment within one coffee. `candidates`, not
   `pending`: pending drains as documents settle, so by the end of a productive
   sweep it is empty too, and the two cases are not the same one. */
function nextSweepDelayMS(state) {
  return state.phase === 'waiting' && state.candidates === 0
    ? IDLE_SWEEP_INTERVAL_MS : SWEEP_INTERVAL_MS;
}

/* The failure half of settle. It goes to the session ring and Zotero.debug(),
   never to a file, for the reason createSDTJournal carries. The identity is the
   opaque cache key, never the attachment's title. */
function reportSettleFailure(info, error) {
  emit('settle', { id: info.cacheKey ?? null, ok: false, error: classifyError(error) }, 'error');
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

/* Every phase a reader can meet on hover, in the user's vocabulary. A blocked or
   failed sitter must be distinguishable from a healthy idle one at zero clicks,
   so each blocking reason gets its own plain sentence; the raw internal name
   stays in the diagnostics disclosure. `null` is the deliberate no-label case:
   the two healthy idle phases, where the count already says everything. An
   unlisted phase falls back to the bare count rather than leaking its name. */
var SDT_PHASE_LABELS = {
  ready: null,
  waiting: null,
  census: 'Recensement',
  extracting: 'Indexation en cours',
  error: 'Erreur',
  disabled: 'Désactivé',
  'native-worker-busy': 'En attente : indexation native en cours',
  'cpu-busy': 'En pause : processeur occupé',
  'low-memory': 'En pause : mémoire insuffisante',
  'low-disk': 'En pause : espace disque insuffisant',
  'storage-unavailable': 'En pause : stockage indisponible',
  'resources-unavailable': 'En pause : ressources système illisibles',
  'launch-declined; disable/re-enable to launch': 'Non lancé : désactiver puis réactiver l’extension',
};

function describeSDTTooltip(state) {
  const indexed = state.completed > 1
    ? `${state.completed} fichiers indexés` : `${state.completed} fichier indexé`;
  const label = SDT_PHASE_LABELS[state.phase];
  return label ? `${label} — ${indexed}` : indexed;
}

/* The unit of work is one attachment, and Zotero names attachments for us
   ('Full Text PDF', 'Snapshot'), so the attachment title alone identifies
   nothing. Lead with the reference that owns it. One composer, so the progress
   line and the error line cannot drift into naming the same file two ways. */
function describeSDTFile(info, fallback) {
  const { parentTitle, title } = info || {};
  if (parentTitle && title) return `${parentTitle} — ${title}`;
  return parentTitle || title || fallback;
}

function describeSDTActiveFile(state) {
  return describeSDTFile(state.activeInfo, `fichier n° ${state.active}`);
}

/* Ticket 0702. renderState() runs unguarded DOM work over `dialogs`, and it is
   reached from publish(), which the scheduler calls from inside its own finally.
   A throw there — a dead XUL dialog after its window closed, getElementById
   returning null mid-render — rejected sitter.sweep(), so the wrapper that
   reschedules the next sweep never ran and the sitter stopped for the rest of
   the session while `phase` still read 'waiting'. Indistinguishable from working.

   The failure is recorded on its transition, not on its tick: the pulse calls
   this at 10 Hz, and a persistent broken dialog emitting every time would evict
   the whole 2000-record ring in under four minutes — destroying exactly the
   evidence ticket 0703 keeps. */
function render() {
  try {
    renderState();
    renderFailing = false;
  } catch (error) {
    if (renderFailing) return;
    renderFailing = true;
    emit('render-error', { error: classifyError(error) }, 'error');
  }
}

function renderState() {
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
      ? `${['◐', '◓', '◑', '◒'][Math.floor(now / 140) % 4]} Index${coverageLabel}` : `Index${coverageLabel}`);
    const opacity = s.phase === 'census'
      ? 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(now / 450))
      : blinking ? ((Math.floor(now / 180) % 2) ? 0.2 : 1) : 1;
    button.style.setProperty('opacity', String(opacity), 'important');
    button.setAttribute('tooltiptext', describeSDTTooltip(s));
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
    status.textContent = coverage.known ? `Fichiers indexés : ${coverage.current} / ${coverage.total}` : `Fichiers indexés : ${coverage.current}`;
    const activeMessage = s.active === null ? 'Aucune indexation en cours' :
      `Indexation : ${describeSDTActiveFile(s)} — ${s.progress ?? '?'} % — ${formatDocumentDuration(elapsed * 1000)} écoulées`;
    const quietMessage = s.active !== null && Number(s.progress) >= 90 && silence >= 60
      ? (Number(s.progress) >= 95 ? 'Finalisation…' : 'Analyse des références…') : '';
    doc.getElementById('sdt-document-status').textContent = [activeMessage, quietMessage].filter(Boolean).join('\n');
    doc.getElementById('sdt-document-estimate').textContent = activePrediction
      ? `Durée estimée : ${formatDocumentDuration(activePrediction.median)} (entre ${formatDocumentDuration(activePrediction.low)} et ${formatDocumentDuration(activePrediction.high)})` : '';
    const globalEstimate = !overrun && s.scanned === s.total && s.fittedSamples.length >= 3
      ? `Fin estimée vers ${finishAt(total.median)} (entre ${finishAt(total.low)} et ${finishAt(total.high)})` : '';
    doc.getElementById('sdt-global-estimate').textContent = globalEstimate;
    // Failures were reachable only by opening the diagnostics. Surface the count.
    doc.getElementById('sdt-failures').textContent = s.failed === 0 ? ''
      : s.failed > 1 ? `${s.failed} fichiers n’ont pas pu être indexés`
        : `${s.failed} fichier n’a pas pu être indexé`;
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
    doc.title = 'Assistant d’indexation';
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
      ['pre', 'sdt-status'], ['progress', 'sdt-global-progress'], ['pre', 'sdt-global-estimate'],
      ['pre', 'sdt-failures']]);
    section('sdt-document-section', 'Indexation en cours', [
      ['pre', 'sdt-document-status'], ['progress', 'sdt-progress'], ['pre', 'sdt-document-estimate']]);
    const details = element('details', 'sdt-details');
    const summary = element('summary', 'sdt-details-title');
    summary.textContent = 'Détails';
    details.append(summary, element('pre', 'sdt-diagnostics'));
    const indexDetails = element('details', 'sdt-index-details');
    const indexSummary = element('summary', 'sdt-index-title');
    indexSummary.textContent = 'Index de recherche textuelle';
    indexDetails.append(indexSummary, element('pre', 'sdt-fulltext'));
    details.append(indexDetails); body.append(details);
    dialogs.add(dialog); render();
    try {
      const stats = await Zotero.Fulltext.getIndexStats();
      if (alive && !dialog.closed) doc.getElementById('sdt-fulltext').textContent =
        `Index de recherche textuelle de Zotero (distinct de l’index préparé par l’assistant) :\n${JSON.stringify(stats, null, 2)}`;
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
/* Ticket 0688. The plugin "tends to disappear on its own from the installed-plugins
   list" and left nothing behind saying which build was running when it did. Raw
   values, no compatibility-range parsing: `strict_max_version` against
   `Zotero.version` is exactly the comparison the host already made, and a second
   verdict here could only disagree with it.

   Every read is guarded, because this runs as an ARGUMENT to emit() and therefore
   outside emit()'s own guard — the hazard classifyError() above carries for the
   same reason. `JSON.parse` of a document that is not an object is the case the
   first draft missed (`null` and `3` parse, then read wrong or throw), and
   `Zotero.version` is a getter that runs code in a compartment this plugin does
   not own. A diagnosis must never be the thing that stops startup. */
async function sitterStartupSelfCheck(rootURI) {
  let manifest = null;
  try {
    manifest = JSON.parse(await Zotero.File.getContentsFromURLAsync(rootURI + 'manifest.json'));
  } catch (error) { manifest = { version: `unreadable (${classifyError(error)})` }; }
  if (!manifest || typeof manifest !== 'object') manifest = { version: `unreadable (${typeof manifest})` };
  const application = (manifest.applications && manifest.applications.zotero) || {};
  let zoteroVersion = '<unreadable>';
  try { zoteroVersion = Zotero.version; } catch (_error) { /* A getter can throw. */ }
  return { version: manifest.version, rootURI, zoteroVersion,
    strictMinVersion: application.strict_min_version,
    strictMaxVersion: application.strict_max_version };
}
async function initialize(rootURI, token) {
  await Zotero.initializationPromise;
  // First thing after the host is up, and before any of the work below can throw:
  // a disappearance that leaves no `startup` record happened earlier than this
  // point. It goes through 0689's channel rather than a Zotero.debug() of its own
  // — one diagnostic channel, already guarded, already sealed at shutdown. The
  // ring is not up yet (scheduler.js loads below), so this record reaches the
  // debug log only; that is the half a vanished plugin leaves behind anyway.
  try {
    emit('startup', await sitterStartupSelfCheck(rootURI));
  } catch (_error) { /* Diagnostics must never throw into startup. */ }
  await Zotero.uiReadyPromise;
  if (token !== generation) return;
  Services.scriptloader.loadSubScript(rootURI + 'scheduler.js', globalThis);
  // `??=`: a re-initialization within one Zotero session keeps the transitions
  // that led to it. A real plugin unload tears this scope down and takes the ring
  // with it; surviving that needs a durable store, which the ruling forbids.
  journal ??= createSDTJournal();
  // A second handle, under a name shutdown never deletes. The natural recovery
  // from a hang is disable/re-enable, and disable removes Zotero.SDTPackSitter —
  // which was the only way in to the ring, so the recovery action destroyed the
  // evidence of what it was recovering from (ticket 0703). Republished in
  // shutdown()'s finally as well, so the guarantee holds for a session whose
  // initialize() never got this far.
  Zotero.SDTPackSitterJournal = journal;
  sealed = false;
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
  // In memory, never on disk: the pack cache above carries claims worth keeping
  // across sessions, and a source hash is reconstructible from the file itself.
  const sourceHashes = createSDTSourceHashes();
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
        // This one resumes after an await, so disable can land under it. The seal
        // in shutdown() is what keeps it off the far side of the shutdown record.
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
    if (!sourcePath) return { status: 'missing-source' };
    // One stat where there were an exists() and a stat(): it answers both
    // questions at once, and its (size, lastModified) is what lets the MD5 below
    // be skipped on a file nothing has touched since the last census.
    let source;
    try { source = await IOUtils.stat(sourcePath); }
    catch (_error) { return { status: 'missing-source' }; }
    const cacheKey = `${item.libraryID}/${item.key}`;
    const hash = await sourceHashes.hash(cacheKey, sourcePath, source, () => item.attachmentHash);
    const directory = Zotero.Attachments.getStorageDirectory(item).path;
    const path = PathUtils.join(directory, '.zotero-sdt-cache');
    const [title, parentTitle] = await Promise.all([getItemTitle(item), getItemTitle(parent)]);
    const result = { status: 'missing-pack', directory,
      title: title || sourcePath.split(/[\\/]/).pop(),
      parentTitle: parentTitle || null,
      identity: `${item.libraryID}/${item.key}/${hash}/${JSON.stringify(versions)}` };
    result.cacheKey = cacheKey;
    seen.add(result.cacheKey);
    result.sourceBytes = source.size;
    result.pages = processor === 'pdf' ? await Zotero.DB.valueQueryAsync(
      'SELECT totalPages FROM fulltextItems WHERE itemID = ?', [id]) : null;
    // The same collapse as the source file above, in the same census walk: this
    // exists() and the stat() that followed it asked one file one question.
    // An absent pack takes the branch it always took. One case does move: a pack
    // present but unstattable (permissions) now reads 'missing-pack' where it
    // read 'invalid-pack'. Both re-extract, so only the diagnostic bucket
    // differs, and 'missing-pack' is the truer of the two for a file the
    // filesystem will not describe.
    let stat;
    try { stat = await IOUtils.stat(path); }
    catch (_error) { cache.drop(result.cacheKey); return result; }
    try {
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
    censusComplete: async () => {
      cache.prune(seen); sourceHashes.prune(seen); await saveCache(); return cache.samples();
    },
    observed: async (info, sample) => { cache.observe(info.cacheKey, info.identity, sample); await saveCache(); },
    inspect, blocked, now: () => Date.now(), changed: render,
    // 0691's on-screen wording, this ticket's journal: describeError still shows
    // the author the file and the full error text, locally, and the failure that
    // reaches the journal is what replaced the retired on-disk error ledger.
    describeError: (info, error) =>
      `Échec de « ${describeSDTFile(info, 'fichier inconnu')} » : ${String(error)}`,
    reportError: reportSettleFailure,
    emit,
    yield: () => new Promise(resolve => timers.setTimeout(resolve, 0)),
    ensure: (id, onProgress) => Zotero.SDT.ensure(id, { isPriority: false, onProgress }),
  });
  alive = true;
  Zotero.SDTPackSitter = { state: sitter.state, inspect, blocked, journal };
  for (const window of Zotero.getMainWindows()) onMainWindowLoad({ window });
  const launch = Services.prompt.confirm(win, 'Assistant d’indexation — expérimental',
    'Indexer toute la bibliothèque cette nuit ?\n\n' +
    'Un fichier à la fois, avec au moins 4 Gio de RAM disponible et 8 Gio de disque libre. ' +
    'Les PDF et les préférences de l’index de recherche textuelle restent inchangés.\n\n' +
    'Le worker partagé ne peut être interrompu ni recevoir une priorité système indépendante. ' +
    'Un gros fichier peut retarder un travail natif arrivé ensuite. Les seuils ne plafonnent pas sa consommation.\n\n' +
    'Désactiver l’extension arrête les admissions ; le fichier en cours finit. ' +
    'Les erreurs restent propres à la session. Un cache local jetable conserve les vérifications et durées ; il ne contient ni texte ni tâche active.');
  if (token !== generation) return;
  if (!launch) { sitter.state.phase = 'launch-declined; disable/re-enable to launch'; render(); return; }
  // Defence in depth behind render()'s own guard. The reschedule is the single
  // point whose loss stops the sitter for the session, so it does not depend on
  // the sweep having returned normally — nor on this file being the only place a
  // throw can come from.
  const sweep = async () => {
    try {
      await sitter.sweep();
    } catch (error) {
      emit('sweep-error', { error: classifyError(error) }, 'error');
    } finally {
      if (alive && token === generation) {
        timer = timers.setTimeout(sweep, nextSweepDelayMS(sitter.state));
      }
    }
  };
  pulse = timers.setInterval(render, 100);
  heartbeat = timers.setInterval(heartbeatTick, 60000);
  timer = timers.setTimeout(sweep, 0);
}
function shutdown(data, reason) {
  // try/finally, because the teardown between here and the seal calls out to the
  // platform: dialog.close() during app shutdown is a real throw site, and a
  // shutdown that throws halfway would otherwise leave the channel open and write
  // no record — losing the evidence at exactly the moment disable is being used
  // to recover from a hang. The throw still propagates; the record is not lost.
  try {
    ++generation; alive = false; sitter?.stop();
    if (timers) { timers.clearTimeout(timer); timers.clearInterval(pulse); timers.clearInterval(heartbeat); }
    for (const button of buttons) button.remove();
    buttons.clear();
    for (const dialog of dialogs) if (!dialog.closed) { noteDialogClose(dialog); dialog.close(); }
    dialogs.clear();
    delete Zotero.SDTPackSitter;
  } finally {
    emit('shutdown', { reason: typeof reason === 'number' ? SHUTDOWN_REASONS[reason] || `reason-${reason}`
      : reason ? String(reason).toLowerCase().replace(/^addon[_-]/, '').replace(/_/g, '-') : 'unknown' });
    sealed = true;
    // The shutdown record is the last thing written, and this is what keeps the
    // ring holding it reachable afterwards. Guarded for the same reason emit()
    // is: a teardown already halfway through a throw must not acquire a second.
    try { if (journal) Zotero.SDTPackSitterJournal = journal; } catch (_error) { /* Nothing. */ }
  }
}
function install() {}
function uninstall() {}
