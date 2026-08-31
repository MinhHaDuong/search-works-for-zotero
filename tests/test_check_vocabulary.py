"""The vocabulary guard, exercised against fixture repositories.

Same shape as the other guard suites: each test builds a small repository and
runs the real `run()` against it. Every test asserting a failure is a positive
control — the guard exists to fail on prose that reads perfectly well, which is
exactly the prose nobody catches by review.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("cv", REPO / "bench" / "check_vocabulary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cv = load()


def build(root: Path, body: str, name: str = "spec/DESIGN.md") -> Path:
    """A fixture repository carrying every scanned document, one of them with `body`."""
    (root / "spec").mkdir(parents=True, exist_ok=True)
    for scanned in cv.SCANNED:
        (root / scanned).write_text("# clean\n", encoding="utf-8")
    for unscanned in cv.UNSCANNED_BY_DESIGN:
        (root / unscanned).write_text("# a 15 000-page monster, recorded as it was written\n",
                                      encoding="utf-8")
    (root / name).write_text(body, encoding="utf-8")
    return root


def test_a_clean_repository_passes(tmp_path):
    assert cv.run(build(tmp_path, "# The 44.9 MB dictionary, named.\n")) == 0


def test_a_banned_word_fires(tmp_path):
    assert cv.run(build(tmp_path, "# One monster cannot monopolise the pipeline.\n")) == 1


def test_the_ban_is_case_insensitive_and_catches_compounds(tmp_path):
    """A ban answered by capitalising it, or by hyphenating it into a compound, is no ban."""
    assert cv.run(build(tmp_path, "# Monster-document arithmetic.\n")) == 1


def test_the_record_is_not_scanned(tmp_path):
    """The append-only ledger recorded rulings in the words they were made in."""
    repo = build(tmp_path, "# clean\n")
    (repo / "spec" / "DECISIONS.md").write_text("A monster, as ruled.\n", encoding="utf-8")
    assert cv.run(repo) == 0


def test_a_document_in_neither_list(tmp_path):
    """A document that arrives unscanned is the silent half of a hand-kept scope."""
    repo = build(tmp_path, "# clean\n")
    (repo / "NEWCOMER.md").write_text("# clean\n", encoding="utf-8")
    assert cv.run(repo) == 1


def test_a_scanned_document_that_vanished(tmp_path):
    """An all-clear reachable by failing to look is not an all-clear."""
    repo = build(tmp_path, "# clean\n")
    (repo / "spec" / "DESIGN.md").unlink()
    assert cv.run(repo) == 1


def test_every_ban_states_its_replacement(tmp_path):
    """A ban that only prohibits gets answered with a synonym."""
    assert all(len(replacement) > 20 for replacement in cv.BANNED.values())


def test_the_live_repository_passes():
    """The shipped documents, not a fixture."""
    assert cv.run(REPO) == 0
