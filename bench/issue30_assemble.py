#!/usr/bin/env python3
"""Fold the three runs into the one artifact the tracking repo commits."""
import datetime
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("ISSUE30_ROOT", "/home/haduong/.claude/jobs/upstream30-latency"))
sem = json.loads((ROOT / "results-semantic.json").read_text())
aut = json.loads((ROOT / "results-auto.json").read_text())
extra = json.loads((ROOT / "results-codebuild-agreement.json").read_text())
run2 = json.loads((ROOT / "results-semantic-run2.json").read_text())
extra2 = json.loads((ROOT / "results-codebuild-agreement-run2.json").read_text())

ARMS = ["v1.9.0", "v1.10.0-exact", "v1.10.0-default"]
REPORTER_VECTORS, REPORTER_DIM = 255703, 3072


def arm_block(run, name):
    a = run["arms"][name]
    return {
        "sha": a["sha"],
        "env": a["env"],
        "warm": a["warm"],
        "cold_pass0": a["cold_pass0"],
        "vectorScan_observed_warm": a["vectorScan_values_warm"],
    }


def ratios(run):
    p = {n: run["arms"][n]["warm"] for n in ARMS}
    return {
        "v1.10.0-default_vs_v1.9.0": {
            "p50": round(p["v1.9.0"]["p50_ms"] / p["v1.10.0-default"]["p50_ms"], 2),
            "p95": round(p["v1.9.0"]["p95_ms"] / p["v1.10.0-default"]["p95_ms"], 2),
        },
        "v1.10.0-exact_vs_v1.9.0 (the fused cosine loop alone, #31/999cb1c)": {
            "p50": round(p["v1.9.0"]["p50_ms"] / p["v1.10.0-exact"]["p50_ms"], 2),
            "p95": round(p["v1.9.0"]["p95_ms"] / p["v1.10.0-exact"]["p95_ms"], 2),
        },
        "v1.10.0-default_vs_v1.10.0-exact (the two-stage alone, ad7c434)": {
            "p50": round(p["v1.10.0-exact"]["p50_ms"] / p["v1.10.0-default"]["p50_ms"], 2),
            "p95": round(p["v1.10.0-exact"]["p95_ms"] / p["v1.10.0-default"]["p95_ms"], 2),
        },
    }


geo = dict(sem["geometry"])
geo["vectors_are"] = (
    "REAL. The 93 022 passages are the author's own Zotero library as exported to "
    "bench substrate vec-real/; the vectors are mrl/minilm384.f32, produced by "
    "all-MiniLM-L6-v2 over those exact passage strings. Provenance was confirmed rather "
    "than assumed: five sampled rows re-embedded through Xenova/all-MiniLM-L6-v2 -- the "
    "model zoteus's own LocalEmbeddingProvider loads -- return cosine 1.000000 against "
    "the stored row, so the query and the corpus live in one vector space and no "
    "embedder mismatch can silently drop the vectors. Nothing here is synthetic."
)
geo["reporter_geometry_for_comparison"] = {
    "vectors": REPORTER_VECTORS,
    "dim": REPORTER_DIM,
    "vector_bytes_total": REPORTER_VECTORS * REPORTER_DIM * 4,
    "ours_is_smaller_by": round(REPORTER_VECTORS * REPORTER_DIM * 4 / geo["vector_bytes_total"], 1),
    "note": ("Issue #30 was reported on 255 703 passages at 3 072 dimensions -- 3,1 GB of "
             "vectors read per query against our 143 MB. The exact scan is linear in that "
             "product and the code scan is linear in the codes, so the ratio below is a "
             "FLOOR for what that reporter would see, not a ceiling."),
}

out = {
    "what": "semantic-query latency of upstream zoteus v1.9.0 against v1.10.0, three arms, one real index",
    "why": ("Upstream issue #30 was closed on a synthetic 42x measured on the maintainer's own "
            "machine, with a prediction that a real library would drop 'to a few hundred ms'. "
            "Nobody had measured v1.9.0 -> v1.10.0 end to end on a real index. This is that "
            "measurement."),
    "when": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "upstream": {
        "repository": "https://github.com/oscardvs/zoteus.git",
        "v1.9.0": "bb414df74852ce9ae106217a10462a828a91f375",
        "v1.10.0": "b132f2d",
        "changes_under_test": {
            "999cb1c": "perf(search): one traversal per vector, and stop making norm() polymorphic (#31)",
            "ad7c434": "perf(search): rank vectors through binary codes, then rescore exactly (#30)",
            "998865e": ("fix(search): cache on-device model weights under the data directory -- not "
                        "under test, but it is why each v1.10.0 arm's very first query in the main "
                        "run also paid a model download; see code_build, measured apart from it."),
        },
    },
    "machine": sem["machine"],
    "method": {
        "one_index_three_copies": ("v1.10.0 deliberately did not bump the schema, so the v1.9.0-built "
                                   "index opens there and gains its codes on first use. Each arm got "
                                   "its own COPY of that file so the two-stage arm's vector_codes "
                                   "writes could not reach the others."),
        "index_built_by": ("upstream v1.9.0's own SqliteSearchIndex (putItem / putPassage / putVector / "
                           "save), from real passages and real vectors already on disk -- no hand-written "
                           "SQL, so the schema, the FTS5 external-content protocol and the meta keys are "
                           "what a real v1.9.0 build writes."),
        "interleaved": "arms were rotated query by query, so no transient can land inside one arm.",
        "cold_separated": ("pass 0 is reported apart from the five warm passes; on the two-stage arm its "
                           "first query builds every binary code in one pass and is not steady state."),
        "vectorScan_checked": ("zotero_index action:'status' was read after EVERY query and its vectorScan "
                               "field recorded, so a timing cannot be mistaken for a two-stage that never "
                               "ran. The field is capable of both values in this harness: the "
                               "ZOTEUS_INDEX_ANN=false arm reports 'exact' on all 120 of its queries and "
                               "the default arm 'codes' on all 120 of its own. v1.9.0 has no such field, "
                               "and no code path either -- its exact scan is its only one."),
        "query_population": ("the twenty natural-language queries of bench/queries-x2.txt, committed in the "
                            "tracking repo. A p95 is a claim about a population."),
        "limit": sem["limit"],
        "repetitions": sem["repetitions"],
    },
    "geometry": geo,
    "results": {
        "semantic_mode": {
            "what": "mode:'semantic' -- vectors alone, no BM25. The path #30 is about.",
            "arms": {n: arm_block(sem, n) for n in ARMS},
            "speedups": ratios(sem),
            "per_query_warm_p50_ms": sem["per_query_warm_p50"],
        },
        "auto_mode": {
            "what": "mode:'auto' -- the hybrid default a user actually gets: BM25 and vectors, fused.",
            "arms": {n: arm_block(aut, n) for n in ARMS},
            "speedups": ratios(aut),
            "per_query_warm_p50_ms": aut["per_query_warm_p50"],
        },
    },
    "first_query_code_build": {
        **extra["code_build"],
        "second_independent_run": {k: extra2["code_build"][k] for k in
                                   ("first_query_building_codes_ms",
                                    "first_query_codes_already_on_disk_ms",
                                    "difference_ms", "upstream_own_notice")},
        "spread": ("the build is 1 527,8 ms then 1 440,0 ms across two independent runs, and "
                   "upstream's own notice reads 2,0 s then 1,8 s. Quote it as about one and a "
                   "half seconds, once, and not to three figures."),
    },
    "ranking_agreement": {
        **extra["agreement"],
        "reproduced": ("a second independent run returns the same three figures exactly "
                       "(9,65 / 20 / 17): the two-stage is deterministic here, so this is a "
                       "property of the index and not of the run."),
    },
    "query_embedding_cost": {
        "what": ("what every arm pays before a vector is touched, measured through upstream's own "
                 "LocalEmbeddingProvider on the same twenty queries"),
        "warm": {"n": 100, "min_ms": 4.0, "p50_ms": 5.0, "p95_ms": 6.1, "max_ms": 9.1},
        "first_call_ms_includes_model_load": 764.0,
        "why_it_matters": ("it is a fixed floor under every arm. At a two-stage p50 of 21,7 ms it is "
                           "roughly a quarter of the whole query; at v1.9.0's 1 069,1 ms it is half a "
                           "percent. So the arm ratios below UNDERSTATE what the vector scan itself "
                           "gained."),
    },
    "findings": {
        "against_the_prediction": (
            "Issue #30 was closed predicting a drop 'to a few hundred ms'. On this index "
            "v1.10.0 lands an order of magnitude BELOW that prediction on the vector path: "
            "mode:'semantic' median 21,7 ms against v1.9.0's 1 069,1 ms, and the hybrid "
            "default a user actually gets is 93,1 ms against 1 136,0 ms. The prediction is "
            "met with room to spare -- on OUR geometry, which is 22x smaller than the "
            "reporter's in bytes read per query."),
        "the_two_causes_do_not_split_evenly": (
            "Of the 49,3x median, the fused cosine loop (#31, 999cb1c) contributes 1,31x and "
            "the two-stage code path (ad7c434) the remaining 37,5x. #31's own commit measured "
            "2,19x on a 255 703 x 3 072 index; the smaller end-to-end gain here is consistent "
            "with the model that commit states -- a width-proportional arithmetic saving "
            "sitting on a per-row fetch cost that does not shrink with it, and our vectors are "
            "eight times narrower -- but that decomposition was NOT isolated in this run and is "
            "offered as a reading, not a measurement."),
        "the_fast_answer_is_the_same_answer": (
            "Across the twenty queries the two-stage returns the same first hit 20 times out of "
            "20, the identical ordered top-10 17 times out of 20, and a mean top-10 overlap of "
            "9,65. The approximation costs about 3,5% of the page at limit 10 on this index, "
            "which is the documented behaviour, not a defect."),
        "the_upgrade_is_not_free_but_it_is_cheap": (
            "A v1.9.0-built index pays one code build inside its first semantic query: 1 527,8 ms "
            "here, measured as the difference between that query and the same query after a "
            "restart on the file that now carries the codes. Upstream's own notice reports 2,0 s "
            "for the same event, which additionally covers loading the codes into the process -- "
            "work the restart also pays, so the two numbers agree. The codes cost 4 465 056 bytes "
            "beside 142 881 792 bytes of vectors."),
        "what_this_does_not_settle": (
            "The reporter's index is 255 703 x 3 072 and reported ~95 s per query on Windows / "
            "Node 24; this one is 93 022 x 384 and reports ~1,07 s on Linux / Node 22. The gap "
            "between 1,07 s and 95 s is not explained by anything measured here, and 999cb1c's "
            "own message flags the same open question. So this run says what the change is worth "
            "on a real Linux library of this size. It does not say what it is worth on that "
            "reporter's machine, and no arithmetic here can be stretched to."),
    },
    "reproducibility": {
        "why": ("Ticket 0025 recorded that these scan figures move run to run more than one run "
                "admits (three invocations at #30's geometry gave 42,1x / 44,6x / 55,9x). So the "
                "whole semantic run was repeated, independently, fresh copies and fresh servers."),
        "run1": {n: sem["arms"][n]["warm"] for n in ARMS},
        "run2": {n: run2["arms"][n]["warm"] for n in ARMS},
        "median_speedup_v1100default_vs_v190": {
            "run1": round(sem["arms"]["v1.9.0"]["warm"]["p50_ms"]
                          / sem["arms"]["v1.10.0-default"]["warm"]["p50_ms"], 2),
            "run2": round(run2["arms"]["v1.9.0"]["warm"]["p50_ms"]
                          / run2["arms"]["v1.10.0-default"]["warm"]["p50_ms"], 2),
        },
        "p95_speedup_v1100default_vs_v190": {
            "run1": round(sem["arms"]["v1.9.0"]["warm"]["p95_ms"]
                          / sem["arms"]["v1.10.0-default"]["warm"]["p95_ms"], 2),
            "run2": round(run2["arms"]["v1.9.0"]["warm"]["p95_ms"]
                          / run2["arms"]["v1.10.0-default"]["warm"]["p95_ms"], 2),
        },
        "reading": ("the median ratio reproduces to two figures; the p95 ratio does not, because "
                    "the EXACT arm's tail moves (1 363,5 ms then 1 708,0 ms) while the two-stage "
                    "arm's does not. Quote the median, and the smaller of the two p95 ratios."),
    },
    "raw": {
        "semantic": sem["raw"],
        "semantic_run2": run2["raw"],
        "auto": aut["raw"],
        "semantic_restart_cold": sem["raw_restart"],
    },
}
p = ROOT / "v190-vs-v1100-semantic-latency-93022x384.json"
p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf8")
print(p, p.stat().st_size)
