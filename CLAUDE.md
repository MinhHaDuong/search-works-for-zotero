# CLAUDE.md — how to work in this repo

Work tracking for the search redesign of zoteus (an MCP server over a local
Zotero library). This repo holds documents, tickets, and a measurement
harness — the TypeScript under discussion lives upstream at `oscardvs/zoteus`
and in the author's fork, not here.

## The document set, and who is authoritative for what

- `REQUIREMENTS.md` / `CONSTRAINTS.md` — the sheet, materialized. Stable.
- `DESIGN.md` — the current design ("The Instrumented Ledger", cycle 2). Owns
  every design number: gate thresholds (§2.8), experiment decision rules
  (§3), budgets (§2.9).
- `DECISIONS.md` — append-only ratification ledger. The author's rulings land
  here FIRST; the other documents are edited to match. Owns the process
  bounds (PR volume cap, sunset rule) and the awaiting-ratification
  questions. Never edit a ratified entry.
- Tickets `0014`–`0037` (`tickets/`, git-erg) — the executable work train;
  authoritative for each item's scope, evidence, and live state. `DESIGN.md
  §4` carries only the ordering.
- `SYNC.md` — upstream tracking (maintainer behavior, PR/issue status).
  `STATE.md` — the prototype phase's measurement record; mostly frozen.
- `panel/cycle2/` — verbatim session record (memos, critiques, the political
  and implementation reviews). Archive: never edit, never treat as
  authoritative; where it disagrees with DESIGN.md, DESIGN.md is the record.
- Superseded documents are DELETED, not archived in the tree — git is the
  archive. Do not create `history/` directories or versioned doc copies.

## Conventions

- `make check` must be green before any commit: ruff, the figure guard
  (`bench/check_figures.py`), pytest. The figure guard is load-bearing —
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

## Upstream relations (binding, ratified in DECISIONS.md)

At most two upstream PRs in flight, ever; the contained-PR budget beyond the
merged #19/#20 is six ratified, five live (DECISIONS.md 2026-08-27);
design-sized asks go as issues the maintainer builds himself (the
measured asymmetry, SYNC.md); a three-week sunset on unaddressed
items; the acceptance harness is a one-time transfer. Never put this repo's
internal governance or strategy-about-the-maintainer into upstream text — the
repo is public and he reads it.

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
- Upstream API actions (filing an issue; the author authorizes each one) cannot
  run in a session bound to this repo — cross-owner repos do not attach. The
  working technique (issue #26, 2026-08-28): spawn a dedicated sibling session
  with the upstream repository as its initial source (`create_session` with
  `source_url`), hand it the exact text and nothing else to do, then verify the
  result publicly (the issue/PR page) before recording it here.
