# AGENTS.md — how to work in this repo

Work tracking for the search redesign of zoteus (an MCP server over a local
Zotero library). This repo holds documents, tickets, and a measurement
harness — the TypeScript under discussion lives upstream at `oscardvs/zoteus`
and in the author's fork, not here.

## The document set

This file owns workflow conventions alone, with its scoped extensions under
`.claude/`: project state, measurements, requirements, and history live in the
documents that own them. The table says what each is for; what an agent must do
differently in each is `.claude/rules/documents.md`, which loads when you touch
one of them.

| Document or directory | Role |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Instructions and workflow conventions for agents; owns no project state |
| [`.claude/rules/`](.claude/rules/), [`.claude/skills/`](.claude/skills/) | `AGENTS.md`'s conventions scoped out of every session: a rule loads when its `paths:` are touched, a skill when invoked |
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
| [`conception/`](conception/) | Thinking before ratification: scoping briefs, design explorations, proposal ideas. Owns no promise and no number — what survives review leaves here for `SPEC.md` or a ticket |
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
  entries with `erg log`, never by hand; why, and the fork-read incident, in
  `.claude/rules/tickets.md` (it loads only when a `tickets/` file is opened).
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
mirror error of reading a built ticket as unbuilt, are in
`.claude/rules/tickets.md`.

## Environment notes

- Upstream movement, catch-up and re-baseline: the `upstream-catchup` skill.
  The harness's scoped notes (dependency sets, the model registry, probe
  lifecycle, the full-text plugin, where the corpora live) are
  `.claude/rules/bench.md`.
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
