# Index Sitter: live native-indexing probe

Date: 2026-09-05. Ticket: 0672. This report is evidence for the design
discussion, not a ratified requirement or implementation of the sitter.

## Scope and reproduction

The author authorized probing their running Zotero. The installed full-text
control plugin submitted complete native re-extractions of existing attachments.
No source documents, plugin installation, or global preferences were changed.
No cancellation, restart, index clearing, artificial resource exhaustion, or
timeout-triggered retry was performed.

`bench/results/index-sitter-2026-09-05/` holds raw JSONL observations,
`summary.json` holds mechanically derived timing and latency summaries, and
`sdt-metadata.json` holds metadata read from existing structured-text packs.
Numerical results live in those artifacts rather than being duplicated here.

The probe reads cache file sizes, modification times and before/after hashes;
samples the Zotero main process's RSS, CPU ticks and swap; and reads host memory
availability and pressure counters. It concurrently times the plugin status
endpoint and a small native item-list API request. This is HTTP responsiveness,
not GUI latency, lexical-search latency, or total process-tree memory. The host
is the author's working machine, not an isolated benchmark environment.

Run `verification/probes/index_sitter_live.py inspect --pid PID --data-dir DIR`
to inspect candidates and resources. Run `run` with the same arguments plus
`--key KEY --output NEW_JSONL --observe-seconds SECONDS` to submit a reindex.
The output path must not exist. The observation deadline does not cancel the
job. The plugin's busy flag is global, so another job can delay observation of
idle after this target's cache changes.

The committed instrument is the executed temporary instrument with formatting,
an unused SQLite helper removed, explicit PID/data-directory arguments, and a
file-handle context manager. Its sampling and dispatch logic are unchanged.
The initial read-only database query failed with `database is locked`; the
probe did not bypass the lock or copy a live database and WAL. It used the API
and cache files instead. The reserved `snapshot.rows` field is therefore null.

Sampling sleeps between completed request pairs, so it is not a fixed-rate
clock. Timing bounds in `summary.json` bracket when the cache rewrite was first
observed; they are not instrumented extraction-completion timestamps. Resource
sampling is discrete and can miss peaks. A successful HTTP status response or
an unchanged old `indexed` state alone does not establish successful reindexing.

## Sequence

- `TD45RDD6`: an already-complete short attachment, reindexed alone as a control.
- `65F79PTJ`: the already-complete group-library IPCC attachment, reindexed alone.
- `AXE7G67C`: the extra-large New Palgrave attachment.
- `TD45RDD6` again, submitted while New Palgrave was running, to observe how
  short work behaves behind a long native extraction. The second observer's
  phase named `baseline` is already under the large job's load; it is not idle.

The concurrent run has additional polling load. These are single observations,
not a statistically controlled throughput comparison. The short-job request is
an explicit native reindex, not an import or a priority reader request; the
finding does not claim to test those other paths directly.

## Findings

All submitted jobs completed, rewrote their caches, and produced byte-identical
extracted text. The short job submitted behind New Palgrave rewrote its cache
only after the large job's cache rewrite. Its isolated control had finished
quickly. This is observed blocking of short work by a healthy long extraction,
not an induced worker hang.

The group attachment's full-text version stayed unchanged across its completed
re-extraction. The isolated user-library control's version increased; the later
concurrent user-library re-extractions ended with the local-extraction sentinel
instead. Sync activity is not controlled here, so these version movements do
not isolate the effect of extraction from subsequent full-text syncing. Cache
modification time exposed work that the group full-text version did not.

During re-extraction, the per-item state and page counts continued to describe
the old complete extraction. The native pending-work counters did not expose
these plugin-submitted jobs. The plugin's `running` field counts outstanding
calls, including calls waiting for the shared worker, not active extractors.

The native item-list and plugin status endpoints continued responding during
the large extraction while the short attachment's cache remained untouched.
Application responsiveness and the ability of short indexing work to advance
are separate properties. CPU activity is observable but does not prove useful
document progress: a busy loop could also consume CPU.

Around New Palgrave's final cache replacement, both observers' status polls hit
their configured HTTP request timeout. Native item-list requests still returned.
Subsequent status requests recovered and reported idle without intervention.
The extraction completed successfully despite the monitoring-request failures;
these must not be treated as justification to resubmit the document. Slow
successful HTTP responses also occurred. This probe does not isolate their
cause between worker activity, database work, garbage collection and host load.

Existing SDT packs contain `dateCreated`, processor identity and source hash.
Their processor identities match the installed document-worker metadata read
from the application's archive. These are extraction provenance records; they
are not lexical-index completion dates. Reading old packs does not measure a
new SDT generation or establish the wall time of their original production.

The short attachment's native item API still reported its historical item
modification date after successful re-extraction, confirming that item metadata
dates cannot substitute for extraction dates. The flat full-text and lexical
index schemas' lack of processing-date fields remains a source finding; direct
live SQL inspection was blocked by Zotero's database lock.

## Design implications and remaining limits

An idle API is insufficient evidence that indexing is healthy. A supervisor
needs separate signals for queued work, active work, document progress, resource
pressure, completion and failure. Old coverage counters and the plugin's busy
flag cannot supply all of them. A duration threshold alone would confuse a
healthy large document with a stalled operation.

The source reading places native PDF jobs on a shared serial worker with no
per-job cooperative cancellation in the inspected interface. A supervisor can
pace admission, but preventing a running large extraction from delaying short
work needs an interruption/yield boundary or another execution arrangement.
No implementation choice is ratified by this report.

These probes do not establish recovery from a true worker hang, behaviour under
low storage or memory exhaustion, GUI responsiveness, native priority-job
pre-emption, resumable extraction, or live SDT progress. The existing installed
plugin exposes flat-text reindex and status only. Do not promote these limits
to positive results based on the absence of failures in healthy runs.

Source context: Zotero [worker manager](https://github.com/zotero/zotero/blob/10.0.1/chrome/content/zotero/xpcom/pdfWorker/manager.js),
[full-text module](https://github.com/zotero/zotero/blob/10.0.1/chrome/content/zotero/xpcom/fulltext.js),
and [SDT service](https://github.com/zotero/zotero/blob/10.0.1/chrome/content/zotero/xpcom/sdt.js).
