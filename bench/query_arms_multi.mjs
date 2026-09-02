/**
 * Latency and result quality for several (code arm, index file) pairs, interleaved
 * query by query.
 *
 * Derived from the spec repo's bench/query_arms.mjs, which drives several code arms over
 * ONE index file. That discipline cannot apply here: the three designs under comparison
 * (stock fold, dual-token, expansion) *by construction* live in three different index
 * files — the design decides what the file holds. So each arm opens its own file, the
 * passes are interleaved query by query across arms, and every cross-arm LATENCY
 * comparison is labelled cross-file (the page-cache trap the same-file rule exists for;
 * mitigated here by 125 GB of RAM against 3 GB of files, a discarded warm-up pass, and
 * interleaving so machine-state drift shows up inside an arm rather than between arms).
 * The CONTENT columns (rank-biased overlap, top-1 agreement against the stock arm) are
 * cache-independent.
 *
 * Channel: SqliteSearchIndex.query() directly, mode=keyword — NOT the MCP server.
 * For the expansion arm it also replays the query-side expansion against the arm's own
 * accent_variants table, recording per-query variant counts and lookup cost.
 */
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, writeFileSync } from 'node:fs';
import { makeArmProbe, pct, rbo } from './query_arms_lib.mjs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
// --pairs arm=distRoot=indexPath,arm=distRoot=indexPath,...
const pairs = args.pairs.split(',').map((p) => {
  const [arm, dist, index] = p.split('=');
  return { arm, dist, index };
});
const repeat = Number(args.repeat ?? 6);
const limit = Number(args.limit ?? 20);
const referenceArm = args.reference ?? 'stock';
const silent = { debug() {}, info() {}, warn() {}, error() {} };

const queries = readFileSync(args.queries, 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith('#'));

const opened = [];
for (const p of pairs) {
  const root = `${p.dist}/features/search`;
  const { SqliteSearchIndex } = await import(`${root}/sqlite-index.js`);
  const tk = await import(`${root}/tokenize.js`);
  let qt;
  try {
    qt = await import(`${root}/query-terms.js`);
  } catch {
    qt = undefined;
  }
  const idx = new SqliteSearchIndex({ embedder: null, logger: silent, path: p.index });
  await idx.open();
  // For the expansion arm: its own variants table, opened read-only beside the index.
  // Each arm's droplist comes from its OWN file here — unlike query_arms.mjs, where every
  // arm shares one index and therefore one list.
  const meta = new DatabaseSync(p.index, { readOnly: true });
  const hasVariants = !!meta
    .prepare("SELECT name FROM sqlite_master WHERE name='accent_variants'")
    .get();
  const droplist = new Set(
    (meta.prepare("SELECT value FROM meta WHERE key='droplist'").get()?.value ?? '').split(' ').filter(Boolean),
  );
  meta.close();
  const vdb = hasVariants ? new DatabaseSync(p.index, { readOnly: true }) : null;
  const vstmt = vdb ? vdb.prepare('SELECT term, df FROM accent_variants WHERE folded = ?') : null;
  // Refuses here, before any latency is measured, on an arm whose pruning it cannot read.
  const probe = makeArmProbe({ name: p.arm, tokenize: tk.tokenize, queryTerms: qt, isStopword: tk.isStopword }, droplist);
  opened.push({ ...p, idx, tk, qt, vdb, vstmt, probe });
}

const rows = new Map();
for (const a of opened) for (const q of queries) rows.set(`${a.arm} ${q}`, { arm: a.arm, query: q, ms: [], ids: [] });

// Pass 0 is the warm-up and is discarded.
for (let pass = 0; pass <= repeat; pass++) {
  for (const q of queries) {
    for (const a of opened) {
      const t0 = performance.now();
      const hits = await a.idx.query(q, { limit, mode: 'keyword' });
      const ms = performance.now() - t0;
      const r = rows.get(`${a.arm} ${q}`);
      if (pass > 0) r.ms.push(+ms.toFixed(2));
      r.ids = hits.map((h) => h.itemKey);
    }
  }
  process.stderr.write(`pass ${pass}/${repeat}\n`);
}

// Expansion accounting, replayed once per query against the expansion arm's own code
// path: which terms expand, to how many variants, and what the lookup itself costs.
for (const a of opened) {
  if (!a.vstmt || !a.tk.accentKey) continue;
  for (const q of queries) {
    const r = rows.get(`${a.arm} ${q}`);
    // Through the shared probe (ticket 0541), not a direct two-argument call: the r5
    // `pruneTerms` takes (terms, prunable, whenNothingSurvives) and exports no
    // `isStopword`, so the old call passed `undefined` as the predicate and got the raw
    // set back — expansion accounting over terms the arm never searched on.
    const pruned = a.probe.termsFor(q).terms;
    const t0 = performance.now();
    const groups = pruned.map((t) => {
      if (a.tk.accentKey(t) !== t) return { term: t, variants: [] };
      const variantRows = a.vstmt.all(t);
      const hasDf = variantRows.length && variantRows[0].df !== undefined;
      const variants = variantRows.filter((v) => v.term !== t);
      if (hasDf) {
        // Replays the shipped dominance gate: expand only when the accented spellings
        // outweigh the typed one.
        const self = variantRows.find((v) => v.term === t)?.df ?? 0;
        const sum = variants.reduce((s, v) => s + v.df, 0);
        if (sum <= self) return { term: t, variants: [] };
      }
      return { term: t, variants: variants.map((v) => v.term) };
    });
    const lookupMs = performance.now() - t0;
    const expanded = groups.filter((g) => g.variants.length);
    r.expansion = {
      terms: pruned.length,
      expanded_terms: expanded.length,
      added_variants: expanded.reduce((s, g) => s + g.variants.length, 0),
      lookup_ms: +lookupMs.toFixed(3),
      detail: expanded.map((g) => `${g.term}->${g.variants.join('|')}`),
    };
  }
}
for (const a of opened) {
  await a.idx.close();
  a.vdb?.close();
}

const out = {
  pairs,
  queries: args.queries,
  reference: referenceArm,
  repeat,
  limit,
  channel:
    'SqliteSearchIndex.query() directly, mode=keyword — NOT the MCP server. Each arm on ITS OWN index file (the designs differ in what the file holds); latency columns are cross-file, content columns are not.',
  per_query: [...rows.values()],
  summary: {},
};
const ref = [...rows.values()].filter((x) => x.arm === referenceArm);
for (const a of opened) {
  const rs = [...rows.values()].filter((r) => r.arm === a.arm);
  const all = rs.flatMap((r) => r.ms);
  let identical = 0, jac = 0, ord = 0, top1 = 0;
  for (const r of rs) {
    const u = ref.find((x) => x.query === r.query);
    if (!u) continue;
    if (JSON.stringify(r.ids) === JSON.stringify(u.ids)) identical++;
    if (r.ids[0] !== undefined && r.ids[0] === u.ids[0]) top1++;
    const A = new Set(r.ids), B = new Set(u.ids);
    const inter = [...A].filter((x) => B.has(x)).length;
    const uni = new Set([...A, ...B]).size;
    jac += uni ? inter / uni : 1;
    ord += rbo(r.ids ?? [], u.ids ?? []);
  }
  const exp = rs.filter((r) => r.expansion);
  out.summary[a.arm] = {
    index: a.index,
    // How this arm's pruning was read (ticket 0541). Only the expansion accounting uses
    // it here, but the column that says HOW a number was obtained belongs beside it.
    probe_shape: a.probe.shape,
    prune_predicate: a.probe.predicate_source,
    n: all.length,
    p50_ms: +pct(all, 0.5).toFixed(1),
    p95_ms: +pct(all, 0.95).toFixed(1),
    max_ms: +Math.max(...all).toFixed(1),
    mean_jaccard_to_reference: ref.length ? +(jac / rs.length).toFixed(3) : null,
    mean_rbo_to_reference: ref.length ? +(ord / rs.length).toFixed(3) : null,
    top1_same_as_reference: ref.length ? top1 : null,
    ordered_identical_to_reference: ref.length ? identical : null,
    queries: rs.length,
    ...(exp.length
      ? {
          expansion: {
            queries_with_expansion: exp.filter((r) => r.expansion.expanded_terms > 0).length,
            total_added_variants: exp.reduce((s, r) => s + r.expansion.added_variants, 0),
            mean_lookup_ms: +(exp.reduce((s, r) => s + r.expansion.lookup_ms, 0) / exp.length).toFixed(3),
            max_lookup_ms: +Math.max(...exp.map((r) => r.expansion.lookup_ms)).toFixed(3),
          },
        }
      : {}),
  };
}
writeFileSync(args.out, JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary, null, 1));
