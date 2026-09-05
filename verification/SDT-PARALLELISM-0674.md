# SDT on padme: GPU, CPU threads, and parallel documents

Measured 2026-09-05; ticket 0674.

**Parallel documents improve throughput on this pilot. More ONNX CPU threads
do not improve total extraction time. CUDA does not improve inference latency
on the captured document. These observations do not establish a production
worker count or decide a Rust rewrite.**

## Successful extraction measurements

The serial table sums the per-document median warm extraction times. It covers
the real attachment `GMAP993G` and the public document-worker fixtures listed
in `bench/results/0674-sdt-padme/provenance.json`. Model loading is excluded
from these warm times; `getStructure` is timed, including PDF parsing and SDT
construction, but excluding input file reads, output JSON serialization and pack
compression. Each process warms up once and then measures five extractions.

| Runtime | Sum of median extraction times (s) |
|---|---:|
| WASM, one thread | 6,32 |
| Native CPU, one thread | 4,87 |
| Native CPU, two threads | 4,93 |
| Native CPU, four threads | 4,91 |
| Native CPU, eight threads | 5,47 |

WASM and native CPU use different ONNX Runtime versions, pinned in provenance.
Their comparison includes that runtime change. The native CPU thread arms use
the same runtime, graph optimization and PDF pipeline; inter-op threads stay
fixed while intra-op threads vary.

The batch table measures the same document sequence repeated three times,
partitioned by stride between independent processes. Each configuration has
three timed trials; the table reports the median whole-batch wall time.
It includes process startup, model loading, document reads and instrumented
JSON output. The workload totals **849 pages**. Files are warm in the OS cache.

| Processes | Batch time (s) | Speedup over one process |
|---:|---:|---:|
| 1 | 16,54 | 1,00× |
| 2 | 11,18 | 1,48× |
| 4 | 8,43 | 1,96× |
| 8 | 6,23 | 2,65× |
| 12 | 4,49 | 3,69× |

All successful WASM, native CPU thread, and batch arms return exactly the same
structured JSON for each input after normalizing only `metadata.dateCreated`.
The summary checks every extraction digest, not just the final run. The
instrument rejects session errors and runs that silently bypass every model.
This is output preservation on the tested documents, not an audit of whether
their headings, references and tables are semantically correct.

The batch is small and unevenly partitioned: a long document can leave other
processes idle. This is a demonstrated gain with the existing JavaScript
extractor, not the ceiling of balanced scheduling. Process memory is recorded
in the raw evidence, but simultaneous peak memory was not measured.

## GPU control

The full Node CUDA arm completed extraction with matching JSON on `GMAP993G`,
then aborted with `corrupted double-linked list`. Its measurements and log are
kept under `failed-node-cuda/` as diagnostic evidence, **not a successful
end-to-end GPU result**. Serializing session creation and explicitly releasing
sessions did not resolve the problem. The newer native Node package attempted
during setup needed an unavailable CUDA library and was not admitted as a
measurement; the driver now rejects this kind of silent extraction fallback.

An independent Python ONNX Runtime replay then consumed the exact real tensors
captured from the WASM extraction, using identical model bytes for CPU and CUDA.
It prebuilds input arrays and times session execution including output return
to host memory. Each arm excludes its first replay and reports the median of
the subsequent five. Both arms and a separate CUDA profiling run exited cleanly.

| Tensor replay backend | Median inference time (ms) |
|---|---:|
| CPU | 69,50 |
| CUDA | 80,97 |

The separate ONNX profiles confirm actual CUDA execution, with some shape
operations on CPU. Raw compressed profiles and their provider summary are
included. GPU logits differ numerically from WASM, with maximum absolute
differences recorded in the replay JSON; no numerical acceptance threshold is
inferred. The replay cannot prove end-to-end semantic equivalence on other
documents, nor predict GPU throughput after batching pages across documents.

## Scope and provenance

- Host, CPU, GPU, driver, runtime versions, model hashes and source/submodule
  commits are in `bench/results/0674-sdt-padme/provenance.json`.
- The source is document-worker commit `8fb70af4000873561c82b2f4eb88be190efb9979`.
  It is newer than the installed Zotero extractor. Every model hash matches
  the installed model, but the surrounding processor differs. These are
  isolated source-level experiments, not Zotero desktop throughput measurements.
- Only the ONNX runtime adapter was replaced in the isolated source checkout.
  Its model-creation queue is serialized; the warm trials exclude that cost.
- The author authorized temporarily suspending `llama-server`. SIGSTOP prevented
  concurrent work during the final CPU campaign and Python replay; SIGCONT ran
  in cleanup and the resumed process was verified. GPU memory stayed allocated.
- Zotero documents were read directly; no API mutation or cache write occurred.
  Text-bearing structure files and tensor captures remain on padme and are not
  committed. The evidence contains hashes and timings.
- The zoteus catch-up command completed and reported upstream movement; this
  probe depends on the separately pinned document-worker source and does not
  update the zoteus review baseline.

## Installed Zotero queue

The installed `chrome/content/zotero/xpcom/pdfWorker/manager.js` uses a
singleton `Zotero.PDFWorker`, one `Worker(WORKER_URL)`, and a queue loop that
awaits each task before taking the next. `getStructuredDocumentText()` enters
that queue. `sdt.js` separately deduplicates in-flight generations per item.
Exact installed file hashes and source anchors are in `queue-provenance.json`.

A bounded extraction-worker pool is therefore a concrete candidate for a
Zotero patch. It must preserve interactive priority, per-item deduplication,
error routing and resource limits. The pilot does not measure that patch:
its parallel arm uses native ONNX and independent Node processes, while Zotero
uses Web Workers and WASM. Neither simply launching more promises into the
existing queue nor replacing its serial loop alone establishes safe parallelism.
No upstream patch, filing or design ruling is part of this measurement.

## Reproduction

In an isolated checkout at the recorded document-worker SHA, initialize its
submodules, run `npm ci --ignore-scripts` and `bash scripts/build-assets`.
Copy `verification/probes/sdt_onnx_runtime.mjs` over
`src/pdf/structure/model/onnx/runtime.js`; copy
`verification/probes/sdt_gpu_extract.mjs` to `probe.mjs` at the checkout root.
The driver must start with `node --import ./scripts/pdfjs-setup.js` so the
PDF.js resolver is installed before importing its modules.

Run `verification/probes/sdt_cpu_campaign.py` from that checkout, supplying
`--output`, `--real-pdf` and `--ort-path` (the native ONNX Node package directory).
`--pause-pid` is optional and must identify an authorized llama-server process.
It resumes the process in `finally`. Do not run competing measurements.

For the GPU control, set `SDT_BACKEND=wasm` and `SDT_CAPTURE` to a private V8
capture path, then run `probe.mjs PDF OUTPUT_JSON 0`. Convert that capture with
`verification/probes/sdt_capture_json.mjs INPUT OUTPUT`. In a Python environment
with the recorded ONNX Runtime GPU version and NumPy, run
`verification/probes/sdt_onnx_replay.py CAPTURE_JSON OUTPUT_JSON --backend cpu`
and then `--backend cuda`. Set CUDA visibility and the cuDNN library path as
needed. Use `--profile-dir` in a separate run, keeping profiling overhead out
of the timed comparison. `sdt_onnx_replay.mjs` preserves the failed Node control.

Keep only timing JSON, provenance and profiles in the public evidence directory.
Recompute the summary with `verification/probes/sdt_summarize.py RESULTS_DIR`.

## Rust scope, counted rather than estimated

At the same source commit, the structuring subtree contains **15 674 physical
lines** and the SDT format subtree **5 036 physical lines**; comments and blanks
are included. `source-counts.json` also records the PDF adapter and the much
larger PDF.js source tree. Those totals are not estimates of a Rust port:
an existing native PDF engine could replace some of the logic, and the parser
includes rendering code irrelevant to extraction. No Rust implementation or
parser choice is ratified by this probe.
