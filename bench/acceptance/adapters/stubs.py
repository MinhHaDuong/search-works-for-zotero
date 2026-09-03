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

**Goal 2's five, added with the durability assertions.** Each is one cause, so a
red names a defect rather than a region.

`churns-on-resync` is the shipped 92,7 % defect in miniature: a resync of
identical bytes that recomputes anyway. `verifies-nothing-on-resync` is its
opposite and the reason that clause carries two detectors — it recomputes
nothing because it never looked, which a `done`-only check reports as the same
green as a correct target. `recomputes-whole-library-on-edit` re-embeds
everything when one title changes, which is R3's proportionality clause failing
at the other end.

`corrupts-on-company` leaves the index unreadable *after* both processes have
stopped, and it is written that way on purpose: a pair can answer perfectly
while it is live and still wreck the file behind it, so the third-process
detector is the only one that can see this class, and a fixture that failed
during the pair phase would leave it unexercised. `duplicates-work-on-company`
answers every query correctly and simply redoes the work — invisible in a reply,
visible only in the counters, which is why R13 is two clauses and not one.

**The ledger is a file, not an attribute**, and that is what makes the R13
fixtures mean anything. Two adapter instances over one arena are two processes
on one data directory; counters held in memory would be two independent ledgers
and the duplicate-work fixture could not express its defect at all.

**Goal 1's remaining three, added with the pause and configure assertions.**

`ignores-pause` offers the control, answers success from it, and keeps working.
The finding it models is not a missing switch — a missing switch is
`not-offered`, which `verbless` already covers, and it is a different finding
rather than a milder one. `forgets-pause-on-restart` is the same control done
almost right: the work does stop, and the stopping is kept where a restart loses
it, which is the state R22's clause names restarts to exclude.

`configures-blind` accepts a configuration without trying it and fails at the
query that first invokes it. The order is its entire content: the same target
failing at `configure` would be green, because failing loudly before use is what
R31 asks for.

**The pause marker is a file for the same reason the ledger is.** A pause held in
an adapter attribute survives a `running()` block by accident of the process, so
the restart clause could not be failed by any fixture and could not be passed by
any target — the assertion would be reading the harness. `forgets-pause-on-restart`
is exactly the fixture that would then be impossible to write.
"""

import json
import socket
from contextlib import contextmanager
from pathlib import Path

from ..durability import (
    EDIT_ONE_ITEM,
    RESET_TO_SEEDED_INDEX,
    RESTAMP_NEWER,
    RESTAMP_OLDER,
    RESYNC_IDENTICAL_BYTES,
)
from ..interface import Declaration, UnsupportedVerb

#: These are fixtures, not targets: they exist to drive the layer into each of
#: its states, and a gate runs them to prove the assertions still fire. Declared
#: here rather than recognised by a name prefix, so the driver can ask the
#: adapters package which targets are fixtures without holding any of their
#: names itself.
IS_FIXTURE = True

NAMES = (
    "stub-quiet",
    "stub-egress-ip",
    "stub-egress-name",
    "stub-strays",
    "stub-under-declares",
    "stub-verbless",
    "stub-remote-embedder",
    "stub-uninstall-leaves-residue",
    "stub-churns-on-resync",
    "stub-verifies-nothing-on-resync",
    "stub-recomputes-whole-library-on-edit",
    "stub-corrupts-on-company",
    "stub-duplicates-work-on-company",
    "stub-abandons-foreign-stamp",
    "stub-ignores-pause",
    "stub-forgets-pause-on-restart",
    "stub-configures-blind",
)

#: The fixture library: four items of three sections each. These are the
#: fixture's own contents, not a design number — every assertion that needs the
#: section count reads it out of the perturbation's event rather than knowing it.
ITEMS = ("item-a", "item-b", "item-c", "item-d")
SECTIONS = 3

#: A literal address off this machine, and a name that cannot resolve. The
#: address is a public resolver chosen because it is stable and uninteresting;
#: the name is in the reserved `.invalid` TLD, so the control tests the lookup
#: without depending on anything real answering.
OFF_MACHINE = ("1.1.1.1", 443)
OFF_MACHINE_NAME = ("example.invalid", 443)


class _Stub:
    """A deterministic target. Every verb records what it did and touches disk only
    where the fixture's point requires it."""

    #: This fixture's ledger is written synchronously, so the durability layer
    #: need not wait a real target's polling interval to see it stationary.
    #: Adapter-declared, like the lifecycle and the perturbation hook.
    settle_poll_s = 0.01

    def __init__(self, name: str, arena: Path, declaration: Declaration):
        self.arena = arena
        self.declaration = declaration
        self._log: list[str] = []
        self._live = False

    # -- the ledger, on disk because two processes must share one -------------

    def _ledger(self) -> Path:
        return self._data_dir() / "ledger.json"

    def _counters(self) -> dict[str, int]:
        path = self._ledger()
        if not path.is_file():
            return {}
        try:
            return {str(k): int(v) for k, v in json.loads(path.read_text()).items()}
        except (ValueError, OSError):
            return {}

    def _bump(self, **counters: int) -> dict[str, int]:
        """Move counters and persist them, the way a ledger transition would."""
        current = self._counters()
        for name, by in counters.items():
            current[name.replace("__", ".")] = current.get(name.replace("__", "."), 0) + by
        self._write(self._ledger(), json.dumps(current, indent=2))
        return current

    def _first_build(self) -> None:
        """The work a first start does, recorded under the `new` trigger."""
        if self._ledger().is_file():
            return
        self._bump(work__record__new__done=len(ITEMS),
                   work__embed__new__done=len(ITEMS) * SECTIONS)

    @contextmanager
    def running(self):
        self._log.append("running")
        self._live = True
        self._first_build()
        self._on_start()
        try:
            yield
        finally:
            self._live = False
            self._on_stop()

    def _on_start(self) -> None:
        """What this fixture does when its process starts. Nothing, here."""

    def _on_stop(self) -> None:
        """What this fixture leaves behind when its process ends. Nothing, here."""

    # -- perturbation: adapter-declared harness setup, not an eighth verb -----

    def perturb(self, what: str) -> dict:
        if what == EDIT_ONE_ITEM:
            return self._edit_one_item()
        if what == RESYNC_IDENTICAL_BYTES:
            return self._resync_identical_bytes()
        if what in (RESTAMP_OLDER, RESTAMP_NEWER):
            return self._restamp(what)
        if what == RESET_TO_SEEDED_INDEX:
            return self._reset_to_seeded_index()
        raise NotImplementedError(f"this fixture cannot do {what!r}")

    def _reset_to_seeded_index(self) -> dict:
        """Put the index back to a settled one under the stamp this fixture writes.

        R23's two directions are two experiments and each needs this state to
        start from. Implemented on the base so every fixture inherits it: a
        fixture earns its place by modelling one defect, and none of them models
        an inability to be reset.
        """
        stamped = self._data_dir() / "stamp"
        was = stamped.read_text() if stamped.is_file() else None
        if stamped.is_file():
            stamped.unlink()
        restored = self._write(self._data_dir() / "index.db", "derived state\n")
        return {"perturbation": RESET_TO_SEEDED_INDEX, "stamp_before_reset": was,
                "index": restored.name, "file_deleted_by_hand": False}

    def _edit_one_item(self) -> dict:
        """One title changes: its record recomputes, and its sections re-embed.

        Unless this fixture has been stopped, in which case the change is noticed
        and no work is done — which is what R22 asks of a target, and what makes
        `stub-quiet` the green baseline for the pause clauses as well.
        """
        event = {"perturbation": EDIT_ONE_ITEM, "item": ITEMS[0], "sections": SECTIONS}
        if self._is_paused():
            return {**event, "work_done_while_stopped": False}
        self._bump(work__record__edit__done=1, work__embed__edit__done=SECTIONS)
        return event

    def _resync_identical_bytes(self) -> dict:
        """Signals move, keys are verified, nothing is recomputed."""
        self._bump(work__record__resync__noop=len(ITEMS),
                   work__embed__resync__noop=len(ITEMS) * SECTIONS)
        return {"perturbation": RESYNC_IDENTICAL_BYTES, "items": len(ITEMS),
                "bytes_changed": 0}

    def _restamp(self, direction: str) -> dict:
        """The index is stamped under another schema version. This one keeps serving."""
        self._write(self._data_dir() / "stamp", direction)
        return {"perturbation": direction, "file_deleted_by_hand": False}

    def _require(self, verb: str) -> None:
        # The lifecycle guard, and it is here because its absence was a real
        # defect rather than a hypothetical one. A stub needs no process, so a
        # layer that called verbs outside `running()` passed every fixture and
        # then crashed against the first target with a real lifecycle — and the
        # two residue assertions did worse than crash: they called `install()`
        # on a target whose state only materializes once the process starts, so
        # they graded a state they had prevented from existing. Enforcing the
        # lifecycle in the fail-controls is what makes `make acceptance-fixtures`
        # able to see that class at all.
        if not self._live:
            raise RuntimeError(
                f"{self.declaration.name}: {verb!r} was called outside running(). "
                "Every verb reaches a target through its process; an assertion that "
                "reaches around the lifecycle measures a target that was never started."
            )
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
        return {"hits": self._hits(limit), "mode": mode, "limit": limit}

    def _hits(self, limit: int) -> list:
        """What this fixture serves. One row per item it holds, capped at `limit`."""
        return [{"item": key} for key in ITEMS][:limit]

    def status(self) -> dict:
        self._require("status")
        return {
            "embedding": {"locality": "local", "active": True, "model": "a-local-model"},
            "work": self._counters(),
        }

    # -- the durable pause -----------------------------------------------------

    def _pause_marker(self) -> Path:
        """Where this fixture keeps the fact that it was stopped.

        On disk and under the data directory, so it is derived state like
        everything else here: uninstall removes it with the rest, and a restart
        finds it. An attribute would survive a `running()` block for reasons that
        have nothing to do with the target, which is the one thing R22's restart
        clause must not be allowed to read.
        """
        return self._data_dir() / "paused"

    def _is_paused(self) -> bool:
        return self._pause_marker().is_file()

    def pause(self) -> dict:
        self._require("pause")
        self._write(self._pause_marker(), "background work is stopped\n")
        return {"paused": True}

    def resume(self) -> dict:
        self._require("resume")
        marker = self._pause_marker()
        if marker.is_file():
            marker.unlink()
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


class _RemoteEmbedderStub(_Stub):
    """R10's other fail-control: a default configuration whose embedder is hosted.

    It makes no network call — the point is the *reported* configuration, which
    is what the local-by-default clause reads. A target can be perfectly quiet
    on the wire during a smoke run and still default to a hosted provider.
    """

    def status(self) -> dict:
        return {"embedding": {"locality": "remote", "active": True,
                              "model": "a-hosted-model"}}


class _UninstallLeavesResidueStub(_Stub):
    """R15's uninstall fail-control: the surface runs and its own state survives.

    Distinct from the two residue fixtures, which are about the declaration's
    completeness. Here the declaration is honest and complete, the uninstall verb
    is genuinely offered, and it simply does not finish the job — which is the
    literal reading of "after uninstall, none of that state may remain".
    """

    def uninstall(self) -> dict:
        outcome = super().uninstall()
        kept = self._write(self._data_dir() / "survivor.db", "still here\n")
        return {**outcome, "kept": str(kept)}


class _ChurnsOnResyncStub(_Stub):
    """R3's first red, and the shipped defect in miniature.

    The bytes are identical and it re-embeds anyway. The counters say so under
    the `done` outcome, which is the whole point: the defect this fixture models
    ran in production for a long time precisely because nothing read them.
    """

    def _resync_identical_bytes(self) -> dict:
        self._bump(work__record__resync__noop=len(ITEMS),
                   work__embed__resync__done=len(ITEMS) * SECTIONS)
        return {"perturbation": RESYNC_IDENTICAL_BYTES, "items": len(ITEMS),
                "bytes_changed": 0, "and_re_embedded_anyway": True}


class _VerifiesNothingOnResyncStub(_Stub):
    """R3's second red, and the reason that clause needs two detectors.

    It recomputes nothing — and it also verifies nothing, because its reconcile
    tick never ran. A check reading only the `done` outcome reports this as the
    same clean green a correct target earns, which is the failure mode this whole
    harness exists to refuse: an all-clear indistinguishable from "I could not
    look".
    """

    def _resync_identical_bytes(self) -> dict:
        return {"perturbation": RESYNC_IDENTICAL_BYTES, "items": 0,
                "bytes_changed": 0, "verification_ran": False}


class _RecomputesWholeLibraryOnEditStub(_Stub):
    """R3's third red: one title changes and the whole library re-embeds.

    Proportionality failing at the size-of-the-library end, which is the clause's
    own wording — the cost tracks the library rather than the change.
    """

    def _edit_one_item(self) -> dict:
        self._bump(work__record__edit__done=1,
                   work__embed__edit__done=len(ITEMS) * SECTIONS)
        return {"perturbation": EDIT_ONE_ITEM, "item": ITEMS[0], "sections": SECTIONS}


class _CorruptsOnCompanyStub(_Stub):
    """R13's first red, and it wrecks the index only once both processes are gone.

    Written this way deliberately. A pair that fails while it is live is caught
    by the clause's first detector; a pair that answers perfectly and leaves the
    file unreadable is caught only by the third process, and that detector would
    otherwise never be seen red. The marker is written when a second process
    stops, so the first two answer normally and the third does not.
    """

    # Concurrency is the condition, not restart count. The first draft wrecked
    # the index after any two process *stops*, which also made this fixture red
    # on R23 — a clause it is not about. A fail-control must fail the clause it
    # was built for and no other, or the artifact stops naming causes.
    #
    # Both counters live in the ledger rather than in files of their own, and are
    # only touched while the ledger exists: a marker recreated after `uninstall`
    # had emptied the declared root turned this fixture red on R15's uninstall
    # clause as well. Neither is a `work.<stage>.<trigger>.<outcome>` name, so no
    # durability clause reads them.
    def _on_start(self) -> None:
        if not self._ledger().is_file():
            return
        if self._bump(live=1).get("live", 0) >= 2:
            self._bump(saw_company=1)

    def _on_stop(self) -> None:
        # The damage becomes visible only once BOTH processes have gone, which is
        # the point of this fixture: a pair that answers perfectly while it is
        # live and leaves the file unreadable behind it is seen by the third
        # process or by nothing. Marking the index unreadable the moment a second
        # process started put the red in the pair phase instead and left the
        # third-process detector unproven.
        if not self._ledger().is_file():
            return
        current = self._bump(live=-1)
        if current.get("live", 0) <= 0 and current.get("saw_company", 0):
            self._bump(corrupt=1)

    def query(self, q: str, mode: str, limit: int) -> dict:
        self._require("query")
        if self._counters().get("corrupt", 0):
            raise RuntimeError(
                "the index cannot be read: two concurrent processes left it in a "
                "state this fixture cannot open")
        return super().query(q, mode, limit)


class _DuplicatesWorkOnCompanyStub(_Stub):
    """R13's second red: the second process redoes work the first had finished.

    It answers every query correctly while doing it, which is the reason the
    clause is read from the counters and not from the replies. Its ledger is
    shared with the first process because it is a file in the data directory,
    so the duplication is visible where a real one would be.
    """

    def _first_build(self) -> None:
        self._bump(work__record__new__done=len(ITEMS),
                   work__embed__new__done=len(ITEMS) * SECTIONS)


class _AbandonsForeignStampStub(_Stub):
    """R23's red: a foreign stamp is declined, a fresh empty index opened, nothing served.

    No file is deleted — the original is set aside under another name, which is
    what makes this the interesting failure rather than an obvious one. Every
    damage-prevention assertion passes against this behaviour; only the serving
    clause sees it.
    """

    def _restamp(self, direction: str) -> dict:
        stamped = self._data_dir() / "stamp"
        self._write(stamped, direction)
        sidelined = self._data_dir() / f"index.db.incompatible-{direction}"
        index = self._data_dir() / "index.db"
        if index.is_file():
            index.rename(sidelined)
        return {"perturbation": direction, "file_deleted_by_hand": False,
                "sidelined_as": sidelined.name}

    def _hits(self, limit: int) -> list:
        if (self._data_dir() / "stamp").is_file():
            return []
        return super()._hits(limit)


class _IgnoresPauseStub(_Stub):
    """R22's first red: the control is offered, it answers, and the work goes on.

    It writes the marker like any other fixture and then declines to read it, so
    the defect is exactly the one an outcome-blind check cannot see: `pause`
    returns `{"paused": True}`, the reply is honest about having been called, and
    nothing stopped. A check reading the verb's reply grades this green.
    """

    def _is_paused(self) -> bool:
        return False


class _ForgetsPauseOnRestartStub(_Stub):
    """R22's second red: the control holds while the process lives, and no longer.

    The pause is real — a change made in the same process creates no work — and
    the fact of it is dropped the next time the process starts. That is the
    common shape of the defect rather than an invented one: a switch kept in a
    running engine's state costs nothing to implement and looks correct in every
    test that does not restart anything.
    """

    def _on_start(self) -> None:
        marker = self._pause_marker()
        if marker.is_file():
            marker.unlink()


class _ConfiguresBlindStub(_Stub):
    """R31's red: the configuration is accepted without being tried, and cannot serve.

    `configure` returns success and validates nothing; the query that first
    invokes what was configured is where the failure surfaces. The order is the
    whole fixture — the same target raising at `configure` would be green,
    because failing loudly before use is R31's other branch.
    """

    #: Whether this instance has been handed the configuration it never checked.
    #: The failure is bounded to that, and the bound is what keeps the fixture to
    #: one cause: a stub whose query raised unconditionally also failed R13's
    #: both-answer clause, which is a true verdict about the stub and a false lead
    #: about the defect — a red naming a region instead of a cause.
    _configured = False

    def configure(self) -> dict:
        self._require("configure")
        self._configured = True
        return {"configuration": self.declaration.default_configuration,
                "validated": False}

    def query(self, q: str, mode: str, limit: int) -> dict:
        self._require("query")
        if not self._configured:
            return super().query(q, mode, limit)
        raise RuntimeError(
            "the configured embedder could not be loaded on this machine, reported "
            "when the query invoked it — which is after the configuration was accepted"
        )


def _declaration(name: str, arena: Path, *, roots: tuple[Path, ...],
                 unsupported: dict[str, str] | None = None) -> Declaration:
    return Declaration(
        name=name,
        revision="fixture",
        derived_state_roots=roots,
        query_transport="in process; this fixture has no transport and no product behind it",
        default_configuration="the fixture's only configuration",
        process="none; the fixture runs inside the harness process",
        unsupported=unsupported or {},
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

    if name == "stub-remote-embedder":
        return _RemoteEmbedderStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-uninstall-leaves-residue":
        return _UninstallLeavesResidueStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-churns-on-resync":
        return _ChurnsOnResyncStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-verifies-nothing-on-resync":
        return _VerifiesNothingOnResyncStub(
            name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-recomputes-whole-library-on-edit":
        return _RecomputesWholeLibraryOnEditStub(
            name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-corrupts-on-company":
        return _CorruptsOnCompanyStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-duplicates-work-on-company":
        return _DuplicatesWorkOnCompanyStub(
            name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-abandons-foreign-stamp":
        return _AbandonsForeignStampStub(
            name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-ignores-pause":
        return _IgnoresPauseStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-forgets-pause-on-restart":
        return _ForgetsPauseOnRestartStub(
            name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-configures-blind":
        return _ConfiguresBlindStub(name, arena, _declaration(name, arena, roots=(data,)))

    if name == "stub-verbless":
        return _Stub(name, arena, _declaration(
            name, arena, roots=(data,),
            unsupported={
                "uninstall": "declared absent on purpose, so the third state has a "
                             "fixture of its own rather than being inferred from a "
                             "target that happens to lack a surface today",
                "query": "declared absent on purpose, as above",
                "resume": "declared absent on purpose, as above",
                # Goal 1's two later clauses need the third state as much as the
                # earlier ones do, and for the sharper reason: R22 is *verified
                # absent* upstream, so not-offered is the state the layer will
                # actually report against a real target, and a state no fixture
                # produces is a state nobody has checked survives the artifact.
                "pause": "declared absent on purpose, as above; a target with no such "
                         "control is a different finding from one whose control does "
                         "nothing, and both must be reachable",
                "configure": "declared absent on purpose, as above",
            },
        ))

    raise SystemExit(f"{name!r} is not one of {list(NAMES)}")
