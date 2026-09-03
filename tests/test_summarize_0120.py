"""The 0120 assembler's parsing, where a wrong answer would look like a measurement.

`summarize_0120.py` does no measuring: it reads the `RESULT {...}` lines
`bench/run_build.py` writes and arranges them. So the failure to guard against is not a
bad number but a *plausible* one — a run that never finished read as a build that cost
nothing, a WAL folded into the main file so the steady state looks larger than it is, or
a metadata count that silently absorbs whatever the status object forgot to report.

The real logs are not mocked away where they exist: the fixtures below are the shape
`run_build.py` actually emits, copied from a run, because a fixture invented from the
docstring tests the docstring.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("s0120", REPO / "bench" / "summarize_0120.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s = load()

#: The shape run_build.py emits, trimmed to the keys the assembler reads.
RESULT = {
    "elapsed_s": 140.3,
    "peak_rss_kb": 425320,
    "status": {
        "documents": 19966, "vectors": 0, "items": 300, "passages": 19966,
        "fulltextPassages": 19571, "ownWordsPassages": 36, "fulltextItems": 258,
        "embedder": "none (keyword-only)", "state": "done", "itemsAvailable": 7541,
    },
    "files": {"search-index.sqlite": 42975232, "search-index.sqlite-wal": 32964152,
              "search-index.sqlite-shm": 65536, "update-check.json": 122},
}


def write_log(path: Path, results: list[dict], noise: bool = True) -> Path:
    lines = []
    if noise:
        lines += ["[server] [zoteus] INFO Zoteus MCP server started on stdio.",
                  "[   10s peak 0.16 GB] {\"documents\": 395}"]
    lines += [f"RESULT {json.dumps(r)}" for r in results]
    path.write_text("\n".join(lines) + "\n")
    return path


def test_a_run_that_never_finished_raises_rather_than_reading_as_free(tmp_path):
    """The whole point of the guard: no RESULT must not become a build of zero cost.

    This is the negative control. Returning {} here would put a keyword build costing
    0 s, 0 kB and 0 bytes into an artifact whose entire subject is what that build costs.
    """
    log = write_log(tmp_path / "wedged.log", [])
    with pytest.raises(RuntimeError, match="no RESULT"):
        s.last_result(log)


def test_the_last_result_wins_when_a_log_carries_several(tmp_path):
    """A resumed or re-driven run appends; the final line is the one that describes it."""
    first = json.loads(json.dumps(RESULT))
    first["elapsed_s"] = 11.1
    log = write_log(tmp_path / "twice.log", [first, RESULT])
    assert s.last_result(log)["elapsed_s"] == 140.3


def test_disk_keeps_the_wal_beside_the_main_file(tmp_path):
    """Folding the WAL in would overstate the steady state; dropping it understates the build."""
    d = s.disk(RESULT["files"])
    assert d["sqlite_bytes"] == 42975232
    assert d["wal_bytes"] == 32964152
    assert d["total_bytes"] == 42975232 + 32964152 + 65536
    # update-check.json is not index bytes and must not be counted as any of them.
    assert d["total_bytes"] < sum(RESULT["files"].values()) + 1
    assert 122 not in (d["sqlite_bytes"], d["wal_bytes"], d["shm_bytes"])


def test_metadata_passages_are_what_the_other_two_do_not_claim(tmp_path):
    """The platform index holds no metadata, so this count is the bound action 1 reports."""
    log = write_log(tmp_path / "one.log", [RESULT])
    a = s.arm(log)
    assert a["metadata_passages"] == 19966 - 19571 - 36
    assert a["fulltext_passages"] + a["own_words_passages"] + a["metadata_passages"] == a["passages"]


def test_a_keyword_arm_carries_no_vectors(tmp_path):
    """A silently-enabled embedder would change every figure in the artifact.

    `--embeddings off` is run_build.py's default, so nothing in the command line says
    keyword-only out loud; the status object is where it is legible.
    """
    log = write_log(tmp_path / "one.log", [RESULT])
    a = s.arm(log)
    assert a["vectors"] == 0
    assert a["embedder"] == "none (keyword-only)"


def test_the_fit_is_arithmetic_and_not_a_shape(tmp_path):
    """Numbers chosen so the answer is exact and checkable by hand.

    Two points 1 000 passages apart, 10 s apart: 10 ms per passage. The small arm then
    spends 1 000 x 10 ms = 10 s of its 40 s on passages, so the fixed term is 30 s, and
    a 5 000-passage library predicts 30 + 50 = 80 s. Measured 100 s makes the error
    -20 %. Every one of those is a value a wrong sign or a dropped unit changes.
    """
    lo = {"passages": 1000, "elapsed_s": 40.0, "disk": {"sqlite_bytes": 2_000_000}}
    hi = {"passages": 2000, "elapsed_s": 50.0, "disk": {"sqlite_bytes": 3_000_000}}
    full = {"passages": 5000, "elapsed_s": 100.0}
    fit = s.two_point_fit(lo, hi, full)
    assert fit["marginal_ms_per_passage"] == 10.0
    assert fit["fixed_s_per_build"] == 30.0
    assert fit["marginal_bytes_per_passage"] == 1000.0
    assert fit["predicted_full_library_s"] == 80.0
    assert fit["measured_full_library_s"] == 100.0
    assert fit["prediction_error_pct"] == -20.0


def test_the_fit_refuses_two_points_that_are_one(tmp_path):
    """Equal passage counts divide by zero; a raise beats an inf travelling into prose."""
    same = {"passages": 1000, "elapsed_s": 40.0, "disk": {"sqlite_bytes": 1}}
    with pytest.raises(RuntimeError, match="no passage difference"):
        s.two_point_fit(same, dict(same, elapsed_s=50.0), {"passages": 5000, "elapsed_s": 1.0})


@pytest.mark.integration
def test_decompose_splits_the_keyword_half_from_the_store(tmp_path):
    """A real SQLite file, because the split is a dbstat query and not a dict lookup.

    The figure the recommendation turns on is which bytes the platform index could
    stand in for, so what must not drift is the FTS_TABLES membership: a shadow table
    dropped from that set silently moves bytes from the keyword half to the store and
    makes the platform look more attractive than it is.
    """
    db = tmp_path / "idx.sqlite"
    subprocess.run(
        ["sqlite3", str(db),
         "CREATE TABLE passages(pid INTEGER PRIMARY KEY, text TEXT);"
         "CREATE VIRTUAL TABLE passages_fts USING fts5(text, content='passages',"
         " content_rowid='pid');"
         "INSERT INTO passages(text) SELECT hex(randomblob(400)) FROM generate_series(1,400);"
         "INSERT INTO passages_fts(passages_fts) VALUES('rebuild');"],
        check=True, capture_output=True)
    out = s.decompose(db)
    assert out["total_bytes"] == sum(out["bytes_by_object"].values())
    assert out["keyword_index_bytes"] + out["stored_text_and_addressing_bytes"] == out["total_bytes"]
    # The shadow tables must actually be found, or the "keyword half" is zero and the
    # store looks like the whole file — the failure this test exists to catch.
    assert out["keyword_index_bytes"] > 0
    assert "passages_fts_data" in out["bytes_by_object"]
    assert round(out["keyword_index_share_pct"] + out["stored_text_share_pct"], 1) == 100.0


@pytest.mark.integration
def test_decompose_counts_every_fts_shadow_table_it_declares(tmp_path):
    """FTS_TABLES is the load-bearing constant; assert it against what FTS5 really makes."""
    db = tmp_path / "idx2.sqlite"
    subprocess.run(
        ["sqlite3", str(db),
         "CREATE TABLE passages(pid INTEGER PRIMARY KEY, text TEXT);"
         "CREATE VIRTUAL TABLE passages_fts USING fts5(text, content='passages',"
         " content_rowid='pid');"
         "INSERT INTO passages(text) VALUES('alpha beta gamma');"
         "INSERT INTO passages_fts(passages_fts) VALUES('rebuild');"],
        check=True, capture_output=True)
    made = subprocess.run(
        ["sqlite3", str(db),
         "select name from sqlite_master where type='table' and name like 'passages_fts%';"],
        check=True, capture_output=True, text=True).stdout.split()
    assert set(made) <= set(s.FTS_TABLES) | {"passages_fts"}, (
        f"FTS5 made a shadow table the split does not know about: {set(made) - set(s.FTS_TABLES)}")


def test_peak_trajectory_reads_when_the_peak_arrived(tmp_path):
    """A peak that arrives early and holds is a different claim from one that spikes late."""
    log = tmp_path / "poll.log"
    log.write_text(
        "[     5s peak 0.16 GB] {}\n"
        "[   100s peak 0.16 GB] {}\n"
        "[   200s peak 0.71 GB] {}\n"
        "[   300s peak 0.71 GB] {}\n"
        "RESULT {}\n")
    t = s.peak_trajectory(log)
    assert t["opening_gb"] == 0.16
    assert t["peak_gb_as_the_driver_printed_it"] == 0.71
    assert t["first_reached_at_s"] == 200
    assert t["held_for_s"] == 100
    assert t["polls"] == 4


def test_peak_trajectory_raises_on_a_log_with_no_polls(tmp_path):
    """Same negative control as last_result: absence must not read as a flat zero."""
    log = tmp_path / "silent.log"
    log.write_text("RESULT {}\n")
    with pytest.raises(RuntimeError, match="no poll lines"):
        s.peak_trajectory(log)


def test_the_shipped_artifact_matches_its_own_logs():
    """The committed artifact is re-derivable from the logs it names, or it is folklore.

    Skipped rather than failed where the run logs are absent: they live under the data
    volume, not in the repo, so a clean-room checkout cannot re-derive them and must not
    be told it has a broken test.
    """
    out = REPO / "bench" / "results" / "0120-keyword-build" / "keyword-build-cost.json"
    if not out.exists():
        pytest.skip("artifact not built in this checkout")
    art = json.loads(out.read_text())
    # The quantum is the instrument's resolution, and a coarse one makes elapsed_s a
    # reading of the poll rather than of the build: at --poll 20 the 300- and 1200-item
    # runs both returned 140,3 s. Ten seconds is under 3 % of the full-library figure.
    assert art["under_measurement"]["poll_quantum_s"] <= 10
    full = art["ours"]["full_library"]
    log = Path(full["log"])
    if not log.exists():
        pytest.skip(f"run log {log} is not on this machine")
    live = s.arm(log)
    assert live["elapsed_s"] == full["elapsed_s"]
    assert live["passages"] == full["passages"]
    assert live["peak_rss_kb"] == full["peak_rss_kb"]
    assert live["disk"] == full["disk"]
