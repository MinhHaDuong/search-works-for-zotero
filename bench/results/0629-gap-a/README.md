# Gap A — what the four DNS lookups under R10-no-egress were

Ticket 0629, a child of tracker 0613 (goal 1). Read against
`bench/results/0604-ladder-matrix/acceptance-zoteus-v1130.json`, the current
zoteus column, whose `R10-no-egress` subject arm recorded
`{"off_machine": 0, "dns": 4}` — four `connect(127.0.0.53:53)` — and which
0613 left open with the question "whether the update check accounts for all
four lookups."

**Finding: it does. All four are one name lookup, not four.** One
`getaddrinfo` costs exactly four resolver-port connects on this machine under
the harness's no-route sandbox, and zoteus's startup path in the acceptance
configuration contains exactly one hostname to resolve.

This directory is an **ungraded diagnostic**. `R10-no-egress`'s verdict stays
bound to the default configuration and is unchanged: still `fail`, for the
reason it already gave — `ZOTEUS_UPDATE_CHECK` defaults `true`.

## 1. Every network-shaped call reachable from startup

Read from a real `fork/` built at the reviewed SHA
`b0e0bc872b5727d21ea83aba8bfe834293013264` (`UPSTREAM`, v1.13.0 + 4), not from
a fetched copy. Line numbers below are that tree's.

| site | destination | resolves a name? | reached in this run? |
|---|---|---|---|
| `src/lib/update-check.ts:93` (`fetchImpl(RELEASES_LATEST_URL)`, URL at `:5`) | `api.github.com` | **yes** | **yes** |
| `src/router/capabilities.ts:40` (`web.keysCurrent()`) | `api.zotero.org` (`src/api/web-client.ts:70`) | yes | no — guarded by `deps.web.hasKey`, and the run's own log line reads `Capabilities: cloud=none` |
| `src/router/capabilities.ts:55-56` (desktop probe, up to 3 attempts) | `http://127.0.0.1:<port>` (`src/api/local-client.ts:57`) | no — IP literal | yes, 3 times, and costs no lookup |
| `src/api/connector-writes.ts:40`, `src/api/local-writes.ts:78` | `http://127.0.0.1:<port>` | no — IP literal | constructed at startup, no I/O until a write |
| `src/features/citation/styles.ts:26-27`, `src/features/attachments/store.ts:92`, `src/api/web-client.ts` (all others), `src/features/scholar/*` | various | yes | no — all behind a tool call, none on the startup path |

The update check is wired at `src/server.ts:184-190` (`new UpdateChecker({… enabled: config.updateCheck})`, then `void ctx.updates.start()`), gated on
`ZOTEUS_UPDATE_CHECK` (`src/config.ts:237` declares it `bool(true)`, `:408`
carries it into the config). `update-check.ts` does one unauthenticated GET,
no retry and no redirect chain (`:93-102`), with a 24 h cache (`:8`, `:82`).

**The embedder does not resolve anything here.** `createEmbeddingProvider`
loads `@huggingface/transformers` from the local `ZOTEUS_TRANSFORMERS_PATH`;
the run's counts below leave no residual for it to explain, so the absence of
`HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` in `src/config.ts` did not cost a
lookup on this path. That is a statement about this configuration and this
run, not about a build path that reaches for weights it does not have.

## 2. One lookup, four syscalls — measured

`bench/probe_getaddrinfo_shape.py` → `syscall-shape.json`, run on this machine
through the acceptance layer's own tracer and sandbox
(`bench/acceptance/sandbox.py`), three programs × two arms:

| program | isolated (no route) | net-shared |
|---|---|---|
| `nothing` (null arm) | `off_machine 0, dns 0` | `off_machine 0, dns 0` |
| `numeric_connect_only` (control) | `off_machine 1, dns 0` | `off_machine 1, dns 0` |
| `one_getaddrinfo` | `off_machine 0, **dns 4**` | `off_machine 0, **dns 3**` |

The null arm is what makes four a signal rather than tracer noise; the numeric
connect is the arm that could have come out the other way, and did not — a
socket touched without a name resolved costs zero resolver connects. So the
four are per-lookup, and they are glibc's, not the application's.

Both numbers match the v1130 artifact exactly, on both arms: subject
`dns: 4` under isolation, net-shared control `dns: 3`. The artifact's own
positive control (`_EGRESS_PROBE` in `bench/acceptance/assertions.py:993`,
one `create_connection` to a numeric address plus one `getaddrinfo`) recorded
`dns: 4` isolated and `dns: 3` shared in that same run — the same signature,
from a program that makes exactly one lookup.

**Two runs, not three, and on two different sandboxes.** The v1130 subject arm
and its `_EGRESS_PROBE` control are one run and one apparatus, so they are two
readings rather than two independent ones. And this probe did **not** run on
that apparatus: `syscall-shape.json` records `"mechanism": "podman-unshare"`,
where v1130 used `bwrap`. `sandbox.choose()` prefers `bwrap` and fell through
because it cannot start inside this executor's own sandbox
(`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` — a nested
namespace refusing to configure loopback), so the fallback mechanism was
taken. That the two mechanisms produce identical counts is a stronger reading
than a single-apparatus repeat, not a weaker one — but it is a fact about the
evidence and belongs stated rather than discovered.

**The 4-vs-3 split is explained, from the traces, not waved at.** With a route,
the three connects each succeed and each is followed by a `sendmmsg` carrying
an A and an AAAA query — for the bare `example.invalid` first (glibc tries the
unqualified name before the search list, since it already has a dot and
`ndots` defaults to 1), then `example.invalid.localdomain`, then
`example.invalid.netbird.cloud`: one connect for the bare name, then one per
entry of this machine's two-entry `resolv.conf` search list. Without a route,
all four connects fail `ENETUNREACH` and **no query is ever sent**, so the
isolated arm is walking a failure-retry ladder rather than the search list;
why that ladder stops at four exactly is not established here, and does not
need to be. Two consequences worth carrying: the absolute count is a property
of this machine's resolver configuration, not a constant, and the isolated
and shared counts are not the same quantity — which is why the comparison
that matters is subject-versus-control **within** an arm, exactly as the
assertion already
does it.

**And that reading is checkable from the record.** It was first written off
strace output this directory does not keep — a trace carries this machine's
paths and pids — which left every claim in the paragraph above unverifiable
from what is committed: `attempts` carries an address and a port, no errno, no
send. Each arm now carries a `resolver_shape` block beside its counts:

| arm | `connect_outcomes` | `query_messages_sent` |
|---|---|---|
| `one_getaddrinfo/isolated` | `{"ENETUNREACH": 4}` | 0 |
| `one_getaddrinfo/net_shared` | `{"ok": 3}` | 6 |

Six messages over three connects is the A and the AAAA on each. Zero against
four is what makes the isolated arm a different quantity rather than a smaller
one. Query payloads are counted and never transcribed there — they carry the
search-domain configuration named above, and the artifact is read by tooling
that has no reason to hold it.

**The hypothesis 0629 logged holds.** Four lookups need no second cause:
zoteus's one `fetch()` accounts for all of them.

## 3. The confirming arm still did not run — and the reason changed

The ticket's Action 2 (`ZOTEUS_UPDATE_CHECK=false`, expected `dns: 0`) is the
direct confirmation. **2026-09-04 update:** `/etc/sudoers.d/acceptance-tester`
now exists — the remedy this section originally asked for — and
`posture._works('tester')` genuinely succeeds when called directly. The
confirming arm was re-run twice (once alongside a same-session default-config
comparison, per the ticket's own Test discipline) and still reports
`R10-no-egress` as `not-run`, both artifacts committed:
`acceptance-zoteus-update-check-default-comparison.json` and
`acceptance-zoteus-update-check-false.json`.

**The blocker moved, from a missing file to a structural composition
conflict, diagnosed and filed as ticket 0633.** `check_no_egress` runs the
posture-wrapped spawn (`sudo -n -u tester …`) *inside* the sandbox's
`podman-unshare` namespace, not outside it. Reproduced directly:

```bash
$ podman unshare unshare -n sudo -n -u tester -- true
sudo: /etc/sudo.conf is owned by uid 65534, should be 0
sudo: ouverture de /etc/sudoers impossible: Permission non accordée
$ echo $?
1
```

Inside a rootless user namespace the invoking user maps to uid 0 *only within
that namespace*; a file really owned by host root — `/etc/sudo.conf`,
`/etc/sudoers` — appears owned by the overflow uid (65534) from inside it, so
`sudo`, a setuid-root binary, refuses to run. This is a property of how
unprivileged user namespaces work, not a sudoers misconfiguration, and it
fires identically on the net-shared control invocation (not specific to
`--unshare-net`). It also explains a second observation: even the
**default-configuration** comparison run now reads `R10-no-egress` as
`not-run` rather than the `fail` the 2026-09-03 matrix recorded — the matrix's
`acceptance-zoteus-v1130.json` predates ticket 0625's account-posture gate
entirely (commit `d3b299c` at 15:44 versus the posture commit `f89a2bc` at
16:15 the same day), so nothing before today exercised this exact
composition. Full argument and next steps: ticket 0633.

Both controls fire correctly in both new artifacts — `off_machine`/`dns`
counts present, matching the shape `syscall-shape.json` already established —
so the tracer and the sandbox mechanism are not in question; only the
account-posture spawn inside that mechanism is.

**What this changes about the finding: still less than it looks, for the same
reason as before, plus one more data point in the same direction.** The
attribution in §1–§2 rests on the source read and the discriminating
syscall-shape measurement, neither of which the confirming arm was ever going
to add to — it was always going to *corroborate*, not establish, the
attribution. It still has not run to completion, so it corroborates nothing
new; what it does add is that the account-posture layer itself (not gap A's
subject) is what is blocked now, which is a finding about the harness's own
composition, not about zoteus.

**Source re-verification, 2026-09-04:** `fork/` rebuilt at
`UPSTREAM_REVIEWED_SHA` `b0e0bc8` (`UPSTREAM`, unmoved since this ticket
closed its first pass). Every file:line citation in §1 was re-read from that
real build and matches exactly, with one two-line drift: the desktop-probe
loop in `src/router/capabilities.ts` starts at `:53`, not `:55-56` as
originally logged — non-load-bearing (still three attempts against an IP
literal, no name resolution). `src/lib/update-check.ts:5`/`:93`,
`src/config.ts:237`/`:408`, and `src/server.ts:184-190` all confirmed
unchanged.

## Files

- `syscall-shape.json` — the measurement, six arms, produced by
  `bench/probe_getaddrinfo_shape.py`.
- `acceptance-zoteus-update-check-default-comparison.json` —
  same-session, same-machine, same-build companion to the `false` arm below;
  default configuration (`ZOTEUS_UPDATE_CHECK` unset), taken 2026-09-04.
  `R10-no-egress` reads `not-run` (see §3), both controls fire.
- `acceptance-zoteus-update-check-false.json` — the ticket's Action 2 arm,
  `ZOTEUS_UPDATE_CHECK=false`, taken immediately after the comparison run
  above. `R10-no-egress` reads `not-run` for the same reason (see §3), both
  controls fire; this is not the `dns: 0` confirmation the ticket asked for —
  ticket 0633 tracks why not.
- `traces/` is git-ignored (`.gitignore`); re-run the probe to regenerate it.
- `tests/test_probe_getaddrinfo_shape.py` fails if the artifact loses its null
  arm or its discriminating control, or if the getaddrinfo count stops
  matching the subject arm it explains. It reads the **committed artifact** and
  never re-invokes the probe, deliberately: the measurement needs a sandbox and
  a tracer that a test tier cannot assume. So it guards the record against
  being emptied or contradicted, and cannot detect the machine drifting
  underneath it — the probe has to be re-run by hand for that.
