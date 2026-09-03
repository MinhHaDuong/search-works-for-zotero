"""Tests for bench/pooling_ablation_summary.py — the pairing behind ticket 0612's numbers.

The script's whole job is to keep two arms apart that look alike: a cell measuring a model
and a cell measuring a defect. Every guard below was checked by sabotage — remove the
guard, confirm the test goes red — because a summary that silently pairs the wrong cells
would produce a number with nothing wrong on its face, which is the failure this ablation
exists to talk about.

    python3 -m pytest tests/test_pooling_ablation_summary.py -q
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location(
        "pas", REPO / "bench" / "pooling_ablation_summary.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pas = load()


def cell(pooling="cls", dtype="fp32", ranks=(1.0, 0.5), forced=None, declared=None):
    """One score file's worth of structure — only the fields the summary reads."""
    per_query = [
        {
            "reciprocal_rank": r,
            "hit_at_1": r == 1.0,
            "hit_at_5": True,
            "hit_at_10": True,
        }
        for r in ranks
    ]
    # The negative-control rows carry no rank; the aggregate must skip them rather than
    # crash on them, which is how the real scorer writes an unranked query.
    per_query.append(
        {"reciprocal_rank": None, "hit_at_1": False, "hit_at_5": False, "hit_at_10": False}
    )
    out = {
        "model_id": "m",
        "model": "org/m",
        "dtype": dtype,
        "pooling": pooling,
        "template": {"query": "", "passage": ""},
        "per_query": per_query,
        "negative_control": {"clean": 2, "n": 4},
    }
    if forced is not None:
        out["pooling_forced"] = forced
    if declared is not None:
        out["declared_pooling"] = declared
    return out


# --- the aggregate ------------------------------------------------------------------


def test_unranked_rows_are_excluded_from_the_mean_not_counted_as_zero():
    # Counting the negative-control row as a miss would deflate every arm by the same
    # factor and quietly shrink the delta the ablation is measuring.
    agg = pas.aggregate(cell(ranks=(1.0, 0.5)))
    assert agg["queries_ranked"] == 2
    assert agg["mrr"] == 0.75


def test_hit_at_1_is_a_share_of_ranked_queries():
    assert pas.aggregate(cell(ranks=(1.0, 0.5)))["hit_at_1"] == 0.5


# --- the pairing guards -------------------------------------------------------------


def test_an_ablation_cell_without_its_marker_is_refused():
    """The marker is the only thing separating this arm from a measurement of the model."""
    with pytest.raises(SystemExit, match="pooling_forced"):
        pas.pair(cell(), cell(pooling="mean", declared="cls"))


def test_a_control_whose_pooling_is_not_what_the_ablation_declares_is_refused():
    # Pairing a `mean` model's control against a `cls` model's ablation would produce a
    # delta between two different models and call it a pooling cost.
    with pytest.raises(SystemExit, match="control pools"):
        pas.pair(cell(pooling="mean"), cell(pooling="mean", forced=True, declared="cls"))


def test_arms_at_different_dtypes_are_refused():
    with pytest.raises(SystemExit, match="dtype differs"):
        pas.pair(
            cell(dtype="q8"),
            cell(pooling="mean", dtype="fp32", forced=True, declared="cls"),
        )


# --- the delta ----------------------------------------------------------------------


def test_a_degrading_forced_arm_reports_a_negative_delta():
    out = pas.pair(
        cell(ranks=(1.0, 1.0)),
        cell(pooling="mean", ranks=(0.5, 0.5), forced=True, declared="cls"),
    )
    assert out["delta"]["mrr"] == -0.5
    assert out["delta"]["mrr_relative_pct"] == -50.0
    assert out["correct_pooling"] == "cls"
    assert out["forced_pooling"] == "mean"


def test_the_summary_names_the_worst_cell(tmp_path, monkeypatch):
    """The headline figure is the worst cell, so it must be the minimum, not the last one."""
    control_dir, ablation_dir = tmp_path / "c", tmp_path / "a"
    control_dir.mkdir()
    ablation_dir.mkdir()
    for name, ranks in (("aa", (0.5, 0.5)), ("zz", (0.9, 0.9))):
        (control_dir / f"{name}.score.json").write_text(json.dumps(cell(ranks=(1.0, 1.0))))
        (ablation_dir / f"{name}-forced-mean.score.json").write_text(
            json.dumps(cell(pooling="mean", ranks=ranks, forced=True, declared="cls"))
        )
    out_path = tmp_path / "SUMMARY.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pooling_ablation_summary.py",
            "--control-dir",
            str(control_dir),
            "--ablation-dir",
            str(ablation_dir),
            "--output",
            str(out_path),
        ],
    )
    assert pas.main() == 0
    summary = json.loads(out_path.read_text())
    assert len(summary["cells"]) == 2
    assert summary["worst_mrr_relative_pct"] == -50.0
    assert summary["best_mrr_relative_pct"] == -10.0
