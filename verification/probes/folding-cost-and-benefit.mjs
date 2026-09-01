/**
 * What folding diacritics buys, and what it costs, counted on the same evidence.
 *
 * An earlier probe here compared accented surface forms against the FTS5 vocabulary and
 * reported that nearly all of them "collide with a token the index already holds". That
 * finding was guaranteed rather than observed: the index is declared
 * `remove_diacritics 2`, so an accented word IS its folded spelling in that vocabulary and
 * the comparison could not have come out any other way. A check whose all-clear is
 * indistinguishable from its could-not-look is not a check, and neither is one whose
 * positive is unavoidable.
 *
 * This reads the raw passage text instead, which the index stores unfolded, and groups
 * every surface form by what it folds to. Then the two effects are separable and countable
 * on identical evidence:
 *
 *   BENEFIT — a group holding one word spelled two ways (`économie` / `economie`). Folding
 *   unites them; without it, a query in one spelling misses the other.
 *
 *   COST — a group holding two DIFFERENT words (`thể` / `the`, `bé` / `be`). Folding merges
 *   distinct vocabulary, and the loss is at index time, so nothing downstream can undo it.
 *
 * The two are told apart by a property that needs no dictionary: within a group, is the
 * unaccented member a word in its own right elsewhere in the corpus? `economie` occurs
 * only as a mistyping of `économie`; `the` occurs hundreds of thousands of times on its
 * own account. So the ratio between the group's members is the signal, and it is reported
 * rather than thresholded into a verdict.
 */
import { DatabaseSync } from 'node:sqlite';
import { writeFileSync } from 'node:fs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const sample = Number(args.sample ?? 40000);

const LATIN_MARKS = /(\p{Script=Latin})[̀-ͯ]+/gu;
const fold = (s) => s.normalize('NFD').replace(LATIN_MARKS, '$1').normalize('NFC');

const db = new DatabaseSync(args.index, { readOnly: true });
const passages = db.prepare('SELECT count(*) AS n FROM passages').get().n;
const step = Math.max(1, Math.floor(passages / sample));
const rows = db.prepare(`SELECT text FROM passages WHERE rowid % ${step} = 0 LIMIT ${sample}`).all();
db.close();

/** folded spelling -> surface form -> count */
const groups = new Map();
let tokens = 0;
for (const { text } of rows) {
  for (const raw of text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []) {
    if (raw.length < 2) continue;
    tokens++;
    const f = fold(raw);
    let g = groups.get(f);
    if (!g) groups.set(f, (g = new Map()));
    g.set(raw, (g.get(raw) ?? 0) + 1);
  }
}

const mixed = [];
for (const [folded, forms] of groups) {
  if (forms.size < 2) continue; // only one spelling ever seen: folding changes nothing here
  const sorted = [...forms.entries()].sort((a, b) => b[1] - a[1]);
  const bare = forms.get(folded) ?? 0; // the unaccented spelling, if it occurs at all
  const accentedTotal = sorted.filter(([f]) => f !== folded).reduce((s, [, c]) => s + c, 0);
  mixed.push({
    folded,
    forms: sorted.map(([f, c]) => ({ form: f, count: c })),
    bare,
    accentedTotal,
    // How lopsided the group is. Near 1 means the two spellings are comparable, which is
    // what one word spelled two ways looks like. Very large means the unaccented member
    // stands on its own and the accented one is being absorbed into it.
    ratio: accentedTotal ? +(bare / accentedTotal).toFixed(1) : Infinity,
  });
}

// A group where the unaccented member never occurs alone is pure benefit: folding only
// ever unites spellings of one word. A group where it dwarfs the accented member is where
// distinct vocabulary is being merged.
const unitesOnly = mixed.filter((g) => g.bare === 0);
const balanced = mixed.filter((g) => g.bare > 0 && g.ratio <= 10);
const absorbing = mixed.filter((g) => g.bare > 0 && g.ratio > 10);

const out = {
  index: args.index,
  sampled_passages: rows.length,
  tokens,
  distinct_folded_groups: groups.size,
  groups_with_more_than_one_spelling: mixed.length,
  groups_where_the_unaccented_spelling_never_occurs_alone: unitesOnly.length,
  groups_where_the_two_spellings_are_comparable: balanced.length,
  groups_where_the_unaccented_spelling_dominates_10x_or_more: absorbing.length,
  reading:
    'Comparable groups are what folding buys: one word, two spellings, united. Dominating groups are what it costs: the accented word is absorbed into an unaccented word that stands on its own. Groups where the unaccented spelling never occurs alone are unaffected either way — folding unites nothing and merges nothing.',
  benefit_examples: balanced.sort((a, b) => b.accentedTotal - a.accentedTotal).slice(0, 20),
  cost_examples: absorbing.sort((a, b) => b.accentedTotal - a.accentedTotal).slice(0, 25),
};
writeFileSync(args.out, JSON.stringify(out, null, 1));

console.log(`sampled ${rows.length} passages, ${tokens} tokens, ${groups.size} distinct folded groups`);
console.log(`${mixed.length} groups hold more than one spelling. Of those:`);
console.log(`  ${unitesOnly.length}  the unaccented spelling never occurs alone (folding neither unites nor merges)`);
console.log(`  ${balanced.length}  the two spellings are comparable  <- what folding BUYS`);
console.log(`  ${absorbing.length}  the unaccented spelling dominates 10x or more  <- what folding COSTS`);

console.log('\nBENEFIT — one word, two spellings, united by folding:');
for (const g of out.benefit_examples.slice(0, 12)) {
  console.log(`  ${g.folded.padEnd(16)} ${g.forms.map((f) => `${f.form}:${f.count}`).join('  ')}`);
}
console.log('\nCOST — an accented word absorbed into an unaccented word that stands on its own:');
for (const g of out.cost_examples.slice(0, 15)) {
  console.log(`  ${g.folded.padEnd(16)} ${g.forms.map((f) => `${f.form}:${f.count}`).join('  ')}`);
}
