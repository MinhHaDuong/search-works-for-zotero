"""Watch the Zotero profile for the ticket-0727 removal signature.

Polls at 50 ms. Records every appearance, disappearance, size change and mtime
change under the profile's extension bookkeeping, with wall-clock stamps that
can be lined up against the plugin's own journal (whose `at` values are epoch
ms).

The signature established from the 19:00:53 event: the add-on's .xpi is deleted
from extensions/, extensions.json is rewritten without it, and the add-on's
preference branch is cleared -- all within the same second, and roughly three
seconds after the plugin's bootstrap starts.
"""
import datetime
import pathlib
import sys
import time

PROFILE = pathlib.Path("/home/haduong/.zotero/zotero/e8mz6uxw.default")
DATADIR = pathlib.Path("/home/haduong/Zotero")

WATCH = [
    PROFILE / "extensions.json",
    PROFILE / "prefs.js",
    PROFILE / "addonStartup.json.lz4",
    DATADIR / "sdt-sitter-cache.jsonl",
    DATADIR / "sdt-sitter-last-shutdown.json",
]
WATCH_DIRS = [PROFILE / "extensions"]

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
POLL = 0.05


def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def snap_file(p):
    try:
        st = p.stat()
        return (round(st.st_mtime, 3), st.st_size)
    except FileNotFoundError:
        return None


def snap_dir(p):
    try:
        return {c.name: snap_file(c) for c in p.iterdir()}
    except FileNotFoundError:
        return None


def sitter_in(p):
    """Does extensions.json still name the add-on?"""
    try:
        return "sdt-pack-sitter" in p.read_text(errors="replace")
    except OSError:
        return None


def log(msg):
    line = f"{stamp()}  {msg}"
    print(line, flush=True)


files = {p: snap_file(p) for p in WATCH}
dirs = {p: snap_dir(p) for p in WATCH_DIRS}
named = sitter_in(PROFILE / "extensions.json")

log(f"WATCHING (poll {POLL * 1000:.0f} ms, {DURATION:.0f} s)")
for p, v in files.items():
    log(f"  baseline {p.name}: {'ABSENT' if v is None else v}")
for p, v in dirs.items():
    log(f"  baseline {p}/: {sorted(v) if v else v}")
log(f"  baseline extensions.json names sdt-pack-sitter: {named}")
log("--- armed; install the .xpi now ---")

end = time.monotonic() + DURATION
while time.monotonic() < end:
    time.sleep(POLL)

    for p in WATCH:
        new = snap_file(p)
        old = files[p]
        if new != old:
            if old is None:
                log(f"CREATED  {p.name}  {new}")
            elif new is None:
                log(f"DELETED  {p.name}")
            else:
                log(f"CHANGED  {p.name}  mtime {old[0]} -> {new[0]}  "
                    f"size {old[1]} -> {new[1]}")
            files[p] = new
            if p.name == "extensions.json":
                now = sitter_in(p)
                global_named = named
                if now != global_named:
                    log(f"  >>> extensions.json names sdt-pack-sitter: "
                        f"{global_named} -> {now}")
                    named = now
                else:
                    log(f"      (still names sdt-pack-sitter: {now})")

    for p in WATCH_DIRS:
        new = snap_dir(p)
        old = dirs[p]
        if new != old:
            oldset = set(old or {})
            newset = set(new or {})
            for gone in sorted(oldset - newset):
                log(f"DELETED  {p.name}/{gone}")
            for came in sorted(newset - oldset):
                log(f"CREATED  {p.name}/{came}  {new[came]}")
            for same in sorted(oldset & newset):
                if old[same] != new[same]:
                    log(f"CHANGED  {p.name}/{same}  {old[same]} -> {new[same]}")
            dirs[p] = new

log("--- watch window closed ---")
