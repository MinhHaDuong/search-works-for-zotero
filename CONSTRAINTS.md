# CONSTRAINTS — what the world imposes

## Intro

This document lists the constraints, C1 to C4: facts about Zotero, the
upstream project, and the user's machine that the design must operate under.
They were consolidated on 2026-08-26 from three earlier documents — the
ratified sheet, its delta, and the scout report — which are superseded and
live only in git history. Where the scouts (code-reading and measurement
passes over Zotero and upstream) sharpened a constraint, the sharpened form
is stated here and is binding.
Ratifications are recorded in DECISIONS.md. Requirements are in
REQUIREMENTS.md; the design that operates under all of this is DESIGN.md.

## C1 — the derivation graph

Everything the index stores is derived data, in a chain:

- extracted text derives from (attachment file, extractor);
- chunks derive from (extracted text *or* item metadata, chunker identity
  and geometry) — the heuristic segmenter's identity folds into the chunker
  key, per the boundary ruling (the third ruling in REQUIREMENTS.md);
- vectors derive from (chunks, embedder identity and model).

A "key" is the recorded identity of the inputs that produced a piece of
derived data. Work is stale exactly when a stored key no longer equals the
current key, and invalidation propagates downstream only.

The extractor's identity is visible only in-process. Over HTTP, the
observable proxy is the `/fulltext?since=` counter, which Zotero bumps when
it re-extracts synced content. We do not yet know whether a *local*
re-extraction re-stamps version 0, which would make it invisible to the
counter; experiment X6 (ticket 0025) will measure this, and DESIGN.md §2.4
is designed to work under either answer. Items and full-text extractions are
numbered on two unrelated sequences (measured: 410 versus 0..25 036).

Binding sharpenings from the scouts:

- The local `/fulltext?since=` sequence is **mixed**: web stamps, local
  client versions, and 0 for local extraction, all in one column. The
  correct filter is `since=0 OR version>since`. Versions can be compared for
  equality per item; they are **never a monotonic cursor**. Any design that
  uses this counter as a resume cursor on the local transport will silently
  miss locally-extracted text. (Measured: 584 of 8 037 fulltext entries at
  version 0 on the reference library.)
- Version validity is scoped by the **`Zotero-Server-ID`** header. A
  different server ID means a different database, different versions,
  different keys. Stored state must be partitioned by server ID; a
  local/cloud label is not enough — two local profiles share the label and
  share nothing else.
- Even Zotero accepts a staleness residue here: their embeddings layer
  deliberately does not chase a processor bump without a file change
  ("vectors stay derived from the older extraction until the file changes or
  the index is rebuilt").

## C2 — the ground moves

The platform and the upstream project are both moving:

- zotero/zotero#6012 — the draft pull request in which Zotero is building
  its own semantic search — is active, and exposes nothing over the local
  API yet.
- The upstream maintainer (oscardvs/zoteus) merges small contained PRs and
  reimplements design-sized proposals himself — measured two-for-two in each
  direction (SYNC.md).
- Some twenty other AI plugins are evolutionary pressure, not a runtime
  concern.

Therefore: every pipeline stage (extract, chunk, embed) is a swappable
component — an adapter — identified by its key. The lasting value is the
contract: the MCP tools, coverage honesty, the freshness protocol, and the
filters (all defined in DESIGN.md). The machinery behind them is
replaceable. Anything sent upstream decomposes into small PRs the maintainer
will actually merge. The index describes itself (schema version plus
artifact keys), so it is openable or cleanly rebuildable, never silently
wrong.

Binding sharpenings from the scouts:

- Local API: "only one API version will ever be supported at a time" — read
  the `Zotero-API-Version` and `Zotero-Schema-Version` headers.
- The local API has no `/deleted` endpoint; the documented deletion route is
  a key-set diff (`format=versions`, unpaginated).
- Constraining FTS5 MATCH to a rowid set makes FTS5 evaluate the expression
  per row — seconds at library scale (#6012's measurement). MATCH therefore
  runs unconstrained on the general path, with scoping enforced elsewhere.
  One exception is permitted and disclosed in DESIGN.md §2.6: on scopes
  smaller than a threshold (to be measured by experiment X4), MATCH may run
  constrained. That fallback is never the default path.
- If the local API ever serves structured extraction, the SDT pack
  (zotero/structured-document-text) is the concrete thing to adapt to: a
  random-access container with a reader contract
  `{byteLength, read(offset,length)}`, describing itself with exactly the
  key shape of C1. Zotero's own chunker splits on structural boundaries,
  measured in tokens — 120 minimum, 768 maximum, 48 overlap — never crosses
  a section, and embeds the heading path with the text. This is platform
  prior art; the boundary ruling aligns with it.
- Once #6012's saved-search serialization merges, it will be the first place
  platform semantic results appear in the local API.

## C3 — the machine belongs to the user

Background work runs at leftover priority. The RAM ceiling is independent of
library and document size: extraction and chunking stream, so peak memory is
proportional to a section batch, not to the document. The embed stage is the
core-hog and must be isolatable. One scheduling rule: **foreground always
beats background**.

### Ratified budgets (2026-08-26)

- background ≤ ~1 core, low priority
- server steady-state RSS ≤ ~300 MB
- pipeline peak ≤ ~500 MB regardless of document size
- embed worker killable/restartable at any time with zero index damage

How the 300 MB figure scopes under N processes is awaiting the author's
ratification; the question is stated once, in DECISIONS.md.

## C4 — status answers from counters

Status must answer in a few milliseconds while all three queues run, and
never by scanning a table a stage is writing. Status is the only window into
requirements R1 and R2 (coverage and its newest-first order —
REQUIREMENTS.md), and agents poll it every few seconds, forever. The obvious
implementation — a GROUP BY over the table the build is writing — was
measured at 374 ms with a cold cache. R6 budgets the query path; C4 budgets
the observation path.

## Politeness (web transport only, from the official API docs)

At most 4 concurrent requests; honor `Backoff: <seconds>` on ANY response,
including 2xx; honor 429/`Retry-After` with exponential fallback. The local
API has no rate limits and is unpaginated by default — this constraint is
scoped to the web transport, not to the design.

## The author's structural hint (standing instruction to any panel)

A "panel" is one of this repo's recorded design-review sessions; cycle 2's is
in git history, last present at commit `e32afe3` as `panel/cycle2/`. The
hint: three asynchronous processes — extract, chunk, embed — independently
paced, with queues between them. Two justifications
found: keyword availability never waits on embedding, and an OS process can
be nice'd, observed, and restarted. Panels take the hint seriously, not as
gospel. (Cycle 2's answer: two OS processes, three ledger-paced loops —
DESIGN.md §2.5.)
