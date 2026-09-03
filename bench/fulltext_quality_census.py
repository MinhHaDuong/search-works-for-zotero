#!/usr/bin/env python3
"""Ticket 0480 — census of full-text cache *quality* over a Zotero storage tree.

The 2026-08-30 presence-probe ruling covers the cache that vanished. This
measures the cache that survived but may be poor: text produced by an older
extractor generation, which no upstream mechanism will ever reach (a fully
extracted old cache has `indexedPages == totalPages`, so `reindexTruncated`'s
query never selects it — `verification/SDT-CAPS-0483.md` §3).

    python3 bench/fulltext_quality_census.py --storage ~/data/Zotero-fresh/storage \\
        --output bench/results/0480-fulltext-quality/census.json

**Read-only.** The probe opens files and stats them; it writes nothing under
`--storage`. Ticket 0480's Invariants require that, and
`tests/test_fulltext_quality_census.py` asserts it against a fixture tree.

Signals, and what each one can and cannot say
---------------------------------------------

- **form feed** (`\\f`) — Zotero's PDF extractor began emitting a form feed at
  each page break with the 2024 generation. A PDF cache with no form feed
  anywhere was written before it. This is the strongest structural signal
  available from the filesystem alone, and it applies to PDFs only: an HTML or
  plain-text cache legitimately has none, so the field is `None` there rather
  than `False`. A one-page PDF is the known false flag and is counted
  separately.
- **near-empty** — a PDF whose cache holds almost no words is a *missing text
  layer*, not an old extraction. Separating the two matters: re-extracting with
  a better extractor does nothing for a scan, which needs OCR.
- **mojibake** — UTF-8 read through a single-byte codec, detected with
  `ftfy.badness.is_bad`. ftfy is used rather than a hand-rolled character-class
  heuristic because the failure mode of a hand-rolled one is a silent false
  negative on exactly the accented text this library is full of. When ftfy is
  absent the field is `None` — *unmeasured*, never *clean*.
- **raw ligatures** — U+FB01/U+FB02 surviving in the text mean nothing
  normalised them; a keyword index then misses "efficient" spelled with a
  ligature. Reported as a count, advisory.
- **mtime** — recorded, and on a resynced library it dates the sync rather than
  the extraction. See the artifact's own reading before using it.

Every count is written to one JSON artifact with its provenance, so a later
reader can tell which machine, which library and which ftfy produced it.
"""

import argparse
import json
import logging
import os
import platform
import socket
import stat
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

CACHE_NAME = ".zotero-ft-cache"

#: A PDF cache below this many words has no usable text layer. Chosen an order
#: of magnitude under a sparse title page rather than at a tuned boundary: the
#: class this separates out (a scan) is nowhere near it.
NEAR_EMPTY_WORDS = 50

#: Mojibake detection reads a prefix rather than the whole body. The monster
#: document's cache is tens of MiB and the signal, when present, is dense from
#: the first page; a prefix keeps a full-library pass to minutes.
MOJIBAKE_PREFIX_CHARS = 200_000

LIGATURES = "ﬁﬂﬀﬃﬄ"


def resolve_mojibake_fixer() -> Callable[[str], bool] | None:
    """`ftfy.badness.is_bad`, or None when ftfy is not installed.

    Returned as a callable so the census never imports ftfy itself: the test
    suite runs in the gate's dependency set, which does not carry ftfy, and a
    probe that cannot be exercised without an optional package is a probe
    nobody runs.
    """
    try:
        from ftfy.badness import is_bad
    except ImportError:
        return None
    return is_bad


def ftfy_version() -> str | None:
    try:
        import ftfy
    except ImportError:
        return None
    return getattr(ftfy, "__version__", "unknown")


def _attachment_suffixes(directory: Path) -> list[str]:
    """The suffixes of the directory's non-hidden files. Raises on an unlistable one.

    It used to swallow `OSError` and return `[]`, which made an unreadable
    attachment directory look like an attachment-less one — an unreadable cache
    silently reclassified as a non-PDF rather than reported. The caller counts
    the failure instead.
    """
    return [p.suffix.lower() for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")]


def classify(cache: Path, mojibake_fixer: Callable[[str], bool] | None = None) -> dict:
    """One cache's quality signals. Never raises on a bad file — it reports it."""
    directory = cache.parent
    suffixes = _attachment_suffixes(directory)
    attachments = [s for s in suffixes if s]
    is_pdf = ".pdf" in suffixes

    raw = cache.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    decode_errors = text.count("�")
    words = len(text.split())
    form_feeds = text.count("\f")

    record = {
        "key": directory.name,
        "is_pdf": is_pdf,
        "suffixes": sorted(set(suffixes)),
        # Two ways the directory-scoped `is_pdf` can be wrong, each counted rather
        # than assumed away: a cache with no co-located attachment at all (the
        # extraction's source is gone, so nothing dates it), and a directory
        # holding a PDF *and* something else, where the cache text may have come
        # from either. Neither is inside the single-page false-flag ceiling.
        "no_attachment": not attachments,
        "mixed_attachments": is_pdf and any(s != ".pdf" for s in attachments),
        "bytes": len(raw),
        "words": words,
        "form_feeds": form_feeds,
        # A signal that does not apply is absent, not false.
        "has_form_feed": (form_feeds > 0) if is_pdf else None,
        "near_empty": (words < NEAR_EMPTY_WORDS) if is_pdf else None,
        "decode_errors": decode_errors,
        "ligatures": sum(text.count(c) for c in LIGATURES),
        "cache_mtime": cache.stat().st_mtime,
        "mojibake": None,
    }
    if mojibake_fixer is not None:
        probe = text[:MOJIBAKE_PREFIX_CHARS]
        record["mojibake"] = bool(probe.strip()) and bool(mojibake_fixer(probe))
    return record


def census(storage: Path, mojibake_fixer: Callable[[str], bool] | None = None) -> dict:
    """Walk `storage/*/.zotero-ft-cache` and aggregate. Read-only.

    **The walk is explicit, and `Path.glob` is deliberately not used.** `glob`
    swallows `PermissionError` while scanning subdirectories, inside its own
    recursion, before any `try` here could see it: a directory the process cannot
    enter is simply absent from the results, with no exception, no count and no
    log line. That would make `unreadable_caches: 0` mean either "everything was
    readable" or "the walker cannot see failures", which are the same output —
    and it would mean it under the very count that decides the ticket's
    population. Enumerating `storage.iterdir()` and probing each directory
    ourselves puts every failure on the record.
    """
    detail: list[dict] = []
    unreadable: list[dict] = []
    root = Path(storage)
    for entry in sorted(root.iterdir()):
        try:
            # `entry.is_dir()` / `cache.is_file()` would swallow the same
            # PermissionError that `glob` does — a predicate returning False is
            # not distinguishable from a predicate that could not look. `stat`
            # and `listdir` raise, which is the point.
            if not stat.S_ISDIR(entry.stat().st_mode):
                continue
            if CACHE_NAME not in os.listdir(entry):
                continue
            detail.append(classify(entry / CACHE_NAME, mojibake_fixer))
        except OSError as e:
            unreadable.append({"key": entry.name, "error": str(e)})

    pdfs = [c for c in detail if c["is_pdf"]]
    measured = [c for c in pdfs if c["mojibake"] is not None]
    no_ff = [c for c in pdfs if not c["has_form_feed"]]
    return {
        "caches": len(detail),
        "pdf_caches": len(pdfs),
        "non_pdf_caches": len(detail) - len(pdfs),
        "unreadable_caches": len(unreadable),
        "unreadable_detail": unreadable,
        "pdf_with_form_feed": sum(1 for c in pdfs if c["has_form_feed"]),
        "pdf_no_form_feed": len(no_ff),
        # The known false flag: a genuinely single-page PDF has no page break to
        # mark, so its absent form feed dates nothing. A near-empty cache is
        # excluded — it is short for a different reason (no text layer), and
        # folding the two together would inflate this ceiling with a population
        # that re-extraction cannot help anyway.
        "pdf_no_form_feed_single_page_suspect": sum(
            1 for c in no_ff if not c["near_empty"] and c["words"] < 700
        ),
        "pdf_near_empty": sum(1 for c in pdfs if c["near_empty"]),
        # Reported separately from near-empty because the prose distinguishes them:
        # a cache with literally no words is a PDF Zotero could not read at all,
        # which no re-extraction fixes and OCR might.
        "pdf_zero_words": sum(1 for c in pdfs if c["words"] == 0),
        # The number a policy would act on: old-generation caches that hold real
        # text and could be improved by re-extraction. The raw no-form-feed count
        # includes near-empty caches, which need OCR and not a better extractor,
        # so quoting it as the population would put an OCR population inside a
        # re-extraction estimate.
        "pdf_reextraction_population": sum(1 for c in no_ff if not c["near_empty"]),
        "caches_with_no_attachment": sum(1 for c in detail if c["no_attachment"]),
        "pdf_caches_mixed_attachments": sum(1 for c in pdfs if c["mixed_attachments"]),
        "pdf_mojibake": (sum(1 for c in measured if c["mojibake"]) if measured else None),
        "pdf_mojibake_measured": len(measured),
        "pdf_with_ligatures": sum(1 for c in pdfs if c["ligatures"] > 0),
        "decode_error_caches": sum(1 for c in detail if c["decode_errors"] > 0),
        # The internal control. Form feed dates the extractor; ligatures and mojibake
        # measure the text. If the two are independent the split is arbitrary and the
        # signal means nothing — so the cross-tabulation is part of the measurement, not
        # a diagnostic afterthought.
        "by_form_feed": {
            group: _group_stats([c for c in pdfs if bool(c["has_form_feed"]) is want])
            for group, want in (("with_form_feed", True), ("no_form_feed", False))
        },
        "caches_detail": detail,
    }


def _group_stats(group: list[dict]) -> dict:
    measured = [c for c in group if c["mojibake"] is not None]
    words = sorted(c["words"] for c in group)
    return {
        "caches": len(group),
        "median_words": words[len(words) // 2] if words else None,
        "mojibake": (sum(1 for c in measured if c["mojibake"]) if measured else None),
        "mojibake_measured": len(measured),
        "with_ligatures": sum(1 for c in group if c["ligatures"] > 0),
        "near_empty": sum(1 for c in group if c["near_empty"]),
        "zero_words": sum(1 for c in group if c["words"] == 0),
    }


def provenance(storage: Path) -> dict:
    return {
        "host": socket.gethostname(),
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ftfy_version": ftfy_version(),
        "storage_realpath": str(Path(storage).resolve()),
        "loadavg": os.getloadavg(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--storage", required=True, type=Path, help="a Zotero storage/ directory (read only)")
    ap.add_argument("--output", type=Path, help="write the JSON artifact here (default: stdout summary only)")
    ap.add_argument("--no-detail", action="store_true", help="omit the per-cache rows from the artifact")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.storage.is_dir():
        logging.error("no such storage directory: %s", args.storage)
        return 2

    fixer = resolve_mojibake_fixer()
    if fixer is None:
        logging.warning("ftfy not installed — the mojibake column will be null, which means UNMEASURED")

    result = census(args.storage, fixer)
    detail = result.pop("caches_detail")
    doc = {
        "ticket": "0480",
        "storage": str(args.storage),
        "provenance": provenance(args.storage),
        "summary": result,
        "caches_detail": [] if args.no_detail else detail,
    }
    for k, v in doc["summary"].items():
        if k not in ("caches_detail", "unreadable_detail"):
            logging.info("%-42s %s", k, v)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename: a run interrupted partway through leaves the previous
        # artifact intact rather than a truncated one that still parses as JSON
        # only sometimes. Cheap here, and this script is proposed as standing
        # background-campaign machinery.
        tmp = args.output.with_suffix(args.output.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        tmp.replace(args.output)
        logging.info("wrote %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
