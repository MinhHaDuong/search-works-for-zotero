# AGENTS.md — how to work in this repo

Work tracking for the search redesign of zoteus (an MCP server over a local
Zotero library). This repo holds documents, tickets, and a measurement
harness — the TypeScript under discussion lives upstream at `oscardvs/zoteus`
and in the author's fork, not here.

## The document set, and who is authoritative for what

This file owns workflow conventions only. Project state, measurements,
requirements, and history live in the documents below.

- `README.md` — the chain's entry point and this repository's landing page on
  the forge. Owns one thing nothing else does: where each requirement stands,
  on two axes (designed, and delivered on stock upstream at the reviewed
  baseline), with an `evidence` column saying how each verdict was
  established. It also owns the goals ladder's five rosters — which
  requirements sit on each rung, the level each is decided at, and the address
  where its work lives — checked against the rulings in `DECISIONS.md` rather
  than against itself. It owns no threshold and no design number: standing is
  read from the upstream source, never computed, and `bench/check_progress.py`
  fails the build when the reviewed baseline moves past it. Durable public
  status, not a live session handoff.
- `SPEC.md` — the specification, RFC-ordered, under a PEP-style header. The
  date is the version; bump it whenever the document changes substantively.
  `Status: DRAFT` until the author himself declares otherwise. §1
  Introduction, §2 Terminology, §3 Requirements and §4 Constraints (the sheet,
  materialized and stable), §5 Design, §6 Security Considerations. §5 owns
  every design number: gate thresholds §5.2.8, experiment decision rules §5.3,
  budgets §5.2.9. §2 and §6 own none and point at the owner instead; §6
  discloses rather than decides, so closing a gap it names is a ruling in
  `DECISIONS.md` first and a requirement in §3 second. SPEC.md speaks only of
  the system: ruling provenance, ticket tracking and process narration live in
  `DECISIONS.md`, the tickets, and this file, never restated there undated.
  Handles are position-independent and outlive a section's renumbering —
  R1–R35 requirements, C1–C4 constraints, D1–D11 resolved decisions, X1–X8
  experiments. Cite a handle on its own; cite a section as `SPEC.md §N.M`.
- `DECISIONS.md` — append-only ratification ledger. The author's rulings land
  here FIRST; `SPEC.md` is edited to match. Owns the record of every ruling,
  technical and process alike, and the awaiting-ratification questions. Never
  edit a ratified entry.
- `GOVERNANCE.md` — how this repo conducts itself upstream: the bounds on our
  own conduct, going forward. It owns the rules; the ledger keeps the rulings
  that made them, and `SYNC.md` keeps the live counts.
- `SYNC.md` — upstream tracking: maintainer behavior, PR and issue status.
- `STATE.md` — the compact live operational handoff, held under forty lines
  and pointer-only. Owns no requirement, measurement, verdict, or history.
- Tickets (`tickets/`, git-erg) — the executable work train, authoritative for
  each item's scope, evidence, and live state. `GOVERNANCE.md`'s increment
  train carries only the ordering.
- `verification/` — evidence, not authority. Reports that settle a factual
  question (a platform probe, an acceptance dossier, a voice measurement) and
  the scripts under `verification/probes/` that produced them. A report is
  cited by path from the ticket it serves and never becomes a source of truth:
  where it touches the design, the owning section of `SPEC.md` is the record.
  Reports are committed here rather than left in an agent worktree, because an
  uncommitted artifact dies with the worktree — the report about the work is
  not the work. `verification/FIELD-REVIEW.md` is the prior-art survey:
  authoritative for the inventory and for each project's observed state at its
  stated observation date, and a dated snapshot rather than a live tracker.
- Superseded documents are DELETED, not archived in the tree — git is the
  archive. Do not create `history/` directories or versioned doc copies.

## Conventions

- **`make check` green before any commit.** The Makefile's `check` target is
  what actually runs; any list of guards in prose drifts. The figure guard
  (`bench/check_figures.py`) is load-bearing: every measurement quoted in
  prose is declared there with an anchor, so when you quote a number from
  `bench/results/`, declare it, and when you re-measure, the guard names every
  prose site to update.
- **Stamp ticket logs with `erg log`**, which reads the real clock. A
  hand-typed stamp is how log entries came to name times that had not
  happened, and `bench/check_ticket_logs.py` now fails on one stamped after
  the commit that wrote it. Out-of-order logs are fine and are not checked:
  parallel sessions merge into one log.
- **Two dependency sets.** `requirements-check.txt` is what the gate needs to
  run at all (`ruff`, `pytest`, `numpy`); `requirements-drivers.txt` is what a
  measurement driver needs on top, so nobody installs a model runtime to run a
  lint gate. `bench/check_deps.py` runs FIRST in `make check` and names a
  missing package before any guard prints, so a failure cannot hide in the
  tail of a green-looking run.
- **One model name, one place:** `bench/models.json`. Every driver names a
  model by registry id and resolves it — with its `pooling` mode and its
  `input_template` prefixes — through `bench/registry.mjs` or
  `bench/registry.py`, which also decide whether the run wants the ONNX mirror
  or the author's own repository. Adding a model means adding a record.
  `bench/check_models.py` fails on a model id, a pooling mode, or a declared
  input template written literally anywhere else under `bench/`, and on a
  candidate missing the `pooling` / `pooling_source` pair. Read pooling off the
  model's own `1_Pooling/config.json` and never infer it from a sibling: a
  wrong pooling degrades retrieval silently, so it reads as the model being
  worse rather than as a bug.
- **Numbers use decimal comma and space thousands** ("2 084,9 MiB",
  "360 811") — the guard cannot match US formatting.
- **Both numbers, always:** any external memory claim carries the honest pair
  (e.g. 45x and 6,8x) — see README.
- **Tickets:** `./tickets/erg` (check / ready / new / close / log), rules in
  `tickets/AGENTS.md`. `erg check` must pass, `erg ready` is the work queue,
  and sequencing is machine-readable `Blocked-by`, never prose.
- **One statement per fact.** Thresholds, rules, and open questions live in
  their owning document above, and everywhere else is a pointer. Duplicated
  numbers drift — this repo's most expensive recurring defect.

## Upstream relations

Binding, and stated once in `GOVERNANCE.md`: the volume bound, the budget, the
form each item takes, the sunset, the harness transfer, the fork's end state.
Read it before filing anything upstream. What remains live against those bounds
is `SYNC.md`'s, never restated elsewhere.

The one line worth repeating here, because it governs every outward action
rather than a filing decision: never put this repo's internal governance or its
reading of the maintainer into upstream text. The repo is public and he reads
it. No guard enforces the separation, and nothing ever enforced it on the text
you send — so read what you send, as sent.

## Environment notes

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
  `make upstream-checkout` recreates the git-ignored `fork/` at the reviewed
  SHA with both `origin` and `upstream` remotes. Do not overwrite an existing
  checkout.
- The measurement corpora are NOT in this repo: real vectors, the 477k index,
  and the 44,9 MB extraction live on the author's machine, and `bench/results/`
  holds committed JSON summaries. Ticket 0025's substrate map says which
  experiments run where.
- The author's fork (`FORK_REPOSITORY` in `UPSTREAM`) is authorized for direct
  pushes from agent sessions; in a remote session attach it with `add_repo`
  rather than reporting it unreachable. The upstream repository is read-only,
  always.
- Upstream API actions need the author's authorization for each one, and need
  no special session: from a local session the forge CLI acts on
  `oscardvs/zoteus` directly on a `repo`-scoped token, with no push rights
  required — opening a PR from the fork and editing a PR you authored both
  work. Always verify the result publicly, on the issue or PR page, before
  recording it here.
- **Once authorized, execute.** Do not hand the author a URL to click or a
  body to paste: mechanical work the agent can do is the agent's.
