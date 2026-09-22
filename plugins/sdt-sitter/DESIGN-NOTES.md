# SDT pack sitter — design notes

Written for a Zotero developer, not for someone installing the add-on: what
this build is an experiment in, what trying to be polite inside the platform
revealed about it, and what none of it claims. Nothing here is needed to use
the sitter — that is `RELEASE-NOTES.md`, which these notes were crowding out.

Moved here unedited on 2026-09-14. The release notes had reached 680 lines of
engineering rationale under a filename that promises a short list of what
changed; the two audiences were fighting each other and the essays were
winning.

## Three experiments in one plugin

This release is three experiments rather than one, and they are worth separating
because they can fail independently.

**Scheduling.** Whether extraction can usefully run eagerly — ahead of any
consumer's demand — over Zotero's own extractor and worker, under an admission
policy that yields. The next section is this one.

**Concurrency.** What an eager third party finds out about the platform's
implicit concurrency model by trying to be polite inside it. That is the section
following the removed controls, and its findings are about the platform rather
than about the plugin.

**Supervision.** Whether an unattended background process can be made
accountable to the person whose machine it runs on. The commitments there are
narrow and checkable: name what the sitter is waiting for rather than only that
it waits, with the phases worded as waiting so that on and off name the user's
own switch alone; never display a number nobody observed, so an unmeasured
duration is withheld and an overrunning job makes the finish estimate
unavailable rather than now; and keep what the sitter does not control readable
at any time rather than only in a first-run dialog. This is the axis with the
least favourable evidence of the three, and nothing here claims otherwise. The
independent panel review returned "APPROUVÉ AVEC RÉSERVES pour un usage
expérimental cette nuit", followed by "pas encore une interface de supervision
aboutie", and "CHANGES REQUESTED pour qualifier l'UI d'accessible ; pas de
blocage fonctionnel démontré pour l'usage visuel à la souris". Reduced-motion
handling and a stable accessible name were built after it; keyboard access,
focus restoration, screen-reader announcement and overflow at enlarged font
sizes remain unestablished, and no unit test takes those readings. The verdicts
and their disposition are in
[the panel review](../../verification/SDT-SITTER-UI-PANEL.md).

## The scheduling experiment: an eager extracting scheduler

The sitter changes one thing about structured-text extraction: when it happens.
The extractor, the shared worker, the pack format, the cache location and the
identity checks that decide reuse are all Zotero's, and the sitter reimplements
none of them. What it contributes is a scheduling policy, and that policy is
what this release asks a reader to evaluate.

In those terms Zotero prepares packs lazily: one is produced when a consumer
asks for it — a reader opening the attachment, an automatic indexing pass
reaching the item, an internal caller of the generation entry point. The sitter
is the eager arm of the same choice. It enumerates the attachments a library can
support and prepares their packs before any consumer asks, so that the first
demand meets a cache hit rather than a model inference.

Eagerness is defensible here for a reason that belongs to the work rather than
to our implementation. Extraction is deterministic given the source bytes and
the processor versions, and its result is durable in Zotero's own cache, so work
done early is never wrong — it can only go unused, on documents nobody reads or
searches. What the eager arm buys is control over when the cost falls: an idle
machine overnight, instead of the moment someone first searches. What it costs
is that the cost falls unconditionally, and in proportion to the library rather
than to what is used.

"Durable" needs a qualifier: durable only until the processor stamps in
`resource://zotero/document-worker/metadata.json` change. Between the 10.0
build read into SYNC.md (`SDT_SCHEMA_VERSION` 1.1.0, PDF processor 3,
build `20260817151751`, 2026-08-17) and the 10.0.2 build installed
2026-09-11 (build `20260909184950`), `SDT_SCHEMA_VERSION` moved to 1.2.0 and
the PDF processor stamp moved from 3 to 14 — a delta of eleven across three
point releases. Neither `zotero/document-worker` nor
`zotero/structured-document-text` publishes release notes, so whether that
delta was one jump or several is not knowable from here; what is knowable is
that on this host three point releases were enough to move it.

#6012's own suite pins what a processor-stale pack triggers. "Should
regenerate a stale-processor pack before resolving `ensure()`"
(`test/tests/sdtTest.js` at `19e7962`): unlike `getPack()`, which can hand
back the stale pack immediately and regenerate in the background, `ensure()`
blocks until the fresh pack exists. That is the call the sitter's census
makes. The file is byte-identical at `4427be9a` — same blob
`2609c641` at both heads — so this reading needs no re-derivation.

"Work done early is never wrong, only unused" is therefore half the claim.
Work done early can also be redone, on the sitter's own initiative, at a
cadence set by an upstream repository that gives no warning of it. Each
recurrence is a blocking, library-wide pass, not a background one. Eager
preparation is a one-time cost only between processor bumps, and on this
host three point releases already used up that interval once.

An eager scheduler is tolerable only if it yields, so the admission policy is
the substance of the experiment. The sitter submits at most one attachment at a
time; only while Zotero's own worker is idle; only above 4 GiB available memory
and 8 GiB free on the pack's filesystem; and only while the one-minute load
average is below the machine's reported core count. Resources are read again
after the asynchronous checks, and worker idleness once more immediately before
submission, so a document is never deliberately queued behind native work. An
unreadable resource figure refuses admission rather than assuming it. These are
admission guards, not caps: they decide whether to start, and nothing about a
document already running. The thresholds and the rest of the policy are owned by
[SPEC.md's R22 design paragraph](../../SPEC.md).

Two of those three guards are Linux-only, and the sentence above about an
unreadable figure is a Linux sentence. Memory and load come from `/proc`, so on
macOS and Windows they are skipped — not read, not failed, not counted as
unavailable — and the sitter admits work without them. The distinction is drawn
on the platform rather than on whether a reading can be taken, and that is
deliberate: keying it on the read would also grant admission on a Linux machine
whose `/proc` had become unreadable, where a failed reading is a fault and
assuming room on a fault is how an eager scheduler takes a machine down. A
platform the host will not name is treated as Linux, which keeps the stricter
behaviour where the answer is uncertain. The free-disk guard reaches the volume
through host APIs that answer everywhere and is not part of the split. Decided
2026-09-13, ticket
[0783](../../tickets/0783-skip-the-resource-guards-off-linux-and-d.erg); for
the nearest prior art, Zotero's own #6012 reads its memory figure through
`Zotero.Embeddings.Diagnostics.getAvailableMemory()`, returns 0 when the
platform cannot say, and treats 0 as room to proceed on every platform — we
take that posture only where the platform genuinely cannot answer.

Admission is also the *only* control point available, which is the experiment's
sharpest limit rather than an implementation shortcut. The generation entry
point accepts no abort signal, its priority argument orders waiting jobs rather
than running ones, and the shared worker exposes no priority control a plugin
could use; the [prerequisites review](../../verification/SDT-PLUGIN-PREREQUISITES.md)
records all three. An eager scheduler on this host can therefore choose when to
start work, and never what to do next. The consequence is observable: in the
earlier live probe a short attachment submitted behind a very large extraction
rewrote its cache only after the large one had finished, while an isolated
control of the same attachment finished quickly
([live probe](../../verification/INDEX-SITTER-LIVE.md)).

Queue order is a free parameter this experiment has not varied: pending
attachments are taken in the order the census observed them. Zotero's draft
[semantic-search PR #6012](https://github.com/zotero/zotero/pull/6012) has varied
it, and the direction it moved is the interesting part.

At `19e7962`, read 2026-09-08, `_getEligibleItemIDs()` ordered attachments
**smallest first** — "smallest first so that one enormous book doesn't sit at
the head of the queue while the rest of the library waits behind it", with
unrecorded sizes sorting to the end
([§5.3 of the full-text reading](../../verification/VERIFY-FULLTEXT-SQLITE.md),
a reading pinned at that head and left standing). At
`4427be9a`, read 2026-09-12, that policy is gone. The same function now orders
attachments **most recently touched first**, by the greatest of the attachment's
last-read time, its own modification time, its parent's, its annotations' and
its sibling notes', descending. The comment says why: "Attachments the user
touched most recently go first … since those are what they're most likely to
search for". Attachments
are enqueued last, after metadata, because they are "an order of magnitude more
to index".

The move is from a cost-minimizing order to a value-maximizing one. Smallest
first shortens the average wait for *any* result; most-recent first shortens the
wait for the result someone actually wants, and pays for it with the head-of-line
behaviour the earlier comment was written to avoid — the same behaviour the live
probe observed. So the axis this experiment left fixed is one the other scheduler
has now moved along, deliberately and in a direction our own reasoning did not
consider. #6012 remains an eager scheduler over the same extraction stage,
arrived at independently; two eager schedulers over one serial worker is the
situation the concurrency section below is about.

It is eager by the same mechanisms, and these were re-read at `4427be9a` rather
than carried forward. Indexing resumes five seconds
after startup whenever a model is selected and indexing is not paused; item add
and modify notifications enqueue behind a three-second debounce; and
`startIndexing()` re-enqueues every eligible item in every library. No query
path starts an indexing run. What differs is the demand boundary, and that is
the whole of the difference between the two schedulers: #6012's eagerness begins
once semantic search is enabled with a model selected, and its attachments
become eligible only while `embeddings.indexFulltext` is on, whereas the
sitter's begins before either — which is what preparing "without enabling
semantic search" means above. Extraction in #6012 is therefore eager
derivatively, pulled by an embedding pipeline that is itself eager; the sitter's
is eager in its own right.

The two also converge on how an eager run stops, which is worth recording
because it shows the shape is the host's and not our preference. #6012's
consumer threads a `shouldStop` predicate through its passes and checks it
*before* each `Zotero.SDT.ensure()` call, so a document already handed to the
extractor finishes; `stopIndexing()` clears both queues and the pending kick
timer around it. That is the same graceful stop the sitter implements and the
author ratified for it on 2026-09-05 — stop admitting, let the submitted
document finish and persist its pack — arrived at independently, and for the
same reason: the generation entry point takes no abort signal, so between
documents is the only place either scheduler can stop.

What the experiment can decide is correspondingly narrow: whether whole-library
preparation runs unattended on a working machine without the user noticing it,
and at what observed rate. It is an overnight arrangement on the author's own
library, not a demonstration of foreground non-interference; the
[launch report](../../verification/SDT-SITTER-LAUNCH.md) keeps that list of
limits.

## Zotero's automatic indexing and the removed controls

Dan Stillman's ["Rework the Index Statistics preferences pane" commit](https://github.com/zotero/zotero/commit/02fb0e92ed029d95240cf95bce7e407800466534)
explains why Zotero removed Rebuild Index and Clear Index. Rebuilding marked
full-text content unsynced, causing uploads, server reindexing and downloads on
other devices. Automatic indexing and targeted reindexing were intended to
cover the useful cases, including re-extracting affected items after a length
limit increases. Clearing deleted both the local index and extracted-text
caches. The replacement displays progress and actively processes pending
indexing work while the statistics pane is open.

That pane's "up to date" describes its pending queues: partially indexed items
can already count as indexed, and unavailable files remain separately reported.
It therefore does not establish complete extraction of every document. The
sitter's contribution is independently preparing native structured-text packs
and making their coverage understandable. The missing bulk button alone is
not evidence that Zotero lacks automatic full-text indexing.

## What the removed controls did not replace: a concurrency model

That rationale is about sync amplification and about targeted reindexing
covering the useful cases, and nothing here disputes either. The observation is
a different one, and it is what this plugin kept running into: bulk indexing did
not leave with the buttons. It moved into automatic paths, and the questions the
buttons used to answer explicitly moved with it — who may run bulk work, when,
against what budget, and what yields to what. Those questions have answers
today, but the answers are implicit in code rather than stated, and a plugin
cannot read an implicit answer.

Building against it from outside looks like this. There is no public read-only
status for structured-text extraction: `getPack` can regenerate in the
background, `getReader` calls it, and `ensure` reduces a failure to a boolean,
so none of the three serves as a passive census or as an admission preflight
that promises not to start work. Neither is there a public predicate for "the
extractor is busy", so the sitter's politeness gate reads two private fields on
the shared worker and fails closed when they are absent — a plugin depending on
internals in order to stay out of the way, which is the opposite of what an
internal should be load-bearing for. The worker itself is a singleton with a
serial queue that awaits each task before taking the next; its error event only
logs, so a crash can strand an awaited job; and per-item deduplication means a
later priority consumer joins an already queued generation rather than upgrading
it. The sitter neither cancels nor isolates that worker, and does not try to
([prerequisites](../../verification/SDT-PLUGIN-PREREQUISITES.md),
[queue reading](../../verification/SDT-PARALLELISM-0674.md)).

This matters more now than when the buttons went, because the index has stopped
being a cheap byproduct of text stripping. Over the same source bytes there are
now the flat text and its lexical tables, the structured-document-text packs
produced by an ONNX segmentation pipeline, and, in the draft semantic-search
work, embeddings — each with model inference somewhere in its build path, and
each carrying its own locally reasonable politeness constant. #6012 halves the
runtime's recommended thread count; it orders attachments by how recently the
user touched them; the sitter reads memory, load and disk before every
admission. Three consumers, three private policies, one serial worker, and no
shared budget any of them can see.

The halving is still there and is no longer unconditional, which sharpens the
point rather than blunting it. At `19e7962` it was one expression with a comment
attached — "trade wall time for heat and leave the rest of the machine to the
user"
([inference-boundary review](../../verification/BRIDGE-0496.md), pinned at that
head). At `4427be9a` it has become a named function,
`Zotero.Embeddings.Indexing.getEngineThreads()`, whose halving a set of *thread
boosts* can lift — among them `user-idle`, so the politeness is withdrawn
precisely when nobody is at the machine. The quoted comment is gone from the
source. A constant became a policy with inputs, and none of those inputs is
visible to another consumer either.

The memory floors show it most sharply, and they are unchanged between the two
heads. The embedding indexer declines to start a pass below 1,5 GiB available
and retries five minutes later with its queue untouched; the sitter refuses
admission below 4 GiB. Two components read the same meter on the same machine,
disagree by more than a factor of two about what "enough" is, and neither can
see the other's answer. They also disagree about the unreadable case, in
opposite directions: where the platform cannot report available memory the read
returns 0 and the check treats it as room to proceed, while the sitter refuses
to admit. (That read has moved from a private `_availableMemory()` at `19e7962`
to a public `Zotero.Embeddings.Diagnostics.getAvailableMemory()` at `4427be9a`;
it still returns 0 on the unreadable case, and the check still reads 0 as room.)
Neither default is wrong on its own terms — one protects progress, the other
protects the machine — and that is exactly the point: they are answers to a
question no document poses, so nothing makes them agree. One mechanism there is
better than ours and worth saying so: under memory pressure #6012 halves its
token budget down to a floor and shuts the engine down alongside, restoring both
when the pressure lifts, so it keeps making progress where the sitter simply
waits.

Since `19e7962` it has added a second memory mechanism of a kind the sitter has
no equivalent for: a cap on the *inference process's own footprint*, above which
the engine is restarted between batches. That is a plugin admitting its
long-running arena does not shrink and treating a restart as the only reclaim —
a fourth private constant on the same machine, and the one that would be hardest
for an outside consumer to anticipate, because it is about a process nobody else
can see.

Per-document cost has moved in the same direction. On our own harness a document
set totalling **849 pages** extracted in 16,54 s in one process and in 4,49 s
across twelve, a 3,69× gain, while raising ONNX intra-op threads inside one
process did not improve total time. That measurement uses native ONNX in
independent Node processes rather than Zotero's WASM worker, so it bounds
nothing inside Zotero; it is quoted only to say which axis paid. Document-level
parallelism is the axis a singleton serial queue cannot use by construction. A
bounded extraction-worker pool is a candidate patch, not one this experiment has
measured, and any such change would have to preserve interactive priority,
per-item deduplication, error routing and resource limits
([parallelism pilot](../../verification/SDT-PARALLELISM-0674.md)).

The same split runs through the stop controls, and this one bears on a
requirement of ours. R22 asks for one obvious way to stop all background work.
#6012 has a real one for its own indexer: `embeddings.indexingPaused` is a
persisted preference, so a stop survives a restart, and while it is set nothing
is indexed at all — item changes are not even enqueued — until `startIndexing()`
clears it and re-enqueues, cheaply, since already-indexed items are skipped by
source hash. It carries a second, finer control besides: turning
`embeddings.indexFulltext` off keeps metadata indexing running while dropping
attachment work and pruning its chunks.

The sitter's control used to be the same kind of object, persisted the same way.
Since ticket 0797 it is not, and the difference is worth stating because it is a
different answer to the same requirement. The sitter's "Pause indexing" checkbox
is session-scoped and remembers nothing; R22's durable clause is answered by
Zotero's own add-on disable, which the host already stores. So where #6012 grew
a preference of its own to hold a stop across a restart, the sitter declined to,
on the ground that the host was already holding one. Neither design is wrong for
its component; they are two readings of whose job a durable stop is.

Neither control is a stop for work already submitted, and that is a platform
fact rather than a choice either of them made: open question 4 below records
that a submitted extraction cannot be ended from this side at all, and that from
here a slow tail and a wedged worker leave the same journal. Ticket 0797 is the
second consumer of that answer. The checkbox ends admissions and cannot end the
document under way, so the line beside a checked box says exactly that and
points the reader at the host's add-on disable — it promises no stop the plugin
cannot perform, which is the one thing the wording had to get right.

What the split costs is unchanged, and is worse for having two shapes: the two
controls cannot see each other, each stops its own consumer and nothing else,
and extraction that a reader or the other consumer triggers continues either
way. There is no way for a user, or for either component, to say "stop indexing
on this machine" — which is the R22 question asked of the platform rather than
of one plugin, and the answer to it is currently a list of switches a user has
to know to find, now in two idioms rather than one.

The model is also not local, and the removal rationale is itself the proof:
marking full-text content unsynced caused uploads, server reindexing and
downloads on other devices, so indexing state was a distributed concern already
in the lexical era. Larger derived artifacts make the same question harder —
what syncs, what is rebuilt per device, and which device pays.

The sitter added a fifth constant of its own on 2026-09-15, and it is the one
that marks where the shared-budget question stops. `SDT_DRAIN_BUDGET_MS = 5000`
(`scheduler.js`) caps how long one pass of the notification drain may hold the
pump before the candidate search below it gets a turn. Before it, that loop ran
to an empty set and paid a library-wide unattached-items query per id, so a bulk
file sync — which fires notifications faster than the query returns — held
control below it indefinitely: the backlog went 761 to 6 573 in twenty minutes
on the author's library and `active` stayed null
(`verification/incidents/0795-2026-09-15-drain-during-sync.md`), and both sweep
records read `completed: 0` while the window showed a plausible busy sitter
(`verification/incidents/0796-2026-09-15-toggle-does-not-recover.md`, which also
records that forcing the outer loop round by hand does not recover it). Ticket
0796.

It is deliberately not a candidate for any shared budget, and that is the answer
to question 6 below that we can give from inside. The four constants above
ration a *machine* — memory, threads, the inference process's own footprint —
and a machine-wide arbiter could in principle set all of them, which is what
makes their disagreement a defect rather than a difference. This one rations
this scheduler's control flow between two stretches of its own work. No other
consumer could read the number and act on it, so sharing it would buy nothing
and hide where it belongs. The test for which kind a constant is: whether
anything outside the component could have an opinion about its value.

Its value is chosen against a different neighbour entirely. Wall clock rather
than a count of ids, because what it bounds is work whose cost does not scale
with the backlog, and the same count is a different duration on a library of 700
and one of 10 000. Five seconds, an order of magnitude under `bootstrap.js`'s
60 s heartbeat, so no drain pass can span a heartbeat: a stretch of work no
periodic record could see the inside of was the whole visibility failure in the
incident. The number is a cadence knob and not a correctness gate — any positive
budget restores the property, because what admission needs is control reaching
the end of the loop, not `dirty` being empty.

Ticket 0810 removed the per-id library-wide query the budget was first measured
against, and left the budget where it is. The no-attachment view is now held as
a map by itemID between censuses: a drain pass re-reads `numFileAttachments()`
for the records its events actually named and the old and new parents of every
attachment they touched, coalesced into one `refreshUnattached()` call per pass,
so the cost scales with the distinct affected records rather than with the
library size times the dirty-id count. The full walk stays where it was correct
— the initial census and the hourly reconciliation — and one further
reconciliation is requested, never a targeted re-walk, when an event names an id
that is gone and that nothing in this module ever placed under a parent. That is
the only case a targeted refresh cannot answer, and a full census is already the
mechanism for it.

This does not make the budget redundant. What a drain pass now pays per id is an
inspection — a `getAsync`, a stat, possibly an MD5 — which a bulk file sync
still produces faster than the loop retires it, so the starvation guard 0796
added is answering a different question from the cost 0810 removed. The
wall-clock choice survives for the same reason: an inspection's duration is a
property of the file, not of the backlog.

The questions we could not answer from outside, in the order they cost us most:

1. Is there a read-only way to observe extraction work — queued, active,
   progress — that does not itself start work?
2. With no preferences pane open, what drives pending indexing, and is that
   ownership meant to be stable?
3. Is background indexing expected to yield to interactive work, and by which
   mechanism? Priority orders waiting jobs only.
4. Is submitted extraction meant to become cancellable? Still open, and ticket
   0793 sharpened rather than settled it: on 2026-09-15 a 3 949-page document
   held progress at 90 for at least 173 s with the sitter's heartbeat still
   firing, and from this side a slow tail and a wedged worker leave the same
   journal. `bench/sdt_stall_probe.py` now separates the two — but only with a
   per-thread CPU sample taken from OUTSIDE the process, which is itself the
   answer to question 1 in miniature: the observation exists, and not through
   any interface the platform offers. Until a submitted call can be cancelled,
   the sitter cannot bound `ensure()`; the only move available to it is to
   announce the plateau, which is what 0793's exit criteria were corrected to
   say.

   **The platform half is now settled, against the shipped 10.0.2**
   (`~/.local/Zotero_linux-x86_64/app/omni.ja`, BuildID 20260909184950), read
   on 2026-09-16. No affordance exists, and the obvious workaround is worse
   than doing nothing.

   `Zotero.SDT.ensure()`'s whole option surface is `isPriority` and
   `onProgress`; `setTimeout`, `Promise.race`, `AbortController` and
   `AbortSignal` appear zero times in `sdt.js` and `pdfWorker/manager.js`. The
   worker's dispatcher accepts twelve actions and none of them cancels. The
   `isPriority` note above is confirmed rather than assumed: `_processQueue`
   has already shifted the running item off `_queue` before awaiting it, so
   priority can only reorder jobs that have not started. And extraction runs
   inside the worker's single `self.onmessage`, with the block-seg ONNX models
   executing as WASM on that same thread because `manager.js` never sets
   `nativeONNX` — so a cancel message could not be dequeued by the thread that
   would have to act on it, even if one existed.

   `Zotero.PDFWorker._worker.terminate()` IS reachable — plugins get a
   system-principal sandbox with `Worker` injected, and `PDFWorker` is a plain
   instance with plain underscore fields. It must not be used. The parked
   promise settles only from the `message` listener (the `error` listener just
   logs), so it never settles; `_processingQueue` therefore never returns to
   `false`, and the queue never drains again for the life of the process —
   the same queue full-text indexing, annotation import and the recognizer all
   share. One stuck job becomes a stuck queue. The cache is safe either way:
   the pack is written atomically in the parent, after the bytes return.

   There is no watchdog anywhere in the worker path. `fulltext.js`'s stall
   detector (three non-decreasing passes, 1 s apart) watches database queue
   counts and sits one frame above a hang it cannot observe: its `maxTime` is a
   slice budget checked BETWEEN items, never evaluated if the worker hangs
   under the await, which also strands `_indexingInProgress` at true.

   The strongest evidence that this is an omission rather than a design is at
   `pdfWorker/manager.js`, where upstream wrote worker recycling at the right
   hook point and shipped it commented out: `this._processingQueue = false;`
   followed by `// this._worker.terminate();` and `// this._worker = null;`.

   So detection is supported and intervention is not: `onProgress` is strictly
   monotonic, so "stopped progressing" is measurable to the tick, with nothing
   to do about it. **What an upstream request would have to ask for**, in one
   sentence: an abort signal threaded from `ensure()` through `_enqueue`/
   `_query` into the worker's extraction loop, plus a supervisor that on abort,
   worker error or a per-job deadline rejects every parked promise, resets
   `_processingQueue` and recycles the worker — that is, uncomment those two
   lines and give the recycle a policy. Not filed: the author owns anything
   sent upstream in his name, and 0793's run decides whether the case is a
   wedge at all.

   One thing the source read could NOT settle: whether Gecko's `terminate()`
   preempts a worker blocked inside a long synchronous WASM call, or only takes
   effect at the next interrupt point. That is a platform question and needs an
   experiment, not more reading.
5. Is the singleton serial worker meant to stay one as per-document cost rises,
   and if a bounded pool were considered, which invariants would it have to keep?
6. Should the several indexing consumers share one resource budget rather than
   each carrying its own constant? Half-answered above, and only for our side:
   what meters a machine should be shared, what paces a loop's own internals
   should not, and `SDT_DRAIN_BUDGET_MS` is the second kind. The half addressed
   to the platform stays open — nothing the sitter can read exposes a budget to
   join, so the memory floors still disagree by more than a factor of two with
   no way for either side to learn it.

These are questions rather than requests, and they are not an argument for
restoring the removed buttons. The narrower claim is that an eager third-party
scheduler is a stress test of an implicit concurrency model, and this one found
the model expressible only through private fields and per-call-site constants.

## Why preparation ahead of demand matters

Time until useful attachment-content results matters alongside query latency.
Zotero's draft [semantic-search PR #6012](https://github.com/zotero/zotero/pull/6012)
already separates extraction from attachment embedding. At head `19e7962`,
checked 2026-09-08, its indexing loop embeds item metadata first, then finishes
the queued attachments' extraction pass before starting their embedding pass.
On an initially unindexed library, a long extraction backlog therefore delays
the first attachment-content semantic results, even for documents whose packs
are already ready. This is an implementation reading, not a measured duration;
see the pinned [indexing source](https://github.com/zotero/zotero/blob/19e79625b1c6fbbdd75367aa85b62d5a7080d7f6/chrome/content/zotero/xpcom/embeddings.js).
Re-read at `4427be9a` on 2026-09-12: the barrier holds, and the newer head is
more explicit about it — attachments are enqueued after metadata because they
are "an order of magnitude more to index".

The search request itself does not ordinarily wait for the whole indexing run:
it can use available embeddings, and hybrid search falls back to lexical ranking
when the semantic index is not ready. Early replies can therefore precede useful
semantic coverage of attachment content; see the pinned
[search source](https://github.com/zotero/zotero/blob/19e79625b1c6fbbdd75367aa85b62d5a7080d7f6/chrome/content/zotero/xpcom/bestMatch.js).

The sitter's contribution is to make extraction independently available ahead
of that demand. With current packs already prepared, a consumer can proceed to
chunking and embedding without paying for their extraction then. Embedding still
takes time, and installing the sitter only when semantic search is first wanted
does not remove the initial extraction cost. Independent preparation is not a
claim that the sitter builds a progressively searchable index or that its
scheduler is better overall than #6012's.

Stage separation is not the same thing as that barrier, and the two are easy to
conflate. Separating extraction from chunking and embedding pays for itself
inside a single pipeline, before any second consumer exists: the stages have
large disjoint working sets, and #6012 shuts its inference engine down at the
start of its extraction pass for exactly that reason, downloading the model
without instantiating it so that it is not resident while documents are
extracted. The separation also gives the two artifacts their own invalidation
lifetimes — a model switch wipes every stored vector and leaves packs untouched
— their own failure classes, durable for extraction and transient for
embedding, and their own resource shapes, since extraction parallelises across
documents while embedding is batch- and memory-bound. What a whole-backlog
barrier costs is therefore chargeable to running the stages at library
granularity, not to separating them: a consumer that pipelines over ready packs
keeps every one of those properties and regains progressive coverage. The sitter
is not that consumer and does not decide its schedule. It makes the packs
available early enough for the choice to exist.

## GPU embedding and runtime independence

Independent packs also let extraction stay with Zotero while an external
embedding service uses a verified GPU-capable runtime. This is an advantage of
the wider pipeline, not a GPU feature shipped by the sitter. The existing
[inference-boundary review](../../verification/BRIDGE-0496.md) establishes the
limit at the same #6012 head: Zotero's embedding caller selects no GPU device
or execution provider. Its inference already runs outside the UI process;
the useful separation is from Zotero's bundled runtime and its exposed options,
not merely from the UI thread. This does not establish that Gecko could never
support GPU inference.

The review also identifies an outbound passage-embedding hook in #6012, so
Zotero could itself consume a compatible external service. Queries still embed
locally through that implementation. Our existing service work (tickets 0491 and
0575) is the reuse path; device usability and compatibility between query and
passage vectors must be verified before claiming GPU benefit.

That description was accurate at `19e7962` and now understates what is there.
Re-read at `4427be9a` on 2026-09-12, the hook has become a subsystem of its own:
`Zotero.Embeddings.Endpoint`, with an active-endpoint resolver, failure and
success recording, a recheck, a reported status — and a **sentinel-vector
check**, which embeds a known passage through the endpoint and compares the
answer, so a service that returns plausible numbers without actually serving
embeddings is caught before a batch of vectors is stored against it. There is a
preferences pane for it,
`chrome/content/zotero/preferences/embeddingsEndpoint.xhtml`, so it is a
user-facing setting rather than an internal seam. The GPU limit above is
unchanged — `embeddings.js` still selects no device and no execution provider at
either head — but the assumption that an external embedding service would be
ours to design is not: the compatibility contract that work has to meet now
exists upstream, and the sentinel check is the part to meet first.
