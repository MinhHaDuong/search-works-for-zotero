/**
 * The cost of NOT folding, isolated to the case where it is a genuine cost.
 *
 * A previous pass compared, for every word spelled more than one way, what a folded and an
 * unfolded index return. Most of what that showed was not a cost at all: `the`, `thể` and
 * `thế` are not one word spelled three ways, they are an English word and two Vietnamese
 * ones, so an unfolded index returning 252 documents for `thể` instead of 50 478 is the
 * folded index's false positives being withdrawn. Reading that as lost recall would have
 * inverted the conclusion.
 *
 * The real cost of keeping diacritics is narrower and lives where that comparison could
 * not see it: a word the corpus only ever spells WITH its marks. `théorie` appears; if
 * `theorie` never does, then in an unfolded index a user who types `theorie` gets nothing
 * — not fewer documents, none. Folding is what makes an unaccented query work at all, and
 * that population is exactly the one the earlier filter excluded by construction.
 *
 * So: find the accented words this corpus never spells bare, count the documents holding
 * them, and count the passages that would become unreachable to someone typing without
 * accents. Those documents are what folding buys, and nothing else is.
 */
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const sample = Number(args.sample ?? 60000);

const LATIN_MARKS = /(\p{Script=Latin})[̀-ͯ]+/gu;
const fold = (s) => s.normalize('NFD').replace(LATIN_MARKS, '$1').normalize('NFC');

const src = new DatabaseSync(args.index, { readOnly: true });
const total = src.prepare('SELECT count(*) AS n FROM passages').get().n;
const step = Math.max(1, Math.floor(total / sample));
const texts = src.prepare(`SELECT text FROM passages WHERE rowid % ${step} = 0 LIMIT ${sample}`).all().map((r) => r.text);
src.close();

/** Surface-form counts, and which passages each accented form appears in. */
const count = new Map();
const passagesWith = new Map();
texts.forEach((t, i) => {
  for (const raw of t.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []) {
    if (raw.length < 2) continue;
    count.set(raw, (count.get(raw) ?? 0) + 1);
    const f = fold(raw);
    if (f === raw) continue;
    let s = passagesWith.get(raw);
    if (!s) passagesWith.set(raw, (s = new Set()));
    s.add(i);
  }
});

// An accented word the corpus never (or almost never) spells bare. `almost` is 2, so a
// single OCR slip does not disqualify a word from this population.
const onlyAccented = [];
for (const [form, n] of count) {
  if (n < 20) continue;
  const f = fold(form);
  if (f === form) continue;
  const bare = count.get(f) ?? 0;
  if (bare > 2) continue;
  onlyAccented.push({ form, folded: f, occurrences: n, bareOccurrences: bare, passages: passagesWith.get(form).size });
}
onlyAccented.sort((a, b) => b.passages - a.passages);

// Passages that hold at least one such word: these are what an unaccented query can still
// reach through folding and could not reach without it.
const reachable = new Set();
for (const w of onlyAccented) for (const i of passagesWith.get(w.form)) reachable.add(i);

const out = {
  source: args.index,
  sampled_passages: texts.length,
  words_the_corpus_only_spells_accented: onlyAccented.length,
  passages_holding_at_least_one: reachable.size,
  share_of_sampled_passages: +((100 * reachable.size) / texts.length).toFixed(2),
  reading:
    'These are the words for which folding is the only thing that makes an unaccented query work: the bare spelling does not occur, so an unfolded index answers such a query with nothing. The share is an upper bound on the benefit — it counts a passage if it holds ANY such word, not if the user would have searched for it.',
  top: onlyAccented.slice(0, 30),
};
writeFileSync(args.out, JSON.stringify(out, null, 1));

console.log(`sampled ${texts.length} passages`);
console.log(`${onlyAccented.length} words occur 20+ times and are NEVER spelled bare in this corpus`);
console.log(`they appear in ${reachable.size} passages — ${out.share_of_sampled_passages}% of the sample`);
console.log(`\nthe ones that would cost the most, if a user typed them without accents:`);
for (const w of onlyAccented.slice(0, 25)) {
  console.log(`  ${w.form.padEnd(18)} ${String(w.occurrences).padStart(6)}x in ${String(w.passages).padStart(5)} passages   (bare "${w.folded}" seen ${w.bareOccurrences}x)`);
}
