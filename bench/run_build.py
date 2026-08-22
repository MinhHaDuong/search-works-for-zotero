#!/usr/bin/env python3
"""Build a Zoteus search index on a chosen backend, timing it and recording true peak RSS.

Peak RSS is read from /proc/<pid>/status VmHWM (kernel high-water mark), not sampled
with ps: a sampler misses a spike between polls, VmHWM cannot.
"""
import argparse
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_drive import Server  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build")


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


def dir_listing(path: str) -> dict[str, int]:
    out = {}
    for root, _, files in os.walk(path):
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, path)] = os.path.getsize(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--backend", default="json")
    ap.add_argument("--poll", type=float, default=15.0)
    ap.add_argument("--max-wait", type=float, default=5400.0)
    ap.add_argument("--max-items", default="5000")
    ap.add_argument("--max-chars", default="200000")
    # Default EMPTY. Whether the server survives on a stock heap is itself an
    # exit criterion of ticket 0003, so the flag under test must never be the
    # default -- a run with defaults would pass the criterion without
    # exercising it. Pass it explicitly when driving the JSON backend, which
    # genuinely needs it.
    ap.add_argument("--node-options", default="")
    ap.add_argument("--build", action="store_true", help="kick off a build; otherwise only start+status")
    # Vectors are OFF by default for the same reason --node-options is empty: the storage
    # comparison this harness was written for is keyword-only, and an embedder silently
    # turned on would change both the wall clock and the on-disk size it reports. Ticket
    # 0008 needs the opposite, so it is a flag rather than an edit.
    ap.add_argument("--embeddings", default="off", help="ZOTEUS_EMBEDDINGS: off | local | openai | gemini")
    ap.add_argument("--transformers-path", default="", help="ZOTEUS_TRANSFORMERS_PATH for a non-bundled model runtime")
    a = ap.parse_args()

    env = {"ZOTEUS_EMBEDDINGS": a.embeddings,
           "ZOTEUS_INDEX_FULLTEXT": "1",
           "ZOTEUS_DATA_DIR": a.data_dir,
           "ZOTEUS_SEARCH_BACKEND": a.backend,
           "ZOTEUS_INDEX_MAX_ITEMS": a.max_items,
           "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": a.max_chars,
           "ZOTEUS_INDEX_AUTO_REFRESH": "false",
           "NODE_OPTIONS": a.node_options}
    if a.transformers_path:
        env["ZOTEUS_TRANSFORMERS_PATH"] = a.transformers_path
    t_launch = time.monotonic()
    s = Server(["node", a.server], env, a.max_wait)
    s.handshake()
    log.info("[startup] handshake at %.1f s, pid %d", time.monotonic() - t_launch, s.p.pid)

    if not a.build:
        st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
        log.info("status: %s", json.dumps(st, ensure_ascii=False)[:2000])
        log.info("RESULT %s", json.dumps({"peak_rss_kb": vmhwm_kb(s.p.pid),
                                          "startup_s": round(time.monotonic() - t_launch, 2),
                                          "files": dir_listing(a.data_dir)}))
        s.p.terminate()
        return

    t0 = time.monotonic()
    start = payload(s.call("tools/call", {"name": "zotero_index",
                                          "arguments": {"action": "build", "fulltext": True}}))
    log.info("build kicked off: %s", json.dumps(start, ensure_ascii=False)[:600])

    last, peak = None, 0
    while time.monotonic() - t0 < a.max_wait:
        time.sleep(a.poll)
        peak = max(peak, vmhwm_kb(s.p.pid))
        st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
        state = json.dumps(st, ensure_ascii=False)
        if state != last:
            log.info("[%6.0fs peak %.2f GB] %s", time.monotonic() - t0, peak / 1048576, state[:500])
            last = state
        status = str(st.get("status") or st.get("state") or "")
        if status and status not in {"running", "building", "in_progress", "pending"}:
            break

    elapsed = time.monotonic() - t0
    peak = max(peak, vmhwm_kb(s.p.pid))
    final = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    log.info("RESULT %s", json.dumps({"elapsed_s": round(elapsed, 1),
                                      "peak_rss_kb": peak,
                                      "status": final,
                                      "files": dir_listing(a.data_dir)}, ensure_ascii=False))
    s.p.terminate()


if __name__ == "__main__":
    main()
