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

## Pending before describing the new scheduling behavior as shipped

Ticket [0752](../../tickets/0752-make-sdt-sitter-event-driven-with-reconc.erg)
replaces frequent full-library sweeps with event-driven updates and reconciliation
on startup, re-enabling and the periodic cadence owned by
[SPEC.md §5.2.7](../../SPEC.md#527-custody-and-lifecycle). This behavior is ticketed,
not implemented. Update this paragraph against release evidence before publishing.

The experimental scope and operational limitations are recorded in
[the launch report](../../verification/SDT-SITTER-LAUNCH.md).
