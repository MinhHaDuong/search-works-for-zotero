"""The clone-rung recipe copies the author's data directory, or refuses (ticket 0818).

Rung 4 runs the sitter on a reflink copy of the author's library. The copy is
only worth anything if Zotero was closed while it was taken, and only cheap if
it really is a reflink: `cp --reflink=auto` falls back to a full byte copy of
46 GB without a word. So the recipe refuses on a running Zotero, found by bare
process name -- never `pgrep -f`, which matched its own command line in an
earlier probe here -- and on a live profile lock; and it copies with
`--reflink=always`, which fails loudly, leaving nothing behind when it does.

Every refusal is driven through a faked process listing and a faked `cp`, so
no test here needs, or touches, a Zotero.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

import sitter_clone_data as clone  # noqa: E402
import sitter_clone_rung as rung  # noqa: E402
from sitter_smoke_test import setup_profile_existing_data  # noqa: E402


def _library(tmp_path: Path) -> Path:
    source = tmp_path / "Zotero"
    (source / "storage" / "ABCD1234").mkdir(parents=True)
    (source / "zotero.sqlite").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    (source / "zotero.sqlite-wal").write_bytes(b"")
    (source / "storage" / "ABCD1234" / "paper.pdf").write_bytes(b"%PDF-1.4")
    return source


class _Runner:
    """Records every argv; answers `ps` with the given listing and `cp` by
    either copying for real (reflink or not, the bytes are the same) or
    failing after writing a partial tree, the way a per-file clone failure
    does."""

    def __init__(self, comms=("bash", "python3"), cp_fails=False):
        self.comms, self.cp_fails = comms, cp_fails
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[0] == "ps":
            out = "".join(f"{c}\n" for c in self.comms)
            return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")
        if argv[0] == "cp":
            source, dest = Path(argv[-2]), Path(argv[-1])
            if self.cp_fails:
                (dest / "storage").mkdir(parents=True)
                (dest / "zotero.sqlite").write_bytes(b"partial")
                return subprocess.CompletedProcess(
                    argv, 1, stdout="", stderr="cp: failed to clone: Operation not supported")
            shutil.copytree(source, dest, symlinks=True)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command {argv}")


def _no_locks(tmp_path: Path) -> Path:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    return profiles


def test_refuses_while_zotero_bin_runs_and_asks_ps_by_bare_name(tmp_path):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    run = _Runner(comms=("bash", "zotero-bin", "python3"))
    with pytest.raises(clone.Refused, match="zotero-bin"):
        clone.clone_data(source, dest, profiles_root=_no_locks(tmp_path), run=run)
    # Exactly this argv: a regression to `pgrep -f zotero`, which matches its
    # own command line, fails here.
    assert run.calls[0] == ["ps", "-eo", "comm="]
    assert not any(c[0] == "cp" for c in run.calls)
    assert not dest.exists()


def test_a_process_merely_named_like_zotero_does_not_refuse(tmp_path):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    run = _Runner(comms=("zotero", "zotero-bin-helper", "python3"))
    clone.clone_data(source, dest, profiles_root=_no_locks(tmp_path), run=run)
    assert (dest / "zotero.sqlite").exists()


def test_refuses_on_a_live_profile_lock_with_the_process_list_clean(tmp_path):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    profiles = _no_locks(tmp_path)
    profile = profiles / "abcd.default"
    profile.mkdir()
    # Firefox's lock symlink names the holder as "<ip>:+<pid>"; this process
    # is alive, so the lock is live whatever the listing said.
    os.symlink(f"127.0.1.1:+{os.getpid()}", profile / "lock")
    run = _Runner()
    with pytest.raises(clone.Refused, match="lock"):
        clone.clone_data(source, dest, profiles_root=profiles, run=run)
    assert not any(c[0] == "cp" for c in run.calls)
    assert not dest.exists()


def test_a_stale_profile_lock_is_recorded_not_refused(tmp_path):
    """The author's profile carries a lock symlink with no Zotero running
    (ticket 0818's recon): the lock is a cross-check, never sufficient alone."""
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    profiles = _no_locks(tmp_path)
    profile = profiles / "abcd.default"
    profile.mkdir()
    os.symlink("127.0.1.1:+999999999", profile / "lock")
    rec = clone.clone_data(source, dest, profiles_root=profiles, run=_Runner())
    assert rec["locks"] == [{"profile": str(profile), "pid": 999999999, "live": False}]


def test_copies_with_reflink_always_and_records_the_wal(tmp_path):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    run = _Runner()
    rec = clone.clone_data(source, dest, profiles_root=_no_locks(tmp_path), run=run)
    cp = [c for c in run.calls if c[0] == "cp"]
    assert cp == [["cp", "-a", "--reflink=always", str(source), str(dest)]]
    assert (dest / "storage" / "ABCD1234" / "paper.pdf").read_bytes() == b"%PDF-1.4"
    assert rec["wal_bytes"] == 0
    assert rec["files"] == 3
    # The process list is read again after the copy: a Zotero started
    # mid-copy would have torn it.
    assert [c for c in run.calls if c[0] == "ps"] == [["ps", "-eo", "comm="]] * 2


def test_reflink_failure_raises_and_leaves_nothing(tmp_path):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    run = _Runner(cp_fails=True)
    with pytest.raises(clone.CopyFailed, match="failed to clone"):
        clone.clone_data(source, dest, profiles_root=_no_locks(tmp_path), run=run)
    cp = [c for c in run.calls if c[0] == "cp"]
    assert cp and "--reflink=always" in cp[0]
    assert not dest.exists()


def test_refuses_an_existing_destination_and_leaves_it_alone(tmp_path):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    dest.mkdir(parents=True)
    (dest / "keep").write_text("mine")
    with pytest.raises(clone.Refused, match="exists"):
        clone.clone_data(source, dest, profiles_root=_no_locks(tmp_path), run=_Runner())
    assert (dest / "keep").read_text() == "mine"


def test_refuses_across_devices(tmp_path, monkeypatch):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    real = os.stat

    def fake_stat(path, *a, **k):
        st = real(path, *a, **k)
        if Path(path) == dest.parent:
            return os.stat_result((st.st_mode, st.st_ino, st.st_dev + 1) + tuple(st)[3:])
        return st

    monkeypatch.setattr(clone.os, "stat", fake_stat)
    run = _Runner()
    with pytest.raises(clone.Refused, match="device"):
        clone.clone_data(source, dest, profiles_root=_no_locks(tmp_path), run=run)
    assert not any(c[0] == "cp" for c in run.calls)


def test_refuses_below_the_free_space_floor(tmp_path):
    source = _library(tmp_path)
    dest = tmp_path / "clone" / "Zotero"
    run = _Runner()
    with pytest.raises(clone.Refused, match="free"):
        clone.clone_data(source, dest, profiles_root=_no_locks(tmp_path), run=run,
                         min_free_gb=10 ** 9)
    assert not any(c[0] == "cp" for c in run.calls)


def test_refuses_a_source_that_is_not_a_data_directory(tmp_path):
    source = tmp_path / "empty"
    source.mkdir()
    with pytest.raises(clone.Refused, match="zotero.sqlite"):
        clone.clone_data(source, tmp_path / "clone" / "Zotero",
                         profiles_root=_no_locks(tmp_path), run=_Runner())


def _fs_type(path: Path) -> str:
    out = subprocess.run(["stat", "-f", "-c", "%T", str(path)],
                         capture_output=True, text=True, check=False)
    return out.stdout.strip()


@pytest.mark.integration
@pytest.mark.skipif(_fs_type(Path("/tmp")) != "tmpfs",
                    reason="needs a filesystem that cannot reflink")
def test_real_cp_on_a_filesystem_that_cannot_reflink_fails_and_writes_nothing(tmp_path_factory):
    """The real `cp`, on tmpfs, which has no reflink: it must fail, not copy."""
    base = tmp_path_factory.mktemp("noreflink", numbered=True)
    if _fs_type(base) != "tmpfs":
        pytest.skip(f"{base} is not tmpfs")
    source = _library(base)
    dest = base / "clone" / "Zotero"

    def ps_clean(argv, **kwargs):
        if argv[0] == "ps":
            return subprocess.CompletedProcess(argv, 0, stdout="bash\n", stderr="")
        return subprocess.run(argv, **kwargs)

    with pytest.raises(clone.CopyFailed):
        clone.clone_data(source, dest, profiles_root=_no_locks(base), run=ps_clean,
                         min_free_gb=0)
    assert not dest.exists()


def test_setup_profile_existing_data_points_a_fresh_profile_at_the_copy(tmp_path):
    data = _library(tmp_path)
    profile = setup_profile_existing_data(tmp_path / "work", data)
    prefs = (profile / "prefs.js").read_text(encoding="utf-8")
    assert f'"extensions.zotero.dataDir", "{data}"' in prefs
    assert 'user_pref("extensions.zotero.useDataDir", true);' in prefs
    with pytest.raises(FileExistsError):
        setup_profile_existing_data(tmp_path / "work", data)


def test_setup_profile_existing_data_refuses_an_empty_directory(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        setup_profile_existing_data(tmp_path / "work", empty)


# --------------------------------------------------------------------------
# the rung driver's pure parts
# --------------------------------------------------------------------------


@pytest.mark.parametrize("state, want", [
    ({"ok": True, "pending": 0, "busy": False, "phase": "idle"}, True),
    ({"ok": True, "pending": 0, "busy": False, "phase": "census"}, False),
    ({"ok": True, "pending": 0, "busy": False, "phase": "draining"}, False),
    ({"ok": True, "pending": 0, "busy": False, "phase": "extracting"}, False),
    ({"ok": True, "pending": 3, "busy": False, "phase": "idle"}, False),
    ({"ok": True, "pending": 0, "busy": True, "phase": "idle"}, False),
    ({"ok": False, "reason": "no-handle"}, False),
])
def test_settled_needs_an_empty_queue_out_of_the_working_phases(state, want):
    assert rung.settled(state) is want


def test_the_driver_refuses_a_data_directory_a_profile_is_pinned_to(tmp_path):
    live = _library(tmp_path)
    profiles = tmp_path / "profiles"
    (profiles / "abcd.default").mkdir(parents=True)
    (profiles / "abcd.default" / "prefs.js").write_text(
        f'user_pref("extensions.zotero.dataDir", "{live}");\n', encoding="utf-8")
    assert rung.pinned_data_dirs(profiles) == {
        str(live.resolve()): str(profiles / "abcd.default")}

    class Args:
        data_dir = live
        integrity_records: list = []

    Args.profiles = profiles
    with pytest.raises(rung.CloneFailure, match="REFUSING"):
        rung.run_clone(Args, log=None)
