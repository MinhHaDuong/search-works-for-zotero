"""Every driver that reports a per-unit rate warms before its timing window.

Ticket 0260. A benchmark driver times a window containing a cost paid once — a model
download, a graph initialisation, a cache fill, a JIT warm-up — and reports the result
as a per-unit rate. The first run is then wrong by that cost divided by the unit count,
and nothing in the artifact says which kind of run it was.

This class has already cost a retraction from the ratification ledger, which is the most
expensive place in this repo to be wrong: an append-only entry is never edited again. A
set of embedder RSS figures was taken on each model's FIRST load, so the weight download
sat inside the window: 364,8 MB cold against 410,2 MB warm on one rung and 453,5 against
404,9 on another — 45 to 49 MB of error, in BOTH directions, so it did not even bias
consistently, against an 11,7 MB difference the numbers were being used to argue about.
A vocab x dim memory model was fitted on those, reproduced its calibration point to a
tenth of a megabyte, and missed its first out-of-sample test by 106 MB. Re-measured warm
over five fresh processes the spread is 2,5 to 6,9 MB: the instrument was fine and the
protocol was not.

The discipline already existed here, held per author and enforced nowhere. Ticket 0240
carried "warm only, and repeat every cell" as prose the executor was asked to follow.
Prose is what failed. This is the mechanical form.

SOURCE INSPECTION, not execution, and deliberately so: the drivers need corpora that are
not in this repository, so a test that ran them could not run here at all. What it can do
is read the shape — and the shape is what regressed.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"

#: A driver reports a per-unit rate if it divides an elapsed time by a unit count and
#: publishes the quotient. These are the key names this repo uses for that quotient.
#: Deliberately the emitted KEY rather than the arithmetic: a rate computed and never
#: reported harms nobody, and a rate reported is a promise about a steady state.
RATE_KEY = re.compile(r"\b(ms_per_[a-z0-9_]+|passages_per_min|hours_to_index)\s*:")

#: `const embedMs = performance.now() - t1;` — an elapsed time, and the variable that
#: opened its window. Resolving the window through the arithmetic rather than guessing
#: at "the last clock" is the whole difficulty: every one of these drivers reads the
#: clock four times, and only one of those reads opens the window the rate divides.
#: Written to tolerate the three spellings actually in the tree — a bare subtraction
#: (`= performance.now() - t1`), a parenthesised one already divided down
#: (`= (performance.now() - t1) / texts.length`), and a coerced one (`= +(...)`).
ELAPSED = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"[^;\n]*?performance\.now\(\)\s*-\s*(?P<start>[A-Za-z_$][\w$]*)"
)

#: `const t1 = performance.now();` — where a window opens.
def _opens_at(source: str, variable: str) -> int | None:
    match = re.search(
        r"\b(?:const|let|var)\s+" + re.escape(variable) + r"\s*=\s*performance\.now\(\)",
        source,
    )
    return match.start() if match else None


#: A warm call: an inference issued for its side effect before the clock. The repo's
#: correct drivers all write it as an awaited extractor call, plus an explicit
#: `warm-up:` marker for a driver whose warm-up is shaped differently and says so.
WARM_CALL = re.compile(r"await\s+extractor\(|warm-up:")


def drivers_reporting_a_rate() -> list[Path]:
    found = []
    for path in sorted(BENCH.glob("*.mjs")):
        if RATE_KEY.search(path.read_text(encoding="utf-8")):
            found.append(path)
    return found


def warms_before_its_timing_window(source: str) -> bool:
    """Is a warm call issued before the window the reported rate is divided out of?

    Resolved rather than guessed: read the rate's numerator off the emitted key, find
    where that elapsed variable was computed, read the variable it subtracts, and find
    where THAT was assigned the clock. Anything this cannot resolve returns False —
    "I could not tell" is not a pass, which is the rule the whole ticket rests on.
    """
    rate = RATE_KEY.search(source)
    if rate is None:
        return False
    # The numerator: the first elapsed variable named in the rate's own statement.
    line_end = source.find("\n", rate.end())
    statement = source[rate.end(): line_end if line_end != -1 else len(source)]
    elapsed_names = {m.group("name"): m for m in ELAPSED.finditer(source)}
    numerator = next((n for n in elapsed_names if n in statement), None)
    if numerator is None:
        return False
    start_variable = elapsed_names[numerator].group("start")
    opens = _opens_at(source, start_variable)
    if opens is None:
        return False
    return any(m.start() < opens for m in WARM_CALL.finditer(source))


def test_the_inventory_is_not_empty():
    """A scan that found nothing would pass silently and look like coverage."""
    assert drivers_reporting_a_rate(), (
        "no bench/*.mjs reports a per-unit rate — either the naming convention moved "
        "or this test stopped looking. A guard whose all-clear is indistinguishable "
        "from not looking is not a guard."
    )


@pytest.mark.parametrize(
    "driver", drivers_reporting_a_rate(), ids=lambda p: p.name
)
def test_a_rate_reporting_driver_warms_before_its_timing_window(driver: Path):
    assert warms_before_its_timing_window(driver.read_text(encoding="utf-8")), (
        f"{driver.relative_to(REPO)} publishes a per-unit rate but issues no warm call "
        f"before the window it divides. The first batch then pays graph initialisation, "
        f"and on a cold cache the model download, inside the rate. Copy the pattern in "
        f"bench/embed_feasibility.mjs. Ticket 0260."
    )


# --- the positive control ----------------------------------------------------------
#
# Both directions, run and recorded. A guard written after the fix and never seen
# failing is indistinguishable from one that cannot look — which is the same defect
# class as the bug it guards.


PRE_FIX_QUANT_FIDELITY = """
const t0 = performance.now();
const extractor = await pipeline('feature-extraction', modelRepo, pipelineOpts);
const loadMs = performance.now() - t0;

const t1 = performance.now();
for (let i = 0; i < texts.length; i += BATCH) {
  const tensor = await extractor(batch, { pooling, normalize: false });
}
const embedMs = performance.now() - t1;
const row = { ms_per_passage: Number((embedMs / texts.length).toFixed(2)) };
"""

POST_FIX_QUANT_FIDELITY = """
const t0 = performance.now();
const extractor = await pipeline('feature-extraction', modelRepo, pipelineOpts);
const loadMs = performance.now() - t0;

const tWarm = performance.now();
await extractor(texts.slice(0, BATCH), { pooling, normalize: false });
const warmMs = performance.now() - tWarm;

const t1 = performance.now();
for (let i = 0; i < texts.length; i += BATCH) {
  const tensor = await extractor(batch, { pooling, normalize: false });
}
const embedMs = performance.now() - t1;
const row = { warm: true, ms_per_passage: Number((embedMs / texts.length).toFixed(2)) };
"""


def test_the_control_fails_on_the_shape_quant_fidelity_actually_had():
    """quant_fidelity.mjs as it stood on 2026-09-01, verbatim in shape.

    Its headline outputs are cosine and overlap and are unaffected by the protocol
    error, which is exactly why this went unnoticed for two campaigns.
    """
    assert not warms_before_its_timing_window(PRE_FIX_QUANT_FIDELITY)


def test_the_control_passes_after_the_warm_call_is_added():
    assert warms_before_its_timing_window(POST_FIX_QUANT_FIDELITY)


def test_a_load_clock_alone_does_not_satisfy_the_check():
    """The one-clock case: no separate window at all, so the load IS in the rate."""
    source = """
    const t0 = performance.now();
    const extractor = await pipeline('feature-extraction', repo);
    const ms = performance.now() - t0;
    const row = { ms_per_passage: ms / n };
    """
    assert not warms_before_its_timing_window(source)


# --- the Python side: aggregators propagate, they do not invent --------------------
#
# Two bench/*.py report a per-unit rate and neither opens a timing window of its own.
# measure_throughput_reps.py invokes the .mjs measurer once per rep and reads the rate
# back; gpu_feasibility.py parses a rate out of a log. For both, warmth is a property
# of the run underneath, so the only honest thing they can do is carry it forward — or
# say they cannot. A second-hand claim dressed as a measurement is the same defect one
# level up.

PY_RATE = re.compile(r"[\"'](?:ms_per_passage|ms_per_passage_median|passages_per_min)[\"']\s*:")


def python_rate_reporters() -> list[Path]:
    found = []
    for path in sorted(BENCH.glob("*.py")):
        if path.name.startswith("check_"):
            continue  # the guards quote these key names to reason about them
        if PY_RATE.search(path.read_text(encoding="utf-8")):
            found.append(path)
    return found


def test_the_python_inventory_is_not_empty():
    assert python_rate_reporters()


@pytest.mark.parametrize("driver", python_rate_reporters(), ids=lambda p: p.name)
def test_a_python_rate_reporter_states_its_warmth(driver: Path):
    """It must emit a `warm` key — propagated from its source, or None for cannot-say.

    Not "must be warm": these drivers cannot warm anything. Must SAY. An artifact that
    cannot say is as bad as one that lies, and check_figures refuses both.
    """
    source = driver.read_text(encoding="utf-8")
    assert re.search(r"[\"']warm[\"']\s*:", source), (
        f"{driver.relative_to(REPO)} reports a per-unit rate but writes no `warm` key. "
        f"Propagate it from the run it reads, or write None to say it cannot know. "
        f"Ticket 0260."
    )
