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

import argparse
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

#: The surface this repository actually reasons about. Upstream ships several
#: times a day and most of it is none of our business — a docs pass, a tool this
#: chain never models. Reading every release is not sustainable and was never
#: required; what is required is knowing whether a release touched US. That is a
#: path set, so it is answerable in one diff.
WATCHED = ["src/features/search/"]

#: The two facts that break this repo's own drivers without breaking upstream:
#: the index schema's version, and the shape of the table the drivers open.
#: Ticket 0100 exists because a driver was pinned to a schema that had moved.
SCHEMA_FILE = "src/features/search/sqlite-index.ts"
SCHEMA_VERSION = re.compile(r"SCHEMA_VERSION\s*=\s*(\d+)")
PASSAGES_DDL = re.compile(
    r"CREATE TABLE IF NOT EXISTS passages\s*\((.*?)\)", re.S
)


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


def schema_at(rev: str) -> tuple[str | None, str | None]:
    """The index schema version and `passages` shape at `rev`.

    Read rather than inferred, and read separately from the diff: a schema can
    move without the version moving (an additive column under the same stamp),
    and that is the shape that breaks a driver silently — it still opens, and
    returns the wrong thing.
    """
    try:
        src = git("show", f"{rev}:{SCHEMA_FILE}", cwd=MIRROR)
    except RuntimeError:
        return None, None
    version = SCHEMA_VERSION.search(src)
    ddl = PASSAGES_DDL.search(src)
    return (
        version.group(1) if version else None,
        re.sub(r"\s+", " ", ddl.group(1)).strip() if ddl else None,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--full",
        action="store_true",
        help="the merge list, pull refs and branches, not only the verdict",
    )
    args = ap.parse_args()

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
        print("\nQUIET: the reviewed baseline is current. Nothing to catch up on.")
        return 0

    span = f"{base}..{branch}"
    baseline_date = git("log", "-1", "--format=%cI", base, cwd=MIRROR).strip()

    releases = []
    for tag in git("tag", "--merged", branch, cwd=MIRROR).splitlines():
        tag = tag.strip()
        if not RELEASE.match(tag):
            continue
        tag_sha = git("rev-list", "-n1", tag, cwd=MIRROR).strip()
        if not is_ancestor(tag_sha, base):
            when = git("log", "-1", "--format=%cs", tag_sha, cwd=MIRROR).strip()
            releases.append((when, tag, tag_sha))
    releases.sort()

    log = git("log", "--format=%H%x1f%s%x1f%b%x1e", span, cwd=MIRROR)
    commits = [c for c in log.split("\x1e") if c.strip()]
    print(
        f"          {len(releases)} release(s), {len(commits)} commit(s) since the baseline"
    )

    # THE VERDICT. Everything below this line is detail for someone who has
    # already been told they need it.
    stat = git("diff", "--shortstat", span, "--", *WATCHED, cwd=MIRROR).strip()
    was_version, was_ddl = schema_at(base)
    now_version, now_ddl = schema_at(branch)
    schema_moved = (was_version, was_ddl) != (now_version, now_ddl)

    if not stat and not schema_moved:
        print(
            f"\nQUIET: nothing under {', '.join(WATCHED)}, and the index schema is"
            f" unchanged.\n       None of it is yours. Catch up when you need"
            f" currency, not because upstream shipped."
        )
        return 0

    print("\nTOUCHED — this one is yours to read:")
    if stat:
        names = git("diff", "--name-status", span, "--", *WATCHED, cwd=MIRROR)
        new = [ln.split("\t")[-1] for ln in names.splitlines() if ln.startswith("A")]
        print(f"  search layer   {stat}")
        for path in new:
            print(f"                 new: {path}")
    if schema_moved:
        print(f"  index schema   SCHEMA_VERSION {was_version} -> {now_version}")
        if was_ddl != now_ddl:
            print("                 passages table shape CHANGED — bench drivers open it")
    else:
        print(f"  index schema   unchanged (SCHEMA_VERSION {now_version}, same passages shape)")

    items = sorted({int(n) for c in commits for n in ITEM.findall(c)})
    if items:
        print("  items named    " + " ".join(f"#{n}" for n in items))

    if not args.full:
        print("\n  --full for the release list, merges, pull refs and branches.")
        return 0

    if releases:
        print(f"\n{len(releases)} release(s) since the baseline:")
        for when, tag, sha in releases:
            print(f"  {tag:<10} {sha[:7]}  {when}")

    merges = git("log", "--merges", "--format=  %h %s", span, cwd=MIRROR).splitlines()
    if merges:
        print(f"\n{len(merges)} merge(s) — what actually landed:")
        print("\n".join(merges))

    # A pull ref whose head postdates the baseline is a PR this repo has not
    # seen. It says nothing about whether the PR is open — see the module note.
    fresh = []
    for ref in git("for-each-ref", "--format=%(refname)", "refs/pull/", cwd=MIRROR).splitlines():
        ref = ref.strip()
        when = git("log", "-1", "--format=%cI", ref, cwd=MIRROR).strip()
        if when > baseline_date:
            fresh.append((when, int(ref.split("/")[2])))
    if fresh:
        print("\npull refs newer than the baseline: " + " ".join(f"#{n}" for _, n in sorted(fresh)))

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
