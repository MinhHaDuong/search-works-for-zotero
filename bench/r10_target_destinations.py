#!/usr/bin/env python3
"""Name the destinations a run reaches for, on both arms, as an OBSERVATION.

`SPEC.md` §3 R10 is the clause and `bench/acceptance/` is where it is asserted.
This script asserts nothing. It exists because of one property of the assertion's
instrument that no amount of care inside the layer can remove:

**Inside a network namespace with no route, a destination has no name.** A run
that reaches for a hostname dies at name resolution, and what the tracer sees is
a `connect` to the stub resolver on loopback — `127.0.0.53:53`, the same three
numbers whether the target was asking for its own backend or for a font. The
`dns` detector counts those, correctly, and it is the detector that keeps the
assertion honest. But it cannot say WHICH name, so two runs that differ entirely
in where they were trying to go produce the same `destinations` list and differ
only in a count. A count is not a finding when the arena state moves it by 7x on
its own.

So this reads the other arm. With the route intact, resolution succeeds and the
addresses are real, and the difference between two shared arms — the host
application alone, and the same host with a target installed — is what names the
target's own upstreams. That difference is the observation this script produces.

**Why running an arm with a route is defensible here and is NOT the assertion.**
`assertions.check_no_egress` deliberately never runs its subject net-shared:
observing no egress on a machine that has a route asserts the default rather
than the clause. The inverse is what is done here — the point is precisely to
see what leaves — and it is an observation carried beside the verdict, never a
verdict. The caller is responsible for the conditions that make it safe to take:
an empty library and no credentials, so that nothing a user owns can leave. Those
conditions are recorded in the artifact rather than assumed, because a reader
cannot otherwise tell this from a measurement taken on somebody's real library.

It holds no target's name: it runs an argv, exactly as `sandbox.py` does.
"""

import argparse
import json
import os
import socket
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acceptance import sandbox  # noqa: E402


def destinations(result) -> list[dict]:
    """Every distinct destination the run named, with a count and a reverse name.

    The reverse lookup is best effort and is labelled as such: a PTR record is
    not proof of who owns an address, and an address with none is not thereby
    innocent. It is here so a reader is not left comparing two lists of octets.
    """
    rows = []
    counted = Counter((a.detector, a.address, a.port) for a in result.attempts)
    for (detector, address, port), count in sorted(counted.items(), key=lambda r: -r[1]):
        name = None
        if detector == "off_machine":
            try:
                name = socket.gethostbyaddr(address)[0]
            except OSError:
                name = None
        rows.append({"detector": detector, "address": address, "port": port,
                     "attempts": count, "reverse_name": name,
                     "destination": f"{address}:{port}/{detector}"})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", required=True,
                    help="what this cell is, for the artifact's reader")
    ap.add_argument("--output", required=True)
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--conditions", default="",
                    help="the conditions that make a net-shared arm safe to take")
    ap.add_argument("--settle", type=float, default=10.0,
                    help="seconds between the two arms, so one's process is gone")
    ap.add_argument("--arm", choices=("both", "shared", "isolated"), default="both",
                    help=("which arm to run. `both` reuses one command and therefore "
                          "one state directory, so the second arm sees whatever the "
                          "first left; run the arms separately against fresh state "
                          "when the subject's own first-run work is what is being "
                          "compared"))
    ap.add_argument("--env", action="append", default=[], metavar="KEY=VALUE",
                    help="environment overrides for the run; repeatable")
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("argv", nargs=argparse.REMAINDER,
                    help="-- then the command to run")
    a = ap.parse_args()
    argv = [x for x in a.argv if x != "--"]
    if not argv:
        ap.error("give the command to run after --")

    env = dict(os.environ)
    for pair in a.env:
        key, sep, value = pair.partition("=")
        if not sep:
            ap.error(f"--env wants KEY=VALUE, got {pair!r}")
        env[key] = value

    mechanism, why = sandbox.choose()
    if mechanism is None:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(json.dumps(
            {"probe": "R10 destinations, observation only", "label": a.label,
             "instrument_works_here": False, "why": why}, indent=2))
        print(f"no isolation mechanism here: {why}", file=sys.stderr)
        return 1

    arms = (("shared", True), ("isolated", False))
    if a.arm != "both":
        arms = tuple(x for x in arms if x[0] == a.arm)
    cells = {}
    for arm, shared in arms:
        result = sandbox.run_traced(
            list(argv), mechanism=mechanism, network_shared=shared,
            log_dir=Path(a.log_dir), tag=f"{a.label}-{arm}", env=env,
            timeout=a.timeout,
        )
        cells[arm] = {
            "network_shared": shared,
            "returncode": result.returncode,
            "attempt_counts": result.counts(),
            "destinations": destinations(result),
            "stderr_tail": result.stderr[-1000:],
        }
        print(f"{a.label}/{arm}: {result.counts()}", file=sys.stderr)
        time.sleep(a.settle)

    # The shared arm reaching nothing off-machine means the tracer or the route
    # was not working, and then neither cell says anything. Where this run took
    # only the isolated arm, that question is answered by its sibling cell and
    # not here, so the field says `null` rather than a verdict it cannot reach.
    works = (cells["shared"]["attempt_counts"]["off_machine"] > 0
             if "shared" in cells else None)
    out = {
        "probe": (
            "R10 destinations for one argv, on both arms. An OBSERVATION carried "
            "beside the acceptance layer's verdict, never a verdict: SPEC.md §3 R10 "
            "is asserted in bench/acceptance/, which never runs its subject with a "
            "route. This does, because inside a no-route namespace every name "
            "resolves to the same stub resolver and a destination has no name."
        ),
        "label": a.label,
        "conditions": a.conditions,
        "date": time.strftime("%Y-%m-%d"),
        "mechanism": mechanism.name,
        "argv": argv,
        "env_overrides": sorted(x.split("=", 1)[0] for x in a.env),
        "instrument_works_here": works,
        "cells": cells,
    }
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"wrote {a.output}", file=sys.stderr)
    return 0 if works is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
