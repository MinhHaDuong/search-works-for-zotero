"""Aggregate ticket 0482's committed cells into one summary table.

The GPU-corrected re-run of 0264's fidelity campaign: `bench/sweep.py` now forwards
`--device` (ticket 0481's fix), so every cell here is a genuine GPU measurement, not the
silent CPU fallback 0264 recorded. This reads only what `run_sweep` already wrote under
`bench/results/0482-gpu-corrected/`; it embeds and scores nothing itself.

Unlike `summarize_0263.py`, this campaign runs `fidelity` only (no `cost` kind — ticket
0482 does not ask for batch-1 query latency, only the batch-8 fidelity-cell throughput and
a dedicated repeated-rep throughput measurement, kept separately under `throughput/`).

    python3 bench/summarize_0482.py [--results-dir bench/results/0482-gpu-corrected/cells]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry import candidate_ids, load_registry  # noqa: E402

logger = logging.getLogger("summarize_0482")

BENCH = Path(__file__).resolve().parent

RUNGS = ("fp32", "fp16", "q8", "uint8")


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
    """A measured cell's metrics, or the status/reason for anything else -- never absent,
    since a missing cell here is a campaign gap the summary should show, not hide.
    """
    if cell is None:
        return {"status": "missing"}
    if cell.get("status") == "measured":
        return {
            "status": "measured",
            "device_selected": cell.get("device_selected"),
            **cell.get("metrics", {}),
        }
    return {"status": cell.get("status"), "reason": cell.get("reason", cell.get("error", ""))}


def summarize(results_dir: Path) -> dict:
    registry = load_registry()
    by_id = {m["id"]: m for m in registry["models"]}
    cells = load_cells(results_dir)

    ordered = [mid for mid in candidate_ids(registry) if mid in cells]
    ordered += sorted(mid for mid in cells if mid not in ordered)

    rows = []
    for model_id in ordered:
        fidelity = cells[model_id].get("fidelity", {})
        row = {
            "model": model_id,
            "registry_status": by_id.get(model_id, {}).get("status", "unknown"),
            "fidelity": {dtype: cell_view(fidelity.get(dtype)) for dtype in RUNGS},
        }
        q8 = fidelity.get("q8")
        uint8 = fidelity.get("uint8")
        fp32 = fidelity.get("fp32")
        rate_by_rung = {}
        for dtype, cell in (("fp32", fp32), ("q8", q8), ("uint8", uint8)):
            if cell and cell.get("status") == "measured":
                rate_by_rung[dtype] = cell["metrics"]["ms_per_passage"]
        if rate_by_rung:
            row["ms_per_passage_by_rung"] = rate_by_rung
        if "q8" in rate_by_rung and "uint8" in rate_by_rung:
            # The rung the deployable-throughput measurement re-runs with repeats: whichever
            # 8-bit rung is faster on THIS host's GPU stack, not assumed from a CPU prior --
            # 0481 found the quantized matmul has no CUDA kernel, so the CPU-vs-GPU winner can
            # differ from either arm's own intuition.
            row["better_8bit_rung"] = "uint8" if rate_by_rung["uint8"] < rate_by_rung["q8"] else "q8"
        rows.append(row)

    counts = {"measured": 0, "unloadable": 0, "duplicate": 0, "failed": 0}
    for model_cells in cells.values():
        for kind_cells in model_cells.values():
            for cell in kind_cells.values():
                counts[cell.get("status", "measured")] = counts.get(cell.get("status", "measured"), 0) + 1

    return {
        "what": "ticket 0482: GPU-corrected fidelity cells for every registry candidate on "
        "padme, every rung loadable under an explicit GPU device (fp32/q8/uint8 always, "
        "fp16 attempted and recorded per ticket 0240/0264's known reliability) -- supersedes "
        "the CPU-mislabeled bench/results/0264-gpu-arm/ fidelity figures (ticket 0481)",
        "tracker": "ticket 0240",
        "results_dir": str(results_dir),
        "cells_total": sum(counts.values()),
        "counts": counts,
        "rows": rows,
    }


#: The cells live one level down from the campaign's own directory, alongside a
#: `throughput/` sibling (`bench/measure_throughput_reps.py`'s output) and this script's
#: own `SUMMARY.json`, written at the campaign level so it sits beside both.
DEFAULT_RESULTS_DIR = BENCH / "results" / "0482-gpu-corrected" / "cells"
DEFAULT_OUTPUT = BENCH / "results" / "0482-gpu-corrected" / "SUMMARY.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    summary = summarize(args.results_dir)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("wrote %s (%d rows)", args.output, len(summary["rows"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
