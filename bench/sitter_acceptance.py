#!/usr/bin/env python3
"""The sitter's acceptance run: the author's own script, end to end.

`bench/sitter_smoke_test.py` stays what it is -- short and fast, run on every
change. This is the long one, run before a release, and it goes where the smoke
test deliberately stops: the switch, the two invalidation cycles, and the
uninstall.

    1. fresh Zotero, fresh data directory, Menagerie imported
    2. install the add-on, indexing starts
    3. PAUSE at the real switch, and verify it actually paused
    4. RESUME, and watch it finish
    5. every pack's source hash checked against the bytes on disk
    6. delete an ATTACHMENT -- its pack goes, by itself
    7. put it back -- its pack returns, within a minute
    8. the same for a whole ITEM
    9. remove the add-on -- verify no state is left behind

WHAT MAKES 3 A REAL STEP AND NOT A GESTURE. Pausing by writing
`state.enabled = false` would test the scheduler's own flag against itself. This
clicks `#sdt-switch` in the window the toolbar button opens -- the control a
user reaches -- and then checks that no NEW document is admitted while it is
off, which is what "it pauses" means. A pause that only reports itself paused is
the assertion this repository keeps finding.

WHAT 6 AND 8 ARE FOR. Coverage that only ever grows is easy; the hard half is a
library that shrinks. Both cycles assert in both directions, and both bound the
return at 60 s, because "eventually" is not a guarantee anybody can rely on.

Nothing here touches a real library: a fresh profile (refused if it already has
a prefs.js) and a data directory pinned beside it, re-read from the running
Zotero before anything is imported -- ticket 0782's refusal, kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bench"))

from fixtures.smoke_library import (  # noqa: E402
    pick_menagerie_documents,
    write_menagerie_subset,
)
from sitter_smoke_test import (  # noqa: E402
    DEFAULT_MENAGERIE,
    NotRunError,
    SmokeFailure,
    build_xpi,
    check_packs,
    find_zotero_bin,
    launch_zotero,
    poll_until_armed,
    read_pack_metadata,
    setup_profile,
    stop_zotero,
)
from sitter_volume_experiment import (  # noqa: E402
    eval_action,
    import_menagerie_code,
    install_or_replace_code,
    uninstall_code,
    wait_for_port,
)
from sitter_watch import Log, connect_resilient  # noqa: E402


class AcceptanceFailure(Exception):
    """A real defect, observed against a live Zotero."""


# --------------------------------------------------------------------------
# chrome-side probes
# --------------------------------------------------------------------------

STATE = """
(function() {
  try {
    const s = Zotero.SDTPackSitter && Zotero.SDTPackSitter.state;
    if (!s) return JSON.stringify({ok: false, reason: "no-handle"});
    return JSON.stringify({ok: true, enabled: !!s.enabled, busy: !!s.busy,
      phase: s.phase, active: s.active, scanned: s.scanned, total: s.total,
      completed: s.completed, failed: s.failed, pending: s.pending.length});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

#: Open the panel the way a user does -- the toolbar button's own command --
#: rather than by calling openDialog(), which is not reachable from here anyway
#: and would skip whatever the button does on the way.
OPEN_PANEL = """
(function() {
  try {
    const win = Zotero.getMainWindow();
    const button = win.document.getElementById("sdt-pack-sitter-button");
    if (!button) return JSON.stringify({ok: false, reason: "no-toolbar-button"});
    button.doCommand();
    return JSON.stringify({ok: true});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""


def _switch_js(body: str) -> str:
    """Find the sitter's window by the control it carries, not by title.

    Titles are localised and the panel is built at runtime; `#sdt-switch` is
    the thing this step is actually about.
    """
    return f"""
(function() {{
  try {{
    const windows = Services.wm.getEnumerator(null);
    while (windows.hasMoreElements()) {{
      const w = windows.getNext();
      let el = null;
      try {{ el = w.document && w.document.getElementById("sdt-switch"); }}
      catch (_e) {{ continue; }}
      if (!el) continue;
      {body}
    }}
    return JSON.stringify({{ok: false, reason: "no-window-carrying-sdt-switch"}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


READ_SWITCH = _switch_js("""
      return JSON.stringify({ok: true, label: el.textContent,
        ariaLabel: el.getAttribute("aria-label"),
        state: (w.document.getElementById("sdt-switch-state") || {}).textContent});
""")

CLICK_SWITCH = _switch_js("""
      el.click();
      return JSON.stringify({ok: true, clicked: true});
""")

CONSENT_PREF = """
(function() {
  try {
    const read = (name) => {
      try { return Zotero.Prefs.get(name, true); } catch (e) { return `threw: ${e}`; }
    };
    return JSON.stringify({ok: true,
      enabled: read("extensions.sdt-pack-sitter.enabled"),
      debug: read("extensions.sdt-pack-sitter.debug"),
      branchViaServices: (() => {
        try {
          return Services.prefs.getBoolPref("extensions.sdt-pack-sitter.enabled");
        } catch (e) { return `threw: ${e}`; }
      })()});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

ATTACHMENTS = """
(async function() {
  try {
    const rows = [];
    for (const lib of Zotero.Libraries.getAll()) {
      const ids = await Zotero.Items.getAll(lib.libraryID);
      for (const item of ids) {
        if (!item.isAttachment || !item.isAttachment()) continue;
        let path = null;
        try { path = await item.getFilePathAsync(); } catch (_e) { path = null; }
        rows.push({id: item.id, key: item.key, parentID: item.parentItemID,
                   title: item.getField("title"), path});
      }
    }
    return JSON.stringify({ok: true, attachments: rows});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""


def erase_code(item_id: int) -> str:
    return f"""
(async function() {{
  try {{
    const item = await Zotero.Items.getAsync({item_id});
    if (!item) return JSON.stringify({{ok: false, reason: "no-such-item"}});
    const parent = item.parentItemID;
    await item.eraseTx();
    return JSON.stringify({{ok: true, erased: {item_id}, parent}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


def attach_code(parent_id, path: str) -> str:
    parent = "null" if parent_id is None else str(parent_id)
    return f"""
(async function() {{
  try {{
    const item = await Zotero.Attachments.importFromFile({{
      file: {json.dumps(path)},
      parentItemID: {parent},
    }});
    return JSON.stringify({{ok: true, id: item.id, key: item.key}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


# --------------------------------------------------------------------------
# on-disk reads -- independent of anything the add-on says about itself
# --------------------------------------------------------------------------

def packs_on_disk(data_dir: Path) -> dict:
    """{storage key: source hash}, with None where the pack would not parse.

    The first version of this dropped unparsable packs on the floor, and that
    turned a limitation of OUR reader into a silent undercount: the run waited
    for a pack that was sitting right there, polled for fifteen minutes and said
    nothing. A pack that exists but will not parse is a fact this function has
    to carry, not hide -- the count is what the waits key on, and the None is
    what makes the reason visible when a hash assertion later needs it.
    """
    out = {}
    for pack in sorted((data_dir / "storage").glob("*/.zotero-sdt-cache")):
        try:
            meta = read_pack_metadata(pack)
        except SmokeFailure:
            out[pack.parent.name] = None
            continue
        out[pack.parent.name] = (meta.get("source") or {}).get("hash")
    return out


def wait_for_pack_count(data_dir: Path, want: int, deadline: float, log: Log,
                        what: str) -> dict:
    last = None
    while time.monotonic() < deadline:
        last = packs_on_disk(data_dir)
        if len(last) == want:
            log.write(f"acceptance {what}: {want} pack(s) on disk")
            return last
        time.sleep(2.0)
    raise AcceptanceFailure(
        f"{what}: waited for {want} pack(s) and the disk still shows "
        f"{len(last or {})} after the deadline. Present: {sorted((last or {}))}")


# --------------------------------------------------------------------------

class Run:
    def __init__(self, client, log, timeout):
        self.client, self.log, self.timeout = client, log, timeout

    def ev(self, code, what, timeout=None):
        out = eval_action(self.client, code, timeout or self.timeout, self.log, what)
        if not out.get("ok"):
            raise AcceptanceFailure(f"{what} failed: {out}")
        return out

    def state(self):
        return self.ev(STATE, "state")


def import_with_retry(run: Run, ris: Path, args, log: Log) -> dict:
    """The fixture import, waiting out the translator race rather than losing to it.

    `import_menagerie_code` already awaits `Zotero.initializationPromise`, and
    its own comment calls this the place the race would fire. It fires: on a
    profile whose translators have never been installed, `getTranslators()`
    answers an empty list for some seconds AFTER initialization resolves, and
    the probe correctly reports `no-translator` rather than inventing a result.
    That is the probe being right; waiting is the driver's job.

    Retried here and not fixed in the shared probe on purpose -- changing what
    `import_menagerie_code` means would change it under the volume experiment
    too, and its callers have their own timing.
    """
    deadline = time.monotonic() + args.translator_timeout
    attempt = 0
    while True:
        attempt += 1
        out = eval_action(run.client, import_menagerie_code(ris), 180.0, log,
                          f"import fixture (attempt {attempt})")
        if out.get("ok"):
            return out
        if out.get("reason") != "no-translator":
            raise AcceptanceFailure(f"the fixture would not import: {out}")
        if time.monotonic() >= deadline:
            raise NotRunError(
                f"Zotero never installed an RIS translator within "
                f"{args.translator_timeout}s on this fresh profile, so the "
                "fixture could not be imported. Nothing about the sitter was "
                "tested; this is a setup failure, not a defect.")
        log.write("acceptance translators not ready yet; waiting")
        time.sleep(5.0)


def phase_pause(run: Run, args, log: Log) -> dict:
    """Step 3, first half: turn it off at the real switch, before there is work.

    ORDER IS THE WHOLE POINT. The first version of this paused a library that
    was already fully indexed and reported success with `completed` stuck at
    4 of 4 -- nothing was admitted because nothing was left to admit, an
    assertion that could not fail. The fixture is now imported while the switch
    is OFF, so the outstanding work is created during the pause and resuming is
    the control: if it indexes afterwards, the stillness was the switch and not
    a dead sitter.
    """
    run.ev(OPEN_PANEL, "open panel")
    time.sleep(2.0)
    before = run.ev(READ_SWITCH, "read switch")
    log.write(f"acceptance switch before: {before}")

    started = run.state()
    if not started["enabled"]:
        raise AcceptanceFailure(
            f"the sitter was already off before the pause step: {started}")

    run.ev(CLICK_SWITCH, "click switch off")
    time.sleep(3.0)
    paused = run.state()
    if paused["enabled"]:
        raise AcceptanceFailure(f"clicking the switch did not turn it off: {paused}")
    after = run.ev(READ_SWITCH, "read switch off")
    log.write(f"acceptance switch after off: {after}")
    return {"before": before, "after": after, "completed_at_pause": paused["completed"]}


def phase_verify_paused(run: Run, data_dir: Path, args, log: Log, mark: int) -> dict:
    """Step 3, second half: nothing was indexed while the switch was off."""
    log.write(f"acceptance holding {args.pause_hold}s with work outstanding")
    time.sleep(args.pause_hold)
    held = run.state()
    packs = packs_on_disk(data_dir)
    # The file already under way when the switch was thrown is allowed to
    # finish -- that is the ruling, not a defect -- so one completion is
    # tolerated and a second is the failure. Here there was none under way.
    if held["completed"] > mark + 1:
        raise AcceptanceFailure(
            f"the sitter kept admitting work while paused: completed went "
            f"{mark} -> {held['completed']} over {args.pause_hold}s")
    if len(packs) > mark + 1:
        raise AcceptanceFailure(
            f"packs appeared on disk while paused: {len(packs)} present, "
            f"{mark} expected")
    log.write(f"acceptance pause verified: completed {mark} -> {held['completed']}, "
              f"{len(packs)} pack(s) on disk")
    return {"completed": held["completed"], "packs": len(packs)}


def phase_resume(run: Run, log: Log) -> dict:
    """Step 4. Turning it back on is the pause step's own control."""
    run.ev(CLICK_SWITCH, "click switch on")
    time.sleep(3.0)
    resumed = run.state()
    if not resumed["enabled"]:
        raise AcceptanceFailure(f"clicking the switch did not turn it back on: {resumed}")
    log.write("acceptance resumed")
    return resumed


def phase_invalidation(run: Run, data_dir: Path, fixture_dir: Path, log: Log,
                       args, *, whole_item: bool) -> dict:
    """Steps 6-7 and 8. Delete, watch the pack go; restore, watch it return."""
    what = "item" if whole_item else "attachment"
    listing = run.ev(ATTACHMENTS, f"list attachments before {what} delete", timeout=90)
    rows = [r for r in listing["attachments"] if r.get("path")]
    if not rows:
        raise AcceptanceFailure("no attachment with a file on disk to delete")
    victim = rows[0]
    before = packs_on_disk(data_dir)
    log.write(f"acceptance {what} victim={victim['key']} packs_before={len(before)}")
    if victim["key"] not in before:
        raise AcceptanceFailure(
            f"the attachment chosen to delete has no pack to lose "
            f"({victim['key']} not in {sorted(before)}) -- the arm would pass "
            "by having nothing to observe")
    lost_hash = before[victim["key"]]
    source = Path(victim["path"])
    if not source.exists():
        raise AcceptanceFailure(f"{source} is gone before the step began")
    kept = source.read_bytes()
    digest = hashlib.md5(kept).hexdigest()
    if digest != lost_hash:
        raise AcceptanceFailure(
            f"the pack for {victim['key']} names source hash {lost_hash!r} but "
            f"the file on disk is {digest!r} -- the pack does not belong to it")

    target = victim["parentID"] if whole_item and victim["parentID"] else victim["id"]
    run.ev(erase_code(target), f"erase {what} {target}")

    after = wait_for_pack_count(data_dir, len(before) - 1,
                                time.monotonic() + args.invalidation_timeout,
                                log, f"{what} deleted")
    if victim["key"] in after:
        raise AcceptanceFailure(
            f"the count fell but {victim['key']}'s own pack is still there")

    # Put it back and bound the return. `restore_timeout` defaults to 60 s
    # because that is the promise: within a minute, not eventually.
    scratch = fixture_dir / f"restore-{victim['key']}.pdf"
    scratch.write_bytes(kept)
    parent = None if whole_item else victim["parentID"]
    added = run.ev(attach_code(parent, str(scratch)), f"re-add {what}", timeout=90)
    log.write(f"acceptance re-added as {added}")

    back = wait_for_pack_count(data_dir, len(before),
                               time.monotonic() + args.restore_timeout,
                               log, f"{what} restored")
    if digest not in set(back.values()):
        raise AcceptanceFailure(
            f"a pack came back but none names the restored file's hash {digest!r}; "
            f"packs now name {sorted(set(back.values()))}")
    return {"what": what, "key": victim["key"], "hash": digest,
            "packs_before": len(before), "packs_after_delete": len(after),
            "packs_after_restore": len(back)}


CLEAR_DIAGNOSTICS = """
(function() {
  try {
    Zotero.Prefs.clear("extensions.sdt-pack-sitter.debug", true);
    let still;
    try { still = Zotero.Prefs.get("extensions.sdt-pack-sitter.debug", true); }
    catch (e) { still = undefined; }
    return JSON.stringify({ok: true, debugAfterClear: still ?? null});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""


def phase_uninstall(run: Run, data_dir: Path, profile: Path, log: Log, args) -> dict:
    """Step 9. Removed means removed -- in the configuration a release ships.

    THE FIRST VERSION OF THIS ASSERTED THE WRONG THING and the run caught it: it
    demanded no certificate while the rig's own SEED_PREFS had set
    `extensions.sdt-pack-sitter.debug = true`, so the uninstall correctly wrote
    one. That is the ruling of 2026-09-12 -- the certificate is the ONE file a
    clean uninstall must not sweep away, because it is the operator's own
    request, made before the event -- and a test that calls the ruling a defect
    is worse than no test.

    So the diagnostics opt-in is withdrawn first, and the assertion becomes the
    one the author actually asked for: with the switch off, which is how a
    release ships, an uninstall leaves NOTHING. The opted-in half is asserted by
    the unit suite ("an uninstall writes one too, and an ordinary quit does
    not"), where it can be driven without spending a live run on it.
    """
    cleared = run.ev(CLEAR_DIAGNOSTICS, "withdraw the diagnostics opt-in")
    if cleared.get("debugAfterClear"):
        raise AcceptanceFailure(
            f"the diagnostics pref would not clear: {cleared}. The arm below "
            "would then pass or fail for the wrong reason.")
    stale = data_dir / "sdt-sitter-last-shutdown.json"
    if stale.exists():
        # Nothing in this run has disabled or uninstalled yet, so a certificate
        # here would be from a shutdown that never happened -- refuse rather
        # than quietly delete evidence the next assertion depends on.
        raise AcceptanceFailure(
            f"a certificate already exists at {stale} before the uninstall step; "
            "the arm cannot tell a surviving one from a newly written one")
    run.ev(uninstall_code("sdt-pack-sitter@search-works-for-zotero.invalid"),
           "uninstall")
    deadline = time.monotonic() + args.uninstall_timeout
    residue = None
    while time.monotonic() < deadline:
        residue = {
            "cache": (data_dir / "sdt-sitter-cache.jsonl").exists(),
            "cache_tmp": (data_dir / "sdt-sitter-cache.jsonl.tmp").exists(),
            "certificate": (data_dir / "sdt-sitter-last-shutdown.json").exists(),
            "xpi": (profile / "extensions"
                    / "sdt-pack-sitter@search-works-for-zotero.invalid.xpi").exists(),
        }
        if not any(residue.values()):
            log.write("acceptance uninstall left nothing behind")
            return {"residue": residue, "clean": True}
        time.sleep(2.0)
    raise AcceptanceFailure(
        f"state survived the uninstall with diagnostics withdrawn: {residue}")


def run_acceptance(args) -> dict:
    log = Log(args.work_dir / "acceptance.log")
    binary = find_zotero_bin(args.zotero_bin)
    app_ini = binary.parent / "app" / "application.ini"

    xpi = args.xpi or (args.work_dir / "sitter-acceptance.xpi")
    if args.xpi is None:
        build_xpi(xpi)
    log.write(f"acceptance payload {xpi}")

    fixture_dir = args.work_dir / "fixture"
    fixture_dir.mkdir(parents=True)
    documents = pick_menagerie_documents(args.menagerie, args.fixture_documents)
    if not documents:
        raise NotRunError(
            f"no Menagerie package at {args.menagerie}; this run is about real "
            "documents with distinct hashes and will not fall back")
    ris = write_menagerie_subset(fixture_dir, documents)
    log.write(f"acceptance fixture: {[d.name for d in documents]}")

    profile, requested = setup_profile(args.work_dir, args.port)
    proc, stdout_log = launch_zotero(binary, app_ini, profile, args.port,
                                     args.work_dir / "zotero-stdout.log")
    client = None
    phases = {}
    try:
        wait_for_port("127.0.0.1", args.port, time.monotonic() + 90)
        client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)
        run = Run(client, log, args.eval_timeout)

        installed = run.ev(install_or_replace_code(xpi), "install")
        try:
            live = poll_until_armed(client, log, args.eval_timeout,
                                    time.monotonic() + args.arm_timeout)
        except SmokeFailure:
            # Read the consent pref from INSIDE the process before giving up.
            # Attempt 3 failed with phase 'switched-off' on a profile whose
            # prefs.js carried enabled=true, and the failure could not say
            # whether the pref was not read, not honoured, or overwritten --
            # three different bugs wearing one message.
            probe = eval_action(client, CONSENT_PREF, args.eval_timeout, log,
                                "consent pref")
            log.write(f"acceptance arm failed; consent pref reads {probe}")
            raise
        data_dir = Path(live["dataDir"]).resolve()
        if data_dir != requested.resolve():
            raise AcceptanceFailure(
                f"REFUSING to import: Zotero opened {data_dir}, not the pinned "
                f"{requested.resolve()}. Nothing was imported.")
        phases["install"] = {"installed": installed, "dataDir": str(data_dir)}

        # OFF FIRST, then import: the work has to be created during the pause
        # for the pause to be observable at all.
        phases["pause"] = phase_pause(run, args, log)
        mark = phases["pause"]["completed_at_pause"]

        imported = import_with_retry(run, ris, args, log)
        prepared = imported["attachments"] - imported["missing"]
        if prepared < 2:
            raise NotRunError(
                f"only {prepared} attachment(s) landed on disk; the invalidation "
                "steps need more than one so that deleting one leaves something")
        phases["import"] = imported

        phases["paused_verified"] = phase_verify_paused(run, data_dir, args, log, mark)
        phases["resume"] = phase_resume(run, log)

        wait_for_pack_count(data_dir, prepared,
                            time.monotonic() + args.index_timeout, log, "indexed")
        phases["packs"] = check_packs(data_dir, fixture_dir, prepared, log)

        phases["attachment_cycle"] = phase_invalidation(
            run, data_dir, fixture_dir, log, args, whole_item=False)
        phases["item_cycle"] = phase_invalidation(
            run, data_dir, fixture_dir, log, args, whole_item=True)

        phases["uninstall"] = phase_uninstall(run, data_dir, profile, log, args)
        log.write("acceptance PASS")
        return {"ok": True, "phases": phases}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
        stop_zotero(proc)
        stdout_log.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work-dir", type=Path, required=True,
                    help="a fresh directory; the profile and data dir are made under it")
    ap.add_argument("--xpi", type=Path, help="payload; built from the tree if omitted")
    ap.add_argument("--zotero-bin", type=Path,
                    default=Path("/home/haduong/.local/bin/zotero"))
    ap.add_argument("--menagerie", type=Path, default=DEFAULT_MENAGERIE)
    ap.add_argument("--fixture-documents", type=int, default=4)
    ap.add_argument("--port", type=int, default=6960)
    ap.add_argument("--eval-timeout", type=float, default=60.0)
    ap.add_argument("--arm-timeout", type=float, default=180.0)
    ap.add_argument("--index-timeout", type=float, default=900.0)
    ap.add_argument("--translator-timeout", type=float, default=180.0,
                    help="how long to wait for a fresh profile to install its "
                         "RIS translator before calling the run NOT-RUN")
    ap.add_argument("--pause-hold", type=float, default=30.0,
                    help="seconds to hold the switch off while watching for "
                         "admissions that should not happen")
    ap.add_argument("--invalidation-timeout", type=float, default=120.0)
    ap.add_argument("--restore-timeout", type=float, default=60.0,
                    help="the promise this run holds the sitter to: a restored "
                         "file is prepared again WITHIN A MINUTE")
    ap.add_argument("--uninstall-timeout", type=float, default=60.0)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args(argv)

    args.work_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = run_acceptance(args)
    except NotRunError as exc:
        print(f"NOT-RUN: {exc}")
        return 2
    except (AcceptanceFailure, SmokeFailure) as exc:
        print(f"FAIL: {exc}")
        return 1
    print("\n================ ACCEPTANCE: PASS ================")
    for name, payload in result["phases"].items():
        print(f"  {name}")
        print(f"      {json.dumps(payload)[:160]}")
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
