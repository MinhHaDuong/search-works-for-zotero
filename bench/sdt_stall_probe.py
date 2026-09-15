#!/usr/bin/env python3
"""Is the native SDT worker still working, or has it stopped? (ticket 0793)

THE QUESTION. On 2026-09-15 a full-library sweep ran the IPCC AR6 WG1 (3 949
pages, 242 MB) from progress 49 to 90 in 126 s and then held 90 for at least
173 s, phase still `extracting`, while the sitter's own 60 s heartbeat kept
firing. Nothing crashed. `Zotero.SDT.ensure()`
(`plugins/sdt-sitter/bootstrap.js:3433`) simply stopped reporting. At the
observed rate the remaining ~10 % should have taken ~25 s. Two readings fit
the trace and they point at different fixes:

    slow tail -- the worker is still chewing, the last pages are heavy, and
                 the progress number is too coarse to show it;
    wedged    -- the worker has stopped and will never settle.

THIS FILE DOES NOT ANSWER THAT. It builds the two instruments that can, and it
is deliberate that they are two:

    1. `analyse_heartbeats()` reads the sitter's journal and says whether a
       PLATEAU is present -- an observation, not a cause. A plateau is
       exactly "no progress tick reached the sitter for longer than the
       threshold", and that is compatible with both readings above.
    2. `snapshot()` / `cpu_between()` read the host's own /proc, per thread,
       and say whether the process is spinning or idle.

    3. `stall_verdict()` is the only place the two meet, and it is the only
       place a cause is named. With a plateau and a busy worker thread it
       says slow-tail; with a plateau and a flat one it says wedged; with a
       plateau and no CPU sample at all it says UNDETERMINED and refuses to
       guess. `rules/workflow.md` § Diagnosis discipline is the rule: report
       the observation, hold the cause until it is isolated.

WHY THE PREDICATE IS TESTED IN BOTH DIRECTIONS. The preserved trace
(`verification/incidents/0793-2026-09-15-ar6-stall.json`) carries a healthy arm
and a plateau arm in one file -- ticks 5 000-5 800 ms apart while progress
climbs 69 -> 88, then three beats whose `sinceProgressMS` grows by exactly one
heartbeat interval each time with progress pinned at 90. A predicate only ever
tested against the plateau cannot be trusted when it later reports "not
wedged", because that reading is indistinguishable from a predicate that
cannot see. `tests/test_sdt_stall_probe.py` asserts both arms through one call
with one set of thresholds.

HOW A PLATEAU IS READ, AND THE ONE BLIND SPOT. `sinceProgressMS` is
`monotonic() - state.lastProgressAt` computed at the beat
(`plugins/sdt-sitter/bootstrap.js:644`), i.e. the age of the last progress tick
as the sitter itself measured it. That is the primary reading and it needs no
inference. The beat-to-beat delta corroborates it: if `lastProgressAt` did not
move, `sinceProgressMS` grows by exactly the wall time between the beats, so
`d(since) >= d(wall) - slack` means NO tick landed in that interval. The blind
spot is at the granularity of one interval -- a tick landing just after a beat
leaves the next delta looking nearly quiet -- which is why the primary reading
is the reported age and not the inference, and why the count of `progress`
records inside the quiet window is reported as a third, independent reading.
That third reading is the weakest of the three: the journal ring is bounded at
50 records, so an absence there can be a record that rolled off.

WHAT THIS CANNOT DO. It cannot make the AR6 run happen. That run needs the
author's machine, his library and a Zotero window. See the ticket's "The single
experiment" section.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

#: The sitter's own heartbeat period (`plugins/sdt-sitter/bootstrap.js`).
HEARTBEAT_INTERVAL_MS = 60_000

#: How far `d(sinceProgressMS)` may fall short of `d(wall)` and still count as
#: "no tick landed". Beat-to-beat jitter in the preserved trace is under 80 ms;
#: 2 s is two orders of margin and still an order below a whole interval.
DEFAULT_SLACK_MS = 2_000

#: Two heartbeat intervals of silence before a plateau is declared. One would
#: fire on a document whose tick simply landed early in the interval; the
#: preserved AR6 plateau reached 172 724 ms, so the margin is ample in the
#: direction that matters.
DEFAULT_QUIET_MS = 2 * HEARTBEAT_INTERVAL_MS

#: Corroborating beats required before `corroborated` is set. Advisory: the
#: plateau itself is decided by DEFAULT_QUIET_MS on the reported age.
DEFAULT_MIN_QUIET_BEATS = 2

#: The discriminator's two bands, per CPU core (100.0 == one core saturated).
#: Below the first, a thread is doing nothing; above the second it is working.
#: Between them the probe declines to choose rather than rounding to the
#: reading the reader was hoping for.
WEDGE_CPU_PCT = 2.0
SLOW_CPU_PCT = 10.0


class ProbeError(Exception):
    """The probe could not read what it was asked to read."""


# --------------------------------------------------------------------------
# 1. the plateau predicate -- pure, over journal records
# --------------------------------------------------------------------------

def _beats(records, item_id):
    out = []
    for record in records:
        if record.get("kind") != "heartbeat":
            continue
        if item_id is not None and record.get("id") != item_id:
            continue
        out.append(record)
    return out


def _ticks_between(records, item_id, after_at, until_at):
    """`progress` records strictly after `after_at` and up to `until_at`."""
    count = 0
    for record in records:
        if record.get("kind") != "progress":
            continue
        if item_id is not None and record.get("id") != item_id:
            continue
        at = record.get("at")
        if at is None:
            continue
        if after_at < at <= until_at:
            count += 1
    return count


def analyse_heartbeats(records, *, item_id=None, quiet_ms=DEFAULT_QUIET_MS,
                       slack_ms=DEFAULT_SLACK_MS,
                       min_quiet_beats=DEFAULT_MIN_QUIET_BEATS) -> dict:
    """Read a sitter journal and say whether the last document plateaued.

    `records` is the `records` array of a sitter shutdown journal (or any
    prefix of one -- the reading is of the trailing state, so a prefix ending
    inside the healthy stretch reads as advancing and the whole file reads as
    a plateau, which is what makes the two control arms one call).

    Returns a dict whose `reading` is one of:

        "unknown"   -- no heartbeat, or no tick age reported. NOT an all-clear:
                       a probe that could not look must not sound like one that
                       looked and saw nothing.
        "advancing" -- the last beat's tick age is under the threshold.
        "plateau"   -- it is over. An observation. It does not name a cause;
                       `stall_verdict()` does that, and only with a CPU sample.
    """
    beats = _beats(records, item_id)
    if not beats:
        return {
            "reading": "unknown", "plateau": False, "corroborated": False,
            "beats": 0, "id": item_id, "phase": None, "progress": None,
            "quietMS": None, "quietBeats": 0, "quietSpan": [],
            "ticksInQuietWindow": None, "ticksSinceFirstBeat": None,
            "elapsedMS": None,
            "thresholds": {"quietMS": quiet_ms, "slackMS": slack_ms,
                           "minQuietBeats": min_quiet_beats},
            "why": "no heartbeat record for this document; the probe could not "
                   "look, which is not the same as finding nothing",
        }

    last = beats[-1]
    resolved_id = last.get("id") if item_id is None else item_id
    if item_id is None and resolved_id is not None:
        beats = _beats(records, resolved_id) or beats
        last = beats[-1]
    quiet_ms_observed = last.get("sinceProgressMS")

    # How many trailing beats saw no tick at all, by the delta rule.
    quiet_beats = 0
    for older, newer in zip(reversed(beats[:-1]), reversed(beats[1:])):
        wall = newer.get("at", 0) - older.get("at", 0)
        since_new = newer.get("sinceProgressMS")
        since_old = older.get("sinceProgressMS")
        if since_new is None or since_old is None:
            break
        if since_new - since_old >= wall - slack_ms:
            quiet_beats += 1
        else:
            break
    span = beats[len(beats) - quiet_beats:] if quiet_beats else []

    first_at = beats[0].get("at")
    ticks_since_first = _ticks_between(records, resolved_id, first_at,
                                       last.get("at"))
    quiet_from = (last.get("at") - quiet_ms_observed
                  if quiet_ms_observed is not None and last.get("at") is not None
                  else None)
    ticks_in_quiet = (None if quiet_from is None
                      else _ticks_between(records, resolved_id, quiet_from,
                                          last.get("at")))

    if quiet_ms_observed is None:
        reading, plateau = "unknown", False
        why = ("the last heartbeat reports no tick age (sinceProgressMS null): "
               "no document had been submitted, so there is nothing to read")
    elif quiet_ms_observed >= quiet_ms:
        reading, plateau = "plateau", True
        why = (f"no progress tick for {quiet_ms_observed} ms (threshold "
               f"{quiet_ms} ms) with phase {last.get('phase')!r} at progress "
               f"{last.get('progress')}; {quiet_beats} consecutive beat(s) saw "
               "no tick. This is an observation, not a cause: a slow tail and "
               "a wedged worker produce the same journal.")
    else:
        reading, plateau = "advancing", False
        why = (f"last tick {quiet_ms_observed} ms ago, under the {quiet_ms} ms "
               f"threshold; progress {last.get('progress')}")

    return {
        "reading": reading,
        "plateau": plateau,
        "corroborated": plateau and quiet_beats >= min_quiet_beats,
        "beats": len(beats),
        "id": resolved_id,
        "phase": last.get("phase"),
        "progress": last.get("progress"),
        "elapsedMS": last.get("elapsedMS"),
        "quietMS": quiet_ms_observed,
        "quietBeats": quiet_beats,
        "quietSpan": span,
        "ticksInQuietWindow": ticks_in_quiet,
        "ticksSinceFirstBeat": ticks_since_first,
        "thresholds": {"quietMS": quiet_ms, "slackMS": slack_ms,
                       "minQuietBeats": min_quiet_beats},
        "why": why,
    }


# --------------------------------------------------------------------------
# 2. the sampler -- /proc, stdlib only, per thread
# --------------------------------------------------------------------------

_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
_PAGE_SIZE = os.sysconf("SC_PAGESIZE") if hasattr(os, "sysconf") else 4096


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, ProcessLookupError):
        return None
    except PermissionError:
        return None


def _stat_fields(text: str) -> list[str]:
    """Fields of a /proc stat line, with the parenthesised comm taken out."""
    head, _, tail = text.partition(" (")
    comm, _, rest = tail.rpartition(") ")
    return [head, comm] + rest.split()


#: proc(5): utime is field 14 and stime field 15, 1-indexed from `pid`. With
#: `_stat_fields` keeping pid at 0 and comm at 1 those are offsets 13 and 14.
#: Off-by-two here reads majflt+cmajflt and reports a spinning process as idle,
#: which is the exact direction this probe must never be wrong in -- it is what
#: the first run of the busy-loop control caught. Note that the fault counters
#: are what make the wrong reading a silent zero rather than a wrong number: any
#: offset that still included utime would have come back non-zero and looked
#: merely imprecise.
_UTIME = 13
_STIME = 14


def _cpu_jiffies(text: str) -> tuple[str, int]:
    fields = _stat_fields(text)
    return fields[1], int(fields[_UTIME]) + int(fields[_STIME])


def _io(path: Path) -> dict | None:
    text = _read(path)
    if text is None:
        return None
    out = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        try:
            out[key.strip()] = int(value)
        except ValueError:
            continue
    return out


def snapshot(pid: int) -> dict:
    """One reading of a process: CPU per thread, RSS, and read/write I/O.

    Raises ProbeError if the process is not there. A snapshot is a counter
    reading, not a rate; `cpu_between()` turns two of them into rates.
    """
    root = Path("/proc") / str(pid)
    stat = _read(root / "stat")
    if stat is None:
        raise ProbeError(f"no readable /proc/{pid}/stat; the process is gone "
                         "or not ours")
    comm, jiffies = _cpu_jiffies(stat)

    rss_bytes = None
    statm = _read(root / "statm")
    if statm:
        try:
            rss_bytes = int(statm.split()[1]) * _PAGE_SIZE
        except (IndexError, ValueError):
            rss_bytes = None

    threads = {}
    task = root / "task"
    try:
        tids = sorted(int(entry.name) for entry in task.iterdir()
                      if entry.name.isdigit())
    except (FileNotFoundError, PermissionError):
        tids = []
    for tid in tids:
        tstat = _read(task / str(tid) / "stat")
        if tstat is None:
            continue  # a thread that exited between listing and reading
        tcomm, tjiffies = _cpu_jiffies(tstat)
        threads[str(tid)] = {"tid": tid, "comm": tcomm, "cpuJiffies": tjiffies,
                             "io": _io(task / str(tid) / "io")}

    return {
        "pid": pid,
        "comm": comm,
        "at": int(time.time() * 1000),
        "monotonic": time.monotonic(),
        "cpuJiffies": jiffies,
        "rssBytes": rss_bytes,
        "io": _io(root / "io"),
        "threads": threads,
        "clockTicks": _CLK_TCK,
    }


def _io_delta(before, after, key):
    if not before or not after or key not in before or key not in after:
        return None
    return after[key] - before[key]


def cpu_between(before: dict, after: dict) -> dict:
    """Rates between two snapshots: percent of one core, per process and thread.

    100.0 is one core saturated; a four-thread process can exceed 100.
    """
    elapsed = after["monotonic"] - before["monotonic"]
    if elapsed <= 0:
        raise ProbeError("the two snapshots are not separated in time")
    ticks = before.get("clockTicks") or _CLK_TCK

    def pct(delta_jiffies):
        return delta_jiffies / ticks / elapsed * 100.0

    threads = []
    for tid, now in after["threads"].items():
        was = before["threads"].get(tid)
        if was is None:
            continue  # a thread born inside the window has no baseline
        threads.append({
            "tid": now["tid"],
            "comm": now["comm"],
            "percent": pct(now["cpuJiffies"] - was["cpuJiffies"]),
            "readBytes": _io_delta(was.get("io"), now.get("io"), "read_bytes"),
            "rcharBytes": _io_delta(was.get("io"), now.get("io"), "rchar"),
        })
    threads.sort(key=lambda t: t["percent"], reverse=True)

    return {
        "elapsedS": elapsed,
        "processPercent": pct(after["cpuJiffies"] - before["cpuJiffies"]),
        "rssBytes": after.get("rssBytes"),
        "rssDeltaBytes": (None if after.get("rssBytes") is None
                          or before.get("rssBytes") is None
                          else after["rssBytes"] - before["rssBytes"]),
        "readBytes": _io_delta(before.get("io"), after.get("io"), "read_bytes"),
        "rcharBytes": _io_delta(before.get("io"), after.get("io"), "rchar"),
        "threads": threads,
        "topThread": threads[0] if threads else None,
    }


def sample_series(pid: int, seconds: float, interval: float = 5.0,
                  on_sample=None) -> list[dict]:
    """Snapshots every `interval` for `seconds`, stopping if the process dies."""
    series = []
    deadline = time.monotonic() + seconds
    while True:
        try:
            shot = snapshot(pid)
        except ProbeError:
            break
        series.append(shot)
        if on_sample is not None:
            on_sample(shot)
        if time.monotonic() >= deadline:
            break
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
    return series


def summarize_cpu(series: list[dict]) -> dict:
    """Fold a series into per-interval rates plus the whole-window rate."""
    if len(series) < 2:
        raise ProbeError("a rate needs two snapshots; got "
                         f"{len(series)}")
    intervals = [cpu_between(a, b) for a, b in zip(series, series[1:])]
    overall = cpu_between(series[0], series[-1])
    return {
        "intervals": len(intervals),
        "windowS": overall["elapsedS"],
        "overall": {k: overall[k] for k in
                    ("elapsedS", "processPercent", "rssBytes", "rssDeltaBytes",
                     "readBytes", "rcharBytes")},
        "overallTopThread": overall["topThread"],
        "maxProcessPercent": max(i["processPercent"] for i in intervals),
        "minProcessPercent": min(i["processPercent"] for i in intervals),
        "perInterval": [
            {"elapsedS": i["elapsedS"], "processPercent": i["processPercent"],
             "rssBytes": i["rssBytes"], "readBytes": i["readBytes"],
             "topThread": i["topThread"]}
            for i in intervals
        ],
    }


def worker_cpu(summary: dict, *, comm_hint: str | None = None) -> dict | None:
    """The thread to read as the document worker, and how it was chosen.

    Identification is by CPU share over the whole window, optionally narrowed
    by a `comm` substring. This is a heuristic and says so in the record: the
    sitter cannot name the native worker's thread from the JavaScript side, so
    the reading is "the busiest thread", and where every thread is flat the
    choice does not matter -- which is exactly the wedge case.
    """
    top = summary.get("overallTopThread")
    if top is None:
        return None
    return {
        "workerPercent": top["percent"],
        "processPercent": summary["overall"]["processPercent"],
        "tid": top["tid"],
        "comm": top["comm"],
        "how": "busiest thread over the whole sampling window"
               + (f", comm hint {comm_hint!r} recorded but not enforced"
                  if comm_hint else ""),
    }


# --------------------------------------------------------------------------
# 3. the verdict -- the only place a cause is named
# --------------------------------------------------------------------------

def stall_verdict(plateau: dict, cpu: dict | None, *,
                  wedge_cpu_pct: float = WEDGE_CPU_PCT,
                  slow_cpu_pct: float = SLOW_CPU_PCT) -> dict:
    """Combine the journal reading with the CPU reading, or refuse to.

    The discriminator, and the whole of ticket 0793: with heartbeats still
    firing -- which proves the extension is alive -- a worker thread holding
    non-trivial CPU through the plateau is a SLOW TAIL; a worker thread at
    ~0 % is WEDGED. Without a CPU sample the two are indistinguishable from
    the journal alone, and the answer is UNDETERMINED, never a default.
    """
    base = {
        "plateau": plateau.get("plateau"),
        "reading": plateau.get("reading"),
        "bands": {"wedgeBelowPct": wedge_cpu_pct, "slowAbovePct": slow_cpu_pct},
        "evidence": {"journal": plateau.get("why"), "cpu": cpu},
    }
    if plateau.get("reading") == "unknown":
        return {**base, "verdict": "undetermined",
                "why": "the journal reading is unknown: no heartbeat carried a "
                       "tick age, so there is no plateau to explain"}
    if not plateau.get("plateau"):
        return {**base, "verdict": "advancing",
                "why": "no plateau: progress was still ticking within the "
                       "threshold, so neither reading applies"}
    if cpu is None or cpu.get("workerPercent") is None:
        return {**base, "verdict": "undetermined",
                "why": "a plateau was observed and no CPU sample accompanies "
                       "it; a slow tail and a wedged worker leave the same "
                       "journal, so nothing here distinguishes them"}
    worker = cpu["workerPercent"]
    if worker >= slow_cpu_pct:
        return {**base, "verdict": "slow-tail",
                "why": f"plateau with the worker thread at {worker:.1f} % of a "
                       f"core (>= {slow_cpu_pct} %): the native worker is still "
                       "doing work the progress number is too coarse to show"}
    if worker <= wedge_cpu_pct:
        return {**base, "verdict": "wedged",
                "why": f"plateau with the worker thread at {worker:.1f} % of a "
                       f"core (<= {wedge_cpu_pct} %) while heartbeats keep "
                       "firing: the extension is alive and the native worker "
                       "is not working"}
    return {**base, "verdict": "undetermined",
            "why": f"plateau with the worker thread at {worker:.1f} % of a "
                   f"core, between the {wedge_cpu_pct} % and {slow_cpu_pct} % "
                   "bands: the sample does not separate the two readings. "
                   "Sample longer or per-interval before concluding."}


# --------------------------------------------------------------------------
# 4. the record -- sitter_acceptance.py's phase dict, extended
# --------------------------------------------------------------------------

def build_record(*, ok: bool, phases: dict, run: dict | None = None) -> dict:
    """The acceptance harness's shape, not a new one (ticket 0793 says so).

    `verification/acceptance/0.4.15-2026-09-14.json` is the reference: a top
    level `ok`, a `phases` dict keyed by step, and a `_run` block naming the
    version, the host and the script. Keeping the shape means one reader, one
    set of tooling, and a stall record that sits beside an acceptance record
    without either needing a special case.
    """
    meta = {
        "version": None,
        "zotero": None,
        "host": platform.node(),
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "script": "bench/sdt_stall_probe.py",
        "fixture": None,
    }
    meta.update(run or {})
    return {"ok": ok, "phases": phases, "_run": meta}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def analyse_journal_file(path: Path, **kwargs) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", payload if isinstance(payload, list) else [])
    return analyse_heartbeats(records, **kwargs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--journal", type=Path,
                    help="a sitter shutdown journal (or a preserved incident "
                         "copy); read offline, no Zotero needed")
    ap.add_argument("--pid", type=int,
                    help="a running Zotero to sample; per-thread CPU, RSS, I/O")
    ap.add_argument("--seconds", type=float, default=1800.0,
                    help="how long to sample (default: 30 min past the plateau)")
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--comm-hint", default=None,
                    help="substring of the worker thread's comm, recorded with "
                         "the reading; never used to override the busiest thread")
    ap.add_argument("--item-id", type=int, default=None)
    ap.add_argument("--quiet-ms", type=float, default=DEFAULT_QUIET_MS)
    ap.add_argument("--version", default=None, help="sitter version, for _run")
    ap.add_argument("--zotero", default=None, help="Zotero version, for _run")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args(argv)

    if args.journal is None and args.pid is None:
        ap.error("give --journal, --pid, or both")

    phases: dict = {}
    reading = None
    if args.journal is not None:
        reading = analyse_journal_file(args.journal, item_id=args.item_id,
                                       quiet_ms=args.quiet_ms)
        reading["source"] = str(args.journal)
        phases["heartbeats"] = reading

    cpu = None
    if args.pid is not None:
        series = sample_series(args.pid, args.seconds, args.interval)
        summary = summarize_cpu(series)
        cpu = worker_cpu(summary, comm_hint=args.comm_hint)
        phases["sampling"] = {"pid": args.pid, "requestedSeconds": args.seconds,
                              "intervalS": args.interval, **summary}

    if reading is not None:
        phases["verdict"] = stall_verdict(reading, cpu)

    record = build_record(ok=True, phases=phases,
                          run={"version": args.version, "zotero": args.zotero})
    text = json.dumps(record, indent=2)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.json_out}")
    else:
        print(text)
    if "verdict" in phases:
        print(f"\nVERDICT: {phases['verdict']['verdict']} — "
              f"{phases['verdict']['why']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
