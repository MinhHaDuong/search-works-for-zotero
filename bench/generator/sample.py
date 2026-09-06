#!/usr/bin/env python3
"""Sample answer paragraphs from the real library, read-only, with their citation chain.

    python3 -m bench.generator.sample --n 100 --seed 1 --work-dir /path/private \\
        --census bench/results/0029-library-census/census.json \\
        --zotero-data-dir ~/data/Zotero [--scope-keys keys.txt]

**Read-only, and provably so.** The only network call site is
`bench.library_census.http_fetch`, which builds a GET and nothing else;
`tests/test_generator_sample.py` asserts this module builds no request of its
own. The PDF page labels are read from the attachment file through an immutable
open. Nothing is written except into `--work-dir`.

**Private output.** `sample.jsonl` in the work directory carries paragraph text,
keys and titles: it is the answer key of one run and never leaves the machine or
enters the repository. `sample-summary.json` beside it carries aggregates only
and is what the run artifact copies.

**Stratification.** The frame is every (record, attachment) pair whose attachment
has extracted text and whose record is in scope. A target joint distribution is
the product of three census marginals — item type, attachment format among the
attachments with text, and document length in census quartiles — and the sampler
fills the cell with the largest deficit first, drawing uniformly inside it. The
summary reports target against achieved on every marginal, so a frame that cannot
supply a cell (a webpage attached as PDF, say) is visible rather than silently
reweighted. Language is recorded, not quota'd: ruling 2 of 2026-09-06 reads
Zotero's language field as a weak indicator, so the paragraph's own language is
detected from its text and the lane is built from that.

**The chain, element by element, with a measured flag on each.** Title, creators,
date and identifier (DOI, then ISBN, then URL) come from the record. The PDF page
index comes from the form feeds Zotero's extractor writes between pages in recent
generations, and is not measured when the text carries none. The printed page
label comes from the PDF's own `/PageLabels` tree when the file is local and
readable, and is not measured otherwise — a PDF without that tree numbers its
pages by index, which is not the number printed on the page. The section heading
is derived only where the text makes it evident. A compound document's part is
the record's own title with `bookTitle` or `proceedingsTitle` as the container.
"""

import argparse
import json
import logging
import random
import sys
from collections import Counter
from pathlib import Path

from bench.generator import text as T
from bench.generator.score import aggregate_key
from bench.library_census import (
    FILE_LINK_MODES,
    NON_RECORD_TYPES,
    DEFAULT_BASE_URL,
    Fetch,
    Library,
    http_fetch,
    normalise_language,
)

#: zoteus's `DEFAULT_FULLTEXT_MAX_CHARS`: body text beyond this offset in an
#: item is not indexed by the target's default configuration. Recorded per
#: sample as reachability, never used to drop a sample.
DEFAULT_FULLTEXT_CAP = 40_000

#: Item types that get their own stratum; the rest fold into `other`.
TYPE_GROUPS = (
    "journalArticle", "report", "webpage", "book", "conferencePaper", "bookSection",
    "presentation", "newspaperArticle", "magazineArticle", "blogPost", "document",
)

FORMATS = ("pdf", "html", "other")

#: Item types whose record is one part of a compound document.
COMPOUND_PARTS = {
    "bookSection": "bookTitle",
    "conferencePaper": "proceedingsTitle",
    "encyclopediaArticle": "encyclopediaTitle",
    "dictionaryEntry": "dictionaryTitle",
}


def type_group(item_type: str) -> str:
    return item_type if item_type in TYPE_GROUPS else "other"


def format_of(content_type: str) -> str:
    if content_type == "application/pdf":
        return "pdf"
    if content_type in ("text/html", "application/xhtml+xml"):
        return "html"
    return "other"


# ---------------------------------------------------------------- targets from the census


def census_targets(census: dict) -> dict:
    """Marginal targets read from the census artifact, as shares summing to one.

    Item type: the census's `item_types`, grouped. Format: attachments with text
    (`indexed` or `partial` state) by content type — the frame can only supply
    paragraphs from those. Length: four equal quartiles by construction, with the
    census's `totalChars` cuts recorded so the buckets mean the same thing on
    every run.
    """
    personal = census["personal"]
    types = Counter()
    for t, n in personal["item_types"].items():
        types[type_group(t)] += n
    total = sum(types.values())
    formats = Counter()
    for ct, row in personal["fulltext"]["by_content_type"].items():
        with_text = row["state"].get("indexed", 0) + row["state"].get("partial", 0)
        formats[format_of(ct)] += with_text
    ftotal = sum(formats.values())
    q = personal["fulltext"]["quantiles"]["totalChars"]
    return {
        "type": {t: types[t] / total for t in (*TYPE_GROUPS, "other")},
        "format": {f: formats[f] / ftotal for f in FORMATS},
        "length": {b: 0.25 for b in ("short", "medium", "long", "very-long")},
        "length_cuts_chars": (q["p25"], q["p50"], q["p75"]),
        "census_measured_at": census["provenance"]["measured_at"],
        "census_library_version": census["provenance"]["library_last_modified_version"],
    }


# ---------------------------------------------------------------- the chain


def creators_of(record: dict) -> list[str]:
    out = []
    for c in record.get("creators") or []:
        if c.get("creatorType") not in (None, "author", "editor", "contributor", "presenter", "director"):
            continue
        if c.get("name"):
            out.append(c["name"])
        else:
            out.append(" ".join(p for p in (c.get("firstName"), c.get("lastName")) if p))
    return out


def identifier_of(record: dict) -> tuple[str | None, str | None]:
    for field in ("DOI", "ISBN", "url"):
        value = (record.get(field) or "").strip()
        if value:
            return field.lower(), value
    return None, None


def chain_of(record: dict) -> dict:
    """The record's part of the chain: what Zotero's metadata carries, each element
    with a `measured` flag that is False when the field is empty."""
    kind, value = identifier_of(record)
    part_field = COMPOUND_PARTS.get(record["itemType"])
    container = (record.get(part_field) or "").strip() if part_field else ""
    creators = creators_of(record)
    return {
        "title": {"value": record.get("title") or "", "measured": bool(record.get("title"))},
        "creators": {"value": creators, "measured": bool(creators)},
        "date": {"value": record.get("date") or "", "measured": bool(record.get("date"))},
        "identifier": {"value": value, "kind": kind, "measured": value is not None},
        "compound": {
            "applies": part_field is not None,
            "part_title": record.get("title") or "" if part_field else None,
            "container": container or None,
            "measured": bool(container) if part_field else None,
        },
    }


def page_label(pdf_path: Path | None, index: int | None) -> tuple[str | None, str]:
    """The printed page label from the PDF's own `/PageLabels`, and how it was read.

    Returns `(label, source)`; `source` is `pdf-page-labels` when the tree exists,
    `no-page-labels` when the file opens but numbers its pages by index only,
    `not-measured` when there is no readable local file or no page index.
    """
    if pdf_path is None or index is None:
        return None, "not-measured"
    try:
        import pikepdf
    except ImportError:
        return None, "not-measured"
    try:
        with pikepdf.open(pdf_path) as pdf:
            if "/PageLabels" not in pdf.Root:
                return None, "no-page-labels"
            if index - 1 >= len(pdf.pages):
                return None, "not-measured"
            return str(pdf.pages[index - 1].label), "pdf-page-labels"
    except Exception:  # a damaged or encrypted file is a not-measured, not a crash
        return None, "not-measured"


def attachment_file(attachment: dict, zotero_data_dir: Path | None) -> Path | None:
    """The local file of an attachment, or None. Never creates anything."""
    if attachment.get("contentType") != "application/pdf":
        return None
    mode = attachment.get("linkMode")
    if mode == "linked_file":
        p = Path(attachment.get("path") or "")
        return p if p.is_file() else None
    if zotero_data_dir is None or mode not in FILE_LINK_MODES:
        return None
    folder = zotero_data_dir / "storage" / attachment["key"]
    name = attachment.get("filename")
    if name and (folder / name).is_file():
        return folder / name
    pdfs = sorted(folder.glob("*.pdf")) if folder.is_dir() else []
    return pdfs[0] if pdfs else None


# ---------------------------------------------------------------- the sampler


class Sampler:
    def __init__(self, lib: Library, targets: dict, seed: int, zotero_data_dir: Path | None,
                 fulltext_cap: int = DEFAULT_FULLTEXT_CAP, max_tries_per_cell: int = 12):
        self.lib = lib
        self.targets = targets
        self.rng = random.Random(seed)
        self.zotero_data_dir = zotero_data_dir
        self.fulltext_cap = fulltext_cap
        self.max_tries_per_cell = max_tries_per_cell
        self.achieved: dict[str, Counter] = {"type": Counter(), "format": Counter(), "length": Counter()}
        self.rejected: Counter = Counter()
        self._cell_count: Counter = Counter()
        self._texts: dict[str, dict] = {}

    def frame(self, items: list[dict], entries: dict[str, int], scope: set[str] | None) -> dict[tuple, list]:
        """Cells of (type group, format) → candidate (record, attachment) pairs."""
        by_key = {it["key"]: it for it in items}
        cells: dict[tuple, list] = {}
        for it in items:
            if it["itemType"] != "attachment" or it.get("linkMode") not in FILE_LINK_MODES:
                continue
            if entries.get(it["key"], 0) <= 0:
                continue
            parent = by_key.get(it.get("parentItem") or "")
            if parent is None or parent.get("parentItem") or parent["itemType"] in NON_RECORD_TYPES:
                continue
            if scope is not None and parent["key"] not in scope:
                continue
            cell = (type_group(parent["itemType"]), format_of(it.get("contentType") or ""))
            cells.setdefault(cell, []).append((parent, it))
        for pairs in cells.values():
            self.rng.shuffle(pairs)
        return cells

    def _deficit(self, cell: tuple, n_total: int) -> float:
        """Target count of a (type, format) cell minus what it holds so far."""
        t, f = cell
        return self.targets["type"][t] * self.targets["format"][f] * n_total - self._cell_count[cell]

    def draw(self, cells: dict[tuple, list], n: int) -> list[dict]:
        """Fill the (type, format) cell with the largest deficit first.

        A draw whose length bucket is already over quota is deferred, not
        discarded: on a small scope the frame is the scarce thing, so once every
        cell is empty the deferred pairs come back and the length quota yields.
        The summary counts both the deferrals and how many came back.
        """
        self._cell_count = Counter()
        out: list[dict] = []
        tries: Counter = Counter()
        deferred: dict[tuple, list] = {}
        length_quota = True
        while len(out) < n:
            live = [c for c, pairs in cells.items() if pairs]
            if not live and deferred and length_quota:
                cells = deferred
                deferred = {}
                length_quota = False
                self.rejected["length-quota-released"] = sum(len(v) for v in cells.values())
                continue
            if not live:
                logging.warning("frame exhausted after %d samples", len(out))
                break
            cell = max(live, key=lambda c: (self._deficit(c, n), self.rng.random()))
            record, attachment = cells[cell].pop()
            tries[cell] += 1
            row = self.one(record, attachment)
            if row is None:
                self.rejected["no-eligible-paragraph"] += 1
                continue
            bucket = row["length_bucket"]
            over = self.achieved["length"][bucket] - self.targets["length"][bucket] * n
            if length_quota and over >= 1 and tries[cell] <= self.max_tries_per_cell:
                self.rejected["length-over-quota"] += 1
                deferred.setdefault(cell, []).append((record, attachment))
                continue
            tries[cell] = 0
            self._cell_count[cell] += 1
            self.achieved["type"][cell[0]] += 1
            self.achieved["format"][cell[1]] += 1
            self.achieved["length"][bucket] += 1
            out.append(row)
        return out

    def _fulltext(self, key: str) -> dict:
        """One GET per attachment, however many times a pair is drawn."""
        if key not in self._texts:
            self._texts[key] = self.lib.get_json(f"items/{key}/fulltext")
        return self._texts[key]

    def one(self, record: dict, attachment: dict) -> dict | None:
        """One sampled paragraph of one attachment, with its whole chain, or None
        when the text holds no eligible paragraph."""
        doc = self._fulltext(attachment["key"])
        content = doc.get("content") or ""
        paragraphs = T.split_paragraphs(content)
        if not paragraphs:
            return None
        chosen = self.rng.choice(paragraphs)
        index = T.page_index(content, chosen.offset)
        label, label_source = page_label(attachment_file(attachment, self.zotero_data_dir), index)
        heading = T.section_heading(content, chosen.offset)
        chars = doc.get("totalChars") or doc.get("indexedChars") or len(content)
        chain = chain_of(record)
        chain["page_index"] = {"value": index, "measured": index is not None}
        chain["page_label"] = {"value": label, "measured": label is not None, "source": label_source}
        chain["section"] = {"value": heading, "measured": heading is not None}
        detected = T.detect_language(chosen.text)
        record_language = normalise_language(str(record.get("language") or ""))
        # The paragraph's own text decides the lane. When it decides nothing — a
        # legacy encoding that lost its diacritics, a passage of numbers — the
        # record's field stands in, and the row says which of the two it was.
        if detected != "und":
            language, language_source = detected, "text"
        elif record_language not in ("empty", "unmapped"):
            language, language_source = record_language, "record-field"
        else:
            language, language_source = "und", "none"
        return {
            "item_key": record["key"],
            "attachment_key": attachment["key"],
            "item_type": record["itemType"],
            "type_group": type_group(record["itemType"]),
            "format": format_of(attachment.get("contentType") or ""),
            "content_type": attachment.get("contentType") or "",
            "record_language": record_language,
            "language": language,
            "language_source": language_source,
            "length_chars": chars,
            "length_bucket": T.length_bucket(chars, tuple(self.targets["length_cuts_chars"])),
            "pages_total": doc.get("totalPages"),
            "pages_indexed": doc.get("indexedPages"),
            "offset": chosen.offset,
            "within_default_cap": chosen.offset < self.fulltext_cap,
            "paragraph": chosen.text,
            "chain": chain,
        }


# ---------------------------------------------------------------- summary (aggregates only)


def summarise(rows: list[dict], sampler: Sampler, n_requested: int) -> dict:
    """Counts and rates only. Nothing here identifies an item."""
    n = len(rows)
    chain_elements = ("title", "creators", "date", "identifier", "page_index", "page_label", "section")
    measured = {aggregate_key(e): sum(1 for r in rows if r["chain"][e]["measured"]) for e in chain_elements}
    compound = [r for r in rows if r["chain"]["compound"]["applies"]]
    measured["compound_container"] = sum(1 for r in compound if r["chain"]["compound"]["measured"])
    label_sources = Counter(r["chain"]["page_label"]["source"] for r in rows)
    identifiers = Counter(r["chain"]["identifier"]["kind"] or "none" for r in rows)

    def marginal(name: str, keys) -> dict:
        """Target counts are the plan (`n_requested` times the census share);
        achieved counts are what the frame supplied."""
        return {k: {"target": round(sampler.targets[name][k] * n_requested, 1), "achieved": sampler.achieved[name][k]}
                for k in keys}

    return {
        "n_requested": n_requested,
        "n": n,
        "rejected": dict(sampler.rejected),
        "strata": {
            "type": marginal("type", (*TYPE_GROUPS, "other")),
            "format": marginal("format", FORMATS),
            "length": marginal("length", ("short", "medium", "long", "very-long")),
            "length_cuts_chars": list(sampler.targets["length_cuts_chars"]),
        },
        "language": {
            "answer": dict(Counter(r["language"] for r in rows).most_common()),
            "answer_language_source": dict(Counter(r["language_source"] for r in rows)),
            "record_field": dict(Counter(r["record_language"] for r in rows).most_common()),
        },
        "chain_measured": measured,
        "chain_not_measured": {e: n - v for e, v in measured.items() if e != "compound_container"},
        "compound_documents": len(compound),
        "page_label_source": dict(label_sources),
        "identifier_kind": dict(identifiers),
        "within_default_cap": sum(1 for r in rows if r["within_default_cap"]),
        "beyond_default_cap": sum(1 for r in rows if not r["within_default_cap"]),
        "default_cap_chars": sampler.fulltext_cap,
        "census": {
            "measured_at": sampler.targets["census_measured_at"],
            "library_version": sampler.targets["census_library_version"],
        },
    }


def sample(args: argparse.Namespace, fetch: Fetch = http_fetch) -> tuple[list[dict], dict, dict[str, str]]:
    """Run the sampler. Returns the private rows, the aggregate summary and the
    API headers of the listing (library version, Zotero version)."""
    census = json.loads(Path(args.census).read_text(encoding="utf-8"))
    targets = census_targets(census)
    lib = Library(fetch, args.base_url, "users/0", page_size=args.page_size)
    logging.info("listing the library")
    items = list(lib.items())
    headers = dict(lib.last_headers)
    entries = lib.fulltext_entries()
    scope = None
    if args.scope_keys:
        scope = {line.strip() for line in Path(args.scope_keys).read_text().splitlines() if line.strip()}
        logging.info("scope: %d item keys", len(scope))
    sampler = Sampler(lib, targets, args.seed, Path(args.zotero_data_dir).expanduser() if args.zotero_data_dir else None,
                      fulltext_cap=args.fulltext_cap)
    cells = sampler.frame(items, entries, scope)
    frame_pairs = sum(len(v) for v in cells.values())
    logging.info("frame: %d pairs in %d cells", frame_pairs, len(cells))
    rows = sampler.draw(cells, args.n)
    summary = summarise(rows, sampler, args.n)
    summary["frame_pairs"] = frame_pairs
    summary["scope_items"] = len(scope) if scope is not None else None
    summary["seed"] = args.seed
    return rows, summary, headers


def write_outputs(rows: list[dict], summary: dict, work_dir: Path) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    with (work_dir / "sample.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (work_dir / "sample-summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def add_arguments(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Zotero local API root")
    ap.add_argument("--census", type=Path, required=True, help="the census artifact the strata target")
    ap.add_argument("--n", type=int, default=100, help="answer paragraphs to sample")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--scope-keys", type=Path, help="restrict records to these item keys (one per line)")
    ap.add_argument("--zotero-data-dir", default="", help="Zotero data directory, for PDF page labels (read-only)")
    ap.add_argument("--fulltext-cap", type=int, default=DEFAULT_FULLTEXT_CAP,
                    help="the target's per-item body-text cap, for the reachability flag")
    ap.add_argument("--page-size", type=int, default=100)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(ap)
    ap.add_argument("--work-dir", type=Path, required=True, help="private output directory (never committed)")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows, summary, _ = sample(args)
    write_outputs(rows, summary, args.work_dir)
    logging.info("sampled %d paragraphs into %s", len(rows), args.work_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
