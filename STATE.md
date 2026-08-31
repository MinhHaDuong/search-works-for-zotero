# STATE — Search Works for Zotero

*Reconciled 2026-08-31, and held under forty lines by ruling of the same day.*

One page of live state, and it owns nothing: every line is a pointer to the
document that does own the fact, and anything longer than a pointer has drifted.

**The measurement record that used to fill this file is gone.** It described a
tree three upstream versions stale and said so itself. Git log is the archive —
this repo deletes rather than archives in the tree. A measurement's durable
home is its artifact under `bench/results/` and the ticket that produced it;
prose quoting one is a convenience, never the record.

## Where the live state lives

| | |
|---|---|
| Upstream: what is filed, merged, in flight | [`SYNC.md`](SYNC.md) |
| The reviewed baseline SHA, machine-readable | `UPSTREAM`; `make upstream-status` detects movement |
| The work queue and every item's state | `./tickets/erg ready` |
| The design, and every design number | [`spec/DESIGN.md`](spec/DESIGN.md) |
| Rulings, and what awaits one | [`spec/DECISIONS.md`](spec/DECISIONS.md) |
| Where each requirement stands | [`spec/README.md`](spec/README.md) |
| What we will and will not send upstream | [`GOVERNANCE.md`](GOVERNANCE.md) |
| How to work here | [`CLAUDE.md`](CLAUDE.md) |

## What this repo is

Public design record, ticket store, and measurement harness for an
implementation-neutral work programme. The reference code lives in a fork of
someone else's project: `fork/` is git-ignored here and recreated by
`make upstream-checkout`. A `tickets/` directory must never appear in it, or it
would show up in a diff sent upstream.

## Handoff

The tracking repository is clean on `main`. `make check` is green on the system
interpreter; no `.venv` exists and none is needed. What is in flight upstream,
and what remains of the budget it spends, is `SYNC.md`'s to report.
