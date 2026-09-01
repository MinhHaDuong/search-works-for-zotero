#!/usr/bin/env python3
"""Can a hash over sign bits identify the chain that produced a vector file?

Ticket 0499. The calibration-header ruling (`DECISIONS.md`, 2026-08-31) makes
every vector file carry vectors its own chain produced, and rules a hash over that
header out cross-machine on one measured fact: X8's fp32 rows are cross-provider
compatible without being bit-identical, so a byte hash calls the same chain a
different one. The obvious repair is to hash something coarser — the sign bit of
each dimension, which is what this repository already quantizes to (ticket 0008)
and which throws away exactly the low-order noise a byte hash trips on.

This asks whether that repair works, from evidence already committed here, and it
answers in two independent ways that agree.

**The probabilistic half**, from `0482-gpu-corrected/`. Two unit vectors at angle
theta disagree on a coordinate's sign with probability theta/pi when their
orientation relative to the axes carries no special structure — the identity
behind sign-bit LSH, and the same geometry ticket 0008's Hamming pool rests on.
Applied to X8's per-rung cosines it says how many of a vector's bits move when the
provider changes but the chain does not, and a hash is all-or-nothing over every
one of them.

**The mechanism half**, from `0008-real-vectors/`. That run measured, on 93 022
real vectors, two dimensions over 95% one-sided whose mean magnitude is a
millionth or less of the median dimension — dimensions the model never activates,
whose "sign is float noise rather than corpus geometry". A hash over all
dimensions hashes those too. Their bits are not merely uninformative; they are the
least stable bits in the vector, and no amount of cosine agreement constrains them.

**Identification needs both populations, and they are in different files.** The
noise floor is the same chain read on the other arm — every X8 summary row, since
that probe scores the GPU arm against the CPU arm at the SAME model and rung. The
signal is the distance to a chain that is not this one, which lives inside each
cell, where the ladder scores a dtype against the fp32 rung beside it on one
provider. Paired that way the answer splits: an fp32 file separates comfortably,
and at the 8-bit rungs the provider difference swamps the chain difference, which
is the boundary the ledger already accepted from the cosine side.

What this driver does NOT do is measure sign flips on real vectors: those live on
the author's machine, and the committed artifacts carry summary cosines rather than
the vectors themselves. It computes what those cosines imply, states the precision
that bounds the implication, and runs a synthetic control to establish the
direction of the estimator's error. Ticket 0499 carries the real-vector arm.

Usage:
    python3 bench/sign_stability.py                      # print the reading
    python3 bench/sign_stability.py --output <file.json> # write the artifact
"""

import argparse
import json
import logging
import math
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sign")

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bench" / "results"

#: X8's cross-provider fidelity, and the per-cell files that carry each model's width.
X8 = RESULTS / "0482-gpu-corrected" / "x8-cross-provider-fidelity.json"
CELLS = RESULTS / "0482-gpu-corrected" / "cells"

#: The real-vector run whose anisotropy section measured the dead dimensions.
ANISOTROPY = RESULTS / "0008-real-vectors" / "real-93022.json"

#: The header is 64 chunks (the calibration ruling), so a hash over it spans
#: 64 x dim bits and any one of them breaks the match.
HEADER_CHUNKS = 64

#: The artifacts round cosine to six decimals. A row reading 1,0 is therefore
#: anything at or above this, which is the precision that bounds every statement
#: below about a rung whose cosine "is" 1.
COS_PRECISION = 5e-7


def flip_fraction(cosine: float) -> float:
    """Expected fraction of coordinates whose sign differs, at this cosine.

    The sign-LSH identity: two vectors at angle theta fall on opposite sides of a
    hyperplane with probability theta/pi. The coordinate axes are not random
    hyperplanes, so this is a model rather than a measurement — the synthetic
    control below establishes which way it errs.
    """
    return math.acos(min(1.0, max(-1.0, cosine))) / math.pi


def dims_by_model(cells: Path) -> dict[str, int]:
    """Vector width per model, read from the per-cell artifacts.

    The summary rows carry `dim: null`; the cells carry it under `metrics`.
    """
    widths: dict[str, int] = {}
    for path in sorted(cells.glob("*.json")):
        cell = json.loads(path.read_text(encoding="utf-8"))
        width = (cell.get("metrics") or {}).get("dim")
        if width:
            widths[cell["model"]] = int(width)
    return widths


def ladder_by_cell(cells: Path) -> dict[tuple[str, str], dict]:
    """Each rung scored against its OWN arm's fp32 — a different chain, one provider.

    This is the distinction the first pass of this analysis got wrong and that the
    artifacts settle: X8's summary rows compare the GPU arm against the CPU arm at
    the SAME rung, so every one of them is the same chain seen twice. The
    cross-*chain* measurement is inside each cell, where `quant_fidelity_score`
    scores a dtype against the fp32 rung beside it. Identification needs both — one
    is the noise floor, the other is the signal.
    """
    ladder: dict[tuple[str, str], dict] = {}
    for path in sorted(cells.glob("*.json")):
        cell = json.loads(path.read_text(encoding="utf-8"))
        metrics = cell.get("metrics") or {}
        if cell.get("status") == "measured" and "cos_mean" in metrics:
            ladder[(cell["model"], cell["dtype"])] = metrics
    return ladder


def row_reading(model: str, rung: str, cosine: float, width: int) -> dict:
    """What one X8 row implies about a sign hash over a header of this width."""
    fraction = flip_fraction(cosine)
    per_vector = (1.0 - fraction) ** width
    at_floor = cosine >= 1.0 - COS_PRECISION
    return {
        "model": model,
        "rung": rung,
        "dim": width,
        "cos": round(cosine, 6),
        "angle_rad": round(math.acos(min(1.0, max(-1.0, cosine))), 6),
        "flip_fraction": round(fraction, 6),
        "expected_flipped_bits_per_vector": round(fraction * width, 3),
        # A row printed as 1,0 states only that the cosine rounds there. What it
        # admits is this many flips, and no committed artifact narrows it further —
        # which is why the exact-hash question needs vectors, not summaries.
        "cos_at_artifact_precision_floor": at_floor,
        "flipped_bits_upper_bound": round(
            max(fraction, flip_fraction(1.0 - COS_PRECISION)) * width, 3
        ),
        "p_sign_hash_matches_one_vector": round(per_vector, 6),
        "p_sign_hash_matches_64_chunk_header": float(f"{per_vector ** HEADER_CHUNKS:.3g}"),
    }


def isotropic_control(width: int, cosine: float, trials: int, rng) -> dict:
    """Does the identity hold when the pair really is isotropic? It should."""
    flips = []
    for _ in range(trials):
        u = rng.normal(size=width)
        u /= np.linalg.norm(u)
        w = rng.normal(size=width)
        w -= u * (w @ u)
        w /= np.linalg.norm(w)
        v = cosine * u + math.sqrt(max(0.0, 1.0 - cosine**2)) * w
        flips.append(int(np.count_nonzero(np.sign(u) != np.sign(v))))
    return {
        "cos": cosine,
        "dim": width,
        "trials": trials,
        "measured_mean_flips": round(float(np.mean(flips)), 3),
        "predicted_flips": round(flip_fraction(cosine) * width, 3),
    }


def quantization_control(width: int, dead_fraction: float, trials: int, rng) -> dict:
    """The same question when the perturbation is per-coordinate and the vector is not isotropic.

    Real embeddings are neither: coordinates are heavy-tailed, some dimensions are
    dead (0008 measured two at a millionth of the median magnitude), and a
    quantization error is applied coordinate by coordinate rather than as a
    rotation. Both effects push the same way — a coordinate near zero needs almost
    no error to change sign — so the identity is a FLOOR on flips at a given
    cosine, and every statement above that quotes it understates the damage.
    """
    live = max(1, int(width * (1.0 - dead_fraction)))
    measured, predicted, cosines = [], [], []
    for _ in range(trials):
        u = rng.standard_t(df=3, size=width)
        u[live:] *= 1e-6  # the dead dimensions, at 0008's measured order of magnitude
        u /= np.linalg.norm(u)
        step = np.max(np.abs(u)) / 127.0  # an 8-bit scale over the vector's own range
        v = np.round(u / step) * step
        v /= np.linalg.norm(v)
        cosine = float(np.clip(u @ v, -1.0, 1.0))
        cosines.append(cosine)
        measured.append(int(np.count_nonzero(np.sign(u) != np.sign(v))))
        predicted.append(flip_fraction(cosine) * width)
    return {
        "dim": width,
        "dead_fraction": dead_fraction,
        "trials": trials,
        "mean_cos": round(float(np.mean(cosines)), 6),
        "measured_mean_flips": round(float(np.mean(measured)), 3),
        "predicted_mean_flips": round(float(np.mean(predicted)), 3),
        "understatement_factor": round(float(np.mean(measured)) / max(1e-9, float(np.mean(predicted))), 2),
    }


def build(seed: int) -> dict:
    x8 = json.loads(X8.read_text(encoding="utf-8"))
    widths = dims_by_model(CELLS)
    anisotropy = json.loads(ANISOTROPY.read_text(encoding="utf-8"))["anisotropy"]

    rows = [
        row_reading(row["model"], row["rung"], row["cos_min"], widths[row["model"]])
        for row in x8["rows"]
        if row.get("status") == "scored" and row["model"] in widths
    ]

    ladder = ladder_by_cell(CELLS)
    # A row printed as cos 1,0 has a noise floor the artifact cannot resolve, so the
    # floor stands in for it rather than a zero that would divide into infinity and
    # read as perfect discrimination. Conservative in the direction that matters:
    # it never claims less noise than the evidence can rule out.
    resolution = flip_fraction(1.0 - COS_PRECISION)
    noise = {
        (row["model"], row["rung"]): max(row["flip_fraction"], resolution) for row in rows
    }

    # Identification, per model and per rung the file could be built at. The noise
    # floor is the same chain read on the other arm; the signal is the distance to
    # the nearest chain that is not this one. Sign distance identifies only where
    # the second exceeds the first.
    identification = []
    for model, width in sorted(widths.items()):
        distances = {
            rung: flip_fraction(metrics["cos_mean"])
            for (owner, rung), metrics in ladder.items()
            if owner == model and rung != "fp32"
        }
        if not distances:
            continue
        for rung in ["fp32", *sorted(distances)]:
            if (model, rung) not in noise:
                continue
            others = [d for other, d in distances.items() if other != rung]
            if rung != "fp32":
                # A file built at this rung is one rung away from fp32 too.
                others = [*others, distances[rung]]
            if not others:
                continue
            nearest = min(others)
            floor_here = noise[(model, rung)]
            identification.append({
                "model": model,
                "file_rung": rung,
                "dim": width,
                "same_chain_noise_flip_fraction": round(floor_here, 6),
                "nearest_other_chain_flip_fraction": round(nearest, 6),
                "separation": round(nearest / floor_here, 2) if floor_here else None,
                "separates": bool(floor_here and nearest > floor_here),
            })

    # The precision floor: a row printed as 1,0 is anything at or above
    # 1 - COS_PRECISION, so even a perfect-looking rung admits this many flips.
    floor_width = max(widths.values())
    floor = flip_fraction(1.0 - COS_PRECISION) * floor_width

    rng = np.random.default_rng(seed)
    worst_same = max((r for r in rows if r["rung"] == "fp32"), key=lambda r: r["flip_fraction"])
    at_fp32 = [item for item in identification if item["file_rung"] == "fp32"]
    at_8bit = [item for item in identification if item["file_rung"] != "fp32"]

    return {
        "probe": "ticket 0499 — can a hash over sign bits identify the chain",
        "what": (
            "What X8's committed cosines and 0008's real-vector anisotropy imply about "
            "identifying an embedding chain by hashing the sign bits of a calibration header. "
            "Derived from committed artifacts; no vectors were embedded here."
        ),
        "inputs": {
            "x8": X8.relative_to(REPO).as_posix(),
            "cells": CELLS.relative_to(REPO).as_posix(),
            "anisotropy": ANISOTROPY.relative_to(REPO).as_posix(),
        },
        "method": {
            "identity": "expected sign disagreement per coordinate = arccos(cos)/pi",
            "header_chunks": HEADER_CHUNKS,
            "cos_precision": COS_PRECISION,
            "seed": seed,
            "caveat": (
                "The axes are not random hyperplanes and the artifacts carry summary "
                "cosines rather than vectors, so these are implications of committed "
                "measurements, not measurements of sign flips."
            ),
        },
        "rows": rows,
        "identification": identification,
        "verdict": {
            "worst_same_chain_row": worst_same,
            "exact_hash_survives_cross_provider": False,
            "flip_fraction_floor_at_artifact_precision": round(
                flip_fraction(1.0 - COS_PRECISION), 8
            ),
            "expected_flips_at_artifact_precision": round(floor, 3),
            "fp32_files": {
                "models": len(at_fp32),
                "all_separate": all(item["separates"] for item in at_fp32),
                "narrowest_separation": min(item["separation"] for item in at_fp32),
                "widest_separation": max(item["separation"] for item in at_fp32),
            },
            "eight_bit_files": {
                "cells": len(at_8bit),
                "separating": sum(1 for item in at_8bit if item["separates"]),
                # The bare count flatters: a 1,04x margin is not identification when the
                # identity behind both sides understates flips several-fold. Two-to-one is
                # the weakest margin worth calling a separation, and one cell reaches it.
                "separating_by_2x": sum(1 for item in at_8bit if item["separation"] >= 2.0),
                "inverting": sum(1 for item in at_8bit if not item["separates"]),
                "narrowest_separation": min(item["separation"] for item in at_8bit),
                "reading": (
                    "At an 8-bit rung the same chain read on the other arm can move more "
                    "bits than the nearest different chain does, so sign distance stops "
                    "identifying anything. That is the same boundary the calibration-header "
                    "ruling already accepted from the cosine side — the device is part of "
                    "the chain at the 8-bit rungs — reached independently in sign space."
                ),
            },
        },
        "dead_dimensions": {
            "source": "0008, 93 022 real vectors at 384 dims",
            "over_95pct_one_sided": anisotropy["dimensions_over_95pct_one_sided"],
            "one_sided_but_dead": anisotropy["dimensions_one_sided_but_dead"],
            "median_dimension_mean_abs": anisotropy["median_dimension_mean_abs"],
            "reading": (
                "Both dimensions above 95% one-sided are dimensions the model never "
                "activates, at a millionth or less of the median magnitude. Their sign is "
                "float noise, and an all-or-nothing hash over every dimension hashes them "
                "alongside the ones that carry the corpus."
            ),
        },
        "controls": {
            "isotropic": [
                isotropic_control(768, cosine, 200, rng) for cosine in (0.999974, 0.9975, 0.97)
            ],
            "coordinate_quantization": quantization_control(768, 2 / 384, 200, rng),
        },
    }


def render(report: dict) -> None:
    verdict = report["verdict"]
    worst = verdict["worst_same_chain_row"]
    log.info("Sign-bit stability, from committed artifacts (ticket 0499)\n")
    log.info("%-30s %-6s %5s %10s %9s %9s %12s",
             "model", "rung", "dim", "cos", "flips", "bound", "P(hash ok)")
    for row in report["rows"]:
        log.info(
            "%-30s %-6s %5d %10.6f %9.3f %9.3f %12.6f",
            row["model"], row["rung"], row["dim"], row["cos"],
            row["expected_flipped_bits_per_vector"], row["flipped_bits_upper_bound"],
            row["p_sign_hash_matches_one_vector"],
        )
    log.info(
        "\nWorst same-chain row (%s, fp32, cross-provider): %.3f bits move per vector, "
        "so an exact sign hash over one vector agrees %.1f%% of the time and over a "
        "%d-chunk header %.2g of the time.",
        worst["model"], worst["expected_flipped_bits_per_vector"],
        100 * worst["p_sign_hash_matches_one_vector"], HEADER_CHUNKS,
        worst["p_sign_hash_matches_64_chunk_header"],
    )
    log.info(
        "Even a rung printed as cos 1,0 admits %.3f flipped bits at the artifacts' own "
        "six-decimal precision.", verdict["expected_flips_at_artifact_precision"],
    )
    log.info(
        "\nIdentification — the noise floor is the same chain on the other arm, the signal "
        "is the nearest chain that is not this one:"
    )
    log.info("%-30s %-6s %10s %10s %8s", "model", "file", "noise", "nearest", "ratio")
    for item in report["identification"]:
        log.info(
            "%-30s %-6s %10.5f %10.5f %8.2f%s",
            item["model"], item["file_rung"], item["same_chain_noise_flip_fraction"],
            item["nearest_other_chain_flip_fraction"], item["separation"],
            "" if item["separates"] else "   <- does not separate",
        )
    fp32, eight = verdict["fp32_files"], verdict["eight_bit_files"]
    log.info(
        "\nAn fp32 file separates for %d of %d models, narrowest %.2fx. An 8-bit file "
        "clears 2x for %d of %d cells and inverts on %d, narrowest %.2fx.",
        fp32["models"] if fp32["all_separate"] else -1, fp32["models"],
        fp32["narrowest_separation"], eight["separating_by_2x"], eight["cells"],
        eight["cells"] - eight["separating"], eight["narrowest_separation"],
    )
    for control in report["controls"]["isotropic"]:
        log.info(
            "Control (isotropic, cos %.6f): %.3f flips measured against %.3f predicted.",
            control["cos"], control["measured_mean_flips"], control["predicted_flips"],
        )
    quant = report["controls"]["coordinate_quantization"]
    log.info(
        "Control: under coordinate-wise quantization on a heavy-tailed vector, flips run "
        "%.2fx the identity's prediction at the same cosine — the estimate above is a floor.",
        quant["understatement_factor"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, help="write the artifact here")
    parser.add_argument("--seed", type=int, default=20260831, help="control-arm seed")
    args = parser.parse_args()

    for path in (X8, CELLS, ANISOTROPY):
        if not path.exists():
            log.error("missing input: %s", path.relative_to(REPO))
            return 1

    report = build(args.seed)
    render(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        log.info("\nwrote %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
