"""Tests for bench/geometry.py — the ratified chunk geometry (ticket 0140).

The construction must make over-feeding the embedder unwritable: for every
model in the window census, including the long-window ones (8 192 and 32 768
tokens declared), the whole embedded sequence — prefix included — fits the
model's window. The census artifact is real data, committed; these tests are
pure arithmetic over it, so they stay in the fast tier.

    python3 -m pytest tests/test_chunk_geometry.py -q
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CENSUS = REPO / "bench" / "results" / "0140-model-windows" / "candidate-windows.json"


def load():
    spec = importlib.util.spec_from_file_location("geometry", REPO / "bench" / "geometry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


g = load()
census = json.loads(CENSUS.read_text())


# --- the budget construction -------------------------------------------------------

def test_no_census_model_can_be_over_fed():
    # The point of the ticket: budget + specials + prefix <= window for EVERY
    # candidate, the 8 192- and 32 768-token ones included. Specials at 2 and a
    # worst-case measured instruction prefix of 4 tokens ("search_document: ").
    for name, record in census["models"].items():
        window = record["window"]
        for prefix in (0, 4):
            budget = g.resolve_budget(window, special_tokens=2, prefix_tokens=prefix)
            assert budget + 2 + prefix <= window, name


def test_budget_resolves_identically_across_every_census_candidate():
    # §5.2.2's stability claim, the reason the ceiling is 500: the min never
    # binds, so a model swap cannot move the chunk key.
    budgets = {g.resolve_budget(r["window"], 2, 0) for r in census["models"].values()}
    assert len(budgets) == 1
    assert budgets.pop() == g.CEILING - 2


def test_ordering_min_then_subtract_not_subtract_then_min():
    # At a 512 window the two orders agree; at 8 192 they diverge, and the
    # wrong order would let the prefix ride on top of the ceiling.
    window, specials, prefix = 8192, 2, 40
    right = g.resolve_budget(window, specials, prefix)
    wrong = min(window - specials - prefix, g.CEILING)
    assert right == g.CEILING - specials - prefix
    assert wrong == g.CEILING
    assert right < wrong


def test_window_is_the_minimum_over_declared_fields():
    # nomic-embed-text-v1.5 declares four fields spanning a factor of four;
    # the rule reads the tightest. An empty declaration raises rather than
    # defaulting — a window is read, never assumed.
    assert g.model_window({"max_position_embeddings": 8192, "model_max_length": 2048}) == 2048
    with pytest.raises(ValueError):
        g.model_window({})


def test_a_window_below_the_affordances_raises_instead_of_going_negative():
    with pytest.raises(ValueError):
        g.resolve_budget(4, special_tokens=2, prefix_tokens=4)


# --- the quarter rule --------------------------------------------------------------

def test_heading_path_over_a_quarter_is_dropped_entirely_not_truncated():
    budget = 498
    assert g.effective_prefix(125, budget) == 0       # 125 > 498/4 = 124.5 -> dropped
    assert g.effective_prefix(124, budget) == 124     # under the quarter -> kept whole
    # Sabotage check: a truncating implementation would return something in
    # between; the rule's outputs are exactly {0, prefix}.
    assert g.effective_prefix(400, budget) in (0, 400)
    assert g.effective_prefix(400, budget) == 0


# --- the counting model ------------------------------------------------------------

def test_an_entry_shorter_than_the_budget_is_one_chunk_regardless():
    # The max rarely binds: this is why §5.2.9 must be measured, not divided.
    assert g.chunk_count([30, 40, 50], budget=498) == 1


def test_paragraphs_accumulate_until_the_budget_stops_them():
    # Four paragraphs of 200 tokens: 200+200 fits 498, a third would not.
    assert g.chunk_count([200, 200, 200, 200], budget=498) == 2


def test_an_oversized_paragraph_splits_with_overlap_only_inside_itself():
    # 1 000 tokens at budget 498, overlap 48: ceil((1000-48)/450) = 3 pieces.
    assert g.chunk_count([1000], budget=498) == 3
    # Whole paragraphs carry no overlap: two 400-token paragraphs are two
    # chunks, not two-plus-overlap arithmetic.
    assert g.chunk_count([400, 400], budget=498) == 2


def test_split_count_agrees_with_its_own_boundary():
    assert g.split_count(498, 498) == 1
    assert g.split_count(499, 498) == 2


def test_a_sub_minimum_fill_is_absorbed_into_the_following_split():
    # 50 tokens then 1 000: the 50 rides into the split (1 050 -> 3 pieces)
    # instead of closing as a runt chunk followed by 3 (which would be 4).
    assert g.chunk_count([50, 1000], budget=498) == 3
    # At or above the minimum it closes normally: 120 + split(1000) = 1 + 3.
    assert g.chunk_count([120, 1000], budget=498) == 4
