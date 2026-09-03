# What our own keyword build costs — ticket 0120 action 1, 2026-09-03

Action 1 asks one question and refuses to accept an estimate for it: *measure our own
keyword build — wall time, peak RSS, disk — against zero for the platform path, on the
same library.* "A saving nobody measured is not a saving." Until today the figure did
not exist; the ticket's other actions had been reasoned at length around a number
nobody had run.

It has now been run. **Our whole keyword index over the real library costs 305,9 s,
730,6 MiB of peak RSS and 709,9 MiB on disk.** Everything below either qualifies that
sentence or says what it does not settle.

Artifact: `bench/results/0120-keyword-build/keyword-build-cost.json`, assembled by
`bench/summarize_0120.py` from three run logs it names. Machine: `doudou`, the
reference machine of SPEC.md §5.2.8.

## The measurement

Same server, same library, same flags as the 2026-09-02 full build — `--backend
sqlite`, `--max-items` uncapped, `--max-chars 200000`, `ZOTEUS_INDEX_AUTO_REFRESH`
false. The single difference is `ZOTEUS_EMBEDDINGS`, `off` here against `local` there,
and the status object says so out loud: `embedder: "none (keyword-only)"`, `vectors: 0`.

| | keyword only | the 2026-09-02 build | share |
|---|---|---|---|
| wall | **305,9 s** | 29 643,9 s (8 h 14) | **1,03 %** |
| peak RSS | **730,6 MiB** | 2 409,6 MiB | 30,3 % |
| index on disk | **709,9 MiB** | 1 627,0 MiB | 43,6 % |
| passages | 363 613 | 363 613 | — |

The passage counts are identical, which is what makes the two rows comparable rather
than merely adjacent: 7 541 items, 5 562 of them with body text, 348 516 full-text
passages, 12 402 metadata passages, 2 695 own-words passages, both times.

**So the embedder is the build, and the keyword half is a rounding error on its clock.**
That confirms from the end-to-end direction what 0500 established per passage and
`EXTRACTION-ROUTES.md` restated as a share — but it is a different measurement, not the
same one re-divided: those figures priced extract and chunk alone at about 63 s, and
this one is a build, including the metadata pass, the 8 037-attachment walk, the crawl,
the chunking and every SQLite write.

## Zero, and what the zero excludes

The platform side of the comparison is **0 s of wall, 0 kB of peak RSS and 0 bytes of
incremental disk**. This is not a rhetorical zero. Zotero builds and maintains
`fulltext.sqlite` whether or not we ever open it; the file is 294,8 MiB on this machine
today and was paid for before we arrived. Adopting it adds no extraction pass, no
memory, and no bytes of ours.

What the zero does not include, and none of it is priced here:

- the **query-time** cost of using it, which action 1 does not measure;
- **metadata and own words** — 15 097 passages, 4,2 % of ours — which `fulltext.sqlite`
  does not hold at any price and could not be made to;
- reproducing Zotero's tokenization to turn a token offset into an entry span
  (action 4), which an approximation missed by +13, +2 and 0 tokens on three documents;
- **availability under a writer's exclusive lock** (action 3).

That last one stopped being hypothetical during this session. A read-only
`sqlite3` open of `fulltext.sqlite` with Zotero up returned `database is locked` twice,
about a minute apart, on `select count(*) from fulltextContent`. It is recorded here as
an observation and nothing more: the cause was not isolated, no positive control was
run, and one unconditioned failure does not measure availability. Action 3 owns that
question, and SPEC.md §4 C2's sentence — "whether it is readable while Zotero runs is
not established here" — still stands as written.

## What a saving could reach at most, on disk

Splitting the built index by `dbstat` bounds the whole argument:

| | bytes | share |
|---|---|---|
| `passages` and its addressing (stored text) | 534,0 MiB | 75,2 % |
| FTS5 shadow tables (the keyword index proper) | **175,9 MiB** | **24,8 %** |

The platform index could stand in for the second row and nothing else. Our passage text
has to stay on disk whatever indexes it, because `fulltext.sqlite` is contentless: it
cannot print a passage back, and the entry is our ratified unit of answer. So the
disk saving available from the whole platform path is at most **175,9 MiB against a
294,8 MiB file we would then depend on** — we would be trading a smaller artifact we
control for a larger one we do not.

The time saving is bounded the same way and lands lower still. Adopting the platform
index removes neither the crawl nor the chunking nor the passage writes; it removes the
FTS5 insert alone, some fraction of 305,9 s that is itself 1,03 % of a build.

## The fixed term, and why two scale points

A single full-library run gives a total and no way to read it. Two runs give the split
by difference:

| items | passages | wall | peak RSS | index |
|---|---|---|---|---|
| 300 | 19 966 | 140,4 s | 406,9 MiB | 41,0 MiB |
| 1 200 | 64 459 | 156,6 s | 454,2 MiB | 126,6 MiB |
| all 7 541 | 363 613 | 305,9 s | 730,6 MiB | 709,9 MiB |

Marginal cost **0,364 ms per passage**; fixed cost **133,1 s per build**. The fixed term
is most of a 300-item build and it is not overhead in the dismissible sense — it is the
attachment-page walk, which covers all 8 037 extracted attachments no matter how few
items the run indexes.

That fit predicts 265,5 s for the full library against the measured full run, an error
of **-13,2 %**, reported rather than tuned away. Two points
cannot see a marginal rate that rises with scale, and this one evidently does. The
number to carry forward is the measured 305,9 s; the fit is here for what it says about
a *smaller* library, where the fixed term dominates and the marginal term is nearly free.

## Peak RSS sits at the C3 figure

The full build's peak is not comfortably inside SPEC.md §4 C3's ~750 MB; it is level
with it. Two things bound what that observation licenses. It is a *build* peak of the server
process, where C3's rows name a server steady state and a pipeline-worker peak — which
row owns a keyword build is not settled here and is not this action's to settle. And it
is 30,3 % of the embedding build's 2 409,6 MiB, so on this axis too the embedder is the
consumer. What can be said flatly: the keyword half alone very nearly fills the budget,
so a plan that assumes it is cheap in memory because it is cheap in time is wrong.

## What the 305,9 s actually indexed, which is not the library

The build reads Zotero's extracted text and never parses, so it inherits whatever
state that text is in — and on this machine the text is in a poor one. Two defects,
measured by ticket 0483 on 2026-09-03 and recorded with their evidence in
`verification/SDT-CAPS-0483.md` §3, both of which this build read straight into the
index:

- **1 053 attachments are truncated**, every one stopped at exactly 100 pages, the
  stock `pdfMaxPages` default. Both caps are raised on this install, which did not
  help them: `reindexTruncated` fires on a live preference change and nothing has
  fired it since, so a population can sit truncated indefinitely under a raised limit.
  The worst loses 100 of 3 949 pages. One document held in both libraries shows the
  size of it — the group copy's cache is 10 705 102 B against 303 749 B for the user
  copy of the same volume.
- **3 882 PDF caches are pre-form-feed**, written by the extractor generation before
  2024. A cache extracted in full under the old extractor has `indexedPages ==
  totalPages`, so `reindexTruncated`'s query never selects it and no upstream
  mechanism will ever reach it.

So the honest reading of the headline is: **305,9 s is what it costs to index the
library as Zotero has extracted it, which is a floor rather than the price of
indexing the library.** A build over complete, current bodies would carry more
passages, more bytes and more seconds, in proportion to the pages missing today.
Nothing here measures that build, and the projection is not attempted because the
missing text's chunk yield is not known.

This sharpens the ticket's question rather than softening it. The platform FTS5 index
is built from **the same** extracted text, so adopting it inherits both defects
exactly, and inherits them with less recourse: we can point our chunker at a better
source — the SDT pack (action 6), or our own extraction — while keeping everything
downstream, where a contentless index we do not own leaves us the text quality we are
given and no signal when it changes. The build cost was never the argument; the text
is.

## Caveats, each bounding a figure above

- **Every wall figure is an upper bound within a 5 s poll quantum.** `run_build.py`
  sleeps `--poll` between status calls and breaks on the first poll that sees `done`, so
  its elapsed is the true build time rounded up. This is not pedantry: at `--poll 20`
  the 300- and 1 200-item runs **both reported 140,3 s** — the quantum, not the build —
  and an earlier full-library run at `--poll 30` read 332,9 s against the 305,9 s here.
  That 332,9 s is a superseded number and should not be quoted.
- **Both Zotero full-text caps are raised on this install** (`pdfMaxPages` 999999,
  `textMaxLength` 999999999), so for everything extracted since they were raised the
  body text read here is longer than a default install holds, and the passage counts
  with it. Nothing here describes a stock machine — in either direction, since the
  raised caps did not reach the 1 053 attachments already truncated under the old ones.
- **`--max-chars 200000`** matches the 2026-09-02 build; the shipped default is 40 000
  and would index far less body text per item.
- **The comparison build's crawl was degraded and this one's was not.**
  `localApiDegradedAt` is set in the 2026-09-02 status and null in all three runs here,
  so the 8 h 14 includes a full-text fetch that ran one at a time. That inflates the
  denominator of the 1,03 %; it cannot inflate it much, since the fetch overlaps the
  embed queue there and extract plus chunk is 0,2 % of that build either way.
- **Other lanes were active** — loadavg is recorded in the artifact rather than
  controlled — so the wall figures are upper bounds on an idle machine.
- **The WAL is reported beside the main file, not folded into it.** The full run left
  141,1 MiB of WAL; a checkpoint moves those bytes without changing what the build
  needed.
- One machine, no GPU.

## What this does and does not decide

It closes action 1 and the first box of the ticket's verification list: the saving is
measured on the real library, not estimated. It does not close the ticket. Actions 2
through 6 remain, and this measurement pushes on the recommendation in action 7 in a
specific direction rather than settling it: **the platform index's attraction was never
going to be build cost**, because the build cost it displaces is 1 % of a build and a
quarter of an index file. If it is worth adopting, the case has to be made on what it
answers, on staleness, or on coverage — and each of those is another action's question.

## Reproducing

    python3 bench/run_build.py --server fork/dist/index.js --data-dir <dir> \
      --backend sqlite --embeddings off --build \
      --max-items 1000000 --max-chars 200000 --poll 5 --max-wait 1800

    python3 bench/summarize_0120.py --full <log> --small <log> --mid <log> \
      --embedding-build <the 2026-09-02 build.log> \
      --server fork/dist/index.js --index-db <dir>/search-index.sqlite \
      --poll-quantum-s 5 --out bench/results/0120-keyword-build/keyword-build-cost.json

Zotero must be up and idle: the crawl reads body text over the local API, and concurrent
traffic on port 23119 trips `localApiDegradedAt`, after which the fetch runs one at a
time for the rest of the build and never climbs back.
