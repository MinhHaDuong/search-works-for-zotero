"""A base arena does not grow without bound: old runs are pruned at allocation.

The defect this guards (ticket 0720): `assess()` allocates a fresh arena per
run, on purpose — a residue sweep needs a clean baseline and refuses a dirty
arena — and nothing ever deleted one. A run against a real target copies the
embedding weights into each of three per-check arenas, so one base arena
reached 878 MB in a week and the home volume 90 %. The mechanism is a retention
policy applied where the arena is allocated: before a run makes its own
directories, it removes every completed previous run beyond the `keep_runs`
most recent ones, and never anything else.

What "never anything else" means is the bulk of this file, because a pruner is
the one part of a harness whose failure mode is destructive:

- the current run's arenas are never removed, however low the keep count;
- a run that carries an in-progress marker is never removed, so two runs on one
  base arena cannot delete each other's baselines;
- only directories in the run layout (`<date>/<HHMMSS>-<check>`) are
  candidates — a hand-made probe directory beside them, the tracer's log
  directory, a stray file and a symlink are all left where they are;
- a removal that fails is reported and the run continues, because a full disk
  is what this is for and a failing pruner must not turn into a failing gate.

Fast tier: the driver's `assess()` is called in-process against the quiet stub.
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance.adapters import stubs  # noqa: E402


def _run_module():
    spec = importlib.util.spec_from_file_location(
        "acceptance_run", REPO / "bench" / "acceptance" / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    return run


def _make(at: Path):
    at.mkdir(parents=True, exist_ok=True)
    return stubs.build("stub-quiet", at)


def _assess(run, base: Path, **kw):
    return run.assess(_make, base_arena=base, log_dir=base / "trace",
                      drive_argv_for=lambda at: ["true"], **kw)


def _plant_run(base: Path, date: str, started: str, checks=("R10-local-by-default",)):
    """A previous run's directories, each holding one file, as the driver lays them out."""
    for check in checks:
        where = base / date / f"{started}-{check}"
        where.mkdir(parents=True)
        (where / "data").mkdir()
        (where / "data" / "weights.bin").write_bytes(b"x" * 16)
    return base / date / f"{started}-{checks[0]}"


def _previous_runs(base: Path) -> set[tuple[str, str]]:
    """Every (date, started) pair present under the base arena's run layout."""
    found = set()
    for date_dir in base.iterdir():
        if not date_dir.is_dir() or date_dir.is_symlink():
            continue
        for run_dir in date_dir.iterdir():
            if run_dir.is_dir() and "-" in run_dir.name:
                found.add((date_dir.name, run_dir.name.split("-", 1)[0]))
    return found


def test_previous_runs_beyond_the_keep_count_are_removed_at_allocation(tmp_path):
    run = _run_module()
    base = tmp_path / "arena"
    planted = [("2026-08-30", "090000"), ("2026-08-31", "120000"),
               ("2026-09-01", "080000"), ("2026-09-01", "230000"),
               ("2026-09-02", "010000")]
    for date, started in planted:
        _plant_run(base, date, started)

    result = _assess(run, base, keep_runs=2)

    assert result.checks, "the run itself must still have happened"
    survivors = _previous_runs(base)
    current = (result.date, run._started())
    assert current in survivors, "the current run's arenas are never removed"
    assert survivors - {current} == set(planted[-2:]), (
        "exactly the two most recent previous runs survive; older ones are removed")
    assert not (base / "2026-08-30").exists(), "an emptied date directory goes too"


def test_the_default_bound_is_finite_and_named(tmp_path):
    run = _run_module()
    base = tmp_path / "arena"
    assert isinstance(run.DEFAULT_KEEP_RUNS, int) and run.DEFAULT_KEEP_RUNS >= 1
    planted = [("2026-01-01", f"{n:02d}0000") for n in range(run.DEFAULT_KEEP_RUNS + 4)]
    for date, started in planted:
        _plant_run(base, date, started)

    result = _assess(run, base)

    current = (result.date, run._started())
    assert _previous_runs(base) - {current} == set(planted[-run.DEFAULT_KEEP_RUNS:])


def test_the_current_run_and_runs_in_progress_are_never_removed(tmp_path):
    run = _run_module()
    base = tmp_path / "arena"
    live = _plant_run(base, "2026-01-01", "010000")
    _plant_run(base, "2026-01-01", "020000")
    _plant_run(base, "2026-01-02", "030000")
    marker = run.in_progress_marker(base, "2026-01-01", "010000")
    marker.write_text("")

    result = _assess(run, base, keep_runs=0)

    current = (result.date, run._started())
    assert live.is_dir(), "a run whose marker is present is never removed"
    assert marker.exists(), "another run's marker is not this run's to remove"
    assert _previous_runs(base) == {("2026-01-01", "010000"), current}
    assert not run.in_progress_marker(base, result.date, run._started()).exists(), (
        "the current run's own marker is removed once its assertions have all run")


def test_the_marker_is_removed_even_when_an_assertion_raises(tmp_path, monkeypatch):
    run = _run_module()
    base = tmp_path / "arena"

    def boom(*a, **k):
        raise RuntimeError("the transport died")

    monkeypatch.setattr(run, "check_local_by_default", boom)
    result = _assess(run, base, keep_runs=1)
    assert not run.in_progress_marker(base, result.date, run._started()).exists()


def test_nothing_outside_the_run_layout_is_touched(tmp_path):
    run = _run_module()
    base = tmp_path / "arena"
    _plant_run(base, "2026-01-01", "010000")
    # A hand-made probe directory holding a model copy, as sessions leave them.
    (base / "seed" / "data" / "models").mkdir(parents=True)
    (base / "seed" / "data" / "models" / "weights.bin").write_bytes(b"x")
    # The tracer's logs, a stray file at the base, and an odd name inside a
    # date directory that is not a run directory.
    (base / "trace").mkdir()
    (base / "trace" / "subject.strace").write_text("")
    (base / "notes.txt").write_text("")
    (base / "2026-01-01" / "notes").mkdir()
    (base / "2026-01-01" / "notes" / "keep.txt").write_text("")
    # A date-shaped symlink pointing outside the arena, holding a run-shaped
    # directory: a pruner that followed it would delete outside the base.
    outside = tmp_path / "elsewhere"
    (outside / "020000-R10-local-by-default").mkdir(parents=True)
    (outside / "020000-R10-local-by-default" / "precious").write_text("")
    os.symlink(outside, base / "2026-01-02")

    _assess(run, base, keep_runs=0)

    assert (base / "seed" / "data" / "models" / "weights.bin").exists()
    assert (base / "trace" / "subject.strace").exists()
    assert (base / "notes.txt").exists()
    assert (base / "2026-01-01" / "notes" / "keep.txt").exists()
    assert not (base / "2026-01-01" / "010000-R10-local-by-default").exists(), (
        "the planted previous run is the one thing that goes: the control for "
        "this test, so that survival above is discrimination and not a no-op")
    assert (outside / "020000-R10-local-by-default" / "precious").exists()
    assert (base / "2026-01-02").is_symlink()


def test_a_removal_that_fails_is_reported_and_the_run_continues(tmp_path, caplog):
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions; this cannot fail here")
    run = _run_module()
    base = tmp_path / "arena"
    stuck = _plant_run(base, "2026-01-01", "010000")
    locked = stuck / "data"
    locked.chmod(0o500)
    try:
        with caplog.at_level(logging.WARNING, logger="acceptance"):
            result = _assess(run, base, keep_runs=0)
    finally:
        locked.chmod(0o700)

    assert result.checks, "a pruner that cannot remove must not end the run"
    assert (locked / "weights.bin").exists()
    assert any(str(stuck) in rec.getMessage() for rec in caplog.records), (
        "what could not be removed is named, so an operator can see it")


def test_keep_runs_rejects_a_negative_count(tmp_path, monkeypatch, capsys):
    run = _run_module()
    monkeypatch.setattr(sys, "argv", [
        "run.py", "--adapter", "stub-quiet", "--arena", str(tmp_path / "arena"),
        "--output", str(tmp_path / "out.json"), "--keep-runs", "-1",
    ])
    with pytest.raises(SystemExit) as stop:
        run.main()
    assert stop.value.code not in (0, None)
    # An unknown flag also exits 2, so the refusal has to be the count's own:
    # on a tree without the flag this test would otherwise pass for nothing.
    assert "--keep-runs must be 0 or more" in capsys.readouterr().err
    assert not (tmp_path / "arena").exists(), "refused before anything is allocated"
