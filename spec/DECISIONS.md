# DECISIONS — the ratification ledger

*Append-only — this document is authority's chronological point of entry; its
role in the full chain is stated once, in README.md.*

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


**2026-08-29 — R26 is rejected as written: newest-first is an orientation, not
a strict order.** The requirement asserted that at every poll the indexed set
is a most-recent-first prefix, "the newest N items, never a gap in the middle".
The author rejects the sentence, on three grounds. Recency orients the work; it
does not impose a verifiable total order. Items enter and leave the library in
real time, so any invariant asserted over a positional prefix is asserted over
a set that has already changed. And the two-band frontier that was to carry the
observable does not survive that motion: a band partition of a moving set is
not a stable thing to assert.

What replaces it is priority by content type, not position in a queue.
Embedding an item's title, keywords, abstract and notes takes priority over
embedding its body content. That ordering is checkable at any instant without
reference to a snapshot of the library, which is what R26 was reaching for and
could not have.

Consequences: R26 is rewritten to state the orientation and the tier priority,
and to drop the prefix observable. DESIGN.md §2.3's two-band frontier (band 0,
band 1, the derived cap K) loses its justification as an observable and is
reworked. §2.3's "the R26 observable is then asserted per phase" paragraph
goes with it, and with it the interpretive reading that cycle 2 flagged for
veto — the veto is this entry. The convergence harness stops asserting
prefix-ness and asserts the tier ordering instead.

One consequence is **not** settled here and is carried by ticket 0080: the band
cap did anti-monopoly work that the tier ordering only partly replaces. Tiers
stop a monster delaying every other item's record, because records all precede
body content. They do not stop a monster monopolizing the body tier once it is
reached. Whether that needs a mechanism, and which, is open.

**2026-08-29 — notes belong to the record tier.** Amends the ratified entry of
2026-08-26 ("the record is the semantic core"), which grouped notes with
annotations and body text as material that extends the core. The author places
notes with title, keywords and abstract: they are embedded before body content,
not after it. The earlier entry is not edited — this is the amendment, per the
ledger's own rule. Annotations are not addressed here and stay where the
2026-08-26 entry put them.

**2026-08-29 — the RAM budget is per process, and the machine total is stated
beside it.** The 300 MB was ratified against a single-server picture; the normal
deployment is one zoteus per MCP client. Ratified: the budget binds per process,
because that is the only scope a process can measure and therefore the only one
a gate can assert — an unenforceable budget is an aspiration, and Risk 5 is
about exactly that decay. The whole-machine figure is stated alongside it rather
than dropped: ≈ 250 MB fixed for the single background worker plus ≈ 220 MB per
P0 the user chooses to run, ≈ 690 MB at two clients. Stating it this way makes
the total legible without pretending a process can enforce it. FIELD-REVIEW.md
records that no project among the 39 surveyed publishes a memory or CPU budget
of any kind, so there is no external norm here to defer to and enforceability is
the right criterion.

**2026-08-29 — the RSS gate runs in the slow suite, with a mechanism proxy in
the fast tier.** R20's letter says the budgets are asserted on every check. Read
literally it puts a 44,9 MB fixture with ~43 000 headings in the fast loop,
which is how a gate gets disabled — the normalization-of-deviance channel
DESIGN.md Risk 5 names, and the one that produced ticket 0011's defect. Ratified
instead: the budget assertion stays in `check-slow`, and a cheap fixture in the
fast tier asserts the *mechanism* — that the cap engages and resident memory
stays flat — without the monster. The two failure modes are different and get
different tests: "the mechanism stopped engaging" is cheap to detect
continuously, "the budget regressed" needs the real fixture and can run per PR.

**2026-08-29 — the synthetic surrogate satisfies R20's intent, conditional on
periodic revalidation.** R20's letter names the 44,9 MB dictionary, which is
copyrighted library content and cannot enter a public repository; keeping the
letter would put the only memory gate on one machine, where no reviewer and no
CI can observe it. Ratified: the deterministic synthetic monster at the measured
44 906 152 chars, entry-structured, satisfies R20's intent. The condition is not
optional. X3a on the real dictionary is re-run at each release and the surrogate
is revalidated against that measurement, because a surrogate whose fidelity is
never re-measured drifts silently from the document it stands for, and its pass
then proves only that the surrogate is cheap. Without the revalidation this is a
check whose all-clear is indistinguishable from "I could not look".


**2026-08-29 — R7 is hard; C3's memory ceiling gives way.** Multilingual is not
negotiable against a resident-memory budget. Where the two conflict, the
embedder stays multilingual and the 300 MB server ceiling moves. The author's
ruling, on the measurement below.

The conflict is real and structural rather than a property of one model. A
multilingual embedder pays for its vocabulary in resident memory, and
quantization does not recover it. `multilingual-e5-small` — Zotero core's own
multilingual pick, and the smallest serious candidate — measures 404,4 MB
resident at uint8, its cheapest loadable rung, against a ratified ceiling of
300 MB (`bench/results/0025-x1-recall/dtype-ladder-multilingual-e5-small.json`).
It is the *smaller* of the two models swept that day: 118M parameters at 384
dimensions against nomic-768's 137M at 768, and yet 404,4 MB against 235,2 MB.

Why multilingual costs this much is NOT established, and an earlier draft of
this entry claimed it was. Vocabulary is the obvious suspect — e5 carries
250 037 tokens against nomic's 30 528, so its embedding table is 366,3 MB at
fp32 against 89,4 MB — and the *file* sizes fit that reading exactly. The
*resident* sizes do not. Measured warm at q8, five fresh processes each, spread
under 7 MB: nomic-768 234,2 MB, granite-embedding-97m-multilingual-r2
407,8 MB, multilingual-e5-small 419,5 MB. Granite and e5 differ by 102,6 MB of
embedding table and by 11,7 MB of resident memory. A predictor built on
`vocab x dim` matched e5-small to a tenth of a megabyte — and it had been
calibrated on e5-small; its first out-of-sample test, Granite, it missed by
106 MB. So the mechanism is open, and the ruling does not depend on it.

What the ruling rests on is the measurement, which is robust: every
multilingual embedder measured sits between 405 and 420 MB at its cheapest
loadable rung, against 234 MB for the English small-vocabulary model, and none
of them fits 300 MB. Two independent candidates, repeated, agree on that.

**What this entry does not settle.** It does not set the new number. C3's
replacement ceiling is a consequence of which embedder ticket 0240 selects, so
the number is ratified after that choice and not before — with one bound
already known, that no multilingual candidate measured fits under ~400 MB, so
any revised ceiling below that is unachievable on current evidence.
`spec/CONSTRAINTS.md` C3 and `spec/DESIGN.md` §2.9 are edited to match once the
figure exists; until then C3's 300 MB stands in the documents with this entry
as its known exception, because editing a ratified constraint to an unknown
value would be worse than leaving the conflict visible.

Two consequences worth naming now. The RSS gate (R20, `check-slow`) asserts
`server p95 <= 300 MB` verbatim and will fail the moment a multilingual
embedder is resident, so it is re-pinned in the same change as C3, never
before. And the pipeline peak (`<= 500 MB regardless of document size`) is a
separate budget on the worker, untouched by this ruling — an embedder resident
in the server does not license a larger extraction peak.

**2026-08-29 — the plain-language rewrite is accepted, and its voice is the
specification chain's standard.** Ticket 0036 rewrote REQUIREMENTS.md,
CONSTRAINTS.md and DESIGN.md out of the cycle-2 panel's compressed idiom, on the
author's verdict of 2026-08-27 that "the house style is purely llm at the
moment, not my voice yet". The author read all three and accepted them; the veto
route the ticket reserved into this ledger went unused. What this settles past
those three files: prose entering the specification chain later is written in
that voice rather than the panel's, which is the standard for 0050's normative
keywords, 0051's glossary and 0052's security section. The rewrite's own bounds
carry with it — R-, C-, D- and section numbers survive as the addressing scheme
tickets point into, the requirements list holds R-items only, and each preamble
is an Intro section.

**2026-08-29 — the chunk budget is `min(500, modelMax) − specialTokens −
prefix`, and the resolved budget is recorded in the chunker key.** §2.2 read
120 / 768 / 48, "Zotero's geometry, adopted verbatim". That was wrong twice
over: 768 is the platform's ceiling rather than its chunk size, and the
platform pairs that ceiling with a minimum against the model's own window
which we did not copy. We took a ceiling, used it as a target, and dropped the
guard that made it safe, while the embedder truncates past its window in
silence — ticket 0140 measures the identity and its positive control.

Ratified against the two other constructions the ticket put up, and differing
from both:

- **The minimum stays**, rather than a bare constant below 512. A fixed number
  is safe only against models at or above it: it covers the long-window case
  the ticket worried about and fails silently on a short-window one, which
  0140's first verification criterion does not check. Safety by construction
  beats safety resting on a premise about which models exist.
- **The ceiling is 500, not 768.** Every model in ticket 0240's candidate set,
  plus the one zoteus loads today, declares a window above 500 — measured, not
  assumed (`verification/probes/model-window-census.py`, artifact
  `bench/results/0140-model-windows/candidate-windows.json`, 2026-08-29; the
  figures are stated in DESIGN.md §2.2, which owns them). So the minimum never
  binds across the candidate set, the budget resolves to one number whichever
  model 0240 picks, and the chunk key is stable in fact. At 768 it would bind
  at each model's own window instead, roughly half again as much text averaged
  into one vector under a long-window model than under today's — in the
  direction §2.2's standing caveat calls degradation, since one vector is a
  fixed-size summary and a model accepting more text is not a reason to give
  it more.
- **The resolved budget goes in the chunker key.** The dependency on the
  embedder is real in form even where it does not bind, and C1's staged
  invalidation is worth more when a change that *does* move the budget
  invalidates chunks loudly. This amends the invariant 0140 stated for itself,
  "the chunk key does not depend on the embedder": it does, through the
  resolved budget and nothing else, and that value is constant across every
  candidate measured.

**A field-selection problem the ballot did not see, and the second argument for
the low ceiling.** "The model's limit" is not one number. One candidate
declares four position-limit fields spanning a factor of four, the larger ones
extrapolation past what was trained; another declares different limits in its
config and its tokenizer config. Any construction reading `modelMax` must
therefore name which field it reads, and that choice moves the budget. The
census takes the minimum over every field a model declares, the only reading
that cannot over-feed. At a ceiling of 500 the question stops mattering, which
is an argument the ballot could not make because it had not measured.

**Riding with the ruling:** the platform's quarter-rule, where a heading path
costing more than a quarter of the budget is dropped entirely rather than
truncated. The ceiling bounds the whole embedded sequence, heading path
included, and `min(500, width) − affordances` is not `min(width − affordances,
500)`.

**Not settled here.** §2.9's passage count is recomputed from a measurement
rather than divided; `truncation: true` on the embed call remains 0140's
action 4, competing for upstream budget on its own merits. "Adopted verbatim"
is replaced rather than made true: the construction is the platform's, the
ceiling is ours, and §2.2 now says which is which.


**2026-08-29 — no precision knob goes upstream; the ask is a registry.** Ticket
0220 proposed `ZOTEUS_EMBEDDING_DTYPE`, a standalone precision knob, on the
reading that the model was already configurable and precision was the one axis
without one. The local path configures neither: it hardcodes
`Xenova/all-MiniLM-L6-v2`, and `ZOTEUS_EMBEDDING_MODEL` reaches only the API
providers. The asymmetry the ticket argued from never existed, and the remedy is
withdrawn.

What replaces it is one registry whose knob is an entry id, filed as ticket 0440
and held until 0262/0263 have a candidate table under it. The ground is that
precision cannot travel alone. `dtype` resolves to a filename, so it is a bet on
one repo's naming that some repos lose outright; pooling is per-model, and four
of six sweep candidates want `cls` where the drivers hardcode `mean`; input
templates are per-model, and e5 without its prefixes measures worse than an
English model that never needed any. A user given a precision knob and none of
the rest has a setting whose likeliest outcome is a wrong conclusion about a good
model — and the knob would then have to be unwound by the registry that follows
it. Zotero core reached the same shape independently: those fields are properties
of a curated model entry, the preference names the entry, and no precision knob
is exposed anywhere.

Two things this does not retire. The observation stands — the shipped local path
runs at full precision by omission, measured on the default model at 143,7 MB
against 69,1 MB resident — and it is what the registry ask leads with. And the
device finding is separable: `device: 'auto'` fails on an ordinary CPU-only Linux
desktop whichever way the package was installed
(`verification/DEVICE-AUTO-0220.md`), which travels as an issue at no slot cost
and does not wait for the registry. The device-shape entry below, awaiting
ratification, is thereby narrowed rather than answered: nothing is being filed
that passes any device, so the question is now about this repository's fork
rather than about an upstream offer.


**2026-08-29 — correction: the device finding is not an upstream item, and there
is nothing to file.** The entry above says it "travels as an issue at no slot
cost". That was wrong, and wrong twice.

Nobody passes `device: 'auto'`. zoteus passes no options object at all, and
transformers.js defaults to `['cpu']` on Node, so the failure is unreachable from
the maintainer's code. An issue reporting it would describe a problem he does not
have, about a call he does not make — noise dressed as a finding, and the sort of
filing the volume bound exists to prevent even when it is free.

Where the defect does live it is already reported:
**huggingface/transformers.js#1642**, opened 2026-04-14 against 4.0.1, labelled a
bug, still open with no comments. Same error string, same platform, same
mechanism. Confirmed here still present at 4.2.0.

So the finding's value is entirely internal, and that is not a demotion. It is
the reason this fork passes no device, it is the evidence that voided 0220's
device ruling, and it is a standing risk to watch: if transformers.js ever
changes its Node default away from `['cpu']`, the shipped local path acquires
this failure without anyone editing zoteus.

One datapoint here is genuinely absent from #1642, should a corroborating comment
ever be wanted: installing with `--onnxruntime-node-install=skip`, so the CUDA
provider is never fetched at all, fails identically on the absent
`libonnxruntime_providers_shared.so`. That narrows the diagnosis — the
registration is attempted regardless of what is installed, so the title's "when
the CUDA shared library is unavailable" is a symptom rather than the condition.


## Awaiting ratification

- **X1's quantizer: 1-bit measured where the rule says int8.** DESIGN.md §3
  states the rule as *"int8 ships if recall@30 >= 0.98, pool <= 32xtopK, and
  scan+rerank <= 400 ms at 650k; the float32 slab is the permanent fallback."*
  The X1 recall half was measured with **1-bit** codes rather than int8, and the
  substitution was justified in ticket 0025's log rather than here, which is the
  wrong order — DESIGN.md owns the rule and the ruling lands in this ledger
  first. Put to the author now rather than left in the log.

  The substitution is not a convenience. Ticket 0008 measured both on real
  vectors: int8 bought 1,6x against 3,8x less data, while binary bought 13x,
  because Hamming distance is a popcount and removes the arithmetic rather than
  only the bytes. Binary is the stronger member of the same family, and
  measuring it subsumes the int8 question rather than dodging it.

  Evaluated clause by clause on 93 022 real passages (Qwen3-Embedding-0.6B,
  1 024 dims, `bench/results/`):
  - *recall@30 >= 0.98* — **0,9973** at the 8x pool, full width. Holds.
  - *pool <= 32xtopK* — the verdict is claimed at **8x**, well inside 32x.
  - *scan+rerank <= 400 ms at 650k* — not measured at 650k. Measured at
    255 703 x 3 072, where the binary scan is **87,6 ms** against the exact
    scan's 4 893,9 ms. Both figures are the committed artifact's
    (`bench/results/0025-x1-recall/scan-shapes-255703x3072.json`); three
    independent invocations at that geometry gave exact 4 088,7 / 4 196,2 /
    4 893,9 ms and binary 97,2 / 94,1 / 87,6 ms, and the upstream comment
    deliberately quotes the most conservative of the three rather than this
    one. The clause's own substrate is untested and the ship decision is
    provisional on it.

  **The pool multiple is load-bearing and was omitted from the log.** At the 8x
  pool quoted throughout, nomic-768 scores **0,9710 — below the 0,98 bar**; it
  clears at 16x (0,9893), still inside the 32x allowance. The rule passes, but
  only once the pool is named, and a reader checking the headline against the
  rule without it finds a failure. Any ratification should carry the pool.

  Three ways to rule, and the third is available: extend the rule to read
  "int8 or a narrower quantizer" and record the 1-bit evidence against it;
  keep the rule int8-only and treat this as evidence for a separate binary
  decision; or hold ratification until the 650k substrate clause is measured.


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

- **The device ruling of 2026-08-29 rests on a premise that measurement voids.**
  The ruling — the device is always `auto`, never a knob — was made on the
  reading that `auto` hands ONNX Runtime the whole provider list and that ORT's
  own fallback walks past a provider it cannot use, so no escape hatch is
  needed. That reading was taken from `src/backends/onnx.js` and never executed;
  ticket 0220 said as much about its GPU claims, but the same gap covered the
  half that needs no GPU to test.

  Executed, `device: 'auto'` **fails** on a CPU-only linux-x64 machine:
  `OrtSessionOptionsAppendExecutionProvider_Cuda: Failed to load shared library`,
  from `libcublasLt.so.12` being absent. Reproduced against a clean
  `npm install @huggingface/transformers@4.2.0`, where the same call with no
  device option loads and serves bit-identical vectors. There is no fallback
  loop to rely on: `createInferenceSession` passes the provider list straight to
  the binding, `onnxruntime-node` ships the CUDA provider on linux-x64
  unconditionally, and the list is built from `process.platform` and
  `process.arch` alone. Evidence and the mechanism:
  `verification/DEVICE-AUTO-0220.md`; artifacts `bench/results/0220-device-dtype/`.

  So the ordinary Linux desktop is the failing case, not the exotic one the
  ruling set aside. Shipping `auto` unconditionally would end semantic search on
  the default local path for every Linux user without a CUDA runtime.

  The branch built for 0220 therefore passes **no** device and ships the dtype
  half alone, which is behaviour-preserving everywhere and is the only shape
  that neither regresses nor presumes a ruling. What needs the author is which
  shape the device takes from here: keep passing none; pass `auto` and catch the
  failure, which recovers the macOS/Windows accelerators at the price of a
  native ORT error on stderr at every cold start for Linux users without CUDA;
  or pass `cpu` explicitly, measured identical to today but foreclosing any
  future improvement to the runtime's own default. The ruling's *intent* is
  untouched by the measurement and no knob is proposed.
