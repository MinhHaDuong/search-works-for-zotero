#!/usr/bin/env python3
"""The authority chain is described in one place, and pointed at from the rest.

CLAUDE.md's rule: "One statement per fact: thresholds, rules, and open questions
live in their owning document and everywhere else is a pointer." The authority
chain -- rulings enter DECISIONS.md, the other documents are edited to match, a
veto is a new entry -- is a rule, so it falls under that sentence. Before ticket
0054 each of the five chain documents restated it in its own words.

Why this guard matches phrases and not whole sentences. The ticket asked for a
check that fires when the same sentence, normalised, appears in more than one
chain document. Measured on the pre-0054 tree, that check found nothing: all
five restatements were paraphrases and shared no sentence verbatim. A guard that
is green on the very tree whose defect it exists to catch is not a guard. So the
shape here is the one bench/check_governance.py already uses -- a small set of
named phrases, each excused by a pointer on the same line.

The phrases below are the ones the five Intros actually used. Each was checked
against the rest of the five documents for false positives before being added;
the many other mentions of DECISIONS.md, of vetoes, and of requirements do not
match them.
"""

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Where the chain is described. A line that points here is excused.
OWNER = "README.md"

#: The specification chain. CLAUDE.md is deliberately absent: it carries its own
#: restatement, it is the agent contract rather than a chain document, and
#: sweeping it in here would fail the build over a file ticket 0054 did not
#: rewrite. Tracked as a follow-up instead of silently widened.
SCANNED = [
    "spec/REQUIREMENTS.md",
    "spec/CONSTRAINTS.md",
    "spec/DESIGN.md",
    "spec/FIELD-REVIEW.md",
    "spec/DECISIONS.md",
]

#: Each entry is a phrase one of the five Intros used to describe the chain.
CHAIN_MARKERS = {
    "rulings recorded in DECISIONS.md": re.compile(
        r"\b(?:ruling|ratification)s?\s+(?:are|is)\s+(?:recorded\s+)?in\s+DECISIONS\.md",
        re.I,
    ),
    "the other documents are edited to match": re.compile(r"\bedited\s+to\s+match\b", re.I),
    "vetoable on a later reading": re.compile(
        r"\bvet(?:o|oed|oable)\b[^.\n]{0,40}\blater\s+reading\b", re.I
    ),
    "authority works like this": re.compile(r"\bauthority\s+works\s+like\s+this\b", re.I),
    "rulings land here first": re.compile(r"\brulings?\s+land\s+here\s+first\b", re.I),
}

#: The pointer must sit on the offending line itself. A reader who arrives at the
#: sentence through a search sees one line, and a pointer they have to hunt for
#: is not a pointer. Same rule, and same reason, as bench/check_governance.py.
POINTER = re.compile(re.escape(OWNER))


def scan(text: str) -> list[tuple[int, str, str]]:
    """Return (line number, marker name, line) for every unexcused restatement."""
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        if POINTER.search(line):
            continue
        for name, pattern in CHAIN_MARKERS.items():
            if pattern.search(line):
                hits.append((number, name, line.strip()))
    return hits


def run(repo: Path) -> int:
    if not (repo / OWNER).exists():
        print(f"{OWNER} is missing: the chain has no home to point at", file=sys.stderr)
        return 1

    failures = 0
    scanned = 0
    for relative in SCANNED:
        path = repo / relative
        if not path.exists():
            # Never a silent pass. A document that could not be read is a
            # document that was not checked, and the two must not look alike.
            print(f"{relative} is missing: cannot check it", file=sys.stderr)
            failures += 1
            continue
        scanned += 1
        for number, name, line in scan(path.read_text(encoding="utf-8")):
            print(
                f"{relative}:{number}: restates the authority chain "
                f"({name}) without pointing at {OWNER}\n    {line}",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(
            f"\n{failures} restatement(s) of the authority chain. "
            f"It is described in {OWNER}; everywhere else points there.",
            file=sys.stderr,
        )
        return 1

    print(
        f"{scanned} documents scanned, {len(CHAIN_MARKERS)} markers tracked: "
        f"the chain has one home"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(REPO), help="repository root to check")
    args = parser.parse_args()
    return run(Path(args.repo))


if __name__ == "__main__":
    raise SystemExit(main())
