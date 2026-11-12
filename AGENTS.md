# AGENTS.md — how to work in this repo

Work tracking for the search redesign of zoteus (an MCP server over a local
Zotero library). This repo holds documents, tickets, and a measurement
harness — the TypeScript under discussion lives upstream at `oscardvs/zoteus`
and in the author's fork, not here.

## The document set

This file owns workflow conventions alone: project state, measurements,
requirements, and history live in the documents that own them. The table says
what each is for; what an agent must do differently in each is
§ Path-scoped rules below.

| Document or directory | Role |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Instructions and workflow conventions for agents; owns no project state |
| [`.claude/skills/`](.claude/skills/) | `AGENTS.md`'s on-demand procedures, loaded when invoked |
| [`SPEC.md`](SPEC.md) | What the system promises, what the world imposes, how it answers both, the shared vocabulary, and where it can leak |
| [`DECISIONS.md`](DECISIONS.md) | Append-only record of ratified choices and later vetoes |
| [`README.md`](README.md) | Public landing page: proposition and the three deliverables' compact status |
| [`verification/FIELD-REVIEW.md`](verification/FIELD-REVIEW.md) | Survey of prior art: what others have built, and what is borrowable — a dated snapshot, not a live tracker |
| [`GOVERNANCE.md`](GOVERNANCE.md) | How this repository conducts itself upstream: the bounds on our own conduct |
| [`SYNC.md`](SYNC.md) | Live account of Zotero and zoteus upstream movement |
| [`STATE.md`](STATE.md) | Compact live operational handoff and pointers; owns no requirements, measurements, or history |
| [`tickets/`](tickets/) | Work train, tracked with [git-erg](https://github.com/MinhHaDuong/git-erg) |
| [`bench/`](bench/) | Executable probes, one-off measurement scripts, and acceptance-harness work |
| [`bench/results/`](bench/results/) | Committed raw evidence behind reported figures |
| [`plugins/`](plugins/) | Zotero plugins this repo ships: source with its own manifest, version and install lifecycle — a probe belongs in `bench/` |
| [`verification/`](verification/) | Reports that settle a factual question, and the probes that produced them |
| [`design/`](design/) | Thinking before ratification: scoping briefs, design explorations, proposal ideas. Owns no promise and no number — what survives review leaves here for `SPEC.md` or a ticket |
| [`UPSTREAM`](UPSTREAM) | Machine-readable zoteus review baseline |

How authority passes between `SPEC.md`, `DECISIONS.md`,
`verification/FIELD-REVIEW.md`, `GOVERNANCE.md` and `README.md` — and why
`SPEC.md`'s own sections each keep their own organising principle — is stated
once, in `SPEC.md` §1. Read it there rather than here.

- **Superseded documents are DELETED, not archived in the tree** — git is the
  archive. Do not create `history/` directories or versioned doc copies.

## Conventions

- **Run `make check-diff` before any commit and quote its `selected:` and
  `skipped:` lines in the PR description.** The tracked `.idh-checks.json`
  maps documentation, evidence, and tickets to the targets they can affect;
  SPEC and plugin documentation add the model and test gates, and plugin
  changes add the sitter gates. Any unmapped path runs the full
  `make check`. A scoped pass does not claim that the full gate passed. The
  Makefile's targets are what actually run; any list of guards in prose drifts.
  The 2026-09-23 cold full-gate pilot took 889.80 seconds; the bounded raid
  allowance is declared in `.idh-checks.json`. The figure guard
  (`bench/check_figures.py`) is load-bearing: every measurement quoted in
  prose is declared there with an anchor, so when you quote a number from
  `bench/results/`, declare it, and when you re-measure, the guard names every
  prose site to update.
- **Numbers use decimal comma and space thousands** ("2 084,9 MiB",
  "360 811") — the guard cannot match US formatting.
- **Both numbers, always:** any external memory claim carries the honest pair
  (e.g. 45x and 6,8x) — see README.
- **Tickets:** `./tickets/erg` (check / ready / new / close / log), rules in
  `tickets/AGENTS.md`. `erg check` must pass, `erg ready` is the work queue,
  and sequencing is machine-readable `Blocked-by`, never prose. Stamp log
  entries with `erg log`, never by hand (§ Path-scoped rules, `tickets/**`).
- **One statement per fact.** Thresholds, rules, and open questions live in
  their owning document above, and everywhere else is a pointer. Duplicated
  numbers drift — this repo's most expensive recurring defect.

## Merge authority

A verdict gates nothing unless the merge is serialized behind it. On 2026-09-02
five pull requests merged carrying no review verdict on their own pages, while
a sixth of the same evening (#218) shows what a recorded one looks like — so the
channel existed and was simply not used.

- **A pull request merges only after a review verdict is recorded on the pull
  request itself.** On the page, where the next reader finds it — not in a
  session transcript, not in a report to whoever launched the lane. A merge with
  no verdict on the page is out of order however good the change is. The absence
  is detectable afterwards, and reading the six pages of that evening is exactly
  how the five were found; what no later reading can settle is whether a review
  happened and went unrecorded or never happened at all. That irrecoverability
  is the reason for the rule.
- **Quote a verdict as received.** Relay the reviewer's own words and its own
  verdict token. Never paraphrase one into an approval, never fold several
  reviewers into a verdict none of them wrote, and never write a verdict on
  behalf of a reviewer that has not spoken.
- **A reviewer that has not reported leaves the pull request BLOCKED**, never
  approved and never inferred. Silence is the absence of a verdict, not the
  presence of a favourable one. A lane that cannot obtain a verdict says so and
  leaves the branch open.
- **Never attribute to a reviewer a finding you observed yourself.** Report it
  under your own name. An observation laundered through a reviewer's name is a
  fabricated verdict even when the observation is correct — and a fabricated
  verdict costs more than the finding is worth, because it spends the one thing
  a verdict is for.
- **A reviewer posts its own verdict to the pull-request page, and a lead
  waiting on a verdict polls the page rather than a notification.** Quoting a
  verdict as received, and refusing to launder your own finding through a
  reviewer's name, are the two rules aimed most directly at the incident and the
  two nothing can check afterwards, because one account authors every artifact
  on this forge: a comment reporting that a reviewer said APPROVED reads later
  exactly like one the reviewer wrote. This clause is worth more than either
  rule it patches. It closes the routing defect behind the incident, since a
  reviewer subagent's completion notice reaches the session that launched it and
  nowhere else, so a lead waiting elsewhere can wait indefinitely on a verdict
  that already exists. It also gives the verdict a timestamped existence
  independent of any lane's report, which can be compared against the merge
  time. The residual limit stands: with one account there is
  still no proof of authorship, so what this buys is that a verdict must exist
  on the page before a merge, not that the page establishes who wrote it.
- **A lane does not merge a pull request another lane is gating.** The gate's
  owner is whoever opened it, and ownership is released by that lane's verdict,
  not by elapsed time. A gate that looks stalled is a lane to ask, not a queue
  to step around.
- **When these rules block a merge, say what is missing and stop.** An unmerged
  branch with a named blocker is a working state; a merged one with an invented
  verdict is not recoverable.
- **A session may merge its own pull request once `/verify-gate` has
  returned APPROVED** and that verdict is recorded on the page (ruled
  2026-09-24, superseding 2026-09-03's "a lane does not press merge"; the
  ruling is one entry of `DECISIONS.md`). Before merging, the pull request is
  based on the current `main`, with gates measured **at that base** and quoted
  on the page. Under `/raid` the orchestrator merges, as the coordinator below.
  A lane dispatched by a coordinator that is still live hands its open pull
  request up rather than racing it.
- **The coordinator merges as pull requests arrive, not in a batched pass.** A
  finished lane does not queue behind an unfinished one, and overnight that is
  the difference between a lane's work landing and a lane's work waiting for
  someone to wake up. The review this repository has instead of continuous
  integration is the merge itself: `make check-diff` runs where a lane runs it, so
  the coordinator reads the gates the page quotes rather than re-running them.
- **A merge moves every other open branch's base, so it is announced.** This is
  the cost of merging as they arrive, and it falls on the coordinator to pay:
  tell the live lanes that `main` has moved. Each one re-merges it, re-runs
  `make check-diff` at the new base, and re-quotes `selected:` and `skipped:`
  on its own page. A gate reading is true only of the base it was taken at —
  an unannounced merge turns
  a green page stale without touching it, and the page still reads green.

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

Before filing a ticket that specifies new code, read the fork's `src/` and
`SYNC.md`'s upstream rows: the implementation may already exist. Why, and the
mirror error of reading a built ticket as unbuilt: § Path-scoped rules,
`tickets/**`.

## Environment notes

- Upstream movement, catch-up and re-baseline: the `upstream-catchup` skill.
  The harness's notes (dependency sets, the model registry, probe lifecycle,
  the full-text plugin, where the corpora live): § Path-scoped rules,
  `bench/**`.
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

## Path-scoped rules

Each subsection binds only when you edit the paths in its heading.

### `SPEC.md`, `DECISIONS.md`, `README.md`, `STATE.md`, `verification/**`, `fork/**`, `fork-*/**`

- **`DECISIONS.md` is append-only.** The author's rulings land there first and
  `SPEC.md` is edited to match; never edit a ratified entry. One exception: a
  false factual statement proved by a reproducible measurement or an
  authoritative source. Stop, trace the consequences through design,
  requirements, tickets, evidence and implementation, correct the fact,
  propagate only its forced consequences, and record the evidence and that
  analysis in `DECISIONS.md` in the same change. Requirements, thresholds,
  design choices, interpretations, mechanism substitutions and choices among
  consequences are decisions, not facts: they still need the ruling first.
- **`SPEC.md` owns every design number**, and nothing else carries one: gate
  thresholds §5.2.8, the fixture contract's per-cell minima §5.2.10,
  experiment decision rules §5.3, budgets §5.2.9. §2 Terminology and §6
  Security own none and point at the owner; §6 discloses rather than decides,
  so closing a gap it names is a ruling in `DECISIONS.md` first and a
  requirement in §3 second. The header date is the version: bump it on every
  substantive change, and leave `Status: DRAFT` until the author declares
  otherwise. `SPEC.md` speaks only of the system; ruling provenance, ticket
  tracking and process narration go elsewhere. Handles (R requirements,
  C constraints, D resolved decisions, X experiments) outlive renumbering: cite
  a handle on its own, a section as `SPEC.md §N.M`.
- **`README.md` tracks deliverables, not the design process.** It names the
  formal specification, the Multilingual Menagerie and the verification bench,
  expanding only the unfinished ones, and carries no workflow procedure,
  design ledger, threshold, measurement history or per-requirement board.
- **`STATE.md` stays under forty lines and pointer-only.**
- **`verification/` is evidence, not authority.** A report is cited by path
  from the ticket it serves; where it touches the design, the owning `SPEC.md`
  section is the record. Commit reports there: an uncommitted one dies with
  its worktree.
- **`fork/` never contains a `tickets/` directory**, or it shows up in a diff
  sent upstream.

### `bench/**`, `verification/probes/**`, `requirements-check.txt`, `requirements-drivers.txt`

- **Two dependency sets.** `requirements-check.txt` is what the gate needs
  (`ruff`, `pytest`, `numpy`); `requirements-drivers.txt` is what a measurement
  driver adds, so nobody installs a model runtime to run a lint gate.
  `bench/check_deps.py` runs first in `make check` and names a missing package
  before any guard prints.
- **One model name, one place: `bench/models.json`.** Drivers name a model by
  registry id and resolve it — `pooling` mode, `input_template` prefixes, ONNX
  mirror or the author's own repository — through `bench/registry.mjs` or
  `bench/registry.py`; adding a model means adding a record.
  `bench/check_models.py` fails on a model id, pooling mode or input template
  written literally elsewhere under `bench/`, and on a candidate missing the
  `pooling` / `pooling_source` pair. Read pooling off the model's own
  `1_Pooling/config.json`, never from a sibling: a wrong pooling degrades
  retrieval silently and reads as a worse model, not a bug.
- **Throwaway probe state gets a lifecycle before it gets a path.** The
  acceptance runner allocates a fresh arena per run under
  `$ACCEPTANCE_ARENA/<date>/<time>-<check>` and keeps the three most recent
  runs per base (ticket 0720). Nothing else under `~/data` is ever swept, so a
  hand-made directory beside the run layout is invisible to every cleanup (on
  2026-09-03 one afternoon left five, 613 MB, each with its own model
  weights). Put an ad-hoc probe under a job's `tmp/` or inside the run layout;
  if it must live beside the arena, name it in the ticket or verification note
  that consumes it, with when it can go.
- **The full-text plugin.** Zotero's local API cannot request extraction and
  Zotero 10 has no bulk reindex, so the author's Zotero carries
  `bench/zotero-fulltext-plugin/`: two endpoints on Zotero's own server that
  reindex named attachments in full and report their state; the client is
  `bench/zotero_fulltext.py`. Group-library items answer only under the local
  API's group path (`/api/groups/<id>/…`); the plugin resolves keys across
  libraries. The page cap was lifted and the X5 arm documents re-extracted on
  2026-09-02 (ticket 0025's log); every other cache holds at most 100 pages,
  so census numbers measured before that date stand.
- **The measurement corpora are not in this repo.** Real vectors, the 477k
  index and the 44,9 MB extraction live on the author's machine;
  `bench/results/` holds committed JSON summaries. Ticket 0025's substrate map
  says which experiments run where.

### `tickets/**`

- **Stamp ticket logs with `erg log`**, which reads the real clock: hand-typed
  stamps named times that had not happened, and `bench/check_ticket_logs.py`
  fails on a stamp later than its commit. Out-of-order entries are fine:
  parallel sessions merge into one log.
- **Why the fork is read before filing new code** (§ Upstream relations): the
  code lives in a separate repository, so a null search here reads exactly
  like a real absence. On 2026-09-01 two of tracker 0557's children were filed
  for work shipped upstream in v1.10.0 on 2026-08-29: 0560 (embedded-TOC
  extraction, shipped as `extractPdfOutline`) and 0558 (attachment file
  access, `SYNC.md` issue #29). The mirror error — reporting built work as
  unbuilt, as seg/1 was the day after its fork branch was tested — is fixed by
  reading the ticket's own log, which carries branch, SHA and measurements.
