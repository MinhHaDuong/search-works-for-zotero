#!/usr/bin/env python3
"""Ticket 0825 probe: call Zotero.SDT.ensure() on the 0818 failed-session
attachments in a reflink arena and record what it throws.

Usage: sdt_ensure_probe_0825.py ARENA_ROOT PORT DISPLAY IDS_FILE
ARENA_ROOT already holds data/ (a `cp -a --reflink=always` of the clone-rung
library, never the library itself). IDS_FILE holds one `libraryID/KEY` per
line. Writes into ARENA_ROOT: profile/, zotero-stdout.txt, results.json.
Starts nothing but Zotero (the caller starts its own Xvfb on a free display
and passes it); stops only the Zotero it started, by PID.

Read the result from the debug output, not from the call: `ensure()` does
not throw. Zotero 10.0.3 catches the worker's error, hands it to
`Zotero.logError` and resolves `false`, so the message is the line
"Worker action 'getStructuredDocumentText' failed" captured per item in
`debug_slice`. The 2026-09-24 run's redacted record is
`verification/clone/0825-ensure-probe-2026-09-24.json`.
"""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench"))
from zotero_rdp_client import ZoteroRDPClient, RDPEvalError  # noqa: E402

ZBIN = Path.home() / ".local/Zotero_linux-x86_64/zotero-bin"
APPINI = Path.home() / ".local/Zotero_linux-x86_64/app/application.ini"

PREFS = """\
user_pref("extensions.zotero.dataDir", "{data_dir}");
user_pref("extensions.zotero.useDataDir", true);
user_pref("devtools.debugger.remote-enabled", true);
user_pref("devtools.debugger.prompt-connection", false);
user_pref("devtools.chrome.enabled", true);
user_pref("extensions.zotero.debug.log", true);
user_pref("extensions.zotero.debug.store", true);
user_pref("extensions.zotero.debug.level", 5);
user_pref("extensions.zotero.sync.autoSync", false);
user_pref("extensions.zotero.sync.storage.enabled", false);
user_pref("extensions.zotero.automaticScraperUpdates", false);
user_pref("app.update.enabled", false);
"""

READY = """
(async function() {
  try {
    await Zotero.initializationPromise;
    await Zotero.Schema.schemaUpdatePromise;
    Zotero.Debug.setStore(true);
    return JSON.stringify({ok: true, dataDir: Zotero.DataDirectory.dir,
      version: Zotero.version, hasSDT: typeof Zotero.SDT,
      ensureType: Zotero.SDT && typeof Zotero.SDT.ensure});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

INFO = """
(async function() {
  const [lib, key] = %s;
  try {
    const it = await Zotero.Items.getByLibraryAndKeyAsync(lib, key);
    if (!it) return JSON.stringify({ok: false, reason: 'no item'});
    const path = await it.getFilePathAsync();
    return JSON.stringify({ok: true, itemID: it.id, contentType: it.attachmentContentType,
      linkMode: it.attachmentLinkMode, filename: it.attachmentFilename, path: path || null,
      parentID: it.parentID, deleted: it.deleted});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

ENSURE = """
(async function() {
  const itemID = %d;
  function desc(e, depth) {
    if (e === null || e === undefined) return e === null ? 'null' : 'undefined';
    if (typeof e !== 'object') return {primitive: String(e), type: typeof e};
    const d = {string: String(e), name: e.name, message: e.message, stack: e.stack,
      ctor: e.constructor && e.constructor.name, keys: Object.keys(e)};
    for (const k of Object.keys(e)) { try { d['own_' + k] = String(e[k]); } catch (_) {} }
    if (e.cause !== undefined && depth < 4) d.cause = desc(e.cause, depth + 1);
    return d;
  }
  const t0 = Date.now();
  const progress = [];
  try {
    const r = await Zotero.SDT.ensure(itemID, { isPriority: false,
      onProgress: (p) => { if (progress.length < 50) progress.push(p); } });
    let rs;
    try { rs = JSON.stringify(r); } catch (_) { rs = String(r); }
    return JSON.stringify({ok: true, threw: false, ms: Date.now() - t0,
      resolvedType: typeof r, resolved: rs && rs.slice(0, 2000), progress});
  } catch (e) {
    return JSON.stringify({ok: true, threw: true, ms: Date.now() - t0,
      error: desc(e, 0), progress});
  }
})()
"""

QUIT = """
(function() { try { Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
  return JSON.stringify({ok: true}); } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); } })()
"""


def ev(client, code, timeout):
    raw = client.eval_js(code, timeout=timeout)
    return json.loads(raw)


def file_facts(path):
    out = {"path": path}
    if not path or not os.path.exists(path):
        out["exists"] = False
        return out
    out["exists"] = True
    out["size"] = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(1024)
    out["head64_hex"] = head[:64].hex()
    out["head64_ascii"] = "".join(chr(b) if 32 <= b < 127 else "." for b in head[:64])
    out["head200_repr"] = repr(head[:200])
    out["pdf_magic_in_1024"] = b"%PDF-" in head
    out["pdf_magic_offset"] = head.find(b"%PDF-")
    if b"%PDF-" in head:
        i = head.find(b"%PDF-")
        out["pdf_version"] = head[i:i + 8].decode("latin-1")
        with open(path, "rb") as f:
            f.seek(max(0, out["size"] - 4096))
            tail = f.read()
        out["tail_has_EOF"] = b"%%EOF" in tail
        out["tail_has_startxref"] = b"startxref" in tail
        with open(path, "rb") as f:
            data = f.read()
        out["has_Encrypt"] = b"/Encrypt" in data
        out["has_ObjStm"] = b"/ObjStm" in data
        out["has_XRefStm_or_XRef"] = b"/XRef" in data
        out["count_EOF"] = data.count(b"%%EOF")
        out["count_xref_kw"] = data.count(b"\nxref")
        pi = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=60)
        out["pdfinfo_rc"] = pi.returncode
        out["pdfinfo"] = pi.stdout.strip()
        out["pdfinfo_err"] = pi.stderr.strip()[:1500]
        fi = subprocess.run(["file", "-b", path], capture_output=True, text=True)
        out["file"] = fi.stdout.strip()
    else:
        fi = subprocess.run(["file", "-b", path], capture_output=True, text=True)
        out["file"] = fi.stdout.strip()
    return out


def wait_port(port, deadline):
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def main():
    arena, port, ids_file = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[4])
    os.environ["DISPLAY"] = sys.argv[3]
    data_dir = (arena / "data").resolve()
    assert (data_dir / "zotero.sqlite").is_file()
    ids = [line.strip() for line in ids_file.read_text().splitlines() if line.strip()]
    profile = arena / "profile"
    profile.mkdir()
    (profile / "prefs.js").write_text(PREFS.replace("{data_dir}", str(data_dir)))
    log_path = arena / "zotero-stdout.txt"
    logf = open(log_path, "a")
    env = {**os.environ, "MOZ_ALLOW_DOWNGRADE": "1", "MOZ_LEGACY_PROFILES": "1"}
    cmd = [str(ZBIN), "-app", str(APPINI), "--start-debugger-server", str(port),
           "--profile", str(profile), "-ZoteroDebugText"]
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, env=env)
    results = {"pid": proc.pid, "cmd": cmd, "dataDir": str(data_dir), "items": []}
    print(f"zotero pid {proc.pid}", flush=True)
    client = None
    try:
        if not wait_port(port, time.monotonic() + 120):
            results["error"] = "port never came up"
            return
        time.sleep(3)
        client = ZoteroRDPClient.connect("127.0.0.1", port, timeout=30)
        ready = ev(client, READY, 600)
        results["ready"] = ready
        print("ready", ready, flush=True)
        if not ready.get("ok") or Path(ready["dataDir"]).resolve() != data_dir:
            results["error"] = f"REFUSING: dataDir mismatch {ready}"
            return
        time.sleep(20)  # let start-up chatter settle
        for ident in ids:
            lib, key = ident.split("/")
            rec = {"id": ident}
            info = ev(client, INFO % json.dumps([int(lib), key]), 60)
            rec["info"] = info
            if info.get("ok"):
                pack = Path(info["path"]).parent / ".zotero-sdt-cache" if info.get("path") else None
                rec["pack_before"] = bool(pack and pack.exists())
                rec["file"] = file_facts(info.get("path"))
                logf.flush()
                off0 = os.path.getsize(log_path)
                try:
                    rec["ensure"] = ev(client, ENSURE % info["itemID"], 900)
                except RDPEvalError as exc:
                    rec["ensure"] = {"ok": False, "rdp_error": str(exc)}
                time.sleep(2)
                off1 = os.path.getsize(log_path)
                with open(log_path, "rb") as f:
                    f.seek(off0)
                    rec["debug_slice"] = f.read(off1 - off0).decode("utf-8", "replace")
                rec["debug_slice_offsets"] = [off0, off1]
                rec["pack_after"] = bool(pack and pack.exists())
                if pack and pack.exists():
                    rec["pack_after_size"] = pack.stat().st_size
            e = rec.get("ensure", {})
            print(ident, "threw" if e.get("threw") else "resolved",
                  (e.get("error") or {}).get("message") if isinstance(e.get("error"), dict) else e,
                  flush=True)
            results["items"].append(rec)
            (arena / "results.json").write_text(json.dumps(results, indent=1))
    finally:
        if client is not None:
            try:
                ev(client, QUIT, 30)
            except Exception as exc:  # noqa: BLE001
                results["quit_note"] = str(exc)
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            proc.wait(timeout=180)
            results["quit"] = f"exited rc={proc.returncode}"
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=30)
                results["quit"] = "terminated"
            except subprocess.TimeoutExpired:
                proc.kill()
                results["quit"] = "killed"
        (arena / "results.json").write_text(json.dumps(results, indent=1))
        logf.close()


if __name__ == "__main__":
    main()
