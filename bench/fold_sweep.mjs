// R19's fold gate (SPEC.md §5.2.8): does the JS query side agree, codepoint by codepoint,
// with what FTS5 actually indexes?
//
// Filed as ticket 0009's probe. R19 ("every token the query side produces MUST be one the
// index side can also produce") turned it into a standing gate, and ticket 0578 Action 5
// gave it the three things a gate needs and a probe does not.
//
// The method is the only one that settles it: put each codepoint through a REAL FTS5 table
// declared with the shipped tokenizer, read back what SQLite stored via `fts5vocab`, and
// compare it with what the shipped JS tokenizer produces for the same input. Nothing here
// reimplements either side.
//
// A divergence is classified by direction, because the two are not equally bad:
//   - `narrows`   the query terms are a subset of the index's: the query retrieves LESS
//                 than it could. Costly, not wrong.
//   - `misses`    the query produces a term the index does not hold, while the index holds
//                 terms of its own: the query goes where the index is not. This is the
//                 0009 defect class and R19's clause, and it is what fails this gate.
//   - `widens`    the query produces a term where the index stores nothing at all.
//
// ── Exit codes ────────────────────────────────────────────────────────────────────────
//   0  agreed — no query term the index cannot produce, at codepoint or word level.
//   1  red — `misses_total` > 0. The count and every case are in the artifact.
//   2  usage error.
//   3  could not look — the tree named by `--fork` has no loadable
//      `dist/features/search/tokenize.js`. A gate that cannot look says so and exits
//      nonzero; it never reports a green it did not measure.
// Before 0578 this script always exited 0, printed a WARNING on a miss, and left the
// caller to notice. A gate that cannot fail is not a gate.
//
// ── The two query-side arms ───────────────────────────────────────────────────────────
// SPEC.md §5.2.8 requires the query side to fall back to `tokenize`-only when
// `normalizeForSearch` is absent, so a pre-fold tree (upstream below v1.7.2, where PR #19
// introduced the fold) is red BY CLASSIFICATION rather than by crash. Which arm ran is
// recorded in the artifact as `query_side`, because the two are not comparable and a
// reader of the numbers must be able to tell them apart:
//   - `normalizeForSearch+class` — the fold, then `[\p{L}\p{N}]+`. These are the same two
//     steps `tokenize` performs, applied here without its length filter, which would
//     otherwise hide every single-character codepoint.
//   - `tokenize-only` — the shipped `tokenize` called as it stands, because a pre-fold
//     `tokenize` fuses its (absent) fold, its token class and its length filter into one
//     function with no separable middle. The filter drops 1-character tokens, so the
//     per-codepoint arm collapses to `narrows` almost everywhere on this arm; that is
//     recorded in `query_side_caveat`, and the word-level regressions are what carry the
//     miss signal. Measured against v1.7.1: the codepoint arm finds no miss and the word
//     arm finds several, which is the shape of the defect PR #19 fixed.
//
// ── Comparing as sets, not as sequences ───────────────────────────────────────────────
// `fts5vocab(probe, row)` returns each DISTINCT term once, ordered by term. The query side
// returns tokens in text order, with repeats. Comparing those two as sequences was
// harmless while every probe produced at most one token, and became wrong the moment this
// sweep gained scripts whose words fragment: `हिन्दी` indexes as {द, न, ह} and queries as
// [ह, न, द] — the same three consonants, called a divergence by an ordering artifact of
// the SQL. So both sides are compared as sets. On every case the old sequence rule
// decided, the set rule decides identically (a set of at most one element).
//
// ── The ranges ────────────────────────────────────────────────────────────────────────
// The scripts are R7's, read from the sheet rather than chosen here: English, French and
// Vietnamese in the MUST tier, and one language per script and morphology class in the
// SHOULD tier — right-to-left (Arabic), Cyrillic (Russian), no word boundaries (Chinese),
// compounding (German), abugida (Hindi), Latin-with-diacritics (Spanish). Latin, Greek,
// Cyrillic and Latin Extended Additional covered six of those. Arabic, Devanagari and CJK
// were added by ticket 0578: 0026's log of 2026-08-31T13:38Z records why they break a
// Latin-plus-Cyrillic sweep's assumptions — Arabic joins letters and drops short vowels,
// Devanagari combines marks and forms conjuncts, and Chinese has no word boundaries at
// all.
//
// No sampling. CJK Unified Ideographs plus Extension A is 27 584 codepoints and the whole
// sweep measures 1,9 s wall clock on the author's machine (doudou, 2026-09-02, under a
// concurrent full-library build) — a sampling rule would have to
// be justified, recorded and defended, and buys nothing against a 3-second gate.
//
// ── What is deliberately NOT swept ────────────────────────────────────────────────────
// U+FDD0–U+FDEF, sixteen of which sit inside Arabic Presentation Forms-A. They are
// permanently reserved noncharacters, which is exactly why the shipped normalizer uses
// them as placeholders for the characters it shields from its own fold. Feeding them in as
// input measures the probe's own scaffolding: the fold hands back the shielded character,
// so all six occupied slots classify as `misses` against an input no document can contain.
// Excluded, with the block split around them rather than silently trimmed.
//
// ── Lone combining marks ──────────────────────────────────────────────────────────────
// In an abugida or a vocalized Arabic text a single codepoint is often a combining mark,
// and the directive for this change asked whether such a case should be excluded from the
// miss count. Measured: it should not, because it never enters it. unicode61 stores a lone
// mark as a term while `[\p{L}\p{N}]+` does not match one, so every lone mark classifies as
// `narrows`. They are flagged in the artifact (`lone_combining_mark`) so a reader can see
// them, and nothing is subtracted — an exclusion no case needs is machinery nobody should
// carry.
import { DatabaseSync } from 'node:sqlite';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const USAGE =
  'usage: node bench/fold_sweep.mjs --output <file.json> [--fork <dir>] [--blocks <substring,...>]';

let opt;
try {
  ({ values: opt } = parseArgs({
    options: {
      fork: { type: 'string', default: new URL('../fork/', import.meta.url).pathname },
      output: { type: 'string' },
      // Re-run one script class after a fix without paying for the other eighteen. A
      // filtered run is recorded as one in the artifact (`blocks_filter`), because a
      // partial green that reads like a full one is the failure this whole file is about.
      blocks: { type: 'string' },
    },
  }));
} catch (why) {
  console.error(`${why.message}\n${USAGE}`);
  process.exit(2);
}
if (!opt.output) {
  console.error(USAGE);
  process.exit(2);
}

// `--fork` is a checkout root, given by whoever runs the gate and therefore arbitrary:
// relative or absolute, with or without a trailing slash. The old code pasted it straight
// in front of `dist/...`, so an absolute path without the slash silently addressed a
// sibling directory and a relative one resolved against the process's cwd rather than the
// caller's intent.
const tree = isAbsolute(opt.fork) ? resolve(opt.fork) : resolve(process.cwd(), opt.fork);
const modulePath = resolve(tree, 'dist/features/search/tokenize.js');

/** Exit 3 with a diagnostic naming what is missing, never a stack trace. */
function cannotLook(why) {
  console.error(
    `NOT-RUN: ${why}\n` +
      `  tree:   ${tree}\n` +
      `  wanted: ${modulePath}\n` +
      `  A built checkout is needed. From the checkout: npm install && npm run build.\n` +
      `  The repository's own is recreated by \`make upstream-checkout\`.`,
  );
  process.exit(3);
}

if (!existsSync(tree)) cannotLook('no such checkout');
if (!existsSync(modulePath)) {
  cannotLook('the checkout is not built — dist/features/search/tokenize.js is absent');
}

let shipped;
try {
  shipped = await import(pathToFileURL(modulePath).href);
} catch (why) {
  cannotLook(`dist/features/search/tokenize.js would not load (${why.message})`);
}

const { tokenize, normalizeForSearch } = shipped;
if (typeof tokenize !== 'function') {
  cannotLook('dist/features/search/tokenize.js exports no `tokenize` — this is not the module the gate reads');
}

// Provenance: an absolute path says where the gate ran, not what it ran against. The
// version pins the tree, and it is what a reader comparing two artifacts needs.
let treeVersion = null;
try {
  treeVersion = JSON.parse(readFileSync(resolve(tree, 'package.json'), 'utf8')).version ?? null;
} catch {
  treeVersion = null;
}

const folds = typeof normalizeForSearch === 'function';
const querySideName = folds ? 'normalizeForSearch+class' : 'tokenize-only';
const querySideCaveat = folds
  ? null
  : 'pre-fold tree: `normalizeForSearch` is absent, so `tokenize` is called as it stands. ' +
    'It drops 1-character tokens, which empties the query side for every single-codepoint ' +
    'probe; the per-codepoint arm therefore under-reports on this arm and the word-level ' +
    'regressions carry the miss signal.';

/**
 * The blocks R7's languages plausibly put in a library.
 *
 * Each entry is [name, lo, hi, why]. `why` is in the artifact so a reader of the numbers
 * does not have to come back here to learn what a block was doing in the sweep.
 */
const RANGES = [
  ['Latin-1 Supplement + Latin Extended-A/B', 0x00c0, 0x024f,
    "R7's Latin tier: French, German, Spanish, and the Latin-with-diacritics class"],
  ['Greek and Coptic', 0x0370, 0x03ff,
    'a cased non-Latin script whose diacritics remove_diacritics 2 does NOT strip'],
  ['Cyrillic', 0x0400, 0x04ff, "R7's Cyrillic class, Russian"],
  ['Latin Extended Additional (Vietnamese)', 0x1e00, 0x1eff,
    "R7's MUST tier: Vietnamese tone marks and the dot below"],
  ['Arabic', 0x0600, 0x06ff,
    "R7's right-to-left class: letters that join, and the short vowels a writer may omit"],
  ['Arabic Supplement', 0x0750, 0x077f, 'the extended Arabic letters, same script class'],
  ['Arabic Extended-A', 0x08a0, 0x08ff, 'the rest of the extended letters, and the Quranic marks'],
  ['Arabic Presentation Forms-A (below the noncharacters)', 0xfb50, 0xfdcf,
    'the joined ligature forms legacy encodings produce; U+FDD0-U+FDEF is excluded, see the header'],
  ['Arabic Presentation Forms-A (above the noncharacters)', 0xfdf0, 0xfdff,
    'the ligature forms above the reserved noncharacter block'],
  ['Arabic Presentation Forms-B', 0xfe70, 0xfeff,
    'the positional forms, which a document converted from a legacy encoding carries'],
  ['Devanagari', 0x0900, 0x097f,
    "R7's abugida class, Hindi: matras, the virama and the nukta"],
  ['Devanagari Extended', 0xa8e0, 0xa8ff, 'the Vedic marks, same script class'],
  ['CJK Symbols and Punctuation', 0x3000, 0x303f,
    'the punctuation a Chinese document separates its terms with'],
  ['CJK Unified Ideographs', 0x4e00, 0x9fff,
    "R7's no-word-boundaries class, Chinese: the block a Han run is drawn from"],
  ['CJK Unified Ideographs Extension A', 0x3400, 0x4dbf, 'the rarer Han, same class'],
  ['Letterlike Symbols', 0x2100, 0x214f, 'symbols that print as letters and index as terms'],
  ['Number Forms', 0x2150, 0x218f, 'the Roman numerals, which lowercase differently on the two sides'],
  ['Alphabetic Presentation Forms (ligatures)', 0xfb00, 0xfb06, 'the Latin ligatures a PDF extractor emits'],
  ['Halfwidth and Fullwidth Forms', 0xff01, 0xff5e,
    'the fullwidth Latin a CJK document mixes into its text'],
];

/**
 * The blocks this run sweeps. `--blocks` selects by case-insensitive substring; no filter
 * means all of them. A filter matching nothing is a usage error rather than an empty green.
 */
const wanted = opt.blocks
  ? opt.blocks.split(',').map((s_) => s_.trim().toLowerCase()).filter(Boolean)
  : null;
const ranges = wanted
  ? RANGES.filter(([name]) => wanted.some((w) => name.toLowerCase().includes(w)))
  : RANGES;
if (wanted && ranges.length === 0) {
  console.error(
    `--blocks ${opt.blocks} matches no block. Known blocks:\n` +
      RANGES.map(([name]) => `  ${name}`).join('\n'),
  );
  process.exit(2);
}

const db = new DatabaseSync(':memory:');
// The shipped declaration, character for character. Any drift here makes the whole sweep
// a measurement of something else.
db.exec("CREATE VIRTUAL TABLE probe USING fts5(body, tokenize='unicode61 remove_diacritics 2')");
db.exec('CREATE VIRTUAL TABLE probe_vocab USING fts5vocab(probe, row)');
const insert = db.prepare('INSERT INTO probe(rowid, body) VALUES(?, ?)');
const del = db.prepare('DELETE FROM probe WHERE rowid = ?');
const terms = db.prepare('SELECT term FROM probe_vocab ORDER BY term');

/** What FTS5 stores for one input, as the distinct set of terms `fts5vocab` reports. */
function indexSide(text) {
  insert.run(1, text);
  const rows = terms.all().map((r) => r.term);
  del.run(1);
  return rows;
}

/** What the shipped JS query side produces for the same input, on whichever arm is live. */
function querySide(text) {
  if (!folds) return tokenize(text);
  return normalizeForSearch(text).match(/[\p{L}\p{N}]+/gu) ?? [];
}

const sorted = (terms_) => [...new Set(terms_)].sort();

/**
 * The verdict for one input, over R19's clause: every term the query side produces must be
 * one the index side can also produce.
 */
function classify(indexed, queried) {
  const index = sorted(indexed);
  const query = sorted(queried);
  if (index.length === query.length && index.every((t, i) => t === query[i])) return 'agree';
  if (query.every((t) => index.includes(t))) return 'narrows';
  if (index.length === 0) return 'widens';
  return 'misses';
}

const started = Date.now();
const divergences = [];
let swept = 0;
let agree = 0;
const perRange = [];

for (const [name, lo, hi, why] of ranges) {
  let n = 0;
  let bad = 0;
  for (let cp = lo; cp <= hi; cp++) {
    const ch = String.fromCodePoint(cp);
    // Unpaired surrogates and the like never reach an index; skip rather than record noise.
    if (!ch || ch.length === 0) continue;
    swept++;
    n++;
    const idx = indexSide(ch);
    const qry = querySide(ch);
    const direction = classify(idx, qry);
    if (direction === 'agree') {
      agree++;
      continue;
    }
    bad++;
    divergences.push({
      codepoint: `U+${cp.toString(16).toUpperCase().padStart(4, '0')}`,
      char: ch,
      block: name,
      indexed_as: sorted(idx),
      queried_as: sorted(qry),
      direction,
      // Flagged, not excluded — see the header. A lone mark is not a query anyone types,
      // and measured it only ever narrows.
      lone_combining_mark: /^\p{M}$/u.test(ch),
    });
  }
  perRange.push({ block: name, why, from: `U+${lo.toString(16).toUpperCase().padStart(4, '0')}`,
    to: `U+${hi.toString(16).toUpperCase().padStart(4, '0')}`, swept: n, divergences: bad });
}

// A sweep that agreed everywhere would be indistinguishable from one that compared a
// string to itself. These run on every invocation, `--blocks` included: they are the
// gate's fixed control set, not one of its ranges. These are the cases 0009 was about, plus one per script class added by
// 0578: each MUST agree, or the fold does not do what R19 says it does. They are part of
// the gate's verdict, not a printout beside it — before 0578 nothing failed on them.
const REGRESSIONS = [
  ['théorie', 'the defect that opened the ticket'],
  ['theorie', 'its unaccented spelling — both must reach the same term'],
  ['Θεωρία', 'Greek tonos, which remove_diacritics 2 does NOT strip'],
  ['теория', 'Cyrillic, untouched by a Latin-only fold'],
  ['đại', 'Vietnamese đ, which the index keeps — the query must keep it too'],
  ['mathématiques', 'the second worst case measured on the real library'],
  ['probabilità', 'Italian, the case only the SQLite backend ever retrieved'],
  ['søren', 'a Latin letter with a stroke, which unicode61 does not fold'],
  ['مكتبة',
    "R7's right-to-left class: unicode61 keeps the unvocalized Arabic word whole, so the query must too"],
  ['مَكْتَبَة',
    'the same word with its short vowels written: unicode61 treats every haraka as a separator, so ' +
      'both sides must fragment into the same consonants — a query-side fold that dropped the marks ' +
      'would look for a whole word the index does not hold'],
  ['هندسة', 'a second Arabic word, so the class does not rest on one root'],
  ['हिन्दी',
    "R7's abugida class: matras and the virama separate on both sides, so the word arrives as its " +
      'consonants and the two sides must agree on which'],
  // Written as an escape, not as a literal, and that is load-bearing: U+0958 is a
  // composition exclusion, so an editor storing this file in NFC would silently turn the
  // literal into U+0915 U+093C — the decomposed spelling, which agrees on both sides and
  // would make this entry test the opposite of what it claims.
  ['\u0958',
    'Devanagari nukta, precomposed U+0958: a Unicode composition exclusion, so NFD splits it and NFC ' +
      'cannot put it back while unicode61 stores it whole. The abugida case 0026 predicted would break ' +
      'a Latin-shaped fold'],
  ['\u0915\u093C',
    'the same sound written the way Unicode recommends, base plus nukta: it agrees, which is what ' +
      'makes the entry above a finding about the precomposed spelling rather than about Devanagari'],
  ['数据',
    "R7's no-word-boundaries class: the shortest Chinese term a two-gram geometry carries. unicode61 " +
      'keeps a Han run whole, so the query side must keep it whole rather than split it per character'],
  ['数据库', 'a three-character Chinese term, so the class does not rest on the two-gram case alone'],
];
const regressions = REGRESSIONS.map(([word, why]) => {
  const idx = indexSide(word);
  const qry = querySide(word);
  const direction = classify(idx, qry);
  return {
    word,
    why,
    indexed_as: sorted(idx),
    queried_as: sorted(qry),
    direction,
    agree: direction === 'agree',
  };
});

const byDirection = (rows) =>
  rows.reduce((acc, r) => ({ ...acc, [r.direction]: (acc[r.direction] ?? 0) + 1 }), {});

const missesCodepoint = divergences.filter((d) => d.direction === 'misses');
const missesWord = regressions.filter((r) => r.direction === 'misses');
const missesTotal = missesCodepoint.length + missesWord.length;
const elapsedMs = Date.now() - started;

const out = {
  probe: 'R19 fold gate — JS query side versus what FTS5 unicode61 remove_diacritics 2 actually indexes',
  requirement: 'R19 (SPEC.md §3); the gate is SPEC.md §5.2.8',
  tokenizer: 'unicode61 remove_diacritics 2',
  tree,
  tree_version: treeVersion,
  // null when every block ran. A filtered run is a partial measurement and says so.
  blocks_filter: opt.blocks ?? null,
  // Which arm produced these numbers. The two are not comparable; see the header.
  query_side: querySideName,
  query_side_caveat: querySideCaveat,
  verdict: missesTotal > 0 ? 'red' : 'agreed',
  exit_code: missesTotal > 0 ? 1 : 0,
  elapsed_ms: elapsedMs,
  codepoints_swept: swept,
  codepoints_agreeing: agree,
  divergences_total: divergences.length,
  divergences_by_direction: byDirection(divergences),
  // The claim under test, counted over both arms of the gate: no query term the index
  // cannot produce, at codepoint level or at word level.
  misses_total: missesTotal,
  misses_codepoint: missesCodepoint.length,
  misses_word: missesWord.length,
  per_block: perRange,
  misses: missesCodepoint,
  divergences,
  word_level_regressions_by_direction: byDirection(regressions),
  word_level_regressions: regressions,
};
mkdirSync(dirname(resolve(opt.output)), { recursive: true });
writeFileSync(opt.output, JSON.stringify(out, null, 1));
db.close();

console.log(
  `query side: ${querySideName}  (tree ${tree})\n` +
    `swept ${swept} codepoints in ${elapsedMs} ms; ${agree} agree, ${divergences.length} diverge ` +
    `(${JSON.stringify(out.divergences_by_direction)})\n` +
    `word-level: ${regressions.filter((r) => r.agree).length}/${regressions.length} agree ` +
    `(${JSON.stringify(out.word_level_regressions_by_direction)})\n` +
    (missesTotal > 0
      ? `RED: ${missesTotal} case(s) send a query where the index is not ` +
        `(${missesCodepoint.length} codepoint, ${missesWord.length} word-level) — see ${opt.output}`
      : 'no query goes where the index is not'),
);
process.exit(missesTotal > 0 ? 1 : 0);
