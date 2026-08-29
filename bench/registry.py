"""Read the model registry from Python. The JS side is `bench/registry.mjs`.

Two repositories per record, and the difference matters. `hf_repo` is what the ONNX
runtime loads — usually a mirror, because the mirror is what publishes the filenames
the dtype knob can address. `upstream_repo` is the author's own repository, which is
what a PyTorch/sentence-transformers loader wants and where the card, the licence and
the language list live. A driver that resolves the wrong one silently benchmarks a
different artifact.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("registry")

REGISTRY_PATH = Path(__file__).resolve().parent / "models.json"


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_model(token: str, registry: dict | None = None, kind: str = "onnx") -> dict:
    """Resolve a registry id to `{id, repo, template, record}`.

    Anything containing a slash is taken as a literal repository id and passed through
    with a warning: an ad-hoc run stays possible, but its result has no record saying
    what was measured.
    """
    registry = registry if registry is not None else load_registry()
    for record in registry["models"]:
        if record["id"] == token:
            repo = record["upstream_repo"] if kind == "upstream" else record["hf_repo"]
            return {
                "id": record["id"],
                "repo": repo,
                "template": record["input_template"],
                "record": record,
            }
    if "/" in token:
        logger.warning(
            "%s is not declared in %s; the run is undeclared. Add a record rather than "
            "passing a repository id.",
            token,
            REGISTRY_PATH.name,
        )
        return {"id": token, "repo": token, "template": {"query": "", "passage": ""}, "record": None}
    known = ", ".join(record["id"] for record in registry["models"])
    raise KeyError(f"unknown model {token}. Declared ids: {known}")


def candidate_ids(registry: dict | None = None) -> list[str]:
    """Every registry id whose record is a live candidate."""
    registry = registry if registry is not None else load_registry()
    return [record["id"] for record in registry["models"] if record["status"] == "candidate"]
