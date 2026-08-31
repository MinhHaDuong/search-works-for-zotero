# DECISIONS — the ratification ledger

*Append-only — this document is authority's chronological point of entry; its
role in the full chain is stated once, in README.md.*

*The documents these entries ratified — the original sheet, the elicitation
panel's delta (19 requirements, 11 decisions, 7 out-of-scope declarations,
22 kills, each with its evidence), cycle 1's synthesis ("The Settled Ledger"),
and the scout report — are superseded and are now gone: they lived only in the
history this repository was re-rooted away from on 2026-08-29, and 2026-08-31's
ruling below abandoned it rather than republish it. The consolidated truth in
the working tree replaces them, and is now the whole of the record. The cycle-2
panel record that entries below cite by name — the memos, the critiques, the
political and implementation reviews — went the same way. Entries below that
cite a panel document by name cite something no reader can now open; they are
ratified and stay as written, and this paragraph is the standing correction.*

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


**2026-08-30 — GPU acceleration is a requirement: R30.** The author's ruling,
overturning the session's advisory that acceleration stay a mechanism detail.
Three grounds, his. It is the one structural advantage this design holds over
the field: zoteus runs as a native process that can reach CUDA, where the
surveyed plugins and Zotero core's #6012 live inside the application runtime,
which has no GPU path today. The advantage has a sunset — it lasts until GPU
support reaches that runtime — and the sunset argues for shipping while it
matters, not against the promise. It is testable on padme, the designated GPU
host, with the same disclosed-hardware standing R20's letter already has on
the author's machine. And time-to-coverage is user-visible: R1's "eventually"
deliberately declines to bound the wall clock, and "indexing finishes today"
is a promise a user with a capable machine cares about.

The requirement enters the sheet as R30 — R29 stays reserved for ticket 0037's
cross-lingual proposal — with three MUST clauses: use a usable GPU; disclose
the execution device actually serving, on every machine, which is the clause
any harness can gate anywhere; and meet a wall-clock bound to full embed
coverage on the designated GPU host, the bound's value pinned in DESIGN.md
§2.8 from ticket 0264's measurement in the same change that first asserts it,
the C3-replacement pattern, never before the measurement exists.

This ruling also decides the direction of the device-shape question below
(awaiting ratification, 2026-08-29): of its three shapes, only passing a
GPU-bearing provider list and catching the failure can satisfy R30's first
clause — passing none or `cpu` forecloses it. What remains open there is the
mechanism's detail (what `auto` actually selects, observed on padme; the
fallback's cost on CPU-only Linux), which is ticket 0264's to measure, not a
further ruling to make.

**2026-08-30 — I-2 is not filed.** The measurement-correction issue (ticket
0024's second item) is ruled noise: upstream adopted the sqlite backend,
`auto` prefers it on a capable Node, and `docs/semantic-search.md` at v1.10.0
names the JSON ceiling's mechanism and carries measured figures of its own.
The trunk re-measurement taken to carry the filing
(`bench/results/trunk-1.10.0/`, ticket 0025's log) stands as repo-side
evidence; nothing goes upstream for it. The same ruling settles ticket 0460's
open question identically: no upstream issue for the write-side string
ceiling — the sqlite path is the sufficient upstream response. I-3 is
untouched, still behind the zotero#6012 checkpoint.

**2026-08-30 — the presence probe: cache loss becomes a stored warning
state.** X6's headless arm settled one thing while its profile arms stay open:
the full-text content endpoint and the version/census machinery are decoupled —
a derived cache can vanish (content 404) with library version, item version,
and census entry all unmoved, and a source-file md5 unmoved too, since only
the derived cache was touched (`bench/results/0025-x6-version-dynamics/`).
Ruling, from four argued options: verification gains a **content-presence
probe**, and absence becomes a stored warning state (**cache-lost**) on the
item's passages — kept and served, because the source did not change and the
text remains faithful; counted; reason stored in the terminal-state vocabulary
(ticket 0019). Never an eviction: deleting true passages because a derived
cache blinked is the one harmful response. Healing is surfaced, not automated
— a count of items needing Reindex in Zotero — because X6 measured that
nothing re-extracts headless. The md5-widened signal stands as the
ingestion-side complement: necessary for file-driven changes, proven
insufficient alone for cache loss. Rejected: accepting the class as invisible
(the fetch-and-hash convergence path hits these 404s regardless, so the choice
was a designed state versus an improvised one), and automated repair (no API
path exists; mutating the user's library is out of bounds everywhere else in
the design). The probe rides whatever bounded background walk §2.4 ends up
with; its cadence is owned there when scoped issue A's machinery lands
(ticket 0033). X6's still-pending question — what a real re-extraction stamps
— is untouched and still decides §2.4's part (iii).

**2026-08-30 — the embed-call guard travels inside the upstream contribution,
never as its own filing.** Ticket 0140's fourth action — assert the cap in the
chunker and declare the embed call's truncation behaviour explicitly, so an
over-length chunk surfaces loudly instead of embedding its head in silence —
was left open on the 0140 branch as "an author decision under the GOVERNANCE
budget", framed as a possible standalone upstream PR. The author rules it the
other way, and restates the posture the framing had drifted from: this
repository explores, designs, and prepares the upstream contribution — it
implements nothing that ships. The guard is design for the seg/1 PR, which is
the change that creates the exposure: zoteus today chunks in characters and
never over-feeds its embedder, so a standalone filing would spend bounded
upstream budget fixing a latent risk that only our own redesign introduces.
Bundled, it costs nothing and lands exactly where the risk begins. DESIGN.md
§2.2 now states the embed call's contract; ticket 0028 carries the bundle as
an exit criterion.

**2026-08-30 — the chunk is the paragraph; the geometry question is closed.**
The unit of chunking is the authored paragraph, and §2.2's token budget is a
guard against extraction artifacts, never a target. Basis, measured on this
corpus: readable paragraphs run 100–200 words, which the two tokenizer
families in play price at roughly 130–390 tokens (1,26 tokens per word for
the English wordpiece, 1,57 for the multilingual vocabulary, measured on a
196-word abstract; `verification/probes/tokens-per-word-probe.mjs`) — every
authored paragraph fits one 498-token chunk with room to spare. The window
binds only on extraction artifacts: in a 254-PDF sample, most 350-plus-word
blocks carry the glued-paragraph signature — sentence-end, newline, capital —
left when extraction drops the first-line indent that separated paragraphs;
the rest are reference lists and mangled layout
(`verification/probes/glued-block-probe.py`; figures on ticket 0028's log).
Splitting those loses nothing an author wrote.

Two corollaries close with it. Window size ceases to be an embedder-selection
criterion beyond ≥ 512 tokens: authored paragraphs never approach the window,
so a long-context model buys nothing for chunk geometry, and 0140's action 5
— long-context embedders as insurance — is answered, not needed. And seg/1
splits oversized blocks at the recoverable seams, recorded on 0028.

**Rejected: keeping upstream's chunker as it stands.** Read at v1.10.0
(`b132f2d`, `src/features/search/chunker.ts`): `chunkText` collapses all
whitespace — newlines included — to single spaces as its first act, then
strides 1 200 characters with 150 of overlap, snapping cuts to word
boundaries. Three grounds. (i) It is paragraph-*sized* only statistically and
paragraph-*aligned* never: structure is flattened before the first cut, so
boundaries land mid-sentence everywhere and each seam vector averages two
unrelated thoughts. (ii) A character cap is token-safe in Latin scripts
alone: 1 200 characters of CJK exceed the 512-token window severalfold,
reproducing on the multilingual path (R7, C2) the silent truncation 0140
measured. (iii) It is entry-blind, ruled against on 2026-08-26 — the entry
as unit of answer. What upstream got right is kept: the scale of its chunks,
1 200 characters being roughly 250–300 English tokens, inside the paragraph
band — which is why nothing truncates in the field today, and why this
ruling is an alignment fix, not a size change.

**2026-08-30 — the pipeline is four processes, and the extract stage is a shim
over Zotero for now.** The author's architecture: extract, chunk, and embed as
three asynchronous processes, the MCP query servers the fourth — coordinated
through the ledger, whose keyed, idempotent derivations are what make the
stage boundaries process boundaries. The extract process starts as a shim
that only queries Zotero, same functionality as today's in-server crawl,
because the shim's real content is already nontrivial: the bookkeeping that
everything gets extracted *eventually* and *to the latest extractor* — the
since-cursor, extractor-version staleness (ticket 0480's class), and the
per-attachment truncation flags (ticket 0483). Someday it is replaced by a
better extractor — one that, for instance, keeps blank lines so the chunker
can be structural. A fact measured the same day narrows what "someday" must
deliver: the local API serves the cache file byte-identical — blank lines and
form-feed page breaks arrive intact (3 probes, one at the 100-page cap,
`verification/probes/api-vs-cache-probe.py`) — so structure is destroyed by
the *chunker's* whitespace-flattening, not the transport, and the shim can
pass structure through from day one. The workers' lifecycle is run-to-drain —
spawn on a tick, drain the ledger queue, exit — so steady state holds only
the query servers and the RAM arithmetic keeps today's shape; the chunker
and embedder split buys failure-mode isolation (monster-RSS risk is
chunk-side; the embedder is memory-steady), not wall-clock. Propagation of
the process model into DESIGN.md §2.4/§2.5/§2.9 is ticketed rather than
improvised here.

**2026-08-30 — C3's replacement ceiling: server steady-state RSS ≤ ~750 MB
p95.** The author's ruling, given in the batched decision round closing the
embedder study's measurement phase. The 2026-08-29 entry above made R7 hard
and let the 300 MB ceiling give way without setting the new number; this sets
it, from measurement.

The arithmetic, labelled derived: a query server idles near 100 MB
(DESIGN.md §2.9's Node-plus-cache figure) and the recommended candidate,
multilingual-e5-base at q8, resides at 572,6 MB median with a spread of
8,9 MB over five fresh processes (`bench/results/0263-cpu-arm/SUMMARY.json`)
— roughly 673 MB steady, and 750 gives about 11 % headroom. The number is
robust to the recommendation itself: every multilingual candidate measured
sits between 406,6 and 660,0 MB at its 8-bit rungs, so 750 covers each of
them with its idle share. The serve-stale window's second, lazy-loaded model
is a disclosed transient excursion under §2.7's eviction rule, not part of
the p95 promise; the pipeline worker's 500 MB peak is a separate budget and
untouched. C3 and DESIGN §2.8's gate line were re-pinned in the same change
as this entry, and `tests/test_c3_gate_agreement.py` — run red against the
300-era tree first — keeps the two from drifting apart. The executable gate
itself remains ticket 0026's; it inherits this number when it is built.

**2026-08-30 — ticket 0269's normative cleanup changes no system behaviour.**
Three author rulings settle the remaining editorial questions. First,
DESIGN.md §2.9's disk arithmetic remains an estimate, not a contract or a new
gate. Second, CONSTRAINTS.md C2 owns the measured platform constraint on
rowid-constrained MATCH, while DESIGN.md §2.6 alone owns the conditional
fallback and the threshold experiment X4 measures. Third, RFC 2119 keywords
remain limited to the R-items in REQUIREMENTS.md. The three structural rulings
and the constraints bind through their place in the authority chain, not
through upper-case modal verbs; `bench/check_normative.py` therefore remains
scoped to R-items.

**2026-08-30 — the embedder registry lands invariant-first; the study selects
nothing yet.** The candidate measurements are feasibility evidence, not a new
default. Work proceeds in this order: extract the incumbent MiniLM chain as
one registry entry; make every vector-affecting field authoritative while
proving identical vectors and keys; add curated entries and select one by entry
id; validate the selected entry automatically on the actual execution
environment; only then use the golden gate to decide which entries, if any,
ship or become the default. Unknown, unloadable and invalid entries fail
explicitly and never trigger a silent fallback.

The embedding interface makes a shareable local service the architectural exit,
but no daemon implementation is a prerequisite here. The default path remains
in-process and preserves zoteus's install-and-run promise; the same complete
entry may later be requested through a `local_endpoint` provider. Ticket 0491
separately compares reuse of Zotero #6012's existing Firefox inference process,
an embedded child process, a user-session service and an external OS/community
facility against startup, cross-platform packaging, custody, failure and memory
costs, including whether zoteus should build a service or merely consume one.
The Zotero path requires an official bridge: internal `Zotero.ML` and
`Zotero.Embeddings` methods are not an external API. It does not block registry
entries or local validation. Until that decision lands, the existing four-role
run-to-drain topology and C3's per-process accounting remain unchanged.

Automatic validation is a technical compatibility check over a bundled public
fixture: load, shape, finite values, normalization, declared query/passage
templates and basic matched-versus-unmatched discrimination. It is not a
retrieval-quality vote. A content-free attestation of that result may be shared
only by explicit opt-in and may identify the exact entry fingerprint and
runtime shape, never library text, query text or Zotero identifiers. Local
validation remains authoritative. Upstream, this is one design issue with
staged acceptance tests, not a prepared implementation PR series; the
maintainer retains implementation choices at each stage.

**2026-08-31 — no names, only keys.** A committed artifact, ticket or
specification document identifies a document in the author's library by its
Zotero item key and never by its title, its creators or its attachment
filename. The repository is public; a measurement record that names what the
author reads discloses the library one figure at a time, and the disclosure
outlives whatever the figure was for. The key carries every property provenance
needs — stable, unique, resolvable by whoever holds the library — and none of
the properties that make a title a leak.

Scope, and its cost. `bench/query.py` and `bench/smoke_upstream.py` recorded
titles into every result they wrote; both now record keys. 4 630 name fields
were removed from 24 committed artifacts, and the prose in `spec/DESIGN.md`,
`STATE.md` and three tickets was rewritten to cite the key or a generic
descriptor. Each redacted artifact carries a `redaction` field saying what was
removed, because a provenance field that quietly stops existing is worse than
one that never did. One artifact loses identification outright rather than
gaining a key it never recorded: `bench/results/0025-x2-stopwordless/zotero-native-baseline.json`
noted the first hit per query by filename alone, so those rows can no longer
say which document ranked first. That is the accepted price.

**Git history is not rewritten** (author, 2026-08-31). The names are in the
public log and stay there. A scrub of history would break every SHA this
chain cites — `UPSTREAM`, the artifacts' own provenance, every ticket that
pins a commit — to remove what is already published and already read. The
harm is past; the rule binds going forward.

What this ruling does not reach, and what therefore stays open: committed
artifacts also hold `passage` and `snippet` text drawn from the library, and
the benchmark query sets are the author's own research questions. Both are
larger disclosures than a title. Neither is decided here.

**2026-08-31 — the embedder swap is R7 conformance, not a move on the
cost-versus-quality frontier.** The author's ruling. The reason to leave the
incumbent MiniLM is that the library and its reader are multilingual. It is not
that some other model sits at a better point on a trade-off between resident
memory, latency and retrieval quality.

The distinction decides what the selection gate can return. Judged on that
trade-off alone the incumbent wins, and keeps winning: `all-MiniLM-L6-v2` is
several times smaller than every multilingual candidate in the field, and it is
tuned for the one language in which such a comparison is easiest to measure. A
gate that weighs quality against resident memory therefore has one stable
answer — keep MiniLM — however many multilingual candidates it is shown. That is
a property of the question, not a finding about the candidates.

R7 is the question that has an answer, it is hard by the 2026-08-29 ruling
above, and the incumbent fails it on its own model card: `bench/models.json`
records the declared language set of `all-MiniLM-L6-v2` as English alone. So the
swap is a conformance repair on the reviewed baseline; the candidate campaign of
ticket 0240 prices that repair rather than justifies it; and C3's replacement
ceiling, ruled 2026-08-30 above, is what the repair costs rather than what a
quality upgrade bought.

Consequences for the train. Ticket 0495's gate applies R7 first: an entry whose
declared language set is not multilingual is not a candidate for the default,
whatever its golden and resource scores, and the golden gate then chooses among
the entries that conform. The 2026-08-30 invariant-first entry above stands
unamended, and its "which entries, if any, ship or become the default" reads
under this entry as a question about which multilingual entry — never as a route
by which the incumbent is re-confirmed on frontier evidence. Where no entry yet
passes, MiniLM remains in place as the disclosed interim state of a known
non-conformance, never as a ruling that the evidence did not justify a change.

**What this entry does not settle.** It does not rule on R29, the cross-lingual
property — a query in one language retrieving documents in another — which is a
strictly stronger promise than R7 and remains ticket 0037's proposal, awaiting
ratification. Whether R29 joins R7 as a gate criterion in 0495 is open, and it
is not academic: ticket 0266 measured the cross-lingual arm and its negative
control cleared at every deployed dtype for only two of six candidates, so
admitting R29 as a criterion narrows the field before any budget question is
asked. Nor does this entry select an embedder, which remains 0495's after 0493.

**2026-08-31 — R29 is ratified, amended: the cross-lingual promise enters the
sheet, and it is a gate criterion.** The author's ruling on the proposal ticket
0037 has carried since 2026-08-27, and it answers the question the entry above
left open.

R29 says the query language is not the document language: a query in English or
French retrieves relevant Vietnamese content with the user translating nothing.
R7 promises each language its own lane; R29 promises the lanes connect, which is
the stronger claim and the one the author actually wants from a multilingual
embedder. Both are conformance criteria in ticket 0495's ship gate, applied
before the golden and resource gates and traded against neither.

Three amendments to the proposal as drafted. **No new experiment.** The proposal
commissioned an experiment X8 to measure cross-lingual recall. That label has
since been taken — DESIGN §3's X8 is cross-provider fidelity — and the
measurement itself is already done: ticket 0266 ran EN and FR queries against
Vietnamese, German and Russian content at every deployed dtype, and its artifact
is committed. The design cites that evidence instead of commissioning a fresh
experiment under a colliding name, and no new experiment label is allocated.
**The constraints land with their owners.** That keyword search cannot cross
languages, that the embedding space is therefore the only channel, and that
fusion cannot require keyword confirmation before a semantic hit surfaces are
facts about the two query paths, so DESIGN §2.6 carries them beside the CJK
posture they transpose. R10 already forbids a translation service on the default
path, and the sheet's out-of-scope list gains the sentence saying query
translation is not the mechanism. Nothing is restated in CONSTRAINTS.md.
**The cross-lingual slice of the golden corpus is gated separately** from the
monolingual queries, as proposed, so a regression names which of the two
promises it broke rather than reporting one number for both.

**What this entry does not settle.** It selects no embedder — that stays ticket
0495's, after ticket 0493 — and it pins no threshold. R29's gate numbers are the
golden gate's, and ticket 0029 pins them when it builds the slice.
**2026-08-31 — the pre-restart history is abandoned, and the panel record with
it.** This repository's `main` was re-rooted on 2026-08-29; everything before
that date — 121 commits back to the true root of 2026-08-21 — survived only in
one container's clone, on no remote ref. Ruled: let it go. Not preserved, not
pushed to an archive branch, not bundled.

The reason is the ruling above it. Fifteen files at that lineage's tip carry
the document names removed the same day, so preserving the history would
republish exactly what "no names, only keys" was for. Weighed against that,
what the history held: the cycle-2 panel's verbatim session record
(`panel/cycle2/`, fifteen files, 255 715 bytes) and the commit-level provenance
behind nine citations in the working tree. The tree itself loses nothing — all
one hundred and six files common to both lineages are current, the four chain
documents merely moved under `spec/`, and the five tickets that looked missing
are in `tickets/closed/`.

**Every citation into that history is now corrected rather than left
dangling**, which is the part that would otherwise rot silently: a pointer to
`e32afe3` reads as an archive until someone tries it. `CLAUDE.md`, `README.md`,
`spec/CONSTRAINTS.md`, `spec/DESIGN.md` (four sites), `spec/TERMINOLOGY.md`
(two), this document's own preamble, and two tickets said the panel record was
in git history; they now say it is gone. `verification/ACCEPTANCE-0036.md` is
annotated at its head and untouched below it — a dossier rewritten after its
evidence became uncheckable would be worth less than one that says so.

Ratified entries below that cite a panel document by name are not edited. They
are the record of what was decided and why, the ledger is append-only, and the
preamble carries the standing correction instead.
**2026-08-31 — files certify their own embedding chain: a calibration header,
and one chain per file.** Ratified as proposed. Every vector file opens with a
fixed, public set of calibration chunks, embedded by the same chain in the same
run as the corpus behind them, and no file ever mixes chains, so that header
speaks for every row in the file. Verification is thereby local and
self-contained — embed the same chunks, compare, decide — with no registry to
consult and no declared metadata to trust.

What this answers is a defect class realized three times, each a case where the
*declared* identity held while the function changed: pooling hardcoded `mean`
against four `cls` candidates (ticket 0421), the device flag dropped by the
sweep wrapper (0481), `normalize` carried in the registry and applied nowhere
(0486). CONSTRAINTS.md C1's third link derives vectors from "chunks, embedder
identity and model", and all four of DESIGN.md §2.1's stage keys hash *inputs*.
Nothing measured what the embedder did. A header does.

Three consequences follow. Adopting a foreign index becomes a local
measurement rather than a negotiation over provenance, which is the mechanism
the adopt-by-copy entry below is waiting on. Serving through an embedder change
falls out of the invariant: a new chain is a new file, so the old file serves
while the new one builds and the cutover is atomic. And X8 becomes a field
instrument, since every file carries vectors its own chain produced.

**A header does not make the comparison exact, and the ruling does not pretend
otherwise.** X8's fp32 rows are cross-provider compatible without being
bit-identical: `multilingual-e5-base` reaches a minimum cosine of 0,999974 at fp32
(`bench/results/0482-gpu-corrected/x8-cross-provider-fidelity.json`). A hash over
the header would call that a different chain, so a hash is ruled out
cross-machine; it is admissible only as a same-machine tripwire, and ticket 0486
carries the bit-determinism check that claim rests on.

Three sub-rulings settle what the proposal left open. **The calibration vectors
live in the manifest, not the slab's row space** — addressable-as-a-row means a
consumer that forgets to exclude them returns a calibration chunk as a hit, and
the alternative is a permanent exclusion obligation on every reader that will
ever open the format. **The set is 64 chunks, self-authored and published in
this repository as a fixture**, never drawn from the library, since SECURITY.md
lists vectors as an asset and a header derived from library text would leak the
library into every file handed out; they span the four languages X2 separated,
span roughly ten tokens to near the resolved budget, and pass through the
model's own `input_template`. **And the comparison is two tests, not one**:
per-vector cosine against the stored header proves the two vector spaces align,
which is what adopting a foreign file requires, while rank agreement over the
calibration set's own pairwise similarity matrix catches what cosine cannot —
`granite-97m-multilingual-r2` at q8 clears the bar while keeping 0,4164
of its top-30 overlap. Sixty-four chunks give that matrix enough pairs at the
cost of a single forward pass.

Three costs are accepted with the ruling. A cutover holds two slabs at the real
geometry, against budgets DESIGN.md §2.9 owns. The execution device is part of
the chain, so under R30 a GPU-built and a CPU-built file cannot be merged at the
8-bit rungs, where X8 says most candidates fail. And `embed_hash`'s EXISTS guard
on deletes becomes per-file rather than global, which DESIGN.md §2.1 must
restate rather than inherit.

This reshapes DESIGN.md §2.1's stage keys and §2.2's storage section, gives
CONSTRAINTS.md C1's third link a measured half beside its declared one, and
supplies the mechanism the adopt-a-foreign-index entry is waiting on. Ticket
0497 carries the portable format the invariant implies; ticket 0485 still
decides what the header is compared on before that contract is frozen.

**2026-08-31 — ticket 0031 builds calibration from the description, and the
read-at-source instruction is withdrawn.** FIELD-REVIEW.md instructed ticket
0031 to read `Zotero.Embeddings.Calibration` at source before committing to its
own calibration, on the ground that the procedure is an algorithm with
parameters rather than an idea and so the survey's usual read-describe-rebuild
route could not carry it. `zotero/zotero` is AGPL-3.0 and zoteus is MIT, and
that instruction stood with no bound on what the reading could produce.

The premise does not survive inspection, and the ruling dissolves the question
rather than adopting a protocol for it. FIELD-REVIEW.md has already described
the whole algorithm — build a query-by-passage score matrix from a labelled
corpus of relevant and irrelevant pairs, set a per-model minimum relevance
threshold from it, reject a model that cannot clear it — so nothing is
withheld. What the source would add is their parameter *values*, and those are
the one part that must not be reused: a threshold calibrated on their corpus
and their task is wrong for ours by construction, in the same way X2 showed a
stoplist is wrong for a corpus whose majority language differs. Deriving our
own thresholds is not a weaker result; it is the correct one.

So ticket 0031 builds from FIELD-REVIEW.md's description and its own stated
pair-generation protocol, does not read `Zotero.Embeddings.Calibration`, and
FIELD-REVIEW.md's read-at-source instruction is withdrawn in the same change as
this ruling. No contamination question remains to price, and 0031 is unblocked.

What this ruling does NOT touch is reading upstream source to verify a factual
claim about upstream behaviour — the #6012 checkpoint, and the attributions
settled for ticket 0180. That produces assertions about what upstream does,
never code, and tickets 0180 and 0181 depend on it continuing.


**2026-08-31 — the accepted-staleness residue: the corroboration is withdrawn,
and no ruling is disturbed.** Ratified as closing, with no further action.
DESIGN.md disclosed a residue in the freshness contract — re-extraction with no
file change is not caught, accepted as staleness — and asserted beside it that
"Zotero's own embeddings layer documents the same residue". Read at source
(PR head `77e2c4b`, ticket 0180), that does not hold: `embeddings.js` documents
staleness only as model-revision-driven reindex and as pref-toggle eligibility,
and addresses re-extraction without a file change nowhere. The sentence is
removed; the disclosure's own wording is unchanged.

The question this entry was opened to answer — whether the residue was accepted
partly on the strength of the platform accepting it too — is answered from the
record, and the answer is that no ruling was influenced because no ruling
exists. The four-part resolution lives in DESIGN.md §2.4 as design, not as a
ratified reading; this ledger's only trace of its vocabulary is inside the
2026-08-30 presence-probe ruling, where the widened signal appears as a
complement being noted rather than as the thing ratified;
REQUIREMENTS.md carries no R-item for it. That same presence-probe ruling
records part (iii) as still gated on X6's profile arms, which have not run, so
part (ii) is the interim position of an open design — which is what a
corroboration should never have been load-bearing for. The residue is decided
when those arms run, on our own measurement.

What the episode earns is a dimension for ticket 0181's guard, recorded there:
a citation that supports a *design choice* rather than a fact survives
unexamined longest, because nothing downstream breaks when it is wrong, and no
measurement-keyed guard would ever have caught this one.


**2026-08-31 — the session-start hook is project state, and `.gitignore` now
says which part.** The `.claude/` ignore rule was written for per-session agent
runtime state, and a `SessionStart` hook is not that: a hook only runs if it is
already in the tree the session opens on, so ticket 0498's exit criterion — a
fresh container that runs `make check` with no human installing anything —
cannot be met while the rule covers it. The rule is narrowed to `.claude/*`
with two exceptions, `.claude/settings.json` and `.claude/hooks/`, and the
reason is stated in the file beside them. Everything else under `.claude/`
stays out, which was the original rule's whole point.

Ratified after the change was flagged for veto rather than merged quietly,
because it edits a rule the author wrote deliberately. It sets no precedent for
the rest of the directory: a third exception is a third ruling.


**2026-08-31 — the header's cheap identifier is a projected vector at a published
seed, and no hash of anything.** Ratified as proposed, in shape rather than in
threshold. The calibration-header entry above rules a hash out cross-machine
because X8's fp32 rows agree in space without agreeing in bytes, and admits one
only as a same-machine tripwire. The obvious repair — hash the sign bit of each
dimension rather than the bytes, 32x smaller and blind to low-order noise — fails
too, for two independent reasons, and ticket 0499 establishes both from artifacts
already committed here.

At the worst same-chain row (`multilingual-e5-base`, fp32, cross-provider cosine
0,999974) **1,763 of 768 sign bits move**, so an exact sign hash agrees on one
vector 17,1 % of the time and on the 64-chunk header never: hashing amplifies,
because one flipped bit in some 49 000 destroys the match. And ticket 0008
measured two dimensions over 95 % one-sided on 93 022 real vectors, **both of them
dimensions the model never activates**, at a millionth or less of the median
magnitude — their sign is float noise, and an all-or-nothing hash hashes those
bits beside the ones carrying the corpus.

**What identification actually needs is a ratio**, and naming it is what makes the
question answerable: the distance to the nearest chain that is not this one, over
the distance this chain moves when only the provider changes. The two populations
sit in different artifacts — the noise floor is X8's summary rows (the same chain
on two arms, at the same model and rung), the signal is inside each cell (a dtype
against the fp32 rung beside it, one provider). Paired that way, sign distance
identifies an **fp32** file for 6 of 6 models at **31,67x** the noise floor in the
narrowest case; at the 8-bit rungs **1 of 12** cells clears even a 2:1 margin and
**3 invert**. That boundary is the cost this ledger already accepted from the
cosine side — the device is part of the chain at the 8-bit rungs — reached
independently in sign space.

**The object that carries the ratio is a seeded random projection.** Preserving
the ratio is a far weaker requirement than preserving cosine at the noise floor's
precision, and Johnson-Lindenstrauss meets it exactly, being multiplicative on
distances: a nearly-identical pair stays nearly identical, both distances shrink
by nearly the same factor, and the ratio survives. Sign bits quantize the small
angle away instead, which is the whole of why they fail. Measured over each
model's own measured cosines, 200 simulated headers per width, worst trial rather
than mean, with a control projecting to the source width that must reproduce the
unprojected ratio: **one width serves all six models — 32 dims, 8 192 bytes per
header, 24,0x smaller than the full fp32 header, keeping a worst case of 29,68x
against the narrowest unprojected 31,67x.** The header being 64 chunks is most of
that steadiness, the projection's error being zero-mean.

Three properties make it admissible where a data-derived basis is not. The matrix
comes from a **published seed**, so it carries no corpus — SECURITY.md lists
vectors as an asset, and a basis fitted to the library would put the library into
every file handed out. It is **reproducible** on both machines from that seed,
with nothing to transmit. And the guarantee is **distribution-free**, so the
anisotropy that broke the sign-bit argument does not weaken it. MRL truncation is
model-specific and PCA on the calibration set is circular; neither can be the
format's rule.

So the header carries `R·v` at 32 dims *beside* the fp32 calibration vectors and
never instead of them, as the cheap first read that fails fast. The ratified
per-vector cosine test stays what adopting a foreign file rests on. Nothing is
claimed at 8-bit, and no projection can claim anything there: preserving a ratio
faithfully is no help where the ratio is already below one.

**Ratified in shape, not in bar.** The threshold the projected distance is
compared against is NOT ratified here: it waits on ticket 0485, which decides what
the header is compared on, and must be sized from measured flip and angle
distributions rather than from a simulation. Two further limits are ratified with
the shape rather than papered over. The evidence is derived from committed
cosines, not from vectors — the artifacts store six decimals, so a rung printed
1,0 still admits 0,244 flipped bits at 768 dims, and ticket 0499 carries the
real-vector arm. And the theta/pi identity behind the sign half is a floor, not an
estimate: reproduced exactly under an isotropic control, it understates flips
**7,76x** under coordinate-wise quantization, because a coordinate near zero needs
almost no error to change sign.

This adds the projected vector and its seed to DESIGN.md §2.2. The fuller reshape
that the calibration-header entry above owes that section — the header itself,
§2.1's stage keys, the per-file `embed_hash` guard — is still outstanding and is
that entry's, not this one's.

**2026-08-31 — the excess-weight ruling: the guards that check prose are not
the work.** The repo was audited against its own purpose. Its two sanctioned
outputs are stated in GOVERNANCE.md — changes merged upstream, and the
one-time acceptance-harness transfer — and the audit asked of each standing
commitment whether it serves one of them. The measured shape: 3 187 lines of
guard code against 6 426 lines of measurement driver; ten of twenty test files
testing the guards rather than the science; eight of the nine guards in `make
check` existing to keep 6 743 lines of prose across thirteen documents
mutually consistent; and thirteen of fifty-six closed tickets having been pure
document maintenance.

The finding that settles it is not a ratio. **The guards are green and the
bench is red.** Two drivers have been unable to open any index built since the
upstream table rename (ticket 0100), `make check` has never opened a database
at all, and 0013's concentration figures stand quoted in STATE.md, produced by
a driver that cannot run — so they can be believed but neither re-measured nor
refuted, while the figure guard passes them, because it checks that a number is
declared and not that it is reproducible.

**The line.** A guard that protects a measurement's fidelity, or the honesty of
text leaving the repo, earns its place; a guard that keeps internal documents
consistent with each other does not. The first kind has paid repeatedly — the
pooling guard catches a class where four of six candidates are `cls` against a
hardcoded `mean` and retrieval degrades silently; the dependency guard exists
because the gate once died at its last step after eight guards printed success;
the review of outward text caught a false public claim of prototyping work that
does not exist. The second kind has produced no upstream artifact.

**Dropped:** ticket 0161 (a guard on which documents are in scope for another
guard — and by its own analysis unable to fire for the case that motivated it,
since CONSTRAINTS.md's platform figures have no artifact to match against) and
ticket 0181 (a guard requiring prose to be read for semantic intent, which its
own actions predict "will be fought and then disabled"). Ticket 0320 is
rescoped, not dropped: its sabotage proof stands and the parallel-append merge
shape recurs by construction, but it becomes one property — the ratified entry
count never decreases — because git already holds every prior text of the
ledger and only loss is invisible to review.

**Not dropped, and named so the ruling is not over-read:** ticket 0101, which
is the one guard that would have caught the schema break, and is science rather
than prose; the pooling and dependency guards; ticket 0180's one-time
attribution audit, as distinct from the standing guard built on it; and the
review discipline applied to every text sent upstream, which is where this
repo's care demonstrably pays.

The ruling is about standing commitments, not about care. Nothing here lowers
the evidence bar for a claim, a number, or a sentence sent to the maintainer.

**2026-08-31 — ticket 0400 goes (author, on the same day it was defended
here).** The tracker closes. It was filed to keep an evidence gap visible —
"22 of 28 are not yet measured" — and what it produces is bookkeeping: an
evidence column, a guard recomputing it, a tally to keep true. The work that
would close the gap is not its own; it is 0029's fixture corpus, 0026's gates
and 0032's offer, which the tracker itself names as its children. A tracker
whose children hold all the work and whose own output is a status page is the
excess weight the earlier entry today describes, one level up.

**What this ruling does NOT touch, stated because a parallel branch was
building on the tracker when it landed.** The goal-1 work of 2026-08-31 stands
in full: the standing table read as a test board, goal 1 as a conjunction over
terms, the terms/instruments distinction, R14 folded into R1, R30 split with
time-to-coverage becoming R32, and `bench/check_progress.py` reading goal
membership from the ledger rather than from the status page. None of it lives
in the tracker. The rulings are ratified here, the membership is in
`spec/README.md` and in the guard, and closing a ticket removes none of them.

**What the closure does require, and it is owed by whoever closes it.** Ticket
0400's log ties goal 1 to the tracker in terms — "GOAL 1 ORDERS THIS TRACKER'S
WORK", later corrected, and "this tracker's unit is unchanged". Those notes are
the only place some of that reasoning is written down outside the ledger
entries. Re-home what is load-bearing into 0029, 0026 or 0032 before closing,
rather than closing over it. The evidence column itself is not abolished by
this ruling and stays where it is; what ends is tracking its completion as a
work item.

This reverses a withdrawal recorded here earlier the same day. That withdrawal
was right on its own information — a session must not contradict a ruling it
has not read — and is superseded by the author ruling with both branches in
view. The near-miss it recorded stands as the finding: nothing in this repo
detects two sessions ruling opposite ways on one ticket before the merge.



**2026-08-31 — STATE.md is a pointer page under forty lines, and FIELD-REVIEW
leaves the chain.** Two cuts under the excess-weight ruling, both by author
direction the same day.

**STATE.md keeps only live state, and history belongs to the git log.** It was
542 lines, of which roughly 330 were measurement sections against `bae82a7` —
the archived pre-merge tree — which the file itself said had never been
re-measured, while upstream moved three versions past it. One of those sections
quoted figures whose driver cannot open a current index (ticket 0100), so the
page asserted numbers that could be believed but not reproduced. A "Current
handoff" dated three days back had already been found wrong once on the
in-flight slots. The cut follows `RUNBOOK.md`'s self-sunset of 2026-08-30 and
this repo's standing rule that superseded documents are deleted rather than
archived in the tree.

The durable home of a measurement is its artifact under `bench/results/` and
the ticket that produced it; prose quoting one is a convenience, never the
record. Thirty-seven figure-guard declarations named STATE.md. Thirty-one also
named their ticket and simply lost a duplicate slot; five had no other prose
home and are deleted with the prose; one — 0009's swept-codepoint count — was
re-anchored to R19, which quotes it live and which the guard had been reaching
only through STATE.md, so the shrink contains a small coverage gain. The
ratchet fired on the way through and was lowered deliberately, with that
accounting written where it is enforced.

**FIELD-REVIEW.md moves to `verification/`.** At 1 974 lines it was the largest
document in the repo and 29 % of its prose, while owning no design number, no
requirement and no threshold — a dated snapshot, by its own description. That
is the definition this repo already gives `verification/`: evidence, not
authority, cited by path from the ticket it serves and never a source of truth.
It keeps its place in the governance and chain-dedup scanned sets, because it
is public authored prose rather than a generated report, and both guards fail
loudly on a scanned document that vanishes — which is how the move was made
safely. The chain is twelve documents and 4 367 lines, from thirteen and 6 743.

Two test fixtures hardcoded `spec/` when building their scanned-document
trees and broke on the move: the guards were right and their own tests were
what failed. Both now derive each directory from the scanned path, so the next
document to move does not repeat it.

**2026-08-31 — the standing table is read as a test board, and goal 1 is his
own first promise, made strong.** The author's instruction, in his words: read
the completion table in `spec/README.md` as test-driven development, and take
goal 1 to be the upstream README's first promise made strong — *search all my
library, hybrid* — meaning large documents, multilingual, everything indexed
today, and retrieval in reasonable time.

Two things follow, and the first is a re-reading rather than a new column. Under
TDD the test is written before the thing it tests and it must fail first, so the
`evidence` column *is* the test column: `measured` means an assertion ran, and
`code` and `inferred` mean no assertion exists. Rows in those two states are not
red. They are unwritten, which from a distance looks the same and is worse — a
red test is a claim about the system, an absent one is a claim about nobody. The
page has said this since the evidence column existed; what the ruling adds is
that the unwritten rows are the *work*, not the caveat. `delivered` then stops
being a verdict a reader assigns and becomes a result a run reports, which is
ticket 0400's fourth exit criterion arriving by another road.

The second is scope. Thirty promises do not have a first, so the author names
one: not our sheet's opening row but *his* README's, the one already published
over his name — "find anything in your own work", hybrid keyword and semantic
over the library, the body of every PDF included. Made strong means the four
strengthenings the instruction lists, each of which is already a requirement:
every document including the monsters (R9) at the design-point size (R8); every
language on the default path (R7), whose keyword half only matches at all if the
two normalizers agree (R19); everything indexed, unattended (R1), with a
text-less attachment ending as covered-with-a-reason rather than retried forever
(R14), the reaching watched rather than asserted (R26), one's own notes and
annotations in the corpus at all (R16), and the whole of it legible in one
sentence (R17); today rather than eventually, which is exactly what R30's
hardware clause promises where R1's "eventually" declines to; and an answer
inside the latency the query path is budgeted for (R6).

Goal 1 binds: R1, R6, R7, R8, R9, R14, R16, R17, R19, R26, R30.

That list is the reading, and the reading is vetoable — the instruction gave the
axes, not the roster. Three deliberate exclusions, stated so the silence does
not read as an oversight. The same README bullet also promises the matching
passage *with its page number*, which is R24 and R25; that strand is gated on
the segmenter behind experiment X5 (ticket 0028) and is a second goal, not a
tail of this one. R21's golden set keeps goal 1 green once it is green and does
not help make it true, so it is the net under the bundle rather than a member.
R2 and R4 shape how coverage grows and what a half-built index answers, which
is the promise's manner rather than its substance.

Nothing new enters the work train. The tests goal 1 needs are the ones already
scoped — the fixture corpus (ticket 0029), the repo-side gates (ticket 0026),
and the acceptance harness offered upstream (ticket 0032) — and goal 1 orders
them rather than adding to them: it says which assertions get written first, and
ticket 0400 keeps the count.

**2026-08-31 — correction: goal 1 is a conjunction, not a queue.** The author,
on reading the entry above: *"ordering was not significant."* That entry closed
by saying goal 1 "orders" the already-scoped work and "says which assertions get
written first". The reading is withdrawn. Nothing about the bundle ranks its
members against each other or against anything outside it, and the number in its
name is a label rather than a rank — a second goal, when there is one, is not a
successor.

What the bundle asserts instead is a conjunction. The upstream README's opening
promise, made strong, is kept only when all eleven members hold at once, and any
one of them failing falsifies it whatever the other ten do. That is what makes
the bundle worth naming: eleven separate rows can be reported as ten-elevenths
done, and a promise cannot. It also fixes what the goal's bar is for — it shows
where the members stand, and it is not a progress bar, because there is no
partial credit in a conjunction.

Membership is unchanged, and so is the rest of the entry above: the TDD reading
of the evidence column, the three stated exclusions, and the fact that no new
work enters the train. `spec/README.md`, `spec/TERMINOLOGY.md` and `CLAUDE.md`
are edited to match; the entry above stands as written, per this ledger.

**2026-08-31 — step 1: goal 1 is a conjunction over terms, and time-to-coverage
leaves R30.** The author ruled the perimeter review's four-step order — rule the
shape, then the membership, then the sheet, then write the assertions — and this
entry is step 1. Everything below is his, except where it says otherwise.

**The shape.** A *term* is a property the user meets; an *instrument* is a thing
that decides whether a term holds. Goal 1 is a conjunction over terms alone, and
its instruments are named beside it rather than counted in it. The sorting test
is one question per clause: if this clause fails and nothing else changes, is
what the user can know or do any different? The defect it removes is concrete —
goal 1 read not-kept partly because this repository's own `make check` does not
run a fold sweep, which makes a claim about zoteus hostage to a Makefile here,
and makes the bundle unhandable to anyone else.

**Binding is per clause, not per requirement.** R19 is one row and two clauses:
its property (every token the query normalizer produces, the index normalizer
can also produce) is a term; its cadence (the sweep runs on every check) is an
instrument. The same mechanism is what lets a requirement be split when the
clauses turn out to belong to different promises, which is what happened to R30
below.

**R14 is folded, not dropped.** Its clause becomes part of R1's assertion: a
no-text attachment ends covered, with its reason recorded, counted in the
denominator. It keeps its MUST and its row; it stops being a term, because its
only failure mode reaches the user as R1 failing.

**R17 is a term, against the reviewer's recommendation.** The review proposed it
as an instrument and offered R4 as the carrier of the user-facing half. That was
wrong on the text: R4's single MUST is availability, and its honesty sentence is
rationale carrying no force, so R17 is the only normative home in the sheet for
honest coverage reporting. The author's ground: honesty and observability during
the transition phase matter. The promise is "search *all* my library", and a user
who cannot be told how much is searchable cannot hold anyone to "all". R26 stays
an instrument by the same test — it changes what this repository knows, not what
the user can.

**What counts as searchable, ruled.** Everything searchable is the MVP, even if
not extracted, chunked and embedded at the latest version. So R1's "covered"
means searchable by *some* version, which is D3's serve-stale, and it is R17's
per-stage report that keeps that honest. Two consequences. R11 and R3 stay out
of the bundle: counter churn re-embedding the library does not make anything
unsearchable, because the old vectors keep answering, so freshness currency is
not this promise's business. And stale is admitted where truncated is not — R9
is untouched, since a monster indexed by its opening pages is not searchable at
an older version, it is missing.

**R30 is split, on measured ground.** The review recommended against a split and
the author overruled it, correctly. R30 carried both "use the GPU where one is
usable, and name the device serving" and "on the designated GPU host, time to
full embed coverage meets a bound". Measured, finishing today is a property of
the *configuration*, not of the hardware: in the runtime zoteus ships, on a
laptop CPU, the incumbent small model reaches an overnight build of a
design-point library, and so do the two small multilingual candidates, while the
base-sized candidates do not — GPU or no GPU
(`bench/results/0025-x1-recall/embed-feasibility.json`, and the CPU cells ticket
0481 recovered from `bench/results/0264-gpu-arm/`, whose `auto` runs never
received a device). Binding goal 1's "today" to R30 would therefore have said
hardware-conditional where the evidence says configuration-conditional.

So R30 keeps hardware use and device disclosure and carries no wall-clock bound,
and **R32 — the build finishes today** enters the sheet: on the reference machine
DESIGN.md §2.8 names, an initial build with the default configuration reaches
record coverage of the whole library inside the record bound and body coverage
inside the build bound. Two bounds, because the design already stages it that
way. The reference machine is laptop-class CPU, which is the second gain of the
split: the term stops being decidable only on the disclosed GPU host, and the
gate runs wherever the fixture runs. `spec/REQUIREMENTS.md` and `spec/DESIGN.md`
are edited to match.

**A consequence for the embedder decision, recorded before it is taken.** R32
puts a throughput constraint where the study carried a quality one: an entry the
default cannot meet the build bound with is not eligible to be the default. On
today's evidence that separates the small multilingual candidates from the
base-sized ones. The study that measured them, ticket 0240, is closed and its
recommendation (ticket 0267) explicitly declines to set a default, so the
constraint lands on the ticket that does — ticket 0495, which already applies
resource budgets to decide which entries ship and whether the default changes.
Build time joins those budgets.

Goal 1 binds: R1, R6, R7, R8, R9, R16, R17, R19, R32.

Goal 1 instruments: R19, R26.

R19 appears in both by clause, per the binding rule above. R21 joins the
instruments when step 3's recall term exists; R27 leaves, because R11 did.
R30 leaves the bundle outright. What step 1 does not settle, and step 2 owes:
R12, and the two items the review found missing — hybrid retrieval and recall.

**2026-08-31 — steps 2 and 3: the search perimeter is what Zotero shows, and
retrieval gets the two clauses it never had.** The author's rulings, taken
together because each was given as an answer to the last.

**The perimeter.** Asked whether R12 was in the bundle, the author answered with
a rule instead of a verdict: the search perimeter is every item visible in the
user's Zotero, the group libraries they subscribe to included. That settles R12
— a subscribed group is visible, so it is in scope, and being subscribed it is
also synced, so this is the locally-served set and no cloud path is implied —
and it settles the shape of every future question of the same kind. Two edges
were ruled where "visible" reached further than intended: the **trash is out**,
since taking it literally would contradict R15 outright, and R15 keeps owning
the transition; and **feeds are out**, being neither owned nor curated. One case
needed no ruling, because the machinery already carries it: in a group readable
without fetchable attachments, the item is inside the perimeter and its body
text is not, which is R14 and R17's metadata-only state.

The perimeter is not R12's to state. It is what R1, R8, R9, R12 and R16 each
presuppose and none of them says, so it enters `spec/REQUIREMENTS.md` as a
fourth ruling beside the three of 2026-08-26, and the glossary gains **search
perimeter** as ours — the inherited entry for `library` stays as it is, because
it correctly says what Zotero means by the word and this is not that.

**R33 — lexical, semantic and hybrid each work.** Ruled in on the author's
"having all three work is of the essence", as a requirement rather than a
clarification: D5 is a resolved-decision row and a MUST parked there is
invisible to the normative pass, and a recall floor cannot see a missing mode,
since a semantic-only system clears a floor measured over the path it has. It
is written as observable behaviour and not as mechanism, on R5's own lesson —
the obligation is on the honesty of the result, never on which operator
enforces it — so the combination rule stays DESIGN.md §2.6's. Its falsifiers,
in the order the clauses appear: an embedder-only system misses the exact
string, a keyword-only system misses the paraphrase, a fusion that drops one
side misses the agreement case (which is the shape of the open defect
`spec/FIELD-REVIEW.md` records in a neighbouring project), and a mode parameter
that silently serves something else misses the last.

**R34 — if it is in my library, I find it.** Minimum retrieval quality enters
the MVP, and two rulings shaped it. *Default only*: the floor binds the default
configuration, not every shipped mode. *A requirement cannot defer to a k later
defined*: the line the author draws is that a **threshold** may be pinned from
measurement, because "the build finishes inside the bound" means something
before the number exists, while a **metric shape** may not, since recall at one
result and recall at a hundred are different properties rather than different
strictnesses of one. So k is in the requirement, at the ten `spec/DESIGN.md`
§2.8's golden set and ticket 0029's answer sets already use. Those two rulings
composed: with the scope narrowed to the default, the absolute clause subsumed
the keyword-only baseline clause that was drafted beside it, and the baseline
returns to being what it always was in practice — a diagnostic the harness
reports, and the one that condemned granite-97m at its q8 rung. R34 therefore
defers nothing and invents no number.

R21 and R34 read the same pinned set in opposite directions, and DESIGN.md §2.8
now says so: R21 compares a run against the last and tolerates legitimate drift,
R34 compares it against the pinned answers and tolerates none. A corpus can be
stable and wrong, which is why both readings exist.

**R6 gains its second clause.** Its only MUST was that freshness work on the
query path is O(1); the hard budget lived in DESIGN.md §2.9, which stated it and
attributed it to R6, so the attribution was aspirational and the term was
unassertable. R6 now carries the clause and points at §2.9 for the value, on
R30's precedent.

**The rosters, restated whole.** Terms gain R12, R33 and R34; instruments are
unchanged. Ticket 0029's exit criteria widen to the intersections, because
scale and language are independent axes everywhere except through the embedder,
and a fixture that tests each alone would let a French monster or a
multilingual library at scale pass unexamined.

Goal 1 binds: R1, R6, R7, R8, R9, R12, R16, R17, R19, R32, R33, R34.

Goal 1 instruments: R19, R26.

Not settled here, and named so the silence does not read as a decision: the
two-level model the author raised — a portable fixture level and a real-library
level, where the second is what re-earns the first's fidelity rather than a
second suite — is not ruled and no machinery was built for it. The terms table
carries no level attribute until it is.

**2026-08-31 — tracker 0400 is dissolved into the work it tracked.** The
author's instruction, and the ground moved under the tracker while goal 1 was
being written. Its function is now performed continuously by two things it
cannot compete with: `spec/README.md`'s evidence column states the gap for all
thirty-four requirements, and `bench/check_progress.py` recomputes the tally on
every build, so the statement cannot go stale between readings the way a
tracker's inventory does.

Its substance went where the work is, rather than being deleted: the unit of
work — one assertion per MUST clause, never one per requirement, since a
compound requirement graded as a single token is what made `partial` ambiguous
before the evidence column split it — to tickets 0026 and 0032; R17's four-part
payload behind one MUST to ticket 0026, written as four; the precondition role,
no fixture library and no assertion, to ticket 0029; and R26's missing RFC 2119
force to ticket 0080, which owns its rewrite. One rule had no home but this
page's own honesty section, because no guard can hold it: **a row is not
upgraded to `measured` without the artifact that measured it.**

What dies with the tracker is its inventory of which rows sat at `inferred` and
which at `code`. That is the one thing the evidence column already says
continuously, which is the argument for dissolving rather than a loss.

Entries above this one cite ticket 0400 as live. They were true when written and
are not edited, per this ledger; the ticket resolves in `tickets/closed/`.

**2026-08-31 — two levels, and the second one re-earns the first.** The author
raised it as a related thought — bench on a portable fixture, bench on a real
library — and ruled it in. Named rather than numbered, because a digit in this
vocabulary would be a quantity nobody could tell from an address: the **fixture
level** is the committable corpus that runs wherever the gate runs, and the
**library level** is the author's real library or a disclosed machine, which
cannot be committed at all — copyrighted documents, private text, one host.

What makes this a model rather than two lists is the relation between them. They
are not two suites covering the same ground twice. **The fixture level is where
assertions run; the library level is where the fixture's fidelity is re-earned.**
Every fixture that stands in for something real — a synthetic monster, a
reference machine, a scaled corpus — carries a fidelity claim, and only the
library level can renew it. A surrogate whose fidelity nobody renews is a green
that has stopped meaning anything.

The rule is not new; it has been ratified three times as separate facts, and
each is now an instance of it. R20's synthetic surrogate is revalidated against
the real dictionary at each release (2026-08-29). R30's disclosure clause gates
everywhere while R32's build bound needs its reference machine. Ticket 0025's
substrate map says which experiment runs where. Stating the rule once is what
lets a fourth case be recognised without a fourth ruling.

Two things follow without further decision. The dependency split ticket 0498
built is the same seam seen from another side: the fixture level runs on
`requirements-check.txt` in a bare container, and the library level may want
`requirements-drivers.txt`, a GPU, or a running Zotero. And the reason the
author's second thought matters — that neither the requirements nor the harness
is zoteus-specific, and that Zotero core's own work needs a real-library level
too — is that a fixture-level spec is the half that can travel, while the
library level never can.

`spec/README.md`'s goal tables gain a *decided at* column over a closed
vocabulary — `fixture`, `library`, `both` — and `bench/check_progress.py` fails
on any other word, on a row that sheds the cell, and on a row that keeps the old
three-cell shape. The per-requirement assignment is a reading and is vetoable:
it says where each assertion can be decided, not where it has happened to run.
`both` is the value the vocabulary exists for, and today it falls on R9, R12 and
R32 — a surrogate monster, a cross-library guard whose repro ran against a real
Zotero, and a build bound whose reference machine stands for a real library.

What is deliberately not built: no date column, no per-row record of when a
fidelity claim was last renewed. That obligation is DESIGN.md §2.8's, where the
gates live, and a page carrying a date per row would rot faster than the claim
it records.

**2026-08-31 — what verifies a promise is not itself a promise, and thirty-four
requirements were too many.** Two rulings from the author, one criterion, eleven
numbers retired.

**The criterion.** An item belongs in `spec/REQUIREMENTS.md` only if it is a
promise someone outside this repository can hold us to. Anything that exists to
*verify* a promise is apparatus, and apparatus belongs to the gates in
DESIGN.md §2.8. The tell had been visible on the status page for weeks without
being read: three rows were red — R20, R21, R26 — because *this repository's*
build does not run them, so a page reporting on zoteus was reporting on us. R19
makes the same point from the other side: with its cadence clause gone, the
property it protects has been shipped upstream since the fold merged, and the
row moves without anyone writing code.

**A second criterion, for size.** Thirty-four items overstated how many
independent promises the system makes, because the sheet had been treating the
item as the unit when the unit is the MUST clause — the point tracker 0400 made
before it dissolved this morning. Two items are one requirement when one is a
clause of the other, or when they can only fail together. Merging items merges
no clauses, so nothing testable is lost; what goes is the pretence that an item
is the unit.

**Retired, and never reused.** R20 and R26 as apparatus; R21 with them, its
thin user-facing residue — *my answers do not change under me* — now carried by
R34's absolute floor. R19's cadence clause, leaving its property behind. Then
the merges: R14 and R2 into R1 (what "covered" means, and the order coverage
grows in); R11 into R3 (counter churn is the special case of recompute what
changed); R9 into R8, retitled *size does not disqualify*, because a library is
large in both directions at once; R25 into R24, which have never been able to
fail apart; R28 into R15, removal being complete at the item scale and the
install scale; R27 into R17, one observability surface rather than two; and R30
into R32 and R17 — the promise was always that indexing finishes today, the
GPU was how, and *naming the device serving* is a clause of the coverage
sentence. R31 stays, rewritten to state its property instead of its registry.

Twenty-three remain. `spec/REQUIREMENTS.md` numbers to R34 with gaps, and the
gaps are the record: a retired number is never reused.

**The instruments roster goes with them.** It existed to name the apparatus that
happened to be written as requirements — a fact about the sheet's history rather
than about goal 1 — and this criterion removes its subject entirely. Goal 1
keeps one roster. The defect that exposed it is worth recording: step 1 ruled
that R21 would join the instruments once the recall term existed, R34 landed,
and neither the page nor the ledger moved, because the guard could only compare
the page against the ledger and both were wrong together. A roster whose only
check is self-consistency drifts exactly like that.

Goal 1 binds: R1, R6, R7, R8, R12, R16, R17, R19, R32, R33, R34.

Eleven terms, R9 having merged into R8. `bench/check_progress.py` loses its
instruments path, and `bench/check_normative.py` gains one: its exemption table
is empty now that R26 is gone, and an entry naming an item the sheet does not
declare fails the build, because an exemption for a requirement that does not
exist excuses nothing and hides that it is stale.

**2026-08-31 — a requirement names no implementation, and goal 1's subject is
the promise rather than a document.** The author, reading goal 1 back: *line 1
already off; R must not refer to zoteus.*

Two things were wrong and they are the same thing. **The sheet named the
implementation twice** — R13 spoke of "two zoteus processes on one data
directory", R23 of "a zoteus with a different schema version" — which narrows a
promise to one codebase and contradicts what makes the sheet worth handing to
anyone: it states properties, not mechanisms, so it survives reimplementation.
Both are rewritten to the property (two server processes; an index written under
a different schema version), and `bench/check_normative.py` now fails on any
R-item naming the implementation, with a test. Zotero itself is untouched: the
platform is the domain, and the sheet is about a library held in it.

**And goal 1 was defined by that implementation's README.** Its heading and its
opening sentence derived the bundle's subject from the upstream README's first
bullet, which made the goal exactly as portable as one project's marketing copy.
The subject is restated as the promise in the user's own terms — *search all of
my library*: every document it holds, in every language it is written in,
indexed today and answered in reasonable time, by meaning and by exact words
alike. The README keeps one sentence, demoted to what it always was: the promise
happens also to be published by the implementation this page measures, which is
what makes it cheap to test rather than argue, and if that text changed tomorrow
goal 1 would not.

Entries above this one define goal 1 by the upstream README. They record how the
bundle was arrived at, which is true, and they are not edited; this entry is
where its subject is stated.

**2026-08-31 — R7 becomes two tiers, and the languages are named rather than
implied.** The author: English, French and Vietnamese are MUST; Arabic, Russian,
Chinese and German are SHOULD; Spanish is SHOULD too.

The old sentence listed five languages at one strength — French, German,
Vietnamese, Greek, Russian — which said nothing about what may be traded when a
candidate covers four of them well and the fifth badly. RFC 2119 already has the
distinction the list was missing, and the sheet's own intro states it: SHOULD is
a preference that may be set aside **for a stated reason**. That last clause is
what makes a tier different from a wish, and it is now the operative half of
R7's second sentence.

Three consequences, and none of them costs anything today. **Chinese in the
second tier is the explicit CJK decision R7 used to defer** — the sentence
demanded that any CJK ambition be decided explicitly and never silently, and
this is the explicit decision. It carries the keyword half with it: the platform
two-gram geometry read at source on 2026-08-29 stops being context and becomes
what a Chinese query term has to survive, which lands on R19's
normalizer-agreement clause. **Arabic moves from the untested bullet into the
second tier**, RTL and all, and Hebrew stays untested. **Greek leaves the matrix
altogether** and joins the untested list, which now names what it covers instead
of implying it: Greek, Hebrew, Portuguese and the rest ride the default path,
and a language nobody measured is not a language anybody promised.

Checked before ruling rather than after: every candidate the embedder study
measured — granite-97m, granite-311m, arctic-m-v2, gte-base, e5-small, e5-base —
declares `en`, `fr`, `vi`, `ar`, `ru`, `zh`, `de` and `es`, so **the filter's
field does not move** and ticket 0495 inherits no new work. Three legacy
sentence-transformers models lose Chinese and two granite v1 models lose Russian
and Vietnamese, none of which was in contention.

`bench/check_models.py` reads both sentences out of the sheet rather than
restating either. The MUST tier stays a filter: a candidate that does not declare
it is not a candidate. The SHOULD tier is **reported and not failed**, because a
guard that fails a SHOULD has promoted it to a MUST, which is the one thing the
convention asks a reader not to do — so a candidate short of the second tier
prints where the stated reason would have to go.

**2026-08-31 — the second tier covers script classes, not communities; Hindi
joins, Portuguese is covered by argument.** Ratified by the author on the
proposal put to him.

The rule, which is what keeps the tier from growing by sentiment: **R7's second
tier names one language per script and morphology class, never one per
community.** A language earns its place by stressing the pipeline in a way
nothing else in the tier does, not by how many researchers write in it. Today
that reads right-to-left (Arabic), Cyrillic (Russian), no word boundaries
(Chinese), compounding (German), Latin-with-diacritics (Spanish) — and it had a
hole at abugida, which **Hindi** now fills: Devanagari combines vowel marks and
forms conjuncts, so normalization that is a no-op in Latin is not one there.

**Portuguese is covered by argument and not by measurement**, and the sheet says
so in those words rather than leaving it unnamed. It sits in the class Spanish
represents, as Italian does. That is a weaker guarantee than a tested language
has, which is the point of writing it down: Greek and Hebrew, by contrast, are
in no tier's class at all and are covered by nothing.

Checked before ratifying: all six measured candidates declare `hi` alongside the
rest, so **the field does not move again** and `bench/check_models.py` needed one
line — Hindi in the ISO map it reads R7's sentences through.

The cost lands on ticket 0029 rather than on the embedder study, and it is real:
each tier language needs freely licensed documents and pinned answers in the
fixture corpus, and a public-domain Devanagari or Arabic set is work nobody has
done. That is exactly the case the tier was built for — a SHOULD may be set
aside for a stated reason, so a language whose corpus cannot be assembled is set
aside in the open, with the reason recorded on the ticket, rather than quietly
missing.

Ticket 0026 carries the consequence for R19: the character-folding sweep was
built on Latin plus Cyrillic assumptions, and Arabic, Devanagari and the
platform's two-gram Chinese geometry each break a different one.

**2026-08-31 — the sheet's form: a name, a sentence, a paragraph.** The author's
instruction, applied to all twenty-three items: `Rx. Oneworddescriptor.` then one
sentence describing a testable user-facing feature, clear with no context needed,
then one paragraph unpacking it.

The old form was a bolded title and a blob, and the blob did three jobs at once —
it stated the promise, argued for it, and cited whichever document owned a number
it leaned on. A reader could not tell which sentence they were being held to. The
new form separates them: **the sentence is the contract** and stands alone, the
paragraph is everything that explains it, and the one-word name is the handle the
rest of the chain cites. Nothing testable moved; every MUST and MUST NOT clause
that was in an item is in the same item, either in its sentence or in its
paragraph.

Three consequences worth recording because they are what the format costs.
`bench/check_normative.py` and `bench/check_progress.py` both parsed the old
bullet shape and now read the new one, the second gathering the sentence across
its wrapped lines — a promise cut at the first newline is a promise the page
could never quote back. `bench/check_models.py` reads R7's two tiers out of its
sentence, which the reformat rewrote, so its two patterns moved with it. And the
status page now quotes the **sentence** rather than the name: a promise column
reading "Coverage" tells a reader nothing they came to the page for.

**2026-08-31 — the time bounds are specified, and every one of them names its
hardware.** The author: specify time budgets and bounds — *on given hardware*.

The parenthesis is the ruling. **A time bound with no machine attached is not a
bound**, and R32 had been carrying two of exactly that kind, deferred under the
pin-when-first-asserted rule until someone measured. The measurements exist, so
`spec/DESIGN.md` §2.8 now states them and states the machine they hold on.

*The reference machine* is a laptop-class x86-64 CPU, four cores, no GPU, in the
runtime the implementation ships — the class the feasibility run used. Modest on
purpose: a bound met only on the author's desktop promises nothing to anyone
else, and the promise is to the user with a laptop.

*Records*: SHOULD inside 30 minutes at the design point, MUST inside 1 hour.
*Body text*: SHOULD inside 12 hours, MUST inside 24 — which is what "indexed
today" means once it is written down rather than felt. The SHOULD/MUST split is
§2.9's own shape for the query budget, reused because it says the true thing
twice over: what one should expect, and what one is owed.

Two consequences fall out with no further decision. The eligibility test ticket
0495 applies stops being a comparison between candidates and becomes a number:
on the CPU evidence in hand the two small multilingual candidates land inside
the SHOULD band and the four base-sized ones clear neither bound. And R32's row
on the status page becomes falsifiable for the first time — a row asserting a
bound nobody had written could never have gone red.

The disclosed GPU host stands as a second configuration where the same bounds
hold with room to spare, never as a substitute for the first. A machine slower
than the reference is not a failure of the promise; it is outside the
disclosure, and the gate reports which machine it ran on so a reader can tell
the two cases apart.

**2026-08-31 — the build bound is a rate, and the wall clock is what it means.**
The author, on the bounds pinned an hour earlier: throughput instead. Ratified
with one substitution — **per passage, not per item**.

Per item does not survive R8. Items are deliberately non-uniform there: a
15k-page PDF is one item and a two-page note is one item, so a per-item rate
measured on short papers says nothing about the PDF, and one loose enough to
admit the PDF is absurd for papers. The passage is the unit the work is done in
and the unit every committed artifact already measures.

What the rate fixes is a real defect in the wall-clock form ruled an hour
before: "inside twelve hours at the design point" promises a 15k-library user
something and a 60k-library user nothing at all. A rate is library-size
independent, and it is assertable from a few hundred passages per stage, so a
regression surfaces in a minute rather than at the end of a build.

What the wall clock keeps is that it is the user's own question — *will my
library be searchable today?* — which a rate answers only after arithmetic over
a library size the user may not know. So both stand, as one bound stated once
and derived twice: on the reference machine the embed stage MUST hold ≤ 150 ms
per passage and SHOULD hold ≤ 75 ms; against §2.9's measured census those are
23,7 h and 11,8 h, which is where the 24-hour MUST and 12-hour SHOULD come from,
and the same bracket over a 15k library's record chunks gives the 1-hour and
30-minute record bounds with no second rate. **The census is the bridge and the
arithmetic is shown**, so a reader with a different library can redo it.

Two costs are named in §2.8 rather than left to be found. A rate hides fixed and
non-linear work — model load, compaction, WAL checkpoints — so a sample can pass
where a full build does not, which is why the gate asserts the rate every run
and the wall clock whenever a full build exists, and treats a disagreement as a
finding about the non-linear part. And a rate does not transfer across passage
length distributions, which is why the fixture's distribution is pinned with the
corpus.

**2026-08-31 — the rate is on the pipeline, and the arithmetic that exposed
it.** The author, on the throughput bound ruled minutes earlier: what about
extracting and chunking speed?

The question is a defect report. The bound had been written on the **embed
stage**, and a build finishes when extract, chunk and embed have all finished,
so a bound on one stage was never a bound on the build. Worse, the numbers did
not survive the question: the 24-hour wall clock over §2.9's measured census is
152,2 ms per passage for *everything*, and the embed bound alone had been set at
150 — **98,6 % of the whole budget**, leaving 2,2 ms for extraction, chunking and
the record write together, which is not a number anyone could meet. The rate was
right and its scope was wrong.

So the bound is now the pipeline's: MUST ≤ 150 ms per passage, SHOULD ≤ 75, and
the per-stage split is an **allocation** rather than a finding — embed ≤ 120 and
≤ 65, the rest 30 ms and 10 ms. The allocation may be re-cut in any proportion so
long as the total holds, because the total is what the user feels and the split
is an engineering convenience. Stating it that way is what lets two unmeasured
stages sit inside a pinned bound without the bound becoming a guess.

Extract and chunk are unpinned and said to be: no artifact in this repository
measures either. What is known without measuring is that extraction is usually a
read of the platform's own full-text cache rather than a parse — the census
counted the caches — and that the expensive path is the attachment the platform
has not indexed, where a 15k-page PDF yields tens of MiB. **Ticket 0500** opens
to measure both on the reference machine, over both extraction paths and the
observed mix, and to re-cut the allocation from what it finds — or to report that
the total cannot hold, which would be a finding about the bound rather than
about the stages.

**2026-08-31 — the segmenter is for books and proceedings first; the dictionary
is a rare case.** The author's ruling inverts what seg/1 was specified against.
Every clause of DESIGN.md §2.2's segmenter was written for the dictionary, and
the rare case had been standing in for the common one.

Three consequences, and the propagation is ticket 0502 rather than improvised
here. First, the discriminating heuristic goes: heading candidates are accepted
on the headword *rhythm*, a median gap and MAD over candidate spacing, which
works only because a dictionary's entries are near-uniform in length. A book's
chapters and a proceedings' papers are unequal by nature, so that statistic
measures a property the primary class does not have — it is not a threshold to
retune, and what replaces it as the core signal is a table of contents, chapter
and section numbering, author bylines, and chapter starts on page boundaries.
Second, the entry arithmetic in the same section is the dictionary's story, and
the "first-class peers" framing it calls the entry ruling's whole point is now
the illustration rather than the point: a book's entry is a chapter, tens per
item, not hundreds. Third, X5's rule changes corpus AND ground truth, which is
the one place this ruling makes the work cheaper: hand-scoring cuts against a
printed dictionary needed a human with the physical book, where a book's own
table of contents is mechanical ground truth for the cut set it should have
produced. The bar's form survives; what it is sampled from does not.

What this ruling does NOT touch, stated because a careless propagation would
take it: the dictionary holds a second, unrelated role as the monster document.
REQUIREMENTS.md makes a 15 000-page PDF first-class, X3a baselines the uncapped
document that once measured 2 084,9 MiB, and DESIGN.md §2.8's RSS gate is
calibrated against that class. Demoting the dictionary as a segmenter TARGET
leaves it exactly where it is as an RSS FIXTURE, and the extraction-cap example
in §1 is likewise a coverage statement, not a segmenter one. Two roles, one
document; only the first moves.
**2026-08-31 — the perimeter review is consumed, and one question outlives it.**
This entry rules nothing. It records where each finding of the day's perimeter
review landed, and takes the review off the awaiting list, because the entry had
begun to say the opposite of what happened: it closed with "nothing above is
acted on … `spec/README.md` carries the roster unchanged", and by the time it
could be read the roster had changed twice.

Finding by finding, with the ruling that consumed it. **Hybrid unbound** — R33,
which puts lexical, semantic and the two combined in the sheet as observable
behaviour, so a semantic-only system now fails a term instead of passing every
one. **Nothing asserts that search finds anything** — R34, the absolute floor
over the pinned set, scoped to the default configuration, with the metric shape
in the requirement and only the threshold left to measurement. **The latency
term rests on a clause that does not say so** — R6 gained its second clause and
points at DESIGN.md §2.9 for the value, on R30's precedent. **R30 bound by its
wrong half** — split, over the review's recommendation and on measured ground:
R32 carries the build finishing, R17 the device disclosure, and R30's number is
gone from the sheet entirely. **R26 excluded and depended on** — R26 is retired
as apparatus; the newest-first prefix question it carried survives its item and
is re-addressed below.

The structural question under the five is settled the way the review proposed,
one member excepted: goal 1 is a conjunction over terms alone, R17 is a term
against the recommendation (the sheet has no other normative home for honest
coverage reporting, and a user who cannot be told how much is searchable cannot
hold anyone to "all"), and the instruments roster the review's shape implied has
since gone too, its subject removed when the sheet retired the apparatus items.
Of the two omissions, R12 is in — not on its own argument but on the perimeter
rule, which decides every question of that kind — and R11 with R3 are out,
because stale still answers and freshness currency is a different promise.

What outlives the review is its last paragraph, which no ruling has reached:
R23, and whether the goal is kept by reaching the state or by holding it. It
moves to the awaiting list as its own question rather than staying buried in a
consumed one.

The drift is worth naming, because it is the second of the same shape in one
day. The first: step 1 said R21 would join the instruments once the recall term
existed, R34 landed, and neither the page nor the ledger moved. Both are open
text going stale under rulings that answered it, and nothing checks that — the
guards read the sheet and the ratified stream, never the questions.

**2026-08-31 — three open questions were not open: one answered twice, one
answered on another branch, one addressed to a retired item.** Bookkeeping,
recorded rather than performed silently, since the awaiting list is where the
author's attention is spent, and a list that keeps settled questions spends it
on nothing.

**R20's letter vs the gate's practice: deleted, having been answered twice.**
Both halves were ratified on 2026-08-29 — the cadence (the budget assertion
stays in `check-slow`, with a cheap fixture asserting the mechanism in the fast
tier) and the fixture (the deterministic synthetic monster at the measured size
satisfies R20's intent, conditional on revalidation against X3a at each
release). The question stood open for two days after being settled, then lost
its item as well this morning; what it argued about now lives in DESIGN.md as
budget and gate, and in no R-item at all.

**The accepted-staleness residue: deleted, having been closed on 2026-08-31.**
The closing entry is above in this ledger, ratified as closing with no further
action; the question stood in the awaiting list beside it. Neither branch was
wrong — one appended a question, the other answered it — and the merge kept
both, which is the failure mode of a section that is appended to from several
places and reconciled from none.

**R26's prefix granularity: kept, re-addressed to R1.** R26 is retired and R2 is
merged into R1, so the reading belongs to R1's newest-first clause. DESIGN.md
§2.3 already states it without the retired handle. The substance is unchanged
and the author's veto stands; what changed is that it is no longer a spare
interpretive question, because R1 is a term of goal 1 and the assertion ticket
0026 owes cannot be written without knowing which granularity it asserts.


**2026-08-31 — robust and efficient beats strict, and the priority classes said
plainly.** The author, on the design: *I prefer robust and efficient to
strict.* A tie-break for the whole design and not for one paragraph. Where a
guarantee can be stated strictly or robustly, it is stated robustly; where
strictness costs throughput, strictness loses.

Asked what the ordering actually is, he stated it: **three priority classes —
metadata, then notes and annotations, then body text — and newer first inside
each. New or deleted data in any class is discovered in reasonable time.** That
is the design's own Phase A / A′ / B plus the reconcile tick, and it is now how
§2.3 opens. The second sentence is a separate promise from the first: ordering
says what is indexed next, discovery latency says how fast a change is noticed,
and §2.3 said the first at length while never saying the second.

The ruling is not new and that is the finding. On 2026-08-29 he rejected R26's
strict newest-first prefix on the same instinct — recency orients the work, it
does not impose a verifiable total order over a library that changes while the
build runs — and that entry says in terms that the veto is that entry. It had
not been executed. Two days later DESIGN.md §2.3 still carried the vetoed
paragraph, and §2.8's convergence harness still asserted prefix arithmetic over
a boundary cursor. Both are corrected in this change. The band cap keeps its
anti-monopoly job and loses its standing as an observable; what else has to
replace it is ticket 0080's, unchanged.

**Two sheet edits, flagged for veto.** R1 now names the three classes and says
newest-first applies inside each, because R26 carried the tier priority and R26
is retired — the promise had no normative home left. And R1 gains the discovery
clause from the author's second sentence, with the value delegated to §2.4 on
R6's pattern, since ordering and discovery are different obligations and only
the first was written down.

One session error belongs with it, because it is the same class as the three
the awaiting list was reconciled for this morning. That reconciliation kept the
cycle-2 prefix-granularity question and re-addressed it to R1. It should have
been deleted: the author had answered it two days earlier. A question already
settled was carried forward as open, in the very change that removed three
others for being settled — reading the questions against the sheet, and not
against the rulings.


**2026-08-31 — the class order is ruling 2's, and discovery becomes R35.** The
author, on the two clauses added to R1 earlier the same day: *look at other R,
R1 may not be best home.* It was not, for two different reasons.

**The class order was already stated twice.** Ruling 2 has always said that
every item's record is indexed before any body text; R32's paragraph said it
again to explain why it carries two bounds; R1 said it a third time this
morning. Three copies of one fact is this repository's most expensive recurring
defect, and none of the three named the middle class — notes and annotations
are indexed between the record and the body, and no document said so. Ruling 2
now names all three classes. R1 and R32 point at it. R1 keeps what is its own:
newest-first inside the order, a priority order rather than a page cursor.

**Discovery becomes its own item, R35, beside R3 under Change and cost.** The
test is the one the retirement used: two items are one requirement when they
can only fail together, and these fail apart — a library can be re-indexed at
exactly the right cost and still take a day to notice a deletion. So R3 bounds
what staying current costs and R35 bounds how long it takes. The gap was real
and pre-dated this morning: R1 says an item becomes searchable without saying
when the system learns there is one, R32 bounds the first build and not the
steady state, R15 says deletion removes text everywhere without saying when,
and the reconcile cadence and deletion latency in DESIGN.md §2.4 were promised
to nobody. R35 delegates its value there on R6's pattern.

**R35 enters at `inferred`, which is the weakest evidence class, and ticket
0503 owns getting it out.** The machinery exists upstream — incremental updates
on a library version cursor, deletion reconciling against the key set — but
nothing here has read what triggers a run or how often, and no latency has been
measured. The ticket reads the trigger at source, measures both latencies, and
either confirms §2.4's values as the bound or re-pins them.

**Goal 1's membership does not move here.** R35 is a candidate term — indexed
*today* is a claim about a state the library has to keep having — and that is
exactly the question already awaiting a ruling in the list below, whether the
goal is kept by reaching the state or by holding it. A bundle should not gain a
member as a side effect of a new requirement being filed.


**2026-08-31 — a requirement is readable, and it states its number: the
discovery bound is one minute.** The author, on R35 as filed an hour earlier:
*R must be readable. Do not start reintroducing variables. Bound is 1 mn.*

R35 said "inside the discovery bound" and delegated the value to DESIGN.md
§2.4. That is a variable: the reader of the sheet is sent to another document
to find out what was promised, and a coined name for a number reads as
machinery rather than as a promise. R35 now says one minute, in the sentence,
and the glossary entry that defined the name is deleted. The precedent it was
built on — R6 pointing at §2.9 for the latency budget — is not touched here,
but it is the same defect and R32 carries two of them.

What R35 promises, said plainly: the system notices a new, changed or deleted
item within one minute. Noticing is not indexing, so a 15 000-page PDF is
noticed as fast as a note and indexed a great deal slower. Deleting is the
strict case, because removing text costs nothing: deleted text stops being
served inside the same minute. A Zotero that is not running has nothing to
report, so the minute starts when it comes back.

Two design consequences, both executed. The 60 s reconcile tick is what
delivers the minute, and §2.4 now says so — worst case is one full tick.
Deletion subtraction moves from every tenth tick to every tick: the old cadence
disclosed ≤ ~10 min, which the promise no longer allows. What the item census
costs per tick is unmeasured, unlike the full-text census beside it, so ticket
0503 measures it; if it proves too expensive to run every minute, that is a
finding about the cadence and never about the bound.


**2026-08-31 — the rule was general, and R6 and R32 were the rest of it.** The
author, on being asked whether the same fix applied to them: *but I TOLD YOU
ALREADY.* He had. "Do not start reintroducing variables" was a rule about
requirements, not a note about R35, and asking again was asking him to rule
twice on one thing.

So both are stated. R6 promises an answer within 3 seconds and inside 700 ms in
the ordinary case, instead of "inside the hard budget". R32 promises 150 ms per
passage or better on a laptop-class machine with no GPU — an hour to records and
a day to body text for a 15k library — instead of "inside the record bound and
the build bound" on "the reference machine", which was three variables in one
sentence.

The ownership inverts with them, and that is the substantive half. DESIGN.md
§2.8 and §2.9 no longer pin these numbers; they derive them and say whose they
are. The design keeps what it is for — which laptop, the census bridge, where
the query milliseconds go, the per-stage allocation ticket 0500 will re-cut —
and the sheet keeps the promise. `bench/check_progress.py` already required the
page's promise cell to quote the sheet exactly and exempted it from the digit
rule on that ground, so the page followed both sentences with no change to the
guard.

What is not swept in: R33's combination rule and R31's configuration identity
still point at DESIGN.md. Neither is a value — they are mechanisms the sheet
deliberately does not fix, on R5's lesson that the obligation is on the honesty
of the result and never on which operator enforces it.

**2026-08-31 — goal 1 is kept by reaching the state, R23 does not join the
terms, and its clause folds into R1's assertion.** The author's ruling on the
question the perimeter review left behind, taken with a second on the scope of
R32's bounds. This settles the last of the review's findings; nothing of it
outlives this entry.

**Reaching, and the reading was never open.** The choice was put as a choice and
it is not one: the terms' own grammar forecloses it. R32 is *the build finishes
today* — an event with a clock, which cannot be held, only reached — and R1 is
*becomes searchable*. A conjunction cannot be evaluated over members of two
temporal types, so goal 1 speaks to a state reached, or half its members want
rewriting into properties they were never drafted as. Goal 1 therefore says so
in words on `spec/README.md`, where it said nothing before and a reader supplied
the duration themselves.

**R23 stays out of the terms, and the case for admitting it is answered rather
than overruled.** The case is real — a version rollback is a mundane, in-scope
event, and after it the library is not searchable at all, which is closer to the
promise's own words than anything R11 ever was. Three things answer it. **R4 is
already out**: *the index answers at every moment of its life, including during
its first build* is the sheet's own home for an empty or rebuilding index, and
admitting R23 on the empty-index worry while the direct case sits outside would
be incoherent. **R14's precedent fits exactly**: R14 kept its MUST and its row
and stopped being a term because its only failure mode reaches the user as R1
failing, and R23's abandonment case reaches the user the same way — the library
is not searchable until R1 re-earns it, unattended. **What survives that fold is
a cost promise**: after an abandonment nobody deletes anything by hand and
coverage regrows unasked, so R1 is kept on its letter and what the user actually
loses is a day. Bounding that day is R3 and R32's family, and R3 stayed out of
the bundle on step 1's *stale still answers*.

So Wednesday is not unowned. Under reaching, an event that empties the index
restarts the same promise, and the bundle's terms already say what has to happen
next and how fast.

**The fold is where option (ii) alone would have lost something.** Ruling only
that the event is R1's to repair would take the failure mode out of the bundle
and out of the harness in one move. Instead, on R14's pattern, R23's clause
becomes part of R1's assertion: ticket 0026's convergence harness asserts that
after a schema-version flip in either direction, coverage returns unattended,
with no file deleted by hand, inside R32's bounds. R23 keeps its MUST, its row
and its own stronger promise — that migration ought to make the rebuild
unnecessary at all — which is filed upstream as issue #34 and is not goal 1's to
carry.

Goal 1 binds: R1, R6, R7, R8, R12, R16, R17, R19, R32, R33, R34.

Eleven terms, unchanged, restated because this entry ruled on a twelfth.

**R32's bounds are any full build's, not only the first.** The second ruling,
and the one that makes the first bounded rather than rhetorical. R32 read *a
first build*, which left the rebuild after an abandonment bounded by nothing —
the same work, the same machine, the same default configuration, and no promise
about it because of how it was reached. The bounds now bind whenever the system
builds from nothing, however it got there. What does not move is the line R35
draws beside it: these are a full build's bounds and never those of a library
already in service, where R3 bounds the cost and R35 the delay. `spec/REQUIREMENTS.md`
R32 and R35 and `spec/DESIGN.md` §2.8 are edited to match; no number changes.


**2026-08-31 — ticket 0320 is closed won't-do, and "rescoped, not dropped" is
superseded.** The author, asked which of two decisions on the same ticket was
live — the close of 2026-08-30 (git history already preserves the append-only
ledger, and a committed per-entry census is maintenance machinery
disproportionate to the residual merge-resolution risk) or the rescope of
2026-08-31 (the program drops, one property survives: the ratified entry count
never decreases) — ruled the close. The rescope is the later text but not the
later decision; it was written before the question was put.

So the fifteen-line residue goes with the rest of it. The sabotage proof stands
as a description and not as a commitment: a whole ratified entry can be deleted
and `make check` stays green, and nothing will now notice. What the repo relies
on instead is git, which holds every prior text of the ledger, and review of the
diff that edits it — which is what the close said in the first place.

This is a new entry rather than a correction because the excess-weight ruling
above says, in terms, that ticket 0320 is rescoped and not dropped, and that
entry is ratified. The ledger is append-only, so a reversal names what it
reverses and leaves it standing. That is this ticket's own subject settled by
the rule rather than by the guard it asked for.

**2026-08-31 — the second perimeter review: goal 1 is the MVP, and the MVP is
"works for me".** The author, naming the bundle's acceptance standard for the
first time. Everything below follows from it, and the roster grows by five
clauses and inverts its levels.

**The frame does three things, and the third is what reopened the roster.** It
names the user, so the languages are the author's own, the pinned set is his
questions, and the machine is his machine. It makes the goal an MVP, so what is
not needed to use the system daily is not in it. And it makes the **library**
the deciding level rather than the surrogate, which no earlier reading did.

**The structural finding: the roster's inclusions were re-founded and its
exclusions were not.** The original bundle stated three deliberate exclusions,
and every one of them is argued from the upstream README's first bullet — the
page-number strand as "a second goal", R21 as the net, R2 and R4 as "the
promise's manner rather than its substance". Then the subject changed: goal 1
stopped being that bullet and became the promise in the user's own terms, and
the *inclusions* were reworked twice afterwards while the exclusions were never
re-stated. They had been resting on a subject that no longer exists. Under this
frame they rest on nothing, so each was put again.

**R29 joins, and it was an omission rather than an exclusion.** Nothing ever
ruled it out: R29 was ratified on the same day the roster was being reworked and
no entry asked whether it joins. R7, already a term, promises each language its
own lane; R29 promises the lanes connect, which the sheet itself requires to be
gated separately so a regression names which promise it broke. Under *works for
me* it is the sharpest term in the bundle — the author's three languages are
exactly R7's MUST tier, and without R29 the library answers only in whichever of
them he happened to type.

**R24's page clause joins, and its exclusion was a schedule reason.** The strand
was excluded as gated on the segmenter behind experiment X5. Step 1 later
established that binding is per clause and not per requirement, which is how R19
is in by its property and out by its cadence, and R24's clauses have different
fates: *a hit leads to the page it came from* needs no segmenter and is already
partly delivered, while *the primary locator is the entry heading* waits on X5
with the dedup clause. A term is not excluded because its work is blocked. The
page clause binds; the other two stay out with the segmenter.

**R18 joins as R17's per-query complement.** R17 says how much is searchable;
R18 says, of this answer, whether nothing matched or the scope is not indexed
yet. R32's own bounds admit a day in which body text is still arriving, so the
MVP meets empty answers inside the window the bundle grants, and a null result
that cannot be told from a gap makes every conclusion drawn from it unsound.

**R4 and R35 join: the additive event.** R4 was excluded as the promise's
manner; R35 was never considered. The library grows weekly and the perimeter is
live, so a bundle speaking only to a state reached describes the library as of
one build unless something binds the arrival of new items. R1 carries the
additive case in words and no clock; R35 owns the clock; R4 owns what the index
answers while it is still filling.

**A consequence for this morning's R23 refusal, recorded rather than left to
rot.** That entry gave three grounds, and the first was that R4 is already out,
so admitting R23 for an empty index while the direct case sat outside would be
incoherent. R4 is now in and that ground is spent. The refusal stands on the two
that never depended on it — R14's precedent, R23's failure mode reaching the
user as R1 failing, and the cost residue belonging to the family step 1 excluded
with R3 — and the fold into R1's assertion is untouched. Anyone reading the
morning entry reads this one beside it.

**Nothing is cut.** The two candidates were put to the author as facts rather
than as arguments, and both came back standing: group libraries are subscribed,
so R12 binds whole, and the library is at the design point, so R8's scale clause
is a claim about something he owns.

**The levels invert, and this is the ruling with the most consequence.** Six of
the eleven terms decided at `fixture` alone, which means the conjunction could
have gone all-green on a committable corpus while the author's library had never
been searched. That is the right reading when goal 1 means *the design is sound*
and exactly the wrong one when it means *works for me*. So the library level
decides and the fixture stands in for it, its fidelity re-earned there — the
pattern DESIGN.md §2.8 already states for the RSS surrogate, applied the other
way round. Every term a real library can decide is `both`; R16 stays `library`,
having nowhere else to be decided. What this costs is stated rather than hidden:
the goal is now kept by an acceptance session against the author's own library,
and no gate alone can keep it.

Goal 1 binds: R1, R4, R6, R7, R8, R12, R16, R17, R18, R19, R24, R29, R32, R33, R34, R35.

Sixteen terms, R24 by its page clause alone and R19 by its property clause
alone. `spec/README.md` is edited to match: five rows, the levels, and the bar
and counts the guard recomputes.

**2026-08-31 — the ladder is named, and goal 1 keeps its number.** The author,
asked what would stand below the bundle if its number ranked anything: *write up
the goals ladder at the end of the sheet.* Two things are ruled by that
instruction, and a third is deliberately not.

**The ladder is a dependency reading, and it is written in the sheet rather than
on the status page.** What depends on what is a property of the promises
themselves, so it belongs beside them; where each bundle *stands* remains
`spec/README.md`'s, and the ladder states no standing.

**Goal 1 keeps its number.** The name is a label and ranks nothing — ruled
2026-08-31 — so a bundle that sits third in dependency order is not renamed to
match. Renumbering would rewrite every reference in this ledger, the page, the
guards and the tickets, to move a label that was never a rank. The ladder says
where goal 1 sits and leaves its name alone.

**What is NOT ruled: the two lower rungs' rosters.** Goal 1's membership is a
ruling with a machine-readable line and a guard that fails the build when the
page and the ledger disagree. The rungs below it have neither, and this entry
does not give them one. They are named, their candidate members are listed, and
the sheet says in terms that only goal 1's roster is ruled — because a bundle
with an unruled roster that reads like a ruled one is exactly the drift the
instruments roster died of.

The rungs, in the user's own terms. **It is mine, and I can leave** — R10, R15,
R22, R31: nothing leaves the machine unasked, deleting the data directory is the
whole uninstall, one obvious switch stops the work, and a configuration proves
it runs here before it is used. This is the entry condition: nobody points an
indexer at a real library for a day unless trying it is reversible. **It survives
the second day** — R3, R13, R23: cost proportional to what changed, two
processes on one data directory, an index under another schema version ending up
served. Then goal 1 above them.

Two consequences worth recording, because neither was visible before the rungs
were drawn. The durability rung **precedes** goal 1 rather than following it: R32
admits a build that runs for a day, and an index a second process corrupts or a
version flip abandons mid-build never reaches the state goal 1 measures, so
these promises are what make arrival possible rather than what protects it
afterwards. And R23, refused as a term this morning and folded into R1's
assertion, is that rung's charter member — the refusal was about which
conjunction it belongs to, never about whether it matters.

**R5 is on no rung.** It is the one residual promise the sheet has that the
design answered negatively — the constrained path lost to ranking everything —
and its user-facing residue moved into goal 1 as R18. A decided question with
its promise already rehoused is not a goal.

**2026-08-31 — the ladder is sequential, the number is the build order, and the
sheet is partitioned across five goals.** The author, rejecting the reading that
kept the bands unruled and the conjunction unranked: *I want a clean ladder of
reqs, with sequential goals. The intention is to prioritize work. We start by
building the tests for the lower ladder, then making it work.* Put again after
the objection below was raised, and this entry executes it in full.

**What this reverses, named because the ledger is append-only.** Two rulings go.
*The number names the bundle and ranks nothing* (2026-08-26, restated
2026-08-31): the number now ranks — it is the order the work is done in, and
that is the whole reason the ladder exists. And *goal 1 keeps its number*
(2026-08-31, earlier today): the bundle that carried that name is now goals 3, 4
and 5. Entries above this one say "goal 1" meaning the search bundle. They are
not edited, and this entry is where the renaming is stated; a reader meeting the
old name in an older entry should read it as goals 3 through 5 together.

**What is NOT reversed, because it is the reason the bundles exist.** Each goal
is still a conjunction, kept when every one of its members holds and at no state
before that. Sequencing the goals does not give any of them partial credit, and
a lower goal kept does not make a higher one partly kept. What the number now
says is which conjunction to make true first, never how much of one is true.

**The ladder is a partition, and that is what "clean" buys.** Every requirement
the sheet declares sits on exactly one rung, the rungs number from 1 without a
gap, and `bench/check_progress.py` now enforces both alongside the per-goal
rosters it already held: a requirement on no rung is work nobody scheduled, one
on two rungs is work counted twice, and a gap in the numbering is a rung nobody
can stand on. The guard reads five rosters from this ledger instead of one, and
the last line ruling each goal is that goal's live roster.

The five, bottom first, each stated in the user's own terms.

**Goal 1 — I can install it and take it off again.** Nothing leaves this machine
unasked, one obvious switch stops the work, deleting the data directory is the
whole uninstall, and a configuration proves it runs here before it is used.
Lowest because its assertions need no corpus, no build and no library: they are
decidable the moment the system is installed, which is exactly what the build
order wants first.

**Goal 2 — it does not lose or corrupt what it built.** The cost of staying
current is what changed, two server processes on one data directory do not
corrupt or duplicate, and an index under another schema version ends up served.
Second because these need a built index but not a good one, and because a build
that cannot survive its own second day never reaches the goals above.

**Goal 3 — it answers, and it is honest about what it has.** Coverage converges
unattended, the build finishes inside its bounds, the index answers while it is
still filling, the query path waits for no freshness work, the normalizers
agree, and it says how much is behind an answer and which emptiness an empty one
is.

**Goal 4 — it finds the right thing, in my languages, and I can open it.** All
three modes, the pinned answer inside the first ten, scoping enforced before
truncation, three languages unconfigured with the lanes connected, and a hit
that opens at the page it came from.

**Goal 5 — all of my library.** A 15k library and a 15k-page PDF as ordinary
input, group libraries searchable and never erasing one another, one's own notes
and annotations in the corpus, and a new item noticed without anyone asking.

Goal 1 binds: R10, R15, R22, R31.

Goal 2 binds: R3, R13, R23.

Goal 3 binds: R1, R4, R6, R17, R18, R19, R32.

Goal 4 binds: R5, R7, R24, R29, R33, R34.

Goal 5 binds: R8, R12, R16, R35.

**The method, ruled with the ladder: tests for the lower rung first, then make
it work.** This is what the ordering is for, and it changes what ticket 0026
does first — the fold, golden, RSS and convergence gates were scoped by
instrument, and they are now taken in rung order, goal 1's assertions before
goal 2's. It also gives the evidence column somewhere to go: a rung whose tests
exist can be red, and red is a claim about the system, which is the state this
repository has never been able to reach.

**Three consequences worth recording.** The MVP frame survives the renumbering:
*works for me* is now the standard for goals 3 through 5 together, and the
levels ruled this evening stand, with the library deciding and the fixture
standing in. R5 gains a rung — it was on no bundle at all, its design answer
having come back negative, and a partition has no room for a requirement that
belongs nowhere; it sits with the finding promises in goal 4, where its honesty
obligation is met or broken. And R23 stops being homeless: refused as a term of
the search bundle this morning and folded into R1's assertion, it is now a
member of goal 2 in its own right, which is where a promise about surviving a
version flip always belonged.

**What the objection was, and why it is overruled rather than quietly dropped.**
The reading this entry replaces held that a conjunction should not be sequenced,
that sub-bundles are promises to a more patient person than the author, and that
naming rungs without ruled rosters was the safer half-step. The author put the
instruction again after hearing it. The substance of the objection is kept where
it belongs — each goal is a conjunction, no band reports partial credit — and
the caution that produced unruled rosters is dropped, because an unruled roster
is exactly the drift this repository has twice paid for.


## Awaiting ratification

- **When the reviewed baseline is bumped, and on what trigger (ticket 0504,
  2026-08-31).** Upstream ships several times a day and the baseline moved two
  releases in one of them, so "bump because upstream shipped" is a cadence this
  repository cannot hold and does not want: a bump obliges a re-read of every
  row on the status page, and `check_baseline` keeps the build red until that
  re-read is done. Not bumping costs nothing today — the page is self-scoping
  and the guard fires only after a bump — which is why the question is what
  makes the bump worth its own price, not when upstream next releases.

  The proposal is three triggers, any one sufficient. **(a) The acceptance
  harness exists** (ticket 0032): once a row's verdict is produced by something
  that runs, re-reading twenty-four of them stops being twenty-four judgements
  and becomes one run. **(b) The page faces outward** — offered upstream,
  linked from an issue, or read by anyone who did not write it — because a
  dated page is honest scaffolding internally and a misleading claim in public.
  **(c) A re-read establishes that a row's `delivered` verdict is wrong rather
  than merely dated.** The third is the one this ticket's own work argues for,
  and the argument cuts against the comfortable reading: the four rows read at
  v1.12.0 (`verification/UPSTREAM-1.12.0-REREAD.md`) found R16 kept where the
  page says `none`, and R12's second clause kept where the page says it fails
  and names a pull request still in flight. The page is not merely stale there;
  it under-reports what upstream delivered, and it names as pending a filing
  that merged. Under-reporting is the safe direction for a specification
  repository, which is why this is a trigger for the author to weigh rather
  than an emergency.

  What ratifying this settles is which ticket carries the bump and when it is
  allowed to run. What it does not settle is R10's transport question (ticket
  0505) or the smoke repair the re-run needs first (ticket 0506); both gate the
  bump's evidence half independently of the trigger.

- **Which of the prose guards come out, and whether thirteen documents is the
  right number (raised 2026-08-31 by the excess-weight ruling, which settled
  the principle and left the instances open).** Three questions the ruling
  implies but does not decide, because each destroys something on the author's
  say-so rather than an agent's. (i) `bench/check_figures.py` is 1 141 lines,
  a third of all guard code; its value is real but proportional to how much
  prose is kept, so it is decided *after* the document count, not before.
  (ii) The chain-dedup, terminology and normative guards exist to manage a
  problem created by having eleven places a fact could live; if that number
  falls, they lose their subject. (iii) `spec/FIELD-REVIEW.md` is 1 974 lines,
  the largest document in the repo, a dated snapshot that is authoritative for
  nothing in the design. Merging or retiring documents is a deletion, and this
  repo deletes rather than archives, so each one wants its own ruling.

- **Reading AGPL source in order to reimplement it is unpriced, and ticket
  0031 is where it lands (session finding, 2026-08-30).**
  `spec/FIELD-REVIEW.md` sets the survey's general route for an idea held by a
  copyleft or unlicensed project — read the design, write the paragraph, build
  it independently — and then names one place that route is *not* enough:
  Zotero core's calibration procedure, "an algorithm with parameters rather
  than an idea", with the instruction that ticket 0031 read
  `Zotero.Embeddings.Calibration` at source before committing to its own.
  Nothing in the chain says what that reading may then produce.

  The asymmetry is real. `zotero/zotero` is AGPL-3.0 and zoteus is MIT, and
  reading an algorithm-with-parameters at source in order to reimplement it is
  a different act from reading a design and describing it: the closer the
  reimplementation tracks the parameters, the less "independently built"
  describes it. This is not a claim that 0031 would infringe — it is the
  observation that the chain currently gives 0031 an instruction and no bound,
  and that the bound is the kind of thing decided before the work rather than
  argued afterwards.

  What this entry does NOT question is reading upstream source to verify a
  factual claim about upstream behaviour. This session did that at length —
  the #6012 checkpoint, and three attributions settled for ticket 0180 — and
  it produces assertions about what upstream does, never code. The two acts
  should be separated by whatever rule is adopted, because conflating them
  would forbid the verification `spec/FIELD-REVIEW.md` and ticket 0181 both
  depend on.

  Options, unranked and for the author: adopt a clean-room split (one reader
  writes the parameter-free description, a second builds from it and never
  reads the source); take the parameters as facts about the problem rather
  than as expression, and record that reasoning; ask upstream for the
  procedure under a permissive grant; or build 0031's calibration from its own
  stated pair-generation protocol and never read theirs, accepting a weaker
  result. Ratifying any of them settles ticket 0031's method; ratifying none
  leaves the instruction standing without one.

- **Files certify their own embedding chain: calibration chunks in every
  file's header, and one chain per file (author, 2026-08-30).** Two proposals
  that are one mechanism. Every vector file opens with a fixed, public set of
  calibration chunks, embedded by the same chain in the same run as the corpus
  behind them; and no file ever mixes chains, so that header speaks for every
  row in the file. Verification becomes local and self-contained — embed the
  same chunks, compare, decide — with no registry to consult and no declared
  metadata to trust.

  What it answers is a defect class this repository has realized three times,
  each one a case where the *declared* identity held while the function
  changed: pooling hardcoded `mean` against four `cls` candidates (ticket
  0421), the device flag dropped by the sweep wrapper (0481), `normalize`
  carried in the registry and applied nowhere (0486). `spec/CONSTRAINTS.md`
  C1's third link derives vectors from "chunks, embedder identity and model",
  and all four of `spec/DESIGN.md` §2.1's stage keys hash *inputs* —
  `text_hash`, and `embed_hash` over the embedded text including its prefix.
  Nothing anywhere measures what the embedder did. A header does.

  Three consequences beyond hygiene. Adopting a foreign index stops being a
  negotiation over provenance and becomes a local measurement, which is the
  mechanism the adopt-by-copy entry is waiting on. Serving through an embedder
  change falls out of the invariant: a new chain is a new file, so the old file
  serves while the new one builds and the cutover is atomic — the shape ZotSeek
  reaches with per-model chunk keying and a coverage table
  (`spec/FIELD-REVIEW.md`; unlicensed, so reimplemented from the description
  and never copied). And X8 becomes a field instrument rather than a lab one,
  since every file then carries vectors its own chain produced.

  **What a header cannot do is make the comparison exact**, and this should not
  be ratified as though it could. X8's own fp32 rows are cross-provider
  compatible without being bit-identical: in
  `bench/results/0482-gpu-corrected/x8-cross-provider-fidelity.json`,
  `multilingual-e5-base` reaches a minimum cosine of 0,999974 at fp32. A hash
  over the header would call that a different chain. The comparison therefore
  stays tolerant — and on the same artifact it should not be cosine alone,
  since `granite-97m-multilingual-r2` at q8 clears the bar while keeping 0,4164
  of its top-30 overlap. Ticket 0485 prices that gap and owns the question; the
  bar itself is `spec/DESIGN.md` §3's.

  Two sub-questions this entry does not settle. **Where the calibration vectors
  live**: physically first is right for a reader, but if they occupy slab rows
  they are addressable as corpus rows and every consumer must remember to
  exclude them, which is the silent wrongness C1 exists to prevent — a manifest
  section is proposed instead of row space. **Which chunks**: they must be
  public, fixed, and reproducible by a stranger, and they must not be drawn
  from the library, because `SECURITY.md` lists vectors as an asset rather than
  assuming they are safe for looking like numbers, and a header derived from
  library text would leak the library into every file handed out. They should
  span the languages X2 showed behave differently, span short to near-budget
  length, and pass through the model's own `input_template`, without which the
  header measures a different function than production does.

  Three costs to weigh before ratifying. A cutover holds two slabs at the real
  geometry, against budgets `spec/DESIGN.md` §2.9 owns. The execution device is
  part of the chain, so under R30 a GPU-built and a CPU-built file cannot be
  merged at the 8-bit rungs, where X8 says most candidates fail. And
  `embed_hash`'s EXISTS guard on deletes becomes per-file rather than global,
  which `spec/DESIGN.md` §2.1 must restate rather than inherit.

  Ratifying this reshapes `spec/DESIGN.md` §2.1's stage keys and §2.2's storage
  section, gives `spec/CONSTRAINTS.md` C1's third link a measured half beside
  its declared one, and supplies the mechanism the adopt-a-foreign-index entry
  is waiting on. Ticket 0497 carries the portable format the invariant implies.

- **The book segmenter works at page boundaries on the PDF side — and the
  open question is where the split runs relative to the extractor (author,
  2026-08-30; a first recording of this entry misread the position as
  "segment = page" and is corrected here — awaiting entries are drafts, the
  append-only rule protects ratified ones).** For books, proceedings, and
  encyclopedias, chapters and articles begin on pages, and the PDF side
  holds that map: measured, 15 of 24 sampled 100-plus-page PDFs (63 %)
  carry a machine-readable outline (`mutool show … outline`), page-anchored.
  The question — split before or after the extractor — resolves under the
  shim ruling into **discover before, cut after**: true before-the-extractor
  splitting means extracting text per chapter ourselves, which contradicts
  the shim (Zotero stays the extractor, and its API has no per-range call);
  but *discovery* before it is only reading structure, not extracting text.
  So the segmenter reads the chapter map from the PDF (outline first, TOC
  parse as fallback), and cuts the *extracted text* at the mapped page
  boundaries, located by form feeds — present in 55 % of caches today,
  raisable by a re-extraction sweep (0480's class). Two consequences favor
  this shape. The outline names chapters past the 100-page cap that
  extraction never delivered, giving honest coverage its denominator —
  "present in the book, absent from the index" — which flat text cannot
  express (ticket 0483's state gains chapter names). And when the
  someday-better extractor arrives, the same map drives true per-chapter
  extraction with no redesign. Online encyclopedias have no pages: there the
  structure signal is markup headings, necessarily text-side; the
  segmenter's interface should take structure signals (PDF outline + form
  feeds | HTML headings | headword rhythm) and cut text, with today's
  heuristic seg/1 as the no-signal fallback. Reference works keep entry
  segmentation under the entry-as-unit-of-answer ruling. Ratifying this
  reshapes ticket 0028's spec and X5's question.

- **Scoping by a stored attribute is affordable, and the author wants years.**
  The entry below reports X4 and concludes the ladder loses its middle rung.
  That conclusion is about the mechanism X4 measured — an arbitrary rowid set
  shipped through `json_each` — and it should not be read as "scoping is dead",
  which is how it first reached the author. A **collection** or a **tag** needs
  that mechanism, because their membership is a set the index does not store. A
  **year** does not: it is an attribute of an item, so it can be a column with an
  index on it and an ordinary predicate the planner pushes into the scan.

  Measured 2026-08-29 on the real 477 512-passage index
  (`bench/results/0025-year-scope/year-vs-json-each.json`), each scope run BOTH
  ways over the same items and the same queries:

  | scope | indexed predicate | `json_each`, same items |
  |---|---|---|
  | one year (2020) | **254,8 ms** median | **11 141,9 ms** median |
  | five years | 181,3 ms median | not run — X4's curve |
  | a decade | 196,1 ms median | not run — X4's curve |

  Ranking the whole corpus with no filter at all costs **207 ms** median in the
  same run. So the predicate is **43x** cheaper than the blob on identical work,
  and its cost against no filter is nil to within this run's noise — a five-year
  scope is *cheaper* than no scope, because the filter removes work rather than
  adding any. Read the comparison within this run only; its baseline is not the
  X4 arm's, which used a different probe set and a different file.

  **The precondition is the finding that comes first.** The shipped index stores
  no date: `items` is `(item_key, title)` and `passages` carries none either. So
  year scoping today is not slow, it is *impossible*, and no latency verdict was
  ever the obstacle. Adding the column and its two indexes over the whole index
  cost **529 ms**, and Zotero's local API already returns `meta.parsedDate`, so
  the build has the value in hand.

  **What this does not license.** It says nothing about collections or tags,
  whose arbitrary sets remain X4's territory, and nothing about a scope so narrow
  that the ranked stream runs out before it fills k — the give-up frequency the
  entry below leaves open. It generalises to stored attributes, item type
  included, and no further.

  Two ways to rule. Record a third ladder rung for stored-attribute filters,
  distinct from the rowid-set rung X4 killed, and let R5's date and item-type
  clauses stand on it; or hold until the give-up frequency is measured, on the
  ground that a filter which is free per query can still empty a result set. The
  upstream half — that `zotero_semantic_search` accepts no filters at all and the
  index carries no date to filter on — is an upstream ask and is not filed.

- **X4 fired, and the ladder loses its middle rung.** DESIGN.md §3 states the
  rule as *"the ladder step sits at the largest measured scope whose
  constrained-MATCH p95 <= 150 ms; if even 1k exceeds it, no constrained step
  ships and the ladder ends at the honest R18 give-up."* The real-corpus arm ran
  2026-08-29 on the 477 512-passage index
  (`bench/results/0025-x4-constrained-match/real-477k.json`), and the smallest
  rung fails by a wide margin: constrained p95 at a 1000-rowid scope is
  **11 969,6 ms**. The rule's own second clause therefore fires. No constrained
  step ships.

  The result is stronger than "too slow", and the difference matters for any
  retry. Ranking the **whole** corpus unconstrained costs **73,6 ms** median,
  where constraining to a thousand rowids costs **585,7 ms** — so scoping via
  `json_each` is not an optimisation that fell short of a budget, it is
  dominated by not scoping at all. The synthetic arm reached the same verdict;
  this is its confirmation on real text with a real vocabulary.

  **What this changes in DESIGN.md §2, which is why it is here and not only in
  the ticket.** The ladder is written there as three rungs — refetch deeper to
  4 096; then, *"for scopes of roughly <= 20k passages"*, a constrained MATCH via
  `json_each`; then the honest give-up. The middle rung is now void, and with it
  the "roughly <= 20k passages" clause and its number, which were placeholders
  for what X4 would measure. The surrounding sentence — *"the actual threshold is
  measured by X4, not trusted"* — is still written in the future tense and now
  reads as a promise already kept. Two rungs remain: refetch deeper, then
  disclose.

  **R5 does not fall with the mechanism, and should not be read as falling.**
  R5's own text already refuses to read "pushed into SQL" as constraining FTS5's
  MATCH, warns that doing so "measures at seconds per query at library scale",
  and puts the obligation on *"the honesty of the result, not on which operator
  enforces it"*. X4 confirms the scouts' correction with a number rather than
  overturning anything. What R5 forbids is post-filtering a top-k that claims
  completeness; a bounded deeper refetch that discloses its residue is legal by
  construction.

  **R18 is promoted by this, and it is the least-evidenced row in the area.**
  With the middle rung gone, the `scope{}` block stops being the last resort and
  becomes the primary answer whenever a narrow scope outruns the deeper refetch.
  R18 stands at delivered `none`, evidence `inferred`, and spec/README's standing
  sentence still says the decision it depends on sits in ticket 0025 — that
  decision is this entry.

  **The open question the verdict creates, and nobody has measured it.** How
  often does rung 1 fail to fill k for a realistic scope — a collection, a tag —
  now that nothing catches it? That frequency is what decides whether R5's
  `partial` is benign or embarrassing, and it is a new experiment rather than a
  retry of this one. Ticket 0025's log names the two candidate mechanisms if a
  third rung is ever wanted (an indexed temp table; post-filtering a ranked
  stream *before* truncation). Note the burden any such retry now carries: the
  mechanism it replaces lost to doing nothing.

  Three ways to rule. Delete the middle rung from §2 and record the ladder as
  two, leaving the give-up frequency unmeasured; or the same, and commission the
  frequency experiment before R5's row is called again; or commission the
  indexed-temp-table experiment first, as a candidate third rung, and hold §2's
  edit until it reports.

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


One reading cycle 2 could not decide on the sheet's text alone (flagged in
DESIGN.md §2.9; put to the author directly — the re-formed train keeps
internal governance out of upstream filings, so it is resolved here, not in any
issue text). The other two are gone: R20's letter against the gate's practice
was answered on 2026-08-29, and the prefix-granularity reading was vetoed on
2026-08-29. Both removal entries are above.
- **The 300 MB budget's scope under N processes.** Ratified against a
  single-server picture; the normal deployment is one zoteus per MCP client,
  ~690 MB whole-machine steady at two clients. Per process or per machine is
  the author's call; both figures stated in DESIGN.md §2.9.
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

- **May an index travel by copy? "Work does not travel" meets the GPU machine.**
  REQUIREMENTS.md's out-of-scope list rules vector export and sync out. The
  author's stated use (2026-08-30) is narrower: embed on the GPU machine,
  retrieve on the CPU one, by one-shot copy, with no live sharing. The
  architecture sits closer to that use than the scope sentence suggests. A
  copied index's signals are foreign on arrival — versions scope by
  `Zotero-Server-ID` (C1), and two machines' local profiles share nothing — but
  its keys are content hashes, so the signal/key split (DESIGN.md §2.1)
  converges a copied index by fetch-and-hash with zero re-embedding: R23's open
  protocol opens it, R1 re-earns the delta. Three conditions gate the path. X8
  (DESIGN.md §3) must clear the compatibility bar, so the embedder key is
  provider-free; the corpus rung must load on the query machine, since a query
  embedded at a different rung than the corpus is the measured cross-rung
  failure ticket 0240 records, and fp16 loads on no CPU provider; and transport
  is one-shot copy, never a shared live file — WAL needs same-host shared
  memory, and §2.5's conductor protocol binds one machine. Two ways to rule,
  after X8 reports: amend the out-of-scope sentence to keep sync out while
  admitting a one-shot adopt-a-foreign-index path, and the design gains that
  path (new origin row, signals marked stale, verify sweep, R1 from there); or
  keep the sentence as ratified and record the copy path as unsupported. The
  ruling waits for X8 — if X8 fails the bar, the question answers itself.

- **The sole-writer conductor and the pure streaming worker (raised 2026-08-31,
  from the author's own three-process sketch reviewed against the ratified
  topology).** The 2026-08-30 ruling gave the pipeline three worker kinds, each
  opening the store and committing its own stage's rows, plus the query servers.
  The author's amendment is that the conductor does the writing, and that it
  also segments: the worker streams an attachment's text in from Zotero in
  bounded windows, the conductor decides the boundaries and writes the slabs,
  entries and passages as they close, and the worker is then handed **ranges** —
  the slab addresses §2.2 already gives every passage — which it embeds and
  streams back as vectors for the conductor to commit. A book therefore crosses
  the pipe once as text and never again; a re-embed after a model change moves
  no text at all. Query embedding stays in-process, per the same amendment, and
  is not reopened here.

  What the change buys, in one sentence each. The vector sidecar and the ledger
  stop being two artifacts with two writers kept in agreement by a generation
  stamp, and become one ordering decision in one process. C3's
  killable-at-any-time bullet becomes structural rather than argued, since a
  worker holding no durable state cannot damage a store it never opens, and one
  of the two mandatory orphan repairs loses its subject. And streaming chunk
  records ahead of vectors keeps the ledger a stage boundary — resumability
  stays at the chunk, not at the document — while delivering the structural
  hint's first justification, keyword availability never waiting on embedding,
  without a third process — under the amendment it is stronger than a streaming
  order, since an item's slabs and passages are committed before any vector for
  it is computed. The two-band frontier becomes a dispatch policy over ranges
  rather than machinery of its own.

  What it costs, and the two questions that decide it. The conductor becomes a
  query-serving process that performs every durable write, so C3's
  foreground-beats-background rule has to move inside it, and nothing has
  measured query latency on a conductor draining a build against R6's budget.
  And a single worker running a multilingual model plus a section batch makes
  the collision between C3's pipeline ceiling and the candidates' measured
  residency concrete: that ceiling was ratified against an English-embedder
  picture and was explicitly left untouched when the server ceiling was re-pinned
  on the 0263 measurements. Either it is re-pinned on the same evidence, or
  chunking keeps its own process and the ceiling covers the smaller of the two.
  Both questions are the author's; neither is an agent's to settle.

  One clause carries the rest and is worth ratifying explicitly: the conductor
  must never materialize a whole document. The local API answers with the text
  inside one JSON object, so the convenient read is the one that puts a 44,9 MB
  attachment into the process that holds the query embedder and answers queries,
  and the arithmetic against C3's per-process ceiling says that does not fit.
  Streaming it is ordinary work, but it is work nothing currently measures, and
  a library of ordinary papers never exposes the omission.

  The full proposal, the requirement-by-requirement review behind it, and its
  five findings are `verification/SOLE-WRITER-0507.md`. The propagation into
  DESIGN.md §2.4/§2.5/§2.9, TERMINOLOGY.md and SECURITY.md is ticket 0507 and
  waits on this ruling.
