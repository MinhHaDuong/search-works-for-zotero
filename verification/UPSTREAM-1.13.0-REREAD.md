# The twenty-three rows read at upstream v1.13.0

*Evidence, not authority. Read 2026-09-03 for ticket 0618, the third
re-baseline. Where anything here touches the design, the owning document in
`AGENTS.md`'s document set is the record.*

**Subject:** upstream `oscardvs/zoteus` at
`b0e0bc872b5727d21ea83aba8bfe834293013264`, which is `main`'s tip. The tag
`v1.13.0` is `8f16efeb61ecee87a785fd560c39be165d266af6`, three commits earlier;
the three commits between them are the #43 weight-precision work, which
upstream's own changelog files under `[Unreleased]`, plus a registry
description fix. Every `file:line` below addresses the tip.

**Why the tip and not the tag.** `make upstream-status` compares the reviewed
SHA against `main`. Pinning the tag would leave that target red on the day it
was written, and a status target that is permanently red is a status target
nobody reads. `UPSTREAM_REVIEWED_VERSION` therefore names the last release
*contained in* the reviewed tree — which is what the standing page dates itself
by — and the three-commit gap is disclosed rather than encoded, because
`check_progress.PAGE_VERSION` parses `vN.N.N` and a `v1.13.0+3` would fail to
match itself.

**Substrate, in two parts.** The source read was done against the bare mirror
`upstream.git/` that `make upstream-catchup` maintains, at both revisions, so
nothing depended on a working tree. The runs were done against a fresh checkout
at `fork/`, built with `npm ci && npm run build`, whose server reports version
1.13.0.

**Method.** Source read for every row, plus two instruments that ran: the smoke
(`bench/smoke_upstream.py` → `bench/results/smoke-1.13.0/checks.json`) and the
acceptance layer. What each row's `evidence` column claims is what was actually
done for it, never what was done for it last time.

**What this document is not.** It is not the standing page. A row's verdict
lives in `README.md`; this is the reading the verdict was written from.

---

## The delta

`b05ed69..b0e0bc8` — 34 commits, 10 merges, 67 files, +4912/−524. Under the
watched surface `src/features/search/`: 15 files, +1830/−198, with
`query-terms.ts` new.

Ten merges, naming #37, #43 (twice), #44, #45, #46, #47, #48 and #49. Three of
those are this repository's own pull requests, and they merged as a stack.

**The index schema stamp moved for the first time since v1.7.0.** That is the
single most consequential fact in this delta for us, and the catch-up caught it
mechanically: `SCHEMA_VERSION` 1 → 2.

---

## What upstream did, in the order it matters to us

### The schema, and why it moved

`passages` is **byte-identical** across the bump — same columns, same
constraints, same two indexes. So is `items`, `meta` and `vector_codes`. Two
things changed:

- `passages_fts` is declared with the diacritic-stripping tokenizer turned
  **off** rather than on, so the index now stores each word as written;
- a new table `accent_variants(folded, term, df) WITHOUT ROWID` carries the map
  from a folded spelling to the accented spellings the index actually holds.

And `SCHEMA_MIGRATIONS`, empty since it was introduced, has its first rung:

```ts
{
  to: 2,
  what: 'keeps diacritics in the keyword index, answering unaccented queries by expansion',
  up(db) { /* DROP + recreate passages_fts, re-insert paged by pid, deriveAccentVariants */ },
}
```

It runs inside the transaction that stamps the new version, so a throw leaves
the file exactly as it was at its old stamp. It rebuilds the keyword index from
`passages.text` and **re-computes no vector**. `migrationPath` still refuses to
walk backwards, so a *newer*-stamped file is still sidelined.

`passages_fts` no longer holds `passages.text` verbatim: upstream inserts
`normalizeForSearch(text)`, and the three delete sites re-derive the same string
because FTS5's external-content delete protocol needs a byte match.

**This rung exists because of our pull request #46.** The tokenizer change is
ours; the ladder that carries it is his.

### Issue #48 — the embed-phase resume, built to the contract we posted

- `sqlite-index.ts` prepares
  `SELECT id, item_key, title, text, source FROM passages WHERE vector IS NULL ORDER BY pid LIMIT ?`,
  consumed by a new `passagesMissingVectors(limit)`.
- `index-manager.ts` keeps the checkpoint when the embedder failed rather than
  clearing it, and **withholds the library version stamp** so a later
  `action:"update"` cannot run a `?since=V` delta over a half-embedded index.
- `backfillVectors()` pages 500 at a time, runs **only on a resume**, and
  breaks if a round fails to reduce the shortfall.
- Retry policy in `embeddings.ts`: five attempts by default, exponential from
  one second, per-wait ceiling and total-wait ceiling, `Retry-After` honoured in
  both header forms and *replacing* the exponential term, jitter added. Retried
  on 429, 408, 5xx and network errors; deliberately **not** on 400, 401, 403.
- Status gained `passagesWithoutVectors` and an `embedRate` object whose
  `tokensPerMinute` is measured — for API providers only.

**One correction to what this repository believed going in.** The claim that
`StartBuildOptions.fresh` "is deliberately not set by `action:"build"`" is true
of the *index* layer and false of the *tool* layer: `index-tool.ts` sets
`fresh: args.action === 'refresh'`, an explicit `false` for a build, and
`build.ts` then spreads the key only when truthy, so it genuinely arrives unset
at `buildIncremental`. The effect is what the claim intends; the wording named
the wrong type.

### The rest

- **#37** deletes the Electron full-text refusal outright, along with
  `ZOTEUS_ALLOW_ELECTRON_FULLTEXT`, and caps the local embedder's batch under
  Electron instead. The diagnosis is worth keeping: SIGTRAP from Chromium's
  allocator on one attention tensor, which is why there was no stack.
- **#43** makes `ZOTEUS_EMBEDDING_MODEL` name the **local** model, adds input
  prefixes derived from the model id for instruction-tuned families (kept out
  of the embedder identity on purpose), and adds a weight-precision selector
  over twelve dtypes that **does** enter the identity — above full precision
  only, so no existing local index is invalidated.
- **#44** scopes vector salvage to the library that wrote the sidelined file.
  That is this repository's own courtesy filing, built by the maintainer.
- **#49** type-checks the test suite as a blocking CI step. Ours.
- **#45, #46, #47** are the 0091 stopword series, merged whole.

### What did NOT change, checked rather than assumed

- The per-item full-text cap and the item cap. `fulltext-source.ts` is untouched
  by the release.
- The startup release check, still enabled by default, still contacting GitHub
  once a day per data directory.
- The MCP tool surface: `zotero_index`'s action list is unchanged, so there is
  still no pause.
- The update path's single entry point and single call site, and the absence of
  any timer that would start it.
- `src/lib/metrics.ts`, and with it the absence of any per-stage, per-trigger,
  per-outcome work counter.

---

## The rows

Twenty-three, in the page's own order. "Moved" means the row's text changed;
"verdict moved" means the `delivered` or `evidence` column changed.

### Coverage and convergence

**R1 — moved, verdict unchanged (`partial`/`code`).** The resume clause is now
true in a stronger sense than the row stated: #48 completed the embed phase of
it. The two clauses that did not hold — the crawl paging rather than
prioritising, and an attachment yielding no text not recorded as
done-with-a-reason — were re-read and neither moved. The
convergence-to-latest-chain clause no longer postdates the baseline; it is
unassessed for want of the harness.

**R4 — moved, verdict unchanged.** `passagesWithoutVectors` and the unembedded
notice are one honest coverage signal, and they are not coverage per stage.

**R17 — moved, verdict unchanged.** Both clauses re-read, neither holds. The
new status fields are per-job state on one build, not a work counter; the metric
registry is untouched and carries a handful of names, none per stage.

**R32 — moved, verdict unchanged (`partial`/`measured`).** The evidence is our
own GPU and CPU measurements, which no upstream release touches. Upstream now
surfaces a measured embed rate, for API providers only, so the rate this row is
about is still unreported for the local default path.

### Change and cost

**R3 — see the acceptance section below.**

**R35 — moved, verdict unchanged.** Re-read at the tip: `buildIncremental` still
has exactly one call site, and the only timer anywhere in the search feature is
the delay between embedding batches.

### Corpus

**R8 — moved, verdict unchanged.** The caps were re-read in a file the release
does not touch.

**R16 — moved, verdict unchanged (`shipped`/`code`).** Re-read; the release does
not touch own-words.

### Query

**R5 — unchanged.** Nothing in the release bears on it.

**R6 — moved, verdict unchanged.** The query side gained work it did not have:
a droplist prune on every query, and an expansion of an unaccented term into the
accented spellings the index holds. Neither costs anything this repository has
measured, so what the row calls "true and unwatched" is now a larger unwatched
thing.

**R18 — moved, verdict unchanged (`none`).** #45 removed one *cause* of an
unexplained empty answer without supplying the distinction R18 asks for.

**R24 — moved, verdict unchanged.** Snippet cutting was rewritten; the locator
was not touched.

**R33 — moved, verdict unchanged.** The row's observation that "the keyword side
stayed put" is dated: three of our own merged pull requests moved it.

**R34 — unchanged.** No pinned set exists upstream and nothing asserts one.

### Multilingual

**R7 — moved substantially, verdict unchanged (`partial`/`measured`).** Two
clauses were **wrong**, not dated, and this is one of the three findings that
fired trigger (c). Upstream no longer hardcodes the English-tuned MiniLM
construction — it defaults to it, and `ZOTEUS_EMBEDDING_MODEL` now selects the
local model. And the English stopword list is gone, replaced by the
library-derived droplist this repository measured and filed. The MUST tier still
fails at English alone on the default path, which is why the verdict does not
move.

**R29 — moved, verdict unchanged (`none`/`measured`).** Same fact from the other
side: the default path still has no cross-lingual channel, but the absence is a
default's rather than the construction's. This row's citation of a v1.10.0 smoke
session — two baselines stale, and carried through the last bump unrepaired — is
replaced by a source read at the current baseline; the `measured` half rests on
ticket 0266's cross-lingual artifact, which no upstream release touches.

### Custody and lifecycle

**R10, R15, R22, R23 — see the runs below.** R22 was re-read in source: the
index tool's action list is unchanged and there is still no pause, so "verified
absent" stands. An inventory pass over this repository read ticket 0613 as
recording a pause switch that exists and is offered; that reading is wrong —
0613 says "none of them is a durable pause, so gaps B and C stand as written",
and 0033 records both R22 clauses as `not-offered` against a verb-less stub
precisely because the pause is absent.

### Multi-library and multi-process

**R12 — moved, verdict unchanged (`shipped`/`measured`).** The one seam this row
reported as beyond the guard's reach is now inside it: #44 scopes vector salvage
to the library that wrote the sidelined file. Our courtesy filing, his build.

**R13 — see the acceptance section below.**

### Normalization

**R19 — moved, verdict unchanged (`none`/`inferred`).** The substrate under the
fold gate changed: the index keeps diacritics instead of folding them, and the
unaccented spelling is reached query-side by expansion, in one direction only.
An accented query never expands, and an unaccented one expands only where the
accented spellings' summed document frequency exceeds the typed spelling's own —
upstream's own worked counter-example is a Vietnamese function word that does
not expand. So `bench/results/0578-fold-sweep/codepoints.json` measures a
tokenizer upstream no longer ships. It stays as a dated record; nothing may cite
it as a fact about current upstream until the sweep is re-run. Ticket 0619.

---

## The runs

Both instruments ran against a checkout built at the pinned SHA, whose server
reports version 1.13.0. Artifacts under `bench/results/smoke-1.13.0/`.

### The smoke — five checks, five passes, nothing observed

`R10-local-embedder`, `R6-query-answers`, `R15-model-in-data-dir`,
`R23-previous-schema-migrates-in-place`, `R23-foreign-schema-sidelined`.

Three things about that line are worth more than the count.

**The migration ladder was driven in anger, which no previous run could do.** A
real library-sized index stamped at the previous generation was opened by a build
at the current one, at its own path, and the server logged the in-place upgrade
by name. Nothing was moved aside, the passage and vector counts are identical
before and after, and the probe query answered.
`verification/UPSTREAM-1.12.0-REREAD.md` recorded the ladder as "real, tested,
and untested in anger — the same shape as a guard with no positive control".
That is no longer true, and the check that says so was renamed to what it now
asserts: `R23-no-migration-path` became
`R23-previous-schema-migrates-in-place`.

**Two checks were repaired before the run, and neither repair was cosmetic.**
`check_migration_absent` carried a hardcoded consequence string asserting the
ladder was empty; it wrote that string into the artifact, and it would have
written it into a run where the ladder had just fired. Ticket 0506 repaired the
same class of defect in the same script at the previous bump, which is the
precedent for repairing it here rather than filing it. And
`check_model_stays_in_data_dir` ran *before* anything embedded, so on a fresh
data directory it looked for a cache before the download that creates it — an
all-clear indistinguishable from "I could not look". Moved after the query
check, it now records that the directory held no cache at server start and held
one after the queries: a positive control rather than a coincidence.

**`R6-query-answers` flipped from fail to pass, and that is an index artifact
rather than an upstream improvement.** The previous run used a one-item build.
Nothing in the release bears on it.

**`R23-foreign-schema-sidelined` now exercises both foreign directions and says
which is which.** A stamp below the build's with no contiguous ladder up to it,
and a stamp above it, since the ladder is forwards-only. Both are moved aside
byte-identical and answered from a fresh empty index; the ordinary
one-version-behind case is the other check's.

### The acceptance layer — the first run where every fail-control fired

`assertions_never_seen_red` is **empty**. Every assertion in the layer,
including the two R22 clauses that had no row in the previous artifact, was
driven red by a fail-control of its own. The previous baseline's artifact could
not say that, and `README.md` disclosed as much; the disclosure is discharged.

Against the real target: four pass, one fail, one not-offered, six not-run.

- **`R10-no-egress` is red again**, and what it reads has changed. The run
  records name-lookup attempts, all of them to this machine's own stub resolver,
  and **zero attempts off the machine**. Its own captured output shows the
  permitted one-time model-weight download failing on a blocked fetch under the
  network-isolated arm, so at least part of that count is the download `SPEC.md`
  §6 allows. How much is **not established**, and the clause grades any lookup
  rather than any departure. The startup release check that raised the original
  question is unchanged at this baseline and still on by default, so the
  question in `DECISIONS.md` stands; what has changed is that this run cannot be
  cited as evidence about *that* endpoint specifically.
- **`R15-residue-inventory` and `R15-model-cache-under-declared-roots` pass**
  against a real target for the first time. Every location the target created is
  accounted for by its declaration, and nothing sits outside it. This is what
  moves R15's evidence column from `inferred` to `measured`.
- **`R15-uninstall-removes-declared-state` is not-offered.** The adapter declares
  no uninstall surface, and `purge` is maintenance rather than a substitute the
  harness may call to manufacture a clean result.
- **`R13-two-processes-both-answer` passes**; the third-process detector returns
  identical hits after both are gone.
- **Both R3 clauses and `R13-two-processes-do-not-duplicate-work` are not-run**,
  for the reason this repository has now re-earned rather than re-asserted: the
  target reports no per-stage, per-trigger, per-outcome work counter.
- **Both R22 clauses are not-run**, because the positive control and the graded
  target could not be shown to resolve separate state on this host.
- **`R23-foreign-stamp-ends-up-serving` is not-run rather than red.** Its
  newer-stamp arm could not be armed: with the index put back into the state the
  clause is about, it served nothing, so an empty answer afterwards would have
  been a fact about the arm and not about the direction. Reported as not decided
  on purpose — a clause that cannot be armed and a clause that fails are not the
  same finding, and the previous baseline reported this one as red.

### One defect in the instrument, found by running it and not fixed here

The acceptance layer's not-run reasons cite **"SPEC.md §5.2.8, Counters (C4)"**
in three live strings — `bench/acceptance/durability.py` twice and
`bench/acceptance/assertions.py` once. **C4 was dissolved into R17 on
2026-09-03** (`DECISIONS.md`), and `SPEC.md` already records the retirement, so
a reader following that pointer lands nowhere. It is a rename sweep from that
morning's ruling that did not reach `bench/acceptance/`, it is three strings
wide, and it is deliberately left alone here: the artifacts committed with this
re-baseline record what the instrument said on the day, and editing the code
without re-running would put the committed record and the code in contradiction
to hide a one-line miss belonging to another change. Reported rather than
ticketed, per the severity floor.

---

## Corrections this read makes to earlier readings

1. **`StartBuildOptions.fresh`** — see above; the mechanism is as believed, the
   type named was not.
2. **R22 and the pause** — an inventory pass read two tickets as contradicting
   the row. They do not.
3. **The page's hand-maintained counts** — "twenty-four", and "nine" read in the
   source. R31 retired on 2026-09-03 and took the sheet to twenty-three and the
   `code` tally to eight. Guard-exempt by ruling, wrong since that morning,
   corrected here.
4. **The smoke instrument paragraph** — it described the instrument by pointing
   at a run two baselines old while `UPSTREAM` named v1.12.0, and `make check`
   was green. That is ticket 0622's second item, and this is its instance.
