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
import re
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


def test_refused_host_is_matched_case_insensitively():
    """`https://VBPL.VN/x.pdf` is the same host as `vbpl.vn`; a substring test let it through."""
    assert any("personal host" in o for o in fr.validate([good(bytes_url="https://VBPL.VN/doc.pdf")]))
    assert any("personal host" in o for o in fr.validate([good(bytes_url="https://WWW.GOV.UK/guidance/x")]))


def test_bytes_url_host_must_belong_to_the_declared_archive():
    """The closed PR's defect in miniature: an arbitrary host under an archive's label."""
    stray = good(bytes_url="https://www.dropbox.com/s/abc/exampleitem00some.pdf")
    assert any("does not belong to archive" in o for o in fr.validate([stray]))
    raw = good(bytes_url="https://raw.githubusercontent.com/x/y/main/a.pdf")
    assert any("does not belong to archive" in o for o in fr.validate([raw]))
    sub = good(bytes_url="https://ia800300.us.archive.org/12/items/exampleitem00some/x.pdf")
    assert fr.validate([sub]) == [], "a subdomain of the archive's host is the archive"


def test_unadmitted_archive_is_an_offence():
    assert any("not admitted" in o for o in fr.validate([good(archive="google-books")]))


def test_open_archive_without_version_is_an_offence():
    hal = dict(archive="hal", identifier="hal-04214661", bytes_url="https://hal.science/hal-04214661/file/x.pdf")
    assert any("no version" in o for o in fr.validate([good(**hal)]))
    assert any("no version" in o for o in fr.validate([good(**hal, version="final")]))
    assert fr.validate([good(**hal, version="v1")]) == []


def test_faolex_is_admitted_for_one_document_only():
    fao = dict(archive="faolex", bytes_url="https://faolex.fao.org/docs/pdf/vie000001.pdf")
    assert any("FAOLEX is admitted for" in o for o in fr.validate([good(**fao, identifier="LEX-FAOC000001")]))
    ok = good(archive="faolex", identifier="LEX-FAOC179224", bytes_url="https://faolex.fao.org/docs/pdf/vie179224.pdf")
    assert fr.validate([ok]) == []


def test_a_challenge_page_is_blocked_and_a_network_error_is_unfetched():
    import urllib.error

    http403 = urllib.error.HTTPError("https://x", 403, "Forbidden", {}, None)
    http500 = urllib.error.HTTPError("https://x", 500, "Server", {}, None)
    assert fr.classify_failure(http403) == "blocked"
    assert fr.classify_failure(http500) == "unfetched"
    assert fr.classify_failure(RuntimeError("u: expected b'%PDF' at file start, got b'<htm'")) == "blocked"
    assert fr.classify_failure(urllib.error.URLError("timed out")) == "unfetched"
    assert fr.classify_failure(RuntimeError("u: 12 bytes, expected at least 1000")) == "unfetched"


def test_exit_status_fails_on_mismatch_or_outage_and_not_on_expected_states():
    assert fr.exit_status([{"status": "match"}, {"status": "blocked"}, {"status": "unpinned"}]) == 0
    assert fr.exit_status([{"status": "match"}, {"status": "unfetched"}]) == 1
    assert fr.exit_status([{"status": "MISMATCH"}]) == 1
    assert fr.exit_status([]) == 0


def test_null_hash_needs_a_reason():
    assert any("sha256_reason" in o for o in fr.validate([good(sha256=None)]))
    assert fr.validate([good(sha256=None, sha256_reason="1,2 GB; archive md5 recorded instead")]) == []


def test_id_is_one_path_component_and_format_is_known():
    """`../x` would name a cache file outside the cache; an unknown format skips the magic check."""
    assert any("not a lowercase slug" in o for o in fr.validate([good(id="../x")]))
    assert any("not a lowercase slug" in o for o in fr.validate([good(id="a/b")]))
    assert any("not a lowercase slug" in o for o in fr.validate([good(id="Upper-Case")]))
    assert any("bytes_format" in o for o in fr.validate([good(bytes_format="exe")]))
    assert fr.validate([good(bytes_format="djvu")]) == []


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


def test_live_recipe_tally_is_swept_into_its_documentation():
    recipe = json.loads((FIXTURES / "recipe.json").read_text(encoding="utf-8"))
    hashed = sum(bool(doc["sha256"]) for doc in recipe)
    open_by_archive = {
        archive: sum(doc["sha256"] is None and doc["archive"] == archive for doc in recipe)
        for archive in {doc["archive"] for doc in recipe}
        if any(doc["sha256"] is None and doc["archive"] == archive for doc in recipe)
    }
    assert (len(recipe), hashed, open_by_archive) == (
        26,
        17,
        {"gallica": 4, "hal": 4, "internet-archive": 1},
    )

    readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
    tally = re.search(
        r"As of (\d{4}-\d{2}-\d{2}), the recipe holds (\d+) records: "
        r"(\d+) with the bytes hashed and (\d+)",
        readme,
    )
    assert tally, "README must carry a dated, machine-checkable recipe tally"
    assert tuple(map(int, tally.groups()[1:])) == (len(recipe), hashed, len(recipe) - hashed)
    challenge_split = re.search(
        r"(\d+) of those\s+open records belong to the two represented archives.*?: "
        r"(\d+) HAL\s+.*?and (\d+) Gallica",
        readme,
        re.DOTALL,
    )
    assert challenge_split, "README must account for the open hashes by source"
    assert tuple(map(int, challenge_split.groups())) == (
        open_by_archive["hal"] + open_by_archive["gallica"],
        open_by_archive["hal"],
        open_by_archive["gallica"],
    )
    assert "The ninth is the oversized Malynes scan" in readme


def test_fetch_script_has_argparse_and_no_extraction():
    src = (FIXTURES / "fetch_recipe.py").read_text(encoding="utf-8")
    assert "ArgumentParser" in src and "--cache-dir" in src and "--only" in src
    for tool in ("pdftotext", "pandoc", "tesseract"):
        assert tool not in src, f"the recipe fetcher must not extract text ({tool})"
