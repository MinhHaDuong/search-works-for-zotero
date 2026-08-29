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

`██░` &nbsp; 2 ratified · 1 still open

`█▓░` &nbsp; 1 shipped · 1 partial · 1 not yet

| section | designed | delivered |
|---|---|---|
| Coverage | `█░` | `█▓` |
| Corpus | `█` | `░` |

### Coverage

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R1 | eventually the whole library is indexed | ratified | shipped | Landed upstream. |
| R2 | most recent first | open | partial | Under revision in ticket 0080. |

### Corpus

| | promise | designed | delivered | standing |
|---|---|---|---|---|
| R9 | 15 000-page documents are included | ratified | none | Ticket 0024 carries the filing. |
"""


def build(root: Path, page: str | None = PAGE, sheet: str | None = SHEET) -> Path:
    """A fixture repository, with either document optionally absent."""
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "tickets" / "closed").mkdir(parents=True, exist_ok=True)
    # The two tickets the fixture page cites, so the ticket check has something
    # to resolve. One closed, one open: closing a ticket moves its file, and a
    # citation must survive the move.
    (root / "tickets" / "0080-rewrite-r26.erg").write_text("%erg 0.1\n", encoding="utf-8")
    (root / "tickets" / "closed" / "0024-file-the-issues.erg").write_text("%erg 0.1\n", encoding="utf-8")
    if page is not None:
        (root / "spec" / "README.md").write_text(page, encoding="utf-8")
    if sheet is not None:
        (root / "spec" / "REQUIREMENTS.md").write_text(sheet, encoding="utf-8")
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
        "| R9 | 15 000-page documents are included | ratified | none | Ticket 0024 carries the filing. |",
        "| R9 | 15 000-page documents are included | ratified | none | Ticket 0024 carries the filing. |\n"
        "| R7 | multilingual by default | ratified | none | Invented. |",
    )
    assert cp.run(build(tmp_path, page=page)) == 1


def test_row_filed_under_the_wrong_section(tmp_path):
    """Sections are the sheet's, not the page's; a row that migrates is a finding."""
    page = PAGE.replace(
        "| R9 | 15 000-page documents are included | ratified | none | Ticket 0024 carries the filing. |\n",
        "",
    ).replace(
        "| R2 | most recent first | open | partial | Under revision in ticket 0080. |",
        "| R2 | most recent first | open | partial | Under revision in ticket 0080. |\n"
        "| R9 | 15 000-page documents are included | ratified | none | Ticket 0024 carries the filing. |",
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
    page = PAGE.replace("| Coverage | `█░` | `█▓` |", "| Coverage | `█░` | `██` |")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_headline_count_that_stopped_matching_its_bar(tmp_path):
    page = PAGE.replace("2 ratified · 1 still open", "3 ratified · 0 still open")
    assert cp.run(build(tmp_path, page=page)) == 1


def test_status_word_outside_the_vocabulary(tmp_path):
    page = PAGE.replace("| ratified | shipped |", "| ratified | done |")
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
        "experiment X3a, commit b132f2d, ticket 0080.",
    )
    assert cp.run(build(tmp_path, page=page)) == 0


def test_the_real_page_passes_its_own_guard(tmp_path):
    """The shipped documents, not a fixture — the wiring the fixtures cannot see."""
    assert cp.run(REPO) == 0
