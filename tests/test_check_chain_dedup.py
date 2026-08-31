"""The chain-dedup guard, exercised against fixture repositories.

Same shape, and same reason, as tests/test_check_governance.py: each test builds
a whole small repository under tmp_path and runs the real `run()` against it. The
defects worth catching live in the wiring — a document that is not read at all,
an owner that does not exist — and a test that only ever feeds `scan()` a string
cannot see any of them.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("ccd", REPO / "bench" / "check_chain_dedup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ccd = load()


def build(root, docs: dict[str, str], owner: bool = True):
    """A fixture repository. `docs` overrides the default empty scanned files."""
    # Derive each directory from the scanned path itself. Hardcoding "spec" here
    # made the fixture break the day a scanned document moved out of spec/
    # (FIELD-REVIEW.md to verification/, 2026-08-31) — the guard was correct and
    # its own test was what failed.
    if owner:
        (root / ccd.OWNER).parent.mkdir(parents=True, exist_ok=True)
        (root / ccd.OWNER).write_text("# Readme\n\nThe authoritative chain is described here.\n")
    for rel in ccd.SCANNED:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(docs.get(rel, "nothing to see\n"))
    return root


def test_clean_repo_passes(tmp_path):
    assert ccd.run(build(tmp_path, {})) == 0


def test_restatement_without_pointer_fails(tmp_path):
    """The positive control. Without this firing, a green run means nothing.

    The fixture text is the real pre-0054 sentence from spec/REQUIREMENTS.md:12,
    not an invented one: the guard exists because of that line.
    """
    repo = build(
        tmp_path,
        {
            "spec/REQUIREMENTS.md": (
                "Authority works like this: the author's rulings are recorded in\n"
                "DECISIONS.md first, and this document is then edited to match.\n"
            )
        },
    )
    assert ccd.run(repo) == 1


def test_pointer_on_the_line_excuses_it(tmp_path):
    repo = build(
        tmp_path,
        {"spec/DESIGN.md": "Its place in the authority chain is stated once, in README.md.\n"},
    )
    assert ccd.run(repo) == 0


def test_pointer_elsewhere_in_the_paragraph_does_not_excuse_it(tmp_path):
    """A reader who lands on the sentence through a search sees one line."""
    repo = build(
        tmp_path,
        {
            "spec/DESIGN.md": (
                "The chain is described in README.md.\n"
                "The author's rulings are recorded in DECISIONS.md.\n"
            )
        },
    )
    assert ccd.run(repo) == 1


def test_missing_owner_fails(tmp_path):
    """No home to point at is not a clean run."""
    assert ccd.run(build(tmp_path, {}, owner=False)) == 1


def test_missing_scanned_document_fails(tmp_path):
    """A document that could not be read must not look like one that passed."""
    repo = build(tmp_path, {})
    (repo / "spec" / "DESIGN.md").unlink()
    assert ccd.run(repo) == 1


def test_every_marker_has_a_phrase_that_fires():
    """No marker may be dead. A regex that matches nothing is a silent gap."""
    phrases = {
        "rulings recorded in DECISIONS.md": "Rulings are recorded in DECISIONS.md.",
        "the other documents are edited to match": "The others are then edited to match.",
        "vetoable on a later reading": "Any line remains vetoable on a later reading.",
        "authority works like this": "Authority works like this: rulings come first.",
        "rulings land here first": "The author's rulings land here first.",
    }
    assert set(phrases) == set(ccd.CHAIN_MARKERS), "a marker gained or lost its probe"
    for name, phrase in phrases.items():
        hits = ccd.scan(phrase)
        assert any(hit[1] == name for hit in hits), f"{name} matched nothing"


def test_a_ratified_entry_below_the_intro_is_not_a_finding(tmp_path):
    """The false positive that scoping to the head exists to prevent.

    A ratified DECISIONS.md entry legitimately says CONSTRAINTS.md and DESIGN.md
    "are edited to match" about one specific ruling. That is the chain working,
    not a restatement of it — and DECISIONS.md is append-only, so a guard able to
    demand an edit to an entry is wrong however it phrases the complaint.
    """
    repo = build(
        tmp_path,
        {
            "spec/DECISIONS.md": (
                "*Append-only. Its role is stated once, in README.md.*\n"
                "\n"
                "## Ratified\n"
                "\n"
                "**2026-08-29 — the RAM budget is per process.** CONSTRAINTS.md C3\n"
                "and DESIGN.md 2.9 are edited to match once the measurement lands.\n"
            )
        },
    )
    assert ccd.run(repo) == 0


def test_a_restatement_inside_the_intro_still_fires(tmp_path):
    """Head-scoping must not have bought its silence by looking nowhere."""
    repo = build(
        tmp_path,
        {
            "spec/DECISIONS.md": (
                "*The author's rulings land here first.*\n"
                "\n"
                "## Ratified\n"
                "\n"
                "Nothing yet.\n"
            )
        },
    )
    assert ccd.run(repo) == 1


def test_an_arriving_spec_document_must_be_triaged(tmp_path):
    """The other half of a hand-kept scope, and the half that fails silently.

    FIELD-REVIEW.md sat outside the governance guard this way, and TERMINOLOGY.md
    arrived while this guard was being written.
    """
    repo = build(tmp_path, {})
    (repo / "spec" / "ONTOLOGY.md").write_text("A new chain document nobody triaged.\n")
    assert ccd.run(repo) == 1


def test_the_repo_itself_is_clean():
    """The guard's own subject. Red before ticket 0054, green after."""
    assert ccd.run(REPO) == 0


def test_the_repo_itself_is_fully_triaged():
    """Every document in the spec directory is in exactly one list."""
    assert ccd.untriaged(REPO) == set()
