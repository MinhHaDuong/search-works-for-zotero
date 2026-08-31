#!/usr/bin/env python3
"""Banned vocabulary stays out of the chain, and the ban names what to say instead.

A word can be wrong in two ways. It can be inaccurate, which review catches, or
it can be *vague where the document has something specific to say*, which review
does not catch because every sentence containing it reads fine. "Monster" was
the second kind: it stood for a 15 000-page PDF in one paragraph, for the 44.9 MB
dictionary in another, and for any inconveniently large input in a third, so a
reader could not tell whether two sentences were about the same thing. Ruled out
2026-08-31 by the author — be specific everywhere: a 15k library, a 15k-page PDF.

Each ban therefore carries its replacement, not only its prohibition. A guard
that says "do not write this" and stops there gets worked around with a synonym.

Not scanned, and each for its own reason. `spec/DECISIONS.md` is the append-only
ledger: an entry that used the word recorded a ruling made in those terms, and a
record you may rewrite is a document rather than a record. `verification/` and
`STATE.md` are evidence and dated snapshots, the same argument. Tickets carry
append-only log lines, so a ban over them would demand editing what may not be
edited; their bodies are corrected by hand when the ticket is next worked.

Exit 0 when clean, 1 when a banned word appears in a scanned document.
"""

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Each banned word, with what to write instead. The replacement is the point:
#: the ban exists to make a vague word specific, not to shorten the vocabulary.
BANNED = {
    "monster": (
        "name the thing: a 15k-page PDF, the 44.9 MB dictionary, or a 15k library "
        "— whichever the sentence actually means"
    ),
}

SCANNED = [
    "README.md",
    "CLAUDE.md",
    "GOVERNANCE.md",
    "SECURITY.md",
    "spec/README.md",
    "spec/REQUIREMENTS.md",
    "spec/CONSTRAINTS.md",
    "spec/DESIGN.md",
    "spec/TERMINOLOGY.md",
]

#: Documents deliberately outside the ban, listed rather than merely absent, on
#: the same asymmetry every other guard here names: a document that LEAVES the
#: scan breaks loudly, a document that ARRIVES is never read and nothing says so.
#: FIELD-REVIEW.md left the chain for verification/ on 2026-08-31 (main), so it
#: is out of this scan the way every other dated snapshot is: it records what was
#: observed in the words it was observed in.
UNSCANNED_BY_DESIGN = ["spec/DECISIONS.md", "SYNC.md", "STATE.md"]

#: Where the two lists must, between them, account for every document.
COVERED_GLOBS = ["*.md", "spec/*.md"]


def hits(text: str) -> list[tuple[int, str, str]]:
    """Every (line number, word, line) where a banned word appears."""
    found = []
    for word, replacement in BANNED.items():
        pattern = re.compile(rf"\b{word}\w*\b", re.IGNORECASE)
        for n, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                found.append((n, word, line.strip()))
    return found


def scope(repo: Path) -> list[str]:
    """Documents named by neither list, which is the silent half of a hand-kept scope."""
    seen = {path.relative_to(repo).as_posix() for glob in COVERED_GLOBS for path in repo.glob(glob)}
    return sorted(seen - set(SCANNED) - set(UNSCANNED_BY_DESIGN))


def run(repo: Path) -> int:
    problems = []
    for name in SCANNED:
        path = repo / name
        if not path.exists():
            problems.append(f"MISSING: {name} is scanned for banned vocabulary and does not exist")
            continue
        for number, word, line in hits(path.read_text(encoding="utf-8")):
            problems.append(f"{name}:{number}: {word!r} — {BANNED[word]}\n    {line[:100]}")

    for name in scope(repo):
        problems.append(
            f"UNCLASSIFIED: {name} is in neither SCANNED nor UNSCANNED_BY_DESIGN; "
            f"put it in one list or the other"
        )

    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"\n{len(problems)} vocabulary problem(s).", file=sys.stderr)
        return 1

    print(f"{len(SCANNED)} documents scanned, {len(BANNED)} banned word(s): the chain is specific")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=REPO, type=Path)
    sys.exit(run(parser.parse_args().repo))
