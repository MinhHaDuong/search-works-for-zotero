# The author's library, censused — the sampling frame for the Menagerie's representative core (ticket 0711, measured 2026-09-06)

The Multilingual Menagerie's representative core is supposed to look like a real
library (`conception/0029-golden-fixture-structure-review.md` §3). Until now
nothing said which library or in what proportions. This report is that profile:
the marginal distributions of the author's own Zotero library, measured read-only
over the local API, so the fixture can be quota-sampled against them and the
comparison recorded.

Artifact: `bench/results/0029-library-census/census.json`.
Probe: `bench/library_census.py`, read-only; tests in `tests/test_library_census.py`.
Machine: **doudou**, Zotero **10.0.1** (local API v3, schema 44), personal library
at version 1257, 2026-09-06 10:05 UTC. Every number below comes from that one run
on that one machine unless it says otherwise.

    python3 bench/library_census.py \
        --output bench/results/0029-library-census/census.json \
        --include-group 305258 --sqlite ~/data/Zotero/zotero.sqlite

Wall time 3 min 16 s, of which the full-text counters are nearly all: one GET
per hundred attachments to the control plugin's `status` endpoint, which returns
`indexedPages / totalPages / indexedChars / totalChars` and Zotero's own indexed
state without the text. The same counters are reachable from the API's
`/items/<key>/fulltext`, which returns the text as well; the probe falls back to
that route when the plugin is absent and discards the text on arrival.

## Method, and what it can and cannot see

- **Perimeter.** The personal library (`/api/users/0/`) in full; the group
  library 305258 for the group-versus-personal marginal only; the trash and the
  feeds counted apart, since the 2026-08-31 perimeter ruling puts the fixture at
  what Zotero shows and excludes both.
- **Aggregate only.** The artifact carries counts and quantiles. No key, title,
  file name, creator or note text: titles were read to classify their script and
  notes to measure their length, and neither was kept. A raw `language` value
  longer than forty characters or carrying a path separator is binned as free
  text rather than quoted, because one of them was a URL.
- **Read-only.** Every request is a GET; the SQLite handle is
  `mode=ro&immutable=1`. Both are asserted by tests, one of them against a real
  HTTP server that records the methods it saw.
- **Blind spots of the local API**, each measured around rather than assumed:
  it exposes no annotation items (`itemType=annotation` answers 0 against 38
  rows in the database), no `/collections` endpoint (404; the per-item
  `collections` array is used instead), and no feed library (404). The SQLite
  supplement answers the first and the third from an immutable handle, which
  does not see rows still in an un-checkpointed WAL; a census tolerates that lag.
- **Quantiles** are nearest-rank. Percentages are derived and say so.

## Sizes

| | personal | group 305258 |
|---|---|---|
| items | **17 532** | **13 582** |
| top-level records | **7 541** | **5 758** |
| attachments | **9 309** | **7 277** |
| notes | **682** | **509** |
| full-text entries | **8 045** | **6 075** |
| items in the trash | **2** | **15** |

The personal library has 7 553 top-level items: 7 541 bibliographic records,
12 standalone attachments and no standalone note. The two libraries have the
same shape at this altitude — 1,23 attachments per record against 1,26
(derived) — and the group differs where the STATE handoff said it would: it
carries 236 `embedded_image` attachments (note illustrations) and 173
`linked_url` bookmarks, no `linked_file` at all. Feed libraries: **0**, so
the feed slice the ruling excludes is also one this library cannot supply.
Annotations: 38, every one of them in the group library (36 highlights,
2 images), none in the personal one.

## Item types

29 distinct types. Two of them are 59 % of the library, and the tail is long
but thin: 19 types have fewer than fifty records each.

| item type | records | share |
|---|---|---|
| journalArticle | **2 511** | 33,3 % |
| report | **1 915** | 25,4 % |
| webpage | **602** | 8,0 % |
| book | **509** | 6,7 % |
| conferencePaper | 289 | 3,8 % |
| bookSection | 278 | 3,7 % |
| presentation | 271 | 3,6 % |
| newspaperArticle | 260 | 3,4 % |
| magazineArticle | 222 | 2,9 % |
| blogPost | 190 | 2,5 % |
| document | 181 | 2,4 % |
| manuscript | 95 | 1,3 % |
| thesis | 57 | 0,8 % |
| 16 other types, each under 50 | 161 | 2,1 % |

The tail, for the record: statute 41, preprint 37, encyclopediaArticle 15,
letter 15, map 10, forumPost 8, bill 7, dataset 7, interview 6, artwork 4,
computerProgram 4, email 2, hearing 2, dictionaryEntry 1, patent 1,
videoRecording 1.

## Attachments per record

| attachments | records | share |
|---|---|---|
| 0 | **1 118** | 14,8 % |
| 1 | **4 639** | 61,5 % |
| 2 | **1 343** | 17,8 % |
| 3–9 | 416 | 5,5 % |
| 10 or more | 25 | 0,3 % |

Median 1, p90 2, p99 5, maximum **99**. Counting PDFs alone: 40,9 % of records
have none, 52,0 % have exactly one, 7,0 % have two or more (derived from the
`pdf_attachments_per_record` histogram). The many-attachment parent the
structure review lists as an adversarial case is present but rare: 25 records
carry ten or more attachments, one carries 99.

Whether a record has a PDF depends on its type more than on anything else:

| item type | records | with any attachment | with a PDF | with a note |
|---|---|---|---|---|
| journalArticle | 2 511 | 88,7 % | 72,6 % | 5,7 % |
| report | 1 915 | 90,3 % | 79,7 % | 8,5 % |
| webpage | 602 | 86,7 % | 5,1 % | 6,1 % |
| book | 509 | 86,2 % | 59,7 % | 7,5 % |
| conferencePaper | 289 | 57,4 % | 54,3 % | 6,9 % |
| bookSection | 278 | 44,6 % | 35,3 % | 8,3 % |
| presentation | 271 | 91,1 % | 79,3 % | 3,7 % |
| newspaperArticle | 260 | 92,7 % | 8,8 % | 19,2 % |
| magazineArticle | 222 | 91,9 % | 18,5 % | 24,3 % |
| blogPost | 190 | 91,1 % | 6,8 % | 16,3 % |
| document | 181 | 69,6 % | 43,6 % | 4,4 % |
| manuscript | 95 | 43,2 % | 23,2 % | 13,7 % |
| thesis | 57 | 86,0 % | 78,9 % | 5,3 % |

Web-native types (webpage, newspaperArticle, magazineArticle, blogPost) are
attached as HTML snapshots, not PDFs, and they are where the notes are. A
quota on item type therefore fixes the attachment format and the note rate
almost by itself; the joint cell to sample is (type × format), not the two
marginals separately.

## Attachment formats

| content type | attachments | share |
|---|---|---|
| application/pdf | **5 298** | 56,9 % |
| text/html | **3 076** | 33,0 % |
| office documents (Word, Excel, PowerPoint, OpenDocument, Pages, RTF) | 649 | 7,0 % |
| images (PNG, JPEG, GIF, WebP, XCF) | 120 | 1,3 % |
| empty content type | 117 | 1,3 % |
| other text (Markdown, XML, CSV, plain) | 24 | 0,3 % |
| archives (zip, rar, kmz) | 13 | 0,1 % |
| e-books (EPUB, Mobipocket) | 8 | 0,1 % |
| other (octet-stream, XUL, XHTML) | 4 | 0,0 % |

33 distinct content types. By link mode: `imported_file` **4 481** (48,1 %),
`imported_url` **4 377** (47,0 %), `linked_url` **446** (4,8 %), `linked_file`
**5** (0,1 %). PDFs split 3 645 imported files, 1 591 imported URLs, 59 bare
links and 3 linked files; HTML is 2 757 imported URLs (snapshots), 301 links
and 18 imported files. The linked-file limitation PR #327 made explicit for
the group library touches five attachments in the personal one.

## Notes

682 notes, all of them children; **0** standalone. 619 records (8,2 %) carry
at least one, 58 carry two or more, the maximum is four. Length in characters
of the stored HTML: p10 19, median **435**, p75 6 106, p90 13 132, p99 55 187,
maximum **494 030**. The distribution is bimodal in practice: a short remark or
a pasted document, little in between.

## Language

**3 650** records (48,4 %) carry a language; 3 891 do not. The field is free
text and the author has used 78 distinct spellings for it, from `en` (1 520)
and `EN` (483) through `en-US`, `Anglais`, `English`, `eng`, to `VN` (310) for
Vietnamese and `vn, en` for a bilingual document. Normalised to ISO 639-1 —
taking the first tag of a list, and reading the author's country codes `VN`,
`GB`, `CN`, `SP` as the language he meant:

| language | records | share of records with a language |
|---|---|---|
| en | **2 607** | 71,4 % |
| vi | **761** | 20,8 % |
| fr | **245** | 6,7 % |
| de | 17 | 0,5 % |
| ru | 5 | 0,1 % |
| ar 4, it 2, ja 2, id 1, nl 1, sv 1 | 11 | 0,3 % |
| unmapped free text | 4 | 0,1 % |

Three languages are 99,0 % of the labelled records (derived). Vietnamese is
the second language of this library, not French — one record in five that
says anything says Vietnamese — and the Latin-with-diacritics script class
below is largely that. The unlabelled half is not language-free: it is
where the field was never filled, and the fixture must not read "no language"
as "English".

Title script, over all 7 541 records: Latin ASCII 6 349 (84,2 %), Latin with
diacritics **1 142** (15,1 %), Cyrillic 4, Latin plus Cyrillic 1, Latin plus
Greek 1, no letters 43. **No CJK title at all.** A non-Latin script in this
library is four Russian titles; the fixture's non-Latin monster is adversarial
reserve, not representative core.

## Collections, abstracts, tags, dates

- **6 282** records (83,3 %) sit in at least one collection, 1 259 in none;
  1 863 sit in two, 211 in three or more. 90 collections in the personal
  library, 2 in the group (SQLite).
- **3 124** records (41,4 %) carry an abstract; median length 700 characters,
  p90 1 669, maximum 6 019.
- **1 319** records (17,5 %) carry a tag; the median record has none, p90 3,
  maximum 142.
- 7 402 records (98,2 %) carry a date. By decade of the parsed date: before
  1990 315 (4,2 %), 1990s 250, 2000s **1 620** (21,5 %), 2010s **3 240**
  (43,0 %), 2020s **2 013** (26,7 %), undated 97. The oldest is from the 1620s.
  Six records carry a parsed date that is a data-entry defect — five in
  year 0–9, one in the 2910s — which is the kind of malformed metadata the
  adversarial reserve should hold one of.

## Full-text coverage

The unit here is the file attachment: 8 863 of the 9 309 attachments have a
link mode that carries a file; the 446 `linked_url` bookmarks cannot be
indexed and are left out. 8 045 attachments have a full-text row in Zotero's
census, of which **584** are at version 0 — registered, extracted nothing.
The plugin's own state per attachment:

| content type | file attachments | indexed | partial | unindexed | unavailable |
|---|---|---|---|---|---|
| application/pdf | **5 239** | **4 195** | **584** | **460** | 0 |
| text/html | **2 775** | **2 640** | 0 | 113 | 22 |
| office documents | 649 | 0 | 0 | 649 | 0 |
| images | 120 | 0 | 0 | 120 | 0 |
| other text (Markdown, XML, CSV, plain, XHTML) | 25 | 14 | 0 | 11 | 0 |
| e-books | 8 | 5 | 0 | 3 | 0 |
| everything else | 47 | 0 | 0 | 47 | 0 |

So 77,3 % of file attachments are fully indexed and a further 6,6 % partially
(derived: 6 854 and 584 of 8 863). For PDFs: 80,1 % indexed, 11,1 % partial,
8,8 % unindexed. HTML snapshots index at 95,1 %. Every office document, image
and archive — 816 attachments, 9,2 % of the files — is unindexed, because
Zotero's extractor reads PDF, HTML and plain text and nothing else. A search
that promises "full text" is silent on one attachment in eleven by format
alone, before any extraction failure.

### Document lengths

| counter | n | min | p10 | p25 | p50 | p75 | p90 | p99 | max | mean |
|---|---|---|---|---|---|---|---|---|---|---|
| totalPages | 4 779 | 1 | 5 | 9 | **19** | 46 | **129** | **552** | **3 949** | 54,2 |
| indexedPages | 4 779 | 1 | 5 | 9 | 19 | 46 | 100 | 100 | 1 019 | 35,2 |
| totalChars | 2 659 | 1 | 2 480 | 4 162 | **8 141** | 15 200 | 37 322 | 137 130 | 1 124 660 | 17 205,1 |
| indexedChars | 2 659 | 1 | 2 480 | 4 162 | 8 141 | 15 200 | 37 322 | 137 130 | 1 124 660 | 17 205,1 |

Page counters exist for PDFs, character counters for the text formats; the
two populations do not overlap, so the two rows describe different documents.
The median PDF is 19 pages and the median HTML snapshot 8 141 characters. The
tail is where the fixture's scale layer lives: one PDF in ten is over 129
pages, one in a hundred over 552, and the largest is 3 949.

### The stock caps

- **620** of the 4 779 PDFs with page counters (13,0 %) exceed the stock
  100-page limit. **583** of them (94,0 % of those over the limit; 12,2 % of
  all PDFs with counters) are truncated exactly at it: `indexedPages == 100 <
  totalPages`. **37** are indexed beyond it — the X5 arm re-extracted in full
  on 2026-09-02 (AGENTS.md, environment notes). The single remaining partial
  is partial for another reason.
- **3** text attachments exceed 500 000 characters and **0** are truncated
  there: the character cap is raised on this install
  (`bench/summarize_0120.py` records it), so the stock-cap truncation rate for
  text is not measurable on this machine. It would be 3 of 2 659.

The two `indexedPages` quantiles that read 100 at p90 and p99 against 129 and
552 for `totalPages` are the cap seen from the other side: a tenth of the
PDF corpus is cut, and the ranking layer never sees what was cut.

## Trash and feeds — outside the perimeter, counted anyway

Personal trash: 2 items (one book, its one attachment). Group trash: 15.
Feed libraries: 0, feed items: 0. The exclusion the perimeter ruling makes
costs this library nothing today; the fixture still needs the trash case so
the exclusion is tested rather than assumed.

## What this implies for the representative core

**The large cells, in order.** A quota sample drawn to this profile is mostly
five things: a journal article with one imported PDF of about twenty pages in
English; a report with one imported PDF; a web page or press article with one
HTML snapshot and, for the press, a note one time in five; a book with a PDF; and
a record with no attachment at all (one in seven). Get those five right in
those proportions and the core matches the library on every marginal above
at once, because the marginals are not independent — type fixes format,
format fixes coverage, and the web-native types own the notes.

**Rare but present — sample at least one of each, oversampled or not.**

- ten-or-more attachments on one parent (25 records; maximum 99);
- a PDF over 552 pages (p99) and the 3 949-page extreme; a 1 124 660-character
  text;
- a note of half a million characters beside the 19-character median;
- office, image and archive attachments, which are 9,2 % of files and 0 %
  indexed — the fixture must show search saying so;
- `linked_file` (5 attachments) and bare `linked_url` (446) modes;
- Vietnamese as the second language, Latin script with diacritics — 15 % of
  titles, and the reason a diacritic-insensitive match is a requirement
  rather than a nicety;
- French at 6,7 % of labelled records, German and Russian below 1 %;
- a language field that is free text: 78 spellings, bilingual lists, one URL;
- a parsed date in year 0 or in the 2910s;
- a full-text row at version 0 (584): registered, empty;
- attachments the local API sees but cannot index: `unavailable` HTML (22).

**Absent from the library, mandatory in the fixture — adversarial reserve, not
core.** Standalone notes (0), annotations in the personal library (0; 38 in
the group, so the group slice carries them), CJK or Arabic titles (0), feed
items (0), a trashed item to prove the exclusion (2). The structure review
says the profile must not eliminate rare but important conditions; these are
the conditions the profile cannot even see, and they go in the reserve by
construction.

**Two marginals this census could not measure.** Passage lengths, which need
the extracted text and belong to `bench/results/0140-passage-census/`; and the
annotation types beyond what SQLite carries (`itemAnnotations.type`), since the
API exposes no annotation item — the fixture's annotation slice is specified
from the group's 36 highlights and 2 images, not from the personal library.
