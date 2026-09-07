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
import json
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


def test_live_recipe_hashed_subset_is_fully_pinned():
    """A live-data guard: every record select_hashed keeps has a sha256 on every attachment,
    and the open records (a stated sha256_reason each) are the only ones left out."""
    recipe = fr.load_recipe(FIXTURES / "recipe.json")
    hashed = sh.select_hashed(recipe)
    assert hashed, "the live recipe has pinned records"
    for doc in hashed:
        assert all(isinstance(source.get("sha256"), str) for source in doc.get("attachments", [doc]))
    left_out = [doc for doc in recipe if doc not in hashed]
    for doc in left_out:
        assert any(source.get("sha256") is None and source.get("sha256_reason")
                   for source in doc.get("attachments", [doc])), doc["id"]


def test_committed_pinned_recipe_is_exactly_the_hashed_subset():
    """bench/fixtures/recipe-pinned.json is the file inject, export and the replay all
    read, so the export manifest's recipe_sha256 pins the content the replay re-derives.
    It is derived data: regenerate it with select_hashed.py whenever recipe.json moves,
    and re-export, since a moved recipe hash invalidates the committed snapshot."""
    recipe = fr.load_recipe(FIXTURES / "recipe.json")
    expected = json.dumps(sh.select_hashed(recipe), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert (FIXTURES / "recipe-pinned.json").read_text(encoding="utf-8") == expected


def test_record_only_parent_is_hashed_vacuously_and_new_fields_pass_through():
    """Ticket 0721: a record-only parent (14,8 % of the census) has no bytes to pin, so
    it is kept as-is -- an empty attachment list is hashed vacuously -- and the ruled
    fields (topic, stratum, notes, citation, language_field) ride along untouched."""
    record_only = {
        "id": "record-only", "attachments": [], "record_only": True, "topic": "energy",
        "stratum": "core", "language_field": "", "citation": {"doi": "10.1000/x"},
        "notes": [{"id": "record-only-note", "html": "<p>a</p>"}],
    }
    partial = {"id": "one-missing", "attachments": [{"id": "b1", "sha256": None}], "topic": "energy"}
    assert sh.select_hashed([record_only, partial]) == [record_only]
