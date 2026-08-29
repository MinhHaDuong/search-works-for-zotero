"""Probe each candidate's own repo for the pooling mode it was trained with.

Pooling is the second half of the trap `input_template` closed. A driver that
reads the prefixes from the registry and then hardcodes `pooling: 'mean'` gets one
axis right and the other wrong, and wrong pooling degrades retrieval *silently* --
it reads as the model being worse, not as a bug. A sweep can therefore reject a
good candidate on it and record a confident wrong number.

Where the value lives: sentence-transformers writes `1_Pooling/config.json` with
one `pooling_mode_*` flag set true, and lists the modules in `modules.json`. Both
are read here. The ONNX mirrors do NOT carry either file -- `Xenova/*` and
`onnx-community/*` publish the graph and nothing else -- so the probe reads the
`upstream_repo` field, which is exactly why the registry carries it.

Four outcomes, never collapsed:

  read             the pooling config was fetched and names exactly one mode
  ambiguous        it was fetched and names zero modes, or several
  confirmed_absent the repo was reached and publishes no pooling config
  could_not_look   the repo was NOT reached (401, gated, 404, network, timeout)

A model whose config names zero modes, or more than one, is reported as ambiguous
rather than resolved to a guess. Guessing is how the prefix trap nearly landed,
and a wrong pooling value is not visible downstream.

Controls are enforced, not merely recorded. `--controls` probes a repo whose
pooling is attested independently of this probe (multilingual-e5-small is `mean`
in Zotero core's own registry) and a repo id known not to exist; if either comes
back wrong the script refuses to write the artifact, because a probe that misreads
an attested value makes every value beside it untrustworthy.

Usage:

    python3 verification/probes/probe_pooling.py --registry bench/models.json \\
        --output bench/results/0421-pooling/pooling.json
    python3 verification/probes/probe_pooling.py --registry bench/models.json \\
        --output bench/results/0421-pooling/pooling.json --update-registry
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

DEFAULT_KEYFILE = Path.home() / ".config/keys/huggingface.env"

#: sentence-transformers flag -> the literal string transformers.js accepts for it.
#:
#: The right-hand side is not a label of our own choosing: it is matched against the
#: `switch` in `@huggingface/transformers/src/pipelines/feature-extraction.js`, whose
#: cases are `mean`, `first_token`/`cls`, `last_token`/`eos`, and whose `default:`
#: throws. So a value here that reads well but is not one of those literals produces a
#: run-time throw that looks like a library limitation. The first draft wrote
#: `lasttoken` and drew exactly that wrong conclusion about Qwen3.
#:
#: The modes with no case in that switch are recorded as themselves and left for a
#: human — a mode the library genuinely cannot express is a finding about the
#: candidate, not a value to coerce into one it can.
POOLING_FLAGS = {
    "pooling_mode_cls_token": "cls",
    "pooling_mode_mean_tokens": "mean",
    "pooling_mode_lasttoken": "last_token",
    "pooling_mode_max_tokens": "max",
    "pooling_mode_mean_sqrt_len_tokens": "mean_sqrt_len",
    "pooling_mode_weightedmean_tokens": "weightedmean",
}

POOLING_CONFIG = "1_Pooling/config.json"
MODULES = "modules.json"

#: Attested independently of this probe: Zotero core's own registry
#: (zotero/zotero#6012, chrome/content/zotero/xpcom/embeddings.js) records `mean`
#: for the e5 family.
CONTROL_POSITIVE = "intfloat/multilingual-e5-small"
CONTROL_POSITIVE_EXPECTED = "mean"
CONTROL_NEGATIVE = "search-works-for-zotero/no-such-repo-negative-control"

logger = logging.getLogger("probe_pooling")


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


def fetch_file(repo: str, path: str, token: str | None, timeout: int = 30):
    """GET one file from a repo. Returns (status, parsed-or-None, error-detail)."""
    url = f"https://huggingface.co/{urllib.parse.quote(repo, safe='/')}/resolve/main/{path}"
    headers = {"User-Agent": "search-works-for-zotero/0421"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response), ""
    except urllib.error.HTTPError as error:
        body = error.read(2000).decode("utf-8", "replace")
        return error.code, None, body.strip()
    except json.JSONDecodeError as error:
        return 200, None, f"not JSON: {error}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, None, f"{type(error).__name__}: {error}"


def repo_exists(repo: str, token: str | None, timeout: int = 30) -> bool:
    """Is the repo itself readable? Distinguishes 'no such file' from 'no such repo'."""
    url = f"https://huggingface.co/api/models/{urllib.parse.quote(repo, safe='/')}"
    headers = {"User-Agent": "search-works-for-zotero/0421"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def modes_from_config(config: dict) -> list[str]:
    """Every pooling mode the config sets true, in a stable order."""
    return [name for flag, name in sorted(POOLING_FLAGS.items()) if config.get(flag) is True]


def probe_repo(repo: str, token: str | None) -> dict:
    """One repo's pooling, with the evidence that produced it."""
    record: dict = {
        "repo": repo,
        "state": "could_not_look",
        "pooling": None,
        "http_status": None,
        "normalize": None,
        "modes_set": [],
        "detail": "",
    }
    status, config, detail = fetch_file(repo, POOLING_CONFIG, token)
    record["http_status"] = status
    if status == 404:
        # A 404 on the file cannot tell these apart on its own, and they are the two
        # states this study exists to keep separate: a repo that publishes no pooling
        # config, and a repo that is not there at all. Both answer 404. So ask the
        # metadata endpoint whether the repo itself is readable before deciding.
        # The negative control caught this collapsing the two on the first run.
        if repo_exists(repo, token):
            record["state"] = "confirmed_absent"
            record["detail"] = f"repo reads; {POOLING_CONFIG} is not published by it"
        else:
            record["state"] = "could_not_look"
            record["detail"] = f"repo itself is not readable (404 on {POOLING_CONFIG} and on metadata)"
        return record
    if status != 200 or not isinstance(config, dict):
        record["detail"] = detail or f"HTTP {status}"
        return record

    modes = modes_from_config(config)
    record["modes_set"] = modes
    if len(modes) == 1:
        record["state"] = "read"
        record["pooling"] = modes[0]
    else:
        record["state"] = "ambiguous"
        record["detail"] = f"{len(modes)} pooling modes set: {modes or 'none'}"

    status_m, modules, _ = fetch_file(repo, MODULES, token)
    if status_m == 200 and isinstance(modules, list):
        record["normalize"] = any(
            "Normalize" in str(module.get("type", "")) for module in modules
        )
    return record


def targets_from_registry(path: Path, candidates_only: bool = False) -> list[tuple[str, str]]:
    """(id, upstream_repo) per record. The ONNX mirrors carry no pooling config.

    Every record by default, not only the candidates. A rejected model is still
    driven as a contrast arm — `all-minilm-l6-v2` is the English baseline several
    drivers resolve — and a contrast arm measured with the wrong pooling corrupts
    the comparison exactly as a candidate would.
    """
    registry = json.loads(path.read_text(encoding="utf-8"))
    models = registry.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError(f"{path}: no 'models' list to read")
    return [
        (m["id"], m["upstream_repo"])
        for m in models
        if not candidates_only or m.get("status") == "candidate"
    ]


def update_registry(path: Path, by_id: dict[str, dict], probed_utc: str) -> int:
    """Write pooling + pooling_source onto each candidate record. Returns count."""
    registry = json.loads(path.read_text(encoding="utf-8"))
    written = 0
    for model in registry.get("models", []):
        result = by_id.get(model["id"])
        if result is None:
            continue
        model["pooling"] = result["pooling"]
        if result["pooling"] is not None:
            source = (
                f"{POOLING_CONFIG} on {result['repo']} (read {probed_utc}); "
                f"the ONNX mirror publishes no pooling config"
            )
        else:
            source = f"{result['state']}: {result['detail']} ({result['repo']}, {probed_utc})"
        model["pooling_source"] = source
        written += 1
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path, help="probe every record declared here")
    parser.add_argument("--repo", action="append", default=[], help="repeatable repo id")
    parser.add_argument("--output", type=Path, help="write the JSON artifact here")
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="write pooling + pooling_source back onto the registry's candidate records",
    )
    parser.add_argument(
        "--candidates-only",
        action="store_true",
        help="skip rejected records; they are still driven as contrast arms, so this is rarely right",
    )
    parser.add_argument("--no-controls", dest="controls", action="store_false")
    parser.add_argument("--keyfile", type=Path, default=DEFAULT_KEYFILE)
    parser.add_argument("--sleep", type=float, default=0.3, help="seconds between calls")
    parser.set_defaults(controls=True)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    token = read_token(args.keyfile)
    if token is None:
        logger.warning("no HF_TOKEN; gated repos will read as could_not_look")

    targets: list[tuple[str, str]] = []
    if args.registry:
        targets.extend(targets_from_registry(args.registry, args.candidates_only))
    targets.extend((repo, repo) for repo in args.repo)
    if not targets:
        raise SystemExit("nothing to probe: pass --registry or --repo")

    probed_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    results = []
    by_id = {}
    for model_id, repo in targets:
        record = probe_repo(repo, token)
        record["id"] = model_id
        results.append(record)
        by_id[model_id] = record
        logger.info("%s (%s): %s %s", model_id, repo, record["state"], record["pooling"])
        time.sleep(args.sleep)

    controls = {}
    if args.controls:
        positive = probe_repo(CONTROL_POSITIVE, token)
        time.sleep(args.sleep)
        negative = probe_repo(CONTROL_NEGATIVE, token)
        positive["expected"] = CONTROL_POSITIVE_EXPECTED
        controls = {"positive": positive, "negative": negative}
        if positive["pooling"] != CONTROL_POSITIVE_EXPECTED:
            raise SystemExit(
                f"positive control failed: {CONTROL_POSITIVE} read as "
                f"{positive['pooling']!r}, expected {CONTROL_POSITIVE_EXPECTED!r}. "
                f"Refusing to write an artifact whose controls did not hold."
            )
        if negative["state"] != "could_not_look":
            raise SystemExit(
                f"negative control failed: {CONTROL_NEGATIVE} read as "
                f"{negative['state']!r}, expected could_not_look."
            )

    artifact = {
        "probed_utc": probed_utc,
        "authenticated": token is not None,
        "source_file": POOLING_CONFIG,
        "controls": controls,
        "results": results,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        logger.info("wrote %s", args.output)
    else:
        print(json.dumps(artifact, indent=2, ensure_ascii=False))

    if args.update_registry:
        if not args.registry:
            raise SystemExit("--update-registry needs --registry")
        count = update_registry(args.registry, by_id, probed_utc)
        logger.info("wrote pooling onto %d record(s) in %s", count, args.registry)


if __name__ == "__main__":
    main()
