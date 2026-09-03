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
from a program that makes exactly one lookup. Three independent readings of
the same shape.

**The hypothesis 0629 logged holds.** Four lookups need no second cause:
zoteus's one `fetch()` accounts for all of them.

## 3. The confirming arm did not run — machine, not code

The ticket's Action 2 (`ZOTEUS_UPDATE_CHECK=false`, expected `dns: 0`) is the
direct confirmation and is **not** in this directory. Every assertion that
starts a target process reported `not-run` on this machine:

> `PostureUnavailable: 'tester' exists but a run under it did not succeed here
> (checked by running a trivial command under it, not by looking the account
> up). The sudoers rule the recipe asks for is likely missing or
> misconfigured.`

That is correct behaviour, not a harness defect: the account posture ratified
in `DECISIONS.md` on 2026-09-03 (ticket 0625) refuses to run a target as the
operator. `/etc/sudoers.d/acceptance-tester` does not exist here; what
`sudo -l` shows is a `(tester) NOPASSWD: ALL` line **without** the `SETENV`
tag `bench/acceptance/posture.py:48` requires, and shadowed by a later
`(ALL : ALL) ALL`, so `sudo -n -u tester /bin/true` asks for a password. The
v1130 artifact predates the gate — its commit `d3b299c` is 15:44, the posture
commit `f89a2bc` is 16:15 the same day — which is why that run decided a
clause this one cannot.

The remedy is one line, and needs root:

```bash
echo "haduong ALL=(tester) NOPASSWD:SETENV: ALL" | sudo tee /etc/sudoers.d/acceptance-tester
```

With that in place, the arm the ticket specifies runs unchanged:

```bash
ZOTEUS_UPDATE_CHECK=false python3 bench/acceptance/run.py \
  --adapter zoteus --arena "$ARENA" \
  --adapter-option entrypoint=fork/dist/index.js \
  --adapter-option transformers_path="$ZOTEUS_TRANSFORMERS_PATH" \
  --output bench/results/0629-gap-a/acceptance-zoteus-update-check-false.json
```

`bench/acceptance/adapters/zoteus.py::Zoteus._env()` never sets or strips
`ZOTEUS_UPDATE_CHECK` and `bench/mcp_drive.py::Server.__init__` merges
`{**os.environ, **env}`, so exporting it in the invoking shell is sufficient —
including under `--posture account`, whose `--preserve-env=` list is built
from that merged dict.

**What this changes about the finding: less than it looks.** The attribution
above rests on a measurement that was made here, with a null arm and a
discriminating control, and on a source read of the reviewed tree — not on the
missing arm. What the missing arm would add is a fourth reading of the same
shape from the other direction: `dns` falling to 0 when the one lookup is
switched off. Nothing in §1 or §2 depends on it, and it should still be run
when the machine allows, because a prediction that cheap deserves to be
checked rather than assumed.

## Files

- `syscall-shape.json` — the measurement, six arms, produced by
  `bench/probe_getaddrinfo_shape.py`.
- `traces/` is not committed; re-run the probe to regenerate it.
- `tests/test_probe_getaddrinfo_shape.py` fails if the artifact loses its null
  arm or its discriminating control, or if the getaddrinfo count stops
  matching the subject arm it explains.
