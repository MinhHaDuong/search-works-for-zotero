"""R22's two clauses decide, and say so when they cannot decide.

README.md's goals ladder puts R10, R15, R22 and R31 on the lowest rung and rules
the method: the assertions for a rung are built before anything on it is made to
work, because until they exist a row can only be `code` or `inferred` — a claim
about nobody. R10 and R15 arrived with the acceptance layer; R22's two are these,
and R31 is the rung's one clause the layer cannot decide, for the reason
`assertions.py` states where its assertion would have gone.

Five defects this file guards, and each of them produces a **green** rather than
an error, which is why they need fixtures rather than a careful reading.

**A pause graded from its own reply.** `pause` returning `{"paused": True}` says
that the verb was called and nothing whatever about the workers. A check reading
the reply passes `stub-ignores-pause`, whose whole content is that it answers
correctly and keeps working. `test_a_control_that_answers_and_keeps_working_is_red`
is the fixture, and it is the one that fails against a reply-reading check.

**A pause that is really the process.** The clause names restarts because a
switch kept in a running engine costs nothing and looks correct in every test
that never restarts anything. `stub-forgets-pause-on-restart` is green on the
first clause and red on the second, and that asymmetry is the point: a single
merged assertion could not report it, and a marker held in an adapter attribute
would make the fixture impossible to write at all.

**A finding with no positive control.** Both clauses find that a counter did not
move, and a counter that would not have moved anyway produces that finding on a
target whose control does nothing. So the same change is made on a second,
never-stopped instance in an arena of its own, and a change that creates no work
there leaves the clause undecided rather than green. The instance is separate for
two reasons that each rule out the alternatives: a control run first on the
graded target consumes the change, and one run after it needs `resume`, which a
target may lack by a documented ruling.

**A fail-control that fails a clause it is not about.** The pause was first
honoured in `_edit_one_item`, which three fixtures override, so two of goal 2's
fail-controls kept working while stopped and went red on R22. The gate moved to
`_bump`, where doing the work actually happens and no subclass can forget it.

**An instrument that could not look, read as a verdict.** A target with no work
counters cannot decide the pause clauses, and a target with no such control at
all is a third finding rather than a red. R22 is *verified absent* upstream, so
`not-offered` is the state the layer will actually report against a real target
today; a state no fixture produces is a state nobody has checked survives the
artifact.
"""

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance import assertions  # noqa: E402
from acceptance.adapters import stubs  # noqa: E402
from acceptance.interface import (  # noqa: E402
    FAIL,
    NOT_OFFERED,
    NOT_RUN,
    PASS,
    Declaration,
)

#: R22's two clauses, by the function that asserts them.
PAUSE_CLAUSES = (
    assertions.check_pause_stops_background_work,
    assertions.check_pause_holds_across_restart,
)


def a_stub(name: str, tmp_path: Path, at: str = ""):
    where = tmp_path / (at or name)
    where.mkdir(parents=True, exist_ok=True)
    return stubs.build(name, where)


def graded(assertion, name: str, tmp_path: Path, at: str = "", target=None):
    """Run one pause clause against `name`, with a never-stopped control beside it.

    The control is a second instance in an arena of its own, which is what the
    clause needs and the opposite of R13's pair: independence, so the control's
    own work cannot land in the counters the clause reads.
    """
    at = at or f"{name}-{assertion.__name__}"
    return assertion(target if target is not None else a_stub(name, tmp_path, at=at),
                     control=a_stub(name, tmp_path, at=f"{at}-control"))


# --------------------------------------------------------------------------
# The registry, and the sheet.
# --------------------------------------------------------------------------


def test_every_pause_clause_is_in_the_registry():
    """A check the registry does not name is dead code that looks like coverage."""
    registered = {cid: fn for cid, fn in assertions.ALL.items()}
    for fn in PAUSE_CLAUSES:
        assert fn in registered.values(), f"{fn.__name__} is in the module but not in ALL"


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_the_registry_maps_each_id_to_the_function_that_produces_it(assertion, tmp_path):
    """The id a check reports is the key it is registered under."""
    produced = graded(assertion, "stub-quiet", tmp_path)
    assert assertions.ALL[produced.check] is assertion


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_quiet_target_is_green(assertion, tmp_path):
    """An assertion that has only ever failed is as uninformative as one that never has."""
    check = graded(assertion, "stub-quiet", tmp_path)
    assert check.result == PASS


# --------------------------------------------------------------------------
# R22 — the two clauses, and the fixture that separates them.
# --------------------------------------------------------------------------


def test_a_control_that_answers_and_keeps_working_is_red(tmp_path):
    """The reply is honest and nothing stopped. Only the counters can tell."""
    check = graded(assertions.check_pause_stops_background_work,
                   "stub-ignores-pause", tmp_path)
    assert check.result == FAIL
    assert check.detail["pause_event"] == {"paused": True}, (
        "the fixture must answer its pause surface correctly, or the red proves "
        "only that a broken verb is visible"
    )
    assert check.detail["done_deltas_while_stopped"], (
        "a red must name the work that was done while the target was stopped"
    )


def test_a_pause_that_holds_only_while_the_process_lives_is_red(tmp_path):
    """Green on the clause that does not restart, red on the clause that does.

    Both verdicts come from the same fixture on purpose. The asymmetry is what
    shows the two clauses are not one clause written twice — a merged assertion
    would report a single red here and lose which half failed.
    """
    stopped = graded(assertions.check_pause_stops_background_work,
                     "stub-forgets-pause-on-restart", tmp_path, at="stopped")
    across = graded(assertions.check_pause_holds_across_restart,
                    "stub-forgets-pause-on-restart", tmp_path, at="across")
    assert stopped.result == PASS
    assert across.result == FAIL
    assert across.detail["restarted"] is True
    assert across.detail["resume_never_called"] is True, (
        "a harness that asked the target to carry on would be measuring its own request"
    )


def test_a_queued_change_is_not_work_done(tmp_path):
    """A stopped target may record that there is work to do later.

    The clause is about work being done, not about a target forgetting what it
    saw. A check grading every counter would redden a correct target that queues,
    so the fixture queues and the assertion must stay green — while the counter
    it moved is still visible in the detail rather than dropped.
    """
    target = a_stub("stub-quiet", tmp_path)
    original = target._edit_one_item

    def queues_while_stopped():
        event = original()
        if target._is_paused():
            # Written past `_bump`, which a stopped fixture no-ops: this models a
            # target that keeps noticing while it is stopped, which the base
            # fixture does not do and which the clause must not redden on.
            counters = target._counters()
            counters["work.record.edit.queued"] = (
                counters.get("work.record.edit.queued", 0) + 1)
            target._write(target._ledger(), json.dumps(counters))
        return event

    target._edit_one_item = queues_while_stopped
    check = graded(assertions.check_pause_stops_background_work, "stub-quiet",
                   tmp_path, at="queues", target=target)
    assert check.result == PASS
    assert check.detail["done_deltas_while_stopped"] == {}
    assert check.detail["all_deltas_while_stopped"] == {"work.record.edit.queued": 1}, (
        "what was not graded must still reach the artifact, or the reader cannot "
        "see what the clause let through"
    )


# --------------------------------------------------------------------------
# The states that are not verdicts.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_target_without_the_surface_is_not_offered_rather_than_red(assertion, tmp_path):
    """R22 is verified absent upstream, so this is the state a real run reports."""
    check = graded(assertion, "stub-verbless", tmp_path)
    assert check.result == NOT_OFFERED
    assert check.verb in ("pause", "status", "configure", "query")
    assert check.detail["why_absent"], "an absent verb carries the reason it is absent"


def _run_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "acceptance_run", REPO / "bench" / "acceptance" / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    return run


def _raises(*args, **kwargs):
    raise RuntimeError("this verb is broken on this target")


def test_one_raising_verb_does_not_take_the_egress_sweep_down_with_it(tmp_path):
    """A broken verb must not score a target red on a clause about egress.

    `drive()` is what `--drive` runs under the tracer, and it grades nothing: a
    target that raised at `query` after installing and configuring has still
    either reached off this machine or not, with the tracer watching throughout.
    An exception escaping instead ends that subprocess non-zero, which
    `check_no_egress` reads as its own failure.
    """
    target = a_stub("stub-quiet", tmp_path)
    target.query = _raises
    done = _run_module().drive(target)
    assert "raised: RuntimeError" in done["query"], (
        "a verb that raised must be recorded rather than propagated"
    )
    assert done["install"], "the verbs before it must still have been driven"


def test_every_verb_raising_is_recorded_and_never_a_red(tmp_path):
    """A target that exercised nothing is undecided on egress, not red on it.

    An earlier version re-raised here, which made the subprocess exit on a code
    `check_no_egress` grades as a failure — scoring a target that is not
    installed, or whose transport is down, red on a clause about egress. An
    instrument failure is never a red, and the incomplete run reaches the verdict
    as `DRIVE_INCOMPLETE` instead.
    """
    target = a_stub("stub-quiet", tmp_path, at="all-broken")
    for verb in ("install", "configure", "resume", "query"):
        setattr(target, verb, _raises)
    done = _run_module().drive(target)
    assert all("raised: RuntimeError" in v for v in done.values())


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_change_that_creates_no_work_leaves_the_clause_undecided(assertion, tmp_path):
    """The positive control, without which both clauses are a green about nothing.

    Their whole finding is that a counter did not move. A target whose change
    would not have moved one produces that finding whatever its control does, so
    the change is made once while running and the clause is only decided if it
    created work then.
    """
    control = a_stub("stub-quiet", tmp_path, at=f"{assertion.__name__}-control")
    control._edit_one_item = lambda: {
        "perturbation": assertions.durability.EDIT_ONE_ITEM, "sections": 0}
    check = assertion(a_stub("stub-quiet", tmp_path, at=assertion.__name__),
                      control=control)
    assert check.result == NOT_RUN
    assert "created no work" in check.detail["why"]


@pytest.mark.parametrize("fixture", [
    "stub-recomputes-whole-library-on-edit",
    "stub-duplicates-work-on-company",
])
@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_another_goal_s_fail_control_is_not_red_here(fixture, assertion, tmp_path):
    """A fixture built for one clause must not fail one it is not about.

    Both of these did, and neither by modelling anything about a pause: the
    honouring of it lived in `_edit_one_item`, which the first overrides, and in
    a first build the second is not idempotent about. The gate is now in `_bump`,
    where doing the work happens and no subclass can route around it.
    """
    check = graded(assertion, fixture, tmp_path)
    assert check.result == PASS


class _Counterless:
    """A target that answers every verb and reports no work counters."""

    settle_poll_s = 0.01

    def __init__(self, arena: Path):
        self.declaration = Declaration(
            name="counterless", revision="fixture",
            derived_state_roots=(arena,), query_transport="in process",
            default_configuration="the fixture's only configuration",
            process="none",
        )

    @contextmanager
    def running(self):
        yield

    def install(self): return {}
    def uninstall(self): return {}
    def configure(self): return {}
    def query(self, q, mode, limit): return {"hits": [{"item": "one"}]}
    def status(self): return {"embedding": {"locality": "local", "active": True}}
    def pause(self): return {}
    def resume(self): return {}


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_target_without_work_counters_is_not_run_rather_than_green(assertion, tmp_path):
    """Whether the work stopped cannot be read from a target that counts nothing."""
    check = assertion(_Counterless(tmp_path / assertion.__name__),
                      control=_Counterless(tmp_path / f"{assertion.__name__}-control"))
    assert check.result == NOT_RUN
    assert "work.<stage>.<trigger>.<outcome>" in check.detail["why"]


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_pause_surface_that_raises_is_not_run_rather_than_ending_the_run(
        assertion, tmp_path):
    """`assess` wraps no check in a try, so an unguarded verb loses the artifact.

    Not a hypothetical: the model-cache clause in this same change had to be
    guarded after a fixture's raising query ended a whole fail-control run with a
    traceback, every assertion after it unrecorded.
    """
    target = a_stub("stub-quiet", tmp_path, at=assertion.__name__)

    def raises():
        raise RuntimeError("the transport to this target died")

    target.pause = raises
    check = graded(assertion, "stub-quiet", tmp_path, at=f"{assertion.__name__}-raises",
                   target=target)
    assert check.result == NOT_RUN
    assert "pause surface raised" in check.detail["why"]


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_target_that_cannot_be_perturbed_is_not_run_rather_than_green(assertion, tmp_path):
    """A clause the harness has no way to drive is undecided, never passed."""

    class _NoPerturbation(_Counterless):
        def status(self):
            return {"embedding": {"locality": "local", "active": True},
                    "work": {"work.record.new.done": 1}}

    check = assertion(_NoPerturbation(tmp_path / assertion.__name__),
                      control=_NoPerturbation(tmp_path / f"{assertion.__name__}-c"))
    assert check.result == NOT_RUN


# --------------------------------------------------------------------------
# What the third review round found: three ways to a verdict about nothing.
# --------------------------------------------------------------------------


def test_startup_work_after_a_restart_is_not_graded_as_the_pause_failing(tmp_path):
    """The window opens after the restart settles, not before it.

    A target that scans or reconciles on start does work between the pause and
    the change, and reading the baseline across the restart puts that work inside
    the graded window — a red on a target whose pause held perfectly. The clause
    is about a change made AFTER the restart.
    """
    target = a_stub("stub-quiet", tmp_path)
    started = {"n": 0}
    original = target._on_start

    def works_on_start():
        original()
        started["n"] += 1
        # Written past `_bump`, which a stopped fixture no-ops: this is a target
        # doing startup work despite the pause, which is not this clause's
        # falsifier and must not be read as one.
        counters = target._counters()
        counters["work.record.startup.done"] = (
            counters.get("work.record.startup.done", 0) + 1)
        target._write(target._ledger(), json.dumps(counters))

    target._on_start = works_on_start
    check = graded(assertions.check_pause_holds_across_restart, "stub-quiet",
                   tmp_path, at="startup-work", target=target)
    assert started["n"] >= 2, "the clause must actually have restarted the target"
    assert check.result == PASS
    assert check.detail["done_deltas_while_stopped"] == {}


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_the_control_does_not_consume_the_graded_target_s_change(assertion, tmp_path):
    """A control that is a second phase of the same target eats the change.

    Where making the same change twice is a no-op the second time, a control run
    first on the graded target leaves the graded phase with nothing to find —
    for reasons that have nothing to do with the pause — and that lands as a
    pass. This target makes the change exactly once, ever, and the clause must
    still decide it, because the control happened somewhere else entirely.
    """
    target = a_stub("stub-quiet", tmp_path, at=assertion.__name__)
    original = target._edit_one_item
    spent = {"done": False}

    def only_once():
        if spent["done"]:
            return {"perturbation": assertions.durability.EDIT_ONE_ITEM, "sections": 0}
        spent["done"] = True
        return original()

    target._edit_one_item = only_once
    check = graded(assertion, "stub-quiet", tmp_path, at=assertion.__name__,
                   target=target)
    assert check.result == PASS
    assert check.detail["positive_control"]["done_deltas_on_a_never_stopped_instance"]


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_control_sharing_a_root_is_refused_rather_than_measured(assertion, tmp_path):
    """The opposite of R13's pair, and for the opposite reason.

    R13's two instances must resolve one data directory, because the clause is
    about two processes on one. Here they must not: a control sharing a root does
    its work into the very counters this clause reads, so the finding "no work
    happened while stopped" would be read off a ledger the control was writing.

    The guard reads what an adapter argued is NOT derived state as well, because
    that is where a target's source library is declared and where the change is
    actually made — two instances sharing one library would have the control
    consume the graded target's change, which is the same false pass by the other
    route. A declaration naming no path at all cannot demonstrate independence
    either way, and is refused rather than assumed.
    """
    where = tmp_path / assertion.__name__
    where.mkdir(parents=True, exist_ok=True)
    check = assertion(stubs.build("stub-quiet", where),
                      control=stubs.build("stub-quiet", where))
    assert check.result == NOT_RUN
    assert "share a declared path" in check.detail["why"]


def test_an_assertion_that_raises_is_recorded_rather_than_ending_the_run(tmp_path):
    """Every assertion after it would otherwise go unrecorded, and no artifact written.

    Guarding call sites inside each assertion does not converge — a review found
    the guards covering `query` while `install`, `configure` and `status` beside
    it stayed open, and `settle` reads `status` at five more points. The
    invariant belongs where every assertion passes through.
    """
    run_module = _run_module()

    def make(at: Path):
        at.mkdir(parents=True, exist_ok=True)
        target = stubs.build("stub-quiet", at)
        target.status = _raises
        return target

    result = run_module.assess(
        make, base_arena=tmp_path / "arena", log_dir=tmp_path / "trace",
        drive_argv_for=lambda at: ["true"])
    assert result.checks, "the run must have recorded every assertion"
    raised = [c for c in result.checks
              if c.result == NOT_RUN and "the assertion raised" in str(c.detail)]
    assert raised, "an assertion that raised must reach the artifact as not-run"
    assert result.summary()[FAIL] == 0, "an instrument failure is never a red"


def test_a_control_sharing_only_the_library_is_refused(tmp_path):
    """The other half of independence, and the one the stubs cannot reach.

    A real adapter's two instances take the same options, so they resolve the
    same source library — declared under `not_derived_state`, not under the
    derived-state roots. A guard reading only the roots would let the control
    make its change in the very library the graded target is about to change,
    consuming it and turning the clause into the false pass the control exists to
    prevent. The stubs edit an arena-local ledger, so nothing in the fixture
    matrix can catch this; it needs a declaration written for it.
    """
    library = tmp_path / "a-library"

    def instance(at: str):
        target = a_stub("stub-quiet", tmp_path, at=at)
        target.declaration = Declaration(
            name="shares-a-library", revision="fixture",
            derived_state_roots=(tmp_path / at / "data",),
            query_transport="in process", default_configuration="the only one",
            process="none",
            not_derived_state=((library, "the user's own library, not derived state"),),
        )
        return target

    check = assertions.check_pause_stops_background_work(
        instance("graded"), control=instance("control"))
    assert check.result == NOT_RUN
    assert "share a declared path" in check.detail["why"]


def test_a_lifecycle_that_never_starts_is_incomplete_rather_than_egress(tmp_path):
    """A target whose process never started has not attempted anything.

    `running()` raises before the verb loop is reached, so an uncaught one exits
    the drive subprocess on a code `check_no_egress` grades as a red — reporting
    a target that never ran as one that reached off this machine. It is the same
    incomplete run as a verb raising and exits the same way.
    """
    import subprocess

    done = subprocess.run(
        [sys.executable, str(REPO / "bench" / "acceptance" / "run.py"),
         "--adapter", "stub-quiet", "--arena", str(tmp_path / "arena"), "--drive"],
        capture_output=True, text=True, timeout=120, cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO / "bench")},
    )
    assert done.returncode == 0, f"the control arm must be a clean drive: {done.stderr}"

    run_module = _run_module()
    target = a_stub("stub-quiet", tmp_path, at="no-lifecycle")

    @contextmanager
    def never_starts():
        raise RuntimeError("this target's process did not start")
        yield  # pragma: no cover

    target.running = never_starts
    with pytest.raises(RuntimeError):
        run_module.drive(target)
