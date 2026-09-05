# Experimental native SDT sitter

Ticket 0680. Source: `bench/sdt-sitter/`; package with
`python3 bench/build_sdt_sitter.py --output /absolute/path/to/new.xpi`.

The extension warms native PDF, EPUB and snapshot SDT caches through the
installed service. It never replaces source attachments, changes flat-text
truncation preferences, opens a server endpoint, or persists a private ledger.
Consequently pack coverage is not a claim that Zotero's separate lexical index
or Zoteus's embedding index is complete. Native SDT does not use the flat-text
extraction caps.

Install through Zotero's extension manager, then accept the launch dialog.
The toolbar button opens session coverage and progress, elapsed time and time
since the last native signal, empirical processing speed, an indicative ETA
after census, and a snapshot of native full-text index statistics. ETA is not
a prediction for exceptional books: document sizes and global citation costs
are heterogeneous. Missing local files, unsupported attachments and unsupported
pack versions are reported rather than silently treated as covered.

The session estimator follows the cadence and quantiles owned by SPEC.md's
R22 design paragraph. It uses observed duration per page when available,
otherwise per byte, for the active document and for total remaining scenarios.
It does not infer calibrated predictive coverage from a small sample. An active
job exceeding the empirical upper quantile is not declared failed; this simple
model does not extrapolate an unobserved tail or repair its own selection bias.

Disable the extension to stop further admissions. The already submitted native
job can finish and persist its pack. Re-enabling asks for confirmation again
and reconstructs coverage from native caches. Session failures are forgotten,
so re-enabling can retry them. No unresolved native promise is retried.

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
