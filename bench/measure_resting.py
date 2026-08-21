#!/usr/bin/env python3
"""Measure a Zoteus server at rest: load an existing index, query it, report memory."""
import argparse
import json
import logging
import subprocess
import sys
import time

from mcp_drive import Server

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("rest")


def mem(pid: int) -> dict[str, float]:
    """RSS and swap for a pid, in MB, from /proc/<pid>/status."""
    out = {}
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith(("VmRSS:", "VmSwap:", "VmHWM:")):
                k, v, _ = line.split()
                out[k.rstrip(":")] = int(v) / 1024
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--node-options", default="")
    ap.add_argument("--query", default="cout social du carbone")
    a = ap.parse_args()

    env = {"ZOTEUS_EMBEDDINGS": "off", "ZOTEUS_INDEX_FULLTEXT": "1",
           "ZOTEUS_DATA_DIR": a.data_dir}
    if a.node_options:
        env["NODE_OPTIONS"] = a.node_options

    s = Server(["node", a.server], env, 600)
    s.handshake()
    log.info("après handshake      %s", mem(s.p.pid))

    # The index is loaded lazily, on the first search.
    t0 = time.monotonic()
    r = s.call("tools/call", {"name": "zotero_semantic_search",
                              "arguments": {"q": a.query, "limit": 3}})
    load = time.monotonic() - t0
    sc = r.get("result", {}).get("structuredContent", {})
    log.info("1re requête %.1f s   %d hits", load, len(sc.get("hits", [])))
    log.info("après chargement     %s", mem(s.p.pid))

    t0 = time.monotonic()
    s.call("tools/call", {"name": "zotero_semantic_search",
                          "arguments": {"q": "equilibre general walrasien", "limit": 3}})
    log.info("2e requête  %.3f s", time.monotonic() - t0)
    log.info("au repos             %s", mem(s.p.pid))

    subprocess.run(["node", "--version"], capture_output=True)
    s.p.terminate()


if __name__ == "__main__":
    main()
