# Zoteus v1.16.0 — SECURITY seat review

Commit 910310b. Read-only review of `src/` (111 files), `deploy/`, `Dockerfile`,
`docker-compose.yml`, `fly.toml`, `.github/workflows/`, `mcpb/manifest.json`,
`PRIVACY.md`, `SECURITY.md`.

## Verdict

The codebase is written by someone who has thought hard about this threat model, and
it shows: secrets travel in headers not URLs, `redact.ts` masks secret-bearing keys
before any log line, the OAuth token store is AES-256-GCM encrypted at rest, PKCE is
delegated to the SDK, passcode and metrics-token comparisons are constant-time, the
consent page HTML-escapes and strips bidi from the DCR `client_name`, caller-supplied
filesystem paths are confined to the data directory on shared deployments, FTS5 MATCH
is a bound parameter and every `.prepare()` is parameterised, and there is no
telemetry — the update check is off by default and matches `PRIVACY.md`. I found no
release-blocking finding. The most serious issue is a real SSRF-guard bypass in the
CIMD path (IPv4-mapped IPv6 literals slip past `isPrivateOrReservedIp`), reachable
only when the opt-in `ZOTEUS_CIMD_ENABLED` feature runs without a host allowlist —
verified with a positive control. The second is a deployment finding: the shipped
`fly.toml` enables metrics with no token and no Caddy in front, so `/metrics` and
`/usage.json` (which carry per-user Zotero ids and traffic volumes) are internet-open
on that path. The rest are should-fix/nit: a `PRIVACY.md` omission (the local model is
downloaded from huggingface.co, an undisclosed network endpoint), and an unconfined
`item_key` on the default download path (low impact — the write is blocked by URL
normalization, but an arbitrary directory is created first). SECURITY.md's policy
matches the actual reporting surface.

---

## Findings

### 1. CIMD SSRF guard bypassed by IPv4-mapped IPv6 literals

**Severity: should-fix** (release-blocking *if* an operator runs a public CIMD
directory connector without a host allowlist, which the docs recommend but do not
enforce).

**File:** `src/lib/cimd.ts:39-63` (`isPrivateOrReservedIp`), reached from
`src/lib/cimd.ts:79-81` (`assertHostAllowed`) and `src/auth/provider.ts:146-156`
(unauthenticated `/authorize` → `getClient` → `fetchClientMetadata`).

**Evidence.** The IPv6 branch only recognises the *dotted* IPv4-mapped form:

```js
// src/lib/cimd.ts:59-60
const mapped = lower.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/); // IPv4-mapped
if (mapped) return isPrivateOrReservedIp(mapped[1]!);
```

But `new URL()` normalises a bracketed IPv4-mapped literal to the **hex** form, which
this regex does not match. Positive control (Node 22.23.1, `isPrivateOrReservedIp`
reimplemented verbatim from the file):

```
new URL('https://[::ffff:127.0.0.1]/').hostname   -> [::ffff:7f00:1]
isPrivateOrReservedIp('::ffff:7f00:1')            -> false   (should be true)
isPrivateOrReservedIp('::ffff:a9fe:a9fe')         -> false   (169.254.169.254, cloud IMDS)
```

And Node actually routes that literal to loopback — a server listening on 127.0.0.1
accepted a connection to `::ffff:7f00:1` in the control run ("connected via
::ffff:7f00:1 -> hi"). `assertHostAllowed` only reaches `isPrivateOrReservedIp` for a
literal host (`net.isIP(host)` true); with `allowedHosts` empty (the default, and the
documented "any public host") nothing else stops it.

**Failure scenario.** Operator runs a directory connector with
`ZOTEUS_CIMD_ENABLED=true` and no `ZOTEUS_CIMD_ALLOWED_HOSTS`. An unauthenticated
attacker calls `/authorize?client_id=https://[::ffff:169.254.169.254]/x` (or
`[::ffff:127.0.0.1]`). The guard passes, the server-side GET fires against the cloud
metadata endpoint / a loopback admin service, and though only a JSON body ≤ `maxBytes`
with `redirect:'error'` comes back, response status and body content leak through the
error/parse path — a classic SSRF read primitive against link-local IMDS.

**Proposed fix.** In the `fam === 6` branch of `isPrivateOrReservedIp`, decode *any*
IPv4-mapped address (hex or dotted) before classifying — e.g. expand the last 32 bits
of `::ffff:*` to dotted quad and recurse — and treat `::ffff:*` that you cannot decode
as reserved. Add a fixture for `[::ffff:127.0.0.1]` / `[::ffff:169.254.169.254]` to
`tests/lib/cimd.test.ts` (currently no test exercises the hex-mapped form). The
existing TOCTOU caveat in the file header already tells operators to set an allowlist;
this closes the literal-IP hole for the default (no-allowlist) case.

---

### 2. `fly.toml` exposes `/metrics` and `/usage.json` to the internet with no token

**Severity: should-fix.**

**Files:** `fly.toml:8-21`, `src/transports/http.ts:230-255` (`opsGuard`),
`src/index.ts:75-80`.

**Evidence.** The ops guard fails open when no token is set:

```ts
// src/transports/http.ts:235
if (!opts.metricsToken) return next();
```

`fly.toml` sets `ZOTEUS_METRICS_ENABLED = "true"` and `PORT = "3939"` behind
`[http_service] internal_port = 3939 / force_https = true`, but sets **no**
`ZOTEUS_METRICS_TOKEN` and has **no** Caddy layer (unlike `docker-compose.yml`, whose
`deploy/Caddyfile:25-28` 404s `/metrics*` and `/usage.json*`). So on the Fly path both
endpoints answer any unauthenticated request. `/usage.json` serves
`usage.store.dailyRows`, whose rows carry `userId` (Zotero user ids), `clientId`, and
per-route traffic counts (`src/lib/request-logger.ts:89-101`,
`src/lib/usage/event.ts:18-39`). The app logs a warning to stderr
(`src/index.ts:76-80`) but still serves.

**Failure scenario.** Operator deploys with `fly deploy` using the shipped `fly.toml`
(the file's own comment calls it an "Alternative deploy target"). `curl
https://<app>.fly.dev/usage.json` returns the usage rollups — who uses the instance,
how much — to anyone. `/metrics` leaks the same volumes as Prometheus text. This is
the exact regression `deploy/Caddyfile:9-20` documents having shipped live on
mcp.zoteus.com for a day; the Fly path reintroduces it because there is no proxy to
carry the second lock.

**Proposed fix.** Either (a) make the app refuse to serve `/metrics` and
`/usage.json` without a token when `oauth.enabled` (fail closed on a reachable
deployment) rather than only warning, or (b) add `ZOTEUS_METRICS_TOKEN` to the Fly
required-secrets list and gate the metrics endpoints in `fly.toml` docs. (a) is the
robust fix: a warning to stderr on a PaaS is a warning nobody reads.

---

### 3. `PRIVACY.md` omits the huggingface.co model download from its network-request list

**Severity: should-fix (documentation / privacy accuracy).**

**Files:** `PRIVACY.md` ("Network requests Zoteus makes"),
`src/features/search/embeddings.ts:658,828,1096`, `mcpb/manifest.json` (embedding_model
description: "weights downloaded once into the data directory").

**Evidence.** `PRIVACY.md` says local embeddings are "on-device model by default, so no
library text leaves your machine" and enumerates every network request Zoteus makes
(Zotero, scholar providers, embedding providers *only if openai/gemini selected*,
import resolvers, update check). It does **not** list huggingface.co / its CDN, but the
default `local` embedder downloads model weights from there on first build
(`@huggingface/transformers` fetches from the HF hub; `modelCacheDir` only pins where
they land — `embeddings.ts:828` "before the pipeline downloads anything"). The claim
"no library text leaves your machine" is true; the claim that the list is complete is
not — a default install makes an undisclosed request to a third party (Hugging Face).

**Failure scenario.** A privacy-conscious user reads PRIVACY.md, sees only Zotero
contacted on a default (local, no update check) install, and is surprised when the
first index build reaches out to huggingface.co. No data leak, but the policy
misrepresents the default install's egress.

**Proposed fix.** Add a bullet to `PRIVACY.md`'s network-requests list: the local
embedding model's weights are fetched once from Hugging Face
(`huggingface.co` / `cdn-lfs`), contain no library content, and are cached under the
data directory thereafter; note that `ZOTEUS_EMBEDDINGS=off` or a pre-provisioned
`ZOTEUS_TRANSFORMERS_PATH` model avoids it.

---

### 4. `item_key` is not confined/validated on the default download path

**Severity: nit.**

**File:** `src/tools/attachment.ts:135-137`.

**Evidence.** When `save_path` is omitted, the default is built from the caller's
`item_key` with no `resolveCallerPath` and no key-shape validation:

```ts
savePath ??= join(ctx.config.dataDir, 'attachments', args.item_key);
await mkdir(dirname(savePath), { recursive: true });
const r = await downloadFile(ctx.web, lib, args.item_key, savePath);
```

`item_key` is `z.string()`. `join('/data','attachments','../../../../tmp/x/y')`
resolves to `/tmp/x/y`, and `mkdir(dirname())` then **creates `/tmp/x`** on the
operator's disk. The subsequent write is blocked because `downloadFileBytes` builds
`…/items/<key>/file` and URL normalization collapses the `..` segments, so the Zotero
request 404s before any bytes are written (verified: the fetched pathname becomes
`/users/ID/items/…` with the traversal folded away, returning nothing). So the impact
is bounded to arbitrary empty-directory creation, not arbitrary file write — hence nit,
not should-fix. `save_path` itself is correctly confined
(`src/tools/attachment.ts:57-64`), and the storage-read path already sanitises with
`basename(opts.key)` (`src/features/attachments/bytes.ts:133`).

**Failure scenario.** On a shared/hosted deployment, a caller passes
`item_key: "../../../../var/tmp/probe"` with no `save_path`; the server creates
`/var/tmp` structure under the operator uid. Low value, but it is caller-controlled
filesystem effect that skips the confinement applied everywhere else.

**Proposed fix.** Validate `item_key` against the Zotero key shape (`^[A-Z0-9]{8}$`,
already assumed in `src/features/search/index-manager.ts:135`) in the tool schema, or
run the default `savePath` through `resolveCallerPath` with `confined: ctx.remoteCaller`
like the explicit-path branch does.

---

### 5. Zotero keys interpolated into API URL paths without `encodeURIComponent`

**Severity: nit.**

**Files:** `src/api/web-client.ts:172,178` etc. (`/items/${key}`),
`src/api/local-client.ts` and `src/api/local-writes.ts:313,328` similarly.

**Evidence.** Item/collection keys from tool arguments are template-interpolated into
request paths (`this.prefix(lib) + '/items/' + key`) with no encoding, unlike query
params, which go through `URLSearchParams` (`buildQuery`). Delete is the exception —
`deleteByKeys` does `c.map(encodeURIComponent)` (`web-client.ts:563`). A key containing
`/`, `?`, or `#` would change the request path/query. This is not a server-side
injection into Zoteus (the caller already holds the API key and is acting on their own
library), and Zotero rejects malformed keys, so the blast radius is a
caller-shooting-own-foot request. Worth normalising for consistency with the delete
path and to keep future callers honest.

**Proposed fix.** `encodeURIComponent(key)` at the path-interpolation sites, matching
`deleteByKeys`; or validate the key shape once at the tool boundary.

---

## What is solid (checked, not defects)

- **Secret handling.** `redact.ts:2-3` masks `pass/secret/token/api-key/authorization/
  bearer/zoterokey/…` by key name before any log write; `logger.ts:49` runs
  `redactArgs` on every emit. Zotero and embedding-provider keys travel in headers, not
  URLs (`web-client.ts:91`, `embeddings.ts:997,1011` — the Gemini path explicitly avoids
  `?key=` "because URLs get logged"). `request-logger.ts:66` logs `req.path`, never
  `originalUrl`, "so no query string in logs". `usage/event.ts` records shapes/lengths,
  never argument values (positive intent verified in `describeShape`).
- **OAuth.** Token store is AES-256-GCM with a random IV per write, fails closed on a
  bad secret (`auth/store.ts:160-171`); config *refuses to start* rather than falling
  back on the security-model knobs (`config.ts:326-390`); passcode and metrics token use
  `timingSafeEqual` over SHA-256 digests to avoid length leak
  (`transports/http.ts:64-68`, `provider.ts:504-510`); PKCE S256 is the SDK's;
  auth codes are one-time and TTL'd; DCR client store is FIFO-capped at 1000
  (`provider.ts:483-490`). Consent page escapes + strips control/bidi from
  `client_name` (`auth/consent.ts`).
- **No unauthenticated non-loopback bind.** `transports/http.ts:98-103` throws unless
  OAuth is on, `allowInsecureBind`, or the host is loopback. DNS-rebinding protection is
  enabled whenever OAuth is (`index.ts:107`), tested in
  `tests/integration/dns-rebinding.test.ts`.
- **SQL.** Every statement in `sqlite-index.ts`/`usage/store.ts` is `.prepare()` with
  `?` bind parameters; FTS5 MATCH is a bound `?` (`sqlite-index.ts:1029,1466`), terms
  are quoted via `ftsTerm` (`:2136`, doubles embedded `"`). The only interpolated
  `exec()` strings are constant PRAGMAs (`BUSY_TIMEOUT_MS`, an internal const). Accent
  expansion is capped at `MAX_ACCENT_VARIANTS` against posting-list amplification.
- **Path confinement.** `caller-path.ts` resolves against the realpath (symlink-aware)
  and confines to the data dir when `remoteCaller`; applied in `attach-file.ts`,
  `attachment.ts`, `tag-audit.ts`. Storage reads use `basename` on the key
  (`bytes.ts:133`).
- **exec/shell.** No `child_process` in `src/`; the only uses are `execFileSync` in
  `scripts/mcpb-bundle.ts` (build-time, fixed argv arrays, no shell). No zip/XML entity
  expansion risk — `epub.ts` and `resolve.ts` parse with bounded regex, no XXE parser.
- **Dockerfile.** Drops to the `node` uid, `--ignore-scripts` on installs, multi-stage.
  `deploy.yml` publishes with npm provenance (OIDC) and `GITHUB_TOKEN`, no long-lived
  secrets beyond `NPM_TOKEN`.
- **SECURITY.md** matches the surface: private GitHub advisory + `support@zoteus.com`,
  in-scope list names the npm package, mcpb bundle, ghcr image, and hosted instance;
  hosted-first disclosure ordering is stated. No mismatch with the reporting reality.

## What I could not check, and why

- **Runtime behaviour of the OAuth flow end-to-end** (token replay, refresh rotation
  under concurrency): read-only static review only; the logic in `provider.ts` reads
  correct (rotate-on-use refresh, one-time codes) but I did not execute it.
- **The hosted instance `mcp.zoteus.com`** and `zoteus.com/privacy`: out of this
  clone's scope, not fetched.
- **`@modelcontextprotocol/sdk` 1.29.0 internals** (bearer middleware, authorize
  handler, `redirectUriMatches`): trusted as a pinned dependency; I did not audit
  node_modules. If the SDK's `/authorize` reaches `getClient` before any rate limit, the
  CIMD SSRF in finding 1 is unauthenticated — I confirmed the call path in
  `provider.ts` but not the SDK's ordering.
- **Whether Node's `dns.lookup` can return a hex-form IPv4-mapped address** that would
  extend finding 1 to the DNS (non-literal host) path: the literal-IP bypass is proven;
  the DNS variant is plausible but I did not have a positive control for it, so I report
  only the literal path as established.
- **`transformers.js` actual download host/CDN** for finding 3: I confirmed the code
  downloads and the manifest says "downloaded once", and huggingface.co is the
  documented source (`docs/semantic-search.md:727`), but I did not run a build to
  capture the exact request.
