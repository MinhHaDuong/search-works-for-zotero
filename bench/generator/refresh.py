#!/usr/bin/env python3
"""Recompute a run artifact's aggregates from its private readings, identity untouched.

    python3 -m bench.generator.refresh --work-dir <private dir> --output bench/results/0719-generator/run.json

The readings a run wrote to its work directory are the whole of what the ladder
aggregates; when `run.report()` gains a table, the artifact of a finished run can
carry it without asking the engine again. The identity block, the sample summary
and the questions summary are kept as the run recorded them — this recomputes
only what is a pure function of the readings, and records that it did.
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from bench.generator import run as R


def refresh(output: Path, work_dir: Path) -> dict:
    doc = json.loads(output.read_text(encoding="utf-8"))
    readings = [json.loads(line) for line in (work_dir / "readings.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    fresh = R.report(readings, doc["sample"], doc["questions"])
    doc["ladder"] = fresh["ladder"]
    doc["chain_in_reply"] = fresh["chain_in_reply"]
    doc["readings"] = fresh["readings"]
    doc.setdefault("refreshed", []).append({
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "what": "ladder, chain_in_reply and readings recomputed from readings.jsonl; identity, sample and questions untouched",
    })
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    doc = refresh(args.output, args.work_dir)
    args.output.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(R.markdown(doc))
    logging.info("refreshed %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
