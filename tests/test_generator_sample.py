"""The ticket-0719 sampler against a fixture API whose composition is known.

Three properties beyond the counts, each tested apart:

- **read-only** — the module builds no request of its own; every byte it reads
  passes through the census's one GET call site, and the fixture route records
  every URL it served so a write-shaped path would show;
- **aggregate-only** — the summary carries no key, title, creator, file name or
  paragraph text, checked on its serialised form;
- **honest chain** — each element is flagged measured only when it was: a page
  index only where the text carries form feeds, a printed label only where the
  PDF carries `/PageLabels`, a heading only where the text makes one evident.
"""

import argparse
import importlib
import json
import sys
import urllib.parse
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

S = importlib.import_module("bench.generator.sample")

PROSE_EN = ("The carbon tax was introduced in two thousand and fourteen under the name of the climate "
            "energy contribution, at a rate that rose every year until the protests of two thousand and "
            "eighteen froze it, and the freeze has held since, whatever the successive budgets promised.")
PROSE_FR = ("La taxe carbone a été introduite en France sous le nom de contribution climat-énergie, avec un "
            "taux qui devait croître chaque année jusqu'à ce que les manifestations de deux mille dix-huit "
            "le gèlent, et le gel a tenu depuis malgré les promesses des budgets successifs de l'État.")

SECRET_TITLE = "Abatement cost under discounting"


def _item(key, item_type, parent=None, **data):
    d = {"key": key, "itemType": item_type, "tags": [], "relations": {}, **data}
    if parent:
        d["parentItem"] = parent
    return {"key": key, "meta": {}, "data": d}


ITEMS = [
    _item("RRRRRRR1", "journalArticle", title=SECRET_TITLE, language="en", date="2015-03-01", DOI="10.1000/x1",
          creators=[{"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"}]),
    _item("AAAAAAA1", "attachment", parent="RRRRRRR1", linkMode="imported_file", contentType="application/pdf",
          filename="secret-paper.pdf"),
    _item("RRRRRRR2", "report", title="Rapport annuel", language="fr", date="2020", url="https://example.org/r",
          creators=[{"creatorType": "author", "name": "Agence"}]),
    _item("AAAAAAA2", "attachment", parent="RRRRRRR2", linkMode="imported_url", contentType="text/html"),
    _item("RRRRRRR3", "bookSection", title="Chapter three", bookTitle="The Book", ISBN="978-1",
          creators=[{"creatorType": "editor", "lastName": "Ed"}]),
    _item("AAAAAAA3", "attachment", parent="RRRRRRR3", linkMode="linked_file", contentType="application/pdf",
          path="/nonexistent/chapter.pdf"),
    # No full-text entry: never in the frame.
    _item("RRRRRRR4", "book", title="Unextracted"),
    _item("AAAAAAA4", "attachment", parent="RRRRRRR4", linkMode="imported_file", contentType="application/pdf"),
    # Entry at version 0: registered, nothing extracted, never in the frame.
    _item("RRRRRRR5", "webpage", title="Version zero"),
    _item("AAAAAAA5", "attachment", parent="RRRRRRR5", linkMode="imported_url", contentType="text/html"),
    # A standalone attachment has no record and no chain.
    _item("AAAAAAA6", "attachment", linkMode="imported_file", contentType="application/pdf"),
]

ENTRIES = {"AAAAAAA1": 12, "AAAAAAA2": 7, "AAAAAAA3": 3, "AAAAAAA5": 0, "AAAAAAA6": 4}

FULLTEXT = {
    "AAAAAAA1": {"content": "1 Introduction\n\n" + PROSE_EN + "\f2 Methods\n\n" + PROSE_EN.replace("carbon", "energy") + "\n",
                 "indexedPages": 2, "totalPages": 2},
    "AAAAAAA2": {"content": PROSE_FR + "\n\n" + PROSE_FR.replace("taxe", "prime") + "\n", "indexedChars": 600, "totalChars": 600},
    "AAAAAAA3": {"content": "\n".join([PROSE_EN] * 3), "indexedPages": 1, "totalPages": 1},
    "AAAAAAA6": {"content": PROSE_EN, "indexedPages": 1, "totalPages": 1},
}

HEADERS = {"x-zotero-version": "10.0.1", "last-modified-version": "1257"}

CENSUS = {
    "provenance": {"measured_at": "2026-09-06T10:05:21+00:00", "library_last_modified_version": "1257"},
    "personal": {
        "item_types": {"journalArticle": 50, "report": 30, "bookSection": 10, "webpage": 10},
        "fulltext": {
            "by_content_type": {
                "application/pdf": {"state": {"indexed": 60, "partial": 10, "unindexed": 5}},
                "text/html": {"state": {"indexed": 30}},
                "text/csv": {"state": {"indexed": 1}},
            },
            "quantiles": {"totalChars": {"p25": 100, "p50": 400, "p75": 800}},
        },
    },
}


class Route:
    """The fixture API; records every URL, raises on anything it does not serve."""

    def __init__(self):
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        parsed = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(parsed.query))
        path = parsed.path
        if path == "/api/users/0/items":
            start, limit = int(q.get("start", 0)), int(q.get("limit", 100))
            return HEADERS, json.dumps(ITEMS[start:start + limit]).encode()
        if path == "/api/users/0/fulltext":
            return HEADERS, json.dumps(ENTRIES).encode()
        if path.startswith("/api/users/0/items/") and path.endswith("/fulltext"):
            key = path.split("/")[-2]
            return HEADERS, json.dumps(FULLTEXT[key]).encode()
        raise AssertionError(f"unserved: {url}")


def args(tmp_path, **over):
    census = tmp_path / "census.json"
    census.write_text(json.dumps(CENSUS))
    ns = argparse.Namespace(base_url="http://zotero.test/api/", census=census, n=3, seed=7, scope_keys=None,
                            zotero_data_dir="", fulltext_cap=S.DEFAULT_FULLTEXT_CAP, page_size=100)
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


def test_targets_come_from_the_census():
    t = S.census_targets(CENSUS)
    assert t["type"]["journalArticle"] == 0.5 and t["type"]["other"] == 0.0
    assert t["format"]["pdf"] == pytest.approx(70 / 101) and t["format"]["other"] == pytest.approx(1 / 101)
    assert t["length_cuts_chars"] == (100, 400, 800)


def test_frame_holds_only_extracted_child_attachments_of_records(tmp_path):
    route = Route()
    rows, summary, headers = S.sample(args(tmp_path, n=10), fetch=route)
    keys = {r["attachment_key"] for r in rows}
    assert keys == {"AAAAAAA1", "AAAAAAA2", "AAAAAAA3"}
    assert summary["n"] == 3 and summary["n_requested"] == 10
    assert headers["last-modified-version"] == "1257"


def test_scope_restricts_the_frame(tmp_path):
    scope = tmp_path / "keys.txt"
    scope.write_text("RRRRRRR2\n")
    rows, summary, _ = S.sample(args(tmp_path, n=5, scope_keys=scope), fetch=Route())
    assert [r["item_key"] for r in rows] == ["RRRRRRR2"]
    assert summary["scope_items"] == 1


def test_the_chain_flags_each_element_honestly(tmp_path):
    rows, summary, _ = S.sample(args(tmp_path, n=10), fetch=Route())
    by = {r["attachment_key"]: r for r in rows}
    pdf = by["AAAAAAA1"]["chain"]
    assert pdf["title"]["measured"] and pdf["creators"]["value"] == ["Ada Lovelace"]
    assert pdf["identifier"] == {"value": "10.1000/x1", "kind": "doi", "measured": True}
    assert pdf["page_index"]["measured"] and pdf["page_index"]["value"] in (1, 2)
    assert pdf["page_label"] == {"value": None, "measured": False, "source": "not-measured"}
    assert pdf["section"]["measured"] and pdf["section"]["value"] in ("1 Introduction", "2 Methods")
    html = by["AAAAAAA2"]["chain"]
    assert html["identifier"]["kind"] == "url"
    assert not html["page_index"]["measured"] and not html["section"]["measured"]
    assert by["AAAAAAA2"]["language"] == "fr" and by["AAAAAAA2"]["language_source"] == "text"
    chapter = by["AAAAAAA3"]["chain"]
    assert chapter["compound"] == {"applies": True, "part_title": "Chapter three", "container": "The Book", "measured": True}
    assert not chapter["date"]["measured"] and chapter["identifier"]["kind"] == "isbn"
    assert pdf["compound"]["applies"] is False
    # Only the first PDF's text carries a form feed; the chapter's does not, and
    # the HTML has no pages at all.
    assert summary["chain_measured"]["page_index"] == 1 and summary["chain_not_measured"]["page_index"] == 2
    assert summary["chain_not_measured"]["page_label"] == 3
    assert summary["compound_documents"] == 1 and summary["chain_measured"]["compound_container"] == 1


def test_reachability_reads_the_offset_against_the_cap(tmp_path):
    # A one-character cap puts every paragraph but one starting at offset 0
    # beyond it; the PDF's paragraphs all sit after its heading.
    rows, summary, _ = S.sample(args(tmp_path, n=10, fulltext_cap=1), fetch=Route())
    assert summary["beyond_default_cap"] >= 1 and summary["default_cap_chars"] == 1
    assert all(r["within_default_cap"] == (r["offset"] < 1) for r in rows)
    rows, summary, _ = S.sample(args(tmp_path, n=10), fetch=Route())
    assert summary["beyond_default_cap"] == 0 and summary["within_default_cap"] == 3


def test_summary_is_aggregate_only(tmp_path):
    rows, summary, _ = S.sample(args(tmp_path, n=10), fetch=Route())
    text = json.dumps(summary)
    for secret in (SECRET_TITLE, "Lovelace", "secret-paper", "RRRRRRR1", "AAAAAAA1", PROSE_EN[:40], "10.1000"):
        assert secret not in text
    assert summary["strata"]["format"]["pdf"]["achieved"] == 2
    assert summary["strata"]["type"]["journalArticle"]["target"] == pytest.approx(5.0)
    assert set(summary["language"]["answer"]) == {"en", "fr"}


def test_the_sampler_is_read_only():
    """Source: the module opens no connection of its own and names no write verb.
    Runtime: every URL the fixture served was a listing or a full-text read."""
    source = (REPO / "bench" / "generator" / "sample.py").read_text()
    assert "urlopen(" not in source and "Request(" not in source
    assert "from bench.library_census import" in source and "http_fetch" in source
    for verb in ("PUT", "POST", "PATCH", "DELETE"):
        assert f'"{verb}"' not in source and f"'{verb}'" not in source
    route = Route()
    S.sample(args(Path("/nonexistent")) if False else None, fetch=route) if False else None
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        S.sample(args(Path(d), n=5), fetch=route)
    assert route.urls, "the fixture saw traffic"
    assert all("/items" in u or "/fulltext" in u for u in route.urls)
    assert not any("?" in u and "data" in urllib.parse.urlsplit(u).query for u in route.urls)


def test_deterministic_under_a_seed(tmp_path):
    a, _, _ = S.sample(args(tmp_path, n=3, seed=11), fetch=Route())
    b, _, _ = S.sample(args(tmp_path, n=3, seed=11), fetch=Route())
    assert [(r["attachment_key"], r["offset"]) for r in a] == [(r["attachment_key"], r["offset"]) for r in b]


def test_page_label_reads_the_pdf_page_labels_tree(tmp_path):
    pikepdf = pytest.importorskip("pikepdf")
    path = tmp_path / "labelled.pdf"
    with pikepdf.new() as pdf:
        for _ in range(4):
            pdf.add_blank_page()
        pdf.Root.PageLabels = pikepdf.Dictionary(Nums=pikepdf.Array([
            0, pikepdf.Dictionary(S=pikepdf.Name("/r")),
            2, pikepdf.Dictionary(S=pikepdf.Name("/D"), St=5),
        ]))
        pdf.save(path)
    assert S.page_label(path, 2) == ("ii", "pdf-page-labels")
    assert S.page_label(path, 3) == ("5", "pdf-page-labels")
    assert S.page_label(path, 9) == (None, "not-measured")
    plain = tmp_path / "plain.pdf"
    with pikepdf.new() as pdf:
        pdf.add_blank_page()
        pdf.save(plain)
    assert S.page_label(plain, 1) == (None, "no-page-labels")
    assert S.page_label(None, 1) == (None, "not-measured")
    assert S.page_label(tmp_path / "missing.pdf", 1) == (None, "not-measured")


def test_attachment_file_never_leaves_the_storage_folder(tmp_path):
    folder = tmp_path / "storage" / "AAAAAAA1"
    folder.mkdir(parents=True)
    (folder / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    att = {"key": "AAAAAAA1", "linkMode": "imported_file", "contentType": "application/pdf", "filename": "paper.pdf"}
    assert S.attachment_file(att, tmp_path) == folder / "paper.pdf"
    assert S.attachment_file({**att, "contentType": "text/html"}, tmp_path) is None
    assert S.attachment_file(att, None) is None
    linked = {"key": "L", "linkMode": "linked_file", "contentType": "application/pdf", "path": str(folder / "paper.pdf")}
    assert S.attachment_file(linked, None) == folder / "paper.pdf"
