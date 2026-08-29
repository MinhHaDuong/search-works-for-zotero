# VOICE-PILOT — CONSTRAINTS.md rewritten toward the author's voice

Pilot for ticket 0036's open criterion. One document rewritten
(CONSTRAINTS.md, 145 lines); REQUIREMENTS.md and DESIGN.md untouched. The
point is to let the author falsify the voice model on 1 150 words before
anyone spends it on 10 700.

## 1. The voice model, from evidence

Corpus read: the curated author-voice corpus at
`~/data/projets/chemin-de-voix/corpus/clean/voix-auteur-en/` (34 texts,
48 311 words — op-eds, two solo academic papers, a confidential
self-interview) and `voix-auteur-fr/` (7 texts), plus the author-filed
tickets in this repo (0001–0013, `Author: minh`) and his recorded verdicts.
Agent-written prose he merely accepted was excluded as evidence — the premise
of 0036 is that he did not accept it.

What the corpus shows, stated so it can be falsified:

1. **The first sentence says what the text does, plainly.** "This paper
   proposes and justifies a rule on how to choose scenarios" (the 1/n
   Futuribles paper); "This case study describes the social aspects of
   Total's CO2 ... pilot project" (Lacq, 2013); "The purpose of this note is
   to elucidate and illustrate five frequently used definitions" (SAPIENS,
   2009). Workmanlike meta-discourse, never apologized for; explicit
   roadmaps ("The paper is organized as follows").
2. **Question, then answer.** He opens a topic with a direct question and
   answers it at once, sometimes in one word. "What is the value of a tonne
   of CO2 ...? It all depends on what you mean by value!" (SAPIENS). "Why? A
   conjunction of i) ... ii) ... iii) ..." (self-interview).
3. **Mid-length declaratives, verb early.** Typically 15–25 words,
   subject–verb–object, little subordination. Short sentences occur but are
   rare and load-bearing ("Rest in peace." — OECD Insights, 2016; "We
   explicitly decided to stay small and not grow the income." —
   self-interview). Never a drumbeat of aphoristic fragments.
4. **The number instead of the adjective, with units, in-line.** "about
   30 000 metric tons of CO2 per year ... compressed to 27 bars ... about
   30 km" (Lacq); "Production peaked in 1982 at 33 million m³/day". No
   drama around a figure.
5. **Run-in enumerations with markers.** "(a) a legitimate expert in energy,
   (b) interested to lead a think tank and (c) a Party member with high
   situational awareness" (self-interview); the five numbered definitions of
   the carbon price (SAPIENS).
6. **First person, unafraid, including of failure.** "I would prefer to make
   the rest of the traffic quieter than to make the electric vehicles
   louder" (OECD); "I pointed out the critical need to get more Vietnamese
   funders but we failed" (self-interview). "We" in papers, "I" in opinion.
7. **One modest hedge, often idiomatic.** "more often than not", "if not of
   the general public", "may have helped". Never a hedge stack. Balanced
   two-limb weighings: "forecasts ... are problematic because X; scenarios
   ... are problematic because Y" (1/n paper).
8. **Almost no typographic emphasis.** Italics for terms of art; essentially
   no mid-sentence bold; parentheses and commas where LLM prose reaches for
   em-dash appositions. Headings are plain noun phrases ("Local history",
   "Introduction") or full assertions ("Why the plausibility level of
   extreme scenarios in a set of n should be 1/n") — never metaphors.
9. **Metaphor is rare, concrete, and usually playful, one per piece.**
   "Rest in peace, moped"; "cowboy-minded behaviors"; "running out of
   steam". Not a structural metaphor sustained across a document.
10. **Definitions at first use, by restatement.** "'The possibility of X is
    Π(X)' can be read as 'The probability of X is not greater than Π(X)'"
    (1/n paper).
11. **Texture is unfussy, not lapidary.** A slight non-native looseness runs
    through the English ("to some extend", "risks ... are looming now"). I
    did not imitate the slips — that would be parody — but it sets the
    target: plain and direct beats polished and clever.

What he never does in the corpus: sentence fragments as thought-headers;
"Therefore:" as a one-word pivot; bolded verdict words mid-sentence;
metaphorical section titles; rhetorical triads; a paragraph ending on a
flourish rather than a fact.

## 2. Before / after pairs

**Pair A — the section title + opening (most successful, I think).**

Before:

> ## C2 — the ground moves
>
> The platform and the upstream project are both moving: [bullet list]
> Therefore: every pipeline stage (extract, chunk, embed) is a swappable
> component ...

After:

> ## C2 — the platform and the upstream project are both moving
>
> Three facts about the terrain: [bullet list]
> The consequence for the design: every pipeline stage (extract, chunk,
> embed) is a swappable component, an adapter, identified by its key.

Why: "the ground moves" is a metaphor doing a title's job; his titles state
the fact (trait 8). "Therefore:" as a pivot has no equivalent in his corpus;
"The consequence for the design:" is the same logic said in a sentence.

**Pair B — the open question (question-then-answer, trait 2).**

Before:

> We do not yet know whether a *local* re-extraction re-stamps version 0,
> which would make it invisible to the counter; experiment X6 (ticket 0025)
> will measure this, and DESIGN.md §2.4 is designed to work under either
> answer.

After:

> Does a purely local re-extraction re-stamp version 0, which would make it
> invisible to this counter? We do not know yet. Experiment X6 (ticket 0025)
> will measure it, and DESIGN.md §2.4 is designed to work under either
> answer.

Why: this is his most recognizable move — SAPIENS opens the same way, the
self-interview answers "Why?" in one word. Also introduced with "There is one
blind spot." (a short load-bearing sentence, trait 3).

**Pair C — de-bolding a scout finding.**

Before:

> The local `/fulltext?since=` sequence is **mixed**: web stamps, local
> client versions, and 0 for local extraction, all in one column. The
> correct filter is `since=0 OR version>since`. Versions can be compared for
> equality per item; they are **never a monotonic cursor**.

After:

> The local `/fulltext?since=` sequence is mixed. Web stamps, local client
> versions, and 0 for local extraction all appear in one column, so the
> correct filter is `since=0 OR version>since`. Versions can be compared for
> equality per item, but they are never a monotonic cursor: ...

Why: the facts are untouched; the bold shouting goes (trait 8), and the
fragments become sentences with the logical connective ("so", "but") spoken
rather than implied.

**Pair D — the structural hint (run-in enumeration, trait 5).**

Before:

> Two justifications found: keyword availability never waits on embedding,
> and an OS process can be nice'd, observed, and restarted.

After:

> Two justifications were found: (a) keyword availability never waits on
> embedding, and (b) an OS process can be nice'd, observed, and restarted.

Why: his lettered run-in markers, and a verb restored to a verbless clause.
Small, but it is exactly the texture difference.

**Pair E — the one I am not sure about.**

Before:

> The lasting value is the contract: the MCP tools, coverage honesty, the
> freshness protocol, and the filters (all defined in DESIGN.md). The
> machinery behind them is replaceable.

After:

> The lasting value is the contract — the MCP tools, coverage honesty, the
> freshness protocol, and the filters, all defined in DESIGN.md. The
> machinery behind the contract is replaceable.

Why unsure: the original two-beat compression ("The lasting value is the
contract. The machinery behind them is replaceable.") is strong, and it is
the kind of flat assertion he might actually write — my version mostly
reflows punctuation. This sentence is strategy-register, and his
strategy-register evidence (the self-interview) is first-person narrative
("We explicitly decided to stay small"), which a constraints document cannot
use. I kept the assertion and softened the typography; a genuinely Minh
version might not exist for this sentence in this genre.

## 3. What changed structurally, and what was left alone

Changed:

- The H1 dropped its epigram ("what the world imposes"); the intro's first
  sentence now carries that meaning. If the voice is accepted, the parallel
  epigrams on REQUIREMENTS.md ("what the system promises") and DESIGN.md
  would follow — until then the three H1s are inconsistent, deliberately.
- Metaphorical/verdict section titles became fact-stating ones. C1 "the
  derivation graph" → "everything the index stores is derived data"; C2 "the
  ground moves" → "the platform and the upstream project are both moving".
  All C-numbers survive; every inbound pointer (tickets, DECISIONS.md,
  DESIGN.md) addresses C-numbers, not title texts.
- "Binding sharpenings from the scouts:" → "The scouts sharpened this
  constraint on three/five points:". The bindingness is stated once, in the
  Intro — repeating it per section was a duplicated fact, the repo's own
  named defect.
- The derivation chain became a numbered list (1–3): it is a sequence, and
  he numbers sequences.
- Nearly all mid-sentence bold removed; most em-dash appositions became
  parentheses, commas, or separate sentences; fragments got verbs.

Left alone:

- **C3's title, "the machine belongs to the user".** It is an assertion of
  fact with a plain subject and verb, the register of his own "Rest in peace,
  moped". A test case: if the author flags it, the model above is wrong about
  trait 9's tolerance.
- Every number, unit, code literal, quoted upstream sentence, cross-reference
  (X4, X6, ticket 0025, DESIGN.md §§2.4–2.6, R1/R2/R6, #6012), and the
  boundary-ruling pointer. Number formatting untouched (584 of 8 037,
  0..25 036, 374 ms).
- The "Ratified budgets (2026-08-26)" block, verbatim — it is quoted ratified
  text, not prose to restyle.
- The Zotero staleness quotation in C1, verbatim.

`make check` is green after the rewrite (93 figure pairs checked, 0 stale;
15 tests pass). The figure guard does not currently anchor into
CONSTRAINTS.md, so its numbers are format-checked by eye only.

## 4. What I could not make sound like him, and why

- **The scout bullets (C1 and C2).** I made them grammatical and unbolded,
  but they remain spec-register: filter expressions, header names, a reader
  contract in braces. The corpus contains no evidence of the author writing
  reference documentation — his documented registers are the essay, the
  op-ed, the case study, the journal paper, the interview answer. The
  closest model was the Lacq paper's descriptive passages ("The captured gas
  was compressed to 27 bars and transported for about 30 km"), and I used
  it: state the fact, give the number, move on. But "sounds like Minh
  writing an API constraint" is a claim no evidence can support, because he
  has not left one. Diagnosis: not a rewriting failure, a corpus gap. Only
  he can close it, by rewriting one bullet his way.
- **Pair E above** (the contract/machinery aphorism), for the reason given
  there: his strategy voice is narrative and first-person; a constraints
  document is neither.
- **The "standing instruction to any panel" frame.** The section is the
  author instructing future design panels — his voice by definition — yet
  the surviving text is an agent's paraphrase of a hint whose original
  wording is not in the repo. I tightened it but could not restore words he
  never wrote down here. If he re-states the hint in one sentence, that
  sentence should simply replace the paraphrase.

## 5. Cost and risk of extending this to REQUIREMENTS.md and DESIGN.md

Cost: REQUIREMENTS.md (~3 000 words) and DESIGN.md (~7 700 words) are seven
times the pilot. The mechanical passes (de-bolding, fragments to sentences,
titles to facts, question-then-answer where a genuine open question exists)
transfer directly. One to two sessions of work, plus the figure-guard
anchors: both files ARE anchored (71 positional pairs), so many rewordings
of measurement-bearing sentences will each require an anchor update —
tedious, guard-assisted, low-risk.

Risk, in order:

1. **Meaning drift at scale.** 28 R-items and the whole design each carry
   ratified substance; a rewording that reads like a new ruling violates the
   DECISIONS.md-first rule. The pilot's protection — verbatim preservation
   of every number, quotation and pointer, plus a diff read against
   DECISIONS.md — must be re-applied 7 times over, and the earlier rewrite
   round already produced 8 drift repairs on these documents (ticket 0036's
   log). Budget for a drift-review round, not for a clean single pass.
2. **The corpus gap does not shrink.** DESIGN.md is even deeper in
   spec-register than CONSTRAINTS.md. If the author judges the pilot's scout
   bullets "still not me", the same verdict will apply to most of DESIGN.md,
   and the right move is a different one: he rewrites two paragraphs as a
   sample, and the sample — not this model — becomes the target.
3. **Voice model wrong at the root.** Everything above rests on op-eds and
   two solo papers, the most recent from 2023. If his working-document voice
   in 2026 differs from his published voice, this pilot is the cheap place
   to find out. That is what it is for.
