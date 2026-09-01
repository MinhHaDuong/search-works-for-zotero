#!/usr/bin/env python3
"""No ticket log entry may be stamped after the commit that wrote it.

The rule the author ratified 2026-09-01 (`DECISIONS.md`), from ticket 0569's
three candidates. It is the weakest of the three and the only one that is both
checkable and true: a log is an append-only record, but this repository runs
parallel sessions, so a ticket's log is a merge of several append streams and
its stamps legitimately arrive out of order. Monotonicity would fire on those
honest files. What no honest stream can do is name a time that has not
happened.

`erg log` reads the real clock and cannot produce such a stamp. A hand-typed
entry can, and 169 of them had: Copilot found the first on PR #150, where six
tickets filed by one commit all claimed 16:30Z while the commit itself landed
at 11:51Z UTC.

WHAT IS COMPARED. Each stamp against the AUTHOR time of the commit `git blame`
attributes its line to, both truncated to the minute (stamps carry no seconds).
Author time, not committer time, because a rebase rewrites the latter: the
question is when the line was written, and a rebase does not rewrite that.

WHERE IT IS DELIBERATELY WEAK, said plainly because a guard's blind spot is
worth more written down than discovered. Blame names the commit that last
TOUCHED a line, which is at or after the one that introduced it, so a stamp on
a line later reformatted — or corrected, as this guard's own sweep corrected
169 — is checked against a laxer bound than the truth. The direction is safe:
it misses violations, it cannot invent them. What it costs is that a corrected
corpus verifies itself trivially, so the sweep behind the ruling was evidenced
by the introducing commit, walked per line, and only the standing guard reads
blame.

Lines not yet committed are checked against the clock instead, so a future
stamp is caught while it is still cheap to fix rather than one commit later.
"""

import argparse
import datetime as dt
import logging
import pathlib
import re
import subprocess
import sys

TICKETS = "tickets"
LOG_OPEN = "--- log ---"
SECTION = re.compile(r"^--- ")
STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})Z\s")
BLAME_HEADER = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)")
UNCOMMITTED = "0" * 40

log = logging.getLogger("check_ticket_logs")


def stamped_entries(path: pathlib.Path) -> list[tuple[int, dt.datetime]]:
    """Every stamped log-section entry as (1-indexed line number, stamp in UTC)."""
    entries = []
    inside = False
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        if line == LOG_OPEN:
            inside = True
            continue
        if inside and SECTION.match(line):
            break
        match = STAMP.match(line) if inside else None
        if match:
            stamp = dt.datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M")
            entries.append((number, stamp.replace(tzinfo=dt.timezone.utc)))
    return entries


def written(root: pathlib.Path, path: pathlib.Path, first: int, last: int):
    """Line number → author time of the commit blame attributes it to; None if uncommitted."""
    proc = subprocess.run(
        ["git", "blame", "--line-porcelain", "-L", f"{first},{last}", "--",
         path.relative_to(root).as_posix()],
        cwd=root, capture_output=True, text=True,
    )
    if proc.returncode:  # a file git has never seen: every line is as new as the working tree
        return {}
    times: dict[int, dt.datetime | None] = {}
    number, sha = None, ""
    for line in proc.stdout.split("\n"):
        header = BLAME_HEADER.match(line)
        if header:
            sha, number = header.group(1), int(header.group(2))
            if sha == UNCOMMITTED:
                times[number] = None
        elif line.startswith("author-time ") and number is not None and sha != UNCOMMITTED:
            times[number] = dt.datetime.fromtimestamp(int(line.split()[1]), dt.timezone.utc)
    return times


def run(root: pathlib.Path) -> tuple[list[str], int, int, int]:
    """Findings, entries checked, tickets read, entries not yet committed."""
    now = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    findings, entries, tickets, pending = [], 0, 0, 0
    for path in sorted((root / TICKETS).rglob("*.erg")):
        stamps = stamped_entries(path)
        if not stamps:
            continue
        tickets += 1
        entries += len(stamps)
        times = written(root, path, stamps[0][0], stamps[-1][0])
        for number, stamp in stamps:
            commit = times.get(number)
            uncommitted = commit is None
            pending += uncommitted
            bound = (now if uncommitted else commit).replace(second=0, microsecond=0)
            if stamp > bound:
                findings.append(
                    f"{path.relative_to(root).as_posix()}:{number}: stamped "
                    f"{stamp:%Y-%m-%dT%H:%MZ}, written {bound:%Y-%m-%dT%H:%MZ}"
                    + (" (uncommitted, so checked against the clock)" if uncommitted else "")
                )
    return findings, entries, tickets, pending


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    root = parser.parse_args().root.resolve()

    if not (root / TICKETS).is_dir():
        log.error("FAIL: no %s/ directory to check under %s", TICKETS, root)
        return 1
    if subprocess.run(["git", "rev-parse", "--git-dir"], cwd=root, capture_output=True).returncode:
        log.error("NOT EVIDENCED: not a git checkout, so no commit time to check a stamp against")
        return 1
    git_dir = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
    if (pathlib.Path(git_dir) / "shallow").exists():
        log.warning(
            "WEAK: this checkout is shallow, so a line older than its boundary blames to the "
            "boundary commit and is checked against a later time than it was written. Run "
            "`git fetch --unshallow` before trusting a green here."
        )

    findings, entries, tickets, pending = run(root)
    for finding in findings:
        log.error("FAIL: %s", finding)
    if findings:
        log.error(
            "%d log entr%s stamped after the commit that wrote it. Correct the stamp to a time "
            "the record evidences — `git log` on the commit that carries the line — never the "
            "other way round.",
            len(findings), "y is" if len(findings) == 1 else "ies are",
        )
        return 1
    log.info(
        "OK: %d log entries across %d tickets, none stamped after the commit that wrote it%s",
        entries, tickets,
        f" ({pending} not yet committed, checked against the clock)" if pending else "",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
