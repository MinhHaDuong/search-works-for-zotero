#!/usr/bin/env python3
"""Build the Zoteus search index and poll to completion, timing and sizing it."""
import argparse
import json
import logging
import os
import subprocess
import time

from mcp_drive import Server

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build")


def payload(resp: dict) -> dict:
    """Pull the structured body out of an MCP tool result."""
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


def dir_size(path: str) -> int:
    return sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(path)
        for f in files
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--poll", type=float, default=20.0)
    ap.add_argument("--max-wait", type=float, default=3600.0)
    ap.add_argument("--max-items", default="5000")
    ap.add_argument("--max-chars", default="40000")
    ap.add_argument("--node-options", default="--max-old-space-size=10240")
    a = ap.parse_args()

    env = {"ZOTEUS_EMBEDDINGS": "off", "ZOTEUS_INDEX_FULLTEXT": "1",
           "ZOTEUS_DATA_DIR": a.data_dir,
           "ZOTEUS_INDEX_MAX_ITEMS": a.max_items,
           "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": a.max_chars,
           "NODE_OPTIONS": a.node_options}
    s = Server(["node", a.server], env, a.max_wait)
    s.handshake()

    t0 = time.monotonic()
    start = payload(s.call("tools/call", {"name": "zotero_index",
                                          "arguments": {"action": "build",
                                                        "fulltext": True}}))
    log.info("build kicked off: %s", json.dumps(start, ensure_ascii=False)[:400])

    last, peak = None, 0
    while time.monotonic() - t0 < a.max_wait:
        time.sleep(a.poll)
        rss = subprocess.run(["ps", "-o", "rss=", "-p", str(s.p.pid)],
                             capture_output=True, text=True).stdout.strip()
        peak = max(peak, int(rss or 0))
        st = payload(s.call("tools/call", {"name": "zotero_index",
                                           "arguments": {"action": "status"}}))
        state = json.dumps(st, ensure_ascii=False)
        if state != last:
            log.info("[%6.0fs] %s", time.monotonic() - t0, state[:400])
            last = state
        status = str(st.get("status") or st.get("state") or "")
        if status and status not in {"running", "building", "in_progress", "pending"}:
            break

    elapsed = time.monotonic() - t0
    rss = subprocess.run(["ps", "-o", "rss=", "-p", str(s.p.pid)],
                         capture_output=True, text=True).stdout.strip()
    log.info("--- elapsed %.0f s | node RSS %s kB | peak RSS %.2f GB | data dir %.1f MB ---",
             elapsed, rss or "?", peak / 1048576, dir_size(a.data_dir) / 1e6)
    s.p.terminate()


if __name__ == "__main__":
    main()
