# SDT pack sitter — release notes draft

Keep Zotero's structured-text caches ready, and make their state understandable.

The sitter's contribution is:

- **Observability:** see cache coverage, the active document, progress, reasons
  for waiting, failures and qualified completion estimates.
- **Insurance against missed changes:** reconcile cache state with local files
  to discover missing or stale packs and unavailable or restored attachments.
- **Independent preparation:** prepare native structured-text packs without
  opening each attachment or enabling semantic search, so extraction can be
  paid for before the first demand for semantic results.
- **Cautious scheduling:** check resources and native worker availability before
  submitting extraction work.

The sitter uses Zotero's own extractor. It does not improve extraction quality,
build a search index or isolate a stuck native worker. Coverage describes the
last observed state; preparation depends on local files, available resources
and successful native extraction.

## Why preparation ahead of demand matters

Time until useful attachment-content results matters alongside query latency.
Zotero's draft [semantic-search PR #6012](https://github.com/zotero/zotero/pull/6012)
already separates extraction from attachment embedding. At head `19e7962`,
checked 2026-09-08, its indexing loop embeds item metadata first, then finishes
the queued attachments' extraction pass before starting their embedding pass.
On an initially unindexed library, a long extraction backlog therefore delays
the first attachment-content semantic results, even for documents whose packs
are already ready. This is an implementation reading, not a measured duration;
see the pinned [indexing source](https://github.com/zotero/zotero/blob/19e79625b1c6fbbdd75367aa85b62d5a7080d7f6/chrome/content/zotero/xpcom/embeddings.js).

The search request itself does not ordinarily wait for the whole indexing run:
it can use available embeddings, and hybrid search falls back to lexical ranking
when the semantic index is not ready. Early replies can therefore precede useful
semantic coverage of attachment content; see the pinned
[search source](https://github.com/zotero/zotero/blob/19e79625b1c6fbbdd75367aa85b62d5a7080d7f6/chrome/content/zotero/xpcom/bestMatch.js).

The sitter's contribution is to make extraction independently available ahead
of that demand. With current packs already prepared, a consumer can proceed to
chunking and embedding without paying for their extraction then. Embedding still
takes time, and installing the sitter only when semantic search is first wanted
does not remove the initial extraction cost. Independent preparation is not a
claim that the sitter builds a progressively searchable index or that its
scheduler is better overall than #6012's. Stage separation alone also does not
require a whole-backlog barrier; consuming ready packs incrementally is a
separate consumer scheduling choice.

## GPU embedding and runtime independence

Independent packs also let extraction stay with Zotero while an external
embedding service uses a verified GPU-capable runtime. This is an advantage of
the wider pipeline, not a GPU feature shipped by the sitter. The existing
[inference-boundary review](../../verification/BRIDGE-0496.md) establishes the
limit at the same #6012 head: Zotero's embedding caller selects no GPU device
or execution provider. Its inference already runs outside the UI process;
the useful separation is from Zotero's bundled runtime and its exposed options,
not merely from the UI thread. This does not establish that Gecko could never
support GPU inference.

The review also identifies an existing outbound passage-embedding hook in
#6012, so Zotero could itself consume a compatible external service. Queries
still embed locally through that implementation. Our existing service work
(tickets 0491 and 0575) is the reuse path; device usability and compatibility
between query and passage vectors must be verified before claiming GPU benefit.

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
