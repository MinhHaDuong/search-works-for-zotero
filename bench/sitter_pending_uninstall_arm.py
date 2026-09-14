#!/usr/bin/env python3
"""Ticket 0727, the arm no previous arm could run: an install that lands while a
STAGED uninstall of the same add-on id is pending, followed by a restart.

WHY THIS ARM DID NOT EXIST. `bench/sitter_volume_experiment.py`'s
`uninstall_code()` calls `addon.uninstall()` with no argument. In
`XPIInstall.sys.mjs` the parameter is `aForcePending`, so no argument means the
IMMEDIATE path: the add-on is gone when the call returns. The Add-ons window
calls `uninstall(true)`, which takes the other branch entirely --

    if (aForcePending) {
      // We create an empty directory in the staging directory to indicate
      // that an uninstall is necessary on next startup. ...
      stage.create(Ci.nsIFile.DIRECTORY_TYPE, ...);
      XPIDatabase.setAddonProperties(aAddon, { pendingUninstall: true });
      Services.prefs.setBoolPref(PREF_PENDING_OPERATIONS, true);
    }

-- a removal QUEUED FOR NEXT STARTUP. Arm 6's 24 replace/disable/enable cycles
therefore never put a pending uninstall on the record at all, and its bounded
negative says nothing about this axis. Reproducing what the author hit on
2026-09-14 needs the flag the UI passes and the rig never did.

THE CLAIM UNDER TEST, stated so it can fail: with a staged uninstall pending,
installing a fresh copy of the same id cleans the staging directory but does not
cancel the operation, so the restart completes the removal and deletes the copy
that was just installed.

    ARM      install -> uninstall(true) -> install -> restart  => add-on ABSENT
    CONTROL  install ->                    install -> restart  => add-on PRESENT

The control is the half that makes the arm mean anything: an add-on that
vanishes across a restart in BOTH arms is a rig defect or an ordinary
replacement bug, not this mechanism, and only running both tells them apart.

Nothing here touches the author's profile or library: a fresh profile directory
(refused if it already holds a prefs.js) and a data directory pinned beside it,
which is ticket 0782's lesson and the reason SEED_PREFS carries the dataDir
line at all.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bench"))

from sitter_volume_experiment import (  # noqa: E402
    ADDON_ID,
    SEED_PREFS,
    build_payload,
    install_or_replace_code,
    wait_for_port,
)
from sitter_watch import Log, connect_resilient  # noqa: E402


def stage_uninstall_code(addon_id: str) -> str:
    """`uninstall(true)` -- the Add-ons window's own call, and the one the rig
    has never made. Reports back what the host recorded so the arm can prove the
    pending state EXISTS before it installs over it; an arm that assumed the
    staging happened would be unable to tell this mechanism from a plain
    replacement."""
    lit = json.dumps(addon_id)
    return f"""
(async function() {{
  try {{
    const {{ AddonManager }} = ChromeUtils.importESModule(
      "resource://gre/modules/AddonManager.sys.mjs");
    const addon = await AddonManager.getAddonByID({lit});
    if (!addon) return JSON.stringify({{ok: false, reason: "not-found"}});
    await addon.uninstall(true);
    const after = await AddonManager.getAddonByID({lit});
    return JSON.stringify({{
      ok: true,
      stillReadable: !!after,
      pendingUninstall: after ? !!(after.pendingOperations &
        AddonManager.PENDING_UNINSTALL) : null,
      pendingOperationsPref: Services.prefs.getBoolPref(
        "extensions.pendingOperations", false),
    }});
  }} catch (e) {{
    return JSON.stringify({{ok: false, reason: "threw", error: String(e)}});
  }}
}})()
"""


def presence_code(addon_id: str) -> str:
    lit = json.dumps(addon_id)
    return f"""
(async function() {{
  try {{
    const {{ AddonManager }} = ChromeUtils.importESModule(
      "resource://gre/modules/AddonManager.sys.mjs");
    const addon = await AddonManager.getAddonByID({lit});
    return JSON.stringify({{
      ok: true,
      present: !!addon,
      version: addon ? addon.version : null,
      active: addon ? !!addon.isActive : null,
    }});
  }} catch (e) {{
    return JSON.stringify({{ok: false, reason: "threw", error: String(e)}});
  }}
}})()
"""


def staged_entries(profile: Path) -> list:
    d = profile / "extensions" / "staged"
    try:
        return sorted(p.name for p in d.iterdir())
    except FileNotFoundError:
        return []


def xpi_present(profile: Path, addon_id: str) -> bool:
    return (profile / "extensions" / f"{addon_id}.xpi").exists()


def names_addon(profile: Path, addon_id: str) -> bool:
    try:
        return addon_id in (profile / "extensions.json").read_text(errors="replace")
    except OSError:
        return False


class Run:
    def __init__(self, label: str, profile: Path, args, log, logpath):
        self.label, self.profile, self.args, self.log = label, profile, args, log
        self.logpath = logpath
        self.proc = None
        self.client = None

    def say(self, msg):
        line = f"[{self.label}] {time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        self.log.write(line + "\n")
        self.log.flush()

    def seed(self, data_dir: Path):
        if (self.profile / "prefs.js").exists():
            raise SystemExit(f"refusing to reuse a profile that has a prefs.js: "
                             f"{self.profile}")
        self.profile.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        if (data_dir / "zotero.sqlite").exists():
            raise SystemExit(f"refusing: {data_dir} already holds a library")
        (self.profile / "prefs.js").write_text(
            SEED_PREFS.replace("{data_dir}", str(data_dir)), encoding="utf-8")

    def launch(self):
        install_dir = Path(self.args.zotero_bin).resolve().parent
        env = {**os.environ, "MOZ_ALLOW_DOWNGRADE": "1",
               "MOZ_LEGACY_PROFILES": "1", "MOZ_ENABLE_WAYLAND": "1"}
        cmd = [str(install_dir / "zotero-bin"), "-app",
               str(install_dir / "app" / "application.ini")]
        if self.args.headless:
            cmd.append("--headless")
        cmd += ["--start-debugger-server", str(self.args.port),
                "--profile", str(self.profile)]
        self.proc = subprocess.Popen(cmd, stdout=self.log,
                                     stderr=subprocess.STDOUT, env=env)
        self.say(f"launched pid={self.proc.pid}")
        wait_for_port("127.0.0.1", self.args.port, time.monotonic() + 120)
        # `connect_resilient` and not a bare `.connect()`: ticket 0766 found the
        # single-shot attach unreliable against this host, and it also performs
        # the `attach_chrome_target` step an eval needs.
        self.client = connect_resilient(
            "127.0.0.1", self.args.port, self.args.eval_timeout,
            Log(self.logpath))
        self.say("attached")

    def ev(self, code, what):
        raw = self.client.eval_js(code, timeout=self.args.eval_timeout)
        try:
            out = json.loads(raw)
        except (TypeError, ValueError):
            out = {"ok": False, "raw": raw}
        self.say(f"{what}: {out}")
        return out

    def stop(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=30)
            self.say(f"stopped pid={self.proc.pid}")
            self.proc = None

    def disk(self, when):
        self.say(f"DISK {when}: staged={staged_entries(self.profile)} "
                 f"xpi={xpi_present(self.profile, ADDON_ID)} "
                 f"named={names_addon(self.profile, ADDON_ID)}")


def one_arm(label, stage_it, args, xpi, log, logpath) -> dict:
    profile = Path(args.workdir) / f"{label}-profile"
    data_dir = Path(args.workdir) / f"{label}-data"
    for p in (profile, data_dir):
        if p.exists():
            shutil.rmtree(p)
    run = Run(label, profile, args, log, logpath)
    result = {"arm": label, "staged_uninstall": stage_it}
    try:
        run.seed(data_dir)
        run.launch()

        first = run.ev(install_or_replace_code(xpi), "install #1")
        result["install1"] = first
        run.disk("after install #1")

        if stage_it:
            staged = run.ev(stage_uninstall_code(ADDON_ID), "uninstall(true)")
            result["stage"] = staged
            run.disk("after uninstall(true)")
            result["staged_on_disk"] = staged_entries(profile)

        second = run.ev(install_or_replace_code(xpi), "install #2")
        result["install2"] = second
        run.disk("after install #2")

        # DWELL, and it is the whole point of the second version of this arm.
        # The author's add-on was erased 3.83 s after the install LANDED, in the
        # same session, before any restart. The first version checked presence
        # 0.4 s after install #2 and restarted immediately, so it could not have
        # observed the loss even if the loss were happening -- it looked before
        # the window opened, which is this repository's oldest trap wearing new
        # clothes. Sampled once a second rather than only at the end, so a
        # disappearance is timestamped instead of merely noticed.
        result["dwell"] = []
        start = time.monotonic()
        while time.monotonic() - start < args.dwell:
            time.sleep(1.0)
            t = round(time.monotonic() - start, 1)
            here = run.ev(presence_code(ADDON_ID), f"presence +{t}s")
            result["dwell"].append({
                "t": t,
                "present": here.get("present"),
                "xpi": xpi_present(profile, ADDON_ID),
                "named": names_addon(profile, ADDON_ID),
                "staged": staged_entries(profile),
            })
            if not here.get("present"):
                run.say(f"!!! DISAPPEARED IN-SESSION at +{t}s, before any restart")
                break
        run.disk("after dwell")
        result["before_restart"] = run.ev(presence_code(ADDON_ID), "presence before restart")

        run.say("--- restarting Zotero ---")
        run.stop()
        time.sleep(args.restart_gap)
        run.disk("while stopped")
        run.launch()
        time.sleep(args.settle)

        after = run.ev(presence_code(ADDON_ID), "presence AFTER restart")
        result["after_restart"] = after
        run.disk("after restart")
        result["final_disk"] = {
            "staged": staged_entries(profile),
            "xpi": xpi_present(profile, ADDON_ID),
            "named": names_addon(profile, ADDON_ID),
        }
    finally:
        run.stop()
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", required=True,
                    help="scratch directory; per-arm profiles are created under it")
    ap.add_argument("--xpi", help="payload to install; built from the tree if omitted")
    ap.add_argument("--zotero-bin", default="/home/haduong/.local/bin/zotero")
    ap.add_argument("--port", type=int, default=6899)
    ap.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--eval-timeout", type=float, default=60.0)
    ap.add_argument("--restart-gap", type=float, default=5.0)
    ap.add_argument("--dwell", type=float, default=20.0,
                    help="seconds to stay live after install #2 before restarting. "
                         "The observed loss was at +3.83 s IN-SESSION, so an arm "
                         "that restarts sooner cannot see it.")
    ap.add_argument("--settle", type=float, default=15.0)
    ap.add_argument("--json-out", help="write the two arms' results here")
    args = ap.parse_args(argv)

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)

    if args.xpi:
        xpi = Path(args.xpi).resolve()
    else:
        xpi = work / "payload.xpi"
        build_payload("0.4.13", xpi)

    logpath = work / "arm.log"
    results = []
    with logpath.open("a", encoding="utf-8") as log:
        for label, stage_it in (("control", False), ("arm", True)):
            results.append(one_arm(label, stage_it, args, xpi, log, logpath))
            args.port += 1  # a fresh port per arm; the old server may linger

    print("\n================ RESULT ================")
    verdict = {}
    for r in results:
        present = (r.get("after_restart") or {}).get("present")
        verdict[r["arm"]] = present
        lost = [d for d in r.get("dwell", []) if not d["present"]]
        mark = f"at +{lost[0]['t']}s" if lost else "no"
        print(f"{r['arm']:<8} staged_uninstall={r['staged_uninstall']!s:<5} "
              f"in_session_loss={mark:<10} present_after_restart={present}")
    ok = verdict.get("control") is True and verdict.get("arm") is False
    print()
    if ok:
        print("REPRODUCED: the control survived the restart and the staged arm did not.")
    elif verdict.get("control") is not True:
        print("NOT-ESTABLISHED: the CONTROL did not survive, so this rig cannot "
              "attribute the arm's loss to the pending uninstall.")
    else:
        print("NOT REPRODUCED: the staged arm survived too. The claim is wrong, "
              "or the mechanism needs something this arm does not do.")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
