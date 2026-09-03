# The acceptance matrix — five targets, twelve clauses

Assembled 2026-09-03 on `doudou`, from four per-target artifacts plus one
in-flight column. The layer, its seven-verb interface and the four states it may
emit are SPEC.md §5.2.8; the adapter contract and the five-target roster are
DECISIONS.md's ratified entry of 2026-09-02.

**This is not a test suite.** Each cell is one MUST clause of one requirement,
asserted once, against one named target. A green is a green for that target and
for nothing else.

**Beaver's column was filled after assembly, from its own committed artifact**
(`../0586-beaver/acceptance.json`, same day; adapter merged in PR #237 and
verified in #269). Its five goal-1 clauses are measured; the seven goal-2
clauses read `not-measured` because `durability.py` landed after that run, not
because anything was undecided. Those five change the totals below and nothing
else in this document.

**Instrument health:** healthy — `assertions_never_seen_red` is empty in
`acceptance-fixtures.json` (16 fixtures × 12 assertions, 2026-09-03), and every one of
the twelve assertions was independently driven red by at least one fail-control,
so none has gone inert.

---

## The matrix

| Clause | Req | verb | zoteus | Zotero core #6012 | ZotSeek | 54yyyu/zotero-mcp | Beaver |
|---|---|---|---|---|---|---|---|
| R10-local-by-default | R10 | status | **pass** | not-offered | not-offered | not-run | not-offered |
| R10-no-egress | R10 | query | **FAIL** | not-staged | not-staged | **pass** | **FAIL** |
| R15-residue-inventory | R15 | install | **pass** | not-staged | not-staged | **pass** | **pass** |
| R15-model-cache-under-declared-roots | R15 | query | **pass** | not-offered | not-offered | not-run | not-offered |
| R15-uninstall-removes-declared-state | R15 | uninstall | not-offered | not-offered | not-offered | not-offered | **FAIL** |
| R22-pause-stops-background-work | R22 | pause | not-run | not-offered | not-offered | not-offered | not-measured |
| R22-pause-holds-across-restart | R22 | pause | not-run | not-offered | not-offered | not-offered | not-measured |
| R3-edit-recomputes-only-what-changed | R3 | status | not-run | not-offered | not-offered | not-run | not-measured |
| R3-identical-resync-recomputes-nothing | R3 | status | not-run | not-offered | not-offered | not-run | not-measured |
| R13-two-processes-both-answer | R13 | query | not-run | not-offered | not-offered | not-run | not-measured |
| R13-two-processes-do-not-duplicate-work | R13 | status | not-run | not-offered | not-offered | not-run | not-measured |
| R23-foreign-stamp-ends-up-serving | R23 | query | not-run | not-offered | not-offered | not-run | not-measured |

Per-column totals, and they close against each artifact's own `summary` block:

| Target | pass | fail | not-offered | not-run | not-staged | not-measured | artifact |
|---|---|---|---|---|---|---|---|
| zoteus 1.12.0 | 3 | 1 | 1 | 7 | 0 | 0 | `acceptance-zoteus.json` |
| Zotero core #6012 @19e7962 | 0 | 0 | 10 | 0 | 2 | 0 | `acceptance-zotero-core-6012.json` |
| ZotSeek 1.21.2 @f442f82 | 0 | 0 | 10 | 0 | 2 | 0 | `acceptance-zotseek.json` |
| zotero-mcp 0.11.0 @3cb3e2e | 2 | 0 | 3 | 7 | 0 | 0 | `acceptance-zotero-mcp.json` |
| Beaver 0.23.3 @`bec71e14` | 1 | 2 | 2 | 0 | 0 | 7 | `../0586-beaver/acceptance.json` |
| **60 cells** | **6** | **3** | **26** | **14** | **4** | **7** | |

Five cells of sixty are green. No cell is blank and no cell is inferred: each
traces to a `result` field in a named artifact, except Beaver's column, marked
in-flight because its adapter is being written right now under ticket 0586 and
was not touched here.

---

## Legend — the four non-green states are four different things

**`not-offered` — the target has no such surface.** Read from the adapter's own
`Declaration.unsupported`, which the assertion consults *before* it touches the
target. This is a statement about the target, carrying a written reason, and it
is frequently the finding rather than an obstacle to one. It is not a failure:
per SPEC.md §5.2.8 and the ratified contract, the harness will not simulate a
verb's effect to manufacture a verdict, and will not delete declared state on a
target's behalf to make an uninstall clause close.

**`not-run` — the harness looked and there was nothing to read.** The surface
exists, was exercised, and what came back carries nothing the clause can be
decided from: no `work.<stage>.<trigger>.<outcome>` counters, no hit list, no
embedding locality, no model in effect. The target was measured; the clause was
not decided. A green here would mean the harness could not look, which is why
the layer refuses to emit one.

**`not-staged` — the harness could not look at all.** The declaration gate
passed, the verb is offered, and execution stopped before the assertion could
run. All four such cells stopped at the same place: the assertion walks into
`with target.running():`, which launches a Zotero desktop host, and this session
was forbidden to launch one (a peer session's full-library index build owns the
local Zotero host and its port). No fact about the target was produced. This
state is *distinct from `not-offered` in both directions* — the surface is there
and was not exercised.

**`fail` — asserted against this target and falsified.** One cell. Its
instrument was proven working in the same run by two fail-controls.

**`in-flight` — not a harness state.** Beaver's adapter does not yet exist in a
runnable form for this matrix; its twelve cells are unmeasured, not undecided.

---

## Blocking analysis — 55 non-green cells, ranked by cause

### 1. The target declares the verb absent — 24 cells (44%)

| Target | absent verbs these clauses need | cells |
|---|---|---|
| Zotero core #6012 | status (4), query (3), pause (2), uninstall (1) | 10 |
| ZotSeek | status (4), query (3), pause (2), uninstall (1) | 10 |
| zotero-mcp | pause (2), uninstall (1) | 3 |
| zoteus | uninstall (1) | 1 |

These are **executed** verdicts, not skipped ones. For #6012 and ZotSeek the ten
assertion functions whose declaration guard sits before the lifecycle block were
called directly against real adapters, and each artifact carries a positive
control — the same ten functions returning `pass` against `stub-quiet` and
`not-offered` against `stub-verbless` — proving neither branch is stuck.

The recorded reasons are four architecturally different absences, and that
difference is the substance of this block:

- **#6012** computes the roster's most complete status object and no transport
  carries it — its own doc comment says it is for the preferences UI, and the
  local API answers 403 by default. Its pause control is real, durable and
  correct, reachable only from a GUI preferences pane. Its uninstall would be
  deleting the user's own library.
- **ZotSeek** *has* the surfaces — a `/zotseek/stats` endpoint, REST and MCP
  routes, a true `ADDON_UNINSTALL` cleanup hook, a pause button in a progress
  window — and gates every machine-reachable one behind an opt-in preference
  that ships false. Enabling it is a non-default option, which the contract
  forbids.
- **zotero-mcp** has no background work to pause at all — the architectural
  opposite, not a missing control.
- **zoteus** has no uninstall surface, and SPEC.md §5.2.7 says in as many words
  that its maintenance purge is not a stand-in the harness may call.

**What would unblock it:** nothing in this repository, and nothing the harness
may do — a patch, a non-default option, or access a user does not have are all
forbidden by the adapter contract, so *this block is the finding*. It moves only
if a target exposes the verb to a machine in its default configuration. Nearest
owner: the upstream-issue lane (ticket 0024 for the zoteus-side issues). Nothing
on the roster owns a filing against #6012, ZotSeek or zotero-mcp — a gap in the
ticket set, not in the matrix.

### 2. Beaver is unbuilt — 12 cells (22%)

**Unblock:** ticket 0586, in progress in another session. Untouched here by
instruction.

### 3. No target reports `work.<stage>.<trigger>.<outcome>` counters — 8 cells (15%)

zoteus 5 (R22 ×2, R3 ×2, R13-do-not-duplicate-work) and zotero-mcp 3 (R3 ×2,
R13-do-not-duplicate-work). SPEC.md §5.2.8's Counters paragraph is what these
clauses read; no target on the roster emits them, so five of the twelve clauses
have no readable substrate anywhere on the sheet. On zoteus the R22 pair degrades
one step further: its *positive control* — a second, never-stopped instance —
also reports no counters, so the harness could not even show that the change it
makes creates work.

**Unblock:** a target that emits the counters. **Ticket 0033** (scoped issue A:
ledger, freshness, counters) is the one that would put them in front of the
zoteus maintainer; its log of 2026-09-03 records that the two R22 assertions now
exist and are graded on the `done` half of exactly these counters.

### 4. The query answer carries no hit list and no report of what it matched — 4 cells (7%)

zoteus and zotero-mcp, on R13-two-processes-both-answer and
R23-foreign-stamp-ends-up-serving. Both targets answer; neither answer says what
was matched, so "both answered" and "ends up serving" have nothing to be read
from.

**Unblock:** a query result shape that reports its hits. **No ticket owns this.**
It is adjacent to ticket 0602's gap 2 (verbs that are the subject of no
assertion) but distinct: here the verb is asserted and its *return value* is too
thin. Worth filing.

### 5. This session may not launch a Zotero desktop host — 4 cells (7%)

#6012 and ZotSeek, on R10-no-egress and R15-residue-inventory. Both runners
verified this is the *only* obstacle: `acceptance.sandbox.choose()` returned the
`bwrap` mechanism with no reason-why-not on both targets, so R10's "no isolation
mechanism" not-run path is not what happened; and both proved no host started —
no `host.log` under any arena for #6012, while ZotSeek's guard tripped precisely
at the XPI sideload inside `running()`, which is that report's own positive
control. No traffic reached 127.0.0.1:23119 from either.

**Unblock:** permission to start a host, plus an Xvfb display. That is all —
staging is complete on both targets and each artifact carries the exact command.
No ticket owns it, because it is a session-scheduling constraint rather than a
defect: the peer's full-library index build owns the local Zotero host today.

### 6. The target reports no embedding locality — 1 cell (2%)

zotero-mcp, R10-local-by-default. `zotero_mcp.status()` returns no embedding key,
so locality is `None` and the assertion takes the not-run branch at
`assertions.py:332`.

**Unblock:** an adapter that can answer, or a target that says. Note the trap in
**ticket 0602 gap 1**: one line below, `assertions.py:338` scores a target that
honestly answers `"none"` as **fail** against a clause reading "the embedder is
local". zotero-mcp sits on the ignorant side of that asymmetry today.

### 7. No model in effect — 1 cell (2%)

zotero-mcp, R15-model-cache-under-declared-roots. The semantic extra is not
installed in the venv and the README's documented install command does not pull
it, so no weights were exercised and nothing was decided about where they land.
**Unblock:** none available under the contract — installing the extra by hand is
a non-default option. **Unowned.**

### 8. One real red — 1 cell (2%)

**zoteus, R10-no-egress.** Four `connect` calls to the resolver at 127.0.0.53:53
during a default-configuration run under `--unshare-net`; off-machine attempts
zero. The clause's `falsified_by` names "any connection attempted to an address
off this machine, **or any name lookup**", and the detector note explains why the
second detector must exist: inside a no-route namespace a hostname attempt dies
at resolution and leaves no off-machine connect at all, so a detector without it
reports a false green. Both controls fired — the net-shared and isolated arms
each recorded an off-machine attempt — so this is a finding, not a could-not-look.

**Unblock:** not a blocker. It is the matrix's one result that needs carrying
upstream, and **no ticket owns it.** Scope it honestly when filing: it says a
default-configuration run performs name lookups, not that library text left the
machine.

---

## What this matrix does not establish

**Two of five targets were never executed end to end, and a third was never
built.** `bench/acceptance/run.py` has never been run against Zotero core #6012
or against ZotSeek. Their twenty `not-offered` cells are real executed readings
of their declarations — their positive controls prove that much — but every cell
that would have observed *runtime behaviour* is `not-staged`. Nothing in this
matrix says how either target behaves. Beaver contributes nothing at all, and it
is the one target the roster adopted precisely to show R10's consequence in a
real product whose normal configuration attempts egress; the only egress evidence
here is one fail-control pair and one red on zoteus.

**Four of the five greens are thin, by their own runners' admission.**

- zotero-mcp `R15-residue-inventory` is **vacuous by construction, and now
  measured to be so**: the adapter ignores its arena argument, `created_count` is
  0, all fourteen per-assertion arena directories were empty afterwards, and the
  target wrote into the sandbox `HOME` instead — into two of its declared roots.
  The same run recorded that `install()` is not idempotent (uv exited 2, "a
  virtual environment already exists"), so the install event graded here was a
  no-op.
- zotero-mcp `R10-no-egress` is a genuine zero with a working instrument, but
  over a thin path: `install()` inside the sandbox did nothing at all (read-only
  filesystem, uv could not write its cache), and the driven query short-circuited
  before constructing any client because the semantic extra is absent. Zero
  attempts from a path that mostly did not execute is still zero — it is not
  evidence that a working retrieval path stays home.
- zoteus `R15-residue-inventory` has `created_count` 0: a residue sweep over
  nothing.
- zoteus `R10-local-by-default` was obtained with one input the adapter itself
  flags as **not a default** — the path to the on-device model runtime, passed in
  because the built checkout does not vendor it. Disclosed rather than hidden,
  but the green rests on a runtime handed to the target.

Only zoteus `R15-model-cache-under-declared-roots` has material behind it: four
files created, none outside the declared roots, query answered.

**Every reading here is from an empty index.** zoteus's declaration says it
plainly: the data directory starts empty, so any clause about an index already in
service has nothing to read. Nothing was measured against a target that had
converged on a library.

**The provenance is inconsistent, and two artifacts name no machine at all.**
Neither `acceptance-zoteus.json` nor `acceptance-zotero-mcp.json` records a
machine; the paths place them in this operator's home and this session runs on
`doudou`, but that is inference, not a recorded fact. The #6012 artifact records
`machine: doudou` while its own `declaration.revision` says the build was made
"on padme", and the artifact and its runner report name **different BuildIDs for
the same commit** (…011524 versus …123818) — two builds of one pin. The commit is
the pin and the BuildID is explicitly recorded-not-enforced, so this does not void
the reading, but nobody can now point at the binary that was measured. ZotSeek's
declaration reasons — including its measured uninstall-hook finding with its
control arm — were produced on `padme` in earlier sessions by another lane and
folded in as recorded reasons; they were not re-verified in this run.

**Coverage of the requirement sheet is not what this shows.** Twelve clauses
across six requirements (R3, R10, R13, R15, R22, R23). Of the seven ratified
verbs, `configure` and `resume` are the subject of no check in either registry
(`assertions.py:1012`, `durability.py:730`) — ticket 0602's gap 2, half closed
now that `pause` has two assertions. A reader must not read the sheet's coverage
into this table.

**A row that is `not-offered` across four columns is not a verdict on the
requirement.** R15-uninstall is not-offered on all four measured targets;
R22-pause on three, not-run on the fourth. The matrix cannot distinguish "no
target does this" from "no target exposes this to a machine", and the recorded
reasons say it is the second in at least three cases — #6012's pause control is
real and correct behind a GUI, ZotSeek's is a button in a progress window and its
uninstall hook demonstrably fires when a human clicks Remove, zoteus's purge
exists and is ruled out as a stand-in. Read those cells as interface findings,
never as absent capability.

**Ticket 0602 gap 1 is still live and this matrix does not exercise it.**
`assertions.py:338` still scores a target reporting locality `"none"` as `fail`
against "the embedder is local". #6012's shipped default is exactly that case —
and it declares `status` absent, so it takes the `not-offered` branch and never
reaches the comparison. The #6012 column is silence about the gap, not evidence
against it.

**The instrument's clean bill of health is job-local, not committed.** It comes
from `acceptance-fixtures.json` (2026-09-03, 16 fixtures × 12 assertions). The repo's
committed fail-control matrix,
`bench/results/smoke-1.12.0/acceptance-fixtures.json`, is dated 2026-09-02 and
carries 14 fixtures × 10 checks — **no R22 rows at all**. Both report an empty
`assertions_never_seen_red`, but the committed one cannot speak for the two
assertions that did not exist when it was written.

**One red is one red.** The zoteus egress failure is a name-lookup finding on one
target, at one revision, on one machine. It is not a statement about the other
four, and inflating it into one would be exactly the error this layer is built to
prevent.
