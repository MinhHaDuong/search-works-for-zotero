"""A sitter refusal ends a rung run NOT-RUN, never at the index timeout (ticket 0824).

Faked state streams, no Zotero. The three rung drivers --
`bench/sitter_smoke_test.py`, `bench/sitter_menagerie_test.py`,
`bench/sitter_clone_rung.py` -- all go through `bench/sitter_refusal.py`, so
each wait is driven here with the same streams: a `low-disk` phase with work
pending ends it within one poll, naming the gate; a transient gate gets one
forced retry and no more; a completing stream still passes. The preflight
refuses a work directory below the sitter's disk floor before any Zotero
launch, and no driver's default arena is on `/tmp`.
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

import sitter_clone_rung as clone  # noqa: E402
import sitter_menagerie_test as menagerie  # noqa: E402
import sitter_refusal as refusal  # noqa: E402
import sitter_smoke_test as smoke  # noqa: E402
from zotero_rdp_client import RDPConnectionClosed  # noqa: E402

BOOTSTRAP = REPO / "plugins/sdt-sitter/bootstrap.js"
GIB = 1024 ** 3


# -- the plugin is the one owner of the gate list and the floor ----------------

def test_constants_are_read_from_the_plugin_source():
    got = refusal.plugin_constants()
    assert got["min_free_disk"] == 8 * GIB
    assert {"low-disk", "cpu-busy", "sync-in-progress"} <= set(got["blocked_phases"])
    assert refusal.TRANSIENT_GATES <= set(got["blocked_phases"])


def test_a_floor_moved_in_the_plugin_moves_the_preflight():
    # Positive control: the parser follows the source rather than a copy.
    source = BOOTSTRAP.read_text(encoding="utf-8")
    moved = source.replace("MIN_FREE_DISK = 8 * 1024 ** 3", "MIN_FREE_DISK = 2 * 1024 ** 3")
    assert moved != source
    assert refusal.plugin_constants(moved)["min_free_disk"] == 2 * GIB
    planted = source.replace("var SDT_BLOCKED_PHASES = ['cpu-busy',",
                             "var SDT_BLOCKED_PHASES = ['new-gate', 'cpu-busy',")
    assert "new-gate" in refusal.plugin_constants(planted)["blocked_phases"]


def test_no_driver_carries_a_second_copy_of_the_floor():
    for name in ("sitter_refusal.py", "sitter_smoke_test.py",
                 "sitter_menagerie_test.py", "sitter_clone_rung.py"):
        text = (REPO / "bench" / name).read_text(encoding="utf-8")
        assert not re.search(r"8\s*\*\s*1024\s*\*\*\s*3", text), name


# -- the guard ------------------------------------------------------------------

class FakeZotero:
    """Answers the guard's two probes and counts them."""

    def __init__(self, admission=None):
        self.retries = 0
        self.reads = 0
        self.admission = admission or {"directory": "/w/data/storage",
                                       "diskAvailableBytes": int(7.8 * GIB)}

    def __call__(self, code, what):
        if code == refusal.FORCE_RETRY:
            self.retries += 1
            return {"ok": True, "how": "scope"}
        if code.startswith(refusal.READ_ADMISSION_MARK):
            self.reads += 1
            return {"ok": True, "source": "sitter", "admission": self.admission,
                    "refusal": "Paused: not enough disk space"}
        raise AssertionError(f"unexpected probe {what}")


class _Log:
    def __init__(self):
        self.lines = []

    def write(self, line):
        self.lines.append(line)


def _guard(zotero=None, directory=Path("/w/data")):
    return refusal.RefusalGuard(zotero or FakeZotero(), _Log(), directory=directory)


def test_a_blocked_gate_with_work_pending_is_refused_at_once():
    zotero = FakeZotero()
    guard = _guard(zotero)
    with pytest.raises(refusal.SitterRefused, match="low-disk") as caught:
        guard.check({"phase": "low-disk", "pending": 44})
    assert zotero.retries == 0 and zotero.reads == 1
    record = caught.value.record
    assert record["gate"] == "low-disk"
    assert record["readings"]["admission"]["diskAvailableBytes"] == int(7.8 * GIB)
    assert isinstance(caught.value, smoke.NotRunError)


def test_a_transient_gate_gets_one_forced_retry_and_no_second():
    zotero = FakeZotero()
    guard = _guard(zotero)
    guard.check({"phase": "cpu-busy", "pending": 3})
    assert zotero.retries == 1
    with pytest.raises(refusal.SitterRefused, match="cpu-busy") as caught:
        guard.check({"phase": "cpu-busy", "pending": 3})
    assert zotero.retries == 1
    assert caught.value.record["forced_retry"] == "cpu-busy"


def test_each_transient_gate_gets_its_own_forced_retry():
    """Review of PR #626 (red team): the menagerie driver reuses one guard
    across three waits, so a retry spent on one gate must not be charged to
    another met later in the run."""
    zotero = FakeZotero()
    guard = _guard(zotero)
    guard.check({"phase": "cpu-busy", "pending": 3})
    guard.check({"phase": "low-memory", "pending": 3})
    assert zotero.retries == 2
    with pytest.raises(refusal.SitterRefused, match="low-memory") as caught:
        guard.check({"phase": "low-memory", "pending": 3})
    assert caught.value.record["forced_retry"] == "low-memory"


def test_a_lost_rdp_link_is_not_reported_as_a_refusal():
    """Review of PR #626 (red team): a dropped debugger link while reading the
    admission is a crash, and must not come out as a clean NOT-RUN refusal."""
    def zotero(code, what):
        if code.startswith(refusal.READ_ADMISSION_MARK):
            raise RDPConnectionClosed("connection closed")
        return {"ok": True}

    guard = refusal.RefusalGuard(zotero, _Log(), directory=Path("/w/data"))
    with pytest.raises(RDPConnectionClosed):
        guard.check({"phase": "low-disk", "pending": 4})


def test_the_arena_default_is_the_makefile_s_own(monkeypatch):
    """Review of PR #626 (consistency): the default lives in the Makefile, which
    exports it to its recipes; a driver run by hand falls back to a copy, and
    this holds the copy to its source."""
    make = (REPO / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^export ACCEPTANCE_ARENA$", make, re.M), "the Makefile must export it"
    default = re.search(r"^ACCEPTANCE_ARENA \?= (.+)$", make, re.M).group(1).strip()
    monkeypatch.delenv("ACCEPTANCE_ARENA", raising=False)
    expected = Path(default.replace("$(HOME)", str(Path.home())))
    assert refusal.arena_base("smoke") == expected / "sitter-smoke"


def test_working_phases_pass_the_guard():
    guard = _guard()
    for phase in ("census", "draining", "extracting", "waiting", "switched-off",
                  "native-worker-busy"):
        guard.check({"phase": phase, "pending": 5})


def test_an_unreachable_sitter_scope_falls_back_to_the_drivers_own_readings(tmp_path):
    def zotero(code, what):
        if code == refusal.FORCE_RETRY:
            return {"ok": True}
        return {"ok": False, "reason": "no-scope"}

    guard = refusal.RefusalGuard(zotero, _Log(), directory=tmp_path / "data" / "storage")
    with pytest.raises(refusal.SitterRefused) as caught:
        guard.check({"phase": "low-disk", "pending": 1})
    readings = caught.value.record["readings"]
    assert readings["source"] == "driver"
    assert readings["diskAvailableBytes"] > 0
    assert Path(readings["directory"]) == tmp_path


# -- each driver's wait, fed the same streams ------------------------------------

@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    for mod in (menagerie, clone, smoke):
        monkeypatch.setattr(mod.time, "monotonic", lambda: now[0])
        monkeypatch.setattr(mod.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    return now


def _state(phase, pending, completed=0, busy=False, scanned=5):
    return {"ok": True, "phase": phase, "pending": pending, "busy": busy,
            "completed": completed, "failed": 0, "total": scanned,
            "scanned": scanned, "active": None}


class _Run:
    def __init__(self, states):
        self.states = list(states)
        self.polls = 0

    def state(self):
        self.polls += 1
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]


def test_menagerie_wait_ends_on_low_disk_within_one_poll(clock):
    run = _Run([_state("low-disk", 5)])
    args = SimpleNamespace(index_timeout=10800.0, settle_quiet=300.0)
    with pytest.raises(refusal.SitterRefused, match="low-disk"):
        menagerie.wait_settled(run, args, _Log(), expected=5, guard=_guard())
    assert run.polls == 1 and clock[0] < 60


def test_menagerie_wait_still_drains_a_completing_stream(clock):
    run = _Run([_state("extracting", 3, busy=True), _state("waiting", 0, completed=5)])
    args = SimpleNamespace(index_timeout=10800.0, settle_quiet=300.0)
    out = menagerie.wait_settled(run, args, _Log(), expected=5, guard=_guard())
    assert out["how"] == "drained"


def test_menagerie_pack_wait_watches_the_sitter_too(clock, tmp_path):
    guard = _guard()
    with pytest.raises(refusal.SitterRefused, match="low-disk"):
        menagerie.wait_for_pack_count(
            tmp_path, 1, clock[0] + 60, _Log(), "restored",
            watch=lambda: guard.check(_state("low-disk", 1)))


class _CloneEval:
    def __init__(self, states, zotero):
        self.states, self.zotero, self.polls = list(states), zotero, 0

    def __call__(self, client, code, timeout, log, what):
        if code == clone.STATE:
            self.polls += 1
            return self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return self.zotero(code, what)


class _Sampler:
    def reading(self):
        return {"ok": False, "why": "faked"}


def _clone_args():
    return SimpleNamespace(settle_timeout=6 * 3600.0, eval_timeout=30.0,
                           poll_interval=15.0, settle_polls=4)


def test_clone_wait_ends_on_low_disk_within_one_poll(clock, monkeypatch):
    fake = _CloneEval([_state("low-disk", 40, scanned=225)], FakeZotero())
    monkeypatch.setattr(clone, "eval_action", fake)
    with pytest.raises(refusal.SitterRefused, match="low-disk"):
        clone.wait_for_settle(None, _Log(), _clone_args(), _Sampler(),
                              guard=refusal.RefusalGuard(
                                  lambda c, w: fake(None, c, 0, None, w), _Log(),
                                  directory=Path("/w")))
    assert fake.polls == 1 and clock[0] < 60


def test_clone_wait_still_settles_a_completing_stream(clock, monkeypatch):
    done = _state("waiting", 0, scanned=225)
    fake = _CloneEval([_state("extracting", 2, busy=True, scanned=225), done], FakeZotero())
    monkeypatch.setattr(clone, "eval_action", fake)
    out = clone.wait_for_settle(None, _Log(), _clone_args(), _Sampler(),
                                guard=_guard(fake.zotero))
    assert out["settled"] is True


def test_smoke_preparation_wait_ends_on_low_disk_within_one_poll(clock, tmp_path):
    polls = []
    guard = _guard()

    def watch():
        polls.append(1)
        guard.check(_state("low-disk", 3))

    with pytest.raises(refusal.SitterRefused, match="low-disk"):
        smoke.wait_for_preparation(tmp_path, tmp_path, tmp_path / "cache.jsonl", 3,
                                   clock[0] + 60, _Log(), watch=watch)
    assert len(polls) == 1


# -- the preflight --------------------------------------------------------------

def test_preflight_refuses_below_the_floor_and_names_it(tmp_path):
    with pytest.raises(refusal.NotRunError, match=r"7,8 GiB free.*needs 8,0 GiB") as caught:
        refusal.preflight(tmp_path, margin=0, free=int(7.8 * GIB), load=0.1, cpus=4)
    assert str(tmp_path) in str(caught.value) or "on /" in str(caught.value)


def test_preflight_counts_the_margin_and_passes_above_it(tmp_path):
    with pytest.raises(refusal.NotRunError):
        refusal.preflight(tmp_path, margin=GIB, free=int(8.5 * GIB), load=0.1, cpus=4)
    out = refusal.preflight(tmp_path, margin=GIB, free=10 * GIB, load=0.1, cpus=4)
    assert out["floor"] == 8 * GIB


def test_preflight_refuses_a_load_the_gate_would_refuse(tmp_path):
    with pytest.raises(refusal.NotRunError, match="load 25.*24 cores"):
        refusal.preflight(tmp_path, margin=0, free=100 * GIB, load=25.0, cpus=24)


def _no_launch(*_a, **_k):
    raise AssertionError("Zotero was launched past a failed preflight")


@pytest.fixture
def full_disk(monkeypatch):
    class Usage:
        free = int(7.8 * GIB)
    monkeypatch.setattr(refusal.shutil, "disk_usage", lambda _p: Usage)
    for mod in (smoke, menagerie, clone):
        monkeypatch.setattr(mod, "launch_zotero", _no_launch)
        monkeypatch.setattr(mod, "find_zotero_bin", _no_launch)
        monkeypatch.setattr(mod, "build_xpi", _no_launch)


def test_smoke_refuses_before_launch(full_disk, tmp_path, capsys):
    code = smoke.main(["--work-dir", str(tmp_path / "w")])
    assert code == smoke.NOT_RUN
    assert "sitter needs 8,0 GiB" in capsys.readouterr().err


def test_menagerie_refuses_before_launch(full_disk, tmp_path, capsys):
    out = tmp_path / "rec.json"
    code = menagerie.main(["--work-dir", str(tmp_path / "w"), "--json-out", str(out)])
    assert code == menagerie.NOT_RUN_EXIT
    assert "sitter needs 8,0 GiB" in capsys.readouterr().out
    assert '"not_run": true' in out.read_text(encoding="utf-8")


def test_clone_refuses_before_launch(full_disk, tmp_path):
    data = tmp_path / "copy"
    data.mkdir()
    (data / "zotero.sqlite").write_bytes(b"")
    rec = tmp_path / "rec.json"
    code = clone.main(["--data-dir", str(data), "--work-dir", str(tmp_path / "w"),
                       "--profiles", str(tmp_path / "none"), "--record", str(rec)])
    assert code == clone.NOT_RUN
    assert "sitter needs 8,0 GiB" in rec.read_text(encoding="utf-8")


# -- the default arena --------------------------------------------------------------

def test_the_default_arena_is_under_acceptance_arena_not_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("ACCEPTANCE_ARENA", str(tmp_path / "arena"))
    with refusal.arena_work_dir("smoke") as work:
        assert (tmp_path / "arena") in work.parents
        assert re.fullmatch(r"\d{6}-smoke", work.name)
        assert work.is_dir()


def test_the_unset_default_is_on_data_not_tmp(monkeypatch):
    monkeypatch.delenv("ACCEPTANCE_ARENA", raising=False)
    base = refusal.arena_base("smoke")
    assert base == Path.home() / "data" / "acceptance-arena" / "sitter-smoke"
    assert not str(base).startswith("/tmp")


@pytest.mark.parametrize("driver, argv", [
    (smoke, []),
    (menagerie, []),
    (clone, ["--data-dir", "/nonexistent"]),
])
def test_no_driver_defaults_its_work_dir_to_tmp(driver, argv, monkeypatch, tmp_path):
    seen = {}

    def spy(check, **_kw):
        seen["check"] = check
        raise SystemExit(0)

    monkeypatch.setattr(driver, "arena_work_dir", spy)
    with pytest.raises(SystemExit):
        driver.main(argv)
    assert seen["check"]
