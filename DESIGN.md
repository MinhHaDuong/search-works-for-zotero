# DESIGN — the sheet for what comes after the sync

*Agreed with the author 2026-08-26. Requirements are the author's, stated as testable
properties; constraints were worked out together. Resource budgets ratified verbatim.
This sheet is the input to the architecture panel; its output will be recorded beside it.*

## User requirements

| id | requirement | as a testable property |
|---|---|---|
| R1 | eventually all the lib is indexed | **convergence**: with no further edits, coverage reaches 100% without anyone asking; no state needs a manual rebuild |
| R2 | most recent first | coverage grows newest-first; the crawl frontier is a priority order, not a page cursor |
| R3 | avoid unnecessary rebuild | cost of staying current ∝ the change, not the library; recompute exactly what is downstream of a changed input — the unit of invalidation is (item × stage) |
| R4 | something partial is better than nothing | the index serves at every moment of its life, first build included — which obliges honest coverage reporting, or partial is indistinguishable from complete |
| R5 | filters are good to have | collection / tag / itemType / date scoping pushed into SQL, never post-filtering a top-k |
| R6 | sufficient reply in 3 s beats optimum in 3 min | freshness work on the query path is O(1) requests; anything bigger is scheduled, never awaited |
| R7 | multilingual by default | the default path works for FR/DE/VI/EL/RU without configuration; CJK ambition decided explicitly; the English STOPWORDS list is a known ranking bias (candidate move: delete it, let idf work); the default embedder is multilingual |
| R8 | 10k docs is not much | design point ≥ 10k docs with full text (~650k passages at the measured 63/item); known red zone: the vector full scan ≈ 1 s there |
| R9 | 15k-page docs are included | monster documents are first-class input, not an outlier to cap away (the 44.9 MB dictionary is the living example) |

## Constraints

**C1 — the derivation graph.** vectors ← (chunks, embedder id+model); chunks ← (extracted
text *or* item metadata, chunker id+geometry); extracted text ← (attachment file,
extractor). Staleness = stored key ≠ current key; invalidation propagates downstream only.
Extractor identity (`Zotero.SDT.getProcessorVersion`, `'pdf/3/1'`) is in-process only — the
observable proxy over HTTP is the `/fulltext?since=` counter, which Zotero bumps on
re-extraction. Items and full-text extraction are numbered on two unrelated sequences
(measured: 410 vs 0..25 036).

**C2 — the ground moves.** zotero/zotero#6012 is active and exposes nothing over the local
API yet; oscardvs/zoteus merges small contained PRs and reimplements design-sized proposals
himself; ~20 other AI plugins are evolutionary pressure, not a runtime concern. Therefore:
every stage is an adapter behind its key; durable value lives in the contract (MCP tools,
coverage honesty, freshness protocol, filters), not the machinery; anything sent upstream
decomposes into merge-shaped increments; the index self-describes (schema version +
artifact keys) — openable or cleanly rebuildable, never silently wrong.

**C3 — the machine belongs to the user.** Background at leftover priority; RAM ceiling
independent of library and document size (streaming extraction/chunking: peak is
O(section batch), not O(document)); the embed stage is the core-hog and must be isolatable.
One scheduling rule: **foreground always beats background**.

### Ratified budgets (2026-08-26)

- background ≤ ~1 core, low priority
- server steady-state RSS ≤ ~300 MB
- pipeline peak ≤ ~500 MB regardless of document size
- embed worker killable/restartable at any time with zero index damage

## The author's structural hint

Three asynchronous processes — extract, chunk, embed — independently paced, queued between.
Two justifications found: keyword availability never waits on embedding, and an OS process
can be nice'd, observed, and restarted. The panel is instructed to take it seriously, not
as gospel.

## Open decisions the panel must resolve

Semantic path at 650k vectors inside 3 s (scan / BM25-candidate rerank / int8 — int8 recall
is unmeasured and gets an experiment with a decision rule, not a hope); CJK ambition; the
STOPWORDS deletion; queue fairness against the monster doc; process vs worker vs async loop
per stage; the coverage sentence an agent sees.

## Ratification log

**2026-08-26 — the unit of answer is the entry.** The full sheet delta (19 candidate
requirements, 11 decisions, from the elicitation panel; held in the session record) awaits
ratification. One ruling made ahead of it, by the author: the panel's "one item, one hit"
is rejected as framed. The monster document is encyclopedic — a collection of entries —
and an unsplit multi-chapter book is a collection of chapters, so the retrieval and dedup
unit is the **section**, not the Zotero item. An encyclopedic item may legitimately yield
several distinct hits; a focused article yields one.

Consequences accepted with it: the monster-weight decision dissolves (thousands of peer
entries, not one over-weighted item); section identity becomes a derivation-graph concern —
`/fulltext` delivers flat text, so a heuristic segmenter (its identity folded into the
chunker key) stands in until structured extraction is ever served over the local API; the
citeable locator is the entry heading where one is known. Platform-aligned: Zotero's own
chunking already treats the section as the topic unit and carries outline paths.

**2026-08-26 — the record is the semantic core.** Title, abstract, and keywords are the
key semantic targets. Verified against upstream: they are indexed today but flattened into
one joined string (`[title, abstract, creators, tags, date, publication, book, note]`)
chunked at a fixed stride — fields lose identity, so a tag match scores like a title match
and a long abstract can separate the tags from their title. The ruling: every item's
record is indexed before any body text; fields keep their identity for ranking; notes,
annotations and body text extend the core, never dilute it. Feeds D1 (record coverage is
the first 100%) and fixes the phase order: record for everyone, newest first — body text
after.

**2026-08-26 — chunking respects entry boundaries; context is prepended.** Two further
rulings: chunk boundaries align to section/entry boundaries where structure is detectable
(never straddling two entries), and each chunk's embedded text is prefixed with its context
(entry heading / outline path / item title) — prior art in Zotero's own chunker, which
never lets two sections share a chunk and charges the outline-path prefix to the budget.

**2026-08-26 — the delta is ratified by delegation.** The author validated the presented
recommendations wholesale: additions R10–R28 (as amended by the rulings above) and C4
enter the sheet; decisions resolve as D1 items (+metadata-only counts), D2 hosted-out,
D3 serve-stale, D4 merged, D5 phrase, D6 first-with-text, D7 notes+annotations,
D8 leave-room (OCR out today), D9 dissolved by the entry ruling, D10 labeled-estimate,
D11 set; the seven out-of-scope declarations stand; the 22 kills stand. Any line remains
vetoable on later reading. Scout findings (mixed full-text sequence, Server-ID
partitioning, web politeness, R5's MATCH nuance, R2/smallest-first composition) are
sheet-candidate sharpenings recorded in the session and folded into cycle 2's input.
