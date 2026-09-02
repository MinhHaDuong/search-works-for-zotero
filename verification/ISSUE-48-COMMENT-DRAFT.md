Two readings of the v1.12.0 source that may help scope this, and a testable contract for the resume half, in the same spirit as the one on #24.

**What happens on the 429.** `ApiEmbeddingProvider.embedBatch` is a bare `fetch` that throws on any non-2xx status (`src/features/search/embeddings.ts:313`). The build does not abort there: `embedPending` catches the throw, records it as `embedderError`, and empties the remaining queue (`index-manager.ts:1745-1753`), so the rest of the build runs keyword-only and status reports `embedder=none` with the 429 as the reason. Every passage is still stored; only the vectors from that point on are missing. A retry loop that honors `Retry-After` with exponential fallback already exists in the tree: `RateLimitedFetcher` (`src/api/http.ts:81-87`) does exactly that for the Zotero web API. It is just not on the embedder's path. Putting the two provider calls behind it would close request 1 without new machinery.

**Why a resume re-embeds everything.** The checkpoint that survives (`resumedFrom`, `index-manager.ts:831`) records crawl progress, not embedding progress, and nothing records which stored passages lack a vector. After a degraded build there is no unit of work smaller than "rebuild" that fills the gap, and a rebuild re-embeds every passage. `VectorSalvage` would hand back the 53k–84k vectors already paid for, but it is armed only when an index is sidelined for a schema mismatch (`sqlite-index.ts:579`), not on an ordinary rebuild.

The contract for request 2, as a regression test:

1. Build with full text against a provider that answers 429 once, mid-run, then succeeds. The build completes with every passage embedded, and no vector is computed twice.
2. Kill the process during the embedding pass, restart, and run `update` against the unchanged library.
3. Passages that already had a vector are not re-embedded; passages that did not are, and only those.
4. Finding them does not require scanning every stored passage. A "vector missing" set, or a flag on the passage row, is enough.
5. A resumed run and an uninterrupted run converge to the same vector count.

Stated once: a passage without a vector is pending work, not history, and a provider failure is a property of one request, not of the index. That is also what makes the embedding pass safe to run anywhere, in the server process, in a child, or on a later day, since whatever runs it can die at any point and lose at most the batch in flight.

**On the throttle dials.** Both are documented at v1.12.0, in `docs/configuration.md` (rows 18–19) and `docs/semantic-search.md` (around line 638), with the tokens-per-minute guidance. The npm package may not ship `docs/`, which would explain finding them only in `dist/config.js`. Note that the default `ZOTEUS_EMBED_BATCH_SIZE` is 32, not 500: at 500 passages of ~240 tokens a request is ~120k tokens, so on a 1M TPM tier eight requests are the whole minute, and any two arriving inside 7 s trip the limit. Sizing a request by a token budget rather than a passage count, and pacing on tokens per minute rather than on a fixed delay, would make the arithmetic done by hand here the provider's own; request 4, surfacing that arithmetic in status, then comes from the same numbers. The batch size does not change the total time: the TPM ceiling does, however the requests are cut.
