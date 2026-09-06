"""A random item sample the target sees as its whole library: the scope proxy.

Ruling of 2026-09-06 on the library-level scope: a seeded random sample of
items, not a stratified one and not the newest N, built into its own index —
thin cells are what the library has, and a random sample reports them at their
true weight. The target's build tool pages the library's top-level items and
can cap the count, but it cannot take a list of keys. So the harness gives it a
library that *is* the sample: a read-only HTTP proxy on 127.0.0.1 that forwards
every GET to Zotero's local API and filters the listings — `/items`,
`/items/top`, `?format=versions`, the `/fulltext` census — to the sampled
records and their children. Everything else (`/items/<key>`, `/children`,
`/items/<key>/fulltext`, `/groups`, the liveness ping) passes through. The
target is pointed at the proxy through its own `ZOTERO_LOCAL_PORT` setting,
which the run identity records.

Paging is served by the proxy, not delegated: a filtered page of Zotero's would
shrink below the requested size and a caller reading `Total-Results` would stop
early or overshoot. The proxy fetches the sample itself, by `itemKey=` chunks
of fifty (the local API honours the filter, checked 2026-09-06), with the
query's other parameters (`itemType`, `format`) passed along so Zotero applies
them; it caches the result per query and serves `start`/`limit` slices with
`Total-Results` set to the filtered count. Fetching the sample rather than
paging the library matters twice over: a 17 000-item listing takes minutes,
and the target's liveness probe (`/users/0/items?limit=1`, with a deadline)
concluded the app was down and fell back to the Web API when the first version
of this proxy paged the whole library to answer it.

Read-only, and asserted: the proxy answers 405 to anything but GET and never
builds a request of its own with another method. It is a fixture library in the
sense of `bench/fixtures/README.md` — the same author's library, restricted —
not a non-default option of the target.
"""

import json
import logging
import random
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bench.library_census import NON_RECORD_TYPES

#: Keys per `itemKey=` request; the Web API caps the filter at fifty.
KEY_CHUNK = 50
FORWARDED_HEADERS = ("content-type", "last-modified-version", "x-zotero-version",
                     "zotero-api-version", "zotero-schema-version", "location")


@dataclass(frozen=True)
class Scope:
    """The sampled records and their children, by key."""

    seed: int
    requested: int
    record_keys: frozenset[str]
    child_keys: frozenset[str]

    @property
    def all_keys(self) -> frozenset[str]:
        return self.record_keys | self.child_keys

    @classmethod
    def random(cls, items: list[dict], n: int, seed: int) -> "Scope":
        """`n` top-level bibliographic records drawn uniformly by `seed`, with
        every child (attachment, note) that hangs off them."""
        records = sorted(it["key"] for it in items
                         if not it.get("parentItem") and it["itemType"] not in NON_RECORD_TYPES)
        chosen = frozenset(random.Random(seed).sample(records, min(n, len(records))))
        children = frozenset(it["key"] for it in items if it.get("parentItem") in chosen)
        return cls(seed=seed, requested=n, record_keys=chosen, child_keys=children)

    def as_json(self) -> dict:
        return {"kind": "random-items", "seed": self.seed, "requested": self.requested,
                "records": len(self.record_keys), "children": len(self.child_keys)}


def _get(url: str, timeout: float = 600.0) -> tuple[int, dict[str, str], bytes]:
    """The proxy's one upstream call site: GET, and nothing else, ever."""
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


urllib.request.install_opener(urllib.request.build_opener(_NoRedirect))


@dataclass
class Listing:
    status: int
    headers: dict[str, str]
    kind: str            # "array" | "versions" | "keys" | "opaque"
    rows: list = field(default_factory=list)
    body: bytes = b""


class ScopeProxy:
    def __init__(self, upstream_base: str, scope: Scope, prefix: str = "/api/users/0"):
        self.upstream = upstream_base.rstrip("/")
        self.scope = scope
        self.prefix = prefix
        self.keys = scope.all_keys
        self.attachment_keys = scope.child_keys
        self._cache: dict[str, Listing] = {}
        self._lock = threading.Lock()
        self.requests: list[tuple[str, str]] = []
        self.refused: int = 0
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                proxy.handle(self)

            def _refuse(self):
                proxy.refused += 1
                self.send_response(405)
                self.end_headers()

            do_POST = do_PUT = do_PATCH = do_DELETE = _refuse

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> "ScopeProxy":
        self._thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    # -- classification -----------------------------------------------------

    def _is_listing(self, path: str) -> bool:
        return path in (f"{self.prefix}/items", f"{self.prefix}/items/top")

    def _is_fulltext_census(self, path: str) -> bool:
        return path == f"{self.prefix}/fulltext"

    # -- upstream reads -----------------------------------------------------

    def _fetch_all(self, path: str, params: list[tuple[str, str]], fmt: str) -> Listing:
        """The whole listing behind one query, fetched by key chunks and filtered to the scope."""
        cache_key = path + "?" + urllib.parse.urlencode(sorted(params))
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        wanted = sorted(self.scope.record_keys if path.endswith("/top") else self.keys)
        rows: list = []
        seen: set[str] = set()
        headers: dict[str, str] = {}
        listing = None
        for i in range(0, len(wanted), KEY_CHUNK):
            chunk = wanted[i:i + KEY_CHUNK]
            # A key chunk can answer with more rows than keys (`/items?itemKey=` adds
            # the children of a listed record), so each chunk is paged to its own total.
            start = 0
            while True:
                q = urllib.parse.urlencode(params + [("itemKey", ",".join(chunk)), ("start", str(start)),
                                                     ("limit", str(KEY_CHUNK * 2))])
                status, headers, body = _get(f"{self.upstream}{path}?{q}")
                if status != 200:
                    listing = Listing(status, headers, "opaque", body=body)
                    break
                if fmt == "keys":
                    page = [k for k in body.decode().splitlines() if k]
                    for k in page:
                        if k in self.keys and k not in seen:
                            seen.add(k)
                            rows.append(k)
                else:
                    doc = json.loads(body)
                    if isinstance(doc, dict):
                        page = list(doc.items())
                        for k, v in page:
                            if k in self.keys and k not in seen:
                                seen.add(k)
                                rows.append((k, v))
                    else:
                        page = doc
                        for it in page:
                            k = it.get("key")
                            if k in self.keys and k not in seen:
                                seen.add(k)
                                rows.append(it)
                start += len(page)
                if not page or start >= int(headers.get("total-results", len(page))):
                    break
            if listing is not None:
                break
        if listing is None:
            kind = "keys" if fmt == "keys" else "versions" if fmt == "versions" else "array"
            listing = Listing(200, headers, kind, rows)
        with self._lock:
            self._cache[cache_key] = listing
        return listing

    # -- the handler --------------------------------------------------------

    def handle(self, h: BaseHTTPRequestHandler) -> None:
        parsed = urllib.parse.urlsplit(h.path)
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        self.requests.append(("GET", parsed.path))
        try:
            if self._is_listing(parsed.path):
                self._serve_listing(h, parsed.path, params)
            elif self._is_fulltext_census(parsed.path):
                self._serve_census(h, parsed.path, params)
            else:
                self._passthrough(h, parsed.path, parsed.query)
        except Exception as e:  # the target must see a failure, not a hang
            logging.warning("scope proxy: %s %s: %s", parsed.path, parsed.query, e)
            h.send_response(502)
            h.end_headers()

    def _serve_listing(self, h, path: str, params: list[tuple[str, str]]) -> None:
        paging = {k: v for k, v in params if k in ("start", "limit")}
        rest = [(k, v) for k, v in params if k not in ("start", "limit")]
        if paging.get("limit") == "1" and not rest and "start" not in paging:
            # The target's liveness probe, which runs on a deadline: one upstream
            # page, filtered, with the scope's own total — never a full fetch.
            status, headers, body = _get(f"{self.upstream}{path}?limit=1")
            if status == 200:
                body = json.dumps([it for it in json.loads(body) if it.get("key") in self.keys]).encode()
            total = len(self.scope.record_keys if path.endswith("/top") else self.keys)
            self._reply(h, status, headers, body, total=total)
            return
        fmt = dict(rest).get("format", "json")
        listing = self._fetch_all(path, rest, fmt)
        if listing.kind == "opaque":
            self._reply(h, listing.status, listing.headers, listing.body, total=None)
            return
        start = int(paging.get("start", 0))
        limit = int(paging.get("limit", 25))
        page = listing.rows[start:start + limit]
        if listing.kind == "keys":
            body = ("\n".join(page) + ("\n" if page else "")).encode()
        elif listing.kind == "versions":
            body = json.dumps(dict(page)).encode()
        else:
            body = json.dumps(page).encode()
        self._reply(h, 200, listing.headers, body, total=len(listing.rows))

    def _serve_census(self, h, path: str, params: list[tuple[str, str]]) -> None:
        q = urllib.parse.urlencode(params)
        status, headers, body = _get(f"{self.upstream}{path}" + (f"?{q}" if q else ""))
        if status == 200:
            doc = json.loads(body)
            body = json.dumps({k: v for k, v in doc.items() if k in self.attachment_keys}).encode()
        self._reply(h, status, headers, body, total=None)

    def _passthrough(self, h, path: str, query: str) -> None:
        status, headers, body = _get(f"{self.upstream}{path}" + (f"?{query}" if query else ""))
        self._reply(h, status, headers, body, total=headers.get("total-results"))

    @staticmethod
    def _reply(h, status: int, headers: dict[str, str], body: bytes, total) -> None:
        h.send_response(status)
        for name in FORWARDED_HEADERS:
            if name in headers:
                h.send_header(name.title(), headers[name])
        if total is not None:
            h.send_header("Total-Results", str(total))
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)
