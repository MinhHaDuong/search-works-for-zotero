"""The fixtures that show each assertion can fail. A check never seen red is a habit.

These are not targets. They are deterministic stand-ins built so that each
assertion in `assertions.py` has been driven to every state it can reach, which
is the whole of ticket 0578's Test section: "red first per assertion, and the
red state is produced rather than argued".

Six of them, and the reason there are six rather than three:

`quiet` is the green baseline. An assertion that has only ever failed is as
uninformative as one that has only ever passed, and the residue sweep in
particular is easy to write so that nothing can satisfy it.

`egress-ip` and `egress-name` are R10's fail-control, and they are two because
the detector is two. Inside a namespace with no route, a run that reaches for a
literal address leaves a visible `connect` that failed; a run that reaches for a
*hostname* dies at name resolution and leaves nothing but loopback traffic to
the stub resolver. One control cannot exercise both paths, and a single red
would prove only that one half of the instrument works. `SPEC.md` §5.2.8 names a
deterministic egressing stub as R10's fail-control; nothing here is a real
product, deliberately, so that proof-the-assertion-fires stays separate from any
finding about a real one.

`strays` and `under-declares` are R15's two reds, and they are the same sweep
seen from opposite sides. `strays` is a target misbehaving: the declaration is
honest and the target writes somewhere it should not. `under-declares` is a
declaration being incomplete while the target behaves perfectly normally — it
writes to its own data directory, and simply does not list it. Only the second
one proves the sweep is not letting the declaration grade itself, which is why
both are required.

`verbless` declares verbs absent on purpose, so that the third state has a
fixture of its own rather than being inferred from a target that happens to lack
a surface today.
"""

import socket
from contextlib import contextmanager
from pathlib import Path

from ..interface import Declaration, UnsupportedVerb

NAMES = (
    "stub-quiet",
    "stub-egress-ip",
    "stub-egress-name",
    "stub-strays",
    "stub-under-declares",
    "stub-verbless",
)

#: A literal address off this machine, and a name that cannot resolve. The
#: address is a public resolver chosen because it is stable and uninteresting;
#: the name is in the reserved `.invalid` TLD, so the control tests the lookup
#: without depending on anything real answering.
OFF_MACHINE = ("1.1.1.1", 443)
OFF_MACHINE_NAME = ("example.invalid", 443)


class _Stub:
    """A deterministic target. Every verb records what it did and touches disk only
    where the fixture's point requires it."""

    def __init__(self, name: str, arena: Path, declaration: Declaration):
        self.arena = arena
        self.declaration = declaration
        self._log: list[str] = []

    @contextmanager
    def running(self):
        self._log.append("running")
        yield

    def _require(self, verb: str) -> None:
        if not self.declaration.offers(verb):
            raise UnsupportedVerb(self.declaration.name, verb)

    def _write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def _data_dir(self) -> Path:
        return self.arena / "data"

    def install(self) -> dict:
        self._require("install")
        written = self._write(self._data_dir() / "index.db", "derived state\n")
        return {"installed": True, "wrote": str(written)}

    def uninstall(self) -> dict:
        self._require("uninstall")
        removed = []
        for root in self.declaration.derived_state_roots:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    path.unlink()
                    removed.append(str(path))
        return {"uninstalled": True, "removed": removed}

    def configure(self) -> dict:
        self._require("configure")
        return {"configuration": self.declaration.default_configuration}

    def query(self, q: str, mode: str, limit: int) -> dict:
        self._require("query")
        return {"hits": [], "mode": mode, "limit": limit}

    def status(self) -> dict:
        self._require("status")
        return {"embedding": {"locality": "local", "active": True, "model": "a-local-model"}}

    def pause(self) -> dict:
        self._require("pause")
        return {"paused": True}

    def resume(self) -> dict:
        self._require("resume")
        return {"resumed": True}


class _EgressStub(_Stub):
    """R10's fail-control. It attempts one known off-machine destination per verb
    it is asked for, and swallows the failure — which is precisely the behaviour
    an outcome-only check cannot tell from a target that never reached."""

    #: Set by the subclass: which of the two attempts this fixture makes.
    by_name = False

    def _reach(self) -> str:
        try:
            if self.by_name:
                socket.getaddrinfo(*OFF_MACHINE_NAME)
                return f"resolved {OFF_MACHINE_NAME[0]}"
            socket.create_connection(OFF_MACHINE, timeout=2).close()
            return f"connected {OFF_MACHINE[0]}"
        except OSError as why:
            return f"attempt failed, and the stub carries on: {type(why).__name__}"

    def install(self) -> dict:
        outcome = super().install()
        return {**outcome, "reach": self._reach()}

    def query(self, q: str, mode: str, limit: int) -> dict:
        outcome = super().query(q, mode, limit)
        return {**outcome, "reach": self._reach()}


class _EgressByName(_EgressStub):
    by_name = True


class _StraysStub(_Stub):
    """R15's first red: the declaration is honest, and the target writes outside it."""

    def install(self) -> dict:
        outcome = super().install()
        stray = self._write(self.arena / "elsewhere" / "leftover.cache", "derived state\n")
        return {**outcome, "also_wrote": str(stray)}


def _declaration(name: str, arena: Path, *, roots: tuple[Path, ...],
                 unsupported: frozenset[str] = frozenset()) -> Declaration:
    return Declaration(
        name=name,
        revision="fixture",
        derived_state_roots=roots,
        query_transport="in process; this fixture has no transport and no product behind it",
        default_configuration="the fixture's only configuration",
        process="none; the fixture runs inside the harness process",
        unsupported=unsupported,
        not_derived_state=(),
    )


def build(name: str, arena: Path, **_opts):
    arena = Path(arena)
    data = arena / "data"

    if name == "stub-quiet":
        return _Stub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-egress-ip":
        return _EgressStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-egress-name":
        return _EgressByName(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-strays":
        return _StraysStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-under-declares":
        # The target behaves normally: it writes its derived state to its own
        # data directory and nowhere else. The declaration simply omits it,
        # naming a root the target never uses. Nothing here misbehaves — the
        # list is short, and only a sweep that looks at disk can tell.
        return _Stub(name, arena, _declaration(name, arena, roots=(arena / "declared-but-unused",)))

    if name == "stub-verbless":
        return _Stub(name, arena, _declaration(
            name, arena, roots=(data,),
            unsupported=frozenset({"uninstall", "query", "resume"}),
        ))

    raise SystemExit(f"{name!r} is not one of {list(NAMES)}")
