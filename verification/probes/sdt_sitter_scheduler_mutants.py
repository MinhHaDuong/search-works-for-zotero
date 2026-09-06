"""Which sitter-scheduler regressions does tests/sdt_sitter_scheduler.mjs actually detect?

A green suite says nothing about the defects it would catch. This breaks
`bench/sdt-sitter/scheduler.js` one edit at a time and reports, per mutant, which
tests go red. A mutant nothing catches is a regression class the suite does not
close; a mutant caught only by a test that already existed is a new test earning
nothing. Ticket 0690 used it both ways.

Nothing in the repository is written. Each mutant is applied to a copy in a
temporary directory, and the runner is rewritten to load the scheduler from
there -- so an interrupt, a CI timeout, a container stop, or a SIGKILL cannot
leave a mutated scheduler behind in a checkout that is shared between sessions.
A `finally` would not have covered the last two.

The runner is rebuilt from the real test file on each run, patched only to load
that copy and to report per-test verdicts instead of aborting on the first
failure -- so the assertions exercised here are the committed ones, not a copy
that can drift.

    python3 verification/probes/sdt_sitter_scheduler_mutants.py     # from the repo root

Exit 0 when every mutant is caught. Non-zero when one survives, when an anchor no
longer matches (the scheduler or the test file moved under the probe), or when the
unmutated suite is not green to begin with -- a mutation result read off a red
baseline is noise. Every anchor is required to match exactly once and every node
run is required to exit 0, because the failure mode this probe is most exposed to
is its own silence: a rewrite that quietly matched nothing, or a crashed child
whose output happens to contain no FAIL line, both look exactly like "all clear".
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCHEDULER = pathlib.Path("bench/sdt-sitter/scheduler.js")
TESTS = pathlib.Path("tests/sdt_sitter_scheduler.mjs")

SCHEDULER_LOAD = "fs.readFileSync('bench/sdt-sitter/scheduler.js', 'utf8')"
TEST_HARNESS = "async function test(name, body) { await body(); results.push(name); }"
REPORTING_HARNESS = (
    "async function test(name, body) { try { await body(); results.push(['PASS', name]); }"
    " catch (e) { results.push(['FAIL', name, e.message.split('\\n')[0]]); } }")
TAIL = "console.log(JSON.stringify({ tests: results"

# A mutant that restores an older shape needs more than one edit: the shape has a
# second half elsewhere in the file. Keyed by the mutant's label prefix, applied
# before the mutant's own edit, and anchored under the same replace_once rule -- a
# setup that silently matched nothing would leave a mutant that means something
# else entirely and still print a verdict.
SETUPS = {
    # `M7` reads a binding the real loop does not have.
    "M7": (
        "        for (const { id, before, status } of candidates) {",
        "        const hoisted = candidates.length ? await host.blocked(candidates[0].before) : null;\n"
        "        for (const { id, before, status } of candidates) {",
    ),
    # `M11` restores the increment that used to sit beside the census; its own edit
    # then removes the derivation, reconstituting the pre-0699 running total.
    "M11": (
        "            failed.add(before.identity);\n",
        "            failed.add(before.identity); state.failed++;\n",
    ),
}

MUTANTS = [
    ("M1 failure path does not decrement the document's original bucket",
     "            state.counts[status]--; state.counts['failed-session'] =",
     "            state.counts['failed-session'] ="),
    ("M2 failure path does not set state.error (the UI tooltip source)",
     "            state.error = host.describeError ? host.describeError(before, error) : String(error);\n",
     ""),
    ("M3 finally no longer clears state.active / state.pending (spinner sticks)",
     "          } finally {\n            state.active = null;\n"
     "            state.pending = state.pending.filter(item => item.id !== id);\n          }\n",
     "          }\n"),
    ("M4 resource block skips one document instead of halting the sweep",
     "if (reason) { state.phase = reason; publish(); break; }",
     "if (reason) { state.phase = reason; publish(); continue; }"),
    ("M5 success path stops accumulating duration samples",
     "            if (measured) state.samples.push(measured);\n",
     ""),
    ("M6 host.reportError is never called",
     "            if (host.reportError) await host.reportError(before, error);\n",
     ""),
    ("M7 host.blocked hoisted out of the per-candidate loop",
     "          const reason = await host.blocked(before);",
     "          const reason = hoisted;"),
    ("M8 per-candidate catch deleted, so a rejection ends the whole sweep",
     "          } catch (error) {\n            if (!state.enabled) break;\n"
     "            failed.add(before.identity);\n"
     "            state.error = host.describeError ? host.describeError(before, error) : String(error);\n"
     "            if (host.reportError) await host.reportError(before, error);\n"
     "            state.counts[status]--; state.counts['failed-session'] = "
     "(state.counts['failed-session'] || 0) + 1;\n",
     ""),
    # M9 and M10 are ticket 0699's two halves. The classification is now the single
    # owner of what "not indexed" means, so a status dropped from it is exactly the
    # under-report the ticket was filed for -- and the one that leaves every other
    # assertion in the suite green, because nothing throws and every bucket still
    # sums to the census.
    ("M9 inspection-error falls out of the failure classification (the 0699 under-report)",
     "  failed: ['failed-session', 'inspection-error', 'unsupported-pack', 'missing-source'],",
     "  failed: ['failed-session'],"),
    ("M10 a throwing duration observation reaches the verdict again (the 0699 false failure)",
     "              try { await host.observed(before, measured); }\n",
     "              await host.observed(before, measured);\n"
     "              try { /* the catch below is now unreachable */ }\n"),
    # The banner used to be incremented beside the census instead of derived from
    # it, so it grew by one sweep's failures every pass over an unchanged library.
    # Paired with the SETUPS["M11"] edit, this is exactly the pre-0699 shape.
    ("M11 the failure total accumulates across sweeps instead of reading this census",
     "    if (state.scanned === state.total) {\n"
     "      state.failed = SDT_STATUS_CLASSES.failed\n"
     "        .reduce((n, key) => n + (state.counts[key] || 0), 0);\n"
     "    }\n",
     ""),
    # The other half of the derivation, and the one only a mid-census observer can
    # see: an ungated recompute reads a `counts` the census has not finished
    # filling, so the banner empties at the top of every sweep and refills as the
    # scan runs. Every assertion taken after `sweep()` resolves is blind to it.
    ("M12 the failure total is recomputed from a half-filled census",
     "    if (state.scanned === state.total) {\n"
     "      state.failed = SDT_STATUS_CLASSES.failed\n"
     "        .reduce((n, key) => n + (state.counts[key] || 0), 0);\n"
     "    }\n",
     "    state.failed = SDT_STATUS_CLASSES.failed\n"
     "      .reduce((n, key) => n + (state.counts[key] || 0), 0);\n"),
    # Ticket 0704's two shapes, and the pair is the point: the duration is the one
    # number in this loop that regresses to a WRONG value rather than a missing
    # one, so no count moves and no record disappears when either lands.
    # M13 is the original defect. `state.startedAt` is still in scope and still
    # correct a few lines above, which makes it the easiest edit in the file to
    # make by accident.
    ("M13 duration sample measures from submission again, not from first progress",
     "                milliseconds: host.now() - extractingSince };",
     "                milliseconds: host.now() - state.startedAt };"),
    # M14 is the defect the FIRST fix carried, found by red team on PR #389 and
    # invisible to every test that had progress ticks in its fixture: falling back
    # to the submission clock when no tick ever fired reinstates the whole of M13
    # for exactly the documents too small or too cached to report progress. A
    # mutant rather than only a test, because the fallback is the reflex fix and
    # will be proposed again by whoever next reads a null here as a bug.
    ("M14 no-progress extraction falls back to the submission clock instead of withholding",
     "            const measured = extractingSince === null ? null\n",
     "            const measured = extractingSince === null\n"
     "              ? { sourceBytes: before.sourceBytes, pages: before.pages,\n"
     "                milliseconds: host.now() - state.startedAt }\n"),
]


class AnchorError(RuntimeError):
    """A string the probe rewrites no longer matches exactly once."""


def replace_once(source: str, old: str, new: str, what: str) -> str:
    """Substitute, refusing to guess when the anchor is not unique.

    A rewrite that matches nothing is the dangerous case: it leaves the source
    it meant to change intact and reports nothing, so every downstream verdict
    is measured against a probe that did not do what it says.
    """
    found = source.count(old)
    if found != 1:
        raise AnchorError(f"{what}: anchor matched {found} times, expected exactly 1")
    return source.replace(old, new)


def build_runner(directory: pathlib.Path, scheduler: pathlib.Path) -> pathlib.Path:
    """The committed tests, loading `scheduler` and reporting every verdict."""
    source = TESTS.read_text()
    source = replace_once(
        source, SCHEDULER_LOAD, f"fs.readFileSync({str(scheduler.resolve())!r}, 'utf8')",
        "scheduler load path")
    source = replace_once(source, TEST_HARNESS, REPORTING_HARNESS, "test harness")
    # Drop the tail: the cache, estimator and bootstrap assertions are not per-test,
    # and an uncaught throw there would be indistinguishable from a crashed run.
    if source.count(TAIL) != 1:
        raise AnchorError(f"tail marker: anchor matched {source.count(TAIL)} times, expected exactly 1")
    source = source.split(TAIL)[0]
    source += "for (const r of results) console.log(r.join(' | '));\n"
    runner = directory / "control_arm.mjs"
    runner.write_text(source)
    return runner


def failing_tests(runner: pathlib.Path) -> list[str]:
    """Names of the tests that went red. A crashed child is an error, not a silence."""
    done = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=120)
    if done.returncode != 0:
        tail = (done.stderr or done.stdout).strip().splitlines()
        raise RuntimeError(f"node exited {done.returncode}: {tail[-1] if tail else 'no output'}")
    if not done.stdout.strip():
        raise RuntimeError("node exited 0 but printed nothing")
    return [line.split(" | ")[1] for line in done.stdout.splitlines() if line.startswith("FAIL")]


def mutate(pristine: str, label: str, old: str, new: str) -> str:
    source = pristine
    for prefix, (setup_old, setup_new) in SETUPS.items():
        if label.split()[0] == prefix:
            source = replace_once(source, setup_old, setup_new, f"{prefix} setup")
    return replace_once(source, old, new, label)


def run(verbose: bool) -> int:
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="sdt-mutants-"))
    try:
        pristine = SCHEDULER.read_text()
        scratch = workdir / SCHEDULER.name
        scratch.write_text(pristine)
        runner = build_runner(workdir, scratch)

        red = failing_tests(runner)
        if red:
            print(f"baseline is not green ({len(red)} failing) — fix that before reading mutants")
            for name in red:
                print(f"  {name}")
            return 2
        print("baseline: all tests green\n")

        survivors, unanchored = [], []
        for label, old, new in MUTANTS:
            try:
                scratch.write_text(mutate(pristine, label, old, new))
            except AnchorError as error:
                unanchored.append(label)
                print(f"{label}\n  ANCHOR LOST — {error}")
                continue
            caught_by = failing_tests(runner)
            if not caught_by:
                survivors.append(label)
                print(f"{label}\n  SURVIVES — no test detects it")
            else:
                print(f"{label}\n  caught by {len(caught_by)}:")
                for name in (caught_by if verbose else caught_by[:1]):
                    print(f"    {name}")

        print(f"\n{len(MUTANTS) - len(survivors) - len(unanchored)}/{len(MUTANTS)} caught")
        return 1 if survivors or unanchored else 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verbose", action="store_true",
                        help="name every test that catches a mutant, not just the first")
    args = parser.parse_args()
    if not SCHEDULER.exists() or not TESTS.exists():
        parser.error("run from the repository root")
    try:
        return run(args.verbose)
    except (AnchorError, RuntimeError) as error:
        print(f"probe failed: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
