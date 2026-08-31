// Does zotero#6012's chunker align to paragraphs on the text WE would feed it?
//
// #6012 chunks paragraph-first: "Paragraphs are the topic units, so two never share a
// passage unless one was too small to stand alone" (utilities_internal.js). That is our
// ratified geometry (spec/DECISIONS.md, 2026-08-30), so the design reads as adoptable
// wholesale. This probe measures the one detail that decides whether it is.
//
// The detail: `_measureParagraphs` splits on /[^\n]+/g. The unit is a LINE, not a
// blank-line-delimited paragraph, and the grouping loop that follows accumulates lines
// until `minSize` with no check for a blank-line gap anywhere. Blank lines carry no
// signal. So the algorithm is paragraph-aligned exactly when newlines already MEAN
// paragraph breaks -- true for notes (HTML-derived) and for SDT blocks, which is what
// #6012 feeds it, and false for `.zotero-ft-cache`, where the extractor hard-wraps every
// line. Ticket 0120's survey is why that matters here: the cache is the only text surface
// the local API exposes, so it is the text any consumer of ours would hand this chunker.
//
// Three arms over the same four ~150-word single-topic paragraphs, so the only thing that
// varies is the newline shape:
//   (a) one line per paragraph  -- what a structure-preserving extractor gives
//   (b) hard-wrapped             -- what the cache actually holds
//   (c) hard-wrapped, unwrapped first (collapse newlines inside a block, keep blank lines)
//
// Measured 2026-08-31 at PR head 77e2c4b, the same head spec/CONSTRAINTS.md read:
//   (a) 4 chunks, one topic each, none straddling
//   (b) 6 chunks, 2 straddling two topics, several opening mid-sentence
//   (c) 4 chunks, identical to (a)
//
// So adopting the geometry does not by itself buy paragraph alignment on our text; the
// unwrap in (c) is what buys it, and it is one line. Read alongside spec/CONSTRAINTS.md's
// entry on the same PR, which owns the geometry (120 / 768 / 48) and the effective-budget
// caveat -- this probe owns only the newline question and settles no number of its own.
//
// LICENCE: Zotero is AGPL-3.0 and zoteus is MIT, so no Zotero source is vendored here.
// The chunker is extracted from a local checkout at RUN time into a temporary module and
// never committed; ticket 0140 ruled the design adoptable as specification and the source
// not. This probe reads the source to measure its behaviour, which is the same thing a
// review does, and produces a specification-level fact.
//
//     node verification/probes/zotero-6012-chunker-probe.mjs --zotero /path/to/zotero
//
// The checkout must be at the PR head, not main: `git fetch --depth 1 origin
// refs/pull/6012/head` in a clone of zotero/zotero, then check out FETCH_HEAD.
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const { values: opt } = parseArgs({
  options: {
    zotero: { type: 'string', default: '/home/user/zotero-6012' },
    width: { type: 'string', default: '80' },
  },
});

// The namespace, located by its own markers rather than by line number: #6012 is a live
// branch and a hardcoded span would silently extract the wrong text after any rebase.
function extractChunking(zoteroRoot) {
  const path = join(zoteroRoot, 'chrome/content/zotero/xpcom/utilities_internal.js');
  const source = readFileSync(path, 'utf8');
  const open = 'Zotero.Utilities.Internal.Chunking = new function () {';
  const from = source.indexOf(open);
  if (from < 0) {
    throw new Error(`${path}: no Zotero.Utilities.Internal.Chunking -- wrong revision?`);
  }
  // Ends at the first line that closes a top-level `new function () {` block.
  const rest = source.slice(from);
  const end = rest.search(/\n\};\s*\n/);
  if (end < 0) throw new Error('Chunking namespace has no top-level close');
  const body = rest.slice(0, end + 4);
  const dir = mkdtempSync(join(tmpdir(), 'zot6012-'));
  const module = join(dir, 'chunking.mjs');
  writeFileSync(
    module,
    'const Zotero = { Utilities: { Internal: {} } };\n'
      + body
      + '\nexport const Chunking = Zotero.Utilities.Internal.Chunking;\n',
  );
  return module;
}

// Four paragraphs, one topic each, each long enough to stand alone against the 120-token
// minimum. Synthetic on purpose: a real extraction confounds the newline question with
// every other thing extraction does to text, and the newline question is the whole probe.
const TOPICS = ['Alpha', 'Beta', 'Gamma', 'Delta'];
const paragraphs = TOPICS.map((topic) =>
  Array.from(
    { length: 12 },
    (_, i) => `${topic} sentence ${i + 1} carries a distinct claim about the subject at hand.`,
  ).join(' '));

const hardWrap = (text, width) =>
  text.replace(new RegExp(`(.{1,${width}})(\\s|$)`, 'g'), '$1\n').trim();

// The candidate fix: collapse the newlines INSIDE a block, keep blank lines as breaks.
const unwrap = (text) =>
  text
    .split(/\n\s*\n/)
    .map((block) => block.replace(/\s*\n\s*/g, ' ').trim())
    .filter(Boolean)
    .join('\n');

function report(label, chunks) {
  let straddling = 0;
  const lines = [];
  for (const chunk of chunks) {
    const flat = chunk.text.replace(/\s+/g, ' ');
    const topics = TOPICS.filter((t) => flat.includes(`${t} sentence`));
    if (topics.length > 1) straddling++;
    lines.push(
      `    ${String(chunk.size).padStart(4)} chars | ${topics.join('+') || '-'}`
        + ` | "${flat.slice(0, 44)}…"`,
    );
  }
  console.log(`\n=== ${label}`);
  console.log(`    ${chunks.length} chunks, ${straddling} straddling more than one topic`);
  console.log(lines.join('\n'));
  return { chunks: chunks.length, straddling };
}

const { Chunking } = await import(pathToFileURL(extractChunking(opt.zotero)).href);
const width = Number(opt.width);
const clean = paragraphs.join('\n\n');
const cache = paragraphs.map((p) => hardWrap(p, width)).join('\n\n');

const arms = [
  ['(a) one line per paragraph — a structure-preserving extractor', clean],
  ['(b) hard-wrapped — what .zotero-ft-cache actually holds', cache],
  ['(c) hard-wrapped, unwrapped first — the candidate fix', unwrap(cache)],
];

const metrics = Chunking.getCharacterMetrics(clean);
console.log(
  `character metrics: budget ${metrics.budget} chars, min ${metrics.minSize},`
    + ` overlap ${metrics.overlap}`,
);
const results = arms.map(([label, text]) => report(label, Chunking.chunkText(text, metrics)));

const [a, b, c] = results;
console.log(
  `\nverdict: paragraph-aligned on (a) ${a.straddling === 0}, on (b) ${b.straddling === 0},`
    + ` on (c) ${c.straddling === 0}`,
);
