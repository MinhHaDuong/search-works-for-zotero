"""The one shape-guarded reader of a Zotero profile's `extensions.json`.

Ticket 0713. The same four-defect fix — document-shape, container-shape,
element-shape, and the parse doors that are neither `ValueError` nor `OSError`
— was written twice and hand-ported once, between `bench/sdt_sitter_install.py`
and `bench/acceptance/adapters/beaver.py`. Two copies of a fix drift; this
module is the single implementation, and this file is the suite that owns its
behaviour.

The two call-site suites keep their own arms, which is deliberate: they pin
what each *caller* does with the record (an exit code in one, an evidence
dictionary in another), not how the record is computed. What this file adds
that neither could is the delegation arms — proof that both call sites reach
this function rather than a private copy of it, which is the only thing that
keeps the duplication from growing back unnoticed.
"""

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "bench") not in sys.path:
    sys.path.insert(0, str(ROOT / "bench"))

shared = importlib.import_module("bench.host_addon_record")
read = shared.host_addon_record

ADDON_ID = "ours@example.invalid"
OTHER_ID = "other@example.org"

#: Nested past the interpreter's recursion limit: `json` rejects it by
#: exhausting the stack, and `RecursionError` descends from `RuntimeError`.
TOO_DEEP = "[" * 200_000 + "]" * 200_000


def profile_with(tmp_path: Path, name: str, document: str) -> Path:
    """A profile directory holding `document` verbatim as its extensions.json."""
    profile = tmp_path / name
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "extensions.json").write_text(document, encoding="utf-8")
    return profile


def with_addons(tmp_path: Path, name: str, addons: list) -> Path:
    return profile_with(tmp_path, name,
                        json.dumps({"schemaVersion": 35, "addons": addons}))


def test_present_absent_and_unread_are_three_findings(tmp_path):
    """The controls, without which the shape arms below prove only that it runs.

    Three findings the reader must keep apart: our add-on is recorded, someone
    else's is and ours is not, and the file could not be read at all. The last
    is the one that collapses silently — coerced to `present: False` it reads
    as a measurement rather than as a failure to measure, and both callers
    turn that into a green.
    """
    entry = {"id": ADDON_ID, "version": "1.2.3", "active": True,
             "location": "app-profile"}
    present = with_addons(tmp_path, "present", [{"id": OTHER_ID}, entry])
    assert read(present, ADDON_ID) == {
        "read": True, "present": True, "version": "1.2.3",
        "active": True, "location": "app-profile"}

    absent = with_addons(tmp_path, "absent", [{"id": OTHER_ID}])
    record = read(absent, ADDON_ID)
    assert record["read"] is True and record["present"] is False
    assert record["ids"] == [OTHER_ID]

    missing = tmp_path / "missing"
    missing.mkdir()
    assert read(missing, ADDON_ID) == {
        "read": False, "why": f"{missing / 'extensions.json'} does not exist"}

    truncated = profile_with(tmp_path, "truncated", "{ truncated")
    record = read(truncated, ADDON_ID)
    assert record["read"] is False and "present" not in record


@pytest.fixture
def unsearchable_profile(tmp_path):
    """A profile holding `extensions.json`, then stripped of its search bit.

    Mode 0o600 is readable and not searchable, so `open()` on anything inside
    fails with EACCES — the errno `pathlib` does *not* fold into "not a file".
    The mode is restored in teardown so a failing assertion cannot leave
    `tmp_path` undeletable.
    """
    profile = with_addons(tmp_path, "locked", [{"id": ADDON_ID}])
    profile.chmod(0o600)
    try:
        yield profile
    finally:
        profile.chmod(0o700)


@pytest.mark.skipif(os.geteuid() == 0,
                    reason="root ignores the search bit, so the arm discriminates nothing")
def test_an_unsearchable_profile_is_unread_rather_than_a_crash(unsearchable_profile):
    """The failure the `try` could not see, because it happened before the `try`.

    `is_file()` sat above the guard, and `pathlib` swallows OSError only for
    ENOENT, ENOTDIR, EBADF and ELOOP. EACCES is not among them, so a profile
    directory without its search bit re-raised PermissionError past every guard
    below — out of this reader, into the sitter's `main()` (which exits 1, the
    code that tool means by ABSENT) and into the evidence dictionaries beaver's
    verbs return unguarded. Fixed on the two originals as ticket 0762, and
    carried here with them when 0713 merged the copies.
    """
    # Positive control: the mode really does bite here, so a green below is the
    # reader's doing and not the filesystem's indulgence.
    with pytest.raises(PermissionError):
        (unsearchable_profile / "extensions.json").read_text(encoding="utf-8")

    record = read(unsearchable_profile, ADDON_ID)
    assert record["read"] is False
    assert "present" not in record
    # Named as a permission, so the arm cannot be satisfied by a reader that
    # reports the file missing.
    assert "PermissionError" in record["why"], record["why"]


def test_a_path_that_is_there_and_is_not_a_file_says_so(tmp_path):
    """"Does not exist" is a false sentence about a path `ls` plainly shows.

    `pathlib` folds a symlink loop (ELOOP) into "not a file" exactly as it
    folds ENOENT, and `exists()` follows the link and comes back False on the
    loop — so `is_symlink()` is what tells the two apart.
    """
    profile = tmp_path / "looped"
    profile.mkdir()
    path = profile / "extensions.json"
    path.symlink_to(path)
    record = read(profile, ADDON_ID)
    assert record == {"read": False, "why": f"{path} is not a regular file"}

    directory = tmp_path / "adirectory"
    (directory / "extensions.json").mkdir(parents=True)
    assert read(directory, ADDON_ID)["why"].endswith("is not a regular file")


def test_an_id_matches_on_the_id_and_not_on_a_neighbouring_field(tmp_path):
    """A foreign add-on whose every other field matches ours is not ours.

    A positive and a negative arm alone are satisfied by a reader keyed on
    `version` or `location`; only an id-keyed read tells "our add-on is
    installed" from "an add-on is installed".
    """
    foreign = with_addons(tmp_path, "foreign", [
        {"id": OTHER_ID, "version": "1.2.3", "active": True,
         "location": "app-profile"}])
    assert read(foreign, ADDON_ID)["present"] is False


def test_a_document_of_the_wrong_shape_is_unread_rather_than_a_crash(tmp_path):
    """Valid JSON is not a valid record, and `except (ValueError, OSError)` cannot tell.

    `[]` and `"text"` parse cleanly and then have no `.get`; an `addons` that
    is an object rather than a list iterates over its KEYS, handing a string to
    the same `.get`. Both raised out of the reader before the fix — into an
    exit code one caller reads as ABSENT, and into an unguarded evidence
    dictionary in the other.
    """
    for i, document in enumerate(("[]", '"text"', "3", "null",
                                  json.dumps({"addons": {"id": "x"}}),
                                  json.dumps({"addons": "one add-on"}))):
        record = read(profile_with(tmp_path, f"shape-{i}", document), ADDON_ID)
        assert record["read"] is False, document
        assert "present" not in record, document

    deep = profile_with(tmp_path, "deep", TOO_DEEP)
    record = read(deep, ADDON_ID)
    assert record["read"] is False and "present" not in record


def test_a_parse_that_exhausts_a_resource_is_unread_rather_than_a_crash(
        tmp_path, monkeypatch):
    """The two doors that are neither ValueError nor OSError, pinned as a pair.

    `RecursionError` descends from `RuntimeError` and `MemoryError` inherits
    `Exception` directly, so a reader catching the two obvious families by
    reflex lets both through. `MemoryError` is the arm the sitter's own copy
    did not have before this module merged the two: the union of the two
    implementations is the tolerant one, since the narrower tuple's only extra
    behaviour was to raise.

    Raising the door directly rather than exhausting the heap is not the
    weaker test: what would regress is a future edit narrowing the tuple, and
    for that the exception's identity is the whole content.
    """
    target = with_addons(tmp_path, "exhausted", [])
    for door in (RecursionError, MemoryError):
        def raise_door(*a, _door=door, **kw):
            raise _door()
        monkeypatch.setattr(json, "loads", raise_door)
        record = read(target, ADDON_ID)
        assert record["read"] is False, door.__name__
        assert "present" not in record, door.__name__
        assert door.__name__ in record["why"], record["why"]


def test_an_element_of_the_wrong_shape_is_absent_rather_than_a_crash(tmp_path):
    """The third floor of the same trapdoor: document, container, then element.

    An entry whose `id` is a number is valid JSON in a valid object in a valid
    list, and it reached `sorted()` over mixed types, where `str < int` raises
    TypeError. The second arm keeps the fix from being a blanket "give up on
    any odd file": the add-on is still found when it sits among that debris.
    """
    debris = with_addons(tmp_path, "mixed", [
        {"id": 17, "version": "1.0"},
        {"id": OTHER_ID},
        {"id": None},
        {"id": ["a", "list"]},
        "not an object at all",
        {},
    ])
    record = read(debris, ADDON_ID)
    assert record["read"] is True and record["present"] is False
    assert record["ids"] == [OTHER_ID], record["ids"]

    found = with_addons(tmp_path, "found-among-debris",
                        [{"id": 17}, {"id": ADDON_ID, "active": True}, "junk"])
    assert read(found, ADDON_ID)["present"] is True


def test_a_directory_named_extensions_json_is_unread_rather_than_a_crash(tmp_path):
    """`is_file()` and not `exists()`: a directory of that name is not a record."""
    profile = tmp_path / "dir-shaped"
    (profile / "extensions.json").mkdir(parents=True)
    record = read(profile, ADDON_ID)
    assert record["read"] is False and "present" not in record


# ---- delegation: both call sites reach this function ------------------------
#
# The arms that make this module the single implementation rather than a third
# copy. Each patches the name in the *importing* module's namespace, which is
# where a `from … import` binding lives — so an arm goes red the day a caller
# grows a private reader again, which no behavioural test could see.


@pytest.fixture
def sitter():
    return importlib.import_module("sdt_sitter_install")


@pytest.fixture
def beaver():
    return importlib.import_module("bench.acceptance.adapters.beaver")


def test_the_sitter_installer_reads_through_the_shared_function(
        sitter, monkeypatch, tmp_path):
    seen = {}

    def spy(profile, addon_id):
        seen["call"] = (Path(profile), addon_id)
        return {"read": True, "present": True, "sentinel": True}

    monkeypatch.setattr(sitter, "host_addon_record", spy)
    assert sitter.read_addon_record(tmp_path)["sentinel"] is True
    assert seen["call"] == (tmp_path, sitter.ADDON_ID)

    assert sitter.read_addon_record(tmp_path, "explicit@example.invalid")
    assert seen["call"] == (tmp_path, "explicit@example.invalid")


def test_the_beaver_adapter_reads_through_the_shared_function(
        beaver, monkeypatch, tmp_path):
    seen = {}

    def spy(profile, addon_id):
        seen["call"] = (Path(profile), addon_id)
        return {"read": True, "present": True, "sentinel": True}

    monkeypatch.setattr(beaver, "host_addon_record", spy)
    # Constructed without `__init__`: this arm is about the one attribute the
    # method reads, and the real constructor demands a host binary and a
    # digest-pinned artifact that have nothing to do with it.
    target = object.__new__(beaver.Beaver)
    target.profile = tmp_path / "profile"
    assert target._host_addon_record()["sentinel"] is True
    assert seen["call"] == (tmp_path / "profile", beaver.ADDON_ID)
