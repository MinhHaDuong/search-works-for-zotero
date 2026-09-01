"""Tests for bench/check_figures.py — the guard against stale figures in the prose.

Written after the checker's own fixer corrupted a tracked ticket (`0,406,406,406and`) and
the checker, then a substring test, reported the file clean.

Each test was checked by sabotage — break the guard it names, confirm it goes red. One did
not: `test_a_corrupted_slot_fails` stays green when the exact slot match is reverted to a
substring test, because the empty-tail ban already makes the two equivalent. That is
recorded in the test rather than papered over, and it is why the test is named for the
outcome it observes instead of the mechanism it was assumed to cover.

The repo had no test directory. It has one now, because a 300-line guard whose failure
mode is silently certifying a broken document is exactly the thing that needs one.

    python3 -m pytest tests/ -q
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("cf", REPO / "bench" / "check_figures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cf = load()


# --- rendering ---------------------------------------------------------------------

def test_rendered_uses_a_decimal_comma_and_no_thousands_separator():
    # The comparison form. Documents separate thousands; the artifact does not, and the
    # comparison happens on the de-spaced text, so the wanted string must carry no
    # separator of its own.
    assert cf.rendered(360811, 0) == "360811"
    assert cf.rendered(101.42, 1) == "101,4"
    assert cf.rendered(0.5213, 1, pct=True) == "52,1"


def test_render_value_handles_a_two_element_range():
    # Declaring the ends of a range as two figures made each anchor contain the other's
    # value, so fixing either broke the other.
    assert cf.render_value([0.5, 9.2], 1) == "0,5-9,2"


@pytest.mark.parametrize("sep", [" ", " ", " ", " "])
def test_despace_removes_every_separator_between_digits(sep):
    # A narrow no-break space once leaked from the French prose into the checker's own
    # source, which then reported all fifty pairs stale.
    assert cf.despace(f"360{sep}811") == "360811"


def test_despace_leaves_spaces_that_are_not_between_digits():
    assert cf.despace("mean norm 0,406, and only 2") == "mean norm 0,406, and only 2"


# --- key paths ---------------------------------------------------------------------

def test_dig_walks_dicts_and_lists():
    # dig() walked only dict.get(), so the recall column — a list — was precisely what the
    # checker could not see, and its most-quoted figures went unguarded.
    doc = {"recall": [{"v": 1}, {"v": 2}, {"v": 3}]}
    assert cf.dig(doc, "recall.2.v") == 3
    assert cf.dig(doc, "recall.9.v") is None
    assert cf.dig(doc, "recall.x.v") is None
    assert cf.dig(doc, "absent.v") is None


# --- the corruption this file exists for ---------------------------------------------

def test_every_declared_anchor_delimits_its_slot_on_both_sides():
    # An empty tail leaves the slot with no right-hand boundary, so a match runs on into
    # whatever follows. That is what produced `0,406,406,406and`.
    for entry in cf.FIGURES:
        for key, anchor in entry[3].items():
            if anchor is None:
                continue
            head, marker, tail = anchor.partition("{}")
            assert marker == "{}", f"{entry[1]} in {key}: anchor has no slot"
            assert tail.strip(), f"{entry[1]} in {key}: anchor {anchor!r} has nothing after the slot"


def test_validate_anchors_refuses_an_empty_tail(monkeypatch):
    monkeypatch.setattr(cf, "FIGURES", [("a.json", "k", 1, {"state": "mean norm {}"})])
    with pytest.raises(SystemExit):
        cf._validate_anchors()


def test_a_corrupted_slot_fails(tmp_path, monkeypatch):
    """A slot holding 0,406,406,406 must not satisfy an expected 0,406.

    Named for what it proves, after an earlier version of it claimed more. It does NOT
    demonstrate that the exact slot match is load-bearing: with `_validate_anchors`
    refusing empty tails, a substring test gives the same verdict here, and sabotaging the
    exactness leaves this green. The guard that actually stops the corruption is the
    empty-tail ban, covered by `test_validate_anchors_refuses_an_empty_tail` — sabotage
    that one and the suite goes red. The exact match stays as defence in depth and is not
    claimed to be more.
    """
    artifact = tmp_path / "results" / "a.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"norm": 0.406}))
    doc = tmp_path / "DOC.md"

    monkeypatch.setattr(cf, "REPO", tmp_path)
    monkeypatch.setattr(cf, "PROSE", {"doc": ["DOC.md"]})
    monkeypatch.setattr(cf, "FIGURES", [("a.json", "norm", 3, {"doc": "mean norm {}, and"})])

    doc.write_text("Measured: mean norm 0,406, and only 2 of 384.\n")
    assert cf.main_for_test(str(artifact.parent)) == 0, "the intact document must pass"

    doc.write_text("Measured: mean norm 0,406,406,406, and only 2 of 384.\n")
    assert cf.main_for_test(str(artifact.parent)) == 1, (
        "a corrupted slot that merely STARTS with the right digits must fail — "
        "this is the defect that let a broken ticket be certified clean"
    )


def test_a_stale_duplicate_elsewhere_cannot_mask_an_anchored_figure(tmp_path, monkeypatch):
    """Presence-only was defeated by a surviving duplicate; anchoring is what fixed it."""
    artifact = tmp_path / "results" / "a.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"ms": 59.6}))
    doc = tmp_path / "DOC.md"

    monkeypatch.setattr(cf, "REPO", tmp_path)
    monkeypatch.setattr(cf, "PROSE", {"doc": ["DOC.md"]})
    monkeypatch.setattr(cf, "FIGURES", [("a.json", "ms", 1, {"doc": "| 0,969 | {} ms |"})])

    # The right value in the slot, and a stale copy of an older value further down.
    doc.write_text("| 0,969 | 59,6 ms |\nElsewhere the text still says 63,1 ms.\n")
    assert cf.main_for_test(str(artifact.parent)) == 0

    # The slot goes stale while the correct value survives elsewhere in the document.
    doc.write_text("| 0,969 | 63,1 ms |\nAnd elsewhere, correctly, 59,6 ms.\n")
    assert cf.main_for_test(str(artifact.parent)) == 1


def test_a_missing_artifact_is_reported_rather_than_passing(tmp_path, monkeypatch):
    # A check whose all-clear is indistinguishable from "I could not look" is not a check.
    monkeypatch.setattr(cf, "REPO", tmp_path)
    monkeypatch.setattr(cf, "PROSE", {"doc": ["DOC.md"]})
    monkeypatch.setattr(cf, "FIGURES", [("nope.json", "k", 1, {"doc": "x {} y"})])
    (tmp_path / "DOC.md").write_text("nothing here\n")
    assert cf.main_for_test(str(tmp_path)) == 1


# --- the real declarations ------------------------------------------------------------

def test_the_repo_declarations_are_all_current():
    """The live check, so a stale figure fails the suite and not only a manual run."""
    assert cf.main_for_test(
        str(REPO / "bench" / "results"), minimum_pairs=cf.MINIMUM_PAIRS
    ) == 0


def test_shrinking_below_the_pair_count_ratchet_fails(monkeypatch, caplog):
    """A green check must not be reachable by shrinking below its coverage floor."""
    figures = list(cf.FIGURES)
    while sum(len(entry[3]) for entry in figures) >= cf.MINIMUM_PAIRS:
        figures.pop()
    monkeypatch.setattr(cf, "FIGURES", figures)
    assert cf.main_for_test(
        str(REPO / "bench" / "results"), minimum_pairs=cf.MINIMUM_PAIRS
    ) == 1
    assert "Re-record MINIMUM_PAIRS deliberately" in caplog.text


def test_adding_a_declaration_needs_no_second_edit(monkeypatch):
    """The floor is one-way: extra coverage passes without moving the ratchet."""
    monkeypatch.setattr(cf, "FIGURES", [*cf.FIGURES, cf.FIGURES[-1]])
    assert cf.main_for_test(
        str(REPO / "bench" / "results"), minimum_pairs=cf.MINIMUM_PAIRS
    ) == 0


def test_a_ticket_is_found_whether_open_or_archived(tmp_path, monkeypatch):
    """Closing a ticket moves it to `closed/`; its declarations must follow it.

    The first version listed the two paths as separate keys and skipped whichever did not
    exist, so archiving ticket 0008 dropped 23 checks and the run still reported 0 stale —
    at exactly the moment the document became permanent.
    """
    artifact = tmp_path / "results" / "a.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"n": 42}))
    monkeypatch.setattr(cf, "REPO", tmp_path)
    monkeypatch.setattr(cf, "PROSE", {"t": ["tickets/x.erg", "tickets/closed/x.erg"]})
    monkeypatch.setattr(cf, "FIGURES", [("a.json", "n", 0, {"t": "holds {} rows"})])

    (tmp_path / "tickets" / "closed").mkdir(parents=True)
    open_path = tmp_path / "tickets" / "x.erg"
    closed_path = tmp_path / "tickets" / "closed" / "x.erg"

    open_path.write_text("it holds 42 rows\n")
    assert cf.main_for_test(str(artifact.parent)) == 0

    # Archived, still correct: found at its new path rather than skipped.
    open_path.rename(closed_path)
    assert cf.main_for_test(str(artifact.parent)) == 0

    # Archived and stale: must fail, not silently vanish from the count.
    closed_path.write_text("it holds 41 rows\n")
    assert cf.main_for_test(str(artifact.parent)) == 1

    # Gone entirely: reported, never skipped.
    closed_path.unlink()
    assert cf.main_for_test(str(artifact.parent)) == 1


def test_a_line_break_inside_an_anchored_phrase_still_matches(tmp_path, monkeypatch):
    """Ticket 0542: an ordinary prose re-wrap must not report STALE on an unchanged figure.

    Anchors are one-line Python literals; the documents are re-wrapped prose. Before the
    whitespace normalization this asserted, a phrase the author split across two physical
    lines stopped matching, and the workaround — keeping every figure-bearing phrase on
    one line — had become folklore in two agent prompts.
    """
    artifact = tmp_path / "results" / "a.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"hits": 1234}))
    doc = tmp_path / "DOC.md"

    monkeypatch.setattr(cf, "REPO", tmp_path)
    monkeypatch.setattr(cf, "PROSE", {"doc": ["DOC.md"]})
    monkeypatch.setattr(cf, "FIGURES", [("a.json", "hits", 0, {"doc": "of {} hits both"})])

    doc.write_text("So of 1234 hits both arms return the same head.\n")
    assert cf.main_for_test(str(artifact.parent)) == 0, "the one-line form must pass"

    # The same sentence, re-wrapped. The figure did not move.
    doc.write_text("So of 1234\nhits both arms return the same head.\n")
    assert cf.main_for_test(str(artifact.parent)) == 0, (
        "a line break inside the anchored phrase is a re-wrap, not a stale figure"
    )

    # A spaced figure inside the phrase is fine, and so is a break beside it.
    doc.write_text("So of 1 234 hits\nboth arms return the same head.\n")
    assert cf.main_for_test(str(artifact.parent)) == 0

    # The stated remainder: a break landing on the figure's OWN thousands separator is
    # not matched, and deliberately so. despace() runs before unwrap() precisely so that
    # a line break is never read as a thousands separator — reading it as one glued
    # `2026-08-22` to the next line's `93022` and made the slot swallow the date, a false
    # STALE of exactly the kind this ticket removes. This asserts the trade, so nobody
    # "fixes" it by swapping the order and re-introducing the gluing.
    doc.write_text("So of 1\n234 hits both arms return the same head.\n")
    assert cf.main_for_test(str(artifact.parent)) == 1

    # Staleness still fails: normalization widens what counts as the same phrase,
    # never what counts as the same number.
    doc.write_text("So of 9999\nhits both arms return the same head.\n")
    assert cf.main_for_test(str(artifact.parent)) == 1


def test_unwrap_never_lets_a_break_glue_two_numbers_into_one_slot(tmp_path, monkeypatch):
    """The regression the whitespace normalization introduced, and the order that fixed it.

    Ticket 0542's first cut unwrapped before despacing, so a line break between two
    unrelated tokens became a space and despace() then removed it as a thousands
    separator. `2026-08-22\\n93022 passages` collapsed to `2026-08-2293022` and the slot
    reported the date as part of the figure. Both real documents that broke this way are
    covered by the live declarations; this holds the mechanism on its own.
    """
    artifact = tmp_path / "results" / "a.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"vectors": 93022}))
    doc = tmp_path / "DOC.md"

    monkeypatch.setattr(cf, "REPO", tmp_path)
    monkeypatch.setattr(cf, "PROSE", {"doc": ["DOC.md"]})
    monkeypatch.setattr(
        cf, "FIGURES", [("a.json", "vectors", 0, {"doc": "{} passages of the real library"})]
    )

    doc.write_text("Measured 2026-08-22\n93022 passages of the real library, warm.\n")
    assert cf.main_for_test(str(artifact.parent)) == 0, (
        "the digits ending the previous line must not be glued into the slot"
    )
