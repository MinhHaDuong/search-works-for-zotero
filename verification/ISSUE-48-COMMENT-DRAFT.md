A reading of the v1.12.0 source that may help scope this, with the seams named, and a regression test for the resume half in the same spirit as the one on #24.

**What happens on the 429.** `ApiEmbeddingProvider.embedBatch` is a bare `fetch` that throws on any non-2xx status (`src/features/search/embeddings.ts:313`). The build does not abort there: `embedPending` catches the throw, records it as `embedderError`, and empties the remaining queue (`index-manager.ts:1745-1753`), so the rest of the build runs keyword-only and status reports `embedder=none` with the 429 as the reason. Every passage is still stored. `passages.vector` is a nullable column (`sqlite-index.ts:685-692`), and the passages embedded before the failure keep theirs; the ones after it are `NULL`. What is missing is not state but two pieces of code.

**1. Retry, on the embedder's path.** `RateLimitedFetcher` (`src/api/http.ts:81-87`) already retries 429 and 503 honoring `Retry-After` with exponential fallback, bounded by attempts and a deadline, for the Zotero web API. The two provider calls in `embedBatch` are not behind it. Behind it, the split should be: 429, 503 and network errors retry; 400, 401 and 403 do not, and fall through to today's labeled degradation (the documented 400 above 300K tokens per request is a sizing fault, not a transient). When retries are exhausted the build degrades exactly as today, and the passages stay `NULL`, which is what makes item 2 pick them up.

**2. Resume, as a query rather than a checkpoint.** Pending embedding work is already representable with no schema change:

```sql
SELECT id, text FROM passages WHERE vector IS NULL
```

Fed to `embedPending` at the end of both `build` and `update`, after the crawl and before the version stamp, it finishes any pass that degraded, restarted, or was killed, and embeds nothing twice. `update` already clears `embedderError` at start (`index-manager.ts:1245`), so a restarted process retries on its own. If the scan matters at 255k rows, a partial index (`CREATE INDEX ... ON passages(pid) WHERE vector IS NULL`) makes it a lookup. The shape to avoid is an embedding cursor in the `checkpoint` blob: a cursor says where a serial pass stopped, not which rows are done, and it stops being true the first time `update` interleaves changed items with a backfill. The nullable column is already the per-row truth; the checkpoint is for the crawl.

**The regression test.** Wrap `FakeEmbeddingProvider` (`embeddings.ts:48`) in a provider that throws a 429 on its Nth call and succeeds after.

1. Full-text build over a fixture library, one 429 mid-run. The build completes with every passage embedded, and the provider's call log shows no text embedded twice.
2. Cancel the build during the embedding pass, reopen the index, run `update` against the unchanged library.
3. Passages that had a vector are not re-sent to the provider; passages that had `NULL` are, and only those.
4. The resumed index and an uninterrupted build have the same `vectors` count (`sqlite-index.ts:862`) and the same `vector_codes` count.
5. Exhaust the retries (a provider that always answers 429): status reports the labeled degradation, no passage is lost, and the next `update` with a working provider fills every `NULL`.

**Sizing and the dials.** Both dials are documented at v1.12.0 (`docs/configuration.md:18-19`, `docs/semantic-search.md:638-653`), with the tokens-per-minute guidance; the npm package may not ship `docs/`, which would explain finding them only in `dist/config.js`. The default `ZOTEUS_EMBED_BATCH_SIZE` is 32, not 500. At 500 passages of ~240 tokens a request is ~120k tokens, so on a 1M TPM tier eight requests fill the minute and any two inside 7 s trip the limit. Two rules would replace the arithmetic done by hand here: cap each request by an estimated token count (characters divided by four is within the providers' own tolerance) under the provider's per-request ceiling, and pace on a trailing-minute token total rather than a fixed delay. The status line then reports tokens per request and per minute from the same two numbers, which is request 4. The batch size does not change the total time: the TPM ceiling does, however the requests are cut.

Stated once: a passage without a vector is pending work, not history, and a provider failure is a property of one request, not of the index. That is also what makes the embedding pass safe to run anywhere, in the server process, in a child, or on a later day, since whatever runs it can die at any point and lose at most the batch in flight.
