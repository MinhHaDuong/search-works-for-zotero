# What triggers an upstream index update, and how often

*Evidence, not authority. Read at source on 2026-09-02 for ticket 0503, the
read-at-source half. The measurement half is deferred and its reason is stated
below. Where anything here touches the design, the owning document in
`AGENTS.md`'s document set is the record.*

**Subject:** upstream `oscardvs/zoteus` at
`b05ed69a88e3a0c1ef874f57f97a0e11ddf7ec3c`, tag `v1.12.0`, which is
`UPSTREAM_REVIEWED_SHA` in this repo's `UPSTREAM` file. Every `file:line` below
addresses that tree, verified by `git rev-parse HEAD` against `UPSTREAM` before
anything was read.

**Substrate:** a fresh read-only clone in a scratch directory, not `fork/`.
Nothing was built, nothing was executed, and Zotero's local API was not touched
— the reference machine is running a full-library build tonight and this read
must not compete with it.

## The question

Ticket 0503 asks what **triggers** an upstream update run and **at what
cadence** — "whether the update path is a cadence, a hook on a Zotero event, or
something that only happens when a build or a query asks". R35's row in
`README.md` stood at `inferred` because nobody here had opened the source on
that point.

## Verdict

**Upstream has no discovery cadence and no discovery trigger of its own. The
update path runs when, and only when, an MCP caller asks for it by name.**

The whole update path has exactly one entry point, `startIndexUpdate`
(`src/features/search/build.ts:369` @ `b05ed69`), and exactly one call site in
the whole of `src/`:

    src/tools/index-tool.ts:125    const s = startIndexUpdate(ctx, lib, maxItems, opts);

That line is reached only from the `zotero_index` tool handler, on the branch
`if (args.action === 'update')` (`src/tools/index-tool.ts:124` @ `b05ed69`),
where `action` is a required argument of the tool's input schema —
`action: z.enum(['build', 'refresh', 'update', 'status', 'stop'])`
(`src/tools/index-tool.ts:22` @ `b05ed69`). So the trigger is a tool call, the
cadence is whatever the caller's cadence happens to be, and upstream states
none. The tool's own description confirms the intended usage in the same
breath: it tells the caller to "poll `action:"status"`" and never tells anything
to poll for changes (`src/tools/index-tool.ts:20` @ `b05ed69`). The handler's
only other mention of the verb is a refusal — an update against an unreadable
store is turned away rather than repaired (`src/tools/index-tool.ts:83` @
`b05ed69`) — so it adds no second route in.

**A query can start a first BUILD; it never starts an UPDATE.** The other
caller-independent path into indexing is
`src/tools/semantic-search.ts:51` @ `b05ed69`, `const s = startIndexBuild(ctx);`
— reached only inside `if (ctx.search.isEmpty)`
(`src/tools/semantic-search.ts:31` @ `b05ed69`) and only when the caller has not
passed `auto_build:false`. That is first-time setup on an empty index, not
discovery of a change to a populated one. A query against a non-empty index
kicks nothing: the handler falls straight through to ranking.

**Startup kicks nothing either.** `src/index.ts` warms the tool context —
`void context()` at `src/index.ts:106` @ `b05ed69` — which opens the search
index and probes Zotero; it calls neither `startIndexBuild` nor
`startIndexUpdate`. `src/lib/lifecycle.ts` is 54 lines of shutdown handling and
carries no reference to indexing at all.

**The only periodic thing in the tree is unrelated to library content.**
`UpdateChecker` (`src/lib/update-check.ts:43` @ `b05ed69`) checks the *software
release* feed at most once per day
(`CACHE_TTL_MS = 24 * 60 * 60 * 1000`, `src/lib/update-check.ts:8` @ `b05ed69`).
It has nothing to do with items.

**Nor is there a cadence outside the process.** `deploy/` holds a
`zoteus.service` and a `Caddyfile` and no `.timer` unit; `docker-compose.yml`,
`fly.toml`, `Dockerfile` and `scripts/` carry no cron, systemd timer or
schedule. `.env.example` and `src/config.ts` expose no interval, cadence, poll
or period knob of any kind.

### What this rules out, and how each nil was earned

A grep that returns nothing because the construct is absent and a grep that
returns nothing because it was mis-typed are the same output. Each probe below
therefore carries a control: the same expression with one alternative added that
is known to exist in the tree. The control firing is what makes the nil
readable.

Every command runs with GNU grep from the root of a clone checked out at
`b05ed69`, and every one of them was re-run on 2026-09-03; the results below are
what they printed. **An earlier version of this table did not reproduce.** Three
rows were wrong and all three are corrected here, each noted in place: one
expression was a syntax error whose nil meant "could not look", one matched
1 340 lines while the row claimed nil, and one positive control undercounted its
own hits. A table that does not reproduce is exactly the defect this report is
about, so the corrections are recorded rather than quietly absorbed.

| # | Probe | Result | Control | Control result |
|---|---|---|---|---|
| 1 | `grep -rnE 'setInterval' src/` | one hit, and it is not a trigger: `src/transports/stdio.ts:93`, a shutdown-flush keepalive cleared four lines later | `grep -rnE 'setInterval\|setTimeout' src/ \| wc -l` | `13` — the hit above plus 12 `setTimeout`, so the expression fires where the construct exists |
| 2 | `grep -rnE 'cron\|node-schedule\|node-cron\|scheduler\|\.schedule\(' src/` | no output, exit 1 | same expression with `\|setInterval` appended | `src/transports/stdio.ts:93`, exit 0 |
| 3 | `grep -rnE 'fs\.watch\|watchFile\|chokidar\|inotify\|FSWatcher' src/` | no output, exit 1 | same with `\|readFileSync` | `src/api/local-writes.ts:2` and `:198`, exit 0 |
| 4 | `grep -rnE "WebSocket\|EventSource\|text/event-stream\|EventEmitter\|\.subscribe\(\|\.on\('change'\|\.addEventListener\(" src/` | no output, exit 1 | same with `\|AbortController` | `src/lib/update-check.ts:88`, `src/lib/health.ts:56`, `src/lib/cimd.ts:136`, `src/api/http.ts:54`, exit 0 |
| 5 | `grep -rnE 'Notifier\|addObserver\|registerObserver\|\bnotify\(' src/` — a Zotero event subscription | no output, exit 1 | same with `\|localApiDegraded` | 8 hits in `src/features/search/index-manager.ts` (`:236`, `:530`, `:531`, `:536`, `:597`, `:598`, `:805`, `:1248`), exit 0 |
| 6 | `grep -rnE '\bstartIndexUpdate\s*\(' src/ \| grep -v 'export function'` | one call site, `src/tools/index-tool.ts:125` | the identical enumeration for `startIndexBuild` | **three** call sites — `src/tools/semantic-search.ts:51`, `src/tools/index-tool.ts:136`, `src/features/search/build.ts:382` — so the enumeration finds three when three exist |
| 7 | `grep -rnE 'cron\|systemd\|OnCalendar\|schedule' deploy/ scripts/ .github/ docker-compose.yml fly.toml Dockerfile mcpb/` | no output, exit 1 | same with `\|zoteus` | `deploy/zoteus.service`, `deploy/Caddyfile`, `docker-compose.yml`, `fly.toml`, `mcpb/manifest.json` and five files under `scripts/`, exit 0 |
| 8 | `grep -nE 'INTERVAL\|CADENCE\|POLL\|PERIOD\|EVERY\|CRON\|SCHEDULE' .env.example` | no output, exit 1 | same with `\|ZOTEUS_INDEX_MAX_ITEMS` | `.env.example:72`, exit 0 |
| 9 | `grep -nE 'interval\|cadence\|poll\|periodic\|schedule' src/config.ts` | no output, exit 1 | same with `\|indexMaxItems` | `src/config.ts:43` and `:338`, exit 0 |

**Row 2 was a syntax error.** It was written as a basic regular expression
ending `\.schedule\(`, where `\(` opens a group that is never closed; GNU grep
exits 2 with `Unmatched ( or \(` and prints nothing. Its nil said "could not
look", not "nothing there". Rewritten as an extended regular expression, where
`\(` is a literal parenthesis, it runs and is genuinely empty.

**Row 4 matched 1 340 lines.** It carried `update` and `item` as bare top-level
alternatives, which match most of `src/`; the row nevertheless reported nil, so
the row and the expression beside it were not the same probe. Both alternatives
are removed. They could not have discriminated a subscription from any of the
hundreds of ordinary uses of those two words, and the constructs that *would*
show a push channel — `WebSocket`, `EventSource`, SSE, `EventEmitter`,
`.subscribe(`, a `'change'` listener, `addEventListener` — are what the row now
tests.

**Row 6's control undercounted.** It reported two `startIndexBuild` call sites
and there are three. The missed one is `src/features/search/build.ts:382`, and
it is inside `startIndexUpdate` itself; the consequence is set out below and it
is not bookkeeping.

Also read directly rather than grepped: `src/index.ts` in full (119 lines),
`src/lib/lifecycle.ts` (54 lines), the `zotero_index` handler
(`src/tools/index-tool.ts:100-140`), the `zotero_semantic_search` handler
(`src/tools/semantic-search.ts:25-80`), `startIndexUpdate` itself
(`src/features/search/build.ts:360-400`) and `updateBlocker`
(`src/features/search/index-manager.ts:1185-1218`). Upstream's runtime
dependency list carries no scheduler: `@modelcontextprotocol/sdk`, `citeproc`,
`cors`, `express`, `express-rate-limit`, `zod` (`package.json`).

### The negative, stated at the width the evidence supports

What is established is that **no path in the upstream tree at `b05ed69` starts
an index update by itself** — not a timer, not a Zotero event, not a file
watcher, not a stream subscription, not process startup, not a query, and not a
deployment-level schedule. What is *not* claimed is that nothing anywhere
notices a change: an MCP host that calls `zotero_index action:"update"` on a
clock of its own gets exactly the cadence it dials, and Zotero's own extraction
happens whether anyone asks or not. Upstream supplies the *mechanism* of
noticing and no *clock* for it.

## One call site, two costs: `action:"update"` is bimodal

Enumerating `startIndexBuild`'s call sites correctly turns up a third, and it
sits inside the update path:

    src/features/search/build.ts:382    return startIndexBuild(ctx, lib, maxItems, { ...opts, note: ... });

It is reached when `ctx.search.updateBlocker(backend)` returns a reason
(`src/features/search/build.ts:380` @ `b05ed69`). So a caller who asks for an
update does not always get a delta. On any of six conditions the same call runs
a **full rebuild** instead, with the reason attached to the status rather than
silently (`updateBlocker`, `src/features/search/index-manager.ts:1190-1218` @
`b05ed69`):

1. the store could not be read at all — and an unreadable index overrides the
   method to refuse unconditionally (`src/features/search/corruption.ts:70` @
   `b05ed69`);
2. the backing store cannot remove rows, so a deleted item could never leave
   the index;
3. the index is empty;
4. no library version stamp exists to diff against — either the build that
   would have written one was interrupted, in which case the rebuild resumes
   from its checkpoint, or the index predates incremental updates;
5. the stamp came from a different Zotero API than the one this update would be
   served by, whose version sequences are unrelated;
6. the stored vectors were produced by a different embedder than the one now
   configured.

None of this touches the verdict: the trigger is still a caller and there is
still no cadence. What it changes is the **deferred half**. `SPEC.md` §5.2.4's
reconcile tick calls this path on a clock, so the cost of a tick is not one
number but two — a cheap delta, and a whole library — with a documented rule
selecting between them. Measuring only the delta would report the mode and call
it the cost. The handler upstream already declines to assume which mode ran,
reading the outcome back off the status instead
(`s.operation === 'update' ? 'Index update' : ... 'Full index rebuild'`,
`src/tools/index-tool.ts:127-131` @ `b05ed69`); the measurement needs the same
discipline — record the mode each tick took and report the two distributions
apart.

## Consequence for R35

R35 promises that the system notices a new, changed or deleted item within one
minute, **without anyone asking**. That last clause is the one this read
settles, and it settles it against upstream: upstream's discovery is
caller-driven, so the promise is met by nobody at `b05ed69` unless the caller
asks — which is precisely the thing R35 says must not be required. The
machinery R35 needs exists upstream (the version cursor for changes, the
keys-only census for deletions, both described in the tool's own text at
`src/tools/index-tool.ts:20`); the clock does not.

The clock is therefore ours alone. `SPEC.md` §5.2.4's reconcile tick — 60 s when
idle, conductor-owned, deletions subtracted every tick — is the only thing in
either tree that would deliver R35's minute, and it is design, not code.

**R35's row moves off `inferred` to `code`**, on the README's own definition of
that class ("the source was opened at the reviewed baseline"). What the row now
says is not that the promise is kept but that its standing is read rather than
guessed: upstream supplies the mechanism and no cadence, so R35's minute rests
entirely on `SPEC.md` §5.2.4's tick. The row does not go to `measured`, and
cannot until the deferred half below runs — the README's own rule is that a row
is not upgraded to `measured` without the artifact that measured it.

## The measurement half: deferred, and what it needs

**Explicitly not attempted, and the reason is contention, not difficulty.** The
reference machine `doudou` is running a ~17 h full-library build tonight, and
driving Zotero's local API from a second lane is exactly what degrades it —
`localApiDegradedAt` has been observed mid-build, after which the whole session
falls back to the slower Web API and the build's remaining time stops resembling
its start. The overnight briefing
(`/home/haduong/data/projets/zoteus-bench/overnight-2026-09-02/BRIEFING.md`)
makes doudou's Zotero staying strictly idle a condition of tonight's run. A
latency probe is a second lane against that same API, so it does not run
tonight.

What the deferred half needs:

- a quiet reference machine — doudou, per `SPEC.md` §5.2.8, with no build in
  flight and Zotero idle;
- the two latencies: **deletion** (from the delete in Zotero to the text no
  longer being served) and **new item** (from the add to the item being
  queued), each measured rather than reasoned;
- **the mode of every tick recorded, not just its duration.** This one is new
  with this read. `action:"update"` is bimodal — the six conditions above send
  it to a full rebuild — so a run that reports a single mean over an unrecorded
  mix reports nothing. Read `operation` off the status the way
  `src/tools/index-tool.ts:127-131` does, keep the delta and the rebuild
  distributions apart, and state how many ticks fell each way;
- an artifact committed under `bench/results/`, per the README's rule that no
  row reaches `measured` without one.

One thing this read changes about that measurement's shape: since upstream
starts nothing by itself, a latency measured against upstream as-is measures
the *caller's* cadence plus the update run, not a discovery latency. The honest
measurement is of the update run's own cost — how long `action:"update"` takes
to see a change once invoked — and of what the item census costs per tick, which
`SPEC.md` §5.2.4 already flags as unmeasured beside the full-text one. The
minute itself is a property of our tick, and there is no upstream number that
either confirms or refutes it.

## Question for the author

Does R35's clock stay ours, or is a discovery cadence something to offer
upstream? The read makes the gap concrete and small — upstream has every piece
except a caller — and `GOVERNANCE.md` bounds what may be filed. Nothing here
assumes an answer; §5.2.4's tick is written as ours either way.
