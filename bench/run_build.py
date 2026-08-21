#!/usr/bin/env python3
"""Ticket 0003: full-library FTS5 index build, timed and RSS-measured.

Peak RSS is read from /proc/<pid>/status VmHWM (kernel high-water mark, exact),
not sampled from ps (which can miss a peak between polls). VmRSS is sampled too,
for the shape of the curve.
"""
import json, os, subprocess, sys, time

sys.path.insert(0, "/home/haduong/CNRS/projets/actifs/zoteus-fts5/bench")
from mcp_drive import Server  # noqa: E402

SERVER = "/home/haduong/CNRS/projets/actifs/zoteus-fts5/fork/dist/index.js"
DATA_DIR = "/home/haduong/.zoteus-bench-0003"
OUT = "/tmp/zbench0003"
POLL = 10.0
MAX_WAIT = 6 * 3600.0


def payload(resp):
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


def procmem(pid):
    out = {}
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                for k in ("VmRSS:", "VmHWM:", "VmSize:", "VmPeak:"):
                    if line.startswith(k):
                        out[k.rstrip(":")] = int(line.split()[1])  # kB
    except FileNotFoundError:
        pass
    return out


def dirlist(path):
    return {f: os.path.getsize(os.path.join(path, f))
            for f in sorted(os.listdir(path))
            if os.path.isfile(os.path.join(path, f))}


def main():
    env = {
        "ZOTEUS_EMBEDDINGS": "off",
        "ZOTEUS_INDEX_FULLTEXT": "1",
        "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": "0",     # no character cap
        "ZOTEUS_INDEX_MAX_ITEMS": "1000000",        # effectively no item cap
        "ZOTEUS_SEARCH_BACKEND": "sqlite",
        "ZOTEUS_DATA_DIR": DATA_DIR,
        "NODE_OPTIONS": "",                          # NO --max-old-space-size
    }
    logf = open(f"{OUT}/build.log", "a", buffering=1)

    def say(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")

    say(f"env: {json.dumps(env)}")
    s = Server(["node", SERVER], env, MAX_WAIT)
    pid = s.p.pid
    say(f"server pid {pid}")
    s.handshake()

    t0 = time.monotonic()
    start = payload(s.call("tools/call", {"name": "zotero_index",
                                          "arguments": {"action": "build", "fulltext": True}}))
    say("build kicked off: " + json.dumps(start, ensure_ascii=False)[:600])

    samples = open(f"{OUT}/rss_samples.jsonl", "a", buffering=1)
    last, final = None, None
    while time.monotonic() - t0 < MAX_WAIT:
        time.sleep(POLL)
        mem = procmem(pid)
        if not mem:
            say("!! server process gone (check build.log tail for a crash)")
            break
        st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
        el = time.monotonic() - t0
        samples.write(json.dumps({"t": round(el, 1), **mem,
                                  "state": st.get("state"),
                                  "itemsFetched": st.get("itemsFetched"),
                                  "documents": st.get("documents"),
                                  "fulltextPassages": st.get("fulltextPassages")}) + "\n")
        key = (st.get("state"), st.get("itemsFetched"), st.get("documents") and st.get("documents") // 1000)
        if key != last:
            say(f"[{el:7.0f}s] RSS {mem.get('VmRSS',0)/1024:.0f}M HWM {mem.get('VmHWM',0)/1024:.0f}M "
                + json.dumps(st, ensure_ascii=False)[:400])
            last = key
        final = st
        state = st.get("state")
        if state in ("done", "error"):
            break
        if state == "idle" and el > 90:
            say("!! state fell back to idle after 90s — treating as terminal")
            break

    elapsed = time.monotonic() - t0
    mem = procmem(pid)
    result = {
        "elapsed_s": round(elapsed, 1),
        "peak_rss_kB_VmHWM": mem.get("VmHWM"),
        "final_rss_kB_VmRSS": mem.get("VmRSS"),
        "peak_vsize_kB_VmPeak": mem.get("VmPeak"),
        "status": final,
        "files_before_shutdown": dirlist(DATA_DIR),
    }
    say("RESULT " + json.dumps(result, ensure_ascii=False))
    with open(f"{OUT}/build_result.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Graceful shutdown so SQLite checkpoints cleanly.
    try:
        s.p.stdin.close()
    except Exception:
        pass
    try:
        s.p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        say("stdin close did not end the server; sending SIGTERM")
        s.p.terminate()
        try:
            s.p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            s.p.kill()
    say(f"server exit code {s.p.returncode}")
    say("files after shutdown: " + json.dumps(dirlist(DATA_DIR)))


if __name__ == "__main__":
    main()
