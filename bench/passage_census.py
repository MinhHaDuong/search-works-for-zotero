"""Counting pass of the §5.2.9 passage census (ticket 0140).

Consumes the JSONL that bench/passage_census.mjs measured with the embedder's
own tokenizer, applies the ratified geometry (bench/geometry.py — the one
implementation the fast tests cover), and writes the summary artifact §5.2.9
quotes: passages in total, per attachment kind, and the median per attachment
that derives band cap K.

Stated approximation: entries come from seg/1, which does not exist yet
(ticket 0028 builds to this geometry), so the census chunks each cache file as
one continuous paragraph sequence. Synthetic entry boundaries would only add
chunk closures, so the census errs low by that margin and the artifact says so.

    python3 bench/passage_census.py --paragraphs <paragraphs.jsonl> \
        --output bench/results/0140-passage-census/census.json
"""
import argparse
import json
import logging
import statistics
from pathlib import Path

import geometry

CENSUS_WINDOWS = Path(__file__).parent / "results" / "0140-model-windows" / "candidate-windows.json"

KINDS = ("pdf", "html", "other")


def summarize(rows: list[dict], budget: int) -> dict:
    per_kind = {k: {"files": 0, "paragraphs": 0, "tokens": 0, "passages": 0} for k in KINDS}
    per_file_passages = {k: [] for k in KINDS}
    for row in rows:
        kind = row["kind"]
        paragraphs = row["paragraphs"]
        passages = geometry.chunk_count(paragraphs, budget)
        bucket = per_kind[kind]
        bucket["files"] += 1
        bucket["paragraphs"] += len(paragraphs)
        bucket["tokens"] += sum(paragraphs)
        bucket["passages"] += passages
        per_file_passages[kind].append(passages)
    for kind in KINDS:
        counts = per_file_passages[kind]
        per_kind[kind]["median_passages_per_attachment"] = (
            statistics.median(counts) if counts else None
        )
    every = [c for kind in KINDS for c in per_file_passages[kind]]
    return {
        "budget": budget,
        "files": len(rows),
        "passages_total": sum(per_kind[k]["passages"] for k in KINDS),
        "tokens_total": sum(per_kind[k]["tokens"] for k in KINDS),
        "median_passages_per_attachment": statistics.median(every) if every else None,
        "by_kind": per_kind,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paragraphs", type=Path, required=True,
                        help="JSONL from bench/passage_census.mjs")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--windows", type=Path, default=CENSUS_WINDOWS,
                        help="window census the budget is resolved against")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    lines = args.paragraphs.read_text().splitlines()
    header = json.loads(lines[0])
    assert header.get("meta"), "first JSONL row must be the tokenization pass's meta header"
    rows = [json.loads(line) for line in lines[1:]]

    window = json.loads(args.windows.read_text())["min_window"]
    # The incumbent's passage prefix is empty (bench/models.json); a model with
    # an instruction prefix re-runs the tokenization pass, which records it.
    budget = geometry.resolve_budget(window, header["special_tokens"], 0)

    artifact = {
        "ticket": "tickets/0140-cap-the-chunker-below-the-embedder-limit.erg",
        "probe": ["bench/passage_census.mjs", "bench/passage_census.py"],
        "tokenization": {k: header[k] for k in
                         ("run_utc", "model", "special_tokens", "population", "sampled", "seed")},
        "geometry": {"budget": budget, "window": window,
                     "min_tokens": geometry.MIN_TOKENS, "overlap_tokens": geometry.OVERLAP_TOKENS},
        "approximation": "entry = one cache file (seg/1 not built yet); synthetic entry "
                         "boundaries would only add closures, so passage counts err low",
        "summary": summarize(rows, budget),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    logging.info(json.dumps(artifact["summary"], indent=2))


if __name__ == "__main__":
    main()
