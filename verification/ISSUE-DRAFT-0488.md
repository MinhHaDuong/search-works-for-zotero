# Curated local embedder registry, staged without changing the default

## Problem

The local embedding path currently constructs `Xenova/all-MiniLM-L6-v2`
directly. The existing model environment variable applies to API providers,
not this local path, while pooling and normalization are coupled to the
constructor. A model-name knob would therefore permit configurations that load
but silently produce the wrong vectors.

PR #110 measured several candidate configurations, including their licences,
artifact sizes, runtime compatibility and retrieval probes. Those results are
evidence for building a safe selection mechanism; they do not select a new
default.

## Proposed staged contract

1. Extract today's complete MiniLM chain into a singleton, versioned registry
   entry and prove vector/key parity.
2. Make every vector-affecting field authoritative: pinned model revision,
   graph/dtype, pooling, normalization, query and passage templates, context
   window and output dimension. Derive vector identity from the complete entry.
3. Add other complete curated entries and select one by entry id. Keep an unset
   selector on the incumbent MiniLM entry.
4. Before creating or querying an index, validate the selected entry on the
   actual runtime/provider using a bundled public fixture. Fail explicitly;
   never switch entries silently.
5. Separately, use retrieval-quality and resource gates to decide which entries
   are exposed and whether the default should ever change.

The query/passage interface should remain transport-neutral: the install
default is `local_endpoint`, one embedding service per machine serving the same
registry entry to every client. This issue does not require a daemon. Whether that shareable
service belongs in zoteus, in an optional companion, or in the OS is a separate
design discussion that must not block this registry. Zotero #6012 already owns
a separate native inference process internally; if Zotero later exposes an
official query/passage embedding bridge, it should be another executor of this
same contract rather than a competing registry.

## Acceptance tests

- Capture incumbent MiniLM query/passage vectors and vector keys before the
  extraction; require identical results afterward.
- Perturb every registry field independently and prove it affects construction
  or the fingerprint as declared; display metadata must not affect identity.
- Reject unknown, incomplete, unloadable and fingerprint/dimension-mismatched
  entries before index access.
- Exercise the same query/passage interface in-process without adding an
  installation or activation step.
- Validate loadability, shape, finite values, normalization, templates,
  provider-local determinism and simple matched-over-unmatched discrimination
  on the bundled fixture.

## Optional compatibility crowdtesting

A later opt-in could aggregate only the automatic compatibility result keyed by
the exact entry fingerprint and minimum runtime/provider/platform shape. It
must send no library text, query text, vector or Zotero identifier. Such counts
say that a configuration executes on reported environments; they are not votes
about retrieval quality and must not choose the default.

## Non-goals

- Recommending or changing the default embedder in this issue.
- Exposing independent raw model, pooling, prefix or dtype knobs.
- Replacing the private golden retrieval gate with crowd opinion.
- Requiring, packaging or prescribing an embedding daemon or OS service.

## Open implementation choices for the registry

- Registry file format and schema-validation library.
- Selector name and how status exposes the resolved entry.
- Validation-result cache location and invalidation.
- Whether compatibility aggregation warrants a separate endpoint at all.

I suggest one design issue with staged pull requests, each independently
reversible and keeping the incumbent behavior until the final ship decision.
