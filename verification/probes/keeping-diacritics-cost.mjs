/**
 * What would it actually cost to stop folding diacritics?
 *
 * Folding is set in the FTS5 table declaration (`unicode61 remove_diacritics 2`), so it is
 * an index-level decision and the query side has no say: whatever the index folded, the
 * query must fold identically or it misses. The question is therefore whether the index
 * should fold, and the honest way to answer it is to build both and ask them the same
 * things.
 *
 * Two indexes are built here over the SAME passages, differing only in that one clause.
 * Then, for every word this corpus spells more than one way, three counts:
 *
 *   folded          — documents the folding index returns. It cannot tell the spellings
 *                     apart, so this is their union, plus any unrelated word that happens
 *                     to fold to the same string.
 *   unfolded, as typed accented    — what a user who types the accents gets.
 *   unfolded, as typed unaccented  — what a user who does not gets.
 *
 * The gap between the folded count and each unfolded count is the recall folding buys, in
 * that typing direction. It is reported in both directions because which one matters
 * depends on how people type, which no corpus can tell us — and because for this library
 * the answer differs sharply by language.
 *
 * Also reported: vocabulary size and index bytes, which is the other half of the cost —
 * not folding means more distinct terms and shorter posting lists.
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

/** Both indexes, same rows, one clause apart. */
function build(clause) {
  const db = new DatabaseSync(':memory:');
  db.exec(`CREATE VIRTUAL TABLE p USING fts5(text, tokenize='unicode61 ${clause}')`);
  const ins = db.prepare('INSERT INTO p(text) VALUES (?)');
  db.exec('BEGIN');
  for (const t of texts) ins.run(t);
  db.exec('COMMIT');
  db.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main', 'p', 'row')");
  return db;
}
const folded = build('remove_diacritics 2');
const unfolded = build('remove_diacritics 0');

const vocab = (db) => db.prepare('SELECT count(*) AS n FROM temp.v').get().n;
const bytes = (db) => db.prepare("SELECT sum(length(block)) AS n FROM p_data").get().n;
const hits = (db, term) => {
  try {
    return db.prepare('SELECT count(*) AS n FROM p WHERE p MATCH ?').get(`"${term.replace(/"/g, '""')}"`).n;
  } catch {
    return 0;
  }
};

// The words this corpus spells more than one way, biggest first. These are the only words
// where the two indexes can possibly differ, so they are the whole population of interest.
const groups = new Map();
for (const t of texts) {
  for (const raw of t.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []) {
    if (raw.length < 2) continue;
    const f = fold(raw);
    let g = groups.get(f);
    if (!g) groups.set(f, (g = new Map()));
    g.set(raw, (g.get(raw) ?? 0) + 1);
  }
}
const multi = [...groups.entries()]
  .filter(([, forms]) => forms.size > 1)
  .map(([f, forms]) => ({ folded: f, forms: [...forms.entries()].sort((a, b) => b[1] - a[1]), total: [...forms.values()].reduce((a, b) => a + b, 0) }))
  .sort((a, b) => b.total - a.total)
  .slice(0, Number(args.top ?? 120));

const rows = [];
for (const g of multi) {
  const foldedHits = hits(folded, g.folded);
  // The most common accented spelling, and the unaccented one if it occurs at all.
  const topAccented = g.forms.find(([f]) => f !== g.folded)?.[0];
  if (!topAccented) continue;
  const accentedHits = hits(unfolded, topAccented);
  const bareHits = hits(unfolded, g.folded);
  rows.push({
    folded: g.folded,
    spellings: g.forms.map(([f, c]) => `${f}:${c}`),
    folded_hits: foldedHits,
    unfolded_hits_typing_accented: accentedHits,
    unfolded_hits_typing_unaccented: bareHits,
    recall_kept_typing_accented: foldedHits ? +(accentedHits / foldedHits).toFixed(3) : null,
    recall_kept_typing_unaccented: foldedHits ? +(bareHits / foldedHits).toFixed(3) : null,
  });
}

const mean = (xs) => (xs.length ? +(xs.reduce((a, b) => a + b, 0) / xs.length).toFixed(3) : null);
const out = {
  source: args.index,
  sampled_passages: texts.length,
  folded_index: { vocabulary_terms: vocab(folded), fts_bytes: bytes(folded) },
  unfolded_index: { vocabulary_terms: vocab(unfolded), fts_bytes: bytes(unfolded) },
  words_spelled_more_than_one_way: multi.length,
  mean_recall_kept_typing_accented: mean(rows.map((r) => r.recall_kept_typing_accented).filter((x) => x !== null)),
  mean_recall_kept_typing_unaccented: mean(rows.map((r) => r.recall_kept_typing_unaccented).filter((x) => x !== null)),
  reading:
    'recall_kept is the share of the folding index’s documents that the unfolded index still returns for a query typed that way. 1,0 means dropping the fold costs nothing for that word; 0,1 means nine documents in ten become unreachable.',
  rows,
};
writeFileSync(args.out, JSON.stringify(out, null, 1));

console.log(`sampled ${texts.length} passages`);
console.log(`vocabulary: folded ${out.folded_index.vocabulary_terms}, unfolded ${out.unfolded_index.vocabulary_terms} (+${(100 * (out.unfolded_index.vocabulary_terms / out.folded_index.vocabulary_terms - 1)).toFixed(1)}%)`);
console.log(`fts bytes:  folded ${out.folded_index.fts_bytes}, unfolded ${out.unfolded_index.fts_bytes} (+${(100 * (out.unfolded_index.fts_bytes / out.folded_index.fts_bytes - 1)).toFixed(1)}%)`);
console.log(`\nover ${rows.length} words this corpus spells more than one way:`);
console.log(`  mean recall kept if the user TYPES THE ACCENTS   : ${out.mean_recall_kept_typing_accented}`);
console.log(`  mean recall kept if the user TYPES NO ACCENTS    : ${out.mean_recall_kept_typing_unaccented}`);
console.log(`\nworst losses when typing the accented spelling:`);
for (const r of rows.slice().sort((a, b) => a.recall_kept_typing_accented - b.recall_kept_typing_accented).slice(0, 15)) {
  console.log(`  ${r.folded.padEnd(14)} folded ${String(r.folded_hits).padStart(6)}  accented ${String(r.unfolded_hits_typing_accented).padStart(6)} (${r.recall_kept_typing_accented})  bare ${String(r.unfolded_hits_typing_unaccented).padStart(6)} (${r.recall_kept_typing_unaccented})   ${r.spellings.slice(0, 4).join(' ')}`);
}
