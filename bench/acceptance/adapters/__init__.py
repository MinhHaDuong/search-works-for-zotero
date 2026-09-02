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


def load(name: str, arena: Path, **opts) -> Target:
    """Build the named target's adapter, or say what the choices were."""
    where = _modules()
    if name not in where:
        raise SystemExit(
            f"no adapter named {name!r}. Available: {', '.join(sorted(where)) or 'none'}"
        )
    module = importlib.import_module(f"{__name__}.{where[name]}")
    return module.build(name, arena, **opts)
