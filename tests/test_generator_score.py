"""The ticket-0719 ladder: win, near-win, miss (rulings 5 and 7 of 2026-09-06).

Every rung is reached by one fixture reply, and the two readings that must
stay apart — the answer row against the same work, and a complete chain
against an incomplete one — are each shown to move the verdict.
"""

import importlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SC = importlib.import_module("bench.generator.score")

PARA = ("The carbon tax was introduced in two thousand and fourteen under the name of the climate energy "
        "contribution, at a rate that rose every year until the protests froze it, and the freeze has held.")

ANSWER = {
    "item_key": "ITEM0001",
    "paragraph": PARA,
    "chain": {"title": {"value": "Carbon pricing in France"}, "identifier": {"value": "10.1000/abc"}},
}

ROW = {"itemKey": "ITEM0001", "title": "Carbon pricing in France",
       "snippet": "…under the name of the climate energy contribution, at a rate that rose every year…", "score": 0.02}
FULL_ROW = {**ROW, "creators": ["A. Author"], "date": "2019", "DOI": "10.1000/abc", "section": "2 Policy", "pageLabel": "14"}
SAME_ITEM_OTHER_TEXT = {"itemKey": "ITEM0001", "title": "Carbon pricing in France", "snippet": "an unrelated snippet from the abstract of the paper"}
OTHER_RENDERING = {"itemKey": "OTHER999", "title": "Carbon pricing in France", "snippet": "a translation in another file"}
NOISE = [{"itemKey": f"N{i}", "title": f"Noise {i}", "snippet": "nothing to do with it"} for i in range(12)]


def test_overlap_needs_a_shared_shingle():
    assert SC.overlaps(ROW["snippet"], PARA)
    assert not SC.overlaps("the carbon tax of another country entirely", PARA)
    assert SC.overlaps("The carbon tax", PARA)  # a short snippet contained whole


def test_win_is_the_row_with_a_resolvable_key_for_a_simple_document():
    """Ruled 2026-09-06: the item key satisfies the identifier and work-identity part
    of the chain, so a title-plus-key hit wins; the chain reading is kept beside it."""
    s = SC.classify([NOISE[0], FULL_ROW], ANSWER)
    assert s["verdict"] == SC.WIN and s["row_rank"] == 2 and s["work_rank"] == 2
    assert s["row_rr"] == pytest.approx(0.5) and s["chain_complete"] and not s["compound"]
    s = SC.classify([ROW], ANSWER)
    assert s["verdict"] == SC.WIN and s["row_rank"] == 1 and s["key_resolvable"]
    assert s["chain_in_reply"]["title"] and not s["chain_in_reply"]["page_label"] and not s["chain_complete"]
    keyless = {**ROW, "itemKey": ""}
    assert SC.classify([keyless], {**ANSWER, "item_key": ""})["verdict"] != SC.WIN


def test_a_compound_document_needs_part_byline_and_page_to_win():
    """The exception: for a book, section, proceedings paper or dictionary entry a
    key alone is a near-win; the part's title with its byline and the page win."""
    chapter = {**ANSWER, "item_type": "bookSection"}
    s = SC.classify([ROW], chapter)
    assert s["verdict"] == SC.NEAR and s["row_rank"] == 1 and s["compound"]
    part = {**ROW, "creators": ["A. Author"], "pageLabel": "14"}
    assert SC.classify([part], chapter)["verdict"] == SC.WIN
    assert SC.classify([{**ROW, "creators": ["A. Author"]}], chapter)["verdict"] == SC.NEAR
    for t in ("book", "conferencePaper", "dictionaryEntry", "encyclopediaArticle"):
        assert SC.classify([ROW], {**ANSWER, "item_type": t})["verdict"] == SC.NEAR
    assert SC.classify([ROW], {**ANSWER, "item_type": "report"})["verdict"] == SC.WIN


def test_same_work_without_the_paragraph_is_a_near_win():
    s = SC.classify([SAME_ITEM_OTHER_TEXT], ANSWER)
    assert s["verdict"] == SC.NEAR and s["row_rank"] is None and s["work_rank"] == 1
    s = SC.classify(NOISE[:3] + [OTHER_RENDERING], ANSWER)
    assert s["verdict"] == SC.NEAR and s["work_rank"] == 4 and s["row_rr"] == 0.0
    by_doi = {"itemKey": "X", "title": "different title", "snippet": "…", "doi": "10.1000/ABC"}
    assert SC.classify([by_doi], ANSWER)["verdict"] == SC.NEAR


def test_beyond_the_tenth_is_a_miss():
    s = SC.classify(NOISE[:10] + [FULL_ROW], ANSWER)
    assert s["verdict"] == SC.MISS and s["row_rank"] is None and s["work_rank"] is None
    assert s["row_rr"] == 0.0 and s["work_rr"] == 0.0 and s["hits"] == 11
    assert SC.classify([], ANSWER)["verdict"] == SC.MISS


def test_aggregate_counts_beside_rates_with_misses_at_zero():
    readings = [
        {"lane": "en->en", "score": SC.classify([FULL_ROW], ANSWER)},
        {"lane": "en->en", "score": SC.classify([NOISE[0], ROW], ANSWER)},
        {"lane": "fr->en", "score": SC.classify(NOISE, ANSWER)},
    ]
    agg = SC.aggregate(readings, lambda r: r["lane"])
    assert list(agg)[0] == "all"
    assert agg["all"] == {"n": 3, "win": 2, "near_win": 0, "miss": 1, "win_rate": 0.667, "near_win_rate": 0.0,
                          "miss_rate": 0.333, "row_mrr": 0.5, "work_mrr": 0.5, "row_in_top10": 2, "work_in_top10": 2,
                          "chain_complete": 1}
    assert agg["fr->en"]["n"] == 1 and agg["fr->en"]["row_mrr"] == 0.0
    # A row asked in several modes aggregates under the mode's own score.
    multi = [{"lane": "x", "score": readings[2]["score"], "by_mode": {"exact": readings[0]["score"]}}]
    assert SC.aggregate(multi, lambda r: r["lane"], "by_mode.exact")["all"]["win"] == 1
    assert SC.aggregate(multi, lambda r: r["lane"])["all"]["miss"] == 1
    tally = SC.chain_tally(readings)
    assert tally["answer_rows_found"] == 2
    assert tally["carried"]["entry_title"] == 2 and tally["carried"]["page_label"] == 1
    assert "title" not in tally["carried"] and "creators" not in tally["carried"]
