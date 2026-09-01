"""Every check in `bench/smoke_upstream.py` must name a requirement `SPEC.md` still
carries.

The gap this guards: `smoke_upstream.py` labelled a check `R28` after R28 had
already been retired (merged into R15's uninstall clause, DECISIONS.md
2026-08-31), and nothing caught it — the smoke script and the requirements
sheet had no cross-check (ticket 0506). This test is that cross-check.
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
