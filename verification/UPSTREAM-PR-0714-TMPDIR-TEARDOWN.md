# Upstream PR draft — vitest globalSetup teardown for leaked temp directories (ticket 0714)

**Staged, not sent.** No branch was pushed anywhere — not to `MinhHaDuong/zoteus`, and not to
`oscardvs/zoteus` — and no `gh pr create` was run. This raid was told explicitly to stop before
submitting to upstream. What follows is the drafted, tested content that rides inside whichever
upstream PR is prepared next (per the repo's standing rule: this repository explores, designs,
and prepares the upstream contribution — it does not file standalone patches for a fix this small).

## The measurement

`ls /tmp` filled on 2026-09-06 (12 GB tmpfs, quota'd, per-user 80%) from names the shell history
attributes to the fork's own vitest suite: `mkdtempSync(join(tmpdir(), 'zoteus-<name>-'))` calls
with no matching `rmSync`, across (at last count) 22 test files in `fork-0091`
(`~/data/projets/zoteus-bench/fork-0091`, branch `pr3-droplist`).

Reproduced fresh, one `npx vitest run` against `fork-0091` under a private `TMPDIR`:

| leftover directories | size |
|---|---|
| 116 (115 `zoteus-*`, 1 `node-compile-cache` — pre-existing, unrelated to this leak) | 16 MB |

Matches the ticket's own table exactly. The suite reads the same either way, 949 passed and 7 skipped (invariant preserved by
every change below).

## The drafted fix

One new file, `tests/global-setup.ts`, wired into `vitest.config.ts`'s `test.globalSetup`. It
redirects `TMPDIR` to a fresh per-run directory before any test file runs, and removes that
directory — everything any test put under it, by construction — in the teardown vitest calls
after the run:

```ts
// tests/global-setup.ts
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export default function setup() {
  const root = mkdtempSync(join(tmpdir(), 'zoteus-test-run-'));
  const previousTmpdir = process.env.TMPDIR;
  process.env.TMPDIR = root;

  return () => {
    if (previousTmpdir === undefined) {
      delete process.env.TMPDIR;
    } else {
      process.env.TMPDIR = previousTmpdir;
    }
    rmSync(root, { recursive: true, force: true });
  };
}
```

```diff
   test: {
     environment: 'node',
     globals: false,
     include: ['tests/**/*.test.ts'],
+    globalSetup: ['./tests/global-setup.ts'],
   },
```

This catches every present and future `tmpdir()` caller without touching the 22 test files
themselves — the fix rides at the one place all of them already funnel through (`os.tmpdir()`
reads `TMPDIR`), which is the ticket's own proposed shape.

**Verified, not just written.** Applied to a disposable rsync copy of `fork-0091`
(`node_modules` symlinked in, `.git` excluded — the working checkout was never touched, git or
otherwise) and run against an empty external `TMPDIR`:

| | Test Files | Tests | leftover `zoteus-*` dirs after the run |
|---|---|---|---|
| unfixed | 100 passed, 2 skipped (102) | 949 passed, 7 skipped (956) | 115 |
| fixed | 100 passed, 2 skipped (102) | 949 passed, 7 skipped (956) | 0 |

Same pass/test counts both ways — the fix changes nothing about what the suite does, only where
its own scratch files land and whether they survive the run.

## What this does not do

It does not touch any of the 22 test files' own `mkdtempSync` calls — the ticket's own point is
that a single choke point catches all of them without a 22-file diff. It does not change
`TMPDIR` for anything outside the vitest process (the acceptance harness's own arena-scoped
`TMPDIR`, `bench/acceptance/adapters/zoteus.py`, is untouched and was already fine per the
ticket). It does not address `bench/smoke_upstream.py`'s own leak — that is this repo's own
code, fixed directly below, not an upstream filing.

---

## Title

fix(test): stop the vitest suite from leaking `mkdtempSync` directories

## Body

Every test file that calls `mkdtempSync(join(tmpdir(), 'zoteus-<name>-'))` leaves that directory
behind — nothing in the suite calls `rmSync` on it. One `npx vitest run` leaks 115 such
directories, 16 MB, with no bound: `tmpdir()` resolves to `/tmp` by default, and a CI runner or a
developer's workstation with `/tmp` on tmpfs fills real memory this way over repeated (watch-mode)
runs.

This adds a `globalSetup` (`tests/global-setup.ts`) that points `TMPDIR` at a fresh, per-run
directory before any test runs and removes it — and everything any test put under it — in the
returned teardown. Every current and future `tmpdir()`-based caller is covered without touching
the call sites themselves.

949 passed, 7 skipped, before and after; the only difference is that the scratch directories no longer
survive the run.
