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

**Open:** #255, its base long stale and needing a re-merge;
`claude/resume-journee-taj5f8` undecided.

**Next session.** The three probes this line used to order are answered and merged
(`28a5685`, `8c261ba`): `reindexTruncated` ships but fires only on a live preference
change, so **1 053 attachments sit truncated at 100 pages** under a raised cap; the WASM
worker is **uncapped** (2 913 of 2 913); 0606's ratio is **2,24** at book scale, and that
route runs at 5,26 pages/s — about 24,6 h to pack the library. What remains is **0120
action 1**, the measured saving, still the only thing that ticket formally requires and
still without a figure.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list. Still open here:
**is 0491 inside the codex fence**, and the two questions the 2026-09-03 ladder re-cut
raised — whether to split 0606, and which ticket owns the dispatcher 0564 and 0606
action 4 both describe. The re-cut itself is in the tickets (0606, 0557, 0560/0561/0564).

**The 0557 ladder was specified without reading the fork, and three of its premises are wrong**
(logged on 0557). seg/1 is built (fork `t0028-seg1` at `f936102`, 26 tests); 0560 is substantially
built as `extractPdfOutline`, dated a day before the tracker was filed; 0558 likely the same via
`annotate.ts` and upstream #29. Read the fork before picking up any child of 0557.
