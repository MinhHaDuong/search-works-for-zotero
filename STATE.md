# STATE — Search Works for Zotero

*Live handoff. Updated 2026-09-17 (sitter 0.4.26, acceptance FAIL 11:38Z). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search across a whole Zotero library — records, notes, annotations, full text, every
language — local, current, bounded, honest about coverage. [README.md](README.md) owns the
proposition, [SPEC.md](SPEC.md) the design.

## Current Goals

- **The release is blocked: acceptance FAILS on 0.4.26** (`45da9ac9`) — the pause checkbox
  reports "Indexing is off" while the sitter completes all four fixture documents. **0809** is
  the one thing left; last PASS is 0.4.15, so the regression sits in 0.4.16–0.4.26.
- **The critical path is down to 0795.** The chain rested on "the sitter indexes nothing"; the
  2026-09-16 live run killed all four symptoms (`admit 11940`, `drain-end drained 5`, two
  `settle ok`). **0796 and 0797 closed.** **0795**: detection is one unmeasured path.
- **0793: the AR6 plateau is SLOW, not wedged.** 248 s at 90, then 95, `settle ok` at 469 s —
  the citation/reference stage, silent by construction (five `onProgress` sites; the page loop
  owns 5→90). Waits on the author's decision to announce the tail. Suspect: **0679**.
- **Zotero gets patches, not forum threads** (author, 2026-09-16). `GOVERNANCE.md` is
  zoteus-only. Convert **0679**, **0727** (133758), **0787** (133759) to PRs. Blocker for
  all three: the shipped `worker.js` is a bundle, upstream source not located.
- After 0809, the retag is **author's hands, in order**: build, GPG-sign, publish the `.xpi`,
  then ONE commit adding BOTH `tag` and `update_link`. v0.4.10 is sixteen versions behind.
- Release the Multilingual test library and questions + grader as public Challenge.

## Handoff

Open here: 0774, 0786, **0808** (the stall probe loses its run if stopped), 0727's guard 2 —
unbuilt: a check that cannot fire must not ship. Gaps: R10 (0660–0664), R13 (0650–0652), R15
(0654–0657), R22 (0643, 0665), fixtures 0602, 0623, 0658. #6012 train (0754–0757) and **0794**
unstarted. Hygiene: 6 branches unmerged, 9 worktrees dirty.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (0738). Requirements: **24 ratified**. Tickets:
`erg ready tickets/`. In flight: `gh pr list`. Hand-maintained (`## Basic state`, not
`## Status`), so `refresh-STATE.py` exits 2 by design.
