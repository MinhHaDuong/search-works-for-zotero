"""The progress guard, exercised against fixture repositories.

Same shape as `test_check_governance.py` and `test_check_terminology.py`: each
test builds a small repository under tmp_path and runs the real `run()` against
it. The defects worth catching live in the wiring — a sheet that is never
opened, a page whose rows stopped parsing — and a test that only ever feeds a
string to a scanner cannot see either.

Every test here that asserts a failure is a positive control. This guard's
whole purpose is to fail on a page that looks fine, so a suite that only ever
fed it clean fixtures would report an all-clear indistinguishable from not
having looked.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("cp", REPO / "bench" / "check_progress.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cp = load()

SHEET = """# REQUIREMENTS

## Requirements

### Coverage

- **R1 — eventually the whole library is indexed.** With no further edits.
- **R2 — most recent first.** Coverage grows newest-first.

### Corpus

- **R9 — 15 000-page documents are included.** Monsters are first-class.

## The resolved decisions

| D1 | counted in items. |
"""

PAGE = """# The specification chain

Measured against upstream v1.10.0, the reviewed baseline.

`●●○` &nbsp; 2 ratified · 1 still open

`●◐○` &nbsp; 1 shipped · 1 partial · 1 not yet

1 measured · 1 read in the source · 1 inferred

| section | designed | delivered |
|---|---|---|
| Coverage | `●○` | `●◐` |
| Corpus | `●` | `○` |

## Goal 1 — the bundle

`●○` &nbsp; 2 in the bundle · 1 rest on something that ran

| | the clause goal 1 binds | decided at | where its test would live |
|---|---|---|---|
| R1 | the whole library, unattended | fixture | ticket 0080 |
| R9 | a monster indexed whole | both | ticket 0024 |

**Instruments.** What decides the terms.

| | what it decides | run at | where it is built |
|---|---|---|---|
| R2 | the crawl order is watched, deciding R1 | fixture | ticket 0080 |

### Coverage

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R1 | eventually the whole library is indexed | ratified | shipped | code | Landed upstream. |
| R2 | most recent first | open | partial | inferred | Under revision in ticket 0080. |

### Corpus

| | promise | designed | delivered | evidence | standing |
|---|---|---|---|---|---|
| R9 | 15 000-page documents are included | ratified | none | measured | Ticket 0024 carries the filing. |
"""


UPSTREAM = "UPSTREAM_REVIEWED_SHA=b132f2d\nUPSTREAM_REVIEWED_VERSION=v1.10.0\n"

#: The ledger, which owns the goal's membership. The page is checked against
#: this rather than against itself: a bundle whose scope is set by the document
#: reporting on it is a scope nothing can contradict.
LEDGER = """# DECISIONS

**2026-08-31 — the bundle.**

Goal 1 binds: R1, R9.

Goal 1 instruments: R2.
"""


def build(
    root: Path,
    page: str | None = PAGE,
    sheet: str | None = SHEET,
    upstream: str | None = UPSTREAM,
    ledger: str | None = LEDGER,
) -> Path:
    """A fixture repository, with either document optionally absent."""
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "tickets" / "closed").mkdir(parents=True, exist_ok=True)
    # The two tickets the fixture page cites, so the ticket check has something
    # to resolve. One closed, one open: closing a ticket moves its file, and a
    # citation must survive the move.
    (root / "tickets" / "0080-rewrite-r26.erg").write_text("%erg 0.1\n", encoding="utf-8")
    (root / "tickets" / "closed" / "0024-file-the-issues.erg").write_text("%erg 0.1\n", encoding="utf-8")
    if upstream is not None:
        (root / "UPSTREAM").write_text(upstream, encoding="utf-8")
    if page is not None:
        (root / "spec" / "README.md").write_text(page, encoding="utf-8")
    if sheet is not None:
        (root / "spec" / "REQUIREMENTS.md").write_text(sheet, encoding="utf-8")
    if ledger is not None:
        (root / "spec" / "DECISIONS.md").write_text(ledger, encoding="utf-8")
    return root


def test_clean_fixture_passes(tmp_path):
    assert cp.run(build(tmp_path)) == 0


def test_missing_page_is_loud(tmp_path):
    """Absent, the page must fail — never "0 rows, 0 findings"."""
    assert cp.run(build(tmp_path, page=None)) == 1


def test_missing_sheet_is_loud(tmp_path):
    """The sheet is what coverage is measured against; without it there is no measurement."""
    assert cp.run(build(tmp_path, sheet=None)) == 1


def test_requirement_added_to_the_sheet_and_not_the_page(tmp_path):
    """The failure this guard exists for: a promise with no standing, and nothing looks wrong."""
    sheet = SHEET.replace(
        "### Corpus",
        "### Corpus\n\n- **R16 — my own words.** Notes and annotations are part of the corpus.",
    )
    assert cp.run(build(tmp_path, sheet=sheet)) == 1


def test_requirement_the_sheet_does_not_declare(tmp_path):
    page = PAGE.replace(
        "| R9 | 15 000-page documents are included | ratified | none | measured | Ticket 0024 carries the filing. |",
        "| R9 | 15 000-page documents are included | ratified | none | measured | Ticket 0024 carries the filing. |\n"
        "| R7 | multilingual by default | ratified | none | code | Invented. |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_row_filed_under_the_wrong_section(tmp_path):
    """Sections are the sheet's, not the page's; a row that migrates is a finding."""
    page = PAGE.replace(
        "| R9 | 15 000-page documents are included | ratified | none | measured | Ticket 0024 carries the filing. |\n",
        "",
    ).replace(
        "| R2 | most recent first | open | partial | inferred | Under revision in ticket 0080. |",
        "| R2 | most recent first | open | partial | inferred | Under revision in ticket 0080. |\n"
        "| R9 | 15 000-page documents are included | ratified | none | measured | Ticket 0024 carries the filing. |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_promise_cell_that_stopped_quoting_the_sheet(tmp_path):
    """The digit rule exempts the promise cell, so the quotation has to be exact.

    Without this check the exemption would be a hole: any number could be
    parked in the promise column and the digit scan would step over it.
    """
    page = PAGE.replace(
        "| R9 | 15 000-page documents are included |",
        "| R9 | 20 000-page documents are included |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_status_edited_in_the_table_but_not_the_bar(tmp_path):
    """A status must never exist in one place alone."""
    page = PAGE.replace(
        "| R1 | eventually the whole library is indexed | ratified | shipped |",
        "| R1 | eventually the whole library is indexed | ratified | partial |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_section_bar_that_stopped_matching_its_rows(tmp_path):
    page = PAGE.replace("| Coverage | `●○` | `●◐` |", "| Coverage | `●○` | `●●` |")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_section_bar_left_in_glyphs_the_vocabulary_dropped(tmp_path):
    """A bar that stops parsing is invisible, not wrong, unless every section is named.

    The page was first drawn in block shades and moved to circles when the
    author could not tell shipped from partial. A row left behind in the old
    glyphs matches no pattern, so without the completeness check the guard
    passes it in silence — the all-clear it would give a page with no summary
    table at all.
    """
    page = PAGE.replace("| Coverage | `●○` | `●◐` |", "| Coverage | `█░` | `█▓` |")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_section_with_no_summary_row(tmp_path):
    page = PAGE.replace("| Corpus | `●` | `○` |\n", "")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_headline_count_that_stopped_matching_its_bar(tmp_path):
    page = PAGE.replace("2 ratified · 1 still open", "3 ratified · 0 still open")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_status_word_outside_the_vocabulary(tmp_path):
    page = PAGE.replace("| ratified | shipped | code |", "| ratified | done | code |")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_measurement_quoted_in_a_standing_cell(tmp_path):
    """The second copy of a number is what this repository's guards exist to refuse."""
    page = PAGE.replace("Landed upstream.", "Landed upstream, at a warm p95 of 392,3 ms.")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_ticket_cited_that_does_not_exist(tmp_path):
    page = PAGE.replace("ticket 0080", "ticket 9999")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_addresses_are_not_measurements(tmp_path):
    """The exemptions, each exercised: an exemption nothing tests is one nobody notices widening."""
    page = PAGE.replace(
        "Landed upstream.",
        "Landed upstream as issue #33 at v1.10.0, ratified 2026-08-29, DESIGN §2.8, "
        "experiment X3a, commit b132f2d, ticket 0080, bound into goal 1.",
    )
    assert cp.run(build(tmp_path, page=page)) == 0


def test_the_real_page_passes_its_own_guard(tmp_path):
    """The shipped documents, not a fixture — the wiring the fixtures cannot see."""
    assert cp.run(REPO) == 0


def test_the_baseline_moved_and_the_page_did_not(tmp_path):
    """The question this check answers: nothing recomputes a status when upstream ships.

    `make upstream-status` fires when upstream moves. This fires at the next
    moment — the baseline is bumped to the new release and the page still
    describes the one before it, every bar still arithmetically perfect. That
    is when a status page starts lying while looking correct.
    """
    upstream = UPSTREAM.replace("v1.10.0", "v1.11.0")
    assert cp.run(build(tmp_path, upstream=upstream)) == 1


def test_a_row_read_against_some_other_release(tmp_path):
    """A status read against one release is not evidence about another."""
    page = PAGE.replace("Landed upstream.", "Landed upstream in v1.7.1.")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_upstream_absent_is_loud(tmp_path):
    """Nothing dates the standing, so the page cannot be believed about any release."""
    assert cp.run(build(tmp_path, upstream=None)) == 1


def test_upstream_declaring_no_version_is_loud(tmp_path):
    assert cp.run(build(tmp_path, upstream="UPSTREAM_REVIEWED_SHA=b132f2d\n")) == 1


def test_evidence_word_outside_the_vocabulary(tmp_path):
    """`evidence` is a closed vocabulary: measured, code, inferred."""
    page = PAGE.replace("| ratified | shipped | code |", "| ratified | shipped | probably |")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_evidence_tally_that_stopped_matching_its_rows(tmp_path):
    """The tally is the guard's, recomputed like every other count on the page."""
    page = PAGE.replace(
        "1 measured · 1 read in the source · 1 inferred",
        "2 measured · 1 read in the source · 0 inferred",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_verdict_may_be_downgraded_to_inferred(tmp_path):
    """Evidence is independent of status: re-grading how we know it is not a status change."""
    page = PAGE.replace(
        "| ratified | shipped | code |", "| ratified | shipped | inferred |"
    ).replace(
        "1 measured · 1 read in the source · 1 inferred",
        "1 measured · 0 read in the source · 2 inferred",
    )
    assert cp.run(build(tmp_path, page=page)) == 0


def test_a_standing_row_that_no_longer_parses(tmp_path):
    """A row missing a column is invisible, not wrong — the same hole as a stale bar."""
    page = PAGE.replace(
        "| R2 | most recent first | open | partial | inferred |",
        "| R2 | most recent first | open | partial |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


# The goal block. A bundle is a claim about scope, and every one of its failure
# modes is silent in the same way the page's own are: a member dropped leaves a
# conjunction over fewer terms than were ruled, a member added leaves one that
# can never be true, and a bar left behind after a row moved leaves both looking
# authoritative.
# Every test below asserts a failure, so each is a positive control.


def test_a_ruled_member_dropped_from_the_page(tmp_path):
    """The bundle's own silent failure: a conjunction reported over fewer terms."""
    page = PAGE.replace("| R9 | a monster indexed whole | both | ticket 0024 |\n", "").replace(
        "`●○` &nbsp; 2 in the bundle · 1 rest on something that ran",
        "`●` &nbsp; 1 in the bundle · 0 rest on something that ran",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_member_the_ledger_never_ruled(tmp_path):
    """The other direction: scope widened on the page, with no ruling behind it."""
    page = PAGE.replace(
        "| R9 | a monster indexed whole | both | ticket 0024 |",
        "| R9 | a monster indexed whole | both | ticket 0024 |\n"
        "| R2 | newest first | fixture | ticket 0080 |",
    ).replace(
        "`●○` &nbsp; 2 in the bundle · 1 rest on something that ran",
        "`●◐○` &nbsp; 3 in the bundle · 1 rest on something that ran",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_the_ledger_rules_no_membership(tmp_path):
    """A page free to set its own scope is a page nothing can contradict."""
    assert cp.run(build(tmp_path, ledger="# DECISIONS\n\nNothing ruled.\n")) == 1


def test_the_later_ruling_supersedes_the_earlier(tmp_path):
    """The ledger is append-only: a bundle changes by a new line, and the last one is live."""
    ledger = LEDGER + "\n**Later.**\n\nGoal 1 binds: R1, R2, R9.\n"
    page = PAGE.replace(
        "| R9 | a monster indexed whole | both | ticket 0024 |",
        "| R9 | a monster indexed whole | both | ticket 0024 |\n"
        "| R2 | newest first | fixture | ticket 0080 |",
    ).replace(
        "`●○` &nbsp; 2 in the bundle · 1 rest on something that ran",
        "`●◐○` &nbsp; 3 in the bundle · 1 rest on something that ran",
    )
    assert cp.run(build(tmp_path, page=page, ledger=ledger)) == 0


def test_the_goal_bar_stopped_matching_its_members(tmp_path):
    """Same failure as every other bar, recomputed the same way — from the members' rows."""
    page = PAGE.replace(
        "| R9 | 15 000-page documents are included | ratified | none | measured |",
        "| R9 | 15 000-page documents are included | ratified | partial | measured |",
    ).replace("| Corpus | `●` | `○` |", "| Corpus | `●` | `◐` |").replace(
        "`●◐○` &nbsp; 1 shipped · 1 partial · 1 not yet",
        "`●◐◐` &nbsp; 1 shipped · 2 partial · 0 not yet",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_member_row_that_stopped_parsing(tmp_path):
    """A malformed member is not a wrong claim, it is an invisible one."""
    page = PAGE.replace(
        "| R9 | a monster indexed whole | both | ticket 0024 |",
        "| R9 | a monster indexed whole | both | extra | ticket 0024 |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_member_with_no_address_for_its_test(tmp_path):
    """A member whose assertion lives nowhere is a promise, not a milestone."""
    page = PAGE.replace(
        "| R9 | a monster indexed whole | both | ticket 0024 |",
        "| R9 | a monster indexed whole | both |  |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_the_goal_section_deleted_outright(tmp_path):
    """Dropping the section does not stop the work; it stops the page reporting it."""
    page = PAGE[: PAGE.index("## Goal 1")] + PAGE[PAGE.index("### Coverage") :]
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_member_row_is_not_read_as_a_standing_row(tmp_path):
    """The two tables share an opener. If the split failed, R1 would read as duplicated."""
    outside, block = cp.goal_split(PAGE)
    terms, instruments = cp.goal_members(block)
    assert [name for name, _, _, _ in terms] == ["R1", "R9"]
    assert [name for name, _, _, _ in instruments] == ["R2"]
    assert sorted(name for name, *_ in cp.page_rows(outside)) == ["R1", "R2", "R9"]
    assert cp.goal_members(outside) == ([], [])


# The instruments half of the same block. An instrument is not a term, and the
# guard has to hold both apart: counted into the bar it would move a conjunction
# it is not part of, and lost from the page it would leave a term nothing decides.


def test_a_ruled_instrument_dropped_from_the_page(tmp_path):
    """A term whose instrument is gone cannot be settled, and nothing else says so."""
    page = PAGE.replace("| R2 | the crawl order is watched, deciding R1 | fixture | ticket 0080 |\n", "")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_an_instrument_the_ledger_never_ruled(tmp_path):
    """Scope widened on the page, in the half that is easiest to widen unnoticed."""
    page = PAGE.replace(
        "| R2 | the crawl order is watched, deciding R1 | fixture | ticket 0080 |",
        "| R2 | the crawl order is watched, deciding R1 | fixture | ticket 0080 |\n"
        "| R9 | re-read as an instrument | fixture | ticket 0024 |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_the_ledger_rules_no_instruments(tmp_path):
    """Both rosters are rulings; one of them missing is not a page that half-passes."""
    assert cp.run(build(tmp_path, ledger=LEDGER.replace("\nGoal 1 instruments: R2.\n", "\n"))) == 1


def test_the_instruments_marker_lost(tmp_path):
    """Without the switch every instrument reads as a term, and the bar moves with it."""
    page = PAGE.replace("**Instruments.** What decides the terms.", "What decides the terms.")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_level_outside_the_vocabulary(tmp_path):
    """Where an assertion can be decided is part of what it claims, so it is a closed set."""
    page = PAGE.replace(
        "| R9 | a monster indexed whole | both | ticket 0024 |",
        "| R9 | a monster indexed whole | someday | ticket 0024 |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_a_row_that_lost_its_level(tmp_path):
    """A four-cell row shedding a cell parses as nothing, which is the invisible failure."""
    page = PAGE.replace(
        "| R9 | a monster indexed whole | both | ticket 0024 |",
        "| R9 | a monster indexed whole | ticket 0024 |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1
