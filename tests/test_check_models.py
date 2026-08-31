"""The model-registry guard, exercised against fixture repositories.

Two defects are in scope and they fail in opposite directions.

The first is a model id hard-coded in `bench/` outside the registry. That one is
loud once you look for it, and the tests below give the guard a fixture carrying a
real id so a green run means something: a grep that finds nothing and a grep that
cannot look return the same output otherwise.

The second is the asymmetric one. A guard built only from the ids the registry
already declares catches the removal case and misses the arrival case — a new model
wired straight into a driver, which is exactly the move the registry exists to
prevent. `test_a_model_absent_from_the_registry_is_still_caught` is that direction,
and it is the test that would fail against a registry-derived-only implementation.

Fixtures are whole small repositories under tmp_path, run through the real `run()`,
because the wiring — which directories are read, which are skipped — is where this
guard can go quietly wrong.
"""

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("cm", REPO / "bench" / "check_models.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cm = load()

MINIMAL_RECORD = {
    "id": "fixture-model",
    "hf_repo": "Fixture/fixture-embed-v1",
    "upstream_repo": "Fixture/fixture-embed-v1",
    "params": 1,
    "dim": 8,
    "max_seq": 512,
    "max_seq_source": "fixture",
    "languages": {"codes": ["fr", "de", "vi", "el", "ru"], "source": "fixture"},
    "licence": "apache-2.0",
    "mrl": {"claimed": False, "source": "fixture"},
    "input_template": {"query": "", "passage": ""},
    "pooling": "mean",
    "pooling_source": "fixture",
    "normalize": True,
    "normalize_source": "fixture",
    "hf_revision": "0" * 40,
    "availability": {
        "state": "available",
        "http_status": 200,
        "probed_utc": "2026-08-29T00:00Z",
        "dtypes": {"fp32": ["onnx/model.onnx"]},
        "reason": "",
    },
    "status": "candidate",
    "notes": "fixture",
}

R7_LINE = (
    "- **R7 — multilingual by default, in two tiers.** The default path MUST work\n"
    "  for French, German, Vietnamese, Greek and Russian with no configuration. It\n"
    "  SHOULD work, with no configuration, for Arabic and Chinese.\n"
)


def build(root: Path, files: dict[str, str], models: dict | None = None) -> Path:
    """A fixture repository: a registry, R7's sheet, and whatever `files` adds."""
    registry = models if models is not None else {"states": cm.STATES, "models": [MINIMAL_RECORD]}
    (root / "bench").mkdir(parents=True, exist_ok=True)
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / cm.REGISTRY).write_text(json.dumps(registry, indent=2), encoding="utf-8")
    (root / cm.R7_SOURCE).write_text(R7_LINE, encoding="utf-8")
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


# --- the guard, against fixtures -------------------------------------------------


def test_clean_repo_passes(tmp_path):
    repo = build(tmp_path, {"bench/driver.mjs": "const model = opt.model;\n"})
    assert cm.run(repo) == 0


def test_hard_coded_registry_repo_fails(tmp_path):
    """The positive control. Without this firing, a green run means nothing."""
    repo = build(tmp_path, {"bench/driver.mjs": "const m = 'Fixture/fixture-embed-v1';\n"})
    assert cm.run(repo) == 1


def test_a_model_absent_from_the_registry_is_still_caught(tmp_path):
    """The arrival case: a new model wired into a driver instead of declared.

    A guard whose vocabulary is only the registry's own repos passes this and is
    useless for the defect the registry exists to prevent.
    """
    repo = build(tmp_path, {"bench/driver.mjs": "const m = 'mixedbread-ai/mxbai-embed-large-v1';\n"})
    assert cm.run(repo) == 1


def test_results_are_data_and_are_not_scanned(tmp_path):
    """A result record names the model it measured; that provenance is required."""
    repo = build(
        tmp_path,
        {"bench/results/run/cell.json": '{"model": "Fixture/fixture-embed-v1"}\n'},
    )
    assert cm.run(repo) == 0


def test_the_registry_itself_may_name_models(tmp_path):
    assert cm.run(build(tmp_path, {})) == 0


def test_file_paths_are_not_read_as_model_ids(tmp_path):
    """`onnx/model_fp16.onnx` and `bench/results/…` are paths, not repo ids."""
    repo = build(
        tmp_path,
        {
            "bench/driver.mjs": (
                "// resolves onnx/model_fp16.onnx and writes bench/results/embed-cost.json\n"
                "// see bench/results/0025-x1-recall/embed-feasibility.json and/or the ladder\n"
            )
        },
    )
    assert cm.run(repo) == 0


def test_a_ticket_path_is_not_read_as_a_model_id(tmp_path):
    """A driver citing its ticket writes `tickets/NNNN-….erg`, whose slug can
    contain a family word ('embedder'); that is a path, not a repo id."""
    repo = build(
        tmp_path,
        {
            "bench/census.mjs": (
                "// ticket: tickets/0140-cap-the-chunker-below-the-embedder-limit.erg\n"
            )
        },
    )
    assert cm.run(repo) == 0


def test_a_record_missing_a_required_key_fails(tmp_path):
    incomplete = dict(MINIMAL_RECORD)
    del incomplete["input_template"]
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [incomplete]})
    assert cm.run(repo) == 1


def test_an_unknown_availability_state_fails(tmp_path):
    """The three states are an enum; a fourth spelling of "no" is the drift."""
    record = json.loads(json.dumps(MINIMAL_RECORD))
    record["availability"]["state"] = "missing"
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_candidate_without_an_available_dtype_fails(tmp_path):
    """A model nothing can load is a finding, never a candidate."""
    record = json.loads(json.dumps(MINIMAL_RECORD))
    record["availability"]["state"] = "confirmed_absent"
    record["availability"]["dtypes"] = {}
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_model_failing_r7_must_be_rejected(tmp_path):
    """R7 is a filter, not a tiebreak: an English-only model is recorded, not run."""
    record = json.loads(json.dumps(MINIMAL_RECORD))
    record["languages"]["codes"] = ["en"]
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_unreadable_r7_fails_rather_than_passing(tmp_path):
    """If the guard cannot read R7 it says so; it never reports a clean sheet."""
    repo = build(tmp_path, {})
    (repo / cm.R7_SOURCE).write_text("nothing about languages here\n", encoding="utf-8")
    assert cm.run(repo) == 1


# --- R7 extraction ---------------------------------------------------------------


def test_r7_languages_are_read_from_the_sheet_not_restated():
    """The codes come from R7's own sentences, so editing R7 moves the guard with it.

    Two tiers since 2026-08-31: the MUST tier filters candidates, the SHOULD tier
    is reported rather than enforced, because failing a SHOULD would promote it.
    """
    assert cm.r7_language_codes(REPO / cm.R7_SOURCE) == (
        {"en", "fr", "vi"},
        {"ar", "zh", "de", "hi", "ru", "es"},
    )


# --- the real repository ---------------------------------------------------------


def test_the_repository_passes_its_own_guard():
    assert cm.run(REPO) == 0


def test_registry_records_carry_every_required_key():
    registry = cm.load_registry(REPO)
    assert registry["models"], "the registry declares no model"
    for record in registry["models"]:
        missing = sorted(cm.REQUIRED_KEYS - set(record))
        assert not missing, f"{record.get('id')} is missing {missing}"


def test_the_three_states_are_distinct_values():
    assert len(set(cm.STATES)) == 3
    assert cm.STATES["confirmed_absent"] != cm.STATES["could_not_look"]


def test_the_registry_exercises_all_three_states():
    """An enumeration that can only come out one way has measured nothing.

    Each state must be carried by at least one record, so the distinction between
    "queried, publishes nothing" and "could not read the listing" is visible in the
    artifact rather than only in the schema.
    """
    states = {record["availability"]["state"] for record in cm.load_registry(REPO)["models"]}
    assert states == set(cm.STATES)


def test_every_rejected_record_carries_its_reason():
    for record in cm.load_registry(REPO)["models"]:
        if record["status"] == "rejected":
            criteria = record.get("rejection", {}).get("criteria")
            assert criteria, f"{record['id']} is rejected with no criterion"
            assert set(criteria) <= set(cm.REJECTION_CRITERIA), criteria


def test_the_e5_input_template_lives_in_the_registry():
    """The prefixes are a per-model property; a driver that hard-codes them is the bug."""
    e5 = [r for r in cm.load_registry(REPO)["models"] if r["id"].startswith("multilingual-e5")]
    assert e5, "no e5 record in the registry"
    for record in e5:
        if record["status"] != "candidate":
            continue
        assert record["input_template"]["query"] == "query: "
        assert record["input_template"]["passage"] == "passage: "


def test_exemptions_are_only_the_registry_and_the_guard():
    """Every exemption is a hole; two are argued in the guard, a third is not."""
    assert cm.EXEMPT == {cm.REGISTRY, "bench/check_models.py"}


def test_the_data_exemption_does_not_extend_to_siblings_by_prefix():
    """`bench/results_backup/` is not `bench/results/`, and must not inherit its pass.

    The tuple is pinned rather than merely non-empty because every entry is a hole,
    and a hole added without argument is the one nobody audits. Two are argued in
    the guard: `results/` is data whose cells must name their model, `__pycache__/`
    is generated bytecode of source already scanned. A third arriving here should
    fail this test until someone writes down why.
    """
    assert cm.SKIPPED == ("bench/results/", "bench/__pycache__/")


def test_a_generated_binary_under_bench_does_not_fail_the_scan(tmp_path):
    """The exemption above, from the other side.

    Making an undecodable file a finding is right for a driver and wrong for
    bytecode, and `make check` runs after a test run has populated `__pycache__`.
    Without this the guard would go red on its own artifacts, which is how a guard
    gets switched off.
    """
    repo = build(tmp_path, {})
    cache = repo / "bench" / "__pycache__"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "driver.cpython-314.pyc").write_bytes(b"\xda\xfd\x00binary not utf-8\n")
    assert cm.run(repo) == 0


def test_the_heuristic_boundary_is_declared():
    """What escapes the grep today, pinned so the hole is a size and not a surprise.

    Catching every conceivable repo id would mean treating every `owner/name` string
    in every comment as a model, and a guard that cries wolf gets exempted rather
    than fixed. These are real embedding models whose publisher is unlisted and whose
    name carries no family word: they would slip past. Anyone who widens the pattern
    should watch this test go red and delete the entry, not the test.
    """
    escapes = ["sergeyzh/rubert-tiny-turbo", "ai-forever/ru-en-RoSBERTa"]
    for model in escapes:
        assert not cm.model_ids_in(f"const m = '{model}';"), f"{model} is now caught"
    # And the boundary is a boundary, not a blanket: an unlisted publisher with a
    # family word in the name is still caught.
    assert cm.model_ids_in("const m = 'acme-labs/super-bge-v9';")


def test_the_registry_agrees_with_the_probe_artifact():
    """Availability is observed once and copied; a copy that drifts is the defect.

    The registry's blocks are written by the probe. Nothing stops a hand edit, and a
    hand-edited availability is exactly the "read a 401 as an absence" mistake coming
    back through a different door.
    """
    registry = cm.load_registry(REPO)
    artifact = json.loads(
        (REPO / registry["probe"]["artifact"]).read_text(encoding="utf-8")
    )
    probed = {record["repo"]: record for record in artifact["results"]}
    for record in registry["models"]:
        observed = probed.get(record["hf_repo"])
        assert observed, f"{record['id']}: {record['hf_repo']} is in no probe run"
        assert record["availability"]["state"] == observed["state"], record["id"]
        assert record["availability"]["http_status"] == observed["http_status"], record["id"]
        assert record["availability"]["dtypes"] == (observed.get("dtypes") or {}), record["id"]


def test_a_pytorch_loader_resolves_the_upstream_repository():
    """The mirror publishes ONNX; the author's repo publishes the weights.

    A sentence-transformers loader handed the ONNX mirror benchmarks a different
    artifact and says nothing about it, so the pairing is checked rather than trusted.
    """
    for path in sorted((REPO / "bench").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "SentenceTransformer(" not in source or "resolve_model" not in source:
            continue
        assert 'kind="upstream"' in source, f"{path.name} loads PyTorch weights from a mirror"


# --- the two ways this guard reported a clean sheet it had not read --------------
#
# Both were found by adversarial review of the first implementation, and both are
# the same defect in different clothes: the guard returned OK for a repository it
# had failed to inspect. A guard whose all-clear is indistinguishable from "I could
# not look" is not a guard, so each case below is pinned with the shape that used
# to pass.


def test_an_empty_models_list_is_a_failure_to_read_not_a_clean_sheet(tmp_path):
    """`registry.get("models", [])` looped zero times and reported OK.

    A bad merge or a half-written regeneration run empties the payload, and every
    per-record check below it then passes vacuously. Malformed JSON already failed
    loudly; this is the narrower hole beside it.
    """
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": []})
    assert cm.run(repo) == 1


def test_a_registry_whose_models_key_is_missing_fails(tmp_path):
    """The same hole reached by a renamed or typo'd key rather than an empty list."""
    repo = build(tmp_path, {}, models={"states": cm.STATES, "modelz": [MINIMAL_RECORD]})
    assert cm.run(repo) == 1


def test_a_models_key_of_the_wrong_type_fails(tmp_path):
    """A dict where a list belongs iterates over its keys and checks nothing."""
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": {"a": MINIMAL_RECORD}})
    assert cm.run(repo) == 1


def test_an_undecodable_file_is_reported_rather_than_skipped(tmp_path):
    """One stray byte used to exempt a whole file from the scan, silently.

    The pair matters more than either half: the same content in valid UTF-8 is
    caught (the test below), so a green run on the undecodable version would have
    meant the encoding -- not the absence of a model id -- bought the silence. In a
    repository whose conventions mandate non-ASCII prose, that is a live accident.
    """
    repo = build(tmp_path, {})
    (repo / "bench" / "driver.mjs").write_bytes(
        b"// un commentaire avec un octet latin1: \xe9clair\n"
        b"const m = 'Fixture/fixture-embed-v1';\n"
    )
    assert cm.run(repo) == 1


def test_the_same_content_in_valid_utf8_is_caught(tmp_path):
    """The control for the test above: decodable, so the id itself is the finding."""
    repo = build(
        tmp_path,
        {"bench/driver.mjs": "// un commentaire\nconst m = 'Fixture/fixture-embed-v1';\n"},
    )
    assert cm.run(repo) == 1


# --- prose that must name its model, and the hole that exemption could become ----


def test_a_line_marked_as_a_literal_is_not_flagged(tmp_path):
    """Provenance prose carries the name on purpose; the guard's remedy can't reach it.

    A docstring saying what was measured, or a result's own `what:` label, has to
    hold the literal name -- "resolve it by registry id" is meaningless in prose,
    and an anonymous provenance cell cannot be read a month later.
    """
    repo = build(
        tmp_path,
        {"bench/driver.mjs": "// measured with Fixture/fixture-embed-v1 model-id-literal: provenance\n"},
    )
    assert cm.run(repo) == 0


def test_the_marker_does_not_exempt_the_rest_of_the_file(tmp_path):
    """The exemption is per line, and this is the test that keeps it that way.

    Exempting the whole file would be the cheap version and would hide real wiring
    in the next driver that grows a comment. A marked comment beside an unmarked
    `pipeline(...)` call must still fail.
    """
    repo = build(
        tmp_path,
        {
            "bench/driver.mjs": (
                "// measured with Fixture/fixture-embed-v1 model-id-literal: provenance\n"
                "const m = 'Fixture/fixture-embed-v1';\n"
            )
        },
    )
    assert cm.run(repo) == 1


# --- pooling: the input_template trap one axis over ------------------------------
#
# Measured 2026-08-29: four of the six candidates pool with `cls` while every
# transformers.js driver hardcoded `mean`. Wrong pooling degrades retrieval
# silently -- it reads as the model being worse rather than as a bug -- so a sweep
# could have rejected a good candidate on it. These pin the guard that stops a
# candidate arriving without the value, and the pair that stops it being a guess.


def test_a_candidate_without_pooling_fails(tmp_path):
    """The positive control: run it against a registry lacking the field."""
    record = dict(MINIMAL_RECORD)
    del record["pooling"]
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_candidate_with_pooling_but_no_source_fails(tmp_path):
    """A value with no provenance cannot be told from a guess, so the pair is required."""
    record = dict(MINIMAL_RECORD, pooling_source="   ")
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_pooling_mode_the_drivers_cannot_pass_fails(tmp_path):
    """`weightedmean` is real and transformers.js has no case for it.

    The first version of this test used `lasttoken`, which was the wrong example:
    the library accepts `last_token`/`eos`, and the throw it produced came from
    this repository canonicalising the flag to a string with no underscore. The
    rule is unchanged and the example now matches it — a mode with no case in
    `feature-extraction.js`'s switch is a finding about the candidate, because
    coercing it to `mean` to let a run proceed would be invisible in the results.
    """
    record = dict(MINIMAL_RECORD, pooling="weightedmean")
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_rejected_record_is_not_required_to_carry_pooling(tmp_path):
    """The requirement is scoped to candidates, and this is the other side of it.

    Without this, the test above would pass just as well if the guard demanded
    pooling of everything, which would be a different rule than the one intended.
    """
    record = dict(MINIMAL_RECORD, status="rejected", rejection={"criteria": ["r7"]})
    del record["pooling"]
    del record["pooling_source"]
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 0


# --- normalize and hf_revision: ticket 0262's two new registry columns -----------
#
# `normalize` (whether the pipeline L2-normalizes the pooled vector) and
# `hf_revision` (the commit sha the availability probe read) closed a gap the
# same shape as pooling's: a value with no provenance is a value nobody can tell
# from a guess. normalize differs from pooling in one respect — "unknown" is
# itself a legitimate recorded value here, because a model's own published
# pipeline config sometimes cannot be read at all, and the requirement is that
# this be written down rather than defaulted to true or false.


def test_a_candidate_without_normalize_fails(tmp_path):
    """The positive control: run it against a registry lacking the field."""
    record = dict(MINIMAL_RECORD)
    del record["normalize"]
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_candidate_with_normalize_but_no_source_fails(tmp_path):
    """A value with no provenance cannot be told from a guess, so the pair is required."""
    record = dict(MINIMAL_RECORD, normalize_source="   ")
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_normalize_defaulted_to_a_bare_default_fails(tmp_path):
    """Any value other than True, False or the literal 'unknown' is rejected.

    This is the guard against exactly the failure mode the ticket names: a
    driver author defaulting an unread value instead of recording that it
    could not be read.
    """
    record = dict(MINIMAL_RECORD, normalize="mean")
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_normalize_unknown_with_its_source_passes(tmp_path):
    """'unknown' is a legitimate recorded state, not a failure to fill the field."""
    record = dict(
        MINIMAL_RECORD,
        normalize="unknown",
        normalize_source="modules.json on Fixture/fixture-embed-v1: not read (could_not_look)",
    )
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 0


def test_a_candidate_without_hf_revision_fails(tmp_path):
    """The positive control: run it against a registry lacking the field."""
    record = dict(MINIMAL_RECORD)
    del record["hf_revision"]
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_blank_hf_revision_fails(tmp_path):
    record = dict(MINIMAL_RECORD, hf_revision="   ")
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 1


def test_a_rejected_record_is_not_required_to_carry_normalize_or_hf_revision(tmp_path):
    """Scoped to candidates, same as pooling — the other side of the requirement."""
    record = dict(MINIMAL_RECORD, status="rejected", rejection={"criteria": ["r7"]})
    del record["pooling"]
    del record["pooling_source"]
    del record["normalize"]
    del record["normalize_source"]
    del record["hf_revision"]
    repo = build(tmp_path, {}, models={"states": cm.STATES, "models": [record]})
    assert cm.run(repo) == 0


# --- the two gaps ticket 0422 closes ---------------------------------------------
#
# Both were demonstrated by adversarial review of 0421 rather than argued, and both
# were the same shape: a check that passed for a reason other than the thing being
# right. Model identity had a mechanical guard from the start; pooling did not.


def test_a_hardcoded_pooling_literal_is_caught(tmp_path):
    """The positive control. Reverting a driver to `pooling: 'mean'` used to pass.

    The reviewer proved the gap by doing exactly this to quant_fidelity.mjs and
    watching check_models, ruff and the whole suite stay green.
    """
    repo = build(
        tmp_path,
        {"bench/driver.mjs": "const t = await extractor(b, { pooling: 'mean' });\n"},
    )
    assert cm.run(repo) == 1


def test_the_python_form_is_caught_too(tmp_path):
    """`pooling="cls"` at a Python call site is the same defect in another syntax."""
    repo = build(tmp_path, {"bench/driver.py": 'out = enc(b, pooling="cls")\n'})
    assert cm.run(repo) == 1


def test_resolving_pooling_from_the_registry_passes(tmp_path):
    """The other side: the shape the drivers actually use must NOT be flagged.

    Without this, a scan that flagged every line containing the word would look
    identical on the failing case and be unusable on the real tree.
    """
    repo = build(
        tmp_path,
        {
            "bench/driver.mjs": (
                "const { pooling } = resolveModel(token);\n"
                "const t = await extractor(b, { pooling, normalize: true });\n"
            )
        },
    )
    assert cm.run(repo) == 0


def test_a_pooling_literal_can_be_exempted_per_line(tmp_path):
    """Reuses the id scan's marker rather than inventing a second mechanism."""
    repo = build(
        tmp_path,
        {"bench/driver.mjs": "// upstream passes pooling: 'mean' model-id-literal: quoting upstream\n"},
    )
    assert cm.run(repo) == 0


# --- input_template: the parity claim, made true rather than retracted -----------


def test_a_hardcoded_input_template_is_caught(tmp_path):
    """The positive control for the guard 0422's first pass wrongly declined to build.

    The retraction priced a bare substring scan, which would have been red on
    arrival. The quote-requiring shape the pooling scan already uses is quiet on the
    real tree and still catches this.
    """
    record = dict(MINIMAL_RECORD, input_template={"query": "query: ", "passage": "passage: "})
    repo = build(
        tmp_path,
        {"bench/driver.mjs": "const t = texts.map((x) => 'passage: ' + x);\n"},
        models={"states": cm.STATES, "models": [record]},
    )
    assert cm.run(repo) == 1


def test_the_words_alone_do_not_trip_the_template_scan(tmp_path):
    """The anti-false-positive control, and the reason the retraction was wrong.

    Four of the five real occurrences under bench/ are these shapes: a bare object
    key, a prose sentence, and an identifier with the word embedded. None is a
    quoted literal, so none is flagged.
    """
    record = dict(MINIMAL_RECORD, input_template={"query": "query: ", "passage": "passage: "})
    repo = build(
        tmp_path,
        {
            "bench/driver.mjs": (
                "return { query: q, ms_per_passage: 1 };\n"
                "// a sentence about the first semantic query: 1 527,8 ms\n"
            )
        },
        models={"states": cm.STATES, "models": [record]},
    )
    assert cm.run(repo) == 0


def test_an_empty_template_declares_nothing_to_scan_for(tmp_path):
    """An empty prefix must not become a literal that matches every line."""
    record = dict(MINIMAL_RECORD, input_template={"query": "", "passage": ""})
    repo = build(
        tmp_path,
        {"bench/driver.mjs": "const s = '';\nconst t = \"\";\n"},
        models={"states": cm.STATES, "models": [record]},
    )
    assert cm.run(repo) == 0


def test_a_quoted_pooling_key_is_caught(tmp_path):
    """`{ "pooling": "mean" }` evaded the first version of the scan.

    The shape is not hypothetical — bench/registry.py assigns through a quoted
    "pooling" key — so a hardcoded value written that way would have passed.
    """
    repo = build(tmp_path, {"bench/driver.mjs": 'const o = { "pooling": "mean" };\n'})
    assert cm.run(repo) == 1
