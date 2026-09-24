---
name: upstream-catchup
description: "Check whether upstream zoteus moved and what a re-baseline must re-run. Use per decision — before filing upstream, before measuring, before claiming currency — since `make check` never reports upstream movement."
argument-hint: "[--full]"
---

# Upstream catch-up and re-baseline

Scoped from `AGENTS.md` § Environment notes. Nothing tells you upstream moved
unless you ask; this is how to ask, and what to do with the answer.

- `UPSTREAM` owns the reviewed upstream SHA and the repository URLs.
  `make upstream-status` detects upstream movement, and it is not in
  `make check`, so nothing tells you upstream moved unless you ask.
  `make upstream-catchup` answers as a verdict rather than as reading: QUIET
  when nothing under `src/features/search/` moved and the index schema is
  unchanged, TOUCHED with the detail when something did, and `--full` adds the
  releases, merges, pull refs and branches. Its cost is flat in the number of
  releases, so catch up per DECISION — before filing, before measuring, before
  claiming currency — never per release. It never reports whether an issue is
  open, since that state is the forge's and a copy here would be stale on
  arrival; the report ends with the query URL instead.
- **A re-baseline does not automatically re-run the full benchmark or
  acceptance suite.** Read the upstream delta first, then run only the probes
  whose standing evidence could have been invalidated by a changed mechanism,
  schema, dependency, default, or runtime path. Measurements on untouched
  surfaces remain historical evidence and keep their grade; do not reproduce
  them merely because the version label moved. If a materially affected probe
  cannot run on an admissible substrate, say so and downgrade only the claim
  that depended on it. `make check-diff` remains the pre-commit repository gate;
  this rule concerns measurement campaigns and target acceptance runs, not the
  lightweight consistency and unit-test gate.
- `make upstream-checkout` recreates the git-ignored `fork/` at the reviewed
  SHA with both `origin` and `upstream` remotes. Do not overwrite an existing
  checkout.
