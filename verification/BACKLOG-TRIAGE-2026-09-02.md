# Backlog triage — which open tickets are cheap to execute

**Measured 2026-09-02** against `main` at a280fa8, `fork` at `c031478`
(`conductor-integration`) and `b05ed69` (`main`, upstream v1.12.0).

This document is read, not run. It records a judgement about the queue at one
moment, and the queue moves daily: twelve rulings landed the morning it was
written. Every claim below carries the file and line it rests on so a reader can
re-check the one row he cares about instead of trusting the whole. **What
invalidates it:** any ticket closing, any new filing, or `conductor-integration`
merging. Re-derive rather than amend.

## What makes a ticket expensive here, as of this date

Not a pending ruling. Of the eighteen entries in `DECISIONS.md`'s
awaiting-ratification section, fourteen carry a resolution. The four that remain
are the AGPL-reading policy (which gates ticket 0031, itself `deferred`), the
300 MB budget's scope per process or per machine (both figures already stated in
`SPEC.md` §5.2.9), the `zotero_index` action set that the author has declared
negotiated rather than ruled and which travels inside ticket 0033, and two
residual sub-findings of ticket 0180's attribution audit.

What makes a ticket expensive is one of three other things: a measurement run on
the reference machine, the author's real Zotero library, or upstream-filing
authorization (`AGENTS.md:163`, each upstream API action needs his yes).

Recording this because the first pass of this survey got it wrong. Unticked exit
criteria reading "the author ratifies X" look like a pending ruling and are
mostly already answered in the ledger; the checkbox lags the decision. Read the
ledger, not the checkbox.

## Shape of the queue

Seventy-three open tickets against eighty-three closed. Thirty-six carry a
`Blocked-by`, and every one of those blockers resolves to a still-open ticket,
so nothing is waiting on paperwork and the candidate pool is the thirty-seven
unblocked. No open merge requests.

Two gates, and they are not the same one. `make check` covers this repo's
harness and prose: deps, ruff over `bench/ tests/ verification/probes/`, the
figures guard, models, names, README progress arithmetic, `erg check`,
ticket-log timestamps, then pytest. Fork TypeScript is gated by `npx vitest run`
from inside `fork/`, which `make check` never invokes. A ticket touching fork
code is not gated by `make check` at all.

## Cheap, in order

### 1. Ticket 0570 — the choice set's write is not atomic

The only candidate needing nothing from the author: no ruling, no measurement,
no library. One exit criterion.

The fix is named in the ticket. Wrap `putAttachmentChoice`'s row loop in
`this.transaction()` so it is atomic however it is reached. Both symbols verified
present on `fork` `c031478`: `Ledger.transaction()` at
`src/features/search/conductor/ledger.ts:483` doing `BEGIN IMMEDIATE`, and
`putAttachmentChoice` at `ledger.ts:1245` looping `stmt.run()` bare.
`extract-stage.ts` carries the asymmetry: `complete()` reaches `decide()` inside
a transaction, `isChosen()` does not.

The design point is named too, and it is how the fix breaks. `BEGIN IMMEDIATE`
inside an open transaction throws on SQLite, and `complete()` already holds one,
so this needs a savepoint or an open-transaction check. Red-first test and
positive control are both specified in the ticket, and
`tests/features/conductor-ledger.test.ts` exists on that branch to extend.

### 2. Ticket 0100 — two bench drivers pinned to the pre-rename schema

Also needs nothing from the author, and the root cause is diagnosed to the line.
`bench/index_concentration.mjs:138` still calls `fts5vocab(passages, row)` and
`bench/bm25_idf_effect.mjs:4` hardcodes a stale index path. The pinned fixture at
`~/data/projets/zoteus-bench/x2-rebuild/search-index.sqlite` is on disk at 939 MB
and carries the post-rename schema: `items, passages, passages_fts,
passages_fts_config, passages_fts_data, passages_fts_docsize, passages_fts_idx,
meta`. `passages` is a plain table now and `passages_fts` the virtual one, which
is the break.

Behind 0570 on two counts. Both drivers must run against that 939 MB index, and
the ticket asks whether 0013's figures moved, which is a judgement on which of
two runs is right and touches the figures guard.

**Local only.** The fixture is not in any repository.

### 3. Ticket 0483 — which extraction cap binds where

Most of the work is already run. `verification/probes/api-vs-cache-probe.py`
records the `pdfMaxPages` half as settled on 2026-08-30 over three probes, with
byte-identical API and cache content. What is left is the `textMaxLength` half,
which the ticket's own log calls suggestive rather than settled, and the
write-up: a grep for `pdfMaxPages`, `textMaxLength` and `truncated-body` across
`SPEC.md` and `DECISIONS.md` returns nothing, so no ruling has been written.

Small, but it needs one targeted probe against the real library, on a long
document near the character cap rather than one already page-capped.

**Local only.** Needs the live Zotero library.

### 4. Ticket 0530 — upstream typecheck never covers the test suite

Mechanical work that cannot close without the author. The premise reproduces on
both the fork branch and `upstream/main`: `tsconfig.json` carries
`"exclude": ["node_modules", "dist", "tests"]` while `package.json`'s `typecheck`
is `tsc --noEmit`. So 102 test files and 15 907 lines have never been
type-checked.

The autonomous half is a positive control in both directions and a blast-radius
measurement. That radius is the open variable, and the ticket says it decides
whether the outcome is a one-line `exclude` fix or a design-sized issue. Exit is
either an upstream filing or an explicit deliberately-unfiled line under
`GOVERNANCE.md` § The courtesy filing.

## Priced and set aside

| Ticket | Verdict | Why |
|---|---|---|
| 0541 query_arms fallback columns | small to medium | The bug is real: `bench/query_arms.mjs:62-71` still reads the removed `MIN_MATCH_TERMS` and `isStopword` exports. But `~/data/projets/zoteus-bench/query_arms_r5.mjs`, the runner it was to be ported from, does not exist, so this is reconstruction against two divergent `pruneTerms` signatures across open upstream PRs #46 and #47 |
| 0490 embedder fields authoritative | medium | 0489's closeout left a live disagreement, a declared 256-token window against actual 512-token truncation, that 0490 must settle; its base branch `t0489-minilm-singleton-entry` is merged nowhere |
| 0503 upstream discovery bound | medium to large | The read-at-source half is already answered on `conductor-integration` (`DEFAULT_TICK_CADENCE_MS = 60_000`); what remains is live latency timing |
| 0500 extract and chunk throughput | medium | Nothing measured yet; needs a new timing driver, the 0029 fixture corpus, and a reference-machine run |
| 0592 version-0 reverify sweep | medium to large | A new mechanism: idle scheduler, persistent cursor, fairness across restarts, horizon reporting |
| 0590 scoped queries failing to fill k | medium | Needs a disclosed sample of the author's real collection and tag scopes, and ends in his judgement |
| 0593 attachment format coverage | large | Nine live-Zotero fixtures, a ruling gate, then new code and acceptance tests |
| 0488 embedder registry | tracker | Nothing to execute; one of six children closed |
| 0591 index schema normalization | deferred | Its exit criterion is the author reopening the discussion |
| 0480, 0485, 0496, 0577, 0579, 0441 | measurement | Each exit criterion turns on a reference-machine run or the real library |

## What can leave this machine

Only 0570 and 0530 are pure fork TypeScript and can run in a cloud session with
the fork attached. 0100 needs the 939 MB fixture and 0483 needs the live Zotero
library, so both are local work.

Dispatched to cloud sessions on 2026-09-02: ticket 0570 in full, and ticket
0530's measurement half with the filing explicitly withheld pending the author's
authorization.
