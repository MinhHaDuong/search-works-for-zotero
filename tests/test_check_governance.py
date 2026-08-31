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
    # Directories come from the scanned paths themselves. Hardcoding "spec" broke
    # this fixture the day a scanned document moved to verification/ (2026-08-31).
    if owner:
        (root / cg.OWNER).parent.mkdir(parents=True, exist_ok=True)
        (root / cg.OWNER).write_text("# Governance\n\nThe bounds live here.\n")
    for rel in cg.SCANNED:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
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


def test_an_arriving_document_must_be_triaged(tmp_path):
    """The positive control for the completeness check.

    This is the half of the scope problem that used to fail silently. A document
    that leaves breaks the build at the missing-document check; a document that
    arrives was simply never read, and nothing said so. FIELD-REVIEW.md sat
    unscanned that way. The fixture drops in a new root-level document listed
    nowhere, and the guard must refuse it.
    """
    repo = build(tmp_path, {})
    (repo / "THREATS.md").write_text("A new document nobody triaged.\n")
    assert cg.run(repo) == 1


def test_an_arriving_spec_document_must_be_triaged(tmp_path):
    """Same defect one directory down, where FIELD-REVIEW.md actually landed."""
    repo = build(tmp_path, {})
    (repo / "spec" / "GLOSSARY.md").write_text("Also untriaged.\n")
    assert cg.run(repo) == 1


def test_a_triaged_document_is_accepted(tmp_path):
    """Listing the arrival in either list clears it. Otherwise the check is a wall."""
    repo = build(tmp_path, {})
    (repo / "STATE.md").write_text("Operational, and listed as unscanned by design.\n")
    assert cg.run(repo) == 0


def test_verification_reports_are_out_of_scope(tmp_path):
    """Evidence, not authority: a different object class, deliberately unglobbed."""
    repo = build(tmp_path, {})
    (repo / "verification").mkdir(exist_ok=True)
    (repo / "verification" / "ACCEPTANCE-9999.md").write_text("A report.\n")
    assert cg.run(repo) == 0


def test_an_arriving_upstream_pr_body_must_be_triaged(tmp_path):
    """The one part of verification/ that IS in scope, because it is text we send.

    An upstream PR body is not evidence about upstream, it is the message: whatever
    governance sentence reaches it reaches the maintainer, on a repository he reads.
    So the arrival half of the scope problem has to close over these the way it
    closes over the spec — which is the same asymmetry the two tests above cover,
    at the only address where the reader is outside this repo.
    """
    repo = build(tmp_path, {})
    (repo / "verification").mkdir(exist_ok=True)
    (repo / "verification" / "UPSTREAM-PR-9999-SOMETHING.md").write_text("Outgoing.\n")
    assert cg.run(repo) == 1


def test_a_report_about_upstream_is_not_an_upstream_pr_body(tmp_path):
    """The boundary, and it is a discrimination rather than a formality.

    `UPSTREAM-PR-*` and not `UPSTREAM-*`, because a re-read of upstream's tree is
    a report — the same object class as every other file in this directory — and
    globbing it in would have made two independently green branches red in
    combination, with no CI here to notice. The narrower glob is the semantic
    answer as well as the merge-safe one: sending is what earns the gate.
    """
    repo = build(tmp_path, {})
    (repo / "verification").mkdir(exist_ok=True)
    (repo / "verification" / "UPSTREAM-1.12.0-REREAD.md").write_text("A report about upstream.\n")
    assert cg.run(repo) == 0


def test_the_repo_itself_is_fully_triaged():
    """Every document in the real tree is in exactly one list."""
    assert cg.uncovered(REPO) == set()
