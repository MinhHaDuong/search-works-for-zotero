"""The governance guard, exercised against fixture repositories.

Each test builds a whole small repository under tmp_path and runs the real
`run()` against it, rather than calling `scan()` on a string. The defects worth
catching here live in the wiring — a document that is not read at all, an owner
that does not exist — and a test that only ever feeds `scan()` a string cannot
see any of them.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("cg", REPO / "bench" / "check_governance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cg = load()


def build(root, docs: dict[str, str], owner: bool = True):
    """A fixture repository. `docs` overrides the default empty scanned files."""
    (root / "spec").mkdir(parents=True, exist_ok=True)
    if owner:
        (root / cg.OWNER).write_text("# Governance\n\nThe bounds live here.\n")
    for rel in cg.SCANNED:
        (root / rel).write_text(docs.get(rel, "nothing to see\n"))
    return root


def test_clean_repo_passes(tmp_path):
    assert cg.run(build(tmp_path, {})) == 0


def test_bound_without_pointer_fails(tmp_path):
    """The positive control. Without this firing, a green run means nothing."""
    repo = build(tmp_path, {"spec/DESIGN.md": "At most two upstream PRs in flight, ever.\n"})
    assert cg.run(repo) == 1


def test_pointer_on_the_line_excuses_it(tmp_path):
    """How DESIGN.md keeps naming the train's shape without restating the terms."""
    repo = build(
        tmp_path,
        {"spec/DESIGN.md": "The contained-PR budget is GOVERNANCE.md's; the remainder SYNC.md's.\n"},
    )
    assert cg.run(repo) == 0


def test_pointer_elsewhere_in_the_paragraph_does_not_excuse_it(tmp_path):
    """A reader who lands on the sentence by search sees the line, not the paragraph."""
    repo = build(
        tmp_path,
        {"spec/DESIGN.md": "See GOVERNANCE.md for process.\n\nAt most two PRs in flight, ever.\n"},
    )
    assert cg.run(repo) == 1


def test_naming_the_maintainer_is_not_a_finding(tmp_path):
    """CONSTRAINTS.md owns what he does; the guard flags what we decided about him.

    A guard that fired on the actor would push a measured fact out of the
    document whose whole job is facts about the terrain.
    """
    repo = build(
        tmp_path,
        {
            "spec/CONSTRAINTS.md": (
                "The upstream maintainer merges small contained PRs and reimplements\n"
                "design-sized proposals himself; the asymmetry is measured two-for-two.\n"
            )
        },
    )
    assert cg.run(repo) == 0


def test_missing_owner_fails(tmp_path):
    assert cg.run(build(tmp_path, {}, owner=False)) == 1


def test_missing_scanned_document_fails(tmp_path):
    """An all-clear must never be reachable by failing to look."""
    repo = build(tmp_path, {})
    (repo / "spec" / "DESIGN.md").unlink()
    assert cg.run(repo) == 1


def test_every_bound_is_detected(tmp_path):
    """Each tracked bound fires on its own, so none is dead vocabulary."""
    phrases = {
        "the in-flight cap": "at most two PRs in flight",
        "the contained-PR budget": "the contained-PR budget stands",
        "the sunset rule": "a three-week sunset applies",
        "the harness as a one-time transfer": "the harness is a one-time transfer",
        "the PR volume cap": "the volume cap is two",
        "the commitment bounds": "the commitment bounds are binding",
    }
    assert set(phrases) == set(cg.BOUNDS), "a bound was added without a detection test"
    for name, phrase in phrases.items():
        repo = tmp_path / name.replace(" ", "_")
        build(repo, {"spec/DESIGN.md": phrase + "\n"})
        assert cg.run(repo) == 1, f"{name} was not detected in {phrase!r}"
