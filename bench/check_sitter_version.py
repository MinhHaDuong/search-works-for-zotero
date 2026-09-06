#!/usr/bin/env python3
"""No two sitter payloads may answer to one version. Ticket 0688.

The XPI is hand-delivered to the author, so there is no registry, no release
feed and no installer to notice that the file he just dropped in is a different
plugin from the one already carrying that number. Zotero keys its add-on record
on the manifest `version`; two builds sharing one are indistinguishable to it,
to the author's `extensions.json`, and to any bug report either of them
produces. The sitter has already shipped several payloads under `2.2.0`.

WHAT IS COMPARED, and it is anchored at the tip rather than swept over the
whole history:

1. **No regression.** No commit's manifest version is greater than the working
   tree's. A number that goes backwards means the newer artifact looks older.
2. **No reuse.** No earlier commit carries the working tree's version over a
   DIFFERENT payload — the three files `build_sdt_sitter.DELIVERED` names,
   hashed together. Change one byte of `bootstrap.js` without bumping and this
   fires; bump and it clears.

WHERE IT IS DELIBERATELY BLIND, because a guard's blind spot is worth more
written down than discovered. It says nothing about a collision between two
purely historical versions — `2.2.0`'s several payloads are recorded and
unfixable, and a guard that reddened over them would be a guard nobody could
make green, which is a guard that gets deleted. Anchoring at the tip is what
makes it both true today and binding tomorrow: the very next unbumped payload
change is a collision with the tip's own version.

It needs real history to say anything. A checkout that has none — not a git
tree, or a shallow clone whose boundary could hide the earlier payload at this
exact version — reports NOT-RUN and exits non-zero. A gate that cannot look
must never answer green.

    python3 bench/check_sitter_version.py [--root .]
"""

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path

from build_sdt_sitter import DELIVERED

#: Where the payload lives, relative to the repository root.
SITTER = "bench/sdt-sitter"

log = logging.getLogger("check_sitter_version")


def parse(version: str) -> tuple[int, ...]:
    """`"2.10.0"` → `(2, 10, 0)`. A dotted version sorts as numbers, not as text.

    String order calls 2.10.0 older than 2.9.0, which is the direction that
    lets a regression pass. A component that is not an integer is a manifest
    this guard cannot order, and it says so rather than guessing.
    """
    return tuple(int(part) for part in version.split("."))


def payload(read) -> str | None:
    """One digest over every delivered file, or None if the manifest is not there.

    `read(name)` returns the file's bytes or None. A revision missing the
    manifest predates the plugin (or removed it); it carries no version and is
    not compared. A revision missing some OTHER delivered file is compared
    anyway, with that file's absence folded into the digest — a payload that
    lost a file is a different payload.
    """
    manifest = read("manifest.json")
    if manifest is None:
        return None
    digest = hashlib.sha256()
    for name in DELIVERED:
        content = read(name)
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00" if content is None else b"\x01")
        digest.update(content or b"")
    return digest.hexdigest()


def version_of(read) -> str | None:
    """The manifest `version` at one revision; None if unreadable rather than absent."""
    manifest = read("manifest.json")
    if manifest is None:
        return None
    try:
        value = json.loads(manifest.decode("utf-8")).get("version")
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, str) else None


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=root, capture_output=True)


def worktree_reader(root: Path):
    def read(name: str) -> bytes | None:
        path = root / SITTER / name
        return path.read_bytes() if path.is_file() else None
    return read


def commit_reader(root: Path, sha: str):
    def read(name: str) -> bytes | None:
        shown = git(root, "show", f"{sha}:{SITTER}/{name}")
        return shown.stdout if shown.returncode == 0 else None
    return read


def history(root: Path) -> list[str]:
    """Every commit that touched the payload, newest first."""
    listed = git(root, "log", "--format=%H", "--", SITTER)
    return listed.stdout.decode("utf-8", "replace").split()


def run(root: Path) -> tuple[list[str], str, int]:
    """Findings, the working tree's version, and how many revisions were read."""
    current_version = version_of(worktree_reader(root))
    if current_version is None:
        return ([f"{root / SITTER}/manifest.json is absent or carries no string version"],
                "", 0)
    current = parse(current_version)
    current_payload = payload(worktree_reader(root))
    findings, read = [], 0
    for sha in history(root):
        reader = commit_reader(root, sha)
        was = version_of(reader)
        if was is None:
            continue
        read += 1
        if parse(was) > current:
            findings.append(
                f"{sha[:12]} carries version {was}, ahead of the working tree's "
                f"{current_version}. A version that goes backwards makes the newer "
                "artifact look older to Zotero and to every bug report about it.")
        elif was == current_version and payload(reader) != current_payload:
            findings.append(
                f"{sha[:12]} already shipped a DIFFERENT payload under version "
                f"{current_version}. Bump the manifest version: two builds sharing "
                "one number are indistinguishable in the author's extensions.json.")
    return findings, current_version, read


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="repository root to check (default: the working directory)")
    root = parser.parse_args().root.resolve()

    if not (root / SITTER / "manifest.json").is_file():
        log.error("FAIL: no %s/manifest.json under %s", SITTER, root)
        return 1
    if git(root, "rev-parse", "--git-dir").returncode:
        log.error("NOT-RUN: %s is not a git checkout, so no earlier payload can be read. "
                  "This guard compares the working tree against history and has none.", root)
        return 1
    git_dir = git(root, "rev-parse", "--absolute-git-dir").stdout.decode().strip()
    if (Path(git_dir) / "shallow").exists():
        log.error("NOT-RUN: this checkout is shallow, so a payload older than its boundary "
                  "is invisible and a reused version would read as unused. Run "
                  "`git fetch --unshallow` before trusting a verdict here.")
        return 1

    try:
        findings, version, read = run(root)
    except ValueError as exc:
        log.error("FAIL: a manifest version this guard cannot order: %s", exc)
        return 1
    for finding in findings:
        log.error("FAIL: %s", finding)
    if findings:
        return 1
    log.info("OK: version %s is ahead of all %d earlier revisions of %s, and no earlier "
             "revision shipped a different payload under it", version, read, SITTER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
