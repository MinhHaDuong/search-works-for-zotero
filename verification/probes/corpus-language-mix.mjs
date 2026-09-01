/**
 * What languages is this library actually in, and at what document frequency do each
 * language's function words sit?
 *
 * The droplist argument turns on a token space shared by every language at once. That
 * claim is worth nothing here unless this corpus really is mixed, so measure it before
 * building a second-language arm on top of it. Reads `fts5vocab` for document frequency
 * — the same quantity the droplist rule reads — and samples passages for a second,
 * independent estimate that does not depend on the vocabulary table being right.
 */
import { DatabaseSync } from 'node:sqlite';

const dbPath = process.argv[2];
if (!dbPath) throw new Error('usage: corpus-language-mix.mjs <index.sqlite>');
const db = new DatabaseSync(dbPath, { readOnly: true });

const passages = db.prepare('SELECT count(*) AS n FROM passages').get().n;

db.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, passages_fts, 'row')");
const dfOf = db.prepare('SELECT doc FROM temp.v WHERE term = ?');
const df = (t) => dfOf.get(t)?.doc ?? 0;

// Function words that are unambiguous markers of their language, i.e. not also a common
// word of the other. `die` is deliberately absent: it is the German article AND the
// English verb, which is the whole point of the argument and useless as a marker.
const MARKERS = {
  en: ['the', 'and', 'of', 'that', 'with', 'which', 'this', 'from', 'have', 'been'],
  fr: ['les', 'des', 'une', 'dans', 'pour', 'est', 'sont', 'cette', 'nous', 'plus'],
  de: ['und', 'der', 'nicht', 'auch', 'werden', 'aber', 'oder', 'einer', 'diese', 'sich'],
  es: ['los', 'las', 'una', 'por', 'con', 'para', 'como', 'pero', 'sus', 'este'],
};

const out = { index: dbPath, passages, markers: {} };
for (const [lang, words] of Object.entries(MARKERS)) {
  out.markers[lang] = words.map((w) => ({ term: w, doc: df(w), pct: +(100 * df(w) / passages).toFixed(2) }));
}

// Independent estimate: sample passages, score each by how many markers of each language
// it contains, assign it to the winner. Does not consult the vocabulary table at all.
const SAMPLE = 4000;
const rows = db.prepare(`SELECT text FROM passages WHERE rowid IN (SELECT rowid FROM passages ORDER BY rowid LIMIT ${SAMPLE} OFFSET (SELECT max(rowid)/7 FROM passages))`).all();
const tally = { en: 0, fr: 0, de: 0, es: 0, none: 0 };
for (const { text } of rows) {
  const toks = new Set((text.toLowerCase().match(/[\p{L}]+/gu) ?? []));
  let best = 'none', bestN = 0;
  for (const [lang, words] of Object.entries(MARKERS)) {
    const n = words.filter((w) => toks.has(w)).length;
    if (n > bestN) { best = lang; bestN = n; }
  }
  tally[bestN >= 2 ? best : 'none']++;
}
out.sample = { n: rows.length, tally };
console.log(JSON.stringify(out, null, 2));
