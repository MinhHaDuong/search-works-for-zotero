#!/usr/bin/env python3
"""Ticket 0727's deferred experiment: many install/replace/disable/enable
cycles in ONE continuous Zotero process, unattended, watching for the exact
disappearance signature 0727 has twice observed organically -- `extensions.json`
mutated to disabled, then the `.xpi` deleted from disk, with the running
instance otherwise alive. Four deliberate arms (first install, one
replacement, a pre-fix payload, one disable/re-enable) all survived; the one
untested candidate left is intermittency under VOLUME, which needs dozens of
cycles back to back rather than one of each. Ticket 0766 built the tool this
runs on (`bench/zotero_rdp_client.py`); this script is what actually drives
it, against a THROWAWAY profile, never the author's real library.

## The install/replace call, and why it is this call and not another

Every install and replace below runs the exact sequence
`chrome/toolkit/content/mozapps/extensions/aboutaddonsCommon.js`'s
`installAddonsFromFilePicker()` runs for a real "Install Add-on From File"
click -- `AddonManager.getInstallForFile(file, null, {source: "about:addons",
method: "install-from-file"})` then `AddonManager.installAddonFromAOMWithOptions`
with `preferUpdateOverInstall: true` -- cited in full, with the reasoning for
why `browser`/`uri` can be `null`/a throwaway URI, in ticket 0766's body. It
is NOT `AddonsActor.installTemporaryAddon`: that is Firefox's non-persistent
"Load Temporary Add-on" mechanism and does not exercise the same
`extensions.json` machinery, so it could not approach this ticket's
phenomenon at all, deliberate or not.

Disable/enable calls `addon.disable()`/`addon.enable()` on the `AddonWrapper`
returned by `AddonManager.getAddonByID` -- `modules/addons/XPIDatabase.sys.mjs`,
`AddonWrapper.prototype.{enable,disable}`, each a thin wrapper over
`addonFor(this).setUserDisabled(val)`. This is the same call the Zotero UI's
own disable/enable toggle makes.

## Two clocks, on purpose

`extensions.json` (read via `bench/host_addon_record.py`, the same reader
0727's own `bench/sdt_sitter_install.py` uses) LAGS the live in-process
`AddonManager` state -- confirmed empirically before this run: immediately
after `addon.enable()` resolves, a live `AddonManager.getAddonByID` query
already reports `isActive: true`, while `extensions.json`'s `active` field
still reads `false` for some interval afterward (the on-disk write is
debounced). So this script keeps two separate loops: a background WATCHER
polls only `extensions.json` + the `.xpi`'s presence on disk, at a fixed
cadence, logging a line ONLY on change -- because `extensions.json` is what
ticket 0727's disappearance signature is defined in terms of, and reading it
right after issuing an action would just describe the debounce, not the
disappearance. The action LOOP separately confirms each of its own
install/disable/enable calls succeeded via a live `AddonManager` query, which
is a different, faster-settling question ("did the call I just made take
effect") from "what does the host's persistent record now say".

## Never against the author's real profile or library

This script always launches its OWN Zotero process against a profile
directory you pass with `--profile` (create a fresh, empty directory for it;
this script pre-seeds the three `devtools.*` prefs `bench/zotero_rdp_client.py`
needs into `prefs.js` before first launch, so no `Run JavaScript` gesture and
no restart-after-arming step is needed here). It never touches
`~/.zotero/zotero/*/`. The add-on under test is packaged fresh, version-bumped
each cycle, into a scratch directory you pass with `--payload-dir`; nothing
under `plugins/sdt-sitter/` (the repository's real, released source) is ever
written to.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from host_addon_record import host_addon_record  # noqa: E402
from zotero_rdp_client import (  # noqa: E402
    RDPConnectionClosed,
    RDPError,
    RDPEvalError,
    RDPTimeout,
    ZoteroRDPClient,
)

#: The real plugin's own three delivered files (`bench/build_sdt_sitter.py`'s
#: own `DELIVERED`), read from the repository's real, released source and
#: never written back to it -- only `manifest.json`'s `version`/`name` fields
#: are patched, in a scratch copy, per cycle.
SITTER_SOURCE = REPO / "plugins" / "sdt-sitter"
ADDON_ID = json.loads((SITTER_SOURCE / "manifest.json").read_text(
    encoding="utf-8"))["applications"]["zotero"]["id"]

#: Prefs `bench/zotero_rdp_client.py` needs, seeded into a FRESH profile's
#: `prefs.js` before first launch -- see that module's own docstring and
#: `bench/zotero_arm_devtools_server.js` for the citations. A profile that
#: already has a `prefs.js` is refused (this script never edits a profile
#: that could be in use).
SEED_PREFS = """\
// Pre-seeded before first launch, ticket 0727's volume experiment.
user_pref("devtools.debugger.remote-enabled", true);
user_pref("devtools.debugger.prompt-connection", false);
user_pref("devtools.chrome.enabled", true);
user_pref("app.update.auto", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
"""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Log:
    """Appends timestamped lines to a file and echoes them to stdout, flushing
    every write -- a run that dies at hour 1 must not lose hour 1's lines to
    a buffer."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = open(path, "a", encoding="utf-8")  # noqa: SIM115

    def write(self, line: str) -> None:
        stamped = f"{utc_stamp()} {line}"
        print(stamped)
        self._fh.write(stamped + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def build_payload(version: str, out_path: Path) -> Path:
    """A scratch copy of the real sitter, `version` patched, otherwise
    byte-identical -- the isolation discipline 0727's arm 2 established: a
    version bump is the only variable a replacement should exercise."""
    manifest = json.loads((SITTER_SOURCE / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest["name"] = f"{manifest['name']} [0727 VOLUME EXPERIMENT, throwaway]"
    if out_path.exists():
        out_path.unlink()
    with zipfile.ZipFile(out_path, "x", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("manifest.json", json.dumps(manifest, indent=2))
        package.writestr("bootstrap.js", (SITTER_SOURCE / "bootstrap.js").read_bytes())
        package.writestr("scheduler.js", (SITTER_SOURCE / "scheduler.js").read_bytes())
    return out_path


def wait_for_port(host: str, port: int, deadline: float) -> None:
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"{host}:{port} never accepted a connection")


def connect_resilient(host: str, port: int, timeout: float, log: Log,
                       attempts: int = 5) -> ZoteroRDPClient:
    """Connect with bounded retries. Every attempt carries its own timeout,
    so a hung handshake (the `prompt-connection` trap this ticket's history
    already hit once) costs at most `timeout` seconds per try, never the rest
    of the run."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            client = ZoteroRDPClient.connect(host, port, timeout=timeout)
            client.attach_chrome_target(timeout=timeout)
            return client
        except (RDPError, OSError) as exc:
            last_error = exc
            log.write(f"driver warn connect attempt {attempt}/{attempts} failed: {exc}")
            time.sleep(min(2 * attempt, 10))
    raise RuntimeError(f"could not connect after {attempts} attempts: {last_error}")


def eval_action(client: ZoteroRDPClient, code: str, timeout: float, log: Log,
                 action_name: str) -> dict:
    """Run one action, parse its JSON `{"ok": ...}` result, and log a
    one-line anomaly report rather than raising past the caller for anything
    that is not a hard protocol failure -- an install that legitimately
    failed (a bad payload, a locked file) is data this experiment wants
    recorded, not a crash that ends a two-hour run at cycle 3."""
    try:
        raw = client.eval_js(code, timeout=timeout)
    except RDPEvalError as exc:
        log.write(f"driver warn {action_name} raised: {exc}")
        return {"ok": False, "reason": "rdp-eval-error", "error": str(exc)}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        log.write(f"driver warn {action_name} returned non-JSON: {raw!r}")
        return {"ok": False, "reason": "non-json-result", "raw": raw}
    if not parsed.get("ok"):
        log.write(f"driver warn {action_name} reported failure: {parsed}")
    return parsed


def install_or_replace_code(xpi_path: Path) -> str:
    path_literal = json.dumps(str(xpi_path))
    return f"""
(async function() {{
  try {{
    const {{ FileUtils }} = ChromeUtils.importESModule(
      "resource://gre/modules/FileUtils.sys.mjs", {{ global: "contextual" }});
    const {{ AddonManager }} = ChromeUtils.importESModule(
      "resource://gre/modules/AddonManager.sys.mjs");
    const file = new FileUtils.File({path_literal});
    const install = await AddonManager.getInstallForFile(
      file, null, {{ source: "about:addons", method: "install-from-file" }});
    if (!install) {{
      return JSON.stringify({{ok: false, reason: "no-install-object"}});
    }}
    const outcome = await new Promise((resolve) => {{
      install.addListener({{
        onInstallFailed: (inst) => resolve(
          {{ok: false, reason: "install-failed", error: inst.error}}),
        onDownloadFailed: (inst) => resolve(
          {{ok: false, reason: "download-failed", error: inst.error}}),
        onInstallCancelled: () => resolve(
          {{ok: false, reason: "install-cancelled"}}),
        onInstallEnded: (inst, addon) => resolve(
          {{ok: true, id: addon.id, version: addon.version}}),
      }});
      AddonManager.installAddonFromAOMWithOptions(
        null, Services.io.newURI("about:blank"), install,
        {{preferUpdateOverInstall: true}});
    }});
    return JSON.stringify(outcome);
  }} catch (e) {{
    return JSON.stringify({{ok: false, reason: "threw", error: String(e)}});
  }}
}})()
"""


def disable_enable_code(addon_id: str, want_disabled: bool) -> str:
    id_literal = json.dumps(addon_id)
    method = "disable" if want_disabled else "enable"
    return f"""
(async function() {{
  try {{
    const {{ AddonManager }} = ChromeUtils.importESModule(
      "resource://gre/modules/AddonManager.sys.mjs");
    const addon = await AddonManager.getAddonByID({id_literal});
    if (!addon) return JSON.stringify({{ok: false, reason: "not-found"}});
    await addon.{method}();
    return JSON.stringify({{ok: true, isActive: addon.isActive,
                            userDisabled: addon.userDisabled}});
  }} catch (e) {{
    return JSON.stringify({{ok: false, reason: "threw", error: String(e)}});
  }}
}})()
"""


def format_state(state: dict, xpi_present: bool, zotero_pid: int) -> str:
    """The exact grammar `verification/SDT-SITTER-DISAPPEARANCE-0727.md`'s
    prior arms used, so this run's log reads as one more arm of the same
    record rather than a format nobody else's tooling recognizes."""
    xpi = "present" if xpi_present else "absent"
    if not state.get("read"):
        return f"record=unreadable:{state.get('why')} xpi={xpi} zotero_pid={zotero_pid}"
    if not state.get("present"):
        return f"record=absent xpi={xpi} zotero_pid={zotero_pid}"
    return (f"record=present:{state.get('version')}:active={state.get('active')} "
            f"xpi={xpi} zotero_pid={zotero_pid}")


class Watcher:
    """Polls `extensions.json` + the `.xpi`'s presence on disk on a fixed
    cadence and logs a line ONLY on change -- `scratchpad/sitter-watch.sh`'s
    own discipline (ticket 0727's history): a quiet log is "nothing moved", a
    line is a transition, stamped. Runs independently of the action loop's
    cadence, because the two clocks this module's docstring describes mean an
    action-adjacent sample would describe the write debounce, not a real
    transition.
    """

    def __init__(self, profile: Path, addon_id: str, log: Log,
                 get_pid, poll_seconds: float = 1.5):
        self.profile = profile
        self.addon_id = addon_id
        self.log = log
        self.get_pid = get_pid
        self.poll_seconds = poll_seconds
        self.xpi_path = profile / "extensions" / f"{addon_id}.xpi"
        self.disappearance = threading.Event()
        self._stop = threading.Event()
        self._last_line = None
        self._was_present = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop.is_set():
            state = host_addon_record(self.profile, self.addon_id)
            xpi_present = self.xpi_path.exists()
            line = format_state(state, xpi_present, self.get_pid())
            if line != self._last_line:
                self.log.write(line)
                self._last_line = line
                now_present = bool(state.get("read") and state.get("present"))
                if self._was_present and not now_present:
                    self.log.write(
                        "watcher ALERT disappearance signature: record went "
                        "from present to absent with no uninstall issued by "
                        "this driver"
                    )
                    self.disappearance.set()
                self._was_present = now_present
            self._stop.wait(self.poll_seconds)


def run_cycle(client: ZoteroRDPClient, cycle: int, version: str,
              payload_dir: Path, log: Log, timeout: float) -> None:
    xpi = build_payload(version, payload_dir / f"sdt-sitter-{version}.xpi")
    log.write(f"driver cycle {cycle} installing version {version}")
    result = eval_action(client, install_or_replace_code(xpi), timeout, log,
                          f"cycle {cycle} install/replace")
    if not result.get("ok"):
        return
    log.write(f"driver cycle {cycle} disabling")
    eval_action(client, disable_enable_code(ADDON_ID, True), timeout, log,
                f"cycle {cycle} disable")
    log.write(f"driver cycle {cycle} enabling")
    eval_action(client, disable_enable_code(ADDON_ID, False), timeout, log,
                f"cycle {cycle} enable")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, required=True,
                         help="A fresh, empty directory. Refused if it "
                              "already has a prefs.js.")
    parser.add_argument("--payload-dir", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--zotero-bin", default="/opt/zotero7/zotero")
    parser.add_argument("--port", type=int, default=6000)
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--burst-cycles", type=int, default=8,
                         help="Rapid REPLACEMENTS right after the first "
                              "install, mimicking the organic 2026-09-08 "
                              "recurrence shape more closely than one "
                              "replacement at a time.")
    parser.add_argument("--burst-interval-seconds", type=float, default=8.0)
    parser.add_argument("--spaced-cycles", type=int, default=42,
                         help="Additional replace/disable/enable cycles "
                              "after the burst, spaced out. "
                              "burst-cycles + spaced-cycles should total "
                              "around 50.")
    parser.add_argument("--spaced-interval-seconds", type=float, default=120.0)
    parser.add_argument("--max-minutes", type=float, default=120.0)
    parser.add_argument("--eval-timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    args.profile.mkdir(parents=True, exist_ok=True)
    args.payload_dir.mkdir(parents=True, exist_ok=True)
    prefs_path = args.profile / "prefs.js"
    if prefs_path.exists():
        print(f"refusing to run against {args.profile}: prefs.js already "
              f"exists -- this must be a fresh profile, not one that could "
              f"be in use", file=sys.stderr)
        return 2
    prefs_path.write_text(SEED_PREFS, encoding="utf-8")

    log = Log(args.log)
    log.write(f"driver starting: profile={args.profile} addon_id={ADDON_ID} "
              f"burst_cycles={args.burst_cycles} spaced_cycles={args.spaced_cycles} "
              f"max_minutes={args.max_minutes}")

    stdout_log = open(args.profile.parent / "zotero-stdout.log", "a",  # noqa: SIM115
                      encoding="utf-8")
    # `--zotero-bin` names the launcher wrapper script (`/opt/zotero7/zotero`),
    # but that wrapper is a plain bash script that runs the real `zotero-bin`
    # as an ordinary (non-`exec`'d) child and then exits once its own `bash`
    # returns -- observed directly in a dry run: `subprocess.Popen`'s own pid
    # stopped existing seconds in, while the actual `zotero-bin` process (a
    # DIFFERENT pid) kept running as an orphan, un-killable through the
    # wrapper's pid. So this launches `zotero-bin` directly, replicating the
    # wrapper's own three env vars (read from the wrapper script itself)
    # rather than going through it, so `proc.pid` names a process this
    # script can actually terminate at the end of a 2-hour run.
    install_dir = Path(args.zotero_bin).resolve().parent
    env = {
        **os.environ,
        "MOZ_ALLOW_DOWNGRADE": "1",
        "MOZ_LEGACY_PROFILES": "1",
        "MOZ_ENABLE_WAYLAND": "1",
    }
    cmd = [str(install_dir / "zotero-bin"), "-app", str(install_dir / "app" / "application.ini")]
    if args.headless:
        cmd.append("--headless")
    cmd += ["--start-debugger-server", str(args.port), "--profile", str(args.profile)]
    proc = subprocess.Popen(cmd, stdout=stdout_log, stderr=subprocess.STDOUT, env=env)
    log.write(f"driver launched zotero pid={proc.pid}: {' '.join(cmd)}")

    def get_pid() -> int:
        return proc.pid

    watcher = Watcher(args.profile, ADDON_ID, log, get_pid)
    exit_code = 0
    try:
        wait_for_port("127.0.0.1", args.port, time.monotonic() + 60)
        watcher.start()
        client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)

        deadline = time.monotonic() + args.max_minutes * 60
        cycle = 0

        # Cycle 0: the one genuine FIRST install into a never-before-used
        # process -- everything after this is a REPLACE.
        cycle += 1
        run_cycle(client, cycle, "9.0.0", args.payload_dir, log, args.eval_timeout)

        # Burst phase: rapid replacements, mimicking the organic recurrence
        # shape (several GUI-menu replacements in one continuously-running
        # process, close together) more closely than any prior deliberate arm.
        for i in range(1, args.burst_cycles + 1):
            if watcher.disappearance.is_set() or time.monotonic() > deadline:
                break
            cycle += 1
            time.sleep(args.burst_interval_seconds)
            try:
                run_cycle(client, cycle, f"9.{cycle}.0", args.payload_dir, log,
                          args.eval_timeout)
            except (RDPConnectionClosed, RDPTimeout) as exc:
                log.write(f"driver warn cycle {cycle} RDP call failed: {exc}; reconnecting")
                client.close()
                client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)

        # Spaced phase: the rest of the volume budget.
        for i in range(1, args.spaced_cycles + 1):
            if watcher.disappearance.is_set() or time.monotonic() > deadline:
                break
            cycle += 1
            time.sleep(args.spaced_interval_seconds)
            try:
                run_cycle(client, cycle, f"9.{cycle}.0", args.payload_dir, log,
                          args.eval_timeout)
            except (RDPConnectionClosed, RDPTimeout) as exc:
                log.write(f"driver warn cycle {cycle} RDP call failed: {exc}; reconnecting")
                client.close()
                client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)

        if watcher.disappearance.is_set():
            log.write(f"driver REPRODUCED after {cycle} cycles -- stopping early, "
                      f"this is the finding")
            exit_code = 3
        else:
            log.write(f"driver completed {cycle} cycles with no disappearance observed")
        client.close()
    except Exception as exc:  # noqa: BLE001 -- an unattended run must log its own crash
        log.write(f"driver FATAL {type(exc).__name__}: {exc}")
        exit_code = 1
    finally:
        watcher.stop()
        log.write(f"driver terminating zotero pid={proc.pid}")
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        stdout_log.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
