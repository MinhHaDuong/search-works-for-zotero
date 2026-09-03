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
  `limit`, `truncat` or `cap`. The grep is empty, not sparse.
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
