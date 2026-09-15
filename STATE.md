# STATE — Search Works for Zotero

*Live handoff. Updated 2026-09-15 (sitter 0.4.18, critical path 21:05Z). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search across a whole Zotero library — records, notes, annotations and full text, in
every language present — local by default, current, bounded, honest about coverage.
[README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- **Critical path: 0796 → 0795 → 0793 → 0797** (author, 2026-09-15). The sitter indexes
  nothing: two sweeps at `completed: 0`, admission never reached, the drain loop at
  `scheduler.js:201` unbounded — **0796**, and whether it recovers unaided is open. Then
  stop working against the sync that feeds it, and ship the phase that says so — **0795**,
  whose opening reading needs a bulk sync caught rather than provoked: author's hands.
  Then extraction wedged on one document, the AR6 plateau — **0793**. Then the "Pause
  indexing" checkbox — **0797**. Bound it, quiet it, unwedge it, make it legible.
- **v0.4.10 released; the tree is eight versions past it at 0.4.18, awaiting a retag.**
  Acceptance PASS covers **0.4.15 only** (`verification/acceptance/0.4.15-2026-09-14.json`);
  0.4.16 through 0.4.18 untested. Re-run `bench/sitter_acceptance.py`, or tag 0.4.15. **Author's
  hands only, in order:** build, GPG-sign the tag, publish the `.xpi`, then ONE commit
  adding BOTH `tag` and `update_link` (half-filled FAILs rule 2).
- Release the Multilingual test library and questions + grader as public Challenge.
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
  with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Handoff

**0727 and 0787 stay open as upstream matters**, both filed, neither ours to fix. Open here:
0774, 0786, and 0727's guard 2 — unbuilt: a check that cannot fire must not ship. Correctness
and privacy gaps unchanged: R10 (0660–0664), R13 (0650–0652), R15 (0654–0657), R22 (0643,
0665), fixtures 0602, 0623, 0658. #6012 parity train (0754, 0755–0757) and **0794** unstarted.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (0738). Requirements: **24 ratified**.
Tickets: `erg ready tickets/`. In flight: `gh pr list`. Hand-maintained: the heading is
`## Basic state`, not `## Status`, so `refresh-STATE.py` exits 2 by design.
