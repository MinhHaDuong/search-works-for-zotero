#!/usr/bin/env python3
"""The library-level bench, end to end: a random item scope, its index, sample, ask, score.

    python3 -m bench.generator.run --entrypoint fork/dist/index.js --arena ~/data/generator-0719/arena \\
        --transformers-path <dir> --zotero-data-dir ~/data/Zotero --scope-items 300 \\
        --census bench/results/0029-library-census/census.json --n 100 --seed 1 \\
        --writer llama-server --endpoint http://127.0.0.1:18080 --endpoint-note "ssh tunnel to padme" \\
        --fallback-model <hub id of an instruct model, ONNX weights> --cache-dir ~/data/cache/transformersjs \\
        --work-dir ~/data/generator-0719/work --output bench/results/0719-generator/run.json

**Scope** (ruled 2026-09-06): a seeded random sample of `--scope-items` top-level
records. The target cannot take a list of keys, so the harness stands a read-only
proxy in front of Zotero's local API that filters the listings to the sample
(`scope.py`) and points the target at it through its own `ZOTERO_LOCAL_PORT`
setting. The index is built through the target's own tool over that library, the
scope is read back from the index file, and the sampler is restricted to the keys
the index holds.

**Modes.** Every question is asked in each of the interface's three retrieval
modes — `exact`, `meaning`, `combined` — so a lane's result can be read as a mode
effect or a model effect. Which target mode each maps to is read from the
adapter's own table, and what the target says it ran (embedder, active or not,
vectors) is read from its replies, not from documentation. The per-lane tables
use `combined`, the target's default path.

The engine is reached through the acceptance adapter and its `query` verb only;
the one thing done outside the seven verbs is starting the target's own index
build. The output is aggregates only, with the run identity: seed, scope,
library version, Zotero version, target revision, index counters, question
writer and endpoint, modes and their evidence, extraction configuration.
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import socket
import sqlite3
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from bench.acceptance.adapters import zoteus as zoteus_adapter
from bench.generator import questions as Q
from bench.generator import sample as S
from bench.generator import score as SC
from bench.generator.scope import Scope, ScopeProxy
from bench.registry import load_registry

PRIMARY_MODE = "combined"
MODES = ("combined", "exact", "meaning")

#: The two values the target's `embedderIdentity()` leaves OUT of the string it
#: stamps on an index's vectors, so that adding a suffix does not declare every
#: index ever built stale (`embeddings.ts`, DEFAULT_LOCAL_DTYPE and
#: DEFAULT_POOLING). They are the semantic content of that elision: a stamp with
#: no `@` means fp32, one with no `#` means mean. Reproducing them here is not a
#: copy of the target's model tables — it is the inverse of its elision rule,
#: which is what lets this run write the two values out explicitly in exactly
#: the arm where the stamp is silent about them.
STAMP_ELIDED_DTYPE = "fp32"
STAMP_ELIDED_POOLING = "mean"

#: The settings that decide which vectors a local build produces. Read from the
#: operator environment because the adapter merges its own dict OVER `os.environ`
#: and sets none of these four (it sets `ZOTEUS_EMBEDDINGS` only), so what the
#: shell exported is what the target saw.
EMBEDDER_SETTINGS = ("ZOTEUS_EMBEDDINGS", "ZOTEUS_EMBEDDING_MODEL", "ZOTEUS_EMBEDDING_DTYPE",
                     "ZOTEUS_EMBEDDING_POOLING", "ZOTEUS_EMBEDDING_PREFIXES")

#: The registry id whose record carries the E5 template, for the one setting
#: that forces those markers regardless of the model
#: (`ZOTEUS_EMBEDDING_PREFIXES=e5`). A registry id, never a repository and never
#: the prefix strings: one model name, one place, and both the template and the
#: repositories it maps to belong to `bench/models.json`.
E5_TEMPLATE_ID = "multilingual-e5-small"


def index_item_keys(data_dir: Path) -> tuple[Path | None, list[str]]:
    """The item keys a built index holds, read from the index file itself
    (read-only). Identified by its `meta` table, not by name, like the adapter."""
    for candidate in sorted(data_dir.glob("*.sqlite")):
        try:
            con = sqlite3.connect(f"file:{candidate}?mode=ro", uri=True)
            try:
                if not con.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone():
                    continue
                keys = [r[0] for r in con.execute("SELECT item_key FROM items")]
                return candidate, keys
            finally:
                con.close()
        except sqlite3.Error:
            continue
    return None, []


def index_embedder_stamp(index_file: Path | None) -> str | None:
    """The embedder identity the index stamped on its own vectors, read from the
    index file (read-only, `meta.embedderId`).

    This is the load-bearing witness, not the configuration: it is written when
    the vectors are written, so it names what actually produced them even if the
    environment has moved since. An index with no vectors stores the empty
    string, which is absence and is returned as such."""
    if index_file is None or not index_file.is_file():
        return None
    try:
        con = sqlite3.connect(f"file:{index_file}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = con.execute("SELECT value FROM meta WHERE key = 'embedderId'").fetchone()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    return (row[0] or None) if row else None


def expand_embedder_stamp(stamp: str | None) -> dict | None:
    """`provider[:model][@dtype][#pooling]` with its elisions written out.

    The target omits the default dtype and the default pooling from the string
    on purpose, so a default run's stamp is `local:<model>` and says nothing
    about either. Read literally, a run identity built on it would be silent
    about precision and pooling in exactly the arm that needs them named. The
    elision is total ordering, not information loss — absent means default — so
    this expands it, and reports which parts were implicit so a reader can tell
    a value that was in the string from one this function supplied."""
    if not stamp:
        return None
    rest, sep, pooling = stamp.rpartition("#")
    if not sep:
        rest, pooling = stamp, None
    head, sep, dtype = rest.rpartition("@")
    if sep:
        rest = head
    else:
        dtype = None
    provider, sep, model = rest.partition(":")
    return {"stamp": stamp, "provider": provider or None, "model": model if sep and model else None,
            "dtype": dtype or STAMP_ELIDED_DTYPE, "pooling": pooling or STAMP_ELIDED_POOLING,
            "elided": [k for k, v in (("dtype", dtype), ("pooling", pooling)) if not v]}


def weights_digest(models_dir: Path, model: str | None) -> dict:
    """The weight files the target actually loaded, by content.

    `bench/models.json` declares a revision per repository, but the target
    passes none to the pipeline: transformers.js fetches whatever the hub serves
    today and caches it under `<dataDir>/models`, so a run that copied the
    registry's revision into its identity would be recording a declaration as if
    it were a fact about the weights it held. What can be measured is the bytes:
    every file in the model's cache directory, with its size and SHA-256. Two
    runs held the same weights when these agree, which is the question the
    revision was being asked."""
    if not model:
        return {"present": False, "reason": "no model resolved, so no weights directory to look in"}
    root = models_dir / model
    if not root.is_dir():
        return {"present": False, "dir": str(root),
                "reason": "no cache directory for this model under the arena; the weights were served from "
                          "elsewhere or the provider is not the on-device one"}
    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        files.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
                      "sha256": digest.hexdigest()})
    return {"present": True, "dir": str(root), "files": files,
            "bytes": sum(f["bytes"] for f in files)}


def registry_record(model: str | None, registry: dict | None = None) -> dict | None:
    """The `bench/models.json` record for a repository id, or None.

    Matched on the registry id first, then on the repository the runtime loads,
    then on the upstream one: a mirror and its source name the same weights and
    either may reach here, and a registry id never contains a slash, so the two
    namespaces cannot collide. An undeclared repository returns None and is reported as undeclared:
    the registry is the one place a model's template, pooling and revision are
    written down, and a model missing from it is one this run cannot speak for
    rather than one with nothing to say."""
    if not model:
        return None
    reg = registry if registry is not None else load_registry()
    for key in ("id", "hf_repo", "upstream_repo"):
        for record in reg["models"]:
            if record.get(key) == model:
                return record
    return None


def declared_template(record: dict | None) -> dict | None:
    """The input template a record declares, or None when it declares none.

    An all-empty template is the registry's way of saying this model wants no
    markers, which is a declaration; it comes back as None here so a reader is
    not handed two empty strings to interpret."""
    template = (record or {}).get("input_template") or {}
    return dict(template) if any(template.values()) else None


def embedder_identity(status: dict, stamp: str | None, evidence: dict,
                      env: dict[str, str], models_dir: Path) -> dict:
    """Which embedder produced this run's vectors, resolved and written out.

    Exists because `embedder: "local"` — all the run identity carried before —
    is a PROVIDER, and the question a cross-lingual reading turns on is the
    MODEL: an English-centric default and a multilingual substitute are both
    "local" and give opposite meanings to the same near-zero. So the model, its
    precision and its pooling are recorded explicitly, never by omission, and
    each is attributed to where it was read from."""
    expanded = expand_embedder_stamp(stamp)
    status_model = status.get("embedderModel")
    stamp_model = (expanded or {}).get("model")
    model = stamp_model or status_model
    record = registry_record(model)
    prefix_mode = env.get("ZOTEUS_EMBEDDING_PREFIXES") or "auto"
    if prefix_mode == "off":
        prefixes, prefix_note = None, "the setting turns the markers off for every model"
    elif prefix_mode == "e5":
        prefixes = declared_template(registry_record(E5_TEMPLATE_ID))
        prefix_note = f"the setting forces the E5 template, read from the registry record {E5_TEMPLATE_ID}"
    elif record is None:
        prefixes = None
        prefix_note = ("the registry declares no record for this repository, so the template it wants could "
                       "not be resolved: this is unresolved, not `no markers`")
    else:
        prefixes = declared_template(record)
        prefix_note = f"the template `bench/models.json` declares for {record['id']}"
    identity: dict = {
        "provider": status.get("embedder"),
        "configured": status.get("embedderConfigured"),
        "active": status.get("embedderActive"),
        "model": model,
        "model_source": "index stamp" if stamp_model else ("index status" if status_model else None),
        "index_stamp": stamp,
        "status_model": status_model,
        "settings": {k: env.get(k) for k in EMBEDDER_SETTINGS},
        "registry": ({"id": record["id"], "status": record["status"], "upstream_repo": record["upstream_repo"],
                      "pooling": record.get("pooling"), "languages": record.get("languages")}
                     if record else None),
        "prefixes": {
            "setting": prefix_mode,
            "expected": prefixes,
            "expected_from": prefix_note,
            "observed": None,
            "observability": "the target reports no prefix evidence in its status or its replies, so "
                             "`expected` is what the registry declares this model wants and not a "
                             "read-back of what the pipeline was handed",
        },
        "revision": {
            "declared": (record or {}).get("hf_revision"),
            "pinned_at_load": False,
            "note": "the target passes no revision to the pipeline: it loads whatever the hub serves and "
                    "caches it, so `declared` is the registry's record of the repository and the weights "
                    "below are what this run actually held",
            "weights": weights_digest(models_dir, model),
        },
        "query_reply_names_model": any("embedderModel" in e for e in evidence.values()),
    }
    if expanded:
        identity["dtype"] = expanded["dtype"]
        identity["pooling"] = expanded["pooling"]
        identity["resolved_from_stamp_elision"] = expanded["elided"]
    else:
        #: No stamp means no vectors were written, so there is nothing that
        #: witnessed the build. The settings still say what was asked for; the
        #: pooling of an `auto` setting is decided by a table inside the target
        #: and cannot be recovered from outside, and is reported as unmeasured
        #: rather than filled in with the default it may not have.
        identity["dtype"] = env.get("ZOTEUS_EMBEDDING_DTYPE") or STAMP_ELIDED_DTYPE
        setting = env.get("ZOTEUS_EMBEDDING_POOLING") or "auto"
        identity["pooling"] = None if setting == "auto" else setting
        identity["unmeasured"] = ("no index stamp: the index wrote no vectors, so what produced them cannot be "
                                  "read back; `pooling` under an `auto` setting comes from a table inside the "
                                  "target and is not recoverable from outside")
    declared_pooling = (record or {}).get("pooling")
    if record and identity["pooling"] and declared_pooling and identity["pooling"] != declared_pooling:
        #: The stamp is what the vectors were built with; the registry is what
        #: the model was trained for. A disagreement is a silent retrieval loss,
        #: so it is stated rather than left for a reader to notice.
        identity["pooling_disagrees_with_registry"] = (
            f"the vectors were pooled {identity['pooling']} but bench/models.json declares "
            f"{declared_pooling} for {record['id']}")
    if stamp_model and status_model and stamp_model != status_model:
        identity["disagreement"] = (f"the index was built by {stamp_model} but the target now reports "
                                    f"{status_model}: the vectors are the stamp's, not the status's")
    return identity


def index_status(target) -> dict:
    return zoteus_adapter._payload(target.server.call("tools/call", {
        "name": "zotero_index", "arguments": {"action": "status"}}))


def build_index(target, limit: int, timeout_s: float, poll_s: float = 15.0) -> dict:
    """Start the target's own build over the library it sees, body text on, poll
    its status until it settles, and return the cost and the final counters."""
    t0 = time.monotonic()
    started = zoteus_adapter._payload(target.server.call("tools/call", {
        "name": "zotero_index",
        "arguments": {"action": "build", "fulltext": True, "limit": limit, "auto_build": False},
    }))
    logging.info("build started: %s", json.dumps(started)[:300])
    status: dict = {}
    while time.monotonic() - t0 < timeout_s:
        time.sleep(poll_s)
        status = index_status(target)
        state = status.get("state")
        logging.info("build %s phase=%s items=%s/%s passages=%s vectors=%s",
                     state, status.get("phase"), status.get("itemsFetched"), status.get("itemsTotal"),
                     status.get("passages"), status.get("vectors"))
        if state in ("done", "error", "idle"):
            break
    elapsed = time.monotonic() - t0
    # `embedder` is a provider label ("local"); `embedderModel` is the model, and
    # without it a build record cannot say which vector space it produced.
    keep = ("state", "phase", "items", "itemsTotal", "itemsAvailable", "passages", "vectors",
            "fulltextItems", "fulltextPassages", "ownWordsPassages", "embedder", "embedderModel",
            "embedderConfigured", "embedderActive", "embedderReason",
            "libraryVersion", "libraryBackend", "fulltextVersion", "builtFromVersion", "error",
            "passagesWithoutVectors", "localApiDegradedAt")
    return {"limit": limit, "elapsed_s": round(elapsed, 1), "timed_out": elapsed >= timeout_s,
            "status": {k: status.get(k) for k in keep if k in status}}


def mode_evidence(reply: dict) -> dict:
    """What the target's reply says about the path it ran, read off the reply."""
    # `embedderModel` is asked for and, on the reviewed build, never answered: the
    # query reply names the provider only. Kept so a target that grows the field
    # is recorded by it, and `embedder_identity` states in the artifact whether
    # any reply carried it, so its absence reads as absence rather than as silence.
    return {k: reply.get(k) for k in ("embedder", "embedderModel", "embedderConfigured", "embedderActive",
                                       "embedderReason", "vectors", "passagesWithoutVectors",
                                       "fulltextEnabled", "isError")
            if k in reply}


def ask(target, rows: list[dict], top_k: int, modes: tuple[str, ...] = MODES) -> tuple[list[dict], dict]:
    """Every question in every mode. The primary mode's score sits under `score`;
    every mode's under `by_mode`. Returns the readings and, per mode, the target's
    own account of what it ran, taken from the first reply in that mode."""
    readings = []
    evidence: dict[str, dict] = {}
    for i, row in enumerate(rows, 1):
        by_mode = {}
        for mode in modes:
            t0 = time.monotonic()
            reply = target.query(row["question"], mode, top_k)
            wall_ms = (time.monotonic() - t0) * 1000
            hits = reply.get("hits") or []
            by_mode[mode] = {**SC.classify(hits, row, top_k), "wall_ms": round(wall_ms, 1),
                             "reply_error": bool(reply.get("isError"))}
            evidence.setdefault(mode, {"target_mode": zoteus_adapter.MODES.get(mode), **mode_evidence(reply)})
        primary = by_mode[modes[0]]
        readings.append({**row, "score": primary, "wall_ms": primary["wall_ms"],
                         "reply_error": primary["reply_error"], "by_mode": by_mode})
        if i % 10 == 0:
            logging.info("%d / %d questions asked", i, len(rows))
    return readings, evidence


def identity(args, headers: dict, target, build: dict | None, index_file: Path | None,
             n_scope: int, writer, scope: Scope | None, proxy_port: int | None, evidence: dict,
             embedder: dict) -> dict:
    return {
        "ticket": "0719",
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "seed": args.seed,
        "library": {
            "base_url": args.base_url,
            "zotero_version": headers.get("x-zotero-version"),
            "last_modified_version": headers.get("last-modified-version"),
        },
        "target": target.declaration.as_json(),
        # Which model produced the vectors, at which precision and pooling. A run
        # read without this can be reported two opposite ways (ticket 0732).
        "embedder": embedder,
        "posture": "none: the process runs unwrapped under the operator, since the run's "
                   "subject is the operator's own library",
        "scope": {
            **(scope.as_json() if scope else {"kind": "index-as-found"}),
            "proxy": f"127.0.0.1:{proxy_port}, ZOTERO_LOCAL_PORT of the target" if proxy_port else None,
            "index_file": index_file.name if index_file else None,
            "items_in_index": n_scope,
            "build": build,
            "built_in_this_run": bool(build) and not args.reuse_index,
        },
        "extraction": {
            "target_fulltext_cap_chars": args.fulltext_cap,
            "text_source": "Zotero's own extraction, over the local API's /fulltext",
        },
        "question_writer": {
            "writer": writer.name, "model": writer.model,
            "endpoint": getattr(writer, "endpoint", None),
            "server_fingerprint": getattr(writer, "fingerprint", None),
            "fallback_reason": getattr(writer, "fallback_reason", None),
            "other_language_share": args.other_language_share,
        },
        "query": {"primary_mode": PRIMARY_MODE, "modes": {m: zoteus_adapter.MODES.get(m) for m in MODES},
                  "top_k": args.top_k, "mode_evidence": evidence},
        "census": str(args.census),
    }


def report(readings: list[dict], sample_summary: dict, questions_summary: dict) -> dict:
    walls = [r["wall_ms"] for r in readings]
    by_mode = {m: SC.aggregate(readings, lambda r: "all", f"by_mode.{m}")["all"]
               for m in MODES if readings and m in readings[0].get("by_mode", {})}
    by_mode_lane = {m: SC.aggregate(readings, lambda r: r["lane"], f"by_mode.{m}")
                    for m in MODES if readings and m in readings[0].get("by_mode", {})}
    by_mode_cross = {m: SC.aggregate(readings, lambda r: "cross-lingual" if r["cross_lingual"] else "same-language",
                                     f"by_mode.{m}")
                     for m in MODES if readings and m in readings[0].get("by_mode", {})}
    return {
        "sample": sample_summary,
        "questions": questions_summary,
        "readings": {
            "n": len(readings),
            "reply_errors": sum(1 for r in readings if r["reply_error"]),
            "query_wall_ms": {"first": walls[0] if walls else None,
                              "median_after_first": round(statistics.median(walls[1:]), 1) if len(walls) > 1 else None,
                              "max": max(walls) if walls else None},
        },
        "ladder": {
            "by_lane": SC.aggregate(readings, lambda r: r["lane"]),
            "by_cross_lingual": SC.aggregate(readings, lambda r: "cross-lingual" if r["cross_lingual"] else "same-language"),
            "by_format": SC.aggregate(readings, lambda r: r["format"]),
            "by_type": SC.aggregate(readings, lambda r: r["type_group"]),
            "by_compound": SC.aggregate(readings, lambda r: "compound" if r["score"].get("compound") else "simple"),
            "by_length": SC.aggregate(readings, lambda r: r["length_bucket"]),
            "by_reachability": SC.aggregate(readings, lambda r: "within-cap" if r["within_default_cap"] else "beyond-cap"),
            "by_writer": SC.aggregate(readings, lambda r: r["writer"]),
            "by_mode": by_mode,
            "by_mode_and_lane": by_mode_lane,
            "by_mode_and_cross_lingual": by_mode_cross,
        },
        "chain_in_reply": SC.chain_tally(readings),
        "self_consistency_note": (
            "every question was written from the paragraph it must retrieve, so this is a "
            "self-consistency probe, closer to a recall check than to a user need; need-driven "
            "questions are the Menagerie's (ticket 0029)"),
    }


def markdown(doc: dict) -> str:
    def table(title: str, cells: dict) -> str:
        lines = [f"**{title}**", "", "| group | n | win | near-win | miss | row MRR | work MRR |", "|---|---|---|---|---|---|---|"]
        for g, c in cells.items():
            lines.append(f"| {g} | {c['n']} | {c['win']} | {c['near_win']} | {c['miss']} | {c['row_mrr']} | {c['work_mrr']} |")
        return "\n".join(lines) + "\n"
    out = [table("by lane (question language -> answer language), primary mode", doc["ladder"]["by_lane"]),
           table("by retrieval mode", doc["ladder"]["by_mode"]),
           table("by format", doc["ladder"]["by_format"]),
           table("by item type", doc["ladder"]["by_type"]),
           table("compound vs simple documents", doc["ladder"]["by_compound"]),
           table("by document length", doc["ladder"]["by_length"]),
           table("by reachability under the target's body-text cap", doc["ladder"]["by_reachability"])]
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrypoint", required=True, help="the target's built entrypoint (fork/dist/index.js)")
    ap.add_argument("--arena", type=Path, required=True, help="the target's arena: data directory, home, tmp")
    ap.add_argument("--scope-items", type=int, default=300,
                    help="size of the seeded random item sample the target sees as its library")
    ap.add_argument("--reuse-index", action="store_true",
                    help="skip the build and use the arena's index and recorded build cost")
    ap.add_argument("--build-only", action="store_true",
                    help="build the index, record its cost in the arena, and stop")
    ap.add_argument("--build-timeout", type=float, default=3600.0)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--work-dir", type=Path, required=True, help="private rows (never committed)")
    ap.add_argument("--output", type=Path, required=True, help="the aggregate artifact")
    # `--transformers-path` serves both the target's embedder (through the adapter)
    # and the fallback writer; `--zotero-data-dir` serves the sampler's page labels
    # and the target's library location. Both are declared once, by the sampler
    # and the writer, and read here.
    S.add_arguments(ap)
    Q.add_arguments(ap)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.arena.mkdir(parents=True, exist_ok=True)
    record = args.arena / "build-record.json"
    scope_file = args.arena / "scope.json"

    listed = S.list_library(args)
    _, items, headers = listed
    if args.reuse_index and scope_file.is_file():
        saved = json.loads(scope_file.read_text())
        scope = Scope(saved["seed"], saved["requested"], frozenset(saved["record_keys"]), frozenset(saved["child_keys"]))
    else:
        scope = Scope.random(items, args.scope_items, args.seed)
        scope_file.write_text(json.dumps({"seed": scope.seed, "requested": scope.requested,
                                          "record_keys": sorted(scope.record_keys),
                                          "child_keys": sorted(scope.child_keys)}))
    proxy = ScopeProxy(args.base_url.split("/api")[0], scope).start()
    os.environ["ZOTERO_LOCAL_PORT"] = str(proxy.port)
    logging.info("scope: %d records, %d children; proxy on 127.0.0.1:%d", len(scope.record_keys),
                 len(scope.child_keys), proxy.port)

    target = zoteus_adapter.build(
        "zoteus", args.arena, entrypoint=args.entrypoint, transformers_path=args.transformers_path,
        zotero_data_dir=args.zotero_data_dir, posture=None)
    writer = Q.build_writer(args)
    try:
        with target.running():
            if args.reuse_index:
                build = json.loads(record.read_text()) if record.is_file() else None
            else:
                build = build_index(target, len(scope.record_keys), args.build_timeout)
                record.write_text(json.dumps(build, indent=1) + "\n")
                if args.build_only:
                    logging.info("built; record in %s", record)
                    return 0
            index_file, keys = index_item_keys(target.data_dir)
            if not keys:
                raise SystemExit(f"no built index under {target.data_dir}")
            args.scope_keys = args.work_dir / "scope-keys.txt"
            args.scope_keys.write_text("\n".join(keys) + "\n")
            rows, sample_summary, _ = S.sample(args, listed=listed)
            S.write_outputs(rows, sample_summary, args.work_dir)
            rows = Q.write_questions(rows, writer, args.other_language_share, args.seed)
            questions_summary = Q.questions_summary(rows, writer, args.other_language_share)
            with (args.work_dir / "questions.jsonl").open("w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            readings, evidence = ask(target, rows, args.top_k)
            status_after = index_status(target)
    finally:
        proxy.stop()
    # Read after the target is down: the stamp is a file, and the status is the
    # last one the running target gave. `models` is where the target caches the
    # weights it loaded (`modelCacheDir` = <dataDir>/models).
    embedder = embedder_identity(status_after, index_embedder_stamp(index_file), evidence,
                                 dict(os.environ), target.data_dir / "models")
    logging.info("embedder: %s", json.dumps({k: embedder[k] for k in ("model", "dtype", "pooling", "model_source")}))
    with (args.work_dir / "readings.jsonl").open("w", encoding="utf-8") as f:
        for r in readings:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    doc = {
        "identity": identity(args, headers, target, build, index_file, len(keys), writer, scope, proxy.port,
                             evidence, embedder),
        "index_after_run": {k: status_after.get(k) for k in ("passages", "vectors", "items", "embedder", "state")},
        "proxy": {"requests": len(proxy.requests), "refused_non_get": proxy.refused},
        **report(readings, sample_summary, questions_summary),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(markdown(doc))
    logging.info("wrote %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
