#!/usr/bin/env python3
"""Fetch the fixture corpus's source bytes from the archives the recipe names,
and check each against its pinned hash.

The recipe (`recipe.json`, beside this script) is the first of the fixture's
three layers (DECISIONS.md, 2026-09-02, "The golden fixture corpus"): one
record per document naming a public archive, a persistent identifier, the
address of the bytes, and their sha256. This script turns that record into
files on disk and says, per document, whether the archive still serves the
bytes the recipe pinned. It extracts nothing. Text enters the fixture only as
the export of Zotero's own extraction, the third layer, which is a later
script's job.

Why a hash and not just an address: an identifier can be persistent while the
bytes behind it move. Gutenberg revises texts in place, Commons files are
overwritten with history kept, arXiv regenerates a version's PDF from source,
and an unversioned database of record can replace a corrected translation
under the same id. The hash makes each of those a visible mismatch in this
script's report rather than a silent change in the corpus. A mismatch is
something to inspect, never something to fix by editing the hash: re-pinning
is a commit whose diff is the review artifact.

The cache lives outside `bench/` (default `corpus-cache/` at the repo root,
git-ignored) so that scanned PDFs never land where `check_models.py` scans for
text. A truncated download must never be trusted on the next run, so every
fetch goes to a `.partial` file and is renamed only after the size and magic
bytes look right.
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger("fetch_recipe")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_RECIPE = HERE / "recipe.json"
DEFAULT_CACHE = REPO / "corpus-cache"

#: Some archive front ends answer 403 to a bare urllib agent while serving the
#: same bytes to a browser. A browser-shaped agent string is the difference
#: between "blocked" and "fetched" on FAOLEX and Gallica.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0"

#: First bytes each format must open with. An HTML error page served with a
#: 200 fails this check instead of poisoning the cache.
MAGIC = {"pdf": b"%PDF", "djvu": b"AT&T", "wikitext": None, "html": None}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_atomic(url: str, dest: Path, timeout: float, magic: bytes | None, min_size: int) -> None:
    """Fetch `url` to `dest` through a temp file and a rename."""
    tmp = dest.with_suffix(dest.suffix + ".partial")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    size = tmp.stat().st_size
    if size < min_size:
        tmp.unlink()
        raise RuntimeError(f"{url}: {size} bytes, expected at least {min_size}")
    if magic is not None:
        with open(tmp, "rb") as fh:
            head = fh.read(len(magic))
        if head != magic:
            tmp.unlink()
            raise RuntimeError(f"{url}: expected {magic!r} at file start, got {head!r}")
    os.replace(tmp, dest)


def fetch_one(doc: dict, cache_dir: Path, timeout: float) -> dict:
    """Fetch one recipe entry and compare its hash. Returns a report row."""
    fmt = doc.get("bytes_format", "pdf")
    dest = cache_dir / f"{doc['id']}.{fmt}"
    row = {"id": doc["id"], "archive": doc["archive"], "path": str(dest)}
    if not dest.exists():
        log.info("fetching %s from %s", doc["id"], doc["bytes_url"])
        try:
            download_atomic(doc["bytes_url"], dest, timeout, MAGIC.get(fmt), doc.get("min_size", 1_000))
        except Exception as exc:  # noqa: BLE001 — one dead archive must not stop the others
            row["status"] = "unfetched"
            row["reason"] = str(exc)
            return row
    got = sha256_of(dest)
    row["sha256"] = got
    if doc.get("sha256") is None:
        row["status"] = "unpinned"
    elif got == doc["sha256"]:
        row["status"] = "match"
    else:
        row["status"] = "MISMATCH"
        row["pinned"] = doc["sha256"]
    return row


#: The archives a fixture document may come from (DECISIONS.md, 2026-09-02,
#: rulings 2, 3 and the FAOLEX entry). A public, third-party-hosted, persistent
#: identifier naming one fixed set of bytes; a personal library or homepage is
#: not one. The three open archives need a version on the identifier.
ADMITTED_ARCHIVES = frozenset(
    {
        "internet-archive",
        "gallica",
        "wikimedia-commons",
        "wikisource",
        "hal",
        "arxiv",
        "zenodo",
        "faolex",
        "uk-government-web-archive",
    }
)
VERSIONED_ARCHIVES = frozenset({"hal", "arxiv", "zenodo"})
#: Hosts that are publishers or personal sites, never archives. Listed because
#: each one appeared as a source in the closed PR #151.
REFUSED_HOSTS = ("minh.haduong.com", "zotero.org", "www.gov.uk", "chinhphu.vn", "vbpl.vn", "thuvienphapluat.vn")
REQUIRED = ("id", "title", "author", "year", "language", "tier", "facet", "archive", "identifier", "bytes_url", "sha256", "license_basis")
LANGUAGES = frozenset({"en", "fr", "de", "vi", "zh", "ar", "ru", "hi", "es", "la", "pt"})
TIERS = frozenset({"MUST", "SHOULD"})
FACETS = frozenset({"core", "notes", "group", "deep-body"})
HEX64 = frozenset("0123456789abcdef")


def validate(recipe: list[dict]) -> list[str]:
    """Every way a recipe entry can break the provenance rulings, by entry id.

    Returns the list of offences; an empty list is a valid recipe. Kept as data
    rather than exceptions so a test can assert on the whole set at once and the
    script can print them all before refusing.
    """
    found: list[str] = []
    seen: set[str] = set()
    for doc in recipe:
        did = doc.get("id", "<no id>")
        for key in REQUIRED:
            if key not in doc:
                found.append(f"{did}: missing {key}")
        if did in seen:
            found.append(f"{did}: duplicate id")
        seen.add(did)
        for key in doc:
            if key.startswith("zotero_"):
                found.append(f"{did}: {key} names a personal library")
        if doc.get("archive") not in ADMITTED_ARCHIVES:
            found.append(f"{did}: archive {doc.get('archive')!r} is not admitted")
        if doc.get("archive") in VERSIONED_ARCHIVES and not doc.get("version"):
            found.append(f"{did}: {doc['archive']} identifier carries no version")
        url = doc.get("bytes_url") or ""
        if any(host in url for host in REFUSED_HOSTS):
            found.append(f"{did}: bytes_url {url} is a publisher or personal host, not an archive")
        digest = doc.get("sha256")
        if digest is None:
            if not doc.get("sha256_reason"):
                found.append(f"{did}: sha256 is null with no sha256_reason")
        elif len(digest) != 64 or not set(digest) <= HEX64:
            found.append(f"{did}: sha256 is not 64 hex characters")
        if doc.get("language") not in LANGUAGES:
            found.append(f"{did}: language {doc.get('language')!r} unknown")
        if doc.get("tier") not in TIERS:
            found.append(f"{did}: tier {doc.get('tier')!r} unknown")
        if doc.get("facet") not in FACETS:
            found.append(f"{did}: facet {doc.get('facet')!r} unknown")
        if not doc.get("license_basis"):
            found.append(f"{did}: license_basis is empty")
    return found


def load_recipe(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        recipe = json.load(fh)
    assert isinstance(recipe, list), f"{path}: the recipe is a JSON array of documents"
    offences = validate(recipe)
    if offences:
        for line in offences:
            log.error("%s", line)
        raise SystemExit(f"{path}: {len(offences)} provenance offence(s); nothing fetched")
    return recipe


def run(recipe: list[dict], cache_dir: Path, timeout: float, only: set[str] | None) -> list[dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for doc in recipe:
        if only and doc["id"] not in only:
            continue
        if doc.get("bytes_url") is None:
            rows.append({"id": doc["id"], "archive": doc["archive"], "status": "no-bytes-url"})
            continue
        rows.append(fetch_one(doc, cache_dir, timeout))
    return rows


def report(rows: list[dict]) -> int:
    """Print one line per document; exit status is the count of mismatches."""
    width = max((len(r["id"]) for r in rows), default=8)
    for r in rows:
        extra = r.get("reason") or (f"pinned {r['pinned'][:12]}" if "pinned" in r else "")
        print(f"{r['id']:<{width}}  {r['status']:<11} {r.get('sha256', '')[:12]:<12} {extra}")
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("summary:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return counts.get("MISMATCH", 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE, help="recipe.json to read")
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="where fetched bytes land (git-ignored)")
    ap.add_argument("--only", action="append", default=None, metavar="ID", help="fetch only this document id (repeatable)")
    ap.add_argument("--timeout", type=float, default=600.0, help="seconds per download")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    rows = run(load_recipe(args.recipe), args.cache_dir, args.timeout, set(args.only) if args.only else None)
    sys.exit(1 if report(rows) else 0)


if __name__ == "__main__":
    main()
