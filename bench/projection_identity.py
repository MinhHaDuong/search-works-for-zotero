#!/usr/bin/env python3
"""A seeded random projection keeps the chain-identity margin that sign bits destroy.

Ticket 0499, second arm. The first arm ruled out both a hash over bytes (the ledger
had already) and a hash over sign bits, and found that what identification actually
needs is a *ratio*: the distance to the nearest different chain over the distance
the same chain moves when only the provider changes. At fp32 that ratio is 31,67x
in the narrowest case, and the question this arm answers is whether a smaller object
can carry it.

It can, and the reason is the one property sign bits lack. Johnson-Lindenstrauss is
multiplicative on distances — `‖R(u-v)‖` is `‖u-v‖` to within a factor — so a pair
that is nearly identical stays nearly identical after projection. Both distances
shrink by nearly the same factor and the ratio survives. Sign bits do the opposite:
they quantize the small angle away entirely, which is exactly how an angle of
0,0072 rad became noise.

Three properties make the projection admissible here where a data-derived reduction
is not. It is **oblivious**: `R` is drawn from a published seed, so it carries no
corpus, which SPEC.md's asset list requires of anything shipped in a file
handed out. It is **reproducible**: both machines derive the same `R` from the same
seed, with no basis to transmit. And its guarantee is **distribution-free**, so the
anisotropy that broke the sign-bit argument (0008's dead dimensions) does not
weaken it.

What this does NOT do is embed anything. The pairs are synthetic, drawn at the
cosines X8 and the per-cell ladder measured, which is the same limit the first arm
states: real vectors would confirm the angles are what the cosines say. What is
being simulated is the projection's own behaviour, and that is distribution-free.

Usage:
    python3 bench/projection_identity.py                      # print the reading
    python3 bench/projection_identity.py --output <file.json> # write the artifact
"""

import argparse
import json
import logging
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sign_stability as ss  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("projection")

REPO = Path(__file__).resolve().parent.parent

#: Widths to price. The full width of each model is in the list — 768 for the wide
#: ones, 384 for the narrow — and is carried as the control: a "projection" to the
#: source width is no projection, so its ratio must land on the unprojected one or
#: the harness is measuring its own noise.
WIDTHS = (16, 32, 64, 128, 256, 384, 768)

#: The ratified header is 64 chunks, and the decision is taken over all of them. That
#: aggregation is most of the answer — the projection's error is zero-mean, so the
#: mean over 64 chunks is far steadier than any single chunk.
HEADER_CHUNKS = 64

#: A projection is worth taking only if it keeps essentially the whole margin. Ninety
#: per cent of the unprojected ratio, in the WORST trial rather than the mean, is the
#: bar used to pick a width below.
RETENTION_BAR = 0.9


def pair_at(rng, base: np.ndarray, cosine: float) -> np.ndarray:
    """A unit vector at exactly this cosine from `base`, in a random direction."""
    step = rng.normal(size=base.shape)
    step -= base * (step @ base)
    step /= np.linalg.norm(step)
    return cosine * base + math.sqrt(max(0.0, 1.0 - cosine**2)) * step


def angles(matrix: np.ndarray, other: np.ndarray) -> np.ndarray:
    """Row-wise angle between two stacks of vectors."""
    dots = np.einsum("ij,ij->i", matrix, other)
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(other, axis=1)
    return np.arccos(np.clip(dots / norms, -1.0, 1.0))


def trial(rng, dim: int, width: int, cos_same: float, cos_other: float) -> tuple[float, float]:
    """One header's worth of chunks, projected once, read two ways.

    Returns the ratio a per-vector decision would see at its worst chunk, and the
    ratio the 64-chunk mean sees — the decision the header actually takes.
    """
    base = rng.normal(size=(HEADER_CHUNKS, dim))
    base /= np.linalg.norm(base, axis=1, keepdims=True)
    same = np.stack([pair_at(rng, row, cos_same) for row in base])
    other = np.stack([pair_at(rng, row, cos_other) for row in base])

    if width >= dim:
        projected = (base, same, other)
    else:
        matrix = rng.normal(size=(width, dim)) / math.sqrt(width)
        projected = tuple(stack @ matrix.T for stack in (base, same, other))

    noise = angles(projected[0], projected[1])
    signal = angles(projected[0], projected[2])
    per_chunk = float(np.min(signal / noise))
    aggregated = float(np.mean(signal) / np.mean(noise))
    return per_chunk, aggregated


def sweep(model: str, dim: int, cos_same: float, cos_other: float, trials: int, seed: int) -> dict:
    """Every width, for one model's measured pair of cosines."""
    unprojected = math.acos(cos_other) / math.acos(cos_same)
    rows = []
    for width in WIDTHS:
        if width > dim:
            continue
        rng = np.random.default_rng(seed)
        results = [trial(rng, dim, width, cos_same, cos_other) for _ in range(trials)]
        per_chunk = [value for value, _ in results]
        aggregated = [value for _, value in results]
        rows.append({
            "projected_dim": width,
            "header_bytes": HEADER_CHUNKS * width * 4,
            "worst_per_chunk_ratio": round(min(per_chunk), 2),
            "worst_aggregated_ratio": round(min(aggregated), 2),
            "mean_aggregated_ratio": round(float(np.mean(aggregated)), 2),
            "retention_worst_aggregated": round(min(aggregated) / unprojected, 4),
        })
    keeping = [row for row in rows if row["retention_worst_aggregated"] >= RETENTION_BAR]
    return {
        "model": model,
        "dim": dim,
        "cos_same_chain": cos_same,
        "cos_nearest_other_chain": cos_other,
        "unprojected_ratio": round(unprojected, 2),
        "full_header_bytes": HEADER_CHUNKS * dim * 4,
        "widths": rows,
        "smallest_width_at_bar": min((row["projected_dim"] for row in keeping), default=None),
    }


def measured_pairs() -> list[tuple[str, int, float, float]]:
    """The two cosines per model, taken from the first arm's own pairing.

    Same-chain is X8's fp32 row (one chain, two arms), floored at the artifacts'
    six-decimal resolution so a row printed 1,0 does not divide into infinity.
    Nearest-other-chain is the closest rung in that model's own ladder.
    """
    report = ss.build(seed=0)
    rows = {(row["model"], row["rung"]): row for row in report["rows"]}
    ladder = ss.ladder_by_cell(ss.CELLS)
    pairs = []
    for item in report["identification"]:
        if item["file_rung"] != "fp32":
            continue
        model, dim = item["model"], item["dim"]
        cos_same = min(rows[(model, "fp32")]["cos"], 1.0 - ss.COS_PRECISION)
        cos_other = max(
            metrics["cos_mean"]
            for (owner, rung), metrics in ladder.items()
            if owner == model and rung != "fp32"
        )
        pairs.append((model, dim, cos_same, cos_other))
    return pairs


def build(trials: int, seed: int) -> dict:
    sweeps = [sweep(*pair, trials=trials, seed=seed) for pair in measured_pairs()]
    chosen = [s["smallest_width_at_bar"] for s in sweeps if s["smallest_width_at_bar"]]
    widest_needed = max(chosen) if chosen else None
    at_choice = [
        row
        for s in sweeps
        for row in s["widths"]
        if widest_needed and row["projected_dim"] == widest_needed
    ]
    return {
        "probe": "ticket 0499 — a seeded random projection as the chain identifier",
        "what": (
            "How much of the fp32 chain-identity margin survives a data-oblivious random "
            "projection, at each projected width. Pairs are synthetic, drawn at the cosines "
            "X8 and the per-cell ladder measured; the projection's behaviour is what is "
            "simulated, and it is distribution-free."
        ),
        "inputs": {
            "cosines_from": ss.X8.relative_to(REPO).as_posix(),
            "ladder_from": ss.CELLS.relative_to(REPO).as_posix(),
        },
        "method": {
            "projection": "Gaussian R (width x dim), scaled 1/sqrt(width), drawn from a seed",
            "header_chunks": HEADER_CHUNKS,
            "trials_per_width": trials,
            "seed": seed,
            "retention_bar": RETENTION_BAR,
            "statistic": (
                "worst trial, not the mean: an identifier is only as good as its worst "
                "header, and the mean hides the case that misidentifies a file."
            ),
            "caveat": (
                "Nothing is embedded here. This prices the projection, not the models — "
                "and it cannot rescue the 8-bit rungs, where the first arm found the ratio "
                "already below one. Preserving a ratio faithfully is no help when the "
                "ratio itself says the chains are indistinguishable."
            ),
        },
        "sweeps": sweeps,
        "verdict": {
            "models": len(sweeps),
            "narrowest_unprojected_ratio": min(s["unprojected_ratio"] for s in sweeps),
            "width_that_serves_every_model": widest_needed,
            "worst_aggregated_ratio_at_that_width": (
                min(row["worst_aggregated_ratio"] for row in at_choice) if at_choice else None
            ),
            "header_bytes_at_that_width": (
                HEADER_CHUNKS * widest_needed * 4 if widest_needed else None
            ),
            "shrink_against_widest_full_header": (
                round(max(s["full_header_bytes"] for s in sweeps) / (HEADER_CHUNKS * widest_needed * 4), 1)
                if widest_needed
                else None
            ),
            "fp32_only": (
                "This says nothing about the 8-bit rungs, and neither does any projection: "
                "at those rungs the same chain on the other arm already moves more than the "
                "nearest different chain does."
            ),
        },
    }


def render(report: dict) -> None:
    log.info("A seeded projection against the fp32 identity margin (ticket 0499)\n")
    for entry in report["sweeps"]:
        log.info(
            "%s — %d dims, same-chain cos %.6f, nearest other chain %.6f, "
            "unprojected ratio %.2fx",
            entry["model"], entry["dim"], entry["cos_same_chain"],
            entry["cos_nearest_other_chain"], entry["unprojected_ratio"],
        )
        log.info("%12s %14s %14s %12s", "projected", "header bytes", "worst ratio", "retention")
        for row in entry["widths"]:
            log.info(
                "%12d %14d %14.2f %11.1f%%",
                row["projected_dim"], row["header_bytes"], row["worst_aggregated_ratio"],
                100 * row["retention_worst_aggregated"],
            )
        log.info("")
    verdict = report["verdict"]
    log.info(
        "One width serves all %d models: %d dims, %d bytes per header — %.1fx smaller than "
        "the full fp32 header — keeping a worst-case ratio of %.2fx against the narrowest "
        "unprojected %.2fx.",
        verdict["models"], verdict["width_that_serves_every_model"],
        verdict["header_bytes_at_that_width"], verdict["shrink_against_widest_full_header"],
        verdict["worst_aggregated_ratio_at_that_width"], verdict["narrowest_unprojected_ratio"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, help="write the artifact here")
    parser.add_argument("--trials", type=int, default=200, help="headers simulated per width")
    parser.add_argument("--seed", type=int, default=20260831)
    args = parser.parse_args()

    report = build(args.trials, args.seed)
    render(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        log.info("\nwrote %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
