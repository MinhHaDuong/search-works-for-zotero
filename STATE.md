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

**The full-library build finished** — 8 h 14, 363 613 passages, a 1,71 GB index, the
first populated current-schema data dir that serves. It unblocks 0605, 0120 and 0503's
measurement half; 0594/0595/0596 need no machine; `make ladder-matrix` is asked for and
unfiled.

**Blocked:** goal 3 (0580) terminates in X5 through 0566 → 0565 → 0028; 0581 waits on
0029, which codex holds. No lane work reaches either.

**Open:** #255, its base nine merges stale and needing a re-merge;
`claude/resume-journee-taj5f8` undecided.

**Next session, in order.** Two greps on this machine settle more than anything written
on 2026-09-03: whether build `20260817151751` carries `reindexTruncated` (grep the
extracted `omni.ja`), and whether the WASM document-worker caps pages (open `65F79PTJ`,
2 913 pages, in the reader; read the page catalog with
`verification/probes/sdt_read.py`). Then 0606 action 1, the pack-to-flat size ratio,
which decides that ticket's shape before any code. Then 0120 action 1, the measured
saving, still without a figure.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list. Still open here:
**is 0491 inside the codex fence**, and the two questions the 2026-09-03 ladder re-cut
raised — whether to split 0606, and which ticket owns the dispatcher 0564 and 0606
action 4 both describe. The re-cut itself is in the tickets (0606, 0557, 0560/0561/0564).

**The 0557 ladder was specified without reading the fork, and three of its premises are wrong**
(logged on 0557). seg/1 is built (fork `t0028-seg1` at `f936102`, 26 tests); 0560 is substantially
built as `extractPdfOutline`, dated a day before the tracker was filed; 0558 likely the same via
`annotate.ts` and upstream #29. Read the fork before picking up any child of 0557.
