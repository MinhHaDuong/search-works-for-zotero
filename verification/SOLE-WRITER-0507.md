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
and against Zotero's draft pull request #6012 read at source. Three of the
author's amendments shape it: the query embedder stays in-process, the
conductor rather than the worker does the writing, and the conductor segments —
handing the worker ranges rather than documents.

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

### W2 — the worker is pure, and it is handed ranges

The worker holds no lease, opens no write handle and owns no file. It does two
jobs, both of them contained, and it writes nothing in either.

**Fetching.** It streams one attachment's extracted text from Zotero's local API
and forwards it to the conductor in bounded windows. It does not decide
boundaries and does not accumulate: one window at a time crosses the pipe.

**Embedding.** It receives work orders and returns vectors. A work order for a
small input — a record, a note, an annotation — carries its text outright. A work
order for a large one carries **ranges**: `(slab, off_start, off_end)`, the
addresses §2.2 already gives every passage. The worker opens the store read-only,
gunzips the slab, slices, embeds, and streams the vectors back. A book therefore
crosses the pipe once as text on its way in, and never again: re-embedding after
a model change, a band-1 backfill and a resumed run all dispatch ranges over text
that is already stored.

The property to state honestly is *never a writer*, not *never a reader*: the
worker is a WAL reader like any sibling P0, which is what makes it killable at
any instant with zero index damage — C3's bullet, structural rather than argued.
It also means one of the two mandatory orphan repairs loses its subject: an
orphaned worker can only read a database and write into a closed pipe. Exit on
stdin EOF remains, as hygiene.

### W2′ — the conductor segments, and never holds a document

Segmentation is a streaming state machine over the arriving windows: it closes
entries at structural boundaries, writes each closed entry's text into a slab
(§2.2's cap and its entry-aligned cuts, unchanged), and writes the entry and
passage rows that address it. Peak memory is one window plus the segmenter's
own state — which is exactly the property C3 already asserts, that extraction and
chunking stream so peak memory is proportional to a section batch rather than to
the document.

**The clause this rests on, and it is load-bearing: the conductor must never
materialize a whole document.** The local API answers `/items/<key>/fulltext`
with one JSON object carrying the text in a `content` field
(`verification/probes/api-vs-cache-probe.py`), so `response.json()` on a 44,9 MB
attachment materializes the body and its decoded string inside the process that
also holds the query embedder and answers queries. The arithmetic, labeled
derived: §2.9's idle figure plus the recommended candidate's measured residency
already sits near C3's per-process server ceiling, and a materialized monster
document puts it over. Hence the fetch is the worker's, and it forwards windows
— the incremental decode is written once, in the process whose failure costs a
restart rather than a breached ceiling and a missed query budget.

This is why the fetch does not simply move into the conductor along with the
segmenter. The conductor gains the boundary decisions, which are cheap and
bounded; it does not gain the transport, which is neither.

### W3 — chunk rows are durable before any vector exists

Because the conductor segments and writes as the text arrives, an item's slabs,
entries and passages are committed before a single vector is computed for it.
The keyword index is complete for that item at that moment; the vectors fill in
behind.

This is the first of the two justifications the author's structural hint gives
for asynchronous stages (`CONSTRAINTS.md`, the standing instruction) — keyword
availability never waits on embedding — delivered without a third process. It
also fixes where work resumes: the ledger boundary between chunk and embed
survives as a *write ordering* rather than a process boundary, so a worker death
loses only the vectors of the ranges in flight, never the segmentation of a
15 000-page book.

It also makes the two-band frontier a dispatch policy rather than machinery:
band 0 is the first K ranges of each item, band 1 is the rest, and both are just
which range dispatches the conductor sends first. §2.3 keeps the derivation of K.

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
sorting the ranges it was handed by length before packing, because the runtime
pads every member of a batch to the longest sequence in it. Batch size is then a memory and
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
is the worker's under W2, and arrives back as windows. The stage keeps its key
(`text_hash`, §2.1) and its terminal states; the hash is computed over the
stream as it passes, so nothing has to hold the document to identify it.

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
| `DESIGN.md` §2.5 | one run-to-drain worker of each of three kinds | one pipeline worker: fetch and embed; segmentation is the conductor's |
| `DESIGN.md` §2.5 | two orphan repairs per worker kind | stdin EOF only; the lease re-check has no subject in a worker that writes nothing |
| `DESIGN.md` §2.4 | the tick schedules the extract shim | the tick dispatches work orders and fetches nothing; the conductor never materializes a document |
| `DESIGN.md` §2.2 | passages are references into slabs | unchanged, and now also the dispatch address: a work order for a large input carries ranges |
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
Under W1 no queue between stages holds text outside the store: the durable
intermediate is the slab table, which the same `WHERE lib = ?` delete sweeps, and
the only text outside it lives in one window in flight and behind the commit
guard. A range dispatch whose slab has been deleted meanwhile reads nothing; the
worker reports the input as vanished and the conductor discards it, which is a
race to tolerate rather than an error to log. A deletion landing while a document is being
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

**R8, scale — held, on the clause in W2′.** Neither the 44,9 MB dictionary nor a
15 000-page PDF is ever resident whole in any process: the worker streams it,
the conductor segments a window at a time, and the slab layer stores it in
entry-aligned pieces. What makes this a promise rather than a hope is that
nothing on the path is allowed to call for the whole body at once — which is a
property of how the fetch is written, not of the topology, and is therefore the
one thing here that a careless implementation can lose while every test still
passes. Finding F5.

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

**R32, buildtime — held, on an assumption, and the assumption got wider.** The
proposal adds one serialization hop per batch to a per-passage budget stated in
tens of milliseconds. The hop is negligible against it by arithmetic, not by
measurement; ticket 0500 is where the number would come from. The 2026-08-31
ruling that R32's bounds are any full build's rather than only the first sharpens
F2 rather than this verdict: a rebuild happens on a library already in service,
so the conductor is answering real queries while it does the work, which is
exactly the case F2 says nothing measures.

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
This is not created by the proposal — a ratified embed worker running a ratified
multilingual model has the same problem today — but the proposal is the first
document that has to state a single number for a single process, so it surfaces
it.

The segmentation amendment improves the case rather than worsening it: with
boundaries decided in the conductor and the worker handed ranges, the worker's
peak is the model plus one batch and nothing else — the smallest a process that
embeds can be. **Needs a ruling all the same**: the pipeline ceiling is either
re-pinned on the same measurements that re-pinned the server one, or it stands
and no multilingual candidate can be run by a pipeline worker at all. The
measurement exists; what is missing is the ruling.

**F2. The conductor now serves queries, segments, and performs every write, and
nothing measures what that does to R6.** In the ratified design the write-free query path
is a property of every P0 including the conductor, because the writing happens in
worker processes. Under W1 and W2′ one P0 segments and writes continuously during a build while
answering queries against the 700 ms preference and the 3 s bound. Segmentation
is cheap beside embedding but it is on-thread work, so it belongs in the same
measurement rather than in a separate argument. The fairness
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

**F5. The whole design's memory story rests on an incremental read that nobody
has written or measured.** The local API serves the text inside one JSON object,
so streaming it means decoding a JSON string value incrementally — escapes,
form feeds and all — rather than calling `response.json()`. The convenient call
is the one that breaks C3 on the conductor, and it breaks it silently: a build
over a library of ordinary papers never approaches the ceiling, and the failure
arrives on the one library that holds a dictionary. **Instrument**: measure
resident memory across a fetch of the largest attachment in the reference
library, both ways, in a process that has already loaded the query embedder —
the same shape as the RSS gate ticket 0026 owns, run against the transport
rather than the model. Until that exists, W2′'s clause is an instruction, not a
verified property, and it is the first thing a reviewer of the implementation
should look for.

---

## What this proposal does not decide

It does not touch ranking, chunk geometry, the entry ruling, the coverage order
or any threshold. It does not decide whether the embedding path later becomes a
local endpoint — that is ticket 0491's, and W2 is compatible with either answer,
since a pure worker is already the shape an endpoint client takes. It does not
re-open the query embedder's location: in-process, per the author.
