# How this repository conducts itself upstream

Process rules live here. The specification in [`SPEC.md`](SPEC.md) says what
the system promises, what the world imposes, and how the design answers; none of
that tells you how many pull requests we may have open at once, or what we do
when one goes unanswered for a month. Those are different questions, with a
different audience and a different lifetime, and the IETF separates them for the
same reason: someone implementing the system has no use for the PR cap, and
someone trying to understand the upstream relationship should not have to read
the architecture to find it.

There is a second reason, particular to this repository. It is public, and the
upstream maintainer reads it. Keeping strategy in one file is what makes
"never put our internal governance into upstream text" checkable at all: one
place to read before anything goes out. The mechanical guard that once
enforced the separation was retired on its record of zero catches
(DECISIONS.md, 2026-09-01); the rule binds exactly as before, kept by
the reader.

## Where the rulings themselves live

This document owns process rules **going forward**. It does not own the record.
Every bound below was ratified in [`DECISIONS.md`](DECISIONS.md) and
stays there, unmoved, cited by date. That ledger is append-only, and its
append-only-ness is the whole of its evidential value: a record you may rewrite
is a document, not a record. Relocating ratified entries into this file was
considered and rejected on exactly that ground (DECISIONS.md 2026-08-29).

The transitional cost is accepted and named: process rulings are readable in two
places for a while, and the pointer, not a move, is what resolves them.

**Live counts are not here either.** A bound is stable; how much of it is spent
this week is not. [`SYNC.md`](SYNC.md) records what is in flight, what merged,
and what remains of the budget. Restating a tally here would put a decaying
number in a stable document, which is this repository's most expensive recurring
defect. Ask this file what the rule is; ask SYNC.md where we stand against it.

## The bounds

**Volume: at most two upstream pull requests in flight.** Ratified 2026-08-26.
Cadence is demand-triggered — the next pair waits for the current pair to
resolve, and silence upstream is queueing, not an invitation to add more.

A **third slot was granted once**, on 2026-08-29, for the cosine-fusion change.
Read that grant precisely: it is a grant, not an amendment, and the ledger says
so in terms. The cap stands as ratified. The exception's ground was that a
simplification carrying its own equivalence proof spends the maintainer's
attention differently from a design ask, and it is precedent for that shape of
change and nothing wider.

**The contained-PR budget is six, ratified 2026-08-26** beyond the merged #19
and #20. What remains live is SYNC.md's to report, not this file's.

**Form follows the measured asymmetry.** A contained defect carrying a failing
test goes as a pull request. Anything design-sized goes as an issue he builds
himself. This is a rule *we* adopted; the asymmetry it answers is a fact about
the terrain, measured in both directions and recounted in SYNC.md as it
moves, and it is owned by [`SPEC.md` §4](SPEC.md). Gates are
repo-side, in this repo's Makefile, and never travel upstream as pull requests.

**A three-week sunset.** Any upstream item unaddressed after three weeks, or
overtaken by his own implementation, is closed from our side with one
appreciative line and no relitigation. Ratified 2026-08-26; it has fired before
(DECISIONS.md 2026-08-27).

**The acceptance harness is a one-time artifact transfer**, not a tracking duty.
We hand over an executable specification he can run against whatever he builds,
and we do not thereafter own its maintenance.

**The fork is archived once the train resolves.** Ratified 2026-08-26 among the
commitment bounds. The end state is not a maintained parallel implementation.

## The increment train

*(Re-formed 2026-08-26 by the political and implementation reviews and
ratified in DECISIONS.md. Both those reviews and the original fifteen-step
train are gone, lost with the pre-restart history (DECISIONS.md, 2026-08-31):
what survived the re-forming is this section. Moved here from `SPEC.md`
2026-09-01 — process planning, not a promise the system keeps or a fact the
world imposes on it.)*

Upstream code root: `/home/user/oscardvs/zoteus/src/features/search/`.
SYNC.md's measured asymmetry governs the form each item takes: a contained
defect with a failing test goes as a **[PR]** (merged twice), and anything
design-sized goes as an **[issue]** he builds himself (the precedent is
upstream issue #10; two for two).
**[X]** means measure first, and gates are repo-side, in this repo's
Makefile, never PRs.

This section carries the train's *shape* only. The terms it runs under are
`## The bounds` above, which points at the entries that ratified them; each
item's scope, evidence, and live state live in its ticket. The tickets are
authoritative for content, this list for ordering.

Two orders coexist. The ladder on `README.md` governs the order repo-side
assertions are built; this train governs the order items go upstream. On
collision the ladder wins for tests and the train for filings — ticket 0488, a
rung-1 member filed at item 8, is the documented case (DECISIONS.md
2026-08-31).

1. **The head, resolved** — PR #19 (accent fold) and #20 (corruption path)
   merged 2026-08-27 (`4f61b2a`, `6e4637b`); the stopwords follow-up
   (ticket 0014) is now the head.
2. **The contained-PR items** (the budget is `## The bounds`' above, the live
   remainder SYNC.md's) — schema read-before-write (0015), the wipe guard
   (0016; `busy_timeout` closed under the sunset, overtaken by v1.7.1 —
   DECISIONS.md 2026-08-27), cacheDir and key-to-header (0017).
3. **The reserve, demand-triggered** — terminal states (0019), own words
   (0022).
4. **Issues I-1..I-3** (0024) — the fulltext-delta finding, the measurements
   as an extension of his own #10 citation, the 40k cap behind the #6012
   checkpoint; I-4 is folded into scoped issue A, not filed.
5. **The harness offer, the first design conversation** (0032) — the
   acceptance spec he can run against whatever he builds; a one-time
   transfer.
6. **Three #10-shaped scoped issues, after the train and the offer** — A:
   ledger/freshness/counters (0033); B: entries and the segmenter (0034); C:
   multi-process on one data dir (0035). The contract survives even if he
   reimplements the machinery in his own idiom, which is where `SPEC.md` C2
   says the durable value lives.
7. **Experiments before their dependents** (0025 carries the substrate map;
   the rules live in `SPEC.md` §5.3): X1 before the sidecar work, X4 before
   any ladder constant, X5 (seg/1 built first, 0028) before issue B, X6 with
   I-1, X7 before the tick cadence is documented, X3a feeding the rss-gate
   fixture, and X3b traveling with issue B.
8. **The curated embedder registry** (tracker 0488) — singleton extraction;
   authoritative fields and parity; curated entries plus entry-id selection;
   local automatic compatibility validation; optional content-free
   attestations; then the separate gate that decides what ships — R7 and R29
   conformance first and untraded, the golden and resource gates choosing
   among the entries that pass it (ticket 0495; the ruling on why the swap
   happens at all is DECISIONS.md 2026-08-31).
   The autonomous-service experiment (0491) reuses the interface seam
   but does not block this sequence. One upstream design issue carries staged
   acceptance tests; it is not a prepared PR series.
9. **The commitment bounds** — stated above, ratified in DECISIONS.md's
   re-form entry; the fork's end state is **archived** once the train
   resolves.

## The disclosure rule

Nothing about this repository's internal governance, and nothing about our
reading of the maintainer's behaviour, enters text destined upstream — pull
request bodies, issue text, review replies. The repository is public and he
reads it, so the rule is not about secrecy but about not conducting a
relationship in front of the person it concerns.

Two things follow, and the second is the one that has actually gone wrong.
A pull request body is written for its reader, so it carries the change, the
measurement, and the reproduction, and stops there. And a body pasted from
somewhere else carries whatever that somewhere else contained: SYNC.md records a
filed body that arrived with a session trailer attached, in a public repository.
Read what you are about to send, as sent.

Where a bound above needs to be mentioned in the specification chain, cite this
file on the line that mentions it. That is what the guard looks for, and it is
also what a reader needs — a pointer they have to hunt for is a pointer that
does not resolve.

## The courtesy filing

One norm runs the other direction — toward the maintainer rather than about
him (ratified 2026-09-01, DECISIONS.md). A repo-side record that
documents a defect-shaped seam in upstream's shipped code at file-line
precision is accompanied by a short upstream filing of its own — standalone,
never folded into an unrelated filing — or carries an explicit line stating
why it is deliberately unfiled. The ground is the disclosure rule's own: this
repository is public and he reads it, so the seam is disclosed either way;
the norm makes it a note addressed to him rather than a row about him.
