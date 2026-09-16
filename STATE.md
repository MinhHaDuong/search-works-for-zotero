# STATE — Search Works for Zotero

*Live handoff. Updated 2026-09-16 (sitter 0.4.26, AR6 read 10:41Z). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search across a whole Zotero library — records, notes, annotations, full text, every
language — local, current, bounded, honest about coverage. [README.md](README.md) owns the
proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- **Critical path: 0796 → 0795 → 0797** (author, 2026-09-15). The sitter indexes nothing:
  sweeps at `completed: 0`, admission never reached, drain loop unbounded — **0796**, bounded
  in PR 590, awaiting a live reading; unaided recovery open. Then **0795** (phase, label,
  backoff shipped; detection is one unmeasured path, dead until a two-armed reading), **0797**.
- **0793 is off the critical path: the AR6 plateau is SLOW, not wedged.** Live on 0.4.26 —
  248 s at 90, then 95, `settle ok` at 469 s. It is the citation/reference stage, silent by
  construction (five `onProgress` sites; the page loop owns 5→90). 0793 waits only on the
  author's decision to announce the tail. The suspect: **0679**, O(B × R).
- **Zotero gets patches, not forum threads** (author, 2026-09-16). `GOVERNANCE.md` is
  zoteus-only. Convert **0679**, **0727** (133758), **0787** (133759) to PRs. Blocker for
  all three: the shipped `worker.js` is a bundle, upstream source not located.
- **v0.4.10 released; the tree is sixteen versions past it, awaiting a retag.** Acceptance PASS
  covers **0.4.15 only**. Re-run `bench/sitter_acceptance.py` or tag 0.4.15. **Author's hands,
  in order:** build, GPG-sign, publish the `.xpi`, then ONE commit adding `tag` + `update_link`.
- Release the Multilingual test library and questions + grader as public Challenge.

## Handoff

Open here: 0774, 0786, **0808** (the stall probe loses its run if stopped), and 0727's
guard 2 — unbuilt: a check that cannot fire must not ship. Gaps unchanged: R10 (0660–0664),
R13 (0650–0652), R15 (0654–0657), R22 (0643, 0665), fixtures 0602, 0623, 0658. #6012 train
(0754–0757) and **0794** unstarted. Hygiene: 23 branches unmerged, 8 worktrees dirty.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (0738). Requirements: **24 ratified**. Tickets:
`erg ready tickets/`. In flight: `gh pr list`. Hand-maintained (`## Basic state`, not
`## Status`), so `refresh-STATE.py` exits 2 by design.
