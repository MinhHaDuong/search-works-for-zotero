"""The registry-driven, resumable sweep harness (ticket 0262), exercised entirely
through a fake executor — no model is downloaded, no ONNX file is loaded here.

`bench/sweep.py`'s `CellExecutor` is a `Protocol` for exactly this reason: the
harness's own bookkeeping (skip/resume, ONNX-hash dedup, unloadable-vs-absent,
missing-cell tolerance, engine-version drift) is independent of which driver a
real executor shells out to, and the ticket's Test section asks for it be
driven with fakes. `FakeExecutor` below plays that role and records every call
it receives so a test can assert a skipped or deduplicated cell never reached
it.
"""

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("sweep", REPO / "bench" / "sweep.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sw = load()


def registry(models: list[dict]) -> dict:
    return {"models": models}


def candidate(model_id: str, **overrides) -> dict:
    record = {
        "id": model_id,
        "status": "candidate",
        "hf_repo": f"Fixture/{model_id}",
        "input_template": {"query": "", "passage": ""},
        "pooling": "mean",
        "normalize": True,
        "availability": {"dtypes": {"fp32": [f"onnx/{model_id}.onnx"], "q8": [f"onnx/{model_id}-q8.onnx"]}},
    }
    record.update(overrides)
    return record


class FakeExecutor:
    """Every call is recorded, so a test can prove a skipped/deduplicated cell
    never reached `measure()` — the thing an all-clear-looking skip test must
    show to be a check rather than a null.
    """

    def __init__(self, resolve_map=None, versions=None, ok=True, error="boom"):
        self.resolve_map = resolve_map or {}
        self._versions = versions or {"@huggingface/transformers": "4.2.0"}
        self.resolve_calls = []
        self.measure_calls = []
        self._ok = ok
        self._error = error

    def engine_versions(self):
        return dict(self._versions)

    def resolve(self, record, dtype):
        self.resolve_calls.append((record["id"], dtype))
        key = (record["id"], dtype)
        if key in self.resolve_map:
            return self.resolve_map[key]
        return sw.ResolveResult(
            loadable=True,
            onnx_path=f"onnx/{record['id']}-{dtype}.onnx",
            onnx_hash=f"hash-{record['id']}-{dtype}",
        )

    def measure(self, record, dtype, device, corpus, kind, resolved, rep):
        self.measure_calls.append((record["id"], dtype, device, corpus, rep))
        if not self._ok:
            return sw.MeasureResult(ok=False, device_selected=device, metrics={}, error=self._error)
        return sw.MeasureResult(
            ok=True,
            device_selected=device,
            metrics={"rss_delta_mb": 100.0 + rep, "query_ms_median": 12.0},
        )


def one_cost_plan(model_id="m1", dtype="fp32", device="cpu") -> "sw.CellPlan":
    return sw.CellPlan(model_id, dtype, device, "fixed-queries-v1", "cost")


# --- resume / skip, in both directions --------------------------------------------
#
# "Skips everything" and "resumes correctly" look identical on a full directory,
# so the test that only ever sees an empty directory is not a check. This pair
# is the positive control: one cell pre-exists, one does not, in the SAME run.


def test_absent_cell_is_run_and_present_cell_is_skipped_in_the_same_sweep(tmp_path):
    reg = registry([candidate("already-measured"), candidate("not-yet-measured")])
    by_id = {m["id"]: m for m in reg["models"]}
    plans = [
        sw.CellPlan("already-measured", "fp32", "cpu", "fixed-queries-v1", "cost"),
        sw.CellPlan("not-yet-measured", "fp32", "cpu", "fixed-queries-v1", "cost"),
    ]
    results_dir = tmp_path / "results"
    pre_existing = sw.cell_path(results_dir, plans[0])
    sw.write_result(pre_existing, {"status": "measured", "sentinel": "do-not-touch"})
    before_mtime = pre_existing.stat().st_mtime_ns
    before_text = pre_existing.read_text()

    executor = FakeExecutor()
    stats = sw.run_sweep(plans, results_dir, executor, by_id)

    assert stats.skipped == 1
    assert stats.measured == 1
    # The pre-existing cell was never touched, and the fake was never asked
    # to resolve or measure it — "skipped" means the executor was not called,
    # not merely that the file still exists afterward.
    assert pre_existing.stat().st_mtime_ns == before_mtime
    assert pre_existing.read_text() == before_text
    assert executor.resolve_calls == [("not-yet-measured", "fp32")]
    assert len(executor.measure_calls) == sw.KIND_REPS["cost"]
    assert all(call[0] == "not-yet-measured" for call in executor.measure_calls)

    new_result = json.loads(sw.cell_path(results_dir, plans[1]).read_text())
    assert new_result["status"] == "measured"


def test_a_second_sweep_over_the_same_plans_does_no_new_work(tmp_path):
    """Idempotence end to end: re-running is a no-op once every cell exists."""
    reg = registry([candidate("m1")])
    by_id = {m["id"]: m for m in reg["models"]}
    plans = [one_cost_plan("m1")]
    results_dir = tmp_path / "results"

    executor = FakeExecutor()
    sw.run_sweep(plans, results_dir, executor, by_id)
    assert executor.measure_calls  # first run did real work

    executor2 = FakeExecutor()
    stats = sw.run_sweep(plans, results_dir, executor2, by_id)
    assert stats.skipped == 1
    assert stats.measured == 0
    assert executor2.measure_calls == []
    assert executor2.resolve_calls == []


# --- the scorer tolerates a missing cell --------------------------------------------


def test_report_names_a_missing_cell_and_still_scores_the_rest(tmp_path):
    reg = registry([candidate("m1"), candidate("m2")])
    by_id = {m["id"]: m for m in reg["models"]}
    plans = [one_cost_plan("m1"), one_cost_plan("m2")]
    results_dir = tmp_path / "results"

    executor = FakeExecutor()
    # Only measure m1; m2 stays absent, as a partial/interrupted sweep would.
    sw.run_sweep([plans[0]], results_dir, executor, by_id)

    report = sw.sweep_report(plans, results_dir)
    assert report["counts"]["missing"] == 1
    assert plans[1].cell_id in report["missing"]
    assert report["counts"]["measured"] == 1
    assert plans[0].cell_id in report["measured"]


def test_report_on_a_wholly_empty_directory_does_not_raise(tmp_path):
    plans = [one_cost_plan("m1")]
    report = sw.sweep_report(plans, tmp_path / "results")
    assert report["counts"]["missing"] == 1
    assert report["counts"]["measured"] == 0


# --- positive control on the fidelity scorer ----------------------------------------
#
# "Already how the nomic q8 result was known to be real rather than a broken
# probe" (ticket) -- promoted here to an assertion against the shipped scorer.


def test_fp32_against_itself_returns_cosine_and_overlap_of_one():
    import numpy as np

    import quant_fidelity_score as qfs

    rng = np.random.default_rng(20260830)
    vectors = rng.normal(size=(64, 16)).astype(np.float32)
    result = qfs.compare(vectors, vectors, k=10)
    assert result["cos_mean"] == 1.0
    assert result["cos_min"] == 1.0
    assert result["overlap_at_10_mean"] == 1.0
    assert result["top1_kept_frac"] == 1.0


# --- duplicate ONNX hash -------------------------------------------------------------


def test_duplicate_onnx_hash_is_recorded_and_costs_no_second_run(tmp_path):
    """Two registry entries whose resolved file is byte-identical: q8 and int8
    resolving to one blob, as nomic did (ticket 0240's tracker).
    """
    reg = registry([candidate("q8-variant"), candidate("int8-variant")])
    by_id = {m["id"]: m for m in reg["models"]}
    shared = sw.ResolveResult(loadable=True, onnx_path="onnx/shared.onnx", onnx_hash="same-hash-both")
    executor = FakeExecutor(
        resolve_map={
            ("q8-variant", "fp32"): shared,
            ("int8-variant", "fp32"): shared,
        }
    )
    plans = [
        sw.CellPlan("q8-variant", "fp32", "cpu", "fixed-queries-v1", "cost"),
        sw.CellPlan("int8-variant", "fp32", "cpu", "fixed-queries-v1", "cost"),
    ]
    results_dir = tmp_path / "results"
    stats = sw.run_sweep(plans, results_dir, executor, by_id)

    assert stats.measured == 1
    assert stats.duplicate == 1
    # No second run spent: measure() called once, not twice.
    assert len(executor.measure_calls) == sw.KIND_REPS["cost"]

    first = json.loads(sw.cell_path(results_dir, plans[0]).read_text())
    second = json.loads(sw.cell_path(results_dir, plans[1]).read_text())
    assert first["status"] == "measured"
    assert second["status"] == "duplicate"
    assert second["duplicate_of"] == plans[0].cell_id


def test_duplicate_detection_holds_across_a_resumed_sweep(tmp_path):
    """The hash index is read from disk at the start of every run, not only
    accumulated in memory — a duplicate must be caught even when the cell it
    duplicates was measured in an earlier, separate invocation.
    """
    reg = registry([candidate("first"), candidate("second")])
    by_id = {m["id"]: m for m in reg["models"]}
    shared = sw.ResolveResult(loadable=True, onnx_path="onnx/shared.onnx", onnx_hash="same-hash")
    results_dir = tmp_path / "results"

    executor1 = FakeExecutor(resolve_map={("first", "fp32"): shared})
    sw.run_sweep([sw.CellPlan("first", "fp32", "cpu", "fixed-queries-v1", "cost")], results_dir, executor1, by_id)

    executor2 = FakeExecutor(resolve_map={("second", "fp32"): shared})
    stats = sw.run_sweep(
        [sw.CellPlan("second", "fp32", "cpu", "fixed-queries-v1", "cost")], results_dir, executor2, by_id
    )
    assert stats.duplicate == 1
    assert executor2.measure_calls == []


# --- engine-version mismatch is surfaced --------------------------------------------


def test_a_stale_engine_version_is_surfaced_not_ignored(tmp_path):
    reg = registry([candidate("m1")])
    by_id = {m["id"]: m for m in reg["models"]}
    plans = [one_cost_plan("m1")]
    results_dir = tmp_path / "results"

    old_executor = FakeExecutor(versions={"@huggingface/transformers": "4.1.0"})
    sw.run_sweep(plans, results_dir, old_executor, by_id)

    report = sw.sweep_report(
        plans, results_dir, current_engine_versions={"@huggingface/transformers": "4.2.0"}
    )
    assert len(report["engine_version_mismatches"]) == 1
    mismatch = report["engine_version_mismatches"][0]
    assert mismatch["recorded"] == "4.1.0"
    assert mismatch["running"] == "4.2.0"


def test_a_matching_engine_version_raises_no_mismatch(tmp_path):
    reg = registry([candidate("m1")])
    by_id = {m["id"]: m for m in reg["models"]}
    plans = [one_cost_plan("m1")]
    results_dir = tmp_path / "results"

    executor = FakeExecutor(versions={"@huggingface/transformers": "4.2.0"})
    sw.run_sweep(plans, results_dir, executor, by_id)

    report = sw.sweep_report(
        plans, results_dir, current_engine_versions={"@huggingface/transformers": "4.2.0"}
    )
    assert report["engine_version_mismatches"] == []


# --- unloadable is a result, and it does not serialise like absent -----------------


def test_unloadable_is_recorded_and_is_not_the_same_as_absent(tmp_path):
    reg = registry([candidate("no-fp16")])
    by_id = {m["id"]: m for m in reg["models"]}
    plan = sw.CellPlan("no-fp16", "fp16", "cpu", "fixed-queries-v1", "cost")
    results_dir = tmp_path / "results"

    executor = FakeExecutor(
        resolve_map={
            ("no-fp16", "fp16"): sw.ResolveResult(
                loadable=False, reason="fp16 aborts at ONNX session init on the CPU provider"
            )
        }
    )
    stats = sw.run_sweep([plan], results_dir, executor, by_id)

    assert stats.unloadable == 1
    path = sw.cell_path(results_dir, plan)
    assert path.exists()  # a RESULT, not a gap in the directory
    record = json.loads(path.read_text())
    assert record["status"] == "unloadable"
    assert executor.measure_calls == []  # never attempted a run it cannot serve

    # And the report tells the two apart: this one is "unloadable", a truly
    # unplanned cell is "missing" -- they must not collapse into one bucket.
    other_plan = sw.CellPlan("no-fp16", "q8", "cpu", "fixed-queries-v1", "cost")
    report = sw.sweep_report([plan, other_plan], results_dir)
    assert plan.cell_id in report["unloadable"]
    assert other_plan.cell_id in report["missing"]
    assert plan.cell_id not in report["missing"]


def test_a_failed_measurement_is_also_not_serialised_as_absent(tmp_path):
    """Distinct from unloadable: resolve succeeded, the run itself errored."""
    reg = registry([candidate("m1")])
    by_id = {m["id"]: m for m in reg["models"]}
    plan = one_cost_plan("m1")
    results_dir = tmp_path / "results"

    executor = FakeExecutor(ok=False, error="ORT session init crashed")
    stats = sw.run_sweep([plan], results_dir, executor, by_id)

    assert stats.failed == 1
    record = json.loads(sw.cell_path(results_dir, plan).read_text())
    assert record["status"] == "failed"
    assert "crashed" in record["error"]


# --- planning is registry-driven, not hardcoded -------------------------------------


def test_plan_cells_defaults_to_every_candidate_and_no_one_else():
    reg = registry([candidate("a"), candidate("b"), dict(candidate("c"), status="rejected")])
    plans = sw.plan_cells(reg, dtypes=("fp32",), devices=("cpu",), kinds=("cost",))
    assert {p.model for p in plans} == {"a", "b"}


def test_cell_path_is_a_pure_function_of_the_five_key_fields():
    plan_a = sw.CellPlan("m1", "fp32", "cpu", "corpus-x", "cost")
    plan_b = sw.CellPlan("m1", "fp32", "cpu", "corpus-x", "cost")
    assert sw.cell_path(Path("/x"), plan_a) == sw.cell_path(Path("/x"), plan_b)


def test_bumping_the_driver_version_invalidates_old_cells(tmp_path):
    """A driver-version bump changes the path, so an old cell reads as absent
    without any special-cased migration code.
    """
    reg = registry([candidate("m1")])
    by_id = {m["id"]: m for m in reg["models"]}
    plan_v1 = one_cost_plan("m1")
    results_dir = tmp_path / "results"
    executor = FakeExecutor()
    sw.run_sweep([plan_v1], results_dir, executor, by_id)
    path_v1 = sw.cell_path(results_dir, plan_v1)
    assert path_v1.exists()

    original_version = sw.KIND_DRIVER_VERSION["cost"]
    try:
        sw.KIND_DRIVER_VERSION["cost"] = "2"
        plan_v2 = one_cost_plan("m1")
        path_v2 = sw.cell_path(results_dir, plan_v2)
        assert path_v1 != path_v2
        assert path_v1.exists()  # the old cell's file is untouched, still on disk
        stats = sw.run_sweep([plan_v2], results_dir, executor, by_id)
        assert stats.measured == 1  # not skipped: a different path, a new cell
    finally:
        sw.KIND_DRIVER_VERSION["cost"] = original_version


# --- the demonstrated exit criterion: adding one candidate measures only it --------


def test_adding_one_candidate_and_re_running_measures_only_the_new_cells(tmp_path):
    """Ticket 0262's verification bullet, driven with a fake executor -- the
    ticket explicitly allows this: "A fake-executor demonstration is
    acceptable; say which it was."
    """
    reg = registry([candidate("granite-97m"), candidate("e5-small")])
    by_id = {m["id"]: m for m in reg["models"]}
    results_dir = tmp_path / "results"
    dtypes = ("fp32", "q8")

    executor = FakeExecutor()
    first_plans = sw.plan_cells(reg, dtypes=dtypes, devices=("cpu",), kinds=("cost",))
    sw.run_sweep(first_plans, results_dir, executor, by_id)
    assert len(executor.measure_calls) == len(first_plans) * sw.KIND_REPS["cost"]
    first_run_files = sorted(p.name for p in results_dir.glob("*.json"))

    # Add one candidate to the registry -- the demonstrated move.
    reg["models"].append(candidate("arctic-embed-m-v2"))
    by_id = {m["id"]: m for m in reg["models"]}
    second_plans = sw.plan_cells(reg, dtypes=dtypes, devices=("cpu",), kinds=("cost",))
    assert len(second_plans) == len(first_plans) + len(dtypes)

    executor2 = FakeExecutor()
    stats = sw.run_sweep(second_plans, results_dir, executor2, by_id)

    assert stats.measured == len(dtypes)  # only the new candidate's cells
    assert stats.skipped == len(first_plans)  # every old cell, untouched
    assert {call[0] for call in executor2.measure_calls} == {"arctic-embed-m-v2"}
    # The old result files are byte-identical to before -- resume touched nothing.
    for name in first_run_files:
        assert (results_dir / name).exists()
    assert len(list(results_dir.glob("*.json"))) == len(first_run_files) + len(dtypes)
