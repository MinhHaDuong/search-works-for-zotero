#!/usr/bin/env python3
"""Run the panel's keyboard assertions in a real Zotero window. Ticket 0769.

Ticket 0686's accessibility verdict was CHANGES REQUESTED, and the item this
answers is the keyboard half: the supervision panel must be openable,
navigable and dismissable without a mouse, with focus restored afterwards.
Nothing headless can establish that -- `<details>`, XUL command dispatch and a
dialog's Escape handling are platform behaviours, and Gecko ignores untrusted
synthetic events precisely so that a test cannot fake them.

What this script does is the setup; the verdict comes from
`sdt_panel_keyboard.js`, evaluated inside the window (ticket 0769's invariant:
the driver performs gestures, the in-window assertions are the verdict).

Reused rather than re-implemented: `bench/sitter_smoke_test.py`'s launch,
profile and install path, which already produces an armed sitter in a real
window in about ten seconds, and `bench/sitter_watch.py`'s resilient connect.

## The deliberate break

`--break-escape` removes the panel's Escape handling in the built payload
before installing it. Ticket 0769 requires each assertion to have been seen red
once in a real window, for the reason its own log records: this probe already
shipped a stale assertion that would have failed in a real window before
reading anything it was there for, and that was caught by reading rather than
running. A probe never seen red in a real window has not been shown to run
there at all.

Exit codes follow the repo's convention (`bench/sitter_smoke_test.py`):
  0 PASS, 1 FAIL (an assertion came back red), 2 usage, 3 NOT-RUN.
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "bench"))

from fixtures.smoke_library import (  # noqa: E402
    DEFAULT_MENAGERIE,
    pick_menagerie_documents,
    write_menagerie_subset,
    write_smoke_library,
)
from sitter_smoke_test import (  # noqa: E402
    NotRunError,
    SmokeFailure,
    find_zotero_bin,
    launch_zotero,
    poll_until_armed,
    setup_profile,
    stop_zotero,
)
from sitter_volume_experiment import (  # noqa: E402
    eval_action,
    import_menagerie_code,
    install_or_replace_code,
    wait_for_port,
)
from sitter_watch import Log, connect_resilient  # noqa: E402

PROBE = Path(__file__).resolve().parent / "sdt_panel_keyboard.js"
SITTER = REPO / "plugins" / "sdt-sitter"


def build_xpi(out_path: Path, break_escape: bool = False) -> Path:
    """The real payload, optionally with its Escape handling removed.

    The break is applied to a scratch copy and never to the tree, the isolation
    discipline ticket 0727's arm 2 established.
    """
    bootstrap = (SITTER / "bootstrap.js").read_text(encoding="utf-8")
    if break_escape:
        # Remove the dialog's own Escape handling, whatever spelling it uses,
        # and refuse to proceed if nothing matched -- a "deliberate break" that
        # broke nothing would produce a green run and read as a red arm passed.
        patterns = [
            r"if\s*\(\s*event\.key\s*===?\s*['\"]Escape['\"]\s*\)",
            r"case\s+['\"]Escape['\"]\s*:",
            r"event\.key\s*===?\s*['\"]Escape['\"]",
        ]
        broken = bootstrap
        for pattern in patterns:
            broken, count = re.subn(pattern, "if (false)", broken, count=1)
            if count:
                break
        else:
            raise NotRunError(
                "--break-escape found no Escape handling to remove in bootstrap.js; "
                "the break would have been a no-op and its red arm meaningless")
        bootstrap = broken

    manifest = json.loads((SITTER / "manifest.json").read_text(encoding="utf-8"))
    if break_escape:
        manifest["name"] = f"{manifest['name']} [0769 DELIBERATE BREAK, throwaway]"
    if out_path.exists():
        out_path.unlink()
    with zipfile.ZipFile(out_path, "x", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("manifest.json", json.dumps(manifest, indent=2))
        package.writestr("bootstrap.js", bootstrap)
        package.writestr("scheduler.js", (SITTER / "scheduler.js").read_bytes())
    return out_path


def run(args, log: Log) -> dict:
    binary = find_zotero_bin(Path(args.zotero_bin))
    app_ini = Path(args.zotero_bin).parent / "app" / "application.ini"

    xpi = build_xpi(args.work_dir / "sitter-keyboard.xpi", args.break_escape)
    log.write(f"keyboard xpi at {xpi}"
              + (" [ESCAPE DELIBERATELY BROKEN]" if args.break_escape else ""))

    fixture_dir = args.work_dir / "fixture"
    fixture_dir.mkdir(parents=True)
    documents = pick_menagerie_documents(args.menagerie, 3)
    ris = (write_menagerie_subset(fixture_dir, documents) if documents
           else write_smoke_library(fixture_dir))
    log.write(f"fixture at {ris} ({'menagerie' if documents else 'synthetic'})")

    profile, requested_data = setup_profile(args.work_dir, args.port)
    proc, stdout_log = launch_zotero(binary, app_ini, profile, args.port,
                                     args.work_dir / "zotero-stdout.log")
    log.write(f"launched zotero pid={proc.pid}")
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

        installed = eval_action(client, install_or_replace_code(xpi),
                                args.eval_timeout, log, "install")
        if not installed.get("ok"):
            raise SmokeFailure(f"the XPI would not install: {installed}")
        log.write(f"installed: {installed}")

        live = poll_until_armed(client, log, args.eval_timeout,
                                time.monotonic() + args.arm_timeout)
        if not live.get("handle"):
            raise SmokeFailure(f"the sitter never armed: {live}")
        actual_data = Path(live["dataDir"]).resolve()
        if actual_data != requested_data.resolve():
            raise SmokeFailure(
                f"REFUSING to continue: Zotero opened {actual_data}, not the "
                f"requested {requested_data.resolve()} (ticket 0782's hazard)")
        log.write(f"armed: {live}")

        imported = eval_action(client, import_menagerie_code(ris),
                               max(args.eval_timeout, 60.0), log, "fixture import")
        log.write(f"imported: {imported}")

        probe = Path(args.probe) if args.probe else PROBE
        raw = client.eval_js(probe.read_text(encoding="utf-8"), timeout=args.eval_timeout)
        outcome = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(outcome, str):
            outcome = json.loads(outcome)
        return outcome
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001 -- teardown
                pass
        stop_zotero(proc)
        stdout_log.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zotero-bin",
                        default=str(Path.home() / ".local" / "Zotero_linux-x86_64" / "zotero"))
    parser.add_argument("--menagerie", type=Path, default=DEFAULT_MENAGERIE)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--port", type=int, default=6150)
    parser.add_argument("--eval-timeout", type=float, default=120.0)
    parser.add_argument("--arm-timeout", type=float, default=120.0)
    parser.add_argument("--probe", default=None,
                        help="evaluate this file in the window instead of the "
                             "keyboard probe (introspection and iteration)")
    parser.add_argument("--break-escape", action="store_true",
                        help="remove the panel's Escape handling before installing, to "
                             "show the Escape assertion red (ticket 0769's red step)")
    args = parser.parse_args(argv)

    own = args.work_dir is None
    if own:
        args.work_dir = Path(tempfile.mkdtemp(prefix="sdt-panel-keyboard-"))
    else:
        args.work_dir.mkdir(parents=True, exist_ok=True)
    log = Log(args.work_dir / "keyboard-log.txt")

    try:
        outcome = run(args, log)
    except NotRunError as exc:
        print(f"NOT-RUN: {exc}")
        return 3
    except SmokeFailure as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        if own and not args.keep:
            shutil.rmtree(args.work_dir, ignore_errors=True)
        else:
            print(f"work dir kept at {args.work_dir}")

    # NOT-ESTABLISHED is printed as itself. Folding it into FAIL would report a
    # reading the probe could not take as a panel that failed it, which is the
    # confusion this whole probe is built to avoid.
    for row in outcome.get("results", []):
        mark = {"pass": "PASS", "FAIL": "FAIL"}.get(row["result"], "NOT-ESTABLISHED")
        detail = f"  -- {row['detail']}" if row.get("detail") else ""
        print(f"  [{mark}] {row['name']}{detail}")
    if outcome.get("error"):
        print(f"  probe error: {outcome['error']}")
    if args.probe:
        # An introspection probe answers a shape this script does not know;
        # printing only the keys it expects would hide the answer.
        print(json.dumps(outcome, indent=2))
    else:
        print(json.dumps(outcome.get("report", {}), indent=2))

    if args.break_escape:
        # Inverted: with Escape removed, a green run means the probe is not
        # reading what it claims to read.
        escape_red = any(r["name"].startswith("Escape closes") and r["result"] != "pass"
                         for r in outcome.get("results", []))
        print("\nRED ARM: " + ("the Escape assertion went red, as required"
                               if escape_red else
                               "THE ESCAPE ASSERTION STAYED GREEN WITH ESCAPE REMOVED"))
        return 0 if escape_red else 1
    # `ok` is "nothing FAILED"; `established` is "everything PASSED". A run
    # with an unobservable reading is not a pass, and exit 3 (NOT-RUN) says so
    # without claiming a defect.
    if not outcome.get("ok"):
        return 1
    return 0 if outcome.get("established") else 3


if __name__ == "__main__":
    sys.exit(main())
