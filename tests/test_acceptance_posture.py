"""Ticket 0625: no target process runs as the operator, and never falls back.

Two kinds of check, matching the ticket's own Test section.

**The control that matters, run for real.** A target process that writes
outside the arena to a path the operator owns must fail to write it once
wrapped under the account posture, where the identical, unwrapped spawn --
today's posture, before this ticket -- succeeds. Both arms run here, on the
same machine, in the same test: this is not "trust the mechanism argued in
the module docstring", it is the actual write attempt observed twice. The
wrapped arm is skipped, honestly, when this machine carries no working
    `untrusted-runner` account -- a skip is not a pass, and `test_acceptance_states.py`'s
own convention (`pytest.mark.integration` for anything that spawns a real
subprocess) is followed here for the same reason.

**The weaker check, which is deterministic everywhere.** `posture.resolve`
must refuse rather than fall back when the account is absent or does not
work, and `Posture.wrap` must raise on a refused posture rather than return an
argv a caller could spawn unwrapped. These do not need any real account and
are pinned with the account/`_works` probes patched, so they hold on any
machine this suite runs on -- including the one this ticket was written on,
    which has no `untrusted-runner` account at all.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance import posture  # noqa: E402


# --------------------------------------------------------------------------
# The control that matters: a real write, wrapped and unwrapped.
# --------------------------------------------------------------------------


@pytest.mark.integration
def test_a_wrapped_spawn_cannot_write_outside_the_arena_where_an_unwrapped_one_can(
    tmp_path,
):
    """Ticket 0625's Test section, run against the real filesystem.

    Arm 1 is the red this ticket exists to fix: a target process, spawned the
    way every adapter spawned one before this change, writes to a path outside
    the arena that the operator owns -- and succeeds. Arm 2 is the same write,
    from the same argv, wrapped under the account posture: it must fail. If
    this machine has no working `untrusted-runner` account the second arm cannot be
    observed and the test says so rather than reporting a green that measured
    nothing.
    """
    outside = tmp_path / "operator-owned" / "not-the-arena.txt"
    outside.parent.mkdir()
    write_argv = [
        sys.executable, "-c",
        f"open({str(outside)!r}, 'w').write('written by the target')",
    ]

    # Arm 1: unwrapped, today's posture. Must succeed -- otherwise the second
    # arm would prove nothing about the wrapping, only that this write was
    # already impossible for an unrelated reason.
    done = subprocess.run(write_argv, capture_output=True, timeout=30)
    assert done.returncode == 0 and outside.is_file(), (
        "the unwrapped control write did not succeed, so the wrapped arm below "
        f"cannot demonstrate anything: {done.stderr!r}"
    )
    outside.unlink()

    # Arm 2: wrapped under the account posture. Must fail.
    resolved = posture.resolve(posture.ACCOUNT_POSTURE)
    if resolved.refused is not None:
        pytest.skip(
            f"no working {posture.ACCOUNT!r} account on this machine, so the "
            f"account posture cannot be exercised for real: {resolved.refused}"
        )
    wrapped = resolved.wrap(write_argv, {})
    subprocess.run(wrapped, capture_output=True, timeout=30)
    assert not outside.exists(), (
        "a target process wrapped under the account posture wrote to a path "
        "outside the arena, owned by the operator: the boundary did not hold"
    )


# --------------------------------------------------------------------------
# The weaker check: refuse, never fall back. Deterministic everywhere.
# --------------------------------------------------------------------------


def test_resolve_refuses_when_the_account_does_not_exist(monkeypatch):
    monkeypatch.setattr(posture, "_account_exists", lambda account: False)
    resolved = posture.resolve(posture.ACCOUNT_POSTURE, account="not-a-real-account")
    assert resolved.refused is not None
    assert "not-a-real-account" in resolved.refused
    assert resolved.name == posture.ACCOUNT_POSTURE, (
        "a refused account posture must still say it was the account posture "
        "that was asked for, not collapse into an unnamed refusal"
    )
    with pytest.raises(posture.PostureUnavailable):
        resolved.wrap(["true"], {})


def test_resolve_refuses_when_the_account_exists_but_sudo_does_not_work(monkeypatch):
    """The account being IN the passwd database is not the same as it working.

    Mirrors `sandbox.py`'s own reasoning for why `choose()` runs a mechanism
    rather than looking it up: an account can exist with no working sudoers
    rule, and that must read as unavailable rather than as a surprise later.
    """
    monkeypatch.setattr(posture, "_account_exists", lambda account: True)
    monkeypatch.setattr(posture, "_works", lambda account: False)
    resolved = posture.resolve(posture.ACCOUNT_POSTURE, account="untrusted-runner")
    assert resolved.refused is not None
    assert "did not succeed" in resolved.refused
    with pytest.raises(posture.PostureUnavailable):
        resolved.wrap(["true"], {})


def test_resolve_accepts_when_the_account_exists_and_works(monkeypatch):
    monkeypatch.setattr(posture, "_account_exists", lambda account: True)
    monkeypatch.setattr(posture, "_works", lambda account: True)
    resolved = posture.resolve(posture.ACCOUNT_POSTURE, account="untrusted-runner")
    assert resolved.refused is None
    assert resolved.account == "untrusted-runner"
    wrapped = resolved.wrap(["node", "server.js"], {"HOME": "/arena/home"})
    assert wrapped == [
        "sudo", "-n", "-u", "untrusted-runner", "--preserve-env=HOME", "--",
        "node", "server.js",
    ]


def test_wrap_never_puts_an_environment_value_on_the_argv(monkeypatch):
    """The regression a first draft of this module introduced, and the fix.

    An earlier version carried `env -i KEY=VALUE ...` on this argv, which
    would have put anything ambient in the operator's shell -- an API key, a
    token -- somewhere any local account can read it (`ps`, `/proc/*/cmdline`)
    for as long as the wrapped process lives, worse than the exposure this
    ticket exists to close. Only NAMES may appear; a value survives nowhere
    in the returned argv.
    """
    monkeypatch.setattr(posture, "_account_exists", lambda account: True)
    monkeypatch.setattr(posture, "_works", lambda account: True)
    resolved = posture.resolve(posture.ACCOUNT_POSTURE, account="untrusted-runner")
    secret = "sk-not-a-real-secret-but-shaped-like-one-9f3c7b"
    wrapped = resolved.wrap(["node", "server.js"], {
        "HOME": "/arena/home", "OPENAI_API_KEY": secret,
    })
    joined = " ".join(wrapped)
    assert secret not in joined
    assert "OPENAI_API_KEY" in joined, (
        "the NAME must still be forwarded via --preserve-env, or the target "
        "never receives the variable at all"
    )
    assert "=" + secret not in joined and f"OPENAI_API_KEY={secret}" not in joined


def test_wrap_omits_preserve_env_entirely_for_an_empty_environment(monkeypatch):
    """`--preserve-env=` with an empty value is not a flag to hand `sudo`."""
    monkeypatch.setattr(posture, "_account_exists", lambda account: True)
    monkeypatch.setattr(posture, "_works", lambda account: True)
    resolved = posture.resolve(posture.ACCOUNT_POSTURE, account="untrusted-runner")
    wrapped = resolved.wrap(["true"], {})
    assert wrapped == ["sudo", "-n", "-u", "untrusted-runner", "--", "true"]
    assert not any(part.startswith("--preserve-env") for part in wrapped)


def test_already_isolated_posture_never_wraps_and_needs_no_account():
    """No account is checked for at all under this posture -- it is a
    documented precondition, not something the harness verifies (the module
    docstring argues why no verifying probe is safe)."""
    resolved = posture.resolve(posture.ISOLATED_POSTURE)
    assert resolved.refused is None
    assert resolved.account is None
    argv = ["node", "server.js"]
    assert resolved.wrap(argv, {"X": "1"}) == argv


def test_an_unknown_posture_name_is_refused_rather_than_defaulted():
    resolved = posture.resolve("some-future-posture-nobody-implemented-yet")
    assert resolved.refused is not None
    with pytest.raises(posture.PostureUnavailable):
        resolved.wrap(["true"], {})


def test_as_json_names_what_was_asked_for_even_when_refused():
    """The artifact must be able to show a run had no boundary, and what was
    asked for -- not just that something, unnamed, went wrong."""
    resolved = posture.resolve("bogus")
    payload = resolved.as_json()
    assert payload["posture"] == "bogus"
    assert payload["account"] is None
    assert payload["refused"]


def test_as_json_names_the_account_on_a_working_posture(monkeypatch):
    monkeypatch.setattr(posture, "_account_exists", lambda account: True)
    monkeypatch.setattr(posture, "_works", lambda account: True)
    resolved = posture.resolve(posture.ACCOUNT_POSTURE, account="untrusted-runner")
    payload = resolved.as_json()
    assert payload == {"posture": "account", "account": "untrusted-runner", "refused": None}


# --------------------------------------------------------------------------
# Wired into `run.py`: the artifact names the posture, and a stub target
# (which spawns nothing real) is unaffected by an account being unavailable.
# --------------------------------------------------------------------------

RUN = REPO / "bench" / "acceptance" / "run.py"


def _drive(tmp_path: Path, *extra: str) -> dict:
    import json

    output = tmp_path / "checks.json"
    done = subprocess.run(
        [sys.executable, str(RUN), "--adapter", "stub-quiet",
         "--arena", str(tmp_path / "arena"), "--output", str(output), *extra],
        capture_output=True, text=True, timeout=600, cwd=REPO,
    )
    assert output.is_file(), f"the driver wrote no artifact: {done.stderr[-3000:]}"
    return json.loads(output.read_text())


@pytest.mark.integration
def test_the_artifact_names_the_posture_the_run_had(tmp_path):
    """Ticket 0625's third Verification line: the artifact names the account
    a run belonged to -- or, here, that it belonged to none because the run
    declared itself already isolated."""
    artifact = _drive(tmp_path, "--posture", "already-isolated")
    assert artifact["posture"] == {
        "posture": posture.ISOLATED_POSTURE, "account": None, "refused": None,
    }


@pytest.mark.integration
def test_already_isolated_prints_a_notice_that_no_account_is_checked(tmp_path):
    """A review-round nit: the artifact records the posture, but nothing said
    so on the terminal while the run was happening -- the one place an
    operator watching a live run would see it before waiting for the JSON.
    `already-isolated` is the one posture the harness cannot verify (the
    module docstring argues why no probe is safe), which is exactly why it
    is the one that must be said loudly rather than left to the artifact
    alone.
    """
    output = tmp_path / "checks.json"
    done = subprocess.run(
        [sys.executable, str(RUN), "--adapter", "stub-quiet",
         "--arena", str(tmp_path / "arena"), "--output", str(output),
         "--posture", posture.ISOLATED_POSTURE],
        capture_output=True, text=True, timeout=600, cwd=REPO,
    )
    assert "already-isolated" in done.stderr
    assert "no dedicated account is required or checked" in done.stderr


@pytest.mark.integration
def test_a_stub_target_is_unaffected_by_a_missing_account(tmp_path):
    """The account requirement binds a target's own process spawn, and a stub
    fixture has none -- `stubs.py` simulates every verb in-process. Driving
    one with the default `account` posture on a machine with no `untrusted-runner`
    account must still reach ordinary verdicts: the posture that could not be
    established is recorded on the run, but it never reaches a target that
    never had a process to wrap in the first place.
    """
    artifact = _drive(tmp_path)  # default posture: "account"
    assert artifact["posture"]["posture"] == posture.ACCOUNT_POSTURE
    checks = artifact["checks"]
    assert checks, "the stub target produced no checks at all"
    if artifact["posture"]["refused"] is not None:
        refusal = artifact["posture"]["refused"]
        posture_blocked = [
            check for check in checks
            if check["result"] == "not-run"
            and refusal in check.get("detail", {}).get("why", "")
        ]
        assert not posture_blocked, (
            "a stub target that spawns no real process must not be pushed to "
            "not-run by an unrelated account being unavailable: "
            f"{refusal}"
        )
