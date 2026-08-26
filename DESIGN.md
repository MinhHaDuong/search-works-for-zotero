# DESIGN v2 — The Instrumented Ledger

*Output of design cycle 2 (2026-08-26): six lens-architects (derivation, corpus, custody,
concurrency, query, operator) re-ran the design against **sheet v2** — now consolidated in
REQUIREMENTS.md and CONSTRAINTS.md, with the rulings recorded in DECISIONS.md — each
adversarially critiqued, this synthesis assembled from what survived plus named repairs.
The incumbent was cycle 1's synthesis "The Settled Ledger" (referred to as v1 throughout);
it and the sheet documents this cycle consumed are superseded and live in git history.
Resolved decisions and rulings are not reopened here; scout findings are binding input;
the raw panel record is in panel/cycle2/.*

*Every load-bearing code claim was re-verified this session against upstream
`oscardvs/zoteus` at HEAD `edf2748` (v1.7.0) — the tree v1's `/home/user/zoteus-ci` claims
now map onto — and the two numbers the critics disputed were recomputed from the artifacts:
`bench/results/0013-concentration/uncapped-477512.json` random sample (n=60) has per-query
Jaccard **minimum 0.25** (two queries below 0.5), which kills the proposed golden-gate floor;
`bench/results/0012-fulltext-sequence/sequences.json` carries **584 of 8,037** fulltext
entries at version 0, which makes the version-0 freshness residue real, not hypothetical.
Also re-confirmed live at edf2748: the broken query tokenizer (`tokenize.ts`,
`/[a-z0-9]+/g` + 29 English stopwords), zero `busy_timeout`/`SQLITE_BUSY` handling anywhere
in `src/`, `SCHEMA_VERSION` written (`sqlite-index.ts:26,153`) and never read,
`DEFAULT_FULLTEXT_MAX_CHARS = 40_000` truncating the 44.9 MB living example ~1,100-fold,
`dropStaleVectors`→`clearVectors()` at open, `top:true`-only crawls, and `clearStore()` in
the build path. Where an architect and their critic disagreed, these facts decided; the two
places facts could not decide are named as such in §1 and §3.*

**What changed since v1, in one paragraph.** Sheet v2 did three things to v1. The rulings
changed the *units*: the answer unit is the entry, not the item; the record is the semantic
core and indexes first; chunks respect entry boundaries and carry context. The delta
(R10–R28, C4) changed the *observables*: v1 designed an engine whose promises — convergence,
newest-first, budgets, edit-costs, custody — were mostly unobservable, and sheet v2 makes
observability itself the requirement, so v2 designs the instrument panel and the gates
beside the engine. And the scouts changed two *facts* v1 was standing on: the local
`/fulltext` sequence is mixed and must never be cursored (v1's freshness sweep dies), and
constraining FTS5 MATCH costs seconds at library scale (v1's filter pushdown dies as
worded). The skeleton — the (item × stage) SQLite ledger, lease claim/commit, two planes,
two processes — survived all six lenses and all six critics untouched.

---

## 1. The verdict on v1

### Survived unchanged

- **The skeleton** (§1): durable ledger rows with lease claim → compute → commit, control
  through a pipe, durable work through the DB, query path write-free. All six lenses
  verdicted SURVIVES; R13, R22, and R27 in fact *want* it — a second process, a persistent
  pause, and work counters are all one-row concerns on a substrate that already exists.
- **Census-seeded newest-first discovery** (§2.2) — the scouts *confirmed* census-diff as
  the only local deletion route (no `/deleted` endpoint), promoting it from optimization to
  the R15 trigger.
- **The failure policy** (§2.6): transient/persistent split, bisection quarantine,
  reachability gating, backpressure in items.
- **Two OS processes** (§2.3), the write-free query path, micro-batch commits — the last
  two now load-bearing for N-process safety, not just latency (concurrency lens).
- **X1's vector-layout/int8 gate, the stored-norm dot product, slabs, the derived sidecar,
  probe-don't-fix, sideline-never-delete, the recovery-verb grammar** — all unchallenged.
- **The stopwords/tokenizer fix** (§3.3) — no longer a plan: open **PR #19** is v1's PR1,
  hardened; the STOPWORDS deletion rides its follow-up.

### Amended, and by what

- **§2.4 fairness** — the record ruling adds the phase order v1 never had: records for
  everyone, newest-first, *before any body text*; the two-band frontier survives inside the
  body phase only. K is re-derived, not transplanted (corpus-critic m2): "one median item's
  worth" was K=64 at the measured 63 passages/item under char-stride chunking; under the
  token geometry adopted below the median item is ~25 passages, so **K = ceil(median
  passages/item measured on this corpus, floor 16)** — a derived constant, stated in meta.
- **§2.6** — quarantine auto-clear keys on the *content* signal chain, not raw counter
  movement (derivation lens): a resync must not mass-replay every poison input. And R14's
  terminal states (`empty`) are *done*, not failures — different bookkeeping, different
  sentence (corpus lens).
- **§2.8 contract** — gains R27 work counters, R22 pause flag, record/body coverage split,
  custody line, per-library rows, and the version-0 residue disclosure.
- **§3.2 CJK** — trigram → **2-gram twin tables**: #6012's shipped geometry, and decisive
  on its own terms — the modal Chinese word is two characters, unrepresentable as an exact
  trigram (query lens; critic confirmed).
- **§3.6 self-description** — the meta key set gains segmenter id (folded into the chunker
  key per the boundary ruling), `Zotero-Server-ID` scope rows, `min_reader_version`, the
  derived K, and the calibration block placeholder; and the open protocol is rebuilt (§2.9).
- **§2.9 budgets** — survive as numbers; the disk line is recomputed under the new geometry
  (§2.10), and the *scoping* of the ratified 300 MB server figure under N processes is
  flagged as a ratification question for the author, not decided here (concurrency-critic
  M5: reinterpreting a ratified number is the author's call). Both figures are stated.

### Died, and what killed it

1. **The `/fulltext` ascending-sweep freshness** (v1 §2.5) — killed by the SCOUTS
   mixed-sequence finding (web stamps / local client versions / 0 for local extraction;
   equality-comparable per item, never a monotonic cursor). All six lenses converged on the
   same replacement independently: census-intersect by equality. The 584 measured
   version-0 entries are the proof the loss is non-empty. v1 §2.5 is the one section of the
   incumbent that would have shipped the 0012 defect's mirror image.
2. **Extract keyed "only by the counter"** (v1 §2.1) — killed by R11 (counter churn is not
   change) and the fork's own shipped 92.7%-changed-forever defect. Replaced by the
   signals-vs-keys split (§2.1), which survived its critique intact.
3. **The two-column FTS split** (`meta_text`/`body_text`) — killed by the record ruling
   (fields keep identity) and by D5 (corpus-critic verified: with `'. '`-joined fields,
   unicode61 treats `.` as a separator, so a quoted phrase matches across the field seam).
   Replaced by per-field columns (§2.2).
4. **Collapse-to-items before ranking** (v1 §2.7) — killed by the entry ruling's own words
   ("an encyclopedic item may legitimately yield several distinct hits"). Replaced by
   entry collapse, score = MAX over chunks (§2.6).
5. **"The FTS statement joins the predicate down"** (v1 §2.7) — killed by #6012's
   measurement (rowid-constrained MATCH evaluates per row, seconds at library scale) and by
   upstream's own already-unconstrained statement. Replaced by unconstrained MATCH plus a
   *guaranteed-fill* bitmap filter (§2.7) — the naive "filter a truncated pool" variant was
   itself killed twice (corpus-critic M4, concurrency-critic M3) as R5's letter re-violated.
6. **The rejection of fraction-weighted RRF** (v1 §2.7) — overturned by arithmetic the
   query-critic verified empirically: every list crossing the fusion seam is higher-better
   and strictly positive at four verified lines (SQLite clamps idf, `-r.rank` stays
   positive), and `frac ∈ [0,1]` bounds every contribution *above* by plain RRF — v1's
   "degenerate single-hit list" objection was wrong arithmetic. Adopted behind D11's
   golden-set gate (§2.6).
7. **`frontierDate`-adjacent single-figure coverage and v1's §3.7 sentence** — killed by
   D1 (items denominator, metadata-only counts), the record ruling, and the entry unit for
   partials. Replaced by the operator lens's sentence and counter contract (§2.8).
8. **Pipe-only pause** — killed by R22 (verified: today's `stop` cancels one job and
   `auto_build` restarts on the next query). Replaced by the durable pause row (§2.9).
9. **Unconditional sideline-on-unknown-schema** (v1 §3.6) — killed by R13/R23 composition
   (concurrency lens): under N processes it is a denial-of-service one stale install
   inflicts on a fresh one. Replaced by read-compatibility gating, conductor-only sideline,
   and — the concurrency-critic's F1 repair — **a new filename** for the v2 schema, because
   no protocol can bind binaries that predate it: a v1.7.0 sibling reaching `clearStore()`
   against an in-place upgraded file would erase every library. `search-index-v2.sqlite`
   makes old binaries coexist on the old file and downgrade-keeps-serving falls out free.
10. **v1's PR6 (item-collapse) and PR1** — PR6 dies into the entries RFC (shipping
    item-collapse now would ship the ruling's rejected framing); PR1 is superseded by open
    PR #19.

---

## 2. The architecture

### 2.1 Signals vs keys (graft: derivation lens, survived critique whole)

Every stage row stores **signals** and **keys**, never mixed. A *signal* is a Zotero
version counter, scoped by server identity, only ever equality-compared; a mismatch
schedules *verification* (one fetch + one hash), never recompute. A *key* is
`(content hash, tool identity)`; work is stale iff stored key ≠ current key. R11 falls out
structurally: a resync flips signals, the verify pass re-hashes, hashes match, nothing
downstream moves — and the R27 counters record thousands of `resync.noop`s and zero
`resync.done`s, so the counter that once hid the 92.7% defect now proves its absence.
Stage keys: record = field-tagged `record_hash` (canonicalization version folded into the
tool identity, so a canon fix is a labeled key bump); extract = `text_hash` over the
streamed bytes; chunk = `(text_hash, seg_id+ver, chunker_id+geometry)` — the segmenter
lives inside the chunker key exactly as the boundary ruling directs; embed =
`embed_hash` = hash of the **full embedded text including the context prefix**
(query/corpus critics' M5 repair: hashing chunk text alone would let a vector computed
under an old heading serve under a new one, silently), with an EXISTS guard on shared-hash
deletes. Honest restatement of the R11 benefit: *unchanged regions never re-embed* — a
segmenter bump re-embeds what it actually touched, no more.

The disclosed R3 residue (concurrency-critic m3): a counter-churning resync still costs
O(changed-attachments) local fetches before hashes stop the chain — fetch-and-hash is the
price of verification, and it is stated, not hidden.

### 2.2 Storage: one file, one schema, every row library-keyed

`search-index-v2.sqlite` (WAL, `synchronous=NORMAL`, `busy_timeout=5000` on every
connection, `PRAGMA auto_vacuum=INCREMENTAL` set **before the first table** —
custody-critic M5: without it the promised idle `incremental_vacuum` is a no-op).

Identity (graft: concurrency lens): `origins(oid, server_id)` — the `Zotero-Server-ID`
partition SCOUTS mandates; `libraries(lib, oid, kind, remote_id, item_watermark, …)`.
**Every downstream row carries `lib`** (corpus-critic M3: Zotero keys are unique per
library; D4-merged without the column makes R15's delete an R12 violation), and every
delete is `WHERE lib = ?`. `clearStore()` is abolished from the build path — "rebuild" is
a ledger state (`UPDATE … SET status='pending' WHERE lib=?`), never a `DELETE FROM
passages` — R12 made unwritable for protocol-aware binaries, and the new filename (§1
kill 9) fences the binaries that are not.

The entry layer (graft: corpus lens, with its critic's F1 repair): `entries(eid, lib,
item_key, attachment_key, ordinal, heading, path, kind ∈ record|note|annotation|body|
synthetic, char_start, char_end, page_est, page_est_kind)`; `slabs(sid, lib, source ∈
attachment|record|note|annotation, source_key, char range, gzip bytes ≤1 MiB,
content_hash)` — the `source` column is the repair: **record and own-words text is slabbed
too**, or the first 100% (phase A) would ship hits whose snippets are underivable;
`passages(pid, eid, lib, item_key, sid, off_start, off_end, fp)` — **references, not
text** (#6012's discipline re-based onto our own slab store, so snippet re-derivation
never touches Zotero: gunzip one slab, slice, verify the fingerprint, null-rather-than-
wrong-words on mismatch). Slab cuts land on entry boundaries, not byte counts.

FTS5, per-field columns, `unicode61 remove_diacritics 2`:
`fts(title, abstract, creators, tags, pub, ctx, own, body)` — record rows fill the field
columns (a tag match no longer scores like a title match — the ruling's exact complaint);
body rows put chunk text in `body` and heading-path + item title in `ctx` (context matches,
weighted, without polluting `body`'s df or phrase positions); the *embedded* text is
`«title» › «heading path» ¶ «chunk»`, prefix charged to the token budget — Zotero's own
prior art. The query-critic's m4 repair is applied: creators, venue, and date have a
stated column mapping (creators/pub columns; date into the record row's `pub`), so no
field indexed today silently vanishes. bm25 column weights ship as a starting point and
are tuned against R21's golden set once it is re-pinned at entry granularity — not before
(corpus-critic m5). Contentless FTS (`content=''`, `contentless_delete=1`) where SQLite
≥ 3.43; v1's external-content layout is the probed fallback, chosen once, recorded in meta.

Chunking: **tokens on structural boundaries, 120 min / 768 max / 48 overlap** (Zotero's
geometry, adopted verbatim), never across entries, overlap only within a split paragraph.
For the record: the "upstream chunks below Zotero's minimum" jab holds only for its
512-char *metadata* stride; its 1,200-char body chunks are ~250–300 tokens, inside the
band (derivation-critic m2) — the move to token-structural chunking rests on the boundary
ruling, not on that line.

The segmenter `seg/1` (new machinery, corpus lens): line classification, heading
candidates (numbering patterns, case shape, and the dictionary's headword *rhythm* —
median gap and MAD over candidate spacing), entry cut at accepted headings, confidence =
fraction of text inside confirmed entries, fallback below 0.5 to **synthetic ~6k-token
entries** cut at paragraph boundaries, labeled. Palgrave arithmetic (input assumption
labeled, unmeasured): 44.9 MB / ~1,850 entries ≈ 24 KB ≈ 6k tokens ≈ 8–9 chunks each —
the monster becomes ~1,850 first-class peers, which is the entry ruling's whole point.
**The segmenter is the design's biggest unmeasured bet and is gated by X5 before the RFC
ships numbers** (§5, risk 1).

### 2.3 Discovery and fairness: records for everyone, then bodies, newest-first throughout

Phase order (the record ruling, all lenses concurring): **Phase A** — every item's record,
fields kept apart, globally newest-first across libraries (`date_added DESC` interleaved by
k-way merge on per-library sorted sweeps; recency is the researcher's notion and is
library-blind — concurrency lens). Cost arithmetic: a record is 1–2 chunks; 10k items ≈
12–15k record chunks at an assumed (labeled) 25 passages/s ≈ **8–10 minutes to D1's first
100%**. **Phase A′** — own words (R16, D7=both): child notes and annotations, crawled as a
second, itemType-filtered pass (verified gap: builds are `top:true`-only; standalone notes
are indexed today, child notes and annotations are not — corpus-critic m4's overbreadth
correction applied). **Phase B** — body text, entry-segmented, two-band frontier, derived K.

**The smallest-first decision, stated as sheet v2 requires**: #6012 orders attachments
smallest-first; our ratified R2 is newest-first. Rejected at item granularity, on R2's own
text — and honestly, per the derivation-critic's M2: the R26 observable is asserted at
stated granularities, **record coverage: strict newest-first prefix; body: band-0 coverage
is a newest-first prefix; band-1 is disclosed residue** — because the two-band cap itself
breaks a strict full-coverage prefix by construction, and one standard must bind both our
design and the rejected alternative. This granularity split is the one resolution in v2
made by interpretive fiat rather than verified fact: the sheet's R26 sentence does not
specify its own granularity, and the author can veto the reading. The band cap does the
anti-monopoly work smallest-first does for #6012.

D6 (first-with-text): per item, exactly one attachment indexed for body text —
deterministic first (ascending `dateAdded`, key tie-break) that appears in the fulltext
census; skipped attachments get a stored reason ("identical text, suppressed" / "different
text, not indexed under first-with-text") — honesty without reopening the decision. If a
later extraction gives an earlier attachment text, the choice function's output changes and
the chain re-derives — convergent by construction.

### 2.4 Freshness: census-equality where the sequence is mixed, a cursor where it is not

The reconcile tick (conductor-owned, 60 s idle cadence, backoff when unreachable), per
library:

1. **Items**: `?since=item_watermark@(oid,lib)` — a legitimate cursor; library versions are
   monotonic per backend, and the stamp is partitioned by server ID (SCOUTS; upstream's
   `local`/`cloud` label verified insufficient — the header machinery already exists at
   `local-writes.ts` to lift).
2. **Full text, local scope**: `/fulltext?since=0` census, equality-diffed per attachment
   against stored versions. **No fulltext watermark column exists for any local scope** —
   the mixed-sequence trap is schema-unrepresentable, the same unwritability move v1 used
   for the 0012 transposition. The per-scope qualifier is the derivation-critic's F1
   repair: v1's universal-census purity would have hammered api.zotero.org — **cloud
   scopes use an ordinary `?since=` cursor** on the genuinely monotonic web sequence, under
   the politeness constraint (≤4 concurrent; honor `Backoff` on any response including 2xx;
   429/`Retry-After` with exponential fallback — transport-scoped, from SCOUTS).
   Census cost stated, not laundered (three critics): ~8,037 entries ≈ 120–200 KB
   serialized per tick, O(attachments) in memory, zero extra requests; if X7 measures the
   parse above 50 ms at 30k entries, the cadence backs off to every 5th tick — a decision
   rule, not a hope.
3. **Deletions**: item-census subtraction every Nth tick (N=10 → ≤ ~10 min disclosed
   deletion latency; the `sync` verb forces it).

**The version-0 residue, resolved across four findings** (derivation M1, custody F1,
corpus M2, operator M3 — the one place all six documents collided): 584 of 8,037 measured
entries sit at version 0; a local re-extraction that stamps 0 again is invisible to
equality, and on a never-synced library that could be *every* entry. The composite
resolution, facts where they exist and an experiment where they don't: (i) **widen the
extract signal to `(fulltext version, attachment item md5/version)`** — a file replacement
bumps the attachment item in the item sequence the tick already sweeps, so file-driven
re-extraction is caught for free (custody-critic F1's repair, adopted); (ii) the remaining
residue — re-extraction with no file change — is **disclosed in the contract** as a
platform-aligned accepted staleness ("version-0 text refreshes on file change or rebuild";
Zotero's own embeddings layer documents the same residue); (iii) the derivation lens's
bounded idle re-verify sweep is **built only if X6 shows local re-extraction genuinely
re-stamps 0** — the experiment (re-extract one attachment on a synced and a never-synced
profile, watch the census; the empirical half of the already-drafted SYNC §4 issue) runs
before the machinery is written. No lens gets its first answer whole; every critic's kill
is honored.

Query path unchanged from v1: zero Zotero requests when the tick ran within ~30 s,
otherwise one memoized probe, 500 ms deadline, reports-and-nudges, `probedMsAgo` in
replies.

### 2.5 Topology and concurrency: N servers, one conductor, one worker (graft: concurrency lens, both FATALs repaired)

N × P0 is the *normal* deployment (one zoteus per MCP client on one fixed default dataDir —
verified). Every P0 answers queries (WAL readers, write-free query path). Exactly one is
**conductor** — elected by a lease row (`UPDATE leases SET holder=:uuid, expires_at=…
WHERE name='conductor' AND (holder=:uuid OR expires_at < :now)`; UUID, not recyclable pid;
a lockfile is rejected because lockfiles go stale exactly when the holder dies). Lease
timing per the concurrency-critic's M4: **TTL = 2× heartbeat (20 s), an election-check
cadence named in every server (10 s), migration gate < TTL + cadence = 30 s** — constants
that satisfy their own gate. The conductor runs the reconcile tick and owns the single P1
worker (`nice 19`, three ledger-paced loops), so the pipeline budget does not multiply.

The two orphan repairs (concurrency-critic F2, operator-critic M4, both mandatory): the
worker **exits on stdin EOF** (parent death) and re-verifies `leases.holder == parent-uuid`
between micro-batches, exiting on mismatch; and lease renewal runs on a **timer decoupled
from batch progress, renewed immediately before any long fetch** — the 44.9 MB single-GET
monster fetch has no micro-batch boundary inside it, and without these two lines "exactly
one P1" is a hope, not a mechanism.

Safety never depends on the singleton: per-row leases with the `claimed_input` commit guard
are the correctness layer, cross-process by construction. R13's letter is restated
honestly, as the concurrency lens confessed and its critic accepted once F2 was repaired:
**never committed twice; duplicate compute ≤ one micro-batch per failover** — the strict
letter has no implementation on a single-file SQLite substrate, and the design says so
rather than implying otherwise.

Foreground-beats-background across processes: each P0 touches `<dataDir>/activity` on
query arrival (a filesystem op — the query path stays write-free even in the DB sense);
the worker stats it between micro-batches and idles 2 s. The conductor's own stdio pipe
remains the low-latency fast path; `nice 19` remains the OS floor. Upstream's
BEGIN-at-first-mutation transaction is repaired *surgically* per the concurrency-critic's
M1: the **build path** commits per page (its 200-item/10 s persist cadence already exists;
the hold window shrinks below the busy_timeout), while the **update path keeps its
single-transaction rollback** — upstream's own comment is right that a half-applied delta
is a wrong index, not a partial one, and a PR that removed it would be caught by the
person who wrote it.

Sidecar discipline: conductor-only writes, generation-numbered
(`vectors-<embedderKey>.g<N>`), fsync + atomic rename, generation stamped in meta and
verified by scans; deletion tombstones cover **every live generation** (custody-critic
m2); compaction at >10% dead rows or the idle weekly slot.

### 2.6 Query path and ranking (graft: query lens, four MAJOR repairs applied)

**D5 semantics, granularity decided out loud** (query-critic M1): hard units — quoted
phrases, explicit AND, NOT — are filters; bare terms are soft, ranking, OR'd (today's
recall-friendly default kept deliberately). Phrases evaluate per passage (FTS5-native,
positions intact; a phrase straddling entries is correctly dead text). **AND and NOT
evaluate at *entry* scope**: one MATCH per hard term, id-lists joined on `eid` — AND =
every term hits ≥1 passage of the entry, NOT = no passage of the entry hits — a few id-set
operations over lists the design already fetches, one extra MATCH per hard term, trivially
inside R6. Passage-scope AND on a multi-chunk entry — the sheet-ratified hit unit — would
silently exclude legitimate hits, and the critic's construction proved it. Memory-backend
parity (query-critic M2): the phrase/AND/NOT check runs against a **fold-only, unfiltered
token stream** re-tokenized from stored text — the retained `tokenize()` arrays are
stopword-stripped and would make `"war and peace"` match "war versus peace" — and the
predicate is pushed inside `search()` before its top-k slice.

**Filters (R5, corrected)**: facets compile in SQL to an allowed-entry bitmap. Vector
scan: bitmap before the dot product (genuine pushdown — the loop is ours). Keyword: MATCH
runs **unconstrained** (#6012's measured economics; upstream already does this), pool
`max(8×limit, 256)`, bitmap applied to the candidate stream **with a fill guarantee**: the
ladder refetches deeper (4,096), then — for scopes ≤ ~20k passages — issues a constrained
MATCH via `json_each` (the query-critic verified `carray` does not exist in `node:sqlite`),
the threshold measured by X4, not trusted; then stops and answers honestly through R18's
`scope{}` block. No path ever post-filters a top-k and *claims completeness* — the
give-up is disclosed, which is the letter R5 and R18 jointly demand (corpus-critic M4,
concurrency-critic M3 both satisfied by the same loop).

**Entry collapse**: each engine collapses passages to entries *before ranks are assigned*
— entry score = MAX over its chunks (#6012, transposed to the ratified unit) — and the
vector scan does it **in a single pass with an entry-keyed top-S heap** (query-critic M4:
the refetch variant hid a second 650k scan, ~0.5–1 s by v1's own arithmetic, on exactly the
dictionary-heavy queries that trigger it). Presentation groups entries under items;
ranking never re-collapses. D9/R25 dissolve as the ruling says: the dictionary earns many
slots only with many genuinely distinct entries; concentration is still disclosed in
status.

**Fusion**: fraction-weighted RRF at k=60, adopted (v1's rejection overturned by verified
arithmetic, §1 kill 6), with the critic's repairs: `frac ∈ [0,1]` (0 = noise-suppressed,
stated); the seam invariant ("every ranked list higher-better, strictly positive") is a
unit-tested contract at the four verified lines; `frac_vec` defaults to **list-local
max-normalization** — #6012's calibration block (mean centering, noise floor = p99
unrelated, ceiling = median matched, reject bad models outright) is *deferred to its own
ticket* with a stated pair-generation protocol (title↔abstract of one item as matched
pairs, cross-item as unrelated: the library is the corpus), because as adopted it had no
data source and left `frac_vec` undefined at minute zero (query-critic M3). Ship gate
(D11): golden-set Jaccard ≥ the §2.8 thresholds against plain-RRF, both behind one flag.

**R24 locator**, discriminated by the hit's entry kind (a record or note hit has no
attachment and no page, and the reply never fabricates either): a **body** hit carries
`{itemKey, attachmentKey, entry heading/path (primary, per the ruling), charStart/End
(exact), pageEstimate + pageIsEstimate: true}` — the estimate computed within its
attachment from per-attachment totals that extraction now records instead of discarding
(verified: upstream keeps only `content` and concatenates, destroying the
offset→attachment mapping); `pageIsEstimate` is unconditional until a verified exact
mapping exists; the "concatenation caused the error" excuse is dropped (query-critic m2)
— the label is the honesty mechanism, not the excuse. A **record** hit carries
`{itemKey, field}`; a **note/annotation** hit `{itemKey, sourceKey}` (the annotation's
parent attachment and page, when Zotero supplies them, pass through as exact).

**R18**: an empty result names its scope in one of three disjoint sentences ("not indexed
yet (0 of 947)" / "partial: 812 of 947 — the miss may be coverage" / "fully covered —
nothing matches"), computed at query time from facet tables joined to ledger terminal
states — deliberately *not* a materialized counter (C4 governs the status path; R6 governs
this one). Under a strict query, one relaxed soft-MATCH count offers the drop-the-quotes
alternative.

**CJK**: v1 posture (multilingual embedder is the CJK path; typed `CJK_KEYWORD_DEGRADED`)
plus the scheduled companion now **2-gram** twin tables backfilled from slabs, query-routed,
fused as a third list. SentencePiece quadratic-encode caution inherited: cap encode
segments ~1,000 chars.

### 2.7 Custody and lifecycle (graft: custody lens, all five MAJOR repairs applied)

**R10** — verified: local by default, exactly two opt-in exfiltration paths, no silent
fallback. The sole permitted external call on the default path is the one-time weight
download, named in status, degrading to keyword-only and *never* to an API embedder (that
invariant gets a test). Every reply carries the one-line **custody string**. Consent gate:
auto-build default-on only for the free local embedder; API embedders quote cost and
require explicit go-ahead per index generation. Hygiene PR: the Gemini key moves from the
URL query string to the header.

**R15** — deletion rides the census tick; every copy has a named path: rows, FTS delete
protocol (upstream's correct discipline kept), passages, vectors, slabs (keyed per
attachment/source, never shared), sidecar tombstone bitmaps across **all** generations,
ledger rows (a worker's commit on a deleted item fails its guard), WAL/free pages
(`auto_vacuum=INCREMENTAL` now actually set — custody-critic M5 — plus idle checkpoint and
the `purge` verb = checkpoint + VACUUM + compaction), and the legacy `search-index.json`
(left in place forever by upstream; renamed `.migrated-<ts>` after first post-migration
save, swept at 30 days or `purge` — an *issue*, not a PR, because it reverses his
documented decision). **Pause never gates removal** (custody-critic M3: deletion
propagation is classified as removal, not derivation — one branch in the tick; without it
a paused index serves deleted text for months). The acceptance test decompresses slabs
before grepping (custody-critic m1: `strings` on gzip proves nothing). Byte-level
"gone" is eventual with a disclosed bound — stated as the negotiated reading of R15, per
the custody confession, for the author to veto.

**R22** — one meta row, written by `pause`, read before any scheduling decision: gates
worker spawn (a paused pipeline is zero processes — drain-then-shutdown grafted from
#6012), the tick's build side, and `auto_build` (verified: today any query against an
empty index starts a build). Does not gate queries, the probe, deletions, or explicit
verbs (`build` while paused asks — operator-critic m5's unspecified branch, specified).
Survives restart by construction; survives *sideline* by being carried into the fresh
file (custody-critic m4). R1-vs-R22 resolved in the user's favor, disclosed:
"paused since <date>".

**D3 serve-stale** — the verified violation (`dropStaleVectors` → `clearVectors()` at
open) dies. Per-row embedder keys; on a switch nothing drops; re-embed drains newest-first;
queries **dual-embed** during the window with each row scored in its own space — and the
old model is **lazy-loaded only when old-generation rows are in the pool, evicted after
~60 s idle**, falling back to labeled keyword-anchored fusion under memory pressure
(custody-critic M1: two resident models ≈ 240 MB + 70 + 32–64 busts the ratified 300 MB
for a days-long window; the repair keeps the budget honest at the price of a disclosed
cold-load spike). At most two generations; storage worst case 2× sidecar, disclosed. The
*small PR* version of D3 is rescoped per the derivation-critic's M3: upstream's one global
`embedderId` cannot support mixed spaces, so the contained fix is keep-vectors +
**pin the query-side embedder to the stored id** until a rebuild switches both; dual-embed
lives in the RFC.

**R23** — the open protocol: read `meta.schemaVersion` **before any DDL or write**
(verified defect: `createSchema` re-stamps via `INSERT OR REPLACE` before `loadMeta`, so
today a downgrade destroys the evidence of skew at the moment it matters); newer →
conductor-only sideline (never delete), fresh build, notice; older → versioned migrations;
plus `min_reader_version` so a too-old-but-aware server serves everything that never
touches the index and answers search with typed `SCHEMA_NEWER {remedy}`. The
ping-pong-downgrade hybrid state (custody-critic M4) is handled by its own tamper
evidence: `stamp==1 && v2 tables present` means an old binary wrote here — not "migrate"
but **reconcile-heal** (mark derived stages stale, census-diff, let R1 re-earn). The
retroactive limit is stated plainly: binaries ≤1.7.0 are unreachable; the new filename
(§1 kill 9) is what actually protects against them.

**R28** — pin `env.cacheDir` under dataDir before constructing the pipeline (the
transformers default lands outside dataDir per its documentation — documentation-cited,
not disk-verified, and the fix is correct regardless; the confession stands). Uninstall =
delete dataDir; `purge` + uninstall = byte-clean. **D2 hosted-out** deletes, explicitly:
per-tenant contract keying, multi-tenant consent bookkeeping, encryption-at-rest, quota
arithmetic — the four returned privacy lines stay dead.

### 2.8 The instrument panel (graft: operator lens, FATAL and M1/M2 repaired)

**The coverage sentence** (replaces v1 §3.7), D1 denominator = items, metadata-only
covered with reason, sections only ever the partial qualifier:

> "All 7,541 items are record-searchable (titles, abstracts, keywords — 100%, newest
> first). Body text: 5,561 of 6,100 items with attachments extracted and
> keyword-searchable back to 2016-04-11; 538 covered as metadata-only (no extractable
> text). Semantic: 2,101 items fully embedded back to 2019-09-02, newest first; 1
> partially embedded (record + 214 of ~1,850 entries — The New Palgrave). Building in
> background at idle priority; not paused. 1 quarantined: BHT7Q2 — extraction failed 3×;
> retries when its content changes."

(The flagship example's own arithmetic is now consistent — 5,561 extracted + 538
metadata-only + 1 quarantined = 6,100, the states disjoint — operator-critic m1 — and
"covered at extract" is defined once: items with no attachments are vacuously covered, the
"of 6,100" clause scopes the with-attachments subset, so `covered.embed == items.total` is
stateable on a real library.)

**Counters (C4)**: `counters(name, value)` updated **in the same transaction as the
ledger transition it describes**; per-stage `covered/empty/partial/outOfBand/quarantined`,
and work counters on two axes — `work.<stage>.<trigger>.<outcome>`, trigger ∈ `{new,
edit, re-extract, resync, key-bump, prefix-stale, retry, delete}` (R27's "which input"),
outcome ∈ `{noop, done}` (`noop` = signals moved, keys verified unchanged, nothing
recomputed; `done` = recomputed) — R27 needs both what triggered work and what became of
it, and one flat vocabulary cannot say both; the derivation-critic's m3 signal-noop
accounting lands as the `resync.noop` cell. Idle reconciliation recomputes with real
COUNTs, fixes, and increments a **surfaced** `drift` counter the harness fails on — a
counter that drifts is a status that lies. Status point reads are sub-ms against the
measured 374 ms cold scan. The accounting is the operator-critic's M1 repair, verbatim:
the boundary cursor is the **total-order key `(dateAdded, lib, itemKey)`**, never the
bare date — a tie group must be partially passable — and passes **settled** states
(`done|empty|quarantined|band0-done`); `outOfBand` is pure set-membership (covered items
older than the boundary, decremented as it sweeps); edit work counts only under the
`edit` trigger, and the record stage counts its own edits.

**The convergence harness (R26/R27)**: fixture library, empty dataDir, status polls at
1 Hz touching nothing else (R1 needs no asking). Asserts: status ≤ 50 ms; monotone
coverage; **prefix arithmetic per stage at the granularity §2.3 states** — `covered ==
|{(dateAdded, lib, itemKey) ≥ boundary}| − partial − quarantined + outOfBand`, the
boundary being the total-order key above, with the repaired definitions; terminal = all
stages at total, drift 0, `pipeline: idle` (the #6012 engine-shutdown observable), work
stationary. Phase 2: edit one title → exactly `work.record.edit.done == 1`,
`work.embed.edit.done == sections(record)`, everything else 0; then a simulated
identical-bytes resync → **zero recompute**: every `*.done` delta 0, the touched items
appearing only under `work.*.resync.noop` (§2.1 says verification runs — the gate must
permit exactly it and nothing downstream of it) — R11 measured by R27's own counters,
the test that would have caught the shipped 92.7% defect. **Phase 3** (the
critic's demanded fixture): one quarantine, one monster, dateAdded ties — the harness must
fail on the corpus that exercises its subtraction terms, not only pass on the gentle one.

**The gates** (Makefile: `check: lint figures fold-gate golden check-fast`;
`check-slow: check rss-gate convergence soak`):

- **R19 fold gate**: `fold_sweep.mjs` repointed at the tree under test, with the
  operator-critic's M2 repair — query-side falls back to `tokenize`-only when
  `normalizeForSearch` is absent, so against stock upstream the gate is red *by
  classification* (a recorded miss count), not red by crash; waiver keyed to PR #19's URL,
  deleted on merge.
- **R20 RSS gate**: deterministic synthetic monster at the measured 44,906,152 chars,
  entry-structured (~43k headings) so segmenter and band cap are exercised; assert worker
  `VmHWM ≤ 500 MB`, server p95 ≤ 300 MB — the budgets verbatim, against the artifact that
  measured 2,084.9 MiB when nobody was looking.
- **R21 golden gate, D11=set**: pinned multilingual fixture corpus, ~40 queries, answer
  *sets* at k=10. Thresholds re-derived from the artifact after the operator-critic's F1
  kill (the proposed 0.5 floor sat above the measured legitimate minimum of 0.25):
  **mean Jaccard ≥ 0.8; ≤ 5% of queries below 0.35; hard floor 0.2** — below the observed
  legitimate minimum, far above the failure class's measured 0.00. Order deliberately
  ungated (`identical_ordered` 22/60 under legitimate perturbation — an order gate flakes
  and gets turned off, which is how 0009 happened). Re-pins are commits whose set diff is
  the review artifact. The golden set is re-pinned at **entry granularity** when entries
  exist; until then it gates item-projections and says so.
- **R13 soak gate**: three P0s, full 10k drain, 1 query/s each, kill -9 the conductor
  twice; assert p95 ≤ 1.5 s, zero SQLITE_BUSY surfacing, WAL ≤ 256 MB, lease migration
  < 30 s, zero double-commits, duplicate compute ≤ 1 micro-batch per failover — v1's
  Risk 3 promoted to a gate, now with constants the protocol can meet.

**R13 observability**: the non-conductor reports `pipeline: "held-by-other"` instead of
silently duplicating work.

### 2.9 Budgets, recomputed and honestly scoped

Disk at the design point, token geometry (corpus-critic M1's recompute, both counts
stated): 768-token chunks ≈ 250–300k passages from the same corpus that yields 650k under
the old 1,200-char stride (bench comparability keeps the old count; budgets use the new).
FTS ~0.3–0.4 GB + gzip slabs ~0.23 GB (680 MB raw at ~3:1) + int8 sidecar ~0.1 GB
(300k × 384) + metadata/ledger ~0.1 GB ≈ **~0.8–0.9 GB** — under v1's 2.3 GB because the
passage text is no longer stored twice (references into slabs) and the chunks are fewer.
Float32 fallback adds ~0.35 GB.

RAM: P0 idle ≈ 70 (Node) + 32 (cache) ≈ ~100 MB; + ~120 MB query model on first semantic
use ≈ ~220–250 MB; one P1 ≈ ~250 MB steady, ≤ 500 MB transient hard-kill. Whole-machine at
two clients ≈ 2×220 + 250 ≈ **~690 MB steady** — stated, because "≤300 MB per process" is
a *re-scoping* of a ratified single-server number and re-ratifying it is the author's
call, not this panel's (concurrency-critic M5); the question is filed beside the scout
candidates. Dual-embed no longer threatens the budget (lazy-load repair, §2.7).

Warm query: probe 0–1 request + embed 20–50 ms + FTS tens of ms + single-pass sidecar scan
(X1) + fuse ≈ 300–700 ms typical, hard budget 3 s — unchanged, and now with the hidden
second scan deleted (§2.6).

---

## 3. Open decisions: committed, or experiments with decision rules

- **Semantic path at scale** — X1 unchanged (int8 ships at recall@30 ≥ 0.98, pool ≤
  32×topK, scan+rerank ≤ 400 ms at 650k; float32 slab is the permanent fallback), plus the
  single-pass entry-heap making pool guarantees free.
- **CJK** — committed: 2-gram twin tables, CJK-bearing passages only, backfilled from
  slabs, typed degradation meanwhile.
- **STOPWORDS** — shipped via PR #19 + follow-up; X2's latency guard unchanged.
- **Fairness** — committed: record phase then two-band body, K derived (§2.3), smallest-
  first rejected on the record.
- **Fraction-RRF** — conditional ship behind the golden gate; calibration deferred to its
  own ticket with the library-derived pair protocol.
- **Version-0 freshness residue** — **X6 decides**: if local re-extraction re-stamps 0,
  build the bounded re-verify sweep (M/tick, horizon reported); if it bumps anything
  observable, the md5-widened signal already catches it and the sweep is never built.
  Until X6 runs, the residue is disclosed, platform-aligned.
- **Census cadence** — **X7 decides**: local census every tick unless parse > 50 ms at 30k
  entries, then every 5th tick.
- **Constrained-MATCH threshold** — **X4 decides** (json_each, the mechanism that
  actually exists): cost curve at 1k/5k/20k/100k rowids on the 477k corpus turns the ~20k
  ladder step from an adjective into a constant.
- **Segmenter** — **X5 gates the RFC**: seg/1 over the real 44.9 MB extraction, 50
  hand-checked cut points; below acceptable precision the confidence gate rises and
  synthetic entries carry more of the corpus, honestly labeled.
- **Budget scoping under N processes** — deferred to the author as a ratification
  question, both figures stated (§2.9).

**Rejected this cycle, for the record**: cursoring any fulltext sequence on the local
transport (SCOUTS); a universal fulltext census across transports (derivation-critic F1);
passage-scope AND/NOT (query-critic M1); the stopword-filtered token stream for phrase
parity (M2); the always-resident dual model (custody-critic M1); the 0.5 golden floor
(operator-critic F1, artifact-refuted); item-granularity smallest-first (R2); trigram CJK
(2-char words); `carray` (not shipped in node:sqlite); in-place v2 schema under the old
filename (concurrency-critic F1); pause gating deletions (custody-critic M3); the
"contained" D3 PR as first proposed (derivation-critic M3).

---

## 4. The increment sequence from v1.7.0

Root: `/home/user/oscardvs/zoteus/src/features/search/`. SYNC.md's measured asymmetry
governs form: contained defect + failing test → **[PR]** (merged twice); design-sized →
**[issue]** he builds (#10, two for two). **[X]** = measure first. Gates are repo-side, in
this repo's Makefile, not PRs. PR #19 and #20 are already open upstream and are the head
of the train.

1. **PR #19** (open) — accent fold. On merge: delete the fold-gate waiver; land the
   STOPWORDS deletion + full Unicode split as its follow-up PR with X2's number.
2. **PR #20** (open) — corruption path.
3. **PR-1 [PR]** — schema read-before-write + conductor-aware sideline (§2.7 R23): open a
   `schemaVersion=99` fixture, assert not re-stamped and sidelined. After #20 (same file
   family).
4. **PR-2 [PR]** — `busy_timeout=5000` + per-page commits on the **build path only**,
   explicitly preserving the update path's single-transaction rollback (the
   concurrency-critic's M1 rescope; the two-handle SQLITE_BUSY repro is the failing test —
   reproduced empirically this cycle: default timeout 0, immediate throw).
5. **PR-3 [PR]** — cross-library wipe guard: a build for a different library than stamped
   refuses with a notice naming both, instead of `clearStore()` (the verified
   build.ts→reset→clearStore chain is the repro). The guard, not the feature.
6. **PR-4 [PR]** — pin `env.cacheDir` under dataDir (R28). **PR-5 [PR]** — Gemini key to
   header (R10). Cheapest custody wins; build merge history before the RFC.
7. **PR-6 [PR]** — per-attachment fulltext: stop concatenating, keep per-attachment
   `totalChars`/`totalPages`, deterministic first-with-text + stored skip reasons (D6,
   R24's load-bearing prerequisite).
8. **PR-7 [PR]** — R14 terminal recording: the warn-once becomes a stored reason;
   metadata-only counts enter status (D1).
9. **PR-8 [PR]** — persisted pause + `auto_build` gate + verbs residue (`purge`, confirm
   tokens) — the piece users feel first.
10. **PR-9 [PR]** — D3 minimal serve-stale: keep vectors, pin query embedder to the stored
    `vectorEmbedderId` until rebuild (the honest scope under one global key; failing test =
    open a db under a different `ZOTEUS_EMBEDDING_MODEL`, watch semantic coverage survive).
11. **PR-10 [PR]** — child notes + annotations crawl, itemType-filtered second pass (R16,
    D7), #6012 eligibility cited.
12. **PR-11 [PR]** — D5 query compiler with entry-scope AND/NOT and the fold-only parity
    stream (after #19; the failing test proves `"general equilibrium"` retrieves
    either-word today). **PR-12 [PR]** — fraction-RRF behind a flag, seam-invariant test,
    golden Jaccard in the body.
13. **Issues, filed early**: **I-1** the fulltext-delta/mixed-sequence question (drafted
    FINAL per SYNC — now upgraded from question to finding: `startIndexUpdate` keys on
    `libraryVersion` alone, so post-build extraction is invisible to `action:"update"`;
    X6 is its empirical annex). **I-2** the measurement corrections (drafted FINAL).
    **I-3** the 40k cap vs R9 (design-sized: streaming; #10's history says he builds it).
    **I-4** legacy JSON retirement (reverses a documented decision — issue, not PR).
14. **The RFC [issue]** — one design conversation, not four: the ledger with signals-vs-
    keys, the entries schema + slab references + segmenter (X5-gated), the lib-keyed
    store under the new filename, the conductor protocol with both F-repairs in the text,
    record-first frontier, dual-embed migration, counters + the convergence harness
    offered as the acceptance spec he can run against whatever he builds. Opened after the
    PR train establishes credibility; the contract survives even if he reimplements the
    machinery in his own idiom — which is where C2 says the durable value lives.
15. **[X] before their dependents**: X1 (vector layout/int8) before the sidecar work; X4
    (json_each cost) before PR-11's ladder constant; X5 (segmenter) before the RFC's
    numbers; X6 (version-0 dynamics) with I-1; X7 (census parse) before the tick cadence
    is documented. X3 (monster RSS) feeds the rss-gate fixture.

---

## 5. The biggest remaining risks, and the cheapest falsifiers

**Risk 1 — the segmenter is unmeasured, and everything downstream inherits it.** Entry
collapse, locators, dedup, the golden re-pin, and the Palgrave arithmetic all stand on
seg/1's error rate on flat `/fulltext` text, which has never touched the real 44.9 MB
extraction; its failure mode is *silent plausible-looking entries* — wrong citeable
locators and wrong dedup units, worse than honest synthetic ones. Both the corpus and
query lenses confessed it; both critics ratified it as the genuine top risk. *Falsifier:*
X5 — run seg/1 over the real extraction, hand-check 50 cut points; half a day, before the
RFC claims numbers. Below acceptable precision, the design degrades gracefully to labeled
synthetic entries — the contract survives, the "1,850 peers" story does not.

**Risk 2 — the version-0 freshness residue could be the whole story, not the residue.**
On a never-synced library the census may be structurally blind to every re-extraction; the
md5-widening catches file-driven changes, but if X6 shows re-extraction bumps nothing
observable, "coverage: current" is a lie the design can only disclose, not fix — an honest
but ugly amendment to the freshness contract. *Falsifier:* X6 — re-extract one attachment
on a synced and a never-synced profile, watch the census and the item version; an
afternoon, and I-1 is already drafted to carry the answer upstream.

**Risk 3 — the maintainer reimplements the core underneath us, faster than the RFC
converses.** Sharpened since v1: he built #10's answer himself in days, and #6012's
saved-search serialization is the first crack through which platform semantic results will
leak into the local API. *Falsifier:* the RFC issue itself, after the PR train — one
thread settles fork-vs-upstream for the cost of writing it; the hedge is structural (every
stage behind a key; the contract, counters, and harness are ours whoever writes the
machinery).

**Risk 4 — N-process reality diverges from the protocol on exactly the edges the soak
must catch.** The conductor election, activity-file yield, and lease timing are designed
against named failure states (orphaned worker, mid-monster steal, torn sidecar) but
unmeasured; filesystem mtime granularity and WAL growth are folklore until soaked.
*Falsifier:* the §2.8 soak gate — scripted, 30 minutes, kill -9 twice; its assertions are
now constants the protocol can arithmetically meet, so a failure is information, not
noise.

**Risk 5 — gate decay.** The fold gate runs red-with-waiver until #19 merges; rss and
convergence sit in `check-slow`; a 14-day-stale WARN is advisory. This is the
normalization-of-deviance channel that produced 0011, reintroduced at a slower time
constant with better signage — designed around, not away, and named so the author can
choose to tighten it. *Falsifier:* none needed — the risk is organizational; the
mitigation is that every gate's threshold now cites the artifact that justifies it, so
re-pins and waivers leave evidence.

---

The bet, in one sentence: the same ledger still makes every failure boring and the same
contract still makes every answer honest — what cycle 2 adds is that the units are now the
ones the author ratified (entries, records, items), the freshness protocol can no longer
be fooled by the counter it watches, N processes are a designed state instead of an
accident, and every promise the sheet makes is either watched by a gate whose threshold
cites its artifact or named as one of five experiments, each falsifiable for less than a
day before the expensive code exists.
