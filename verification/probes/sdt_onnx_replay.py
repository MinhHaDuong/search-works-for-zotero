"""Replay real SDT tensors with explicit CPU or CUDA; no PDF parser is loaded."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import onnxruntime as ort

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('capture', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--backend', choices=['cpu', 'cuda'], required=True)
parser.add_argument('--profile-dir', type=Path)
args = parser.parse_args()
provider = 'CUDAExecutionProvider' if args.backend == 'cuda' else 'CPUExecutionProvider'
if provider not in ort.get_available_providers():
    raise RuntimeError(f'{provider} unavailable')
options = ort.SessionOptions()
options.intra_op_num_threads = 1
options.inter_op_num_threads = 1
options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
sessions = {}
for model in ['clusterer/model.onnx', 'clusterer/repair.onnx', 'classifier/model.onnx']:
    path = Path('build/block-seg') / model
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.profile_dir:
        args.profile_dir.mkdir(parents=True, exist_ok=True)
        options.enable_profiling = True
        options.profile_file_prefix = str(args.profile_dir / digest)
    session = ort.InferenceSession(str(path), sess_options=options, providers=[provider])
    if provider not in session.get_providers():
        raise RuntimeError(f'{model}: requested provider was not loaded')
    sessions[digest] = session
calls = json.loads(args.capture.read_text())
prepared = []
for call in calls:
    feeds = {key: np.array(value['data'], dtype=value['type']).reshape(value['dims'])
             for key, value in call['feeds'].items()}
    prepared.append((call, feeds))
rows = []
for iteration in range(6):
    total_ms = 0
    by_model = {}
    max_abs_error = 0
    for call, feeds in prepared:
        session = sessions[call['hash']]
        names = call.get('outputNames') or [out.name for out in session.get_outputs()]
        start = time.perf_counter()
        outputs = session.run(names, feeds)
        elapsed = (time.perf_counter() - start) * 1000
        total_ms += elapsed
        by_model[call['hash']] = by_model.get(call['hash'], 0) + elapsed
        for name, output in zip(names, outputs, strict=True):
            expected = np.array(call['outputs'][name]['data']).reshape(output.shape)
            if output.size:
                error = float(np.max(np.abs(output.astype(float) - expected)))
                if not np.isfinite(error):
                    raise RuntimeError('Nonfinite output difference')
                max_abs_error = max(max_abs_error, error)
    rows.append({'iteration': iteration, 'warmup': iteration == 0, 'sumMs': total_ms,
                 'byModel': by_model, 'maxAbsError': max_abs_error})
profiles = [session.end_profiling() for session in sessions.values()] if args.profile_dir else []
args.output.write_text(json.dumps({'backend': args.backend, 'ortVersion': ort.__version__,
                                  'calls': len(calls), 'rows': rows, 'profiles': profiles}, indent=2))
print(json.dumps(rows), flush=True)
