#!/usr/bin/env python3
"""A stub MCP server over stdio, for tests of bench/golden_run.py.

Speaks just enough JSON-RPC for the runner: `initialize`, the `notifications/initialized`
notification, `tools/call` for `zotero_index` (status) and `zotero_semantic_search`. The
hits it answers come from the JSON file named by GOLDEN_STUB_HITS, keyed by query string;
a query with no entry gets no hits. Every call is echoed to GOLDEN_STUB_LOG when set, so a
test can assert what the runner actually asked for.
"""

import json
import os
import sys


def main() -> int:
    hits_by_query = {}
    if os.environ.get("GOLDEN_STUB_HITS"):
        with open(os.environ["GOLDEN_STUB_HITS"], encoding="utf-8") as stream:
            hits_by_query = json.load(stream)
    log_path = os.environ.get("GOLDEN_STUB_LOG")

    def log(entry):
        if log_path:
            with open(log_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry) + "\n")

    def send(message):
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        method = message.get("method")
        mid = message.get("id")
        log({"method": method, "params": message.get("params")})
        if mid is None:
            continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "serverInfo": {"name": "golden-stub", "version": "0"},
            }})
        elif method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name == "zotero_index":
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": "status"}],
                    "structuredContent": {"state": "done", "items": 3, "passages": 9, "vectors": 0,
                                          "embedder": "none (stub)", "chunker": "stub-chunker"},
                }})
            elif name == "zotero_semantic_search":
                hits = hits_by_query.get(arguments.get("q"), [])[: int(arguments.get("limit") or 10)]
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": f"{len(hits)} hit(s)"}],
                    "structuredContent": {"hits": hits, "embedder": "none (stub)", "fulltextEnabled": True},
                }})
            else:
                send({"jsonrpc": "2.0", "id": mid, "result": {"isError": True,
                                                              "content": [{"type": "text", "text": f"unknown tool {name}"}]}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
