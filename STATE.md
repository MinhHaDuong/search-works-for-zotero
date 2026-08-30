# STATE — Search Works for Zotero

*Repository state reconciled 2026-08-30 evening (housekeeping run
2026-08-30T16:45Z) — 46 tickets closed, 39 open; reviewed upstream baseline
v1.10.0 (`b132f2d`); the in-container and workstation halves of 0025 are both
measured and decided, `RUNBOOK.md` sunset per its own clause; superseded
implementation archived at `archive/fts5-storage-2026-08-21`. See `SYNC.md`.*

*Embedder study, 2026-08-29/30 — the measurement train and recommendation
review ran to completion in one day; PR #110 merged. Children 0261–0267 and
the follow-ups 0481/0482 are closed and
merged: the registry (`bench/models.json`, with pooling, input template,
normalize and revision per model, each guarded), the resumable sweep harness
(`bench/sweep.py`), the CPU arm, the corrected GPU arm on padme (the first
arm's fidelity cells had silently run on CPU — a dropped `--device` flag,
ticket 0481), recall at the deployed dtype plus the first fused-RRF delta,
and the cross-lingual probe. Ratified along the way: R30 (GPU acceleration
is a requirement), C3 re-pinned at ~750 MB p95, X8's rule in DESIGN §3.
The study does not select the implementation default. Tracker 0488 now carries
the invariant-first registry path: singleton extraction, authoritative fields,
curated entry selection, local automatic compatibility validation, optional
content-free attestations, and only then a ship/default decision. The separate
ticket 0491 asks whether a future autonomous embedding service belongs in
zoteus at all; it does not block the registry. The upstream design text is
`verification/ISSUE-DRAFT-0488.md`. Ticket 0485 carries the X8-bar task-metric
check; ticket 0486 carries the normalize-consumer gap.*

Operational handoff and measurement record for the open workshop on semantic
retrieval in Zotero. Zoteus is the current reference implementation and
upstream contribution target; Zotero core, including PR #6012 and its
successors, is an equally important influence point.

## Current handoff — 2026-08-28

This work session is safe to close. The tracking repository is clean on `main`.
The ignored upstream checkout was last left on `schema-read-before-write` at
`fd51659` — since merged upstream; `make upstream-checkout` recreates `fork/`
at the current baseline.

- [Upstream PR #25](https://github.com/oscardvs/zoteus/pull/25), implementing
  ticket 0015, was **merged 2026-08-28**, the same day it was filed — `fd51659`
  sits in upstream `main` verbatim, and v1.9.0 ships it. Ticket 0015 is closed;
  fork `main` was re-aligned to `bb414df` and the merged
  `schema-read-before-write` branch deleted the same day. The fork carries
  `main`, `stopwords-follow-up`, `cross-library-guard`, and the archive
  branch (SYNC.md).
- [Upstream issue #24](https://github.com/oscardvs/zoteus/issues/24) is the
  existing thread for ticket 0033's resume slice. Our requirements/performance
  comment is already the only reply; do not add another unless the maintainer
  responds or the design changes materially.
- [Upstream issue #26](https://github.com/oscardvs/zoteus/issues/26) now carries
  ticket 0024's I-1 finding: post-build full-text extraction is invisible to an
  update keyed only by `libraryVersion`. Await the maintainer's response before
  extending it; I-2 remains ready, while I-3 stays behind its checkpoint.
- `origin/stopwords-follow-up` is at `94d994d`; its tree is unchanged from
  `4a5e554`. **X2 ran on 2026-08-29 and the branch failed it.** On the real
  477 512-passage index the stopword-less warm p95 is 1 773,0 ms against the
  ~500 ms rule, while a stock-v1.9.0 control arm on the same index and the same
  twenty queries answers at 392,3 ms — so the deletion is the cause (4,5× on
  p95, 5,7× on the median) and DESIGN §3 requires df-driven pruning inside this
  PR rather than after it. Two further blockers, independent of the number: the
  PR body's claim that `to be or not to be` tokenizes to nothing is false
  (`tokenize()` returns `["not"]` on stock, since `not` was never on the
  29-word list), and both in-flight slots are spent. Artifacts:
  `bench/results/0025-x2-stopwordless/`; the reasoning is on tickets 0014/0025.
- **Both in-flight upstream slots are spent**, on #27 and #28 (filed
  2026-08-28, both open). The bullet that used to sit here said they were free
  again after #25 merged; that reading predates those two filings, and SYNC.md's
  status table has carried the correct state since. Ticket 0016's PR-3 is
  **built** and waiting on a slot, not on a measurement: fork branch
  `cross-library-guard` (`61a0e38`, one commit atop `bb414df`), validated on
  upstream's own gates (typecheck, lint, build; 754 passed / 7 skipped),
  pre-filled form at RUNBOOK.md's PR B.
- The harness runs on the system interpreter on doudou: `make check` is green
  (ruff clean, 160 figure pairs / 0 stale, 38 tests), with ruff 0.15.21 and
  pytest 9.0.2 on PATH. No `.venv` exists in the repo and none is needed. The
  earlier note here — that the venv was unusable because `python` was missing
  and `ruff` segfaulted — described the handoff container, not this machine.

## What this repo is

Public design record, ticket store, and measurement harness for an
implementation-neutral work programme. The current reference code lives in a
**fork of someone else's project**. `fork/` is a plain checkout of
`MinhHaDuong/zoteus` (upstream `oscardvs/zoteus`) and is git-ignored here — it
has its own history, and a `tickets/` directory must never appear in it, or it
would show up in any diff sent upstream.

## The upstream baseline and archived implementation

`UPSTREAM` records the reviewed upstream baseline, currently **`bb414df`**
(v1.9.0). `make upstream-status` detects movement beyond it;
`make upstream-checkout` recreates the git-ignored `fork/` with `origin` set to
`MinhHaDuong/zoteus`, `upstream` set to `oscardvs/zoteus`, and a detached
checkout at the exact reviewed SHA.

The superseded implementation is preserved on
**`archive/fts5-storage-2026-08-21`**, head **`bae82a7`**, where **757 tests**,
`tsc --noEmit` and `eslint` were clean. Its base combined PR #11 and PR #12,
which upstream has since merged; it is evidence, not a working branch.

## Posture — the maintainer answered on 2026-08-25

He merged #11 and #12 (both with review follow-ups that found real defects in
them), and then **built the SQLite/FTS5 backend himself**, closing #10 and
shipping it in v1.7.0 with incremental updates on top. His seam is a `SearchIndex`
interface plus `SearchIndexBase`; ours was a `PassageStore` port under the one
index. Same problem, same absence of a new dependency, different cut.

So the storage layer here is superseded, and the experiment has done its job: it
was the argument, not the shipping code. The plan of record is **DESIGN.md §4
as ratified in DECISIONS.md, executed through tickets 0014–0037**; **SYNC.md**
tracks upstream — what he took, what is still missing there (the accented-query
defect, live in v1.7.0, was fixed by PR #19's merge in v1.7.2), and the harness
rename that must land before any number in this file is quoted about upstream
(ticket 0030).

Everything below this line was measured against `bae82a7` on the pre-merge base
and stands as that tree's record. None of it has been re-measured against v1.7.0.

## Upstream, at the cycle-2 verification baseline

Cycle 2 verified against head `edf2748`, v1.7.0 (released 2026-08-25). The
tree has already moved past it: v1.7.1 shipped 2026-08-26 (`80f8aa0` fixing
#18, `2cde6a7`) without touching then-open PRs #19/#20; on 2026-08-27 both
merged and v1.7.2/v1.7.3/v1.8.0 followed in one day. What upstream took and
built is SYNC.md's account, stated once there.

## The comparison, on one corpus

Every earlier version of this table compared columns that were not comparable —
different corpora, different geometries, one number measured here and one
inherited from before the first commit. This one does not, and the difference is
worth stating plainly: **both backends read the same 360 811 passages.**

The SQLite side is that crawl's own `search-index.json`, migrated in place. Not
two crawls that ought to agree — the same rows.

| | resident JS (json) | SQLite/FTS5 |
|---|---|---|
| passages | 360 811 | 360 811 |
| items | 7 541 | 7 541 |
| startup to first answer | **90,87 s** | **3,86 s** |
| resident after load (`VmHWM`) | **5 406,1 MiB** | **121,1 MiB** |
| resident after 16 queries | **5 759,6 MiB** | **128,0 MiB** |
| on disk | 463,3 MiB | 712,9 MiB |

**45x less memory and 23x faster to answer, like for like.** Artifacts and the
per-query rows in `bench/results/0001-old-vs-new/`; drivers `bench/query.py` and
`bench/compare.py`, instrument `/proc/<pid>/status VmHWM` on both sides.

**The one caveat measurement cannot remove, quantified.** RSS excludes the
kernel page cache holding the database file, and the JS heap figure has no such
remainder. Charge the SQLite side the *whole* 712,9 MiB file — the most
pessimistic reading available — and it is 840,9 MiB against 5 759,6 MiB, a
**6,8x** win rather than 45x. Both numbers are measured, on the same corpus, and
any external claim should carry both. The direction is not in question either
way; the ratio depends on which question is asked.

**A previous entry here said no strictly comparable at-rest number existed.**
That was true of the geometries then in hand: the JSON backend cannot reach the
uncapped 477 512-passage index at all (see below), so it could not be compared
against the column FTS5 was measured at. The answer was to measure both at a
geometry *both* can reach, which is what the table above is.

## The wall the JSON backend hits

Measured 2026-08-21/22 on a ladder of geometries, `bench/results/json-baseline/`:

| geometry | passages | build peak | at rest | persists? |
|---|---|---|---|---|
| 5 000 items | — | 5 132,5 MiB | 3 788,3 MiB | yes |
| 6 000 items | — | 6 264,7 MiB | 4 603,0 MiB | yes |
| 7 000 items | — | 6 986,4 MiB | 5 316,0 MiB | yes |
| all items, 200 000 chars | 360 811 | 6 862,0 MiB | 5 673,5 MiB | yes |
| all items, **uncapped** | 477 512 | **8 691,5 MiB** | — | **no — `Invalid string length`, x3** |

The uncapped rung is the structural wall this work exists for: the build
completes, holds 477 512 passages in the heap, and then cannot write them.
`Invalid string length` is Node's `RangeError` for a string past V8's maximum
(536 870 888 characters), and `saveIndex` builds one with `JSON.stringify`.

**Stated as an attribution, not as an isolation.** The failure is consistent
with the string limit and the message is V8's canonical one for it, but the
probe did not record the length at the moment of failure or capture a stack
inside `JSON.stringify`. Reproduced three times; cause consistent, not proven.
Logging the length at the catch site would settle it and has not been done.

The at-rest ladder is linear in passages (16,09 to 16,35 kB/passage across every
rung, a 1,6% spread) and the build peak sublinear, so the resident cost is a
property of the corpus rather than of any one run.

## The FTS5 side at full size

Uncapped, the geometry the JSON backend cannot persist at (2026-08-22,
`bench/results/0011-rss/uncapped-build-3.json`, driver `bench/run_build.py`):

| | |
|---|---|
| passages | **477 512** |
| build wall clock | 371,6 s |
| peak RSS during build | **1 848,8 MiB** |
| on disk | 949,4 MiB + 166,7 MiB WAL |

Reproduces the two earlier runs (1 892 and 2 085 MiB) within their spread. The
build is API-bound, not SQLite-bound.

**477 512, not 477 511.** Earlier artifacts say 477 511 and are not wrong: the
library gained one top-level item between them (7 540 → 7 541). Both numbers are
correct as of their own crawl, and harmonising them would have hidden a real
change.

## Peak build memory is ~1,85 GB, and it is one book (0011)

0003 anticipated "a few hundred MB" and that is **not met** — a promise this
work programme should not have made in that form. The honest headline is **~1,85 GB
peak during build, ~128 MiB at rest**, and every place that said otherwise now
says this.

The cause is isolated: **one 44,9 MB document**. Capping per-item characters at
2 000 000 cuts the peak 5,2x, to 404 MiB
(`bench/results/0011-rss/capped-vs-uncapped.json`).

**Zoteus ships no such cap by default** — decided by the author 2026-08-22.
`fulltext_max_chars` exists for anyone who wants one, and the 2 M figure is
documented as the value that buys the reduction, but turning it on changes what
is indexed, so it is the user's call and not a default.

## One dictionary is 9% of the index (0013)

*The New Palgrave Dictionary of Economics* holds **42 963 of 477 512
passages**, against 1 450 for the next largest item — a 30x gap. It depresses
BM25's idf for the vocabulary it saturates, measured against FTS5's own
`fts5vocab` counts:

| term | df | df without it | idf shift |
|---|---|---|---|
| keynes | 1 819 | 346 | **+28,1%** |
| walras | 831 | 157 | **+24,7%** |
| ricardo | 1 218 | 275 | +23,3% |
| equilibrium | 11 616 | 4 908 | +20,6% |
| climate | 62 026 | 61 853 | −4,5% |

**What that does to the ranking, corrected.** An earlier reading said the effect
"almost entirely cancels" and that "in two of three, every other result keeps
its exact order". Re-measured through **FTS5's own `bm25()`** rather than a
re-implementation of it, over 12 purposive queries *and* 60 seeded random term
pairs drawn from the index's own mid-frequency vocabulary:

- **97% of the non-dominant results survive** the idf change — the answer *set*
  is essentially unaffected.
- **Relative order among them is preserved in only 5/12 purposive and 37/60
  random queries.** Order moves in roughly half.

So: it does not change *what* you find, it does reshuffle *the order* far more
often than "negligible" allowed. That is a weaker case for a ceiling than the
first reading suggested and still not a case for one — which is where the
no-cap decision above lands. Artifact `bench/results/0013-concentration/`,
driver `bench/index_concentration.mjs`.

The distribution is a **documented query**, not a `status()` field: `GROUP BY
item` costs 374 ms cold on that index and `status` is polled throughout a build,
against the table the build is writing. Written up in the fork's
`docs/semantic-search.md`.

## Migration, measured to the full size (0005)

Three points on real indexes, the largest being the 463 MB case that stayed open
since filing. Driver `bench/migrate_measure.mjs`, which records Node version,
`NODE_OPTIONS`, both file sizes and `VmHWM` into its own output.

| | 105 MB | 321 MB | **463 MB** |
|---|---|---|---|
| migration, isolated | 13,7 s | 42,7 s | **55,5 s** |
| **peak RSS** (`VmHWM`) | 80,7 MiB | 97,0 MiB | **93,2 MiB** |
| resulting database | 162,3 MB | 498,7 MB | **747,5 MB** |
| ratio to JSON | 1,5416 | 1,5522 | **1,5388** |

**The third point changes the reading.** Two points showed 80,7 → 97,0 MiB and
were described here as "strongly sublinear, not flat". The third, at 4,4x the
smallest file, comes in at 93,2 MiB — *below* the middle point. So the curve
rises early and then **flattens**: there is a size-dependent component that
saturates well before the full size, not one that keeps growing. Two points
could not have shown that, and the earlier wording over-read them.

For comparison the JSON backend loading its own indexes costs roughly 11,8x the
file and linearly. The database/JSON ratio holds at **1,54x** across all three
sizes.

## Accented queries: fixed, and the sweep found the fix incomplete

`toMatchQuery` tokenised with `/[a-z0-9]+/g`, so `théorie` became `"th" OR
"orie"` while FTS5 had folded the document side to `theorie`. Jaccard 0,00
against the JSON backend — twenty confident, entirely wrong results. Fixed
Zotero's way: fold in JS on both sides, token class widened to `/[\p{L}\p{N}]+/u`.

**Measured on the full library, after the fix** (`bench/results/0001-old-vs-new/`):
each accented query and its unaccented spelling now return *identical* answers —
`théorie`/`theorie` both 0,889 against the JSON backend, `mathématiques`/
`mathematiques` both 0,429, `probabilità`/`probabilita` both 1,000. The shift
that was the defect is gone.

**The codepoint sweep the ticket described in prose was then actually run**, and
it contradicted the prose. `bench/fold_sweep.mjs` puts 1 301 codepoints through
a real FTS5 table declared with the shipped tokenizer and compares what SQLite
stores against what the shipped JS fold produces. It found 27 divergences, of
which **twelve sent a query to a token the index does not hold** — 0009's own
defect class on rarer input, not the "all toward retrieving less" the ticket
claimed. `Ǽgir` queried as `ægir`, which other documents genuinely contain.

Ten were letters whose base is itself non-ASCII Latin (`Ǡ Ǣ Ǯ Ǽ Ǿ`), two were
gaps in unicode61's Greek case table (`U+037F`, `U+0374`). All twelve are fixed;
the sweep now reports **1 286 of 1 301 agreeing and no query going where the
index is not**. The residual fifteen are unassigned or symbol codepoints that
unicode61 indexes and `\p{L}\p{N}` does not — those genuinely only retrieve less.

The first attempt at that fix put two nested shields in one placeholder block
and handed the outer restore the inner's character. The test written to pin the
twelve is what caught it.

## The delta compared two unrelated sequences (0012)

`delta.ts` correctly asks `fullTextSince` about re-extracted attachments, and
handed it the wrong counter. Measured on the live local API and committed as
`bench/results/0012-fulltext-sequence/sequences.json`:

| | |
|---|---|
| library version (`Last-Modified-Version`) | **410** |
| full-text versions | **0 … 25 036**, median 12 884, over 8 037 entries |
| entries returned by `/fulltext?since=410` | **7 453** — 92,7% of the library |

Every delta reported nearly the whole library as newly extracted, quietly:
`maxItems` capped the set, so the handful that had genuinely changed were lost
in map order among ~7 400 candidates, each costing a `getItem`, and the next
delta was no closer because the number being advanced belonged to the other
sequence.

0006 guards carefully against exactly this class *across backends* — that is
what `indexBackend` is for — and then compared two unrelated sequences *inside*
one backend. **Guarding one instance of a defect class does not guard the class.**

Fixed: a second watermark, seeded free from the `/fulltext?since=0` read the
build already makes, swept in ascending version order, advanced only past
versions swept completely so a truncated sweep resumes rather than re-reads.

## A corrupt index now refuses and reports (0010)

There was no corruption path at all: `SQLITE_CORRUPT` propagated out of a
constructor as SQLite's own sentence, failing every query, again after every
restart. It is now a typed error naming the file, its two sidecars and the
command, and the server survives it — item lookups and bibliographies never
touch the index.

**Refuse, never rebuild**, decided by the author 2026-08-22: the caller is an
agent mid-task who cannot consent to an unrequested re-crawl of several minutes.
Refusing rather than answering emptily is the load-bearing half — an empty
answer reads to an agent as an empty library. Deleting the file also clears the
watermark that lives inside it, so the recovery sidesteps the
empty-index-claims-current trap rather than having to guard against it.

## Chunk geometry is configuration (0007)

Three hardcoded constants and a pair of default arguments decided every passage
count this work ever reported. They are `ZOTEUS_CHUNK_SIZE`,
`ZOTEUS_CHUNK_OVERLAP`, `ZOTEUS_FULLTEXT_CHUNK_SIZE` and
`ZOTEUS_FULLTEXT_CHUNK_OVERLAP` now, with defaults byte-identical to what
shipped, pinned against their literal values. The geometry is stamped beside the
watermark and a mismatch rebuilds: otherwise one environment variable makes the
index a silent mixture of two populations.

**Structure-aware chunking is reachable, on one trigger only.** Zotero 10 ships
`Zotero.SDT` (`sdt.js`, `structured-document-text.js`) writing a
`.zotero-sdt-cache` pack with page labels, outline paths and running-head
exclusion. Three probes over ten hours found **zero packs**, and a fourth —
after the author opened two PDFs in the reader on 2026-08-22 — found **two,
within a minute, for exactly those two items**
(`bench/results/0007-sdt-probe.txt`).

So: **full-text extraction never produces a pack** (1 036 post-install
extractions, zero packs) and **the reader does**. The earlier reading, that
extraction is ruled out and the reader path is merely "narrowed", implied a
verdict on SDT that was wrong; the correction is at the end of closed ticket
0007. That fourth probe is also the first with a **positive control** —
`.zotero-reader-state` appears for both items, so the probe demonstrably sees
the path it is testing, where the first three could not distinguish "no packs"
from "could not look".

Two things bound what this opens. Packs are lazy and per reading session:
**2 of 13 631 attachments** with extracted text have one, and no bulk operation
this project can invoke will make more — so SDT is an *enrichment* for papers a
user actually reads, never a general chunking input. The second bound is now
retired: the pack is a custom binary container (magic
`89 53 44 54 0d 0a 1a 0a`, a u32 offset table), but its sections **are** raw
deflate, and reading one needs neither vendoring nor reimplementing Zotero's
decoder. `verification/probes/sdt_read.py` is that reader, ~200 lines with tests, and it
parses both packs on this machine. Cost known, not estimated.

## Binary quantization, now measured on real vectors (0008)

Proposed on a measured 13x speedup taken at `k=30`, which did not survive being
asked for a *pool*: vec0's k-best structure costs more than linearly in `k`. On
a clustered fixture the pool that preserved the ranking (16x) was slower than
the exact scan it replaced, so the two-stage path shipped **off by default**.

**93 022 real passages, embedded by the shipped on-device model, settle the
criterion that stayed open** (`bench/results/0008-real-vectors/`, driver
`bench/vec_real_measure.mjs`):

| pool | fixture | **real** | centred | two-stage | vs exact (103,3 ms) |
|---|---|---|---|---|---|
| 4x (k=120) | 0,628 | **0,884** | 0,918 | 34,4 ms | **~3,0x faster** |
| 8x (k=240) | 0,862 | **0,953** | 0,969 | 61,5 ms | **~1,7x faster** |
| 16x (k=480) | 0,998 | 0,986 | 0,991 | 120,7 ms | ~0,85x — slower |

On disk: **1 563,2 B per float32 vector against 71,1 B per binary code, 22x**.

Latencies are timed round robin rather than in per-candidate blocks. Blocks gave
interquartile spreads of 25-137% of the median, which cannot support an
ordering; interleaving and shuffling brought them to 1,8-10,0%, and all three
rows are separated from the exact scan by non-overlapping interquartile ranges
in every one of four recorded runs (4x pool 2,99/3,01/2,98/3,00x).

**The anisotropy risk is refuted, and it ran the other way.** The fear was that
`vec_quantize_binary`, thresholding at zero, would find real embeddings sitting
off the origin with dimensions where every vector agrees. Measured: corpus mean
norm **0,406**, and **2 of 384 dimensions** more than 95% one-sided — and those
two are dimensions the model never activates, mean |x| of 5,5e-8 and 5,7e-33
against a median 3,9e-2, so their sign is float noise rather than corpus
geometry. Among dimensions carrying signal, one-sidedness tops out at **0,909**.
Centring on the corpus mean buys 0,5 to 3,4 points depending on the pool. Real embeddings are
*easier* to quantize than the clustered fixture at every pool below 16x — the
fixture was a harder problem than real data, not a conservative stand-in for it.

**So the original ruling was narrow rather than wrong.** At 16x, the pool the
fixture demanded, the two-stage path is still slower on real data. Real data
does not need 16x: it reaches 0,953 at 8x, where the path is ~1,7x faster. The
same mistake this work keeps paying for — a ratio at one operating point
read as a property of the system — with the sign reversed.

**Nothing shipped has changed and the default is not flipped here.** Turning the
path on trades about 5% of vector recall for ~1,7x latency, which is a product
decision the author owns. Both columns are maintained on every insert, so it
stays a one-line flip.

Two caveats, both making the recall column optimistic: 52% of a probe's exact
top-30 is its own item's sibling chunks (chunk overlap is 150 characters), so
the task is easier than a real query's; and recall is against the exact *vector*
ranking, where the shipped path fuses keyword and vector with RRF.

One observation for whoever revisits it: the first pass is not what costs. At 8x
it is 30,4 ms of the 61,5, and the rest is the rerank issuing one round trip per
pooled rowid. Batching that would put 8x near 35 ms — about 3x faster than exact
at 0,953 recall.

## What Zotero itself is doing

**Zotero 10 already runs FTS5**, in `fulltext.sqlite`. The platform facts — the
schema, what the contentless tables do and do not yield, and the bound that sets
on reusing them — are CONSTRAINTS.md C2's to state, and whether we depend on
them is ticket 0120's. This prototype builds its own index over text it fetches
from the local API.

**Zotero is building semantic search** — zotero/zotero#6012, draft, two core
developers. It exposes nothing over the local API, so zoteus cannot delegate.
They declined `sqlite-vec` and score with brute-force JS dot products, which
puts this prototype's `vec0` KNN ahead of theirs rather than behind, and they
fuse keyword and vector with RRF at `k = 60` — the constant this prototype
picked independently.

**The local API documentation settles 0006's design.** Local versions have "no
relation to Web API versions"; `?since=`, `Last-Modified-Version` and
`?format=versions` are supported and `/deleted` is not, which is why the
key-set reconcile is the documented route rather than a workaround. Reads need
no authentication, so the port must never be forwarded.

## What has landed

All of 0002–0006 in the fork, plus tonight's four fixes. Upstream's suite went
**477 → 757 tests**, `tsc --noEmit` and `eslint` clean at every wave.

| ticket | what |
|---|---|
| 0002 | `PassageStore` port, `Fts5PassageStore`, MATCH sanitiser, `SqliteSearchIndex` |
| 0003 | transaction boundaries, `ZOTEUS_SEARCH_BACKEND`, `persistence.ts` off the SQLite path |
| 0004 | vectors in `vec0` via `sqlite-vec` (optional dep), KNN in C |
| 0005 | streaming JSON → SQLite migration, no dependency, atomic rename |
| 0006 | library-version watermark, `?since=` deltas, deletion by key-set reconcile |
| 0007 | chunk geometry from configuration, stamped beside the watermark |
| 0009 | fold in JS on both sides; twelve codepoints the sweep caught |
| 0010 | typed corruption error; refuse and report |
| 0012 | a second watermark on the full-text sequence |
| 0013 | concentration as a documented query |

One deliberate divergence from upstream: the SQLite backend refuses
`toJSON`/`loadFromJSON` rather than materialising the library into the heap.

## Next action

**Live (2026-08-28): the plan of record is DESIGN.md §4, ratified in
DECISIONS.md and executed through tickets 0014–0037 — `erg ready` is the
queue. The immediate next step is the workstation session `RUNBOOK.md`
scripts: X2 opens the stopwords PR (0014), the trunk re-measurement unblocks
I-2, X6 feeds the #26 thread; everything they need is committed.** Everything
below records the prototype phase's close-out as it stood before that plan
existed.

**The prototype work programme is complete.** All twelve children are closed and
0001 closed 2026-08-22 after its integration review — the children read as one
change (`fts5-base..HEAD`, 42 files, +6 772/−147, 477 → 757 tests), the four
criteria re-checked against the merged result. What remained then:

1. **Whether to turn the two-stage vector path on** is now a decision with
   numbers behind it rather than a blocked measurement (0008 above). It is the
   author's call, and nothing waits on it.
2. **0007's last residual is settled** — the author opened two PDFs on
   2026-08-22 and the reader wrote a pack for each. What it opens is bounded
   (see above) and nothing is filed against it: an opportunity, not a defect.
3. **Nothing goes upstream** unless the maintainer answers #10. That was the
   posture then. *Superseded 2026-08-26: he answered (SYNC.md) — #10 closed by
   his own backend, PRs #19/#20 opened from here (merged 2026-08-27), and the
   ratified train governs what goes upstream.*

## Gates

Upstream's own: `npx vitest run`, `tsc --noEmit`, `eslint`. This project's
Python and prose rules do not apply to a TypeScript repo; `ruff check bench/`
covers the harness. The load-bearing check is not the suite but **same corpus
in, same results out** against the current index — a green suite passes on a
refactor that quietly changed ranking, which is why the comparison at the top of
this file is run rather than assumed.

## Status
<!-- generated 2026-08-29T18:06Z · as of 16c2c67 -->

**Tickets:** 23 ready · 19 blocked · 2 awaiting author — `erg ready tickets/` for full list
  next: 0016 Upstream concurrency floor: the cross-library w… · 0024 File the upstream issues (I-1..I-3; I-4 folded …
**In flight:** no open PRs
**Recent (first-parent):**
  16c2c67 Merge pull request #82 from MinhHaDuong/doc-one-statement-per-fact
  1cffd4d Merge pull request #74 from MinhHaDuong/worktree-explore-zoteus-library
  292aed1 Merge pull request #80 from MinhHaDuong/t0422-close-pooling-gaps
