"""The golden scorer can land before the private-free corpus without lying green.

Ticket 0029 owns the pinned set and the Zotero-free replay harness.  Ticket 0581
owns the readings over that set.  These tests exercise the latter against small,
invented answer sets; they neither invent corpus documents nor copy a threshold
out of SPEC.md.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "SPEC.md"
DRIVER = REPO / "bench" / "golden_gate.py"

sys.path.insert(0, str(REPO / "bench"))

from golden_gate import (  # noqa: E402
    FAIL,
    NOT_RUN,
    PASS,
    InputError,
    evaluate,
    load_thresholds,
)


def query(
    qid: str,
    *,
    slice_: str = "monolingual",
    facet: str = "core",
    pinned: list[str] | None = None,
    baseline: list[str] | None = None,
    candidate: list[str] | None = None,
) -> dict:
    return {
        "id": qid,
        "slice": slice_,
        "facet": facet,
        "pinned_answers": [f"{qid}-answer"] if pinned is None else pinned,
        "baseline_answers": (
            [f"{qid}-answer", f"{qid}-other"] if baseline is None else baseline
        ),
        "candidate_answers": (
            [f"{qid}-answer", f"{qid}-other"] if candidate is None else candidate
        ),
    }


def bundle(*queries: dict, covered_facets: list[str] | None = None) -> dict:
    return {
        "schema": "golden-gate-input/v1",
        "corpus_revision": "fixture-revision",
        "baseline_revision": "baseline-revision",
        "candidate_revision": "candidate-revision",
        "granularity": "item",
        "covered_facets": covered_facets or ["core"],
        "queries": list(queries),
    }


@pytest.fixture(scope="module")
def thresholds():
    return load_thresholds(SPEC)


def test_thresholds_are_read_from_the_owning_spec_section(thresholds):
    assert thresholds.source == "SPEC.md §5.2.8"
    assert thresholds.k > 0
    assert 0 < thresholds.hard_floor <= thresholds.below_cutoff <= thresholds.mean_min <= 1
    assert 0 <= thresholds.below_max_fraction <= 1


def test_identical_answer_sets_pass_both_slices_without_reading_order(thresholds):
    mono = query("mono", candidate=["mono-other", "mono-answer"])
    cross = query(
        "cross",
        slice_="cross-lingual",
        candidate=["cross-other", "cross-answer"],
    )
    report = evaluate(bundle(mono, cross), thresholds)

    assert report["state"] == PASS
    assert report["readings"]["stability"]["monolingual"]["state"] == PASS
    assert report["readings"]["stability"]["cross-lingual"]["state"] == PASS
    assert report["readings"]["r34"]["monolingual"]["state"] == PASS
    assert report["readings"]["r34"]["cross-lingual"]["state"] == PASS
    assert "thresholds" not in report
    assert report["threshold_source"] == thresholds.source


def test_failure_class_is_red_in_only_its_cross_lingual_slice(thresholds):
    mono = query("mono")
    cross = query(
        "cross",
        slice_="cross-lingual",
        candidate=["wholly-unrelated"],
    )
    report = evaluate(bundle(mono, cross), thresholds)

    assert report["state"] == FAIL
    assert report["readings"]["stability"]["monolingual"]["state"] == PASS
    assert report["readings"]["stability"]["cross-lingual"]["state"] == FAIL
    assert report["readings"]["stability"]["cross-lingual"]["failed_rules"] == [
        "mean-jaccard",
        "below-cutoff-fraction",
        "hard-floor",
    ]
    assert report["readings"]["r34"]["monolingual"]["state"] == PASS
    assert report["readings"]["r34"]["cross-lingual"]["state"] == FAIL


def test_stability_can_pass_while_absolute_r34_fails(thresholds):
    moved = query(
        "moved",
        pinned=["pinned-answer"],
        baseline=["stable-but-wrong"],
        candidate=["stable-but-wrong"],
    )
    cross = query("cross", slice_="cross-lingual")
    report = evaluate(bundle(moved, cross), thresholds)

    assert report["readings"]["stability"]["monolingual"]["state"] == PASS
    assert report["readings"]["r34"]["monolingual"]["state"] == FAIL
    assert report["readings"]["r34"]["monolingual"]["missing"] == {
        "moved": ["pinned-answer"]
    }


def test_facets_name_what_ran_and_do_not_turn_uncovered_queries_green(thresholds):
    core = query("core")
    group = query("group", facet="group")
    deferred = query("deep", facet="deep-body")
    cross = query("cross", slice_="cross-lingual")
    report = evaluate(bundle(core, group, deferred, cross, covered_facets=["core", "group"]), thresholds)

    assert report["evaluated_facets"] == ["core", "group"]
    assert report["unevaluated_facets"] == ["deep-body"]
    for reading in ("stability", "r34"):
        assert report["readings"][reading]["facets"]["core"]["state"] == PASS
        assert report["readings"][reading]["facets"]["group"]["state"] == PASS
        assert report["readings"][reading]["facets"]["deep-body"] == {
            "state": NOT_RUN,
            "query_ids": ["deep"],
            "reason": "facet is not covered by this corpus export",
        }


def test_a_missing_slice_is_not_a_pass(thresholds):
    report = evaluate(bundle(query("mono")), thresholds)
    assert report["state"] == NOT_RUN
    assert report["readings"]["stability"]["cross-lingual"]["state"] == NOT_RUN
    assert report["readings"]["r34"]["cross-lingual"]["state"] == NOT_RUN


@pytest.mark.parametrize(
    "broken",
    [
        bundle(query("one"), query("one", slice_="cross-lingual")),
        bundle(
            query("mono", candidate=["duplicate", "duplicate"]),
            query("cross", slice_="cross-lingual"),
        ),
        bundle(query("mono", pinned=[]), query("cross", slice_="cross-lingual")),
        bundle(
            query("mono", facet="typo"),
            query("cross", slice_="cross-lingual"),
            covered_facets=["core", "typo"],
        ),
        {**bundle(query("mono"), query("cross", slice_="cross-lingual")), "schema": "later"},
    ],
)
def test_malformed_or_ambiguous_inputs_are_refused(broken, thresholds):
    with pytest.raises(InputError):
        evaluate(broken, thresholds)


def test_zero_hits_is_a_real_red_result_not_malformed_input(thresholds):
    report = evaluate(
        bundle(
            query("mono", candidate=[]),
            query("cross", slice_="cross-lingual"),
        ),
        thresholds,
    )

    assert report["state"] == FAIL
    assert report["readings"]["stability"]["monolingual"]["state"] == FAIL
    assert report["readings"]["r34"]["monolingual"]["state"] == FAIL


def test_missing_future_export_writes_not_run_and_exits_distinctly(tmp_path):
    output = tmp_path / "report.json"
    done = subprocess.run(
        [
            sys.executable,
            str(DRIVER),
            "--input",
            str(tmp_path / "not-committed-yet.json"),
            "--output",
            str(output),
            "--spec",
            str(SPEC),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    report = json.loads(output.read_text())
    assert done.returncode == 3
    assert report["state"] == NOT_RUN
    assert "does not exist" in report["reason"]
    assert "pass" not in report["reason"].lower()


def test_cli_failure_is_red_and_success_is_green(tmp_path):
    input_path = tmp_path / "input.json"
    output = tmp_path / "report.json"
    cross = query("cross", slice_="cross-lingual")
    input_path.write_text(json.dumps(bundle(query("mono"), cross)))
    good = subprocess.run(
        [sys.executable, str(DRIVER), "--input", str(input_path), "--output", str(output)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert good.returncode == 0
    assert json.loads(output.read_text())["state"] == PASS

    input_path.write_text(
        json.dumps(bundle(query("mono", candidate=["wrong"]), cross))
    )
    bad = subprocess.run(
        [sys.executable, str(DRIVER), "--input", str(input_path), "--output", str(output)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 1
    assert json.loads(output.read_text())["state"] == FAIL
