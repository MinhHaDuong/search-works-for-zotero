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

**The full-library build finished** — 8 h 14, 363 613 passages, a 1,71 GB index,
and the first populated current-schema data dir that serves. It unblocks 0590,
0120 and 0503's measurement half, all deferred all night for want of it;
0594/0595/0596 need no machine; `make ladder-matrix` is asked for and unfiled.

**Blocked:** goal 3 (0580) terminates in X5 through 0566 → 0565 → 0028, and 0581
waits on 0029, which codex holds. No lane work reaches either.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list, the service
ceiling included (0577 closed, GPU arm measured). Also: may a lane merge its own
PR, and **is 0491 inside the codex fence** — the two handoff documents disagree.

**Open:** nothing. #232 and #235 merged after their one citation fix each (`0bb5304`,
`9dd6fcd`); `main` green at 592/13, 167 tickets. `claude/resume-journee-taj5f8` undecided.
