"""A sitter refusal is the host's verdict, not the sitter's failure (ticket 0824).

The sitter's resource gate refuses admission on a host that cannot take the
work -- `low-disk`, `cpu-busy`, and the rest of `SDT_BLOCKED_PHASES` in
`plugins/sdt-sitter/bootstrap.js` -- and retries on its own schedule. A rung
driver that waits only on completion reads that as a timeout, and a timeout as
a sitter failure. So the three rung drivers (`sitter_smoke_test.py`,
`sitter_menagerie_test.py`, `sitter_clone_rung.py`) share this module:

- `preflight()`, before anything is built or launched: free space where the
  sitter will measure it against the plugin's own disk floor plus a margin,
  and load against the core count, refused with a named reason.
- `RefusalGuard.check(state)`, on every poll of every wait on the sitter: a
  blocked phase with work pending ends the wait at once as `SitterRefused` --
  a `NotRunError`, so each driver exits NOT-RUN -- after at most one forced
  retry (switch off, then on) for a transient gate. The record names the gate
  and the readings the gate took (`admission`, the variable
  `describeSDTAdmission` renders), read out of the add-on's own sandbox.
- `arena_work_dir()`, the default work directory: under `$ACCEPTANCE_ARENA`
  (on `~/data`), never `/tmp`, bounded by the acceptance layer's retention.

The gate list and the floor are READ from the plugin source, never restated:
a floor moved there moves the preflight here.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance.run import DEFAULT_KEEP_RUNS, in_progress_marker, retain  # noqa: E402

BOOTSTRAP = REPO / "plugins" / "sdt-sitter" / "bootstrap.js"

#: Headroom over the sitter's floor that the preflight asks for, so a run does
#: not start a hair above the floor and cross it with its own fixture and packs.
DEFAULT_DISK_MARGIN = 1024 ** 3

#: Gates that can clear on their own within a run: one forced retry each run,
#: then NOT-RUN. The others (a full disk, missing storage, unreadable procfs)
#: do not clear by waiting, so they end the wait on the first sighting.
TRANSIENT_GATES = frozenset({"cpu-busy", "low-memory", "sync-in-progress"})


class NotRunError(Exception):
    """Could not look: environment/setup, never the add-on's own behaviour.

    Declared here and re-exported by `sitter_smoke_test`, so one class is
    raised and caught whichever driver runs as `__main__`."""


# --------------------------------------------------------------------------
# what the plugin says
# --------------------------------------------------------------------------

def _product(expr: str) -> int:
    """A JS product such as `4 * 1024 ** 3`: integers, `*` and `**`, nothing else."""
    if not re.fullmatch(r"[\d\s*]+", expr):
        raise ValueError(f"not a plain product: {expr!r}")
    return int(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 -- charset checked above


def plugin_constants(source: str | None = None) -> dict:
    """`SDT_BLOCKED_PHASES` and `MIN_FREE_DISK`, as the plugin declares them."""
    if source is None:
        source = BOOTSTRAP.read_text(encoding="utf-8")
    names = dict(re.findall(r"var (SDT_\w+) = '([^']*)';", source))
    block = re.search(r"var SDT_BLOCKED_PHASES = \[(.*?)\];", source, re.S)
    floor = re.search(r"MIN_FREE_DISK = ([\d\s*]+?)\s*[;,]", source)
    if not block or not floor:
        raise ValueError(f"SDT_BLOCKED_PHASES or MIN_FREE_DISK not found in {BOOTSTRAP}")
    phases = []
    for quoted, ident in re.findall(r"'([^']+)'|(\b[A-Z_]+\b)", block.group(1)):
        if quoted:
            phases.append(quoted)
        elif ident in names:
            phases.append(names[ident])
        else:
            raise ValueError(f"SDT_BLOCKED_PHASES names {ident}, which is not declared")
    return {"blocked_phases": phases, "min_free_disk": _product(floor.group(1))}


def gib(n: float) -> str:
    """Bytes as GiB, one decimal, decimal comma (the repo's number format)."""
    return f"{n / 1024 ** 3:.1f}".replace(".", ",") + " GiB"


def _existing(path: Path) -> Path:
    """The nearest existing ancestor -- what the plugin's gate stats, too."""
    path = Path(path).absolute()
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


def _mount_point(path: Path) -> Path:
    path = _existing(path)
    dev = path.stat().st_dev
    while path.parent != path and path.parent.stat().st_dev == dev:
        path = path.parent
    return path


# --------------------------------------------------------------------------
# before launch
# --------------------------------------------------------------------------

def preflight(directory: Path, *, margin: int = DEFAULT_DISK_MARGIN,
              free: int | None = None, load: float | None = None,
              cpus: int | None = None) -> dict:
    """Refuse, before any build or launch, a host the gate would refuse.

    `directory` is where the sitter will measure disk: the data directory the
    run will pin (or its nearest existing ancestor). The load rule is the
    gate's own, `load >= cpus` refuses (bootstrap.js, `blocked()`).
    """
    floor = plugin_constants()["min_free_disk"]
    where = _existing(directory)
    if free is None:
        free = shutil.disk_usage(where).free
    if free < floor + margin:
        try:
            fs = _mount_point(where)
        except OSError:
            fs = where
        raise NotRunError(
            f"work dir {directory} on {fs}: {gib(free)} free, sitter needs "
            f"{gib(floor)} (+{gib(margin)} margin). The sitter would refuse "
            "admission `low-disk`; nothing was launched.")
    if load is None:
        load = os.getloadavg()[0]
    if cpus is None:
        cpus = os.cpu_count() or 0
    if cpus and load >= cpus:
        raise NotRunError(
            f"load {load:.2f} on {cpus} cores: the sitter refuses admission "
            "`cpu-busy` at load >= cores; nothing was launched.")
    return {"directory": str(where), "free": free, "floor": floor, "margin": margin,
            "load": load, "cpus": cpus}


# --------------------------------------------------------------------------
# during a run
# --------------------------------------------------------------------------

#: What every wait polls. `phase` is what the guard reads.
STATE = """
(function() {
  try {
    const s = Zotero.SDTPackSitter && Zotero.SDTPackSitter.state;
    if (!s) return JSON.stringify({ok: false, reason: "no-handle"});
    return JSON.stringify({ok: true, enabled: !!s.enabled, busy: !!s.busy,
      phase: s.phase, active: s.active, scanned: s.scanned, total: s.total,
      completed: s.completed, failed: s.failed, pending: s.pending.length});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

#: The add-on's bootstrap sandbox, where `admission`, `nextSweepAt` and the
#: switch live as top-level bindings (bootstrap.js says why they are `var`).
#: Zotero keeps plugin sandboxes in a private map (`Zotero.Plugins`), and
#: XPIProvider's scope for this add-on holds only `{extension}` -- both read on
#: Zotero 10.0.3, 2026-09-24. The handle's own `inspect` was defined in that
#: sandbox, so its global IS the sandbox: that is the way in.
_SCOPE = """
    const handle = Zotero.SDTPackSitter;
    const scope = handle && handle.inspect ? Cu.getGlobalForObject(handle.inspect) : null;
"""

READ_ADMISSION_MARK = "/* read-admission */"


def read_admission_code(phase: str) -> str:
    """The refusing gate's readings, and the panel's own sentence for them."""
    return f"""{READ_ADMISSION_MARK}
(function() {{
  try {{{_SCOPE}
    if (!scope) return JSON.stringify({{ok: false, reason: "no-scope"}});
    const a = scope.admission;
    let now = null, text = null;
    try {{ now = scope.monotonic(); }} catch (_e) {{ now = null; }}
    try {{ text = scope.describeSDTRefusal({json.dumps(phase)}); }} catch (_e) {{ text = null; }}
    return JSON.stringify({{ok: true, source: "sitter",
      admission: a ? JSON.parse(JSON.stringify(a)) : null,
      readingAgeMs: a && now !== null ? now - a.at : null,
      nextSweepInMs: scope.nextSweepAt !== null && now !== null
        ? scope.nextSweepAt - now : null,
      refusal: text}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


#: Switch off, then on: the user's forced retry. `toggleSDTSwitch` is what the
#: panel's checkbox calls; the panel is the fallback when the scope is not
#: reachable. Turning it back on schedules a sweep at once (armSDTSitter).
FORCE_RETRY = f"""
(function() {{
  try {{{_SCOPE}
    if (scope && typeof scope.toggleSDTSwitch === "function") {{
      scope.toggleSDTSwitch(true);
      scope.toggleSDTSwitch(false);
      return JSON.stringify({{ok: true, how: "scope"}});
    }}
    const windows = Services.wm.getEnumerator(null);
    while (windows.hasMoreElements()) {{
      const w = windows.getNext();
      let el = null;
      try {{ el = w.document && w.document.getElementById("sdt-switch"); }} catch (_e) {{ continue; }}
      if (!el) continue;
      el.click(); el.click();
      return JSON.stringify({{ok: true, how: "panel"}});
    }}
    return JSON.stringify({{ok: false, reason: "no-scope-and-no-panel"}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


class SitterRefused(NotRunError):
    """The sitter's gate refused admission: the host cannot run this rung."""

    def __init__(self, gate: str, readings: dict, forced_retry: str | None, state: dict):
        self.record = {"gate": gate, "readings": readings, "forced_retry": forced_retry,
                       "state": state}
        admission = readings.get("admission") or readings
        parts = []
        if admission.get("diskAvailableBytes") is not None:
            parts.append(f"{gib(admission['diskAvailableBytes'])} free on "
                         f"{admission.get('directory')}")
        if admission.get("load") is not None:
            parts.append(f"load {admission['load']} on {admission.get('cpus')} cores")
        if admission.get("memoryAvailableBytes") is not None:
            parts.append(f"{gib(admission['memoryAvailableBytes'])} memory available")
        retried = f" after a forced retry on {forced_retry}" if forced_retry else ""
        super().__init__(
            f"the sitter refused admission `{gate}`{retried} with work pending "
            f"({'; '.join(parts) or 'no reading'}, readings from the "
            f"{readings.get('source', 'unknown')}). The host cannot run this rung; "
            "nothing about the sitter was tested.")


def _driver_readings(directory: Path) -> dict:
    """The same three readings, taken by the driver on the same host, when the
    add-on's own are out of reach. Labelled so nobody mistakes them for the
    gate's."""
    where = _existing(directory)
    out = {"source": "driver", "directory": str(where),
           "diskAvailableBytes": shutil.disk_usage(where).free,
           "cpus": os.cpu_count()}
    try:
        out["load"] = os.getloadavg()[0]
    except OSError:
        pass
    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
        kb = re.search(r"^MemAvailable:\s+(\d+) kB$", meminfo, re.M)
        if kb:
            out["memoryAvailableBytes"] = int(kb.group(1)) * 1024
    except OSError:
        pass
    return out


class RefusalGuard:
    """Watches every state a wait reads; raises `SitterRefused` on a refusal.

    `evaluate(code, what) -> dict` runs chrome JS in the Zotero under test.
    `directory` is where the sitter measures disk, for the fallback readings.
    """

    def __init__(self, evaluate, log, directory: Path, constants: dict | None = None):
        self.evaluate, self.log, self.directory = evaluate, log, Path(directory)
        self.blocked = frozenset((constants or plugin_constants())["blocked_phases"])
        self.retried: str | None = None

    def check(self, state: dict) -> None:
        phase = state.get("phase")
        if phase not in self.blocked or not state.get("pending", 1):
            return
        if phase in TRANSIENT_GATES and self.retried is None:
            self.retried = phase
            out = self.evaluate(FORCE_RETRY, f"forced retry on {phase}")
            self.log.write(f"refusal {phase} with {state.get('pending')} pending: "
                           f"one forced retry (switch off, on): {out}")
            return
        readings = self.read(phase)
        self.log.write(f"refusal {phase}: ending the wait NOT-RUN; readings {readings}")
        raise SitterRefused(phase, readings, self.retried, state)

    def read(self, phase: str) -> dict:
        try:
            out = self.evaluate(read_admission_code(phase), "read admission")
        except Exception as exc:  # noqa: BLE001 -- a probe failure must not hide the refusal
            out = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        if out.get("ok"):
            return out
        return {**_driver_readings(self.directory), "sitter_probe": out}


def guard_for(client, log, directory: Path, eval_timeout: float) -> RefusalGuard:
    """A guard over a live RDP client."""
    from sitter_volume_experiment import eval_action

    return RefusalGuard(lambda code, what: eval_action(client, code, eval_timeout, log, what),
                        log, directory)


# --------------------------------------------------------------------------
# where a run lives
# --------------------------------------------------------------------------

def arena_base(check: str) -> Path:
    """`$ACCEPTANCE_ARENA/sitter-<check>`, defaulting as the Makefile does."""
    root = os.environ.get("ACCEPTANCE_ARENA") or str(Path.home() / "data" / "acceptance-arena")
    return Path(root) / f"sitter-{check}"


@contextlib.contextmanager
def arena_work_dir(check: str, *, keep: int = DEFAULT_KEEP_RUNS):
    """A fresh `<base>/<date>/<HHMMSS>-<check>` run directory.

    The acceptance layer's layout, so its retention bounds it: before this run,
    every completed run of the same base beyond the `keep` most recent is
    removed; the in-progress marker keeps this one safe from a concurrent run
    until it returns.
    """
    base = arena_base(check)
    date, started = time.strftime("%Y-%m-%d"), time.strftime("%H%M%S")
    retain(base, keep=keep, current=(date, started))
    work = base / date / f"{started}-{check}"
    work.mkdir(parents=True)
    marker = in_progress_marker(base, date, started)
    marker.touch()
    try:
        yield work
    finally:
        with contextlib.suppress(OSError):
            marker.unlink()
