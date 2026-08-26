# DESIGN DELTA — ratified by delegation 2026-08-26 (see DESIGN.md ratification log for the rulings that amend it)

SHEET DELTA — for line-by-line ratification. Adds 19 requirements (R10–R28) and 1 constraint (C4), asks 11 decisions answerable in a word (D1–D11), offers 7 out-of-scope declarations, and lists 22 kills for veto. R1–R9 and C1–C3 are untouched.

---

## 1. PROPOSED ADDITIONS

Ordered by regret of omission. A tag like "(D4)" means the line takes final shape from that decision below.

### Requirements

**R10 LOCAL BY DEFAULT** — with no explicit opt-in, no library text and no query text leaves the machine; the default build and query path make zero external calls.
  (privacy) The sheet fixes a multilingual default embedder but never the custody posture, and today's bundle error hint steers .mcpb users to API embedders that POST passage text to api.openai.com / generativelanguage.googleapis.com (zoteus-ci src/features/search/embeddings.ts:248,257; config.ts:115).

**R11 COUNTER CHURN IS NOT CHANGE** — a resync or extractor upgrade that advances versions on identical bytes re-embeds nothing whose content is unchanged.
  (lifecycle) Counter-keyed staleness satisfies R3's letter while a resync recomputes everything at the most expensive stage; this project already shipped the defect: 92.7% of the library reported changed on every delta, forever (fork-zoteus bae82a7; C1's two unrelated sequences, 410 vs 0..25,036).

**R12 GROUP LIBRARIES** — my groups are searchable like my own, and indexing one library never erases another. (D4)
  (reader) The sheet says "the lib" as if singular while PR #12 made groups servable; today the store is keyed by context, not library, and a group build calls clearStore() over the personal index (zoteus-ci src/features/search/build.ts; semantic-search.ts takes no library argument).

**R13 SECOND PROCESS** — two zoteus on one data dir both answer, neither corrupts the index, and no passage is extracted or embedded twice.
  (lifecycle) Not an edge case: stdio spawns one zoteus per MCP client on one fixed default dataDir (src/lib/paths.ts), no busy_timeout or SQLITE_BUSY handling exists anywhere in src/, and the three-writer design multiplies it.

**R14 NO TEXT IS A TERMINAL STATE** — an attachment that yields none is done, not retried forever: counted covered as metadata-only, reason recorded, coverage report says so. (D8)
  (corpus) R1 has no terminal state for scanned PDFs — forever-retry never reaches 100%, silent skip lies about it; pr6012 records no-text as processed so counts converge, upstream logs once and re-encounters forever (fulltext-source.ts:131).

**R15 DELETED MEANS GONE** — deleting an item in Zotero removes its text from every stage's store and the queues between, not merely from search results.
  (privacy) R3 defines invalidation, never removal, and the three-process design adds two new persistent text copies nothing obliges anyone to purge; docs/semantic-search.md:136 already treats a store that cannot delete as convergence-breaking for the one store that exists.

**R16 MY OWN WORDS** — notes and annotations are in the corpus, not just papers. (D7)
  (corpus) Builds crawl top:true only, so the researcher's own text is invisible while pr6012 embeds notes and annotations as first-class — and zoteus can create annotations (src/tools/annotate.ts) it can never find again (build.ts:214,260).

**R17 COVERAGE IN ONE SENTENCE** — "how much of my library is searchable?" gets a human answer: N of M items, per stage, most-recent-covered date.
  (reader) Three independently paced queues make coverage a vector, and R2's newest-first is unverifiable without a frontier date; today's status describes one build job's machinery, not the library's coverage (build.ts statusSummary).

**R18 AN EMPTY RESULT SAYS WHICH** — "nothing matches" or "this scope is not indexed yet", for the scope the query asked, not the library as a whole.
  (query) Joins R4 to R5 at the answer: a filtered query over a 0%-covered collection prints the same "No matches" as a true miss over a covered one (semantic-search.ts ~line 120; no per-collection coverage exists anywhere).

**R19 THE FOLD SWEEP IS A GATE** — no query token may point where the index cannot hold; the 1,301-codepoint sweep runs on every check, not in a closed ticket.
  (operator) The one class where regression-by-copy is proven: upstream v1.7.0 re-shipped the byte-identical broken tokenize.ts after the fix — "théorie" → ['th','orie'] is live there today (bench/fold_sweep.mjs found 12 escaping codepoints; SYNC.md).

**R20 RAM BUDGETS ARE GATES** — C3's numbers are asserted by the harness against the 44.9MB dictionary on every check, not measured once.
  (operator) This repo already broke an ungated RAM promise: 0003 said "a few hundred MB", 0011 measured 1,848.8 MiB, found only because someone looked (bench/results/0011-rss/; the Makefile gates lint, figures, pytest — no RSS assertion).

**R21 SAME CORPUS IN, SAME ANSWERS OUT** — a pinned query set with golden answers gates every change. (D11)
  (operator) 0009 shipped Jaccard 0.00 on real French queries under a green suite; the comparison exists only as a manual ritual (compare.py), and a regression it would catch lands the day nobody runs it (STATE.md gates).

**R22 PAUSE STAYS PAUSED** — one obvious way to stop all background work, and it holds across restarts.
  (reader) C3 caps how hard the background runs but gives the user no veto: today's stop halts one job and auto_build (default true) starts a fresh build on the next query (index-tool.ts action:"stop"; semantic-search.ts).

**R23 UPGRADE AND DOWNGRADE** — a zoteus with a different schema opens the old file and ends up serving, in either direction, without anyone deleting files by hand.
  (lifecycle) SCHEMA_VERSION=1 is written and never read (sqlite-index.ts:27,163); C2's moving target guarantees skew, and the only documented recovery today is a manual rm of three files (corruption.ts).

**R24 A CITEABLE PAGE IN ONE STEP** — a fulltext hit leads to its page, and an estimated page number says it is an estimate. (D10)
  (query) A hit today is snippet-only (backend.ts:23-27); pageApprox is proportional over totalChars — off by hundreds of pages on the dictionary — and precise_pages refuses files over 20MB, which the 44.9MB living example always exceeds (passages.ts, pdf-pages.ts:7).

**R25 ONE ITEM, ONE HIT** — and a 15k-page doc cannot crowd other items out of the candidate pool before that dedup happens. (D9)
  (query) R9 makes the monster first-class input but says nothing of its weight in answers: the dictionary holds 42,963 of 477,512 passages and lands in the top-10 of 28/60 random-term queries; dedup runs after a limit*3 pool it can fill (bench/results/0013-concentration/; index-manager.ts:881-918).

**R26 CONVERGENCE IS WATCHED, NOT TRUSTED** — from empty, touching nothing but status, the harness sees 100% arrive unattended, and every poll's indexed set is a most-recent-first prefix.
  (operator) R1 and R2 are the sheet's core promises and neither has an observable; three queues emit no done event, and newest-first is measured nowhere today (bench/run_build.py drives builds, asserts neither).

**R27 EDIT ONE, COUNT ONE** — every stage reports what it processed and which input triggered it; one edited item shows as one.
  (operator) R3 is untestable without work-performed counters; the one shipped delta defect was silent precisely because nothing counted — 7,453 candidates per delta, hidden by maxItems (ticket 0012; bench/results/0012-fulltext-sequence/sequences.json).

**R28 UNINSTALL** — deleting the data dir is the whole uninstall; no index state, queue, watermark, or downloaded model survives anywhere else.
  (lifecycle) Holds by accident today and R7's local embedder will break it: model runtimes cache weights in ~/.cache unless told otherwise — one line now versus gigabytes of surprise after uninstall (all current state lands under dataDir; no writes outside paths.ts found).

### Constraints

**C4 STATUS ANSWERS FROM COUNTERS** — a few ms while all three queues run; never a scan of a table a stage is writing.
  (operator) Status is the only window into R1/R2 and agents are told to poll it every few seconds forever (index-tool.ts); 0013 measured the convenient GROUP BY at 374 ms cold against the table the build writes. R6 budgets the query path; nothing budgets the observation path.

---

## 2. DECISIONS REQUIRED

Each answerable in a word; several additions above take their final shape from these.

**D1 THE DENOMINATOR** (corpus — gates R17, R26, and every acceptance test): 100% of what — items touched, attachments extracted, or characters of extractable text — and do metadata-only items count toward it? [items / attachments / characters + yes / no] The ratified no-cap decision (STATE.md, 2026-08-22) leans characters; the sheet never says so.

**D2 HOSTED MODE** (privacy): do R1–R9 and the C3 budgets bind the multi-tenant OAuth server (per-user indexes, ContextCache×50), or is this redesign desktop-only? [in / out / metadata-only-when-hosted] Four killed privacy lines return if the answer is "in".

**D3 EMBEDDER CHANGE** (lifecycle — fires with certainty, since R7's default differs from today's): do yesterday's vectors keep answering, labeled stale, until re-embedding overtakes newest-first — or does semantic coverage drop to zero at open, as the code silently does today (index-manager.ts:306 dropStaleVectors)? [serve-stale / drop-all]

**D4 GROUP SHAPE** (reader — shapes R12): one merged index spanning personal + groups, searched together with library as an R5 facet — or per-library indexes built and queried one at a time? [merged / per-library]

**D5 PHRASES** (query): does a quoted phrase match as a phrase? Today "general equilibrium" retrieves passages containing either word — promise phrase (and AND/NOT) semantics, or freeze bag-of-words OR as the contract for both backends? [phrase / bag-of-words]

**D6 TWIN ATTACHMENTS** (corpus): PDF + snapshot with the same text on one item — index both, first-with-text per item, or suppress near-duplicates? [both / first / dedupe] 0013 measured idf shifts to +28% from one over-represented text.

**D7 OWN-WORDS SCOPE** (corpus — shapes R16): match #6012 eligibility exactly (notes + annotations), or notes first with annotations an explicit later line? [both / notes-first]

**D8 IMAGE-ONLY PDFs** (corpus — shapes R14): OCR permanently out of scope, converging as metadata-only — or a future extractor stage the keys leave room for? [out / leave-room]

**D9 MONSTER WEIGHT** (query — shapes R25): cap one item's passages in the candidate pool, or accept that a dictionary legitimately matches almost everything and let ranking decide? [cap / ranking]

**D10 PAGE FIDELITY** (query — shapes R24): the cited page is exact, recorded when the text is read — or estimated at answer time and honestly labeled an estimate? [exact / labeled-estimate]

**D11 WHAT THE GOLDEN PINS** (operator — shapes R21): the answer SET (Jaccard threshold) or the full ORDER? 0013: legitimate idf shifts reshuffle order in roughly half of queries while 97% of the set survives — order is flaky, set misses rank regressions. [set / order]

---

## 3. EXPLICIT OUT-OF-SCOPE CANDIDATES

One-line declarations the sheet could carry so silence does not read as promise. Ratify or strike.

- **WORK DOES NOT TRAVEL** — the index is per-machine; a second machine re-earns it unattended via R1; vector export/sync is out of scope. (from reader's killed portability question)
- **THE REBUILD IS THE BACKUP** — the index is derived (C1) and backup-exempt; no snapshot tooling. (from lifecycle's killed backup question)
- **RECENCY ORDERS COVERAGE, NOT ANSWERS** — R2 is an indexing frontier; ranking stays relevance-only. (from query's killed ranking question)
- **OCR IS OUT** — image-only attachments converge as metadata-only. (the "out" branch of D8)
- **HOSTED MODE IS OUT** — the redesign binds the desktop; the OAuth server keeps today's behavior. (the "out" branch of D2)
- **AR/HE UNTESTED** — Arabic/Hebrew are expected to ride the default path (unicode61 + multilingual embedder) but sit outside R7's tested matrix. (from corpus's killed RTL question)
- **NO ENUMERATION** — semantic search returns a bounded page; exhaustiveness is R5 narrowing's job, not paging's. (from query's killed "show me more" question)

---

## 4. KILLED

One line each; veto any by naming it.

- (reader) First question after install answers — covered: R4's "serves at every moment" includes minute zero; the evidence shows a violation, not a missing line.
- (reader) Does 100% include body text — answered: R8 is "10k docs with full text" and R9 makes monsters first-class; the surviving question is D1's denominator.
- (reader) The other machine — gold-plating toward a sync product; R1 is the second machine's answer, and C2 warns #6012 may absorb portability. [returns as out-of-scope line 1]
- (reader) Per-item "why is X missing" — covered piecewise by R14's recorded reason, R17's per-stage figures, and the ratified no-cap; what remains is diagnostic UI.
- (reader) Every hit names its page — duplicate of R24, which adds the honest-estimate obligation this phrasing lacks.
- (lifecycle) FIRST RUN — implied by R1 ("without anyone asking; no manual rebuild"), and empty is a state; violation, not hole.
- (lifecycle) DISK FULL — composition of R1, R4, and 0010's ratified refuse-never-corrupt posture; ENOSPC is one instance, not a new line.
- (lifecycle) BACKUP — C1 says derived, R1 says the rebuild converges unattended; snapshot tooling is gold-plating. [returns as out-of-scope line 2]
- (privacy) SAY WHEN IT LEAVES — covered by R10: once off-machine requires explicit opt-in, custody disclosure happened at opt-in; a per-answer banner is gold-plating.
- (privacy) DELETE MY INDEX — contingent on D2; the desktop half is covered by R28 and R15.
- (privacy) WHOSE CONSENT IN MULTI-TENANT — contingent on D2; deciding consent before scoping hosted is enterprise gold-plating.
- (privacy) PLAINTEXT AT REST — contingent on D2; encrypting a desktop index of the user's own library is gold-plating.
- (privacy) NO SILENT FALLBACK — contingent on D2; documented single-tenant behavior today, and follows from tenancy itself if hosted is scoped in.
- (corpus) EPUBs and snapshots — covered by C1's own wording: the stage is text <- (attachment, extractor), not (PDF, extractor); /fulltext already delivers all three types.
- (corpus) Hit names its attachment — duplicate of R24: a one-step citeable page necessarily names the attachment it lives in.
- (corpus) Arabic/Hebrew matrix — gold-plating: R7's list is the owner's own corpus; unicode61 and the default embedder already handle RTL. [returns as out-of-scope line 6]
- (operator) O(1)-requests gate — duplicate of R6, already the countable assertion; unlike the RSS budget, never broken; process, not a missing requirement.
- (operator) kill -9 test — duplicate of C3's ratified "killable any time with zero index damage"; the defect has never actually occurred.
- (operator) One coverage figure or per-stage — duplicate of R17, which decides it (per stage), with D1 supplying the unit.
- (query) Recency in ranking — R2's own wording draws the line at coverage; recency-weighted scoring is solutioneering in question form. [returns as out-of-scope line 3]
- (query) Monster-doc reading budgets — covered: R6 binds every reply and C3's ceiling is explicitly independent of doc size, no carve-out; violation, not gap.
- (query) "Show me more" paging — gold-plating: agents narrow and re-query; R5's filters are the stated instrument. [returns as out-of-scope line 7]