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

IT BITES INSIDE A BRANCH TOO, and that is intended rather than tolerated. An
unbumped payload change fires against the branch's own previous commit, not
only against `main`. In another workshop that would be nagging; here it is the
case that matters, because this plugin is hand-delivered — ticket 0680 carried
an XPI to the author's home directory straight from a branch. A commit on a
branch is a payload someone can install, so it needs its own number.

WHERE IT IS DELIBERATELY BLIND, because a guard's blind spot is worth more
written down than discovered. It says nothing about a collision between two
purely historical versions — `2.2.0`'s several payloads are recorded and
unfixable, and a guard that reddened over them would be a guard nobody could
make green, which is a guard that gets deleted. Anchoring at the tip is what
makes it both true today and binding tomorrow: the very next unbumped payload
change is a collision with the tip's own version.

It needs real history to say anything, and every way of having none is a
NOT-RUN rather than a green — a gate that cannot look must never answer as
though it had. Four are covered, and they were found one at a time, each by a
control rather than by reading the code:

* **not a git tree** — nothing to compare against;
* **a shallow clone** — its boundary hides the earlier payload. Detected with
  `--is-shallow-repository`, NOT the `shallow` marker under
  `--absolute-git-dir`: that marker lives in the common git dir, so from a
  linked worktree, which is how every lane here works, the marker check looks
  where it never is;
* **a grafted history** — `git replace --graft` truncates the visible ancestry
  and sets no marker at all, so the shallow probe answers false;
* **no commit touching the payload path** — a fresh checkout, or a rename to a
  path whose history starts empty. Zero revisions compared is no comparison;
* **a partial clone** — commits present, blobs absent. `git show` fails there
  exactly as it does on a path that never existed, and only the tree can say
  which, so the tree is asked;
* **a redirected environment** — `GIT_DIR` and its relatives answer about a
  different repository than `--root` names, so they are stripped rather than
  detected. There is no case where this guard wants one tree's files read
  against another tree's log.

What it still cannot see: a rewritten history that keeps the same shape (a
filter-branch that edited an old manifest in place), and a payload delivered
outside this repository. Both are outside what a path's own log can evidence.

    python3 bench/check_sitter_version.py [--root .]
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from build_sdt_sitter import DELIVERED

#: Where the payload lives, relative to the repository root.
SITTER = "bench/sdt-sitter"

#: Environment that redirects git away from `--root`. Inherited from whoever ran
#: the gate, and every one of these silently answers the question about a
#: DIFFERENT repository — `--root` names the working tree to read and the
#: environment quietly names the history, so the guard reported OK about a
#: repository it had not looked at. Stripped rather than detected: there is no
#: case where this guard wants to read one tree's files against another's log.
REDIRECTING = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
               "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
               "GIT_CEILING_DIRECTORIES", "GIT_NAMESPACE")

log = logging.getLogger("check_sitter_version")


class Unreadable(Exception):
    """A blob the tree names and the repository cannot produce.

    A partial (blobless) clone has the commits and not their contents. `git
    show` fails on both that and a path which never existed, and only one of
    those is a payload that was never there — conflating them turned a history
    the guard could not read into a history with nothing in it.
    """


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
    environment = {name: value for name, value in os.environ.items()
                   if name not in REDIRECTING}
    # A promisor remote would otherwise fetch a missing blob mid-gate, turning
    # the partial-clone case into a network call instead of the NOT-RUN below.
    environment["GIT_NO_LAZY_FETCH"] = "1"
    return subprocess.run(["git", *arguments], cwd=root, capture_output=True, env=environment)


def worktree_reader(root: Path):
    def read(name: str) -> bytes | None:
        path = root / SITTER / name
        return path.read_bytes() if path.is_file() else None
    return read


def commit_reader(root: Path, sha: str):
    def read(name: str) -> bytes | None:
        address = f"{sha}:{SITTER}/{name}"
        shown = git(root, "show", address)
        if shown.returncode == 0:
            return shown.stdout
        # `git show` failed. The tree says which of the two reasons it was, and
        # it can say so without the blob: a name the tree lists is a payload
        # that exists and could not be produced, which is a gap in the clone
        # rather than a file that was never committed.
        listed = git(root, "ls-tree", "--name-only", sha, "--", f"{SITTER}/{name}")
        if listed.returncode == 0 and listed.stdout.strip():
            raise Unreadable(f"{address} is listed by the tree but its object is not here")
        return None
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
        # Numerically, like the regression check one line up, and not as text.
        # `"2.03.0"` and `"2.3.0"` are one version to any dotted-number
        # comparator, Zotero's included; string equality calls them two, so a
        # leading zero slipped a changed payload past BOTH checks at once.
        elif parse(was) == current and payload(reader) != current_payload:
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
    # `--is-shallow-repository`, and not the `shallow` marker under
    # `--absolute-git-dir`: that marker lives in the COMMON git dir, so a linked
    # worktree — which is how every lane in this repository works — looks for it
    # in its own per-worktree dir, never finds it, and answers green while blind.
    # Probed three ways (full clone, shallow primary, shallow linked worktree);
    # only this form is right in all three.
    if git(root, "rev-parse", "--is-shallow-repository").stdout.decode().strip() == "true":
        log.error("NOT-RUN: this checkout is shallow, so a payload older than its boundary "
                  "is invisible and a reused version would read as unused. Run "
                  "`git fetch --unshallow` before trusting a verdict here.")
        return 1
    # A grafted history is a truncated one that sets no marker: `git replace
    # --graft` cuts the visible ancestry while `--is-shallow-repository` still
    # answers false. Reproduced — 17 real revisions against 3 after grafting,
    # same tip, opposite truth, and the same OK sentence either way. A replace
    # ref in a checkout being gated is not a state to reason under.
    if git(root, "for-each-ref", "--format=%(refname)", "refs/replace/").stdout.strip():
        log.error("NOT-RUN: this checkout carries replace/graft refs, so the history read "
                  "here is not the history that was written and a truncated ancestry would "
                  "read as an absent one. Run `git replace --list` and clear them first.")
        return 1

    try:
        findings, version, read = run(root)
    except Unreadable as exc:
        log.error("NOT-RUN: %s. This checkout has the commits and not their contents — a "
                  "partial or filtered clone — so an earlier payload cannot be hashed and a "
                  "reused version would read as unused. Run `git fetch --refetch` or clone "
                  "without a filter before trusting a verdict here.", exc)
        return 1
    except ValueError as exc:
        log.error("FAIL: a manifest version this guard cannot order: %s", exc)
        return 1
    if not findings and read == 0:
        # The last way to be blind and look green: a checkout that is neither
        # shallow nor grafted and simply has no commit touching the payload —
        # a fresh `git init`, or the payload moved to a new path whose history
        # starts empty (ticket 0697's rename is exactly that). Zero revisions
        # compared is not a clean comparison, it is no comparison.
        log.error("NOT-RUN: no commit under %s touches %s, so there is no earlier payload "
                  "to compare against. If the directory was just renamed, pass the old path "
                  "too; if the checkout is fresh, this guard has nothing to say yet.",
                  root, SITTER)
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
