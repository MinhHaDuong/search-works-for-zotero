#!/usr/bin/env python3
"""R10 on a plugin target: the same host, with and without the plugin, nothing else.

Ticket 0584. `bench/acceptance/` decides R10 for one adapter and records the
harness's own generic egress probe as its control. That control answers "is the
instrument working here". It does not answer the question a PLUGIN target raises,
which is different and sharper: the traced process tree is the HOST application's,
so how much of the verdict belongs to the host?

This driver answers that one, and only that one. It launches the same host
application twice under the same isolation and the same tracer, differing in
**nothing but whether the plugin's XPI is in the profile**, and reports both
counts. It scores nothing, compares nothing and subtracts nothing: it writes the
arms down side by side and a reader compares them. Subtracting one from the other
in code would be this harness deciding a target's verdict, which the ratified
contract forbids.

**Three properties it was built to have, each because its absence has cost this
project a wrong answer before.**

*The arms are the same length.* Readiness-driven dwells are not: the plugin's
sidecar database appears later than the host's own, so waiting on each arm's own
readiness file makes the with-plugin arm run longer and the difference between
the arms is then partly duration. The dwell here is a fixed wall time, identical
in every arm, and the readiness files are only OBSERVED and reported.

*The instrument has a positive control that can fail.* One arm runs with the
route intact. If it does not trip both detectors, `instrument_works_here` is
false and the artifact says the arms decide nothing — a probe whose all-clear is
indistinguishable from "I could not look" is not a probe.

*Both detectors, always.* Inside a namespace with no route, a target reaching for
a hostname dies at resolution and never attempts an off-machine connect, so a
connect-only detector reports zero for a host that is actively phoning home. The
detectors are `bench/acceptance/sandbox.py`'s, imported rather than restated, so
these numbers come from the same instrument that produced the adapter's.

It lives outside `bench/acceptance/` deliberately: it names a host application,
and the assertion layer's neutrality guard should not be asked to tolerate that.

    python3 bench/r10_plugin_pair.py \\
        --launcher <the host's launcher> --artifact <the plugin's .xpi> \\
        --root <a scratch directory> --output bench/results/<...>.json

Related: `bench/r10_host_baseline.py` (ticket 0584's lane lead) measures the host
alone at a longer dwell, with a null control. The two overlap and should be folded
into one driver if both land; this one is kept separate because it was written
against a different question and its arms are paired rather than staged.
"""

import argparse
import importlib.util
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SANDBOX = REPO / "bench" / "acceptance" / "sandbox.py"

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("r10-plugin-pair")

#: The preferences written into the profile before the host starts. Harness
#: setup, identical in every arm, and none of them touches the plugin's own
#: preference branch — a preference under that branch would be a target option,
#: and the arms would then differ in two things rather than one.
HARNESS_PREFS = (
    ("extensions.zotero.httpServer.enabled", "true"),
    ("extensions.autoDisableScopes", "0"),
    ("extensions.enabledScopes", "15"),
    ("app.update.enabled", "false"),
)

#: The inner driver, run inside the isolation mechanism and under the tracer. It
#: owns the host process and stops it by process GROUP: the launcher is a shell
#: script and the application starts further processes of its own, so signalling
#: the direct child leaves them reparented and alive — and the tracer follows
#: descendants, so it then waits for them and the run never returns.
INNER = '''
import os, signal, subprocess, time
root = {root!r}
env = dict(os.environ)
env["HOME"] = os.path.join(root, "home")
env["DISPLAY"] = {display!r}
env.pop("XAUTHORITY", None)
log = open(os.path.join(root, "host.log"), "wb")
p = subprocess.Popen(
    [{launcher!r}, "-profile", os.path.join(root, "profile"),
     "-datadir", os.path.join(root, "data"), "-no-remote"],
    stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
group = os.getpgid(p.pid)
time.sleep({dwell})
seen = {{name: os.path.exists(os.path.join(root, "data", name))
        for name in {witness!r}}}
for sig, grace in ((signal.SIGTERM, 30), (signal.SIGTERM, 15), (signal.SIGKILL, 30)):
    try:
        os.killpg(group, sig)
    except Exception:
        pass
    try:
        p.wait(grace)
        break
    except Exception:
        continue
print(__import__("json").dumps(seen))
'''


def load_sandbox():
    """The layer's own tracer and detectors, by path.

    Imported rather than restated: two implementations of one detector drift,
    and the whole point of these numbers is that they are comparable with the
    adapter's.
    """
    spec = importlib.util.spec_from_file_location("sandbox", SANDBOX)
    if spec is None or spec.loader is None:  # pragma: no cover - path is fixed
        raise RuntimeError(f"cannot load the sandbox module at {SANDBOX}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(root: Path, artifact: Path | None, addon_id: str, port: int) -> None:
    """A fresh, virgin profile and data directory. Never seeded, never cleared.

    The arena's state is part of the measurement — a warmed profile makes the
    host do none of its first-run work — so every arm starts from nothing and the
    artifact records that it did.
    """
    for sub in ("home", "profile/extensions", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    prefs = (("extensions.zotero.httpServer.port", str(port)), *HARNESS_PREFS)
    (root / "profile" / "prefs.js").write_text(
        "\n".join(f'user_pref("{name}", {value});' for name, value in prefs) + "\n",
        encoding="utf-8",
    )
    if artifact is not None:
        placed = root / "profile" / "extensions" / f"{addon_id}.xpi"
        try:
            subprocess.run(["cp", "--reflink=auto", str(artifact), str(placed)],
                           check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):  # pragma: no cover
            placed.write_bytes(artifact.read_bytes())


def arm(sandbox, *, root: Path, launcher: Path, artifact: Path | None,
        addon_id: str, port: int, display: str, dwell: float, shared: bool,
        witness: tuple[str, ...]) -> dict:
    """One traced launch, and what it named."""
    mechanism, why = sandbox.choose()
    if mechanism is None:
        raise SystemExit(f"no isolation mechanism ran here: {why}")
    prepare(root, artifact, addon_id, port)
    inner = INNER.format(root=str(root), launcher=str(launcher), display=display,
                         dwell=dwell, witness=list(witness))
    began = time.monotonic()
    result = sandbox.run_traced(
        [sys.executable or "python3", "-c", inner],
        mechanism=mechanism, network_shared=shared,
        log_dir=root / "trace", tag="shared" if shared else "isolated",
    )
    try:
        seen = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        seen = {}
    return {
        "arm": root.name,
        "plugin_present": artifact is not None,
        "network_shared": shared,
        "dwell_s": dwell,
        "profile_state": "virgin: created fresh for this arm, never seeded, never cleared",
        "mechanism": mechanism.name,
        "attempt_counts": result.counts(),
        "returncode": result.returncode,
        "wall_s": round(time.monotonic() - began, 1),
        "witnesses_present": seen,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--launcher", required=True, help="the host application's launcher")
    ap.add_argument("--artifact", required=True, help="the plugin's release .xpi")
    ap.add_argument("--addon-id", required=True, help="the filename a sideloaded XPI takes")
    ap.add_argument("--root", required=True, help="a scratch directory to build arenas in")
    ap.add_argument("--output", required=True, help="where the artifact lands")
    ap.add_argument("--witness", action="append", default=[],
                    help="a data-directory filename to observe; repeatable")
    ap.add_argument("--port", type=int, default=23219)
    ap.add_argument("--display", default=":1")
    ap.add_argument("--dwell", type=float, default=120.0,
                    help="fixed wall time per arm; identical across arms by design")
    ap.add_argument("--replicates", type=int, default=2)
    a = ap.parse_args()

    sandbox = load_sandbox()
    root = Path(a.root).resolve()
    witness = tuple(a.witness)
    stamp = time.strftime("%H%M%S")
    common = dict(launcher=Path(a.launcher), addon_id=a.addon_id, port=a.port,
                  display=a.display, dwell=a.dwell, witness=witness)

    arms = []
    for replicate in range(1, a.replicates + 1):
        for present in (False, True):
            name = f"{stamp}-isolated-{'with' if present else 'without'}-{replicate}"
            log.info("arm %s", name)
            arms.append(arm(sandbox, root=root / name,
                            artifact=Path(a.artifact) if present else None,
                            shared=False, **common))
    log.info("arm control (route intact)")
    control = arm(sandbox, root=root / f"{stamp}-shared-with",
                  artifact=Path(a.artifact), shared=True, **common)

    works = bool(control["attempt_counts"]["off_machine"]
                 and control["attempt_counts"]["dns"])
    document = {
        "probe": (
            "R10 on a plugin target: the same host application launched with and "
            "without the plugin, under the same isolation and the same tracer, "
            "differing in nothing else (ticket 0584)"
        ),
        "not_a_verdict": (
            "this driver scores nothing and subtracts nothing. It records the arms "
            "side by side so a reader can see how much of an R10 verdict on a plugin "
            "target belongs to the host application; subtracting one arm from the "
            "other in code would be the harness deciding a target's verdict."
        ),
        "date": time.strftime("%Y-%m-%d"),
        "detectors": (
            "bench/acceptance/sandbox.py's, imported rather than restated, so these "
            "counts are comparable with the acceptance layer's own"
        ),
        "instrument_works_here": works,
        "instrument_control": control,
        "arms": arms,
    }
    if not works:
        document["warning"] = (
            "the route-intact control did not trip both detectors, so the instrument "
            "is not known to work here and the arms below decide nothing"
        )
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in (*arms, control):
        log.info("%-34s %s", row["arm"], row["attempt_counts"])
    log.info("instrument_works_here=%s; wrote %s", works, out)
    return 0 if works else 1


if __name__ == "__main__":
    raise SystemExit(main())
