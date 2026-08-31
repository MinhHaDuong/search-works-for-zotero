#!/usr/bin/env python3
"""What upstream did since the reviewed baseline, in one command.

`make upstream-status` answers one bit: has upstream moved. The bit is the
cheap half. The expensive half is what moved, and on 2026-08-31 that was
half a session of archaeology done by hand — clone, walk the tag list, read
the log between two tags, grep the merge subjects for item numbers, diff the
search layer, compare the pull refs against a list nobody had kept. Every step
of it is mechanical, and none of it is a judgement. So it is here instead.

What this does NOT do, deliberately: it never says whether an issue is open or
closed. That state belongs to the forge, which owns it and answers instantly,
and a copy of it here would be stale the moment somebody clicked a button. The
report ends with the query URL instead. SYNC.md already settled this for one
class of decaying fact — "the count that matters from now on is his —
re-counted there at send time, never quoted from here" — and an item's state is
the same kind of fact as a test count.

The mirror is bare and git-ignored. Fetching it is incremental, so the second
run costs a round trip rather than a clone.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MIRROR = REPO / "upstream.git"

#: Refspecs worth mirroring. Pull heads are what make a new PR visible before
#: it merges — the only pre-merge signal available without an API token.
REFSPECS = [
    "+refs/heads/*:refs/heads/*",
    "+refs/tags/*:refs/tags/*",
    "+refs/pull/*/head:refs/pull/*/head",
]

#: `#31`, `(#32)`, `Closes #30` — an upstream item named in a commit subject or
#: body. Three digits at most, and the bound is the point: upstream is in the
#: forties, while an unbounded `#\d+` swallows byte counts and SHA fragments and
#: reports items nobody filed. Widen it when upstream reaches #999, not before.
ITEM = re.compile(r"#(\d{1,3})\b")

#: A release tag. Anything else in refs/tags is not a release here.
RELEASE = re.compile(r"^v\d+\.\d+\.\d+$")


def upstream_config() -> dict[str, str]:
    """`UPSTREAM`, parsed the way the Makefile's `include` reads it."""
    out = {}
    for line in (REPO / "UPSTREAM").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def git(*args: str, cwd: Path | None = None) -> str:
    """Run git, returning stdout. Failure is the caller's to interpret."""
    done = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def sync_mirror(url: str) -> None:
    """Create or update the bare mirror. Incremental after the first run."""
    if not (MIRROR / "HEAD").exists():
        print(f"cloning the mirror into {MIRROR.name}/ (first run only)…", flush=True)
        git("clone", "--bare", url, str(MIRROR))
    git("fetch", "--prune", "--quiet", url, *REFSPECS, cwd=MIRROR)


def is_ancestor(maybe: str, of: str) -> bool:
    """`git merge-base --is-ancestor`, whose answer is its exit status.

    Kept out of `git()` on purpose: there a non-zero exit is a failure to
    report, and here it is the reply.
    """
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", maybe, of],
            cwd=str(MIRROR),
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def released(sha: str) -> str:
    """The release tag pointing at `sha`, or an empty string."""
    for line in git("tag", "--points-at", sha, cwd=MIRROR).splitlines():
        if RELEASE.match(line.strip()):
            return line.strip()
    return ""


def main() -> int:
    cfg = upstream_config()
    url = cfg["UPSTREAM_REPOSITORY"]
    branch = cfg["UPSTREAM_BRANCH"]
    base = cfg["UPSTREAM_REVIEWED_SHA"]

    sync_mirror(url)

    head = git("rev-parse", branch, cwd=MIRROR).strip()
    print(
        f"reviewed  {base[:7]}  {cfg['UPSTREAM_REVIEWED_VERSION']}"
        f"  ({cfg['UPSTREAM_REVIEWED_DATE']})"
    )
    print(f"upstream  {head[:7]}  {released(head) or '(untagged)'}  ({branch})")

    if head == base:
        print("\nOK: the reviewed baseline is current. Nothing to catch up on.")
        return 0

    span = f"{base}..{branch}"
    baseline_date = git("log", "-1", "--format=%cI", base, cwd=MIRROR).strip()

    # Releases, oldest first, so the reader walks forward from the baseline.
    releases = []
    for tag in git("tag", "--merged", branch, cwd=MIRROR).splitlines():
        tag = tag.strip()
        if not RELEASE.match(tag):
            continue
        tag_sha = git("rev-list", "-n1", tag, cwd=MIRROR).strip()
        # Merged into the branch but not behind the baseline: shipped since.
        if not is_ancestor(tag_sha, base):
            when = git("log", "-1", "--format=%cs", tag_sha, cwd=MIRROR).strip()
            releases.append((when, tag, tag_sha))
    releases.sort()
    if releases:
        print(f"\n{len(releases)} release(s) since the baseline:")
        for date, tag, sha in releases:
            print(f"  {tag:<10} {sha[:7]}  {date}")

    log = git("log", "--format=%H%x1f%s%x1f%b%x1e", span, cwd=MIRROR)
    commits = [c for c in log.split("\x1e") if c.strip()]
    print(f"\n{len(commits)} commit(s) since the baseline.")

    items = sorted({int(n) for c in commits for n in ITEM.findall(c)})
    if items:
        print("upstream items named in them: " + " ".join(f"#{n}" for n in items))

    merges = git(
        "log", "--merges", "--format=  %h %s", span, cwd=MIRROR
    ).splitlines()
    if merges:
        print(f"\n{len(merges)} merge(s) — what actually landed:")
        print("\n".join(merges))

    stat = git("diff", "--shortstat", span, "--", "src/features/search/", cwd=MIRROR).strip()
    if stat:
        added = git("diff", "--name-status", span, "--", "src/features/search/", cwd=MIRROR)
        new = [ln.split("\t")[-1] for ln in added.splitlines() if ln.startswith("A")]
        print(f"\nsearch layer: {stat}")
        for path in new:
            print(f"  new: {path}")

    # A pull ref whose head postdates the baseline is a PR this repo has not
    # seen. It says nothing about whether the PR is open — see the module note.
    fresh = []
    for ref in git("for-each-ref", "--format=%(refname)", "refs/pull/", cwd=MIRROR).splitlines():
        number = ref.strip().split("/")[2]
        when = git("log", "-1", "--format=%cI", ref.strip(), cwd=MIRROR).strip()
        if when > baseline_date:
            fresh.append((when, int(number)))
    if fresh:
        nums = " ".join(f"#{n}" for _, n in sorted(fresh))
        print(f"\npull refs newer than the baseline: {nums}")

    others = [
        b.strip()
        for b in git("for-each-ref", "--format=%(refname:short)", "refs/heads/", cwd=MIRROR).splitlines()
        if b.strip() and b.strip() != branch
    ]
    if others:
        print(f"other upstream branches: {', '.join(others)}")

    slug = re.sub(r"^https://github\.com/|\.git$", "", url)
    print(
        "\nOpen/closed state is the forge's and is deliberately not mirrored here:"
        f"\n  https://github.com/{slug}/issues?q=is%3Aissue+sort%3Acreated-desc"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
