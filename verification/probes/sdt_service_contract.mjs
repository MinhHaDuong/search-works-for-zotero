/** Execute the installed SDT service with simulated host, storage and worker.
 * This tests orchestration, NOT PDF extraction, pack parsing or Gecko integration.
 * Usage: node verification/probes/sdt_service_contract.mjs /path/to/app/omni.ja
 */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import vm from 'node:vm';

const archive = process.argv[2];
if (!archive) throw new Error('Supply the installed app/omni.ja');
const source = execFileSync('unzip', ['-p', archive,
  'chrome/content/zotero/xpcom/sdt.js'], { encoding: 'utf8' });
const metadata = JSON.parse(execFileSync('unzip', ['-p', archive,
  'resource/document-worker/metadata.json'], { encoding: 'utf8' }));
const encode = value => new TextEncoder().encode(JSON.stringify(value));
const defer = () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
};
function fixture() {
  const f = { file: null, hash: 'original', mtime: 1, calls: 0,
    writes: 0, readBytes: 0, priority: null, failure: null,
    workerGate: null, writeGate: null, entered: defer(), writing: defer() };
  const item = {
    id: 1, key: 'FIXTURE1', libraryID: 1, libraryKey: '1/FIXTURE1',
    isAttachment: () => true, isPDFAttachment: () => true,
    getFilePathAsync: async () => '/fixture/source.pdf',
    get attachmentHash() { return Promise.resolve(f.hash); },
  };
  f.pack = (version = metadata.SDT_PROCESSOR_VERSIONS.pdf, hash = f.hash) =>
    encode({ source: { hash }, processor: { type: 'pdf', version } });
  const context = {
    Uint8Array, Map, Set,
    require: name => name === 'pako' ? { inflateRaw: x => x } : {
      ...metadata,
      openStructuredDocumentTextPack: async src => ({
        header: { packVersion: metadata.SDT_PACK_VERSION,
          schemaVersion: metadata.SDT_SCHEMA_VERSION },
        getMetadata: async () => JSON.parse(new TextDecoder().decode(
          await src.read(0, src.byteLength))),
      }),
    },
    PathUtils: { join: (...p) => p.join('/'), parent: () => '/fixture/cache' },
    IOUtils: {
      stat: async () => ({ size: 100, lastModified: f.mtime }),
      read: async () => {
        if (!f.file) throw Object.assign(new Error('missing'), { name: 'NotFoundError' });
        f.readBytes += f.file.byteLength;
        return f.file;
      },
      write: async (path, bytes, options) => {
        f.writing.resolve();
        if (f.writeGate) await f.writeGate.promise;
        if (f.writeFailure) throw new Error('simulated disk full');
        assert.equal(options.tmpPath, `${path}.tmp`);
        f.file = bytes; f.writes++;
      },
    },
    Zotero: {
      debug() {}, logError() {},
      Items: { getAsync: async () => item },
      Attachments: { getStorageDirectory: () => ({ path: '/fixture/cache' }) },
      File: { createDirectoryIfMissingAsync: async () => {},
        getContentsFromURLAsync: async () => JSON.stringify(metadata) },
      PDFWorker: { getStructuredDocumentText: async (id, opts) => {
        f.calls++; f.priority = opts.isPriority;
        const bytes = f.pack();
        f.entered.resolve();
        opts.onProgress(0);
        if (f.workerGate) await f.workerGate.promise;
        if (f.failure) throw f.failure;
        opts.onProgress(100);
        return { buf: bytes.buffer };
      } },
    },
  };
  vm.runInNewContext(source, context, { filename: 'installed-sdt.js' });
  f.sdt = context.Zotero.SDT;
  return f;
}
const results = [];
async function check(name, test) {
  await test(); results.push({ name, result: 'pass' });
}
await check('current cache: no worker or write, but whole pack read', async () => {
  const f = fixture(); f.file = f.pack();
  assert.equal(await f.sdt.ensure(1), true);
  assert.equal(f.calls, 0); assert.equal(f.writes, 0);
  assert.equal(f.readBytes, f.file.byteLength);
});
await check('missing cache: background generation and subsequent cache hit', async () => {
  const f = fixture();
  assert.equal(await f.sdt.ensure(1), true);
  assert.equal(f.priority, false); assert.equal(f.writes, 1);
  assert.equal(await f.sdt.ensure(1), true); assert.equal(f.calls, 1);
});
await check('stale processor: ensure regenerates', async () => {
  const f = fixture(); f.file = f.pack(metadata.SDT_PROCESSOR_VERSIONS.pdf + 1);
  assert.equal(await f.sdt.ensure(1), true); assert.equal(f.calls, 1);
});
await check('concurrent callers share work and both receive progress', async () => {
  const f = fixture(); f.workerGate = defer();
  const a = [], b = [];
  const first = f.sdt.ensure(1, { onProgress: n => a.push(n) });
  await f.entered.promise;
  const second = f.sdt.ensure(1, { isPriority: true, onProgress: n => b.push(n) });
  await new Promise(r => setImmediate(r));
  f.workerGate.resolve();
  assert.deepEqual(await Promise.all([first, second]), [true, true]);
  assert.equal(f.calls, 1); assert.equal(f.priority, false);
  assert.deepEqual(a, [0, 100]); assert.deepEqual(b, [0, 100]);
});
await check('100 percent precedes persistence and ensure completion', async () => {
  const f = fixture(); f.writeGate = defer();
  let complete = false, progress;
  const pending = f.sdt.ensure(1, { onProgress: n => { progress = n; } })
    .then(ok => { complete = true; return ok; });
  await f.writing.promise;
  assert.equal(progress, 100); assert.equal(complete, false); assert.equal(f.file, null);
  f.writeGate.resolve(); assert.equal(await pending, true);
});
await check('changed source during extraction: reject generated pack', async () => {
  const f = fixture(); f.workerGate = defer();
  const pending = f.sdt.ensure(1); await f.entered.promise;
  f.hash = 'changed'; f.mtime++;
  f.workerGate.resolve();
  assert.equal(await pending, false); assert.equal(f.writes, 0);
});
await check('write failure returns false without exposing reason', async () => {
  const f = fixture(); f.writeFailure = true;
  assert.equal(await f.sdt.ensure(1), false); assert.equal(f.file, null);
});
await check('password failure memoized in session until source changes', async () => {
  const f = fixture(); f.failure = Object.assign(new Error('locked'), { name: 'PasswordException' });
  assert.equal(await f.sdt.ensure(1), false);
  assert.equal(await f.sdt.ensure(1), false); assert.equal(f.calls, 1);
  f.hash = 'changed'; f.mtime++;
  assert.equal(await f.sdt.ensure(1), false); assert.equal(f.calls, 2);
});
await check('generic failure is not memoized: caller must prevent retry loop', async () => {
  const f = fixture(); f.failure = new Error('worker failed');
  assert.equal(await f.sdt.ensure(1), false);
  assert.equal(await f.sdt.ensure(1), false); assert.equal(f.calls, 2);
});
console.log(JSON.stringify({ scope: 'installed service; mocked host, parser, storage and worker',
  source_sha256: createHash('sha256').update(source).digest('hex'), metadata, results }, null, 2));
