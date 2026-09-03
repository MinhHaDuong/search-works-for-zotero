"""Goal 1's two remaining clauses decide, and say so when they cannot decide.

README.md's goals ladder puts R10, R15, R22 and R31 on the lowest rung and rules
the method: the assertions for a rung are built before anything on it is made to
work, because until they exist a row can only be `code` or `inferred` — a claim
about nobody. R10 and R15 arrived with the acceptance layer; these are the other
two, and this file is what stops each of them from being a habit.

Four defects it guards, and each of them produces a **green** rather than an
error, which is why they need fixtures rather than a careful reading.

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

**A configuration graded by whether the call returned.** R31's defect is an
order, not an exception: the configuration is accepted, and what was accepted
fails later at the query that first invokes it. `stub-configures-blind` is that
order. Its mirror — a target that raises at `configure` — must be green, because
failing loudly before use is the clause's other branch, and a check that reddens
on any exception scores the two identically.

**An instrument that could not look, read as a verdict.** A target with no work
counters cannot decide the pause clauses, and a target with no such control at
all is a third finding rather than a red. R22 is *verified absent* upstream, so
`not-offered` is the state the layer will actually report against a real target
today; a state no fixture produces is a state nobody has checked survives the
artifact.
"""

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

#: The rung's two new clauses, by the function that asserts them.
PAUSE_CLAUSES = (
    assertions.check_pause_stops_background_work,
    assertions.check_pause_holds_across_restart,
)
GOAL_1_CLAUSES = (*PAUSE_CLAUSES, assertions.check_configure_proves_it_works_here)


def a_stub(name: str, tmp_path: Path, at: str = ""):
    where = tmp_path / (at or name)
    where.mkdir(parents=True, exist_ok=True)
    return stubs.build(name, where)


# --------------------------------------------------------------------------
# The registry, and the sheet.
# --------------------------------------------------------------------------


def test_every_goal_1_clause_is_in_the_registry():
    """A check the registry does not name is dead code that looks like coverage."""
    registered = {cid: fn for cid, fn in assertions.ALL.items()}
    for fn in GOAL_1_CLAUSES:
        assert fn in registered.values(), f"{fn.__name__} is in the module but not in ALL"


@pytest.mark.parametrize("assertion", GOAL_1_CLAUSES)
def test_the_registry_maps_each_id_to_the_function_that_produces_it(assertion, tmp_path):
    """The id a check reports is the key it is registered under."""
    produced = assertion(a_stub("stub-quiet", tmp_path, at=assertion.__name__))
    assert assertions.ALL[produced.check] is assertion


@pytest.mark.parametrize("assertion", GOAL_1_CLAUSES)
def test_a_quiet_target_is_green(assertion, tmp_path):
    """An assertion that has only ever failed is as uninformative as one that never has."""
    check = assertion(a_stub("stub-quiet", tmp_path, at=assertion.__name__))
    assert check.result == PASS


# --------------------------------------------------------------------------
# R22 — the two clauses, and the fixture that separates them.
# --------------------------------------------------------------------------


def test_a_control_that_answers_and_keeps_working_is_red(tmp_path):
    """The reply is honest and nothing stopped. Only the counters can tell."""
    check = assertions.check_pause_stops_background_work(
        a_stub("stub-ignores-pause", tmp_path))
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
    stopped = assertions.check_pause_stops_background_work(
        a_stub("stub-forgets-pause-on-restart", tmp_path, at="stopped"))
    across = assertions.check_pause_holds_across_restart(
        a_stub("stub-forgets-pause-on-restart", tmp_path, at="across"))
    assert stopped.result == PASS
    assert across.result == FAIL
    assert across.detail["restarted"] is True
    assert across.detail["resume_called"] is False, (
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
            target._bump(work__record__edit__queued=1)
        return event

    target._edit_one_item = queues_while_stopped
    check = assertions.check_pause_stops_background_work(target)
    assert check.result == PASS
    assert check.detail["done_deltas_while_stopped"] == {}
    assert check.detail["all_deltas_while_stopped"] == {"work.record.edit.queued": 1}, (
        "what was not graded must still reach the artifact, or the reader cannot "
        "see what the clause let through"
    )


# --------------------------------------------------------------------------
# R31 — the order, not the exception.
# --------------------------------------------------------------------------


def test_a_configuration_accepted_while_dead_is_red(tmp_path):
    """The red is the target's own report, not an exception."""
    check = assertions.check_configure_proves_it_works_here(
        a_stub("stub-configures-blind", tmp_path))
    assert check.result == FAIL
    assert check.detail["configure_event"]["validated"] is False
    assert check.detail["embedder_active_after_configure"] is False


@pytest.mark.parametrize("surface", ["configure", "query"])
def test_a_surface_that_raises_is_not_run_rather_than_a_verdict(surface, tmp_path):
    """Neither direction of the exception reading survives, and that is the point.

    The first version of this clause graded a raising `configure` green — it
    "failed loudly" — and a raising `query` red — it "could not answer". The
    layer cannot tell a target refusing a configuration from a transport that
    died, so one reading manufactured a green out of a broken instrument and the
    other manufactured a red out of the same event one verb later. Both are
    `not-run`, and this test is parametrized over the pair so that reintroducing
    either asymmetry fails here.
    """
    target = a_stub("stub-quiet", tmp_path, at=surface)

    def raises(*args, **kwargs):
        raise RuntimeError("the transport to this target died")

    setattr(target, surface, raises)
    check = assertions.check_configure_proves_it_works_here(target)
    assert check.result == NOT_RUN
    assert "RuntimeError" in check.detail["why"]
    assert "cannot tell" in check.detail["why"]


def test_a_target_reporting_no_embedder_state_leaves_the_clause_undecided(tmp_path):
    """Whether what was accepted is in effect cannot be read from silence."""
    target = a_stub("stub-quiet", tmp_path)
    target.status = lambda: {"embedding": {}, "work": {}}
    check = assertions.check_configure_proves_it_works_here(target)
    assert check.result == NOT_RUN
    assert "no embedder state" in check.detail["why"]


def test_an_empty_answer_is_an_answer(tmp_path):
    """A correctly configured target holding nothing yet must not redden this."""
    target = a_stub("stub-quiet", tmp_path)
    target.query = lambda q, mode, limit: {"hits": []}
    check = assertions.check_configure_proves_it_works_here(target)
    assert check.result == PASS
    assert check.detail["hits_after_configure"] == 0


# --------------------------------------------------------------------------
# The states that are not verdicts.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("assertion", GOAL_1_CLAUSES)
def test_a_target_without_the_surface_is_not_offered_rather_than_red(assertion, tmp_path):
    """R22 is verified absent upstream, so this is the state a real run reports."""
    check = assertion(a_stub("stub-verbless", tmp_path, at=assertion.__name__))
    assert check.result == NOT_OFFERED
    assert check.verb in ("pause", "status", "configure", "query")
    assert check.detail["why_absent"], "an absent verb carries the reason it is absent"


def test_a_raising_verb_does_not_take_the_egress_sweep_down_with_it(tmp_path):
    """One fixture's broken verb must not score every target red on another clause.

    `drive()` is what `--drive` runs under the tracer, and it grades nothing: the
    egress clause is about what a default-configuration run touched, and a target
    that raises at `query` has still either reached off this machine or not. An
    exception escaping instead ends that subprocess non-zero, which
    `check_no_egress` reads as its own failure — R10 red on a target for a defect
    in R31's fixture. Reproduced against `stub-configures-blind` before the guard.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "acceptance_run", REPO / "bench" / "acceptance" / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)

    done = run.drive(a_stub("stub-configures-blind", tmp_path))
    assert "raised: RuntimeError" in done["query"], (
        "a verb that raised must be recorded rather than propagated"
    )
    assert done["install"], "the verbs before it must still have been driven"


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
    check = assertion(_Counterless(tmp_path))
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
    check = assertion(target)
    assert check.result == NOT_RUN
    assert "pause surface raised" in check.detail["why"]


@pytest.mark.parametrize("assertion", PAUSE_CLAUSES)
def test_a_target_that_cannot_be_perturbed_is_not_run_rather_than_green(assertion, tmp_path):
    """A clause the harness has no way to drive is undecided, never passed."""

    class _NoPerturbation(_Counterless):
        def status(self):
            return {"embedding": {"locality": "local", "active": True},
                    "work": {"work.record.new.done": 1}}

    check = assertion(_NoPerturbation(tmp_path))
    assert check.result == NOT_RUN


def test_a_target_that_reports_no_hits_leaves_the_configure_clause_undecided(tmp_path):
    """"It works here" cannot be read from the fact that a call returned."""

    class _Hitless(_Counterless):
        def query(self, q, mode, limit):
            return {"answered": True}

    check = assertions.check_configure_proves_it_works_here(_Hitless(tmp_path))
    assert check.result == NOT_RUN
    assert "nothing here to be read from" in check.detail["why"]
