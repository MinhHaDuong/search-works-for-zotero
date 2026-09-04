# Issue draft — ticket 0634, gap A of tracker 0613 (goal 1)

Measured 2026-09-04 at `oscardvs/zoteus` main tip `b0e0bc872b5727d21ea83aba8bfe834293013264`
(v1.13.0 + 4 commits — `UPSTREAM`), reproduced on a fresh `fork/` checkout at
that SHA built with `npm ci && npm run build`, and against the acceptance
harness's own no-egress detector (`bench/acceptance/assertions.py::
check_no_egress`, DNS-connect-counting `strace` under a no-route sandbox).

**Staged, not sent.** No per-action authorization has been given for this
filing; `GOVERNANCE.md`'s "Form follows the measured asymmetry" rules this a
design-sized item (an intentional, documented feature — not a bug with a
one-line fix), so the repo's convention is a drafted issue the author files
himself, never one the harness opens. Everything from `## Title` down is what
would go out verbatim; this preamble would not.

Form argued: a contained defect with a failing test goes as a pull request
(two precedents, #27 and #28, merged verbatim). This is not that — turning the
check off by default is a product decision about what "manual install" users
should expect, not a defect with one correct fix, so it goes as an issue
naming the behavior and the evidence, with the fix proposed rather than
demanded.

---

## Title

Update check phones home by default on every manual install, with no opt-in prompt

## Body

`ZOTEUS_UPDATE_CHECK` defaults to `true` (`src/config.ts:237`, `z.boolean` via
the local `bool(true)` helper, carried into the resolved config at `:408`).
Wired at startup in `src/server.ts:184-190`:

```ts
if (!perUser) {
  ctx.updates = new UpdateChecker({
    currentVersion: VERSION,
    dataDir: config.dataDir,
    logger,
    enabled: config.updateCheck,
  });
  void ctx.updates.start();
}
```

`UpdateChecker.start()` (`src/lib/update-check.ts:65-78`) does one
unauthenticated `GET` to
`https://api.github.com/repos/oscardvs/zoteus/releases/latest`
(`RELEASES_LATEST_URL`, `:5`; the request itself at `:93`), cached 24 h
(`:8`), 5 s timeout, no retry, no redirect chain. On a manual install (the
`.dxt`/MCP-config path most users are on, per the code comment at
`server.ts:186-187`: *"Manual installs … have no auto-update channel"*), this
fires on every session's first tool call with no prior notice and no opt-in
step — the operator finds out from the request itself, or from the log line
("Update available: Zoteus …"), not before it happens.

### Why this is being reported

We run an acceptance harness (a fork's worth of no-egress, uninstall, and
pause/resume checks against several local-first MCP servers, zoteus among
them) whose baseline rule is: *without an explicit opt-in, library text and
queries must not leave the machine, with the one-time model-weight download
the sole named exception.* The update check is a second, silent exception —
harmless in what it sends (no user data, no query text, no library content —
this issue is not reporting an information leak), but it does perform a
DNS lookup and an outbound HTTPS connection to a third party by default,
which our checklist treats as egress requiring consent.

### Evidence: one call, isolated and measured

Read from the built tree at the SHA above — the only network-shaped call
reachable from server startup in a default, no-cloud-key, local-embedder
configuration:

| site | destination | reached at startup? |
|---|---|---|
| `src/lib/update-check.ts:93` | `api.github.com` | **yes**, gated only on `ZOTEUS_UPDATE_CHECK` |
| `src/router/capabilities.ts:40` (`web.keysCurrent()`) | `api.zotero.org` | no — guarded by `deps.web.hasKey`; not reached with no cloud key configured |
| `src/router/capabilities.ts:53` (desktop probe, 3 attempts) | `127.0.0.1:<port>` | yes, but an IP literal — no name resolution, no egress |
| local embedder (`@huggingface/transformers`, local `ZOTEUS_TRANSFORMERS_PATH`) | — | no residual lookup observed on this path |

Our detector counts DNS-resolver connects under a namespace with no route
out; the update check's one call produces a small fixed number of resolver
syscalls per lookup (glibc's retry/search-list behavior on this machine, not
an application-level detail), and turning the flag off removes the signal
from that count entirely in the configuration we tested it in. We are not
asking you to trust a black-box scan: the file:line citations above are the
whole causal chain, and the fixed line-number drift we hit while re-deriving
them (`capabilities.ts:55-56` reads `:53` at this SHA — three lines earlier)
is exactly the kind of thing a second pair of eyes on the same source will
also see, and does not change which calls exist.

### What we are asking

Not that the check be removed — the maintainer comment at `server.ts:186-187`
gives a real reason for it (manually installed builds, notably the `.dxt`,
have no other update channel), and the failure mode is already the right
shape: every path degrades to "no notice" (the `catch` blocks in
`update-check.ts`), never breaking the server. The ask is only about the
*default*, for the class of user this project's threat model already singles
out — someone who explicitly runs zoteus against their own Zotero library.

Two shapes that would satisfy our checklist, roughly in order of how little
they change:

1. **Default `ZOTEUS_UPDATE_CHECK` to `false`**, and mention it once in the
   README/setup docs as an opt-in for users who want the notice. Simplest,
   changes one line plus documentation; the tradeoff is fewer users ever
   hearing about a new release.
2. **Ask once, on first run** (a first-run flag written beside
   `update-check.json` in `dataDir`), and honor whatever the user answers
   from then on, same as many CLIs handle telemetry/update-check consent.
   More work, keeps the notice reaching people who want it, without it being
   silent on install one.

We would lean toward (1) for a server with no interactive install step to
hang a prompt on, but the tradeoff is yours to weigh. Happy to open a PR for
whichever shape you'd rather take, if that's useful.
