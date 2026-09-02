#!/usr/bin/env python3
"""What the HOST application attempts, with no plugin installed. R10's baseline.

`SPEC.md` §3 owns R10; `SPEC.md` §5.2.8 owns the acceptance harness. This is
neither an assertion nor part of that harness: it asserts nothing, it scores
nothing, and it returns 0 whatever it measures. It exists because of one fact
about the in-process-plugin architecture class, which the roster now contains:

**the process R10 traces is not the target's.**

An external server target owns its process, so a zero on both detectors is a
statement about the target. A plugin does not. The process under trace is the
reference manager's, and it does its own update, blocklist and telemetry work
whether a plugin is loaded or not. So a plugin target's egress number is
unreadable on its own: it is the host's number plus whatever the plugin added,
and nothing in the artifact says which is which.

This driver measures the first term. It launches the host with **no plugin**,
under the same isolation and the same tracer the assertion uses — importing
`acceptance.sandbox` rather than restating it, so the detectors here are the
layer's own and cannot drift from them.

Three cells, and the third is what makes the other two readable:

    virgin-isolated   a profile nothing has run against, no route out
    warmed-isolated   the SAME profile, second run, no route out
    virgin-shared     a fresh virgin profile, route intact

`virgin-shared` is the discriminating control. If it does not trip both
detectors, the instrument is not known to work on this machine and no cell
decides anything — the same honest-gate rule the assertion layer is held to.
The virgin/warmed pair is there because the arena is part of the measurement:
a check that reads one number from a virgin profile and another from a warmed
one is reporting the profile's history, not the software's behaviour.

**Read the output as an observation, never as a verdict, and never subtract it
from a target's number in code.** Arithmetic between two runs of different
software is the layer scoring a result, which the ratified adapter contract
forbids in as many words. The artifact carries both numbers; a reader compares
them.

**The committed artifact carries verdicts and destinations, never paths.** An
arena lives under a scratch directory whose name is one machine's business, and
`bench/results/**` is a public tree — the same rule `acceptance/run.py` states
for its fixture artifact.

    python3 bench/r10_host_baseline.py \\
        --application /path/to/the/host/launcher \\
        --root /a/scratch/directory \\
        --output bench/results/r10-host-baseline/hostbase.json

The application is named on the command line and never in this file, for the
reason the acceptance layer gives: a usage example naming one would put a
product's name in a module that is supposed to hold none.
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acceptance.sandbox import choose, run_traced  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("r10-host-baseline")

#: How long the host is left running before it is killed. A GUI application does
#: not exit on its own, so the dwell is the measurement window and it is
#: recorded in the artifact: a number measured over 75 s and one measured over 5
#: are not comparable, and nothing else in the output would say so.
DWELL_SECONDS = 75

#: The preferences the launch needs, and nothing else. Two are harness setup —
#: they are what makes a side-loaded add-on active without a GUI click, i.e. the
#: state an ordinary user reaches by installing one — and are written even in the
#: no-plugin cells so that the baseline and a plugin run differ in the plugin
#: alone. The port move exists only so several instances coexist on one machine.
PREFS = (
    'user_pref("extensions.zotero.httpServer.port", {port});',
    'user_pref("extensions.zotero.httpServer.enabled", true);',
    'user_pref("extensions.autoDisableScopes", 0);',
    'user_pref("extensions.enabledScopes", 15);',
)


def prepare(root: Path, name: str, port: int, *, reuse: bool) -> Path:
    """A cell's profile and data directory, virgin or reused.

    `reuse=True` is the warmed arm and is the whole point of the pair: it runs
    against the profile the previous call left behind rather than against a new
    one. Nothing is deleted to make a virgin cell — an old one is moved aside,
    so a rerun cannot silently inherit it.
    """
    cell = root / name
    if cell.exists() and not reuse:
        shutil.move(str(cell), f"{cell}.superseded.{int(time.time())}")
    for sub in ("home", "profile/extensions", "data"):
        (cell / sub).mkdir(parents=True, exist_ok=True)
    (cell / "profile" / "prefs.js").write_text(
        "\n".join(line.format(port=port) for line in PREFS) + "\n"
    )
    return cell


def launch(application: Path, cell: Path, *, mechanism, shared: bool, tag: str,
           display: str, dwell: int, log_dir: Path, marker: str) -> dict:
    """One cell: start the host in the cell, trace it, kill it after the dwell.

    `started` is not decoration. A launch that dies early — no display, a
    profile lock, a missing library — attempts almost nothing and reads exactly
    like a clean run. So the cell records whether the host got far enough to
    create its database, and a cell that did not is not a measurement.
    """
    env = {
        "HOME": str(cell / "home"),
        "DISPLAY": display,
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
    }
    argv = [
        "timeout", "-k", "10", str(dwell), str(application),
        "-profile", str(cell / "profile"),
        "-datadir", str(cell / "data"),
        "-no-remote",
    ]
    result = run_traced(argv, mechanism=mechanism, network_shared=shared,
                        log_dir=log_dir, tag=tag, timeout=dwell + 300, env=env)
    counts = result.counts()
    return {
        "network_shared": shared,
        "isolation_mechanism": mechanism.name,
        "dwell_seconds": dwell,
        "attempt_counts": counts,
        # The destinations, deduplicated, so a reader can see WHAT was reached
        # for without carrying one line per syscall. The addresses are the
        # host's own upstreams; no path and no profile name is recorded.
        "destinations": sorted({
            f"{a.address}:{a.port}/{a.detector}" for a in result.attempts
        }),
        # `timeout` kills the host, so this is 124 on every cell. Recorded
        # because the acceptance layer's egress assertion requires a zero
        # return code for a pass, which a GUI application can never give it.
        "returncode": result.returncode,
        "host_reached_its_database": (cell / "data" / marker).exists(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--application", required=True,
                    help="the host application's launcher, with no plugin installed")
    ap.add_argument("--root", required=True,
                    help="a scratch directory this run may create cells under")
    ap.add_argument("--output", required=True, help="where the artifact lands")
    ap.add_argument("--display", default=os.environ.get("DISPLAY", ":0"),
                    help="the X display the host attaches to")
    ap.add_argument("--dwell", type=int, default=DWELL_SECONDS,
                    help="seconds the host runs before it is killed")
    ap.add_argument("--port", type=int, default=23419,
                    help="the host's HTTP port, moved only so instances coexist")
    ap.add_argument("--started-marker", default="zotero.sqlite",
                    help="a file the host creates in its data directory once it has "
                         "really started; a cell that lacks it is not a measurement")
    a = ap.parse_args()

    mechanism, why = choose()
    if mechanism is None:
        log.error("no isolation mechanism ran here: %s", why)
        return 0

    application, root = Path(a.application).resolve(), Path(a.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    traces = root / "trace"

    cells: dict[str, dict] = {}
    virgin = prepare(root, "virgin", a.port, reuse=False)
    cells["virgin-isolated"] = launch(
        application, virgin, mechanism=mechanism, shared=False,
        tag="virgin-isolated", display=a.display, dwell=a.dwell, log_dir=traces,
        marker=a.started_marker)
    # The same profile, deliberately not refreshed: whatever the first run
    # recorded on disk is now there, which is the difference being measured.
    cells["warmed-isolated"] = launch(
        application, virgin, mechanism=mechanism, shared=False,
        tag="warmed-isolated", display=a.display, dwell=a.dwell, log_dir=traces,
        marker=a.started_marker)
    control = prepare(root, "control", a.port + 10, reuse=False)
    cells["virgin-shared"] = launch(
        application, control, mechanism=mechanism, shared=True,
        tag="virgin-shared", display=a.display, dwell=a.dwell, log_dir=traces,
        marker=a.started_marker)

    shared = cells["virgin-shared"]["attempt_counts"]
    instrument_works = bool(shared["off_machine"] and shared["dns"])
    artifact = {
        "probe": ("what the host application attempts with NO plugin installed — the "
                  "baseline an in-process-plugin target's R10 number has to be read "
                  "against (SPEC.md §3 R10, §5.2.8)"),
        "not_a_verdict": (
            "this scores nothing and decides nothing. A plugin target's egress number "
            "is the host's plus the plugin's, and this measures only the first term. "
            "Compare the two; never subtract one from the other in code, which would "
            "be the harness scoring a result."),
        "date": time.strftime("%Y-%m-%d"),
        "host_version": read_version(application),
        "isolation_mechanism": mechanism.name,
        "detectors": {
            "off_machine": "a connect/sendto/sendmsg naming a non-loopback address",
            "dns": ("a connect/sendto/sendmsg to a resolver port, loopback included — "
                    "under isolation a hostname attempt dies at resolution and leaves "
                    "no off-machine connect, so a detector without this one reports a "
                    "false green"),
        },
        "instrument_works_here": instrument_works,
        "why_the_control": (
            "the shared arm must trip BOTH detectors or the instrument is not known to "
            "work on this machine, and no cell decides anything"),
        "cells": cells,
    }
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2))

    for name, cell in cells.items():
        log.info("%-18s %s  started=%s", name, cell["attempt_counts"],
                 cell["host_reached_its_database"])
    if not instrument_works:
        log.info("the control did not trip both detectors: this run decides nothing")
    log.info("wrote %s", output)
    return 0


def read_version(application: Path) -> str:
    """The host's own version string, so the artifact says what it measured."""
    candidates = (application.parent / "application.ini",
                  application.parent / "app" / "application.ini")
    for candidate in candidates:
        if not candidate.exists():
            continue
        fields = {}
        for line in candidate.read_text(errors="replace").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in ("Name", "Version", "BuildID"):
                fields[key.strip()] = value.strip()
        if fields:
            return " ".join(f"{k}={v}" for k, v in fields.items())
    return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
