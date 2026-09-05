"""Summarize raw Index Sitter probe JSONL without issuing Zotero requests."""

import argparse
import json
from pathlib import Path
import statistics


def summarize(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    before = next(row for row in rows if row["kind"] == "before")
    dispatch = next(row for row in rows if row["kind"] == "dispatch")
    after = next((row for row in reversed(rows) if row["kind"] == "after"), None)
    samples = [row for row in rows if row["kind"] == "sample"]
    original = before["snapshot"]["files"][".zotero-ft-cache"]
    changed = [
        row
        for row in samples
        if row.get("cache", {}).get("mtime_ns") != original["mtime_ns"]
    ]
    unchanged = [
        row
        for row in samples
        if row.get("cache", {}).get("mtime_ns") == original["mtime_ns"]
    ]
    result = {
        "artifact": path.name,
        "finished": after is not None and after["status"]["body"].get("busy") is False,
        "dispatch_utc": dispatch["utc"],
        "target": before["status"]["body"]["items"][0],
        "peak_main_process_rss_mib": max(
            int(row["resources"]["process"]["VmRSS"].split()[0]) for row in samples
        )
        / 1024,
        "minimum_host_available_mib": min(
            int(row["resources"]["memory"]["MemAvailable"].split()[0])
            for row in samples
        )
        / 1024,
        "latency": {},
    }
    for phase in ("baseline", "work", "after"):
        selected = [row for row in samples if row["phase"] == phase]
        result["latency"][phase] = {}
        for channel in ("status", "api"):
            times = [
                row[channel]["seconds"] for row in selected if "seconds" in row[channel]
            ]
            result["latency"][phase][channel] = {
                "samples": len(times),
                "errors": sum("error" in row[channel] for row in selected),
                "median_s": statistics.median(times) if times else None,
                "maximum_s": max(times, default=None),
            }
    if changed:
        result["first_cache_change_observed_s"] = (
            changed[0]["elapsed"] - dispatch["elapsed"]
        )
        result["last_unchanged_cache_observed_s"] = max(
            row["elapsed"] - dispatch["elapsed"]
            for row in unchanged
            if row["elapsed"] < changed[0]["elapsed"]
        )
    if after:
        result["cache_hash_unchanged"] = (
            original["sha256"]
            == after["snapshot"]["files"][".zotero-ft-cache"]["sha256"]
        )
        result["end_status"] = after["status"]["body"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps([summarize(path) for path in args.paths], indent=2) + "\n"
    if args.output:
        with args.output.open("x") as stream:
            stream.write(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
