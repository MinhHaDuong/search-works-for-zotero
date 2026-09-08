Revalidated against the release recipe on `main` at `5a81cee88be6d979e9ca1e99e897b6b6df25beef`. The distinction here is packaging evidence versus native runtime verification: I have a Linux reproduction and cross-platform loader simulations, not a native Windows/macOS smoke result.

### Reproduction and actual behavior

The release job runs on `ubuntu-latest` and stages production dependencies using:

```sh
npm ci --omit=dev --ignore-scripts --no-audit --no-fund
```

It then packs that installed tree into one `zoteus.mcpb`. The manifest advertises `darwin`, `win32`, and `linux`. The PDF dependency chain is `pdfjs-dist` → `@napi-rs/canvas` → platform-specific native canvas packages. Inspection of the published [v1.15.0 archive](https://github.com/oscardvs/zoteus/releases/download/v1.15.0/zoteus.mcpb) confirms it contains only `@napi-rs/canvas-linux-x64-gnu` and `@napi-rs/canvas-linux-x64-musl` native canvas packages. Windows/macOS binaries are absent; entries in the lockfile do not put those binaries into the archive. The downloaded archive SHA-256 is `c53a0dc4161b9b5a3e9b9bbed470346a950d10f1f07d3cd1f2ddb80078aa6f14`.

A minimal one-page PDF containing “Hello PDF” extracts successfully on Linux. In fresh Node processes against the extracted release dependency tree, selecting the Windows or macOS native-loader branch fails to load canvas, then importing `pdfjs-dist/legacy/build/pdf.mjs` fails with `ReferenceError: DOMMatrix is not defined`. These are loader simulations on Linux, not native host runs. Zoteus's `extractPdfPages()` catches the import failure and returns `null`, so exact-page extraction degrades; attachment-byte extraction paths using the same dependency are also affected. This does not imply every full-text read fails: Zotero's existing text cache is a separate path.

### Expected behavior

The shipped bundle should contain working PDF dependencies for every advertised platform, or advertise only the platform support actually packaged and verified.

### Smallest fix shape

Assemble the supported native dependencies explicitly, or publish platform-specific bundles if the bundle distribution supports that. Include architecture coverage as well as OS coverage. A platform-specific install on the release builder is insufficient evidence for a cross-platform artifact.

Relevant code: [.github/workflows/deploy.yml](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/.github/workflows/deploy.yml), [mcpb/manifest.json](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/mcpb/manifest.json), [package-lock.json](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/package-lock.json), [src/features/fulltext/pdf-pages.ts](https://github.com/oscardvs/zoteus/blob/5a81cee88be6d979e9ca1e99e897b6b6df25beef/src/features/fulltext/pdf-pages.ts).

### Acceptance criteria

- Inspect the final archive for the native packages required by each advertised target.
- Install the actual archive on native Windows and macOS hosts and extract a known page through Zoteus; retain Linux as a positive control.
- Test the shipped bundle without a separate development `node_modules` tree masking a missing dependency.
- If any target remains unverified or unsupported, make that limitation explicit in the advertised support.

Related: #29 added attachment extraction; #38 concerns transformer installation instructions, a different dependency and failure path.
