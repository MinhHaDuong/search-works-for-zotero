# Phase 0+1 work counters — does a real build move R22 off `not-run`, and does it prove durability?

Ticket 0642, the goal-1 slice of tracker 0613's gap C and of ticket 0033's scoped issue A. This
directory is the measured answer to two separate questions the ticket asked: does the real,
durable counter implementation work end to end against a live target and a real library (yes),
and does landing it move `R22-pause-stops-background-work` / `R22-pause-holds-across-restart`
off `not-run` (no — for a reason already on record before this run, confirmed rather than
discovered here).

**This is an ungraded diagnostic**, the same status `bench/results/0629-gap-a/` and
`bench/results/0630-gap-b/` carry. Every clause's verdict in the two acceptance artifacts below
is real and machine-produced, but the patch under test is a local branch of `MinhHaDuong/zoteus`
(`work-counters-0642`, pushed to the author's own fork, not upstream) — not yet zoteus's shipped
behavior. Nothing in `README.md`'s graded ladder moves because of this run; that only happens if
and when the maintainer merges the change (or a fork this repo controls is what a graded run
measures against).

## What ran, and in what order

1. **Unit tests, against the patch itself**, not the harness: `tests/features/work-counters.test.ts`
   in the zoteus checkout (a positive control, a migration-path case, a salvage/noop case, a
   cross-connection durability case, a forced-rollback atomicity case). Full suite 1097 passed, 0
   failed, 7 skipped (pre-existing, no `node:sqlite` in some environments). `npm run lint`,
   `npm run build`, `npm run typecheck:tests` all clean. Not reproduced as a file here — see the
   zoteus branch itself; this directory is this repo's artifact, not zoteus's.

2. **A live end-to-end proof against a real, resident Zotero library**
   (`live-seed-build-status.json`), before touching the acceptance harness at all: the patched
   build, run with `bench/mcp_drive.py`'s `Server` directly (not yet under the harness), against
   this operator's own library (7 546 items available), `action:"build" limit:1 own_words:false
   fulltext:false`. `action:"status"` reported `work.embed.build.done: 1` after the build. A
   **separate** `sqlite3` connection — no zoteus process running at all — reopened the resulting
   `search-index.sqlite` file cold and read back `work_counters = [('embed', 'build', 'done', 1)]`.
   This is what "durable" means for this ticket: the number was not read from anything a process
   remembered, it was read off disk by something that had never run the process. This step exists
   because the acceptance harness's own R22 checks, run first without it (see below), could not
   get far enough to exercise the counter at all — the target's data directory starts empty and
   nothing in `install()`/`pause()`/`perturb(EDIT_ONE_ITEM)` ever triggers a build.

3. **`bench/acceptance/run.py --adapter zoteus`, unseeded** (`acceptance-zoteus-r22-unseeded.json`).
   `R22-pause-stops-background-work` and `R22-pause-holds-across-restart` both report `not-run`,
   `why: "the positive control ... reports no work.<stage>.<trigger>.<outcome> counters"`. Honest,
   and unsurprising given step 2's finding: the target the harness builds here has an empty data
   directory (no `seed_index` was passed), so no embedding has ever happened for either the graded
   target or its never-stopped positive-control instance — this state says nothing about whether
   the counter mechanism works, only that a target that has never embedded anything has nothing to
   report yet, which is correct.

4. **`bench/acceptance/run.py --adapter zoteus`, seeded** (`acceptance-zoteus-r22-seeded.json`),
   `--adapter-option seed_index=` pointing at the `search-index.sqlite` step 2 produced (copied
   into a fresh path so the harness's own seeding, not this ticket's ad hoc script, places it).
   Seeding gives BOTH the graded target and its positive control an index that already carries a
   real `work.embed.build.done: 1` row from the moment either process opens it.

## The R22 finding, seeded

```
R22-pause-stops-background-work          NOT-RUN
R22-pause-holds-across-restart           NOT-RUN
```

Detail, both clauses, verbatim:

> the positive control — a second, never-stopped instance of this target — could not be
> perturbed (this adapter cannot drive the perturbation 'edit-one-item' against its target (this
> would write to the user's own Zotero library, which this target is configured read-only
> against and which R15 excludes from derived state, so the harness declines to drive it and the
> clause is not decided here); the clause is not decided here), so the harness could not show
> that the change it makes creates work at all, and this clause is not decided

**This is not a new blocker.** It is exactly tracker 0613's gap-C log entry of
2026-09-04T05:33Z, confirmed by direct measurement rather than by source-reading prediction:
`_the_change_creates_work` (`bench/acceptance/assertions.py`) needs a positive control that
creates work on a never-stopped instance, and the only perturbation either R22 clause is wired
to drive is `EDIT_ONE_ITEM` — a write to the user's own Zotero library, which `zoteus.py`'s
adapter refuses on a principled R15 ground this ticket's scope does not touch. Landing durable
counters — proven real and durable above — does not by itself unblock R22, because the gate
sitting in front of it is independent of whether counters exist. Ticket 0636 (an R22-only check
via a different, build/embed-triggered perturbation, sidestepping `EDIT_ONE_ITEM` entirely) was
drafted for exactly this gap and dropped by the author on 2026-09-04 in favor of relying on the
real counters landing through 0033/0642 instead — that decision did not claim counters alone
would be sufficient, and this run is the first direct measurement confirming they are not. What
would still be needed, unstarted here and explicitly out of this ticket's scope: a second,
build/embed-triggered perturbation added to `durability.py`'s vocabulary and to the zoteus
adapter, or a reopening of 0636's own sidestep design.

**One incidental improvement this seeding produced, unplanned:** `R13-two-processes-both-answer`
and `R13-two-processes-do-not-duplicate-work` both moved from `not-run` to `PASS` between the
unseeded and seeded runs (both goal-2 clauses needing "an index already in service," which the
unseeded arena had none of). Not this ticket's target and not claimed as this ticket's
accomplishment — recorded because the same seed index is what moved both, and a reader comparing
the two JSON files would otherwise wonder why.

`R23-foreign-stamp-ends-up-serving` stayed `not-run` in both runs, for an unrelated reason: "the
index served nothing before the stamp was touched, so an empty answer afterwards would prove
nothing about migration" — a `limit:1` seed is too small for that clause's own query fixture to
land a hit before the perturbation runs. Not investigated further here; out of scope for a
work-counters ticket.

`R10-no-egress` still `FAIL` in both runs (the default configuration issues its update-check DNS
lookup — gap A, tickets 0629/0634, unrelated to this patch and unmoved by it).

## Files

- `live-seed-build-status.json` — the live, pre-harness proof: a real build's `status` reply,
  with provenance, and what a cold re-read of the resulting file confirmed.
- `acceptance-zoteus-r22-unseeded.json` — a full `run.py` pass against the patched build, no
  `seed_index`. Establishes the "reports no counters" baseline honestly, before anything has
  embedded.
- `acceptance-zoteus-r22-seeded.json` — the same pass, `seed_index` pointing at a copy of the
  file `live-seed-build-status.json` describes. This is the run the R22 finding above is read
  from.

## Reproducing

Requires a built `work-counters-0642` branch checkout of `zoteus` (`npm ci && npm run build`),
the standalone `@huggingface/transformers` install this repo's `project-live-smoke-recipe`
memory documents, the `tester` account and sudoers rule from the Makefile's `ACCEPTANCE_ARENA`
recipe (ticket 0625), and a resident Zotero library reachable on the local API.

```sh
# 1. Build a seed index with the patch (any small library build works; here limit:1
#    against a real, resident library over the local API).
python3 bench/mcp_drive.py --server /path/to/work-counters-0642/dist/index.js \
  --tool zotero_index \
  --args '{"action":"build","limit":1,"own_words":false,"fulltext":false}' \
  --env ZOTEUS_DATA_DIR=/tmp/seed/data --env ZOTEUS_EMBEDDINGS=local \
  --env ZOTEUS_TRANSFORMERS_PATH=~/.zoteus-deps/node_modules \
  --env ZOTEUS_INDEX_BACKEND=sqlite --env ZOTEUS_READ_ONLY=true
# poll action:"status" the same way until state:"done" — mcp_drive.py's one-shot --tool
# call starts the build and returns immediately; use bench/mcp_drive.Server directly (as
# this run did) to keep one process alive across build + poll + read.

# 2. Run the acceptance harness against the patched build, seeded.
python3 bench/acceptance/run.py --adapter zoteus \
  --arena "$ACCEPTANCE_ARENA/0642-seeded" --posture account \
  --adapter-option entrypoint=/path/to/work-counters-0642/dist/index.js \
  --adapter-option transformers_path=~/.zoteus-deps/node_modules \
  --adapter-option seed_index=/tmp/seed/data/search-index.sqlite \
  --output bench/results/0642-work-counters/acceptance-zoteus-r22-seeded.json
```
