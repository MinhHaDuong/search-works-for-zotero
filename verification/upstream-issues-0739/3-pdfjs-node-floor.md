# `pdfjs-dist` is frozen on the last release that runs on Node 20.19, so the PDF parser is on a branch that can no longer be patched

Read on `main` at `910310b3979aaad9d314087ffd043eaf59eb023a` (the v1.16.0 release commit), with registry facts re-checked against npm on 2026-09-08. No `node_modules` was installed and nothing was executed; the version and engine facts below come from `npm view`, the advisory from `npm audit --package-lock-only` and the GitHub advisory page.

### Not a live vulnerability, and worth saying first

`npm audit` reports GHSA-hq66-cqwq-w95j against the pinned `pdfjs-dist` 5.6.205, high, affected `>=5.6.83 <6.2.108`. It is a viewer-scripting XSS: the advisory text is "if PDF.js is used to load a malicious PDF, and PDF.js is configured with `enableScripting` set to true (which is the default value) and no CSP for disallowing script-src, unrestricted attacker-controlled JavaScript will be executed in the context of the hosting domain", and its two mitigations are to set `enableScripting` to false or set a CSP.

Zoteus never builds a viewer. It calls `getDocument({ data, useSystemFonts: true, isEvalSupported: false })` and then `page.getTextContent()` ([pdf-pages.ts:32-38](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/fulltext/pdf-pages.ts#L32-L38), and the same shape at [:85](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/features/fulltext/pdf-pages.ts#L85) and in `pdf-locate.ts`). The advisory's precondition does not arise on that path. I did not run a proof-of-concept PDF through the extractor, so that is a reading of the code against the advisory text rather than a measurement, but I would not file this as a vulnerability and I am not asking you to treat it as one.

### The actual problem

`pdfjs-dist` 5.6.205 is the only release left that satisfies the declared `engines.node`, and the whole line above it is closed to you:

```
npm view pdfjs-dist@5.6.205 engines.node  →  >=20.19.0 || >=22.13.0 || >=24
npm view pdfjs-dist@5.7.284 engines.node  →  >=22.13.0 || >=24
npm view pdfjs-dist@6.2.108 engines.node  →  >=22.13.0 || >=24
npm view pdfjs-dist@6.3.289 engines.node  →  >=22.13.0 || >=24
```

`package.json` declares `engines.node: ">=20.19"` ([:33-35](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/package.json#L33-L35)) and `pdfjs-dist: "^5.6.205"` ([:76-78](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/package.json#L76-L78)). Every release since 5.6.205 (5.7.284, 6.0.227, 6.1.200, 6.2.108, 6.3.289) requires Node 22.13. So the current advisory cannot be patched without raising the floor, and neither can the next one. The parser is 38.9 MB of code that reads files which arrived from the open web through the user's library, and it is now on an orphaned branch.

There is a second, smaller edge on the same fact: the declared range `^5.6.205` admits 5.7.284. Any resolve that ignores the lockfile — `npm update`, a deleted lockfile, a downstream project depending on `@oscardvs/zoteus` and resolving its own tree — picks a release that breaks the Node 20 promise the CI matrix exists to defend ([ci.yml:13-15](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/.github/workflows/ci.yml#L13-L15), whose comment names this dependency as the reason 20 is in the matrix).

### The floor the code already wants

Four declarations disagree about the floor, and the code has half-moved already. `package.json` and `mcpb/manifest.json` say `>=20.19` ([manifest.json:133](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/mcpb/manifest.json#L133)); the CI matrix is `[20, 22]`; the Dockerfile is `node:22-bookworm-slim` at all three stages. Meanwhile the SQLite index backend needs Node 22.13 ([config.ts:59](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/config.ts#L59)), so does the usage log ([usage/index.ts:65](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/lib/usage/index.ts#L65)), and the docs tell users on large libraries to "Run on Node 22.13+ so the index goes to SQLite" ([docs/semantic-search.md:1022](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/docs/semantic-search.md#L1022)).

Claude Desktop runs Electron 42.10.0 by Zoteus's own record ([docs/semantic-search.md:413](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/docs/semantic-search.md#L413)), and that Electron bundles Node 24.18.1. Node 20 reached end of life on 2026-04-30. So the Node 20 promise costs the pdfjs freeze and buys support for a runtime that is out of maintenance and that the flagship client does not use.

### Smallest fix shape

Set `engines.node: ">=22.13"` in `package.json` and `runtimes.node` in `mcpb/manifest.json`, drop 20 from the CI matrix, and take `pdfjs-dist@^6.3.289`. That brings `@napi-rs/canvas` from `^0.1.96` to `^1.0.0`; 1.0.8 is current, publishes the same eleven platform packages, and its release notes state no breaking changes. The bundle gate follows automatically, because `requiredNativePackages` and the "at one version" assertion in `tests/scripts/mcpb-bundle.test.ts` read the lockfile rather than a hardcoded version.

If Node 20 has to stay, the honest alternative is to pin `pdfjs-dist` to exactly `5.6.205` with no caret, so nothing can drift into a release the engine floor forbids, and to record in `SECURITY.md` that the PDF parser is frozen. An explicit orphan is better than an accidental one.

### Acceptance criteria

- `npm audit --omit=dev` reports no advisory against `pdfjs-dist`, or `SECURITY.md` states why the branch is frozen.
- The three declarations of the floor (`package.json`, `mcpb/manifest.json`, the CI matrix) agree with each other and with what `config.ts` and `usage/index.ts` require.
- The `.mcpb` bundles still carry a working canvas binary for each advertised platform after the canvas major bump, checked with the existing bundle gate.
- Page-level extraction still returns the same text for a known PDF before and after the upgrade.

### What I did not check

I did not build against pdfjs 6.x, so I cannot say whether `getTextContent`'s output is byte-identical across the major. I did not pull the published Docker image. I did not run a proof-of-concept PDF through the extractor to confirm the CVE is unreachable, as said above.

Related: #62 is the packaging half of the same dependency (native canvas binaries per platform).
