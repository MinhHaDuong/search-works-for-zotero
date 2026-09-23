#!/usr/bin/env python3
"""Rung 4: run the sitter on a reflink copy of the author's library (ticket 0818).

The copy is taken by `bench/sitter_clone_data.py`, never here. This driver
takes that copy and runs the sitter over it in a clean-room profile until the
census settles, with ticket 0816's integrity check against the copy's own
before-snapshot:

    1. snapshot the copy with no Zotero running (the pre-launch record);
    2. launch Zotero on a fresh profile pinned to the copy, wait for its data
       layer, take the integrity baseline -- so Zotero's own start-up writes
       are recorded (`startup`, never judged) but not charged to the sitter;
    3. install the built sitter, confirm Zotero opened the copy and nothing
       else (ticket 0782's refusal, as rung 2 does it);
    4. poll `Zotero.SDTPackSitter.state` until it is settled -- `pending == 0`,
       not busy, phase out of census, draining and extracting -- for
       `--settle-polls` consecutive reads, sampling the process's CPU all the
       while with `bench/sdt_stall_probe.py`'s instruments, so a run that never
       settles is reported with the reading that tells a slow tail from a
       wedge (0793) rather than as a blind timeout;
    5. close the `census` integrity segment, edit-free: only the SDT cache may
       have changed;
    6. quit Zotero gracefully, record whether `zotero.sqlite-wal` is empty
       after the quit, and close a `quit` segment against the copy read with
       Zotero gone -- the WAL control: the snapshot must read the database
       identically either side of the quit.

Refuses to run on a data directory any local Zotero profile is pinned to: the
author's live library is never this driver's target.

Exit codes, this repo's convention: 0 PASS (settled, both segments clean);
1 FAIL (a violation, a census that never settled, or the wrong data directory
opened); 2 usage; 3 NOT-RUN (no Zotero, no display, no RDP).
"""

import argparse
import json
import platform
import re
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

import sdt_stall_probe as stall  # noqa: E402
import sitter_integrity as integrity  # noqa: E402
from sitter_menagerie_test import STATE  # noqa: E402
from sitter_smoke_test import (  # noqa: E402
    FAIL,
    NOT_RUN,
    PASS,
    USAGE,
    ZOTERO_READY,
    NotRunError,
    build_xpi,
    find_zotero_bin,
    launch_zotero,
    poll_until_armed,
    setup_profile_existing_data,
    stop_zotero,
)
from sitter_volume_experiment import (  # noqa: E402
    eval_action,
    install_or_replace_code,
    wait_for_port,
)
from sitter_watch import Log, connect_resilient, refuse_dot_log  # noqa: E402
from zotero_rdp_client import RDPConnectionClosed, RDPTimeout  # noqa: E402

#: Phases in which the sitter is still working through the library.
WORKING_PHASES = frozenset({"census", "draining", "extracting"})

QUIT = """
(function() {
  try {
    Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
    return JSON.stringify({ok: true});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

_PREF_DATADIR = re.compile(r'user_pref\("extensions\.zotero\.dataDir",\s*"([^"]*)"\)')


class CloneFailure(Exception):
    """A real defect or a finding, observed against a live Zotero."""


def pinned_data_dirs(profiles_root: Path) -> dict:
    """{resolved data dir: profile} for every local profile's dataDir pref."""
    out = {}
    if not profiles_root.is_dir():
        return out
    for prefs in sorted(profiles_root.glob("*/prefs.js")):
        for match in _PREF_DATADIR.finditer(prefs.read_text(encoding="utf-8", errors="replace")):
            out[str(Path(match.group(1)).resolve())] = str(prefs.parent)
    return out


def settled(state: dict) -> bool:
    """One read of the sitter's state says the census is done. The census
    must also have covered the library (`scanned >= total > 0`): a copy
    carries the live sitter's cache, so the sitter arms on it before its
    census has begun, and an idle read then is not a settled one."""
    total, scanned = state.get("total") or 0, state.get("scanned") or 0
    return (bool(state.get("ok")) and state.get("pending") == 0
            and not state.get("busy") and state.get("phase") not in WORKING_PHASES
            and total > 0 and scanned >= total)


class Sampler:
    """`sdt_stall_probe.snapshot()` of the Zotero process every `interval`,
    keeping the last `window` seconds, on a thread of its own."""

    def __init__(self, pid: int, interval: float = 5.0, window: float = 600.0):
        self.pid, self.interval = pid, interval
        self.shots = deque(maxlen=max(2, int(window / interval) + 1))
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.is_set():
            try:
                self.shots.append(stall.snapshot(self.pid))
            except stall.ProbeError:
                return
            self.stop.wait(self.interval)

    def reading(self) -> dict:
        shots = list(self.shots)
        try:
            summary = stall.summarize_cpu(shots)
        except stall.ProbeError as exc:
            return {"ok": False, "why": str(exc)}
        summary.pop("perInterval", None)
        return {"ok": True, "pid": self.pid, **summary,
                "worker": stall.worker_cpu(summary)}


def wait_for_settle(client, log, args, sampler: Sampler) -> dict:
    """Poll the sitter's state until `settled()` holds for `settle_polls`
    consecutive reads, or the deadline passes. Keeps a trace of every read
    whose phase or pending count changed."""
    started = time.monotonic()
    deadline = started + args.settle_timeout
    trace, streak, last_key, state = [], 0, None, {}
    polls = 0
    while True:
        state = eval_action(client, STATE, args.eval_timeout, log, "state")
        polls += 1
        key = (state.get("phase"), state.get("pending"), state.get("busy"))
        elapsed = round(time.monotonic() - started)
        if key != last_key or polls % 20 == 0:
            trace.append({"t": elapsed, **{k: state.get(k) for k in (
                "phase", "busy", "pending", "scanned", "total", "completed", "failed")}})
            log.write(f"clone state t={elapsed}s {state}")
            last_key = key
        streak = streak + 1 if settled(state) else 0
        if streak >= args.settle_polls:
            return {"settled": True, "seconds": elapsed, "polls": polls,
                    "final": state, "trace": trace, "cpu": sampler.reading()}
        if time.monotonic() >= deadline:
            return {"settled": False, "seconds": elapsed, "polls": polls,
                    "final": state, "trace": trace, "cpu": sampler.reading()}
        time.sleep(args.poll_interval)


def quit_zotero(client, proc, log, eval_timeout: float) -> str:
    """Quit the way a user does, so Zotero closes its database itself; fall
    back to a signal only if it will not go. Returns how it went."""
    try:
        result = eval_action(client, QUIT, eval_timeout, log, "quit")
    except (RDPConnectionClosed, RDPTimeout, OSError) as exc:
        result = {"ok": True, "note": f"connection closed on quit: {exc}"}
    try:
        proc.wait(timeout=180)
        return f"graceful ({result})"
    except subprocess.TimeoutExpired:
        stop_zotero(proc)
        return f"signalled after a graceful quit did not finish in 180 s ({result})"


def _sqlite_sidecars(data_dir: Path) -> dict:
    return {p.name: p.stat().st_size for p in sorted(data_dir.glob("*.sqlite-*"))}


def _record_segment(ledger_records: list, name: str, before: dict, after: dict) -> dict:
    rec = integrity.record(name, integrity.diff(before, after))
    ledger_records.append(rec)
    return rec


def run_clone(args, log: Log) -> dict:
    data_dir = args.data_dir.resolve()
    pinned = pinned_data_dirs(args.profiles)
    if str(data_dir) in pinned:
        raise CloneFailure(f"REFUSING: {data_dir} is the data directory of profile "
                           f"{pinned[str(data_dir)]} -- this driver runs on a copy only")
    if not (data_dir / "zotero.sqlite").is_file():
        raise NotRunError(f"{data_dir} holds no zotero.sqlite")

    binary = find_zotero_bin(args.zotero_bin)
    app_ini = binary.parent / "app" / "application.ini"
    xpi_path = args.xpi or args.work_dir / "sdt-sitter-clone.xpi"
    if args.xpi is None:
        build_xpi(xpi_path)
    log.write(f"clone xpi={xpi_path} data_dir={data_dir}")

    out = {"dataDir": str(data_dir), "sidecars_before_launch": _sqlite_sidecars(data_dir)}
    t0 = time.monotonic()
    log.write("clone pre-launch snapshot (no Zotero running)")
    pre_launch = integrity.snapshot(data_dir)
    out["pre_launch_snapshot_s"] = round(time.monotonic() - t0)

    profile = setup_profile_existing_data(args.work_dir, data_dir)
    proc, stdout_log = launch_zotero(binary, app_ini, profile, args.port,
                                     args.work_dir / "zotero-stdout.log")
    log.write(f"clone launched zotero pid={proc.pid} profile={profile}")
    client, sampler = None, None
    try:
        try:
            wait_for_port("127.0.0.1", args.port, time.monotonic() + 120)
        except TimeoutError as exc:
            raise NotRunError(f"debugger port never came up: {exc}") from exc
        try:
            client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)
        except RuntimeError as exc:
            raise NotRunError(f"could not attach over RDP: {exc}") from exc

        ready = eval_action(client, ZOTERO_READY, max(args.eval_timeout, 600.0), log,
                            "zotero ready")
        if not ready.get("ok"):
            raise NotRunError(f"Zotero's data layer never came up: {ready}")
        if Path(ready["dataDir"]).resolve() != data_dir:
            raise CloneFailure(f"REFUSING: Zotero opened {ready['dataDir']}, not {data_dir}")

        ledger = integrity.Ledger(data_dir, log.write, settle=args.snapshot_settle,
                                  timeout=args.snapshot_timeout)
        records = args.integrity_records = ledger.records
        t0 = time.monotonic()
        try:
            ledger.start()
        except integrity.NotQuiesced as exc:
            raise CloneFailure(f"integrity baseline: {exc}") from exc
        out["baseline_snapshot_s"] = round(time.monotonic() - t0)
        startup = integrity.diff(pre_launch, ledger.last)
        out["startup"] = {"files": startup.files, "tables": startup.tables,
                          "housekeeping": startup.housekeeping,
                          "note": "Zotero's own start-up on a fresh profile; recorded, "
                                  "not judged"}
        log.write(f"clone startup diff (not judged): {out['startup']}")

        installed = eval_action(client, install_or_replace_code(xpi_path),
                                args.eval_timeout, log, "install")
        if not installed.get("ok"):
            raise CloneFailure(f"the XPI would not install: {installed}")
        out["installed"] = installed
        live = poll_until_armed(client, log, args.eval_timeout,
                                time.monotonic() + args.arm_timeout)
        if Path(live["dataDir"]).resolve() != data_dir:
            raise CloneFailure(f"REFUSING: the sitter armed over {live['dataDir']}, "
                               f"not {data_dir}")
        out["armed"] = live
        log.write(f"clone armed: {live}")

        sampler = Sampler(proc.pid, window=args.cpu_window)
        sampler.thread.start()
        out["settle"] = wait_for_settle(client, log, args, sampler)
        sampler.stop.set()
        log.write(f"clone settle: settled={out['settle']['settled']} "
                  f"seconds={out['settle']['seconds']} final={out['settle']['final']}")

        census_violation = None
        try:
            ledger.segment("census")
        except integrity.IntegrityViolation as exc:
            census_violation = str(exc)
        except integrity.NotQuiesced as exc:
            census_violation = f"not quiesced: {exc}"
        running_after = ledger.last

        out["quit"] = quit_zotero(client, proc, log, args.eval_timeout)
        client = None
        out["sidecars_after_quit"] = _sqlite_sidecars(data_dir)
        after_quit = integrity.snapshot(data_dir)
        quit_rec = _record_segment(records, "quit", running_after, after_quit)
        log.write(f"clone quit: {out['quit']} sidecars={out['sidecars_after_quit']} "
                  f"segment={quit_rec['verdict']} {quit_rec['violations']}")
        out["integrity"] = records

        problems = []
        if census_violation:
            problems.append(f"census segment: {census_violation}")
        if quit_rec["violations"]:
            problems.append("quit segment: " + "; ".join(quit_rec["violations"]))
        if not out["settle"]["settled"]:
            problems.append(f"the census never settled in {args.settle_timeout:.0f} s: "
                            f"{out['settle']['final']}")
        out["ok"] = not problems
        out["problems"] = problems
        return out
    finally:
        if sampler is not None:
            sampler.stop.set()
        if client is not None:
            try:
                client.close()
            except (RDPConnectionClosed, RDPTimeout, OSError):
                pass
        stop_zotero(proc)
        stdout_log.close()


def _git_head() -> str | None:
    out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, check=False)
    return out.stdout.strip() or None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, required=True,
                        help="the COPY to run on (bench/sitter_clone_data.py made it)")
    parser.add_argument("--work-dir", type=Path, required=True,
                        help="a fresh directory for the profile, XPI and logs")
    parser.add_argument("--record", type=Path, default=None,
                        help="where to write the run record (JSON)")
    parser.add_argument("--clone-record", type=Path, default=None,
                        help="the JSON bench/sitter_clone_data.py wrote, carried "
                             "into the run record")
    parser.add_argument("--note", default="", help="free text carried into _run")
    parser.add_argument("--zotero-bin",
                        default=str(Path.home() / ".local" / "Zotero_linux-x86_64" / "zotero"))
    parser.add_argument("--xpi", type=Path, default=None)
    parser.add_argument("--profiles", type=Path, default=Path.home() / ".zotero" / "zotero",
                        help="local profiles whose pinned data directories are refused")
    parser.add_argument("--port", type=int, default=6118)
    parser.add_argument("--eval-timeout", type=float, default=30.0)
    parser.add_argument("--arm-timeout", type=float, default=300.0)
    parser.add_argument("--poll-interval", type=float, default=15.0)
    parser.add_argument("--settle-polls", type=int, default=4,
                        help="consecutive settled reads required")
    parser.add_argument("--settle-timeout", type=float, default=6 * 3600.0)
    parser.add_argument("--cpu-window", type=float, default=600.0,
                        help="seconds of CPU samples kept for the stall reading")
    parser.add_argument("--snapshot-settle", type=float, default=5.0)
    parser.add_argument("--snapshot-timeout", type=float, default=3600.0)
    args = parser.parse_args(argv)
    args.zotero_bin = Path(args.zotero_bin)
    args.integrity_records = []

    args.work_dir.mkdir(parents=True, exist_ok=True)
    if any(args.work_dir.iterdir()):
        print(f"--work-dir {args.work_dir} is not empty", file=sys.stderr)
        return USAGE
    log_path = args.work_dir / "clone-log.txt"
    if log_path.suffix == ".log":
        print(refuse_dot_log(log_path), file=sys.stderr)
        return USAGE

    log = Log(log_path)
    started = time.monotonic()
    when = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    code, outcome = FAIL, {}
    try:
        outcome = run_clone(args, log)
        code = PASS if outcome["ok"] else FAIL
    except NotRunError as exc:
        outcome, code = {"ok": False, "error": f"NOT-RUN: {exc}"}, NOT_RUN
    except Exception as exc:  # noqa: BLE001 -- an unattended run records its own crash
        outcome = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                   "integrity": args.integrity_records}
        code = FAIL
    finally:
        wall = round(time.monotonic() - started)
        manifest = json.loads((REPO / "plugins" / "sdt-sitter" / "manifest.json")
                              .read_text(encoding="utf-8"))
        rec = {"ok": outcome.get("ok", False),
               "_run": {"version": manifest.get("version"), "host": platform.node(),
                        "when": when, "wall_seconds": wall, "main": _git_head(),
                        "script": "bench/sitter_clone_rung.py",
                        "zotero_bin": str(args.zotero_bin), "note": args.note},
               "clone": (json.loads(args.clone_record.read_text(encoding="utf-8"))
                         if args.clone_record else None),
               **outcome}
        text = json.dumps(rec, indent=1, default=str)
        if args.record:
            args.record.parent.mkdir(parents=True, exist_ok=True)
            args.record.write_text(text + "\n", encoding="utf-8")
        log.write(f"clone done code={code} wall={wall}s problems={outcome.get('problems')}")
        log.close()
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
