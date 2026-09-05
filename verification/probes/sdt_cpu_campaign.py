"""Run isolated SDT thread and document-process experiments on an equipped host.

Place alongside probe.mjs in the prepared document-worker checkout. No live
Zotero API or cache is written. An optional --pause-pid is resumed in finally.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--real-pdf', required=True)
parser.add_argument('--ort-path', required=True)
parser.add_argument('--pause-pid', type=int)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
fixtures = Path.cwd() / 'test/fixtures/pdf/full'
docs = [args.real_pdf, str(fixtures / 'ethics-in-law-enforcement.pdf'),
        str(fixtures / 'raster-text-flow.pdf'), str(fixtures / 'crs-r48555.pdf')]
env_base = dict(os.environ, SDT_ORT_PATH=args.ort_path)
summary = []


def run(name, backend, threads, pdf=None, manifest=None):
    env = dict(env_base, SDT_BACKEND=backend, SDT_THREADS=str(threads))
    if manifest is not None:
        path = args.output / f'{name}.manifest.json'
        path.write_text(json.dumps(manifest))
        env['SDT_MANIFEST'] = str(path)
    output = args.output / f'{name}.json'
    with (args.output / f'{name}.log').open('w') as log:
        begin = time.perf_counter()
        result = subprocess.run(
            ['node', '--import', './scripts/pdfjs-setup.js', 'probe.mjs',
             pdf or docs[0], str(output), '5'], env=env,
            stdout=log, stderr=subprocess.STDOUT, timeout=600, check=False)
        wall = time.perf_counter() - begin
    if result.returncode:
        raise RuntimeError(f'{name}: exit {result.returncode}; see log')
    return {'name': name, 'backend': backend, 'threads': threads,
            'processWallSeconds': wall, 'exitCode': result.returncode}


def save(row):
    summary.append(row)
    (args.output / 'campaign.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(row), flush=True)


paused = False
try:
    if args.pause_pid:
        if Path(f'/proc/{args.pause_pid}/comm').read_text().strip() != 'llama-server':
            raise RuntimeError('Refusing to signal a process other than llama-server')
        os.kill(args.pause_pid, signal.SIGSTOP)
        paused = True
    for doc_index, pdf in enumerate(docs):
        for backend, threads in [('wasm', 1), ('cpu', 1), ('cpu', 2), ('cpu', 4), ('cpu', 8)]:
            save(run(f'doc{doc_index}-{backend}-t{threads}', backend, threads, pdf=pdf))
    workload = docs * 3
    # Same total work each time. Reverse the order on the middle repetition.
    for repeat in range(3):
        jobs_order = [1, 2, 4, 8, 12]
        if repeat == 1:
            jobs_order.reverse()
        for jobs in jobs_order:
            begin = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
                futures = [pool.submit(run, f'batch-r{repeat}-j{jobs}-w{worker}',
                                       'cpu', 1, manifest=workload[worker::jobs])
                           for worker in range(jobs)]
                workers = [future.result() for future in futures]
            save({'kind': 'batch', 'repeat': repeat, 'jobs': jobs,
                  'wallSeconds': time.perf_counter()-begin, 'workers': workers})
finally:
    if paused:
        os.kill(args.pause_pid, signal.SIGCONT)
        print('llama-server resumed', flush=True)
