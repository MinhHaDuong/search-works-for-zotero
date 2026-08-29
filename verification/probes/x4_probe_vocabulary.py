#!/usr/bin/env python3
"""Why X4's real-corpus arm cannot be run with the driver as written.

`bench/constrained_match.mjs` builds a synthetic Zipf corpus and probes it with
terms from that corpus's own vocabulary — `"w5" OR "w1200" OR "w25000"`. Given a
db path it skips the build and probes an EXISTING index, and RUNBOOK step 7
offered that as X4's confirmation on the real 477 512-passage corpus.

The trap is that the synthetic terms are not absent from a real library. OCR
debris and variable names put a handful of them in, so the MATCH neither errors
nor returns empty: it returns almost nothing, fast, and the run reads as a pass.
Since X4's rule is an upper bound on latency, a vacuously fast arm INVERTS the
verdict — DESIGN 3's 150 ms allowance looks satisfied by a query that did no
work.

This probe measures both arms so the claim is reproducible rather than asserted.
The real-vocabulary arm is the positive control: it must be slow, or the probe
has not demonstrated that the synthetic arm's speed means anything.

    python3 verification/probes/x4_probe_vocabulary.py --db <real-index.sqlite>
"""
import argparse
import json
import logging
import sqlite3
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("x4probe")

SYNTHETIC = '"w5" OR "w1200" OR "w25000"'
#: The df bands the driver's own comment says the cost depends on: one common
#: term, one mid, one rare. Fractions of the passage count.
BANDS = {"common": (0.10, 1.01), "mid": (0.001, 0.01), "rare": (5e-6, 1e-3)}
MATCH_SQL = ("SELECT rowid, bm25(passages_fts) AS score FROM passages_fts "
             "WHERE passages_fts MATCH ? ORDER BY score LIMIT 30")


def time_match(con: sqlite3.Connection, query: str, repeats: int = 3) -> dict:
    best = None
    rows = 0
    for _ in range(repeats):
        t = time.perf_counter()
        rows = len(con.execute(MATCH_SQL, (query,)).fetchall())
        ms = (time.perf_counter() - t) * 1000
        best = ms if best is None else min(best, ms)
    return {"query": query, "rows_returned": rows, "best_ms": round(best, 1)}


def vocabulary(con: sqlite3.Connection, n_passages: int) -> dict:
    """Read the term/df spread from fts5vocab, and sample one term per band."""
    con.execute("CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, passages_fts, row)")
    t = time.perf_counter()
    total = con.execute("SELECT count(*) FROM temp.v").fetchone()[0]
    scan_s = round(time.perf_counter() - t, 1)

    bands, sample = {}, {}
    for name, (lo, hi) in BANDS.items():
        lo_n, hi_n = int(lo * n_passages), int(hi * n_passages)
        bands[name] = con.execute(
            "SELECT count(*) FROM temp.v WHERE doc >= ? AND doc < ?", (lo_n, hi_n)).fetchone()[0]
        row = con.execute(
            "SELECT term, doc FROM temp.v WHERE doc >= ? AND doc < ? ORDER BY doc DESC LIMIT 1",
            (lo_n, hi_n)).fetchone()
        if row:
            sample[name] = {"term": row[0], "df": row[1], "df_pct": round(100 * row[1] / n_passages, 2)}
    return {"distinct_terms": total, "vocab_scan_s": scan_s, "band_counts": bands, "sampled": sample}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="a NEW-schema index (passages + passages_fts)")
    ap.add_argument("--output", help="write JSON here instead of stdout")
    a = ap.parse_args()

    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    n = con.execute("SELECT count(*) FROM passages").fetchone()[0]

    synthetic = time_match(con, SYNTHETIC)
    voc = vocabulary(con, n)
    real_query = " OR ".join(f'"{voc["sampled"][b]["term"]}"' for b in ("common", "mid", "rare")
                             if b in voc["sampled"])
    control = time_match(con, real_query)

    verdict = ("DEMONSTRATED: the synthetic arm is fast because it matches almost nothing, and the "
               "real-vocabulary control on the same index is far slower"
               if control["best_ms"] > 10 * max(synthetic["best_ms"], 0.1)
               else "NOT DEMONSTRATED: the control did not come out slower, so this run shows nothing")

    out = {
        "probe": "X4's real-corpus arm cannot use the driver's synthetic probe vocabulary",
        "db": a.db,
        "passages": n,
        "synthetic_arm": synthetic,
        "real_vocabulary_control": control,
        "vocabulary": voc,
        "verdict": verdict,
    }
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.output:
        with open(a.output, "w") as fh:
            fh.write(text)
    else:
        print(text)
    log.info("%s", verdict)


if __name__ == "__main__":
    main()
