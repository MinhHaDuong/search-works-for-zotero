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


const SITTER = 'plugins/sdt-sitter';
const decoder = new TextDecoder();

export const ROOT_URI = 'file:///home/tester/.zotero/profile/extensions/sdt-pack-sitter/';
/** The id Gecko hands `startup()` (ticket 0781), read off the real manifest
    rather than typed a second time -- the same file bootstrap.js's own
    `getContentsFromURLAsync('manifest.json')` route reads at startup. */
export const ADDON_ID = JSON.parse(fs.readFileSync(`${SITTER}/manifest.json`, 'utf8'))
  .applications.zotero.id;
/** What the host hands `startup()`. A real installed add-on is given its
    version from the record Zotero already holds; a harness that omitted it
    modelled a host nobody runs, which is how the version field went unnoticed
    reading "unreadable" in production for the life of ticket 0688. */
export const INSTALLED_VERSION = '9.9.9-test';
export const DATA_DIR = '/home/tester/Zotero';
/* The cache row schema bootstrap.js stamps every row with (ticket 0771). Here
   rather than spelled out per scenario, so a fixture cannot disagree with the
   plugin about what a well-formed row looks like. */
export const CACHE_FORMAT = 1;
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
  /* Focus, recorded on the document exactly as a real one records it. Added
     for ticket 0769: the dialog now places initial focus, and without this the
     stub answered `first.focus is not a function` -- an absent capability, not
     a failing behaviour. Recording it rather than making it a no-op is what
     lets a headless test assert WHERE focus landed, which is the whole of the
     accessibility claim; a no-op would have made the suite green while
     establishing nothing. */
  focus() { if (this.ownerDocument) this.ownerDocument.activeElement = this; }
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
    this.activeElement = null;
  }
  createElementNS(namespace, tag) {
    assert.equal(namespace, 'http://www.w3.org/1999/xhtml', 'the dialog must build XHTML, not XUL');
    return new StubNode(this, tag);
  }
  createXULElement(tag) { return new StubNode(this, tag); }
  getElementById(id) {
    return this.documentElement.descendants().find(node => node.id === id) || null;
  }
  /* Enough of a selector engine for the one shape the dialog asks for: a
     comma-separated list of tag names and `[attr]` / `[attr="value"]` tests,
     matched in document order. Added for ticket 0769, whose initial-focus fix
     asks the dialog for its first focusable control.

     Deliberately NOT a real selector engine. A stub that silently answered a
     selector it does not implement -- a descendant combinator, `:not()`, a
     class -- would return null and read as "no such element", which is the
     mock lying in the direction that makes a test pass. Anything it cannot
     parse throws instead, so the suite fails loudly on the day the production
     selector grows past it. */
  querySelector(selector) {
    const clauses = String(selector).split(',').map(part => part.trim()).filter(Boolean);
    const matchers = clauses.map(clause => {
      const attr = clause.match(/^\[([A-Za-z-]+)(?:="([^"]*)")?\]$/);
      if (attr) {
        const [, name, value] = attr;
        return node => node.attributes?.has?.(name)
          && (value === undefined || node.attributes.get(name) === value);
      }
      const not = clause.match(/^\[([A-Za-z-]+)\]:not\(\[([A-Za-z-]+)="([^"]*)"\]\)$/);
      if (not) {
        const [, name, exclName, exclValue] = not;
        return node => node.attributes?.has?.(name)
          && node.attributes.get(exclName) !== exclValue;
      }
      if (/^[A-Za-z][A-Za-z0-9-]*$/.test(clause)) {
        const tag = clause.toLowerCase();
        return node => String(node.tagName || '').toLowerCase() === tag;
      }
      throw new Error(`StubDocument.querySelector cannot parse ${JSON.stringify(clause)}; `
        + 'extend the stub rather than letting it answer null');
    });
    for (const node of this.documentElement.descendants()) {
      if (matchers.some(match => match(node))) return node;
    }
    return null;
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
    /* `data` is text or raw bytes. The bytes form exists because a fixture has
       to be able to hold a file whose CONTENT contradicts its declared type —
       a JPEG recorded as `text/html` (ticket 0740) — and no string can express
       one: 0xFF is not a valid UTF-8 lead byte, so `encoder.encode` cannot
       produce a JPEG signature from any source text whatsoever. */
    put(path, data, lastModified = 1000) {
      const bytes = typeof data === 'string' ? encoder.encode(data) : Uint8Array.from(data);
      files.set(path, { bytes, lastModified });
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
    /* nsIFile.remove()'s own contract: absent is a throw, not a no-op, which
       is exactly what makes a `.tmp` that most sessions never leave behind a
       case bootstrap.js's removal must survive rather than one the mock can
       paper over. */
    remove(path) {
      if (!files.has(path)) throw Object.assign(new Error('no such file'), { name: 'NotFoundError' });
      files.delete(path);
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
 * @param options.launch       answer for a modal the plugin no longer shows
 *                             (ticket 0797). Kept with `onPrompt` and
 *                             `calls.prompt` so `Services.prompt.confirmEx`
 *                             stays a WORKING surface: an assertion that the
 *                             plugin asked nothing proves nothing against a
 *                             mock that could not have been asked.
 * @param options.prefs        prefs already set in the profile, `{ name: value }`
 * @param options.onPrompt     `windows => void`, run while a modal is up
 * @param options.windows      how many main windows exist (default: 1)
 * @param options.libraries    `[{libraryID, name, libraryType}]` (default: one user library)
 * @param options.meminfo      `() => string` for /proc/meminfo, or a thrower
 * @param options.loadavg      `() => string` for /proc/loadavg
 * @param options.isLinux      what `Zotero.isLinux` answers; omit for `true`,
 *                             pass `undefined` for a host that does not say
 * @param options.isLinuxThrows  make reading `Zotero.isLinux` throw
 * @param options.writable     whether the storage directory accepts writes
 * @param options.diskAvailable  bytes free on the storage volume
 * @param options.pathToFile   replaces the whole `Zotero.File.pathToFile` answer
 * @param options.write        `(path, bytes, opts) => void|throw`, run before the write lands
 * @param options.ensure       `(id, onProgress) => Promise<boolean>`, the native extractor
 */
export function createHarness(options = {}) {
  // The single user library is the default every existing scenario assumes.
  // `libraryType` is carried because the panel reads it to put the personal
  // library first, and a mock that omitted it would make every library a group.
  const libraries = options.libraries
    || [{ libraryID: 1, name: 'Ma bibliothèque', libraryType: 'user' }];
  const rows = (options.attachments || []).map(attachment);
  const library = new Map(rows.map(row => [row.id, row]));
  const bibliographic = new Map((options.unattached || []).map(row => [row.id, {
    libraryID: 1, key: `ITEM${row.id}`, title: null, deleted: false, ...row,
  }]));
  const files = createFiles();
  const timers = createTimers();
  // Counted rather than merely observed: several scenarios turn on HOW MANY
  // times a reading was taken, which is the difference between one check per
  // admission and a poll, and between a cache hit and a native re-inspection.
  const calls = { meminfo: 0, loadavg: 0, openPack: [], ensure: [], prompt: 0,
    prompts: [], writes: [], hash: [], list: 0, affected: [], inspect: [],
    putContents: [], getAddonByID: 0, selected: [], blockReads: [],
    // Counted for the same reason `blockReads` is, and for one scenario the
    // block count cannot reach: the catalogue read sits AFTER the walk, so a
    // teardown landing between the last block and it is invisible in
    // `blockReads` — the walk finished either way. Whether the catalogue was
    // consulted at all is the only observable that separates a verdict the
    // module stopped short of from one it went on to compute.
    catalogReads: [] };
  const observers = new Map(); let observerSequence = 0;

  // Two clocks, moving independently. `mono` is what ChromeUtils.now() answers
  // and every span in bootstrap.js is measured on; `wall` is the calendar.
  const clock = { mono: 5_000, wall: 1_700_000_000_000 };
  const advance = ms => { clock.mono += ms; clock.wall += ms; };

  /* The bytes on disk, which are not always what the attachment's declared type
     claims. `magic` prepends a real file signature, so a row can be a snapshot
     to `isSnapshotAttachment()` and a JPEG to anything that reads the file —
     which is the whole of the population ticket 0740 is about. Without it the
     body is filler, and filler is what every other scenario here wants. */
  const sourceBody = row => {
    const body = new Uint8Array(row.sourceBytes).fill(0x78);
    if (row.magic) body.set(row.magic, 0);
    return body;
  };
  for (const row of rows) {
    if (!row.missingSource) files.put(`${STORAGE}/${row.key}/file.pdf`, sourceBody(row), 500);
    if (row.pack) {
      // The pack's bytes name the pack, so the mock reader can identify the file
      // through the real `read(offset, length)` closure bootstrap.js builds —
      // including its `.buffer.slice(...)`, which is where a byteOffset bug lives.
      files.put(`${STORAGE}/${row.key}/.zotero-sdt-cache`,
        JSON.stringify({ key: row.key }), row.pack.lastModified ?? 900);
    }
  }
  if (options.cache !== undefined && options.cache !== null) files.put(CACHE_PATH, options.cache);

  /* Which record owns this attachment. The synthetic `id + 1000` is the shape
     every scenario before ticket 0744's reparenting arm used: a parent that
     exists only as a title, resolved by `parentItem` below and never a member of
     the bibliographic view. A row may instead NAME its parent, and then the
     parent is an ordinary record from `options.unattached` — which is the only
     way a fixture can move one attachment between two records the no-attachment
     view actually walks. */
  const parentOf = row => ('parentItemID' in row ? row.parentItemID
    : row.parentTitle ? row.id + 1000 : null);
  const item = row => ({
    id: row.id, key: row.key, libraryID: row.libraryID, deleted: row.deleted,
    parentItemID: parentOf(row),
    // A getter, because the whole point of the memoized hash is that it is NOT
    // read: in Zotero this property computes an MD5 over the file, so a test
    // about the re-verify window has to count reads rather than compare values.
    get attachmentHash() { calls.hash.push(row.key); return row.hash; },
    isAttachment: () => !row.notAnAttachment,
    isPDFAttachment: () => row.kind === 'pdf',
    isEPUBAttachment: () => row.kind === 'epub',
    isSnapshotAttachment: () => row.kind === 'snapshot',
    /* Stored unless the fixture says otherwise, which is the ordinary case in a
       Zotero library and the one the old harness could not represent. A fixture
       asking for `linkModeUnreadable` gets the throwing getter bootstrap.js
       guards against: a group library's record can fail to load after a restart,
       and an unreadable link mode must not decide the class. */
    get attachmentLinkMode() {
      if (row.linkModeUnreadable) throw new Error('the link mode is unreadable');
      return row.linked ? 2 : row.urlOnly ? 3 : 0;
    },
    getFilePathAsync: async () => (row.missingSource ? null : `${STORAGE}/${row.key}/file.pdf`),
    loadData: async () => {},
    getField: () => row.title,
    getDisplayTitle: () => row.title,
  });
  const parentItem = row => ({
    deleted: row.parentDeleted, isAttachment: () => false,
    loadData: async () => {}, getField: () => row.parentTitle, getDisplayTitle: () => row.parentTitle,
  });
  const regularItem = row => ({
    id: row.id, key: row.key, libraryID: row.libraryID, deleted: row.deleted,
    isRegularItem: () => true, loadData: async () => {},
    /* Derived, where it used to be a constant `0`. A constant answers "this
       record has no file" for every record in the fixture, so the whole
       no-attachment view was a list the fixture declared rather than one the
       host computed — and a reparenting that emptied a record could not be seen.
       `notAnAttachment` (a note) and `urlOnly` (a link with no file) are
       excluded because Zotero's own `numFileAttachments()` excludes them; a
       trashed child likewise. Every pre-existing fixture keeps its old answer:
       nothing in them names a bibliographic record as a parent, so no child is
       ever counted. */
    numFileAttachments: () => [...library.values()].filter(child =>
      parentOf(child) === row.id && !child.deleted
      && !child.notAnAttachment && !child.urlOnly).length,
    getField: () => row.title, getDisplayTitle: () => row.title,
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
        /* The page catalog, which is what lets a textless pack be called
           VERIFIED empty rather than merely unread: a page the native worker
           had to fall back on is stamped `extractionDegraded`, and a pack
           carrying one cannot vouch for its own emptiness (ticket 0760). The
           default is a single undegraded page, so every fixture that says
           nothing about the catalog gets the ordinary complete reading; the
           three escapes below are the abnormal contracts the plugin has to
           survive, and each is unreachable from a fixture that does not ask
           for it by name. */
        getCatalog: async () => {
          calls.catalogReads.push(row.key);
          if (row.pack.catalogUnreadable) throw new Error('the catalog is unreadable');
          if ('catalog' in row.pack) return row.pack.catalog;
          return { pages: (Array.isArray(row.pack.blocks) ? row.pack.blocks : [null])
            .map((_block, index) => ({ extractionDegraded: (row.pack.degradedPages ?? []).includes(index) })) };
        },
        /* A reader that answers neither question is not a hypothetical: the
           plugin reads this object out of Zotero's own omni.ja, so a host
           whose module predates the block API hands back exactly this shape.
           Omitted rather than stubbed, so `typeof ... !== 'function'` sees
           what it is written to see. */
        ...(row.pack.readerWithoutBlockAccess ? {} : {
          getTopLevelBlockCount: () => ('blockCount' in row.pack ? row.pack.blockCount
            : Array.isArray(row.pack.blocks) ? row.pack.blocks.length : 1),
          getBlocks: async (start, end) => {
            /* Counted, because the assertion a teardown scenario needs is that
               the walk STOPPED — and a walk that stopped and a walk that never
               started look the same in the resulting status, which the scheduler
               discards either way.

               `onBlockRead` is the seam that makes such a scenario decided
               rather than raced: a test that tears the plugin down from outside
               can only aim at "somewhere around the fifth block", and a run that
               lands after the walk finished reads exactly like a walk that
               refused to stop. Called after the count is recorded, so the hook
               sees the read it is being told about. */
            calls.blockReads.push([row.key, start]);
            if (options.onBlockRead) options.onBlockRead(row.key, start);
            if (row.pack.blockRangeNotArray) return null;
            if (row.pack.blockRangeThrows) throw new Error('the content chunk is unreadable');
            const blocks = Array.isArray(row.pack.blocks) ? row.pack.blocks
              : [{ content: row.pack.empty ? [] : [{ text: row.pack.text ?? 'indexed text' }] }];
            return blocks.slice(start, end + 1);
          },
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
    const window = {
      document, toolbar, dialogs,
      navigator: { hardwareConcurrency: 8 },
      /* The item pane the "Not indexed" section's one action drives. Present on
         every window rather than opted into, because the plugin reaches it
         through `Zotero.getMainWindow()?.ZoteroPane` and a mock that omitted it
         would make every such click take the "unavailable" branch — the arm
         that reads as a pass and proves nothing. A test that WANTS that branch
         deletes this property, or replaces `selectItems`, on its own window.
         The ids are recorded rather than acted on: what a click hands the pane
         is the assertion, and nothing here changes a library. */
      ZoteroPane: { selectItems: async ids => { calls.selected.push([...ids]); } },
      /* A chrome window answers media queries, and ticket 0686's reduced-motion
         item is a reading taken from one. Only the query the plugin asks is
         answered; anything else comes back `false` rather than silently
         matching, so a mistyped query in the plugin fails the test instead of
         reading as the default. */
      matchMedia(query) {
        return { media: query,
          matches: query === '(prefers-reduced-motion: reduce)' && !!options.reducedMotion };
      },
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
          fire(type, event = {}) {
            for (const listener of dialog.listeners.get(type) || []) listener(event);
          },
        };
        dialogs.push(dialog);
        return dialog;
      },
    };
    // The plugin reaches the window from a node it owns, which is the only
    // route it has inside the render loop.
    document.defaultView = window;
    return window;
  };
  const windows = Array.from({ length: options.windows ?? 1 }, makeWindow);

  /* Seeded, so a profile that has already answered the launch question can be
     staged (ticket 0742). A `Map` and not an object: `Zotero.Prefs.get` of an
     unset pref must answer `undefined`, which is the tri-state's "never
     answered" — an object with inherited keys would answer something else for
     names like `constructor`. */
  const prefs = new Map(Object.entries(options.prefs || {}));
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
    /* The platform, as Zotero itself answers it: `Zotero.isLinux` is set from
       `Services.appinfo.OS == 'Linux'` in the host's own `zotero.js` (read at
       10.0.1, `chrome/content/zotero/xpcom/zotero.js:245`). Ticket 0783 keys
       the procfs resource guards on it.

       Defaulted to `true` rather than invented: Linux is the platform this
       repository runs, measures and ships from, so every scenario that does
       not speak about the platform keeps reading /proc exactly as it did. The
       two indefinite answers are reachable on purpose — `isLinux: undefined`
       for a host that does not say, `isLinuxThrows` for one whose read fails —
       because the ruling's conservative direction is that BOTH are treated as
       Linux, and a default of `true` would otherwise make that untestable. */
    get isLinux() {
      if (options.isLinuxThrows) throw new Error('the host cannot say what platform this is');
      return 'isLinux' in options ? options.isLinux : true;
    },
    // The UI locale the sitter follows (ticket 0692). French, because every
    // string assertion in `tests/sdt_sitter_bootstrap.mjs` is French — and
    // because a mock that left this undefined would silently drive the whole
    // harness in English and turn each of those into a puzzle about wording.
    locale: options.locale ?? 'fr-FR',
    debug: line => debugged.push(line),
    logError: error => logged.push(String(error)),
    Prefs: { get: name => prefs.get(name), set: (name, value) => prefs.set(name, value),
      clear: name => prefs.delete(name) },
    getMainWindow: () => windows[0],
    getMainWindows: () => windows,
    Libraries: { getAll: () => libraries, get: id => libraries.find(row => row.libraryID === id) || null },
    Fulltext: { getIndexStats: async () => ({ indexed: 3, partial: 0, unindexed: 1 }) },
    Utilities: { Internal: { copyTextToClipboard: text => { clipboard.text = text; } } },
    DataDirectory: { dir: DATA_DIR },
    PDFWorker: { _processingQueue: false, _queue: [] },
    /* The link-mode constants are Zotero's own, and their ABSENCE was a defect
       of this harness rather than a simplification. bootstrap.js falls back to
       `item.attachmentLinkMode === Zotero.Attachments.LINK_MODE_LINKED_FILE`
       when the host offers no `isLinkedFileAttachment()`, and with neither side
       defined that comparison is `undefined === undefined` — true. Every
       attachment in every fixture therefore read as a LINKED file, so
       "Stored file unavailable" was unreachable here and "Linked file
       unavailable" was reached by accident, which is a host nobody runs. */
    Attachments: {
      getStorageDirectory: target => ({ path: `${STORAGE}/${target.key}` }),
      LINK_MODE_IMPORTED_FILE: 0,
      LINK_MODE_IMPORTED_URL: 1,
      LINK_MODE_LINKED_FILE: 2,
      LINK_MODE_LINKED_URL: 3,
    },
    SDT: {
      ensure: (id, { onProgress }) => {
        calls.ensure.push(id);
        return (options.ensure || defaultEnsure)(id, onProgress);
      },
    },
    Notifier: {
      registerObserver(observer, types) { const id = ++observerSequence; observers.set(id, { observer, types }); return id; },
      unregisterObserver(id) { observers.delete(id); },
    },
    Items: {
      getAsync: async id => {
        calls.inspect.push(id);
        const row = library.get(id);
        if (row) return item(row);
        const record = bibliographic.get(id);
        if (record) return regularItem(record);
        const owner = library.get(id - 1000);
        return owner ? parentItem(owner) : null;
      },
    },
    DB: {
      columnQueryAsync: async (sql, params) => {
        if (params) { calls.affected.push(params[0]); return [...library.values()]
          .filter(row => parentOf(row) === params[0]).map(row => row.id); }
        if (sql.includes('FROM items')) return [...bibliographic.keys()];
        calls.list++; return [...library.keys()];
      },
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
        // Anything this profile has actually written, read back synchronously
        // as Zotero's own does -- the death certificate verifies its write this
        // way (ticket 0727), and a mock that could not answer would make that
        // check untestable. A missing file throws, as the real one does.
        const written = files.text(path);
        if (written !== null) return written;
        throw new Error(`unexpected sync read of ${path}`);
      },
      getContentsFromURLAsync: async url => {
        if (url === `${ROOT_URI}manifest.json`) return fs.readFileSync(`${SITTER}/manifest.json`, 'utf8');
        if (url === 'resource://zotero/document-worker/metadata.json') return options.versions ? JSON.stringify(options.versions()) : VERSIONS_JSON;
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
        // `path` is carried because the real nsIFile carries it, and because
        // `putContents` below is given the file and has to know where it goes.
        path,
        // nsIFile's own. Absent from this mock until ticket 0727's guard 1
        // needed it, and its absence made that guard's first test fail for a
        // reason that had nothing to do with the guard -- a mock that does not
        // model a method the code calls answers the wrong question silently.
        exists: () => files.files.has(path),
        isWritable: () => options.writable !== false,
        diskSpaceAvailable: options.diskAvailable ?? 500 * 1024 ** 3,
        // `options.removeThrows`, a predicate over the path, stages the
        // "unwritable directory" arm of ticket 0773's removal test without
        // reaching for the whole-object override every other scenario here
        // uses -- the default `isWritable`/`diskSpaceAvailable` stay live
        // alongside it.
        remove: () => {
          if (options.removeThrows && options.removeThrows(path)) {
            throw new Error('cannot remove (mock)');
          }
          files.remove(path);
        },
      }),
      /* Synchronous, as Zotero's own is: the death certificate (ticket 0727) is
         written from a teardown whose sandbox does not outlive it, so an async
         write would be the one thing that function exists to rule out. */
      putContents: (file, text) => {
        if (options.putContentsThrows) throw new Error('write failed');
        calls.putContents.push({ path: file && file.path, text });
        // `putContentsDrops` is the file system that accepts a write and keeps
        // nothing -- a full volume, or a writer that turns out not to be
        // synchronous. It returns without throwing, which is what makes it a
        // different arm from `putContentsThrows` and the reason the certificate
        // reads itself back.
        if (options.putContentsDrops) return;
        files.put(file.path, text);
      },
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

  /* Ticket 0781's self-check, answered here rather than assumed: the default
     is the healthy host every pre-existing scenario runs against, so nothing
     above this line has to know this mock exists. `options.addon` stages a
     removal (return `null`, or `{ isActive: false }`); `options.addonManagerThrows`
     stages a host whose read itself fails. */
  const AddonManagerMock = {
    getAddonByID: async id => {
      calls.getAddonByID++;
      if (options.addonManagerThrows) throw new Error('AddonManager is unavailable (mock)');
      return typeof options.addon === 'function' ? options.addon(id) : { id, isActive: true };
    },
  };
  const debugged = [];
  const logged = [];
  const context = vm.createContext({
    Zotero, IOUtils, PathUtils, TextEncoder, Cc: {}, Ci: {},
    Services: {
      /* THE PLUGIN NO LONGER ASKS ANYTHING (ticket 0797), and this surface is
         kept precisely because of that. `calls.prompt` is asserted to be zero
         in several places, and a zero from a host that has no `confirmEx` at
         all is the all-clear-indistinguishable-from-could-not-look trap: a
         bootstrap.js that started asking again would throw here rather than
         move the counter, and a throw in startup is a different failure
         wearing a different message. So the call stays live, counting, and
         answering.

         `confirmEx`, and deliberately NOT `confirm` beside it (ticket 0742).
         A mock that answered the old two-button call would let a bootstrap.js
         reverted to OK/Cancel stay green. The button titles are captured so a
         test can assert a question is not asked over generic buttons.

         `BUTTON_POS_*` and `BUTTON_TITLE_IS_STRING` are nsIPromptService's own
         values, not invented ones: a flag word computed from different numbers
         would be a mock inventing the platform, which is the failure the
         `importESModule` assertion below records. */
      prompt: {
        BUTTON_POS_0: 1, BUTTON_POS_1: 256, BUTTON_TITLE_IS_STRING: 127,
        confirmEx: (_parent, title, text, flags, button0, button1) => {
          calls.prompt++;
          calls.prompts.push({ title, text, flags, buttons: [button0, button1] });
          // The one moment the modal is up. A real `confirmEx` blocks here, so
          // this hook is the only place a test can read the window as the user
          // sees it while the question is being asked — which is the whole of
          // ticket 0742's ordering race.
          if (options.onPrompt) options.onPrompt(windows);
          return options.launch === false ? 1 : 0;
        },
      },
      scriptloader: {
        loadSubScript: url => {
          assert.equal(url, `${ROOT_URI}scheduler.js`, 'the scheduler is not loaded from rootURI');
          vm.runInContext(fs.readFileSync(`${SITTER}/scheduler.js`, 'utf8'), context);
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
        if (spec === 'resource://gre/modules/AddonManager.sys.mjs') return { AddonManager: AddonManagerMock };
        assert.equal(spec, 'resource://gre/modules/Timer.sys.mjs',
          'the real host serves no other module through importESModule');
        return timers.module;
      },
    },
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
    context, Zotero, files, timers, calls, windows, library, observers,
    notify(event, type, ids) { for (const { observer, types } of observers.values())
      if (types.includes(type)) observer.notify(event, type, ids, {}); },
    clock, advance, quiet, turn, persistPack, debugged, logged,
    /** Every toast shown, in order, with the lines it carried. */
    toasts,
    /** Run the real `startup()` and let `initialize()` reach its first sweep. */
    async start() { context.startup({ rootURI: ROOT_URI, version: INSTALLED_VERSION, id: ADDON_ID }); await quiet(); assertStarted(); },
    /** The same, for a fixture whose `ensure` never settles. */
    async startHanging(times = 12) {
      context.startup({ rootURI: ROOT_URI, version: INSTALLED_VERSION, id: ADDON_ID });
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
      advance(timers.pending.get(armed[0]).ms);
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
      return JSON.stringify({ format: CACHE_FORMAT, versions: VERSIONS_JSON, key: `1/${key}`, record });
    },
  };
}

/** A deferred promise, for hanging the native extractor mid-job. */
export function deferred() {
  let resolve;
  const promise = new Promise(settle => { resolve = settle; });
  return { promise, resolve };
}
