# STATE — Search Works for Zotero

*Live handoff. Updated 2026-11-09 night (#648, #642, #632 merged and wrapped up; no pull request open). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search across a whole Zotero library — records, notes, annotations, full text, every
language — local, current, bounded, honest about coverage. [README.md](README.md) owns the
proposition, [SPEC.md](SPEC.md) the design.

## Current Goals

- **The sitter's test ladder** (tracker **0815**, `plugins/sdt-sitter/TESTING.md`): **0822**
  (lifecycle in the Menagerie rung) closed with PR #632, green live at sitter 0.4.40. Tracker **0817** closed 2026-11-09;
  its rerun with **0794**'s two documents is now one of 0794's exit criteria. **0819** (the bar for rung 3
  and up) is unblocked.
- **Before any live install**: 0826 closed (doudou holds 8 037 stale-processor packs, about 8 035 to
  regenerate on the first run). 0825 closed (PR #633, sitter 0.4.34: "Empty file" and "Web page saved
  as PDF" groups). **0827** ("Damaged PDF", 14 truncated files) is now unblocked.
- **Security, author's call**: sudo logged an `HF_TOKEN` value in padme's system journal on
  2026-11-09 (**0829**); rotation not done. The fix (env allowlist) landed with PR #642; **0830** (journal
  criterion, names only, read live) and **0831** (the traced re-invocation's ambient names) stay open.
- **Rungs run on padme** under Xvfb, arenas on `~/data`, **one Zotero at a time**: two instances
  collide even on separate displays. doudou's load and small `/tmp` trip the sitter's own gates.
- The retag is **author's hands, in order**: build, GPG-sign, publish the `.xpi`, then ONE commit
  adding BOTH `tag` and `update_link`. Released tag v0.4.10; code at 0.4.40 (0786, 0800, 0774).
- **0795** (pause while syncing, one unmeasured path) and **0793** (the AR6 slow tail; suspect
  **0811**) stay open. Zotero patches are followed by **0811**, **0812**, **0813**; [SYNC.md](SYNC.md).
- Release the Multilingual test library and questions + grader as public Challenge.

## Handoff

Open here: 0814's guard 2. Gaps: R10 (0660–0664), R13 (0650–0652), R15
(0654–0657), R22 (0643, 0665), fixtures 0602, 0658. #6012 train (0754–0757) unstarted.
Proposed next: a backlog triage with the author, cluster by cluster. The pristine library copy
lives on at padme `~/data/clone-rung/library`, refreshed by rsync from a cheap reflink snapshot
on doudou. Cleanup owed now that #632 merged (author's call): padme's `~/data/clone-rung/2026-09-23/` and arenas.
Parked WIP, branches pruned 2026-11-09 and kept as tags `archive/2026-11-09/*`: the draft
`make check` split into check-fast and check-full (with a "deploy memory v8" ticket whose number
clashes with main's 0827) is `archive/2026-11-09/wip-primary-dirty-check-split-20261109`. Design notes now live under `design/` (0828; formerly `conception/`).
Journal: `memory/journal/2026/2026-11-09-tidy-sprint.md`.

## Basic state

Reviewed upstream: **v1.20.2** at `c386e83` (2026-09-17; `verification/UPSTREAM-1.20.2-REREAD.md`).
Requirements: **24 ratified**. Tickets: `erg ready tickets/`. In flight: `gh pr list`. Hand-maintained
(`## Basic state`, not `## Status`), so `refresh-STATE.py` exits 2 by design.
