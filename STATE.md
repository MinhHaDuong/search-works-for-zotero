# STATE — Search Works for Zotero

*Held under forty lines by ruling of 2026-08-31. Last updated 2026-09-03.*

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
| The 2026-09-02/03 overnight run: result, corrections, machine state | `~/data/projets/zoteus-bench/overnight-2026-09-02/LOOP-STATE.md` |

## Handoff

**Upstream shipped v1.13.0 today; the reviewed baseline is still v1.12.0.** #48 is in it,
verified in source: a resumed build reads `passages WHERE vector IS NULL` and re-fetches
nothing. **Re-baselining precedes everything** — 0033's remaining scope is what 1.13.0
moved, and 0504 is the pattern.

**0613, 0614, 0615 ask whether zoteus passes goal 1, 2, 3.** Goal 1 is 3 of 7 clauses
green: the update-check egress default (ours, a pull request), no uninstall surface,
R22's pair unreadable for want of counters. Goal 2 waits on 0033; goal 3 has no
assertions, which is 0580's. The matrix is `bench/results/0604-ladder-matrix/`.

**Open:** #278 decides the four host-bound cells; its caveat is that the egress sandbox's
read-only `/tmp` kills both desktop hosts ~7 s in, so `R10-no-egress` there measures
startup only. #276 is another lane's. **Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list; still open here is
**whether 0491 is inside the codex fence**, and the ladder re-cut's two questions.
