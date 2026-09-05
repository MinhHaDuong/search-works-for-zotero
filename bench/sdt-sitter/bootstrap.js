/* Experimental native SDT warmer. No endpoints, private ledger, or worker patch. */
var createSDTSitter;
var estimateSDTDuration;
let sitter, alive = false, timer, pulse, timers;
const buttons = new Set(), dialogs = new Set();
const BUTTON = 'sdt-pack-sitter-button';
let generation = 0;

function render() {
  if (!alive || !sitter) return;
  const s = sitter.state;
  for (const button of buttons) {
    button.setAttribute('label', s.active === null ? 'SDT' : `${['◐', '◓', '◑', '◒'][Math.floor(Date.now() / 1000) % 4]} SDT`);
    button.setAttribute('tooltiptext', `${s.phase} — ${s.completed} packs créés`);
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
    const mean = s.completed ? s.serviceMS / s.completed : null;
    const format = prediction => prediction ? [prediction.low, prediction.median, prediction.high]
      .map(ms => `${Math.round(ms / 1000).toLocaleString('fr-FR')} s`).join(' / ') : 'indisponible';
    const activePrediction = s.active === null ? null : estimateSDTDuration(s.fittedSamples, s.activeInfo);
    const total = { low: 0, median: 0, high: 0 };
    let unknown = 0;
    for (const item of s.pending) {
      const prediction = estimateSDTDuration(s.fittedSamples, item);
      if (!prediction) { unknown++; continue; }
      const spent = item.id === s.active ? Date.now() - s.startedAt : 0;
      for (const key of ['low', 'median', 'high']) total[key] += Math.max(0, prediction[key] - spent);
    }
    status.textContent = [
      `État : ${s.phase}`, `Recensement : ${s.scanned} / ${s.total} pièces jointes`,
      ...Object.entries(s.counts).map(([key, n]) => `${key} : ${n}`),
      `Créés cette session : ${s.completed} ; échecs : ${s.failed}`,
      s.active === null ? 'Aucun document en cours' : `Pièce jointe ${s.active} : ${s.progress ?? '?'} % ; ${elapsed} s ; dernier progrès il y a ${silence} s`,
      s.active === null ? '' : `Taille : ${s.activeInfo?.sourceBytes?.toLocaleString('fr-FR') ?? '?'} octets ; pages : ${s.activeInfo?.pages ?? '?'}`,
      'Un long silence peut correspondre à une résolution normale des citations.',
      mean ? `Vitesse empirique : ${(3600000 / mean).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} documents/h de traitement` : 'Vitesse : en attente du premier pack',
      `Durée totale du document actif, quantiles empiriques 5 / 50 / 95 % : ${format(activePrediction)}`,
      s.scanned === s.total && !unknown && s.fittedSamples.length >= 3
        ? `Travail total restant, scénarios bas / médian / haut : ${format(total)} (hors attentes)`
        : `Estimation totale indisponible : ${unknown || remaining} documents sans estimation ou recensement incomplet`,
      `Distribution : ${s.fittedSamples.length} observations ; mise à jour tous les 3 documents. Normalisation par pages, sinon octets.`,
      'Quantiles empiriques non calibrés. Les scénarios totaux ne sont pas un intervalle prédictif conjoint. Un dépassement ne signifie pas une panne.',
      s.error ? `Dernière erreur : ${s.error}` : '',
      'Désactiver dans les extensions arrête les admissions, pas le document en cours.',
    ].filter(Boolean).join('\n');
    const progress = doc.getElementById('sdt-progress');
    if (s.active !== null && Number.isFinite(s.progress)) progress.value = s.progress;
    else progress.removeAttribute('value');
  }
}

function openDialog(window) {
  const dialog = window.openDialog('about:blank', 'sdt-pack-sitter-status',
    'chrome,dialog=no,resizable,width=700,height=650');
  const populate = async () => {
    if (!alive || dialog.closed) return;
    const doc = dialog.document;
    doc.title = 'SDT Pack Sitter';
    const body = doc.body || doc.documentElement;
    body.replaceChildren();
    // A bare chrome about:blank window does not inherit Zotero's opaque surface.
    doc.documentElement.style.cssText = 'background: #f5f5f5; color: #202020; color-scheme: light; min-height: 100%;';
    body.style.cssText = 'background: #f5f5f5; color: #202020; margin: 0; padding: 16px; box-sizing: border-box; min-height: 100vh; font: menu;';
    for (const [tag, id] of [['pre', 'sdt-status'], ['progress', 'sdt-progress'], ['pre', 'sdt-fulltext']]) {
      const node = doc.createElementNS('http://www.w3.org/1999/xhtml', tag);
      node.id = id;
      if (tag === 'progress') { node.max = 100; node.style.width = '100%'; }
      else node.style.cssText = 'white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.5;';
      body.append(node);
    }
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
  const win = Zotero.getMainWindow();
  if (!win || typeof Zotero.SDT?.ensure !== 'function') throw new Error('Zotero 10 native SDT unavailable');
  const SDT = win.require('resource://zotero/document-worker/structured-document-text.js');
  const pako = win.require('pako');
  const versions = JSON.parse(await Zotero.File.getContentsFromURLAsync('resource://zotero/document-worker/metadata.json'));
  if (token !== generation) return;

  async function inspect(id) {
    const item = await Zotero.Items.getAsync(id);
    if (!item?.isAttachment() || item.deleted || (item.parentItemID && (await Zotero.Items.getAsync(item.parentItemID))?.deleted)) return { status: 'excluded' };
    const processor = item.isPDFAttachment() ? 'pdf' : item.isEPUBAttachment() ? 'epub' : item.isSnapshotAttachment() ? 'snapshot' : null;
    if (!processor) return { status: 'unsupported' };
    const sourcePath = await item.getFilePathAsync();
    if (!sourcePath || !(await IOUtils.exists(sourcePath))) return { status: 'missing-source' };
    const hash = await item.attachmentHash;
    const directory = Zotero.Attachments.getStorageDirectory(item).path;
    const path = PathUtils.join(directory, '.zotero-sdt-cache');
    const result = { status: 'missing-pack', directory,
      identity: `${item.libraryID}/${item.key}/${hash}/${JSON.stringify(versions)}` };
    result.sourceBytes = (await IOUtils.stat(sourcePath)).size;
    result.pages = processor === 'pdf' ? await Zotero.DB.valueQueryAsync(
      'SELECT totalPages FROM fulltextItems WHERE itemID = ?', [id]) : null;
    if (!(await IOUtils.exists(path))) return result;
    try {
      const stat = await IOUtils.stat(path);
      const reader = await SDT.openStructuredDocumentTextPack({ byteLength: stat.size,
        read: async (offset, length) => {
          const bytes = await IOUtils.read(path, { offset, maxBytes: length });
          return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        },
      }, { inflate: bytes => pako.inflateRaw(bytes) });
      const metadata = await reader.getMetadata();
      result.status = reader.header.packVersion !== versions.SDT_PACK_VERSION ||
        String(reader.header.schemaVersion).split('.')[0] !== versions.SDT_SCHEMA_VERSION.split('.')[0]
        ? 'unsupported-pack' : metadata.source?.hash !== hash ? 'stale-source'
          : metadata.processor?.type !== processor || metadata.processor?.version !== versions.SDT_PROCESSOR_VERSIONS[processor]
            ? 'stale-processor' : 'current';
    } catch (error) { result.status = 'invalid-pack'; }
    return result;
  }

  async function blocked(info) {
    if (!alive) return 'disabled';
    if (Zotero.PDFWorker?._processingQueue !== false || Zotero.PDFWorker?._queue?.length !== 0) return 'native-worker-busy';
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
    if (Zotero.PDFWorker._processingQueue || Zotero.PDFWorker._queue.length) return 'native-worker-busy';
    return null;
  }

  sitter = createSDTSitter({
    list: () => Zotero.DB.columnQueryAsync('SELECT itemID FROM itemAttachments ORDER BY itemID'),
    inspect, blocked, now: () => Date.now(), changed: render,
    yield: () => new Promise(resolve => timers.setTimeout(resolve, 0)),
    ensure: (id, onProgress) => Zotero.SDT.ensure(id, { isPriority: false, onProgress }),
  });
  alive = true;
  Zotero.SDTPackSitter = { state: sitter.state, inspect, blocked };
  for (const window of Zotero.getMainWindows()) onMainWindowLoad({ window });
  const launch = Services.prompt.confirm(win, 'SDT Pack Sitter — expérimental',
    'Préparer les packs SDT de toute la bibliothèque cette nuit ?\n\n' +
    'Un document à la fois, avec au moins 4 Gio de RAM disponible et 8 Gio de disque libre. ' +
    'Les PDF et les préférences d’indexation texte restent inchangés.\n\n' +
    'Le worker partagé ne peut être interrompu ni recevoir une priorité système indépendante. ' +
    'Un gros document peut retarder un travail natif arrivé ensuite. Les seuils ne plafonnent pas sa consommation.\n\n' +
    'Désactiver l’extension arrête les admissions ; le document en cours finit. ' +
    'Les erreurs et statistiques de session ne sont pas conservées au redémarrage.');
  if (token !== generation) return;
  if (!launch) { sitter.state.phase = 'launch-declined; disable/re-enable to launch'; render(); return; }
  const sweep = async () => {
    await sitter.sweep();
    if (alive && token === generation) timer = timers.setTimeout(sweep, 30000);
  };
  pulse = timers.setInterval(render, 1000);
  timer = timers.setTimeout(sweep, 0);
}
function shutdown() {
  ++generation; alive = false; sitter?.stop();
  if (timers) { timers.clearTimeout(timer); timers.clearInterval(pulse); }
  for (const button of buttons) button.remove();
  buttons.clear();
  for (const dialog of dialogs) if (!dialog.closed) dialog.close();
  dialogs.clear();
  delete Zotero.SDTPackSitter;
}
function install() {}
function uninstall() {}
