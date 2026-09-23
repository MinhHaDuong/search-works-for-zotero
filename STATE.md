# STATE — Search Works for Zotero

*Live handoff. Updated 2026-09-22 (sitter 0.4.31, 0810 closed, Zotero patches filed). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search across a whole Zotero library — records, notes, annotations, full text, every
language — local, current, bounded, honest about coverage. [README.md](README.md) owns the
proposition, [SPEC.md](SPEC.md) the design.

## Current Goals

- **0810 closed** (PR #607): sitter 0.4.31 refreshes the no-attachment view per generation, not
  per changed item. **0809 closed works-for-me** (2026-09-17): the pause stops the sitter live; the
  rung-3 Menagerie test FAILED step 3 on 0.4.26 at `45da9ac9`, then PASSED all nine steps at `58aff58b`
  (`verification/menagerie/0.4.26-2026-09-17.json`); the cause of the difference is not established.
- **The critical path is down to 0795.** The chain rested on "the sitter indexes nothing"; the
  2026-09-16 live run killed all four symptoms (`admit 11940`, `drain-end drained 5`, two
  `settle ok`). **0796 and 0797 closed.** **0795**: detection is one unmeasured path.
- **0793: the AR6 plateau is SLOW, not wedged.** 248 s at 90, then 95, `settle ok` at 469 s — the
  citation stage, silent by construction. Waits on the author's decision to announce the tail. Suspect: **0811**.
- **Zotero gets patches, not forum threads** (author, 2026-09-16). `GOVERNANCE.md` is
  zoteus-only. The three patches are filed — document-worker#33, zotero#6054, zotero#6055 —
  and followed by **0811**, **0812**, **0813**; [SYNC.md](SYNC.md) owns their live status.
- The retag is **author's hands, in order**: build, GPG-sign, publish the `.xpi`,
  then ONE commit adding BOTH `tag` and `update_link`. Released tag v0.4.10; code at 0.4.31.
- Release the Multilingual test library and questions + grader as public Challenge.

## Handoff

Open here: 0774, 0786, **0808** (the stall probe loses its run if stopped), 0814's guard 2 —
unbuilt: a check that cannot fire must not ship. Gaps: R10 (0660–0664), R13 (0650–0652), R15
(0654–0657), R22 (0643, 0665), fixtures 0602, 0623, 0658. #6012 train (0754–0757) and **0794**
unstarted. Hygiene (2026-09-22): 17 remote branches unmerged, 1 of 5 worktrees dirty.

## Basic state

Reviewed upstream: **v1.20.2** at `c386e83` (2026-09-17; `verification/UPSTREAM-1.20.2-REREAD.md`).
Requirements: **24 ratified**. Tickets: `erg ready tickets/`. In flight: `gh pr list`. Hand-maintained
(`## Basic state`, not `## Status`), so `refresh-STATE.py` exits 2 by design.
