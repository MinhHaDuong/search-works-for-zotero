# AGENTS.md — how to work in this repo

Work tracking for the search redesign of zoteus (an MCP server over a local
Zotero library). This repo holds documents, tickets, and a measurement
harness — the TypeScript under discussion lives upstream at `oscardvs/zoteus`
and in the author's fork, not here.

## The document set

This file owns workflow conventions alone: project state, measurements,
requirements, and history live in the documents that own them. The table says
what each is for; the rules under it say what an agent must do differently in
each.

| Document or directory | Role |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Instructions and workflow conventions for agents; owns no project state |
| [`SPEC.md`](SPEC.md) | What the system promises, what the world imposes, how it answers both, the shared vocabulary, and where it can leak |
| [`DECISIONS.md`](DECISIONS.md) | Append-only record of ratified choices and later vetoes |
| [`README.md`](README.md) | The public landing page: the proposition, and where each promise stands at the reviewed baseline |
| [`verification/FIELD-REVIEW.md`](verification/FIELD-REVIEW.md) | Survey of prior art: what others have built, and what is borrowable — a dated snapshot, not a live tracker |
| [`GOVERNANCE.md`](GOVERNANCE.md) | How this repository conducts itself upstream: the bounds on our own conduct |
| [`SYNC.md`](SYNC.md) | Live account of Zotero and zoteus upstream movement |
| [`STATE.md`](STATE.md) | Compact live operational handoff and pointers; owns no requirements, measurements, or history |
| [`tickets/`](tickets/) | Work train, tracked with [git-erg](https://github.com/MinhHaDuong/git-erg) |
| [`bench/`](bench/) | Executable probes and acceptance-harness work |
| [`bench/results/`](bench/results/) | Committed raw evidence behind reported figures |
| [`verification/`](verification/) | Reports that settle a factual question, and the probes that produced them |
| [`UPSTREAM`](UPSTREAM) | Machine-readable zoteus review baseline |

How authority passes between `SPEC.md`, `DECISIONS.md`,
`verification/FIELD-REVIEW.md`, `GOVERNANCE.md` and `README.md` — and why
`SPEC.md`'s own sections each keep their own organising principle — is stated
once, in `SPEC.md` §1. Read it there rather than here.

- **`DECISIONS.md` is append-only.** The author's rulings land there FIRST and
  `SPEC.md` is edited to match. Never edit a ratified entry. A narrow exception
  applies to a false factual statement proved by a reproducible measurement or
  authoritative source: stop first and trace the consequences through the
  design, requirements, tickets, evidence, and implementation. Correct the
  fact, propagate only forced factual consequences, and record the evidence
  and consequence analysis in `DECISIONS.md` in the same change, without
  waiting for ratification. Requirements, thresholds, design choices,
  interpretations, mechanism substitutions, and choices among consequences
  are decisions, not factual corrections, and still require the ruling first.
- **`SPEC.md` owns every design number**, and nothing else carries one: gate
  thresholds §5.2.8, experiment decision rules §5.3, budgets §5.2.9. §2
  Terminology and §6 Security own none and point at the owner instead, and §6
  discloses rather than decides, so closing a gap it names is a ruling in
  `DECISIONS.md` first and a requirement in §3 second. The header date is the
  version; bump it whenever the document changes substantively, and leave
  `Status: DRAFT` until the author himself declares otherwise. SPEC.md speaks
  only of the system: ruling provenance, ticket tracking and process narration
  belong in `DECISIONS.md`, the tickets, and this file. Handles are
  position-independent and outlive a section's renumbering — R1–R35
  requirements, C1–C4 constraints, D1–D11 resolved decisions, X1–X8
  experiments. Cite a handle on its own; cite a section as `SPEC.md §N.M`.
- **`README.md`'s standing is read, never computed.** It owns no threshold and
  no design number, its verdicts come from the upstream source, and
  `bench/check_progress.py` fails the build when the reviewed baseline moves
  past it. It is durable public status, not a live session handoff.
- **`STATE.md` stays under forty lines and stays pointer-only.** It owns no
  requirement, measurement, verdict, or history.
- **`verification/` is evidence, not authority.** A report is cited by path
  from the ticket it serves and never becomes a source of truth: where it
  touches the design, the owning section of `SPEC.md` is the record. Commit
  reports there rather than leaving them in an agent worktree, because an
  uncommitted artifact dies with the worktree and the report about the work is
  not the work.
- **`fork/` must never contain a `tickets/` directory**, or it shows up in a
  diff sent upstream.
- **Superseded documents are DELETED, not archived in the tree** — git is the
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
  that already exists. It also gives the verdict a
  timestamped existence independent of any lane's report, which can be compared
  against the merge time. The residual limit stands: with one account there is
  still no proof of authorship, so what this buys is that a verdict must exist
  on the page before a merge, not that the page establishes who wrote it.
- **A lane does not merge a pull request another lane is gating.** The gate's
  owner is whoever opened it, and ownership is released by that lane's verdict,
  not by elapsed time. A gate that looks stalled is a lane to ask, not a queue
  to step around.
- **When these rules block a merge, say what is missing and stop.** An unmerged
  branch with a named blocker is a working state; a merged one with an invented
  verdict is not recoverable.

Who may press merge once a verdict is recorded — the lane that wrote the change,
or a second party — is not settled here. The question is in `DECISIONS.md`.

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
- Zotero's local API cannot request extraction, and Zotero 10 has no bulk
  reindex button, so the author's Zotero carries a small plugin of ours,
  `bench/zotero-fulltext-plugin/`: two endpoints on Zotero's own server that
  reindex named attachments in full and report their state; the client is
  `bench/zotero_fulltext.py`. Group-library items answer only under the group
  path of the local API (`/api/groups/<id>/…`), and the plugin resolves keys
  across libraries so callers need not know which. The page cap was lifted
  and the X5 arm documents re-extracted in full on 2026-09-02 (ticket 0025's
  log); every other cache still holds at most 100 pages, so census numbers
  measured before that date stand.
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
