# STATE — Search Works for Zotero

*Reconciled 2026-08-31, and held under forty lines by ruling of the same day.*

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

`main` is clean, `make check` green on the system interpreter, no `.venv`
needed. Two things a session gets wrong by default. **Work may not be on
`main`**: fetch and sweep every branch before reading the working tree as the
whole picture. And **the reviewed baseline is deliberately behind upstream** —
ticket 0520 owns the bump, held until `spec/DECISIONS.md`'s awaiting trigger is
ratified, so `make upstream-status` STALE is expected.
