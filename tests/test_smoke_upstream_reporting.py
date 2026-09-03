"""The two reporting fields of `smoke_upstream.py`'s query check say what they measured.

Ticket 0621. Neither defect changed a verdict; both wrote a wrong number into a
committed artifact, which is worse than a red check because nothing protests.

**The warm figure kept the cold run.** The field was
`sorted(wall_ms)[1:]` — the sorted list minus its *minimum*. On a fresh data
directory the first query pays the model download and the ONNX session start, so
it is the largest number in the set: it survived into a field labelled warm while
the fastest warm query was the one discarded. The fixture below is built so the
true cold run is NOT the sorted minimum; the old expression cannot tell the two
apart on it, the new one can.

**The RRF counter read zero where every score was exactly the fusion value.** The
check compared the returned scores against a *contiguous prefix* of the series
`1/(60+rank)`. Item-level dedup in the query path leaves gaps in the ranks, so a
query whose hits skip a rank failed strict prefix equality even though each score
is exactly the fusion value for its own rank. The fixture below has a gap.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def load_smoke():
    spec = importlib.util.spec_from_file_location(
        "smoke_upstream", REPO / "bench" / "smoke_upstream.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = load_smoke()


def rrf(rank: int) -> float:
    """The fusion value a real run carries: the full double, not a rounded one.

    Upstream computes `1/(60+rank)` and serializes the double; the six-place
    rounding the old check applied is what let it accept almost any small float
    once the series grew dense. So the fixtures use the exact value, and
    `test_a_six_place_rounding_of_a_fusion_value_is_not_accepted` pins that a
    rounded stand-in is refused.
    """
    return 1 / (60 + rank)


# --------------------------------------------------------------------------
# Defect 1: cold versus warm
# --------------------------------------------------------------------------

#: Execution order matters: the first query is the cold one and it is the
#: slowest, so the sorted minimum (110.0) is a *warm* run. Any implementation
#: that sorts before dropping reports 110.0 as cold or keeps 900.0 as warm.
COLD_FIRST_RUNS = [
    {"q": "a", "wall_ms": 900.0, "hits": 1, "scores": [rrf(1)], "keys": ["A"]},
    {"q": "b", "wall_ms": 130.0, "hits": 1, "scores": [rrf(1)], "keys": ["B"]},
    {"q": "c", "wall_ms": 110.0, "hits": 1, "scores": [rrf(1)], "keys": ["C"]},
]

#: A warm data directory: the first query is not special, and nothing here is an
#: outlier. A reader must be able to tell this run from the one above.
ALL_WARM_RUNS = [
    {"q": "a", "wall_ms": 120.0, "hits": 1, "scores": [rrf(1)], "keys": ["A"]},
    {"q": "b", "wall_ms": 130.0, "hits": 1, "scores": [rrf(1)], "keys": ["B"]},
    {"q": "c", "wall_ms": 110.0, "hits": 1, "scores": [rrf(1)], "keys": ["C"]},
]


def test_cold_field_is_the_first_query_in_execution_order():
    fields = smoke.timing_fields(COLD_FIRST_RUNS)
    assert fields["cold_ms"] == 900.0, (
        "the cold field must be the FIRST query in execution order, not the "
        "sorted minimum — 110.0 here is a warm run that merely finished fastest"
    )


def test_warm_field_excludes_the_cold_run_and_keeps_the_fastest():
    fields = smoke.timing_fields(COLD_FIRST_RUNS)
    assert 900.0 not in fields["warm_ms"], "the cold run survived into the warm field"
    assert 110.0 in fields["warm_ms"], (
        "the fastest warm query was discarded — the old `sorted(...)[1:]` drops "
        "the minimum, which is a warm run, not the cold one"
    )
    assert sorted(fields["warm_ms"]) == [110.0, 130.0]


def test_fresh_and_warm_runs_are_distinguishable():
    """Exit criterion: a reader can tell a fresh-directory run from a warm one."""
    fresh = smoke.timing_fields(COLD_FIRST_RUNS)
    warm = smoke.timing_fields(ALL_WARM_RUNS)
    assert fresh["cold_ms"] != warm["cold_ms"]
    assert fresh["warm_ms"] == warm["warm_ms"], (
        "the two fixtures differ only in their first query, so only the cold "
        "field should move"
    )
    # And the fields carry their own labels, so the artifact says what they include.
    for f in (fresh, warm):
        assert isinstance(f.get("timing_note"), str) and f["timing_note"], (
            "the timing fields must be labelled with what they include"
        )


def test_timing_fields_on_no_runs():
    fields = smoke.timing_fields([])
    assert fields["cold_ms"] is None
    assert fields["warm_ms"] == []


def test_timing_fields_on_a_single_run():
    fields = smoke.timing_fields(COLD_FIRST_RUNS[:1])
    assert fields["cold_ms"] == 900.0
    assert fields["warm_ms"] == [], "one query is the cold one; there is no warm figure"


# --------------------------------------------------------------------------
# Defect 2: rank fusion with gaps
# --------------------------------------------------------------------------

#: Ranks 1, 3, 4 — item-level dedup dropped rank 2. Every score is exactly the
#: fusion value for its own rank; a contiguous-prefix comparison reads zero.
GAPPED_RUNS = [
    {"q": "a", "wall_ms": 900.0, "hits": 3,
     "scores": [rrf(1), rrf(3), rrf(4)], "keys": ["A", "B", "C"]},
    {"q": "b", "wall_ms": 130.0, "hits": 2,
     "scores": [rrf(2), rrf(5)], "keys": ["D", "E"]},
]

#: A control that must NOT be counted: a genuine similarity magnitude, which is
#: what the field exists to distinguish a relabelled rank from.
SIMILARITY_RUNS = [
    {"q": "a", "wall_ms": 120.0, "hits": 2,
     "scores": [0.8123, 0.7734], "keys": ["A", "B"]},
]


def test_gapped_ranks_are_still_rank_shaped():
    agree = smoke.rank_fusion_agreement(GAPPED_RUNS, limit=5)
    assert agree["hits_compared"] == 5
    assert agree["hits_matching_own_rank"] == 5, (
        "each score is exactly 1/(60+rank) for ITS OWN rank; a contiguous-prefix "
        "comparison mistakes the dedup gap for a mismatch"
    )
    assert agree["queries_all_hits_rank_shaped"] == 2


def test_similarity_scores_are_not_counted_as_rank_shaped():
    """The discriminating control: this field must be able to come out the other way."""
    agree = smoke.rank_fusion_agreement(SIMILARITY_RUNS, limit=5)
    assert agree["hits_compared"] == 2
    assert agree["hits_matching_own_rank"] == 0
    assert agree["queries_all_hits_rank_shaped"] == 0


def test_out_of_order_ranks_are_not_rank_shaped():
    """A fused list is ordered by score; ranks that go backwards are not a fusion."""
    runs = [{"q": "a", "wall_ms": 1.0, "hits": 2,
             "scores": [rrf(4), rrf(1)], "keys": ["A", "B"]}]
    agree = smoke.rank_fusion_agreement(runs, limit=5)
    assert agree["hits_matching_own_rank"] == 2
    assert agree["queries_all_hits_rank_shaped"] == 0, (
        "every score matches some rank, but descending ranks are not a "
        "rank-fusion ordering"
    )


def test_hits_compared_is_stated():
    """Ticket action 1: the artifact states how many hits were compared."""
    agree = smoke.rank_fusion_agreement(GAPPED_RUNS, limit=5)
    assert agree["hits_compared"] == sum(len(r["scores"]) for r in GAPPED_RUNS)


def test_zero_hits_compare_to_nothing():
    runs = [{"q": "a", "wall_ms": 1.0, "hits": 0, "scores": [], "keys": []}]
    agree = smoke.rank_fusion_agreement(runs, limit=5)
    assert agree["hits_compared"] == 0
    assert agree["queries_all_hits_rank_shaped"] == 0, (
        "a query that returned nothing has not demonstrated a rank-shaped score"
    )


def test_a_small_float_far_down_the_series_is_not_accepted():
    """Red team, round 1 of PR #304: the inversion must not say yes to anything.

    The series thins out as the rank grows — past a few hundred, consecutive
    `1/(60+rank)` values sit closer together than a six-place comparison can
    separate, so `round(x, 6)` equality accepts 0.86 of arbitrary floats in
    `[0.0005, 0.001)`. That is exactly the regime this field exists to police: a
    raw similarity magnitude leaking through where a relabelled rank was
    promised. `0.00091` inverts to rank 1039, which is neither a dedup gap nor
    equal to `1/1099` at any honest tolerance.
    """
    runs = [{"q": "a", "wall_ms": 1.0, "hits": 1, "scores": [0.00091], "keys": ["A"]}]
    agree = smoke.rank_fusion_agreement(runs, limit=5)
    assert agree["hits_matching_own_rank"] == 0
    assert agree["queries_all_hits_rank_shaped"] == 0


def test_a_six_place_rounding_of_a_fusion_value_is_not_accepted():
    """The tolerance is what does the work above, so pin it in isolation."""
    assert smoke._rrf_rank_of(1 / 61, limit=5) == 1
    assert smoke._rrf_rank_of(round(1 / 61, 6), limit=5) is None


def test_a_rank_far_past_the_limit_is_not_a_dedup_gap():
    """Dedup gaps are small; the cap is what says so."""
    assert smoke._rrf_rank_of(1 / (60 + 12), limit=5) == 12
    assert smoke._rrf_rank_of(1 / (60 + 200), limit=5) is None


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.5, 0.0, None, True, "0.016"])
def test_a_score_that_is_not_a_positive_finite_number_is_refused(score):
    """NaN escapes a `<= 0` guard under IEEE 754, and `round(1/nan)` raises.

    That exception would propagate out of `check_query_answers` through `main`'s
    bare `try/finally`, before the JSON is written — losing every check's result,
    not just this field.
    """
    assert smoke._rrf_rank_of(score, limit=5) is None


#: The run that produced both wrong numbers, read off the committed artifact
#: `bench/results/smoke-1.13.0/checks.json`. Kept as a fixture rather than
#: loaded, so the test states what it is regressing against and does not go
#: quiet if that file is ever rewritten. Note the ranks: the first query ends on
#: `1/66` with `--limit 5`, because deduplication happens after fusion — a
#: rank-bounded search would call that a mismatch for the same reason the prefix
#: comparison did.
ARTIFACT_1_13_0_RUNS = [
    {"q": "carbon tax and household energy spending", "wall_ms": 11995.4, "hits": 5,
     "scores": [1 / 61, 1 / 62, 1 / 63, 1 / 65, 1 / 66],
     "keys": ["ZKRX27ZV", "XPVRCKU8", "CJVEWKK3", "JBIVTK4H", "6424DHF8"]},
    {"q": "permafrost thaw feedback", "wall_ms": 22.8, "hits": 3,
     "scores": [1 / 61, 1 / 68, 1 / 72],
     "keys": ["FK8J46GB", "Z6Q7IMNJ", "RN8Z26LY"]},
    {"q": "integrated assessment model discount rate", "wall_ms": 20.3, "hits": 5,
     "scores": [1 / 61, 1 / 62, 1 / 63, 1 / 64, 1 / 66],
     "keys": ["H5R3XXTM", "UQG8B2QW", "NGVECB7I", "UT4FF28F", "UEYCD3HH"]},
]


def test_real_v1_13_0_run_reports_the_download_as_cold():
    fields = smoke.timing_fields(ARTIFACT_1_13_0_RUNS)
    assert fields["cold_ms"] == 11995.4
    assert fields["warm_ms"] == [22.8, 20.3], (
        "the committed artifact reported warm_ms = [22.8, 11995.4]: it kept the "
        "12-second model download and dropped the 20.3 ms query"
    )


def test_real_v1_13_0_run_is_rank_shaped_throughout():
    agree = smoke.rank_fusion_agreement(ARTIFACT_1_13_0_RUNS, limit=5)
    assert agree["hits_compared"] == 13
    assert agree["hits_matching_own_rank"] == 13
    assert agree["queries_all_hits_rank_shaped"] == 3, (
        "the committed artifact reported 0: every score is exactly the fusion "
        "value for its own rank, and the zero was the check's, not the target's"
    )


# --------------------------------------------------------------------------
# The check as a whole, driven through a fake server
# --------------------------------------------------------------------------

class FakeServer:
    """Answers `tools/call` with canned hits, in the order the queries are asked."""

    def __init__(self, per_query_hits):
        self._hits = list(per_query_hits)
        self.calls = 0

    def call(self, method, params):
        hits = self._hits[self.calls]
        self.calls += 1
        return {"result": {"structuredContent": {"hits": hits}}}


@pytest.mark.parametrize("limit", [5])
def test_check_query_answers_reports_both_fields(limit):
    s = FakeServer([
        [{"score": rrf(1), "itemKey": "A"}, {"score": rrf(3), "itemKey": "B"}],
        [{"score": rrf(1), "itemKey": "C"}],
    ])
    out = smoke.check_query_answers(s, ["q1", "q2"], limit)
    detail = out["detail"]
    assert out["result"] == "pass"
    assert detail["cold_ms"] == detail["runs"][0]["wall_ms"], (
        "the cold field must be the first query in execution order"
    )
    assert detail["warm_ms"] == [r["wall_ms"] for r in detail["runs"][1:]]
    assert detail["hits_compared"] == 3
    assert detail["hits_matching_own_rank"] == 3, (
        "the gapped second hit of the first query is exactly 1/(60+3)"
    )
