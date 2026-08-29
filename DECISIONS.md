# DECISIONS — the ratification ledger

*Append-only. The author's rulings land here first; REQUIREMENTS.md,
CONSTRAINTS.md and DESIGN.md are then edited to match. Any ratified line
remains vetoable on later reading — a veto is a new entry here.*

*The documents these entries ratified — the original sheet, the elicitation
panel's delta (19 requirements, 11 decisions, 7 out-of-scope declarations,
22 kills, each with its evidence), cycle 1's synthesis ("The Settled Ledger"),
and the scout report — are superseded and live in git history, last present at
commit `6f7fcd1` as `DESIGN.md`, `DESIGN-DELTA.md`, `DESIGN-V1.md`,
`SCOUTS.md`. The consolidated truth in the working tree replaces them; git is
the archive. The cycle-2 panel record that entries below cite by name — the
memos, the critiques, the political and implementation reviews — is likewise
in git history, last present at commit `e32afe3` as `panel/cycle2/`.*

## Ratified

**2026-08-26 — the sheet, as agreed.** Requirements R1–R9 stated by the author
as testable properties; constraints C1–C3 worked out together; resource
budgets ratified verbatim: background ≤ ~1 core low priority; server
steady-state RSS ≤ ~300 MB; pipeline peak ≤ ~500 MB regardless of document
size; embed worker killable/restartable at any time with zero index damage.

**2026-08-26 — the unit of answer is the entry.** The panel's "one item, one
hit" rejected as framed. The monster document is encyclopedic — a collection
of entries — and an unsplit multi-chapter book is a collection of chapters, so
the retrieval and dedup unit is the **section**, not the Zotero item. An
encyclopedic item may legitimately yield several distinct hits; a focused
article yields one. Consequences accepted: the monster-weight decision
dissolves; section identity becomes a derivation-graph concern (a heuristic
segmenter, its identity folded into the chunker key, stands in until
structured extraction is served over the local API); the citeable locator is
the entry heading where one is known.

**2026-08-26 — the record is the semantic core.** Title, abstract, and
keywords are the key semantic targets. Every item's record is indexed before
any body text; fields keep their identity for ranking; notes, annotations and
body text extend the core, never dilute it. Fixes the phase order: record for
everyone, newest first — body text after.

**2026-08-26 — chunking respects entry boundaries; context is prepended.**
Chunk boundaries align to section/entry boundaries where structure is
detectable (never straddling two entries), and each chunk's embedded text is
prefixed with its context (entry heading / outline path / item title) — prior
art in Zotero's own chunker.

**2026-08-26 — the delta is ratified by delegation.** The author validated the
elicitation panel's recommendations wholesale: R10–R28 (as amended by the
rulings above) and C4 enter the sheet; decisions resolve as D1 items
(+ metadata-only counts), D2 hosted-out, D3 serve-stale, D4 merged, D5 phrase,
D6 first-with-text, D7 notes+annotations, D8 leave-room (OCR out today),
D9 dissolved by the entry ruling, D10 labeled-estimate, D11 set; the seven
out-of-scope declarations stand; the 22 kills stand. Scout findings (mixed
full-text sequence, Server-ID partitioning, web politeness, R5's MATCH nuance,
R2/smallest-first composition) folded into cycle 2's input as binding.

**2026-08-26 — the work train is re-formed on the panel reviews.** The author
applied the political and implementation reviews' structural recommendations
(panel/cycle2/review-political.md, review-implementation.md) wholesale:

- **Volume**: at most **two upstream PRs in flight, ever**; the contained-PR
  budget beyond #19/#20 is **six** — the stopwords follow-up, PR-1 (schema
  read-before-write), PR-2 reduced to `busy_timeout` alone, PR-3 (wipe guard,
  identity stamped first), PR-4 (cacheDir), PR-5 (key to header). Cadence is
  demand-triggered: the next pair waits for the current pair to resolve, and
  silence is queueing, not a signal to add more.
- **Reserve** (opened only on a warm batch or third-party demand, the #13/#14
  pattern): PR-7 (terminal states), PR-10 (own words).
- **The mega-RFC is replaced** by the **acceptance-harness offer first** — the
  convergence harness, fold sweep, and golden set as an executable spec he can
  run against whatever he builds — followed by **three #10-shaped scoped
  issues**: A ledger/freshness/counters (pause and serve-stale as motivating
  defects; the query-semantics work rides here or waits for demand), B
  entries/segmenter (X5-gated, #6012-checkpointed), C multi-process on one
  data dir (absorbs the per-page-commit question). The bet stands: his
  machinery under our contract is a good ending.
- **Issue forms**: I-2 framed as extending the citation his docs already make
  to #10; I-4 folded into scoped issue A's custody paragraph; I-1 and I-3
  stand (I-3 behind the #6012 checkpoint).
- **Commitment bounds** (binding on this repo's side): two PRs in flight;
  a three-week sunset — any upstream item unaddressed after three weeks, or
  overtaken by his own implementation, is closed from our side with one
  appreciative line and no relitigation; the harness is a one-time artifact
  transfer, not a tracking duty; the fork's end state is **archived** once the
  train resolves.

**2026-08-27 — the head resolved; the sunset rule's first executions.** An
event record, not a new ruling: the 2026-08-26 bounds firing on upstream's
second batch (the evidence is SYNC.md's, stated once there — #19/#20 merged
unmodified with authorship preserved; the maintainer filed follow-up #21
himself off #20's review questions and shipped its fix with #22/#23 as v1.8.0
the same day). Each consequence is the mechanical application of a ratified
line, vetoable as ever:

- **Both in-flight slots are empty**; the demand-triggered cadence admits the
  next pair. The measured asymmetry the train's form rests on strengthens to
  four-for-four (contained PRs merged as ours) and two-for-two (design-sized
  built by him) — #21, filed and fixed by him with the finding still credited,
  is its strongest data point yet.
- **"Overtaken by his own implementation" fires twice.** The two
  swallowed-error items (`keywordSearch`'s catch, JSON `loadIndex`) — closed,
  fixed upstream via his #21, with appreciation and no relitigation. And
  **PR-2** (`busy_timeout` alone) — closed: v1.7.1's `80f8aa0` ships a 10 s
  `busy_timeout` with WAL tolerance. The contained-PR budget's live remainder
  is five; ticket 0016 narrows to PR-3, whose wipe-guard hazard is verified
  still live at v1.8.0.
- **The reserve's warm-batch condition is met** (0019, 0022 eligible per the
  #13/#14 clause); opening them stays a choice, not an obligation.
- **I-1 and I-2 stand, re-verified at v1.8.0** (SYNC.md §4/§5 notes); the
  internal I-labels never assumed upstream numbers, and #21–#23 are now
  consumed.

**2026-08-28 — the project becomes Search Works for Zotero.** The author
renamed `zoteus-fts5` to `search-works-for-zotero` and repositioned it as an
independent public statement and open workshop for advancing semantic retrieval
in Zotero. Zoteus remains the current reference implementation and upstream
contribution target, but it is one implementation among others and is not the
project's destination by definition. Zotero core — beginning with
[zotero/zotero#6012](https://github.com/zotero/zotero/pull/6012) and its
successors — is an equally important surface to study and influence. An
upstream change, a reusable retrieval contract or acceptance harness, a
reproducible experiment, or evidence that kills a proposal all count as project
outcomes; shipping a Zoteus implementation is only one possible outcome.

## Awaiting ratification

Three readings cycle 2 could not decide on the sheet's text alone (flagged in
DESIGN.md §2.3, §2.8 and §2.9; put to the author directly — the re-formed
train keeps internal governance out of upstream filings, so they are resolved
here, not in any issue text):

- **R26's prefix granularity.** The panel asserts newest-first prefix-ness at
  stated granularities — record coverage as a strict newest-first prefix; body
  coverage as a band-0 prefix with band-1 as disclosed residue — because the
  two-band anti-monopoly cap breaks a strict full-coverage prefix by
  construction. An interpretive reading, vetoable.
- **The 300 MB budget's scope under N processes.** Ratified against a
  single-server picture; the normal deployment is one zoteus per MCP client,
  ~690 MB whole-machine steady at two clients. Per process or per machine is
  the author's call; both figures stated in DESIGN.md §2.9.
- **R20's letter vs the gate's practice — two readings to ratify.**
  (i) *Cadence*: the sheet says the budgets are asserted "on every check"; the
  design places the RSS gate in the slow suite (`check-slow`) because its
  fixture is a 44.9M-char monster, and names the weakening in Risk 5.
  Every-check or slow-suite is the author's call. (ii) *Fixture*: the sheet
  says "against the 44.9 MB dictionary"; the committable gate necessarily uses
  a synthetic surrogate of its measured size and structure, because the
  dictionary itself is copyrighted library content that cannot enter a public
  repo — the real-document run remains X3a on the author's machine. Ratify the
  surrogate as satisfying R20's intent, or keep R20's letter and accept that
  the gate half of it lives only on the author's machine.
