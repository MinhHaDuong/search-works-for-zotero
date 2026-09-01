/**
 * What the 29-word English list costs a query in another language, measured rather than
 * argued, and what the corpus-derived droplist actually holds.
 *
 * The list is consulted on a token space that holds every language at once. Where an
 * English function word is also a content word somewhere else, the list deletes it from
 * that query with no way to know it did. This prints the document frequency of each
 * collision so the cost is a number and not a worry.
 */
import { DatabaseSync } from 'node:sqlite';

const STOPWORDS = ['the','a','an','and','or','of','to','in','on','for','with','is','are','was','were',
  'be','by','as','at','that','this','it','from','we','our','their','its','these','those'];

/** English function word -> what it means as a content word elsewhere. */
const COLLISIONS = {
  or: 'fr: gold / yet',
  on: 'fr: one (indefinite pronoun)',
  as: 'fr: ace; have (2sg)',
  an: 'fr: year',
  a: 'fr: has (avoir 3sg)',
  in: 'de: in',
  is: 'de: ice (Eis) — no; nl: is',
  was: 'de: what',
  at: 'sv/da: at',
};
/** Not on the list, and expensive in their own language — the other half of the asymmetry. */
const UNLISTED = ['die','der','das','und','les','des','une','dans','pour','est','sont','que','qui','par','sur','plus','war','sie','nicht','ist'];

const dbPath = process.argv[2];
const db = new DatabaseSync(dbPath, { readOnly: true });
const passages = db.prepare('SELECT count(*) AS n FROM passages').get().n;
db.exec("CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, passages_fts, 'row')");
const dfOf = db.prepare('SELECT doc FROM temp.v WHERE term = ?');
const pct = (t) => { const d = dfOf.get(t)?.doc ?? 0; return { term: t, doc: d, pct: +(100*d/passages).toFixed(2) }; };

const derived = db.prepare('SELECT term, doc FROM temp.v WHERE doc >= ? ORDER BY doc DESC').all(Math.ceil(passages*0.3))
  .map((r) => ({ term: r.term, doc: r.doc, pct: +(100*r.doc/passages).toFixed(2) }));

console.log(JSON.stringify({
  passages,
  derivedAt30pct: { n: derived.length, terms: derived },
  listedButNotDerived: STOPWORDS.filter((w) => !derived.some((d) => d.term === w)).map(pct),
  collisions: Object.entries(COLLISIONS).map(([t, meaning]) => ({ ...pct(t), meaning, onList: STOPWORDS.includes(t) })),
  unlistedAndCostly: UNLISTED.map(pct).sort((a,b) => b.doc - a.doc),
}, null, 2));
