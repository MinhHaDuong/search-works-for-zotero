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
