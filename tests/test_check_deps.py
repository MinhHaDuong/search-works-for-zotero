"""The dependency guard, exercised against fixture repositories and the live one.

Same shape as tests/test_check_names.py: each test builds a small repository under
tmp_path and runs the real `run()` against it. The failures worth freezing are the
ones that actually happened — a package the gate needs and the machine does not
have (ticket 0498's own failure, twice in two days), a console script left behind
by an uninstall that made the guard call a broken gate ready, an import nobody
declared, and a declaration nobody imports.

The fixtures deliberately name no binary the test machine has to own: presence is
asked of the gate's own set, so a fixture declaring `ruff` would make this suite
fail on a machine where the guard is right.
"""

import ast
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

MODULE_GATE = "check:\n\tpython3 -m pytest tests/ -q\n"


def load():
    spec = importlib.util.spec_from_file_location("cd", REPO / "bench" / "check_deps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cd = load()


def build(root, gate: str, drivers: str = "", files=None, makefile: str = MODULE_GATE):
    """A fixture repository: two declarations, a Makefile, and some Python."""
    (root / "requirements-check.txt").write_text(gate, encoding="utf-8")
    (root / "requirements-drivers.txt").write_text(drivers, encoding="utf-8")
    (root / "Makefile").write_text(makefile, encoding="utf-8")
    for name, source in (files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return root


def test_a_declared_and_used_set_passes(tmp_path):
    build(tmp_path, "pytest\n", files={"tests/test_a.py": "import pytest\n"})
    assert cd.run(tmp_path) == 0


def test_a_missing_gate_package_fails(tmp_path):
    """0498's failure: the package the gate needs is not on the machine."""
    build(tmp_path, "pytest\nnotapackage-xyz\n",
          files={"tests/test_a.py": "import pytest\nimport notapackage_xyz\n"})
    assert cd.run(tmp_path) == 1


def test_a_console_script_does_not_satisfy_a_module_import(tmp_path, monkeypatch):
    """The hole this guard fell into first.

    Uninstalling pytest left `~/.local/bin/pytest` behind. A presence check that
    accepted any binary on PATH called the gate ready for a run that then died at
    collection — which is the exact failure 0498 was filed on.
    """
    binaries = tmp_path / "bin"
    binaries.mkdir()
    script = binaries / "ghostpkg"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(binaries))
    build(tmp_path, "ghostpkg\n", makefile="check:\n\tpython3 -m ghostpkg\n")
    assert cd.run(tmp_path) == 1


def test_an_undeclared_import_in_the_gate_scope_fails(tmp_path):
    build(tmp_path, "pytest\n", files={"tests/test_a.py": "import pytest\nimport scipy\n"})
    assert cd.run(tmp_path) == 1


def test_a_driver_import_declared_in_the_drivers_file_passes(tmp_path):
    """The split is the point: a driver's dependency is not the gate's, and the
    gate does not have to be installable alongside a model runtime to run."""
    build(
        tmp_path,
        "pytest\n",
        drivers="torch\n",
        files={"tests/test_a.py": "import pytest\n", "bench/embed.py": "import torch\n"},
    )
    assert cd.run(tmp_path) == 0


def test_a_gate_import_declared_only_for_the_drivers_fails(tmp_path):
    """`make check` runs tests/, so the gate's own set has to carry what they import."""
    build(
        tmp_path,
        "pytest\n",
        drivers="numpy\n",
        files={"tests/test_a.py": "import pytest\nimport numpy\n"},
    )
    assert cd.run(tmp_path) == 1


def test_a_declaration_with_no_consumer_fails(tmp_path):
    """Ticket 0486's class, caught at the declaration rather than a week later."""
    build(tmp_path, "pytest\nnumpy\n", files={"tests/test_a.py": "import pytest\n"})
    assert cd.run(tmp_path) == 1


def test_our_own_modules_are_not_dependencies(tmp_path):
    """Suites put bench/ on sys.path and import a driver by name; that is ours."""
    build(
        tmp_path,
        "pytest\n",
        files={"bench/registry.py": "", "tests/test_a.py": "import pytest\nimport registry\n"},
    )
    assert cd.run(tmp_path) == 0


def test_a_binary_is_consumed_by_the_recipe_that_invokes_it(tmp_path):
    """Ruff has no importer. The lint recipe naming it is the consumer."""
    build(tmp_path, "pytest\n", makefile="lint:\n\truff check bench/\n")
    assert "ruff" in cd.makefile_commands(tmp_path)
    assert "pytest" not in cd.makefile_commands(tmp_path)


def test_the_module_runner_is_read_as_an_import(tmp_path):
    build(tmp_path, "pytest\n")
    assert cd.makefile_module_runs(tmp_path) == {"pytest"}


def test_the_import_name_and_the_distribution_name_are_one_name():
    assert cd.canonical("sentence_transformers") == cd.canonical("sentence-transformers")


def test_the_guard_imports_nothing_it_might_be_missing():
    """It runs when the dependencies do not, so it may use the standard library only."""
    tree = ast.parse((REPO / "bench" / "check_deps.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names)


def test_the_live_repository_declares_what_it_needs():
    assert cd.run(REPO) == 0
