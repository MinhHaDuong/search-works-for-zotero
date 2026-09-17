# Upstream review before re-baselining to v1.20.2

*Evidence, not authority. Read 2026-09-17 from the bare mirror `upstream.git/`
(`make upstream-catchup`). Where this report touches design, `SPEC.md` remains
the record. This is the delta review `make upstream-rebaseline` asks for before
the `UPSTREAM` block moves; it is not the requirement-row re-read, which the
recipe files as `verification/UPSTREAM-<version>-REREAD.md` and which remains
to be done (see § 6).*

## Subject and method

Base `446766320867f1a0a2c6c55ab63b3df734a05c69` (v1.16.0 + one README commit,
2026-09-08). Head `c386e835a2ef90b539b611168130c8540cd55fe5`, which is the
v1.20.2 tag itself (2026-09-16). Six releases (v1.17.0 `356cfc7`, v1.18.0
`87122d4`, v1.19.0 `9c0e39c`, v1.20.0 `3bf2637`, v1.20.1 `692df02`, v1.20.2
`c386e83`), 73 commits, 8 merges. A `1.18.1` heading exists in the CHANGELOG
with no matching tag.

`python3 bench/upstream_catchup.py` says **TOUCHED**: 53 watched files,
+5406/−611; 117 files outside the watched surface, +10572/−292, not read here
except `CHANGELOG.md` and `package.json`'s pin. The watched surface is
`src/features/`, `src/tools/`, `src/config.ts`, `src/router/`,
`src/lib/update-check.ts`; the last has no hunk in this span.

Method: the full 8139-line watched diff was read by one reader (Opus), the
ticket corpus by a second (Sonnet), and the item-to-ticket mapping was
re-verified against both the diff and the ticket text by a third, decorrelated
reader (Sonnet). Every claim below that cites a function or a `watched.diff`
line range was made by a reader who opened the hunk. No upstream code was
built or run; nothing here is promoted to `measured`.

## 1. The 53 watched files

`git diff --stat` prints one number per file, insertions plus deletions;
`+ins/−del` below is the split. Impact key: **NONE** no local consequence;
**DOC** a README row or SPEC citation must be re-read; **BENCH** a bench
driver, fixture or pending local patch is affected; **TICKET** a concern a
local ticket holds.

| path | +ins/−del | what changed | impact |
|---|---|---|---|
| `src/config.ts` | +30/−0 | Three env vars: `ZOTEUS_ZOTERO_DEADLINE_MS` (desktop-only per-request budget, `min(5000).max(600000).optional()`, unset ⇒ fetcher's 25 s stands, #78), `ZOTEUS_OPENALEX_API_KEY` (#76), `ZOTEUS_CONFIRM_BULK_WRITES` (`default(0)` = gate off, #71). No existing default moves. | DOC (R7/R8/R10/R15 rows; new security default) |
| `src/features/attachments/resolve.ts` | +158/−0 | New. `resolveAttachment`, `detectKind`, `fetchAttachmentBytes`, `SOURCE_LABEL` lifted verbatim out of `get-fulltext.ts` so `zotero_get_fulltext` and `zotero_pdf_images` mean the same file. | NONE |
| `src/features/fulltext/pdf-images.ts` | +913/−0 | New. `renderPdfPages` (pages → JPEG/PNG, DPI and edge caps) and `extractPdfImages` (walks `getOperatorList`, tracks the CTM, dedupes by pixel sha1); a `serialized()` one-job gate and a canvas pool because `@napi-rs/canvas` does not return memory. | NONE for search |
| `src/features/fulltext/pdf-locate.ts` | +49/−6 | New `pageHeights()` (viewports only); the dynamic pdfjs import goes through `loadPdfjs()`. | NONE |
| `src/features/fulltext/pdf-pages.ts` | +24/−13 | Both extractors go through `loadPdfjs()`; `parsePageRange` exported (accepts `-` and `–`), moved from `get-fulltext.ts`. | NONE |
| `src/features/fulltext/pdfjs-loader.ts` | +135/−0 | New single import site. `loadPdfjs()` deletes `process.type` for the import and restores it (`pdfjs` throws `DOMMatrix is not defined` under Electron's `process.type === "utility"`); `pdfjsAssetUrls()`, `loadCanvas()` via pdfjs's own `createRequire`. Commit `910d211`. | TICKET (the #62 failure class; 0613's install half) |
| `src/features/resolve/resolve.ts` | +33/−2 | `SCHOLAR_ITEM_TYPES` table; fallback `'generic'` → `'document'` (`generic` is not a Zotero item type, #77). | NONE |
| `src/features/scholar/crossref.ts` | +23/−1 | `isSingleWork()` rejects the list endpoint a bare `/works/` returns for an empty DOI. | NONE |
| `src/features/scholar/graph.ts` | +31/−14 | Lists return `ScholarList {works, total}`; options object carries `openalexApiKey`. | NONE |
| `src/features/scholar/openalex.ts` | +56/−16 | `mailtoParam()` deleted (OpenAlex ignores it); `User-Agent` and `Authorization: Bearer` headers; `OpenAlexError` with `status`. | NONE |
| `src/features/search/backend.ts` | +56/−1 | `SearchIndexStatus.fulltextPartial?`; `IncrementalBuildOptions.fulltextMapIncomplete?()` and `fulltextMapComplete?()` (explicitly not each other's negation); `FulltextCatchUp.incomplete?`; `IndexSnapshot.fulltextPartial?`/`fulltextRecoveryAttempts?`. | BENCH (acceptance and coverage drivers read `SearchIndexStatus`; `fulltextReason` no longer means "produced nothing") |
| `src/features/search/build.ts` | +27/−2 | `fulltextNotice` branches on `fulltextPassages > 0`; `crawlOptions` gains the two map closures and folds `src.incomplete` into `fulltextCatchUp`. | DOC (SPEC cites `build.ts:631-633`, `:617-620`; moved) |
| `src/features/search/corruption.ts` | +3/−0 | `CorruptSearchIndex.fulltextPassageIds()` returns `[]` to satisfy the new abstract. | NONE |
| `src/features/search/fulltext-source.ts` | +213/−53 | Attachment map rebuilt (#78): deep-offset paging (`ATTACHMENT_PAGE_SIZE`, `MAX_ATTACHMENT_PAGES`) deleted; keyed `itemKey=` batches of 50 with 3 attempts, 3 sweeps, `absorb()` guards double counting; `incomplete?` on the source; `textFor` **throws** on a read failure and on a miss under an incomplete map (was `continue`, #67). | BENCH + TICKET (`bench/fulltext_quality_census.py`, `fulltext_sequence.py`; R1/R17 coverage honesty; the ≈180-keyed-requests-vs-90-pages trade is measurable here) |
| `src/features/search/index-manager.ts` | +648/−27 | `FULLTEXT_RECOVERY_ATTEMPTS = 3`; persisted `fulltextPartial`/`fulltextRecoveryAttempts`; `status()` emits `fulltextPartial` and `partialCoverageNotice()`; build cursor guard adds `&& !fulltextMapIncomplete`; update path gains `fulltextGap`/`fulltextStale`/`fulltextFailed`, `fulltextRecords()` + `restorePassages()` (a failed read keeps the item's body text, #67), `libraryVersion` stamp withheld on `fulltextGap`; `fulltextCatchUp` rewritten to ask from 0 whenever `fulltextPartial` stands; `updateBlocker` calls `refreshFromStore()` first (#68); `MemorySearchIndex.save()` skips the write when the signature is unchanged and the file stamp moved (#68). | BENCH + TICKET (R13 concurrency 0650–0652; R1/R17; SPEC cites `index-manager.ts:672`, `:881`; moved) |
| `src/features/search/sqlite-index.ts` | +169/−20 | See § 3. No DDL change. | DOC + BENCH (SPEC cites `:499`, `:585`; `bench/index_schema.mjs` pin holds) |
| `src/router/library-router.ts` | +274/−10 | Every routed read goes through `await route()`, which overlays a pending-cloud-write override on `servesLocally`; `noteCloudWrite`, `desktopHasCaughtUp` (#80, #81); `topLevelItemsOfType` (#79); four newly routed reads `listTags`, `versions`, `deleted`, `listSearches` (#64 precedent, #74). `servesLocally` ignores the override so a crawl never flips backend. | DOC + TICKET (SPEC cites `library-router.ts:72`; the routed-read set SPEC §6 enumerates grew by four; #75 fix consumes `exportItems`) |
| `src/router/pending-writes.ts` | +66/−0 | New. `PendingCloudWrites` keeps the latest write per library slot; `setBaseline`/`clear` compare object identity (#80). | NONE |
| `src/tools/annotate.ts` | +249/−42 | A given-but-broken `position` is refused with a per-field message instead of falling through to text anchoring; unknown keys refused naming the twin; PDF opened at most once per call; caller rects get a real `annotationSortIndex` via `pageHeights()`. `outputSchema`. | NONE |
| `src/tools/attach-file.ts` | +15/−2 | Shared `libraryArgs`; `outputSchema`. | NONE |
| `src/tools/attachment.ts` | +23/−9 | `libraryArgs`, `optionalLibrary`; descriptions; `outputSchema`. | NONE |
| `src/tools/bibliography.ts` | +56/−7 | `entryCount` counted from the XHTML replaces the echoed request count; shortfall noted; empty render says so. | NONE |
| `src/tools/collection-guard.ts` | +53/−0 | New. `refuseUnknownCollection()` because the desktop answers `/collections/<unknown>/items` with the whole library. | NONE |
| `src/tools/common-args.ts` | +29/−0 | New. One described `libraryArgs` pair replacing ~25 undescribed copies (#74). | NONE |
| `src/tools/common-output.ts` | +106/−0 | New. Output-schema blocks incl. `provenance` (the library-origin marker, #71) and `indexStatus`. | DOC (`indexStatus` is now a declared description of the status surface SPEC reasons about) |
| `src/tools/create-items.ts` | +20/−3 | `libraryArgs`; group-write instructions; `outputSchema`. | NONE |
| `src/tools/delete-items.ts` | +10/−2 | `libraryArgs`; `outputSchema`. | NONE |
| `src/tools/export.ts` | +135/−49 | Stock exports go `ctx.web.exportItems` → `ctx.router.exportItems` (#75); named keys that render nothing are an error; other empty selections return `empty: true`; unknown-collection guard. | TICKET (closes #75, filed by 0761) |
| `src/tools/format-bibliography.ts` | +12/−5 | `libraryArgs`, `optionalLibrary`; `outputSchema`. | NONE |
| `src/tools/fulltext.ts` | +58/−14 | `action:"get"` carries `item_key` on both branches (the one handler change forced by output-schema validation); keyless personal-library `set` explanation. | NONE |
| `src/tools/get-fulltext.ts` | +83/−149 | Shrinks: shared helpers moved out; `ok` → `okLibraryContent`; degrade notice distinguishes "read, not parsed" from "bytes unreadable". | NONE |
| `src/tools/get-item.ts` | +35/−8 | `include` always contains `data` (Zotero replaces the representation otherwise); `okLibraryContent`. | NONE |
| `src/tools/groups.ts` | +119/−5 | Keyless install lists desktop-held groups (`locallyHeldGroups`); merged rows carry `source`. | DOC (group reachability without a cloud key) |
| `src/tools/import.ts` | +72/−14 | Empty identifier/url refused up front; translation-server guard narrowed to `by_url`; `writeResult`. | NONE |
| `src/tools/index-tool.ts` | +20/−8 | `outputSchema` from `indexStatus`; description gains a `fulltextPartial` paragraph. | DOC (user-facing statement of coverage honesty) |
| `src/tools/index.ts` | +4/−2 | `AnyToolDefinition[]`; `pdfImages` registered. | NONE |
| `src/tools/list-collections.ts` | +12/−6 | `libraryArgs`; `outputSchema`. | NONE |
| `src/tools/list-tags.ts` | +22/−8 | `ctx.web.listTags` → `ctx.router.listTags` (keyless desktop could not list tags). | NONE |
| `src/tools/manage-collections.ts` | +35/−6 | `list` reads the library given (#74); `remove_items` behind `requireBulkConfirm` (#71); `confirm` arg. | NONE |
| `src/tools/manage-tags.ts` | +39/−8 | `list` via `resolveLibrary` + router; `add`/`remove` behind `requireBulkConfirm`. | NONE |
| `src/tools/pdf-images.ts` | +545/−0 | New tool `zotero_pdf_images` (`mode: "pages"|"figures"`; caps 4/8 pages, 16/40 images, 5 MiB inline; `save` refused for a remote caller). Tool count 30 → 31. | DOC (any row enumerating the tool surface) |
| `src/tools/saved-searches.ts` | +41/−7 | `list` via router with `resolveLibrary` (last direct `ctx.web` read). | NONE |
| `src/tools/schema.ts` | +9/−0 | `outputSchema`. | NONE |
| `src/tools/scholar.ts` | +106/−31 | Empty DOI refused; `OpenAlexError` mapped (404 vs provider failure); `total`/`truncated` (#76). | NONE |
| `src/tools/search-items.ts` | +65/−13 | Unknown-collection guard; `okLibraryContent`; all args described; `outputSchema`. | NONE |
| `src/tools/search-tools.ts` | +16/−0 | `outputSchema`. | NONE |
| `src/tools/semantic-search.ts` | +77/−10 | `mode:"semantic"` refuses unless `hasVectors && embedderId !== undefined` (#7, this repo's PR #73); `noVectors`/`noEmbedder` causes; `okLibraryContent`. The `auto` branch is untouched. | BENCH (refusal vs empty answer is what the fixture fail-controls score) |
| `src/tools/styles.ts` | +13/−1 | Description; `outputSchema`. | NONE |
| `src/tools/sync.ts` | +97/−15 | `versions`/`deleted` via router with the backend pinned once per call (the two APIs number versions independently); per-type `unavailable[]`; all-unavailable is an error. | DOC (SPEC's version-sequence discussion) |
| `src/tools/tag-audit.ts` | +202/−15 | `listAllTags` via router; strict-object schemas that refuse an unknown key and name its twin; unknown scope collection refused before listing. | NONE |
| `src/tools/trash-items.ts` | +27/−4 | `requireBulkConfirm` on the trash direction; `writeResult`. | NONE |
| `src/tools/update-item.ts` | +26/−2 | `libraryArgs`; `outputSchema`. | NONE |
| `src/tools/whoami.ts` | +67/−1 | Payload gains `version` and `attribution`; summary ends with the CPAL line (#70). | DOC (`zotero_whoami` is now a version oracle a local probe can read directly) |

Cross-cutting: every tool gained per-argument descriptions and an
`outputSchema` (`00bb05e`, v1.20.0); that is what exposed #83. Upstream also
**withdrew** the `zotero/zotero#6012 modelCalibration.meanVector` citation from
the `MEAN_SAMPLE` comment in `sqlite-index.ts` as unverified (`3a1e942`);
`SPEC.md:2128` still argues from "#6012-style library calibration (mean
centering …)" and now has no upstream text behind it.

## 2. The 23 named items against the local tickets

Item state on the forge is deliberately not mirrored here (see
`bench/upstream_catchup.py`'s docstring). "Resolves" means the diff builds
what the local ticket asked for; "no-touch" means no open ticket's concern
moves. Each verdict was checked against the hunk and the ticket text by the
decorrelated reader.

| item | what the span does (evidence) | local ticket(s) | verdict |
|---|---|---|---|
| #7 | `987d072` + `1278091`: semantic refusal tests both ends (`semantic-search.ts`, `watched.diff` 7413–7470). These are **this repo's PR #73**, rebased in under new SHAs with identical code (author Minh Ha-Duong; only an em-dash edit in a comment and changelog prose differ; `refs/pull/73/head` is therefore not an ancestor of the tip). | 0739 (closed) filed PR #73. 0611 (open, silent `auto` fallback) | Resolves 0739's PR item. **No-touch** on 0611: the guard fires only on explicit `mode:"semantic"`; the `auto` branch is unchanged and 0611's criteria (assertion seen red, clause in SPEC) are untouched. |
| #26 | Not in any commit subject; cited in comments as the "two independent sequences" precedent. The cursor is withheld one notch more strictly under #78. | 0024 (closed) | No-touch. |
| #30 | `050c320`: `deleteFulltextCodes`/`deleteOwnWordsCodes` + `invalidateCodes()` in `clearFulltext`/`clearOwnWords` (`watched.diff` 3300–3318, 3493–3520). **This repo's PR #72**, same rebase pattern as #73. | 0739 (closed) filed PR #72; 0070 (closed) | Resolves 0739's PR item. No-touch on open tickets (0734 cites `vector_codes` only as a side-table precedent). |
| #33 | Not in the diff; named in changelog prose for #30 only. | 0022 (closed) | No-touch. |
| #39 | Not in the diff; named in changelog prose for #67 as the saturation condition. | 0019, 0480, 0483 (open) cite it as context | No-touch for #39 itself; the behaviour under saturation moves via #67/#78, below. |
| #58 | No commit; two unchanged context comments. | 0735 (closed) names PR #58 | No-touch. |
| #63 | No commit; one context comment. The diff adds `fulltextGap` beside `ownWordsGap` and the stamp guard becomes `&& !ownWordsGap && !fulltextGap` (`watched.diff` 2672). | 0736 (closed) filed it; 0613 cites it as a pattern | No-touch. |
| #64 | `8503a05`, `a71da13`, `9776e55`: four new routed reads, consumers moved off `ctx.web` (`library-router.ts` 3760–3895; `list-tags`, `manage-tags`, `saved-searches`, `sync`, `tag-audit`). | 0736, 0761 (closed) | No-touch on open tickets. |
| #67 | `d916aa1`: `textFor` throws instead of `continue`; `fulltextRecords`/`restorePassages` keep the item's body text; `fulltextGap` withholds the item stamp (`watched.diff` 2118–2130, 2333–2350, 3000–3040, 3134–3170). Changelog and diff agree. | 0739 (closed) filed it. 0019, 0480 (open) | **Resolves the filed issue.** No-touch on 0019: its ask is a *terminal, never-retried* no-text state with a D1 denominator; the diff does the opposite (withhold the stamp so the next update retries), and no per-item state table exists. No-touch on 0480 (quality staleness is orthogonal). |
| #68 | `484257c`: `metaRow()`, merging `writeMeta()`, `readDataVersion()` (`PRAGMA data_version`), `refreshFromStore()` with a four-way bail, `MemorySearchIndex.save()` skip (`watched.diff` 3040–3100, 3350–3500). | 0739 (closed) filed it. 0035, 0614 (open) | **Resolves the filed issue.** Partial on 0035: the stamp-clobber symptom is fixed, the four-role topology question its exit criteria are about is not. Partial-but-inert on 0614: repairs R13's hazard but moves none of its checkboxes, which are blocked on absent counters. |
| #69 | `b899aa5`, `package.json` only (outside the watched surface): `pdfjs-dist` pinned exactly `5.6.205`. | 0739 (closed) filed it. 0560 (open) | **Resolves the filed issue.** Partial on 0560: its criterion reads "pdf.js vendored at a pinned version"; pinned yes, vendored no. |
| #70 | `408512e` (notices, bundle, image — outside watched) + `whoami.ts` attribution line (`watched.diff` 8105–8130). | 0739 (closed) | Resolves the filed issue. No open ticket. |
| #71 | `1233cb0`: `ZOTEUS_CONFIRM_BULK_WRITES` (`config.ts` 34–44), `requireBulkConfirm` at three call sites, `provenance` marker + `okLibraryContent` swaps; threat model and `requireBulkConfirm` itself live outside the watched surface. The string `#71` appears nowhere in the diff. | 0739 (closed) | Resolves the filed issue. No open ticket on untrusted library content. |
| #74 | `0d79c16`: `common-args.ts` refuses `library_type:"group"` alone; `list` sub-actions read the library they were given. The "file's time budget" bullet is outside the watched surface. | none | No-touch. |
| #75 | `9f32cc4`: `stockExport(format)` over `ctx.router.exportItems` (`export.ts`, `watched.diff` 5085–5185). | 0761 (closed) filed it | **Resolves the filed issue.** `SYNC.md:7–10` still says "Open at filing; no PR submitted". |
| #76 | `efd3e85`: OpenAlex key header, list totals, `mailto` dropped. | none | No-touch. |
| #77 | `c3f9ae7`: `SCHOLAR_ITEM_TYPES`, `'generic'` → `'document'`. | none | No-touch. |
| #78 | `8e8e700`, `0c4ba3b`, `2bddf4c`: keyed attachment map with retry, cursor never stamped over an incomplete map, `fulltextPartial`, bounded recovery (`fulltext-source.ts` 1929–2284, `backend.ts` 1751–1846, `build.ts` 1871–1912, `index-manager.ts` 2285–3240, `config.ts` 8–58). | none by number. 0019, 0480, 0757, 0033, 0613, 0614 checked | No-touch on every open ticket's stated criteria (0019 as under #67; 0757 is a measurement ticket whose log already noted the mechanism at `357ad1f`). It does change what R1/R17 rows can claim. |
| #79 | `07f4a10`: `topLevelItemsOfType` intersects two key listings and fetches by key with `top:true` (`library-router.ts` 3706–3790). | 0441 (open) checked | No-touch: 0441 is about facet columns in the search index, a different layer. |
| #80 | `15f06cc`: `PendingCloudWrites.setBaseline`/`clear` compare object identity. | none (the "#80"/"#81" hits in closed 0422/0220 are this repo's own PR numbers) | No-touch. |
| #81 | `973043e`: `desktopHasCaughtUp` keeps an unknown baseline on the cloud. | none | No-touch. |
| #82 | Merge of `integration/issues-78-79`; no code of its own. | none | No-touch. |
| #83 | `c386e83`, `src/registry/registry.ts` (outside watched): tool schemas declare no JSON Schema dialect, because the new `outputSchema` was refused by 2020-12 clients. | none; `bench/` MCP drivers read `structuredContent` and never a `$schema` | No-touch. |

Not in the named list but in the span: `910d211` (`pdfjs-loader.ts`) is the
fix for the failure signature of #62, filed from here and closed at v1.16.0;
0613's install half rests on it.

## 3. Index schema

Read at both SHAs by `bench/upstream_catchup.schema_at()` and by hand in
`src/features/search/sqlite-index.ts`:

- `const SCHEMA_VERSION = 2;` at line 63 at both `4467663` and `c386e83`.
- `passages` DDL identical at both:
  `pid INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, item_key TEXT NOT NULL,
  title TEXT NOT NULL, text TEXT NOT NULL, source TEXT, vector BLOB`
  (head lines 958–966). `meta`, `items`, `vector_codes`, `passages_fts`,
  `accent_variants` unchanged; there is no `createSchema` hunk in the diff.
- `SCHEMA_MIGRATIONS` still has its one rung, `to: 2`.
- The only storage-format change is two new `meta` key/value rows,
  `fulltextPartial` and `fulltextRecoveryAttempts`, which need no bump.
- `bench/index_schema.mjs:85` (`SCHEMA_VERSION = 2`) and `UPSTREAM`'s
  `UPSTREAM_INDEX_SCHEMA_VERSION=2` therefore both still hold.

`make schema-gate`, run in this worktree with `RTK_DISABLED=1`, exit **0**:

```
SCHEMA_LEG_STRICT=1 python3 -m pytest tests/test_index_schema_fixtures.py -q \
  -k the_declaration_matches_upstreams_own_constant
.                                                                        [100%]
1 passed, 25 deselected in 0.11s
```

Read that for what it checks: the leg compares the declaration against
upstream's constant **at `UPSTREAM_REVIEWED_SHA`**, i.e. still `4467663`. The
same comparison at `c386e83` is the `schema_at` reading above; both give 2.

## 4. The UPSTREAM block `--rebaseline` prints

```
UPSTREAM_REVIEWED_SHA=c386e835a2ef90b539b611168130c8540cd55fe5
UPSTREAM_REVIEWED_VERSION=v1.20.2
UPSTREAM_REVIEWED_DATE=2026-09-16
UPSTREAM_INDEX_SCHEMA_VERSION=2
```

The recipe also lists what the re-baseline must touch: `README.md` rows R1,
R3, R4, R5, R7, R8, R10, R12, R15, R16, R17, R18, R19, R22, R23, R24, R32,
R33, R35; `SPEC.md` where 5/18 citations are unchanged and seven drifted
(`index-manager.ts:672`, `:881`; `sqlite-index.ts:499`, `:585`;
`build.ts:631-633`, `:617-620`; `library-router.ts:72`; six Zotero-core
citations unresolvable from the mirror); `SYNC.md`; a new `DECISIONS.md`
entry; `verification/UPSTREAM-1.20.2-REREAD.md`; `bench/results/smoke-1.20.2/`;
and a log entry on 29 open tickets naming a changed file (0019, 0025, 0029,
0033, 0034, 0035, 0441, 0480, 0557, 0558, 0560, 0561, 0566, 0590, 0595, 0606,
0607, 0613, 0614, 0632, 0642, 0643, 0677, 0722, 0732, 0734, 0754, 0757).

## 5. Tickets to close or re-triage because of this move

Nothing here closes outright: every item this span resolves was filed by a
ticket that already closed on the filing. What moves is the state those
closed tickets and `SYNC.md` recorded, and the premise of a few open ones.

| ticket | state | evidence | action |
|---|---|---|---|
| 0739 (closed) | its five issues #67–#71 are built and its two PRs #72/#73 are in `main` as `050c320` and `987d072`/`1278091`, code identical | § 2 rows #67–#71, #7, #30; patch comparison in § 2 | Record in `SYNC.md`, which today names none of #67–#73 (grep finds only #75). |
| 0761 (closed) | #75 built by `9f32cc4` | `export.ts` hunk | Correct `SYNC.md:7–10` ("Open at filing; no PR submitted"). |
| 0560 (open) | criterion "pdf.js vendored at a pinned version" half met: `pdfjs-dist` pinned exactly `5.6.205` (#69), one import site (`pdfjs-loader.ts`) | `b899aa5`; `watched.diff` `pdfjs-loader.ts` | Re-triage: decide whether a pin satisfies the criterion or whether vendoring was the point. |
| 0035 (open) | the stamp-clobber half of "two processes on one data dir" is built (#68) | `sqlite-index.ts` `writeMeta`/`refreshFromStore` | Re-triage: narrow the issue-to-file to the topology question, or record #68 as the maintainer's answer. |
| 0614 (open) | R13's hazard repaired upstream (#68); its checkboxes still blocked on counters | § 2 row #68 | Log entry only. |
| 0019 (open) | upstream chose retry-with-withheld-stamp plus a `fulltextPartial` flag, the opposite of a terminal no-text state | § 2 row #67 | Re-argue the ask against the new mechanism before filing; the reserve-item framing at v1.12.0 is stale. |
| 0613 (open) | the #62 failure class has a fix (`pdfjs-loader.ts`); the native macOS/Windows `page_range` check SYNC records as outstanding is still unproducible here | `910d211` | Log entry; the outstanding check does not move. |
| 0754 (open) | upstream withdrew its `#6012 meanVector` citation (`3a1e942`); `SPEC.md:2128` still argues from it | § 1 cross-cutting note | Re-triage the parity matrix row that leans on it. |
| 0734 (open) | its three anchors (`chunker.ts:8`, `backend.ts:61-68`, `ChunkRecord`) were re-pinned at v1.15.0; `backend.ts` changed in this span | § 1 `backend.ts` row | Re-pin the anchors at `c386e83`. |
| 0757 (open) | its log already records TOUCHED at `357ad1f`; the span now has a SHA | § 2 row #78 | Log entry with the reviewed SHA. |
| 0611 (open) | unchanged: the semantic guard moved, the `auto` fallback did not | § 2 row #7 | None beyond the recipe's log entry. |

## 6. Residual

- The requirement rows were not re-read here; that is the `-REREAD` file the
  recipe demands and `check_progress` gates on.
- No live run: nothing was built from the mirror, so no row can be promoted
  and the four smoke-backed rows fall to `code` at the move unless
  `bench/results/smoke-1.20.2/` is produced first.
- Item open/closed state on the forge was not queried, by the catch-up
  script's own rule.
