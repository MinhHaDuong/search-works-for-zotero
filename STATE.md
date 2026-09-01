# STATE — Search Works for Zotero

*Reconciled 2026-08-31, and held under forty lines by ruling of the same day.
Last updated 2026-09-01 (conductor raid: 0551/0552/0556 merged; 0553 resumed
and closed with its two concurrency bugs fixed — PR #156 — taking 0567 with
it; 0565/0566 open, 0554 unblocked).*

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

`main` is clean, `make check` green on the system interpreter, no `.venv`
needed. Three things a session gets wrong by default. **Work may not be on
`main`**: fetch and sweep every branch before reading the working tree as the
whole picture. **The reviewed baseline is deliberately behind upstream** —
ticket 0520 owns the bump, held until `DECISIONS.md`'s awaiting trigger is
ratified, so `make upstream-status` STALE is expected. And **the PR 2
measurement campaign runs on padme, not here** — frozen substrates, both
repos, and the instruction were staged there 2026-09-01; its record lands on
branch `t0091-pr2-expansion` (state: ticket 0091's log and
`verification/0091-SERIES-CHECKPOINT.md`). Harvest that branch before
re-measuring anything diacritics-related on this machine.
