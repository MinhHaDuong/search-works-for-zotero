#!/usr/bin/env python3
"""Copy a Zotero data directory for the clone rung, or refuse (ticket 0818).

Rung 4 of the sitter's ladder (`plugins/sdt-sitter/TESTING.md`) runs the sitter
on a copy of the author's own library. The copy is worth something only if it
is whole and taken with Zotero closed, and cheap only if it is a reflink. So:

- **Zotero closed.** Decided by the process list, `ps -eo comm=`, matching the
  bare name `zotero-bin` exactly -- never `pgrep -f`, which matched its own
  command line in an earlier probe here. Read before the copy and again after
  it, since a Zotero started mid-copy tears it. The profile locks are a
  cross-check: the author's profile carries a `lock` symlink with no Zotero
  running (ticket 0818's recon), so a lock is live only when the pid it names
  is, and a live one refuses on its own. The data directory has no lock of
  its own.
- **The whole tree.** `zotero.sqlite` references every attachment, so a
  partial copy would show Zotero missing files.
- **A reflink.** `cp -a --reflink=always`, which fails rather than falling back
  to a full byte copy (`=auto` copies 46 GB without a word). Source and
  destination must share a device (`st_dev`), and the destination's free space
  must clear a modest floor: a reflink needs little up front, but a sitter run
  writes packs into the copy. A failed copy removes what it wrote.

The destination must not exist. Copies live under
`~/data/clone-rung/<date>/`; the run record names when each goes.

The same recipe takes the pre-install snapshot for rung 5.

Exit codes: 0 copied; 1 refused or failed (nothing written); 2 usage.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PS_ARGV = ["ps", "-eo", "comm="]
ZOTERO_COMM = "zotero-bin"
DEFAULT_PROFILES = Path.home() / ".zotero" / "zotero"
DEFAULT_MIN_FREE_GB = 5.0


class Refused(Exception):
    """A precondition does not hold; nothing was copied."""


class CopyFailed(Exception):
    """`cp` failed; whatever it wrote has been removed."""


def zotero_processes(run=subprocess.run) -> int:
    """How many processes are named exactly `zotero-bin`."""
    out = run(PS_ARGV, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise Refused(f"could not read the process list: {' '.join(PS_ARGV)} "
                      f"exited {out.returncode}")
    return sum(1 for line in out.stdout.splitlines() if line.strip() == ZOTERO_COMM)


def _pid_alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def profile_locks(profiles_root: Path, pid_alive=_pid_alive) -> list[dict]:
    """Every profile `lock` symlink under `profiles_root`, with whether the
    pid it names (Firefox's `<ip>:+<pid>`) is alive."""
    locks = []
    if not profiles_root.is_dir():
        return locks
    for profile in sorted(p for p in profiles_root.iterdir() if p.is_dir()):
        lock = profile / "lock"
        if not lock.is_symlink():
            continue
        target = os.readlink(lock)
        try:
            pid = int(target.rsplit("+", 1)[1])
        except (IndexError, ValueError):
            locks.append({"profile": str(profile), "pid": None, "live": None,
                          "target": target})
            continue
        locks.append({"profile": str(profile), "pid": pid, "live": pid_alive(pid)})
    return locks


def _refuse_if_running(run, profiles_root: Path, when: str) -> list[dict]:
    n = zotero_processes(run)
    if n:
        raise Refused(f"{ZOTERO_COMM} is running ({n} process(es)) {when}: "
                      "quit Zotero first")
    locks = profile_locks(profiles_root)
    live = [lk for lk in locks if lk["live"]]
    if live:
        raise Refused(f"a live profile lock {when}, though no {ZOTERO_COMM} is "
                      f"listed: {live}")
    return locks


def _count(tree: Path) -> tuple[int, int]:
    files = size = 0
    for root, _dirs, names in os.walk(tree):
        for name in names:
            st = os.lstat(Path(root) / name)
            files += 1
            size += st.st_size
    return files, size


def clone_data(source: Path, dest: Path, *, profiles_root: Path = DEFAULT_PROFILES,
               min_free_gb: float = DEFAULT_MIN_FREE_GB, run=subprocess.run) -> dict:
    """Reflink-copy `source` to `dest`, or raise Refused / CopyFailed having
    written nothing. Returns the record of the copy."""
    source, dest = Path(source).absolute(), Path(dest).absolute()
    if not (source / "zotero.sqlite").is_file():
        raise Refused(f"{source} holds no zotero.sqlite: not a Zotero data directory")
    if dest.exists() or dest.is_symlink():
        raise Refused(f"{dest} exists; the recipe never writes into an existing path")

    locks = _refuse_if_running(run, profiles_root, "before the copy")

    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    if os.stat(source).st_dev != os.stat(parent).st_dev:
        raise Refused(f"{source} and {parent} are on different devices: a reflink "
                      "needs one filesystem")
    free_gb = shutil.disk_usage(parent).free / 1e9
    if free_gb < min_free_gb:
        raise Refused(f"{free_gb:.1f} GB free under {parent}, below the "
                      f"{min_free_gb:g} GB floor")

    wal = source / "zotero.sqlite-wal"
    wal_bytes = wal.stat().st_size if wal.exists() else None

    argv = ["cp", "-a", "--reflink=always", str(source), str(dest)]
    started = time.monotonic()
    out = run(argv, capture_output=True, text=True, check=False)
    seconds = time.monotonic() - started
    if out.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise CopyFailed(f"{' '.join(argv)} exited {out.returncode}: "
                         f"{(out.stderr or '').strip()} -- nothing kept")

    try:
        _refuse_if_running(run, profiles_root, "after the copy (it may be torn)")
    except Refused:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    files, size = _count(dest)
    return {"source": str(source), "dest": str(dest), "argv": argv,
            "seconds": round(seconds, 1), "files": files, "bytes": size,
            "wal_bytes": wal_bytes, "free_gb_before": round(free_gb, 1),
            "locks": locks,
            "when": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True,
                        help="the Zotero data directory to copy")
    parser.add_argument("--dest", type=Path, required=True,
                        help="where the copy goes; must not exist "
                             "(convention: ~/data/clone-rung/<date>/Zotero)")
    parser.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES,
                        help="the Zotero profiles directory whose locks are cross-checked")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        rec = clone_data(args.source, args.dest, profiles_root=args.profiles,
                         min_free_gb=args.min_free_gb)
    except (Refused, CopyFailed) as exc:
        print(f"{type(exc).__name__.upper()}: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(rec, indent=2)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
