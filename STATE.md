# STATE — Search Works for Zotero

*Live handoff. Updated 2026-09-24 (sitter ladder rungs 2–4 real, code at 0.4.33, 143 open tickets). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search across a whole Zotero library — records, notes, annotations, full text, every
language — local, current, bounded, honest about coverage. [README.md](README.md) owns the
proposition, [SPEC.md](SPEC.md) the design.

## Current Goals

- **The sitter's test ladder** (tracker **0815**, `plugins/sdt-sitter/TESTING.md`): rungs 2–4 now run
  with the integrity check — 0816, 0818, 0821, 0824 closed on 2026-09-23. Left: **0822** (lifecycle in
  the Menagerie rung, now unblocked; tracker **0817**), **0819** (the bar for rung 3 and up), **0794**.
- **Before any live install**: the clone run's two findings are accounted for, neither a sitter defect
  (`verification/clone/0818-findings-2026-09-24.md`). **0825**: `failed` is absent files plus known
  native failures. **0826**: stale-processor packs, which set the first live run's length.
- **Rungs run on padme** under Xvfb, arenas on `~/data`; doudou's load and small `/tmp` trip the
  sitter's own gates. The dialog now names such a refusal (0823).
- The retag is **author's hands, in order**: build, GPG-sign, publish the `.xpi`, then ONE commit
  adding BOTH `tag` and `update_link`. Released tag v0.4.10; code at 0.4.33.
- **0795** (pause while syncing, one unmeasured path) and **0793** (the AR6 slow tail; suspect
  **0811**) stay open. Zotero patches are followed by **0811**, **0812**, **0813**; [SYNC.md](SYNC.md).
- Release the Multilingual test library and questions + grader as public Challenge.

## Handoff

Open here: 0774, 0786, **0808**, 0814's guard 2. Gaps: R10 (0660–0664), R13 (0650–0652), R15
(0654–0657), R22 (0643, 0665), fixtures 0602, 0658. #6012 train (0754–0757) unstarted.
Proposed next: a backlog triage with the author, cluster by cluster. The pristine library copy
lives on at padme `~/data/clone-rung/library`, refreshed by rsync from a cheap reflink snapshot
on doudou. Cleanup owed once 0825 and 0826 settle: the dated `~/data/clone-rung/2026-09-23/` and
the run arenas on padme. Hygiene (2026-09-24): 15 remote branches unmerged into main.

## Basic state

Reviewed upstream: **v1.20.2** at `c386e83` (2026-09-17; `verification/UPSTREAM-1.20.2-REREAD.md`).
Requirements: **24 ratified**. Tickets: `erg ready tickets/`. In flight: `gh pr list`. Hand-maintained
(`## Basic state`, not `## Status`), so `refresh-STATE.py` exits 2 by design.
