# Can a hosted server spawn a child, and as what — ticket 0576, portable arm

Run: 2026-09-02, on `doudou` (Linux 7.0.0-30-generic, x86-64).
Probe sources: `verification/probes/electron-spawn/`.
Raw artifacts: `verification/probes/electron-spawn/results-2026-09-02/`.
Electron **44.1.1** (Chromium 152.0.7977.65, embedded Node 24.19.0), installed
from `electron@latest` at run time. Host Node for the control: **v22.23.1**.

## What this report settles, and what it does not

Ticket 0576 lists five things to measure. This run answers **item 1** for both
hosts and **items 2, 3 and 4** for the Electron runtime. It does **not** answer
**item 5** — whether the child survives the host's own lifecycle events, and
what the host does to it on quit — because item 5 is Claude Desktop's behaviour,
not Electron's, and no Claude Desktop is installed on either machine here.

The harness reproduces one property of the host population: that the server runs
inside an Electron `UtilityProcess` on Electron's embedded Node rather than as
its own program. Upstream established that shape by detecting the host through
`UtilityProcess` (`src/features/search/electron.ts`, read in
`verification/UPSTREAM-1.12.0-REREAD.md`). The harness reproduces nothing else:
not Desktop's packaging, not its extension lifecycle, not its shutdown sequence.
That it really did reach the shape it claims is recorded rather than asserted —
the payload reports its own `process.type` as `utility`.

## The binding arm is NOT-RUN. That is not a negative finding

The binding arm needs a real Claude Desktop install on macOS or Windows, the two
platforms `SPEC.md` §6 names. Re-checked at the start of this run:
`/home/haduong/.config/Claude` does not exist. `padme`, the other machine
available tonight, is a headless Linux box with no Claude Desktop either.

So the binding arm is **not-run**, and nothing below is evidence about what
Claude Desktop does. The one experiment that would settle it is named at the end.

## The positive control fired first

Under standalone Node v22.23.1, with the identical payload file:

| arm | spawned | child announced itself | outlived the call | duplex PING/PONG | child `process.type` |
|---|---|---|---|---|---|
| `execPath-plain` | yes | yes | yes | 3/3 | absent (Node) |
| `execPath-run-as-node` | yes | yes | yes | 3/3 | absent (Node) |
| `path-node` | yes | yes | yes | 3/3 | absent (Node) |

The host was then `SIGKILL`ed with a child still running. The child observed
`stdin` end and wrote its marker: `{"how":"stdin-end", …}`. So the orphan-repair
signal `SPEC.md` §5.2.5 depends on works where it must.

Order matters here. A probe that cannot spawn anywhere is measuring its own
harness, and its negative would be indistinguishable from "I could not look".
Only because every control arm is green may anything below be read as a finding.

## Electron `UtilityProcess`, arm by arm

Host: `process.type === 'utility'`, `process.versions.electron === '44.1.1'`,
`process.execPath` = the Electron binary. No `ELECTRON_RUN_AS_NODE` inherited.

| arm | spawned | announced | outlived | duplex | child `process.type` | child runtime |
|---|---|---|---|---|---|---|
| `execPath-plain` | yes (pid returned) | **no** | no | — | — | died `SIGTRAP` |
| `execPath-plain-no-sandbox` | yes | yes | yes | 0/3 (3/3 in a second run) | **`browser`** | Electron 44.1.1 |
| `execPath-run-as-node` | yes | yes | yes | **3/3** | absent | Node 24.19.0, `versions.electron` 44.1.1 |
| `path-node` | yes | yes | yes | 3/3 | absent | Node 22.23.1 |

**Item 1 — spawn works.** `child_process.spawn` from inside a `UtilityProcess`
returns a pid in every arm, and the child outlives the call in every arm that
gets past process startup.

**Item 2 — `process.execPath` is the Electron binary, and a child started from
it is Electron, not Node.** The plain arm's first result was a confound and is
reported as one: the child died at
`sandbox/linux/suid/client/setuid_sandbox_host.cc:166` because Chromium's SUID
helper is not setuid root on this box
(`kernel.apparmor_restrict_unprivileged_userns=1`, the same refusal that made
`unshare -rn` unusable for the egress probe). "Died at the sandbox check" is not
"launched a GUI", so a disconfounding arm was added that passes `--no-sandbox`
to the child. With that one flag the child starts and announces
`process.type === 'browser'` — Electron's **main-process** runtime. The hazard
`DECISIONS.md` 2026-09-02 states in one line is confirmed at the runtime level.

`process.versions.electron` **cannot** tell these apart: it is `44.1.1` in the
run-as-node child too. `process.type` is the discriminator — `browser` for the
GUI runtime, absent under `ELECTRON_RUN_AS_NODE`. A test that gates on
`versions.electron` would pass while launching the wrong runtime.

Nor does a working pipe discriminate. The `browser` child answered 3 of 3 PINGs
in one run and 0 of 3 in another, so "the stdio pipe worked" is not evidence the
child is a Node process, and the variability is itself a reason not to ship that
path.

**Item 3 — `ELECTRON_RUN_AS_NODE=1` is necessary and, here, sufficient.**
Necessary: without it the same command line yields the GUI runtime. Sufficient:
with it, on this harness, the child is a plain Node 24.19.0 process, outlives the
call, and speaks full duplex. The recipe, verbatim:

    spawn(process.execPath, [entryPoint], {
      env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' },
      stdio: ['pipe', 'pipe', 'pipe'],
    })

Scope: Electron 44.1.1 on Linux. Sufficiency is asserted for this harness, not
for Claude Desktop, which may add packaging, entitlements or a seatbelt profile
of its own.

`path-node` also worked, but only because this workstation has Node 22.23.1 on
`PATH`. Whether any `node` is on `PATH` inside Claude Desktop is unknown and is
not a thing to depend on.

**Item 4 — full duplex works, and stdin EOF reaches the child when the host
dies.** Under the ship recipe the parent's writes reached the child and the
child's replies came back, 3 rounds of 3. The orphan test then spawned a child
under that recipe and `SIGKILL`ed the Electron **main** process — not the
`UtilityProcess`, the app. The child observed `stdin` end within the 8 s window
and wrote `{"how":"stdin-end", …}`. So killing the app took the `UtilityProcess`
down with it and the orphan-repair signal arrived.

One honest wrinkle. In an earlier run the app kill produced no EOF and the
`UtilityProcess` had to be killed directly. That run had orphaned a **`browser`**
child, selected by a "first arm that answered" rule; the probe now spawns the
orphan under the recipe that would actually ship, and the earlier run is kept as
`results-2026-09-02/electron-run3.json`. The result under the ship recipe
reproduced; the result under the GUI arm did not, which is one more reason the
GUI arm is not a fallback.

**Item 5 — NOT ANSWERED.** Electron says nothing about what Claude Desktop does
to a child on quit. Do not read item 4's result as covering it: a `SIGKILL` of
the app process is not the same event as Desktop's own shutdown, which may reap
a process group, may close the extension gracefully first, or may leave the child
running.

## What this means for the decision rule

The ticket's decision rule has three branches. On the evidence here the second
one is the live candidate — "spawn works only under `ELECTRON_RUN_AS_NODE`" —
with the caveat that it is established for the Electron runtime and not for the
host population. Two consequences follow if it holds there too:

1. The environment becomes a stated part of both spawn paths (`SPEC.md` §5.2.5's
   conductor spawn and the embedding-service spawn of ticket 0575), with a test
   that fails when it is absent.
2. That test must gate on `process.type`, not on `process.versions.electron`,
   for the reason recorded under item 2.

0566 should not commit the boundary on this report alone. What is missing is
exactly item 5 and the confirmation of items 2–4 on the real host.

## Open question for the author

The one experiment nothing here can perform: run this same harness's payload
inside a real Claude Desktop on macOS or Windows, as a configured zoteus server,
and record the four items plus item 5. It needs a machine you have. Concretely:
point a Desktop MCP server entry at `probe-payload.mjs`, run it once, and send
back the JSON it writes — the payload writes its whole report to the path in
`ZOTEUS_PROBE_OUT` and needs nothing else.

Until that runs, the ruling this probe was filed to test stays untested on the
population that motivated it.
