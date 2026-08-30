"""Fast, no-ONNX tests for bench/cross_lingual_score.py's ranking logic.

Drives `score_cell()` directly with tiny synthetic vectors (2-4 dims), so the
ranking/aggregation/control logic is exercised without a real embedding run.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cross_lingual_score", REPO / "bench" / "cross_lingual_score.py")
cls = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(REPO / "bench"))
spec.loader.exec_module(cls)


def _manifest(pool_ids, query_ids):
    return dict(
        model_id="fake-model", model="fake/fake-model", dtype="q8", device="cpu",
        pooling="mean", template={"query": "", "passage": ""},
        pool_ids=pool_ids, query_ids=query_ids,
    )


def test_relevant_item_ranked_first_scores_hit_at_1():
    pool_meta = [
        dict(pool_id="P0", kind="gold", lang_tag="vi"),
        dict(pool_id="P1", kind="distractor", lang_tag="en"),
        dict(pool_id="P2", kind="distractor", lang_tag="en"),
    ]
    query_meta = [dict(query_id="Q0", topic_id="T1", query_lang="en", target_lang="vi",
                        relevant_pool_ids=["P0"])]
    pool_vecs = [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)]
    query_vecs = [(1.0, 0.0)]  # identical to P0 -> rank 1

    manifest = _manifest(["P0", "P1", "P2"], ["Q0"])
    out = cls.score_cell(manifest, pool_meta, query_meta, pool_vecs, query_vecs, topk=10)

    assert out["per_query"][0]["best_rank"] == 1
    assert out["per_query"][0]["hit_at_1"] is True
    assert out["pair_summary"]["en->vi"]["mrr"] == 1.0


def test_relevant_item_far_away_misses_top_k():
    pool_meta = [
        dict(pool_id="P0", kind="gold", lang_tag="vi"),
        dict(pool_id="P1", kind="distractor", lang_tag="en"),
    ]
    query_meta = [dict(query_id="Q0", topic_id="T1", query_lang="en", target_lang="vi",
                        relevant_pool_ids=["P0"])]
    pool_vecs = [(-1.0, 0.0), (1.0, 0.0)]
    query_vecs = [(1.0, 0.0)]  # matches P1, not the gold P0 -> rank 2

    manifest = _manifest(["P0", "P1"], ["Q0"])
    out = cls.score_cell(manifest, pool_meta, query_meta, pool_vecs, query_vecs, topk=1)

    assert out["per_query"][0]["best_rank"] == 2
    assert out["per_query"][0]["hit_at_1"] is False
    assert out["pair_summary"]["en->vi"]["hit_at_1"] == 0.0


def test_negative_control_clean_when_gold_absent_from_top_k():
    pool_meta = [
        dict(pool_id="P0", kind="gold", lang_tag="vi"),
        dict(pool_id="P1", kind="distractor", lang_tag="en"),
    ]
    query_meta = [dict(query_id="QNEG", topic_id="NEG", query_lang="en", target_lang="none",
                        relevant_pool_ids=[])]
    pool_vecs = [(-1.0, 0.0), (1.0, 0.0)]
    query_vecs = [(1.0, 0.0)]  # matches the distractor, not the gold

    manifest = _manifest(["P0", "P1"], ["QNEG"])
    out = cls.score_cell(manifest, pool_meta, query_meta, pool_vecs, query_vecs, topk=1)

    assert out["negative_control"]["n"] == 1
    assert out["negative_control"]["clean"] == 1
    assert out["negative_control"]["leaked"] == []
    # A negative-control query never contributes to a pair_summary lane.
    assert out["pair_summary"] == {}


def test_negative_control_catches_leakage():
    pool_meta = [
        dict(pool_id="P0", kind="gold", lang_tag="vi"),
        dict(pool_id="P1", kind="distractor", lang_tag="en"),
    ]
    query_meta = [dict(query_id="QNEG", topic_id="NEG", query_lang="en", target_lang="none",
                        relevant_pool_ids=[])]
    pool_vecs = [(1.0, 0.0), (-1.0, 0.0)]
    query_vecs = [(1.0, 0.0)]  # matches the gold -> control must catch it

    manifest = _manifest(["P0", "P1"], ["QNEG"])
    out = cls.score_cell(manifest, pool_meta, query_meta, pool_vecs, query_vecs, topk=1)

    assert out["negative_control"]["clean"] == 0
    assert out["negative_control"]["leaked"] == ["QNEG"]


def test_english_only_gold_excluded_from_leakage_check():
    # An EN gold item matching a negative-control query is not "leakage" in
    # the cross-lingual sense the control exists to catch (see lang_tag != 'en'
    # in cross_lingual_score.py); only non-English gold counts.
    pool_meta = [
        dict(pool_id="P0", kind="gold", lang_tag="en"),
        dict(pool_id="P1", kind="distractor", lang_tag="en"),
    ]
    query_meta = [dict(query_id="QNEG", topic_id="NEG", query_lang="en", target_lang="none",
                        relevant_pool_ids=[])]
    pool_vecs = [(1.0, 0.0), (-1.0, 0.0)]
    query_vecs = [(1.0, 0.0)]

    manifest = _manifest(["P0", "P1"], ["QNEG"])
    out = cls.score_cell(manifest, pool_meta, query_meta, pool_vecs, query_vecs, topk=1)

    assert out["negative_control"]["clean"] == 1


def test_pool_id_order_mismatch_is_caught():
    pool_meta = [dict(pool_id="P0", kind="gold", lang_tag="vi")]
    query_meta = [dict(query_id="Q0", topic_id="T1", query_lang="en", target_lang="vi",
                        relevant_pool_ids=["P0"])]
    manifest = _manifest(["P_WRONG"], ["Q0"])  # deliberately mismatched
    with pytest.raises(AssertionError, match="does not match the vectors"):
        cls.score_cell(manifest, pool_meta, query_meta, [(1.0, 0.0)], [(1.0, 0.0)])
