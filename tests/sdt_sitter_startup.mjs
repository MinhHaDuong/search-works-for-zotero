// The startup self-check of ticket 0688, driven rather than read.
//
// A log line verified by inspection is a log line nobody ran: the call can sit
// after something that throws, name a variable that is not in scope, or be
// unreachable, and every one of those reads fine in a diff. So `initialize` is
// actually invoked here, against a Zotero stub whose `uiReadyPromise` rejects.
// That rejection is the positive control's other half — reaching it proves the
// record was emitted BEFORE the first thing that can fail, which is the whole
// point of where it was placed.
//
// The record goes through 0689's `emit`, so what lands in the debug log is
// `SDT sitter startup {...}` rather than a line of this ticket's own devising.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const SITTER = 'plugins/sdt-sitter';
const manifest = JSON.parse(fs.readFileSync(path.join(SITTER, 'manifest.json'), 'utf8'));
const HALT = /halt: after the self-check/;

const logged = [];
const errors = [];
const context = {
  Zotero: {
    initializationPromise: Promise.resolve(),
    // Rejected lazily, so nothing is an unhandled rejection before initialize awaits it.
    get uiReadyPromise() { return Promise.reject(new Error('halt: after the self-check')); },
    version: '10.0.5-stub',
    debug: message => logged.push(message),
    logError: error => errors.push(String(error)),
    Prefs: { get: () => false },
  },
};
context.Zotero.File = {
  getContentsFromURLAsync: async url => {
    assert.equal(url, `${SITTER}/manifest.json`, 'the manifest is read from rootURI');
    return fs.readFileSync(url, 'utf8');
  },
};
vm.runInNewContext(fs.readFileSync(path.join(SITTER, 'bootstrap.js'), 'utf8'), context);

/** The one `startup` record emitted by a run of initialize, as its detail object. */
async function startupRecord() {
  logged.length = 0;
  await assert.rejects(context.initialize(`${SITTER}/`, 0), HALT);
  const records = logged.filter(line => line.startsWith('SDT sitter startup '));
  assert.equal(records.length, 1,
    `expected exactly one startup record, got ${JSON.stringify(logged)}`);
  return JSON.parse(records[0].slice('SDT sitter startup '.length));
}

let record = await startupRecord();
assert.deepEqual(record, {
  version: manifest.version,
  rootURI: `${SITTER}/`,
  zoteroVersion: '10.0.5-stub',
  strictMinVersion: manifest.applications.zotero.strict_min_version,
  strictMaxVersion: manifest.applications.zotero.strict_max_version,
});

// An unreadable manifest must not be what stops startup: the record still goes
// out, saying so, because a disappearance with NO record is the case this exists
// to distinguish from one whose manifest could not be read. The error's class
// reaches it and its message does not — 0689's rule, and a manifest read failure
// carries a full filesystem path.
context.Zotero.File.getContentsFromURLAsync = async () => {
  const error = new Error('/home/someone/Zotero/extensions/x.xpi is missing');
  error.name = 'NotFoundError';
  throw error;
};
record = await startupRecord();
assert.equal(record.version, 'unreadable (NotFoundError)');
assert.equal(record.zoteroVersion, '10.0.5-stub');
assert(!JSON.stringify(record).includes('/home/someone'), JSON.stringify(record));

// A manifest that parses to something that is not an object. `null` and `3` are
// valid JSON, so the parse succeeds and the shape is what is wrong; before this
// was checked, `null` threw and the diagnostic aborted the startup it explains.
for (const [document, shape] of [['null', 'object'], ['3', 'number'],
  ['"text"', 'string'], ['true', 'boolean']]) {
  context.Zotero.File.getContentsFromURLAsync = async () => document;
  record = await startupRecord();
  assert.equal(record.version, `unreadable (${shape})`, document);
  assert.equal(record.zoteroVersion, '10.0.5-stub', document);
}
// An array IS an object; it simply has no version, which reads as undefined
// rather than as a lie about one.
context.Zotero.File.getContentsFromURLAsync = async () => '[]';
record = await startupRecord();
assert.equal(record.version, undefined);

// The two ways the self-check could itself become a new way to fail startup.
// Both must leave initialize running far enough to reach the rejecting
// uiReadyPromise: reaching it is the assertion, since a throw from the
// diagnostic would surface as its own error instead.
context.Zotero.File.getContentsFromURLAsync = async url => fs.readFileSync(url, 'utf8');

Object.defineProperty(context.Zotero, 'version',
  { configurable: true, get() { throw new Error('version getter is broken'); } });
record = await startupRecord();
assert.equal(record.zoteroVersion, '<unreadable>');
assert.equal(record.version, manifest.version, 'the rest of the record survives');
Object.defineProperty(context.Zotero, 'version',
  { configurable: true, value: '10.0.5-stub', writable: true });

// `emit` swallows a failing debug by design (0689); what this arm proves is that
// the swallow holds all the way out to initialize, which is where it matters.
logged.length = 0;
context.Zotero.debug = () => { throw new Error('debug is unavailable'); };
await assert.rejects(context.initialize(`${SITTER}/`, 0), HALT);
assert.equal(logged.length, 0);
context.Zotero.debug = message => logged.push(message);

// The version the HOST hands us survives a manifest that cannot be read, which
// is the case every installed add-on is actually in: `rootURI` is a `jar:` URL
// and `Zotero.File` cannot parse one, so the read below fails in production on
// every startup. Until ticket 0727 the record therefore said
// `version: "unreadable (NS_ERROR_FAILURE)"` in the field whose entire purpose
// is to name the build that was running when the plugin disappeared — the
// instrumentation of ticket 0688, defeated by the same defect that made every
// UI string render as its own id.
context.Zotero.File.getContentsFromURLAsync = async () => {
  const error = new Error('jar:file:///…/x.xpi!/manifest.json');
  error.name = 'NS_ERROR_FAILURE';
  throw error;
};
context.installedVersion = '9.9.9-handed';
record = await startupRecord();
assert.equal(record.version, '9.9.9-handed',
  'the handed version did not survive an unreadable manifest');
// And it is preferred over a manifest that CAN be read, so the two cannot
// disagree about which build is running.
context.Zotero.File.getContentsFromURLAsync = async url => fs.readFileSync(url, 'utf8');
record = await startupRecord();
assert.equal(record.version, '9.9.9-handed');
assert.notEqual(manifest.version, '9.9.9-handed', 'the arm above proves nothing');
context.installedVersion = null;

console.log(JSON.stringify({ tests: [
  'startup record', 'unreadable manifest carries a class and no path',
  'manifest of the wrong shape', 'Zotero.version throws', 'Zotero.debug throws',
  'the host-handed version survives an unreadable manifest and wins over a readable one',
], result: 'pass' }));
