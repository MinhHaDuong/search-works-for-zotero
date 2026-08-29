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
#: A ticket is named by its FILENAME, not its directory, because closing one moves it from
#: `tickets/` to `tickets/closed/`. The first version listed both paths as separate keys
#: and skipped whichever did not exist — so archiving ticket 0008 silently dropped its 23
#: declarations, coverage fell from 68 pairs to 45, and nothing failed. A check whose
#: all-clear is indistinguishable from "I could not look" is not a check, and a guard
#: against stale figures that quietly stops guarding the moment a ticket closes is the
#: worst version of it: the document becomes permanent at exactly that moment.
PROSE = {
    "state": ["STATE.md"],
    "readme": ["README.md"],
    "sync": ["SYNC.md"],
    "design": ["DESIGN.md"],
    "requirements": ["REQUIREMENTS.md"],
    "t0025": [
        "tickets/0025-experiments-x1-x7-each-before-its-depend.erg",
        "tickets/closed/0025-experiments-x1-x7-each-before-its-depend.erg",
    ],
    "t0026": [
        "tickets/0026-repo-side-gates-fold-golden-rss-converge.erg",
        "tickets/closed/0026-repo-side-gates-fold-golden-rss-converge.erg",
    ],
    "t0014": [
        "tickets/0014-shepherd-prs-19-and-20-to-merge-stopword.erg",
        "tickets/closed/0014-shepherd-prs-19-and-20-to-merge-stopword.erg",
    ],
    "t0008": [
        "tickets/0008-quantize-the-vector-column-binary-first.erg",
        "tickets/closed/0008-quantize-the-vector-column-binary-first.erg",
    ],
    "t0001": [
        "tickets/0001-replace-the-resident-js-index-with-sqlit.erg",
        "tickets/closed/0001-replace-the-resident-js-index-with-sqlit.erg",
    ],
}


def resolve(key: str) -> Path | None:
    """The one path that exists for this document, or None if it has genuinely vanished."""
    for candidate in PROSE[key]:
        path = REPO / candidate
        if path.exists():
            return path
    return None

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
    if isinstance(value, list):
        # A per-run sequence, written a/b/c/d. Declared because the sentence quoting it
        # claims the runs are read from the artifact rather than reconstructed from git
        # history — and it was, twice, quoting the previous run while saying so.
        return "/".join(rendered(v, places, pct) for v in value)
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
    if isinstance(value, list) and len(value) > 2:
        return "/".join(display(v, places, pct) for v in value)
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
     {"t0008": "mean norm {}, and", "state": "norm **{}**"}),
    ("0008-real-vectors/real-93022.json", "anisotropy.most_one_sided_LIVE_dimension.one_sided", 3,
     {"t0008": "tops out at **{}**", "state": "tops out at **{}**"}),
    ("0008-real-vectors/real-93022.json", "on_disk.float32_bytes_per_vector", 1,
     {"t0008": "**{} B per float32", "state": "**{} B per float32"}),
    ("0008-real-vectors/real-93022.json", "on_disk.binary_bytes_per_vector", 1,
     {"t0008": "against {} B per binary", "state": "against {} B per binary"}),
    ("0008-real-vectors/real-93022.json", "probe_design.exact_topk_from_the_probe_own_item", 1,
     {"t0008": "**{}% of a probe's exact top-30"}, "pct"),
    ("0008-real-vectors/build.json", "elapsed_s", 1, {"t0008": "**{} s wall clock**"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.speedup_vs_exact_per_run.two_stage_pool_4x", 2,
     {"t0008": "git history: {}\nat the 4x pool", "state": "(4x pool {}x)"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.speedup_vs_exact_per_run.two_stage_pool_8x", 2,
     {"t0008": "at the 4x pool, {} at 8x"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.speedup_vs_exact_per_run.two_stage_pool_16x", 2,
     {"t0008": "at 8x, {} at 16x"}),
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
     {"t0001": None, "state": None, "readme": "one corpus of {} passages", "sync": "of {} passages read"}),
    ("0001-old-vs-new/SUMMARY.json", "startup_s.json", 2,
     {"t0001": "| startup to first answer | {} s |", "state": "| startup to first answer | **{} s**",
      "readme": "**{} s\nagainst", "sync": "and {} s against"}),
    ("0001-old-vs-new/SUMMARY.json", "startup_s.sqlite", 2,
     {"t0001": None, "state": None, "readme": None, "sync": "against {} s to first answer"}),
    ("0001-old-vs-new/SUMMARY.json", "resident_mib.json_after_16_queries", 1,
     {"t0001": "| resident after 16 queries | {} MiB |", "state": "| resident after 16 queries | **{} MiB**",
      "readme": "**{} MiB against", "sync": "{} MiB against"}),
    ("0001-old-vs-new/SUMMARY.json", "resident_mib.sqlite_after_16_queries", 1,
     {"t0001": None, "state": None, "readme": None, "sync": "{} MiB resident and"}),
    ("0001-old-vs-new/SUMMARY.json", "memory_caveat.conservative_ratio", 1,
     {"state": "a\n**{}x** win", "readme": "win is {}x rather", "sync": "{}x rather than 45x"}),
    ("0001-old-vs-new/uncapped_stock_node.json", "status.documents", 0, {"t0001": None, "state": None}),
    # ---- 0005, the migration ----
    ("0005-migration/migrate_463MB.json", "ratio_db_over_json", 4, {"state": None}),
    # ---- 0009, the fold sweep ----
    ("0009-fold-sweep/codepoints.json", "codepoints_swept", 0, {"state": None}),
    ("0009-fold-sweep/codepoints.json", "codepoints_agreeing", 0, {"state": "**{} of 1 301 agreeing"}),
    # ---- 0012, the two version sequences ----
    ("0012-fulltext-sequence/sequences.json", "library_version_from_items_header", 0, {"state": None}),
    ("0012-fulltext-sequence/sequences.json", "fulltext_version_max", 0, {"state": None}),
    ("0012-fulltext-sequence/sequences.json", "fulltext_entries_total", 0,
     {"state": None, "design": None}),
    ("0012-fulltext-sequence/sequences.json",
     "fraction_of_library_reported_new_at_library_version", 1,
     {"design": None, "requirements": None}, "pct"),
    # ---- 0011, the uncapped-build RSS — quoted by the redesign's gate and experiments ----
    ("0011-rss/capped-vs-uncapped.json", "baseline_uncapped_chars.peak_MiB", 1,
     {"design": None, "t0025": None, "t0026": None}),
    # ---- 0013, concentration ----
    ("0013-concentration/uncapped-477512.json", "passages_total", 0, {"state": None}),
    ("0013-concentration/uncapped-477512.json", "dominant_item.passages", 0,
     {"state": "holds **{} of 477 512"}),
    ("0013-concentration/uncapped-477512.json", "next_largest_passages", 0,
     {"state": "against {} for the next largest"}),
    # ---- 0025 X7, census parse cost (synthetic wire shape, container CPU) ----
    ("0025-x7-census/parse-cost.json", "rows.1.median_ms", 2,
     {"t0025": "at 30 000 entries median {} ms and"}),
    ("0025-x7-census/parse-cost.json", "rows.1.p95_ms", 2,
     {"t0025": "a p95 of {} ms — under the 50 ms rule"}),
    ("0025-x7-census/parse-cost.json", "rows.0.median_ms", 2,
     {"t0025": "8 037 entries the tick costs {} ms;"}),
    ("0025-x7-census/parse-cost.json", "rows.2.median_ms", 2,
     {"t0025": "it reaches {} ms median, where the rule"}),
    # ---- 0025 X1 timing half, slab vs rows (synthetic vectors, container CPU) ----
    ("0025-x1-timing/slab-vs-rows.json", "rows.1.rows.median_ms", 1,
     {"t0025": "per-row BLOB rows cost {} ms median"}),
    ("0025-x1-timing/slab-vs-rows.json", "rows.1.slab.median_ms", 1,
     {"t0025": "the float32 slab costs {} ms and"}),
    ("0025-x1-timing/slab-vs-rows.json", "rows.1.int8.median_ms", 1,
     {"t0025": "the int8 slab {} ms, both under"}),
    ("0025-x1-timing/slab-vs-rows.json", "rows.0.rows.median_ms", 1,
     {"t0025": "rows {} ms, slab"}),
    ("0025-x1-timing/slab-vs-rows.json", "rows.0.slab.median_ms", 1,
     {"t0025": "slab {} ms, int8"}),
    ("0025-x1-timing/slab-vs-rows.json", "rows.0.int8.median_ms", 1,
     {"t0025": "int8 scans in {} ms. DECISION"}),
    # ---- 0025 X2, stopword-less OR p95 (REAL 477k index + stock control arm, doudou) ----
    # Both arms are declared, because the verdict is a comparison: a re-measurement that moved
    # only the control would leave the treatment figure true and the conclusion false.
    ("0025-x2-stopwordless/x2-verdict.json", "warm_p95_ms.stopword_less", 1,
     {"t0025": "Warm p95 stopword-less = {} ms against the ~500 ms rule",
      "t0014": "Warm p95 stopword-less = {} ms at 477 512 passages",
      "state": "warm p95 is {} ms against the"}),
    ("0025-x2-stopwordless/x2-verdict.json", "warm_p95_ms.stock_with_stoplist", 1,
     {"t0025": "answers them at a warm p95 of {} ms, inside the allowance",
      "t0014": "same index and queries answers at {} ms",
      "state": "twenty queries answers at {} ms"}),
    ("0025-x2-stopwordless/x2-verdict.json", "ratio_p95", 1,
     {"t0025": "the deletion multiplies p95 by {} and", "t0014": "({}x on p95",
      "state": "({}\u00d7 on\n  p95"}),
    ("0025-x2-stopwordless/x2-verdict.json", "ratio_p50", 1,
     {"t0025": "the median by {} (1 233,2 vs 215,7 ms)", "t0014": "{}x on the median)",
      "state": "{}\u00d7 on the median)"}),
    ("0025-x2-stopwordless/x2-verdict.json", "warm_p50_ms.stopword_less", 1,
     {"t0025": "({} vs 215,7 ms)"}),
    ("0025-x2-stopwordless/x2-verdict.json", "warm_p50_ms.stock_with_stoplist", 1,
     {"t0025": "(1 233,2 vs {} ms)"}),
    # The floor, not the tail: this is the number that says no query in the population made
    # the budget, which is what rules out a re-run with a gentler query set.
    ("0025-x2-stopwordless/x2-verdict.json", "warm_min_ms.stopword_less", 1,
     {"t0025": "The cheapest of the twenty still costs {} ms"}),
    ("0025-x2-stopwordless/x2-verdict.json", "rebuild.elapsed_s", 1,
     {"t0025": "{} s and 1 755,6 MiB on doudou"}),
    ("0025-x2-stopwordless/x2-verdict.json", "rebuild.peak_rss_mib", 1,
     {"t0025": "263,7 s and {} MiB on doudou"}),
    # ---- 0025 X2 mechanism annex: where the cost comes from, and what it buys ----
    ("0025-x2-stopwordless/x2-mechanism.json", "corpus.stopword_share_of_tokens", 1,
     {"t0025": "and {}% of all token occurrences"}, "pct"),
    ("0025-x2-stopwordless/x2-mechanism.json", "totals.postings_ratio", 1,
     {"t0025": "a factor of {}, while time rises"}),
    ("0025-x2-stopwordless/x2-mechanism.json", "totals.ns_per_posting_stock", 1,
     {"t0025": "per entry ({} ns ->"}),
    ("0025-x2-stopwordless/x2-mechanism.json", "totals.ns_per_posting_new", 1,
     {"t0025": "-> {} ns), so this is a design cost"}),
    # The number that decides whether the deletion is worth its cost at all.
    ("0025-x2-stopwordless/x2-mechanism.json", "what_it_buys.mean_top20_overlap", 1,
     {"t0025": "overlap between the arms is {}%", "t0014": "{}% identical top-20"}, "pct"),
    # ---- Zotero's own search: the null alternative, and the baseline every latency
    # figure here lacked. One pass per query, so declared but coarse by construction.
    ("0025-x2-stopwordless/zotero-native-baseline.json", "latency_ms.median", 1,
     {"t0025": "median {} ms, p95"}),
    # No space after `p95` on purpose. Anchors are matched against the DESPACED text, and
    # `p95` ends in a digit, so the separator before the figure sits between two digits and
    # despace() glues them: `p95 4 198,5` compares as `p954198,5`. An anchor head ending in
    # a digit must therefore drop the space the prose actually has. The guard caught this
    # as a stale figure, which is the right refusal for the wrong-looking reason.
    ("0025-x2-stopwordless/zotero-native-baseline.json", "latency_ms.p95", 1,
     {"t0025": "p95{} ms, against 392,3 ms stock"}),
    ("0025-x2-stopwordless/zotero-native-baseline.json", "matches_per_query.median", 0,
     {"t0025": "the median query matches {} items"}),
    # ---- The library-derived droplist sweep. Three figures decide the design: the
    # threshold DESIGN §3 names and does not reach the budget at, and the working policy's
    # cost and fidelity. Every anchor head here ends in a non-digit on purpose — `p50 ` and
    # `p95 ` would be glued to the value by despace(), per the note above.
    ("0025-x2-stopwordless/df-droplist-sweep.json", "threshold_sweep.df_ge_50pct.p95_ms", 1,
     {"t0025": "terms drop and p95 stays at {} ms"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json", "recommended_policy.p50_ms", 1,
     {"t0025": "fallback): p50{} ms", "t0014": "gives p50{} ms"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json", "recommended_policy.p95_ms", 1,
     {"t0025": "p95{} ms, 98% top-30 overlap", "t0014": "and p95{} ms with 98%"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json",
     "recommended_policy.mean_top30_overlap_with_unfiltered", 0,
     {"t0025": "ms, {}% top-30 overlap with the unfiltered",
      "t0014": "with {}% of the unfiltered"}, "pct"),
    # ---- Multilingual cost. The French/English pair is the claim; `in`'s frequency is
    # the mechanism behind the German anomaly. Anchor heads end in non-digits, as above.
    ("0025-x2-stopwordless/multilingual-cost.json", "latency_ms_median.French.no_filter", 0,
     {"t0025": "a French query costs {} ms"}),
    ("0025-x2-stopwordless/multilingual-cost.json", "latency_ms_median.English.no_filter", 0,
     {"t0025": "matched English one costs {} ms"}),
    ("0025-x2-stopwordless/multilingual-cost.json",
     "latency_ms_median.French.median_postings_unfiltered", 0,
     {"t0025": "walking {} postings against"}),
    ("0025-x2-stopwordless/multilingual-cost.json",
     "latency_ms_median.English.median_postings_unfiltered", 0,
     {"t0025": "postings against {} — eighteen times cheaper"}),
    ("0025-x2-stopwordless/multilingual-cost.json",
     "latency_ms_median.German.df30_plus_fallback", 0,
     {"t0025": "the droplist gives {} ms"}),
    # ---- 0025 X4, json_each-constrained MATCH (synthetic corpus, container CPU) ----
    ("0025-x4-constrained-match/synthetic-477k.json", "rows.0.median_ms", 1,
     {"t0025": "whole corpus costs {} ms median"}),
    ("0025-x4-constrained-match/synthetic-477k.json", "rows.1.median_ms", 0,
     {"t0025": "constrained query costs {} ms median"}),
    ("0025-x4-constrained-match/synthetic-477k.json", "rows.4.median_ms", 0,
     {"t0025": "reaching {} ms median at"}),
]


def _validate_anchors() -> None:
    """An anchor must delimit its slot on BOTH sides.

    With an empty tail the slot has no right-hand boundary, so the match runs on into
    whatever follows the number — a trailing comma, the next word. That is not a style
    preference: the fixer this file used to carry produced `0,406,406,406and` from exactly
    such an anchor and the checker, then a substring test, certified the file it had
    broken. The fixer is gone; the trap that fed it is refused here.
    """
    bad = [
        (path, key, anchor)
        for entry in FIGURES
        for key, anchor in entry[3].items()
        if anchor is not None and not anchor.partition("{}")[2].strip()
        for path in [entry[1]]
    ]
    if bad:
        for path, key, anchor in bad:
            log.error("BAD ANCHOR %s in %s: %r has nothing after the slot", path, key, anchor)
        raise SystemExit(2)


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


def main_for_test(results_dir: str, verbose: bool = False) -> int:
    """The check, callable without argv. Exists so `tests/test_check_figures.py` drives the
    real code path rather than a copy of it — a test that reimplements the check tests the
    reimplementation."""
    return run(results_dir, verbose=verbose, listing=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=str(REPO / "bench" / "results"))
    ap.add_argument("--verbose", action="store_true", help="name every presence-only pair")
    ap.add_argument("--list", action="store_true", help="print every declared figure and its current value")
    a = ap.parse_args()
    _validate_anchors()
    return run(a.results, verbose=a.verbose, listing=a.list)


def run(results_dir: str, verbose: bool = False, listing: bool = False) -> int:
    _validate_anchors()
    cache: dict[str, dict] = {}
    text: dict[str, str] = {}
    failures: list[str] = []
    unanchored: list[str] = []
    checked = 0
    anchored = 0

    for entry in FIGURES:
        artifact, path, places, prose_keys = entry[:4]
        pct = len(entry) > 4 and entry[4] == "pct"
        f = Path(results_dir) / artifact
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
        if listing:
            log.info("%-46s %-58s %s", artifact, path, display(value, places, pct))
        for key, anchor in prose_keys.items():
            doc = resolve(key)
            if doc is None:
                # Reported, never skipped. Skipping is how 23 checks disappeared when a
                # ticket was archived and the run still said "0 stale".
                failures.append(
                    f"MISSING DOCUMENT {key}: none of {PROSE[key]} exists "
                    f"(declared for {artifact}:{path})"
                )
                continue
            if key not in text:
                text[key] = despace(doc.read_text())
            checked += 1
            if anchor is None:
                ok = want in text[key]
                where = "anywhere in"
                unanchored.append(f"{artifact}:{path} in {doc.relative_to(REPO)}")
            else:
                anchored += 1
                # Positional, and the slot's content compared rather than merely found.
                #
                # The corruption that motivated this — a slot holding `0,406,406,406`
                # passing a check for `0,406` — required an anchor with an EMPTY tail, and
                # `_validate_anchors` now refuses those. So with the tails delimited this
                # is equivalent to the substring test it replaced: sabotaging it leaves the
                # suite green, which is recorded in the test rather than hidden. Kept as
                # defence in depth against an anchor whose tail begins with a digit-like
                # character, not claimed as the load-bearing guard.
                head, _, tail = despace(anchor).partition("{}")
                pattern = re.compile(
                    # `/` so a per-run sequence (2,99/3,01/…) is one slot, `-` so a
                    # range (1,8-10,0) is one slot.
                    re.escape(head) + r"(?P<slot>[0-9,./\-]+)" + re.escape(tail)
                )
                found = [m.group("slot") for m in pattern.finditer(text[key])]
                ok = want in found
                where = (
                    f"at anchor {anchor!r} (slot holds {found!r}) in" if found
                    else f"at anchor {anchor!r} (no slot matched) in"
                )
            if not ok:
                failures.append(
                    f"STALE  {artifact}:{path} = {display(value, places, pct)} not found "
                    f"{where} {doc.relative_to(REPO)}"
                )

    if listing:
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
    if unanchored and verbose:
        for u in unanchored:
            log.info("  presence-only: %s", u)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
