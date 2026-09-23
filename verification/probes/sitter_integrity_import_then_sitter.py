"""What does an import write, and what does the sitter add on top? Ticket 0816.

The rung drivers import with the sitter live or paused, so neither can say on
its own which writes are Zotero's reaction to being handed a document and which
the sitter's. This probe separates them in one clean-room Zotero: import a few
Menagerie documents with NO sitter installed and take a settled snapshot; then
install the sitter, let it prepare them, snapshot again; then uninstall with
diagnostics withdrawn and snapshot a third time. `bench/sitter_integrity.py`
diffs each pair, and the sitter-only diff is checked against the permitted set
with no declared edit.

It also tests the reading premise live, at each stage: a plain `mode=ro` open of
the running Zotero's `zotero.sqlite` and `fulltext.sqlite`, an `immutable=1`
open, and the check's own main+WAL copy, each asked how many items it sees.

Writes one JSON; `bench/results/0816-sitter-integrity/` keeps the committed copy.
Needs a Zotero install and a display, like the drivers.

    python3 verification/probes/sitter_integrity_import_then_sitter.py \
        --work-dir <fresh dir> --out <file.json> --zotero-bin /opt/zotero7/zotero
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench"))

import sitter_integrity as si  # noqa: E402
from fixtures.smoke_library import (  # noqa: E402
    DEFAULT_MENAGERIE,
    pick_menagerie_documents,
    write_menagerie_subset,
)
from sitter_smoke_test import (  # noqa: E402
    ZOTERO_READY,
    build_xpi,
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
    uninstall_code,
    wait_for_port,
)
from sitter_watch import Log, connect_resilient  # noqa: E402

ADDON_ID = "sdt-pack-sitter@search-works-for-zotero.invalid"
CLEAR_DEBUG = """JSON.stringify((() => {
  Zotero.Prefs.clear("extensions.sdt-pack-sitter.debug", true); return {ok: true};
})())"""


def live_reads(data_dir: Path) -> dict:
    """How many items each reader sees in the running Zotero's database."""
    out = {}
    db = data_dir / "zotero.sqlite"
    for label, uri in (("mode_ro", f"file:{db}?mode=ro"),
                       ("immutable", f"file:{db}?mode=ro&immutable=1")):
        try:
            con = sqlite3.connect(uri, uri=True)
            out[label] = {"items": con.execute("SELECT count(*) FROM items").fetchone()[0]}
            con.close()
        except sqlite3.Error as exc:
            out[label] = {"error": str(exc)}
    out["copy"] = {"items": si.snapshot(data_dir)["sqlite"]["zotero.sqlite"]["items"]["rows"]}
    wal = data_dir / "zotero.sqlite-wal"
    out["wal_bytes"] = wal.stat().st_size if wal.exists() else None
    out["shm_exists"] = (data_dir / "zotero.sqlite-shm").exists()
    ft = data_dir / "fulltext.sqlite"
    if ft.exists():
        try:
            con = sqlite3.connect(f"file:{ft}?mode=ro", uri=True)
            con.execute("SELECT count(*) FROM sqlite_master").fetchone()
            out["fulltext_mode_ro"] = "readable"
            con.close()
        except sqlite3.Error as exc:
            out["fulltext_mode_ro"] = f"error: {exc}"
    return out


def summarize(d: si.Diff) -> dict:
    return {"files": d.files, "tables": d.tables}


def measure(args, log: Log, result: dict) -> None:
    binary = find_zotero_bin(args.zotero_bin)
    xpi = args.work_dir / "sitter.xpi"
    build_xpi(xpi)
    fixture = args.work_dir / "fixture"
    fixture.mkdir()
    ris = write_menagerie_subset(fixture, pick_menagerie_documents(args.menagerie, args.docs))
    profile, data_dir = setup_profile(args.work_dir, args.port)
    proc, out_log = launch_zotero(binary, binary.parent / "app" / "application.ini",
                                  profile, args.port, args.work_dir / "zotero-stdout.log")
    client = None
    try:
        wait_for_port("127.0.0.1", args.port, time.monotonic() + 90)
        client = connect_resilient("127.0.0.1", args.port, 60, log)
        ready = eval_action(client, ZOTERO_READY, 120, log, "ready")
        if Path(ready["dataDir"]).resolve() != data_dir.resolve():
            raise SystemExit(f"REFUSING: Zotero opened {ready['dataDir']}, not {data_dir}")
        s0 = si.settled_snapshot(data_dir, settle=10, timeout=300)
        result["live_reads_start"] = live_reads(data_dir)
        for _ in range(40):
            imported = eval_action(client, import_menagerie_code(ris), 180, log, "import")
            if imported.get("ok") or imported.get("reason") != "no-translator":
                break
            time.sleep(5)
        result["import"] = imported
        result["live_reads_after_import"] = live_reads(data_dir)
        s1 = si.settled_snapshot(data_dir, settle=15, timeout=600)
        result["import_only"] = summarize(si.diff(s0, s1))
        result["install"] = eval_action(client, install_or_replace_code(xpi), 60, log, "install")
        poll_until_armed(client, log, 60, time.monotonic() + 180)
        want = imported["attachments"] - imported["missing"]
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            if len(list((data_dir / "storage").glob("*/.zotero-sdt-cache"))) >= want:
                break
            time.sleep(3)
        s2 = si.settled_snapshot(data_dir, settle=15, timeout=600)
        result["sitter_only"] = summarize(si.diff(s1, s2))
        result["sitter_only_verdict"] = si.check(si.diff(s1, s2))
        eval_action(client, CLEAR_DEBUG, 30, log, "clear diagnostics")
        result["uninstall"] = eval_action(client, uninstall_code(ADDON_ID), 60, log, "uninstall")
        s3 = si.settled_snapshot(data_dir, settle=15, timeout=300)
        result["uninstall_diff"] = summarize(si.diff(s2, s3))
        result["uninstall_verdict"] = si.check(si.diff(s2, s3))
        result["live_reads_end"] = live_reads(data_dir)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
        stop_zotero(proc)
        out_log.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--work-dir", type=Path, required=True, help="a fresh directory")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--zotero-bin", type=Path, default=Path("/opt/zotero7/zotero"))
    ap.add_argument("--menagerie", type=Path, default=DEFAULT_MENAGERIE)
    ap.add_argument("--port", type=int, default=6977)
    ap.add_argument("--docs", type=int, default=3)
    args = ap.parse_args()
    args.work_dir.mkdir(parents=True)
    log = Log(args.work_dir / "measure.txt")
    result = {}
    try:
        measure(args, log, result)
    finally:
        args.out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        log.close()


if __name__ == "__main__":
    main()
