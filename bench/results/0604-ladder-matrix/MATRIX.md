# The acceptance matrix — five targets, twelve clauses

Assembled 2026-09-03 on `doudou` from four per-target artifacts plus one
in-flight column, then twice amended the same day: Beaver's column folded in
from its own artifact, and four host-bound cells decided from two further runs.
Seven artifacts now stand behind it, all named in the totals table and in
`PROVENANCE.md`. The layer, its seven-verb interface and the four states it may
emit are SPEC.md §5.2.8; the adapter contract and the five-target roster are
DECISIONS.md's ratified entry of 2026-09-02.

**Four cells were filled later the same day, and this is what they were waiting
for.** `R10-no-egress` and `R15-residue-inventory` on Zotero core #6012 and on
ZotSeek both walk into `with target.running():`, which starts a Zotero desktop
host. While this matrix was assembled a peer session held the machine's Zotero
for a full-library index build and every agent was forbidden to launch one, so
those four read `not-staged` — the only cells on the sheet blocked for a
scheduling reason rather than a technical one. The prohibition was lifted, the
staging both agents had done was still on disk and still valid, and
`bench/acceptance/run.py` was run end to end against each adapter. Three of the
four came back red and one green; the ten other cells in each column came back
`not-offered` exactly as the staging pass had read them, now from an executed
run. The two new artifacts are `acceptance-zotero-core-6012-hosted.json` and
`acceptance-zotseek-hosted.json`, committed beside the staging artifacts rather
than replacing them. Nothing else on the sheet moved: no other cell was blocked
on a host, so lifting the hold changed these four and nothing more.

**This is not a test suite.** Each cell is one MUST clause of one requirement,
asserted once, against one named target. A green is a green for that target and
for nothing else.

**Beaver's column was filled after assembly, from its own committed artifact**
(`../0586-beaver/acceptance.json`, same day; adapter merged in PR #237 and
verified in #269). Its five goal-1 clauses are measured; the seven goal-2
clauses read `not-measured` because `durability.py` landed after that run, not
because anything was undecided. That fold changed the totals and left the prose
underneath stale, which a separate recount then repaired (PR #275). The
four-cell amendment above moves the same arithmetic once more: 55 non-green
cells at assembly, 54 after the recount, 53 now.

**Instrument health:** healthy — `assertions_never_seen_red` is empty in
`acceptance-fixtures.json` (16 fixtures × 12 assertions, 2026-09-03), and every one of
the twelve assertions was independently driven red by at least one fail-control,
so none has gone inert.

---

## The matrix

| Clause | Req | verb | zoteus | Zotero core #6012 | ZotSeek | 54yyyu/zotero-mcp | Beaver |
|---|---|---|---|---|---|---|---|
| R10-local-by-default | R10 | status | **pass** | not-offered | not-offered | not-run | not-offered |
| R10-no-egress | R10 | query | **FAIL** | **FAIL** | **FAIL** | **pass** | **FAIL** |
| R15-residue-inventory | R15 | install | **pass** | **FAIL** | **pass** | **pass** | **pass** |
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
| Zotero core #6012 @19e7962 | 0 | 2 | 10 | 0 | 0 | 0 | `acceptance-zotero-core-6012-hosted.json` |
| ZotSeek 1.21.2 @f442f82 | 1 | 1 | 10 | 0 | 0 | 0 | `acceptance-zotseek-hosted.json` |
| zotero-mcp 0.11.0 @3cb3e2e | 2 | 0 | 3 | 7 | 0 | 0 | `acceptance-zotero-mcp.json` |
| Beaver 0.23.3 @`bec71e14` | 1 | 2 | 2 | 0 | 0 | 7 | `../0586-beaver/acceptance.json` |
| **60 cells** | **7** | **6** | **26** | **14** | **0** | **7** | |

The `not-staged` column is now empty and the state is retired from this sheet;
its definition stays in the legend below because two committed artifacts still
carry it. The two columns that moved are named against their **hosted**
artifacts above; the staging artifacts they supersede,
`acceptance-zotero-core-6012.json` and `acceptance-zotseek.json`, stay committed
and still hold the ten `not-offered` readings, the declarations and the
positive controls those runs produced.

Seven cells of sixty are green. No cell is blank and no cell is inferred: each
traces to a `result` field in a named artifact. Beaver's column was folded in
from its own committed artifact after assembly and its adapter was not touched
here. The blocking analysis below counts the 53 non-green cells this table now
carries.

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
`with target.running():`, which launches a Zotero desktop host, and the
assembling session was forbidden to launch one (a peer session's full-library
index build owned the local Zotero host). No fact about the target was produced.
This state is *distinct from `not-offered` in both directions* — the surface is
there and was not exercised. **No cell reads it any more**: the hold lifted and
all four were run. The definition stays because the two staging artifacts still
carry the word, and because it is the one state on this list that says something
about the session rather than about the target.

**`fail` — asserted against this target and falsified.** Six cells, on four of
the five targets. Every one of them was obtained with its instrument proven
working in the same run: the two egress fail-controls fire on each egress red,
and the residue sweep names the files it found.

**`not-measured` — not a harness state either.** Beaver's seven goal-2 cells.
The assertions that decide them did not exist when its lane ran the layer, so
nothing about the target was asked; they are unmeasured, not undecided. The word
`in-flight` appeared here while Beaver's column was empty and is retired with
it — its five goal-1 cells are measured and folded in above.

---

## Blocking analysis — 53 non-green cells by cause

The order below is the one this analysis was assembled in rather than a re-sort:
sections 5 and 8 changed size when the four host-bound cells were decided, and
the ranking no longer descends. The counts sum to 53, which is 60 minus the
seven greens.

### 1. The target declares the verb absent — 26 cells (49%)

| Target | absent verbs these clauses need | cells |
|---|---|---|
| Zotero core #6012 | status (4), query (3), pause (2), uninstall (1) | 10 |
| ZotSeek | status (4), query (3), pause (2), uninstall (1) | 10 |
| zotero-mcp | pause (2), uninstall (1) | 3 |
| Beaver | status (1), query (1) | 2 |
| zoteus | uninstall (1) | 1 |

These are **executed** verdicts, not skipped ones. For #6012 and ZotSeek the ten
assertion functions whose declaration guard sits before the lifecycle block were
first called directly against real adapters, and each staging artifact carries a
positive control — the same ten functions returning `pass` against `stub-quiet`
and `not-offered` against `stub-verbless` — proving neither branch is stuck.
Those twenty readings have since been reproduced by full runs of the driver
against both targets, and came back identical.

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

### 2. Beaver predates `durability.py` — 7 cells (13%)

Beaver's adapter was in flight during assembly and its column was filled
afterwards from `../0586-beaver/acceptance.json` (PR #237, verified in #269).
Its five goal-1 clauses are measured — 1 pass, 2 fail, 2 not-offered, and its
two reds are counted under cause 8. The seven goal-2 clauses read
`not-measured`: `durability.py` landed after that run, so R3, R13 and R23 were
never asserted against this target at all. That is not the harness declining to
decide; it is a question never put.

**Unblock:** re-run the layer against the Beaver adapter now that the goal-2
registry exists. Cheaper than any other row here, since the adapter and its
pinned artifact are committed. Owner: ticket 0586, still open on its credentials
exit criterion.

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

### 5. This session may not launch a Zotero desktop host — 0 cells (resolved)

#6012 and ZotSeek, on R10-no-egress and R15-residue-inventory. The staging
reports predicted the unblock exactly — permission to start a host, plus an
Xvfb display, against staging that was already complete — and that is what it
took. Both hosts started on an Xvfb server at `:77`, on the adapters' own ports
(23519 and 23219), and the operator's resident Zotero kept 127.0.0.1:23119
throughout, untouched and still running afterwards. **The port was never in fact
free**, and it did not need to be: no adapter on this roster uses 23119. What
had been in the way was a policy on launching a host, and the policy is what
lifted.

The four verdicts are in sections 8 below and in the two `-hosted` artifacts.
Their residue arenas are the substantive part of this pass: 1 190 files created
under ZotSeek's, 1 171 under #6012's, against `created_count` 0 on both greens
this sheet already carried.

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

### 8. Real reds — 6 cells (11%)

**Four of the five targets attempt name lookups in a default-configuration
run.** Lookups to the local stub resolver at 127.0.0.53:53, and nothing else on
either detector: zoteus 4, Beaver 60, ZotSeek 94, #6012 98 in each assertion's
own subject arm — **counts that are not comparable across targets**, because
each arm runs its own adapter's lifecycle and those windows differ in length. A
larger number over a longer window is not more egress. What is comparable within
a target is a controlled A/B, which only Beaver's lane has run. Off-machine
attempts are zero on all four. The clause's `falsified_by` names "any connection
attempted to an address off this machine, **or any name lookup**", and the
detector note explains why the second detector must exist: inside a no-route
namespace a hostname attempt dies at resolution and leaves no off-machine
connect at all, so a detector without it reports a false green. Both controls
fired on every one of these runs — the net-shared and isolated arms each
recorded an off-machine attempt — so these are findings, not could-not-looks.

Read the two new ones with their limit attached, which their artifacts state
first: **on both host-bound targets the driven run did not complete.** Inside
the egress sandbox `/tmp` is read-only, GTK's icon loader needs to write a
temporary file there, and the host aborts about seven seconds into startup. The
assertion decides this case itself — `DRIVE_INCOMPLETE` with a *zero* count is
`not-run`, an attempt the tracer recorded stands anyway — so the lookups counted
are the ones the run got as far as making, and the target's own retrieval path
never executed. That crash is the harness's sandbox meeting this machine's
desktop stack, not a defect of either target: the same hosts start and stop
cleanly in the residue assertion, which uses no sandbox. Whether the sandbox
should hand the host a writable temporary directory belongs to the harness lane;
nothing here changed the instrument mid-reading.

**#6012, R15-residue-inventory.** Two files outside the declaration, both under
`<arena>/home/.local/share/gvfs-metadata/` — the GIO metadata store, written
under the sandbox HOME by the desktop stack the application runs on. This is a
**declaration-completeness** finding, which is what R15's ratified clause is
for, and not a claim that the target put library text somewhere it should not:
the same class as the `.config/libreoffice` entry the adapter's own declaration
already calls "an admission, not the resolution". The declaration names its own
falsifiers, and "a write at the top of the sandbox HOME" is one of them. It was
swept on `padme` when written and this run is on `doudou`, where gvfs is active
— a declaration is complete only with respect to the machines it has been swept
on.

**Beaver, R10-no-egress and R15-uninstall-removes-declared-state.** Both folded
in with its column and both read against controls of their own; the egress red
in particular is stated as the **+4** attributable to the plugin over a
host-only baseline that already fails the clause — 430 lookups against 426 over
a matched 90-second window — not as "Beaver fails R10". `../0586-beaver/` holds
both arms, and that A/B is the shape the other three egress reds do not have.

**Unblock:** none of these is a blocker. They are the matrix's results that need
carrying upstream, and **no ticket owns any of them.** Scope the egress family
honestly when filing: it says a default-configuration run performs name lookups,
not that library text left the machine.

---

## What this matrix does not establish

**All five targets have now been executed, and on two of them the executed part
is thin.** `bench/acceptance/run.py` has been run end to end against every
column. On #6012 and ZotSeek that run reached exactly two clauses: ten of their
twelve are `not-offered` at the declaration gate, so the only *runtime*
behaviour this sheet has ever observed on either is one residue sweep and one
egress sweep each — and the egress sweep on both crashed seven seconds in. Two
cells apiece is not a picture of how a target behaves.

**The two new egress reds rest on runs that did not finish.** Stated in the
legend and again in section 8, and repeated here because it is the single
easiest thing to over-read on this sheet: the counted lookups are real and the
verdict is the assertion's own, but the retrieval path they were supposed to
cover never ran. A complete run could only have found more; it could not have
found fewer. That is the whole of what the incompleteness costs, and it is not
nothing.

**ZotSeek's green and #6012's red are the same two files, read against two
declarations.** `.local/share/gvfs-metadata/` appeared under *both* targets'
sandbox HOME. #6012's declaration names its HOME exemptions one at a time and
does not name that one, so the sweep called it residue; ZotSeek's exempts the
entire sandbox HOME as the host application's, so the sweep never looked. The
difference between those two verdicts is a difference between two declarations,
not between two behaviours, and the green is the weaker of the two readings for
exactly that reason. What is material in it is the rest: 1 190 files created,
the pinned XPI actually loaded, `zotseek.sqlite` at 557 056 bytes and sixteen of
the target's own preference keys written — the first residue green on this sheet
with a real install behind it.

**Four of the seven greens are thin, by their own runners' admission.**

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

Of the remaining three, zoteus `R15-model-cache-under-declared-roots` has
material behind it — four files created, none outside the declared roots, query
answered — and so does ZotSeek `R15-residue-inventory`, with the reservation
above. Beaver's `R15-residue-inventory` came from its own lane's run and is not
assessed here.

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
the reading, but nobody can now point at the binary that was measured. *That much
is closed for the two hosted runs*: both record `machine: doudou`, both name the
launcher they ran, and the #6012 hosted run stamps BuildID …123818 for the binary
that is on disk at the recorded path — the adapter checked the commit pin at
construction and the install event carries `pin_checked: true`. ZotSeek's
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
requirement.** R15-uninstall is not-offered on four of the five columns and
`fail` on the fifth; R22-pause is not-offered on three, not-run on one and
not-measured on one. The matrix cannot distinguish "no
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

**Each red is one red.** Every one of the six is a finding about one target, at
one revision, on one machine, under one clause. Four of them now sit in the same
row, and a reader who reads that row as "the roster leaks" has made exactly the
error this layer is built to prevent: what the row says is that four default
configurations perform name lookups on the local stub resolver, with zero
off-machine attempts on any of them, two of the four measured on runs that
crashed before the retrieval path executed. Aggregating cells across a row is
not one of the things this sheet supports.
