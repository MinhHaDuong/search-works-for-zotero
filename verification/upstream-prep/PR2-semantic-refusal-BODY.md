# fix(search): refuse `mode:"semantic"` when nothing can embed the query

Base: `4467663` (main at v1.16.0 + the readme commit).
Branch: `fix/semantic-refuses-without-embedder` — 2 commits, +101 / −7 over 3 files.

## The symptom

Build the index with an embedder, then restart the server with `ZOTEUS_EMBEDDINGS=off`
and run a semantic search. The tool answers:

```
No matches for "deep learning".
```

That is the whole reply. No `isError`, no notice, no cause. It is byte-identical to
what an honest empty result looks like, so the caller — a model, usually — reads it as
"this library holds nothing on the subject" and moves on. It is the #7 failure mode that
the 0-vector refusal was written to prevent, arriving through the one door that refusal
does not cover.

The index in this state is not damaged and is not empty: the same query in `auto` or
`keyword` mode returns hits normally.

## Mechanism

Three things have to line up, and all three are working as designed on their own.

1. **The vectors survive the switch-off.** `SearchIndexBase.reconcileVectorProvenance`
   (`src/features/search/index-manager.ts:688`) drops stored vectors only when the
   *current* embedder identity disagrees with the stored one. With embeddings off there
   is no current identity, so the guard short-circuits and the rows are kept — correctly,
   since they are unusable, not known-wrong. `tests/features/embedding-config.test.ts:389`
   already pins that behaviour ("stays silent with no active embedder, which never queries
   them anyway"). So `hasVectors` is **true**.

2. **The refusal only tests the vectors.** `src/tools/semantic-search.ts:102` reads
   `args.mode === 'semantic' && !ctx.search.hasVectors && !ctx.search.storeFault`.
   With vectors present it does not fire, and the handler falls through to `query()`.

3. **`query()` closes both rankers and returns `[]`.** In
   `SearchIndexBase.query` (`index-manager.ts:2363`): the query is embedded only when
   `mode !== 'keyword' && this.opts.embedder && this.counts().vectors`, and with
   embeddings off `opts.embedder` is undefined, so `qv` stays undefined. Two lines set
   the rankers: `keywordOpen = mode !== 'semantic'` → `false`, and
   `vectorOpen = qv !== undefined` → `false`. The loop runs once over two empty
   candidate lists and returns `[]`.

Then the summary is assembled at `semantic-search.ts:133`. It appends `embedderNotice`,
and `build.ts:70` reads `if (s.embedderActive || s.embedderConfigured === 'off') return ''`
— deliberately silent about a provider that was switched off on purpose, because a
keyword-only index by choice should not be lectured about it on every call
(`tests/features/embedder-degradation.test.ts:123` pins that). `staleVectorsNotice` and
`unembeddedNotice` are both empty here too. What is left is the bare `No matches`.

Each piece is right; the composition is the defect.

## State matrix

`mode:"semantic"`, index non-empty, no store fault.

| # | vectors | embedder | before | after |
|---|---|---|---|---|
| 1 | present | configured and working | ranks normally, hits returned | **unchanged** |
| 2 | present | `ZOTEUS_EMBEDDINGS=off` | `No matches for "…".` — `isError` unset, no cause | **error** naming the stranded vectors and `ZOTEUS_EMBEDDINGS` |
| 3a | present | configured, never started (runtime missing) | `No matches …` + `Semantic ranking is OFF (embeddings=local requested but not active): …` — explained, but not an error | **error** naming the provider and its cause |
| 3b | present | configured, throws during *this* query | `No matches …` + the same `Semantic ranking is OFF …` notice | **unchanged** |
| 4 | none | configured but down | error: `… this index has 0 vectors. No vectors exist because the embedder is not active: …` | **unchanged, byte for byte** |
| 4b | none | active | error: `… this index has 0 vectors. The index holds no vectors yet. Rebuild it with zotero_index action:"build" …` | **unchanged, byte for byte** |
| 5 | none | off | error: `… this index has 0 vectors. No vectors exist because the embedder is not active: unavailable` | **unchanged, byte for byte** |

`auto` and `keyword` are untouched in every row — they do not need the query embedded,
and the gate is still `args.mode === 'semantic'`.

State 2 is the defect. State 3a changes as a consequence of fixing it and I think that is
right: it is the same condition as state 4, which already errors, differing only in
whether the index happens to hold rows the query cannot reach. Leaving it as a non-error
would keep the refusal keyed on an irrelevant fact. It also makes the tool description
true again — it already promised "when the configured embedder is not running … it
returns an error naming the cause instead of an empty result set", which state 3a did not
honour. Say the word if you would rather 3a stayed a notice; it is one clause.

State 3b is deliberately left alone. `embedderActive` is still true when the gate runs
(the failure has not happened yet), so the pre-query gate cannot see it, and the existing
post-query notice already reports it. Catching it too would mean re-checking after
`query()` — a different change, and not this bug.

## The fix

`src/tools/semantic-search.ts`, one condition and one message branch:

```diff
-if (args.mode === 'semantic' && !ctx.search.hasVectors && !ctx.search.storeFault) {
+if (args.mode === 'semantic' && !(ctx.search.hasVectors && ctx.search.hasEmbedder) && !ctx.search.storeFault) {
```

with `cause` selecting between the existing 0-vector wording (unchanged) and a new
no-embedder one. The new message, in the voice of its neighbours — what is wrong, then
what to do next:

> `mode:"semantic"` cannot run: it ranks by vector similarity only, and this index holds
> 2 vectors but nothing can embed the query. Embeddings are switched off
> (`ZOTEUS_EMBEDDINGS=off`), so the stored vectors have nothing to be ranked against. Set
> `ZOTEUS_EMBEDDINGS` back to the provider that built them to rank by meaning again.
> Re-run with `mode:"keyword"` (or the default `"auto"`) to search this library right now.

and for a configured-but-down provider:

> … this index holds 2 vectors but nothing can embed the query. The configured `local`
> embedder is not running: `@huggingface/transformers` is not installed … Re-run with
> `mode:"keyword"` …

The tool description gains one clause so the documented promise matches the code
("needs both vectors in the index and a running embedder to turn the query into one:
when either is missing …"). `CHANGELOG.md` gets an `[Unreleased] / Fixed` entry.

`hasEmbedder` is already on the `SearchIndex` interface (`backend.ts:613`) and is
`embedderActive`; nothing new was added to the interface.

## Tests

Three tests in a new describe block in `tests/features/embedder-degradation.test.ts`,
built on a helper that reproduces the real state — build with an embedder, serialize,
reload into an index with `embedder: null` — which is the same fixture shape
`embedding-config.test.ts` already uses.

- **errors instead of answering "No matches" when embeddings are switched off** — asserts
  `hasVectors === true` and `hasEmbedder === false` first, so the test is pinned to the
  state it claims to cover and not to some accidentally-empty index; then
  `isError === true`, the text does *not* start with `No matches`, it names
  `ZOTEUS_EMBEDDINGS` and `mode:"keyword"`, and `structuredContent` reports
  `hits: []`, `embedderConfigured: 'off'`, `embedderActive: false`.
- **names the provider and its cause when one was configured but is not running** — state
  3a: `isError === true` and the text carries `@huggingface/transformers`.
- **still answers in auto and keyword mode** — the control. It passes both before and
  after, and it is what would fail if the fix over-reached into the modes that do not
  need a query vector.

### Seen red

The two behavioural tests were committed on the unfixed tree
(`dcaf67d28bc96f02bec74d7a5c36f8380090a6cc`, source untouched from `4467663`) and run
there:

```
 ❯ tests/features/embedder-degradation.test.ts (20 tests | 2 failed)
   × … errors instead of answering "No matches" when embeddings are switched off
     → expected undefined to be true
   × … names the provider and its cause when one was configured but is not running
     → expected undefined to be true
      Tests  2 failed | 18 passed (20)
```

`expected undefined to be true` is `res.isError` being absent — the tool answering
normally with an empty page, which is exactly the symptom. The third test passed on the
red tree, as a control should.

## Gate

At `04350e2813cd050013812cd3d4b2eded3f3f9333`, clean tree, Node 20+:

| command | result |
|---|---|
| `npm run typecheck` | pass |
| `npm run typecheck:tests` | pass |
| `npm run lint` | pass |
| `npm run build` | pass |
| `npm test` | **1253 passed, 7 skipped (1260) — 124 files passed, 2 skipped** |

Baseline at `4467663` is 1250 passing; the three added tests account for the difference.

`npx prettier --check .` fails on 206 files across the repo, including files this branch
does not touch, so it is not a gate and nothing was reformatted.
