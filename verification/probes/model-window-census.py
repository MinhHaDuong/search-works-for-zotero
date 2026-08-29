#!/usr/bin/env python3
"""Read the declared context window of every embedder 0240 is choosing between.

Ticket 0140 ratifies a chunk budget of `min(500, modelMax) - specialTokens - prefix`.
The 500 is worth its irregularity only if it is below every candidate's window, because
that is what stops the `min` from binding and therefore what keeps the chunk key stable
across a model swap. That premise was asserted from 0240's candidate list and never
measured; this measures it.

The window is not one number. A single model declares up to four fields and they
disagree: nomic-embed-text-v1.5 carries `max_position_embeddings` 2048, `n_positions`
8192, `max_trained_positions` 2048 and `model_max_length` 8192 — a 4x spread, where the
larger figures are RoPE extrapolation past what was trained. So a construction that reads
"the model's limit" has to say which field it reads, and the answer changes the budget.
The minimum over all declared fields is the only reading that cannot over-feed, and it is
what this reports as `window`.

Usage:
    python3 verification/probes/model-window-census.py
    python3 verification/probes/model-window-census.py --output path/to/census.json
"""
import argparse
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("windows")

REPO = Path(__file__).resolve().parent.parent.parent

#: 0240's candidate set, plus the model zoteus loads today (all-MiniLM-L6-v2).
#: Read from ticket 0240's body; a model added there belongs here too.
CANDIDATES = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "intfloat/multilingual-e5-small",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "BAAI/bge-small-en-v1.5",
    "BAAI/bge-m3",
    "nomic-ai/nomic-embed-text-v1.5",
    "nomic-ai/nomic-embed-text-v2-moe",
    "jinaai/jina-embeddings-v3",
    "Qwen/Qwen3-Embedding-0.6B",
]

#: Every field seen declaring a position limit, across the nine candidates. A model
#: declares some subset; the effective window is the minimum of those it declares,
#: because a caller reading any single field can be handed a larger number than the
#: model was trained on.
WINDOW_FIELDS = (
    "max_position_embeddings",
    "n_positions",
    "max_trained_positions",
    "model_max_length",
)

FILES = ("config.json", "tokenizer_config.json")


def fetch(model: str, filename: str, timeout: int) -> dict:
    """One config file, or an empty dict when the model does not publish it."""
    url = f"https://huggingface.co/{model}/raw/main/{filename}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        log.warning("  %s: %s", filename, exc)
        return {}


def declared_fields(model: str, timeout: int) -> dict[str, int]:
    """Every position-limit field this model declares, across both config files."""
    found: dict[str, int] = {}
    for filename in FILES:
        document = fetch(model, filename, timeout)
        for field in WINDOW_FIELDS:
            value = document.get(field)
            # A sentinel like 1e30 means "unbounded" in tokenizer_config, not a window.
            if isinstance(value, int) and 0 < value < 10**6:
                found[field] = value
    return found


def census(models: list[str], timeout: int) -> dict:
    rows = {}
    for model in models:
        fields = declared_fields(model, timeout)
        window = min(fields.values()) if fields else None
        rows[model] = {"declared": fields, "window": window}
        log.info("%-60s window=%s  %s", model, window, fields)
    windows = [row["window"] for row in rows.values() if row["window"] is not None]
    return {
        "probe": "verification/probes/model-window-census.py",
        "source": "huggingface.co/<model>/raw/main/{config,tokenizer_config}.json",
        "reading": "window = min over every position-limit field the model declares",
        "candidates": len(rows),
        "resolved": len(windows),
        "min_window": min(windows) if windows else None,
        "ratified_ceiling": 500,
        "models": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "bench/results/0140-model-windows/candidate-windows.json",
        help="where to write the census JSON",
    )
    parser.add_argument("--timeout", type=int, default=15, help="per-request seconds")
    args = parser.parse_args()

    result = census(CANDIDATES, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    log.info("")
    log.info(
        "%d of %d resolved; tightest window %s against a ceiling of %s",
        result["resolved"],
        result["candidates"],
        result["min_window"],
        result["ratified_ceiling"],
    )
    log.info("wrote %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
