"""The normative-language guard, exercised against fixture documents.

Same discipline as the sibling guards' tests: the positive controls come first
and they use real sentences from the pre-0050 tree, not invented ones. A guard
whose all-clear is indistinguishable from "I could not look" is not a guard, and
this one has two distinct ways to look, so it needs two distinct controls.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("cn", REPO / "bench" / "check_normative.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cn = load()


HEAD = "# REQUIREMENTS\n\n## Intro\n\nPreamble.\n\n## Requirements\n\n### Coverage\n\n"
TAIL = "\n## The resolved decisions\n\nA table.\n"


def document(*bullets: str) -> str:
    return HEAD + "\n".join(bullets) + TAIL


def test_a_keyworded_item_passes():
    text = document("- **R1 — a promise.** Coverage MUST reach 100 %.")
    assert cn.check(text) == []


def test_lowercase_modal_in_a_contract_line_fires():
    """Positive control one: R19's real pre-0050 sentence.

    It carried the only literal lowercase "must" inside an R-item.
    """
    text = document(
        "- **R19 — the fold sweep is a gate.** Every token the query normalizer\n"
        "  produces must be one the index normalizer can also produce."
    )
    problems = cn.check(text)
    assert any("lowercase 'must'" in p for p in problems), problems


def test_an_item_with_no_modal_at_all_fires():
    """Positive control two, and the one a lowercase-modal grep cannot see.

    This is R21's real pre-0050 sentence. It states an obligation with no modal
    verb of any kind, so a blacklist reports it clean while its force is
    undeclared. DESIGN 2.9 was the same shape: zero modals, every budget
    unforced.
    """
    text = document(
        "- **R21 — same corpus in, same answers out.** A pinned query set with\n"
        "  golden answers gates every change."
    )
    problems = cn.check(text)
    assert any("declares no force" in p for p in problems), problems


def test_the_two_checks_are_independent():
    """One item can fail both ways; neither check subsumes the other."""
    both = document(
        "- **R19 — a gate.** Every token the query normalizer produces must be\n"
        "  one the index normalizer can also produce."
    )
    problems = cn.check(both)
    assert any("declares no force" in p for p in problems)
    assert any("lowercase 'must'" in p for p in problems)


def test_a_named_exemption_is_accepted(monkeypatch):
    """An item may be unforced while a ticket owns its rewrite. The table is empty
    since R26 was retired from the sheet (2026-08-31), so the mechanism is tested
    with an exemption the test installs rather than one the repository carries."""
    monkeypatch.setitem(cn.UNFORCED, "R41", "under revision; a ticket owns the rewrite")
    text = document("- **R41 — convergence is watched.** Coverage must reach 100 %.")
    assert cn.check(text) == []


def test_an_exempt_item_that_gains_a_keyword_fires(monkeypatch):
    """The exemption is a debt, not a licence. Paying it must retire the entry."""
    monkeypatch.setitem(cn.UNFORCED, "R41", "under revision; a ticket owns the rewrite")
    text = document("- **R41 — convergence is watched.** Coverage MUST reach 100 %.")
    problems = cn.check(text)
    assert any("listed as unforced" in p for p in problems), problems


def test_narrative_outside_the_requirements_section_is_untouched():
    """The case convention applies to R-items, not the structural rulings."""
    text = (
        "# REQUIREMENTS\n\n## Intro\n\nA tag match must not outrank a title.\n\n"
        "## Requirements\n\n- **R1 — a promise.** Coverage MUST reach 100 %.\n"
        "\n## The resolved decisions\n\nD5 may be revisited.\n"
    )
    assert cn.check(text) == []


def test_a_renamed_section_is_not_a_pass():
    """An empty scan is the likeliest way for this guard to hide a hole."""
    text = "# REQUIREMENTS\n\n## Intro\n\nNo requirements section here.\n"
    problems = cn.check(text)
    assert any("found no R-items" in p for p in problems), problems


def test_missing_document_fails(tmp_path):
    assert cn.run(tmp_path) == 1


def test_the_repo_itself_is_clean():
    assert cn.run(REPO) == 0


def test_an_exemption_for_an_item_that_does_not_exist(monkeypatch):
    """A dead exemption excuses nothing and says nothing, which is how it survives.

    The case that exposed it: R26 was retired from the sheet and its entry stayed
    behind, excusing an item nobody could find.
    """
    monkeypatch.setitem(cn.UNFORCED, "R99", "retired, and never removed from this table")
    text = document("- **R1 — the whole library.** Coverage MUST reach 100 %.")
    problems = cn.check(text)
    assert any("R99" in problem for problem in problems), problems
