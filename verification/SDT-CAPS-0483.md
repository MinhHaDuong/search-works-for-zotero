# Does the SDT path honour `fulltext.pdfMaxPages`? — no

**Scope, and it is not what was asked for.** Read on **2026-09-03** from
`zotero/zotero` **`main`** over `raw.githubusercontent.com`, three files:
`chrome/content/zotero/xpcom/sdt.js` (15 089 B),
`chrome/content/zotero/xpcom/fulltext.js` (116 964 B),
`chrome/content/zotero/xpcom/pdfWorker/manager.js` (24 108 B). **Not** the
installed build `20260817151751`, which lives on `doudou` and is unreachable
from the session container — every earlier platform reading in this chain was
taken from the installed build, so this one is a different substrate and any
disagreement is dated, not contradictory. The check that closes the gap is one
line on `doudou`: grep the extracted `omni.ja` for `reindexTruncated`.

## The answer

**The structured-text path is not capped by the full-text preferences.**

- `sdt.js` contains **zero** occurrences of `Prefs`, `maxPages`, `maxLength`,
  `limit` or `truncat`, case-insensitively — five empty greps, not sparse ones.
  The pattern actually run also carried `cap\b`, which is empty too; **bare
  `cap` is not**, and an earlier draft of this line overstated it: `grep -ic cap`
  returns 1, the word *captured* in the comment at `sdt.js:287`. Irrelevant to
  the conclusion, and recorded because the line as first written was false.
- Generation runs through `_generateUnqueued`, which calls
  `Zotero.PDFWorker.getStructuredDocumentText(item.id, { isPriority, onProgress })`.
- In `pdfWorker/manager.js` the two entry points differ exactly here:
  - `getFullText(itemID, maxPages, isPriority, password)` (line 612) forwards
    `maxPages` into the worker query (line 629) — the capped path, and
    `fulltext.js:651` supplies it as `allPages ? null : maxPages`;
  - `getStructuredDocumentText(itemID, { isPriority, password, onProgress })`
    (line 652) sends `{ buf, contentType, password, sourceHash, reportProgress }`
    (line 677) — **no page or length argument at all**; the whole file buffer
    goes over.
- `manager.js` reads no preference anywhere.

**What this does not establish:** the WASM side. A limit internal to
`resource/document-worker/` would not appear in any of these three files. The
empirical control is available and cheap: open the IPCC volume `65F79PTJ`
(2 913 pages, already re-extracted flat and complete) in Zotero's reader, then
read the resulting pack's page catalog with `verification/probes/sdt_read.py`.
2 913 settles it one way, 100 the other. The two packs on the machine today
(26 and 24 pages) are far too short to test it.

## The second finding, larger than the question

`fulltext.js:345-362` registers preference observers on
`fulltext.textMaxLength` and `fulltext.pdfMaxPages`. Each schedules, debounced
5 s on the settled value, a call to `this.reindexTruncated(type, limit)`
(line 3093), whose whole body is:

    SELECT itemID FROM fulltextItems
    WHERE indexedPages IS NOT NULL AND indexedPages < totalPages AND indexedPages < ?

(and the `indexedChars`/`totalChars` twin for `chars`), followed by
`this.indexItems(itemIDs, { ignoreErrors: true })`. Its own comment states the
intent: *re-extract just the items it affects rather than forcing a full rebuild
(which would re-upload everything)*.

So upstream already holds **both halves of ticket 0483**: the truncation ledger
is `fulltextItems.indexedPages/totalPages` and `indexedChars/totalChars`, and
the drain is `reindexTruncated`, triggered by the preference itself. Raising the
cap once re-extracts exactly the affected attachments, unattended, with no full
rebuild. They pay the same treadmill this project has been reasoning about, and
bound it the same way — by the ledger, not by a verb.

**The two halves separate cleanly, and only one of them is ours.**

| half | population | who drains it |
|---|---|---|
| truncated bodies | `indexedPages < totalPages` | upstream `reindexTruncated`, on a preference change — **if the installed build carries it** |
| old-generation caches | 3 882 pre-form-feed PDF caches | **nobody**: a cache fully extracted under the old extractor has `indexedPages == totalPages`, so the query never selects it |

An old-generation cache is not truncated, so no upstream mechanism will ever
reach it. That half stays ours whatever the dating says, and it is the half our
own extraction — or a plugin-commanded reindex — exists for.

---

# Both open questions, closed on `doudou` — 2026-09-03

The document above ends on two named checks, each said to be one line on this
machine. Both were run. They agree with its prediction on the first and settle
the second the way it hoped, and a third finding falls out that changes the
"who drains it" table.

**The build has moved.** Installed is Zotero **10.0.1**, BuildID
**`20260824184709`** (`/opt/zotero7/app/application.ini`), not the
`20260817151751` named above. The greps below read the build that is installed,
which is a week newer than the one the dating caveat was written about.

## 1. `reindexTruncated` is in the installed build — and has no startup sweep

`omni.ja` extracted from `/opt/zotero7/app/omni.ja` (7 492 files). The symbol
occurs **twice**, both in `chrome/content/zotero/xpcom/fulltext.js`: the
preference observer at line 353, and the definition at line 3093. The body
matches the upstream reading above exactly.

**Two occurrences is the finding, not an incidental count.** There is no third
call site, so `reindexTruncated` is reachable *only* from a live preference-change
event, debounced 5 s. Nothing sweeps at startup. A limit raised while Zotero is
closed — editing `prefs.js` — or raised under a build predating the feature,
fires no observer and leaves the affected items truncated with no catch-up path.

Stock defaults, read from the shipped code rather than asserted:
`"pdfMaxPages", 100` and `"textMaxLength", 500000`.

## 2. The WASM worker does **not** cap pages — 2 913, not 100

The empirical control ran. One correction to its recipe: the pack landed on
**`LGMFDEDM`**, the user-library copy, not `65F79PTJ`. The library holds the
IPCC volume twice, once per library, and the two files are **byte-identical**
(`md5 a1f1b47358a3a6d3cac5088b252d0a5f`), so the substitution is sound.

Read with `verification/probes/sdt_read.py`:

| | |
|---|---|
| pack version / schema | 1 / 1.1.0, processor `pdf v3` |
| blocks | 25 002 |
| catalog pages | **2 913** |
| distinct pages carrying blocks | **2 913** |
| catalog pages with no block | **0** |
| page index range | 0 .. 2912 |

Block counts across the flat path's cliff show no discontinuity — pages 98–102
carry 9, 10, 27, 7, 14 blocks — and the last pages are populated (2908–2912:
28, 37, 21, 26, 10). Every one of the 2 913 catalog entries has a
`contentRange`. **2 913 settles it: the structured-text path is uncapped end to
end, WASM side included.**

Cost: pack metadata `dateCreated` 11:17:41 local, file written 11:26:55 —
**about 9 minutes** for 2 913 pages, roughly 5 pages/s. (Whether `dateCreated`
stamps the queue or the start is not pinned; the span is an upper bound.)

## 3. Upstream holds the mechanism, and it did not drain this machine

The table above credits `reindexTruncated` with draining the truncated half.
On this machine it has not, and finding 1 says why.

`extensions.zotero.fulltext.pdfMaxPages` currently reads **999999** and
`textMaxLength` **999999999**. Yet `fulltextItems` still holds **1 053** rows
with `indexedPages < totalPages`, every one of them stopped at exactly **100**
— the stock default. Truncated by chars: **0**. The worst lose 100 of 3 949
pages. The population spans both libraries, in duplicate pairs (3 949, 1 259,
1 236 and 1 058 pages each appear once in library 1 and once in library 3).

The same document, indexed under the two regimes, is the whole story:

| copy | library | `indexedPages` | `.zotero-ft-cache` |
|---|---|---|---|
| `65F79PTJ` | group (3) | **2913** / 2913 | 10 705 102 B |
| `LGMFDEDM` | user (1) | **100** / 2913 | 303 749 B |

So the cap that binds the flat cache is `pdfMaxPages`, and
`indexedPages < totalPages` reports it faithfully — 0483's ledger half is
answered, and answered by a column that already exists. The revision the table
needs is to its second column, not its first: the upstream drain is real but
**event-triggered only**, so a population can sit truncated indefinitely under a
raised limit. That is a third half, and it is nobody's today.

**Caveat that bounds every number here:** both caps are raised on this machine.
Nothing measured on `doudou` describes what a default install produces.

## 4. What this hands 0120 and 0606

**0120** gets its action-2 bound measured rather than reasoned: for **1 053**
attachments the platform FTS5 index holds only the first 100 pages, so it cannot
serve those bodies at all. The asymmetry runs the useful way for action 6 —
exactly where the flat index fails (long books), the SDT pack is complete.

**0606 action 1** gets its book-scale point. Pack-to-flat, same document each
time, the flat side for the IPCC volume taken from the *untruncated* group copy:

| document | pages | pack | flat | ratio |
|---|---|---|---|---|
| `GMAP993G` | 26 | 140 215 | 72 916 | 1,92 |
| `BSMCQ6BM` | 24 | 345 539 | 123 682 | 2,79 |
| `EBWH8FNB` | 28 | 26 705 | 9 734 | 2,74 |
| IPCC volume | **2 913** | 24 011 164 | 10 705 102 | **2,24** |

The ratio **holds at book scale** — 2,24 sits inside the band the three short
documents set, so it does not blow up with length. Against 0606's own
thresholds it is neither "near 1" (the shape stands) nor "near 3" (the ticket
re-opens); the per-glyph `textMap` the ticket named as the term that could
dominate does roughly double the artifact, and no more.

Corpus consequence, and the derived figure is labelled as derived: the library's
13 631 `.zotero-ft-cache` files total **874 609 144 B (0,875 GB)** — that part is
measured. At the book-scale ratio that projects to **≈1,96 GB** of packs beside
a 1,71 GB index. The projection understates, because 1 053 of those flat caches
are themselves truncated at 100 pages.
