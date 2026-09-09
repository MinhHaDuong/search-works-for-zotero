# Experimental native SDT sitter

Ticket 0680. Source: `plugins/sdt-sitter/`; package with
`python3 bench/build_sdt_sitter.py --output /absolute/path/to/new.xpi`.

The extension warms native PDF, EPUB and snapshot SDT caches through the
installed service. It never replaces source attachments, changes flat-text
truncation preferences, opens a server endpoint, or persists a private ledger.
Consequently pack coverage is not a claim that Zotero's separate lexical index
or Zoteus's embedding index is complete. Native SDT does not use the flat-text
extraction caps.

Install through Zotero's extension manager. The first activation asks once
whether to index in the background; the answer is written to
`extensions.sdt-pack-sitter.enabled` and the question is never asked again, on
this restart or any later one. That preference is R22's one obvious way for the
sitter (ratified 2026-09-08, ticket 0742), and the switch that carries it is the
first control in the add-on's window: off runs no census and admits nothing, and
says so on the toolbar; on is ordinary operation. Editing the preference away in
the Config Editor puts the profile back in the unanswered state, and the question
is asked once more.

Attachment changes and completed file downloads now queue targeted inspections.
Full reconciliation runs on activation, re-enabling and the cadence owned by
SPEC.md §5.2.7. Resource retries resume the queue without another library census.
Coverage reports the last observed state and the age of the last completed
reconciliation. [Scheduling verification](SDT-SITTER-EVENTS.md) records the host
notification mapping and tests; live deployment of this change is not measured.

The toolbar button opens session coverage and progress, elapsed time and time
since the last native signal, empirical processing speed, an indicative ETA
after census, and a snapshot of native full-text index statistics. ETA is not
a prediction for exceptional books: document sizes and global citation costs
are heterogeneous. Missing local files, unsupported attachments and unsupported
pack versions are reported rather than silently treated as covered.

The empirical estimator follows the cadence and quantiles owned by SPEC.md's
R22 design paragraph. It uses observed duration per page when available,
otherwise per byte, for the active document and for completion date/time scenarios.
It does not infer calibrated predictive coverage from a small sample. An active
job exceeding the empirical upper quantile is not declared failed; this simple
model reports the finish estimate as unavailable rather than completion now.
It does not extrapolate an unobserved tail or repair its own selection bias.

The disposable `sdt-sitter-cache.jsonl` in Zotero's data directory retains
verified census hints and the latest successful duration observation per
attachment. It contains no text, source paths, active tasks or failure ledger:
a document whose extraction fails is suppressed in memory for the remainder of
the session and asked again on the next activation.
Native source hashes, processor versions and pack filesystem fingerprints
gate reuse. Missing/corrupt records fall back to inspection. The first completed
census compacts the cache; later writes append changed derived rows, avoiding
a whole-library rewrite on every completion. Removing this file is safe while
the extension is disabled; it will be rebuilt without deleting native packs.

To read what the sitter itself is doing, open Zotero's Help → Debug Output
Logging → View Output with logging enabled; the same transitions are also held
in a volatile in-session ring, readable as `Zotero.SDTPackSitter.journal.tail()`
from Tools → Developer → Run JavaScript. That object exists only while the
sitter is running, so the command throws before startup completes, on a build
where native SDT is unavailable, and after the extension is disabled — which is
exactly when the debug output is the only copy left. The ring dies with the
session, so the no-private-ledger promise above stands. What a record may and
may not carry, and what the trace level adds, are owned by SPEC.md's R22 design
paragraph; the on-screen failure line remains the place the whole error text
appears. To widen the debug output,
create `extensions.sdt-pack-sitter.debug` and set it true in the Config Editor
(Settings → Advanced → Config Editor); errors and state transitions are logged
whether or not it is set.

The cache/clock and grouped-progress build is covered by
`bench/results/sdt-sitter-launch-2026-09-05/cache-and-progress.json`, including
reactivation with restored observations and no repeated native extraction.
`verification/SDT-SITTER-UI-PANEL.md` records the requested independent panel
verdicts and the remaining accessibility/wording recommendations.

Turn the switch off, in the add-on's own window, to stop further admissions;
disabling the extension in Zotero's add-ons manager does the same and also
removes the window and the toolbar entry. Under either, the already submitted
native job can finish and persist its pack. Re-enabling does not ask for
confirmation again — the persisted answer stands — and reconstructs coverage
from native caches. Turning the in-window switch back on retains session
failures; a fresh extension activation creates a new session and can retry them. No unresolved native promise is retried.

What the sitter does not control (the shared worker's priority and
interruptibility) and what stopping it does and does not do are readable in the
window's Details layer at any time, rather than only in the first-run dialog.

## Experimental limits

Admission guards are owned by SPEC.md's R22 design paragraph. Resource checks
currently depend on Linux procfs and native filesystem free-space reporting;
missing readings stop admission. CPU load is an admission proxy, not an exact
count of free cores. Shared-worker queue fields are private API and fail closed
when absent. These checks do not reserve resources or cap a running extraction.

The worker has no independent OS priority control and cannot be preempted.
Native work arriving after admission may wait. This is an overnight experiment,
not demonstrated foreground non-interference. The plugin animation means an
outstanding job, not a heartbeat from the worker. A silent global citation phase
can be healthy. A dead or permanently unresolved worker requires native recovery
or a Zotero restart; the extension does not monkey-patch its shared lifecycle.
Tickets 0679 and 0681 separately track the quadratic membership patch and safe
native crash recovery.

## Verification

`tests/sdt_sitter_scheduler.mjs`, invoked by `tests/test_sdt_sitter.py`, covers
census ordering, cache hits, resource waits, single admission, unresolved native
promises, disable during asynchronous work, failure suppression, changed-source
retry, persistence validation and unsupported input exclusion.

The real-application smoke command is:

```sh
python3 verification/probes/run_sdt_diagnostic.py --sitter --application /opt/zotero7/zotero
```

It installs the unmodified production extension plus a private UI driver in a
fresh marked profile, with synthetic attachments only. The host is read-only
apart from that arena and the network is unshared. The historical installation
directory name does not identify the Zotero version. Raw run results, including
source digests and UI checks, determine whether a particular build is cleared
for handoff; the command existing is not itself a passing verdict.

The passing launch run is recorded in
`bench/results/sdt-sitter-launch-2026-09-05/integration.json`. It completed
normally, confirmed automatic native PDF/EPUB generation and empirical fit
refresh, opened the toolbar dialog with native full-text statistics, and
removed the UI on disable. Snapshot extraction and a whole-library overnight
run are not established by these synthetic fixtures. Scheduler disable during
unresolved work is tested independently by the asynchronous unit host; earlier
native graceful completion evidence belongs to `SDT-DIAGNOSTIC-LIVE.md`.
