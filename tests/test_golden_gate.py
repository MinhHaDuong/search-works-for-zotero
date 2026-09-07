"""The golden gate at bank schema v2 (ticket 0722).

These tests drive the scorer against a small invented export written to a tmp dir — two
works, one of them with a declared translation twin — and against the committed export for
the reachability positive and negative controls. They copy no threshold out of SPEC.md.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "SPEC.md"
DRIVER = REPO / "bench" / "golden_gate.py"
COMMITTED_EXPORT = REPO / "bench" / "fixtures" / "export"
COMMITTED_BANK = REPO / "bench" / "fixtures" / "questions"
COMMITTED_REPLIES = REPO / "bench" / "results" / "golden" / "replies.json"

sys.path.insert(0, str(REPO / "bench"))

from golden_gate import (  # noqa: E402
    BANK_SCHEMA,
    CHAIN_FIELDS,
    FACETS,
    FAIL,
    GENERATORS,
    LANGUAGES,
    MODES,
    NOT_MEASURED,
    NOT_RUN,
    PASS,
    REPLIES_SCHEMA,
    SET_KINDS,
    SIGNALS,
    STRATA,
    InputError,
    bank_shape,
    check_reachability_policy,
    compute_reachability,
    evaluate,
    load_bank,
    load_export,
    load_replies,
    load_thresholds,
    locate_quote,
    render_report,
    validate_bank,
    validate_question,
)

ALPHA_TEXT = (
    "Article 1. Scope\nThe quick brown fox jumps over the lazy dog near the riverbank.\n"
    "Article 2. Tariff\nThe buyer purchases every kilowatt-hour at 2,086 dong, equivalent "
    "to 9.35 cents.\n\x0cArticle 3. Effect\nThis decision takes effect on the first of June "
    "and expires two years later.\n"
)
ALPHA_FR_TEXT = "Article 2. Tarif\nL’acheteur achète chaque kilowattheure à 2 086 dongs.\n"
BETA_TEXT = "Chapter one. Wealth is the set of scarce things, useful and limited in quantity.\n"
CAP = 200
ALPHA_QUOTE_ART2 = "The buyer purchases every kilowatt-hour at 2,086 dong, equivalent to 9.35 cents."
ALPHA_QUOTE_ART3 = "This decision takes effect on the first of June and expires two years later."
BETA_QUOTE = "Wealth is the set of scarce things, useful and limited in quantity."


def make_export(root: Path) -> Path:
    """An invented export: work alpha (pdf) with translation twin alpha-fr (html), and work beta."""

    export = root / "export"
    (export / "fulltext").mkdir(parents=True)

    def parent(key, work, title, extra_relations="[]", language="en"):
        return {"key": key, "version": 1, "data": {
            "key": key, "itemType": "document", "title": title, "date": "1901", "language": language,
            "url": f"https://example.org/{work}", "creators": [{"creatorType": "author", "name": f"Author of {work}"}],
            "extra": f"ticket-0029 recipe id: {work}\nticket-0029 work id: {work}\n"
                     f"ticket-0029 type fidelity: unreviewed\nticket-0029 work relations: {extra_relations}",
        }}

    def attachment(key, parent_key, content_type):
        return {"key": key, "version": 2, "data": {
            "key": key, "itemType": "attachment", "parentItem": parent_key, "contentType": content_type,
            "title": "attachment", "filename": f"{key}.bin",
        }}

    items = [
        parent("P1ALPHA1", "alpha", "Alpha, a decision"),
        attachment("A1ALPHA1", "P1ALPHA1", "application/pdf"),
        parent("P2ALPHA2", "alpha-fr", "Alpha, décision (traduction)", '[{"type": "translation", "work_id": "alpha"}]', "fr"),
        attachment("A2ALPHA2", "P2ALPHA2", "text/html"),
        parent("P3BETA33", "beta", "Beta, a treatise"),
        attachment("A3BETA33", "P3BETA33", "text/plain"),
        parent("P4CTRL44", "gamma", "Gamma, a scan"),
        attachment("A4CTRL44", "P4CTRL44", "application/pdf"),
    ]
    (export / "items.json").write_text(json.dumps(items), encoding="utf-8")
    for key, text in (("A1ALPHA1", ALPHA_TEXT), ("A2ALPHA2", ALPHA_FR_TEXT), ("A3BETA33", BETA_TEXT)):
        (export / "fulltext" / f"{key}.json").write_text(
            json.dumps({"content": text, "indexedPages": 1, "totalPages": 1}), encoding="utf-8"
        )

    def row(key, parent_key, recipe, state="indexed", control=None):
        out = {"attachment_key": key, "parent_key": parent_key, "recipe_id": recipe, "terminal_state": state,
               "fulltext_file": f"fulltext/{key}.json" if state == "indexed" else None}
        if control:
            out["failure_control"] = control
        return out

    manifest = {
        "schema_version": 1,
        "recipe_sha256": "c" * 64,
        "library": {"type": "group", "id": 1, "collection_key": "COLL0001"},
        "zotero": {"client_version": "test", "fulltext.pdfMaxPages": 100, "fulltext.textMaxLength": 500000},
        "reindex": {"mode": "complete", "limits": "ignored"},
        "index_fulltext_max_chars": CAP,
        "items_file": "items.json",
        "attachments": [
            row("A1ALPHA1", "P1ALPHA1", "alpha"),
            row("A2ALPHA2", "P2ALPHA2", "alpha-fr"),
            row("A3BETA33", "P3BETA33", "beta"),
            row("A4CTRL44", "P4CTRL44", "gamma", "unindexed",
                {"expected_state": "unindexed", "expected_degradation": "no text layer", "answer_set_participation": "none"}),
        ],
    }
    (export / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return export


def export_sha(export: Path) -> str:
    return hashlib.sha256((export / "manifest.json").read_bytes()).hexdigest()


def chain(**overrides):
    base = {name: None for name in CHAIN_FIELDS}
    base.update({"title": "Alpha, a decision", "author": "Author of alpha", "date": "1901",
                 "identifier": "https://example.org/alpha"})
    base.update(overrides)
    return base


def alpha_row(section, quote, page=None, **chain_overrides):
    return {"work_id": "alpha", "recipe_id": "alpha", "attachment_id": None, "attachment_key": "A1ALPHA1",
            "section": section, "alternates": [{"page_printed": page, "char_offset": None, "quote": quote}],
            "chain": chain(section_heading=f"Article {section[-1]}.", page_printed=page, **chain_overrides)}


def beta_row(quote=BETA_QUOTE):
    return {"work_id": "beta", "recipe_id": "beta", "attachment_id": None, "attachment_key": "A3BETA33",
            "section": "Chapter one", "alternates": [{"page_printed": "3", "char_offset": None, "quote": quote}],
            "chain": chain(title="Beta, a treatise", author="Author of beta", identifier="https://example.org/beta",
                           section_heading="Chapter one", page_printed="3")}


def question(qid, primary, *, set_kind="any-of", ql="en", al="en", expected_miss=False, mechanism=None,
             mode="any", stratum="core", signal="exact", **extra):
    record = {
        "schema": BANK_SCHEMA, "id": qid, "need": "a need", "query": f"query for {qid}",
        "question_language": ql, "answer_language": al, "lane": f"{ql}->{al}", "signal": signal, "mode": mode,
        "facet": "core", "stratum": stratum, "mechanism": [], "generator": "need", "set_kind": set_kind,
        "primary": primary, "expected_miss": expected_miss, "expected_miss_mechanism": mechanism,
        "reachability": None, "provenance": {"author": "test", "date": "2026-09-06", "page_read": True},
    }
    record.update(extra)
    return record


def write_bank(root: Path, *questions) -> Path:
    bank = root / "questions"
    bank.mkdir(exist_ok=True)
    for record in questions:
        (bank / f"{record['id']}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return bank


def result(rank, item_key, evidence=None, *, work_id=None, page=None, title=None, chain_fields=None):
    carried = {name: None for name in CHAIN_FIELDS}
    carried.update({"title": title or "Alpha, a decision", "author": "Author of alpha", "date": "1901",
                    "identifier": "https://example.org/alpha"})
    if chain_fields:
        carried.update(chain_fields)
    return {"rank": rank, "item_key": item_key, "attachment_key": None, "work_id": work_id, "evidence": evidence,
            "page": page, "chain": carried, "score": 1.0 / rank}


def bundle(export: Path, replies, previous=None):
    run = {"recipe_sha256": "c" * 64, "export_sha256": export_sha(export), "extraction": {}, "embedder": "off",
           "chunker": "test", "index_schema": "2", "retrieval_mode": "keyword", "build_sha": "deadbeef"}
    out = {"schema": REPLIES_SCHEMA, "run": run, "replies": replies}
    if previous is not None:
        out["previous_run"] = {"run": dict(run), "replies": previous}
    return out


def reply(qid, results, mode="lexical"):
    return {"id": qid, "mode": mode, "results": results}


@pytest.fixture(scope="module")
def thresholds():
    return load_thresholds(SPEC)


@pytest.fixture
def export(tmp_path):
    return make_export(tmp_path)


def test_thresholds_are_read_from_the_owning_spec_section(thresholds):
    assert thresholds.source == "SPEC.md §5.2.8"
    assert thresholds.k > 0
    assert 0 < thresholds.hard_floor <= thresholds.below_cutoff <= thresholds.mean_min <= 1
    assert 0 <= thresholds.below_max_fraction <= 1


# ------------------------------------------------------------------ refusals


def test_a_v1_bundle_is_refused_by_name():
    with pytest.raises(InputError, match="golden-gate-input/v1"):
        load_replies({"schema": "golden-gate-input/v1", "queries": []})
    with pytest.raises(InputError, match="menagerie-replies/v2"):
        load_replies({"schema": "something-else", "replies": []})


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda q: q["primary"][0]["alternates"][0].pop("quote"), "quote"),
        (lambda q: q["primary"][0].update({"extra_field": 1}), "unknown fields"),
        (lambda q: q["primary"].append(dict(q["primary"][0])), "repeats"),
        (lambda q: q.update({"lane": "fr->en"}), "lane"),
        (lambda q: q.update({"expected_miss": True}), "expected_miss_mechanism"),
        (lambda q: q.update({"primary": []}), "empty primary set"),
        (lambda q: q.update({"signal": "vibes"}), "signal"),
        (lambda q: q.update({"set_kind": "some-of"}), "set_kind"),
        (lambda q: q["primary"][0]["chain"].update({"publisher": "x"}), "chain fields"),
        (lambda q: q.update({"schema": "menagerie-bank/v1"}), "schema"),
    ],
)
def test_a_malformed_row_or_record_is_refused(mutate, message):
    record = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    mutate(record)
    with pytest.raises(InputError, match=message):
        validate_question(record)


def test_the_bank_directory_is_flat_and_ids_match_file_names(tmp_path):
    bank = write_bank(tmp_path, question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)]))
    (bank / "q-0002.json").write_text(json.dumps(question("q-0009", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])))
    with pytest.raises(InputError, match="does not match its file name"):
        load_bank(bank)


def test_a_reply_without_results_must_say_why_and_ranks_must_be_ordered(export):
    with pytest.raises(InputError, match="not_run_reason"):
        load_replies(bundle(export, [{"id": "q-0001", "mode": "semantic", "results": None}]))
    with pytest.raises(InputError, match="ranks"):
        load_replies(bundle(export, [reply("q-0001", [result(2, "P1ALPHA1")])]))


# ------------------------------------------------------------------ the ladder


def test_any_of_scores_the_best_row_and_all_of_the_weakest(export, thresholds):
    rows = [alpha_row("Article 2", ALPHA_QUOTE_ART2), alpha_row("Article 3", ALPHA_QUOTE_ART3)]
    any_of = question("q-0001", rows)
    all_of = question("q-0002", rows, set_kind="all-of")
    hit = result(1, "P1ALPHA1", evidence="... purchases every kilowatt-hour at 2,086 dong, equivalent to 9.35 cents. Article 3 ...")
    report = evaluate(
        [any_of, all_of], load_replies(bundle(export, [reply("q-0001", [hit]), reply("q-0002", [hit])])),
        load_export(export), thresholds,
    )
    q1 = report["questions"]["q-0001/lexical"]
    q2 = report["questions"]["q-0002/lexical"]
    assert q1["level"] == "win" and q1["rank"] == 1
    assert q2["level"] == "near-win" and q2["rank"] == 1
    assert q2["rows_found"] == {"count": 2, "of": 2, "fraction": 1.0}
    assert [row["level"] for row in q2["rows"]] == ["win", "near-win"]
    assert report["readings"]["r34"]["state"] == PASS


def test_all_of_misses_and_fails_r34_when_one_row_is_absent(export, thresholds):
    rows = [alpha_row("Article 2", ALPHA_QUOTE_ART2), beta_row()]
    all_of = question("q-0001", rows, set_kind="all-of")
    any_of = question("q-0002", rows, set_kind="any-of")
    hit = result(1, "P1ALPHA1", evidence="purchases every kilowatt-hour at 2,086 dong, equivalent to 9.35 cents.")
    report = evaluate(
        [all_of, any_of], load_replies(bundle(export, [reply("q-0001", [hit]), reply("q-0002", [hit])])),
        load_export(export), thresholds,
    )
    assert report["questions"]["q-0001/lexical"]["level"] == "miss"
    assert report["questions"]["q-0001/lexical"]["rows_found"]["count"] == 1
    assert report["questions"]["q-0002/lexical"]["level"] == "win"
    assert report["readings"]["r34"]["state"] == FAIL
    assert report["readings"]["r34"]["missing"] == {"q-0001/lexical": ["beta#Chapter one"]}
    assert report["state"] == FAIL


def test_the_translation_twin_is_a_near_win_and_counts_as_present(export, thresholds):
    q = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    twin_hit = result(2, "P2ALPHA2", evidence="L’acheteur achète chaque kilowattheure", work_id="alpha-fr",
                      title="Alpha, décision (traduction)")
    other = result(1, "P3BETA33", evidence="Wealth is the set of scarce things", work_id="beta")
    report = evaluate([q], load_replies(bundle(export, [reply("q-0001", [other, twin_hit])])),
                      load_export(export), thresholds)
    entry = report["questions"]["q-0001/lexical"]
    assert entry["level"] == "near-win" and entry["rank"] == 2
    assert entry["rows"][0]["evidence"]["why"] == "work-twin"
    assert report["readings"]["r34"]["state"] == PASS


def test_a_printed_page_match_wins_without_evidence_overlap(export, thresholds):
    q = question("q-0001", [beta_row()])
    hit = result(1, "P3BETA33", evidence="nothing overlapping", page="3", work_id="beta",
                 title="Beta, a treatise", chain_fields={"page_printed": "3", "author": "Author of beta",
                                                          "identifier": "https://example.org/beta"})
    report = evaluate([q], load_replies(bundle(export, [reply("q-0001", [hit])])), load_export(export), thresholds)
    entry = report["questions"]["q-0001/lexical"]
    assert entry["level"] == "win"
    assert entry["rows"][0]["evidence"]["how"] == "printed-page"
    assert entry["chain"] == {"matched": 5, "of": 6, "fraction": 5 / 6, "missing": ["section_heading"], "mismatched": []}


def test_chain_completeness_counts_only_primary_fields_and_is_not_run_on_a_miss(export, thresholds):
    q = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    hit = result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2, chain_fields={"date": "1999"})
    report = evaluate([q], load_replies(bundle(export, [reply("q-0001", [hit])])), load_export(export), thresholds)
    entry = report["questions"]["q-0001/lexical"]
    assert entry["chain"]["of"] == 5
    assert entry["chain"]["mismatched"] == ["date"]
    assert entry["chain"]["missing"] == ["section_heading"]
    missed = evaluate([q], load_replies(bundle(export, [reply("q-0001", [])])), load_export(export), thresholds)
    assert missed["questions"]["q-0001/lexical"]["level"] == "miss"
    assert missed["questions"]["q-0001/lexical"]["chain"] == NOT_RUN


# ------------------------------------------------------------------ expected-miss


def test_a_no_answer_question_has_an_empty_primary_set_and_is_reported_apart(export, thresholds):
    none = question("q-0001", [], expected_miss=True, mechanism="no-answer in the corpus")
    real = question("q-0002", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    hit = result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2)
    report = evaluate([none, real], load_replies(bundle(export, [reply("q-0001", [hit]), reply("q-0002", [hit])])),
                      load_export(export), thresholds)
    assert report["expected_miss"] == {
        "count": 1, "pass": 1, "unexpected_hit": 0, "by_mechanism": {"no-answer in the corpus": 1},
        "per_question": {"q-0001/lexical": PASS},
    }
    assert report["scored_count"] == 1
    assert report["ladder"]["by_stratum"]["core"]["all"]["count"] == 1
    assert report["readings"]["r34"]["question_count"] == 1


def test_an_expected_miss_with_primary_rows_reports_an_unexpected_hit(export, thresholds):
    unreachable = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)], expected_miss=True,
                           mechanism="past the index cap")
    report = evaluate([unreachable], load_replies(bundle(export, [reply("q-0001", [result(1, "P1ALPHA1")])])),
                      load_export(export), thresholds)
    assert report["expected_miss"]["unexpected_hit"] == 1
    assert report["state"] == NOT_RUN  # nothing scored, nothing gated: not a pass


# ------------------------------------------------------------------ counts and not-measured


def test_every_rate_prints_its_count_and_empty_groups_print_not_measured(export, thresholds):
    q = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)], ql="fr", al="en")
    hit = result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2)
    report = evaluate([q], load_replies(bundle(export, [reply("q-0001", [hit])])), load_export(export), thresholds)
    text = render_report(report)
    assert "lane fr->en: n=1 win 1/1 (100 %)" in text
    assert "stratum reserve:" in text and "  all: n=0 not-measured" in text
    assert "format html: n=0 not-measured" in text
    assert "mode semantic: n=0 not-measured" in text
    core = report["ladder"]["by_stratum"]["core"]
    assert core["by_format"]["pdf"]["count"] == 1 and core["by_format"]["pdf"]["win_rate"] == 1.0
    assert core["by_format"]["html"] == {"count": 0, "state": NOT_MEASURED}
    assert report["ladder"]["by_stratum"]["reserve"]["all"] == {"count": 0, "state": NOT_MEASURED}
    assert report["ladder"]["all_strata_macro_by_lane"]["lanes"] == 1
    assert report["ladder"]["all_strata_weighted"]["count"] == 1


def test_strata_are_printed_apart_and_a_macro_average_sits_beside_the_pooled_figure(export, thresholds):
    core = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    reserve = question("q-0002", [alpha_row("Article 3", ALPHA_QUOTE_ART3)], stratum="reserve", ql="fr")
    hit = result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2)
    report = evaluate([core, reserve], load_replies(bundle(export, [reply("q-0001", [hit]), reply("q-0002", [hit])])),
                      load_export(export), thresholds)
    assert report["ladder"]["by_stratum"]["core"]["all"]["win"] == 1
    assert report["ladder"]["by_stratum"]["reserve"]["all"]["near_win"] == 1
    assert report["ladder"]["all_strata_weighted"]["win_rate"] == 0.5
    assert report["ladder"]["all_strata_macro_by_lane"] == {
        "lanes": 2, "win_rate": 0.5, "near_or_better_rate": 1.0, "mrr": 1.0,
    }


def test_modes_the_build_could_not_run_are_not_run_never_a_miss(export, thresholds):
    q = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    replies = [
        reply("q-0001", [result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2)]),
        {"id": "q-0001", "mode": "semantic", "results": None, "not_run_reason": "no vectors"},
    ]
    report = evaluate([q], load_replies(bundle(export, replies)), load_export(export), thresholds)
    assert report["not_run_count"] == 1
    assert report["questions"]["q-0001/semantic"]["state"] == NOT_RUN
    assert report["ladder"]["by_stratum"]["core"]["by_mode"]["semantic"]["reason"] == "no vectors"
    assert report["readings"]["r34"]["question_count"] == 1
    with pytest.raises(InputError, match="scoped to mode"):
        evaluate([question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)], mode="lexical")],
                 load_replies(bundle(export, [reply("q-0001", [], mode="hybrid")])), load_export(export), thresholds)


# ------------------------------------------------------------------ stability


def test_stability_reads_the_previous_run_and_is_not_run_without_one(export, thresholds):
    q = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    now = [reply("q-0001", [result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2), result(2, "P3BETA33")])]
    alone = evaluate([q], load_replies(bundle(export, now)), load_export(export), thresholds)
    assert alone["readings"]["stability"]["state"] == NOT_RUN
    assert alone["state"] == NOT_RUN
    same = evaluate([q], load_replies(bundle(export, now, previous=now)), load_export(export), thresholds)
    assert same["readings"]["stability"]["state"] == PASS
    assert same["readings"]["stability"]["per_query"] == {"q-0001/lexical": 1.0}
    assert same["state"] == PASS
    moved = [reply("q-0001", [result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2), result(2, "P2ALPHA2")])]
    drift = evaluate([q], load_replies(bundle(export, now, previous=[reply("q-0001", [result(1, "P2ALPHA2")])])),
                     load_export(export), thresholds)
    assert drift["readings"]["stability"]["per_query"]["q-0001/lexical"] == 0.0
    assert drift["readings"]["stability"]["state"] == FAIL
    assert drift["state"] == FAIL
    assert moved  # the perturbation used above; kept explicit for the reader


def test_replies_from_another_export_are_refused(export, thresholds):
    q = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    payload = bundle(export, [reply("q-0001", [result(1, "P1ALPHA1")])])
    payload["run"]["export_sha256"] = "d" * 64
    with pytest.raises(InputError, match="produced against export"):
        evaluate([q], load_replies(payload), load_export(export), thresholds)


# ------------------------------------------------------------------ reachability


def test_locate_quote_normalises_whitespace_and_apostrophes_and_resolves_the_raw_offset():
    content = "Head\n\n\x0cThe   buyer’s\nduty is clear.\n"
    located = locate_quote("The buyer's duty is clear.", content)
    assert located["reachable"] and located["occurrences"] == 1
    assert content[located["char_offset"]:].startswith("The   buyer")
    assert locate_quote("not in the text", content)["reachable"] is False
    twice = locate_quote("clear", content + " clear")
    assert twice["occurrences"] == 2 and twice["char_offset"] == content.index("clear")


def test_reachability_is_stamped_then_compared_and_a_missing_quote_is_refused(tmp_path, export):
    good = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    bank = write_bank(tmp_path, good)
    summary = validate_bank(bank, load_export(export), stamp=True)
    assert summary == {"questions": 1, "stamped": 1, "alternates": 1, "reachable_alternates": 1, "past_index_cap": 0}
    stamped = json.loads((bank / "q-0001.json").read_text())
    block = stamped["reachability"]
    assert block["reachable"] is True
    assert block["extraction"]["index_fulltext_max_chars"] == CAP
    assert block["extraction"]["recipe_sha256"] == "c" * 64
    assert block["export_sha256"] == export_sha(export)
    offset = stamped["primary"][0]["alternates"][0]["char_offset"]
    assert ALPHA_TEXT[offset:].startswith("The buyer purchases")
    assert validate_bank(bank, load_export(export), stamp=False)["stamped"] == 0

    bad = question("q-0002", [alpha_row("Article 2", "This sentence is nowhere in the export.")])
    write_bank(tmp_path, bad)
    with pytest.raises(InputError, match="unreachable alternate"):
        validate_bank(bank, load_export(export), stamp=False)
    (bank / "q-0002.json").unlink()

    stamped["reachability"]["rows"][0]["alternates"][0]["char_offset"] += 1
    (bank / "q-0001.json").write_text(json.dumps(stamped))
    with pytest.raises(InputError, match="stale"):
        validate_bank(bank, load_export(export), stamp=False)


def test_an_unreachable_answer_is_allowed_only_as_expected_miss_with_a_mechanism(export):
    loaded = load_export(export)
    flagged = question("q-0001", [alpha_row("Article 2", "This sentence is nowhere in the export.")],
                       expected_miss=True, mechanism="OCR mangled the span")
    block = compute_reachability(flagged, loaded)
    assert block["reachable"] is False
    check_reachability_policy(flagged, block)  # no raise
    unflagged = question("q-0002", [alpha_row("Article 2", "This sentence is nowhere in the export.")])
    with pytest.raises(InputError, match="unreachable"):
        check_reachability_policy(unflagged, compute_reachability(unflagged, loaded))
    control = question("q-0003", [{**alpha_row("Article 2", ALPHA_QUOTE_ART2), "work_id": "gamma",
                                   "recipe_id": "gamma", "attachment_key": "A4CTRL44"}])
    with pytest.raises(InputError, match="failure control"):
        compute_reachability(control, loaded)
    wrong_recipe = question("q-0004", [{**alpha_row("Article 2", ALPHA_QUOTE_ART2), "recipe_id": "beta"}])
    with pytest.raises(InputError, match="binds it to"):
        compute_reachability(wrong_recipe, loaded)


def test_an_answer_past_the_index_cap_is_reachable_but_flagged(export):
    past = question("q-0001", [alpha_row("Article 3", ALPHA_QUOTE_ART3)])
    block = compute_reachability(past, load_export(export))
    alternate = block["rows"][0]["alternates"][0]
    assert alternate["reachable"] is True
    assert alternate["char_offset"] + len(ALPHA_QUOTE_ART3) > CAP
    assert alternate["within_index_cap"] is False


def test_reachability_positive_and_negative_controls_on_the_committed_export():
    loaded = load_export(COMMITTED_EXPORT)
    decision = json.loads((COMMITTED_EXPORT / "fulltext" / "R74WLCBB.json").read_text())["content"]
    start = decision.index("Article 12. Feed in Tariff")
    quote = " ".join(decision[start:start + 120].split())
    row = {"work_id": "vn-decision-11-2017-qdttg-solar-fit-en", "recipe_id": "vn-decision-11-2017-qdttg-solar-fit-en",
           "attachment_id": None, "attachment_key": "R74WLCBB", "section": "Article 12",
           "alternates": [{"page_printed": None, "char_offset": None, "quote": quote}],
           "chain": {name: None for name in CHAIN_FIELDS}}
    positive = compute_reachability(question("q-0001", [row]), loaded)
    assert positive["rows"][0]["alternates"][0] == {
        "reachable": True, "char_offset": start, "occurrences": 1, "reason": None, "within_index_cap": True,
    }
    negative_row = {**row, "alternates": [{"page_printed": None, "char_offset": None,
                                           "quote": "The feed-in tariff for wind power is 8.5 US cents per kWh."}]}
    negative = compute_reachability(question("q-0002", [negative_row]), loaded)
    assert negative["reachable"] is False
    assert negative["rows"][0]["alternates"][0]["reason"] == "quote not located in the export fulltext"


# ------------------------------------------------------------------ the committed bank and artifacts


def test_the_committed_bank_validates_against_the_committed_export_without_restamping():
    summary = validate_bank(COMMITTED_BANK, load_export(COMMITTED_EXPORT), stamp=False)
    assert summary["questions"] >= 5
    # An unreachable alternate is a defect only on a question that claims an answer.
    # A declared failure control, and an answer the stock reindex never reached, pin a
    # quote that is genuinely absent from the export — that absence IS the question, and
    # validate_bank's own policy admits it only behind expected_miss with a mechanism.
    # Equality here would have forced those rows out of the bank, which the authoring
    # ruling of 2026-09-06 forbids ("do not drop such questions").
    unreachable = 0
    for path in sorted(COMMITTED_BANK.glob("q-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        absent = [
            alternate
            for row in record["reachability"]["rows"]
            for alternate in row["alternates"]
            if not alternate["reachable"]
        ]
        unreachable += len(absent)
        if absent:
            assert record["expected_miss"] is True, f"{record['id']} pins an absent quote but claims an answer"
            assert record["expected_miss_mechanism"], f"{record['id']} is expected-miss with no mechanism named"
    # Positive control: the reachability probe must be able to come out the other way.
    # Without this the assertion above passes on a bank where nothing is ever unreachable.
    assert unreachable > 0, "no expected-miss row exercises the unreachable branch"
    assert summary["reachable_alternates"] == summary["alternates"] - unreachable


def test_the_committed_replies_score_against_the_committed_bank(thresholds):
    if not COMMITTED_REPLIES.is_file():
        pytest.skip("no committed replies file")
    replies = load_replies(json.loads(COMMITTED_REPLIES.read_text(encoding="utf-8")))
    report = evaluate(load_bank(COMMITTED_BANK), replies, load_export(COMMITTED_EXPORT), thresholds)
    assert report["state"] in {PASS, FAIL, NOT_RUN}
    assert report["unanswered_questions"] == []
    assert report["run"]["build_sha"]
    assert set(report["run"]["reply_shape"]["hit_fields"]) >= {"itemKey", "snippet"}


def test_the_json_schema_carries_the_scorers_vocabularies():
    schema = json.loads((COMMITTED_BANK / "bank.schema.json").read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert properties["schema"]["const"] == BANK_SCHEMA
    assert tuple(properties["signal"]["enum"]) == SIGNALS
    assert tuple(properties["mode"]["enum"]) == MODES
    assert tuple(properties["facet"]["enum"]) == FACETS
    assert tuple(properties["stratum"]["enum"]) == STRATA
    assert tuple(properties["generator"]["enum"]) == GENERATORS
    assert tuple(properties["set_kind"]["enum"]) == SET_KINDS
    assert tuple(schema["$defs"]["language"]["enum"]) == LANGUAGES
    assert tuple(schema["$defs"]["chain"]["properties"]) == CHAIN_FIELDS
    for record in load_bank(COMMITTED_BANK):
        assert set(record) - {"retained_reason"} <= set(properties)


def test_the_specification_and_the_schema_name_the_same_record_fields():
    """SPEC §5.2.10 owns the field names; the schema and the scorer follow them.

    The /gaze round on PR #409 found the two disagreeing by construction: the
    specification described `primary`, `relations` and a singular `mechanism`
    that `bank.schema.json` never implemented, while the schema set
    `additionalProperties: false`, so the missing ones could not even be added.
    This test is what makes that class of drift loud instead of silent: every
    field the schema requires must appear in the specification's own table, and
    the two names the specification owns must be the ones the scorer reads.
    """

    spec = SPEC.read_text(encoding="utf-8")
    start = spec.index("**The question record is the gate's input contract.**")
    end = spec.index("A **lane** is R29's pair", start)
    table = spec[start:end]
    schema = json.loads((COMMITTED_BANK / "bank.schema.json").read_text(encoding="utf-8"))
    for field in schema["required"]:
        assert f"`{field}`" in table, f"SPEC §5.2.10's record table does not name {field}"
    assert "`primary`" in table and "`mechanism`" in table
    # And what the specification calls out as living elsewhere is not a field.
    assert "relations" not in schema["properties"] and "answers" not in schema["properties"]
    record = load_bank(COMMITTED_BANK)[0]
    assert isinstance(record["primary"], list) and isinstance(record["mechanism"], list)


def test_a_bank_record_at_the_superseded_v2_schema_is_refused_by_name():
    record = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    record["schema"] = "menagerie-bank/v2"
    record["pinned"] = record.pop("primary")
    record["mechanisms"] = record.pop("mechanism")
    with pytest.raises(InputError, match="menagerie-bank/v2 records are no longer read"):
        validate_question(record)


def test_bank_shape_lists_every_vocabulary_value_with_zeros(export):
    questions = [question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])]
    shape = bank_shape(questions, load_export(export))
    assert shape["by_stratum"] == {"core": 1, "reserve": 0}
    assert shape["by_signal"]["agreement"] == 0
    assert shape["by_format"] == {"pdf": 1, "html": 0, "other": 0}
    assert shape["rows_per_document"] == {"alpha": 1, "alpha-fr": 0, "beta": 0}


# ------------------------------------------------------------------ the CLI


@pytest.mark.integration
def test_cli_exit_codes_not_run_pass_fail_and_input_error(tmp_path, export):
    bank = write_bank(tmp_path, question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)]))
    output = tmp_path / "report.json"

    def score(replies_path):
        return subprocess.run(
            [sys.executable, str(DRIVER), "score", "--bank", str(bank), "--export", str(export),
             "--replies", str(replies_path), "--output", str(output), "--spec", str(SPEC)],
            cwd=REPO, capture_output=True, text=True,
        )

    missing = score(tmp_path / "absent.json")
    assert missing.returncode == 3
    assert json.loads(output.read_text())["state"] == NOT_RUN
    assert "by_stratum: core 1, reserve 0 (not-measured)" in missing.stdout

    good = [reply("q-0001", [result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2)])]
    replies_path = tmp_path / "replies.json"
    replies_path.write_text(json.dumps(bundle(export, good, previous=good)))
    assert score(replies_path).returncode == 0
    assert json.loads(output.read_text())["state"] == PASS

    replies_path.write_text(json.dumps(bundle(export, [reply("q-0001", [result(1, "P3BETA33")])],
                                              previous=good)))
    assert score(replies_path).returncode == 1
    assert json.loads(output.read_text())["state"] == FAIL

    replies_path.write_text(json.dumps({"schema": "golden-gate-input/v1"}))
    refused = score(replies_path)
    assert refused.returncode == 2
    assert "golden-gate-input/v1" in refused.stderr

    validate = subprocess.run(
        [sys.executable, str(DRIVER), "validate", "--bank", str(bank), "--export", str(export)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert validate.returncode == 2 and "no reachability stamp" in validate.stderr
    stamp = subprocess.run(
        [sys.executable, str(DRIVER), "validate", "--bank", str(bank), "--export", str(export), "--stamp"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert stamp.returncode == 0 and "1/1 alternate(s) reachable" in stamp.stdout


def test_a_previous_run_against_another_export_makes_stability_not_run_not_fail(export, thresholds):
    """B.6: a re-pin moves item keys and the passage distribution, so a Jaccard against the
    old run measures the re-pin. The first run on a re-exported fixture read 0.029 and
    failed the gate for that reason alone (2026-09-06); it is not-run with the reason."""
    q = question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)])
    now = [reply("q-0001", [result(1, "P1ALPHA1", evidence=ALPHA_QUOTE_ART2), result(2, "P3BETA33")])]
    payload = bundle(export, now, previous=[reply("q-0001", [result(1, "OLDKEY01")])])
    payload["previous_run"]["run"]["export_sha256"] = "e" * 64
    report = evaluate([q], load_replies(payload), load_export(export), thresholds)
    stability = report["readings"]["stability"]
    assert stability["state"] == NOT_RUN and "re-pin" in stability["reason"]
    assert report["readings"]["r34"]["state"] == PASS
    assert report["state"] == NOT_RUN
