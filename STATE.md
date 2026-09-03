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
and the first populated current-schema data dir that serves. It unblocks 0605,
0120 and 0503's measurement half, all deferred all night for want of it;
0594/0595/0596 need no machine; `make ladder-matrix` is asked for and unfiled.

**Blocked:** goal 3 (0580) terminates in X5 through 0566 → 0565 → 0028, and 0581
waits on 0029, which codex holds. No lane work reaches either.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list — the service ceiling
(0577 closed) and the 0590 redesign's three entries included. Still open: **is 0491 inside the codex fence**.

**Open:** #255 — its base has moved nine merges, so its quoted gates are stale and it
needs a re-merge. #232 and #235 merged after their one citation fix each (`0bb5304`,
`9dd6fcd`); `claude/resume-journee-taj5f8` undecided.

**2026-09-03, the extract session (0120, 0483, 0606).** `main` green at 592/13, 169
tickets. #256 merged (`b6d739a`) after `REROLL` then `ESCALATE` on its page; this branch
merged on the author's explicit instruction with **no review verdict on its page**, which
he waived and which is recorded there rather than inferred. What it leaves for the next
session, in order: **two greps on this machine settle more than anything written today** —
whether build `20260817151751` carries `reindexTruncated` (grep the extracted `omni.ja`),
and whether the WASM document-worker caps pages (open `65F79PTJ`, 2 913 pages, in the
reader; read the pack's page catalog with `verification/probes/sdt_read.py`). Then 0606's
action 1, the pack-to-flat size ratio on the two real packs, which decides that ticket's
shape before any code. Then 0120 action 1, the measured saving, still the only thing the
ticket formally requires and still without a figure. Awaiting the author beyond
`DECISIONS.md`'s standing list: three entries of 2026-09-03 — the refresh belonging to the
R1 tick, supersession being total, and 0606's third extractor identity in C1 link 1.
