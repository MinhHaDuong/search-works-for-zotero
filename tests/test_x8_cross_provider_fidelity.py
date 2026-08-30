"""X8 cross-provider fidelity scorer (ticket 0264), driven against synthetic vectors --
no model download, no ONNX load. Mirrors quant_fidelity_score's own positive control:
scoring a rung against itself must return cosine 1,0, which is how a broken scorer is told
apart from a genuinely low-fidelity pair (0240's tracker).
"""

import importlib.util
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location(
        "x8_cross_provider_fidelity", REPO / "verification" / "probes" / "x8_cross_provider_fidelity.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


x8 = load()


def write_vectors(
    directory: Path, model: str, rung: str, vectors: np.ndarray, device: str | None = "cuda"
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{model}__{rung}.f32").write_bytes(vectors.astype(np.float32).tobytes())
    meta = {"rows": vectors.shape[0], "dim": vectors.shape[1]}
    if device is not None:
        meta["device"] = device
    (directory / f"{model}__{rung}.json").write_text(json.dumps(meta))


def test_pending_when_cpu_dir_empty(tmp_path):
    gpu_dir = tmp_path / "gpu"
    cpu_dir = tmp_path / "cpu"
    cpu_dir.mkdir()
    write_vectors(gpu_dir, "modelA", "fp32", np.random.default_rng(0).standard_normal((5, 4)))
    out = tmp_path / "out.json"

    assert x8.main(["--gpu-dir", str(gpu_dir), "--cpu-dir", str(cpu_dir), "--output", str(out)]) == 0

    result = json.loads(out.read_text())
    assert result["status"] == "pending-CPU-side"


def test_identical_vectors_score_1_0(tmp_path):
    """The positive control: same bytes on both arms must return cosine 1,0 and
    overlap 1,0 -- proof the scorer discriminates rather than always reporting a bar-clearing
    number.
    """
    rng = np.random.default_rng(1)
    vectors = rng.standard_normal((40, 8)).astype(np.float32)
    gpu_dir = tmp_path / "gpu"
    cpu_dir = tmp_path / "cpu"
    write_vectors(gpu_dir, "modelA", "q8", vectors)
    write_vectors(cpu_dir, "modelA", "q8", vectors)
    out = tmp_path / "out.json"

    assert x8.main(["--gpu-dir", str(gpu_dir), "--cpu-dir", str(cpu_dir), "--output", str(out)]) == 0

    result = json.loads(out.read_text())
    assert result["status"] == "scored"
    assert result["verdict"] == "all-clear"
    assert result["scored_count"] == 1
    assert result["cleared_count"] == 1
    row = result["rows"][0]
    assert row["status"] == "scored"
    assert row["cos_mean"] == 1.0
    assert row["clears_bar"] is True


def test_divergent_vectors_below_bar(tmp_path):
    """A genuinely different pair must NOT clear the bar -- the counterpart of the
    positive control: the scorer must also be able to say no.
    """
    rng = np.random.default_rng(2)
    gpu_dir = tmp_path / "gpu"
    cpu_dir = tmp_path / "cpu"
    write_vectors(gpu_dir, "modelA", "q8", rng.standard_normal((40, 8)))
    write_vectors(cpu_dir, "modelA", "q8", rng.standard_normal((40, 8)))
    out = tmp_path / "out.json"

    assert x8.main(["--gpu-dir", str(gpu_dir), "--cpu-dir", str(cpu_dir), "--output", str(out)]) == 0

    result = json.loads(out.read_text())
    row = result["rows"][0]
    assert row["clears_bar"] is False
    assert result["verdict"] == "some-below-bar"
    assert result["scored_count"] == 1
    assert result["cleared_count"] == 0


def test_gpu_side_runtime_default_device_refused(tmp_path):
    """Ticket 0482's assertion: a GPU-side vector whose metadata records no resolved
    device -- the exact fingerprint ticket 0481 found on every 0264 fidelity cell,
    where the harness silently ran on CPU regardless of the requested device -- must
    not be scored, even though the bytes could otherwise compare fine.
    """
    rng = np.random.default_rng(3)
    vectors = rng.standard_normal((10, 4)).astype(np.float32)
    gpu_dir = tmp_path / "gpu"
    cpu_dir = tmp_path / "cpu"
    write_vectors(gpu_dir, "modelA", "fp32", vectors, device="(runtime default)")
    write_vectors(cpu_dir, "modelA", "fp32", vectors, device="cpu")
    out = tmp_path / "out.json"

    assert x8.main(["--gpu-dir", str(gpu_dir), "--cpu-dir", str(cpu_dir), "--output", str(out)]) == 0

    result = json.loads(out.read_text())
    row = result["rows"][0]
    assert row["status"] == "device-unresolved"
    assert result["verdict"] is None  # nothing scored, so no all-clear/some-below-bar verdict
    assert result["scored_count"] == 0
    assert result["cleared_count"] == 0


def test_missing_gpu_side_reported_not_crashed(tmp_path):
    gpu_dir = tmp_path / "gpu"
    cpu_dir = tmp_path / "cpu"
    write_vectors(gpu_dir, "modelA", "fp32", np.zeros((3, 2)))
    # CPU dir has content but not this (model, rung) pair.
    write_vectors(cpu_dir, "modelB", "fp32", np.zeros((3, 2)))
    out = tmp_path / "out.json"

    assert x8.main(["--gpu-dir", str(gpu_dir), "--cpu-dir", str(cpu_dir), "--output", str(out)]) == 0

    result = json.loads(out.read_text())
    row = result["rows"][0]
    assert row["status"] == "missing"
    assert row["have_gpu"] is True
    assert row["have_cpu"] is False
