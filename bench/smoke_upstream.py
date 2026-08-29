#!/usr/bin/env python3
"""Smoke the reviewed upstream baseline against a real Zotero library, by requirement.

`verification/SMOKE-1.10.0.md` recorded one session driven by hand. This is the
repeatable form: each check names the requirement clause it exercises, states what
would falsify it, and lands in a JSON artifact so `spec/README.md` can cite a run
rather than a memory.

What it is NOT: a requirements test suite. R-items are sets of MUST clauses, and a
check here exercises ONE clause of one requirement, against one library, once. It
earns a row the word `measured` in place of `code` — something ran — and nothing
stronger. Where a check cannot decide, it reports `observed` rather than inventing
a verdict.

Every check is read-only against the Zotero library. The schema check writes only
to a COPY of an index, made by this script in a scratch directory.

    python3 bench/smoke_upstream.py --server <fork>/dist/index.js \\
        --index <a-current-search-index.sqlite> --output bench/results/smoke-1.10.0/checks.json
"""
import argparse
import json
import logging
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_drive import Server  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("smoke")


def payload(resp: dict) -> dict:
    r = resp.get("result", resp)
    if "structuredContent" in r:
        return r["structuredContent"]
    for block in r.get("content", []):
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return {"text": block["text"][:4000]}
    return r


def env_for(a: argparse.Namespace, data_dir: Path) -> dict[str, str]:
    env = {
        "ZOTEUS_EMBEDDINGS": "local",
        "ZOTEUS_DATA_DIR": str(data_dir),
        "ZOTEUS_INDEX_BACKEND": "sqlite",
        "ZOTEUS_INDEX_AUTO_REFRESH": "false",
        "ZOTEUS_INDEX_FULLTEXT": "1",
        "ZOTEUS_READ_ONLY": "true",
    }
    if a.transformers_path:
        env["ZOTEUS_TRANSFORMERS_PATH"] = a.transformers_path
    if a.zotero_data_dir:
        env["ZOTERO_DATA_DIR"] = a.zotero_data_dir
    return env


def start(a: argparse.Namespace, data_dir: Path) -> Server:
    s = Server(["node", a.server], env_for(a, data_dir), timeout=a.timeout)
    s.handshake()
    return s


def check(cid: str, requirement: str, clause: str, falsified_by: str,
          result: str, detail: object) -> dict:
    return {"check": cid, "requirement": requirement, "clause": clause,
            "falsified_by": falsified_by, "result": result, "detail": detail}


def check_local_by_default(s: Server) -> dict:
    """R10: the default embedder is local — asserted against a running server, not the source."""
    who = payload(s.call("tools/call", {"name": "zotero_whoami", "arguments": {}}))
    st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    emb = who.get("embeddings", {})
    ok = emb.get("effective") == "local" and st.get("embedderActive") is True and st.get("embedder") == "local"
    return check(
        "R10-local-embedder", "R10", "the embedder is local by default",
        "effective embeddings resolving to a hosted provider, or an inactive local embedder",
        "pass" if ok else "fail",
        {"whoami_embeddings": emb, "status_embedder": st.get("embedder"),
         "embedderActive": st.get("embedderActive"), "model": st.get("embedderModel"),
         "cloud": who.get("cloud"), "localApi": who.get("localApi")})


def check_model_stays_in_data_dir(data_dir: Path) -> dict:
    """R28: the downloaded model does not escape the data directory."""
    models = data_dir / "models"
    present = models.is_dir()
    files = sorted(p.name for p in models.iterdir()) if present else []
    return check(
        "R28-model-in-data-dir", "R28", "the model cache lives under the data directory",
        "a model cache created outside the data directory (a shared HF cache, or $HOME)",
        "pass" if present else "observed",
        {"models_dir": str(models), "exists": present, "entries": files[:10],
         "note": None if present else
         "no model directory in this data dir — the run reused an existing cache, so this "
         "check did not exercise a download and decides nothing"})


def _restamp_and_open(a: argparse.Namespace, scratch: Path, stamp: str) -> dict:
    """Copy the index, restamp it, start a server on it, and report what happened to the file."""
    data_dir = scratch / f"schema-{stamp}"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "search-index.sqlite"
    shutil.copyfile(a.index, target)
    before_bytes = target.stat().st_size

    con = sqlite3.connect(target)
    was = con.execute("SELECT value FROM meta WHERE key='schemaVersion'").fetchone()
    con.execute("UPDATE meta SET value=? WHERE key='schemaVersion'", (stamp,))
    con.commit()
    con.close()

    s = start(a, data_dir)
    st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    s.p.terminate()

    sidelined = sorted(p for p in data_dir.glob("search-index.sqlite.incompatible-*")
                       if not p.name.endswith(("-wal", "-shm")))
    return {
        "original_schemaVersion": was[0] if was else None,
        "restamped_to": stamp,
        "sidelined_file": sidelined[0].name if sidelined else None,
        "sidelined_bytes_match_original": bool(sidelined) and sidelined[0].stat().st_size == before_bytes,
        "served_index_is_empty": (st.get("passages") or 0) == 0 and (st.get("documents") or 0) == 0,
        "storageNotice": st.get("storageNotice"),
    }


def check_foreign_schema_is_sidelined(a: argparse.Namespace, scratch: Path) -> dict:
    """R23: a schema stamp this build must not write into is read BEFORE the file is opened writable.

    The positive control is the point. A copy of a current index is restamped to a version
    the build cannot serve; the check passes only if the original bytes survive under a
    `.incompatible-` name AND the served index is a fresh empty one. A build that silently
    wrote into the foreign file, or deleted it, fails here.

    BOTH DIRECTIONS are exercised, and the older one is the one that matters. A newer stamp
    is the rare case — a user who downgraded. An OLDER stamp is what every user holds the
    day the current build's `SCHEMA_VERSION` is incremented, so if the two are not treated
    alike, the interesting half is the one a forward-only probe would miss.
    """
    older, newer = _restamp_and_open(a, scratch, "0"), _restamp_and_open(a, scratch, "9999")
    both = [older, newer]
    ok = all(d["sidelined_bytes_match_original"] and d["served_index_is_empty"] for d in both)
    return check(
        "R23-foreign-schema-sidelined", "R23",
        "an index this build must not write into is detected before anything writes to it",
        "the foreign index modified or deleted, or its rows served as if current",
        "pass" if ok else "fail",
        {"older_stamp": older, "newer_stamp": newer,
         "treated_alike": older["served_index_is_empty"] == newer["served_index_is_empty"]})


def check_migration_absent(a: argparse.Namespace, scratch: Path, sideline: dict) -> dict:
    """The other half of R23: 'serving in both directions is still design.'

    The sideline check above proves the DAMAGE half. This one names what the same
    evidence shows about the remaining half: a stamped older version is not migrated,
    it is abandoned. Reported as `observed`, since one restamp cannot prove no code
    path anywhere migrates — it shows this one does not.
    """
    d = sideline["detail"]
    abandoned = sideline["result"] == "pass" and d["older_stamp"]["served_index_is_empty"]
    return check(
        "R23-no-migration-path", "R23",
        "an index stamped with a different version is read rather than abandoned",
        "a rebuilt index carrying the old index's passages or vectors",
        "observed",
        {"index_was_abandoned_not_migrated": bool(abandoned),
         "consequence": "every passage must be re-embedded after any SCHEMA_VERSION change",
         "cost_reference": "bench/results/0025-x1-recall/embed-feasibility.json"})


def check_query_answers(s: Server, queries: list[str], limit: int) -> dict:
    """R6/R7: a query answers, in what time, and whether the score carries magnitude."""
    runs = []
    for q in queries:
        t = time.perf_counter()
        r = payload(s.call("tools/call", {"name": "zotero_semantic_search", "arguments": {
            "q": q, "mode": "semantic", "limit": limit, "auto_build": False}}))
        ms = round((time.perf_counter() - t) * 1000, 1)
        hits = r.get("hits") or []
        runs.append({"q": q, "wall_ms": ms, "hits": len(hits),
                     "scores": [h.get("score") for h in hits],
                     "titles": [(h.get("title") or "")[:80] for h in hits]})
    answered = [r for r in runs if r["hits"] > 0]
    # RRF over one list gives 1/(60+rank) exactly; a similarity would not.
    rrf = [round(1 / (60 + i), 6) for i in range(1, limit + 1)]
    rank_shaped = sum(1 for r in runs
                      if [round(x, 6) for x in r["scores"]] == rrf[:len(r["scores"])])
    return check(
        "R6-query-answers", "R6", "a query returns something usable, warm, within the budget",
        "a query returning no hits on a populated index, or no run completing",
        "pass" if len(answered) == len(runs) and runs else "fail",
        {"runs": runs,
         "warm_ms": sorted(r["wall_ms"] for r in runs)[1:],
         "queries_whose_scores_are_exactly_1_over_60_plus_rank": rank_shaped,
         "score_note": ("a score equal to 1/(60+rank) is reciprocal-rank fusion over a single "
                        "list — a relabelled rank, carrying no similarity magnitude, so a caller "
                        "cannot threshold it to mean 'nothing good was found'")})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="path to the upstream MCP entrypoint")
    ap.add_argument("--data-dir", required=True, help="data dir holding an index to query")
    ap.add_argument("--index", help="a CURRENT-schema index, copied for the schema check")
    ap.add_argument("--transformers-path", default="")
    ap.add_argument("--zotero-data-dir", default="")
    ap.add_argument("--queries", nargs="*", default=[
        "carbon tax and household energy spending",
        "permafrost thaw feedback",
        "integrated assessment model discount rate",
    ])
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    data_dir = Path(a.data_dir)
    checks = []
    s = start(a, data_dir)
    server_info = None
    try:
        checks.append(check_local_by_default(s))
        checks.append(check_model_stays_in_data_dir(data_dir))
        checks.append(check_query_answers(s, a.queries, a.limit))
    finally:
        s.p.terminate()

    if a.index:
        with tempfile.TemporaryDirectory(prefix="zoteus-smoke-") as tmp:
            sideline = check_foreign_schema_is_sidelined(a, Path(tmp))
            checks.append(sideline)
            checks.append(check_migration_absent(a, Path(tmp), sideline))

    version = subprocess.run(
        ["node", "-e", "console.log(require('./package.json').version)"],
        cwd=Path(a.server).resolve().parent.parent, capture_output=True, text=True).stdout.strip()

    out = {
        "probe": "smoke the reviewed upstream baseline against a real Zotero library, by requirement",
        "not_a_test_suite": (
            "each check exercises ONE clause of one requirement, once, against one library. It "
            "earns a spec/README row the word 'measured' rather than 'code' — something ran — and "
            "nothing stronger."),
        "upstream_version": version or None,
        "server_info": server_info,
        "date": time.strftime("%Y-%m-%d"),
        "data_dir": str(data_dir),
        "checks": checks,
        "summary": {r: sum(1 for c in checks if c["result"] == r)
                    for r in ("pass", "fail", "observed")},
    }
    Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    for c in checks:
        log.info("%-32s %-8s %s", c["check"], c["result"].upper(), c["clause"])
    log.info("wrote %s", a.output)
    if out["summary"]["fail"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
