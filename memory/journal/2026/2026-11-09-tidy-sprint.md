# 2026-11-09 — tidy sprint (TLC sprint, 15:22Z to 19:22Z)

Context: an autonomous tidy pass on this repository, led from the CNRS interface
session on padme (dirty files, branches and worktrees, open PRs, ready tickets).
The first lead exhausted its context after the merges; a second lead ran this roar.

## Merged (forge merge commits, read back)

| PR | Merge commit | Content |
|----|--------------|---------|
| #640 | 2f7a7621 | ticket 0829: acceptance adapters forward the whole environment to sudo, which logs it |
| #638 | 2f9de2ca | ticket 0828: adopt design/ (rename conception/, sort tracked docs/) |
| #635 | 44a55256 | ticket 0732: external Menagerie spot check recorded |
| #633 | 05cbb071 | sitter 0.4.34: Empty file and Web page saved as PDF groups, never retried (0825, closed) |
| #639 | cb0c5293 | tickets: required erg ID claims adopted (git-erg 513cd3c4) |
| #641 | e2ddb3f3 | rename conception/ to design/ and update live references (0828, closed) |

Main after the sprint: e2ddb3f3.

## Left open

- #632 (0822, lifecycle in the Menagerie rung), head 5b958987: verify-gate REROLL; it needs a
  live Menagerie run on padme, which the sprint did not perform.
- #642 (0829, env allowlist for sudo --preserve-env), head 359b8022: NEEDS-AUTHOR; one exit
  criterion was split out into a new ticket 0830, and the split is the author's call.

## Branches, worktrees, dirty files

- Six merged local branches and sixteen stale worktrees were removed by the first lead.
  Among the worktrees: `t1478-claims-16705`, which may have belonged to a harness agent
  (ticket 1478); the "ticket 1478 summary" session was notified. Its branch has no remote copy.
- The primary checkout's dirty files were committed and pushed to
  `wip/primary-dirty-check-split-20261109` (tip abb677ad): a WIP split of `make check` into
  check-fast and check-full, plus an untracked ticket file `tickets/0827-d-ployer-la-m-moire-v8.erg`
  (deploy memory v8; created by codex on 2026-10-05 from GitHub issue 636, never committed).
  Its number clashes with main's `tickets/0827-a-damaged-pdf-group-…` (2026-09-24), and since
  #639 ticket IDs need a claim, so it needs a fresh claimed number before it can land.
- Untracked in the primary and left alone: `nohup.out`, `zotero-work/`.

## Security fact

At 14:05:52 (time as recorded in ticket 0829) sudo wrote to padme's system journal, readable by the journal
group, an invocation whose `ENV=` list carried the whole inherited environment, an `HF_TOKEN`
value among it (ticket 0829). The value was not copied anywhere. Rotating the token is the
author's decision; nothing was rotated during the sprint. The code fix is PR #642, open.

## Review attribution

Records captured under `memory/evidence/attribution/` for #639 and #641. Capture failures,
reported rather than reconstructed: #633 (two verify-gate rounds on the PR, ESCALATE then
APPROVED, but no gaze seat or reviewer model identity in the trail), #635, #638 and #640
(no review trail on the forge: no gaze result, no attribution block).

## Round 2 (16:55Z to 18:20Z): ready tickets

Seven tickets hunted, five merged, each by a Sonnet executor in its own worktree; gates by Opus seats.

| Ticket | PR | State |
|--------|----|-------|
| 0627 README per-row table test | #645 | merged, head fa104220 |
| 0802 phase scrape ignores comments | #644 | merged, head 42955056 (0801 still supersedes it) |
| 0808 stall probe survives SIGINT/SIGTERM | #646 | merged, head c7f0d88c |
| 0786 generation token on removal recheck | #649 | merged, head 7544d7d1, sitter 0.4.35 |
| 0774 say why the cache emptied | #648 | parked: round 1 APPROVED on 7c58817c; merging main (0.4.35) forced a bump to 0.4.38, so head 399d3357 needs a fresh gaze, then gate round 2 |
| 0800 smallest attachment first | #647 | merged after round 2, head 11c80ec1, sitter 0.4.39 (round 1 REROLL: starvation unanswered; fixed by a drain argument and mutant M37) |
| 0631 resolver_shape hardening | #650 | parked: round 1 REROLL (scoping inert on real `-e trace=network` traces), fixed at a301308d; round 2 owed |

Facts worth keeping:
- Parallel sitter lanes collide by construction: `check_sitter_version` rule 1 refuses a lane's
  own number once a merge of main changes its payload, so every merge-main costs a version bump
  and a re-gate. Serialize sitter-payload tickets, or land them one per gate cycle.
- `make check` was killed twice by an outside SIGTERM inside `sitter-mutants` (source not found);
  re-running the remaining targets passed.
- `sitter-version` rule 3 reads open PRs and printed NOT-RUN (HTTP 403) for several runs.
- One codex correctness seat ran in gaze on #648 (external seat, under 0.10 USD, estimate).
- Ticket 0715 skipped: it needs Zotero's omni.ja, not installed on padme. 0596 skipped: its code
  is not in this repository.
