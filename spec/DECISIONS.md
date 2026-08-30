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

## Awaiting ratification

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
  is waiting on. Ticket 0487 carries the portable format the invariant implies.

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
