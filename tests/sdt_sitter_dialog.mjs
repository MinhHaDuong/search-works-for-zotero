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
//     into text destined for a bug report, including by the indirect route: the
//     ring survives a disable/re-enable, so the second `initialize()` writes a
//     startup record carrying rootURI INTO the ring, and a verbatim tail puts it
//     on the clipboard even though it is omitted as a top-level field;
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

const state = { prefs: new Map(), clipboard: null, copyAvailable: true, libraries: [] };

function makeZotero() {
  return {
    debug: () => {},
    Prefs: {
      get: (name, full) => { assert.equal(full, true, 'the pref name must be fully qualified'); return state.prefs.get(name); },
      set: (name, value, full) => { assert.equal(full, true, 'the pref name must be fully qualified'); state.prefs.set(name, value); },
    },
    Fulltext: { getIndexStats: async () => ({ indexed: 3, partial: 0, unindexed: 1 }) },
    Libraries: { getAll: () => state.libraries },
    Utilities: { Internal: { copyTextToClipboard: text => {
      if (!state.copyAvailable) throw new Error('clipboard unavailable');
      state.clipboard = text;
    } } },
  };
}

const ui = vm.createContext({});
vm.runInContext(fs.readFileSync('plugins/sdt-sitter/bootstrap.js', 'utf8'), ui);
// Loaded second, as `initialize` loads it at runtime: `var` redeclaration
// without an initializer leaves bootstrap.js's own bindings alone, so the
// dialog gets the real estimator and the real ring rather than stand-ins.
vm.runInContext(fs.readFileSync('plugins/sdt-sitter/scheduler.js', 'utf8'), ui);
// Ticket 0692: the window's text comes from `locale/fr/sdt-pack-sitter.ftl`,
// through the plugin's own loader. Every French assertion below is therefore
// about the layout, the translation and the load path at once — and the arms
// that assert what does NOT reach the clipboard are unaffected either way,
// which is why they still read the same.

const DEBUG_PREF = 'extensions.sdt-pack-sitter.debug';
const INSTALL_PATH = 'file:///home/tester/.zotero/profile/extensions/sdt-pack-sitter/';

ui.Zotero = makeZotero();
ui.journal = ui.createSDTJournal(2000);
ui.alive = true;
ui.sealed = false;
/* What `startup()` imports from `resource://gre/modules/Timer.sys.mjs` and binds
   here. The dialog fixture never runs `startup()`, and until ticket 0742 nothing
   in this file needed it — the switch does: turning indexing on arms the sweep
   loop and the two intervals, which is the half of the control a source grep
   cannot see. Counted rather than merely accepted, so an arm that never happened
   and an arm that happened twice are different observations. */
const armed = { intervals: 0, timeouts: 0, cleared: 0 };
ui.timers = {
  setInterval: () => ++armed.intervals,
  setTimeout: () => ++armed.timeouts,
  clearInterval: () => { armed.cleared++; },
  clearTimeout: () => { armed.cleared++; },
};
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
  // The switch leads (ticket 0742): R22's "one obvious way" is not obvious three
  // sections down, and a reader who opens this window in a hurry opens it to
  // stop the thing. Progress still leads everything that is a READING.
  assert.deepEqual(top,
    ['sdt-switch-row', 'sdt-global-section', 'sdt-document-section', 'sdt-details'],
    'primary progress no longer leads the window');
  assert(layer2 && layer3, 'a disclosure layer is missing');
  assert.equal(layer3.parentNode, layer2,
    'diagnostics is a sibling of Details, not nested inside it');
  assert.equal(doc.getElementById('sdt-index-details').parentNode, layer2);
  // Nothing sets `open`, which is what makes both closed on first paint.
  assert.equal(layer2.getAttribute('open'), null, 'Details ships expanded');
  assert.equal(layer3.getAttribute('open'), null, 'Technical diagnostics ships expanded');
  // The stub document has no layout engine, so this cannot see the button
  // actually hold still — only that the declaration a real browser would obey
  // is present. `space-between` pins the button to the row's fixed edge
  // instead of to wherever the state text happens to end, which is what moved
  // when "on" and "off" describe very different lengths of text (found live,
  // testing v0.3.15).
  assert(doc.getElementById('sdt-switch-row').style.cssText.includes('justify-content: space-between'),
    'the switch button is not pinned to a fixed edge of its row');
  // `element()`'s default styling carries `white-space: pre-wrap`, meant for
  // the prose blocks; on the button it let "Turn indexing on"/"off" wrap to a
  // second line at some widths, turning it into a square (found live, testing
  // v0.3.17). The button overrides it to a single line; the state text is
  // free to wrap in its place.
  assert(doc.getElementById('sdt-switch').style.cssText.includes('white-space: nowrap'),
    'the switch button can still wrap onto a second line');
  assert(doc.getElementById('sdt-switch-state').style.cssText.includes('min-width: 0'),
    'the state text cannot shrink to make room for the button');
  // Same caveat: this only proves the reservation exists, not that the box
  // stops visibly collapsing between files — the defect this line guards
  // against (found live, testing v0.3.15).
  assert.equal(doc.getElementById('sdt-document-status').style.minHeight, '3em',
    'the active-file box has no reserved height, so it can still collapse between files');
});

/* Found live, testing v0.3.18: three long library names joined into the bold
   `<legend>` wrapped it five lines deep on a narrow window. Moved into its
   own plain line (`sdt-scope`), which wraps like any other sentence, while
   the heading itself stays the short, static message id. */
test('the library scope reads as its own line, not as part of the bold heading', () => {
  const legend = doc.getElementById('sdt-global-section-title');
  assert.equal(legend.textContent, 'Overall progress',
    'the heading still carries the scope it was asked to drop');
  state.libraries = [{ name: 'A First Very Long Library Name' },
    { name: 'A Second Very Long Library Name' },
    { name: 'A Third Very Long Library Name' }];
  ui.render();
  const scope = doc.getElementById('sdt-scope');
  assert.equal(scope.parentNode.id, 'sdt-global-section',
    'the scope line is not under the section it scopes');
  assert(scope.textContent.includes('A First Very Long Library Name'), scope.textContent);
  assert.equal(legend.textContent, 'Overall progress',
    'the heading changed when the library set did');
  state.libraries = [];
  ui.render();
});

test('layer 1 still carries progress, and layer 2 still carries the counts', () => {
  assert(doc.getElementById('sdt-status').textContent.startsWith('Files indexed'));
  assert.equal(doc.getElementById('sdt-global-progress').parentNode.id, 'sdt-global-section');
  assert.equal(doc.getElementById('sdt-progress').parentNode.id, 'sdt-document-section');
  assert(doc.getElementById('sdt-diagnostics').textContent.includes('Scanned 3 attachments out of 3.'));
  // A real `<table>` now, not a JSON dump and not padded text (found live,
  // testing v0.3.15, then v0.3.17 once the padding turned out not to align in
  // the dialog's own proportional font): a row named after the field, its
  // count in a cell of its own.
  const indexedRow = doc.getElementById('sdt-fulltext-body').childNodes
    .find(row => row.childNodes[0].textContent === 'Indexed');
  assert(indexedRow, 'the native index statistics did not land');
  assert.equal(Number(indexedRow.childNodes[1].textContent), 3);
  assert(indexedRow.childNodes[1].style.cssText.includes('text-align: right'),
    'the count cell is not right-aligned');
});

/* Ticket 0742. The switch is layer 1's first control, and "off" is a state the
   window can both show and leave. A source grep sees the strings; only driving
   the control shows that clicking it stops the sitter, persists the answer, and
   redraws the two lines the reader is looking at — and that clicking it again
   comes back. The order matters to the arms below, so they run as one. */
test('the switch turns indexing off and on again, persisting each answer', () => {
  const control = doc.getElementById('sdt-switch');
  const label = doc.getElementById('sdt-switch-state');
  assert.equal(control.tagName, 'button', 'the switch is not a native control');
  assert.equal(control.parentNode.id, 'sdt-switch-row');
  assert.equal(control.textContent, 'Turn indexing off');
  // The switch line and the raw "State: {phase}" line merged into one
  // (found live, testing v0.3.18): the phase now speaks in a sentence, here.
  assert.equal(label.textContent, 'Indexing is on. Nothing to index right now.');

  control.fire('click');
  assert.equal(sitter.state.enabled, false, 'the sitter kept admitting after the switch');
  assert.equal(sitter.state.phase, 'switched-off');
  assert.equal(state.prefs.get('extensions.sdt-pack-sitter.enabled'), false,
    'the answer was not persisted, so it would not hold across a restart');
  assert.equal(control.textContent, 'Turn indexing on', 'the switch offers no way back');
  assert.equal(label.textContent,
    'Indexing is off. Zotero will still index PDFs as you view them.');

  const before = armed.intervals;
  control.fire('click');
  assert.equal(sitter.state.enabled, true, 'turning indexing on left the sitter stopped');
  assert.equal(sitter.state.phase, 'ready');
  assert.equal(state.prefs.get('extensions.sdt-pack-sitter.enabled'), true);
  assert.equal(control.textContent, 'Turn indexing off');
  // The redraw pulse and the heartbeat, armed again. Without this the switch
  // could flip the pref and the phase and never restart the loop, and every
  // assertion above would still pass.
  assert.equal(armed.intervals - before, 2, 'turning indexing on armed no loop');
});

/* Found live, after PR #481 shipped: turning indexing off mid-census left the
   overall-progress bar animating forever. The 100 ms render loop is cleared by
   the switch, but a native `<progress>` with no `value` attribute is
   indeterminate and animates by itself, on the platform's own clock, with no
   further redraw needed — so the loop being stopped proves nothing here. The
   scanned/total split below is the reproduction: a census that has not
   finished when the switch is thrown, which is the ordinary case, since a
   user reaches for the switch precisely while indexing is under way. */
test('switching off mid-census freezes the progress bar instead of leaving it animating', () => {
  sitter.state.scanned = 1;
  sitter.state.total = 3;
  const control = doc.getElementById('sdt-switch');
  control.fire('click');
  assert.equal(sitter.state.phase, 'switched-off');
  const globalProgress = doc.getElementById('sdt-global-progress');
  assert.notEqual(globalProgress.value, undefined,
    'the overall-progress bar has no value attribute after switching off mid-census — ' +
    'indeterminate, so the platform animates it forever with the sitter off');
  control.fire('click');
  assert.equal(sitter.state.phase, 'ready');
  sitter.state.scanned = 3;
  sitter.state.total = 3;
});

/* Ticket 0742's other half. The worker limitation and the disable semantics were
   the third and fourth paragraphs of a modal shown once per session and gone the
   moment it was dismissed. The assertion is on WHERE they hang, which is the
   thing the move was for: readable at any time, beside the switch they describe.
   `getElementById` finds them wherever they were appended, so the parent is the
   only question a source grep cannot answer.

   Found live, testing v0.3.16: they moved a level deeper, into their own About
   disclosure alongside the version/compatibility lines, apart from the
   debug/log one that used to hold both — a reader opens one to learn what the
   add-on does, and the other to chase a problem. */
test('the launch disclosures are readable in their own About disclosure', () => {
  const disclosures = doc.getElementById('sdt-disclosures');
  assert(disclosures, 'the disclosures reach no layer of the window at all');
  const about = doc.getElementById('sdt-about-details');
  assert(about, 'the About disclosure does not exist');
  assert.equal(about.parentNode.id, layer2.id, 'About is not nested inside the Details layer');
  assert.equal(disclosures.parentNode.id, about.id,
    'the disclosures are not inside the About disclosure');
  assert.equal(doc.getElementById('sdt-environment').parentNode.id, about.id,
    'the version/compatibility lines did not move into About with the disclosures');
  assert.notEqual(about.id, layer3.id, 'About and the debug/log disclosure are the same element');
  // Rewritten in plain language after the author read the jargon version live
  // ("shared worker", "native work", "thresholds") and could not follow it
  // (found live, testing v0.3.15) — the assertion is on the plain-language
  // replacement, not on the words that were removed for being unclear.
  assert(disclosures.textContent.includes('cannot be paused once a file has started'),
    'the worker limitation is not readable in the window');
  assert(disclosures.textContent.includes('one already being processed still finishes'),
    'what turning indexing off does is not readable in the window');
});

// Author's ruling of 2026-09-08, second half: "Observed durations" is technical
// diagnostics, not a primary reading. It kept its wording and changed layer, so
// the arm is about WHERE the node hangs — which is precisely what a source grep
// cannot answer, since `getElementById` finds it wherever it was appended.
test('the observed durations are read in the diagnostics layer, not in Details', () => {
  const observations = doc.getElementById('sdt-observations');
  assert.equal(observations.parentNode.id, layer3.id,
    'the durations still hang in Details, above the diagnostics layer they belong to');
  // Three page counts were observed, so the per-page covariate is the one that
  // carried. The reading itself must survive the move.
  assert.equal(observations.textContent, 'Observed durations: 3 — basis: per page');
});

/* Author's ruling of 2026-09-08, first half, taken live while he read the census
   on his own library: THE CENSUS IS AN ACCOUNT AND SHOULD READ AS ONE.

   What it replaces read `unsupported: 2600 / missing-source: 367 /
   failed-session: 39` — internal keys, in the order a JavaScript object happened
   to hand them over — above a separate `Could not be indexed (last census): 406`
   that silently added 367 files merely absent from this disk to 39 real
   failures. Two unrelated facts under one label. The classes sum exactly, so
   the arithmetic was honest and only the presentation was not.

   Driven rather than read, because the two things that can go wrong here are
   both invisible to a grep: a status the scheduler can produce and this table
   cannot name (it would render as its raw key, which is the defect), and a
   total that does not equal the rows printed above it (which is what makes an
   account an account). */
test('the census reads as an account: words, then a total at the bottom', () => {
  const counts = sitter.state.counts;
  const saved = { ...counts };
  for (const key of Object.keys(counts)) delete counts[key];
  Object.assign(counts, { current: 13699, unsupported: 2600, 'missing-source': 367,
    'failed-session': 39, 'missing-pack': 1 });
  ui.render();
  const body = doc.getElementById('sdt-census-body');
  const rowLabel = row => row.childNodes[0].textContent;
  const rowValue = row => Number(row.childNodes[1].textContent.replace(/[^0-9]/g, ''));

  // No internal key survives as a label, exactly (a raw key found here is the
  // exact defect: `failed-session` is the string the author read on screen
  // and objected to). The account is a `<table>` now, so no colon and no
  // hand-aligned column exists to check for — the cell IS the column (found
  // live, testing v0.3.15, then v0.3.17 for the alignment itself).
  for (const key of ['unsupported', 'missing-source', 'failed-session', 'missing-pack']) {
    assert(!body.childNodes.some(row => rowLabel(row) === key),
      `the raw status key ${key} is still the label a reader is shown`);
  }
  // The conflating aggregate is gone: every one of its constituents is now on a
  // row of its own, so nothing is lost and nothing is summed that should not be.
  assert(!body.childNodes.some(row => rowLabel(row).includes('Could not be indexed (last census)')),
    'the line that added files-not-on-this-disk to real failures is still there');

  const row = label => {
    const found = body.childNodes.find(candidate => rowLabel(candidate) === label);
    assert(found, `no row named ${label}: ${body.childNodes.map(rowLabel).join(' | ')}`);
    return rowValue(found);
  };
  assert.equal(row('Indexed and up to date'), 13699);
  assert.equal(row('No extractor for this format'), 2600);
  assert.equal(row('File missing from this disk'), 367);
  assert.equal(row('Extraction failed this session'), 39);
  assert.equal(row('Waiting to be indexed'), 1);

  // The total is last, and it is the sum of the rows above it — 13 699 + 2 600 +
  // 367 + 39 + 1 = 16 706, the author's own arithmetic.
  const last = body.childNodes[body.childNodes.length - 1];
  assert.equal(rowLabel(last), 'Attachments counted in all',
    `the total is not at the bottom: ${rowLabel(last)}`);
  assert.equal(rowValue(last), 16706);
  // Every value cell right-aligned, in any font — the point of a real
  // `<table>` over the padded text it replaced (found live, testing v0.3.17).
  assert(body.childNodes.every(candidate =>
    candidate.childNodes[1].style.cssText.includes('text-align: right')),
    'a value cell is not right-aligned');
  // A rule sets the total off from the rows it sums (found live, testing
  // v0.3.18) — a plain visual convention for a sum row, and none of the
  // category rows above it carries the same border.
  assert(last.childNodes[0].style.cssText.includes('border-top'),
    'no rule separates the total from the rows above it');
  assert(!body.childNodes[0].style.cssText.includes('border-top'),
    'a category row carries the total\'s own rule');
  assert(doc.getElementById('sdt-census-table').style.cssText.includes('margin: 8px 0'),
    'the table carries no space below it');

  // A status nobody named must be visible, not silently dropped from an account
  // that still claims to add up.
  Object.assign(counts, { 'a-status-nobody-named': 7 });
  ui.render();
  assert(body.childNodes.some(candidate => rowLabel(candidate) === 'a-status-nobody-named'
    && rowValue(candidate) === 7),
    'an unnamed status vanished from the account');
  const withUnknownTotal = body.childNodes[body.childNodes.length - 1];
  assert.equal(rowValue(withUnknownTotal), 16713);

  // Before the first census there are no rows, and a lone total of zero would be
  // a measurement where there is none. The scan line above already says 0 / 0.
  for (const key of Object.keys(counts)) delete counts[key];
  ui.render();
  assert.equal(body.childNodes.length, 0, 'an empty census still prints an account');
  assert(doc.getElementById('sdt-diagnostics').textContent.includes('Scanned '),
    'the scan line went with it');

  Object.assign(counts, saved);
  ui.render();
});

/* Found live, testing v0.3.18: the account visibly blinked between
   documents, because `render()` rebuilt the whole `<table>` from scratch on
   every 100 ms tick regardless of whether the census had changed since the
   last one -- almost always, since a document transition is a small minority
   of ticks. Node identity across two unchanged renders is the proof a source
   grep cannot give: the same `<tr>` survives, not a new one wearing the same
   text. */
test('the census table is rebuilt only when the account itself changes', () => {
  const body = doc.getElementById('sdt-census-body');
  const before = body.childNodes[0];
  ui.render();
  assert.equal(body.childNodes[0], before, 'the table rebuilt on an unchanged census');

  const counts = sitter.state.counts;
  counts.current = (counts.current || 0) + 1;
  ui.render();
  assert.notEqual(body.childNodes[0], before, 'the table did not rebuild on a real change');
  counts.current--;
  ui.render();
});

/* Found live, testing v0.3.18: the switch line and the raw "State: {phase}"
   line merged into one. Every phase a reader can actually meet while on,
   driven rather than read, since a phase this composer forgets falls
   through to the idle wording silently -- a source grep sees the branches,
   not which phase reaches which one. */
test('the switch line names the phase, in a sentence, for every phase a reader can meet', () => {
  const label = doc.getElementById('sdt-switch-state');
  const on = phase => {
    sitter.state.phase = phase;
    ui.render();
    return label.textContent;
  };
  assert.equal(on('ready'), 'Indexing is on. Nothing to index right now.');
  assert.equal(on('waiting'), 'Indexing is on. Nothing to index right now.');
  assert.equal(on('census'), 'Indexing is on. Scanning the library for new or modified attachments.');
  assert.equal(on('extracting'), 'Indexing is on. Extracting structured text from attachments.');
  assert.equal(on('error'), 'Indexing is on. An unexpected problem stopped the last scan — see Technical diagnostics.');
  // A resource-blocked phase reuses the toolbar tooltip's own label verbatim
  // (no trailing period there, since the tooltip joins it by em dash), so
  // the two never word the same fact two different ways.
  assert.equal(on('cpu-busy'), 'Indexing is on. Waiting: processor busy');
  sitter.state.phase = 'ready';
  ui.render();
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
  // The raw phase name moved here with the "State: {phase}" line it used to
  // be (found live, testing v0.3.18) — greppable against the source for
  // debugging, apart from the sentence the switch line now carries instead.
  assert.equal(doc.getElementById('sdt-internal-phase').textContent, 'Internal phase: ready');
});

/* Found live, testing v0.3.17: a routine single-attachment extraction failure
   — already carried, correctly, as its own row in the census account —
   ALSO surfaced as a top-of-window "Error:" banner in the main Details layer,
   reading as a live alarm for something the account already shows as
   expected and handled. Moved to Technical diagnostics, where a reader opens
   specifically to see raw detail, and reworded so it no longer overclaims
   "Error" for a single failed attachment among possibly thousands. */
test('a single extraction failure reads as a technical detail, not a top-level alarm', () => {
  assert(!doc.getElementById('sdt-diagnostics').textContent.includes('Error'),
    'the error still surfaces in the primary Details layer');
  const before = doc.getElementById('sdt-error').textContent;
  assert.equal(before, '', 'a closed disclosure is being redrawn ten times a second');
  sitter.state.error = 'Native SDT did not persist a current pack';
  layer3.open = true;
  ui.render();
  const error = doc.getElementById('sdt-error').textContent;
  assert.equal(doc.getElementById('sdt-error').parentNode.id, layer3.id,
    'the error line is not inside Technical diagnostics');
  assert(error.includes('Native SDT did not persist a current pack'), error);
  assert(!error.startsWith('Error:'), 'still reads as an unqualified alarm rather than a detail');
  sitter.state.error = null;
  layer3.open = false;
  ui.render();
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
  // The environment line now redraws only while About is open (found live,
  // testing v0.3.16 — it moved out of the debug/log disclosure into its own).
  doc.getElementById('sdt-about-details').open = true;
  ui.render();
  const environment = doc.getElementById('sdt-environment').textContent;
  assert(environment.includes('9.9.9-fixture'), environment);
  assert(environment.includes('10.0.5-stub'), environment);
  assert(environment.includes('2.1'), environment);
  assert(environment.includes(INSTALL_PATH), 'the install path is not shown');
  // Absent readings say so rather than printing zeros that read as measurements.
  assert.equal(doc.getElementById('sdt-admission').textContent,
    'No resource reading since startup.');
  ui.admission = { at: Date.now(), memoryAvailableBytes: 6.5 * 1024 ** 3, load: 1.5, cpus: 8,
    diskAvailableBytes: 120 * 1024 ** 3 };
  ui.render();
  const readings = doc.getElementById('sdt-admission').textContent;
  assert(readings.includes('6.5 GiB'), readings);
  assert(readings.includes('120.0 GiB'), readings);
  assert(readings.includes('1.5 on 8'), readings);
});

test('the copied journal carries the build and never the install path', () => {
  doc.getElementById('sdt-journal-copy').fire('click');
  assert.equal(doc.getElementById('sdt-journal-copy-status').textContent,
    'Log copied to the clipboard.');
  const report = JSON.parse(state.clipboard);
  assert.equal(report.version, '9.9.9-fixture');
  assert.equal(report.zoteroVersion, '10.0.5-stub');
  assert.equal(report.nativeVersions.SDT_SCHEMA_VERSION, '2.1');
  assert(report.records.some(record => record.kind === 'settle'));
  // Weak on its own, and deliberately kept as the shallow arm: `ui.environment`
  // was assigned by hand above, so nothing ever put the install path into this
  // ring and its absence here proves only that the top-level field is omitted.
  // The arm that carries the invariant is the last one in this file, where the
  // ring is contaminated by the real startup path first.
  assert(!state.clipboard.includes(INSTALL_PATH), 'the install path reached the clipboard');
  assert(!state.clipboard.includes('Secret'), state.clipboard);
});

test('an unavailable clipboard is reported, not thrown', () => {
  state.copyAvailable = false;
  state.clipboard = null;
  doc.getElementById('sdt-journal-copy').fire('click');
  assert.equal(doc.getElementById('sdt-journal-copy-status').textContent,
    'Copy failed: clipboard unavailable.');
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
  assert(doc.getElementById('sdt-status').textContent.startsWith('Files indexed'),
    'the rest of the redraw did not run');
  ui.Zotero.Prefs.get = working;
});

test('a torn-down ring degrades to a message instead of throwing', () => {
  const ring = ui.journal;
  ui.journal = { tail() { throw new Error('ring gone'); } };
  ui.render();
  assert.equal(doc.getElementById('sdt-journal').textContent, 'Log unreadable: Error');
  ui.journal = ring;
});

/* The arm the clipboard invariant actually rests on, and the one the first draft
   of this file got wrong. Assigning `ui.environment` by hand never contaminates
   the ring, so asserting the clipboard is clean proved nothing: it was a null
   result with no positive control, which is the shape that reads like evidence
   and is not.

   Here the real `emit('startup', environment)` runs, from the real
   `initialize()`, into a ring that already exists. That is not a contrived
   state: `journal ??=` keeps the ring across a disable/re-enable, which is
   exactly what the sitter's own "turn the add-on off, then on again" tells
   the author to do. Halted at `uiReadyPromise`, the first thing after the
   startup record, as tests/sdt_sitter_startup.mjs halts it. */
async function driveReinitialisation() {
  const host = ui.Zotero;
  ui.Zotero = {
    initializationPromise: Promise.resolve(),
    // Lazily rejected, so nothing is an unhandled rejection before the await.
    get uiReadyPromise() { return Promise.reject(new Error('halt: after the self-check')); },
    version: '10.0.5-stub',
    debug: () => {},
    logError: () => {},
    Prefs: host.Prefs,
    File: { getContentsFromURLAsync: async url => {
      assert.equal(url, `${INSTALL_PATH}manifest.json`, 'the manifest is not read from rootURI');
      return fs.readFileSync('plugins/sdt-sitter/manifest.json', 'utf8');
    } },
  };
  await assert.rejects(ui.initialize(INSTALL_PATH, 0), /halt: after the self-check/);
  ui.Zotero = host;
}

await driveReinitialisation();

test('a re-initialization contaminates the ring, and the clipboard still holds no path', () => {
  // The positive control, first and load-bearing: without it the two assertions
  // below pass whether or not the scrub exists.
  const startup = Array.from(ui.journal.tail(50)).filter(record => record.kind === 'startup');
  assert.equal(startup.length, 1, 'the real startup record never reached the ring');
  assert.equal(startup[0].rootURI, INSTALL_PATH,
    'the ring was not contaminated, so this arm would prove nothing');
  // On screen the path stays: the panel prints it two lines above, on the
  // author's own machine. The difference between the channels is the point.
  assert(ui.describeSDTJournalTail(50).includes(INSTALL_PATH),
    'the on-screen tail hides what the panel shows deliberately');

  state.copyAvailable = true;
  doc.getElementById('sdt-journal-copy').fire('click');
  assert(!state.clipboard.includes(INSTALL_PATH), 'the install path reached the clipboard');
  assert(!state.clipboard.includes('/home/tester'), state.clipboard);
  assert(!state.clipboard.includes('file://'), state.clipboard);
  // Surgical, not a whole-record drop: deleting the startup record entirely
  // would satisfy every assertion above and lose the build identity that makes
  // a pasted ring worth reading.
  const copied = JSON.parse(state.clipboard).records.filter(record => record.kind === 'startup');
  assert.equal(copied.length, 1, 'the scrub dropped the record instead of the field');
  assert.equal(copied[0].zoteroVersion, '10.0.5-stub');
  assert.equal(copied[0].rootURI, undefined);
});

console.log(JSON.stringify({ tests: results, result: 'pass' }));
