# Palgrave SDT: isolated phase and memory measurements

Date: 2026-09-05. Ticket 0676. Evidence, not a production resource policy.

## Outcome

Both progressively larger Palgrave subsets completed through the native SDT
service, persisted readable packs with the requested page coverage, and reported
no degraded pages. The original PDF's digest stayed unchanged. An unmodified
worker control on the smaller identical input produced the same decoded pack
after excluding only its creation date.

The larger subset spent more time in document-wide transformations after page
processing than in the page loop itself. Citation resolution was the largest
instrumented global stage, followed by reference application. Native progress
was silent during those global transformations. This demonstrates a healthy
long progress gap, not a hung job. It does NOT attribute all citation time to
the membership scan identified in `verification/SDT-PALGRAVE-AUDIT.md`.

No full-volume Palgrave extraction was launched. The sparse subset evidence
does not establish that the whole volume fits the chosen experiment memory
cap, and simple linear extrapolation of elapsed time is contradicted by the
observed global-stage growth. Full-volume work remains a separate admission
decision, preferably after profiling the citation phase more narrowly or with
more memory headroom on an isolated host. No out-of-memory event or string-size
failure was observed, and this is not a claim that the complete book would fail.

## Evidence and definitions

Raw results and the mechanically derived numerical summary live exclusively in
`bench/results/sdt-palgrave-phases-2026-09-05/`:

- `pages-256.json` and `pages-1024.json`: instrumented runs, including phase
  timestamps, native progress, cgroup memory samples and verified resource limits.
- `control-256.json`: unmodified-worker control with the same input bytes.
- `summary.json`: phase durations, maximum observed progress gap, scope peak,
  native service elapsed time, and canonical pack comparison.

`ensureSeconds` measures dispatch through native service resolution after cache
persistence, including any queue wait and source preparation inside the service.
`phaseSeconds.pages` is worker page processing, including cold model loading;
`globalAfterPages` spans the end of that loop through the start of packing.
Packing is separately instrumented. Subset construction, application startup
and shutdown are outside `ensureSeconds`, but inside neither the page nor global
stage timings. The overall driver wall time includes application startup and
shutdown, not arena preparation.

Memory is cgroup accounting for the whole experimental process tree and charged
cache, not JavaScript heap or main-process RSS. The probe samples the kernel's
retained peak as well as current usage; this is stronger than a peak of sampled
RSS, but a peak after the last readable sample can still be missed when the
scope disappears. These are cold application/model starts on a working machine,
with filesystem caches not controlled and no repeated-run timing distribution.

The subsets preserve selected PDF pages but are rebuilt with `mutool merge`.
Document-level metadata, outlines and cross-page destinations may differ from
the full source. The smaller prefix is contained in the larger; neither is a
random or representative sample of all encyclopedia entries. The control
compares identical subset bytes, not a rebuilt subset against the original PDF.

## Instrumentation and isolation

`verification/probes/sdt_phase_probe.py` copies the installed app archive and
adds phase messages around exact, uniquely checked statements in its worker.
The original operations remain in order. A private `bwrap` bind overlays that
archive for the experimental process only; the installed application is never
edited. Original and instrumented worker digests, anchor statements and addon
source digests accompany the raw evidence.

The phase harness in `verification/probes/sdt-phase-harness/` listens for those
messages and drives the native `SDT.ensure` method. The diagnostic plugin from
ticket 0675 supplies passive inspection. The native models, WASM backend and
thread selection are unchanged. Instrumentation adds message/report-writing
overhead; the small control agrees on content and has similar elapsed time,
but does not prove zero overhead for larger documents or all phases.

The experimental profile disables native flat-PDF indexing so it does not
compete with SDT. This preference is set only in the new profile. Its synthetic
configuration contains no sync credentials. The application is Zotero 10.0.1;
the historical installation directory name does not identify its version.

The complete experimental process tree is in a user-systemd scope. Memory and
swap limits are read back before accepting them as enforced. A separate host
available-memory check and observation deadline stop only that process group.
No stop guard fired in these runs. The platform did not support the attempted
`MemoryOOMGroup` scope property; it is not used or claimed. Per-scope memory
and swap caps were supported and verified. The emergency stop is an experiment
facility, not native cancellation available to the production sitter.

The host filesystem is read-only inside `bwrap` apart from the fresh arena;
network and process namespaces are separate. Arenas are in the gitignored
`corpus-cache/` on disk, not RAM-backed `/tmp`. Original PDF and real Zotero
profile/cache files are never written. PDFs, generated packs and full application
logs stay in those arenas, not in the committed measurement summaries.

## Reproduction

Use the installed Zotero launcher and original PDF paths for the host under
test. The resource arguments below reproduce the experiment, not sitter defaults.

```sh
python3 verification/probes/sdt_phase_probe.py \
  --application /opt/zotero7/zotero --source /path/to/Palgrave.pdf \
  --key AXE7G67C --pages 1-256 --expected-pages 256 \
  --memory-mib 4096 --min-host-available-mib 2048 --deadline 240
```

Use the larger range and corresponding expected count for the other arm;
`--control` selects the unmodified worker. The printed arena contains `run.json`
and `phases.json`. Then run:

```sh
python3 verification/probes/sdt_phase_summary.py ARENA_SMALL ARENA_LARGE ARENA_CONTROL
```

The summary's independent Python pack reader materializes the resulting subset
packs outside the measured process to compare their content. It is not used
inside extraction and is not a recommendation to materialize a full Palgrave
pack in the sitter. The probe and summary only emit provenance, counts, hashes
and timings, not document text.
