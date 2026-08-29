"""Tests for the latency block bench/query.py grew for X2 (ticket 0014).

Written because the driver the runbook names for X2 recorded hits and peak RSS and no
timing at all, so the step could not produce the p95 its decision rule is stated against.
A driver that cannot measure the quantity it is invoked for is the "all clear
indistinguishable from could not look" shape, and the fix needs a guard of its own.

Only the pure functions are covered here. Driving the MCP server needs a built fork and a
1 GB index, which is the workstation substrate, not the fast tier.

    python3 -m pytest tests/ -q
"""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("q", REPO / "bench" / "query.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


q = load()


# --- percentile --------------------------------------------------------------------

def test_p95_of_twenty_samples_is_the_second_largest():
    # Nearest rank: ceil(0.95 * 20) = 19, so the 19th of 20 sorted samples. This is the
    # case the flag docstring warns about — with one pass over 20 queries the p95 names
    # the second-slowest query rather than measuring a tail.
    samples = [float(i) for i in range(1, 21)]
    assert q.percentile(samples, 95) == 19.0


def test_percentile_returns_an_observed_sample_never_an_interpolation():
    # Sabotage check: switching to a linear-interpolation percentile returns 19.05 here.
    # The figure feeds a latency budget, so it must be a duration that actually occurred.
    samples = [float(i) for i in range(1, 21)]
    assert q.percentile(samples, 95) in samples


def test_p50_of_an_even_run_takes_the_lower_middle_not_their_mean():
    assert q.percentile([10.0, 20.0, 30.0, 40.0], 50) == 20.0


def test_percentile_ignores_input_order():
    assert q.percentile([500.0, 1.0, 7.0], 95) == q.percentile([1.0, 7.0, 500.0], 95)


def test_p100_and_p0_are_the_extremes():
    samples = [3.0, 1.0, 2.0]
    assert q.percentile(samples, 100) == 3.0
    # Rank ceil(0) = 0 is clamped up to the first sample rather than indexing [-1],
    # which in Python would silently return the MAXIMUM for a minimum-percentile ask.
    assert q.percentile(samples, 0) == 1.0


def test_percentile_of_nothing_raises_instead_of_reporting_zero():
    # The module's standing rule (see vmhwm_kb): a measurement is never invented. A p95
    # of 0.0 ms would be published as a passing latency figure.
    with pytest.raises(ValueError):
        q.percentile([], 95)


# --- summarize ---------------------------------------------------------------------

def test_summarize_reports_the_run_it_was_given():
    got = q.summarize([100.0, 200.0, 300.0, 400.0])
    assert got == {"n": 4, "min_ms": 100.0, "p50_ms": 200.0, "p95_ms": 400.0,
                   "max_ms": 400.0}


def test_summarize_of_an_empty_population_is_none_not_a_block_of_zeros():
    # A single-pass run has no warm samples. The artifact must say "not measured", so a
    # reader cannot mistake an absent population for a fast one.
    assert q.summarize([]) is None


def test_a_single_sample_is_its_own_every_statistic():
    assert q.summarize([42.0]) == {"n": 1, "min_ms": 42.0, "p50_ms": 42.0,
                                   "p95_ms": 42.0, "max_ms": 42.0}
