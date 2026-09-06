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

# `M7` reads a binding the real loop does not have, so it ships its own setup edit.
HOIST_SETUP = (
    "        for (const { id, before, status } of candidates) {",
    "        const hoisted = candidates.length ? await host.blocked(candidates[0].before) : null;\n"
    "        for (const { id, before, status } of candidates) {",
)

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
     "            state.samples.push({ sourceBytes: before.sourceBytes, pages: before.pages,\n"
     "              milliseconds: host.now() - (extractingSince ?? state.startedAt) });\n",
     ""),
    # Ticket 0704's defect, kept as a mutant rather than only as a test: the
    # sample is the one number here that is wrong rather than absent when it
    # regresses, and a wrong duration is invisible in every count the other
    # mutants move. It reads state.startedAt, which is still right there and
    # still legitimately used two lines above — the easiest edit in the file to
    # make by accident.
    ("M9 duration sample measures from submission again, not from first progress",
     "              milliseconds: host.now() - (extractingSince ?? state.startedAt) });",
     "              milliseconds: host.now() - state.startedAt });"),
    ("M6 host.reportError is never called",
     "            if (host.reportError) await host.reportError(before, error);\n",
     ""),
    ("M7 host.blocked hoisted out of the per-candidate loop",
     "          const reason = await host.blocked(before);",
     "          const reason = hoisted;"),
    ("M8 per-candidate catch deleted, so a rejection ends the whole sweep",
     "          } catch (error) {\n            if (!state.enabled) break;\n"
     "            failed.add(before.identity); state.failed++;\n"
     "            state.error = host.describeError ? host.describeError(before, error) : String(error);\n"
     "            if (host.reportError) await host.reportError(before, error);\n"
     "            state.counts[status]--; state.counts['failed-session'] = "
     "(state.counts['failed-session'] || 0) + 1;\n",
     ""),
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
    source = replace_once(pristine, *HOIST_SETUP, "hoist setup") if label.startswith("M7") else pristine
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
