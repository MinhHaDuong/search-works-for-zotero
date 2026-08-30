"""Aggregate ticket 0263's committed cells into one summary table.

`bench/sweep.py`'s `sweep_report()` answers "what ran" (counts by status). This
answers the ticket's actual questions: the RSS cost curve per candidate, and —
the tracker's open question — whether nomic's q8-worse-than-uint8 ordering
generalises. It reads only what `run_sweep` already wrote under
`bench/results/0263-cpu-arm/`; it embeds and scores nothing itself, so it stays
outside the guard `check_models.py` runs against `bench/` (`bench/results/` is
its one exemption, in `RealExecutor`'s own written data) by reading the model
each row names from the JSON, never spelling one out in this file.

    python3 bench/summarize_0263.py [--results-dir bench/results/0263-cpu-arm]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry import candidate_ids, load_registry  # noqa: E402

logger = logging.getLogger("summarize_0263")

BENCH = Path(__file__).resolve().parent


def load_cells(results_dir: Path) -> dict[str, dict[str, dict]]:
    """model -> kind -> dtype -> the cell's own JSON record."""
    cells: dict[str, dict[str, dict]] = {}
    for path in sorted(results_dir.glob("*.json")):
        if path.name == "SUMMARY.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        cells.setdefault(record["model"], {}).setdefault(record["kind"], {})[record["dtype"]] = record
    return cells


def cell_view(cell: dict | None) -> dict:
    """A measured cell's metrics, or the status/reason for anything else —
    never absent, since a missing cell here is a campaign gap the summary
    should show, not hide.
    """
    if cell is None:
        return {"status": "missing"}
    if cell.get("status") == "measured":
        return {"status": "measured", **cell.get("metrics", {})}
    return {"status": cell.get("status"), "reason": cell.get("reason", cell.get("error", ""))}


def summarize(results_dir: Path) -> dict:
    registry = load_registry()
    by_id = {m["id"]: m for m in registry["models"]}
    cells = load_cells(results_dir)

    ordered = [mid for mid in candidate_ids(registry) if mid in cells]
    ordered += sorted(mid for mid in cells if mid not in ordered)

    rows = []
    for model_id in ordered:
        model_cells = cells[model_id]
        cost = model_cells.get("cost", {})
        fidelity = model_cells.get("fidelity", {})
        row = {
            "model": model_id,
            "registry_status": by_id.get(model_id, {}).get("status", "unknown"),
            "is_contrast": by_id.get(model_id, {}).get("status") != "candidate",
            "cost": {dtype: cell_view(cost.get(dtype)) for dtype in ("fp32", "fp16", "q8", "uint8")},
            "fidelity": {dtype: cell_view(fidelity.get(dtype)) for dtype in ("fp32", "fp16", "q8", "uint8")},
        }
        q8 = fidelity.get("q8")
        uint8 = fidelity.get("uint8")
        if q8 and q8.get("status") == "measured" and uint8 and uint8.get("status") == "measured":
            q8m, u8m = q8["metrics"], uint8["metrics"]
            row["q8_vs_uint8"] = {
                "q8_overlap_at_30_mean": q8m["overlap_at_30_mean"],
                "uint8_overlap_at_30_mean": u8m["overlap_at_30_mean"],
                # The retrieval-relevant ordering, not the cosine one: overlap@30 is what a
                # user's top-k actually loses, where cosine can look fine while rank moves.
                "winner": "uint8"
                if u8m["overlap_at_30_mean"] > q8m["overlap_at_30_mean"]
                else ("q8" if q8m["overlap_at_30_mean"] > u8m["overlap_at_30_mean"] else "tie"),
                # Nobody in the field measures this (DESIGN's framing): a candidate's
                # exposure to picking the WORSE of two equal-cost 8-bit rungs blind.
                "quant_robustness_worst_overlap_at_30": min(
                    q8m["overlap_at_30_mean"], u8m["overlap_at_30_mean"]
                ),
            }
        rows.append(row)

    counts = {"measured": 0, "unloadable": 0, "duplicate": 0, "failed": 0}
    for model_cells in cells.values():
        for kind_cells in model_cells.values():
            for cell in kind_cells.values():
                counts[cell.get("status", "measured")] = counts.get(cell.get("status", "measured"), 0) + 1

    return {
        "what": "ticket 0263: CPU-arm cost and fidelity for every registry candidate, "
        "every loadable dtype, plus two CONTRAST cells (all-minilm-l6-v2, bge-small-en-v15) "
        "re-measured one-process-per-cell to supersede the 0025 sequential-process figures",
        "tracker": "ticket 0240",
        "results_dir": str(results_dir),
        "cells_total": sum(counts.values()),
        "counts": counts,
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", type=Path, default=BENCH / "results" / "0263-cpu-arm")
    parser.add_argument("--output", type=Path, help="default: <results-dir>/SUMMARY.json")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    summary = summarize(args.results_dir)
    out = args.output or (args.results_dir / "SUMMARY.json")
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("wrote %s (%d rows)", out, len(summary["rows"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
