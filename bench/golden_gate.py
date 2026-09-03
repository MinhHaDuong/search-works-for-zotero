#!/usr/bin/env python3
"""Score golden answer sets without requiring Zotero or a model runtime.

The committed corpus export and the code that replays it belong to ticket 0029.
This scorer accepts their eventual result as plain JSON.  It deliberately reads
the stability policy from SPEC.md rather than becoming a second owner for the
gate's design numbers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PASS = "pass"
FAIL = "fail"
NOT_RUN = "not-run"

INPUT_SCHEMA = "golden-gate-input/v1"
REPORT_SCHEMA = "golden-gate-report/v1"
THRESHOLD_SOURCE = "SPEC.md §5.2.8"
SLICES = ("monolingual", "cross-lingual")
FACETS = ("core", "notes", "group", "deep-body")


class InputError(ValueError):
    """The scorer cannot give a meaningful verdict for the supplied input."""


@dataclass(frozen=True)
class Thresholds:
    """Golden-gate policy resolved from its authoritative source."""

    k: int
    mean_min: float
    below_max_fraction: float
    below_cutoff: float
    hard_floor: float
    source: str = THRESHOLD_SOURCE


def _one_match(pattern: str, text: str, label: str) -> str:
    matches = re.findall(pattern, text, flags=re.DOTALL)
    if len(matches) != 1:
        raise InputError(
            f"could not resolve exactly one {label} from {THRESHOLD_SOURCE}"
        )
    return matches[0]


def load_thresholds(spec_path: Path) -> Thresholds:
    """Resolve the golden policy directly from SPEC.md's owning paragraph."""

    try:
        spec = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read threshold source {spec_path}: {exc}") from exc

    start_marker = "- **The golden gate (D11 = set)**"
    end_marker = "- **R13, the soak gate.**"
    start = spec.find(start_marker)
    end = spec.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise InputError(f"cannot locate the golden-gate paragraph in {spec_path}")
    section = spec[start:end]

    k = int(_one_match(r"answer \*sets\* at k=(\d+)", section, "answer-set depth"))
    mean_min = float(
        _one_match(r"mean Jaccard\s*≥\s*([0-9]+(?:\.[0-9]+)?)", section, "mean")
    )
    below_percent = float(
        _one_match(
            r"at most\s+([0-9]+(?:\.[0-9]+)?)\s*%\s+of queries below",
            section,
            "below-cutoff fraction",
        )
    )
    below_cutoff = float(
        _one_match(
            r"at most\s+[0-9]+(?:\.[0-9]+)?\s*%\s+of queries below\s+"
            r"([0-9]+(?:\.[0-9]+)?)",
            section,
            "below-cutoff boundary",
        )
    )
    hard_floor = float(
        _one_match(
            r"hard floor of\s+([0-9]+(?:\.[0-9]+)?)",
            section,
            "hard floor",
        )
    )
    thresholds = Thresholds(
        k=k,
        mean_min=mean_min,
        below_max_fraction=below_percent / 100,
        below_cutoff=below_cutoff,
        hard_floor=hard_floor,
    )
    if not (
        thresholds.k > 0
        and 0 < thresholds.hard_floor
        <= thresholds.below_cutoff
        <= thresholds.mean_min
        <= 1
        and 0 <= thresholds.below_max_fraction <= 1
    ):
        raise InputError(f"invalid golden-gate policy in {spec_path}")
    return thresholds


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field} must be a non-empty string")
    return value


def _answer_set(
    value: Any,
    field: str,
    *,
    k: int,
    may_be_empty: bool,
) -> list[str]:
    if not isinstance(value, list):
        raise InputError(f"{field} must be a list")
    if not may_be_empty and not value:
        raise InputError(f"{field} must not be empty")
    answers = [_string(answer, f"{field} answer") for answer in value]
    if len(answers) != len(set(answers)):
        raise InputError(f"{field} must be a set encoded as a duplicate-free list")
    if len(answers) > k:
        raise InputError(f"{field} exceeds the k resolved from {THRESHOLD_SOURCE}")
    return answers


def _validate(bundle: Any, thresholds: Thresholds) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise InputError("input must be a JSON object")
    if bundle.get("schema") != INPUT_SCHEMA:
        raise InputError(f"schema must be {INPUT_SCHEMA}")
    for field in ("corpus_revision", "baseline_revision", "candidate_revision"):
        _string(bundle.get(field), field)
    if bundle.get("granularity") not in {"item", "entry"}:
        raise InputError("granularity must be item or entry")

    raw_facets = bundle.get("covered_facets")
    if not isinstance(raw_facets, list) or not raw_facets:
        raise InputError("covered_facets must be a non-empty list")
    covered_facets = [
        _string(facet, "covered_facets value") for facet in raw_facets
    ]
    if len(covered_facets) != len(set(covered_facets)):
        raise InputError("covered_facets must not contain duplicates")
    unknown_covered = sorted(set(covered_facets) - set(FACETS))
    if unknown_covered:
        raise InputError(f"unknown covered facets: {unknown_covered}")

    raw_queries = bundle.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise InputError("queries must be a non-empty list")
    queries: list[dict[str, Any]] = []
    ids: set[str] = set()
    for position, raw_query in enumerate(raw_queries):
        if not isinstance(raw_query, dict):
            raise InputError(f"queries[{position}] must be an object")
        qid = _string(raw_query.get("id"), f"queries[{position}].id")
        if qid in ids:
            raise InputError(f"duplicate query id: {qid}")
        ids.add(qid)
        slice_ = raw_query.get("slice")
        if slice_ not in SLICES:
            raise InputError(f"query {qid} slice must name one of {SLICES}")
        facet = _string(raw_query.get("facet"), f"query {qid} facet")
        if facet not in FACETS:
            raise InputError(f"query {qid} facet must name one of {FACETS}")
        queries.append(
            {
                "id": qid,
                "slice": slice_,
                "facet": facet,
                "pinned_answers": _answer_set(
                    raw_query.get("pinned_answers"),
                    f"query {qid} pinned_answers",
                    k=thresholds.k,
                    may_be_empty=False,
                ),
                "baseline_answers": _answer_set(
                    raw_query.get("baseline_answers"),
                    f"query {qid} baseline_answers",
                    k=thresholds.k,
                    may_be_empty=True,
                ),
                "candidate_answers": _answer_set(
                    raw_query.get("candidate_answers"),
                    f"query {qid} candidate_answers",
                    k=thresholds.k,
                    may_be_empty=True,
                ),
            }
        )
    return {
        **bundle,
        "covered_facets": covered_facets,
        "queries": queries,
    }


def _jaccard(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 1.0


def _not_run(rows: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    return {
        "state": NOT_RUN,
        "query_ids": sorted(row["id"] for row in rows),
        "reason": reason,
    }


def _stability(
    rows: list[dict[str, Any]], thresholds: Thresholds
) -> dict[str, Any]:
    if not rows:
        return _not_run(rows, "no covered queries in this reading")
    scores = {
        row["id"]: _jaccard(row["baseline_answers"], row["candidate_answers"])
        for row in rows
    }
    mean = sum(scores.values()) / len(scores)
    below_count = sum(score < thresholds.below_cutoff for score in scores.values())
    below_fraction = below_count / len(scores)
    minimum = min(scores.values())
    failed_rules = []
    if mean < thresholds.mean_min:
        failed_rules.append("mean-jaccard")
    if below_fraction > thresholds.below_max_fraction:
        failed_rules.append("below-cutoff-fraction")
    if minimum < thresholds.hard_floor:
        failed_rules.append("hard-floor")
    return {
        "state": FAIL if failed_rules else PASS,
        "query_count": len(scores),
        "mean_jaccard": mean,
        "below_cutoff_count": below_count,
        "below_cutoff_fraction": below_fraction,
        "minimum_jaccard": minimum,
        "per_query": dict(sorted(scores.items())),
        "failed_rules": failed_rules,
    }


def _r34(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _not_run(rows, "no covered queries in this reading")
    missing = {
        row["id"]: sorted(set(row["pinned_answers"]) - set(row["candidate_answers"]))
        for row in rows
    }
    missing = {qid: answers for qid, answers in missing.items() if answers}
    return {
        "state": FAIL if missing else PASS,
        "query_count": len(rows),
        "missing": dict(sorted(missing.items())),
    }


def _readings(
    rows: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    facets: list[str],
    covered_facets: set[str],
    scorer: Any,
) -> dict[str, Any]:
    readings = {
        "overall": scorer(rows),
        **{
            slice_: scorer([row for row in rows if row["slice"] == slice_])
            for slice_ in SLICES
        },
        "facets": {},
    }
    for facet in facets:
        facet_rows = [row for row in all_rows if row["facet"] == facet]
        if facet not in covered_facets:
            readings["facets"][facet] = _not_run(
                facet_rows, "facet is not covered by this corpus export"
            )
        else:
            readings["facets"][facet] = scorer(facet_rows)
    return readings


def evaluate(bundle: Any, thresholds: Thresholds) -> dict[str, Any]:
    """Return separate stability and absolute-answer readings."""

    checked = _validate(bundle, thresholds)
    all_rows = checked["queries"]
    covered_facets = set(checked["covered_facets"])
    rows = [row for row in all_rows if row["facet"] in covered_facets]
    facets = sorted({row["facet"] for row in all_rows})
    evaluated_facets = sorted({row["facet"] for row in rows})
    unevaluated_facets = sorted(set(facets) - set(evaluated_facets))

    stability = _readings(
        rows,
        all_rows,
        facets,
        covered_facets,
        lambda selected: _stability(selected, thresholds),
    )
    r34 = _readings(rows, all_rows, facets, covered_facets, _r34)
    required = [
        reading[name]
        for reading in (stability, r34)
        for name in ("overall", *SLICES)
    ]
    if any(result["state"] == FAIL for result in required):
        state = FAIL
    elif any(result["state"] == NOT_RUN for result in required):
        state = NOT_RUN
    else:
        state = PASS
    return {
        "schema": REPORT_SCHEMA,
        "state": state,
        "threshold_source": thresholds.source,
        "corpus_revision": checked["corpus_revision"],
        "baseline_revision": checked["baseline_revision"],
        "candidate_revision": checked["candidate_revision"],
        "granularity": checked["granularity"],
        "query_count": len(all_rows),
        "evaluated_query_count": len(rows),
        "evaluated_facets": evaluated_facets,
        "unevaluated_facets": unevaluated_facets,
        "readings": {"stability": stability, "r34": r34},
    }


def _write_report(report: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "SPEC.md",
    )
    args = parser.parse_args(argv)

    try:
        thresholds = load_thresholds(args.spec)
        if not args.input.is_file():
            _write_report(
                {
                    "schema": REPORT_SCHEMA,
                    "state": NOT_RUN,
                    "threshold_source": thresholds.source,
                    "reason": f"input export {args.input} does not exist",
                },
                args.output,
            )
            return 3
        try:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputError(f"cannot read input export {args.input}: {exc}") from exc
        report = evaluate(payload, thresholds)
    except InputError as exc:
        _write_report(
            {"schema": REPORT_SCHEMA, "state": FAIL, "reason": str(exc)},
            args.output,
        )
        return 2

    _write_report(report, args.output)
    return {PASS: 0, FAIL: 1, NOT_RUN: 3}[report["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
