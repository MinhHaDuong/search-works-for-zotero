# SDT pack sitter — release notes draft

Keep Zotero's structured-text caches ready, and make their state understandable.

The sitter's contribution is:

- **Observability:** see cache coverage, the active document, progress, reasons
  for waiting, failures and qualified completion estimates.
- **Insurance against missed changes:** reconcile cache state with local files
  to discover missing or stale packs and unavailable or restored attachments.
- **Independent preparation:** prepare native structured-text packs without
  opening each attachment or enabling semantic search.
- **Cautious scheduling:** check resources and native worker availability before
  submitting extraction work.

The sitter uses Zotero's own extractor. It does not improve extraction quality,
build a search index or isolate a stuck native worker. Coverage describes the
last observed state; preparation depends on local files, available resources
and successful native extraction.

## Prepared for the next release

Ticket [0752](../../tickets/closed/0752-make-sdt-sitter-event-driven-with-reconc.erg)
replaces frequent full-library sweeps with targeted updates from attachment and
file-download notifications. Reconciliation runs on startup and re-enabling, and
at the periodic cadence owned by
[SPEC.md §5.2.7](../../SPEC.md#527-custody-and-lifecycle).
Resource retries resume queued work without rescanning the library. The window
shows how recently reconciliation completed; disk availability remains a last
observation. Missing files stay in Zotero and their native packs are preserved.

Implementation and host-mock verification are recorded in
[the scheduling report](../../verification/SDT-SITTER-EVENTS.md). This draft does
not claim a live-profile deployment or a published release.

The experimental scope and operational limitations are recorded in
[the launch report](../../verification/SDT-SITTER-LAUNCH.md).
