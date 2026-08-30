"""Does the local API serve the cache file verbatim — structure included?

Ticket 0483 (extraction caps) and the shim-extractor ruling both rest on what
the transport preserves. This probe compares, for attachments the fulltext API
lists, the `.zotero-ft-cache` bytes against the API's `content`: character
count, form feeds (page breaks), blank lines, and the indexedPages/totalPages
metadata that makes extractor truncation detectable per attachment.

Measured 2026-08-30 (3 attachments, one at the 100-page cap): byte-identical
content, form feeds and blank lines intact, cap visible in the metadata.

    python3 verification/probes/api-vs-cache-probe.py
"""
import argparse
import json
import pathlib
import urllib.request

API = "http://localhost:23119/api/users/0"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=pathlib.Path,
                        default=pathlib.Path("/home/haduong/data/Zotero/storage"))
    parser.add_argument("--probes", type=int, default=3)
    args = parser.parse_args()

    keys = json.load(urllib.request.urlopen(f"{API}/fulltext?since=0"))
    tested = 0
    for key in keys:
        cache = args.storage_root / key / ".zotero-ft-cache"
        if not cache.exists():
            continue
        raw = cache.read_text(errors="replace")
        if "\f" not in raw or len(raw) < 20_000:
            continue
        with urllib.request.urlopen(f"{API}/items/{key}/fulltext") as response:
            d = json.load(response)
        t = d.get("content", "")
        meta = {k: v for k, v in d.items() if k != "content"}
        blank = "yes" if "\n\n" in t or "\n \n" in t else "no"
        print(f"{key} | meta: {meta}")
        print(f"  cache: chars {len(raw)} ff {raw.count(chr(12))} | "
              f"API: chars {len(t)} ff {t.count(chr(12))} blank-lines {blank} | "
              f"identical: {raw == t}")
        tested += 1
        if tested == args.probes:
            break


if __name__ == "__main__":
    main()
