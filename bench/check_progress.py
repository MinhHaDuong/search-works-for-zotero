#!/usr/bin/env python3
"""`spec/README.md` states where each requirement stands. This checks it can be believed.

A status page is the cheapest document in a repository to write and the most
expensive to trust, because every one of its failure modes is silent. A
requirement added to the sheet and never given a row leaves the page looking
complete. A status edited in the table and not in the bar above it leaves both
looking authoritative. A threshold quoted here to save the reader a click
becomes the second copy that drifts.

So three things are checked, and the first is checked against
`spec/REQUIREMENTS.md` rather than against the page itself: a guard that reads
only the document under guard cannot tell an omission from an absence.

1. COVERAGE. Every requirement in the sheet has exactly one row, under the
   section the sheet files it in. Nothing invented, nothing duplicated.
2. ARITHMETIC. Every bar is recomputed from the rows and compared with what is
   written, so no status exists in one place alone.
3. DIGITS. Every digit on the page is an address — a requirement, a ticket, an
   upstream item, a version, a date. Same rule as `check_terminology.py`, for
   the same reason: a definition and a status line are the two most inviting
   places to leave a number that nobody will remember to update. The counts the
   guard computes are exempt, because the guard owns them.
"""

import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("progress")

REPO = Path(__file__).resolve().parent.parent

SHEET = "spec/REQUIREMENTS.md"
PAGE = "spec/README.md"

#: The sheet's own section headings, inside its `## Requirements` block.
SHEET_SECTION = re.compile(r"^### (.+?)\s*$")
#: `- **R1 — eventually the whole library is indexed.**` — the name, then the title.
SHEET_ITEM = re.compile(r"^- \*\*(R\d{1,2}) — (.+?)\.?\*\*")
#: Where the sheet's requirement list begins and ends.
SHEET_START = "## Requirements"
SHEET_END = "## The resolved decisions"

#: A standing row: `| R1 | promise | designed | delivered | standing |`.
PAGE_ROW = re.compile(r"^\|\s*(R\d{1,2})\s*\|(.+?)\|\s*(\w+)\s*\|\s*(\w+)\s*\|(.+)\|\s*$")
#: A section heading in the page's per-section tables.
PAGE_SECTION = re.compile(r"^### (.+?)\s*$")

#: The glyphs, and the vocabulary each axis admits. `designed` has two states
#: and `delivered` three, which is the asymmetry the page exists to show: a
#: promise is designed or it is not, but it can be half-kept.
#:
#: Filled, half and empty circles rather than block shades. The first version
#: used █ and ▓, whose fills differ by a quarter, and the author could not tell
#: them apart in the rendered page — which costs the reader the one distinction
#: the delivered bar exists to draw. A half-filled circle carries "partial" in
#: its shape, so the bar survives being read without its legend.
DESIGNED = {"ratified": "●", "open": "○"}
DELIVERED = {"shipped": "●", "partial": "◐", "none": "○"}

#: The two headline lines, whose bar and counts must both match the rows.
HEAD_DESIGNED = re.compile(r"^`([●○]+)`\s*&nbsp;\s*(\d+) ratified · (\d+) still open\s*$")
HEAD_DELIVERED = re.compile(r"^`([●◐○]+)`\s*&nbsp;\s*(\d+) shipped · (\d+) partial · (\d+) not yet\s*$")
#: A row of the at-a-glance table: `| section | \`bar\` | \`bar\` |`.
SUMMARY_ROW = re.compile(r"^\|\s*([A-Z][^|]+?)\s*\|\s*`([●○]+)`\s*\|\s*`([●◐○]+)`\s*\|\s*$")

#: Digits that address something instead of measuring it. Deleted from the line
#: before the digit test, so what remains is whatever was written as a quantity.
ALLOWED = {
    "requirement": re.compile(r"\bR\d{1,2}\b"),
    # C3, D8, X5 — and X3a, since DESIGN §3 splits that experiment in two. The
    # suffix is part of the address: without it the bare digit survives the
    # strip and X3a reads as a quantity.
    "reference code": re.compile(r"\b[CDX]\d{1,2}[ab]?\b"),
    # Capitalised at the start of a sentence as often as not, and every
    # citation is spelled out: `ticket 0026, ticket 0080`, never `0026 and
    # 0080`. A bare number in a list would have to be admitted as a bare
    # number, which is the exemption this rule exists to refuse.
    "ticket ID": re.compile(r"\btickets?[/\s]\d{4}\b", re.IGNORECASE),
    "upstream item": re.compile(r"#\d{1,4}\b"),
    "version string": re.compile(r"\bv\d+(?:\.\d+)*\b|\b(?:Zotero|SQLite|Node)\s+\d+(?:\.\d+)*\b"),
    "ISO date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "section mark": re.compile(r"§\s?\d+(?:\.\d+)*"),
    "git SHA": re.compile(r"\b(?![0-9]+\b)[0-9a-f]{7,40}\b"),
}

DIGIT = re.compile(r"\d")


def sheet_requirements(text: str) -> list[tuple[str, str, str]]:
    """Every `(requirement, section, title)` the sheet declares, in the sheet's order."""
    found: list[tuple[str, str, str]] = []
    section = None
    live = False
    for line in text.splitlines():
        if line.startswith(SHEET_START):
            live = True
            continue
        if line.startswith(SHEET_END):
            break
        if not live:
            continue
        if heading := SHEET_SECTION.match(line):
            section = heading.group(1)
        elif item := SHEET_ITEM.match(line):
            found.append((item.group(1), section, item.group(2).strip()))
    return found


def page_rows(text: str) -> list[tuple[str, str, str, str, str]]:
    """Every `(requirement, section, designed, delivered, standing)` row on the page."""
    rows = []
    section = None
    for line in text.splitlines():
        if heading := PAGE_SECTION.match(line):
            section = heading.group(1)
        elif row := PAGE_ROW.match(line):
            rows.append((row.group(1), section, row.group(3), row.group(4), row.group(5)))
    return rows


def page_promises(text: str) -> dict[str, str]:
    """The promise cell of each row, which must quote the sheet's own title."""
    return {row.group(1): row.group(2).strip() for row in map(PAGE_ROW.match, text.splitlines()) if row}


def bar(states: list[str], vocabulary: dict[str, str]) -> str:
    """The states rendered in the vocabulary's own order, best first."""
    return "".join(glyph * states.count(name) for name, glyph in vocabulary.items())


def check_coverage(sheet, rows, promises) -> list[str]:
    """Requirements present exactly once, under the section and title the sheet gives them."""
    findings = []
    declared = {name: (section, title) for name, section, title in sheet}
    seen: dict[str, int] = {}
    for name, section, _, _, _ in rows:
        seen[name] = seen.get(name, 0) + 1
        if name not in declared:
            findings.append(f"INVENTED {name}: a row for a requirement {SHEET} does not declare")
            continue
        filed, title = declared[name]
        if filed != section:
            findings.append(
                f"MISFILED {name}: {SHEET} files it under {filed!r}, the page under {section!r}"
            )
        # The promise cell is a quotation, and the digit rule exempts it on that
        # ground alone (R9's title carries a page count). The exemption is only
        # safe while the quotation is exact, so it is checked here rather than
        # trusted: a promise cell free to drift would be a digit nobody guards.
        if promises.get(name, "").strip() != title:
            findings.append(
                f"PROMISE {name}: the sheet says {title!r}, the page says {promises.get(name, '')!r}"
            )
    for name, section, _ in sheet:
        count = seen.get(name, 0)
        if count == 0:
            findings.append(f"MISSING {name} ({section}): declared in {SHEET}, no row on the page")
        elif count > 1:
            findings.append(f"DUPLICATE {name}: {count} rows")
    return findings


def check_tokens(rows) -> list[str]:
    """Each axis spelled with a word its vocabulary admits."""
    findings = []
    for name, _, designed, delivered, _ in rows:
        if designed not in DESIGNED:
            findings.append(f"TOKEN {name}: designed={designed!r}, not one of {sorted(DESIGNED)}")
        if delivered not in DELIVERED:
            findings.append(f"TOKEN {name}: delivered={delivered!r}, not one of {sorted(DELIVERED)}")
    return findings


def check_bars(text: str, rows) -> list[str]:
    """Every written bar recomputed from the rows it claims to summarise."""
    findings = []
    ordered = [section for section, _ in dict.fromkeys((s, None) for _, s, _, _, _ in rows)]
    summarised: list[str] = []

    for line in text.splitlines():
        if head := HEAD_DESIGNED.match(line):
            written, ratified, still_open = head.group(1), int(head.group(2)), int(head.group(3))
            states = [d for _, _, d, _, _ in rows]
            expected = bar(states, DESIGNED)
            if written != expected:
                findings.append(f"BAR designed: written {written!r}, rows give {expected!r}")
            if (ratified, still_open) != (states.count("ratified"), states.count("open")):
                findings.append(
                    f"COUNT designed: written {ratified} ratified / {still_open} open, rows give "
                    f"{states.count('ratified')} / {states.count('open')}"
                )
        elif head := HEAD_DELIVERED.match(line):
            written = head.group(1)
            counts = tuple(int(head.group(n)) for n in (2, 3, 4))
            states = [d for _, _, _, d, _ in rows]
            expected = bar(states, DELIVERED)
            if written != expected:
                findings.append(f"BAR delivered: written {written!r}, rows give {expected!r}")
            actual = tuple(states.count(name) for name in ("shipped", "partial", "none"))
            if counts != actual:
                findings.append(f"COUNT delivered: written {counts}, rows give {actual}")
        elif row := SUMMARY_ROW.match(line):
            section, written_d, written_v = row.group(1), row.group(2), row.group(3)
            summarised.append(section)
            if section not in ordered:
                findings.append(f"SUMMARY {section!r}: no section of that name carries rows")
                continue
            here = [r for r in rows if r[1] == section]
            expected_d = bar([d for _, _, d, _, _ in here], DESIGNED)
            expected_v = bar([d for _, _, _, d, _ in here], DELIVERED)
            if written_d != expected_d:
                findings.append(
                    f"SUMMARY {section!r} designed: written {written_d!r}, rows give {expected_d!r}"
                )
            if written_v != expected_v:
                findings.append(
                    f"SUMMARY {section!r} delivered: written {written_v!r}, rows give {expected_v!r}"
                )

    # A summary row is checked only if it parses, so a row whose glyphs fall
    # outside the vocabulary — a stale bar left behind when the glyphs changed,
    # a hand-edit — is not wrong, it is invisible, and the guard reports the
    # all-clear it would report for a page with no such row at all. Every
    # section must therefore be accounted for by name.
    for section in ordered:
        if section not in summarised:
            findings.append(
                f"SUMMARY {section!r}: no row summarises it, or its row no longer parses as bars"
            )
    return findings


def check_tickets(repo: Path, rows) -> list[str]:
    """Every ticket the standing column cites resolves to a ticket that exists."""
    findings = []
    for name, _, _, _, standing in rows:
        for cited in re.findall(r"\bticket[s]?\s+(\d{4})\b", standing):
            matches = list((repo / "tickets").glob(f"{cited}-*.erg"))
            matches += list((repo / "tickets" / "closed").glob(f"{cited}-*.erg"))
            if not matches:
                findings.append(f"TICKET {name}: cites ticket {cited}, which does not exist")
    return findings


def check_digits(text: str, rows, promises) -> list[str]:
    """Every digit an address. The counts the guard itself computes are its own."""
    designed = [d for _, _, d, _, _ in rows]
    delivered = [d for _, _, _, d, _ in rows]
    owned = [
        f"{designed.count('ratified')} ratified · {designed.count('open')} still open",
        f"{delivered.count('shipped')} shipped · {delivered.count('partial')} partial · "
        f"{delivered.count('none')} not yet",
    ]
    # Verified quotations of the sheet, per check_coverage. Longest first, so a
    # title that is the prefix of another cannot leave its tail behind.
    quoted = sorted(promises.values(), key=len, reverse=True)

    findings = []
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line
        for phrase in owned + quoted:
            stripped = stripped.replace(phrase, " ")
        for pattern in ALLOWED.values():
            stripped = pattern.sub(" ", stripped)
        if DIGIT.search(stripped):
            findings.append(f"DIGIT line {n}: {line.strip()}")
    return findings


def run(repo: Path) -> int:
    """The status page under `repo`, checked. Returns a process exit code."""
    page, sheet = repo / PAGE, repo / SHEET

    # A guard whose all-clear is reachable by failing to look is not a guard.
    # Either document absent must be loud, never "0 rows, 0 findings".
    for path, rel in ((page, PAGE), (sheet, SHEET)):
        if not path.exists():
            log.error("MISSING: %s does not exist", rel)
            return 1

    text = page.read_text(encoding="utf-8")
    declared = sheet_requirements(sheet.read_text(encoding="utf-8"))
    rows = page_rows(text)
    promises = page_promises(text)

    if not declared:
        log.error("MISSING: %s declares no requirements; the sheet parse found nothing", SHEET)
        return 1
    if not rows:
        log.error("MISSING: %s carries no standing rows", PAGE)
        return 1

    findings = (
        check_coverage(declared, rows, promises)
        + check_tokens(rows)
        + check_bars(text, rows)
        + check_tickets(repo, rows)
        + check_digits(text, rows, promises)
    )

    if findings:
        for finding in findings:
            log.error("%s", finding)
        log.error("PROGRESS: %d finding(s) over %d requirements", len(findings), len(declared))
        return 1

    log.info("PROGRESS: %d requirements, every bar recomputed, 0 findings", len(declared))
    return 0


if __name__ == "__main__":
    sys.exit(run(REPO))
