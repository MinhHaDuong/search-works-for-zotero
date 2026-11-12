# 2026-11-12: `.claude/rules/` retired into AGENTS.md (#661, ticket 0833)

Context: the author asked to merge the three path-scoped rule files into
`AGENTS.md` and delete the directory, because only Claude Code reads it.

## Events

- The three files became `AGENTS.md` § Path-scoped rules, one subsection per file,
  each headed by its old `paths:` list. `.gitignore` dropped the exception, and
  `DECISIONS.md` gained a 2026-11-12 entry quoting the directive verbatim.
- `make check-diff` exited 2 with the default `IDH_HOME` (`~/.claude/scripts/scoped-check.py`
  is missing). It ran with `IDH_HOME=$HOME/.agents`. Filed as ticket 0834.
- The two edits to `bench/*.py` comments made the diff unmapped, so the full gate ran
  each time. The first run was killed by the 10-minute background-shell limit, not by a
  failure; with a 60-minute limit it passed (1646 passed, 16 skipped), three times.
- `/verify-gate` refused twice without ruling: once with no gaze record on notes, once
  with the gaze record stale after a fix commit. Gaze round 1 found FINDINGS: the merge
  had dropped "without waiting for ratification" from the false-fact exception. A Sonnet
  seat and the session's own read both caught it. The clause was restored, re-gaze
  answered REVIEWED, verify-gate round 1 APPROVED at d531a70f, and `raid_land.py` merged
  48064ca4.
