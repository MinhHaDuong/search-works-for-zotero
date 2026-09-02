"""The vocabulary the assertion layer is phrased in. It holds no target's name.

`SPEC.md` §5.2.8 owns the contract and `DECISIONS.md`'s ratified entry of
2026-09-02 owns the ruling behind it. This module is their executable form and
restates neither.

Three things live here and nothing else.

**The seven verbs.** `install`, `uninstall`, `configure`, `query`, `status`,
`pause`, `resume`. An assertion calls verbs; it never reaches around one to a
path, a process or a tool name. Starting and stopping a target's process is
adapter-declared harness setup rather than an eighth verb, which is why
`Target` exposes it as a context manager instead. Convergence is likewise no
verb: the harness changes its fixture library and observes convergence through
`status`, because a nudge cannot prove R1's unattended clause.

**The four states.** `pass`, `fail`, `not-offered`, `not-run`. The third is the
one the layer exists to make possible: a verb a target does not offer is
declared absent by its adapter, and every assertion needing that verb reports
`not-offered` — a state distinguishable from green and from red, so that a
target which simply lacks a surface is never scored as one that failed at it.
The fourth is the honest-gate rule: a check whose "all clear" is
indistinguishable from "I could not look" is not a check, so an assertion that
could not run says so instead of returning a verdict.

**The declaration.** What an adapter says about itself, and the whole of what it
is allowed to contain beyond minimal transport. The derived-state roots are the
load-bearing field: R15's clause reads over them, and a declaration nobody
checks for completeness grades itself, which is why `assertions.py` sweeps for
residue outside them rather than trusting the list.

Why `result` is a string and not an enum on the wire: `bench/results/**` is a
committed artifact tree read by tools and by people, and a JSON verdict that
round-trips through `str` needs no decoder. `State` names the four values so a
typo is a `ValueError` here rather than a silent third category downstream.
"""

import json
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

#: The interface, ratified 2026-09-02 and specified in `SPEC.md` §5.2.8. The
#: order is the ruling's own. Pause and resume are the two transitions of one
#: durable background-work control, not two independent capabilities.
VERBS: tuple[str, ...] = (
    "install",
    "uninstall",
    "configure",
    "query",
    "status",
    "pause",
    "resume",
)

#: The three retrieval modes R33 names. A target that offers a mode selector
#: MUST serve the mode selected; which of these an adapter can reach is its
#: declaration's business, not an assertion's.
MODES: tuple[str, ...] = ("exact", "meaning", "combined")

PASS = "pass"
FAIL = "fail"
NOT_OFFERED = "not-offered"
NOT_RUN = "not-run"

#: The four states, and the reason there are four rather than two. `not-offered`
#: separates "this target has no such surface" from "this target has one and it
#: failed"; `not-run` separates both from "the harness could not look".
STATES: tuple[str, ...] = (PASS, FAIL, NOT_OFFERED, NOT_RUN)


class UnsupportedVerb(Exception):
    """Raised by an adapter asked for a verb its declaration lists as absent.

    An assertion catches this and reports `not-offered`. It is an exception
    rather than a return value so that an assertion which forgets to check
    `Declaration.offers` cannot silently read a `None` as a failure.
    """

    def __init__(self, target: str, verb: str) -> None:
        super().__init__(f"{target} does not offer {verb!r}")
        self.target = target
        self.verb = verb


@dataclass(frozen=True)
class Declaration:
    """Everything an adapter says about its target. The adapter's whole content.

    Per the ratified contract an adapter declares its surfaces and carries only
    the minimal transport needed to invoke them: no patch or workaround, no
    non-default option, no access unavailable to the target's own users, and no
    scoring of a result.
    """

    #: The target's identity. The ONLY place a tool's name is allowed to appear
    #: in this harness.
    name: str

    #: The revision under test, so an artifact says what it measured.
    revision: str

    #: Every location in which the target creates derived state. R15's clause
    #: reads over exactly this list, and the residue sweep is what stops the
    #: list from grading itself.
    derived_state_roots: tuple[Path, ...]

    #: How the query surface is reached, in prose, for the artifact's reader.
    query_transport: str

    #: What "default configuration" means for this target — the configuration
    #: an ordinary user gets, which is the only one R10's clause is about.
    default_configuration: str

    #: How the target's process starts and stops. Adapter-declared harness
    #: setup, per §5.2.8, and deliberately not an interface verb.
    process: str

    #: The verbs this target does not offer. Every assertion needing one of
    #: these reports `not-offered`.
    unsupported: frozenset[str] = frozenset()

    #: Locations the sweep must not count as residue, each with the reason it
    #: is not target-created derived state. User-authored library data and
    #: externally supplied configuration are not derived state (R15); anything
    #: else listed here is an admission that needs an argument, which is why
    #: the value is the reason rather than a bare path.
    not_derived_state: tuple[tuple[Path, str], ...] = ()

    def __post_init__(self) -> None:
        unknown = sorted(set(self.unsupported) - set(VERBS))
        if unknown:
            raise ValueError(
                f"{self.name} declares {unknown} unsupported, which are not interface "
                f"verbs. The interface is {list(VERBS)} (SPEC.md §5.2.8)."
            )
        if not self.derived_state_roots and "install" not in self.unsupported:
            raise ValueError(
                f"{self.name} declares no derived-state root while offering install. "
                "A target that writes nothing anywhere is a claim, not an omission — "
                "declare it explicitly with an empty tuple and say so in the adapter."
            )

    def offers(self, verb: str) -> bool:
        if verb not in VERBS:
            raise ValueError(f"{verb!r} is not one of {list(VERBS)}")
        return verb not in self.unsupported

    def as_json(self) -> dict:
        """The declaration as it lands in the artifact, so a reader can audit it."""
        return {
            "target": self.name,
            "revision": self.revision,
            "derived_state_roots": [str(p) for p in self.derived_state_roots],
            "query_transport": self.query_transport,
            "default_configuration": self.default_configuration,
            "process": self.process,
            "unsupported_verbs": sorted(self.unsupported),
            "not_derived_state": [
                {"path": str(p), "why": why} for p, why in self.not_derived_state
            ],
        }


@runtime_checkable
class Target(Protocol):
    """What an adapter must provide. Seven verbs, a declaration, and a lifecycle.

    A verb an adapter's declaration lists as unsupported raises
    `UnsupportedVerb`; it does not return a sentinel, and it does not simulate
    the verb's effect. The harness never manufactures a clean result by doing a
    target's work for it — R15's uninstall clause says this in as many words.
    """

    declaration: Declaration

    def running(self) -> AbstractContextManager[None]:
        """Start the target's process, yield, stop it. Harness setup, not a verb."""
        ...

    def install(self) -> dict: ...
    def uninstall(self) -> dict: ...
    def configure(self) -> dict: ...
    def query(self, q: str, mode: str, limit: int) -> dict: ...
    def status(self) -> dict: ...
    def pause(self) -> dict: ...
    def resume(self) -> dict: ...


@dataclass
class Check:
    """One assertion's record: one MUST clause, one target, one run.

    The unit is the clause and not the requirement (inherited from ticket 0026),
    so `README.md`'s delivered column is a count rather than a reader's
    judgement. `target` and `verb` are what the target-neutral rescope added:
    a green is a green for one named target rather than for the harness, and a
    reader can see which surface produced it.
    """

    check: str
    requirement: str
    clause: str
    falsified_by: str
    result: str
    target: str
    verb: str | None
    detail: object

    def __post_init__(self) -> None:
        if self.result not in STATES:
            raise ValueError(
                f"{self.check}: result {self.result!r} is not one of {list(STATES)}. "
                "A fifth state is a verdict nobody can read (SPEC.md §5.2.8)."
            )
        if self.verb is not None and self.verb not in VERBS:
            raise ValueError(
                f"{self.check}: verb {self.verb!r} is not one of {list(VERBS)}"
            )

    def as_json(self) -> dict:
        return {
            "check": self.check,
            "requirement": self.requirement,
            "clause": self.clause,
            "falsified_by": self.falsified_by,
            "result": self.result,
            "target": self.target,
            "verb": self.verb,
            "detail": self.detail,
        }


def not_offered(check: str, requirement: str, clause: str, falsified_by: str,
                target: Target, verb: str) -> Check:
    """The third state, built in one place so every assertion spells it the same.

    Called when an assertion needs a verb the target's declaration lists as
    absent. The detail records which verb was missing, because "not-offered"
    with no verb named is as unreadable as a bare failure.
    """
    return Check(
        check=check, requirement=requirement, clause=clause,
        falsified_by=falsified_by, result=NOT_OFFERED,
        target=target.declaration.name, verb=verb,
        detail={
            "verb": verb,
            "why": (
                f"the adapter declares {verb!r} absent, so this clause has no surface to "
                "assert against on this target. Not a failure: the harness does not "
                "simulate a verb's effect to manufacture a verdict."
            ),
            "unsupported_verbs": sorted(target.declaration.unsupported),
        },
    )


def not_run(check: str, requirement: str, clause: str, falsified_by: str,
            target: Target, verb: str | None, why: str) -> Check:
    """The honest-gate state: the assertion could not look, and says so.

    Distinct from `not_offered`: there the surface is absent by declaration,
    here the harness's own instrument was unavailable — no sandbox mechanism, no
    tracer, no built checkout. Both are distinct from a red.
    """
    return Check(
        check=check, requirement=requirement, clause=clause,
        falsified_by=falsified_by, result=NOT_RUN,
        target=target.declaration.name, verb=verb,
        detail={"why": why},
    )


@dataclass
class Run:
    """A batch of checks against one target, and what lands in `checks.json`."""

    target: Declaration
    checks: list[Check] = field(default_factory=list)
    date: str = ""

    def summary(self) -> dict[str, int]:
        return {s: sum(1 for c in self.checks if c.result == s) for s in STATES}

    def as_json(self) -> dict:
        return {
            "probe": (
                "the target-neutral acceptance layer, run against one adapter "
                "(SPEC.md §5.2.8; DECISIONS.md, ratified 2026-09-02)"
            ),
            "not_a_test_suite": (
                "each check exercises ONE MUST clause of one requirement, once, "
                "against ONE named target. A green is a green for that target and "
                "for nothing else."
            ),
            "date": self.date,
            "declaration": self.target.as_json(),
            "checks": [c.as_json() for c in self.checks],
            "summary": self.summary(),
        }

    def write(self, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.as_json(), ensure_ascii=False, indent=2))

    def exit_code(self) -> int:
        """Nonzero on a red, and only on a red.

        `not-offered` and `not-run` are not failures of the target and must not
        turn the gate red — but they are not successes either, which is why the
        driver prints them and the artifact counts them separately.
        """
        return 1 if self.summary()[FAIL] else 0
