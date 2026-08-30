// The keyword arm of ticket 0265's fused-RRF measurement: FTS5/bm25 over the SAME
// same-item probe set bench/vec_task_recall.mjs draws, so keyword-alone, vector-alone and
// fused can all be read against one golden set (answer-set metrics: sets, not order).
//
// This is NOT bench/fts5_bench.mjs (that one indexes a live Zotero storage/ directory of
// .zotero-ft-cache files, at zoteus's own 1200-char chunking, and times build/query cost --
// a different corpus, a different question). This indexes ticket 0265's own subsample
// corpus at ITS existing chunk boundaries (the same passages the vector arm embeds) and
// scores retrieval quality, not latency.
//
// A probe's own passage text is its "query": there is no separate query set with known
// relevance for this corpus (the same-item task's whole point is a target that needs no
// human labels -- bench/vec_task_recall.mjs's header). So the keyword arm's query is a
// small set of the probe passage's own distinctive words, OR-joined -- the standard
// "more-like-this" move for a document-length query -- rather than the full passage text
// verbatim, which FTS5 would implicitly AND into a near-certain zero-hit query.
//
// Independent of any embedding candidate or dtype: run ONCE per corpus and cache the
// per-probe ranked lists for bench/fused_recall.mjs to fuse against every (candidate,
// dtype) cell -- 18 fusions share one keyword arm rather than rebuilding it 18 times.
//
//   node bench/fts5_keyword_arm.mjs --corpus subsample-passages.txt --items subsample-items.txt \
//     --ords subsample-ords.txt --output keyword-arm.json
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { drawProbes } from './recall_probes.mjs';

const { values: opt } = parseArgs({
  options: {
    corpus: { type: 'string' },
    items: { type: 'string' },
    ords: { type: 'string' },
    output: { type: 'string' },
    topk: { type: 'string', default: '30' },
    gap: { type: 'string', default: '3' },
    probes: { type: 'string', default: '400' },
    seed: { type: 'string', default: '20260830' },
    'query-terms': { type: 'string', default: '12' },
  },
});
if (!opt.corpus || !opt.items || !opt.ords || !opt.output) {
  console.error(
    'usage: node bench/fts5_keyword_arm.mjs --corpus <f> --items <f> --ords <f> --output <json>',
  );
  process.exit(2);
}
const TOPK = Number(opt.topk);
const GAP = Number(opt.gap);
const QUERY_TERMS = Number(opt['query-terms']);

const texts = readFileSync(opt.corpus, 'utf8').split('\n').filter(Boolean);
const items = readFileSync(opt.items, 'utf8').split('\n').filter(Boolean);
const ords = readFileSync(opt.ords, 'utf8').split('\n').filter(Boolean).map(Number);
if (texts.length !== items.length || items.length !== ords.length) {
  console.error(`corpus (${texts.length}), items (${items.length}), ords (${ords.length}) disagree`);
  process.exit(2);
}
const N = texts.length;

const { byItem, eligible, probeIdx } = drawProbes({
  items, ords, gap: GAP, probes: Number(opt.probes), seed: opt.seed,
});

// A short multilingual stoplist, high-document-frequency function words that carry no
// topic signal -- not exhaustive (the corpus is French/English/German/Italian per
// bench/queries.txt), just enough that the top QUERY_TERMS words are content words, not
// "de la et the of und".
const STOP = new Set([
  'the','a','an','and','or','of','to','in','on','for','with','is','are','was','were','be',
  'by','as','at','that','this','it','from','we','our','their','its','these','those','not',
  'le','la','les','de','des','du','un','une','et','ou','est','sont','pour','dans','sur',
  'que','qui','ce','ces','se','au','aux','par','plus','ne','pas','il','elle','nous','vous',
  'der','die','das','und','ist','sind','ein','eine','mit','von','zu','auf','den','dem',
  'il','lo','la','le','gli','di','che','per','con','del','della','sono','anche',
]);

function extractKeywords(text, k) {
  const freq = new Map();
  for (const raw of text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []) {
    if (raw.length < 4 || STOP.has(raw)) continue;
    freq.set(raw, (freq.get(raw) ?? 0) + 1);
  }
  return [...freq.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, k)
    .map(([w]) => w);
}

/** FTS5 phrase-quoted OR query; a term containing a double quote is dropped rather than
 * risking a syntax error on hand-built query text. */
function buildMatchQuery(words) {
  return words
    .filter((w) => !w.includes('"'))
    .map((w) => `"${w}"`)
    .join(' OR ');
}

const db = new DatabaseSync(':memory:');
db.exec(`CREATE VIRTUAL TABLE passages USING fts5(
           body, item UNINDEXED, ord UNINDEXED, idx UNINDEXED,
           tokenize='unicode61 remove_diacritics 2')`);
const ins = db.prepare('INSERT INTO passages(rowid, body, item, ord, idx) VALUES (?,?,?,?,?)');
db.exec('BEGIN');
for (let i = 0; i < N; i++) ins.run(i + 1, texts[i], items[i], ords[i], i);
db.exec('COMMIT');
db.exec("INSERT INTO passages(passages) VALUES('optimize')");

// item is TEXT, so it cannot be bound positionally alongside the gap arithmetic in one
// expression portably across drivers; bind item and gap bounds separately and compare on
// the indexed columns FTS5 exposes as UNINDEXED (still ordinary SQL columns for WHERE).
const q = db.prepare(`
  SELECT idx, bm25(passages) AS s
  FROM passages
  WHERE passages MATCH ?
    AND NOT (item = ? AND (idx = ? OR ABS(ord - ?) < ?))
  ORDER BY s
  LIMIT ?
`);

let recall = 0;
let mrr = 0;
let zeroHitProbes = 0;
const ranklists = {};
const queryLengths = [];
for (const p of probeIdx) {
  const relevant = new Set(byItem.get(items[p]).filter((j) => j !== p && Math.abs(ords[j] - ords[p]) >= GAP));
  const kws = extractKeywords(texts[p], QUERY_TERMS);
  queryLengths.push(kws.length);
  const matchQuery = buildMatchQuery(kws);
  let rows = [];
  if (matchQuery) {
    try {
      rows = q.all(matchQuery, items[p], p, ords[p], GAP, TOPK);
    } catch (err) {
      console.error(`probe ${p}: FTS5 query failed (${err.message}); scored as zero hits`);
    }
  }
  if (rows.length === 0) zeroHitProbes++;
  // bm25() is smaller-is-better in SQLite's own convention (ORDER BY s ascending, as
  // bench/fts5_bench.mjs already does) -- rank 0 is the best match.
  ranklists[p] = rows.map((r) => r.idx);
  const hits = rows.filter((r) => relevant.has(r.idx)).length;
  recall += hits / Math.min(relevant.size, TOPK);
  const rank = rows.findIndex((r) => relevant.has(r.idx));
  if (rank >= 0) mrr += 1 / (rank + 1);
}

const result = {
  what: 'keyword arm (FTS5/bm25) of the same-item retrieval task, scored on ticket 0265\'s '
    + 'subsample corpus; shared across every (candidate, dtype) fusion cell, never rebuilt '
    + 'per cell',
  not_this: 'bench/results/0070-cosine-fusion/ is loop fusion -- a JIT/arithmetic '
    + 'optimisation of the vector scan\'s cosine function. This file has nothing to do '
    + 'with that; it is the keyword-search half of the RRF search-result fusion this '
    + 'ticket measures.',
  task: {
    relevant: `other passages of the probe's own item, at least ${GAP} chunks away`,
    query_construction: `top ${QUERY_TERMS} highest-frequency content words (len>=4, `
      + 'multilingual stoplist, ties broken alphabetically) of the probe passage itself, '
      + 'OR-joined as an FTS5 MATCH query -- the standard more-like-this move for a '
      + 'document-length query, since the same-item task has no separate query set',
    topk: TOPK,
    tokenizer: 'unicode61 remove_diacritics 2',
    bm25_convention: 'SQLite bm25() is smaller-is-better; ORDER BY s ASC, rank 0 = best',
  },
  corpus: { passages: N, items: byItem.size, eligible_probes: eligible.length },
  probes: { count: probeIdx.length, seed: opt.seed, zero_hit_probes: zeroHitProbes,
    mean_query_terms: Number((queryLengths.reduce((a, b) => a + b, 0) / queryLengths.length).toFixed(2)) },
  recall_at_topk: Number((recall / probeIdx.length).toFixed(4)),
  mrr: Number((mrr / probeIdx.length).toFixed(4)),
  probe_idx: probeIdx,
  ranklists,
};
writeFileSync(opt.output, `${JSON.stringify(result, null, 2)}\n`);
console.error(
  `keyword arm: recall@${TOPK} ${result.recall_at_topk} MRR ${result.mrr} `
  + `(${zeroHitProbes}/${probeIdx.length} zero-hit probes) -> ${opt.output}`,
);
