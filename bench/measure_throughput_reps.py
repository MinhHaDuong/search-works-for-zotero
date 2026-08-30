"""Repeated-process throughput measurement at the deployable rungs (ticket 0482).

`bench/sweep.py`'s fidelity kind runs one rep per cell (`KIND_REPS["fidelity"] = 1`) --
right for correctness, since the vectors do not change run to run, but not enough to
report a spread for a THROUGHPUT figure. This script re-runs `quant_fidelity.mjs`
directly, several fresh processes per (model, dtype), and reports median + spread --
the same "fresh process per rep" discipline `RealExecutor._aggregate_reps` already uses
for the cost kind's RSS figure, applied here to `ms_per_passage`.

Writes to a SCRATCH prefix, never the campaign's `--vectors-dir` -- overwriting a
fidelity cell's persisted reference/rung vectors here would silently invalidate the X8
vectors that same directory feeds ticket 0482's action 2, and this script's own vectors
are discarded after each rep's timing is read (`--rows` here is the same 600-row sample,
not the full 93 022-row corpus; the full-corpus figure is a projection, matching the
methodology tickets 0264/0481 established and cross-validated).

    python3 bench/measure_throughput_reps.py --pkg-root ~/data/zoteus-bench-pkg \
        --corpus ~/data/zoteus-bench/vec-real/passages.txt --model multilingual-e5-small \
        --dtype fp32 --device cuda --reps 3 --scratch-dir ~/data/0482-throughput \
        --output bench/results/0482-gpu-corrected/throughput/multilingual-e5-small__fp32.json
"""

import argparse
import json
import logging
import statistics
import subprocess
from pathlib import Path

logger = logging.getLogger("measure_throughput_reps")

BENCH = Path(__file__).resolve().parent

CORPUS_ROWS = 93022  # ticket 0263/0264's real-passage corpus; see CLAUDE.md Environment notes


def run_once(pkg_root: Path, corpus: Path, out_prefix: Path, model: str, dtype: str, device: str, rows: int, batch: int) -> dict:
    cmd = [
        "node",
        str(BENCH / "quant_fidelity.mjs"),
        "--pkg-root", str(pkg_root),
        "--corpus", str(corpus),
        "--out-prefix", str(out_prefix),
        "--model", model,
        "--dtype", dtype,
        "--device", device,
        "--rows", str(rows),
        "--batch", str(batch),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    meta_path = out_prefix.with_suffix(".json")
    vec_path = out_prefix.with_suffix(".f32")
    if not meta_path.is_file():
        raise RuntimeError(
            f"rep for {model}/{dtype}/{device} produced no output "
            f"(returncode={result.returncode}); stderr tail: {(result.stderr or '')[-2000:]}"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # Vectors are not needed after the timing is read -- this is a throughput
    # measurement, not a fidelity one, and the scratch prefix is not X8's vectors-dir.
    vec_path.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)
    return meta


def measure(pkg_root: Path, corpus: Path, scratch_dir: Path, model: str, dtype: str, device: str, rows: int, batch: int, reps: int) -> dict:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    reps_data = []
    for rep in range(reps):
        prefix = scratch_dir / f"{model}__{dtype}__{device}__b{batch}__r{rows}__rep{rep}"
        meta = run_once(pkg_root, corpus, prefix, model, dtype, device, rows, batch)
        reps_data.append(meta["ms_per_passage"])
        logger.info("%s %s %s batch=%d rep=%d: %.2f ms/passage", model, dtype, device, batch, rep, meta["ms_per_passage"])
    median = statistics.median(reps_data)
    return {
        "model": model,
        "dtype": dtype,
        "device": device,
        "rows": rows,
        "batch": batch,
        "reps": reps,
        "ms_per_passage_reps": reps_data,
        "ms_per_passage_median": round(median, 2),
        "ms_per_passage_spread": round(max(reps_data) - min(reps_data), 2),
        "projection_minutes_93022_rows": round(median * CORPUS_ROWS / 1000 / 60, 1),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pkg-root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--model", required=True, help="registry id")
    parser.add_argument("--dtype", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--rows", type=int, default=600)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    result = measure(
        args.pkg_root, args.corpus, args.scratch_dir, args.model, args.dtype, args.device,
        args.rows, args.batch, args.reps,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("wrote %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
