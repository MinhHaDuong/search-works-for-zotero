"""The red-state harness's own guards (ticket 0722, item 1 of 0029's closeout order).

The exercise exists because a green golden run and a vacuous one are the same artifact.
That failure mode reproduces one level up: a differ that reports "nothing went red" when it
is itself broken is indistinguishable from a bank that cannot fail. So every test here is a
control rather than a coverage tick:

  * the two ruled scores of 2026-09-07 are pinned to numbers measured on the committed
    golden run. Without them, "no cell went red" and "my score code is wrong" print the same;
  * the official score reads zero everywhere, and a *positive control* injects a synthetic
    reply carrying a page inside the target's range and asserts the score counts it — a zero
    with no positive control is not a finding, it is a probe that may not be looking;
  * the identity transform's delta must be empty, which is the differ's negative control;
  * each real transform must be non-identity, which is the positive control for the arms —
    a transform that changes nothing is precisely the vacuity this ticket exists to catch.

What this file deliberately does NOT test is the ruled predicate itself. R34 lives in
`golden_gate.py` and is tested in `tests/test_golden_gate.py`; `bench/redstate.py` reads the
scores out of the gate's report and implements none. An earlier draft of this harness carried
its own copy, written before the gate had the ruling, and the two drifted 24 questions apart
on one bundle. `test_the_harness_implements_no_scoring_of_its_own` is the guard that keeps
the copy from coming back.

Fast tier: no build, no node, no network.
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
import golden_gate  # noqa: E402
from golden_gate import InputError, load_replies  # noqa: E402

BANK = REPO / "bench" / "fixtures" / "questions"
EXPORT = REPO / "bench" / "fixtures" / "export"
SPEC = REPO / "SPEC.md"
BASELINE_REPORT = REPO / "bench" / "results" / "golden" / "report.json"
BASELINE_REPLIES = REPO / "bench" / "results" / "golden" / "replies.json"

#: Measured on the committed golden run (export 579ab8dd…2296ccc) by `make golden`, and read
#: back out of the gate's own report — not recomputed here. The accommodating figure is 51 and
#: not the 75 an earlier draft of this harness printed: that draft scored a pageless
#: attachment by character span, which the gate refuses (22 questions), and located a snippet
#: by progressive prefix trimming, which finds a different span (2 questions).
HITS = 1928
HITS_CARRYING_A_PAGE = 0
SCORED = 195
PRIMARY_ROWS = 202
OFFICIAL_PRESENT = 0
ACCOMMODATING_PRESENT = 51

#: Rows the gate refused because the attachment carries no form feed. Fewer than the 99 rows
#: whose attachment is pageless, because a row whose work never came back within k, or whose
#: evidence is not located in the export, fails before the page question is reached.
ROWS_WITHOUT_PAGE_STRUCTURE = 67


@pytest.fixture(scope="module")
def bank() -> dict:
    return {question["id"]: question for question in redstate.load_bank(BANK)}


@pytest.fixture(scope="module")
def export():
    return redstate.load_export(EXPORT)


@pytest.fixture(scope="module")
def baseline_bundle() -> dict:
    return json.loads(BASELINE_REPLIES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ruled(report) -> dict:
    return redstate.ruled_scores(report)


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
    """A patch that no longer matches would make an arm a silent no-op rebuild.

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


# --------------------------------------------------------------------------- the ruled scores


def test_the_harness_implements_no_scoring_of_its_own():
    """The guard against the defect this rewrite fixed: a private copy of the ruled predicate.

    `bench/redstate.py` once carried its own R34 — a `RuledScore` class with its own page
    index, its own locate and its own intersection test — written in the window before
    `golden_gate.py` had the ruling. On the very same replies bundle the two read 24 questions
    differently, all 24 in the copy's favour. A red-state exercise scored by a private copy
    proves the copy can go red.

    So the harness must hold no page arithmetic. This is a source-level assertion because
    that is where the defect lives: a behavioural test would pass right up until the copy
    drifted, which is exactly what happened.
    """

    source = (REPO / "bench" / "redstate.py").read_text(encoding="utf-8")
    forbidden = {
        "\\f": "a form-feed literal means this file is finding page breaks itself",
        "page_of(": "a page index of its own",
        "page_range(": "a page range of its own",
        "_ranges_intersect": "an intersection test of its own",
        "class RuledScore": "the scorer that drifted",
        "class PageIndex": "the page index that drifted",
    }
    found = [why for needle, why in forbidden.items() if needle in source]
    assert not found, "bench/redstate.py has grown scoring again: " + "; ".join(found)


def test_the_reading_is_the_gates_own_numbers(report, ruled):
    """Every figure the harness reports must be the gate's, not a recomputation that agrees.

    Two implementations that happen to agree today are still two implementations. This ties
    the harness's headline numbers to the report fields they are lifted from, so a future
    edit that starts computing instead of reading fails here rather than in six months.
    """

    official = report["readings"]["r34"]["official"]
    accommodating = report["readings"]["r34"]["accommodating"]
    assert ruled["official_present"] == official["satisfied"]
    assert ruled["accommodating_present"] == accommodating["satisfied"]
    assert ruled["scored_questions"] == official["question_count"] == report["scored_count"]
    assert ruled["hits"] == official["page_reporting"]["hits"]
    assert ruled["hits_carrying_a_page"] == official["page_reporting"]["carrying_a_page"]
    for key, entry in ruled["questions"].items():
        block = report["questions"][key]["r34"]
        assert entry[redstate.OFFICIAL] == block["official"]["satisfied"]
        assert entry[redstate.ACCOMMODATING] == block["accommodating"]["satisfied"]


def test_no_hit_in_the_golden_run_carries_a_page(ruled):
    """The measurement the ruling rests on, held as a fixture rather than quoted.

    R34 as ruled needs the page the system reports. The schema has the field; the engine
    returns key, title, snippet and score. Ticket 0734 is the requirement gap.
    """

    assert ruled["hits"] == HITS
    assert ruled["hits_carrying_a_page"] == HITS_CARRYING_A_PAGE


def test_the_official_score_is_zero_and_says_why(ruled):
    assert ruled["scored_questions"] == SCORED
    assert ruled["primary_rows"] == PRIMARY_ROWS
    assert ruled["official_present"] == OFFICIAL_PRESENT
    reasons = ruled["official_rows_by_reason"]
    assert reasons.get("the reply reports no page"), (
        "the official zero must be attributed to the missing page, not left unexplained"
    )
    assert "satisfied" not in reasons, "no row can be satisfied while no hit carries a page"


def _plant_a_page(bundle, bank, export, page_of_target, limit=3):
    """Rewrite `limit` replies so each returns its own row's parent item, carrying a page.

    The target is the *printed folio* the bank pins on an alternate, because that is what
    R34's official reading compares a reported page against — not the form-feed index the
    accommodating reading derives. Planting the derived index instead is how a first draft of
    this control failed while the reading was correct.

    `page_of_target` picks the page out of that folio set, so the caller decides whether the
    planted page lands inside it or outside. Returns the doctored bundle and the keys touched.
    """

    doctored = copy.deepcopy(bundle)
    planted = []
    for reply in doctored["replies"]:
        question = bank.get(reply["id"])
        if not question or reply.get("results") is None or question["expected_miss"]:
            continue
        if not question["primary"]:
            continue
        row = question["primary"][0]
        target: set[str] = set()
        for alternate in row["alternates"]:
            target |= golden_gate.page_set(alternate["page_printed"])
        pages = sorted((int(page) for page in target if page.isdigit()))
        if not pages:
            continue
        reply["results"] = [{
            "rank": 1,
            "item_key": export.parent_of.get(row["attachment_key"]),
            "attachment_key": row["attachment_key"],
            "work_id": row["work_id"],
            "evidence": row["alternates"][0]["quote"],
            "page": str(page_of_target(pages)),
            "chain": {},
            "score": 1.0,
        }]
        planted.append(f'{reply["id"]}/{reply["mode"]}')
        if len(planted) >= limit:
            break
    return doctored, planted


def test_the_official_score_counts_a_reply_that_does_carry_the_page(bank, export, baseline_bundle):
    """The positive control. A zero whose probe cannot see anything is not a finding.

    Three replies are rewritten to carry the right work and a page inside the target's range,
    and the whole bundle goes back through `golden_gate.evaluate`. If the official score still
    reads zero, the reading is broken rather than the system, and every other number in this
    exercise would be worthless.
    """

    thresholds = golden_gate.load_thresholds(SPEC)
    questions = golden_gate.load_bank(BANK)
    doctored, planted = _plant_a_page(baseline_bundle, bank, export, lambda pages: pages[0])
    assert len(planted) == 3, "the control could not be planted; the fixture has moved"

    after = redstate.ruled_scores(
        golden_gate.evaluate(questions, load_replies(doctored), export, thresholds)
    )
    assert after["hits_carrying_a_page"] == len(planted)
    assert after["official_present"] == len(planted), (
        "the official score did not count a reply carrying the right work and an intersecting "
        "page — the reading is broken, not the system"
    )
    assert set(planted) <= redstate.present_set(after, redstate.OFFICIAL)


def test_the_official_score_refuses_a_page_far_outside_the_target(bank, export, baseline_bundle):
    """The discriminating half of the control above: it must be able to come out the other way."""

    thresholds = golden_gate.load_thresholds(SPEC)
    questions = golden_gate.load_bank(BANK)
    doctored, planted = _plant_a_page(baseline_bundle, bank, export, lambda pages: pages[-1] + 500)
    assert len(planted) == 3

    after = redstate.ruled_scores(
        golden_gate.evaluate(questions, load_replies(doctored), export, thresholds)
    )
    assert after["hits_carrying_a_page"] == len(planted), "the planted pages must still be reported"
    assert after["official_present"] == 0
    assert after["official_rows_by_reason"].get(
        "the reported page does not intersect the target's page range"
    ), "a page was reported and refused, and the reason must say which of the two happened"


def test_the_accommodating_score_reproduces_the_committed_reading(ruled):
    assert ruled["accommodating_present"] == ACCOMMODATING_PRESENT


def test_pageless_attachments_bound_the_accommodating_score(ruled, bank, export):
    """What the accommodating score cannot reach, counted rather than described.

    The ruled reading derives a page from the extraction's own form feeds, so a row in an
    attachment that carries none cannot be satisfied under it at all. That is not a defect in
    the arms and no arm can redden it; it is a standing ceiling, and one of the two readings
    left for the author (verification/RED-STATE-0722.md, question 2).

    Two counts, kept apart because they answer different questions: how many rows the gate
    actually refused for pagelessness, and how many rows sit in a pageless attachment at all.
    """

    assert ruled["rows_without_page_structure"] == ROWS_WITHOUT_PAGE_STRUCTURE
    assert ruled["accommodating_rows_by_reason"][redstate.NO_PAGE_STRUCTURE] == ROWS_WITHOUT_PAGE_STRUCTURE

    pageless_rows = sum(
        export.page_span(row["attachment_key"], 0, 1) is None
        for question in bank.values()
        if not question["expected_miss"]
        for row in question["primary"]
    )
    assert pageless_rows == 99
    assert pageless_rows > ruled["rows_without_page_structure"], (
        "a row can fail before the page question is reached, so the refusal count must be the "
        "smaller of the two; if they were equal the distinction would not be being made"
    )


def test_the_cross_lingual_must_cells_have_almost_no_headroom_under_either_score(ruled):
    """The measurement that shapes the whole reading.

    The official score floors every cell at zero, because no hit carries a page. The
    accommodating score leaves five of the six cross-lingual MUST cells at zero and vi->en
    holding one question. An arm cannot redden a cell that is already at the floor, and the
    differ has to say so rather than counting it as a failure to reach.
    """

    present = redstate.present_set(ruled, redstate.ACCOMMODATING)
    counts = {}
    for lane in redstate.MUST_LANES_CROSSLINGUAL:
        keys = {key for key, entry in ruled["questions"].items() if entry["lane"] == lane}
        assert keys, f"{lane} holds no scored question"
        counts[lane] = len(keys & present)
    assert sum(counts.values()) == 1, f"cross-lingual accommodating headroom moved: {counts}"
    assert counts["vi->en"] == 1
    assert not redstate.present_set(ruled, redstate.OFFICIAL)


def test_the_twin_reading_actually_fires_on_this_bank(report):
    """The judgement 'a twin is not the right work' is live, not hypothetical.

    `golden_gate.py` owns the rule and `tests/test_golden_gate.py` tests it. What belongs
    here is its *weight*: a judgement whose case never arises costs nothing to get wrong. On
    the committed run the twin path carries the best row of several questions, so the reading
    the author is asked to confirm is load-bearing.
    """

    carried = {
        key
        for key, entry in report["questions"].items()
        if entry["state"] == "scored"
        and any((row["evidence"] or {}).get("why") == "work-twin" for row in entry["rows"])
    }
    assert carried, "no question's row is carried by a twin; this reading would be untested weight"
    for key in carried:
        assert not report["questions"][key]["r34"]["official"]["satisfied"], (
            "a twin satisfied R34's official reading, which the ruling excludes"
        )


# --------------------------------------------------------------------------- the differ


def test_the_differ_reports_nothing_on_a_run_against_itself(ruled, report):
    """The negative control: a differ that cannot say 'nothing changed' cannot say anything."""

    arm = redstate.ARMS_BY_NAME["null-reply"]
    for predicate in redstate.PREDICATES:
        document = redstate.compute_delta(arm, predicate, ruled, ruled, report, report, {})
        assert document["changed"] == {}
        assert document["delta"] == 0
        assert document["mechanisms_fired"] == {}
        assert document["expected_miss_flips"] == {}


def test_the_differ_names_a_cell_that_stayed_green_and_says_why(ruled, report):
    """The positive control for `must_cells_that_did_not_go_red`, on a hand-built pair.

    One en->en question is flipped from present to absent; every other MUST cell is
    untouched, so the differ must report the untouched ones and must distinguish a cell with
    no headroom from one the arm simply did not reach. Those are different findings and the
    artifact must not fold them together.
    """

    arm = redstate.ARMS_BY_NAME["global-shuffle-sim"]
    after = copy.deepcopy(ruled)
    victim = next(
        key for key, entry in after["questions"].items()
        if entry["lane"] == "en->en" and entry[redstate.ACCOMMODATING]
    )
    after["questions"][victim][redstate.ACCOMMODATING] = False
    for row in after["questions"][victim]["rows"]:
        row["accommodating"] = {"satisfied": False, "path": "page", "why": "planted"}

    document = redstate.compute_delta(arm, redstate.ACCOMMODATING, ruled, after, report, report, {})
    assert document["changed"][victim]["to"] == "absent"
    assert document["must_cells"]["en->en"]["went_red"] is True
    stayed = {cell["lane"]: cell["reason"] for cell in document["must_cells_that_did_not_go_red"]}
    assert "en->en" not in stayed
    assert stayed, "every other MUST cell was untouched and none was reported"
    assert set(stayed.values()) <= {"not-reached", "no-headroom", "no-question"}
    for lane in ("en->fr", "en->vi", "fr->en", "fr->vi", "vi->fr"):
        assert stayed[lane] == "no-headroom", (
            f"{lane} reads zero present at baseline and must be reported as already at the floor, "
            "not as an arm that failed to reach it"
        )
    assert stayed["fr->fr"] == "not-reached"


def test_the_differ_labels_the_accommodating_score_as_not_official(ruled, report):
    arm = redstate.ARMS_BY_NAME["global-shuffle-sim"]
    official = redstate.compute_delta(arm, redstate.OFFICIAL, ruled, ruled, report, report, {})
    accommodating = redstate.compute_delta(arm, redstate.ACCOMMODATING, ruled, ruled, report, report, {})
    assert official["official"] is True
    assert accommodating["official"] is False
    assert "NOT OFFICIAL" in accommodating["label"]


def test_thin_cells_print_a_count_and_no_rate(ruled, report):
    """SPEC §5.2.10 leaves the MUST-cell minima unruled; a rate on n=2 would invent one."""

    arm = redstate.ARMS_BY_NAME["global-shuffle-sim"]
    document = redstate.compute_delta(arm, redstate.ACCOMMODATING, ruled, ruled, report, report, {})
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

    Presence is set membership over `results[:k]`; rank feeds only the never-gated MRR. So the
    arm has to change the *set*, and this asserts it does.
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


def test_cap_crossing_target_is_computed_from_the_bank_and_is_mostly_expected_miss(bank):
    """Arm E's declared target moves the wrong way, and the harness must say so in data.

    The ticket declares 'the cap-crossing questions'. Most of them are expected-miss, whose
    pass condition is 'no pinned row in the top k' — a smaller cap makes them *greener*. The
    honest target is the scored subset, and this holds the harness to computing it.
    """

    at_40k = redstate.cap_crossing_questions(bank, 40000)
    assert len(at_40k["expected_miss"]) > len(at_40k["scored"]), (
        "the cap-naming population is expected to be dominated by expected-miss questions"
    )
    at_2k = redstate.cap_crossing_questions(bank, 2000)
    assert len(at_2k["scored"]) > len(at_40k["scored"]), (
        "cutting the cap must enlarge the scored subset the arm can actually redden"
    )


def test_cap_crossing_target_is_monotone_in_the_cap(bank):
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
