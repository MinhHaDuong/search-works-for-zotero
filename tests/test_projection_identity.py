"""The projection arm: the properties it claims, checked rather than asserted.

The driver's claim is narrow and mechanical — a random projection is multiplicative
on distances, so the RATIO of two angles survives it while the angles themselves
shrink. These tests exercise that on small cases, plus the control that catches a
harness measuring its own noise: projecting to the source width must reproduce the
unprojected ratio exactly.

Small trial counts throughout. The committed artifact is the 200-trial run; this
suite is a gate, and a gate that takes forty seconds gets skipped.
"""

import importlib.util
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location(
        "pi", REPO / "bench" / "projection_identity.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pi = load()


def test_a_pair_is_drawn_at_exactly_the_cosine_asked_for():
    rng = np.random.default_rng(0)
    base = rng.normal(size=768)
    base /= np.linalg.norm(base)
    other = pi.pair_at(rng, base, 0.9)
    assert math.isclose(float(base @ other), 0.9, abs_tol=1e-9)
    assert math.isclose(float(np.linalg.norm(other)), 1.0, abs_tol=1e-9)


def test_projecting_to_the_source_width_changes_nothing():
    """The control. If this drifts, the harness is measuring itself."""
    entry = pi.sweep("m", 384, 0.999974, 0.974042, trials=3, seed=7)
    full = [row for row in entry["widths"] if row["projected_dim"] == 384]
    assert full and full[0]["retention_worst_aggregated"] == 1.0


def test_the_ratio_survives_a_projection_that_shrinks_both_angles():
    """The property the whole arm rests on, stated as a test rather than a citation."""
    rng = np.random.default_rng(3)
    dim, width = 768, 32
    base = rng.normal(size=dim)
    base /= np.linalg.norm(base)
    same, other = pi.pair_at(rng, base, 0.999974), pi.pair_at(rng, base, 0.974042)
    matrix = rng.normal(size=(width, dim)) / math.sqrt(width)
    before = pi.angles(base[None], other[None])[0] / pi.angles(base[None], same[None])[0]
    after = (
        pi.angles((matrix @ other)[None], (matrix @ base)[None])[0]
        / pi.angles((matrix @ same)[None], (matrix @ base)[None])[0]
    )
    assert 0.5 * before < after < 2.0 * before


def test_a_narrower_projection_never_reads_as_better_than_the_source():
    entry = pi.sweep("m", 384, 0.999974, 0.974042, trials=5, seed=11)
    retentions = {row["projected_dim"]: row["retention_worst_aggregated"] for row in entry["widths"]}
    assert retentions[16] <= retentions[384]


def test_the_aggregated_decision_is_steadier_than_a_single_chunk():
    """Sixty-four chunks are most of the answer: the projection's error is zero-mean."""
    entry = pi.sweep("m", 768, 0.999974, 0.974042, trials=5, seed=13)
    narrow = [row for row in entry["widths"] if row["projected_dim"] == 16][0]
    assert narrow["worst_aggregated_ratio"] > narrow["worst_per_chunk_ratio"]


def test_the_cosines_come_from_the_measured_pairing_not_from_literals():
    """Every pair the sweep prices must trace to an artifact, or the arm invents its case."""
    pairs = pi.measured_pairs()
    assert pairs
    for _, dim, cos_same, cos_other in pairs:
        assert dim in (384, 768)
        assert 0.9 < cos_other < cos_same <= 1.0 - pi.ss.COS_PRECISION


def test_the_committed_artifact_reports_a_width_that_serves_every_model():
    import json

    committed = json.loads(
        (REPO / "bench" / "results" / "0499-chain-identifier" / "projection-identity.json")
        .read_text(encoding="utf-8")
    )
    verdict = committed["verdict"]
    assert verdict["width_that_serves_every_model"] in pi.WIDTHS
    assert verdict["worst_aggregated_ratio_at_that_width"] > 0
    assert len(committed["sweeps"]) == verdict["models"]
