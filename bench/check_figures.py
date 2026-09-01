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
    "readme": ["README.md"],
    "sync": ["SYNC.md"],
    "design": ["SPEC.md"],
    "requirements": ["SPEC.md"],
    # Ticket 0160: SPEC.md quotes 0012's sequence-probe figures as "measured" —
    # C1's two-sequences sentence and C1's since=0 scoping bullet — and was the one live
    # instance the first pass of that ticket missed, because its figures use space
    # thousands with no decimal comma, so a decimal-comma grep returns zero. A scan finds
    # figures only in the shape it was written for.
    "constraints": ["SPEC.md"],
    # The ratification ledger quotes measured figures while a ruling is pending, and until
    # 2026-08-29 it was the one prose document with no entry here — so every number in it
    # was unguarded, and the X1 entry drifted onto a superseded run within a day of being
    # written. An append-only ledger is the worst place for a stale figure: a ratified
    # entry is never edited again, so a wrong number there becomes permanent.
    "decisions": ["DECISIONS.md"],
    # verification/ reports settle a factual question and quote artifact figures to do
    # it, so they need the guard as much as the tracker does. The map is hand-listed,
    # which fails asymmetrically: removing a guarded file is loud, a new file ARRIVING
    # unguarded is silent. This one arrived 2026-08-29.
    "v30": ["verification/issue-30-thread.md"],
    "v0220": ["verification/DEVICE-AUTO-0220.md"],
    "v0267": ["verification/EMBEDDER-RECOMMENDATION-0267.md"],
    "vsmoke": ["verification/SMOKE-1.10.0.md"],
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
    "t0070": [
        "tickets/0070-fuse-the-cosine-loop-upstream-s-vector-s.erg",
        "tickets/closed/0070-fuse-the-cosine-loop-upstream-s-vector-s.erg",
    ],
    "t0001": [
        "tickets/0001-replace-the-resident-js-index-with-sqlit.erg",
        "tickets/closed/0001-replace-the-resident-js-index-with-sqlit.erg",
    ],
    "t0263": [
        "tickets/0263-cpu-arm-cost-and-fidelity-for-every-cand.erg",
        "tickets/closed/0263-cpu-arm-cost-and-fidelity-for-every-cand.erg",
    ],
    "t0481": [
        "tickets/0481-the-gpu-throughput-anomaly-find-the-mech.erg",
        "tickets/closed/0481-the-gpu-throughput-anomaly-find-the-mech.erg",
    ],
    "t0482": [
        "tickets/0482-re-run-the-gpu-fidelity-and-x8-cells-wit.erg",
        "tickets/closed/0482-re-run-the-gpu-fidelity-and-x8-cells-wit.erg",
    ],
    "v0482": ["verification/GPU-CORRECTED-0482.md"],
    "t0499": [
        "tickets/0499-sign-bits-as-the-chain-identifier-a-hash.erg",
        "tickets/closed/0499-sign-bits-as-the-chain-identifier-a-hash.erg",
    ],
    "t0266": [
        "tickets/0266-cross-lingual-probe-on-the-multilingual.erg",
        "tickets/closed/0266-cross-lingual-probe-on-the-multilingual.erg",
    ],
    "t0265": [
        "tickets/0265-recall-at-the-deployed-dtype-and-the-fus.erg",
        "tickets/closed/0265-recall-at-the-deployed-dtype-and-the-fus.erg",
    ],
    "t0091": [
        "tickets/0091-library-derived-droplist-plus-degeneracy.erg",
        "tickets/closed/0091-library-derived-droplist-plus-degeneracy.erg",
    ],
    # The upstream PR body, drafted here and sent as-is. Every figure it carries is one
    # the maintainer will read, which makes it the LAST place a stale number may sit —
    # and the one document in this repo whose readers are outside it.
    "u0091": ["verification/UPSTREAM-PR-0091-DROPLIST.md"],
    # Same contract, for the series' first PR — the degenerate query.
    "u0091a": ["verification/UPSTREAM-PR-0091-DEGENERATE.md"],
    # And for the second — keep diacritics, the two measured designs.
    "u0091d": ["verification/UPSTREAM-PR-0091-DIACRITICS.md"],
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


#: Coverage floor established at 349 pairs by ticket 0420 on 2026-08-30, after
#: the GPU-correction and embedder-recommendation declarations landed. It moves
#: only with an explicit explanation of removed coverage. New declarations pass
#: without changing it: this is a one-way floor, not an equality check.
#:
#: LOWERED to 318 on 2026-08-31, and here is the removed coverage, as the ratchet
#: requires. STATE.md was cut to a pointer page under forty lines by author ruling
#: the same day: its measurement record described a tree three upstream versions
#: stale, and git log is this repo's archive. Thirty-seven declarations named it.
#: Thirty-one of those quoted a figure that ALSO lives in the ticket that produced
#: it, so they lost one prose site and kept their anchor — no coverage is gone
#: there, only a duplicate slot. Six had STATE.md as their only prose home and are
#: deleted outright: 0005's migration ratio, 0009's codepoints_agreeing, and
#: 0013's three concentration figures. Their artifacts stay under bench/results/
#: and their tickets stay authoritative for the evidence; what ends is a prose
#: quote that no document makes any more, and a figure nobody quotes cannot drift.
#: One was re-anchored rather than dropped — 0009's codepoints_swept, which R19
#: quotes live ("over 1 301 codepoints") and which was, until this edit, guarded
#: only through STATE.md. That one is a coverage GAIN hiding inside the shrink.
#:
#: RE-TIGHTENED to 346 on the same day, at the merge with main. The STATE.md cut
#: lowered this to 318 on a tree of 318 pairs; main meanwhile carried 349 and
#: added the 0499 projection declarations. Git took the lower number, which is
#: the safe direction for a merge and the wrong one for a ratchet: it would have
#: left main's deliberately-ratcheted coverage with 28 pairs of slack, and this
#: floor exists precisely because coverage can fall without anything failing.
#: 346 is the merged tree's actual count, so the floor is tight again.
#:
#: RAISED to 377 on 2026-08-31 by ticket 0091: seventeen declarations for the droplist
#: measurement in the ticket, two more re-declaring the figures it borrows from the X2
#: verdict and the threshold sweep to place its own, and twelve for the upstream PR body,
#: which is the first document here written to be read outside the repo and therefore the
#: one where a stale figure costs most. No coverage was removed.
#:
#: RAISED again to 381 in review round 1, for arm D — X2's own binary re-run on the same
#: file to isolate why the unpruned arm reads under X2's figure — and for arm C's pooled
#: pair where its second run is recorded. Both are provenance rather than results, which is
#: exactly the kind of figure that rots unnoticed.
#:
#: And to 392 for the snippet probe, the one criterion `bench/query.py` structurally cannot
#: measure: it records item keys and scores and never the snippet text, so that claim had
#: rested on a unit fixture. Its four figures are each declared in both prose homes, worded
#: apart so neither copy can mask the other.
MINIMUM_PAIRS = 392

#: A figure is (artifact, key path, places, {prose key: anchor-or-None}), optionally with
#: "pct" when the prose writes the fraction as a percentage. An anchor is a snippet with
#: `{}` marking the slot; None falls back to the weaker presence check. A figure may
#: legitimately live in several documents; it must be current in every one that claims it.
FIGURES = [
    # ---- 0008, the real-vector measurement. The latency table is anchored: every stale
    # figure on this branch was a table cell whose value also appeared elsewhere.
    ("0008-real-vectors/real-93022.json", "corpus.vectors", 0,
     {"t0008": "{} passages of the real library"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.exact_k30.median_ms", 1,
     {"t0008": "Exact float32 scan at k=30: **{} ms**"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.two_stage_pool_4x.median_ms", 1,
     {"t0008": "| 0,918 | {} ms |"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.two_stage_pool_8x.median_ms", 1,
     {"t0008": "| 0,969 | {} ms |"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.two_stage_pool_16x.median_ms", 1,
     {"t0008": "| 0,991 | {} ms |"}),
    ("0008-real-vectors/real-93022.json", "anisotropy.corpus_mean_norm", 3,
     {"t0008": "mean norm {}, and"}),
    ("0008-real-vectors/real-93022.json", "anisotropy.most_one_sided_LIVE_dimension.one_sided", 3,
     {"t0008": "tops out at **{}**"}),
    ("0008-real-vectors/real-93022.json", "on_disk.float32_bytes_per_vector", 1,
     {"t0008": "**{} B per float32"}),
    ("0008-real-vectors/real-93022.json", "on_disk.binary_bytes_per_vector", 1,
     {"t0008": "against {} B per binary"}),
    ("0008-real-vectors/real-93022.json", "probe_design.exact_topk_from_the_probe_own_item", 1,
     {"t0008": "**{}% of a probe's exact top-30"}, "pct"),
    ("0008-real-vectors/build.json", "elapsed_s", 1, {"t0008": "**{} s wall clock**"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.speedup_vs_exact_per_run.two_stage_pool_4x", 2,
     {"t0008": "git history: {}\nat the 4x pool"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.speedup_vs_exact_per_run.two_stage_pool_8x", 2,
     {"t0008": "at the 4x pool, {} at 8x"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.speedup_vs_exact_per_run.two_stage_pool_16x", 2,
     {"t0008": "at 8x, {} at 16x"}),
    # The headline recall column — the most-quoted numbers in the ticket, and unreachable
    # until dig() learned to walk lists. Anchored on the table rows they live in.
    ("0008-real-vectors/real-93022.json", "recall.2.recall_threshold_zero", 3,
     {"t0008": "| 0,628 | **{}**"}),
    ("0008-real-vectors/real-93022.json", "recall.2.recall_mean_centred", 3,
     {"t0008": "**0,884** | {} |"}),
    ("0008-real-vectors/real-93022.json", "recall.3.recall_threshold_zero", 3,
     {"t0008": "| 0,862 | **{}**"}),
    ("0008-real-vectors/real-93022.json", "recall.3.recall_mean_centred", 3,
     {"t0008": "**0,953** | {} |"}),
    ("0008-real-vectors/real-93022.json", "recall.4.recall_threshold_zero", 3,
     {"t0008": "| 0,998 | {} |"}),
    # The figure whose staleness bounced this branch twice. Declaring it is the point.
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.iqr_pct_range_all_candidates", 1,
     {"t0008": "the spreads fell to **{}%**"}),
    ("0008-real-vectors/real-93022.json", "latency_run_agreement.iqr_pct_range_two_stage", 1,
     {"t0008": "**{}%** across the three two-stage rows"}),
    ("0008-real-vectors/real-93022.json", "coarse_pool_fidelity.recall_via_vec0_pool.2.via_vec0_pool", 4,
     {"t0008": "(0,8840 against {} at 4x"}),
    ("0008-real-vectors/real-93022.json", "latency_ms.binary_first_pass_k240.median_ms", 1,
     {"t0008": "At 8x it is {} ms of the"}),
    # ---- 0001, the like-for-like comparison ----
    # SYNC.md's §5 slots were removed 2026-08-30 with the I-2 withdrawal
    # (DECISIONS.md): the §5 prose that quoted these figures is gone.
    ("0001-old-vs-new/SUMMARY.json", "corpus.passages", 0,
     {"t0001": None, "readme": "one corpus of {} passages"}),
    ("0001-old-vs-new/SUMMARY.json", "startup_s.json", 2,
     {"t0001": "| startup to first answer | {} s |",
      "readme": "**{} s\nagainst"}),
    ("0001-old-vs-new/SUMMARY.json", "startup_s.sqlite", 2,
     {"t0001": None, "readme": None}),
    ("0001-old-vs-new/SUMMARY.json", "resident_mib.json_after_16_queries", 1,
     {"t0001": "| resident after 16 queries | {} MiB |",
      "readme": "**{} MiB against"}),
    ("0001-old-vs-new/SUMMARY.json", "resident_mib.sqlite_after_16_queries", 1,
     {"t0001": None, "readme": None}),
    ("0001-old-vs-new/SUMMARY.json", "memory_caveat.conservative_ratio", 1,
     {"readme": "win is {}x rather"}),
    ("0001-old-vs-new/uncapped_stock_node.json", "status.documents", 0, {"t0001": None}),
    # ---- 0005, the migration ----
    # ---- 0009, the fold sweep ----
    ("0009-fold-sweep/codepoints.json", "codepoints_swept", 0,
     {"requirements": "over {} codepoints"}),
    # ---- 0012, the two version sequences ----
    # SPEC.md's C1 quotes three of this artifact's scalars in one sentence — "measured:
    # 410 versus 0..25 036" — plus the entries-total in the since=0 scoping bullet. Anchored,
    # not presence-only: "0" and "25 036" both recur as bare small numbers elsewhere in the
    # document, so a bare containment check would stay green with either one stale.
    ("0012-fulltext-sequence/sequences.json", "library_version_from_items_header", 0,
     {"constraints": "measured: {} versus"}),
    ("0012-fulltext-sequence/sequences.json", "fulltext_version_min", 0,
     {"constraints": "versus {}.."}),
    ("0012-fulltext-sequence/sequences.json", "fulltext_version_max", 0,
     {"constraints": "0..{})."}),
    ("0012-fulltext-sequence/sequences.json", "fulltext_entries_total", 0,
     {"design": None, "constraints": "584 of {} fulltext"}),
    ("0012-fulltext-sequence/sequences.json",
     "fraction_of_library_reported_new_at_library_version", 1,
     {"design": None, "requirements": None}, "pct"),
    # ---- 0011, the uncapped-build RSS — quoted by the redesign's gate and experiments ----
    ("0011-rss/capped-vs-uncapped.json", "baseline_uncapped_chars.peak_MiB", 1,
     {"design": None, "t0025": None, "t0026": None}),
    # ---- 0140, the embedder window census. The 500 ceiling is worth its irregularity
    # only while it sits below every candidate's window, so the tightest window is the
    # figure the whole ruling rests on. Anchored rather than presence-only: 512 is also
    # the embedder limit quoted elsewhere in this section, which is exactly the
    # duplicate-value case a bare presence check cannot see.
    ("0140-model-windows/candidate-windows.json", "min_window", 0,
     {"design": "window is {} tokens, so the minimum never binds"}),
    # ---- 0140, the passage census. §5.2.9's count is a measurement, and these anchors
    # are what make a re-measurement propagate: re-run the census, and every quoted
    # figure below goes stale together instead of drifting one by one.
    ("0140-passage-census/census.json", "summary.passages_total", 0,
     {"design": "derived**: {} passages at the"}),
    ("0140-passage-census/census.json", "summary.files", 0,
     {"design": "counted over all {} fulltext caches"}),
    ("0140-passage-census/census.json", "summary.tokens_total", 0,
     {"design": "({} tokens through the"}),
    ("0140-passage-census/census.json", "summary.median_passages_per_attachment", 0,
     {"design": "attachment measures {} passages"}),
    ("0140-passage-census/census.json", "summary.by_kind.pdf.median_passages_per_attachment", 0,
     {"design": "{} for PDFs"}),
    ("0140-passage-census/census.json", "summary.by_kind.html.median_passages_per_attachment", 0,
     {"design": "{} for HTML snapshots"}),
    ("0140-passage-census/census.json", "geometry.budget", 0,
     {"design": "resolved budget of {} tokens"}),
    # ---- 0013, concentration ----
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
    # ---- 0025 X1 recall half (REAL vectors, 93 022 passages, doudou) ----
    # The timing half above was declared from the start; the recall half was not, and the
    # asymmetry was the finding: `make check` stayed green because the guard validates only
    # what someone declared, so an undeclared figure drifts in silence. Same experiment,
    # same treatment now.
    ("0025-x1-recall/qwen3-06b-1024.json",
     "per_width.0.binary_recall.threshold_zero.rerank_full_width.3.recall", 4,
     {"t0025": "full width reads {} recall@30",
      "decisions": "**{}** at the 8x pool, full width"}),
    ("0025-x1-recall/nomic-v15-768.json",
     "per_width.0.binary_recall.threshold_zero.rerank_full_width.3.recall", 4,
     {"t0025": "nomic-768 reads {} at 8x",
      "decisions": "nomic-768 scores **{} — below"}),
    ("0025-x1-recall/nomic-v15-768.json",
     "per_width.0.binary_recall.threshold_zero.rerank_full_width.4.recall", 4,
     {"t0025": "clearing only at 16x ({})",
      "decisions": "clears at 16x ({}), still inside"}),
    # Both rerank targets, because the conclusion IS the gap between them: a re-measurement
    # that moved only one would leave the other figure true and the finding false.
    ("0025-x1-recall/qwen3-06b-1024.json",
     "per_width.1.binary_recall.threshold_zero.rerank_full_width.3.recall", 4,
     {"t0025": "reranking narrow scores 0,8603 against {} full"}),
    ("0025-x1-recall/qwen3-06b-1024.json",
     "per_width.1.binary_recall.threshold_zero.rerank_at_width.3.recall", 4,
     {"t0025": "reranking narrow scores {} against"}),
    # The scan shapes. Declared at the run the artifact holds; the ticket log records the
    # three-invocation spread these sit inside, and why the upstream comment quotes the
    # most conservative of them rather than this one.
    ("0025-x1-recall/scan-shapes-255703x3072.json", "results.0.median_ms", 1,
     {"t0025": "4 196,2 / {} ms and binary_3072",
      "decisions": "scan's {} ms. Both figures"}),
    ("0025-x1-recall/scan-shapes-255703x3072.json", "results.2.median_ms", 1,
     {"t0025": "97,2 / 94,1 / {} ms",
      "decisions": "the binary scan is **{} ms** against"}),
    ("0025-x1-recall/scan-shapes-255703x3072.json", "results.4.bytes_scanned", 0,
     {"t0025": "it now reads {}, equal to binary_3072"}),
    # Which shape scan-shapes' baseline actually measures. All three declared, because the
    # finding IS the ratio between them: a re-measurement that moved only one would leave the
    # others true and the conclusion false. The mislabelled baseline is what put "more than
    # twenty" into a public comment where the honest figure is about ten.
    ("0025-x1-recall/scan-shape-attribution.json", "results.0.us_per_row", 3,
     {"v30": "what v1.9.0 ran | {} |"}),
    ("0025-x1-recall/scan-shape-attribution.json", "results.1.us_per_row", 3,
     {"v30": "isolates the polymorphism | {} |"}),
    ("0025-x1-recall/scan-shape-attribution.json", "results.2.us_per_row", 3,
     {"v30": "what #31 shipped | {} |"}),
    ("0025-x1-recall/scan-shape-attribution.json", "results.1.speedup_vs_v190", 2,
     {"v30": "Of the 2,29x, {}x is the polymorphic call site"}),
    ("0025-x1-recall/scan-shape-attribution.json", "results.2.speedup_vs_v190", 2,
     {"v30": "| **{}x** |"}),
    # v1.9.0 against v1.10.0 on a real 93k index. All three arms declared plus the
    # decomposition, because the finding is the split: the total says the release works,
    # the split says which of the two merged changes did it. A re-measurement that moved
    # only the total would leave the attribution true and wrong.
    ("0025-upstream-v190-vs-v1100/v190-vs-v1100-semantic-latency-93022x384.json",
     "results.semantic_mode.arms.v1\\.9\\.0.warm.p50_ms", 1,
     {"v30": "| v1.9.0 `bb414df` | {} ms |"}),
    ("0025-upstream-v190-vs-v1100/v190-vs-v1100-semantic-latency-93022x384.json",
     "results.semantic_mode.arms.v1\\.10\\.0-exact.warm.p50_ms", 1,
     {"v30": "`ZOTEUS_INDEX_ANN=false` | {} ms |"}),
    ("0025-upstream-v190-vs-v1100/v190-vs-v1100-semantic-latency-93022x384.json",
     "results.semantic_mode.arms.v1\\.10\\.0-default.warm.p50_ms", 1,
     {"v30": "| v1.10.0 stock | **{} ms** |"}),
    # ---- 0025 X2, stopword-less OR p95 (REAL 477k index + stock control arm, doudou) ----
    # Both arms are declared, because the verdict is a comparison: a re-measurement that moved
    # only the control would leave the treatment figure true and the conclusion false.
    ("0025-x2-stopwordless/x2-verdict.json", "warm_p95_ms.stopword_less", 1,
     {"t0025": "Warm p95 stopword-less = {} ms against the ~500 ms rule",
      "t0014": "Warm p95 stopword-less = {} ms at 477 512 passages"}),
    ("0025-x2-stopwordless/x2-verdict.json", "warm_p95_ms.stock_with_stoplist", 1,
     {"t0025": "answers them at a warm p95 of {} ms, inside the allowance",
      "t0014": "same index and queries answers at {} ms"}),
    ("0025-x2-stopwordless/x2-verdict.json", "ratio_p95", 1,
     {"t0025": "the deletion multiplies p95 by {} and", "t0014": "({}x on p95"}),
    ("0025-x2-stopwordless/x2-verdict.json", "ratio_p50", 1,
     {"t0025": "the median by {} (1 233,2 vs 215,7 ms)", "t0014": "{}x on the median)"}),
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
    # threshold SPEC.md §5.3 names and does not reach the budget at, and the working policy's
    # cost and fidelity. Every anchor head here ends in a non-digit on purpose — `p50 ` and
    # `p95 ` would be glued to the value by despace(), per the note above.
    ("0025-x2-stopwordless/df-droplist-sweep.json", "threshold_sweep.df_ge_50pct.p95_ms", 1,
     {"t0025": "terms drop and p95 stays at {} ms",
      "design": "terms drop and p95 remains {} ms"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json", "threshold_sweep.df_ge_50pct.terms_dropped", 0,
     {"design": "only {} terms drop and p95"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json", "threshold_sweep.df_ge_30pct.p95_ms", 1,
     {"design": "alone reaches {} ms p95"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json", "recommended_policy.p50_ms", 1,
     {"t0025": "fallback): p50{} ms", "t0014": "gives p50{} ms"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json", "recommended_policy.p95_ms", 1,
     {"t0025": "p95{} ms, 98% top-30 overlap", "t0014": "and p95{} ms with 98%"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json",
     "recommended_policy.mean_top30_overlap_with_unfiltered", 0,
     {"t0025": "ms, {}% top-30 overlap with the unfiltered",
      "t0014": "with {}% of the unfiltered"}, "pct"),
    # ---- 0091, the droplist implemented and measured end to end (REAL 477k index) ----
    # Three arms against ONE file, so all six latency figures move together or not at all;
    # every one is declared, because the claim is a comparison and a re-measurement that
    # moved only one arm would leave every figure true and the conclusion false. Anchor
    # heads that end in `p50`/`p95` carry no space before the slot: `p95` ends in a digit,
    # so despace() glues the separator that follows it (see the note above zotero-native).
    ("0091-droplist/query-477k.json", "arms.A_stock_v1_12_0.latency.p50_ms", 1,
     {"t0091": "answers the twenty queries at p50{} ms and"}),
    ("0091-droplist/query-477k.json", "arms.A_stock_v1_12_0.latency.p95_ms", 1,
     {"t0091": "and p95{} ms, which lands"}),
    ("0091-droplist/query-477k.json", "arms.C_no_stoplist_no_droplist.latency.p50_ms", 1,
     {"t0091": "costs p50{} ms and"}),
    ("0091-droplist/query-477k.json", "arms.C_no_stoplist_no_droplist.latency.p95_ms", 1,
     {"t0091": "and p95{} ms: X2's failure mode"}),
    ("0091-droplist/query-477k.json", "arms.B_droplist_plus_fallback.latency.p50_ms", 1,
     {"t0091": "brings it to p50{} ms and"}),
    # Quoted three times in the ticket — the measurement entry, the findings entry, and the
    # verification block — and each slot is declared. Two of the three copies exist because
    # the figure is the one the exit criterion turns on, which is exactly the shape of the
    # duplicate-goes-stale defect this file was written against.
    ("0091-droplist/query-477k.json", "arms.B_droplist_plus_fallback.latency.p95_ms", 1,
     {"t0091": "and p95{} ms. The tail"}),
    ("0091-droplist/query-477k.json", "arms.B_droplist_plus_fallback.latency.p95_ms", 1,
     {"t0091": "can move the {} ms figure"}),
    ("0091-droplist/query-477k.json", "arms.B_droplist_plus_fallback.latency.p95_ms", 1,
     {"t0091": "allowance; {} ms over all twenty"}),
    ("0091-droplist/query-477k.json",
     "arms.B_droplist_plus_fallback.latency_excluding_the_degenerate_query.p95_ms", 1,
     {"t0091": "reads p95{} ms, inside"}),
    ("0091-droplist/query-477k.json",
     "arms.B_droplist_plus_fallback.latency_excluding_the_degenerate_query.p95_ms", 1,
     {"t0091": "is split: {} ms over the nineteen"}),
    ("0091-droplist/query-477k.json", "result_quality.mean_jaccard_vs_stock_droplist", 3,
     {"t0091": "mean Jaccard against stock {}, no query"}),
    ("0091-droplist/query-477k.json", "derivation.droplist_terms", 0,
     {"t0091": "reproduces the sweep's {} terms over"}),
    ("0091-droplist/query-477k.json", "derivation.vocabulary_terms", 0,
     {"t0091": "terms over {} vocabulary terms"}),
    ("0091-droplist/query-477k.json", "derivation.scan_ms.first_call", 0,
     {"t0091": "it costs {} ms on first call"}),
    ("0091-droplist/query-477k.json", "derivation.scan_ms.second_call", 0,
     {"t0091": "call and {} ms on the second"}),
    # ---- The snippet criterion, the one figure bench/query.py structurally cannot
    # produce: that driver records item keys and scores and never the snippet text, so
    # until this probe ran the claim rested on a unit fixture. Declared in three places
    # each, because the pair is a comparison and one half going stale would leave the
    # sentence true and the conclusion false.
    # The ticket carries the pair twice — once in the log, once in the verification block —
    # and the two are worded apart on purpose, so each anchor has a head of its own. With
    # identical wording the two slots collapse into one `finditer` result and a stale copy
    # is masked by its correct twin, which is the exact recurrence this file exists against.
    ("0091-droplist/snippets-477k.json", "comparable_pairs", 0,
     {"t0091": "Of {} hits both arms return",
      "u0091": "of {} hits both arms return"}),
    ("0091-droplist/snippets-477k.json", "comparable_pairs", 0,
     {"t0091": "of {} hits both arms return, 82 open"}),
    ("0091-droplist/snippets-477k.json", "snippets_starting_at_the_passage_opening.unpruned", 0,
     {"t0091": "return, {} begin at the passage opening unpruned",
      "u0091": "return, **{}** begin at the"}),
    ("0091-droplist/snippets-477k.json", "snippets_starting_at_the_passage_opening.unpruned", 0,
     {"t0091": "return, {} open at"}),
    ("0091-droplist/snippets-477k.json", "snippets_starting_at_the_passage_opening.pruned", 0,
     {"t0091": "opening unpruned and {} do pruned",
      "u0091": "unpruned and **{}** do so pruned"}),
    ("0091-droplist/snippets-477k.json", "snippets_starting_at_the_passage_opening.pruned", 0,
     {"t0091": "character unpruned and {} do so pruned"}),
    ("0091-droplist/snippets-477k.json", "moved_off_the_opening_by_pruning", 0,
     {"t0091": "so {} moved onto the match",
      "u0091": "so **{}** moved onto the match"}),
    # Arm D exists only to answer a question the review asked: why the unpruned arm reads
    # well under X2's 1 773,0 ms when the stock control reproduces X2 to 0,05 %. It is X2's
    # OWN binary on this file, so its two figures are the isolation, and a stale one would
    # turn a ruled-out cause back into an open one.
    ("0091-droplist/query-477k.json", "arms.D_x2_own_binary.latency.p50_ms", 1,
     {"t0091": "reading p50{} ms and"}),
    ("0091-droplist/query-477k.json", "arms.D_x2_own_binary.latency.p95_ms", 1,
     {"t0091": "and p95{} ms. Statistically"}),
    # Arm C's pooled pair, quoted a second time where its second run is recorded.
    ("0091-droplist/query-477k.json", "arms.C_no_stoplist_no_droplist.latency.p50_ms", 1,
     {"t0091": "(pooled p50{} ms, p95"}),
    ("0091-droplist/query-477k.json", "arms.C_no_stoplist_no_droplist.latency.p95_ms", 1,
     {"t0091": "965,6 ms, p95{} ms) since"}),
    # The two figures the ticket quotes from OTHER artifacts to place its own. The stock
    # control is what says the machine and the harness still agree with August; the sweep's
    # prediction is what says the implementation lands where the design said it would.
    ("0025-x2-stopwordless/x2-verdict.json", "warm_p95_ms.stock_with_stoplist", 1,
     {"t0091": "lands on the {} ms the X2"}),
    ("0025-x2-stopwordless/df-droplist-sweep.json", "threshold_sweep.df_ge_30pct.p95_ms", 1,
     {"t0091": "near the {} ms the sweep predicted"}),
    # ---- The same measurement as the upstream PR body carries it. Rounded to whole
    # milliseconds, deliberately: that document is written for a reader outside this repo,
    # where a decimal comma reads as a typo, and an integer has no decimal mark to disagree
    # about. The THOUSANDS mark still does — the document writes `1 012 ms` beside its
    # `477 512` and `639 888`, consistently with itself, and despace() is what lets the
    # anchor match either way. So `places=0` sidesteps the decimal question and nothing
    # else; the spaced form in the anchors is not decoration.
    #
    # The p95 anchors embed their row's p50 because a markdown table gives them no other
    # left-hand boundary — a one-way coupling, so a p50 edit fails its neighbour too, which
    # is the safe direction.
    # ---- u0091a, the outgoing body for the series' first PR. Its two figures are the
    # library size and the still-free degenerate short queries; the rest of that body is
    # deliberately figure-light because the contract is "everything else unchanged".
    ("0091-droplist/degenerate-recut-477k.json", "passages", 0,
     {"u0091a": "a real {}-passage library"}),
    ("0091-droplist/degenerate-recut-477k.json", "probes.12.ms", 0,
     {"u0091a": "still cost {} ms and return nothing"}),
    # ---- u0091d, the outgoing body for the series' second PR: the decision table's
    # load-bearing figures — the two designs' penalties, migrations and agreement rows.
    ("0091-droplist/expansion-penalties.json", "arms.1.length_penalty.penalty_pct", 1,
     {"u0091d": "controlled pair) | **{} %**"}),
    ("0091-droplist/expansion-penalties.json", "arms.2.length_penalty.penalty_pct", 0,
     {"u0091d": "{} % (= stock control)"}),
    ("0091-droplist/expansion-migration.json", "runs.0.open_s", 1,
     {"u0091d": "477 512 passages | {} s |"}),
    ("0091-droplist/expansion-migration.json", "runs.1.open_s", 1,
     {"u0091d": "477 512 passages | 116,4 s | **{} s**"}),
    ("0091-droplist/arms-expansion-en.json", "summary.armA.top1_same_as_reference", 0,
     {"u0091d": "(20 queries each) | {} / 16 / 14 / 19"}),
    ("0091-droplist/arms-expansion-en.json", "summary.armB.top1_same_as_reference", 0,
     {"u0091d": "19 / 16 / 14 / 19 | {} / 17 / 12 / 20"}),
    ("0091-droplist/arms-expansion-en.json", "summary.armA.mean_rbo_to_reference", 3,
     {"u0091d": "short | {} / 0,886 / 0,692 / 0,977"}),
    ("0091-droplist/arms-expansion-en.json", "summary.armB.mean_rbo_to_reference", 3,
     {"u0091d": "0,977 | {} / 0,902 / 0,675 / 0,992"}),
    ("0091-droplist/arms-expansion-ungated-en.json", "summary.armB.top1_same_as_reference", 0,
     {"u0091d": "agreement fell to {}/12/10/10 of 20"}),
    ("0091-droplist/expansion-penalties.json", "arms.1.aboutness.scores.ABOUT", 2,
     {"u0091d": "ranked **last** ({} vs 1,59)"}),
    ("0091-droplist/expansion-penalties.json", "arms.2.aboutness.scores.ABOUT", 2,
     {"u0091d": "ranked first ({} vs 2,86)"}),
    ("0091-droplist/expansion-migration.json", "runs.1.accent_variants_rows_at_first_derivation", 0,
     {"u0091d": "map, {} variant pairs at first derivation"}),
    # The one figure in the body that comes from outside the 0091 artifacts: the
    # document frequency of `energy`, measured under X2 (2026-08-25) and quoted as the
    # motivating example. It was unanchored until 2026-09-01 — a number the maintainer
    # reads, traceable to no declaration, which is exactly the shape this guard exists
    # for. Its source is X2's mechanism probe, and `pct` because the body writes the
    # fraction as a percentage.
    ("0025-x2-stopwordless/x2-mechanism.json", "most_frequent.energy.share_of_passages", 1,
     {"u0091": "`energy` appears in {}% of its passages"}, "pct"),
    ("0091-droplist/query-477k.json", "arms.A_stock_v1_12_0.latency.p50_ms", 0,
     {"u0091": "29-word list | {} ms |"}),
    ("0091-droplist/query-477k.json", "arms.A_stock_v1_12_0.latency.p95_ms", 0,
     {"u0091": "29-word list | 222 ms | {} ms |"}),
    ("0091-droplist/query-477k.json", "arms.C_no_stoplist_no_droplist.latency.p50_ms", 0,
     {"u0091": "nothing pruned | {} ms |"}),
    ("0091-droplist/query-477k.json", "arms.C_no_stoplist_no_droplist.latency.p95_ms", 0,
     {"u0091": "nothing pruned | 966 ms | {} ms |"}),
    ("0091-droplist/query-477k.json", "arms.B_droplist_plus_fallback.latency.p50_ms", 0,
     {"u0091": "degeneracy fallback | {} ms |"}),
    ("0091-droplist/query-477k.json", "arms.B_droplist_plus_fallback.latency.p95_ms", 0,
     {"u0091": "degeneracy fallback | 282 ms | {} ms |"}),
    # Round 5 dropped the 492 ms excluding-the-degenerate paragraph and the Jaccard 87%
    # line from u0091: both described the superseded <2-survivor fallback measurement,
    # replaced by the full-stack table anchored below.
    ("0091-droplist/derivation-477k.json", "passages", 0,
     {"u0091": "On a {}-passage library"}),
    ("0091-droplist/derivation-477k.json", "vocabulary_terms", 0,
     {"u0091": "scan reads {} terms and"}),
    ("0091-droplist/derivation-477k.json", "scan_ms.first_call", 0,
     {"u0091": "about {} ms on a first call"}),
    ("0091-droplist/derivation-477k.json", "scan_ms.second_call", 0,
     {"u0091": "call and {} ms on a"}),
    ("0091-droplist/derivation-477k.json", "droplist_terms", 0,
     {"u0091": "small — {} terms, 75 bytes"}),
    ("0091-droplist/derivation-477k.json", "droplist_bytes", 0,
     {"u0091": "terms, {} bytes of text"}),
    # ---- u0091, the full-stack re-measurement (round 5, stacked on pr2-expansion):
    # stock vs the whole series, four query sets, from arms-stack-*.json. Latency is
    # cross-file by necessity (stock cannot read schema 2) and the artifact says so.
    ("0091-droplist/arms-stack-en.json", "summary.stock.p50_ms", 0,
     {"u0091": "stoplist-heavy) | {} / 264 ms"}),
    ("0091-droplist/arms-stack-en.json", "summary.stock.p95_ms", 0,
     {"u0091": "stoplist-heavy) | 143 / {} ms"}),
    ("0091-droplist/arms-stack-en.json", "summary.stack.p50_ms", 0,
     {"u0091": "264 ms | {} / 341 ms"}),
    ("0091-droplist/arms-stack-en.json", "summary.stack.p95_ms", 0,
     {"u0091": "264 ms | 187 / {} ms"}),
    ("0091-droplist/arms-stack-en.json", "summary.stack.mean_rbo_to_reference", 3,
     {"u0091": "341 ms | {} | 20 of 20"}),
    ("0091-droplist/arms-stack-en.json", "summary.stack.top1_same_as_reference", 0,
     {"u0091": "| 0,916 | {} of 20"}),
    ("0091-droplist/arms-stack-fr.json", "summary.stock.p50_ms", 0,
     {"u0091": "| FR | {} / 275 ms"}),
    ("0091-droplist/arms-stack-fr.json", "summary.stock.p95_ms", 0,
     {"u0091": "| FR | 116 / {} ms"}),
    ("0091-droplist/arms-stack-fr.json", "summary.stack.p50_ms", 0,
     {"u0091": "275 ms | {} / 269 ms"}),
    ("0091-droplist/arms-stack-fr.json", "summary.stack.p95_ms", 0,
     {"u0091": "275 ms | 112 / {} ms"}),
    ("0091-droplist/arms-stack-fr.json", "summary.stack.mean_rbo_to_reference", 3,
     {"u0091": "269 ms | {} | 16 of 20"}),
    ("0091-droplist/arms-stack-fr.json", "summary.stack.top1_same_as_reference", 0,
     {"u0091": "| 0,886 | {} of 20"}),
    ("0091-droplist/arms-stack-vi.json", "summary.stock.p50_ms", 0,
     {"u0091": "| VI | {} / 228 ms"}),
    ("0091-droplist/arms-stack-vi.json", "summary.stock.p95_ms", 0,
     {"u0091": "| VI | 83 / {} ms"}),
    ("0091-droplist/arms-stack-vi.json", "summary.stack.p50_ms", 0,
     {"u0091": "228 ms | {} / 215 ms"}),
    ("0091-droplist/arms-stack-vi.json", "summary.stack.p95_ms", 0,
     {"u0091": "228 ms | 64 / {} ms"}),
    ("0091-droplist/arms-stack-vi.json", "summary.stack.mean_rbo_to_reference", 3,
     {"u0091": "215 ms | {} | 14 of 20"}),
    ("0091-droplist/arms-stack-vi.json", "summary.stack.top1_same_as_reference", 0,
     {"u0091": "| 0,692 | {} of 20"}),
    ("0091-droplist/arms-stack-short.json", "summary.stock.p50_ms", 0,
     {"u0091": "| short | {} / 161 ms"}),
    ("0091-droplist/arms-stack-short.json", "summary.stock.p95_ms", 0,
     {"u0091": "| short | 53 / {} ms"}),
    ("0091-droplist/arms-stack-short.json", "summary.stack.p50_ms", 0,
     {"u0091": "161 ms | {} / 172 ms"}),
    ("0091-droplist/arms-stack-short.json", "summary.stack.p95_ms", 0,
     {"u0091": "161 ms | 55 / {} ms"}),
    ("0091-droplist/arms-stack-short.json", "summary.stack.mean_rbo_to_reference", 3,
     {"u0091": "172 ms | {} | 18 of 20"}),
    ("0091-droplist/arms-stack-short.json", "summary.stack.top1_same_as_reference", 0,
     {"u0091": "| 0,937 | {} of 20"}),
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
    # ---- 0070, the cosine fusion. Two artifacts because they answer different questions:
    # `shapes` isolates the arithmetic and separates its two causes, `insitu` measures the
    # shipped function over a real scan and is the number the upstream PR quotes.
    ("0070-cosine-fusion/shapes-3072.json", "two_pass_shared_norm.us_per_row", 2,
     {"t0070": "shared `norm()` — upstream today | {} |"}),
    ("0070-cosine-fusion/shapes-3072.json", "two_pass_monomorphic_norm.us_per_row", 2,
     {"t0070": "two-pass, monomorphic `norm()` | {} |"}),
    ("0070-cosine-fusion/shapes-3072.json", "fused.us_per_row", 2,
     {"t0070": "| fused single traversal | {} |"}),
    ("0070-cosine-fusion/shapes-3072.json", "speedup_total", 2,
     {"t0070": "**{}x**, decomposing into"}),
    ("0070-cosine-fusion/shapes-3072.json", "speedup_from_monomorphism", 2,
     {"t0070": "decomposing into **{}x** from the polymorphic"}),
    ("0070-cosine-fusion/shapes-3072.json", "speedup_from_fusion", 2,
     {"t0070": "call site and **{}x**\nfrom the redundant traversal"}),
    ("0070-cosine-fusion/insitu-255703.json", "rows", 0,
     {"t0070": "exact geometry — {} rows, 3072 dims"}),
    ("0070-cosine-fusion/insitu-255703.json", "two_pass.median_ms", 0,
     {"t0070": "| two-pass (before) | {} ms |"}),
    ("0070-cosine-fusion/insitu-255703.json", "two_pass.us_per_row", 2,
     {"t0070": "| two-pass (before) | 8 606 ms | {} |"}),
    ("0070-cosine-fusion/insitu-255703.json", "fused.median_ms", 0,
     {"t0070": "| fused (shipped) | {} ms |"}),
    ("0070-cosine-fusion/insitu-255703.json", "fused.us_per_row", 2,
     {"t0070": "| fused (shipped) | 3 933 ms | {} |"}),
    ("0070-cosine-fusion/insitu-255703.json", "marshalling_floor.median_ms", 0,
     {"t0070": "no arithmetic | {} ms |"}),
    ("0070-cosine-fusion/insitu-255703.json", "marshalling_floor.us_per_row", 2,
     {"t0070": "no arithmetic | 2 559 ms | {} |"}),
    # Anchored so neither carries the other's value: fixing one must not break the other.
    ("0070-cosine-fusion/insitu-255703.json", "speedup_median", 2,
     {"t0070": "**{}x median**"}),
    ("0070-cosine-fusion/insitu-255703.json", "speedup_worst_case", 2,
     {"t0070": "and {}x worst case"}),
    ("0070-cosine-fusion/insitu-255703.json", "equivalence.rows_checked", 0,
     {"t0070": "rather than a fixture: {} rows\nchecked, 0 mismatches"}),
    # ---- The embedder cost campaign, 2026-08-29. These five sit in the ratification
    # ledger's R7/C3 entry, which is where a stale figure is worst: an append-only entry
    # is never edited again, so a wrong number there becomes permanent. The entry also
    # argues FROM them — the ruling that C3 gives way rests on multilingual measuring far
    # over 300 MB — so a drifted figure would leave a ratified ruling standing on a number
    # that no longer exists.
    ("0025-x1-recall/dtype-ladder-multilingual-e5-small.json", "rungs.2.rss_delta_mb", 1,
     {"decisions": "measures {} MB\nresident at uint8"}),
    ("0025-x1-recall/dtype-ladder-nomic.json", "rungs.1.rss_delta_mb", 1,
     {"decisions": "and yet 404,4 MB against {} MB."}),
    # The three repeated figures live in the Granite artifact because that is the run that
    # produced them, one block for all three models. Anchor heads end in a non-digit: a
    # head ending in a digit would be glued to the value by despace().
    ("0025-x1-recall/dtype-ladder-granite-97m-multilingual.json",
     "repeated_measurement.nomic_v1_5_mb.median", 1,
     {"decisions": "under 7 MB: nomic-768{} MB"}),
    ("0025-x1-recall/dtype-ladder-granite-97m-multilingual.json",
     "repeated_measurement.granite_97m_mb.median", 1,
     {"decisions": "{} MB, multilingual-e5-small"}),
    ("0025-x1-recall/dtype-ladder-granite-97m-multilingual.json",
     "repeated_measurement.multilingual_e5_small_mb.median", 1,
     {"decisions": "multilingual-e5-small {} MB. Granite and e5"}),

    # ---- 0220, the device/dtype probe. The cosine column is anchored per row because the
    # report's whole argument is which rows are EQUAL: three variants share the value
    # 0,9999996 and one does not, so a bare presence check would stay green with any of
    # them wrong. Six places for the quantised row, seven for the normalisation floor —
    # the floor's last digit is what says "bit-identical" rather than "close".
    ("0220-device-dtype/summary.json", "variants.dtype-q8.cosine_vs_no_options", 6,
     {"v0220": "| dtype-q8 | `{dtype: 'q8'}` | loads | {} |"}),
    ("0220-device-dtype/summary.json", "variants.no-options.cosine_vs_no_options", 7,
     {"v0220": "| no-options | *(none)* | loads | {} |"}),
    ("0220-device-dtype/summary.json", "variants.device-cpu.cosine_vs_no_options", 7,
     {"v0220": "| device-cpu | `{device: 'cpu'}` | loads | {} |"}),
    ("0220-device-dtype/summary.json", "variants.dtype-q7.cosine_vs_no_options", 7,
     {"v0220": "| dtype-q7 | `{dtype: 'q7'}` | loads | {} |"}),

    # The default model's own numbers, anchored per cell. Two runs of this pair exist and
    # only the warm one is reported; anchoring each cell is what stops the discarded cold
    # figures from drifting back into the table, since both sets are plausible there.
    #
    # Each q8 anchor carries the fp32 cell that precedes it in the row, which is the
    # coupling render_value's docstring calls avoidable — deliberately, and it is a
    # different case. There the two figures were the independent ends of a RANGE, so
    # fixing one broke the other for no reason. Here the left cell genuinely is the right
    # cell's position: they are neighbours in one row, measured in one pair, and a
    # re-measurement of fp32 SHOULD force both to be re-read. The failure is loud and
    # names the slot, so it cannot become the silent trap this file exists to refuse.
    ("0220-device-dtype/minilm-fp32.json", "models.0.rss_after_load_mb", 1,
     {"v0220": "| resident after load | {} MB |"}),
    ("0220-device-dtype/minilm-q8.json", "models.0.rss_after_load_mb", 1,
     {"v0220": "| resident after load | 230,6 MB | {} MB |"}),
    ("0220-device-dtype/minilm-fp32.json", "models.0.rss_delta_mb", 1,
     {"v0220": "| resident added by the load | {} MB |"}),
    ("0220-device-dtype/minilm-q8.json", "models.0.rss_delta_mb", 1,
     {"v0220": "| resident added by the load | 143,7 MB | {} MB |"}),
    ("0220-device-dtype/minilm-fp32.json", "models.0.load_ms", 1,
     {"v0220": "| load | {} ms |"}),
    ("0220-device-dtype/minilm-q8.json", "models.0.load_ms", 1,
     {"v0220": "| load | 415,2 ms | {} ms |"}),
    ("0220-device-dtype/minilm-fp32.json", "models.0.query_ms_median", 1,
     {"v0220": "| query median | {} ms |"}),
    ("0220-device-dtype/minilm-q8.json", "models.0.query_ms_median", 1,
     {"v0220": "| query median | 4,2 ms | {} ms |"}),
    # ---- the v1.10.0 smoke test. Its numbers are n=1 session observations rather than a
    # benchmark, which is exactly why they are declared: an indicative figure quoted twice
    # drifts as readily as a measured one, and this report states the live library's size
    # and the warm-latency band that a reader will carry away.
    ("smoke-1.10.0/queries.json", "live_library.total_results", 0,
     {"vsmoke": "returned **{} results** at"}),
    ("smoke-1.10.0/queries.json", "live_library.library_version", 0,
     {"vsmoke": "version **{}** — the live number"}),
    ("smoke-1.10.0/queries.json", "index.passages", 0,
     {"vsmoke": "index it queried holds {} passages** with"}),
    ("smoke-1.10.0/queries.json", "index.items", 0,
     {"vsmoke": "over\n{} items, of which"}),
    ("smoke-1.10.0/queries.json", "index.fulltext_items", 0,
     {"vsmoke": "of which {} carry full text"}),
    ("smoke-1.10.0/queries.json", "index.fulltext_passages", 0,
     {"vsmoke": "contributing {} passages;"}),
    ("smoke-1.10.0/queries.json", "latency_ms.first_semantic_query_includes_model_load", 1,
     {"vsmoke": "| `semantic` | {} ms |"}),
    ("smoke-1.10.0/queries.json", "latency_ms.warm_semantic_min", 1,
     {"vsmoke": "ms | {} ms to"}),
    ("smoke-1.10.0/queries.json", "latency_ms.warm_semantic_max", 1,
     {"vsmoke": "ms to {} ms |\n| `auto`"}),
    ("smoke-1.10.0/queries.json", "latency_ms.auto_min", 1,
     {"vsmoke": "| — | {} ms to"}),
    ("smoke-1.10.0/queries.json", "latency_ms.auto_max", 1,
     {"vsmoke": "ms to {} ms |\n\nThe first figure"}),
    # The RRF table is the report's load-bearing claim: the score is a relabelled rank.
    # Anchored per cell, because the whole finding is that these five values recur
    # unchanged across unrelated queries — a stale cell would destroy exactly that.
    ("smoke-1.10.0/queries.json", "score_semantics.expected_1_over_60_plus_rank.0", 6,
     {"vsmoke": "| observed | {} |"}),
    ("smoke-1.10.0/queries.json", "score_semantics.expected_1_over_60_plus_rank.1", 6,
     {"vsmoke": "| {} | 0,015873"}),
    ("smoke-1.10.0/queries.json", "score_semantics.expected_1_over_60_plus_rank.2", 6,
     {"vsmoke": "0,016129 | {} | 0,015625"}),
    ("smoke-1.10.0/queries.json", "score_semantics.expected_1_over_60_plus_rank.3", 6,
     {"vsmoke": "0,015873 | {} | 0,015385"}),
    ("smoke-1.10.0/queries.json", "score_semantics.expected_1_over_60_plus_rank.4", 6,
     {"vsmoke": "0,015625 | {} |\n| 1/(60+rank)"}),
    # The fresh build from the live library — the half that proves the whole path, and the
    # half this report first got wrong by calling a finished build stalled.
    ("smoke-1.10.0/fresh-build.json", "passages", 0,
     {"vsmoke": "items, **{} passages** and"}),
    ("smoke-1.10.0/fresh-build.json", "fulltext_passages", 0,
     {"vsmoke": "of which {} passages came from"}),
    ("smoke-1.10.0/fresh-build.json", "fulltext_items", 0,
     {"vsmoke": "from the {} items carrying"}),
    ("smoke-1.10.0/fresh-build.json", "query_semantic_ms", 1,
     {"vsmoke": "answered in {} ms and an"}),
    ("smoke-1.10.0/fresh-build.json", "query_auto_ms", 1,
     {"vsmoke": "`auto` query in {} ms."}),
    ("smoke-1.10.0/fresh-build.json", "peak_rss_mib", 0,
     {"vsmoke": "reached **{} MiB** (`VmHWM`)"}),
    # ---- X4's real-corpus arm. Quoted in the ledger, which is append-only: a ratified
    # entry is never edited again, so a wrong number there becomes permanent. The three
    # that carry the argument are the failing rung and the two the domination rests on.
    ("0025-x4-constrained-match/real-477k.json", "rows.1.p95_ms", 1,
     {"decisions": "scope is\n  **{} ms**"}),
    ("0025-x4-constrained-match/real-477k.json", "rows.0.median_ms", 1,
     {"decisions": "unconstrained costs **{} ms** median"}),
    ("0025-x4-constrained-match/real-477k.json", "rows.1.median_ms", 1,
     {"decisions": "thousand rowids costs **{} ms**"}),
    # ---- the year-scope follow-up. The table's two columns are the whole argument: the
    # same work, two mechanisms, and a reader who checks one cell checks the claim.
    ("0025-year-scope/year-vs-json-each.json", "scopes.0.predicate.median_ms", 1,
     {"decisions": "| one year (2020) | **{} ms** median"}),
    ("0025-year-scope/year-vs-json-each.json", "scopes.0.json_each_control.median_ms", 1,
     {"decisions": "median | **{} ms** median |"}),
    ("0025-year-scope/year-vs-json-each.json", "scopes.1.predicate.median_ms", 1,
     {"decisions": "| five years | {} ms median"}),
    ("0025-year-scope/year-vs-json-each.json", "scopes.2.predicate.median_ms", 1,
     {"decisions": "| a decade | {} ms median"}),
    ("0025-year-scope/year-vs-json-each.json", "baseline.0.median_ms", 0,
     {"decisions": "no filter at all costs **{} ms** median"}),
    ("0025-year-scope/year-vs-json-each.json", "column_and_index_build_ms", 0,
     {"decisions": "cost **{} ms**, and Zotero's local API"}),
    # ---- 0263, the CPU arm: cost and fidelity for every candidate at every
    # loadable dtype. SUMMARY.json aggregates the 64 committed cells; every
    # figure below is quoted once, in the campaign's own ticket-log entry.
    ("0263-cpu-arm/SUMMARY.json", "cells_total", 0, {"t0263": "All {} planned cells resolved"}),
    ("0263-cpu-arm/SUMMARY.json", "counts.measured", 0, {"t0263": "resolved: {} measured, 16 unloadable"}),
    ("0263-cpu-arm/SUMMARY.json", "counts.unloadable", 0, {"t0263": "48 measured, {} unloadable, 0 duplicate"}),
    ("0263-cpu-arm/SUMMARY.json", "counts.duplicate", 0, {"t0263": "unloadable, {} duplicate, 0 failed"}),
    ("0263-cpu-arm/SUMMARY.json", "counts.failed", 0, {"t0263": "duplicate, {} failed (`bench/results"}),
    # The fp32-against-itself control -- one representative model; every other
    # model's fp32 cell carries the identical triple by the scorer's own design.
    ("0263-cpu-arm/SUMMARY.json", "rows.0.fidelity.fp32.cos_mean", 1,
     {"t0263": "control: cos_mean {}, overlap_at_30_mean 1,0",
      "t0265": "control: {} for every candidate"}),
    # granite-97m's outlier collapse -- the finding the whole campaign turns on.
    # Ticket 0265 quotes this same pair as the real-world cost of the collapse: its
    # own recall@30 falls from 0,9025 (fp32) to 0,5895 (q8) on exactly this cell.
    ("0263-cpu-arm/SUMMARY.json", "rows.0.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "q8{} (cos_mean 0,743121)",
      "t0266": "overlap@30 of {} there, cos_mean 0,743121",
      "t0265": "overlap_at_30_mean {}); its own uint8"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.0.fidelity.q8.cos_mean", 6,
     {"t0263": "q8 0,2349 (cos_mean {})",
      "t0265": "q8 cos_mean {}, overlap_at_30_mean"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.0.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "against uint8{} (cos_mean 0,948132)"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.0.fidelity.uint8.cos_mean", 6,
     {"t0263": "(cos_mean {}) — a 0,4156 gap"}),
    # q8-versus-uint8 overlap@30, every other candidate and both CONTRAST cells --
    # the "does nomic's ordering generalise" answer, checkable row by row.
    ("0263-cpu-arm/SUMMARY.json", "rows.1.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "`granite-311m-multilingual-r2` q8{} / uint8 0,8334"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.1.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "q8 0,8346 / uint8{} (q8 ahead"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.2.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "`arctic-embed-m-v2` q8{} / uint8 0,8351"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.2.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "q8 0,8338 / uint8{} (uint8 ahead"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.3.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "`gte-multilingual-base` q8{} / uint8 0,7213"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.3.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "q8 0,7227 / uint8{} (q8 ahead)"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.4.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "`multilingual-e5-small` q8{} / uint8 0,8302"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.4.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "q8 0,8664 / uint8{} (q8 ahead"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.5.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "`multilingual-e5-base` q8{} / uint8 0,7336"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.5.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "q8 0,7376 / uint8{} (q8 ahead)"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.6.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "`all-minilm-l6-v2` q8{} / uint8 0,8804"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.6.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "q8 0,9272 / uint8{} and"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.7.q8_vs_uint8.q8_overlap_at_30_mean", 4,
     {"t0263": "`bge-small-en-v15` q8{} / uint8 0,8683"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.7.q8_vs_uint8.uint8_overlap_at_30_mean", 4,
     {"t0263": "q8 0,9137 / uint8{} (both favour q8)"}),
    # RSS medians, five fresh processes -- the campaign's cost table, one anchor
    # per cell, positional against its two table-row neighbours.
    ("0263-cpu-arm/SUMMARY.json", "rows.0.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "| granite-97m-multilingual-r2 | {} | 6,3 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.0.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "6,3 | {} | 7,4 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.0.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "7,4 | {} | 4,8 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.1.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "| granite-311m-multilingual-r2 | {} | 16,1 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.1.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "16,1 | {} | 70,1 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.1.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "70,1 | {} | 91,5 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.2.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "| arctic-embed-m-v2 | {} | 22,1 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.2.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "22,1 | {} | 47,5 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.2.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "47,5 | {} | 55,5 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.3.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "| gte-multilingual-base | {} | 68,4 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.3.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "68,4 | {} | 52,7 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.3.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "52,7 | {} | 20,9 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.4.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "| multilingual-e5-small | {} | 51,0 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.4.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "51,0 | {} | 18,6 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.4.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "18,6 | {} | 51,6 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.5.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "| multilingual-e5-base | {} | 21,6 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.5.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "21,6 | {} | 8,9 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.5.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "8,9 | {} | 51,5 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.6.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "all-minilm-l6-v2 (CONTRAST) | {} | 48,7 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.6.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "48,7 | {} | 24,1 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.6.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "24,1 | {} | 23,6 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.7.cost.fp32.rss_delta_mb_median", 1,
     {"t0263": "bge-small-en-v15 (CONTRAST) | {} | 17,7 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.7.cost.q8.rss_delta_mb_median", 1,
     {"t0263": "17,7 | {} | 19,6 |"}),
    ("0263-cpu-arm/SUMMARY.json", "rows.7.cost.uint8.rss_delta_mb_median", 1,
     {"t0263": "19,6 | {} | 2,3 |"}),
    # ---- 0481, the GPU throughput anomaly's mechanism ----
    ("0481-gpu-anomaly/SUMMARY.json", "step6_r30_throughput.ms_per_passage_fp32_cuda_batch8_600rows", 1,
     {"t0481": "measured **{} ms/passage**"}),
    ("0481-gpu-anomaly/SUMMARY.json", "step6_r30_throughput.projection_minutes_93022_rows", 1,
     {"t0481": "projects to **{} minutes**"}),
    # ---- 0482, the GPU-corrected fidelity/X8/throughput campaign ----
    ("0482-gpu-corrected/x8-cross-provider-fidelity.json", "cleared_count", 0,
     {"v0482": "**{} of 18 clear the bar"}),
    ("0482-gpu-corrected/SUMMARY.json", "counts.measured", 0, {"v0482": None}),
    ("0482-gpu-corrected/SUMMARY.json", "counts.unloadable", 0, {"v0482": None}),
    ("0482-gpu-corrected/throughput/multilingual-e5-small__fp32.json", "ms_per_passage_median", 2,
     {"v0482": None}),
    ("0482-gpu-corrected/throughput/multilingual-e5-small__uint8.json", "ms_per_passage_median", 2,
     {"v0482": None}),
    ("0482-gpu-corrected/throughput/granite-97m-multilingual-r2__fp32.json", "ms_per_passage_median", 2,
     {"v0482": None}),
    ("0482-gpu-corrected/throughput/batch-spotcheck__granite-97m__uint8__b1.json", "ms_per_passage_median", 2,
     {"v0482": None}),
    ("0482-gpu-corrected/throughput/batch-spotcheck__granite-97m__uint8__b128.json", "ms_per_passage_median", 2,
     {"v0482": None}),
    # ---- 0266, the cross-lingual probe. cells is keyed by "<model_id>__<dtype>", not
    # indexed by list position, so a re-run that adds a candidate cannot silently shift
    # which cell an anchor names.
    ("0266-cross-lingual/SUMMARY.json", "cells.multilingual-e5-base__q8.pool_size", 0,
     {"t0266": "Fixed retrieval pool, same across every cell: {} passages, 24 gold"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.multilingual-e5-base__q8.query_count", 0,
     {"t0266": "{} queries: EN + FR + native per non-English topic"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.all-minilm-l6-v2__q8.pair_summary.en->vi.hit_at_10", 2,
     {"t0266": "scores en->vi hit@10 of {} at q8"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.multilingual-e5-base__q8.pair_summary.en->vi.hit_at_10", 2,
     {"t0266": "q8: {}/0,62/0,50/0,88/1,00/1,00"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.multilingual-e5-small__q8.pair_summary.en->vi.hit_at_10", 2,
     {"t0266": "q8: {}/0,25/0,50/0,62/0,75/0,50"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.arctic-embed-m-v2__fp32.pair_summary.en->vi.hit_at_10", 2,
     {"t0266": "fp32/q8/uint8 identically {}/1,00/0,88/0,88/1,00/1,00"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.gte-multilingual-base__q8.pair_summary.en->vi.hit_at_10", 2,
     {"t0266": "q8: {}/0,88/1,00/0,88/1,00/1,00"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.granite-311m-multilingual-r2__q8.pair_summary.en->vi.hit_at_10", 2,
     {"t0266": "q8: {}/0,62/0,75/0,75/1,00/1,00"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.granite-97m-multilingual-r2__q8.pair_summary.en->vi.hit_at_10", 2,
     {"t0266": "q8 COLLAPSES: {}/0,25/0,00/0,00/0,00/0,00"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.granite-97m-multilingual-r2__fp32.negative_control.clean", 0,
     {"t0266": "granite-97m-multilingual-r2 fp32 clean={}/4, q8 clean=0/4"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.granite-97m-multilingual-r2__q8.negative_control.clean", 0,
     {"t0266": "q8 clean={}/4, uint8 clean=3/4"}),
    ("0266-cross-lingual/SUMMARY.json", "cells.granite-97m-multilingual-r2__uint8.negative_control.clean", 0,
     {"t0266": "uint8 clean={}/4;"}),
    # ---- 0265, recall at the deployed dtype and the fused RRF delta. SUMMARY.json
    # aggregates the 18 committed cells (6 candidates x fp32/q8/uint8); every figure
    # below is quoted once, in the campaign's own ticket-log entry.
    ("0265-recall-fusion/SUMMARY.json", "subsample.items_selected", 0,
     {"t0265": "{} items / 1 533"}),
    ("0265-recall-fusion/SUMMARY.json", "subsample.passages_selected", 0,
     {"t0265": "items / {} of the 2 100"}),
    # "recall@30" ends in a digit immediately before the value's own leading digit, so
    # despace() merges the space between them (the "p95 4 198,5" trap this file's own
    # comment already documents) -- the anchor head carries no space here to match.
    ("0265-recall-fusion/SUMMARY.json", "keyword_arm.recall_at_topk", 4,
     {"t0265": "recall@30{}, MRR"}),
    ("0265-recall-fusion/SUMMARY.json", "keyword_arm.mrr", 4,
     {"t0265": "MRR {}, 400 probes"}),
    # granite-97m-multilingual-r2, the one candidate whose quantized rung breaks --
    # fp32, q8 (the break), and uint8 (recovers), row indices 0/1/2 by construction
    # (bench/build_0265_summary.py's MODELS x DTYPES loop order).
    ("0265-recall-fusion/SUMMARY.json", "rows.0.vector_arm.recall_at_topk", 4,
     {"t0265": "(from {} at fp32)"}),
    ("0265-recall-fusion/SUMMARY.json", "rows.1.vector_arm.recall_at_topk", 4,
     {"t0265": "collapses to {} (from"}),
    ("0265-recall-fusion/SUMMARY.json", "rows.2.vector_arm.recall_at_topk", 4,
     {"t0265": "loses far less ({})"}),
    ("0265-recall-fusion/SUMMARY.json", "rows.1.fused_arm.recall_at_topk", 4,
     {"t0265": "fused recall {} beats"}),
    ("0265-recall-fusion/SUMMARY.json", "rows.1.fused_gain_over_keyword", 4,
     {"t0265": "fused_gain_over_keyword {})"}),
    # The fusion-gain analysis block: the 17-cell range and the fraction of the
    # vector-arm's isolated gain that survives fusion -- a derived figure, computed
    # by bench/build_0265_summary.py from the 17 healthy cells, not hand-arithmetic
    # in the prose.
    ("0265-recall-fusion/SUMMARY.json", "fusion_gain_analysis.vector_arm_gain_range", 4,
     {"t0265": "gain over keyword-alone ranges {} and"}),
    ("0265-recall-fusion/SUMMARY.json", "fusion_gain_analysis.fused_gain_range", 4,
     {"t0265": "fused gain ranges {};"}),
    ("0265-recall-fusion/SUMMARY.json", "fusion_gain_analysis.fraction_of_vector_gain_surviving_fusion_mean", 4,
     {"t0265": "mean fraction {}, median"}),
    ("0265-recall-fusion/SUMMARY.json", "fusion_gain_analysis.fraction_of_vector_gain_surviving_fusion_median", 4,
     {"t0265": "median {})"}),
    # ---- 0267, the recommendation report. Every load-bearing figure it quotes,
    # anchored, per the ticket's own adherence test.
    ("0265-recall-fusion/SUMMARY.json", "keyword_arm.recall_at_topk", 4,
     {"v0267": 'keyword arm alone stands at {}):'}),
    ("0265-recall-fusion/SUMMARY.json", "keyword_arm.recall_at_topk", 4,
     {"v0267": 'keyword-alone baseline of {}, so'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.0.vector_recall.recall_at_topk", 4,
     {"v0267": 'falling from {} at its own'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.1.vector_recall.recall_at_topk", 4,
     {"v0267": 'fp32 to {}\n   (against'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.2.vector_recall.recall_at_topk", 4,
     {"v0267": 'recovers it ({})'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.0.vector_recall.recall_at_topk", 4,
     {"v0267": 'granite-97m-multilingual-r2 | {} | 0,5895'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.1.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9025 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.2.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,5895 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.3.vector_recall.recall_at_topk", 4,
     {"v0267": 'granite-311m-multilingual-r2 | {} | 0,9208'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.4.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9249 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.5.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9208 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.6.vector_recall.recall_at_topk", 4,
     {"v0267": 'arctic-embed-m-v2 | {} | 0,9278'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.7.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9294 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.8.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9278 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.9.vector_recall.recall_at_topk", 4,
     {"v0267": 'gte-multilingual-base | {} | 0,9164'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.10.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9158 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.11.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9164 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.12.vector_recall.recall_at_topk", 4,
     {"v0267": 'multilingual-e5-small | {} | 0,9058'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.13.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9049 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.14.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,9058 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.15.vector_recall.recall_at_topk", 4,
     {"v0267": 'multilingual-e5-base | {} | 0,896'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.17.vector_recall.recall_at_topk", 4,
     {"v0267": '| 0,896 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.16.vector_recall.recall_at_topk", 3,
     {"v0267": '| 0,9093 | {} |'}),
    ("0265-recall-fusion/SUMMARY.json", "fusion_gain_analysis.fraction_of_vector_gain_surviving_fusion_mean", 4,
     {"v0267": 'On average {} of\nthe vector'}),
    ("0265-recall-fusion/SUMMARY.json", "rows.1.fused_gain_over_keyword", 4,
     {"v0267": 'lands {} *below*'}),
    ("0482-gpu-corrected/throughput/granite-97m-multilingual-r2__fp32.json", "ms_per_passage_median", 2,
     {"v0267": 'granite-97m-multilingual-r2 | {} |'}),
    ("0482-gpu-corrected/throughput/gte-multilingual-base__fp32.json", "ms_per_passage_median", 1,
     {"v0267": 'gte-multilingual-base | {} |'}),
    ("0482-gpu-corrected/throughput/arctic-embed-m-v2__fp32.json", "ms_per_passage_median", 1,
     {"v0267": 'arctic-embed-m-v2 | {} |'}),
    ("0482-gpu-corrected/throughput/multilingual-e5-base__fp32.json", "ms_per_passage_median", 2,
     {"v0267": 'multilingual-e5-base | {} |'}),
    ("0482-gpu-corrected/throughput/granite-311m-multilingual-r2__fp32.json", "ms_per_passage_median", 2,
     {"v0267": 'granite-311m-multilingual-r2 | {} |'}),
    ("0482-gpu-corrected/throughput/multilingual-e5-small__fp32.json", "ms_per_passage_median", 2,
     {"v0267": 'multilingual-e5-small | {} |'}),
    ("0482-gpu-corrected/throughput/multilingual-e5-base__fp32.json", "projection_minutes_93022_rows", 1,
     {"v0267": 'corpus embeds in\n{} minutes'}),
    ("0482-gpu-corrected/x8-cross-provider-fidelity.json", "bar", 3,
     {"v0267": 'clears the {} vector-compatibility bar'}),
    ("0482-gpu-corrected/x8-cross-provider-fidelity.json", "cleared_count", 0,
     {"v0267": '({} of 18 scored cells'}),
    ("0482-gpu-corrected/x8-cross-provider-fidelity.json", "scored_count", 0,
     {"v0267": '(7 of {} scored cells'}),
    ("0482-gpu-corrected/x8-cross-provider-fidelity.json", "rows.1.cos_mean", 4,
     {"v0267": 'sit near {})'}),
    ("0263-cpu-arm/SUMMARY.json", "rows.0.cost.q8.rss_delta_mb_median", 1,
     {"v0267": 'loads at {} MB median'}),
    ("0263-cpu-arm/SUMMARY.json", "rows.5.cost.q8.rss_delta_mb_median", 1,
     {"v0267": 'recommended one\nat {} MB'}),
    ("0266-cross-lingual/multilingual-e5-base-q8.score.json", "pair_summary.en->vi.hit_at_10", 2,
     {"v0267": 'hit@10 of {} at q8'}),
    ("0266-cross-lingual/all-minilm-l6-v2-q8.score.json", "pair_summary.en->vi.hit_at_10", 2,
     {"v0267": 'contrast model scores\n{} — recall'}),

    # ---- the calibration-header entry (DECISIONS.md, awaiting ratification) ----
    # Two X8 cells carry that entry's argument: fp32 is cross-provider compatible
    # WITHOUT being bit-identical (so a hash over a header would false-positive),
    # and a cell can clear the bar while losing most of its top-30 overlap (so the
    # tolerant comparison cannot be cosine alone).
    ("0482-gpu-corrected/x8-cross-provider-fidelity.json", "rows.12.cos_min", 6,
     {"decisions": 'a minimum cosine of {} at fp32'}),
    ("0482-gpu-corrected/x8-cross-provider-fidelity.json", "rows.7.overlap_at_30_mean", 4,
     {"decisions": 'clears the bar while keeping {}\nof its top-30 overlap'}),

    # ---- 0499, sign bits as the chain identifier ----
    # The successor question to the entry above: if a byte hash is ruled out because
    # fp32 agrees in space and not in bytes, does a hash over SIGN bits survive? It
    # does not, and both the ledger entry and the ticket quote the same four figures
    # from one artifact. They are derived from committed cosines rather than measured
    # on vectors, which is exactly why they need the guard: the real-vector arm will
    # replace them, and the prose must move when it does.
    ("0499-chain-identifier/sign-stability.json",
     "verdict.worst_same_chain_row.expected_flipped_bits_per_vector", 3,
     {"decisions": '**{} of 768 sign bits move**', "t0499": '{} of 768 sign bits move'}),
    ("0499-chain-identifier/sign-stability.json",
     "verdict.worst_same_chain_row.p_sign_hash_matches_one_vector", 1,
     {"decisions": 'vector {} % of the time',
      "t0499": 'one vector {}% of the time'}, "pct"),
    ("0499-chain-identifier/sign-stability.json", "verdict.fp32_files.narrowest_separation", 2,
     {"decisions": 'at **{}x** the noise floor', "t0499": '{}x the noise floor'}),
    ("0499-chain-identifier/sign-stability.json", "verdict.eight_bit_files.separating_by_2x", 0,
     {"decisions": '**{} of 12** cells clears', "t0499": '{} of 12 cells clears'}),
    ("0499-chain-identifier/sign-stability.json", "verdict.eight_bit_files.inverting", 0,
     {"decisions": '**{} invert**', "t0499": 'and {} invert'}),
    ("0499-chain-identifier/sign-stability.json", "verdict.fp32_files.widest_separation", 2,
     {"t0499": 'case and {}x in the widest'}),

    # The projection arm. Its four numbers decide a format field, so they are the
    # ones a later re-run has to move in three places at once.
    ("0499-chain-identifier/projection-identity.json", "verdict.width_that_serves_every_model", 0,
     {"decisions": 'six models — {} dims', "t0499": 'six models: {} dims'}),
    ("0499-chain-identifier/projection-identity.json", "verdict.header_bytes_at_that_width", 0,
     {"decisions": 'dims, {} bytes per', "t0499": 'dims, {} bytes per header',
      "design": '{} bytes per header'}),
    ("0499-chain-identifier/projection-identity.json",
     "verdict.shrink_against_widest_full_header", 1,
     {"decisions": '{}x smaller than the full fp32', "t0499": '{}x smaller\nthan the full fp32',
      "design": '{}x smaller than the full fp32'}),
    ("0499-chain-identifier/projection-identity.json",
     "verdict.worst_aggregated_ratio_at_that_width", 2,
     {"decisions": 'worst case of {}x', "t0499": 'worst-case ratio of {}x against',
      "design": 'worst case of **{}x**'}),
    ("0499-chain-identifier/sign-stability.json", "verdict.expected_flips_at_artifact_precision", 3,
     {"decisions": 'admits {} flipped bits', "t0499": 'admits {} flipped bits'}),
    ("0499-chain-identifier/sign-stability.json",
     "controls.coordinate_quantization.understatement_factor", 2,
     {"decisions": '**{}x** under coordinate-wise', "t0499": 'flips {}x'}),
    ("0499-chain-identifier/sign-stability.json", "controls.isotropic.0.measured_mean_flips", 3,
     {"t0499": '({} measured against'}),
    ("0008-real-vectors/real-93022.json", "anisotropy.median_dimension_mean_abs", 5,
     {"t0499": 'median dimension of {})'}),

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

    A key containing a dot was unreachable for the same reason, and version numbers are
    exactly that: an artifact keyed by arm name (`v1.9.0`, `v1.10.0-default`) could not be
    declared at all. Escape the dots that belong to the key — `v1\\.9\\.0` — and only the
    unescaped ones separate levels. Renaming the artifact's keys to suit the checker was
    the alternative, and it is the wrong way round: the measurement names its arms after
    the releases it measured.
    """
    for part in re.split(r"(?<!\\)\.", path):
        part = part.replace("\\.", ".")
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


def main_for_test(results_dir: str, verbose: bool = False, minimum_pairs: int = 0) -> int:
    """The check, callable without argv. Exists so `tests/test_check_figures.py` drives the
    real code path rather than a copy of it — a test that reimplements the check tests the
    reimplementation."""
    return run(results_dir, verbose=verbose, listing=False, minimum_pairs=minimum_pairs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=str(REPO / "bench" / "results"))
    ap.add_argument("--verbose", action="store_true", help="name every presence-only pair")
    ap.add_argument("--list", action="store_true", help="print every declared figure and its current value")
    a = ap.parse_args()
    _validate_anchors()
    return run(a.results, verbose=a.verbose, listing=a.list, minimum_pairs=MINIMUM_PAIRS)


def run(
    results_dir: str,
    verbose: bool = False,
    listing: bool = False,
    minimum_pairs: int = MINIMUM_PAIRS,
) -> int:
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
    if checked < minimum_pairs:
        failures.append(
            f"COVERAGE SHRANK: {checked} pairs checked, below the {minimum_pairs}-pair "
            "ratchet. Re-record MINIMUM_PAIRS deliberately only after explaining which "
            "coverage was removed"
        )
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
