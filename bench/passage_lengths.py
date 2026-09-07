"""The passage-length distribution of the committed golden export (ticket 0029).

R32 is a rate — 150 ms per passage as the MUST, 75 ms as the SHOULD — and
SPEC.md §5.2.9 names the cost of stating it that way in as many words: *"a rate
measured on one passage-length distribution does not transfer to another, which
is why the fixture's distribution is pinned with the corpus."* Nothing computed
that distribution until this script. Without it a reading of R32 taken over the
Menagerie is void: the same milliseconds-per-passage divide differently when the
corpus changes underneath them, and a corpus edit is indistinguishable from a
regression.

**What a passage is here.** The `ChunkRecord` the shipped index build creates
and embeds — the unit `zotero_index status` counts as `passages`, and therefore
the unit R32's per-passage rate is divided by. Two populations make it up, cut
by `fork/src/features/search/chunker.ts` (`chunkText`) at the sizes
`index-manager.ts` passes:

* **metadata** — one pass over each top-level item's `itemText` (title,
  abstract, creators, tags, date, publication, book title, note joined by
  `. `), chunked at 512 characters with 64 of overlap;
* **fulltext** — per ITEM, not per attachment: `fulltext-source.ts` concatenates
  every attachment of the item that Zotero's `/fulltext` census names, in the
  attachment-listing order, capped at `index_fulltext_max_chars` characters for
  the item as a whole, joined by a blank line, then chunked at 1200 characters
  with 150 of overlap.

Own-words passages (notes, annotations) are a third population the build can
hold; the replayed export produces none, and the cross-check below reads that
from the build's own status rather than assuming it.

**Characters, not tokens.** The shipped chunker cuts on characters. SPEC.md
§5.2.2 ratifies a *token* geometry (budget `min(500, modelMax) − specials −
prefix`, 120 minimum, 48 overlap) which `bench/geometry.py` implements and
`bench/passage_census.py` counts with — that is seg/1's geometry, and seg/1 is
not built. So the two populations are different and this artifact measures the
one R32 can be read against today. A token census over this export would need a
tokenizer this machine does not carry (no `tokenizers`, no `transformers`, no
model cache); the experiment that would produce it is
`bench/passage_census.mjs` run over `export/fulltext/`, and it is named here
rather than estimated.

**Staleness.** The artifact carries the export's `sha256` — the same digest
`golden_gate.load_export` computes and the golden gate reports as
`export_sha256` — its `recipe_sha256`, and the manifest counters the population
derives from. `--check` recomputes and refuses when they have moved, so a
distribution read against a different export is detectably stale rather than
silently wrong. `tests/test_passage_lengths.py` runs that check on the
committed pair in the fast tier.

    python3 bench/passage_lengths.py
    python3 bench/passage_lengths.py --check
    python3 bench/passage_lengths.py --output bench/fixtures/passage-lengths.json
"""
import argparse
import importlib.util
import json
import logging
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
EXPORT = REPO / "bench" / "fixtures" / "export"
ARTIFACT = REPO / "bench" / "fixtures" / "passage-lengths.json"
REPORT = REPO / "bench" / "results" / "golden" / "report.json"

SCHEMA = "menagerie-passage-lengths/v1"

#: `chunkText`'s defaults, which `addMetadata` takes (index-manager.ts:2072).
METADATA_CHUNK_SIZE = 512
METADATA_CHUNK_OVERLAP = 64
#: `FULLTEXT_CHUNK_SIZE` / `FULLTEXT_CHUNK_OVERLAP` (index-manager.ts:73-74), which
#: `addFulltext` and `addOwnWords` pass.
FULLTEXT_CHUNK_SIZE = 1200
FULLTEXT_CHUNK_OVERLAP = 150

#: The fields `itemText` concatenates, in its order (index-manager.ts:112).
ITEM_TEXT_FIELDS = ("title", "abstractNote", "_creators", "_tags", "date",
                    "publicationTitle", "bookTitle", "note")

#: ECMAScript's `\s`, spelled out: Python's `\s` and JavaScript's differ at both ends
#: (Python adds U+001C..U+001F, JavaScript adds U+FEFF), and the chunker's whitespace
#: collapse decides every passage boundary, so the class is not left to a default.
_JS_SPACE = (" \\t\\n\\v\\f\\r\\u0020\\u00a0\\u1680\\u2000-\\u200a"
             "\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff")
_WHITESPACE_RUN = re.compile(f"[{_JS_SPACE}]+")
_WORD_RUN = re.compile(r"\S+")

#: Quantiles the artifact reports. A mean alone hides the pathology this corpus was
#: built to contain, so the tail is reported at three resolutions above the median.
QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)

#: How many extremes each tail listing names, by key and slug.
TAIL_SIZE = 10

#: R32's two bounds, in milliseconds per passage: the MUST and the SHOULD. Quoted here
#: only to turn the pinned passage count into the wall clock a build over this fixture
#: would have to meet; SPEC.md owns the numbers and §5.2.9 owns their allocation.
R32_MUST_MS = 150
R32_SHOULD_MS = 75


def _load_golden_gate() -> Any:
    """The export loader, from its one owner.

    `golden_gate.load_export` validates the manifest, resolves parents, and computes the
    `export_sha256` the gate reports. Re-deriving any of that here would make this file a
    second owner of the export's identity, which is exactly the drift the stamp exists to
    catch.
    """
    spec = importlib.util.spec_from_file_location(
        "golden_gate", Path(__file__).resolve().parent / "golden_gate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("golden_gate", module)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- the chunker


def chunk_spans(text: str, size: int, overlap: int) -> list[tuple[int, int]]:
    """`chunkText`'s passage boundaries, as `[start, end)` in the WHITESPACE-COLLAPSED text.

    A faithful port of `fork/src/features/search/chunker.ts`: collapse every whitespace run
    to one space and trim; a text at or under `size` is one passage; otherwise walk forward
    cutting at `size`, snapping the cut back to the last space when that space falls past
    the halfway mark, and restarting `overlap` characters before the cut.

    Spans rather than strings because a fulltext passage has to be attributed back to the
    attachment whose characters it holds, and only an offset can do that.

    JavaScript indexes strings in UTF-16 code units and Python in code points; the two
    agree exactly while no character is outside the BMP. `astral_characters` in the
    artifact counts the ones that would break the agreement, so the assumption is a
    measurement rather than a hope.
    """
    clean = _WHITESPACE_RUN.sub(" ", text).strip()
    if not clean:
        return []
    if len(clean) <= size:
        return [(0, len(clean))]
    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(clean):
        end = min(start + size, len(clean))
        if end < len(clean):
            # `lastIndexOf(' ', end)` searches backward from `end` INCLUSIVE.
            last_space = clean.rfind(" ", 0, end + 1)
            if last_space > start + size / 2:
                end = last_space
        spans.append((start, end))
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return spans


def collapse(text: str) -> str:
    """The chunker's own normalisation, exposed so callers measure the text it measures."""
    return _WHITESPACE_RUN.sub(" ", text).strip()


def item_text(data: dict[str, Any]) -> str:
    """`itemText(d)` (index-manager.ts:112): the item's own words, in the build's order."""
    creators = " ".join(
        name for name in
        ((c.get("lastName") or c.get("name")) for c in data.get("creators") or [])
        if name
    )
    tags = " ".join(t.get("tag") for t in data.get("tags") or [] if t.get("tag"))
    values = {"_creators": creators, "_tags": tags}
    parts = [values.get(field, data.get(field)) for field in ITEM_TEXT_FIELDS]
    return ". ".join(str(part) for part in parts if part)


# --------------------------------------------------------------------------- the population


def census_keys(export: Any) -> dict[str, bool]:
    """Attachment keys Zotero's `/fulltext?since=0` names, and whether the route serves text.

    The census and the route are two different facts, and the build feels both: an
    `indexed-not-served` attachment (a content type outside `isCachedMIMEType`) and a
    failure control Zotero marked missing at version 0 are both LISTED, so they occupy a
    slot in the item's attachment list, and both answer 404, so they contribute no
    characters. Folding them into "absent" would silently move the per-item cap.
    """
    census: dict[str, bool] = {}
    for key, row in export.attachments.items():
        if row.get("fulltext_file"):
            census[key] = True
        elif row.get("fulltext_version") is not None:
            census[key] = False
    return census


def attachment_order(export: Any) -> list[str]:
    """Attachment keys in the order the build walks them.

    `createFulltextSource` pages `itemType=attachment` and pushes each key onto its
    parent's list in arrival order; the replay answers that listing in `items.json` order.
    The order is not cosmetic: it decides which attachment of a multi-attachment item is
    cut off by the per-item character cap.
    """
    return [key for key, data in export.items.items() if data.get("itemType") == "attachment"]


class Passage:
    """One `ChunkRecord` the build would create, with what it is made of."""

    __slots__ = ("id", "item_key", "source", "text", "attachments")

    def __init__(self, passage_id: str, item_key: str, source: str, text: str,
                 attachments: tuple[str, ...]):
        self.id = passage_id
        self.item_key = item_key
        self.source = source
        self.text = text
        self.attachments = attachments

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def bytes(self) -> int:
        return len(self.text.encode("utf-8"))

    @property
    def words(self) -> int:
        return len(_WORD_RUN.findall(self.text))


def build_passages(export: Any, max_chars: int) -> tuple[list[Passage], dict[str, Any]]:
    """Every passage the shipped build makes of this export, and how it made them.

    Returns the passages and a per-attachment ledger: characters available, characters
    the per-item cap let through, and how many passages hold any of them. The ledger is
    where the corpus's pathologies are legible — an attachment that contributes nothing
    is a different finding from one that contributes 40 000 characters and is cut.
    """
    census = census_keys(export)
    order = attachment_order(export)

    by_item: dict[str, list[str]] = defaultdict(list)
    for key in order:
        if key not in census:
            continue
        by_item[export.parent_of.get(key, key)].append(key)

    ledger: dict[str, dict[str, Any]] = {}
    for key, row in export.attachments.items():
        content = export.fulltext(key) if row.get("fulltext_file") else None
        ledger[key] = {
            "attachment_id": row.get("attachment_id"),
            "attachment_key": key,
            "parent_key": export.parent_of.get(key),
            "terminal_state": row.get("terminal_state"),
            "format": export.format_of(key),
            "content_type": str(export.items.get(key, {}).get("contentType") or ""),
            "language": row.get("language"),
            "in_census": key in census,
            "route_serves_text": census.get(key, False),
            "chars_available": None if content is None else len(content),
            "chars_offered": 0,
            "chars_indexed": 0,
            "passages": 0,
            "reason_no_passage": None,
        }

    passages: list[Passage] = []
    top_items = [(key, data) for key, data in export.items.items()
                 if not data.get("parentItem") and data.get("itemType") != "attachment"]

    for item_key, data in top_items:
        text = item_text(data)
        clean = collapse(text)
        for index, (start, end) in enumerate(
                chunk_spans(text, METADATA_CHUNK_SIZE, METADATA_CHUNK_OVERLAP)):
            passages.append(Passage(f"{item_key}#{index}", item_key, "metadata",
                                    clean[start:end].strip(), ()))

        keys = by_item.get(item_key)
        if not keys:
            continue
        # `textFor`: concatenate under one per-ITEM budget, in listing order.
        parts: list[str] = []
        owners: list[str] = []
        used = 0
        for key in keys:
            if max_chars > 0 and used >= max_chars:
                ledger[key]["reason_no_passage"] = "the item's character cap was already spent"
                continue
            content = export.fulltext(key) if census[key] else None
            if content is None:
                ledger[key]["reason_no_passage"] = (
                    "listed by the census, 404 on its fulltext route: "
                    f"{ledger[key]['terminal_state']}")
                continue
            if not content:
                ledger[key]["reason_no_passage"] = "Zotero's extraction returned an empty body"
                continue
            ledger[key]["chars_offered"] = len(content)
            piece = content[: max_chars - used] if max_chars > 0 else content
            parts.append(piece)
            owners.append(key)
            used += len(piece)
            ledger[key]["chars_indexed"] = len(piece)
        if not parts:
            continue

        # Where each attachment's characters land in the COLLAPSED text the chunker cuts.
        # Collapsing distributes over the blank-line join once every part is non-blank —
        # `collapse(a + "\n\n" + b) == collapse(a) + " " + collapse(b)` — so the segment
        # bounds are exact rather than interpolated, and the assertion below says so.
        segments = [(key, collapse(piece)) for piece, key in zip(parts, owners)]
        segments = [(key, text) for key, text in segments if text]
        clean = " ".join(text for _, text in segments)
        assert clean == collapse("\n\n".join(parts)), item_key
        bounds: list[tuple[int, int, str]] = []
        cursor = 0
        for key, text in segments:
            bounds.append((cursor, cursor + len(text), key))
            cursor += len(text) + 1

        for index, (start, end) in enumerate(
                chunk_spans(clean, FULLTEXT_CHUNK_SIZE, FULLTEXT_CHUNK_OVERLAP)):
            holders = tuple(key for begin, stop, key in bounds if begin < end and stop > start)
            passages.append(Passage(f"{item_key}#f{index}", item_key, "fulltext",
                                    clean[start:end].strip(), holders))
            for key in holders:
                ledger[key]["passages"] += 1

    for key, row in ledger.items():
        if row["passages"] or row["reason_no_passage"]:
            continue
        if not row["in_census"]:
            row["reason_no_passage"] = (
                "absent from Zotero's fulltext census: "
                f"{row['terminal_state']} ({row['content_type'] or 'no content type'})")
    return passages, ledger


# --------------------------------------------------------------------------- the reading


def quantiles(values: list[int]) -> dict[str, float | int | None]:
    """The shape of a distribution in the terms a rate has to be read against."""
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    reading: dict[str, float | int | None] = {
        "count": len(ordered),
        "total": sum(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "mean": sum(ordered) / len(ordered),
        "stdev": statistics.pstdev(ordered) if len(ordered) > 1 else 0.0,
    }
    for q in QUANTILES:
        # Nearest-rank: the reported value is one the corpus actually holds, so a
        # quantile can be checked against a passage rather than only against arithmetic.
        rank = max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))
        reading[f"p{int(q * 100):02d}"] = ordered[rank]
    return reading


def histogram(values: list[int], edges: tuple[int, ...]) -> dict[str, int]:
    """Counts per half-open bucket, with an explicit overflow bucket."""
    buckets: dict[str, int] = {}
    previous = 0
    for edge in edges:
        buckets[f"{previous}-{edge - 1}"] = sum(1 for v in values if previous <= v < edge)
        previous = edge
    buckets[f"{previous}+"] = sum(1 for v in values if v >= previous)
    return buckets


def describe(passages: list[Passage]) -> dict[str, Any]:
    """One population, measured three ways.

    Characters are what the chunker cuts on and the only exact unit. Bytes and words are
    reported beside them because neither transfers across scripts the way a reader of a
    per-passage rate would assume: a 1200-character passage of Chinese is three times the
    bytes and one word of a 1200-character passage of English. All three are counts taken
    on the text; none is an estimate of tokens, which is the unit an embedder charges by
    and which nothing here computes.
    """
    chars = [p.chars for p in passages]
    return {
        "chars": quantiles(chars),
        "bytes": quantiles([p.bytes for p in passages]),
        "words": quantiles([p.words for p in passages]),
        "bytes_per_char": (sum(p.bytes for p in passages) / sum(chars)) if chars else None,
        "histogram_chars": histogram(chars, (100, 200, 400, 600, 800, 1000, 1150, 1200)),
    }


def by_dimension(passages: list[Passage], ledger: dict[str, dict[str, Any]],
                 field: str) -> dict[str, Any]:
    """The distribution split on one attachment property, plus the metadata population.

    A fulltext passage can straddle two attachments; it is counted under each value it
    touches, and `passages_counted` says so rather than letting the split sum to something
    other than the population.
    """
    groups: dict[str, list[Passage]] = defaultdict(list)
    for passage in passages:
        if passage.source == "metadata":
            groups["(metadata)"].append(passage)
            continue
        values = {ledger[key][field] for key in passage.attachments} or {None}
        for value in values:
            groups[str(value)].append(passage)
    return {
        name: {"passages": len(rows), **describe(rows)}
        for name, rows in sorted(groups.items())
    }


def tails(passages: list[Passage], ledger: dict[str, dict[str, Any]],
          size: int = TAIL_SIZE) -> dict[str, Any]:
    """The extremes, named by attachment key and slug — never by title.

    A title is not an identifier here: the corpus deliberately carries the same work in
    several renderings and languages, and several of them share a title.

    Two orderings, because the character tail is nearly degenerate: 1 843 of the 2 276
    fulltext passages sit in one 50-character bucket below the chunk size, so a top-ten by
    characters is a list of ties. The byte tail is not degenerate — the same 1 200
    characters cost 1 200 bytes in English and 3 000 in Devanagari — and it is the one that
    says where an embedding rate would diverge.
    """

    def row(passage: Passage) -> dict[str, Any]:
        return {
            "id": passage.id,
            "source": passage.source,
            "chars": passage.chars,
            "bytes": passage.bytes,
            "words": passage.words,
            "item_key": passage.item_key,
            "attachments": [
                {"attachment_key": key, "attachment_id": ledger[key]["attachment_id"]}
                for key in passage.attachments
            ],
        }

    by_chars = sorted(passages, key=lambda p: (p.chars, p.id))
    by_bytes = sorted(passages, key=lambda p: (p.bytes, p.id))
    return {
        "shortest_chars": [row(p) for p in by_chars[:size]],
        "longest_chars": [row(p) for p in reversed(by_chars[-size:])],
        "lightest_bytes": [row(p) for p in by_bytes[:size]],
        "heaviest_bytes": [row(p) for p in reversed(by_bytes[-size:])],
    }


def recipe_of_parent(export: Any) -> dict[str, str]:
    """Parent item key to its recipe id — the slug a reader can look up in `recipe.json`.

    The manifest's `parents` block is where the binding lives; an item absent from it is
    reported by key alone rather than given a guessed name.
    """
    return {row["parent_key"]: row["recipe_id"]
            for row in export.manifest.get("parents") or []
            if row.get("parent_key") and row.get("recipe_id")}


def per_item(passages: list[Passage], slugs: dict[str, str]) -> dict[str, Any]:
    """Passages per top-level item — the unit both chunking passes actually run over.

    The per-item character cap bounds this directly: 40 000 characters at a 1 200 chunk
    with 150 of overlap is at most 39 body passages, and the median says how many of the
    corpus's items reach it.
    """
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for passage in passages:
        counts[passage.item_key][passage.source] += 1
    return {
        "items": len(counts),
        "all": quantiles([sum(c.values()) for c in counts.values()]),
        "metadata": quantiles([c["metadata"] for c in counts.values() if c["metadata"]]),
        "fulltext": quantiles([c["fulltext"] for c in counts.values() if c["fulltext"]]),
        "most_passages": sorted(
            ({"item_key": key, "recipe_id": slugs.get(key), "passages": sum(c.values()),
              "fulltext": c["fulltext"]} for key, c in counts.items()),
            key=lambda r: (-r["passages"], str(r["recipe_id"])))[:TAIL_SIZE],
        "items_with_no_body_text": sorted(
            ({"item_key": key, "recipe_id": slugs.get(key)}
             for key, c in counts.items() if not c["fulltext"]),
            key=lambda r: str(r["recipe_id"])),
    }


def per_attachment(ledger: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """What each attachment contributed, and which ones produced nothing.

    Three quantities that are easy to conflate and that mean different things for a rate:
    `chars_available` is what the export holds, `chars_indexed` is what the per-item cap
    let through, and `passages` is what the chunker made of it. An attachment with
    `chars_available` 0 was measured and found empty; one with `chars_available` null was
    never served, which is not the same finding.
    """
    rows = list(ledger.values())
    truncated = [r for r in rows
                 if r["chars_offered"] and r["chars_indexed"] < r["chars_offered"]]
    silent = [r for r in rows if not r["passages"]]
    return {
        "attachments": len(rows),
        "contributing": sum(1 for r in rows if r["passages"]),
        "passages_per_attachment": quantiles(
            [r["passages"] for r in rows if r["passages"]]),
        "most_passages": sorted(
            ({"attachment_id": r["attachment_id"], "attachment_key": r["attachment_key"],
              "language": r["language"], "format": r["format"], "passages": r["passages"]}
             for r in rows if r["passages"]),
            key=lambda r: (-r["passages"], str(r["attachment_id"])))[:TAIL_SIZE],
        "fewest_passages": sorted(
            ({"attachment_id": r["attachment_id"], "attachment_key": r["attachment_key"],
              "language": r["language"], "format": r["format"], "passages": r["passages"],
              "chars_indexed": r["chars_indexed"]}
             for r in rows if r["passages"]),
            key=lambda r: (r["passages"], str(r["attachment_id"])))[:TAIL_SIZE],
        "chars_indexed": quantiles([r["chars_indexed"] for r in rows if r["chars_indexed"]]),
        "truncated_by_the_item_cap": sorted(
            ({
                "attachment_id": r["attachment_id"],
                "attachment_key": r["attachment_key"],
                "language": r["language"],
                "format": r["format"],
                "chars_available": r["chars_available"],
                "chars_offered": r["chars_offered"],
                "chars_indexed": r["chars_indexed"],
                "dropped": r["chars_offered"] - r["chars_indexed"],
            } for r in truncated),
            key=lambda r: -r["dropped"],
        ),
        "no_passage": sorted(
            ({
                "attachment_id": r["attachment_id"],
                "attachment_key": r["attachment_key"],
                "terminal_state": r["terminal_state"],
                "content_type": r["content_type"],
                "chars_available": r["chars_available"],
                "reason": r["reason_no_passage"],
            } for r in silent),
            key=lambda r: str(r["attachment_id"]),
        ),
    }


def cross_check(passages: list[Passage], status: dict[str, Any] | None) -> dict[str, Any]:
    """The population against a real run of the shipped build over the same export.

    The counting model above is a re-implementation of two TypeScript files, and a
    re-implementation that agrees with nothing is a guess. `bench/results/golden/report.json`
    holds the status a built `fork/` reported after building this export through the
    offline replay, so its `passages`, `fulltextPassages`, `items` and `fulltextItems` are
    the same four numbers computed by the code that ships. A disagreement is reported as a
    disagreement; it is not repaired here.
    """
    counted = {
        "passages": len(passages),
        "metadata_passages": sum(1 for p in passages if p.source == "metadata"),
        "fulltext_passages": sum(1 for p in passages if p.source == "fulltext"),
        "items": len({p.item_key for p in passages if p.source == "metadata"}),
        "fulltext_items": len({p.item_key for p in passages if p.source == "fulltext"}),
    }
    if status is None:
        return {"counted": counted, "compared": None,
                "reason": "no golden-gate report is available to compare against"}
    reported = {
        "passages": status.get("passages"),
        "metadata_passages": (status.get("passages", 0)
                              - status.get("fulltextPassages", 0)
                              - status.get("ownWordsPassages", 0)),
        "fulltext_passages": status.get("fulltextPassages"),
        "items": status.get("items"),
        "fulltext_items": status.get("fulltextItems"),
    }
    return {
        "counted": counted,
        "compared": reported,
        "own_words_passages_reported": status.get("ownWordsPassages"),
        "differences": {k: counted[k] - reported[k] for k in counted
                        if reported.get(k) is not None and counted[k] != reported[k]},
        "agrees": all(counted[k] == reported[k] for k in counted if reported.get(k) is not None),
    }


def build(export: Any, status: dict[str, Any] | None) -> dict[str, Any]:
    max_chars = export.manifest.get("index_fulltext_max_chars")
    if not isinstance(max_chars, int):
        raise SystemExit("the export manifest carries no index_fulltext_max_chars")
    passages, ledger = build_passages(export, max_chars)
    astral = sum(1 for p in passages for ch in p.text if ord(ch) > 0xFFFF)
    metadata_chars = [p.chars for p in passages if p.source == "metadata"]
    return {
        "schema": SCHEMA,
        "ticket": "tickets/0029-the-golden-fixture-corpus-and-a-zotero-f.erg",
        "probe": "bench/passage_lengths.py",
        "requirement": "R32 (SPEC.md): the buildtime bound is a rate per passage; "
                       "SPEC.md §5.2.9 requires the fixture's passage-length distribution "
                       "to be pinned with the corpus, because a rate measured on one "
                       "distribution does not transfer to another",
        "export": {
            "root": str(export.root.relative_to(REPO)),
            "sha256": export.sha256,
            "recipe_sha256": export.manifest.get("recipe_sha256"),
            "library_version": export.manifest.get("library_version"),
            "schema_version": export.manifest.get("schema_version"),
            "attachment_count": export.manifest.get("attachment_count"),
            "parent_item_count": export.manifest.get("parent_item_count"),
            "index_fulltext_max_chars": max_chars,
            "reindex_mode": (export.manifest.get("reindex") or {}).get("mode"),
            "caps": (export.extraction() or {}).get("caps"),
        },
        "geometry": {
            "unit": "the ChunkRecord the shipped build embeds; `passages` in zotero_index status",
            "cut_on": "characters of the whitespace-collapsed text",
            "metadata": {"size": METADATA_CHUNK_SIZE, "overlap": METADATA_CHUNK_OVERLAP,
                         "per": "top-level item, over itemText"},
            "fulltext": {"size": FULLTEXT_CHUNK_SIZE, "overlap": FULLTEXT_CHUNK_OVERLAP,
                         "per": "top-level item, over its census attachments concatenated "
                                "under one per-item character cap"},
            "source": ["fork/src/features/search/chunker.ts",
                       "fork/src/features/search/index-manager.ts",
                       "fork/src/features/search/fulltext-source.ts"],
            "not_this": "SPEC.md §5.2.2's ratified TOKEN geometry (budget min(500, modelMax) "
                        "− specials − prefix, 120 minimum, 48 overlap), implemented in "
                        "bench/geometry.py and counted by bench/passage_census.py. That is "
                        "seg/1's geometry and seg/1 is not built; the two populations differ "
                        "and this artifact measures the one a reading of R32 divides by today",
            "astral_characters": astral,
            "astral_note": "JavaScript indexes in UTF-16 code units, Python in code points; "
                           "at zero astral characters the two are the same index",
            "metadata_size_binds": bool(metadata_chars) and max(metadata_chars) >= METADATA_CHUNK_SIZE,
            "metadata_size_note": "no item's own text reaches the 512-character metadata "
                                  "chunk size (the longest is "
                                  f"{max(metadata_chars) if metadata_chars else 0}), so every "
                                  "record is one passage and this corpus does not exercise "
                                  "that size. A change to it would not move any number here; "
                                  "a change to the body size or overlap would",
        },
        "population": {
            "passages": len(passages),
            "by_source": dict(sorted(Counter(p.source for p in passages).items())),
            "items_with_metadata": len({p.item_key for p in passages if p.source == "metadata"}),
            "items_with_fulltext": len({p.item_key for p in passages if p.source == "fulltext"}),
        },
        "distribution": {
            "all": describe(passages),
            "metadata": describe([p for p in passages if p.source == "metadata"]),
            "fulltext": describe([p for p in passages if p.source == "fulltext"]),
        },
        "by_language": by_dimension(passages, ledger, "language"),
        "by_format": by_dimension(passages, ledger, "format"),
        "tails": tails(passages, ledger),
        "per_item": per_item(passages, recipe_of_parent(export)),
        "per_attachment": per_attachment(ledger),
        "cross_check": cross_check(passages, status),
        "r32_arithmetic": {
            "passages": len(passages),
            "must_ms_per_passage": R32_MUST_MS,
            "should_ms_per_passage": R32_SHOULD_MS,
            "must_seconds": len(passages) * R32_MUST_MS / 1000,
            "should_seconds": len(passages) * R32_SHOULD_MS / 1000,
            "note": "arithmetic on the pinned count, not a measured build. It says what a "
                    "full build over THIS export has to come in under for the rate to hold, "
                    "and it is void the moment the count above moves — which is the whole "
                    "reason the count is pinned to an export sha",
            "machine": "R32's reference machine is SPEC.md §5.2.9's, not this one; no build "
                       "was timed here",
        },
        "not_measured": {
            "tokens": "no tokenizer is installed on this machine (no `tokenizers`, no "
                      "`transformers`, no model cache), so token lengths are absent rather "
                      "than estimated. The experiment: bench/passage_census.mjs over "
                      "export/fulltext/ with the incumbent embedder's own tokenizer",
            "own_words": "the replayed export produces no note or annotation passages; the "
                         "cross-check reads that from the build's own ownWordsPassages "
                         "rather than assuming it",
        },
    }


def load_status(report: Path) -> dict[str, Any] | None:
    if not report.is_file():
        return None
    payload = json.loads(report.read_text(encoding="utf-8"))
    return ((payload.get("run") or {}).get("build") or {}).get("status")


def stale(committed: dict[str, Any], fresh: dict[str, Any]) -> list[str]:
    """Every way a committed artifact no longer describes the export beside it.

    The export's identity is the whole point: a distribution read against a different
    export is not approximately right, it is void, and this is what makes that mechanical
    rather than a matter of noticing. Both the stamp and the population are compared,
    because the two fail apart — a manifest edited without touching any body text moves
    the sha and not the counts, and an edit under an unchanged manifest would move the
    counts and not the sha.
    """
    findings = []
    if committed.get("schema") != fresh["schema"]:
        findings.append(f"schema {committed.get('schema')!r}, expected {fresh['schema']!r}")
    for field in ("sha256", "recipe_sha256", "library_version", "index_fulltext_max_chars"):
        was, now = committed.get("export", {}).get(field), fresh["export"][field]
        if was != now:
            findings.append(f"export.{field}: artifact {was!r}, export now {now!r}")
    for field in ("passages", "by_source"):
        was, now = committed.get("population", {}).get(field), fresh["population"][field]
        if was != now:
            findings.append(f"population.{field}: artifact {was!r}, recomputed {now!r}")
    return findings


def format_table(artifact: dict[str, Any]) -> str:
    lines = [f"{'population':12} {'n':>6} {'min':>6} {'p50':>6} {'p90':>6} {'p99':>6} "
             f"{'max':>6} {'mean':>7} {'B/char':>7}"]
    for name in ("all", "metadata", "fulltext"):
        block = artifact["distribution"][name]["chars"]
        if not block.get("count"):
            continue
        lines.append(
            f"{name:12} {block['count']:6} {block['min']:6} {block['p50']:6} "
            f"{block['p90']:6} {block['p99']:6} {block['max']:6} {block['mean']:7.1f} "
            f"{artifact['distribution'][name]['bytes_per_char']:7.2f}")
    lines.append("")
    lines.append(f"{'language':12} {'n':>6} {'p50':>6} {'max':>6} {'B/char':>7} {'words p50':>10}")
    for name, block in artifact["by_language"].items():
        lines.append(
            f"{name:12} {block['passages']:6} {block['chars']['p50']:6} "
            f"{block['chars']['max']:6} {block['bytes_per_char']:7.2f} "
            f"{block['words']['p50']:10}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export", type=Path, default=EXPORT,
                        help="the committed golden export to measure")
    parser.add_argument("--report", type=Path, default=REPORT,
                        help="golden-gate report whose build status the population is "
                             "cross-checked against")
    parser.add_argument("--no-report", action="store_true",
                        help="measure the export alone, with no cross-check")
    parser.add_argument("--output", type=Path, default=None,
                        help="write the artifact as JSON here")
    parser.add_argument("--check", type=Path, nargs="?", const=ARTIFACT, default=None,
                        metavar="ARTIFACT",
                        help="compare a committed artifact against a fresh measurement and "
                             "exit 1 when it is stale")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    golden_gate = _load_golden_gate()
    export = golden_gate.load_export(args.export)
    status = None if args.no_report else load_status(args.report)
    artifact = build(export, status)

    logging.info(format_table(artifact))
    check = artifact["cross_check"]
    if check["compared"] is None:
        logging.info("cross-check: %s", check["reason"])
    else:
        logging.info("cross-check against the built index: %s",
                     "agrees on all four counters" if check["agrees"]
                     else f"DIFFERS {check['differences']}")

    if args.check is not None:
        if not args.check.is_file():
            logging.error("no artifact at %s", args.check)
            raise SystemExit(1)
        findings = stale(json.loads(args.check.read_text(encoding="utf-8")), artifact)
        if findings:
            for finding in findings:
                logging.error("stale: %s", finding)
            raise SystemExit(1)
        logging.info("%s describes the export beside it", args.check)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
        logging.info("wrote %s", args.output)


if __name__ == "__main__":
    main()
