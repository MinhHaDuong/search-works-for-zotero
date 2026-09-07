"""Fast tests for bench/bank_cells.py, the per-cell counter of ticket 0733.

The counting itself is arithmetic; what these tests defend is the part a reader
would otherwise have to take on trust: that the MUST cell set is R7's and
R29's and not a hand-list, that the bank count and the retrieval count stay
different quantities, that the cross-check against the golden gate can come out
*wrong* (a probe whose disagreement is unrepresentable is not a cross-check),
and that a floor's set-aside list is computed from the retrieval count.

The synthetic bank is deliberately tiny and lopsided, so a defect that averages
the cells together shows up as a wrong single number rather than a rounding
difference.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bank_cells", REPO / "bench" / "bank_cells.py")
bank_cells = importlib.util.module_from_spec(_spec)
sys.modules["bank_cells"] = bank_cells
_spec.loader.exec_module(bank_cells)


def _question(qid: str, lane: str, *, expected_miss: bool = False, stratum: str = "core",
              mode: str = "any", signal: str = "exact", facet: str = "core") -> dict:
    question_language, answer_language = lane.split("->")
    return {
        "schema": "menagerie-bank/v3",
        "id": qid,
        "need": "n", "query": "q",
        "question_language": question_language, "answer_language": answer_language,
        "lane": lane, "signal": signal, "mode": mode, "facet": facet, "stratum": stratum,
        "mechanism": [], "generator": "need", "set_kind": "any-of", "primary": [],
        "expected_miss": expected_miss,
        "expected_miss_mechanism": "cap" if expected_miss else None,
        "reachability": None,
        "provenance": {"author": "test", "date": "2026-09-07", "page_read": True},
    }


def _write_bank(directory: Path, questions: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for question in questions:
        (directory / f"{question['id']}.json").write_text(json.dumps(question))
    return directory


def _report(by_lane_core: dict[str, int], by_lane_reserve: dict[str, int] | None = None) -> dict:
    def block(counts: dict[str, int]) -> dict:
        return {lane: {"count": n} for lane, n in counts.items()}
    return {
        "schema": "golden-gate-report/v3",
        "scored_count": sum(by_lane_core.values()) + sum((by_lane_reserve or {}).values()),
        "ladder": {"by_stratum": {
            "core": {"by_lane": block(by_lane_core)},
            "reserve": {"by_lane": block(by_lane_reserve or {})},
        }},
    }


def test_must_cells_are_r7_tier_one_squared_and_nothing_else():
    # R7's MUST languages are en, fr, vi; R29 binds every ordered pair over them.
    assert set(bank_cells.MUST_CELLS) == {
        "en->en", "en->fr", "en->vi",
        "fr->en", "fr->fr", "fr->vi",
        "vi->en", "vi->fr", "vi->vi",
    }
    assert len(bank_cells.MUST_CELLS) == 9
    assert "de->de" not in bank_cells.MUST_CELLS  # second tier, R7 allows a stated set-aside


def test_bank_count_and_retrieval_count_are_different_quantities():
    questions = [
        _question("q-0001", "en->en"),
        _question("q-0002", "en->en", expected_miss=True),
        _question("q-0003", "en->en", expected_miss=True),
    ]
    cell = bank_cells.cell_counts(questions, "en->en")
    assert cell["bank"] == 3
    assert cell["retrieval"] == 1
    assert cell["expected_miss"] == 2


def test_cell_counts_split_by_stratum_and_exclude_other_lanes():
    questions = [
        _question("q-0001", "en->en", stratum="core"),
        _question("q-0002", "en->en", stratum="reserve"),
        _question("q-0003", "en->en", stratum="reserve", expected_miss=True),
        _question("q-0004", "vi->fr", stratum="core"),
    ]
    cell = bank_cells.cell_counts(questions, "en->en")
    assert cell["by_stratum"]["core"] == {"bank": 1, "retrieval": 1}
    assert cell["by_stratum"]["reserve"] == {"bank": 2, "retrieval": 1}
    assert bank_cells.cell_counts(questions, "vi->fr")["bank"] == 1


def test_absent_cell_counts_zero_rather_than_vanishing():
    # A MUST cell nobody authored must print 0, not fall out of the table.
    artifact = bank_cells.build([_question("q-0001", "en->en")], None, None)
    assert artifact["must_cells"]["vi->fr"]["bank"] == 0
    assert artifact["must_cells"]["vi->fr"]["retrieval"] == 0
    assert set(artifact["must_cells"]) == set(bank_cells.MUST_CELLS)


def test_non_must_lanes_are_counted_separately_not_folded_in():
    questions = [_question("q-0001", "en->en"), _question("q-0002", "de->de")]
    artifact = bank_cells.build(questions, None, None)
    assert artifact["totals"]["must_bank"] == 1
    assert artifact["totals"]["non_must_bank"] == 1
    assert "de->de" in artifact["non_must_cells"]
    assert "de->de" not in artifact["must_cells"]


def test_gate_scored_counts_are_summed_over_both_strata():
    report = _report({"en->en": 3}, {"en->en": 2, "vi->vi": 1})
    assert bank_cells.gate_scored_by_lane(report) == {"en->en": 5, "vi->vi": 1}


def test_cross_check_agrees_when_retrieval_matches_the_gate():
    questions = [
        _question("q-0001", "en->en"),
        _question("q-0002", "en->en"),
        _question("q-0003", "en->en", expected_miss=True),
    ]
    artifact = bank_cells.build(questions, _report({"en->en": 2}), None)
    assert artifact["cross_check"]["agrees"] is True
    assert artifact["cross_check"]["per_must_cell"]["en->en"]["difference"] == 0


def test_cross_check_can_disagree_and_names_the_difference():
    # The positive control: a cross-check that cannot come out wrong is not one.
    questions = [_question("q-0001", "en->en"), _question("q-0002", "en->en")]
    artifact = bank_cells.build(questions, _report({"en->en": 1}), None)
    assert artifact["cross_check"]["agrees"] is False
    assert artifact["cross_check"]["per_must_cell"]["en->en"]["difference"] == 1


def test_floor_sets_aside_on_the_retrieval_count_not_the_bank_count():
    # Five bank questions, one reachable: a floor of 3 must set the cell aside.
    questions = [_question("q-0001", "en->en")] + [
        _question(f"q-000{i}", "en->en", expected_miss=True) for i in range(2, 6)
    ]
    artifact = bank_cells.build(questions, None, 3)
    floor = artifact["floor"]
    assert "en->en" in floor["cells_set_aside"]
    assert floor["shortfall"]["en->en"] == 2
    assert floor["set_aside"] == 9  # every MUST cell, the other eight being empty


def test_floor_evaluates_a_cell_exactly_at_the_minimum():
    questions = [_question(f"q-{i:04d}", "en->en") for i in range(1, 4)]
    floor = bank_cells.build(questions, None, 3)["floor"]
    assert floor["cells_evaluated"] == ["en->en"]


def test_unevenness_is_zero_on_a_flat_matrix_and_rises_with_concentration():
    flat = bank_cells.unevenness([4, 4, 4, 4])
    assert flat["gini"] == pytest.approx(0.0)
    assert flat["max_over_min"] == pytest.approx(1.0)
    skewed = bank_cells.unevenness([1, 1, 1, 13])
    assert skewed["gini"] > flat["gini"]
    assert skewed["max_over_min"] == pytest.approx(13.0)


def test_unevenness_survives_an_empty_cell_without_dividing_by_zero():
    reading = bank_cells.unevenness([0, 4])
    assert reading["min"] == 0
    assert reading["max_over_min"] is None


def test_load_bank_refuses_a_superseded_schema(tmp_path):
    stale = _question("q-0001", "en->en")
    stale["schema"] = "menagerie-bank/v2"
    _write_bank(tmp_path, [stale])
    with pytest.raises(AssertionError, match="menagerie-bank/v3"):
        bank_cells.load_bank(tmp_path)


def test_load_bank_refuses_an_empty_directory(tmp_path):
    with pytest.raises(AssertionError, match="no q-"):
        bank_cells.load_bank(tmp_path)


def test_committed_bank_counts_reproduce_the_committed_gate_report():
    """The real artifact: the bank's retrieval counts must equal the gate's scored counts.

    This is the ticket's cross-check, run on the committed files rather than
    read off a report — the whole point of the script being a script.
    """
    records = bank_cells.load_bank(bank_cells.QUESTIONS)
    report = json.loads(bank_cells.REPORT.read_text())
    artifact = bank_cells.build(records, report, None)
    assert artifact["cross_check"]["agrees"], artifact["cross_check"]["per_must_cell"]
    assert artifact["bank"]["retrieval"] == report["scored_count"]
