# STATE — Search Works for Zotero

*Held under forty lines by ruling of 2026-08-31. Last updated 2026-09-04T09:04Z.*

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

**Reviewed baseline: v1.13.0** (`b0e0bc8`, ticket 0618, main's tip not the tag).

**0613/0614/0615: does zoteus pass goal 1/2/3?** Gaps A/B closed, sent
upstream (#54, #55). Gap C (R22) now decided **FAIL** not `not-run` (0642+0643):
`stop` doesn't gate a later `build` — sent as #56, waiting on the maintainer.

**Awaiting the author:** [`DECISIONS.md`](DECISIONS.md) owns the list — 0491's codex-fence question, the ladder re-cut's two.

## Status
<!-- generated 2026-09-04T09:04Z · as of e12c4ca -->

**Tickets:** 43 ready · 31 blocked · 6 awaiting author — `erg ready tickets/` for full list
  next: 0025 Experiments X1-X7, each before its dependent, e… · 0026 Repo-side gates: fold, golden, RSS, convergence…
**In flight:** 1 open PR — #327 (0632, golden-fixture harness verify)
**Recent (first-parent):**
  e12c4ca Merge pull request #349 from MinhHaDuong/housekeeping-20260904
  fb90b42 Merge pull request #348 from MinhHaDuong/worktree-t0656-pause-issue
  ec6f52f Merge pull request #347 from MinhHaDuong/t0643-validate
