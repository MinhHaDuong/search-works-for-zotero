#!/usr/bin/env python3
"""Run the same keyword queries against a Zoteus index on a chosen backend.

Emits one JSON document on stdout: per query, the ordered itemKey list, plus the
server's startup peak RSS (VmHWM) so a migration at startup is measured too.
"""
import argparse
import json
import logging
import math
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
    """Peak RSS from the kernel high-water mark. Raises rather than returning 0.

    It used to swallow OSError and return 0, which made an unreadable /proc entry
    indistinguishable from a measurement of zero. Three of the five call sites take a
    max(), where a spurious 0 is harmless; two record the value directly into the
    artifact, and there a failed read would have been published as a memory figure. The
    numbers this harness exists to produce are exactly the ones that must not be
    silently invented, so the failure is raised and the run stops.
    """
    with open(f"/proc/{pid}/status") as fh:
        for line in fh:
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    raise RuntimeError(f"/proc/{pid}/status has no VmHWM line — cannot report peak RSS")


def percentile(samples: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest sample at or above p% of the sorted run.

    Nearest-rank and not an interpolating variant, because the figure this feeds is a
    latency budget compared against a threshold — the honest answer to "what did a slow
    query actually cost" is an observed sample, not a weighted average of two that
    straddle it. Interpolation would report a duration that never occurred, and at the
    small sample counts this harness runs (20 queries x a few passes) it would sit
    systematically below the observed tail.

    Raises on an empty run rather than returning 0.0: a p95 of zero is a plausible-looking
    number, and the whole point of this module is that a measurement must never be
    silently invented (same reasoning as vmhwm_kb above).
    """
    if not samples:
        raise ValueError("percentile of an empty sample list — nothing was measured")
    ordered = sorted(samples)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[max(1, min(rank, len(ordered))) - 1]


def summarize(samples: list[float]) -> dict:
    """The latency block for one population of samples. Empty population -> None."""
    if not samples:
        return None
    return {"n": len(samples),
            "min_ms": round(min(samples), 1),
            "p50_ms": round(percentile(samples, 50), 1),
            "p95_ms": round(percentile(samples, 95), 1),
            "max_ms": round(max(samples), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--data-dir", required=True)
    # Upstream vocabulary (>= v1.7.0): the JSON backend is "memory". The old
    # "json" value must fail loudly here: upstream's config warn-and-defaults
    # unknown knob values to "auto" (v1.7.3), so a stale value would silently
    # measure auto and report it as whatever the flag said (ticket 0030).
    ap.add_argument("--backend", required=True, choices=("sqlite", "memory"))
    ap.add_argument("--queries-file", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--out", required=True)
    # Default EMPTY. Whether the server survives on a stock heap is itself an
    # exit criterion of ticket 0003, so the flag under test must never be the
    # default -- a run with defaults would pass the criterion without
    # exercising it. Pass it explicitly when driving the JSON backend, which
    # genuinely needs it.
    ap.add_argument("--node-options", default="")
    # Latency. Default 1 keeps the pre-existing single-pass behaviour of every caller
    # that predates the timing block. A p95 wants more: with 20 queries answered once
    # each, the 95th percentile IS the second-slowest query, so the figure reports which
    # query is slowest rather than how slow a query is. Pass --repeat for a real
    # population, and read p95 off the warm passes — pass 0 pays the page-cache and
    # FTS5-segment first touch, which is a different question from steady-state latency.
    ap.add_argument("--repeat", type=int, default=1,
                    help="timed passes over the whole query list; pass 0 is the cold one")
    a = ap.parse_args()
    if a.repeat < 1:
        ap.error("--repeat must be at least 1")

    env = {"ZOTEUS_EMBEDDINGS": "off",
           "ZOTEUS_INDEX_FULLTEXT": "1",
           "ZOTEUS_DATA_DIR": a.data_dir,
           "ZOTEUS_INDEX_BACKEND": a.backend,
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

    out = {"backend": a.backend, "limit": a.limit, "repeat": a.repeat,
           "handshake_s": round(handshake_s, 2),
           "ready_s": round(ready_s, 2), "peak_rss_kb_after_start": peak_after_start,
           "status": st, "queries": {}}

    cold, warm = [], []
    for pass_no in range(a.repeat):
        for q in queries:
            t = time.monotonic()
            resp = s.call("tools/call", {"name": "zotero_semantic_search",
                                          "arguments": {"q": q, "mode": "keyword",
                                                        "limit": a.limit,
                                                        "auto_build": False}})
            dt_ms = (time.monotonic() - t) * 1000
            r = payload(resp)
            if resp.get("result", {}).get("isError"):
                raise SystemExit(f"tool error on query {q!r}: "
                                 f"{json.dumps(resp['result'])[:800]}")
            hits = r.get("hits", [])
            (cold if pass_no == 0 else warm).append(dt_ms)
            # Hits are recorded from the cold pass and never overwritten: the result set
            # must not depend on the pass, and pinning it to one pass makes a drift
            # visible as a changed artifact rather than hiding it behind a last-write-wins.
            if pass_no == 0:
                keys = []
                for h in hits:
                    if isinstance(h, dict):
                        keys.append(h.get("itemKey") or h.get("key") or h.get("item_key"))
                out["queries"][q] = {
                    "n": len(hits), "keys": keys, "latency_ms": [],
                    "hits": [{"itemKey": h.get("itemKey"), "score": h.get("score"),
                              "source": h.get("source"), "title": h.get("title")}
                             for h in hits if isinstance(h, dict)]}
            elif len(hits) != out["queries"][q]["n"]:
                raise SystemExit(f"query {q!r} returned {len(hits)} hits on pass "
                                 f"{pass_no} but {out['queries'][q]['n']} on the cold "
                                 f"pass — the index moved under the measurement")
            out["queries"][q]["latency_ms"].append(round(dt_ms, 1))
            log.info("[%s p%d] %-40s -> %d hits, %.1f ms",
                     a.backend, pass_no, q[:40], len(hits), dt_ms)

    # Three populations, reported separately and never silently pooled. The decision rule
    # (DESIGN §3) is about steady-state query cost, so it reads `warm`; `cold` is kept
    # because a first-touch tail an order of magnitude worse is itself a finding, and
    # `all` is kept so nobody has to recombine them by hand to check.
    out["latency"] = {"cold_pass": summarize(cold),
                      "warm_passes": summarize(warm),
                      "all_passes": summarize(cold + warm)}
    out["peak_rss_kb_final"] = vmhwm_kb(s.p.pid)
    with open(a.out, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    log.info("wrote %s", a.out)
    s.p.terminate()


if __name__ == "__main__":
    main()
