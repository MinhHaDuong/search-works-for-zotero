"""Which bootstrap.js regressions do the sitter's JavaScript suites actually detect?

The sibling of `sdt_sitter_scheduler_mutants.py`, pointed at the other file. It
exists because ticket 0695's acceptance asks that each new scenario be shown red
against a deliberately broken implementation, and a red run recorded once in a
merge request is a fact nobody can re-derive. This makes it a gate: break
`bench/sdt-sitter/bootstrap.js` one edit at a time and report, per mutant, which
tests go red. A mutant nothing catches is a regression class the suites leave
open; a mutant caught only by a test that predates the ticket is a new test
earning nothing.

Nothing in the repository is written. The whole plugin and the whole test tree
are copied into a temporary directory and node is run with that directory as its
working directory, so the tests' own relative paths (`bench/sdt-sitter/...`, and
the mock's `./sdt_sitter_zotero_mock.mjs`) resolve to the copies with no path
rewriting at all -- and an interrupt, a CI timeout or a SIGKILL cannot leave a
mutated bootstrap behind in a checkout shared between sessions.

Each runner is rebuilt from the committed test file, patched only to report
per-test verdicts instead of aborting on the first failure, so the assertions
exercised here are the committed ones rather than a copy that can drift.

    python3 verification/probes/sdt_sitter_bootstrap_mutants.py     # from the repo root

Exit 0 when every mutant is caught. Non-zero when one survives, when an anchor no
longer matches (bootstrap.js or a test file moved under the probe), or when the
unmutated suites are not green to begin with -- a mutation result read off a red
baseline is noise. Every anchor is required to match exactly once and every node
run is required to exit 0, because the failure this probe is most exposed to is
its own silence: a rewrite that quietly matched nothing, and a crashed child
whose output happens to contain no FAIL line, both look exactly like "all clear".
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

BOOTSTRAP = pathlib.Path("bench/sdt-sitter/bootstrap.js")
PLUGIN = pathlib.Path("bench/sdt-sitter")
TESTS = pathlib.Path("tests")

#: The suites that load bootstrap.js. Both report one line per test, so a mutant's
#: verdict names the assertion that caught it rather than the file.
RUNNERS = ("sdt_sitter_bootstrap.mjs", "sdt_sitter_scheduler.mjs")

TEST_HARNESS = "async function test(name, body) { await body(); results.push(name); }"
REPORTING_HARNESS = (
    "async function test(name, body) { try { await body(); results.push(['PASS', name]); }"
    " catch (e) { results.push(['FAIL', name, String(e.message).split('\\n')[0]]); } }")
TAIL = "console.log(JSON.stringify({ tests: results"

MUTANTS = [
    # ---- the real blocked(), which no test reached before ticket 0695 --------
    ("M1 an unreadable /proc escapes blocked() instead of refusing admission",
     "    } catch (error) {\n"
     "      if (alive && sitter) sitter.state.error = `Lecture des ressources : ${error}`;\n"
     "      return 'resources-unavailable';\n"
     "    }\n",
     "    } catch (error) { throw error; }\n"),
    # The readings are kept where they are TAKEN, not where the verdict is
    # returned, so the diagnostics panel can say how far from the threshold the
    # gate was even on a healthy sitter. Moved below the check, the panel is blank
    # in exactly the state it is opened to explain.
    ("M2 the admission reading is recorded only on the refusing branch",
     "      admission = { at: monotonic(), memoryAvailableBytes: available };\n"
     "      if (!Number.isFinite(available)) return 'resources-unavailable';\n",
     "      if (!Number.isFinite(available)) return 'resources-unavailable';\n"
     "      admission = { at: monotonic(), memoryAvailableBytes: available };\n"),

    # ---- the cache file, as the next session finds it ------------------------
    ("M3 one corrupt cache row aborts the whole load instead of being skipped",
     "      } catch (error) { /* Ignore incomplete/corrupt cache rows. */ }\n",
     "      } catch (error) { throw error; }\n"),
    ("M4 a row stamped with another pack version is loaded anyway",
     "        if (row.versions !== raw.versions || typeof row.key !== 'string') continue;",
     "        if (typeof row.key !== 'string') continue;"),
    ("M5 a failed cache write is silent again",
     "        if (!cacheFailing) {\n"
     "          cacheFailing = true;\n"
     "          emit('cache-error', { error: classifyError(error), compact }, 'error');\n"
     "        }\n",
     ""),
    # The latch is what keeps one unwritable directory from evicting the ring:
    # saveCache runs once per settled duration, so an unlatched record is one per
    # document for the life of the session.
    ("M6 the cache-write failure is recorded per attempt, not per episode",
     "        if (!cacheFailing) {\n"
     "          cacheFailing = true;\n"
     "          emit('cache-error', { error: classifyError(error), compact }, 'error');\n"
     "        }\n",
     "        cacheFailing = true;\n"
     "        emit('cache-error', { error: classifyError(error), compact }, 'error');\n"),
    ("M7 the pack versions fall out of the cache identity, so a stale pack is trusted",
     "      identity: `${item.libraryID}/${item.key}/${hash}/${JSON.stringify(versions)}` };",
     "      identity: `${item.libraryID}/${item.key}/${hash}` };"),

    # ---- the dialog and the second window ------------------------------------
    ("M8 a second dialog is opened instead of raising the one already open",
     "  for (const existing of dialogs) {\n    if (!existing.closed) {\n",
     "  for (const existing of dialogs) {\n    if (false) {\n"),
    ("M9 a closed dialog is never dropped from the render set",
     "  dialog.addEventListener('unload', () => { dialogs.delete(dialog); noteDialogClose(dialog); }, { once: true });",
     "  dialog.addEventListener('unload', () => { noteDialogClose(dialog); }, { once: true });"),
    # Two main windows put two initialize() calls in flight; the generation token
    # is the only thing that stops the loser building a second sitter, prompting
    # the author twice and submitting every document twice. Written as the ONE
    # edit that makes the whole mechanism inert rather than as the removal of a
    # single `token !== generation` guard: there are five of them along
    # initialize(), so removing one only moves the stand-down to the next.
    ("M10 startup() does not supersede the initialize() already in flight",
     "function startup({ rootURI }) {\n  const token = ++generation;",
     "function startup({ rootURI }) {\n  const token = generation;"),
    ("M11 shutdown leaves the sweep, pulse and heartbeat timers armed",
     "    if (timers) { timers.clearTimeout(timer); timers.clearInterval(pulse); timers.clearInterval(heartbeat); }\n",
     ""),
    # Clearing the handles is not enough on its own: the sweep wrapper re-arms
    # `timer` from inside its own finally, so a sweep already in flight schedules
    # the next one after shutdown has cleared it.
    ("M12 shutdown clears the timers but does not burn the generation token",
     "    ++generation; alive = false; sitter?.stop();",
     "    alive = false; sitter?.stop();"),

    # ---- the two clocks -------------------------------------------------------
    ("M13 the finish-time projection ignores the empirical upper bound",
     "    const globalEstimate = !overrun && s.scanned === s.total && s.fittedSamples.length >= 3",
     "    const globalEstimate = s.scanned === s.total && s.fittedSamples.length >= 3"),
    ("M14 the elapsed line reads the wall clock again",
     "    const elapsed = s.active === null ? null : Math.round((monotonic() - s.startedAt) / 1000);",
     "    const elapsed = s.active === null ? null : Math.round((Date.now() - s.startedAt) / 1000);"),
    ("M15 the scheduler is stamped with the wall clock again",
     "    inspect, blocked, now: monotonic, changed: render,",
     "    inspect, blocked, now: () => Date.now(), changed: render,"),
    ("M16 the heartbeat's ages read the wall clock again",
     "  const age = since => (since == null ? null : monotonic() - since);",
     "  const age = since => (since == null ? null : Date.now() - since);"),
    # The fallback for a host with no monotonic source at all. Unratcheted it is
    # simply the wall clock, which is the defect the whole clock carries.
    ("M17 the wall-clock fallback is not ratcheted, so it can be read backwards",
     "  monotonicFloor = Math.max(monotonicFloor, Date.now());\n  return monotonicFloor;",
     "  return Date.now();"),
    # The two spans a reader never sees as a stopwatch, and so the two most
    # likely to drift back to the calendar unnoticed. SPEC.md advertises a
    # behavioural consequence for the first: 0701's window bounds RUNNING time.
    ("M18 the source-hash re-verify window reads the wall clock again",
     "    const hash = await sourceHashes.hash(cacheKey, sourcePath, source, monotonic(),",
     "    const hash = await sourceHashes.hash(cacheKey, sourcePath, source, Date.now(),"),
    ("M19 the admission panel ages its reading on the wall clock again",
     "    `Dernière mesure il y a ${formatSDTAge(monotonic() - admission.at)}",
     "    `Dernière mesure il y a ${formatSDTAge(Date.now() - admission.at)}"),
    # The three tiers of the clock, and the guards that decide which one answers.
    # Each of these changes the clock the whole sitter runs on and moves nothing
    # else, which is what makes them the hardest edits in this file to notice.
    ("M20 a non-numeric ChromeUtils.now reading is believed instead of skipped",
     "      const reading = ChromeUtils.now();\n      if (Number.isFinite(reading)) return reading;",
     "      return ChromeUtils.now();"),
    # A torn-down compartment can throw from a getter, and this call is made ten
    # times a second from the render loop. Absent and throwing are not the same
    # host, and only the guard makes them behave the same way.
    ("M21 a throwing ChromeUtils.now escapes instead of falling through",
     "  try {\n"
     "    if (typeof ChromeUtils === 'object' && typeof ChromeUtils.now === 'function') {\n"
     "      const reading = ChromeUtils.now();\n"
     "      if (Number.isFinite(reading)) return reading;\n"
     "    }\n"
     "  } catch (_error) { /* Fall through to the next source. */ }\n",
     "  if (typeof ChromeUtils === 'object' && typeof ChromeUtils.now === 'function') {\n"
     "    const reading = ChromeUtils.now();\n"
     "    if (Number.isFinite(reading)) return reading;\n"
     "  }\n"),
    ("M22 the performance.now tier is never consulted",
     "    if (typeof performance === 'object' && typeof performance.now === 'function') {\n"
     "      const reading = performance.now();\n"
     "      if (Number.isFinite(reading)) return reading;\n"
     "    }\n",
     ""),
]


class AnchorError(RuntimeError):
    """A string the probe rewrites no longer matches exactly once."""


def replace_once(source: str, old: str, new: str, what: str) -> str:
    """Substitute, refusing to guess when the anchor is not unique.

    A rewrite that matches nothing is the dangerous case: it leaves the source it
    meant to change intact and reports nothing, so every downstream verdict is
    measured against a probe that did not do what it says.
    """
    found = source.count(old)
    if found != 1:
        raise AnchorError(f"{what}: anchor matched {found} times, expected exactly 1")
    return source.replace(old, new)


def build_tree(workdir: pathlib.Path) -> None:
    """A whole working copy, so every relative path in the tests still resolves."""
    shutil.copytree(PLUGIN, workdir / PLUGIN)
    (workdir / TESTS).mkdir(parents=True)
    for path in TESTS.glob("sdt_sitter_*.mjs"):
        shutil.copy(path, workdir / TESTS / path.name)
    for name in RUNNERS:
        source = (workdir / TESTS / name).read_text()
        source = replace_once(source, TEST_HARNESS, REPORTING_HARNESS, f"{name}: test harness")
        # Drop the tail: the estimator, cache and tooltip assertions below it are
        # not per-test, and an uncaught throw there is indistinguishable from a
        # crashed run.
        if source.count(TAIL) != 1:
            raise AnchorError(f"{name}: tail marker matched {source.count(TAIL)} times, expected 1")
        source = source.split(TAIL)[0]
        source += "for (const r of results) console.log(r.join(' | '));\n"
        (workdir / TESTS / name).write_text(source)


def failing_tests(workdir: pathlib.Path) -> list[str]:
    """Names of the tests that went red. A crashed child is an error, not a silence."""
    red = []
    for name in RUNNERS:
        done = subprocess.run(["node", f"tests/{name}"], cwd=workdir,
                              capture_output=True, text=True, timeout=180)
        if done.returncode != 0:
            tail = (done.stderr or done.stdout).strip().splitlines()
            raise RuntimeError(f"{name}: node exited {done.returncode}: "
                               f"{tail[-1] if tail else 'no output'}")
        if not done.stdout.strip():
            raise RuntimeError(f"{name}: node exited 0 but printed nothing")
        red += [line.split(" | ")[1] for line in done.stdout.splitlines() if line.startswith("FAIL")]
    return red


def run(verbose: bool) -> int:
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="sdt-bootstrap-mutants-"))
    try:
        build_tree(workdir)
        pristine = BOOTSTRAP.read_text()
        scratch = workdir / BOOTSTRAP

        red = failing_tests(workdir)
        if red:
            print(f"baseline is not green ({len(red)} failing) — fix that before reading mutants")
            for name in red:
                print(f"  {name}")
            return 2
        print("baseline: all tests green\n")

        survivors, unanchored = [], []
        for label, old, new in MUTANTS:
            try:
                scratch.write_text(replace_once(pristine, old, new, label))
            except AnchorError as error:
                unanchored.append(label)
                print(f"{label}\n  ANCHOR LOST — {error}")
                continue
            caught_by = failing_tests(workdir)
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
    if not BOOTSTRAP.exists() or not (TESTS / RUNNERS[0]).exists():
        parser.error("run from the repository root")
    try:
        return run(args.verbose)
    except (AnchorError, RuntimeError) as error:
        print(f"probe failed: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
