# ACCEPTANCE-0036 — dossier for the one open exit criterion

Ticket `tickets/0036-rewrite-requirements-constraints-and-des.erg`, `Label:
needs-human`. Five criteria ticked; one open:

> `[ ] The author reads all three and accepts the voice; any veto lands in
> DECISIONS.md first`

This report exists to make that read cheap and to say honestly whether the
criterion is met. Nothing in the repo was edited to produce it. Every count
below comes from a script run against the files; the scripts are in
`/tmp/acc0036/` and are named where they matter.

A caution on section 3, stated up front. It is written by an LLM judging
whether prose still sounds like an LLM, which is the one judgement it is worst
placed to make by impression. The section therefore rests on measured rates
against a control: 951 words of the author's own prose, committed to this repo
on 2026-08-28 (`3a99103`, `b69ce9d`, `a108d54`, all `README.md`). That control
is the strongest evidence available and it is not perfect — a README is a
different genre from a specification.

---

## 1. What changed

Two commits did the work, both on 2026-08-27, both authored by Claude. The
pre-rewrite state is `7d4db23` (2026-08-26).

| commit | time | REQUIREMENTS | CONSTRAINTS | DESIGN |
|---|---|---|---|---|
| `72b4068` the rewrite | 08:37Z | 173+ / 163− | 105+ / 85− | 738+ / 662− |
| `ea0a2e0` the prose pass | 11:25Z | 50+ / 39− | 53+ / 42− | 160+ / 114− |
| combined vs `7d4db23` | | 184+ / 163− | 117+ / 86− | 784+ / 662− |

The deletion counts are the honest measure of scope: 662 of DESIGN.md's 716
pre-rewrite lines were replaced (92 %), 163 of REQUIREMENTS.md's 185 (88 %),
85 of CONSTRAINTS.md's 113 (75 %). This was a rewrite, not an edit pass.

Since `ea0a2e0`, REQUIREMENTS.md and CONSTRAINTS.md have not been touched at
all. DESIGN.md took 28+ / 15− across two upstream-sync commits (`c196265`,
`b3cd8dc`) that carried it to v1.9.0 and PR #25. Those are ticket 0015's work,
not 0036's, and section 2 treats them separately.

Sizes: 9 873 words before, 10 435 after (1 849 + 1 142 + 7 444). The
documents grew 6 % while shedding the panel forensics, because glosses and
sentence splits cost words.

**REQUIREMENTS.md.** The italic preamble became an `## Intro` section. The
R-list was purified: D3, D5 and D6 left the requirements and moved to the
resolved-decisions table, each keeping its full sentence rather than being
compressed to a label — D3's table row now carries the whole serve-stale
sentence that used to sit under "Custody and lifecycle". Abbreviations were
expanded in place (`FR/DE/VI/EL/RU` to the five language names, `AR/HE` to
Arabic and Hebrew, `10k`/`15k` to `10 000`/`15 000`). Section headings gained
`###` levels. Median sentence length fell from 46 to 31 words.

**CONSTRAINTS.md.** Same preamble-to-Intro move. C1's derivation graph was
turned from a right-to-left arrow chain into a top-down bulleted chain and the
word "key" was given a definition at first use. Two terms of art that the
document had been using bare — "scouts" and "panel" — were glossed. Median
sentence length fell from 31 to 21 words, the largest relative improvement of
the three.

**DESIGN.md.** The Intro is new. Section 1 was cut from a three-part
verdict-by-verdict record (survived / amended / died, 94 lines, ten numbered
kills) to a 72-line narrative "What changed since v1", with an explicit
pointer to git history and `panel/cycle2/` for the full record. Every
`(graft: … lens, N MAJOR repairs applied)` heading suffix is gone. So is every
critic attribution: a grep for `graft`, `corpus-critic`, `concurrency-critic`,
`query-critic`, `operator-critic`, `custody-critic`, `derivation-critic`,
`SCOUTS`, `kill N`, and bare `M1`/`F2`/`m2` labels returns **zero hits** across
all three documents. Sections 2.1 through 2.9, 3, 4 and 5 kept their numbers
and their argument; the prose inside them was re-sentenced.

---

## 2. Did meaning survive?

Verified independently of the ticked box, by four mechanical passes plus a
close read of every section of DESIGN.md against its pre-rewrite text.

**Result: no requirement, threshold, budget or decision changed in substance.
No R-, C- or D-number was lost. No new ruling was legislated.**

### 2a. Numbers

`/tmp/acc0036/numset.py` normalises thousands separators, extracts every
numeric token with its unit, and reports the set difference between
`7d4db23` and `ea0a2e0` (the rewrite's own endpoint, so upstream-sync edits
do not pollute the comparison).

| document | tokens only in pre | tokens only in post | verdict |
|---|---|---|---|
| REQUIREMENTS.md | `15k`, `100%` | `15000`, `10000`, `100 %` | notation only |
| CONSTRAINTS.md | `20` | — | numeral to word |
| DESIGN.md | `5%`, `10%`, `50%`, `§3.2`, `§3.3`, `§3.6`, `§3.7`, `§2.10` | `5 %`, `10 %`, `50 %`, `100 %`, `32 MB`, `70 MB`, `0031` | notation, v1 refs, new gloss |

Every one accounted for:

- `15k` became `15 000`, `10k` gained `10 000` beside it, `100%` became
  `100 %`, `5%`/`10%`/`50%` gained their space. House style, same values.
- CONSTRAINTS' `~20` became "Some twenty other AI plugins". Same value, now
  invisible to any numeric sweep. See the nit in 2e.
- `§3.2`, `§3.3`, `§3.6`, `§3.7`, `§2.10` were references to **v1's** section
  numbers, carried in the old §1 forensics ("v1's §3.7 sentence", "the disk
  line is recomputed under the new geometry (§2.10)"). §1 no longer narrates
  v1 section by section, so they went with it. This document's own headings
  are intact: §1, §2, §2.1–2.9, §3, §4, §5, all present.
- `32 MB` / `70 MB` are the same figures pre-rewrite wrote unitless as
  "70 (Node) + 32 (cache)". Units added.
- `0031` is a real ticket (`tickets/0031-frac-vec-calibration-from-library-derive.erg`).
  Pre-rewrite §2.6 said calibration was "deferred to its own ticket"; the
  rewrite names which. An improvement in traceability, not a new decision.

Every threshold survives verbatim. Checked individually against the pre-rewrite
text: recall@30 ≥ 0.98, pool ≤ 32×topK, scan+rerank ≤ 400 ms at 650k; X2's
~500 ms and ~50 % document frequency; X7's 50 ms at 30k entries; X4's
1k/5k/20k/100k ladder and 150 ms p95; X5's 45/50, 40–44, < 40 bands; golden
mean Jaccard ≥ 0.8, ≤ 5 % below 0.35, hard floor 0.2, `identical_ordered`
22/60, measured minimum 0.25; soak p95 ≤ 1.5 s, WAL ≤ 256 MB, lease migration
< 30 s; TTL 20 s, election cadence 10 s, gate 30 s; `nice 19`; 200-item/10 s
persist cadence; 2 s idle; > 10 % dead rows; chunk geometry 120/768/48;
K = ceil(median passages per item, floor 16) with both 63→K=64 and ~25
readings stated; disk ~0,8–0,9 GB against v1's 2,3 GB, float32 +~0,35 GB; RAM
~100 MB, ~220–250 MB, ~250 MB steady, ≤ 500 MB transient, ~690 MB
whole-machine; warm query 300–700 ms typical, 3 s hard; deletion every 10th
tick, ≤ ~10 min; 584 of 8 037; 44 906 152 chars; 2 084,9 MiB; 374 ms; 1 301
codepoints; 92,7 %.

`make figures` passes: **93 pairs checked, 71 anchored, 22 presence-only,
0 stale**. `make lint` clean, `make check-fast` 15 passed. Exit criterion 5
confirmed independently.

### 2b. Identifiers

`/tmp/acc0036/ids.py` diffs the sets of R-, C-, D-, X- and §-numbers.

| document | R | C | D | X | § |
|---|---|---|---|---|---|
| REQUIREMENTS.md | 28 → 28 | 1 → 1 | 11 → 11 | — | 3 → 3 |
| CONSTRAINTS.md | 3 → 3 | 4 → 4 | — | 2 → 2 | 3 → 3 |
| DESIGN.md | 23 → 23 | 2 → 3 | 9 → 8 | 9 → 9 | 18 → 13 |

Two entries need explaining, and neither is a loss of meaning:

- **D4 no longer appears in DESIGN.md.** Pre-rewrite §2.2 read "D4-merged
  without the column makes R15's delete an R12 violation". The current text
  reads "a merged index without the column would turn R15's delete into an R12
  violation". The argument is intact and now readable; only the D-number
  pointer is gone. D4 remains in REQUIREMENTS.md's decisions table. This is a
  traceability nit, not a substance change.
- **C1 is newly cited in DESIGN.md** at L165 and L294, where the pre-rewrite
  text said "SCOUTS mandates" and "the mixed-sequence trap". Replacing an
  internal source label with the constraint number is exactly what the ticket
  asked for.

The five lost § references are the v1 numbers already accounted for in 2a.

### 2c. Code identifiers

`/tmp/acc0036/toks.py` diffs every backticked span. Eighteen appear only
pre-rewrite, ten only post. All are reformatting (`done|empty|quarantined` to
`done | empty | quarantined`), unit additions, or renames of internal jargon
(`seg/1` and `(text_hash, seg_id+ver, …)` now spell out "segmenter
id+version"). Two are substantive and both are additions: `4f61b2a` /
`6e4637b` / `bb414df` (the merge SHAs, added post-rewrite by the upstream-sync
commits) and `DELETE FROM passages`.

One genuine simplification: `?since=item_watermark@(oid,lib)` became
`?since=item_watermark`. The `(oid, lib)` scoping did not vanish — it moved
into the sentence: "the watermark scoped to (oid, lib)". Verified at DESIGN.md
L286–L290.

### 2d. Against DECISIONS.md — did the rewrite legislate?

Cross-checked every decision-shaped sentence in the three documents against
DECISIONS.md's ratified entries and its three awaiting-ratification questions.

| claim | DECISIONS.md source | verdict |
|---|---|---|
| Budgets: 1 core, 300 MB, 500 MB, killable worker | 2026-08-26 "the sheet, as agreed", verbatim | intact |
| Three rulings (entry, record, boundaries) | three 2026-08-26 entries | REQUIREMENTS' wording tracks the ledger's; nothing added |
| D1–D11 table rows | 2026-08-26 "ratified by delegation" | all eleven present, resolutions unchanged |
| Seven out-of-scope declarations | same entry | all seven present |
| R26 prefix granularity flagged vetoable | awaiting-ratification #1 | flagged in REQUIREMENTS R26 and DESIGN §2.3 |
| 300 MB scope under N processes | awaiting-ratification #2 | flagged in CONSTRAINTS C3, DESIGN §2.9, both figures stated |
| R20 cadence and fixture | awaiting-ratification #3 | flagged in REQUIREMENTS R20 and DESIGN §2.8 |
| Two PRs in flight; six ratified, five live; three-week sunset | 2026-08-26 and 2026-08-27 entries | DESIGN §4 states the shape and points at DECISIONS.md for the terms, as the entry requires |

**Nothing in the three documents asserts a ruling absent from DECISIONS.md.**
Where the rewrite added a sentence, it added an explanation, not a decision.
Two examples, both checked against the pre-rewrite text and the design:

- R26 gained "the newest N items, never a gap in the middle". That is a
  restatement of "prefix", not a new granularity claim; the granularity is
  still deferred to §2.3 and flagged vetoable.
- The REQUIREMENTS Intro gained "A 'stage' below is one step of the indexing
  pipeline: record, extract, chunk, embed." Four stages, and DESIGN §2.1 does
  list four stage keys (record, extract, chunk, embed). Accurate — but see the
  nit below.

### 2e. Nits found while verifying — none blocking

1. **CONSTRAINTS.md is not in the figure guard's document map.** `PROSE` in
   `bench/check_figures.py` covers STATE, README, SYNC, DESIGN, REQUIREMENTS
   and four tickets. CONSTRAINTS.md carries 584 / 8 037, 410, 0..25 036,
   374 ms, 120/768/48 and both RAM budgets, and none of them is anchored. A
   re-measurement would not name a single CONSTRAINTS.md site to update. This
   predates 0036 and is not its defect, but 0036 is what made CONSTRAINTS.md
   the document a reader is asked to trust.
2. **US thousands separators survive in one block.** The rewrite fixed
   `1,100`, `1,200`, `1,850`, `4,096`, `44,906,152` and `1,000`, but left the
   §2.8 coverage-sentence example untouched: DESIGN.md L560–L572 carries
   `7,541`, `5,561`, `6,100` (twice), `2,101`, `1,850` and a bare `100%`. Eight
   lines, one contiguous block.
3. **"Some twenty other AI plugins"** (CONSTRAINTS.md L66) turns a measured
   `~20` into a word. Harmless in itself; it removes the figure from every
   numeric sweep, including any future guard.
4. **The "stage" gloss reads against C4's "three queues".** REQUIREMENTS'
   Intro names four stages; CONSTRAINTS C4 says "while all three queues run"
   and the structural hint says "three asynchronous processes". Both are
   correct at their own level — the record stage has no queue of its own — but
   a reader meeting both in one sitting will stop. Worth one clause.
5. **Two rhetorical lines were dropped with the forensics**, both harmless:
   "a PR that removed it would be caught by the person who wrote it" (§2.5) and
   "the same unwritability move v1 used for the 0012 transposition" (§2.4).
6. **One error was silently corrected**: §5's closing said "one of five
   experiments" pre-rewrite while §3 lists X1 through X7. The current text says
   "an experiment with a decision rule (§3)". A repair, recorded here so it is
   not mistaken for drift.

---

## 3. Does the voice claim hold?

The standard is the author's own: *"the house style is purely llm at the
moment, not my voice yet."* The question is therefore not "does this text
contain LLM tics from a generic list" but "does it read as his".

### 3a. The tic register — clean

`/tmp/acc0036/tics.py` runs 35 patterns over each document: the
antithesis-reversal family, empty intensifier openers, the banned vocabulary
(delve, tapestry, landscape, realm, robust, seamless, leverage, boasts,
underscores, testament to, game-changer), the panorama adjectives
(comprehensive, holistic, multifaceted, nuanced), the transition drumbeat,
importance inflation, weak copulas, filler verbs of inquiry, hedging stacks,
authorial winks, and misused structure words.

| pattern family | REQUIREMENTS | CONSTRAINTS | DESIGN |
|---|---|---|---|
| "not just/only X but Y" | 0 | 0 | 0 |
| "isn't X, it's Y" | 0 | 0 | 0 |
| empty intensifier openers | 0 | 0 | 0 |
| banned vocabulary (12 terms) | 0 | 0 | 0 |
| panorama adjectives (4 terms) | 0 | 0 | 0 |
| Moreover / Furthermore / Additionally / Notably | 0 | 0 | 0 |
| crucial / critical / vital / essential / key-as-adjective | 0 | 0 | 0 |
| serves as / acts as / plays a role in | 0 | 0 | 0 |
| unpack / explore / dive deeper | 0 | 0 | 0 |
| hedging stacks, life-coaching, winks, coda/overture | 0 | 0 | 0 |
| "significant" without a test | 0 | 0 | 0 |
| **"X, not Y" appositive** | **9** | **3** | **9** |

Only one pattern fires, and it is not a defect. The author's own README uses
it twice in 951 words: "one means, not the definition of success"; "the
current working vehicle and upstream contribution target, not the project
identity". Per 1 000 words the rate is author 2,1, REQUIREMENTS 4,9,
CONSTRAINTS 2,6, DESIGN 1,2. DESIGN sits below the control. The construction
is in his voice; it is retired as evidence.

On the standard tic register the documents are **clean**. That is a real
result and the prose pass earned it.

### 3b. The register that is left — measured against the author

Tic absence is not voice presence. `/tmp/acc0036/rates.py` measures the
punctuation and register signature per 1 000 words. Control is the 951-word
author sample; pre-rewrite figures are shown so the direction of travel is
visible.

| per 1 000 words | **author** | REQ pre → now | CON pre → now | DES pre → now |
|---|---|---|---|---|
| **em-dash** | **3,2** | 34,3 → **23,3** | 22,5 → **21,9** | 24,4 → **22,2** |
| semicolon | 9,5 | 19,7 → 11,9 | 24,7 → 10,5 | 20,7 → **24,0** |
| mid-sentence colon | 3,2 | 3,2 → 4,9 | 11,2 → 9,6 | 9,2 → 10,3 |
| parentheticals | 16,8 | 17,1 → 13,5 | 28,1 → 21,0 | 30,1 → 20,4 |
| bold spans | 7,4 | 39,3 → 28,1 | 5,6 → 2,6 | 20,5 → 17,2 |
| meta-honesty words | 2,1 | 3,8 → 3,8 | 4,5 → 3,5 | 5,4 → 5,5 |

Structural measures, from `/tmp/acc0036/struct.py` and `emdash.py`:

| | **author** | REQ pre → now | CON pre → now | DES pre → now |
|---|---|---|---|---|
| median sentence, words | **23** | 46 → **31** | 31 → **21** | 30 → **26** |
| sentences over 60 words | 1 of 34 | 7 of 28 → 4 of 48 | 5 of 23 → 4 of 40 | 27 of 138 → 22 of 240 |
| units with > 1 em-dash | **4 %** | 16 % → 23 % | 13 % → 19 % | 41 % → **32 %** |
| bold-lead bullets | 6 of 6 | 41 of 41 → 38 of 38 | 0 of 12 → 0 of 18 | 48 of 48 → 36 of 61 |

Three findings.

**The sentence-splitting worked.** Median sentence length fell in all three,
CONSTRAINTS by a third. Counting clauses rather than sentences, DESIGN went
from 25,4 words per clause to 17,8 — a 30 % fall. On the dimension the prose
pass targeted, it delivered.

**The em-dash signature did not move, and it is the largest single divergence
from the author.** He writes 3,2 em-dashes per 1 000 words. The three
documents write 22 to 23, **seven times his rate**, and the rewrite barely
moved that ratio (pre-rewrite: 22 to 34). REQUIREMENTS and
CONSTRAINTS got *worse* by the per-unit measure (16 % → 23 %, 13 % → 19 % of
units carrying more than one), because telegraphic fragments were expanded
into sentences jointed with dashes rather than broken into two. Sample sites:
REQUIREMENTS L52, L61; CONSTRAINTS L121, L138; DESIGN L379 (eight in one
paragraph), L47, L80, L96, L190, L451.

**DESIGN's semicolon rate rose, from 20,7 to 24,0 — two and a half times the
author's 9,5.** Combined with the em-dash figure this says what the rewrite
actually did to DESIGN: it broke long sentences at their weakest joints and
re-punctuated the rest, leaving the clause-stacking syntax intact. The result
is shorter sentences built the same way.

Two smaller register gaps. Meta-commentary about the document's own honesty
("stated honestly", "said out loud", "for the record", "not laundered",
"disclosed", "deliberately") runs at 5,5 per 1 000 words in DESIGN against the
author's 2,1 — 41 instances. And DESIGN.md still closes on a summary that
restates the body (L843–L852: "The bet: … Cycle 2 adds four things", then four
one-sentence beats). The pre-rewrite version had the same paragraph as one
long sentence; the rewrite made the four-beat cadence more audible, not less.
REQUIREMENTS.md's 38-of-38 bold-lead bullets are the correct form for a
numbered requirements list and are not counted against it; DESIGN's 36 of 61
are a mixed case where several bold leads stand in for topic sentences.

### 3c. Verdict on the voice

**Partly met.** The prose pass removed the panel jargon completely and the
standard LLM tic register completely, and it shortened the sentences
measurably. Against the author's own prose, one signature is unchanged and
large: the documents are punctuated with em-dashes at seven times his rate,
and DESIGN compensated by adding semicolons. On the evidence, the text no
longer reads as *generic* LLM output; it reads as a house style that is not
yet his.

I do not claim more than the measurement supports. The control is 951 words of
README, and README prose is naturally plainer than a specification. A reader
could reasonably hold that a design document earns more dashes than a
statement of intent. That is the author's call, and it is exactly the call the
open criterion asks him to make. What the numbers establish is that the
divergence is real, specific, and mechanical enough to fix in one pass.

---

## 4. Residual jargon

The ticket required "every term of art defined where it first appears". Tested
with `/tmp/acc0036/jargon.py`, which locates each term's first occurrence in
each document and prints its context. Verdicts below are read off that
context.

**Defined at first use, the rewrite's own work.** FTS (DESIGN L74, "SQLite's
full-text search engine"); census (L53, "a full listing — every item, or every
fulltext version — fetched whole rather than paged"); vector sidecar (L63);
sideline (L64); reciprocal-rank fusion / RRF (L99, spelled out); MAD (L224);
P0 and P1 (L329–331); conductor (L333, with the lease row); lens (L15,
enumerated); Sheet v2 (L79); band 0 / band 1 (L251–256); golden-answer sample
(L35); segmenter and seg/1 (L141, L219); top-k (REQUIREMENTS L96, "the k
best-scoring results"); scouts (CONSTRAINTS L8); panel (CONSTRAINTS L136);
key (CONSTRAINTS L24); CJK (REQUIREMENTS L122, expanded).

**Defined, but not at first use.** *slab*: bare at DESIGN L62, defined by its
table at L181. *passage*: bare at L171, defined at L184 ("references, not
text"). *the train*: first at L698, its meaning arriving at the §4 heading on
L745. *scoped issue*: first at L108, explained at L751–L779.

**Undefined anywhere in the three documents.** Grouped by who will trip on
them.

| term | first use | who needs it |
|---|---|---|
| MCP | DESIGN L331 | any reader outside this project; the acronym is never expanded |
| WAL | DESIGN L158 | non-SQLite reader |
| busy_timeout, SQLITE_BUSY, rowid, contentless FTS, unicode61, json_each, carray | DESIGN L29, L92, L206 | non-SQLite reader |
| bm25 | DESIGN L204 | non-IR reader |
| idf | DESIGN L421 | non-IR reader |
| Jaccard | DESIGN L38 | non-IR reader; it carries a threshold the golden gate turns on |
| recall@30 | DESIGN L691 | the `@k` notation is never explained |
| int8 / float32 | DESIGN L61, L672 | quantization is never named as such |
| p95 | DESIGN L636 | appears in four gate thresholds |
| RSS, VmHWM | CONSTRAINTS L112, DESIGN L636 | both are budget units |
| micro-batch | REQUIREMENTS L152 | appears in R13's honest restatement |
| backpressure, bisection quarantine | DESIGN L55–56 | carried over from v1 without gloss |
| lease | DESIGN L48 | mechanism defined at L333, term used 285 lines earlier |
| I-1 … I-4 | DESIGN L773 | the internal issue numbering is never explained |
| #10-shaped | DESIGN L779 | shorthand for upstream issue #10's form |
| SentencePiece | DESIGN L463 | one mention, carries a cap |
| OCR | REQUIREMENTS L55 | common enough to leave |

**Cross-document dependencies.** Three terms are glossed in one document and
used bare in another: *scouts* and *panel* (glossed in CONSTRAINTS, bare in
DESIGN L24 and L9), and *CJK* (expanded in REQUIREMENTS R7, bare in DESIGN
L459). A reader who opens DESIGN.md alone meets all three undefined. The
ticket's first criterion — "read cleanly without `panel/cycle2/` open" — is
met; "read each one on its own" is not quite, for DESIGN.

**For the terminology work.** A TERMINOLOGY.md would need to carry, at
minimum, the sixteen undefined terms above plus the four cross-document ones,
plus the four whose definition arrives late. The IR cluster (bm25, idf,
Jaccard, recall@k, int8/float32, p95) and the SQLite cluster (WAL,
busy_timeout, rowid, contentless FTS, unicode61, json_each) are the two blocks
that would carry most of the value.

I could not find a ticket 0051 in this checkout or on any fetched branch —
`tickets/` runs to 0037 and `tickets/closed/` to 0030, and a grep for `0051`
across `tickets/` returns nothing. This inventory is written to be attachable
to whichever ticket carries the work.

---

## 5. The reading plan

Total 10 435 words. At careful technical reading speed, roughly **70 minutes**
for all three: REQUIREMENTS 12 min, CONSTRAINTS 8 min, DESIGN 50 min.

The criterion is about voice, not correctness, and section 2 has already
verified correctness mechanically. So the read can be much shorter than a full
one. Ranked:

1. **REQUIREMENTS.md, whole, 12 min.** Read first. It is the shortest, it was
   88 % rewritten, and it is where the voice question is cleanest — 28 short
   items in a row make a register audible fast. Pay attention to the Intro and
   to the "Out of scope" list, both of which are near-parallel to prose the
   author wrote himself in README.md and are therefore the sharpest available
   comparison.
2. **DESIGN.md §1 "What changed since v1", 8 min.** Highest-risk section by
   change volume: it replaced a 94-line forensic record with 72 lines of
   narrative. If any argument was lost in compression, it was lost here.
3. **DESIGN.md Intro plus §5, 6 min.** The Intro is entirely new. §5 closes
   the document on the four-beat summary flagged in 3b; it is the single
   passage most likely to draw a veto on voice.
4. **CONSTRAINTS.md, whole, 8 min.** Largest sentence-length improvement, and
   the one document with no figure-guard coverage.
5. **DESIGN.md §2.4 and §2.8, 12 min.** The two sections that carry the most
   disclosed residue and the most gate thresholds. §2.8 also holds the
   US-separator block from nit 2.
6. **Skim: DESIGN.md §2.1–2.3, §2.5–2.7, §3, §4.** Verified faithful
   section by section against the pre-rewrite text in section 2; read for
   register only, or not at all.

A voice-only read of items 1 to 3 is **26 minutes** and is enough to settle
the criterion.

### If the verdict is "not yet" — the fix pass

Short enough to act on, in the order that buys the most per edit:

1. **Halve the em-dashes.** Target the 44 DESIGN units, 10 REQUIREMENTS units
   and 6 CONSTRAINTS units carrying more than one. Rule: a second dash in a
   paragraph becomes a full stop or a comma. Sites listed in 3b.
2. **Convert DESIGN's semicolon chains to sentences.** 179 semicolons in
   7 444 words. The joint is doing the work a period should.
3. **Cut DESIGN.md's closing summary** (L843–L852) or reduce it to one
   sentence. It restates §1 through §5.
4. **Thin the meta-honesty vocabulary in DESIGN** from 41 instances toward the
   author's rate. Most of the sentences say the honest thing and then say that
   they said it.
5. **Fix nits 2 and 3 from section 2e** — eight lines of US separators in
   §2.8, one numeral-as-word in CONSTRAINTS.
6. **Gloss the sixteen undefined terms**, or file them to TERMINOLOGY.md and
   link it once from each Intro.

Items 1 to 3 are the ones that would move the measured signature. Items 4 to 6
are hygiene.

---

## 6. Recommendation

**Tick it with named reservations, or send it back for one short pass — the
author's call, and this is the evidence for it.**

Meaning survived: no requirement, threshold, budget or decision changed, no
R/C/D-number was lost, nothing was legislated outside DECISIONS.md, and the
gates are green. Criteria one through five hold on independent verification.

The voice claim is partly met, not fully. The panel jargon and the standard
LLM tic register are gone — measured zero across 35 patterns. But against 951
words of the author's own prose in this repo, the documents still carry
em-dashes at seven times his rate, unchanged by the rewrite, and DESIGN
answered the sentence-splitting by adding semicolons. That is a house style,
not yet his.

Nothing here blocks a merge. If the author accepts the register, tick it and
record the two nits. If not, the fix pass in section 5 is six items and one
sitting.
