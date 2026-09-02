# Attribution audit — every external claim in SPEC.md, verified at source

**Ticket:** `tickets/0180-audit-every-external-attribution-against.erg`
**Date:** 2026-09-02
**Subject:** `SPEC.md`, all sections, §6 included, at this branch's base.

## Instruments, and the commits every verdict is addressed to

| source | ref | date | how read |
|---|---|---|---|
| `zotero/zotero` PR #6012 (draft) | `77e2c4b05111077108fe31e879f95b9687643e9a` | 2026-08-28 | clone, `refs/pull/6012/head`, checked out detached |
| `zotero/zotero` `main` | `9e28eb0d39d86a2df19e4f952c8533b748b1aa09` | 2026-09-01 | same clone, read with `git show` |
| PR base / merge-base | `3af8cea1af597f572155ee02d87bf62ef7e2e7f4` | — | used to separate what #6012 adds from what already shipped |
| `oscardvs/zoteus` reviewed baseline | `b05ed69a88e3a0c1ef874f57f97a0e11ddf7ec3c` (v1.12.0) | 2026-09-01 | `make upstream-checkout` |
| `oscardvs/zoteus` at the design's own pin | `c5d25aa` (v1.7.0) | — | read to establish that the stale claims were once exact |

**#6012 has not moved.** `77e2c4b` is the same head the 2026-08-29 and
2026-08-30 reads used. The ticket's invariant is that a verdict is a verdict
*at a commit*; four days on, the commit is the same one, so those earlier
verdicts are addressed to the same source this audit read. It is still a
draft, still not an ancestor of `main`, and still touches no `server/` or
API file.

## The two tallies

Both are counts of the register's own rows below, and reproduce from them: 83
rows, 54 verified, 29 not.

**Claims wrong: 19.** Counted the way the ticket's own table counts — a claim
is wrong when the mechanism, value, scope or actor it names is not what the
source does. Nine concern Zotero core and #6012, seven upstream zoteus, three
the platform outside #6012.

**Evidence grades wrong: 10.** A claim whose substance is true, cited at a
strength the source does not support: a rationale read as a measurement, a
comment read as behaviour, a third party's assertion read as our own reading,
a report cited for figures it does not contain, a quotation silently cut.
Five concern the platform, three #6012, two upstream.

By verdict the 29 are 15 refuted, 13 holds-in-part, 1 overstated.

The two are counted separately and deliberately, per the author's ruling of
2026-08-31: folding a grade defect into the mechanism tally blunts a finding
whose force comes from being about mechanism. Both are defects; only one
misleads an implementer.

Beside them, **1 verdict of this audit's own was wrong and is reversed in the
same branch** — the §4 C1 residue row, and the section "Three faces of one
class" below tells it. It is not in either tally, because it never
reached the document; it is recorded because the reversal is the most
instructive row here.

## Register

Verdicts: **V** verified · **P** holds in part · **O** overstated · **R**
refuted · **N** could not look. Kind: **claim** = wrong mechanism/value/scope ·
**grade** = wrong evidentiary standing.

### Zotero core and PR #6012

| site | claim in short | verdict | kind | coordinate |
|---|---|---|---|---|
| §4 C1 | Zotero accepts the same processor-bump staleness residue | **R** | claim | `embeddings.js:2352-2360`, `:2428`, `sdt.js:298-308` @ `77e2c4b` |
| §4 C1 | `/fulltext?since=` counter bumps on re-extraction | **P** | claim | `fulltext.js:508-534`, `:1130` @ `9e28eb0` |
| §4 C1 | different server ID ⇒ different versions **and keys** | **P** | claim | `userdata.sql:169` @ `9e28eb0` |
| §4 C2 | #6012 active, exposes nothing over the local API | **V** | — | `3af8cea..77e2c4b`, no `server/` file touched |
| §4 C2 | rowid-constrained MATCH is #6012's *stated rationale*, no figure | **V** | — | `lexical.js:355-366` @ `77e2c4b` |
| §4 C2 | SDT pack produced by `zotero/structured-document-text` | **R** | claim | `.gitmodules:33-34` — the producer is `zotero/document-worker` |
| §4 C2 | local API neither serves nor creates the pack; read beside the file | **V** | — | `sdt.js:760-761`; no SDT reference under `xpcom/server/` |
| §4 C2 | reader contract `{byteLength, read(offset,length)}` | **V** | — | `sdt.js:704-709` @ `77e2c4b` |
| §4 C2 | in shipped 10.0 only the reader writes a pack | **V** | — | at tag `10.0.1`, `Zotero.SDT.` appears only in `reader.js` |
| §4 C2 | the embedding branch generates one per embedded attachment | **V** | — | `embeddings.js:2428` @ `77e2c4b` |
| §4 C2 | chunker splits on structural boundaries, tokens, heading path embedded | **V** | — | `utilities_internal.js:3692`, `:3752-3754`, `:3810` |
| §4 C2 | geometry 120 min / 48 overlap / 768 **ceiling not chunk size** | **V** | — | `embeddings.js:1516`, `:1523`, `:1525-1527` |
| §4 C2 | the ceiling comment, quoted verbatim | **P** | grade | quote cut mid-sentence; source continues "and how far a single oversized paragraph is split" |
| §4 C2 | budget formula at `embeddings.js:1642` | **V** | — | line still exact at `77e2c4b` |
| §4 C2 | 6 of 8 models at `maxTokens: 512`; two at 8 192 labelled `test:` | **V** | — | `embeddings.js:69-150` |
| §4 C2 | merges sections below the minimum forward, asserted by #6012's tests | **V** | — | `utilities_internal.js:3717-3740`; `embeddingsTest.js:670`, `:689` |
| §4 C2 | `bestMatch` condition + `/searches/:searchKey/items` already on main | **V** | — | `searchConditions.js:274` @ `77e2c4b`; `server_localAPI.js:1218` @ `9e28eb0` |
| §4 C2 | "#6012's saved-search **serialization**" | **P** | grade | the PR adds a *condition*; the serialization is pre-existing |
| §3 R7 | the two-gram geometry **the platform ships** | **V** | — | `fulltext.js:2224` @ `9e28eb0`; correct as phrased |
| §5.2.6 | 2-gram twin tables are **#6012's shipped geometry** | **R** | grade | geometry present at the PR base `3af8cea`; #6012 only calls it |
| §5.2.6 | calibration noise floor = **p99** of unrelated pairs | **R** | claim | `NULL_PERCENTILE = 0.999` @ `embeddings.js:3068` |
| §5.2.6 | calibration: mean centering, ceiling = median matched, reject bad models | **V** | — | `embeddings.js:742-750`, `:3072`, `:3496-3505` |
| §5.2.6 | entry score is MAX over chunks, #6012's rule | **V** | — | `embeddings.js:1226-1228`, `:1243` |
| §5.2.6 | annotation parent attachment and page pass through when supplied | **V** | — | `item.js` `toJSON`: `parentItem`, `annotationPageLabel` |
| §5.2.3 | #6012 orders attachments smallest-first | **V** | — | `embeddings.js:2093-2113` |
| §5.2.5 | #6012 runs ONNX in a separate memory-gated process; calls internal | **V** | — | `ml.js:27-30`, `:95-100`; `embeddings.js:673` |
| §5.2.7 | drain then shut down, a #6012 pattern | **V** | — | `embeddings.js:2909-2912`, `:2996-3014` |
| §5.2.8 | `pipeline: idle` is the #6012 engine-shutdown observable | **R** | claim | field is `phase`; `idle` on both the shutdown and keep-alive branches (`:2782`, `:2998`) |
| §5.2.4 | pack reached through the `/file/view/url` **redirect** | **R** | claim | that route returns the URL as a plain-text body (`server_localAPI.js:1264-1276`) |
| §3 R24 | SDT page is the block's own anchor, not an estimate | **V** | — | `sdt.js:182-184`, `:406-421`; `utilities_internal.js:3785-3790` |
| §5.2.2 | prefix charged to the budget, Zotero's own prior art | **V** | — | `utilities_internal.js:3754-3758`, `:3811` |
| §5.2.2 | Zotero pairs the ceiling with the same minimum *against the model window* | **P** | claim | `min()` applies to the ceiling only; `CHUNK_MIN_TOKENS` is flat — **registered, not edited** |
| §5.2.2 | length trigger reads Zotero's `indexedPages` | **P** | claim | column saturates at the `maxPages` cap (`fulltext.js:680`) — **registered, not edited** |

### The Zotero platform outside #6012

| site | claim in short | verdict | kind | coordinate |
|---|---|---|---|---|
| §2 | `/fulltext` lists **every** attachment's version | **P** | claim | one library, and only attachments already carrying a row (`server_localAPI.js:1470-1483`) |
| §2 | `Zotero-Server-ID` scopes versions **and keys** | **P** | claim | as §4 C1 above |
| §2 | local API is loopback, unpaginated, unthrottled | **V** | — | `server.js:75`, `:325`; `server_localAPI.js:82-86` |
| §2 | item keys unique only within a library | **V** | — | `userdata.sql:169` |
| §2 | the **measured** cost of constraining a MATCH is C2's | **R** | grade | C2 disclaims a measurement; X4 has not run |
| §4 C2 | local API docs: "only one API version … at a time" | **V** | — | `server_localAPI.js:33-36`; docs page, fetched 2026-09-02 |
| §4 C2 | no `/deleted`; the **documented** deletion route is `format=versions` | **P** | grade | route real, unpaginated; documented as such nowhere |
| §4 C2 | userdata step 127, commit `7c2a1d1`, tagged 10.0.0/10.0.1 only | **V** | — | `schema.js:3790-3795`; `git tag --contains` |
| §4 C2 | four contentless FTS5 tables and their tokenizers | **V** | — | `fulltext.js:159-227` |
| §4 C2 | `fulltextContent.rowid` is the local `itemID` | **V** | — | `fulltext.js:2275-2292` |
| §4 C2 | contentless discards the source text | **V** | — | `fulltext.js:159-181` |
| §4 C2 | main-index vocabulary counts, evidence "in VERIFY-FULLTEXT-SQLITE.md" | **R** | grade | figures in no artifact; the report measures the CJK vocabulary only |
| §4 C2 | `Zotero.PDFWorker.getFullText`; nothing writes `.zotero-ft-info` | **V** | — | `fulltext.js:651`; whole-tree grep, zero hits |
| §4 C2 | `.zotero-ft-cache` census (13 631 files, 819,4 MiB, the form-feed split) | **P** | grade | measured on the author's machine, in no committed artifact |
| §4 C2 | `rebuildIndex()` has no caller in the shipped app | **V** | — | whole-tree grep: definition plus four tests |
| §4 C2 | readable while Zotero runs; 7 ms / 8 ms; no `locking_mode=EXCLUSIVE` | **R** | grade | the cited report says "Not tested here — Zotero was not running, deliberately"; EXCLUSIVE is PR #100's assertion |
| §4 C2 | `journal_mode` is `delete`, not WAL | **V** | — | `VERIFY-FULLTEXT-SQLITE.md` §2.2 |
| §4 C2 | 10.0 changelog says only "Much faster full-text content searches" | **V** | — | changelog, fetched 2026-09-02 |
| §4 politeness | web API: 4 concurrent, `Backoff` honored on any response incl. 2xx | **V** | — | web API docs; `syncAPIClient.js:905`, `:1016-1020` |
| §4 politeness | the local API **has no rate limits** | **P** | claim | true of data endpoints; `/api/local/authorize` is 5 per 60 s |
| §5.2.9 | extraction is usually a cache read, not a parse | **V** | — | hedge present and adequate; `server_localAPI.js:1427-1449` |
| §5.2.4 | pack filename `.zotero-sdt-cache` | **V** | — | `sdt.js:26` @ `9e28eb0` |

### Upstream zoteus

| site | claim in short | verdict | kind | coordinate |
|---|---|---|---|---|
| §5 intro | tokenizer is `/[a-z0-9]+/g` + 29 English stopwords | **R** | claim | `tokenize.ts:67` @ `b05ed69`; fixed by `4f61b2a`, v1.7.2 |
| §5 intro | no `busy_timeout`, no `SQLITE_BUSY` handling in `src/` | **R** | claim | `sqlite-index.ts:124` @ `b05ed69`; `80f8aa0`, v1.7.1 |
| §5 intro | `SCHEMA_VERSION` written at `:26,153`, never read | **R** | claim | read at `sqlite-index.ts:304`; `fd51659`, v1.9.0 |
| §5 intro | `DEFAULT_FULLTEXT_MAX_CHARS = 40_000`, ~1 100-fold truncation | **V** | — | `fulltext-source.ts:11` |
| §5 intro | changing embedder drops every vector at open | **V** | — | `index-manager.ts:544-548` |
| §5 intro | builds crawl `top:true` only | **R** | claim | second crawl at `own-words-source.ts:92`; `d8266f7`, v1.11.0 |
| §5 intro | `clearStore()` sits in the build path | **V** | — | `index-manager.ts:668-669` |
| §5.2.3 | "Upstream does not do this today, **verified**" (own words) | **R** | claim | indexed by default since v1.11.0; the stale fact restated inline |
| §5.2.7 R23 | "**verified defect**: `createSchema` re-stamps before `loadMeta`" | **P** | grade | mechanic intact, the defect it names is fixed (`fd51659`) |
| §5.2.4 | "the Web-API fallback upstream's **#39** chose" | **R** | claim | #39 chose a per-API concurrency default with back-off (`c859407`) |
| §6 | a keyless install fails such a read "rather than sending it anywhere" | **O** | claim | dispatched to `api.zotero.org` under user id 0, rejected server-side |
| §6 | router prefers local, falls back to cloud, not per-call opt-in | **V** | — | `library-router.ts:116-163` |
| §6 | a build pins its transport once and fails rather than re-routing | **V** | — | `build.ts:310-315` |
| §5.1 | upstream chunks below Zotero's minimum only on its 512-char metadata stride | **V** | — | `chunker.ts:7`; `index-manager.ts:70-71` |
| §5.2.4 | header machinery to lift exists at `local-writes.ts` | **V** | — | `local-writes.ts:48-55`, `:97-124` |
| §5.2.5 | the install-failure class of upstream's #38 | **V** | — | `CHANGELOG.md:8-47`, v1.12.0 |
| §5.2.8 | upstream BEGIN-at-first-mutation; 200-item/10 s cadence; his own comment | **V** | — | `sqlite-index.ts:798-801`; `index-manager.ts:854-855`; `build.ts:208-209` |
| §5.2.6 | no entries upstream, so hard predicates ship at item scope | **V** | — | `sqlite-index.ts:681-718` |
| §5.2.6 | MATCH unconstrained, "upstream already does this" | **V** | — | `sqlite-index.ts:761-767`; upstream ships no facet filters at all |
| §5.2.6 | upstream keeps only `content` and concatenates | **V** | — | `fulltext-source.ts:24-25`, `:170-193` |
| §5.2.7 | FTS delete protocol, upstream's correct discipline | **V** | — | `sqlite-index.ts:734`, `:947-949` |
| §5.2.7 | legacy `search-index.json` left in place forever, reverses his decision | **V** | — | `sqlite-index.ts:886-889`; `docs/configuration.md:27` |
| §5.2.7 | any query against an empty index starts a build | **V** | — | `semantic-search.ts:24-26` |
| §5.2.7 | one global `embedderId`, cannot support mixed spaces | **V** | — | `index-manager.ts:467-468` |
| §5.2.8 | stock ≥ v1.7.2 ships `normalizeForSearch` | **V** | — | `tokenize.ts:67`; `4f61b2a` ancestor of the v1.7.2 tag |
| §5.3 | X3a baselines "stock upstream on the **uncapped**" document | **P** | grade | uncapped is a stock *setting*, `ZOTEUS_INDEX_FULLTEXT_MAX_CHARS=0`, not stock behaviour |
| §5.2.6 | `carray` does not exist in `node:sqlite` | **V** | — | probe, node v22.23.1, 2026-09-02, with `json_each` as positive control |
| §5.4 | #10 built in days; #20 → #21/#22/#23 inside one day on 2026-08-27 | **V** | — | `6e4637b`, `2f453d6` |

## What was corrected, and what was not

**Corrected in `SPEC.md` on this branch: 27 sites.** Every wrong claim and
every wrong grade above except two, and those two are marked in place in the
prose rather than left silent.

**Registered and marked, not reworded: 2.** Both sit in §5.2.2, under
concurrent edit by the segmenter work, and both are design decisions rather
than wording repairs: the `min()` pairing, and `indexedPages` saturation. Each
now carries a parenthesis in the design prose saying what is wrong and who owns
the repair, so no reader meets the claim unwarned; both are on `DECISIONS.md`'s
awaiting list with the third finding, X6. The `.zotero-ft-cache` census figures
are likewise flagged in place rather than removed, because unlike the
vocabulary counts they are corroborated by a second site in `DECISIONS.md`.

**Nothing here reverses a ratified reading.** The one candidate — §4 C1's
residue bullet — turned out to *apply* the ratified withdrawal of 2026-08-31 to
a site that withdrawal never reached, so it was corrected rather than escalated.
The 2026-08-31 entry's verdict stands; only its stated reason is wrong, and an
append-only ledger records that here rather than by editing the entry.

## Three faces of one class

The ticket named the class: *a value or behaviour is read from an upstream
summary, adopted as a constant, and cited as though the mechanism around it
came too.* This sweep found it wearing three faces.

**The constant without its guard**, the original: 768 copied as a chunk size
where upstream uses it as a ceiling inside a `min()`. Still the most expensive,
because it changes what gets built.

**The rationale graded as a measurement**, the author's 2026-08-31 addition:
`lexical.js` states a cost in a comment and publishes no figure, and citing it
as a measurement credits the maintainer with numbers he never produced. This
sweep found four more of these, and the worst is not an attribution at all —
C2 cites its own report for vocabulary figures the report does not contain, and
asserts a live-read measurement the same report says it deliberately did not
take.

**The comment cited as behaviour**, new here, and the one that caught this
audit itself. `embeddings.js` carries a comment describing a staleness residue
and, fifteen lines below it, code from a later commit in the same pull request
that closes it. A first pass here read the comment, graded the claim verified
*verbatim*, and committed a coordinate for it — then had to reverse that in the
same branch after reading the function body. Two independent readers reached
two different wrong answers about this one sentence before the code settled it.

The transferable rule is one line: **cite the key, not the comment.** A comment
is the author's account of the code at the moment he wrote it, and nothing in
any toolchain fails when the code moves out from under it.

## The staleness axis, which the ticket did not anticipate

Six of the nine upstream rows are staleness, not misreading: the four facts in
§5's opening list, its restatement in §5.2.3, and the R23 grade. Every one was
**exact when written**. They rot on a clock the audit's original
method could not see: the ticket's instrument is "read the source at a SHA",
which catches a misreading and is blind to a reading that has expired.

Three of the four stale facts in §5's opening paragraph were fixed by the
maintainer *closing this repository's own filings* — #19, #18 and #25. So the
document was quoting his pre-fix code back at him, in a public repository he
reads, as a live diagnosis of his project. That is the same cost the ticket
names for misattribution, arrived at from the opposite direction.

The paragraph carried an honest pin and an honest pointer to `SYNC.md`. Neither
helped, for a structural reason worth keeping: a flat list of seven facts,
pinned once at the top, cannot show a reader which member has moved, and two of
the seven were restated elsewhere in the document **without the pin and marked
"verified"**. A hedge that a later sentence can drop is not a hedge. The
correction splits the list by standing — still true, repaired since, each with
its commit — so the next release strands one row visibly instead of the whole
paragraph silently.

## What would make this cheap to repeat

Ticket 0181 would have made this a standing guard. It was closed as excess
weight on 2026-08-31, on the ground that finding attribution sentences needs
prose read for semantic intent, and that a hard fail on an uncited attribution
"will be fought and then disabled" — the discipline kept instead in the review
of text that leaves the repository. This sweep is evidence for that ruling
rather than against it: the nineteen wrong claims share no vocabulary a grep
could key on, and six were correctly cited and simply expired, which
no presence check can see.

What the sweep does add is one line for that review, and it is cheap because it
binds the citation rather than the sentence: **a coordinate must name a ref,
not only a file and a line.** Every citation here that survived contact carried
`77e2c4b`; the bare `file:line` ones had drifted by up to 180 lines. A reviewer
who asks "at which commit?" catches both failure modes at once — the misreading
and the expiry — where a reviewer who asks "is there a citation?" catches
neither.

The second line is for whoever next writes a paragraph of upstream facts. Pin
per fact, not per paragraph, and split by standing. §5's opening list was
pinned once at the top and honest about it, and it still stranded four facts
silently, because a flat list cannot show a reader which member has moved.
