# STATE — Search Works for Zotero

*Reconciled 2026-08-31, and held under forty lines by ruling of the same day.
Last updated 2026-09-02 (PRs #178–186 and #188 merged: field review, 0028
segmenter interface, conductor-lane reconciliation — 0554 rescoped, 0575–0577
filed — seg/1 and the embed-cap guard built on the fork leaving 0028 open
only for X5, 0026 split into 0578–0582 as a tracker, 0180's attribution audit
closed (`verification/ATTRIBUTION-AUDIT-0180.md`), 0489 closed on the fork
branch `t0489-minilm-singleton-entry`, ticket citations repointed to
`SPEC.md`; PR #187 — the target-neutral acceptance-harness ruling, gate
APPROVED — held open for the author's ratification).*

One page of live state, and it owns nothing: every line is a pointer to the
document that does own the fact, and anything longer than a pointer has drifted.

**The measurement record that used to fill this file is gone**; git log is the
archive. A measurement's durable home is its artifact under `bench/results/`
and the ticket that produced it — prose quoting one is never the record.

## Where the live state lives

| | |
|---|---|
| Upstream: what is filed, merged, in flight | [`SYNC.md`](SYNC.md) |
| The reviewed baseline SHA, machine-readable | `UPSTREAM`; `make upstream-status` detects movement, `make upstream-catchup` reads it |
| The work queue and every item's state | `./tickets/erg ready` |
| The spec: promises, constraints, design, every design number | [`SPEC.md`](SPEC.md) |
| Rulings, and what awaits one | [`DECISIONS.md`](DECISIONS.md) |
| Where each requirement stands | [`README.md`](README.md) |
| What we will and will not send upstream | [`GOVERNANCE.md`](GOVERNANCE.md) |
| How to work here | [`CLAUDE.md`](CLAUDE.md) |

## What this repo is

Public design record, ticket store, and measurement harness for an
implementation-neutral work programme. The reference code lives in a fork of
someone else's project: `fork/` is git-ignored here and recreated by
`make upstream-checkout`. A `tickets/` directory must never appear in it, or it
would show up in a diff sent upstream.

## Handoff

**PR #187** drafts the target-neutral acceptance-harness ruling under
`DECISIONS.md`'s awaiting list and rescopes 0578 onto it; gate APPROVED, left
unmerged pending the author's ratification — at merge, resolve
`DECISIONS.md`'s tail as a union with `origin/main`. **Ready now**: 0578
(goal-1 gates — the assertion layer and the zoteus adapter first), 0490 and
0575 (unblocked by 0489's close), 0565 (unblocked by seg/1), 0554 (rescoped,
branches from the fork's conductor-integration). **Awaiting the author**: PR
#187's ruling; `DECISIONS.md`'s awaiting-ratification list, where the
`zotero_index` action set and 0569's retry policy gate the conductor lane;
two README calls recorded in ticket logs — 0578's R15 goal-1-cell address,
0582's absent `Blocked-by`. `SPEC.md` §4 and §5.1 still count the topology at
two processes; open exit criterion on tracker 0550. **The PR-2 diacritics
campaign's record is ticket 0091's log** (0091 is closed) — the branch named
in a prior note, `t0091-pr2-expansion`, is not on origin.
