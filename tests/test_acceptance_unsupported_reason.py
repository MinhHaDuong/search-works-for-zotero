"""An absent verb records why it is absent, and a blank reason is refused.

The defect this closes, in the words of the two adapters that found it
independently: `unsupported` was a set of verb names, so "this target hides a
control it has" and "this target has no such work to control at all" landed in
the same cell. They are opposite findings. One is a gap in a product; the other
is an architecture, and reading the second as the first is how a harness invents
a defect.

**The blank-reason refusal is the load-bearing half**, and it is the one worth a
test. A reason field adapters may leave empty is the same undifferentiated cell
with a longer type: every adapter passes `""`, nothing breaks, and the artifact
says exactly what it said before. So the refusal is checked against a
declaration that omits the reason, and the check fails against any
implementation that merely widened the type.

The other half is that the reason survives to `checks.json`. A reason recorded
in a dataclass and dropped on the way out is a reason nobody reads.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance.adapters import stubs  # noqa: E402
from acceptance.assertions import check_uninstall_removes_declared_state  # noqa: E402
from acceptance.interface import NOT_OFFERED, Declaration  # noqa: E402


def a_declaration(**overrides) -> Declaration:
    fields = dict(
        name="probe", revision="fixture", derived_state_roots=(Path("/nonexistent"),),
        query_transport="in process", default_configuration="the only one",
        process="none",
    )
    fields.update(overrides)
    return Declaration(**fields)


def test_a_reason_is_kept_and_offers_still_works():
    declaration = a_declaration(unsupported={"resume": "nothing maps onto it"})
    assert declaration.offers("pause") is True
    assert declaration.offers("resume") is False
    assert declaration.unsupported["resume"] == "nothing maps onto it"


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_reason_is_refused(blank):
    """The whole point of the field. Widening the type without this passes silently."""
    with pytest.raises(ValueError, match="absent with no reason"):
        a_declaration(unsupported={"resume": blank})


def test_an_unknown_verb_is_still_refused():
    """The old guard keeps working: a name outside the interface is not a verb."""
    with pytest.raises(ValueError, match="not interface"):
        a_declaration(unsupported={"reticulate": "a reason for a verb that is not one"})


def test_the_reason_reaches_the_declaration_as_it_lands_in_the_artifact():
    declaration = a_declaration(unsupported={"resume": "nothing maps onto it"})
    landed = declaration.as_json()
    assert landed["unsupported_verbs"] == ["resume"]
    assert landed["unsupported"] == [{"verb": "resume", "why": "nothing maps onto it"}]


def test_the_reason_reaches_a_not_offered_verdict(tmp_path):
    """A `not-offered` check carries the target's own reason, not only the harness's.

    The two sentences are not interchangeable. The harness's says what it did —
    it found no surface to assert against. The target's says what the absence
    means, and that is the finding a reader is after.
    """
    where = tmp_path / "verbless"
    where.mkdir()
    target = stubs.build("stub-verbless", where)
    check = check_uninstall_removes_declared_state(target, arena=where)
    assert check.result == NOT_OFFERED
    assert check.detail["why_absent"], "the target's own reason must reach the verdict"
    assert check.detail["why_absent"] != check.detail["why"]
