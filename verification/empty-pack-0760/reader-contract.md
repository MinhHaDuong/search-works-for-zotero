# What makes a native pack *verifiably* empty — ticket 0760

Ticket 0760's first Action asks whether the native format and reader offer "an
authoritative complete-content indicator", and its Verification list requires
the answer to be committed rather than asserted. This is that answer, measured
against Zotero's own shipped reader and the author's own packs.

- Probe: [`probe.mjs`](./probe.mjs) — reads only; emits no title, no text, no
  storage key, no path beyond the two roots it is given.
- Reading: [`reading.json`](./reading.json), 2026-09-13.
- Reader under test: `<zotero-app>/resource/document-worker/structured-document-text.js`,
  sha256 `340f44fea8d616eaac04b83ef6329eaad2753916b1d50342a8edc7a0b717bed4` —
  the same build `bench/results/sdt-diagnostic-2026-09-05/pack-roundtrip.json`
  was taken against.

```
node verification/empty-pack-0760/probe.mjs \
  <zotero-app>/resource/document-worker/structured-document-text.js \
  ~/Zotero/storage
```

## There is no positive indicator, and that is the finding

The reader's whole surface, read off the live object:

    getBlock  getBlocks  getCatalog  getMetadata  getPageBlocks
    getTopLevelBlockCount  materialize  header  index

No field answers "does this document contain text". Nothing counts runs,
nothing summarises block types, and `getMetadata()` describes the *source* and
the *processor*, not the yield. So presence cannot be read; it can only be
enumerated, which is what `packSDTTextVerdict` does.

## What makes the enumeration trustworthy is a refusal, not a flag

`openStructuredDocumentTextPack` validates before it returns: magic bytes,
index shape (`chunkByteOffsets` and `chunkBlockStarts` both zero-based and
strictly increasing), and — the load-bearing one — `validatePackLayout`, which
requires the declared content extent to land exactly on the file's own length.
A pack that opens has therefore already proved that its block index describes
the whole file, so `getTopLevelBlockCount()` cannot silently under-report a
truncated or half-written pack.

That claim is worth nothing unless the refusal actually fires, so the probe
corrupts a real pack four ways and requires an exception from each. All four
fired:

| Mutation | Reader's answer |
|---|---|
| flipped magic byte | throws `Invalid SDTPack magic` |
| truncated by one byte | throws `Invalid SDTPack layout outside file` |
| content extent understated | throws `Invalid SDTPack chunkByteOffsets` |
| block index zeroed (would manufacture a false "verified empty") | throws `Invalid SDTPack chunkBlockStarts` |

The fourth is the one that matters: the mutation that makes a text-bearing pack
*declare* zero blocks is refused rather than answered. A probe that only ever
met well-formed packs would have reported the same "all clear" whether this
validation existed or not.

## The one completeness indicator the format does carry is negative

`getCatalog()` returns `{ outline, pages }`, and each page record carries
`extractionDegraded`. The native worker has fallback paths for inference
overload and per-page inference errors, and a page that took one is stamped
here — read in `verification/SDT-PALGRAVE-AUDIT.md` (worker.js:143251, 153043),
which states the consequence directly: *a generated pack must not be presented
as evidence that every page received full-quality layout analysis.*

This is the authoritative indicator Action 1 asked for, and it is negative: it
can never confirm that text was found, only withdraw the claim that its absence
was established. So the rule the implementation now follows is

> textless **and** every page undegraded → `empty-pack` (verified empty)
>
> textless **and** any page degraded, or the catalog unreadable, or no page
> records at all → `current` (unknown; unchanged admission, unchanged retries)

which is SPEC.md §5.2.7's "Unknown content remains unknown, never a confident
empty classification" applied to the one case that can actually reach it.

## Measured on the author's library

46 packs, 11 909 pages:

| | count |
|---|---|
| packs carrying text | 43 |
| packs verified empty | 3 (265, 340 and 347 blocks) |
| packs unknown | 0 |
| packs the reader refused | 0 |
| degraded pages | 29, all in **one** text-bearing pack |
| packs that are both textless and degraded | **0** |

Two things follow, and the second is the honest one.

First, requiring a readable non-empty `pages` array costs no real document its
empty verdict: every pack here carries one, EPUB as well as PDF. The guard was
measured before it was written rather than assumed to be free.

Second, **the defect this guard closes is latent, not observed.** The
population where a textless pack meets a degraded page is empty in this
library, so nothing was being misclassified on 2026-09-13. The case for
closing it now is that the combination is reachable by construction — one
inference-overloaded scan of an image-only document produces it — and that the
claim it would print, "No extracted text", is a confident one under a heading
the reader is invited to act on with OCR.

## Scope, and what this does not establish

- Nothing here diagnoses a *source*. An empty native pack says the extractor
  found no text in this document; it does not prove the PDF has no text layer,
  does not identify a scan, and does not recommend OCR beyond the conditional
  wording the panel already uses.
- The three empty packs are not extrapolated to a population. They are three
  packs in one library, reported as such.
- The probe reads packs at rest. It does not exercise the sitter's cache path,
  its scheduling, or Gecko; those are covered by `tests/sdt_sitter_bootstrap.mjs`
  and the mutation gate, not by this file.
