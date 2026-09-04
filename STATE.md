# STATE — Search Works for Zotero

*Held under forty lines by ruling of 2026-08-31. Last updated 2026-09-04.*

One page of live operational handoff, and it owns nothing: every line points
to the document that owns the fact. What this repository is is [`README.md`](README.md)'s.

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

**Reviewed baseline: v1.14.0** (`34d6c26`, ticket 0670, main's tip two documentation commits past the tag).

**Through the September 21 checkpoint:** focus on correctness, packaging,
privacy, and their unfinished tests. Keep #56 as a contained contribution;
defer the separate indexer/worker rewrite, oversized-document segmenter, and
other feature work. [`SYNC.md`](SYNC.md) owns #56's live state; `erg ready`
owns the executable queue.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list — 0491's codex-fence question, the ladder re-cut's two.

## Status
<!-- generated 2026-09-04T12:34Z · as of 2091c06 -->

**Tickets:** 56 ready · 31 blocked · 7 awaiting author — `erg ready tickets/` for full list
  next: 0025 Experiments X1-X7, each before its dependent, e… · 0026 Repo-side gates: fold, golden, RSS, convergence…
**In flight:** 1 open PR — #327 (0632, golden-fixture harness verify)
**Recent (first-parent):**
  2091c06 Merge pull request #355 from MinhHaDuong/fix/v114-count-correction
