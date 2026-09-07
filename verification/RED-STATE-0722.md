# The bank's red-state exercise — reading (ticket 0722, item 1 of 0029's closeout order)

Two hundred green questions and two hundred vacuous ones are the same artifact. The
instrument is not accepted until each MUST cell has been shown capable of going red against
a deliberately broken build (0029 log, closeout order ruled 2026-09-06). This is that
reading.

**Verdict in one line: four of the nine MUST cells go red; five cannot, and the reason is
not the arms.** Under the official score of the ruling of 2026-09-07, none of the nine can
go red at all, because no hit in the run carries a page.

Harness: `bench/redstate.py` (`list` / `run` / `read`). Artifacts:
`bench/results/0722-redstate/`, one directory per arm, plus `matrix.txt`. Tests:
`tests/test_redstate.py`, fast tier.

## Provenance of every number below

| | |
|---|---|
| Measured | 2026-09-07, on **doudou**, in a worktree of `search-works-for-zotero` |
| Baseline replies | `bench/results/golden/replies.json` — build `b0e0bc8`, export `579ab8dd…2296ccc`, 843 replies, 1 928 hits, keyword-only (`embedder: none`) |
| Scorer | `bench/golden_gate.py` at this branch's HEAD, unpatched, driven by `make golden` |
| Bank | `bench/fixtures/questions`, 281 questions, 195 scored, 86 negative controls |

Nothing here is carried over from the parked branch's own figures. The parked lane reported
an accommodating score of 75/195; this reading measures 51/195 on the same replies bundle.
The whole of that difference is the scorer, and §1 accounts for it question by question.

The **reply** arms were regenerated from the committed baseline on this machine and came out
byte-identical to the committed bundles, which is the transforms' determinism check. The two
**build** arms with committed bundles (`control-build`, `index-cap`) were **re-scored, not
re-run**: their replies are the parked lane's measurement of a real patched build, and only
the scoring below is mine.

`make golden` was re-run here and rewrote `bench/results/golden/report.json` **byte for
byte** — the committed report and this machine's are the same file — so the baseline every
arm is differenced against is reproducible rather than inherited.

## 1. One predicate, one home — and what the second copy cost

`bench/redstate.py` used to carry its own implementation of the ruled R34 predicate: a
`RuledScore` class with its own page index, its own snippet locator and its own intersection
test. It was written in the window between the ruling of 2026-09-07 and PR #430, which moved
the predicate into `bench/golden_gate.py`. Its own docstring said so — *"`golden_gate.py`
still implements the predicate the ruling superseded"* — and that sentence stopped being
true the night PR #430 merged.

Both implementations were run here on the same replies bundle and the same export:

| | official | accommodating |
|---|---|---|
| `golden_gate.py` (the gate) | 0 / 195 | **51 / 195** |
| `redstate.py`'s private copy | 0 / 195 | **75 / 195** |

The gate's satisfied set is a **strict subset** of the copy's: 24 questions the copy counted
and the gate does not, and **zero** the other way. The 24 attribute cleanly:

- **22 — the character-span substitution.** Where an attachment's extraction carries no form
  feed, the copy fell back to intersecting *character spans*. The gate refuses outright:
  *"the extraction wrote no page break for this attachment: no page can be derived."* This is
  judgement call 2 in §5 below, and 22 of 195 questions ride on it.
- **2 — a different snippet locator.** The copy trimmed a needle back to a 30-character
  prefix and took the first match; the gate takes the longest fragment between ellipses and
  disambiguates against the reachability stamp's own offset. A shorter needle matches in more
  places, and the two land on different spans.
- **0 — the work half.** The copy admitted any item mapped to the row's `work_id`; the gate
  admits only the row's own parent item or its own attachment. On this bundle that difference
  fires on nothing (0 hits, measured), so it was latent. It would fire on a corpus holding two
  items for one work.

`bench/redstate.py` now implements no scoring. It reads `readings.r34.official`,
`readings.r34.accommodating`, `readings.r34.official.page_reporting` and each question's own
`r34` block out of the gate's report, reshapes them for the differ, and tallies the gate's own
refusal reasons. `test_the_harness_implements_no_scoring_of_its_own` is the guard against the
copy coming back; run against the pre-rewrite file it goes red on five of its six needles, and
against this one it is green.

## 2. The arms

Nine arms declared, four run, five not.

| arm | letter | kind | official | accommodating | ladder wins | negative controls |
|---|---|---|---|---|---|---|
| `null-reply` | control | reply | 0 → 0 | 51 → 51 | 42 → 42 | no flip |
| `control-build` | control | build | 0 → 0 | 51 → 51 | 42 → 42 | no flip |
| `global-shuffle` | A | build | **not run — needs a built `fork/dist`** | | | |
| `global-shuffle-sim` | A | reply | 0 → 0 | **51 → 0** | 42 → 0 | 45 flip `unexpected-hit → pass` |
| `semantic-off` | B | build | **not run — declared: the break IS the shipped baseline** | | | |
| `lexical-off` | C | build | **not run — declared: blocked on B's prerequisite** | | | |
| `english-embedder` | D | build | **not run — declared: the break is the shipped default** | | | |
| `index-cap` | E | build | 0 → 0 | **51 → 14** | 42 → 17 | 4 each way, net 0 |
| `collapse-off` | F | build | **not run — needs a built `fork/dist`** | | | |
| `collapse-off-sim` | F | reply | 0 → 0 | 51 → **52** | 42 → 41 | no flip |

A `sim` arm is a seeded transform of the committed replies bundle, re-scored by the same
scorer. It is evidence about a **stipulated reply distribution**, not about a build, and every
sentence using it has to say so. Its value is that it runs in seconds anywhere and is a
permanent red fixture.

Both controls behave: the identity transform moves nothing, and the rebuilt-unmodified build
reproduces the committed baseline exactly. A differ that cannot say "nothing changed" cannot
say anything else either.

### `collapse-off-sim` went the wrong way

One question, `q-0167/lexical` (vi→en, `cross-lingual-anchor` + `compound-book-section`),
moved from absent to present: with entry collapse off, the top k fills with several passages
of one item and one of them happens to land on the target's page. Net +1 on a score a
red-state arm is supposed to push down, and 41 rather than 42 ladder wins. Arm F's declared
targets are the nine MUST lanes; it reddens none of them. Whether the *build* arm behaves like
its simulation is exactly what a built `fork/dist` would settle, and this run cannot.

### `global-shuffle-sim` reddens R34 and *greens* the negative controls

Forty-five controls flip `unexpected-hit → pass`. That is not a bonus: shuffling the results
away from the real items stops the controls firing, and the controls **gate**
(`golden_gate.evaluate` reads them alongside R34's official score and stability). So an arm
can move the gate's three readings in opposite directions at once, and a red-state claim that
quotes only one of them is incomplete. Both are recorded in each arm's `delta.json`.

## 3. The deliverable: which MUST cells went red

Accommodating score, which is the only one of the two with any headroom at all.

| lane | n | present at baseline | reddened by |
|---|---|---|---|
| en→en | 56 | 29 | `global-shuffle-sim` 29→0, `index-cap` 29→8 |
| fr→fr | 19 | 10 | `global-shuffle-sim` 10→0, `index-cap` 10→0 |
| vi→vi | 33 | 5 | `global-shuffle-sim` 5→0, `index-cap` 5→3 |
| vi→en | 11 | 1 | `global-shuffle-sim` 1→0, `index-cap` 1→0 |
| en→fr | 4 | **0** | nothing — and nothing can |
| en→vi | 8 | **0** | nothing — and nothing can |
| fr→en | 10 | **0** | nothing — and nothing can |
| fr→vi | 7 | **0** | nothing — and nothing can |
| vi→fr | 2 | **0** | nothing — and nothing can |

Two lanes, en→fr (n=4) and vi→fr (n=2), sit under the `THIN_CELL` floor of 5 and print a
count with no rate, per SPEC §5.2.10's not-evaluated clause, whose minimum is unruled.

**Read the two halves of that table apart.** A cell that goes red is evidence the bank can
fail. A cell holding zero present at baseline is *at the floor already*: no arm can make it
redder, and reporting it as "an arm that failed to reach it" would be false. The differ
distinguishes the two — `no-headroom` versus `not-reached` — and every artifact carries the
distinction.

So: **the four MUST cells that have any headroom all go red.** The instrument fails when the
product is broken, in the cells where it can. The five that do not are a statement about the
build, not about the bank.

Under the **official** score every one of the nine reads zero at baseline, so no cell can go
red under it. That is ticket 0734's finding restated as a red-state verdict, and §4 gives the
positive control that says so.

## 4. The nulls, and the controls that make them findings

Three zeros are reported here. A zero and a measurement that could not be taken are different
findings, so each names the control that would have fired.

**"No hit carries a page" — 0 of 1 928.** Positive control: three replies were rewritten to
carry the right work and a page inside the target's printed folio range, and the doctored
bundle was driven back through `golden_gate.evaluate`. The official score counted all three.
A second, discriminating control planted a page 500 folios outside the target: the pages were
still *reported* (3 of 3) and the score refused all three with the reason *"the reported page
does not intersect the target's page range."* So the reading can come out either way, and the
zero is the engine's silence. (`test_the_official_score_counts_a_reply_that_does_carry_the_page`
and `…_refuses_a_page_far_outside_the_target`.)

**"Five cross-lingual MUST cells cannot go red."** Positive control: the four cells that do
have headroom all went red under two independent arms. A differ that could not redden anything
would have shown nine no-shows, not four reddenings and five floors.

**"The work-half difference fires on nothing."** Positive control: the count that would have
been non-zero was taken directly — hits within k that carry the row's own `work_id` but are
not the row's own item. It is 0. The *twin* count over the same replies is 18, so the probe
can find a non-same-item hit when one exists; it simply found no same-work one.

**One control could not run at all.** `test_build_patches_still_match_the_fork_source` is
**skipped** on this machine: it checks that each build arm's exact-string patch still matches
one place in `fork/src`, and `fork/` is a separate, git-ignored checkout absent from this
worktree. So the three build arms' patches are unverified here — not verified-and-clean.

## 5. Two judgement calls, re-examined and left for the author

Both were flagged by the parked lane for re-examination. Neither is decided here.

### (a) A translation twin does not count as the right work

**Reading: I agree with the ruling as `golden_gate.py` now implements it, and the case is
live rather than hypothetical.**

The gate scores a twin `near-win` on the ladder and refuses it under both R34 readings; R34
admits only the row's own parent item or its own attachment. That follows SPEC §5.2.10 —
returning the other-language rendering *in place of* the answer paragraph is precisely the
miss R29 exists to catch — and it matches the author's ruling of 2026-09-06 that the
other-language twin returned in place of the answer paragraph is a **near-win**, not a win.
The ladder says near-win, R34 says not satisfied; the two answer different questions and the
ruling did not merge them.

Measured weight, on the committed run: **18 hits** are a declared twin of a primary row's
work, carrying the best row of **7 of the 195 scored questions**. The export declares twin
relations over 16 works. So this is not a rule with no cases — it moves 3.6 % of the scored
bank, and getting it wrong would silently promote a cross-lingual miss to a pass.

**For the author:** confirm that R34's official reading excludes a twin outright, while the
ladder keeps it at near-win. Nothing in this pass changes it either way.

### (b) A pageless attachment intersecting on character spans

**Reading: the parked lane's substitution is a defensible reading of §5.2.10 and it is not
what the gate implements, so it should stay out until it is ruled.**

The numbers, measured on this bank:

| | |
|---|---|
| Primary rows in scored questions | 202 |
| Rows whose attachment carries no form feed | **99** — 95 HTML, 3 other, 1 PDF |
| Distinct attachments among them | 50 of 81 |
| Scored questions touching at least one | 96 of 195 |
| Rows the gate actually *refused* for pagelessness | **67** |

The 99 and the 67 are both correct and answer different questions. A row can fail before the
page question is ever asked — 41 rows because no result within k returned the row's work, 11
because the returned evidence is not located in the export — so only 150 rows reach the page
test, and 67 of those are refused for having no page structure.

SPEC §5.2.10 does say a file with no pages "locates by character number instead". The parked
lane read that as licensing a character-span intersection under the accommodating score, which
is what produced its 75. The gate refuses, and the difference is 22 of the 195 scored
questions.

The argument for the gate's stricter reading: the accommodating score's whole justification is
that it derives *a page* from the extraction's own page breaks, so both sides are read in one
coordinate system. A character span is a different quantity, and substituting it makes the
score mean two things at once — which is precisely the confusion the ruling separated the two
scores to avoid. The argument against: 99 of 202 rows have no page structure and 95 of those
are HTML, so under the strict reading roughly half the bank is permanently unreachable by the
score that is supposed to give development a signal.

**For the author:** rule whether §5.2.10's "locates by character number instead" extends the
accommodating reading to character-span intersection. If it does, `golden_gate.py` gains it —
not `redstate.py`, and not as a second implementation. If it does not, the accommodating score
is capped by the corpus's format mix and should say so where it is reported.

## 6. What was not run, and why

| arm | why |
|---|---|
| A `global-shuffle` (build) | Needs a built `fork/dist`. `fork/` is a separate, git-ignored checkout that exists only in the primary working copy and is absent from this worktree; building it was out of scope for this pass. Its reply-level simulation ran and is reported above — as a simulation. |
| F `collapse-off` (build) | Same. Its simulation ran and reddened nothing. |
| B `semantic-off` | Declared unrunnable: the break **is** the shipped baseline. The committed run is `embedder: none (keyword-only)`, 0 vectors, with semantic and hybrid written `not-run`. There is no semantic baseline to degrade from, so the positive control has to be built first. |
| C `lexical-off` | Declared unrunnable: blocked on B's prerequisite, plus a way to suppress the lexical arm. |
| D `english-embedder` | Declared unrunnable: the English-only embedder **is** the default (`Xenova/all-MiniLM-L6-v2`, read out of the build's own source). The configuration that would have to be built is the multilingual one, which needs B's vectors-on run. |

Every one of these writes a `not-run.json` carrying `blocked_on` — `build` for a machine
fact, `declared` for a finding about the product — so the matrix cannot show a green row for
an arm nothing measured.

## 7. Recorded, not decided

- **`make golden` exits non-zero by design** and is deliberately not part of `make check`. It
  read `fail` before this pass and reads `fail` after it, from the same three readings:
  official R34 0/195, stability `not-run`, 49 of 86 negative controls firing. Nothing here
  tried to change that.
- **The official score cannot be reddened by any arm** while no hit carries a page. Item 6 of
  0029's closeout order — the golden gate consuming the bank in `make check` — meets a gate
  whose official reading is pinned at zero for a reason that is not the bank's.
- **A new question for the author, recorded and not decided:** should a red-state arm be
  required to move the gate's *three* readings coherently, or is reddening R34 enough? Arm A's
  simulation reddens R34 to zero while flipping 45 negative controls from firing to passing.
  Both are recorded per arm; nothing in SPEC says which combination counts as a red state.
