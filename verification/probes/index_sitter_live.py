"""Live single-attachment reindex probe; see verification/INDEX-SITTER-LIVE.md.

Uses the installed full-text plugin. It changes the selected attachment's derived
extraction/index state. The observation deadline neither cancels nor retries work.
"""

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.request

BASE = "http://localhost:23119"
DATA = Path("/home/haduong/data/Zotero")


def request(path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=5) as response:
        result = json.load(response)
    return {"seconds": time.monotonic() - start, "body": result}


def snapshot(key):
    rows = None
    files = {}
    directory = DATA / "storage" / key
    if directory.exists():
        for path in directory.iterdir():
            if path.is_file():
                stat = path.stat()
                entry = {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
                if path.name in (".zotero-ft-cache", ".zotero-sdt-cache"):
                    with path.open("rb") as stream:
                        entry["sha256"] = hashlib.file_digest(
                            stream, "sha256"
                        ).hexdigest()
                files[path.name] = entry
    return {"rows": rows, "files": files}


def resources(pid):
    status = Path(f"/proc/{pid}/status").read_text()
    stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    memory = Path("/proc/meminfo").read_text()
    return {
        "process": {
            line.split(":")[0]: line.split(":", 1)[1].strip()
            for line in status.splitlines()
            if line.startswith(("VmRSS:", "VmSwap:", "Threads:"))
        },
        "cpu_ticks": int(stat[11]) + int(stat[12]),
        "memory": {
            line.split(":")[0]: line.split(":", 1)[1].strip()
            for line in memory.splitlines()
            if line.startswith(("MemAvailable:", "SwapFree:"))
        },
        "pressure": {
            kind: Path(f"/proc/pressure/{kind}").read_text().strip()
            for kind in ("cpu", "memory", "io")
        },
    }


def main():
    global DATA
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["inspect", "run"])
    ap.add_argument("--key")
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--output")
    ap.add_argument("--observe-seconds", type=int, default=300)
    args = ap.parse_args()
    DATA = args.data_dir
    if args.mode == "inspect":
        caches = []
        for directory in (DATA / "storage").iterdir():
            cache = directory / ".zotero-ft-cache"
            if cache.exists():
                caches.append({"key": directory.name, "bytes": cache.stat().st_size})
        print(
            json.dumps(
                {
                    "largest": sorted(
                        caches, key=lambda row: row["bytes"], reverse=True
                    )[:12],
                    "resources": resources(args.pid),
                },
                indent=2,
            )
        )
        return
    if not args.key or not args.output:
        ap.error("run requires --key and --output")
    started = time.monotonic()
    with open(args.output, "x") as out:

        def emit(kind, **values):
            entry = {
                "kind": kind,
                "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "elapsed": time.monotonic() - started,
                **values,
            }
            out.write(json.dumps(entry) + "\n")
            out.flush()
            if kind != "sample":
                print(json.dumps(entry), flush=True)

        status_path = "/search-works/fulltext/status?keys=" + args.key
        emit(
            "before",
            snapshot=snapshot(args.key),
            status=request(status_path),
            resources=resources(args.pid),
        )
        paths = {"status": status_path, "api": "/api/users/0/items?limit=1&format=json"}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:

            def sample(phase):
                futures = {
                    name: pool.submit(request, path) for name, path in paths.items()
                }
                entry = {"phase": phase, "resources": resources(args.pid)}
                for name, future in futures.items():
                    try:
                        result = future.result()
                        if name == "api":
                            result.pop("body")
                        entry[name] = result
                    except Exception as error:
                        entry[name] = {"error": str(error)}
                cache = DATA / "storage" / args.key / ".zotero-ft-cache"
                if cache.exists():
                    st = cache.stat()
                    entry["cache"] = {"bytes": st.st_size, "mtime_ns": st.st_mtime_ns}
                emit("sample", **entry)
                return entry

            for _ in range(5):
                sample("baseline")
                time.sleep(1)
            emit(
                "dispatch",
                response=request(
                    "/search-works/fulltext/reindex", {"keys": [args.key]}
                ),
            )
            deadline = time.monotonic() + args.observe_seconds
            idle_count = 0
            while time.monotonic() < deadline:
                entry = sample("work")
                body = entry.get("status", {}).get("body", {})
                idle_count = idle_count + 1 if body.get("busy") is False else 0
                if idle_count >= 3:
                    break
                time.sleep(1)
            else:
                emit(
                    "observation_window_ended",
                    note="No cancellation or retry issued; job may still be running",
                )
            for _ in range(3):
                sample("after")
                time.sleep(1)
        emit(
            "after",
            snapshot=snapshot(args.key),
            status=request(status_path),
            resources=resources(args.pid),
        )


if __name__ == "__main__":
    main()
