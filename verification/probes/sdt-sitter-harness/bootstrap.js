/* Test driver only: admits synthetic attachments in a marked private profile. */
// `var`, not `let` — and not a style choice. Gecko can evaluate a bootstrapped
// add-on's bootstrap.js a second time into a scope that has already run it, and
// `const`/`let`/`class` refuse redeclaration where `var`/`function` tolerate it:
// the second load then dies at PARSE time, so `startup()` never runs, nothing is
// journalled, and the failure is silent and total. Tickets 0730 and 0741;
// tests/sdt_sitter_bootstrap.mjs holds every bootstrap.js in this tree to it.
var observer;
function startup() {
  const { setTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  setTimeout(() => run().catch(error => Zotero.logError(error)), 0);
}
async function run() {
  await Zotero.initializationPromise;
  const path = PathUtils.join(Zotero.DataDirectory.dir, 'sdt-sitter-smoke.json');
  if (!(await IOUtils.exists(path))) return;
  const config = await IOUtils.readJSON(path);
  if (config.dataDir !== Zotero.DataDirectory.dir || !config.allowDiagnostic) return;
  const { setTimeout, setInterval, clearInterval } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const report = { tests: [], version: Zotero.version, scope: 'isolated unmodified production sitter, synthetic attachments' };
  const save = () => IOUtils.writeJSON(config.output, report, { tmpPath: `${config.output}.tmp` });
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  let accepted = false;
  const acceptWindow = window => {
    const title = window.args?.title || window.document?.documentElement?.getAttribute('headertitle') || window.document?.title || '';
    if (!title.includes('Assistant d’indexation')) return;
    const dialog = window.document.querySelector('dialog');
    if (dialog?.getButton('accept')) { accepted = true; dialog.getButton('accept').click(); }
  };
  const acceptExisting = () => {
    const windows = Services.ww.getWindowEnumerator();
    while (windows.hasMoreElements()) acceptWindow(windows.getNext());
  };
  observer = {
    observe(window) {
      window.addEventListener('load', () => setTimeout(() => acceptWindow(window), 0), { once: true });
    },
  };
  Services.ww.registerNotification(observer);
  let ticks = 0;
  const promptPoll = setInterval(() => {
    acceptExisting();
    if (++ticks % 10 === 0) {
      report.lastState = Zotero.SDTPackSitter?.state || null;
      report.accepted = accepted;
      save().catch(error => Zotero.logError(error));
    }
  }, 100);
  // An enable after fixture creation provides deterministic addon startup order.
  const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
  try {
    const addon = await AddonManager.getAddonByID('sdt-pack-sitter@search-works-for-zotero.invalid');
    for (let i = 0; i < 600 && !accepted; i++) { acceptExisting(); await sleep(100); }
    assert(accepted, 'initial launch dialog was not observed');
    await addon.disable();
    const pdf = await Zotero.Attachments.importFromFile({ file: config.pdf });
    const epub = await Zotero.Attachments.importFromFile({ file: config.epub });
    const anotherPDF = await Zotero.Attachments.importFromFile({ file: config.pdf });
    await Zotero.uiReadyPromise;
    await addon.enable();
    for (let i = 0; i < 1200 && Zotero.SDTPackSitter?.state.completed !== 3; i++) { acceptExisting(); await sleep(100); }
    const api = Zotero.SDTPackSitter;
    assert(api, 'sitter API absent');
    assert(accepted, 'launch confirmation not accepted through UI');
    assert(api.state.completed === 3, JSON.stringify(api.state));
    assert(api.state.fittedSamples.length === 3, 'empirical fit was not refreshed');
    for (const item of [pdf, epub, anotherPDF]) assert((await api.inspect(item.id)).status === 'current', 'pack not current');
    report.tests.push({ name: 'confirmed automatic sweep produces native PDF and EPUB packs', result: 'pass' });
    const button = Zotero.getMainWindow().document.getElementById('sdt-pack-sitter-button');
    assert(button, 'toolbar absent');
    assert(button.getAttribute('label').includes('%'), 'toolbar does not show library coverage');
    assert(button.getBoundingClientRect().width >= 80, 'toolbar label constrained to icon width');
    button.doCommand();
    await sleep(1000);
    const windows = Services.ww.getWindowEnumerator(); let dialog;
    while (windows.hasMoreElements()) {
      const window = windows.getNext();
      if (window.document?.getElementById('sdt-status')) dialog = window;
    }
    assert(dialog?.document.getElementById('sdt-fulltext')?.textContent.includes('indexed'), 'native statistics absent');
    const globalBar = dialog.document.getElementById('sdt-global-progress');
    assert(globalBar?.closest('fieldset')?.id === 'sdt-global-section', 'global bar is not grouped');
    assert(globalBar.value === api.state.counts.current && globalBar.max === api.state.total,
      'global progress does not reflect verified pack coverage');
    assert(dialog.document.getElementById('sdt-progress')?.closest('fieldset')?.id === 'sdt-document-section', 'document bar is not separately grouped');
    report.tests.push({ name: 'global verified coverage and document progress have separate labelled groups', result: 'pass' });
    const surface = dialog.getComputedStyle(dialog.document.documentElement).backgroundColor;
    const foreground = dialog.getComputedStyle(dialog.document.documentElement).color;
    assert(surface.startsWith('rgb(') && surface !== foreground, `dialog surface or contrast invalid: ${surface}, ${foreground}`);
    assert(dialog.document.documentElement.style.colorScheme === 'light dark', 'system color scheme disabled');
    if (config.expectDark) {
      assert(dialog.matchMedia('(prefers-color-scheme: dark)').matches, 'dark system preference not propagated');
      const brightness = color => color.match(/\d+/g).slice(0, 3).map(Number).reduce((a, b) => a + b, 0);
      assert(brightness(surface) < brightness(foreground), 'dark system theme did not produce a dark surface');
    }
    assert(dialog.getComputedStyle(dialog.document.getElementById('sdt-status')).whiteSpace === 'pre-wrap', 'status lines do not wrap');
    report.tests.push({ name: 'toolbar has text width and dialog has opaque wrapping surface', result: 'pass',
      buttonWidth: button.getBoundingClientRect().width, surface, foreground,
      darkSystemTheme: dialog.matchMedia('(prefers-color-scheme: dark)').matches });
    report.tests.push({ name: 'toolbar opens status with native fulltext statistics', result: 'pass' });
    // Ticket 0693's layers, checked in a real window because that is the only
    // place `<details>` has its platform behaviour. Ticket 0686's keyboard items
    // must be verified against THIS layout, not re-approved from the old one, so
    // what can be established without synthesizing key events is asserted, and
    // the two readings a source review cannot take are recorded for it.
    const layerDoc = dialog.document;
    const layer2 = layerDoc.getElementById('sdt-details');
    const layer3 = layerDoc.getElementById('sdt-tech-details');
    assert(layer2 && layer3, 'a disclosure layer is absent');
    assert(layer3.parentNode === layer2, 'diagnostics is not nested inside the details layer');
    assert(!layer2.open && !layer3.open, 'a disclosure layer opens expanded');
    assert(layerDoc.body.firstElementChild.id === 'sdt-global-section' &&
      layerDoc.body.lastElementChild.id === 'sdt-details',
      'technical detail does not sit below primary progress');
    const debugToggle = layerDoc.getElementById('sdt-debug');
    assert(debugToggle && debugToggle.type === 'checkbox', 'the debug switch is not a native checkbox');
    assert(layerDoc.querySelector('label[for="sdt-debug"]'), 'the debug switch carries no bound label');
    // Focus, which the 0686 smoke could not establish: each summary must take it,
    // because that is what makes the layers reachable without a mouse.
    for (const disclosure of [layer2, layer3]) {
      const summary = disclosure.querySelector('summary');
      summary.focus();
      assert(layerDoc.activeElement === summary, `${disclosure.id} summary does not take focus`);
    }
    // Opening layer 3 with debug logging off is the acceptance criterion: the
    // ring is populated whatever the pref says, and only Zotero's debug output
    // is gated by it.
    Zotero.Prefs.set('extensions.sdt-pack-sitter.debug', false, true);
    layer2.open = true; layer3.open = true;
    await sleep(300);
    assert(layerDoc.getElementById('sdt-journal').textContent.includes('settle'),
      'the ring tail is empty with debug logging off');
    assert(layerDoc.getElementById('sdt-environment').textContent.includes(Zotero.version),
      'the diagnostics layer does not name the running host');
    layer2.open = false; layer3.open = false;
    report.tests.push({ name: 'diagnostics nests inside details, both closed, ring readable with debug off',
      result: 'pass',
      // Not assertions: reduced-motion is 0686's open item and this plugin does
      // not yet honour it. Recorded so the run produces the evidence rather than
      // leaving it to another reading of the source.
      reducedMotionPreferred: dialog.matchMedia('(prefers-reduced-motion: reduce)').matches,
      toolbarAccessibleName: button.getAttribute('label') });
    const firstDialog = dialog;
    button.doCommand();
    await sleep(100);
    let secondDialog;
    const reopened = Services.ww.getWindowEnumerator();
    while (reopened.hasMoreElements()) {
      const window = reopened.getNext();
      if (window.document?.getElementById('sdt-status')) secondDialog = window;
    }
    assert(secondDialog === firstDialog, 're-click created/replaced the status window');
    assert(secondDialog.document.getElementById('sdt-fulltext')?.textContent.includes('indexed'),
      're-click cleared the dialog contents');
    report.tests.push({ name: 're-click preserves the existing dialog contents', result: 'pass' });
    await addon.disable();
    assert(!Zotero.SDTPackSitter && !Zotero.getMainWindow().document.getElementById('sdt-pack-sitter-button'), 'disable left API or toolbar');
    assert(dialog.closed, 'disable left dialog');
    report.tests.push({ name: 'disable removes UI and API', result: 'pass' });
    await addon.enable();
    for (let i = 0; i < 600 && Zotero.SDTPackSitter?.state.scanned !== 3; i++) await sleep(100);
    await sleep(500);
    const restored = Zotero.SDTPackSitter;
    assert(restored.state.samples.length === 3 && restored.state.completed === 0,
      `observations did not survive reload: ${JSON.stringify(restored.state)}`);
    assert((await restored.inspect(pdf.id)).cached === true, 'verified census metadata was not cached');
    report.tests.push({ name: 'reload restores duration observations and reuses verified census cache without extraction', result: 'pass' });
    await addon.disable();
  } catch (error) { report.fatal = String(error); report.stack = error.stack; }
  finally { clearInterval(promptPoll); Services.ww.unregisterNotification(observer); observer = null; }
  report.finished = new Date().toISOString(); await save();
  Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
}
function shutdown() { if (observer) Services.ww.unregisterNotification(observer); }
function install() {}
function uninstall() {}
