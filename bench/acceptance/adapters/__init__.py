"""One thin adapter per target, and the lookup that finds them.

An adapter declares its target's surfaces and carries only the minimal transport
needed to invoke them: no patch or workaround, no non-default option, no access
the target does not give its own users, and no scoring of a result
(`DECISIONS.md`, ratified 2026-09-02; `SPEC.md` §5.2.8).

**The registry is derived, not written down.** Every module in this package
declares `NAMES` — the targets it can build — and a `build(name, arena, **opts)`
factory. `available()` walks the package rather than reading a hand-kept list,
so an adapter added here is selectable without a second edit, and the
target-neutrality guard finds its target's name without being told.

**Why construction takes an arena.** The residue sweep compares what appeared on
disk against what the adapter declared, so it needs a bounded, harness-owned
directory to sweep. Where a target puts its derived state is the adapter's
business; that the whole of it lands inside a directory the harness can watch is
the harness's. Construction is not one of the seven verbs, so this parameter
changes nothing about the interface.
"""

import ast
import importlib
import pkgutil
from pathlib import Path

from ..interface import Target


def _modules() -> dict[str, str]:
    """Every target this package can build, mapped to the module that builds it."""
    found: dict[str, str] = {}
    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        for name in getattr(module, "NAMES", ()):
            found[name] = info.name
    return found


def available() -> list[str]:
    return sorted(_modules())


def declared_env_names() -> tuple[str, ...]:
    """Every environment variable an adapter declares its target reads.

    AST-parsed rather than imported — the same shape the target-neutrality
    guard uses for `NAMES` — so the layer can forward the run's own
    target-configuration names across the account switch without naming a
    target itself (ticket 0831: `sudo` journals every preserved name, so the
    set must be explicit, and the adapters are the one allowed home for a
    target's vocabulary).
    """
    names: set[str] = set()
    for info in pkgutil.iter_modules(__path__):
        source = Path(__file__).parent / f"{info.name}.py"
        if not source.is_file():
            continue
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "TARGET_ENVIRONMENT"
                       for t in node.targets):
                continue
            for element in getattr(node.value, "elts", []):
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    names.add(element.value)
    return tuple(sorted(names))


def fixtures() -> list[str]:
    """The adapters that are fail-controls rather than targets.

    A module declares `IS_FIXTURE = True` to say its targets exist to drive the
    layer into each of its states. The driver asks this rather than matching a
    name prefix, which is what lets it run the fail-controls without holding any
    fixture's name — the same rule the layer itself is held to.
    """
    found: list[str] = []
    for name, module_name in _modules().items():
        module = importlib.import_module(f"{__name__}.{module_name}")
        if getattr(module, "IS_FIXTURE", False):
            found.append(name)
    return sorted(found)


def load(name: str, arena: Path, **opts) -> Target:
    """Build the named target's adapter, or say what the choices were."""
    where = _modules()
    if name not in where:
        raise SystemExit(
            f"no adapter named {name!r}. Available: {', '.join(sorted(where)) or 'none'}"
        )
    module = importlib.import_module(f"{__name__}.{where[name]}")
    return module.build(name, arena, **opts)
