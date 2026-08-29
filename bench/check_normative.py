#!/usr/bin/env python3
"""Contract lines say so in upper case; narrative keeps its lowercase modals.

Ticket 0050 adopted RFC 2119 across the requirements. The convention only pays
if it holds: an R-item written next year with a lowercase "must" reads exactly
like the twenty-eight that carry force, and nothing would say otherwise.

Two checks, because they fail in opposite directions and neither covers the
other.

The BLACKLIST catches a stray lowercase modal inside a contract line — the
regression where someone edits an R-item and reaches for ordinary English.

The WHITELIST catches an R-item with no modal verb at all. That is the failure
the blacklist structurally cannot see, and it is the likelier one: a new R29
written as a clean declarative sentence passes a lowercase-modal grep in
silence, with its force still undeclared. DESIGN §2.9 is the standing proof —
before this ticket it contained zero modal verbs of any kind, so a blacklist
alone would have reported the budgets section clean while every budget in it
was unforced.

Scope is deliberately narrow. CONSTRAINTS.md is out: it states facts about the
world, and its Intro's "the design must operate under" is description, not
duty — a guard here would fire on the document's own framing sentence.
DECISIONS.md is out as the append-only ledger. Narrative prose everywhere is
out, which is the whole point of the case convention.
"""

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

REQUIREMENTS = "spec/REQUIREMENTS.md"

#: The uppercase vocabulary. NOT-forms are matched by their first word.
KEYWORD = re.compile(r"\b(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b")

#: The lowercase modals that carry no force but read as though they might.
LOWERCASE_MODAL = re.compile(r"\b(must|shall|should|may)\b")

#: An R-item opens a bullet and names itself.
R_ITEM = re.compile(r"^- \*\*(R\d+) — ")

#: R-items exempt from the whitelist, each with the reason and its owner. An
#: exemption is written down rather than skipped silently: a guard with a hidden
#: hole is worse than one with a documented one, because only the second gets
#: removed. R26 was rejected as written on 2026-08-29 (DECISIONS.md); recording
#: rejected text as contract would be worse than leaving it unmarked.
UNFORCED = {"R26": "rejected 2026-08-29; ticket 0080 owns the rewrite"}


def r_items(text: str) -> list[tuple[str, int, str]]:
    """Every R-item as (name, first line number, full bullet text).

    Only the Requirements section is read. The rulings above it and the
    resolved-decisions table below carry lowercase modals legitimately.
    """
    lines = text.splitlines()
    try:
        start = lines.index("## Requirements")
    except ValueError:
        return []

    items: list[tuple[str, int, list[str]]] = []
    for offset, line in enumerate(lines[start:], start=start + 1):
        if line.startswith("## ") and not line.startswith("## Requirements"):
            break
        match = R_ITEM.match(line)
        if match:
            items.append((match.group(1), offset, [line]))
        elif items and (line.startswith("  ") or not line.strip()):
            items[-1][2].append(line)
        elif line.startswith("- ") or line.startswith("### "):
            continue
    return [(name, number, "\n".join(body)) for name, number, body in items]


def check(text: str) -> list[str]:
    """Every complaint about the requirements document."""
    problems = []
    items = r_items(text)

    if not items:
        # An empty scan is the failure mode this guard is most likely to hide
        # behind. No R-items found means the section moved or was renamed, not
        # that the document is clean.
        return [f"{REQUIREMENTS}: found no R-items; the Requirements section moved or was renamed"]

    for name, number, body in items:
        reason = UNFORCED.get(name)
        if reason:
            if KEYWORD.search(body):
                problems.append(
                    f"{REQUIREMENTS}:{number}: {name} carries a normative keyword but is "
                    f"listed as unforced ({reason}); remove it from UNFORCED or from the text"
                )
            continue

        if not KEYWORD.search(body):
            problems.append(
                f"{REQUIREMENTS}:{number}: {name} declares no force. Give it an RFC 2119 "
                f"keyword, or list it in UNFORCED with a reason and an owner"
            )
        for hit in LOWERCASE_MODAL.finditer(body):
            problems.append(
                f"{REQUIREMENTS}:{number}: {name} uses lowercase '{hit.group(1)}' in a "
                f"contract line; upper case carries the force, lower case does not"
            )
    return problems


def run(repo: Path) -> int:
    path = repo / REQUIREMENTS
    if not path.exists():
        print(f"{REQUIREMENTS} is missing: cannot check it", file=sys.stderr)
        return 1

    problems = check(path.read_text(encoding="utf-8"))
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"\n{len(problems)} normative-language problem(s).", file=sys.stderr)
        return 1

    counted = len(r_items(path.read_text(encoding="utf-8")))
    print(f"{counted} R-items checked, {len(UNFORCED)} unforced by name: every force is declared")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(REPO), help="repository root to check")
    args = parser.parse_args()
    return run(Path(args.repo))


if __name__ == "__main__":
    raise SystemExit(main())
