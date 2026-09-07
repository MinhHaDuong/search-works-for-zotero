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

import pytest
import re
import zipfile
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


def representative(**over) -> dict:
    first = good(id="example-pdf")
    second = good(id="example-html", bytes_format="html",
                  bytes_url="https://archive.org/download/exampleitem00some/example.html")
    doc = {
        "id": "example-work", "title": "An example", "author": "Someone", "year": 1900,
        "language": "en", "tier": "MUST", "facet": "core", "item_type": "journalArticle",
        "type_fidelity": "correct", "work_id": "example-work", "work_relations": [], "structural_features": [],
        "topic": "economics", "stratum": "core",
        "attachments": [
            {key: first[key] for key in fr.ATTACHMENT_REQUIRED if key in first} | {"bytes_format": "pdf"},
            {key: second[key] for key in fr.ATTACHMENT_REQUIRED if key in second} | {"bytes_format": "html", "charset": "utf-8"},
        ],
    }
    caps = {"pages": "does-not-cross", "chars": "does-not-cross", "combined": "neither", "locators": {}}
    doc["attachments"][0].update(role="primary", relation="same-text-different-format", selection_expectation="indexed", cap_expectations=caps)
    doc["attachments"][1].update(role="alternate-format", relation="same-text-different-format", selection_expectation="skipped-first-with-text", cap_expectations=caps, skip_reason="same-language sibling suppressed by first-with-text")
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


def test_project_gutenberg_ebook_number_is_persistent_and_unversioned():
    source = dict(
        archive="project-gutenberg", identifier="2701",
        bytes_url="https://www.gutenberg.org/cache/epub/2701/pg2701.txt",
        bytes_format="txt",
    )
    assert fr.validate([good(**source)]) == []
    assert any("ebook number" in o for o in fr.validate([good(**(source | {"identifier": "moby-dick"}))]))
    assert any("unversioned" in o for o in fr.validate([good(**(source | {"version": "v1"}))]))


def test_native_text_html_and_epub_capability_checks(tmp_path):
    text = tmp_path / "work.txt"
    text.write_bytes("Project Gutenberg\r\nMoby-Dick\r\n".encode())
    assert fr.validate_download_format(text, "txt") is None
    text.write_bytes(b"not utf8: \xff")
    assert "UTF-8" in fr.validate_download_format(text, "txt")

    html = tmp_path / "work.html"
    html.write_text("\ufeff<!DOCTYPE html><html><body>Work</body></html>", encoding="utf-8")
    assert fr.validate_download_format(html, "html") is None
    html.write_text("an error page without HTML markup", encoding="utf-8")
    assert "HTML" in fr.validate_download_format(html, "html")

    epub = tmp_path / "work.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<container/>")
    assert fr.validate_download_format(epub, "epub") is None
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("readme.txt", "not an epub")
    assert "EPUB" in fr.validate_download_format(epub, "epub")


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


def test_representative_parent_with_two_independently_provenanced_attachments_passes():
    assert fr.validate([representative()]) == []


def test_representative_schema_fails_closed_on_identity_type_and_attachment_semantics():
    bad_type = representative(type_fidelity="maybe")
    assert any("type_fidelity" in offence for offence in fr.validate([bad_type]))
    missing_reason = representative(type_fidelity="intentionally-wrong")
    assert any("type_fidelity_reason" in offence for offence in fr.validate([missing_reason]))
    bad_relation = representative(work_relations=[{"type": "translation", "target": "Other"}])
    assert any("target" in offence for offence in fr.validate([bad_relation]))
    bad_source = representative()
    del bad_source["attachments"][1]["license_basis"]
    bad_source["attachments"][0]["role"] = "unknown"
    offences = fr.validate([bad_source])
    assert any("missing license_basis" in offence for offence in offences)
    assert any("attachment role" in offence for offence in offences)


def test_attachment_ids_are_global_so_export_markers_and_cache_paths_are_unambiguous():
    other = representative(id="other-work", work_id="other-work")
    assert any("globally unique" in offence for offence in fr.validate([representative(), other]))


def test_cap_expectations_are_independent_consistent_and_located_across_boundaries():
    crossing = representative()
    crossing["attachments"][0]["cap_expectations"] = {
        "pages": "crosses", "chars": "crosses", "combined": "both",
        "locators": {"before_page_cap": "page-before-token", "after_page_cap": "page-after-token",
                     "before_char_cap": "char-before-token", "after_char_cap": "char-after-token"},
    }
    assert fr.validate([crossing]) == []
    crossing["attachments"][0]["cap_expectations"]["combined"] = "page-only"
    crossing["attachments"][0]["cap_expectations"]["locators"].pop("after_char_cap")
    offences = fr.validate([crossing])
    assert any("contradicts" in offence for offence in offences)
    assert any("before/after locators" in offence for offence in offences)


@pytest.mark.parametrize("control, message", [
    ({"expected_state": "unindexed", "expected_degradation": "no text layer"}, "must contain exactly"),
    ({"expected_state": "partial", "expected_degradation": "x", "answer_set_participation": "none"}, "expected_state 'partial' unknown"),
    ({"expected_state": "unindexed", "expected_degradation": " ", "answer_set_participation": "none"}, "expected_degradation is empty"),
    ({"expected_state": "unindexed", "expected_degradation": "x", "answer_set_participation": "pinned"}, "no part in golden answer sets"),
])
def test_failure_control_declares_state_degradation_and_no_answer_part(control, message):
    """DECISIONS.md 2026-09-03: every failure control declares its expected terminal or
    degradation state and whether it takes part in golden answers."""
    offences = fr.validate([good(failure_control=control)])
    assert len(offences) == 1 and message in offences[0], offences
    complete = {"expected_state": "unindexed", "expected_degradation": "no text layer",
                "answer_set_participation": "none"}
    assert fr.validate([good(failure_control=complete)]) == []


def test_live_recipe_declares_the_three_ruled_failure_controls():
    """Author, 2026-09-04 and 2026-09-06: the two Vietnamese dead-text volumes and the
    Ramsey scan stay, exported and scored as failure controls. At the ruled shape
    (ticket 0721) a control is declared on the attachment; further controls (the
    unindexable office, image and archive formats of the census) may join them."""
    recipe = json.loads((FIXTURES / "recipe.json").read_text(encoding="utf-8"))
    declared = {
        source["id"]: source["failure_control"]
        for doc in recipe
        for source in doc.get("attachments", [doc])
        if "failure_control" in source
    }
    assert {
        "tran-trong-kim-1920-viet-nam-su-luoc-q1",
        "tran-trong-kim-1928-viet-nam-su-luoc-q2",
        "ramsey-1931-foundations-of-mathematics",
    } <= set(declared)
    assert all(control["expected_state"] == "unindexed" for control in declared.values())
    assert all(control["answer_set_participation"] == "none" for control in declared.values())


def test_live_recipe_is_valid():
    recipe = json.loads((FIXTURES / "recipe.json").read_text(encoding="utf-8"))
    assert isinstance(recipe, list) and recipe
    assert fr.validate(recipe) == []


def test_live_recipe_covers_the_must_tier_languages():
    recipe = json.loads((FIXTURES / "recipe.json").read_text(encoding="utf-8"))
    must = {d["language"] for d in recipe if d["tier"] == "MUST"}
    assert {"en", "fr", "vi"} <= must, f"MUST tier languages present: {sorted(must)}"


def test_live_recipe_tally_is_swept_into_its_documentation():
    """The README's dated tally sentence is machine-checkable against the recipe: record
    count, hashed count and open count. The per-record table beside it is regenerated
    from the recipe by hand (ruling 10 of 2026-09-06: checklists, no prose guards)."""
    recipe = json.loads((FIXTURES / "recipe.json").read_text(encoding="utf-8"))
    hashed = sum(
        all(isinstance(source.get("sha256"), str) for source in doc.get("attachments", [doc]))
        for doc in recipe
    )
    readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
    tally = re.search(
        r"As of (\d{4}-\d{2}-\d{2}), the recipe holds (\d+) records: "
        r"(\d+) with the bytes hashed and (\d+)",
        readme,
    )
    assert tally, "README must carry a dated, machine-checkable recipe tally"
    assert tuple(map(int, tally.groups()[1:])) == (len(recipe), hashed, len(recipe) - hashed)


def test_fetch_script_has_argparse_and_no_extraction():
    src = (FIXTURES / "fetch_recipe.py").read_text(encoding="utf-8")
    assert "ArgumentParser" in src and "--cache-dir" in src and "--only" in src
    for tool in ("pdftotext", "pandoc", "tesseract"):
        assert tool not in src, f"the recipe fetcher must not extract text ({tool})"


# --- Ticket 0721: the ruled shape (topics, strata, charsets, notes, record-only
# --- parents, same-subject links, archives as data). One test per new offence.

def offences(*docs):
    return fr.validate(list(docs))


def test_topic_and_stratum_are_required_from_the_ruled_vocabularies():
    assert any("topic 'animals'" in o for o in offences(representative(topic="animals")))
    assert any("topic None" in o for o in offences(_without(representative(), "topic")))
    assert any("stratum 'extra'" in o for o in offences(representative(stratum="extra")))
    assert any("names the mechanisms" in o for o in offences(representative(stratum="reserve")))
    assert offences(representative(stratum="reserve", mechanisms=["page-cap-crossing"])) == []
    assert any("mechanisms must be a list" in o for o in offences(representative(mechanisms=["", 3])))


def _without(doc, key):
    del doc[key]
    return doc


def test_text_attachments_declare_a_charset_python_can_name_and_legacy_records_are_exempt():
    bare = representative()
    del bare["attachments"][1]["charset"]
    assert any("html attachment declares its charset" in o for o in offences(bare))
    unknown = representative()
    unknown["attachments"][1]["charset"] = "windows-9999"
    assert any("not a codec Python knows" in o for o in offences(unknown))
    legacy_1990s = representative()
    legacy_1990s["attachments"][1]["charset"] = "windows-1258"
    assert offences(legacy_1990s) == [], "an authentic legacy encoding is declared, never converted"
    assert offences(good(bytes_format="wikitext", bytes_url="https://archive.org/download/x/x.wikitext")) == [], \
        "a legacy-shape record carries no charset until the recipe lane rewrites it"
    assert any("charset must be a non-empty" in o for o in offences(good(charset=""))), \
        "an empty charset is the bare-text/plain defect written down"


def test_same_subject_is_a_work_relation_and_translation_is_not_its_synonym():
    linked = representative(work_relations=[{"type": "same-subject", "target": "other-work"}])
    assert offences(linked) == []
    assert any("unknown" in o for o in offences(representative(work_relations=[{"type": "interlanguage", "target": "other-work"}])))


def test_record_only_parents_carry_no_attachment_and_empty_attachment_lists_need_the_flag():
    assert any("unless the record is record_only" in o for o in offences(representative(attachments=[])))
    assert offences(representative(attachments=[], record_only=True)) == []
    assert any("carries no attachments" in o for o in offences(representative(record_only=True)))
    assert any("record_only must be a boolean" in o for o in offences(representative(attachments=[], record_only="yes")))


def test_citation_language_field_retained_reason_and_notes_have_their_shapes():
    assert offences(representative(citation={"doi": "10.1000/x", "isbn": "978-0", "url": "https://example.org"},
                                   language_field="", retained_reason="carries the only DjVu")) == []
    assert any("citation must be an object" in o for o in offences(representative(citation={"pmid": "1"})))
    assert any("citation values" in o for o in offences(representative(citation={"doi": ""})))
    assert any("language_field is the exact string" in o for o in offences(representative(language_field=None)))
    assert any("retained_reason is empty" in o for o in offences(representative(retained_reason=" ")))
    assert offences(representative(notes=[{"id": "note-a", "html": "<p>a</p>"}])) == []
    assert any("exactly id and html" in o for o in offences(representative(notes=[{"id": "note-a"}])))
    assert any("not a lowercase slug" in o for o in offences(representative(notes=[{"id": "Note A", "html": "<p>a</p>"}])))
    twin = representative(id="other-work", work_id="other-work", notes=[{"id": "note-a", "html": "<p>b</p>"}])
    twin["attachments"] = []
    twin["record_only"] = True
    assert any("not globally unique" in o for o in offences(representative(notes=[{"id": "note-a", "html": "<p>a</p>"}]), twin))


def test_content_type_declared_min_body_chars_and_encoding_note_are_checked_when_present():
    lying = representative()
    lying["attachments"][0]["content_type_declared"] = "text/html"
    assert offences(lying) == []
    lying["attachments"][0]["content_type_declared"] = "html"
    assert any("content_type_declared must be a bare MIME type" in o for o in offences(lying))
    # A parameter is refused: Zotero copies the upload's content type onto the item, so
    # 'text/html; charset=…' became the item's content type on the 2026-09-06 padme run.
    lying["attachments"][0]["content_type_declared"] = "text/html; charset=windows-1252"
    assert any("content_type_declared must be a bare MIME type" in o for o in offences(lying))
    short = representative()
    short["attachments"][1]["min_body_chars"] = -1
    assert any("min_body_chars" in o for o in offences(short))
    short["attachments"][1]["min_body_chars"] = 200
    short["attachments"][1]["encoding_note"] = "served as-is by the archive"
    assert offences(short) == []


def test_archives_are_data_and_a_dropped_archive_is_refused_on_the_ruled_shape():
    entries = json.loads((FIXTURES / "archives.json").read_text(encoding="utf-8"))["archives"]
    by_name = {entry["name"]: entry for entry in entries}
    assert set(by_name) == fr.ADMITTED_ARCHIVES | set(fr.DROPPED_ARCHIVES)
    assert by_name["gallica"]["dropped"] is True and "2026-09-04" in by_name["gallica"]["dropped_reason"]
    for name in fr.ADMITTED_ARCHIVES:
        probe = by_name[name]["admission"]
        assert {"date", "robot_open", "licence", "reputable", "byte_exact", "age"} <= set(probe), name
        assert all(isinstance(probe[leg], str) and probe[leg].strip() for leg in probe), name
    assert fr.FAOLEX_ADMITTED == frozenset({"LEX-FAOC179224"})
    assert fr.VERSIONED_ARCHIVES == frozenset({"hal", "arxiv", "zenodo"})
    gallica = representative()
    gallica["attachments"][0].update(archive="gallica", identifier="ark:/12148/bpt6k1",
                                     bytes_url="https://gallica.bnf.fr/ark:/12148/bpt6k1.pdf")
    assert any("archive 'gallica' was dropped" in o for o in offences(gallica))
    legacy = good(archive="gallica", identifier="ark:/12148/bpt6k1", bytes_url="https://gallica.bnf.fr/ark:/12148/bpt6k1.pdf",
                  sha256=None, sha256_reason="ALTCHA challenge")
    assert offences(legacy) == [], "tolerated on the legacy shape until the recipe lane retires it"


def test_a_dropped_archive_is_never_fetched(tmp_path):
    row = fr.fetch_one({"id": "old-gallica", "archive": "gallica", "bytes_url": "https://gallica.bnf.fr/x.pdf",
                        "sha256": None}, tmp_path, timeout=1)
    assert row["status"] == "dropped-archive" and "2026-09-04" in row["reason"]
    assert fr.exit_status([row]) == 0 and not list(tmp_path.iterdir())


def test_wikipedia_is_an_admitted_archive_pinned_by_language_title_and_oldid():
    article = dict(archive="wikipedia", identifier="vi:Kinh_tế_học@12345678", bytes_format="wikitext",
                   bytes_url="https://vi.wikipedia.org/w/index.php?title=Kinh_t%E1%BA%BF_h%E1%BB%8Dc&oldid=12345678&action=raw")
    assert offences(good(**article)) == []
    assert any("does not match" in o for o in offences(good(**(article | {"identifier": "Kinh_tế_học"}))))
    assert any("does not match" in o for o in offences(good(**(article | {"identifier": "vi:Kinh_tế_học"}))))
    assert any("does not belong to archive" in o for o in offences(good(**(article | {"bytes_url": "https://vi.wikisource.org/x"}))))


def test_widened_formats_carry_their_magic_and_text_decodes_under_its_declared_charset(tmp_path):
    assert {"docx", "xlsx", "odt", "zip"} <= {f for f, m in fr.MAGIC.items() if m == b"PK"}
    assert (fr.MAGIC["rtf"], fr.MAGIC["jpg"], fr.MAGIC["png"], fr.MAGIC["tgz"], fr.MAGIC["md"]) == (
        b"{\\rtf", b"\xff\xd8", b"\x89PNG", b"\x1f\x8b", None)
    legacy = tmp_path / "legacy.txt"
    legacy.write_bytes("\u042d\u043a\u043e\u043d\u043e\u043c\u0438\u043a\u0430 \u0440\u0438\u0441\u043a\u0430".encode("koi8-r"))
    assert fr.validate_download_format(legacy, "txt", "koi8-r") is None
    assert "UTF-8" in fr.validate_download_format(legacy, "txt")
    assert "unknown charset" in fr.validate_download_format(legacy, "txt", "windows-9999")
    md = tmp_path / "note.md"
    md.write_text("# heading\n", encoding="utf-8")
    assert fr.validate_download_format(md, "md") is None
