# 0793 — the stall probe and its controls

**This is not the AR6 run.** The AR6 run is still owed and only the author can
make it: the document lives at `~/data/Zotero-fresh/storage/AI6DJUTA/`, weighs
242 MB, is not in this repository and is not redistributable. What is recorded
here is the *instrument* — built, and demonstrated to react in both directions
before it is ever pointed at Zotero.

Instrument: `bench/sdt_stall_probe.py`. Controls: `tests/test_sdt_stall_probe.py`.

## What the instrument is, and why it is three things and not one

| Piece | Reads | Says |
|---|---|---|
| `analyse_heartbeats()` | the sitter's journal records | whether a **plateau** is present |
| `snapshot()` / `cpu_between()` | `/proc/<pid>/task/<tid>/`, per thread | whether the process is spinning or idle |
| `stall_verdict()` | both | **slow-tail**, **wedged**, or **undetermined** |

The split is the point. A plateau is an observation and is compatible with both
readings of the 2026-09-15 trace; only the CPU sample separates them. Where the
CPU sample is missing, `stall_verdict()` returns `undetermined` and says so —
it never falls through to a default.

### Three ways a flat worker thread is *not* a wedge

Added after review round 1, which produced two of them as measured
counterexamples rather than as arguments. Each downgrades to `undetermined`:

1. **The process is busy while the identified thread is not.** Thread
   identification is a heuristic — the busiest thread — and Zotero rotates
   workers. A rotation inside the sampling window used to drop the busy thread
   from the roster entirely, because a tid absent from the *first* snapshot was
   skipped; the reviewer measured `processPercent 99.7` with `workerPercent 0.0`
   and a verdict of **wedged** on a fully saturated process. Two repairs:
   a thread born in the window now gets a zero baseline (all its jiffies did
   accrue in the window), and a process-versus-thread contradiction over the
   window average is reported as undetermined.
2. **The worker is blocked on I/O.** A read off a slow device holds ~0 % CPU and
   is work. The I/O counters were being computed and then stripped by
   `worker_cpu()` before the verdict saw them; measured, 6.4 MB genuinely read
   at `processPercent 1.0` returned **wedged**. They now travel with the
   reading, and bytes at or above a 1 MB floor veto a wedge — counting **both**
   `read_bytes` (block layer) and `rchar` (syscall layer). Round 2 found the
   first repair reading only `read_bytes`, so a worker pulling *already-cached*
   pages — the case the floor's own comment names — still returned `wedged` at
   7.9 MB of real reads. Both counters are read now, and both must be present.
3. **The I/O counters could not be read at all.** `/proc/<pid>/io` is unreadable
   under some hardening. A wedge verdict then rests on a channel nobody
   consulted, which is the all-clear-versus-could-not-look failure this
   repository keeps meeting. It is refused.

### One thing the AR6 run settles about guard 2 itself

`rchar` is process-wide and the recipe samples for 2 400 s. An idle Python
interpreter accrued 52 517 bytes of `rchar` in 3 s from startup alone — about
5 % of the 1 MB floor — so over forty minutes a live Zotero's ambient
housekeeping may clear the floor whatever the worker is doing, and `wedged`
would become unreachable. Not tuned on no data: it fails toward `undetermined`,
the tolerated direction. The record carries the **worker thread's own**
`read_bytes` and `rchar` beside the process-wide figures, and a `wedged`-vetoing
verdict names both, so one run answers it. If the process cleared the floor
while the worker thread read nothing, the floor should be thread-scoped.

### Why the guards read the window average and not the peak

Round 1 asked for the peak as well, and round 2 measured what that costs: over
480 five-second intervals of a live desktop application, a single unrelated
15 %-of-a-core burst is a near-certainty, so a peak-based veto makes `wedged`
almost unobservable — a *common false negative* traded for a *rare false
positive*, on the exact question this ticket asks. The guards therefore decide
on the window average, which is what separated the measured defect (a rotation
leaving the process at 99.7 % throughout) from ordinary desktop noise.

The peaks are not discarded. `maxProcessPercent`, `maxTopThreadPercent` and the
count of intervals above the slow band are recorded, and a `wedged` verdict
names all three in its own `why` string, so a reader sees exactly how much the
window average smoothed over. A *burst* pattern there — idle on average,
repeatedly busy for one interval at a time — is neither of the two readings
0793 offers, and it is a finding in its own right.

## Control arm 1 — the predicate, both directions, one call

`verification/incidents/0793-2026-09-15-ar6-stall.json` carries a healthy arm
and a plateau arm in one file, which is why nothing here is fabricated:

```
elapsed 148238   sinceProgressMS   5818   progress 69   <- healthy
elapsed 208276   sinceProgressMS   5200   progress 88   <- healthy
elapsed 268299   sinceProgressMS  52637   progress 90   <- plateau
elapsed 328314   sinceProgressMS 112652   progress 90   <- plateau
elapsed 388386   sinceProgressMS 172724   progress 90   <- plateau
```

Same function, same thresholds (`quiet_ms=120000`, `slack_ms=2000`,
`min_quiet_beats=2`), opposite answers:

| Input | `reading` | `plateau` | `quietMS` | `quietBeats` |
|---|---|---|---|---|
| records up to the beat at progress 88 | `advancing` | `False` | 5 200 | 0 |
| the whole file | `plateau` | `True` | 172 724 | 2 |

A predicate only ever tested against the plateau cannot be trusted when it
later reports "not wedged": that reading would be indistinguishable from a
predicate that fires on nothing. Both directions are asserted, and
`test_one_predicate_one_threshold_two_answers` exists to hold the two calls to
one set of knobs so the silence cannot be bought by retuning.

There is a third answer. An empty record list, or a beat whose
`sinceProgressMS` is null, returns `reading: "unknown"` — never `advancing`.
"I could not look" and "I looked and saw nothing" are different findings.

### Three readings of the same silence, in decreasing strength

1. **`sinceProgressMS` at the last beat.** `monotonic() - state.lastProgressAt`,
   computed by the sitter itself (`plugins/sdt-sitter/bootstrap.js:644`). No
   inference. This is what decides `plateau`.
2. **The beat-to-beat delta.** If `lastProgressAt` did not move,
   `sinceProgressMS` grows by exactly the wall time between beats. Observed:
   +60 072 ms and +60 015 ms against wall deltas of 60 072 ms and 60 015 ms —
   equal to the millisecond. Blind spot, stated honestly: a tick landing just
   after a beat leaves the next delta looking nearly quiet, so this
   corroborates and does not decide.
3. **`progress` records inside the quiet window:** zero. Weakest of the three —
   the journal ring is bounded at 50 records, so an absence here can be a
   record that rolled off.

## Control arm 2 — the sampler, spinning versus sleeping

Validated offline against two synthetic processes before any Zotero is
involved, measured on `padme`, 1.0 s window:

| Process | `processPercent` | top thread |
|---|---|---|
| `while True: x += 1` | **100.0** | `python3`, 100.0 % |
| `time.sleep(60)` | **0.0** | `python3`, 0.0 % |

The control earned its keep on the first run: the sampler reported the
busy-loop at **0.0 %** because `utime`/`stime` were read at `proc(5)` offsets 11
and 12 instead of 13 and 14, i.e. `majflt + cmajflt`. Two fault counters, which
is why the wrong reading was a silent zero and not a wrong number: any offset
that still included `utime` would have come back non-zero and looked merely
imprecise. That is a failure in the
one direction this instrument must never fail in — a spinning worker reported
as idle is a *wedge verdict on a healthy document*. Nothing but a positive
control catches it; the predicate tests were all green throughout.

Per-thread is not a nicety here: Zotero runs the document extraction off the
main thread, and a main thread busy painting a progress bar would mask an idle
worker in any process-level reading. `snapshot()` walks
`/proc/<pid>/task/<tid>/stat` and reports every thread with its `comm`, plus
RSS from `statm` and `read_bytes`/`rchar` from `io` where the kernel allows
reading them (it reports absence rather than a zero that reads like "no I/O").

Stdlib only — no `psutil`, nothing added to `requirements-check.txt`.

## Control arm 3 — every threshold that decides something, at its exact value

Review round 1 found the offsets defect recurring one level up: flipping `>=` to
`>` on the plateau threshold, or on either CPU band, left the suite fully green.
A boundary that no test stands on is a boundary nobody chose. Each decision
threshold now carries two assertions — one exactly on the value, one one unit
off — and the mutation control was run to confirm they fire:

| Mutant | Result |
|---|---|
| `quiet_ms_observed >= quiet_ms` → `>` | CAUGHT |
| `worker >= slow_cpu_pct` → `>` | CAUGHT |
| `worker <= wedge_cpu_pct` → `<` | CAUGHT |
| `io_bytes >= io_floor_bytes` → `>` | CAUGHT |
| `process >= slow_cpu_pct` → `>` (the contradiction guard) | CAUGHT |
| `io_bytes = max(read, rchar)` → `read` only | CAUGHT |
| `io_bytes = max(read, rchar)` → `rchar` only | CAUGHT |
| I/O presence check → `read_bytes` only | CAUGHT |
| `_UTIME = 13` → `11` | CAUGHT |
| a thread born in the window dropped again | CAUGHT |
| `_ms()` passes wrong-typed values through | CAUGHT |

Eleven mutants, eleven red suites. That is the only evidence that any of these
guards is load-bearing. The last five were added in round 2, which found the
contradiction guard itself unguarded at its exact value — the same defect one
level further up, for the third time in this file.

## What the instrument says about the preserved trace

Recorded as `verification/incidents/0793-2026-09-15-ar6-stall-reading.json`:

- `heartbeats.reading` = **plateau**, corroborated, `quietMS` 172 724,
  `progress` 90, `phase` `extracting`, zero ticks in the quiet window;
- `verdict.verdict` = **undetermined** — "a plateau was observed and no CPU
  sample accompanies it; a slow tail and a wedged worker leave the same
  journal, so nothing here distinguishes them".

That undetermined is the honest state of ticket 0793 today, and it is why the
ticket stays open.

## The single experiment that closes it

Written for the author in one paragraph, in the ticket body under **The single
experiment**. In short: run the sweep on `~/data/Zotero-fresh` with the AR6
admitted, sample `bench/sdt_stall_probe.py --pid <zotero> --seconds 2400` from
a second terminal, let it sit 30 minutes past the plateau instead of switching
off, then feed the shutdown journal back through `--journal`. The reading that
decides it: the **busiest thread's percent through the plateau window**.
Non-trivial (≥ 10 % of a core) with heartbeats still firing is a slow tail;
~0 % (≤ 2 %) with heartbeats still firing is a wedge — subject to the three
downgrades above, which the probe applies and explains in its own `why`.

`johnson-1785-dictionary` is a useful pipeline-realism control and **cannot**
stand in for the AR6: it always finishes, so a Johnson run can show that the
instrument sees a completion and can measure how long a document that *does*
settle sits on its last tick. It can never show that the predicate detects a
wedge, because it never wedges. A scheduler-level wedge control — a mock
`host.ensure` that never resolves — is filed as its own follow-up ticket.
