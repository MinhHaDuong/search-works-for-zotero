"""The assertion layer. One clause per assertion, phrased over the seven verbs.

`SPEC.md` §3 owns R10, R15, R22 and R31 — goal 1's whole rung, per README.md's
goals ladder; `SPEC.md` §5.2.8 owns this harness; `DECISIONS.md`'s ratified entry
of 2026-09-02 owns the ruling. None is restated here — this module cites
addresses and asserts clauses.

**The ladder's method is tests first, bottom-up**: until a rung's assertions
exist, its rows can only be `code` or `inferred`, a claim about nobody. R22's two
clauses were the last members of the lowest rung with no assertion at all, and
they read the work counters `durability.py` already defines rather than a second
set of their own. R31 is the rung's one clause this layer cannot decide, and the
section below says why rather than leaving its absence to be read as an
oversight.

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
    DRIVE_INCOMPLETE,
    FAIL,
    PASS,
    Check,
    Target,
    UnsupportedVerb,
    not_offered,
    not_run,
)
from . import durability
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
    disk. That is a false green of exactly the class this layer exists to catch,
    so it is fixed here rather than worked around in one adapter.

    **Measured against a real target rather than argued** (ticket 0586). The
    same run, driven twice against the same product, once with this branch and
    once without: with it, `fail`, two survivors named. Without it, `pass`,
    `survivor_count` zero — and a 32 KB database and a 2.3 MB write-ahead log
    sitting in the directory the check had just swept. Both artifacts are
    committed under that ticket's results directory, as `acceptance.json` and
    `acceptance-prefix-control.json`, because a fix whose defect was only
    reasoned about is a fix nobody can check. (This paragraph named the target's
    results path on its first draft and the neutrality guard refused it, which
    is the guard working: a layer module may cite a ticket, never a product.)
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
    if subject.returncode == DRIVE_INCOMPLETE and clean:
        # The driven run reported that a verb raised inside it AND the tracer saw
        # nothing. Zero attempts then means "this path never executed", not "this
        # path stayed home", and the two are the same number. Reported as not
        # decided rather than as a red: the target has not failed a clause about
        # egress by having a broken verb, and it has not passed one either.
        #
        # The `clean` conjunct is not belt and braces. Under a no-route namespace
        # the verb that reaches off this machine is usually the very verb that
        # then raises, so testing the return code alone would downgrade the exact
        # target this clause exists to catch — an attempt the tracer recorded is
        # a finding whatever else went wrong afterwards, and it stands.
        undecided = not_run(
            cid, req, clause, falsified, target, "query",
            "a verb raised inside the driven run, so part of the default-configuration "
            "path never executed and the attempt counts are read off an incomplete "
            "sweep; this clause is not decided",
        )
        # The measurement rides along with the reason. `run_fixtures` reads
        # `detail["subject"]` for this check, and a not-run carrying only prose
        # publishes `attempt_counts: null` — which makes a zero that was measured
        # on an incomplete run indistinguishable from one nobody looked for.
        undecided.detail = {**undecided.detail, "subject": subject.as_json(),
                            "control": control, "verbs_driven": driven,
                            "verbs_not_offered": skipped}
        return undecided
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
        try:
            answered = target.query(
                "a query that exercises the retrieval surface", MEANING, 5)
        except UnsupportedVerb:
            raise
        except Exception as why:
            # A target whose retrieval surface raises has exercised no weights, so
            # this clause is undecided — and saying so is not tidiness. Before this
            # was guarded, one such target ended the whole run mid-fixture with a
            # traceback: every assertion after it went unrecorded, and the artifact
            # the gate reads was never written. An assertion that cannot look must
            # report that it could not look, not take the driver down with it.
            return not_run(
                cid, req, clause, falsified, target, "query",
                f"the target's retrieval surface raised ({type(why).__name__}: {why}), "
                "so no weights were exercised and nothing here decides where they land",
            )
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
# R22 — one obvious way to stop all background work, holding across restarts.
# --------------------------------------------------------------------------
#
# Two clauses, so two assertions, per the layer's unit rule. The requirement's
# own wording joins them with an "and it MUST", and they fail differently: a
# target that never stops is a missing control, a target that stops until it is
# next started is a control that does not hold. One verdict covering both would
# report the same red for either.
#
# **Both grade the `done` half of the counters and nothing else.** A stopped
# target may still notice a change and record that there is work to do later;
# recording it is not doing it, and a clause that reddened on a queue would be
# asking for amnesia rather than for a pause. Every delta lands in the detail so
# a reader can see what was not graded.
#
# **Neither calls `resume`.** The restart clause is about what a target does
# with no one asking it to carry on, so asking would erase the finding.


def _pause_could_not_look(cid: str, req: str, clause: str, falsified: str,
                          target: Target, why: BaseException) -> Check:
    """The control was reached for and the reach itself failed.

    Guarded rather than left to propagate, and the reason is one this commit
    already had to fix once: `assess` wraps no check in a try, so a verb raising
    on a real target's transport ends the whole run with a traceback — every
    assertion after it unrecorded, and the artifact the gate reads never written.
    An assertion that cannot look reports that it could not look.
    """
    return not_run(
        cid, req, clause, falsified, target, "pause",
        f"the target's pause surface raised ({type(why).__name__}: {why}), so the "
        "control was never used and nothing here decides whether it stops the work",
    )


def _pause_verdict(cid: str, req: str, clause: str, falsified: str, target: Target,
                   before: dict[str, int], after: dict[str, int], detail: dict) -> Check:
    """The arithmetic both pause clauses share: did any `done` counter advance.

    Written once because the two clauses differ in what happens between the two
    reads — a change made while stopped, or a restart and then the change — and
    not at all in how the reads are graded.
    """
    moved = durability.delta(before, after)
    worked = {k: v for k, v in moved.items()
              if durability.outcome_of(k) == durability.DONE and v > 0}
    return Check(
        check=cid, requirement=req, clause=clause, falsified_by=falsified,
        result=PASS if not worked else FAIL,
        target=target.declaration.name, verb="pause",
        detail={
            **detail,
            "done_deltas_while_stopped": worked,
            "all_deltas_while_stopped": moved,
            "grades": (
                "the `done` half of work.<stage>.<trigger>.<outcome> alone: a stopped "
                "target may record that there is work to do later, and recording it is "
                "not doing it"
            ),
        },
    )


def _the_change_creates_work(cid: str, req: str, clause: str, falsified: str,
                             target: Target,
                             control: Target) -> tuple[dict | None, Check | None]:
    """The positive control: the same change, on a second target that was never stopped.

    Without a control at all, both clauses are a green that means "could not
    look": their whole finding is that a counter did not move, and a counter that
    would not have moved anyway produces that finding on a target whose control
    does nothing.

    **The control is a second target rather than a second phase**, and both
    alternatives were tried and are worse. Making the change on the graded target
    *before* pausing it consumes it: where editing the same item twice is a no-op
    the second time, the graded phase then finds no work for reasons that have
    nothing to do with the pause, and that lands as a pass. Making it *after*,
    by letting the target go again, needs `resume` — and a target may offer the
    control while having nothing that maps onto resuming, by a documented ruling
    rather than an oversight, which would leave both clauses permanently
    undecided for it. A second instance in an arena of its own is neither: it is
    never paused, so nothing is consumed and nothing is asked of a verb the
    target may not have.

    Independence is the point, so the two must not share a root — the opposite of
    R13's clauses, which are about two processes on ONE data directory and refuse
    to run when the roots differ. Here a shared root would let the control's own
    work land in the graded target's counters.

    Returns `(control, None)` when work was created, and `(None, check)` carrying
    the `not-run` when it was not.
    """
    def paths(who: Target) -> set:
        # Both halves, because the change and the work land in different places.
        # The declared derived-state roots are where the work is recorded; what
        # the adapter argued is NOT derived state is where the change is made —
        # a target's source library is declared there, and two instances given
        # the same adapter options resolve the same one. A guard reading only the
        # first would pass a control that edits the very library the graded
        # target is about to edit, consuming the change and turning the clause
        # into the false pass it exists to prevent.
        declared = who.declaration
        return set(declared.derived_state_roots) | {p for p, _why in declared.not_derived_state}

    shared = paths(target) & paths(control)
    if shared or not (paths(target) and paths(control)):
        return None, not_run(
            cid, req, clause, falsified, target, "status",
            "the positive control and the graded target do not demonstrably resolve "
            "separate state: they share a declared path, or one of them declares none "
            "at all and independence cannot be established from the declarations. The "
            "control's own work would land in the counters this clause reads, or its "
            "change would consume the graded target's, so this run is not decided.",
        )
    with control.running():
        if durability.work_counters(control) is None:
            return None, durability.no_counters(cid, req, clause, falsified, target)
        undecided = _installed(cid, req, clause, falsified, control)
        if undecided:
            return None, undecided
        before, settled = durability.settle(control)
        if not settled:
            return None, durability.unsettled(cid, req, clause, falsified, target,
                                              "before the positive control")
        event, why = durability.perturb(control, durability.EDIT_ONE_ITEM)
        if why:
            return None, not_run(cid, req, clause, falsified, target, "status", why)
        after, settled = durability.settle(control)
        if not settled:
            return None, durability.unsettled(cid, req, clause, falsified, target,
                                              "after the positive control")

    created = {k: v for k, v in durability.delta(before, after).items()
               if durability.outcome_of(k) == durability.DONE and v > 0}
    if not created:
        return None, not_run(
            cid, req, clause, falsified, target, "status",
            "the change the harness makes created no work on a second, never-stopped "
            "instance of this target, so a stopped one creating none proves nothing "
            "about the control. Reported as not decided rather than as a green: a "
            "clause whose finding is that a counter did not move needs the counter to "
            "have been able to move.",
        )
    return {"perturbation": durability.EDIT_ONE_ITEM, "event": event,
            "done_deltas_on_a_never_stopped_instance": created}, None


def _installed(cid: str, req: str, clause: str, falsified: str,
               target: Target) -> Check | None:
    """Install where it is offered, or the `not-run` saying why the clause cannot run.

    Run for the reason `check_model_cache_under_declared_roots` runs it: a target
    whose work only exists after installation would otherwise be graded on a
    state the harness withheld from it.
    """
    if not target.declaration.offers("install"):
        return None
    try:
        target.install()
    except UnsupportedVerb:
        raise
    except Exception as why:
        return not_run(
            cid, req, clause, falsified, target, "install",
            f"the target's install surface raised ({type(why).__name__}: {why}), so no "
            "state exists for a change to create work against",
        )
    return None


def check_pause_stops_background_work(target: Target, *, control: Target) -> Check:
    """R22: after the control is used, a change that would create work creates none.

    The falsifier is a control that answers and does nothing, and that is the
    reason this is phrased over counters rather than over the verb's reply. A
    target returning `paused` from its pause surface satisfies any check that
    reads the reply, whatever its workers then go on to do; §5.2.8's counters are
    the only thing here that distinguishes the two.

    The positive control runs first, on a second never-stopped instance, because
    the counters have to be shown capable of moving before their not moving means
    anything — see `_the_change_creates_work`.

    A target with no such surface reports `not-offered`, and that is a different
    finding rather than a softer one: R22's own status on the sheet is *verified
    absent*, so the state this assertion reaches against stock upstream is the
    third one, and it must not be scored as a failure at a control the target
    never claimed to have.
    """
    cid, req = "R22-pause-stops-background-work", "R22"
    clause = ("there is one obvious way to stop all background work, and after it is "
              "used a change that would create work creates none")
    falsified = ("any work.*.*.done counter advancing against a change made while the "
                 "target is stopped")

    for verb in ("pause", "status"):
        if not target.declaration.offers(verb):
            return not_offered(cid, req, clause, falsified, target, verb)

    control, undecided = _the_change_creates_work(
        cid, req, clause, falsified, target, control)
    if undecided:
        return undecided

    with target.running():
        if durability.work_counters(target) is None:
            return durability.no_counters(cid, req, clause, falsified, target)
        undecided = _installed(cid, req, clause, falsified, target)
        if undecided:
            return undecided
        _, settled = durability.settle(target)
        if not settled:
            return durability.unsettled(cid, req, clause, falsified, target,
                                        "before the pause")
        try:
            paused = target.pause()
        except UnsupportedVerb:
            raise
        except Exception as why:
            return _pause_could_not_look(cid, req, clause, falsified, target, why)
        before, settled = durability.settle(target)
        if not settled:
            return durability.unsettled(cid, req, clause, falsified, target,
                                        "after the pause")
        change, why = durability.perturb(target, durability.EDIT_ONE_ITEM)
        if why:
            return not_run(cid, req, clause, falsified, target, "pause", why)
        after, settled = durability.settle(target)
        if not settled:
            return durability.unsettled(cid, req, clause, falsified, target,
                                        "after the change made while stopped")

    return _pause_verdict(cid, req, clause, falsified, target, before, after, {
        "pause_event": paused,
        "positive_control": control,
        "change_made_while_stopped": change,
        "restarted": False,
    })


def check_pause_holds_across_restart(target: Target, *, control: Target) -> Check:
    """R22: the control survives the process it was used in.

    The restart is the whole clause. A pause held in a running process stops the
    work for exactly as long as nothing goes wrong, which is the opposite of what
    someone reaches for the control to obtain — the machine is closed, the plugin
    host is restarted, and the work everyone thought was stopped resumes
    unattended. Here the target's process is stopped and started again through
    the adapter's own lifecycle, the same one every other assertion uses, and the
    change is made after the restart.

    `resume` is never called, which is why the clause can be read at all: a
    harness that asked the target to carry on would be measuring its own request.

    The positive control runs here too, and the restart makes it matter more
    rather than less: a target that stops doing work simply because it was
    restarted would otherwise be indistinguishable from one whose control held.
    """
    cid, req = "R22-pause-holds-across-restart", "R22"
    clause = ("the control that stops all background work holds across a restart, with "
              "no one asking for it again")
    falsified = ("any work.*.*.done counter advancing against a change made after the "
                 "process is restarted, with no resume in between")

    for verb in ("pause", "status"):
        if not target.declaration.offers(verb):
            return not_offered(cid, req, clause, falsified, target, verb)

    control, undecided = _the_change_creates_work(
        cid, req, clause, falsified, target, control)
    if undecided:
        return undecided

    with target.running():
        if durability.work_counters(target) is None:
            return durability.no_counters(cid, req, clause, falsified, target)
        undecided = _installed(cid, req, clause, falsified, target)
        if undecided:
            return undecided
        _, settled = durability.settle(target)
        if not settled:
            return durability.unsettled(cid, req, clause, falsified, target,
                                        "before the pause")
        try:
            paused = target.pause()
        except UnsupportedVerb:
            raise
        except Exception as why:
            return _pause_could_not_look(cid, req, clause, falsified, target, why)
        _, settled = durability.settle(target)
        if not settled:
            return durability.unsettled(cid, req, clause, falsified, target,
                                        "after the pause")

    # The restart the clause is about: the lifecycle closed above, and opens again
    # here. Nothing asks the target to carry on in between.
    with target.running():
        # The baseline is read AFTER the restart has settled, not before it. Read
        # across the restart, any work a target does on start — a scan, a
        # reconciliation — lands inside the window and is graded as the pause
        # having failed, on a target whose pause held perfectly. The clause is
        # about a CHANGE made after the restart, and this is where that window
        # opens.
        before, settled = durability.settle(target)
        if not settled:
            return durability.unsettled(cid, req, clause, falsified, target,
                                        "after the restart")
        change, why = durability.perturb(target, durability.EDIT_ONE_ITEM)
        if why:
            return not_run(cid, req, clause, falsified, target, "pause", why)
        after, settled = durability.settle(target)
        if not settled:
            return durability.unsettled(cid, req, clause, falsified, target,
                                        "after the change made while stopped")

    return _pause_verdict(cid, req, clause, falsified, target, before, after, {
        "pause_event": paused,
        "positive_control": control,
        "change_made_while_stopped": change,
        "restarted": True,
        "resume_never_called": True,
    })


# --------------------------------------------------------------------------
# R31 — why this layer does not assert it, and what would let it.
# --------------------------------------------------------------------------
#
# R31 asks that a configuration offered to me prove it works on my machine
# BEFORE it is used, or fail loudly there. The load-bearing word is "before":
# the clause is about when validation happens, not about whether the target
# ends up working.
#
# An assertion was written for it and withdrawn under review, and the reason is
# worth keeping because it is not a bug that a rewrite fixes. Everything the
# layer can observe through the seven verbs after `configure` returns — the
# embedder's reported locality, whether it is active, whether a query answers —
# is a fact about the target's CURRENT state, and `check_local_by_default`
# already grades that state, over a strictly wider condition. So the assertion
# reddened exactly where R10 already reddened and nowhere else: it had no
# discriminating power, and a check that cannot fail where its own requirement
# fails is a green about nobody wearing a requirement's number.
#
# Reading exceptions does not rescue it either, and that was the first attempt:
# a `configure` that raises was graded green ("it failed loudly") and a `query`
# that raises red ("it could not answer"), when the layer cannot tell either one
# from a transport that died.
#
# What would make the clause decidable is a way to offer a configuration KNOWN to
# be unusable here and watch when the target notices. `configure` takes no
# argument (`interface.py`, VERBS; SPEC.md §5.2.8), so the harness cannot offer
# one, and inventing the configuration itself would mean naming a target's own
# settings surface in this layer — which the ratified contract puts in the
# adapter. Extending the contract is the author's, not this layer's: ticket 0488
# carries it.


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
#:
#: Goal 2's clauses live in `durability.py` and are folded in here rather than
#: copied: one registry, so a reader asking what this layer asserts has one place
#: to look and the target-neutrality guard has one package to walk.
ALL = {
    "R10-local-by-default": check_local_by_default,
    "R10-no-egress": check_no_egress,
    "R15-residue-inventory": check_residue_inventory,
    "R15-model-cache-under-declared-roots": check_model_cache_under_declared_roots,
    "R15-uninstall-removes-declared-state": check_uninstall_removes_declared_state,
    "R22-pause-stops-background-work": check_pause_stops_background_work,
    "R22-pause-holds-across-restart": check_pause_holds_across_restart,
    **durability.ALL,
}
