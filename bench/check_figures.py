#!/usr/bin/env python3
"""Check that figures quoted in the prose still match the artifacts they came from.

Five times on one branch, a number was updated in an artifact and left stale in a
paragraph that the same commit rewrote around it. Every one was caught by a human
reviewer, three of them bounced a merge, and one reached a ticket that would have become
a permanent record. The class is mechanical: the figures live at stable key paths in
`bench/results/*.json`, and the prose that quotes them is a handful of files.

So this walks a declared map — prose file, artifact, key path, format — and fails when the
rendered figure is absent from the file that is supposed to carry it.

**Anchors, and why presence alone is not enough.** A bare "does this document contain
42 963" check passes as long as the figure appears *somewhere* — so when a figure is
quoted twice and one copy goes stale, which is precisely the recurrence this exists to
catch, the check stays green. Verified by sabotage: changing one cell of the latency
table to a superseded value left the plain check reporting 0 stale, because the same
number still appeared two paragraphs down. An entry may therefore declare an `anchor`, a
snippet with `{}` where the value belongs; the check is then positional and a wrong value
in that slot fails. Anchors are declared for every figure that has actually gone stale
here.

**What it does not do**, deliberately: it does not scan prose for numbers and try to
attribute them. That direction has no ground truth (a document legitimately cites other
artifacts, fixtures, and derived values), and a check that guesses produces noise until
someone turns it off. Declaring the load-bearing figures is the work; the check is then
exact, and a figure nobody declared is a figure nobody promised to keep current.

Usage:
    python3 bench/check_figures.py            # check
    python3 bench/check_figures.py --list     # show every declared figure and its value
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("figures")

REPO = Path(__file__).resolve().parent.parent

#: Files that must carry a figure, by short name.
PROSE = {
    "state": "STATE.md",
    "t0008": "tickets/0008-quantize-the-vector-column-binary-first.erg",
    "t0008c": "tickets/closed/0008-quantize-the-vector-column-binary-first.erg",
    "t0001": "tickets/0001-replace-the-resident-js-index-with-sqlit.erg",
    "t0001c": "tickets/closed/0001-replace-the-resident-js-index-with-sqlit.erg",
    "readme": "README.md",
}

#: Every character that has been used as a thousands separator in these documents.
#: ASCII space is what they actually contain; the others are here because a narrow
#: no-break space leaked from the prose into the FIRST version of this very function,
#: which then reported all fifty pairs stale. A checker that cries wolf on everything is
#: retired by its reader as fast as one that never fires.
SEPARATORS = " \u00a0\u202f\u2009_"

_DIGIT_SEP = re.compile(rf"(?<=\d)[{SEPARATORS}](?=\d)")


def despace(text: str) -> str:
    """Drop separators sitting between two digits, so 360 811 and 360811 compare equal."""
    return _DIGIT_SEP.sub("", text)


def render_value(value, places: int, pct: bool = False) -> str:
    """A scalar, or a two-element range rendered as `lo-hi`.

    Declaring the ends of a range as two separate figures made each one's anchor contain
    the other's value, so fixing either broke the other — an avoidable coupling that the
    fixer surfaced immediately by refusing both.
    """
    if isinstance(value, list) and len(value) == 2:
        return f"{rendered(value[0], places, pct)}-{rendered(value[1], places, pct)}"
    return rendered(value, places, pct)


def rendered(value: float, places: int, pct: bool = False) -> str:
    """The figure with no thousands separator and a decimal comma — the comparison form.

    `pct` covers a fraction the prose writes as a percentage. A rendering the declaration
    cannot express is a figure the check quietly cannot cover, so the modes live here
    rather than in an exception list.
    """
    if pct:
        value *= 100
    return f"{value:.{places}f}".replace(".", ",")


def display(value, places: int, pct: bool = False) -> str:
    """How it reads in the documents, for messages only."""
    if isinstance(value, list) and len(value) == 2:
        return f"{display(value[0], places, pct)}-{display(value[1], places, pct)}"
    if pct:
        value *= 100
    text = f"{value:,.{places}f}".replace(",", "\u00a0").replace(".", ",").replace("\u00a0", " ")
    return text + "%" if pct else text


#: A figure is (artifact, key path, places, {prose key: anchor-or-None}), optionally with
#: "pct" when the prose writes the fraction as a percentage. An anchor is a snippet with
#: `{}` marking the slot; None falls back to the weaker presence check. A figure may
#: legitimately live in several documents; it must be current in every one that claims it.
FIGURES = [
    # ---- 0008, the real-vector measurement. The latency table is anchored: every stale
    # figure on this branch was a table cell whose value also appeared elsewhere.
    ("0008-real-vectors/real-93022.json", "corpus.vectors", 0,
     {"t0008": "{} passages of the real library", "state": "**{} real passages"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.exact_k30.median_ms", 1,
     {"t0008": "Exact float32 scan at k=30: **{} ms**", "state": "vs exact ({} ms)"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.two_stage_pool_4x.median_ms", 1,
     {"t0008": "| 0,918 | {} ms |", "state": "| 0,918 | {} ms |"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.two_stage_pool_8x.median_ms", 1,
     {"t0008": "| 0,969 | {} ms |", "state": "| 0,969 | {} ms |"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.two_stage_pool_16x.median_ms", 1,
     {"t0008": "| 0,991 | {} ms |", "state": "| 0,991 | {} ms |"}),
    ("0008-real-vectors/real-93022.json", "anisotropy.corpus_mean_norm", 3,
     {"t0008": "mean norm {}", "state": "norm **{}**"}),
    ("0008-real-vectors/real-93022.json", "anisotropy.most_one_sided_LIVE_dimension.one_sided", 3,
     {"t0008": "tops out at **{}**", "state": "tops out at **{}**"}),
    ("0008-real-vectors/real-93022.json", "on_disk.float32_bytes_per_vector", 1,
     {"t0008": "**{} B per float32", "state": "**{} B per float32"}),
    ("0008-real-vectors/real-93022.json", "on_disk.binary_bytes_per_vector", 1,
     {"t0008": "against {} B per binary", "state": "against {} B per binary"}),
    ("0008-real-vectors/real-93022.json", "probe_design.exact_topk_from_the_probe_own_item", 1,
     {"t0008": "**{}% of a probe's exact top-30"}, "pct"),
    ("0008-real-vectors/build.json", "elapsed_s", 1, {"t0008": "**{} s wall clock**"}),
    # The headline recall column — the most-quoted numbers in the ticket, and unreachable
    # until dig() learned to walk lists. Anchored on the table rows they live in.
    ("0008-real-vectors/real-93022.json", "recall.2.recall_threshold_zero", 3,
     {"t0008": "| 0,628 | **{}**", "state": "| 0,628 | **{}**"}),
    ("0008-real-vectors/real-93022.json", "recall.2.recall_mean_centred", 3,
     {"t0008": "**0,884** | {} |", "state": "**0,884** | {} |"}),
    ("0008-real-vectors/real-93022.json", "recall.3.recall_threshold_zero", 3,
     {"t0008": "| 0,862 | **{}**", "state": "| 0,862 | **{}**"}),
    ("0008-real-vectors/real-93022.json", "recall.3.recall_mean_centred", 3,
     {"t0008": "**0,953** | {} |", "state": "**0,953** | {} |"}),
    ("0008-real-vectors/real-93022.json", "recall.4.recall_threshold_zero", 3,
     {"t0008": "| 0,998 | {} |", "state": "| 0,998 | {} |"}),
    # The figure whose staleness bounced this branch twice. Declaring it is the point.
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.iqr_pct_range_all_candidates", 1,
     {"t0008": "the spreads fell to **{}%**", "state": "shuffling brought them to {}%"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.iqr_pct_range_two_stage", 1,
     {"t0008": "**{}%** across the three two-stage rows"}),
    ("0008-real-vectors/real-93022.json", "coarse_pool_fidelity.recall_via_vec0_pool.2.via_vec0_pool", 4,
     {"t0008": "(0,8840 against {} at 4x"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.binary_first_pass_k240.median_ms", 1,
     {"t0008": "At 8x it is {} ms of the", "state": "it is {} ms of the"}),
    # ---- 0001, the like-for-like comparison ----
    ("0001-old-vs-new/SUMMARY.json", "corpus.passages", 0,
     {"t0001": None, "state": None, "readme": "one corpus of {} passages"}),
    ("0001-old-vs-new/SUMMARY.json", "startup_s.json", 2,
     {"t0001": "| startup to first answer | {} s |", "state": "| startup to first answer | **{} s**",
      "readme": "**{} s\nagainst"}),
    ("0001-old-vs-new/SUMMARY.json", "startup_s.sqlite", 2, {"t0001": None, "state": None, "readme": None}),
    ("0001-old-vs-new/SUMMARY.json", "resident_mib.json_after_16_queries", 1,
     {"t0001": "| resident after 16 queries | {} MiB |", "state": "| resident after 16 queries | **{} MiB**",
      "readme": "**{} MiB against"}),
    ("0001-old-vs-new/SUMMARY.json", "resident_mib.sqlite_after_16_queries", 1,
     {"t0001": None, "state": None, "readme": None}),
    ("0001-old-vs-new/SUMMARY.json", "memory_caveat.conservative_ratio", 1,
     {"state": "a\n**{}x** win", "readme": "win is {}x rather"}),
    ("0001-old-vs-new/uncapped_stock_node.json", "status.documents", 0, {"t0001": None, "state": None}),
    # ---- 0005, the migration ----
    ("0005-migration/migrate_463MB.json", "ratio_db_over_json", 4, {"state": None}),
    # ---- 0009, the fold sweep ----
    ("0009-fold-sweep/codepoints.json", "codepoints_swept", 0, {"state": None}),
    ("0009-fold-sweep/codepoints.json", "codepoints_agreeing", 0, {"state": "**{} of 1 301 agreeing"}),
    # ---- 0012, the two version sequences ----
    ("0012-fulltext-sequence/sequences.json", "library_version_from_items_header", 0, {"state": None}),
    ("0012-fulltext-sequence/sequences.json", "fulltext_version_max", 0, {"state": None}),
    ("0012-fulltext-sequence/sequences.json", "fulltext_entries_total", 0, {"state": None}),
    # ---- 0013, concentration ----
    ("0013-concentration/uncapped-477512.json", "passages_total", 0, {"state": None}),
    ("0013-concentration/uncapped-477512.json", "dominant_item.passages", 0,
     {"state": "holds **{} of 477 512"}),
    ("0013-concentration/uncapped-477512.json", "next_largest_passages", 0,
     {"state": "against {} for the next largest"}),
]


def dig(obj, path: str):
    """Walk a dotted key path, through lists as well as dicts.

    Lists were unreachable in the first version — `dict.get()` only — so every declaration
    naming one silently resolved to None and was reported as a missing key. The headline
    recall figures live in a list, which is how the ticket's most-quoted numbers came to be
    the ones the checker could not see.
    """
    for part in path.split("."):
        if obj is None:
            return None
        if isinstance(obj, list):
            try:
                obj = obj[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=str(REPO / "bench" / "results"))
    ap.add_argument("--verbose", action="store_true", help="name every presence-only pair")
    ap.add_argument("--fix", action="store_true", help="rewrite anchored slots from the artifacts")
    ap.add_argument("--list", action="store_true", help="print every declared figure and its current value")
    a = ap.parse_args()
    if a.fix:
        return fix(a.results)

    cache: dict[str, dict] = {}
    text: dict[str, str] = {}
    failures: list[str] = []
    unanchored: list[str] = []
    checked = 0
    anchored = 0

    for entry in FIGURES:
        artifact, path, places, prose_keys = entry[:4]
        pct = len(entry) > 4 and entry[4] == "pct"
        f = Path(a.results) / artifact
        if not f.exists():
            failures.append(f"MISSING ARTIFACT {artifact} (declared for {path})")
            continue
        if artifact not in cache:
            cache[artifact] = json.loads(f.read_text())
        value = dig(cache[artifact], path)
        if value is None:
            failures.append(f"MISSING KEY {artifact}:{path}")
            continue
        want = render_value(value, places, pct)
        if a.list:
            log.info("%-46s %-58s %s", artifact, path, display(value, places, pct))
        for key, anchor in prose_keys.items():
            doc = REPO / PROSE[key]
            if not doc.exists():
                continue  # a ticket archived under closed/ is checked at its closed path
            if key not in text:
                text[key] = despace(doc.read_text())
            checked += 1
            if anchor is None:
                ok = want in text[key]
                where = "anywhere in"
                unanchored.append(f"{artifact}:{path} in {PROSE[key]}")
            else:
                anchored += 1
                # Positional: the slot must hold this value. A stale duplicate elsewhere
                # in the document cannot mask it.
                ok = despace(anchor.replace("{}", want)) in text[key]
                where = f"at anchor {anchor!r} in"
            if not ok:
                failures.append(
                    f"STALE  {artifact}:{path} = {display(value, places, pct)} not found "
                    f"{where} {PROSE[key]}"
                )

    if a.list:
        return 0
    for line in failures:
        log.error("%s", line)
    # Anchored and presence-only are reported apart, because they are not the same check.
    # A presence-only pair is satisfied by the figure appearing ANYWHERE in the document,
    # so a stale duplicate elsewhere masks it — which is the very recurrence this exists to
    # catch. Summing them into one number would quote a coverage the mechanism does not
    # support, and that is the defect class this file was written against.
    log.info(
        "%d pairs checked: %d anchored (positional), %d presence-only (maskable), %d stale",
        checked, anchored, len(unanchored), len(failures),
    )
    if unanchored and a.verbose:
        for u in unanchored:
            log.info("  presence-only: %s", u)
    return 1 if failures else 0


#: `--fix` rewrites the slot an anchor names, from the artifact.
#:
#: Only anchored figures, and only where the anchor matches exactly once — an anchor that
#: matches twice names no single slot, and guessing which one is meant is how an automatic
#: edit corrupts a document. Presence-only figures are never touched: there is no slot to
#: write into, so there is nothing an automaton can safely do but report them.
#:
#: This is the end state the anchors were for. Hand-transcribing a figure from an artifact
#: into six documents is the operation that failed five times on this branch; it is not a
#: discipline problem, it is a copying problem, and copying is what a machine is for.
def fix(results_dir: str) -> int:
    cache: dict[str, dict] = {}
    edits = 0
    refused: list[str] = []
    for entry in FIGURES:
        artifact, path, places, prose_keys = entry[:4]
        pct = len(entry) > 4 and entry[4] == "pct"
        f = Path(results_dir) / artifact
        if not f.exists():
            continue
        if artifact not in cache:
            cache[artifact] = json.loads(f.read_text())
        value = dig(cache[artifact], path)
        if value is None:
            continue
        want = render_value(value, places, pct)
        for key, anchor in prose_keys.items():
            if anchor is None:
                continue
            doc = REPO / PROSE[key]
            if not doc.exists():
                continue
            body = doc.read_text()
            # De-spaced exactly as the check does, or an anchor whose literal text
            # contains a separated thousand ("of 1 301 agreeing") matches in the check and
            # not in the fixer — two mechanisms disagreeing about the same anchor.
            head, _, tail = despace(anchor).partition("{}")
            pattern = re.compile(
                re.escape(head) + r"([0-9" + SEPARATORS + r",.\-]+?)" + re.escape(tail)
            )
            hits = pattern.findall(despace(body))
            if len(hits) != 1:
                refused.append(f"{PROSE[key]}: anchor {anchor!r} matched {len(hits)} slots")
                continue
            new_body = re.sub(
                pattern, lambda _m: head + want + tail, despace(body), count=1
            )
            if new_body != despace(body):
                # Written back de-spaced only where the slot was; the rest of the document
                # keeps its own separators because only this span was rebuilt.
                doc.write_text(rewrite_slot(body, pattern, head + want + tail))
                edits += 1
    for r in refused:
        log.warning("REFUSED %s", r)
    log.info("%d slot(s) rewritten, %d refused", edits, len(refused))
    return 0


def rewrite_slot(body: str, pattern: re.Pattern, replacement: str) -> str:
    """Apply `pattern` to the de-spaced body, then map the edit back onto the original.

    Matching has to happen de-spaced (the documents separate thousands, the artifact does
    not), but writing has to happen on the original text or every other separator in the
    file would be silently stripped. So: find the span de-spaced, find the same span in the
    original by walking both in step, and replace only that.
    """
    flat = despace(body)
    m = pattern.search(flat)
    if not m:
        return body
    # Walk the original alongside the flattened text to locate the same span.
    i = j = 0
    start = end = None
    while i < len(body) and j <= len(flat):
        if j == m.start() and start is None:
            start = i
        if j == m.end():
            end = i
            break
        if j < len(flat) and body[i] == flat[j]:
            j += 1
        i += 1
    if start is None or end is None:
        return body
    return body[:start] + replacement + body[end:]


if __name__ == "__main__":
    sys.exit(main())
