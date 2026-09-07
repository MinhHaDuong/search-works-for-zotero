"""The red-state harness's own guards (ticket 0722, item 1 of 0029's closeout order).

The exercise exists because a green golden run and a vacuous one are the same artifact.
That failure mode reproduces one level up: a differ that reports "nothing went red" when it
is itself broken is indistinguishable from a bank that cannot fail. So every test here is a
control rather than a coverage tick:

  * the predicates are pinned to two numbers measured on the committed report (161/195 and
    42/195). Without them, "no cell went red" and "my predicate code is wrong" print the same;
  * the identity transform's delta must be empty, which is the differ's negative control;
  * each real transform must be non-identity, which is the *positive* control — a transform
    that changes nothing is precisely the vacuity the ticket exists to catch.

Fast tier: no build, no node, no network. The two that read the committed report parse a
712 KB JSON once and are shared through a module-scoped fixture.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

import redstate  # noqa: E402
from golden_gate import InputError, load_replies  # noqa: E402

BASELINE_REPORT = REPO / "bench" / "results" / "golden" / "report.json"
BASELINE_REPLIES = REPO / "bench" / "results" / "golden" / "replies.json"
EXPORT = REPO / "bench" / "fixtures" / "export"

#: Measured on the committed report of build b0e0bc8 over export 579ab8dd…2296ccc. These are
#: the predicate code's positive control: a change to either is a change to what "present"
#: means, which is the author's open ruling on PR #409 and never a silent edit here.
SHIPPED_PRESENT = 161
EVIDENCE_MATCHED_PRESENT = 42
SCORED = 195


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def export():
    return redstate.load_export(EXPORT)


@pytest.fixture(scope="module")
def baseline_bundle() -> dict:
    return json.loads(BASELINE_REPLIES.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- the arms


def test_every_non_control_arm_declares_targets():
    """An arm without a declared target cannot be shown to have missed anything."""

    for arm in redstate.ARMS:
        if arm.control:
            continue
        assert arm.target_lanes, f"{arm.name} declares no target lane"
        assert arm.target_mechanisms, f"{arm.name} declares no target mechanism"


def test_every_not_run_arm_states_its_reason():
    for arm in redstate.ARMS:
        if arm.runnable:
            assert arm.not_run_reason is None, f"{arm.name} is runnable but carries a not-run reason"
        else:
            assert arm.not_run_reason, f"{arm.name} is not-run and says nothing about why"


def test_arm_names_are_unique_and_kinds_are_known():
    names = [arm.name for arm in redstate.ARMS]
    assert len(names) == len(set(names))
    for arm in redstate.ARMS:
        assert arm.kind in ("build", "reply")
        if arm.kind == "reply" and arm.runnable:
            assert arm.transform in redstate.REPLY_TRANSFORMS, f"{arm.name} names no known transform"
        if arm.kind == "build" and arm.runnable and not arm.control:
            assert arm.patches, f"{arm.name} is a runnable build arm with no patch"


def test_build_patches_still_match_the_fork_source():
    """A patch that no longer matches would make an arm silently a no-op rebuild.

    Skipped rather than failed where fork/ is absent: it is git-ignored and cloned on demand,
    so its absence is a missing prerequisite, not a defect in this repo.
    """

    for arm in redstate.ARMS:
        for relative, old, _new in arm.patches:
            path = REPO / relative
            if not path.is_file():
                pytest.skip(f"{relative} absent (fork/ not checked out)")
            assert path.read_text(encoding="utf-8").count(old) == 1, (
                f"{arm.name}: {relative} no longer holds exactly one copy of the patched text"
            )


# --------------------------------------------------------------------------- the predicates


def test_shipped_predicate_reproduces_the_committed_reading(report):
    scored = redstate.scored_entries(report)
    assert len(scored) == SCORED
    assert len(redstate.present_set(report, "shipped")) == SHIPPED_PRESENT


def test_evidence_matched_predicate_reproduces_the_committed_reading(report):
    assert len(redstate.present_set(report, "evidence-matched")) == EVIDENCE_MATCHED_PRESENT


def test_the_two_predicates_disagree_structurally(report):
    """They are not two readings of one number: one is a strict subset of the other."""

    shipped = redstate.present_set(report, "shipped")
    matched = redstate.present_set(report, "evidence-matched")
    assert matched < shipped
    assert len(shipped - matched) == SHIPPED_PRESENT - EVIDENCE_MATCHED_PRESENT


def test_twin_excluded_sits_between_the_two(report):
    shipped = redstate.present_set(report, "shipped")
    matched = redstate.present_set(report, "evidence-matched")
    twinless = redstate.present_set(report, "twin-excluded")
    assert matched <= twinless <= shipped
    assert twinless < shipped, "no question rides the work-twin path — the third reading would be vacuous"


def test_cross_lingual_must_cells_have_no_evidence_matched_headroom(report):
    """The measurement that shapes the whole reading, held as a fixture.

    Under the evidence-matched predicate all six cross-lingual MUST cells already read zero
    present at baseline, so no arm can make them redder. If this ever fails, the reading's
    central claim has moved and the artifact must be rewritten, not patched.
    """

    scored = redstate.scored_entries(report)
    matched = redstate.present_set(report, "evidence-matched")
    for lane in redstate.MUST_LANES_CROSSLINGUAL:
        keys = {key for key, entry in scored.items() if entry["lane"] == lane}
        assert keys, f"{lane} holds no scored question"
        assert not (keys & matched), f"{lane} has evidence-matched headroom; the reading assumed none"


# --------------------------------------------------------------------------- the differ


def test_the_differ_reports_nothing_on_a_report_against_itself(report):
    """The negative control: a differ that cannot say 'nothing changed' cannot say anything."""

    arm = redstate.ARMS_BY_NAME["null-reply"]
    for predicate in redstate.PREDICATES:
        document = redstate.compute_delta(arm, predicate, report, report, {})
        assert document["changed"] == {}
        assert document["delta"] == 0
        assert document["mechanisms_fired"] == {}
        assert document["expected_miss_flips"] == {}


def test_the_differ_names_a_cell_that_stayed_green_and_says_why(report):
    """The positive control for `must_cells_that_did_not_go_red`, on a hand-built pair.

    One en->en question is flipped from present to absent; every other MUST cell is
    untouched, so the differ must report the untouched ones and must distinguish a cell with
    no headroom from one the arm simply did not reach.
    """

    arm = redstate.ARMS_BY_NAME["global-shuffle-sim"]
    after = copy.deepcopy(report)
    scored = redstate.scored_entries(after)
    victim = next(key for key, entry in scored.items() if entry["lane"] == "en->en" and entry["r34_present"])
    after["questions"][victim]["r34_present"] = False
    for row in after["questions"][victim]["rows"]:
        row["level"] = "miss"
        row["evidence"] = None

    document = redstate.compute_delta(arm, "shipped", report, after, {})
    assert document["changed"][victim]["to"] == "absent"
    assert document["must_cells"]["en->en"]["went_red"] is True
    stayed = {cell["lane"]: cell["reason"] for cell in document["must_cells_that_did_not_go_red"]}
    assert "en->en" not in stayed
    assert stayed, "every other MUST cell was untouched and none was reported"
    assert set(stayed.values()) <= {"not-reached", "no-headroom", "no-question"}

    matched = redstate.compute_delta(arm, "evidence-matched", report, after, {})
    crosslingual = {cell["lane"]: cell["reason"] for cell in matched["must_cells_that_did_not_go_red"]}
    for lane in redstate.MUST_LANES_CROSSLINGUAL:
        assert crosslingual[lane] == "no-headroom", (
            f"{lane} must be reported as already at the floor under the evidence-matched predicate, "
            "not as an arm that failed to reach it"
        )


def test_thin_cells_print_a_count_and_no_rate(report):
    """SPEC §5.2.10 leaves the MUST-cell minima unruled; a rate on n=2 would invent one."""

    arm = redstate.ARMS_BY_NAME["global-shuffle-sim"]
    document = redstate.compute_delta(arm, "shipped", report, report, {})
    thin = document["must_cells"]["vi->fr"]
    assert thin["n"] < redstate.THIN_CELL
    assert thin["rate"] == "not-evaluated"
    assert "n=" in thin["why_no_rate"]


# --------------------------------------------------------------------------- the transforms


def _tiny_bundle() -> dict:
    return {
        "schema": redstate.REPLIES_SCHEMA,
        "run": {"recipe_sha256": "r", "export_sha256": "e", "extraction": {}},
        "replies": [
            {
                "id": "q-0001",
                "mode": "lexical",
                "results": [
                    {"rank": 1, "item_key": "AAAA1111", "attachment_key": None, "work_id": None,
                     "evidence": "one", "page": None, "chain": {}, "score": 1.0},
                    {"rank": 2, "item_key": "BBBB2222", "attachment_key": None, "work_id": None,
                     "evidence": "two", "page": None, "chain": {}, "score": 0.5},
                ],
            },
            {"id": "q-0002", "mode": "semantic", "results": None, "not_run_reason": "embeddings off"},
        ],
    }


@pytest.mark.parametrize("name", sorted(redstate.REPLY_TRANSFORMS))
def test_transform_is_deterministic_under_a_fixed_seed(name, export):
    transform = redstate.REPLY_TRANSFORMS[name]
    bundle = _tiny_bundle()
    assert transform(bundle, export, 0) == transform(bundle, export, 0)


@pytest.mark.parametrize("name", sorted(set(redstate.REPLY_TRANSFORMS) - {"identity"}))
def test_transform_is_not_the_identity(name, export, baseline_bundle):
    """A transform that changes nothing is the vacuity this whole ticket exists to catch."""

    transform = redstate.REPLY_TRANSFORMS[name]
    out = transform(baseline_bundle, export, 0)
    changed = sum(
        1
        for before, after in zip(baseline_bundle["replies"], out["replies"])
        if before.get("results") != after.get("results")
    )
    assert changed > 0, f"{name} left every reply untouched"


def test_identity_transform_really_is_the_identity(export, baseline_bundle):
    out = redstate.REPLY_TRANSFORMS["identity"](baseline_bundle, export, 0)
    assert out == baseline_bundle
    assert out is not baseline_bundle


def test_global_shuffle_draws_from_the_whole_export_not_the_top_k(export, baseline_bundle):
    """A permutation *within* the top k is invisible to the gate and would be a vacuous arm.

    `score_row` takes presence from set membership over `results[:k]`; rank feeds only the
    never-gated MRR. So the arm has to change the *set*, and this asserts it does.
    """

    out = redstate.transform_global_shuffle(baseline_bundle, export, 0)
    same_set = 0
    total = 0
    for before, after in zip(baseline_bundle["replies"], out["replies"]):
        if before.get("results") is None:
            continue
        total += 1
        if {r["item_key"] for r in before["results"]} == {r["item_key"] for r in after["results"]}:
            same_set += 1
    assert total > 0
    assert same_set < total // 10, f"{same_set}/{total} replies kept their item set — the shuffle is near-vacuous"


@pytest.mark.parametrize("name", sorted(redstate.REPLY_TRANSFORMS))
def test_transformed_bundle_still_loads_through_the_scorer(name, export, baseline_bundle):
    """Both kinds of arm go through the same unmodified scorer, so both must validate."""

    out = redstate.REPLY_TRANSFORMS[name](baseline_bundle, export, 0)
    arm = next(a for a in redstate.ARMS if a.transform == name)
    stamped = redstate.stamp_arm(out, arm, 0, {"transform": name, "simulation": True})
    loaded = load_replies(stamped)
    assert len(loaded["replies"]) == len(baseline_bundle["replies"])
    assert stamped["run"]["arm"]["name"] == arm.name


def test_a_malformed_transform_output_is_refused_by_the_scorer(export):
    """The control for the test above: load_replies would object if a bundle went wrong."""

    bundle = _tiny_bundle()
    bundle["replies"][0]["results"][1]["rank"] = 7  # ranks must run 1..n
    with pytest.raises(InputError):
        load_replies(bundle)


# --------------------------------------------------------------------------- arm E's target


def test_cap_crossing_target_is_computed_from_the_bank_and_is_mostly_expected_miss():
    """Arm E's declared target moves the wrong way, and the harness must say so in data.

    The ticket declares 'the cap-crossing questions'. Most of them are expected-miss, whose
    pass condition is 'no pinned row in the top k' — a smaller cap makes them *greener*. The
    honest target is the scored subset, and this holds the harness to computing it.
    """

    bank = {q["id"]: q for q in redstate.load_bank(REPO / "bench" / "fixtures" / "questions")}
    at_40k = redstate.cap_crossing_questions(bank, 40000)
    assert len(at_40k["expected_miss"]) > len(at_40k["scored"]), (
        "the cap-naming population is expected to be dominated by expected-miss questions"
    )
    at_2k = redstate.cap_crossing_questions(bank, 2000)
    assert len(at_2k["scored"]) > len(at_40k["scored"]), (
        "cutting the cap must enlarge the scored subset the arm can actually redden"
    )


def test_cap_crossing_target_is_monotone_in_the_cap():
    bank = {q["id"]: q for q in redstate.load_bank(REPO / "bench" / "fixtures" / "questions")}
    wide = set(redstate.cap_crossing_questions(bank, 40000)["scored"])
    narrow = set(redstate.cap_crossing_questions(bank, 2000)["scored"])
    assert wide <= narrow


# --------------------------------------------------------------------------- the CLI


def test_list_names_every_arm(capsys):
    assert redstate.main(["list"]) == 0
    out = capsys.readouterr().out
    for arm in redstate.ARMS:
        assert arm.name in out


def test_run_refuses_an_unknown_arm():
    assert redstate.main(["run", "--arm", "no-such-arm"]) == 2


def test_run_refuses_an_empty_arm_list():
    assert redstate.main(["run"]) == 2


def test_read_reports_not_run_on_an_empty_directory(tmp_path):
    assert redstate.main(["read", "--out", str(tmp_path)]) == 3
