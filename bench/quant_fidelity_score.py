"""Score a quantization ladder against its own fp32 rung.

`quant_fidelity.mjs` embeds one fixed passage sample at each dtype. This reads those
files and answers the two questions a cost curve cannot:

  1. **Fidelity** — per-row cosine between the dtype vector and the fp32 vector. This is
     `cboulanger/zotero-rag`'s compatibility gate (cosine >= 0,999 on probe texts before two
     models are called vector-compatible), applied to a dtype instead of a model. It prices
     the deployment shortcut of building a corpus at one dtype and serving queries at
     another.
  2. **Rank agreement** — both sides quantized, the sample used as its own corpus and its own
     query set, top-k compared against the fp32 ranking of the same sample. Fidelity can look
     fine while ranking moves, because retrieval reads order and cosine reads magnitude of
     agreement. Overlap is the number closer to what a user sees.

Absolute recall on a sample pool is not the recall of the full corpus: a 400-row pool is an
easier retrieval problem than 93 022 rows. Read the rungs against each other, never against
`0025-x1-recall/task-recall.json`.

Optionally `--pytorch-reference` scores the ONNX fp32 rung against the committed
sentence-transformers vectors at the same row indices. That is a different question from the
ladder — whether the corpora this repo measured recall on are even in the space the shipped
runtime produces — and it is reported apart, never mixed into the dtype curve.
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

LADDER = ["fp32", "fp16", "q8", "int8", "uint8", "q4", "q4f16", "bnb4"]


def load_rung(prefix: Path, dtype: str) -> tuple[np.ndarray, dict] | None:
    meta_path = prefix.with_name(f"{prefix.name}-{dtype}.json")
    vec_path = prefix.with_name(f"{prefix.name}-{dtype}.f32")
    if not meta_path.exists() or not vec_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    vectors = np.fromfile(vec_path, dtype=np.float32).reshape(meta["rows"], meta["dim"])
    return vectors, meta


def unit(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def topk_sets(vectors: np.ndarray, k: int) -> np.ndarray:
    """Top-k neighbours of every row, self excluded."""
    sims = unit(vectors) @ unit(vectors).T
    np.fill_diagonal(sims, -np.inf)
    return np.argpartition(-sims, k, axis=1)[:, :k]


def compare(reference: np.ndarray, other: np.ndarray, k: int) -> dict:
    cos = np.sum(unit(reference) * unit(other), axis=1)
    ref_top = topk_sets(reference, k)
    oth_top = topk_sets(other, k)
    overlap = [
        len(set(ref_top[i].tolist()) & set(oth_top[i].tolist())) / k for i in range(len(ref_top))
    ]
    # Whether the single best fp32 neighbour survives anywhere in the dtype's top-k: the
    # coarsest thing a user would notice, and the last to break.
    best_kept = [ref_top[i][0] in set(oth_top[i].tolist()) for i in range(len(ref_top))]
    return {
        "cos_mean": round(float(np.mean(cos)), 6),
        "cos_p05": round(float(np.percentile(cos, 5)), 6),
        "cos_min": round(float(np.min(cos)), 6),
        "cos_ge_0999_frac": round(float(np.mean(cos >= 0.999)), 4),
        f"overlap_at_{k}_mean": round(float(np.mean(overlap)), 4),
        f"overlap_at_{k}_p05": round(float(np.percentile(overlap, 5)), 4),
        "top1_kept_frac": round(float(np.mean(best_kept)), 4),
    }


def score_ladder(prefix: Path, k: int) -> list[dict]:
    reference = load_rung(prefix, "fp32")
    if reference is None:
        raise SystemExit(f"no fp32 rung at {prefix}-fp32.f32 — it is the reference")
    ref_vectors, ref_meta = reference
    rows = []
    for dtype in LADDER:
        rung = load_rung(prefix, dtype)
        if rung is None:
            logger.warning("rung %s absent, skipping", dtype)
            continue
        vectors, meta = rung
        if vectors.shape != ref_vectors.shape:
            logger.warning("rung %s shape %s != fp32 %s, skipping", dtype, vectors.shape, ref_vectors.shape)
            continue
        row = {"dtype": dtype, "ms_per_passage": meta["ms_per_passage"], "load_ms": meta["load_ms"]}
        row.update(compare(ref_vectors, vectors, k))
        rows.append(row)
    logger.info("scored %d rungs against fp32 (%d rows, dim %d)", len(rows), ref_meta["rows"], ref_meta["dim"])
    return rows


def score_pytorch(prefix: Path, pytorch_f32: Path, dim: int) -> dict:
    """ONNX fp32 versus the committed sentence-transformers vectors, same rows."""
    ref_vectors, meta = load_rung(prefix, "fp32")
    committed = np.memmap(pytorch_f32, dtype=np.float32, mode="r").reshape(-1, dim)
    picked = np.asarray(committed[meta["row_index"], :], dtype=np.float32)
    result = compare(ref_vectors, picked, 30)
    result["note"] = (
        "ONNX fp32 versus sentence-transformers/PyTorch on the same rows. A different "
        "question from the dtype ladder: it asks whether the committed corpora are in the "
        "space the shipped runtime produces."
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True, help="path prefix; reads <prefix>-<dtype>.f32")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--topk", type=int, default=30, help="k for the rank-agreement comparison")
    parser.add_argument("--pytorch-reference", type=Path, help="committed .f32 to cross-check ONNX fp32 against")
    parser.add_argument("--pytorch-dim", type=int, help="dim of --pytorch-reference")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    _, ref_meta = load_rung(args.prefix, "fp32")
    report = {
        "what": "quantization ladder scored against its own ONNX fp32 rung",
        "model": ref_meta["model"],
        "rows": ref_meta["rows"],
        "dim": ref_meta["dim"],
        "topk": args.topk,
        "runtime": ref_meta["runtime"],
        "rungs": score_ladder(args.prefix, args.topk),
        "caveats": [
            "Absolute overlap on a sample pool is not full-corpus recall: a small pool is an "
            "easier retrieval problem. Read rungs against each other.",
            "fp32 means ONNX fp32 from this same driver, so the ladder isolates quantization "
            "and not the PyTorch-versus-ONNX stack difference.",
            "Cost, not quality, is in query-cost*.json; recall is in task-recall*.json. This "
            "file is neither: it is the damage a dtype does relative to fp32.",
        ],
    }
    if args.pytorch_reference:
        if not args.pytorch_dim:
            raise SystemExit("--pytorch-reference needs --pytorch-dim")
        report["onnx_vs_pytorch_fp32"] = score_pytorch(
            args.prefix, args.pytorch_reference, args.pytorch_dim
        )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    logger.info("wrote %s", args.output)


if __name__ == "__main__":
    main()
