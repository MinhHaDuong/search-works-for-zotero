function startup() {
  const { setTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  setTimeout(() => run().catch(error => Zotero.logError(error)), 0);
}
async function run() {
  await Zotero.initializationPromise;
  await Zotero.uiReadyPromise;
  const path = PathUtils.join(Zotero.DataDirectory.dir, 'sdt-diagnostic.json');
  if (!(await IOUtils.exists(path))) return;
  const config = await IOUtils.readJSON(path);
  if (!config.allowDiagnostic || config.dataDir !== Zotero.DataDirectory.dir || !config.phaseProbe) return;
  const { setTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const report = { key: config.key, pagesRequested: config.pages, version: Zotero.version,
    started: Date.now(), phases: [], progress: [], scope: 'isolated modified worker, native SDT path' };
  let writes = Promise.resolve();
  const save = () => {
    const json = JSON.stringify(report);
    writes = writes.then(() => IOUtils.write(config.output, new TextEncoder().encode(json),
      { tmpPath: `${config.output}.tmp` }));
    return writes;
  };
  let listener;
  try {
    for (let i = 0; i < 100 && !Zotero.SDTSitterDiagnostic; i++) await sleep(100);
    const api = Zotero.SDTSitterDiagnostic;
    if (!api) throw new Error('Diagnostic API unavailable');
    report.resources = await api.resources();
    const item = await Zotero.Attachments.linkFromFile({ file: config.input });
    Zotero.PDFWorker._init();
    listener = event => {
      if (event.data.sdtProbe) {
        report.phases.push(event.data.sdtProbe);
        save().catch(error => Zotero.logError(error));
      }
    };
    Zotero.PDFWorker._worker.addEventListener('message', listener);
    report.before = { status: (await api.inspect(item.id)).status };
    report.dispatched = Date.now(); await save();
    // Same native entry point as the prototype; separate progress evidence.
    report.ok = await Zotero.SDT.ensure(item.id, { isPriority: false, onProgress: value => {
      report.progress.push({ time: Date.now(), value }); save().catch(error => Zotero.logError(error));
    } });
    report.persisted = Date.now();
    if (report.ok) {
      const after = await api.inspect(item.id);
      const reader = await Zotero.SDT.getReader(item.id);
      const catalog = await reader.getCatalog();
      const count = reader.getTopLevelBlockCount();
      const last = count ? await reader.getBlock([count - 1]) : null;
      report.pack = { status: after.status, bytes: after.packBytes,
        hash: await Zotero.Utilities.Internal.md5Async(after.cachePath),
        metadata: after.metadata, pages: catalog.pages.length, blocks: count,
        degradedPages: catalog.pages.filter(page => page.extractionDegraded).length,
        lastBlockReadable: !!last, lastBlockPageRects: last?.anchor?.pageRects ?? null };
      if (report.pack.pages !== config.expectedPages) throw new Error('Unexpected catalog page count');
    }
  } catch (error) { report.error = String(error); report.stack = error.stack; }
  finally {
    if (listener) Zotero.PDFWorker._worker.removeEventListener('message', listener);
    report.finished = Date.now(); await save();
    Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
  }
}
function install() {}
function shutdown() {}
function uninstall() {}
