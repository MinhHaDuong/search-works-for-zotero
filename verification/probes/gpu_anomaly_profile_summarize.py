"""Ticket 0481. Summarize an ONNX Runtime session-profiling JSON (Chrome trace-event format,
written by `InferenceSession.endProfiling()` under `enableProfiling: true`) into per-provider
and per-op-type millisecond totals.

Each event with `"cat": "Node"` carries `args.op_name` and, on onnxruntime-node builds that
report it, `args.provider`. Kernel launch/exec events for CUDA ops are also tagged; a run where
every node's provider reads CPUExecutionProvider, or where CUDA nodes carry zero duration, is
the fallback-to-CPU signature this ticket's Action 2/5 look for.

    python3 verification/probes/gpu_anomaly_profile_summarize.py <profile.json>
"""

import argparse
import json
from collections import defaultdict


def summarize(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = events.get("traceEvents", events.get("events", []))

    by_provider_us: dict[str, float] = defaultdict(float)
    by_op_us: dict[str, float] = defaultdict(float)
    by_provider_count: dict[str, int] = defaultdict(int)
    total_node_us = 0.0
    n_node_events = 0
    top_level_cats: dict[str, int] = defaultdict(int)

    for ev in events:
        cat = ev.get("cat", "")
        top_level_cats[cat] += 1
        args = ev.get("args") or {}
        dur = ev.get("dur", 0) or 0
        if cat == "Node":
            n_node_events += 1
            total_node_us += dur
            provider = args.get("provider", "(unknown)")
            op = args.get("op_name", ev.get("name", "(unknown)"))
            by_provider_us[provider] += dur
            by_provider_count[provider] += 1
            by_op_us[op] += dur

    result = {
        "profile_path": path,
        "n_events_total": len(events),
        "n_node_events": n_node_events,
        "cats": dict(top_level_cats),
        "total_node_ms": round(total_node_us / 1000, 3),
        "by_provider_ms": {k: round(v / 1000, 3) for k, v in sorted(by_provider_us.items(), key=lambda kv: -kv[1])},
        "by_provider_node_count": dict(by_provider_count),
        "top_ops_ms": dict(
            sorted(((k, round(v / 1000, 3)) for k, v in by_op_us.items()), key=lambda kv: -kv[1])[:15]
        ),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_json", help="path to the ORT profiling JSON")
    parser.add_argument("--out", help="write the summary here instead of stdout")
    args = parser.parse_args()

    result = summarize(args.profile_json)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
