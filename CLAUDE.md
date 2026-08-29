# CLAUDE.md — how to work in this repo

Work tracking for the search redesign of zoteus (an MCP server over a local
Zotero library). This repo holds documents, tickets, and a measurement
harness — the TypeScript under discussion lives upstream at `oscardvs/zoteus`
and in the author's fork, not here.

## The document set, and who is authoritative for what

The specification chain lives in `spec/`. What changes week to week — `STATE.md`,
`SYNC.md`, `RUNBOOK.md` — stays at the top level, as do `README.md` and this file.

- `spec/REQUIREMENTS.md` / `spec/CONSTRAINTS.md` — the sheet, materialized. Stable.
- `spec/DESIGN.md` — the current design ("The Instrumented Ledger", cycle 2). Owns
  every design number: gate thresholds (§2.8), experiment decision rules
  (§3), budgets (§2.9).
- `spec/TERMINOLOGY.md` — the glossary, alphabetical, in three marked buckets
  (ours, inherited from Zotero, inherited from SQLite) plus a historical
  section. Authoritative for what a word means and for which document owns it.
  Owns no design number and settles no open question: it points at the owner
  instead, and `bench/check_terminology.py` fails on any digit that is not an
  address. Serves the chain without being in it — enter a document in the
  middle and look the vocabulary up here.
- `spec/DECISIONS.md` — append-only ratification ledger. The author's rulings land
  here FIRST; the other documents are edited to match. Owns the record of
  every ruling, technical and process alike, and the awaiting-ratification
  questions. Never edit a ratified entry.
- `GOVERNANCE.md` — how this repo conducts itself upstream: the bounds on our
  own conduct, going forward. It owns the rules; the ledger keeps the rulings
  that made them, and `SYNC.md` keeps the live counts. Split ratified
  2026-08-29.
- Tickets `0014`–`0037` (`tickets/`, git-erg) — the executable work train;
  authoritative for each item's scope, evidence, and live state. `DESIGN.md
  §4` carries only the ordering.
- `spec/FIELD-REVIEW.md` — the survey of prior art: what other people have already
  built for Zotero AI retrieval, what it teaches, and what is
  license-compatible to borrow. Authoritative for the inventory and for each
  project's observed state at its stated observation date. Owns no design
  number, no requirement, and no threshold; where it touches our design it
  points at the owning document. A dated snapshot, not a live tracker.
- `SYNC.md` — upstream tracking (maintainer behavior, PR/issue status).
  `STATE.md` — the prototype phase's measurement record; mostly frozen.
  `RUNBOOK.md` — how to run the measurements, and on which substrate.
- The cycle-2 panel's verbatim session record (memos, critiques, the political
  and implementation reviews) is in git history, last present at commit
  `e32afe3` as `panel/cycle2/`. It was never authoritative; where it disagrees
  with DESIGN.md, DESIGN.md is the record.
- `verification/` — evidence, not authority. Reports that settle a factual
  question (a platform probe, an acceptance dossier, a voice measurement) and
  the scripts under `verification/probes/` that produced them. A report is
  cited by path from the ticket it serves and never becomes a source of
  truth: where it touches the design, the owning document above is the
  record. Reports live here rather than in an agent worktree because an
  uncommitted artifact dies with the worktree — the report about the work is
  not the work.
- Superseded documents are DELETED, not archived in the tree — git is the
  archive. Do not create `history/` directories or versioned doc copies.

## Conventions

- `make check` must be green before any commit: ruff, the figure guard
  (`bench/check_figures.py`), the governance guard
  (`bench/check_governance.py`), the terminology guard
  (`bench/check_terminology.py`), pytest. The figure guard is load-bearing —
  every measurement quoted in prose is declared there with an anchor; when
  you quote a number from `bench/results/`, declare it; when you re-measure,
  the guard tells you every prose site to update.
- Numbers use decimal comma and space thousands ("2 084,9 MiB", "360 811") —
  the guard cannot match US formatting.
- Both numbers, always: any external memory claim carries the honest pair
  (e.g. 45x and 6,8x) — see README.
- Tickets: `./tickets/erg` (check / ready / new / close / log). Rules in
  `tickets/AGENTS.md`. `erg check` must pass; `erg ready` is the work queue;
  sequencing is machine-readable `Blocked-by`, not prose.
- One statement per fact: thresholds, rules, and open questions live in their
  owning document (above) and everywhere else is a pointer. Duplicated
  numbers drift — this repo's most expensive recurring defect.

## Upstream relations

Binding, and stated once in `GOVERNANCE.md`: the volume bound, the budget, the
form each item takes, the sunset, the harness transfer, the fork's end state.
Read it before filing anything upstream. What remains live against those bounds
is `SYNC.md`'s, never restated elsewhere.

The one line worth repeating here, because it governs every outward action
rather than a filing decision: never put this repo's internal governance or its
reading of the maintainer into upstream text. The repo is public and he reads
it. `bench/check_governance.py` enforces the separation on our side of the line;
nothing enforces it on the text you send, so read what you send, as sent.

## Environment notes

- `UPSTREAM` owns the reviewed upstream SHA and repository URLs.
  `make upstream-status` detects upstream movement; `make upstream-checkout`
  recreates the git-ignored `fork/` at that exact SHA with both `origin` and
  `upstream` remotes. Do not overwrite an existing checkout.
- The measurement corpora are NOT in this repo: real vectors, the 477k index,
  and the 44.9 MB extraction live on the author's machine; `bench/results/`
  holds committed JSON summaries. Ticket 0025's substrate map says which
  experiments run where.
- The author's fork (`FORK_REPOSITORY` in `UPSTREAM`) is authorized for direct
  pushes from Claude sessions — in a remote session, attach it with `add_repo`
  (push access) rather than reporting it unreachable. The upstream repository
  is read-only, always.
- Upstream API actions need the author's authorization for each one. They do
  **not** need a special session: from a local session the forge CLI acts on
  `oscardvs/zoteus` directly, on a `repo`-scoped token, with no push rights
  required — opening a PR from the fork and editing a PR you authored both
  work. Verified 2026-08-29 by editing PR #31's body. Always verify the result
  publicly (the issue/PR page) before recording it here.
- **Once authorized, execute — do not hand the author a URL to click.** The
  earlier note here said upstream actions "cannot run in a session bound to
  this repo — cross-owner repos do not attach", which describes a *remote*
  session's repo-attachment mechanism and was read as a blanket prohibition.
  Acting on it, an authorized PR was reduced to a pre-filled compare link for
  the author to open and a body for him to paste by hand — his paste then
  carried a two-space indent and CRLF into the public PR. Mechanical work the
  agent can do is the agent's (author, 2026-08-29). Where a capability really
  is absent, the sibling-session technique (issue #26, 2026-08-28:
  `create_session` with the upstream repo as `source_url`, handed the exact
  text and nothing else) remains the fallback — but probe the direct route
  first.
