/**
 * Does the corpus-derived list actually adapt to the language of the corpus?
 *
 * The claim is that asking "what does this string cost to retrieve on HERE" has one answer
 * per library, where a shipped English list has one answer everywhere. On the library this
 * was developed against, the claim is true and invisible: that corpus is 85% English, so
 * the derived list is all English function words and looks exactly like the shipped one.
 * A reader is entitled to suspect the rule of being an English list with extra steps.
 *
 * So this builds real FTS5 indexes over language-selected subsets of the SAME library —
 * declared with the same tokenizer, derived by the same query the backend runs — and
 * prints what each one derives. Nothing is simulated: if the rule does not adapt, this
 * prints an English list over a French corpus and the claim is dead.
 *
 * The subsets are selected by marker words rather than by a language classifier, which is
 * crude and does not need to be better: a passage containing `les` and `des` and `dans` is
 * French, and a few misfiled passages cannot manufacture a French droplist out of an
 * English corpus.
 */
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const RATIO = 0.3;

const MARKERS = {
  french: ['les', 'des', 'une', 'dans', 'pour', 'est', 'sont', 'cette', 'nous', 'qui', 'que', 'par'],
  vietnamese: ['nam', 'cua', 'trong', 'viet', 'khong', 'nhung', 'nang', 'luong'],
  english: ['the', 'and', 'that', 'with', 'which', 'from', 'have', 'been'],
};

const src = new DatabaseSync(args.index, { readOnly: true });
const total = src.prepare('SELECT count(*) AS n FROM passages').get().n;
const out = { source: args.index, source_passages: total, ratio: RATIO, subsets: {} };

for (const [lang, markers] of Object.entries(MARKERS)) {
  // A passage counts for this language when it carries at least three of its markers as
  // whole words. Three, so an English passage quoting one French title does not qualify.
  const rows = src.prepare('SELECT text FROM passages').all();
  const chosen = [];
  for (const { text } of rows) {
    const toks = new Set(text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []);
    if (markers.filter((m) => toks.has(m)).length >= 3) chosen.push(text);
    if (chosen.length >= 60000) break;
  }

  // A real index, same tokenizer declaration as the backend uses, so the derivation below
  // is the one the backend would run and not an approximation of it.
  const db = new DatabaseSync(':memory:');
  db.exec("CREATE VIRTUAL TABLE p USING fts5(text, tokenize='unicode61 remove_diacritics 2')");
  const ins = db.prepare('INSERT INTO p(text) VALUES (?)');
  db.exec('BEGIN');
  for (const t of chosen) ins.run(t);
  db.exec('COMMIT');
  db.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main', 'p', 'row')");
  const n = chosen.length;
  const derived = db
    .prepare('SELECT term, doc FROM temp.v WHERE doc >= ? ORDER BY doc DESC')
    .all(Math.ceil(n * RATIO))
    .map((r) => ({ term: r.term, pct: +((100 * r.doc) / n).toFixed(1) }));
  out.subsets[lang] = { passages: n, derived_terms: derived.length, terms: derived };
  db.close();

  console.log(`\n### ${lang}: ${n} passages selected, ${derived.length} terms at ${RATIO * 100}%`);
  console.log('  ' + derived.map((d) => `${d.term}(${d.pct})`).join(' '));
}
src.close();
writeFileSync(args.out, JSON.stringify(out, null, 1));
