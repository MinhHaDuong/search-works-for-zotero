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

console.log(JSON.stringify({ tests: ['startup self-check', 'unreadable manifest'], result: 'pass' }));
