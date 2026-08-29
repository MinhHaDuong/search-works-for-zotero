# CONSTRAINTS — what the world imposes

## Intro

This document lists the constraints, C1 to C4: facts about Zotero, the
upstream project, and the user's machine that the design must operate under.
They were consolidated on 2026-08-26 from three earlier documents (the
ratified sheet, its delta, and the scout report), which are superseded and
live only in git history. Where the scouts, code-reading and measurement
passes over Zotero and upstream, sharpened a constraint, the sharpened form
is stated here and is binding.

The authority chain is stated once, in README.md.

## C1 — everything the index stores is derived data

The index stores derived data only, in a chain of three links:

1. extracted text derives from (attachment file, extractor);
2. chunks derive from (extracted text *or* item metadata, chunker identity
   and geometry), where the heuristic segmenter's identity folds into the
   chunker key, per the boundary ruling (the third ruling in
   REQUIREMENTS.md);
3. vectors derive from (chunks, embedder identity and model).

A "key" is the recorded identity of the inputs that produced a piece of
derived data. Work is stale exactly when a stored key no longer equals the
current key, and invalidation propagates downstream only.

The extractor's identity is visible only in-process. Over HTTP, the
observable proxy is the `/fulltext?since=` counter, which Zotero bumps when
it re-extracts synced content. Does a purely local re-extraction re-stamp
version 0, which would make it invisible to this counter? We do not know
yet. Experiment X6 (ticket 0025) will measure it, and DESIGN.md §2.4 is
designed to work under either answer. Items and full-text extractions are
numbered on two unrelated sequences (measured: 410 versus 0..25 036).

The scouts sharpened this constraint on three points:

- The local `/fulltext?since=` sequence is mixed. Web stamps, local client
  versions, and 0 for local extraction all appear in one column, so the
  correct filter is `since=0 OR version>since`. Versions can be compared
  for equality per item, but they are never a monotonic cursor: any design
  that uses this counter as a resume cursor on the local transport will
  silently miss locally-extracted text. (Measured: 584 of 8 037 fulltext
  entries at version 0 on the reference library.)
- Version validity is scoped by the `Zotero-Server-ID` header. A different
  server ID means a different database, different versions, different keys;
  stored state must therefore be partitioned by server ID. A local/cloud
  label is not enough, because two local profiles share the label and share
  nothing else.
- Even Zotero accepts a staleness residue here: their embeddings layer
  deliberately does not chase a processor bump without a file change
  ("vectors stay derived from the older extraction until the file changes
  or the index is rebuilt").

## C2 — the platform and the upstream project are both moving

Three facts about the terrain:

- zotero/zotero#6012, the draft pull request in which Zotero is building
  its own semantic search, is active and exposes nothing over the local API
  yet.
- The upstream maintainer (oscardvs/zoteus) merges small contained PRs and
  reimplements design-sized proposals himself; the asymmetry is measured
  two-for-two in each direction (SYNC.md).
- Some twenty other AI plugins are evolutionary pressure, not a runtime
  concern.

The consequence for the design: every pipeline stage (extract, chunk,
embed) is a swappable component, an adapter, identified by its key. The
lasting value is the contract — the MCP tools, coverage honesty, the
freshness protocol, and the filters, all defined in DESIGN.md. The
machinery behind the contract is replaceable. Anything sent upstream
decomposes into small PRs the maintainer will actually merge. The index
describes itself (schema version plus artifact keys), so it is openable or
cleanly rebuildable, never silently wrong.

The scouts sharpened this constraint on five points:

- The local API documentation states that "only one API version will ever
  be supported at a time", so a client reads the `Zotero-API-Version` and
  `Zotero-Schema-Version` headers rather than assuming a version.
- The local API has no `/deleted` endpoint; the documented deletion route
  is a key-set diff (`format=versions`, unpaginated).
- Constraining FTS5 MATCH to a rowid set makes FTS5 evaluate the expression
  per row, which costs seconds at library scale (#6012's measurement).
  MATCH therefore runs unconstrained on the general path, with scoping
  enforced elsewhere. One exception is permitted and disclosed in DESIGN.md
  §2.6: on scopes smaller than a threshold, to be measured by experiment
  X4, MATCH may run constrained. That fallback is never the default path.
- If the local API ever serves structured extraction, the SDT pack
  (zotero/structured-document-text) is the concrete thing to adapt to: a
  random-access container with a reader contract
  `{byteLength, read(offset,length)}`, describing itself with exactly the
  key shape of C1. Zotero's own chunker splits on structural boundaries,
  measured in tokens, and embeds the heading path with the text. Two details
  of it are easy to state wrongly, and both were, so they are stated here in
  the platform's terms (read at PR head `77e2c4b`, 2026-08-29).

  The geometry is 120 minimum, 48 overlap, and a maximum of 768 that is
  **a ceiling, not a chunk size**. The source says so in as many words:
  "A ceiling rather than a target: chunks come out paragraph-sized, so this
  decides only how long a text has to be before it's split at all." The
  effective budget is a minimum against the live model, not the constant —
  `Math.min(CHUNK_MAX_TOKENS, getModelMaxTokens()) - specialTokens -
  count(prefix)` (`embeddings.js:1642`). Six of the eight registered models
  declare `maxTokens: 512`; the two at 8 192 (`jina-embeddings-v2-small-en`,
  `bge-m3`) are labelled `test:`. So 768 never binds today, and exists to
  stop a future long-window model from emitting 8 000-token chunks. A
  consumer that copies 768 without the minimum copies a ceiling and uses it
  as a target, which is the opposite of what the number is for.

  The chunker also **does not** never cross a section: it merges sections
  below the 120-token minimum forward into their neighbour, asserted by
  #6012's own tests. It never merges two sections each able to stand alone.
  Our boundary ruling is therefore stricter than the platform's, a
  deliberate divergence rather than the alignment this bullet used to claim.
- Once #6012's saved-search serialization merges, it will be the first
  place platform semantic results appear in the local API.

Zotero 10 moved its keyword index. Verified on 2026-08-29 against the
author's own installation (10.0, build 20260817151751) and the shipped
`fulltext.js` of that build; the evidence is in
`verification/VERIFY-FULLTEXT-SQLITE.md`, and for the vocabulary and cache
measurements in the log of ticket 0120.

- The index left `zotero.sqlite`. Userdata step 127 dropped `fulltextWords`
  and `fulltextItemWords` and moved the keyword index into a separate
  attached database, `fulltext.sqlite`. Upstream commit `7c2a1d1`,
  2026-06-30, tagged in 10.0.0 and 10.0.1 only.
- The schema is four contentless FTS5 tables plus their bookkeeping:
  `fulltextContent` (unicode61), `fulltextContentCJK` (ascii, fed
  overlapping 2-grams), `fulltextNotes` (trigram), `fulltextNotesCJK`,
  with `fulltextIndexState`, `noteText` and `fulltextIndexMeta`. On the
  author's library: 13 090 content documents, 386 CJK, 1 200 notes.
- A row identifies an item directly. `fulltextContent.rowid` is the local
  `itemID`, joined 13 090 of 13 090 against `fulltextIndexState`.
- Contentless means the source text is discarded, not that the index is
  opaque. The stored column and `snippet()` both return nothing, measured,
  so a document cannot be printed back. What survives is the whole inverted
  index, and `fts5vocab` reads it: 670 680 distinct terms, 19 139 711
  (term, document) pairs, 135 973 731 occurrences with their positions.
  Constrained by term, `fts5vocab(…, 'instance')` returns the pair
  `(itemID, token offset)` in under a millisecond; constrained by document
  it is a 7,0 s full scan, so reconstructing a document works but is not a
  route. The bound is weaker than "which items, never which passage": a
  query term locates itself inside an item. Turning that token offset into
  a character position means reproducing Zotero's own tokenization, which
  an approximation did not — occurrence counts matched exactly on three
  documents while token indices drifted +13, +2 and 0.
- The extracted text lives in `.zotero-ft-cache`, one file per indexed
  attachment: 13 631 files, 819,4 MiB, plain UTF-8 carrying no markup. It
  is two extractor generations. Of 8 590 PDF caches, 4 708 carry form-feed
  page separators and 3 882 do not, split by mtime at roughly 2024, and the
  form-feed count equals `fulltextItems.indexedPages` for 4 471 of the
  4 708. The current path is `Zotero.PDFWorker.getFullText` writing straight
  through; nothing in the shipped app writes the older `.zotero-ft-info`
  sidecars, of which 2 788 survive on disk. What is observed is that caches
  written between 2019 and 2024 are still present on a machine now running
  10.0, so upgrading did not rewrite them; that no upgrade ever re-extracts
  is an inference from it, untested here. `rebuildIndex()` in `fulltext.js`
  would re-extract and has no caller in the shipped app. Either way both
  generations are live today, so page boundaries cannot be assumed.
- It is readable while Zotero runs, and fast. A read-only open of the live
  file returned a count in 7 ms and a `MATCH` in 8 ms with the application
  up. No `locking_mode=EXCLUSIVE` is held. `journal_mode` is `delete`, not
  WAL, so a writer takes an exclusive lock and a reader is cheap but not
  guaranteed available.
- Nothing documents any of this. The 10.0 changelog says only "Much faster
  full-text content searches", naming neither the file, nor FTS5, nor the
  split. This is an internal implementation file that has already moved
  once without announcement, which is the C2 risk in its purest form.
- Zoteus does not read it. It reaches full text over the local API
  (`/items/<key>/fulltext` and `/fulltext?since=`), so the move did not
  break it, and the platform's finished keyword index currently goes
  unused. Whether to depend on it is a design question, carried by ticket
  0120.

## C3 — the machine belongs to the user

Background work runs at leftover priority. The RAM ceiling is independent
of library and document size: extraction and chunking stream, so peak
memory is proportional to a section batch, not to the document. The embed
stage is the core-hog and must be isolatable. One scheduling rule covers
everything: foreground always beats background.

### Ratified budgets (2026-08-26)

- background ≤ ~1 core, low priority
- server steady-state RSS ≤ ~300 MB
- pipeline peak ≤ ~500 MB regardless of document size
- embed worker killable/restartable at any time with zero index damage

How the 300 MB figure scopes under N processes is awaiting the author's
ratification; the question is stated once, in DECISIONS.md.

## C4 — status answers from counters

Status must answer in a few milliseconds while all three queues run, and
never by scanning a table a stage is writing. Status is the only window
into requirements R1 and R2, coverage and its newest-first order
(REQUIREMENTS.md), and agents poll it every few seconds, forever. The
obvious implementation, a GROUP BY over the table the build is writing, was
measured at 374 ms with a cold cache. R6 budgets the query path; C4 budgets
the observation path.

## Politeness (web transport only, from the official API docs)

At most 4 concurrent requests; honor `Backoff: <seconds>` on ANY response,
including 2xx; honor 429/`Retry-After` with exponential fallback. The local
API has no rate limits and is unpaginated by default, so this constraint is
scoped to the web transport, not to the design.

## The author's structural hint (standing instruction to any panel)

A "panel" is one of this repo's recorded design-review sessions; cycle 2's
is in git history, last present at commit `e32afe3` as `panel/cycle2/`. The
hint: three asynchronous processes (extract, chunk, embed), independently
paced, with queues between them. Two justifications were found: (a) keyword
availability never waits on embedding, and (b) an OS process can be
nice'd, observed, and restarted. Panels take the hint seriously, not as
gospel. (Cycle 2's answer: two OS processes, three ledger-paced loops; see
DESIGN.md §2.5.)
