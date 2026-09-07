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
from golden_gate import InputError, load_replies  # noqa: E402

BANK = REPO / "bench" / "fixtures" / "questions"
EXPORT = REPO / "bench" / "fixtures" / "export"
BASELINE_REPORT = REPO / "bench" / "results" / "golden" / "report.json"
BASELINE_REPLIES = REPO / "bench" / "results" / "golden" / "replies.json"

#: Measured on the committed golden run (build b0e0bc8, export 579ab8dd…2296ccc), which is
#: also what the ruling of 2026-09-07 was measured against before it was written into SPEC.
HITS = 1928
HITS_CARRYING_A_PAGE = 0
SCORED = 195
OFFICIAL_PRESENT = 0
ACCOMMODATING_PRESENT = 75

#: The two predicates the ruling superseded, kept so the reading can say what moved.
SUPERSEDED_SHIPPED = 161
SUPERSEDED_EVIDENCE_MATCHED = 42


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
def ruled(baseline_bundle, bank, export) -> dict:
    return redstate.score_bundle_ruled(baseline_bundle, bank, export, 10)


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


def test_no_hit_in_the_golden_run_carries_a_page(ruled):
    """The measurement the ruling rests on, held as a fixture rather than quoted.

    R34 as ruled needs the page the system reports. The schema has the field; the engine
    returns key, title, snippet and score. Ticket 0734 is the requirement gap.
    """

    assert ruled["hits"] == HITS
    assert ruled["hits_carrying_a_page"] == HITS_CARRYING_A_PAGE


def test_the_official_score_is_zero_and_says_why(ruled):
    assert ruled["scored_questions"] == SCORED
    assert ruled["official_present"] == OFFICIAL_PRESENT
    reasons = ruled["official_rows_by_reason"]
    assert reasons.get("no-reported-page"), "the official zero must be attributed to the missing page"
    assert "reported-page-outside-target" not in reasons, (
        "a row refused for a page outside the target would mean some page WAS reported"
    )


def test_the_official_score_counts_a_reply_that_does_carry_the_page(bank, export, baseline_bundle):
    """The positive control. A zero whose probe cannot see anything is not a finding.

    One reply is rewritten to carry the right work and a page inside the target's derived
    range. If the official score still reads zero, the score is broken rather than the
    system, and every other assertion here would be worthless.
    """

    scorer = redstate.RuledScore(export, bank, 10)
    doctored = copy.deepcopy(baseline_bundle)
    planted = 0
    for reply in doctored["replies"]:
        question = bank.get(reply["id"])
        if not question or reply.get("results") is None or question["expected_miss"] or not question["pinned"]:
            continue
        row = question["pinned"][0]
        target = scorer.target_ranges(row, question)
        if not target["derived"]:
            continue
        parent = export.parent_of.get(row["attachment_key"])
        low = target["derived"][0][0]
        reply["results"] = [{
            "rank": 1, "item_key": parent, "attachment_key": row["attachment_key"],
            "work_id": row["work_id"], "evidence": None, "page": str(low),
            "chain": {}, "score": 1.0,
        }]
        planted += 1
        if planted >= 3:
            break

    assert planted == 3, "the control could not be planted; the fixture has moved"
    after = redstate.score_bundle_ruled(doctored, bank, export, 10)
    assert after["hits_carrying_a_page"] == planted
    assert after["official_present"] == planted, (
        "the official score did not count a reply that carries the right work and an "
        "intersecting page — the score is broken, not the system"
    )


def test_the_official_score_refuses_a_page_outside_the_target(bank, export, baseline_bundle):
    """The discriminating half of the control above: it must be able to come out the other way."""

    scorer = redstate.RuledScore(export, bank, 10)
    doctored = copy.deepcopy(baseline_bundle)
    planted = 0
    for reply in doctored["replies"]:
        question = bank.get(reply["id"])
        if not question or reply.get("results") is None or question["expected_miss"] or not question["pinned"]:
            continue
        row = question["pinned"][0]
        target = scorer.target_ranges(row, question)
        if not target["derived"]:
            continue
        reply["results"] = [{
            "rank": 1, "item_key": export.parent_of.get(row["attachment_key"]),
            "attachment_key": row["attachment_key"], "work_id": row["work_id"], "evidence": None,
            "page": str(target["derived"][0][1] + 500), "chain": {}, "score": 1.0,
        }]
        planted += 1
        if planted >= 3:
            break
    after = redstate.score_bundle_ruled(doctored, bank, export, 10)
    assert after["hits_carrying_a_page"] == planted
    assert after["official_present"] == 0


def test_the_accommodating_score_reproduces_the_committed_reading(ruled):
    assert ruled["accommodating_present"] == ACCOMMODATING_PRESENT


def test_the_accommodating_score_uses_both_intersection_paths(ruled):
    """Pages where the export has them, character spans where §5.2.10 says it must.

    Both paths must actually carry rows, or the reading would be quoting a mechanism that
    never fires.
    """

    paths = ruled["rows_by_intersection_path"]
    assert paths.get("page"), "no row went through the page-intersection path"
    assert paths.get("char"), "no row went through the character-span path"


def test_the_cross_lingual_must_cells_have_almost_no_headroom_under_either_score(ruled):
    """The measurement that shapes the whole reading, recomputed under the ruling.

    The predecessor's table was computed under the superseded evidence-matched predicate.
    Under the ruled scores the picture is the same in kind and worse in degree: the official
    score floors every cell at zero, and the accommodating score leaves five of the six
    cross-lingual MUST cells at zero with vi->en holding one question.
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


def test_the_superseded_predicates_are_still_readable_for_the_record(report):
    """Reported so the artifact can say what the ruling moved; never gated on."""

    assert len(redstate.superseded_present_set(report, "shipped")) == SUPERSEDED_SHIPPED
    assert len(redstate.superseded_present_set(report, "evidence-matched")) == SUPERSEDED_EVIDENCE_MATCHED


def test_a_translation_twin_is_not_the_right_work(bank, export):
    """SPEC §5.2.10 asserts the other-language rendering distinct; R34's reading follows it.

    The superseded shipped predicate let the twin path count as present. The ruled scores
    must not, or a cross-lingual question would pass on exactly the miss R29 exists to catch.
    """

    scorer = redstate.RuledScore(export, bank, 10)
    twinned = [(work, twins) for work, twins in export.twin_works.items() if twins]
    assert twinned, "the export declares no twin works; this control cannot fire"
    work, twins = twinned[0]
    other = sorted(twins)[0]
    twin_items = sorted(export.items_of_work.get(other, set()))
    assert twin_items, "the twin work holds no item"
    attachment = next(key for key, parent in export.parent_of.items()
                      if export.work_of_item.get(parent) == work)
    row = {"attachment_key": attachment, "work_id": work}
    assert not scorer.right_work(
        {"item_key": twin_items[0], "attachment_key": None}, row
    ), "a twin item counted as the right work"
    assert scorer.right_work(
        {"item_key": export.parent_of[attachment], "attachment_key": None}, row
    ), "the answer's own item did not count as the right work"


def test_page_ranges_intersect_rather_than_match():
    """Intersection, not equality — the ruling's own words, and the reason for them."""

    assert redstate._ranges_intersect((3, 4), (4, 5))
    assert redstate._ranges_intersect((3, 3), (3, 3))
    assert not redstate._ranges_intersect((3, 4), (5, 6))
    assert not redstate._ranges_intersect(None, (5, 6))


def test_a_page_index_reads_the_extractions_own_breaks(export):
    """Form feeds are the page structure; an attachment without them has none."""

    pages = redstate.PageIndex(export)
    with_pages = [key for key in sorted(export.attachments) if pages.has_pages(key)]
    without = [key for key in sorted(export.attachments) if not pages.has_pages(key)]
    assert with_pages and without, "the export must exercise both branches or the split is untested"
    key = with_pages[0]
    breaks = pages.breaks(key)
    assert pages.page_of(key, 0) == 1
    assert pages.page_of(key, breaks[0] + 1) == 2
    assert pages.page_of(key, breaks[-1] + 1) == len(breaks) + 1


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
