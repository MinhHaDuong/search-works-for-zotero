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

**2026-08-29 — a third in-flight slot, granted once, for the cosine fusion.**
The author authorized opening a third upstream PR while #27 and #28 are both
open, on the grounds that the change is a clear code simplification: one
traversal per vector instead of two, and a `norm()` call site that stops being
polymorphic. Ticket 0070 carries the measurement (2,19x on a 255 703-row index
at 3072 dimensions, scores bit-identical, no dependency and no rebuild).

This is a grant, not an amendment. The **two-in-flight cap stands** as ratified
2026-08-26, and the contained-PR budget is untouched — this PR is not drawn from
the five live items, because it is not one of them: it came out of reading
upstream issue #30, which the budget predates. The exception's ground is that a
simplification carrying its own equivalence proof costs the maintainer's
attention differently from a design ask. Read it as precedent only for that
shape of change, and only one at a time.

**2026-08-29 — Zotero 10 shipped the CJK 2-gram geometry.** Verified on the
author's own installation (10.0, build 20260817151751) and in the shipped
`fulltext.js` of that build: Zotero 10 dropped `fulltextWords` /
`fulltextItemWords` at userdata step 127 and moved the keyword index into a
separate attached database `fulltext.sqlite` — four contentless FTS5 tables,
among them `fulltextContentCJK`, `fts5(text, tokenize='ascii', content='')`,
fed space-separated overlapping 2-grams generated by `getCJKBigrams()` over
Han/Hiragana/Katakana/Hangul runs. Measured on the author's index: 2 536
distinct terms, every one exactly two characters. Upstream commit `7c2a1d1`,
2026-06-30, tagged in 10.0.0 and 10.0.1 only. Evidence:
`verification/VERIFY-FULLTEXT-SQLITE.md`.

Consequences: DESIGN.md §2.6 stops crediting the 2-gram geometry to the draft
#6012 and credits shipped Zotero 10 instead; the CJK companion moves from
"scheduled, pending the platform" to "geometry settled, ours to build"; §2.6
states explicitly that our fused-third-list variant **differs** from the
platform, which routes exclusively and answers neither a single CJK character
nor a mixed-script term from the index. C2 gains the shipped-schema bullet.
Nothing here changes an upstream commitment; the PR budget is untouched.

Two further observations ride with this entry and are **read from source, not
measured** — they are corroborating, not load-bearing, and a later reading may
sharpen either. (i) Zotero keys its index by local `itemID`, stamps it with
`localUserKey`, and rebuilds on mismatch, which is the platform's own form of
the Server-ID partitioning C1 already requires. (ii) Zotero tried trigram for
content and abandoned it three weeks later (`0ce289a`, 2026-07-17, trigram →
unicode61, forcing a rebuild), keeping trigram for notes; the trigram-CJK kill
stands, now corroborated. The provenance split is stated because the geometry
above was measured on a live index and these were not, and a ratified entry
should not hide that difference.

**2026-08-29 — of the four #6012 attributions in C2, one is refuted.** Read at
PR head `77e2c4b`, 2026-08-28. (a) The token geometry 120 / 768 / 48 holds as
constants, but 768 never binds: every shipped embedding model declares
`maxTokens: 512`, so the effective ceiling is ~510 minus the heading prefix.
DESIGN.md §2.2's "adopted verbatim" and its ≈ 250–300k passage estimate are
inconsistent with each other under that reading; which one moves is still open
and is carried by ticket 0060. (b) **"Never crosses a section" is refuted as
stated.** The chunker merges sections below the 120-token minimum forward into
their neighbour, asserted by #6012's own tests; it never merges two sections
each able to stand alone, and exempts auxiliary sections. CONSTRAINTS.md C2 is
corrected accordingly, and our boundary ruling is stricter than the platform's
— a deliberate divergence, not the alignment C2 currently claims. (c)
Smallest-first is confirmed and applies to **attachments only**; DESIGN.md
§2.3's scoping was already correct and stands. (d) The CJK 2-gram geometry is
not #6012's, per the entry above; #6012 adds a query-side single-character CJK
fallback the shipped path lacks, worth adopting because it answers one of the
two dead ends our fused third list exists to cover.

**2026-08-29 — security and privacy considerations get their own document.**
`SECURITY.md`, standalone, not a section of DESIGN.md or CONSTRAINTS.md. The
ground is lifetime: threats outlive designs, this project has already
re-designed once, and a section inside DESIGN.md is rewritten with the design
it sits in. A threat model is also requirement-shaped rather than
constraint-shaped — it states obligations we take on, where CONSTRAINTS.md
states facts the world imposes — so filing it under C-numbers would blur the
one definition that document owns. FIELD-REVIEW.md is the supporting evidence:
across 39 surveyed projects not one documents a threat model, while the survey
records a hosted service relaying users' Zotero API keys to a third party, a
shared cloud credential standing in for per-user keys, and a fork whose public
description still advertises a privacy posture it had abandoned. That last is
this repo's own one-statement-per-fact defect, observed in the wild, on exactly
this class of claim. Ticket 0052 carries the work; the D2 hosted-mode ruling is
not reopened, and the scope is local-only.

**2026-08-29 — governance moves to GOVERNANCE.md, which owns process rules
going forward.** Ratified process entries stay in this ledger where they are,
and GOVERNANCE.md points at them rather than moving them. The alternative that
relocates them was rejected on the ground that append-only is what makes this
ledger evidence: a record you may rewrite is a document, not a record. The
transitional cost is accepted — process rulings live in two places for a while,
resolved by the pointer. Tagging in place was rejected as not solving the
problem, since strategy would stay interleaved with the specification in a
public repository the upstream maintainer reads. Promoting SYNC.md was rejected
because SYNC.md records what happened upstream and is rewritten at every
movement, where governance is what we decided to do about it and should be
stable. The prize is that once strategy has one home, the
nothing-about-the-maintainer-in-upstream-text rule becomes a check rather than
a habit. Ticket 0053 carries the work.


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
