<!-- last-reviewed: 2026-09-03 -->
# The Zotero #6012 inference boundary, and which way the bridge runs

Evidence for ticket 0496, and the record of the one outcome it owes ticket 0491.
Everything below is read from `zotero/zotero` at PR #6012's head
`19e79625b1c6fbbdd75367aa85b62d5a7080d7f6` through the forge API, with no local
clone. Every claim carries `path:line @ 19e7962`. Nothing here was executed
against a running build, and the two exit criteria that need one are reported as
NOT RUN rather than as negatives.

**Re-anchored 2026-09-03.** A first version of this report was written against
`77e2c4b` and asserted that the head had not moved. It had: #6012 force-pushed
while that pass was open. §1 records what moved, and every `path:line` below has
been re-read at the new head rather than carried across.

## 1. Currency of the head, and what moved

`GET repos/zotero/zotero/pulls/6012`, called 2026-09-03, returns `state: open`,
`merged: false`, `head: 19e79625b1c6fbbdd75367aa85b62d5a7080d7f6`,
`base: 08ed64f17f58fbd2a1d766af515dd2278f8cfb61`, `changed_files: 56`,
`commits: 69`, `updated_at: 2026-09-02T19:23:11Z`.

**The first version of this report was wrong about currency.** It read the head
at 2026-09-02T19:04Z, found `77e2c4b` with `updated_at: 2026-08-28T21:32:13Z`,
and concluded that "the head has not moved … the prior reading is the current
reading". Nineteen minutes later, at 19:23:11Z — eleven minutes after the pull
request carrying that sentence opened — #6012 force-pushed to `19e7962`. A
currency check is a reading of one instant, not a property of the branch, and
writing it as the latter is what made the claim false rather than merely stale.
It is restated here as what it is: read at 2026-09-03, and true of that call.

**What moved, measured rather than described.**

| | `77e2c4b` | `19e7962` |
|---|---|---|
| base | `ff93139` | `08ed64f` |
| changed files | 56 | 56, but not the same 56 |
| `ml.js` | 236 lines, sha256 `cbacb81f…` | 236 lines, sha256 `cbacb81f…` — **byte-identical** |
| `embeddings.js` | 3 810 lines | 3 637 lines |
| `Zotero.Embeddings.Reranking` | present, 290 lines, its own `createEngine` | **removed entirely** |
| `Zotero.ML.createEngine` call sites | 2 | **1** |
| `embeddings.*` prefs declared | 4 (`model`, `indexingPaused`, `indexFulltext`, `reranker`) | 3 — `reranker` gone with the module |
| chunking | in `embeddings.js`, tokenizing through `chrome://global/content/ml/transformers.js` | delegated to `Zotero.Utilities.Internal.Chunking`; that import survives only in `test/tests/embeddingsTest.js` |
| `numThreads` | `Zotero.ML.getOptimalConcurrency()` | `Math.max(1, Math.floor(Zotero.ML.getOptimalConcurrency() / 2))` |

`ml.js` being byte-identical is worth stating as a hash rather than a
description, because it is what carries §2.2 and §2.3 across the force-push
unchanged: `sha256 cbacb81f3fc61fab690d2d7de15c1bde1f22239512ad0f432e3940f34342f951`
at both heads.

**Nothing that decides the outcome moved.** The removals subtract capability
(one fewer engine, one fewer model, no cross-encoder); none of them adds a
route, a device selector, or a vector out. Every probe of §2.1 was re-run
against the new diff and the new file set, and every one of them returns what it
returned before, with its positive control still firing (§2.1).

## 2. Verified at source tonight

### 2.1 No changed file exposes an external route (confirmed, with a positive control)

`GET repos/zotero/zotero/pulls/6012/files --paginate` returns 56 filenames at
`19e7962`. None lies under `chrome/content/zotero/xpcom/server/`
(`grep -c 'xpcom/server/'` over the list: 0), and none is a connector or
protocol handler; the set is UI (`chrome/content/zotero/**`), xpcom modules
(`bestMatch.js`, `collectionTreeRow.js`, `embeddings.js`, `fulltext.js`,
`lexical.js`, `ml.js`, `notifier.js`, `sdt.js`, `utilities_internal.js`,
`zotero.mjs`, plus `data/item.js`, `data/search.js`,
`data/searchConditions.js`), styles, locale, prefs defaults, and nine test
files.

The unified diff (`Accept: application/vnd.github.v3.diff`, 16 582 lines at
`19e7962`) contains no occurrence of `Zotero.Server.Endpoints`, `Zotero.Server`,
or `endpoints[` — `grep -nE 'Zotero\.Server\.Endpoints|Zotero\.Server|endpoints\['`
over the diff exits 1 with no output.

That null is a finding only because the same pattern was run against a case known
to be positive: the same expression over
`chrome/content/zotero/xpcom/server/server_localAPI.js @19e7962` (2 717 lines)
matches **89** times, including the registration
`Zotero.Server.Endpoints["/api/"] = Zotero.Server.LocalAPI.Root;` at
`server_localAPI.js:811`. The probe can see endpoint registrations; the PR
contains none.

The files under `xpcom/server/` are untouched by the PR
(`saveSession.js`, `server.js`, `server_connector.js`,
`server_connectorIntegration.js`, `server_integration.js`, `server_localAPI.js`),
and `server_localAPI.js @19e7962` mentions neither `Zotero.ML` nor
`Zotero.Embeddings` nor embeddings at all — `grep -n 'Zotero.ML\|Zotero.Embeddings\|embedding'`
exits 1. (`server_localAPI.js:2070` matches `semantic` only inside the word
"semantics", in a comment about PATCH.)

One further probe, added on the re-anchor because the force-push changed the
file set: the string `endpoint`, case-folded, occurs **17 times in the whole
diff and all 17 are in `embeddings.js`** — no preferences XHTML, no locale file,
no test. That is §2.5's "undeclared and hidden" measured rather than asserted.

**No route returns a vector.** That is the sharp form of the first exit criterion,
and it holds.

### 2.2 The runtime is Gecko's, and nothing outside a Gecko process can reach it

`chrome/content/zotero/xpcom/ml.js @19e7962` (236 lines, added by this PR,
byte-identical to `77e2c4b`):

- `:69-70` — `ChromeUtils.importESModule("resource://gre/actors/MLEngineParent.sys.mjs")`
- `:92` — `Services.prefs.getBoolPref('browser.ml.enable', false)`
- `:95` — `Services.prefs.getBoolPref('browser.ml.checkForMemory', true)`
- `:98` — `Services.prefs.getIntPref('browser.ml.minimumPhysicalMemory', 3)`
- `:115-129` — `this.createEngine`, delegating to
  `ChromeUtils.importESModule("chrome://global/content/ml/EngineProcess.sys.mjs")` at `:124-125`
- `:208-209` — `ChromeUtils.importESModule("chrome://global/content/ml/ModelHub.sys.mjs")`
- `:231-232` — `ChromeUtils.importESModule("chrome://global/content/ml/EngineProcess.sys.mjs")`, then `EngineProcess.destroyMLEngine()` at `:234`

`chrome/content/zotero/xpcom/embeddings.js @19e7962`:

- `:666-679` — the single `Zotero.ML.createEngine({ …, backend: 'onnx-native', … })`
  call, with `numThreads` at `:678`. At `77e2c4b` there were two such calls
  (`:670-679` and `:3785-3794`); the second belonged to the reranker, which this
  head removes.
- The tokenizer import is **gone from production code**. At `77e2c4b`,
  `embeddings.js:1570-1571` imported
  `chrome://global/content/ml/transformers.js` to count tokens for chunking; at
  `19e7962` chunking delegates to `Zotero.Utilities.Internal.Chunking`
  (`embeddings.js:1517`, `:1546`, `:1567`, `:1599`) and estimates tokens from
  characters. The string `chrome://global/content/ml/transformers.js` survives in
  the diff exactly once, in `test/tests/embeddingsTest.js`.

The argument does not rest on that import and is unchanged without it:
`resource://gre` and `chrome://global` resolve only inside a Gecko process, and
`ChromeUtils` / `Services` are XPCOM globals, so a Node process cannot reach
`ml.js` at all — and `ml.js` is the whole engine path. Confirmed at this ref.

### 2.3 Nothing in Zotero selects an execution provider; the only knob it sets is a CPU thread count

Stated precisely, because an earlier draft of this section overstated it.

`Zotero.ML.createEngine` (`ml.js:115-129 @19e7962`) does not enumerate the
options it accepts. It takes an `options` object and forwards it **opaquely** to
Firefox's own `createEngine` — `return createEngine(options, onProgress);` at
`ml.js:129`, on the module imported from
`chrome://global/content/ml/EngineProcess.sys.mjs` at `:124-125`. So what that
runtime would do with a device or execution-provider key is not readable here,
and this report does not claim it.

What **is** established, by reading every caller: Zotero never sets one. The
single engine-creation site (`embeddings.js:666-679`) passes `engineId`,
`taskName`, `backend: 'onnx-native'`, `modelId`, `modelRevision`,
`modelHubRootUrl`, `modelHubUrlTemplate`, `dtype` and `numThreads` — and nothing
else. No `device`, no `executionProviders`, no `dml`/`cuda`/`webgpu` string
appears anywhere in `ml.js` or in `embeddings.js` at this ref. The one
performance argument Zotero supplies is `numThreads` (`embeddings.js:678`),
sourced from `Zotero.ML.getOptimalConcurrency()`, whose own doc-comment at
`ml.js:133` reads "Thread count the runtime recommends for **CPU inference** on
this machine" — and which this head now halves, with the comment "trade wall
time for heat and leave the rest of the machine to the user"
(`embeddings.js:675-678`).

So the claim carried into §6 is the narrow one: an embedder hosted inside
Zotero #6012 as it stands gets whatever Firefox's ML runtime does by default,
with a CPU thread count as its only tuning, and no way for a consumer to ask
for a device — because no code path exists that would carry the request. Whether
Firefox's runtime could serve a GPU if something set a key is outside what was
read.

This is the fact that decides the outcome; see §6.

### 2.4 One indirect route does reach inference — and it returns items, not vectors

This refines the prior note rather than contradicting it, and it is the part
that could not be seen from the changed-file set alone.

The PR adds a root-level `bestMatch` search condition
(`data/searchConditions.js`, diff hunk: `name: 'bestMatch'`, `operators: { contains: true }`,
plus an accept rule letting the *operator* carry a positive-integer top-K,
`data/searchConditions.js:274` and `:923-925 @19e7962`).
`data/search.js:837-845 @19e7962` then executes it inside `Zotero.Search.search()`:

```
let bestMatch = this.getBestMatchQuery();
if (ids && ids.length && bestMatch && bestMatch.topK) {
    let { scores } = await Zotero.BestMatch.scoreItemIDs(bestMatch.query, ids);
```

with `getBestMatchQuery()` at `data/search.js:864-882`. Upstream's own comment at
`data/search.js:832-836` names the consumer set explicitly: a top-K cutoff "makes
membership relevance-based … so the saved search returns the same set when used as
a source (scopes, counts, **the API**)."

And the API path exists and is unchanged by the PR:
`Zotero.Server.Endpoints["/api/users/:userID/searches/:searchKey/items"]` at
`server_localAPI.js:1218` (group twin at `:1219`), executing
`search.setScope(savedSearch, true)` (`:1114`) then `await search.search()`
(`:1154`). Saved searches are writable over the same local API — `Searches`
supports `POST` at `server_localAPI.js:1556-1567`, `Search` supports
`PUT`/`PATCH` at `:1581-1590` — behind the write-authorization handshake of
§3.1. All five re-read at `19e7962`; the file is untouched by the PR, but the
base moved with the force-push, so they were re-read rather than carried over.

So a supported external call **can already cause Zotero to embed a query string**:
POST a saved search carrying a root-level `bestMatch` condition whose operator is
K and whose value is the query, then GET that search's `/items`. What comes back
is a ranked, truncated set of item keys.

Three reasons this is not "consume an existing API" for our purposes, and all
three are the reasons it does not satisfy the exit criterion:

1. It returns **items, not embeddings**. No vector, no dimension, no model
   identity crosses the boundary.
2. It embeds **one query**. There is no passage route and no batching; the
   passage side of `embedPassages()` is never reachable inbound.
3. It **writes durable library state per query** — a saved-search object that
   syncs — so it is a side effect masquerading as a transport.

Not executed: this path is read from source. Confirming it end to end needs a
running #6012 build (§5).

### 2.5 The bridge upstream already built runs the other way

`embeddings.js:1027-1053 @19e7962`, inside `embedPassages()`:

```
// Passages can route to an external endpoint serving the same model;
// queries always embed locally. After the retries, only this batch
// falls back to the local engine -- the next one tries the endpoint
// again.
let endpoint = Zotero.Prefs.get('embeddings.endpoint');
```

and the transport at `embeddings.js:952-970`:

```
// POST { inputs: [...] } to the endpoint, which returns one vector per
// input, as a bare array or under an `embeddings` key. `truncate` tells
// a TEI server to cut inputs over the model's window to fit …
async function _embedViaEndpoint(endpoint, texts) {
    let xmlhttp = await Zotero.HTTP.request('POST', endpoint, {
        body: JSON.stringify({ inputs: texts, truncate: true }),
        headers: { 'Content-Type': 'application/json' },
        responseType: 'json',
        timeout: 120000
    });
    let vectors = xmlhttp.response?.embeddings ?? xmlhttp.response;
```

with `ENDPOINT_ATTEMPTS = 3` at `:944`, `ENDPOINT_RETRY_DELAY = 2000` ms at `:946`,
and `_normalize` applied to each returned `Float32Array` at `:969`.

That is the HuggingFace text-embeddings-inference (TEI) request shape. **Zotero
#6012 can already be pointed at an external embedding server for passages.**

Four properties of that hook, all read at this ref, and all load-bearing for §4:

- **It is undeclared and hidden.** `defaults/preferences/zotero.js @19e7962`
  declares three embedding prefs — `embeddings.model` (`:121`),
  `embeddings.indexingPaused` (`:123`), `embeddings.indexFulltext` (`:125`) — and
  **not** `embeddings.endpoint`. (`embeddings.reranker` was the fourth at
  `77e2c4b` and went with the reranker module.) The string `endpoint`, case-folded,
  occurs 17 times in the whole 16 582-line diff and all 17 are inside
  `embeddings.js`: no preferences XHTML, no `.ftl` locale entry, no test. It is a
  developer escape hatch, not a shipped feature.
- **Queries never leave.** Only `embedPassages()` consults it; `embedQuery()`
  (`:995-1019`) always goes to the local engine. Zotero therefore still loads its
  own model even when every passage is embedded elsewhere.
- **There is no handshake.** The request carries `inputs` and `truncate` and
  nothing else — no model name, no revision, no dimension, no pooling. Zotero's
  own vector identity is `getModelVersion()` = `name + '/' + revision`
  (`embeddings.js:208-210`), and none of it is sent or checked. The passage
  prefix is applied locally before the request (`:1028-1029`), so the server
  receives already-prefixed text and must not add its own.
- **Degradation is silent.** After three failed attempts the batch embeds locally
  — `return this.embedMany(texts);` at **`:1053`**, the statement the retry loop
  falls out of — and is stored under the same model version as the endpoint's
  vectors. A dimension or model mismatch is not detected at all; a transport
  failure is not surfaced to the user. (This citation was wrong even at the old
  head: the first version of this report gave `:1050-1052` twice, which is the
  retry-exhausted `Zotero.debug` line, not the fallback. The fallback was
  `:1054 @77e2c4b`.)

### 2.6 The portable half is already what `bench/` runs (constraint (ii), verified here)

Checked against this repo rather than repeated from the prior note:
`bench/recall_embed.mjs:62` resolves and imports `@huggingface/transformers`, and
`:156` records the run's `runtime` as `'@huggingface/transformers in Node (ONNX)'`.
`bench/registry.mjs:37-41` defaults every model resolution to `kind: 'onnx'`.
Both files are being edited by another lane, so the reading is pinned by content:
`sha256(bench/recall_embed.mjs) = 308bc55e429866b748087b948a9a427595dcfeaaf762b3596ee8a74f909e5e16`,
`sha256(bench/registry.mjs) = 9a68f67fd764b6da039644569c6ee22be695caa2304918d0fa52567e3bc1f59f`.

So transformers.js over onnxruntime — the portable half of what #6012 uses — is
already ours. A bridge into Zotero would buy model download, cache custody and
engine lifecycle. It would not buy inference.

## 3. The smallest upstream bridge, specified

Two bridges are possible and they are not symmetric. §3.1 is the one ticket 0496
asked for. §3.2 is the one that already half-exists and is worth an order of
magnitude more. Both are specified; §6 says which to file.

### 3.1 Inbound — a local-API embedding endpoint (the bridge 0496 asked for)

Reuses Zotero's existing local-API authorization rather than inventing one:
`POST /api/local/authorize` with `{ "appName": "…" }` prompts the user and
returns a 32-character key passed thereafter as `Zotero-API-Key`
(`server_localAPI.js:812-868`), with a rate limiter and an "Allow once" mode that
burns the key after first use. A read-only embedding endpoint should require the
same grant, because embedding arbitrary text on demand is a compute grant even
when it touches no library data.

**Route.** `POST /api/local/embeddings` — deliberately under `/api/local/`, beside
`authorize`, because it has no web-API analogue and must never be mistaken for a
data route.

**Request.**

```json
{
  "model": "<name>/<revision>",
  "role": "query" | "passage",
  "inputs": ["…", "…"],
  "truncate": true
}
```

- `model` is `Zotero.Embeddings.getModelVersion()`'s exact string
  (`embeddings.js:208-210 @19e7962`). It is a **precondition, not a hint**: a mismatch with
  the active model is `409`, never a silent re-embed under a different function.
  This is the field whose absence is §2.5's defect.
- `role` selects the prefix Zotero itself applies —
  `getQueryPrefix()` (`embeddings.js:247`) / `getPassagePrefix()` (`:256`). The server
  applies it; the client sends bare text. Role is mandatory with no default:
  the query/passage asymmetry is exactly the thing a caller gets silently wrong.
- `inputs` is a batch for `role: "passage"` and MUST be length 1 for
  `role: "query"`, mirroring `embedQuery()`'s single-string contract (`:995-1019`)
  and its in-flight cache (`:1003-1018`).
- `truncate` mirrors the local pipeline's own behaviour; `false` makes an
  over-window input a `422` instead.

**Response, `200`.**

```json
{
  "model": "<name>/<revision>",
  "dimension": 768,
  "normalized": true,
  "provider": { "backend": "onnx-native", "device": "cpu", "threads": 8 },
  "embeddings": [[…], […]]
}
```

- `model` echoed so a client can pin it without a second call.
- `dimension` explicit — the client must not infer it from array length.
- `normalized: true` states what `_normalize()` (defined at `embeddings.js:787`,
  applied at `:941` and `:969`) already does, so a client does not normalize twice.
- `provider` is what R30's disclosure clause needs from any facility that is not
  ours: backend, the device actually serving, thread count. Zotero sets no device
  at `19e7962` (§2.3), so the endpoint would have to report what the runtime
  actually used rather than echo a request — which is precisely how a consumer
  discovers it, and precisely what no code path exposes today.

**Availability.** `GET /api/local/embeddings` returns the same envelope without
`embeddings`, plus `"enabled": bool` and `"downloaded": bool` — the facts behind
`Zotero.Embeddings.isEnabled()` (`:179-181 @19e7962`), `isDownloaded()` (`:534`),
and `Zotero.ML.isAvailable()` (`ml.js:92-98`, i.e. `browser.ml.enable` and the
physical-memory gate). A caller must be able to ask "can you serve?" without
paying for an engine start.

**Errors** — a closed taxonomy, because "explicit degradation without silent
fallback" is a zoteus requirement (0491) that this endpoint has to make possible:

| Status | Condition |
|---|---|
| `401` | no or invalid `Zotero-API-Key` |
| `403` | user denied, or key exhausted (Allow-once) |
| `409` | `model` does not match the active model version |
| `422` | empty input after normalization; over-window input with `truncate: false`; `role: "query"` with more than one input |
| `429` | rate-limited, `Retry-After` in seconds |
| `503` | ML runtime unavailable (`ml.js:92-98`), model not downloaded, or indexing paused |
| `504` | engine start or run exceeded the server's own deadline |

No status ever means "here are vectors from something else". A `503` is the
correct answer to a failure; substituting a different producer is the defect §2.5
already has.

**Cancellation.** Client-side disconnect aborts the run, and the request accepts
an optional `deadlineMs` capped by the server. `Zotero.Embeddings` already carries
a `ScoringCancelledError` (`embeddings.js:631 @19e7962`) and `scoreItemIDs` takes
a `shouldCancel` callback (`:1209`), so the plumbing exists.

**What it must not do.** No route to the embedding database (`initDB`, `getChunks`,
`getMatchingChunks`, `scoreItemIDs`), no item text, no file paths, no model-file
bytes. Text in, vectors out, nothing retained beyond the request — the endpoint's
security argument is exactly that it holds no state a caller could enumerate.

### 3.2 Outbound — declare and harden `embeddings.endpoint`

Smaller, already 90% written, and the direction that survives R30.

1. **Declare the pref.** `pref("extensions.zotero.embeddings.endpoint", "");` in
   `defaults/preferences/zotero.js`, beside the four the PR already declares.
   An undeclared pref that changes where a user's library text is sent is the
   hazard, not the feature.
2. **Send identity.** Add `model` and `dimension` to the request body, and require
   them back in the response. This is the same precondition as §3.1's `409`,
   applied in the other direction.
3. **Verify the shape.** Reject a returned vector whose length is not the active
   model's dimension. Today only the *count* of vectors is checked
   (`embeddings.js:961-968 @19e7962`); a server answering with the right count of
   wrong-dimension vectors is accepted and stored.
4. **Kill the silent fallback, or record it.** Either surface the endpoint failure
   and pause indexing, or tag the affected chunks with their producer so a later
   audit can find the mixed batch. Today the fallback at `:1053` writes
   locally-produced vectors into a run the user believes was served remotely,
   under one undifferentiated model version.
5. **Say it is passages only.** The comment says it; nothing else does. A user
   pointing this at a remote server will reasonably expect queries to follow, and
   they never do.

Items 1–3 are small, mechanical, and independently useful to upstream. Item 4 is
an arbitration upstream owns.

## 4. What the endpoint hook means for ticket 0491

The recast 0491 asks which of six candidates owns one model on the machine, per
embedder generation. §2.5 changes the shape of that question: Zotero #6012 is not
only a candidate *provider*, it is a candidate *consumer*. A facility zoteus owns,
speaking the TEI shape #6012 already emits, would serve both — one model on the
machine, satisfying the ruling — while staying a native process that reaches CUDA,
satisfying R30.

The gain is partial and must not be overstated: Zotero still loads its own engine
for queries (`embedQuery()` never consults the pref), so during active semantic
searching two engines can be resident. The saving is on the indexing pass, which is
where the bulk of the work and the GPU advantage are.

## 5. NOT RUN — the two criteria that need a running build

Neither is a negative result. Neither was attempted. There is no #6012 build on
any machine reachable from this lane, and this lane was read-only by directive
(no `padme`, no index build).

**Exit criterion 3 — X8 against Zotero's native ONNX backend.**
NOT RUN. The one experiment: build #6012 at `19e7962`, select the registry entry
whose `modelId`/`dtype`/`pooling` match a `bench/models.json` record we already
embed, embed the X8 fidelity-probe corpus through `Zotero.Embeddings.embedPassages()`
with `embeddings.endpoint` unset, export the vectors, and score mean cosine against
the same corpus embedded in-process at the same rung — the X8 rule in SPEC.md §5.3,
≥ 0,999 keeps provider out of the embedder key. Note the trap this arm must avoid:
Zotero applies its own passage prefix (`embeddings.js:1028-1029`) and normalizes
(`:941`), so an arm that also applies our `input_template` would be measuring a
double prefix and not a provider difference.

Cheaper variant worth trying first, because it needs no vector export: with a
build in hand, set `embeddings.endpoint` at a local TEI-shaped server we control,
and compare the vectors Zotero *sends text to* against the vectors it produces
locally for the same batch. That measures the same provider question from the
outside, and it exercises §3.2 at the same time.

**Exit criterion 4 — cold start, steady RAM, cache custody, version skew, failure.**
NOT RUN. The one experiment: three arms on one machine — (a) #6012 in-process,
(b) zoteus in-process, (c) zoteus against a local endpoint — each measured for
time from cold launch to first vector, resident set at steady state with one and
with several P0 items in flight, on-disk model-cache location and what
uninstalling each component leaves behind, and the observed behaviour when the
model version changes underneath a populated index. Arm (a) is the blocked one:
it needs the build. Arms (b) and (c) are runnable today and would still leave the
comparison one-legged, which is why this is reported as not run rather than
partially run.

Two facts about arm (a) are however already readable at source and do not need the
build: the runtime is memory-gated at `browser.ml.minimumPhysicalMemory`, default
3 GiB (`ml.js:98 @19e7962`), and the model cache is the runtime's own `ModelHub`
(`ml.js:207-213`), i.e. Firefox's, not Zotero's and not ours — custody sits with a
third party in arm (a), which is a design fact rather than a measurement.

## 6. The outcome recorded for ticket 0491

**REJECT reuse, with the blocking fact.**

The blocking fact, stated at the width §2.3 supports: at `19e7962`, embedding
inference is created through Firefox's own ML engine process, and **nothing in
Zotero asks it for a device**. The single engine-creation site
(`embeddings.js:666-679`) passes `engineId`, `taskName`, `backend:
'onnx-native'`, `modelId`, `modelRevision`, two model-hub URLs, `dtype` and
`numThreads` — no `device`, no `executionProviders`, no `dml`/`cuda`/`webgpu`
anywhere in `ml.js` or `embeddings.js`. The one performance argument is
`numThreads` (`embeddings.js:678`), whose source is documented as the count "the
runtime recommends for CPU inference" (`ml.js:133`) and which this head halves.
`ml.js:129` forwards its `options` object opaquely, so what Firefox's runtime
would do with a device key is not readable here and is not claimed; what is
claimed is that no path exists through which a consumer could set one.

An embedder hosted there therefore cannot satisfy R30's first MUST clause, use a
usable GPU (DECISIONS.md, 2026-08-30) — not because the runtime is provably
CPU-only, but because reaching a GPU through it would require Zotero to grow an
option it does not have and to expose it over a route that does not exist.
Moving zoteus's inference into Zotero's process forfeits a ratified requirement;
it does not trade RAM for speed, it trades a promise for RAM.

Compounding it, and sufficient on its own: no supported external call returns a
vector (§2.1), and the one indirect route that does reach inference returns ranked
item keys at the cost of writing a synced saved search per query (§2.4).

Why reject rather than defer. Deferral is right when the blocking fact is expected
to move with the thing deferred to. This one is not, and the force-push between
this report's two passes is a small piece of evidence for it: 173 lines left
`embeddings.js`, an entire cross-encoder module went, the thread count was
halved, and none of it moved the blocking fact by a line. #6012 merging adds no
GPU path and no inbound vector route — the GPU path would have to arrive in Firefox's
ML runtime, on Mozilla's schedule, and R30's own ruling already anticipates that
as the sunset of our advantage rather than as a reason to wait for it. Deferring
pending #6012 would buy a re-read that changes nothing and would leave 0491's
ownership question hanging on it.

Why reject rather than "propose the bridge upstream". The inbound bridge of §3.1
is specifiable — it is specified above — but it is a large ask that, if granted in
full, would still deliver a CPU-only embedder. Filing it as the outcome would mean
asking a maintainer to build the thing we have just concluded we cannot use.

What this does not reject. The direction inverts (§4): the outbound hook of §2.5
means the facility can be ours and still serve Zotero. §3.2's items 1–3 are a
small, self-contained, genuinely useful upstream filing, and they belong to the
upstream queue under `GOVERNANCE.md`'s bounds and `SYNC.md`'s live account — not
to this outcome, and not to this lane tonight.

## 7. For the author

One question this pass cannot settle: §3.2 is an upstream filing against a hidden
pref that upstream has not shipped, described in a comment as serving "an external
endpoint serving the same model". Filing items 1–3 discloses that we intend to be
that endpoint. Whether that is the disclosure we want to make, and when relative to
the rest of the upstream queue, is a governance call, not a technical one.
