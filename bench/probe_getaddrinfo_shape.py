#!/usr/bin/env python3
"""How many resolver-port syscalls does ONE name lookup cost on this machine?

Ticket 0629. The R10-no-egress subject arm against zoteus v1.13.0 recorded
`{"off_machine": 0, "dns": 4}` -- four `connect(127.0.0.53:53)` calls -- while
the reviewed source contains exactly one network-shaped call reachable from
server startup in that configuration (`src/lib/update-check.ts`'s single
`fetch()`). Four lookups against one `fetch()` is the gap the ticket exists to
close, and it has two possible shapes: a second, unnamed cause, or one lookup
that simply costs four syscalls here.

This script decides between them by measuring the instrument rather than the
target. It drives the acceptance layer's own tracer and sandbox
(`bench/acceptance/sandbox.py`) over three programs, on both the isolated
(no-route) and net-shared arms:

  nothing               -- a null arm. Without it a count of four is
                           indistinguishable from noise the tracer attributes
                           to any traced process.
  numeric_connect_only  -- a connect to a numeric address, which resolves no
                           name. The discriminating control: it can come out
                           the other way, and if it also showed resolver
                           traffic the per-lookup reading would not follow.
  one_getaddrinfo       -- exactly one `getaddrinfo` of a non-resolving name.

Nothing here starts the target process, so the dedicated-account posture
(DECISIONS.md, ratified 2026-09-03; `bench/acceptance/posture.py`) does not
apply: this is a measurement of glibc's resolver and of the harness's tracer,
not a run against a target.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acceptance import sandbox  # noqa: E402

log = logging.getLogger("probe_getaddrinfo_shape")

#: The three programs, in the order the artifact reports them. Each is the
#: smallest thing that can produce its arm's signal and nothing else.
PROGRAMS: dict[str, str] = {
    "nothing": "pass\n",
    "numeric_connect_only": (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 443), timeout=2).close()\n"
        "except Exception:\n"
        "    pass\n"
    ),
    "one_getaddrinfo": (
        "import socket\n"
        "try:\n"
        "    socket.getaddrinfo('example.invalid', 443)\n"
        "except Exception:\n"
        "    pass\n"
    ),
}

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "bench"
    / "results"
    / "0629-gap-a"
    / "syscall-shape.json"
)


def measure(log_dir: Path) -> dict:
    """Run every program on both arms and return the artifact body."""
    mechanism, why = sandbox.choose()
    if mechanism is None:
        raise SystemExit(f"no isolation mechanism ran here: {why}")
    arms: dict[str, dict] = {}
    for name, source in PROGRAMS.items():
        for network_shared in (False, True):
            arm = "net_shared" if network_shared else "isolated"
            result = sandbox.run_traced(
                [sys.executable, "-c", source],
                mechanism=mechanism,
                network_shared=network_shared,
                log_dir=log_dir,
                tag=f"{name}-{arm}",
            )
            log.info("%s/%s: %s", name, arm, result.counts())
            arms[f"{name}/{arm}"] = {
                "program": source,
                "returncode": result.returncode,
                "counts": result.counts(),
                "attempts": [a.as_json() for a in result.attempts],
            }
    return {
        "probe": (
            "instrument characterization for ticket 0629: how many resolver-port "
            "syscalls one getaddrinfo costs under the acceptance layer's own tracer "
            "and sandbox on this machine"
        ),
        "not_a_target_run": (
            "no target process is started here, so the dedicated-account posture "
            "does not apply; this measures glibc's resolver and the tracer"
        ),
        "mechanism": mechanism.name,
        "detectors": {
            "off_machine": "a connect/sendto/sendmsg naming a non-loopback address",
            "dns": "a connect/sendto/sendmsg to a resolver port, loopback included",
        },
        "arms": arms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="where the artifact lands (default: %(default)s)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="where the tracer's logs land (default: a 'traces' dir beside --output)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    log_dir = args.log_dir or args.output.parent / "traces"
    body = measure(log_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, indent=1) + "\n")
    log.info("wrote %s", args.output)


if __name__ == "__main__":
    main()
