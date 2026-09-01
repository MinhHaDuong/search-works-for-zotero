/**
 * The three ranking penalties, read at the BM25 level: each arm's own code BUILDS the
 * index (so the file holds exactly what that design indexes), then bm25(passages_fts) is
 * read raw — index.query()'s fused scores are rank-reciprocals and cannot price a
 * penalty. The MATCH string given per arm is what that arm's query path produces for the
 * probe query (verified against expandTerm/tokenize by the suite).
 *   node penalties_probe2.mjs <distRoot> <label> <matchStyle: fold|dual|expand>
 */
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

const [dist, label, style] = process.argv.slice(2);
const { SqliteSearchIndex } = await import(`${dist}/features/search/sqlite-index.js`);
const silent = { debug() {}, info() {}, warn() {}, error() {} };

async function buildFile(docs) {
  const path = join(mkdtempSync(join(tmpdir(), 'pen-')), 'search-index.sqlite');
  const index = new SqliteSearchIndex({ embedder: null, logger: silent, path });
  await index.open();
  await index.build(docs.map((d) => ({ key: d.key, data: { itemType: 'book', title: 'F', abstractNote: d.text } })));
  await index.save();
  await index.close();
  return path;
}
function bm25For(path, match) {
  const db = new DatabaseSync(path, { readOnly: true });
  const rows = db
    .prepare(
      'SELECT p.item_key k, bm25(passages_fts) r FROM passages_fts JOIN passages p ON p.pid = passages_fts.rowid WHERE passages_fts MATCH ? ORDER BY r',
    )
    .all(match);
  db.close();
  // bm25() is negative, best first; report positive magnitudes.
  return Object.fromEntries(rows.map((x) => [x.k, +(-x.r).toFixed(4)]));
}

const out = { dist, label, style };

// (a) length penalty — filler differs only in marks; query the shared term.
{
  const fillerAcc = 'élève théorie générale déjà café résumé naïveté étude médaille prévision';
  const fillerPlain = 'eleve theorie generale deja cafe resume naivete etude medaille prevision';
  const pads = Array.from({ length: 20 }, (_, i) => ({ key: `P${i}`, text: `unrelated padding number ${i} about rivers mountains weather climate glaciers forests deserts oceans` }));
  const path = await buildFile([
    { key: 'ACC', text: `economics ${fillerAcc}` },
    { key: 'PLAIN', text: `economics ${fillerPlain}` },
    ...pads,
  ]);
  const s = bm25For(path, '"economics"');
  out.length_penalty = {
    accented_doc: s.ACC ?? null,
    plain_doc: s.PLAIN ?? null,
    penalty_pct: s.ACC != null && s.PLAIN ? +((1 - s.ACC / s.PLAIN) * 100).toFixed(1) : null,
  };
}

// (b) aboutness — a document ABOUT théorie vs one mentioning theorie once, query `theorie`.
{
  const pads = Array.from({ length: 20 }, (_, i) => ({ key: `P${i}`, text: `unrelated padding number ${i} about rivers mountains weather climate glaciers forests deserts oceans` }));
  const path = await buildFile([
    ...pads,
    { key: 'ABOUT', text: 'théorie économique: la théorie des jeux, théorie de la valeur, théorie monétaire, théorie du capital' },
    { key: 'PASSING', text: 'a footnote mentions theorie once amid unrelated hydrology sediment basin text' },
    { key: 'A2', text: 'une autre théorie générale' },
    { key: 'A3', text: 'la théorie des prix' },
  ]);
  const match = style === 'expand' ? '("theorie" OR "théorie")' : '"theorie"';
  const s = bm25For(path, match);
  const order = Object.entries(s).sort((x, y) => y[1] - x[1]).map(([k]) => k);
  out.aboutness = { match, scores: s, order, about_beats_passing: (s.ABOUT ?? -1) > (s.PASSING ?? -1) };
}

// (c) avgdl contamination — unrelated unaccented doc's score before/after accent-heavy filler.
{
  const base = [
    { key: 'TARGET', text: 'sediment transport in river basins under monsoon rainfall' },
    { key: 'OTHER', text: 'unrelated document about macroeconomic policy and inflation' },
    ...Array.from({ length: 20 }, (_, i) => ({ key: `P${i}`, text: `unrelated padding number ${i} about forests deserts oceans glaciers politics history art music` })),
  ];
  const filler = Array.from({ length: 8 }, (_, i) => ({
    key: `F${i}`,
    text: 'đại học kinh tế quốc dân năng lượng tái tạo phát triển bền vững môi trường chính sách kết quả nghiên cứu khoa học '.repeat(3),
  }));
  const match = '"sediment" OR "transport"';
  const before = bm25For(await buildFile(base), match).TARGET ?? null;
  const after = bm25For(await buildFile([...base, ...filler]), match).TARGET ?? null;
  out.avgdl_contamination = {
    score_without_filler: before,
    score_with_filler: after,
    shift_pct: before ? +(((after - before) / before) * 100).toFixed(1) : null,
  };
}

console.log(JSON.stringify(out, null, 1));
