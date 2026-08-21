#!/usr/bin/env python3
"""Run the same keyword queries against a Zoteus index on a chosen backend.

Emits one JSON document on stdout: per query, the ordered itemKey list, plus the
server's startup peak RSS (VmHWM) so a migration at startup is measured too.
"""
import argparse
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_drive import Server  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("query")


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


def vmhwm_kb(pid: int) -> int:
    try:
        with open(f"/proc/{pid}/status") as fh:
            for line in fh:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--queries-file", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--out", required=True)
    # Default EMPTY. Whether the server survives on a stock heap is itself an
    # exit criterion of ticket 0003, so the flag under test must never be the
    # default -- a run with defaults would pass the criterion without
    # exercising it. Pass it explicitly when driving the JSON backend, which
    # genuinely needs it.
    ap.add_argument("--node-options", default="")
    a = ap.parse_args()

    env = {"ZOTEUS_EMBEDDINGS": "off",
           "ZOTEUS_INDEX_FULLTEXT": "1",
           "ZOTEUS_DATA_DIR": a.data_dir,
           "ZOTEUS_SEARCH_BACKEND": a.backend,
           "ZOTEUS_INDEX_AUTO_REFRESH": "false",
           "NODE_OPTIONS": a.node_options}

    with open(a.queries_file) as fh:
        queries = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]

    t0 = time.monotonic()
    s = Server(["node", a.server], env, 3600)
    s.handshake()
    handshake_s = time.monotonic() - t0
    # The migration runs at startup, before the first index touch; poke the index so a
    # lazily-triggered one has happened before we read the high-water mark.
    st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    ready_s = time.monotonic() - t0
    peak_after_start = vmhwm_kb(s.p.pid)

    out = {"backend": a.backend, "handshake_s": round(handshake_s, 2),
           "ready_s": round(ready_s, 2), "peak_rss_kb_after_start": peak_after_start,
           "status": st, "queries": {}}

    for q in queries:
        resp = s.call("tools/call", {"name": "zotero_semantic_search",
                                      "arguments": {"q": q, "mode": "keyword",
                                                    "limit": a.limit,
                                                    "auto_build": False}})
        r = payload(resp)
        if resp.get("result", {}).get("isError"):
            raise SystemExit(f"tool error on query {q!r}: "
                             f"{json.dumps(resp['result'])[:800]}")
        hits = r.get("hits", [])
        keys = []
        for h in hits:
            if isinstance(h, dict):
                keys.append(h.get("itemKey") or h.get("key") or h.get("item_key"))
        out["queries"][q] = {
            "n": len(hits), "keys": keys,
            "hits": [{"itemKey": h.get("itemKey"), "score": h.get("score"),
                      "source": h.get("source"), "title": h.get("title")}
                     for h in hits if isinstance(h, dict)]}
        log.info("[%s] %-40s -> %d hits", a.backend, q[:40], len(hits))

    out["peak_rss_kb_final"] = vmhwm_kb(s.p.pid)
    with open(a.out, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    log.info("wrote %s", a.out)
    s.p.terminate()


if __name__ == "__main__":
    main()
