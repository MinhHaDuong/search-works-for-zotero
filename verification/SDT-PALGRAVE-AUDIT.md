# Palgrave SDT: large-document code audit

Date: 2026-09-05. Read-only audit of the installed application, not a
successful Palgrave SDT extraction and not a new design decision.

## Verdict

There is no identified whole-document string-size blocker in the PDF-to-pack
serialization path. It serializes individual top-level blocks, not the entire
content tree as one JSON string. This is reassuring but does not clear Palgrave:
the whole structured document is retained before packing, the bibliography
analysis has a document-wide multiplicative scan, and failures that kill the
worker can strand the shared queue.

Do not use the production Palgrave attachment as the first diagnostic fixture.
A successful full-text extraction does not validate the additional SDT phases.
The prior source/cache measurements belong to
`bench/results/index-sitter-2026-09-05/summary.json`; they do not determine SDT
heap usage, compressed size, block size or bibliography count.

## Exact inspected artifacts

All line anchors below refer to members of `/opt/zotero7/app/omni.ja`, not
unverified upstream HEAD. Reproduce a view with `unzip -p` and `nl -ba`.

| Member | SHA-256 |
|---|---|
| `resource/document-worker/worker.js` | `070610cc62ba6ff01feb059d12ecb155dc0b6a810f0dfd36074b2eaf21aee231` |
| `resource/document-worker/structured-document-text.js` | `340f44fea8d616eaac04b83ef6329eaad2753916b1d50342a8edc7a0b717bed4` |
| `chrome/content/zotero/xpcom/pdfWorker/manager.js` | `eebf3542754a833d0e05ce56818790a177d8e69b7c69bfd6f3b6d73898f5e1ae` |

The service identity and installed processor metadata are already recorded in
`bench/results/sdt-prerequisites-2026-09-05/service-contract.json`.
The worker bundle includes original module-path comments, allowing the anchors
below to be mapped back to document-worker and structured-document-text source.

## Strings, arrays and pack-format limits

The following are source constants and source-derived bounds, not proposed
sitter thresholds or new measurements.

- `worker.js:164675`, module `structured-document-text/src/pack/write.js`:
  raw content chunks target 32 KiB. A block larger than the target is placed in
  its own chunk, not split. The 64 KiB oversized-block condition only warns.
- `worker.js:164717`: `JSON.stringify(block)` and UTF-8 encoding happen for
  each top-level block. Metadata and the entire catalog are separately
  stringified by `deflateJson` at line 164778. There is no stringification of
  `structure.content` as a whole in this writer.
- Consequently, a pathological giant block or giant catalog can still exceed
  the engine's string/allocation limits. The chunk target is NOT a hard bound
  on serialization memory. This audit does not assert an exact SpiderMonkey
  string limit: it did not inspect the matching engine source or exercise
  allocation limits, and a Node/V8 limit would not establish Zotero's limit.
- `worker.js:164335` and `164377`: offsets use checked unsigned integers.
  `MAX_PACK_BYTES = 0xffffffff` at line 164678; both accumulated compressed
  content and final pack length are explicitly rejected above that value.
  The v1 maximum is therefore one byte below 4 GiB, not an unlimited stream.
  ArrayBuffer allocation can fail before the format maximum.
- `worker.js:164763`: the final length check is late, after content compression.
  There is no preflight estimate or incremental pack file. At line 164344 the
  complete output is allocated as a contiguous `Uint8Array`; compressed chunk
  buffers remain live while copied into it.
- The spread in `[...contentChunks]` at line 164772 is an array-literal spread,
  not a function-call argument expansion. It should not be misreported as an
  argument-count overflow.
- Actual function-call spreads exist: outline recovery
  `combined.push(...recoveredItems)` at line 145306, outline unwrapping
  `result.push(...children)` at line 144929, and author-candidate
  `Math.min(...candidates.map(...))` at line 148943. These are conditional
  argument-count/stack risks for very large derived collections, not proof
  that Palgrave reaches them. Geometry min/max spreads elsewhere are mostly
  per-page or per-block, not proportional directly to document page count.

## Memory and execution lifetime

`getFullStructure` at `worker.js:152860` creates document-wide content, page
catalog, link and word collections. It prepares page contexts in batches, but
`appendPageContext` appends every result to `structure.content`. Batch processing
therefore does not bound the retained document size.

After all pages, line 153125 begins global transformations, reference indexes,
citation resolution, outline construction and cleanup. `StructureIndex`
at line 146715 also retains entries/maps referencing blocks. Its default text
cache is disabled (`textCache: 'none'`), which avoids an additional permanent
full-document text cache, but does not release the structure itself.

Only afterward, at line 164941, packing uses `destructive: true`, nulling content
entries as each is serialized. This is a real memory mitigation; it does not
remove the earlier whole-structure peak or force garbage collection. Compressed
chunks and the final contiguous output overlap during assembly.

The manager reads the complete source file and copies it with
`new Uint8Array(buf)` before transferring its buffer (`manager.js:673`). The
transfer avoids another structured-clone copy of that buffer; it does not make
source loading streaming. On return, the SDT service validates bytes and writes
the cache through a temporary path (`sdt.js:285`, `291`, `300`). Its pack reader
copies requested ranges with `ArrayBuffer.slice` (`sdt.js:322`).

No quantitative Palgrave peak-memory estimate is justified from its flat-cache
size alone. Geometry, style, references, JS objects and temporary indexes can
dominate the text bytes. Nor does a modest final compressed pack prove a modest
working set.

## A credible long tail specific to an encyclopedia

`getMentionWindows` (`worker.js:148668`) loops through structure-index block
entries. For each eligible block it calls `isReferenceBlock`
(`worker.js:147987`), which scans `referenceIndex.runs` linearly before its Set
lookup. The resulting worst-case membership work is proportional to blocks
times bibliography runs. It does not become constant-time merely because the
function ends in a Set lookup.

The bounded probe `verification/probes/sdt_reference_membership.mjs` executes
that exact installed function with synthetic nonmatching runs and counts loop
visits. Its assertions confirm the multiplicative count. This is a control-flow
test in Node, not a Zotero timing, heap-limit test or Palgrave extraction.
Reproduce without spawning a subprocess inside Node:

```sh
unzip -p /opt/zotero7/app/omni.ja resource/document-worker/worker.js | node verification/probes/sdt_reference_membership.mjs
```

An encyclopedia with many article bibliographies is a plausible stress case;
the actual detected run count in Palgrave is unmeasured. Additional citation
candidate lists depend on shared author names and years. This supports testing
the global phases independently; it is not a prediction of nontermination.

Inference overload and per-page inference errors have fallback paths rather
than an unconditional abort (`worker.js:143251`, `153043`). Fallback can mark
`extractionDegraded` in the page catalog. A generated pack must therefore not
be presented as evidence that every page received full-quality layout analysis.

## Supervision and failure modes

`reportPageProgress` (`worker.js:152841`) maps page processing into the interval
ending at 90 percent. `createProgressReporter` (`164881`) rounds to whole
percentages and drops non-increasing reports: it is not a per-page heartbeat.
Global transformations after the page loop do not report intermediate progress.
The caller next reports 95 percent after structure creation, then packs
synchronously, and reports 100 percent before the service validates and writes
the cache (`164928`). Long silence near the end is compatible with healthy
work; 100 percent is not persisted completion.

The manager serially awaits each job (`manager.js:53`), without a job timeout
or cancellation token. A caught worker action exception can reject the query
and release that queue position. In contrast, its worker `error` listener only
logs (`manager.js:180`): it does not reject outstanding promises or recreate
the worker. An out-of-memory failure or worker termination may thus strand the
queue. The sitter must not treat a watchdog alarm as permission to enqueue a
duplicate job or terminate Zotero's shared worker.

## Bounded pack round-trip completed

`verification/probes/sdt_pack_roundtrip.mjs` extracts the installed writer
modules and executes the installed reader in a Node VM. Both a many-small-block
structure and an oversized single-block structure round-trip without lost text,
including accented characters, CJK and astral Unicode. Metadata, catalog, all
blocks, last-block/page access and a cross-chunk block range are checked.
Instrumentation verifies that the writer stringifies blocks individually and
nulls the destructive input entries. The oversized block is retained in a
single chunk and warned about, not truncated. Tiny injected accounting inputs
also exercise compressed-content overflow and unsigned-offset rejection
without giant buffers. Raw output:
`bench/results/sdt-diagnostic-2026-09-05/pack-roundtrip.json`.

This uses the writer/reader's compression hooks with Node raw DEFLATE, not the
worker's bundled compressor. It does not execute PDF analysis, emulate Gecko's
allocation limits, measure memory or establish Palgrave's successful completion.
In particular, instrumentation deliberately retains references to serialized
values; it verifies destructive assignment, not garbage collection.

Reproduce in Bash using read-only process-substitution streams:

```sh
node verification/probes/sdt_pack_roundtrip.mjs \
  <(unzip -p /opt/zotero7/app/omni.ja resource/document-worker/worker.js) \
  <(unzip -p /opt/zotero7/app/omni.ja resource/document-worker/structured-document-text.js) \
  <(unzip -p /opt/zotero7/app/omni.ja resource/document-worker/metadata.json)
```

## Bounded tests that would reduce the remaining risk

These are proposals, not work claimed completed by this audit.

- Instrument bibliography membership on synthetic structures while varying
  block and bibliography counts independently. Count comparisons before
  relying on elapsed-time extrapolation; a precomputed top-level membership
  Set is a candidate upstream optimization, not a plugin monkey patch.
- Use disposable extracted Palgrave subsets in an isolated profile, with
  coverage of prose, bibliographies, equations and dense pages. Record
  phase timings, progress gaps, degraded-page flags and memory. Subsets can
  expose page-local failures but cannot establish whole-document scaling.
- Before a full isolated run, add phase instrumentation around the global
  transformations and packing in the diagnostic environment. Admit no other
  jobs; keep the production application/profile out of that process. A
  controlled process-stop fallback protects the experiment, not native
  in-flight cancellation semantics.

No production PDF, cache, preference or application code was changed, and no
Palgrave SDT generation was launched for this audit.
