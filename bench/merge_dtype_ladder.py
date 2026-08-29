"""Merge the per-dtype cost runs into one ladder artifact, with published download sizes."""

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ORDER = ["fp32", "fp16", "q8", "int8", "uint8", "q4", "q4f16", "bnb4"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True, help="filename prefix, e.g. nomic")
    parser.add_argument("--sizes", type=Path, required=True, help="JSON map dtype -> download MB")
    parser.add_argument("--failed", default="", help="comma-separated dtypes that would not load")
    parser.add_argument("--failure-note", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    sizes = json.loads(args.sizes.read_text())
    rungs, model, machine, runtime = [], None, None, None
    for dtype in ORDER:
        path = args.sweep_dir / f"{args.tag}-{dtype}.json"
        if not path.exists():
            continue
        doc = json.loads(path.read_text())
        entry = doc["models"][0]
        model = entry["model"]
        machine, runtime = doc["machine"], doc["runtime"]
        rungs.append(
            {
                "dtype": dtype,
                "download_mb": sizes.get(dtype),
                "rss_delta_mb": entry["rss_delta_mb"],
                "query_ms_median": entry["query_ms_median"],
                "query_ms_p95": entry["query_ms_p95"],
                "load_ms": entry["load_ms"],
                "dim": entry["dim"],
            }
        )
    failed = [d for d in args.failed.split(",") if d]
    report = {
        "what": "cost of every published quantization rung, at query time (batch 1)",
        "model": model,
        "runtime": runtime,
        "rungs": rungs,
        "would_not_load": failed,
        "failure_note": args.failure_note,
        "caveats": [
            "One process per rung, warm cache: RSS is the total a fresh server process pays "
            "(ONNX Runtime and Node included), not the marginal cost of the weights. Loading a "
            "second model into a live process costs less, because the runtime is already there.",
            "load_ms is warm — the weights were already downloaded. A first run also pays the "
            "download in the size column.",
            "download_mb is the published ONNX file size on the Hugging Face repo, external "
            "data files included.",
            "Cost, not quality. Read beside the fidelity ladder, never instead of it.",
        ],
        "machine": machine,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    logger.info("wrote %s with %d rungs (%d unloadable)", args.output, len(rungs), len(failed))


if __name__ == "__main__":
    main()
