#!/usr/bin/env python3
"""The red-state exercise for the Menagerie question bank (ticket 0722, item 1 of 0029).

A green golden run and a vacuous golden run are the same artifact until the bank has been
shown capable of going red. This harness breaks one mechanism at a time, re-scores the bank
through the *unmodified* `golden_gate.py`, and reports per lane, per stratum and per signal
which questions changed verdict, which mechanism ids fired, and — the deliverable — which
MUST cells did **not** go red under an arm that named them.

Two kinds of arm, labelled and never conflated:

  kind: build   the product is really broken (a patch in `fork/src`, rebuilt) and the bank is
                re-driven through `golden_run.py` over the offline replay. Evidence about the
                bank against a real build.
  kind: reply   a seeded, deterministic transform of a committed replies bundle, re-scored by
                the same scorer. Evidence about the bank against a *stipulated* reply
                distribution: a simulation, and every sentence that uses it must say so. Its
                value is that it runs in seconds on any machine and gives a permanent red
                fixture.

Both write a real `menagerie-replies/v2` bundle carrying an `arm` block in `run`, so no
artifact can be mistaken for a measurement of an unbroken build.

Three predicates, because what "present" means for R34 is the author's open ruling on
PR #409 and this harness must not preempt it:

  shipped           `level != miss` — win, or `item-without-evidence`, or `work-twin`
  evidence-matched  `level == win` — the pinned quote overlapped, or the printed page matched
  twin-excluded     shipped minus the `work-twin` path (reported, not one of the two)

All three are pure functions of the emitted report. The scorer is never patched.

Subcommands: `list`, `run`, `read`.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import gzip
import hashlib
import json
import logging
import os
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_gate import (  # noqa: E402
    MISS,
    REPLIES_SCHEMA,
    CHAIN_FIELDS,
    Export,
    InputError,
    evaluate,
    load_bank,
    load_export,
    load_replies,
    load_thresholds,
)

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("redstate")

REPO = Path(__file__).resolve().parent.parent
DEFAULT_BANK = REPO / "bench" / "fixtures" / "questions"
DEFAULT_EXPORT = REPO / "bench" / "fixtures" / "export"
DEFAULT_RECIPE = REPO / "bench" / "fixtures" / "recipe-pinned.json"
DEFAULT_BASELINE = REPO / "bench" / "results" / "golden" / "replies.json"
DEFAULT_OUT = REPO / "bench" / "results" / "0722-redstate"
DEFAULT_SERVER = REPO / "fork" / "dist" / "index.js"

#: R7's first tier gives the three monolingual MUST lanes; R29 binds all six ordered pairs
#: over the same three languages. SPEC §5.2.10 says every MUST cell carries a minimum
#: question count and that none is ruled, so this harness prints counts beside every cell
#: and claims no rate on a thin one.
MUST_LANES_MONOLINGUAL = ("en->en", "fr->fr", "vi->vi")
MUST_LANES_CROSSLINGUAL = ("en->fr", "en->vi", "fr->en", "fr->vi", "vi->en", "vi->fr")
MUST_LANES = MUST_LANES_MONOLINGUAL + MUST_LANES_CROSSLINGUAL

#: Below this many questions a cell's rate is not reported as a rate (SPEC §5.2.10's
#: not-evaluated clause, whose minimum is unruled; the count is printed either way).
THIN_CELL = 5

PREDICATES = ("shipped", "evidence-matched", "twin-excluded")
EVIDENCE_HOWS = frozenset({"evidence-overlap", "printed-page"})


# --------------------------------------------------------------------------- predicates


def _row_present(row: dict[str, Any], predicate: str) -> bool:
    """Is one scored pinned row 'present' under this predicate?"""

    evidence = row.get("evidence") or {}
    if predicate == "evidence-matched":
        return evidence.get("how") in EVIDENCE_HOWS
    if row["level"] == MISS:
        return False
    if predicate == "twin-excluded":
        return evidence.get("why") != "work-twin"
    return True


def question_present(entry: dict[str, Any], predicate: str) -> bool:
    """R34's reading of one scored question under a predicate.

    The shipped predicate is read off the report's own `r34_present` rather than recomputed,
    so a disagreement between this harness and the scorer would show up as a test failure
    rather than as a silently different headline number.
    """

    if entry.get("state") != "scored":
        raise ValueError(f"{entry.get('id')} is {entry.get('state')}, not scored")
    if predicate == "shipped":
        return bool(entry["r34_present"])
    rows = entry["rows"]
    found = [_row_present(row, predicate) for row in rows]
    return any(found) if entry["set_kind"] == "any-of" else all(found)


def scored_entries(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key: entry for key, entry in report["questions"].items() if entry["state"] == "scored"}


def expected_miss_entries(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key: entry for key, entry in report["questions"].items() if entry["state"] == "expected-miss"}


def present_set(report: dict[str, Any], predicate: str) -> set[str]:
    return {key for key, entry in scored_entries(report).items() if question_present(entry, predicate)}


# --------------------------------------------------------------------------- the arms


@dataclass(frozen=True)
class Arm:
    """One break, its declared targets, and whether it can be run here.

    `targets` is a claim made *before* the arm runs: the lanes and the mechanism ids this
    break should redden. `delta.json`'s `must_cells_that_did_not_go_red` is the set
    difference between that claim and the observation, and it is the deliverable.
    """

    name: str
    letter: str
    kind: str  # build | reply
    summary: str
    target_lanes: tuple[str, ...] = ()
    target_mechanisms: tuple[str, ...] = ()
    control: bool = False
    runnable: bool = True
    not_run_reason: str | None = None
    #: exact-string patches applied to the fork source for a build arm
    patches: tuple[tuple[str, str, str], ...] = ()
    #: reply transform name, resolved in REPLY_TRANSFORMS
    transform: str | None = None
    notes: tuple[str, ...] = ()

    def as_json(self) -> dict[str, Any]:
        out = dataclasses.asdict(self)
        out["patches"] = [{"file": f, "old": o, "new": n} for f, o, n in self.patches]
        return out


_SHUFFLE_HELPER = """
/**
 * Ticket 0722 red-state arm A: a seeded global shuffle of the fused candidate list. Not a
 * permutation of the top k — that is invisible to the gate, whose levels and R34 verdict are
 * set membership over the first k and whose rank feeds only the never-gated MRR. The pool is
 * widened to the whole matching set first, so the arm destroys the ranking without changing
 * what the index can see, and snippets survive so the evidence path is not confounded.
 */
function redstateShuffle(fused: Array<{ id: string; score: number }>, q: string): Array<{ id: string; score: number }> {
  let seed = 0x9e3779b9;
  for (const ch of q) seed = (Math.imul(seed ^ ch.charCodeAt(0), 0x85ebca6b) >>> 0);
  const next = () => {
    seed = (Math.imul(seed ^ (seed >>> 15), 0x2545f491) + 0x6d2b79f5) >>> 0;
    return seed / 0x100000000;
  };
  const out = fused.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(next() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out.map((entry, i) => ({ id: entry.id, score: 1 - i / (out.length || 1) }));
}
"""

_QUERY_MANAGER = "fork/src/features/search/index-manager.ts"
_CONFIG = "fork/src/config.ts"

ARMS: tuple[Arm, ...] = (
    Arm(
        name="null-reply",
        letter="control",
        kind="reply",
        summary="the identity transform of the baseline bundle: the control that proves the differ can say 'nothing changed'",
        control=True,
        transform="identity",
        notes=(
            "A differ whose 'no cell went red' is indistinguishable from 'my differ is broken' is not a differ.",
        ),
    ),
    Arm(
        name="control-build",
        letter="control",
        kind="build",
        summary="the unmodified build, rebuilt and re-driven here: the control that proves the build path reproduces the committed baseline",
        control=True,
        notes=(
            "Every build arm is differenced against this, never against the committed baseline, "
            "because the committed baseline was produced by a checkout this harness does not pin.",
        ),
    ),
    Arm(
        name="global-shuffle",
        letter="A",
        kind="build",
        summary="arm A: the ranker no longer ranks — the fused candidate list is widened to the whole matching set and shuffled on a seed derived from the query",
        target_lanes=MUST_LANES,
        target_mechanisms=("*",),
        patches=(
            (_QUERY_MANAGER, "    const pool = limit * 3;", "    const pool = 1000000; // redstate arm A"),
            (
                _QUERY_MANAGER,
                "    const fused = rrf([keyword, vector]);",
                "    const fused = redstateShuffle(rrf([keyword, vector]), q); // redstate arm A",
            ),
            (_QUERY_MANAGER, "function rrf(", _SHUFFLE_HELPER + "\nfunction rrf("),
        ),
        notes=(
            "Anything that stays present under a global shuffle is a defect in the bank or in the scorer.",
            "The work-twin path has a raised floor here: a shuffled ranker that returns any rendering of "
            "the work still scores near-win.",
        ),
    ),
    Arm(
        name="global-shuffle-sim",
        letter="A",
        kind="reply",
        summary="arm A as a reply-level simulation: each reply's results replaced by k parent items drawn without replacement from the export, seeded, with evidence taken from each drawn item's own fulltext",
        target_lanes=MUST_LANES,
        target_mechanisms=("*",),
        transform="global-shuffle",
        notes=(
            "A simulation, not a measurement of a build. Its job is to calibrate the build arm and to be "
            "a permanent red fixture that runs with python alone.",
        ),
    ),
    Arm(
        name="semantic-off",
        letter="B",
        kind="build",
        summary="arm B: the semantic path disabled, so the paraphrase questions should catch it",
        target_lanes=MUST_LANES,
        target_mechanisms=("paraphrase",),
        runnable=False,
        not_run_reason=(
            "This arm cannot be run as a degradation because it IS the shipped baseline: the committed run "
            "is embedder 'none (keyword-only)', vectors 0, with semantic and hybrid written not-run. There is "
            "no semantic baseline to degrade from, so the positive control has to be built first — a vectors-on "
            "run — and only then is keyword-only the broken arm. Simulating 'semantic off' from a run that "
            "never had semantic on is circular. make_index_fixture.mjs refuses --embeddings != off in two "
            "places, so a vectors-on run has to drive bench/run_build.py directly with a model runtime; that is "
            "its own ticket."
        ),
    ),
    Arm(
        name="lexical-off",
        letter="C",
        kind="build",
        summary="arm C: semantic only, so the rare-exact-string questions should catch it",
        target_lanes=MUST_LANES,
        target_mechanisms=("known-item", "transliterated-proper-name", "section-heading-case-variant", "lexical-false-negative"),
        runnable=False,
        not_run_reason=(
            "Blocked on arm B's prerequisite (no vectors exist in the offline replay), plus a way to suppress "
            "the lexical arm. If it becomes runnable, a run where both the exact and the paraphrase cells fall "
            "is measuring the absence of an index, not the absence of a lexical path."
        ),
    ),
    Arm(
        name="english-embedder",
        letter="D",
        kind="build",
        summary="arm D: an English-only embedder where a multilingual one is expected — the six cross-lingual MUST lanes should catch it",
        target_lanes=MUST_LANES_CROSSLINGUAL,
        target_mechanisms=("cross-lingual",),
        runnable=False,
        not_run_reason=(
            "The break is already the shipped default and so is not injectable: the run block's "
            "embedder_model.build_default reads Xenova/all-MiniLM-L6-v2, parsed out of the build's own source, "
            "which is English-only. The configuration that would have to be BUILT to make this comparison is "
            "the multilingual one, which needs the same vectors-on run arm B is blocked on. Under the "
            "evidence-matched predicate the six cross-lingual MUST cells already hold zero wins, so this arm "
            "has zero headroom there whatever is built."
        ),
    ),
    Arm(
        name="index-cap",
        letter="E",
        kind="build",
        summary="arm E: the index character cap cut from 40 000 to 2 000, at the one place config resolves it, so both the build and the query side see the small cap",
        target_lanes=MUST_LANES,
        target_mechanisms=("index-cap",),
        patches=(
            (
                _CONFIG,
                "    indexFulltextMaxChars: parsed.ZOTEUS_INDEX_FULLTEXT_MAX_CHARS,",
                "    indexFulltextMaxChars: 2000, // redstate arm E",
            ),
        ),
        notes=(
            "The ticket's declared target — 'the cap-crossing questions' — is wrong, and showing that is the "
            "point of running it. 35 of the 39 cap-naming questions are expected-miss, whose pass condition is "
            "'no pinned row in the top k'; a smaller cap makes them GREENER, and expected-miss outcomes enter "
            "no gated reading at all. The honest target is computed from the bank's own stamps: every scored "
            "question whose reachability char_offset exceeds the new cap. That set is written into delta.json "
            "as computed_target_questions.",
            "The run block will report index_fulltext_max_chars 40 000 from the export manifest, which the "
            "patch overrides; the arm block records the real cap.",
        ),
    ),
    Arm(
        name="collapse-off",
        letter="F",
        kind="build",
        summary="arm F: entry collapse disabled — the per-item de-duplication in the query path removed, so the top k fills with several passages of one item",
        target_lanes=MUST_LANES,
        target_mechanisms=(
            "work-identity",
            "declared-translation",
            "same-text-different-format",
            "metadata-conflicting-duplicate",
            "near-duplicate-publication",
            "multi-attachment-parent",
            "compound-document-entries",
        ),
        patches=(
            (
                _QUERY_MANAGER,
                "      if (!rec || seen.has(rec.itemKey)) continue;",
                "      if (!rec) continue; // redstate arm F: entry collapse disabled",
            ),
        ),
        notes=(
            "This breaks what the BUILD does with renderings. What the SCORER does with twins "
            "(TWIN_RELATIONS, Export.is_twin) is a different clause and this arm proves nothing about it.",
        ),
    ),
    Arm(
        name="collapse-off-sim",
        letter="F",
        kind="reply",
        summary="arm F as a reply-level simulation at the work level rather than the passage level: each hit expanded into its work's sibling items and its twin works, truncated to k",
        target_lanes=MUST_LANES,
        target_mechanisms=(
            "work-identity",
            "declared-translation",
            "same-text-different-format",
            "metadata-conflicting-duplicate",
            "near-duplicate-publication",
            "multi-attachment-parent",
            "compound-document-entries",
        ),
        transform="collapse-off",
        notes=(
            "A simulation, and of a different unit than the build arm: the build's collapse is per item over "
            "passages, this expansion is per work over items. Read the two side by side, never as one number.",
        ),
    ),
)

ARMS_BY_NAME = {arm.name: arm for arm in ARMS}


# --------------------------------------------------------------------------- reply transforms


def _rng(seed: int, arm: str, key: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{arm}:{key}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _creators(data: dict[str, Any]) -> str | None:
    names = []
    for creator in data.get("creators") or []:
        if creator.get("name"):
            names.append(creator["name"])
        else:
            parts = [creator.get("firstName"), creator.get("lastName")]
            names.append(" ".join(part for part in parts if part))
    return "; ".join(name for name in names if name) or None


def _chain_for(export: Export, item_key: str) -> dict[str, str | None]:
    data = export.items.get(item_key, {})
    chain: dict[str, str | None] = {name: None for name in CHAIN_FIELDS}
    chain["title"] = data.get("title") or None
    chain["author"] = _creators(data)
    chain["date"] = data.get("date") or None
    chain["identifier"] = data.get("DOI") or data.get("ISBN") or data.get("url") or None
    return chain


class _Corpus:
    """The export read as a draw pool: parent items, their attachments, their fulltext."""

    def __init__(self, export: Export):
        self.export = export
        self.attachments_of: dict[str, list[str]] = {}
        for attachment_key, parent in export.parent_of.items():
            self.attachments_of.setdefault(parent, []).append(attachment_key)
        for keys in self.attachments_of.values():
            keys.sort()
        self.pool = sorted(set(export.work_of_item) | set(self.attachments_of))
        self._fulltext: dict[str, str | None] = {}

    def fulltext(self, item_key: str) -> str | None:
        if item_key in self._fulltext:
            return self._fulltext[item_key]
        text: str | None = None
        for attachment_key in self.attachments_of.get(item_key, []):
            try:
                body = self.export.fulltext(attachment_key)
            except InputError:
                body = None
            if body:
                text = body
                break
        self._fulltext[item_key] = text
        return text

    def snippet(self, item_key: str, rng: random.Random, width: int = 240) -> str | None:
        text = self.fulltext(item_key)
        if not text:
            data = self.export.items.get(item_key, {})
            return (data.get("abstractNote") or data.get("title") or None)
        if len(text) <= width:
            return text
        start = rng.randrange(0, len(text) - width)
        return text[start : start + width]

    def result(self, rank: int, item_key: str, rng: random.Random, score: float) -> dict[str, Any]:
        return {
            "rank": rank,
            "item_key": item_key,
            "attachment_key": None,
            "work_id": self.export.work_of_item.get(item_key),
            "evidence": self.snippet(item_key, rng),
            "page": None,
            "chain": _chain_for(self.export, item_key),
            "score": round(score, 6),
            "source": "fulltext",
        }


def transform_identity(bundle: dict[str, Any], export: Export, seed: int) -> dict[str, Any]:
    """The control: change nothing. Its delta must be empty under every predicate."""

    return copy.deepcopy(bundle)


def transform_global_shuffle(bundle: dict[str, Any], export: Export, seed: int) -> dict[str, Any]:
    """Arm A, reply level: k parent items drawn without replacement from the whole export.

    Deliberately NOT a permutation of the top k. `score_row` takes presence from set
    membership over `results[:k]`, so a within-k permutation changes rank and MRR and leaves
    every level and every R34 verdict exactly where it was — a green arm that means nothing.
    """

    corpus = _Corpus(export)
    out = copy.deepcopy(bundle)
    for reply in out["replies"]:
        if reply.get("results") is None:
            continue
        k = len(reply["results"])
        if k == 0:
            continue
        rng = _rng(seed, "global-shuffle", reply["id"])
        drawn = rng.sample(corpus.pool, min(k, len(corpus.pool)))
        reply["results"] = [
            corpus.result(rank, item_key, rng, 1.0 - (rank - 1) / max(k, 1))
            for rank, item_key in enumerate(drawn, start=1)
        ]
    return out


def transform_collapse_off(bundle: dict[str, Any], export: Export, seed: int) -> dict[str, Any]:
    """Arm F, reply level: each hit expanded into its work's siblings and its twin works.

    Work level, not passage level — the build arm breaks the per-item de-duplication over
    passages, which is a different unit. Reading the two as one number would be wrong.
    """

    corpus = _Corpus(export)
    out = copy.deepcopy(bundle)
    for reply in out["replies"]:
        if not reply.get("results"):
            continue
        k = len(reply["results"])
        rng = _rng(seed, "collapse-off", reply["id"])
        expanded: list[str] = []
        for result in reply["results"]:
            item_key = result["item_key"]
            if item_key not in expanded:
                expanded.append(item_key)
            work = export.work_of_item.get(item_key)
            if work is None:
                continue
            siblings = sorted(export.items_of_work.get(work, set()))
            for twin_work in sorted(export.twin_works.get(work, set())):
                siblings.extend(sorted(export.items_of_work.get(twin_work, set())))
            for sibling in siblings:
                if sibling not in expanded:
                    expanded.append(sibling)
            if len(expanded) >= k:
                break
        expanded = expanded[:k]
        by_key = {result["item_key"]: result for result in reply["results"]}
        results = []
        for rank, item_key in enumerate(expanded, start=1):
            if item_key in by_key:
                kept = copy.deepcopy(by_key[item_key])
                kept["rank"] = rank
                results.append(kept)
            else:
                results.append(corpus.result(rank, item_key, rng, 1.0 - (rank - 1) / max(k, 1)))
        reply["results"] = results
    return out


REPLY_TRANSFORMS: dict[str, Callable[[dict[str, Any], Export, int], dict[str, Any]]] = {
    "identity": transform_identity,
    "global-shuffle": transform_global_shuffle,
    "collapse-off": transform_collapse_off,
}


# --------------------------------------------------------------------------- the differ


def _cell(before: set[str], after: set[str], keys: list[str]) -> dict[str, Any]:
    keyset = set(keys)
    present_before = len(keyset & before)
    present_after = len(keyset & after)
    cell = {
        "n": len(keys),
        "present_before": present_before,
        "present_after": present_after,
        "delta": present_after - present_before,
        "went_red": present_after < present_before,
    }
    if len(keys) < THIN_CELL:
        cell["rate"] = "not-evaluated"
        cell["why_no_rate"] = f"n={len(keys)} < {THIN_CELL}; SPEC §5.2.10 leaves the MUST-cell minima unruled"
    else:
        cell["rate"] = f"{present_after}/{len(keys)}"
    return cell


def _group(entries: dict[str, dict[str, Any]], axis: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for key, entry in entries.items():
        out.setdefault(entry[axis], []).append(key)
    return {name: sorted(keys) for name, keys in sorted(out.items())}


def _mechanisms(question: dict[str, Any] | None) -> list[str]:
    if not question:
        return []
    return list(question.get("mechanisms") or [])


def compute_delta(
    arm: Arm,
    predicate: str,
    baseline: dict[str, Any],
    after: dict[str, Any],
    bank: dict[str, dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One arm, one predicate: what changed, and which declared cell did not."""

    before_entries = scored_entries(baseline)
    after_entries = scored_entries(after)
    shared = sorted(set(before_entries) & set(after_entries))
    if set(before_entries) != set(after_entries):
        log.warning(
            "arm %s: baseline scores %d questions, arm scores %d; differencing the %d in common",
            arm.name, len(before_entries), len(after_entries), len(shared),
        )
    before = {key for key in shared if question_present(before_entries[key], predicate)}
    now = {key for key in shared if question_present(after_entries[key], predicate)}

    changed: dict[str, Any] = {}
    for key in shared:
        was, is_ = key in before, key in now
        if was == is_:
            continue
        entry = after_entries[key]
        question = bank.get(entry["id"])
        changed[key] = {
            "from": "present" if was else "absent",
            "to": "present" if is_ else "absent",
            "lane": entry["lane"],
            "stratum": entry["stratum"],
            "signal": entry["signal"],
            "set_kind": entry["set_kind"],
            "facet": entry["facet"],
            "level_before": before_entries[key]["level"],
            "level_after": entry["level"],
            "mechanisms": _mechanisms(question),
        }

    fired: dict[str, int] = {}
    for record in changed.values():
        if record["to"] != "absent":
            continue
        for mechanism in record["mechanisms"] or ["(none declared)"]:
            fired[mechanism] = fired.get(mechanism, 0) + 1

    by_lane = {name: _cell(before, now, keys) for name, keys in _group(after_entries, "lane").items()}
    must_cells = {}
    for lane in MUST_LANES:
        keys = _group(after_entries, "lane").get(lane, [])
        must_cells[lane] = _cell(before, now, keys)

    did_not_go_red: list[dict[str, Any]] = []
    for lane in arm.target_lanes:
        cell = must_cells.get(lane)
        if cell is None or cell["n"] == 0:
            did_not_go_red.append({"lane": lane, "n": 0, "reason": "no-question", "reading": "the cell holds no scored question in this bank"})
            continue
        if cell["went_red"]:
            continue
        if cell["present_before"] == 0:
            did_not_go_red.append({
                "lane": lane, **cell, "reason": "no-headroom",
                "reading": "the cell already read zero present at baseline under this predicate, so no arm can "
                           "make it redder; this is a property of the predicate, not of the arm",
            })
        else:
            did_not_go_red.append({
                "lane": lane, **cell, "reason": "not-reached",
                "reading": "the cell held present questions and the arm, which named it, moved none of them; "
                           "this is the finding",
            })

    em_before = expected_miss_entries(baseline)
    em_after = expected_miss_entries(after)
    flips: dict[str, list[str]] = {"pass->unexpected-hit": [], "unexpected-hit->pass": []}
    for key in sorted(set(em_before) & set(em_after)):
        was, is_ = em_before[key]["outcome"], em_after[key]["outcome"]
        if was == is_:
            continue
        flips.setdefault(f"{was}->{is_}", []).append(key)

    document = {
        "arm": arm.name,
        "arm_letter": arm.letter,
        "kind": arm.kind,
        "control": arm.control,
        "predicate": predicate,
        "scored_questions": len(shared),
        "present_before": len(before),
        "present_after": len(now),
        "delta": len(now) - len(before),
        "went_absent": sorted(before - now),
        "went_present": sorted(now - before),
        "changed": dict(sorted(changed.items())),
        "by_lane": by_lane,
        "by_stratum": {name: _cell(before, now, keys) for name, keys in _group(after_entries, "stratum").items()},
        "by_signal": {name: _cell(before, now, keys) for name, keys in _group(after_entries, "signal").items()},
        "by_set_kind": {name: _cell(before, now, keys) for name, keys in _group(after_entries, "set_kind").items()},
        "by_facet": {name: _cell(before, now, keys) for name, keys in _group(after_entries, "facet").items()},
        "must_cells": must_cells,
        "mechanisms_fired": dict(sorted(fired.items(), key=lambda kv: (-kv[1], kv[0]))),
        "target_lanes": list(arm.target_lanes),
        "target_mechanisms": list(arm.target_mechanisms),
        "must_cells_that_did_not_go_red": did_not_go_red,
        "expected_miss_flips": {name: keys for name, keys in sorted(flips.items()) if keys},
        "expected_miss_note": "expected-miss outcomes are computed and reported and enter no gated reading: "
                              "golden_gate.evaluate() takes the gate state from R34 and stability alone",
        "gate_state_before": baseline["state"],
        "gate_state_after": after["state"],
    }
    if extra:
        document.update(extra)
    return document


# --------------------------------------------------------------------------- arm E's honest target


def cap_crossing_questions(bank: dict[str, dict[str, Any]], cap: int) -> dict[str, list[str]]:
    """Every question with a stamped alternate whose char_offset exceeds `cap`.

    Arm E's declared target is 'the cap-crossing questions'. This computes the set from the
    bank's own reachability stamps, before the arm runs, and splits it by whether the
    question is scored or expected-miss — which is the whole point: a smaller cap moves the
    expected-miss ones toward *pass*, not toward red.
    """

    scored, expected = [], []
    for qid, question in sorted(bank.items()):
        offsets = [
            alternate.get("char_offset")
            for row in (question.get("reachability") or {}).get("rows", [])
            for alternate in row.get("alternates", [])
        ]
        if not any(isinstance(offset, int) and offset > cap for offset in offsets):
            continue
        (expected if question.get("expected_miss") else scored).append(qid)
    return {"cap": cap, "scored": scored, "expected_miss": expected}


# --------------------------------------------------------------------------- running


def _gz(path: Path) -> Path:
    return path if path.suffix == ".gz" else path.with_suffix(path.suffix + ".gz")


def _read_json(path: Path) -> Any:
    """Read a JSON artifact, gzipped or not: the large ones are committed compressed."""

    if path.suffix != ".gz" and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    target = _gz(path)
    if target.exists():
        with gzip.open(target, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    raise FileNotFoundError(f"neither {path} nor {target}")


def _write_json(document: Any, path: Path, *, compress: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if compress:
        target = _gz(path)
        with gzip.open(target, "wt", encoding="utf-8", compresslevel=9) as handle:
            handle.write(text)
        return target
    path.write_text(text, encoding="utf-8")
    return path


def stamp_arm(bundle: dict[str, Any], arm: Arm, seed: int, extra: dict[str, Any]) -> dict[str, Any]:
    """Put an `arm` block in the run block so the artifact cannot read as an unbroken run."""

    bundle = dict(bundle)
    run = dict(bundle["run"])
    run["arm"] = {
        "name": arm.name,
        "letter": arm.letter,
        "kind": arm.kind,
        "control": arm.control,
        "summary": arm.summary,
        "seed": seed,
        "harness": "bench/redstate.py",
        "ticket": "0722",
        **extra,
    }
    bundle["run"] = run
    return bundle


def score_bundle(bundle: dict[str, Any], questions: list[dict[str, Any]], export: Export, thresholds) -> dict[str, Any]:
    """The unmodified scorer, in process, on SPEC's own thresholds. golden_gate.py is never patched."""

    return evaluate(questions, load_replies(bundle), export, thresholds)


def run_reply_arm(
    arm: Arm, baseline_bundle: dict[str, Any], export: Export, seed: int
) -> dict[str, Any]:
    transform = REPLY_TRANSFORMS[arm.transform or ""]
    bundle = transform(baseline_bundle, export, seed)
    return stamp_arm(bundle, arm, seed, {"transform": arm.transform, "simulation": True})


def _git_fork(args: list[str], fork: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(fork), *args], capture_output=True, text=True, check=True)


def apply_patches(arm: Arm, fork: Path) -> None:
    for relative, old, new in arm.patches:
        path = REPO / relative
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise RuntimeError(f"arm {arm.name}: {relative} holds {text.count(old)} copies of the patched text, expected 1")
        path.write_text(text.replace(old, new), encoding="utf-8")
    log.info("arm %s: %d patch(es) applied", arm.name, len(arm.patches))


def revert_patches(fork: Path) -> None:
    _git_fork(["checkout", "--", "src"], fork)
    log.info("fork/src reverted")


def run_build_arm(
    arm: Arm, server: Path, data_root: Path, out_dir: Path, seed: int, bank: Path, export_dir: Path, recipe: Path
) -> dict[str, Any]:
    """Patch the product, rebuild, drive the bank over the offline replay, revert.

    No live Zotero client and no port 23119 is involved: `golden_run.py` starts
    `golden_replay_serve.mjs` for both the build and the query side.
    """

    fork = server.resolve().parent.parent
    data_dir = data_root / arm.name
    if data_dir.exists() and any(data_dir.iterdir()):
        raise RuntimeError(f"arm {arm.name}: {data_dir} is not empty; the replay refuses a dirty index directory")
    data_dir.mkdir(parents=True, exist_ok=True)
    head = _git_fork(["rev-parse", "HEAD"], fork).stdout.strip()
    replies_path = out_dir / "replies.json"
    try:
        if arm.patches:
            apply_patches(arm, fork)
        subprocess.run(["npm", "run", "build"], cwd=fork, check=True, capture_output=True, text=True)
        command = [
            sys.executable, str(REPO / "bench" / "golden_run.py"),
            "--bank", str(bank), "--export", str(export_dir), "--recipe", str(recipe),
            "--server", str(server), "--data-dir", str(data_dir), "--output", str(replies_path),
        ]
        log.info("arm %s: %s", arm.name, " ".join(command))
        subprocess.run(command, cwd=REPO, check=True)
    finally:
        if arm.patches:
            revert_patches(fork)
            subprocess.run(["npm", "run", "build"], cwd=fork, check=True, capture_output=True, text=True)
    bundle = json.loads(replies_path.read_text(encoding="utf-8"))
    return stamp_arm(bundle, arm, seed, {
        "simulation": False,
        "fork_head": head,
        "patches": [{"file": f, "old": o, "new": n} for f, o, n in arm.patches],
        "data_dir": str(data_dir),
    })


# --------------------------------------------------------------------------- subcommands


def _bank_by_id(bank_dir: Path) -> dict[str, dict[str, Any]]:
    return {question["id"]: question for question in load_bank(bank_dir)}


def cmd_list(args: argparse.Namespace) -> int:
    for arm in ARMS:
        state = "RUNNABLE" if arm.runnable else "NOT-RUN"
        tag = " (control)" if arm.control else ""
        print(f"{arm.name:22s} {arm.letter:8s} {arm.kind:6s} {state}{tag}")
        print(f"  {arm.summary}")
        if arm.target_lanes:
            print(f"  targets: lanes {', '.join(arm.target_lanes)}")
        if arm.target_mechanisms:
            print(f"           mechanisms {', '.join(arm.target_mechanisms)}")
        if arm.not_run_reason:
            print(f"  blocked: {arm.not_run_reason}")
        for note in arm.notes:
            print(f"  note: {note}")
        print()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    names = list(args.arm or [])
    if args.all:
        names = [arm.name for arm in ARMS]
    if not names:
        print("redstate: name at least one --arm, or --all", file=sys.stderr)
        return 2
    unknown = [name for name in names if name not in ARMS_BY_NAME]
    if unknown:
        print(f"redstate: unknown arm(s) {', '.join(unknown)}", file=sys.stderr)
        return 2

    try:
        thresholds = load_thresholds(args.spec)
        questions = load_bank(args.bank)
        export = load_export(args.export)
    except InputError as exc:
        print(f"redstate: input error — {exc}", file=sys.stderr)
        return 2
    bank = {question["id"]: question for question in questions}
    baseline_bundle = _read_json(args.baseline)
    baseline_report = score_bundle(baseline_bundle, questions, export, thresholds)
    args.out.mkdir(parents=True, exist_ok=True)
    _write_json(baseline_report, args.out / "baseline-report.json", compress=True)

    for name in names:
        arm = ARMS_BY_NAME[name]
        out_dir = args.out / arm.name
        out_dir.mkdir(parents=True, exist_ok=True)
        if not arm.runnable:
            _write_json(
                {"arm": arm.name, "letter": arm.letter, "kind": arm.kind, "state": "not-run",
                 "reason": arm.not_run_reason, "target_lanes": list(arm.target_lanes),
                 "target_mechanisms": list(arm.target_mechanisms), "notes": list(arm.notes)},
                out_dir / "not-run.json",
            )
            log.info("arm %s: not-run — %s", arm.name, (arm.not_run_reason or "")[:90])
            continue
        if arm.kind == "reply":
            bundle = run_reply_arm(arm, baseline_bundle, export, args.seed)
        else:
            if not args.server.is_file():
                log.warning("arm %s: no built server at %s — skipped", arm.name, args.server)
                _write_json(
                    {"arm": arm.name, "state": "not-run",
                     "reason": f"no built server at {args.server}: run `make upstream-checkout` then "
                               f"`npm ci && npm run build` in fork/"},
                    out_dir / "not-run.json",
                )
                continue
            bundle = run_build_arm(arm, args.server, args.data_root, out_dir, args.seed,
                                   args.bank, args.export, args.recipe)
        report = score_bundle(bundle, questions, export, thresholds)
        _write_json(bundle, out_dir / "replies.json", compress=True)
        _write_json(report, out_dir / "report.json", compress=True)
        (out_dir / "replies.json").unlink(missing_ok=True)

        # A build arm is differenced against the build control when one has been run, because
        # the committed baseline came from a checkout this harness does not pin.
        control_report_path = args.out / "control-build" / "report.json"
        reference, reference_name = baseline_report, "committed baseline"
        if arm.kind == "build" and not arm.control and _gz(control_report_path).exists():
            reference, reference_name = _read_json(control_report_path), "control-build"

        extra: dict[str, Any] = {"reference": reference_name}
        if arm.name == "index-cap":
            extra["computed_target_questions"] = cap_crossing_questions(bank, 2000)
        deltas = {
            predicate: compute_delta(arm, predicate, reference, report, bank, extra)
            for predicate in PREDICATES
        }
        _write_json({"arm": arm.name, "predicates": deltas}, out_dir / "delta.json")
        for predicate in PREDICATES:
            document = deltas[predicate]
            log.info(
                "arm %-20s %-16s present %d -> %d (%+d); MUST cells not red: %s",
                arm.name, predicate, document["present_before"], document["present_after"],
                document["delta"],
                ", ".join(f"{c['lane']}({c['reason']})" for c in document["must_cells_that_did_not_go_red"]) or "none",
            )
    return 0


def _matrix(out: Path) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for arm in ARMS:
        delta_path = out / arm.name / "delta.json"
        not_run_path = out / arm.name / "not-run.json"
        if delta_path.exists():
            rows[arm.name] = _read_json(delta_path)["predicates"]
        elif not_run_path.exists():
            rows[arm.name] = {"state": "not-run", "reason": _read_json(not_run_path).get("reason")}
    return rows


def cmd_read(args: argparse.Namespace) -> int:
    rows = _matrix(args.out)
    if not rows:
        print(f"redstate: nothing under {args.out}", file=sys.stderr)
        return 3
    for predicate in PREDICATES:
        print(f"\n=== predicate: {predicate} ===")
        print(f"{'arm':22s} {'kind':6s} {'present':>15s} {'delta':>7s}  MUST cells that did not go red")
        for name, row in rows.items():
            arm = ARMS_BY_NAME[name]
            if "state" in row:
                print(f"{name:22s} {arm.kind:6s} {'not-run':>15s} {'—':>7s}  {row['reason'][:60] if row.get('reason') else ''}")
                continue
            document = row[predicate]
            present = f"{document['present_before']} -> {document['present_after']}"
            cells = ", ".join(f"{c['lane']}[{c['reason']}]" for c in document["must_cells_that_did_not_go_red"])
            print(f"{name:22s} {arm.kind:6s} {present:>15s} {document['delta']:>+7d}  {cells or 'none'}")
    print("\nMUST cells, per arm, per predicate (n beside every count; a cell under "
          f"n={THIN_CELL} prints not-evaluated per SPEC §5.2.10):")
    for name, row in rows.items():
        if "state" in row:
            continue
        print(f"\n  {name}")
        for predicate in PREDICATES:
            cells = row[predicate]["must_cells"]
            rendered = "  ".join(
                f"{lane} {cells[lane]['present_before']}->{cells[lane]['present_after']}/n={cells[lane]['n']}"
                for lane in MUST_LANES if cells.get(lane, {}).get("n")
            )
            print(f"    {predicate:16s} {rendered}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list", help="the arms, their kind, their targets, their blockers")
    listing.set_defaults(func=cmd_list)

    run = subparsers.add_parser("run", help="run one or more arms and write their deltas")
    run.add_argument("--arm", action="append", help="arm name; repeatable")
    run.add_argument("--all", action="store_true", help="every arm, in registry order")
    run.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    run.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    run.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE)
    run.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    run.add_argument("--out", type=Path, default=DEFAULT_OUT)
    run.add_argument("--server", type=Path, default=DEFAULT_SERVER, help="built MCP server for build arms")
    run.add_argument("--data-root", type=Path, default=Path.home() / "data" / "redstate",
                     help="parent of each build arm's fresh index directory")
    run.add_argument("--spec", type=Path, default=REPO / "SPEC.md")
    run.add_argument("--seed", type=int, default=0)
    run.set_defaults(func=cmd_run)

    read = subparsers.add_parser("read", help="the cross-arm matrix")
    read.add_argument("--out", type=Path, default=DEFAULT_OUT)
    read.set_defaults(func=cmd_read)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
