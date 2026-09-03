# Full-text cache quality on the author's library — ticket 0480, measured 2026-09-03

The ticket carries an author's estimate: *roughly half* of his library's full-text
cache was produced by an older extractor and could be improved. That is a testable
population claim, and until now nobody had tested it.

Artifact: `bench/results/0480-fulltext-quality/census.json`.
Probe: `bench/fulltext_quality_census.py`, read-only over `storage/`.
Machine: **padme**, library `~/data/Zotero-fresh/storage`, 2026-09-03.

    pip install ftfy  # optional: without it, mojibake reads None (unmeasured), never "clean"
    python3 bench/fulltext_quality_census.py \
        --storage ~/data/Zotero-fresh/storage \
        --output bench/results/0480-fulltext-quality/census.json --no-detail

Drop `--no-detail` to regenerate the per-cache rows. They are 3,9 MiB and are not
committed; every count below is reproducible from the tree in one pass of a few
minutes.

## The headline: the population is not half, it is nearly all of it

| | caches |
|---|---|
| `.zotero-ft-cache` files under `storage/` | **13328** |
| of which the attachment is a PDF | **8580** |
| of which the attachment is not a PDF (HTML, JS, plain text) | **4748** |
| PDF caches carrying at least one form feed | **343** |
| PDF caches carrying **none** | **8237** |

A Zotero PDF extraction of the current generation writes a form feed at every page
break. A multi-page PDF cache with no form feed anywhere was therefore written by
the generation before it. On this library that is 8237 of 8580 PDF caches —
**96,0 %** (derived, 8237/8580), not the roughly half the ticket estimated. The
estimate understated the population by a factor of about two.

The direction matters more than the ratio. The ticket's exit criteria allow the
finding "the population is too small to justify the machinery"; the measurement
closes that exit. Whatever policy the author rules, it applies to substantially the
whole PDF corpus, not to a minority of it.

## The signal is not arbitrary — two independent text defects sort with it

A date-shaped signal that predicted nothing about text quality would be a curiosity.
The cross-tabulation is in the artifact under `summary.by_form_feed`, and it
separates:

| | with form feed | no form feed |
|---|---|---|
| caches | 343 | 8237 |
| median words | 9162 | 8166 |
| caches carrying raw ligature glyphs (ﬁ ﬂ ﬀ) | **0** | **1011** |
| caches flagged mojibake by `ftfy.badness.is_bad` | 14 | 753 |
| caches with no usable text layer | 0 | 342 |

Every one of the 1011 caches carrying an unnormalised ligature glyph is in the
no-form-feed group, and the other group has none at all. Mojibake runs at 4,1 %
against 9,1 % (derived). Two signals measured on the *text*, neither of which the
classifier used to decide the split, both land on the same side of it.

This is the control the split needed. It could have come out the other way — an
even spread of ligatures across both groups would have said the form feed dates
something irrelevant to quality — and it did not.

## The false-flag ceiling: 3,5 %, and it is an upper bound

The known false flag is a genuinely single-page PDF: it has no page break to mark,
so its missing form feed dates nothing. The census counts the no-form-feed caches
that carry real text yet are short enough for that to be plausible — under 700
words, roughly two pages of body: **286** of 8237, **3,5 %** (derived). Every one
of the 286 is a *suspect*, not a confirmed false flag, so 3,5 % is a ceiling and
the true rate is lower.

Near-empty caches are deliberately kept out of that count. **342** PDFs in the
no-form-feed group hold under 50 words and **257** hold none at all — those are a
different defect, a missing text layer needing OCR rather than a better extractor,
and folding them in would inflate the ceiling with a population re-extraction
cannot help. They are all in the no-form-feed group; the other group has none.

A false "poor" flag costs one needless re-extraction. The floor for a false "fine"
flag is already known, because it is the state the library is in today.

**So the number a policy would act on is 7895, not 8237**: old-generation caches
holding real text, which a better extractor could improve. The 8237 above is the
dating result; this is the population. Both are in the artifact, under
`pdf_no_form_feed` and `pdf_reextraction_population`.

## Two findings that fall out, both of which change who drains this

**Zotero's own truncation ledger is empty on this machine.** `fulltextItems` in
`~/Zotero/zotero.sqlite` holds **0 rows**, while 13328 caches sit on disk. So
`reindexTruncated` — the mechanism `verification/SDT-CAPS-0483.md` §3 identified as
upstream's drain for the *truncated* half — would select nothing here at all. Not
because nothing is truncated, but because the local index state did not survive
whatever produced this library. Neither half has an upstream drain on this machine.

**mtime dates the sync, not the extraction.** Ticket 0120's candidate heuristic
paired the form feed with cache mtime against attachment mtime. On this library
every cache mtime falls in 2026, in both groups, without exception: the tree was
resynced, and the filesystem clock now records that event. The mtime arm of the
0120 candidate is dead here and should not be carried into the detection design.
The form feed survives because it is *in the bytes*.

## Caveats, each bounding a figure above

- **One library, one machine.** `verification/KEYWORD-BUILD-COST-0120.md` reported
  3 882 pre-form-feed PDF caches on **doudou**. That is a different machine and a
  different library state; the two numbers are not a trend and must not be read as
  one.
- **The form-feed signal has no positive control on real data**, only on the
  fixture (`tests/test_fulltext_quality_census.py`). Nothing here re-extracted a
  known document with the current extractor and observed a form feed appear. The
  cross-tabulation above is strong circumstantial evidence and is not that
  experiment. The experiment is one item through a plugin-commanded reindex, and it
  is the next thing worth an hour.
- **Mojibake is read from the first 200 000 characters** of each cache, not the
  whole body. The signal is dense from the first page when present; a body that
  turns bad only past that prefix is not counted.
- **`ftfy.badness.is_bad` is a heuristic** and was chosen over a hand-rolled
  character-class test because the latter's failure mode is a silent false negative
  on exactly the accented French this library is full of. It is used as a
  *corroborating* signal here, never as the classifier.
- **181 caches contain undecodable bytes**, replaced on read. They are counted and
  not excluded; their word counts are approximate.
- **"Is it a PDF?" is answered from the file, not assumed from its name.**
  An earlier pass answered from the suffix alone: it reported 20 caches with
  no attachment, every one of which was in fact a real PDF whose filename had
  lost its extension (Zotero occasionally truncates a long download name to
  nothing but the key), confirmed by opening each and checking for the `%PDF`
  magic bytes. Suffix-only classification silently moved all 20 into
  `non_pdf_caches`, undercounting the PDF population by that many. Fixed: an
  extensionless file is now sniffed for the magic bytes rather than assumed
  absent, and **0** caches have no attachment file at all on this library
  (`caches_with_no_attachment`, genuinely zero — no source is actually lost
  here) — and **25** PDF directories hold a non-PDF file beside the PDF (the
  cache text may have come from either), inside `pdf_caches` (8580) at 0,3 %,
  outside the 3,5 % ceiling above, which covers only the single-page case.
- **The walk reports what it could not read.** `unreadable_caches` is 0 here,
  and it is 0 for a reason the code can attest to: the census enumerates
  `storage/` itself rather than using `Path.glob`, which swallows a
  permission error inside its own recursion and would have made that zero mean
  either "all readable" or "cannot see failures". The distinction has a
  positive control in the suite.
- **The non-PDF 4776 are outside the question.** The form feed dates the PDF
  extractor and nothing else, so the census reports the signal as absent for them
  rather than false.

## What this hands the ruling

Detection is cheap, structural, and reads no Zotero API: one byte scan of a cache
already on disk, with a bounded false-flag ceiling of 3,5 %. The population a
policy would act on is 7895 attachments. What is *not* settled by measurement is
whether zoteus should serve its own extraction in place of the platform's for
those items — that is a
contract question, and it is filed in `DECISIONS.md` § Awaiting ratification.
