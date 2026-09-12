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
    connect_resilient,
    format_state,
    make_ring_reader,
    refuse_dot_log,
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


def test_an_unreadable_record_is_not_a_disappearance_and_does_not_spend_the_alert(profile, log):
    """The trap this repo names generically and fell into once here: a check
    whose all-clear is indistinguishable from its could-not-look.

    `host_addon_record` is three-valued on purpose, and the watcher has to stay
    three-valued at the DECISION, not only in the line it prints. The case is
    not hypothetical for a watcher meant to run for days: the author restarts
    Zotero himself, and a partial `extensions.json` read during one of those is
    an unreadable, not an absence.
    """
    watcher = watcher_for(profile, log)
    poll(watcher)
    assert watcher._was_present

    (profile / "extensions.json").write_text("{ not json", encoding="utf-8")
    poll(watcher)
    assert not watcher.disappearance.is_set(), "an unreadable record fired the alert"
    assert "unreadable" in log.path.read_text(encoding="utf-8"), "the reading was not even logged"

    # And the positive control, which is what makes the silence above mean
    # something: the SAME watcher still fires when the record is readable and
    # the add-on is genuinely gone. `_was_present` survived the unreadable.
    write_extensions(profile, [OTHER])
    poll(watcher)
    assert watcher.disappearance.is_set(), "the unreadable reading disarmed the watcher"


def test_the_ring_read_retries_because_it_cannot_be_repeated(log):
    """The one RDP call in this system that gets no second chance.

    Every routine call in the volume driver goes through `connect_resilient`
    because a bare connect was found unreliable against this host (ticket 0766).
    The parked-ring read happens once, at an event seen twice in six days across
    two machines, and losing it to a hiccup loses the only statement of Gecko's
    own reason.
    """
    attempts = []

    class Client:
        def attach_chrome_target(self, timeout=None):
            pass

        def eval_js(self, code, timeout=None):
            return '{"parked": true}'

        def close(self):
            pass

    def flaky(host, port, timeout=None):
        attempts.append(port)
        if len(attempts) < 3:
            raise OSError("connection refused")
        return Client()

    read = make_ring_reader(6000, log, connect=flaky, sleep=lambda _seconds: None)
    assert json.loads(read())["parked"] is True
    assert len(attempts) == 3, attempts
    assert "rdp connect attempt 1/5 failed" in log.path.read_text(encoding="utf-8")


def test_a_connect_that_never_comes_back_raises_after_its_attempts(log):
    """The failure is still a failure -- it is reported once, not retried
    forever, and `preserve()` catches it and keeps the other two artefacts."""
    def refused(host, port, timeout=None):
        raise OSError("connection refused")

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        connect_resilient("127.0.0.1", 6000, 1.0, log, attempts=3, connect=refused,
                          sleep=lambda _seconds: None)


def test_a_log_that_cannot_be_committed_is_refused(tmp_path):
    """`.gitignore:20` ignores `*.log`, and this file exists to be committed as
    evidence. The trap already fired once (ticket 0727, 2026-09-11T16:08Z) and
    cost a post-hoc rename; documenting it was not enough."""
    message = refuse_dot_log(tmp_path / "run-watch.log")
    assert "run-watch.txt" in message and ".gitignore:20" in message

    import sitter_watch

    assert sitter_watch.main(["--profile", str(tmp_path), "--log",
                              str(tmp_path / "run-watch.log")]) == 2


def test_a_deliberate_uninstall_is_not_filed_as_the_signature(profile, log):
    """The randomised arms of the volume driver uninstall on purpose, and a
    deliberate removal produces the exact on-disk signature the watcher is armed
    for. A reproduction manufactured by the instrument would be investigated as
    though it were the defect -- worse than no reproduction, because it would
    end in the driver's own log."""
    watcher = watcher_for(profile, log)
    poll(watcher)

    with watcher.expect_absence("cycle 7 uninstall-then-install"):
        write_extensions(profile, [OTHER])
        poll(watcher)
        assert not watcher.disappearance.is_set(), "an asked-for removal was filed as the bug"
    text = log.path.read_text(encoding="utf-8")
    assert "EXPECTED" in text, "the log hides what it excused"
    assert "cycle 7 uninstall-then-install" in text

    # And the window is the gesture, not the run: the same watcher fires on the
    # next unexplained removal. Without this the excuse would be permanent, and
    # the arm that uses it would be blind for the rest of its cycles.
    write_extensions(profile, [ADDON, OTHER])
    poll(watcher)
    write_extensions(profile, [OTHER])
    poll(watcher)
    assert watcher.disappearance.is_set(), "the expectation outlived the gesture"


def test_an_expected_absence_that_never_comes_back_is_the_signature_after_all(profile, log, tmp_path):
    """The false NEGATIVE that mirrors the false positive.

    `uninstall-then-install` always ends with the add-on back, so a record still
    gone when the window closes is not the gesture that was supposed to explain
    it. Without this, a genuine occurrence whose timing landed inside a
    six-second window would be filed as expected and lost -- and the event is
    what six days of deliberate arms could not produce once.
    """
    evidence = tmp_path / "evidence"
    watcher = watcher_for(profile, log, evidence_dir=evidence)
    poll(watcher)

    with watcher.expect_absence("cycle 3 uninstall-then-install"):
        write_extensions(profile, [OTHER])
        poll(watcher)
        assert not watcher.disappearance.is_set()
        # and the reinstall never happens

    assert watcher.disappearance.is_set(), "an absence that outlived its excuse was excused"
    text = log.path.read_text(encoding="utf-8")
    assert "did not come back" in text
    assert list(evidence.glob("disappearance-*")), "no evidence was taken"


def test_the_gesture_that_does_come_back_stays_excused(profile, log, tmp_path):
    """The positive control for the arm above: the ordinary case still does not
    fire, or the randomised arm would redden on one cycle in ten."""
    watcher = watcher_for(profile, log, evidence_dir=tmp_path / "evidence")
    poll(watcher)
    with watcher.expect_absence("cycle 4 uninstall-then-install"):
        write_extensions(profile, [OTHER])
        poll(watcher)
        write_extensions(profile, [ADDON, OTHER])  # the reinstall
    assert not watcher.disappearance.is_set()
