# Zoteus v1.16.0 (910310b) — SAFETY seat: user data and library integrity

Scope: the tools that write to the user's Zotero library, the library routing added for #61, and the search-index store (build / update / pause / migration / repair). Read-only review of `src/` and `tests/`; no code was run against a live Zotero, so every claim about Zotero's own server behaviour is flagged as such and sourced to the public API contract or to Zoteus's own comments. Line numbers are from the clone at 910310b.

## Verdict

No release-blocking defect on the library-write side that I could demonstrate from the code alone: the two irreversible tools (`zotero_delete_items`, collection delete) do what they say, the #61 routing decision is made once per call in every write tool, and the index store never deletes a file except on an explicit `action:"build"` over a fault it itself named. Three defects are should-fix at high priority because each produces a *silent* wrong state rather than an error: (1) any second Zoteus process on the same data directory rewrites the index's on-disk stamp, checkpoint, library and pause flag from its own stale memory when it saves or exits, which turns a finished index into one the next `action:"update"` erases and rebuilds — and the docs recommend exactly that two-process setup; (2) the incremental update drops an item's PDF body passages for good when the full-text read for that item fails transiently (the full-text sibling of #63, which fixed only the notes/annotations lane); (3) the connector-protocol save path (Zotero 7–9 desktop, the default desktop write path before Zotero 10) saves into whatever library is selected in the Zotero pane, so a "personal" write can land in a shared group. Below them: a cloud permanent delete of more than 50 keys purges the first 50 and then fails on a stale precondition, an ungated hard delete of collections, and a `library_type` argument that is silently ignored without `library_id`.

---

## Findings (most severe first)

### 1. A second process on the same data dir overwrites the index's stamp, checkpoint, library and pause flag from stale memory — and the next `update` then erases the index

**Severity:** should-fix (high). Silent; ends in a full rebuild (hours, plus API embedding spend) of an index that was complete; also silently clears a durable pause and the library guard.

**Where.**
- `src/features/search/sqlite-index.ts:2053-2058`
  ```ts
  private flush(): void {
    if (!this.db) return;
    this.begin();
    this.writeMeta();
    this.commit();
  }
  ```
  `writeMeta()` (`:1112-1128`) unconditionally writes `builtFromVersion`, `itemsTotal`, `itemsAvailable`, `embedderId`, `libraryVersion`, `libraryBackend`, `fulltextVersion`, `checkpoint`, `paused`, `library` from the instance's fields. Nothing is dirty-tracked; nothing re-reads the row before writing.
- `flush()` runs from `save()` (`:2067-2072`) and from `close()` (`:2074-2090`, "Whatever was indexed is worth keeping; an abandoned transaction would discard it"). `persistPaused()` (`:2060-2065`) also calls `writeMeta(paused)` — the whole row, not just the flag.
- The server calls both on every shutdown: `src/server.ts:401-410` (`c.search.save()` then `c.search.close()`).
- Meta is loaded exactly once per handle, at `open()` (`:458 loadMeta()`), and after a rollback (`:1403`). There is no periodic reload.
- The JSON backend is worse: `MemorySearchIndex.save()` (`src/features/search/index-manager.ts:2707-2726`) serialises the entire in-memory index over the file (`toJSON()` then atomic rename), rows included.

**The documented setup that triggers it.** `docs/semantic-search.md:459-471` recommends building headlessly "against the same `ZOTEUS_DATA_DIR`" while Claude Desktop's Zoteus is running, and the tool description repeats it (`src/tools/index-tool.ts:20`, "a user who wants the fastest possible first build can still run one headlessly against the same ZOTEUS_DATA_DIR and let Desktop read the result"). `sqlite-index.ts:236-241` says the 10 s busy timeout exists precisely because "processes legitimately share a data dir".

**Failure scenario.**
1. Claude Desktop's Zoteus (process A) starts; the index is empty or stale. A's memory: `libraryVersion=0`, `checkpoint=undefined`, `library=undefined`, `fulltextVersion=0`.
2. The user runs the headless build (process B) with `fulltext:true`. Hours later B commits a complete index: 97 000 passages, `libraryVersion=V`, `libraryBackend='local'`, `library='user:123'`, `checkpoint=''`.
3. The user quits Claude Desktop. A's shutdown runs `save()` + `close()`, so `flush()`, so `writeMeta()` writes `libraryVersion='0'`, `library=''`, `embedderId=''`, `fulltextVersion='0'` over B's row. Nothing errors, nothing logs.
4. Next session, `zotero_index action:"update"` (the tool description says it "should be the default for a library that is already indexed"): `updateBlocker()` at `index-manager.ts:1534-1541` returns "this index carries no library version stamp"; `startIndexUpdate` falls back to `startIndexBuild` (`build.ts:480-489`); `resumeFrom()` finds no checkpoint; `reset()` calls `clearStore()` (`sqlite-index.ts:1220-1225`), which deletes every passage at the build's first commit. The complete full-text index is gone and is rebuilt from scratch, re-embedding everything. This is the #59 outcome ("a 1,300-item partial index where a complete 97,000-passage one had been") by a different route, and nothing in the status says why.

   Variants: B's `action:"pause"` is undone by A's exit (A writes `paused='false'`); B's `library` stamp is erased, disarming `assertLibrary` for the next build; on the JSON backend A's exit replaces B's rows outright.

**What a maintainer would have to believe for this to be harmless:** that no second process ever holds an index handle across another process's build. The docs and the busy-timeout comment say the opposite.

**Minimal fix.** Make meta writes ownership-aware: (a) keep the tuple loaded by `loadMeta()` (`libraryVersion`, `checkpoint`, `paused`, `library`) and in `flush()`/`persistPaused()` write only the fields this instance actually changed — an idle process should commit nothing on close; (b) cheaper still, guard `writeMeta()` with `UPDATE meta ... WHERE value = <loaded value>` on `libraryVersion` and skip with a warning when the row moved under it. For the JSON backend, refuse the shutdown save when the file on disk carries a newer `libraryVersion` than the one loaded.

**Positive control (vitest sketch).**
```ts
const file = join(tmpdir, 'search-index.sqlite');
const a = new SqliteSearchIndex({ path: file }); await a.open();          // idle process
const b = new SqliteSearchIndex({ path: file }); await b.open();
await b.buildIncremental(fetchPage, { versionBackend: 'cloud', library: 'user:1' });
expect(b.buildStatus().libraryVersion).toBe(42);
await b.close();
await a.close();                                                          // idle process exits
const c = new SqliteSearchIndex({ path: file }); await c.open();
expect(c.buildStatus().libraryVersion).toBe(42);                          // FAILS today: 0
expect(c.updateBlocker('cloud')).toBeUndefined();                         // FAILS today: "no library version stamp"
```

---

### 2. An incremental update silently drops an item's PDF body text when its full-text read fails transiently (full-text sibling of #63)

**Severity:** should-fix (high). Silent, permanent until a full rebuild; the stamp and cursor advance, so no later update revisits the item.

**Where.**
- `src/features/search/index-manager.ts:1650` — `const texts = await this.fulltextForPage(pageItems, opts, token, fulltextLimit);`
- `:2102-2131` — `fulltextForPage` wraps every read: `catch (e) { this.opts.logger?.debug(...); return undefined; }`. Below it, `createFulltextSource().textFor` (`src/features/search/fulltext-source.ts:167-195`) also catches per attachment (`failures++`, `continue`) and returns `undefined` when nothing was read — the same value it returns for "this item has no extracted text".
- `:1688-1689`
  ```ts
  this.deleteItem(key);
  this.addOneItem(item, pending, texts?.[i], own?.[i]);
  ```
  `deleteItem` removes *all* of the item's passages, body text included (`sqlite-index.ts:1325-1335`, `deletePassages: DELETE FROM passages WHERE item_key = ?`). `addOneItem` (`:2201-2208`) re-adds body text only `if (fulltext)`.
- The update never consults `readFailures()`: `fulltextFailures` is read only in `buildIncremental` (`:1412-1413`, `:1462`). The stamp is written at `:1777-1779` gated on `ownWordsGap` only; the full-text cursor at `:1788` gated on `reconciled` only.
- The catch-up pass has the same gap: `fulltextCatchUp` computes `const version = Math.max(since, answer.version)` (`:1895`) before any read, skips unreadable items with `if (!text) continue;` (`:1917`), and returns the advanced cursor regardless (`:1929`).

Contrast the notes/annotations lane, which #63 fixed in this release: `:1656-1686` reads the old own-words rows back (`ownWordsRecords`) and re-inserts them when the census cannot be read, and `ownWordsGap` withholds the stamp. Nothing equivalent exists for `source = 'fulltext'`.

**Failure scenario.** Index built with `fulltext:true`; item K holds 40 body passages. The user edits K's tags in Zotero (K enters the next `?since=` delta). `action:"update"` runs while the desktop app is busy (the saturation #39 describes) or the Web API answers 429 past the budget: `router.getFullText(K's attachment)` throws, `textFor` returns `undefined`, K is re-indexed with metadata only. Stamp advances to V. K's attachment is unchanged in Zotero, so it appears in no later delta; `fullTextSince(cursor)` never returns it because its extraction version is older than the cursor. K's body is unsearchable until someone runs `action:"refresh"`, and `status` shows only `fulltextItems` one lower than before. The same happens to every changed item on a page while Zotero is saturated — dozens at a time.

**What a maintainer would have to believe for this to be harmless:** that a full-text read never fails on an item that was readable at build time. `noteLocalApiDegraded` (`:657-668`) and #39 document that it does.

**Minimal fix.** Distinguish "no text" from "could not read" (have `textFor` throw, or return `{ text?, failed: true }`, or snapshot `readFailures()` around each page). On failure for an item the index already holds body text for: do not `deleteItem`; replace metadata only, or read the body rows back the way `ownWordsRecords` does and re-insert them; and set a `fulltextGap` that withholds the stamp exactly as `ownWordsGap` does at `:1777`. In `fulltextCatchUp`, return `since` (not `answer.version`) whenever any read in the loop failed.

**Positive control (vitest sketch, mirrors `tests/features/search-own-words-retry.test.ts:296-318`).**
```ts
const { lib, search, ctx, router, stamp } = await indexedWithFulltext();   // K has body passages
lib.item('KKKKKKKK', 'Urban heat islands revisited');                       // K enters the delta
failOnce(router, 'getFullText');                                            // one 503 on K's attachment
await update(search, ctx);
expect(await keys(search, '<phrase only in K body>')).toEqual(['KKKKKKKK']); // FAILS today: []
expect(search.buildStatus().libraryVersion).toBe(stamp);                     // FAILS today: advanced
```

---

### 3. Connector-protocol saves go to whatever library is selected in the Zotero pane, not to the library `resolveLibrary` decided

**Severity:** should-fix (high), pending live confirmation. A personal-library write can land in a shared group library visible to collaborators; reversible only by hand.

**Where.**
- `src/tools/import.ts:175-181`
  ```ts
  if (personal && ctx.connectorWrites && (await ensureLocalApi(ctx))) {
    const stripped = payload.map(({ collections: _c, ...rest }) => rest);
    const { sessionID, connectorIds } = await ctx.connectorWrites.saveItems(stripped, {
      uri: 'zotero://zoteus/import',
    });
  ```
  `updateSession` is called only when `collection_key` is given (`:183-189`); with none, the session is never re-targeted. `resolveTreeViewId` (`:356-372`) calls `getSelectedCollection()` but reads only `targets`, never the current library.
- `src/tools/annotate.ts:268-269` takes the same path for annotations.
- The two source comments disagree about what the connector does: `src/api/connector-writes.ts:30-32` says "saves land in the personal library only"; `src/registry/registry.ts:155-160` says "the connector protocol saves into the library the app has open". The second is what Zotero's connector server does: `POST /connector/saveItems` saves to `Zotero.Server.Connector.getSaveTarget()`, the currently selected (editable) library/collection in the pane, falling back to My Library only when the selection is not editable. Zoteus's own `getSelectedCollection()` (`connector-writes.ts:166-177`) is the endpoint that reports that target, and it returns `libraryID`/`libraryEditable` alongside `id`/`targets` — Zoteus discards them.
- This path is the *default* desktop write path for Zotero 7, 8 and 9 (local-API writes exist only from Zotero 10: `local-writes.ts:40-42`), so it is live for most desktop users today.

**Failure scenario.** Zotero 9 desktop is open with the lab's shared group "Grant-2026" selected in the left pane (the user was filing a colleague's paper). The scholar asks the assistant to "add this DOI to my library". `zotero_import save_to_library:true`: `resolveLibrary` says personal, `ensureLocalApi` is true, Zotero 9 has no local writes, so the connector `saveItems` runs and Zotero saves the item (and the `attach_url` PDF) into "Grant-2026". The tool reports `target: 'desktop'`, `created: [...]` (recovered by title from `pollImportedItems`, which lists `users/0` — it may even find nothing and report "could not be matched back yet"). The colleague sees an unrelated item and a PDF appear in the group; the user's own library does not have it.

**What a maintainer would have to believe for this to be harmless:** that the pane is always on My Library when an import runs, or that Zotero routes connector saves to the personal library regardless of selection. I could not run Zotero here; this is the one finding I would confirm live before filing (thirty seconds: select a group in the pane, run `zotero_import ... save_to_library:true` against a Zotero 9 install).

**Minimal fix.** Before `saveItems`, call `getSelectedCollection()` and check the returned library: if it is not the user library, either pass `target: 'L1'` through `updateSession(sessionID, { target: 'L1' })` immediately after the save (the connector's own "change target after saving" mechanism), or fall through to the cloud path with `requireCloud`. Add the library id to the tool's `structuredContent` so the caller can see where the item went.

---

### 4. Cloud permanent delete of more than 50 keys purges the first chunk, then fails the rest on a stale precondition

**Severity:** should-fix. The items were asked for, so this is partial execution plus a misleading error, not unwanted loss — but it is the *irreversible* tool, the description advertises auto-chunking, and no test covers more than 50 keys.

**Where.**
- `src/api/web-client.ts:556-577`
  ```ts
  private async deleteByKeys(path, keyParam, keys, libraryVersion: number): Promise<void> {
    for (const c of chunk(keys, 50)) {
      const url = ...;
      const res = await this.fetcher.fetch(url, {
        method: 'DELETE',
        headers: { ...this.headers(), 'If-Unmodified-Since-Version': String(libraryVersion) },
      });
      if (!res.ok) { ... throw new ZoteroApiError(...) }
    }
  }
  ```
  The same `libraryVersion` is sent for every chunk. The first successful DELETE advances the library version, so the second chunk's `If-Unmodified-Since-Version` is stale. Per the Web API v3 write contract, a multi-object DELETE requires that header to equal the current library version and answers 412 otherwise. The sibling `postArray` (`:512-514`) already carries the version forward between chunks (`currentVersion = newV`), and the local-API client re-probes on 412 (`local-writes.ts:269-274`) — `deleteByKeys` alone does neither.
- `src/tools/delete-items.ts:62-68` reports either full success or throws; the thrown message names no keys, so the caller cannot tell which 50 are gone.
- Test coverage: `tests/api/web-client-writes.test.ts:85-92` exercises `deleteItems` with two keys; `tests/tools/writes.test.ts:158-161` with two. The chunk boundary is untested for DELETE while it is tested for POST (`:46-62`, 60 objects).

**Failure scenario.** `zotero_delete_items item_keys:[60 keys] confirm:true` against the cloud (no desktop app, or a group library). Chunk 1 (50 keys) is purged; chunk 2 gets 412; the tool returns `isError` "Precondition failed…". The model retries with the same 60 keys and a fresh version: chunk 1 now names 50 non-existent keys (Zotero's answer to that is not something I can verify here); the user is left reasoning about which items still exist from a message that says none were deleted.

**Minimal fix.** In `deleteByKeys`, read `Last-Modified-Version` from each successful response and use it for the next chunk (exactly as `postArray` does); on failure, throw an error that carries `deleted: <keys so far>` and have `delete-items.ts` surface it. Add a 60-key test asserting the second request's header equals the first response's `Last-Modified-Version`.

---

### 5. `zotero_manage_collections action:"delete"` is a hard, ungated delete

**Severity:** should-fix. Irreversible loss of a collection tree; not covered by the `ZOTEUS_ALLOW_DELETE` + `confirm` policy that guards `zotero_delete_items`.

**Where.** `src/tools/manage-collections.ts:79-84`
```ts
if (args.action === 'delete') {
  if (!args.collection_key) return err('`collection_key` is required.');
  const version = await ctx.web.currentLibraryVersion(lib);
  await ctx.web.deleteCollections(lib, [args.collection_key], version);
  return ok({ deleted: args.collection_key }, `Deleted collection ${args.collection_key}.`);
}
```
`deleteCollections` (`web-client.ts:480-482`) is the same `DELETE …?collectionKey=` primitive as the item purge — a server-side delete recorded in `/deleted`, not a trash flag. The description (`:19`) says only "delete (needs `collection_key`)". `zotero_saved_searches action:"delete"` (`saved-searches.ts:241-245`) is the same shape at lower stakes.

**Failure scenario.** "Tidy up my collections": the model deletes a top-level collection with fifteen years of nested sub-collections. Items survive in the library, but the hierarchy — the part that was hand-built — is gone. Whether the Web API cascades to sub-collections and whether the desktop client trashes or erases a remotely deleted collection on the next sync are Zotero-side behaviours I could not verify from this tree; either way there is no undo through Zoteus.

**What a maintainer would have to believe for this to be harmless:** that a collection is not user data. The item purge is double-gated on the premise that irreversible operations need consent; this one is the same class.

**Minimal fix.** Require `confirm:true` for `delete` (and, arguably, honour `allowDelete`); say "permanent, removes sub-collections" in the description; mark `destructiveHint` only on the mutating actions.

---

### 6. `library_type` is silently ignored when `library_id` is absent

**Severity:** should-fix (low). With a configured group default, an explicit `library_type:"user"` writes to the group.

**Where.** `src/registry/registry.ts:147-153`
```ts
export function resolveLibrary(ctx, args?) {
  if (args?.library_id) return { type: args.library_type ?? 'group', id: args.library_id };
  return ctx.router.defaultLibrary();
}
```
Every write tool exposes both fields as independent optionals. `library_type:'user'` without an id falls through to `defaultLibrary()`, which is the configured `ZOTERO_LIBRARY_TYPE/ID` (`library-router.ts:68-73`) — a group, in the #61 configuration. The desktop shortcut compounds it: `isPersonalLibrary` (`:161-163`) tests only `lib.type === 'user'`, and the local clients always address `users/0` (`local-writes.ts:283, 312, 327`), so `library_type:'user', library_id:<any number>` writes or deletes in the desktop's own library whatever the id says (`delete-items.ts:50-52`).

**Failure scenario.** `ZOTERO_LIBRARY_TYPE=group ZOTERO_LIBRARY_ID=456` (a shared group as default). The user says "trash this in *my* library"; the model sends `zotero_trash_items item_keys:[K] library_type:"user"`. The key resolves to the group; K in the group is trashed. Reversible, but wrong library — the class #61 was about.

**Minimal fix.** Treat `library_type:'user'` with no id as the key's personal library (`capabilities.cloud.userID`, else `users/0`), and reject `library_type:'group'` with no id. Add the case to `tests/tools/library-routing.test.ts` (which today only tests type+id pairs, `:143-183`).

---

### 7. `zotero_update_item` retries a stale patch after a 412 and overwrites the concurrent edit

**Severity:** should-fix (low). Silent loss of a user's own concurrent change on array fields.

**Where.** `src/tools/update-item.ts:81-90`
```ts
if (err instanceof ZoteroApiError && err.status === 412) {
  const fresh = versionOf(await ctx.web.getItem(lib, args.item_key));
  if (fresh == null) throw err;
  const newVersion = await ctx.web.patchItem(lib, args.item_key, args.patch, fresh);
```
Only the version is refreshed; the patch — computed by the model from an earlier read — is re-sent unchanged. PATCH replaces `tags`/`collections`/`creators` wholesale (the description says so). The 412 existed to stop exactly this.

**Failure scenario.** The model reads item K (tags A, B), decides to add C, and sends `{tags:[A,B,C]}`. Meanwhile the user adds tag D in Zotero (version moves). 412, auto-retry with `{tags:[A,B,C]}`, D is gone; the tool reports "Updated … after a version conflict".

**Minimal fix.** On 412, re-fetch the item, and retry only if none of the patched fields differ between the version the patch was computed against and the fresh one; otherwise return the conflict with the fresh values so the caller can recompute (the `dry_run` diff machinery at `:48-66` already does the comparison).

---

### 8. Nits

- **`zotero_annotate action:"delete"` trashes any keys it is given** (`annotate.ts:118-131`): `setDeleted(keys, 1)` / `writeItems({key, deleted:1})` with no check that the keys are annotations. Reversible (trash), so a nit — but the description says "annotation keys" and nothing enforces it; a regular-item key trashes the item.
- **Local permanent delete: partial-batch error names nothing** (`local-writes.ts:325-334`): chunk N throws after chunks 1..N-1 were purged; same shape as finding 4's reporting half.
- **`zotero_import` has no duplicate guard**: two calls with the same DOI create two items; the code knows (`import.ts:145-147`, `:256-259`, "re-running would duplicate them") and pushes the burden to the caller via a warning. A DOI/arXiv pre-check against the library would close it cheaply.
- **`zotero_attachment save_path` + `overwrite:true` can replace any file the process can write** on stdio (`attachment.ts:58-71`; confinement applies only to `remoteCaller`). The explicit `overwrite` flag is the guard; an LLM can set it. Acceptable for a local tool, but worth naming in the description.

---

## Verified safe (probes that could have fired, and did not)

Each of these is a path I read looking for the same defect class; recorded so the null is distinguishable from "not looked".

- **Permanent item delete is gated twice** (`delete-items.ts:25-46`) and both refusals are tested (`tests/tools/writes.test.ts:144-157`). Trash uses the `deleted` flag, never DELETE, on both APIs (`trash-items.ts:33-36`, tested `:125-137`).
- **#61 routing at every write call site.** Enumerated: `annotate.ts:115`, `attach-file.ts:82`, `import.ts:133`, `delete-items.ts:47`, `trash-items.ts:30` use `resolveLibrary` once and thread `lib` to reads and the cloud write; `create-items.ts:30`, `update-item.ts:47`, `manage-collections.ts:42`, `manage-tags.ts:158`, `saved-searches.ts:227`, `attachment.ts:87` use `requireCloudLibrary`. Cloud writes always carry `lib`; desktop writes are taken only when `isPersonalLibrary(lib)`. The residual gaps are findings 3 (connector target) and 6 (`library_type` alone).
- **Update failure rolls back and keeps the stamp** (`index-manager.ts:1824-1840`, `sqlite-index.ts:1396-1405`); an empty item census withholds the stamp (`:1720-1728`); an own-words gap withholds it (`:1760-1779`); a cancelled update withholds it (`:1788`). Tested in `search-incremental-update.test.ts:255-296` and `search-own-words-retry.test.ts`.
- **Build stamps only when complete**: no stamp on cancel, on a wholly failed full-text pass, or on an embedder failure (`:1449-1457`); full-text cursor withheld on any read failure (`:1462-1464`); checkpoint kept on cancel or embedder death (`:1471-1472`). Partial full-text failures in a *build* are reported in `fulltextReason` (`:1412-1424`) — the build lane handles what the update lane (finding 2) does not.
- **One build per process** is refused (`:1005`, `:1568`) and `reopenSearchIndex` refuses while building (`server.ts:181-188`).
- **Migration ladder is one transaction with the stamp inside it** (`sqlite-index.ts:680-705`); a transient failure leaves the file untouched and *refuses* rather than sidelining (`:604-648`), and the fault names no files so `repairSearchIndex` cannot delete it (`repair.ts:27-33`). A sideline renames, never deletes, sidecars first and database last (`:721-760`).
- **Repair deletes only on an explicit `action:"build"` and only the files the fault named** (`index-tool.ts:112-140`, `repair.ts:22-25`); `action:"update"` over a fault refuses (`:117-129`).
- **Durable pause** is honoured by `build`, `buildIncremental`, `updateIncremental` (`refuseIfPaused`, `:742-777`) and by the auto-build in `zotero_semantic_search` via `startIndexBuild:393-395`. (Finding 1 is the one way it is cleared without `resume`.)
- **JSON persistence is atomic** (temp + rename, `persistence.ts:23-33`), and an unparseable or wrong-shaped file becomes a fault rather than an empty index that would be written back (`:50-76`).
- **Attachment upload after item creation never retries elsewhere**, so no second empty attachment is created (`attach-file.ts:110-121`, `store.ts:147-163`); tested `attach-file.test.ts:131`.
- **Reads that back writes are pinned to one API per crawl** (`library-router.ts:21-39`, `build.ts:407-412`), so a build cannot splice two version sequences.

## What I could not check, and why

- **Zotero's server-side behaviour** for: 412 on a multi-object DELETE with a stale `If-Unmodified-Since-Version` (finding 4 — the public API contract says so, and Zoteus's own `postArray` and local client are written on that premise); the connector save target (finding 3 — Zotero's `server_connector.js` is not in this tree and I could not run a desktop app); cascade of sub-collections and client-side handling of a remote collection delete (finding 5). Each is a thirty-second live check; run finding 3's before filing it.
- **The local API's `?since=` and `?format=versions` fidelity** (`local-client.ts:308-330`): if Zotero 10 ignored `since`, an update would re-fetch everything (slow, not wrong); not verified.
- **Windows file semantics** around repair and sideline (the code comments handle them; not exercised).
- **Multi-tenant HTTP mode**: per-user index paths (`searchIndexPath`) were not audited for path sharing between users; outside the "user's own library" lens.
- **No tests were executed** (constraint: no `npm install`). The two positive-control sketches above are written against the existing fixtures in `tests/features/search-own-words-retry.test.ts` and `tests/api/web-client-writes.test.ts` and should drop in.
