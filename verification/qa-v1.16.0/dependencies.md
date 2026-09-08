# Zoteus v1.16.0 — dependencies and pathological libraries

Target: fresh clone of oscardvs/zoteus at `910310b` (package.json `version: 1.16.0`). Read-only; no `node_modules` was created in the target. Tooling on this machine: Node v22.23.1, npm 10.9.8 (`node --version`, `npm --version`). Date of the registry reads: 2026-09-08.

## Verdict

The production tree is small and clean for a Node project: 107 non-dev packages in the lockfile (`package-lock.json`, counted by script), all from the npm registry with integrity hashes, zero packages with install scripts, zero deprecated packages, one licence that is not permissive (citeproc, CPAL-1.0 OR AGPL-1.0), and native binaries pinned at one coherent version (`@napi-rs/canvas` 0.1.100 across all 11 platform packages, enforced by an existing test). `npm audit --package-lock-only` flags 16 advisories; 10 are dev-only, 5 of the 6 production ones are unreachable from `src/` and disappear with a plain in-range `npm update` and no code change. The one that matters is structural rather than a CVE: `pdfjs-dist` is pinned at 5.6.205, the **last release that runs on Node 20.19**, and everything after it (from 5.7.284 onward, still inside the declared `^5.6.205` range) requires Node ≥ 22.13. The tree therefore cannot take the pdfjs security fix (CVE-2026-16633, patched in 6.2.108) without raising the Node floor, which the code has half-done already (`node:sqlite`, Node 22.13+, is the documented index backend). Nothing here blocks shipping v1.16.0 as built; the two should-fix items are the Node-floor/pdfjs decision and a CPAL attribution notice for citeproc, both cheap and both actionable by the maintainer alone.

## Production dependencies

Direct dependencies and every transitive package large or load-bearing enough to matter. Versions are the lockfile's resolved versions; licences are the lockfile's `license` fields (`node -e` over `package-lock.json`), cross-checked with `npm view` for the direct ones. "Latest" is `npm view <pkg> version` on 2026-09-08.

| Package | Locked | Latest | Licence | Role / who pulls it |
|---|---|---|---|---|
| @modelcontextprotocol/sdk | 1.29.0 | 1.30.0 | MIT | direct — MCP server, stdio + streamable HTTP + OAuth router |
| zod | 3.25.76 | 4.5.4 (major) | MIT | direct — 32 imports in src; SDK peer allows ^3.25 or ^4 |
| express | 5.2.1 | 5.2.1 | MIT | direct — HTTP transport (`src/transports/http.ts`), also an SDK dep |
| express-rate-limit | 8.5.2 | 8.7.0 | MIT | direct — two limiters (`http.ts:259`, `auth/router.ts:79`) |
| cors | 2.8.6 | 2.8.6 | MIT | direct — one `app.use(path, cors())` |
| citeproc | 2.4.63 | 2.4.63 (published 2023-04-17) | **CPAL-1.0 OR AGPL-1.0** | direct — `format_bibliography` tool via `features/citation/citeproc-engine.ts` |
| pdfjs-dist | 5.6.205 (optional) | 6.3.289 | Apache-2.0 | direct optional — exact page numbers in `features/fulltext/pdf-pages.ts`, `pdf-locate.ts`; 38.9 MB unpacked |
| @napi-rs/canvas | 0.1.100 (optional) | 1.0.8 | MIT | via pdfjs-dist `^0.1.96`; loader only, 0.13 MB |
| @napi-rs/canvas-{darwin-arm64, darwin-x64, linux-x64-gnu, linux-x64-musl, linux-arm64-gnu, linux-arm64-musl, win32-x64-msvc, win32-arm64-msvc, android-arm64, linux-arm-gnueabihf, linux-riscv64-gnu} | 0.1.100 each | 1.0.8 | MIT | skia binaries, 19.1–36.0 MB unpacked each (`npm view … dist.unpackedSize`) |
| node-readable-to-web-readable-stream | 0.4.2 (optional) | — | MIT | via pdfjs-dist |
| hono | 4.12.23 | 4.13.7 | MIT | via @hono/node-server `^4`; 1.35 MB; no SDK module Zoteus imports uses hono itself |
| @hono/node-server | 1.19.14 | 2.1.1 (major; SDK 1.30 accepts either) | MIT | via SDK — `getRequestListener` only, in `server/streamableHttp.js` |
| ajv + ajv-formats + fast-uri | 8.20.0 / 3.0.1 / 3.1.2 | 8.20.0 / — / 4.1.4 | MIT / MIT / BSD-3 | via SDK — tool output-schema validation |
| jose | 6.2.3 | 6.2.12 | MIT | via SDK — OAuth JWT |
| pkce-challenge | 5.0.1 | — | MIT | via SDK (also, redundantly, a devDependency in package.json) |
| eventsource, eventsource-parser | 3.0.7 / 3.1.0 | — | MIT | via SDK |
| cross-spawn | 7.0.6 | — | MIT | via SDK (stdio client side; unused by a server) |
| zod-to-json-schema, json-schema-typed | 3.25.2 / 8.0.2 | — | ISC / BSD-2 | via SDK |
| ip-address | 10.2.0 | 10.7.0 | MIT | via express-rate-limit — `Address6` only, IPv6 subnet keys |
| body-parser, qs, raw-body, iconv-lite, router, send, serve-static, … | 2.2.2 / 6.15.2 / 3.0.2 / 0.7.2 / 2.2.0 / 1.2.1 / 2.2.1 | — | MIT / BSD-3 / MIT | express 5 internals |

Licence histogram of the 107 production packages (lockfile fields): MIT 95, ISC 7, BSD-3-Clause 2 (fast-uri, qs), BSD-2-Clause 1 (json-schema-typed), Apache-2.0 1 (pdfjs-dist), CPAL-1.0 OR AGPL-1.0 1 (citeproc). No GPL, SSPL or unlicensed package. `LICENSE` at the repo root is MIT, copyright 2026 Oscar Devos; `package.json`, `mcpb/manifest.json`, `plugin.json` all say MIT.

Not in the tree at all, contrary to the briefing's list: there is no SQLite driver package (the index uses the built-in `node:sqlite`, `src/features/search/vector-salvage.ts:12`, `src/lib/usage/index.ts:48`) and no transformers.js / ONNX package (`@huggingface/transformers` is resolved at runtime from a user-supplied path, `src/features/search/embeddings.ts:407`, never installed by Zoteus). Both are correct design choices for the bundle size; the transformers tree the docs tell users to install is audited separately in finding 6.

Size composition, measured with `npm view <pkg>@<ver> dist.unpackedSize` over all 107 production packages (9 tiny old packages report no size and count as 0): non-native production tree **53.6 MB unpacked**, of which pdfjs-dist is 38.9 MB and everything else 14.7 MB (SDK 4.07, zod 3.43, hono 1.35, ajv 0.99, citeproc 0.93). Native skia binaries are on top of that, per platform above.

## Findings, most severe first

Severity scale: release-blocking / should-fix / nit. None is release-blocking.

### 1. pdfjs-dist is frozen on the last Node-20 release, and the pinned line carries an unpatched high advisory — should-fix (a decision, then a two-line change)

**Evidence.**
- `npm audit --package-lock-only --json` (exit 1, report saved): `pdfjs-dist` 5.6.205, high, GHSA-hq66-cqwq-w95j / CVE-2026-16633, "Arbitrary JavaScript execution upon opening a malicious PDF", affected `>=5.6.83 <6.2.108`, `fixAvailable: {version: 6.3.289, isSemVerMajor: true}`.
- `npm view pdfjs-dist versions`: after 5.6.205 come 5.7.284, 6.0.227, 6.1.200, 6.2.108, 6.3.289 (released 2026-03-29, 04-27, 05-30, 06-27, 07-28, 08-29 respectively, from `time`).
- `npm view pdfjs-dist@5.6.205 engines.node` → `>=20.19.0 || >=22.13.0 || >=24`. `npm view pdfjs-dist@5.7.284 engines.node` → `>=22.13.0 || >=24`. Same for 6.0.227, 6.1.200, 6.2.108, 6.3.289. So **5.6.205 is the only pdfjs release compatible with the declared `engines.node: ">=20.19"`**, and it is 5 releases and 5 months behind.
- The declared range is `^5.6.205` (package.json `optionalDependencies`), which admits 5.7.284. Any resolve that ignores the lockfile (`npm update`, a deleted lockfile, a downstream project that depends on `@oscardvs/zoteus` and resolves its own tree) picks 5.7.284 and silently breaks the Node 20 promise the CI matrix (`ci.yml`: `node-version: [20, 22]`) is there to defend.
- pdfjs 6.x moves the canvas dependency to `@napi-rs/canvas ^1.0.0` (`npm view pdfjs-dist@6.3.289 optionalDependencies`); canvas 1.0.0 release notes state "no breaking changes", 1.0.8 is current, and the same 11 platform packages exist at 1.0.8 (`npm view @napi-rs/canvas@1.0.8 optionalDependencies`).
- Who runs the bundle: Zoteus's own docs record Claude Desktop as Electron 42.10.0 (`docs/semantic-search.md:413`, `CHANGELOG.md:604`), and Electron 42.10.0 bundles **Node 24.18.1** (releases.electronjs.org/release/v42.10.0). The Docker image is `node:22-bookworm-slim` (currently 22.23). Node 20 reached end of life on 2026-04-30.

**Reachability of the CVE itself.** Low, and the maintainer can verify the premise: the advisory is CWE-79, triggered "if PDF.js has `enableScripting` at its default of true and no CSP restricts script execution", i.e. it is the viewer's PDF-JavaScript sandbox. Zoteus never instantiates a viewer; it calls `getDocument({data, useSystemFonts: true, isEvalSupported: false})` then `page.getTextContent()` (`src/features/fulltext/pdf-pages.ts:32-37,85`, `pdf-locate.ts:253`). For the CVE to bite, the maintainer would have to believe the legacy Node build executes document-level JS actions during text extraction — it does not, as far as the advisory text goes. The reason to act is not this CVE but the next one: the pinned line will never receive a fix, because every later pdfjs requires Node ≥ 22.13.

**Impact.** Zoteus parses PDFs that come from the user's Zotero library, which come from the web; a PDF parser is the single largest attack surface in the tree (38.9 MB of it), and it is now on an orphaned branch.

**Fix.** Decide the Node floor. Recommended: `engines.node: ">=22.13"` in package.json and `runtimes.node` in `mcpb/manifest.json`, drop 20 from the CI matrix, then `npm i pdfjs-dist@^6.3.289` (which brings `@napi-rs/canvas` 1.0.8; `tests/scripts/mcpb-bundle.test.ts:168` "at one version" and `requiredNativePackages` read the lockfile, so the bundle gate follows automatically). This matches what the docs already say is the good path ("Run on Node 22.13+ so the index goes to SQLite", `docs/semantic-search.md:1022`). If Node 20 must stay: pin `pdfjs-dist` to exactly `5.6.205` (no caret) so nothing can drift, and record in SECURITY.md that the PDF parser is frozen — an explicit orphan is better than an accidental one.

### 2. citeproc is CPAL-1.0 / AGPL-3.0 dual-licensed and the redistributed bundles carry no attribution notice — should-fix

**Evidence.**
- `package-lock.json` `node_modules/citeproc.license`: `"CPAL-1.0 OR AGPL-1.0"`; `npm view citeproc@2.4.63 license` says the same. The tarball (`data.jsdelivr.com …/citeproc@2.4.63/flat`) contains `LICENSE`, whose text (fetched from the CDN) grants use "under EITHER the terms of the Common Public Attribution License (CPAL) … OR the terms of the GNU Affero General Public License (AGPL)".
- CPAL Exhibit B for citeproc-js (fetched from `Juris-M/citeproc-js/master/CPAL`): copyright notice "(c) Frank Bennett", attribution phrase "citeproc-js implements the Citation Style Language", attribution URL `https://citationstyles.org/`; Section 14 requires the attribution to be displayed in Larger Works.
- What redistributes it: the three `.mcpb` archives and the `ghcr.io/oscardvs/zoteus` image both ship `node_modules/citeproc` (the `.mcpb` stage copies the full production tree, `scripts/mcpb-bundle.ts:254`; the Docker `deps` stage does `npm ci --omit=dev`). The npm package does not vendor it (`files: ["dist", "README.md", "LICENSE"]`), so the obligation attaches to the bundles and the image, not to `npm i @oscardvs/zoteus`.
- No attribution anywhere: `grep -ri "Frank Bennett\|citationstyles.org\|CPAL" README.md docs mcpb/manifest.json LICENSE` returns nothing (the only hits for "citeproc" are tool descriptions).

**Impact.** Under the CPAL branch (file-scoped copyleft, MPL-1.1 lineage) an MIT Larger Work is fine and citeproc's own files stay CPAL — no contamination of Zoteus's source. What is missing is the Exhibit B notice, which is the whole point of the CPAL over the MPL. Under the AGPL branch the whole distributed program would be AGPL, which the MIT label on the manifest contradicts; Zoteus should state that it takes the CPAL option. Zotero itself ships citeproc-js under its AGPL; a scholar's tool is exactly where someone will look.

**Fix.** Add a `THIRD_PARTY_NOTICES.md` (or a "Licences" section in README) with the three Exhibit B lines and the sentence "citeproc-js is used under the Common Public Attribution License 1.0", include it in `files` and in the staged bundle, and have `zotero_whoami` or the server's startup line print the attribution phrase once (CPAL §14 asks for display in the user interface; an MCP server's only UI is its text). Ten minutes.

### 3. Five production advisories, all unreachable, all fixed by `npm update` — should-fix (mechanical)

`npm audit --package-lock-only` metadata: 16 advisories (1 critical, 9 high, 5 moderate, 1 low) over 357 packages (prod 94, dev 250, optional 89 in npm's overlapping categories). The command demonstrably resolved the tree — it returned a non-empty report with per-package node paths, so this is a positive result, not silence. Ten advisories are dev-only (vitest/vite/esbuild/postcss/js-yaml/nanoid/brace-expansion; see finding 7). The six production ones, triaged against `src/`:

| Package (locked) | Advisories | Reachable from src/? | Fix |
|---|---|---|---|
| pdfjs-dist 5.6.205 | GHSA-hq66-cqwq-w95j high | no viewer → no (finding 1) | major, see 1 |
| hono 4.12.23 | 12 advisories (CORS reflect, serve-static traversal, Lambda adapters, JSX, language middleware ReDoS, proxy helper) | **No.** Scanned all 58 non-example `dist/esm/**/*.js` files of the SDK 1.29.0 via the CDN: the only hono-family import is `getRequestListener` from `@hono/node-server` in `server/streamableHttp.js`; `@hono/node-server/dist/listener.mjs` imports only `http2`, `stream`, `crypto`. No hono middleware or adapter is ever instantiated. | `npm update hono` → 4.12.34+ is in range (`^4` / `^4.11.4`); audit says `fixAvailable: true`, not major |
| @hono/node-server 1.19.14 | GHSA-frvp-7c67-39w9 moderate, `serve-static` traversal on Windows | No — `serveStatic` is not imported | `npm update` → 1.19.15+ in range |
| fast-uri 3.1.2 | 6 high (host confusion / SSRF in URI parsing) | No — reached only through ajv `$ref` resolution of Zoteus's own tool schemas (`server/mcp.js` output-schema validation); no attacker-supplied URI passes through it | `npm update` → 3.1.6+ in `^3.0.1` |
| ip-address 10.2.0 | GHSA-mwp4-54f8-5fhr high + 2 moderate, all in `Address4` | No — `express-rate-limit@8.5.2/dist/index.mjs:3` imports `Address6` only; the advisory itself says `Address6` rejects the leading-zero form | `npm update` → 10.3.1+ in `^10.2.0` |
| qs 6.15.2 | GHSA-4mjr-xmp4-gh2g moderate (isBuffer DoS), GHSA-x5fp-wj9c-mxmx moderate (array-limit bypass) | Marginal — express 5 parses query strings on the hosted transport; Zoteus reads only `req.query.days` (`http.ts:250`) and the OAuth params | `npm update` → 6.16.0 in `^6.14.0` |
| body-parser 2.2.2 | GHSA-v422-hmwv-36x6 low (invalid `limit` silently disables the cap) | No — the only call passes a valid `limit: '8mb'` (`http.ts:279`) | `npm update` → 2.3.0 in `^2.2.1` |

**Fix.** `npm update` (no package.json change; every fix is inside the existing caret ranges — verified by the audit's `fixAvailable: true` without `isSemVerMajor`), run the suite, commit the lockfile. It also lifts the SDK to 1.30.0 in range. What a maintainer would have to believe for this to be harmless as-is: that the hosted instance at `mcp.zoteus.com` never exposes a hono middleware, `Address4`, or ajv to untrusted input — which is what the code shows today, but a future SDK minor could start using `hono/cors`, and the update is free.

### 4. The Linux bundle and the Linux Docker image carry musl skia binaries that no supported host loads — should-fix (size), nit (correctness)

**Evidence.**
- `requiredNativePackages(lock, 'linux')` selects by `os` and `cpu` only (`scripts/mcpb-bundle.ts:95-105`), so the Linux bundle owes and the gate demands both `-gnu` and `-musl` for x64 and arm64: four binaries, unpacked 31.8 + 28.4 + 26.4 + 24.4 MB (`npm view … dist.unpackedSize`). `docs/distribution.md:134-135` records the result: macOS ≈ 33 MB, Windows ≈ 32 MB, Linux ≈ 57 MB.
- Why both land: the platform packages declare `libc` (`npm view @napi-rs/canvas-linux-x64-musl@0.1.100 libc` → `["musl"]`, `-gnu` → `["glibc"]`), but `grep -c '"libc"' package-lock.json` → **0**. Positive control: a lockfile I generated in the scratchpad with npm 10.9.8 for `@huggingface/transformers` (whose `sharp` platform packages also declare `libc`) also has 0 `libc` entries — so npm 10.9.8 simply does not record `libc` in lockfiles, and `npm ci` from a lockfile cannot filter on it. Not a Zoteus defect; a property of the tool it uses.
- Derived, not measured: Linux bundle unpacked ≈ 53.6 + 31.8 + 28.4 + 26.4 + 24.4 = 164.6 MB, of which musl = 52.8 MB = 32 %. Applying that share to the 57 MB archive gives ≈ 18 MB of download per Linux user that nothing loads (assumes a uniform compression ratio, which native binaries and JS do not share; the real figure needs one `unzip -lv`). The Docker image is built with a plain `npm ci --omit=dev` on Debian (`Dockerfile:16`); by the same mechanism the amd64 image should carry `linux-x64-musl` (28.4 MB) and the arm64 image `linux-arm64-musl` (24.4 MB). I did not pull the image to confirm; `docker run --rm ghcr.io/oscardvs/zoteus ls node_modules/@napi-rs` settles it in one line.
- Who needs musl: an Alpine host. Claude Desktop's built-in Node is Electron's glibc build; the Docker base is Debian bookworm. No Alpine path exists in the repo.

**Fix.** Pass `--libc=glibc` in the Linux `stage` step (npm ≥ 10.3 accepts it, the script already gates on that) and make `requiredNativePackages` skip directories whose name ends in `-musl` for the linux target — the lockfile has no `libc` field to read, so the name is the only signal, and the existing test at `tests/scripts/mcpb-bundle.test.ts:134` ("owes linux glibc and musl") flips to "owes glibc only". Add `--libc=glibc` to the Dockerfile `deps` stage too. If Alpine is meant to be supported, say so in the docs and keep the binaries; then this is a nit.

### 5. The bundle gate is version-blind on a foreign archive — nit

**Evidence.** `auditBundle` (`scripts/mcpb-bundle.ts:138-179`) proves each owed native package by "a `.node` file under `node_modules/@napi-rs/canvas-<target>/`" and takes the expected version from the **repo's** lockfile, never from the archive's own `package.json` files. `check` on a downloaded release asset (`docs/distribution.md`, "a downloaded release asset can be checked the same way") therefore passes an old archive against a newer lockfile as long as the directory names match, and prints the lockfile's version next to it (`ok  <name>@<version>`), which is then a claim about the lockfile, not the archive.

Can a build from one lockfile carry mismatched versions? No: `stage` runs `npm ci` then `npm install --no-save` under the same lockfile, and `tests/scripts/mcpb-bundle.test.ts:168-180` asserts every owed binary sits at the main `@napi-rs/canvas` version — a real gate, and it read the real lockfile. The gap is only the standalone `check` of an asset that was not built from the current tree.

**Fix.** In `check`, `unzip -p <archive> node_modules/@napi-rs/canvas-*/package.json` and compare `version` to the lockfile's; five lines. Worth doing before the canvas 1.0.8 upgrade, which is the first time the old and new archives will differ in version but not in directory name.

### 6. The on-device embedding tree users are told to install has four unfixable high advisories and three install scripts — nit for Zoteus, worth a sentence in the docs

**Evidence.** The docs and the manifest instruct users to run `npm i @huggingface/transformers` in a private folder (`mcpb/manifest.json` `transformers_path.description`, README:70). Resolved in the scratchpad with `npm install --package-lock-only` (no `node_modules` created, verified by `ls`): 74 packages, `@huggingface/transformers` 4.2.0, `onnxruntime-node` 1.24.3, `sharp` 0.34.5. Install scripts: `onnxruntime-node`, `protobufjs`, `sharp` (`hasInstallScript` in that lockfile) — onnxruntime-node's script downloads binaries at install time. `npm audit --package-lock-only` there: 4 high, `fixAvailable: false` for all — `adm-zip <0.6.0` (GHSA-xcpc-8h2w-3j85, via onnxruntime-node's installer), `sharp <0.35.0` (GHSA-f88m-g3jw-g9cj, four libvips CVEs), plus the umbrella entries on `onnxruntime-node` and `@huggingface/transformers` themselves.

**Reachability.** Zoteus uses the feature-extraction pipeline on text only (`embeddings.ts`); `sharp` decodes images and is never invoked; `adm-zip` runs once inside onnxruntime-node's installer on an archive fetched from the vendor. So: not exploitable through Zoteus, but the user is told to put 700 MB of unaudited native code next to their library on Zoteus's advice.

**Fix.** Nothing in the tree. In the docs, name the version the release was tested against (`@huggingface/transformers@4.2.0`, which `embeddings.ts:85` already mentions) so the instruction is reproducible, and note that `--ignore-scripts` is not an option there (onnxruntime-node needs its installer).

### 7. Dev tooling is end-of-life: ESLint 8, vitest 2, and ten dev-only advisories — nit

**Evidence.** Lockfile `deprecated` fields (script over `package-lock.json`): `eslint` 8.57.1 "no longer supported", `@humanwhocodes/config-array`, `@humanwhocodes/object-schema`, `glob` 7.2.3, `inflight` 1.0.6, `rimraf` 3.0.2 — all six dev-only. Audit, dev-only: `vitest` 2.1.9 critical (GHSA-5xrq-8626-4rwp, "when Vitest UI server is listening" — CI runs `vitest run`, no UI), `vite` 5.4.21 high, `esbuild` 0.21.5/0.28.0 moderate (dev server), `postcss` 8.5.15 high, `js-yaml` 4.1.1 high, `nanoid` 3.3.12 high, `brace-expansion` 1.1.15 high (five copies). Fix path for the vitest cluster is `vitest@5` (major). Duplicates are all dev (23 `@esbuild/*` pairs from two esbuild versions, ajv 6 vs 8, minimatch 3 vs 10); the only production duplicate is `content-type` 1.0.5 / 2.0.0, 12 KB.

**Impact.** None at runtime; none of it ships. The cost is a growing `npm audit` wall that will hide the next real production advisory — finding 3 was found by reading 16 entries, 10 of which are this noise.

**Fix.** `eslint@9` (flat config, the two `@typescript-eslint` packages are already on 8.x which supports it) and `vitest@5` in one dev PR; run `npm audit --omit=dev` in CI so the signal is production-only.

### 8. Runtime pins: three declarations of the Node floor disagree with what the code wants — nit, folded into finding 1

`package.json` `engines: ">=20.19"`; `mcpb/manifest.json` `runtimes.node: ">=20.19.0"`; `ci.yml` matrix `[20, 22]`; `Dockerfile` `node:22-bookworm-slim` (floating minor tag, no digest); `docs/architecture.md:3` "Node 20+"; index backend and usage log require 22.13 (`config.ts:59`, `usage/index.ts:65`). Claude Desktop runs Node 24.18.1 (Electron 42.10.0). The Node 20 promise costs the pdfjs freeze (finding 1) and buys support for a runtime that is EOL. Also `plugin.json` still says `"version": "1.15.0"` while `package.json`, `server.json` and the manifest say 1.16.0 — not a dependency matter, but it is a manifest and a one-word drift.

### What is healthy, stated so it is not re-audited

- Supply chain: 0 production packages with install scripts (3 in the whole lockfile, all dev: esbuild ×2, fsevents); 357/357 packages resolve to `https://registry.npmjs.org/` with an `integrity` hash; no git or tarball URLs. The skia binaries arrive as ordinary npm packages, nothing fetches at install time. npm publish uses `--provenance` under OIDC (`deploy.yml`).
- Native pins: `@napi-rs/canvas` and all 11 platform packages at 0.1.100, `optional: true`, correct `os`/`cpu` arrays; `tests/scripts/mcpb-bundle.test.ts:168` asserts this against the real lockfile on every CI run.
- The bundle script hardcodes no version; a canvas upgrade flows from the lockfile into staging and the gate.
- Docker: `--ignore-scripts` on both `npm ci` layers, `--omit=dev` for the runtime layer, non-root `node` user; `.dockerignore` keeps tests, docs and `.git` out.
- Single-maintainer packages on the production path: `hono`/`@hono/node-server` (yusukebe), `zod` (colinhacks), `jose` (panva), `ip-address` (beaugunderson), `citeproc` (fbennett + one). All are widely depended-on; only citeproc is dormant (last publish 2023-04-17), and it wraps a spec-driven library that changes when CSL does.
- Nothing in the tree ships a second runtime. The only thing approaching one — onnxruntime — is deliberately kept out (finding 6).

## What I could not check, and why

- **Whether the musl binaries actually land in the published Docker image** (finding 4). Inferred from the same lockfile mechanism that produces the documented 57 MB Linux bundle; pulling `ghcr.io/oscardvs/zoteus:1.16.0` was outside the read-only scope. One `docker run … ls node_modules/@napi-rs` settles it.
- **The compressed share of the musl binaries in `zoteus-linux.mcpb`.** The 18 MB figure is derived from unpacked sizes and a uniform-compression assumption; `unzip -lv zoteus-linux.mcpb | grep musl` on the release asset gives the real number.
- **Whether `npm ≥ 11` records `libc` in lockfiles.** My positive control only shows npm 10.9.8 does not. If a newer npm does, regenerating the lockfile might make `npm ci` filter musl on its own; the `--libc=glibc` flag works either way.
- **Runtime reachability of hono was established by static import scanning** of SDK 1.29.0's 58 non-example ESM files via the CDN, not by loading the SDK — a dynamic `import('hono/…')` inside a function body would not show up. I saw none in `streamableHttp.js`, but I did not read every function body of every file.
- **Claude Desktop's Node version** is taken from Zoteus's own record of Electron 42.10.0 plus Electron's release page (Node 24.18.1). Whether Claude Desktop pins that Electron on every OS, and whether it honours `runtimes.node` at install time, I could not observe; the docs' "built-in node is compatible" log line suggests it checks.
- **No `node_modules` was installed**, per the constraints, so nothing here is a runtime measurement: no bundle was built, no test was run, `npm ls` was not available. Every count comes from `package-lock.json`, every version and size from `npm view`, every advisory from `npm audit --package-lock-only`.
- Commands run against the registry are read-only. The audit JSON is saved at `../audit-v1.16.0.json` beside the target, and the transformers-tree lockfile and audit at `../transformers-audit/`, both in the scratchpad.
