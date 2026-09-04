"""Ticket 0637: the account posture and the network isolation compose in one order only.

Two apparatus modules stand between the harness and a target's process on
R10's egress arm: `posture.py` switches identity to the dedicated account,
`sandbox.py` traces the run and takes away its route. Before this ticket they
composed as tracer, then namespace, then -- from deep inside the re-invoked
`--drive` process -- the identity switch. That order cannot run, for three
independent reasons, each measured on the machine this was written on
(padme, 2026-09-04):

- `sudo` inside a rootless user namespace refuses: the files it must trust
  literally (`/etc/sudo.conf`, `/etc/sudoers`) appear owned by the unmapped
  uid, and it says so rather than trusting a remapped view of them.
- `sudo` under a tracer it did not start refuses too: the kernel neutralises
  a setuid exec under an unprivileged ptrace, so `strace ... sudo ...` reports
  "effective uid is not 0" with no namespace anywhere in sight.
- `bwrap` sets no-new-privs on everything inside it, which is the same refusal
  by a third route.

So the identity switch goes OUTERMOST -- outside the tracer, outside the
mechanism -- and the `--drive` process it encloses spawns its target unwrapped,
because it already IS the account. The deterministic tests below pin that
shape wherever this suite runs; the integration test at the end runs both
orders for real, and skips (not passes) where this machine cannot tell them
apart.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance import assertions, posture, sandbox  # noqa: E402
from acceptance.adapters import stubs  # noqa: E402
from acceptance.interface import NOT_RUN, PASS  # noqa: E402
from acceptance.sandbox import Attempt, TraceResult  # noqa: E402


def _run_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "acceptance_run_0637", REPO / "bench" / "acceptance" / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    return run


class _Recorded(sandbox.Mechanism):
    """A mechanism whose two wrappers are recognisable in a command line."""

    def __init__(self):
        super().__init__(name="recorded", note="a test double")

    def isolated(self, argv, writable):
        return ["MECH-ISOLATED", *argv]

    def shared(self, argv, writable):
        return ["MECH-SHARED", *argv]


# --------------------------------------------------------------------------
# The shape, pinned deterministically.
# --------------------------------------------------------------------------


def test_run_traced_puts_the_outer_wrap_outside_the_tracer_and_the_mechanism(
    monkeypatch, tmp_path
):
    """`under` is applied to the WHOLE traced command, the tracer included.

    Not merely outside the mechanism: a setuid switch under an unprivileged
    tracer is refused before any namespace is reached, so an `under` that sat
    between tracer and mechanism would fail for the second of the three
    reasons in the module docstring while looking like it fixed the first.
    """
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    sandbox.run_traced(
        ["python3", "run.py", "--drive"], mechanism=_Recorded(), network_shared=False,
        log_dir=tmp_path, tag="subject",
        under=lambda argv: ["IDENTITY-SWITCH", "--", *argv],
    )
    assert len(seen) == 1
    command = seen[0]
    assert command[0] == "IDENTITY-SWITCH", command
    assert command.index("IDENTITY-SWITCH") < command.index(sandbox.STRACE), (
        "the identity switch must enclose the tracer, not sit under it"
    )
    assert command.index(sandbox.STRACE) < command.index("MECH-ISOLATED"), (
        "the tracer still wraps the mechanism (the module docstring's own rule)"
    )
    assert command[-3:] == ["python3", "run.py", "--drive"]


def test_run_traced_without_an_outer_wrap_is_unchanged(monkeypatch, tmp_path):
    """Every existing caller passes no `under`; the command they get is the one
    they got before this ticket."""
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    sandbox.run_traced(["true"], mechanism=_Recorded(), network_shared=True,
                       log_dir=tmp_path, tag="control")
    assert seen[0][0] == sandbox.STRACE
    assert seen[0][-2:] == ["MECH-SHARED", "true"]


def _tripping(argv, mechanism, network_shared, **_):
    """A trace result that trips both detectors, as a working control must."""
    attempts = [
        Attempt("connect", "1.1.1.1", 443, "off_machine", ""),
        Attempt("sendto", "127.0.0.53", 53, "dns", ""),
    ]
    return TraceResult(argv=list(argv), mechanism=mechanism.name,
                       network_shared=network_shared, returncode=0,
                       stdout="", stderr="", attempts=attempts)


def _quiet(argv, mechanism, network_shared, **_):
    return TraceResult(argv=list(argv), mechanism=mechanism.name,
                       network_shared=network_shared, returncode=0,
                       stdout="{}", stderr="")


def test_check_no_egress_switches_identity_on_the_subject_arm_only(monkeypatch, tmp_path):
    """The two control arms drive a harness-owned probe, which is the harness's
    own process and runs as the operator like the rest of the harness. Only
    the subject arm re-invokes the driver around a target, so only it crosses
    the account boundary -- and it must, or the target inside it runs as the
    operator, which is the ruling ticket 0625 closed."""
    calls: list[tuple[str, object]] = []

    def fake_run_traced(argv, *, mechanism, network_shared, log_dir, tag, **kwargs):
        calls.append((tag, kwargs.get("under")))
        make = _tripping if tag.startswith("control") else _quiet
        return make(argv, mechanism, network_shared)

    monkeypatch.setattr(assertions, "choose", lambda: (_Recorded(), None))
    monkeypatch.setattr(assertions, "run_traced", fake_run_traced)
    where = tmp_path / "arena"
    where.mkdir()
    marker = object()
    check = assertions.check_no_egress(
        stubs.build("stub-quiet", where), arena=where, log_dir=tmp_path / "trace",
        drive_argv=["true"], under=marker,
    )
    assert check.result == PASS, check.detail
    by_tag = dict(calls)
    assert by_tag["subject"] is marker, "the subject arm must carry the identity switch"
    assert by_tag["control-shared"] is None and by_tag["control-isolated"] is None, (
        "the controls run the harness's own probe and stay as the operator"
    )


def test_inherited_posture_names_the_account_and_wraps_nothing(monkeypatch):
    """What the `--drive` process holds once the outer driver has already put
    the whole of it under the account: a second `sudo` from inside would be
    refused (module docstring), and is not needed -- the boundary was crossed
    once, by the parent, which is still one crossing at one seam."""
    monkeypatch.setenv("USER", "tester")  # the switch this posture describes, as it reads
    inherited = posture.inherited("tester")
    assert inherited.name == posture.ACCOUNT_POSTURE
    assert inherited.account == "tester"
    assert inherited.refused is None
    argv = ["node", "server.js"]
    assert inherited.wrap(argv, {"X": "1"}) == argv
    assert "sudo" not in inherited.wrap(argv, {"X": "1"})


def test_forwardable_drops_the_names_bound_to_the_operator_and_keeps_the_rest():
    """The re-invoked driver needs the operator's PATH and the run's own
    variables (`ZOTEUS_UPDATE_CHECK`, say), and must NOT inherit the operator's
    `HOME` or runtime directory: a rootless container engine started as the
    account with the operator's `HOME` looks for its state under a home it
    cannot write. Adapters that set `HOME` deliberately, to an arena-owned
    directory, are untouched -- this helper is for the re-invocation alone."""
    env = {
        "PATH": "/usr/bin", "ZOTEUS_UPDATE_CHECK": "false", "HOME": "/home/operator",
        "USER": "operator", "LOGNAME": "operator", "XDG_RUNTIME_DIR": "/run/user/1000",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
    }
    kept = posture.forwardable(env)
    assert kept == {"PATH": "/usr/bin", "ZOTEUS_UPDATE_CHECK": "false"}
    for name in posture.IDENTITY_BOUND:
        assert name not in kept


def test_drive_argv_carries_the_inherited_account_only_under_the_account_posture():
    run = _run_module()
    options = {"entrypoint": "dist/index.js"}
    under_account = run.drive_argv("zoteus", Path("/arena"), posture.ACCOUNT_POSTURE,
                                   options, spawned_under="tester")
    assert "--drive" in under_account
    assert under_account[under_account.index("--spawned-under") + 1] == "tester"
    assert under_account[under_account.index("--posture") + 1] == posture.ACCOUNT_POSTURE
    assert "--adapter-option" in under_account and "entrypoint=dist/index.js" in under_account

    isolated = run.drive_argv("zoteus", Path("/arena"), posture.ISOLATED_POSTURE,
                              options, spawned_under=None)
    assert "--spawned-under" not in isolated
    assert isolated[isolated.index("--posture") + 1] == posture.ISOLATED_POSTURE


def test_drive_mode_spawned_under_the_account_does_not_probe_for_a_second_switch(
    monkeypatch, tmp_path
):
    """Inside the enclosing switch, `resolve()`'s `_works` probe would run
    `sudo` again -- and be refused, for the module docstring's first reason.
    The `--drive` process must therefore take the inherited posture and never
    call `resolve()` at all: a probe that cannot succeed there is not a check,
    it is a guaranteed `not-run`."""
    run = _run_module()

    def must_not_resolve(name, account=posture.ACCOUNT):
        raise AssertionError("the --drive process re-resolved the posture")

    handed: list[object] = []

    def fake_load(name, arena, **options):
        handed.append(options.get("posture"))
        return stubs.build("stub-quiet", arena)

    monkeypatch.setattr(run.posture_mod, "resolve", must_not_resolve)
    monkeypatch.setattr(run.adapters, "load", fake_load)
    monkeypatch.setenv("USER", "tester")
    monkeypatch.setattr(sys, "argv", [
        "run.py", "--adapter", "stub-quiet", "--arena", str(tmp_path / "arena"),
        "--drive", "--spawned-under", "tester",
    ])
    assert run.main() == 0
    assert handed and handed[0].account == "tester" and handed[0].refused is None
    assert handed[0].wrap(["node"], {"X": "1"}) == ["node"]


# --------------------------------------------------------------------------
# Ticket 0638: the claim is checked against what the process can actually see.
# --------------------------------------------------------------------------


def test_inherited_refuses_a_claim_the_environment_contradicts(monkeypatch):
    """`--spawned-under tester` says a parent crossed the boundary. Where the
    mechanism does not remap identity, `USER` is evidence about that claim:
    `forwardable()` strips `USER` from what the re-invocation carries across,
    so `sudo` writes the account's own value and a genuine switch reads
    `tester`. An operator hand-typing the flag reads their own name, and this
    is where that stops -- the same "run a probe rather than trust a shape"
    discipline `_works()` follows.

    Refused rather than raised, the shape `resolve()` uses: this is decided at
    argparse time, before the driver's `record()` exists to turn a raise into a
    verdict. And fail-closed -- the refusal reaches the spawn, where `wrap`
    raises rather than returning an argv, so nothing runs unwrapped."""
    monkeypatch.setenv("USER", "operator")
    refused = posture.inherited("tester")
    assert refused.refused is not None
    assert "tester" in refused.refused and "operator" in refused.refused
    with pytest.raises(posture.PostureUnavailable):
        refused.wrap(["node"], {"X": "1"})


def test_inherited_accepts_the_claim_the_environment_corroborates(monkeypatch):
    """The contrast arm for the refusal above: same call, `USER` agreeing.
    Without it the refusal test would pass against an `inherited()` that
    refused everything."""
    monkeypatch.setenv("USER", "tester")
    granted = posture.inherited("tester")
    assert granted.account == "tester" and granted.refused is None
    assert granted.wrap(["node"], {"X": "1"}) == ["node"]


def test_check_still_applies_under_the_uid_remapping_mechanism(monkeypatch):
    """`getuid()` reads 0 inside `podman-unshare`'s rootless user namespace, but
    `USER` is plain `execve` environment inheritance -- orthogonal to
    namespacing, and unaffected by it. Measured live on this project's own
    reference machine (ticket 0638, red-team finding): `podman unshare
    unshare -n -- env` still reports `USER=tester`. So this check needs no
    mechanism-aware skip; the refusal/acceptance pair above already covers
    every mechanism there is."""
    monkeypatch.setenv("USER", "operator")
    refused = posture.inherited("tester")
    assert refused.refused is not None
    with pytest.raises(posture.PostureUnavailable):
        refused.wrap(["node"], {"X": "1"})


def test_egress_check_hands_drive_argv_through_unmodified(monkeypatch, tmp_path):
    """`check_no_egress` holds the chosen mechanism but must not use it to vary
    what it hands the `--drive` subprocess -- `posture.inherited`'s own check
    already covers every mechanism, so there is nothing here for the egress
    check to augment or skip on the child's behalf."""
    seen: dict[str, list[str]] = {}

    def fake_run_traced(argv, *, mechanism, network_shared, log_dir, tag, **kwargs):
        if tag == "subject":
            seen["subject"] = list(argv)
        make = _tripping if tag.startswith("control") else _quiet
        return make(argv, mechanism, network_shared)

    monkeypatch.setattr(assertions, "run_traced", fake_run_traced)
    for mechanism in (sandbox.PodmanUnshare(), sandbox.Bubblewrap()):
        monkeypatch.setattr(assertions, "choose", lambda m=mechanism: (m, None))
        arena = tmp_path / mechanism.name
        arena.mkdir(parents=True, exist_ok=True)
        handed = ["python3", "run.py", "--drive", "--spawned-under", "tester"]
        assertions.check_no_egress(
            stubs.build("stub-quiet", arena), arena=arena, log_dir=tmp_path / "log",
            drive_argv=handed, under=None)
        assert seen["subject"] == handed


def test_spawned_under_is_refused_outside_drive_mode(monkeypatch, tmp_path):
    """The flag says "my parent already put me under the account". The outer
    driver has no parent that did, so accepting it there would let a run
    claim a boundary nothing established -- the `already-isolated` posture
    exists for the case where that claim is the operator's to make."""
    run = _run_module()
    monkeypatch.setattr(sys, "argv", [
        "run.py", "--adapter", "stub-quiet", "--arena", str(tmp_path / "arena"),
        "--output", str(tmp_path / "out.json"), "--spawned-under", "tester",
    ])
    with pytest.raises(SystemExit) as stop:
        run.main()
    assert stop.value.code not in (0, None)


def test_assess_hands_the_outer_wrap_to_the_egress_check_and_nothing_else(monkeypatch, tmp_path):
    run = _run_module()
    seen: dict[str, object] = {}

    def fake_no_egress(target, *, arena, log_dir, drive_argv, under=None):
        seen["under"] = under
        return assertions.not_run("R10-no-egress", "R10", "c", "f", target, "query", "stubbed")

    monkeypatch.setattr(run, "check_no_egress", fake_no_egress)
    marker = object()

    def make(at: Path):
        at.mkdir(parents=True, exist_ok=True)
        return stubs.build("stub-quiet", at)

    result = run.assess(make, base_arena=tmp_path / "arena", log_dir=tmp_path / "trace",
                        drive_argv_for=lambda at: ["true"], under=marker)
    assert seen["under"] is marker
    egress = [c for c in result.checks if c.check == "R10-no-egress"]
    assert egress and egress[0].result == NOT_RUN


# --------------------------------------------------------------------------
# Both orders, run for real. Skips where this machine cannot discriminate.
# --------------------------------------------------------------------------


@pytest.mark.integration
def test_identity_switch_outside_the_namespace_runs_where_the_reverse_is_refused(tmp_path):
    """The ticket's own reproduction and its fix, as one test with a control.

    The wrong order is run first and must fail: if it succeeds here, this
    machine accepts both orders and the test cannot tell the fix from its
    absence, so it says so rather than reporting a green that discriminated
    nothing. Then the composed order this ticket ships -- identity switch
    around tracer around mechanism -- must exit 0.
    """
    resolved = posture.resolve(posture.ACCOUNT_POSTURE)
    if resolved.refused is not None:
        pytest.skip(f"no working {posture.ACCOUNT!r} account here: {resolved.refused}")
    mechanism, why = sandbox.choose()
    if mechanism is None:
        pytest.skip(f"no isolation mechanism runs here: {why}")

    env = posture.forwardable(os.environ)

    # The tracer now runs as the account and writes its log as the account, so
    # the log directory has to be one the account can write — the arena is, by
    # the provisioning recipe; pytest's `tmp_path` (0700, operator-only) is
    # not, and would fail this test for a reason unrelated to the ordering.
    import shutil
    import tempfile

    scratch = Path(tempfile.mkdtemp(prefix="acceptance-0637-", dir="/tmp"))
    os.chmod(scratch, 0o777)
    try:
        # The order before this ticket: mechanism outside, the switch inside.
        wrong = subprocess.run(
            [sandbox.STRACE, "-f", "-e", "trace=network", "-o", str(scratch / "wrong.strace"),
             *mechanism.isolated(resolved.wrap(["true"], env), ())],
            capture_output=True, text=True, timeout=120, env={**os.environ, **env},
        )
        if wrong.returncode == 0:
            pytest.skip(
                f"{mechanism.name} lets sudo run inside it on this machine, so the two "
                "orders are indistinguishable here and this test cannot discriminate"
            )

        right = sandbox.run_traced(
            ["true"], mechanism=mechanism, network_shared=False, log_dir=scratch,
            tag="right", under=lambda argv: resolved.wrap(argv, env),
            env={**os.environ, **env},
        )
        assert right.returncode == 0, (
            f"identity switch outside {mechanism.name} was refused too:\n"
            f"{right.stderr[-2000:]}"
        )
        assert (scratch / "right.strace").is_file(), (
            "the tracer, running as the account, must still leave its log where the "
            "operator's process reads it back"
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
