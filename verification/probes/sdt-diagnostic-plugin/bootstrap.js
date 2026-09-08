/* Diagnostic only. Refuses startup without an isolated-arena marker.
 * Never installs an HTTP endpoint or admits work automatically.
 */
// `var` throughout, and not a style choice. Gecko can evaluate a bootstrapped
// add-on's bootstrap.js a second time into a scope that has already run it, and
// `const`/`let`/`class` refuse redeclaration where `var`/`function` tolerate it:
// the second load then dies at PARSE time, so `startup()` never runs, nothing is
// journalled, and the failure is silent and total. Tickets 0730 and 0741;
// tests/sdt_sitter_bootstrap.mjs holds every bootstrap.js in this tree to it.
var api;
var enabled = false;
var buttons = new Set();
var BUTTON = 'sdt-sitter-diagnostic-button';

function refreshButtons() {
  for (const button of buttons) {
    button.setAttribute('label', api?.state.active ? 'SDT …' : 'SDT');
    button.setAttribute('tooltiptext', JSON.stringify(api?.state ?? {}));
  }
}
function addButton(window) {
  if (!enabled || window.document.getElementById(BUTTON)) return;
  const toolbar = window.document.getElementById('zotero-items-toolbar');
  if (!toolbar) return;
  const button = window.document.createXULElement('toolbarbutton');
  button.id = BUTTON;
  button.addEventListener('command', () => {
    Services.prompt.alert(window, 'SDT diagnostic', JSON.stringify(api.state, null, 2));
  });
  toolbar.append(button);
  buttons.add(button);
  refreshButtons();
}

async function startup() {
  await Zotero.initializationPromise;
  await Zotero.uiReadyPromise;
  const markerPath = PathUtils.join(Zotero.DataDirectory.dir, 'sdt-diagnostic.json');
  if (!(await IOUtils.exists(markerPath))) return;
  const marker = await IOUtils.readJSON(markerPath);
  if (marker.dataDir !== Zotero.DataDirectory.dir || marker.allowDiagnostic !== true) return;
  const { setTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  for (let i = 0; i < 100 && !Zotero.getMainWindow(); i++) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  const requireModule = Zotero.getMainWindow().require;
  const SDT = requireModule('resource://zotero/document-worker/structured-document-text.js');
  const pako = requireModule('pako');
  const versions = JSON.parse(await Zotero.File.getContentsFromURLAsync(
    'resource://zotero/document-worker/metadata.json'));
  if (typeof Zotero.SDT?.ensure !== 'function') throw new Error('Native SDT.ensure unavailable');
  enabled = true;
  const failures = new Map();
  const state = { active: null, last: null, progress: null, callbacks: 0 };

  async function inspect(itemID) {
    const item = await Zotero.Items.getAsync(itemID);
    if (!item?.isAttachment()) return { status: 'unsupported' };
    const processor = item.isPDFAttachment() ? 'pdf' : item.isEPUBAttachment()
      ? 'epub' : item.isSnapshotAttachment() ? 'snapshot' : null;
    if (!processor) return { status: 'unsupported' };
    const sourcePath = await item.getFilePathAsync();
    if (!sourcePath || !(await IOUtils.exists(sourcePath))) return { status: 'missing-source' };
    const hash = await item.attachmentHash;
    const identity = `${item.libraryID}/${item.key}/${hash}/${JSON.stringify(versions)}`;
    const directory = Zotero.Attachments.getStorageDirectory(item);
    const cachePath = PathUtils.join(directory.path, '.zotero-sdt-cache');
    const result = { identity, cachePath, sourcePath, status: 'missing-pack' };
    if (!(await IOUtils.exists(cachePath))) return result;
    try {
      const info = await IOUtils.stat(cachePath);
      const reader = await SDT.openStructuredDocumentTextPack({
        byteLength: info.size,
        read: async (offset, length) => {
          const bytes = await IOUtils.read(cachePath, { offset, maxBytes: length });
          return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        },
      }, { inflate: bytes => pako.inflateRaw(bytes) });
      const metadata = await reader.getMetadata();
      result.metadata = metadata;
      result.packBytes = info.size;
      result.packMtime = info.lastModified;
      result.status = reader.header.packVersion !== versions.SDT_PACK_VERSION ||
        String(reader.header.schemaVersion).split('.')[0] !== versions.SDT_SCHEMA_VERSION.split('.')[0]
        ? 'unsupported-pack' : metadata.source?.hash !== hash ? 'stale-source'
          : metadata.processor?.type !== processor ||
            metadata.processor?.version !== versions.SDT_PROCESSOR_VERSIONS[processor]
            ? 'stale-processor' : 'current';
    } catch (error) {
      result.status = 'invalid-pack'; result.error = String(error);
    }
    return result;
  }
  api = {
    state, versions, inspect,
    async resources() {
      const directory = Zotero.File.pathToFile(Zotero.DataDirectory.dir);
      const optionalProperty = name => {
        try { return Services.sysinfo.getProperty(name); }
        catch { return null; }
      };
      return { diskFreeBytes: directory.diskSpaceAvailable,
        directoryWritable: directory.isWritable(),
        logicalCPUs: Zotero.getMainWindow().navigator.hardwareConcurrency,
        sysinfoCPUs: optionalProperty('cpucount'),
        physicalMemoryBytes: optionalProperty('memsize'),
        availableMemoryBytes: null };
    },
    async run(itemID) {
      if (!enabled) throw new Error('Diagnostic disabled');
      if (state.active !== null) return { ok: false, reason: 'busy' };
      state.active = itemID; state.progress = null; refreshButtons();
      try {
        const before = await inspect(itemID);
        if (!enabled) return { ok: false, reason: 'disabled' };
        if (['unsupported', 'missing-source'].includes(before.status)) return { ok: false, reason: before.status };
        if (before.status === 'current') return { ok: true, cached: true };
        if (failures.has(before.identity)) return { ok: false, reason: 'suppressed-for-session' };
        const resources = await api.resources();
        if (!resources.directoryWritable || resources.diskFreeBytes <= 0) return { ok: false, reason: 'storage-unavailable' };
        // No production memory/disk budget is implied by this diagnostic gate.
        const ok = await Zotero.SDT.ensure(itemID, { isPriority: false,
          onProgress: progress => {
            if (!enabled) return;
            state.progress = progress; state.callbacks++; refreshButtons();
          },
        });
        if (!enabled) return { ok, disabledDuringRun: true };
        if (!ok) failures.set(before.identity, true);
        const after = await inspect(itemID);
        const result = { ok: ok && after.status === 'current', nativeOK: ok,
          status: after.status, reason: ok ? undefined : 'native-failure' };
        state.last = result;
        return result;
      } finally {
        state.active = null;
        if (enabled) refreshButtons();
      }
    },
  };
  Zotero.SDTSitterDiagnostic = api;
  for (const window of Zotero.getMainWindows()) addButton(window);
}
function onMainWindowLoad({ window }) { addButton(window); }
function onMainWindowUnload({ window }) {
  for (const button of buttons) if (button.ownerDocument === window.document) {
    button.remove(); buttons.delete(button);
  }
}
function shutdown() {
  enabled = false;
  for (const button of buttons) button.remove();
  buttons.clear();
  if (Zotero.SDTSitterDiagnostic === api) delete Zotero.SDTSitterDiagnostic;
  api = null;
}
function install() {}
function uninstall() {}
