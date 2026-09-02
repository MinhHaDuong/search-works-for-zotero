# Can a hosted server spawn a child, and as what — ticket 0576, portable arm

Run: 2026-09-02, on `doudou` (Linux 7.0.0-30-generic, x86-64).
Probe sources: `verification/probes/electron-spawn/`.
Raw artifacts: `verification/probes/electron-spawn/results-2026-09-02/`.
Electron **44.1.1** (Chromium 152.0.7977.65, embedded Node 24.19.0), installed
from `electron@latest` at run time. Host Node for the control: **v22.23.1**.

A sibling directory, `results-2026-09-02-recipe-check/`, holds a later run of the
author-facing recipe at the end of this report. It checks that the instructions
work as written. It is not a finding about any host.

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
and record the four items plus item 5. It needs a machine you have.

The payload is **not** self-sufficient, and an earlier draft of this section said
it was. It reads four environment variables, and the half of item 4 that the
topology actually depends on (does `stdin` EOF reach an orphaned child when the
host dies) needs a human action in the middle of the run, not just a variable.
Run it with `ZOTEUS_PROBE_OUT` alone and it answers items 1 to 3, spawns no
orphan, and says so in `orphan.note`. The full recipe follows.

### The environment the payload reads

| variable | who sets it | what it is for |
|---|---|---|
| `ZOTEUS_PROBE_OUT` | **you** | absolute path the report JSON is written to. Unset, the run leaves no trace at all. |
| `ZOTEUS_PROBE_ARMED_FILE` | **you** | absolute path the payload writes once it has spawned the orphan. It carries `hostPid`, which is what you kill. |
| `ZOTEUS_PROBE_EOF_FILE` | **you** | absolute path the orphan writes when its `stdin` closes. Its existence is item 4's second half. |
| `ZOTEUS_PROBE_HOST` | **you** | free-text label recorded in the report, e.g. `claude-desktop-macos-1.2.3`. Unset, the report says `unknown`. |
| `ZOTEUS_PROBE_CHILD_TTL_MS` | the payload | set on each child it spawns. Do not set it yourself. |
| `ZOTEUS_PROBE_HOST_FILE` | the Electron harness | read by `electron-main.mjs` only. Irrelevant when Desktop is the host. |

`ZOTEUS_PROBE_ARMED_FILE` and `ZOTEUS_PROBE_EOF_FILE` are needed **together**.
With either one missing the payload skips the orphan branch, and the report then
records `orphan.armed: false` with the winning arm named, so a skipped
measurement cannot be misread as a measured absence. Both branches of that note
were driven on 2026-09-02 and both artifacts are kept: omitting the two variables
gives `orphan-note-no-arm-vars.json`, where the note names
`execPath-run-as-node` as the arm that did win, and a control run against a
payload with no child script beside it gives
`orphan-note-no-winner-control.json`, the only case in which "no arm produced a
live child to orphan" is the true sentence.

### Step 0 — run the recipe on plain Node first (about 30 seconds)

This is the same positive control the probe runs, done by hand. It costs half a
minute and it tells you what a good result looks like before Desktop is in the
picture. From a clone of this repo:

    cd verification/probes/electron-spawn
    RUN=/tmp/zoteus-0576-recipe-check && mkdir -p "$RUN" && rm -f "$RUN"/*.json
    ZOTEUS_PROBE_HOST=standalone-node \
    ZOTEUS_PROBE_OUT="$RUN/report.json" \
    ZOTEUS_PROBE_ARMED_FILE="$RUN/armed.json" \
    ZOTEUS_PROBE_EOF_FILE="$RUN/eof.json" \
      node probe-payload.mjs &
    for i in $(seq 1 240); do [ -f "$RUN/armed.json" ] && break; sleep 0.25; done
    kill -KILL "$(node -e 'process.stdout.write(String(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).hostPid))' "$RUN/armed.json")"
    for i in $(seq 1 60); do [ -f "$RUN/eof.json" ] && break; sleep 0.25; done
    cat "$RUN/eof.json"; echo

A good run prints `{"how":"stdin-end", …}`. Verified on 2026-09-02 on `doudou`
under Node v22.23.1; the artifacts are in
`verification/probes/electron-spawn/results-2026-09-02-recipe-check/`, which is a
check that this recipe runs and not a new finding about any host.

### Step 1 — point Desktop at the payload

However zoteus itself is configured on that machine, point the same mechanism at
an absolute path to `probe-payload.mjs` and give it the four variables. In a
config that takes an `env` block, that is:

    "command": "node",
    "args": ["/absolute/path/to/probe-payload.mjs"],
    "env": {
      "ZOTEUS_PROBE_HOST": "claude-desktop-<os>-<version>",
      "ZOTEUS_PROBE_OUT": "/absolute/path/to/probe/report.json",
      "ZOTEUS_PROBE_ARMED_FILE": "/absolute/path/to/probe/armed.json",
      "ZOTEUS_PROBE_EOF_FILE": "/absolute/path/to/probe/eof.json"
    }

That snippet shows the shape, not the command. What the command has to be is
whatever launches zoteus on that machine, so that the payload runs where a real
server runs. If zoteus is installed as a Desktop extension, swapping its entry
point for `probe-payload.mjs` puts the payload inside the same `UtilityProcess`
and that is the arm this probe is missing. If the only form available is a plain
stdio server entry, the payload becomes an ordinary child of Desktop instead,
which is a different topology and still worth having, provided
`ZOTEUS_PROBE_HOST` says which one it was.

If the config form you use has no `env` block, put the four `export` lines in a
small wrapper script and `exec` the payload from it, so no extra process is
inserted between Desktop and the payload.

Two things to expect, neither of them a failure of the probe. The payload does
not speak MCP, so Desktop will report the server as failed or unresponsive once
the arms finish. And a client that restarts a failed server will start the whole
sequence again and overwrite the output files, so read them, or copy them, before
retrying.

### Step 2 — the human action item 4 needs

The payload arms the orphan, writes `armed.json`, then sleeps 40 seconds and
exits. The orphan's own TTL is 45 seconds. So the window is about 40 seconds
wide, it opens about 10 seconds after Desktop starts the server, and nothing
announces it. Measured here: 7 seconds from payload start to the orphan under
standalone Node with three arms, 10 seconds under Electron with four. Do not try
to catch that by watching a folder. Start this watcher in a terminal first, then
start Desktop:

    P=/absolute/path/to/probe
    for i in $(seq 1 1200); do [ -f "$P/armed.json" ] && break; sleep 0.25; done
    HOSTPID=$(node -e 'process.stdout.write(String(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).hostPid))' "$P/armed.json")
    echo "armed; host pid $HOSTPID"
    kill -KILL "$HOSTPID"
    for i in $(seq 1 60); do [ -f "$P/eof.json" ] && break; sleep 0.25; done
    cat "$P/eof.json" 2>/dev/null || echo "NO EOF within 15 s"

On Windows, the equivalents are `Test-Path` in a loop and
`Stop-Process -Id $HOSTPID -Force`.

`hostPid` is the process the payload itself runs in, which is the process Desktop
hosts the server in. Killing it reproduces "the process hosting the server died",
which is the event `SPEC.md` §5.2.5's orphan repair turns on. It is **not**
Desktop's own shutdown; that is step 3.

### Step 3 — the same run again, quitting Desktop instead (item 5)

Item 5 asks what the host does to the child on quit, and that is one action away
from step 2. Repeat the run with the `kill -KILL "$HOSTPID"` line deleted from
the watcher, so that it prints `armed` and then waits. Quit Claude Desktop from
its own menu at that moment. Then record two things: whether `eof.json` appeared,
and whether the orphan process named in `armed.json` as `orphanPid` is still
running afterwards (`ps -p <pid>` on macOS, `Get-Process -Id <pid>` on Windows).
A surviving orphan with no EOF is the case `SPEC.md` §5.2.5 has no answer for,
and it is worth reporting precisely.

The quit has to land inside the 40-second window. After it the payload has exited
on its own, and whatever you then observe is no longer the host's quit.

### What to send back

Per run, three files and three lines of prose:

- `report.json` — the whole of items 1, 2 and 3, plus `orphanRecipe` and the
  `orphan` object.
- `armed.json` — `hostPid` and `orphanPid`.
- `eof.json` — present or absent. Absent is a result; say which step it was
  absent from.

And in prose: which step the run was (2 or 3), the Claude Desktop version and OS
version, and whether Desktop's own log for that server shows it being killed
before the arms finished. That log is the only place a truncated run declares
itself.

### What this recipe returns, and what stays open

Steps 1 and 2 return items 1 to 4 for the real host. Step 3 returns item 5. If
Desktop terminates the server before `report.json` appears, that is itself the
answer to item 1 on that host, and it is worth sending back with the log rather
than being retried into silence.

Until those run, the ruling this probe was filed to test stays untested on the
population that motivated it.
