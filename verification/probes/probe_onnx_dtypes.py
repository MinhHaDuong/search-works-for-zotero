"""Probe HuggingFace repos for the ONNX filenames transformers.js can address.

A model is only sweepable if its repo publishes files named the way
`DEFAULT_DTYPE_SUFFIX_MAPPING` (`@huggingface/transformers`, `src/utils/dtypes.js`)
resolves them: `model.onnx`, `model_fp16.onnx`, `model_quantized.onnx`, and so on.
This script asks the authenticated repo-metadata endpoint for the file listing and
reports, per repo, which of those names exist.

It records three outcomes and never collapses them:

  available        the listing was read and at least one addressable ONNX file is in it
  confirmed_absent the listing was read and no addressable ONNX file is in it
  could_not_look   the listing was NOT read (401, 403/gated, 404, network, timeout)

The distinction is the whole point: the tracker's first pass ran unauthenticated,
read several 401s, and one of them was a repo that publishes the full dtype set.

Controls are part of the output, not a separate manual step. `--controls` probes a
repo known to publish ONNX and a repo id known not to exist, so the artifact carries
the evidence that a `confirmed_absent` in it is a finding rather than a blind probe.

Usage:

    python3 verification/probes/probe_onnx_dtypes.py --registry bench/models.json \\
        --output bench/results/0261-onnx-registry/probe.json
    python3 verification/probes/probe_onnx_dtypes.py --repo owner/name --repo other/name
    python3 verification/probes/probe_onnx_dtypes.py --search jina-embeddings-v2
"""

import argparse
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("probe_onnx_dtypes")

API = "https://huggingface.co/api"
DEFAULT_KEYFILE = Path.home() / ".config/keys/huggingface.env"

#: `DEFAULT_DTYPE_SUFFIX_MAPPING`, read from @huggingface/transformers 4.2.0
#: (`src/utils/dtypes.js`). The empty suffix is fp32. Kept in this order so the
#: emitted record reads from most to least precise.
DTYPE_SUFFIXES = {
    "fp32": "",
    "fp16": "_fp16",
    "int8": "_int8",
    "uint8": "_uint8",
    "q8": "_quantized",
    "q4": "_q4",
    "q2": "_q2",
    "q1": "_q1",
    "q4f16": "_q4f16",
    "q2f16": "_q2f16",
    "q1f16": "_q1f16",
    "bnb4": "_bnb4",
}

#: A repo that publishes the conventional set, and an id that cannot exist. Probing
#: both makes the artifact self-validating: if the first does not come back
#: `available`, every `confirmed_absent` beside it is untrustworthy.
CONTROL_POSITIVE = "onnx-community/granite-embedding-97m-multilingual-r2-ONNX"
CONTROL_NEGATIVE = "search-works-for-zotero/no-such-repo-negative-control"


def read_token(keyfile: Path) -> str | None:
    """Return HF_TOKEN from the environment, else from a shell-style env file."""
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    if not keyfile.is_file():
        return None
    for line in keyfile.read_text(encoding="utf-8").splitlines():
        match = re.match(r"""\s*(?:export\s+)?HF_TOKEN\s*=\s*["']?([^"'\s]+)""", line)
        if match:
            return match.group(1)
    return None


def fetch(url: str, token: str | None, timeout: int = 30) -> tuple[int, object, str]:
    """GET a JSON endpoint. Returns (status, parsed-or-None, error-detail)."""
    headers = {"User-Agent": "search-works-for-zotero/0261"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response), ""
    except urllib.error.HTTPError as error:
        body = error.read(2000).decode("utf-8", "replace")
        return error.code, None, body.strip()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, None, f"{type(error).__name__}: {error}"


def classify_dtypes(onnx_files: list[str]) -> dict[str, list[str]]:
    """Map each addressable dtype to the file paths that satisfy it.

    transformers.js builds `<subfolder>/<file_name><suffix>.onnx`, so match on the
    basename and report every directory that carries it — a repo may publish both a
    root-level and an `onnx/` copy.
    """
    found: dict[str, list[str]] = {}
    for dtype, suffix in DTYPE_SUFFIXES.items():
        wanted = f"model{suffix}.onnx"
        hits = [path for path in onnx_files if path.rsplit("/", 1)[-1] == wanted]
        if hits:
            found[dtype] = sorted(hits)
    return found


def fetch_config(repo: str, token: str | None) -> dict:
    """Read `config.json` for the shape the model actually declares.

    Dimension and sequence length copied from a card or a summary table drift; these
    come from the file the runtime itself loads.
    """
    base = f"https://huggingface.co/{repo}/raw/main"
    status, payload, _ = fetch(f"{base}/config.json", token)
    if status != 200 or not isinstance(payload, dict):
        return {}
    config = {
        # DistilBERT names the embedding width `dim`; every other family uses
        # `hidden_size`. Reading only one of them silently returns null for a model
        # that declares the other.
        "hidden_size": payload.get("hidden_size", payload.get("dim")),
        "max_position_embeddings": payload.get("max_position_embeddings"),
        "model_type": payload.get("model_type"),
        "vocab_size": payload.get("vocab_size"),
    }
    # `max_position_embeddings` is the architecture's capacity; sentence-transformers
    # declares separately, in its own file, the length it actually truncates to. They
    # are different numbers and the second is the one a retrieval run lives under.
    status, st_config, _ = fetch(f"{base}/sentence_bert_config.json", token)
    if status == 200 and isinstance(st_config, dict):
        config["st_max_seq_length"] = st_config.get("max_seq_length")
    return config


def probe_repo(repo: str, token: str | None) -> dict:
    """Query one repo's metadata and classify the outcome into one of three states."""
    url = f"{API}/models/{urllib.parse.quote(repo, safe='/')}"
    status, payload, detail = fetch(url, token)
    record: dict = {"repo": repo, "http_status": status}

    if status != 200 or not isinstance(payload, dict):
        record["state"] = "could_not_look"
        record["reason"] = detail[:300] or f"HTTP {status}"
        record["onnx_files"] = None
        record["dtypes"] = None
        logger.warning("%s: could not look (HTTP %s)", repo, status)
        return record

    siblings = [
        entry.get("rfilename", "")
        for entry in payload.get("siblings", [])
        if isinstance(entry, dict)
    ]
    onnx_files = sorted(name for name in siblings if name.endswith(".onnx"))
    dtypes = classify_dtypes(onnx_files)

    card = payload.get("cardData") or {}
    record["gated"] = payload.get("gated", False)
    record["private"] = payload.get("private", False)
    record["licence"] = card.get("license")
    languages = card.get("language")
    if isinstance(languages, str):
        languages = [languages]
    record["declared_languages"] = languages
    record["parameters"] = (payload.get("safetensors") or {}).get("total")
    record["last_modified"] = payload.get("lastModified")
    record["config"] = fetch_config(repo, token)
    record["onnx_files"] = onnx_files
    record["dtypes"] = {dtype: paths for dtype, paths in dtypes.items()}
    record["state"] = "available" if dtypes else "confirmed_absent"
    record["reason"] = (
        ""
        if dtypes
        else (
            "listing read; no file named model<suffix>.onnx for any suffix in "
            "DEFAULT_DTYPE_SUFFIX_MAPPING"
            + (f" ({len(onnx_files)} other .onnx files present)" if onnx_files else "")
        )
    )
    logger.info("%s: %s (%d dtypes)", repo, record["state"], len(dtypes))
    return record


def search_models(query: str, token: str | None, limit: int = 50) -> list[dict]:
    """List repo ids matching a search string — for resolving a suspect repo id."""
    url = f"{API}/models?search={urllib.parse.quote(query)}&limit={limit}"
    status, payload, detail = fetch(url, token)
    if status != 200 or not isinstance(payload, list):
        logger.error("search failed: HTTP %s %s", status, detail[:200])
        return []
    return [{"id": item.get("id"), "gated": item.get("gated")} for item in payload]


def repos_from_registry(path: Path) -> list[str]:
    """Every `hf_repo` declared in the registry, in declaration order."""
    registry = json.loads(path.read_text(encoding="utf-8"))
    return [record["hf_repo"] for record in registry["models"]]


def update_registry(path: Path, results: list[dict], probed_utc: str) -> int:
    """Rewrite each record's `availability` block from this run. Returns records hit.

    Availability is the one part of a record that is observed rather than declared,
    so it is refreshed mechanically. Everything else — the rejection reason, the
    input template, the licence a mirror does not restate — stays hand-maintained,
    which is the point of a declared registry.
    """
    registry = json.loads(path.read_text(encoding="utf-8"))
    by_repo = {record["repo"]: record for record in results}
    touched = 0
    for record in registry["models"]:
        probe = by_repo.get(record["hf_repo"])
        if probe is None:
            continue
        record["availability"] = {
            "state": probe["state"],
            "http_status": probe["http_status"],
            "probed_utc": probed_utc,
            "dtypes": probe.get("dtypes") or {},
            "onnx_files": probe.get("onnx_files"),
            "reason": probe.get("reason", ""),
        }
        touched += 1
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return touched


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path, help="probe every hf_repo declared here")
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="rewrite each --registry record's availability block from this run",
    )
    parser.add_argument("--repo", action="append", default=[], help="repeatable repo id")
    parser.add_argument("--repo-file", type=Path, help="one repo id per line")
    parser.add_argument("--search", help="list repo ids matching this string, then exit")
    parser.add_argument("--output", type=Path, help="write the JSON artifact here")
    parser.add_argument(
        "--controls",
        action="store_true",
        default=True,
        help="also probe the positive and negative controls (default: on)",
    )
    parser.add_argument("--no-controls", dest="controls", action="store_false")
    parser.add_argument("--keyfile", type=Path, default=DEFAULT_KEYFILE)
    parser.add_argument("--sleep", type=float, default=0.3, help="seconds between calls")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    token = read_token(args.keyfile)
    if token is None:
        logger.warning("no HF_TOKEN: every gated repo will read as could_not_look")

    if args.search:
        for hit in search_models(args.search, token):
            print(f"{hit['id']}\tgated={hit['gated']}")
        return

    repos = list(args.repo)
    if args.repo_file:
        repos += [
            line.strip()
            for line in args.repo_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    if args.registry:
        repos += repos_from_registry(args.registry)
    if not repos:
        raise SystemExit("nothing to probe: pass --registry, --repo or --repo-file")

    controls = {}
    if args.controls:
        for name, repo in (("positive", CONTROL_POSITIVE), ("negative", CONTROL_NEGATIVE)):
            controls[name] = probe_repo(repo, token)
            time.sleep(args.sleep)

    seen: set[str] = set()
    results = []
    for repo in repos:
        if repo in seen:
            continue
        seen.add(repo)
        results.append(probe_repo(repo, token))
        time.sleep(args.sleep)

    artifact = {
        "probe": "onnx dtype availability, authenticated repo metadata",
        "ticket": "0261",
        "endpoint": f"{API}/models/<repo>",
        "authenticated": token is not None,
        "probed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "dtype_suffix_mapping": DTYPE_SUFFIXES,
        "dtype_suffix_source": "@huggingface/transformers 4.2.0 src/utils/dtypes.js",
        "controls": controls,
        "results": results,
    }
    if args.update_registry:
        if not args.registry:
            raise SystemExit("--update-registry needs --registry")
        touched = update_registry(args.registry, results, artifact["probed_utc"])
        logger.info("refreshed %d availability blocks in %s", touched, args.registry)

    text = json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        logger.info("wrote %s", args.output)
    else:
        print(text)


if __name__ == "__main__":
    main()
