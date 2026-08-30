"""Assemble ticket 0265's committed results from the scoring pass's raw outputs.

Ticket 0265: recall at the deployed dtype, and the fused RRF delta. This script does no
measuring itself -- `recall_embed.mjs` embeds, `vec_task_recall.mjs` scores the vector arm
(the canonical driver ticket 0240's tracker names), `fused_recall.mjs` scores the fused RRF
arm against `fts5_keyword_arm.mjs`'s shared keyword arm. This reads what those wrote,
cross-checks the one invariant that must hold if they agree with each other (the vector-arm
recall figure fused_recall.mjs computed independently must equal vec_task_recall.mjs's own),
and writes one committed JSON per cell plus a SUMMARY.

Fidelity is NOT duplicated here. `bench/results/0263-cpu-arm/SUMMARY.json` is the fidelity
figure's one home (CLAUDE.md's one-statement-per-fact convention); each cell below carries a
POINTER to its row there, never a copied cos_mean. The campaign's own prose (the ticket 0265
log entry) quotes both columns side by side and cites each artifact separately.

Usage:
  python3 bench/build_0265_summary.py \
    --data-dir /home/haduong/data/projets/zoteus-bench/0265 \
    --results-dir bench/results/0265-recall-fusion \
    --fidelity-summary bench/results/0263-cpu-arm/SUMMARY.json
"""

import argparse
import json
import logging
import statistics
from pathlib import Path

logger = logging.getLogger("build_0265_summary")

MODELS = [
    "granite-97m-multilingual-r2",
    "granite-311m-multilingual-r2",
    "arctic-embed-m-v2",
    "gte-multilingual-base",
    "multilingual-e5-small",
    "multilingual-e5-base",
]
DTYPES = ["fp32", "q8", "uint8"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data-dir", type=Path, required=True, help="the 0265 scratch dir (vectors/, scores/, keyword-arm.json, subsample-meta.json)")
    p.add_argument("--results-dir", type=Path, required=True, help="committed output dir")
    p.add_argument("--fidelity-summary", type=Path, required=True)
    return p.parse_args()


def load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_fidelity_row(fidelity_summary: dict, model: str) -> int | None:
    for i, row in enumerate(fidelity_summary.get("rows", [])):
        if row.get("model") == model:
            return i
    return None


def fusion_gain_analysis(rows: list[dict]) -> dict:
    """How much of the vector arm's isolated gain over keyword-alone survives fusion.

    "Healthy" is defined mechanically, not by naming a model: any cell whose vector arm
    already LOSES to keyword-alone (a negative gain) is a broken rung, not a washing-out
    case, and is reported separately rather than folded into the range/fraction below --
    it would drag the range toward numbers that describe a different phenomenon.
    """
    healthy = [r for r in rows if r["vector_arm_gain_over_keyword"] >= 0]
    broken = [r for r in rows if r["vector_arm_gain_over_keyword"] < 0]
    vg = [r["vector_arm_gain_over_keyword"] for r in healthy]
    fg = [r["fused_gain_over_keyword"] for r in healthy]
    fractions = [f / v for f, v in zip(fg, vg) if v]
    return {
        "what": "of the cells where the vector arm beats keyword-alone, how much of that "
        "gain survives fusion into the fused RRF arm",
        "healthy_cells": len(healthy),
        "broken_cells": [f"{r['model']}/{r['dtype']}" for r in broken],
        "vector_arm_gain_range": [round(min(vg), 4), round(max(vg), 4)] if vg else None,
        "fused_gain_range": [round(min(fg), 4), round(max(fg), 4)] if fg else None,
        "fraction_of_vector_gain_surviving_fusion_mean": round(sum(fractions) / len(fractions), 4)
        if fractions
        else None,
        "fraction_of_vector_gain_surviving_fusion_median": round(statistics.median(fractions), 4)
        if fractions
        else None,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    subsample_meta = load(args.data_dir / "subsample-meta.json")
    keyword_arm = load(args.data_dir / "keyword-arm.json")
    fidelity_summary = load(args.fidelity_summary)
    if subsample_meta is None or keyword_arm is None or fidelity_summary is None:
        raise SystemExit("missing subsample-meta.json, keyword-arm.json, or the 0263 fidelity summary")

    args.results_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    mismatches = []
    missing = []

    for model in MODELS:
        fidelity_row_idx = find_fidelity_row(fidelity_summary, model)
        for dtype in DTYPES:
            vec_path = args.data_dir / "scores" / f"{model}__{dtype}__vec_task_recall.json"
            fuse_path = args.data_dir / "scores" / f"{model}__{dtype}__fusion.json"
            embed_meta_path = args.data_dir / "vectors" / f"{model}__{dtype}.json"
            vec = load(vec_path)
            fuse = load(fuse_path)
            embed_meta = load(embed_meta_path)
            if vec is None or fuse is None or embed_meta is None:
                missing.append(f"{model}/{dtype}")
                continue

            # vec_task_recall.mjs nests the figure under models[0].at[0] (its "at" list is
            # for Matryoshka width sweeps; a single-width run like this campaign's still
            # writes a one-element list, per its own --widths handling).
            vec_model = vec["models"][0]["at"][0]
            # The seam invariant: two independently-written scorers (vec_task_recall.mjs's
            # aggregate and fused_recall.mjs's own vector-arm reimplementation, needed
            # because vec_task_recall.mjs exposes no raw ranklist to fuse against) must
            # agree on the vector-only figure, or something in the duplicated candidate-
            # exclusion / cosine logic has drifted.
            if vec_model["recall_at_topk"] != fuse["vector_arm"]["recall_at_topk"]:
                mismatches.append(
                    f"{model}/{dtype}: vec_task_recall {vec_model['recall_at_topk']} != "
                    f"fused_recall vector_arm {fuse['vector_arm']['recall_at_topk']}"
                )
            if embed_meta["dtype"] != dtype:
                mismatches.append(
                    f"{model}/{dtype}: embedding metadata dtype {embed_meta['dtype']!r} != cell dtype {dtype!r}"
                )
            if embed_meta["model_id"] != model:
                mismatches.append(
                    f"{model}/{dtype}: embedding metadata model_id {embed_meta['model_id']!r} != cell model {model!r}"
                )

            row = {
                "model": model,
                "dtype": dtype,
                "device": "cpu",
                "embedding": embed_meta,
                "vector_recall": vec_model,
                "keyword_arm": fuse["keyword_arm"],
                "vector_arm": fuse["vector_arm"],
                "fused_arm": fuse["fused_arm"],
                "vector_arm_gain_over_keyword": fuse["vector_arm_gain_over_keyword"],
                "fused_gain_over_keyword": fuse["fused_gain_over_keyword"],
                "fusion_rule": fuse["fusion_rule"],
                "fidelity_pointer": {
                    "source": "bench/results/0263-cpu-arm/SUMMARY.json",
                    "row_index": fidelity_row_idx,
                    "dtype_key": dtype,
                    "note": "reused from ticket 0263, not re-measured here -- see "
                    f"rows.{fidelity_row_idx}.fidelity.{dtype} for cos_mean / overlap_at_30_mean / top1_kept_frac",
                }
                if fidelity_row_idx is not None
                else None,
            }
            rows.append(row)
            out_path = args.results_dir / f"{model}__{dtype}.json"
            out_path.write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "what": "ticket 0265: recall at the deployed dtype, and the fused RRF delta -- "
        "vector-arm and fused-arm same-item retrieval for every 0263-surviving "
        "(candidate, rung), scored on one seeded subsample of the real 93 022-passage "
        "corpus",
        "tracker": "ticket 0240",
        "ticket": "tickets/0265-recall-at-the-deployed-dtype-and-the-fus.erg",
        "subsample": subsample_meta,
        "keyword_arm": {
            "recall_at_topk": keyword_arm["recall_at_topk"],
            "mrr": keyword_arm["mrr"],
            "probes": keyword_arm["probes"],
            "corpus": keyword_arm["corpus"],
            "task": keyword_arm["task"],
            "not_this": keyword_arm["not_this"],
            "source": "bench/results/0265-recall-fusion/keyword-arm.json (shared across every cell)",
        },
        "cells_total": len(MODELS) * len(DTYPES),
        "cells_present": len(rows),
        "missing": missing,
        "mismatches": mismatches,
        "fusion_gain_analysis": fusion_gain_analysis(rows),
        "rows": rows,
    }
    (args.results_dir / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    if missing:
        logger.warning("missing cells: %s", ", ".join(missing))
    if mismatches:
        for m in mismatches:
            logger.error("MISMATCH: %s", m)
        raise SystemExit(f"{len(mismatches)} consistency mismatch(es) -- see above")
    logger.info("wrote %d cells + SUMMARY.json to %s", len(rows), args.results_dir)


if __name__ == "__main__":
    main()
