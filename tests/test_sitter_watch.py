"""The watcher that has to be right the ONE time the sitter disappears again.

Ticket 0727. Both organic occurrences were watched by `scratchpad/sitter-watch.sh`,
which was never committed and is gone, and the only versioned successor lived
inside `bench/sitter_volume_experiment.py` and could not be pointed at the
author's own profile. `bench/sitter_watch.py` is the standalone one. This suite
owns two things about it that a live run cannot be asked to demonstrate twice:
that it fires on the signature and on nothing else, and that when it fires it
KEEPS the three artefacts that decay within minutes.

Every silence arm here is paired with the arm that makes it mean something. A
watcher that never fires passes every "did not fire" assertion, and a preserve()
that copies nothing passes every "did not raise" one.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

from sitter_watch import (  # noqa: E402
    CERTIFICATE_NAME,
    Log,
    Watcher,
    format_state,
)

ADDON = "sdt-pack-sitter@search-works-for-zotero.invalid"
OTHER = "fulltext-control@search-works-for-zotero.invalid"


def write_extensions(profile: Path, ids) -> None:
    """The profile's own record, in the shape Zotero writes it."""
    addons = [{"id": addon_id, "version": "0.3.43", "active": True,
               "location": "app-profile"} for addon_id in ids]
    (profile / "extensions.json").write_text(json.dumps({"schemaVersion": 35, "addons": addons}),
                                             encoding="utf-8")


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    directory = tmp_path / "profile"
    (directory / "extensions").mkdir(parents=True)
    write_extensions(directory, [ADDON, OTHER])
    (directory / "extensions" / f"{ADDON}.xpi").write_text("payload", encoding="utf-8")
    return directory


@pytest.fixture
def log(tmp_path: Path) -> Log:
    return Log(tmp_path / "watch.txt")


def watcher_for(profile: Path, log: Log, **kwargs) -> Watcher:
    """A watcher that never starts its thread: the tests drive `_run`'s body
    through one poll at a time, because a test that raced a 1.5 s poll would be
    a test that sometimes passes."""
    return Watcher(profile, ADDON, log, poll_seconds=0.01, **kwargs)


def poll(watcher: Watcher) -> None:
    """One iteration of the watch loop, without the thread or the wait."""
    watcher.poll_once()


def test_the_three_readings_are_distinguishable_in_the_line():
    """"Could not look" and "looked, and it is gone" are different findings, and
    a line that renders them the same makes the log unreadable at the one moment
    it matters."""
    unreadable = format_state({"read": False, "why": "no such file"}, False)
    absent = format_state({"read": True, "present": False, "ids": [OTHER]}, False)
    present = format_state({"read": True, "present": True, "version": "0.3.43",
                            "active": True, "location": "app-profile"}, True)
    assert "unreadable" in unreadable and "no such file" in unreadable
    assert "ABSENT" in absent and "unreadable" not in absent
    assert "present version=0.3.43 active=True" in present
    assert len({unreadable, absent, present}) == 3


def test_a_disappearance_fires_and_an_unrelated_change_does_not(profile, log):
    """The signature is this add-on's record going away. Another add-on being
    removed, or this one's version moving, is not it -- and the positive control
    is the same watcher firing two polls later."""
    watcher = watcher_for(profile, log)
    poll(watcher)
    assert not watcher.disappearance.is_set()

    write_extensions(profile, [ADDON])  # the OTHER add-on goes
    poll(watcher)
    assert not watcher.disappearance.is_set(), "another add-on's removal read as the signature"

    write_extensions(profile, [OTHER])  # and now this one
    (profile / "extensions" / f"{ADDON}.xpi").unlink()
    poll(watcher)
    assert watcher.disappearance.is_set(), "the signature did not fire"
    assert "ALERT disappearance signature" in log.path.read_text(encoding="utf-8")


def test_an_install_is_not_a_disappearance(profile, log):
    """absent -> present is the direction a first install takes, and it was the
    only direction arm 5 ever positive-controlled."""
    write_extensions(profile, [OTHER])
    watcher = watcher_for(profile, log)
    poll(watcher)
    write_extensions(profile, [ADDON, OTHER])
    poll(watcher)
    assert not watcher.disappearance.is_set()
    assert "ALERT" not in log.path.read_text(encoding="utf-8")


def test_the_quiet_log_stays_quiet(profile, log):
    """A line means a transition. Ten polls over an unchanging profile write
    one line, not ten, or the log cannot be read at a glance after a week."""
    watcher = watcher_for(profile, log)
    for _ in range(10):
        poll(watcher)
    lines = [line for line in log.path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1, lines


def test_firing_keeps_the_three_artefacts(profile, log, tmp_path):
    """The evidence, and the whole reason this round exists: the alert line
    alone is what the two organic occurrences already produced."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / CERTIFICATE_NAME).write_text(
        json.dumps({"reason": "uninstall", "report": "{}"}), encoding="utf-8")
    evidence = tmp_path / "evidence"
    ring = json.dumps({"parked": True, "records": [{"kind": "shutdown", "reason": "uninstall"}]})

    watcher = watcher_for(profile, log, evidence_dir=evidence, data_dir=data_dir,
                          read_ring=lambda: ring)
    poll(watcher)
    write_extensions(profile, [OTHER])
    poll(watcher)
    assert watcher.disappearance.is_set()

    taken = list(evidence.glob("disappearance-*"))
    assert len(taken) == 1, taken
    kept = taken[0]
    # extensions.json as it was AT the alert, before the host rewrites it.
    recorded = json.loads((kept / "extensions.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in recorded["addons"]] == [OTHER]
    # The certificate, which outlives the process.
    assert json.loads((kept / CERTIFICATE_NAME).read_text(encoding="utf-8"))["reason"] == "uninstall"
    # And the ring parked on the Zotero global, which does not.
    assert json.loads((kept / "parked-ring.json").read_text(encoding="utf-8"))["parked"] is True


def test_a_missing_artefact_is_reported_and_never_raises(profile, log, tmp_path):
    """Each artefact is conditional -- the ring needs a debugger port, the
    certificate needs the add-on's debug pref -- and an absent one is itself a
    finding. What must not happen is the taking of the other two being lost to a
    raise from the first."""
    evidence = tmp_path / "evidence"
    watcher = watcher_for(profile, log, evidence_dir=evidence,
                          data_dir=tmp_path / "no-such-data-dir",
                          read_ring=lambda: (_ for _ in ()).throw(RuntimeError("no port")))
    poll(watcher)
    write_extensions(profile, [OTHER])
    poll(watcher)

    text = log.path.read_text(encoding="utf-8")
    assert f"NO {CERTIFICATE_NAME}" in text
    assert "FAILED to read the parked ring" in text
    # The one that was there was still taken, after the other two failed.
    kept = next(iter(evidence.glob("disappearance-*")))
    assert (kept / "extensions.json").exists()


def test_no_evidence_directory_says_so_rather_than_failing_silently(profile, log):
    """A watcher started without somewhere to put the evidence still fires, and
    says in the log that the evidence was not taken -- the one thing worse than
    no evidence is a log that implies there is some."""
    watcher = watcher_for(profile, log)
    poll(watcher)
    write_extensions(profile, [OTHER])
    poll(watcher)
    assert watcher.disappearance.is_set()
    assert "evidence NOT taken: no --evidence-dir given" in log.path.read_text(encoding="utf-8")
