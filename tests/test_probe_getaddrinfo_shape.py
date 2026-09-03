"""The syscall-shape probe behind ticket 0629's attribution, and its artifact.

Ticket 0629 attributes the four DNS lookups the R10-no-egress subject arm
recorded against zoteus v1.13.0 (`bench/results/0604-ladder-matrix/
acceptance-zoteus-v1130.json`) to a single `getaddrinfo`-shaped call. That
attribution rests entirely on one measured claim -- that ONE `getaddrinfo`
of a non-resolving hostname produces exactly four resolver-port connects
under the harness's own no-route sandbox on this machine -- so the claim's
artifact has to carry the two arms that make it non-vacuous:

  * a **null arm** (a program that does nothing network-shaped), because
    without it a count of four is indistinguishable from background noise the
    tracer attributes to any traced process;
  * a **discriminating control** (a connect to a numeric address, which
    resolves no name), because without it "four connects appear whenever a
    socket is touched" explains the data just as well as "one name lookup
    costs four".

A probe whose all-clear is indistinguishable from "I could not look" is not a
probe (`bench/acceptance/assertions.py`'s own `why_both`, and the repo's
standing positive-control discipline). These tests fail if the committed
artifact loses either arm, or if the getaddrinfo arm stops matching the
counts the v1130 subject arm has to be explained by.
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "bench" / "results" / "0629-gap-a" / "syscall-shape.json"
PROBE = REPO / "bench" / "probe_getaddrinfo_shape.py"
V1130 = (
    REPO
    / "bench"
    / "results"
    / "0604-ladder-matrix"
    / "acceptance-zoteus-v1130.json"
)


def _arms() -> dict:
    return json.loads(ARTIFACT.read_text())["arms"]


def test_probe_script_is_committed_and_has_an_entry_point():
    """The measurement is reproducible, not a number typed into a note."""
    assert PROBE.exists(), f"{PROBE} is missing; the artifact would be unreproducible"
    source = PROBE.read_text()
    assert "argparse" in source, "every entry point gets argparse"
    assert "__main__" in source


def test_artifact_carries_a_null_arm_that_counted_nothing():
    arms = _arms()
    for arm in ("nothing/isolated", "nothing/net_shared"):
        assert arm in arms, f"the null arm {arm} is missing from the artifact"
        counts = arms[arm]["counts"]
        assert counts["dns"] == 0, f"{arm} saw resolver traffic: {counts}"
        assert counts["off_machine"] == 0, f"{arm} saw off-machine traffic: {counts}"


def test_artifact_carries_a_control_that_touches_a_socket_without_a_lookup():
    """A numeric connect must cost zero DNS -- otherwise 'four per lookup' is unearned."""
    arms = _arms()
    for arm in ("numeric_connect_only/isolated", "numeric_connect_only/net_shared"):
        assert arm in arms, f"the discriminating control {arm} is missing"
        counts = arms[arm]["counts"]
        assert counts["dns"] == 0, (
            f"{arm} produced resolver traffic without resolving a name ({counts}); "
            "the per-lookup attribution does not follow from this artifact"
        )
        assert counts["off_machine"] == 1, (
            f"{arm} did not reach the off-machine detector ({counts}); the control "
            "cannot show the tracer was watching"
        )


def test_one_getaddrinfo_explains_the_v1130_subject_count():
    """The load-bearing claim: one lookup == the four the subject arm recorded."""
    arms = _arms()
    isolated = arms["one_getaddrinfo/isolated"]["counts"]
    shared = arms["one_getaddrinfo/net_shared"]["counts"]
    assert isolated["off_machine"] == 0, isolated
    assert isolated["dns"] == 4, (
        f"one getaddrinfo no longer costs four resolver connects under isolation "
        f"({isolated}); 0629's attribution of the v1130 subject arm rests on this"
    )
    assert shared["dns"] == 3, (
        f"one getaddrinfo no longer costs three resolver connects with a route "
        f"({shared}); the v1130 net-shared control's dns:3 rests on this"
    )

    egress = next(
        c
        for c in json.loads(V1130.read_text())["checks"]
        if c["check"] == "R10-no-egress"
    )
    assert egress["detail"]["subject"]["attempt_counts"]["dns"] == isolated["dns"], (
        "the subject arm this ticket attributes no longer shows the count the probe "
        "explains; re-run the probe before trusting the attribution"
    )
