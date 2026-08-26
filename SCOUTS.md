# SCOUTS — upstream design-doc findings, 2026-08-26 (inputs to design cycle 2)

# Scout-derived sheet candidates (for the ratification desk, beside the panel delta)

From the official API docs + Zotero source (scout 3):
- C1 SHARPENING — local `/fulltext?since=` versions are a mixed sequence (web stamps / local
  client versions / 0 for local extraction) and the filter is `since=0 OR version>since`:
  they are equality-comparable per item, NEVER a monotonic cursor. Any design cursoring
  that counter on the local transport silently loses locally-extracted text.
- C1 SHARPENING — version validity is scoped by `Zotero-Server-ID` (docs: "a different ID
  means a different database and therefore a different set of object versions and keys";
  clients that store data between runs "should partition it by server ID"). A local/cloud
  label is not enough: two local profiles share the label and share nothing else.
- NEW CONSTRAINT CANDIDATE (politeness, web transport only) — ≤4 concurrent requests;
  honor `Backoff: <seconds>` on ANY response including 2xx; honor 429/`Retry-After` with
  exponential fallback. Local API: no rate limits, unpaginated by default.
- CONFIRMED — no `/deleted` on the local API; key-set diff (`format=versions`, unlimited)
  is the documented deletion route. The fork's census design was right.
- MOVING-TARGET SHARPENING — local API: "only one API version will ever be supported at a
  time"; read `Zotero-API-Version` / `Zotero-Schema-Version` headers.

From the SDT pack design (scout 4; zotero/structured-document-text is PUBLIC):
- ADAPTER PATH IS CONCRETE — the pack is a random-access container (16-byte header, index,
  32 KiB-target independently-deflated chunk groups); the reader contract is
  `{byteLength, read(offset,length)}`, which maps 1:1 onto HTTP Range requests; open costs
  one ≤64 KB read. If the local API ever serves packs, the extract stage swaps without
  touching chunks/vectors. Pack is self-describing: packVersion + schemaVersion +
  processor{type,version} + source.hash — exactly our C1 key shape, already shipped.
- MONSTER-DOC ANSWER EXISTS PLATFORM-SIDE — section-at-a-time reads with bounded memory is
  the pack's designed use ("memory use can stay bounded by the sections or chunks being
  accessed"). C3's streaming requirement has platform prior art.
- CHUNKING PRIOR ART CONTRADICTS UPSTREAM'S GEOMETRY — Zotero chunks by TOKENS on
  STRUCTURAL boundaries: 120 min / 768 max / 48 overlap only within a split paragraph,
  never across sections; heading path injected into embed text; captions lifted out;
  bibliography entries dropped from embedding. Upstream's 512-char fixed-stride chunks sit
  BELOW Zotero's minimum ("splitting text into fragments inflates the score without adding
  information"). R7/R8 quality work should weigh structural-token chunking, not tune char
  strides.
- CORPUS BOUNDS — processors exist for pdf / epub / snapshot only; OCR text is flagged
  per-page (`textSource:'ocr'`, `extractionDegraded`) — a quality-floor signal exists.
- THEIR OWN DOCUMENTED GAP — a processor bump without a file change is deliberately not
  chased by their embeddings layer ("vectors stay derived from the older extraction until
  the file changes or the index is rebuilt"). Even Zotero accepts a staleness residue here.

From the maintainer's docs (scout 1): see conflicts table in conversation — cap defaults vs
R8/R9, coarse invalidation vs R3, no ordering commitment vs R2, hostility to unrequested
heavy work vs R1, English-centric default model vs R7; vocabulary and merge-shaping rules.

From Zotero #6012's rationale (scout 2 — the richest haul):
- R2 TENSION — their monster-doc fairness is SCHEDULING, not truncation, and it is
  smallest-first: metadata/notes/annotations for ALL libraries first, then attachments
  ordered smallest-first "so one enormous book doesn't sit at the head of the queue",
  sizes read from the existing fulltext index (no stat). Notifier-driven changes bypass
  the ordering. Our sheet says newest-first; theirs says smallest-first-within-attachments.
  These compose (newest-first for metadata, smallest-first within the fulltext phase) but
  that is a ratification decision, not an assumption.
- R5 CORRECTION CANDIDATE — they measured that constraining FTS5 MATCH to a rowid set
  "makes FTS5 evaluate the expression per row, which at library scale costs seconds";
  they run MATCH unconstrained and filter candidates in JS. Our R5 says "pushed into SQL,
  never post-filtering" — right for metadata columns, WRONG if read as pushing filters
  into the MATCH itself. Rephrase.
- R7 CJK ANSWER EXISTS — dedicated FTS5 2-gram twin tables for Han/Kana/Hangul runs beside
  the unicode61 word tables; sentence/word boundaries via Intl.Segmenter; SentencePiece
  tokenizers are QUADRATIC in input length (they cap encode segments at 1,000 chars).
- CALIBRATION, MEASURED NOT CONFIGURED — per model-version: mean-vector centering (removes
  the common direction that makes everything look moderately similar), noise floor = p99
  of unrelated pairs, display ceiling = median of matched pairs, model rejected outright if
  matched-median <= null-p99 ("better to fail loudly than to index with it"). Portable.
- STORE REFERENCES, NOT TEXT — chunk rows carry block ranges + offsets + an 8-hex
  fingerprint; snippets re-derived from the pack at display and verified ("null text
  rather than the wrong words"). Halves storage and makes drift detectable.
- RESOURCE PACING PRIOR ART (C3) — token-budget batching (3,000 tokens, chunks sorted by
  length ≈ halves fulltext indexing time); on OS memory pressure the budget halves and the
  engine restarts ("its memory arena never shrinks"); refuses to start under 1.5 GB free;
  engine shut down the moment the queue drains; per-item transactional writes so a stop
  mid-item never fakes completeness.
- R4 PATTERN — IndexNotReadyError: BestMatch catches it and drops the semantic engine from
  the query, leaving lexical scores alone. Partial vectors serve as they exist.
- FUSION — fraction-weighted RRF at k=60 (rank rewards agreement; the fraction keeps a
  strong single-engine match from capping at half); item score = MAX over chunks (bounds
  the 0013 dictionary concentration differently than idf arguments do).
- SCALE HONESTY — their design point is 5K items, in-memory scoring over the CURRENT SCOPE
  only, sqlite-vec named as the escape hatch "if needed". Our R8 point is beyond theirs.
- TRAJECTORY — local API untouched by #6012 today, BUT the bestMatch saved-search
  condition serializes with a top-K cutoff so saved searches "return the same set when
  used as a source (scopes, counts, the API)" — semantic result sets will leak into the
  local API via saved searches once merged. First crack in the wall.
