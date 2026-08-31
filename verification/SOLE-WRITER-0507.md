# The sole-writer conductor — proposal, and its review against the sheet

**What this is.** A proposal and its review, not authority. `spec/DESIGN.md`
remains the record of the design; ratification is `spec/DECISIONS.md`'s, where
the question is filed. This report is ticket 0507's artifact and is cited by
path from it. Nothing below sets a number: where the proposal meets one, it
points at the document that owns it.

**Where it came from.** The author's own sketch — a one-minute ticker that
refreshes the work queue and manages deletions, an embedder that drains it, and
a query embedder — reviewed against the ratified four-role topology
(`DECISIONS.md`, 2026-08-30), against upstream zoteus at the reviewed baseline,
and against Zotero's draft pull request #6012 read at source. Two of the
author's amendments shape it: the query embedder stays in-process, and the
conductor, not the worker, does the writing.

---

## Part 1 — the design

### The shape

Unchanged from the ratified topology: N × P0, one query-serving zoteus per MCP
client on one data directory, exactly one of them the *conductor*, elected
through the lease row `DESIGN.md` §2.5 owns. Query embedding is in-process in
every P0, behind the transport-neutral interface, as §2.5 already says.

What changes is the division of labour behind the conductor. Instead of three
worker kinds that each open the store and commit their own stage's rows, there
is **one pipeline worker that writes nothing** and a **conductor that writes
everything**. Five clauses state it.

### W1 — the conductor is the only writer

Every durable artifact — ledger rows, slabs, the FTS tables, the vector sidecar
— is written by the conductor process and by nothing else. Every other process
in the system is a reader: the sibling P0s serve queries as WAL readers on a
write-free path, exactly as today, and the pipeline worker holds no handle on
the store at all.

The gain is not contention, which the lease already bounded. It is that the
sidecar and the ledger stop being two artifacts with two writers that have to be
kept agreeing. Today §2.5 gives the sidecar its own writer and its own
generation-stamp-and-verify protocol to keep it consistent with rows another
process wrote. One writer makes the commit a single ordering decision: append
the vector bytes, fsync, commit the row that references them. A crash between
the two leaves bytes nothing points at, which is the safe direction — the same
dead weight the compaction rule already collects.

### W2 — the worker is pure

The worker receives a work order naming an item or attachment and the keys its
inputs were seen at. It then does all of the expensive, unbounded and
crash-prone work: it fetches the extracted text from Zotero's local API,
segments it, chunks it, embeds the chunks, and streams the results back over its
pipe. It opens no database, holds no lease of its own, and owns no file.

Two consequences worth stating as properties rather than hopes. C3's
"killable/restartable at any time with zero index damage" becomes structural: a
process that holds no durable state cannot damage any. And the second orphan
repair §2.5 mandates — re-verifying `leases.holder` between micro-batches —
becomes unnecessary for this worker: an orphaned worker whose parent died can
only produce records into a closed pipe. Exit on stdin EOF remains, as
hygiene rather than as a correctness measure.

The worker is also where every unbounded allocation now lives: the whole-document
fetch, the segmentation of a 44,9 MB dictionary, the model. The conductor never
holds a document.

### W3 — streaming order: chunk rows ahead of vectors

The worker streams each item's chunk records as it produces them, and its
vectors behind them. The conductor commits in that order.

This is what keeps the ledger a stage boundary rather than a process boundary.
§2.5's "the ledger's keyed, idempotent derivations — not an in-memory pipe — are
the boundary between stages" was load-bearing for a reason: the boundary decides
where work resumes. Collapse chunk and embed into one worker with no streaming
and a death mid-document loses every chunk computed for it, which on a
15 000-page PDF is a redo measured in hours. Streaming makes the boundary a
*write ordering* instead, and resumability stays at the chunk.

It also delivers, without a third process, the first of the two justifications
the author's structural hint gives for asynchronous stages (`CONSTRAINTS.md`, the
standing instruction): keyword availability never waits on embedding, because
the chunk rows that feed the keyword index are committed before the vectors that
did not yet exist.

### W4 — the commit guard

Immediately before writing a streamed record, the conductor checks two things:
that it still holds the conductor lease, and that the key the record was computed
under still equals the current key for that row. On either mismatch the record is
discarded and nothing is written.

"One writer" is a property of the topology, not an invariant the substrate
enforces: during a handover two P0s can each believe they are conductor. The
guard is what makes R13's letter hold — never committed twice — and it is
cheaper here than in the ratified design, being a local comparison inside the one
process that writes rather than a cross-process claim protocol.

### W5 — the batch is the memory dial

The worker packs each engine call to a token budget rather than to a count,
sorting by length inside a window before packing, because the runtime pads every
member of a batch to the longest sequence in it. Batch size is then a memory and
latency dial, not a throughput lever: it is what the pipeline peak scales with,
it is the unit R13's duplicate-compute bound is stated in, and it is the grain at
which the worker yields to foreground work and at which a death loses progress.

Zotero #6012 packs this way (a token budget with an item cap, and a window sorted
by length); upstream zoteus batches by item count alone. Our own GPU sweeps
(`verification/GPU-ANOMALY-0481.md`, `verification/GPU-CORRECTED-0482.md`) show
per-passage cost flat-to-worse as the batch grows, and roughly doubling for one
candidate — so nothing here is bought by making the batch large. The deployed
path is CPU and has never been swept; ticket 0500 owns the measurement.

### The tick decides and does not fetch

The reconcile tick keeps every duty §2.4 gives it — the items delta scoped by
server identity, the full-text census diffed by equality, the deletion
subtraction every tick — and gains one prohibition: **no document fetch happens
inside the tick.** The whole-document GET has no micro-batch boundary inside it,
and a tick that performs one is a tick that does not run for as long as the
document takes, which is where R35's minute goes. The tick writes work orders;
the worker fetches.

### What Zotero's extraction leaves us

Zotero extracts the file; we never do. What remains of the extract stage is
bookkeeping, and all of it is writing, so all of it is the conductor's: the item
cursor, the census diff, extractor-version staleness, the per-attachment
truncation flags, the version-0 residue and the content-presence probe that marks
passages `cache-lost`. The one part that is reading — the whole-document GET —
moves into the worker under W2. The stage keeps its key (`text_hash`, §2.1) and
its terminal states; only the fetch moves.

### Fairness moves inside the conductor

`CONSTRAINTS.md` C3's "foreground always beats background" is implemented today
across processes: workers stat the `activity` file between micro-batches and idle
while it is fresh. Put every durable write in the conductor and the rule has to
apply to the conductor's own write loop as well, since the process serving
queries is now also the process draining the stream. The fsync is not the hazard
— it is off-thread — but the serialization of a long run of records is on it.
The write loop checks `activity` between micro-batches, exactly as a worker does.

### Failure attribution

A worker that dies takes its in-flight batch with it and nothing else. The
conductor attributes the failure to the last work order it dispatched and the
last record it received, which is a sharper attribution than the ratified design
gets from a worker that died mid-transaction. Quarantine, bisection and the
transient/persistent split are unchanged.

---

## Part 2 — what it would change in the documents

| document | what it says now | what the proposal needs |
|---|---|---|
| `DESIGN.md` §2.5 | the conductor's single embed worker alone writes the sidecar | the conductor alone writes, both artifacts |
| `DESIGN.md` §2.5 | the ledger, not an in-memory pipe, is the boundary between stages | the boundary survives as a write ordering; W3 states how |
| `DESIGN.md` §2.5 | one run-to-drain worker of each of three kinds | one pipeline worker; the stages remain, the processes do not |
| `DESIGN.md` §2.5 | two orphan repairs per worker kind | stdin EOF only; the lease re-check has no subject in a worker that writes nothing |
| `DESIGN.md` §2.4 | the tick schedules the extract shim | the tick dispatches work orders and fetches nothing |
| `DESIGN.md` §2.9 | extract, chunk and embed add transient residency | one worker's residency, and see finding F1 |
| `CONSTRAINTS.md` C4 | status answers while all three queues run | unchanged: the queues are ledger queues, not processes |
| `TERMINOLOGY.md` | *P0 / pipeline workers*: one worker of each pipeline kind | one pipeline worker; *the ledger* entry unaffected |

---

## Part 3 — review against the sheet

Verdicts: **held** (the proposal keeps the promise by the same mechanism or a
better one), **held with a clause** (kept only because of something the proposal
must state, named here), **at risk** (a finding below).

### Where the topology bites

**R35, discovery — held with a clause.** The minute is the tick's cadence, and
the clause is the prohibition above: no fetch inside the tick. With it, the worst
case remains one full tick for a change and one for a deletion. Without it, a
single large document silently suspends discovery for everything, and no counter
shows it. The deletion half is strengthened rather than merely preserved: see
R15.

**R15, deletion — held, and strengthened.** The promise reaches "the queues
between the stages", which is where text survives a deletion and comes back.
Under W1 no queue between stages holds text at all: the durable queue is ledger
rows written by one process, and the only text in flight lives in the worker's
memory and behind the commit guard. A deletion landing while a document is being
chunked cannot reach the store, because W4 rejects at commit every record whose
row is gone. The slab write and the row that references it are one transaction,
so removing an item removes both.

**R13, concurrency — held.** No passage is committed twice, by W4 rather than by
the singleton. Duplicate compute is bounded at one batch per failover, W5's
batch. The claim that only one process writes is not what carries the promise,
which is as it should be: the guard carries it, and the topology only makes the
guard cheap.

**R4, availability — held.** Partial answers ship from the first passage
committed, and W3 makes that earlier than the ratified design does: chunk rows
reach the keyword index without waiting for the vectors of the same document.

**R22, pause — held, and simplified.** The durable pause row is read by the one
process that dispatches work. Pausing stops dispatch; the worker exits on EOF;
nothing else in the system is capable of doing background work. One switch, one
enforcement point, and it holds across a restart because it is a row.

**R17, reporting — held.** Counters are ledger rows, written by the conductor and
read by status, so C4's "never by scanning a table a stage is writing" is easier
to keep than before: there is one writer to be behind. "Which input triggered
it" comes free, since every streamed record carries the work order it answers.

**R3, proportionality — held.** Untouched: the signal/key split does this work
and the proposal moves no key.

**R8, scale — held, and this is the point of W2.** Neither the 44,9 MB
dictionary nor a 15 000-page PDF ever enters a query-serving process. The
unbounded allocation is in the killable worker, which is what C3 asks for.

**R10, locality — held, with one documentation consequence.** No new network
surface: the worker speaks to the local API only, and the model download is the
same named exception. But the process that talks to Zotero is no longer the
process that answers the user, so `SECURITY.md`'s data-flow description names
the wrong process once the proposal lands.

**R31, validation — held with a clause.** The model now loads in the worker, so
local validation happens where the model runs. The handshake §2.5 requires —
requested and actual fingerprint, dimension, runtime, execution provider,
validation standing — must cross the pipe with the first record, and the
conductor must reject a mismatch before writing a vector. Stated, it is the same
promise; unstated, the validation is performed in a process whose result nothing
checks.

**R6, latency — at risk; see F2.**

**R32, buildtime — held, on an assumption.** The proposal adds one serialization
hop per batch to a per-passage budget stated in tens of milliseconds. The hop is
negligible against it by arithmetic, not by measurement; ticket 0500 is where the
number would come from.

**R16, notes — unaffected, on a path worth naming.** Notes and annotations are
child items whose text comes from Zotero's item API rather than from the
full-text cache, so the worker fetches them by a different route than a PDF's
body. Nothing in the proposal distinguishes the two: a work order names an input
and the worker fetches whatever that input is. The clause matters only because
the phase that indexes own words is the one upstream does not have at all.

**R23, migration; R12, libraries; R5, R18, R24, R33, R34, R19, R7, R29, R1 —
unaffected.** These are query-path, schema or coverage-order promises, and the
proposal moves no ranking, no schema and no priority. R1's class order and the
two-band frontier are §2.3's and are untouched: the proposal changes who writes,
not what is worked first.

### Constraints

**C1 — held.** Keys and signals are unchanged; the worker computes hashes and
the conductor stores them.

**C2 — held, and slightly better.** The stages remain swappable adapters
identified by their keys. A worker that writes nothing is a smaller thing to
replace than one that owns a transaction.

**C3 — held on scheduling, at risk on memory.** One core, low priority,
foreground-beats-background: held, with the fairness clause moved inside the
conductor. The killable-worker bullet is strengthened. The pipeline peak is F1.

**C4 — held.** Status answers from counters, and the queue count in its sentence
is about ledger queues rather than processes, so collapsing two worker kinds into
one process does not touch it.

**The author's structural hint — honoured in substance.** Three asynchronous
stages, independently paced, with queues between them: the queues are ledger
queues and the pacing is the conductor's. Justification (a), keyword
availability never waiting on embedding, is delivered by W3. Justification (b),
a process that can be nice'd, observed and restarted, is delivered by the worker
— and the proposal makes it *more* restartable, not less.

---

## Part 4 — findings

**F1. The pipeline peak and the multilingual model collide, and the proposal
makes the collision concrete.** C3's ratified pipeline ceiling was set in 2026-08
against an English-embedder picture. The 2026-08-30 ruling that re-pinned the
*server* ceiling on the candidate measurements says in as many words that the
pipeline peak is a separate budget and untouched — but the recommended
candidate's measured fresh-process residency (`DECISIONS.md`, 2026-08-30, from
`bench/results/0263-cpu-arm/SUMMARY.json`) is already above that pipeline
ceiling, and every multilingual candidate's 8-bit rung sits in the same region.
Merging chunking into the same process adds a section batch on top of it. This
is not created by the proposal — a ratified embed worker running a ratified
multilingual model has the same problem today — but the proposal is the first
document that has to state a single number for a single process, so it surfaces
it. **Needs a ruling**: either the pipeline ceiling is re-pinned on the same
measurements that re-pinned the server one, or chunking goes back into its own
process and the ceiling covers the smaller of the two. The measurement exists;
what is missing is the ruling.

**F2. The conductor now serves queries and performs every write, and nothing
measures what that does to R6.** In the ratified design the write-free query path
is a property of every P0 including the conductor, because the writing happens in
worker processes. Under W1 one P0 writes continuously during a build while
answering queries against the 700 ms preference and the 3 s bound. The fairness
clause above is the intended remedy and is untested. **Instrument**: a soak
measurement of query latency on the conductor during a full build, against the
same budget §2.9 states — the shape of the RSS and soak gates ticket 0026 owns.
If it fails, the fallback is not to abandon W1 but to make the writer a
dedicated small process that owns the store, at the cost of the third process the
proposal removes.

**F3. The batch size on the deployed path is unmeasured.** W5 makes the batch the
memory dial, the duplicate-compute unit and the yield grain, and every sweep we
have is GPU. A CPU sweep at the deployed rung would settle all three at once
(ticket 0500).

**F4. The item census cost sits on the tick's critical path and is unmeasured.**
Independent of this proposal, but the proposal concentrates the tick's duties in
one process, so it inherits the exposure whole. Ticket 0503 owns it.

---

## What this proposal does not decide

It does not touch ranking, chunk geometry, the entry ruling, the coverage order
or any threshold. It does not decide whether the embedding path later becomes a
local endpoint — that is ticket 0491's, and W2 is compatible with either answer,
since a pure worker is already the shape an endpoint client takes. It does not
re-open the query embedder's location: in-process, per the author.
