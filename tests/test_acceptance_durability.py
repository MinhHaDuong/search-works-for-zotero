"""Goal 2's assertions decide the clause, and say so when they cannot decide it.

Four defects this guards, each of which produces a *green* rather than an error
— which is why they need a test rather than a careful reading.

**A one-detector resync check.** R3's resync clause reads two things: nothing was
recomputed, and the verification that a resync consists of actually ran. The
second is easy to drop as redundant, and dropping it makes the check pass a
target that did nothing at all — one whose signals never moved and whose hashes
were never verified reports exactly the zero `*.done` a correct target reports.
`test_a_resync_that_verified_nothing_is_red` is the fixture for that, and it is
the one that fails against a done-only implementation.

**A missing instrument read as a pass.** Three of these clauses cannot be decided
without something the target must provide: work counters, a hit list, a way to
perturb its storage. Each absence has to reach the artifact as `not-run`. A
harness that returned `pass` there would report the same verdict whether the
target is correct or the harness could not look.

**A second process that is not one.** R13's clauses are about two processes on
*one* data directory. Two adapter instances that resolved different roots would
run happily and assert nothing, so the mismatch is refused rather than measured.

**An assertion that is not run at all.** `assertions.ALL` is the registry the
layer's readers and the driver both go by; a check that exists in `durability.py`
and not in `ALL` is dead code that looks like coverage.
"""

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance import durability  # noqa: E402
from acceptance.adapters import stubs  # noqa: E402
from acceptance.assertions import ALL as REGISTRY  # noqa: E402
from acceptance.interface import FAIL, NOT_RUN, PASS, Declaration  # noqa: E402


def a_stub(name: str, tmp_path: Path):
    where = tmp_path / name
    where.mkdir(parents=True, exist_ok=True)
    return stubs.build(name, where)


# --------------------------------------------------------------------------
# The registry, and what it is for.
# --------------------------------------------------------------------------


def test_every_goal_2_assertion_is_in_the_registry():
    """A check the registry does not name is dead code that looks like coverage."""
    missing = sorted(set(durability.ALL) - set(REGISTRY))
    assert not missing, f"{missing} are in durability.ALL but not in assertions.ALL"


def test_the_registry_maps_each_id_to_the_function_that_produces_it(tmp_path):
    """The id a check reports is the key it is registered under.

    A mismatch is invisible in every green run and turns the artifact's own index
    into a lie the moment anything reads it by id.
    """
    target = a_stub("stub-quiet", tmp_path)
    second = stubs.build("stub-quiet", tmp_path / "stub-quiet")
    for cid, fn in durability.ALL.items():
        produced = (fn(target, second=second) if cid in durability.NEEDS_A_SECOND_TARGET
                    else fn(target))
        assert produced.check == cid


# --------------------------------------------------------------------------
# R3 — the two detectors, and the one that is easy to drop.
# --------------------------------------------------------------------------


def test_a_clean_resync_is_green(tmp_path):
    check = durability.check_identical_resync_recomputes_nothing(
        a_stub("stub-quiet", tmp_path))
    assert check.result == PASS
    assert check.detail["recomputed"] == {}
    assert check.detail["verified_as_noop"], "a green must have seen the verification run"


def test_a_resync_that_recomputed_is_red(tmp_path):
    check = durability.check_identical_resync_recomputes_nothing(
        a_stub("stub-churns-on-resync", tmp_path))
    assert check.result == FAIL
    assert check.detail["recomputed"], "the red must name what was recomputed"


def test_a_resync_that_verified_nothing_is_red(tmp_path):
    """The detector that a done-only implementation drops, and the reason for two.

    This fixture recomputes nothing — and it verified nothing, because its
    reconcile tick never ran. Read on the `done` outcome alone it is
    indistinguishable from a correct target, which is the false green this whole
    harness exists to refuse. A done-only implementation passes every other test
    in this file and fails only this one.
    """
    check = durability.check_identical_resync_recomputes_nothing(
        a_stub("stub-verifies-nothing-on-resync", tmp_path))
    assert check.result == FAIL
    assert check.detail["recomputed"] == {}, (
        "this fixture recomputes nothing; if the red came from a recompute the test is "
        "passing for the wrong reason and the second detector is still unexercised")
    assert check.detail["verified_as_noop"] == {}


def test_an_edit_that_recomputes_the_whole_library_is_red(tmp_path):
    check = durability.check_edit_recomputes_only_what_changed(
        a_stub("stub-recomputes-whole-library-on-edit", tmp_path))
    assert check.result == FAIL
    assert check.detail["missing_or_wrong"] or check.detail["unexpected"]


def test_an_edit_recomputing_only_its_own_sections_is_green(tmp_path):
    check = durability.check_edit_recomputes_only_what_changed(
        a_stub("stub-quiet", tmp_path))
    assert check.result == PASS
    assert check.detail["expected_done_deltas"] == check.detail["observed_done_deltas"]


# --------------------------------------------------------------------------
# R13 — two processes, and what makes them two.
# --------------------------------------------------------------------------


def test_two_processes_on_one_directory_are_green_when_nothing_breaks(tmp_path):
    where = tmp_path / "shared"
    where.mkdir()
    check = durability.check_two_processes_both_answer(
        stubs.build("stub-quiet", where), second=stubs.build("stub-quiet", where))
    assert check.result == PASS
    assert check.detail["hits_third_after_both_stopped"], (
        "the third process is the detector that sees corruption left behind; a green "
        "that never got an answer from it has asserted only half the clause")


def test_an_index_left_unreadable_after_the_pair_is_red(tmp_path):
    where = tmp_path / "shared"
    where.mkdir()
    check = durability.check_two_processes_both_answer(
        stubs.build("stub-corrupts-on-company", where),
        second=stubs.build("stub-corrupts-on-company", where))
    assert check.result == FAIL
    assert check.detail["failures"], "the red must name what happened"
    assert check.detail["hits_second_while_first_live"] is not None, (
        "this fixture answers correctly while the pair is live; a red raised during the "
        "pair phase means the third-process detector is still unexercised")


def test_a_second_process_that_redoes_settled_work_is_red(tmp_path):
    where = tmp_path / "shared"
    where.mkdir()
    check = durability.check_two_processes_do_not_duplicate_work(
        stubs.build("stub-duplicates-work-on-company", where),
        second=stubs.build("stub-duplicates-work-on-company", where))
    assert check.result == FAIL
    assert check.detail["recomputed_on_company"]


def test_two_targets_on_different_roots_are_refused_rather_than_measured(tmp_path):
    """Two instances that do not share a root are not two processes on one directory."""
    check = durability.check_two_processes_both_answer(
        a_stub("stub-quiet", tmp_path), second=a_stub("stub-strays", tmp_path))
    assert check.result == NOT_RUN
    assert "same derived-state root" in check.detail["why"]


# --------------------------------------------------------------------------
# R23 — ending up serving, in both directions.
# --------------------------------------------------------------------------


def test_a_stamp_flip_that_keeps_serving_is_green(tmp_path):
    check = durability.check_foreign_stamp_ends_up_serving(a_stub("stub-quiet", tmp_path))
    assert check.result == PASS
    assert set(check.detail["arms"]) == {durability.RESTAMP_OLDER, durability.RESTAMP_NEWER}, (
        "both directions are the clause; a green from one of them is half an answer")
    assert not check.detail["a_file_disappeared"]


def test_a_stamp_flip_that_abandons_the_index_is_red(tmp_path):
    check = durability.check_foreign_stamp_ends_up_serving(
        a_stub("stub-abandons-foreign-stamp", tmp_path))
    assert check.result == FAIL
    assert check.detail["baseline_hits"], (
        "the baseline must have served something, or an empty answer afterwards proves "
        "nothing")
    assert not check.detail["arms"][durability.RESTAMP_OLDER]["serving"]


# --------------------------------------------------------------------------
# The instruments, and their absence.
# --------------------------------------------------------------------------


class _Counterless:
    """A target that answers every verb and reports no work counters at all.

    Written here rather than added to the fixtures because its point is the
    absence of one field, and a fixture in `stubs.py` earns its place by
    modelling a defect a real target could have.
    """

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


@pytest.mark.parametrize("assertion", [
    durability.check_edit_recomputes_only_what_changed,
    durability.check_identical_resync_recomputes_nothing,
])
def test_a_target_without_work_counters_is_not_run_rather_than_green(assertion, tmp_path):
    check = assertion(_Counterless(tmp_path))
    assert check.result == NOT_RUN
    assert "work.<stage>.<trigger>.<outcome>" in check.detail["why"]


def test_a_target_that_cannot_be_perturbed_is_not_run_rather_than_green(tmp_path):
    """A clause the harness has no way to drive is undecided, never passed."""

    class _NoPerturbation(_Counterless):
        def status(self):
            return {"embedding": {"locality": "local", "active": True},
                    "work": {"work.record.new.done": 1}}

    check = durability.check_edit_recomputes_only_what_changed(_NoPerturbation(tmp_path))
    assert check.result == NOT_RUN
    assert durability.EDIT_ONE_ITEM in check.detail["why"]


def test_a_target_that_reports_no_hits_leaves_the_serving_clause_undecided(tmp_path):
    """'It ends up serving' cannot be read from the fact that a call returned."""

    class _Hitless(_Counterless):
        def query(self, q, mode, limit):
            return {"served": True, "hits": None}

    check = durability.check_foreign_stamp_ends_up_serving(_Hitless(tmp_path))
    assert check.result == NOT_RUN
    assert "reporting what it matched" in check.detail["why"]


def test_an_empty_baseline_leaves_the_serving_clause_undecided(tmp_path):
    """An index that served nothing to begin with cannot show that it stopped."""

    class _Empty(_Counterless):
        def query(self, q, mode, limit):
            return {"hits": []}

    check = durability.check_foreign_stamp_ends_up_serving(_Empty(tmp_path))
    assert check.result == NOT_RUN


def test_the_counter_name_parser_ignores_names_that_are_not_work_counters():
    """`work.<stage>.<trigger>.<outcome>` and nothing else.

    The fixtures keep bookkeeping of their own in the same ledger, so a parser
    that read any dotted name as a work counter would let a fixture's private
    state reach a verdict.
    """
    assert durability.outcome_of("work.embed.resync.noop") == "noop"
    assert durability.trigger_of("work.embed.resync.noop") == "resync"
    assert durability.stage_of("work.embed.resync.noop") == "embed"
    for not_one in ("live", "corrupt", "processes", "work.embed.done", "embed.resync.noop"):
        assert durability.outcome_of(not_one) == ""
        assert durability.trigger_of(not_one) == ""
        assert durability.stage_of(not_one) == ""
