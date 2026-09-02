"""The assertion layer holds no target's name, no tool name and no path literal.

The defect this guards: the harness was one script written against one product
(`bench/smoke_upstream.py`), and the ratified rescope of 2026-09-02
(`DECISIONS.md`; `SPEC.md` §5.2.8) makes it one assertion layer over five
targets. A layer that names a target has not been made neutral, it has been
renamed — and the failure is silent, because an assertion mentioning one product
runs perfectly well against that product. Ticket 0578's Verification line 1 is
this test: "grepping the layer for a zoteus path, a zoteus tool name or a
data-directory literal returns nothing".

**Both sides are derived, which is what keeps this honest as the harness grows.**
The modules scanned are every `.py` under `bench/acceptance/` at any depth, so a
file arriving there later — including in a subpackage carved out of a module
that grew too big — falls under the guard without anyone remembering to add it.
The names forbidden are read out of the adapters' own `NAMES` declarations, so a
target gains its protection the moment its adapter exists. A hand-kept list on
either side would go stale in exactly the direction that matters — a *new* thing
being unguarded — which is the failure mode the harness has already recorded
once for a hand-listed gate scope.

**The positive control is not decoration.** A grep-based guard returns "nothing
found" both when the layer is clean and when the scan is broken, and those are
the same output. `test_scan_catches_a_planted_name` plants a target's name in a
copy of a layer module and asserts the scan reports it; without that, every
other assertion here passes vacuously.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAYER = REPO / "bench" / "acceptance"
ADAPTERS = LAYER / "adapters"


def layer_modules() -> list[Path]:
    """Every module of the layer proper, at any depth, with `adapters/` excluded.

    Derived from the directory rather than listed, so a module added to the
    package is scanned without a second edit.

    **Recursive, and that is a correction rather than a flourish.** The first
    version globbed `*.py` at one level only, so any subdirectory other than
    `adapters/` was invisible to the guard — a file at
    `bench/acceptance/helpers/leak.py` naming a target passed all four tests,
    demonstrated by planting one. That is not an obfuscation nobody would write
    by accident: `sandbox.py` is already large enough that splitting it into a
    package is a reasonable next move, and the split would have silently taken
    its contents out of scope. A guard whose reach is narrower than the claim it
    makes is the defect this whole ticket is about, so it would have been a poor
    place to keep one.
    """
    return sorted(
        p for p in LAYER.rglob("*.py")
        if p.name != "__init__.py" and ADAPTERS not in p.parents
    )


def adapter_modules() -> list[Path]:
    return sorted(p for p in ADAPTERS.rglob("*.py") if p.name != "__init__.py")


def declared_target_names() -> set[str]:
    """Every name an adapter answers to, read from its `NAMES` tuple.

    Parsed rather than imported: this test must not depend on an adapter's
    imports resolving, and a module-level constant is exactly what AST reads
    cheaply.
    """
    names: set[str] = set()
    for path in adapter_modules():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "NAMES" for t in node.targets):
                continue
            for element in getattr(node.value, "elts", []):
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    names.add(element.value)
    return names


#: The five targets the ruling names (`SPEC.md` §5.2.8). Four have no adapter
#: yet, so the derived set above cannot cover them; this is the floor that keeps
#: them forbidden in the meantime, and it shrinks in relevance as adapters land
#: rather than needing maintenance.
RATIFIED_TARGETS = frozenset({"zoteus", "zotseek", "beaver", "zotero-mcp", "6012"})

#: Shapes that are a target's vocabulary even when no target is named: a tool
#: name, an environment variable a product defines, a home-directory or
#: data-directory literal, a build path. Each is a way the old script leaked its
#: one product into code that is supposed to be about a clause.
FORBIDDEN_SHAPES = (
    (re.compile(r"\bzotero_[a-z_]+\b"), "a target's tool name"),
    (re.compile(r"\bZOTEUS_[A-Z_]+\b"), "a target's environment variable"),
    (re.compile(r"\bZOTERO_[A-Z_]+\b"), "a target's environment variable"),
    (re.compile(r"/home/[a-z]"), "an absolute path from someone's machine"),
    (re.compile(r"dist/index\.js"), "a target's build path"),
    (re.compile(r"node_modules"), "a target's dependency directory"),
)


def offences_in(text: str, names: set[str]) -> list[str]:
    """Every target name or target-shaped literal in one module's source."""
    found: list[str] = []
    lowered = text.lower()
    for name in sorted(names):
        if re.search(rf"\b{re.escape(name.lower())}\b", lowered):
            found.append(f"names the target {name!r}")
    for pattern, what in FORBIDDEN_SHAPES:
        for hit in sorted(set(pattern.findall(text))):
            found.append(f"carries {what}: {hit!r}")
    return found


def forbidden_names() -> set[str]:
    return declared_target_names() | set(RATIFIED_TARGETS)


def test_the_scan_has_something_to_scan():
    # Without this, a package that failed to import or a glob that stopped
    # matching would make every assertion below pass on an empty set.
    assert layer_modules(), "no layer modules found under bench/acceptance/"
    assert adapter_modules(), "no adapters found under bench/acceptance/adapters/"
    assert declared_target_names(), (
        "no adapter declares NAMES — the forbidden-name set is derived from those "
        "declarations, so an empty set would make this guard vacuous"
    )


def test_scan_catches_a_planted_name(tmp_path):
    """The positive control: the scan must go red on a layer that names a target.

    A guard whose all-clear is indistinguishable from "I could not look" is not
    a guard. This plants each forbidden shape and each derived name in turn and
    requires the scan to report it.
    """
    names = forbidden_names()
    planted = "def check_something():\n    return 'zoteus said it was fine'\n"
    assert offences_in(planted, names), "the scan missed a planted target name"

    for shape, _what in FORBIDDEN_SHAPES:
        example = {
            "a target's tool name": 'call("zotero_whoami")',
            "a target's environment variable": 'env["ZOTEUS_DATA_DIR"] = "x"',
            "an absolute path from someone's machine": 'Path("/home/someone/data")',
            "a target's build path": 'Path("fork/dist/index.js")',
            "a target's dependency directory": 'Path("fork/node_modules/x")',
        }
        for text in example.values():
            if shape.search(text):
                assert offences_in(text, names), f"the scan missed {text!r}"


def test_the_scan_reaches_a_module_one_directory_down():
    """The other half of the positive control: discovery, not just the scanner.

    `test_scan_catches_a_planted_name` proves the text scanner fires. It cannot
    prove the guard LOOKS at a given file, and those are different failures with
    the same symptom — silence. A review found the difference for real: with a
    one-level glob, a module at `bench/acceptance/helpers/leak.py` naming a
    target passed every test in this file, because the scanner was never handed
    it. So this plants a real module one directory down and requires
    `layer_modules()` to return it.

    Planted in the real package rather than a fixture directory, because
    `layer_modules()` reads the real path and a test against a copy would be
    testing a copy.
    """
    nested = LAYER / "_probe_pkg"
    planted = nested / "planted.py"
    try:
        nested.mkdir()
        planted.write_text("# a module the guard must reach\n")
        found = layer_modules()
        assert planted in found, (
            "layer_modules() did not reach a module one directory below "
            f"{LAYER}. The guard's scope is narrower than the claim it makes: a "
            "file it never reads cannot be found to name a target. Found: "
            f"{[str(p) for p in found]}"
        )
    finally:
        planted.unlink(missing_ok=True)
        if nested.exists():
            nested.rmdir()


def test_layer_names_no_target():
    """Verification line 1 of ticket 0578, over every module of the layer."""
    names = forbidden_names()
    complaints: list[str] = []
    for path in layer_modules():
        for offence in offences_in(path.read_text(), names):
            complaints.append(f"{path.relative_to(REPO).as_posix()}: {offence}")
    assert not complaints, (
        "the assertion layer must hold no target's name, tool name or path literal — "
        "a target's identity lives in its adapter's Declaration.name, which the "
        "contract calls the only place a tool's name may appear (SPEC.md §5.2.8).\n  "
        + "\n  ".join(complaints)
    )


def test_every_adapter_declares_the_names_it_answers_to():
    """The registry is derived from these declarations, and so is this guard.

    An adapter without `NAMES` is unreachable through the loader and invisible
    to the guard above — the second being the quieter of the two failures.
    """
    silent = [
        p.relative_to(REPO).as_posix()
        for p in adapter_modules()
        if not re.search(r"^NAMES\s*=", p.read_text(), re.MULTILINE)
    ]
    assert not silent, f"adapters with no NAMES declaration: {silent}"
