# Full-text indexing truncates each item at 40,000 characters, and nothing reports it

The README says that with `ZOTEUS_INDEX_FULLTEXT` on, "semantic search covers
the body of every PDF too, so a claim that never made it into an abstract is
still findable."

For most of a library that is true. For a long document it is not, and the gap
is invisible from the outside.

## Mechanism

`createFulltextSource` concatenates an item's attachment text and cuts it at
`maxChars` (`src/features/search/fulltext-source.ts`):

```ts
const slice = maxChars > 0 ? content.slice(0, maxChars - used) : content;
```

`maxChars` defaults to `DEFAULT_FULLTEXT_MAX_CHARS = 40_000`, whose own comment
scopes it honestly: "~13 pages of dense text, so a typical paper is covered end
to end." A book is not a typical paper. One reference work in my library has
roughly 43 MiB of extracted text — about 1,100 times the cap. Everything after
its opening pages is not in the index, and no query can reach it.

The budget is also spent across an item's attachments in sequence: the loop
breaks once `used >= maxChars`, so on an item with two attachments carrying
text, the first can consume the whole allowance and the second is indexed not
at all.

`zotero_get_fulltext` is unaffected; it serves ranges on demand. This is about
the search index only.

## The cap is defensible. Its silence is not.

I measured what happens without it. Stock v1.10.0, sqlite backend, a fresh data
directory, my real personal library (7,541 top-level items, one of which is the
long reference work above), `--max-chars 0`:

| | uncapped build |
|---|---|
| peak RSS (VmHWM) | 2,046.1 MiB |
| elapsed | 182.2 s |
| passages | 477,511 (465,109 full-text) |
| index on disk | 938.8 MiB + 147.4 MiB WAL |

At rest afterwards the same server holds 122.7–137.1 MiB and answers warm
queries at 7.7 ms p50, with a p95 of 210.5 ms on the same run — so the cost is
transient build-time memory, not serving memory. A 2 GB peak during a build is a real reason for a default cap. I am not
asking for a bigger number.

What is missing is that the truncation leaves no trace. The build status
reports item truncation deliberately and well:

```ts
/** Items the library actually holds, before the build limit is applied ...
 *  Kept apart from `itemsTotal` so a truncated build stays legible: with only
 *  the capped figure, a build that stopped at the limit reports `5000/5000`
 *  and is indistinguishable from one that indexed the whole library. */
itemsAvailable: number;
```

The body cap has no counterpart — no counter, no notice, no per-item flag. A
user whose book was cut at page 13 gets an empty result set that looks exactly
like "your library does not discuss this," and `truncationNotice` stays silent
because the item *was* indexed.

## Why `ZOTEUS_INDEX_FULLTEXT_MAX_CHARS=0` is not the answer

The setting exists and it works; step 4 below uses it. It does not close this,
for three reasons.

**It requires the knowledge it is meant to supply.** Setting it presupposes
knowing that a cap silently truncated something. That is precisely what no
surface tells you. The user who would benefit is the user who cannot know to
look; the user who can set it has already, somehow, found out. A workaround
reachable only after you have diagnosed the problem does not fix a
discoverability defect — it is the same defect wearing a different hat.

**Zero is not safe to recommend generally.** It is what the 2,046.1 MiB row
above measures. Telling a user with a book-length PDF to disable the cap trades
a silent wrong answer for a possible OOM during the build, on a default install
that is often a desktop extension. Neither value of this one number is right for
everyone, which is the argument for reporting rather than retuning.

**It is per-install; the promise is per-user.** The README sentence is about
what zoteus does out of the box. An environment variable that a fraction of
users will ever read cannot make a shipped default's behavior honest.

Report the truncation and all three go away, including for the people who never
change a setting.

## Shapes that would close it

Yours to pick; the first is much smaller than the second.

1. **Report it.** Count items whose body text hit the cap, surface the pair the
   way `itemsAvailable` / `itemsTotal` already does, and extend
   `truncationNotice`. This makes the current behavior honest without changing
   it, and it is what makes the setting above usable by the people it is for.
2. **Stream past it.** Chunk and embed an attachment's text incrementally
   rather than materializing and slicing it, so a long document costs bounded
   memory instead of a bigger cap. That is what would let the README sentence
   be true unqualified.

## One thing that interacts with (2)

I have a design for entry-aligned chunking — cutting a long document at its own
section and entry boundaries rather than at a fixed character stride, and
prepending each chunk's heading and outline path to the text that gets embedded.
It is designed and not yet built, and nothing about it is measured. I am not
offering it here and not asking you to wait for it.

The reason to mention it now is that it and (2) touch the same seam. If a
streaming reader emits chunks at a fixed stride over a byte window, a chunk in a
reference work can straddle two entries, and the heading that would make the
passage citeable is exactly what the stride discards. If instead the reader
emits at boundaries it is handed, both designs fit behind the same interface and
neither has to be decided now. That is the whole of it — a seam, not a feature.

I will come back with measurements or not at all.

## A ceiling above this one, worth knowing before building (2)

Zotero's own extractor carries caps of its own — `fulltext.pdfMaxPages` defaults
to 100. I probed the local API against the cache on three attachments including
one sitting exactly at that cap (`indexedPages` 100, `totalPages` 114) and the
API serves the cache byte-identically, so for those attachments the platform has
already truncated before zoteus sees anything. Not all of them: the reference
work above reaches zoteus whole, at its full 43 MiB. The regime is mixed across
a real library. Streaming raises the ceiling for the documents that arrive
whole; it cannot recover the ones Zotero capped.

## Reproduction

1. Index a library containing a book-length PDF with
   `ZOTEUS_INDEX_FULLTEXT=true`.
2. `zotero_semantic_search` for a distinctive phrase from late in that book.
3. No hit; `zotero_index` action:"status" reports the item as indexed and says
   nothing about the body.
4. Rebuild with `ZOTEUS_INDEX_FULLTEXT_MAX_CHARS=0` — the phrase is found. This
   identifies the cap as the cause; see above for why it is not the remedy.
