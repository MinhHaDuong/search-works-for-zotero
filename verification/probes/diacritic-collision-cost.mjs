/**
 * What does folding diacritics cost in a library that holds several languages?
 *
 * The index is declared `unicode61 remove_diacritics 2`, so the document side is folded
 * before it is stored and the query side must fold identically or every accented query
 * misses. That makes folding an index-level decision, not a query-level one, and the
 * question worth asking is whether the index should fold at all.
 *
 * Folding buys recall: someone who types `economie` finds `économie`, which matters
 * because accents are the first thing lost to keyboards, copy-paste and OCR. It costs
 * precision, and the cost is not symmetric. When an accented word of one language folds
 * onto an unaccented word of another, the two become one token — and if the second is
 * common, the first becomes unsearchable. `thé` folds to `the`, which is in 84% of this
 * corpus: a French tea query cannot be answered, and no amount of work downstream can
 * recover a distinction the tokenizer already threw away.
 *
 * This measures that, rather than arguing it. The FTS5 vocabulary holds only folded
 * tokens, so the accented forms cannot be recovered from it — the raw `passages.text` is
 * tokenized here twice, once folded and once not, and the pairs are compared.
 *
 * Reported per collision: how often the accented form actually occurs (what folding
 * destroys), and the document frequency of the token it lands on (how badly).
 */
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const sample = Number(args.sample ?? 40000);

const db = new DatabaseSync(args.index, { readOnly: true });
const passages = db.prepare('SELECT count(*) AS n FROM passages').get().n;
db.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main', 'passages_fts', 'row')");
const dfStmt = db.prepare('SELECT doc FROM temp.v WHERE term = ?');
const df = (t) => dfStmt.get(t)?.doc ?? 0;

/** The fold the tokenizer applies: strip combining marks that sit on a Latin base. */
const LATIN_MARKS = /(\p{Script=Latin})[̀-ͯ]+/gu;
const fold = (s) => s.normalize('NFD').replace(LATIN_MARKS, '$1').normalize('NFC');

// Every N-th passage, so the sample spans the whole library rather than one end of it.
const step = Math.max(1, Math.floor(passages / sample));
const rows = db.prepare(`SELECT text FROM passages WHERE rowid % ${step} = 0 LIMIT ${sample}`).all();

/** accented surface form -> occurrences, and the token it folds onto. */
const accented = new Map();
let tokensSeen = 0;
for (const { text } of rows) {
  for (const raw of text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []) {
    tokensSeen++;
    if (raw.length < 2) continue;
    const f = fold(raw);
    if (f === raw) continue; // carries no mark the fold would remove
    const rec = accented.get(raw) ?? { term: raw, foldsTo: f, occurrences: 0 };
    rec.occurrences++;
    accented.set(raw, rec);
  }
}

const collisions = [];
for (const rec of accented.values()) {
  // A collision only matters if the token it lands on is itself a word of the corpus:
  // folding `théorie` to `theorie` costs nothing if nothing else spells it that way.
  const landedDf = df(rec.foldsTo);
  if (!landedDf) continue;
  // How often the folded form occurs in its own right, unaccented, in the sample. When
  // that dwarfs the accented form, the accented word is what disappears into it.
  collisions.push({
    ...rec,
    landsOnDoc: landedDf,
    landsOnPct: +((100 * landedDf) / passages).toFixed(2),
  });
}
collisions.sort((a, b) => b.landsOnDoc - a.landsOnDoc);

const severe = collisions.filter((c) => c.landsOnPct >= 10);
const out = {
  index: args.index,
  passages,
  sampled_passages: rows.length,
  tokens_seen: tokensSeen,
  distinct_accented_forms: accented.size,
  collisions_total: collisions.length,
  collisions_onto_common_tokens: severe.length,
  note: 'A collision is an accented form whose folded spelling is ALSO a real token of this index. Severity is the document frequency of the token it lands on: the higher, the more completely the accented word disappears into it.',
  worst: collisions.slice(0, 30),
  severe,
};
writeFileSync(args.out, JSON.stringify(out, null, 1));

console.log(`sampled ${rows.length} passages, ${tokensSeen} tokens`);
console.log(`${accented.size} distinct accented forms; ${collisions.length} of them fold onto a token this index already holds`);
console.log(`${severe.length} land on a token in 10% or more of the corpus:\n`);
for (const c of severe.slice(0, 25)) {
  console.log(`  ${c.term.padEnd(12)} -> ${c.foldsTo.padEnd(12)} seen ${String(c.occurrences).padStart(5)}x   lands on a token in ${String(c.landsOnPct).padStart(6)}% of passages`);
}
console.log('\ntop collisions by severity regardless of threshold:');
for (const c of out.worst.slice(0, 12)) {
  console.log(`  ${c.term.padEnd(12)} -> ${c.foldsTo.padEnd(12)} ${String(c.occurrences).padStart(5)}x  ${String(c.landsOnPct).padStart(6)}%`);
}
