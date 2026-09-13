// What establishes "this native pack is verifiably empty" rather than "we could
// not tell" — measured against Zotero's OWN shipped pack reader, not against a
// mock of it, and against the author's own packs on disk. Ticket 0760.
//
// The question the ticket asks is whether the format offers an authoritative
// complete-content indicator. It offers no POSITIVE one: the reader exposes no
// hasText, no textLength, no block-type summary. What it offers instead is a
// refusal — `open()` validates the index shape and ties the declared content
// extent to the file's own length, so a pack that opens has already proved its
// block index describes the whole file — and one negative indicator, the
// catalog's per-page `extractionDegraded` stamp. Emptiness is therefore the
// enumeration of exactly `getTopLevelBlockCount()` blocks with no non-whitespace
// run in any of them, over a catalog that reports no degraded page. "Unknown"
// is anything that threw on the way, and anything the catalog will not vouch for.
//
// That distinction is worthless unless the refusal actually fires, so the
// controls below corrupt a real pack four ways and require a throw from each.
// A probe that only ever saw well-formed packs would report the same "all
// clear" whether the validation existed or not.
//
// Reads only. Emits no title, no text, no storage key and no path beyond the
// two roots it was given.
//
// Usage:
//   node verification/empty-pack-0760/probe.mjs \
//     <zotero-app>/resource/document-worker/structured-document-text.js \
//     ~/Zotero/storage
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import vm from 'node:vm';
import { inflateRawSync } from 'node:zlib';

assert.equal(process.argv.length, 4, 'Expected a reader source path and a storage directory');
const [readerPath, storageRoot] = process.argv.slice(2);

const readerContext = vm.createContext({
  Uint8Array, ArrayBuffer, TextEncoder, TextDecoder, JSON, Math, Number, Array, Error, TypeError,
  module: { exports: {} },
});
vm.runInContext(readfile(readerPath), readerContext);
const { openStructuredDocumentTextPack } = readerContext.module.exports;
assert.equal(typeof openStructuredDocumentTextPack, 'function', 'the reader source exported nothing openable');

function readfile(path) { return readFileSync(path, 'utf8'); }
const open = bytes => openStructuredDocumentTextPack(bytes, { inflate: inflateRawSync });

/* The plugin's own predicate, copied verbatim from plugins/sdt-sitter/bootstrap.js
   so this measures what ships rather than a second opinion about it. The
   recursion is load-bearing: a `list` block holds its runs one level down inside
   `listitem` children, and a flat read of the top level sees no text at all in a
   bibliography. */
const blockHasSDTText = block => {
  if (!block || typeof block !== 'object') return false;
  if (typeof block.text === 'string' && block.text.trim()) return true;
  return Array.isArray(block.content) && block.content.some(blockHasSDTText);
};

/* Whether the pack's own catalog vouches for every page. The native worker has
   fallback paths for inference overload and per-page inference errors, and a
   page that took one is stamped `extractionDegraded`
   (verification/SDT-PALGRAVE-AUDIT.md, reading worker.js:143251 and 153043).
   This is the closest thing the format has to a completeness indicator, and it
   is a NEGATIVE one: it cannot confirm that text was found, only withdraw the
   claim that its absence was established. */
async function extractionComplete(reader) {
  if (typeof reader.getCatalog !== 'function') return { complete: false, reason: 'no catalog accessor' };
  let catalog = null;
  try { catalog = await reader.getCatalog(); }
  catch (error) { return { complete: false, reason: `catalog unreadable: ${error.message}` }; }
  const pages = catalog?.pages;
  if (!Array.isArray(pages) || !pages.length) return { complete: false, reason: 'no page records' };
  const degraded = pages.filter(page => page?.extractionDegraded).length;
  return { complete: degraded === 0, pages: pages.length, degraded,
    reason: degraded ? `${degraded} degraded page(s)` : null };
}

/* One block at a time, exactly as `packSDTTextVerdict` walks it: the point of
   the measurement is the verdict of the shipped loop, not of a faster one this
   file could have written. Three answers, because two would be the defect —
   "no text found" and "no text present" are the same observation only when the
   catalog says the whole document was actually read. */
async function inspect(bytes) {
  const reader = await open(bytes);
  const count = reader.getTopLevelBlockCount();
  if (!Number.isInteger(count) || count < 0) throw new Error('Invalid native block count');
  let read = 0;
  for (let index = 0; index < count; index++) {
    const blocks = await reader.getBlocks(index, index);
    if (!Array.isArray(blocks)) throw new Error('Invalid native block range');
    read += blocks.length;
    if (blocks.some(blockHasSDTText)) {
      return { verdict: 'text', declaredBlocks: count, blocksRead: read, blocksScanned: index + 1 };
    }
  }
  const complete = await extractionComplete(reader);
  return { verdict: complete.complete ? 'empty' : 'unknown', declaredBlocks: count,
    blocksRead: read, blocksScanned: count, completeness: complete };
}

/* ---- 1. the reader's surface: what could an indicator even be read off? ---- */
const sample = findPacks(storageRoot);
assert.ok(sample.length, `no .zotero-sdt-cache under ${storageRoot}`);
const probeReader = await open(readFileSync(sample[0]));
const surface = [...new Set([
  ...Object.getOwnPropertyNames(probeReader),
  ...Object.getOwnPropertyNames(Object.getPrototypeOf(probeReader)),
])].filter(name => name !== 'constructor').sort();

function findPacks(root) {
  const found = [];
  for (const entry of readdirSync(root)) {
    const candidate = join(root, entry, '.zotero-sdt-cache');
    try { if (statSync(candidate).isFile()) found.push(candidate); } catch { /* no pack here */ }
  }
  return found.sort();
}

/* ---- 2. the author's own packs, classified by the shipped loop ---- */
const census = { packs: 0, text: 0, empty: 0, unknown: 0, unreadable: 0,
  pages: 0, degradedPages: 0, packsWithDegradedPages: 0, emptyBlockCounts: [], errors: {} };
let widest = null;
for (const path of sample) {
  census.packs++;
  const bytes = readFileSync(path);
  try {
    const result = await inspect(bytes);
    census[result.verdict]++;
    const completeness = result.completeness ?? await extractionComplete(await open(bytes));
    census.pages += completeness.pages ?? 0;
    census.degradedPages += completeness.degraded ?? 0;
    if (completeness.degraded) census.packsWithDegradedPages++;
    if (result.verdict === 'empty') census.emptyBlockCounts.push(result.declaredBlocks);
    // Every block the loop asked for came back. A short read here would be the
    // silent under-report the whole classification rests on not happening.
    assert.equal(result.blocksRead, result.blocksScanned,
      'the reader returned fewer blocks than the range asked for');
    if (!widest || result.declaredBlocks > widest.declaredBlocks) widest = { ...result, bytes };
  } catch (error) {
    census.unreadable++;
    census.errors[error.message] = (census.errors[error.message] || 0) + 1;
  }
}

/* ---- 3. the controls: corruption must throw, never read as empty ---- */
/* This is the half that makes the two paragraphs above mean anything. Each
   mutation takes a real, non-empty pack and breaks one of the four things the
   reader checks. The requirement is not merely "different answer" — it is that
   the answer is an exception, because `packSDTTextVerdict`'s caller turns a throw
   into `invalid-pack` and turns a `false` into `empty-pack`. A mutation that
   came back `empty` would be a scanned page silently reported as "No extracted
   text" on the strength of a truncated file. */
const control = readFileSync(sample.find(path => {
  const bytes = readFileSync(path);
  return bytes.length > 64;
}) ?? sample[0]);
assert.ok(control.length > 64, 'no pack large enough to corrupt');

const u32 = (buf, offset, value) => { const copy = Buffer.from(buf); copy.writeUInt32LE(value, offset); return copy; };
const HEADER_SIZE = 16;
const indexLength = control.readUInt32LE(12);
const entryCount = (indexLength - 8) / 8;

const mutations = {
  // The magic is the cheapest thing an unrelated file can fail.
  'flipped magic byte': (() => { const copy = Buffer.from(control); copy[3] ^= 0xff; return copy; })(),
  // One byte short: the layout check ties the declared content extent to the
  // file length, so a pack still being written cannot present as a short list.
  'truncated by one byte': control.subarray(0, control.length - 1),
  // The index claims the content ends before it does -- the shape a partial
  // write leaves behind, and the one that would under-report blocks.
  'content extent understated': u32(control, HEADER_SIZE + 8 + (entryCount - 1) * 4, 0),
  // The block index declares zero blocks over a content region that holds
  // some. This is the mutation that would manufacture a false "verified empty".
  'block index zeroed': u32(control, HEADER_SIZE + 8 + entryCount * 4 + (entryCount - 1) * 4, 0),
};

const controls = {};
for (const [name, bytes] of Object.entries(mutations)) {
  let outcome;
  try {
    const result = await inspect(bytes);
    outcome = { threw: false, verdict: result.verdict, declaredBlocks: result.declaredBlocks };
  } catch (error) { outcome = { threw: true, error: error.message }; }
  controls[name] = outcome;
  assert.equal(outcome.threw, true,
    `${name}: the reader answered ${JSON.stringify(outcome)} instead of refusing — ` +
    'a corrupt pack that returns a block count can be classified as verified empty');
}

console.log(JSON.stringify({
  readerSource: readerPath,
  storageRoot,
  // No field on this list can answer "does this document have text": the
  // enumeration is the only route, which is what Action 1 of the ticket asked.
  readerSurface: surface,
  census: { ...census, emptyBlockCounts: census.emptyBlockCounts.sort((a, b) => a - b) },
  widestPackScanned: widest && { declaredBlocks: widest.declaredBlocks, verdict: widest.verdict,
    blocksScannedBeforeVerdict: widest.blocksScanned, packBytes: widest.bytes.length },
  controls,
  verdict: 'every corruption refused; emptiness is enumeration plus a validated layout',
}, null, 2));
