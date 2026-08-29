#!/usr/bin/env python3
"""Fold the probe matrix into one table, with cosines against the no-options run.

Vectors are L2-normalised by the probe's pooling call, so the dot product IS the
cosine. The baseline is `no-options` — today's shipped call — because the question
every row answers is "does this option change what the user gets today?".
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ORDER = [
    "no-options",
    "device-cpu",
    "device-auto",
    "device-auto-q8",
    "dtype-q8",
    "dtype-fp16",
    "dtype-q7",
]


def load(label: str) -> dict | None:
    path = HERE / f"{label}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def main() -> int:
    runs = {label: load(label) for label in ORDER}
    base = runs.get("no-options")
    if base is None or not base.get("ok"):
        print("no usable baseline run", file=sys.stderr)
        return 1

    rows = []
    for label in ORDER:
        run = runs.get(label)
        if run is None:
            continue
        if run["ok"]:
            cos = cosine(base["vector"], run["vector"])
            rows.append((label, json.dumps(run["options"]), "loads", f"{cos:.6f}".replace(".", ","), str(run["dim"])))
        else:
            rows.append((label, json.dumps(run["options"]), "THROWS", "—", run["error"][:70]))

    width = [max(len(r[i]) for r in rows) for i in range(5)]
    header = ("variant", "options", "outcome", "cosine", "dim / error")
    width = [max(w, len(h)) for w, h in zip(width, header, strict=True)]
    line = "  ".join(h.ljust(w) for h, w in zip(header, width, strict=True))
    print(line)
    print("  ".join("-" * w for w in width))
    for row in rows:
        print("  ".join(c.ljust(w) for c, w in zip(row, width, strict=True)))

    meta = base
    print()
    print(f"transformers {meta['transformers']}  {meta['platform']}  node {meta['node']}  model {meta['model']}")

    # One artifact the prose can be checked against. The per-variant files hold 384-float
    # vectors; what any sentence actually quotes is a cosine and an outcome.
    summary = {
        "transformers": meta["transformers"],
        "platform": meta["platform"],
        "node": meta["node"],
        "model": meta["model"],
        "baseline": "no-options",
        "variants": {
            label: (
                {"loads": True, "cosine_vs_no_options": cosine(base["vector"], run["vector"]), "dim": run["dim"]}
                if run["ok"]
                else {"loads": False, "error": run["error"]}
            )
            for label, run in runs.items()
            if run is not None
        },
    }
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
