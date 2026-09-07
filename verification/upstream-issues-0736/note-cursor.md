Reproduced on `main` at `5a81cee88be6d979e9ca1e99e897b6b6df25beef`, through `startIndexBuild()` and `startIndexUpdate()`, on both the memory and SQLite backends with a deterministic library transport.

### Minimal reproduction

1. Build an index with own words enabled and a child note already indexed.
2. Edit that note and add another child note without changing the parent item. The library version advances.
3. Let the next update's top-level item delta and live-key census succeed, but make its `itemVersions(itemType="note || annotation")` request fail once.
4. Restore that request and run `action:"update"` again, without further library changes.

### Actual behavior

The first update reports `done` and advances `libraryVersion` despite failing to read child versions. On the successful retry, the edited note and new note are no longer newer than that stamp. The old note text remains searchable, while the replacement text and added note are missing. A rebuild or a later change that forces a re-read can heal the gap; simply retrying the failed update does not.

The mechanism is in [src/features/search/index-manager.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/features/search/index-manager.ts): `ownWordsCatchUp()` catches the child census failure and returns normally; `updateIncremental()` then stamps the newer library version. The subsequent child comparisons use that stamp (`version > since`), including for unheld children when some own words are already indexed.

### Expected behavior

A transient failure must leave the missed child changes eligible for the next successful update. The status should distinguish incomplete own-words catch-up from a fully current index.

### Smallest fix shape

Do not advance the shared cursor past failed own-words work. Alternatively, persist a separate acknowledged own-words cursor or explicit retry work, only advancing it after successful attribution and text indexing. Apply the same rule to child-body/attribution failures and incomplete censuses rather than treating a degraded empty source as success.

### Acceptance criteria

- Inject the one-shot census failure above on both backends; the next successful update finds both the edit and the addition without rebuilding.
- Cover failed note-body/parent-attribution reads as well as the initial versions request.
- Preserve prior indexed text while its replacement cannot be read.
- A later successful catch-up removes stale text, and an idle update remains idle.

Related: #33/#36 introduced own-words indexing; this is its transient-failure retry path. It is distinct from #26's independent full-text version sequence.
