Reproduced on `main` at `5a81cee88be6d979e9ca1e99e897b6b6df25beef` on both memory and SQLite backends, with deterministic embeddings and real index build/query paths.

### Minimal reproduction

Build an index containing one paper with forty short annotations and four other relevant papers. Give the annotation passages vectors `[1, 0]`, the other papers vectors `[0.8, 0.6]`, and the query vector `[1, 0]`. This makes all five papers relevant while the annotations rank first at passage level.

Query in semantic mode with `limit: 5`: the result contains only the annotated paper. Querying the same index with `limit: 20` returns all five distinct papers. The larger call is a control showing that the other papers and their vectors are present, not an absent-indexing case.

### Actual versus expected behavior

[src/features/search/index-manager.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/features/search/index-manager.ts) fixes each retrieval pool at `limit * 3`, fuses passage candidates, and only then deduplicates by `itemKey`. With the smaller request all selected passages belong to one paper, so the remaining relevant items never reach deduplication.

An annotated paper should occupy one result slot while leaving room for other relevant items up to the requested item limit. Deduplicating the returned array alone does not ensure that.

### Smallest fix shape

Progressively widen the passage candidate pool until enough distinct items are available or the candidates are exhausted, or retrieve at item level where the backend supports it. Reuse the query embedding across retries and retain a clear work bound. Avoid replacing the current fixed multiplier with another fixed multiplier that merely moves the failure point.

### Acceptance criteria

- The concentrated-annotation fixture returns the requested distinct papers on both backends when enough candidates exist.
- Cover child notes as well as annotations, plus keyword and hybrid modes where the same pool/deduplication sequence applies.
- A library with fewer eligible items terminates and returns the available distinct items.
- Preserve item attribution and the source label on each chosen snippet.

Related: #33/#36 made child passages searchable under their parent item; this is a recall defect in the finite candidate pool, not a request to remove those passages.
