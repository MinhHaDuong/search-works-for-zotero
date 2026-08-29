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
    "- **R7 — multilingual by default.** The default path MUST work for French,\n"
    "  German, Vietnamese, Greek and Russian with no configuration.\n"
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
    """The codes come from R7's own sentence, so editing R7 moves the guard with it."""
    assert cm.r7_language_codes(REPO / cm.R7_SOURCE) == {"fr", "de", "vi", "el", "ru"}


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
