// Bounded synthetic tests of the writer and reader bundled with Zotero.
// Arguments may be process-substitution paths; no library or output file is opened.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { deflateRawSync, inflateRawSync } from 'node:zlib';

assert.equal(process.argv.length, 5, 'Expected worker, reader and metadata paths');
const [worker, readerSource, metadataText] = process.argv.slice(2).map(path => readFileSync(path, 'utf8'));
const metadata = JSON.parse(metadataText);
const start = worker.indexOf(';// ./structured-document-text/src/pack/bytes.js');
const end = worker.indexOf(';// ./src/index.js', start);
assert.ok(start >= 0 && end > start, 'Writer module anchors changed');
const warnings = [];
let serialized = [];
const shared = { Uint8Array, ArrayBuffer, TextEncoder, TextDecoder };
const writerContext = vm.createContext({
  ...shared,
  SDT_PACK_VERSION: metadata.SDT_PACK_VERSION,
  console: { warn: value => warnings.push(value) },
  JSON: { stringify(value) {
    const json = JSON.stringify(value);
    serialized.push({ value, codeUnits: json.length, utf8Bytes: Buffer.byteLength(json) });
    return json;
  } },
});
vm.runInContext(worker.slice(start, end), writerContext);
const readerContext = vm.createContext({ ...shared, module: { exports: {} } });
vm.runInContext(readerSource, readerContext);
const { openStructuredDocumentTextPack } = readerContext.module.exports;
const normalize = value => JSON.parse(JSON.stringify(value));
const sha = value => createHash('sha256').update(value).digest('hex');
const cases = [];

for (const fixture of ['many-small-blocks', 'single-oversized-block']) {
  const blocks = fixture === 'many-small-blocks' ? 10000 : 1;
  const text = fixture === 'many-small-blocks'
    ? 'Économie, 数学, 😀 — '.repeat(16)
    : 'Économie, 数学, 😀 — '.repeat(65536);
  const structure = {
    schemaVersion: metadata.SDT_SCHEMA_VERSION,
    metadata: {
      processor: { type: 'pdf', version: metadata.SDT_PROCESSOR_VERSIONS.pdf },
      dateCreated: '2026-09-05T00:00:00.000Z',
      source: { contentType: 'application/pdf', hash: '0'.repeat(32), properties: {} },
    },
    catalog: {
      pages: Array.from({ length: blocks }, (_, i) => ({
        viewRect: [0, 0, 600, 800], contentRange: [[i], [i + 1]],
      })),
      outline: [],
    },
    content: Array.from({ length: blocks }, (_, i) => ({
      type: 'paragraph', anchor: { pageRects: [[i, 0, 0, 600, 800]] },
      content: [{ type: 'text', text: `${i}: ${text}` }],
    })),
  };
  const expected = JSON.stringify(structure);
  const originalContent = structure.content;
  serialized = [];
  const warningStart = warnings.length;
  const pack = writerContext.packStructuredDocumentText(structure, {
    destructive: true, deflate: deflateRawSync,
  });
  assert.ok(originalContent.every(block => block === null));
  assert.ok(serialized.every(entry => entry.value !== structure && entry.value !== originalContent));
  assert.equal(serialized.length, blocks + 2);
  const reader = await openStructuredDocumentTextPack(pack, { inflate: inflateRawSync });
  assert.equal(reader.getTopLevelBlockCount(), blocks);
  const materialized = await reader.materialize();
  assert.equal(JSON.stringify(materialized), expected);
  assert.deepEqual(normalize(await reader.getBlock([blocks - 1])), normalize(materialized.content.at(-1)));
  assert.deepEqual(normalize(await reader.getPageBlocks(blocks - 1)), [normalize(materialized.content.at(-1))]);
  assert.deepEqual(normalize(await reader.getBlocks(0, Math.min(blocks - 1, 100))), normalize(materialized.content.slice(0, 101)));
  const chunks = reader.index.chunkBlockStarts.length - 1;
  if (blocks === 1) {
    assert.equal(chunks, 1, 'Oversized block should remain a single chunk');
    assert.equal(warnings.length - warningStart, 1);
  } else {
    assert.ok(chunks > 1);
    assert.equal(warnings.length - warningStart, 0);
  }
  cases.push({
    fixture, blocks, chunks, packBytes: pack.byteLength,
    packSha256: sha(new Uint8Array(pack)),
    maximumJsonCodeUnits: Math.max(...serialized.map(entry => entry.codeUnits)),
    maximumJsonUtf8Bytes: Math.max(...serialized.map(entry => entry.utf8Bytes)),
    serializationCalls: serialized.length,
    warnings: warnings.slice(warningStart),
    checks: ['destructive-release', 'no-whole-content-stringify', 'full-roundtrip', 'last-block', 'last-page', 'block-range'],
  });
}

// Exercise real accounting with a tiny payload, not a giant allocation.
assert.throws(() => writerContext.appendContentChunk([], 0xffffffff,
  [new Uint8Array([1])], deflateRawSync), /exceeds v1 4 GiB size limit/);
assert.throws(() => writerContext.writeU32LE(new Uint8Array(4), 0, 0x100000000), /Invalid u32/);
console.log(JSON.stringify({
  workerSha256: sha(worker), readerSha256: sha(readerSource), metadata,
  runtime: process.version,
  scope: 'Installed writer/reader in Node VM; synthetic structures; Node raw-DEFLATE hooks; not PDF extraction or Gecko heap-limit validation',
  cases,
  overflowChecks: ['content-length-rejected-before-append', 'u32-overflow-rejected'],
}, null, 2));
