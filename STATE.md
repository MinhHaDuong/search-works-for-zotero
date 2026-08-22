# STATE — zoteus-fts5

Prototype work: replace zoteus's resident JS search index with SQLite/FTS5.

## What this repo is

Ticket store, measurement harness, and notes for a chantier whose code lives in
a **fork of someone else's project**. `fork/` is a plain checkout of
`MinhHaDuong/zoteus` (upstream `oscardvs/zoteus`) and is git-ignored here — it
has its own history, and a `tickets/` directory must never appear in it, or it
would show up in any diff sent upstream.

## The fork checkout

`fork/` sits on branch **`fts5-storage`**, off `fts5-base` = PR #11 ⊕ PR #12
merged, not upstream `main`. Both are prerequisites for measuring anything:
without #11's configurable cap the library never indexes past 5 000 items, and
without #12 the ASEAN group library is invisible. Current head **`bae82a7`**,
**757 tests**, `tsc --noEmit` and `eslint` clean, pushed to
`origin/fts5-storage`.

## Posture

The maintainer has not yet answered. Work proceeds as a **prototype in the
fork, with no merge request opened** for the storage layer — the posture stated
in the comment on oscardvs/zoteus#10. If he picks direction (d), this becomes
the PR; if he picks (a) or declines, it is a usable fork.

**Nothing has been reported upstream, and that is now a decision rather than a
pending action.** 0001's "report findings on #10" criterion was dropped by the
author 2026-08-22. The measurements below stand as the fork's own record.

## Upstream, as of 2026-08-22

| | state |
|---|---|
| [oscardvs/zoteus#10](https://github.com/oscardvs/zoteus/issues/10) | open — persistence ceiling, + comment proposing SQLite as direction (d) |
| [#11](https://github.com/oscardvs/zoteus/pull/11) | open, no review — item cap configurable + `truncationNotice` |
| [#12](https://github.com/oscardvs/zoteus/pull/12) | open, no review — group libraries served locally on Zotero 10 |

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

The uncapped rung is the structural wall this chantier exists for: the build
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
chantier should not have made in that form. The honest headline is **~1,85 GB
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
count this chantier ever reported. They are `ZOTEUS_CHUNK_SIZE`,
`ZOTEUS_CHUNK_OVERLAP`, `ZOTEUS_FULLTEXT_CHUNK_SIZE` and
`ZOTEUS_FULLTEXT_CHUNK_OVERLAP` now, with defaults byte-identical to what
shipped, pinned against their literal values. The geometry is stamped beside the
watermark and a mismatch rebuilds: otherwise one environment variable makes the
index a silent mixture of two populations.

**Structure-aware chunking stays out of reach.** Zotero 10 ships `Zotero.SDT`
(`sdt.js`, `structured-document-text.js`) writing a `.zotero-sdt-cache` pack
with page labels, outline paths and running-head exclusion — everything the
ticket assumed was unavailable. Probed three times over ten hours
(`bench/results/0007-sdt-probe.txt`): **zero packs library-wide**, including
after opening a PDF that Zotero reported as indexed. Full-text extraction is
ruled out as a trigger. The reader-tab path is *narrowed, not disproven*, and
cannot be tested from here — the local API exposes no way to open a reader tab,
so it needs one human to open one PDF and re-run the probe.

## Binary quantization, now measured on real vectors (0008)

Proposed on a measured 13x speedup taken at `k=30`, which did not survive being
asked for a *pool*: vec0's k-best structure costs more than linearly in `k`. On
a clustered fixture the pool that preserved the ranking (16x) was slower than
the exact scan it replaced, so the two-stage path shipped **off by default**.

**93 022 real passages, embedded by the shipped on-device model, settle the
criterion that stayed open** (`bench/results/0008-real-vectors/`, driver
`bench/vec_real_measure.mjs`):

| pool | fixture | **real** | centred | two-stage | vs exact (104,0 ms) |
|---|---|---|---|---|---|
| 4x (k=120) | 0,628 | **0,884** | 0,918 | 35,2 ms | **2,96x faster** |
| 8x (k=240) | 0,862 | **0,953** | 0,969 | 62,6 ms | **1,66x faster** |
| 16x (k=480) | 0,998 | 0,986 | 0,991 | 123,6 ms | 0,84x — slower |

On disk: **1 563,2 B per float32 vector against 71,1 B per binary code, 22x**.

Latencies are timed round robin rather than in per-candidate blocks. Blocks gave
interquartile spreads of 25-137% of the median, which cannot support an
ordering; interleaving brought them to 4-11%, and all three rows are separated
from the exact scan by non-overlapping interquartile ranges.

**The anisotropy risk is refuted, and it ran the other way.** The fear was that
`vec_quantize_binary`, thresholding at zero, would find real embeddings sitting
off the origin with dimensions where every vector agrees. Measured: corpus mean
norm **0,406**, and **2 of 384 dimensions** more than 95% one-sided. Centring on
the corpus mean buys 2-4 points of recall, not a rescue. Real embeddings are
*easier* to quantize than the clustered fixture at every pool below 16x — the
fixture was a harder problem than real data, not a conservative stand-in for it.

**So the original ruling was narrow rather than wrong.** At 16x, the pool the
fixture demanded, the two-stage path is still slower on real data. Real data
does not need 16x: it reaches 0,953 at 8x, where the path is 1,66x faster. The
same mistake this chantier keeps paying for — a ratio at one operating point
read as a property of the system — with the sign reversed.

**Nothing shipped has changed and the default is not flipped here.** Turning the
path on trades about 5% of vector recall for 1,66x latency, which is a product
decision the author owns. Both columns are maintained on every insert, so it
stays a one-line flip.

Two caveats, both making the recall column optimistic: 52% of a probe's exact
top-30 is its own item's sibling chunks (chunk overlap is 150 characters), so
the task is easier than a real query's; and recall is against the exact *vector*
ranking, where the shipped path fuses keyword and vector with RRF.

One observation for whoever revisits it: the first pass is not what costs. At 8x
it is 32,2 ms of the 62,6, and the rest is the rerank issuing one round trip per
pooled rowid. Batching that would put 8x near 35 ms — about 3x faster than exact
at 0,953 recall.

## What Zotero itself is doing

**Zotero 10 already runs FTS5** (`fulltext.sqlite`, `fulltextContent USING
fts5(text, tokenize='unicode61', content='')`) — but the tables are
*contentless*: matchable, not readable. That is why zoteus keeps its own copy of
the text, and it forecloses "just reuse Zotero's index".

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

**The chantier is complete.** 0001 and all twelve children are closed. What
remains is not work this repo owes anyone:

1. **Whether to turn the two-stage vector path on** is now a decision with
   numbers behind it rather than a blocked measurement (0008 above). It is the
   author's call, and nothing waits on it.
2. **One PDF opened in a Zotero reader tab** would close 0007's last residual —
   whether the reader path writes an SDT pack. It needs a human; the local API
   cannot open a reader tab.
3. **Nothing goes upstream** unless the maintainer answers #10. That is the
   posture, and dropping 0001's report criterion made it explicit.

## Gates

Upstream's own: `npx vitest run`, `tsc --noEmit`, `eslint`. This project's
Python and prose rules do not apply to a TypeScript repo; `ruff check bench/`
covers the harness. The load-bearing check is not the suite but **same corpus
in, same results out** against the current index — a green suite passes on a
refactor that quietly changed ranking, which is why the comparison at the top of
this file is run rather than assumed.
