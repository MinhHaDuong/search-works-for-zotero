#!/usr/bin/env python3
"""Smoke the reviewed upstream baseline against a real Zotero library, by requirement.

`verification/SMOKE-1.10.0.md` recorded one session driven by hand. This is the
repeatable form: each check names the requirement clause it exercises, states what
would falsify it, and lands in a JSON artifact so `README.md` can cite a run
rather than a memory.

What it is NOT: a requirements test suite. R-items are sets of MUST clauses, and a
check here exercises ONE clause of one requirement, against one library, once. It
earns a row the word `measured` in place of `code` — something ran — and nothing
stronger. Where a check cannot decide, it reports `observed` rather than inventing
a verdict.

Every check is read-only against the Zotero library. The schema check writes only
to a COPY of an index, made by this script in a scratch directory.

    python3 bench/smoke_upstream.py --server <fork>/dist/index.js \\
        --index <a-current-search-index.sqlite> --output bench/results/smoke-1.10.0/checks.json
"""
import argparse
import json
import logging
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_drive import Server  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("smoke")


def payload(resp: dict) -> dict:
    r = resp.get("result", resp)
    if "structuredContent" in r:
        return r["structuredContent"]
    for block in r.get("content", []):
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return {"text": block["text"][:4000]}
    return r


def env_for(a: argparse.Namespace, data_dir: Path) -> dict[str, str]:
    env = {
        "ZOTEUS_EMBEDDINGS": "local",
        "ZOTEUS_DATA_DIR": str(data_dir),
        "ZOTEUS_INDEX_BACKEND": "sqlite",
        "ZOTEUS_INDEX_AUTO_REFRESH": "false",
        "ZOTEUS_INDEX_FULLTEXT": "1",
        "ZOTEUS_READ_ONLY": "true",
    }
    if a.transformers_path:
        env["ZOTEUS_TRANSFORMERS_PATH"] = a.transformers_path
    if a.zotero_data_dir:
        env["ZOTERO_DATA_DIR"] = a.zotero_data_dir
    return env


def start(a: argparse.Namespace, data_dir: Path) -> Server:
    s = Server(["node", a.server], env_for(a, data_dir), timeout=a.timeout)
    s.handshake()
    return s


def check(cid: str, requirement: str, clause: str, falsified_by: str,
          result: str, detail: object) -> dict:
    return {"check": cid, "requirement": requirement, "clause": clause,
            "falsified_by": falsified_by, "result": result, "detail": detail}


def check_local_by_default(s: Server) -> dict:
    """R10: the default embedder is local — asserted against a running server, not the source."""
    who = payload(s.call("tools/call", {"name": "zotero_whoami", "arguments": {}}))
    st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    emb = who.get("embeddings", {})
    ok = emb.get("effective") == "local" and st.get("embedderActive") is True and st.get("embedder") == "local"
    return check(
        "R10-local-embedder", "R10", "the embedder is local by default",
        "effective embeddings resolving to a hosted provider, or an inactive local embedder",
        "pass" if ok else "fail",
        {"whoami_embeddings": emb, "status_embedder": st.get("embedder"),
         "embedderActive": st.get("embedderActive"), "model": st.get("embedderModel"),
         "cloud": who.get("cloud"), "localApi": who.get("localApi")})


def check_model_stays_in_data_dir(data_dir: Path, present_before: bool,
                                  embedder_active: bool, runs: int) -> dict:
    """R15: the downloaded model does not escape the data directory (the uninstall clause).

    Filed against R28 originally; R28 merged into R15's uninstall clause on
    2026-08-31 (DECISIONS.md), "removal being complete at the item scale and
    the install scale" -- relabelled here rather than kept on a retired number.

    ORDERING IS THE WHOLE CHECK, and it was wrong until 2026-09-03. The model is
    fetched lazily, on the first text this process embeds. Run before any query and
    a fresh data directory has no `models/` yet, so the check reported the absence
    as "reused an existing cache … decides nothing" — an all-clear indistinguishable
    from "I could not look", on precisely the run that was about to prove the clause.
    It now runs AFTER the query check, and takes `present_before` (sampled at server
    start) so the artifact distinguishes three different facts:

      - a cache that did not exist before this run and does after → this run
        downloaded it, under the data directory: `pass`, the positive control;
      - a cache that was already there → `observed`, nothing was exercised;
      - no cache after an embedding really happened → `fail`, the falsifier: the
        weights went somewhere else.
    """
    models = data_dir / "models"
    present = models.is_dir()
    files = sorted(p.name for p in models.iterdir()) if present else []
    embedded = embedder_active and runs > 0
    if present and not present_before:
        result, note = "pass", ("no model cache existed in this data dir at server start and one "
                                "does after the queries — this run downloaded it, here")
    elif present:
        result, note = "observed", ("the cache was already in this data dir before the run, so this "
                                    "check did not exercise a download and decides nothing")
    elif embedded:
        result, note = "fail", ("the embedder was active and queries ran, so weights were loaded, "
                                "yet no model cache exists under the data dir — it went elsewhere")
    else:
        result, note = "observed", ("nothing embedded on this run (no active embedder, or no query "
                                    "completed), so this check could not look")
    return check(
        "R15-model-in-data-dir", "R15", "the model cache lives under the data directory",
        "a model cache created outside the data directory (a shared HF cache, or $HOME)",
        result,
        {"models_dir": str(models), "exists_at_server_start": present_before,
         "exists_after_queries": present, "entries": files[:10],
         "embedding_happened_this_run": embedded, "note": note})


def _index_facts(path: Path) -> dict:
    """What an index file holds, read straight off the file with no server in the way.

    The before/after pair of this is the only evidence in the script that does not come
    from the thing under test describing itself. A migration notice is upstream's claim;
    these row counts are the check's own.
    """
    facts: dict = {"bytes": path.stat().st_size if path.exists() else None}
    if not path.exists():
        return facts
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        for name, sql in (
            ("schemaVersion", "SELECT value FROM meta WHERE key='schemaVersion'"),
            ("embedderId", "SELECT value FROM meta WHERE key='embedderId'"),
            ("passages", "SELECT COUNT(*) FROM passages"),
            ("passages_with_vector", "SELECT COUNT(*) FROM passages WHERE vector IS NOT NULL"),
        ):
            try:
                row = con.execute(sql).fetchone()
                facts[name] = row[0] if row else None
            except sqlite3.Error:
                facts[name] = None
    finally:
        con.close()
    return facts


def check_previous_schema_migrates_in_place(a: argparse.Namespace, scratch: Path,
                                            queries: list[str], limit: int) -> dict:
    """R23, older-stamp direction: an index written under the PREVIOUS schema ends up served.

    This replaces `check_migration_absent`, whose premise upstream retired. That check
    reported, in a string typed into the source, that "no in-place upgrade ladder runs
    (SCHEMA_MIGRATIONS is empty)". At v1.13.0 `SCHEMA_VERSION` is 2 and the ladder carries
    one real rung — it rebuilds `passages_fts` under a diacritic-preserving tokenizer and
    re-embeds nothing — so the old check wrote a false sentence into the artifact on a run
    where the ladder had just fired. A check whose verdict is typed in advance cannot be
    falsified by the run; that, and not the version number, is what was wrong with it.

    So every string this writes is read back off the run: the stamps come from the file
    before and after, the row counts from the file, the served counts and the notice from
    the running server, the hits from a real query. What it asserts is R23's promise in the
    direction upstream now keeps:

      - the file at the ORIGINAL path is the one being served (in place, not sidelined),
      - nothing was moved aside and nothing deleted,
      - every passage survived, and every vector with it — the expensive half,
      - and the index answers a query afterwards, so "migrated" means "serving".

    Where `--index` is already at this build's version there is nothing to migrate. That is
    reported `observed` with the reason, never `pass`: a ladder that was not walked has not
    been shown to work.
    """
    data_dir = scratch / "migrate"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "search-index.sqlite"
    shutil.copyfile(a.index, target)
    before = _index_facts(target)

    s = start(a, data_dir)
    st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    q = payload(s.call("tools/call", {"name": "zotero_semantic_search", "arguments": {
        "q": queries[0], "mode": "semantic", "limit": limit, "auto_build": False}}))
    s.p.terminate()

    after = _index_facts(target)
    sidelined = sorted(p.name for p in data_dir.glob("search-index.sqlite.incompatible-*")
                       if not p.name.endswith(("-wal", "-shm")))
    hits = len(q.get("hits") or [])
    notice = st.get("storageNotice")
    detail = {
        "index_under_test": str(a.index),
        "schemaVersion_before": before.get("schemaVersion"),
        "schemaVersion_after": after.get("schemaVersion"),
        "served_from_original_path": target.exists(),
        "files_moved_aside": sidelined,
        "passages_before": before.get("passages"),
        "passages_served": st.get("passages"),
        "passages_with_vector_before": before.get("passages_with_vector"),
        "passages_with_vector_after": after.get("passages_with_vector"),
        "vectors_served": st.get("vectors"),
        "embedderId_before": before.get("embedderId"),
        "query": queries[0],
        "hits": hits,
        "storageNotice": notice,
    }
    stamped = before.get("schemaVersion")
    if stamped is None:
        detail["note"] = ("the index carries no schemaVersion stamp, so there is no previous "
                          "version to migrate FROM — this run could not look")
        result = "observed"
    elif stamped == after.get("schemaVersion"):
        detail["note"] = (f"the index was already at schema version {stamped}, which is this "
                          "build's own — the ladder was not walked, so nothing here is evidence "
                          "that it works")
        result = "observed"
    else:
        upgraded = (
            target.exists()
            and not sidelined
            and st.get("passages") == before.get("passages")
            and after.get("passages_with_vector") == before.get("passages_with_vector")
            and hits > 0
            and isinstance(notice, str)
            and "upgraded in place" in notice
        )
        detail["note"] = (f"schema {stamped} → {after.get('schemaVersion')} at the original path; "
                          f"{before.get('passages')} passage(s) and "
                          f"{before.get('passages_with_vector')} vector(s) before, "
                          f"{st.get('passages')} passage(s) and {st.get('vectors')} vector(s) "
                          f"served after, {hits} hit(s) on the probe query")
        result = "pass" if upgraded else "fail"
    return check(
        "R23-previous-schema-migrates-in-place", "R23",
        "an index written under the previous schema version ends up served, in place, "
        "with its vectors preserved and nothing deleted by hand",
        "the previous-version index moved aside, emptied, re-embedded, or unable to answer "
        "a query after the upgrade",
        result, detail)


def _restamp_and_open(a: argparse.Namespace, scratch: Path, stamp: str) -> dict:
    """Copy the index, restamp it, start a server on it, and report what happened to the file."""
    data_dir = scratch / f"schema-{stamp}"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "search-index.sqlite"
    shutil.copyfile(a.index, target)
    before_bytes = target.stat().st_size

    con = sqlite3.connect(target)
    was = con.execute("SELECT value FROM meta WHERE key='schemaVersion'").fetchone()
    con.execute("UPDATE meta SET value=? WHERE key='schemaVersion'", (stamp,))
    con.commit()
    con.close()

    s = start(a, data_dir)
    st = payload(s.call("tools/call", {"name": "zotero_index", "arguments": {"action": "status"}}))
    s.p.terminate()

    sidelined = sorted(p for p in data_dir.glob("search-index.sqlite.incompatible-*")
                       if not p.name.endswith(("-wal", "-shm")))
    return {
        "original_schemaVersion": was[0] if was else None,
        "restamped_to": stamp,
        "sidelined_file": sidelined[0].name if sidelined else None,
        "sidelined_bytes_match_original": bool(sidelined) and sidelined[0].stat().st_size == before_bytes,
        "served_index_is_empty": (st.get("passages") or 0) == 0 and (st.get("documents") or 0) == 0,
        # The stamp the build wrote into the fresh replacement it opened at the original
        # path: this build's own SCHEMA_VERSION, read off disk rather than asserted here,
        # so the artifact says what `0` and `9999` are above and below.
        "build_schema_version": _index_facts(target).get("schemaVersion"),
        "storageNotice": st.get("storageNotice"),
    }


def check_foreign_schema_is_sidelined(a: argparse.Namespace, scratch: Path) -> dict:
    """R23: a schema stamp this build must not write into is read BEFORE the file is opened writable.

    The positive control is the point. A copy of a current index is restamped to a version
    the build cannot serve; the check passes only if the original bytes survive under a
    `.incompatible-` name AND the served index is a fresh empty one. A build that silently
    wrote into the foreign file, or deleted it, fails here.

    BOTH DIRECTIONS are exercised, and WHAT each one now exercises changed at v1.13.0.
    The docstring used to say that stamp `0` stood in for "what every user holds the day
    the current build's SCHEMA_VERSION is incremented". That day has arrived — the build
    is at 2 — and what every user holds is stamp 1, which is now MIGRATED in place, not
    sidelined. So:

      - `0` no longer stands for the ordinary older index. It exercises a ladder GAP:
        `migrationPath(0)` looks for a rung `to: 1`, finds none, and refuses on the
        contiguity rule rather than stepping over a version whose rows nothing claims to
        understand. Still a real path, and still the sideline — but a different one.
      - `9999` exercises the only-forwards refusal: a stamp at or above this build's is
        never walked backwards, because a newer file may hold columns this build cannot
        read at all. This is the half R23 does NOT keep as a migration, and it is why the
        newer direction stays in the check rather than being dropped as the rare case.

    The ordinary older-stamp case — an index one version behind, which now upgrades in
    place — is `check_previous_schema_migrates_in_place` above, and it is where the
    positive control for the ladder lives. Neither check subsumes the other.
    """
    older, newer = _restamp_and_open(a, scratch, "0"), _restamp_and_open(a, scratch, "9999")
    both = [older, newer]
    ok = all(d["sidelined_bytes_match_original"] and d["served_index_is_empty"] for d in both)
    return check(
        "R23-foreign-schema-sidelined", "R23",
        "an index this build must not write into is detected before anything writes to it",
        "the foreign index modified or deleted, or its rows served as if current",
        "pass" if ok else "fail",
        {"older_stamp": older, "newer_stamp": newer,
         "treated_alike": older["served_index_is_empty"] == newer["served_index_is_empty"],
         "what_each_stamp_exercises": (
             "both stamps are foreign to this build, for different reasons: "
             f"{older['restamped_to']} is below its schema version "
             f"({older.get('build_schema_version')}) with no contiguous ladder up to it, "
             f"{newer['restamped_to']} is above it and the ladder is forwards-only. The "
             "ordinary one-version-behind case migrates instead — see "
             "R23-previous-schema-migrates-in-place")})


#: Reciprocal-rank fusion's smoothing constant, upstream's value.
RRF_K = 60


def timing_fields(runs: list[dict]) -> dict:
    """Split the per-query wall times by EXECUTION ORDER, never by magnitude.

    The field this replaces was `sorted(wall_ms)[1:]` — the sorted list minus its
    *minimum*. On a fresh data directory the first query pays the model download
    and the ONNX session start, so it is the largest number in the set: it
    survived into a field labelled warm, while the fastest warm query was the one
    thrown away. Sorting cannot recover which query ran first; only the order the
    runs were appended in can, and that is what this reads.

    Both fields are labelled with what they include, so a run on a fresh data
    directory and a run on a warm one are distinguishable in the artifact: the
    cold figure carries the download on the first, and does not on the second.
    """
    cold = runs[0]["wall_ms"] if runs else None
    warm = [r["wall_ms"] for r in runs[1:]]
    return {
        "cold_ms": cold,
        "warm_ms": warm,
        "timing_note": (
            "cold_ms is the FIRST query in execution order — it carries whatever "
            "one-time cost this process paid on it (model download on a fresh data "
            "directory, ONNX session start always). warm_ms is every query after "
            "the first, in execution order, nothing dropped. Neither field is "
            "sorted: the fastest run is not the warm one, and the slowest is not "
            "necessarily the cold one."),
    }


def _rrf_rank_of(score: object, k: int = RRF_K) -> int | None:
    """The rank whose fusion value equals this score, or None if no rank does.

    Inverted rather than searched over `1..limit`, and the difference is not
    cosmetic: dedup happens AFTER fusion, so a list of `limit` hits can carry a
    rank above `limit` — the v1.13.0 artifact has a five-hit query whose last
    score is `1/66`. A search bounded by the limit would call that a mismatch for
    the same reason the prefix comparison did.
    """
    if isinstance(score, bool) or not isinstance(score, (int, float)) or score <= 0:
        return None
    rank = round(1 / float(score)) - k
    if rank < 1:
        return None
    return rank if round(float(score), 6) == round(1 / (k + rank), 6) else None


def rank_fusion_agreement(runs: list[dict]) -> dict:
    """Match each score against the fusion value for ITS OWN rank, gaps allowed.

    The check this replaces compared the returned scores against a *contiguous
    prefix* of the series `1/(60+rank)`. Item-level deduplication in the query
    path leaves gaps in the ranks, so a query whose hits skip a rank failed strict
    prefix equality even though every individual score is exactly the fusion value
    for its own rank — the counter read zero for a reason that was the check's,
    not the target's.

    A hit matches when some rank in 1..limit fuses to its score. A *query* counts
    only when every one of its hits matches AND the ranks ascend, since a fused
    list is ordered by score; a descending or repeated rank is not a fusion
    ordering. A query that returned nothing demonstrates nothing and is not
    counted.

    Reports how many hits were compared, so the artifact says what the count is
    out of rather than leaving a bare number the reader cannot size.
    """
    compared = matched = queries_ok = 0
    for r in runs:
        scores = r.get("scores") or []
        ranks = [_rrf_rank_of(x) for x in scores]
        compared += len(scores)
        matched += sum(1 for x in ranks if x is not None)
        ordered = all(a < b for a, b in zip(ranks, ranks[1:])) if None not in ranks else False
        if scores and None not in ranks and ordered:
            queries_ok += 1
    return {
        "hits_compared": compared,
        "hits_matching_own_rank": matched,
        "queries_all_hits_rank_shaped": queries_ok,
        "rank_fusion_note": (
            f"each score is compared against 1/({RRF_K}+rank) for its own rank, not "
            "against a contiguous prefix of the series: item-level deduplication "
            "leaves gaps in the ranks, and a gap is not a mismatch. A query counts "
            "only when every hit matches and the ranks ascend."),
    }


def check_query_answers(s: Server, queries: list[str], limit: int) -> dict:
    """R6/R7: a query answers, in what time, and whether the score carries magnitude."""
    runs = []
    for q in queries:
        t = time.perf_counter()
        r = payload(s.call("tools/call", {"name": "zotero_semantic_search", "arguments": {
            "q": q, "mode": "semantic", "limit": limit, "auto_build": False}}))
        ms = round((time.perf_counter() - t) * 1000, 1)
        hits = r.get("hits") or []
        # Keys, not titles: a committed artifact names a library document by its item
        # key and never by its title or filename (ruling 2026-08-31, DECISIONS.md).
        runs.append({"q": q, "wall_ms": ms, "hits": len(hits),
                     "scores": [h.get("score") for h in hits],
                     "keys": [h.get("itemKey") or h.get("key") for h in hits]})
    answered = [r for r in runs if r["hits"] > 0]
    # RRF over one list gives 1/(60+rank) exactly; a similarity would not.
    detail = {"runs": runs}
    detail.update(timing_fields(runs))
    detail.update(rank_fusion_agreement(runs))
    return check(
        "R6-query-answers", "R6", "a query returns something usable, warm, within the budget",
        "a query returning no hits on a populated index, or no run completing",
        "pass" if len(answered) == len(runs) and runs else "fail",
        {**detail,
         "score_note": ("a score equal to 1/(60+rank) is reciprocal-rank fusion over a single "
                        "list — a relabelled rank, carrying no similarity magnitude, so a caller "
                        "cannot threshold it to mean 'nothing good was found'")})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="path to the upstream MCP entrypoint")
    ap.add_argument("--data-dir", required=True, help="data dir holding an index to query")
    ap.add_argument("--index", help="a CURRENT-schema index, copied for the schema check")
    ap.add_argument("--transformers-path", default="")
    ap.add_argument("--zotero-data-dir", default="")
    ap.add_argument("--queries", nargs="*", default=[
        "carbon tax and household energy spending",
        "permafrost thaw feedback",
        "integrated assessment model discount rate",
    ])
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    data_dir = Path(a.data_dir)
    checks = []
    # Sampled BEFORE the server starts, because the model cache check downstream needs to
    # tell a cache this run created from one that was already sitting here.
    models_present_before = (data_dir / "models").is_dir()
    s = start(a, data_dir)
    server_info = None
    try:
        local = check_local_by_default(s)
        checks.append(local)
        # The query check runs BEFORE the model-cache check, and the order is the point:
        # the weights are fetched on the first text this process embeds, so a check that
        # looks earlier can only ever report that it could not look.
        queried = check_query_answers(s, a.queries, a.limit)
        checks.append(queried)
        checks.append(check_model_stays_in_data_dir(
            data_dir, models_present_before,
            bool(local["detail"].get("embedderActive")),
            len(queried["detail"].get("runs") or [])))
    finally:
        s.p.terminate()

    if a.index:
        with tempfile.TemporaryDirectory(prefix="zoteus-smoke-") as tmp:
            checks.append(check_previous_schema_migrates_in_place(
                a, Path(tmp), a.queries, a.limit))
            checks.append(check_foreign_schema_is_sidelined(a, Path(tmp)))

    version = subprocess.run(
        ["node", "-e", "console.log(require('./package.json').version)"],
        cwd=Path(a.server).resolve().parent.parent, capture_output=True, text=True).stdout.strip()

    out = {
        "probe": "smoke the reviewed upstream baseline against a real Zotero library, by requirement",
        "not_a_test_suite": (
            "each check exercises ONE clause of one requirement, once, against one library. It "
            "earns a README row the word 'measured' rather than 'code' — something ran — and "
            "nothing stronger."),
        "upstream_version": version or None,
        "server_info": server_info,
        "date": time.strftime("%Y-%m-%d"),
        "data_dir": str(data_dir),
        "checks": checks,
        "summary": {r: sum(1 for c in checks if c["result"] == r)
                    for r in ("pass", "fail", "observed")},
    }
    Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    for c in checks:
        log.info("%-32s %-8s %s", c["check"], c["result"].upper(), c["clause"])
    log.info("wrote %s", a.output)
    if out["summary"]["fail"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
