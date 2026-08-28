#!/usr/bin/env python3
"""Assemble one rung artifact: measurements + full environment provenance."""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
import datetime


def dirsizes(path):
    out = {}
    if not os.path.isdir(path):
        return out
    for root, _, files in os.walk(path):
        for f in files:
            p = os.path.join(root, f)
            try:
                out[os.path.relpath(p, path)] = os.path.getsize(p)
            except OSError:
                pass
    return out


def mtime_iso(path: str) -> str | None:
    """Server mtime as provenance, or None when the path is absent.

    A missing build is a gap in the record, not a reason to lose the whole
    measurement -- the artifact is written after a run that already happened.
    """
    if not path:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(path)))
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rung", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--max-items", required=True)
    ap.add_argument("--max-chars", required=True)
    ap.add_argument("--node-options", required=True)
    ap.add_argument("--server", default="",
                    help="path to the built server rung.sh drove; recorded as provenance")
    ap.add_argument("--build-log", default="")
    ap.add_argument("--atrest-json", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    rec = {
        "rung": a.rung,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": a.note,
        "env": {
            "node_version": subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip(),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "NODE_OPTIONS": a.node_options,
            "ZOTEUS_INDEX_BACKEND": "memory",
            "ZOTEUS_INDEX_MAX_ITEMS": a.max_items,
            "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": a.max_chars,
            "ZOTEUS_INDEX_FULLTEXT": "1",
            "ZOTEUS_EMBEDDINGS": "off",
            "ZOTEUS_INDEX_AUTO_REFRESH": "false",
            "ZOTEUS_DATA_DIR": a.data_dir,
            "server": a.server,
            "server_mtime": mtime_iso(a.server),
            "instrument": "/proc/<pid>/status VmHWM (kernel high-water mark)",
            "wall_clock_contaminated": "yes -- another agent ran tests on this machine concurrently; VmHWM is per-process and unaffected",
        },
        "files": dirsizes(a.data_dir),
    }

    if a.build_log and os.path.exists(a.build_log):
        lines = open(a.build_log, errors="replace").read().splitlines()
        rec["build_log_tail"] = lines[-40:]
        res = [ln for ln in lines if "RESULT " in ln]
        if res:
            rec["build"] = json.loads(res[-1].split("RESULT ", 1)[1])
            k = rec["build"].get("peak_rss_kb", 0)
            rec["build_peak_rss_kb"] = k
            rec["build_peak_rss_mib"] = round(k / 1024, 1)
        else:
            rec["build"] = None
            rec["build_failed"] = True

    if a.atrest_json and os.path.exists(a.atrest_json):
        d = json.load(open(a.atrest_json))
        rec["atrest"] = d
        k = d.get("peak_rss_kb_final", 0)
        rec["atrest_peak_rss_kb"] = k
        rec["atrest_peak_rss_mib"] = round(k / 1024, 1)
        rec["atrest_after_start_kb"] = d.get("peak_rss_kb_after_start")
        rec["atrest_after_start_mib"] = round(d.get("peak_rss_kb_after_start", 0) / 1024, 1)
        rec["status"] = d.get("status")
        rec["startup_s"] = d.get("ready_s")

    idx = rec["files"].get("search-index.json")
    if idx:
        rec["index_bytes"] = idx
        rec["index_mib"] = round(idx / 1048576, 1)

    with open(a.out, "w") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in rec.items()
                      if k in ("rung", "index_mib", "build_peak_rss_mib",
                               "atrest_peak_rss_mib", "startup_s")}, indent=2))


if __name__ == "__main__":
    main()
