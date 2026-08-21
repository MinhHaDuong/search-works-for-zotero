// Ticket 0009: does the JS fold agree with what FTS5 actually indexes, codepoint by codepoint?
//
// The fix for 0009 rests on a symmetry claim — that `normalizeForSearch` in JS produces
// the same token unicode61 does on the document side — and a review found that claim
// stated in prose with no artifact behind it. This is the sweep, committed with its output.
//
// The method is the only one that settles it: put each codepoint through a REAL FTS5 table
// declared with the shipped tokenizer, read back what SQLite stored via `fts5vocab`, and
// compare it with what the shipped JS tokenizer produces for the same input. Nothing here
// reimplements either side.
//
// A divergence is classified by direction, because the two are not equally bad:
//   - `narrows`   the query token is a strict sub-case (or absent) where the index has a
//                 term: the query retrieves LESS than it could. Costly, not wrong.
//   - `misses`    query and index produce different non-empty terms: the query goes where
//                 the index is not. This is the 0009 defect class, and must be zero for
//                 anything a user is likely to type.
//   - `widens`    the query produces a term where the index stores none.
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';

const { values: opt } = parseArgs({
  options: {
    fork: { type: 'string', default: new URL('../fork/', import.meta.url).pathname },
    output: { type: 'string' },
  },
});
if (!opt.output) {
  console.error('usage: node bench/fold_sweep.mjs --output <file.json> [--fork <dir>]');
  process.exit(2);
}

const { tokenize, normalizeForSearch } = await import(`${opt.fork}dist/features/search/tokenize.js`);

/** The blocks a European/Vietnamese/Greek/Cyrillic library plausibly contains. */
const RANGES = [
  ['Latin-1 Supplement + Latin Extended-A/B', 0x00c0, 0x024f],
  ['Greek and Coptic', 0x0370, 0x03ff],
  ['Cyrillic', 0x0400, 0x04ff],
  ['Latin Extended Additional (Vietnamese)', 0x1e00, 0x1eff],
  ['Letterlike Symbols', 0x2100, 0x214f],
  ['Number Forms', 0x2150, 0x218f],
  ['Alphabetic Presentation Forms (ligatures)', 0xfb00, 0xfb06],
  ['Halfwidth and Fullwidth Forms', 0xff01, 0xff5e],
];

const db = new DatabaseSync(':memory:');
// The shipped declaration, character for character. Any drift here makes the whole sweep
// a measurement of something else.
db.exec("CREATE VIRTUAL TABLE probe USING fts5(body, tokenize='unicode61 remove_diacritics 2')");
db.exec('CREATE VIRTUAL TABLE probe_vocab USING fts5vocab(probe, row)');
const insert = db.prepare('INSERT INTO probe(rowid, body) VALUES(?, ?)');
const del = db.prepare('DELETE FROM probe WHERE rowid = ?');
const terms = db.prepare('SELECT term FROM probe_vocab ORDER BY term');

/** What FTS5 stores for a single character, standing alone as its own token. */
function indexSide(ch) {
  insert.run(1, ch);
  const rows = terms.all().map((r) => r.term);
  del.run(1);
  return rows;
}

/** What the shipped JS tokenizer produces for the same character. */
function querySide(ch) {
  // `tokenize` drops 1-character tokens and stopwords, which would hide every single-char
  // codepoint. The comparison is on the fold plus the token class, so it is applied here
  // directly — the same two steps `tokenize` performs, without its length filter.
  const folded = normalizeForSearch(ch);
  return folded.match(/[\p{L}\p{N}]+/gu) ?? [];
}

const divergences = [];
let swept = 0;
let agree = 0;
const perRange = [];

for (const [name, lo, hi] of RANGES) {
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
    const same = idx.length === qry.length && idx.every((t, i) => t === qry[i]);
    if (same) {
      agree++;
      continue;
    }
    bad++;
    const direction =
      qry.length === 0 && idx.length > 0
        ? 'narrows'
        : idx.length === 0 && qry.length > 0
          ? 'widens'
          : 'misses';
    divergences.push({
      codepoint: `U+${cp.toString(16).toUpperCase().padStart(4, '0')}`,
      char: ch,
      block: name,
      indexed_as: idx,
      queried_as: qry,
      direction,
    });
  }
  perRange.push({ block: name, swept: n, divergences: bad });
}

// A sweep that agreed everywhere would be indistinguishable from one that compared a
// string to itself. These are the cases 0009 was about: each MUST agree, or the fix does
// not do what the ticket says it does.
const REGRESSIONS = [
  ['théorie', 'the defect that opened the ticket'],
  ['theorie', 'its unaccented spelling — both must reach the same term'],
  ['Θεωρία', 'Greek tonos, which remove_diacritics 2 does NOT strip'],
  ['теория', 'Cyrillic, untouched by a Latin-only fold'],
  ['đại', 'Vietnamese đ, which the index keeps — the query must keep it too'],
  ['mathématiques', 'the second worst case measured on the real library'],
  ['probabilità', 'Italian, the case only the SQLite backend ever retrieved'],
  ['søren', 'a Latin letter with a stroke, which unicode61 does not fold'],
];
const regressions = REGRESSIONS.map(([word, why]) => {
  const idx = indexSide(word);
  const qry = querySide(word);
  return {
    word,
    why,
    indexed_as: idx,
    queried_as: qry,
    agree: idx.length === qry.length && idx.every((t, i) => t === qry[i]),
  };
});

const out = {
  probe: 'ticket 0009 — JS fold versus what FTS5 unicode61 remove_diacritics 2 actually indexes',
  tokenizer: "unicode61 remove_diacritics 2",
  codepoints_swept: swept,
  codepoints_agreeing: agree,
  divergences_total: divergences.length,
  divergences_by_direction: divergences.reduce((acc, d) => ({ ...acc, [d.direction]: (acc[d.direction] ?? 0) + 1 }), {}),
  per_block: perRange,
  // The claim under test: no divergence sends a query somewhere the index is not.
  misses: divergences.filter((d) => d.direction === 'misses'),
  divergences,
  word_level_regressions: regressions,
};
writeFileSync(opt.output, JSON.stringify(out, null, 1));
db.close();

const misses = out.divergences_by_direction.misses ?? 0;
console.log(
  `swept ${swept} codepoints; ${agree} agree, ${divergences.length} diverge ` +
    `(${JSON.stringify(out.divergences_by_direction)})\n` +
    `word-level: ${regressions.filter((r) => r.agree).length}/${regressions.length} agree\n` +
    (misses > 0 ? `WARNING: ${misses} codepoint(s) send a query where the index is not` : 'no query goes where the index is not'),
);
