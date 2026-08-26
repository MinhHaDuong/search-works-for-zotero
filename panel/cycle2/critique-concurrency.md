# CRITIQUE — cycle-2 memo: MULTI-LIBRARY & CONCURRENCY

*Adversarial review against sheet v2 (DESIGN.md rulings + ratified DELTA + SCOUTS), upstream
verified at `/home/user/oscardvs/zoteus` HEAD `edf2748`, with one new empirical measurement.*

## Verification of the fact base (memo §"Verified facts")

All seven facts re-verified independently. Fact 1: `defaultDataDir()` at paths.ts:5-10 ✓.
Fact 2: the keyed-by-context doc-comment at build.ts:184-190 and `startIndexBuild` paging at
199-227 ✓. Fact 3: build.ts:220 → index-manager.ts:467 `reset()` → :387-388 `clearStore()` →
sqlite-index.ts:307-316 (`delete-all` + `DELETE FROM passages` + `DELETE FROM items`) ✓;
semantic-search.ts takes no library input ✓. Fact 4: `items (item_key TEXT PRIMARY KEY, ...)`
at sqlite-index.ts:129, unscoped deletes at :172-173 ✓. Fact 5: grep for
`busy_timeout|SQLITE_BUSY|busyTimeout` over src/ returns zero ✓. Fact 6: begin-on-first-
mutation at :192-197, commit-only-in-flush/save at :462-472, persist cadence 200 items / 10 s
at index-manager.ts:472-473 ✓. Fact 7: `isBuilding` throw at :447-448; meta cached from
`loadMeta()` at open ✓.

**New measurement.** I ran the two-handle repro the memo's PR-A promises (Node v22.22.2,
`node:sqlite`, WAL): default `busy_timeout` is 0, and the second handle's first write while
the first holds an open write transaction throws `database is locked` after **0 ms**;
concurrent reads succeed. The memo's most load-bearing citation is not only correctly read,
it reproduces. That part of the memo is armored.

## FATAL

**F1 — The b.7 skew protocol cannot bind the process it exists for: a stale v1.7.0 sibling
wipes the new multi-library store, resurrecting the exact R12 violation the memo claims to
have "made unwritable."** b.1 keeps the table names (`items`, `passages`) and, by silence,
the filename (`search-index.sqlite`). b.7's `min_reader_version` is read only by binaries
that implement it — v1.7.0 writes `schemaVersion` and never reads it (verified;
sqlite-index.ts:151-153, loadMeta:210-224 reads no schemaVersion). So in the deployment the
memo itself calls normal (N servers, one dataDir, upgraded one client at a time), the
not-yet-upgraded zoteus opens the new file, `CREATE TABLE IF NOT EXISTS` no-ops, and any
build/rebuild path reaches `clearStore()`: `DELETE FROM passages; DELETE FROM items` succeeds
against the new schema (deletes violate no NOT NULL), *then* its inserts fail on the `lib`
column — every library erased, nothing rebuilt. R12 ("indexing one never erases another") and
R23 both die in one scenario, and the memo's centerpiece sentence — clearStore abolished,
R12 unwritable-to-violate — is false against the one writer it cannot legislate for: old
code. **Cheapest repair:** the new schema lives under a new filename
(`search-index-v2.sqlite` or equivalent); old binaries then coexist on the old file,
downgrade-keeps-serving falls out for free, and b.7's protocol only has to govern
protocol-aware versions — which is all it ever could.

**F2 — The orphaned-worker state: "exactly one P1" and "at most one duplicated micro-batch
per failover" have no mechanism behind them.** b.5.1: conductor killed (the soak's own
kill -9 case) → lease expires → another server elects itself and spawns its worker. Nothing
stated terminates the dead conductor's child. SIGKILL of the parent does not kill the child;
the worker's loop reads the ledger and stats the activity file — it may never touch the
broken pipe, so no SIGPIPE arrives. The zombie keeps claiming fresh ledger rows
indefinitely: two P1 processes, 2 × 500 MB and 2 cores (b.6's "the pipeline budget does not
multiply" is now false), and unbounded duplicate *compute* — the commit guard prevents
double-commit, but "at most one duplicated micro-batch" (Confession 1's carefully weakened
R13 claim) is wrong by an unbounded factor. The b.9 soak asserts "duplicate compute ≤ 1
micro-batch per failover" — the design fails its own gate as written. **Cheapest repair:**
two lines of protocol: the worker exits on stdin EOF (parent death), and re-verifies
`leases.holder == parent-UUID` between micro-batches, exiting on mismatch. Both must be
*stated*; neither currently is.

## MAJOR

**M1 — PR-A misreads what the long transaction buys, and its own arithmetic doesn't close.**
(a) The memo calls upstream's BEGIN-until-save "nothing but the write lock." Verified
otherwise: the update path *deliberately* uses the single open transaction as its atomicity
guarantee — index-manager.ts:762-771 rolls back a failed delta because "a half-applied delta
is not a partial index but a wrong one," via sqlite-index.ts rollback():372-381. Convert to
commit-per-batch and a failed update lands in precisely the committed-half-applied state
upstream's comment names as the worse one. A PR built on this misread gets caught in review
by the author of that comment. (b) The build path *already is* commit-per-persist-batch:
`persist = () => this.save()` fires every 200 items / 10 s (index-manager.ts:472-480,
sqlite-index.ts:469-472). "Converting BEGIN-until-save to commit-per-persist-batch" is a
description of the status quo. (c) The real hold window is that ~10 s persist interval —
which spans async embed awaits, so it can stretch further — and PR-A's `busy_timeout = 5000`
covers half of it: a second writer can wait 5 s and still throw. **Repair:** rescope PR-A as
busy_timeout + *more frequent commits on the build path only* (e.g., per page), explicitly
preserving the update path's single-transaction rollback; state the timeout ≥ worst-case
hold, or bound the hold below the timeout.

**M2 — The census-intersect has a blind spot exactly where SCOUTS pointed: version 0.** b.2
re-queues a key when census version ≠ stored version. SCOUTS: locally-extracted text reports
version **0**. First extraction: NULL ≠ 0, caught. *Re*-extraction on a local profile
(re-run OCR, replaced PDF re-extracted locally): 0 == 0 — equality-compare never fires, the
re-fetch never happens, so `content_hash` is never consulted, and the design serves the old
text forever while coverage reports complete. The memo's claim that b.2 depends on the SYNC
§4 answer "only in degree, not in kind" is false in the 0-stays-0 world (unless the parent
item version bumps — the exact unverified question §4 asks): there the mechanism is blind in
kind. **Repair:** a slow-cadence hash-check sweep over version-0 rows (re-fetch, compare
`content_hash`), or hold b.2's final shape behind §4's answer instead of filing it as
independent.

**M3 — "Bitmap applied to MATCH candidates after unconstrained evaluation" is ambiguous at
the point that decides correctness.** If it means a SQL predicate on the joined content
table between MATCH and LIMIT, it is right. If it means JS filtering of a LIMIT-k pool
(upstream's keyword statement is `... MATCH ? ORDER BY rank LIMIT ?`, sqlite-index.ts:178-184,
and "candidates after evaluation" reads that way), then a scoped query whose hits rank below
the pool returns a false "No matches" — serving a wrong answer and gutting R18's honesty for
exactly the filtered case R18 exists for. The scout finding forbids constraining the MATCH
*expression*; it does not license filtering after a truncated pool. **Repair:** one
sentence — the bitmap/predicate applies before LIMIT (or: iterate the rank-ordered cursor
until topK filtered hits accumulate).

**M4 — The lease arithmetic contradicts itself and its gate.** Heartbeat 10 s, expiry
`now+30`: "two missed beats and any server's next tick steals" is wrong (expiry is three
beats); worst case the conductor dies just after renewing, the lease is valid for 30 more
seconds, and the steal additionally waits for a poll — yet b.9 gates "conductor lease
migrates < 30 s," unsatisfiable by the protocol's own constants. Compounding: §a says "the
tick runs in the conductor, not in every server," yet the steal happens on "any server's
next tick" — non-conductors have no stated timer at all. **Repair:** TTL = 2× heartbeat
(20 s), a named election-check cadence in every server (e.g., 10 s), gate at
< TTL + cadence.

**M5 — A ratified budget is silently re-ratified, and "total" hides the worker.** C3's
"server steady-state RSS ≤ ~300 MB" was ratified verbatim under a one-server model; b.6
declares it per-process by fiat ("C3's server budget is per-process and the docs say so").
The arithmetic given is right (2 × (70+32+120) = 444), but "444 MB total" is not the total:
the machine also runs the conductor's P1 (~250 MB steady, 500 MB transient) — ~694 MB steady
for two clients, ~944 MB peak, on the user's machine C3 protects. Reinterpreting a ratified
number is the author's call, not the architect's. **Repair:** one line marking per-process
scoping as a ratification question beside the scout candidates, and state the whole-machine
figure.

## MINOR

1. The 374 ms cold GROUP BY is cited to `bench/results/0013-concentration/`; the artifact
   there (`uncapped-477512.json`) does not contain it — the figure lives in STATE.md:185.
   Citation is honest in substance, wrong in address (inherited from the delta).
2. b.8's coverage sentence names "conductor: pid 4711" after b.5.1 rejected pid as
   recyclable in favor of a UUID. Cosmetic self-contradiction.
3. R11 is met for *derivation* but the memo never states the residual cost: a resync that
   churns counters on identical bytes still triggers an O(changed-attachments) full-text
   re-*fetch* over local HTTP before hashes stop the chain. Should be disclosed as R3
   residue.
4. Non-conductor election attempts are 0-row UPDATEs that still take the write lock briefly;
   harmless under busy_timeout but worth a word, since the query path's "write-free"
   guarantee is per-query, not per-process.

## CONFESSIONS — real or decoys?

Confession 2 (Server-ID unverified on local transport) is real and correctly weighted — it
also silently underwrites PR-B, which needs a canonical library identity to refuse
cross-library builds; upstream stamps *no* library identity today, and the doc-comment's
whole point (build.ts:184-190) is that the same personal library legitimately arrives as
local `users/0` and as cloud `users/<id>` — a naive "different from stamped" guard refuses a
legitimate backend switch. PR-B is salvageable but underspecified on exactly Confession 2's
axis. Confession 3 is real but small. Confession 1 is the decoy problem: it agonizes over
the *letter* of R13 while the bigger hole is that even the weakened claim ("≤ 1 micro-batch
per failover") is unsupported (F2) — and the largest concurrency hole of all, the
non-participating old binary (F1), goes unconfessed although R23 was the requirement under
amendment.

## SURVIVED ATTACK

- All seven verified facts check out line-for-line at `edf2748`; the SQLITE_BUSY repro
  reproduces empirically (timeout 0, immediate throw, reads unaffected).
- Killing the fulltext watermark for per-attachment equality + census-intersect is correct
  against SCOUTS' mixed-sequence trap, and making the cursor schema-unrepresentable is a
  genuine structural win (modulo M2's version-0 residue).
- The `lib`-keyed schema with clearStore abolished from the build path is the right shape
  for R12/D4-merged and composes with D3 serve-stale (modulo F1's filename hole).
- DB-lease election over a lockfile survives: single-statement CAS under the discipline
  everything already uses; the stale-lockfile objection is correct.
- Per-row leases as the safety layer with the conductor as pure efficiency is the right
  decomposition (once F2's exit rule exists).
- The (item, entry) dedup amendment and phase-order composition statement match the entry
  and record rulings exactly; the write-free query path plus activity-file floor is sound.
- Budget multiplication arithmetic itself (444 = 2×222) is correct as far as it goes.

## TALLY

FATAL 2 (F1 stale-binary wipe defeats b.7/R12; F2 orphaned P1 worker), MAJOR 5 (M1 PR-A
misread + timeout arithmetic; M2 version-0 census blindness; M3 filtered-MATCH ambiguity;
M4 lease timing vs its own gate; M5 budget re-ratification), MINOR 4. Both FATALs have
one-line repairs (new filename; worker exit rule) — the design frame survives, but neither
repair is optional, and both belong in ISSUE-C's text before it is filed.
