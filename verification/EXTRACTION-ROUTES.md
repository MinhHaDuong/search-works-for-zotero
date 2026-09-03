# Extending 0500 to the structured-text route — 2026-09-03

**Most of this table is ticket 0500's, and 0500's numbers are the better ones.**
It pinned the two routes a build can take — the cache read and the forced flat
re-parse — at `bench/results/0500-extract-chunk/extract-chunk-throughput.json`,
declared in `bench/check_figures.py`, over five disjoint repetitions and 22 562
passages, with a warm-up discipline and a min-max spread. Nothing here improves
on that, and where the two disagree 0500 wins on method.

What 0500 did not measure is the **structured-text route**, which did not exist
in its frame: `.zotero-sdt-cache` is produced by a different worker, on a
different trigger, and no artifact in this repository timed it. That is what
this pass adds, and the rest of the table is here only so the new route has
something to be compared against on equal terms.

**The equal terms are the point.** 0500 measured its two arms on different
populations, which is right for pricing a build and wrong for ranking routes. So
every route below ran on one document: the IPCC AR6 WGIII volume, **2 913
pages**, 88 466 648 B. Choosing the longest document is 0500's own finding
applied, not a new one — it reported the per-passage cost falling with document
size, *"what a fixed per-file overhead over a variable yield looks like"*, and
its five-page sample spent almost none of its 278 ms parsing.

Machine: `doudou`, Intel i5-8250U @ 1,6 GHz, 8 cores, 23,4 GB, no GPU — the
reference machine SPEC.md §5.2.8 names.

## The measurement

| route | what it does | reps (s) | wall | pages/s |
|---|---|---|---|---|
| local API read | serves text the platform **already** extracted | 3,825 cold / 1,177 / 0,801 | ~0,8 s warm | ~3 600 |
| poppler `pdftotext` | parses the PDF to plain text | 12,94 / 12,96 / 13,60 / 13,60 | 13,3 s | 219 |
| Zotero flat (`pdf-worker`) | parses to `.zotero-ft-cache` | 64,90 / 62,59 | 63,7 s | 45,7 |
| Zotero SDT (`document-worker`) | parses to `.zotero-sdt-cache` | 554,1 | 554 s | 5,26 |

**Reading beats parsing by about 70x, and parsing routes span 42x between them.**
That is the whole finding, and it is why `build.ts` reads the platform cache
rather than parsing anything itself: the read is not a cheaper parse, it is a
different order of magnitude.

## Two things that keep this from being one number

**The SDT rate is stable across a 100x size range**, so 554 s is a rate and not
an outlier. Taken from each pack's `dateCreated` to its file mtime:

| pack | pages | span | pages/s |
|---|---|---|---|
| `GMAP993G` | 26 | 2,9 s | 8,85 |
| `BSMCQ6BM` | 24 | 3,4 s | 7,03 |
| `EBWH8FNB` | 28 | 4,3 s | 6,49 |
| IPCC volume | **2 913** | 554,1 s | **5,26** |

**A second document reproduces the flat-vs-SDT ratio.** `GMAP993G` was timed on
the flat route by 0500 arm B (0,591 s, 26 pp, 44,0 pages/s) and on the SDT route
here (8,85 pages/s): **5,0x**, against **8,8x** on the IPCC volume. Same
direction, magnitude growing with document size.

## What it costs at library scale

`fulltextItems` holds a page count for **8 576** attachments totalling
**464 599 pages**. Applying each measured rate — **derived, not measured end to
end**:

| route | whole library |
|---|---|
| local API read | 0,04 h |
| poppler `pdftotext` | 0,59 h |
| Zotero flat | 2,82 h |
| **Zotero SDT** | **24,6 h** |

So producing packs for the library costs about **a day of wall clock**, three
times the entire 8 h 14 index build of 2026-09-02. That is the number 0606 needs
beside its size ratio: the pack is not only ~2,2x the bytes, it is ~9x the time
of the flat extraction it would replace, and ~42x `pdftotext`.

## Where the build's time goes — 0500's number, re-divided

This paragraph adds no measurement. 0500 pinned extract plus chunk at
0,164 ms/passage and re-cut §5.2.8's allocation from it; against the
2026-09-02 build's **29 643,9 s** over 363 613 passages, those stages come to
**about 63 s, or 0,2 % of the build** (derived from 0500's rate, not measured
here). The embedder is the build. Restated only because the ratio is the form in
which it decides whether to optimise extraction at all, and 0500 expressed it as
a per-passage allocation rather than as a share.

The corollary points the other way and is the one that matters for 0120: because
the build only ever *reads* what the platform already extracted, the platform's
extraction policy — not our throughput — decides coverage. Where the platform
stopped at 100 pages, the build inherits 100 pages at full speed.

## Caveats, each of which bounds a number above

- **The SDT spans are `dateCreated` → mtime.** Whether `dateCreated` stamps the
  queue or the parse start is not pinned, so each is an upper bound. Four
  documents agreeing is what makes the rate credible; no single one would.
- **The flat figures include the plugin round trip and a 250 ms poll quantum**,
  so they too are upper bounds — the same method, and the same caveat, 0500 used.
- **`pdftotext` is poppler, not Zotero's engine.** It is here as a floor for what
  parsing this PDF costs at all, not as a drop-in substitute.
- **`complete()` in `bench/zotero_fulltext.py` is ledger-state based**, so for an
  already-complete item it fires at 0 s and only `busy` tracks the job. The outer
  wall is the figure; a reader taking the "1 of 1 complete" line for the
  finish time would record ~0 s for a 63 s parse.
- **Both full-text caps are raised on this machine** (`pdfMaxPages` 999999,
  `textMaxLength` 999999999), so the flat route here extracts all 2 913 pages
  where a default install would stop at 100 — and would look ~29x faster for it.
- **The library projections are rate x page count**, not an end-to-end run.
- **The flat figure sits below the 60-80 pages/s previously recorded** for
  platform reindexing. Not a contradiction to resolve here: 45,7 pages/s is one
  2 913-page document with both caps raised, where the earlier range came from
  other documents. Recorded so the gap is visible rather than averaged away.
- One machine, no GPU. The SDT route is ONNX segmentation and is the route most
  likely to move with hardware.

## Reproducing

    python3 bench/zotero_fulltext.py reindex 65F79PTJ --wait --poll 0.25   # flat
    pdftotext "<the volume>.pdf" /tmp/out.txt                              # poppler
    curl http://127.0.0.1:23119/api/groups/305258/items/65F79PTJ/fulltext  # read
    python3 verification/probes/sdt_read.py <pack>                         # SDT pack

The flat reindex is idempotent on an already-complete item: the `.zotero-ft-cache`
came back byte-identical (`md5 00263ce2dda66bd98a501f5b0c7322af`) across both
reps, which is also a free determinism check on the extractor.
