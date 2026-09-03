# Four extraction routes, timed on one document — 2026-09-03

Ticket 0500 timed the build's own path and closed. It measured a *cache read*
plus a forced flat re-parse, over a sample of short attachments, and it did not
touch the structured-text route at all. This pass answers the different
question: **what does each way of getting text out of a PDF actually cost**, on
one document, so the routes can be compared without dividing an aggregate by a
count.

**The control is a single document, used by every route:** the IPCC AR6 WGIII
volume, **2 913 pages**, 88 466 648 B. It is the largest thing in the library and
the only one where per-page cost is not swamped by fixed overhead — 0500's arm B
put five pages through in 278 ms, of which almost none was parsing.

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

## What this says about where the build's time actually goes

The 2026-09-02 build measured **29 643,9 s** (8 h 14) for 363 613 passages.
0500's measured extract-plus-chunk rate is 0,174 ms/passage, so extract and chunk
together account for **63,3 s — 0,21 % of that build** (derived). The embedder is
the build. Any effort spent making extraction faster is spent on a fifth of one
percent, which is worth knowing before optimising it.

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
