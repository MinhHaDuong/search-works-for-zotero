# A build-triggered perturbation for R22 — does zoteus's pause actually hold?

Ticket 0643, the direct sequel to 0642 and the second half of tracker 0613's gap C. Where 0642
asked "does the real, durable counter implementation work end to end" (yes) and "does landing it
alone move R22 off `not-run`" (no — `EDIT_ONE_ITEM` is refused on an R15 ground unrelated to
counters), this ticket asks the question the author's ruling actually required before the
staged upstream PR (`verification/UPSTREAM-PR-WORK-COUNTERS-0642.md`) can be considered for
sending: **run the check it exists to unblock, and report what it says — not what a green test
suite implies.**

**This is still an ungraded diagnostic**, same status as `bench/results/0642-work-counters/`:
the patch under test is a local branch of `MinhHaDuong/zoteus` (`work-counters-0642`, pushed to
the author's own fork, not upstream). Nothing in `README.md`'s graded ladder moves because of
this run.

## The result, plainly

**Both R22 clauses now reach a real, decided verdict — FAIL, not `not-run`.**

```
R22-pause-stops-background-work          FAIL
R22-pause-holds-across-restart           FAIL
```

This is the validation the author's ruling (tickets/0642, 2026-09-04T07:49Z) asked for: a real
local run, with a real positive control, deciding both clauses rather than leaving them
undecided. The counters landed by 0642 were necessary — without them, `_the_change_creates_work`
dies at `durability.work_counters(control) is None` before either clause is even reached — and,
combined with this ticket's new perturbation, they are now sufficient to reach a verdict. That
verdict is red, and the reason is a genuine reading of R22, not a harness artifact — see
"Why FAIL, and why that is not a false red" below.

## What ran

1. **Re-verified design against live source** (Action 1): both `upstream/main` (tip `7de4a2f`,
   unmoved since 0642/0613's last reading this session) and the `work-counters-0642` branch
   specifically (`4b97536`, one commit ahead of `7de4a2f`), built fresh
   (`git clone --branch work-counters-0642 ... && npm ci && npm run build`).
   `sqlite-index.ts`'s `SCHEMA_VERSION` is 3 with a `work_counters` table, confirming the branch
   used is the one this ticket needed to build FROM.

2. **Built a real, incompletely-embedded fixture** (Action 2): a real build against this
   operator's resident Zotero library (7,546 items, cloud transport — no desktop Zotero on this
   host), `action:"build" limit:400 own_words:false fulltext:false`, `action:"stop"` called
   deliberately mid-embed (after embedding was observed underway, ~15s into it). Confirmed by a
   direct, read-only sqlite query (mirroring the adapter's own `_index()`/`_stamp()` precedent):
   359 passages, 352 with a vector, **7 without** — `passagesWithoutVectors > 0`, the fixture's
   whole point. The `checkpoint` meta row records `crawlOffset:300` of `itemsTotal:400`, so the
   crawl itself was also genuinely interrupted, not only the embed pass. The embed pass ran long
   enough (~35s total for 461 passages, measured separately) that a 15s `stop` window is a real
   mid-flight interruption, not a race the embed pass would have won anyway.

3. **Added `RESUME_EMBEDDING`** to `durability.PERTURBATIONS` and to
   `BACKGROUND_WORK_PERTURBATIONS` (Action 3) — a new, target-neutral constant naming "a
   background build/embed job continues from its own checkpoint," implemented in
   `zoteus.py::perturb()` as `action:"build"` against the seeded fixture, bounded to the
   checkpoint's own `maxItems` (read back directly off the index file — an unbounded call
   measurably balloons into a full, own-words-and-fulltext crawl of the real library, see
   "What went wrong first" below). `check_pause_stops_background_work`,
   `check_pause_holds_across_restart` and their shared `_the_change_creates_work` needed no
   restructuring, as the ticket predicted — only a generic candidate-selection helper
   (`durability.perturb_background_work`) replacing the hardcoded `EDIT_ONE_ITEM` literal at the
   three call sites, trying `EDIT_ONE_ITEM` first (so every target this layer already graded is
   unaffected) and falling back to `RESUME_EMBEDDING`.

4. **Ran both R22 checks for real** (Action 4), `bench/acceptance/run.py --adapter zoteus
   --posture account`, seeded with the fixture from step 2. `--posture account` composed
   correctly (ticket 0637's fix holds); the run needed one further fix beyond the perturbation
   itself — see below.

## What went wrong first, and had to be fixed before either clause could decide anything

Two real defects surfaced only by actually running the check, not by reading the design — both
now fixed, in this ticket's own diff, and covered by the new tests in
`tests/test_acceptance_goal1_control.py`.

**(a) An unbounded resume balloons past the fixture's own scope.** `action:"build"` does NOT
inherit `limit`/`own_words`/`fulltext` from the checkpoint when a caller omits them — they are
recomputed fresh from the new call's own arguments against the server's configured defaults
(`index-tool.ts`'s handler). A first `_resume_embedding()` that called `action:"build"` bare
resumed straight past the fixture's intended 400-item, no-own-words scope into a full,
own-words-and-fulltext crawl of the entire 7,546-item library — a real cost and a correctness
risk, since a job that size does not settle inside the harness's patience
(`durability.SETTLE_DEADLINE_S`, 300s). Fixed by reading the checkpoint's own `maxItems` back
off the index file directly (the same read-only technique `_stamp()` already uses) and
resupplying it, along with `own_words:false, fulltext:false` matching this ticket's own fixture
convention.

**(b) `durability.settle()`'s default poll rate is faster than this target's real commit
cadence.** `settle()` declares two consecutive equal reads "stationary" — a real target's build
persists (and bumps its work counters, in the same transaction) at most every 10 real seconds
while actively building, never per-passage (`persistEveryMs`, `index-manager.ts`). Polling at
the harness's 1-second default reads two counters from inside the SAME unflushed window and
calls a job that is very much still running "settled," at an unmoved counter — measured directly
against the real fixture: the first genuine counter movement after triggering
`RESUME_EMBEDDING` did not appear until ~18-20 real seconds in. `Zoteus` now declares
`settle_poll_s = 15.0`, the adapter-declared knob `settle()`'s own docstring already provides
for exactly this ("a fixture whose ledger is updated synchronously would otherwise pay a real
target's polling cost for nothing" — the reverse trap, a real target polled too fast, is the one
this ticket found). With both (a) and (b) fixed, the positive control demonstrably moves the
counter (`work.embed.build.done` +109 on a never-stopped instance) before either clause's graded
result is trusted, and both clauses reach a real verdict rather than a false "created no work"
`not-run`.

## Why FAIL, and why that is not a false red

Read literally, R22-pause-stops-background-work's clause is "there is one obvious way to stop
all background work, and after it is used a change that would create work creates none." The
graded run: `pause()` (→ `action:"stop"`) is called, the target genuinely goes idle
(`state:"idle"`, `itemsFetched:0`, nothing building) — then `perturb(target, "resume-embedding")`
is called, the identical candidate the positive control just demonstrated creates real work with
("the same change", per `_the_change_creates_work`'s own requirement) — and it DOES create work:
`work.embed.build.done` advances by 109. Explicitly asking the target to build again, right
after telling it to stop, works.

Is that a fair test, or an artifact of a perturbation shaped differently from `EDIT_ONE_ITEM`?
It is fair, and it answers a question the adapter's own docstring already flagged as open rather
than settled. The ratified interface (cited in `_the_change_creates_work`'s own docstring) frames
pause and resume as "the two transitions of one durable background-work control" — the implicit
model is a control that, once paused, refuses or queues further work until `resume()` is
explicitly called. zoteus offers `pause` (mapped onto `stop`, a one-shot cancel of whatever is
*currently* running) but declares `resume` `UnsupportedVerb` — nothing maps onto it, on the
adapter's own principled ground (the only verb that could is `build`, which is also the full
rebuild and the repair). `zoteus.py`'s docstring already named the tension this measurement now
confirms rather than merely argues: *"Either the two verbs are independently declarable, or a
target missing one of them has no such control at all and both should be absent."* This run is
the direct answer: zoteus's `stop` cancels an in-flight job, genuinely and durably (the
checkpoint survives, nothing auto-resumes on its own initiative — `R22-pause-holds-across-restart`'s
own `resume_never_called: true` field confirms the restart clause never asked it to), but it does
not gate a subsequent EXPLICIT request the way a true pause/resume pair would. That is a real
property of zoteus today, not a harness defect — the same six-review-round machinery
(independence guard, restart-window timing, guarded settle) that graded `EDIT_ONE_ITEM`-based
targets correctly is what produced this FAIL, unmodified.

## Does this validate the upstream counters PR per the author's ruling?

**Yes, as validation of what the ruling asked for — not as a green light to send it.** The
ruling (tickets/0642, 2026-09-04T07:49Z) drew the bar at "run the check it exists to unblock
before proposing to send it," specifically because a green test suite proves a patch correct,
not that it solves the problem it was built for. That check has now run, for real, with a real
positive control, against the patched build — and it reached a decided verdict rather than
staying `not-run`. The counters are doing exactly the job 0642 built them for: making R22
*decidable*. That the decision is FAIL is a finding about zoteus's pause/resume shape, not about
whether the counters work — the positive control (`work.embed.build.done` +109 on a never-stopped
instance) proves the counters move correctly and durably, exactly as 0642's own unit and live
tests already showed. Whether a PR that only proves its own counters correct is worth sending
upstream *before* zoteus also grows something resume-shaped is a judgment call for the author;
this run supplies the missing measurement, not the decision. `verification/UPSTREAM-PR-WORK-COUNTERS-0642.md`
stays unsent.

## An incidental, unrelated finding: R23 raised rather than decided

`R23-foreign-stamp-ends-up-serving` raised `OperationalError: attempt to write a readonly
database` in every run this session, seeded or not, before and after this ticket's own changes —
reproduced, not introduced, and out of this ticket's own scope to fix (R23 does not touch
`RESUME_EMBEDDING` or the counters at all). The cause is confirmed, not merely argued:
`check_foreign_stamp_ends_up_serving` opens the seeded index directly, as the *operator*, for
`_restamp`'s write, in between two `with target.running()` blocks that spawn the target process
under the `tester` account. That spawned process is the first to open the file, and SQLite
creates its `-wal`/`-shm` sidecar files at that point — inspected directly in this session's own
R23 arena, both are `tester:tester`-owned with `other::r--`. The account posture's default ACL
on the arena grants `tester` a *named* entry on files the operator creates
(`user:tester:rwx`), but grants the operator no reciprocal named entry on files `tester`
creates — haduong falls through to the unnamed `other::r--` class on those two files, hence
"attempt to write a readonly database" the moment `_restamp`'s own connection (running as the
operator) needs to write to the WAL. Not filed as a ticket here — informational for whoever
picks up R23, and arguably `posture.py`'s own concern (the arena's ACL recipe, not this
adapter) rather than a zoteus-adapter defect.

## Files

- `acceptance-zoteus-r22-seeded.json` — the full `run.py` pass against the patched,
  `work-counters-0642` build, seeded with the fixture step 2 built. R22's two clauses are read
  from this file, verbatim, above.

## Reproducing

Requires a built `work-counters-0642` branch checkout of `zoteus` (`npm ci && npm run build`),
the standalone `@huggingface/transformers` install this repo's `project-live-smoke-recipe`
memory documents, the `tester` account and sudoers rule from the Makefile's `ACCEPTANCE_ARENA`
recipe (ticket 0625), read-ACL for `tester` on the built checkout and the transformers install
(the Makefile's own parent-traverse-then-recursive-rX recipe), and a resident Zotero library
reachable over the cloud API (`ZOTEUS_LOCAL=off`, `ZOTERO_API_KEY` from
`~/.config/keys/zotero.env`).

```sh
# 1. Build a seed index with passagesWithoutVectors > 0: a real build, stopped mid-embed.
#    (bench/mcp_drive.py's Server class driven directly, polling action:"status" until
#    embedding is observed underway, then calling action:"stop" — see this ticket's own
#    scratch script for the exact pattern; not vendored into the repo, since it is a one-time
#    fixture-building step rather than part of the acceptance layer itself.)

# 2. Run the acceptance harness against the patched build, seeded.
python3 bench/acceptance/run.py --adapter zoteus \
  --arena "$ACCEPTANCE_ARENA/0643-r22" --posture account \
  --adapter-option entrypoint=/path/to/work-counters-0642/dist/index.js \
  --adapter-option transformers_path=~/.zoteus-deps/node_modules \
  --adapter-option seed_index=/path/to/the/interrupted/search-index.sqlite \
  --output bench/results/0643-resume-embedding-perturbation/acceptance-zoteus-r22-seeded.json
```
