#!/usr/bin/env python3
"""Decompose query latency: same restart, auto-refresh OFF, to separate the
Zotero freshness probe (a network round trip) from the FTS5 query itself."""
import json
import sys
import time
sys.path.insert(0, "/home/haduong/CNRS/projets/actifs/zoteus-fts5/bench")
from mcp_drive import Server

SERVER = "/home/haduong/CNRS/projets/actifs/zoteus-fts5/fork/dist/index.js"
QUERIES = ["carbon tax revenue recycling", "biomass energy Vietnam",
           "integrated assessment model uncertainty", "carbon capture and storage cost",
           "discount rate", "photovoltaic"]

def payload(resp):
    r = resp.get("result", resp)
    if "structuredContent" in r:
        return r["structuredContent"]
    for b in r.get("content", []):
        if b.get("type") == "text":
            try:
                return json.loads(b["text"])
            except json.JSONDecodeError:
                continue
    return r

env = {"ZOTEUS_EMBEDDINGS": "off", "ZOTEUS_INDEX_FULLTEXT": "1",
       "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": "0", "ZOTEUS_INDEX_MAX_ITEMS": "1000000",
       "ZOTEUS_SEARCH_BACKEND": "sqlite", "ZOTEUS_DATA_DIR": "/home/haduong/.zoteus-bench-0003",
       "ZOTEUS_INDEX_AUTO_REFRESH": "false", "NODE_OPTIONS": ""}
s = Server(["node", SERVER], env, 600)
s.handshake()
out = {"env": env, "rows": []}
for rnd in ("cold", "warm"):
    for q in QUERIES:
        t = time.monotonic()
        p = payload(s.call("tools/call", {"name": "zotero_semantic_search",
                                          "arguments": {"q": q, "mode": "keyword", "limit": 10}}))
        dt = (time.monotonic() - t) * 1000
        hits = p.get("hits") or []
        out["rows"].append({"round": rnd, "q": q, "ms": round(dt, 1), "n": len(hits),
                            "indexRefresh": p.get("indexRefresh")})
        print(f"{rnd:5s} {dt:7.1f} ms  n={len(hits):2d}  refresh={p.get('indexRefresh')}  {q}")
with open("/tmp/zbench0003/serve_result_norefresh.json", "w") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
try:
    s.p.stdin.close()
    s.p.wait(timeout=30)
except Exception:
    s.p.terminate()
