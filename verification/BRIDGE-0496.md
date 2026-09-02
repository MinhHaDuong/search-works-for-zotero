<!-- last-reviewed: 2026-09-02 -->
# The Zotero #6012 inference boundary, and which way the bridge runs

Evidence for ticket 0496, and the record of the one outcome it owes ticket 0491.
Everything below is read from `zotero/zotero` at PR #6012's head
`77e2c4b05111077108fe31e879f95b9687643e9a` through the forge API, with no local
clone. Every claim carries `path:line @ 77e2c4b`. Nothing here was executed
against a running build, and the two exit criteria that need one are reported as
NOT RUN rather than as negatives.

## 1. Currency of the head, and what that settles

`GET repos/zotero/zotero/pulls/6012`, called 2026-09-02T19:04Z, returns
`state: open`, `merged: false`, `head: 77e2c4b05111077108fe31e879f95b9687643e9a`,
`base: ff93139cce23209747a4519a32f992a1f45cd764`, `changed_files: 56`,
`updated_at: 2026-08-28T21:32:13Z`.

The head has not moved since the 2026-08-30 reading recorded in ticket 0496's
log. So "verify against the current #6012 head" is answered by the currency check
itself: the prior reading is the current reading, and the head SHA and the date
of the call above are what make that a check rather than an assumption. The
findings below were nonetheless re-derived from source at this ref, because the
prior note was taken from a clone and this pass had to read a different surface
to answer the same question.

Line numbers agree with the prior note in every case but one: the tokenizer
import URL is at `embeddings.js:1571`, not `:1570` — `:1570` is the
`ChromeUtils.importESModule(` call whose argument it is. The file lengths agree:
`ml.js` is 236 lines, `embeddings.js` is 3810.

## 2. Verified at source tonight

### 2.1 No changed file exposes an external route (confirmed, with a positive control)

`GET repos/zotero/zotero/pulls/6012/files --paginate` returns 56 filenames. None
lies under `chrome/content/zotero/xpcom/server/`, and none is a connector or
protocol handler; the set is UI (`chrome/content/zotero/**`), five xpcom modules
(`bestMatch.js`, `embeddings.js`, `lexical.js`, `ml.js`, `sdt.js` plus
`data/item.js`, `data/search.js`, `data/searchConditions.js`, `fulltext.js`,
`notifier.js`, `utilities_internal.js`, `zotero.mjs`), styles, locale, prefs
defaults, and ten test files.

The unified diff (`Accept: application/vnd.github.v3.diff`, 16 999 lines) contains
no occurrence of `Zotero.Server.Endpoints`, `Zotero.Server`, or `endpoints[`.

That null is a finding only because the same pattern was run against a case known
to be positive: `chrome/content/zotero/xpcom/server/server_localAPI.js @77e2c4b`
matches it 20+ times, including the registration
`Zotero.Server.Endpoints["/api/"] = Zotero.Server.LocalAPI.Root;` at
`server_localAPI.js:811`. The probe can see endpoint registrations; the PR
contains none.

The six files under `xpcom/server/` are unchanged by the PR
(`saveSession.js`, `server.js`, `server_connector.js`,
`server_connectorIntegration.js`, `server_integration.js`, `server_localAPI.js`),
and neither `server_localAPI.js` nor `server_connector.js @77e2c4b` mentions
`Zotero.ML`, `Zotero.Embeddings`, or embeddings at all. (`server_localAPI.js:2070`
matches `semantic` only inside the word "semantics", in a comment about PATCH.)

**No route returns a vector.** That is the sharp form of the first exit criterion,
and it holds.

### 2.2 The runtime is Gecko's, and nothing outside a Gecko process can reach it

`chrome/content/zotero/xpcom/ml.js @77e2c4b` (236 lines, added by this PR):

- `:69-70` — `ChromeUtils.importESModule("resource://gre/actors/MLEngineParent.sys.mjs")`
- `:92` — `Services.prefs.getBoolPref('browser.ml.enable', false)`
- `:95` — `Services.prefs.getBoolPref('browser.ml.checkForMemory', true)`
- `:98` — `Services.prefs.getIntPref('browser.ml.minimumPhysicalMemory', 3)`
- `:115-129` — `this.createEngine`, delegating to
  `ChromeUtils.importESModule("chrome://global/content/ml/EngineProcess.sys.mjs")` at `:124-125`
- `:208-209` — `ChromeUtils.importESModule("chrome://global/content/ml/ModelHub.sys.mjs")`
- `:231-232` — `ChromeUtils.importESModule("chrome://global/content/ml/EngineProcess.sys.mjs")`, then `EngineProcess.destroyMLEngine()` at `:234`

`chrome/content/zotero/xpcom/embeddings.js @77e2c4b`:

- `:670-679` and `:3785-3794` — `Zotero.ML.createEngine({ …, backend: 'onnx-native', … })`
- `:1570-1571` — `ChromeUtils.importESModule('chrome://global/content/ml/transformers.js')` for the tokenizer

`resource://gre` and `chrome://global` resolve only inside a Gecko process, and
`ChromeUtils` / `Services` are XPCOM globals. A Node process cannot reach any of
it. Confirmed at this ref.

### 2.3 There is no execution-provider selection: the engine is CPU-threaded

`ml.js:115-129` accepts `taskName`, `modelId` and `backend` and passes them
through; the only performance knob the caller sets is `numThreads`
(`embeddings.js:679`, `:3794`), sourced from `Zotero.ML.getOptimalConcurrency()`,
whose own doc-comment at `ml.js:131-133` reads "Thread count the runtime
recommends for **CPU inference** on this machine." No `device`, no
`executionProviders`, no `dml`/`cuda`/`webgpu` string appears anywhere in the
engine-creation path at this ref.

This is the fact that decides the outcome; see §6.

### 2.4 One indirect route does reach inference — and it returns items, not vectors

This refines the prior note rather than contradicting it, and it is the part
that could not be seen from the changed-file set alone.

The PR adds a root-level `bestMatch` search condition
(`data/searchConditions.js`, diff hunk: `name: 'bestMatch'`, `operators: { contains: true }`,
plus an accept rule letting the *operator* carry a positive-integer top-K).
`data/search.js:837-845 @77e2c4b` then executes it inside `Zotero.Search.search()`:

```
let bestMatch = this.getBestMatchQuery();
if (ids && ids.length && bestMatch && bestMatch.topK) {
    let { scores } = await Zotero.BestMatch.scoreItemIDs(bestMatch.query, ids);
```

with `getBestMatchQuery()` at `data/search.js:864-880`. Upstream's own comment at
`data/search.js:832-835` names the consumer set explicitly: a top-K cutoff "makes
membership relevance-based … so the saved search returns the same set when used as
a source (scopes, counts, **the API**)."

And the API path exists and is unchanged by the PR:
`Zotero.Server.Endpoints["/api/users/:userID/searches/:searchKey/items"]` at
`server_localAPI.js:1218` (group twin at `:1219`), executing
`search.setScope(savedSearch, true)` (`:1114`) then `search.search()` (`:1152`).
Saved searches are writable over the same local API — `Searches` supports
`POST` at `server_localAPI.js:1556-1567`, `Search` supports `PUT`/`PATCH` at
`:1581-1590` — behind the write-authorization handshake of §3.1.

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

`embeddings.js:1028-1053 @77e2c4b`, inside `embedPassages()`:

```
// Passages can route to an external endpoint serving the same model;
// queries always embed locally. After the retries, only this batch
// falls back to the local engine -- the next one tries the endpoint
// again.
let endpoint = Zotero.Prefs.get('embeddings.endpoint');
```

and the transport at `embeddings.js:953-971`:

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

with `ENDPOINT_ATTEMPTS = 3` at `:945`, `ENDPOINT_RETRY_DELAY = 2000` ms at `:947`,
and `_normalize` applied to each returned `Float32Array` at `:970`.

That is the HuggingFace text-embeddings-inference (TEI) request shape. **Zotero
#6012 can already be pointed at an external embedding server for passages.**

Four properties of that hook, all read at this ref, and all load-bearing for §4:

- **It is undeclared and hidden.** `defaults/preferences/zotero.js` in this diff
  declares `embeddings.model`, `embeddings.indexingPaused`,
  `embeddings.indexFulltext` and `embeddings.reranker` — and **not**
  `embeddings.endpoint`. The string `endpoint` occurs nowhere in the diff outside
  `embeddings.js`: no preferences XHTML, no `.ftl` locale entry, no test.
  It is a developer escape hatch, not a shipped feature.
- **Queries never leave.** Only `embedPassages()` consults it; `embedQuery()`
  (`:996-1019`) always goes to the local engine. Zotero therefore still loads its
  own model even when every passage is embedded elsewhere.
- **There is no handshake.** The request carries `inputs` and `truncate` and
  nothing else — no model name, no revision, no dimension, no pooling. Zotero's
  own vector identity is `getModelVersion()` = `name + '/' + revision`
  (`embeddings.js:208-210`), and none of it is sent or checked. The prefixes are
  applied locally before the request (`:1029-1031`), so the server receives
  already-prefixed text and must not add its own.
- **Degradation is silent.** After three failed attempts the batch embeds locally
  (`:1050-1052`) and is stored under the same model version as the endpoint's
  vectors. A dimension or model mismatch is not detected at all; a transport
  failure is not surfaced to the user.

### 2.6 The portable half is already what `bench/` runs (constraint (ii), verified here)

Checked against this repo rather than repeated from the prior note:
`bench/recall_embed.mjs:62` resolves and imports `@huggingface/transformers`, and
`:156` records the run's `runtime` as `'@huggingface/transformers in Node (ONNX)'`.
`bench/registry.mjs:37-41` defaults every model resolution to `kind: 'onnx'`.

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
  (`embeddings.js:208-210`). It is a **precondition, not a hint**: a mismatch with
  the active model is `409`, never a silent re-embed under a different function.
  This is the field whose absence is §2.5's defect.
- `role` selects the prefix Zotero itself applies —
  `getQueryPrefix()` / `getPassagePrefix()` (`embeddings.js:247-265`). The server
  applies it; the client sends bare text. Role is mandatory with no default:
  the query/passage asymmetry is exactly the thing a caller gets silently wrong.
- `inputs` is a batch for `role: "passage"` and MUST be length 1 for
  `role: "query"`, mirroring `embedQuery()`'s single-string contract and its
  in-flight cache (`embeddings.js:1005-1018`).
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
- `normalized: true` states what `_normalize()` at `embeddings.js:942` already
  does, so a client does not normalize twice.
- `provider` is what R30's disclosure clause needs from any facility that is not
  ours: backend, the device actually serving, thread count. At `77e2c4b` this is
  always `"cpu"` (§2.3), and saying so in the response is precisely how a
  consumer discovers that.

**Availability.** `GET /api/local/embeddings` returns the same envelope without
`embeddings`, plus `"enabled": bool` and `"downloaded": bool` — the facts behind
`Zotero.Embeddings.isEnabled()` (`:179-181`), `isDownloaded()` (`:534`), and
`Zotero.ML.isAvailable()` (`ml.js:92-98`, i.e. `browser.ml.enable` and the
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
a `ScoringCancelledError` (`embeddings.js:635`) and `scoreItemIDs` takes a
`shouldCancel` callback (`:1210`), so the plumbing exists.

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
   (`embeddings.js:962-969`); a server answering with the right count of
   wrong-dimension vectors is accepted and stored.
4. **Kill the silent fallback, or record it.** Either surface the endpoint failure
   and pause indexing, or tag the affected chunks with their producer so a later
   audit can find the mixed batch. Today the fallback at `:1050-1052` writes
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
NOT RUN. The one experiment: build #6012 at `77e2c4b`, select the registry entry
whose `modelId`/`dtype`/`pooling` match a `bench/models.json` record we already
embed, embed the X8 fidelity-probe corpus through `Zotero.Embeddings.embedPassages()`
with `embeddings.endpoint` unset, export the vectors, and score mean cosine against
the same corpus embedded in-process at the same rung — the X8 rule in SPEC.md §5.3,
≥ 0,999 keeps provider out of the embedder key. Note the trap this arm must avoid:
Zotero applies its own passage prefix (`embeddings.js:1029-1031`) and normalizes
(`:942`), so an arm that also applies our `input_template` would be measuring a
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
3 GiB (`ml.js:98`), and the model cache is the runtime's own `ModelHub`
(`ml.js:207-213`), i.e. Firefox's, not Zotero's and not ours — custody sits with a
third party in arm (a), which is a design fact rather than a measurement.

## 6. The outcome recorded for ticket 0491

**REJECT reuse, with the blocking fact.**

The blocking fact: at `77e2c4b`, embedding inference is created through Firefox's
own ML engine process with a recommended CPU thread count and **no
execution-provider selection of any kind** — `ml.js:115-129` passes `taskName`,
`modelId` and `backend` through and nothing else; the only performance argument
the caller supplies is `numThreads` (`embeddings.js:679`, `:3794`), whose source
is documented as the count "the runtime recommends for CPU inference"
(`ml.js:131-133`). An embedder hosted there therefore cannot satisfy R30's first
MUST clause, use a usable GPU (DECISIONS.md, 2026-08-30). Moving zoteus's
inference into Zotero's process forfeits a ratified requirement; it does not trade
RAM for speed, it trades a promise for RAM.

Compounding it, and sufficient on its own: no supported external call returns a
vector (§2.1), and the one indirect route that does reach inference returns ranked
item keys at the cost of writing a synced saved search per query (§2.4).

Why reject rather than defer. Deferral is right when the blocking fact is expected
to move with the thing deferred to. This one is not: #6012 merging adds no GPU
path and no inbound vector route — the GPU path would have to arrive in Firefox's
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
