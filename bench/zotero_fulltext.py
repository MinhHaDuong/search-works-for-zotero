"""Client for the full-text control plugin (bench/zotero-fulltext-plugin/).

    uv run python bench/zotero_fulltext.py status KEY [KEY ...]
    uv run python bench/zotero_fulltext.py reindex KEY [KEY ...] [--wait] [--poll 15]

Talks to Zotero's local server on localhost; nothing leaves the machine.
"""

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "http://localhost:23119/search-works/fulltext/"


def call(base: str, path: str, body: dict | None = None, timeout: float = 120.0) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def status(base: str, keys: list[str]) -> dict:
    return call(base, "status?keys=" + ",".join(keys))


def print_status(s: dict) -> None:
    stats = s.get("stats") or {}
    logging.info("busy=%s running=%s lastError=%s stats=%s", s.get("busy"), s.get("running"), s.get("lastError"), stats)
    for it in s.get("items", []):
        if "error" in it:
            logging.info("  %s %s", it["key"], it["error"])
            continue
        logging.info(
            "  %s lib=%s(%s) %-10s pages %s/%s chars %s/%s v%s",
            it["key"], it["libraryID"], it["libraryType"], it["state"],
            it["indexedPages"], it["totalPages"], it["indexedChars"], it["totalChars"], it["version"],
        )


def complete(it: dict) -> bool:
    if it.get("indexedPages") is not None and it.get("totalPages") is not None:
        return it["indexedPages"] >= it["totalPages"]
    if it.get("indexedChars") is not None and it.get("totalChars") is not None:
        return it["indexedChars"] >= it["totalChars"]
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["status", "reindex"])
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--wait", action="store_true", help="reindex: poll status until every key is complete")
    ap.add_argument("--poll", type=float, default=15.0, help="seconds between polls")
    ap.add_argument("--max-wait", type=float, default=3600.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        if args.command == "status":
            print_status(status(args.base, args.keys))
            return 0
        if not args.keys:
            ap.error("reindex needs at least one key")
        r = call(args.base, "reindex", {"keys": args.keys})
        logging.info("queued=%s missing=%s notAttachments=%s", r.get("queued"), r.get("missing"), r.get("notAttachments"))
        if not args.wait:
            return 0
        started = time.monotonic()
        while time.monotonic() - started < args.max_wait:
            time.sleep(args.poll)
            s = status(args.base, args.keys)
            done = [it for it in s.get("items", []) if complete(it)]
            logging.info("%ds: %d of %d complete, busy=%s", int(time.monotonic() - started), len(done), len(args.keys), s.get("busy"))
            if len(done) == len(args.keys) and not s.get("busy"):
                print_status(s)
                return 0
        logging.error("gave up after %ds", int(args.max_wait))
        return 1
    except urllib.error.URLError as e:
        logging.error("Zotero not reachable or plugin not installed: %s", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
