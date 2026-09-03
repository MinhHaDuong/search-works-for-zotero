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

**Blocked:** goal 3 (0580) terminates in X5 through 0566 → 0565 → 0028; 0581 waits on
0029, which codex holds. No lane work reaches either.

**Open:** #255, its base long stale and needing a re-merge;
`claude/resume-journee-taj5f8` undecided.

**Next.** **0120 action 1**, the measured saving — the one thing that ticket formally
requires and still without a figure. The 2026-09-03 caps and route probes are answered
and merged: `verification/SDT-CAPS-0483.md` and `EXTRACTION-ROUTES.md` own what they
found, 0610 the population they left undrained.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list. Still open here:
**is 0491 inside the codex fence**, and the ladder re-cut's two questions — whether to
split 0606, and which ticket owns the dispatcher 0564 and 0606 action 4 both describe.
