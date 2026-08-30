"""X8: cross-provider fidelity. DESIGN §3 owns the rule; this applies it.

Scores the GPU arm's (ticket 0264) per-(model, rung) vectors against the CPU arm's
(ticket 0263) vectors for the SAME model and rung, on the SAME 600-passage sample --
guaranteed identical rows because `quant_fidelity.mjs`'s sampling is a pure function of
(corpus length, row count), and both arms embed the byte-identical corpus file at the same
row count. Reuses `quant_fidelity_score.compare`, the same fp32-against-itself-controlled
scorer the in-arm quantization ladder uses; it is not a new scoring path.

Vector files are read as `{model_id}__{rung}.f32` / `.json` pairs from two directories, one
per arm -- the convention `bench/sweep.py --vectors-dir` writes. If the CPU arm's directory
uses the same convention, pass it directly; otherwise adapt --cpu-glob.

Rule (DESIGN §3, X8): mean cosine >= 0.999 (the field's vector-compatibility bar,
FIELD-REVIEW.md) keeps the execution provider out of the embedder key -- device stays an
execution detail recorded in results, never in vector identity. Below the bar, the provider
enters the key.

Usage:
    python3 verification/probes/x8_cross_provider_fidelity.py \
        --gpu-dir ~/data/0264-vectors --cpu-dir /path/to/0263-vectors \
        --output bench/results/0264-gpu-arm/x8-cross-provider-fidelity.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "bench"))
import quant_fidelity_score as qfs  # noqa: E402

logger = logging.getLogger("x8")

BAR = 0.999


def load_pair(directory: Path, model: str, rung: str) -> tuple[np.ndarray, dict] | None:
    meta_path = directory / f"{model}__{rung}.json"
    vec_path = directory / f"{model}__{rung}.f32"
    if not meta_path.exists() or not vec_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    vectors = np.fromfile(vec_path, dtype=np.float32).reshape(meta["rows"], meta["dim"])
    return vectors, meta


def discover_pairs(gpu_dir: Path) -> list[tuple[str, str]]:
    """(model, rung) pairs the GPU arm actually produced, from its filenames."""
    pairs = []
    for f in sorted(gpu_dir.glob("*.f32")):
        stem = f.stem  # "{model}__{rung}"
        if "__" not in stem:
            continue
        model, rung = stem.rsplit("__", 1)
        pairs.append((model, rung))
    return pairs


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--gpu-dir", type=Path, required=True)
    p.add_argument("--cpu-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--topk", type=int, default=30)
    args = p.parse_args(argv)

    if not args.cpu_dir.is_dir() or not any(args.cpu_dir.iterdir()):
        logger.warning(
            "CPU-side vectors absent at %s -- X8 is pending-CPU-side, not scored", args.cpu_dir
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "status": "pending-CPU-side",
                    "gpu_dir": str(args.gpu_dir),
                    "cpu_dir": str(args.cpu_dir),
                    "reason": "CPU-side (0263) vectors not present at the documented path when this ran",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 0

    rows = []
    for model, rung in discover_pairs(args.gpu_dir):
        gpu = load_pair(args.gpu_dir, model, rung)
        cpu = load_pair(args.cpu_dir, model, rung)
        if gpu is None or cpu is None:
            rows.append({"model": model, "rung": rung, "status": "missing", "have_gpu": gpu is not None, "have_cpu": cpu is not None})
            continue
        gpu_vec, gpu_meta = gpu
        cpu_vec, cpu_meta = cpu
        if gpu_vec.shape != cpu_vec.shape:
            rows.append(
                {
                    "model": model,
                    "rung": rung,
                    "status": "shape-mismatch",
                    "gpu_shape": list(gpu_vec.shape),
                    "cpu_shape": list(cpu_vec.shape),
                }
            )
            continue
        metrics = qfs.compare(cpu_vec, gpu_vec, k=args.topk)
        metrics.update(
            {
                "model": model,
                "rung": rung,
                "status": "scored",
                "clears_bar": metrics["cos_mean"] >= BAR,
                "bar": BAR,
            }
        )
        rows.append(metrics)
        logger.info(
            "%s %s: cos_mean=%.6f clears=%s", model, rung, metrics["cos_mean"], metrics["clears_bar"]
        )

    scored = [r for r in rows if r["status"] == "scored"]
    verdict = None
    if scored:
        verdict = "all-clear" if all(r["clears_bar"] for r in scored) else "some-below-bar"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"status": "scored" if scored else "no-overlap", "bar": BAR, "verdict": verdict, "rows": rows},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("wrote %s (%d scored, %d skipped)", args.output, len(scored), len(rows) - len(scored))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
