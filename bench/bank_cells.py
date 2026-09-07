"""Per-cell question counts of the menagerie bank (ticket 0733).

SPEC.md §5.2.10 requires a minimum question count per MUST cell of the lane
matrix and states no number, because a floor invented from the armchair is a
floor the bank was authored to clear. This counts what the bank actually holds,
so the number the author rules is derived from a distribution rather than
believed from a report.

A **MUST cell** is a lane both R7 and R29 make normative: R7's first-tier
languages are English, French and Vietnamese, and R29 binds all six ordered
cross-lingual pairs over them. Nine cells, three monolingual and six
cross-lingual. Every other lane in the bank rides R7's second tier, where a
set-aside is allowed if stated, and is counted here separately rather than
folded into the MUST distribution.

Two quantities are counted and they are not the same number:

* **bank count** — questions the bank holds in the cell, expected-miss records
  included. An expected-miss question is a real member of the bank (§5.2.10
  keeps it and never deletes it), but it is gated on the mechanism hiding the
  answer, not on retrieval.
* **retrieval count** — questions in the cell whose answer is reachable in the
  committed export (`expected_miss` false). This is the population a retrieval
  rate is computed over, and it is what the golden gate reports as scored.

A minimum on a retrieval rate binds the retrieval count. The bank count is
reported beside it because it is what an authoring lane can move.

    python3 bench/bank_cells.py
    python3 bench/bank_cells.py --minimum 12 --output /tmp/cells.json
"""
import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
QUESTIONS = REPO / "bench" / "fixtures" / "questions"
REPORT = REPO / "bench" / "results" / "golden" / "report.json"

BANK_SCHEMA = "menagerie-bank/v3"

#: R7's first tier: the three languages the default path MUST work in.
FIRST_TIER = ("en", "fr", "vi")

#: The MUST cells of the lane matrix: R7's three monolingual lanes plus R29's
#: six ordered cross-lingual pairs over the same tier. Order is stable so the
#: printed table does not shuffle between runs.
MUST_CELLS = tuple(
    f"{q}->{a}" for q in FIRST_TIER for a in FIRST_TIER
)

STRATA = ("core", "reserve")


def load_bank(directory: Path) -> list[dict[str, Any]]:
    """Read every question record, refusing a bank that is not the schema we count."""
    records = []
    for path in sorted(directory.glob("q-*.json")):
        record = json.loads(path.read_text())
        schema = record.get("schema")
        assert schema == BANK_SCHEMA, f"{path.name}: schema {schema!r}, expected {BANK_SCHEMA!r}"
        records.append(record)
    assert records, f"no q-*.json under {directory}"
    return records


def cell_counts(records: list[dict[str, Any]], lane: str) -> dict[str, Any]:
    """Count one lane, split the ways §5.2.10 names: stratum, mode, signal, facet."""
    rows = [r for r in records if r["lane"] == lane]
    retrieval = [r for r in rows if not r["expected_miss"]]
    return {
        "bank": len(rows),
        "retrieval": len(retrieval),
        "expected_miss": len(rows) - len(retrieval),
        "by_stratum": {
            stratum: {
                "bank": sum(1 for r in rows if r["stratum"] == stratum),
                "retrieval": sum(1 for r in retrieval if r["stratum"] == stratum),
            }
            for stratum in STRATA
        },
        "by_mode": dict(sorted(Counter(r["mode"] for r in rows).items())),
        "by_mode_retrieval": dict(sorted(Counter(r["mode"] for r in retrieval).items())),
        "by_signal": dict(sorted(Counter(r["signal"] for r in rows).items())),
        "by_facet": dict(sorted(Counter(r["facet"] for r in rows).items())),
    }


def gate_scored_by_lane(report: dict[str, Any]) -> dict[str, int]:
    """Scored counts the golden gate reports per lane, summed over both strata.

    The report groups by lane inside each stratum only, so the union is taken
    here rather than read; a lane absent from a stratum contributes zero.
    """
    totals: Counter[str] = Counter()
    for stratum in STRATA:
        for lane, block in report["ladder"]["by_stratum"][stratum]["by_lane"].items():
            totals[lane] += block["count"]
    return dict(totals)


def unevenness(counts: list[int]) -> dict[str, Any]:
    """How far the distribution is from flat, in terms that do not need a plot."""
    ordered = sorted(counts)
    total = sum(ordered)
    n = len(ordered)
    # Gini over the cell counts: 0 is a flat matrix, 1 is one cell holding all.
    gini = (
        sum((2 * i - n + 1) * value for i, value in enumerate(ordered)) / (n * total)
        if total and n
        else 0.0
    )
    return {
        "cells": n,
        "total": total,
        "min": ordered[0] if ordered else 0,
        "max": ordered[-1] if ordered else 0,
        "median": ordered[n // 2] if n else 0,
        "max_over_min": (ordered[-1] / ordered[0]) if ordered and ordered[0] else None,
        "gini": gini,
        "mean_if_flat": total / n if n else 0.0,
    }


def evaluate_floor(cells: dict[str, dict[str, Any]], minimum: int) -> dict[str, Any]:
    """Which MUST cells a candidate floor evaluates, and which it sets aside."""
    clearing = [lane for lane, c in cells.items() if c["retrieval"] >= minimum]
    aside = [lane for lane, c in cells.items() if c["retrieval"] < minimum]
    return {
        "minimum": minimum,
        "binds": "retrieval count (expected-miss questions excluded)",
        "cells_evaluated": clearing,
        "cells_set_aside": aside,
        "evaluated": len(clearing),
        "set_aside": len(aside),
        "shortfall": {lane: minimum - cells[lane]["retrieval"] for lane in aside},
    }


def build(records: list[dict[str, Any]], report: dict[str, Any] | None,
          minimum: int | None) -> dict[str, Any]:
    must = {lane: cell_counts(records, lane) for lane in MUST_CELLS}
    other_lanes = sorted({r["lane"] for r in records} - set(MUST_CELLS))
    other = {lane: cell_counts(records, lane) for lane in other_lanes}

    artifact: dict[str, Any] = {
        "ticket": "tickets/0733-set-the-minimum-question-count-per-must.erg",
        "probe": "bench/bank_cells.py",
        "bank": {
            "schema": BANK_SCHEMA,
            "questions": len(records),
            "retrieval": sum(1 for r in records if not r["expected_miss"]),
            "expected_miss": sum(1 for r in records if r["expected_miss"]),
            "modes_declared": dict(sorted(Counter(r["mode"] for r in records).items())),
        },
        "must_cells": must,
        "non_must_cells": other,
        "totals": {
            "must_bank": sum(c["bank"] for c in must.values()),
            "must_retrieval": sum(c["retrieval"] for c in must.values()),
            "non_must_bank": sum(c["bank"] for c in other.values()),
            "non_must_retrieval": sum(c["retrieval"] for c in other.values()),
        },
        "unevenness": {
            "bank": unevenness([c["bank"] for c in must.values()]),
            "retrieval": unevenness([c["retrieval"] for c in must.values()]),
        },
    }

    if report is not None:
        scored = gate_scored_by_lane(report)
        artifact["cross_check"] = {
            "source": "bench/results/golden/report.json",
            "report_schema": report["schema"],
            "gate_scored_total": report["scored_count"],
            "bank_retrieval_total": artifact["bank"]["retrieval"],
            "per_must_cell": {
                lane: {
                    "bank_retrieval": must[lane]["retrieval"],
                    "gate_scored": scored.get(lane, 0),
                    "difference": must[lane]["retrieval"] - scored.get(lane, 0),
                }
                for lane in MUST_CELLS
            },
            "agrees": all(
                must[lane]["retrieval"] == scored.get(lane, 0) for lane in MUST_CELLS
            ),
        }

    if minimum is not None:
        artifact["floor"] = evaluate_floor(must, minimum)
    return artifact


def format_table(artifact: dict[str, Any]) -> str:
    lines = [
        f"{'cell':8} {'bank':>5} {'retr':>5} {'miss':>5} {'core':>5} {'resv':>5} {'gate':>5}",
    ]
    check = artifact.get("cross_check", {}).get("per_must_cell", {})
    for lane, cell in artifact["must_cells"].items():
        gate = check.get(lane, {}).get("gate_scored", "-")
        lines.append(
            f"{lane:8} {cell['bank']:5} {cell['retrieval']:5} {cell['expected_miss']:5} "
            f"{cell['by_stratum']['core']['retrieval']:5} "
            f"{cell['by_stratum']['reserve']['retrieval']:5} {gate:>5}"
        )
    totals = artifact["totals"]
    lines.append(f"{'MUST':8} {totals['must_bank']:5} {totals['must_retrieval']:5}")
    lines.append(f"{'other':8} {totals['non_must_bank']:5} {totals['non_must_retrieval']:5}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=Path, default=QUESTIONS,
                        help="the bank directory of q-*.json records")
    parser.add_argument("--report", type=Path, default=REPORT,
                        help="golden gate report to cross-check scored counts against")
    parser.add_argument("--no-report", action="store_true",
                        help="count the bank alone, with no cross-check")
    parser.add_argument("--minimum", type=int, default=None,
                        help="evaluate a candidate per-cell floor against the distribution")
    parser.add_argument("--output", type=Path, default=None,
                        help="write the full artifact as JSON here")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    records = load_bank(args.questions)
    report = None
    if not args.no_report and args.report.exists():
        report = json.loads(args.report.read_text())

    artifact = build(records, report, args.minimum)
    logging.info(format_table(artifact))
    if report is not None:
        check = artifact["cross_check"]
        logging.info("cross-check against the gate: %s",
                     "agrees on every MUST cell" if check["agrees"] else "DIFFERS, see artifact")
    if args.minimum is not None:
        floor = artifact["floor"]
        logging.info("floor %d: %d MUST cells evaluated, %d set aside (%s)",
                     floor["minimum"], floor["evaluated"], floor["set_aside"],
                     ", ".join(floor["cells_set_aside"]) or "none")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2) + "\n")


if __name__ == "__main__":
    main()
