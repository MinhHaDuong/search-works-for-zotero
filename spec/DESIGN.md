# DESIGN v2 — The Instrumented Ledger

## Intro

This is the current design, produced by design cycle 2 (2026-08-26). It owns
every design number: the gate thresholds (§2.8), the experiment decision
rules (§3), and the budgets (§2.9). Its place in the authority chain is
stated once, in README.md. The raw panel record is gone, lost with the pre-restart history (DECISIONS.md, 2026-08-31); where it once disagreed with this
document, this document was already the record, and is now the only one. The predecessor design (cycle 1's
"The Settled Ledger", called v1 below) is superseded and lives in git
history.

How cycle 2 worked, in two sentences: six architects each re-ran the design
through one lens (derivation, corpus, custody, concurrency, query, operator)
against the consolidated requirements and constraints; each result was
adversarially critiqued, and this synthesis assembles what survived, plus
the named repairs. Every load-bearing claim about upstream code was
re-verified against `oscardvs/zoteus` at HEAD `edf2748` (v1.7.0; upstream
has since moved to v1.9.0 `bb414df`, whose deltas SYNC.md characterizes, and
each ticket re-verifies its own evidence on moved files before acting), and
the disputed numbers were recomputed from the committed artifacts in
`bench/results/`. Two process bounds held throughout: decisions and rulings
already ratified were not reopened, and the scout findings entered as
binding input.

Seven facts were verified live at edf2748 and are relied on below. The
query tokenizer is broken for non-English text (`tokenize.ts`:
`/[a-z0-9]+/g` plus 29 English stopwords). There is no `busy_timeout` and
no `SQLITE_BUSY` handling anywhere in `src/`. `SCHEMA_VERSION` is written
(`sqlite-index.ts:26,153`) and never read. `DEFAULT_FULLTEXT_MAX_CHARS =
40_000` truncates the 44.9 MB living example roughly 1 100-fold. Changing
embedder drops every vector at open (`dropStaleVectors` →
`clearVectors()`). Builds crawl `top:true` only, and `clearStore()` sits in
the build path. Two artifact recomputations
decided disputes: the golden-answer stability sample (60 queries with
pinned known-correct results, from
`bench/results/0013-concentration/uncapped-477512.json`) has a per-query
Jaccard minimum of 0.25 under legitimate perturbation (two of the 60 fall
below 0.5), and
`bench/results/0012-fulltext-sequence/sequences.json` carries 584 of 8 037
fulltext entries at version 0.

---

## 1. What changed since v1

v1's skeleton survived every lens and every critique untouched: durable
(item × stage) ledger rows in SQLite with lease claim → compute → commit,
control through a pipe and durable work through the database, a write-free
query path, and two OS processes. R13 (second process), R22 (durable pause)
and R17's work counters each turn out to *want* that skeleton: every one is
a one-row concern on a substrate that already exists. Also carried over:
census-seeded newest-first discovery (a census is a full listing, every
item or every fulltext version, fetched whole rather than paged),
micro-batch commits, the int8 vector plan with its X1 gate, the stored-norm
dot product, slabs, the derived vector sidecar (vectors live in a file
beside the database, derived from it), probe-don't-fix,
sideline-never-delete (an unreadable index file is moved aside, never
deleted), the recovery-verb grammar, and the failure policy. The failure
policy
(transient/persistent split, bisection quarantine, reachability gating,
backpressure counted in items; mechanism spec unchanged from v1 §2.6, whose
document is lost) carries two amendments. Quarantine auto-clear now keys on the
*content* signal chain, not on raw counter movement, so a resync cannot
mass-replay every poison input. And R1's terminal states (`empty`) are
*done*, not failures: different bookkeeping, different sentence in status.
The stopwords/tokenizer fix stopped being a plan: it is PR #19, merged
upstream 2026-08-27 (`4f61b2a`).

Three forces changed the rest.

1. **The rulings changed the units.** The unit of answer is the entry, not
   the item; the record is the semantic core and indexes first; chunks
   respect entry boundaries and carry their context. This killed v1's
   two-column FTS layout (FTS: SQLite's full-text search engine; replaced by
   per-field columns, §2.2), its
   collapse-to-items ranking (replaced by entry collapse, §2.6), and its
   single-figure coverage (replaced by the coverage sentence and counters,
   §2.8).

2. **Observability became the requirement.** v1 designed an engine whose
   promises (convergence, newest-first, budgets, edit costs, custody) were
   mostly unobservable. Sheet v2, the consolidated requirements and
   constraints now in REQUIREMENTS.md and CONSTRAINTS.md, makes
   observability itself the requirement, so v2 designs the instrument panel
   and the gates beside the engine.

3. **Two measured facts killed v1 machinery.** The local `/fulltext`
   sequence is mixed and must never be cursored: v1's ascending-sweep
   freshness would have silently lost locally-extracted text (the 584
   measured version-0 entries prove the loss non-empty), and
   census-equality replaces it (§2.4). And constraining FTS5 MATCH costs
   seconds at library scale (FTS5 evaluates a rowid-constrained MATCH once
   per row), so v1's filter pushdown dies as worded. Unconstrained MATCH
   plus a guaranteed-fill bitmap filter replaces it (§2.6).

Other reversals worth naming, each with its reason. Extract is no longer
keyed by the version counter alone, because R3's counter-churn clause and the shipped
92,7 %-changed-forever defect killed that reading: signals and keys are now
separate (§2.1). Fraction-weighted reciprocal-rank fusion (RRF) is adopted
behind the golden gate (§2.6): v1's rejection rested on wrong arithmetic,
verified empirically. Pause is a durable row, not a pipe message, because
today's `stop` was verified to cancel one job while `auto_build` restarts
on the next query (§2.7). Unknown-schema handling is read-compatibility
gating plus a new filename (`search-index-v2.sqlite`), because no protocol
can bind binaries that predate it: a v1.7.0 sibling reaching `clearStore()`
against an in-place upgraded file would erase every library (§2.7). And
v1's item-collapse PR is folded into the entries conversation (scoped issue
B, §4): shipping item-collapse now would ship exactly the framing the entry
ruling rejected.

The full verdict-by-verdict record (what survived, what was amended by
which critique, what died and what killed it) no longer exists. It lived in
this file before the plain-language rewrite and in `panel/cycle2/`, both of
them only in the pre-restart history, abandoned by ruling (DECISIONS.md,
2026-08-31). The narrative above is what remains of it.

---

## 2. The architecture

### 2.1 Signals vs keys

Every stage row stores *signals* and *keys*, never mixed.

- A *signal* is a Zotero version counter, scoped by server identity, and
  only ever compared for equality. A signal mismatch schedules
  *verification*, one fetch plus one hash, never recomputation.
- A *key* is `(content hash, tool identity)`. Work is stale exactly when the
  stored key differs from the current key.

R3's counter-churn clause falls out structurally: a resync flips
signals, the verify pass re-hashes, the hashes match, and nothing downstream
moves. R17's counters record thousands of `resync.noop` and zero
`resync.done`, so the counter that once hid the 92,7 % defect now proves
its absence.

The stage keys:

- **record**: a field-tagged `record_hash`. The canonicalization version
  folds into the tool identity, so a canonicalization fix is a labeled key
  bump.
- **extract**: `text_hash` over the streamed bytes.
- **chunk**: `(text_hash, segmenter id+version, chunker id+geometry)`. The
  segmenter lives inside the chunker key, exactly as the boundary ruling
  directs.
- **embed**: `embed_hash`, the hash of the full embedded text including the
  context prefix, with an EXISTS guard on deletes, so removing one row
  never removes a vector another row with the same hash still references.
  Hashing the chunk text alone would let a vector computed under an old
  heading silently keep serving under a new one.

Honest restatement of that benefit: *unchanged regions never re-embed*,
and a segmenter bump re-embeds only what it actually touched. And one
disclosed R3 residue: a counter-churning resync still costs
O(changed-attachments) local fetches before the hashes stop the chain.
Fetch-and-hash is the price of verification, stated rather than hidden.

### 2.2 Storage: one file, one schema, every row library-keyed

The store is `search-index-v2.sqlite`: WAL mode, `synchronous=NORMAL`,
`busy_timeout=5000` on every connection, and `PRAGMA
auto_vacuum=INCREMENTAL` set before the first table. Set any later it is a
no-op, and the idle `incremental_vacuum` promised in §2.7 would never
reclaim a page.

**Identity.** `origins(oid, server_id)` is the `Zotero-Server-ID` partition
C1 mandates, and `libraries(lib, oid, kind, remote_id, item_watermark, …)`
hangs libraries under origins. Every downstream row carries `lib`, and
every delete is `WHERE lib = ?`: Zotero keys are unique only per library,
so a merged index without the column would turn R15's delete into an R12
violation. `clearStore()` is abolished from the build path: "rebuild"
is a ledger state (`UPDATE … SET status='pending' WHERE lib=?`), never a
`DELETE FROM passages`. That makes an R12 violation unwritable for
protocol-aware binaries; the new filename (§1) fences the binaries that are
not.

**The entry layer.**

- `entries(eid, lib, item_key, attachment_key, ordinal, heading, path,
  kind ∈ record|note|annotation|body|synthetic, char_start, char_end,
  page_est, page_est_kind)`.
- `slabs(sid, lib, source ∈ attachment|record|note|annotation, source_key,
  char range, gzip bytes ≤ 1 MiB, content_hash)`. Record and own-words text
  is slabbed too, because otherwise the first 100 % (phase A) would ship
  hits whose snippets cannot be re-derived.
- `passages(pid, eid, lib, item_key, sid, off_start, off_end, fp)` are
  references, not text. Snippets re-derive from our own slab store,
  never from Zotero: gunzip one slab, slice, verify the fingerprint, and
  return null rather than wrong words on a mismatch, and slab cuts land on
  entry boundaries, not byte counts.

**FTS.** FTS5 with per-field columns, tokenizer `unicode61
remove_diacritics 2`: `fts(title, abstract, creators, tags, pub, ctx, own,
body)`. Per-field columns replace v1's two joined columns for two reasons.
Fields keep their identity for ranking: a tag match no longer scores like a
title match, the record ruling's exact complaint. And joined fields break
phrase search: with `'. '`-joined fields, unicode61 treats `.` as a
separator, so a quoted phrase can falsely match across the seam between two
fields. Body rows put
chunk text in `body` and the heading path plus item title in `ctx`, so
context matches count (weighted) without polluting `body`'s document
frequencies or phrase positions. The *embedded* text is
`«title» › «heading path» ¶ «chunk»`, with the prefix charged to the token
budget, Zotero's own prior art. Creators, venue, and date have a stated
column mapping (the creators and pub columns; date goes into the record
row's `pub`), so no field indexed today silently vanishes. The bm25 column
weights ship as a starting point and are tuned against the golden set once
it is re-pinned at entry granularity, not before. Contentless FTS
(`content=''`, `contentless_delete=1`) where SQLite ≥ 3.43. v1's
external-content layout is the probed fallback, chosen once and recorded in
meta.

**Chunking.** Tokens on structural boundaries: 120 minimum / 48 overlap,
never across entries, with overlap only inside a split paragraph. The maximum
is not a constant but a budget, resolved once per model (ratified 2026-08-29):

    budget = min(500, modelMax) − specialTokens − count(passagePrefix)

and the resolved budget is recorded in the chunker key, so a model change that
moves it invalidates chunks explicitly rather than silently. The construction
is the platform's; the ceiling is ours, and the difference is deliberate.
Zotero uses 768 as a ceiling rather than a chunk size, and pairs it with this
same minimum against the model's window. Cycle 2 copied the ceiling, used it as
a target, and dropped the minimum — which is what left a 768-token chunk
unreadable by a 512-token embedder with nothing raised.

The ceiling is 500 because it sits below every window in play. Across the nine
embedders of ticket 0240 plus the one zoteus loads today, the tightest declared
window is 512 tokens, so the minimum never binds: the budget resolves to the
same number under every candidate, which is what keeps the chunk key stable
across a model swap. Measured, not assumed
(`verification/probes/model-window-census.py`, artifact
`bench/results/0140-model-windows/candidate-windows.json`). A ceiling of 768
would bind at each model's own window instead, giving roughly half again as
much text per vector under a long-window model. That is not free capacity: one
vector is a fixed-size summary, and averaging more text into it degrades
retrieval whatever window the model advertises.

`modelMax` means the minimum over every position-limit field the model
declares. The fields disagree: one candidate declares four of them spanning a
factor of four, the largest being extrapolation past what it was trained on,
and another declares different limits in its config and its tokenizer config.
A construction naming no field is therefore underspecified. At this ceiling the
ambiguity never bites, and the rule is stated so it stays that way should the
ceiling ever move.

The unit is the authored paragraph; the budget is a guard, not a target
(ratified 2026-08-30). Real paragraphs measure roughly 130–390 tokens across
both tokenizer families in play — inside the budget with room to spare — so
the cap binds only on extraction artifacts: glued paragraphs, reference
lists, mangled layout. Splitting those loses nothing an author wrote.

The heading path is charged to this budget, and dropped entirely rather than
truncated when it would cost more than a quarter of it — a deeply nested entry
should not yield a chunk that is mostly breadcrumb. Ordering matters: the
budget bounds the whole embedded sequence, path included, so
`min(500, width) − affordances` is not `min(width − affordances, 500)`.

The embed call is part of this contract. Seg/1's embed path asserts the cap
before embedding — an over-length chunk is a bug and surfaces loudly — and
declares its truncation behaviour explicitly on the call, rather than
inheriting whatever the runtime does in silence (measured: the incumbent
embeds the first 512 tokens and discards the rest without a word, ticket
0140's founding identity). The guard ships inside the seg/1 upstream change
(ticket 0028), the change that creates the exposure — never as a standalone
filing (DECISIONS.md, 2026-08-30).

(For the record: the claim that upstream chunks below Zotero's minimum holds
only for its 512-char *metadata* stride; its 1 200-char body chunks are roughly 250–300 tokens,
inside the band. The move to token-structural chunking rests on the boundary
ruling, not on that comparison.)

**The calibration header's cheap read: a projected vector at a published seed**
(ratified 2026-08-31). Every vector file certifies its own chain by carrying a
fixed calibration set its chain produced, and a reader decides locally by
embedding the same chunks and comparing. That comparison is two tests — per-vector
cosine, and rank agreement over the set's own similarity matrix — and both want
the full fp32 vectors. Beside them the header carries the same vectors under a
random projection to **32 dims**, `R` drawn from a seed published with the format,
as the cheap first read that fails fast before the full comparison runs.

The projection is admissible where a data-derived basis is not, for three
reasons. Its matrix carries no corpus, so a file handed to a stranger discloses
nothing about the library it was built from; both machines derive the same `R`
from the seed, so no basis travels; and its guarantee is distribution-free, so it
does not depend on the geometry of any one model. What it preserves is the ratio
the decision reads — the distance to the nearest other chain over the distance
this chain moves when only the provider changes — at **8 192 bytes per header,
24,0x smaller than the full fp32 header**, keeping a worst case of **29,68x**
against the narrowest unprojected **31,67x** (ticket 0499,
`bench/results/0499-chain-identifier/`).

Two bounds ship with it. The threshold this distance is compared against is not
set here: it waits on X8's successor question (§3, ticket 0485) and must be sized
from measured distributions rather than simulation. And the read is meaningful at
fp32 only — at the 8-bit rungs the same chain read on another execution provider
already moves further than the nearest different chain does, which is the same
boundary §2.5's device rule reaches from the cosine side. A hash of any kind is
ruled out cross-machine, sign bits included, and the ledger records why.

*Owed here, and not by this entry:* the header itself, its never-mix invariant and
its fixed 64-chunk set are ratified (DECISIONS.md, 2026-08-31) and this section
still has to carry them, along with §2.1's stage keys and the per-file
`embed_hash` guard that ruling reshapes.

**The segmenter, seg/1** is new machinery: the spec lives here, and ticket
0028 builds to it.

- Classify lines, and collect heading candidates from numbering patterns,
  case shape, and the dictionary's headword *rhythm*, the median gap and
  median absolute deviation (MAD) over candidate spacing.
- Cut entries at accepted headings.
- Confidence = the fraction of text inside confirmed entries.
- Below confidence 0.5, fall back to synthetic entries of ~6k tokens cut
  at paragraph boundaries, labeled as synthetic.

Dictionary arithmetic (input assumption labeled, unmeasured): 44.9 MB across
~1 850 entries ≈ 24 KB ≈ 6k tokens ≈ 8–9 chunks each, so the dictionary
becomes ~1 850 first-class peers, which is the entry ruling's whole point.
The segmenter is the design's biggest unmeasured bet; experiment X5 gates
scoped issue B on it (§5, risk 1).

### 2.3 Discovery order: three priority classes, newest first inside each

Three priority classes, in this order: **metadata**, then **notes and
annotations**, then **body text**. Within each class, newer first. That is the
whole ordering rule, and it is checkable at any instant: no item's body text is
indexed before its record.

Ordering is not the only promise. New and deleted data in any class must be
discovered in reasonable time, which is the reconcile tick's job and is stated
in §2.4 rather than here.

What the order buys: within minutes a user can find any item by its title,
author or abstract, and body text fills in behind that for hours.

- **Phase A — records.** Every item's record, its fields kept apart. Each
  library is swept `date_added DESC` and the sweeps are merged k-way, so the
  order is newest-first across all libraries at once — recency is the
  researcher's notion of priority and does not stop at a library boundary. A
  record is 1–2 chunks, so 10k items make ≈ 12–15k record chunks; at an assumed
  (labeled) 25 passages/s that is ≈ 8–10 minutes to D1's first 100 %.

- **Phase A′ — own words** (R16; D7 = both). Child notes and annotations
  follow, in a second pass filtered by item type. Upstream does not do this
  today, verified: its builds crawl `top:true` only, so standalone notes are
  indexed and child notes and annotations are not.

- **Phase B — body text.** Entry-segmented. Each item's first K passages ride
  the main frontier (band 0) and the rest queue behind it (band 1), so one
  15 000-page PDF cannot monopolize the pipeline. K is derived from this corpus
  rather than transplanted: K = ceil(median passages per item), floor 16,
  stated in meta.

  Where K lands, and why the number moved. Under the old char-stride chunking
  the measured median was 63 passages/item, giving K = 64. Under the token
  geometry the median attachment measures 18 passages —
  35 for PDFs, 5 for HTML snapshots, whose extraction is mostly chrome —
  so K lands near the floor instead. The census counts per attachment cache, the closest measurable proxy
  for the item until seg/1 exists
  (`bench/results/0140-passage-census/census.json`).

**What is checked, and what is not.** The harness asserts the class order
above, per item, and it asserts that discovery keeps up. It does not assert a
position. The reading that record coverage is a strict
newest-first prefix was rejected on 2026-08-29 and the veto is in DECISIONS.md:
items enter and leave the library while the build runs, so an invariant over a
positional prefix is asserted over a set that has already moved. The two bands
stay, as anti-monopoly machinery rather than as an observable; ticket 0080 owns
what else has to replace them, since the class order stops a 15k-page PDF
delaying every *record* and does not stop it monopolizing the body tier.

Zotero's own draft PR #6012 (CONSTRAINTS.md C2) orders attachments
smallest-first. Ours orders by recency and stops monopoly with the band cap
instead, and the same standard binds both: neither ordering is asserted as an
invariant over a moving set.

**D6, first-with-text.** Per item, exactly one attachment carries the body
text: the first — ascending `dateAdded`, key tie-break — that appears in the
fulltext census. A skipped attachment gets a stored reason, "identical text,
suppressed" or "different text, not indexed under first-with-text", which is
honesty without reopening the decision. If a later extraction gives an earlier
attachment text, the choice function's output changes and the chain re-derives
from there.

### 2.4 Freshness: how the index finds out what changed

The reconcile tick asks Zotero what changed and queues the work. It does not
extract anything itself. It is conductor-owned (§2.5), runs every 60 s when
idle, backs off when Zotero is unreachable, and schedules the **extract shim**,
which runs to drain. The 60 s cadence is what delivers R35's one-minute
promise, so the worst case is one full tick: a change landing just after a tick
waits for the next. Backing off is not a violation — a Zotero that is not
answering has nothing to report, and R35 starts its minute when it comes back. The shim talks to Zotero only. It drains the extract-stage
ledger queue and keeps the bookkeeping that makes extraction converge, and
converge to the latest extractor: the item cursor, the full-text census,
extractor-version staleness, and per-attachment truncation flags. Three things
per library.

1. **Items.** Fetch `?since=item_watermark`, the watermark scoped to
   (oid, lib). A cursor is legitimate here because library versions are
   monotonic per backend, and scoping by server ID is what makes that true —
   the local/cloud label was verified insufficient, and the header machinery to
   lift already exists upstream at `local-writes.ts`.

2. **Full text, local scope.** Fetch the whole `/fulltext?since=0` census and
   diff it per attachment against the stored versions. No cursor, and no
   fulltext watermark column exists for any local scope, because the local
   sequence is mixed: one attachment's version may be a web sync stamp, a local
   client version, or 0 for locally extracted text (C1). The schema makes that
   trap unrepresentable rather than documenting it. Cloud scopes are different
   — the web sequence really is monotonic — so they use an ordinary `?since=`
   cursor, under the web politeness constraint CONSTRAINTS.md states once. The
   census is cheap: ~8 037 entries ≈ 120–200 KB serialized per tick,
   O(attachments) in memory, no extra requests. If X7 measures the parse above
   50 ms at 30k entries, the cadence backs off to every 5th tick — a decision
   rule, not a hope.

3. **Deletions.** Subtract the item census every tick, because R35 gives
   deleting a one-minute bound and the tick is what delivers it — an earlier
   every-10th-tick cadence disclosed ≤ ~10 min and no longer meets the
   promise. The `sync` verb still forces it immediately. The local API has no
   `/deleted` endpoint (C2), so census subtraction is the only local route.
   What the item census costs per tick is unmeasured, unlike the full-text one
   above; ticket 0503 measures it, and if it proves too expensive to run every
   minute the finding is about the cadence, never about the bound.

The shim passes Zotero's bytes through unchanged. The local API serves the
cache bytes as they are, blank lines and form-feed page boundaries included
(`verification/probes/api-vs-cache-probe.py`; ruling 2026-08-30), so structure
is lost in today's chunker rather than in transport, and the extract stage
carries those signals through from day one. A later extractor can replace the
shim without moving the ledger boundary or touching the stages downstream.

**The version-0 residue.** 584 of 8 037 measured fulltext entries sit at
version 0. A local re-extraction that stamps 0 again is invisible to an
equality comparison, and on a never-synced library that could be *every* entry.
The resolution has four parts.

(i) Widen the extract signal to `(fulltext version, attachment item
md5/version)`. Replacing a file bumps the attachment item in the item sequence
the tick already sweeps, so file-driven re-extraction is caught for free.

(ii) What remains — re-extraction with no file change — is disclosed in the
contract as accepted staleness: "version-0 text refreshes on file change or
rebuild".

(iii) A bounded idle re-verify sweep is built only if X6 shows that local
re-extraction really does re-stamp 0. The experiment runs before the machinery
is written: re-extract one attachment on a synced profile and on a never-synced
one, and watch the census and the attachment item's version.

(iv) A **content-presence probe** at verify time, ratified 2026-08-30 on X6's
decoupling finding (`bench/results/0025-x6-version-dynamics/`). A derived cache
can vanish — content 404 — with every version signal and the source md5
unmoved, so nothing in (i)–(iii) sees it. A 404 on an item whose passages are
indexed marks them **cache-lost**: a stored warning state, counted, its reason
in the terminal-state vocabulary. Never an eviction, because the source did not
change and the passages remain faithful; the healing path is the user's
Reindex, surfaced as a count. The probe rides the extract shim's bounded verify
walk — part (iii)'s sweep if X6 forces it, otherwise its own slow walk — and
its cadence is pinned when the machinery lands.

**The query path** is unchanged from v1: no Zotero requests at all when the
tick ran within ~30 s, otherwise one memoized probe with a 500 ms deadline that
reports and nudges rather than blocks, with `probedMsAgo` in replies.

### 2.5 Embedder registry, topology and concurrency

**The registry is configuration, not a menu of model names.** One indivisible,
versioned entry owns the model repository and revision, graph and dtype,
pooling, normalization, query and passage templates, model window, output
dimension and registry-schema revision. Those vector-affecting fields produce
the embedder fingerprint in C1. Display text and validation standing do not.
The public selector accepts an entry id, never a bag of raw overrides; an
unknown id is an error. During the invariant stages an unset selector resolves
to the singleton incumbent MiniLM entry and must reproduce its old vectors and
keys byte for byte.

**Embedding has one transport-neutral interface.** Both
`embed_query(text, entry)` and `embed_passages(batch, entry)` return vectors
with a handshake naming the requested and actual fingerprints, dimension,
runtime, execution provider and local-validation result. The client rejects a
mismatch before reading or writing a vector. The first implementation and the
installation default remain in-process. The interface admits a later local IPC
adapter without making a daemon, supervisor or OS facility part of the registry
contract or a prerequisite for curated entries. Conceptually the execution
choice is `provider: in_process` now or `provider: local_endpoint` later; it
does not alter the selected entry. The actual execution provider contributes to
the vector fingerprint only when §3's X8 rule says its vectors are not
interchangeable. Endpoint syntax and discovery stay out of the registry until
ticket 0491 decides their owner.
A future `provider: zotero` is the preferred reuse probe: #6012 already runs
native ONNX inference in Firefox's separate memory-gated process, but its
`Zotero.ML` and `Zotero.Embeddings` calls are internal at the reviewed head.
Ticket 0496 asks whether an official local bridge can expose query and batched
passage embedding with the same fingerprint handshake. Sharing Zotero's stored
embedding database or depending on private in-process symbols is not that bridge.

**Process topology.** Four process roles appear below: P0, a query-serving
zoteus server, and one worker kind for each asynchronous pipeline stage —
extract, chunk, embed.

The normal deployment is N × P0: one zoteus per MCP client, all on one fixed
default data directory (verified). Every P0 answers queries, as a WAL reader
on a write-free query path. Exactly one P0 is the *conductor*, elected through
a lease row:

    UPDATE leases SET holder=:uuid, expires_at=…
    WHERE name='conductor' AND (holder=:uuid OR expires_at < :now)

The holder is a UUID, not a recyclable pid. A lockfile was rejected because
lockfiles go stale exactly when their holder dies. Lease timing: TTL = 2×
heartbeat (20 s), an election-check cadence of 10 s in every server, and a
migration gate < TTL + cadence = 30 s. The constants satisfy their own
gate. The conductor runs the reconcile tick and owns at most one worker of
each kind (`nice 19`), so the pipeline does not multiply with N. Each worker
is run-to-drain: it is spawned when its stage's ledger queue has work, drains
that queue, and exits. The ledger's keyed, idempotent derivations — not an
in-memory pipe — are the boundary between stages. When every queue is drained,
steady state contains no pipeline worker.

Two orphan repairs are mandatory for every worker kind, because without them
nothing actually enforces the one-of-each bound. Each worker exits on stdin
EOF (parent death) and re-verifies `leases.holder == parent-uuid` between
micro-batches, exiting on mismatch. Lease renewal runs on a timer decoupled
from stage progress and is renewed immediately before any long unit of work;
the extract stage's whole-document GET has no micro-batch boundary inside it.

Safety never depends on the singleton: per-row leases with the
`claimed_input` commit guard are the correctness layer, cross-process by
construction. R13's letter is restated honestly: never committed twice, and
duplicate compute ≤ one micro-batch per failover. The strict letter has no
implementation on a single-file SQLite substrate, and the design says so
rather than implying otherwise.

Foreground beats background across processes: each P0 touches
`<dataDir>/activity` on query arrival (a filesystem operation, so the query
path stays write-free even in the database sense). Every active worker stats
that file between micro-batches and idles 2 s while it is fresh. The
conductor's stdio pipes remain the low-latency fast path; `nice 19` remains
the OS floor. Upstream's BEGIN-at-first-mutation transaction is repaired
surgically: the build path commits per page (its 200-item/10 s persist
cadence already exists; the hold window shrinks below the busy_timeout),
while the update path keeps its single-transaction rollback. Upstream's
own comment is right that a half-applied delta is a wrong index, not a
partial one.

Sidecar discipline: the conductor's single embed worker alone writes, into
generation-numbered files (`vectors-<embedderKey>.g<N>`), fsynced then
atomically renamed. The generation is stamped in meta and verified by scans,
and deletion tombstones cover every live generation. Compaction runs at >10 %
dead rows or in the idle weekly slot.

### 2.6 Query path and ranking

**Query semantics (D5), granularity decided out loud.** Hard units (quoted
phrases, explicit AND, NOT) are filters, while bare terms are soft: they
rank, OR'd, which is today's recall-friendly default, kept deliberately. Phrases
evaluate per passage (FTS5-native, positions intact; a phrase straddling
two entries is correctly dead text). AND and NOT evaluate at entry scope:
one MATCH per hard term, id-lists joined on `eid`. AND means every term
hits at least one passage of the entry; NOT means no passage of the entry
hits. That is a few id-set operations over lists the design already
fetches, one extra MATCH per hard term, trivially inside R6. Passage-scope
AND on a multi-chunk entry would silently exclude legitimate hits (proved
by construction during the critique). Until entries exist upstream, hard
predicates ship at item scope, entry scope's conservative projection at
today's granularity, and any upstream filing of this work says so out
loud. Memory-backend parity: the phrase/AND/NOT check runs against a
fold-only, unfiltered token stream re-tokenized from stored text, because
the retained `tokenize()` arrays are stopword-stripped and would make
`"war and peace"` match "war versus peace". The predicate is pushed inside
`search()` before its top-k slice.

**Filters (R5).** Facets compile in SQL to an allowed-entry bitmap, and on
the vector scan the bitmap applies before the dot product: genuine
pushdown, since that loop is ours. On the keyword side, MATCH runs unconstrained
(C2's measured economics, and upstream already does this) with pool
`max(8×limit, 256)`, and the bitmap filters the candidate stream. A ladder
guarantees the result fills up: first refetch deeper (4 096); then, for
scopes of roughly ≤ 20k passages, run a constrained MATCH via `json_each`
(`carray` does not exist in `node:sqlite`), where the actual threshold is
measured by X4, not trusted; then stop and answer honestly through R18's
`scope{}` block. No path ever post-filters a top-k and *claims
completeness*; the give-up is disclosed, which is what R5 and R18 jointly
demand.

**Entry collapse.** Each engine collapses passages to entries *before ranks
are assigned*: the entry score is the MAX over its chunks (#6012's rule,
transposed to the ratified unit). The vector scan does the collapse in a
single pass with an entry-keyed top-S heap, because a refetch variant would
hide a second 650k scan, ~0.5–1 s, on exactly the dictionary-heavy queries
that trigger it. Presentation groups entries under items; ranking never
re-collapses. D9 dissolves as the ruling says, and R24 absorbed the dedup clause: the dictionary earns
many slots only with many genuinely distinct entries, and concentration is
still disclosed in status.

**Fusion.** The fusion rule is fraction-weighted RRF at k=60. The seam invariant, that every
ranked list crossing the fusion seam is higher-is-better and strictly
positive, is a unit-tested contract at the four verified lines (SQLite
clamps idf; `-r.rank` stays positive). `frac ∈ [0,1]` bounds every
contribution above by plain RRF, and frac = 0 is noise-suppressed, stated.
`frac_vec` defaults to list-local max-normalization. #6012-style
registry introduces two deliberately separate checks. First, every selected
entry must pass the bundled public compatibility fixture on the actual local
runtime and provider before it creates or queries an index. That check covers
loadability, declared dimension, finite values, normalization, application of
query and passage templates, determinism within the provider, and basic
matched-over-unmatched discrimination. Its cached result is keyed by the full
entry fingerprint plus engine version, runtime, operating system, architecture
and execution provider. A remote result can inform the UI but never substitutes
for this local gate.

Second, #6012-style library calibration (mean centering, noise floor = p99 of
unrelated pairs, ceiling = median of matched pairs, reject bad models outright)
remains deferred to ticket 0031. One item's title and abstract form a matched
pair, cross-item pairs are unrelated, and the private library is the corpus.
Those texts and scores never enter a shared attestation. An optional,
content-free compatibility attestation may report only pass/fail, exact entry
fingerprint and runtime shape, after explicit opt-in; it is evidence that a
configuration executes, not that it retrieves well. Ship gate (D11): golden-set
Jaccard at or above §2.8's thresholds against plain RRF, both behind one flag.

**The locator (R24)** is discriminated by the hit's entry kind: a record or
note hit has no attachment and no page, and the reply never fabricates
either.

- A **body** hit carries `{itemKey, attachmentKey, entry heading/path,
  charStart/End, pageEstimate, pageIsEstimate: true}`. The heading path is
  the primary locator (per the ruling); the char offsets are exact. The
  page is estimated within its attachment, from per-attachment totals that
  extraction now records instead of discarding (verified: upstream keeps
  only `content` and concatenates, destroying the offset→attachment
  mapping). `pageIsEstimate` stays true until a verified exact mapping
  exists; the label is the honesty mechanism.
- A **record** hit carries `{itemKey, field}`.
- A **note/annotation** hit carries `{itemKey, sourceKey}`; the
  annotation's parent attachment and page, when Zotero supplies them, pass
  through as exact.

**Empty results (R18).** An empty result names its scope in one of three
disjoint sentences ("not indexed yet (0 of 947)", "partial: 812 of 947 —
the miss may be coverage", "fully covered — nothing matches"), computed at
query time from facet tables joined to ledger terminal states, deliberately
*not* a materialized counter (C4 governs the status path; R6 governs this
one). Under a strict query, one relaxed soft-MATCH count offers the
drop-the-quotes alternative.

**Cross-lingual (R29).** Keyword search cannot cross languages: FTS5 and
`bm25()` have no path from "hydropower" or "hydroélectricité" to "thủy điện",
whatever the tokenizer folds. The embedding space is the only channel, so the
promise stands or falls on the embedder and rides the semantic path with no new
query-side machinery. On such a query the keyword list is empty or noise, so
fusion has to let a semantic hit surface without keyword confirmation — the
`frac_vec` question ticket 0031 owns, with the cross-lingual slice as its
hardest case. When the semantic path is unavailable the reply carries a typed
`CROSS_LINGUAL_DEGRADED` disclosure beside R18's sentences, the CJK posture
below transposed. Alignment is a property of the embedder's training and varies
by language pair, so it is measured per candidate at the deployed dtype rather
than read off a model card; ticket 0266 is that measurement, and R29 is a
conformance criterion in the registry's ship gate (ticket 0495).

**CJK.** The multilingual embedder is the CJK path, with a typed
`CJK_KEYWORD_DEGRADED` disclosure meanwhile. The scheduled companion is
2-gram twin tables (#6012's shipped geometry, and decisive on its own
terms: the modal Chinese word is two characters, unrepresentable as an
exact trigram), backfilled from slabs for CJK-bearing passages only,
query-routed, fused as a third list. SentencePiece quadratic-encode caution
inherited: cap encode segments at ~1 000 chars.

### 2.7 Custody and lifecycle

**R10 — local by default.** Verified: exactly two opt-in exfiltration paths,
no silent fallback. The sole permitted external call on the default path is
the one-time model-weight download, named in status, degrading to
keyword-only and *never* to an API embedder; that invariant gets a test.
Every reply carries the one-line custody string. The consent gate:
auto-build defaults on only for the free local embedder; API embedders
quote a cost and require an explicit go-ahead per index generation. One
hygiene PR: the Gemini key moves from the URL query string to a header.

**R15 — deleted means gone.** Deletion rides the census tick, and every copy
of the text has a named removal path:

- item and entry rows
- the FTS index, via its delete protocol (upstream's correct discipline,
  kept)
- passages
- vectors
- slabs (keyed per attachment/source, never shared)
- sidecar tombstone bitmaps, across *all* generations
- ledger rows (a worker committing on a deleted item fails its guard)
- WAL and free pages: `auto_vacuum=INCREMENTAL` actually set (§2.2), plus
  idle checkpoint, plus the `purge` verb = checkpoint + VACUUM + compaction
- the legacy `search-index.json`, which upstream leaves in place forever,
  renamed `.migrated-<ts>` after the first post-migration save and swept at
  30 days or on `purge` (an *issue*, not a PR, because it reverses his
  documented decision)

Pause never gates removal: deletion propagation is classified as removal,
not derivation (one branch in the tick), because otherwise a paused index
serves deleted text for months. The acceptance test decompresses slabs
before grepping (`strings` on gzip proves nothing). Byte-level "gone" is
eventual, with a disclosed bound, stated as the negotiated reading of R15,
for the author to veto.

**R22 — pause stays paused.** One meta row, written by `pause`, read before
any scheduling decision. It gates worker spawn (a paused pipeline is zero
processes: drain, then shut down, a #6012 pattern), the tick's build side,
and `auto_build`
(verified: today any query against an empty index starts a build). It does
not gate queries, the probe, deletions, or explicit verbs (`build` while
paused asks). It survives restart by construction, and survives *sideline*
by being carried into the fresh file. R1-versus-R22 resolves in the user's
favor, disclosed: "paused since <date>".

**D3 — serve-stale.** The verified violation (`dropStaleVectors` →
`clearVectors()` at open) dies. Vectors carry per-row embedder keys: on a
model switch nothing drops, re-embedding drains newest-first, and during
the window queries dual-embed, each row scored in its own space. The old
model is lazy-loaded only while old-generation rows are in the pool, and
evicted after ~60 s idle. Under memory pressure, queries fall back to
labeled keyword-anchored fusion. Two resident models (~240 MB + 70 +
32–64) would bust the ratified ceiling for a days-long window, so
lazy-loading keeps the budget honest at the price of a disclosed cold-load
spike. At most two generations coexist; worst-case storage is 2× the
sidecar, disclosed.
The *small PR* version of D3 is narrower: upstream's one global
`embedderId` cannot support mixed spaces, so the contained fix is
keep-vectors plus pinning the query-side embedder to the stored id until a
rebuild switches both. Dual-embed lives in scoped issue A (§4).

**R23 — upgrade and downgrade.** The open protocol: read
`meta.schemaVersion` before any DDL or write (verified defect:
`createSchema` re-stamps via `INSERT OR REPLACE` before `loadMeta`, so today
a downgrade destroys the evidence of skew at the moment it matters). A
newer file → sideline (never delete), fresh build, notice. Only the
conductor may sideline, because under N processes an unconditional
per-server sideline would let one stale install repeatedly sideline a fresh
one's index. An older file → versioned migrations. `min_reader_version`
lets a too-old-but-aware server keep serving everything that never touches
the index, and answer search with a typed `SCHEMA_NEWER {remedy}`. The
ping-pong-downgrade hybrid state carries its own tamper evidence:
`stamp==1 && v2 tables present` means an old binary wrote here, and the
response is not "migrate" but reconcile-heal: mark derived stages stale,
census-diff, let R1 re-earn. The retroactive limit is stated plainly:
binaries that predate the protocol (every release through v1.8.0; v1.9.0
ships the read-before-write + sideline slice via PR #25, but not the
conductor rule or `min_reader_version`) are unreachable by it; the new
filename (§1) is what actually protects against them.

**R15's uninstall clause.** Pin `env.cacheDir` under the data directory before
constructing the pipeline (the transformers default lands outside it, per
its documentation: documentation-cited, not disk-verified, and the fix is
correct regardless). Uninstall = delete the data directory; `purge` +
uninstall = byte-clean. D2 hosted-out deletes, explicitly: per-tenant
contract keying, multi-tenant consent bookkeeping, encryption-at-rest,
quota arithmetic; the four returned privacy lines stay dead.

### 2.8 The instrument panel

**The coverage sentence** (D1 denominator = items; metadata-only covered
with reason; sections only ever the partial qualifier):

> "All 7,541 items are record-searchable (titles, abstracts, keywords —
> 100%, newest first). Body text: 5,561 of 6,100 items with attachments
> extracted and keyword-searchable back to 2016-04-11; 538 covered as
> metadata-only (no extractable text). Semantic: 2,101 items fully embedded
> back to 2019-09-02, newest first; 1 partially embedded (record + 214 of
> ~1,850 entries — item DH8EXSVA). Building in background at idle
> priority; not paused. 1 quarantined: BHT7Q2 — extraction failed 3×;
> retries when its content changes."

The example's arithmetic is deliberately consistent (5,561 extracted + 538
metadata-only + 1 quarantined = 6,100, the states disjoint), and "covered
at extract" is defined once: items with no attachments are vacuously
covered, the "of 6,100" clause scopes the with-attachments subset, so
`covered.embed == items.total` is stateable on a real library. Beyond the
sentence, status carries per-library rows, the pause line ("paused since
<date>"), the custody string, the record/body coverage split, and the
version-0 residue disclosure (§2.4).

**Counters (C4).** `counters(name, value)`, updated in the same
transaction as the ledger transition each one describes. Per stage:
`covered / empty / partial / outOfBand / quarantined`. Work counters on two
axes: `work.<stage>.<trigger>.<outcome>`, with trigger ∈ `{new, edit,
re-extract, resync, key-bump, prefix-stale, retry, delete}` (R17's "which
input") and outcome ∈ `{noop, done}`. Here `noop` means signals moved, keys
verified unchanged, nothing recomputed; `done` means recomputed. R17 needs
both what triggered work and what became of it, and one flat vocabulary
cannot say both. Idle reconciliation recomputes the counters with real
COUNTs, fixes them, and increments a surfaced `drift` counter the harness
fails on, because if the counters can drift silently, every status answer
built on them is suspect. Status point reads are sub-ms, against the
measured 374 ms cold scan.

The boundary cursor is where the crawl resumes, not an invariant anyone
asserts. It is the total-order key `(dateAdded, lib, itemKey)`, never the bare
date, because several items can share a `dateAdded` and the boundary MUST be
able to stop partway through such a tie group. It passes settled states
(`done | empty | quarantined | band0-done`). `outOfBand` is pure set
membership: covered items older than the boundary, decremented as the
boundary sweeps past them. Edit work counts only under the `edit` trigger,
and the record stage counts its own edits.

**The convergence harness.** Apparatus for R1 and R17, and no requirement of
its own since 2026-08-31. A fixture library, an empty data
directory, status polls at 1 Hz touching nothing else (R1 needs no asking).
It asserts four things.

- Status answers in ≤ 50 ms.
- Coverage is monotone.
- The class order §2.3 states holds, per item: nothing has body passages
  indexed before its record. A positional prefix is not asserted — the reading
  that it should be was vetoed on 2026-08-29 — and the counter arithmetic
  written to check one (`covered == |{(dateAdded, lib, itemKey) ≥ boundary}| −
  partial − quarantined + outOfBand`) is ticket 0080's to rework or retire.
- The terminal state arrives: all stages at total, drift 0, `pipeline: idle`
  (the #6012 engine-shutdown observable), work counters stationary.

Phase 2: edit
one title → exactly `work.record.edit.done == 1`, `work.embed.edit.done ==
sections(record)`, everything else 0; then a simulated identical-bytes
resync → zero recompute: every `*.done` delta 0, the touched items
appearing only under `work.*.resync.noop` (§2.1 says verification runs, and
the gate MUST permit exactly that and nothing downstream of it). This is
R3's counter-churn clause measured by R17's own counters, the test that would have caught the
shipped 92,7 % defect. Phase 3 is the hostile fixture: one quarantine, one
a 15 000-page PDF, dateAdded ties. The harness MUST fail on the corpus that exercises
its subtraction terms, not only pass on the gentle one.

Phase 4 is the schema flip, which goal 1's fold added on 2026-08-31: restamp the
built index to a foreign schema version, in either direction, restart, and
assert that the terminal state above returns unattended — nothing asked for, no
file deleted by hand — inside R32's bounds. This is R1's clause and not R23's:
what it asserts is that coverage comes back, never that it was never lost. Where
a build serves the foreign stamp rather than abandoning it, which is R23's own
promise and filed upstream, the same terminal state MUST arrive with the embed
counters flat, and it is those counters rather than the elapsed time that tell
the two outcomes apart.

**The gates** (Makefile: `check: lint figures fold-gate golden check-fast`;
`check-slow: check rss-gate convergence soak`):

- **R19, the fold gate.** `fold_sweep.mjs`, repointed at the tree under
  test. The query side falls back to `tokenize`-only when
  `normalizeForSearch` is absent, so against a pre-fold tree the gate is red
  *by classification* (a recorded miss count), not red by crash. The waiver
  keyed to PR #19's URL retired with its merge (2026-08-27): stock ≥v1.7.2
  ships `normalizeForSearch`, so against current upstream the gate runs
  green by right.
- **The RSS gate**, over constraint C3. A deterministic synthetic document at the measured
  44 906 152 chars, entry-structured (~43k headings) so the segmenter and
  the band cap are exercised. Assert: concurrent background-pipeline peak ≤
  500 MB across the run-to-drain stage workers, server p95 ≤ 750 MB, the
  ratified budgets verbatim, against the document class whose
  uncapped build once measured 2 084,9 MiB. The surrogate is a flagged
  deviation from the ratified letter ("against the 44.9 MB dictionary", content
  that cannot be committed to a public repo). Per the 2026-08-29 ruling, the
  real-document X3a run revalidates it at each release on the author's machine.
Every gate below is decided at one of two levels, and the relation between them
is calibration rather than coverage (DECISIONS.md, 2026-08-31). The **fixture
level** runs wherever the gate runs, on the committable corpus. The **library
level** runs against the author's real library or a disclosed machine and cannot
be committed. A fixture that stands in for something real — the synthetic
synthetic document, the reference machine, a scaled corpus — carries a fidelity
claim, and
the library level is the only thing that can renew it: the RSS gate's revalidation clause
is the pattern, and it binds every surrogate here, not only that one.

- **The golden gate (D11 = set)**, which decides R34. A pinned multilingual fixture
  corpus, ~40 queries, answer *sets* at k=10. Thresholds derive from the
  stability artifact: the measured per-query Jaccard minimum under
  legitimate perturbation is 0.25, so a 0.5 floor would flag legitimate
  churn. The thresholds: mean Jaccard ≥ 0.8, at most 5 % of queries below
  0.35, and a hard floor of 0.2, below the observed legitimate minimum and
  far above the failure class's measured 0.00. Order is deliberately ungated
  (`identical_ordered` was 22/60 under legitimate perturbation; an order
  gate flakes, gets turned off, and that is how ticket 0009's defect
  happened). Re-pins are commits
  whose set diff is the review artifact, and the golden set is re-pinned at
  entry granularity when entries exist; until then it gates item
  projections and says so. The corpus carries a cross-lingual slice — EN and
  FR queries whose answer sets are Vietnamese entries — gated separately from
  the monolingual queries, so a regression names which of R7 and R29 it broke.
  The same pinned set decides R34, and the two readings of it are opposite on
  purpose: the stability reading compares one run against the last and
  tolerates legitimate drift, which is what the thresholds above are for, while
  R34 compares the run against the pinned answers and tolerates none. A corpus that
  can be stable and wrong is exactly why both readings exist. Ticket 0029
  builds it, and its intersections — a 15 000-page PDF in a non-Latin script, a
  scale
  run at the multilingual default — are where terms that look independent fail
  together.
- **R13, the soak gate.** Three P0s, a full 10k drain, 1 query/s each,
  kill -9 the conductor twice. Assert: p95 ≤ 1.5 s, zero SQLITE_BUSY
  surfacing, WAL ≤ 256 MB, lease migration < 30 s, zero double-commits,
  and duplicate compute ≤ 1 micro-batch per failover.
- **The disclosure gate**, over R17's device clause. Status names the execution device actually
  serving, and that clause gates everywhere, on every machine. The throughput
  half moved to R32 on 2026-08-31 (DECISIONS.md), so this gate no longer
  carries a wall-clock threshold.
- **R32, the build-time gate.** Two bounds on any full build with the default
  configuration — the first, and equally a rebuild from nothing after an index
  is abandoned (ruled 2026-08-31) — and **a time bound with no machine attached
  is not a bound**, so each is stated on disclosed hardware and nowhere else.

  *The reference machine*: a laptop-class x86-64 CPU, four cores, no GPU, in
  the ONNX runtime the implementation ships — the class the feasibility run
  used (`bench/results/0025-x1-recall/embed-feasibility.json`, an Intel i5-8250U
  at 1,6 GHz). It is deliberately modest: a bound met only on the author's
  desktop would promise nothing to anyone else.

  *The bound is a rate*, because a wall-clock number silently fixes the library
  size: "inside twelve hours" promises a 15k-library user something and a
  60k-library user nothing. Per **passage**, not per item — R8 makes items
  deliberately non-uniform, so a per-item rate measured on short papers says
  nothing about a 15k-page PDF and one loose enough to admit that PDF is absurd
  for papers. The passage is the unit the work is done in and the unit every
  artifact already measures.

  *The bound is on the pipeline, not on one stage.* A build finishes when
  extract, chunk and embed have all finished, so a bound on embed alone is not a
  bound on the build. R32 states the rate the gate asserts — **≤ 150 ms per
  passage**, **≤ 75 ms** as the SHOULD — and this section supplies the machine
  it is measured on and the arithmetic behind the wall-clock figures it quotes.
  A rate is assertable from a few hundred passages, per stage, so a regression
  surfaces in a minute instead of at the end of a build.

  *The allocation across stages is provisional, and the total is not.* Embed is
  the dominant term and the only one measured: **≤ 120 ms** at the MUST and
  **≤ 65 ms** at the SHOULD, leaving **30 ms** and **10 ms** for extract, chunk
  and the record write together. Those two are **unpinned** — no artifact in
  this repository measures either — and the allocation may be re-cut in any
  proportion so long as the total holds, because the total is what the user
  feels and the split is an engineering convenience. What is known without
  measurement: extraction is usually a read of the platform's own full-text
  cache rather than a parse, and the expensive path is the file the platform has
  not indexed, where a 15k-page PDF yields tens of MiB (ticket 0480). Ticket
  0500 measures both stages on the reference machine and pins their share.

  *The wall clock is the promise*, and it is this rate against the measured
  census of §2.9 — the census is the bridge, and the arithmetic is shown rather
  than folded in, so a reader with a different library can do their own. At the
  design point's 567 829 passages the two rates land at 23,7 h and 11,8 h, which
  is where R32's **day** and its half come from — "indexed today", written down.
  A 15k library is roughly 22 500 record chunks, so the same bracket puts
  records inside R32's **hour**, and no separate rate is needed for them.

  The two small multilingual candidates and the incumbent sit in the SHOULD
  band on this machine; the base-sized candidates clear neither, and the largest
  is outside the MUST outright. That is the throughput constraint ticket 0495
  applies (the CPU cells ticket 0481 recovered from
  `bench/results/0264-gpu-arm/`, beside the feasibility run).

  Two costs of stating it as a rate, named rather than left to be discovered.
  A rate hides fixed and non-linear work — model load, compaction, WAL
  checkpoints, the frontier's own bookkeeping — so a sample can pass while a
  full build does not; the gate therefore asserts the rate on every run and the
  wall clock whenever a full build is available, and a disagreement between
  them is a finding about the non-linear part rather than noise. And a rate
  measured on one passage-length distribution does not transfer to another,
  which is why the fixture's distribution is pinned with the corpus.

  *Second configuration*: the disclosed GPU host, where the same bounds hold
  with room to spare. It is a second place the gate may run, never a substitute
  for the first — the promise is to the user with a laptop.

  Both bounds are design numbers this section owns, pinned here from the
  measurements cited rather than before them, per the C3-replacement pattern
  ruled 2026-08-30 (DECISIONS.md). A machine slower than the reference is not a
  failure of the promise; it is outside the disclosure, and the gate reports
  the machine it ran on so a reader can tell which case they are looking at.

**R13 observability**: a non-conductor reports `pipeline: "held-by-other"`
instead of silently duplicating work.

### 2.9 Budgets, recomputed and honestly scoped

**Disk** at the design point, under the token geometry (both counts stated).
**The passage count is measured, not derived**: 567 829 passages at the
resolved budget of 498 tokens, counted over all 13 630 fulltext caches
(211 342 921 tokens through the embedder's own tokenizer;
`bench/results/0140-passage-census/census.json`, ticket 0140). The earlier
≈ 250–300k figure was arithmetic at a 768-token maximum and understated the
count by nearly half — the measurement, not a rescaling, was the ticket's
instruction, and it was right to insist: under structural chunking the
maximum rarely binds, so no ratio could have produced this number. One stated
approximation: the census chunks each cache as one paragraph sequence (seg/1
does not exist yet), and entry boundaries only add chunk closures, so the
count errs low by that margin. The same corpus yields 650k under the old
1 200-char stride, coherently above the token count since 498 tokens is
roughly 2 000 characters; bench comparability keeps the old count. FTS
~0.3–0.4 GB + gzip slabs ~0.23 GB (680 MB raw at ~3:1) + int8 sidecar
~0.22 GB (567 829 × 384) + metadata/ledger ~0.1 GB ≈ ~0.9–1.0 GB, under
v1's 2.3 GB, because passage text is no longer stored twice (passages are
references into slabs) and the chunks are fewer. The float32 fallback adds
~0.87 GB.

**RAM**: a P0 idles at ≈ 70 MB (Node) + 32 MB (cache) ≈ ~100 MB; plus
≈ 570–660 MB of multilingual query model at its 8-bit rung on first
semantic use ≈ ~670–760 MB (the measured range across candidates, ticket
0263; the ceiling is C3's). At drain-complete steady state only P0s remain,
so two clients cost ≈ 2×700 ≈ ~1,4 GB; the former steady-state arithmetic
incorrectly kept a pipeline worker resident. Extract, chunk, and embed add
transient residency only: they are run-to-drain, one of each kind at most,
and together remain under C3's ≤ 500 MB pipeline peak with hard kill rather
than multiplying that budget by stage. The chunk split isolates the long-document
RSS risk from the memory-steady embedder; it does not buy wall-clock. Whether
the server ceiling scopes per process is settled: it does, because that is the
scope the gate can assert; the two-client whole-machine arithmetic above keeps
the aggregate visible (DECISIONS.md, 2026-08-29). Dual-embed no longer threatens
the budget (the lazy-load rule, §2.7).

**Warm query**: probe 0–1 request + embed 20–50 ms + FTS tens of ms + a
single-pass sidecar scan (X1) + fusion, which is where R6's two numbers go —
≈ 300–700 ms in the ordinary case, against the 3 s it promises never to exceed.
Unchanged, and now without the hidden second scan (§2.6).

---

## 3. Open decisions: committed, or experiments with decision rules

- **Semantic path at scale — X1.** int8 ships if recall@30 ≥ 0.98, pool ≤
  32×topK, and scan+rerank ≤ 400 ms at 650k; the float32 slab is the
  permanent fallback. The single-pass entry heap makes the pool guarantees
  free.
- **CJK — committed.** 2-gram twin tables, CJK-bearing passages only,
  backfilled from slabs; typed degradation meanwhile.
- **Stopwords — committed.** PR #19 merged (`4f61b2a`); the deletion itself
  ships in its follow-up (0014, now the train's head). X2 rejects the former
  ~50 % rule: only 9 terms drop and p95 remains 820,7 ms against the ~500 ms
  allowance. Prune query terms at df ≥ 30 %, the working point inside the
  measured ~25–35 % window: above that window the budget is not recovered;
  below it content terms begin to disappear. At the working point pruning
  alone reaches 463,5 ms p95. If fewer than two terms survive, send the raw
  token set: `to be or not to be` otherwise retains only `not`, so an
  empty-set fallback does not fire. The cutoff is justified by cost — each
  dropped term avoids walking a posting list — never by ranking quality;
  BM25 already down-weights common terms continuously, while a hard cutoff
  can only approximate that signal.
- **Fairness — committed.** Record phase, then two-band body with derived K
  (§2.3); smallest-first rejected on the record.
- **Fraction-RRF — conditional.** Ships behind the golden gate; calibration
  deferred to its own ticket with the library-derived pair protocol (§2.6).
- **Version-0 freshness residue — X6 decides.** If local re-extraction
  re-stamps 0, build the bounded re-verify sweep (M entries per tick,
  horizon reported); if it bumps anything observable, the md5-widened signal
  already catches it and the sweep is never built. Until X6 runs, the
  residue is disclosed, platform-aligned.
- **Census cadence — X7 decides.** Local census every tick, unless the parse
  exceeds 50 ms at 30k entries; then every 5th tick.
- **Constrained-MATCH threshold — X4 decides** (via `json_each`, the
  mechanism that actually exists). Measure the cost curve at 1k/5k/20k/100k
  rowids on the 477k corpus. Rule: the ladder step sits at the largest
  measured scope whose constrained-MATCH p95 ≤ 150 ms (the filter allowance
  inside the 300–700 ms typical budget); if even 1k exceeds it, no
  constrained step ships and the ladder ends at the honest R18 give-up.
- **The 15 000-page PDF's RSS — X3, split in two.** X3a, runnable before any new code,
  baselines stock upstream on the uncapped 44.9 MB document (the 2 084,9 MiB
  class) and feeds the rss-gate fixture. X3b, the streamed-slab measurement
  against the 500 MB rule, travels with the entries machinery (scoped issue
  B).
- **Segmenter — X5 gates scoped issue B.** Run seg/1 over the real 44.9 MB
  extraction; sample 50 cut points uniformly at random (seeded, recorded)
  from accepted entry boundaries; hand-score them against the printed
  dictionary. Rule: ≥ 45/50 correct ships the entry story; 40–44 raises the
  confidence gate and re-runs; < 40 means synthetic entries carry the
  corpus, labeled.
- **Cross-provider fidelity — X8 decides where the device lives.** Same model,
  same rung, the GPU provider's vectors scored against the CPU provider's over
  the fidelity probe corpus; the cells ride the 0264 GPU arm, at every rung
  both providers load, and the CPU side is the 0263 artifacts already on disk.
  Rule: at mean cosine ≥ 0,999 (the field's vector-compatibility bar,
  verification/FIELD-REVIEW.md) the execution provider stays out of the embedder key —
  device is an execution detail recorded in results, never in vector identity,
  and an index embedded on one machine can serve on another; below the bar,
  the provider enters the key and the adopt-a-foreign-index question
  (DECISIONS.md, awaiting ratification) dies on the evidence. Either way fp16
  is a single-machine rung: the CPU provider cannot load it, so no CPU
  query-side embedder can match an fp16-embedded corpus, and cross-rung mixing
  is the measured failure ticket 0240 records.
- **Budget scoping under N processes** — awaiting the author's ratification
  (DECISIONS.md; both figures stated there and in §2.9).
- **Autonomous embedding service — architectural direction, open ownership.**
  The interface seam and its future `local_endpoint` execution mode are
  committed in §2.5; implementing a daemon in zoteus is not. Ticket 0491
  compares the in-process default with Zotero #6012 runtime reuse (probe 0496),
  a bundled child, a per-user service and an external OS/community facility.
  The decision rule includes install time, cross-platform packaging, custody
  and uninstall behavior, single- and multi-P0 RAM, failure semantics, and
  whether this responsibility belongs in zoteus at all. The experiment is
  parallel to, and never a blocker for, registry entries or validation.

**Rejected this cycle, for the record** (each killed by a verified fact or a
critique, whose details are lost with the pre-restart history): cursoring any fulltext sequence on the
local transport, a universal fulltext census across transports (it would
hammer api.zotero.org), passage-scope AND/NOT, the stopword-filtered token
stream for phrase parity, the always-resident dual model, the 0.5 golden
floor (artifact-refuted), item-granularity smallest-first, trigram CJK (the
modal Chinese word is two characters), `carray` (not shipped in
`node:sqlite`), an in-place v2 schema under the old filename, pause gating
deletions, and the "contained" D3 PR as first proposed.

---

## 4. The increment sequence from v1.7.0

*(Re-formed 2026-08-26 by the political and implementation reviews and
ratified in DECISIONS.md. Both those reviews and the original fifteen-step
train are gone, lost with the pre-restart history (DECISIONS.md, 2026-08-31): what
survived the re-forming is this section.)*

Upstream code root: `/home/user/oscardvs/zoteus/src/features/search/`.
SYNC.md's measured asymmetry governs the form each item takes: a contained
defect with a failing test goes as a **[PR]** (merged twice), and anything
design-sized goes as an **[issue]** he builds himself (the precedent is
upstream issue #10; two for two).
**[X]** means measure first, and gates are repo-side, in this repo's
Makefile, never PRs.

This section carries the train's *shape* only. The terms it runs under live
once in GOVERNANCE.md, which points at the entries that ratified them; each
item's scope, evidence, and live state live in its ticket. The tickets are
authoritative for content, this list for ordering.

1. **The head, resolved** — PR #19 (accent fold) and #20 (corruption path)
   merged 2026-08-27 (`4f61b2a`, `6e4637b`); the stopwords follow-up
   (ticket 0014) is now the head.
2. **The contained-PR items** (the budget is GOVERNANCE.md's, the live
   remainder SYNC.md's) — schema read-before-write (0015), the wipe guard
   (0016; `busy_timeout` closed under the sunset, overtaken by v1.7.1 —
   DECISIONS.md 2026-08-27), cacheDir and key-to-header (0017).
3. **The reserve, demand-triggered** — terminal states (0019), own words
   (0022).
4. **Issues I-1..I-3** (0024) — the fulltext-delta finding, the measurements
   as an extension of his own #10 citation, the 40k cap behind the #6012
   checkpoint; I-4 is folded into scoped issue A, not filed.
5. **The harness offer, the first design conversation** (0032) — the
   acceptance spec he can run against whatever he builds; a one-time
   transfer.
6. **Three #10-shaped scoped issues, after the train and the offer** — A:
   ledger/freshness/counters (0033); B: entries and the segmenter (0034); C:
   multi-process on one data dir (0035). The contract survives even if he
   reimplements the machinery in his own idiom, which is where C2 says the
   durable value lives.
7. **Experiments before their dependents** (0025 carries the substrate map;
   the rules live in §3): X1 before the sidecar work, X4 before any ladder
   constant, X5 (seg/1 built first, 0028) before issue B, X6 with I-1, X7
   before the tick cadence is documented, X3a feeding the rss-gate fixture,
   and X3b traveling with issue B.
8. **The curated embedder registry** (tracker 0488) — singleton extraction;
   authoritative fields and parity; curated entries plus entry-id selection;
   local automatic compatibility validation; optional content-free
   attestations; then the separate gate that decides what ships — R7 and R29
   conformance first and untraded, the golden and resource gates choosing
   among the entries that pass it (ticket 0495; the ruling on why the swap
   happens at all is DECISIONS.md 2026-08-31).
   The autonomous-service experiment (0491) reuses the interface seam
   but does not block this sequence. One upstream design issue carries staged
   acceptance tests; it is not a prepared PR series.
9. **The commitment bounds** — stated in GOVERNANCE.md, ratified in
   DECISIONS.md's re-form entry; the fork's end state is **archived** once
   the train resolves.

---

## 5. The biggest remaining risks, and the cheapest falsifiers

**Risk 1 — the segmenter is unmeasured, and everything downstream inherits
it.** Entry collapse, locators, dedup, the golden re-pin, and the long-document
arithmetic all stand on seg/1's error rate over flat `/fulltext` text, and
seg/1 has never touched the real 44.9 MB extraction. Its failure mode is
*silent plausible-looking entries*: wrong citeable locators and wrong dedup
units, worse than honest synthetic ones. *Falsifier:* X5, half a day,
before scoped issue B claims numbers. Below acceptable precision the design
degrades gracefully to labeled synthetic entries: the contract survives;
the "1 850 peers" story does not.

**Risk 2 — the version-0 freshness residue could be the whole story, not
the residue.** On a never-synced library the census may be structurally
blind to every re-extraction. The md5 widening catches file-driven changes,
but if X6 shows re-extraction bumps nothing observable, "coverage: current"
is a lie the design can only disclose, not fix: an honest but ugly
amendment to the freshness contract. *Falsifier:* X6, an afternoon, and I-1
is already drafted to carry the answer upstream.

**Risk 3 — upstream ships its own core before the design conversation
completes.** Sharpened since v1: he built #10's answer himself in days, the
risk materialized a second time on 2026-08-27, when he filed and fixed
his own follow-up to PR #20 (#21, with #22/#23) inside one day, and
#6012's saved-search serialization is the first crack through which platform
semantic results will leak into the local API. *Falsifier:* the harness
offer and the scoped issues themselves, after the PR train; those threads
settle fork-versus-upstream for the cost of writing them. The hedge is
structural: every stage behind a key; the contract, counters, and harness
are ours whoever writes the machinery.

**Risk 4 — N-process reality diverges from the protocol on exactly the
edges the soak must catch.** The conductor election, the activity-file
yield, and the lease timing are designed against named failure states
(orphaned worker, a steal mid-document, torn sidecar) but unmeasured, and
filesystem mtime granularity and WAL growth are folklore until soaked.
*Falsifier:* the §2.8 soak gate: scripted, 30 minutes, kill -9 twice. Its
assertions are constants the protocol can arithmetically meet, so a failure
is information, not noise.

**Risk 5 — gate decay.** The fold gate's waiver retired with #19's merge
(2026-08-27), the rss and convergence gates sit in `check-slow`, and a
14-day-stale WARN is advisory. This is the normalization-of-deviance
channel that produced ticket 0011's defect, reintroduced at a slower time
constant with better signage: designed around, not away, and named so the
author can choose to tighten it. *Falsifier:* none needed, because the risk
is organizational. The mitigation is that every gate threshold cites the
artifact that justifies it, so re-pins and waivers leave evidence.

---

The bet: the ledger keeps failures boring, and the contract keeps answers
honest. Cycle 2 adds four things: the units are now the ones the author
ratified (entries, records, items), the freshness protocol can no longer be
fooled by the counter it watches, N processes are a designed state rather
than an accident, and every promise is either watched by a gate whose
threshold cites its artifact or named as an experiment with a decision rule
(§3), each falsifiable in under a day, before the expensive code exists.
