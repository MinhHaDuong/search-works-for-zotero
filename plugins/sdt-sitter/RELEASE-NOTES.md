# SDT pack sitter — release notes draft

Keep Zotero's structured-text caches ready, and make their state understandable.

The sitter's contribution is:

- **Observability:** see cache coverage, the active document, progress, reasons
  for waiting, failures and qualified completion estimates.
- **Insurance against missed changes:** reconcile cache state with local files
  to discover missing or stale packs and unavailable or restored attachments.
- **Independent preparation:** prepare native structured-text packs without
  opening each attachment or enabling semantic search, so extraction can be
  paid for before the first demand for semantic results.
- **Cautious scheduling:** check resources and native worker availability before
  submitting extraction work.

The sitter uses Zotero's own extractor. It does not improve extraction quality,
build a search index or isolate a stuck native worker. Coverage describes the
last observed state; preparation depends on local files, available resources
and successful native extraction.

Installing the sitter causes one outbound request, and the plugin is not what
makes it. `manifest.json` declares an update manifest served from this
repository's `main` branch on `raw.githubusercontent.com`, and Zotero's own
add-on update check fetches it on the host's cadence — `extensions.update.interval`,
86 400 seconds, or once a day, as read on the author's profile — for as long as
the add-on stays installed. That check is not optional: ticket 0727 established
with a control that a build identical but for the removal of `update_url` is
refused at install ("peut-etre incompatible avec cette version de Zotero"), so
an add-on that declares none cannot be installed at all. The request is for a
fixed URL: nothing about the library is sent, and the sitter opens no network
connection of its own, here or anywhere else. What the fetch necessarily
discloses to the other end is the requesting address and that this add-on's
manifest is being checked; whether the host adds the installed version to the
check has not been read here. The surface is recorded with the others in
[SPEC.md §6](../../SPEC.md#6-security-considerations).

## Prepared for the next release

Tickets [0760](../../tickets/0760-text-less-scanned-pdfs-silently-count-as.erg)
and [0744](../../tickets/0744-group-unsupported-and-refused-documents.erg)
make the distinction between a native pack that contains verified text and one
that has been completely inspected but contains none. The latter is not
admitted again and is not counted as indexed. The Details layer now groups
observed obstacles, including unavailable files, unsupported formats, session
failures and bibliographic records without a file attachment. It uses safe
error classes and identifiers; it does not display filesystem paths or raw host
errors.

Ticket [0752](../../tickets/closed/0752-make-sdt-sitter-event-driven-with-reconc.erg)
replaces frequent full-library sweeps with targeted updates from attachment and
file-download notifications. Reconciliation runs on startup and re-enabling, and
at the periodic cadence owned by
[SPEC.md §5.2.7](../../SPEC.md#527-custody-and-lifecycle).
Resource retries resume queued work without rescanning the library. The window
shows how recently reconciliation completed; disk availability remains a last
observation. Missing files stay in Zotero and their native packs are preserved.

Ticket [0686](../../tickets/0686-follow-up-sdt-sitter-panel-accessibility.erg)
adds a status region to the window for screen-reader users. It announces a
change of state — scanning, waiting for resources, an error, indexing turned
on or off — once the state it replaces has been gone for two seconds, and never
the progress figures that update several times a second. A state that comes
back inside those two seconds is not announced; one that does not is, even if
the window has moved on again since. Opening the window announces nothing.
Behaviour with an actual screen reader has not yet been verified.

The same ticket makes the window's resting sentence say which kind of rest it
is in. It used to read "Nothing to index right now" over a library that was
fully indexed and over one where every remaining attachment had been given up
on. It now distinguishes everything in view being indexed, attachments waiting
for the next pass, and a pass that finished with attachments it could not index
— the last pointing at the "Not indexed" list, where each obstacle already
carries its own explanation.

Implementation and host-mock verification are recorded in
[the scheduling report](../../verification/SDT-SITTER-EVENTS.md). This draft does
not claim a live-profile deployment or a published release.

The experimental scope and operational limitations are recorded in
[the launch report](../../verification/SDT-SITTER-LAUNCH.md).

---

The rest of these notes is written for a Zotero developer rather than for
someone installing the plugin: what this release is an experiment in, what
trying to be polite inside the platform revealed about it, and what none of it
claims. Nothing below is needed to use the sitter.

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
makes.

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
[semantic-search PR #6012](https://github.com/zotero/zotero/pull/6012) chose the
other obvious policy for the same problem.
`_getEligibleItemIDs()` orders attachments smallest first — "smallest first so
that one enormous book doesn't sit at the head of the queue while the rest of
the library waits behind it", with unrecorded sizes sorting to the end
([§5.3 of the full-text reading](../../verification/VERIFY-FULLTEXT-SQLITE.md)).
That is worth naming plainly: #6012 is itself an eager scheduler over the same
extraction stage, arrived at independently, and its own comment identifies the
head-of-line behaviour the live probe observed. Two eager schedulers over one
serial worker is the situation the concurrency section below is about.

It is eager by the same mechanisms. At `19e7962`, indexing resumes five seconds
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
runtime's recommended thread count, commenting "trade wall time for heat and
leave the rest of the machine to the user"
([inference-boundary review](../../verification/BRIDGE-0496.md)); it orders
attachments smallest first; the sitter reads memory, load and disk before every
admission. Three consumers, three private policies, one serial worker, and no
shared budget any of them can see.

The memory floors show it most sharply. At `19e7962` the embedding indexer
declines to start a pass below 1,5 GiB available and retries five minutes later
with its queue untouched; the sitter refuses admission below 4 GiB. Two
components read the same meter on the same machine, disagree by more than a
factor of two about what "enough" is, and neither can see the other's answer.
They also disagree about the unreadable case, in opposite directions: where the
platform cannot report available memory, `_availableMemory()` returns 0 and the
check treats it as room to proceed, while the sitter refuses to admit. Neither
default is wrong on its own terms — one protects progress, the other protects
the machine — and that is exactly the point: they are answers to a question no
document poses, so nothing makes them agree. One mechanism there is better than
ours and worth saying so: under memory pressure #6012 shrinks its batches and
releases the engine rather than stopping, so it keeps making progress where the
sitter simply waits.

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
attachment work and pruning its chunks. The sitter's switch is the same kind of
object, persisted the same way, and the two cannot see each other. Each stops
its own consumer and nothing else; extraction that a reader or the other
consumer triggers continues either way. There is no way for a user, or for
either component, to say "stop indexing on this machine" — which is the R22
question asked of the platform rather than of one plugin, and the answer to it
is currently a list of switches a user has to know to find.

The model is also not local, and the removal rationale is itself the proof:
marking full-text content unsynced caused uploads, server reindexing and
downloads on other devices, so indexing state was a distributed concern already
in the lexical era. Larger derived artifacts make the same question harder —
what syncs, what is rebuilt per device, and which device pays.

The questions we could not answer from outside, in the order they cost us most:

1. Is there a read-only way to observe extraction work — queued, active,
   progress — that does not itself start work?
2. With no preferences pane open, what drives pending indexing, and is that
   ownership meant to be stable?
3. Is background indexing expected to yield to interactive work, and by which
   mechanism? Priority orders waiting jobs only.
4. Is submitted extraction meant to become cancellable?
5. Is the singleton serial worker meant to stay one as per-document cost rises,
   and if a bounded pool were considered, which invariants would it have to keep?
6. Should the several indexing consumers share one resource budget rather than
   each carrying its own constant?

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

The review also identifies an existing outbound passage-embedding hook in
#6012, so Zotero could itself consume a compatible external service. Queries
still embed locally through that implementation. Our existing service work
(tickets 0491 and 0575) is the reuse path; device usability and compatibility
between query and passage vectors must be verified before claiming GPU benefit.
