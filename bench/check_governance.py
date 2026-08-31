#!/usr/bin/env python3
"""Governance vocabulary stays in its owning document.

This repository is public and the upstream maintainer reads it. CLAUDE.md has
always said that this repo's internal governance and its strategy about him must
never enter text destined upstream — and until GOVERNANCE.md existed, that
separation was enforced by the care of whoever happened to be writing. A rule
kept by care is kept until the first tired afternoon.

The split ratified 2026-08-29 (DECISIONS.md) gives process rules one owner.
This guard is what makes the split hold: it reads the specification documents
and the agent brief, and fails when a named process bound appears there without
a pointer to the document that owns it.

What it deliberately does NOT flag is the word "maintainer". CONSTRAINTS.md says
that he merges small contained PRs and reimplements design-sized proposals, the
asymmetry measured two-for-two — and that is a fact about the terrain, which is
exactly what CONSTRAINTS.md is for. The hazard is not naming him; it is stating
what we have decided to do about him. So the vocabulary below names process
BOUNDS, not the actor. A guard that fired on "maintainer" would be loud, easy to
write, and would push true constraints out of the document that owns them.

Exit 0 when clean, 1 when a bound is stated outside its owner.
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("governance")

REPO = Path(__file__).resolve().parent.parent

#: The document that owns process rules going forward. A line in a scanned
#: document may state a bound if it points here, which is how DESIGN.md §4 keeps
#: naming the train's shape without restating the terms.
OWNER = "GOVERNANCE.md"

#: Scanned: the specification chain, plus the two documents a newcomer or an
#: agent reads first. CLAUDE.md is in scope deliberately — it is where the
#: binding paragraph used to live, so leaving it out would let the guard pass
#: over the very text the split exists to move. TERMINOLOGY.md joined the list
#: with the file itself (ticket 0051): a glossary is where a bound gets restated
#: as a definition, and a specification document that arrives unscanned is
#: indistinguishable from one with nothing to hide. FIELD-REVIEW.md joined the
#: same way, late: it had arrived unscanned and stayed that way, which is the
#: asymmetry ticket 0221 named — a document removed breaks loudly, a document
#: added goes unnoticed. The completeness check below closes it.
SCANNED = [
    "README.md",
    "CLAUDE.md",
    # The chain's front page, and a status page is where the division of labour
    # with upstream is most tempting to explain: every row has to say why a
    # promise is unshipped, and the honest short answer is a governance one.
    "spec/README.md",
    "SECURITY.md",
    "spec/REQUIREMENTS.md",
    "spec/CONSTRAINTS.md",
    "spec/DESIGN.md",
    "verification/FIELD-REVIEW.md",
    "spec/TERMINOLOGY.md",
    # The upstream PR bodies. A new document class, and the one that matters most
    # here: everything below the rule in these files is verbatim text SENT to the
    # maintainer, on a repository he reads. CLAUDE.md's one non-negotiable —
    # never put this repo's governance or its reading of him into upstream text —
    # had until now no mechanical enforcement on the outgoing side at all, only
    # on ours. What this adds is what the guard can actually do, and no more: the
    # six BOUNDS regexes below, which catch a bound RESTATED. A sentence reading
    # the maintainer, or disclosing how the queue is run, passes clean — the
    # judgement stays the writer's and CLAUDE.md still says read what you send,
    # as sent. This closes the loud half, which is the half that has recurred.
    #
    # Scanned WHOLE rather than below the rule: the internal head note says what
    # the document is and where the branch sits, and that is exactly the kind of
    # sentence that must not drift downward into the body. Scanning only below
    # the rule would license writing it above.
    "verification/UPSTREAM-PR-0091-DROPLIST.md",
]

#: Not scanned, and each for its own reason. GOVERNANCE.md owns the bounds.
#: DECISIONS.md is the append-only ledger where the rulings were made — the
#: record is evidence precisely because it is never rewritten. SYNC.md records
#: what happened upstream, including the live tally the bounds are spent
#: against. STATE.md is operational. Tickets carry the work. RUNBOOK.md was
#: operational too, self-sunset 2026-08-30 once its measurements executed
#: (ticket 0160) — removed from this list with the file, not left dangling.
#:
#: This list is documentation, not code: anything absent from SCANNED is already
#: unscanned. It is written down because "why is SYNC.md not checked?" is the
#: question that would otherwise be answered by adding it and breaking the
#: build.
UNSCANNED_BY_DESIGN = ["GOVERNANCE.md", "spec/DECISIONS.md", "SYNC.md", "STATE.md"]

#: Where the two lists above must, between them, account for every document.
#: A hand-written scope fails asymmetrically: a document that LEAVES breaks the
#: build loudly at the missing-document check below, while a document that
#: ARRIVES is simply never read, and nothing says so. FIELD-REVIEW.md arrived
#: that way and sat unscanned — 114 kB of public, newcomer-facing prose outside
#: the gate — until ticket 0052 went looking. The completeness check turns the
#: silent half into the loud half: a new document here fails the build until
#: someone puts it in one list or the other, which takes one line and one
#: moment's thought at the only time anybody has the context to spend it.
#:
#: Most of verification/ is deliberately outside this scope. CLAUDE.md classifies
#: it as evidence rather than authority, a different object class from the
#: documents whose governance vocabulary this guard polices.
#:
#: `verification/UPSTREAM-PR-*.md` is the exception, and it is the sharpest case
#: the completeness check has: those files are not evidence, they are OUTGOING
#: TEXT, and a governance sentence that reaches one of them reaches the
#: maintainer. The glob is here rather than the filename so the SECOND such
#: document cannot arrive unread — which is precisely how FIELD-REVIEW.md spent
#: months outside the gate, and precisely what ticket 0221 named.
#:
#: `-PR-` and not a bare `UPSTREAM-*`, which is what this first said and which
#: was wrong twice over. Technically: a sibling branch was adding
#: `verification/UPSTREAM-1.12.0-REREAD.md` at the same moment, so each PR was
#: green alone and their union was red — nothing here runs CI, so main would
#: have gone red silently. Semantically, and this is the reason the narrower
#: glob is not merely a dodge: the class being gated is *text we send*, not
#: *documents about upstream*. A re-read report is evidence about upstream, the
#: same object class as every other report in this directory, and reads by the
#: rule two paragraphs up. Sending is what earns the gate, and the filename says
#: which is which.
COVERED_GLOBS = ["*.md", "spec/*.md", "verification/UPSTREAM-PR-*.md"]

#: The named process bounds. Each is a rule the author ratified about how this
#: repository conducts itself upstream — not a fact about the world, and not a
#: design number.
BOUNDS = {
    "the in-flight cap": re.compile(r"\b(PRs?\s+in\s+flight|in-flight\s+(?:cap|slot)|two-in-flight)\b", re.I),
    "the contained-PR budget": re.compile(r"\bcontained-PR\s+budget\b", re.I),
    "the sunset rule": re.compile(r"\b(three-week\s+sunset|sunset\s+rule)\b", re.I),
    "the harness as a one-time transfer": re.compile(r"\bone-time\s+transfer\b", re.I),
    "the PR volume cap": re.compile(r"\bvolume\s+cap\b", re.I),
    "the commitment bounds": re.compile(r"\bcommitment\s+bounds\b", re.I),
}

#: A line is excused when it points at the owner. The pointer must be on the
#: line itself, not merely in the paragraph: a reader who lands on the sentence
#: through a search sees one line, and a pointer they have to hunt for is a
#: pointer that does not resolve.
POINTER = re.compile(re.escape(OWNER))


def scan(text: str) -> list[tuple[int, str, str]]:
    """Every line stating a bound without pointing at the owner."""
    findings = []
    for n, line in enumerate(text.splitlines(), 1):
        if POINTER.search(line):
            continue
        for name, pattern in BOUNDS.items():
            if pattern.search(line):
                findings.append((n, name, line.strip()))
    return findings


def uncovered(repo: Path) -> set[str]:
    """Documents under COVERED_GLOBS that appear in neither list."""
    listed = set(SCANNED) | set(UNSCANNED_BY_DESIGN)
    found = set()
    for glob in COVERED_GLOBS:
        for path in repo.glob(glob):
            if path.is_file():
                found.add(path.relative_to(repo).as_posix())
    return found - listed


def run(repo: Path) -> int:
    """Every scanned document under `repo`, checked. Returns a process exit code."""
    failures = 0
    checked = 0

    owner = repo / OWNER
    if not owner.exists():
        log.error("MISSING OWNER: %s does not exist; the split has no home", OWNER)
        failures += 1

    for rel in sorted(uncovered(repo)):
        # Not a warning. An unlisted document is one nobody decided about, and
        # the decision is cheap exactly now, while the file is new.
        log.error(
            "UNTRIAGED DOCUMENT: %s is in neither SCANNED nor UNSCANNED_BY_DESIGN; "
            "add it to one of them in bench/check_governance.py",
            rel,
        )
        failures += 1

    for rel in SCANNED:
        path = repo / rel
        if not path.exists():
            # A scanned document that vanished is not a pass. This guard's
            # all-clear must never be reachable by failing to look.
            log.error("MISSING DOCUMENT: %s is scanned for governance but does not exist", rel)
            failures += 1
            continue
        checked += 1
        for n, name, line in scan(path.read_text(encoding="utf-8")):
            log.error("%s:%d states %s without pointing at %s\n    %s", rel, n, name, OWNER, line)
            failures += 1

    if failures:
        log.error(
            "\n%d governance statement(s) outside %s. Move the rule there, or "
            "cite %s on the line that mentions it.",
            failures,
            OWNER,
            OWNER,
        )
        return 1

    log.info("%d documents scanned, %d bounds tracked: governance has one home", checked, len(BOUNDS))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=str(REPO), help="repository root to scan")
    a = ap.parse_args()
    return run(Path(a.repo))


if __name__ == "__main__":
    sys.exit(main())
