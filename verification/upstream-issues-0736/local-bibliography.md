Following your invitation in [the #58 reply](https://github.com/oscardvs/zoteus/issues/58#issuecomment-5559939505) to file local bibliography routing separately. Revalidated on `main` at `5a81cee88be6d979e9ca1e99e897b6b6df25beef`; the style forwarding/alias fixes from #58 are present.

### Minimal reproduction

1. Run Zotero with its local API enabled, set `ZOTEUS_LOCAL=on`, and leave `ZOTERO_API_KEY` unset.
2. Confirm that a personal-library item is readable locally.
3. Call `zotero_bibliography` with `{"item_keys":["LOCALKEY"]}`.
4. Call `zotero_format_bibliography` with the same `item_keys` input.

### Actual behavior

Both item-key paths bypass the local-capable router and use `ctx.web`: `getBibliography()` in the first tool and `exportItems(format="csljson")` in the second. In key-free personal-library mode the default library is `users/0`, so both requests target `https://api.zotero.org/users/0/items?...` instead of the local API.

This was reproduced with the real handlers, router, and Web API client, capturing transport URLs and supplying a deterministic HTTP 400 response. No live cloud/library data was needed. Supplying CSL-JSON via `items` to `zotero_format_bibliography` avoids this item-export path and is not the defect reported here.

### Expected behavior

Library-backed bibliography generation should work for a library already readable through local Zotero, without a cloud key. Rendered bibliography and CSL-JSON export should follow the selected library's read transport. Style/locale retrieval is a separate concern; this request does not claim fully offline formatting.

### Smallest fix shape

Add routed bibliography/export reads, or compose the existing routed item reads with local CSL rendering where appropriate. Keep explicit library, style, and locale selection throughout; preserve the supplied-CSL path.

Relevant code: [src/tools/bibliography.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/tools/bibliography.ts), [src/tools/format-bibliography.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/tools/format-bibliography.ts), [src/router/library-router.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/router/library-router.ts), [src/api/web-client.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/api/web-client.ts).

### Acceptance criteria

- Both item-key tools produce a bibliography from a local personal library without a cloud key.
- Tests assert the local library transport is used and no request goes to cloud `users/0`.
- Cover a locally available group and an explicit cloud-library selection.
- Keep style/locale behavior and the direct CSL-JSON formatting path intact.
