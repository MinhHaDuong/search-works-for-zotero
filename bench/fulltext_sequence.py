#!/usr/bin/env python3
"""Record Zotero's item and full-text version sequences side by side.

Ticket 0012's whole finding is that these are two unrelated counters, and that the
delta handed one of them to an endpoint that reads the other. The numbers were first
reported from an uncaptured one-off call; a review found no artifact behind them, so
this script exists to produce one — raw responses included, so a later reader can check
the derivation rather than re-run the session.

The probe reads only. It never writes to Zotero and never touches the search index.
"""
import argparse
import json
import logging
import statistics
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ftseq")


def get(url: str, timeout: float) -> tuple[dict, dict]:
    """Body and headers. A 404 is data here, not a failure: /deleted answers that way."""
    req = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return (json.loads(raw) if raw else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_reason": str(e.reason)}, dict(e.headers or {})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:23119/api", help="Zotero local API root")
    ap.add_argument("--user", default="0", help="local API user id (0 on the desktop app)")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument(
        "--probe-since",
        type=int,
        nargs="*",
        default=[0, 200, 410],
        help="values of ?since= to ask /fulltext for, to show how the two sequences diverge",
    )
    ap.add_argument("--output", required=True, help="where to write the artifact")
    a = ap.parse_args()

    prefix = f"{a.base}/users/{a.user}"

    # The ITEM sequence: what `?since=` on /items compares against.
    _, item_headers = get(f"{prefix}/items?limit=1", a.timeout)
    library_version = int(item_headers.get("Last-Modified-Version", -1))

    # The FULL-TEXT sequence: a key -> version map over every extracted attachment.
    full_map, ft_headers = get(f"{prefix}/fulltext?since=0", a.timeout)
    if not isinstance(full_map, dict) or "_http_error" in full_map:
        raise SystemExit(f"/fulltext?since=0 did not return a version map: {full_map}")
    versions = sorted(v for v in full_map.values() if isinstance(v, int))

    # How many entries each `since=` returns. The defect is visible in one line of this
    # table: asking with the LIBRARY version returns nearly everything.
    since_counts = {}
    for s in a.probe_since:
        body, _ = get(f"{prefix}/fulltext?since={s}", a.timeout)
        since_counts[str(s)] = len(body) if isinstance(body, dict) and "_http_error" not in body else body

    out = {
        "probe": "ticket 0012 — item versus full-text version sequences",
        "base": a.base,
        "library_version_from_items_header": library_version,
        "fulltext_last_modified_version_header": ft_headers.get("Last-Modified-Version"),
        "fulltext_entries_total": len(versions),
        "fulltext_version_min": versions[0] if versions else None,
        "fulltext_version_max": versions[-1] if versions else None,
        "fulltext_version_median": statistics.median(versions) if versions else None,
        "fulltext_entries_returned_by_since": since_counts,
        # The one derived number the ticket leans on, spelled out rather than asserted.
        "fraction_of_library_reported_new_at_library_version": (
            round(since_counts.get(str(library_version), 0) / len(versions), 4)
            if versions and isinstance(since_counts.get(str(library_version)), int)
            else None
        ),
        # Kept so the aggregates above are re-derivable without another live call.
        "fulltext_versions_sorted": versions,
    }
    with open(a.output, "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    log.info("library version %s; full-text %s..%s over %s entries",
             library_version, out["fulltext_version_min"], out["fulltext_version_max"], len(versions))
    log.info("since= counts: %s", since_counts)


if __name__ == "__main__":
    main()
