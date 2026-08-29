#!/usr/bin/env python3
"""Harvest item_key -> year from the Zotero local API.

The search index stores no date, so a year-scoped query cannot be measured against it
without supplying one. This reads `meta.parsedDate`, which is Zotero's own parse of the
item's date field, and keeps only a four-digit year.

Read-only against the running desktop app.
"""
import argparse
import json
import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("years")


def fetch_page(base: str, start: int, limit: int) -> list[dict]:
    url = f"{base}/items?format=json&limit={limit}&start={start}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def year_of(item: dict) -> int | None:
    parsed = (item.get("meta") or {}).get("parsedDate") or ""
    head = parsed[:4]
    if head.isdigit():
        y = int(head)
        # A library holds reprints and bad metadata; a year outside this window is noise,
        # and letting it through would widen every "decade" scope with junk.
        if 1400 <= y <= 2100:
            return y
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:23119/api/users/0")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    years: dict[str, int] = {}
    seen = 0
    start = 0
    while True:
        page = fetch_page(a.base, start, a.limit)
        if not page:
            break
        for item in page:
            seen += 1
            y = year_of(item)
            if y is not None:
                years[item["key"]] = y
        start += len(page)
        if start % 1000 == 0:
            log.info("%d items scanned, %d with a usable year", seen, len(years))

    Path(a.output).write_text(json.dumps(years))
    log.info("%d items scanned, %d carry a year -> %s", seen, len(years), a.output)


if __name__ == "__main__":
    main()
