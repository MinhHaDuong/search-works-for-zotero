#!/usr/bin/env python3
"""Drive the question bank through a zoteus build over the replayed golden export.

The runner for ticket 0722: build the replay index exactly as
`bench/fixtures/make_index_fixture.mjs --replay-export` does (it shells out to that entry,
never to a hand-written indexer), start the mock local API again for the query side, start
the MCP server over the built index, ask each question's query through the search tool the
server exposes at k=10 in the lexical mode, and write a `menagerie-replies/v2` file holding
everything the reply carried. Embeddings are off in the offline replay, so the semantic and
hybrid modes are written as not-run with the reason, never as an empty result set.

What the reply carries is measured, not assumed: the run block records the union of the
fields the tool's hits actually had (`reply_shape`), and which chain fields came from the
reply itself versus a lookup of the replay items by item key. That is the chain-completeness
ceiling of the build, and the scorer reports it rather than hiding it.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_gate import (  # noqa: E402
    REPLIES_SCHEMA,
    CHAIN_FIELDS,
    Export,
    InputError,
    load_bank,
    load_export,
    load_thresholds,
)
from mcp_drive import Server  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("golden-run")

REPO = Path(__file__).resolve().parent.parent
SEARCH_TOOL = "zotero_semantic_search"
#: The server's name for the lexical mode; the bank's vocabulary calls it `lexical`.
LEXICAL_MODE_ARGUMENT = "keyword"
NOT_RUN_MODES = {
    "semantic": "embeddings are off in the offline replay (ZOTEUS_EMBEDDINGS=off): the index holds no vectors",
    "hybrid": "embeddings are off in the offline replay (ZOTEUS_EMBEDDINGS=off): hybrid would degrade to keyword and say so",
}


def payload(resp: dict) -> dict:
    r = resp.get("result", resp)
    if "structuredContent" in r:
        return r["structuredContent"]
    for block in r.get("content", []):
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                continue
    return r


def build_index(export_dir: Path, recipe: Path, server: Path, data_dir: Path, max_wait: float) -> dict[str, Any]:
    """Build the replay index through the committed entry; return its report."""

    with tempfile.TemporaryDirectory(prefix="golden-build-") as scratch:
        report = Path(scratch) / "build-report.json"
        command = [
            "node",
            str(REPO / "bench" / "fixtures" / "make_index_fixture.mjs"),
            "--replay-export", str(export_dir),
            "--recipe", str(recipe),
            "--server", str(server),
            "--data-dir", str(data_dir),
            "--embeddings", "off",
            "--report", str(report),
            "--max-wait", str(max_wait),
        ]
        log.info("building the replay index: %s", " ".join(command))
        done = subprocess.run(command, cwd=REPO)
        if done.returncode != 0:
            raise RuntimeError(f"replay build exited {done.returncode}")
        return json.loads(report.read_text(encoding="utf-8"))


class Replay:
    """The mock local API for the query side; a context manager owning the node child."""

    def __init__(self, export_dir: Path, recipe: Path):
        self.export_dir = export_dir
        self.recipe = recipe
        self.port: int | None = None
        self.process: subprocess.Popen | None = None

    def __enter__(self) -> "Replay":
        self.process = subprocess.Popen(
            ["node", str(REPO / "bench" / "fixtures" / "golden_replay_serve.mjs"),
             "--export", str(self.export_dir), "--recipe", str(self.recipe)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, cwd=REPO,
        )
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("the golden replay did not report a port")
        self.port = int(json.loads(line)["port"])
        return self

    def __exit__(self, *_: object) -> None:
        if self.process is None:
            return
        try:
            self.process.stdin.close()
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()


def server_environment(export: Export, data_dir: Path, replay_port: int | None) -> dict[str, str]:
    """The query-side environment: the build's, minus nothing the index needs to be read."""

    env = {
        "ZOTEUS_EMBEDDINGS": "off",
        "ZOTEUS_INDEX_FULLTEXT": "1",
        "ZOTEUS_DATA_DIR": str(data_dir),
        "ZOTEUS_INDEX_BACKEND": "sqlite",
        "ZOTEUS_INDEX_AUTO_REFRESH": "false",
        "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": str(export.manifest.get("index_fulltext_max_chars")),
        "ZOTEUS_UPDATE_CHECK": "false",
        "ZOTEUS_OAUTH_ENABLED": "false",
    }
    library = export.manifest.get("library") or {}
    if replay_port is not None:
        env.update({
            "ZOTEUS_LOCAL": "on",
            "ZOTERO_LOCAL_PORT": str(replay_port),
            "ZOTERO_LIBRARY_TYPE": str(library.get("type", "user")),
            "ZOTERO_LIBRARY_ID": str(library.get("id", "")),
        })
    return env


def _creators(data: dict[str, Any]) -> str | None:
    names = []
    for creator in data.get("creators") or []:
        if creator.get("name"):
            names.append(creator["name"])
        else:
            parts = [creator.get("firstName"), creator.get("lastName")]
            names.append(" ".join(part for part in parts if part))
    return "; ".join(name for name in names if name) or None


def chain_from_items(export: Export, item_key: str, hit_title: str | None) -> dict[str, str | None]:
    data = export.items.get(item_key, {})
    chain: dict[str, str | None] = {name: None for name in CHAIN_FIELDS}
    chain["title"] = hit_title or data.get("title") or None
    chain["author"] = _creators(data)
    chain["date"] = data.get("date") or None
    chain["identifier"] = data.get("DOI") or data.get("ISBN") or data.get("url") or None
    return chain


def to_result(rank: int, hit: dict[str, Any], export: Export) -> dict[str, Any]:
    item_key = hit.get("itemKey") or hit.get("key") or hit.get("item_key")
    attachment_key = hit.get("attachmentKey") or hit.get("attachment_key")
    page = hit.get("page") or hit.get("pageLabel") or hit.get("page_label")
    return {
        "rank": rank,
        "item_key": item_key,
        "attachment_key": attachment_key,
        "work_id": export.work_of_item.get(item_key),
        "evidence": hit.get("snippet") or hit.get("passage") or hit.get("text"),
        "page": str(page) if page is not None else None,
        "chain": chain_from_items(export, item_key, hit.get("title")),
        "score": hit.get("score"),
        "source": hit.get("source"),
    }


def drive_queries(
    server_command: list[str], env: dict[str, str], questions: list[dict[str, Any]], k: int, timeout: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ask every question in the lexical mode; return raw hits per question and the index status."""

    server = Server(server_command, env, timeout)
    try:
        init = server.handshake()
        status = payload(server.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
        answers = []
        for question in questions:
            resp = server.call(
                "tools/call",
                {"name": SEARCH_TOOL, "arguments": {"q": question["query"], "mode": LEXICAL_MODE_ARGUMENT,
                                                     "limit": k, "auto_build": False}},
            )
            if resp.get("result", {}).get("isError"):
                raise RuntimeError(f"tool error on {question['id']}: {json.dumps(resp['result'])[:800]}")
            body = payload(resp)
            hits = [hit for hit in body.get("hits", []) if isinstance(hit, dict)]
            log.info("[%s] %-60s -> %d hit(s)", question["id"], question["query"][:60], len(hits))
            answers.append({"question": question, "hits": hits, "body": {k_: v for k_, v in body.items() if k_ != "hits"}})
        return answers, {"status": status, "server_info": init.get("result", {}).get("serverInfo", {})}
    finally:
        server.p.terminate()
        try:
            server.p.wait(timeout=5)
        except Exception:
            server.p.kill()


def assemble_replies(
    answers: list[dict[str, Any]], meta: dict[str, Any], export: Export, k: int, run_extra: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    replies = []
    hit_fields: set[str] = set()
    for answer in answers:
        question = answer["question"]
        for hit in answer["hits"]:
            hit_fields.update(hit.keys())
        results = [to_result(rank, hit, export) for rank, hit in enumerate(answer["hits"][:k], start=1)]
        if question["mode"] in ("any", "lexical"):
            replies.append({"id": question["id"], "mode": "lexical", "results": results, "tool_reply": answer["body"]})
        for mode, reason in NOT_RUN_MODES.items():
            if question["mode"] in ("any", mode):
                replies.append({"id": question["id"], "mode": mode, "results": None, "not_run_reason": reason})
    embedder = None
    for answer in answers:
        embedder = answer["body"].get("embedder") or embedder
    run = {
        "date": _dt.date.today().isoformat(),
        "k": k,
        "recipe_sha256": export.manifest.get("recipe_sha256"),
        "export_sha256": export.sha256,
        "extraction": export.extraction(),
        "embedder": embedder or "off",
        "retrieval_mode": f"{LEXICAL_MODE_ARGUMENT} (BM25 over passages) reported as lexical; semantic and hybrid not-run",
        "tool": SEARCH_TOOL,
        "index_status": meta.get("status"),
        "server_info": meta.get("server_info"),
        "reply_shape": {
            "hit_fields": sorted(hit_fields),
            "chain_from_reply": ["title"],
            "chain_from_replay_items_by_item_key": ["author", "date", "identifier"],
            "chain_never_carried": ["section_heading", "page_printed", "part_title", "part_byline"],
            "attachment_key_carried": "attachmentKey" in hit_fields or "attachment_key" in hit_fields,
            "page_carried": bool({"page", "pageLabel", "page_label"} & hit_fields),
        },
        **run_extra,
    }
    bundle: dict[str, Any] = {"schema": REPLIES_SCHEMA, "run": run, "replies": replies}
    if previous is not None:
        bundle["previous_run"] = {"run": previous["run"], "replies": previous["replies"]}
    return bundle


def fork_build_sha(server: Path) -> str | None:
    """The git HEAD of the checkout that built dist/index.js, when it is one."""

    for candidate in (server.resolve().parent.parent, server.resolve().parent):
        if (candidate / ".git").exists():
            done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=candidate, capture_output=True, text=True)
            if done.returncode == 0:
                return done.stdout.strip()
    return None


def upstream_index_schema() -> str | None:
    try:
        for line in (REPO / "UPSTREAM").read_text(encoding="utf-8").splitlines():
            if line.startswith("UPSTREAM_INDEX_SCHEMA_VERSION="):
                return line.split("=", 1)[1].strip()
    except OSError:
        return None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export", type=Path, default=REPO / "bench" / "fixtures" / "export")
    parser.add_argument("--recipe", type=Path, default=REPO / "bench" / "fixtures" / "recipe-pinned.json")
    parser.add_argument("--bank", type=Path, default=REPO / "bench" / "fixtures" / "questions")
    parser.add_argument("--server", type=Path, required=True, help="the MCP server entrypoint, e.g. fork/dist/index.js")
    parser.add_argument("--server-command", default="node", help="the interpreter that runs --server")
    parser.add_argument("--data-dir", type=Path, required=True, help="an existing, empty directory for the index")
    parser.add_argument("--output", type=Path, default=REPO / "bench" / "results" / "golden" / "replies.json")
    parser.add_argument("--previous", type=Path, help="an earlier replies file, embedded as previous_run")
    parser.add_argument("--spec", type=Path, default=REPO / "SPEC.md")
    parser.add_argument("--k", type=int, help="results per query; default the k of SPEC §5.2.8")
    parser.add_argument("--max-wait", type=float, default=3600.0)
    parser.add_argument("--skip-build", action="store_true", help="the data directory already holds the built index")
    parser.add_argument("--no-replay", action="store_true", help="do not start the mock local API for the query side")
    args = parser.parse_args(argv)

    try:
        thresholds = load_thresholds(args.spec)
        questions = load_bank(args.bank)
        export = load_export(args.export)
    except InputError as exc:
        print(f"golden run: input error — {exc}", file=sys.stderr)
        return 2
    k = args.k or thresholds.k
    previous = None
    if args.previous:
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
        if previous.get("schema") != REPLIES_SCHEMA:
            print(f"golden run: --previous must be a {REPLIES_SCHEMA} file", file=sys.stderr)
            return 2

    build_report = None
    if not args.skip_build:
        build_report = build_index(args.export, args.recipe, args.server, args.data_dir, args.max_wait)
    replay_port = None
    with (Replay(args.export, args.recipe) if not args.no_replay else _NoReplay()) as replay:
        replay_port = replay.port
        env = server_environment(export, args.data_dir, replay_port)
        answers, meta = drive_queries([args.server_command, str(args.server)], env, questions, k, args.max_wait)
    run_extra = {
        "build_sha": fork_build_sha(args.server),
        "index_schema": upstream_index_schema(),
        "chunker": (meta.get("status") or {}).get("chunker", "not-reported by zotero_index status"),
        "build": None if build_report is None else {
            "exit_code": build_report.get("exit_code"),
            "status": (build_report.get("build") or {}).get("status"),
            "elapsed_s": (build_report.get("build") or {}).get("elapsed_s"),
        },
    }
    bundle = assemble_replies(answers, meta, export, k, run_extra, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log.info("wrote %s (%d replies; hit fields %s)", args.output, len(bundle["replies"]),
             bundle["run"]["reply_shape"]["hit_fields"])
    return 0


class _NoReplay:
    port = None

    def __enter__(self) -> "_NoReplay":
        return self

    def __exit__(self, *_: object) -> None:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
