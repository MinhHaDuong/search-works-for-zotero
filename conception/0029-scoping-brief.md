# Ticket 0029 — scoping brief

**Status: the findings stand; the recommendation is superseded.**

**For:** whoever is finishing ticket 0029.
**Written:** overnight 2026-09-02/03, read-only on code.
**Revised:** 2026-09-03, re-verified against `origin/main` at `34e251f`.
**Subject:** `tickets/0029-the-golden-fixture-corpus-and-a-zotero-f.erg`.

This began as a decision brief recommending that 0029 be decomposed. The author
has since assigned 0029 whole to another worker, so that recommendation is
overtaken and has been moved to the end (§11 and §12) rather than deleted. What
is left at the front is the part with value to someone executing the ticket:
what the corpus is for, what it costs, what the fixture level cannot buy, and
the two things most likely to be got wrong.

---

## 1. Status: what changed, and what was re-checked

**The recommendation is superseded.** §11 argued for a tracker plus five
children with the repository-only child scheduled first. The author assigned
0029 whole on 2026-09-03. The partition boundary in §12 stays on the record
because it is reusable if 0029 is ever split, and because the reasoning about
which layer needs what is worth reading even by someone building all five
layers in one pass.

**`origin/main` moved under this brief, in three places.**

- **`bench/acceptance/durability.py` is now on `origin/main`.** It was absent
  at `1f1aeb3`, when this brief was written; PR #226 merged it. The finding it
  carries is unaffected and was re-checked at `34e251f`: the zoteus adapter
  still declines the two write perturbations
  (`bench/acceptance/adapters/zoteus.py:349`), so the R3 clauses still report
  `not-run` for want of a library the harness may write to. §4 now says so
  itself rather than relying on this correction.
- **PR #226 shifted every goal-1 address in §4**, and spliced
  `**durability.ALL` into the `assertions.py` registry, so that registry now
  carries R3, R13 and R23 as well as R10 and R15. §4's table, its registry
  address and its claim about what `assertions.py` asserts are all refreshed to
  `34e251f`, and §4 states the ref they are current as of.
- **`bench/fixtures/recipe.json` holds 26 documents, not 27.** Commit
  `c99b9e8` ("Record embedder tolerance and drop unlicensed fixture", merged in
  PR #242) removed `hal-04214661` on an author ruling. Seventeen of the 26 are
  hashed; the language split is vi 10, fr 8, en 7, de 1. Every count in this
  brief written as 27 should be read as 26, and §2 carries the corrected
  arithmetic.

**Re-checked at `34e251f` and still true, and this is the whole list.**
`check-slow` is absent from the `Makefile`. `R21` does not appear in `SPEC.md`.
`README.md:251-256` and `:269` still name 0029 as the test home for seven
requirements. The first revision of this brief wrote "nothing else moved" over
this list, which was false: §4's goal-1 addresses had already shifted, and a
blanket claim covered the shift instead of reporting it.

**The one merge conflict was resolved as the union.** This branch's single log
line on 0029 and the author's 2026-09-03 ruling line both append to the same
tail, so the ticket file conflicted when `origin/main` came in. Commit
`2cdcf6f` kept both lines in chronological order, this brief's
`2026-09-02T22:41Z` entry before the `2026-09-03T03:44Z` ruling. Neither
replaces the other, and the branch's diff against the ticket file is exactly
its own one inserted line.

---

## 2. Act on this first: pin `maxChars`, and treat the floor argument as an argument

This is the one number that will bite whoever builds the corpus. It is set by
configuration rather than by the corpus, and the product and the bench driver
already disagree about it by a factor of five.

### The constants, re-verified

Both checkouts carry the same values; only the line numbers differ.

| constant | value | address |
|---|---|---|
| `FULLTEXT_CHUNK_SIZE` | 1200 | `fork/src/features/search/index-manager.ts:70`, `fork-stock/…:58` |
| `FULLTEXT_CHUNK_OVERLAP` | 150 | `fork/src/features/search/index-manager.ts:71`, `fork-stock/…:59` |
| `DEFAULT_FULLTEXT_MAX_CHARS` | 40 000 | `fulltext-source.ts:11`, both checkouts |

Stride is 1200 − 150 = **1 050 characters**. `chunkText`
(`fork/src/features/search/chunker.ts:7`) snaps each cut back to the last space
when that space falls past the halfway mark, so the true stride is a little
under 1 050 and the passage counts below are lower bounds by a passage or two.

40 000 is the **shipped** default, not merely a library default:
`config.ts:186-190` gives `ZOTEUS_INDEX_FULLTEXT_MAX_CHARS` a Zod
`.default(DEFAULT_FULLTEXT_MAX_CHARS)`, and `build.ts:449` reads
`ctx.config.indexFulltextMaxChars`. **`bench/run_build.py:72` overrides it to
200 000.** So a corpus built through the product and the same corpus built
through the bench driver differ fivefold in passage count today, with nothing
recording which was used.

### The arithmetic

Passages per document = ceil(maxChars / 1 050), for any document at least
`maxChars` long.

| maxChars | passages/doc | × 26 docs | 10/P at that size |
|---|---|---|---|
| 40 000 (product default) | 39 | **1 014** | 0,99 % |
| 80 000 | 77 | 2 002 | 0,50 % |
| 200 000 (bench driver default) | 191 | 4 966 | 0,20 % |

Two corrections to the naive multiplication. One record,
`vn-decision-11-2017-qdttg-solar-fit-en`, is nine pages and yields roughly 22
passages rather than 39 at any cap, so the 40 000 row is closer to **997**.
Seven records carry no `page_count` at all; the other eighteen are long enough
that the cap, not the document, sets their passage count.

### The floor argument is an argument, and not a strong one

§5 argues a floor from R34: a ranker returning ten at random satisfies one
query with probability 10/P, which is 5 % at P = 200 and 0,5 % at P = 2 000, so
2 000 is where the top-ten cut becomes a real cut. The arithmetic is right and
the conclusion does not follow.

**It uses the wrong statistic.** R34 is absolute: every pinned answer inside
the first ten. A random ranker therefore passes the *gate* with probability
(10/P)^Q over Q queries, not 10/P. At Q = 40 that is vanishing at 1 014
passages, at 2 000, and at 200 alike. The variable carrying the non-vacuity is
the query count, not the corpus size. §5's own text notices this in one clause
and then credits the corpus size for it.

**It uses the wrong null.** The failure R34 will actually meet is not a random
ranker but a degenerate non-random one: a keyword-only fallback, which the
2026-09-02 overnight briefing records happening silently whenever
`@huggingface/transformers` is absent from the built fork, or a ranker that
returns the same ten items for every query. Corpus size does nothing against
either. Query design and distractor density do.

**And raising the cap is the least useful way to raise P.** The passages a
higher cap adds are further overlapping windows of documents already in the
corpus. They inflate P without adding a competing *document*, which is what a
top-ten cut has to discriminate against. If a larger corpus is wanted, more
documents buy it; a larger cap mostly buys build time.

**No bar is declared anywhere.** Calling 5 % "close to vacuous" and 0,5 % "a
real cut" is a judgement, not a rule. No `SPEC.md` clause and no ruling names a
vacuity threshold, and 0,99 % sits between the two numbers the argument uses to
anchor itself.

### What survives, and it is the part that matters

The consequence stands on firmer ground than the floor:

**The fixture must pin `maxChars` explicitly and record the pinned value in the
export, beside the passage count it produced.** Not because 40 000 is too
small, but because the product ships 40 000 and the bench driver ships 200 000,
so an unpinned corpus is a different corpus depending on who builds it, and a
pinned answer set is valid only over the corpus that produced it. Whether the
pinned value should also exceed 40 000 is a judgement to make deliberately
rather than inherit from this brief's arithmetic.

One consequence for R32, unchanged from §5: pinning the cap above the shipped
default is safe, because `SPEC.md` §5.2.8 binds R32 as a rate rather than a
wall clock. It still has to be written down, since the fixture's rate is then
measured at a cap the product does not ship.

---

## 3. The open question, live and being answered by default: fixture provenance

**Is a fixture library allowed to be generated, or must every fixture document
be drawn from the recipe?**

The 2026-09-02 rulings say a fixture document names a public archive identifier
and never a personal library. Read strictly, that governs the *golden corpus*.
Read as a general rule, it forbids a generated library outright. The repository
already generates fixture content under the opposite reading:
`bench/fixtures/make_index_fixture.mjs` writes 600 synthetic passages with
invented titles, and its header gives the reason, which is that real titles are
document names and the naming ruling keeps those out of anything committed.

**Nothing has ruled on it, and something is answering it anyway.** Commit
`c99b9e8` records a 2026-09-03 author ruling dropping `hal-04214661` from the
recipe: the work is not the author's, the HAL deposit rests on the repository's
distribution authorisation rather than a reusable licence, and the fixture has
no consent from its authors. That is a real ruling, made by the author, and it
is the first one that *removes* a record rather than pinning it.

Two things follow.

**Provenance policy is accreting from cases without being written as a
policy.** Each document is ruled on at the moment it blocks. That is a
reasonable way to unblock a document and a poor way to answer the general
question, and the general question is the one that decides whether a
Zotero-free harness can have a library at all.

**The direction of the case law is not what a strict reading would predict.**
The HAL ruling turns on licence and on authors' consent. A generated library
has neither problem: nobody's work, nobody's consent, no archive. If anything
the ruling is evidence for the generated reading. But that is an inference from
an adjacent ruling, which is the move this repository's own discipline forbids,
so it stays an inference.

My reading, unchanged and still not a ruling: the provenance rule governs
documents whose *content is measured for relevance*, and a generated library
measured for durability and lifecycle falls outside it. Whoever finishes 0029
will settle this by whatever they build, and the settlement will land in code
rather than in `DECISIONS.md` unless it is asked first.

---

## 4. What the corpus is for, and what it is not for

The premise handed to this session was that the corpus serves goal 1's five
assertions and goal 2's five. Read against the code, that premise is wrong in
the first case and half right in the second.

### Goal 1 — five assertions, none needing a corpus or an index

**Every address in this section is as of `origin/main` at `34e251f`.** The
first revision took them at `1f1aeb3`; PR #226 shifted all of them, so they are
refreshed here rather than left for the next reader to chase.

`bench/acceptance/assertions.py` defines R10's and R15's five clauses itself.
Its registry (`ALL`, at `assertions.py:553`) also splices `**durability.ALL`,
so R3, R13 and R23 reach a run through it — one registry for the layer, by
design. The five below are the ones this file defines.

| assertion | address | what it needs |
|---|---|---|
| `check_local_by_default` | `assertions.py:270` | neither. Reads `configure()` and `status()["embedding"]`. |
| `check_no_egress` | `assertions.py:169` | neither. Traces syscalls; the query it passes is the literal string supplied at `run.py:80`. |
| `check_residue_inventory` | `assertions.py:357` | neither. A filesystem diff around `install()`. |
| `check_model_cache_under_declared_roots` | `assertions.py:423` | neither. Queries only to trigger a weight download, and never reads the answer. |
| `check_uninstall_removes_declared_state` | `assertions.py:318` | neither. Sweeps declared roots for survivors. |

**The golden fixture corpus buys goal 1 nothing.** Goal 1 closes at the
fixture level on process lifecycle, egress and filesystem residue, and it
already has its fixtures — the synthetic doubles in
`bench/acceptance/adapters/stubs.py`, which stand in for nothing
Zotero-shaped and are right not to.

### Goal 2 — five assertions, now on `origin/main`, and only two want documents

`bench/acceptance/durability.py` **is on `origin/main`**: PR #226 (branch
`t0579-goal-2-gates`) merged it after the first revision of this brief, which
recorded it as absent. Its registry is at `durability.py:725`, and
`assertions.py` folds that registry into its own.

| assertion | address | what it needs |
|---|---|---|
| `check_edit_recomputes_only_what_changed` | `durability.py:240` | a library the harness may **write to**. |
| `check_identical_resync_recomputes_nothing` | `durability.py:308` | the same. |
| `check_two_processes_both_answer` | `durability.py:392` | a serving index over any content. |
| `check_two_processes_do_not_duplicate_work` | `durability.py:486` | work counters zoteus does not expose. |
| `check_foreign_stamp_ends_up_serving` | `durability.py:556` | a serving index with a non-empty baseline. |

The two R3 assertions are the interesting ones. They drive an
adapter-declared `perturb()` hook (`durability.py:192`), and the zoteus
adapter **declines** it: `bench/acceptance/adapters/zoteus.py:349` raises
`NotImplementedError` because editing an item would write to the author's own
Zotero library, which R15 excludes from derived state. The
blocker is not the absence of a golden corpus. It is the absence of *any*
library the harness owns and may perturb.

That is the finding this brief turns on. A fixture library the harness
creates, injects into and may edit at will removes the R3 blocker outright,
and it needs no pinned answer sets, no licence research and no archive
identifiers to do so. It is a strictly smaller artifact than the golden
corpus, and it sits inside the golden corpus's own delivery path.

The two index-needing assertions (R13-both-answer, R23-foreign-stamp) need a
*serving* index, not a *good* one. The one real-target measurement that
exists, `bench/results/smoke-1.12.0/acceptance-zoteus.json`, ran against a
five-item private library at `/home/haduong/data/Zotero-fresh`
with an index seeded from an uncommitted local sqlite file. That is the
current stand-in, and it is neither committable nor reproducible by anyone
else.

### Who the corpus is actually for

`README.md` lines 251–256 and 269 name ticket 0029 as the test home for
**seven** requirements: R5, R7, R24, R29, R33, R34 (all of goal 4) and R8
(goal 5). Four open tickets are `Blocked-by: 0029` — 0032, 0495, 0581, 0588 —
and two more (0501, 0573) declare a soft dependency. 0581 states the position
plainly: there is nothing to gate until the set is pinned, and the set is not
that ticket's to invent.

So the corpus's customers are goal 4 and the offered spec, not goals 1 and 2.
Its urgency comes from the count of tickets behind it, not from the assertions
that exist today.

### What the currently pinned queries demand: nothing

None of `bench/queries.txt` (16), `queries-short.txt` (20), `queries-x2.txt`
(20), `queries-x2-fr.txt` or `queries-x2-vi.txt` carries a pinned answer set.
Their own headers say what they are — cost and degeneracy populations for FTS5
and stopword measurement. A repository-wide search found no committed
answer-set file of any kind. R7's three MUST languages and R33's three probe
shapes therefore demand everything and the current queries demand nothing;
there is no continuity to preserve, only a set to build.

---

## 5. Size: the build clock, and the argument for 2 000 passages

**Recommendation: pin the fixture at roughly 2 000 indexed passages. That is
the 26 documents now in `bench/fixtures/recipe.json` indexed at 80 000
characters each, and it costs about three minutes to build cold on the
reference machine.** The ceiling below is sound; the floor is retracted, and
the block quote carrying it says so before it is read. Treat 2 000 as a
defensible choice rather than a derived requirement.

### The build clock

The Zotero-free replay removes the two fixed terms a real build pays. Ticket
0500's artifact
(`bench/results/0500-extract-chunk/extract-chunk-throughput.json`) measures
the attachment-page walk at 80,6 s and the `/fulltext?since=0` read at
105,5 ms; the metadata crawl of the running full-library build took 793 s for
7 541 items. A replay reads a committed file instead of all three. What
remains is extract, chunk and embed.

Extract and chunk are measured and negligible: 0,164 ms per passage serial,
0,122 ms at the build's own concurrency (same artifact).

Embed is the whole clock. The directly measured figure for the incumbent, over
600 real passages through the same JavaScript runtime the product loads, is
**88,03 ms per passage**:
`bench/results/0263-cpu-arm/all-minilm-l6-v2__fp32__cpu__home-haduong-data-projets-zoteus-bench-vec-real-passages.txt__fidelity-v1.json`.
fp32 is the right cell because `embeddings.ts:182` calls
`pipeline('feature-extraction', model)` with no dtype, taking the library
default. The q8 and uint8 cells of the same run read 63,33 and 65,56 ms.

So, for N passages on the reference machine:

    build ≈ N × 88,2 ms

     1 000 →  88 s
     2 000 → 176 s
     3 400 → 300 s
    40 000 →  59 min

**Cross-check against a real build.** The 60-item derisk build indexed 3 699
passages in 506 s. Predicted from the two measurements above:
3 699 × 88,03 ms = 326 s, plus the 80,6 s walk = 406 s, plus model load and a
60-item metadata crawl. Measured 506 s. The two routes agree within 20 %, and
the residual is the local-API body fetch at concurrency 2, which is exactly
what the replay deletes. Both figures are per-passage rates derived from
aggregates; the derivation is shown here rather than asserted.

### Why 2 000, and not fewer

A ceiling and a floor bracketed the number. The ceiling stands. The floor is
retracted, and only the ceiling is load-bearing now.

**Ceiling: the build must fit in a wait, not a lane.** At 88 ms per passage,
one hour buys 40 000 passages and five minutes buys 3 400. The corpus is
rebuilt when a document is re-pinned or the embedder changes, not once per
test run, so a three-minute cold build is a coffee and an hour is a
scheduling problem.

> **RETRACTED 2026-09-03.** The floor argument below is kept for the record and
> is not a current recommendation. Its arithmetic is right; the inference from
> that arithmetic to a corpus size is not, for the four reasons §2 sets out.
> Read §2 before pinning any number on the strength of what follows.

> **Floor: R34 must not be satisfiable by accident.** R34 asserts that every
> pinned answer comes back inside the first ten results, absolutely. On a
> corpus of P passages, a ranker returning ten at random satisfies one query
> with probability 10/P. At P = 200 that is 5 % and the gate is close to
> vacuous; at P = 2 000 it is 0,5 %, and across 40 queries a random ranker
> passes the whole set with vanishing probability. A gate whose green is
> reachable without the property it asserts is not a gate, which is the
> argument this repository already applies to positive controls. **2 000
> passages is where the top-ten cut becomes a real cut**, and that, not the
> document count, is the reason for the number.

### How the documents reach a passage count

**Moved to §2 and corrected there.** The constants, the shipped default, the
bench driver's override and the count at each cap now live at the front of this
brief, because they are the thing most likely to be got wrong. The short
version: the passage count is set by `maxChars`, the product ships 40 000, the
bench driver ships 200 000, and the fixture has to pin one of them and record
which.

### The passage-length distribution the ticket asks to pin

The 2026-08-31 log entry requires the corpus to record its own passage-length
distribution, because a rate measured on one distribution does not transfer to
another. Two facts sharpen that requirement.

**Passage length in characters is constant by construction** — 1 200
characters, chunked by character. What varies across the corpus is tokens per
passage, and that varies by script.

**`chunkText` packs by characters while `SPEC.md` §5.2.2 and
`bench/geometry.py` express the geometry in tokens, budget 498.** For English
at roughly four characters per token, a 1 200-character passage is about 300
tokens and fits. For a script at roughly one character per token, the same
passage is about 1 200 tokens, overruns the embedder's window, and its tail is
dropped in silence — the defect ticket 0140's truncation regression
demonstrates (`bench/truncation_regression.mjs`, header). **This is an
arithmetic inference, not a measurement.** The experiment that settles it is
one run of `bench/passage_census.mjs` over a 1 200-character sample per
language with the incumbent tokenizer. It is cheap and needs no Zotero.

If the inference holds, the corpus's Vietnamese and non-Latin-script documents
are not decoration. They are the only thing at fixture level that can make
that truncation visible.

---

## 6. What "Zotero-free" means here: the local HTTP API, and nothing else

Verified by reading `fork-stock/src` at the reviewed baseline (`UPSTREAM`,
`UPSTREAM_REVIEWED_SHA=b05ed69a…`, v1.12.0):

- **The index build reads Zotero only over the local HTTP API.**
  `src/api/local-client.ts` is the whole surface it uses: `/users/0/items` and
  `/items/top`, `/collections/<k>/items`, `/items/<key>`,
  `/items/<key>/children`, `/items/<key>/fulltext`, `/fulltext?since=`,
  `/users/0/groups`, `/collections`, and the `/groups/<id>` prefix
  (`localLibraryPrefix`, `local-client.ts:41`).
- **It does not read `zotero.sqlite`.** No file under
  `src/features/search/` references a Zotero data directory.
- **It does not read the attachment store.** `downloadFileBytes`
  (`local-client.ts:201`, which follows the `/file` 302 to a `file://` URL) is
  called only from `api/attachments.ts`, `tools/annotate.ts` and
  `tools/get-fulltext.ts`, never from the build. Ticket 0500 measured the
  consequence from the other side: the build's source can only serve what
  `/fulltext?since=0` names, so an unextracted attachment is invisible to it.

**So "Zotero-free" is one job, not three: stand in for the local HTTP API.**
Replaying a committed export through a route table is sufficient and complete
for the build path. The SQLite files and the attachment store need no
surrogate. Two consequences follow.

**The fake already exists, and not where 0029's body says it is.** The ticket
refers to "0026's mock local API". Ticket 0026 corrected that on 2026-09-02:
the record/replay fake and the synthetic library were built by ticket **0551**
(closed) as `tests/fixtures/{clock,local-api-replay,synthetic-library}.ts` on
the *fork's* branch, which accumulated into `conductor-integration` and was
never filed as a fork merge request. It is TypeScript, it is not in this
repository, and its canned responses were **synthesized from reading
`local-client.ts` rather than captured from a real profile**. That last point
is a fidelity gap the corpus's own export layer closes, since a real export is
by definition a real capture.

**The naming ruling does not bind this corpus, and that is why it can be
committed at all.** `DECISIONS.md:687`, "no names, only keys", forbids a
committed artifact from naming a document *in the author's library* by title,
creator or filename. The fixture's documents are not in his library by
provenance — the 2026-09-02 ruling 2 forbids exactly that — so `recipe.json`
names Cournot and Baudelaire without offence, as it already does. The ruling
also states that it does not reach passage text or query sets, both flagged
there as a larger, undecided disclosure. **The corpus dissolves that open
question instead of answering it**: a `/fulltext` export of public-archive
documents discloses nothing the archive does not already publish, and pinned
answers over it disclose nothing about what the author reads. That is a second
reason the corpus earns its cost, and it is written down nowhere yet.

---

## 7. What the fixture level cannot buy

`SPEC.md` §5.2.8 and `README.md`'s goals ladder both state the rule: the
library level decides, the fixture stands in for it, and every surrogate
carries a fidelity claim only the library level can renew. Concretely, a green
fixture run leaves all of the following unmeasured.

- **The extraction spread.** The export freezes one client version's
  extraction of one set of bytes. The author's library holds text extracted by
  older Zotero versions over years. The 2026-09-02 probe measured word-set
  Jaccard of 0,39 to 0,61 between the client's text and `pdftotext`'s on the
  same scans; the spread *within* the client's own history is unmeasured.
- **The unextracted attachment.** Ticket 0500 found 59 PDFs with no platform
  text, all of them `linked_url`. Fixture attachments are injected and
  extracted by construction, so the fixture cannot reach that path at all.
- **The attachment mix.** The census
  (`bench/results/0140-passage-census/census.json`) reads 8 700 PDFs, 4 867
  HTML and 63 other, with medians of 35, 5 and 29 passages per attachment. A
  26-document, PDF-dominated corpus has no HTML slice and cannot represent
  that mix.
- **Scale, and every ranking term that depends on it.** The design point is
  567 829 passages (same artifact); the fixture is 2 000. That is a factor of
  284, and every document-frequency term — BM25's IDF, the concentration
  bands, the fusion weights — is a different distribution at fixture scale.
  Ticket 0101's own note records that `index_concentration.mjs` needs N ≥ 400
  before its sampling band is non-empty. Two thousand clears that and clears
  nothing else.
- **Fixed terms hidden by a rate.** Ticket 0500's third finding: a per-passage
  rate hides a fixed term, and on the attachment-page walk a small sample is
  the *pessimistic* measurement. The fixture removes that term entirely, so
  its R32 rate is optimistic in a way the real build is not.
- **The judgement itself.** A pinned answer is somebody's ruling on what
  should come back. On the fixture, that ruling concerns public documents the
  author did not choose to keep. "Works for me" is a claim about the library
  he did choose, and no conjunction of fixture assertions can make it.

The one-line version, for the tracker: **the fixture proves the machinery, the
library proves the promise.**

---

## 8. PR #232 and PR #233: keep both, fold neither

The backlog lead read both as small private instances of the same missing
thing. Half right, and the wrong half is the half that would cost work. PR #233
has since merged at `d179847`; the reading below stands, and what it recommends
for #233 is now what the tree holds.

**Right about the pattern.** All three — PR #232, PR #233 and 0029 — build a
committed substrate plus controls that make a check fire in both directions,
runnable with no Zotero. PR #233's own ticket cites
`bench/fixtures/make_index_fixture.mjs` as its model, and that generator came
from ticket 0101. There is a house pattern here, and it is worth naming in the
tracker.

**Wrong about the content.** They answer different questions.

- **PR #232** (ticket 0598, `tests/test_index_driver_roster_closure.py`) is a
  closure guard over the *bench driver inventory*: it refuses a driver that
  opens a zoteus index without appearing in the roster. It contains no
  document, no query and no answer. Overlap with 0029: none. **Keep as-is.**
- **PR #233** (ticket 0599, `bench/fixtures/make_attachment_fixtures.py`),
  merged at `d179847`, generates eight minimal files, one per container format,
  to exercise content-signature classification. Its question is what Zotero
  does with a container; 0029's question is what retrieval returns. A one-page
  synthetic DOCX carrying a `ZZFMT` token cannot serve an answer set, and a
  licensed 454-page Gallica scan cannot be a minimal format probe. Overlap:
  structural only. It is scoped by tracker 0593, a separate estate. **It landed
  unfolded, which is what this reading asked for.**

**Neither should be re-sized as 0029's first slice**, and the reason is
positive rather than defensive: 0029's first slice, as recommended in §11 (superseded), is
the replay harness, which needs a *library* fixture, not a *format* fixture
and not a *roster* guard.

**On ticket 0101, the premise does not hold.** 0101 closed via PR #224 on
2026-09-02 and now sits at
`tickets/closed/0101-standing-guard-bench-drivers-fixture.erg`. Neither the
ticket nor the PR flags any of its work as belonging to 0029's first slice; it
delivered schema-generation coverage for bench drivers, an orthogonal axis.
What it left 0029 is the *pattern* — a generated fixture, cheap,
deterministic, proven red in both directions — and ticket 0598 is its direct
sequel, not 0029.

---

## 9. Three smaller rulings this brief asks for

**R8 does not belong in 0029.** `README.md:269` assigns R8 — a 15 000-item
library answered, a 15 000-page PDF indexed whole — to ticket 0029. The corpus
can serve neither half. No admitted archive holds a 15 000-page document, and
§5.2.8's RSS gate already carries a synthetic 44 906 152-character document
for exactly this purpose. What §5.2.8 asks of the corpus at that intersection
is narrower than the requirement: *a 15 000-page PDF in a non-Latin script*.
That is a generation parameter on the existing synthetic monster, not a corpus
document. **Move R8 to the RSS-gate child (0582), and leave 0029 owing one
line: the synthetic monster is generated in a non-Latin script.**

**R21 is retired.** The ticket's 2026-08-31 log entry frames R34's absolute
reading against "the stability reading of the same fixture R21 uses". R21 was
retired on 2026-08-31 as apparatus; the stability reading now sits beside R34
in §5.2.8's golden-gate paragraph, and 0581 owns the requirement that a
constructed input make the two readings disagree. Correct the body.

**`check-slow` does not exist.** `SPEC.md:2371` specifies
`check-slow: check rss-gate convergence soak`; the `Makefile` has `check`,
`check-fast` and `lint`, and no `check-slow`. 0029's exit criterion "0026's
golden gate consumes it in `make check`" therefore names the wrong target: a
three-minute index build cannot join a nine-second gate. The golden gate
belongs in `check-slow`, and something has to create it.

---

## 10. Verified against assumed

**Verified by reading source or a committed artifact:** the five goal-1
assertions and their inputs; that `durability.py` was not on `origin/main` when this was written, and is now (see §1);
that the zoteus adapter declines the R3 perturbation, and why; that the index
build touches only the local HTTP API and never the data directory or the
attachment store; the chunk size, the overlap and both max-chars defaults; the
88,03 ms/passage embed figure and that fp32 is the shipped cell; the 80,6 s
attachment walk; the recipe's records, 17 of them hashed (26 records since `c99b9e8`; 27 when this brief was written), and its language
distribution; that `check-slow` does not exist; that R21 is retired; that no
answer set is committed anywhere; that 0101 closed with no 0029 flag on it.

**Derived, and labelled as such:** every per-passage rate in §5 is an
aggregate divided by a count, the 88,03 ms figure's own artifact included. Two
independent routes agree within 20 %, which is a cross-check and not a
measurement.

**Assumed, each worth one experiment:** that a 1 200-character passage
overruns the 498-token budget in a one-character-per-token script (§5, last
subsection), settled by one tokenizer run with no Zotero involved; and that
the `0263-cpu-arm` run was taken on doudou, inferred from its corpus path
rather than from a host field the artifact does not carry.

**Not determined:** whether the fork's `conductor-integration` branch can be
carried into this repository as the harness's replay layer, or whether child A
should write a replay of its own. That is child A's first design decision, and
this brief does not pre-empt it.

---

## 11. SUPERSEDED — the original recommendation

> **Superseded 2026-09-03.** The author assigned 0029 whole to another worker,
> so the decomposition below was not adopted. It is kept because a proposal that
> was overtaken is part of the record, and because the partition boundary in §12
> stays usable if 0029 is ever split. Nothing in §11 or §12 should be read as a
> current recommendation.

**Decompose 0029 into a tracker with five children, split by what each layer
needs that the others do not — a browser and a pair of hands, a live Zotero
and a public library account, the repository alone, the author's own
judgement — and schedule the repository-only child first rather than last.**
That child is the Zotero-free replay harness with a generated library behind
it. It is the only piece of 0029 runnable tonight, it is what every blocked
downstream ticket is actually waiting on, and it delivers something 0029's
body does not currently claim: a library the harness is allowed to write to,
which is what two of goal 2's five assertions are `not-run` for want of today.

The alternative I reject is executing 0029 in its written order — recipe,
injection, export, harness, answer sets. That order is the dependency chain of
the *corpus*, and it puts three human-bound steps in front of the one piece of
engineering that unblocks other work. It also front-loads the two steps most
likely to stall: ten of the recipe's twenty-six documents sit behind archive
challenge pages only a browser can clear (`bench/fixtures/README.md`, "What
the recipe holds"), and the injection step needs doudou's Zotero idle, which
is the scarcest resource in the project.

One further recommendation, smaller: **drop R8 from 0029's charter.** See §9.

---

## 12. SUPERSEDED — the proposed partition

> **Superseded 2026-09-03**, with §11. Kept for the partition boundary, which
> stays usable if 0029 is ever split, and for the per-child list of what each
> layer needs, which is worth reading even when one worker builds all five.

0029 is a monster by the standing test: fifteen exit criteria, three layers,
seven requirements, four blocked tickets behind it, and at least three
separate sign-off units bundled — a licence-and-provenance judgement, a piece
of engineering, and a relevance judgement only the author can make. Its
dependency chain is in its prose rather than declared.

**Partition boundary: what each layer needs that the others do not.** A
browser and a pair of hands; a live Zotero and a public library account; the
repository alone; the author's judgement. That boundary is mechanical once
stated, and it puts each child in exactly one sign-off unit.

Proposed shape, following the house style of 0593 → 0599/0600/0601 and
0026 → 0578–0582: tracker edited in place, a `## Children` section, wave order
stated once, invariants stated once in the tracker and pointed at by each
child, and `Blocked-by` naming the real sibling prerequisite and never the
tracker.

| child | scope | needs | `Blocked-by` |
|---|---|---|---|
| **A. The replay harness and its generated library** | A Zotero-free index build in `bench/`, driven by a route-table replay of the local API; a generated library large enough to serve as its positive control; a fail-control proving the harness refuses a malformed route. Delivers the writable fixture library that unblocks goal 2's R3. | the repository | *nothing* |
| **B. Finish the source recipe** | Pin by browser the 10 challenge-blocked hashes; add the missing SHOULD-tier languages and the non-Latin-script document; record each set-aside with its stated reason. | a browser, hands | *nothing* |
| **C. Injection into a public Zotero library** | The injection script, the collection, linked-file attachments, the client version and the two indexing preferences recorded. | Zotero idle, a library account | B |
| **D. The export snapshot** | Items JSON, `/fulltext` JSON per attachment, the passage-length distribution, and the re-pin-as-re-export procedure. | Zotero idle | C |
| **E. Queries and pinned answer sets** | ~40 queries with facet, language lane and carrying signal; R33's three probe shapes; R29's cross-lingual lanes with the negative control; R34's absolute reading beside the stability reading. | the author's judgement | A, D |

Wave order: **A and B run in parallel now. C then D. E last.** A is the only
child runnable tonight, and it is the one with dependants.

Tracker exit criteria: each child closed, plus one integration review that
re-reads the five diffs together and confirms one corpus rather than five
artifacts.

**Carry these out at decomposition, not after:** repoint 0032, 0495, 0581 and
0588 from 0029 to the child each actually waits on. 0581, 0588 and 0495 wait
on E. 0032 waits on A, because the offered spec needs a runnable harness
rather than pinned answers — the offer travels at fixture level, and the
answers are the part that never does.
