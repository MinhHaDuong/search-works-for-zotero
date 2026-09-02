"""Goal 2's assertions: it does not lose or corrupt what it built.

`SPEC.md` §3 owns R3, R13 and R23; `SPEC.md` §5.2.8's "Counters (C4)" and "The
convergence harness" own the counter vocabulary and the phase-2 arithmetic these
read; `DECISIONS.md`'s ratified entry of 2026-09-02 owns the interface. None is
restated here — this module cites addresses and asserts clauses.

It lives beside `assertions.py` rather than inside it, under the same rules: no
target's name, no tool name, no path literal, no data-directory literal. The
target-neutrality guard walks the package recursively, so this file is scanned
without anyone adding it to a list.

**Two normalized shapes are declared here**, in the same place and for the same
reason `assertions.py` declares the embedding shape: the ratified contract fixes
the verbs and the states and deliberately fixes nothing about what a verb
returns, so a clause that has to read something states its requirement on an
adapter next to the clause that needs it.

    status() -> {"work": {"<stage>.<trigger>.<outcome>": int, ...} | None}
    query(...) -> {"hits": list | None}

`work` is `SPEC.md` §5.2.8's `work.<stage>.<trigger>.<outcome>` counters,
flattened to one dotted key per counter. An adapter whose target reports no such
counters sets it to None, and every clause that reads them says `not-run`. That
is not a formality: a target with no work counters cannot be graded on
proportionality by anyone, and a green there would mean "could not look".
`hits` is None for a target that answers without reporting what it matched; the
R23 clause below then says `not-run` too, because "it ends up serving" cannot be
decided from the fact that a call returned.

**Perturbation is the seam this goal needed and the interface does not have.**
Every goal-2 clause has the form *do something to the system, then observe it
through the verbs*. The observing side is `status` and `query`. The doing side —
edit one item, resync unchanged bytes, restamp the index under a foreign schema
version — is not a verb, cannot become one (`Check.verb` and
`Declaration.unsupported` both refuse a name outside `VERBS`, which is the
ratified contract working as intended), and is not something the harness can do
for a target without knowing that target's storage.

So it takes the shape the contract already gives the process lifecycle:
adapter-declared harness setup, exposed as a method rather than a verb. An
adapter that can drive a perturbation implements `perturb(what)`; one that
cannot raises `NotImplementedError`, and the clause reports `not-run` naming the
perturbation. Nothing is added to `Declaration`, nothing to `VERBS`, nothing to
`STATES`. Whether this seam should instead be ratified alongside the seven verbs
is a question about the interface, raised here and not settled.

**Why `not-run` and not `not-offered` for a missing perturbation.**
`not-offered` means the target declares no such surface; the declaration is the
authority and a reader can audit it. A missing perturbation is the harness's own
instrument being unavailable for this target — the adapter has not been taught to
drive it — which is what `not-run` names. The distinction matters because the two
are fixed by different people: a `not-offered` is a fact about a product, a
`not-run` is work.
"""

import os
import time
from pathlib import Path

from .interface import (
    FAIL,
    PASS,
    Check,
    Target,
    not_offered,
    not_run,
)

#: The perturbations goal 2's clauses need, by name. An adapter maps each onto
#: whatever its target requires; the layer never sees the right-hand side.
EDIT_ONE_ITEM = "edit-one-item"
RESYNC_IDENTICAL_BYTES = "resync-identical-bytes"
RESTAMP_OLDER = "restamp-older"
RESTAMP_NEWER = "restamp-newer"

PERTURBATIONS = (EDIT_ONE_ITEM, RESYNC_IDENTICAL_BYTES, RESTAMP_OLDER, RESTAMP_NEWER)

#: How long the harness waits for work counters to stop moving, and how often it
#: looks. This is the harness's patience, not a bound any requirement states: no
#: clause here is about elapsed time, and neither number reaches a verdict. A run
#: that exhausts the deadline reports `not-run`, never a red — an impatient
#: harness must not be able to manufacture a failure.
SETTLE_DEADLINE_S = 300.0
SETTLE_POLL_S = 1.0

#: The outcome half of `work.<stage>.<trigger>.<outcome>`. `done` means
#: recomputed; `noop` means signals moved, keys verified, nothing recomputed
#: (§5.2.8). Both are read: a resync that recomputes nothing *because it never
#: looked* also shows zero `done`, and only the `noop` side tells the two apart.
DONE = "done"
NOOP = "noop"

#: The trigger half this layer names, for the one clause whose falsifier is
#: about a specific trigger rather than about any of them.
RESYNC = "resync"


# --------------------------------------------------------------------------
# Reading the target: counters, hits, settling, perturbing.
# --------------------------------------------------------------------------


def work_counters(target: Target) -> dict[str, int] | None:
    """The flattened work counters this target reports, or None if it reports none.

    Called inside `running()`: `status` is a verb, and a verb reaches a target
    through its process.
    """
    reported = target.status().get("work")
    if reported is None:
        return None
    return {str(k): int(v) for k, v in dict(reported).items()}


def delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """What moved, dropping the counters that did not. Absent means zero."""
    keys = set(before) | set(after)
    moved = {k: after.get(k, 0) - before.get(k, 0) for k in keys}
    return {k: v for k, v in sorted(moved.items()) if v}


def _field(counter: str, index: int) -> str:
    """One field of a `work.<stage>.<trigger>.<outcome>` name, or '' if it is not one."""
    parts = counter.split(".")
    if len(parts) != 4 or parts[0] != "work":
        return ""
    return parts[index]


def stage_of(counter: str) -> str:
    return _field(counter, 1)


def trigger_of(counter: str) -> str:
    return _field(counter, 2)


def outcome_of(counter: str) -> str:
    return _field(counter, 3)


def settle(target: Target, *, deadline_s: float = SETTLE_DEADLINE_S,
           poll_s: float | None = None) -> tuple[dict[str, int] | None, bool]:
    """Poll until the work counters stop moving. Returns them, and whether they did.

    Stationary work counters are §5.2.8's own terminal-state observable, and that
    section says why the counters ride beside any phase field: a phase reaching
    `idle` reports a loop at rest on the branch that shuts the engine down *and*
    on the branch that leaves it up for more work. Two consecutive identical
    reads are required rather than one, so a poll landing between two batches
    does not read as rest.

    The interval is adapter-declared where an adapter declares one
    (`settle_poll_s`), on the same footing as the process lifecycle and the
    perturbation hook: how fast a target's counters can move is a property of
    that target, and a fixture whose ledger is updated synchronously would
    otherwise pay a real target's polling cost for nothing. It is a rate, not a
    verdict — nothing here reads it to decide anything.
    """
    if poll_s is None:
        poll_s = float(getattr(target, "settle_poll_s", SETTLE_POLL_S))
    last = work_counters(target)
    if last is None:
        return None, False
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        time.sleep(poll_s)
        now = work_counters(target)
        if now == last:
            return last, True
        last = now
    return last, False


def hits_of(answer: object) -> list | None:
    """The hit list a query reported, or None when the target does not report one."""
    if not isinstance(answer, dict):
        return None
    hits = answer.get("hits")
    return hits if isinstance(hits, list) else None


def perturb(target: Target, what: str) -> tuple[dict | None, str | None]:
    """Drive a perturbation, or say why this target could not be driven that way.

    Returns `(event, None)` on success and `(None, why)` when the adapter has no
    way to do it. The absence is reported, never worked around: a harness that
    reached past the adapter to edit a target's storage itself would be grading a
    state it had manufactured.
    """
    hook = getattr(target, "perturb", None)
    if hook is None:
        return None, (
            f"this adapter offers no perturbation hook, so the harness cannot make "
            f"{what!r} happen to this target; the clause is not decided here"
        )
    try:
        return dict(hook(what)), None
    except NotImplementedError as why:
        return None, (
            f"this adapter cannot drive the perturbation {what!r} against its target "
            f"({why}); the clause is not decided here"
        )


def _no_counters(cid: str, req: str, clause: str, falsified: str, target: Target) -> Check:
    return not_run(
        cid, req, clause, falsified, target, "status",
        "this target reports no work.<stage>.<trigger>.<outcome> counters "
        "(SPEC.md §5.2.8, Counters (C4)), so there is nothing here to read and this "
        "clause is not decided. A green would mean the harness could not look.",
    )


def _unsettled(cid: str, req: str, clause: str, falsified: str, target: Target,
               when: str) -> Check:
    return not_run(
        cid, req, clause, falsified, target, "status",
        f"the work counters were still moving {when} when the harness ran out of "
        "patience, so the arithmetic would be read off an unfinished run. Reported as "
        "not decided rather than as a red: an impatient harness must not be able to "
        "manufacture a failure.",
    )


# --------------------------------------------------------------------------
# R3 — the cost of staying current is what changed.
# --------------------------------------------------------------------------


def check_edit_recomputes_only_what_changed(target: Target) -> Check:
    """R3: editing one item recomputes exactly what that item implies, and nothing else.

    §5.2.8's phase 2 states the arithmetic and this asserts it: one record
    recomputed, that record's sections re-embedded, every other `*.done` delta
    zero. The section count comes from the perturbation's own event rather than
    from a number written here — how many sections one record has is a property
    of the fixture library, not of this clause.

    The falsifier is the shipped defect: a library where an edit to one title
    re-marks work across items that did not change. That is the 92,7 % defect
    §5.2.8 names, and it is why this clause is measured by counters rather than
    by a clock — a fast enough machine hides it, and a slow one blames the
    hardware.
    """
    cid, req = "R3-edit-recomputes-only-what-changed", "R3"
    clause = ("the cost of staying current is proportional to what changed: an edit to "
              "one item recomputes that item's record and its sections, and nothing else")
    falsified = ("any work.*.*.done delta outside the edited item's record and embed "
                 "stages, or a record-stage delta other than one")

    if not target.declaration.offers("status"):
        return not_offered(cid, req, clause, falsified, target, "status")

    with target.running():
        if work_counters(target) is None:
            return _no_counters(cid, req, clause, falsified, target)
        before, settled = settle(target)
        if not settled:
            return _unsettled(cid, req, clause, falsified, target, "before the edit")
        event, why = perturb(target, EDIT_ONE_ITEM)
        if why:
            return not_run(cid, req, clause, falsified, target, "status", why)
        after, settled = settle(target)
        if not settled:
            return _unsettled(cid, req, clause, falsified, target, "after the edit")

    sections = event.get("sections")
    if not isinstance(sections, int):
        return not_run(cid, req, clause, falsified, target, "status",
                       "the perturbation did not report how many sections the edited "
                       "record has, so the embed arithmetic has no right-hand side and "
                       "the clause is not decided")

    moved = delta(before, after)
    done = {k: v for k, v in moved.items() if outcome_of(k) == DONE}
    expected = {"work.record.edit.done": 1, "work.embed.edit.done": sections}
    unexpected = {k: v for k, v in done.items() if expected.get(k) != v}
    missing = {k: v for k, v in expected.items() if done.get(k) != v}
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if not unexpected and not missing else FAIL,
        target=target.declaration.name, verb="status",
        detail={
            "perturbation": EDIT_ONE_ITEM,
            "event": event,
            "sections_reported_by_the_perturbation": sections,
            "expected_done_deltas": expected,
            "observed_done_deltas": done,
            "unexpected": unexpected,
            "missing_or_wrong": missing,
            "all_deltas": moved,
            "reads": ("SPEC.md §5.2.8's phase-2 arithmetic, against the counters that "
                      "section declares; no counter name is invented here"),
        },
    )


def check_identical_resync_recomputes_nothing(target: Target) -> Check:
    """R3: a resync whose bytes are unchanged recomputes nothing downstream of verification.

    **Two detectors, and the second is what makes the first mean anything.** A
    resync that recomputes nothing shows every `*.done` delta at zero. So does a
    target that did not resync at all — one whose signals never moved, whose
    hashes were never verified, whose reconcile tick never ran. A `done`-only
    detector cannot tell those apart and reports the same green for both.

    So the pass requires both: no `*.done` moved, AND the verification the resync
    consists of is visible as `*.resync.noop` movement. §5.2.8 states exactly that
    split — `noop` means signals moved and keys verified with nothing recomputed —
    and says the gate MUST permit exactly that and nothing downstream of it.
    """
    cid, req = "R3-identical-resync-recomputes-nothing", "R3"
    clause = ("a resync that moves signals without changing bytes runs its verification "
              "and recomputes nothing downstream of it")
    falsified = ("any work.*.*.done delta after an identical-bytes resync, or a resync "
                 "that moves no work.*.resync.noop counter at all — the second being a "
                 "run that verified nothing rather than one that recomputed nothing")

    if not target.declaration.offers("status"):
        return not_offered(cid, req, clause, falsified, target, "status")

    with target.running():
        if work_counters(target) is None:
            return _no_counters(cid, req, clause, falsified, target)
        before, settled = settle(target)
        if not settled:
            return _unsettled(cid, req, clause, falsified, target, "before the resync")
        event, why = perturb(target, RESYNC_IDENTICAL_BYTES)
        if why:
            return not_run(cid, req, clause, falsified, target, "status", why)
        after, settled = settle(target)
        if not settled:
            return _unsettled(cid, req, clause, falsified, target, "after the resync")

    moved = delta(before, after)
    recomputed = {k: v for k, v in moved.items() if outcome_of(k) == DONE and v}
    verified = {k: v for k, v in moved.items()
                if outcome_of(k) == NOOP and trigger_of(k) == RESYNC and v > 0}
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if not recomputed and verified else FAIL,
        target=target.declaration.name, verb="status",
        detail={
            "perturbation": RESYNC_IDENTICAL_BYTES,
            "event": event,
            "recomputed": recomputed,
            "verified_as_noop": verified,
            "all_deltas": moved,
            "two_detectors": (
                "no *.done moved, AND *.resync.noop did move. The first alone is also "
                "what a target that never verified anything reports, and a check that "
                "cannot tell those apart passes a run that did nothing"
            ),
        },
    )


# --------------------------------------------------------------------------
# R13 — two processes on one data directory.
# --------------------------------------------------------------------------


def _answer(target: Target, q: str, limit: int) -> tuple[object, list | None]:
    answer = target.query(q, "meaning", limit)
    return answer, hits_of(answer)


def _answer_or_why(target: Target, q: str, limit: int) -> tuple[object, list | None, str]:
    """As `_answer`, but a raising query is an observation rather than a crash.

    A target that cannot answer after its storage was perturbed is exactly what
    the clauses below are looking for. Letting the exception out would turn that
    finding into a traceback from the gate, which reports nothing to anybody.
    """
    try:
        answer, hits = _answer(target, q, limit)
    except Exception as why:  # noqa: BLE001 - the failure IS the observation
        return None, None, f"{type(why).__name__}: {why}"
    return answer, hits, ""


def check_two_processes_both_answer(target: Target, *, second: Target) -> Check:
    """R13: two processes on one data directory both answer, and the index survives them.

    `second` is a second adapter instance over the same arena, so both processes
    resolve the same declared derived-state root — which is what "one data
    directory" means without the layer knowing any path. The two lifecycles are
    nested rather than sequential: a second process that only ever ran after the
    first exited is not company.

    Three observations, and the third is not decoration. Both must answer while
    the other is live; then, after both have gone, a third process must read the
    same index and answer as well. A pair of processes can both answer perfectly
    and leave the file unreadable behind them, and that is precisely the
    corruption the clause is about — visible only after they are gone.
    """
    cid, req = "R13-two-processes-both-answer", "R13"
    clause = ("two server processes on one data directory both answer queries without "
              "corrupting the index")
    falsified = ("either process failing to answer while the other is live, or an index "
                 "that a third process cannot read after both have stopped")

    if not target.declaration.offers("query"):
        return not_offered(cid, req, clause, falsified, target, "query")

    shared = [str(p) for p in target.declaration.derived_state_roots]
    if shared != [str(p) for p in second.declaration.derived_state_roots]:
        return not_run(cid, req, clause, falsified, target, "query",
                       "the two adapter instances do not resolve the same derived-state "
                       "root, so this run would not put two processes on one data "
                       "directory and would decide nothing")

    q, limit = "a query the harness supplies to both processes", 5
    first_hits = second_hits = third_hits = None
    failures: list[str] = []
    try:
        with target.running():
            _answer(target, q, limit)
            with second.running():
                _, second_hits = _answer(second, q, limit)
                # Re-asked while the other is live: an answer taken before the
                # second process started says nothing about company.
                _, first_hits = _answer(target, q, limit)
    except Exception as why:  # noqa: BLE001 - the failure IS the observation
        failures.append(f"a process raised while the pair was live: {type(why).__name__}: {why}")

    try:
        with target.running():
            _, third_hits = _answer(target, q, limit)
    except Exception as why:  # noqa: BLE001
        failures.append(
            f"a process raised after the pair had stopped: {type(why).__name__}: {why}")

    reported = [h for h in (first_hits, second_hits, third_hits) if h is not None]
    if not reported and not failures:
        return not_run(cid, req, clause, falsified, target, "query",
                       "no process reported a hit list, so whether they answered cannot "
                       "be read from what this target returns; the clause is not decided")
    survived = None not in (first_hits, second_hits, third_hits)
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if survived and not failures else FAIL,
        target=target.declaration.name, verb="query",
        detail={
            "shared_derived_state_roots": shared,
            "hits_first_while_second_live": None if first_hits is None else len(first_hits),
            "hits_second_while_first_live": None if second_hits is None else len(second_hits),
            "hits_third_after_both_stopped": None if third_hits is None else len(third_hits),
            "failures": failures,
            "identical_across_all_three": _identical(first_hits, second_hits, third_hits),
            "why_a_third_process": (
                "a pair can answer perfectly and still leave the file unreadable; the "
                "corruption this clause names is only visible after both have gone"
            ),
            "why_no_replies_here": (
                "counts and an identity comparison, never the replies: a committed "
                "artifact names a library document by its item key and never by its "
                "title (DECISIONS.md, ratified 2026-08-31), and a reply carries both"
            ),
        },
    )


def _identical(*hit_lists: list | None) -> bool | None:
    """Whether every process returned the same hits, without keeping any of them.

    None when any process reported no hit list, because "the same" is not a
    question that has an answer then.
    """
    if any(h is None for h in hit_lists):
        return None
    first = hit_lists[0]
    return all(h == first for h in hit_lists[1:])


def check_two_processes_do_not_duplicate_work(target: Target, *, second: Target) -> Check:
    """R13: the pair does not do the same work twice.

    Read from the work counters and from nothing else, because duplicate work is
    invisible in a query's answer: two processes that each embedded the whole
    library serve exactly what one would. The pass is that adding a second
    process to an already-settled data directory moves no `*.done` counter — the
    work was done, and company does not redo it.

    §5.2.5's honest restatement bounds duplicate *compute* rather than forbidding
    it outright, and that bound is a design number this clause does not restate:
    what is asserted here is the case the bound's own arithmetic starts from, a
    settled index gaining a second reader. A target that redoes settled work on
    company has failed the clause on any reading of the bound.
    """
    cid, req = "R13-two-processes-do-not-duplicate-work", "R13"
    clause = "two server processes on one data directory do not do the same work twice"
    falsified = ("any work.*.*.done counter moving when a second process joins a data "
                 "directory whose work had already settled")

    if not target.declaration.offers("status"):
        return not_offered(cid, req, clause, falsified, target, "status")

    with target.running():
        if work_counters(target) is None:
            return _no_counters(cid, req, clause, falsified, target)
        before, settled = settle(target)
        if not settled:
            return _unsettled(cid, req, clause, falsified, target,
                              "before the second process joined")
        with second.running():
            joined, second_settled = settle(second)
        after = work_counters(target)

    if not second_settled:
        return _unsettled(cid, req, clause, falsified, target,
                          "in the second process")
    moved = delta(before, after)
    recomputed = {k: v for k, v in moved.items() if outcome_of(k) == DONE and v}
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if not recomputed else FAIL,
        target=target.declaration.name, verb="status",
        detail={
            "baseline_settled": before,
            "after_company": after,
            "recomputed_on_company": recomputed,
            "second_process_view": joined,
            "all_deltas": moved,
            "reads": ("work.<stage>.<trigger>.<outcome> (SPEC.md §5.2.8); duplicate work "
                      "is invisible in a query's answer, so it is read here or nowhere"),
        },
    )


# --------------------------------------------------------------------------
# R23 — an index under another schema version ends up serving.
# --------------------------------------------------------------------------


def _inventory(target: Target) -> frozenset[Path]:
    """Every regular file under the declared derived-state roots, right now."""
    found: set[Path] = set()
    for root in target.declaration.derived_state_roots:
        for base, _dirs, names in os.walk(root):
            for name in names:
                found.add(Path(base) / name)
    return frozenset(found)


def check_foreign_stamp_ends_up_serving(target: Target) -> Check:
    """R23: an index stamped under another schema version ends up serving, either way.

    The half already asserted elsewhere is damage prevention: a foreign file is
    detected before anything writes to it, and its bytes survive. That is a
    different clause, it passes, and this one does not touch it. What R23 promises
    beyond it is the outcome — *ends up serving* — and no restamp test can
    establish that, because sidelining the file and opening a fresh empty one
    satisfies every damage-prevention assertion while serving nothing.

    So this asserts the outcome and only the outcome: after the stamp is changed
    and the process restarted, does a query come back with what the index held?
    Both directions, because an older stamp is what every user holds the day the
    build's schema version is incremented, and a newer one is what a rollback
    produces; a forward-only probe misses the common case.

    **What is recorded, and what deliberately is not.** Counts, not replies: a
    committed artifact names a library document by its item key and never by its
    title (`DECISIONS.md`, ratified 2026-08-31), and a search reply carries both.
    The arms record three distinguishable states rather than one — an index
    serving nothing, a reply that carries no hit list at all, and a target that
    could not answer — because all three fail this clause for different reasons
    and a red that cannot say which is a red someone has to reproduce.

    **No file is deleted by hand, and the harness proves that rather than
    promising it.** The clause's own wording makes hand deletion the
    disqualifier, so the harness inventories the declared roots before and after
    and records what disappeared. A run that reached in and removed the sidelined
    file would come back green on the query and would have asserted nothing.

    Where a build declines the foreign stamp and rebuilds instead, this is red,
    and it must be a red rather than a skip: a gate reporting the same thing
    whether the capability is absent or the gate is broken has said nothing. The
    remaining half is upstream issue #34.
    """
    cid, req = "R23-foreign-stamp-ends-up-serving", "R23"
    clause = ("an index written under a different schema version ends up serving, in "
              "either direction, without anyone deleting files by hand")
    falsified = ("a foreign-stamped index that answers nothing after a restart, or one "
                 "that only comes back after a file is removed by hand")

    if not target.declaration.offers("query"):
        return not_offered(cid, req, clause, falsified, target, "query")

    q, limit = "a query the harness supplies before and after the stamp changes", 5
    with target.running():
        _, baseline_hits, baseline_why = _answer_or_why(target, q, limit)
    if baseline_why:
        return not_run(cid, req, clause, falsified, target, "query",
                       "the target could not answer before the stamp was touched "
                       f"({baseline_why}), so there is no baseline to compare against "
                       "and this clause is not decided")
    if baseline_hits is None:
        return not_run(cid, req, clause, falsified, target, "query",
                       "this target answers without reporting what it matched, so "
                       "'ends up serving' has nothing to be read from; the clause is not "
                       "decided rather than assumed either way")
    if not baseline_hits:
        return not_run(cid, req, clause, falsified, target, "query",
                       "the index served nothing before the stamp was touched, so an "
                       "empty answer afterwards would prove nothing about migration")

    arms: dict[str, dict] = {}
    for direction in (RESTAMP_OLDER, RESTAMP_NEWER):
        event, why = perturb(target, direction)
        if why:
            return not_run(cid, req, clause, falsified, target, "query", why)
        before_files = _inventory(target)
        with target.running():
            _, hits, why_not = _answer_or_why(target, q, limit)
        arms[direction] = {
            "event": event,
            # Three distinguishable states, because a red that cannot say which
            # one it saw is a red a reader has to go and reproduce. `hits: 0` is
            # an index serving nothing; `hit_list_reported: false` is a reply that
            # changed shape — which is what an abandoned index produces, the
            # search surface answering with its own empty state and no hit list at
            # all; `raised` is a target that could not answer. All three fail the
            # clause, and they fail it for different reasons.
            "hits_after_restart": None if hits is None else len(hits),
            "hit_list_reported": hits is not None,
            "serving": bool(hits),
            "raised": why_not or None,
            "files_gone": sorted(str(p) for p in before_files - _inventory(target)),
        }

    serving = all(arm["serving"] for arm in arms.values())
    by_hand = any(arm["files_gone"] for arm in arms.values())
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if serving and not by_hand else FAIL,
        target=target.declaration.name, verb="query",
        detail={
            "baseline_hits": len(baseline_hits),
            "arms": arms,
            "both_directions_serve": serving,
            "a_file_disappeared": by_hand,
            "the_other_half": (
                "damage prevention — a foreign file detected before anything writes to "
                "it, its bytes surviving — is a different clause, asserted elsewhere, "
                "passing, and untouched by this one"
            ),
            "where_the_gap_is_filed": (
                "upstream issue #34. A red here is the honest state of the serving half, "
                "not a defect introduced by this harness"
            ),
        },
    )


#: Goal 2's assertions, by check id. `assertions.ALL` folds this in, so a check
#: added here is run without a second edit. The two R13 entries take a second
#: target and are called by the driver with one, which is why they are listed
#: apart from the single-target ones.
NEEDS_A_SECOND_TARGET = (
    "R13-two-processes-both-answer",
    "R13-two-processes-do-not-duplicate-work",
)

ALL = {
    "R3-edit-recomputes-only-what-changed": check_edit_recomputes_only_what_changed,
    "R3-identical-resync-recomputes-nothing": check_identical_resync_recomputes_nothing,
    "R13-two-processes-both-answer": check_two_processes_both_answer,
    "R13-two-processes-do-not-duplicate-work": check_two_processes_do_not_duplicate_work,
    "R23-foreign-stamp-ends-up-serving": check_foreign_stamp_ends_up_serving,
}
