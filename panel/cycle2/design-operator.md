# Design memo, cycle 2 — OPERATOR & GATES lens

*Architect: operator/gates seat, design cycle 2, 2026-08-26. Input: DESIGN.md (sheet v2 with ratification log), DESIGN-DELTA.md (R10–R28, C4, D1–D11 resolved), SCOUTS.md, SYNC.md, DESIGN-V1.md. Code verified this session against upstream v1.7.0 at `/home/user/oscardvs/zoteus` (HEAD edf2748); artifacts cited from `/home/user/zoteus-fts5/bench/results/`.*

The one-sentence position of this memo: **v1's machinery mostly survives; what sheet v2 adds is that almost none of v1's promises are *observable*, and the delta makes observability itself the requirement** (R17, R19–R22, R26, R27, C4). Cycle 1 designed the engine; cycle 2 must design the instrument panel and the gates that keep it honest, because this repo's own history is a list of promises broken silently until someone happened to look (0011: "a few hundred MB" measured at 2,084.9 MiB peak, `bench/results/0011-rss/capped-vs-uncapped.json`; 0009: Jaccard 0.00 under a green suite).

---

## (a) VERDICTS ON V1

**§1 The skeleton (ledger, two planes).** SURVIVES — and is *promoted*: C4 (status from counters, never a scan) and R27 (edit-one-count-one) are only satisfiable because every state change already flows through one ledger transaction, which is exactly where a counter can be updated atomically. One AMEND: v1 never addresses R13 (two zoteus on one dataDir). Leases plus `busy_timeout=4000` prevent corruption but not duplicate work; add a single-pipeline role lease (§b.6).

**§2.1 Storage.** SURVIVES with two AMENDs. (1) Scout finding: version validity is scoped by `Zotero-Server-ID`; v1's "backend label" on the watermarks is insufficient — two local profiles share the label and share nothing else. All watermark/meta rows become keyed by server ID. (2) The record ruling: two FTS columns (`meta_text`/`body_text`) lose field identity, which the ruling forbids — the record's fields (title/abstract/keywords/…) need their own columns and weights. Detail belongs to the ranking seat; the operator consequence is mine: the **record stage** becomes a first-class ledger stage with its own counters and boundary date, because D1 makes "record coverage is the first 100%" the first number the status must report.

**§2.2 Discovery (census-seeded frontier).** SURVIVES — the scout confirmed the census is the documented deletion route (no `/deleted` on local API).

**§2.3 Topology.** SURVIVES. Adopt two #6012 pacing behaviors as *observables*: engine shut down when the queue drains (status must show `pipeline: idle`, which is also R26's terminal state) and refuse-to-start under low free memory as a typed degradation, not a log line.

**§2.4 Fairness (recency-major, K=64 band).** AMEND. The entry ruling changes the unit: band 0 is "the record plus the first K *sections*", not the first 64 passages — the ruling says the record is indexed before any body text, for everyone, newest-first. The scout's note that Zotero's own fairness is smallest-first-within-attachments *composes* with newest-first, but composing is a ratification decision; this design keeps sheet-v2 newest-first with the section-cap and *declares* the composition option unadopted. Operator consequence: partially-embedded monsters must be visible (`partial` counter, §b.2) or R26's prefix assertion is false.

**§2.5 Freshness.** One phrase is DEAD: v1's "`/fulltext?since=` ascending completed-version-group sweep" cursors the mixed sequence. Scout: the sequence mixes web stamps / local client versions / 0 for local extraction — equality-comparable per item, never a monotonic cursor; ordering by it silently loses locally-extracted text (version 0 sorts first, forever "already passed"). Replace with **census-intersect**: fetch the full `/fulltext?since=0` map each tick (8,037 entries measured, one request, `0012-fulltext-sequence/sequences.json`), compare per attachment stored-vs-current by *equality*, mark unequal ones stale. The tick's clock, not the counter, provides progress. The rest of §2.5 (probe-don't-fix, both-sequence watermarks) SURVIVES.

**§2.6 Failure policy.** SURVIVES; R14 confirms the `empty` tombstone (upstream today warns once and re-encounters forever — `fulltext-source.ts:131-137` warns on `failures++ === 0` only, records nothing). AMEND: `empty` rows count as *covered, metadata-only* in the D1 items denominator, with the reason stored, and the count surfaced.

**§2.7 Query & ranking.** Two AMENDs, both from sheet v2. (1) The entry ruling kills item-collapse as the dedup: the unit of answer is the SECTION — collapse passages to *sections* (score = MAX over a section's chunks, per #6012's fusion prior art), then bound items per answer page only for diversity, letting an encyclopedic item legitimately yield several entry hits. (2) R5's "pushed into SQL" is WRONG as v1 implements it for FTS: scout — constraining MATCH to a rowid set makes FTS5 evaluate per row, seconds at library scale; #6012 runs MATCH unconstrained and filters in JS. Amend: metadata-side filters compile to the bitmap as before, but the FTS leg runs MATCH unconstrained and applies the bitmap to candidates *after*, in JS; only pure-metadata queries push predicates into SQL. The vector leg keeps the pre-scan bitmap (that one is ours, not FTS5's).

**§2.8 The contract.** AMEND — full replacement in (b): items denominator, per-stage boundary dates, `outOfBand`/`partial` fields the convergence harness needs, persisted pause, new degradation codes.

**§2.9 Budgets.** SURVIVES as numbers; DEAD as *practice* until gated (R20). The Makefile today gates lint, figures, pytest only (`/home/user/zoteus-fts5/Makefile:21`, `check: lint figures check-fast`) — no RSS assertion exists, which is how 0011 happened.

**§3.1 vector path, §3.2 CJK, §3.3 stopwords, §3.5 topology decision, §3.6 self-description.** SURVIVE. Notes: §3.3's tokenizer fix is now *delivered* as open PR #19 (upstream `tokenize.ts:7-10` is still the live defect: `/[a-z0-9]+/g` plus 29 English stopwords); §3.6 gains the Server-ID partition and R23's explicit downgrade branch (older schema reader meets newer file → sideline + rebuild is already specified; state that it holds in both directions). §3.2's trigram plan should become 2-gram to match #6012's Han/Kana/Hangul twin tables — platform alignment, C2.

**§3.4.** As §2.4: AMEND.

**§3.7 The coverage sentence.** DEAD as written. Three faults under sheet v2: the denominator is unstated (D1 resolves it: ITEMS, metadata-only counts); metadata-only items are invisible in it (they must be counted covered, with the reason); and "3 oversized documents have tails still embedding" has no unit — under the entry ruling the partial qualifier is *sections*. Full replacement in (b.1).

**§4 Increment sequence.** AMEND — PR1 is superseded by open PR #19; PR #20 (corruption) delivers part of PR4/PR8; the freshness PR must be preceded by the drafted §4 issue (mixed-sequence trap); the ledger RFC becomes an issue by SYNC's measured asymmetry. Details in (c).

**§5 Risks.** SURVIVES; add gate-decay as a named risk (see confessions).

---

## (b) THE DESIGN — operator machinery, full replacement text

### b.1 The coverage sentence (replaces v1 §3.7)

Denominator: **items** (D1). An item is *covered* at a stage when every eligible unit under it reached a terminal state (`done` or `empty`). Metadata-only items are covered (their record is indexed; their extract row is `empty` with a stored reason). Per stage, most-recent-covered date. Sections appear only as the partial qualifier, never as a denominator. Mid-build, verbatim:

> "All 7,541 items are record-searchable (titles, abstracts, keywords — 100%, newest first). Body text: 5,562 of 6,100 items with attachments are extracted and keyword-searchable back to 2016-04-11; 538 items have no extractable text (scanned PDFs) and are covered as metadata-only. Semantic: 2,101 items fully embedded back to 2019-09-02, newest first; 1 item partially embedded (record + 214 of ~43,000 entries — The New Palgrave). Building in background at idle priority; not paused. 1 item quarantined: BHT7Q2 — extraction failed 3×; retries automatically when Zotero re-extracts it."

At steady state this collapses to "All 7,541 items fully searchable (record + body text + semantic); index idle." The first clause — record coverage — is the first 100% to arrive, per the record ruling, and it is the number that answers "is my library searchable at all."

### b.2 Counters and the status contract (C4, replaces v1 §2.8's coverage block)

**Schema.**

```sql
CREATE TABLE counters(name TEXT PRIMARY KEY, value INTEGER NOT NULL);
-- meta(k,v) rows, all namespaced by Zotero-Server-ID:
--   'watermark.items.<serverId>', 'watermark.fulltext.<serverId>',
--   'boundary.<stage>' (ISO dateAdded), 'paused', 'schema', artifact keys.
```

**The counter set** (per stage ∈ {record, extract, chunk, embed} unless noted):

- `items.total` — census size (updated in the reconcile-tick transaction that inserts/deletes item rows).
- `covered.<stage>` — items terminal at that stage.
- `empty.extract` — the metadata-only count (subset of `covered.extract`).
- `partial.embed` — items with record+band-0 done but section tail pending (monsters).
- `outOfBand.<stage>` — items covered *ahead of* the frontier prefix (edit-triggered work that jumped the queue).
- `quarantined.<stage>`.
- `work.<stage>.<trigger>` — cumulative units processed, trigger ∈ {census, delta, edit, reextract, keybump, retry, manual}. Units: items for record/extract, sections for chunk/embed, plus `work.embed.batches`.
- `counters.drift` — reconciliation mismatches ever observed (see below).

**Update discipline.** Every counter mutation happens **in the same transaction as the ledger-row transition it describes** — the claim-commit that marks an extract `done` also does `UPDATE counters SET value=value+1 WHERE name='covered.extract'` and the matching `work.*` increment. Boundary advance: each stage keeps a frontier cursor into the recency-ordered item list; a commit that closes the head of the contiguous terminal run walks the cursor forward (amortized O(N) over a whole build) and writes `boundary.<stage>` in that same transaction. Nothing about status ever reads the passages, vectors, or ledger tables.

**Reconciliation.** The idle reconcile tick (pipeline idle ≥ 60s) recomputes each counter with a real `COUNT(*)`, fixes any mismatch, and increments `counters.drift`. Drift is not a repair detail — it is *surfaced in status* and the convergence harness fails on `drift > 0`, because a counter that drifts is a status that lies, which is C4's whole point. Cost basis: the convenient GROUP-BY scan was measured at 374 ms cold against the table a build writes (DELTA C4 evidence); point reads on a 30-row counters table are sub-millisecond, so status answers in a few ms while all three loops run.

**Status reply shape** (the JSON under the sentence):

```json
{ "itemsTotal": 7541, "paused": false, "pipeline": "building|idle",
  "serverId": "…", "drift": 0,
  "stages": {
    "record":  {"covered":7541,"boundary":null,"partial":0,"outOfBand":0,"quarantined":0},
    "extract": {"covered":6100,"empty":538,"boundary":"2016-04-11","outOfBand":0,"quarantined":1},
    "chunk":   {"covered":6099,"boundary":"2016-04-11","outOfBand":0,"quarantined":0},
    "embed":   {"covered":2101,"boundary":"2019-09-02","partial":1,"outOfBand":0,"quarantined":0}},
  "partials":[{"item":"DH8EXSVA","sectionsDone":214,"sectionsTotal":43000}],
  "quarantined":[{"item":"BHT7Q2","stage":"extract","reason":"…","clearsOn":"re-extraction"}],
  "work": { "embed": {"edit":1,"delta":214,"census":132001,"…":0}, "…": {} },
  "freshness": { "…": "as v1 §2.5, both sequences, probedMsAgo" },
  "degradations":[ … ] }
```

R18's scoped answer ("this collection is 0% indexed") is *not* a materialized counter — per-scope coverage for arbitrary collection subtrees is computed at query time from the facet tables joined to ledger terminal states, indexed on `(item_key, stage, status)`. That is a bounded ms-scale join on the **query** path, governed by R6's budget; C4 governs the **status** path, which stays counters-only. The division is deliberate and stated.

### b.3 The convergence harness (R26)

New driver `bench/convergence_watch.py`. It creates a fixture library with a known manifest (item keys, dateAdded values, deliberately tie-free), starts zoteus on an **empty** dataDir, and then touches nothing but `zotero_index action:"status"` at 1 Hz — it never calls build, because R1 says convergence needs no asking. Per poll it asserts:

1. **Latency**: status reply ≤ 50 ms (C4 made observable).
2. **Monotonicity**: every `covered.*` non-decreasing; every `boundary.*` moves only older; every `work.*` non-decreasing.
3. **Prefix-ness** — the answer to "what must be exposed": the harness owns the fixture's dateAdded histogram, so four numbers per stage pin the covered set as a most-recent-first prefix *without a set dump*: assert `covered == |{items : dateAdded ≥ boundary}| − partial − quarantined + outOfBand`, with `outOfBand == 0` in phase 1 (no edits). If status exposes covered/boundary/partial/outOfBand/quarantined per stage, prefix-ness is pure arithmetic against ground truth the harness already holds. Without `outOfBand` the assertion is unstateable the moment an edit jumps the queue — that field exists *for the harness*.
4. **Terminal**: `covered.embed == items.total` (fixture has no quarantines), `partial == 0`, `drift == 0`, `pipeline == "idle"` (the #6012-style engine-shutdown observable), and all `work.*` stationary across three further polls.

**Phase 2 — R27/R11**: edit one item's title; assert exactly `Δwork.chunk.edit == 1`, `Δwork.embed.edit == 1` (item's record sections), all other work cells 0, `outOfBand.embed == 1`, then boundary arithmetic re-holds. Then simulate a resync that bumps versions on identical bytes; assert **all** `work.*` deltas are 0 — R11 measured by the very counters R27 obliges. This is the test that would have caught the shipped 92.7%-changed-forever defect (`0012-fulltext-sequence/sequences.json`: `since=410` → 7,453 of 8,037 entries reported changed).

Tier: `make check-slow` (minutes), nightly and before any release/measurement claim.

### b.4 The gates (R19, R20, R21) — Makefile as the enforcement point

Today: `check: lint figures check-fast` (`Makefile:21`). It becomes:

```make
check:      lint figures fold-gate golden check-fast
check-slow: check rss-gate convergence
```

**R19 — fold gate.** `bench/fold_sweep.mjs` exists and works by construction (real FTS5 table + `fts5vocab` readback vs the shipped JS tokenizer — nothing reimplemented). Two changes wire it in: (1) repoint its `--fork` default from the retired `fork/` checkout (`fold_sweep.mjs:35` imports `${opt.fork}dist/features/search/tokenize.js`) to the tree under test at `/home/user/oscardvs/zoteus`, with an `npm run build` prerequisite; (2) a 20-line assert script that fails on `misses > 0` in the likely-typed set — `misses` being the sweep's own classification for "query token goes where the index is not", the 0009 defect class. Run against v1.7.0 stock the gate is **red today** (upstream `tokenize.ts:8` shreds every non-ASCII query), which is correct: the gate carries a named waiver keyed to the open PR #19 URL, and deleting the waiver is part of confirming the merge. A red gate with a linked waiver beats a gate that can't be turned on — and the gate's reason to exist is exactly R19's evidence: upstream re-shipped the byte-identical broken file once already; regression-by-copy is the proven class.

**R20 — RSS gate.** `make rss-gate`: a deterministic generator emits a synthetic monster — 44,906,152 chars (the measured dictionary size, `0011-rss/capped-vs-uncapped.json` method note), entry-structured with ~43k headings so the segmenter and the section cap are actually exercised. The driver builds it through the pipeline while sampling `/proc/<pid>/status` `VmHWM` for the worker and RSS at 2 Hz for the server under a 1 query/s loop. Assertions are the ratified budgets verbatim: worker `VmHWM ≤ 500 MB`, server p95 RSS ≤ 300 MB. The gate's reason: the uncapped build measured **2,084.9 MiB** peak against **404.1 MiB** with the one dictionary truncated (5.16×, same artifact) — the budget was broken by one document and found only because someone looked. Minutes of runtime → `check-slow` tier; `check` prints a WARN when the last `rss-gate` artifact (`bench/results/gates/latest.json`, datestamped) is older than 14 days, so decay is at least visible.

**R21 — golden gate, D11=SET.** `bench/golden/`: a pinned fixture corpus (committed, ~200 items, FR/DE/VI/EL/RU text), ~40 queries (seed from `bench/queries.txt`), and `golden.json` mapping each query to its item-key **set** at k=10 after section-collapse. `make golden` builds the fixture index, runs every query through the real backend, computes per-query Jaccard against golden. **Thresholds: per-query Jaccard ≥ 0.5 (hard floor) and mean ≥ 0.8.** Justification from 0013 (`uncapped-477512.json`): under the largest *legitimate* perturbation ever measured here — the 42,963-passage dominant item entering/leaving results — the random sample (n=60) held `mean_jaccard = 0.8753` with `rest_retention = 0.9693` (the "97% of the set survives" figure), and the worst legitimate per-query value observed was 0.5385 (purposive set); the failure class the gate exists to catch measured **0.00** (0009, real French queries, green suite). Legitimate ≥ 0.54, broken = 0.00: 0.5/0.8 sit inside that empty gap with margin. Order is deliberately *not* gated: `identical_ordered` was 22/60 under legitimate perturbation — an order gate would flake on ~2/3 of queries and get turned off, which is how 0009 happened (compare.py existed; the ritual was manual). Intentional ranking changes re-pin `golden.json` in the same commit; the set diff is the review artifact. Fast (seconds) → `check` tier, every commit.

### b.5 Pause (R22, amends v1 §2.8 verbs)

Verified defect pair: `action:"stop"` only calls `requestStop()` on the running job (`index-tool.ts:56-64`), and `auto_build !== false` starts a fresh build on the next semantic query (`semantic-search.ts:48-50`) — so today the user has no standing veto; stop is un-stopped by the next search. Design: `pause` writes `meta('paused','1')` in its own transaction and (1) the worker's claim loop refuses all claims while set, (2) `auto_build` checks it and answers "index is paused by you; resume with zotero_index action:'resume'" instead of building, (3) the reconcile tick still *observes* (cheap reads) but schedules nothing. It survives restart because it is a DB row, and it is scoped by dataDir so R13's second process obeys it too. `resume` deletes the row. Status carries `paused: true` and a typed degradation `PAUSED_BY_USER {remedy:"resume"}`. `stop` keeps its current one-job meaning, documented as such.

Degradations list gains, beyond v1's: `PAUSED_BY_USER`; `STALE_VECTORS_SERVING` (D3: `dropStaleVectors` — `index-manager.ts:286`, invoked at `:304` and `:890` — currently zeroes semantic coverage at open/on dim-mismatch; serve-stale means old vectors keep answering, labeled, until re-embedding overtakes newest-first); `SCOPE_UNINDEXED` (R18, from the query-time scope join in b.2); `LOW_MEMORY_DEFERRED` (the #6012-style refusal, typed).

### b.6 Second-process observability (R13, new)

One `pipeline_lease` meta row (holder pid + host + expiry, renewed each micro-batch, stealable when expired). The second zoteus answers queries (WAL readers coexist) and reports `pipeline: "held-by-other"` in status rather than silently running a duplicate embed pass — R13's "no passage embedded twice" made observable, not just hoped.

---

## (c) INCREMENT IMPACT on v1 §4

- **PR1 is delivered**: open **PR #19** is v1's PR1 plus the 445-codepoint generated case set — strictly stronger. Repo-side, the fold gate (b.4) waives-on-#19 until merge, then the waiver is deleted.
- **PR #20** (corruption, open) delivers the sideline/typed-error half of v1's PR4+PR8; what remains of PR4 is the schema *read-back* (verified still missing: `SCHEMA_VERSION` written at `sqlite-index.ts:26,153`, never compared on open) plus artifact keys and the Server-ID partition — still small, still PR-shaped.
- **PR2 splits**: PR2a = status-from-counters + coverage v0 in the D1 items denominator (counters table + same-transaction increments, the statusSummary rewrite — `build.ts:135-160` today narrates one job's machinery, not library coverage); PR2b = persisted pause (tiny: one meta row, two checks in `index-tool.ts`/`semantic-search.ts`). Both match the merged-twice shape: contained defect, failing test included.
- **PR7 (freshness) is amended and re-ordered**: the drafted §4 issue (mixed-sequence trap, SYNC marks it FINAL) files *first*; PR7's fulltext leg becomes census-intersect per b's §2.5 amendment. This is the one place a v1 PR would have shipped a scout-refuted design.
- **PR9 (the ledger) changes form**: SYNC's asymmetry is two-for-two — design-sized asks as issues get built by the maintainer himself (#10). PR9 becomes an **issue whose body is the acceptance spec**: the counter contract (b.2) and the convergence harness (b.3), with our harness offered as the test he can run against whatever he builds. That is the C2 move: the machinery is his to reimplement; the observable contract, and the harness that enforces it, is the durable value and stays ours either way.
- **The gates are repo-side, not PRs**: fold/golden/rss/convergence live in this repo's Makefile and harness, pointed at his tree. Only their *fixtures-as-tests* travel upstream when small (the fold cases already ride #19).
- PR3, PR5, PR6 (amended to section-collapse), PR8-residue, PR10–13 keep v1's order, renumbered.

---

## (d) CONFESSIONS

1. **The prefix arithmetic is brittle at dateAdded ties.** Real libraries have bulk imports sharing a timestamp; "prefix by dateAdded" is then ambiguous at the boundary and the b.3 equality can misreport by the tie-group size. The harness fixture dodges this by construction (tie-free), which means the assertion is proven on a corpus gentler than reality. Mitigation — order by (dateAdded, itemKey) internally — is designed but adds a sort key the Zotero API itself won't honor on the crawl.
2. **The golden thresholds transfer an argument, not a measurement.** 0.5/0.8 are justified from 0013's *corpus* perturbation (dominant item enters/leaves) on one library, n=60+12 queries; the gate guards *code* changes on a pinned corpus, a different perturbation family. The gap [0.0, 0.54] is real but measured once, and a legitimate future change (e.g. the section-collapse itself) may land inside it and force a re-pin that reviewers rubber-stamp.
3. **Gate decay is designed around, not away.** rss-gate and the convergence harness sit in `check-slow` because minutes-long gates in `check` get skipped — but a WARN on a 14-day-stale artifact is advisory, and the fold gate runs red-with-waiver until #19 merges. Both are exactly the normalization-of-deviance channel that produced 0011, reintroduced at a slower time constant and with better signage. If the maintainer never merges #19, the waiver becomes permanent furniture and R19 is satisfied on paper only.
