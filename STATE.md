# STATE — Search Works for Zotero

*Reconciled 2026-08-31 and held under forty lines by ruling of the same day.
Last updated 2026-09-02: PR #187 ratified the target-neutral acceptance harness;
PR #192 propagated it and filed adapter tickets 0583–0586.*

One page of live operational handoff, and it owns nothing: every line is a
pointer to the document that does own the fact, and anything longer than a
pointer has drifted.

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
| How agents work here | [`AGENTS.md`](AGENTS.md) |

## What this repo is

Public design record, ticket store, and measurement harness for an
implementation-neutral work programme. The reference code lives in a fork of
someone else's project: `fork/` is git-ignored here and recreated by
`make upstream-checkout`. A `tickets/` directory must never appear in it, or it
would show up in a diff sent upstream.

## Handoff

**Next:** 0578 builds the assertion layer, zoteus adapter and R10 fail-control;
0583–0586 own the other adapters. `erg ready` owns the rest of the queue.
**Awaiting the author:** `DECISIONS.md`; ticket 0582 records its README call.
Tracker 0550 owns the stale two-process topology in `SPEC.md` §4 and §5.1.
The PR-2 diacritics record is ticket 0091's log; the previously named
`t0091-pr2-expansion` branch never reached origin.
