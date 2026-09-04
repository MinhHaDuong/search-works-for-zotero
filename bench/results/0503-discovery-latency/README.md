# What a reconcile tick costs, measured

Ticket 0503, the measurement half. The read-at-source half is
`verification/UPSTREAM-DISCOVERY-0503.md`, which established that **upstream has
no discovery cadence of its own**: `startIndexUpdate` has exactly one call site
in `src/`, reached only when an MCP caller passes `action:"update"`. There is
therefore no upstream discovery latency to measure. What is measured here is the
thing SPEC.md §5.2.4's 60 s reconcile tick has to fit inside.

## Machine and scope

| | |
|---|---|
| machine | **padme**, quiet: no build in flight, Zotero desktop idle, local API not degraded |
| Zotero | 10.0.1, local API at `http://127.0.0.1:23119`, datadir `/home/haduong/data/Zotero-fresh` |
| upstream | `b0e0bc872b5727d21ea83aba8bfe834293013264` (`v1.13.0`+4), re-read from `UPSTREAM` at run time |
| library scope | **`/items/top` — 7 546 top-level items**, the population SPEC.md's worked example uses |
| indexed | 7 546 of 7 546 available (`items == itemsAvailable`, asserted by the harness) |
| full text | 5 559 items with text, 148 454 full-text passages, 163 556 passages total |
| embedder | **off (keyword-only)**, SQLite backend, `ZOTEUS_INDEX_FULLTEXT=1` |

**The item-count scope was settled before this run and is not re-opened here.**
`/items` counts every record including child attachments and notes (17 518);
`/items/top` counts bibliographic entries (7 546, five above SPEC.md's cited
7 541 — ordinary growth). This artifact is `/items/top` throughout. Personal
library; two group libraries are visible to the server (`localGroups=2`) but the
indexed scope is the user library alone.

`ZOTEUS_INDEX_MAX_ITEMS` had to be raised from its default of 5 000. Left alone
it indexes 5 000 of the 7 546 items **silently**, and every figure below would
have described two thirds of a library while claiming SPEC.md's population. The
harness now asserts `items == itemsAvailable` and refuses to report otherwise.

**Keyword-only is a floor, not the configuration a user runs.** With an embedder
on, every figure here rises by the embedding cost of whatever the tick touches.
The bound question below is decided by the census figure, which embedding does
not affect; the tick-cost figures are lower bounds.

## The one-time manual step

Zotero 10+ gates local-API writes behind an in-app grant
(`POST /api/local/authorize`, `src/api/local-writes.ts`). The author clicked
**Always Allow** on padme's desktop on 2026-09-04; the grant came back
`{"remember": true}`, so it persists and no later run needs the dialog. Not
automatable, and not scripted around.

## The positive control, which fired

Before any rep was trusted the harness forced a full rebuild and checked that it
was labelled one. `updateBlocker` makes `action:"update"` fall back to a whole
rebuild on six conditions (`index-manager.ts:1409-1437`), and
`index-tool.ts:127-131` is where the server labels which happened. Without the
control, a harness that always said "delta" would pass silently on every rep.

**It caught a real defect on the first attempt.** The procedure sketched in the
ticket — `action:"refresh"`, then `action:"update"` — polls the refresh to
completion, and refresh *rebuilds* the index, so by the time the update was
issued the index was no longer empty and the tick was a genuine 1.0 s delta. The
control reported the forced rebuild as a delta and **aborted the run before any
rep was reported**. That first record is kept beside this one as
`control-failure-first-attempt.json`.

The fix is to issue the first `action:"update"` against a **wiped data dir**,
which is what actually meets condition 3 — and which establishes the delta-path
precondition in the same run instead of paying for two rebuilds. The control
then passed, reproducibly: **91.8 s** on the first corrected run, **91.3 s** on
the recorded one, both correctly labelled `rebuild`.

A second defect surfaced one level down and is worth recording because it has
the same shape. `visible()` sent its query under the key `query` where the tool's
schema names it `q` (`semantic-search.ts:22`), so every call was a schema error,
caught by a bare `except` and read as "not visible yet" — the poll loop then span
toward its timeout on a rep whose item was in the index all along. A failed tool
call now raises instead of returning False.

## Results

All ten reps ran on the delta path (`operation: "update"` on every poll). No rep
fell back to a rebuild, so the rebuild distribution here contains only the forced
control — reported apart, never averaged with the deltas.

### Delta ticks

| | n | min | median | max |
|---|---|---|---|---|
| new item becomes searchable | 5 | 44.10 s | **47.11 s** | 98.13 s |
| deleted item stops being served | 5 | 1.051 s | **1.052 s** | 1.054 s |

### Full-rebuild tick (forced, the positive control)

| | n | value |
|---|---|---|
| whole library rebuilt, keyword-only | 1 (+1 unrecorded) | **91.3 s** (91.8 s on the prior run) |

### Item census — the number §5.2.4 called unmeasured

§5.2.4 states of the per-tick item census: *"What the item census costs per tick
is unmeasured, unlike the full-text one above."* Measured here, against the
7 546-item library:

| arm | time | payload |
|---|---|---|
| deletion-by-subtraction, full key set (`/items/top?format=keys`) | **45 ms** | 7 546 keys, 68 KB |
| incremental (`?since=<libraryVersion>`) | 36 ms | 0 keys (nothing changed), 0 B |

The full-text census beside it is 8 037 attachments over 5 999 items, confirming
§5.2.4's ~8 037 figure on this library.

## Reading the numbers

**The delete figure is at the measurement floor.** Every delete rep came back
between 1.051 s and 1.054 s because the update completed before the harness's
first 1 s status poll. 1.05 s is therefore an *upper bound quantized by the poll
interval*, not a measured cost. Re-running with a sub-100 ms poll would put a
real number on it; nothing in this artifact's conclusions depends on doing so.

**The add figure is dominated by the metadata phase, and its cause is not
isolated.** Every add tick sat in `phase: "metadata"` for its whole run — 44 s on
rep 1, 98 s on rep 2 — while the server's own line reported *"1 changed items
re-indexed, 0 removed, 7547 items total"*. So the time is not spent indexing the
one new item. One candidate is that the tick re-walks the whole item set when the
library-version cursor moves; another is that each add rep's tick also absorbs
the previous rep's cleanup deletion, since each rep deletes its throwaway at the
end without running an update. **The recorded finding is the observation and the
phase evidence, not a mechanism.** The experiment that would settle it is a
single add tick against a library with no other pending change, with the item
cursor logged before and after.

## The bound: confirmed, and the reason it survives

The measured update run does **not** fit inside 60 s. Two of five add ticks
exceeded it (68 s, 98 s), and a full-rebuild tick is 91 s every time.

That is not a finding against SPEC.md §5.2.4's 60 s cadence, because
**`action:"update"` is not the tick §5.2.4 specifies.** §5.2.4 is explicit that
*"No document fetch happens inside the tick"* — the tick asks what changed and
writes work orders, and the pipeline worker does the fetching (§5.2.5).
Upstream's `action:"update"` is tick *and* worker in one call, which is precisely
the shape §5.2.4 declines. What the tick as specified does is the census, and the
census is **45 ms**: three orders of magnitude inside the minute, on a library at
SPEC.md's own worked size.

So §5.2.4's values stand as written and no DECISIONS.md ruling is needed. What
this measurement adds is evidence that the tick/worker split is load-bearing
rather than tidy: an upstream-shaped update run inside the tick would blow the
minute on this library, on a quiet machine, with the embedder off.

R35's one-minute promise (ruled 2026-08-31) is untouched either way — it was
never delegated to §5.2.4's numbers, and nothing here bears on it.

## Files

- `discovery-latency.json` — the recorded run: every poll's `operation` and
  `phase`, per-rep latencies and labels, the census arms, and the control.
- `control-failure-first-attempt.json` — the aborted run whose positive control
  failed. Kept because a control that has never fired is not known to work.
- `bench/discovery_latency.py` — the harness; `tests/test_discovery_latency.py`
  covers the classifier and the summarizer.

Reproduce:

```bash
make upstream-checkout && (cd fork && npm install && npm run build)
python3 bench/discovery_latency.py \
  --server fork/dist/index.js \
  --data-dir /home/haduong/data/t0503-discovery \
  --local-key "$ZOTEUS_LOCAL_API_KEY" \
  --zotero-data-dir /home/haduong/data/Zotero-fresh \
  --out bench/results/0503-discovery-latency/discovery-latency.json --reps 5
```

Every item the run writes is a throwaway tagged `zoteus-0503-throwaway`, deleted
again at the end of its own rep and swept by tag at the start and end of the run.
No real library item is created, modified, or deleted. The library was verified
clean of probe items after the run.
