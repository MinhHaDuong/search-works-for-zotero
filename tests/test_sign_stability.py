"""The sign-stability analysis, checked against its own identity and the live artifacts.

Ticket 0499 derives its conclusion from committed cosines rather than from vectors,
so the two things worth freezing are the arithmetic that does the deriving and the
inputs still being where the driver reads them. If X8's artifact moves or loses the
per-cell widths, this fails here rather than in a ledger entry nobody re-runs.
"""

import importlib.util
import math
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("ss", REPO / "bench" / "sign_stability.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ss = load()


def test_orthogonal_vectors_disagree_on_half_their_signs():
    assert ss.flip_fraction(0.0) == 0.5


def test_identical_vectors_never_disagree():
    assert ss.flip_fraction(1.0) == 0.0


def test_the_fraction_grows_as_the_cosine_falls():
    assert ss.flip_fraction(0.99) < ss.flip_fraction(0.9) < ss.flip_fraction(0.5)


def test_the_identity_is_the_angle_over_pi():
    assert math.isclose(ss.flip_fraction(0.5), (math.pi / 3) / math.pi)


def test_a_hash_over_a_header_is_weaker_than_over_one_vector():
    """Hashing amplifies: 64 chunks give 64 times the chances to break the match."""
    row = ss.row_reading("m", "fp32", 0.999974, 768)
    assert row["p_sign_hash_matches_64_chunk_header"] < row["p_sign_hash_matches_one_vector"]


def test_a_cosine_printed_as_one_still_admits_flipped_bits():
    """The artifacts store six decimals, so 1,0 is a range and the bound says how wide."""
    row = ss.row_reading("m", "fp32", 1.0, 768)
    assert row["cos_at_artifact_precision_floor"]
    assert row["flipped_bits_upper_bound"] > 0


def test_the_inputs_the_analysis_reads_are_where_it_reads_them():
    assert ss.X8.exists() and ss.ANISOTROPY.exists()
    assert any(ss.CELLS.glob("*.json"))


def test_every_scored_row_resolves_a_vector_width():
    """`dim` is null in the summary rows; the widths come from the cells or nowhere."""
    widths = ss.dims_by_model(ss.CELLS)
    report = ss.build(seed=1)
    assert report["rows"], "no scored rows resolved a width"
    assert all(row["dim"] in set(widths.values()) for row in report["rows"])


def test_the_isotropic_control_reproduces_the_identity():
    """If the simulation and the identity disagreed, the identity would be the suspect."""
    import numpy as np

    control = ss.isotropic_control(768, 0.99, 200, np.random.default_rng(0))
    assert abs(control["measured_mean_flips"] - control["predicted_flips"]) < 3.0


def test_the_ladder_holds_only_cells_that_measured_something():
    """An unloadable cell has no metrics; counting it as a chain distance invents one."""
    ladder = ss.ladder_by_cell(ss.CELLS)
    assert ladder
    assert all("cos_mean" in metrics for metrics in ladder.values())


def test_identification_reads_the_signal_from_the_cells_not_the_summary_rows():
    """The distinction the first pass got wrong, frozen so it cannot come back.

    Every X8 summary row is one chain seen on two arms, so a signal taken from
    there would be comparing a chain with itself. The cross-chain distances must
    therefore come from the ladder, and the fp32 pairing must use one of them.
    """
    report = ss.build(seed=1)
    ladder = ss.ladder_by_cell(ss.CELLS)
    distances = {
        round(ss.flip_fraction(metrics["cos_mean"]), 6)
        for (_, rung), metrics in ladder.items()
        if rung != "fp32"
    }
    fp32 = [item for item in report["identification"] if item["file_rung"] == "fp32"]
    assert fp32
    assert all(item["nearest_other_chain_flip_fraction"] in distances for item in fp32)


def test_an_eight_bit_file_is_where_the_separation_gives_out():
    report = ss.build(seed=1)
    eight = report["verdict"]["eight_bit_files"]
    assert eight["inverting"] > 0
    assert eight["separating_by_2x"] < eight["cells"]
    assert report["verdict"]["fp32_files"]["all_separate"]


def test_the_committed_artifact_still_matches_the_driver():
    """The ledger and the ticket quote this file; the driver has to still produce it."""
    import json

    committed = json.loads(
        (REPO / "bench" / "results" / "0499-sign-hash" / "sign-stability.json").read_text(
            encoding="utf-8"
        )
    )
    fresh = ss.build(seed=committed["method"]["seed"])
    assert fresh["rows"] == committed["rows"]
    assert fresh["verdict"] == committed["verdict"]
