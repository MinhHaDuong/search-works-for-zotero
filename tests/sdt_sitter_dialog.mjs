// The status dialog's three disclosure layers (ticket 0693), driven rather than
// read. The layout is built by `populate` and kept current by `render`, and both
// are pure DOM work over a document the plugin creates itself — so a stub
// document is enough to run the real functions, and reading the source would
// establish neither that the layers nest nor that anything inside the innermost
// one is reachable with the debug pref off.
//
// What a source grep cannot see, and each of these arms does:
//   * a disclosure that ships expanded (no code sets `open`, so the assertion is
//     on the attribute the platform reflects, not on a stub default);
//   * a diagnostics layer built as a sibling of Details rather than nested in it;
//   * a ring tail that renders only when debug logging is already on, which is
//     the acceptance criterion the author wrote;
//   * a copy action that carries the install path — the author's home directory —
//     into text destined for a bug report;
//   * a redraw that throws out of render() when a pref read fails, which stops
//     the whole 100 ms loop.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const XHTML = 'http://www.w3.org/1999/xhtml';

/* ---------------------------- the stub document ---------------------------- */

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
  // `open` reflects its attribute exactly as HTMLDetailsElement does, so
  // "closed by default" is a statement about the built DOM and not about a
  // convenient default this file chose.
  get open() { return this.attributes.has('open'); }
  set open(value) { if (value) this.attributes.set('open', ''); else this.attributes.delete('open'); }
  get textContent() {
    return this.childNodes.length
      ? this.childNodes.map(child => child.textContent).join('') : this.text;
  }
  set textContent(value) { this.childNodes = []; this.text = String(value); }
  append(...nodes) {
    for (const node of nodes) { node.parentNode = this; this.childNodes.push(node); }
  }
  replaceChildren(...nodes) { this.childNodes = []; this.append(...nodes); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); if (name === 'value') delete this.value; }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  /** Stand-in for a user activating the control; the plugin registers real listeners. */
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
    assert.equal(namespace, XHTML, 'the dialog must build XHTML, not XUL');
    return new StubNode(this, tag);
  }
  getElementById(id) {
    return this.documentElement.descendants().find(node => node.id === id) || null;
  }
}

/* ------------------------------- the host -------------------------------- */

const state = { prefs: new Map(), clipboard: null, copyAvailable: true };

function makeZotero() {
  return {
    debug: () => {},
    Prefs: {
      get: (name, full) => { assert.equal(full, true, 'the pref name must be fully qualified'); return state.prefs.get(name); },
      set: (name, value, full) => { assert.equal(full, true, 'the pref name must be fully qualified'); state.prefs.set(name, value); },
    },
    Fulltext: { getIndexStats: async () => ({ indexed: 3, partial: 0, unindexed: 1 }) },
    Utilities: { Internal: { copyTextToClipboard: text => {
      if (!state.copyAvailable) throw new Error('clipboard unavailable');
      state.clipboard = text;
    } } },
  };
}

const ui = vm.createContext({});
vm.runInContext(fs.readFileSync('bench/sdt-sitter/bootstrap.js', 'utf8'), ui);
// Loaded second, as `initialize` loads it at runtime: `var` redeclaration
// without an initializer leaves bootstrap.js's own bindings alone, so the
// dialog gets the real estimator and the real ring rather than stand-ins.
vm.runInContext(fs.readFileSync('bench/sdt-sitter/scheduler.js', 'utf8'), ui);

const DEBUG_PREF = 'extensions.sdt-pack-sitter.debug';
const INSTALL_PATH = 'file:///home/tester/.zotero/profile/extensions/sdt-pack-sitter/';

ui.Zotero = makeZotero();
ui.journal = ui.createSDTJournal(2000);
ui.alive = true;
ui.sealed = false;
ui.environment = {
  version: '9.9.9-fixture', rootURI: INSTALL_PATH, zoteroVersion: '10.0.5-stub',
  strictMinVersion: '10.0.1', strictMaxVersion: '10.*',
  packVersions: { SDT_PACK_VERSION: '1', SDT_SCHEMA_VERSION: '2.1', SDT_PROCESSOR_VERSIONS: { pdf: '7' } },
};

// A real sweep, so the ring holds records the plugin wrote and the state holds
// durations the estimator can actually fit.
const cached = new Set();
let clock = 0;
const sitter = ui.createSDTSitter({
  list: async () => [1, 2, 3],
  inspect: async id => ({ status: cached.has(id) ? 'current' : 'missing-pack',
    identity: String(id), cacheKey: `1/${id}`, sourceBytes: 1000 * id, pages: id,
    title: 'Secret Title', parentTitle: 'Secret Parent', directory: '/secret/storage' }),
  blocked: async () => null,
  yield: async () => {},
  now: () => (clock += 1000),
  changed: () => {},
  emit: ui.emit,
  reportError: ui.reportSettleFailure,
  ensure: async (id, progress) => { progress(90); cached.add(id); return true; },
});
ui.sitter = sitter;
await sitter.sweep();
assert.equal(sitter.state.completed, 3, 'the fixture sweep did not complete');

const doc = new StubDocument();
const dialog = { closed: false, document: doc, focus: () => {}, close: () => { dialog.closed = true; },
  addEventListener: () => {} };
state.prefs.set(DEBUG_PREF, false);
ui.openDialog({ openDialog: () => dialog });
// populate() is async at its tail (the native index statistics); let it settle.
await new Promise(resolve => setTimeout(resolve, 0));

const results = [];
function test(name, body) { body(); results.push(name); }

const layer2 = doc.getElementById('sdt-details');
const layer3 = doc.getElementById('sdt-tech-details');

test('the three layers exist, in order, with diagnostics nested inside details', () => {
  const top = doc.body.childNodes.map(node => node.id);
  assert.deepEqual(top, ['sdt-global-section', 'sdt-document-section', 'sdt-details'],
    'primary progress no longer leads the window');
  assert(layer2 && layer3, 'a disclosure layer is missing');
  assert.equal(layer3.parentNode, layer2,
    'diagnostics is a sibling of Details, not nested inside it');
  assert.equal(doc.getElementById('sdt-index-details').parentNode, layer2);
  // Nothing sets `open`, which is what makes both closed on first paint.
  assert.equal(layer2.getAttribute('open'), null, 'Détails ships expanded');
  assert.equal(layer3.getAttribute('open'), null, 'Diagnostics techniques ships expanded');
});

test('layer 1 still carries progress, and layer 2 still carries the counts', () => {
  assert(doc.getElementById('sdt-status').textContent.startsWith('Fichiers indexés'));
  assert.equal(doc.getElementById('sdt-global-progress').parentNode.id, 'sdt-global-section');
  assert.equal(doc.getElementById('sdt-progress').parentNode.id, 'sdt-document-section');
  assert(doc.getElementById('sdt-diagnostics').textContent.includes('Recensement : 3 / 3'));
  assert(doc.getElementById('sdt-fulltext').textContent.includes('"indexed": 3'),
    'the native index statistics did not land');
  // The fit the estimates rest on: count and covariate, both in layer 2. Three
  // page counts were observed, so the per-page covariate is the one that carried.
  assert.equal(doc.getElementById('sdt-observations').textContent,
    'Durées observées : 3 — base de calcul : par page');
});

test('the debug switch is a labelled native checkbox', () => {
  const toggle = doc.getElementById('sdt-debug');
  assert.equal(toggle.tagName, 'input');
  assert.equal(toggle.getAttribute('type'), 'checkbox');
  const label = doc.getElementById('sdt-debug-label');
  assert.equal(label.tagName, 'label');
  assert.equal(label.getAttribute('for'), 'sdt-debug',
    'the label is not tied to the checkbox, so neither click nor screen reader reaches it');
  assert.equal(doc.getElementById('sdt-journal-copy').tagName, 'button');
});

test('opening diagnostics shows the ring tail with debug logging off', () => {
  assert.equal(state.prefs.get(DEBUG_PREF), false, 'the arm needs the pref off to mean anything');
  assert.equal(doc.getElementById('sdt-journal').textContent, '',
    'a closed disclosure is being redrawn ten times a second');
  layer3.open = true;
  ui.render();
  const tail = doc.getElementById('sdt-journal').textContent;
  for (const kind of ['admit', 'submit', 'settle']) {
    assert(tail.includes(kind), `${kind} is missing from the ring tail: ${tail}`);
  }
  // Trace-level records reach the ring whatever the pref says; only Zotero's
  // own debug output is gated. That is what makes the disclosure useful before
  // the switch is thrown, which is the acceptance criterion.
  assert(tail.includes('progress'), 'trace records are gated behind the pref');
  assert(!tail.includes('Secret'), 'the ring tail leaked a title into the window');
});

test('the ring tail is not redrawn while the disclosure is closed', () => {
  const before = doc.getElementById('sdt-journal').textContent;
  layer3.open = false;
  ui.emit('cache-write', { rows: 41, compact: false });
  ui.render();
  assert.equal(doc.getElementById('sdt-journal').textContent, before);
  layer3.open = true;
  ui.render();
  assert(doc.getElementById('sdt-journal').textContent.includes('41'));
});

test('the checkbox writes the pref, and an outside change writes the checkbox', () => {
  const toggle = doc.getElementById('sdt-debug');
  assert.equal(toggle.checked, false, 'the switch does not open showing the pref it is bound to');
  toggle.checked = true;
  toggle.fire('change');
  assert.equal(state.prefs.get(DEBUG_PREF), true, 'the checkbox did not reach the pref');
  assert.equal(Array.from(ui.journal.tail(1))[0].kind, 'debug-pref',
    'flipping the switch left no record in the ring that reads it');
  toggle.checked = false;
  toggle.fire('change');
  assert.equal(state.prefs.get(DEBUG_PREF), false);
  // Zotero's own advanced settings can move this pref; the window must follow.
  state.prefs.set(DEBUG_PREF, true);
  ui.render();
  assert.equal(toggle.checked, true, 'the checkbox contradicts the pref it is bound to');
  state.prefs.set(DEBUG_PREF, false);
  ui.render();
  assert.equal(toggle.checked, false);
});

test('versions, admission readings and the install path are on screen', () => {
  const environment = doc.getElementById('sdt-environment').textContent;
  assert(environment.includes('9.9.9-fixture'), environment);
  assert(environment.includes('10.0.5-stub'), environment);
  assert(environment.includes('2.1'), environment);
  assert(environment.includes(INSTALL_PATH), 'the install path is not shown');
  // Absent readings say so rather than printing zeros that read as measurements.
  assert.equal(doc.getElementById('sdt-admission').textContent,
    'Aucune mesure de ressources depuis le démarrage.');
  ui.admission = { at: Date.now(), memoryAvailableBytes: 6.5 * 1024 ** 3, load: 1.5, cpus: 8,
    diskAvailableBytes: 120 * 1024 ** 3 };
  ui.render();
  const readings = doc.getElementById('sdt-admission').textContent;
  assert(readings.includes('6,5 Gio'), readings);
  assert(readings.includes('120,0 Gio'), readings);
  assert(readings.includes('1.5 sur 8'), readings);
});

test('the copied journal carries the build and never the install path', () => {
  doc.getElementById('sdt-journal-copy').fire('click');
  assert.equal(doc.getElementById('sdt-journal-copy-status').textContent,
    'Journal copié dans le presse-papiers.');
  const report = JSON.parse(state.clipboard);
  assert.equal(report.version, '9.9.9-fixture');
  assert.equal(report.zoteroVersion, '10.0.5-stub');
  assert.equal(report.nativeVersions.SDT_SCHEMA_VERSION, '2.1');
  assert(report.records.some(record => record.kind === 'settle'));
  // The ring is scrubbed where it is written; the install path is not, and this
  // text is meant to be pasted into a report that leaves the machine.
  assert(!state.clipboard.includes(INSTALL_PATH), 'the install path reached the clipboard');
  assert(!state.clipboard.includes('/home/tester'), state.clipboard);
  assert(!state.clipboard.includes('Secret'), state.clipboard);
});

test('an unavailable clipboard is reported, not thrown', () => {
  state.copyAvailable = false;
  state.clipboard = null;
  doc.getElementById('sdt-journal-copy').fire('click');
  assert.equal(doc.getElementById('sdt-journal-copy-status').textContent,
    'Copie impossible : presse-papiers indisponible.');
  assert.equal(state.clipboard, null);
  state.copyAvailable = true;
});

test('a pref that cannot be read does not stop the redraw loop', () => {
  const working = ui.Zotero.Prefs.get;
  ui.Zotero.Prefs.get = () => { throw new Error('prefs unavailable'); };
  const toggle = doc.getElementById('sdt-debug');
  toggle.checked = true;
  ui.render();
  // Not forced back: an unreadable pref must not fight the control either.
  assert.equal(toggle.checked, true);
  assert(doc.getElementById('sdt-status').textContent.startsWith('Fichiers indexés'),
    'the rest of the redraw did not run');
  ui.Zotero.Prefs.get = working;
});

test('a torn-down ring degrades to a message instead of throwing', () => {
  const ring = ui.journal;
  ui.journal = { tail() { throw new Error('ring gone'); } };
  ui.render();
  assert.equal(doc.getElementById('sdt-journal').textContent, 'Journal illisible : Error');
  ui.journal = ring;
});

console.log(JSON.stringify({ tests: results, result: 'pass' }));
