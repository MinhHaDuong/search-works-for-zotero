# Native SDT diagnostic plugin: isolated integration

Date: 2026-09-05. Ticket 0675. This is a diagnostic prototype and integration
report, not a production sitter or an acceptance-harness verdict.

## Outcome

The diagnostic addon runs in installed Zotero 10.0.1 and passes its real-host
fixture checks. It can inspect a pack without generating one, explicitly
generate an attachment, report progress, suppress repeated native failures
within the session, and clean up its API and toolbar when disabled.

Actual disable during an observed native extraction stopped the addon's
progress callbacks while Zotero completed the pack. A concurrent native reader
consumer received that pack. Re-enabling created a fresh addon API and reused
the completed cache. This is the graceful-stop behaviour now specified in
SPEC.md's R22 design paragraph, not a failed cancellation test.

The tested code and raw results are:

- `verification/probes/sdt-diagnostic-plugin/`: explicit-work addon; no HTTP
  endpoints, automatic census or background sweep.
- `verification/probes/sdt-diagnostic-harness/`: separate addon that imports
  fixtures and controls actual disable/re-enable through AddonManager.
- `verification/probes/run_sdt_diagnostic.py`: fixture/package/profile setup,
  isolation, process deadline, and result collection.
- `bench/results/sdt-diagnostic-2026-09-05/integration.json`: complete final
  report, tested source digests, runtime identity and process outcome.

## Isolation and reproduction

The driver creates a fresh temporary arena and uses the existing deterministic
PDF/EPUB fixture generator. `pdfunite` repeats the synthetic PDF to make an
in-flight lifecycle test. It starts an independent Zotero profile and data
directory under Xvfb, with a private network namespace and read-only host
filesystem. Only the arena and sandbox temporary/device files are writable.
It does not override HOME, read production attachments, enable a local HTTP
endpoint, or install anything in the production profile.

```sh
python3 verification/probes/run_sdt_diagnostic.py --application /opt/zotero7/zotero
```

The directory name is historical: the report's actual runtime version is
Zotero 10.0.1, not Zotero 7. Dependencies beyond the normal gate are the local
Zotero install, `bwrap`, `xvfb-run`, `pdfunite`, and Python's standard library.
The driver requires permission to launch the sandbox. Its deadline terminates
only the isolated process group it created, never processes selected by name.
The final run exited normally without reaching that deadline.

Each package refuses startup unless the disposable data directory contains the
matching diagnostic marker. The marker is an accident guard, not a security
boundary; the filesystem/network sandbox supplies the latter. Package update
URLs are deliberately nonproduction placeholders and the sandbox has no route
out. This prototype is not offered for installation in the user's real profile.

## What was exercised

- Native generation of PDF and EPUB packs, with the expected body tokens
  actually present in their structured content.
- Passive inspection of a missing cache without creating it, then inspection
  and explicit cache-hit requests without changing the pack hash or timestamp.
- Corruption of a disposable cache, detection, and native repair.
- Source-byte modification, stale-source detection, and regeneration.
- Invalid PDF failure, suppression of a repeated attempt, and successful retry
  after restoring the source bytes.
- Linked-file cache placement in Zotero's attachment storage rather than
  beside the linked source; refusal of a missing source file.
- Native reader consumption, actual addon disable/re-enable and toolbar/API
  cleanup, including disable during active extraction and concurrent native
  progress delivery after the addon's own callbacks stopped.

The passive inspector uses the bundled reader with range reads and compares
source/processor/schema provenance. It does not call `ensure`, `getPack` or
`getReader` merely to display status. These reads are not a snapshot of a file
being concurrently replaced; a future census must handle transient read errors
and recheck before classifying persistent corruption. A current metadata match
does not validate every content chunk or prove extraction completeness.

## Findings from bringing the prototype up

The mocked-service audit did not exercise bootstrap integration. Real runs
exposed a nonexistent Zotero timer helper, serial addon startup (a harness must
return before waiting for another addon), and an unavailable `cpucount` system
property. Those problems were corrected before the final recorded run.

`nsIFile.diskSpaceAvailable` and directory writability worked. Logical CPU
count is available through the window navigator; physical memory through
system information. Available memory is still explicitly unknown, not equated
with physical memory. The resource gate in this diagnostic only refuses an
unwritable/full data directory: it is NOT a production storage reserve or
memory-pressure policy, and the successful fixture runs establish neither.

The toolbar is a minimal diagnostic button with active label and an information
dialog, not the final spinner/statistics/ETA interface. There are no unattended
timers or event-driven library admissions to leak on disable in this prototype.
The test therefore cannot establish cleanup of a future automatic scheduler.

## What remains unproved

No snapshot, group-library, password-protected, low-space, memory-exhaustion,
worker-crash or application-restart experiment was run here. Stale source and
corrupt cache were exercised in Zotero; stale processor control flow remains
the earlier mocked-service test. The native reader consumer is not a GUI reader
latency test, and the concurrent request names the same document, not a short
document competing with a long extraction. Non-interference remains open.

The Palgrave audit and bounded writer tests are independent evidence:
`verification/SDT-PALGRAVE-AUDIT.md`. No Palgrave pack generation occurred in
the production or isolated profile. Whole-document memory and global-reference
phase cost remain reasons to instrument an isolated large-document run before
admitting that attachment to an unattended production sitter.
