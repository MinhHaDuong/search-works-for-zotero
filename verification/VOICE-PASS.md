# VOICE-PASS — the corrected pass over all three documents

The ratified voice model is VOICE-PILOT.md §1; this pass applies it to
CONSTRAINTS.md, REQUIREMENTS.md, and DESIGN.md, correcting the pilot's two
overshoots: semicolons were cut too far (5,8 against the author's 9,5) and
sentences were shortened past him (median 15 against his 23). The targets
for this pass: em-dash 3–6 per 1 000 words, semicolon 7–12, median sentence
21–25 words. Meaning, numbering, thresholds, and every cross-reference are
unchanged; the check is mechanical (number and reference inventories diffed
against origin/main — identical, up to the three list markers added in C1)
and `make check` is green.

## 1. Measurements

Per 1 000 words; sentence medians in words. Measured by one script over
prose only (code blocks, tables, and headings excluded from sentence
splitting; the before-figures reproduce the pilot's measured values for
CONSTRAINTS.md, which calibrates the tool).

| | author | target | CONSTRAINTS before | after | REQUIREMENTS before | after | DESIGN before | after |
|---|---|---|---|---|---|---|---|---|
| em-dash | 3,2 | 3–6 | 21,7 | **5,1** | 26,0 | 17,5* | 22,3 | **5,5** |
| semicolon | 9,5 | 7–12 | 11,3 | **11,0** | 9,7 | **11,5** | 24,0 | **11,2** |
| median sentence | 23 | 21–25 | 19 | **21,5** | 17 | **21,5** | 25 | **22** |

\* REQUIREMENTS.md's raw em-dash figure is entirely structural: 28 of its 29
dashes are the `**R1 — title**` label leads, plus one in the H1 — the same
label convention the author ratified in the pilot's `C1 —` headings, kept
here for that reason. Prose em-dashes in REQUIREMENTS.md after the pass:
zero. The same accounting for the other two: CONSTRAINTS.md keeps 5
structural dashes (four C-headings, the H1) and exactly 1 prose dash;
DESIGN.md keeps 34 structural (H1, phase labels, §2.7 requirement leads, §3
experiment labels, the §4 train, the §5 risks) and 5 inside verbatim output
strings (the coverage sentence and the R18 example sentences, which are
specified system output, not prose), leaving 2 prose dashes in 7 400 words.

REQUIREMENTS.md's before-median of 17 means the correction ran in the
opposite direction from DESIGN.md's: its R-items were chains of short
sentences and needed combining, where DESIGN.md needed its semicolon chains
broken. Both converged on the band from opposite sides, which is some
evidence the band is doing its job.

## 2. Before / after pairs

**Pair A — combining instead of splitting (REQUIREMENTS.md, ruling 1).**
The pilot's failure mode was splitting; here the fix runs the other way.

Before:

> A dictionary or encyclopedia is one Zotero item but many entries.
> Retrieval and deduplication therefore work on the **section**, not the
> item. An encyclopedic item may legitimately give several distinct hits; a
> focused article gives one. Where an entry heading is known, it is the
> citation locator.

After:

> A dictionary or encyclopedia is one Zotero item but many entries, so
> retrieval and deduplication work on the section, not the item. An
> encyclopedic item may legitimately give several distinct hits where a
> focused article gives one, and where an entry heading is known, the
> heading is the citation locator.

Two 21–28-word declaratives with the logic spoken ("so", "and") instead of
four clipped ones, and the mid-sentence bold gone (trait 8).

**Pair B — the dash apposition becomes its own sentence (DESIGN.md §2.1).**

Before:

> **embed**: `embed_hash`, the hash of the **full embedded text including
> the context prefix** — hashing the chunk text alone would let a vector
> computed under an old heading silently keep serving under a new one —
> with an EXISTS guard on deletes, so removing one row never removes a
> vector another row with the same hash still references.

After:

> **embed**: `embed_hash`, the hash of the full embedded text including the
> context prefix, with an EXISTS guard on deletes, so removing one row
> never removes a vector another row with the same hash still references.
> Hashing the chunk text alone would let a vector computed under an old
> heading silently keep serving under a new one.

The interrupting rationale stops interrupting: the rule is stated whole,
then the reason, as its own sentence. No bold shouting (trait 8), and the
fact content is byte-identical.

**Pair C — the semicolon chain becomes counted sentences (DESIGN.md,
intro).**

Before:

> Facts verified live at edf2748 and relied on below: the query tokenizer
> is broken for non-English text (…); there is no `busy_timeout` and no
> `SQLITE_BUSY` handling anywhere in `src/`; `SCHEMA_VERSION` is written
> (…) and never read; … builds crawl `top:true` only; and `clearStore()`
> sits in the build path.

After:

> Seven facts were verified live at edf2748 and are relied on below. The
> query tokenizer is broken for non-English text (…). There is no
> `busy_timeout` and no `SQLITE_BUSY` handling anywhere in `src/`.
> `SCHEMA_VERSION` is written (…) and never read. … Builds crawl `top:true`
> only, and `clearStore()` sits in the build path.

The count announced up front is his move (trait 5 — "Why? A conjunction of
i) … ii) … iii)"), and each fact gets a plain sentence instead of a place
in a six-semicolon queue. This pattern accounts for most of DESIGN.md's
semicolon reduction (179 → 83): genuine enumerations kept their semicolons,
clause-chains became sentences.

**Pair D — the one I am not sure about (DESIGN.md, closing paragraph).**

Before:

> Cycle 2 adds four things. The units are now the ones the author ratified
> (entries, records, items). The freshness protocol can no longer be fooled
> by the counter it watches. N processes are a designed state, not an
> accident. And every promise is either watched by a gate whose threshold
> cites its artifact, or named as an experiment with a decision rule (§3) —
> each falsifiable in under a day, before the expensive code exists.

After:

> Cycle 2 adds four things: the units are now the ones the author ratified
> (entries, records, items), the freshness protocol can no longer be fooled
> by the counter it watches, N processes are a designed state rather than
> an accident, and every promise is either watched by a gate whose
> threshold cites its artifact or named as an experiment with a decision
> rule (§3), each falsifiable in under a day, before the expensive code
> exists.

Why unsure: the before-version's four short declaratives were full
sentences, not fragments, and their drumbeat had force. I folded them into
one announced run-in enumeration because four consecutive sub-11-word
sentences closing a document is a cadence his corpus never shows, and the
counted list is a move it shows repeatedly — but the original may be the
better ending, and the model's "short sentences are rare and load-bearing"
could be read as licensing exactly the original. If the author prefers the
drumbeat, revert this paragraph alone.

**Pair E — the deliberately kept em-dash (CONSTRAINTS.md C2).**

> The lasting value is the contract — the MCP tools, coverage honesty, the
> freshness protocol, and the filters, all defined in DESIGN.md. The
> machinery behind the contract is replaceable.

This is the pilot's Pair E, kept with its single dash: at 3,2 per 1 000 his
rate is low, not zero, and this apposition is the one place in the document
that earns it. It is CONSTRAINTS.md's only prose dash.

## 3. What was deliberately left alone

- **The two H1 subtitles and the provenance heading**, restored per the
  pilot verdict: "CONSTRAINTS — what the world imposes" pairs with
  "REQUIREMENTS — what the system promises", and "Politeness (web transport
  only, from the official API docs)" keeps its source. DESIGN.md's H1 keeps
  its ratified name, "The Instrumented Ledger".
- **The label conventions**: `R1 —`, `C1 —`, `D3 —`, `Phase A —`,
  `Risk 1 —`, `X1` — the pilot's heading form, ratified. Their em-dashes
  dominate the raw REQUIREMENTS figure (the § 1 footnote).
- **Every number, unit, code literal, SQL block, and quoted string**,
  including "92,7 %", "584 of 8 037", "2 084,9 MiB", the coverage-sentence
  blockquote, the R18 example sentences, the ratified-budgets block, and
  the Zotero staleness quotation. The figure guard's three declarations
  into these documents are presence checks on numbers that survive
  verbatim, so no anchor moved.
- **The resolved-decisions table (D1–D11)** with its bold verdict leads: a
  table's answer column is a scannability device, not prose, and the
  resolutions are ratified text.
- **Ticket 0060's two known-wrong claims**: DESIGN.md §2.6's attribution to
  #6012 and CONSTRAINTS.md C2's "never crosses a section" are reworded in
  voice but keep their current meaning; the correction lands separately.
- **"C3 — the machine belongs to the user"**, the pilot's declared test
  case, untouched.
- **The `[PR]` / `[issue]` / `[X]` notation bolds** in §4: notation tokens,
  not emphasis.

## 4. What I could not put in his voice

- **The scout bullets and the spec-register generally.** The pilot's
  diagnosis holds unchanged, and DESIGN.md deepens it: schema definitions,
  gate assertions, and decision rules ("Rule: ≥ 45/50 correct ships the
  entry story") are a register the corpus does not contain. I applied the
  Lacq treatment — state the fact, give the number, move on — and the
  sentences are now grammatical, unbolded, and mid-length, but "sounds like
  Minh writing a schema" remains a claim no evidence can support. Only a
  paragraph rewritten by him can close this.
- **The structural-hint paraphrase (CONSTRAINTS.md, last section).** Still
  holds from the pilot: the section is by definition his voice, and the
  surviving text is an agent's paraphrase of words not recorded in this
  repo. One sentence from him replaces it outright.
- **The R-label leads themselves.** `**R14 — no text is a terminal
  state.**` is a strong plain assertion, arguably his register — but the
  bolded run-in-label form is a document convention with no corpus
  counterpart, and it is what keeps REQUIREMENTS.md's raw em-dash figure at
  17,5 while its prose sits at zero. If the author wants the raw figure
  inside the band, the labels must change form, which is a structural
  decision (it touches every inbound reference's reading habits), not a
  wording one; I did not make it.
