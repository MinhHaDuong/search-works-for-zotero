#!/usr/bin/env python3
"""Two things the arm table cannot say on its own.

1. THE CODE-BUILD COST, isolated. In the main run the two-stage arm's first query also
   paid a one-time model DOWNLOAD (v1.10.0's 998865e caches the on-device weights under
   the data dir, and every arm got a fresh one), so that number is not the code build.
   Here the data dir starts with the model already cached, and the same first query is
   measured twice: once on a fresh index, where it builds the codes, and once after a
   restart on the file that now carries them. The difference is the build.

2. WHETHER THE FAST ANSWER IS THE SAME ANSWER. A speedup means nothing if the codes
   changed the page. The same twenty queries are put to v1.9.0 and to v1.10.0's two-stage
   path and the returned item lists compared.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_drive import Server  # noqa: E402
from issue30_arms import ARMS, MASTER, TRANSFORMERS, payload, status, read_queries, percentile  # noqa: E402

BASE = Path(os.environ.get("ISSUE30_ARMS_DIR", "/home/haduong/data/projets/zoteus-bench/issue30"))
# A data dir that ALREADY holds the on-device model, so the code-build measurement below
# is not confounded by v1.10.0's model download (998865e caches the weights here).
MODELS = Path(os.environ.get("ISSUE30_MODELS", str(BASE / "models-cache")))


def env_for(arm, data_dir):
    return {"ZOTEUS_EMBEDDINGS": "local", "ZOTEUS_TRANSFORMERS_PATH": TRANSFORMERS,
            "ZOTEUS_DATA_DIR": str(data_dir), "ZOTEUS_INDEX_BACKEND": "sqlite",
            "ZOTEUS_INDEX_AUTO_REFRESH": "false", "ZOTEUS_INDEX_FULLTEXT": "1", **arm["env"]}


def start(arm, data_dir):
    s = Server(["node", str(arm["dist"])], env_for(arm, data_dir), label=arm["name"])
    s.handshake()
    return s


def ask(s, q, mode, limit=10):
    t = time.perf_counter()
    r = s.call("tools/call", {"name": "zotero_semantic_search",
                              "arguments": {"q": q, "mode": mode, "limit": limit, "auto_build": False}})
    return (time.perf_counter() - t) * 1000, payload(r)


def fresh_dir(name: Path):
    if name.exists():
        shutil.rmtree(name)
    name.mkdir(parents=True)
    shutil.copy2(MASTER, name / "search-index.sqlite")
    if MODELS.exists():
        shutil.copytree(MODELS, name / "models")
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default="/home/haduong/CNRS/code/search-works-for-zotero/bench/queries-x2.txt")
    ap.add_argument("--mode", default="semantic")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    queries = read_queries(Path(a.queries))
    default_arm = ARMS[2]
    out = {}

    # --- 1. code build, model already cached ------------------------------------------
    d = fresh_dir(BASE / "codebuild")
    s = start(default_arm, d)
    time.sleep(2)
    t_build, _ = ask(s, queries[0], a.mode)
    st = status(s)
    notice = st.get("vectorScanNotice")
    rest_build = [ask(s, q, a.mode)[0] for q in queries[1:]]
    s.stop()
    time.sleep(1)

    s = start(default_arm, d)          # same dir: vector_codes are now on disk
    time.sleep(2)
    t_coded, _ = ask(s, queries[0], a.mode)
    st2 = status(s)
    rest_coded = [ask(s, q, a.mode)[0] for q in queries[1:]]
    s.stop()

    codes_bytes = None
    con = __import__("sqlite3").connect(f"file:{d / 'search-index.sqlite'}?mode=ro", uri=True)
    codes_bytes = con.execute("SELECT COUNT(*), SUM(length(code)) FROM vector_codes").fetchone()
    con.close()

    out["code_build"] = {
        "first_query_building_codes_ms": round(t_build, 1),
        "first_query_codes_already_on_disk_ms": round(t_coded, 1),
        "difference_ms": round(t_build - t_coded, 1),
        "upstream_own_notice": notice,
        "vectorScan_after_first_query": st.get("vectorScan"),
        "vectorScan_after_restart": st2.get("vectorScan"),
        "rest_of_pass_after_build_p50_ms": round(percentile(rest_build, 50), 1),
        "rest_of_pass_after_restart_p50_ms": round(percentile(rest_coded, 50), 1),
        "vector_codes_rows": codes_bytes[0],
        "vector_codes_bytes": codes_bytes[1],
        "note": ("Both first queries load the on-device model from the data dir's cache, so the "
                 "difference is the code build and the write, not the model. The main run's "
                 "first-query figures are NOT this: there each v1.10.0 arm also downloaded the "
                 "model into its fresh data dir."),
    }

    # --- 2. do the arms return the same page? -----------------------------------------
    dirs, servers = [], []
    for arm in (ARMS[0], ARMS[2]):
        dd = fresh_dir(BASE / f"agree-{arm['name']}")
        dirs.append(dd)
        servers.append(start(arm, dd))
    time.sleep(2)
    rows = []
    for q in queries:
        page = {}
        for arm, srv in zip((ARMS[0], ARMS[2]), servers):
            _, res = ask(srv, q, a.mode)
            page[arm["name"]] = [h["itemKey"] for h in res.get("hits", [])]
        base, two = page["v1.9.0"], page["v1.10.0-default"]
        rows.append({"query": q,
                     "v190_top10": base,
                     "v1100_top10": two,
                     "overlap": len(set(base) & set(two)),
                     "same_first": bool(base and two and base[0] == two[0]),
                     "identical_order": base == two})
    for srv in servers:
        srv.stop()
    n = len(rows)
    out["agreement"] = {
        "what": "top-10 item lists, mode:semantic, v1.9.0 exact scan vs v1.10.0 two-stage",
        "queries": n,
        "mean_overlap_at_10": round(sum(r["overlap"] for r in rows) / n, 2),
        "same_first_hit": sum(1 for r in rows if r["same_first"]),
        "identical_order": sum(1 for r in rows if r["identical_order"]),
        "per_query": rows,
    }
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_query"}
                      for k, v in out.items()}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
