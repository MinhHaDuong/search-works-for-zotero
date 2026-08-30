"""Aggregate ticket 0266's committed cross-lingual cells into one summary table.

Reads every `bench/results/0266-cross-lingual/*.score.json` (one per model x
dtype, written by `cross_lingual_score.py`) and produces `SUMMARY.json`: for
each candidate, at each deployed dtype (q8, uint8; fp32 as reference), the
per-(query_lang, target_lang) hit@10/MRR pairs and the negative-control
result. Reads the model each cell names from its own JSON, same discipline as
`summarize_0263.py`, so this stays outside `check_models.py`'s scan (which
exempts `bench/results/`).

    python3 bench/summarize_0266.py [--results-dir bench/results/0266-cross-lingual]
"""

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger("summarize_0266")

BENCH = Path(__file__).resolve().parent


def load_cells(results_dir: Path) -> list[dict]:
    cells = []
    for path in sorted(results_dir.glob("*.score.json")):
        if path.name == "SUMMARY.json":
            continue
        cells.append(json.loads(path.read_text(encoding="utf-8")))
    return cells


def summarize(results_dir: Path) -> dict:
    cells = load_cells(results_dir)
    rows = []
    by_key = {}
    for cell in cells:
        row = {
            "model_id": cell["model_id"],
            "dtype": cell["dtype"],
            "is_contrast": cell.get("model_id") == "all-minilm-l6-v2",
            "pool_size": cell["pool_size"],
            "query_count": cell["query_count"],
            "pair_summary": cell["pair_summary"],
            "negative_control": cell["negative_control"],
        }
        rows.append(row)
        # Keyed by a stable, order-independent string so a prose figure can be
        # anchored at "cells.<model>__<dtype>.…" without depending on list
        # order (unlike `rows`, which sorts and can reorder on a re-run).
        by_key[f"{cell['model_id']}__{cell['dtype']}"] = row
    rows.sort(key=lambda r: (r["is_contrast"], r["model_id"], r["dtype"]))
    return {
        "schema": "0266 cross-lingual probe summary, v1",
        "ticket": "tickets/0266-cross-lingual-probe-on-the-multilingual.erg",
        "cells_total": len(rows),
        "rows": rows,
        "cells": by_key,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(BENCH / "results" / "0266-cross-lingual"))
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    results_dir = Path(args.results_dir)
    summary = summarize(results_dir)
    output = Path(args.output) if args.output else results_dir / "SUMMARY.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("%s: %d cells -> %s", results_dir, summary["cells_total"], output)


if __name__ == "__main__":
    main()
