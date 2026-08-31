"""Every repository guard is wired and exercises the live repository.

A guard that exists without running is worse than no guard: its presence looks
like coverage. These tests derive the inventory from ``bench/check_*.py`` and
refuse both silent gaps — absent from ``make check``, or tested only on toy
fixtures.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUARD = re.compile(r"\bpython3\s+(bench/check_[A-Za-z0-9_]+\.py)\b")
TARGET = re.compile(r"^([A-Za-z0-9_.-]+):(?:\s+(.*))?$")


def guard_scripts(repo: Path) -> set[str]:
    """Every Python guard by repository-relative path."""
    return {path.relative_to(repo).as_posix() for path in (repo / "bench").glob("check_*.py")}


def make_targets(text: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Make target dependencies and recipes, enough to walk ``check``."""
    dependencies: dict[str, list[str]] = {}
    recipes: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        match = TARGET.match(line)
        if match and not line.startswith("\t"):
            current = match.group(1)
            dependencies[current] = (match.group(2) or "").split()
            recipes.setdefault(current, [])
        elif current and line.startswith("\t"):
            recipes[current].append(line.strip())
    return dependencies, recipes


def guards_reached_by_check(makefile: str) -> set[str]:
    """Guard scripts invoked by the transitive dependency tree of ``check``."""
    dependencies, recipes = make_targets(makefile)
    reached: set[str] = set()
    pending = ["check"]
    seen = set()
    while pending:
        target = pending.pop()
        if target in seen:
            continue
        seen.add(target)
        pending.extend(dependencies.get(target, []))
        for recipe in recipes.get(target, []):
            reached.update(GUARD.findall(recipe))
    return reached


def suites_without_live_repo(repo: Path) -> list[str]:
    """Guard suites whose AST never passes the module's ``REPO`` to a call."""
    missing = []
    for guard in sorted(guard_scripts(repo)):
        stem = Path(guard).stem.removeprefix("check_")
        suite = repo / "tests" / f"test_check_{stem}.py"
        if not suite.exists():
            missing.append(suite.relative_to(repo).as_posix())
            continue
        tree = ast.parse(suite.read_text(encoding="utf-8"))
        touches_repo = any(
            isinstance(node, ast.Call)
            and any(isinstance(child, ast.Name) and child.id == "REPO" for child in ast.walk(node))
            for node in ast.walk(tree)
        )
        if not touches_repo:
            missing.append(suite.relative_to(repo).as_posix())
    return missing


def test_unwired_guard_positive_control(tmp_path):
    """A newly added guard absent from the Makefile is named, not skipped."""
    (tmp_path / "bench").mkdir()
    (tmp_path / "bench" / "check_nothing.py").write_text("pass\n")
    missing = guard_scripts(tmp_path) - guards_reached_by_check("check: check-fast\n")
    assert missing == {"bench/check_nothing.py"}


def test_fixture_only_suite_positive_control(tmp_path):
    """A suite that mentions only ``tmp_path`` does not count as a live check."""
    (tmp_path / "bench").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "bench" / "check_nothing.py").write_text("pass\n")
    (tmp_path / "tests" / "test_check_nothing.py").write_text(
        "def test_fixture(tmp_path):\n    assert tmp_path.exists()\n"
    )
    assert suites_without_live_repo(tmp_path) == ["tests/test_check_nothing.py"]


def test_every_guard_is_reached_by_make_check():
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    missing = guard_scripts(REPO) - guards_reached_by_check(makefile)
    assert not missing, f"guard scripts not reached by make check: {sorted(missing)}"


def test_every_guard_suite_exercises_the_live_repository():
    missing = suites_without_live_repo(REPO)
    assert not missing, f"guard suites never exercising REPO: {missing}"


def test_check_prerequisites_are_phony_or_pathless():
    """A `check` prerequisite that names an existing path and is not .PHONY is
    a silent no-op: make reports it up to date and its recipe never runs.

    Caught live on the `tickets` target (t0507, 2026-08-31): it collided with
    the tickets/ directory, printed "up to date", and the erg check it was
    added to enforce never ran — inside the very commit claiming to close that
    ratchet gap. `names` survives today only because no `names` path exists.
    """
    import os
    import re

    text = (REPO / "Makefile").read_text(encoding="utf-8")
    phony = set(re.search(r"^\.PHONY:(.*)$", text, re.M).group(1).split())
    prereqs = re.search(r"^check:(.*)$", text, re.M).group(1).split()
    for target in prereqs:
        assert target in phony or not os.path.exists(REPO / target), (
            f"'check' prerequisite {target!r} collides with an existing path "
            "and is not .PHONY: make reports it up to date and its recipe "
            "never runs"
        )
