# Carrying the page into the reply

Date: 2026-09-07
Status: Proposed, not ratified
Owner: ticket 0734
Prepared as: an upstream contribution to `oscardvs/zoteus`, not a fork-local patch

## Purpose

Ticket 0734 established where the page is lost between extraction and reply.
This note answers the two questions that follow: what carrying it costs, and
what shape the reply takes. It also prices exit criterion 4 without running it.

Every claim below cites a file and a line that was read. Line numbers are for
the `fork/` checkout at the reviewed baseline named by `SYNC.md` (upstream
v1.14.0). Measurements are marked as measured and name their instrument;
everything else is inference and says so.

## 1. Where the page is lost — one loss more than the ticket recorded

The ticket recorded three losses. Reading the supply side adds a fourth, and it
is upstream of the other three.

**Loss 0, new: the supply contract discards attachment identity and page
totals.** `fulltext-source.ts:167-193` (`textFor`) asks the router for each
attachment's full text, keeps only `ft.content`, and joins several attachments'
texts into one string with `'\n\n'`. The router already returned `indexedPages`
and `totalPages` beside the content (`api/web-client.ts:282`), and both are
dropped here. The interface itself forbids carrying them:
`FulltextSource.textFor` is `(itemKey: string) => Promise<string | undefined>`
(`fulltext-source.ts:26`), and the index's own option is
`fulltextFor?: (itemKey, item?) => Promise<string | undefined>`
(`backend.ts:425`). So by the time any chunker runs, the build no longer knows
which attachment a character belongs to, nor how many pages that attachment
has.

The three losses the ticket recorded stand as recorded: `chunker.ts:8` collapses
`\s+` before any chunk exists and slices the collapsed string at `chunker.ts:21`;
`ChunkRecord` (`backend.ts:61-68`) has no page and no offset; the `passages` DDL
(`sqlite-index.ts:930-937`) has no column for one.

## 2. The cost, and whether a rebuild is implied

### 2.1 How the ladder is versioned and dispatched

`SCHEMA_VERSION` is a module constant, currently `2` (`sqlite-index.ts:63`). The
stamp is a row in `meta` under the key `schemaVersion`, written by
`createSchema` (`sqlite-index.ts:972-974`) and read, before any write touches the
file, by `storedSchemaVersion` (`sqlite-index.ts:528-547`), which answers
`'fresh'`, `'unstamped'`, or the integer.

`reconcileSchema` (`sqlite-index.ts:585-645`) dispatches on that answer. A file at
this build's version, or fresh, is left alone (`596`). Otherwise `migrationPath`
(`655-667`) asks for the contiguous run of rungs from the stored stamp up to this
build's, refusing outright when the stored stamp is greater than or equal to this
build's (`658`). `runMigrations` (`680-702`) runs every rung and stamps the new
version inside one `BEGIN IMMEDIATE` transaction, so a database is fully at one
version or fully at the other. A failure that is corruption sidelines the file;
anything else refuses and leaves it untouched (`599-644`).

One rung exists, `to: 2` (`SCHEMA_MIGRATIONS`, `sqlite-index.ts:175-201`): this
fork's own PR #46, which changed the FTS tokenizer and therefore re-tokenized
every passage without touching a vector.

A drive-by documentation defect, below the bar for a ticket and worth sending
upstream with the change: the comment at `sqlite-index.ts:252-255` still says
"SCHEMA_VERSION has never been bumped", which stopped being true when the
constant moved to 2.

### 2.2 The column can be added in place, and should not bump the stamp

Two in-place shapes are available, and the code has already argued for the second
one, in its own words, about a different table.

*A rung.* `to: 3`, `up(db)` running `ALTER TABLE passages ADD COLUMN page TEXT`
inside the stamping transaction. Cheap, atomic, and it satisfies R23 forwards. It
fails R23 backwards: `migrationPath` refuses any stamp at or above this build's
(`658`), so an older build meeting the new index sidelines it and charges its
owner a rebuild. SPEC.md:624-631 calls that a failure of the promise rather than
a way of keeping it, and R23's "either direction" clause is explicit that the
rolled-back build is the case it exists for.

*A side table, with no bump.* This is the `vector_codes` precedent, and the
reasoning is already written at `sqlite-index.ts:53-61`: that table was added
without a bump because every statement the backend issues names its columns, so
an older build neither reads nor writes it, a newer build creates it on demand,
and an index that has neither is searched exactly as before. Bumping "would have
sidelined every index in existence and charged its owner a full re-embed for a
cache the server can rebuild from what is already on disk". A page is the same
kind of object: derived from the extraction, absent means no page reported, which
is today's behaviour exactly.

The DDL's own row-layout argument points the same way. `sqlite-index.ts:946-949`
keeps the binary codes out of `passages` because a column added after the 12 KB
`vector` column sits behind it in the row, so reading it drags the vector's
overflow pages. A page column would sit there too.

So: `CREATE TABLE IF NOT EXISTS passage_pages (...)` in `createSchema`
(`sqlite-index.ts:926-975`), no rung, no stamp change, R23 satisfied in both
directions.

### 2.3 The backfill has no source, and that is the finding

A rung can add the column. Nothing can fill it.

`chunkText` (`chunker.ts:7-26`) collapses every whitespace run to a single space
in its first statement (`8`) and then slices the *collapsed* string (`21`).
`Chunk` is `{index, text}` (`1-4`). What lands in `passages.text` is therefore a
slice of a string whose relation to the raw extraction was discarded before the
slice was taken, and the row stores no offset (`sqlite-index.ts:930-937`). Given
a stored row, no arithmetic recovers where it came from.

Nor can a rung go and look. `SchemaMigration.up` is `up(db: Database): void`
(`sqlite-index.ts:165`): synchronous, and its only argument is the database
handle. `runMigrations` calls it inside `BEGIN IMMEDIATE` (`680-702`). There is no
client, no `await`, and no route to Zotero. A rung that wanted to re-read an
attachment could not, and one that could would be re-reading the whole library
inside a write transaction, which is the opposite of what the ladder is for.

**A backfill with no source for its value is not a backfill.** The column
migrates in place; the values do not. They arrive only when the rows are written
again.

### 2.4 So a re-chunk is implied, and a re-embed is a wiring decision

The rows are written again by re-chunking, and re-chunking is not free by
construction: SPEC.md's C1 makes chunks derive from (extracted text, chunker
identity and geometry) (SPEC.md:751-753). Changing the chunker changes the key, so
every chunk in every library is stale at once.

That is R3-conformant. R3 (SPEC.md:438-445) bounds cost by what changed, and what
changed here is an input to every chunk. A whole-library re-chunk is proportional
to that.

A whole-library **re-embed** would not be. Nothing about a vector's inputs
changed: an embedding is a function of the text and the model, which is the
argument `vector-salvage.ts:19-22` already makes. Re-computing 255k vectors
because a chunker learned to count pages is cost proportional to library size for
an input that did not move, and R3 is what forbids it.

The code can already avoid it, and the avoidance is one wire short of reachable:

- `adoptVector` (`sqlite-index.ts:881-898`) takes a vector from a sidelined index
  when it holds one for `rec.id` and `rec.text`; `VectorSalvage`'s four conditions
  (`vector-salvage.ts:24-33`) are the same embedder, the same library, the same
  passage id, and the same text byte for byte.
- A chunker that keeps `chunkText`'s output *text* byte-identical (same collapse,
  same boundaries, same slices) and merely records where each chunk began in the
  raw argument changes neither id nor text. Every vector is reusable in principle.
- But the salvage is armed in exactly one place, `priceOf`
  (`sqlite-index.ts:770-800`), which runs only from `sideline()`. A `zotero_index
  action:"refresh"` over a live database arms nothing and pays the full re-embed,
  priced by the file's own comments at five and a half hours of local CPU on a
  255k-passage library, or real spend on a hosted embedder
  (`sqlite-index.ts:53-61`, `143-146`).

So the contribution has to extend the arming to a deliberate in-place re-chunk,
and that extension is the difference between minutes and hours. It is not an
optimisation; under R3 it is the requirement.

`action:"update"` needs no such wiring: it re-chunks only changed items, so pages
appear gradually and untouched rows keep a null page until something else touches
them.

### 2.5 The verdict, in one line

**No rebuild is implied by the schema. A full re-chunk is implied by the chunker,
R23 is satisfied in both directions if the page lands in a side table with no
stamp bump, and R3 is satisfied only if the re-chunk reuses the existing vectors,
which the code can do and the current arming does not reach.**

## 3. The reply shape

### 3.1 Vocabulary: reuse `passages.ts`, do not invent a second one

`passages.ts:5-15` already models exactly the distinction D10 asks for: `page` is
"exact page from PDF re-extraction", `pageApprox` is "proportional page
estimate". Presence is the label. This proposal keeps both names and that rule,
so a reader meets one vocabulary and not two.

One deviation, stated because the instruction was to state it: `Passage` types
`pageApprox` as `number` (`passages.ts:12`), and on `SearchHit` it must be a
`string`. A passage straddling a boundary needs a range, a number cannot carry
one, and the gate's own `page_set` (`bench/golden_gate.py:269-289`) reads
`"12-13"` as `{12, 13}`, so a string is the shape the ruled intersection test
consumes. `page` is a string for a second reason as well: real printed folios in
the committed bank include `VIII`, `xxi`, `3-1`, `ES-4` and `17 / 21`.

### 3.2 The change, through the whole path

| Where | What it gains |
|---|---|
| `FulltextSource.textFor` (`fulltext-source.ts:26`, impl `167-193`) | returns `Array<{attachmentKey, content, indexedPages?, totalPages?}>` instead of one joined string; stops discarding what `api/web-client.ts:282` already delivered |
| `SearchIndexOptions.fulltextFor` (`backend.ts:425`) | the same array, so the build knows which attachment each character belongs to |
| `Chunk` (`chunker.ts:1-4`) | `rawStart: number`, `rawEnd: number`, offsets into the RAW argument. `text` is unchanged byte for byte, which is what keeps ids and vectors valid |
| `ChunkRecord` (`backend.ts:61-68`) | `attachmentKey?: string`, `page?: string`, `pageApprox?: string` |
| storage | new table `passage_pages(pid INTEGER PRIMARY KEY, attachment_key TEXT, page TEXT, page_approx TEXT)`, `CREATE TABLE IF NOT EXISTS` in `createSchema` (`sqlite-index.ts:926-975`). No column on `passages`, no rung, no stamp bump (§2.2) |
| `SearchHit` (`backend.ts:51-58`) | `attachmentKey?: string`, and exactly one of `page?: string` or `pageApprox?: string` |
| `query()` (`index-manager.ts:2180-2184`) | copies them onto the hit the way it already copies `source` at `2183` |

Per hit the reply then carries `itemKey`, `title`, `snippet`, `score`, `source?`,
`attachmentKey?`, and one page field. A single page is `"12"`; a passage crossing
a boundary is `"12-13"`. `page` present means a printed folio read off the
document; `pageApprox` present means the system derived it. That presence *is*
D10's estimate flag.

### 3.3 Which source fills which field, and the honest gap

`pageApprox` is fillable today. Where the extraction carries form feeds, the
ordinal is `1 + (count of "\f" before rawStart)`. Where it does not, the
proportional estimate is `approxPage(rawStart, totalChars, totalPages)`
(`passages.ts:18-22`), whose `totalPages` is already on the wire
(`api/web-client.ts:282`) and thrown away at `fulltext-source.ts:167-193`.

`page` is **not fillable today**, and this is the part that must not be glossed.
Nothing in `fork/src` reads a PDF's page-label dictionary: a grep for
`getPageLabels` and `pageLabels` over the whole tree returns only
`annotate.ts:77-78` and `annotate.ts:225`, and what that shows is the opposite of
a folio source. The product's own convention there is `a.page_label ??
String(pageIndex + 1)`, an ordinal used as a label. Two sources exist in
principle and neither is wired:

- `pdfjs-dist ^5.6.205` (`fork/package.json:77`) exposes `getPageLabels():
  Promise<Array<string> | null>`
  (`fork/node_modules/pdfjs-dist/types/src/display/api.d.ts:945`), reachable from
  the same lazy import `extractPdfPages` already does (`pdf-pages.ts:14-44`), but
  only on the PDF-file path, which the search index build never takes, since it
  indexes Zotero's cached text;
- Zotero's structured-text pack, which R24 names as the case where the page is
  the block's own anchor and is not an estimate (SPEC.md:517, §5.2.4).

So under this proposal, as the product stands, every hit would carry `pageApprox`
and none would carry `page`. That is the truthful reply, and §4 prices what it
buys.

## 4. What exit criterion 4 costs — stated, not run

Nothing here was built or run. No Zotero instance was touched.

### 4.1 The mechanics

`make golden-run` needs a built fork: `GOLDEN_SERVER ?= fork/dist/index.js`
(`Makefile:371`) and the target refuses without it (`Makefile:388`), so it implies
`make upstream-checkout`, then `npm ci && npm run build` inside `fork/`. It also
refuses a `GOLDEN_DATA_DIR` that already exists (`Makefile:389`). `make golden`
then validates and scores.

The edit list is §3.2's seven rows, across six files: `fulltext-source.ts`,
`backend.ts`, `chunker.ts`, `sqlite-index.ts`, `index-manager.ts` and `build.ts`
(`562`, where `fulltextFor` is constructed). Plus the salvage-arming change of
§2.4, in `sqlite-index.ts`.

One harness edit is implied and belongs to this repo, not upstream:
`bench/golden_run.py:172` reads `hit.get("page") or hit.get("pageLabel") or
hit.get("page_label")` and does not read `pageApprox`. Under §3.3 a product with
no folio source fills only `pageApprox`, so the runner would map nothing into
`result["page"]` and the official reading would stay at zero. Whether it should
read it is question Q2 below.

### 4.2 The ceiling, measured

Measured over the committed bank (`bench/fixtures/questions`, 281 questions, of
which 195 are scored and 86 are negative controls) and the committed export
(`bench/fixtures/export`), using the gate's own `page_set` and
`Export.page_span` as the instrument. Reproduced by importing
`bench/golden_gate.py` and evaluating each scored question's `set_kind` against
its primary rows.

| If the engine reported, perfectly | Upper bound on R34 official |
|---|---|
| the extraction's form-feed page ordinal | **15 / 195** |
| the printed folio | **85 / 195** |

Two facts produce those numbers.

**110 of the 195 scored questions carry no printed page on any alternate of any
primary row.** `official_page_verdict` (`bench/golden_gate.py:1066-1072`) returns
unsatisfied on an empty target whatever the reply says, so 85/195 (43,6 %) is the
ceiling of the official reading as the bank stands, and no amount of engine work
passes it.

**The extraction ordinal is not the printed folio.** Over the 108 alternates that
carry both a printed folio and a locatable character offset, the ordinal equals
the folio 18 times and differs 90 times. The offset varies per work: +1, +2, +3,
+10, +12, +15, +17, +19, +20, +21, +22, +28, and −100. Thirty of those 90 folios
are not arabic numerals at all. The gate's own negative-control prose says the
same thing in words: "printed p. 307 (scan page 327)", "printed p. 141, pdf page
153", "printed p. 150, pdf page 162" (`bench/results/golden/report.json`,
`readings.negative_controls.firing`).

Also measured, for the population a form-feed derivation can serve at all: 39 of
the 92 fulltext caches in the committed export carry at least one form feed. In
the author's live library the same count is 343 of 8 580 PDF caches
(`bench/results/0480-fulltext-quality/census.json`), so the export is far richer
in page structure than the library it was drawn from, and the export's ratio is
not evidence about the library.

### 4.3 The operational answer

The first non-zero official reading needs, in order: the six-file fork change of
§3.2 plus the salvage arming of §2.4; a fork build; a runner that reads whichever
field the ruling makes official; an empty data dir; then `make golden-run && make
golden`.

What it would read: on the ordinal path, at most 15 of 195, and less than that in
practice, because a question also has to return the right work within k. Of the 85
folio-bearing scored questions, 33 currently fail on work identity alone, their
rows recording "no result within k returned the primary row's work". The 85/195
reading needs a printed-folio source the product does not have, and building one
is a second contribution, not this one.

Stated plainly for the author: **closing 0734 as scoped moves the official
reading off zero, and moves it a little. It does not make the nine arms of the
red-state exercise distinguishable on the official score.** That is a fact about
the bank and the product together, established here for the first time, and it
belongs in front of the decision about what to build next.

## 5. Open questions for the author

Recorded, not answered.

**Q1 — is a ceiling of 85/195 the intended shape of the official reading?** 110
scored questions can never satisfy it, because their answers carry no printed
page. The official score is therefore a fraction of 195 whose numerator is bounded
at 43,6 %. The alternative is to score the official reading over the questions
that carry a printed page and report the denominator, which changes what the
number means.

**Q2 — does a labelled estimate satisfy R34's official reading?** D10 admits a
labelled estimate and R24 requires the label. `official_page_verdict` reads one
field and makes no distinction. If an estimate counts, `golden_run.py:172` must
read `pageApprox`; if it does not, the official reading cannot move at all until
the product gains a printed-folio source.

**Q3 — two-valued vocabulary over three sources.** D10 and `passages.ts` split
pages into exact and estimated. There are three sources: the printed folio, the
extraction's form-feed ordinal, and the proportional estimate. This note maps the
latter two onto `pageApprox`, on the grounds that both are "not the printed
folio". Confirm, or split the vocabulary.
