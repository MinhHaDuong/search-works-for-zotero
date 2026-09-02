#!/usr/bin/env python3
"""Run the acceptance layer against one named adapter and write the artifact.

`SPEC.md` §5.2.8 owns the harness; `DECISIONS.md`'s ratified entry of
2026-09-02 owns the ruling. Neither is restated here.

    python3 bench/acceptance/run.py --list-adapters
    python3 bench/acceptance/run.py --adapter <name> \\
        --arena <a-scratch-directory> --output bench/results/smoke-1.12.0/acceptance.json

The adapter is named on the command line and never in this file: `--list-adapters`
is how a reader finds the choices, because a usage example naming one would put a
target's name in the layer.

**Honest states, which is the whole of Action 6.** Four verdicts reach the
artifact and the exit code distinguishes exactly one of them: `fail`. A verb a
target does not offer (`not-offered`) and an instrument that could not look
(`not-run`) are not failures of the target, so they do not turn the gate red —
and they are not successes either, so they are printed and counted apart from
green rather than absorbed into it. `Run.exit_code()` in `interface.py` already
encodes the rule; this driver's job is to make it visible on the terminal, so a
reader of the output sees the same three-way split the artifact carries.

**Every verdict names its target.** A green here is a green for one named
adapter and for nothing else, which is why the target is a field on every check
rather than a property of the run.

**The inner mode** (`--drive`) is what the egress assertion runs inside the
sandbox. It constructs the adapter and calls the verbs it offers, printing what
happened; the outer process traces it. The seam matters: the adapter never
learns it is being sandboxed, or the layer's isolation concern would have leaked
into a target's declaration.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from acceptance import adapters  # noqa: E402
from acceptance.assertions import EGRESS_VERBS, MEANING, check_no_egress  # noqa: E402
from acceptance.assertions import (  # noqa: E402
    check_local_by_default,
    check_model_cache_under_declared_roots,
    check_residue_inventory,
    check_uninstall_removes_declared_state,
)
from acceptance.durability import (  # noqa: E402
    check_edit_recomputes_only_what_changed,
    check_foreign_stamp_ends_up_serving,
    check_identical_resync_recomputes_nothing,
    check_two_processes_both_answer,
    check_two_processes_do_not_duplicate_work,
)
from acceptance.interface import FAIL, NOT_OFFERED, NOT_RUN, PASS, Run  # noqa: E402
from acceptance.interface import UnsupportedVerb  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("acceptance")


def drive(target, verbs: tuple[str, ...] = EGRESS_VERBS) -> dict:
    """Call every offered verb among `verbs`, inside the target's lifecycle.

    Used by `--drive`, which the egress assertion runs under the tracer. A verb
    the adapter declares absent is skipped and named; it is not simulated.
    """
    done: dict[str, object] = {}
    with target.running():
        for verb in verbs:
            if not target.declaration.offers(verb):
                done[verb] = "not-offered"
                continue
            try:
                if verb == "query":
                    done[verb] = target.query("a query the harness supplies", MEANING, 5)
                else:
                    done[verb] = getattr(target, verb)()
            except UnsupportedVerb:
                done[verb] = "not-offered"
    return done


#: When this process started, to the second. Names this run's arenas so that a
#: re-run never inherits the previous one's files.
_STARTED = time.strftime("%H%M%S")


def _started() -> str:
    return _STARTED


def assess(make_target, *, base_arena: Path, log_dir: Path, drive_argv_for) -> Run:
    """Every assertion the layer offers, each against a fresh target in a clean arena.

    **Why one arena per assertion and not one per run.** The first version of
    this driver shared a single arena, and the sharing was not neutral: the
    egress assertion drives `install` inside its sandbox, so by the time the
    residue sweep took its "before" snapshot the arena already held everything
    that install writes — including, in the fixture built to make the sweep go
    red, the strayed file itself. The sweep saw nothing new, and the red fixture
    passed. Assertions that can write to each other's baselines are not
    independent, and a check whose verdict depends on what ran before it is not
    a check.

    The declaration reported for the run is built against the base arena. The
    per-assertion arenas are subdirectories of it, so the declaration's roots
    differ from any single assertion's by that path component alone; everything
    a reader audits a verdict against — the unsupported verbs, the transport,
    the process, what is argued not to be derived state — is identical across
    them.
    """
    run = Run(target=make_target(base_arena).declaration, date=time.strftime("%Y-%m-%d"))

    def arena_for(check_id: str) -> Path:
        """A directory this run alone has written to.

        Unique per run, because a re-run into a previous run's directory is the
        second way a residue sweep loses its baseline — and it is the one a gate
        hits, since a gate runs repeatedly against a fixed path. Nothing is
        deleted to achieve this: an old arena is left where it is and a new one
        is made beside it. The sweeps additionally refuse a dirty arena, so a
        caller who supplies one gets `not-run` rather than a false green.
        """
        arena = base_arena / run.date / f"{_started():s}-{check_id}"
        arena.mkdir(parents=True, exist_ok=True)
        return arena

    where = arena_for("R10-local-by-default")
    run.checks.append(check_local_by_default(make_target(where)))

    where = arena_for("R10-no-egress")
    run.checks.append(check_no_egress(
        make_target(where), arena=where, log_dir=log_dir,
        drive_argv=drive_argv_for(where),
    ))

    where = arena_for("R15-residue-inventory")
    run.checks.append(check_residue_inventory(make_target(where), arena=where))

    where = arena_for("R15-model-cache-under-declared-roots")
    run.checks.append(check_model_cache_under_declared_roots(make_target(where), arena=where))

    where = arena_for("R15-uninstall-removes-declared-state")
    run.checks.append(check_uninstall_removes_declared_state(make_target(where), arena=where))

    # Goal 2. The two R13 clauses take a SECOND target built over the same arena:
    # two adapter instances resolving one declared derived-state root is what
    # "two server processes on one data directory" means without the layer
    # knowing any path. Everything else here is one target in an arena of its own,
    # for the reason the docstring above gives.
    where = arena_for("R3-edit-recomputes-only-what-changed")
    run.checks.append(check_edit_recomputes_only_what_changed(make_target(where)))

    where = arena_for("R3-identical-resync-recomputes-nothing")
    run.checks.append(check_identical_resync_recomputes_nothing(make_target(where)))

    where = arena_for("R13-two-processes-both-answer")
    run.checks.append(check_two_processes_both_answer(
        make_target(where), second=make_target(where)))

    where = arena_for("R13-two-processes-do-not-duplicate-work")
    run.checks.append(check_two_processes_do_not_duplicate_work(
        make_target(where), second=make_target(where)))

    where = arena_for("R23-foreign-stamp-ends-up-serving")
    run.checks.append(check_foreign_stamp_ends_up_serving(make_target(where)))
    return run


def adapter_options(pairs: list[str]) -> dict[str, str]:
    """`key=value` inputs, passed to the adapter uninterpreted.

    The driver has no flag for any particular target's inputs, and that is not
    fastidiousness: the first version of this file carried three named flags,
    one of which spelled out a product's own environment variable, and the
    target-neutrality guard caught it on the layer's first run. An adapter knows
    what its target needs; the driver knows only how to hand it over.
    """
    options: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--adapter-option wants key=value, got {pair!r}")
        options[key.strip()] = value
    return options


def run_fixtures(arena: Path, output: Path) -> int:
    """Drive every fail-control and record which state each assertion reached.

    This is the gate's own positive control, and it inverts the usual reading:
    a fixture built to fail an assertion must FAIL it, so this target is red
    when the fail-controls come back green. A layer whose assertions have all
    quietly stopped firing passes every target it is pointed at, and nothing
    else in the harness can see that.

    The committed artifact records verdicts, never paths: an arena lives under a
    scratch directory whose name is one machine's business, and
    `bench/results/**` is a public tree.
    """
    rows: list[dict] = []
    for name in adapters.fixtures():
        where = arena / name
        where.mkdir(parents=True, exist_ok=True)

        def make(at: Path, _name=name):
            at.mkdir(parents=True, exist_ok=True)
            return adapters.load(_name, at)

        run = assess(make, base_arena=where, log_dir=where / "trace",
                     drive_argv_for=lambda at, _name=name: [
                         sys.executable or "python3", str(Path(__file__).resolve()),
                         "--adapter", _name, "--arena", str(at), "--drive",
                     ])
        for check in run.checks:
            row = {"fixture": check.target, "check": check.check,
                   "requirement": check.requirement, "verb": check.verb,
                   "result": check.result, "clause": check.clause,
                   "falsified_by": check.falsified_by}
            if check.check == "R10-no-egress" and isinstance(check.detail, dict):
                subject = check.detail.get("subject") or {}
                row["attempt_counts"] = subject.get("attempt_counts")
            rows.append(row)
        log.info("%-22s %s", name, run.summary())

    reached = sorted({r["result"] for r in rows})
    per_check: dict[str, set] = {}
    for row in rows:
        per_check.setdefault(row["check"], set()).add(row["result"])
    never_red = sorted(c for c, states in per_check.items() if FAIL not in states)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "probe": ("the acceptance layer's own fail-controls: every assertion driven to "
                  "each state it can reach (SPEC.md §5.2.8; ticket 0578's Test section)"),
        "not_a_test_suite": (
            "these are fixtures, not targets. A red here is the instrument working: a "
            "fixture built to fail an assertion must fail it, and this artifact is red "
            "when the fail-controls come back green."),
        "date": time.strftime("%Y-%m-%d"),
        "states_reached": reached,
        "assertions_never_seen_red": never_red,
        "rows": rows,
    }, ensure_ascii=False, indent=2))

    log.info("wrote %s", output)
    if never_red:
        log.info("assertions never seen red against any fixture: %s", never_red)
        return 1
    log.info("every assertion was seen red against at least one fail-control")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--adapter", help="which target to run against; --list-adapters names them")
    ap.add_argument("--arena", help="a harness-owned directory the residue sweep may watch")
    ap.add_argument("--output", help="where the artifact lands; omitted in --drive mode")
    ap.add_argument("--log-dir", default="",
                    help="where the tracer's logs land (default: under the arena)")
    ap.add_argument("--drive", action="store_true",
                    help="inner mode: call the offered verbs and print what happened")
    ap.add_argument("--list-adapters", action="store_true")
    ap.add_argument("--fixtures", action="store_true",
                    help="run every fail-control and record which state each assertion reached")
    ap.add_argument("--adapter-option", action="append", default=[], metavar="KEY=VALUE",
                    help="an input this adapter needs; repeatable, passed through uninterpreted")
    a = ap.parse_args()
    options = adapter_options(a.adapter_option)

    if a.list_adapters:
        for name in adapters.available():
            print(name)
        return 0
    if a.fixtures:
        if not a.arena or not a.output:
            ap.error("--fixtures needs --arena and --output")
        return run_fixtures(Path(a.arena).resolve(), Path(a.output))
    if not a.adapter or not a.arena:
        ap.error("--adapter and --arena are required unless --list-adapters is given")

    arena = Path(a.arena).resolve()
    arena.mkdir(parents=True, exist_ok=True)

    def make_target(where: Path):
        where.mkdir(parents=True, exist_ok=True)
        return adapters.load(a.adapter, where, **options)

    if a.drive:
        print(json.dumps(drive(make_target(arena)), ensure_ascii=False, default=str))
        return 0

    if not a.output:
        ap.error("--output is required unless --drive is given")

    log_dir = Path(a.log_dir).resolve() if a.log_dir else arena / "trace"

    def drive_argv_for(where: Path) -> list[str]:
        passthrough: list[str] = []
        for key, value in options.items():
            passthrough += ["--adapter-option", f"{key}={value}"]
        return [
            sys.executable or "python3", str(Path(__file__).resolve()),
            "--adapter", a.adapter, "--arena", str(where), "--drive", *passthrough,
        ]

    run = assess(make_target, base_arena=arena, log_dir=log_dir,
                 drive_argv_for=drive_argv_for)
    run.write(Path(a.output))

    for check in run.checks:
        log.info("%-40s %-12s %s", check.check, check.result.upper(), check.clause)
    summary = run.summary()
    log.info(
        "target %s — %d pass, %d fail, %d not-offered, %d not-run",
        run.target.name,
        summary[PASS], summary[FAIL], summary[NOT_OFFERED], summary[NOT_RUN],
    )
    if summary[NOT_OFFERED] or summary[NOT_RUN]:
        log.info(
            "not-offered and not-run are neither red nor green: %d clause(s) had no "
            "surface on this target, and %d could not be looked at here",
            summary[NOT_OFFERED], summary[NOT_RUN],
        )
    log.info("wrote %s", a.output)
    return run.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
