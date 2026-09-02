# STATE — Search Works for Zotero

*Held under forty lines by ruling of 2026-08-31. Last updated 2026-09-02.*

One page of live operational handoff, and it owns nothing: every line is a
pointer to the document that does own the fact, and anything longer than a
pointer has drifted. What this repository is, and what each document is for,
is [`README.md`](README.md)'s.

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

## Handoff

**Twelve rulings landed 2026-09-02** and the awaiting list is much shorter;
`DECISIONS.md` is the record and the only place that says what is still open.
Two of them moved documents: the goals ladder left `SPEC.md` for `README.md`,
and the document map moved to `AGENTS.md`, which is now the agent instruction
filename.

**Next:** 0578 and 0585 landed 2026-09-02; 0583, 0584 and 0586 own the
remaining adapters. X5 still gates 0028 and eleven tickets under it. `erg
ready` owns the rest of the queue, branch and worktree included.

**Awaiting the author:** `DECISIONS.md`; ticket 0582 records its README call.
Tracker 0550 owns the stale two-process topology in `SPEC.md` §4 and §5.1.
`origin/claude/resume-journee-taj5f8` holds an unmerged remote-container
harness loader, undecided. The PR-2 diacritics record is ticket 0091's log;
the previously named `t0091-pr2-expansion` branch never reached origin.
