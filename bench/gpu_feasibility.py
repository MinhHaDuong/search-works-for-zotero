"""GPU embedding throughput, derived from the run logs of bench/embed_corpus.py.

The CPU half of this question is measured directly by bench/embed_feasibility.mjs. This is
the other half, and it is DERIVED rather than measured on purpose: the runs it reads are the
ones that produced the vectors in bench/results/0025-x1-recall/, so the numbers describe
work that actually happened rather than a benchmark staged to produce them. Re-running three
embeddings of 93 022 passages to time them again would cost an hour of GPU and tell us what
the logs already record.

Two consequences of deriving rather than measuring, both stated in the output:

  - Wall clock includes model load, and for a first run also the download. The per-passage
    figure is therefore an upper bound on the steady-state cost, generous to the CPU side of
    any comparison and never flattering to the GPU.
  - `hours_to_index` scales one corpus size to another by simple proportion. That is an
    arithmetic projection, not a measurement, and it assumes the pipeline stays batch-bound
    at the larger size. The factor is printed so the reader can see what was multiplied.
"""

import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("gpu_feasibility")

# `2026-08-29 10:32:38,743 INFO loading Qwen/Qwen3-Embedding-0.6B on cuda (torch.float16)`
LOAD = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) INFO loading (?P<model>\S+) on (?P<device>\S+) \((?P<dtype>[^)]+)\)"
)
# `2026-08-29 11:07:08,498 INFO done: 93022 rows x 1024 dims -> qwen06b.f32`
DONE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) INFO done: (?P<rows>\d+) rows x (?P<dim>\d+) dims"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--log", type=Path, nargs="+", required=True, help="embed_corpus.py run logs")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--gpu", required=True, help="the device the runs used, for the record")
    p.add_argument("--scale", type=int, default=255703, help="corpus size to project onto")
    return p.parse_args()


def read_run(path: Path) -> dict | None:
    start = done = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if start is None and (m := LOAD.match(line)):
            start = m
        elif m := DONE.match(line):
            done = m
    if not start or not done:
        logger.warning("%s: no complete run (load=%s, done=%s)", path, bool(start), bool(done))
        return None
    fmt = "%Y-%m-%d %H:%M:%S,%f"
    seconds = (
        datetime.strptime(done["ts"], fmt) - datetime.strptime(start["ts"], fmt)
    ).total_seconds()
    rows = int(done["rows"])
    per_row_ms = seconds * 1000 / rows
    return {
        "model": start["model"],
        "device": start["device"],
        "dtype": start["dtype"],
        "dim": int(done["dim"]),
        "rows": rows,
        "wall_seconds": round(seconds, 1),
        "ms_per_passage": round(per_row_ms, 2),
        "passages_per_min": round(60000 / per_row_ms),
        "log": str(path),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    runs = [r for p in args.log if (r := read_run(p))]
    if not runs:
        raise SystemExit("no complete runs found in the given logs")
    for r in runs:
        factor = args.scale / r["rows"]
        r["projection_factor"] = round(factor, 3)
        r["hours_to_index_projected"] = round(r["wall_seconds"] * factor / 3600, 2)
        logger.info(
            "%-38s dim %4d  %6.2f ms/passage  %6d/min  -> %.2f h for %d (x%.2f)",
            r["model"], r["dim"], r["ms_per_passage"], r["passages_per_min"],
            r["hours_to_index_projected"], args.scale, factor,
        )

    args.output.write_text(
        json.dumps(
            {
                "what": "GPU embedding throughput, derived from the logs of the runs that "
                "produced this directory's vectors",
                "derived_not_measured": (
                    "Wall clock is taken between the 'loading' and 'done' lines of each run, "
                    "so it includes model load and, on a first run, download. The per-passage "
                    "cost is therefore an UPPER bound, which is the safe direction: it never "
                    "flatters the GPU against the directly-measured CPU figures in "
                    "embed-feasibility.json."
                ),
                "projection": (
                    f"hours_to_index_projected scales each run's own wall clock to "
                    f"{args.scale} passages by simple proportion. An arithmetic projection, "
                    "not a measurement; the factor used is recorded per run."
                ),
                "gpu": args.gpu,
                "projected_to": args.scale,
                "runs": runs,
                "compare_with": "bench/results/0025-x1-recall/embed-feasibility.json (CPU, "
                "measured in the ONNX runtime zoteus ships; this file is PyTorch on CUDA, "
                "which is what the vectors were actually built with — a different stack, so "
                "read the CPU/GPU gap as an order of magnitude and not a ratio to two figures)",
            },
            indent=2,
        )
        + "\n"
    )
    logger.info("wrote %s", args.output)


if __name__ == "__main__":
    main()
