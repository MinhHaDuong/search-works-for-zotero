Revalidated on `main` at `5a81cee88be6d979e9ca1e99e897b6b6df25beef` with the real tool handlers and `LibraryRouter`, using stubbed API transports (no live library writes).

### Reproduction and actual behavior

1. Configure `ZOTERO_LIBRARY_TYPE=group`, `ZOTERO_LIBRARY_ID=456`, and a cloud key whose user ID is `123`.
2. Call `zotero_create_items` with `{"items":[{"itemType":"book","title":"Routing probe"}]}`, omitting per-call library arguments.
3. `router.defaultLibrary()` resolves group `456`, but `requireCloudLibrary()` resolves user `123`; the create handler sends the write to the personal library.

A second path loses the same effective-library choice before writing:

1. Leave the personal library as the default, and choose a PDF attachment that exists only in group `456`.
2. Call `zotero_annotate` with `{"parent":"PDFGROUP","library_type":"group","library_id":456,"annotations":[{"type":"note","comment":"Routing probe","page":0}]}`.
3. The initial parent lookup uses the personal library and fails before the group write can happen. The reproduction transport returns a 404 for that wrong-library lookup and confirms no write occurs.

### Expected behavior

An explicit per-call library overrides the configured default. Otherwise the configured library applies to the whole operation: parent/children reads, attachment lookup, and writes. Unsupported write targets should fail clearly before mutation, without silently selecting the personal library.

### Smallest fix shape

Resolve the effective library once and pass it throughout the operation. Have `requireCloudLibrary()` respect the configured default, and gate personal-library desktop/connector shortcuts on the resolved library rather than just `!args.library_id`.

Relevant code: [src/registry/registry.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/registry/registry.ts), [src/tools/create-items.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/tools/create-items.ts), [src/tools/annotate.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/tools/annotate.ts), [src/router/library-router.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/router/library-router.ts).

### Acceptance criteria

- A create with a group default and no per-call library writes only to that group.
- Explicit personal/group overrides still select the requested library.
- An annotation parent and its children are read from the selected group, for both direct attachment keys and regular-item parents.
- Local/connector fallback cannot redirect a group operation to the personal library.

Related: #53 describes configured library selection for an instance; this issue concerns write/annotation routing within that selection, not multi-library indexing.
