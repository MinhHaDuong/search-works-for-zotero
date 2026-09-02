# Issue draft — ticket 0530, upstream tsconfig excludes tests

Measured 2026-09-02 at `oscardvs/zoteus` v1.12.0 (`b05ed69`), reproduced on the
fork branch `base-v1.12.0`, TypeScript 5.9.3, vitest 2.1.9, dependencies from
`npm ci` on the committed lockfile.

**Not filed.** Held for the author's per-action authorization. Form ruled by
the measurement (`SPEC.md` §4, GOVERNANCE.md "Form follows the measured
asymmetry"): **issue, not pull request** — 204 errors across 37 of 101 test
files, no one-line fix exists, and one category asks a question about
`src/features/search/backend.ts` that is the maintainer's to answer.

---

## Title

`typecheck` never sees `tests/` — the gate is green on 15.7k lines it does not compile

## Body

`npm run typecheck` is one of the three gates `CONTRIBUTING.md:33` asks
contributors to keep green, and it runs in CI (`.github/workflows/ci.yml:23`)
and on the deploy path (`.github/workflows/deploy.yml:15`). It never
type-checks the test suite: 100 test files, 15,754 lines at v1.12.0
(`b05ed69`). A test that imports a symbol which no longer exists passes all
three gates.

### The seam

```jsonc
// tsconfig.json
"rootDir": "src",                                    // line 8
"include": ["src/**/*"],                             // line 18
"exclude": ["node_modules", "dist", "tests"]         // line 19
```

```jsonc
// package.json
"typecheck": "tsc --noEmit",                         // line 44 — resolves ./tsconfig.json
```

`vitest.config.ts:7` runs `tests/**/*.test.ts`. The compiler and the runner
have disjoint file sets.

### Positive control, both directions

Planting a rename-style ghost import in `tests/config.test.ts`:

```ts
import { loadConfig, aGhostSymbolThatDoesNotExist } from '../src/config.js';
const ghostProbe: number = aGhostSymbolThatDoesNotExist;
const deliberateTypeError: number = loadConfig({} as NodeJS.ProcessEnv).libraryType;
```

`npm run typecheck` — exit **0**, no output, identical to a clean tree.
`npm test` — `✓ tests/config.test.ts (28 tests)`, all green.

Vitest does not catch it because under the SSR transform a missing export is
`undefined` rather than an import-time throw (`typeof ghost = undefined`), so
it only fails if the symbol is *called*. A renamed type, or a symbol read but
not invoked, can stay broken indefinitely.

Compiling the same tree with tests included, nothing else changed:

```
tests/config.test.ts(2,22): error TS2305: Module '"../src/config.js"' has no exported member 'aGhostSymbolThatDoesNotExist'.
tests/config.test.ts(6,7): error TS2322: Type 'string' is not assignable to type 'number'.
```

### Why the obvious one-liner will not do it

`include` and `exclude` each block tests independently, and `rootDir` blocks
the naive combination:

| change | test files compiled | `tsc --noEmit` |
|---|---|---|
| as-is | 0 | exit 0 |
| remove `"tests"` from `exclude` | **0** | exit 0 |
| add `"tests/**/*"` to `include` | **0** | exit 0 |
| both, `rootDir: "src"` kept | 201 | exit 2, **100 × TS6059** |

The last row reports `File '…/tests/api/attachments.test.ts' is not under
'rootDir' '…/src'` once per test file and no type errors at all — and under
`npm run build`, which emits, it scatters `.js`/`.d.ts`/`.js.map` next to the
test sources.

### Blast radius

With a scratch config (`extends ./tsconfig.json`, `rootDir: "."`, `noEmit`,
`include: ["src/**/*", "tests/**/*"]`):

- **204 errors across 37 of 101 test files. Zero in `src/`.** The suite is
  green at runtime: 923 passing, 7 skipped.
- **115 of the 204** disappear with `noUncheckedIndexedAccess: false` — that
  flag alone accounts for 18 of the 37 files. e.g.
  `tests/features/search.test.ts(139,12): TS18048: 'firstWord' is possibly
  'undefined'` on `…split(' ')[0]`, where an undefined index throwing *is* the
  assertion.
- **53** are untyped JSON and loosely-typed mocks: `TS18046: 'meta' is of type
  'unknown'` on `await res.json()`
  (`tests/integration/cimd-metadata.test.ts:32`); `TS2493: Tuple type '[]' …
  has no element at index '0'` on `fetchImpl.mock.calls[0]!`
  (`tests/api/bbt-client.test.ts:23`).
- **5 are genuine drift**, the class this issue is about.
  `tests/integration/array-fields-write.test.ts(33,5): TS2741: Property
  'localGroupIds' is missing in type '{ cloud: any; localApi: false; }' but
  required in type 'Capabilities'`. `Capabilities.localGroupIds`
  (`src/router/capabilities.ts:14`) arrived in `116b4aa`; four fixtures
  explicitly annotated `: ToolContext` / `: Capabilities` were never updated.
  Same at `tests/integration/deferred-startup.test.ts(12,3)` for
  `ToolContext.reopenSearchIndex`.
- **10 point back at `src`**: `TS2339: Property 'loadFromJSON' does not exist
  on type 'SearchIndex'` (`tests/features/embedding-config.test.ts:354` and
  five more; `tests/features/index-truncation.test.ts:111,122`).
  `toJSON`/`loadFromJSON` live on the class
  (`src/features/search/index-manager.ts:2104,2131`) and on
  `src/features/search/persistence.ts:8-9`, but not on the `SearchIndex`
  interface (`src/features/search/backend.ts:524`). Your call which side moves.
- Remainder: express vs node `Response` (`tests/auth/provider.test.ts:335`),
  `FetchLike` optional-`init` variance (`tests/api/local-writes.test.ts:15`).

No new dependencies are needed: zero `TS2307`/`TS2304`/`TS2582`. `vitest`
ships types and `@types/node@^22` is already present.

### Proposed fix

A test-only project rather than widening the build project, so `npm run build`
keeps its `rootDir`/emit contract:

```jsonc
// tsconfig.test.json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "rootDir": ".",
    "noEmit": true,
    "declaration": false,
    "noUncheckedIndexedAccess": false   // optional; drops 115 of 204
  },
  "include": ["src/**/*", "tests/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

```jsonc
// package.json
"typecheck:tests": "tsc -p tsconfig.test.json",
```

plus a step after `npm run typecheck` in `ci.yml` and `deploy.yml`, and a line
in `CONTRIBUTING.md:33`.

Since the suite is not clean today, landing it as a blocking gate means a
37-file (or 19-file) cleanup in the same change. A ratchet may suit better: add
the script and a **non-blocking** CI step now; fix the 15 errors in the two
categories that are real drift (`localGroupIds`, `reopenSearchIndex`, the
`SearchIndex` persistence methods); then work down the mechanical ones and flip
the step to blocking.

Happy to send the config-and-script part as a PR if useful — the cleanup and
the `SearchIndex` question felt like yours to decide, which is why this is an
issue rather than a patch.
