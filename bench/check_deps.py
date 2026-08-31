#!/usr/bin/env python3
"""The gate's dependencies are declared, present, and used.

`CLAUDE.md` opens its conventions with "`make check` must be green before any
commit". Twice in two days a fresh container could not run it: the gate reached
its last step and died on `No module named pytest`, and installing pytest then
exposed `No module named numpy` at collection time. Nothing in the tree said
which packages the gate needed, and the failure arrived after eight guards had
printed success — a session reading its own output tail-first can take that run
for green. Ticket 0498.

So this runs FIRST, before any other guard, and it fails loudly by name.

Three checks, in the order they matter:

1. **Present**, in the way the gate actually uses it. The Makefile runs `ruff` as
   a binary and pytest as `python3 -m pytest`, and those are different questions:
   a stale console script on `PATH` satisfies neither an import nor the module
   runner. That is not hypothetical — uninstalling pytest here left
   `~/.local/bin/pytest` behind, and a guard asking only "is there a binary?"
   called the gate ready for a run that would die at collection.
2. **Declared.** Every third-party import under the gate's own scope is named in
   `requirements-check.txt`, and every one under the drivers' scope is named in
   either file. This is the half that keeps the declaration honest as the tree
   moves: a test that grows an import nobody declared is the next fresh
   container's failure, filed early.
3. **Used.** Every declared name is imported somewhere in its scope or invoked by
   the Makefile. A declared dependency with no consumer is the larval form of the
   class ticket 0486 names — `normalize` sat in the registry for a week while
   every driver passed a literal — and it costs nothing to refuse here.

Stdlib only, and it must stay that way: this is the one guard that runs when the
dependencies are missing.
"""

import argparse
import ast
import importlib.util
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The two declarations, and what each one covers.
GATE = "requirements-check.txt"
DRIVERS = "requirements-drivers.txt"

#: The gate's own scope: what `make check` executes. `bench/check_*.py` is the
#: guards themselves; `tests/` is the suite `check-fast` runs.
GATE_SCOPE = ("bench/check_*.py", "tests/*.py")

#: Everything else that is Python and ours: the measurement drivers, and the
#: probe scripts that produced a committed figure.
DRIVER_SCOPE = ("bench/*.py", "verification/probes/*.py")

#: A requirement line, up to any version specifier or marker. The files carry no
#: pins today; parsing for them anyway costs one regex and avoids a silent
#: mis-read the day one appears.
REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")

#: `python3 -m pytest` — the module runner, which needs an importable module and
#: not a script on PATH.
MODULE_RUN = re.compile(r"\bpython3?\s+-m\s+([A-Za-z0-9._-]+)")


def canonical(name: str) -> str:
    """A distribution name and its import name, reduced to one spelling.

    `sentence-transformers` is imported as `sentence_transformers`; PEP 503 says
    the two are the same name, and nothing here needs a per-package table.
    """
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def declared(repo: Path, filename: str) -> dict[str, str]:
    """Requirement names from one declaration file, canonical spelling to source."""
    names: dict[str, str] = {}
    for line in (repo / filename).read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        match = REQUIREMENT.match(stripped)
        if match:
            names[canonical(match.group(1))] = match.group(1)
    return names


def importable(name: str) -> bool:
    """Importable as a top-level module, without importing it."""
    module = name.replace("-", "_")
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def local_modules(repo: Path) -> set[str]:
    """Module names importable from our own trees rather than from a package.

    Several suites put `bench/` or `verification/probes/` on `sys.path` and
    import a driver by module name; those are ours, not dependencies.
    """
    modules: set[str] = set()
    for directory in ("bench", "tests", "verification/probes"):
        root = repo / directory
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.suffix == ".py":
                modules.add(path.stem)
            elif (path / "__init__.py").exists():
                modules.add(path.name)
    return modules


def top_level_imports(path: Path) -> set[str]:
    """Top-level module of every absolute import in one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def third_party(repo: Path, patterns: tuple[str, ...]) -> dict[str, set[str]]:
    """Third-party imports across one scope: canonical name to the files using it."""
    ours = local_modules(repo)
    users: dict[str, set[str]] = {}
    for pattern in patterns:
        for path in sorted(repo.glob(pattern)):
            for module in top_level_imports(path):
                if module in sys.stdlib_module_names or module in ours:
                    continue
                users.setdefault(canonical(module), set()).add(path.relative_to(repo).as_posix())
    return users


def recipes(repo: Path) -> list[str]:
    """The Makefile's recipe lines, stripped of tabs and the silent/ignore prefixes."""
    text = (repo / "Makefile").read_text(encoding="utf-8")
    return [line.strip().lstrip("@-").strip() for line in text.splitlines() if line.startswith("\t")]


def makefile_commands(repo: Path) -> set[str]:
    """Names the Makefile runs as a binary: the first word of each recipe line.

    Ruff has no importer — the lint gate runs the binary — so a declaration is
    consumed by a recipe invoking it just as well as by an import.
    """
    return {canonical(line.split()[0]) for line in recipes(repo) if line and not line.startswith("#")}


def makefile_module_runs(repo: Path) -> set[str]:
    """Names the Makefile runs as `python3 -m NAME`, which needs the module."""
    return {canonical(name) for line in recipes(repo) for name in MODULE_RUN.findall(line)}


def run(repo: Path) -> int:
    gate = declared(repo, GATE)
    drivers = declared(repo, DRIVERS)
    everything = {**drivers, **gate}

    gate_imports = third_party(repo, GATE_SCOPE)
    driver_imports = third_party(repo, DRIVER_SCOPE)
    commands = makefile_commands(repo)
    module_runs = makefile_module_runs(repo)

    def used_as(module: str) -> set[str]:
        """How the tree consumes one requirement — the question presence must ask."""
        how = set()
        if module in gate_imports or module in driver_imports or module in module_runs:
            how.add("import")
        if module in commands:
            how.add("command")
        return how

    #: Present, checked the way the gate uses it. Nothing else runs until it is.
    absent = []
    for module, name in sorted(gate.items()):
        how = used_as(module)
        if "import" in how and not importable(name):
            why = (
                f"`python3 -m {name}` needs it"
                if module in module_runs
                else f"imported by {sorted(gate_imports.get(module, {'the gate'}))[0]}"
            )
            absent.append(f"{name} (not importable; {why})")
        if "command" in how and shutil.which(name) is None:
            absent.append(f"{name} (not on PATH; a recipe invokes it as a command)")
    if absent:
        for what in absent:
            print(f"MISSING: {what}", file=sys.stderr)
        print(
            f"\n`make check` needs {len(gate)} package(s) and cannot run. "
            f"Nothing below this line ran.\n"
            f"    python3 -m pip install -r {GATE}",
            file=sys.stderr,
        )
        return 1

    failures = 0
    for module, users in sorted(gate_imports.items()):
        if module not in gate:
            print(
                f"{module} is imported by {', '.join(sorted(users))} and declared in no "
                f"requirements file. The gate runs those files, so it belongs in {GATE}.",
                file=sys.stderr,
            )
            failures += 1

    for module, users in sorted(driver_imports.items()):
        if module not in everything:
            print(
                f"{module} is imported by {', '.join(sorted(users))} and declared in no "
                f"requirements file. Add it to {DRIVERS}.",
                file=sys.stderr,
            )
            failures += 1

    for module, name in sorted(everything.items()):
        if not used_as(module):
            source = GATE if module in gate else DRIVERS
            print(
                f"{name} is declared in {source} and nothing imports or invokes it. "
                f"A dependency with no consumer is a declaration that will drift.",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(
            f"\n{failures} dependency declaration problem(s). The gate's set is {GATE}, "
            f"the drivers' is {DRIVERS} (ticket 0498).",
            file=sys.stderr,
        )
        return 1

    scanned = len(set(gate_imports) | set(driver_imports))
    print(
        f"{len(gate)} gate requirement(s) present, {len(everything)} declared, "
        f"{scanned} third-party import(s) scanned: the gate can run"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(REPO), help="repository root to check")
    args = parser.parse_args()
    return run(Path(args.repo))


if __name__ == "__main__":
    raise SystemExit(main())
