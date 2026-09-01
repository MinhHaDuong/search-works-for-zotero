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
 */
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, writeFileSync } from 'node:fs';

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
  opened.push({ arm, index, tokenize: tk.tokenize, qt, isStopword: tk.isStopword });
}

/** What terms this arm will actually search on, and whether the floor fired. */
function termsFor(a, q) {
  const raw = [...new Set(a.tokenize(q))];
  if (!a.qt) return { terms: raw, fellBack: false, pruned: [] }; // stock: tokenize already pruned
  const predicate = a.isStopword ?? ((t) => droplist.has(t)); // PR A prunes by the list, PR B by the corpus
  const kept = raw.filter((t) => !predicate(t));
  const fellBack = kept.length < a.qt.MIN_MATCH_TERMS;
  return { terms: fellBack ? raw : kept, fellBack, pruned: raw.filter((t) => predicate(t)) };
}

const rows = new Map(); // `${arm} ${query}` -> record
for (const a of opened) {
  for (const q of queries) {
    rows.set(`${a.arm} ${q}`, { arm: a.arm, query: q, ms: [], ...termsFor(a, q) });
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

/**
 * Rank-biased overlap: how much two ranked lists agree, weighted toward the top.
 *
 * Set overlap and strict ordered-equality were the two columns this reported before, and
 * between them they missed the thing a reader wants: neither says how much the ORDER moved.
 * Jaccard cannot see order at all, and ordered-equality is all-or-nothing, so a list with
 * two adjacent items swapped scores the same as one that is unrecognisable. The two also
 * track each other closely enough on real data to look like one column reported twice.
 *
 * RBO fixes both. It compares prefixes of increasing depth and discounts by p^(d-1), so a
 * disagreement at rank 1 costs far more than one at rank 20, and it is defined for lists
 * that do not hold the same items. p = 0.9 puts roughly 86% of the weight in the first ten
 * ranks, which is the part of a search result anyone reads.
 */
const rbo = (a, b, p = 0.9) => {
  const depth = Math.max(a.length, b.length);
  if (!depth) return 1;
  const A = new Set();
  const B = new Set();
  let sum = 0;
  let weight = 0;
  for (let d = 1; d <= depth; d++) {
    if (a[d - 1] !== undefined) A.add(a[d - 1]);
    if (b[d - 1] !== undefined) B.add(b[d - 1]);
    let shared = 0;
    for (const x of A) if (B.has(x)) shared++;
    const w = Math.pow(p, d - 1);
    sum += w * (shared / d);
    weight += w;
  }
  return sum / weight;
};

const pct = (xs, p) => {
  const s = [...xs].sort((x, y) => x - y);
  return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : null;
};

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
    fellBack: rs.filter((r) => r.fellBack).length,
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
