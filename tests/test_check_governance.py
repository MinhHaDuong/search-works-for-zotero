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


def test_an_arriving_issue_draft_must_be_triaged(tmp_path):
    """The sibling address, and the one the first version of this missed.

    GOVERNANCE.md's disclosure rule names "pull request bodies, issue text, review
    replies", and this repo's form rule sends anything design-sized as an issue —
    so the issue drafts are not the rarer outgoing class, they are the commoner
    one. Two of them sat committed and paste-ready outside every glob while the
    PR-body glob was being written, because that fix was written from the document
    in front of it.
    """
    repo = build(tmp_path, {})
    (repo / "verification").mkdir(exist_ok=True)
    (repo / "verification" / "ISSUE-DRAFT-9999.md").write_text("Outgoing.\n")
    assert cg.run(repo) == 1


def test_a_leak_inside_an_issue_draft_is_caught(tmp_path):
    """Arrival is half the guard; this is the other half.

    Triaging a document buys nothing unless the scan then reads it, and the two
    failures are independent: a file can be listed and unread if the glob and the
    list disagree about its name. This runs against the REAL SCANNED entry rather
    than a monkeypatched one — `build()` materialises every scanned path, so
    writing the leak into one of them exercises the list as it actually ships.
    A first version appended its own fixture name to SCANNED, which made the test
    pass with or without this change: it was asserting that `scan()` reads
    SCANNED, which was never in doubt.
    """
    draft = "verification/ISSUE-DRAFT-0024.md"
    assert draft in cg.SCANNED, "the fixture below depends on this being a real scanned path"
    repo = build(tmp_path, {draft: "We keep at most two PRs in flight upstream.\n"})
    assert cg.run(repo) == 1
    # The control: the same file with nothing to hide passes, so the refusal above
    # is about the sentence and not about the filename.
    (repo / draft).write_text("A perfectly ordinary paragraph about full-text truncation.\n")
    assert cg.run(repo) == 0


def test_every_committed_outgoing_draft_is_scanned():
    """Read the TREE, not the lists.

    The version of this that read `SCANNED + UNSCANNED_BY_DESIGN` and checked each
    outgoing-looking entry was in the first could not fail for the defect that
    prompted it: the two issue drafts were in NEITHER list, so a list-driven loop
    never saw them and reported all clear. The files exist on disk; that is what
    has to be enumerated.

    A draft may be exempted only by ceasing to be a draft — the one move this class
    of document must never make is sitting in UNSCANNED_BY_DESIGN.
    """
    prefixes = ("ISSUE-DRAFT-", "UPSTREAM-PR-")
    on_disk = sorted(
        p.relative_to(REPO).as_posix()
        for p in (REPO / "verification").glob("*.md")
        if p.name.startswith(prefixes)
    )
    assert on_disk, "no outgoing draft on disk — the naming convention has drifted"
    for name in on_disk:
        assert name in cg.SCANNED, (
            f"{name} is outgoing text and is not scanned; add it to SCANNED in "
            "bench/check_governance.py"
        )


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
