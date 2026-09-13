#!/usr/bin/env python3
"""Does the sitter still start and work inside a REAL Zotero? Ticket 0784.

Every existing sitter suite (`tests/sdt_sitter_*.mjs`, the two mutation probes)
drives `tests/sdt_sitter_zotero_mock.mjs`. All of it is simulated -- the launch
report says so, and nothing in any gate has ever launched a real Zotero and
watched the shipped `.xpi` arm. `bench/sitter_volume_experiment.py` already
launches a real Zotero, installs a real XPI through the same call path the
Add-ons UI uses, and reads liveness over RDP -- but for a different question
(does the add-on SURVIVE many install/replace/disable cycles), over a big
fixture, and it cycles by design. This is the short, non-cycling variant: build
the XPI, launch ONE real Zotero against a fresh throwaway profile and data
directory, install once, wait for the sitter to arm, census a handful of
documents, confirm the cache landed on disk, and tear down. No replace, no
disable/enable, no restart -- that is the volume rig's job, not a smoke test's.

## The data-directory refusal, ticket 0782

Ticket 0782 recorded the volume rig's `--data-dir` silently not taking: it
logged the pinned directory while Zotero opened its default one, and a fixture
import landed in the author's real default data directory purely by luck. This
script re-reads the data directory Zotero ACTUALLY opened (the liveness probe
below, same shape as the volume rig's) and REFUSES, before importing anything,
if it is not the one this run just created and pinned. Fixing that check here
does not close 0782 -- that ticket is about the volume rig's own log line and
mechanism, not this script -- but the hazard is the same one, and a smoke test
run repeatedly and unattended cannot be the second place it is left open.

## Exit codes -- this repo's convention (`make golden-run`, `sitter-verify-install`)

  0  PASS -- the sitter armed, censused the fixture, and wrote its cache.
  1  FAIL -- a real defect: install refused, the sitter never armed, the data
     directory did not match what was requested, or an assertion after import
     came back wrong. This is the state the deliberate-break drill (ticket
     0784's log) is required to produce at least once.
  2  usage error (bad arguments).
  3  NOT-RUN -- could not look: no Zotero binary at `--zotero-bin`, no display,
     the XPI would not build, the debugger port never came up, or RDP never
     connected. Never conflated with 0: a gate whose all-clear cannot be told
     from its could-not-look is not a gate (AGENTS.md, `tickets/AGENTS.md`).

## What is reused, and what this file adds

Reused, not re-implemented: `bench/sitter_watch.py`'s `Log`, `connect_resilient`
and `refuse_dot_log`; `bench/sitter_volume_experiment.py`'s `SEED_PREFS` (the
`devtools.*`/data-directory prefs a fresh profile needs before first launch),
`wait_for_port`, `eval_action`, `install_or_replace_code`,
`import_menagerie_code` (generic despite the name -- it takes any RIS path) and
`liveness_code`; `bench/build_sdt_sitter.py` to build the XPI, run as a
subprocess exactly as `make sitter-install`'s own instructions do, so the
frozen `plugins/sdt-sitter/` payload is only ever READ; and
`bench/fixtures/smoke_library.py` (new, but itself a thin reuse of
`bench/fixtures/make_attachment_fixtures.write_pdf`) for the three-document
fixture. New in this file: argument handling, the launch/teardown for a single
non-cycling run, and the ticket-0782 refusal.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from fixtures.smoke_library import write_smoke_library  # noqa: E402
from sitter_volume_experiment import (  # noqa: E402
    SEED_PREFS,
    eval_action,
    import_menagerie_code,
    install_or_replace_code,
    liveness_code,
    wait_for_port,
)
from sitter_watch import Log, connect_resilient, refuse_dot_log  # noqa: E402
from zotero_rdp_client import RDPConnectionClosed, RDPTimeout  # noqa: E402

NOT_RUN = 3
FAIL = 1
PASS = 0
USAGE = 2


class NotRunError(Exception):
    """Could not look: environment/setup, never the add-on's own behaviour."""


class SmokeFailure(Exception):
    """A real defect, observed against a live Zotero."""


def build_xpi(out_path: Path) -> None:
    """Build the real, released payload -- reading `plugins/sdt-sitter/`,
    never writing to it -- via the same builder `make sitter-install` uses."""
    result = subprocess.run(
        [sys.executable, str(REPO / "bench" / "build_sdt_sitter.py"), "--output", str(out_path)],
        capture_output=True, text=True, check=False)
    if result.returncode != 0 or not out_path.exists():
        raise NotRunError(
            f"could not build the XPI via bench/build_sdt_sitter.py: "
            f"rc={result.returncode} stderr={result.stderr.strip()!r}")


def find_zotero_bin(zotero_launcher: Path) -> Path:
    """The launcher (`.../zotero`) is a wrapper that runs `zotero-bin` as an
    ordinary, non-`exec`'d child (`bench/sitter_volume_experiment.py`'s own
    finding) -- so this launches `zotero-bin` directly, the same way, for the
    same reason: `proc.pid` has to name a process this script can terminate."""
    if not zotero_launcher.exists():
        raise NotRunError(f"no Zotero at {zotero_launcher}")
    install_dir = zotero_launcher.resolve().parent
    binary = install_dir / "zotero-bin"
    app_ini = install_dir / "app" / "application.ini"
    if not binary.exists() or not app_ini.exists():
        raise NotRunError(f"{zotero_launcher} does not look like a Zotero install "
                          f"(missing {binary} or {app_ini})")
    return binary


def setup_profile(work_dir: Path, port: int) -> tuple[Path, Path]:
    """A fresh profile and a fresh, pinned data directory. Refuses to reuse
    either, on the same principle as the volume rig: a profile or data
    directory that could already be in use is never touched."""
    profile = work_dir / "profile"
    data_dir = work_dir / "data"
    profile.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    prefs_path = profile / "prefs.js"
    prefs = SEED_PREFS.replace("{data_dir}", str(data_dir))
    # SEED_PREFS sets `extensions.zotero.dataDir` but not the companion pref
    # that gates it. `chrome/content/zotero/xpcom/dataDirectory.js` (Zotero's
    # own source, read out of the installed omni.ja while chasing this) only
    # honours `dataDir` when `Zotero.Prefs.get('useDataDir')` is ALSO true --
    # `if (Zotero.Prefs.get('useDataDir') && Zotero.Prefs.get('dataDir'))`;
    # otherwise Zotero opens its default directory and never reads the pin at
    # all. This is very likely ticket 0782's actual mechanism ("candidates
    # include the pref name" -- it names exactly this pref as unestablished),
    # reproduced live while first running this script: with SEED_PREFS as-is,
    # Zotero opened `/home/haduong/Zotero` although `dataDir` was pinned
    # elsewhere, and the refusal below caught it before anything was imported.
    # Logged on ticket 0782 rather than fixed there -- this file's job is the
    # smoke test, and 0782's own fix (the refusal, the corrected log line) is
    # a separate ticket's exit criteria.
    prefs += 'user_pref("extensions.zotero.useDataDir", true);\n'
    prefs_path.write_text(prefs, encoding="utf-8")
    return profile, data_dir


def launch_zotero(binary: Path, app_ini: Path, profile: Path, port: int,
                  stdout_log_path: Path):
    env = {
        **os.environ,
        "MOZ_ALLOW_DOWNGRADE": "1",
        "MOZ_LEGACY_PROFILES": "1",
        "MOZ_ENABLE_WAYLAND": "1",
    }
    if not env.get("DISPLAY"):
        raise NotRunError("no DISPLAY set -- headless never arms the sitter "
                          "(ticket 0778: initialize() needs a main window). "
                          "Run with a real X display, e.g. DISPLAY=:1")
    cmd = [str(binary), "-app", str(app_ini),
          "--start-debugger-server", str(port), "--profile", str(profile)]
    stdout_log = open(stdout_log_path, "a", encoding="utf-8")  # noqa: SIM115
    proc = subprocess.Popen(cmd, stdout=stdout_log, stderr=subprocess.STDOUT, env=env)
    return proc, stdout_log


def stop_zotero(proc, timeout: float = 30.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def poll_until_armed(client, log: Log, eval_timeout: float, arm_deadline: float,
                     poll_interval: float = 3.0) -> dict:
    """Wait for `Zotero.SDTPackSitter.state` to exist and show real work, or
    time out. A liveness read that never arms is this script's central FAIL --
    ticket 0778's exact defect, checked here as a smoke assertion rather than
    assumed."""
    last = {}
    while time.monotonic() < arm_deadline:
        last = eval_action(client, liveness_code(), eval_timeout, log, "liveness")
        armed = bool(last.get("handle")) and (
            last.get("cacheWritten") or (last.get("scanned") or 0) > 0)
        if armed:
            return last
        time.sleep(poll_interval)
    raise SmokeFailure(
        f"the sitter never became alive within the arm timeout: {last}. "
        "Ticket 0778: initialize() needs a main window; a dead handle here "
        "means the shipped payload does not arm under a real Zotero.")


def run_smoke(args) -> dict:
    log = Log(args.log)
    try:
        return _run_smoke(args, log)
    finally:
        log.close()


def _run_smoke(args, log: Log) -> dict:
    log.write(f"smoke starting: zotero={args.zotero_bin} port={args.port} "
              f"work_dir={args.work_dir}")

    binary = find_zotero_bin(args.zotero_bin)
    app_ini = binary.parent / "app" / "application.ini"

    if args.xpi is not None:
        # For the deliberate-break drill and any other case where the caller
        # already has a built payload (a scratch copy with something broken on
        # purpose, or a specific released XPI) -- never a substitute for
        # building the real, released `plugins/sdt-sitter/` in the ordinary
        # run, which is what happens when this is not given.
        if not args.xpi.exists():
            raise NotRunError(f"--xpi {args.xpi} does not exist")
        xpi_path = args.xpi
        log.write(f"smoke using given XPI at {xpi_path} (skipping the build)")
    else:
        xpi_path = args.work_dir / "sdt-sitter-smoke.xpi"
        build_xpi(xpi_path)
        log.write(f"smoke built XPI at {xpi_path}")

    fixture_dir = args.work_dir / "fixture"
    fixture_dir.mkdir(parents=True)
    ris_path = write_smoke_library(fixture_dir)
    log.write(f"smoke fixture written at {ris_path}")

    profile, requested_data_dir = setup_profile(args.work_dir, args.port)
    log.write(f"smoke profile={profile} requested data dir={requested_data_dir}")

    proc, stdout_log = launch_zotero(binary, app_ini, profile, args.port,
                                     args.work_dir / "zotero-stdout.log")
    log.write(f"smoke launched zotero pid={proc.pid}")
    client = None
    try:
        try:
            wait_for_port("127.0.0.1", args.port, time.monotonic() + 60)
        except TimeoutError as exc:
            raise NotRunError(f"debugger port never came up: {exc}") from exc
        try:
            client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)
        except RuntimeError as exc:
            raise NotRunError(f"could not attach over RDP: {exc}") from exc

        result = eval_action(client, install_or_replace_code(xpi_path), args.eval_timeout,
                             log, "install")
        if not result.get("ok"):
            raise SmokeFailure(f"the XPI would not install: {result}")
        log.write(f"smoke installed: {result}")

        live = poll_until_armed(client, log, args.eval_timeout,
                                time.monotonic() + args.arm_timeout)
        log.write(f"smoke armed: {live}")

        if not live.get("mainWindows"):
            raise SmokeFailure(f"armed with no main window recorded: {live}")

        # Ticket 0782's refusal, applied here rather than assumed: compare the
        # data directory Zotero ACTUALLY opened against the one this run just
        # created and pinned, before anything is imported into it.
        actual_data_dir = Path(live["dataDir"]).resolve()
        expected_data_dir = requested_data_dir.resolve()
        if actual_data_dir != expected_data_dir:
            raise SmokeFailure(
                f"REFUSING to import: Zotero opened {actual_data_dir}, not the "
                f"requested {expected_data_dir}. Ticket 0782's hazard -- the pin "
                "silently not taking -- importing here could land the fixture "
                "in a real library. Nothing was imported.")
        log.write(f"smoke data directory confirmed: {actual_data_dir}")

        imported = eval_action(client, import_menagerie_code(ris_path),
                               max(args.eval_timeout, 60.0), log, "fixture import")
        if not imported.get("ok"):
            raise SmokeFailure(f"the fixture would not import: {imported}")
        if imported.get("attachments", 0) - imported.get("missing", 0) <= 0:
            raise SmokeFailure(f"the fixture imported with no attachment on disk: {imported}")
        log.write(f"smoke fixture imported: {imported}")

        # Give the census a moment to pick up the just-imported items, then
        # read liveness again rather than assume the earlier read still holds.
        censused = poll_until_armed(client, log, args.eval_timeout,
                                    time.monotonic() + args.census_timeout)
        log.write(f"smoke post-import liveness: {censused}")
        if (censused.get("scanned") or 0) < imported["items"]:
            raise SmokeFailure(
                f"census under-counted: scanned={censused.get('scanned')} "
                f"but {imported['items']} items were just imported")

        cache_path = actual_data_dir / "sdt-sitter-cache.jsonl"
        if not cache_path.exists():
            raise SmokeFailure(
                f"the sitter never wrote its cache at {cache_path} -- checked "
                "directly on disk, not just through the add-on's own report")
        log.write(f"smoke cache confirmed on disk: {cache_path}")

        log.write("smoke PASS")
        return {"ok": True, "dataDir": str(actual_data_dir), "liveness": censused,
               "imported": imported}
    finally:
        if client is not None:
            try:
                client.close()
            except (RDPConnectionClosed, RDPTimeout, OSError):
                pass
        log.write(f"smoke terminating zotero pid={proc.pid}")
        stop_zotero(proc)
        stdout_log.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zotero-bin",
                        default=str(Path.home() / ".local" / "Zotero_linux-x86_64" / "zotero"),
                        help="the Zotero launcher script, not zotero-bin itself")
    parser.add_argument("--work-dir", type=Path, default=None,
                        help="base dir for the throwaway profile/data/fixture/log "
                             "(default: a fresh mkdtemp, removed after the run "
                             "unless --keep is given)")
    parser.add_argument("--keep", action="store_true",
                        help="keep --work-dir after the run instead of removing it")
    parser.add_argument("--xpi", type=Path, default=None,
                        help="use this already-built XPI instead of building "
                             "plugins/sdt-sitter/ fresh -- for the deliberate-"
                             "break drill or replaying a specific payload")
    parser.add_argument("--port", type=int, default=6100)
    parser.add_argument("--eval-timeout", type=float, default=20.0)
    parser.add_argument("--arm-timeout", type=float, default=90.0,
                        help="how long to wait for the sitter to become alive "
                             "after install")
    parser.add_argument("--census-timeout", type=float, default=60.0,
                        help="how long to wait for the census to pick up the "
                             "imported fixture")
    parser.add_argument("--log", type=Path, default=None,
                        help="where to write the timestamped log (default: "
                             "<work-dir>/smoke-log.txt)")
    args = parser.parse_args(argv)

    args.zotero_bin = Path(args.zotero_bin)
    own_work_dir = args.work_dir is None
    if own_work_dir:
        args.work_dir = Path(tempfile.mkdtemp(prefix="sdt-sitter-smoke-"))
    else:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        if any(args.work_dir.iterdir()):
            print(f"--work-dir {args.work_dir} is not empty; pass a fresh directory",
                 file=sys.stderr)
            return USAGE
    if args.log is None:
        args.log = args.work_dir / "smoke-log.txt"
    if args.log.suffix == ".log":
        print(refuse_dot_log(args.log), file=sys.stderr)
        return USAGE

    try:
        outcome = run_smoke(args)
        print(json.dumps(outcome, indent=2))
        return PASS
    except NotRunError as exc:
        print(f"NOT-RUN: {exc}", file=sys.stderr)
        return NOT_RUN
    except SmokeFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return FAIL
    except Exception as exc:  # noqa: BLE001 -- an unattended smoke test logs its own crash
        print(f"FAIL (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        return FAIL
    finally:
        if own_work_dir and not args.keep:
            shutil.rmtree(args.work_dir, ignore_errors=True)
        elif args.keep:
            print(f"work dir kept at {args.work_dir}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
