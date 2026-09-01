# Ticket 0091 — the three-PR series, as it stands

A checkpoint, written so a cold session can pick this up. Evidence, not authority: where
this touches the design, the owning document in `spec/` is the record.

## What the series is, and why it is three PRs

The ticket asked for a library-derived droplist. Measuring it turned up two prerequisites,
and the author ordered them ahead of it:

1. **Fix the degenerate query.** `to be or not to be` returns a confidently-ranked page of
   results about nothing.
2. **Keep diacritics.** The index folds them away, which in a multilingual library merges
   distinct words rather than normalising spelling.
3. **Derive the common-word list from the library** instead of shipping 29 English function
   words.

They are ordered because each earlier one changes what the later ones measure. The author's
reason for putting 2 ahead of 3 — "measurements without it are meaningless" — was tested
rather than assumed, and the test says the droplist itself is robust to the folding decision
(see below); the ordering stands for correctness reasons rather than measurement ones.

## Where the code is

Fork `MinhHaDuong/zoteus`, pushed and durable:

| branch | tip | what |
|---|---|---|
| `pr1-degenerate-r3` | `47461b7` | the degeneracy fix — **filed upstream as PR #45** |
| `pr2-expansion` | `6a201fa` | keep diacritics + dominance-gated query expansion (optional, ZOTEUS_ACCENT_EXPANSION, default on) + migration rung + B3 fix |
| `pr3-droplist-r5` | `11385a2` | the derived list, restacked on the settled PR 2 |

Stacked in that order on `base-v1.12.0` (= upstream `b05ed69`, v1.12.0). Gates green on
each tip; the full stack runs 958 vitest passed / 7 skipped. Superseded branches left
intact for the record: `pr2-diacritics-r3` (`f80d860`, the measured-and-rejected
dual-token design), `pr3-droplist-r3`/`-r4` (`bb5bb4c`/`cf0be56`). Fork PRs #4 #5 #6
hold an earlier round and are stale; #1 #2 #3 closed as superseded.

## What has gone upstream

PR 1 was filed 2026-09-01 with the author's authorization as upstream **PR #45**, from
fork branch `degenerate-query` at `47461b7`, body sent verbatim from
`verification/UPSTREAM-PR-0091-DEGENERATE.md` and verified on the PR page. Three rulings
landed the same day (ledger): PR 1 files now; the budget is **one slot per PR** — PR 1
spends the held stopwords-follow-up slot, PRs 2 and 3 each need a fresh grant when ready;
and PR 2's design question is answered by **measuring the query-expansion alternative**
before ruling, not by ruling on one measured arm.

The other two filed 2026-09-01 with the author's slot grants (ledger, same day),
bodies sent verbatim and verified on their pages: **PR #46** (diacritics + optional
expansion, from `pr2-expansion` @ `6a201fa`) and **PR #47** (droplist, from
`pr3-droplist-r5` @ `11385a2`). The whole series is now in flight; #47 stacks on
`6b7c152` (pre-flag) and rebases once #46 merges.

## The design decision — SETTLED by measurement, 2026-09-01

Per the author's ruling, the query-expansion alternative was built and measured
head-to-head against the dual-token design over copies of the same 477 512-passage index.
**Expansion won on every structural axis** — 0 % BM25 length penalty against 23,5 %, no
IDF distortion, migration 43,5 s against 116,4 s, no 944-codepoint pinned set needed,
per-query cost ≤ 0,18 ms — and needed one refinement the fixtures could not show: naive
expansion collapsed top-1 agreement (rare accented siblings of common words outranking the
typed term), fixed by a knob-free dominance gate (expand only where accented spellings
outweigh the typed one by document frequency). One premise disproven with evidence: the
tokenizer declaration changes either way, so expansion does NOT avoid the migration —
blocker B3 is therefore not moot and is fixed on the branch (non-corruption migration
failure refuses and preserves the file; only corruption sidelines). Decision record and
figures: `verification/UPSTREAM-PR-0091-DIACRITICS.md`, artifacts
`arms-expansion-*.json`, `expansion-{penalties,reach,migration}.json`. Transform order on
the restacked PR 3: prune first, then expand the survivors — the order the code already
forced, verified sensible and asserted end to end on both backends.

The section below records the question as it stood before the measurement, kept for
provenance.

**PR 2's design costs more than it was proposed at, and the alternative has not been tried.**

PR 2 keeps each word as written and indexes its mark-stripped form beside it, so an
unaccented query still reaches an accented document. Review measured three costs that were
not on the table when that design was chosen:

- **A pinned 944-codepoint set is required.** `unicode61` does not treat combining marks
  uniformly under `remove_diacritics 0`: of 2 303 marks it joins 944 to the surrounding word
  and splits on 1 359, and the boundary runs through the middle of the Latin block (U+0300–
  U+0304 join, U+0305 splits, U+0306–U+030C join, U+030D–U+030E split). So a JS token class
  of `[\p{L}\p{N}]+` is wrong for 944 codepoints and `\p{M}` would be wrong for 1 359.
  Agreement needs the joining set generated and pinned, as `UNICODE61_KEEPS_CASE` already is.
  Artifact: `bench/results/0091-droplist/unicode61-mark-boundaries.json`, produced by
  `verification/probes/unicode61-mark-boundaries.mjs`.
- **Accented documents are penalised in ranking.** The extra tokens inflate `doc.length`, so
  BM25 length normalisation degrades a French or Vietnamese document's score on *every*
  query — measured at about 17% on a controlled pair differing only in whether the filler was
  accented. A change motivated by Vietnamese demotes Vietnamese documents.
- **The stripped token's IDF is roughly halved** (4,997 → 2,335 on a constructed corpus),
  because its document frequency is the union of "genuinely spelled that way" and "merely
  augmented"; and capping the extra token at one occurrence can rank a document *about*
  `théorie` below one mentioning `theorie` once in passing.

The alternative, not yet tried: keep the marks, change nothing about what is indexed, and
expand *queries* instead — an unaccented query expands to the accented variants the
vocabulary actually holds. It adds no tokens, so it incurs none of the ranking costs, and it
needs no second codepoint set. It costs a vocabulary lookup per query term and a longer MATCH
string. **This is the decision waiting on the author.**

## What is settled, with its evidence

- **The fallback must never fire while a term survives.** An earlier rule fell back whenever
  the prune left fewer terms than it dropped; review reproduced `in the brain` returning a
  decoy ahead of the right document. Nothing separates an accidental survivor (`not`, 27,3%)
  from a real one (`brain`, 0,10%) except how common each is, which a fixed list cannot know.
  Verified against the same build with the change reverted, on the real 477 512-passage
  index: every ordinary query returns the same documents in the same order as stock; only the
  soliloquy differs.
- **No threshold separates content words from function words.** In the 30–38% band they
  interleave: `or` 37,8 (function), `new` 35,7 (content), `economics` 35,1 (content), `at`
  33,7 (function), `number` 32,6 (content), `have` 32,2, `can` 31,7 (function), `result` 30,8
  (content). Raising the cutoff to save `economics` stops pruning `at`/`have`/`can` and still
  prunes `new`. The threshold is a **cost** decision, not a meaning one: pruning `economics`
  is correct on cost, and the only harm — a query left with nothing — is what the fallback
  covers. Artifact: `bench/results/0091-droplist/droplist-adapts-477k.json`.
- **The droplist is robust to the folding decision.** Derived from the migrated, unfolded
  477 512-passage index it is the *same* 23 terms in the same order, every document frequency
  unchanged but `a` (77,20% → 74,51%, single-letter accented tokens no longer collapsing into
  it).
- **The rule adapts to the corpus.** The same derivation over language-selected subsets of the
  same library yields 38 French terms from the French passages and 59 mostly-Vietnamese terms
  from the Vietnamese ones, against 23 English ones over the whole library.
- **The migration works at real scale.** Schema 1 → 2 over 477 512 passages: 137,6 s, zero
  embedder calls. Note the consequence: an older build cannot read a migrated database — it
  sidelines it and starts an empty one. That is correct, and it destroyed a migrated index
  here when stock was added as a measurement arm against it.
- **`İ` and the snippet offsets.** Both fixed with controls; reverting either turns the new
  tests in `accent-folding.test.ts` red. The `İ` fix came from re-running the keep-case set's
  own generator against the tokenizer the commit actually ships (`remove_diacritics 0`): 446
  codepoints against the 445 pinned, one difference. Probe:
  `verification/probes/unicode61-keeps-case-sweep.mjs`.

## Measurement, and how to reproduce it

`bench/query_arms.mjs` drives several code arms over ONE index file, interleaved query by
query. Query sets: `bench/queries-x2.txt` (EN), `-fr`, `-vi`, and `bench/queries-short.txt`.
Artifacts under `bench/results/0091-droplist/`.

Two things about the numbers:

- **Every arms file names its channel and its index**, because they are not interchangeable.
  These drive the index object directly, not the MCP server, so they are not comparable with
  figures taken end to end. And stock cannot read a schema-2 database, so the stock baseline
  is measured on the pre-migration index and labelled so.
- **Fidelity-to-unpruned is not a quality metric.** It scored the broken fallback 1,000 —
  perfect — exactly where it was returning worse results more slowly, because it rewards
  reproducing a query the user did not type. The driver now also reports rank-biased overlap
  and top-1 agreement. Top-1 is the informative one: it is 19 or 20 of 20 in every arm and
  every language, so pruning almost never changes the result a reader sees first — it
  reshuffles ranks 2 to 20.

## Still to do

Closed since the previous revision of this list: the design decision (measured, expansion
won — see above); the 944-codepoint blocker (moot under expansion); B3 (fixed on
`pr2-expansion`, red-first); the held documentation findings (the five stale sites,
CHANGELOG entries for both PRs, the `SCHEMA_MIGRATIONS` docstring — all applied under the
winning design); PR 3's review panel (round 4, six findings fixed, then restacked as r5
with two interaction tests and a full-stack re-measurement,
`arms-stack-{en,fr,vi,short}.json`).

Remaining:

- **The two upstream filings.** Both rulings that blocked them landed 2026-09-01
  (DECISIONS.md, two ledger entries): the author granted the remaining two slots — PR 2
  from `pr2-expansion` @ `6a201fa` (body `UPSTREAM-PR-0091-DIACRITICS.md`), then PR 3 from
  `pr3-droplist-r5` @ `11385a2` (body `UPSTREAM-PR-0091-DROPLIST.md`), each sent as
  drafted once the repo-side record merges through review — and the soliloquy-survivor
  question (`not` at 27,3 %) was presented and not reopened, so the shipped zero-survivor
  fallback rule stands unless upstream review reopens it. What remains is the filing
  itself: neither PR is filed.
- **PR 3's stack, before it files.** Verified on the fork 2026-09-01:
  `pr3-droplist-r5` (`11385a2`) has `6b7c152` as its parent, while `pr2-expansion` has
  advanced to `6a201fa` (the `ZOTEUS_ACCENT_EXPANSION` commit) — the compare endpoint
  reads the two as diverged, one ahead and one behind. So PR 3 does not carry the flag
  commit. Harmless while PR 2 files first and carries it, but decide whether to restack
  before filing, and do not describe PR 3 as stacked on the current PR 2 tip.
- `Ticket-ref` scoping: no ticket scopes "keep diacritics + first migration rung"; PR 2
  currently rides ticket 0091.
- No speed doctor pass on the latency claims.
- `bench/query_arms.mjs` assumes the pre-r5 exports (`MIN_MATCH_TERMS`/`isStopword`) and
  would mis-report fallback columns against r5-shaped arms; the adapted runner used for
  the stack measurement reads each arm's own `pruneTerms`.
- Filing note for PR 3: the stack's first open of a variants-less schema-2 index derives
  and writes `accent_variants` (~2 s) — a read-path expectation worth one line.
