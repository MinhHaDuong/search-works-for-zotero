"""The assertion layer. One clause per assertion, phrased over the seven verbs.

`SPEC.md` §3 owns R10 and R15; `SPEC.md` §5.2.8 owns this harness;
`DECISIONS.md`'s ratified entry of 2026-09-02 owns the ruling. None is restated
here — this module cites addresses and asserts clauses.

**What this file may not contain**, and the reason it is checked rather than
promised: no target's name, no tool name, no path literal, no data-directory
literal. A target's identity lives in its adapter's `Declaration.name`, which
the contract calls the only place a tool's name is allowed to appear.
`tests/test_acceptance_layer_is_target_neutral.py` derives the forbidden names
from the adapters themselves and greps every module in this package, so a file
arriving here later falls under the guard without anyone remembering to add it.

**The normalized status shape**, and why it is declared here rather than in
`interface.py`. R10's local-by-default clause reads a target's own report of
which embedder is in effect. The contract fixes the verbs and the states; it
deliberately fixes nothing about what `status()` returns, and it says in as many
words that three things live there and nothing else. So the two keys this layer
actually reads are declared here, as the layer's requirement on an adapter,
rather than by growing the settled contract a fourth section:

    status() -> {"embedding": {"locality": "local" | "remote" | "none",
                               "active": bool,
                               "model": str | None}}

An adapter that cannot answer sets `locality` to None, and the assertion reports
`not-run` rather than inventing a verdict. Nothing else in `status()` is read by
this layer, and an adapter is free to return whatever else its target reports.

**Why the residue sweep exists at all.** R15 makes a target declare every
location in which it creates derived state. A declared list nobody checks for
completeness says no more than a location does — it grades itself. So every
R15 assertion here sweeps an arena the harness owns and compares what appeared
against what was declared, rather than reading the declaration back.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from .interface import (
    FAIL,
    PASS,
    Check,
    Target,
    not_offered,
    not_run,
)
from .sandbox import choose, run_traced

#: The three retrieval-mode names R33 uses, in the layer's vocabulary. An
#: adapter maps them onto whatever its target calls them; the layer never sees
#: the target's spelling.
MEANING = "meaning"

#: The verbs R10's egress clause drives, in the order ticket 0578's Action 3
#: names them. A verb the target does not offer is skipped and recorded as
#: skipped: one absent verb must not turn the whole clause into `not-offered`,
#: because the clause is about what the offered verbs do.
EGRESS_VERBS = ("install", "configure", "resume", "query")


# --------------------------------------------------------------------------
# The arena: what the sweep compares against.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    """Every regular file under a root, by path. The sweep's unit of comparison.

    **A root may itself be a file, and `os.walk` yields nothing for one.** A
    declared derived-state root is a directory whenever the target owns a
    directory, which was true of the first two targets and is not true of a
    target embedded in a host application: such a target keeps its sidecar
    database beside the host's own, inside a directory belonging to the host, so
    the only thing it can declare is the file. Without the first branch below,
    `os.walk` is handed a regular file, finds nothing, and the uninstall
    survivor check reports zero survivors — green — while the state sits on
    disk. Measured on a real target (ticket 0586): three files survived the
    removal and the check came back `pass`. That is a false green of exactly the
    class this layer exists to catch, so it is fixed here rather than worked
    around in one adapter.
    """

    root: Path
    files: frozenset[Path]

    @classmethod
    def of(cls, root: Path) -> "Snapshot":
        found: set[Path] = set()
        if root.is_file():
            found.add(root)
        for base, _dirs, names in os.walk(root):
            for name in names:
                found.add(Path(base) / name)
        return cls(root=root, files=frozenset(found))

    def since(self, earlier: "Snapshot") -> frozenset[Path]:
        return self.files - earlier.files


def dirty(arena: Path) -> str | None:
    """Why this arena cannot host a residue sweep, or None if it can.

    A sweep compares what appeared against what was declared, so it needs a
    baseline that nothing has written to. An arena carrying files from an
    earlier run has already absorbed the very residue the sweep is looking for:
    `created` comes back empty and the check reports green.

    This is not hypothetical and it is not a caller's mistake to shrug at. It
    happened twice while this layer was being built — once because another
    assertion wrote to the shared arena first, once because a re-run reused the
    previous run's directory — and both times the fixture built to make the
    sweep go red passed instead. A precondition that turns a red into a green
    when it is violated has to be checked, not documented.
    """
    if not arena.exists():
        return None
    if any(Snapshot.of(arena).files):
        return (
            f"the arena {arena} already holds files, so a sweep from it would compare "
            "against a baseline that already absorbed what it is looking for; a dirty "
            "arena turns this check green rather than red, so it is not run"
        )
    return None


def _under(path: Path, roots: tuple[Path, ...]) -> bool:
    """True when `path` lies at or below one of `roots`."""
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def residue(created: frozenset[Path], target: Target) -> list[Path]:
    """Files the run created that the declaration does not account for.

    Two escapes are honoured and no others: a declared derived-state root, and a
    path the adapter argued is not derived state at all (user-authored library
    data, externally supplied configuration — R15 names both). Everything else
    is residue, whether the target strayed or the declaration was short.
    """
    declared = tuple(target.declaration.derived_state_roots)
    exempt = tuple(path for path, _why in target.declaration.not_derived_state)
    return sorted(p for p in created if not _under(p, declared) and not _under(p, exempt))


# --------------------------------------------------------------------------
# R10 — locality.
# --------------------------------------------------------------------------


def check_no_egress(target: Target, *, arena: Path, log_dir: Path,
                    drive_argv: list[str]) -> Check:
    """R10: nothing leaves this machine, and nothing tries to.

    Three arms, because two of them are what make the third readable.

    1. A net-shared control drives a harness-owned probe that reaches for a
       literal off-machine address and for a hostname. Both detectors must fire
       and the route must be intact. If they do not, the instrument is not
       working and this check reports `not-run` — never green.
    2. The same probe under isolation. Both detectors must still fire: an
       attempt is visible even when it cannot succeed, which is the observation
       the clause turns on.
    3. The target itself, under isolation, driving every offered verb among
       install, configure, resume and query. Zero attempts on both detectors is
       the pass.

    Observing no egress on a machine that HAS a route asserts the default rather
    than the clause, which is why arm 3 never runs net-shared.
    """
    cid, req = "R10-no-egress", "R10"
    clause = ("without an explicit opt-in, library text and queries do not leave this "
              "machine, and no connection to a destination off it is attempted")
    falsified = ("any connection attempted to an address off this machine, or any name "
                 "lookup, during a default-configuration run")

    mechanism, why = choose()
    if mechanism is None:
        return not_run(cid, req, clause, falsified, target, "query", why or "no mechanism")

    driven = [v for v in EGRESS_VERBS if target.declaration.offers(v)]
    skipped = [v for v in EGRESS_VERBS if not target.declaration.offers(v)]
    if not driven:
        return not_offered(cid, req, clause, falsified, target, "query")

    probe = [_python(), "-c", _EGRESS_PROBE]
    shared = run_traced(probe, mechanism=mechanism, network_shared=True,
                        log_dir=log_dir, tag="control-shared")
    isolated = run_traced(probe, mechanism=mechanism, network_shared=False,
                          log_dir=log_dir, tag="control-isolated")

    control = {
        "net_shared": shared.as_json(),
        "isolated": isolated.as_json(),
        "why_both": (
            "the shared arm proves the tracer sees attempts and the machine has a route; "
            "the isolated arm proves each detector still fires when nothing can leave. "
            "Without both, a zero from the subject arm is indistinguishable from an "
            "instrument that could not look."
        ),
    }
    if not (shared.counts()["off_machine"] and shared.counts()["dns"]):
        return not_run(cid, req, clause, falsified, target, "query",
                       "the net-shared control did not trip both detectors, so the "
                       "instrument is not known to work here; this clause is not decided")
    if not (isolated.counts()["off_machine"] and isolated.counts()["dns"]):
        return not_run(cid, req, clause, falsified, target, "query",
                       "the isolated control did not trip both detectors, so an attempt "
                       "made under isolation would not be seen; this clause is not decided")

    subject = run_traced(
        drive_argv,
        mechanism=mechanism,
        network_shared=False,
        log_dir=log_dir,
        tag="subject",
        writable=(arena, *target.declaration.derived_state_roots),
    )
    counts = subject.counts()
    clean = counts["off_machine"] == 0 and counts["dns"] == 0
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if clean and subject.returncode == 0 else FAIL,
        target=target.declaration.name, verb="query",
        detail={
            "verbs_driven": driven,
            "verbs_not_offered": skipped,
            "isolation_mechanism": {
                "name": mechanism.name,
                "how": mechanism.note,
                # Whether the declared roots were the only writable paths. False
                # on a mechanism that leaves the host filesystem mounted, where
                # the writable set is a hint rather than a boundary — so two
                # artifacts from two machines are comparable on egress and not
                # on this. Recorded rather than assumed either way.
                "writable_enforced": mechanism.writable_enforced,
            },
            "subject": subject.as_json(),
            "control": control,
            "detectors": {
                "off_machine": "a connect/sendto/sendmsg naming a non-loopback address",
                "dns": ("a connect/sendto/sendmsg to a resolver port, loopback included: "
                        "inside a no-route namespace a hostname attempt dies at resolution "
                        "and leaves no off-machine connect at all, so a detector without "
                        "this one reports a false green"),
            },
            "run_completed": subject.returncode == 0,
        },
    )


def check_local_by_default(target: Target) -> Check:
    """R10: the embedder in the default configuration is local, and it is running.

    Migrated from `bench/smoke_upstream.py`'s `check_local_by_default`. What that
    check asserted is here; what it hardcoded — two tool names and the shape of
    their replies — is in the adapter, which is the split ticket 0578's Action 2
    names.

    Asserted against a running target rather than against its source: a source
    that defaults to local and a process that fell back to something else are
    the same file and different facts.
    """
    cid, req = "R10-local-by-default", "R10"
    clause = "the embedder is local in the target's default configuration"
    falsified = ("a default configuration whose effective embedder is a hosted provider, "
                 "or a local embedder that is configured but not running")

    for verb in ("configure", "status"):
        if not target.declaration.offers(verb):
            return not_offered(cid, req, clause, falsified, target, verb)

    with target.running():
        configured = target.configure()
        reported = target.status().get("embedding") or {}
    locality, active = reported.get("locality"), reported.get("active")
    if locality is None:
        return not_run(cid, req, clause, falsified, target, "status",
                       "the adapter reports no embedding locality for this target, so "
                       "this clause has nothing to read and is not decided")
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if locality == "local" and active is True else FAIL,
        target=target.declaration.name, verb="status",
        detail={
            "locality": locality,
            "active": active,
            "model": reported.get("model"),
            "default_configuration": target.declaration.default_configuration,
            "configure_returned": configured,
        },
    )


# --------------------------------------------------------------------------
# R15 — deletion, at the install scale.
# --------------------------------------------------------------------------


def check_uninstall_removes_declared_state(target: Target, *, arena: Path) -> Check:
    """R15: after the real uninstall surface runs, none of the declared state remains.

    Event then state, per ticket 0026's log of 2026-08-31T20:08Z: `uninstall` is
    called and observed as an event, and the assertion is about the state that
    follows it. A target with no uninstall surface reports `not-offered` — the
    harness does not delete files itself to manufacture a clean result, and it
    does not call a maintenance verb as a stand-in (`SPEC.md` §5.2.7, R15's
    uninstall clause, says so about one target by name).
    """
    cid, req = "R15-uninstall-removes-declared-state", "R15"
    clause = ("the target declares every location in which it creates derived state, "
              "and after uninstall none of that state remains")
    falsified = "any file surviving under a declared derived-state root after uninstall"

    if not target.declaration.offers("uninstall"):
        return not_offered(cid, req, clause, falsified, target, "uninstall")
    with target.running():
        if target.declaration.offers("install"):
            target.install()
        event = target.uninstall()
    survivors = sorted(
        p for root in target.declaration.derived_state_roots
        for p in Snapshot.of(root).files
    )
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if not survivors else FAIL,
        target=target.declaration.name, verb="uninstall",
        detail={
            "uninstall_event": event,
            "declared_roots": [str(p) for p in target.declaration.derived_state_roots],
            "survivors": [str(p) for p in survivors[:50]],
            "survivor_count": len(survivors),
            "arena": str(arena),
        },
    )


def check_residue_inventory(target: Target, *, arena: Path) -> Check:
    """R15: no target-created derived state exists outside the declaration.

    This is the half that makes the declaration falsifiable, and it fails two
    different mistakes with one mechanism, which is the reason it is written
    this way rather than as a re-read of the declared list:

    - a target that strays, writing somewhere its adapter honestly did not
      expect;
    - an adapter that under-declares, while its target behaves perfectly
      normally.

    A reader cannot tell those apart from the verdict alone, and does not need
    to: both mean the declaration does not account for what is on disk. The
    detail records the paths so the diagnosis is one look away.

    The arena is harness-owned, which is what bounds the sweep. Sweeping the
    whole filesystem would be neither affordable nor meaningful; sweeping only
    the declared roots would ask the declaration to grade itself.

    The arena must be clean when this is called, and the driver gives every
    assertion its own. That is not tidiness. The first version of this layer
    shared one arena across all five assertions, and the egress assertion — which
    drives `install` inside its sandbox — left the strayed file on disk before
    this sweep took its "before" snapshot. The stray was therefore already
    present in the baseline, `created` came back empty, and the fixture built to
    make this check go red **passed**. A sweep whose baseline another assertion
    can write to measures nothing.
    """
    cid, req = "R15-residue-inventory", "R15"
    clause = "no target-created derived state exists outside the declaration"
    falsified = ("any file created by the run that lies outside every declared "
                 "derived-state root and is not argued to be non-derived state")

    if not target.declaration.offers("install"):
        return not_offered(cid, req, clause, falsified, target, "install")
    why = dirty(arena)
    if why:
        return not_run(cid, req, clause, falsified, target, "install", why)

    before = Snapshot.of(arena)
    with target.running():
        event = target.install()
    created = Snapshot.of(arena).since(before)
    stray = residue(created, target)
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if not stray else FAIL,
        target=target.declaration.name, verb="install",
        detail={
            "install_event": event,
            "arena": str(arena),
            "created_count": len(created),
            "declared_roots": [str(p) for p in target.declaration.derived_state_roots],
            "not_derived_state": [
                {"path": str(p), "why": why}
                for p, why in target.declaration.not_derived_state
            ],
            "residue": [str(p) for p in stray[:50]],
            "residue_count": len(stray),
            "reads": ("the declaration is compared against what appeared in a "
                      "harness-owned arena, never read back against itself"),
        },
    )


def check_model_cache_under_declared_roots(target: Target, *, arena: Path) -> Check:
    """R15: weights a run downloads are derived state, and land under a declared root.

    Migrated from `bench/smoke_upstream.py`'s `check_model_stays_in_data_dir`.
    Two things changed in the move and both are corrections.

    It is no longer phrased over a path, and the old phrasing was not merely
    narrow — it could not observe its own falsifier. That check named "a model
    cache created outside the data directory (a shared cache, or the home
    directory)" as what would falsify it, and then looked only for a `models`
    directory *inside* the data directory. A run that wrote weights both inside
    and outside passed cleanly, because the presence of state within the
    declaration and the absence of state outside it are different claims and it
    only ever tested the first. This is the shipped instance of what R15's
    ratified clause means by a declaration nobody checks for completeness.

    So this one exercises the query surface — which is what triggers a download —
    and sweeps for whatever appeared outside the declaration.

    **What the sweep can and cannot see, stated because the first draft of this
    docstring overclaimed it.** It walks the harness-owned arena, so it catches
    weights that land outside a declared root *within that arena* — the case
    that decides anything when the adapter has redirected the target's caches
    into it, which an adapter does by pinning the cache under a root it
    declares. It does NOT walk the whole filesystem, so a cache
    landing at some library's own default outside the arena — a shared cache in
    the home directory, say — is invisible to it. Two honest ways to close that,
    and the choice belongs to whoever needs it: have the adapter redirect the
    cache into the arena, which makes this sweep decisive, or widen the sweep
    and accept that it must then reason about every path the operator already
    had. Until one is taken, read a green here as "nothing strayed inside the
    arena", not as "nothing strayed anywhere".

    One corollary worth stating because it has already misled a report:
    a green here from a data directory that was pre-populated says only that a
    directory exists; it is not evidence that a download was constrained. The
    `not-run` path below is what keeps that case from being read as a pass.

    Its undecided state is no longer `observed`. When a run creates nothing at
    all, the old check said `observed` and a reader had to work out that it
    meant "this run reused an existing cache and decides nothing". That is
    `not-run`, and the contract rejects `observed` outright so that a fifth
    category cannot leak in.
    """
    cid, req = "R15-model-cache-under-declared-roots", "R15"
    clause = "downloaded model weights are derived state and live under a declared root"
    falsified = ("a model cache created outside every declared derived-state root — a "
                 "shared cache in the home directory, say")

    for verb in ("install", "query", "status"):
        if not target.declaration.offers(verb):
            return not_offered(cid, req, clause, falsified, target, verb)
    why = dirty(arena)
    if why:
        return not_run(cid, req, clause, falsified, target, "query", why)

    before = Snapshot.of(arena)
    with target.running():
        target.install()
        target.configure()
        answered = target.query("a query that exercises the retrieval surface", MEANING, 5)
        # Read inside the lifecycle: `status` is a verb, and a verb reaches the
        # target through its process. Read after the block and a target with a
        # real lifecycle raises instead of answering.
        model = (target.status().get("embedding") or {}).get("model")
    created = Snapshot.of(arena).since(before)
    stray = residue(created, target)

    # Whether there are weights at all is the target's own report, not a guess
    # from file sizes or directory names — a size floor would be a design number
    # invented here, and a name pattern would be a target's vocabulary in the
    # layer. With no model in effect there is nothing for this clause to be
    # about, and the honest verdict is that it was not decided. That is also
    # what a missing model runtime looks like, which is the failure this
    # deliberately reports as `not-run` rather than as a green.
    if model is None:
        return not_run(
            cid, req, clause, falsified, target, "query",
            "the target reports no model in effect, so this run exercised no weights and "
            "decides nothing about where they land",
        )
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if not stray else FAIL,
        target=target.declaration.name, verb="query",
        detail={
            "model_in_effect": model,
            "created_count": len(created),
            "residue": [str(p) for p in stray[:50]],
            "residue_count": len(stray),
            "declared_roots": [str(p) for p in target.declaration.derived_state_roots],
            "query_answered": bool(answered),
            "arena": str(arena),
        },
    )


# --------------------------------------------------------------------------
# Apparatus.
# --------------------------------------------------------------------------


def _python() -> str:
    import sys
    return sys.executable or "python3"


#: The harness's own egress probe, run as both control arms. It reaches for a
#: literal off-machine address AND for a hostname, because each trips a
#: different detector and a control that fires only one proves only one works.
#: The address and the name are the harness's, not any target's.
_EGRESS_PROBE = (
    "import socket\n"
    "try:\n"
    "    socket.create_connection(('1.1.1.1', 443), timeout=2).close()\n"
    "except Exception:\n"
    "    pass\n"
    "try:\n"
    "    socket.getaddrinfo('example.invalid', 443)\n"
    "except Exception:\n"
    "    pass\n"
)

#: Every assertion this layer offers, by check id, in the order a run reports
#: them. The driver derives its work from this rather than from a hand-kept
#: list, so an assertion added here is run without a second edit.
ALL = {
    "R10-local-by-default": check_local_by_default,
    "R10-no-egress": check_no_egress,
    "R15-residue-inventory": check_residue_inventory,
    "R15-model-cache-under-declared-roots": check_model_cache_under_declared_roots,
    "R15-uninstall-removes-declared-state": check_uninstall_removes_declared_state,
}
