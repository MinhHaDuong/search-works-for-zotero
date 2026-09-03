"""Summarise the pooling ablation of ticket 0612: what one hardcoded pooling mode costs.

Upstream zoteus pools every model the same way at its pipeline call (`embeddings.ts`),
while half of this repository's measured candidates declare a different mode. This script
pairs each forced cell against the committed correct-pooling cell for the same model at
the same dtype, and writes one SUMMARY.json holding both arms and their difference.

It computes nothing the score files do not already contain: the per-query rows carry the
reciprocal rank and the hit flags, and the aggregate here is over every query whose gold
passage the scorer ranked (the four negative-control rows carry no rank and are counted
separately, exactly as `cross_lingual_score.py` reports them).

    python3 bench/pooling_ablation_summary.py \
      --control-dir bench/results/0266-cross-lingual \
      --ablation-dir bench/results/0612-pooling-ablation \
      --output bench/results/0612-pooling-ablation/SUMMARY.json
"""

import argparse
import json
from pathlib import Path


def aggregate(score: dict) -> dict:
    """MRR and hit@k over the queries that have a rank; the scorer's own per-query rows."""
    rows = [r for r in score["per_query"] if r["reciprocal_rank"] is not None]
    n = len(rows)
    return dict(
        queries_ranked=n,
        mrr=round(sum(r["reciprocal_rank"] for r in rows) / n, 4),
        hit_at_1=round(sum(1 for r in rows if r["hit_at_1"]) / n, 4),
        hit_at_5=round(sum(1 for r in rows if r["hit_at_5"]) / n, 4),
        hit_at_10=round(sum(1 for r in rows if r["hit_at_10"]) / n, 4),
        negative_control_clean=score["negative_control"]["clean"],
        negative_control_n=score["negative_control"]["n"],
    )


def pair(control: dict, ablation: dict) -> dict:
    # A cell that does not declare itself an ablation cannot stand in this arm: the whole
    # point of the markers is that a forced cell is never read as a measurement of the model.
    if not ablation.get("pooling_forced"):
        raise SystemExit(
            f"{ablation['model_id']}: ablation cell carries no pooling_forced marker"
        )
    if control["pooling"] != ablation["declared_pooling"]:
        raise SystemExit(
            f"{ablation['model_id']}: control pools {control['pooling']}, "
            f"ablation declares {ablation['declared_pooling']}"
        )
    if control["dtype"] != ablation["dtype"]:
        raise SystemExit(f"{ablation['model_id']}: dtype differs between arms")
    a, b = aggregate(control), aggregate(ablation)
    delta = {
        k: round(b[k] - a[k], 4)
        for k in ("mrr", "hit_at_1", "hit_at_5", "hit_at_10")
    }
    delta["mrr_relative_pct"] = round(100 * (b["mrr"] - a["mrr"]) / a["mrr"], 1)
    delta["hit_at_1_relative_pct"] = round(
        100 * (b["hit_at_1"] - a["hit_at_1"]) / a["hit_at_1"], 1
    )
    return dict(
        model_id=control["model_id"],
        model=control["model"],
        dtype=control["dtype"],
        correct_pooling=control["pooling"],
        forced_pooling=ablation["pooling"],
        template=control["template"],
        correct=a,
        forced=b,
        delta=delta,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control-dir", required=True)
    ap.add_argument("--ablation-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    control_dir, ablation_dir = Path(args.control_dir), Path(args.ablation_dir)
    cells = []
    for path in sorted(ablation_dir.glob("*-forced-mean.score.json")):
        ablation = json.loads(path.read_text())
        stem = path.name.replace("-forced-mean.score.json", "")
        control_path = control_dir / f"{stem}.score.json"
        if not control_path.exists():
            raise SystemExit(f"no control cell for {stem} at {control_path}")
        cells.append(pair(json.loads(control_path.read_text()), ablation))

    if not cells:
        raise SystemExit(f"no ablation cells found under {ablation_dir}")

    out = dict(
        ticket="0612",
        what="cost of upstream's hardcoded mean pooling on models that declare cls",
        queries_ranked=cells[0]["correct"]["queries_ranked"],
        cells=cells,
        worst_mrr_relative_pct=min(c["delta"]["mrr_relative_pct"] for c in cells),
        best_mrr_relative_pct=max(c["delta"]["mrr_relative_pct"] for c in cells),
    )
    Path(args.output).write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.output}: {len(cells)} cells")
    for c in cells:
        d = c["delta"]
        print(
            f"  {c['model_id']:32} mrr {c['correct']['mrr']:.4f} -> {c['forced']['mrr']:.4f} "
            f"({d['mrr_relative_pct']:+.1f}%)  hit@1 {d['hit_at_1_relative_pct']:+.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
