"""The registry-driven, resumable, idempotent sweep harness.

Ticket 0262. This is not a sixth measurement script: it is the thing that
decides WHICH cell of (model, dtype, device, corpus, kind) to run next, calls
one of the five existing drivers to run it, and writes one result file per
cell so a campaign can be killed and resumed without losing what it already
paid for. `quant_fidelity.mjs`, `quant_fidelity_score.py`,
`query_embed_cost.mjs` and `vec_task_recall.mjs` stay the only code that knows
how to embed a passage or score a vector; this file never does either itself.
`RealExecutor` wires all four into the three kinds this harness drives
(`cost`, `fidelity`, `recall`); `merge_dtype_ladder.py`'s role — merging
per-dtype cost cells into one ladder — is superseded by `sweep_report()`
below, which reads the new keyed-per-cell files directly rather than the
scratch `{tag}-{dtype}.json` layout that script expected.

Two things make a sweep safe to interrupt and rerun:

  1. **A cell is its own filename.** `cell_path()` is a pure function of the
     five key fields plus a driver version, so a completed cell always maps
     to the same path and `path.exists()` is the whole resume test. Bumping
     `KIND_DRIVER_VERSION` for a kind invalidates every prior cell of that
     kind by construction — no separate migration step, because the old
     files simply stop matching any path a new plan would ask for.
  2. **A write is atomic.** `write_result` writes to a sibling `.tmp` path and
     `os.replace()`s it into place, so a process killed mid-write leaves
     either the old complete file or nothing — never a half-written JSON
     that `path.exists()` would wrongly treat as a finished cell.

Three terminal states, and they do not collapse into each other or into
"the file is absent":

  measured    the driver ran and produced metrics
  unloadable  the resolve step determined the dtype cannot be loaded for
              this model — recorded, not skipped, because "we tried and it
              does not load" is a fact worth keeping across a resume
  duplicate   the resolved ONNX file hashes the same as a cell already
              measured; no run was spent, and the record points at the cell
              that was

A cell with none of the three is simply not on disk yet, and the report
below calls that `missing` — which a resumed sweep will pick up, and a
`missing` result at report time is not an error, it is the normal state of
a partial sweep in progress.

Executor abstraction. `resolve()`/`measure()`/`engine_versions()` are the only
places this module touches a model, a subprocess, or the network, and they are
a `Protocol` so tests can supply a fake that does none of those — the Test
section of ticket 0262 requires the skip/resume/duplicate/unloadable/missing
behaviour be driven without downloading a model or loading ONNX, and the fake
is how.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import socket
import statistics
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry import candidate_ids, load_registry  # noqa: E402

logger = logging.getLogger("sweep")

BENCH = Path(__file__).resolve().parent

#: One entry per kind this harness drives. `driver` names the script(s) that
#: actually do the measuring, `reps` is how many fresh-process repeats a cell
#: gets (Action 6: every RSS cell is repeated over five fresh processes and
#: reported as median + spread — "RSS cell" is the cost kind), and the version
#: suffix is what a schema change bumps to invalidate old cells.
KIND_DRIVER = {
    "cost": "query_embed_cost.mjs",
    "fidelity": "quant_fidelity.mjs+quant_fidelity_score.py",
    "recall": "quant_fidelity.mjs+vec_task_recall.mjs",
}
KIND_DRIVER_VERSION = {"cost": "1", "fidelity": "1", "recall": "1"}
KIND_REPS = {"cost": 5, "fidelity": 1, "recall": 1}

#: The four engines a result depends on (DESIGN's "Engine tracking" section).
#: Each is a package under `<pkg-root>/node_modules/<name>/package.json`.
ENGINE_PACKAGES = (
    "@huggingface/transformers",
    "onnxruntime-node",
    "onnxruntime-web",
    "onnxruntime-common",
)

_SLUG = re.compile(r"[^A-Za-z0-9._-]+")


def slug(text: str) -> str:
    return _SLUG.sub("-", text).strip("-") or "x"


# --------------------------------------------------------------------------- plan


@dataclass(frozen=True)
class CellPlan:
    """One cell's identity. Five fields, per the ticket; `kind` selects which
    driver produces it and doubles as the sixth axis a result file's name
    needs to avoid a cost cell and a fidelity cell colliding on one path.
    """

    model: str
    dtype: str
    device: str
    corpus: str
    kind: str

    @property
    def driver_version(self) -> str:
        return KIND_DRIVER_VERSION[self.kind]

    @property
    def cell_id(self) -> str:
        return "__".join(
            slug(part)
            for part in (
                self.model,
                self.dtype,
                self.device,
                self.corpus,
                f"{self.kind}-v{self.driver_version}",
            )
        )


def cell_path(results_dir: Path, plan: CellPlan) -> Path:
    return results_dir / f"{plan.cell_id}.json"


def plan_cells(
    registry: dict,
    *,
    models: list[str] | None = None,
    dtypes: tuple[str, ...] = ("fp32", "fp16", "q8", "uint8"),
    devices: tuple[str, ...] = ("cpu",),
    corpora: dict[str, str] | None = None,
    kinds: tuple[str, ...] = ("cost", "fidelity"),
) -> list[CellPlan]:
    """The cartesian product of candidates x dtypes x devices x kinds.

    `models` defaults to every registry id with `status: candidate` — never a
    hardcoded list, so the registry stays the only place a model name is
    named. `corpora` maps kind -> corpus label; a kind absent from it is
    skipped (a cost cell has no external corpus and always uses the fixed
    label `fixed-queries-v1`, matching `query_embed_cost.mjs`'s own five
    built-in queries).
    """
    ids = models if models is not None else candidate_ids(registry)
    corpora = corpora or {}
    plans = []
    for model_id in ids:
        for kind in kinds:
            corpus = corpora.get(kind, "fixed-queries-v1" if kind == "cost" else "")
            if kind != "cost" and not corpus:
                raise ValueError(f"kind {kind!r} needs a corpus label; none given")
            for dtype in dtypes:
                for device in devices:
                    plans.append(CellPlan(model_id, dtype, device, corpus, kind))
    return plans


# ------------------------------------------------------------------- executor


@dataclass(frozen=True)
class ResolveResult:
    """Whether a (model, dtype) can be loaded, and what its ONNX file hashes to.

    `loadable=False` covers two different real causes and does not
    distinguish them at this level — a dtype the repo never published, and a
    dtype the repo publishes but that fails at session init (fp16 on the CPU
    provider, DESIGN's known case) — because both are the same fact to the
    harness: this cell will not produce a measurement, record it as such.
    `reason` carries which one it was.
    """

    loadable: bool
    onnx_path: str | None = None
    onnx_hash: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class MeasureResult:
    """One rep's raw outcome. `device_selected` is the device ACTUALLY used,
    never the device requested — Action 9's distinction — and it is the
    executor's job to determine it, because only the executor is close enough
    to the run to know.
    """

    ok: bool
    device_selected: str
    metrics: dict
    error: str = ""


class CellExecutor(Protocol):
    """Everything the sweep planner needs from a model, a subprocess, or the
    network — and the whole surface a test replaces with a fake.
    """

    def resolve(self, record: dict, dtype: str) -> ResolveResult: ...

    def measure(
        self,
        record: dict,
        dtype: str,
        device: str,
        corpus: str,
        kind: str,
        resolved: ResolveResult,
        rep: int,
    ) -> MeasureResult: ...

    def engine_versions(self) -> dict[str, str]: ...


# --------------------------------------------------------------- real executor


def read_package_version(pkg_root: Path, package: str) -> str:
    path = pkg_root / "node_modules" / package / "package.json"
    if not path.is_file():
        return "not-installed"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version", "unknown")
    except (OSError, json.JSONDecodeError):
        return "unreadable"


def _read_valid_json(path: Path) -> dict | None:
    """Parse `path` as JSON, or None if it is absent, empty, or truncated.

    A driver subprocess that crashes mid-write (the padme GPU host's native-binding
    exit crash, ticket 0264) can leave a partial file; a truncated JSON parse error
    here is the signal that the crash landed before the write finished, not after.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _subprocess_diagnostic(result: subprocess.CompletedProcess) -> str:
    """Head and tail of stderr, not just the tail.

    A crash that happens deep in graph execution (e.g. a mixed CUDA/WebGPU
    partitioning error) prints its real diagnostic early, then the process can go on
    to print thousands of characters of routine per-op warnings before exiting. A
    tail-only slice loses the actual error under that noise (observed on padme,
    ticket 0264: `result.stderr[-4000:]` captured only repeated WebGPU buffer-limit
    warnings and dropped the "Non-zero status code... Sqrt node" line that named the
    real failure). Head and tail together are cheap and keep both ends.
    """
    err = result.stderr or ""
    head, tail = err[:3000], err[-2000:]
    body = head if len(err) <= 5000 else f"{head}\n...[{len(err) - 5000} chars elided]...\n{tail}"
    return f"returncode={result.returncode}\n{body}"


@dataclass
class RealExecutor:
    """Wires the five existing drivers up as subprocesses. Never invoked by
    the test suite (per CLAUDE.md and the ticket: no download, no ONNX load
    in tests) — exercised for real only by the CPU/GPU campaign tickets
    (0263, 0264), which is why its correctness there is a demonstration, not
    a unit-tested contract.

    Known limitation, stated rather than hidden: transformers.js's public
    pipeline API does not expose which ONNX Runtime execution provider a
    session actually bound (`verification/probes/device-auto-probe.mjs`
    confirms only success/failure, not the provider). Where `device` is a
    concrete request (`cpu`), the selected device equals the requested one by
    construction. Where it is `auto`, this executor reports the requested
    value with an explicit caveat rather than fabricating an observation —
    ticket 0264's exit criterion ("`auto` on padme is observed to select a
    GPU provider") is exactly the gap this leaves for a host that has one.
    """

    pkg_root: Path
    cache_dir: Path
    node_bin: str = "node"
    python_bin: str = sys.executable
    hf_token: str | None = None
    #: The "same-item" recall task's item/ord files (ticket 0037, `vec_task_recall.mjs`'s
    #: own header). Not shipped in this repo — the real corpus lives on the author's
    #: machine (CLAUDE.md's Environment notes) — so a recall cell without these two set
    #: resolves as unloadable rather than crashing on a missing argument.
    recall_items_path: Path | None = None
    recall_ords_path: Path | None = None
    #: Where a fidelity cell's raw vectors are persisted, keyed by (model, fidelity
    #: driver version) — ticket 0263: they are experiment X8's CPU side (SPEC.md §5.3),
    #: and ticket 0264's GPU side reads the same convention to score one arm's vectors
    #: against the other's. Must stay addressable after scoring, not discarded with a
    #: tmp dir. `None` keeps the old ephemeral-tmp-dir behaviour (the sole path any
    #: test exercises).
    vectors_dir: Path | None = None
    #: Ticket 0263's floor, shared by the 0264 GPU arm so both sides sample the SAME
    #: 600 rows: prior fidelity runs (nomic) used 600 rows; the driver's own default
    #: is 400. A named field rather than a literal in the cmd below so a caller can
    #: see and override what a campaign actually asked for. The stride
    #: `quant_fidelity.mjs` samples with is a pure function of (corpus length, rows),
    #: so two arms against the byte-identical corpus file at the same row count see
    #: the identical rows with no separate coordination.
    fidelity_rows: str = "600"
    #: The device `resolve()`'s fp16 probe (below) actually tests against. Loadability
    #: for every other rung in this campaign's floor is a published-file fact; fp16 is
    #: the one rung where "the file exists" and "the session will init" can disagree
    #: (ticket 0240's tracker: a graph-fusion failure on the ONNX CPU provider, not a
    #: missing kernel), and that disagreement is device-specific. `resolve()` itself
    #: takes no device parameter (the Protocol other tests build against, and the
    #: 0262 fake executor's signature, both fix it at two arguments) — so the device
    #: to probe is configured here instead, once, at executor construction. The 0264
    #: GPU arm passes 'auto' or 'cuda' here; on that host the probe is a NECESSARY
    #: condition, not sufficient — fp16 session init there is nondeterministic (the
    #: same bytes at the same device sometimes load, sometimes fail with this exact
    #: signature; verification/DEVICE-AUTO-0264.md), so a single probe pass can mark a
    #: cell loadable that a later real run still fails. `_measure_cost`/`_measure_fidelity`
    #: below stay crash-tolerant for exactly that reason: the probe narrows the field,
    #: it does not replace catching a failure where it actually happens.
    probe_device: str = "cpu"

    def engine_versions(self) -> dict[str, str]:
        return {pkg: read_package_version(self.pkg_root, pkg) for pkg in ENGINE_PACKAGES}

    def resolve(self, record: dict, dtype: str) -> ResolveResult:
        files = (record.get("availability", {}).get("dtypes") or {}).get(dtype)
        if not files:
            return ResolveResult(
                loadable=False,
                reason=f"{dtype} is not in {record['id']}'s published dtype listing",
            )
        rel_path = files[0]
        headers = {"User-Agent": "search-works-for-zotero/0262"}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        url = (
            f"https://huggingface.co/{urllib.parse.quote(record['hf_repo'], safe='/')}"
            f"/resolve/main/{rel_path}"
        )
        dest = self.cache_dir / slug(record["hf_repo"]) / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        # Download first, then measure (Action 5): the file lands on disk here,
        # never inside a timed measurement window, and the hash is computed
        # from the same bytes that were written — not re-read separately,
        # which would let a truncated file hash "successfully".
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response, open(dest, "wb") as out:
                while chunk := response.read(1 << 20):
                    digest.update(chunk)
                    out.write(chunk)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            return ResolveResult(loadable=False, reason=f"download failed: {error}")
        if dtype == "fp16":
            probe_error = self._probe_fp16_loadable(record)
            if probe_error:
                return ResolveResult(
                    loadable=False,
                    onnx_path=rel_path,
                    onnx_hash=digest.hexdigest(),
                    reason=(
                        f"fp16 is published but fails at ONNX session init on "
                        f"{self.probe_device} (ticket 0240's known case): {probe_error}"
                    ),
                )
        return ResolveResult(loadable=True, onnx_path=rel_path, onnx_hash=digest.hexdigest())

    def _probe_fp16_loadable(self, record: dict) -> str:
        """Empty string means the session loaded; anything else is the tail of stderr.

        One extra subprocess per (model, fp16) plan, scoped to fp16 alone: every other
        dtype in the campaign floor has already proven loadable across the field, and
        fp16 is the one rung `resolve()`'s file-listing check cannot tell apart from a
        genuine load failure. `--reps 1` keeps the probe to one model load plus one
        query — the cheapest real exercise of session init the existing driver offers.
        """
        with _tmp_json() as out_path:
            cmd = [
                self.node_bin,
                str(BENCH / "query_embed_cost.mjs"),
                "--pkg-root",
                str(self.pkg_root),
                "--models",
                record["id"],
                "--dtype",
                "fp16",
                "--device",
                self.probe_device,
                "--reps",
                "1",
                "--output",
                str(out_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                return result.stderr[-2000:] or "non-zero exit, no stderr captured"
        return ""

    def measure(
        self,
        record: dict,
        dtype: str,
        device: str,
        corpus: str,
        kind: str,
        resolved: ResolveResult,
        rep: int,
    ) -> MeasureResult:
        if kind == "cost":
            return self._measure_cost(record, dtype, device)
        if kind == "fidelity":
            return self._measure_fidelity(record, dtype, device, corpus)
        if kind == "recall":
            return self._measure_recall(record, dtype, device, corpus)
        raise ValueError(f"no real measurement wired for kind {kind!r}")

    def _measure_cost(self, record: dict, dtype: str, device: str) -> MeasureResult:
        with _tmp_json() as out_path:
            cmd = [
                self.node_bin,
                str(BENCH / "query_embed_cost.mjs"),
                "--pkg-root",
                str(self.pkg_root),
                "--models",
                record["id"],
                "--dtype",
                dtype,
                "--output",
                str(out_path),
            ]
            if device != "(runtime default)":
                cmd += ["--device", device]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            # The GPU host's WebGPU/Dawn native binding crashes the process on exit --
            # AFTER the driver's own writeFileSync completes (device-auto-probe.mjs,
            # ticket 0264, confirmed the crash is strictly post-output on this host/ORT
            # version). A nonzero returncode is therefore not proof the measurement is
            # bad: check for a valid, complete output file first, on every returncode.
            payload = _read_valid_json(out_path)
            if payload is not None and payload.get("models"):
                entry = payload["models"][0]
                if result.returncode != 0:
                    entry["process_exit_note"] = (
                        f"driver exited {result.returncode} after writing valid output "
                        "(known post-output native-binding crash on this host; see ticket 0264)"
                    )
                device_selected = (
                    device if device != "auto" else f"{device} (requested; ORT provider not introspectable)"
                )
                return MeasureResult(ok=True, device_selected=device_selected, metrics=entry)
            return MeasureResult(ok=False, device_selected=device, metrics={}, error=_subprocess_diagnostic(result))

    def _measure_fidelity(self, record: dict, dtype: str, device: str, corpus: str) -> MeasureResult:
        import quant_fidelity_score as qfs

        crash_notes: list[str] = []
        persistent = self.vectors_dir is not None
        tmp_ctx = None
        if persistent:
            self.vectors_dir.mkdir(parents=True, exist_ok=True)
            # Keyed by (model, fidelity driver version), not by dtype: the fp32
            # reference is the SAME file every dtype cell of this model needs, so one
            # prefix shared across all of a model's fidelity cells is what lets the
            # cache below actually be a cache. A driver-version bump changes the
            # prefix, so it invalidates persisted vectors the same way it already
            # invalidates a result cell's path — no separate migration step.
            prefix = str(self.vectors_dir / f"{record['id']}__fidelity-v{KIND_DRIVER_VERSION['fidelity']}")
        else:
            tmp_ctx = _tmp_prefix()
            prefix = tmp_ctx.__enter__()
        try:
            for rung in ("fp32", dtype):
                rung_f32 = Path(f"{prefix}-{rung}.f32")
                rung_json = Path(f"{prefix}-{rung}.json")
                # fp32 is every dtype cell's reference (Action 2), including its own
                # fp32-vs-itself control cell. Persisted, it is embedded once per
                # model rather than once per dtype cell -- q8, uint8 and the fp32
                # control would otherwise each re-embed the whole corpus at fp32 for
                # nothing but a reference the previous cell already produced.
                if persistent and rung == "fp32" and rung_f32.exists() and rung_json.exists():
                    continue
                cmd = [
                    self.node_bin,
                    str(BENCH / "quant_fidelity.mjs"),
                    "--pkg-root",
                    str(self.pkg_root),
                    "--corpus",
                    corpus,
                    "--out-prefix",
                    f"{prefix}-{rung}",
                    "--model",
                    record["id"],
                    "--dtype",
                    rung,
                    "--rows",
                    self.fidelity_rows,
                ]
                # Ticket 0481: this flag was missing entirely until this fix, so every
                # fidelity cell silently ran quant_fidelity.mjs's own default device
                # (transformers.js's Node DEFAULT_DEVICE is 'cpu' -- devices.js) no
                # matter what the plan requested. That is the root cause behind both
                # 0264's throughput anomaly (every "GPU arm" fidelity figure was
                # actually a CPU rate) and its byte-identical X8 verdict (both arms ran
                # the same CPU code path). See verification/GPU-ANOMALY-0481.md.
                if device != "(runtime default)":
                    cmd += ["--device", device]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                # Crash tolerance (ticket 0264): the padme GPU host's native-binding
                # exit crash can kill the process AFTER quant_fidelity.mjs's own
                # writeFileSync completes. Check the rung's output for validity BEFORE
                # trusting the return code, on every returncode -- salvages a
                # post-output crash as measured (with a process_exit_note) while a
                # genuine pre-output crash (session-init or mid-execution) still
                # reports the real diagnostic instead of a generic "missing" message.
                rung_meta = _read_valid_json(rung_json)
                if rung_meta is None or not rung_f32.is_file():
                    return MeasureResult(
                        ok=False, device_selected=device, metrics={}, error=_subprocess_diagnostic(result)
                    )
                if result.returncode != 0:
                    crash_notes.append(
                        f"{rung}: driver exited {result.returncode} after writing valid output "
                        "(known post-output native-binding crash on this host; see ticket 0264)"
                    )
            reference = qfs.load_rung(Path(prefix), "fp32")
            rung_data = qfs.load_rung(Path(prefix), dtype)
            if reference is None or rung_data is None:
                return MeasureResult(ok=False, device_selected=device, metrics={}, error="rung file missing")
            ref_vectors, _ = reference
            vectors, meta = rung_data
            metrics = qfs.compare(ref_vectors, vectors, k=30)
            metrics["ms_per_passage"] = meta["ms_per_passage"]
            metrics["rows"] = meta["rows"]
            metrics["dim"] = meta["dim"]
            metrics["corpus_stride"] = meta["stride"]
            if crash_notes:
                metrics["process_exit_note"] = "; ".join(crash_notes)
            if persistent:
                metrics["vectors"] = {
                    "reference_f32": f"{prefix}-fp32.f32",
                    "reference_meta": f"{prefix}-fp32.json",
                    "rung_f32": f"{prefix}-{dtype}.f32",
                    "rung_meta": f"{prefix}-{dtype}.json",
                }
        finally:
            if tmp_ctx is not None:
                tmp_ctx.__exit__(None, None, None)
        return MeasureResult(ok=True, device_selected=device, metrics=metrics)

    def _measure_recall(self, record: dict, dtype: str, device: str, corpus: str) -> MeasureResult:
        """Recall at the DEPLOYED dtype (ticket 0240's tracker), not fp32-fidelity
        as a proxy for it: embed the corpus once at `dtype` with
        `quant_fidelity.mjs`, then score same-item retrieval on those vectors
        with `vec_task_recall.mjs`. Ticket 0265 supplies the real item/ord
        files; without them this reports a MeasureResult the caller should not
        expect — construct the executor with `recall_items_path`/
        `recall_ords_path` before driving a real recall cell.
        """
        if self.recall_items_path is None or self.recall_ords_path is None:
            return MeasureResult(
                ok=False,
                device_selected=device,
                metrics={},
                error="recall needs recall_items_path and recall_ords_path (ticket 0265's corpus)",
            )
        with _tmp_prefix() as prefix, _tmp_json() as out_path:
            embed_cmd = [
                self.node_bin,
                str(BENCH / "quant_fidelity.mjs"),
                "--pkg-root",
                str(self.pkg_root),
                "--corpus",
                corpus,
                "--out-prefix",
                f"{prefix}-{dtype}",
                "--model",
                record["id"],
                "--dtype",
                dtype,
            ]
            if self.fidelity_rows is not None:
                embed_cmd += ["--rows", str(self.fidelity_rows)]
            # Ticket 0481: same missing forward as _measure_fidelity above, same fix.
            if device != "(runtime default)":
                embed_cmd += ["--device", device]
            result = subprocess.run(embed_cmd, capture_output=True, text=True, timeout=1800)
            if result.returncode != 0:
                return MeasureResult(ok=False, device_selected=device, metrics={}, error=result.stderr[-4000:])
            meta = json.loads(Path(f"{prefix}-{dtype}.json").read_text(encoding="utf-8"))
            recall_cmd = [
                self.node_bin,
                str(BENCH / "vec_task_recall.mjs"),
                "--f32",
                f"{prefix}-{dtype}.f32",
                "--dim",
                str(meta["dim"]),
                "--name",
                f"{record['id']}-{dtype}",
                "--items",
                str(self.recall_items_path),
                "--ords",
                str(self.recall_ords_path),
                "--output",
                str(out_path),
            ]
            result = subprocess.run(recall_cmd, capture_output=True, text=True, timeout=1800)
            if result.returncode != 0:
                return MeasureResult(ok=False, device_selected=device, metrics={}, error=result.stderr[-4000:])
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        return MeasureResult(ok=True, device_selected=device, metrics=payload["models"][0])


class _tmp_json:
    def __enter__(self):
        import tempfile

        self._fd, name = tempfile.mkstemp(suffix=".json")
        os.close(self._fd)
        self.path = Path(name)
        return self.path

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


class _tmp_prefix:
    def __enter__(self):
        import tempfile

        self._dir = tempfile.mkdtemp(prefix="sweep-fidelity-")
        return str(Path(self._dir) / "rung")

    def __exit__(self, *exc):
        import shutil

        shutil.rmtree(self._dir, ignore_errors=True)


# --------------------------------------------------------------------- runner


@dataclass
class SweepStats:
    measured: int = 0
    skipped: int = 0
    duplicate: int = 0
    unloadable: int = 0
    failed: int = 0
    events: list[str] = field(default_factory=list)

    def total(self) -> int:
        return self.measured + self.skipped + self.duplicate + self.unloadable + self.failed


def write_result(path: Path, record: dict) -> None:
    """Atomic: a process killed mid-write leaves the old file or nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_result(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _hash_key(kind: str, driver_version: str, onnx_hash: str) -> tuple[str, str, str]:
    """Scoped to (kind, driver_version): a driver-version bump forces every
    cell of that kind to re-measure even where the ONNX bytes are unchanged
    -- the bump means the measurement LOGIC changed, not the model, and
    deduplicating across it would silently defeat the bump. Dedup is for two
    registry entries whose resolved file is the SAME bytes at the SAME
    driver version (nomic's q8/int8 collision, ticket 0240's tracker).
    """
    return (kind, driver_version, onnx_hash)


def _existing_hash_index(results_dir: Path) -> dict[tuple[str, str, str], str]:
    """(kind, driver_version, onnx_hash) -> cell_id, from every already-measured
    result on disk.

    Read at the start of every run, not only accumulated in-memory during it,
    so dedup works across a resumed sweep and not merely within one process.
    """
    index: dict[tuple[str, str, str], str] = {}
    if not results_dir.is_dir():
        return index
    for path in results_dir.glob("*.json"):
        record = read_result(path)
        if record and record.get("status") == "measured" and record.get("onnx_hash"):
            key = _hash_key(record.get("kind", ""), record.get("driver_version", ""), record["onnx_hash"])
            index.setdefault(key, record.get("cell_id", path.stem))
    return index


def _aggregate_reps(kind: str, measurements: list[MeasureResult]) -> dict:
    """Median + spread for repeated RSS cells; the raw single metrics otherwise.

    Action 6: every RSS cell is repeated over five fresh processes, median
    with spread. `spread_mb` is max - min, matching the way the tracker's own
    numbers are already reported ("median 234,2 MB, spread 6,6").
    """
    if kind != "cost" or len(measurements) == 1:
        return dict(measurements[-1].metrics)
    rss = [m.metrics.get("rss_delta_mb") for m in measurements if m.metrics.get("rss_delta_mb") is not None]
    merged = dict(measurements[-1].metrics)
    if rss:
        merged["rss_delta_mb_median"] = round(statistics.median(rss), 1)
        merged["rss_delta_mb_spread"] = round(max(rss) - min(rss), 1)
        merged["rss_delta_mb_reps"] = rss
    return merged


def run_sweep(
    plans: list[CellPlan],
    results_dir: Path,
    executor: CellExecutor,
    registry_by_id: dict[str, dict],
    *,
    reps_by_kind: dict[str, int] | None = None,
) -> SweepStats:
    """Run every planned cell not already on disk. Idempotent: a second call
    over the same plans, results_dir and registry does no new work at all.
    """
    reps_by_kind = reps_by_kind or KIND_REPS
    stats = SweepStats()
    hash_index = _existing_hash_index(results_dir)
    engine_versions = executor.engine_versions()

    for plan in plans:
        path = cell_path(results_dir, plan)
        if path.exists():
            stats.skipped += 1
            stats.events.append(f"skip {plan.cell_id}")
            continue

        record = registry_by_id.get(plan.model)
        if record is None:
            raise KeyError(f"{plan.model} is not in the registry passed to run_sweep")

        resolved = executor.resolve(record, plan.dtype)
        if not resolved.loadable:
            write_result(
                path,
                _base_record(plan, engine_versions, record)
                | {"status": "unloadable", "reason": resolved.reason},
            )
            stats.unloadable += 1
            stats.events.append(f"unloadable {plan.cell_id}: {resolved.reason}")
            continue

        hash_key = _hash_key(plan.kind, plan.driver_version, resolved.onnx_hash) if resolved.onnx_hash else None
        owner = hash_index.get(hash_key) if hash_key else None
        if owner is not None and owner != plan.cell_id:
            write_result(
                path,
                _base_record(plan, engine_versions, record)
                | {
                    "status": "duplicate",
                    "onnx_hash": resolved.onnx_hash,
                    "onnx_path": resolved.onnx_path,
                    "duplicate_of": owner,
                },
            )
            stats.duplicate += 1
            stats.events.append(f"duplicate {plan.cell_id} == {owner}")
            continue
        if hash_key:
            hash_index[hash_key] = plan.cell_id

        reps = reps_by_kind.get(plan.kind, 1)
        measurements = [
            executor.measure(record, plan.dtype, plan.device, plan.corpus, plan.kind, resolved, rep)
            for rep in range(reps)
        ]
        if not all(m.ok for m in measurements):
            failure = next(m for m in measurements if not m.ok)
            write_result(
                path,
                _base_record(plan, engine_versions, record)
                | {
                    "status": "failed",
                    "onnx_hash": resolved.onnx_hash,
                    "onnx_path": resolved.onnx_path,
                    "error": failure.error,
                },
            )
            stats.failed += 1
            stats.events.append(f"failed {plan.cell_id}: {failure.error[:200]}")
            continue

        write_result(
            path,
            _base_record(plan, engine_versions, record)
            | {
                "status": "measured",
                "onnx_hash": resolved.onnx_hash,
                "onnx_path": resolved.onnx_path,
                "n_reps": reps,
                "device_selected": measurements[-1].device_selected,
                "metrics": _aggregate_reps(plan.kind, measurements),
            },
        )
        stats.measured += 1
        stats.events.append(f"measured {plan.cell_id}")

    return stats


def _base_record(plan: CellPlan, engine_versions: dict[str, str], record: dict) -> dict:
    """The fields every result file carries, whatever its status.

    `normalize`/`pooling`/`input_template` are copied from the registry
    record at write time — a change to the registry after a cell is
    measured does not retroactively rewrite an already-written result,
    which is the point of a resumable harness keeping its own record.
    """
    return {
        "cell_id": plan.cell_id,
        "model": plan.model,
        "dtype": plan.dtype,
        "device_requested": plan.device,
        "corpus": plan.corpus,
        "kind": plan.kind,
        "driver": KIND_DRIVER[plan.kind],
        "driver_version": plan.driver_version,
        "measured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        # The GPU arm and the CPU arm are otherwise identical on paper (same corpus,
        # same probes, same driver, ticket 0240's invariant) -- the host is the one
        # fact that tells them apart on the page, and it lived only nested inside a
        # cost cell's own `machine` sub-object (never a fidelity cell's) before this.
        "host": socket.gethostname(),
        "engine_versions": engine_versions,
        "input_template": record.get("input_template"),
        "pooling": record.get("pooling"),
        "normalize": record.get("normalize"),
    }


# -------------------------------------------------------------------- report


def sweep_report(
    plans: list[CellPlan],
    results_dir: Path,
    *,
    current_engine_versions: dict[str, str] | None = None,
) -> dict:
    """Read what exists, report what is missing, never raise on a gap.

    Action 10: the scorer reads what exists and reports the rest as missing
    rather than failing or silently reporting a short table.
    """
    by_status: dict[str, list[str]] = {"measured": [], "duplicate": [], "unloadable": [], "failed": []}
    missing: list[str] = []
    mismatches: list[dict] = []
    for plan in plans:
        path = cell_path(results_dir, plan)
        if not path.exists():
            missing.append(plan.cell_id)
            continue
        record = read_result(path)
        if record is None:
            # Present but unreadable is its own finding, not a silent miss.
            missing.append(f"{plan.cell_id} (unreadable result file)")
            continue
        status = record.get("status", "unknown")
        by_status.setdefault(status, []).append(plan.cell_id)
        if current_engine_versions and status == "measured":
            recorded = record.get("engine_versions", {})
            for package, version in current_engine_versions.items():
                if recorded.get(package) not in (None, version):
                    mismatches.append(
                        {
                            "cell_id": plan.cell_id,
                            "package": package,
                            "recorded": recorded.get(package),
                            "running": version,
                        }
                    )
    return {
        "planned": len(plans),
        "missing": missing,
        "engine_version_mismatches": mismatches,
        **by_status,
        "counts": {"missing": len(missing), **{k: len(v) for k, v in by_status.items()}},
    }


# ------------------------------------------------------------------------ cli


def read_hf_token(keyfile: Path) -> str | None:
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    if not keyfile.is_file():
        return None
    for line in keyfile.read_text(encoding="utf-8").splitlines():
        match = re.match(r"""\s*(?:export\s+)?HF_TOKEN\s*=\s*["']?([^"'\s]+)""", line)
        if match:
            return match.group(1)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path, default=BENCH / "models.json")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--pkg-root", type=Path, help="dir with node_modules/@huggingface/transformers")
    parser.add_argument("--onnx-cache-dir", type=Path, help="where resolved ONNX files are downloaded")
    parser.add_argument(
        "--vectors-dir",
        type=Path,
        help="persist fidelity-cell raw vectors here, keyed by (model, driver version); "
        "omit to keep the old ephemeral-tmp-dir behaviour",
    )
    parser.add_argument("--fidelity-rows", default="600", help="rows quant_fidelity.mjs samples per fidelity cell")
    parser.add_argument("--probe-device", default="cpu", help="device resolve()'s fp16 loadability probe tests")
    parser.add_argument("--models", help="comma-separated registry ids; default every candidate")
    parser.add_argument("--dtypes", default="fp32,fp16,q8,uint8")
    parser.add_argument("--devices", default="cpu")
    parser.add_argument("--kinds", default="cost,fidelity")
    parser.add_argument("--fidelity-corpus", type=Path, help="passages file for the fidelity kind")
    parser.add_argument("--recall-corpus", type=Path, help="passages file for the recall kind")
    parser.add_argument("--recall-items", type=Path, help="item-id-per-line file (ticket 0265's corpus)")
    parser.add_argument("--recall-ords", type=Path, help="chunk-ordinal-per-line file (ticket 0265's corpus)")
    parser.add_argument("--report", action="store_true", help="print a report instead of running")
    parser.add_argument("--keyfile", type=Path, default=Path.home() / ".config/keys/huggingface.env")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    registry = load_registry(args.registry)
    registry_by_id = {m["id"]: m for m in registry["models"]}
    models = args.models.split(",") if args.models else None
    kinds = tuple(args.kinds.split(","))
    corpora = {}
    if "fidelity" in kinds:
        if not args.fidelity_corpus:
            raise SystemExit("--kinds includes fidelity: pass --fidelity-corpus")
        corpora["fidelity"] = str(args.fidelity_corpus)
    if "recall" in kinds:
        if not args.recall_corpus:
            raise SystemExit("--kinds includes recall: pass --recall-corpus")
        corpora["recall"] = str(args.recall_corpus)
    plans = plan_cells(
        registry,
        models=models,
        dtypes=tuple(args.dtypes.split(",")),
        devices=tuple(args.devices.split(",")),
        corpora=corpora,
        kinds=kinds,
    )

    if args.report:
        report = sweep_report(plans, args.results_dir)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if not args.pkg_root:
        raise SystemExit("running a sweep needs --pkg-root")
    executor = RealExecutor(
        pkg_root=args.pkg_root,
        cache_dir=args.onnx_cache_dir or (args.results_dir / "onnx-cache"),
        hf_token=read_hf_token(args.keyfile),
        recall_items_path=args.recall_items,
        recall_ords_path=args.recall_ords,
        vectors_dir=args.vectors_dir,
        fidelity_rows=args.fidelity_rows,
        probe_device=args.probe_device,
    )
    stats = run_sweep(plans, args.results_dir, executor, registry_by_id)
    logger.info(
        "measured=%d skipped=%d duplicate=%d unloadable=%d failed=%d (of %d planned)",
        stats.measured,
        stats.skipped,
        stats.duplicate,
        stats.unloadable,
        stats.failed,
        stats.total(),
    )
    for event in stats.events:
        logger.info("  %s", event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
