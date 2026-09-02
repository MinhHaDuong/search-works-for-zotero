// What the arm drivers share: rank agreement, percentiles, and — the part this file was
// written for — how a driver learns what an arm did to a query without assuming its shape.
//
// Ticket 0541. `query_arms.mjs` read two exports for its fallback bookkeeping,
// `query-terms.MIN_MATCH_TERMS` and `tokenize.isStopword`. The 0091 r5 arms export
// neither: pruning moved into `pruneTerms(terms, prunable, whenNothingSurvives)`, and the
// rule changed shape as well as name — the prune is never undone while a term survives, so
// there is no minimum to compare against at all. Against an r5 arm the old expression read
// `kept.length < undefined`, which is `false` for every query. The fallback column reported
// a measured zero, the latency columns looked fine, and nothing said the driver had lost
// the ability to see the thing it was measuring.
//
// So the rule here is: never emulate the arm's prune, always CALL it, and refuse when the
// arm's shape cannot be recognised. A driver that cannot introspect an arm must say so,
// because "this arm never fell back" and "I could not tell whether it fell back" are the
// same number and opposite facts.

/**
 * Rank-biased overlap: how much two ranked lists agree, weighted toward the top.
 *
 * Set overlap and strict ordered-equality were the two columns the arm drivers reported
 * before, and between them they missed the thing a reader wants: neither says how much the
 * ORDER moved. Jaccard cannot see order at all, and ordered-equality is all-or-nothing, so
 * a list with two adjacent items swapped scores the same as one that is unrecognisable.
 * The two also track each other closely enough on real data to look like one column
 * reported twice.
 *
 * RBO fixes both. It compares prefixes of increasing depth and discounts by p^(d-1), so a
 * disagreement at rank 1 costs far more than one at rank 20, and it is defined for lists
 * that do not hold the same items. p = 0.9 puts roughly 86% of the weight in the first ten
 * ranks, which is the part of a search result anyone reads.
 */
export const rbo = (a, b, p = 0.9) => {
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

/** Nearest-rank percentile of a sample. Null on an empty sample rather than NaN. */
export const pct = (xs, p) => {
  const s = [...xs].sort((x, y) => x - y);
  return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : null;
};

/**
 * Every shipped call site of the r5 `pruneTerms` passes `'raw'` (`bm25.ts`,
 * `sqlite-index.ts`, `index-manager.ts`), so that is what the probe passes. It is recorded
 * in the artifact rather than left implicit: the third argument decides what the arm does
 * with a query that prunes to nothing, and a driver that quietly chose the other value
 * would be measuring an arm nobody ships.
 */
export const R5_WHEN_NOTHING_SURVIVES = 'raw';

/**
 * How the probe read one arm. Emitted per arm into the artifact, because a column's
 * meaning depends on it and a reader cannot recover it from the number.
 *
 * - `tokenize-only` — no prune stage to introspect; the arm's `tokenize` prunes internally
 *   against a fixed list and has no fallback rule. `fell_back` is structurally false here,
 *   not measured.
 * - `prune-terms-r5` — the arm exports `pruneTerms(terms, prunable, whenNothingSurvives)`.
 * - `prune-terms-min` — the arm exports `pruneTerms(terms, prunable, min)` beside
 *   `MIN_MATCH_TERMS`.
 * - `prune-terms-pair` — the arm exports `pruneTerms(terms, prunable)`.
 * - `min-match-only` — no `pruneTerms`; the old emulation against `MIN_MATCH_TERMS`.
 */
export const PROBE_SHAPES = [
  'tokenize-only',
  'prune-terms-r5',
  'prune-terms-min',
  'prune-terms-pair',
  'min-match-only',
];

/**
 * Build the per-query term probe for one arm, or refuse.
 *
 * @param arm {{name: string, tokenize: Function, queryTerms: object|undefined,
 *             isStopword: Function|undefined}}
 * @param droplist {Set<string>} the index's stored droplist, the predicate of last resort
 * @returns {{shape: string, predicate_source: string, termsFor: (q: string) => object}}
 * @throws when the arm exports no shape this can read — deliberately, and naming what it
 *         found, because a silent zero here is indistinguishable from a real one.
 */
export function makeArmProbe(arm, droplist) {
  const qt = arm.queryTerms;
  const prune = qt?.pruneTerms;

  // The predicate the arm prunes BY. Its own `isStopword` when it has one; otherwise
  // membership of the droplist the index carries, which is what the corpus-derived arms
  // prune by anyway (`highDf()` in `sqlite-index.ts` is exactly that membership test).
  const predicate = arm.isStopword ?? ((t) => droplist.has(t));
  const predicateSource = arm.isStopword ? 'arm.tokenize.isStopword' : 'index droplist membership';

  let shape;
  let call;
  if (typeof prune === 'function') {
    const hasMin = typeof qt.MIN_MATCH_TERMS === 'number';
    if (prune.length >= 3 && hasMin) {
      shape = 'prune-terms-min';
      call = (raw) => prune(raw, predicate, qt.MIN_MATCH_TERMS);
    } else if (prune.length >= 3 || typeof qt.MIN_PHRASE_TERMS === 'number') {
      shape = 'prune-terms-r5';
      call = (raw) => prune(raw, predicate, R5_WHEN_NOTHING_SURVIVES);
    } else if (prune.length === 2) {
      shape = 'prune-terms-pair';
      call = (raw) => prune(raw, predicate);
    }
  } else if (qt && typeof qt.MIN_MATCH_TERMS === 'number') {
    // The pre-r5 emulation, kept so the driver still reads arms built before pruneTerms
    // existed. It is an emulation and says so in `shape`.
    shape = 'min-match-only';
    const min = qt.MIN_MATCH_TERMS;
    call = (raw) => {
      const kept = raw.filter((t) => !predicate(t));
      return kept.length < min ? raw : kept;
    };
  } else if (!qt) {
    shape = 'tokenize-only';
    call = (raw) => raw;
  }

  if (!shape) {
    throw new Error(
      `arm ${arm.name}: cannot introspect its pruning, so its fallback columns would be ` +
        'zeros nobody measured. Refusing rather than reporting.\n' +
        `  query-terms exports: ${qt ? Object.keys(qt).sort().join(', ') || '(none)' : '(no query-terms module)'}\n` +
        `  pruneTerms arity: ${typeof prune === 'function' ? prune.length : 'absent'}\n` +
        `  tokenize exports isStopword: ${arm.isStopword ? 'yes' : 'no'}\n` +
        `  known shapes: ${PROBE_SHAPES.join(', ')}`,
    );
  }

  return {
    shape,
    predicate_source: predicateSource,
    termsFor(q) {
      const raw = [...new Set(arm.tokenize(q))];
      const terms = call(raw);
      const prunable = raw.filter((t) => predicate(t));
      // The arm handed back terms it considers prunable while prunable terms existed:
      // it declined the prune. Read off the arm's OUTPUT rather than re-derived from its
      // threshold, which is the whole repair — it holds for every `prune-terms-*` shape
      // without the driver knowing the rule.
      //
      // `tokenize-only` is excluded by construction, not by measurement. That arm has no
      // separable prune stage for the probe to observe; its `tokenize` prunes internally
      // against a fixed list and never restores anything, so the predicate this probe
      // holds describes the index, not the arm, and every query would read as a fallback.
      const fellBack = shape !== 'tokenize-only' && prunable.length > 0 && terms.some((t) => predicate(t));
      return {
        terms,
        fellBack,
        // r5 can answer a query with nothing at all (`whenNothingSurvives: 'phrase'`),
        // a state the pre-r5 rule had no way to reach and the old driver no column for.
        emptied: raw.length > 0 && terms.length === 0,
        pruned: raw.filter((t) => !terms.includes(t)),
      };
    },
  };
}
