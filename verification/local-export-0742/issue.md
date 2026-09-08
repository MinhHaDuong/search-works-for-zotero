Following your invitation in [the #64 reply](https://github.com/oscardvs/zoteus/issues/64#issuecomment-5575903719). I explored the desktop export surface to help scope the follow-up.

On main at `446766320867f1a0a2c6c55ab63b3df734a05c69`, `zotero_export` still calls `ctx.web.exportItems` in both its ordinary stock-export branch and the stock `biblatex` fallback when Better BibTeX is unavailable. The router and local client now expose the required export operation following #64.

### Expected behavior

A library served by local Zotero should support stock `zotero_export` without a cloud key, following the same selected-library routing as bibliography generation. Keep the working Better BibTeX branch and explicit cloud-library behavior.

### Read-only desktop exploration

Probed the personal-library loopback API on 2026-09-08 without a cloud key. Requests were GETs; nothing was added or edited. Response content and library identifiers are omitted here.

- Every stock format exposed by the tool returned a successful, nonempty response for a sampled parent through `/api/users/0/items/top?itemKey=KEY&format=FORMAT`: `bibtex`, `biblatex`, `ris`, `csljson`, `csv`, `mods`, `tei`, `coins`, `rdf_bibliontology`, `rdf_dc`, `rdf_zotero`, `refer`, `wikipedia`, `bookmarks`. This checks response availability, not translator fidelity.
- For CSL-JSON, exported titles and result cardinality matched the ordinary JSON response for the same path and selectors: explicit parent key, `limit`, `itemType`, matching `q`, nonmatching `q`, collection selection, collection plus item key, and collection plus query/type/limit. Responses were bare arrays.
- The keyed `/items/top` path excluded an attachment child when exporting its parent. A child key alone returned an empty array, matching the behavior you described in #64. The keyed collection `/collections/COLLECTION/items/top` path also worked.
- An invalid format returned a client error identifying the invalid format.

For reproduction on a library of your choice, compare these endpoints first with ordinary JSON, then with `format=csljson` appended:

```text
/api/users/0/items/top?itemKey=PARENT
/api/users/0/items?limit=1
/api/users/0/items?itemType=book&limit=3
/api/users/0/items?q=URL_ENCODED_TITLE&limit=3
/api/users/0/items?q=DELIBERATELY_NONMATCHING_QUERY&limit=3
/api/users/0/collections/COLLECTION/items?limit=3
/api/users/0/collections/COLLECTION/items/top?itemKey=MEMBER_PARENT
/api/users/0/collections/COLLECTION/items?q=URL_ENCODED_TITLE&itemType=book&limit=3
/api/users/0/items/top?itemKey=ATTACHMENT_CHILD
```

Use a matching item type and a known collection member for the combined query. Then try each stock format on the explicit-parent endpoint.

### Suggested implementation and regression coverage

Route both stock calls through `ctx.router.exportItems({ library: lib, ...params })`, retaining the existing format, selectors and limit. Update the tool description and fallback comment that currently describe stock export as cloud-only.

Tests should cover key-free personal-library routing, a locally held group, an explicit cloud library, selector/limit forwarding, and the Better BibTeX-to-stock fallback. Preserve the raw-text and structured payloads, degradation notice, and useful local API error bodies.

Limits of this exploration: direct desktop API probes, not an end-to-end modified-tool run; sampled personal-library records only; no group-library or Better BibTeX runtime probe, no cloud parity comparison, and no exhaustive validation of translators. The CSL comparisons establish agreement with local JSON selection, not independent correctness of the underlying search. No claim of fully offline operation or network-egress tracing.
