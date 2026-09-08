# Quitting Claude Desktop after a headless build zeroes the index stamp, and the next `action:"update"` rebuilds from scratch

Read on `main` at `910310b3979aaad9d314087ffd043eaf59eb023a` (the v1.16.0 release commit). Source reading only: no `node_modules`, no test run, no live Zotero. I have traced the path but not observed the outcome, so please treat the scenario below as a reading of the code that wants one live confirmation.

### The outcome first

Build the index headlessly against the same `ZOTEUS_DATA_DIR` Claude Desktop uses, as the docs recommend. Hours later the build finishes: a complete full-text index, stamped with the library version. Then quit Claude Desktop. Its Zoteus process, which has held an idle index handle since before the build started, writes its own stale in-memory state over the row on the way out: `libraryVersion` back to `0`, `library` and `embedderId` to the empty string, `fulltextVersion` to `0`, `checkpoint` cleared, `paused` to `false`. Nothing errors and nothing logs.

The next session's `zotero_index action:"update"` then finds no version stamp, falls back to a full build, finds no checkpoint to resume from, and clears the store. The finished index is gone and is re-crawled and re-embedded from zero. This is the #59 outcome by a different route, and `status` says nothing about why.

### Mechanism

`writeMeta()` writes the whole row from the instance's fields, unconditionally, with no dirty tracking and no re-read of what is on disk ([sqlite-index.ts:1112-1128](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L1112-L1128)):

```ts
private flush(): void {
  if (!this.db) return;
  this.begin();
  this.writeMeta();
  this.commit();
}
```

[`:2053-2058`](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L2053-L2058). `flush()` runs from `save()` ([:2068-2073](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L2068-L2073)) and from `close()` ([:2075-2092](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L2075-L2092)), and `persistPaused()` writes the same whole row rather than the one flag ([:2060-2065](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L2060-L2065)). The server calls both on every shutdown, for every context ([server.ts:401-410](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/server.ts#L401-L410)). Meta is loaded once per handle, at `open()` and after a rollback ([`loadMeta()` at :1081](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L1081), called at `:458` and `:1403`); there is no periodic reload, so an idle handle's memory is whatever the file said when it opened.

The rest of the chain is then automatic. `updateBlocker` returns "this index carries no library version stamp" ([index-manager.ts:1528-1536](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1528-L1536)); `startIndexUpdate` falls through to `startIndexBuild` ([build.ts:480-489](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/build.ts#L480-L489)); `resumeFrom` finds no checkpoint ([index-manager.ts:953-962](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L953-L962)); `reset()` calls `clearStore()` ([:1071](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L1071) and [sqlite-index.ts:1219](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L1219)). The library guard does not stop it either: with `library` blanked, `loadMeta` reads it back as `undefined` ([sqlite-index.ts:1098](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L1098)) and `assertLibrary` returns early on an unheld library ([index-manager.ts:351-354](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L351-L354)).

The variants are the same write from a different angle: a durable `pause` set by one process is cleared when the other exits, and on the JSON backend the shutdown `save()` serialises the whole in-memory index over the file, rows included ([index-manager.ts:2707-2725](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/index-manager.ts#L2707-L2725)).

### Why this is not a misuse

The two-process setup is the recommended one. `docs/semantic-search.md:457-475` says building headlessly against the same `ZOTEUS_DATA_DIR` "is still the faster route on a large library, and Desktop reads the result either way", and gives the command. The tool description repeats it: "a user who wants the fastest possible first build can still run one headlessly against the same ZOTEUS_DATA_DIR and let Desktop read the result" ([index-tool.ts:20](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/index-tool.ts#L20)). The busy timeout exists on the same premise: "two Zoteus processes legitimately share a data dir" ([sqlite-index.ts:233-241](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/search/sqlite-index.ts#L233-L241)).

Sharing the passages is safe, because those writes are per-row and transactional. It is the index-level meta row that a second handle rewrites wholesale.

### Expected behaviour

A process that indexed nothing should commit nothing when it saves or exits. State written by another process must survive an idle handle's shutdown.

### Smallest fix shape

Two options, either sufficient. Keep the tuple `loadMeta()` read (`libraryVersion`, `fulltextVersion`, `checkpoint`, `paused`, `library`, `embedderId`) and have `flush()` and `persistPaused()` write only the fields this instance actually changed. Or, cheaper, guard the write with `UPDATE meta SET value = ? WHERE key = 'libraryVersion' AND value = <the value this handle loaded>`, and skip the row with a warning when it has moved underneath. For the JSON backend, refuse the shutdown `save()` when the file on disk carries a newer `libraryVersion` than the one loaded.

### Acceptance criteria

- Open handle A on an index file and leave it idle. Open handle B on the same file, run a build that stamps a library version, close B, then close A. A third handle opening the file reads B's stamp, not `0`, and `updateBlocker` returns `undefined`.
- The same for a durable `pause` set by B: A's exit does not clear it.
- The same on the JSON backend: A's shutdown does not replace B's rows.
- A process that did change the index still persists its changes on `save()` and `close()`, and an interrupted build still leaves a resumable checkpoint.

### What I did not check

Whether the desktop app's Zoteus process really is holding an open handle across the whole of a headless build depends on when Claude Desktop starts and stops it, which I could not observe. If it opens the index lazily and closes it between calls, the window is narrower than described, but not closed: any second process that has the file open when the first commits will overwrite the row on its own exit.

Related: #59 is the same end state (a partial index where a complete one had been) reached by a different route; #18 is why two processes share a data directory in the first place.
