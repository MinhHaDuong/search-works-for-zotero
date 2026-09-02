/**
 * Latency and result quality for several code arms over one index file.
 *
 * **Why the arms share a file.** An earlier attempt on this ticket gave each arm its own
 * copy of the index and read stock 9 to 14 times slower on one copy than the same binary
 * read on the other minutes later — the page cache under load, not the code. Every arm
 * here opens the same path, and the arms are interleaved query by query, so a drift in
 * machine state shows up as disagreement between repeats of one arm rather than as a
 * difference between arms.
 *
 * **Channel.** This drives the index object directly — `SqliteSearchIndex.query()` with
 * `mode: 'keyword'` — not the MCP server. That is the layer the change lives at, and it
 * keeps the transport's constant overhead out of a comparison between arms. Numbers from
 * here are therefore NOT comparable with figures taken end-to-end through the server;
 * they are comparable with each other, which is what the arms need.
 *
 * **What it records per query and per arm**: every latency sample, the ordered result
 * list, the terms the arm actually searched on, and whether the degeneracy floor fired.
 * The last two are recomputed from the arm's own exported `tokenize`/`pruneTerms` and the
 * droplist in `meta`, so they describe that arm and not an idealisation of it.
 *
 * Ticket 0541: that last sentence was not true. The fallback columns were computed by
 * re-deriving the arm's rule from `MIN_MATCH_TERMS` and `isStopword`, two exports the r5
 * arms dropped — so against an r5 arm the comparison read `kept.length < undefined` and
 * every query reported "did not fall back". The probe now calls the arm's own `pruneTerms`
 * and reads its OUTPUT, and refuses outright on an arm whose shape it cannot recognise;
 * `bench/query_arms_lib.mjs` holds it, together with the `rbo`/`pct` helpers this driver
 * used to keep its own copy of.
 */
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, writeFileSync } from 'node:fs';
import { makeArmProbe, pct, rbo } from './query_arms_lib.mjs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const indexPath = args.index;
const distRoot = args.dists;
const arms = (args.arms ?? 'stock,fallback,droplist,none').split(',');
const repeat = Number(args.repeat ?? 6);
const limit = Number(args.limit ?? 20);
const silent = { debug() {}, info() {}, warn() {}, error() {} };

const queries = readFileSync(args.queries, 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith('#'));

/** The stored droplist, read once — every arm that prunes by the corpus reads the same one. */
const meta = new DatabaseSync(indexPath, { readOnly: true });
const droplist = new Set(
  (meta.prepare("SELECT value FROM meta WHERE key='droplist'").get()?.value ?? '').split(' ').filter(Boolean),
);
meta.close();

const opened = [];
for (const arm of arms) {
  const root = `${distRoot}/${arm}/features/search`;
  const { SqliteSearchIndex } = await import(`${root}/sqlite-index.js`);
  const tk = await import(`${root}/tokenize.js`);
  // Stock has no query-terms module: its pruning happens inside tokenize(). Reading each
  // arm's own code rather than assuming a shared shape is the point.
  let qt;
  try {
    qt = await import(`${root}/query-terms.js`);
  } catch {
    qt = undefined;
  }
  const index = new SqliteSearchIndex({ embedder: null, logger: silent, path: indexPath });
  await index.open();
  // Built here rather than at first use: an arm this driver cannot introspect must stop
  // the run before any latency is measured, not produce a report with one hollow column.
  const probe = makeArmProbe({ name: arm, tokenize: tk.tokenize, queryTerms: qt, isStopword: tk.isStopword }, droplist);
  opened.push({ arm, index, probe });
}

const rows = new Map(); // `${arm} ${query}` -> record
for (const a of opened) {
  for (const q of queries) {
    rows.set(`${a.arm} ${q}`, { arm: a.arm, query: q, ms: [], ...a.probe.termsFor(q) });
  }
}

// Pass 0 is the warm-up and is discarded: it pays for whatever the file has not been read
// into cache yet, and that cost belongs to the machine, not to the arm.
for (let pass = 0; pass <= repeat; pass++) {
  for (const q of queries) {
    for (const a of opened) {
      const t0 = performance.now();
      const hits = await a.index.query(q, { limit, mode: 'keyword' });
      const ms = performance.now() - t0;
      const r = rows.get(`${a.arm} ${q}`);
      if (pass > 0) r.ms.push(+ms.toFixed(2));
      r.ids = hits.map((h) => h.itemKey);
    }
  }
  process.stderr.write(`pass ${pass}/${repeat}` + String.fromCharCode(10));
}
for (const a of opened) await a.index.close();

const out = {
  index: indexPath,
  queries: args.queries,
  arms,
  reference: args.reference ?? 'none',
  repeat,
  limit,
  channel:
    'SqliteSearchIndex.query() directly, mode=keyword, embeddings off — NOT the MCP server; comparable across these arms only',
  droplist: [...droplist].sort(),
  per_query: [...rows.values()],
  summary: {},
};

// Which arm the fidelity columns are measured against. Named rather than assumed: the
// unpruned arm is not always called 'none', and a reference that silently fails to match
// reports null rather than wrong, which is the only reason this was noticed at all.
const referenceArm = args.reference ?? 'none';
const ref = [...rows.values()].filter((x) => x.arm === referenceArm);
for (const arm of arms) {
  const rs = [...rows.values()].filter((r) => r.arm === arm);
  const all = rs.flatMap((r) => r.ms);
  let identical = 0;
  let jac = 0;
  let ord = 0;
  let top1 = 0;
  for (const r of rs) {
    const u = ref.find((x) => x.query === r.query);
    if (!u) continue;
    if (JSON.stringify(r.ids) === JSON.stringify(u.ids)) identical++;
    if (r.ids[0] !== undefined && r.ids[0] === u.ids[0]) top1++;
    const A = new Set(r.ids);
    const B = new Set(u.ids);
    const inter = [...A].filter((x) => B.has(x)).length;
    const uni = new Set([...A, ...B]).size;
    jac += uni ? inter / uni : 1;
    ord += rbo(r.ids ?? [], u.ids ?? []);
  }
  out.summary[arm] = {
    n: all.length,
    p50_ms: +pct(all, 0.5).toFixed(1),
    p95_ms: +pct(all, 0.95).toFixed(1),
    max_ms: +Math.max(...all).toFixed(1),
    // How the fallback columns were obtained for THIS arm. A count means nothing without
    // it: `tokenize-only` reports a structural zero, the `prune-terms-*` shapes report a
    // measured one, and an arm whose shape could not be read never reaches this line —
    // the run stops at open (ticket 0541).
    probe_shape: opened.find((a) => a.arm === arm).probe.shape,
    prune_predicate: opened.find((a) => a.arm === arm).probe.predicate_source,
    fellBack: rs.filter((r) => r.fellBack).length,
    // r5 can answer with no terms at all. The pre-r5 rule could not reach that state, so
    // there was no column for it and the queries that reach it looked like ordinary ones.
    emptied: rs.filter((r) => r.emptied).length,
    // Which items came back, ignoring order.
    mean_jaccard_to_reference: ref.length ? +(jac / rs.length).toFixed(3) : null,
    // How much the ORDER agrees, weighted toward the top. The column Jaccard cannot give.
    mean_rbo_to_reference: ref.length ? +(ord / rs.length).toFixed(3) : null,
    // The single result most people actually look at.
    top1_same_as_reference: ref.length ? top1 : null,
    // Strict all-or-nothing equality of the whole ordered list, kept because it is the
    // hardest bar and it is what "identical" honestly means.
    ordered_identical_to_reference: ref.length ? identical : null,
    queries: rs.length,
  };
}

writeFileSync(args.out, JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary, null, 1));
