"""Both control arms of the 0793 stall probe, and the sampler's own two controls.

Ticket 0793 asks one question about the AR6 plateau -- slow tail or wedged --
and nothing here answers it: the AR6 document is the author's, 242 MB, not in
this repository and not redistributable. What IS testable offline is the
instrument, and the instrument is worthless untested in both directions.

THE TWO ARMS. `verification/incidents/0793-2026-09-15-ar6-stall.json` carries
them both, which is why nothing is fabricated here:

    elapsed 148238   sinceProgressMS   5818   progress 69   <- healthy
    elapsed 208276   sinceProgressMS   5200   progress 88   <- healthy
    elapsed 268299   sinceProgressMS  52637   progress 90   <- plateau
    elapsed 328314   sinceProgressMS 112652   progress 90   <- plateau
    elapsed 388386   sinceProgressMS 172724   progress 90   <- plateau

A predicate only ever tested against the plateau cannot be trusted when it
later reports "not wedged": that reading would be indistinguishable from a
predicate that fires on everything, or on nothing it was pointed at. The same
function with the same thresholds must go quiet on the first two beats and
loud on the last three, and both directions are asserted below.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bench"))

from sdt_stall_probe import (  # noqa: E402
    DEFAULT_QUIET_MS,
    IO_FLOOR_BYTES,
    ProbeError,
    analyse_heartbeats,
    analyse_journal_file,
    build_record,
    cpu_between,
    snapshot,
    stall_verdict,
    summarize_cpu,
    worker_cpu,
)

INCIDENT = REPO / "verification/incidents/0793-2026-09-15-ar6-stall.json"


def records() -> list[dict]:
    return json.loads(INCIDENT.read_text(encoding="utf-8"))["records"]


def healthy_arm() -> list[dict]:
    """Everything up to and including the second heartbeat (progress 88)."""
    out = []
    beats = 0
    for record in records():
        out.append(record)
        if record.get("kind") == "heartbeat":
            beats += 1
            if beats == 2:
                return out
    raise AssertionError("fixture no longer carries two healthy heartbeats")


# --------------------------------------------------------------------------
# arm 1: the predicate is SILENT while the worker is advancing
# --------------------------------------------------------------------------

def test_healthy_arm_is_silent():
    reading = analyse_heartbeats(healthy_arm())
    assert reading["plateau"] is False
    assert reading["reading"] == "advancing"
    assert reading["beats"] == 2
    assert reading["quietMS"] == 5200
    assert reading["quietBeats"] == 0
    assert reading["progress"] == 88


def test_healthy_arm_sees_the_ticks_that_the_delta_rule_infers():
    # The delta rule says a tick landed between the two beats; the progress
    # records in the same window say the same thing, independently.
    reading = analyse_heartbeats(healthy_arm())
    assert reading["ticksSinceFirstBeat"] > 0


# --------------------------------------------------------------------------
# arm 2: the predicate FIRES on the plateau
# --------------------------------------------------------------------------

def test_plateau_arm_fires():
    reading = analyse_heartbeats(records())
    assert reading["plateau"] is True
    assert reading["reading"] == "plateau"
    assert reading["beats"] == 5
    assert reading["quietMS"] == 172724
    assert reading["quietBeats"] == 2
    assert reading["corroborated"] is True
    assert reading["progress"] == 90
    assert reading["phase"] == "extracting"
    # No progress record at all inside the quiet window -- the second,
    # independent reading of the same silence.
    assert reading["ticksInQuietWindow"] == 0


def test_one_predicate_one_threshold_two_answers():
    """The control that makes either arm mean anything: same call, same knobs."""
    knobs = {"quiet_ms": DEFAULT_QUIET_MS, "slack_ms": 2000, "min_quiet_beats": 2}
    assert analyse_heartbeats(healthy_arm(), **knobs)["plateau"] is False
    assert analyse_heartbeats(records(), **knobs)["plateau"] is True


def test_plateau_grows_by_exactly_one_heartbeat_interval():
    """What 'no ticks at all' looks like in the field the sitter reports."""
    reading = analyse_heartbeats(records())
    quiet = [beat["sinceProgressMS"] for beat in reading["quietSpan"]]
    assert quiet == [112652, 172724]
    assert quiet[1] - quiet[0] == pytest.approx(60000, abs=200)


# --------------------------------------------------------------------------
# the third answer: "I could not look" is not "all clear"
# --------------------------------------------------------------------------

def test_no_heartbeats_is_unknown_not_silent():
    reading = analyse_heartbeats([])
    assert reading["plateau"] is False
    assert reading["reading"] == "unknown"
    assert "no heartbeat" in reading["why"]


def test_null_since_progress_is_unknown_not_silent():
    beat = {"at": 1, "kind": "heartbeat", "id": 7, "phase": "census",
            "progress": None, "elapsedMS": None, "sinceProgressMS": None}
    reading = analyse_heartbeats([beat])
    assert reading["plateau"] is False
    assert reading["reading"] == "unknown"


def test_partial_quiet_below_the_threshold_does_not_fire():
    made = [
        {"at": 0, "kind": "heartbeat", "id": 1, "phase": "extracting",
         "progress": 90, "sinceProgressMS": 3000},
        {"at": 60000, "kind": "heartbeat", "id": 1, "phase": "extracting",
         "progress": 90, "sinceProgressMS": 63000},
    ]
    reading = analyse_heartbeats(made)
    assert reading["quietBeats"] == 1
    assert reading["plateau"] is False  # 63 s < the 120 s threshold


# --------------------------------------------------------------------------
# the verdict: a plateau alone never names a cause
# --------------------------------------------------------------------------

def test_verdict_without_cpu_is_undetermined():
    verdict = stall_verdict(analyse_heartbeats(records()), cpu=None)
    assert verdict["verdict"] == "undetermined"
    assert "CPU" in verdict["why"]


def cpu(worker, process, *, read_bytes=0, rchar_bytes=0, peak=None):
    return {"workerPercent": worker, "processPercent": process,
            "maxProcessPercent": process if peak is None else peak,
            "maxTopThreadPercent": worker, "intervals": 10,
            "intervalsAboveSlow": 0 if peak is None else 1,
            "readBytes": read_bytes, "rcharBytes": rchar_bytes,
            "tid": 4242, "comm": "DOM Worker"}


def test_verdict_wedged_needs_a_flat_worker():
    verdict = stall_verdict(analyse_heartbeats(records()), cpu=cpu(0.2, 0.4))
    assert verdict["verdict"] == "wedged"


def test_verdict_slow_tail_needs_a_busy_worker():
    verdict = stall_verdict(analyse_heartbeats(records()), cpu=cpu(97.0, 104.0))
    assert verdict["verdict"] == "slow-tail"


def test_verdict_between_the_bands_refuses_to_choose():
    verdict = stall_verdict(analyse_heartbeats(records()), cpu=cpu(5.0, 6.0))
    assert verdict["verdict"] == "undetermined"


def test_verdict_on_the_healthy_arm_is_advancing():
    verdict = stall_verdict(analyse_heartbeats(healthy_arm()), cpu=cpu(0.0, 0.1))
    # A flat CPU while progress still ticks is not a wedge; the plateau is the
    # precondition, and without it no CPU reading names anything.
    assert verdict["verdict"] == "advancing"


# --- the three ways a flat worker thread is NOT a wedge --------------------

def test_a_busy_process_with_a_flat_worker_is_not_a_wedge():
    """Thread rotation: the roster lost the busy thread, not the process."""
    verdict = stall_verdict(analyse_heartbeats(records()), cpu=cpu(0.0, 99.7))
    assert verdict["verdict"] == "undetermined"
    assert "heuristic" in verdict["why"]


def test_a_single_noisy_interval_does_not_veto_a_wedge():
    """The verdict is decided on the sustained reading, not on a peak.

    Deliberate reversal of round 1's suggestion. Over 480 five-second intervals
    of a live desktop app one unrelated burst is a near-certainty, so a
    peak-based veto would make `wedged` nearly unobservable -- a common false
    negative traded for a rare false positive, on the exact question 0793 asks.
    The peaks are reported so a reader can see what the average smoothed over.
    """
    verdict = stall_verdict(analyse_heartbeats(records()),
                            cpu=cpu(0.1, 0.9, peak=64.0))
    assert verdict["verdict"] == "wedged"
    assert "64.0 %" in verdict["why"]       # the peak is named, not hidden
    assert "1 of 10 interval(s)" in verdict["why"]


def test_a_sustained_busy_process_with_a_flat_worker_is_not_a_wedge():
    verdict = stall_verdict(analyse_heartbeats(records()),
                            cpu=cpu(0.0, 42.0, peak=99.7))
    assert verdict["verdict"] == "undetermined"


def test_io_bound_work_is_not_a_wedge():
    verdict = stall_verdict(analyse_heartbeats(records()),
                            cpu=cpu(0.2, 1.0, read_bytes=6_400_000,
                                    rchar_bytes=6_400_000))
    assert verdict["verdict"] == "undetermined"
    assert "I/O-bound" in verdict["why"]


def test_cached_reads_are_work_even_when_the_block_layer_is_flat():
    """`read_bytes` is the block layer; already-cached pages move only `rchar`.

    A worker pulling cached pages of a 242 MB PDF -- the case IO_FLOOR_BYTES's
    own comment names -- leaves `read_bytes` at zero. Reading only the block
    layer returned `wedged` on a process doing 7.9 MB of real reads.
    """
    verdict = stall_verdict(analyse_heartbeats(records()),
                            cpu=cpu(0.2, 0.4, read_bytes=0,
                                    rchar_bytes=7_900_000))
    assert verdict["verdict"] == "undetermined"
    assert "syscall layer" in verdict["why"]


def test_unreadable_io_counters_refuse_a_wedge_verdict():
    """An all-clear on a channel that was never consulted is not a check."""
    for missing in ({"read_bytes": None}, {"rchar_bytes": None}):
        verdict = stall_verdict(analyse_heartbeats(records()),
                                cpu=cpu(0.2, 0.4, **missing))
        assert verdict["verdict"] == "undetermined"
        assert "never consulted" in verdict["why"]


def test_io_noise_below_the_floor_does_not_veto_a_wedge():
    verdict = stall_verdict(analyse_heartbeats(records()),
                            cpu=cpu(0.2, 0.4, read_bytes=4096,
                                    rchar_bytes=8192))
    assert verdict["verdict"] == "wedged"


# --- the exact values of every threshold that decides something ------------

def test_the_plateau_threshold_is_inclusive_at_its_exact_value():
    """Off-by-one at the boundary is silent; these two assertions are not."""
    def beat(since):
        return [{"at": since, "kind": "heartbeat", "id": 1,
                 "phase": "extracting", "progress": 90,
                 "sinceProgressMS": since}]
    assert analyse_heartbeats(beat(DEFAULT_QUIET_MS))["plateau"] is True
    assert analyse_heartbeats(beat(DEFAULT_QUIET_MS - 1))["plateau"] is False


def test_the_slow_band_is_inclusive_at_its_exact_value():
    plateau = analyse_heartbeats(records())
    assert stall_verdict(plateau, cpu(10.0, 10.0))["verdict"] == "slow-tail"
    assert stall_verdict(plateau, cpu(9.9, 9.9))["verdict"] != "slow-tail"


def test_the_wedge_band_is_inclusive_at_its_exact_value():
    plateau = analyse_heartbeats(records())
    assert stall_verdict(plateau, cpu(2.0, 2.0))["verdict"] == "wedged"
    assert stall_verdict(plateau, cpu(2.1, 2.1))["verdict"] == "undetermined"


def test_the_io_floor_is_inclusive_at_its_exact_value():
    plateau = analyse_heartbeats(records())
    for field in ("read_bytes", "rchar_bytes"):
        at_floor = cpu(0.2, 0.4, **{field: IO_FLOOR_BYTES})
        below = cpu(0.2, 0.4, **{field: IO_FLOOR_BYTES - 1})
        assert stall_verdict(plateau, at_floor)["verdict"] == "undetermined"
        assert stall_verdict(plateau, below)["verdict"] == "wedged"


def test_the_contradiction_guard_is_inclusive_at_its_exact_value():
    """The guard round 2 found unguarded: `process >= slow_cpu_pct` at :560."""
    plateau = analyse_heartbeats(records())
    assert stall_verdict(plateau, cpu(0.1, 10.0))["verdict"] == "undetermined"
    assert stall_verdict(plateau, cpu(0.1, 9.9))["verdict"] == "wedged"


# --- shapes that must degrade rather than raise ----------------------------

def test_a_heartbeat_with_no_timestamp_degrades_to_unknown():
    beat = {"kind": "heartbeat", "id": 1, "phase": "extracting",
            "progress": 90, "sinceProgressMS": None, "at": None}
    reading = analyse_heartbeats([beat, dict(beat)])
    assert reading["reading"] == "unknown"
    assert reading["ticksSinceFirstBeat"] is None


def test_a_bare_record_array_is_a_journal_too(tmp_path):
    path = tmp_path / "bare.json"
    path.write_text(json.dumps(records()), encoding="utf-8")
    assert analyse_journal_file(path)["plateau"] is True


def test_a_journal_that_is_neither_shape_is_refused(tmp_path):
    path = tmp_path / "odd.json"
    path.write_text("42", encoding="utf-8")
    with pytest.raises(ProbeError):
        analyse_journal_file(path)


def test_a_null_records_key_reads_as_unknown_not_as_a_crash(tmp_path):
    """The shape a truncated or half-written journal takes."""
    path = tmp_path / "null.json"
    path.write_text('{"records": null}', encoding="utf-8")
    assert analyse_journal_file(path)["reading"] == "unknown"


def test_a_wrong_typed_records_key_is_refused(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text('{"records": {"a": 1}}', encoding="utf-8")
    with pytest.raises(ProbeError):
        analyse_journal_file(path)


def test_a_wrong_typed_timestamp_degrades_to_unknown():
    beat = {"kind": "heartbeat", "id": 1, "phase": "extracting",
            "progress": 90, "sinceProgressMS": "172724", "at": "not-a-number"}
    reading = analyse_heartbeats([beat, dict(beat)])
    assert reading["reading"] == "unknown"
    assert reading["quietBeats"] == 0


# --------------------------------------------------------------------------
# the sampler's own two controls: spinning and sleeping, offline
# --------------------------------------------------------------------------

BUSY = "x = 0\nwhile True:\n    x += 1\n"
IDLE = "import time\ntime.sleep(60)\n"


def _sample(code: str, seconds: float = 0.8) -> dict:
    proc = subprocess.Popen([sys.executable, "-c", code],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.15)  # let the interpreter reach the loop
        before = snapshot(proc.pid)
        time.sleep(seconds)
        after = snapshot(proc.pid)
        return cpu_between(before, after)
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.integration
def test_sampler_separates_spinning_from_idle():
    """The sampler is validated before it is ever pointed at Zotero."""
    busy = _sample(BUSY)
    idle = _sample(IDLE)
    assert busy["processPercent"] > 50.0, busy
    assert idle["processPercent"] < 5.0, idle
    # And the separation is not an artefact of one noisy run.
    assert busy["processPercent"] > idle["processPercent"] + 40.0


@pytest.mark.integration
def test_sampler_is_per_thread_so_a_worker_is_separable():
    busy = _sample(BUSY)
    assert busy["threads"], busy
    assert busy["topThread"]["percent"] > 50.0
    for thread in busy["threads"]:
        assert "tid" in thread and "comm" in thread and "percent" in thread


@pytest.mark.integration
def test_sampler_reports_rss_and_read_io():
    proc = subprocess.Popen([sys.executable, "-c", IDLE],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.15)
        shot = snapshot(proc.pid)
    finally:
        proc.kill()
        proc.wait()
    assert shot["rssBytes"] > 1_000_000
    # /proc/<pid>/io can be unreadable under a hardened kernel; the sampler
    # says so rather than reporting a zero that reads like "no I/O".
    assert "io" in shot


def test_stat_field_offsets_are_utime_and_stime():
    """The pure-tier twin of the busy-loop control.

    The busy-loop test above catches a wrong offset, but it is marked
    `integration` and a fast tier that drops that marker would drop the only
    guard over the one arithmetic error that turns this probe into a liar.
    proc(5) field 14 is utime and field 15 is stime; with pid at 0 and comm at
    1 those are offsets 13 and 14. Reading 11 and 12 gets majflt and cmajflt --
    two counters that are zero on a spinning process, which is why that bug
    reported 0.0 % instead of merely a wrong number.
    """
    from sdt_stall_probe import _STIME, _UTIME, _stat_fields

    line = "1234 (a name with spaces) R " + " ".join(str(n) for n in range(4, 30))
    fields = _stat_fields(line)
    assert (fields[11], fields[12]) == ("12", "13")  # majflt, cmajflt
    assert (fields[_UTIME], fields[_STIME]) == ("14", "15")


def test_a_thread_born_inside_the_window_keeps_its_cpu():
    """Zotero rotates workers; dropping the newcomer lost the busy thread.

    Skipping a tid absent from the first snapshot left `topThread` pointing at
    an idle helper while the process ran at full tilt — and the verdict that
    followed was a confident `wedged` on a saturated process.
    """
    ticks = 100
    before = {"pid": 1, "comm": "z", "at": 0, "monotonic": 0.0,
              "cpuJiffies": 0, "rssBytes": 1, "io": None, "clockTicks": ticks,
              "threads": {"11": {"tid": 11, "comm": "idle", "cpuJiffies": 0,
                                 "io": None}}}
    after = {**before, "monotonic": 1.0, "cpuJiffies": 100,
             "threads": {"11": {"tid": 11, "comm": "idle", "cpuJiffies": 0,
                                "io": None},
                         "22": {"tid": 22, "comm": "worker", "cpuJiffies": 100,
                                "io": None}}}
    rates = cpu_between(before, after)
    assert rates["processPercent"] == pytest.approx(100.0)
    assert rates["topThread"]["tid"] == 22
    assert rates["topThread"]["percent"] == pytest.approx(100.0)
    assert rates["topThread"]["bornInWindow"] is True


def test_a_thread_that_exited_inside_the_window_is_counted():
    ticks = 100
    before = {"pid": 1, "comm": "z", "at": 0, "monotonic": 0.0,
              "cpuJiffies": 0, "rssBytes": 1, "io": None, "clockTicks": ticks,
              "threads": {"11": {"tid": 11, "comm": "gone", "cpuJiffies": 0,
                                 "io": None},
                          "12": {"tid": 12, "comm": "stays", "cpuJiffies": 0,
                                 "io": None}}}
    after = {**before, "monotonic": 1.0, "cpuJiffies": 100,
             "threads": {"12": {"tid": 12, "comm": "stays", "cpuJiffies": 0,
                                "io": None}}}
    rates = cpu_between(before, after)
    assert rates["threadsExitedInWindow"] == 1
    # Its CPU is unrecoverable per thread but still in the process total, and
    # that asymmetry is what stall_verdict's contradiction guard exists for.
    assert rates["processPercent"] == pytest.approx(100.0)
    assert rates["topThread"]["percent"] == pytest.approx(0.0)


def test_sampler_refuses_a_pid_that_is_not_there():
    with pytest.raises(ProbeError):
        snapshot(2 ** 22 + 7)


def test_the_worker_threads_own_io_reaches_the_verdict():
    """It decides nothing today; the AR6 run is what it is there to settle.

    The process-wide veto may be unreachable over a 2 400 s window if ambient
    housekeeping clears the floor by itself (see IO_FLOOR_BYTES). Carrying the
    worker thread's own share is what lets ONE run answer that, instead of
    tuning the floor now on no data — and it must actually reach a reader, or
    it is another field computed and never read.
    """
    summary = {
        "intervals": 2, "maxProcessPercent": 1.0, "maxTopThreadPercent": 0.2,
        "intervalsAboveSlow": 0, "threadsExitedInWindow": 0,
        "overall": {"processPercent": 1.0, "readBytes": 2_000_000,
                    "rcharBytes": 2_000_000},
        "overallTopThread": {"tid": 7, "comm": "DOM Worker", "percent": 0.2,
                             "readBytes": 0, "rcharBytes": 0},
    }
    reading = worker_cpu(summary)
    assert reading["workerReadBytes"] == 0
    assert reading["workerRcharBytes"] == 0
    verdict = stall_verdict(analyse_heartbeats(records()), reading)
    assert verdict["verdict"] == "undetermined"
    assert "PROCESS-WIDE" in verdict["why"]
    assert "thread-scoped" in verdict["why"]


def test_the_help_text_states_the_rule_the_code_implements():
    """`--help` prints the module docstring verbatim (description=__doc__)."""
    import sdt_stall_probe

    doc = sdt_stall_probe.__doc__
    assert "WINDOW AVERAGE, not the peak" in doc
    assert "rchar" in doc and "already-cached" in doc
    assert "IO_FLOOR_BYTES" in doc


@pytest.mark.integration
def test_summarize_cpu_folds_a_series():
    proc = subprocess.Popen([sys.executable, "-c", BUSY],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.15)
        series = []
        for _ in range(3):
            series.append(snapshot(proc.pid))
            time.sleep(0.3)
    finally:
        proc.kill()
        proc.wait()
    folded = summarize_cpu(series)
    assert folded["intervals"] == 2
    assert folded["overall"]["processPercent"] > 50.0
    assert folded["maxProcessPercent"] > 50.0


# --------------------------------------------------------------------------
# the record shape: sitter_acceptance.py's phase dict, extended, not replaced
# --------------------------------------------------------------------------

def test_record_shape_follows_the_acceptance_pattern():
    shape = json.loads((REPO / "verification/acceptance/0.4.15-2026-09-14.json")
                       .read_text(encoding="utf-8"))
    record = build_record(
        ok=True,
        phases={"heartbeats": analyse_heartbeats(records())},
        run={"version": "0.4.15", "zotero": "10.0.2", "host": "padme"},
    )
    assert set(shape) <= set(record)
    assert record["phases"]["heartbeats"]["plateau"] is True
    assert record["_run"]["script"] == "bench/sdt_stall_probe.py"
    assert record["_run"]["when"].endswith("Z")
    json.dumps(record)  # the record is serialisable, which is the point of it


def test_the_committed_incident_still_carries_both_arms():
    """If the fixture is ever re-cut, this says so before a control goes quiet."""
    beats = [r for r in records() if r.get("kind") == "heartbeat"]
    assert [b["sinceProgressMS"] for b in beats] == [5818, 5200, 52637, 112652, 172724]
    assert [b["progress"] for b in beats] == [69, 88, 90, 90, 90]
