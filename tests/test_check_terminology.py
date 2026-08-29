"""The terminology guard, exercised against fixture repositories.

Same shape as `test_check_governance.py`, and for the same reason: each test
builds a small repository under tmp_path and runs the real `run()` against it,
rather than calling the line scanner on a string. The defects worth catching
live in the wiring — a file that is never opened, a glossary that emptied
itself — and a test that only ever feeds a string cannot see either.

Two of the assertions here are deliberately the opposite of the governance
suite's, and a reader who mistook one for a copy-paste slip would "fix" the
invariant away. They are documented at their own tests.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("ct", REPO / "bench" / "check_terminology.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ct = load()

CLEAN = """# TERMINOLOGY

## Ours

- **census** — a full listing fetched whole rather than paged.
  Authoritative: DESIGN.md §2.4.
"""


def build(root: Path, body: str | None = CLEAN) -> Path:
    """A fixture repository carrying `body` as the glossary, or none at all."""
    (root / "spec").mkdir(parents=True, exist_ok=True)
    if body is not None:
        (root / ct.GLOSSARY).write_text(body, encoding="utf-8")
    return root


def test_clean_glossary_passes(tmp_path):
    assert ct.run(build(tmp_path)) == 0


def test_restated_threshold_fails(tmp_path):
    """The positive control, verbatim from ticket 0051.

    Without this firing, a green run says nothing about the invariant.
    """
    seeded = (
        "# TERMINOLOGY\n\n## Ours\n\n"
        "- **census** — a full listing of every item, refetched every 60 s.\n"
        "  Authoritative: DESIGN.md §2.4.\n"
    )
    assert ct.run(build(tmp_path, seeded)) == 1


def test_a_pointer_on_the_line_does_not_excuse_the_number(tmp_path):
    """Deliberately the opposite of `test_pointer_on_the_line_excuses_it`.

    The governance guard scans thousands of lines of design prose, where a
    bound named beside its owner is exactly the wanted form. This guard
    enforces "the glossary owns no thresholds", and a threshold restated
    beside a citation is still a threshold restated: the second copy is the
    one that goes stale. Copying the governance semantics here would silently
    retire the invariant.
    """
    body = "# T\n\n- **the tick** — refreshes every 60 s (DESIGN.md §2.4).\n"
    assert ct.run(build(tmp_path, body)) == 1


def test_a_digit_in_the_term_slot_is_a_name_not_a_number(tmp_path):
    """`FTS5`, `seg/1`, `band 0`, `P0` are names. Their definitions are prose."""
    body = (
        "# T\n\n"
        "- **band 0 / band 1** — the two-band body frontier.\n"
        "  Authoritative: DESIGN.md §2.3.\n"
        "- **seg/1** — the heuristic entry segmenter.\n"
        "- **P0 / P1** — the server and the pipeline worker.\n"
    )
    assert ct.run(build(tmp_path, body)) == 0


def test_bold_inside_a_definition_is_still_scanned(tmp_path):
    """Only the leading term slot is exempt, not every emphasis span.

    Otherwise the exemption is a laundry: bold the number and it passes.
    """
    body = "# T\n\n- **the tick** — refreshes every **60 s**.\n"
    assert ct.run(build(tmp_path, body)) == 1


def test_missing_glossary_fails(tmp_path):
    """An all-clear must never be reachable by failing to look."""
    assert ct.run(build(tmp_path, None)) == 1


def test_empty_glossary_fails(tmp_path):
    """A file truncated to nothing is the same defect as a file deleted."""
    body = "# TERMINOLOGY\n\nNothing here yet.\n"
    assert ct.run(build(tmp_path, body)) == 1


def test_every_allowlist_class_is_admitted(tmp_path):
    """Each exemption fires on its own, so none is dead vocabulary.

    The mirror of the governance suite's `test_every_bound_is_detected`: there
    the tracked vocabulary is what must fail, here it is what must pass, so
    this is the test that keeps an unused exemption from quietly widening the
    guard.
    """
    lines = {
        "git SHA": "- **the panel** — the record at commit `e32afe3`.",
        "ISO date": "- **the split** — ratified 2026-08-29.",
        "reference code": "- **coverage** — the R1 promise, under C3, per D1, gated by X5.",
        "section mark": "- **the ledger** — authoritative: DESIGN.md §2.8.",
        "version string": "- **the fork** — v1.9.0 against Zotero 10 and SQLite 3.43.",
        "ticket ID": "- **seg/1** — built by ticket 0028, see tickets/0034.",
    }
    assert set(lines) == set(ct.ALLOWED), "an exemption was added without an admission test"
    for name, line in lines.items():
        repo = build(tmp_path / name.replace(" ", "_"), "# T\n\n" + line + "\n")
        assert ct.run(repo) == 0, f"{name} was not admitted by {line!r}"


def test_a_bare_number_is_not_admitted_by_any_class(tmp_path):
    """The allowlist must not have widened into a general numeric permit.

    Each phrase below is a near-miss of an exemption above: a seven-digit
    decimal that is not a SHA, a bare year that is not a date, a section
    number without its mark, a ceiling that is not a version, a threshold
    that is not a reference code.
    """
    for n, line in enumerate(
        (
            "- **the corpus** — 1234567 passages.",
            "- **the cycle** — closed in 2026.",
            "- **the tick** — see 2.4.",
            "- **the chunker** — a ceiling of 768 tokens.",
            "- **the golden gate** — mean Jaccard at or above 0.8.",
        )
    ):
        repo = build(tmp_path / f"near_miss_{n}", "# T\n\n" + line + "\n")
        assert ct.run(repo) == 1, f"not flagged: {line!r}"
