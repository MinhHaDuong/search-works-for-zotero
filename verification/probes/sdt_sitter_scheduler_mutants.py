"""Which sitter-scheduler regressions does tests/sdt_sitter_scheduler.mjs actually detect?

A green suite says nothing about the defects it would catch. This breaks
`bench/sdt-sitter/scheduler.js` one edit at a time and reports, per mutant, which
tests go red. A mutant nothing catches is a regression class the suite does not
close; a mutant caught only by a test that already existed is a new test earning
nothing. Ticket 0690 used it both ways.

The runner is rebuilt from the real test file on each run, patched only to report
per-test verdicts instead of aborting on the first failure -- so the assertions
exercised here are the committed ones, not a copy that can drift.

    python3 verification/probes/sdt_sitter_scheduler_mutants.py     # from the repo root

Exit 0 when every mutant is caught. Non-zero when one survives, when an anchor no
longer matches (the scheduler moved under the probe), or when the unmutated suite
is not green to begin with -- a mutation result read off a red baseline is noise.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCHEDULER = pathlib.Path("bench/sdt-sitter/scheduler.js")
TESTS = pathlib.Path("tests/sdt_sitter_scheduler.mjs")

# `B` reads a binding the real loop does not have, so it ships its own setup edit.
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
     "              milliseconds: host.now() - state.startedAt });\n",
     ""),
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


def build_runner(directory: pathlib.Path) -> pathlib.Path:
    """The committed tests, reporting every verdict rather than throwing the first."""
    source = TESTS.read_text()
    source = source.replace(
        "async function test(name, body) { await body(); results.push(name); }",
        "async function test(name, body) { try { await body(); results.push(['PASS', name]); }"
        " catch (e) { results.push(['FAIL', name, e.message.split('\\n')[0]]); } }")
    source = source.split("console.log(JSON.stringify({ tests: results")[0]
    source += "for (const r of results) console.log(r.join(' | '));\n"
    runner = directory / "control_arm.mjs"
    runner.write_text(source)
    return runner


def failing_tests(runner: pathlib.Path) -> list[str]:
    done = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=120)
    if not done.stdout.strip():
        raise RuntimeError(done.stderr.strip().splitlines()[-1] if done.stderr else "no output")
    return [line.split(" | ")[1] for line in done.stdout.splitlines() if line.startswith("FAIL")]


def apply_mutant(pristine: str, label: str, old: str, new: str) -> str | None:
    source = pristine.replace(*HOIST_SETUP) if label.startswith("M7") else pristine
    if source.count(old) != 1:
        return None
    return source.replace(old, new)


def run(verbose: bool) -> int:
    workdir = pathlib.Path(tempfile.mkdtemp())
    try:
        runner = build_runner(workdir)
        pristine = SCHEDULER.read_text()

        red = failing_tests(runner)
        if red:
            print(f"baseline is not green ({len(red)} failing) — fix that before reading mutants")
            for name in red:
                print(f"  {name}")
            return 2
        print("baseline: all tests green\n")

        survivors, unanchored = [], []
        for label, old, new in MUTANTS:
            mutated = apply_mutant(pristine, label, old, new)
            if mutated is None:
                unanchored.append(label)
                print(f"{label}\n  ANCHOR LOST — the scheduler changed under this mutant")
                continue
            SCHEDULER.write_text(mutated)
            try:
                caught_by = failing_tests(runner)
            finally:
                SCHEDULER.write_text(pristine)
            if not caught_by:
                survivors.append(label)
                print(f"{label}\n  SURVIVES — no test detects it")
            else:
                print(f"{label}\n  caught by {len(caught_by)}:")
                if verbose:
                    for name in caught_by:
                        print(f"    {name}")
                else:
                    print(f"    {caught_by[0]}")

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
    return run(args.verbose)


if __name__ == "__main__":
    sys.exit(main())
