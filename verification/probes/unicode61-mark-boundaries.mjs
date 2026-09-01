/**
 * Is a combining mark part of a token, or a separator, under `remove_diacritics 0`?
 *
 * The JS token class is `[\p{L}\p{N}]+`, which makes every mark a separator. That matched
 * `remove_diacritics 2`, where marks were removed before tokenization and the question could
 * not arise. Under `0` the marks survive, and whether SQLite keeps `a◌b` as one token or two
 * decides whether the query side agrees with the index. Measured here rather than assumed,
 * because the answer turns out to differ by block.
 */
import { DatabaseSync } from 'node:sqlite';

const db = new DatabaseSync(':memory:');
db.exec("CREATE VIRTUAL TABLE t USING fts5(c, tokenize='unicode61 remove_diacritics 0')");
const ins = db.prepare('INSERT INTO t(rowid, c) VALUES (?, ?)');

const marks = [];
for (let cp = 0x300; cp <= 0x1e94a; cp++) {
  const c = String.fromCodePoint(cp);
  if (/\p{M}/u.test(c)) marks.push(cp);
}

db.exec('BEGIN');
marks.forEach((cp, i) => ins.run(i + 1, `a${String.fromCodePoint(cp)}b`));
db.exec('COMMIT');
db.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main', 't', 'row')");

// One token means the mark joined `a` and `b`; two means it split them.
const joined = [];
const split = [];
const q = db.prepare('SELECT count(*) AS n FROM temp.v WHERE term = ?');
for (const cp of marks) {
  const whole = `a${String.fromCodePoint(cp)}b`;
  (q.get(whole).n > 0 ? joined : split).push(cp);
}

const blocks = (cps) => {
  const out = [];
  let run = null;
  for (const cp of cps) {
    if (run && cp === run[1] + 1) run[1] = cp;
    else { run = [cp, cp]; out.push(run); }
  }
  return out.map(([a, b]) => (a === b ? `U+${a.toString(16).toUpperCase()}` : `U+${a.toString(16).toUpperCase()}..U+${b.toString(16).toUpperCase()}`));
};

import { writeFileSync } from 'node:fs';
if (process.argv[2]) {
  writeFileSync(process.argv[2], JSON.stringify({
    tokenizer: 'unicode61 remove_diacritics 0',
    swept: marks.length,
    part_of_token: joined.length,
    separators: split.length,
    reading:
      'unicode61 does not treat combining marks uniformly. A JS token class of [\\p{L}\\p{N}]+ is wrong for the joining set; adding \\p{M} would be wrong for the separating set. Keeping the query side in agreement needs the joining set pinned, the way UNICODE61_KEEPS_CASE is pinned.',
    part_of_token_ranges: blocks(joined),
    separator_ranges: blocks(split),
  }, null, 1));
}
console.log(`swept ${marks.length} combining marks under remove_diacritics 0`);
console.log(`\nPART OF THE TOKEN (${joined.length}) — the JS class must include these or it splits a word the index kept whole:`);
console.log('  ' + blocks(joined).join('  '));
console.log(`\nSEPARATORS (${split.length}) — the JS class must NOT include these:`);
console.log('  ' + blocks(split).join('  '));
