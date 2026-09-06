// The startup self-check of ticket 0688, driven rather than read.
//
// A log line verified by inspection is a log line nobody ran: the call can sit
// after something that throws, name a variable that is not in scope, or be
// unreachable, and every one of those reads fine in a diff. So `initialize` is
// actually invoked here, against a Zotero stub whose `uiReadyPromise` rejects.
// That rejection is the positive control's other half — it proves the line is
// emitted BEFORE the first thing that can fail, which is the whole point of
// where it was placed.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const SITTER = 'bench/sdt-sitter';
const manifest = JSON.parse(fs.readFileSync(path.join(SITTER, 'manifest.json'), 'utf8'));

const logged = [];
const context = {
  Zotero: {
    initializationPromise: Promise.resolve(),
    // Rejected lazily, so nothing is an unhandled rejection before initialize awaits it.
    get uiReadyPromise() { return Promise.reject(new Error('halt: after the self-check')); },
    version: '10.0.5-stub',
    debug: message => logged.push(message),
    logError: () => {},
  },
};
context.Zotero.File = {
  getContentsFromURLAsync: async url => {
    assert.equal(url, `${SITTER}/manifest.json`, 'the manifest is read from rootURI');
    return fs.readFileSync(url, 'utf8');
  },
};
vm.runInNewContext(fs.readFileSync(path.join(SITTER, 'bootstrap.js'), 'utf8'), context);

await assert.rejects(context.initialize(`${SITTER}/`, 0), /halt: after the self-check/);
assert.equal(logged.length, 1, `expected exactly one startup line, got ${JSON.stringify(logged)}`);
const line = logged[0];
for (const expected of [
  `version=${manifest.version}`,
  `rootURI=${SITTER}/`,
  'zoteroVersion=10.0.5-stub',
  `strictMinVersion=${manifest.applications.zotero.strict_min_version}`,
  `strictMaxVersion=${manifest.applications.zotero.strict_max_version}`,
]) assert(line.includes(expected), `startup line lacks ${expected}: ${line}`);

// An unreadable manifest must not be what stops startup: the line still goes out,
// saying so, because a disappearance with no line at all is the case this exists to
// distinguish from one whose manifest could not be parsed.
logged.length = 0;
context.Zotero.File.getContentsFromURLAsync = async () => { throw new Error('no such file'); };
await assert.rejects(context.initialize(`${SITTER}/`, 0), /halt: after the self-check/);
assert.equal(logged.length, 1);
assert(logged[0].includes('unreadable'), logged[0]);
assert(logged[0].includes('zoteroVersion=10.0.5-stub'), logged[0]);

// A manifest that parses to something that is not an object. `null` and `3` are
// valid JSON, so the parse succeeds and the shape is what is wrong; before this
// was checked, `null` threw and the diagnostic aborted the startup it explains.
for (const document of ['null', '3', '[]', '"text"']) {
  logged.length = 0;
  context.Zotero.File.getContentsFromURLAsync = async () => document;
  await assert.rejects(context.initialize(`${SITTER}/`, 0), /halt: after the self-check/);
  assert.equal(logged.length, 1, `no line for manifest ${document}`);
  assert(logged[0].includes('zoteroVersion=10.0.5-stub'), logged[0]);
}

// The two ways the self-check could itself become a new way to fail startup. Both
// must leave `initialize` running far enough to reach the rejecting uiReadyPromise:
// reaching it is the assertion, since a throw from the diagnostic would surface as
// its own error instead.
context.Zotero.File.getContentsFromURLAsync = async url => fs.readFileSync(url, 'utf8');
const errors = [];
context.Zotero.logError = error => errors.push(String(error));

context.Zotero.debug = () => { throw new Error('debug is unavailable'); };
await assert.rejects(context.initialize(`${SITTER}/`, 0), /halt: after the self-check/);
assert.equal(errors.length, 1, 'a failing Zotero.debug must be reported, not propagated');
assert(errors[0].includes('debug is unavailable'), errors[0]);

logged.length = 0;
errors.length = 0;
context.Zotero.debug = message => logged.push(message);
Object.defineProperty(context.Zotero, 'version',
  { configurable: true, get() { throw new Error('version getter is broken'); } });
await assert.rejects(context.initialize(`${SITTER}/`, 0), /halt: after the self-check/);
assert.equal(logged.length, 0, 'nothing can be logged when the line cannot be built');
assert.equal(errors.length, 1, 'a failing Zotero.version must be reported, not propagated');
assert(errors[0].includes('version getter is broken'), errors[0]);

// And the last resort: reporting the failure must not fail either.
errors.length = 0;
context.Zotero.logError = () => { throw new Error('logError is unavailable too'); };
await assert.rejects(context.initialize(`${SITTER}/`, 0), /halt: after the self-check/);

console.log(JSON.stringify({ tests: [
  'startup self-check', 'unreadable manifest', 'manifest of the wrong shape',
  'Zotero.debug throws', 'Zotero.version throws', 'Zotero.logError throws too',
], result: 'pass' }));
