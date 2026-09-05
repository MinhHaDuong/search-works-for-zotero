/* Independent controller: survives disabling/re-enabling the diagnostic addon. */
function startup() {
  const { setTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  // Zotero awaits addon startup serially. Do not wait for the other addon here.
  setTimeout(() => runHarness().catch(error => Zotero.logError(error)), 0);
}
async function runHarness() {
  await Zotero.initializationPromise;
  await Zotero.uiReadyPromise;
  const markerPath = PathUtils.join(Zotero.DataDirectory.dir, 'sdt-diagnostic.json');
  if (!(await IOUtils.exists(markerPath))) return;
  const config = await IOUtils.readJSON(markerPath);
  if (config.dataDir !== Zotero.DataDirectory.dir || !config.allowDiagnostic) return;
  const report = { scope: 'isolated real Zotero; synthetic PDF and EPUB; no production library',
    version: Zotero.version, tests: [], started: new Date().toISOString() };
  async function save() {
    await IOUtils.writeJSON(config.output, report, { tmpPath: `${config.output}.tmp` });
  }
  const { setTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  async function check(name, fn) {
    try { report.tests.push({ name, result: 'pass', detail: await fn() }); }
    catch (error) { report.tests.push({ name, result: 'fail', error: String(error), stack: error.stack }); }
    await save();
  }
  try {
    for (let i = 0; i < 100 && !Zotero.SDTSitterDiagnostic; i++) await sleep(100);
    assert(Zotero.SDTSitterDiagnostic, 'Diagnostic API never appeared');
    let api = Zotero.SDTSitterDiagnostic;
    await check('runtime resources and toolbar', async () => {
      const resources = await api.resources();
      assert(resources.directoryWritable && resources.diskFreeBytes > 0, 'storage unavailable');
      assert(Zotero.getMainWindow().document.getElementById('sdt-sitter-diagnostic-button'), 'toolbar absent');
      return resources;
    });
    const pdf = await Zotero.Attachments.importFromFile({ file: config.pdf });
    const epub = await Zotero.Attachments.importFromFile({ file: config.epub });
    await check('passive missing-pack inspection writes nothing', async () => {
      const first = await api.inspect(pdf.id);
      const second = await api.inspect(pdf.id);
      assert(first.status === 'missing-pack' && second.status === 'missing-pack', 'unexpected initial cache');
      assert(!(await IOUtils.exists(first.cachePath)), 'inspection wrote cache');
      return { status: second.status };
    });
    await check('PDF generation completes with native pack and progress', async () => {
      const result = await api.run(pdf.id);
      assert(result.ok && api.state.callbacks > 0, JSON.stringify(result));
      const pack = await api.inspect(pdf.id);
      return { result, callbacks: api.state.callbacks, progress: api.state.progress,
        packBytes: pack.packBytes, processor: pack.metadata.processor };
    });
    await check('cache-hit run and passive inspection do not rewrite', async () => {
      const first = await api.inspect(pdf.id);
      const hash = await Zotero.Utilities.Internal.md5Async(first.cachePath);
      const callbacks = api.state.callbacks;
      const result = await api.run(pdf.id);
      const last = await api.inspect(pdf.id);
      assert(result.cached && first.packMtime === last.packMtime && callbacks === api.state.callbacks, 'cache hit mutated');
      assert(hash === await Zotero.Utilities.Internal.md5Async(first.cachePath), 'pack bytes changed');
      return { cached: result.cached, packHash: hash };
    });
    await check('EPUB generation', async () => {
      const result = await api.run(epub.id);
      assert(result.ok, JSON.stringify(result));
      const reader = await Zotero.SDT.getReader(epub.id);
      assert(JSON.stringify((await reader.materialize()).content).includes('ZZFMTEPUB'), 'EPUB body token missing');
      return { ...result, bodyTokenPresent: true };
    });
    await check('corrupt disposable pack is reported then repaired', async () => {
      const pack = await api.inspect(pdf.id);
      await IOUtils.write(pack.cachePath, new TextEncoder().encode('invalid fixture cache'));
      assert((await api.inspect(pdf.id)).status === 'invalid-pack', 'corruption not detected');
      const result = await api.run(pdf.id);
      assert(result.ok, JSON.stringify(result)); return result;
    });
    await check('changed source makes a valid pack stale and regenerates', async () => {
      const before = await api.inspect(pdf.id);
      const bytes = await IOUtils.read(before.sourcePath);
      const changed = new Uint8Array(bytes.length + 1);
      changed.set(bytes); changed[bytes.length] = 10;
      await IOUtils.write(before.sourcePath, changed);
      assert((await api.inspect(pdf.id)).status === 'stale-source', 'source change missed');
      const result = await api.run(pdf.id); assert(result.ok, JSON.stringify(result));
      return result;
    });
    await check('invalid PDF failure is suppressed until source changes', async () => {
      const broken = await Zotero.Attachments.importFromFile({ file: config.pdf });
      const path = await broken.getFilePathAsync();
      const original = await IOUtils.read(path);
      await IOUtils.write(path, new TextEncoder().encode('not a PDF'));
      const first = await api.run(broken.id);
      assert(first.reason === 'native-failure', JSON.stringify(first));
      const callbacks = api.state.callbacks;
      const second = await api.run(broken.id);
      assert(second.reason === 'suppressed-for-session' && callbacks === api.state.callbacks,
        JSON.stringify(second));
      await IOUtils.write(path, original);
      const repaired = await api.run(broken.id); assert(repaired.ok, JSON.stringify(repaired));
      return { first, second, repaired };
    });
    await check('linked-file cache is in Zotero storage, not beside PDF', async () => {
      const linked = await Zotero.Attachments.linkFromFile({ file: config.pdf });
      const before = await api.inspect(linked.id);
      assert(PathUtils.parent(before.cachePath) !== PathUtils.parent(config.pdf), 'linked cache path wrong');
      const result = await api.run(linked.id); assert(result.ok, JSON.stringify(result));
      return { result, cacheInStorage: true };
    });
    await check('missing local file is refused before native generation', async () => {
      const missing = await Zotero.Attachments.importFromFile({ file: config.pdf });
      await IOUtils.remove(await missing.getFilePathAsync());
      const result = await api.run(missing.id);
      assert(result.reason === 'missing-source', JSON.stringify(result)); return result;
    });
    await check('native reader consumer shares valid pack', async () => {
      const reader = await Zotero.SDT.getReader(pdf.id, { isPriority: true });
      assert(reader, 'native reader absent');
      const structure = await reader.getCatalog();
      assert(JSON.stringify((await reader.materialize()).content).includes('ZZFMTPDF'), 'PDF body token missing');
      return { pages: structure.pages.length, bodyTokenPresent: true };
    });
    await check('actual addon disable and re-enable cleans API and toolbar', async () => {
      const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
      const addon = await AddonManager.getAddonByID('sdt-diagnostic@search-works-for-zotero.invalid');
      assert(addon, 'addon missing');
      const oldAPI = api;
      await addon.disable();
      for (let i = 0; i < 100 && Zotero.SDTSitterDiagnostic; i++) await sleep(50);
      assert(!Zotero.SDTSitterDiagnostic, 'API survived disable');
      assert(!Zotero.getMainWindow().document.getElementById('sdt-sitter-diagnostic-button'), 'button survived disable');
      await addon.enable();
      for (let i = 0; i < 100 && !Zotero.SDTSitterDiagnostic; i++) await sleep(50);
      api = Zotero.SDTSitterDiagnostic;
      assert(api && api !== oldAPI, 'fresh API absent');
      const result = await api.run(pdf.id); assert(result.ok && result.cached, 'cache lost on enable');
      return { cachedAfterEnable: result.cached };
    });
    await check('disable during native work suppresses callbacks but does not cancel pack', async () => {
      const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
      const addon = await AddonManager.getAddonByID('sdt-diagnostic@search-works-for-zotero.invalid');
      const long = await Zotero.Attachments.importFromFile({ file: config.multipage });
      const oldAPI = api;
      const pending = api.run(long.id);
      for (let i = 0; i < 1000 && oldAPI.state.progress === null; i++) await sleep(10);
      assert(oldAPI.state.active === long.id && oldAPI.state.progress !== null,
        'did not observe active native job; cannot claim in-flight disable');
      let readerCallbacks = 0;
      const readerPending = Zotero.SDT.getReader(long.id, {
        isPriority: true, onProgress: () => { readerCallbacks++; },
      });
      await addon.disable();
      const atDisable = oldAPI.state.callbacks;
      assert(!Zotero.SDTSitterDiagnostic, 'API survived disable');
      const result = await pending;
      const reader = await readerPending;
      assert(result.ok && result.disabledDuringRun, JSON.stringify(result));
      assert(oldAPI.state.callbacks === atDisable, 'callback mutated disabled plugin');
      assert(reader && readerCallbacks > 0, 'native concurrent consumer failed');
      await addon.enable();
      for (let i = 0; i < 100 && !Zotero.SDTSitterDiagnostic; i++) await sleep(50);
      api = Zotero.SDTSitterDiagnostic;
      assert(api && (await api.inspect(long.id)).status === 'current', 'completed pack missing');
      return { result, readerCallbacks, callbacksAtDisable: atDisable,
        callbacksAfterCompletion: oldAPI.state.callbacks };
    });
  } catch (error) { report.fatal = String(error); report.stack = error.stack; }
  report.finished = new Date().toISOString();
  await save();
  Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
}
function install() {}
function shutdown() {}
function uninstall() {}
