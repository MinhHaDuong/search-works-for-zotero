"""The zoteus adapter derives its work-counter answer from the reply it just read.

Ticket 0624. The adapter used to write `"work": None` as a literal, justified by
a comment recording a measurement taken by hand. The measurement was right on the
day; the defect is that the adapter answered `None` whatever the target reported,
so the layer's `not-run` on R3's two clauses and R13's duplicate-work clause was
reachable by failing to look. A check whose all-clear is indistinguishable from
"I could not look" is not a check.

So the red test is the whole defect in one assertion: hand the adapter a status
payload that *does* carry counters and read what it answers. Against the constant
it answers `None`; against a derivation it answers the counters.

The nil itself is kept, and kept distinguishable: `work` is always a present key,
so `None` means "looked at this run's own status, found no counter object" and
never "the adapter forgot to populate it".

Everything here runs offline. No node process is spawned, nothing is written, and
the transport is replaced at the one seam — `_call` — where the adapter reaches
the target.
"""

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

adapter = importlib.import_module("bench.acceptance.adapters.zoteus")
durability = importlib.import_module("bench.acceptance.durability")
interface = importlib.import_module("bench.acceptance.interface")

#: The index status this target actually returns, trimmed to the keys the adapter
#: reads plus enough neighbours to show that a reply with no counter object is not
#: an empty reply. Measured shape, not an invented one.
NO_COUNTERS = {
    "embedderActive": True,
    "embedderModel": "a-local-model",
    "embedder": {"provider": "local"},
    "phase": "idle",
    "passages": 1200,
}

#: The same reply from a build that ships §5.2.8's counters. Nested, because that
#: is the shape a target grouping them would most plausibly emit.
WITH_COUNTERS = dict(NO_COUNTERS, work={
    "record": {"edit": {"done": 1}, "resync": {"noop": 3}},
    "embed": {"edit": {"done": 4}},
})

WHOAMI = {"embeddings": {"effective": "local"}}


def build(tmp_path, index_reply: dict, whoami: dict = WHOAMI):
    """An adapter whose transport is a fixture. Nothing is spawned."""
    target = adapter.Zoteus(tmp_path / "arena", entrypoint=tmp_path / "dist" / "index.js")

    def call(tool: str, arguments: dict) -> dict:
        return dict(whoami) if tool == "zotero_whoami" else dict(index_reply)

    target._call = call
    #: `settle` polls, and a fixture's ledger is updated synchronously; paying a
    #: real target's polling cost here would buy nothing.
    target.settle_poll_s = 0.0

    @contextmanager
    def running():
        yield

    target.running = running
    return target


# --- 1. the defect, in one assertion ----------------------------------------


def test_a_target_that_reports_counters_is_reported_as_reporting_them(tmp_path):
    """The red test of ticket 0624: the constant answered None regardless.

    This is the assertion the pre-fix adapter fails. It says nothing about
    whether today's build has counters — it says the adapter's answer is a
    function of the reply.
    """
    reported = build(tmp_path, WITH_COUNTERS).status()["work"]
    assert reported == {
        "work.record.edit.done": 1,
        "work.record.resync.noop": 3,
        "work.embed.edit.done": 4,
    }


def test_a_target_that_reports_none_still_answers_none(tmp_path):
    """The nil is preserved — it is now observed rather than typed.

    The measured shape of this target's status carries coverage and phase and no
    counter object, and the adapter must keep saying so.
    """
    assert build(tmp_path, NO_COUNTERS).status()["work"] is None


def test_the_key_is_present_even_when_the_answer_is_none(tmp_path):
    """`None` for "looked, found none" stays distinguishable from a missing key.

    The layer reads `status().get("work")`, which cannot tell an adapter that
    looked from one that forgot. The key's presence is the adapter's claim to
    have looked, and it is asserted here rather than trusted.
    """
    assert "work" in build(tmp_path, NO_COUNTERS).status()


# --- 2. what the derivation does and does not accept ------------------------


def test_an_already_flat_counter_object_is_not_prefixed_twice(tmp_path):
    """A target emitting the dotted names verbatim must not become `work.work.*`."""
    flat = {"work.embed.resync.noop": 2}
    reported = build(tmp_path, dict(NO_COUNTERS, work=flat)).status()["work"]
    assert reported == flat


def test_counters_grouped_under_the_generic_name_are_found(tmp_path):
    """§5.2.8 fixes the counter names, not the object that encloses them."""
    reply = dict(NO_COUNTERS, counters={"embed": {"edit": {"done": 7}}})
    assert build(tmp_path, reply).status()["work"] == {"work.embed.edit.done": 7}


def test_non_counters_beside_the_counters_are_dropped_not_coerced(tmp_path):
    """A phase string or a flag inside the object is not a count.

    The layer coerces with `int(v)`, which raises on a string; dropping the
    non-counters here keeps a neighbouring field from turning a readable reply
    into a crash, and keeps a boolean from being counted as 1.
    """
    reply = dict(NO_COUNTERS, work={"phase": "idle", "running": True,
                                    "embed": {"edit": {"done": 5}}})
    assert build(tmp_path, reply).status()["work"] == {"work.embed.edit.done": 5}


def test_an_empty_counter_object_reads_as_no_counters(tmp_path):
    """A `work` key holding nothing countable is not a target that reports counters."""
    assert build(tmp_path, dict(NO_COUNTERS, work={})).status()["work"] is None


# --- 3. the clauses that rest on it -----------------------------------------


def test_r13_decides_against_a_target_that_reports_counters(tmp_path):
    """The exit criterion: a fixture reporting counters makes the clause decide.

    R13's duplicate-work clause reads the counters and nothing else, and needs no
    perturbation, so it is the clause that shows the change end to end: `not-run`
    against the measured reply, a real verdict against a reply that has counters.
    """
    check = durability.check_two_processes_do_not_duplicate_work(
        build(tmp_path, WITH_COUNTERS), second=build(tmp_path, WITH_COUNTERS))
    assert check.result == interface.PASS


def test_r13_is_not_run_against_the_measured_reply(tmp_path):
    """The control: the same clause on the reply this target really sends.

    Without this the test above proves only that the check can pass, not that the
    counters are what decided it.
    """
    check = durability.check_two_processes_do_not_duplicate_work(
        build(tmp_path, NO_COUNTERS), second=build(tmp_path, NO_COUNTERS))
    assert check.result == interface.NOT_RUN
    assert "reports no work" in check.detail["why"]


def test_r3_stops_reporting_the_counter_absence_once_counters_arrive(tmp_path):
    """R3's edit clause no longer rests on "this target reports no counters".

    It still does not decide here, and honestly so: driving it needs an edit to
    the user's own library, which this adapter declines for reasons R15 owns. The
    assertion is that the *reason* is now that refusal and not the absence of
    counters — the gate this ticket is about has been passed.
    """
    check = durability.check_edit_recomputes_only_what_changed(
        build(tmp_path, WITH_COUNTERS))
    assert check.result == interface.NOT_RUN
    assert "reports no work" not in check.detail["why"]
    assert durability.EDIT_ONE_ITEM in check.detail["why"]
