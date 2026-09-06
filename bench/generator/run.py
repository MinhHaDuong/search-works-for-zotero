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

PRIMARY_MODE = "combined"
MODES = ("combined", "exact", "meaning")


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
    keep = ("state", "phase", "items", "itemsTotal", "itemsAvailable", "passages", "vectors",
            "fulltextItems", "fulltextPassages", "ownWordsPassages", "embedder", "embedderActive",
            "libraryVersion", "libraryBackend", "fulltextVersion", "builtFromVersion", "error",
            "passagesWithoutVectors", "localApiDegradedAt")
    return {"limit": limit, "elapsed_s": round(elapsed, 1), "timed_out": elapsed >= timeout_s,
            "status": {k: status.get(k) for k in keep if k in status}}


def mode_evidence(reply: dict) -> dict:
    """What the target's reply says about the path it ran, read off the reply."""
    return {k: reply.get(k) for k in ("embedder", "embedderConfigured", "embedderActive", "embedderReason",
                                       "vectors", "passagesWithoutVectors", "fulltextEnabled", "isError")
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
             n_scope: int, writer, scope: Scope | None, proxy_port: int | None, evidence: dict) -> dict:
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
    with (args.work_dir / "readings.jsonl").open("w", encoding="utf-8") as f:
        for r in readings:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    doc = {
        "identity": identity(args, headers, target, build, index_file, len(keys), writer, scope, proxy.port, evidence),
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
