# fix(search): refuse `mode:"semantic"` when no provider can embed the query

Base: `4467663` (main at v1.16.0 + the readme commit).
Branch: `fix/semantic-refuses-without-embedder` — 2 commits, +181 / −12 over 4 files.

## The symptom

Build the index with an embedder, then restart the server with `ZOTEUS_EMBEDDINGS=off`
and run a semantic search. The tool answers:

```
No matches for "deep learning".
```

That is the whole reply. No `isError`, no notice, no cause. It is byte-identical to what
an honest empty result looks like, so the caller — a model, usually — reads it as "this
library holds nothing on the subject" and moves on. It is the #7 failure mode that the
0-vector refusal was written to prevent, arriving through the one door that refusal does
not cover.

The index in this state is not damaged and is not empty: the same query in `auto` or
`keyword` mode returns hits normally.

## Mechanism

Three things line up, and all three are working as designed on their own.

1. **The vectors survive the switch-off.** `SearchIndexBase.reconcileVectorProvenance`
   (`src/features/search/index-manager.ts:688`) drops stored vectors only when the
   *current* embedder identity disagrees with the stored one. With embeddings off there is
   no current identity, so the guard short-circuits and the rows are kept — correctly,
   since they are unusable, not known-wrong. `tests/features/embedding-config.test.ts:389`
   already pins that ("stays silent with no active embedder, which never queries them
   anyway"). So `hasVectors` is **true**.

2. **The refusal only tests the vectors.** `src/tools/semantic-search.ts:102` reads
   `args.mode === 'semantic' && !ctx.search.hasVectors && !ctx.search.storeFault`. With
   vectors present it does not fire, and the handler falls through to `query()`.

3. **`query()` closes both rankers and returns `[]`.** In `SearchIndexBase.query`
   (`index-manager.ts:2363`): the query is embedded only when
   `mode !== 'keyword' && this.opts.embedder && this.counts().vectors`, and with embeddings
   off `opts.embedder` is undefined, so `qv` stays undefined. Then
   `keywordOpen = mode !== 'semantic'` → `false` and `vectorOpen = qv !== undefined` →
   `false`. The loop runs once over two empty candidate lists and returns `[]`.

The summary is then assembled at `semantic-search.ts:133`. It appends `embedderNotice`,
and `build.ts:70` reads `if (s.embedderActive || s.embedderConfigured === 'off') return ''`
— deliberately silent about a provider switched off on purpose, so a keyword-only index by
choice is not lectured on every call (`embedder-degradation.test.ts:123` pins that).
`staleVectorsNotice` and `unembeddedNotice` are empty here too. What is left is the bare
`No matches`.

Each piece is right; the composition is the defect.

## The fix, and why it is keyed on `embedderId`

```diff
-if (args.mode === 'semantic' && !ctx.search.hasVectors && !ctx.search.storeFault) {
+const canEmbedQuery = ctx.search.embedderId !== undefined;
+if (args.mode === 'semantic' && !(ctx.search.hasVectors && canEmbedQuery) && !ctx.search.storeFault) {
```

The obvious flag to reach for is `hasEmbedder`, and it is the wrong one. This is the part
worth reviewing closely.

`hasEmbedder` is `embedderActive` (`index-manager.ts:608`) =
`Boolean(this.opts.embedder) && !this.embedderError` (`:576–578`). `embedderError` is set
by `noteEmbedFailure` on the **first** query-time embed failure (`:722–726`, first edge
wins) and is cleared only in `build()` (`:904`), `buildIncremental()` (`:1012`) and
`updateIncremental()` (`:1578`) — never on a later success. But `query()` does not consult
it; it keys on the provider object (`:2375`). So after a 429 or an `ECONNRESET`, the next
semantic query re-embeds and ranks normally while the flag stays false until an index job
runs.

Refusing on `hasEmbedder` therefore converts one rate-limit blip into a mode that stays
dead until the user rebuilds — measured below — while `auto` goes on embedding the same
query successfully one line later. The tool's own log line for that state calls it
*falling back to keyword-only*, not bricking the mode.

`embedderId` (`backend.ts:604`, "undefined with no provider") is undefined exactly when
there is no provider object — the same thing `query()` keys on. It is therefore precisely
"no query can ever be embedded here", which is the condition a refusal should test.
Measured: `off` → undefined, configured-but-never-started → undefined, provider present
but flagged by a past failure → **defined**, and that index still returns 2 hits.

A post-query variant (`hits.length === 0 && !after.embedderActive`) was considered and
rejected. It reads the sticky flag too, so it misfires in a state I constructed and
measured: after a transient failure, a query that embeds successfully (1 embed call) and
honestly matches nothing — `VectorStore.search` filters `score > 0`, so zero hits with a
live embedder is reachable — comes back `hits: 0, embedderActive: false`, and that route
would refuse with "the embedder is not active" about a query it had just embedded.
`embedderId` has no such case.

The 0-vector wording is unchanged. The new branch says how many vectors are stranded and
either names the provider that built them — `vectorEmbedderId` survives the switch-off —
or names the configured provider and why it is not active:

> `mode:"semantic"` cannot run: it ranks by vector similarity only, and this index holds 2
> vectors but nothing can embed the query. Embeddings are switched off
> (`ZOTEUS_EMBEDDINGS=off`), so the stored vectors have nothing to be ranked against. Set
> `ZOTEUS_EMBEDDINGS` back to the provider that built them
> (`openai:text-embedding-3-small`) to rank by meaning again. Re-run with `mode:"keyword"`
> (or the default `"auto"`) to search this library right now.

`docs/semantic-search.md` (the "0 vectors" bullet), the tool description and `CHANGELOG.md`
are updated to match. No interface change: `embedderId` and `vectorEmbedderId` are already
on `SearchIndex`.

## State matrix

`mode:"semantic"`, index non-empty, no store fault. Every row driven through the handler on
both trees.

| # | vectors | embedder | before | after |
|---|---|---|---|---|
| 1 | present | working | 2 hits | unchanged |
| 2 | present | `ZOTEUS_EMBEDDINGS=off` | `No matches for "…".` — no error, no cause | **error**, names the stranded vectors, `ZOTEUS_EMBEDDINGS`, and the provider that built them |
| 3a | present | configured, never started | `No matches …` + `Semantic ranking is OFF …` — explained, not an error | **error**, names the provider and its cause |
| 3b | present | configured, throws during *this* query | `No matches …` + `Semantic ranking is OFF …` | unchanged |
| 3c | present | **second** query, provider still down | `No matches …` + same notice | unchanged |
| 3d | present | **provider healthy again** (flag still stuck false) | 2 hits, 1 embed call, notice still appended | **unchanged — 2 hits, 1 embed call** |
| 4 | none | configured but down | error, `… 0 vectors …` | unchanged, byte for byte |
| 4b | none | active | error, `… rebuild it …` | unchanged, byte for byte |
| 5 | none | off | error, `… 0 vectors …` | unchanged, byte for byte |

`auto` and `keyword` are untouched in every row; the gate is still `args.mode === 'semantic'`.

Rows 2 and 3a are the change. Row 3d is the one that constrains the design: an earlier
revision of this patch keyed on `hasEmbedder` and turned 3d into `isError: true` with
**zero** embed calls, permanently, until an index job cleared the flag. That revision
passed all 1253 upstream tests — nothing pinned the self-heal path — which is why the guard
below now exists.

State 3a changes as a consequence of the fix rather than as its target, and I think that is
right: it is the same structural impossibility as row 4, which already errors, differing
only in whether the index happens to hold rows the query cannot reach. It also makes the
tool description true, since it already promised an error there. Say the word if you would
rather 3a stayed a notice — it is one clause.

State 3b keeps its notice deliberately. The failure has not happened yet when the gate
runs, and the provider may well be fine on the next call; the notice is the existing
contract for a degraded provider and this patch does not relitigate it.

## Tests

Four tests in a new describe block in `tests/features/embedder-degradation.test.ts`, on a
helper that reproduces the real state — build with an embedder, serialize, reload into an
index with `embedder: null`. The provenance stamp is deliberately **kept** (not
`delete`d), because that is the shape a real index has and it is what lets the message name
the provider.

- **errors instead of answering "No matches" when embeddings are switched off** — asserts
  `hasVectors === true` and `hasEmbedder === false` first, so the test is pinned to the
  state it claims to cover; then `isError`, that the text does not start with `No matches`,
  that it names `ZOTEUS_EMBEDDINGS`, `mode:"keyword"` and
  `openai:text-embedding-3-small`, and the `structuredContent` fields.
- **names the provider and its cause when one was configured but is not running** — row 3a.
- **still answers in auto and keyword mode** — control; green before and after.
- **keeps ranking after a transient embedder failure, without an index rebuild** — rows
  3b/3d. Drives a flaky provider through fail-then-recover and asserts the recovered query
  is not an error, returns hits, and made exactly one embed call (in `mode:"semantic"` the
  keyword ranker is closed, so a hit can only be a vector hit).

### Red evidence

The first two are the red step, committed on the unfixed tree
(`df42626bb6192dbe51fc1a34bd5a3dc95167c45d`, source untouched from `4467663`):

```
   × … errors instead of answering "No matches" when embeddings are switched off
     → expected undefined to be true
   × … names the provider and its cause when one was configured but is not running
     → expected undefined to be true
      Tests  2 failed | 19 passed (21)
```

`expected undefined to be true` is `res.isError` being absent — the tool answering normally
with an empty page, which is the symptom.

The recovery test is **green on the base tree**, by design: it is not a red step but a
guard on the one behaviour a refusal keyed on embedder *health* would break. Its positive
control is the rejected revision, where it fails:

```
   × … keeps ranking after a transient embedder failure, without an index rebuild
     → expected true to be undefined
```

— `isError: true` where the base tree returns hits.

## Gate

At `9f25f0cf4185596aaaa21f4f6fc3c2d66d1eaabe`, clean tree:

| command | result |
|---|---|
| `npm run typecheck` | pass |
| `npm run typecheck:tests` | pass |
| `npm run lint` | pass |
| `npm run build` | pass |
| `npm test` | **1254 passed, 7 skipped (1261) — 124 files passed, 2 skipped** |

Baseline at `4467663` measured directly: **1250 passed, 7 skipped**. The four added tests
are the whole delta.

`npx prettier --check .` fails on 206 files repo-wide including untouched ones, so it is not
a gate and nothing was reformatted.
