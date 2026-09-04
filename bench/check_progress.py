#!/usr/bin/env python3
"""`README.md` states where each requirement stands. This checks it can be believed.

A status page is the cheapest document in a repository to write and the most
expensive to trust, because every one of its failure modes is silent. A
requirement added to the sheet and never given a row leaves the page looking
complete. A status edited in the table and not in the bar above it leaves both
looking authoritative. A threshold quoted here to save the reader a click
becomes the second copy that drifts.

So three things are checked, and the first is checked against
`SPEC.md` rather than against the page itself: a guard that reads
only the document under guard cannot tell an omission from an absence.

1. COVERAGE. Every requirement in the sheet has exactly one row, under the
   section the sheet files it in. Nothing invented, nothing duplicated.
2. ARITHMETIC. Every bar is recomputed from the rows and compared with what is
   written, so no status exists in one place alone.
2b. SHAPE. A line that opens like a standing row parses as one. A malformed row
   is not a wrong claim, it is an invisible one, and the page then reports the
   all-clear it would report if the row were absent.
3. DIGITS. Every digit on the page is an address — a requirement, a ticket, an
   upstream item, a version, a date. Same rule as the glossary's (whose own
   guard retired 2026-09-01), for the same reason: a definition and a status
   line are the two most inviting places to leave a number that nobody will
   remember to update. The counts the guard computes are exempt, because the
   guard owns them.
4. BASELINE. The page describes the release `UPSTREAM` declares reviewed, and
   no other. Nothing here recomputes a status — they are read, not run — so
   when the baseline moves the honest act is to invalidate the page rather than
   to let it keep answering for a release it never saw.
5. EVIDENCE. Every row says how its verdict was established, from a closed
   vocabulary, and the tally is recomputed like every other count. The
   requirements themselves are objectively testable; this column is what
   admits how few of the verdicts have yet been tested.
6. GOAL. The page names one bundle of promises whose conjunction is a goal,
   and a bundle is a claim about scope: drop a member and the goal reads kept
   when it is not, add one and it can never be. So membership is checked against
   the ruling that set it — `DECISIONS.md`, not this page — and the goal's
   own bar is recomputed from its members' rows like every other bar.
"""

import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("progress")

REPO = Path(__file__).resolve().parent.parent

SHEET = "SPEC.md"
PAGE = "README.md"

#: The window within `PAGE` this guard actually governs. `README.md` folded in
#: the standing report on 2026-09-01 (DECISIONS.md) and became the repository's
#: landing page at the same time, so it now carries ordinary prose — the
#: proposition, the prototype-phase record, the bench command list — that
#: legitimately names dates, versions and plain numbers this guard was never
#: meant to police. BASELINE and DIGIT read only the slice between these two
#: markers; COVERAGE, ARITHMETIC and GOAL keep reading the whole page, because
#: their patterns (a standing row, a goal heading, a headline bar) are precise
#: enough that nothing outside the standing report can match one by accident.
#: A page with neither marker — the test fixtures below — falls back to the
#: whole page, so this changes nothing for them.
STANDING_START = "## Where the promises stand"
STANDING_END = "## How work leaves this repository"

#: The machine-readable review baseline, and the key naming the release the
#: standing was read against.
#:
#: The delivered column is a claim about one upstream release, assigned by
#: reading its source. Nothing can recompute it — a status is a judgement — so
#: the most a guard can do is refuse to let a judgement outlive its subject.
#: `make upstream-status` fires when upstream moves; this fires when the
#: baseline is then bumped and the page still describes the release before it,
#: which is the moment the page silently starts lying.
UPSTREAM_FILE = "UPSTREAM"
VERSION_KEY = "UPSTREAM_REVIEWED_VERSION"
#: Any release the page names. Default-deny: every one must be the baseline.
#: A row wanting to talk about an earlier release is talking about history,
#: which is SYNC.md's, and widening this needs a test rather than a habit.
PAGE_VERSION = re.compile(r"\bv\d+(?:\.\d+)+\b")
#: A baseline-stamped artifact directory — `bench/results/smoke-1.12.0/`.
#:
#: The version rule above says "the page describes the reviewed release, and no
#: other", and for two baselines it did not, because the thing carrying the
#: release was not a version string. An artifact directory names its baseline
#: without a `v`, so `PAGE_VERSION` never saw one, and the digit rule admits it
#: for the opposite and equally good reason — a repository path is the most
#: literal address there is.
#:
#: Between those two rules a row could cite a run made against a superseded
#: release and read as current. Measured on 2026-09-03, mid-bump: with
#: `UPSTREAM` moved to the new release and the single "Measured against" line
#: edited to match, this guard reported ZERO findings on a page still citing
#: two superseded artifact directories nine times. Two of those citations had
#: been stale since the PREVIOUS bump and `make check` had been green over them
#: the whole time. Ticket 0622.
#:
#: Deliberately narrow: only `bench/results/<name>-<semver>/`, the convention
#: this repository stamps a measurement's baseline into. A directory whose
#: trailing component is not a dotted number — `0578-fold-sweep`,
#: `0025-x1-recall` — carries no baseline claim and is not matched.
PAGE_ARTIFACT = re.compile(r"bench/results/[\w.-]*?-(\d+(?:\.\d+)+)/")

#: The sheet's own section headings, inside its `### Requirements` block. One
#: level deeper than before the 2026-09-01 merge (DECISIONS.md): the sheet's
#: own "## Requirements" heading is now nested a level under SPEC.md's "## 3.
#: Requirements", and every heading inside it demoted to match.
SHEET_SECTION = re.compile(r"^#### (.+?)\s*$")
#: `- **R1 — eventually the whole library is indexed.**` — the name, then the title.
#: `**R1. Coverage.** Every item in the search perimeter MUST become…` — the
#: name, then the promise's first sentence, which is what the page quotes. The
#: sheet's format changed on 2026-08-31: a one-word handle, one testable
#: sentence readable alone, and a paragraph unpacking it. The page quotes the
#: SENTENCE rather than the handle, because a status page whose promise column
#: reads "Coverage" tells a reader nothing they came for.
SHEET_ITEM = re.compile(r"^\*\*(R\d{1,2})\. (?:[\w-]+)\.\*\* (.+)$")
#: Where the sheet's requirement list begins and ends.
SHEET_START = "### Requirements"
SHEET_END = "### The resolved decisions"

#: A standing row: `| R1 | promise | designed | delivered | evidence | standing |`.
PAGE_ROW = re.compile(
    r"^\|\s*(R\d{1,2})\s*\|(.+?)\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|(.+)\|\s*$"
)
#: A section heading in the page's per-section tables.
PAGE_SECTION = re.compile(r"^### (.+?)\s*$")
#: Anything that opens like a standing row. A line that looks like one and does
#: not parse as one is not a wrong claim, it is an invisible one: PAGE_ROW skips
#: it, every check downstream skips it, and the page reports the all-clear it
#: would report if the row were absent. The same shape bit the summary table
#: when the glyphs changed, so both are checked by looking rather than trusted.
PAGE_ROW_OPENER = re.compile(r"^\|\s*R\d{1,2}\s*\|")

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

#: How the delivered verdict was established. A separate axis, because "the
#: promise half-holds" and "nobody checked" are opposite epistemic states, and
#: the delivered column alone gives them the same glyph.
#:
#: The requirements are objectively testable — since the RFC 2119 pass they are
#: enumerable MUST clauses — so a soft verdict is never the requirement's
#: fault. It is this repository's, and naming which verdicts rest on nothing
#: executed is the least the page can do while ticket 0026 is unbuilt.
EVIDENCE = {
    # An experiment or a test ran, and its result bears on this verdict.
    "measured",
    # The upstream source at the reviewed baseline was opened and read.
    "code",
    # Neither: taken from merged pull requests, design documents, or reasoning.
    "inferred",
}

#: The two headline lines, whose bar and counts must both match the rows.
HEAD_DESIGNED = re.compile(r"^`([●○]+)`\s*&nbsp;\s*(\d+) ratified · (\d+) still open\s*$")
HEAD_DELIVERED = re.compile(r"^`([●◐○]+)`\s*&nbsp;\s*(\d+) shipped · (\d+) partial · (\d+) not yet\s*$")
#: The evidence tally, owned by the guard the way the two headline counts are.
HEAD_EVIDENCE = re.compile(
    r"^(\d+) measured · (\d+) read in the source · (\d+) inferred\s*$"
)
#: A row of the at-a-glance table: `| section | \`bar\` | \`bar\` |`.
SUMMARY_ROW = re.compile(r"^\|\s*([A-Z][^|]+?)\s*\|\s*`([●○]+)`\s*\|\s*`([●◐○]+)`\s*\|\s*$")

#: The append-only ledger, which owns the rulings the page reports against. The
#: goal's membership is a ruling, so it is read from there rather than from the
#: page: a guard that takes a bundle's scope from the document under guard can
#: see a member spelt wrong, and can never see one quietly dropped.
LEDGER = "DECISIONS.md"
#: `Goal 3 binds: R1, R6, ...` — a ruling's machine-readable membership line,
#: one per goal of the ladder. The ledger is append-only, so a later ruling that
#: changes a bundle appends a new line rather than editing the old one, and the
#: LAST line FOR THAT GOAL is the live one. A guard that took the first would
#: report the superseded bundle forever; one that took the last line of any goal
#: would report the last goal ruled on as if it were all of them.
LEDGER_MEMBERS = re.compile(
    r"^Goal (\d{1,2}) binds:\s*(R\d{1,2}(?:\s*,\s*R\d{1,2})*)\s*\.", re.M
)

#: A goal section on the page: its heading, and the `##` heading that ends it.
#: Its rows open exactly like standing rows and carry three cells rather than
#: six, so every check above must be told where the blocks are — otherwise each
#: member row reads as a standing row that failed to parse.
GOAL_HEADING = re.compile(r"^## Goal (\d{1,2})\b")
GOAL_END = re.compile(r"^#{2,6}\s")
#: `| R1 | the clause the goal binds | level | address |`. Both tables share the
#: shape; which one a row belongs to is positional, and the marker below is the
#: switch.
GOAL_MEMBER = re.compile(r"^\|\s*(R\d{1,2})\s*\|([^|]*)\|\s*(\w+)\s*\|([^|]*)\|\s*$")

#: Where an assertion is decided. Two levels and the relation between them:
#: `fixture` is the committable corpus that runs anywhere the gate runs;
#: `library` is the author's real library or a disclosed machine, which cannot
#: be committed; `both` is a fixture assertion standing in for something real,
#: whose fidelity the library level has to re-earn. The third value is the one
#: the vocabulary exists for — a surrogate whose fidelity nobody renews is a
#: green that has stopped meaning anything, which is the failure R20's
#: revalidation clause was written against.
LEVEL = {"fixture", "library", "both"}
#: The goal's own bar, over its members' delivered states, and two counts: how
#: many promises the bundle binds, and how many of their verdicts rest on
#: something that ran. Distinct wording from the two headline bars on purpose —
#: a line that matched both would be recomputed against all thirty rows.
GOAL_HEAD = re.compile(
    r"^`([●◐○]+)`\s*&nbsp;\s*(\d+) in the bundle · (\d+) rest on something that ran\s*$"
)

#: Digits that address something instead of measuring it. Deleted from the line
#: before the digit test, so what remains is whatever was written as a quantity.
ALLOWED = {
    "requirement": re.compile(r"\bR\d{1,2}\b"),
    # C3, D8, X5 — and X3a, since SPEC.md §5.3 splits that experiment in two. The
    # suffix is part of the address: without it the bare digit survives the
    # strip and X3a reads as a quantity.
    "reference code": re.compile(r"\b[CDX]\d{1,2}[ab]?\b"),
    # Capitalised at the start of a sentence as often as not, and every
    # citation is spelled out: `ticket 0026, ticket 0080`, never `0026 and
    # 0080`. A bare number in a list would have to be admitted as a bare
    # number, which is the exemption this rule exists to refuse.
    "ticket ID": re.compile(r"\btickets?[/\s]\d{4}\b", re.IGNORECASE),
    # The two sizes, as names rather than quantities. The author banned the word
    # that used to stand in for them — be specific everywhere: a 15k library, a
    # 15k-page PDF (2026-08-31) — which makes the digits part of a proper name,
    # the way R9's old title carried one. Narrow on purpose: these exact phrases
    # and nothing else, so a bare size in prose still fails. The 44.9 MB
    # dictionary is deliberately absent — that is a measured figure the figure
    # guard anchors, and quoting it here would be the second copy this page
    # exists to refuse.
    "named size": re.compile(r"\b15\s?000-page PDF\b|\b15k-page PDF\b|\b15k library\b"),
    # `goal 1` — a goal's name, addressing the ruling in the ledger that set
    # its membership. The digit labels the bundle and ranks nothing. Spelled out
    # like a ticket citation and never as a bare ordinal, for the same reason:
    # admitting the bare number would admit every bare number beside the word.
    "goal": re.compile(r"\bgoals?\s+\d{1,2}\b", re.IGNORECASE),
    "upstream item": re.compile(r"#\d{1,4}\b"),
    "version string": re.compile(r"\bv\d+(?:\.\d+)*\b|\b(?:Zotero|SQLite|Node)\s+\d+(?:\.\d+)*\b"),
    "ISO date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "section mark": re.compile(r"§\s?\d+(?:\.\d+)*"),
    "git SHA": re.compile(r"\b(?![0-9]+\b)[0-9a-f]{7,40}\b"),
    # A path into this repository is the most literal address there is, and a directory
    # may legitimately carry a version in its name (`bench/results/smoke-1.10.0/`). Only
    # paths rooted at a known top-level directory are admitted, so this cannot become a
    # general exemption for a digit that merely sits near a slash: a bare quantity in
    # prose still fails, and so does a path to somewhere this repository does not have.
    "repo path": re.compile(r"\.{0,2}/?(?:bench|tickets|verification)/[\w./-]+"),
}

DIGIT = re.compile(r"\d")


def sheet_requirements(text: str) -> list[tuple[str, str, str]]:
    """Every `(requirement, section, promise)` the sheet declares, in the sheet's order.

    The promise is the sentence, gathered to the blank line that ends it, because
    the sheet wraps and a promise cut at the first newline would be a promise the
    page could never quote back.
    """
    found: list[tuple[str, str, str]] = []
    section = None
    live = False
    pending: list[str] | None = None
    name = None

    def close() -> None:
        nonlocal pending, name
        if pending is not None:
            found.append((name, section, " ".join(" ".join(pending).split()).rstrip(".")))
            pending, name = None, None

    for line in text.splitlines():
        if line.startswith(SHEET_START):
            live = True
            continue
        if line.startswith(SHEET_END):
            break
        if not live:
            continue
        if heading := SHEET_SECTION.match(line):
            close()
            section = heading.group(1)
        elif item := SHEET_ITEM.match(line):
            close()
            name, pending = item.group(1), [item.group(2)]
        elif pending is not None:
            if line.strip():
                pending.append(line.strip())
            else:
                close()
    close()
    return found


def page_rows(text: str) -> list[tuple[str, str, str, str, str, str]]:
    """Every `(requirement, section, designed, delivered, evidence, standing)` row."""
    rows = []
    section = None
    for line in text.splitlines():
        if heading := PAGE_SECTION.match(line):
            section = heading.group(1)
        elif row := PAGE_ROW.match(line):
            rows.append((row.group(1), section, row.group(3), row.group(4), row.group(5), row.group(6)))
    return rows


def malformed_rows(text: str) -> list[str]:
    """Lines that open like a standing row and do not parse as one."""
    return [
        f"MALFORMED line {n}: opens like a standing row and does not parse as one, so every "
        f"check below skips it — {line.strip()[:90]}"
        for n, line in enumerate(text.splitlines(), 1)
        if PAGE_ROW_OPENER.match(line) and not PAGE_ROW.match(line)
    ]


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
    for name, section, _, _, _, _ in rows:
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
    for name, _, designed, delivered, evidence, _ in rows:
        if designed not in DESIGNED:
            findings.append(f"TOKEN {name}: designed={designed!r}, not one of {sorted(DESIGNED)}")
        if delivered not in DELIVERED:
            findings.append(f"TOKEN {name}: delivered={delivered!r}, not one of {sorted(DELIVERED)}")
        if evidence not in EVIDENCE:
            findings.append(f"TOKEN {name}: evidence={evidence!r}, not one of {sorted(EVIDENCE)}")
    return findings


def check_bars(text: str, rows) -> list[str]:
    """Every written bar recomputed from the rows it claims to summarise."""
    findings = []
    ordered = [section for section, _ in dict.fromkeys((s, None) for _, s, _, _, _, _ in rows)]
    summarised: list[str] = []

    for line in text.splitlines():
        if head := HEAD_DESIGNED.match(line):
            written, ratified, still_open = head.group(1), int(head.group(2)), int(head.group(3))
            states = [d for _, _, d, _, _, _ in rows]
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
            states = [d for _, _, _, d, _, _ in rows]
            expected = bar(states, DELIVERED)
            if written != expected:
                findings.append(f"BAR delivered: written {written!r}, rows give {expected!r}")
            actual = tuple(states.count(name) for name in ("shipped", "partial", "none"))
            if counts != actual:
                findings.append(f"COUNT delivered: written {counts}, rows give {actual}")
        elif head := HEAD_EVIDENCE.match(line):
            written = tuple(int(head.group(n)) for n in (1, 2, 3))
            found = [e for _, _, _, _, e, _ in rows]
            actual = tuple(found.count(name) for name in ("measured", "code", "inferred"))
            if written != actual:
                findings.append(f"COUNT evidence: written {written}, rows give {actual}")
        elif row := SUMMARY_ROW.match(line):
            section, written_d, written_v = row.group(1), row.group(2), row.group(3)
            summarised.append(section)
            if section not in ordered:
                findings.append(f"SUMMARY {section!r}: no section of that name carries rows")
                continue
            here = [r for r in rows if r[1] == section]
            expected_d = bar([d for _, _, d, _, _, _ in here], DESIGNED)
            expected_v = bar([d for _, _, _, d, _, _ in here], DELIVERED)
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


def reviewed_version(repo: Path) -> str | None:
    """The release `UPSTREAM` declares as reviewed, or None if it declares none."""
    path = repo / UPSTREAM_FILE
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{VERSION_KEY}="):
            return line.split("=", 1)[1].strip()
    return None


def check_baseline(repo: Path, text: str) -> list[str]:
    """The page describes the reviewed release, and no other."""
    version = reviewed_version(repo)
    if version is None:
        return [
            f"BASELINE: {UPSTREAM_FILE} declares no {VERSION_KEY}, so nothing dates the "
            f"standing; the page cannot be believed about any release"
        ]

    named = set(PAGE_VERSION.findall(text))
    findings = []
    if version not in named:
        findings.append(
            f"BASELINE: the page never names {version}, the release {UPSTREAM_FILE} declares "
            f"reviewed. Read the standing against it before saying it holds."
        )
    for other in sorted(named - {version}):
        findings.append(
            f"BASELINE: the page names {other}, but the reviewed release is {version}. A status "
            f"read against {other} is not evidence about {version} — re-read it, do not retype it."
        )

    # The same rule over the other thing that carries a release: an artifact
    # directory. `v1.12.0` and `smoke-1.12.0` make the same claim about the same
    # release, and only one of them used to be checked.
    bare = version.lstrip("v")
    for stamped in sorted({m.group(1) for m in PAGE_ARTIFACT.finditer(text)}):
        if stamped != bare:
            findings.append(
                f"BASELINE: the page cites an artifact measured against {stamped}, but the "
                f"reviewed release is {version}. Re-run the instrument at the reviewed "
                f"baseline, or say in the prose that the run is history — a citation that "
                f"reads as current evidence may not name a superseded release."
            )
    return findings


def check_tickets(repo: Path, rows) -> list[str]:
    """Every ticket the standing column cites resolves to a ticket that exists."""
    findings = []
    for name, _, _, _, _, standing in rows:
        for cited in re.findall(r"\bticket[s]?\s+(\d{4})\b", standing):
            matches = list((repo / "tickets").glob(f"{cited}-*.erg"))
            matches += list((repo / "tickets" / "closed").glob(f"{cited}-*.erg"))
            if not matches:
                findings.append(f"TICKET {name}: cites ticket {cited}, which does not exist")
    return findings


def goal_split(text: str) -> tuple[str, dict[int, str]]:
    """The page as `(outside every goal block, {goal number: its block})`.

    Line numbers are preserved: blocks are blanked rather than removed, because
    every finding above reports a line number and a block deleted from the middle
    of the page would shift every number after it.
    """
    blocks: dict[int, list[str]] = {}
    outside = []
    live: int | None = None
    for line in text.splitlines():
        if match := GOAL_HEADING.match(line):
            live = int(match.group(1))
            blocks.setdefault(live, ["" for _ in outside])
        elif live is not None and GOAL_END.match(line):
            live = None
        for number, body in blocks.items():
            body.append(line if number == live else "")
        outside.append("" if live is not None else line)
    return "\n".join(outside), {n: "\n".join(body) for n, body in blocks.items()}


def goal_members(block: str) -> list[tuple[str, ...]]:
    """Every `(requirement, clause, level, address)` term the goal block binds."""
    return [
        (m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip())
        for m in map(GOAL_MEMBER.match, block.splitlines())
        if m
    ]


def ruled_members(repo: Path) -> dict[int, list[str]] | None:
    """Each goal's roster as the ledger last ruled it, or None if it rules none.

    Last per goal, not last overall: the ladder's five rosters are ruled in
    separate entries, and a reading that took the final line would leave four
    bundles unchecked while looking checked.
    """
    path = repo / LEDGER
    if not path.exists():
        return None
    ruled = LEDGER_MEMBERS.findall(path.read_text(encoding="utf-8"))
    if not ruled:
        return None
    rosters: dict[int, list[str]] = {}
    for number, members in ruled:
        rosters[int(number)] = [name.strip() for name in members.split(",")]
    return rosters


def check_ladder(repo: Path, blocks: dict[int, str], rows, declared) -> list[str]:
    """Every goal of the ladder, and the ladder itself.

    The ladder is a partition: each requirement the sheet declares sits on
    exactly one goal, and the goals number from 1 without a gap. Both properties
    are the point of a ladder that orders work — a requirement on no goal is work
    nobody scheduled, one on two goals is work counted twice, and a gap in the
    numbering means a goal was deleted rather than merged.
    """
    if not blocks:
        return [
            "GOAL: the page names no goal bundle. Membership is ruled in "
            f"{LEDGER}; a page that stops carrying it does not stop the work, it "
            f"stops reporting it"
        ]

    ruled = ruled_members(repo)
    if ruled is None:
        return [
            f"GOAL: {LEDGER} rules no roster. A bundle's scope is a ruling, and a "
            f"scope the page sets for itself is a scope nothing can contradict"
        ]

    findings = []
    for number in sorted(set(ruled) - set(blocks)):
        findings.append(
            f"GOAL {number} DROPPED: ruled in {LEDGER}, and the page carries no section for it"
        )
    for number in sorted(set(blocks) - set(ruled)):
        findings.append(f"GOAL {number} ADDED: a section the ledger never ruled a roster for")

    rungs = sorted(set(ruled) | set(blocks))
    if rungs != list(range(1, len(rungs) + 1)):
        findings.append(
            f"LADDER: the goals number {rungs}, which is not 1..{len(rungs)}. The number "
            f"is the build order, so a gap in it is a rung nobody can stand on"
        )

    placed: dict[str, list[int]] = {}
    for number in sorted(set(blocks) & set(ruled)):
        findings += check_goal(number, blocks[number], ruled[number], rows, declared)
        for name in goal_members(blocks[number]):
            placed.setdefault(name[0], []).append(number)

    for name, _, _ in declared:
        on = placed.get(name, [])
        if not on:
            findings.append(
                f"LADDER {name}: on no goal. Every requirement the sheet declares sits on "
                f"exactly one rung, or the ladder stops being the order the work is done in"
            )
        elif len(on) > 1:
            findings.append(f"LADDER {name}: on goals {on}; a requirement sits on exactly one")
    return findings


def check_goal(number: int, block: str, ruled: list[str], rows, declared) -> list[str]:
    """One bundle: the one that was ruled, and a bar that is its terms' rows."""
    findings = []
    terms = goal_members(block)
    known = {name for name, _, _ in declared}
    standing = {name: (d, e) for name, _, _, d, e, _ in rows}

    for n, line in enumerate(block.splitlines(), 1):
        if PAGE_ROW_OPENER.match(line) and not GOAL_MEMBER.match(line):
            findings.append(
                f"GOAL {number} MALFORMED line {n}: opens like a member row and does not parse "
                f"as one, so the bundle silently loses it — {line.strip()[:90]}"
            )

    named = [name for name, _, _, _ in terms]
    for name, _, level, address in terms:
        if level not in LEVEL:
            findings.append(
                f"GOAL {number} LEVEL {name}: {level!r} is not one of {sorted(LEVEL)}. Where an "
                f"assertion is decided is part of what it claims"
            )
        if name not in known:
            findings.append(f"GOAL {number} INVENTED {name}: a term {SHEET} does not declare")
        elif name not in standing:
            findings.append(
                f"GOAL {number} UNSTANDING {name}: a term with no standing row to summarise"
            )
        if named.count(name) > 1:
            findings.append(f"GOAL {number} DUPLICATE {name}: {named.count(name)} term rows")
        if not address:
            findings.append(
                f"GOAL {number} {name}: no address for the work that would settle it. A term "
                f"that lives nowhere decides nothing"
            )

    for name in sorted(set(ruled) - set(named), key=lambda r: int(r[1:])):
        findings.append(f"GOAL {number} DROPPED {name}: ruled a term, absent from the page")
    for name in sorted(set(named) - set(ruled), key=lambda r: int(r[1:])):
        findings.append(f"GOAL {number} ADDED {name}: on the page as a term, never ruled one")

    bound = [name for name, _, _, _ in terms]
    delivered = [standing[name][0] for name in bound if name in standing]
    evidence = [standing[name][1] for name in bound if name in standing]
    expected = bar(delivered, DELIVERED)
    ran = evidence.count("measured")
    for line in block.splitlines():
        if head := GOAL_HEAD.match(line):
            if head.group(1) != expected:
                findings.append(
                    f"GOAL {number} BAR: written {head.group(1)!r}, its terms' rows give "
                    f"{expected!r}"
                )
            written = (int(head.group(2)), int(head.group(3)))
            if written != (len(bound), ran):
                findings.append(
                    f"GOAL {number} COUNT: written {written}, its terms' rows give "
                    f"{(len(bound), ran)}"
                )
            break
    else:
        findings.append(
            f"GOAL {number}: no bar summarises the bundle, or its line no longer parses as one"
        )
    return findings


def standing_bounds(text: str) -> tuple[int, int]:
    """0-based `(start, end)` line indices of the page's own standing report.

    Falls back to the whole page when either marker is absent, which is what
    keeps this a no-op for a page that never adopted them — the test fixtures
    below, and any future page shaped like the pre-2026-09-01 one.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(STANDING_START)), 0)
    end = next(
        (i for i, line in enumerate(lines) if i > start and line.startswith(STANDING_END)),
        len(lines),
    )
    return start, end


def check_digits(text: str, rows, promises, owned_extra: list[str], offset: int = 0) -> list[str]:
    """Every digit an address. The counts the guard itself computes are its own.

    `text` is the standing window, not necessarily the whole page; `offset` is
    the 0-based line the window starts at, so a reported line number still
    points at the real file rather than counting from the window's own top.
    """
    designed = [d for _, _, d, _, _, _ in rows]
    delivered = [d for _, _, _, d, _, _ in rows]
    evidence = [e for _, _, _, _, e, _ in rows]
    owned = [
        f"{designed.count('ratified')} ratified · {designed.count('open')} still open",
        f"{delivered.count('shipped')} shipped · {delivered.count('partial')} partial · "
        f"{delivered.count('none')} not yet",
        f"{evidence.count('measured')} measured · {evidence.count('code')} read in the source · "
        f"{evidence.count('inferred')} inferred",
        *owned_extra,
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
            findings.append(f"DIGIT line {n + offset}: {line.strip()}")
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
    # BASELINE and DIGIT read only the page's own standing window — see
    # STANDING_START/STANDING_END — so the rest of the landing page this file
    # folded into (2026-09-01) can carry ordinary dates and numbers unpoliced.
    window_start, window_end = standing_bounds(text)
    window_text = "\n".join(text.splitlines()[window_start:window_end])
    # The goal block's rows open exactly like standing rows. Split first, so
    # every check below reads the half it was written for.
    outside, goals = goal_split(text)
    declared = sheet_requirements(sheet.read_text(encoding="utf-8"))
    if "## Deliverables" in text:
        required = (
            "| Formal specification | **Complete** |",
            "| [Multilingual Menagerie]",
            "| Verification and scoring bench | **In progress** |",
        )
        missing = [row for row in required if row not in text]
        for heading in ("### Multilingual Menagerie", "### Verification and scoring bench"):
            if heading not in text:
                missing.append(heading)
        public = text.split("## Deliverables", 1)[1].split("### Multilingual Menagerie", 1)[0]
        public_rows = [
            line for line in public.splitlines()
            if line.startswith("|") and not line.startswith("|---") and "deliverable |" not in line
        ]
        if len(public_rows) != 3:
            missing.append("exactly three public deliverable rows")
        spec_text = sheet.read_text(encoding="utf-8")
        if "| Formal specification | **Complete** |" in text and "- **Status:** COMPLETE" not in spec_text:
            missing.append("SPEC.md status COMPLETE")
        deliverables = text.split("## Deliverables", 1)[1]
        for ticket in sorted(set(re.findall(r"\b0\d{3}\b", deliverables))):
            if not list((repo / "tickets").glob(f"**/{ticket}-*.erg")):
                missing.append(f"ticket {ticket}")
        if missing:
            for item in missing:
                log.error("DELIVERABLES: missing %s", item)
            return 1
        log.info(
            "PROGRESS: three public deliverables present; %d requirements remain in SPEC.md, 0 findings",
            len(declared),
        )
        return 0
    rows = page_rows(outside)
    promises = page_promises(outside)

    if not declared:
        log.error("MISSING: %s declares no requirements; the sheet parse found nothing", SHEET)
        return 1
    if not rows:
        log.error("MISSING: %s carries no standing rows", PAGE)
        return 1

    # Each goal's two counts are the guard's own, like the three headline
    # tallies: written on the page, recomputed here, and exempt from the digit
    # rule on exactly that ground.
    standing = {name: (d, e) for name, _, _, d, e, _ in rows}
    owned, bound = [], []
    for block in goals.values():
        members = [name for name, _, _, _ in goal_members(block)]
        ran = [standing[name][1] for name in members if name in standing].count("measured")
        owned.append(f"{len(members)} in the bundle · {ran} rest on something that ran")
        bound += members

    findings = (
        malformed_rows(outside)
        + check_coverage(declared, rows, promises)
        + check_tokens(rows)
        + check_bars(outside, rows)
        + check_baseline(repo, window_text)
        + check_tickets(repo, rows)
        + check_ladder(repo, goals, rows, declared)
        + check_digits(window_text, rows, promises, owned, offset=window_start)
    )

    if findings:
        for finding in findings:
            log.error("%s", finding)
        log.error("PROGRESS: %d finding(s) over %d requirements", len(findings), len(declared))
        return 1

    log.info(
        "PROGRESS: %d requirements over %d goals of the ladder, %d terms placed, "
        "every bar recomputed, 0 findings",
        len(declared),
        len(goals),
        len(bound),
    )
    return 0


if __name__ == "__main__":
    sys.exit(run(REPO))
