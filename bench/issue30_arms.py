#!/usr/bin/env python3
"""Semantic-query latency of upstream zoteus v1.9.0 against v1.10.0, three arms, one index.

The question is upstream issue #30: v1.10.0 shipped a fused cosine loop (#31) and a
two-stage binary-code search (ad7c434), and nobody has measured the pair end to end on a
real index. Three arms decompose the total into its two causes:

  v1.9.0            the baseline, exact scan, unfused cosine
  v1.10.0-exact     ZOTEUS_INDEX_ANN=false -- #31's fusion alone
  v1.10.0-default   both -- fusion plus the two-stage code path

Method notes that are not decoration:

* One index, three COPIES. v1.10.0 writes `vector_codes` into the file on its first
  semantic query; sharing one file would let that write reach the v1.9.0 arm.
* The arms are interleaved query by query, so a thermal excursion or a background job
  cannot land inside one arm and be read as its result.
* Pass 0 is reported separately from the warm passes. On an index built before v1.10.0
  the first semantic query builds every binary code in one pass; reading that as the
  steady state is the single easiest way to make v1.10.0 look bad.
* `zotero_index action:"status"` is read after EVERY query, and its `vectorScan` field
  recorded. A timing taken without it cannot tell "the two-stage did not help" from "the
  two-stage never ran": any doubt about code coverage sends the query back to the exact
  scan by design, and the query still answers.
"""
import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_drive import Server  # noqa: E402

# Every path is an env override with the 2026-08-29 run's value as its default, so the
# driver stays runnable from the repo without carrying a scratch directory in its source.
#   ISSUE30_ROOT        checkouts: <root>/v190/dist, <root>/v1100/dist, <root>/embed
#   ISSUE30_MASTER      the index both versions open (a v1.9.0-schema file with vectors)
#   ISSUE30_ARMS_DIR    where the per-arm COPIES are made
ROOT = Path(os.environ.get("ISSUE30_ROOT", "/home/haduong/.claude/jobs/upstream30-latency"))
MASTER = Path(os.environ.get(
    "ISSUE30_MASTER", "/home/haduong/data/projets/zoteus-bench/issue30/master/search-index.sqlite"))
ARMS_DIR = Path(os.environ.get("ISSUE30_ARMS_DIR", "/home/haduong/data/projets/zoteus-bench/issue30"))
TRANSFORMERS = os.environ.get("ISSUE30_TRANSFORMERS", str(ROOT / "embed"))

ARMS = [
    {"name": "v1.9.0", "dist": ROOT / "v190" / "dist" / "index.js", "sha": "bb414df", "env": {}},
    {"name": "v1.10.0-exact", "dist": ROOT / "v1100" / "dist" / "index.js", "sha": "b132f2d",
     "env": {"ZOTEUS_INDEX_ANN": "false"}},
    {"name": "v1.10.0-default", "dist": ROOT / "v1100" / "dist" / "index.js", "sha": "b132f2d", "env": {}},
]


def percentile(samples: list[float], p: float) -> float:
    """Nearest-rank percentile: an observed sample, never an interpolated one that never
    occurred. Raises on an empty run rather than inventing a plausible-looking 0.0."""
    if not samples:
        raise ValueError("percentile of an empty sample list -- nothing was measured")
    ordered = sorted(samples)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[max(1, min(rank, len(ordered))) - 1]


def summarize(samples: list[float]) -> dict | None:
    if not samples:
        return None
    return {"n": len(samples),
            "min_ms": round(min(samples), 1),
            "p50_ms": round(percentile(samples, 50), 1),
            "p95_ms": round(percentile(samples, 95), 1),
            "max_ms": round(max(samples), 1)}


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


def env_for(arm: dict, data_dir: Path) -> dict:
    return {
        "ZOTEUS_EMBEDDINGS": "local",
        "ZOTEUS_TRANSFORMERS_PATH": TRANSFORMERS,
        "ZOTEUS_DATA_DIR": str(data_dir),
        "ZOTEUS_INDEX_BACKEND": "sqlite",
        "ZOTEUS_INDEX_AUTO_REFRESH": "false",
        "ZOTEUS_INDEX_FULLTEXT": "1",
        **arm["env"],
    }


def start(arm: dict, data_dir: Path) -> Server:
    s = Server(["node", str(arm["dist"])], env_for(arm, data_dir), label=arm["name"])
    s.handshake()
    return s


def status(s: Server) -> dict:
    return payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))


def ask(s: Server, q: str, mode: str, limit: int) -> tuple[float, dict]:
    t = time.perf_counter()
    r = s.call("tools/call", {"name": "zotero_semantic_search",
                              "arguments": {"q": q, "mode": mode, "limit": limit, "auto_build": False}})
    ms = (time.perf_counter() - t) * 1000
    return ms, payload(r)


def read_queries(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf8").splitlines()
            if ln.strip() and not ln.startswith("#")]


def geometry(db: Path) -> dict:
    con = __import__("sqlite3").connect(f"file:{db}?mode=ro", uri=True)
    g = {
        "passages": con.execute("SELECT COUNT(*) FROM passages").fetchone()[0],
        "vectors": con.execute("SELECT COUNT(*) FROM passages WHERE vector IS NOT NULL").fetchone()[0],
        "items": con.execute("SELECT COUNT(*) FROM items").fetchone()[0],
        "vector_bytes_each": con.execute(
            "SELECT length(vector) FROM passages WHERE vector IS NOT NULL LIMIT 1").fetchone()[0],
        "embedder_id": con.execute("SELECT value FROM meta WHERE key='embedderId'").fetchone()[0],
        "index_file_bytes": db.stat().st_size,
    }
    g["dimensions"] = g["vector_bytes_each"] // 4
    g["vector_bytes_total"] = g["vectors"] * g["vector_bytes_each"]
    con.close()
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queries", default=str(
        Path("/home/haduong/CNRS/code/search-works-for-zotero/bench/queries-x2.txt")))
    ap.add_argument("--mode", default="semantic", choices=("semantic", "auto", "keyword"))
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--repeat", type=int, default=5, help="warm passes after the cold pass 0")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    queries = read_queries(Path(a.queries))
    tag = a.mode

    # One copy of the master per arm. Copied fresh every run: an arm that already carries
    # `vector_codes` from a previous run would not be measuring the upgrade path.
    servers = []
    for arm in ARMS:
        d = ARMS_DIR / f"arm-{arm['name']}-{tag}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        shutil.copy2(MASTER, d / "search-index.sqlite")
        arm["data_dir"] = d

    geo = geometry(MASTER)

    for arm in ARMS:
        servers.append(start(arm, arm["data_dir"]))
    time.sleep(2)

    opened = {arm["name"]: status(s) for arm, s in zip(ARMS, servers)}

    records = []   # one per (pass, query, arm)
    notices = []

    for p in range(0, a.repeat + 1):
        for qi, q in enumerate(queries):
            for arm, s in zip(ARMS, servers):
                ms, res = ask(s, q, a.mode, a.limit)
                st = status(s)
                rec = {"pass": p, "qi": qi, "arm": arm["name"], "ms": round(ms, 1),
                       "hits": len(res.get("hits", [])) if isinstance(res, dict) else None,
                       "vectorScan": st.get("vectorScan")}
                if st.get("vectorScanNotice"):
                    rec["vectorScanNotice"] = st["vectorScanNotice"]
                    notices.append({"pass": p, "qi": qi, "arm": arm["name"],
                                    "notice": st["vectorScanNotice"]})
                records.append(rec)
        print(f"pass {p} done", file=sys.stderr)

    # Phase C: restart the two-stage arm on its now-coded file. Its cold pass 0 is then the
    # same work MINUS the code build, which is what makes the build cost a measured
    # difference rather than an inference from the other arms' first queries.
    default_arm = ARMS[2]
    servers[2].stop()
    s2 = start(default_arm, default_arm["data_dir"])
    time.sleep(2)
    recoded = []
    for qi, q in enumerate(queries):
        ms, res = ask(s2, q, a.mode, a.limit)
        st = status(s2)
        recoded.append({"pass": "restart-cold", "qi": qi, "arm": default_arm["name"],
                        "ms": round(ms, 1), "vectorScan": st.get("vectorScan")})
    s2.stop()
    for s in servers[:2]:
        s.stop()

    def rows(arm_name, pred):
        return [r["ms"] for r in records if r["arm"] == arm_name and pred(r)]

    arms_out = {}
    for arm in ARMS:
        n = arm["name"]
        warm = rows(n, lambda r: r["pass"] >= 1)
        cold = rows(n, lambda r: r["pass"] == 0)
        scans = sorted({r["vectorScan"] for r in records if r["arm"] == n})
        warm_scans = sorted({r["vectorScan"] for r in records if r["arm"] == n and r["pass"] >= 1})
        arms_out[n] = {
            "sha": arm["sha"],
            "env": arm["env"] or {"(stock defaults)": ""},
            "warm": summarize(warm),
            "cold_pass0": summarize(cold),
            "first_query_ms": next(r["ms"] for r in records if r["arm"] == n and r["pass"] == 0 and r["qi"] == 0),
            "vectorScan_values_seen": scans,
            "vectorScan_values_warm": warm_scans,
            "status_at_open": opened[n],
        }

    # Per-query warm pairs: median over the warm passes of each query, per arm.
    per_query = []
    for qi, q in enumerate(queries):
        row = {"qi": qi, "query": q}
        for arm in ARMS:
            samples = [r["ms"] for r in records
                       if r["arm"] == arm["name"] and r["pass"] >= 1 and r["qi"] == qi]
            row[arm["name"] + "_p50_ms"] = round(percentile(samples, 50), 1)
        per_query.append(row)

    out = {
        "what": "semantic-query latency, upstream zoteus v1.9.0 vs v1.10.0, on one real index",
        "issue": "https://github.com/oscardvs/zoteus/issues/30",
        "mode": a.mode,
        "limit": a.limit,
        "repetitions": {"cold_passes": 1, "warm_passes": a.repeat, "queries": len(queries),
                        "samples_per_arm_warm": a.repeat * len(queries)},
        "machine": {
            "host": platform.node(),
            "kernel": platform.release(),
            "cpu": subprocess.run(["bash", "-c", "lscpu | sed -n 's/^Model name: *//p'"],
                                  capture_output=True, text=True).stdout.strip(),
            "cores": os.cpu_count(),
            "node": subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip(),
        },
        "geometry": geo,
        "queries_file": a.queries,
        "arms": arms_out,
        "two_stage_code_build": {
            "restart_cold_pass_with_codes_on_disk": summarize([r["ms"] for r in recoded]),
            "restart_cold_first_query_ms": recoded[0]["ms"],
            "notices": notices,
        },
        "per_query_warm_p50": per_query,
        "raw": records,
        "raw_restart": recoded,
    }
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps({k: out[k] for k in ("mode", "geometry")}, indent=2))
    for n, v in arms_out.items():
        print(f"{n:20s} warm p50={v['warm']['p50_ms']:>9} p95={v['warm']['p95_ms']:>9} "
              f"scan={v['vectorScan_values_warm']}")


if __name__ == "__main__":
    main()
