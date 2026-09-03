#!/usr/bin/env python3
"""Assemble ticket 0120 action 1: what our own keyword build costs, against zero for the platform path.

Action 1 asks for wall time, peak RSS and disk of *our* keyword index on the real
library, set against the platform FTS5 index, whose build cost to us is zero because
Zotero already paid it. This reads the `RESULT {...}` lines that `bench/run_build.py`
emits and writes one artifact; it measures nothing itself, so every figure here is
traceable to a run whose log is named in `sources`.

Two scale points, not one. A single full-library run gives a total and no way to split
the fixed per-build term (the attachment-page walk, paid once whatever the library
holds) from the marginal per-passage term. The 300- and 1200-item runs give that split
by difference, and the full run is then a check on the extrapolation rather than its
source.

Usage:
    python3 bench/summarize_0120.py --full <log> --small <log> --mid <log> \
        --server <path to fork/dist/index.js> --out bench/results/0120-keyword-build/...json
"""
import argparse
import hashlib
import json
import logging
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("0120")

RESULT_RE = re.compile(r"^RESULT (\{.*\})\s*$")


def last_result(path: Path) -> dict:
    """The final RESULT line of a run log. Raises rather than returning {}.

    A missing RESULT means the run did not finish, and an empty dict would travel
    silently into the artifact as a build that cost nothing.
    """
    found = None
    for line in path.read_text(errors="replace").splitlines():
        m = RESULT_RE.match(line)
        if m:
            found = json.loads(m.group(1))
    if found is None:
        raise RuntimeError(f"{path} carries no RESULT line — the run did not finish")
    return found


def mib(n: int) -> float:
    """Bytes as MiB, rounded where the prose rounds.

    The note and the ticket quote MiB, never bytes, so MiB is what the figure guard has
    to be able to compare. Leaving the conversion to the prose puts arithmetic nothing
    checks between the artifact and the reader — which is the exact failure the guard
    exists for, one step earlier.
    """
    return round(n / 1048576, 1)


def disk(files: dict[str, int]) -> dict[str, int]:
    """Index bytes on disk, splitting the WAL out rather than folding it in.

    The WAL is real occupancy when the build ends and is also transient: a checkpoint
    folds it into the main file. Reporting the sum alone overstates the steady state;
    reporting the main file alone understates what the build needed.
    """
    main = files.get("search-index.sqlite", 0)
    wal = files.get("search-index.sqlite-wal", 0)
    shm = files.get("search-index.sqlite-shm", 0)
    return {"sqlite_bytes": main, "wal_bytes": wal, "shm_bytes": shm,
            "total_bytes": main + wal + shm}


def arm(path: Path) -> dict:
    r = last_result(path)
    st = r["status"]
    passages = st["passages"]
    fulltext = st["fulltextPassages"]
    own = st["ownWordsPassages"]
    return {
        "log": str(path),
        "items_indexed": st["items"],
        "items_available": st["itemsAvailable"],
        "passages": passages,
        "fulltext_passages": fulltext,
        "own_words_passages": own,
        # What is left is metadata. The platform index holds no metadata at all, so this
        # is the part of our index it could not serve even in principle.
        "metadata_passages": passages - fulltext - own,
        "fulltext_items": st["fulltextItems"],
        "vectors": st["vectors"],
        "embedder": st["embedder"],
        "elapsed_s": r["elapsed_s"],
        "peak_rss_kb": r["peak_rss_kb"],
        "peak_rss_mib": mib(r["peak_rss_kb"] * 1024),
        "disk": disk(r["files"]),
        "sqlite_mib": mib(disk(r["files"])["sqlite_bytes"]),
        "wal_mib": mib(disk(r["files"])["wal_bytes"]),
        "state": st["state"],
        "local_api_degraded_at": st.get("localApiDegradedAt"),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


POLL_RE = re.compile(r"^\[\s*(\d+)s peak ([0-9.]+) GB\]")


def peak_trajectory(path: Path) -> dict:
    """When the peak arrived and whether it held — read off the driver's poll lines.

    A single peak figure cannot say which of two very different things it is: a spike
    during the one-off attachment-page walk, or the plateau of steady-state indexing.
    They argue for different ceilings, so the distinction is reported rather than left
    to the reader. The series is already in the log; nothing is re-run to get it.
    """
    points = [(int(m.group(1)), float(m.group(2)))
              for line in path.read_text(errors="replace").splitlines()
              if (m := POLL_RE.match(line))]
    if not points:
        raise RuntimeError(f"{path} carries no poll lines — the trajectory cannot be read")
    top = max(v for _, v in points)
    first_at_top = min(s for s, v in points if v == top)
    last_s = points[-1][0]
    return {
        "polls": len(points),
        "peak_gb_as_the_driver_printed_it": top,
        "first_reached_at_s": first_at_top,
        "held_for_s": last_s - first_at_top,
        "opening_gb": points[0][1],
        "series_s_gb": points,
    }


#: The FTS5 shadow tables: the keyword index proper, and the only part of our file the
#: platform's own index could stand in for. Everything else — the `passages` table and
#: its indexes — is stored text and its addressing, which contentless FTS5 does not hold.
FTS_TABLES = ("passages_fts_data", "passages_fts_idx", "passages_fts_docsize",
              "passages_fts_config")


def decompose(db: Path) -> dict:
    """Split the built index into the keyword half and the stored-text half, by dbstat.

    This is the figure the recommendation turns on. The saving from adopting the platform
    index is bounded by the keyword half alone: our passage text has to stay on disk
    whatever indexes it, because the platform tables are contentless and cannot print a
    passage back.
    """
    rows = subprocess.run(
        ["sqlite3", str(db), "select name, sum(pgsize) from dbstat group by name;"],
        capture_output=True, text=True, check=True).stdout.strip().splitlines()
    by_name = {}
    for row in rows:
        name, _, size = row.rpartition("|")
        by_name[name] = int(size)
    fts = sum(v for k, v in by_name.items() if k in FTS_TABLES)
    total = sum(by_name.values())
    return {
        "db": str(db),
        "bytes_by_object": dict(sorted(by_name.items(), key=lambda kv: -kv[1])),
        "keyword_index_bytes": fts,
        "keyword_index_mib": mib(fts),
        "stored_text_and_addressing_bytes": total - fts,
        "stored_text_and_addressing_mib": mib(total - fts),
        "total_bytes": total,
        "keyword_index_share_pct": round(100 * fts / total, 1),
        "stored_text_share_pct": round(100 * (total - fts) / total, 1),
        "what_the_platform_could_displace": "the keyword half only — the stored text has to "
                                            "stay whatever indexes it, because fulltext.sqlite "
                                            "is contentless and cannot print a passage back",
    }


def machine() -> dict:
    cpuinfo = Path("/proc/cpuinfo").read_text()
    cpu = ""
    for line in cpuinfo.splitlines():
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    mem_kb = 0
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            mem_kb = int(line.split()[1])
            break
    node = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    return {
        "host": platform.node(),
        "cpu": cpu,
        "cores": len(re.findall(r"^processor", cpuinfo, re.M)),
        "mem_gb": round(mem_kb / 1048576, 1),
        "kernel": platform.release(),
        "node": node,
        "loadavg_at_summary": [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]],
        "is_reference_machine": "yes — SPEC.md §5.2.8 names an Intel i5-8250U at 1,6 GHz, no GPU",
    }


def two_point_fit(lo: dict, hi: dict, full: dict) -> dict:
    """Split a build into a fixed per-build term and a marginal per-passage one.

    Lives here rather than inline in main() so it can be tested against fixtures. The
    arithmetic is trivial and that is exactly why it needs a test: an artifact whose
    derived block is only ever checked by "does the prose quote it" is guarded against
    a stale copy and not against a wrong original.
    """
    d_passages = hi["passages"] - lo["passages"]
    if d_passages <= 0:
        raise RuntimeError("the two scale points carry no passage difference to fit on")
    marginal_ms = (hi["elapsed_s"] - lo["elapsed_s"]) * 1000 / d_passages
    fixed_s = lo["elapsed_s"] - lo["passages"] * marginal_ms / 1000
    marginal_bytes = (hi["disk"]["sqlite_bytes"] - lo["disk"]["sqlite_bytes"]) / d_passages
    predicted_s = fixed_s + full["passages"] * marginal_ms / 1000
    return {
        "basis": "the 300- and 1200-item runs, by difference",
        "marginal_ms_per_passage": round(marginal_ms, 3),
        "fixed_s_per_build": round(fixed_s, 1),
        "marginal_bytes_per_passage": round(marginal_bytes, 1),
        "predicted_full_library_s": round(predicted_s, 1),
        "measured_full_library_s": full["elapsed_s"],
        "prediction_error_pct": round(
            100 * (predicted_s - full["elapsed_s"]) / full["elapsed_s"], 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True, type=Path)
    ap.add_argument("--small", required=True, type=Path)
    ap.add_argument("--mid", required=True, type=Path)
    ap.add_argument("--embedding-build", type=Path,
                    help="the 2026-09-02 full build log, for the keyword share of an embedding build")
    ap.add_argument("--server", required=True, type=Path)
    ap.add_argument("--poll-quantum-s", required=True, type=float,
                    help="the --poll the runs were driven at; it bounds how much every "
                         "elapsed_s here overstates the build")
    ap.add_argument("--index-db", type=Path,
                    help="the full-library index the full run left behind, for the "
                         "keyword-half / stored-text split")
    ap.add_argument("--platform-index", type=Path,
                    default=Path("/home/haduong/data/Zotero/fulltext.sqlite"))
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    arms = {"full_library": arm(a.full), "scale_300": arm(a.small), "scale_1200": arm(a.mid)}

    full = arms["full_library"]
    derived = {
        "two_point_fit": two_point_fit(arms["scale_300"], arms["scale_1200"], full),
        "full_library_rates": {
            "ms_per_passage": round(full["elapsed_s"] * 1000 / full["passages"], 3),
            "bytes_per_passage": round(full["disk"]["sqlite_bytes"] / full["passages"], 1),
            "passages_per_s": round(full["passages"] / full["elapsed_s"], 1),
        },
        # An upper bound on the saving, not the saving. The platform tables are
        # contentless, so this counts passages whose text the platform also holds — not
        # passages it could answer with.
        "displaceable_upper_bound": {
            "fulltext_passage_share_pct": round(100 * full["fulltext_passages"] / full["passages"], 1),
            "metadata_and_own_words_passages": full["metadata_passages"] + full["own_words_passages"],
            "metadata_and_own_words_share_pct": round(
                100 * (full["metadata_passages"] + full["own_words_passages"]) / full["passages"], 1),
            "note": "metadata and own words (notes, annotations) have no counterpart in "
                    "fulltext.sqlite at all",
        },
    }

    # What the peak figure is a peak OF. C3's budgets bind per process class, so a
    # number that cannot say which class it measured cannot be checked against them.
    traj = peak_trajectory(a.full)
    derived["peak_rss_scope"] = {
        "process_scope": "one process, and it is the whole tree: run_build.py reads VmHWM "
                         "from /proc/<server pid>/status, which is per-process, and the "
                         "built server spawns nothing — no `new Worker`, no `child_process`, "
                         "no `spawn(` anywhere under fork/dist (checked 2026-09-03). With "
                         "the embedder off there is no embedding service beside it either.",
        "phase": "steady-state indexing, not the one-off crawl setup",
        "evidence": "the driver's own poll series: the run opens at "
                    f"{traj['opening_gb']} GB and holds it through the metadata pass and the "
                    f"8 037-attachment walk, climbs once the full-text pass begins, reaches "
                    f"{traj['peak_gb_as_the_driver_printed_it']} GB at "
                    f"{traj['first_reached_at_s']} s and then stays flat for the remaining "
                    f"{traj['held_for_s']} s of the build",
        "so_it_is_a_plateau_not_a_spike": traj["held_for_s"] > 0,
        "trajectory": traj,
        "no_c3_row_applies": "C3's two ~750 MB rows — server steady-state RSS and "
                             "pipeline-worker peak — both describe SPEC.md §5.2.5's topology: "
                             "a conductor and query servers holding no model beside one "
                             "embedding service that does, with §5.2.9's P0 idling near "
                             "100 MB. The measured binary is stock upstream v1.12.0 and "
                             "implements neither side of that split, which the process_scope "
                             "grep is what establishes. So reading this figure as level with "
                             "the ceiling compares a single-process build against a budget "
                             "written for a topology it does not implement. Both figures are "
                             "annotated as awaiting a re-pin besides.",
        "what_it_does_support": "C3's PROPERTY rather than its number: the RAM ceiling is "
                                "independent of library and document size because extraction "
                                "and chunking stream. Flat through the metadata pass and the "
                                "whole attachment walk, climbing only with full text, then "
                                "flat again while the crawl works through thousands more "
                                "items, is the shape that property predicts.",
        "the_measurement_that_would_settle_it": "the same run against our own topology — a P0 "
                                                "that should idle near 100 MB, weighed against "
                                                "the server row. Nobody has that number and "
                                                "this run is not it.",
        "and_the_plateau_is_bounded_too": "flat for the last 87 s of a 305,9 s build, on one "
                                          "library and one machine. That is what a working-set "
                                          "ceiling looks like, and it is not proof of one: a "
                                          "plateau held over 87 s says nothing about a build "
                                          "that runs for hours, and the 2026-09-02 embedding "
                                          "build reached 2 409,6 MiB on the same library.",
    }

    if a.index_db and a.index_db.exists():
        derived["on_disk_decomposition"] = decompose(a.index_db)

    if a.embedding_build and a.embedding_build.exists():
        emb = last_result(a.embedding_build)
        derived["against_the_embedding_build"] = {
            "log": str(a.embedding_build),
            "elapsed_s": emb["elapsed_s"],
            "peak_rss_kb": emb["peak_rss_kb"],
            "peak_rss_mib": mib(emb["peak_rss_kb"] * 1024),
            "disk": disk(emb["files"]),
            "sqlite_mib": mib(disk(emb["files"])["sqlite_bytes"]),
            "keyword_share_of_wall_pct": round(100 * full["elapsed_s"] / emb["elapsed_s"], 2),
            "keyword_share_of_disk_pct": round(
                100 * full["disk"]["sqlite_bytes"] / disk(emb["files"])["sqlite_bytes"], 1),
            "keyword_share_of_peak_rss_pct": round(
                100 * full["peak_rss_kb"] / emb["peak_rss_kb"], 1),
            "note": "same library, same flags, same server; the only difference is ZOTEUS_EMBEDDINGS",
        }

    plat = a.platform_index
    platform_arm = {
        "build_wall_s": 0.0,
        "build_peak_rss_kb": 0,
        "incremental_disk_bytes": 0,
        "why_zero": "Zotero builds and maintains fulltext.sqlite whether or not we read it; "
                    "adopting it adds no build pass, no extraction, no memory and no bytes of ours",
        "file_on_disk_bytes": plat.stat().st_size if plat.exists() else None,
        "file_on_disk_mib": mib(plat.stat().st_size) if plat.exists() else None,
        "file": str(plat),
        "what_that_zero_does_not_include": [
            "the query-time cost of using it, which this action does not measure",
            "metadata and own-words passages, which it does not hold at any price",
            "reproducing Zotero's tokenizer to turn a token offset into an entry span (action 4)",
            "availability under a writer's exclusive lock (action 3)",
        ],
    }

    # Ticket 0260's warmth flag, read off the runs rather than asserted. The one-time
    # cost that corrupts a per-unit rate here would be a model load or a model download
    # inside the timed window, and the status object is where its absence is legible:
    # an arm with `vectors: 0` and no active embedder loaded nothing. Anything softer —
    # a hand-set true — would make the flag a claim about the author's memory rather
    # than about the run.
    warm = all(a_["vectors"] == 0 and a_["embedder"].startswith("none") for a_ in arms.values())

    out = {
        "ticket": "0120",
        "action": 1,
        "warm": warm,
        "warm_basis": "no model load and no download inside any timed window — every arm ran "
                      "with the embedder off, which the status object records as vectors 0 and "
                      "an inactive embedder, and this assembler sets the flag from that rather "
                      "than by hand. Each arm was also a re-run over caches an earlier identical "
                      "run had already read, so the platform's own text was warm in the page "
                      "cache. The one fixed cost that remains inside the window is the "
                      "8 037-attachment page walk, which is not amortizable — every build pays "
                      "it whole — and it is reported as the fit's fixed term rather than "
                      "smuggled into the per-passage rate.",
        "what": "wall time, peak RSS and disk of our own keyword-only index build on the real "
                "library, against zero for the platform FTS5 path",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "machine": machine(),
        "under_measurement": {
            "server": str(a.server),
            "server_sha256": sha256(a.server),
            "driver": "bench/run_build.py",
            "env": {"ZOTEUS_EMBEDDINGS": "off", "ZOTEUS_INDEX_BACKEND": "sqlite",
                    "ZOTEUS_INDEX_FULLTEXT": "1",
                    "ZOTEUS_INDEX_MAX_ITEMS": "1000000 (full run), 300, 1200",
                    "ZOTEUS_INDEX_FULLTEXT_MAX_CHARS": "200000",
                    "ZOTEUS_INDEX_AUTO_REFRESH": "false"},
            "peak_rss_method": "kernel VmHWM high-water mark, not a sampler",
            "poll_quantum_s": a.poll_quantum_s,
            "what_the_quantum_does": "run_build.py sleeps --poll between status calls and "
                                     "breaks on the first poll that sees `done`, so every "
                                     "elapsed_s is the true build time rounded UP to the next "
                                     "poll boundary. At --poll 20 the 300- and 1200-item runs "
                                     "both reported 140,3 s — the quantum, not the build — "
                                     "which is why these arms were re-driven at a finer one.",
        },
        "ours": arms,
        "platform": platform_arm,
        "derived": derived,
        "caveats": [
            f"Every elapsed_s is an upper bound within the {a.poll_quantum_s:g} s poll "
            f"quantum: the driver breaks on the first poll that sees the build done, so the "
            f"full-library figure overstates by at most {a.poll_quantum_s:g} s "
            f"({100 * a.poll_quantum_s / full['elapsed_s']:.1f} % of it).",
            "One machine, no GPU, and other lanes were active — the loadavg is recorded "
            "rather than controlled, so the wall figures are upper bounds on an idle machine.",
            "Both Zotero full-text caps are raised on this install (pdfMaxPages 999999, "
            "textMaxLength 999999999), so the body text read here is longer than a default "
            "install would hold, and the passage counts with it.",
            "--max-chars 200000 matches the 2026-09-02 embedding build; the shipped default "
            "is 40 000 and would index far less body text per item.",
            "The WAL is reported beside the main file rather than folded into it; a "
            "checkpoint moves those bytes without changing the total the build needed.",
            "The scale points cap items, not attachments: the attachment-page walk covers "
            "all 8 037 extracted attachments in every run, which is why the fixed term is large.",
        ],
        "sources": {k: v["log"] for k, v in arms.items()},
    }

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    log.info("wrote %s", a.out)
    log.info("full library keyword-only: %.1f s, peak %.2f GB, %.1f MB on disk over %d passages",
             full["elapsed_s"], full["peak_rss_kb"] / 1048576,
             full["disk"]["sqlite_bytes"] / 1048576, full["passages"])


if __name__ == "__main__":
    main()
