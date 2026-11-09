# 2026-11-09 evening: #648, #642 and #632 landed

Context: the tidy sprint left three pull requests open (STATE.md at 4446e3df). One
coordinator session on padme took them over at about 18:45 UTC.

## Events

- **#648 (0774, sitter cache-drop notice).** The parked worktree was merged with main
  (sitter 0.4.39 there) and renumbered to 0.4.40. Gaze REVIEWED, verify-gate round 2
  APPROVED at e22384e1, merged 74af3290.
- **#642 (0829, sudo env allowlist).** Round 2 had ruled NEEDS-AUTHOR on a live
  sudo-journal criterion split into 0830. padme has the `untrusted-runner` account, so the
  check was run instead of asked. In the journal, names only: the fixed tree's strace entry
  carried 80 ambient names, none credential-looking. A same-minute control from an
  unfixed tree carried 85, including `HF_TOKEN` and `CLAUDE_CODE_MESSAGING_TOKEN`. The
  14:05 incident line was the traced re-invocation (`posture.forwardable(os.environ)`),
  not the adapters' python3 line the ticket blamed; that line's ENV was already empty.
  Gate rounds were spent, so the author ruled "Merge 642"; merged cd0ffdfe.
- **#632 (0822, lifecycle in rung 3).** An Opus agent ran the whole Menagerie live at head:
  green at 0.4.39 and again at 0.4.40 after #648 changed the sitter, plus a red
  `--repository-check` run. Gaze REVIEWED (after an ESCALATE on an invalid seat report),
  verify-gate round 2 APPROVED at 2f5abb5d, merged cf631232 on the author's "Merge 632".
- Housekeeping PR #656 refreshed STATE.md.

## Snags observed

- During two parallel gaze runs, the housekeeping session removed the worktree the gaze
  forks had started from (`t0774-288575-4791`). Both `gaze_close.py` runs crashed in
  `containment()` before recording; one pass was re-filed from the raw seat store, the
  other re-run. Harness ticket 1491 holds the incident.
- `make check-diff` fails on padme: the Makefile's `IDH_HOME ?= $(HOME)/.claude` names a
  directory with no `scripts/`, while the helper lives in `~/.agents/scripts/`. Lanes fell
  back to full `make check`.
- `raid_land.py` on #632 tried to arm auto-merge on an ungated base; GitHub refused it
  ("Pull request is in clean status"). The PR was merged directly with
  `--match-head-commit` after the close commit was confirmed bookkeeping.
- `make sitter-version` rule 3 reports NOT-RUN (HTTP 403) unless `GH_TOKEN` is exported.

## Outcome

No pull request open at 8907331d. Open follow-ups: 0830, 0831, token rotation (author),
tracker 0817's integration review.
