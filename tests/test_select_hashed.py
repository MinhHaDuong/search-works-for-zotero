"""select_hashed.py keeps exactly the recipe records that are fully pinned.

golden_fixture.py's verify_source_bytes refuses the whole recipe if any one
record lacks a pinned sha256, by design (ticket 0029, ruling 2: a document
with no verified bytes must never reach injection). Ticket 0632's real
injection runs against a subset -- "the 17 already-hashed documents" -- so
this module derives that subset mechanically from the live recipe.json
rather than a hand-maintained copy, and this test proves the filter keeps
only fully-pinned records, in the parent recipe's order, for both the flat
shape (no ``attachments``) and the multi-attachment parent shape.
"""

import hashlib
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "bench" / "fixtures"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, FIXTURES / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sh = load("select_hashed", "select_hashed.py")
fr = load("fr_for_select_hashed", "fetch_recipe.py")

SHA_A = hashlib.sha256(b"a").hexdigest()
SHA_B = hashlib.sha256(b"b").hexdigest()


def test_keeps_only_fully_hashed_flat_records():
    hashed = {"id": "hashed-doc", "sha256": SHA_A}
    unpinned = {"id": "unpinned-doc", "sha256": None, "sha256_reason": "blocked by a challenge page"}
    assert sh.select_hashed([hashed, unpinned]) == [hashed]


def test_preserves_recipe_order():
    first = {"id": "first", "sha256": SHA_A}
    second = {"id": "second", "sha256": SHA_B}
    assert sh.select_hashed([second, first]) == [second, first]


def test_multi_attachment_parent_needs_every_source_pinned():
    complete = {
        "id": "two-attachments",
        "attachments": [{"id": "a1", "sha256": SHA_A}, {"id": "a2", "sha256": SHA_B}],
    }
    partial = {
        "id": "one-missing",
        "attachments": [{"id": "b1", "sha256": SHA_A}, {"id": "b2", "sha256": None}],
    }
    assert sh.select_hashed([complete, partial]) == [complete]


def test_rejects_a_short_or_non_string_sha256():
    short = {"id": "short-hash", "sha256": "abc123"}
    numeric = {"id": "numeric-hash", "sha256": 12345}
    assert sh.select_hashed([short, numeric]) == []


def test_live_recipe_yields_seventeen_hashed_records():
    """A live-data regression guard: the count this ticket's real run depends on."""
    recipe = fr.load_recipe(FIXTURES / "recipe.json")
    hashed = sh.select_hashed(recipe)
    assert len(hashed) == 17
    assert all(isinstance(doc.get("sha256"), str) for doc in hashed)
