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

## What arm 5 held fixed, and what this widens (2026-09-12)

Arm 5 repeated ONE action -- a byte-identical payload, version string apart --
at TWO fixed cadences, in a process that never restarted, over an EMPTY
library. Its negative result reads stronger than it is: seventeen replacements
of an idle add-on is not the state either organic occurrence happened in. The
author asked whether the experiment explores anything or just waits and
watches; it waited. Three axes open here, and one of them matters more than
the other two.

**The library.** `--menagerie` imports the Multilingual Menagerie (ticket 0721,
`bench/fixtures/export/menagerie.ris` plus the `attachments/` directory that
`make menagerie-package` assembles) into the throwaway profile before the first
install, so the sitter is censusing and EXTRACTING while it is replaced under
itself -- holding native worker handles, writing its cache, touching the disk.
That is where both occurrences happened and where no arm has ever put it.
Running without it now takes `--allow-empty-library` and says so in the log,
because the alternative is another run whose negative result is weaker than it
reads. The RIS names 114 attachments by relative path; the BYTES come from the
recipe's fetch cache, which lives on the author's machine, so the package has
to be assembled there -- a package whose files are not on disk is refused, since
a library of records without attachments leaves the sitter exactly as idle as
an empty one.

**Restarts.** `--restart-every N` stops Zotero and brings it back. Both organic
occurrences were in long sessions the author restarts on his own schedule, and
every arm so far -- arm 5 included -- ran in one continuous process. The watcher
stays ARMED across the restart: an add-on that is gone once Zotero is back is
the phenomenon in the shape originally reported, and the unreadable window a
restart opens is exactly what `poll_once` refuses to read as an absence.

**Randomisation.** `--seed` draws each cycle's action from `ACTIONS` and its
interval log-uniformly from 2 s to 10 min, instead of the fixed burst/spaced
script -- which is kept, and is what runs without a seed, as the control. The
seed and the whole plan are written into the log BEFORE the first cycle: a run
that finally reproduces has to be replayable from its log alone, or the
reproduction is a story rather than a finding. One action, `uninstall-then-
install`, produces the watcher's own signature deliberately, and runs inside
`Watcher.expect_absence` so the instrument cannot manufacture the defect it is
watching for.

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
import math
import os
import random
import socket
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from sitter_watch import (  # noqa: E402
    Log,
    Watcher,
    connect_resilient,
    make_ring_reader,
    refuse_dot_log,
)
from zotero_rdp_client import (  # noqa: E402
    RDPConnectionClosed,
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
// AddonManager's own reasoning about add-ons. Without it a reproduction says
// THAT the sitter was disabled and removed and never why, and the host's
// decision is the one account nothing else in this rig can reconstruct.
user_pref("extensions.logging.enabled", true);
// Zotero's debug output, where every non-trace record the add-on emits already
// goes -- the shutdown reason included. Stored rather than merely produced: by
// default it is discarded, which is why the two organic occurrences left none.
user_pref("extensions.zotero.debug.log", true);
user_pref("extensions.zotero.debug.store", true);
// The add-on's own switch, which gates its death certificate. On here, off in a
// released build, per the author's ruling of 2026-09-12.
user_pref("extensions.sdt-pack-sitter.debug", true);
user_pref("app.update.auto", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
"""


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


def uninstall_code(addon_id: str) -> str:
    """Remove the add-on outright. Only a randomised arm issues this, and only
    inside the watcher's `expect_absence` window -- an uninstall the driver
    performed is not the phenomenon, and must never be filed as one."""
    id_literal = json.dumps(addon_id)
    return f"""
(async function() {{
  try {{
    const {{ AddonManager }} = ChromeUtils.importESModule(
      "resource://gre/modules/AddonManager.sys.mjs");
    const addon = await AddonManager.getAddonByID({id_literal});
    if (!addon) return JSON.stringify({{ok: false, reason: "not-found"}});
    await addon.uninstall();
    return JSON.stringify({{ok: true}});
  }} catch (e) {{
    return JSON.stringify({{ok: false, reason: "threw", error: String(e)}});
  }}
}})()
"""


def import_menagerie_code(ris_path: Path) -> str:
    """Import the Menagerie's RIS into the throwaway profile's user library.

    The same sequence `bench/zotero-fulltext-plugin`'s `/import` endpoint runs
    (ticket 0721), lifted here rather than reached through it: that endpoint
    would mean installing a second add-on into the profile under test, and the
    profile under test is the experiment. `linkFiles: true` keeps the
    attachment bytes where they are and resolves each RIS `L1` path beside the
    file, which is what makes the package directory the whole fixture.

    Reports what Zotero made of it, including how many linked files are
    MISSING: a library of 103 records whose attachments are not on disk gives
    the sitter nothing to do, which is the state this import exists to leave.
    """
    path_literal = json.dumps(str(ris_path))
    return f"""
(async function() {{
  try {{
    const libraryID = Zotero.Libraries.userLibraryID;
    const translation = new Zotero.Translate.Import();
    translation.setLocation(Zotero.File.pathToFile({path_literal}));
    const translators = await translation.getTranslators();
    if (!translators || translators.length === 0) {{
      return JSON.stringify({{ok: false, reason: "no-translator"}});
    }}
    translation.setTranslator(translators[0]);
    const imported = await translation.translate(
      {{ libraryID, saveAttachments: true, linkFiles: true }});
    let attachments = 0, missing = 0;
    for (const item of imported) {{
      for (const id of (item.getAttachments ? item.getAttachments() : [])) {{
        attachments += 1;
        const attachment = Zotero.Items.get(id);
        const path = await attachment.getFilePathAsync();
        if (!path) missing += 1;
      }}
    }}
    return JSON.stringify({{ok: true, items: imported.length, attachments, missing}});
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


# `Log`, `Watcher`, `format_state` and `utc_stamp` come from
# `bench/sitter_watch.py`. This driver held the only versioned copy of them,
# which is exactly why nothing could watch the author's OWN profile while he
# worked -- where both organic occurrences happened (ticket 0727, the
# 2026-09-12 instrumentation round). The watcher there is this one, plus the
# evidence it takes when the signature fires.


def run_cycle(client: ZoteroRDPClient, cycle: int, version: str,
              payload_dir: Path, log: Log, timeout: float,
              disable_hold_seconds: float = 6.0) -> None:
    xpi = build_payload(version, payload_dir / f"sdt-sitter-{version}.xpi")
    log.write(f"driver cycle {cycle} installing version {version}")
    result = eval_action(client, install_or_replace_code(xpi), timeout, log,
                          f"cycle {cycle} install/replace")
    if not result.get("ok"):
        return
    log.write(f"driver cycle {cycle} disabling")
    eval_action(client, disable_enable_code(ADDON_ID, True), timeout, log,
                f"cycle {cycle} disable")
    # HELD, deliberately, and this pause is a positive control rather than
    # politeness. Arm 5 ran 17 disable() calls and its log carries zero
    # `active=False` lines, because this function disabled and re-enabled with no
    # pause while `extensions.json`'s `active` field is written late (ticket
    # 0766: `isActive: true` live immediately after enable(), the on-disk field
    # still false moments later). The disabled-state READ was therefore never
    # controlled, and a run that saw no disable could not tell "it never
    # happened" from "we never looked in time" -- the same shape of defect as a
    # scan whose all-clear is indistinguishable from its could-not-look. One
    # pause past the debounce is the whole control: the watcher must emit an
    # active=False line in every cycle, and a run whose log has none is a run
    # whose disabled-state reads prove nothing.
    time.sleep(disable_hold_seconds)
    log.write(f"driver cycle {cycle} enabling after a {disable_hold_seconds:g}s disabled hold")
    eval_action(client, disable_enable_code(ADDON_ID, False), timeout, log,
                f"cycle {cycle} enable")


#: What a randomised cycle can draw, and the weight it draws with. Every one of
#: them is a gesture the author performs or the host performs on its own; none
#: of them is a gesture only a driver could make. The weights are shaped by the
#: organic recurrences, not by uniformity: plain replacement is what he does
#: most, and what both occurrences were surrounded by.
ACTIONS = [
    ("replace", 50),
    ("replace-disable-enable", 20),
    ("replace-disable-immediately", 10),
    ("uninstall-then-install", 10),
    ("double-install", 10),
]


class Step:
    """One planned cycle: what to do, and how long to wait first."""

    def __init__(self, action: str, wait_seconds: float):
        self.action = action
        self.wait_seconds = wait_seconds


def plan_cycles(args, rng) -> list:
    """The whole run's shape, decided up front so the log can carry it.

    Deterministic by default -- the arm-5 script, burst then spaced, kept as
    the control any randomised run is compared against. With a seed, both the
    action and the interval are drawn, and the plan is written into the log
    before the first cycle runs: a run that reproduces has to be replayable
    from the log alone, and a plan printed only as it happens is a plan that
    dies with the process that was executing it.
    """
    total = args.burst_cycles + args.spaced_cycles
    if rng is None:
        return ([Step("replace-disable-enable", args.burst_interval_seconds)
                 for _ in range(args.burst_cycles)]
                + [Step("replace-disable-enable", args.spaced_interval_seconds)
                   for _ in range(args.spaced_cycles)])
    names = [name for name, _weight in ACTIONS]
    weights = [weight for _name, weight in ACTIONS]
    plan = []
    for _ in range(total):
        action = rng.choices(names, weights=weights)[0]
        # Log-uniform over three orders of magnitude, from "two menu items in a
        # row" to "after lunch". A uniform draw over the same range would spend
        # nearly all its cycles at the slow end and never revisit the rapid
        # succession the 2026-09-08 recurrence actually had.
        wait = round(10 ** rng.uniform(math.log10(2), math.log10(600)), 1)
        plan.append(Step(action, wait))
    return plan


def run_action(action: str, client: ZoteroRDPClient, cycle: int, version: str,
               args, log: Log, watcher) -> None:
    """Perform one drawn action.

    `uninstall-then-install` is the one that has to tell the watcher, and the
    reason `expect_absence` exists: the driver removing the add-on on purpose
    produces the exact on-disk signature the watcher is armed for, and a
    reproduction manufactured by the instrument would be investigated as though
    it were the defect.
    """
    xpi = build_payload(version, args.payload_dir / f"sdt-sitter-{version}.xpi")
    timeout = args.eval_timeout

    if action == "uninstall-then-install":
        with watcher.expect_absence(f"cycle {cycle} uninstall-then-install"):
            eval_action(client, uninstall_code(ADDON_ID), timeout, log,
                        f"cycle {cycle} uninstall")
            # Long enough for the host to write the removal it was asked for,
            # so the reinstall is a genuine first install into a process that
            # has had the add-on removed under it -- the 2026-09-06 shape.
            time.sleep(max(args.disable_hold_seconds, 2.0))
        eval_action(client, install_or_replace_code(xpi), timeout, log,
                    f"cycle {cycle} install after uninstall")
        return

    result = eval_action(client, install_or_replace_code(xpi), timeout, log,
                         f"cycle {cycle} install/replace")
    if not result.get("ok"):
        return

    if action == "double-install":
        second = build_payload(f"{version}1", args.payload_dir / f"sdt-sitter-{version}1.xpi")
        eval_action(client, install_or_replace_code(second), timeout, log,
                    f"cycle {cycle} second install")
        return

    if action == "replace":
        return

    eval_action(client, disable_enable_code(ADDON_ID, True), timeout, log,
                f"cycle {cycle} disable")
    if action == "replace-disable-enable":
        # The hold is the watcher's disabled-state positive control; see
        # `run_cycle`, which this replaces for the deterministic arm.
        time.sleep(args.disable_hold_seconds)
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
    parser.add_argument("--disable-hold-seconds", type=float, default=6.0,
                        help="how long to leave the add-on disabled in each cycle; the "
                             "positive control for the watcher's disabled-state read, and "
                             "0 disables that control (ticket 0727)")
    parser.add_argument("--evidence-dir", type=Path,
                        help="where the watcher copies extensions.json, the parked ring and "
                             "the death certificate if the signature fires")
    parser.add_argument("--menagerie", type=Path,
                        help="a Menagerie package directory (menagerie.ris beside "
                             "attachments/, as `make menagerie-package` assembles it), "
                             "imported into the throwaway profile before the cycles so the "
                             "sitter is doing real work while it is replaced")
    parser.add_argument("--allow-empty-library", action="store_true",
                        help="run without --menagerie. Refused by default: arm 5's negative "
                             "result was weaker than it read, because 17 replacements of an "
                             "IDLE add-on over an EMPTY library is not the state either "
                             "organic occurrence happened in")
    parser.add_argument("--warmup-seconds", type=float, default=120.0,
                        help="after the first install, let the sitter census and start "
                             "extracting before anything is replaced under it")
    parser.add_argument("--restart-every", type=int, default=0,
                        help="restart Zotero every N cycles (0: never, as every arm so far). "
                             "The one axis both organic occurrences had -- long sessions the "
                             "author restarts himself -- and that no arm has ever exercised")
    parser.add_argument("--seed", type=int,
                        help="draw each cycle's action and interval at random from this seed "
                             "instead of running the fixed burst/spaced script. The seed is "
                             "logged, and every cycle logs the action it drew, so a run that "
                             "reproduces is replayable")
    args = parser.parse_args(argv)

    if args.menagerie is None and not args.allow_empty_library:
        print("refusing to run against an empty library: pass --menagerie <package dir> "
              "(make menagerie-package, unzipped) or --allow-empty-library if you really "
              "mean to repeat arm 5's weakness.", file=sys.stderr)
        return 2
    if args.menagerie is not None:
        ris = args.menagerie / "menagerie.ris" if args.menagerie.is_dir() else args.menagerie
        if not ris.exists():
            print(f"no menagerie.ris at {ris}", file=sys.stderr)
            return 2
        linked = [line.split("-", 1)[1].strip()
                  for line in ris.read_text(encoding="utf-8-sig").splitlines()
                  if line.startswith("L1  -")]
        on_disk = sum(1 for name in linked if (ris.parent / name).exists())
        if on_disk == 0:
            print(f"{ris} names {len(linked)} attachments and none of them is on disk beside "
                  f"it -- this package has no bytes, and a library whose attachments do not "
                  f"exist leaves the sitter exactly as idle as an empty one. Assemble it "
                  f"with `make menagerie-package MENAGERIE_PACKAGE=...` on a machine that "
                  f"has the fetch cache.", file=sys.stderr)
            return 2
        args.menagerie_ris = ris
        args.menagerie_linked = (len(linked), on_disk)

    if args.log.suffix == ".log":
        print(refuse_dot_log(args.log), file=sys.stderr)
        return 2

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
              f"max_minutes={args.max_minutes} restart_every={args.restart_every}")
    if args.seed is None:
        log.write("driver arm: DETERMINISTIC (the arm-5 script, kept as the control)")
    else:
        # Printed before anything runs and repeated in the log, because a
        # reproduction drawn from an unrecorded seed is a reproduction nobody
        # can have twice.
        log.write(f"driver arm: RANDOMISED seed={args.seed} -- replay with --seed {args.seed}")
    if args.menagerie is None:
        log.write("driver library: EMPTY, by --allow-empty-library. The sitter has nothing "
                  "to index, so these cycles replace an IDLE add-on -- arm 5's weakness, "
                  "entered deliberately.")
    else:
        named, on_disk = args.menagerie_linked
        log.write(f"driver library: Menagerie at {args.menagerie_ris} "
                  f"({named} attachments named, {on_disk} on disk)")

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

    # A one-element list rather than a name, so the restart arm can replace the
    # process without the watcher's `get_pid` closing over a dead one: a log
    # whose pid column stops moving across a restart is a log that cannot say
    # which session a transition happened in, which is the column that broke
    # the 2026-09-06 reading open in the first place.
    running = [subprocess.Popen(cmd, stdout=stdout_log, stderr=subprocess.STDOUT, env=env)]
    log.write(f"driver launched zotero pid={running[0].pid}: {' '.join(cmd)}")

    def get_pid() -> int:
        return running[0].pid

    def stop_zotero(timeout: float = 30.0) -> None:
        proc = running[0]
        log.write(f"driver terminating zotero pid={proc.pid}")
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()

    def restart_zotero(client):
        """Stop Zotero and bring it back, reattaching.

        The axis no arm has ever exercised. Both organic occurrences happened in
        long sessions the author restarts on his own schedule, and every arm so
        far ran in one continuous process -- arm 5's included, which is why its
        negative result says nothing about what a restart does to a profile that
        has been replaced under a dozen times.

        The add-on going away across a restart is NOT excused: if the record is
        absent once Zotero is back, that is the phenomenon, in the shape the
        author originally reported it ("it disappears from the installed list").
        So the watcher is left armed, and the unreadable window a restart opens
        is exactly what `poll_once` is careful not to read as an absence."""
        if client is not None:
            client.close()
        stop_zotero()
        running[0] = subprocess.Popen(cmd, stdout=stdout_log, stderr=subprocess.STDOUT, env=env)
        log.write(f"driver restarted zotero pid={running[0].pid}")
        wait_for_port("127.0.0.1", args.port, time.monotonic() + 120)
        return connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)

    # The evidence side of the watcher, ticket 0727's 2026-09-12 round: a
    # reproduction that keeps only its own alert line leaves the next reader
    # exactly where the two organic occurrences did.
    evidence_dir = args.evidence_dir or args.log.parent / "evidence"
    watcher = Watcher(args.profile, ADDON_ID, log, get_pid,
                      evidence_dir=evidence_dir, data_dir=args.profile,
                      read_ring=make_ring_reader(args.port, log))
    # Arm 5 was stopped by the author mid-run, and its driver had no handler:
    # a bare SIGTERM killed the process outright, the `finally` below never ran,
    # and the headless Zotero it had spawned was left orphaned for the author to
    # find and kill by hand (ticket 0727, 2026-09-11T16:07Z). An unattended run
    # is a run that will be interrupted; raising SystemExit from the handler is
    # what lets the interruption go through the same teardown as a clean end.
    def terminate(signum, _frame):
        log.write(f"driver received signal {signum}; running its own cleanup")
        raise SystemExit(130)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)

    exit_code = 0
    try:
        wait_for_port("127.0.0.1", args.port, time.monotonic() + 60)
        watcher.start()
        client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)

        deadline = time.monotonic() + args.max_minutes * 60
        cycle = 0

        # The library, before anything is installed into the profile: the sitter
        # censuses what it finds at startup, so the Menagerie has to be there
        # first for the very first install to have work to do.
        if args.menagerie is not None:
            log.write(f"driver importing the Menagerie from {args.menagerie_ris}")
            imported = eval_action(client, import_menagerie_code(args.menagerie_ris),
                                   max(args.eval_timeout, 300.0), log, "menagerie import")
            log.write(f"driver menagerie imported: {imported}")
            if not imported.get("ok"):
                raise RuntimeError(f"the Menagerie did not import: {imported}")
            if imported.get("attachments", 0) - imported.get("missing", 0) <= 0:
                raise RuntimeError(
                    "the Menagerie imported with no attachment file on disk; the sitter "
                    "would be as idle as it is over an empty library")

        # Cycle 0: the one genuine FIRST install into a never-before-used
        # process -- everything after this is a REPLACE.
        cycle += 1
        run_cycle(client, cycle, "9.0.0", args.payload_dir, log, args.eval_timeout,
                  args.disable_hold_seconds)

        # And let it get to work before anything is pulled out from under it.
        # Replacing an add-on that has not finished its census is a different
        # experiment from replacing one that is extracting, and the second is
        # the one both organic occurrences were in.
        if args.warmup_seconds > 0:
            log.write(f"driver warming up {args.warmup_seconds:g}s so the sitter is working")
            time.sleep(args.warmup_seconds)

        rng = random.Random(args.seed) if args.seed is not None else None
        planned = plan_cycles(args, rng)
        # Written down before the first one runs. A run that reproduces has to
        # be replayable from its log alone, and a plan narrated as it happens
        # dies with the process that was executing it.
        log.write("driver plan: " + ", ".join(
            f"{step.action}@{step.wait_seconds:g}s" for step in planned))
        for step in planned:
            if watcher.disappearance.is_set() or time.monotonic() > deadline:
                break
            cycle += 1
            time.sleep(step.wait_seconds)
            log.write(f"driver cycle {cycle} action={step.action} "
                      f"after {step.wait_seconds:g}s")
            try:
                run_action(step.action, client, cycle, f"9.{cycle}.0", args, log, watcher)
                if args.restart_every and cycle % args.restart_every == 0:
                    client = restart_zotero(client)
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
    except SystemExit as exc:
        # The signal path, and it must not be swallowed by the handler below:
        # the point of catching it at all is to reach the `finally` that stops
        # the Zotero this driver started.
        log.write("driver stopping on a signal; the current cycle is abandoned")
        exit_code = exc.code if isinstance(exc.code, int) else 130
    except Exception as exc:  # noqa: BLE001 -- an unattended run must log its own crash
        log.write(f"driver FATAL {type(exc).__name__}: {exc}")
        exit_code = 1
    finally:
        watcher.stop()
        stop_zotero()
        log.close()
        stdout_log.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
