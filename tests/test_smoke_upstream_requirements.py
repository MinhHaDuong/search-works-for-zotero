"""Every check must name a requirement `SPEC.md` still carries — in both harnesses.

The gap this guards: `smoke_upstream.py` labelled a check `R28` after R28 had
already been retired (merged into R15's uninstall clause, DECISIONS.md
2026-08-31), and nothing caught it — the smoke script and the requirements
sheet had no cross-check (ticket 0506). This test is that cross-check.

Extended for the target-neutral acceptance layer (ticket 0578). That layer is
where assertions now go, so leaving the guard pointed only at the older script
would let the defect walk into the new file behind it — the same asymmetry this
repository has already recorded once, where a gate scoped by hand caught a thing
leaving and not a thing arriving. The two harnesses spell a check differently,
so each gets its own extractor and each extractor gets a positive control that
fails loudly if it stops matching.
"""

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_check_progress():
    spec = importlib.util.spec_from_file_location("cp", REPO / "bench" / "check_progress.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cp = load_check_progress()

#: `check("R28-model-in-data-dir", "R28", ...)` — the requirement is the
#: second positional argument to `check(...)`, quoted.
CHECK_CALL_REQUIREMENT = re.compile(r'return check\(\s*"[^"]*",\s*"(R\d+)"')


def smoke_requirement_labels() -> list[str]:
    text = (REPO / "bench" / "smoke_upstream.py").read_text()
    return CHECK_CALL_REQUIREMENT.findall(text)


def sheet_requirement_ids() -> set[str]:
    text = (REPO / cp.SHEET).read_text()
    return {name for name, _section, _promise in cp.sheet_requirements(text)}


def test_smoke_script_names_at_least_one_requirement():
    # A positive control: the extractor itself must see something, or a
    # regex drift would make every other assertion here vacuously pass.
    assert smoke_requirement_labels(), (
        "no requirement label found in bench/smoke_upstream.py's check() calls — "
        "CHECK_CALL_REQUIREMENT is not matching, or the script stopped naming "
        "requirements"
    )


def test_every_smoke_requirement_is_live():
    live = sheet_requirement_ids()
    stale = sorted(set(smoke_requirement_labels()) - live)
    assert not stale, (
        f"bench/smoke_upstream.py names {stale}, which SPEC.md's requirements "
        f"list does not carry — a retired or misspelled requirement number. "
        f"Live requirements: {sorted(live)}"
    )


#: The layer spells a check as `cid, req = "R10-no-egress", "R10"`, a tuple
#: assignment rather than a call argument, so the older pattern above cannot see
#: it. Matching the layer's own idiom keeps the extractor readable; the count
#: control below is what makes a drift in that idiom loud instead of silent.
LAYER_CALL_REQUIREMENT = re.compile(r'^\s*cid, req = "[^"]*", "(R\d+)"', re.MULTILINE)

LAYER = REPO / "bench" / "acceptance" / "assertions.py"


def layer_requirement_labels() -> list[str]:
    return LAYER_CALL_REQUIREMENT.findall(LAYER.read_text())


def layer_assertion_count() -> int:
    """How many assertions the layer publishes, read from its own registry."""
    body = LAYER.read_text()
    inside = body.split("ALL = {", 1)[1].split("}", 1)[0]
    return inside.count('": check_')


def test_layer_extractor_sees_every_assertion():
    """The positive control, and it is stronger than "found something".

    Requiring the extractor's count to equal the layer's own published assertion
    count means a check written in a different idiom fails this test rather than
    slipping past the requirement cross-check unnoticed.
    """
    found = layer_requirement_labels()
    expected = layer_assertion_count()
    assert expected > 0, "bench/acceptance/assertions.py publishes no assertions in ALL"
    assert len(found) == expected, (
        f"the extractor found {len(found)} requirement labels but the layer publishes "
        f"{expected} assertions in ALL — an assertion is spelled in an idiom "
        f"LAYER_CALL_REQUIREMENT does not match, so it would escape the cross-check below"
    )


def test_every_layer_requirement_is_live():
    live = sheet_requirement_ids()
    stale = sorted(set(layer_requirement_labels()) - live)
    assert not stale, (
        f"bench/acceptance/assertions.py names {stale}, which SPEC.md's requirements "
        f"list does not carry — a retired or misspelled requirement number. "
        f"Live requirements: {sorted(live)}"
    )
