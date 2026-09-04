# Upstream PR draft — durable embed-stage work counter (ticket 0642, tracker 0613 gap C)

**Staged, not sent.** No per-action authorization has been given for this filing. Branch
`work-counters-0642` on the author's own fork (`MinhHaDuong/zoteus`), pushed 2026-09-04, one
commit atop `upstream/main` at `7de4a2f` (`fix(deploy): keep /metrics off the public internet,
and cap container logs` — 7 commits ahead of this repo's `UPSTREAM_REVIEWED_SHA`,
`b0e0bc872b5727d21ea83aba8bfe834293013264` / v1.13.0, re-verified fresh against the live tip
rather than the stale reviewed baseline per this ticket's own Action 1). **Not** pushed to
`oscardvs/zoteus`, and no `gh pr create` was run against it. Everything from `## Title` down is
what would go out verbatim; this preamble would not.

Real diff, `git diff --stat upstream/main` from the branch tip:

```
 src/features/search/backend.ts                 |  22 ++
 src/features/search/index-manager.ts           |  14 ++
 src/features/search/sqlite-index.ts            | 124 +++++++++-
 tests/features/search-schema-migration.test.ts |  56 ++---
 tests/features/search-schema-version.test.ts   |   8 +-
 tests/features/work-counters.test.ts           | 319 +++++++++++++++++++++++++
 6 files changed, 508 insertions(+), 35 deletions(-)
```

Source-only (the three `src/` files) is **160 lines** (157 added, 3 removed). Ticket 0033's
2026-09-04T06:53Z log entry, grounded against this same live tip, estimated Tier 1 (in-memory,
`metrics.ts`-based) at 40–120 LOC and explicitly flagged that a Tier-1 landing would not satisfy
this ticket's own durability requirement. Ticket 0642's own Action 4 carried that forward as
"~40-150 LOC once done durably rather than in-memory" — the real, durable source diff (160
lines) lands a hair above that upper bound, not the order-of-magnitude jump Tier 2's full
four-stage/eight-trigger design would have needed (800–1500 LOC, same log entry). The other 348
lines are test-fixture maintenance (64 lines: the existing schema-migration and schema-version
suites hardcode version literals relative to the previous `SCHEMA_VERSION`, and bumping it to 3
requires bumping those by one — no behavioral change to what they assert) and a new dedicated
test file (319 lines) covering the positive control, the migration path, the salvage/noop case,
cross-connection durability, and forced-rollback atomicity.

**Form.** Contained PR, not a design-sized issue: a schema-additive change following an
existing, precedented mechanism (`#34`'s migration ladder) at a single, well-bounded transaction
boundary (`flush()`), gated with tests in the project's own convention, all four local gates
green. `GOVERNANCE.md`'s asymmetry rule reads this as the "contained defect/feature with tests,
merges verbatim" lane (precedents: `#27`, `#28`, and this branch's own base commits `#34`, `#43`,
`#48`), not the "design-sized issue the maintainer builds himself" lane Tier 2's full counter
design would need — this PR is deliberately NOT that: see "What this does not do" below.

**Why not build on `src/lib/usage/store.ts` (added in `c2d83da`, immediately ahead of this
branch's base).** That module is a real, durable, sqlite-backed counter/event store, and it
looks like a candidate at first glance — worth naming explicitly so a reviewer does not have to
ask "didn't we just build this?" and getting a precise answer up front. It is the wrong axis for
this need on four independent grounds: its `UsageEvent.kind` is a closed union
(`'tool' | 'http' | 'auth'`, `src/lib/usage/event.ts`) recording call-level operator-facing
usage analytics (tool name, outcome, duration, caller identity), not per-item indexing
progress; it is off by default, opt-in via `ZOTEUS_USAGE_LOG`; it writes to a **separate** file
(`<data dir>/usage.sqlite`), which cannot share one transaction with the search index's own
vector writes — the entire durability property this PR exists to provide; and it prunes raw
events after `ZOTEUS_USAGE_RETENTION_DAYS` (30 days by default), a rolling log rather than a
cumulative ledger, which a work counter must never do. What IS reused from it: the same
`node:sqlite`/`DatabaseSync`-via-`createRequire` binding, the same busy-timeout-before-any-lock
ordering, and (where an error path is touched) the same `isCorruptionError`/corruption-sidelining
discipline `store-faults.ts` already centralizes — `usage/store.ts`'s own header says it is
"modelled on the search index's store... because that one has already been through the failure
modes," and this PR follows `sqlite-index.ts`'s conventions directly rather than inventing a
third variant.

**What this does not do**, named so a reviewer sees the boundary rather than has to infer it
from absence. It does not implement SPEC's full `work.<stage>.<trigger>.<outcome>` cross product
(four stages × eight triggers × two outcomes) — only the embed stage's `done` outcome, under one
coarse, honestly-named trigger (`"build"`), because nothing downstream reads a finer
classification yet and a fabricated one would be worse than an honest coarse one. It does not add
drift detection, idle reconciliation, or the `noop` outcome for a no-op resync (the counter simply
never bumps in that case — see the salvage test below — rather than recording an explicit zero).
It does not touch `record`/`extract`/`chunk` stage counters, which need a per-item key comparison
this pipeline does not build yet. All of that stays scoped to a possible follow-up PR
(tracked, unstarted, in the requesting repo's own ticket 0033) — this PR is deliberately the
smallest real slice that answers one question durably: did embedding work actually happen, and
does the answer survive a restart.

---

## Title

feat(search): durable, per-transaction embed-stage work counter

## Body

### The problem

`action:"status"` can say a build is `"done"`, but nothing durable records **that vectors were
actually recomputed** — as opposed to a pause simply having stopped noticing new work, or a
process having restarted with no memory of what it did before. `src/lib/metrics.ts`'s
`createMetrics()` registry (added in `c2d83da`) is the closest existing thing, and it is
in-memory only: it resets on every restart, which means it can only ever demonstrate "a
background-work control stops work" by accident of timing — it cannot demonstrate "that stop
holds across a restart" with any rigor, since a counter that reset to 0 and stayed 0 looks
identical to one that was never wired at all.

### What this changes

A new `work_counters(stage, trigger_kind, outcome, count)` table in the SQLite search index's
own database — the same file, same connection `sqlite-index.ts` already manages, added through
the existing schema-migration ladder (`#34`'s `SCHEMA_VERSION`/`SCHEMA_MIGRATIONS` mechanism;
this bumps it 2 → 3). `trigger_kind` rather than `trigger`, to avoid the reserved-word-adjacent
name for no benefit.

One transactional bump helper (`bumpWorkCounter`, an `INSERT ... ON CONFLICT DO UPDATE SET
count = count + excluded.count`), called from *inside* the same transaction `flush()` already
opens for `writeMeta()` and the checkpoint — never as a write of its own. `putVector()` tallies
how many vectors it newly wrote since the last flush (`embedDoneSinceFlush`); `flush()` folds
that tally into `work.embed.build.done` immediately before the one `commit()` that already makes
the vectors and the checkpoint durable. A vector reused from vector salvage (`adoptVector`, also
`#34`) deliberately does **not** bump the counter — reuse is `noop`, not `done`, by the
vocabulary SPEC's own comment names, and crediting a reused vector as newly "done" work would be
exactly the fabrication this counter exists to avoid.

Exposed via `zotero_index action:"status"` as a new `work` field
(`{ embed: { build: { done: N } } }`), read fresh from the table on every status call — never
cached in memory — documented in the tool's description string beside every other status field.

### Why this is safe on an existing index

The migration rung (`to: 3`) only creates the table; it does not attempt to backfill a count for
work an older database did before this existed, because there is no honest number to write —
guessing one would be exactly the fabricated-history failure mode this design otherwise avoids.
An upgraded database's counter starts at 0 and grows only from what it embeds from here on.

### Test

`tests/features/work-counters.test.ts`, red-first and in this project's own Vitest convention
(shaped after `search-schema-migration.test.ts` and `embedding-backoff.test.ts`):

- **the table exists** — created directly on a fresh database, and via the migration ladder on
  an aged schema-2 one, crediting no fabricated history;
- **the positive control** — a build that embeds N passages advances `work.embed.build.done` by
  exactly N (the counter is shown capable of moving before anything trusts that it did not);
- **the coarse trigger is honest** — exactly one stage, one trigger, one outcome, nothing wider;
- **the salvage/noop case** — a vector reused from a sidelined index (not recomputed) does NOT
  bump the counter; only the passage actually re-embedded does;
- **durability across a fresh connection** — closing the process and opening a brand-new
  `SqliteSearchIndex` against the same file reads back exactly what a prior one committed, both
  through the object model and through a raw read of the table;
- **atomicity** — forcing the one shared `commit()` to fail (the in-process analogue of a crash
  between the write and the fsync) leaves NEITHER the vector NOR the counter durable: a second,
  independent connection sees neither while the transaction is open (SQLite's own isolation), and
  neither survives an explicit rollback and a fresh reconnect. `commit()` is the only place either
  write becomes durable, so breaking it is a genuine kill switch on the one shared commit, not a
  coincidence of two independent ones happening to break together.

Full suite: 1097 passed, 0 failed, 7 skipped (pre-existing — environments without `node:sqlite`).
`npm run lint`, `npm run build`, `npm run typecheck:tests` all clean.

### A live end-to-end check, beyond the unit suite

Run against a real, resident Zotero library (7 546 items, `limit:1` build) with the on-device
embedder: `action:"status"` reported `"work": {"embed": {"build": {"done": 1}}}` after the
build, and a **completely separate** process reopening the same file read back
`work_counters = [('embed', 'build', 'done', 1)]` from a fresh connection with no server
involved at all.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
