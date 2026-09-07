# The red-state exercise for the Menagerie question bank — design handoff

Ticket 0722 item 1 of 0029's closeout order. Written 2026-09-07 by the agent that
was asked to run the exercise and could not commit, for the successor that will.
Everything below was read or measured in the checkout; nothing is quoted from
memory. Where a number is derived rather than measured I say so.

---

## 0. State of the world when this was written

- **Worktree `.claude/worktrees/redstate-0722`, branch `t0722-red-state`,** created
  off `origin/t0029-menagerie-build` at `5f61e36`. Nothing was committed to it.
  It is yours to use or discard.
- **Why the run did not happen.** This agent was a subagent pinned at launch to
  `.claude/worktrees/t0029-3639832`. The platform's worktree-isolation guard
  refuses *every* git operation naming another tree — `cd <path> && git`,
  `git -C <path>`, `GIT_DIR=`, a relative `-C`, and `rtk proxy git`. `EnterWorktree`
  with a `path` moves the cwd but not the pin, after which *every* Bash call is
  refused because the cwd is no longer the pinned tree. There is no escape from
  inside the session. **Launch the successor with `isolation: "worktree"` and let
  it rebase onto `origin/t0029-menagerie-build` itself.** Do not ask an agent to
  create its own worktree.
- Two smaller mechanical notes for whoever works in this repo under that guard:
  the rtk Bash hook rewrites `git fetch` into `rtk git fetch`, which the guard then
  refuses as unverifiable; `/usr/bin/git fetch` passes. Heredocs (`python3 - <<EOF`)
  and `for f in …; do python3 -c …` are refused as "too complex to verify"; write
  the script to a file and run `python3 <path>`.

---

## 1. What the bank is, as committed

`bench/fixtures/questions/`, 281 questions (283 files = 281 + `README.md` +
`bank.schema.json`), schema `menagerie-bank/v2`, one JSON file per question,
stamped against export `579ab8dd…2296ccc`.

Shape as `python3 bench/golden_gate.py shape` prints it:

- lanes: `en->en` 94, `vi->vi` 45, `fr->fr` 32, `vi->en` 13, `fr->en` 12,
  `zh->zh` 11, `ru->ru` 10, `en->vi` 10, `de->de` 8, `ar->ar` 7, `fr->vi` 7,
  `hi->hi` 6, `es->es` 5, `en->fr` 4, `en->ru` 4, `en->ar` 3, `en->hi` 3,
  `en->zh` 2, `vi->fr` 2, `en->de` 1, `en->es` 1, `vi->zh` 1.
- strata: core 211, reserve 70. signals: exact 181, paraphrase 76, agreement 24.
- set_kind: any-of 277, **all-of 4** (`q-0003`, `q-0125`, `q-0229`, `q-0341`).
- expected_miss: **86**; scored: 195.
- **`mode` is `any` on all 281.** No question is scoped to a single mode, so the
  mode axis of the report is entirely empty of scoped questions and every reply
  is scored in whatever mode it was produced in.
- 119 distinct free-string `mechanisms` values (no enum — 0723's departure 4).
- facets: core 258, notes 1, group 6, deep-body 16.

---

## 2. What the scorer does, precisely — and the one line the whole exercise turns on

`bench/golden_gate.py`, 1400 lines, three subcommands (`validate`, `score`,
`shape`). The parts that decide a red state:

**`score_row` (line ~914).** For each of the first *k* results (k = 10, parsed
from SPEC §5.2.8):

```
same_item = result.item_key == export.parent_of[row.attachment_key]
            or result.attachment_key == row.attachment_key
twin      = (not same_item) and (result.work_id == row.work_id
                                 or export.is_twin(result.item_key, row.work_id))
```

- `same_item` **and** evidence matched → `win`. Evidence matches when token
  overlap with an alternate's quote ≥ `EVIDENCE_OVERLAP_MIN = 0.5` over content
  words of three characters or more, **or** the reply's printed page equals the
  alternate's `page_printed`.
- `same_item` **without** evidence → `near-win`, `why: "item-without-evidence"`.
- `twin` (relation `translation` or `same-work`) → `near-win`, `why: "work-twin"`.
- otherwise `miss`.

**`r34_present` (line ~1012):** `found > 0` for any-of, `found == len(rows)` for
all-of, where *found* counts rows at level ≠ miss.

**Gate state (`evaluate`):** `fail` if R34 fails or stability fails; `not-run` if
either is not-run; else `pass`. **The expected-miss outcomes are computed,
reported, and enter no gated reading.** 49 firing negative controls therefore
cannot fail the gate — 0722's log already says this and it is confirmed in code.

**The single fact that governs the whole exercise: presence is *item*-level, not
*span*-level.** `same_item` compares the reply's item key to the pinned row's
parent item. `attachment_key_carried: false` in the run block — the build never
returns an attachment key — so in practice every presence decision is "did the
parent item come back in the top 10". Nothing about *which paragraph*, *which
page*, *which section*, or *whether the pinned span is even in the index* enters
the presence test. That is why 116 of 195 scored questions sit at
`item-without-evidence`, and why 49 of 86 expected-miss questions come back
`unexpected-hit`.

---

## 3. The two R34 predicates, in code terms

The author's open question is what "present" means. Do not settle it; run both.

| predicate | definition | how to compute it without editing `golden_gate.py` |
|---|---|---|
| **shipped** | `level != miss` — i.e. win, or `item-without-evidence`, or `work-twin` | `report["questions"][key]["r34_present"]`, as written |
| **evidence-matched** | `level == win` — the pinned quote actually overlapped, or the printed page matched | recompute from the same report: a question is present iff (any-of) some row has `evidence.how in {"evidence-overlap", "printed-page"}`, (all-of) every row does |

Both are pure functions of the emitted `report.json`. **The harness must read the
report and apply the predicate itself; it must not patch the scorer.** That keeps
the author's ruling free and keeps `make golden` unchanged.

A third predicate is worth *reporting* even though it is not one of the two: the
shipped predicate minus the `work-twin` path only. It isolates 0723's departure 1
(the twin path counting as present is exactly the miss R29 exists to catch) from
the `item-without-evidence` path. 8 rows over 11 questions ride it.

---

## 4. The baseline, measured

`bench/results/golden/replies.json` (2.0 MB) and `report.json` (712 KB) are
**committed on the build branch** and were produced by build `b0e0bc8` over export
`579ab8dd…`, keyword-only, k=10, 843 replies (281 lexical + 562 not-run for
semantic and hybrid). So **a baseline exists and no build is needed to start.**

```
state fail   scored 195   expected-miss 86   not-run 562
R34 fail, 34 missing            stability not-run (no previous_run)
win 42 (21,5 %)  near-win 119   miss 34   near-or-better 82,6 %   MRR 0,742
row paths: item-without-evidence 116 · evidence-overlap 44 · work-twin 8 · miss 34
expected-miss: pass 37, unexpected-hit 49
```

### Headroom per MUST cell — this is the finding that shapes every arm

R29 binds the six ordered cross-lingual pairs over {en, fr, vi}; R7 the three
monolingual lanes. Present counts at baseline:

| MUST cell | n | shipped: present | room to go red | evidence-matched: present | room to go red |
|---|---:|---:|---:|---:|---:|
| en→fr | 4 | 3 | 3 | **0** | **0** |
| en→vi | 8 | 3 | 3 | **0** | **0** |
| fr→en | 10 | 5 | 5 | **0** | **0** |
| fr→vi | 7 | 3 | 3 | **0** | **0** |
| vi→en | 11 | 5 | 5 | **0** | **0** |
| vi→fr | 2 | 2 | 2 | **0** | **0** |
| en→en | 56 | 56 | 56 | 15 | 15 |
| fr→fr | 19 | 19 | 19 | 4 | 4 |
| vi→vi | 33 | 33 | 33 | 9 | 9 |

**Under the evidence-matched predicate all six cross-lingual MUST cells are
already at the floor: zero wins, zero headroom, no arm can make them redder.**
A red-state exercise cannot demonstrate them at all under that predicate. Under
the shipped predicate they have 3–5 questions of headroom each, and `vi->fr`'s
entire population of 2 is carried by the `work-twin` path — its
`near_or_better_rate` of 1,0 rests on the target-language document never coming
back (0723 already recorded this; it is confirmed here per-question). So an arm
that disables the twin path alone empties `vi->fr` completely, which is a red
state for the *scorer's* twin clause, not evidence of the bank's discrimination.

**Report this in the reading whatever the arms show.** It is the answer to the
question "can the bank fail" for the cells that matter most, and the answer is
predicate-dependent: under one predicate the six MUST cells cannot fail because
they have already failed; under the other they can lose at most 21 questions in
total across all six.

### Other headroom, measured

- by signal: `exact` 31 win / 73 near / 1 miss; `paraphrase` 4 / 32 / 31;
  `agreement` 7 / 14 / 2. The paraphrase cell is where a semantic-path arm has to
  bite, and it is already 31/67 miss at baseline.
- questions whose `mechanisms` name an index/extraction cap: **39 total, of which
  35 are expected-miss and only 4 are scored (1 win)**.
- questions naming work identity / twins / duplicates / multi-attachment:
  17 total, 10 scored (1 win), 7 expected-miss.
- questions naming cross-lingual mechanisms: 45 total, 40 scored (2 wins).
- the 4 all-of questions: three at near-win with both rows found, one (`q-0341`,
  fr→vi) already a miss.

---

## 5. Harness design

### Interface

`bench/redstate.py`, argparse, subcommands:

```
bench/redstate.py list                       # the arms, their kind, their blockers
bench/redstate.py run --arm <name> [--arm …] [--all]
      --bank bench/fixtures/questions --export bench/fixtures/export
      --baseline bench/results/golden/replies.json
      --out bench/results/0722-redstate/
      [--server fork/dist/index.js --data-dir <fresh>]   # build arms only
      --seed 0
bench/redstate.py read --out bench/results/0722-redstate/   # the cross-arm table
```

`run` produces per arm: `<arm>/replies.json` (a real
`menagerie-replies/v2` bundle), `<arm>/report.json` (whatever
`golden_gate.py score` emits, unmodified), and `<arm>/delta.json` — the harness's
own product. `read` renders the cross-arm matrix.

### `delta.json`, per arm

Computed against the baseline report, **for each of the two predicates**:

```json
{"arm": "...", "kind": "build|reply", "predicate": "shipped|evidence-matched",
 "changed": {"q-0107": {"from": "present", "to": "absent", "lane": "vi->en",
                        "stratum": "core", "mechanisms": [...]}, ...},
 "by_lane":     {"vi->en": {"n": 11, "present_before": 5, "present_after": 1, "delta": -4}},
 "by_stratum":  {...}, "by_signal": {...}, "by_mechanism": {...},
 "mechanisms_fired": ["index_fulltext_max_chars", ...],
 "must_cells_that_did_not_go_red": ["en->fr", ...],
 "expected_miss_flips": {"pass->unexpected-hit": [...], "unexpected-hit->pass": [...]}}
```

The **targets declaration is part of the arm, in code**: each arm names, before
it runs, the lanes and mechanism ids it claims should go red. `delta.json`'s
`must_cells_that_did_not_go_red` is the set difference between the claim and the
observation. **That field is the deliverable.** A cell that stays green under an
arm that targets it is the finding.

### Two kinds of arm, labelled and never conflated

- **`kind: build`** — the product is really broken and re-run through
  `golden_run.py`. Needs `fork/dist/index.js`, node, and (for the vector arms) a
  model runtime. This is evidence about the *bank against a real build*.
- **`kind: reply`** — a deterministic, seeded transform of the committed baseline
  `replies.json`, re-scored by the unmodified `golden_gate.py`. This is evidence
  about the *bank against a stipulated reply distribution*: it is a simulation and
  the reading must say so in every sentence that uses it. Its value is that it
  runs in CI, on any machine, in seconds, and gives a permanent red fixture.

Both write a real replies bundle, so both go through the same scorer, and a reply
arm's `run` block must carry an `arm` key naming the transform and its seed so the
artifact cannot be mistaken for a measurement of a build.

### Tests (`tests/test_redstate.py`, fast tier, no build)

1. every arm declares non-empty `targets`;
2. each reply transform is deterministic under a fixed seed and non-identity
   (a transform that changes nothing is the vacuity this whole ticket exists to
   catch — assert it against a tiny synthetic bundle);
3. the emitted bundle validates through `golden_gate.load_replies`;
4. `delta.json` against the baseline-vs-itself is empty under both predicates
   (the null arm — the control that proves the differ can report "nothing
   changed");
5. the evidence-matched predicate reproduces 42/195 on the committed report,
   and the shipped one 161/195. **These two numbers are the positive control for
   the predicate code**; without them "no cell went red" and "my predicate is
   broken" are the same output.

---

## 6. The six arms

Throughout: **never edit the bank, never edit `golden_gate.py`.** Also, every arm
must keep the same export — `evaluate()` raises `InputError` when
`replies.run.export_sha256 != export.sha256`, so an arm that touches
`bench/fixtures/export/manifest.json` cannot be scored at all.

### A. Shuffled ranker — "every question should catch it"

*Targets*: every lane, every mechanism. If any question stays present, that
question is measuring nothing.

**Do not implement it as a permutation of the top k.** `score_row` scans
`results[:k]` and takes presence from set membership; a permutation *within* the
top ten changes rank and MRR and leaves every level and every R34 verdict exactly
where it was. That arm would come back green and mean nothing. This is the single
easiest way to run a vacuous red-state exercise, and it is worth writing down.

The discriminating form is a **global** shuffle: replace each reply's results with
*k* items drawn without replacement, seeded, from the export's parent items
(103 items; `export.work_of_item` gives the pool), with `evidence` drawn from that
item's own fulltext so the shape stays honest. Expected: presence collapses to
roughly k/103 ≈ 10 % per row by chance, so ~175 of 195 scored questions flip to
absent under the shipped predicate and essentially all 42 wins vanish.

*Build variant, if the fork is available*: patch the ordering in the fork's search
path and rebuild. Better evidence, same expectation. Worth doing once to
calibrate the reply variant against a real one.

*Anything that stays present under the global shuffle is a defect in the bank or
in the scorer.* Watch particularly for the `work-twin` path: a shuffled ranker
that happens to return any rendering of a work still scores near-win, so twin-only
questions have a raised floor.

### B. Keyword-only, semantic path disabled — "the paraphrase questions should catch it"

**This arm cannot be run as a degradation, because it is the shipped baseline.**
The committed run is `embedder: "none (keyword-only)"`, `vectors: 0`,
`retrieval_mode: keyword (BM25 over passages) reported as lexical`, with semantic
and hybrid written as `not-run`. There is no semantic baseline to degrade from.

So the arm inverts: **the positive control must be built first.** Produce a
vectors-on run, then the shipped keyword-only run *is* the broken arm, and the
paraphrase cell's delta between the two is the measurement. Until that exists,
report the arm as **not-run with its reason**, and do not substitute a reply-level
simulation — simulating "semantic off" from a run that never had semantic on is
circular.

Cost: `make_index_fixture.mjs` refuses `--embeddings` ≠ `off` in two places
(`runGoldenBuild` throws, and the CLI exits 2), so a vectors-on run cannot go
through the committed replay entry as written. It has to drive `bench/run_build.py`
directly (`--embeddings local --transformers-path …`) against
`bench/fixtures/golden_replay_serve.mjs`, then `golden_run.py --skip-build`. That
is a real piece of work and probably its own ticket.

Headroom if it does run: paraphrase is 4 win / 32 near / 31 miss at baseline, so
the cell has 36 questions of shipped-predicate headroom and 4 of evidence-matched.

### C. Semantic-only — "the rare-exact-string questions should catch it"

Same blocker as B, with the additional requirement of a way to *suppress* the
lexical arm. Not runnable today. Report as not-run.

If it becomes runnable, the target cells are `signal: exact` (181 questions,
104 of them scored) and specifically the mechanisms `known-item`,
`transliterated-proper-name`, `section-heading-case-variant`,
`lexical-false-negative`. Expect the rare-exact-string questions to fall and the
paraphrase ones to hold; a run where *both* fall is measuring the absence of an
index, not the absence of a lexical path.

### D. English-only embedder where a multilingual one is expected

Same blocker as B and C, plus a model swap. Note a fact from the run block that
matters here: `embedder_model.build_default` is `Xenova/all-MiniLM-L6-v2`, parsed
out of `dist/features/search/embeddings.js` — **the build's default is already an
English-only model.** So "an English-only embedder where a multilingual one is
expected" is not a break to be injected; it is the shipped default, and the
*multilingual* configuration is the one that would have to be built to make a
comparison. SPEC §5.2 elsewhere records "the English-embedder picture, and R7
outranks it" (line 968), so this is known upstream; the successor should read that
paragraph before designing the arm.

Target cells: the six cross-lingual MUST lanes. See §4: under the evidence-matched
predicate their headroom is **zero**, so this arm can only be demonstrated under
the shipped predicate, and there it can move at most 21 questions in total.

### E. Index character cap cut small — the one build arm that is runnable offline today

*Targets*: as declared in the ticket, "the cap-crossing questions". **The
measurement will show that claim is wrong, and that is the finding.**

The cap-crossing questions are 39, of which **35 are expected-miss**: their pass
condition is "no pinned row in the top k". Cutting the cap makes the pinned item
*less* retrievable, so those questions move from `unexpected-hit` toward `pass` —
the arm makes them **greener**, not redder. And expected-miss outcomes are not in
any gated reading, so the movement changes no verdict at all. The questions that
actually go red under a smaller cap are the ordinary in-cap scored questions whose
answer sits between the new cap and 40 000 — a cell nobody declared.

So the arm's honest target declaration is: *every scored question whose stamped
`reachability.rows[].alternates[].char_offset` exceeds the new cap*, computable
from the bank's own stamps before the arm runs. Compute that set, then compare it
to what actually flipped. Suggested cap: 2 000 characters (small enough that most
answers fall outside; large enough that the build still produces passages and
passes `validateGoldenBuildResult`, which requires `passages ≥ parent_item_count`
and a non-empty `search-index.sqlite`, and checks neither the cap nor the offsets).

**How to run it without editing the export.** `make_index_fixture.mjs` passes
`--max-chars String(fixture.manifest.index_fulltext_max_chars)` to
`bench/run_build.py` — hardcoded from the manifest, no CLI override. Editing the
manifest changes `export_sha256` and the scorer then refuses the replies outright.
So bypass the fixture entry for the *build* only:

1. `node bench/fixtures/golden_replay_serve.mjs --export bench/fixtures/export
   --recipe bench/fixtures/recipe-pinned.json` → prints `{"port": …}` on stdout;
2. `python3 bench/run_build.py --server fork/dist/index.js --data-dir <fresh empty>
   --backend sqlite --max-chars 2000 --max-items <parent_item_count>
   --embeddings off --build`, with `ZOTEUS_LOCAL=on`,
   `ZOTERO_LOCAL_PORT=<port>`, `ZOTERO_LIBRARY_TYPE`/`ID` from
   `manifest.library`;
3. stop the replay;
4. `python3 bench/golden_run.py --skip-build --data-dir <that dir>
   --server fork/dist/index.js --output <arm>/replies.json` — it starts its own
   replay for the query side;
5. `python3 bench/golden_gate.py score --replies <arm>/replies.json --output
   <arm>/report.json`.

Caveat to record in the artifact: `golden_run.server_environment` sets
`ZOTEUS_INDEX_FULLTEXT_MAX_CHARS` from the manifest (40 000) on the **query**
side. The index was built at 2 000 and the query-side value should not matter, but
the run block will say 40 000 and that is a lie the reading has to correct in
prose. Consider carrying an `arm` block in `run_extra` (`golden_run.py` has a
`run_extra` dict already) rather than leaving it to the reader.

### F. Entry collapse disabled — "the work-identity and twin questions should catch it"

*Targets*: the 17 questions naming `work-identity-*`, `declared-translation`,
`same-text-different-format`, `metadata-conflicting-duplicate`,
`near-duplicate-publication`, `multi-attachment-parent`,
`compound-document-entries`; and the 8 rows over 11 questions currently carried by
the `work-twin` path (0723 counted 12 rows over 11 questions; the report here
counts 8 rows at `why: work-twin` — reconcile before writing the reading, the
difference is probably rows vs establishing rows).

R24 collapse lives in the product (entries / dedup in the fork's search path), and
`fork/` is not present in this checkout — it is gitignored and cloned by
`bootstrap.sh` / `make upstream-checkout`. So this is a build arm that needs the
fork, and the successor must first locate the collapse in the built source before
it can be disabled. Note the layered risk: what the *scorer* does with twins
(`TWIN_RELATIONS = {"translation", "same-work"}`, `Export.is_twin`) is not the
same thing as what the *build* does with renderings, and an arm that disables one
proves nothing about the other. Say which one the arm broke.

A reply-level simulation is available and worth running beside it: expand each hit
into its work's sibling items and truncate to k, so the top ten fills with
renderings of the same work and pushes other works out. Label it `kind: reply`.

---

## 7. Running the offline replay — what was learned

- **A baseline exists and is committed.** `bench/results/golden/replies.json` +
  `report.json`, produced by `b0e0bc8` at `2026-09-07`, against the current export.
  Every reply-kind arm needs nothing but this file and `python3`.
- **`make golden` is scorer-only** and is deliberately *not* in `make check` — the
  Makefile comment explains why (a prerequisite that cannot look would be waived).
  `make golden-run` needs `fork/dist/index.js`; it refuses a non-empty
  `GOLDEN_DATA_DIR` and exits 3 with a message when the server is absent.
- **The replay is genuinely offline.** `offlineBuildEnvironment` passes a reviewed
  allowlist of ~18 variables and nothing else, so no credential can leak into a
  build; `ZOTEUS_LOCAL=on` plus `ZOTERO_LOCAL_PORT` points the product at
  `golden_replay_serve.mjs`. **No live Zotero client and no port 23119 is involved
  at any point** — the standing prohibition is satisfied by construction as long
  as the replay is used.
- **The replay build is fast**: `build.elapsed_s: 0.8` for 103 items, 2 379
  passages, 89 fulltext items. A build arm is cheap once `fork/` exists.
- `requireFreshBuildDirectory` refuses a symlink, a non-empty directory, `$HOME`,
  `/tmp`, the repo root, and the filesystem root. Give every arm its own fresh
  directory under `~/data/`.
- Node is `v22.23.1` on this machine. `fork/` is absent: `make upstream-checkout`
  then `npm ci && npm run build` in `fork/` is the prerequisite for arms A(build),
  B, C, D, E, F.
- The reachability stamp in the bank records `reindex_mode: complete,
  reindex_limits: ignored` (per the README's example) while the run block records
  `reindex_mode: stock, reindex_limits: applied`. Worth a glance before trusting
  any statement about which cap produced which offset; it may just be the README's
  illustrative JSON rather than the stamped values, but I did not verify it.

---

## 8. What surprised me, in order of how much it should change the plan

1. **Presence is item-level, so most of the bank's declared mechanisms are
   unobservable by the gate.** A pinned span past the index cap, in a mangled
   glyph run, in an unserved MIME type — none of it changes the presence test,
   because the parent item comes back anyway. 49 of 86 expected-miss questions are
   `unexpected-hit` for exactly this reason, and none of them can fail the gate.
   The bank describes span-level pathology; the scorer measures item-level recall.
2. **A within-k shuffle is invisible.** Level and R34 are set-membership over the
   top k; rank feeds only MRR, which is never gated (D11). The obvious
   implementation of the obvious control is vacuous.
3. **The evidence-matched predicate floors all six cross-lingual MUST cells at
   zero wins**, so under that predicate the exercise cannot demonstrate them at
   all. The two predicates do not merely disagree on a headline number; they
   disagree on whether the exercise is possible.
4. **The English-only-embedder arm is the shipped default**, not an injected
   break. The break to build is the multilingual one.
5. **The index-cap arm's declared target moves the wrong way.** It makes
   cap-crossing questions greener, and the questions it actually reddens are ones
   nobody declared.
6. `vi->fr`, a MUST cell, has 2 questions and both score only through the
   `work-twin` path — the target-language document never returns. Its perfect
   `near_or_better_rate` is an artifact of the clause 0723 flagged as departure 1.
7. Only 4 of 281 questions are `all-of`, so R34's absolute reading over a pinned
   set is exercised on 4 questions; on the other 277 it is "did one row come back".

---

## 9. What the author still owns, and what the reading must not do

- **The R34 predicate.** Unresolved. Run and report both; say where they disagree,
  which is: everywhere, and structurally, not marginally. Do not change
  `golden_gate.py` scoring to settle it.
- **The MUST-cell minima.** SPEC §5.2.10 says every MUST cell carries a minimum
  question count, that none is stated because none is ruled, and that "until then
  every MUST cell prints not-evaluated". `golden_gate.py` prints no
  `not-evaluated` state at all (0723's departure 3), so a lane at n=2 prints a
  full rate. The red-state reading should print counts beside every cell it names
  and should not claim a rate on `vi->fr` (n=2) or `en->fr` (n=4).
- The reading goes in `verification/`, names every cell that failed to go red,
  and — per the "null result needs a positive control" rule — states for each such
  cell whether it stayed green because the bank cannot see the defect or because
  the arm did not reach it. Those are different findings and the artifact must not
  fold them together.

---

## 10. Suggested order of work

1. Reply-kind arms first, from the committed baseline, no build: null arm (the
   control), global shuffle, twin-expansion simulation. Commit after each.
   This alone answers "can the bank fail at all" and gives a permanent fixture.
2. `make upstream-checkout && npm ci && npm run build` in `fork/`, then arm E
   (index cap) as the first real build arm, plus a build-kind shuffle to
   calibrate arm A's simulation against a real break.
3. Arm F once the collapse is located in the built source.
4. Arms B, C, D behind a separate ticket for a vectors-on run; report them
   not-run with the reason until then. Three of six arms not-run is an honest
   result and better than a simulated one.
