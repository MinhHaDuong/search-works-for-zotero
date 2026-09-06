"""Positive control for the ticket-0711 library census.

The census turns a Zotero library into marginal distributions. Before it is
pointed at the author's real library it has to be shown to react: a fixture API
whose composition is known by construction, and assertions that fail against an
aggregator that always answers one way.

Two properties are load-bearing beyond the counts and are tested apart:

- **read-only** — the one network call site builds a GET and nothing else, the
  SQLite supplement opens an immutable handle, and a real HTTP server in the
  integration tier records that every request it saw was a GET;
- **aggregate-only** — no key, title, file name or note text reaches the artifact.
"""

import http.server
import json
import sqlite3
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

import library_census as lc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
BASE = "http://zotero.test/api/"
STATUS = "http://zotero.test/search-works/fulltext/status"

# ---------------------------------------------------------------- the fixture library

TITLES = {
    "RRRRRRR1": "Abatement cost under discounting",
    "RRRRRRR2": "Économie de l'énergie",
    "RRRRRRR3": "Kinh tế năng lượng Việt Nam",
    "RRRRRRR4": "経済学の基礎",
}


def _item(key, item_type, parent=None, meta=None, **data):
    d = {"key": key, "itemType": item_type, "tags": [], "relations": {}, **data}
    if parent:
        d["parentItem"] = parent
    return {"key": key, "meta": meta or {"numChildren": 0}, "data": d}


PERSONAL_ITEMS = [
    _item("RRRRRRR1", "journalArticle", title=TITLES["RRRRRRR1"], language="en", collections=["C1"],
          abstractNote="x" * 300, tags=[{"tag": "a"}, {"tag": "b"}], date="2015-03-01",
          meta={"parsedDate": "2015-03-01", "numChildren": 3}),
    _item("AAAAAAA1", "attachment", parent="RRRRRRR1", linkMode="imported_file", contentType="application/pdf",
          filename="secret-paper.pdf", title="Full Text PDF"),
    _item("AAAAAAA2", "attachment", parent="RRRRRRR1", linkMode="imported_url", contentType="text/html",
          filename="snapshot.html", title="Snapshot"),
    _item("NNNNNNN1", "note", parent="RRRRRRR1", note="<p>" + "n" * 120 + "</p>"),
    _item("RRRRRRR2", "book", title=TITLES["RRRRRRR2"], language="French", collections=[], date="1998",
          meta={"parsedDate": "1998", "numChildren": 0}),
    _item("RRRRRRR3", "report", title=TITLES["RRRRRRR3"], collections=["C1", "C2"]),
    _item("AAAAAAA3", "attachment", parent="RRRRRRR3", linkMode="linked_url", contentType="", title="Link"),
    _item("RRRRRRR4", "thesis", title=TITLES["RRRRRRR4"], language="vi-VN", collections=["C2"], date="2021",
          meta={"parsedDate": "2021", "numChildren": 1}),
    _item("AAAAAAA4", "attachment", parent="RRRRRRR4", linkMode="linked_file", contentType="application/pdf",
          filename="these.pdf", title="PDF"),
    _item("NNNNNNN2", "note", note="<p>standalone</p>"),
    _item("AAAAAAA5", "attachment", linkMode="imported_file", contentType="application/pdf",
          filename="loose.pdf", title="Loose PDF"),
    # A child whose parent is not in the listing (the parent sits in the trash).
    _item("AAAAAAA6", "attachment", parent="TTTTTTT1", linkMode="imported_file", contentType="application/pdf",
          filename="orphan.pdf", title="Orphan"),
]

TRASH_ITEMS = [
    _item("TTTTTTT1", "book", title="Trashed", deleted=True),
    _item("TTTTTTT2", "attachment", parent="TTTTTTT1", linkMode="imported_file", contentType="application/pdf"),
]

GROUP_ITEMS = [
    _item("GGGGGGG1", "journalArticle", title="Group paper"),
    _item("GGGGGGGA", "attachment", parent="GGGGGGG1", linkMode="linked_file", contentType="application/pdf"),
    _item("GGGGGGGN", "note", parent="GGGGGGG1", note="<p>g</p>"),
]

FULLTEXT = {"AAAAAAA1": 100, "AAAAAAA2": 55, "AAAAAAA4": 0, "AAAAAAA5": 3}
GROUP_FULLTEXT = {"GGGGGGGA": 7}

STATUS_ROWS = {
    "AAAAAAA1": {"state": "partial", "indexedPages": 100, "totalPages": 250, "indexedChars": None, "totalChars": None},
    "AAAAAAA2": {"state": "indexed", "indexedPages": None, "totalPages": None, "indexedChars": 5000, "totalChars": 5000},
    "AAAAAAA4": {"state": "unindexed", "indexedPages": None, "totalPages": None, "indexedChars": None, "totalChars": None},
    "AAAAAAA5": {"state": "indexed", "indexedPages": 12, "totalPages": 12, "indexedChars": None, "totalChars": None},
    "AAAAAAA6": {"state": "unavailable", "indexedPages": None, "totalPages": None, "indexedChars": None, "totalChars": None},
}

HEADERS = {
    "x-zotero-version": "10.0.1", "zotero-api-version": "3",
    "zotero-schema-version": "44", "last-modified-version": "1257",
}


def route(url: str) -> tuple[dict[str, str], bytes]:
    """The fixture API. Raises on anything it does not serve, like the real one."""
    parsed = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(parsed.query))
    path = parsed.path
    if path.endswith("/fulltext/status"):
        keys = [k for k in q.get("keys", "").split(",") if k]
        rows = [{"key": k, **STATUS_ROWS[k]} if k in STATUS_ROWS else {"key": k, "error": "not found"} for k in keys]
        return {}, json.dumps({"busy": False, "running": 0, "items": rows}).encode()
    listings = {
        "/api/users/0/items": PERSONAL_ITEMS,
        "/api/users/0/items/trash": TRASH_ITEMS,
        "/api/groups/305258/items": GROUP_ITEMS,
        "/api/groups/305258/items/trash": [],
    }
    censuses = {"/api/users/0/fulltext": FULLTEXT, "/api/groups/305258/fulltext": GROUP_FULLTEXT}
    if path in censuses:
        assert q.get("since") == "0", "the local API rejects a fulltext census without since="
        return HEADERS, json.dumps(censuses[path]).encode()
    if path in listings:
        rows = listings[path]
        start, limit = int(q.get("start", 0)), int(q.get("limit", 25))
        headers = {**HEADERS, "total-results": str(len(rows))}
        if q.get("format") == "keys":
            return headers, "\n".join(r["key"] for r in rows[start:start + limit]).encode()
        return headers, json.dumps(rows[start:start + limit]).encode()
    raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)


class Recorder:
    """A fetch that serves the fixture and remembers every URL it was asked for."""

    def __init__(self):
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        return route(url)


def _args(**overrides):
    ns = lc.build_parser().parse_args([])
    ns.base_url = BASE
    ns.status_url = STATUS
    ns.include_group = [305258]
    ns.page_size = 5
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


def _items():
    return [{**it["data"], "_meta": it["meta"]} for it in PERSONAL_ITEMS]


# ---------------------------------------------------------------- item marginals


def test_item_marginals_recover_the_known_mix():
    m = lc.item_marginals(_items())
    assert m["items_total"] == 12
    assert m["top_level_records"] == 4
    assert m["item_types"] == {"journalArticle": 1, "book": 1, "report": 1, "thesis": 1}
    assert m["standalone_attachments"] == 1
    assert m["standalone_notes"] == 1
    assert m["orphan_children"] == 1, "a child of a trashed parent is not folded into any record"
    assert m["top_level_total"] == 6


def test_attachments_per_record_includes_zero():
    m = lc.item_marginals(_items())
    assert m["attachments_per_record"] == {"0": 1, "1": 2, "2": 1}
    assert m["pdf_attachments_per_record"] == {"0": 2, "1": 2}
    assert m["attachments_per_record_quantiles"]["n"] == 4
    assert m["attachments_per_record_quantiles"]["max"] == 2
    by_type = m["records_by_type_and_attachment"]
    assert by_type["report"] == {"items": 1, "with_any_attachment": 1, "with_pdf": 0, "with_note": 0}
    assert by_type["journalArticle"]["with_note"] == 1


def test_attachment_format_marginals():
    a = lc.item_marginals(_items())["attachments"]
    assert a["total"] == 6 and a["child"] == 5
    assert a["content_type"] == {"application/pdf": 4, "text/html": 1, "": 1}
    assert a["link_mode"] == {"imported_file": 3, "imported_url": 1, "linked_url": 1, "linked_file": 1}
    assert a["content_type_by_link_mode"]["application/pdf"] == {"imported_file": 3, "linked_file": 1}


def test_notes_language_collections_and_records():
    m = lc.item_marginals(_items())
    assert m["notes"] == {
        "total": 2, "child": 1, "standalone": 1, "per_record": {"0": 3, "1": 1},
        "records_with_notes": 1,
        "length_chars_quantiles": m["notes"]["length_chars_quantiles"],
    }
    assert m["notes"]["length_chars_quantiles"]["max"] == 127
    assert m["language"]["records_with_language"] == 3
    assert m["language"]["raw"] == {"en": 1, "French": 1, "": 1, "vi-VN": 1}
    assert m["language"]["normalised"] == {"en": 1, "fr": 1, "empty": 1, "vi": 1}
    assert m["collections"]["records_in_collections"] == 3
    assert m["collections"]["records_in_no_collection"] == 1
    assert m["collections"]["collections_per_record"] == {"0": 1, "1": 2, "2": 1}
    r = m["records"]
    assert r["with_abstract"] == 1 and r["with_tags"] == 1 and r["with_date"] == 3
    assert r["decade"] == {"2010s": 1, "1990s": 1, "undated": 1, "2020s": 1}
    assert r["title_script"] == {"latin_ascii": 1, "latin_with_diacritics": 2, "cjk": 1}


@pytest.mark.parametrize("raw,code", [
    ("en", "en"), ("English", "en"), ("en-US", "en"), ("en_GB", "en"), ("fre", "fr"),
    ("Français", "fr"), ("vi-VN", "vi"), ("vie", "vi"), ("", "empty"), ("xx", "xx"),
    ("Klingon", "unmapped"), ("fr; en", "fr"), ("eng, fre", "en"), ("VN", "vi"), ("VN, EN", "vi"),
])
def test_language_normalisation(raw, code):
    assert lc.normalise_language(raw) == code


def test_raw_language_bins_free_text_and_paths():
    """A URL pasted into the language field must not reach the artifact verbatim."""
    assert lc.raw_language(" en-GB ") == "en-GB"
    assert lc.raw_language("http://example.org/some/secret-file.pdf") == "(free text, binned)"
    assert lc.raw_language("C:\\docs\\x") == "(free text, binned)"
    assert lc.raw_language("Report is in English with summaries in six other languages") == "(free text, binned)"
    items = _items()
    items[0]["language"] = "http://example.org/secret-file.pdf"
    text = json.dumps(lc.item_marginals(items))
    assert "secret-file" not in text


@pytest.mark.parametrize("title,klass", [
    ("Plain title", "latin_ascii"), ("Économie", "latin_with_diacritics"),
    ("Tiếng Việt", "latin_with_diacritics"), ("経済学", "cjk"), ("Экономика", "cyrillic"),
    ("Économie / 経済", "latin_plus_cjk"), ("12345 — !", "no_letters"), ("", "no_letters"),
])
def test_title_script_classes(title, klass):
    assert lc.title_script(title) == klass


def test_quantiles_are_nearest_rank():
    q = lc.quantiles(list(range(1, 101)))
    assert (q["min"], q["p10"], q["p50"], q["p90"], q["p99"], q["max"]) == (1, 10, 50, 90, 99, 100)
    assert q["n"] == 100 and q["mean"] == 50.5
    assert lc.quantiles([]) == {"n": 0}
    assert lc.quantiles([7]) == {"n": 1, "min": 7, "p10": 7, "p25": 7, "p50": 7, "p75": 7, "p90": 7,
                                "p99": 7, "max": 7, "mean": 7.0}


# ---------------------------------------------------------------- full text


def test_fulltext_coverage_by_content_type_and_caps():
    attachments = [it for it in _items() if it["itemType"] == "attachment"]
    f = lc.fulltext_marginals(attachments, FULLTEXT, STATUS_ROWS)
    assert f["file_attachments"] == 5, "the linked_url bookmark is not a file"
    assert f["non_file_attachments"] == 1
    pdf = f["by_content_type"]["application/pdf"]
    assert pdf["file_attachments"] == 4
    assert pdf["with_entry"] == 3 and pdf["without_entry"] == 1
    assert pdf["entry_version_zero"] == 1
    assert pdf["state"] == {"partial": 1, "unindexed": 1, "indexed": 1, "unavailable": 1}
    assert f["by_content_type"]["text/html"]["state"] == {"indexed": 1}
    assert f["quantiles"]["totalPages"] == {"n": 2, "min": 12, "p10": 12, "p25": 12, "p50": 12, "p75": 250,
                                            "p90": 250, "p99": 250, "max": 250, "mean": 131.0}
    assert f["quantiles"]["totalChars"]["n"] == 1
    caps = f["caps"]
    assert caps["pages_over_stock_cap"] == 1
    assert caps["pages_truncated_at_stock_cap"] == 1
    assert caps["pages_indexed_beyond_stock_cap"] == 0
    assert caps["pages_partial"] == 1
    assert caps["chars_truncated_at_stock_cap"] == 0


def test_a_lifted_cap_is_not_read_as_a_truncation():
    rows = {"AAAAAAA1": {"state": None, "indexedPages": 250, "totalPages": 250, "indexedChars": None, "totalChars": None}}
    att = [{"key": "AAAAAAA1", "itemType": "attachment", "linkMode": "imported_file", "contentType": "application/pdf"}]
    caps = lc.fulltext_marginals(att, {"AAAAAAA1": 1}, rows)["caps"]
    assert caps["pages_truncated_at_stock_cap"] == 0
    assert caps["pages_indexed_beyond_stock_cap"] == 1
    assert caps["pages_over_stock_cap"] == 1


def test_derived_state_when_no_plugin_state():
    assert lc.derived_state(None) == "no_entry"
    assert lc.derived_state(None, has_entry=True) == "unindexed", "a version-0 row is registered, not absent"
    assert lc.derived_state({"state": None, "indexedPages": 100, "totalPages": 250}) == "partial"
    assert lc.derived_state({"state": None, "indexedChars": 9, "totalChars": 9}) == "indexed"
    assert lc.derived_state({"state": None}) == "unindexed"
    assert lc.derived_state({"state": "queued", "indexedPages": 1, "totalPages": 1}) == "queued"


def test_api_fallback_drops_the_content():
    class Lib:
        def get_json(self, path):
            assert path == "items/AAAAAAA1/fulltext"
            return {"content": "THE FULL TEXT", "indexedPages": 3, "totalPages": 3}
    rows = lc.counters_from_api(Lib(), ["AAAAAAA1"])
    assert rows == {"AAAAAAA1": {"state": None, "indexedPages": 3, "totalPages": 3, "indexedChars": None, "totalChars": None}}
    assert "THE FULL TEXT" not in json.dumps(rows)


# ---------------------------------------------------------------- end to end, over the fake API


def test_run_paginates_and_reports_every_section():
    rec = Recorder()
    doc = lc.run(_args(), fetch=rec)
    assert doc["ticket"] == "0711"
    assert doc["provenance"]["zotero_version"] == "10.0.1"
    assert doc["provenance"]["fulltext_counters_source"] == "plugin"
    assert doc["personal"]["items_total"] == 12
    assert doc["personal"]["trash"] == {"items": 2, "top_level": 1, "children": 1,
                                        "item_types": {"book": 1, "attachment": 1}}
    assert doc["groups"]["305258"] == {
        "items_total": 3, "top_level_records": 1, "attachments": 1,
        "attachment_link_mode": {"linked_file": 1}, "notes": 1, "fulltext_entries": 1, "trash_items": 0,
    }
    assert doc["sqlite"] is None
    # page_size=5 over 12 personal items is three pages, not one.
    pages = [u for u in rec.urls if "/api/users/0/items?" in u]
    assert [dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query))["start"] for u in pages] == ["0", "5", "10"]
    assert all(u.startswith(BASE) or u.startswith(STATUS) for u in rec.urls)


def test_auto_source_falls_back_to_the_api_when_the_plugin_is_absent():
    def no_plugin(url):
        if url.startswith(STATUS):
            raise urllib.error.URLError("no plugin")
        if "/items/AAAAAAA1/fulltext" in url or "/items/AAAAAAA5/fulltext" in url:
            return {}, json.dumps({"content": "TEXT", "indexedPages": 12, "totalPages": 12}).encode()
        if "/items/AAAAAAA2/fulltext" in url:
            return {}, json.dumps({"content": "TEXT", "indexedChars": 5, "totalChars": 5}).encode()
        if "/items/AAAAAAA4/fulltext" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return route(url)
    doc = lc.run(_args(include_group=None), fetch=no_plugin)
    assert doc["provenance"]["fulltext_counters_source"] == "api"
    assert doc["personal"]["fulltext"]["counters_measured"] == 3
    pdf = doc["personal"]["fulltext"]["by_content_type"]["application/pdf"]
    assert pdf["state"] == {"indexed": 2, "unindexed": 1, "no_entry": 1}
    assert "TEXT" not in json.dumps(doc)


def test_artifact_carries_no_key_title_or_filename():
    doc = lc.run(_args(), fetch=Recorder())
    text = json.dumps(doc, ensure_ascii=False)
    for it in PERSONAL_ITEMS + TRASH_ITEMS + GROUP_ITEMS:
        assert it["key"] not in text, it["key"]
        for field in ("title", "filename", "note", "abstractNote"):
            value = it["data"].get(field)
            if value:
                assert value not in text, field


# ---------------------------------------------------------------- read-only


def test_the_one_network_call_site_is_a_get(monkeypatch):
    """Source and runtime both: the module builds no request but a GET."""
    source = (REPO / "bench" / "library_census.py").read_text()
    assert source.count("urlopen(") == 1, "exactly one network call site"
    assert source.count("urllib.request.Request(") == 1
    assert 'method="GET"' in source
    assert "data=" not in source.split("def http_fetch")[1].split("\nclass ")[0]
    for verb in ("PUT", "POST", "PATCH", "DELETE"):
        assert f'"{verb}"' not in source and f"'{verb}'" not in source

    seen = []

    class Response:
        headers = {"X-Zotero-Version": "10.0.1"}

        def read(self):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout=None):
        seen.append(request)
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    headers, body = lc.http_fetch("http://zotero.test/api/users/0/items?limit=1")
    assert len(seen) == 1
    assert seen[0].get_method() == "GET" and seen[0].data is None
    assert headers == {"x-zotero-version": "10.0.1"} and body == b"[]"


def test_sqlite_supplement_is_immutable_and_reads_the_known_rows(tmp_path):
    db = tmp_path / "zotero.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE libraries (libraryID INTEGER PRIMARY KEY, type TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, libraryID INTEGER);
        CREATE TABLE itemAnnotations (itemID INTEGER PRIMARY KEY, type INTEGER);
        CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, libraryID INTEGER);
        CREATE TABLE feedItems (itemID INTEGER PRIMARY KEY);
        INSERT INTO libraries VALUES (1, 'user'), (3, 'group'), (9, 'feed');
        INSERT INTO items VALUES (10, 1), (11, 1), (12, 3), (13, 1), (14, 9);
        INSERT INTO itemAnnotations VALUES (10, 1), (11, 1), (12, 3), (13, 5);
        INSERT INTO deletedItems VALUES (13);
        INSERT INTO collections VALUES (1, 1), (2, 1), (3, 3);
        INSERT INTO feedItems VALUES (14);
    """)
    con.commit()
    con.close()
    before = (db.read_bytes(), sorted(p.name for p in tmp_path.iterdir()))

    assert "mode=ro" in lc.sqlite_uri(db) and "immutable=1" in lc.sqlite_uri(db)
    m = lc.sqlite_marginals(db)
    assert m["feed_libraries"] == 1 and m["feed_items"] == 1
    assert m["annotations_by_library_type"] == {"user": {"highlight": 2}, "group": {"image": 1}}
    assert m["annotations_in_trash"] == 1, "a trashed annotation is counted apart, not folded in"
    assert m["collections_by_library_type"] == {"user": 2, "group": 1}
    assert m["libraries_by_type"] == {"user": 1, "group": 1, "feed": 1}

    after = (db.read_bytes(), sorted(p.name for p in tmp_path.iterdir()))
    assert before == after, "no byte changed and no journal or WAL file appeared"


# ---------------------------------------------------------------- integration: a real server


class _Handler(http.server.BaseHTTPRequestHandler):
    methods: list[str] = []

    def log_message(self, *a):  # keep pytest output clean
        pass

    def _serve(self):
        type(self).methods.append(self.command)
        try:
            headers, body = route("http://zotero.test" + self.path)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            return
        self.send_response(200)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _serve
    do_POST = _serve
    do_PUT = _serve
    do_PATCH = _serve
    do_DELETE = _serve


@pytest.mark.integration
def test_cli_against_a_real_server_issues_only_gets(tmp_path):
    _Handler.methods = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        out = tmp_path / "census.json"
        p = subprocess.run(
            [sys.executable, str(REPO / "bench" / "library_census.py"),
             "--base-url", f"http://127.0.0.1:{port}/api/",
             "--status-url", f"http://127.0.0.1:{port}/search-works/fulltext/status",
             "--include-group", "305258", "--output", str(out)],
            capture_output=True, text=True, timeout=60,
        )
    finally:
        server.shutdown()
    assert p.returncode == 0, p.stderr
    doc = json.loads(out.read_text())
    assert doc["personal"]["item_types"] == {"journalArticle": 1, "book": 1, "report": 1, "thesis": 1}
    assert doc["groups"]["305258"]["items_total"] == 3
    assert _Handler.methods and set(_Handler.methods) == {"GET"}, _Handler.methods
    assert not list(out.parent.glob("*.tmp")), "the write-then-rename leaves no scratch file"
