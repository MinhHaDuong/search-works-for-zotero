"""The fixture recipe obeys the provenance rulings, and the validator can say no.

DECISIONS.md, 2026-09-02, "The golden fixture corpus": every document comes
from a public archive by persistent identifier, never from a personal library or
homepage; the three open archives (HAL, arXiv, Zenodo) need a version on the
identifier; a hash pins the bytes or a stated reason says why not. The live
recipe is checked against the real validator, and the validator is checked
against the exact defects the closed PR #151 shipped — a Zotero attachment key,
a personal-homepage URL, a live publisher page — so that an all-clear on the
recipe is known to mean something.
"""

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "bench" / "fixtures"


def load():
    spec = importlib.util.spec_from_file_location("fr", FIXTURES / "fetch_recipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fr = load()


def good(**over) -> dict:
    doc = {
        "id": "example-1900-work",
        "title": "An example",
        "author": "Someone",
        "year": 1900,
        "language": "en",
        "tier": "MUST",
        "facet": "core",
        "archive": "internet-archive",
        "identifier": "exampleitem00some",
        "bytes_url": "https://archive.org/download/exampleitem00some/exampleitem00some.pdf",
        "sha256": "0" * 64,
        "license_basis": "Published 1900; public domain everywhere.",
    }
    doc.update(over)
    return doc


def test_a_clean_entry_passes():
    assert fr.validate([good()]) == []


def test_zotero_key_is_an_offence():
    assert any("personal library" in o for o in fr.validate([good(zotero_attachment_key="DRKJ5I24")]))


def test_personal_homepage_is_an_offence():
    url = "https://minh.haduong.com/files/x.pdf"
    assert any("personal host" in o for o in fr.validate([good(bytes_url=url)]))


def test_live_publisher_page_is_an_offence():
    assert any("personal host" in o for o in fr.validate([good(bytes_url="https://www.gov.uk/guidance/the-highway-code")]))


def test_unadmitted_archive_is_an_offence():
    assert any("not admitted" in o for o in fr.validate([good(archive="google-books")]))


def test_open_archive_without_version_is_an_offence():
    assert any("no version" in o for o in fr.validate([good(archive="hal", identifier="hal-04214661")]))
    assert fr.validate([good(archive="hal", identifier="hal-04214661", version="v1")]) == []


def test_null_hash_needs_a_reason():
    assert any("sha256_reason" in o for o in fr.validate([good(sha256=None)]))
    assert fr.validate([good(sha256=None, sha256_reason="1,2 GB; archive md5 recorded instead")]) == []


def test_duplicate_ids_and_missing_fields_are_offences():
    offences = fr.validate([good(), good(), {"id": "bare"}])
    assert any("duplicate id" in o for o in offences)
    assert any("bare: missing title" in o for o in offences)


def test_live_recipe_is_valid():
    recipe = json.loads((FIXTURES / "recipe.json").read_text(encoding="utf-8"))
    assert isinstance(recipe, list) and recipe
    assert fr.validate(recipe) == []


def test_live_recipe_covers_the_must_tier_languages():
    recipe = json.loads((FIXTURES / "recipe.json").read_text(encoding="utf-8"))
    must = {d["language"] for d in recipe if d["tier"] == "MUST"}
    assert {"en", "fr", "vi"} <= must, f"MUST tier languages present: {sorted(must)}"


def test_fetch_script_has_argparse_and_no_extraction():
    src = (FIXTURES / "fetch_recipe.py").read_text(encoding="utf-8")
    assert "ArgumentParser" in src and "--cache-dir" in src and "--only" in src
    for tool in ("pdftotext", "pandoc", "tesseract"):
        assert tool not in src, f"the recipe fetcher must not extract text ({tool})"
