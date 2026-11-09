# STATE — Search Works for Zotero

*Live handoff. Updated 2026-11-09 (tidy sprint rounds 2-3: #644, #645, #646, #647, #649, #650 merged; #632, #642 and #648 open). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search across a whole Zotero library — records, notes, annotations, full text, every
language — local, current, bounded, honest about coverage. [README.md](README.md) owns the
proposition, [SPEC.md](SPEC.md) the design.

## Current Goals

- **The sitter's test ladder** (tracker **0815**, `plugins/sdt-sitter/TESTING.md`): **0822**
  (lifecycle in the Menagerie rung) is PR #632, reworked to switch off Zotero's translator update check
  in the test profile, verify-gate REROLL pending a live Menagerie run; then **0817** closes and **0819** (the bar for rung 3 and up) opens. **0794** left.
- **Before any live install**: 0826 closed (doudou holds 8 037 stale-processor packs, about 8 035 to
  regenerate on the first run). 0825 closed (PR #633, sitter 0.4.34: "Empty file" and "Web page saved
  as PDF" groups). **0827** ("Damaged PDF", 14 truncated files) is now unblocked.
- **Security, author's call**: sudo logged an `HF_TOKEN` value in padme's system journal on
  2026-11-09 (**0829**); rotation not done. The fix (env allowlist) is PR #642, NEEDS-AUTHOR on
  an exit criterion split into a new ticket 0830.
- **Rungs run on padme** under Xvfb, arenas on `~/data`, **one Zotero at a time**: two instances
  collide even on separate displays. doudou's load and small `/tmp` trip the sitter's own gates.
- The retag is **author's hands, in order**: build, GPG-sign, publish the `.xpi`, then ONE commit
  adding BOTH `tag` and `update_link`. Released tag v0.4.10; code at 0.4.39 (0786, 0800). #648 (0774) has merged main and renumbered to 0.4.40 (head e22384e1), since `make sitter-version` refuses a number over a changed payload.
- **0795** (pause while syncing, one unmeasured path) and **0793** (the AR6 slow tail; suspect
  **0811**) stay open. Zotero patches are followed by **0811**, **0812**, **0813**; [SYNC.md](SYNC.md).
- Release the Multilingual test library and questions + grader as public Challenge.

## Handoff

Open here: 0774 (#648: main merged at e22384e1; gaze on that head, then verify-gate round 2), 0814's guard 2. 0631 landed (#650, 61ff6c4a). Gaps: R10 (0660–0664), R13 (0650–0652), R15
(0654–0657), R22 (0643, 0665), fixtures 0602, 0658. #6012 train (0754–0757) unstarted.
Proposed next: a backlog triage with the author, cluster by cluster. The pristine library copy
lives on at padme `~/data/clone-rung/library`, refreshed by rsync from a cheap reflink snapshot
on doudou. Cleanup owed once #632 merges: padme's `~/data/clone-rung/2026-09-23/` and arenas.
Parked WIP: `wip/primary-dirty-check-split-20261109` (split `make check` into check-fast and
check-full, plus a "deploy memory v8" ticket whose number 0827 clashes with main's and needs a
claimed ID). Design notes now live under `design/` (0828; formerly `conception/`).
Journal: `memory/journal/2026/2026-11-09-tidy-sprint.md`.

## Basic state

Reviewed upstream: **v1.20.2** at `c386e83` (2026-09-17; `verification/UPSTREAM-1.20.2-REREAD.md`).
Requirements: **24 ratified**. Tickets: `erg ready tickets/`. In flight: `gh pr list`. Hand-maintained
(`## Basic state`, not `## Status`), so `refresh-STATE.py` exits 2 by design.
