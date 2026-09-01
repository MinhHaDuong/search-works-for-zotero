# CLAUDE.md — how to work in this repo

Work tracking for the search redesign of zoteus (an MCP server over a local
Zotero library). This repo holds documents, tickets, and a measurement
harness — the TypeScript under discussion lives upstream at `oscardvs/zoteus`
and in the author's fork, not here.

## The document set, and who is authoritative for what

The specification is one document, `SPEC.md`, at the top level, in RFC
section order — merged 2026-09-01 (`DECISIONS.md`) from the five documents
this section used to list separately, and their subdirectory dissolved in the
same change. What changes week to week — `STATE.md`, `SYNC.md` — stays at the top
level too, as do `README.md` and this file.

- `README.md` — the chain's entry point, and this repository's landing page
  on the forge, folded together 2026-09-01. Owns one thing nothing else
  does: where each of the twenty-four requirements stands, on two axes —
  designed, and delivered on stock upstream at the reviewed baseline — plus
  an `evidence` column saying how each verdict was established. It owns no
  threshold and no design number; the standing is read from the upstream
  source, never computed, and `bench/check_progress.py` fails the build when
  the reviewed baseline moves past it, reading only its own standing window
  (`## Where the promises stand` through `## How work leaves this
  repository`) rather than the whole landing page. It also owns the goals
  ladder's five rosters — which requirements sit on each rung, with the
  level each is decided at and the address where its work lives — checked
  against the rulings in `DECISIONS.md` rather than against itself. The
  ladder is a partition and the number is the build order, so the guard
  fails on a requirement sitting on no rung, on two, or on a gap in the
  numbering; the order itself is `SPEC.md` §3's last section. The work that
  earns those verdicts is tickets 0026, 0029 and 0032; the tally is the
  tracker.
- `SPEC.md` — the specification, RFC-ordered, carrying a PEP-style header
  (`Status: DRAFT`, `Author: Minh Ha-Duong (CNRS)`, `Date: 2026-09-01`)
  directly under its title. The date is the version — there is no separate
  version number, and the convention is to bump it whenever the document
  changes substantively. Status stays `DRAFT` until the author himself
  declares otherwise. §1 Introduction (what zoteus is, and the section map).
  §2 Terminology, the glossary, alphabetical in three marked buckets (ours,
  inherited from Zotero, inherited from SQLite) — owns no design number and
  settles no open question, it points at the owner instead, and any digit in
  it that is not an address is drift (the rule outlived its guard, retired
  2026-09-01). §3 Requirements and §4 Constraints — the sheet, materialized,
  stable. §5 Design, the current design ("The Instrumented Ledger") — owns
  every design number: gate thresholds §5.2.8, experiment decision rules
  §5.3, budgets §5.2.9. §6 Security Considerations — what the system holds,
  where it can leak, and what the design currently says about each point; it
  describes and discloses, it decides nothing, so closing a gap it names is a
  ruling in `DECISIONS.md` and then a requirement in §3. SPEC.md speaks only
  of the system (ruled 2026-09-01, `DECISIONS.md`): ruling provenance, ticket
  tracking and document/process narration live in `DECISIONS.md`, the
  tickets, and this file, never restated there undated. Handles are
  position-independent and outlive a section's own renumbering: R1–R35 name
  requirements, C1–C4 constraints, D1–D11 resolved decisions, X1–X8
  experiments. Cite a handle on its own; cite a section address as `SPEC.md
  §N.M`.
- `DECISIONS.md` — append-only ratification ledger, at the top level since
  2026-09-01. The author's rulings land here FIRST; `SPEC.md` is edited to
  match. Owns the record of every ruling, technical and process alike, and
  the awaiting-ratification questions. Never edit a ratified entry.
- `GOVERNANCE.md` — how this repo conducts itself upstream: the bounds on our
  own conduct, going forward. It owns the rules; the ledger keeps the rulings
  that made them, and `SYNC.md` keeps the live counts. Split ratified
  2026-08-29.
- Tickets `0014`–`0037` (`tickets/`, git-erg) — the executable work train;
  authoritative for each item's scope, evidence, and live state.
  `GOVERNANCE.md`'s increment train carries only the ordering.
- `verification/FIELD-REVIEW.md` — the survey of prior art: what other people have already
  built for Zotero AI retrieval, what it teaches, and what is
  license-compatible to borrow. Authoritative for the inventory and for each
  project's observed state at its stated observation date. Owns no design
  number, no requirement, and no threshold; where it touches our design it
  points at the owning section of `SPEC.md`. A dated snapshot, not a live tracker, which is why it sits in
  `verification/` as evidence rather than in the chain as spec (ruled
  2026-08-31).
- `SYNC.md` — upstream tracking (maintainer behavior, PR/issue status).
  `STATE.md` — the prototype phase's measurement record; mostly frozen.
  `RUNBOOK.md` self-sunset 2026-08-30 once its measurements executed; its
  durable state lives in ticket 0014, ticket 0016, ticket 0024, ticket 0025
  and `SYNC.md`.
- The cycle-2 panel's verbatim session record (memos, critiques, the political
  and implementation reviews) is GONE. It lived only in the history `main` was
  re-rooted away from on 2026-08-29, and 2026-08-31's ruling abandoned it
  (`DECISIONS.md`). It was never authoritative and `SPEC.md`'s design section
  was always the record; it is now the only one. Cite it for nothing.
- `verification/` — evidence, not authority. Reports that settle a factual
  question (a platform probe, an acceptance dossier, a voice measurement) and
  the scripts under `verification/probes/` that produced them. A report is
  cited by path from the ticket it serves and never becomes a source of
  truth: where it touches the design, the owning section of `SPEC.md` is the
  record. Reports live here rather than in an agent worktree because an
  uncommitted artifact dies with the worktree — the report about the work is
  not the work.
- Superseded documents are DELETED, not archived in the tree — git is the
  archive. Do not create `history/` directories or versioned doc copies. The
  merge of the five prior specification documents into `SPEC.md` (2026-09-01,
  `DECISIONS.md`) followed exactly this rule — five files gone, `git log` is
  where their history lives.

## Conventions

- `make check` must be green before any commit: ruff, the figure guard
  (`bench/check_figures.py`), the model-registry guard
  (`bench/check_models.py`), the names guard (`bench/check_names.py`), the
  progress guard (`bench/check_progress.py`), pytest. This list is prose and
  drifts: the Makefile's `check` target is what actually runs — it gained two
  guards before this sentence did, and five retired on 2026-09-01 on their
  record of zero catches (their rules bind as before, kept by the reader).
  The figure guard is load-bearing —
  every measurement quoted in prose is declared there with an anchor; when
  you quote a number from `bench/results/`, declare it; when you re-measure,
  the guard tells you every prose site to update.
- What the gate needs to run at all is declared in `requirements-check.txt`
  (`ruff`, `pytest`, `numpy`); what a measurement driver needs on top of it is
  `requirements-drivers.txt`, so nobody installs a model runtime to run a lint
  gate. `bench/check_deps.py` runs FIRST in `make check` and names a missing
  package before any guard prints, because the failure it was filed for arrived
  after eight guards had printed success and reads as green to a session that
  looks at the tail. A remote session installs the gate's set by itself:
  `.claude/hooks/session-start.sh`. Ticket 0498.
- One model name, one place: `bench/models.json`, and the same for the two things
  that decide what a measurement means. Every driver names a model by registry id
  and resolves it — plus its `pooling` mode and its `input_template` prefixes —
  through `bench/registry.mjs` or `bench/registry.py`, which also decide whether the
  run wants the ONNX mirror or the author's own repository. Adding a model means
  adding a record. `bench/check_models.py` fails on any of the three written
  literally anywhere else under `bench/`: a model id, including one it has never
  heard of; a pooling mode; a declared input template. It also fails on a candidate
  missing the `pooling` / `pooling_source` pair. Read pooling off the model's own
  `1_Pooling/config.json` — never infer it from a sibling: four of six candidates
  are `cls` where every driver had hardcoded `mean`, and a wrong pooling degrades
  retrieval silently, so it reads as the model being worse rather than as a bug.
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
it. No guard enforces the separation any more (retired 2026-09-01) and nothing
ever enforced it on the text you send — so read what you send, as sent.

## Environment notes

- `UPSTREAM` owns the reviewed upstream SHA and repository URLs.
  `make upstream-status` detects upstream movement — one bit, and it is not in
  `make check`, so nothing tells you upstream moved unless you ask.
  `make upstream-catchup` answers the other half, and answers it as a **verdict**
  rather than as reading: QUIET when nothing under `src/features/search/` moved
  and the index schema is unchanged, TOUCHED with the detail when something did.
  `--full` adds the releases, merges, pull refs and branches. It fetches a
  git-ignored bare mirror at `upstream.git/`, so it costs a round trip after the
  first run.

  Two properties matter more than the output. **Its cost is flat in the number of
  releases** — it spans `reviewed..main` whatever the distance, so ten releases
  cost exactly what one costs. Upstream ships several times a day, and nothing
  here requires reading each one: you catch up per DECISION (before filing,
  before measuring, before claiming currency), never per release. And it never
  reports whether an issue is open — that state is the forge's, it changes
  without a commit, and a copy here would be stale on arrival; the report ends
  with the query URL instead. `make upstream-checkout` recreates the
  git-ignored `fork/` at the reviewed SHA with both `origin` and `upstream`
  remotes. Do not overwrite an existing checkout.
- The measurement corpora are NOT in this repo: real vectors, the 477k index,
  and the 44,9 MB extraction live on the author's machine; `bench/results/`
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
