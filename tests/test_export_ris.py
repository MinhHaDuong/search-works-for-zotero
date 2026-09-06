"""export_ris.py writes what Zotero's RIS importer reads back as the fixture.

Ticket 0721. Each assertion here is pinned to a line of Zotero's own RIS
translator (zotero/translators RIS.js) or of its import path
(translate_item.js), read in the import direction: the type each `TY` creates,
the single-field creator a comma-less `AU` becomes, the `LA` an empty language
field must not emit, `M2` landing in Extra, one child note per `N1`, and the
relative `L1` path the item saver resolves against the RIS file. The package
tests prove the sha256 gate refuses before a byte is copied, and the round trip
parses the emitted text with a reader written from the RIS line grammar RIS.js
uses (`^([A-Z][A-Z0-9]) {1,2}-(?: (.*))?$`), so a formatting slip that Zotero
would drop silently fails here instead.
"""

import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "bench" / "fixtures"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, FIXTURES / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


er = load("export_ris", "export_ris.py")

SHA_A = hashlib.sha256(b"a").hexdigest()
SHA_B = hashlib.sha256(b"b").hexdigest()

RIS_LINE = re.compile(r"^([A-Z][A-Z0-9]) {1,2}-(?: (.*))?$")


def parse_ris(text: str) -> list[dict[str, list[str]]]:
    """A tiny reader: records split on ER, tag -> values in order. Lines that do
    not match the RIS grammar are a failure, not a continuation."""
    assert text.startswith("﻿")
    body = text[1:]
    records, current = [], None
    for line in body.split("\r\n"):
        if line == "":
            continue
        match = RIS_LINE.match(line)
        assert match, f"not a RIS line: {line!r}"
        tag, value = match.group(1), match.group(2) or ""
        if tag == "TY":
            assert current is None, "TY inside an open record"
            current = {"TY": [value]}
        elif tag == "ER":
            assert current is not None
            records.append(current)
            current = None
        else:
            assert current is not None, f"{tag} outside a record"
            current.setdefault(tag, []).append(value)
    assert current is None, "unterminated record"
    return records


def legacy_record(**overrides) -> dict:
    doc = {
        "id": "walras-1900-elements",
        "title": "Éléments d'économie politique pure",
        "author": "Léon Walras",
        "year": 1900,
        "language": "fr",
        "tier": "MUST",
        "facet": "core",
        "archive": "internet-archive",
        "identifier": "elementsdeconomi00walr",
        "bytes_url": "https://archive.org/download/elementsdeconomi00walr/elementsdeconomi00walr.pdf",
        "bytes_format": "pdf",
        "sha256": SHA_A,
        "license_basis": "Public domain.",
        "notes": "Byte-identical to the closed PR's library copy.",
    }
    doc.update(overrides)
    return doc


def attachments_record(**overrides) -> dict:
    doc = {
        "id": "keynes-1921-treatise-on-probability",
        "title": "A Treatise on Probability",
        "author": "John Maynard Keynes",
        "year": 1921,
        "language": "en",
        "tier": "MUST",
        "facet": "core",
        "item_type": "book",
        "type_fidelity": "correct",
        "work_id": "keynes-1921-treatise-on-probability",
        "work_relations": [{"type": "same-subject", "work_id": "keynes-1921-wikipedia-en"}],
        "structural_features": [],
        "topic": "uncertainty",
        "stratum": "core",
        "language_field": "",
        "mechanisms": [],
        "citation": {"url": "https://archive.org/details/treatiseonprobab00keyn", "isbn": "978-0-00-000000-1"},
        "notes": [{"id": "keynes-note-1", "html": "<p>Read <b>chapter</b> XII.</p>\n<p>Second paragraph.</p>"}],
        "license_basis": "Public domain.",
        "attachments": [
            {"id": "keynes-1921-treatise-on-probability-pdf", "language": "en", "role": "primary",
             "relation": "primary", "selection_expectation": "indexed", "archive": "internet-archive",
             "identifier": "treatiseonprobab00keyn", "bytes_url": "https://archive.org/x.pdf",
             "bytes_format": "pdf", "sha256": SHA_A, "license_basis": "same as parent", "charset": None},
            {"id": "keynes-1921-treatise-on-probability-txt", "language": "en", "role": "alternate-format",
             "relation": "same-text-different-format", "selection_expectation": "skipped-first-with-text",
             "skip_reason": "second en attachment", "archive": "internet-archive",
             "identifier": "treatiseonprobab00keyn", "bytes_url": "https://archive.org/x.txt",
             "bytes_format": "txt", "sha256": SHA_B, "license_basis": "same as parent", "charset": "utf-8"},
        ],
    }
    doc.update(overrides)
    return doc


def record_only(**overrides) -> dict:
    doc = attachments_record(id="census-record-only", title="A record with no file", attachments=[],
                             record_only=True, notes=[], citation={"doi": "10.1000/xyz123"},
                             item_type="journalArticle", language_field="Français")
    doc.update(overrides)
    return doc


def tags_of(doc, key=None):
    return dict(er.record_tags(doc, key))


# --- TY: Zotero's own maps, in the import direction ------------------------------------

@pytest.mark.parametrize("item_type,ty", [
    ("journalArticle", "JOUR"), ("book", "BOOK"), ("bookSection", "CHAP"), ("report", "RPRT"),
    ("thesis", "THES"), ("conferencePaper", "CONF"), ("webpage", "ELEC"), ("encyclopediaArticle", "ENCYC"),
    ("statute", "STAT"), ("presentation", "SLIDE"), ("map", "MAP"), ("dataset", "DATA"),
    ("letter", "PCOMM"), ("manuscript", "MANSCPT"), ("newspaperArticle", "NEWS"),
    ("magazineArticle", "MGZN"), ("blogPost", "BLOG"),
])
def test_ty_round_trips_through_zotero_for_types_with_their_own_tag(item_type, ty):
    assert er.ris_type(item_type) == (ty, item_type)


def test_document_and_unknown_types_fall_to_gen_which_imports_as_journal_article():
    # RIS.js: degenerateExportTypeMap.document = "GEN"; DEFAULT_IMPORT_TYPE = "journalArticle";
    # preprint has no entry in either map.
    assert er.ris_type("document") == ("GEN", "journalArticle")
    assert er.ris_type("preprint") == ("GEN", "journalArticle")
    losses = er.type_losses([legacy_record(), attachments_record(item_type="preprint"), attachments_record()])
    assert losses == {"document": ("GEN", "journalArticle", 1), "preprint": ("GEN", "journalArticle", 1)}


# --- one record per shape ---------------------------------------------------------------

def test_legacy_record_is_its_own_attachment_with_archive_fields():
    tags = tags_of(legacy_record(), key="WDHDGA89")
    assert tags["TY"] == "GEN" and tags["ID"] == "WDHDGA89"
    assert tags["TI"] == "Éléments d'économie politique pure"
    assert tags["AU"] == "Léon Walras"  # no comma: a single-field creator, as the harness injects it
    assert tags["PY"] == "1900" and "DA" not in tags
    assert tags["LA"] == "fr"
    assert tags["UR"].startswith("https://archive.org/download/")
    assert tags["DB"] == "internet-archive" and tags["AN"] == "elementsdeconomi00walr"
    assert tags["KW"] == "zoteus-golden-source:walras-1900-elements"
    assert tags["L1"] == "attachments/walras-1900-elements.pdf"
    # the legacy `notes` string is recipe prose, not a child note
    assert "N1" not in tags


def test_attachments_record_links_every_pinned_attachment_and_carries_notes_and_citation():
    pairs = er.record_tags(attachments_record())
    tags = {}
    for tag, value in pairs:
        tags.setdefault(tag, []).append(value)
    assert tags["TY"] == ["BOOK"]
    assert tags["L1"] == ["attachments/keynes-1921-treatise-on-probability-pdf.pdf",
                          "attachments/keynes-1921-treatise-on-probability-txt.txt"]
    assert tags["SN"] == ["978-0-00-000000-1"]
    assert tags["UR"] == ["https://archive.org/details/treatiseonprobab00keyn"]
    assert "DB" not in tags and "AN" not in tags
    assert tags["M2"] == [
        "ticket-0029 recipe id: keynes-1921-treatise-on-probability",
        "ticket-0029 work id: keynes-1921-treatise-on-probability",
        "ticket-0029 type fidelity: correct",
        'ticket-0029 work relations: [{"type":"same-subject","work_id":"keynes-1921-wikipedia-en"}]',
        "ticket-0029 topic: uncertainty",
        "ticket-0029 stratum: core",
        "ticket-0029 mechanisms: []",
    ]
    # one N1 per note, HTML kept (RIS.js stores a value with tags as-is), folded to one line
    assert tags["N1"] == ["<p>Read <b>chapter</b> XII.</p> <p>Second paragraph.</p>"]


def test_record_only_parent_gets_no_l1_and_carries_its_doi():
    tags = tags_of(record_only())
    assert tags["TY"] == "JOUR"
    assert "L1" not in tags
    assert tags["DO"] == "10.1000/xyz123"
    assert "N1" not in tags


def test_isbn_goes_to_extra_where_sn_would_import_as_something_else():
    # RIS.js fieldMap.SN: ISSN on journalArticle/magazineArticle/newspaperArticle, reportNumber on
    # report; golden_fixture.py writes such an ISBN to Extra as `ISBN: ...`, and so does the RIS
    for item_type in ("journalArticle", "report", "newspaperArticle"):
        pairs = er.record_tags(record_only(item_type=item_type, citation={"isbn": "978-0-00-000000-1"}))
        tags = dict(pairs)
        assert "SN" not in tags, item_type
        assert [v for t, v in pairs if t == "M2"][-1] == "ISBN: 978-0-00-000000-1"
    # a legacy `document` imports as journalArticle (GEN) and never carries an ISBN, its URL is UR
    assert tags_of(legacy_record())["UR"].startswith("https://archive.org/")
    # on a book SN reads back as ISBN and stays a field, after the ticket-0029 Extra lines
    pairs = er.record_tags(attachments_record())
    assert dict(pairs)["SN"] == "978-0-00-000000-1"
    assert not any(v.startswith("ISBN:") for t, v in pairs if t == "M2")


def test_an_author_with_a_comma_is_emitted_as_given_and_warned_about(caplog):
    # RIS.js case "creators": lastName = text before the first comma, firstName = the rest.
    # The fixture holds one single-field name; the RIS cannot say so, so the value is kept
    # and the loss is logged. Three records of the 2026-09-06 recipe carry such a name.
    author = "Albert Einstein and Hermann Minkowski, translated by M. N. Saha and S. N. Bose"
    with caplog.at_level("WARNING", logger="export_ris"):
        tags = tags_of(legacy_record(author=author))
    assert tags["AU"] == author
    assert any("comma" in record.message for record in caplog.records)
    caplog.clear()
    with caplog.at_level("WARNING", logger="export_ris"):
        tags_of(legacy_record(author="Nguyễn Du; Abel des Michels (ed.)"))  # a semicolon is not split
    assert not caplog.records


def test_unpinned_attachment_gets_no_l1():
    tags = tags_of(legacy_record(sha256=None, sha256_reason="blocked"))
    assert "L1" not in tags


def test_full_date_emits_da_in_ris_form():
    tags = tags_of(attachments_record(date="2017-04-11"))
    assert tags["PY"] == "1921" and tags["DA"] == "2017/04/11/"
    assert tags_of(attachments_record(date="2017-04"))["DA"] == "2017/04//"


# --- LA faithfulness ---------------------------------------------------------------------

def test_language_field_is_emitted_verbatim_and_omitted_when_empty():
    # language_field "" is the census's own defect: no LA, so the import leaves the field empty
    assert "LA" not in tags_of(attachments_record(language_field=""))
    assert "LA" not in tags_of(attachments_record(language_field="   "))
    # a malformed spelling on purpose is reproduced, never normalised
    assert tags_of(attachments_record(language_field="Français"))["LA"] == "Français"
    assert tags_of(attachments_record(language_field="en-US"))["LA"] == "en-US"
    # only when the record carries no language_field does the declared language stand in
    doc = attachments_record()
    del doc["language_field"]
    assert tags_of(doc)["LA"] == "en"


# --- export: keys and ordering -----------------------------------------------------------

def test_export_supplies_keys_and_order(tmp_path):
    items = [
        {"key": "ATT00001", "version": 1, "data": {"key": "ATT00001", "itemType": "attachment", "parentItem": "KEY00002",
                                                    "tags": [{"tag": "zoteus-golden-attachment:x"}]}},
        {"key": "KEY00002", "version": 1, "data": {"key": "KEY00002", "itemType": "document",
                                                    "tags": [{"tag": "zoteus-golden-source:keynes-1921-treatise-on-probability"}]}},
        {"key": "KEY00001", "version": 1, "data": {"key": "KEY00001", "itemType": "document",
                                                    "tags": [{"tag": "zoteus-golden-source:walras-1900-elements"}]}},
    ]
    (tmp_path / "items.json").write_text(json.dumps(items), encoding="utf-8")
    keys = er.load_export_keys(tmp_path)
    assert keys == {"keynes-1921-treatise-on-probability": "KEY00002", "walras-1900-elements": "KEY00001"}
    recipe = [legacy_record(), record_only(), attachments_record()]
    records = parse_ris(er.render(recipe, keys))
    assert [r["KW"][0] for r in records] == [
        "zoteus-golden-source:keynes-1921-treatise-on-probability",
        "zoteus-golden-source:walras-1900-elements",
        "zoteus-golden-source:census-record-only",
    ]
    assert records[0]["ID"] == ["KEY00002"] and records[1]["ID"] == ["KEY00001"] and "ID" not in records[2]


def test_missing_export_means_no_keys_and_recipe_order(tmp_path):
    assert er.load_export_keys(tmp_path / "absent") == {}
    records = parse_ris(er.render([attachments_record(), legacy_record()], {}))
    assert [r["TY"] for r in records] == [["BOOK"], ["GEN"]]
    assert all("ID" not in r for r in records)


# --- round trip ---------------------------------------------------------------------------

def test_round_trip_through_a_reader_reproduces_every_record():
    recipe = [legacy_record(), attachments_record(), record_only()]
    text = er.render(recipe, {"walras-1900-elements": "WDHDGA89"})
    assert "\n" not in text.replace("\r\n", "")  # CRLF only
    records = parse_ris(text)
    assert len(records) == 3
    for doc, record in zip(recipe, records):
        expected = {}
        for tag, value in er.record_tags(doc, "WDHDGA89" if doc["id"] == "walras-1900-elements" else None):
            expected.setdefault(tag, []).append(value)
        assert record == expected


def test_written_file_starts_with_the_utf8_bom(tmp_path):
    destination = tmp_path / "out" / "menagerie.ris"
    er.write_ris(er.render([legacy_record()], {}), destination)
    raw = destination.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    assert "Éléments" in raw.decode("utf-8-sig")


def test_attachment_id_must_be_a_safe_file_name():
    with pytest.raises(er.ExportRisError):
        er.record_tags(legacy_record(id="../escape"))


# --- package ------------------------------------------------------------------------------

def make_cache(tmp_path, contents: dict[str, bytes]) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    for name, data in contents.items():
        (cache / name).write_bytes(data)
    return cache


def test_package_holds_the_ris_and_verified_bytes_beside_it(tmp_path):
    recipe = [legacy_record(), attachments_record(), record_only()]
    cache = make_cache(tmp_path, {
        "walras-1900-elements.pdf": b"a",
        "keynes-1921-treatise-on-probability-pdf.pdf": b"a",
        "keynes-1921-treatise-on-probability-txt.txt": b"b",
    })
    text = er.render(recipe, {})
    target = tmp_path / "out" / "menagerie.zip"
    assert er.build_package(recipe, text, "menagerie.ris", cache, target) == 3
    with zipfile.ZipFile(target) as archive:
        names = sorted(archive.namelist())
        assert names == sorted([
            "menagerie.ris", "IMPORT.txt",
            "attachments/walras-1900-elements.pdf",
            "attachments/keynes-1921-treatise-on-probability-pdf.pdf",
            "attachments/keynes-1921-treatise-on-probability-txt.txt",
        ])
        assert archive.read("menagerie.ris").decode("utf-8") == text
        assert archive.read("attachments/keynes-1921-treatise-on-probability-txt.txt") == b"b"
        # every L1 in the RIS resolves inside the zip
        for record in parse_ris(text):
            for link in record.get("L1", []):
                assert link in names
    assert not list((tmp_path / "out").glob("*.part"))


def test_package_refuses_a_hash_mismatch_and_leaves_nothing_behind(tmp_path):
    recipe = [legacy_record()]
    cache = make_cache(tmp_path, {"walras-1900-elements.pdf": b"not a"})
    target = tmp_path / "out" / "menagerie.zip"
    with pytest.raises(er.ExportRisError, match="sha256 mismatch"):
        er.build_package(recipe, er.render(recipe, {}), "menagerie.ris", cache, target)
    assert not target.exists()
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_package_refuses_a_missing_file(tmp_path):
    recipe = [attachments_record()]
    cache = make_cache(tmp_path, {"keynes-1921-treatise-on-probability-pdf.pdf": b"a"})
    target = tmp_path / "menagerie.zip"
    with pytest.raises(er.ExportRisError, match="missing"):
        er.build_package(recipe, er.render(recipe, {}), "menagerie.ris", cache, target)
    assert not target.exists()


def test_package_refuses_a_symlinked_cache_file(tmp_path):
    recipe = [legacy_record()]
    cache = make_cache(tmp_path, {})
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"a")
    (cache / "walras-1900-elements.pdf").symlink_to(outside)
    with pytest.raises(er.ExportRisError, match="regular file"):
        er.verify_package_inputs(recipe, cache)


def test_package_skips_unpinned_and_record_only(tmp_path):
    recipe = [legacy_record(sha256=None, sha256_reason="blocked"), record_only()]
    cache = make_cache(tmp_path, {})
    target = tmp_path / "menagerie.zip"
    assert er.build_package(recipe, er.render(recipe, {}), "menagerie.ris", cache, target) == 0
    with zipfile.ZipFile(target) as archive:
        assert sorted(archive.namelist()) == ["IMPORT.txt", "menagerie.ris"]


# --- the committed RIS is the current recipe and export ---------------------------------------

def test_committed_menagerie_ris_is_regenerable():
    """The committed file is what `make menagerie-ris` writes from the committed
    recipe and export; a recipe or export change without a regeneration fails here."""
    committed = FIXTURES / "export" / "menagerie.ris"
    assert committed.is_file(), "run `make menagerie-ris`"
    recipe = er.load_recipe(FIXTURES / "recipe.json")
    keys = er.load_export_keys(FIXTURES / "export")
    assert committed.read_bytes().decode("utf-8") == er.render(recipe, keys)


def test_cli_main_writes_the_ris_and_returns_zero(tmp_path):
    recipe_file = tmp_path / "recipe.json"
    recipe_file.write_text(json.dumps([legacy_record()]), encoding="utf-8")
    out = tmp_path / "menagerie.ris"
    assert er.main(["--recipe", str(recipe_file), "--no-export", "--ris", str(out)]) == 0
    # read_bytes, not read_text: universal newlines would fold the CRLF the file must carry
    assert parse_ris(out.read_bytes().decode("utf-8"))[0]["TY"] == ["GEN"]


def test_cli_main_returns_one_on_a_refused_package(tmp_path):
    recipe_file = tmp_path / "recipe.json"
    recipe_file.write_text(json.dumps([legacy_record()]), encoding="utf-8")
    cache = make_cache(tmp_path, {"walras-1900-elements.pdf": b"wrong"})
    out = tmp_path / "menagerie.ris"
    code = er.main(["--recipe", str(recipe_file), "--no-export", "--ris", str(out),
                    "--cache-dir", str(cache), "--package", str(tmp_path / "pkg.zip")])
    assert code == 1
    assert not (tmp_path / "pkg.zip").exists()
