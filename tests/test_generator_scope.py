"""The scope proxy: a random item sample the target sees as its whole library (ticket 0719).

A fixture upstream stands in for Zotero's local API — a listing that pages with
`Total-Results`, a versions map, a keys listing, the full-text census, a per-item
full text, a groups endpoint — and the proxy is exercised over real sockets, so
what is asserted is what the target would see: filtered listings with a correct
total and correct slices, a filtered census, and everything else passed through
untouched. Read-only is asserted both ways: the proxy's one upstream call site is
a GET, and a POST at the proxy is refused with 405 and never forwarded.
"""

import importlib
import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

scope_mod = importlib.import_module("bench.generator.scope")

pytestmark = pytest.mark.integration


def _item(key, item_type, parent=None, **data):
    d = {"key": key, "itemType": item_type, **data}
    if parent:
        d["parentItem"] = parent
    return {"key": key, "data": d, "meta": {}}


RECORDS = [_item(f"R{i:07d}", "journalArticle", title=f"t{i}") for i in range(12)]
CHILDREN = [_item(f"A{i:07d}", "attachment", parent=f"R{i:07d}", contentType="application/pdf") for i in range(12)]
NOTES = [_item(f"N{i:07d}", "note", parent=f"R{i:07d}", note="n") for i in range(0, 12, 3)]
ITEMS = RECORDS + CHILDREN + NOTES
#: The shape `Library.items()` yields: the data object, flattened.
FLAT = [it["data"] for it in ITEMS]
FULLTEXT = {c["key"]: 5 for c in CHILDREN}


class Upstream(BaseHTTPRequestHandler):
    seen: list[tuple[str, str]] = []

    def log_message(self, *a):
        pass

    def _send(self, status, body, headers=None):
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Upstream.seen.append(("GET", self.path))
        p = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(p.query))
        common = {"Last-Modified-Version": "4242", "X-Zotero-Version": "10.0.1"}
        if p.path in ("/api/users/0/items", "/api/users/0/items/top"):
            rows = RECORDS if p.path.endswith("/top") else ITEMS
            if "itemKey" in q:
                wanted = set(q["itemKey"].split(","))
                assert len(wanted) <= 50, "the itemKey filter is capped at fifty keys"
                rows = [it for it in rows if it["key"] in wanted]
            if "itemType" in q:
                rows = [it for it in rows if it["data"]["itemType"] in q["itemType"].replace(" ", "").split("||")]
            start, limit = int(q.get("start", 0)), int(q.get("limit", 25))
            page = rows[start:start + limit]
            if q.get("format") == "versions":
                body = json.dumps({it["key"]: 7 for it in page}).encode()
            elif q.get("format") == "keys":
                body = ("\n".join(it["key"] for it in page) + "\n").encode()
            else:
                body = json.dumps(page).encode()
            return self._send(200, body, {**common, "Total-Results": str(len(rows)), "Content-Type": "application/json"})
        if p.path == "/api/users/0/fulltext":
            return self._send(200, json.dumps(FULLTEXT).encode(), common)
        if p.path.startswith("/api/users/0/items/") and p.path.endswith("/fulltext"):
            key = p.path.split("/")[-2]
            if key not in FULLTEXT:
                return self._send(404, b"not found")
            return self._send(200, json.dumps({"content": "text of " + key, "indexedPages": 1}).encode(), common)
        if p.path == "/api/groups":
            return self._send(200, json.dumps([{"id": 305258}]).encode(), {"Total-Results": "1"})
        return self._send(404, b"nope")

    def do_POST(self):
        Upstream.seen.append(("POST", self.path))
        self._send(500, b"a POST reached the upstream")


@pytest.fixture
def upstream():
    Upstream.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()


def test_scope_is_a_seeded_sample_of_records_with_their_children():
    a = scope_mod.Scope.random(FLAT, 4, seed=3)
    b = scope_mod.Scope.random(FLAT, 4, seed=3)
    c = scope_mod.Scope.random(FLAT, 4, seed=4)
    assert a.record_keys == b.record_keys and len(a.record_keys) == 4
    assert a.record_keys != c.record_keys
    assert all(k.startswith("R") for k in a.record_keys)
    for k in a.record_keys:
        assert "A" + k[1:] in a.child_keys
    assert not any(k.startswith("R") for k in a.child_keys)
    assert a.as_json()["kind"] == "random-items" and a.as_json()["records"] == 4
    assert len(scope_mod.Scope.random(FLAT, 500, seed=1).record_keys) == 12


def test_listings_are_filtered_paged_and_totalled(upstream):
    scope = scope_mod.Scope.random(FLAT, 5, seed=1)
    proxy = scope_mod.ScopeProxy(upstream, scope).start()
    try:
        base = f"http://127.0.0.1:{proxy.port}/api/users/0"
        st, h, body = get(base + "/items/top?limit=2&start=0")
        page = json.loads(body)
        assert st == 200 and len(page) == 2 and h["total-results"] == "5" and h["last-modified-version"] == "4242"
        assert {it["key"] for it in page} <= scope.record_keys
        st, h, body = get(base + "/items/top?limit=2&start=4")
        assert len(json.loads(body)) == 1 and h["total-results"] == "5"
        st, h, body = get(base + "/items/top?limit=2&start=6")
        assert json.loads(body) == []
        st, h, body = get(base + "/items?limit=100&start=0")
        keys = {it["key"] for it in json.loads(body)}
        assert keys == scope.all_keys and h["total-results"] == str(len(scope.all_keys))
        st, h, body = get(base + "/items?format=versions&limit=100&start=0")
        assert set(json.loads(body)) == scope.all_keys
        st, h, body = get(base + "/items?format=keys&limit=100&start=0")
        assert set(body.decode().split()) == scope.all_keys
        st, h, body = get(base + "/items?itemType=note%20%7C%7C%20annotation&limit=100&start=0")
        notes = {it["key"] for it in json.loads(body)}
        assert notes == {k for k in scope.child_keys if k.startswith("N")} and h["total-results"] == str(len(notes))
        # The sample was fetched by key, once per query and chunk, never by paging the library.
        top_calls = [p for m, p in Upstream.seen if p.startswith("/api/users/0/items/top")]
        assert len(top_calls) == 1 and "itemKey=" in top_calls[0]
        assert all("itemKey=" in p or p.endswith("limit=1") for m, p in Upstream.seen if "/items" in p and "/fulltext" not in p)
    finally:
        proxy.stop()


def test_census_is_filtered_and_the_rest_passes_through(upstream):
    scope = scope_mod.Scope.random(FLAT, 3, seed=2)
    proxy = scope_mod.ScopeProxy(upstream, scope).start()
    try:
        base = f"http://127.0.0.1:{proxy.port}/api/users/0"
        st, h, body = get(base + "/fulltext?since=0")
        assert set(json.loads(body)) == scope.child_keys - {k for k in scope.child_keys if k.startswith("N")}
        key = next(iter(k for k in scope.child_keys if k.startswith("A")))
        st, h, body = get(base + f"/items/{key}/fulltext")
        assert st == 200 and json.loads(body)["content"] == "text of " + key
        outside = next(iter(k for k in FULLTEXT if k not in scope.child_keys))
        st, h, body = get(base + f"/items/{outside}/fulltext")
        assert st == 200, "pass-through does not filter: the target only asks for keys it was listed"
        st, h, body = get(f"http://127.0.0.1:{proxy.port}/api/groups?limit=100&start=0")
        assert json.loads(body) == [{"id": 305258}] and h["total-results"] == "1"
        # The liveness probe: one upstream page, the scope's total, never a full fetch.
        st, h, body = get(base + "/items?limit=1")
        assert st == 200 and h["total-results"] == str(len(scope.all_keys))
        assert all(it.get("key") in scope.all_keys for it in json.loads(body))
        st, h, body = get(base + "/items/top?limit=1")
        assert h["total-results"] == str(len(scope.record_keys))
        with pytest.raises(urllib.error.HTTPError) as e:
            get(f"http://127.0.0.1:{proxy.port}/api/users/0/nowhere")
        assert e.value.code == 404
    finally:
        proxy.stop()


def test_the_proxy_is_read_only(upstream):
    scope = scope_mod.Scope.random(FLAT, 2, seed=5)
    proxy = scope_mod.ScopeProxy(upstream, scope).start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{proxy.port}/api/users/0/items", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        assert e.value.code == 405 and proxy.refused == 1
        assert not any(m == "POST" for m, _ in Upstream.seen), "nothing but GET reaches the upstream"
    finally:
        proxy.stop()
    source = (REPO / "bench" / "generator" / "scope.py").read_text()
    assert source.count("urlopen(") == 1 and 'method="GET"' in source
    for verb in ("PUT", "PATCH", "DELETE"):
        assert f'"{verb}"' not in source.replace("do_POST = do_PUT = do_PATCH = do_DELETE", "")
