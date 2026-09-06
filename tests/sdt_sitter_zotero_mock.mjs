/* A Zotero host small enough to run bootstrap.js's `initialize()` and
   `openDialog()`, and deliberately no larger.
 *
 * Everything the sitter does that a reader would call "the plugin" lives inside
 * one closure in `initialize()` — `inspect`, `blocked`, `saveCache`, the sweep
 * wrapper, the generation token — and until ticket 0695 no test could reach any
 * of it. `tests/sdt_sitter_scheduler.mjs` drives the scheduler against a hand
 * written host, which is the right shape for the admission loop and says nothing
 * about the implementations bootstrap.js actually passes it; a `blocked()` faked
 * as `async () => 'low-disk'` cannot fail the way reading `/proc/meminfo` fails.
 *
 * So this is a host, not a simulator. It implements exactly the surface
 * bootstrap.js touches — `Zotero`, `IOUtils`, `PathUtils`, `Services`,
 * `ChromeUtils`, one main window, one dialog window — with the smallest
 * behaviour that makes the real code take its real branches, plus the seams the
 * scenarios need: a controllable clock, a controllable timer module, a file
 * system that can refuse a write or truncate one, and counters for the calls
 * whose *number* is the assertion.
 *
 * Two seams are worth naming, because they are what make the scenarios possible
 * rather than approximate:
 *
 *   * The clock is split. `ChromeUtils.now()` is the monotonic source
 *     bootstrap.js measures every span on; `Date.now()` is the calendar. They
 *     move independently here, which is the whole of the clock-jump scenario and
 *     is not observable at all while one function answers both questions.
 *   * The timer module runs a zero-delay timeout for real and merely records
 *     every longer one. `startup()` schedules `initialize` at 0 and the sweep's
 *     `yield` is a 0 ms timeout awaited inside the loop, so both have to run or
 *     nothing progresses; the 30 s reschedule and the 100 ms pulse must not, or
 *     a test would race the sitter it is inspecting. `pending` is left readable
 *     so a test can assert what shutdown cleared.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

import { FluentModule } from './fluent_stub.mjs';

const SITTER = 'plugins/sdt-sitter';
const decoder = new TextDecoder();

export const ROOT_URI = 'file:///home/tester/.zotero/profile/extensions/sdt-pack-sitter/';
export const DATA_DIR = '/home/tester/Zotero';
export const CACHE_PATH = `${DATA_DIR}/sdt-sitter-cache.jsonl`;
export const STORAGE = '/home/tester/Zotero/storage';
/** The native pack metadata `initialize()` reads and every identity embeds. */
export const VERSIONS = { SDT_PACK_VERSION: '1', SDT_SCHEMA_VERSION: '2.0',
  SDT_PROCESSOR_VERSIONS: { pdf: '7', epub: '3', snapshot: '2' } };
export const VERSIONS_JSON = JSON.stringify(VERSIONS);

/* ------------------------------- a stub DOM ------------------------------- */

class StubStyle {
  constructor() { this.cssText = ''; this.properties = new Map(); }
  setProperty(name, value) { this.properties.set(name, value); }
}

class StubNode {
  constructor(doc, tag) {
    this.ownerDocument = doc; this.tagName = tag; this.id = '';
    this.parentNode = null; this.childNodes = [];
    this.attributes = new Map(); this.style = new StubStyle();
    this.listeners = new Map(); this.text = '';
  }
  get open() { return this.attributes.has('open'); }
  set open(value) { if (value) this.attributes.set('open', ''); else this.attributes.delete('open'); }
  get textContent() {
    return this.childNodes.length
      ? this.childNodes.map(child => child.textContent).join('') : this.text;
  }
  set textContent(value) { this.childNodes = []; this.text = String(value); }
  append(...nodes) { for (const node of nodes) { node.parentNode = this; this.childNodes.push(node); } }
  replaceChildren(...nodes) { this.childNodes = []; this.append(...nodes); }
  remove() {
    const parent = this.parentNode;
    if (!parent) return;
    parent.childNodes = parent.childNodes.filter(node => node !== this);
    this.parentNode = null;
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); if (name === 'value') delete this.value; }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  fire(type) { for (const listener of this.listeners.get(type) || []) listener({ target: this }); }
  descendants() { return this.childNodes.flatMap(child => [child, ...child.descendants()]); }
}

class StubDocument {
  constructor() {
    this.documentElement = new StubNode(this, 'html');
    this.body = new StubNode(this, 'body');
    this.documentElement.append(this.body);
    this.readyState = 'complete';
    this.title = '';
  }
  createElementNS(namespace, tag) {
    assert.equal(namespace, 'http://www.w3.org/1999/xhtml', 'the dialog must build XHTML, not XUL');
    return new StubNode(this, tag);
  }
  createXULElement(tag) { return new StubNode(this, tag); }
  getElementById(id) {
    return this.documentElement.descendants().find(node => node.id === id) || null;
  }
}

/* ------------------------------ the timer module --------------------------- */

function createTimers() {
  const pending = new Map();
  let seq = 0, zeroPending = 0;
  const arm = (fn, ms, kind) => {
    const id = ++seq;
    if (ms === 0 && kind === 'timeout') {
      zeroPending++;
      const handle = setTimeout(() => {
        zeroPending--; pending.delete(id);
        // A throw here would be an unhandled exception in the harness rather
        // than in the code under test, and the two must not be confused.
        try { fn(); } catch (error) { pending.set('crash', error); }
      }, 0);
      pending.set(id, { fn, ms, kind, handle });
    } else {
      pending.set(id, { fn, ms, kind });
    }
    return id;
  };
  const disarm = id => {
    const entry = pending.get(id);
    if (!entry) return;
    if (entry.handle) { clearTimeout(entry.handle); zeroPending--; }
    pending.delete(id);
  };
  return {
    pending,
    cleared: [],
    get zeroPending() { return zeroPending; },
    module: {
      setTimeout: (fn, ms) => arm(fn, ms, 'timeout'),
      setInterval: (fn, ms) => arm(fn, ms, 'interval'),
      clearTimeout(id) { disarm(id); },
      clearInterval(id) { disarm(id); },
    },
    /** Run one recorded long timer or interval by hand. */
    fire(id) {
      const entry = pending.get(id);
      assert(entry, `no timer ${id} is armed`);
      if (entry.kind === 'timeout') pending.delete(id);
      entry.fn();
    },
    ids(kind) {
      return [...pending.entries()].filter(([, entry]) => entry && entry.kind === kind).map(([id]) => id);
    },
  };
}

/* ------------------------------ the file system ---------------------------- */

function createFiles() {
  const files = new Map();
  const directories = new Set(['/', '/home', '/home/tester', DATA_DIR, STORAGE]);
  const encoder = new TextEncoder();
  return {
    files, directories,
    put(path, text, lastModified = 1000) {
      files.set(path, { bytes: encoder.encode(text), lastModified });
      let dir = path.slice(0, path.lastIndexOf('/')) || '/';
      while (dir && !directories.has(dir)) {
        directories.add(dir);
        dir = dir.slice(0, dir.lastIndexOf('/')) || '/';
      }
    },
    text(path) {
      const entry = files.get(path);
      return entry === undefined ? null : decoder.decode(entry.bytes);
    },
    stat(path) {
      const entry = files.get(path);
      if (!entry) throw Object.assign(new Error('no such file'), { name: 'NotFoundError' });
      return { size: entry.bytes.length, lastModified: entry.lastModified };
    },
  };
}

/* ------------------------------- the harness ------------------------------- */

/** One attachment as the mock library holds it. Only `id` and `key` are required. */
function attachment(row) {
  return {
    libraryID: 1, kind: 'pdf', pages: 12, sourceBytes: 4096, deleted: false,
    parentDeleted: false, title: 'Full Text PDF', parentTitle: 'Sen 1999',
    hash: `md5-${row.key}`, pack: null, ...row,
  };
}

/**
 * @param options.attachments  rows for the mock library (see `attachment`)
 * @param options.cache        initial contents of the sitter's cache file, or null
 * @param options.launch       the answer to the launch prompt (default: yes)
 * @param options.windows      how many main windows exist (default: 1)
 * @param options.meminfo      `() => string` for /proc/meminfo, or a thrower
 * @param options.loadavg      `() => string` for /proc/loadavg
 * @param options.writable     whether the storage directory accepts writes
 * @param options.diskAvailable  bytes free on the storage volume
 * @param options.pathToFile   replaces the whole `Zotero.File.pathToFile` answer
 * @param options.write        `(path, bytes, opts) => void|throw`, run before the write lands
 * @param options.ensure       `(id, onProgress) => Promise<boolean>`, the native extractor
 */
export function createHarness(options = {}) {
  const rows = (options.attachments || []).map(attachment);
  const library = new Map(rows.map(row => [row.id, row]));
  const files = createFiles();
  const timers = createTimers();
  // Counted rather than merely observed: several scenarios turn on HOW MANY
  // times a reading was taken, which is the difference between one check per
  // admission and a poll, and between a cache hit and a native re-inspection.
  const calls = { meminfo: 0, loadavg: 0, openPack: [], ensure: [], prompt: 0, writes: [], hash: [] };

  // Two clocks, moving independently. `mono` is what ChromeUtils.now() answers
  // and every span in bootstrap.js is measured on; `wall` is the calendar.
  const clock = { mono: 5_000, wall: 1_700_000_000_000 };
  const advance = ms => { clock.mono += ms; clock.wall += ms; };

  for (const row of rows) {
    if (!row.missingSource) files.put(`${STORAGE}/${row.key}/file.pdf`, 'x'.repeat(row.sourceBytes), 500);
    if (row.pack) {
      // The pack's bytes name the pack, so the mock reader can identify the file
      // through the real `read(offset, length)` closure bootstrap.js builds —
      // including its `.buffer.slice(...)`, which is where a byteOffset bug lives.
      files.put(`${STORAGE}/${row.key}/.zotero-sdt-cache`,
        JSON.stringify({ key: row.key }), row.pack.lastModified ?? 900);
    }
  }
  if (options.cache !== undefined && options.cache !== null) files.put(CACHE_PATH, options.cache);

  const item = row => ({
    id: row.id, key: row.key, libraryID: row.libraryID, deleted: row.deleted,
    parentItemID: row.parentTitle ? row.id + 1000 : null,
    // A getter, because the whole point of the memoized hash is that it is NOT
    // read: in Zotero this property computes an MD5 over the file, so a test
    // about the re-verify window has to count reads rather than compare values.
    get attachmentHash() { calls.hash.push(row.key); return row.hash; },
    isAttachment: () => !row.notAnAttachment,
    isPDFAttachment: () => row.kind === 'pdf',
    isEPUBAttachment: () => row.kind === 'epub',
    isSnapshotAttachment: () => row.kind === 'snapshot',
    getFilePathAsync: async () => (row.missingSource ? null : `${STORAGE}/${row.key}/file.pdf`),
    loadData: async () => {},
    getField: () => row.title,
    getDisplayTitle: () => row.title,
  });
  const parentItem = row => ({
    deleted: row.parentDeleted, isAttachment: () => false,
    loadData: async () => {}, getField: () => row.parentTitle, getDisplayTitle: () => row.parentTitle,
  });

  const sdt = {
    openStructuredDocumentTextPack: async (source, decode) => {
      assert.equal(typeof decode.inflate, 'function', 'the pack reader was given no inflater');
      const buffer = await source.read(0, source.byteLength);
      const { key } = JSON.parse(decoder.decode(new Uint8Array(buffer)));
      calls.openPack.push(key);
      const row = rows.find(candidate => candidate.key === key);
      if (row.pack.unreadable) throw new Error('the pack is truncated');
      const versions = { ...VERSIONS, ...row.pack.versions };
      return {
        header: { packVersion: versions.SDT_PACK_VERSION, schemaVersion: versions.SDT_SCHEMA_VERSION },
        getMetadata: async () => ({
          source: { hash: row.pack.hash ?? row.hash },
          processor: { type: row.pack.processor ?? row.kind,
            version: row.pack.processorVersion ?? VERSIONS.SDT_PROCESSOR_VERSIONS[row.kind] },
        }),
      };
    },
  };

  const makeWindow = () => {
    const document = new StubDocument();
    const toolbar = new StubNode(document, 'toolbar');
    toolbar.id = 'zotero-items-toolbar';
    document.body.append(toolbar);
    const dialogs = [];
    return {
      document, toolbar, dialogs,
      navigator: { hardwareConcurrency: 8 },
      require: spec => (spec === 'pako' ? { inflateRaw: bytes => bytes } : sdt),
      openDialog() {
        const doc = new StubDocument();
        const dialog = {
          closed: false, document: doc, listeners: new Map(),
          focus() { dialog.focused = (dialog.focused || 0) + 1; },
          close() { dialog.closed = true; },
          addEventListener(type, listener) {
            if (!dialog.listeners.has(type)) dialog.listeners.set(type, []);
            dialog.listeners.get(type).push(listener);
          },
          fire(type) { for (const listener of dialog.listeners.get(type) || []) listener({}); },
        };
        dialogs.push(dialog);
        return dialog;
      },
    };
  };
  const windows = Array.from({ length: options.windows ?? 1 }, makeWindow);

  const prefs = new Map();
  const clipboard = { text: null };
  /* Ticket 0696's end-of-sweep toast. It belongs in the mock rather than in the
     one scenario that asserts on it, because announceSDTSweep is guarded: a
     missing `Zotero.ProgressWindow` does not fail, it journals `toast-error` and
     returns. So an absent primitive here would leave every scenario in this file
     silently recording a swallowed error where a toast belongs, and the scenario
     that checks for silence would pass because the constructor threw rather than
     because the gate held — a null result with no positive control. */
  const toasts = [];
  class ProgressWindow {
    constructor() { this.lines = []; this.headline = null; this.closeMS = null; toasts.push(this); }
    changeHeadline(text) { this.headline = text; }
    addDescription(text) { this.lines.push(text); }
    show() { this.shown = true; }
    startCloseTimer(ms) { this.closeMS = ms; }
  }
  const Zotero = {
    ProgressWindow,
    initializationPromise: Promise.resolve(),
    uiReadyPromise: Promise.resolve(),
    version: '10.0.5-stub',
    // The UI locale the sitter follows (ticket 0692). French, because every
    // string assertion in `tests/sdt_sitter_bootstrap.mjs` is French — and
    // because a mock that left this undefined would silently drive the whole
    // harness in English and turn each of those into a puzzle about wording.
    locale: options.locale ?? 'fr-FR',
    debug: line => debugged.push(line),
    logError: error => logged.push(String(error)),
    Prefs: { get: name => prefs.get(name), set: (name, value) => prefs.set(name, value) },
    getMainWindow: () => windows[0],
    getMainWindows: () => windows,
    Libraries: { getAll: () => [{ name: 'Ma bibliothèque' }] },
    Fulltext: { getIndexStats: async () => ({ indexed: 3, partial: 0, unindexed: 1 }) },
    Utilities: { Internal: { copyTextToClipboard: text => { clipboard.text = text; } } },
    DataDirectory: { dir: DATA_DIR },
    PDFWorker: { _processingQueue: false, _queue: [] },
    Attachments: { getStorageDirectory: target => ({ path: `${STORAGE}/${target.key}` }) },
    SDT: {
      ensure: (id, { onProgress }) => {
        calls.ensure.push(id);
        return (options.ensure || defaultEnsure)(id, onProgress);
      },
    },
    Items: {
      getAsync: async id => {
        const row = library.get(id);
        if (row) return item(row);
        const owner = library.get(id - 1000);
        return owner ? parentItem(owner) : null;
      },
    },
    DB: {
      columnQueryAsync: async () => rows.map(row => row.id),
      valueQueryAsync: async (_sql, [id]) => library.get(id).pages,
    },
    File: {
      getContents: path => {
        if (path === '/proc/meminfo') {
          calls.meminfo++;
          return options.meminfo ? options.meminfo() : 'MemTotal:       16000000 kB\nMemAvailable:    8000000 kB\n';
        }
        if (path === '/proc/loadavg') {
          calls.loadavg++;
          return options.loadavg ? options.loadavg() : '0.42 0.30 0.25 1/500 1234';
        }
        throw new Error(`unexpected sync read of ${path}`);
      },
      getContentsFromURLAsync: async url => {
        if (url === `${ROOT_URI}manifest.json`) return fs.readFileSync(`${SITTER}/manifest.json`, 'utf8');
        if (url === 'resource://zotero/document-worker/metadata.json') return VERSIONS_JSON;
        // The locale files, served the way the real host serves them — off the
        // packaged tree, one fetch per candidate in the fallback chain, and a
        // throw for a tag this build does not ship (ticket 0692). Reading them
        // from disk rather than from a fixture is deliberate: it is what makes
        // the strings this harness asserts the strings that actually ship.
        if (url.startsWith(`${ROOT_URI}locale/`)) {
          return fs.readFileSync(`${SITTER}/${url.slice(ROOT_URI.length)}`, 'utf8');
        }
        throw new Error(`unexpected URL read of ${url}`);
      },
      pathToFile: path => (options.pathToFile ? options.pathToFile(path) : {
        isWritable: () => options.writable !== false,
        diskSpaceAvailable: options.diskAvailable ?? 500 * 1024 ** 3,
      }),
    },
  };

  /** Write the pack the native extractor would have persisted for one attachment. */
  function persistPack(id, lastModified = 950) {
    const row = library.get(id);
    row.pack = { lastModified };
    files.put(`${STORAGE}/${row.key}/.zotero-sdt-cache`, JSON.stringify({ key: row.key }), lastModified);
  }

  /* The native extractor a scenario does not override. The clock steps between
     the two progress ticks because the scheduler measures a document's duration
     from the FIRST tick (ticket 0704) and refuses to record a zero: an extractor
     that returned instantly would leave every observation unusable and quietly
     empty the sample store every cache scenario reads. */
  async function defaultEnsure(id, onProgress) {
    onProgress(10);
    advance(1000);
    persistPack(id);
    onProgress(100);
    return true;
  }

  const IOUtils = {
    readUTF8: async path => {
      const text = files.text(path);
      if (text === null) throw Object.assign(new Error('no such file'), { name: 'NotFoundError' });
      return text;
    },
    stat: async path => files.stat(path),
    exists: async path => files.files.has(path) || files.directories.has(path),
    read: async (path, { offset, maxBytes }) => {
      const entry = files.files.get(path);
      if (!entry) throw Object.assign(new Error('no such file'), { name: 'NotFoundError' });
      return entry.bytes.slice(offset, offset + maxBytes);
    },
    write: async (path, bytes, opts) => {
      const text = decoder.decode(Uint8Array.from(bytes));
      calls.writes.push({ path, text, opts: { ...opts } });
      // A hook that throws refuses the write outright — an unwritable data
      // directory. A hook that returns `{ persist, fail }` lets a prefix land
      // and then fails, which is what a quit halfway through an append looks
      // like from the next session's side.
      let payload = text, failure = null, lands = true;
      if (options.write) {
        const verdict = options.write(path, text, opts) || {};
        if (verdict.fail) { failure = verdict.fail; lands = false; }
        if (typeof verdict.persist === 'string') { payload = verdict.persist; lands = true; }
      }
      const previous = opts && opts.mode === 'append' ? (files.text(path) ?? '') : '';
      if (lands) files.put(path, previous + payload);
      if (failure) throw failure;
    },
  };

  const PathUtils = {
    join: (...parts) => parts.join('/').replace(/\/+/g, '/'),
    parent: path => {
      const cut = path.lastIndexOf('/');
      return cut <= 0 ? '/' : path.slice(0, cut);
    },
  };

  const debugged = [];
  const logged = [];
  const context = vm.createContext({
    Zotero, IOUtils, PathUtils, TextEncoder, Cc: {}, Ci: {},
    Services: {
      prompt: { confirm: () => { calls.prompt++; return options.launch !== false; } },
      scriptloader: {
        // Two scripts now, and the second is why the locales work at all: a
        // `.ftl` inside a packed XPI cannot be read at runtime, so the packager
        // generates `locales.js` and this loader is the road it travels
        // (ticket 0727). Generated here the same way `bench/build_sdt_sitter.py`
        // generates it, from the same files, so the harness cannot rehearse a
        // delivery the packager does not actually make.
        loadSubScript: url => {
          if (url === `${ROOT_URI}scheduler.js`) {
            vm.runInContext(fs.readFileSync(`${SITTER}/scheduler.js`, 'utf8'), context);
            return;
          }
          assert.equal(url, `${ROOT_URI}locales.js`,
            'a script was loaded from somewhere other than rootURI');
          const sources = Object.fromEntries(['en', 'fr', 'es', 'vi'].map(tag =>
            [tag, fs.readFileSync(`${SITTER}/locale/${tag}/sdt-pack-sitter.ftl`, 'utf8')]));
          vm.runInContext(
            `var SDT_LOCALE_SOURCES = ${JSON.stringify(sources)};`, context);
        },
      },
    },
    ChromeUtils: {
      now: () => clock.mono,
      // Timer is the ONE module the real host serves this way. Fluent used to
      // be answered here too, and that was the mock inventing a platform: no
      // `resource://gre/modules/Fluent.sys.mjs` exists in Zotero 10.0.1, the
      // import always threw there, and the whole locale layer fell to its
      // catch while forty tests stayed green against a module only this file
      // provided. An unexpected spec must be loud, never answered.
      importESModule: spec => {
        assert.equal(spec, 'resource://gre/modules/Timer.sys.mjs',
          'the real host serves no other module through importESModule');
        return timers.module;
      },
    },
    // Ambient globals, exactly as privileged JS sees them. Verified live in
    // Zotero 10.0.1's Browser Console: `typeof FluentBundle`, `FluentResource`,
    // `L10nRegistry` and `L10nFileSource` all answer "function", with no
    // resource:// module backing any of them. bootstrap.js reads them off the
    // global the way it reads `Services`.
    FluentBundle: FluentModule.FluentBundle,
    FluentResource: FluentModule.FluentResource,
    // The calendar, separable from the monotonic source above. Everything else
    // about Date is the real one, so `toLocaleString` still formats.
    Date: class extends Date {
      constructor(...args) { super(...(args.length ? args : [clock.wall])); }
      static now() { return clock.wall; }
    },
  });
  vm.runInContext(fs.readFileSync(`${SITTER}/bootstrap.js`, 'utf8'), context);

  /** Let the event loop run until nothing zero-delay is armed and no sweep is busy. */
  async function quiet(limit = 400) {
    let stable = 0;
    for (let turn = 0; turn < limit; turn++) {
      await new Promise(resolve => setTimeout(resolve, 0));
      if (timers.pending.has('crash')) throw timers.pending.get('crash');
      const idle = timers.zeroPending === 0 && !(context.sitter && context.sitter.state.busy);
      stable = idle ? stable + 1 : 0;
      if (stable >= 3) return;
    }
    throw new Error('the harness never went quiet');
  }

  /** N turns of the event loop, for a scenario that deliberately hangs the worker. */
  async function turn(times = 12) {
    for (let n = 0; n < times; n++) await new Promise(resolve => setTimeout(resolve, 0));
    if (timers.pending.has('crash')) throw timers.pending.get('crash');
  }

  /* `initialize()` runs behind `.catch(error => Zotero.logError(error))`, so a
     throw anywhere inside it is swallowed by the plugin exactly as it would be
     in Zotero -- and a test asserting on a sitter that was never built passes
     vacuously against an empty journal and a null state. Every entry point
     therefore reads this before handing the harness back. */
  function assertStarted() {
    assert.deepEqual(logged, [], 'initialize() threw; nothing below is testing what it means to');
  }

  return {
    context, Zotero, files, timers, calls, windows,
    clock, advance, quiet, turn, persistPack, debugged, logged,
    /** Every toast shown, in order, with the lines it carried. */
    toasts,
    /** Run the real `startup()` and let `initialize()` reach its first sweep. */
    async start() { context.startup({ rootURI: ROOT_URI }); await quiet(); assertStarted(); },
    /** The same, for a fixture whose `ensure` never settles. */
    async startHanging(times = 12) {
      context.startup({ rootURI: ROOT_URI });
      await turn(times);
      assertStarted();
    },
    /* Run the sweep the sitter armed for itself, through bootstrap.js's own
       wrapper rather than by calling the scheduler directly — the reschedule
       lives in that wrapper's `finally`, so a test that bypasses it is blind to
       a sitter that has stopped coming back. */
    async nextSweep() {
      const armed = timers.ids('timeout');
      assert.equal(armed.length, 1, `expected one armed sweep, found ${armed.length}`);
      timers.fire(armed[0]);
      await quiet();
    },
    records(kind) {
      const all = context.journal ? Array.from(context.journal.tail(2000)) : [];
      return kind ? all.filter(record => record.kind === kind) : all;
    },
    /** The cache signature `inspect()` computes for a row, for crafting a cache file. */
    identity(key) {
      const row = rows.find(candidate => candidate.key === key);
      return `${row.libraryID}/${row.key}/${row.hash}/${VERSIONS_JSON}`;
    },
    /** The pack fingerprint `inspect()` compares against, likewise. */
    fingerprint(key) {
      const stat = files.stat(`${STORAGE}/${key}/.zotero-sdt-cache`);
      return JSON.stringify([stat.size, stat.lastModified]);
    },
    cacheLine(key, record) {
      return JSON.stringify({ versions: VERSIONS_JSON, key: `1/${key}`, record });
    },
  };
}

/** A deferred promise, for hanging the native extractor mid-job. */
export function deferred() {
  let resolve;
  const promise = new Promise(settle => { resolve = settle; });
  return { promise, resolve };
}
