"""The volume experiment's plan: what it draws, and whether a run can be replayed.

Ticket 0727. Arm 5 repeated ONE action at two fixed cadences over an EMPTY
library in a process that never restarted, and its negative result reads
stronger than it is: 17 replacements of an idle add-on is not the state either
organic occurrence happened in. This suite owns the part of the widening that
can be checked without a Zotero -- the plan -- and in particular the property
the whole randomised arm rests on: a run that finally reproduces must be
replayable from its seed, or the reproduction is a story rather than a finding.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

from sitter_volume_experiment import ACTIONS, plan_cycles  # noqa: E402


class Args:
    """Just the fields `plan_cycles` reads."""

    def __init__(self, burst=8, spaced=42, burst_interval=8.0, spaced_interval=120.0):
        self.burst_cycles = burst
        self.spaced_cycles = spaced
        self.burst_interval_seconds = burst_interval
        self.spaced_interval_seconds = spaced_interval


def test_without_a_seed_the_plan_is_arm_5_unchanged():
    """The deterministic arm is the control every randomised run is read
    against, so it has to stay exactly what it was: burst then spaced, one
    action, the intervals the flags name."""
    plan = plan_cycles(Args(burst=3, spaced=4), None)
    assert [step.action for step in plan] == ["replace-disable-enable"] * 7
    assert [step.wait_seconds for step in plan] == [8.0] * 3 + [120.0] * 4


def test_a_seed_replays_exactly_and_a_different_seed_does_not():
    """The property the randomised arm rests on. A reproduction drawn from an
    unrecorded or unreplayable seed leaves the next reader with a state they
    cannot get back to -- which is where this ticket already is."""
    import random

    first = plan_cycles(Args(), random.Random(20260912))
    again = plan_cycles(Args(), random.Random(20260912))
    other = plan_cycles(Args(), random.Random(20260913))

    assert [(s.action, s.wait_seconds) for s in first] == [(s.action, s.wait_seconds) for s in again]
    assert [(s.action, s.wait_seconds) for s in first] != [(s.action, s.wait_seconds) for s in other]


def test_the_draw_reaches_every_action_and_both_ends_of_the_clock():
    """A distribution that never draws half its actions is a fixed script with
    extra steps, and one that never draws a short interval cannot revisit the
    rapid succession the 2026-09-08 recurrence had.

    Asserted over a long plan rather than a run's worth, so the arm is about the
    distribution and not about one seed's luck.
    """
    import random

    plan = plan_cycles(Args(burst=0, spaced=2000), random.Random(1))
    drawn = {step.action for step in plan}
    assert drawn == {name for name, _weight in ACTIONS}, drawn

    waits = [step.wait_seconds for step in plan]
    assert min(waits) < 5, min(waits)
    assert max(waits) > 300, max(waits)
    # Log-uniform, not uniform: a uniform draw over the same range would put
    # about nine tenths of its cycles above a minute, and the burst shape would
    # never be revisited. The median is the cheap check that it did not.
    median = sorted(waits)[len(waits) // 2]
    assert 20 < median < 80, median


@pytest.mark.parametrize("weight", [weight for _name, weight in ACTIONS])
def test_every_action_carries_a_positive_weight(weight):
    """A zero-weighted action is an action nobody will ever see drawn, and a
    table that silently contains one is a table that lies about its coverage."""
    assert weight > 0
