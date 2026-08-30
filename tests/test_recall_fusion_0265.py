"""Tests for ticket 0265: recall at the deployed dtype, and the fused RRF delta.

Two things this ticket's own Test section demands as standing, mechanical checks:

  1. The fp32-against-itself fidelity control returns 1,0 (reused from ticket 0263,
     never re-measured here) -- checked against the actual committed 0263 artifact.
  2. No committed cell carries a recall figure whose vector dtype differs from the
     cell's own dtype -- this is the tracker's sharpest failure mode (an fp32 number
     standing in for a quantized deployment) and is checked mechanically against the
     `embedding` block every cell carries, which `recall_embed.mjs` wrote at the moment
     it actually ran that dtype through the ONNX pipeline -- not a hand-typed field a
     later edit could silently diverge from.

A fast, no-network test also covers bench/recall_probes.mjs's own logic on a tiny
synthetic fixture, so the probe draw that both the keyword arm and the fused arm rely on
being identical is checked without needing the real 93 022-passage corpus or any model.

    python3 -m pytest tests/test_recall_fusion_0265.py -q
"""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bench" / "results" / "0265-recall-fusion"
FIDELITY_SUMMARY = REPO / "bench" / "results" / "0263-cpu-arm" / "SUMMARY.json"

DTYPES = ("fp32", "q8", "uint8")


def _cell_files():
    return sorted(p for p in RESULTS.glob("*.json") if p.name != "SUMMARY.json" and "keyword-arm" not in p.name)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------- committed-cell checks

CELLS = _cell_files()


@pytest.mark.skipif(not CELLS, reason="campaign not yet run in this checkout")
@pytest.mark.parametrize("path", CELLS, ids=lambda p: p.stem)
def test_cell_dtype_matches_its_own_embedding_metadata(path):
    """The tracker's sharpest failure mode, checked mechanically: a cell's declared
    dtype must equal the dtype `recall_embed.mjs` actually ran when it produced the
    vectors this cell's recall figure was scored on. No fp32 vectors may stand in for
    a quantized configuration anywhere.
    """
    cell = _load(path)
    assert cell["dtype"] in DTYPES
    assert cell["embedding"]["dtype"] == cell["dtype"], (
        f"{path.name}: cell declares dtype {cell['dtype']!r} but the embedding that "
        f"produced its vectors ran at {cell['embedding']['dtype']!r}"
    )
    assert cell["embedding"]["model_id"] == cell["model"]


@pytest.mark.skipif(not CELLS, reason="campaign not yet run in this checkout")
@pytest.mark.parametrize("path", CELLS, ids=lambda p: p.stem)
def test_vector_arm_agrees_with_the_canonical_recall_driver(path):
    """fused_recall.mjs recomputes the vector-arm top-k independently (it needs the raw
    ranklist to fuse, which vec_task_recall.mjs's own output does not expose) -- so the
    two must agree, or the duplicated candidate-exclusion/cosine logic has drifted.
    """
    cell = _load(path)
    assert cell["vector_recall"]["recall_at_topk"] == cell["vector_arm"]["recall_at_topk"]
    assert cell["vector_recall"]["mrr"] == cell["vector_arm"]["mrr"]


@pytest.mark.skipif(not CELLS, reason="campaign not yet run in this checkout")
@pytest.mark.parametrize("path", CELLS, ids=lambda p: p.stem)
def test_fp32_cells_cite_the_0263_self_control(path):
    """Every fp32 cell's fidelity_pointer must resolve to a 0263 row whose fp32 fidelity
    control is exactly 1,0 -- the invariant this ticket's Test section names, checked
    against the real committed 0263 artifact rather than a hardcoded constant.
    """
    cell = _load(path)
    if cell["dtype"] != "fp32":
        pytest.skip("not an fp32 cell")
    pointer = cell["fidelity_pointer"]
    assert pointer is not None, f"{path.name}: fp32 cell has no fidelity pointer to check"
    fidelity_summary = _load(REPO / pointer["source"])
    row = fidelity_summary["rows"][pointer["row_index"]]
    assert row["model"] == cell["model"]
    assert row["fidelity"]["fp32"]["cos_mean"] == 1.0
    assert row["fidelity"]["fp32"]["overlap_at_30_mean"] == 1.0


def test_summary_reports_zero_cells_and_no_mismatches():
    summary_path = RESULTS / "SUMMARY.json"
    if not summary_path.is_file():
        pytest.skip("campaign not yet run in this checkout")
    summary = _load(summary_path)
    assert summary["mismatches"] == []
    assert summary["missing"] == []
    assert summary["cells_present"] == summary["cells_total"]


def test_every_cell_shares_the_same_keyword_arm():
    """The keyword arm does not depend on any embedding candidate or dtype -- it is
    computed ONCE and every cell's fusion must cite the identical recall/MRR, or a cell
    silently rebuilt its own (drawing a different probe set, most likely).
    """
    summary_path = RESULTS / "SUMMARY.json"
    if not summary_path.is_file():
        pytest.skip("campaign not yet run in this checkout")
    summary = _load(summary_path)
    shared = summary["keyword_arm"]
    for row in summary["rows"]:
        assert row["keyword_arm"]["recall_at_topk"] == shared["recall_at_topk"]
        assert row["keyword_arm"]["mrr"] == shared["mrr"]


# ------------------------------------------------------------ recall_probes.mjs, fast

@pytest.fixture()
def tiny_fixture(tmp_path):
    """Two items: one with 6 passages (eligible at gap=2), one with a single passage
    (never eligible). Deterministic enough to hand-check the eligible count.
    """
    items = ["A"] * 6 + ["B"]
    ords = list(range(6)) + [0]
    items_path = tmp_path / "items.txt"
    ords_path = tmp_path / "ords.txt"
    items_path.write_text("\n".join(items) + "\n", encoding="utf-8")
    ords_path.write_text("\n".join(str(o) for o in ords) + "\n", encoding="utf-8")
    return items_path, ords_path


def _run_probe_draw(items_path, ords_path, *, gap, probes, seed):
    script = f"""
import {{ loadItemsOrds, drawProbes }} from '{(REPO / "bench" / "recall_probes.mjs").as_posix()}';
const {{ items, ords }} = loadItemsOrds('{items_path.as_posix()}', '{ords_path.as_posix()}');
const {{ eligible, probeIdx }} = drawProbes({{ items, ords, gap: {gap}, probes: {probes}, seed: {seed} }});
console.log(JSON.stringify({{ eligible, probeIdx }}));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as f:
        f.write(script)
        path = f.name
    try:
        result = subprocess.run(
            ["node", path], capture_output=True, text=True, timeout=30, check=True
        )
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(result.stdout)


def test_eligible_probes_excludes_the_singleton_item(tiny_fixture):
    items_path, ords_path = tiny_fixture
    out = _run_probe_draw(items_path, ords_path, gap=2, probes=10, seed=1)
    # Item B's single passage (index 6) has no sibling at all, so it is never eligible.
    assert 6 not in out["eligible"]
    # Item A's 6 passages: index i is eligible iff some other index j in [0,6) has
    # |j - i| >= 2. Every index qualifies except none here (0..5 all have a partner
    # >=2 away within a 6-long run), so all six should be eligible.
    assert sorted(out["eligible"]) == [0, 1, 2, 3, 4, 5]


def test_probe_draw_is_deterministic_given_the_same_seed(tiny_fixture):
    items_path, ords_path = tiny_fixture
    a = _run_probe_draw(items_path, ords_path, gap=2, probes=4, seed=42)
    b = _run_probe_draw(items_path, ords_path, gap=2, probes=4, seed=42)
    assert a["probeIdx"] == b["probeIdx"]


def test_probe_draw_never_exceeds_the_eligible_pool(tiny_fixture):
    items_path, ords_path = tiny_fixture
    out = _run_probe_draw(items_path, ords_path, gap=2, probes=1000, seed=7)
    # Only 6 passages are ever eligible; asking for 1000 probes must not loop forever
    # or return duplicates/ineligible indices.
    assert len(out["probeIdx"]) == len(out["eligible"])
    assert sorted(out["probeIdx"]) == sorted(out["eligible"])


def test_a_gap_wider_than_the_run_makes_nothing_eligible(tiny_fixture):
    items_path, ords_path = tiny_fixture
    out = _run_probe_draw(items_path, ords_path, gap=100, probes=10, seed=1)
    assert out["eligible"] == []
    assert out["probeIdx"] == []
