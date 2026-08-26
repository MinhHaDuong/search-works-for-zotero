# Political review — cycle 2, "The Instrumented Ledger"

*Reviewed 2026-08-26 against DESIGN.md, SYNC.md, REQUIREMENTS.md, CONSTRAINTS.md,
DECISIONS.md, tickets 0014–0027, and the live upstream tree. The stakeholder dimension
only; technical merit is other reviews' business. One live fact first, because it
postdates every document in the tree: upstream moved today — v1.7.1 released 2026-08-26,
`80f8aa0` (fix #18) and `2cde6a7` on `main` — and neither `refs/pull/19/head` (`4c4c2ef`)
nor `refs/pull/20/head` (`dd1605a`) is an ancestor of `origin/main`. He was in the repo
today, shipped a release, and did not touch either open PR. That is the batch pattern
behaving exactly as SYNC.md predicts, and it is also the tree moving under two open PRs
within twenty-four hours of their opening.*

## Finding 1 — the train's volume exceeds the maintainer's demonstrated appetite by roughly a factor of seven. (Question a. Highest consequence.)

The record SYNC.md establishes: the maintainer has merged exactly two external PRs in the
project's visible history, both from this project, both in one four-day demand-triggered
batch, and each cost him real work — he found a load-bearing defect in each, wrote his own
follow-up commits (`58943ef`, `8dead91`), and wrote the tests the units lacked. That is
his measured review budget: two contained PRs per batch, with substantial per-PR effort,
when demand triggers a sweep.

The train asks for: #19 and #20 (open), the stopwords follow-up, PR-1 through PR-12, four
issues, and an RFC — on the order of fifteen PRs and five issues from one contributor, on
a repository whose entire issue tracker holds about twenty numbers. Nothing in the record
supports the belief that he will review thirteen more PRs, at any cadence. What the record
does support is a different failure: a wall of open PRs from one account reads as pressure;
each PR that sits goes stale against a tree that shipped a release the day after they
opened; and the reviewer who found the `NaN`-parse defect in #12 will not rubber-stamp a
queue — every PR that does get attention costs him the same real effort #11 and #12 did.
His time and goodwill are the plan's scarcest resource, and the plan as written spends
them like they are not.

**Recommendation — re-sequence and cut.** Hard cap of two PRs in flight (the measured
batch size), demand-triggered cadence: do not open the next pair until the current pair is
resolved, and treat his silence as queueing, not as a signal to add more. The contained-PR
budget for the whole campaign should be about six beyond #19/#20: the stopwords follow-up,
PR-1 (schema read-before-write), the busy_timeout half of PR-2 (see Finding 4), PR-3
(wipe guard), PR-4 (cache dir, verified first — see Finding 4), PR-5 (key to header).
PR-7 and PR-10 go to a reserve list, opened only if a batch lands warmly or user demand
surfaces upstream (the #13/#14 pattern: demand from a third user is what triggers his
sweeps — an issue from someone else asking for notes-in-search is worth more than our PR).
PR-6, PR-8, PR-9, PR-11, and PR-12 leave the PR train entirely — Finding 2 says where
they go.

## Finding 2 — the RFC's ending is right, but the mega-RFC and the machinery-PR back half are the two forms the measured asymmetry says will fail. (Questions d and b.)

First, the bet itself. DESIGN.md §4 accepts "the contract survives even if he reimplements
the machinery in his own idiom" as a good ending, and it is — for the author. Minh's
stated interests are a searchable library, preserved credit, and no open-ended maintenance
burden. If the maintainer rebuilds the ledger under the contract: the library becomes
searchable in shipped software (the goal), the maintenance lands on the person who wants
to maintain it (the author's explicit non-goal discharged), and the credit precedent is
already established — authorship preserved on both merges, co-author credit on #17, and
`docs/semantic-search.md` citing issue #10, which is ours. The fork's code "equity" serves
nobody once the goal is the author's library working; SYNC.md already drew this conclusion
about the prototype ("it was the argument, not the shipping code") and the conclusion
generalizes. Verdict on the bet: keep.

Second, the vehicle. One RFC covering six subsystems — signals-vs-keys, entries plus
segmenter, lib-keyed store, conductor protocol, dual-embed, counters-plus-harness — is not
the input that produced #10's success. #10 was one problem, crisply bounded, with
measurements and no code he had to accept. A six-subsystem RFC invites the two bad
outcomes at once: it sits (and ticket 0027 blocks the fork-vs-upstream decision on his
response, so the plan stalls on silence), or he cherry-picks silently and the record never
shows what was declined. Meanwhile PR-6, PR-8, PR-11, PR-12 are the Instrumented Ledger
arriving in PR-sized installments — per-attachment data model, user-facing verbs, a query
compiler, a ranking experiment. The asymmetry is two-for-two: design-sized input, whatever
its wrapper, gets reimplemented, and a design delivered as a PR sequence predictably gets
recognized as a design mid-train, stranding the unmerged cars.

**Recommendation — re-form.** Split the RFC into (i) the acceptance harness offered
first and standing alone — the convergence harness, fold sweep, and golden set are the
single most maintainer-shaped artifact this project owns, because the one consistent fact
about his reviews is that he writes tests: an executable spec he can run against whatever
he builds respects his style and survives reimplementation by design — and (ii) two or
three #10-shaped scoped issues, each with a documented behavior, a reproduction, a
measurement, and no code to accept: one for the ledger/freshness/counters complex (absorbs
PR-8's pause and PR-9's serve-stale as motivating defects), one for entries/segmenter
(X5-gated, and #6012-gated per Finding 5), one for multi-process (absorbs the per-page
commit question). PR-11/PR-12's query semantics go with the first or wait for demand.
Strike the two internal ratification questions (R26 granularity, 300 MB scoping) from the
upstream RFC ticket — those are questions for Minh, recorded in DECISIONS.md, and putting
this repo's internal governance into his issue tracker confuses the audience; resolve them
before filing, not inside the filing.

## Finding 3 — three instrumental sentences about the maintainer are on the public record where he will read them; the fix is three one-line edits. (Question c.)

The distinction that matters: an honest engineering record about his code is an asset, and
this repo mostly has the tone right. The defect catalogue in DESIGN.md's preamble is
cited to file and line, stated flatly, and balanced by equally flat self-criticism ("the
fork's own shipped 92.7%-changed-forever defect", "the artifact that measured 2,084.9 MiB
when nobody was looking"). SYNC.md's account of his reviews — "what his review caught in
our code, which is the part worth reading twice" — is praise a maintainer can only be
glad to find. The §2.2 self-correction that names its own earlier line a "jab" and
retracts half of it reads as integrity. CONSTRAINTS.md C2 modeling his merge behavior as
an environmental fact is legitimate planning, stated respectfully. None of that should be
sanded down.

What is different in kind is strategy-about-the-person stated where the person can read
it, and there are exactly three instances worth the edit:

1. **DESIGN.md §4 item 14 and ticket 0027**: "Opened after the PR train establishes
   credibility." Read by its subject, this recasts every preceding PR as a move in a
   campaign to manage him — including the two he already reviewed in good faith.
   Reword both to: *"Opened after the PR train, so the conversation starts from merged,
   reviewed pieces rather than from a specification."* Same sequencing, zero manipulation
   frame.
2. **Ticket 0017**: "Cheapest custody wins; they also build merge history before the RFC
   (0027)." Same problem, blunter. Cut the second clause: *"Cheapest custody wins."* The
   cross-reference to 0027 can stand alone.
3. **DESIGN.md §5 Risk 3 heading**: "the maintainer reimplements the core underneath us,
   faster than the RFC converses." "Underneath us" frames his work on his own project as
   something done *to* this one. Reword the heading to *"Risk 3 — upstream ships its own
   core before the RFC conversation completes"* and keep the body, whose closing clause
   ("the contract, counters, and harness are ours whoever writes the machinery") is
   already the gracious version.

Keep-as-is, with reasons: SYNC.md's "a design-sized problem as an issue gets him to build
it himself" is instrumental phrasing but is immediately followed by "That is not a
complaint: #10 is his call to make, and his backend is a good one" — the disclaimer
carries it, and rewriting measured history starts to look like the sanding this review was
told to avoid. SYNC.md §2's issue-vs-PR calculus ("the risk he closes it for his own
version is real and is the price") is candid process record on a decision that was
subsequently skipped anyway; its premise ("he is faster at his own codebase than a review
round trip") is a compliment. The panel/cycle2 raw record ("down payment of credibility"
in design-derivation.md) is clearly labeled deliberation-in-the-raw; archives read as
archives, and editing them retroactively is worse than leaving them.

## Finding 4 — four form and framing corrections inside the surviving train. (Question b.)

- **PR-2 (ticket 0016) — split it.** The busy_timeout half is a contained defect with an
  empirical repro (two handles, timeout 0, immediate throw): the exact shape merged twice.
  The per-page-commit half changes his transaction discipline, on which he has a written
  comment the design itself concedes is right for the update path. Bundled, the judgment
  call sinks the defect fix. Ship busy_timeout alone; the build-path commit cadence goes
  into the multi-process scoped issue (Finding 2), where he can adopt it in his own idiom.
- **I-2 (measurement corrections) — form right, framing decides everything.** SYNC.md
  already made the two key moves: demoting it from a docs PR ("editing his prose with
  numbers measured on other code is not something to do quietly") and disclosing that the
  SQLite figures are the fork's, not his backend's. Hold that line in the issue body: lead
  with the offer ("numbers from a 7,541-item library, both charged honestly"), not the
  correction ("your build column misleads"), and note his docs already cite #10 — this is
  extending a citation he chose to make, and the body should read that way. The one number
  that must not be softened is the 477,512-passage wall; it is the record.
- **I-4 (legacy JSON retirement) — defer and fold.** The form call (issue, because it
  reverses a documented decision) is correct, but this is the lowest-value ask per unit of
  goodwill in the whole plan: a stale file on disk, wrapped in a request to reverse a
  documented choice. Its one real edge — the legacy JSON retains deleted items' text, an
  R15 custody point — is exactly the frame under which it belongs as a paragraph in the
  custody-adjacent scoped issue, not a standalone filing. Cut it from the four-issue batch.
- **PR-3 (wipe guard) and PR-9 (serve-stale) — acknowledge the documented decision in the
  body, or demote.** PR-3 contradicts a deliberate doc-comment ("keyed by the context …
  never by the routed library id", build.ts:185–188); it survives as a PR only because
  data loss is a defect under any reading — the body must quote his comment and frame the
  guard as *enforcing* the documented single-library assumption rather than reversing it.
  PR-9 reverses `dropStaleVectors`, which he wrote on purpose; if it ships as a PR the
  body must present the failing test as a regression-in-effect (semantic coverage zeroed
  by an upgrade) and name the alternative reading; otherwise it folds into the serve-stale
  section of the scoped issue. Per Finding 1, PR-9 is already off the main train.

## Finding 5 — platform risk sorts the train into front-load and checkpoint piles. (Question e.)

If zotero#6012 lands with structured extraction and locally served embeddings, the wasted
motion is: the segmenter and X5 wholesale (structured sections make heuristic segmentation
a fallback at best), PR-6's per-attachment plumbing (the SDT pack is the successor to
concatenation, and C1 already names it the adapter path), I-3's streaming ask (moot under
a random-access container), most of PR-10 (#6012 embeds notes and annotations natively),
and the RFC's embedding-side machinery — X1, the int8 sidecar, dual-embed. Platform-proof
regardless: #19 and #20 (zoteus's own query and durability paths), PR-1 through PR-5
(schema, concurrency floor, custody — all about zoteus's file, whatever fills it), PR-7
and PR-8 (status honesty and pause are zoteus UX under any backend), I-1 (a live defect
today), I-2 (a record, timeless), and the entire gate estate in 0026 — an acceptance
harness binds behavior whichever machinery, including Zotero's, sits underneath, which is
one more argument for leading with it (Finding 2).

**Recommendation.** Front-load the platform-proof set — it is nearly identical to Finding
1's surviving budget, which is convenient rather than coincidental. Put an explicit #6012
checkpoint in tickets 0025 and 0027: before X5 is run and before the entries/segmenter
section of any upstream filing is drafted, check #6012's state; C2 already notes its
saved-search serialization is the first crack, so the tripwire costs one look and saves
the single largest block of speculative work in the plan.

## Finding 6 — the plan commits the author to more than it says; write the caps down. (Question f.)

What the plan implies for Minh, uncapped: review-response duty on up to fifteen PRs (both
merged PRs drew maintainer follow-ups needing response; every open PR needs rebasing as
his tree moves — it moved today); the owner-pastes bottleneck (SYNC: "Body edit pending
(owner pastes)") putting Minh's hands on every upstream interaction, so the real cadence
is Minh's cadence, not the plan's; a permanent CI estate (fold, golden, RSS, convergence,
soak) that Risk 5 already admits decays; open-ended exit criteria ("responses recorded
here as they land"); and, if the harness-as-acceptance-spec offer is taken, an implied
maintenance duty on a test suite for someone else's project.

**Recommendation — add a short "commitment bounds" block to DESIGN.md §4 or ticket
0014:** (i) two PRs in flight, ever; (ii) a sunset rule — any upstream item unaddressed
after three weeks, or overtaken by his own implementation, is closed from our side with
one appreciative line and no relitigation (SYNC's "silence is not rejection" cuts both
ways: our closure is not a protest); (iii) the harness is a one-time artifact transfer —
he vendors it or it stays here, and this repo does not promise to track his tree with it;
(iv) name the fork's end state now — archived once the train resolves — so "no open-ended
maintenance" is written where a future reader, including the maintainer, can see it was
the plan and not a lapse.

## The verdicts in one place

(a) Not realistic; cap at two in flight, six contained PRs total beyond #19/#20, cut
PR-6/8/9/11/12 from the PR train, reserve PR-7/10 for demand. (b) Split PR-2; reframe
I-2 as an offer; defer-and-fold I-4; keep I-1, I-3 as issues (correct per the asymmetry);
PR-3/PR-9 must acknowledge the documented decisions they touch. (c) Three one-line edits
(the two "credibility" sentences, the 0017 clause, the Risk 3 heading); everything else —
defect catalogue, praise, self-corrections, C2's behavioral model — stays, because the
honest record is this project's best asset upstream. (d) The ending is right and serves
the author; replace the mega-RFC with the harness-led offer plus two or three #10-shaped
issues; move the internal ratification questions out of the upstream text. (e) Front-load
the platform-proof set; #6012 checkpoint before X5 and the entries filing. (f) Write the
commitment caps and the fork's end state into the plan.

The single cheapest high-value fix: the three tone edits in Finding 3 — three lines,
touching nothing technical, removing the only wording in the public record that converts
a careful, respectful campaign into one that reads, to its most important reader, as
management of him rather than work offered to him.
