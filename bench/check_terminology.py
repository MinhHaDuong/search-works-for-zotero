#!/usr/bin/env python3
"""The glossary defines; it never decides. Nothing in it restates a design number.

`spec/TERMINOLOGY.md` is the one document in the chain that quotes no
measurement and owns no threshold: it says what a word means and points at the
document that owns the number. That property is easy to state and easy to lose.
A glossary is exactly where a helpful hand adds "refreshes every 60 s" for the
reader's convenience — and from that moment the repository has two copies of a
design number, one of which nobody will ever remember to update. That is this
repo's most expensive recurring defect, and the reason for the one-statement-
per-fact rule.

So the rule here is **default-deny**: a digit anywhere in the glossary fails,
unless it falls in a narrow allowlist of things that are addresses rather than
quantities — a git SHA, an ISO date, a requirement/constraint/decision/
experiment code, a `§` section mark, a version string, a ticket ID.

**Two deliberate inversions of `check_governance.py`**, its sibling guard.

First, that guard is default-allow: it hunts named bound-phrases, because it
scans thousands of lines of legitimate design prose where digits are the normal
furniture. Here the file is small and hand-authored, every digit in it was typed
on purpose, and enumerating the forbidden numbers is impossible — the whole
point is that we do not know in advance which threshold someone will copy in.
Default-deny is the only rule that catches the number nobody anticipated.

Second, and more easily "fixed" by mistake: **a pointer on the line does NOT
excuse the number.** `test_pointer_on_the_line_excuses_it` is correct for the
governance guard, where citing the owner beside a bound is the wanted form.
It is wrong here. The invariant is that the glossary owns no thresholds, and
`"refreshes every 60 s (DESIGN.md §2.4)"` restates one; the citation says where
the original lives, it does not stop the copy from going stale. Copying the
governance semantics across would leave a guard that runs, passes, and enforces
nothing.

**The term slot is exempt, and only the term slot.** Half this vocabulary is
named with a digit — `FTS5`, `unicode61`, `bm25`, `seg/1`, `band 0`, `P0` — and
those are names, not quantities. So the leading `**...**` of an entry is
removed before the line is scanned. Emphasis anywhere else in the definition is
scanned normally: otherwise the exemption is a laundry, and bolding a number
would clear it.

**What it does not do**, stated the way `check_figures.py` states its own
limitation: it cannot see a threshold restated in words. "refreshes roughly
every minute" carries no digit and passes here. No regex closes that — a check
that guessed at prose numbers would produce noise until someone turned it off —
and the cover for it is `verify-adherence` and human review. What this guard
buys is that the mechanical, copy-paste form of the defect, which is the form
it actually takes, cannot land.

Exit 0 when clean, 1 when the glossary states a number of its own.

Usage:
    python3 bench/check_terminology.py
    python3 bench/check_terminology.py --repo /path/to/checkout
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("terminology")

REPO = Path(__file__).resolve().parent.parent

#: The document under guard.
GLOSSARY = "spec/TERMINOLOGY.md"

#: An entry: a list item whose first element is a bolded term. The bolded span
#: is the term slot, exempt from the digit rule because a name is not a number.
ENTRY = re.compile(r"^\s*[-*]\s+\*\*.+?\*\*")

#: Digits that are addresses, not quantities. Each span is deleted from the line
#: before the digit test, so what remains is whatever the author wrote as a
#: number. Every class is admitted by its own test: an exemption nothing
#: exercises is an exemption nobody notices widening.
ALLOWED = {
    # A commit, the coordinate of anything that now lives only in git history.
    # Pure digits are excluded so a bare seven-figure count is not read as a SHA.
    "git SHA": re.compile(r"\b(?![0-9]+\b)[0-9a-f]{7,40}\b"),
    # A ratification date, in the only format this repo writes.
    "ISO date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    # R1, C3, D8, X5 — the chain's own reference codes. These are the
    # glossary's main way of pointing at an owner without quoting it.
    "reference code": re.compile(r"\b[RCDX]\d{1,2}\b"),
    # A section address. The mark is what distinguishes §2.4 from the quantity
    # 2.4, which is why a bare "see 2.4" is still a finding.
    "section mark": re.compile(r"§\s?\d+(?:\.\d+)*"),
    # Software versions, ours and the platform's.
    "version string": re.compile(r"\bv\d+(?:\.\d+)*\b|\b(?:Zotero|SQLite|Node)\s+\d+(?:\.\d+)*\b"),
    # A ticket, cited as `ticket 0028` or by path.
    "ticket ID": re.compile(r"\btickets?[/\s]\d{4}\b"),
    # `goal 1` — a milestone's name, addressing the ruling that set its
    # membership. Spelled out, never a bare ordinal, on the ticket rule's logic.
    "goal": re.compile(r"\bgoals?\s+\d{1,2}\b", re.IGNORECASE),
}

DIGIT = re.compile(r"\d")


def strip_allowed(line: str) -> str:
    """The line with every address-shaped digit span removed."""
    for pattern in ALLOWED.values():
        line = pattern.sub(" ", line)
    return line


def scan(text: str) -> tuple[int, list[tuple[int, str]]]:
    """Entry count, and every line stating a number the glossary does not own."""
    entries = 0
    findings = []
    for n, line in enumerate(text.splitlines(), 1):
        match = ENTRY.match(line)
        if match:
            entries += 1
            # Only the term slot, and only where it leads the entry.
            line = line[match.end() :]
        if DIGIT.search(strip_allowed(line)):
            findings.append((n, line.strip()))
    return entries, findings


def run(repo: Path) -> int:
    """The glossary under `repo`, checked. Returns a process exit code."""
    path = repo / GLOSSARY

    if not path.exists():
        # A guard whose all-clear is reachable by failing to look is not a
        # guard. Absent, the file must be loud, never "0 entries, 0 findings".
        log.error("MISSING: %s does not exist; the glossary is registered but not present", GLOSSARY)
        return 1

    entries, findings = scan(path.read_text(encoding="utf-8"))

    if not entries:
        # Same defect as deletion, arrived at by truncation instead.
        log.error("EMPTY: %s carries no entries; a glossary with nothing in it guards nothing", GLOSSARY)
        return 1

    for n, line in findings:
        log.error("%s:%d states a number the glossary does not own\n    %s", GLOSSARY, n, line)

    if findings:
        log.error(
            "\n%d number(s) in %s. The glossary defines; the owning document "
            "holds the figure. Name the owner instead of quoting it.",
            len(findings),
            GLOSSARY,
        )
        return 1

    log.info("%d entries scanned, %d exemptions tracked: the glossary owns no numbers", entries, len(ALLOWED))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=str(REPO), help="repository root to scan")
    a = ap.parse_args()
    return run(Path(a.repo))


if __name__ == "__main__":
    sys.exit(main())
