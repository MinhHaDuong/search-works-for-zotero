# CONSTRAINTS — what the world imposes, consolidated

*The constraints memo: C1–C4, the ratified budgets, and the scout sharpenings
that bind the design, in their current form. Consolidated 2026-08-26 from the
ratified sheet, its delta, and the scout report (superseded, in git history);
ratifications are recorded in DECISIONS.md. This memo is the readable current
statement. Requirements live in REQUIREMENTS.md; the design that operates
under all of this is DESIGN.md.*

## C1 — the derivation graph

vectors ← (chunks, embedder id+model); chunks ← (extracted text *or* item
metadata, chunker id+geometry — the heuristic segmenter's identity folds into
the chunker key, per the boundary ruling); extracted text ← (attachment file,
extractor). Staleness = stored key ≠ current key; invalidation propagates
downstream only. Extractor identity is in-process only — the observable proxy
over HTTP is the `/fulltext?since=` counter, which Zotero bumps on
re-extraction of synced content; whether a *local* re-extraction re-stamps
version 0 (leaving the counter blind) is an open measurement — X6, ticket
0025, and DESIGN.md §2.4 designs for both answers. Items and full-text
extraction are numbered on two unrelated sequences (measured: 410 vs
0..25,036).

**Sharpenings (scouts, binding):**

- The local `/fulltext?since=` sequence is **mixed** — web stamps, local client
  versions, and 0 for local extraction; the filter is `since=0 OR
  version>since`. Versions are equality-comparable per item, **never a
  monotonic cursor**. Any design cursoring that counter on the local transport
  silently loses locally-extracted text. (Measured: 584 of 8,037 fulltext
  entries at version 0 on the reference library.)
- Version validity is scoped by **`Zotero-Server-ID`** — a different ID means a
  different database, different versions, different keys. Stored state must be
  partitioned by server ID; a local/cloud label is not enough (two local
  profiles share the label and share nothing else).
- Even Zotero accepts a staleness residue here: a processor bump without a file
  change is deliberately not chased by their embeddings layer ("vectors stay
  derived from the older extraction until the file changes or the index is
  rebuilt").

## C2 — the ground moves

zotero/zotero#6012 is active and exposes nothing over the local API yet;
oscardvs/zoteus merges small contained PRs and reimplements design-sized
proposals himself (two for two in each direction — SYNC.md); ~20 other AI
plugins are evolutionary pressure, not a runtime concern. Therefore: every
stage is an adapter behind its key; durable value lives in the contract (MCP
tools, coverage honesty, freshness protocol, filters), not the machinery;
anything sent upstream decomposes into merge-shaped increments; the index
self-describes (schema version + artifact keys) — openable or cleanly
rebuildable, never silently wrong.

**Sharpenings (scouts, binding):**

- Local API: "only one API version will ever be supported at a time" — read the
  `Zotero-API-Version` / `Zotero-Schema-Version` headers.
- No `/deleted` endpoint on the local API; key-set diff (`format=versions`,
  unpaginated) is the documented deletion route.
- Constraining FTS5 MATCH to a rowid set makes FTS5 evaluate the expression per
  row — seconds at library scale (#6012's measurement). MATCH therefore runs
  unconstrained on the general path, with scoping enforced elsewhere; the one
  permitted exception is the disclosed small-scope fallback of DESIGN.md §2.6
  (a constrained MATCH on scopes below a threshold X4 measures, never the
  default path).
- The SDT pack (zotero/structured-document-text) is the concrete adapter path
  if the local API ever serves structured extraction: random-access container,
  reader contract `{byteLength, read(offset,length)}`, self-describing with
  exactly our C1 key shape. Zotero's own chunking is tokens on structural
  boundaries (120 min / 768 max / 48 overlap, never across sections, heading
  path in the embed text) — the platform prior art the boundary ruling aligns
  with.
- #6012's saved-search serialization is the first crack through which platform
  semantic results will leak into the local API once merged.

## C3 — the machine belongs to the user

Background at leftover priority; RAM ceiling independent of library and
document size (streaming extraction/chunking: peak is O(section batch), not
O(document)); the embed stage is the core-hog and must be isolatable. One
scheduling rule: **foreground always beats background**.

### Ratified budgets (2026-08-26)

- background ≤ ~1 core, low priority
- server steady-state RSS ≤ ~300 MB
- pipeline peak ≤ ~500 MB regardless of document size
- embed worker killable/restartable at any time with zero index damage

*Open ratification question (cycle 2, concurrency critique M5):* the 300 MB
figure was ratified against a single-server picture; under the normal N-server
deployment (one zoteus per MCP client) the whole-machine figure at two clients
is ~690 MB steady. Whether the budget binds per process or per machine is the
author's call, not the panel's — both figures are stated in DESIGN.md §2.9.

## C4 — status answers from counters

A few ms while all three queues run; never a scan of a table a stage is
writing. Status is the only window into R1/R2 and agents poll it every few
seconds forever; the convenient GROUP BY was measured at 374 ms cold against
the table the build writes. R6 budgets the query path; C4 budgets the
observation path.

## Politeness (web transport only, from the official API docs)

≤4 concurrent requests; honor `Backoff: <seconds>` on ANY response including
2xx; honor 429/`Retry-After` with exponential fallback. The local API has no
rate limits and is unpaginated by default — this constraint is scoped to the
transport, not the design.

## The author's structural hint (standing instruction to any panel)

Three asynchronous processes — extract, chunk, embed — independently paced,
queued between. Two justifications found: keyword availability never waits on
embedding, and an OS process can be nice'd, observed, and restarted. Panels
take it seriously, not as gospel. (Cycle 2's answer: two OS processes, three
ledger-paced loops — DESIGN.md §2.5.)
