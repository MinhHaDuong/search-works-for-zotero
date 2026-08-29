# How this repository conducts itself upstream

Process rules live here. The specification chain in [`spec/`](spec/) says what
the system promises, what the world imposes, and how the design answers; none of
that tells you how many pull requests we may have open at once, or what we do
when one goes unanswered for a month. Those are different questions, with a
different audience and a different lifetime, and the IETF separates them for the
same reason: someone implementing the system has no use for the PR cap, and
someone trying to understand the upstream relationship should not have to read
the architecture to find it.

There is a second reason, particular to this repository. It is public, and the
upstream maintainer reads it. Keeping strategy in one file is what turns
"never put our internal governance into upstream text" from a habit into a
check — [`bench/check_governance.py`](bench/check_governance.py), which fails the
build when a bound below is stated in a specification document without pointing
back here.

## Where the rulings themselves live

This document owns process rules **going forward**. It does not own the record.
Every bound below was ratified in [`spec/DECISIONS.md`](spec/DECISIONS.md) and
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
the terrain, measured two-for-two in each direction, and it is owned by
[`spec/CONSTRAINTS.md`](spec/CONSTRAINTS.md) and evidenced in SYNC.md. Gates are
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
