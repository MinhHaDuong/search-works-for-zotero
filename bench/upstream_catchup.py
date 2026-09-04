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
#:
#: It was one directory until 2026-09-03, and one directory was too few. The
#: standing report reasons about more than the index: it reasons about every
#: `ZOTEUS_*` default (`src/config.ts`), about the tool surface every
#: requirement is phrased over (`src/tools/`), about which API serves a read
#: (`src/router/`), and about the one external call the default path makes
#: (`src/lib/update-check.ts`). Each entry below names the rows that need it.
#:
#: The cost of the narrow set is measurable rather than hypothetical, and it is
#: measurable twice. At `v1.12.0..v1.13.0` the old set missed `src/config.ts`,
#: where the local embedder became selectable and gained a precision knob — the
#: two facts that made R7's row WRONG rather than dated. And at
#: `v1.7.2..v1.7.3` the old set is entirely EMPTY while eighteen files changed
#: outside it, `src/config.ts` among them at +226 lines: a release about the
#: configuration surface, reported as "None of it is yours".
WATCHED = [
    # The index, the crawl, extraction, embedding, salvage, migration. R1, R3,
    # R4, R8, R16, R17, R19, R23, R24, R32, R33, R35.
    "src/features/",
    # The MCP surface every requirement is phrased over — the verbs R22 counts,
    # the notices R4 and R17 read, the scope block R5 and R18 are about.
    "src/tools/",
    # Every default a "on the default path" claim rests on. R7's embedder, R8's
    # caps, R10's transport and update check, R15's data directory.
    "src/config.ts",
    # Which API serves a read, which is R12's library identity and the narrower
    # read-transport gap SPEC.md §6 discloses.
    "src/router/",
    # R10's one standing egress observation, and the subject of an unratified
    # entry in DECISIONS.md. A file, not a directory, on purpose.
    "src/lib/update-check.ts",
]

#: The same judgement as the comments above `WATCHED`, in a form a script can
#: read: which requirement rows each watched path backs. Kept in sync by hand
#: with those comments -- this is the same judgement stated twice, not a
#: computation, and `test_watched_rows_agrees_with_the_watched_comments` is the
#: guard against the two drifting apart silently.
WATCHED_ROWS: dict[str, list[str]] = {
    "src/features/": [
        "R1", "R3", "R4", "R8", "R16", "R17", "R19", "R23", "R24", "R32", "R33", "R35",
    ],
    "src/tools/": ["R4", "R5", "R17", "R18", "R22"],
    "src/config.ts": ["R7", "R8", "R10", "R15"],
    "src/router/": ["R12"],
    "src/lib/update-check.ts": ["R10"],
}


def affected_rows(touched: set[str]) -> tuple[list[str], list[str]]:
    """Split every row `WATCHED_ROWS` names into affected and untouched, given
    the subset of `WATCHED` a span actually changed.

    Pure on purpose, unlike the git-calling half that decides `touched` (see
    `touched_watched_paths`): the split itself is a set operation and a test
    can hold it without a mirror. A row backed by more than one path is
    affected if ANY of them moved -- a row's premise can rest on either.
    """
    affected = {row for path in touched for row in WATCHED_ROWS.get(path, [])}
    every_row = {row for rows in WATCHED_ROWS.values() for row in rows}
    key = lambda row: int(row[1:])  # noqa: E731
    return sorted(affected, key=key), sorted(every_row - affected, key=key)


def touched_watched_paths(span: str) -> set[str]:
    """Which entries of `WATCHED` actually changed over `span`."""
    return {
        path
        for path in WATCHED
        if git("diff", "--shortstat", span, "--", path, cwd=MIRROR).strip()
    }

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


#: `file.ext:123` or `file.ext:123-456`, the citation form SPEC.md uses to stamp
#: a premise to a source line. `.js` is here for Zotero-core citations (the
#: platform this repo also cites, via #6012) even though `WATCHED` and the
#: mirror below only ever resolve the zoteus ones -- see `citation_drift`.
CITATION = re.compile(r"`([A-Za-z0-9_.-]+\.(?:ts|tsx|mjs|js)):(\d+)(?:-(\d+))?`")


def citations_in(text: str) -> list[tuple[str, int, int]]:
    """Every citation `text` makes, deduplicated, as `(basename, start, end)`.

    Pure parsing, unlike `citation_drift` below which resolves each one against
    the mirror -- kept separate so the regex has a test that needs no network.
    """
    seen: dict[tuple[str, int, int], None] = {}
    for name, start, end in CITATION.findall(text):
        key = (name, int(start), int(end) if end else int(start))
        seen[key] = None
    return list(seen)


def resolve_path(basename: str, rev: str) -> str | None:
    """The repo-relative path `basename` names at `rev`, or `None`.

    A citation names a bare filename because that reads naturally in a
    sentence; `git show` needs the full path. `None` covers two different
    facts a caller must not confuse: no file in the zoteus tree has this name
    (likely a Zotero-core citation, out of this mirror's reach), or more than
    one does, where guessing which one a citation meant would be worse than
    saying so.
    """
    names = git("ls-tree", "-r", "--name-only", rev, cwd=MIRROR).splitlines()
    matches = [n for n in names if n.rsplit("/", 1)[-1] == basename]
    return matches[0] if len(matches) == 1 else None


def cited_lines(rev: str, path: str, start: int, end: int) -> str | None:
    """The exact text lines `start`..`end` hold at `rev`, or `None` if the file
    or the line range does not exist there."""
    try:
        src = git("show", f"{rev}:{path}", cwd=MIRROR)
    except RuntimeError:
        return None
    lines = src.splitlines()
    if start < 1 or end > len(lines):
        return None
    return "\n".join(lines[start - 1 : end])


def citation_drift(base: str, head: str) -> list[tuple[str, int, int, str]]:
    """Every SPEC.md citation, and whether the lines it names still read what
    they read at `base`.

    A `file:line` citation is a promise that the mechanism it backs is at that
    exact spot; nothing enforces it, so it silently rots the moment upstream
    reflows the file around it -- the same failure class a stale README row is,
    stamped to a line instead of a verdict. This does not fix a drifted
    citation, and it does not try to relocate the text elsewhere in the file:
    it names which of SPEC.md's citations a human still has to re-point, so a
    re-baseline stops re-grepping all of them to find the few that moved.
    """
    spec = (REPO / "SPEC.md").read_text(encoding="utf-8")
    results = []
    for name, start, end in citations_in(spec):
        path = resolve_path(name, head)
        if path is None:
            results.append(
                (name, start, end, "unresolved — not a unique path in the zoteus "
                                    "mirror (Zotero-core citation, or renamed)")
            )
            continue
        was = cited_lines(base, path, start, end)
        now = cited_lines(head, path, start, end)
        if was is None:
            results.append((name, start, end, f"unresolved — absent at the reviewed baseline ({path})"))
        elif was == now:
            results.append((name, start, end, "unchanged"))
        else:
            results.append((name, start, end, f"DRIFTED — {path} reads differently now"))
    return results


#: How many of the residue's files to name. Enough to recognise a release about
#: the configuration surface; short enough that a docs pass stays one line.
RESIDUE_NAMED = 6


def residue(span: str) -> tuple[str, list[str]]:
    """The delta OUTSIDE `WATCHED`: a shortstat and the paths, largest first.

    Separate from the verdict on purpose. The verdict says whether this release
    is ours to read; this says what the verdict did not look at, so a reader can
    tell "nothing changed" from "nothing changed where we looked".
    """
    exclude = [f":(exclude){path}" for path in WATCHED]
    stat = git("diff", "--shortstat", span, "--", ".", *exclude, cwd=MIRROR).strip()
    if not stat:
        return "", []
    numstat = git("diff", "--numstat", span, "--", ".", *exclude, cwd=MIRROR)
    rows = []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        # A binary file reports `-` for both counts; it is still a changed file.
        weight = sum(int(n) for n in (added, removed) if n.isdigit())
        rows.append((weight, path))
    rows.sort(reverse=True)
    return stat, [f"{path} ({weight})" for weight, path in rows[:RESIDUE_NAMED]]


def report_residue(outside: tuple[str, list[str]]) -> None:
    """Print the residue, and say plainly that it was not read."""
    stat, top = outside
    if not stat:
        print("  outside        nothing changed outside the watched surface either")
        return
    print(f"  outside        {stat} — NOT read by this verdict")
    for path in top:
        print(f"                 {path}")


#: A bare filename with a source extension, the form a ticket log entry uses
#: when it names a seam ("`sqlite-index.ts`", "`index-manager.ts:1745-1753`") --
#: no line number required, unlike `CITATION`, because most ticket references
#: don't carry one.
FILE_REF = re.compile(r"\b([A-Za-z0-9_.-]+\.(?:ts|tsx|mjs|js))\b")


def open_ticket_paths() -> dict[Path, set[str]]:
    """Every open ticket, and the upstream file basenames its text names.

    Open only (`tickets/*.erg`, not `tickets/closed/`): a closed ticket's file
    references are history, and re-deriving history is not what a re-baseline
    is for. The match is on basename, matching `FILE_REF` -- a ticket log entry
    writes `sqlite-index.ts`, not `src/features/search/sqlite-index.ts`, and
    the two name the same file.
    """
    out = {}
    for path in sorted((REPO / "tickets").glob("*.erg")):
        names = set(FILE_REF.findall(path.read_text(encoding="utf-8")))
        if names:
            out[path] = names
    return out


def tickets_to_rederive(touched_basenames: set[str]) -> dict[Path, set[str]]:
    """Open tickets whose text names a file this span actually touched.

    Pure given its input, unlike `open_ticket_paths` and the `git diff
    --name-only` call that produces `touched_basenames` -- the split is a set
    intersection per ticket, testable without a mirror or a tickets/ fixture.
    A ticket naming a file the span never touched stays silent: printing it
    would be the blanket cost `WATCHED` itself exists to avoid, applied to
    `tickets/` instead of `README.md`.
    """
    return {
        path: matched
        for path, names in open_ticket_paths().items()
        if (matched := names & touched_basenames)
    }


#: Everything a re-baseline has to touch beyond `UPSTREAM` itself, with why.
#: Hand-maintained, and that is the honest form: it is a recipe, not a check. It
#: exists because three re-baselines rediscovered the same list, twice from a
#: closed ticket and once from a session's memory. A list nobody can forget
#: beats a guard nobody can satisfy — and it must never be read as a guarantee
#: that nothing else moved, which is what the re-read is for.
REBASELINE_TOUCHES = [
    ("bench/index_schema.mjs",
     "the mirror of upstream's SCHEMA_VERSION, if the generation below moved"),
    ("bench/fixtures/make_index_fixture.mjs",
     "stamps that generation into the current fixture; if the schema gained a "
     "table, the fixture needs it or it stamps a shape it does not have"),
    ("README.md",
     "every standing row, both headline bars, each section bar, the goal bars, "
     "the evidence tally, the spelled-out counts, and the Measured-against line"),
    ("SPEC.md",
     "every premise stamped to a SHA — §5's seven facts above all — and every "
     "file:line citation, which move even when the mechanism does not"),
    ("SYNC.md",
     "the title, the head note, the status-table stamp, and every item whose "
     "state the release changed"),
    ("DECISIONS.md",
     "a NEW entry. Append-only: a moved baseline is never an edit of an old one"),
    ("verification/UPSTREAM-<version>-REREAD.md",
     "the read itself, as a new file. The previous one is a dated record"),
    ("bench/results/smoke-<version>/",
     "re-run the smoke and the acceptance layer, or every row resting on them "
     "falls from `measured` to `code` — repair a stale assertion BEFORE the run, "
     "or the artifact publishes it"),
    ("tickets/",
     "a log entry on every open ticket arguing from a code seam at the old "
     "version, and on any ticket whose scope upstream has since built"),
]


def rebaseline(cfg: dict[str, str], base: str, head: str, head_ref: str) -> int:
    """Print the `UPSTREAM` block a re-baseline would write, and the rest of the recipe.

    Every value here is read out of the mirror rather than typed, which is the
    half of a re-baseline that is mechanical. What follows it is a checklist,
    and it is labelled as one: nothing in this function verifies that a re-read
    happened, and a printed list that looked like a verdict would be worse than
    no list at all. Three of its lines ARE narrowed mechanically -- README's
    rows, SPEC's citations, and the ticket shortlist -- because those three are
    computed from the same span everything else here is silent about, and
    printing "every standing row" to someone this script could tell "these
    seven, not those thirty" wastes exactly the read the narrowing exists to
    save.
    """
    tag = released(head)
    contained = tag
    if not contained:
        # The tip is past a release. Name the last release contained in the tree,
        # which is what the standing page dates itself by, and say how far past.
        described = git("describe", "--tags", "--match", "v*.*.*", head, cwd=MIRROR).strip()
        contained = described.split("-")[0] if "-" in described else described
        ahead = git("rev-list", "--count", f"{contained}..{head}", cwd=MIRROR).strip()
    else:
        ahead = "0"

    version, _ = schema_at(head_ref)
    today = git("log", "-1", "--format=%cs", head, cwd=MIRROR).strip()

    print("\nThe UPSTREAM block for this tip, computed:\n")
    print(f"UPSTREAM_REVIEWED_SHA={head}")
    print(f"UPSTREAM_REVIEWED_VERSION={contained}")
    print(f"UPSTREAM_REVIEWED_DATE={today}")
    print(f"UPSTREAM_INDEX_SCHEMA_VERSION={version or '(could not read)'}")

    if ahead != "0":
        print(
            f"\n  NOTE: the tip is {ahead} commit(s) past {contained}. The version above "
            f"names\n        the last release CONTAINED in the reviewed tree, not the tip. "
            f"Disclose\n        the gap in UPSTREAM's own comment — `check_progress` parses "
            f"vN.N.N and a\n        version string carrying the gap would fail to match itself."
        )
    if version and version != cfg.get("UPSTREAM_INDEX_SCHEMA_VERSION"):
        print(
            f"\n  NOTE: the index schema generation moves "
            f"{cfg.get('UPSTREAM_INDEX_SCHEMA_VERSION')} -> {version}. The mirror in\n"
            f"        bench/index_schema.mjs and the fixture that stamps it move with it, "
            f"and\n        the fixture must carry the new shape rather than only the new "
            f"number."
        )

    span = f"{base}..{head}"
    touched = touched_watched_paths(span)
    affected, unaffected = affected_rows(touched)
    drift = citation_drift(base, head)
    drifted = [c for c in drift if c[3].startswith("DRIFTED")]
    unresolved = [c for c in drift if c[3].startswith("unresolved")]
    all_changed = {
        Path(p).name for p in git("diff", "--name-only", span, cwd=MIRROR).splitlines()
    }
    rederive = tickets_to_rederive(all_changed)

    print("\nWhat a re-baseline must touch besides UPSTREAM:\n")
    for path, why in REBASELINE_TOUCHES:
        print(f"  {path}")
        print(f"      {why}")
        if path == "README.md":
            if affected:
                print(f"      likely affected by this span: {', '.join(affected)} — re-read these")
            if unaffected:
                print(f"      not touched by this span: {', '.join(unaffected)} — skip")
        elif path == "SPEC.md":
            print(f"      {len(drift) - len(drifted) - len(unresolved)}/{len(drift)} citations unchanged")
            for name, start, end, verdict in drifted:
                loc = f"{name}:{start}" if start == end else f"{name}:{start}-{end}"
                print(f"      {loc} — {verdict}")
            for name, start, end, verdict in unresolved:
                loc = f"{name}:{start}" if start == end else f"{name}:{start}-{end}"
                print(f"      {loc} — {verdict}")
        elif path == "tickets/":
            if rederive:
                for tpath, matched in sorted(rederive.items()):
                    print(f"      {tpath.name} — names {', '.join(sorted(matched))}")
            else:
                print("      no open ticket names a file this span touched")

    print(
        "\nThis is a recipe and not a verdict. Nothing here checks that a row was "
        "re-read;\nthe only thing that does is reading it. `make check` fails until the "
        "page names\nthe release UPSTREAM does — that is the gate, and it is the whole "
        "of the gate."
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--full",
        action="store_true",
        help="the merge list, pull refs and branches, not only the verdict",
    )
    ap.add_argument(
        "--base",
        metavar="REV",
        help="read from this revision instead of UPSTREAM_REVIEWED_SHA. The verdict "
             "this script gives is computed from a path list, so the only way to know "
             "it can still say TOUCHED is to point it at a range where it must — "
             "`--base v1.7.2 --head v1.7.3` is the recorded positive control (ticket 0622)",
    )
    ap.add_argument(
        "--head",
        metavar="REV",
        help="read up to this revision instead of the tracked branch",
    )
    ap.add_argument(
        "--rebaseline",
        action="store_true",
        help="print the UPSTREAM block a re-baseline would write, computed from the "
             "mirror, and the list of everything else a re-baseline must touch",
    )
    args = ap.parse_args()

    cfg = upstream_config()
    url = cfg["UPSTREAM_REPOSITORY"]
    branch = cfg["UPSTREAM_BRANCH"]
    base = cfg["UPSTREAM_REVIEWED_SHA"]

    sync_mirror(url)
    if args.base:
        base = git("rev-parse", args.base, cwd=MIRROR).strip()
    head_ref = args.head or branch
    head = git("rev-parse", head_ref, cwd=MIRROR).strip()

    if args.base or args.head:
        print(f"base      {base[:7]}  {released(base) or '(untagged)'}  (--base)")
    else:
        print(
            f"reviewed  {base[:7]}  {cfg['UPSTREAM_REVIEWED_VERSION']}"
            f"  ({cfg['UPSTREAM_REVIEWED_DATE']})"
        )
    print(f"upstream  {head[:7]}  {released(head) or '(untagged)'}  ({head_ref})")

    if args.rebaseline:
        return rebaseline(cfg, base, head, head_ref)

    if head == base:
        print("\nQUIET: the reviewed baseline is current. Nothing to catch up on.")
        return 0

    span = f"{base}..{head}"
    baseline_date = git("log", "-1", "--format=%cI", base, cwd=MIRROR).strip()

    releases = []
    for tag in git("tag", "--merged", head_ref, cwd=MIRROR).splitlines():
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
    now_version, now_ddl = schema_at(head_ref)
    schema_moved = (was_version, was_ddl) != (now_version, now_ddl)

    # What changed OUTSIDE the watched set. Reported whichever way the verdict
    # goes, and that is the point rather than a nicety: the verdict is computed
    # from a path list and used to be *stated* as a claim about the whole
    # release — "None of it is yours" — which is a claim about files nothing
    # looked at. A guard whose all-clear is reachable by failing to look is not
    # a guard, and neither is a report. Ticket 0622.
    outside = residue(span)

    if not stat and not schema_moved:
        print(
            f"\nQUIET in the watched surface: nothing under"
            f" {', '.join(WATCHED)}, and the index schema is unchanged."
        )
        report_residue(outside)
        print(
            "       Catch up when you need currency, not because upstream"
            " shipped."
        )
        return 0

    print("\nTOUCHED — this one is yours to read:")
    if stat:
        names = git("diff", "--name-status", span, "--", *WATCHED, cwd=MIRROR)
        new = [ln.split("\t")[-1] for ln in names.splitlines() if ln.startswith("A")]
        print(f"  watched        {stat}")
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
    report_residue(outside)

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
