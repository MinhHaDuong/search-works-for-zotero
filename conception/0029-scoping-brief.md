# Ticket 0029 — scoping brief

**For:** the author, to decide from.
**Written:** overnight 2026-09-02/03, read-only on code.
**Subject:** `tickets/0029-the-golden-fixture-corpus-and-a-zotero-f.erg`.

Every lane of the 2026-09-02 overnight run was rate-limited by needing a real
index or a real Zotero. 0029 is the item that removes that constraint, and it
was fenced off pending this scoping. Nothing here changes code; the
measurements cited come from committed artifacts and from source, and none was
re-run.

---

## 1. Recommendation

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
likely to stall: ten of the recipe's twenty-seven documents sit behind archive
challenge pages only a browser can clear (`bench/fixtures/README.md`, "What
the recipe holds"), and the injection step needs doudou's Zotero idle, which
is the scarcest resource in the project.

One further recommendation, smaller: **drop R8 from 0029's charter.** See §7.

---

## 2. What the corpus is for, and what it is not for

The premise handed to this session was that the corpus serves goal 1's five
assertions and goal 2's five. Read against the code, that premise is wrong in
the first case and half right in the second.

### Goal 1 — five assertions, none needing a corpus or an index

`bench/acceptance/assertions.py` on `origin/main` asserts R10 and R15 only.
Its registry is at `assertions.py:523`.

| assertion | address | what it needs |
|---|---|---|
| `check_local_by_default` | `assertions.py:244` | neither. Reads `configure()` and `status()["embedding"]`. |
| `check_no_egress` | `assertions.py:143` | neither. Traces syscalls; the query it passes is the literal string supplied at `run.py:69`. |
| `check_residue_inventory` | `assertions.py:331` | neither. A filesystem diff around `install()`. |
| `check_model_cache_under_declared_roots` | `assertions.py:397` | neither. Queries only to trigger a weight download, and never reads the answer. |
| `check_uninstall_removes_declared_state` | `assertions.py:292` | neither. Sweeps declared roots for survivors. |

**The golden fixture corpus buys goal 1 nothing.** Goal 1 closes at the
fixture level on process lifecycle, egress and filesystem residue, and it
already has its fixtures — the synthetic doubles in
`bench/acceptance/adapters/stubs.py`, which stand in for nothing
Zotero-shaped and are right not to.

### Goal 2 — five assertions, on an open PR, and only two want documents

`bench/acceptance/durability.py` is **not on `origin/main`**. It lives in open
PR #226 (branch `t0579-goal-2-gates`); registry at `durability.py:725`.

| assertion | address | what it needs |
|---|---|---|
| `check_edit_recomputes_only_what_changed` | `durability.py:240` | a library the harness may **write to**. |
| `check_identical_resync_recomputes_nothing` | `durability.py:308` | the same. |
| `check_two_processes_both_answer` | `durability.py:392` | a serving index over any content. |
| `check_two_processes_do_not_duplicate_work` | `durability.py:486` | work counters zoteus does not expose. |
| `check_foreign_stamp_ends_up_serving` | `durability.py:556` | a serving index with a non-empty baseline. |

The two R3 assertions are the interesting ones. They drive an
adapter-declared `perturb()` hook (`durability.py:192`), and the zoteus
adapter **declines** it: the PR's diff to `bench/acceptance/adapters/zoteus.py`
raises `NotImplementedError` because editing an item would write to the
author's own Zotero library, which R15 excludes from derived state. The
blocker is not the absence of a golden corpus. It is the absence of *any*
library the harness owns and may perturb.

That is the finding this brief turns on. A fixture library the harness
creates, injects into and may edit at will removes the R3 blocker outright,
and it needs no pinned answer sets, no licence research and no archive
identifiers to do so. It is a strictly smaller artifact than the golden
corpus, and it sits inside the golden corpus's own delivery path.

The two index-needing assertions (R13-both-answer, R23-foreign-stamp) need a
*serving* index, not a *good* one. The one real-target measurement that
exists, `bench/results/smoke-1.12.0/acceptance-zoteus.json` on the PR branch,
ran against a five-item private library at `/home/haduong/data/Zotero-fresh`
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

## 3. Size: 2 000 passages, and the arithmetic

**Recommendation: pin the fixture at roughly 2 000 indexed passages. That is
the 27 documents already in `bench/fixtures/recipe.json` indexed at 80 000
characters each, and it costs about three minutes to build cold on the
reference machine.**

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

A ceiling and a floor bracket the number. The floor is the one that matters.

**Ceiling: the build must fit in a wait, not a lane.** At 88 ms per passage,
one hour buys 40 000 passages and five minutes buys 3 400. The corpus is
rebuilt when a document is re-pinned or the embedder changes, not once per
test run, so a three-minute cold build is a coffee and an hour is a
scheduling problem.

**Floor: R34 must not be satisfiable by accident.** R34 asserts that every
pinned answer comes back inside the first ten results, absolutely. On a corpus
of P passages, a ranker returning ten at random satisfies one query with
probability 10/P. At P = 200 that is 5 % and the gate is close to vacuous; at
P = 2 000 it is 0,5 %, and across 40 queries a random ranker passes the whole
set with vanishing probability. A gate whose green is reachable without the
property it asserts is not a gate, which is the argument this repository
already applies to positive controls. **2 000 passages is where the top-ten
cut becomes a real cut**, and that, not the document count, is the reason for
the number.

### How 27 documents reach 2 000 passages

The passage count is set by a configuration knob, not by the corpus. Verified
in `fork-stock/src/features/search/`:

- `index-manager.ts:58-59` — `FULLTEXT_CHUNK_SIZE = 1200`,
  `FULLTEXT_CHUNK_OVERLAP = 150`. Stride 1 050 **characters**.
- `fulltext-source.ts:11` — `DEFAULT_FULLTEXT_MAX_CHARS = 40_000` per item.
- `bench/run_build.py:72` — the bench driver overrides it to 200 000.

Passages per document = ceil(maxChars / 1 050). So:

| maxChars per item | passages/doc | × 27 docs | build |
|---|---|---|---|
| 40 000 (product default) | 39 | 1 053 | 93 s |
| **80 000 (recommended)** | **77** | **2 079** | **183 s** |
| 200 000 (bench driver default) | 191 | 5 157 | 454 s |

**At the product default the fixture lands under the R34 floor.** The corpus
must therefore pin the cap above the shipped default and record it in the
export. That is safe for R32, which `SPEC.md` §5.2.8 binds as a rate rather
than a wall clock, but it has to be written down: the fixture's rate is
measured at a cap the product does not ship.

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

## 4. What "Zotero-free" means here: the local HTTP API, and nothing else

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

## 5. What the fixture level cannot buy

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
  27-document, PDF-dominated corpus has no HTML slice and cannot represent
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

## 6. PR #232 and PR #233: keep both, fold neither

The backlog lead read both as small private instances of the same missing
thing. Half right, and the wrong half is the half that would cost work.

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
- **PR #233** (ticket 0599, `bench/fixtures/make_attachment_fixtures.py`)
  generates eight minimal files, one per container format, to exercise
  content-signature classification. Its question is what Zotero does with a
  container; 0029's question is what retrieval returns. A one-page synthetic
  DOCX carrying a `ZZFMT` token cannot serve an answer set, and a licensed
  454-page Gallica scan cannot be a minimal format probe. Overlap: structural
  only. It is scoped by tracker 0593, a separate estate. **Keep as-is.**

**Neither should be re-sized as 0029's first slice**, and the reason is
positive rather than defensive: 0029's first slice, as recommended in §1, is
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

## 7. Three smaller rulings this brief asks for

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
constructed input make the two readings disagree. Correct the body on
decomposition.

**`check-slow` does not exist.** `SPEC.md:2370` specifies
`check-slow: check rss-gate convergence soak`; the `Makefile` has `check`,
`check-fast` and `lint`, and no `check-slow`. 0029's exit criterion "0026's
golden gate consumes it in `make check`" therefore names the wrong target: a
three-minute index build cannot join a nine-second gate. The golden gate
belongs in `check-slow`, and something has to create it.

---

## 8. The proposed partition

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

---

## 9. Verified against assumed

**Verified by reading source or a committed artifact:** the five goal-1
assertions and their inputs; that `durability.py` is not on `origin/main`;
that the zoteus adapter declines the R3 perturbation, and why; that the index
build touches only the local HTTP API and never the data directory or the
attachment store; the chunk size, the overlap and both max-chars defaults; the
88,03 ms/passage embed figure and that fp32 is the shipped cell; the 80,6 s
attachment walk; the recipe's 27 records, 17 of them hashed, and its language
distribution; that `check-slow` does not exist; that R21 is retired; that no
answer set is committed anywhere; that 0101 closed with no 0029 flag on it.

**Derived, and labelled as such:** every per-passage rate in §3 is an
aggregate divided by a count, the 88,03 ms figure's own artifact included. Two
independent routes agree within 20 %, which is a cross-check and not a
measurement.

**Assumed, each worth one experiment:** that a 1 200-character passage
overruns the 498-token budget in a one-character-per-token script (§3, last
subsection), settled by one tokenizer run with no Zotero involved; and that
the `0263-cpu-arm` run was taken on doudou, inferred from its corpus path
rather than from a host field the artifact does not carry.

**Not determined:** whether the fork's `conductor-integration` branch can be
carried into this repository as the harness's replay layer, or whether child A
should write a replay of its own. That is child A's first design decision, and
this brief does not pre-empt it.

---

## 10. The question I most want answered first

**Is child A allowed to generate its library, or must every fixture document
come from the recipe?**

The 2026-09-02 rulings say a fixture document names a public archive
identifier and never a personal library. Read strictly, that governs the
*golden corpus*. Read as a general rule, it also forbids child A's generated
library — and child A's whole value is that it needs no archive, no browser
and no Zotero.

The repository already generates fixture content under a different reading:
`bench/fixtures/make_index_fixture.mjs` writes 600 synthetic passages with
invented titles, and its header gives the reason — real titles are document
names, which the naming ruling keeps out of anything committed.

So the two rules point opposite ways depending on which artifact is in view,
and the answer decides whether the recommended first slice exists at all. My
reading is that the provenance ruling governs documents whose *content is
measured for relevance*, and that a generated library measured for durability
and lifecycle falls outside it. That is my reading and not a ruling, and it is
the one thing I would not proceed on without you.
