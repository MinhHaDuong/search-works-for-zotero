"""Ticket 0481: `RealExecutor`'s device forwarding, per driver.

`bench/sweep.py`'s docstring for `RealExecutor` says it is "[n]ever invoked by the
test suite ... no download, no ONNX load in tests" — and that exemption is exactly
what let this bug through: `_measure_fidelity` and `_measure_recall` built their
`quant_fidelity.mjs` subprocess command without ever appending `--device`, so every
fidelity/recall cell silently ran at transformers.js's own Node default device
('cpu', `devices.js`'s `DEFAULT_DEVICE`) regardless of what the sweep plan
requested. That is the mechanism behind ticket 0264's throughput anomaly (every
"GPU arm" fidelity figure was actually a CPU rate) and its byte-identical X8
verdict (both arms ran the identical CPU code path) — see
verification/GPU-ANOMALY-0481.md.

This test does not touch a model, ONNX, or the network — it only inspects the
constructed subprocess command lists, by monkeypatching `subprocess.run` to record
`cmd` and write the minimal valid output files each `_measure_*` method reads back.
That keeps faith with the stated "no download, no ONNX load" contract while closing
the actual gap: the bug lived entirely in string-list construction, which needs no
real driver to exercise.

The `_measure_cost` cases are the discriminating control: that method already
forwarded `--device` correctly (this is why the cost/batch-1 figures in 0264 were
never suspect), so asserting on it too proves this test can tell "forwarded" from
"not forwarded" apart, rather than passing vacuously.
"""

import importlib.util
import json
import struct
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("sweep", REPO / "bench" / "sweep.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sw = load()

RECORD = {"id": "fixture-model"}
ROWS = 40
DIM = 2


class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_fake_rung(out_prefix_arg: str) -> None:
    """Write the .json + .f32 pair `quant_fidelity.mjs --out-prefix X` would have
    produced, with just enough rows/dim for `quant_fidelity_score.compare`'s
    top-k (k=30) to run without an argpartition error.
    """
    prefix = Path(out_prefix_arg)
    prefix.with_name(f"{prefix.name}.json").write_text(
        json.dumps({"rows": ROWS, "dim": DIM, "ms_per_passage": 1.0, "stride": 1}), encoding="utf-8"
    )
    data = struct.pack(f"<{ROWS * DIM}f", *([0.1, 0.2] * ROWS))
    prefix.with_name(f"{prefix.name}.f32").write_bytes(data)


def make_fake_run(captured: list[list[str]]):
    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        script = cmd[1]
        if script.endswith("quant_fidelity.mjs"):
            out_prefix = cmd[cmd.index("--out-prefix") + 1]
            _write_fake_rung(out_prefix)
        elif script.endswith("query_embed_cost.mjs"):
            out_path = Path(cmd[cmd.index("--output") + 1])
            out_path.write_text(json.dumps({"models": [{"model_id": "fixture-model"}]}), encoding="utf-8")
        elif script.endswith("vec_task_recall.mjs"):
            out_path = Path(cmd[cmd.index("--output") + 1])
            out_path.write_text(json.dumps({"models": [{"model_id": "fixture-model"}]}), encoding="utf-8")
        return _FakeCompleted()

    return fake_run


def _executor(tmp_path, monkeypatch, **kwargs):
    captured: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", make_fake_run(captured))
    executor = sw.RealExecutor(pkg_root=tmp_path, cache_dir=tmp_path, node_bin="node", **kwargs)
    return executor, captured


def test_measure_cost_forwards_device_control(tmp_path, monkeypatch):
    """Discriminating control: _measure_cost already forwards --device. If this
    assertion ever failed, the test's own ability to detect "forwarded" would be
    suspect -- it must pass, proving the mechanism below is a real absence, not
    a blind spot in how this test looks for the flag.
    """
    executor, captured = _executor(tmp_path, monkeypatch)
    result = executor._measure_cost(RECORD, "q8", "cuda")
    assert result.ok
    assert "--device" in captured[-1]
    assert captured[-1][captured[-1].index("--device") + 1] == "cuda"


def test_measure_cost_omits_device_for_runtime_default(tmp_path, monkeypatch):
    executor, captured = _executor(tmp_path, monkeypatch)
    executor._measure_cost(RECORD, "q8", "(runtime default)")
    assert "--device" not in captured[-1]


def test_measure_fidelity_forwards_device(tmp_path, monkeypatch):
    """The regression this ticket exists to close: ticket 0481 found this flag
    absent from every call quant_fidelity.mjs received during the 0264 campaign,
    which is why every fidelity cell silently ran at the Node.js default device
    ('cpu') no matter what the plan requested.
    """
    executor, captured = _executor(tmp_path, monkeypatch)
    result = executor._measure_fidelity(RECORD, "q8", "cuda", "corpus.txt")
    assert result.ok, result.error
    # Two quant_fidelity.mjs invocations happen (fp32 reference, then the q8 rung);
    # both must carry the request, since a fp32 reference silently run on CPU while
    # the rung under test runs on GPU would corrupt the cross-rung comparison itself.
    fidelity_calls = [c for c in captured if c[1].endswith("quant_fidelity.mjs")]
    assert len(fidelity_calls) == 2
    for cmd in fidelity_calls:
        assert "--device" in cmd, cmd
        assert cmd[cmd.index("--device") + 1] == "cuda"


def test_measure_fidelity_omits_device_for_runtime_default(tmp_path, monkeypatch):
    executor, captured = _executor(tmp_path, monkeypatch)
    executor._measure_fidelity(RECORD, "q8", "(runtime default)", "corpus.txt")
    fidelity_calls = [c for c in captured if c[1].endswith("quant_fidelity.mjs")]
    assert len(fidelity_calls) == 2
    for cmd in fidelity_calls:
        assert "--device" not in cmd


def test_measure_recall_forwards_device(tmp_path, monkeypatch):
    items = tmp_path / "items.txt"
    ords = tmp_path / "ords.txt"
    items.write_text("x", encoding="utf-8")
    ords.write_text("x", encoding="utf-8")
    executor, captured = _executor(tmp_path, monkeypatch, recall_items_path=items, recall_ords_path=ords)
    result = executor._measure_recall(RECORD, "q8", "cuda", "corpus.txt")
    assert result.ok, result.error
    embed_calls = [c for c in captured if c[1].endswith("quant_fidelity.mjs")]
    assert len(embed_calls) == 1
    assert "--device" in embed_calls[0]
    assert embed_calls[0][embed_calls[0].index("--device") + 1] == "cuda"


def test_measure_recall_omits_device_for_runtime_default(tmp_path, monkeypatch):
    items = tmp_path / "items.txt"
    ords = tmp_path / "ords.txt"
    items.write_text("x", encoding="utf-8")
    ords.write_text("x", encoding="utf-8")
    executor, captured = _executor(tmp_path, monkeypatch, recall_items_path=items, recall_ords_path=ords)
    executor._measure_recall(RECORD, "q8", "(runtime default)", "corpus.txt")
    embed_calls = [c for c in captured if c[1].endswith("quant_fidelity.mjs")]
    assert len(embed_calls) == 1
    assert "--device" not in embed_calls[0]
