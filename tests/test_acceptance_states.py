"""The acceptance layer's four verdicts stay four, and stay distinguishable.

Two defects this guards, both of which make an artifact unreadable rather than
wrong-looking.

**A fifth state.** `bench/smoke_upstream.py` uses `observed` for "this check did
not decide", which is a fifth category next to the ratified four and one no
reader can interpret against a gate: it is not a pass, not a failure, and not a
declared absence. The contract rejects any value outside `STATES` at
construction (`interface.py`, `Check.__post_init__`), and this test is the
cross-check that the rejection is real rather than documented.

**A collapsed state.** `not-offered` and `not-run` earn their place only if they
survive into `checks.json` as themselves. Absorbed into green they hide a clause
nothing asserted; absorbed into red they score a target for a surface it never
claimed. Both are the failure ticket 0578's Invariants call "a green that means
could not look", so the artifact is asserted field by field and the exit code is
asserted to move on `fail` alone.

The run these read is driven through the real driver against the fixtures, not
constructed inline, because the states have to survive serialisation and the
summary arithmetic — which is where a collapse would actually happen.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RUN = REPO / "bench" / "acceptance" / "run.py"

sys.path.insert(0, str(REPO / "bench"))

from acceptance.interface import (  # noqa: E402
    FAIL,
    NOT_OFFERED,
    NOT_RUN,
    PASS,
    STATES,
    Check,
    Run,
)


def a_check(result: str) -> Check:
    return Check(
        check="probe", requirement="R10", clause="a clause", falsified_by="a falsifier",
        result=result, target="a-target", verb="status", detail={},
    )


def test_the_four_states_are_exactly_four():
    assert set(STATES) == {PASS, FAIL, NOT_OFFERED, NOT_RUN}


@pytest.mark.parametrize("result", list(STATES))
def test_each_ratified_state_is_accepted(result):
    assert a_check(result).result == result


@pytest.mark.parametrize("rejected", ["observed", "skipped", "unknown", "PASS", ""])
def test_a_fifth_state_is_refused(rejected):
    """The positive control for the rejection: it must actually raise.

    `observed` is first in the list because it is not hypothetical — it is what
    the script this layer replaces writes today, so it is the value most likely
    to be copied across by someone porting a check.
    """
    with pytest.raises(ValueError):
        a_check(rejected)


def test_only_fail_moves_the_exit_code():
    """`not-offered` and `not-run` are not failures of the target.

    A gate that reddened on either would punish a target for lacking a surface,
    or punish the harness's own missing instrument as if the target had failed.
    """
    for quiet in (NOT_OFFERED, NOT_RUN, PASS):
        run = Run(target=_a_declaration(), checks=[a_check(quiet)])
        assert run.exit_code() == 0, f"{quiet} must not turn the gate red"
    run = Run(target=_a_declaration(), checks=[a_check(FAIL)])
    assert run.exit_code() == 1


def test_the_summary_counts_each_state_apart():
    """Neither quiet state may be absorbed into green, which is the subtler bug.

    A summary reporting `{"pass": 3}` for one pass, one not-offered and one
    not-run is not wrong about the failures — it is a page that says a clause
    was satisfied when nothing asserted it.
    """
    run = Run(target=_a_declaration(),
              checks=[a_check(PASS), a_check(NOT_OFFERED), a_check(NOT_RUN)])
    assert run.summary() == {PASS: 1, FAIL: 0, NOT_OFFERED: 1, NOT_RUN: 1}


def _a_declaration():
    from acceptance.interface import Declaration

    return Declaration(
        name="a-target", revision="0", derived_state_roots=(Path("/nonexistent"),),
        query_transport="none", default_configuration="none", process="none",
    )


def drive(adapter: str, tmp_path: Path) -> dict:
    """Run the real driver against a fixture and read its artifact."""
    output = tmp_path / "checks.json"
    done = subprocess.run(
        [sys.executable, str(RUN), "--adapter", adapter,
         "--arena", str(tmp_path / "arena"), "--output", str(output)],
        capture_output=True, text=True, timeout=600, cwd=REPO,
    )
    assert output.is_file(), f"the driver wrote no artifact: {done.stderr[-3000:]}"
    return json.loads(output.read_text())


@pytest.mark.parametrize("adapter", ["stub-verbless"])
def test_an_absent_verb_reaches_the_artifact_as_not_offered(tmp_path, adapter):
    """Ticket 0578's Test section: a stub declaring a verb absent on purpose.

    The state has to be visible in `checks.json` as itself — not inferred by a
    reader from an empty detail, and not equal to either neighbour.
    """
    artifact = drive(adapter, tmp_path)
    states = {c["check"]: c["result"] for c in artifact["checks"]}
    absent = [cid for cid, state in states.items() if state == NOT_OFFERED]
    assert absent, f"no check reported {NOT_OFFERED}: {states}"

    for cid in absent:
        check = next(c for c in artifact["checks"] if c["check"] == cid)
        assert check["result"] not in (PASS, FAIL)
        assert check["verb"], "a not-offered check must name the verb that was missing"
        assert check["detail"]["verb"] == check["verb"]
        assert check["target"] == adapter, "every verdict names its target"
    assert artifact["summary"][NOT_OFFERED] == len(absent)


def test_every_check_names_its_target_and_its_clause(tmp_path):
    """A green is a green for one named target, which is the rescope's whole point."""
    artifact = drive("stub-quiet", tmp_path)
    for check in artifact["checks"]:
        assert check["target"] == "stub-quiet"
        assert check["requirement"].startswith("R")
        assert check["clause"] and check["falsified_by"]
        assert check["result"] in STATES


def test_a_dirty_arena_reports_not_run_rather_than_green(tmp_path):
    """The precondition that turned two red fixtures green while this was written.

    A residue sweep from a baseline that already holds the run's files finds
    nothing new and reports green. Here the arena is pre-populated exactly as a
    re-run would leave it, and the sweep must decline to decide instead.
    """
    sys.path.insert(0, str(REPO / "bench"))
    from acceptance.adapters import load
    from acceptance.assertions import check_residue_inventory

    arena = tmp_path / "arena"
    arena.mkdir()
    (arena / "left-over-from-an-earlier-run").write_text("x")

    target = load("stub-strays", arena)
    verdict = check_residue_inventory(target, arena=arena)
    assert verdict.result == NOT_RUN, (
        "a sweep from a dirty arena must not decide; it found "
        f"{verdict.result} instead"
    )
    assert "arena" in verdict.detail["why"]
