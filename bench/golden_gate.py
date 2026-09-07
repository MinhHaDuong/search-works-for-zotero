#!/usr/bin/env python3
"""The golden gate at bank schema v3: validate the question bank, score replies, print its shape.

Ticket 0722 implements the rulings of 2026-09-06: an answer is a paragraph in a page in a
file attached to a Zotero entry; a reply scores win, near-win or miss on the rank at which
the answer paragraph appears and on the completeness of its citation chain; the same work in
another rendering or language is a near-win; a no-answer question carries an empty primary
set and is expected-miss. The primary set is a set of rows (a work, or a section of a work);
`set_kind` says whether one row suffices (any-of) or every row is needed (all-of). Rank and
mean reciprocal rank are reported per lane and never gated (D11).

Three subcommands:

  validate  bank + export: every primary row names an attachment the export manifest holds,
            every alternate's quote is located in the export's fulltext, and the result is
            stamped into each question's `reachability` block (--stamp) or compared with it.
  score     bank + replies (schema menagerie-replies/v2; v1 bundles are refused) -> report
            (schema golden-gate-report/v3): the ladder per lane, stratum, format, signal,
            set_kind, mode and facet with the count beside every rate and `not-measured` at
            zero; R34 absolute over the primary rows; the stability reading against the
            previous run with thresholds parsed from SPEC.md §5.2.8.
  shape     the bank's shape: counts by lane, stratum, signal, set_kind, expected-miss, mode,
            facet, format and questions per document, with not-measured at zero.

Exit codes: 0 pass, 1 fail, 2 input error, 3 not-run.

The stability policy is read from SPEC.md rather than copied here, so this file never becomes
a second owner of the gate's design numbers.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PASS = "pass"
FAIL = "fail"
NOT_RUN = "not-run"
NOT_MEASURED = "not-measured"

BANK_SCHEMA = "menagerie-bank/v3"
#: Bank schemas this file used to read, and what a holder of one has to do. v3 renames two
#: fields to the names SPEC.md §5.2.10 owns; §5.2.10's lifecycle table calls a change to the
#: record shape a major version, so the schema string moves with it rather than silently.
SUPERSEDED_BANK_SCHEMAS = {
    "menagerie-bank/v2": (
        "v3 renames `pinned` to `primary` and `mechanisms` to `mechanism`, the specification's "
        "own names; rename the two keys and set the schema string"
    ),
}
REPLIES_SCHEMA = "menagerie-replies/v2"
REPORT_SCHEMA = "golden-gate-report/v3"
THRESHOLD_SOURCE = "SPEC.md §5.2.8"

WIN = "win"
NEAR_WIN = "near-win"
MISS = "miss"
LEVEL_ORDER = {MISS: 0, NEAR_WIN: 1, WIN: 2}

LANGUAGES = ("en", "fr", "de", "vi", "zh", "ar", "ru", "hi", "es", "la", "pt")
SIGNALS = ("exact", "paraphrase", "agreement")
MODES = ("lexical", "semantic", "hybrid", "any")
REPLY_MODES = ("lexical", "semantic", "hybrid")
FACETS = ("core", "notes", "group", "deep-body")
STRATA = ("core", "reserve")
GENERATORS = ("need", "hazard")
SET_KINDS = ("any-of", "all-of")
FORMATS = ("pdf", "html", "other")
CHAIN_FIELDS = (
    "title",
    "author",
    "date",
    "identifier",
    "section_heading",
    "page_printed",
    "part_title",
    "part_byline",
)
#: Relation types under which another record is the same work in another rendering or
#: language (ruling of 2026-09-02, collapsed by R24; near-win by the ruling of 2026-09-06).
TWIN_RELATIONS = frozenset({"translation", "same-work"})
QUESTION_ID = re.compile(r"^q-\d{4,}$")
EVIDENCE_OVERLAP_MIN = 0.5
WORK_ID_LINE = re.compile(r"^ticket-0029 work id:\s*(.+?)\s*$", re.MULTILINE)
WORK_RELATIONS_LINE = re.compile(r"^ticket-0029 work relations:\s*(.+?)\s*$", re.MULTILINE)


class InputError(ValueError):
    """The scorer cannot give a meaningful verdict for the supplied input."""


# --------------------------------------------------------------------------- thresholds


@dataclass(frozen=True)
class Thresholds:
    """Golden-gate policy resolved from its authoritative source."""

    k: int
    mean_min: float
    below_max_fraction: float
    below_cutoff: float
    hard_floor: float
    source: str = THRESHOLD_SOURCE


def _one_match(pattern: str, text: str, label: str) -> str:
    matches = re.findall(pattern, text, flags=re.DOTALL)
    if len(matches) != 1:
        raise InputError(f"could not resolve exactly one {label} from {THRESHOLD_SOURCE}")
    return matches[0]


def load_thresholds(spec_path: Path) -> Thresholds:
    """Resolve the golden policy directly from SPEC.md's owning paragraph."""

    try:
        spec = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read threshold source {spec_path}: {exc}") from exc

    start_marker = "- **The golden gate (D11 = set)**"
    end_marker = "- **R13, the soak gate.**"
    start = spec.find(start_marker)
    end = spec.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise InputError(f"cannot locate the golden-gate paragraph in {spec_path}")
    section = spec[start:end]

    k = int(_one_match(r"answer \*sets\* at k=(\d+)", section, "answer-set depth"))
    mean_min = float(_one_match(r"mean Jaccard\s*≥\s*([0-9]+(?:\.[0-9]+)?)", section, "mean"))
    below_percent = float(
        _one_match(
            r"at most\s+([0-9]+(?:\.[0-9]+)?)\s*%\s+of queries below",
            section,
            "below-cutoff fraction",
        )
    )
    below_cutoff = float(
        _one_match(
            r"at most\s+[0-9]+(?:\.[0-9]+)?\s*%\s+of queries below\s+([0-9]+(?:\.[0-9]+)?)",
            section,
            "below-cutoff boundary",
        )
    )
    hard_floor = float(_one_match(r"hard floor of\s+([0-9]+(?:\.[0-9]+)?)", section, "hard floor"))
    thresholds = Thresholds(
        k=k,
        mean_min=mean_min,
        below_max_fraction=below_percent / 100,
        below_cutoff=below_cutoff,
        hard_floor=hard_floor,
    )
    if not (
        thresholds.k > 0
        and 0 < thresholds.hard_floor <= thresholds.below_cutoff <= thresholds.mean_min <= 1
        and 0 <= thresholds.below_max_fraction <= 1
    ):
        raise InputError(f"invalid golden-gate policy in {spec_path}")
    return thresholds


# --------------------------------------------------------------------------- small helpers


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InputError(f"{field} must be a string or null")
    return value if value.strip() else None


def _enum(value: Any, field: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise InputError(f"{field} must name one of {list(allowed)}, got {value!r}")
    return value


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"cannot read {label} {path}: {exc}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "‛": "'", "“": '"', "”": '"', "„": '"'})


def normalise_text(text: str) -> tuple[str, list[int]]:
    """Whitespace-normalised, apostrophe-folded, case-preserving text with an origin map.

    Runs of whitespace (including form feeds and newlines) collapse to one space, leading
    whitespace is dropped, curly apostrophes and quotes fold to their ASCII form. `origin[i]`
    is the index in the raw text of the character that produced `normalised[i]`, so a match
    in the normalised text resolves to a raw character offset.
    """

    out: list[str] = []
    origin: list[int] = []
    pending_space = False
    for index, char in enumerate(text):
        if char.isspace():
            pending_space = bool(out)
            continue
        if pending_space:
            out.append(" ")
            origin.append(index)
            pending_space = False
        out.append(char.translate(_APOSTROPHES))
        origin.append(index)
    return "".join(out), origin


def _norm_compare(value: str) -> str:
    text, _ = normalise_text(value)
    return re.sub(r"[\s\.,;:]+$", "", text.casefold())


def content_words(text: str) -> set[str]:
    """Lower-cased word tokens of three characters or more, the units of evidence overlap."""

    return {token for token in re.findall(r"\w+", text.casefold()) if len(token) >= 3}


def lane_of(question_language: str, answer_language: str) -> str:
    return f"{question_language}->{answer_language}"


# --------------------------------------------------------------------------- the export


@dataclass
class Export:
    root: Path
    manifest: dict[str, Any]
    sha256: str
    attachments: dict[str, dict[str, Any]]
    items: dict[str, dict[str, Any]]
    parent_of: dict[str, str]
    work_of_item: dict[str, str]
    items_of_work: dict[str, set[str]]
    twin_works: dict[str, set[str]]

    def format_of(self, attachment_key: str) -> str:
        item = self.items.get(attachment_key, {})
        content_type = str(item.get("contentType") or "")
        if content_type == "application/pdf":
            return "pdf"
        if content_type in {"text/html", "application/xhtml+xml"}:
            return "html"
        return "other"

    def fulltext(self, attachment_key: str) -> str | None:
        row = self.attachments[attachment_key]
        relative = row.get("fulltext_file")
        if not relative:
            return None
        body = _read_json(self.root / relative, f"fulltext of {attachment_key}")
        content = body.get("content") if isinstance(body, dict) else None
        if not isinstance(content, str):
            raise InputError(f"fulltext of {attachment_key} carries no content string")
        return content

    def extraction(self) -> dict[str, Any]:
        reindex = self.manifest.get("reindex") or {}
        zotero = self.manifest.get("zotero") or {}
        return {
            "reindex_mode": reindex.get("mode"),
            "reindex_limits": reindex.get("limits"),
            "caps": {
                "fulltext.pdfMaxPages": zotero.get("fulltext.pdfMaxPages"),
                "fulltext.textMaxLength": zotero.get("fulltext.textMaxLength"),
            },
            "index_fulltext_max_chars": self.manifest.get("index_fulltext_max_chars"),
            "recipe_sha256": self.manifest.get("recipe_sha256"),
        }

    def is_twin(self, item_key: str, work_id: str) -> bool:
        work = self.work_of_item.get(item_key)
        if work is None:
            return False
        return work == work_id or work in self.twin_works.get(work_id, set())


def _relation_targets(extra: str) -> list[tuple[str, str]]:
    found = WORK_RELATIONS_LINE.search(extra)
    if not found:
        return []
    try:
        relations = json.loads(found.group(1))
    except ValueError:
        return []
    out = []
    for relation in relations if isinstance(relations, list) else []:
        if not isinstance(relation, dict):
            continue
        kind = relation.get("type")
        target = relation.get("work_id") or relation.get("target") or relation.get("id")
        if isinstance(kind, str) and isinstance(target, str):
            out.append((kind, target))
    return out


def load_export(directory: Path) -> Export:
    root = directory.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise InputError(f"export {root} has no manifest.json")
    manifest = _read_json(manifest_path, "export manifest")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("attachments"), list):
        raise InputError("export manifest must carry an attachments list")
    items_raw = _read_json(root / str(manifest.get("items_file") or "items.json"), "export items")
    if not isinstance(items_raw, list):
        raise InputError("export items must be a list")
    items: dict[str, dict[str, Any]] = {}
    for item in items_raw:
        data = item.get("data") if isinstance(item, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("key"), str):
            raise InputError("export items carry an item without a data.key")
        items[data["key"]] = data
    attachments: dict[str, dict[str, Any]] = {}
    parent_of: dict[str, str] = {}
    for row in manifest["attachments"]:
        if not isinstance(row, dict) or not isinstance(row.get("attachment_key"), str):
            raise InputError("export manifest carries an attachment row without a key")
        key = row["attachment_key"]
        attachments[key] = row
        parent = row.get("parent_key") or items.get(key, {}).get("parentItem")
        if isinstance(parent, str):
            parent_of[key] = parent
    work_of_item: dict[str, str] = {}
    items_of_work: dict[str, set[str]] = defaultdict(set)
    twin_works: dict[str, set[str]] = defaultdict(set)
    relations: list[tuple[str, str, str]] = []
    for key, data in items.items():
        if data.get("itemType") == "attachment":
            continue
        extra = str(data.get("extra") or "")
        found = WORK_ID_LINE.search(extra)
        if found:
            work_of_item[key] = found.group(1)
            items_of_work[found.group(1)].add(key)
            for kind, target in _relation_targets(extra):
                relations.append((found.group(1), kind, target))
    for work, kind, target in relations:
        if kind in TWIN_RELATIONS:
            twin_works[work].add(target)
            twin_works[target].add(work)
    return Export(
        root=root,
        manifest=manifest,
        sha256=_sha256_file(manifest_path),
        attachments=attachments,
        items=items,
        parent_of=parent_of,
        work_of_item=work_of_item,
        items_of_work=dict(items_of_work),
        twin_works=dict(twin_works),
    )


# --------------------------------------------------------------------------- the bank


def _chain(value: Any, field: str) -> dict[str, str | None]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    unknown = sorted(set(value) - set(CHAIN_FIELDS))
    if unknown:
        raise InputError(f"{field} carries unknown chain fields {unknown}")
    return {name: _optional_string(value.get(name), f"{field}.{name}") for name in CHAIN_FIELDS}


def _alternate(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    unknown = sorted(set(value) - {"page_printed", "char_offset", "quote"})
    if unknown:
        raise InputError(f"{field} carries unknown fields {unknown}")
    offset = value.get("char_offset")
    if offset is not None and (not isinstance(offset, int) or isinstance(offset, bool) or offset < 0):
        raise InputError(f"{field}.char_offset must be a non-negative integer or null")
    return {
        "page_printed": _optional_string(value.get("page_printed"), f"{field}.page_printed"),
        "char_offset": offset,
        "quote": _string(value.get("quote"), f"{field}.quote"),
    }


def _row(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    allowed = {"work_id", "recipe_id", "attachment_id", "attachment_key", "section", "alternates", "chain"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise InputError(f"{field} carries unknown fields {unknown}")
    alternates = value.get("alternates")
    if not isinstance(alternates, list) or not alternates:
        raise InputError(f"{field}.alternates must be a non-empty list")
    return {
        "work_id": _string(value.get("work_id"), f"{field}.work_id"),
        "recipe_id": _string(value.get("recipe_id"), f"{field}.recipe_id"),
        "attachment_id": _optional_string(value.get("attachment_id"), f"{field}.attachment_id"),
        "attachment_key": _string(value.get("attachment_key"), f"{field}.attachment_key"),
        "section": _string(value.get("section"), f"{field}.section"),
        "alternates": [
            _alternate(alternate, f"{field}.alternates[{index}]") for index, alternate in enumerate(alternates)
        ],
        "chain": _chain(value.get("chain"), f"{field}.chain"),
    }


def _provenance(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    date = _string(value.get("date"), f"{field}.date")
    try:
        _dt.date.fromisoformat(date)
    except ValueError as exc:
        raise InputError(f"{field}.date must be an ISO date") from exc
    page_read = value.get("page_read")
    if not isinstance(page_read, bool):
        raise InputError(f"{field}.page_read must be a boolean")
    return {"author": _string(value.get("author"), f"{field}.author"), "date": date, "page_read": page_read}


def validate_question(raw: Any, *, expected_id: str | None = None) -> dict[str, Any]:
    """Structural validation of one question record; returns the normalised record."""

    if not isinstance(raw, dict):
        raise InputError("a question must be a JSON object")
    if raw.get("schema") in SUPERSEDED_BANK_SCHEMAS:
        raise InputError(
            f"{raw.get('schema')} records are no longer read: {SUPERSEDED_BANK_SCHEMAS[raw['schema']]} "
            f"(the bank is {BANK_SCHEMA})"
        )
    if raw.get("schema") != BANK_SCHEMA:
        raise InputError(f"question schema must be {BANK_SCHEMA}, got {raw.get('schema')!r}")
    qid = _string(raw.get("id"), "id")
    if not QUESTION_ID.match(qid):
        raise InputError(f"question id {qid!r} must look like q-0001")
    if expected_id is not None and qid != expected_id:
        raise InputError(f"question id {qid!r} does not match its file name {expected_id!r}")
    label = f"question {qid}"
    allowed = {
        "schema", "id", "need", "query", "question_language", "answer_language", "lane", "signal",
        "mode", "facet", "stratum", "mechanism", "generator", "set_kind", "primary", "expected_miss",
        "expected_miss_mechanism", "reachability", "provenance", "retained_reason",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise InputError(f"{label} carries unknown fields {unknown}")
    question_language = _enum(raw.get("question_language"), f"{label}.question_language", LANGUAGES)
    answer_language = _enum(raw.get("answer_language"), f"{label}.answer_language", LANGUAGES)
    lane = _string(raw.get("lane"), f"{label}.lane")
    if lane != lane_of(question_language, answer_language):
        raise InputError(f"{label}.lane must be {lane_of(question_language, answer_language)!r}")
    mechanisms = raw.get("mechanism")
    if not isinstance(mechanisms, list) or any(not isinstance(m, str) or not m for m in mechanisms):
        raise InputError(f"{label}.mechanism must be a list of non-empty strings")
    primary = raw.get("primary")
    if not isinstance(primary, list):
        raise InputError(f"{label}.primary must be a list of rows")
    rows = [_row(row, f"{label}.primary[{index}]") for index, row in enumerate(primary)]
    row_ids = [(row["work_id"], row["section"]) for row in rows]
    if len(row_ids) != len(set(row_ids)):
        raise InputError(f"{label}.primary repeats a (work, section) row; merge the alternates")
    expected_miss = raw.get("expected_miss")
    if not isinstance(expected_miss, bool):
        raise InputError(f"{label}.expected_miss must be a boolean")
    mechanism = _optional_string(raw.get("expected_miss_mechanism"), f"{label}.expected_miss_mechanism")
    if expected_miss and not mechanism:
        raise InputError(f"{label} is expected-miss and must name expected_miss_mechanism")
    if not expected_miss and mechanism:
        raise InputError(f"{label} names an expected_miss_mechanism but is not expected-miss")
    if not rows and not expected_miss:
        raise InputError(f"{label} has an empty primary set and must be expected-miss")
    set_kind = _enum(raw.get("set_kind"), f"{label}.set_kind", SET_KINDS)
    reachability = raw.get("reachability")
    if reachability is not None and not isinstance(reachability, dict):
        raise InputError(f"{label}.reachability must be an object or null")
    return {
        "schema": BANK_SCHEMA,
        "id": qid,
        "need": _string(raw.get("need"), f"{label}.need"),
        "query": _string(raw.get("query"), f"{label}.query"),
        "question_language": question_language,
        "answer_language": answer_language,
        "lane": lane,
        "signal": _enum(raw.get("signal"), f"{label}.signal", SIGNALS),
        "mode": _enum(raw.get("mode"), f"{label}.mode", MODES),
        "facet": _enum(raw.get("facet"), f"{label}.facet", FACETS),
        "stratum": _enum(raw.get("stratum"), f"{label}.stratum", STRATA),
        "mechanism": list(mechanisms),
        "generator": _enum(raw.get("generator"), f"{label}.generator", GENERATORS),
        "set_kind": set_kind,
        "primary": rows,
        "expected_miss": expected_miss,
        "expected_miss_mechanism": mechanism,
        "reachability": reachability,
        "provenance": _provenance(raw.get("provenance"), f"{label}.provenance"),
        **({"retained_reason": raw["retained_reason"]} if raw.get("retained_reason") else {}),
    }


def load_bank(directory: Path) -> list[dict[str, Any]]:
    """Read every `q-*.json` of a flat bank directory, refusing duplicates and malformed rows."""

    root = directory.resolve()
    if not root.is_dir():
        raise InputError(f"bank directory {root} does not exist")
    questions: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if path.name == "bank.schema.json":
            continue
        raw = _read_json(path, "question")
        try:
            questions.append(validate_question(raw, expected_id=path.stem))
        except InputError as exc:
            raise InputError(f"{path.name}: {exc}") from exc
    if not questions:
        raise InputError(f"bank directory {root} holds no question")
    ids = [question["id"] for question in questions]
    if len(ids) != len(set(ids)):
        raise InputError("duplicate question ids in the bank")
    return questions


# --------------------------------------------------------------------------- reachability


def locate_quote(quote: str, content: str, *, preferred_offset: int | None = None) -> dict[str, Any]:
    """Find `quote` in `content` after normalisation; resolve the raw character offset."""

    norm_content, origin = normalise_text(content)
    norm_quote, _ = normalise_text(quote)
    if not norm_quote:
        return {"reachable": False, "char_offset": None, "occurrences": 0, "reason": "empty quote"}
    offsets: list[int] = []
    start = norm_content.find(norm_quote)
    while start >= 0:
        offsets.append(origin[start])
        start = norm_content.find(norm_quote, start + 1)
    if not offsets:
        return {
            "reachable": False,
            "char_offset": None,
            "occurrences": 0,
            "reason": "quote not located in the export fulltext",
        }
    chosen = preferred_offset if preferred_offset in offsets else offsets[0]
    return {"reachable": True, "char_offset": chosen, "occurrences": len(offsets), "reason": None}


def compute_reachability(question: dict[str, Any], export: Export) -> dict[str, Any]:
    """The reachability block for one question, computed against the export."""

    cap = export.manifest.get("index_fulltext_max_chars")
    rows_out = []
    any_reachable = False
    for row in question["primary"]:
        key = row["attachment_key"]
        manifest_row = export.attachments.get(key)
        if manifest_row is None:
            raise InputError(f"question {question['id']} pins attachment {key} which the export manifest does not hold")
        if manifest_row.get("recipe_id") != row["recipe_id"]:
            raise InputError(
                f"question {question['id']} pins attachment {key} under recipe {row['recipe_id']!r}; "
                f"the export binds it to {manifest_row.get('recipe_id')!r}"
            )
        control = manifest_row.get("failure_control")
        if isinstance(control, dict) and control.get("answer_set_participation") == "none":
            raise InputError(
                f"question {question['id']} pins attachment {key}, a declared failure control that never joins an answer set"
            )
        content = export.fulltext(key) if manifest_row.get("terminal_state") == "indexed" else None
        alternates_out = []
        for alternate in row["alternates"]:
            if content is None:
                located = {
                    "reachable": False,
                    "char_offset": None,
                    "occurrences": 0,
                    "reason": f"attachment {key} is {manifest_row.get('terminal_state')} in the export: no fulltext to locate in",
                }
            else:
                located = locate_quote(alternate["quote"], content, preferred_offset=alternate["char_offset"])
            within_cap = None
            if located["reachable"] and isinstance(cap, int):
                within_cap = located["char_offset"] + len(alternate["quote"]) <= cap
            any_reachable = any_reachable or located["reachable"]
            alternates_out.append({**located, "within_index_cap": within_cap})
        rows_out.append({"attachment_key": key, "alternates": alternates_out})
    return {
        "computed_by": "bench/golden_gate.py validate --stamp",
        "export_sha256": export.sha256,
        "extraction": export.extraction(),
        "reachable": any_reachable,
        "rows": rows_out,
    }


def check_reachability_policy(question: dict[str, Any], block: dict[str, Any]) -> None:
    """Unreachable alternates are an error unless the question is expected-miss with a mechanism."""

    if question["expected_miss"]:
        return
    unreachable = [
        (row["attachment_key"], index, alternate["reason"])
        for row in block["rows"]
        for index, alternate in enumerate(row["alternates"])
        if not alternate["reachable"]
    ]
    if unreachable:
        key, index, reason = unreachable[0]
        raise InputError(
            f"question {question['id']} pins an unreachable alternate ({key} alternates[{index}]: {reason}); "
            "flag the question expected_miss with a mechanism, or fix the quote"
        )


def _comparable(block: dict[str, Any]) -> dict[str, Any]:
    return {
        "export_sha256": block.get("export_sha256"),
        "extraction": block.get("extraction"),
        "reachable": block.get("reachable"),
        "rows": [
            {
                "attachment_key": row.get("attachment_key"),
                "alternates": [
                    {name: alternate.get(name) for name in ("reachable", "char_offset", "within_index_cap")}
                    for alternate in row.get("alternates", [])
                ],
            }
            for row in block.get("rows", [])
        ],
    }


def validate_bank(bank_dir: Path, export: Export, *, stamp: bool) -> dict[str, Any]:
    """Validate the bank against the export; stamp or compare every reachability block."""

    questions = load_bank(bank_dir)
    summary = {"questions": len(questions), "stamped": 0, "alternates": 0, "reachable_alternates": 0, "past_index_cap": 0}
    for question in questions:
        block = compute_reachability(question, export)
        check_reachability_policy(question, block)
        for row in block["rows"]:
            for alternate in row["alternates"]:
                summary["alternates"] += 1
                summary["reachable_alternates"] += int(alternate["reachable"])
                summary["past_index_cap"] += int(alternate["within_index_cap"] is False)
        path = bank_dir / f"{question['id']}.json"
        raw = _read_json(path, "question")
        if stamp:
            raw["reachability"] = block
            for row_raw, row_block in zip(raw["primary"], block["rows"]):
                for alternate_raw, alternate_block in zip(row_raw["alternates"], row_block["alternates"]):
                    alternate_raw["char_offset"] = alternate_block["char_offset"]
            path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary["stamped"] += 1
            continue
        stored = raw.get("reachability")
        if not isinstance(stored, dict):
            raise InputError(f"question {question['id']} carries no reachability stamp; run validate --stamp")
        if stored.get("export_sha256") != export.sha256:
            raise InputError(
                f"question {question['id']} was stamped against export {stored.get('export_sha256')}; "
                f"this export is {export.sha256}: re-run validate --stamp"
            )
        if _comparable(stored) != _comparable(block):
            raise InputError(f"question {question['id']} reachability stamp is stale; re-run validate --stamp")
        for row_raw, row_block in zip(raw["primary"], block["rows"]):
            for alternate_raw, alternate_block in zip(row_raw["alternates"], row_block["alternates"]):
                if alternate_raw.get("char_offset") != alternate_block["char_offset"]:
                    raise InputError(
                        f"question {question['id']} alternate char_offset {alternate_raw.get('char_offset')} "
                        f"differs from the located {alternate_block['char_offset']}; re-run validate --stamp"
                    )
    return summary


# --------------------------------------------------------------------------- shape


def bank_shape(questions: list[dict[str, Any]], export: Export | None) -> dict[str, Any]:
    """Counts along every closed axis, with every vocabulary value listed and zero shown."""

    def counted(values: tuple[str, ...], observed: Counter) -> dict[str, int]:
        table = {value: observed.get(value, 0) for value in values}
        for extra in sorted(set(observed) - set(values)):
            table[extra] = observed[extra]
        return table

    lanes = Counter(q["lane"] for q in questions)
    strata = Counter(q["stratum"] for q in questions)
    signals = Counter(q["signal"] for q in questions)
    set_kinds = Counter(q["set_kind"] for q in questions)
    modes = Counter(q["mode"] for q in questions)
    facets = Counter(q["facet"] for q in questions)
    generators = Counter(q["generator"] for q in questions)
    expected = Counter("expected-miss" if q["expected_miss"] else "scored" for q in questions)
    formats: Counter = Counter()
    per_document: Counter = Counter()
    mechanisms: Counter = Counter()
    for question in questions:
        for mechanism in question["mechanism"]:
            mechanisms[mechanism] += 1
        for row in question["primary"]:
            per_document[row["recipe_id"]] += 1
            if export is not None and row["attachment_key"] in export.attachments:
                formats[export.format_of(row["attachment_key"])] += 1
            elif export is not None:
                formats["unknown-attachment"] += 1
    documents_with_text = []
    if export is not None:
        documents_with_text = sorted(
            {row["recipe_id"] for row in export.manifest["attachments"] if row.get("terminal_state") == "indexed"}
        )
    return {
        "questions": len(questions),
        "by_lane": dict(sorted(lanes.items())),
        "by_stratum": counted(STRATA, strata),
        "by_signal": counted(SIGNALS, signals),
        "by_set_kind": counted(SET_KINDS, set_kinds),
        "by_expected_miss": {"scored": expected.get("scored", 0), "expected-miss": expected.get("expected-miss", 0)},
        "by_mode": counted(MODES, modes),
        "by_facet": counted(FACETS, facets),
        "by_generator": counted(GENERATORS, generators),
        "by_format": counted(FORMATS, formats) if export is not None else NOT_MEASURED,
        "by_mechanism": dict(sorted(mechanisms.items())),
        "rows_per_document": {
            **{recipe_id: 0 for recipe_id in documents_with_text},
            **dict(sorted(per_document.items())),
        },
    }


def render_shape(shape: dict[str, Any]) -> str:
    lines = [f"questions: {shape['questions']}"]
    for axis in (
        "by_lane", "by_stratum", "by_signal", "by_set_kind", "by_expected_miss", "by_mode",
        "by_facet", "by_generator", "by_format", "by_mechanism", "rows_per_document",
    ):
        table = shape[axis]
        if table == NOT_MEASURED:
            lines.append(f"{axis}: {NOT_MEASURED}")
            continue
        cells = ", ".join(
            f"{name} {count}" + ("" if count else f" ({NOT_MEASURED})") for name, count in table.items()
        )
        lines.append(f"{axis}: {cells or NOT_MEASURED}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- replies


def _result(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    rank = value.get("rank")
    if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
        raise InputError(f"{field}.rank must be a positive integer")
    chain = value.get("chain")
    if chain is None:
        chain = {}
    if not isinstance(chain, dict):
        raise InputError(f"{field}.chain must be an object or null")
    return {
        "rank": rank,
        "item_key": _string(value.get("item_key"), f"{field}.item_key"),
        "attachment_key": _optional_string(value.get("attachment_key"), f"{field}.attachment_key"),
        "work_id": _optional_string(value.get("work_id"), f"{field}.work_id"),
        "evidence": _optional_string(value.get("evidence"), f"{field}.evidence"),
        "page": _optional_string(value.get("page"), f"{field}.page"),
        "chain": {name: _optional_string(chain.get(name), f"{field}.chain.{name}") for name in CHAIN_FIELDS},
        "score": value.get("score"),
    }


def _run_block(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    for name in ("recipe_sha256", "export_sha256"):
        _string(value.get(name), f"{field}.{name}")
    if not isinstance(value.get("extraction"), dict):
        raise InputError(f"{field}.extraction must be an object")
    return value


def _reply(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    results = value.get("results")
    if results is not None and not isinstance(results, list):
        raise InputError(f"{field}.results must be a list or null (not-run)")
    reply = {
        "id": _string(value.get("id"), f"{field}.id"),
        "mode": _enum(value.get("mode"), f"{field}.mode", REPLY_MODES),
        "results": None if results is None else [_result(r, f"{field}.results[{i}]") for i, r in enumerate(results)],
        "not_run_reason": _optional_string(value.get("not_run_reason"), f"{field}.not_run_reason"),
    }
    if reply["results"] is None and not reply["not_run_reason"]:
        raise InputError(f"{field} has no results and must say why in not_run_reason")
    if reply["results"] is not None:
        ranks = [result["rank"] for result in reply["results"]]
        if ranks != list(range(1, len(ranks) + 1)):
            raise InputError(f"{field}.results ranks must run 1..n in order")
    return reply


def load_replies(payload: Any) -> dict[str, Any]:
    """Validate a replies bundle; a v1 bundle (golden-gate-input/v1) is refused by name."""

    if not isinstance(payload, dict):
        raise InputError("replies must be a JSON object")
    schema = payload.get("schema")
    if schema == "golden-gate-input/v1":
        raise InputError(
            "golden-gate-input/v1 bundles are no longer scored: the gate reads menagerie-replies/v2 "
            "(bank schema menagerie-bank/v2, ticket 0722); regenerate with bench/golden_run.py"
        )
    if schema != REPLIES_SCHEMA:
        raise InputError(f"replies schema must be {REPLIES_SCHEMA}, got {schema!r}")
    run = _run_block(payload.get("run"), "run")
    previous = payload.get("previous_run")
    previous_bundle = None
    if previous is not None:
        if not isinstance(previous, dict):
            raise InputError("previous_run must be an object")
        previous_bundle = {
            "run": _run_block(previous.get("run"), "previous_run.run"),
            "replies": [_reply(r, f"previous_run.replies[{i}]") for i, r in enumerate(previous.get("replies") or [])],
        }
    raw_replies = payload.get("replies")
    if not isinstance(raw_replies, list) or not raw_replies:
        raise InputError("replies must be a non-empty list")
    replies = [_reply(r, f"replies[{i}]") for i, r in enumerate(raw_replies)]
    seen = set()
    for reply in replies:
        pair = (reply["id"], reply["mode"])
        if pair in seen:
            raise InputError(f"replies repeat question {reply['id']} in mode {reply['mode']}")
        seen.add(pair)
    return {"run": run, "previous_run": previous_bundle, "replies": replies}


# --------------------------------------------------------------------------- scoring


def evidence_overlap(quote: str, evidence: str | None) -> float:
    words = content_words(quote)
    if not words or not evidence:
        return 0.0
    return len(words & content_words(evidence)) / len(words)


def _page_matches(result_page: str | None, alternate_page: str | None) -> bool:
    if not result_page or not alternate_page:
        return False
    return result_page.strip().casefold() == alternate_page.strip().casefold()


def evidence_matches(result: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """The win condition: evidence overlaps an alternate's quote, or the printed page matches."""

    best = 0.0
    for alternate in row["alternates"]:
        overlap = evidence_overlap(alternate["quote"], result["evidence"])
        best = max(best, overlap)
        if overlap >= EVIDENCE_OVERLAP_MIN:
            return {"matched": True, "how": "evidence-overlap", "overlap": round(overlap, 3)}
        if _page_matches(result["page"], alternate["page_printed"]):
            return {"matched": True, "how": "printed-page", "overlap": round(overlap, 3)}
    return {"matched": False, "how": None, "overlap": round(best, 3)}


def _chain_field_matches(name: str, pinned: str, carried: str | None) -> bool:
    if carried is None:
        return False
    if name == "page_printed":
        return pinned.strip() == carried.strip()
    left, right = _norm_compare(pinned), _norm_compare(carried)
    if name == "identifier":
        strip = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:)")
        left, right = strip.sub("", left), strip.sub("", right)
    return left == right or (bool(left) and bool(right) and (left in right or right in left))


def chain_completeness(pinned: dict[str, str | None], carried: dict[str, str | None]) -> dict[str, Any]:
    expected = [name for name in CHAIN_FIELDS if pinned.get(name)]
    matched = [name for name in expected if _chain_field_matches(name, pinned[name], carried.get(name))]
    missing = [name for name in expected if carried.get(name) is None]
    mismatched = [name for name in expected if name not in matched and name not in missing]
    return {
        "matched": len(matched),
        "of": len(expected),
        "fraction": (len(matched) / len(expected)) if expected else None,
        "missing": missing,
        "mismatched": mismatched,
    }


def score_row(row: dict[str, Any], results: list[dict[str, Any]], k: int, export: Export) -> dict[str, Any]:
    """One pinned row against one reply's first k results: level, rank, chain completeness."""

    parent = export.parent_of.get(row["attachment_key"])
    level = MISS
    rank: int | None = None
    establishing: dict[str, Any] | None = None
    how: dict[str, Any] | None = None
    for result in results[:k]:
        same_item = result["item_key"] == parent or (
            result["attachment_key"] is not None and result["attachment_key"] == row["attachment_key"]
        )
        twin = (not same_item) and (
            result["work_id"] == row["work_id"] or export.is_twin(result["item_key"], row["work_id"])
        )
        if same_item:
            match = evidence_matches(result, row)
            if match["matched"]:
                level, rank, establishing, how = WIN, result["rank"], result, match
                break
            if level == MISS:
                level, rank, establishing, how = NEAR_WIN, result["rank"], result, {**match, "why": "item-without-evidence"}
        elif twin and level == MISS:
            level, rank, establishing, how = NEAR_WIN, result["rank"], result, {"matched": False, "why": "work-twin"}
    return {
        "work_id": row["work_id"],
        "section": row["section"],
        "attachment_key": row["attachment_key"],
        "level": level,
        "rank": rank,
        "reciprocal_rank": (1 / rank) if rank else 0.0,
        "evidence": how,
        "chain": chain_completeness(row["chain"], establishing["chain"]) if establishing else NOT_RUN,
    }


def score_reply(question: dict[str, Any], reply: dict[str, Any], k: int, export: Export) -> dict[str, Any]:
    """One (question, mode) pair on the ladder, or its expected-miss reading."""

    base = {
        "id": question["id"],
        "mode": reply["mode"],
        "lane": question["lane"],
        "stratum": question["stratum"],
        "signal": question["signal"],
        "set_kind": question["set_kind"],
        "facet": question["facet"],
        "format": (
            export.format_of(question["primary"][0]["attachment_key"]) if question["primary"] else "none"
        ),
        "expected_miss": question["expected_miss"],
    }
    if reply["results"] is None:
        return {**base, "state": NOT_RUN, "reason": reply["not_run_reason"]}
    results = reply["results"]
    rows = [score_row(row, results, k, export) for row in question["primary"]]
    if question["expected_miss"]:
        present = [row for row in rows if row["level"] != MISS]
        return {
            **base,
            "state": "expected-miss",
            "outcome": PASS if not present else "unexpected-hit",
            "mechanism": question["expected_miss_mechanism"],
            "rows": rows,
            "top_k_item_keys": [result["item_key"] for result in results[:k]],
        }
    if question["set_kind"] == "any-of":
        best = max(rows, key=lambda row: (LEVEL_ORDER[row["level"]], -(row["rank"] or 10**9)))
        level, rank, chain = best["level"], best["rank"], best["chain"]
    else:
        weakest = min(rows, key=lambda row: (LEVEL_ORDER[row["level"]], -(row["rank"] or 10**9)))
        level = weakest["level"]
        ranks = [row["rank"] for row in rows if row["rank"]]
        rank = max(ranks) if level != MISS and len(ranks) == len(rows) else None
        measured = [row["chain"] for row in rows if row["chain"] != NOT_RUN]
        chain = (
            {
                "matched": sum(c["matched"] for c in measured),
                "of": sum(c["of"] for c in measured),
                "fraction": (
                    sum(c["matched"] for c in measured) / sum(c["of"] for c in measured)
                    if sum(c["of"] for c in measured)
                    else None
                ),
            }
            if measured and level != MISS
            else NOT_RUN
        )
    found = sum(row["level"] != MISS for row in rows)
    return {
        **base,
        "state": "scored",
        "level": level,
        "rank": rank,
        "reciprocal_rank": (1 / rank) if rank else 0.0,
        "chain": chain,
        "rows_found": {"count": found, "of": len(rows), "fraction": found / len(rows)},
        "rows": rows,
        "r34_present": (found > 0) if question["set_kind"] == "any-of" else (found == len(rows)),
        "top_k_item_keys": [result["item_key"] for result in results[:k]],
    }


def _ladder_stats(entries: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(entries)
    if n == 0:
        return {"count": 0, "state": NOT_MEASURED}
    wins = sum(e["level"] == WIN for e in entries)
    nears = sum(e["level"] == NEAR_WIN for e in entries)
    misses = n - wins - nears
    chains = [e["chain"]["fraction"] for e in entries if e["chain"] != NOT_RUN and e["chain"]["fraction"] is not None]
    r34_pass = sum(e["r34_present"] for e in entries)
    return {
        "count": n,
        "win": wins,
        "near_win": nears,
        "miss": misses,
        "win_rate": wins / n,
        "near_or_better_rate": (wins + nears) / n,
        "mrr": sum(e["reciprocal_rank"] for e in entries) / n,
        "ranks": {e["id"]: e["rank"] for e in entries},
        "chain_completeness": {
            "measured": len(chains),
            "mean": (sum(chains) / len(chains)) if chains else NOT_MEASURED,
        },
        "r34": {"present": r34_pass, "absent": n - r34_pass},
    }


def _grouped(entries: list[dict[str, Any]], key: str, values: tuple[str, ...] | None) -> dict[str, Any]:
    observed = sorted({e[key] for e in entries})
    names = list(values) if values else []
    for name in observed:
        if name not in names:
            names.append(name)
    return {name: _ladder_stats([e for e in entries if e[key] == name]) for name in names}


def ladder_readings(scored: list[dict[str, Any]], modes_not_run: dict[str, str]) -> dict[str, Any]:
    """The ladder along every axis, strata apart, and a macro-average by lane beside the pooled figure."""

    def axes(entries: list[dict[str, Any]]) -> dict[str, Any]:
        by_mode = _grouped(entries, "mode", REPLY_MODES)
        for mode, reason in modes_not_run.items():
            if by_mode[mode]["count"] == 0:
                by_mode[mode] = {**by_mode[mode], "reason": reason}
        return {
            "all": _ladder_stats(entries),
            "by_lane": _grouped(entries, "lane", None),
            "by_format": _grouped(entries, "format", FORMATS),
            "by_signal": _grouped(entries, "signal", SIGNALS),
            "by_set_kind": _grouped(entries, "set_kind", SET_KINDS),
            "by_mode": by_mode,
            "by_facet": _grouped(entries, "facet", FACETS),
        }

    def macro_by_lane(entries: list[dict[str, Any]]) -> dict[str, Any]:
        lanes = _grouped(entries, "lane", None)
        measured = [stats for stats in lanes.values() if stats["count"]]
        if not measured:
            return {"lanes": 0, "state": NOT_MEASURED}
        return {
            "lanes": len(measured),
            "win_rate": sum(s["win_rate"] for s in measured) / len(measured),
            "near_or_better_rate": sum(s["near_or_better_rate"] for s in measured) / len(measured),
            "mrr": sum(s["mrr"] for s in measured) / len(measured),
        }

    return {
        "by_stratum": {stratum: axes([e for e in scored if e["stratum"] == stratum]) for stratum in STRATA},
        "all_strata_weighted": _ladder_stats(scored),
        "all_strata_macro_by_lane": macro_by_lane(scored),
    }


def r34_reading(scored: list[dict[str, Any]]) -> dict[str, Any]:
    if not scored:
        return {"state": NOT_RUN, "reason": "no scored question in this reading"}
    missing = {
        f"{e['id']}/{e['mode']}": [
            f"{row['work_id']}#{row['section']}" for row in e["rows"] if row["level"] == MISS
        ]
        for e in scored
        if not e["r34_present"]
    }
    return {"state": FAIL if missing else PASS, "question_count": len(scored), "missing": dict(sorted(missing.items()))}


def _jaccard(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 1.0


def stability_reading(
    replies: dict[str, Any], entries: list[dict[str, Any]], thresholds: Thresholds
) -> dict[str, Any]:
    previous = replies["previous_run"]
    if previous is None:
        return {"state": NOT_RUN, "reason": "no previous_run in the replies file; the stability reading needs two runs"}
    previous_export = (previous.get("run") or {}).get("export_sha256")
    current_export = (replies.get("run") or {}).get("export_sha256")
    if previous_export and current_export and previous_export != current_export:
        # A re-pin (conception note B.6): the export changed, so item keys and the passage
        # distribution moved with it, and a Jaccard against the old run measures the re-pin.
        return {
            "state": NOT_RUN,
            "reason": (f"previous_run was produced against export {previous_export[:12]}, this run against "
                       f"{current_export[:12]}: a re-pin invalidates the stability comparison (B.6); "
                       "the first run on a new export has no stability reading"),
            "previous_run": previous["run"],
        }
    previous_sets = {
        (reply["id"], reply["mode"]): [r["item_key"] for r in reply["results"][: thresholds.k]]
        for reply in previous["replies"]
        if reply["results"] is not None
    }
    scores: dict[str, float] = {}
    for entry in entries:
        pair = (entry["id"], entry["mode"])
        if pair in previous_sets and "top_k_item_keys" in entry:
            scores[f"{entry['id']}/{entry['mode']}"] = _jaccard(previous_sets[pair], entry["top_k_item_keys"])
    if not scores:
        return {"state": NOT_RUN, "reason": "previous_run shares no (question, mode) pair with this run"}
    mean = sum(scores.values()) / len(scores)
    below_count = sum(score < thresholds.below_cutoff for score in scores.values())
    below_fraction = below_count / len(scores)
    minimum = min(scores.values())
    failed_rules = []
    if mean < thresholds.mean_min:
        failed_rules.append("mean-jaccard")
    if below_fraction > thresholds.below_max_fraction:
        failed_rules.append("below-cutoff-fraction")
    if minimum < thresholds.hard_floor:
        failed_rules.append("hard-floor")
    return {
        "state": FAIL if failed_rules else PASS,
        "query_count": len(scores),
        "mean_jaccard": mean,
        "below_cutoff_count": below_count,
        "below_cutoff_fraction": below_fraction,
        "minimum_jaccard": minimum,
        "per_query": dict(sorted(scores.items())),
        "failed_rules": failed_rules,
        "previous_run": previous["run"],
    }


def evaluate(
    questions: list[dict[str, Any]], replies: dict[str, Any], export: Export, thresholds: Thresholds
) -> dict[str, Any]:
    """Score every reply against its question and assemble the report."""

    if replies["run"]["export_sha256"] != export.sha256:
        raise InputError(
            f"replies were produced against export {replies['run']['export_sha256']}; "
            f"this export is {export.sha256}"
        )
    by_id = {question["id"]: question for question in questions}
    per_question: list[dict[str, Any]] = []
    modes_not_run: dict[str, str] = {}
    for reply in replies["replies"]:
        question = by_id.get(reply["id"])
        if question is None:
            raise InputError(f"replies name question {reply['id']} which the bank does not hold")
        if question["mode"] != "any" and question["mode"] != reply["mode"]:
            raise InputError(f"question {reply['id']} is scoped to mode {question['mode']}, reply is {reply['mode']}")
        entry = score_reply(question, reply, thresholds.k, export)
        if entry["state"] == NOT_RUN:
            modes_not_run.setdefault(reply["mode"], entry["reason"])
        per_question.append(entry)
    answered = {entry["id"] for entry in per_question}
    unanswered = sorted(set(by_id) - answered)
    scored = [e for e in per_question if e["state"] == "scored"]
    expected = [e for e in per_question if e["state"] == "expected-miss"]
    not_run = [e for e in per_question if e["state"] == NOT_RUN]
    r34 = r34_reading(scored)
    stability = stability_reading(replies, scored + expected, thresholds)
    if r34["state"] == FAIL or stability["state"] == FAIL:
        state = FAIL
    elif r34["state"] == NOT_RUN or stability["state"] == NOT_RUN:
        state = NOT_RUN
    else:
        state = PASS
    return {
        "schema": REPORT_SCHEMA,
        "state": state,
        "threshold_source": thresholds.source,
        "k": thresholds.k,
        "run": replies["run"],
        "export_sha256": export.sha256,
        "question_count": len(questions),
        "reply_count": len(per_question),
        "scored_count": len(scored),
        "expected_miss_count": len(expected),
        "not_run_count": len(not_run),
        "unanswered_questions": unanswered,
        "modes_not_run": modes_not_run,
        "readings": {"r34": r34, "stability": stability},
        "ladder": ladder_readings(scored, modes_not_run),
        "expected_miss": {
            "count": len(expected),
            "pass": sum(e["outcome"] == PASS for e in expected),
            "unexpected_hit": sum(e["outcome"] == "unexpected-hit" for e in expected),
            "by_mechanism": dict(Counter(e["mechanism"] for e in expected)),
            "per_question": {f"{e['id']}/{e['mode']}": e["outcome"] for e in expected},
        },
        "questions": {f"{e['id']}/{e['mode']}": e for e in per_question},
    }


# --------------------------------------------------------------------------- rendering


def _rate(count: int, total: int) -> str:
    return f"{count}/{total} ({100 * count / total:.0f} %)" if total else f"0/0 ({NOT_MEASURED})"


def _stats_line(name: str, stats: dict[str, Any]) -> str:
    if stats.get("count", 0) == 0:
        reason = f" — {stats['reason']}" if stats.get("reason") else ""
        return f"  {name}: n=0 {NOT_MEASURED}{reason}"
    n = stats["count"]
    chain = stats["chain_completeness"]
    chain_text = (
        f"{chain['mean']:.2f} over {chain['measured']}" if chain["mean"] != NOT_MEASURED else NOT_MEASURED
    )
    return (
        f"  {name}: n={n} win {_rate(stats['win'], n)} near-win {_rate(stats['near_win'], n)} "
        f"miss {_rate(stats['miss'], n)} mrr {stats['mrr']:.3f} chain {chain_text} "
        f"r34 present {_rate(stats['r34']['present'], n)}"
    )


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"golden gate: {report['state']}  (k={report['k']}, thresholds from {report['threshold_source']})",
        f"questions {report['question_count']}, replies {report['reply_count']}: scored {report['scored_count']}, "
        f"expected-miss {report['expected_miss_count']}, not-run {report['not_run_count']}",
    ]
    if report["unanswered_questions"]:
        lines.append(f"questions with no reply: {', '.join(report['unanswered_questions'])}")
    r34 = report["readings"]["r34"]
    lines.append(f"R34 absolute: {r34['state']}" + (f" — {r34['reason']}" if r34.get("reason") else ""))
    for pair, rows in r34.get("missing", {}).items():
        lines.append(f"  missing {pair}: {', '.join(rows)}")
    stability = report["readings"]["stability"]
    if stability["state"] == NOT_RUN:
        lines.append(f"stability: {NOT_RUN} — {stability['reason']}")
    else:
        lines.append(
            f"stability: {stability['state']} mean Jaccard {stability['mean_jaccard']:.3f} over "
            f"{stability['query_count']}, below cutoff {stability['below_cutoff_count']}, "
            f"minimum {stability['minimum_jaccard']:.3f}"
            + (f", failed {stability['failed_rules']}" if stability["failed_rules"] else "")
        )
        previous_sha = (stability.get("previous_run") or {}).get("build_sha")
        current_sha = (report.get("run") or {}).get("build_sha")
        if previous_sha and previous_sha == current_sha:
            lines.append(
                f"  previous run is the SAME build ({previous_sha[:12]}): a determinism control, not a drift reading"
            )
        elif previous_sha:
            lines.append(f"  previous run build {previous_sha[:12]} vs this run {str(current_sha)[:12]}")
    for stratum in STRATA:
        axes = report["ladder"]["by_stratum"][stratum]
        lines.append(f"stratum {stratum}:")
        lines.append(_stats_line("all", axes["all"]))
        for axis in ("by_lane", "by_format", "by_signal", "by_set_kind", "by_mode", "by_facet"):
            table = axes[axis]
            if not table:
                lines.append(f"  {axis}: {NOT_MEASURED}")
                continue
            for name, stats in table.items():
                lines.append(_stats_line(f"{axis[3:]} {name}", stats))
    weighted = report["ladder"]["all_strata_weighted"]
    macro = report["ladder"]["all_strata_macro_by_lane"]
    lines.append("all strata (weighted, core+reserve pooled — read the strata above first):")
    lines.append(_stats_line("weighted", weighted))
    if macro.get("lanes"):
        lines.append(
            f"  macro-average by lane over {macro['lanes']} lane(s): win {macro['win_rate']:.2f} "
            f"near-or-better {macro['near_or_better_rate']:.2f} mrr {macro['mrr']:.3f}"
        )
    else:
        lines.append(f"  macro-average by lane: {NOT_MEASURED}")
    expected = report["expected_miss"]
    lines.append(
        f"expected-miss (reported apart): {expected['count']} question(s), pass {expected['pass']}, "
        f"unexpected hit {expected['unexpected_hit']}"
    )
    for mechanism, count in expected["by_mechanism"].items():
        lines.append(f"  mechanism {mechanism}: {count}")
    for pair, entry in report["questions"].items():
        if entry["state"] == "scored":
            chain = entry["chain"]
            chain_text = f"{chain['matched']}/{chain['of']}" if chain != NOT_RUN else NOT_RUN
            lines.append(
                f"  {pair}: {entry['level']} rank {entry['rank']} chain {chain_text} "
                f"rows {entry['rows_found']['count']}/{entry['rows_found']['of']} lane {entry['lane']}"
            )
        elif entry["state"] == "expected-miss":
            lines.append(f"  {pair}: expected-miss {entry['outcome']} ({entry['mechanism']})")
        else:
            lines.append(f"  {pair}: {NOT_RUN} — {entry['reason']}")
    return "\n".join(lines)


def _write_json(document: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


# --------------------------------------------------------------------------- CLI


def _cmd_validate(args: argparse.Namespace) -> int:
    export = load_export(args.export)
    summary = validate_bank(args.bank, export, stamp=args.stamp)
    action = "stamped" if args.stamp else "checked"
    print(
        f"bank {args.bank}: {summary['questions']} question(s) {action} against export {export.sha256[:12]}; "
        f"{summary['reachable_alternates']}/{summary['alternates']} alternate(s) reachable, "
        f"{summary['past_index_cap']} past index_fulltext_max_chars={export.manifest.get('index_fulltext_max_chars')}"
    )
    return 0


def _cmd_shape(args: argparse.Namespace) -> int:
    questions = load_bank(args.bank)
    export = load_export(args.export) if args.export and Path(args.export).is_dir() else None
    shape = bank_shape(questions, export)
    if args.output:
        _write_json(shape, args.output)
    print(render_shape(shape))
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    thresholds = load_thresholds(args.spec)
    questions = load_bank(args.bank)
    export = load_export(args.export)
    if not args.replies.is_file():
        shape = bank_shape(questions, export)
        print(render_shape(shape))
        _write_json(
            {
                "schema": REPORT_SCHEMA,
                "state": NOT_RUN,
                "threshold_source": thresholds.source,
                "reason": f"replies file {args.replies} does not exist; run bench/golden_run.py to produce it",
            },
            args.output,
        )
        print(f"golden gate: {NOT_RUN} — replies file {args.replies} does not exist", file=sys.stderr)
        return 3
    replies = load_replies(_read_json(args.replies, "replies"))
    report = evaluate(questions, replies, export, thresholds)
    _write_json(report, args.output)
    print(render_report(report), file=sys.stderr)
    return {PASS: 0, FAIL: 1, NOT_RUN: 3}[report["state"]]


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="bank + export: locate every alternate, stamp or compare reachability")
    validate.add_argument("--bank", type=Path, default=repo / "bench" / "fixtures" / "questions")
    validate.add_argument("--export", type=Path, default=repo / "bench" / "fixtures" / "export")
    validate.add_argument("--stamp", action="store_true", help="write the reachability block into each question")
    validate.set_defaults(func=_cmd_validate)

    score = sub.add_parser("score", help="bank + replies -> report")
    score.add_argument("--bank", type=Path, default=repo / "bench" / "fixtures" / "questions")
    score.add_argument("--export", type=Path, default=repo / "bench" / "fixtures" / "export")
    score.add_argument("--replies", type=Path, required=True)
    score.add_argument("--output", type=Path)
    score.add_argument("--spec", type=Path, default=repo / "SPEC.md")
    score.set_defaults(func=_cmd_score)

    shape = sub.add_parser("shape", help="print the bank's shape")
    shape.add_argument("--bank", type=Path, default=repo / "bench" / "fixtures" / "questions")
    shape.add_argument("--export", type=Path, default=repo / "bench" / "fixtures" / "export")
    shape.add_argument("--output", type=Path)
    shape.set_defaults(func=_cmd_shape)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except InputError as exc:
        print(f"golden gate: input error — {exc}", file=sys.stderr)
        if getattr(args, "output", None) and args.command == "score":
            _write_json({"schema": REPORT_SCHEMA, "state": FAIL, "reason": str(exc)}, args.output)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
