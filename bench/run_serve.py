#!/usr/bin/env python3
"""Ticket 0003 phase 2: restart the server plain (no heap flag) on the built DB,
confirm it opens without rebuilding, and time real keyword queries."""
import json, sys, time

sys.path.insert(0, "/home/haduong/CNRS/projets/actifs/zoteus-fts5/bench")
from mcp_drive import Server  # noqa: E402

SERVER = "/home/haduong/CNRS/projets/actifs/zoteus-fts5/fork/dist/index.js"
DATA_DIR = "/home/haduong/.zoteus-bench-0003"

QUERIES = ["carbon tax revenue recycling", "biomass energy Vietnam",
           "integrated assessment model uncertainty", "carbon capture and storage cost"]


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


def procmem(pid):
    out = {}
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            for k in ("VmRSS:", "VmHWM:"):
                if line.startswith(k):
                    out[k.rstrip(":")] = int(line.split()[1])
    return out


def main():
    env = {"ZOTEUS_EMBEDDINGS": "off", "ZOTEUS_INDEX_FULLTEXT": "1",
           "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": "0", "ZOTEUS_INDEX_MAX_ITEMS": "1000000",
           "ZOTEUS_SEARCH_BACKEND": "sqlite", "ZOTEUS_DATA_DIR": DATA_DIR,
           "NODE_OPTIONS": ""}
    out = {"env": env, "queries": []}
    t_boot = time.monotonic()
    s = Server(["node", SERVER], env, 600)
    s.handshake()
    out["boot_to_handshake_s"] = round(time.monotonic() - t_boot, 3)
    pid = s.p.pid

    st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    out["status_on_restart"] = st
    out["rss_after_open_kB"] = procmem(pid)
    print("status on restart:", json.dumps(st, ensure_ascii=False))
    print("rss after open:", out["rss_after_open_kB"])

    for q in QUERIES:
        t = time.monotonic()
        r = s.call("tools/call", {"name": "zotero_semantic_search",
                                  "arguments": {"q": q, "mode": "keyword", "limit": 10}})
        dt = time.monotonic() - t
        p = payload(r)
        hits = p.get("results") or p.get("hits") or []
        rec = {"q": q, "latency_ms": round(dt * 1000, 1), "n_results": len(hits),
               "first": (hits[0] if hits else None),
               "raw_keys": sorted(p.keys()) if isinstance(p, dict) else None}
        out["queries"].append(rec)
        print(f"{dt*1000:8.1f} ms  n={len(hits):2d}  {q}")

    # second pass: warm latency
    for q in QUERIES:
        t = time.monotonic()
        s.call("tools/call", {"name": "zotero_semantic_search",
                              "arguments": {"q": q, "mode": "keyword", "limit": 10}})
        out["queries"].append({"q": q, "pass": "warm",
                               "latency_ms": round((time.monotonic() - t) * 1000, 1)})

    out["status_after_queries"] = payload(s.call("tools/call",
        {"name": "zotero_index", "arguments": {"action": "status"}}))
    out["rss_after_queries_kB"] = procmem(pid)
    print("rss after queries:", out["rss_after_queries_kB"])

    with open("/tmp/zbench0003/serve_result.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    try:
        s.p.stdin.close(); s.p.wait(timeout=30)
    except Exception:
        s.p.terminate()


if __name__ == "__main__":
    main()
