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

**Reviewed baseline: v1.13.0** (`b0e0bc8`, ticket 0618, main's tip not the tag).

**0625 merged (PR #295): target processes run under a dedicated account,
never the operator.** `tester` provisioned and verified on doudou and padme
(Makefile). 0626 is open, filed as the test-coverage follow-up.

**0613/0614/0615: does zoteus pass goal 1/2/3?** Goal 1's account
precondition is met on both machines. Gap A (egress control-arm,
`ZOTEUS_UPDATE_CHECK=false`) runs once `fork/` is rebuilt at the reviewed SHA
(this checkout is stale). Gap B (uninstall) stays blocked on a published
`UNINSTALL.md`, deferred. Gap C and goal 2 wait on 0033; goal 3 has no
assertions (0580's). Matrix: `bench/results/0604-ladder-matrix/`.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list; open here: whether 0491 is inside the codex fence, and the ladder re-cut's two questions.
