#!/usr/bin/env python3
"""Rung 3 of the sitter's test ladder: the whole Menagerie, end to end.

`bench/sitter_smoke_test.py` stays what it is -- short and fast, run on every
change. This is the long one, run before a release, and it goes where the smoke
test deliberately stops: the switch, the two invalidation cycles, and the
uninstall.

    1. fresh Zotero, fresh data directory, Menagerie imported
    2. install the add-on, indexing starts
    3. PAUSE at the real switch, and verify it actually paused
    4. RESUME, and watch it finish
    5. every pack's source hash checked against the bytes on disk
    6. delete an ATTACHMENT -- its pack goes, by itself
    7. put it back -- its pack returns, within a minute
    8. the same for a whole ITEM
    9. remove the add-on -- verify no state is left behind

WHAT MAKES 3 A REAL STEP AND NOT A GESTURE. Pausing by writing
`state.enabled = false` would test the scheduler's own flag against itself. This
clicks `#sdt-switch` in the window the toolbar button opens -- the control a
user reaches -- and then checks that no NEW document is admitted while it is
off, which is what "it pauses" means. A pause that only reports itself paused is
the assertion this repository keeps finding.

WHAT 6 AND 8 ARE FOR. Coverage that only ever grows is easy; the hard half is a
library that shrinks. Both cycles assert in both directions, and both bound the
return at 60 s, because "eventually" is not a guarantee anybody can rely on.

AND THROUGHOUT, NOTHING ELSE CHANGES (ticket 0816). A settled snapshot of the
data directory is taken before install, and every step above closes an
integrity segment against it -- the import, the resume, each erase and each
re-attach on its own, the uninstall -- so one edit cannot cancel another in the
diff. Resume-to-indexed holds no library edit, so it is where a write by
`ensure()` beyond the pack would show. The verdicts go in the run record under
`integrity`, a failed run's included.

THE WHOLE CORPUS, EVERY ATTACHMENT ACCOUNTED FOR (ticket 0821). Every file in
the package's `attachments/` is imported -- not only the PDFs, and not a
smallest-first handful -- and the expected count is read off that directory at
run time, never written down here. Once the sitter settles, every attachment's
status is read back through `Zotero.SDTPackSitter.inspect(id)` and classed
against the scheduler's own `SDT_STATUS_CLASSES`: each must end indexed or
unindexed (a pack) or failed / outOfScope (a named reason). One left `queued`,
or a status in no class, fails the run; the per-attachment record is kept
either way. A run that outlives its index deadline while still making
progress says TIMEOUT, not FAIL: the deadline is derived, not measured.

Nothing here touches a real library: a fresh profile (refused if it already has
a prefs.js) and a data directory pinned beside it, re-read from the running
Zotero before anything is imported -- ticket 0782's refusal, kept.

Exit codes: 0 PASS; 1 FAIL; 2 NOT-RUN (no Zotero, no display, or the sitter's
gate refusing admission, ticket 0824); 3 TIMEOUT. NOT-RUN is 2 here and 3 in
the smoke and clone drivers: this driver used 3 for TIMEOUT first, and a
record reader that keys on the code would break if the two swapped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bench"))

from fixtures.smoke_library import (  # noqa: E402
    pick_menagerie_documents,
    write_menagerie_subset,
)
from sitter_smoke_test import (  # noqa: E402
    DEFAULT_MENAGERIE,
    NotRunError,
    SmokeFailure,
    build_xpi,
    check_packs,
    find_zotero_bin,
    integrity_baseline,
    integrity_segment,
    launch_zotero,
    poll_until_armed,
    read_pack_metadata,
    setup_profile,
    stop_zotero,
)
import sitter_integrity as integrity  # noqa: E402
from sitter_refusal import (  # noqa: E402
    DEFAULT_DISK_MARGIN,
    STATE,
    SitterRefused,
    arena_work_dir,
    guard_for,
    preflight,
)
from sitter_volume_experiment import (  # noqa: E402
    eval_action,
    import_menagerie_code,
    install_or_replace_code,
    uninstall_code,
    wait_for_port,
)
from sitter_watch import Log, connect_resilient  # noqa: E402


#: This driver's exit codes; see the module docstring for why they differ
#: from the smoke and clone drivers'.
NOT_RUN_EXIT = 2
TIMEOUT_EXIT = 3


class MenagerieFailure(Exception):
    """A real defect, observed against a live Zotero."""


class RungTimeout(Exception):
    """The run outlived a deadline while the sitter was still making progress.

    Distinct from MenagerieFailure on purpose: the whole-corpus deadlines are
    derived, not measured, so running out of one says the deadline was short,
    not that the sitter is wrong."""


#: A verbatim copy of `SDT_STATUS_CLASSES` in `plugins/sdt-sitter/scheduler.js`
#: -- the one owner of the status vocabulary. Copied rather than read at run
#: time so the classifier is the same object the unit tests exercise, and held
#: to the source by `tests/test_sitter_menagerie.py`, which fails on any drift.
SDT_STATUS_CLASSES = {
    "indexed": ["current"],
    "unindexed": ["empty-pack"],
    "failed": ["failed-session", "inspection-error", "unsupported-pack", "missing-source"],
    "queued": ["missing-pack", "stale-source", "stale-processor", "invalid-pack"],
    "outOfScope": ["excluded", "unsupported"],
}


def classify_status(status) -> str | None:
    """The class `status` belongs to, or None for a status in no class."""
    for name, members in SDT_STATUS_CLASSES.items():
        if status in members:
            return name
    return None


def effective_status(raw, scheduler) -> str:
    """The status the sitter itself holds for an attachment.

    Raw `inspect()` cannot see the scheduler's session verdict: a document the
    scheduler gave up on still inspects `missing-pack`, and only the scheduler's
    own list says `failed-session` (scheduler.js, `classify`). That one status
    is taken from the list; every other status is the fresh inspection's.
    """
    return "failed-session" if scheduler == "failed-session" else raw


def account(rows: list[dict], expected: int) -> dict:
    """Every attachment accounted for, or MenagerieFailure naming the gap.

    `rows` carry `{id, key, status, class}`; `expected` is the count listed
    from the package at run time. `queued` is the one class that is not an
    ending, and a status in no class is a finding, never a pass. Returns the
    per-class counts.
    """
    counts = {name: 0 for name in SDT_STATUS_CLASSES}
    unforeseen, queued = [], []
    for row in rows:
        cls = row.get("class")
        if cls in counts:
            counts[cls] += 1
        if cls is None:
            unforeseen.append(row)
        elif cls == "queued":
            queued.append(row)
    problems = []
    if len(rows) != expected:
        problems.append(f"{len(rows)} attachment(s) swept, {expected} listed in the package")
    if queued:
        problems.append(f"{len(queued)} left queued after settling: "
                        + ", ".join(f"{r.get('key')}={r.get('status')}" for r in queued))
    if unforeseen:
        problems.append(f"{len(unforeseen)} in no status class: "
                        + ", ".join(f"{r.get('key')}={r.get('status')!r}" for r in unforeseen))
    if problems:
        raise MenagerieFailure("not every attachment is accounted for -- "
                               + "; ".join(problems))
    return counts


def pick_victim(rows: list[dict], packs: dict) -> dict | None:
    """The attachment the invalidation cycles erase: one with a pack, smallest.

    The first listed attachment was enough over four PDFs. Over the whole
    corpus it may be an HTML page with no pack to lose -- the arm would then
    have nothing to observe -- or a large PDF whose re-preparation cannot meet
    the one-minute return the cycle holds the sitter to. Rows carry `size` in
    bytes; ties break on the key, so two runs agree.
    """
    eligible = [r for r in rows if r.get("path") and r.get("key") in packs
                and r.get("size") is not None]
    if not eligible:
        return None
    return min(eligible, key=lambda r: (r["size"], r["key"]))


# --------------------------------------------------------------------------
# chrome-side probes
# --------------------------------------------------------------------------

# `STATE`, the probe every wait polls, lives in `sitter_refusal` since ticket
# 0824, beside the guard that reads its `phase`.

#: Open the panel the way a user does -- the toolbar button's own command --
#: rather than by calling openDialog(), which is not reachable from here anyway
#: and would skip whatever the button does on the way.
OPEN_PANEL = """
(function() {
  try {
    const win = Zotero.getMainWindow();
    const button = win.document.getElementById("sdt-pack-sitter-button");
    if (!button) return JSON.stringify({ok: false, reason: "no-toolbar-button"});
    button.doCommand();
    return JSON.stringify({ok: true});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""


def _switch_js(body: str) -> str:
    """Find the sitter's window by the control it carries, not by title.

    Titles are localised and the panel is built at runtime; `#sdt-switch` is
    the thing this step is actually about.
    """
    return f"""
(function() {{
  try {{
    const windows = Services.wm.getEnumerator(null);
    while (windows.hasMoreElements()) {{
      const w = windows.getNext();
      let el = null;
      try {{ el = w.document && w.document.getElementById("sdt-switch"); }}
      catch (_e) {{ continue; }}
      if (!el) continue;
      {body}
    }}
    return JSON.stringify({{ok: false, reason: "no-window-carrying-sdt-switch"}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


READ_SWITCH = _switch_js("""
      return JSON.stringify({ok: true, label: el.textContent,
        ariaLabel: el.getAttribute("aria-label"),
        state: (w.document.getElementById("sdt-switch-state") || {}).textContent});
""")

CLICK_SWITCH = _switch_js("""
      el.click();
      return JSON.stringify({ok: true, clicked: true});
""")

# Ticket 0797 retired `extensions.sdt-pack-sitter.enabled`: nothing about the
# pause is remembered, the startup path arms unconditionally, and the plugin
# CLEARS that preference on startup rather than leaving a dead boolean in the
# profile. So this probe no longer reads a consent answer -- there is none -- and
# instead reads the two facts that can still explain a sitter found paused: the
# phase it is actually in, and whether the retired preference survived (which
# would mean an old build is installed, not that the answer was honoured).
SWITCH_PROBE = """
(function() {
  try {
    const read = (name) => {
      try { return Zotero.Prefs.get(name, true); } catch (e) { return `threw: ${e}`; }
    };
    return JSON.stringify({ok: true,
      phase: Zotero.SDTPackSitter ? Zotero.SDTPackSitter.state.phase : "no sitter",
      retiredPrefStillSet: read("extensions.sdt-pack-sitter.enabled"),
      debug: read("extensions.sdt-pack-sitter.debug")});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

ATTACHMENTS = """
(async function() {
  try {
    const rows = [];
    for (const lib of Zotero.Libraries.getAll()) {
      const ids = await Zotero.Items.getAll(lib.libraryID);
      for (const item of ids) {
        if (!item.isAttachment || !item.isAttachment()) continue;
        let path = null, size = null;
        try { path = await item.getFilePathAsync(); } catch (_e) { path = null; }
        if (path) {
          try { size = (await IOUtils.stat(path)).size; } catch (_e) { size = null; }
        }
        rows.push({id: item.id, key: item.key, parentID: item.parentItemID,
                   title: item.getField("title"), path, size});
      }
    }
    return JSON.stringify({ok: true, attachments: rows});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

#: Every attachment's status, read back through the sitter's own handle after
#: the run settles (ticket 0821). `raw` is a fresh `inspect(id)`; `scheduler`
#: is what the scheduler's own list holds for the id, the only place a
#: `failed-session` verdict is visible. No sitter-side plumbing: both are on
#: `Zotero.SDTPackSitter` already (bootstrap.js).
SWEEP = """
(async function() {
  try {
    const handle = Zotero.SDTPackSitter;
    if (!handle) return JSON.stringify({ok: false, reason: "no-handle"});
    const snapshot = handle.state.censusSnapshot;
    const held = new Map(((snapshot && snapshot.members) || []).map(m => [m.id, m.status]));
    const rows = [];
    for (const lib of Zotero.Libraries.getAll()) {
      for (const item of await Zotero.Items.getAll(lib.libraryID)) {
        if (!item.isAttachment || !item.isAttachment()) continue;
        let info;
        try { info = await handle.inspect(item.id); }
        catch (e) { info = {status: "threw", error: String(e)}; }
        rows.push({id: item.id, key: item.key, filename: item.attachmentFilename || null,
                   contentType: item.attachmentContentType || null,
                   raw: info.status, scheduler: held.has(item.id) ? held.get(item.id) : null,
                   reason: info.reason || null, errorClass: info.errorClass || null});
      }
    }
    return JSON.stringify({ok: true, rows});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""

#: The live red control (ticket 0821): make the native worker read busy once
#: the sitter's queue is down to its last document, so that document is never
#: admitted and stays genuinely `queued`. Over the debugger channel, no plugin
#: edit: `_processingQueue` becomes a getter that answers true from then on,
#: while Zotero's own writes to it still land in `real`. The latch waits until
#: the queue has been seen longer than one, so an empty queue before the
#: census does not freeze the whole run instead of its last document.
HOLD_LAST = """
(function() {
  try {
    const worker = Zotero.PDFWorker;
    if (!worker) return JSON.stringify({ok: false, reason: "no-pdfworker"});
    let real = worker._processingQueue, seen = false;
    Object.defineProperty(worker, "_processingQueue", {configurable: true,
      get() {
        const s = Zotero.SDTPackSitter && Zotero.SDTPackSitter.state;
        const left = s ? s.pending.length : 0;
        if (left > 1) seen = true;
        return (seen && left <= 1) || real;
      },
      set(v) { real = v; }});
    return JSON.stringify({ok: true, armed: true});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""


def erase_code(item_id: int) -> str:
    return f"""
(async function() {{
  try {{
    const item = await Zotero.Items.getAsync({item_id});
    if (!item) return JSON.stringify({{ok: false, reason: "no-such-item"}});
    const parent = item.parentItemID;
    await item.eraseTx();
    return JSON.stringify({{ok: true, erased: {item_id}, parent}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


def attach_code(parent_id, path: str) -> str:
    parent = "null" if parent_id is None else str(parent_id)
    return f"""
(async function() {{
  try {{
    const item = await Zotero.Attachments.importFromFile({{
      file: {json.dumps(path)},
      parentItemID: {parent},
    }});
    return JSON.stringify({{ok: true, id: item.id, key: item.key}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
"""


# --------------------------------------------------------------------------
# on-disk reads -- independent of anything the add-on says about itself
# --------------------------------------------------------------------------

def packs_on_disk(data_dir: Path) -> dict:
    """{storage key: source hash}, with None where the pack would not parse.

    The first version of this dropped unparsable packs on the floor, and that
    turned a limitation of OUR reader into a silent undercount: the run waited
    for a pack that was sitting right there, polled for fifteen minutes and said
    nothing. A pack that exists but will not parse is a fact this function has
    to carry, not hide -- the count is what the waits key on, and the None is
    what makes the reason visible when a hash assertion later needs it.
    """
    out = {}
    for pack in sorted((data_dir / "storage").glob("*/.zotero-sdt-cache")):
        try:
            meta = read_pack_metadata(pack)
        except SmokeFailure:
            out[pack.parent.name] = None
            continue
        out[pack.parent.name] = (meta.get("source") or {}).get("hash")
    return out


def wait_for_pack_count(data_dir: Path, want: int, deadline: float, log: Log,
                        what: str, watch=None) -> dict:
    """`watch`, once per poll, is the refusal guard (ticket 0824): a pack that
    never returns because the gate refused is NOT-RUN, not a FAIL."""
    last = None
    while time.monotonic() < deadline:
        if watch is not None:
            watch()
        last = packs_on_disk(data_dir)
        if len(last) == want:
            log.write(f"menagerie {what}: {want} pack(s) on disk")
            return last
        time.sleep(2.0)
    raise MenagerieFailure(
        f"{what}: waited for {want} pack(s) and the disk still shows "
        f"{len(last or {})} after the deadline. Present: {sorted((last or {}))}")


def wait_settled(run, args, log: Log, expected: int, guard=None) -> dict:
    """Wait until the sitter has nothing left to do, or has stopped doing it.

    Two endings, both handed on to the sweep, which is what judges them:
    DRAINED -- the queue is empty and no job is running -- and STALLED -- no
    job running and no count moving for `settle_quiet` seconds, with work
    still queued. A stall is not waited out to the deadline: whatever holds
    the queue (a host gate, a worker that never frees) is named by the
    sweep's `queued` rows and the `phase` recorded here, which is evidence,
    where a timeout is not. Only a run still making progress at
    `index_timeout` is a RungTimeout. `expected` is the attachment count
    listed from the package.

    A third ending, REFUSED (ticket 0824): `guard` sees the sitter's gate
    refuse admission with work pending and raises `SitterRefused` on that
    poll -- NOT-RUN, the host's verdict -- rather than letting the refusal
    read as a stall or run out the deadline.
    """
    started = time.monotonic()
    deadline = started + args.index_timeout
    last_key, quiet_since, polls = None, None, 0
    while True:
        s = run.state()
        polls += 1
        if guard is not None:
            guard.check(s)
        key = (s["completed"], s["failed"], s["pending"], s["total"], s["active"])
        if key != last_key or s["busy"]:
            last_key, quiet_since = key, time.monotonic()
        elapsed = time.monotonic() - started
        if polls % 30 == 1:
            log.write(f"menagerie settling {elapsed:.0f}s: {s}")
        # `scanned` must reach the listed count first: just after the resume the
        # census has not yet seen the import, and an empty queue then is not
        # a drained one.
        if s["pending"] == 0 and not s["busy"] and s["scanned"] >= expected:
            log.write(f"menagerie drained after {elapsed:.0f}s: {s}")
            return {"how": "drained", "elapsed_s": round(elapsed, 1), "state": s}
        if not s["busy"] and time.monotonic() - quiet_since >= args.settle_quiet:
            log.write(f"menagerie STALLED after {elapsed:.0f}s: {s}")
            return {"how": "stalled", "elapsed_s": round(elapsed, 1), "state": s}
        if time.monotonic() >= deadline:
            raise RungTimeout(
                f"the sitter was still working after --index-timeout "
                f"{args.index_timeout:.0f}s, a derived figure: {s}. Nothing is "
                "known to be wrong; the deadline was short for this corpus.")
        time.sleep(5.0)


def sweep(run, args, log: Log) -> list[dict]:
    """Every attachment's status, classed; re-polled once if any is queued.

    One re-poll, `settle_quiet` seconds later, so a document the scheduler
    was about to record when the settle read was taken is not called left
    behind. A second `queued` is the finding.
    """
    def once():
        out = run.ev_long(SWEEP, "sweep every attachment", timeout=args.sweep_timeout)
        rows = []
        for r in out["rows"]:
            status = effective_status(r["raw"], r["scheduler"])
            rows.append({**r, "status": status, "class": classify_status(status)})
        return rows

    rows = once()
    if any(r["class"] == "queued" for r in rows):
        log.write(f"menagerie sweep found queued rows; re-polling in {args.settle_quiet:.0f}s")
        time.sleep(args.settle_quiet)
        rows = once()
    return rows


# --------------------------------------------------------------------------

class Run:
    def __init__(self, client, log, timeout):
        self.client, self.log, self.timeout = client, log, timeout

    def ev(self, code, what, timeout=None):
        out = eval_action(self.client, code, timeout or self.timeout, self.log, what)
        if not out.get("ok"):
            raise MenagerieFailure(f"{what} failed: {out}")
        return out

    def state(self):
        return self.ev(STATE, "state")

    #: Characters fetched per eval. The debugger hands back a result over
    #: 10 000 characters as a `longString` actor rather than the string, which
    #: the shared client does not follow; the whole-corpus sweep crossed it at
    #: 50 files (ticket 0821's first red run). Each page is JSON-escaped on the
    #: way back, so it stays well under the limit even for non-Latin titles.
    PAGE = 2000

    def ev_long(self, code, what, timeout=None):
        """`ev()` for a result of any length: park it in the chrome process,
        then read it back page by page."""
        size = self.ev(f"""
(async function() {{
  try {{
    const out = await ({code.strip()});
    Zotero.__sdtRung3Out = out;
    return JSON.stringify({{ok: true, length: out.length}});
  }} catch (e) {{ return JSON.stringify({{ok: false, reason: String(e)}}); }}
}})()
""", f"{what} (park)", timeout)["length"]
        pages = []
        for start in range(0, size, self.PAGE):
            pages.append(self.ev(
                f"JSON.stringify({{ok: true, page: Zotero.__sdtRung3Out"
                f".substr({start}, {self.PAGE})}})", f"{what} (page {start})")["page"])
        self.ev("(delete Zotero.__sdtRung3Out, JSON.stringify({ok: true}))",
                f"{what} (release)")
        out = json.loads("".join(pages))
        if not out.get("ok"):
            raise MenagerieFailure(f"{what} failed: {out}")
        return out


def import_with_retry(run: Run, ris: Path, args, log: Log) -> dict:
    """The fixture import, waiting out the translator race rather than losing to it.

    `import_menagerie_code` already awaits `Zotero.initializationPromise`, and
    its own comment calls this the place the race would fire. It fires: on a
    profile whose translators have never been installed, `getTranslators()`
    answers an empty list for some seconds AFTER initialization resolves, and
    the probe correctly reports `no-translator` rather than inventing a result.
    That is the probe being right; waiting is the driver's job.

    Retried here and not fixed in the shared probe on purpose -- changing what
    `import_menagerie_code` means would change it under the volume experiment
    too, and its callers have their own timing.
    """
    deadline = time.monotonic() + args.translator_timeout
    attempt = 0
    while True:
        attempt += 1
        out = eval_action(run.client, import_menagerie_code(ris), args.import_timeout,
                          log, f"import fixture (attempt {attempt})")
        if out.get("ok"):
            return out
        if out.get("reason") != "no-translator":
            raise MenagerieFailure(f"the fixture would not import: {out}")
        if time.monotonic() >= deadline:
            raise NotRunError(
                f"Zotero never installed an RIS translator within "
                f"{args.translator_timeout}s on this fresh profile, so the "
                "fixture could not be imported. Nothing about the sitter was "
                "tested; this is a setup failure, not a defect.")
        log.write("menagerie translators not ready yet; waiting")
        time.sleep(5.0)


def phase_pause(run: Run, args, log: Log) -> dict:
    """Step 3, first half: turn it off at the real switch, before there is work.

    ORDER IS THE WHOLE POINT. The first version of this paused a library that
    was already fully indexed and reported success with `completed` stuck at
    4 of 4 -- nothing was admitted because nothing was left to admit, an
    assertion that could not fail. The fixture is now imported while the switch
    is OFF, so the outstanding work is created during the pause and resuming is
    the control: if it indexes afterwards, the stillness was the switch and not
    a dead sitter.
    """
    run.ev(OPEN_PANEL, "open panel")
    time.sleep(2.0)
    before = run.ev(READ_SWITCH, "read switch")
    log.write(f"menagerie switch before: {before}")

    started = run.state()
    if not started["enabled"]:
        raise MenagerieFailure(
            f"the sitter was already off before the pause step: {started}")

    run.ev(CLICK_SWITCH, "click switch off")
    time.sleep(3.0)
    paused = run.state()
    if paused["enabled"]:
        raise MenagerieFailure(f"clicking the switch did not turn it off: {paused}")
    after = run.ev(READ_SWITCH, "read switch off")
    log.write(f"menagerie switch after off: {after}")
    return {"before": before, "after": after, "completed_at_pause": paused["completed"]}


def phase_verify_paused(run: Run, data_dir: Path, args, log: Log, mark: int) -> dict:
    """Step 3, second half: nothing was indexed while the switch was off."""
    log.write(f"menagerie holding {args.pause_hold}s with work outstanding")
    time.sleep(args.pause_hold)
    held = run.state()
    packs = packs_on_disk(data_dir)
    # The file already under way when the switch was thrown is allowed to
    # finish -- that is the ruling, not a defect -- so one completion is
    # tolerated and a second is the failure. Here there was none under way.
    if held["completed"] > mark + 1:
        raise MenagerieFailure(
            f"the sitter kept admitting work while paused: completed went "
            f"{mark} -> {held['completed']} over {args.pause_hold}s")
    if len(packs) > mark + 1:
        raise MenagerieFailure(
            f"packs appeared on disk while paused: {len(packs)} present, "
            f"{mark} expected")
    log.write(f"menagerie pause verified: completed {mark} -> {held['completed']}, "
              f"{len(packs)} pack(s) on disk")
    return {"completed": held["completed"], "packs": len(packs)}


def phase_resume(run: Run, log: Log) -> dict:
    """Step 4. Turning it back on is the pause step's own control."""
    run.ev(CLICK_SWITCH, "click switch on")
    time.sleep(3.0)
    resumed = run.state()
    if not resumed["enabled"]:
        raise MenagerieFailure(f"clicking the switch did not turn it back on: {resumed}")
    log.write("menagerie resumed")
    return resumed


def phase_invalidation(run: Run, data_dir: Path, fixture_dir: Path, log: Log,
                       args, *, whole_item: bool, ledger: integrity.Ledger,
                       guard=None) -> dict:
    """Steps 6-7 and 8. Delete, watch the pack go; restore, watch it return.

    The integrity check closes a segment after the erase and another after
    the re-attach, each against its own declared edit, so the two edits
    cannot cancel out in one diff (ticket 0816).
    """
    what = "item" if whole_item else "attachment"
    watch = (lambda: guard.check(run.state())) if guard is not None else None
    integrity_segment(ledger, f"before {what} erase", failure=MenagerieFailure)
    listing = run.ev_long(ATTACHMENTS, f"list attachments before {what} delete", timeout=90)
    before = packs_on_disk(data_dir)
    victim = pick_victim(listing["attachments"], before)
    if victim is None:
        raise MenagerieFailure("no attachment with a file on disk and a pack to delete")
    log.write(f"menagerie {what} victim={victim['key']} packs_before={len(before)}")
    if victim["key"] not in before:
        raise MenagerieFailure(
            f"the attachment chosen to delete has no pack to lose "
            f"({victim['key']} not in {sorted(before)}) -- the arm would pass "
            "by having nothing to observe")
    lost_hash = before[victim["key"]]
    source = Path(victim["path"])
    if not source.exists():
        raise MenagerieFailure(f"{source} is gone before the step began")
    kept = source.read_bytes()
    digest = hashlib.md5(kept).hexdigest()
    if digest != lost_hash:
        raise MenagerieFailure(
            f"the pack for {victim['key']} names source hash {lost_hash!r} but "
            f"the file on disk is {digest!r} -- the pack does not belong to it")

    target = victim["parentID"] if whole_item and victim["parentID"] else victim["id"]
    run.ev(erase_code(target), f"erase {what} {target}")

    after = wait_for_pack_count(data_dir, len(before) - 1,
                                time.monotonic() + args.invalidation_timeout,
                                log, f"{what} deleted", watch=watch)
    if victim["key"] in after:
        raise MenagerieFailure(
            f"the count fell but {victim['key']}'s own pack is still there")

    # Erasing a parent erases every attachment under it, not only the victim.
    erased = ([r["key"] for r in listing["attachments"]
               if r.get("parentID") == target] if target != victim["id"]
              else [victim["key"]])
    integrity_segment(ledger, f"{what} erase", integrity.erase_edit(
        erased, parents=0 if target == victim["id"] else 1),
        failure=MenagerieFailure)

    # Put it back and bound the return. `restore_timeout` defaults to 60 s
    # because that is the promise: within a minute, not eventually.
    scratch = fixture_dir / f"restore-{victim['key']}{source.suffix}"
    scratch.write_bytes(kept)
    parent = None if whole_item else victim["parentID"]
    added = run.ev(attach_code(parent, str(scratch)), f"re-add {what}", timeout=90)
    log.write(f"menagerie re-added as {added}")

    back = wait_for_pack_count(data_dir, len(before),
                               time.monotonic() + args.restore_timeout,
                               log, f"{what} restored", watch=watch)
    if digest not in set(back.values()):
        raise MenagerieFailure(
            f"a pack came back but none names the restored file's hash {digest!r}; "
            f"packs now name {sorted(set(back.values()))}")
    integrity_segment(ledger, f"{what} re-attach", integrity.attach_edit(scratch.name),
                      failure=MenagerieFailure)
    return {"what": what, "key": victim["key"], "hash": digest,
            "packs_before": len(before), "packs_after_delete": len(after),
            "packs_after_restore": len(back)}


CLEAR_DIAGNOSTICS = """
(function() {
  try {
    Zotero.Prefs.clear("extensions.sdt-pack-sitter.debug", true);
    let still;
    try { still = Zotero.Prefs.get("extensions.sdt-pack-sitter.debug", true); }
    catch (e) { still = undefined; }
    return JSON.stringify({ok: true, debugAfterClear: still ?? null});
  } catch (e) { return JSON.stringify({ok: false, reason: String(e)}); }
})()
"""


def phase_uninstall(run: Run, data_dir: Path, profile: Path, log: Log, args,
                    ledger: integrity.Ledger) -> dict:
    """Step 9. Removed means removed -- in the configuration a release ships.

    THE FIRST VERSION OF THIS ASSERTED THE WRONG THING and the run caught it: it
    demanded no certificate while the rig's own SEED_PREFS had set
    `extensions.sdt-pack-sitter.debug = true`, so the uninstall correctly wrote
    one. That is the ruling of 2026-09-12 -- the certificate is the ONE file a
    clean uninstall must not sweep away, because it is the operator's own
    request, made before the event -- and a test that calls the ruling a defect
    is worse than no test.

    So the diagnostics opt-in is withdrawn first, and the assertion becomes the
    one the author actually asked for: with the switch off, which is how a
    release ships, an uninstall leaves NOTHING. The opted-in half is asserted by
    the unit suite ("an uninstall writes one too, and an ordinary quit does
    not"), where it can be driven without spending a live run on it.
    """
    cleared = run.ev(CLEAR_DIAGNOSTICS, "withdraw the diagnostics opt-in")
    if cleared.get("debugAfterClear"):
        raise MenagerieFailure(
            f"the diagnostics pref would not clear: {cleared}. The arm below "
            "would then pass or fail for the wrong reason.")
    stale = data_dir / "sdt-sitter-last-shutdown.json"
    if stale.exists():
        # Nothing in this run has disabled or uninstalled yet, so a certificate
        # here would be from a shutdown that never happened -- refuse rather
        # than quietly delete evidence the next assertion depends on.
        raise MenagerieFailure(
            f"a certificate already exists at {stale} before the uninstall step; "
            "the arm cannot tell a surviving one from a newly written one")
    integrity_segment(ledger, "before uninstall", failure=MenagerieFailure)
    run.ev(uninstall_code("sdt-pack-sitter@search-works-for-zotero.invalid"),
           "uninstall")
    deadline = time.monotonic() + args.uninstall_timeout
    residue = None
    while time.monotonic() < deadline:
        residue = {
            "cache": (data_dir / "sdt-sitter-cache.jsonl").exists(),
            "cache_tmp": (data_dir / "sdt-sitter-cache.jsonl.tmp").exists(),
            "certificate": (data_dir / "sdt-sitter-last-shutdown.json").exists(),
            "xpi": (profile / "extensions"
                    / "sdt-pack-sitter@search-works-for-zotero.invalid.xpi").exists(),
        }
        if not any(residue.values()):
            log.write("menagerie uninstall left nothing behind")
            # The last snapshot, with Zotero still running: an uninstall is no
            # library edit, so only the sitter's own files may have moved.
            integrity_segment(ledger, "uninstall", failure=MenagerieFailure)
            return {"residue": residue, "clean": True}
        time.sleep(2.0)
    raise MenagerieFailure(
        f"state survived the uninstall with diagnostics withdrawn: {residue}")


def _tally(values) -> dict:
    out: dict = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def _timing(t: dict) -> dict:
    """Wall-clock spans of the run, in seconds: the first measured figures for
    a whole-corpus rung, which the deadlines below were derived without."""
    out = {}
    if "resumed" in t and "settled" in t:
        out["resume_to_settled_s"] = round(t["settled"] - t["resumed"], 1)
    if "finished" in t:
        out["whole_run_s"] = round(t["finished"] - t["started"], 1)
    return out


def run_menagerie(args) -> dict:
    log = Log(args.work_dir / "menagerie.log")
    # Ticket 0824: a host the sitter's gate would refuse is refused before
    # anything is built, copied or launched. The data dir goes under work_dir.
    log.write(f"menagerie preflight: {preflight(args.work_dir, margin=args.disk_margin)}")
    binary = find_zotero_bin(args.zotero_bin)
    app_ini = binary.parent / "app" / "application.ini"

    xpi = args.xpi or (args.work_dir / "sitter-menagerie.xpi")
    if args.xpi is None:
        build_xpi(xpi)
    log.write(f"menagerie payload {xpi}")

    fixture_dir = args.work_dir / "fixture"
    fixture_dir.mkdir(parents=True)
    # Every file of every type (ticket 0821); `--fixture-documents N` keeps a
    # smallest-first slice of that same listing for a short run.
    documents = pick_menagerie_documents(args.menagerie, args.fixture_documents,
                                         suffixes=None)
    if not documents:
        raise NotRunError(
            f"no Menagerie package at {args.menagerie}; this run is about real "
            "documents with distinct hashes and will not fall back")
    expected = len(documents)
    ris = write_menagerie_subset(fixture_dir, documents)
    log.write(f"menagerie fixture: {expected} file(s) listed from "
              f"{args.menagerie / 'attachments'}: {[d.name for d in documents]}")
    timing = args.timing = {"started": time.time()}

    profile, requested = setup_profile(args.work_dir, args.port)
    proc, stdout_log = launch_zotero(binary, app_ini, profile, args.port,
                                     args.work_dir / "zotero-stdout.log")
    client = None
    phases = {}
    try:
        wait_for_port("127.0.0.1", args.port, time.monotonic() + 90)
        client = connect_resilient("127.0.0.1", args.port, args.eval_timeout, log)
        run = Run(client, log, args.eval_timeout)

        # The integrity baseline, before the sitter exists in this profile.
        ledger = integrity_baseline(client, requested, args.eval_timeout, log,
                                    failure=MenagerieFailure)
        args.integrity_records = ledger.records
        # The baseline itself was taken at the shared default; every segment
        # after it waits up to --settle-timeout for the directory to hold still.
        ledger.timeout = args.settle_timeout

        installed = run.ev(install_or_replace_code(xpi), "install")
        try:
            live = poll_until_armed(client, log, args.eval_timeout,
                                    time.monotonic() + args.arm_timeout)
        except SmokeFailure:
            # Read the switch state from INSIDE the process before giving up.
            # Attempt 3 failed with phase 'switched-off' on a profile whose
            # prefs.js carried enabled=true, and the failure could not say
            # whether the pref was not read, not honoured, or overwritten --
            # three different bugs wearing one message. Since ticket 0797 there
            # is no pref to read, so the same question is answered by the phase
            # itself plus whether an old build's preference is still lying around.
            probe = eval_action(client, SWITCH_PROBE, args.eval_timeout, log,
                                "switch state")
            log.write(f"menagerie arm failed; switch state reads {probe}")
            raise
        data_dir = Path(live["dataDir"]).resolve()
        if data_dir != requested.resolve():
            raise MenagerieFailure(
                f"REFUSING to import: Zotero opened {data_dir}, not the pinned "
                f"{requested.resolve()}. Nothing was imported.")
        phases["install"] = {"installed": installed, "dataDir": str(data_dir)}
        guard = guard_for(client, log, data_dir / "storage", args.eval_timeout)

        # OFF FIRST, then import: the work has to be created during the pause
        # for the pause to be observable at all.
        phases["pause"] = phase_pause(run, args, log)
        mark = phases["pause"]["completed_at_pause"]

        imported = import_with_retry(run, ris, args, log)
        prepared = imported["attachments"] - imported["missing"]
        if imported["attachments"] != expected or imported["missing"]:
            raise MenagerieFailure(
                f"the import made {imported['attachments']} attachment(s), "
                f"{imported['missing']} missing on disk, from {expected} files "
                "listed in the package")
        if prepared < 2:
            raise NotRunError(
                f"only {prepared} attachment(s) landed on disk; the invalidation "
                "steps need more than one so that deleting one leaves something")
        phases["import"] = imported

        phases["paused_verified"] = phase_verify_paused(run, data_dir, args, log, mark)
        # Closed while the switch is still off, so the import's own writes --
        # Zotero indexes what it is handed -- are charged to the declared edit
        # and cannot hide inside the indexing segment that follows.
        integrity_segment(ledger, "install+pause+import", integrity.import_edit(
            imported["items"], imported["attachments"]), failure=MenagerieFailure)
        if args.red_hold_last:
            phases["red_control"] = run.ev(HOLD_LAST, "red control: hold the last document")
            log.write("menagerie RED CONTROL armed: the last document is held queued")
        phases["resume"] = phase_resume(run, log)
        timing["resumed"] = time.time()

        phases["settle"] = wait_settled(run, args, log, expected, guard=guard)
        timing["settled"] = time.time()
        rows = sweep(run, args, log)
        args.attachment_records = rows
        counts = account(rows, expected)
        phases["accounted"] = {"expected": expected, "classes": counts,
                               "statuses": _tally(r["status"] for r in rows)}
        log.write(f"menagerie every attachment accounted for: {phases['accounted']}")
        # One pack per attachment that ended with one, each naming bytes this
        # run wrote: the sweep's own count, checked against the disk.
        phases["packs"] = check_packs(data_dir, fixture_dir,
                                      counts["indexed"] + counts["unindexed"], log)

        # Resume to indexed is the segment with no library edit in it: the
        # import closed its own segment above, so whatever changes here is the
        # sitter's, and only the SDT cache may. This is the segment that says
        # whether ensure() writes anything besides the pack.
        integrity_segment(ledger, "resume+index", failure=MenagerieFailure)

        phases["attachment_cycle"] = phase_invalidation(
            run, data_dir, fixture_dir, log, args, whole_item=False, ledger=ledger,
            guard=guard)
        phases["item_cycle"] = phase_invalidation(
            run, data_dir, fixture_dir, log, args, whole_item=True, ledger=ledger,
            guard=guard)

        phases["uninstall"] = phase_uninstall(run, data_dir, profile, log, args, ledger)
        log.write("menagerie PASS")
        timing["finished"] = time.time()
        return {"ok": True, "phases": phases, "integrity": ledger.records,
                "timing": _timing(timing), "attachments": rows}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
        stop_zotero(proc)
        stdout_log.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work-dir", type=Path, default=None,
                    help="a fresh directory; the profile and data dir are made "
                         "under it (default: a fresh run directory under "
                         "$ACCEPTANCE_ARENA/sitter-menagerie, on ~/data and "
                         "never /tmp, ticket 0824)")
    ap.add_argument("--disk-margin", type=int, default=DEFAULT_DISK_MARGIN,
                    help="bytes the preflight asks for above the sitter's own "
                         "disk floor, which is read from the plugin")
    ap.add_argument("--xpi", type=Path, help="payload; built from the tree if omitted")
    ap.add_argument("--zotero-bin", type=Path,
                    default=Path("/home/haduong/.local/bin/zotero"))
    ap.add_argument("--menagerie", type=Path, default=DEFAULT_MENAGERIE)
    ap.add_argument("--fixture-documents", type=int, default=None,
                    help="import only the N smallest files of the package, any "
                         "type; the default, every file, is the rung (ticket 0821)")
    ap.add_argument("--port", type=int, default=6960)
    ap.add_argument("--eval-timeout", type=float, default=60.0)
    ap.add_argument("--arm-timeout", type=float, default=180.0)
    # The whole-corpus deadlines (ticket 0821). The 900 s index default was
    # tuned for four small PDFs. The one measured extraction rate
    # (verification/SDT-CAPS-0483.md: about 5 pages/s, one PDF) puts the
    # package's 572 MiB of PDF and EPUB near two hours -- DERIVED, NOT MEASURED
    # -- so the default is half as long again, and the run record's `timing`
    # carries the first measured figure. Outliving it while still progressing
    # is a TIMEOUT, not a FAIL.
    ap.add_argument("--index-timeout", type=float, default=3 * 3600.0,
                    help="resume to settled, seconds; derived, see the comment")
    ap.add_argument("--import-timeout", type=float, default=900.0,
                    help="one RIS import eval: was an unnamed 180 s sized for "
                         "four files; the import links every file and hands "
                         "each to Zotero's own full-text indexer")
    ap.add_argument("--settle-quiet", type=float, default=300.0,
                    help="no job running and no count moving this long, with "
                         "work still queued, is a STALL: the sweep then names "
                         "what was left, instead of waiting out --index-timeout")
    ap.add_argument("--settle-timeout", type=float, default=900.0,
                    help="how long each integrity segment waits for the data "
                         "directory to hold still; the import segment follows "
                         "Zotero's own indexing of every imported file")
    ap.add_argument("--sweep-timeout", type=float, default=900.0,
                    help="one eval inspecting every attachment, each hashed")
    ap.add_argument("--red-hold-last", action="store_true",
                    help="RED CONTROL: hold the sitter's last queued document "
                         "behind a native worker that reads busy, so it stays "
                         "queued; the run must then FAIL the completeness check")
    ap.add_argument("--translator-timeout", type=float, default=180.0,
                    help="how long to wait for a fresh profile to install its "
                         "RIS translator before calling the run NOT-RUN")
    ap.add_argument("--pause-hold", type=float, default=30.0,
                    help="seconds to hold the switch off while watching for "
                         "admissions that should not happen")
    ap.add_argument("--invalidation-timeout", type=float, default=120.0)
    ap.add_argument("--restore-timeout", type=float, default=60.0,
                    help="the promise this run holds the sitter to: a restored "
                         "file is prepared again WITHIN A MINUTE")
    ap.add_argument("--uninstall-timeout", type=float, default=60.0)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args(argv)
    if args.work_dir is None:
        with arena_work_dir("menagerie") as work_dir:
            args.work_dir = work_dir
            return _main(args)
    return _main(args)


def _main(args) -> int:
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.integrity_records = []
    args.attachment_records = []
    args.timing = {}
    try:
        result = run_menagerie(args)
    except NotRunError as exc:
        print(f"NOT-RUN: {exc}")
        if args.json_out:
            # A refusal's gate and readings are the record (ticket 0824).
            args.json_out.write_text(json.dumps(
                {"ok": False, "not_run": True, "error": str(exc),
                 "refusal": exc.record if isinstance(exc, SitterRefused) else None,
                 "integrity": args.integrity_records}, indent=2), encoding="utf-8")
            print(f"\nwrote {args.json_out}")
        return NOT_RUN_EXIT
    except RungTimeout as exc:
        print(f"TIMEOUT: {exc}")
        if args.json_out:
            args.json_out.write_text(json.dumps(
                {"ok": False, "timeout": True, "error": str(exc),
                 "integrity": args.integrity_records}, indent=2), encoding="utf-8")
            print(f"\nwrote {args.json_out}")
        return TIMEOUT_EXIT
    except Exception as exc:  # noqa: BLE001 -- MenagerieFailure, SmokeFailure, or a crash
        # The catch-all is the smoke driver's: an unattended run reports its
        # own crash -- a filesystem race inside a snapshot included -- as a
        # FAIL with its evidence, not as a traceback that drops the records.
        known = isinstance(exc, (MenagerieFailure, SmokeFailure))
        print(f"FAIL: {exc}" if known else f"FAIL (unexpected {type(exc).__name__}): {exc}")
        # A failed run still carries every integrity segment it closed, the
        # failing one included: the record is what names the bad write.
        if args.json_out:
            args.json_out.write_text(json.dumps(
                {"ok": False, "error": str(exc), "integrity": args.integrity_records,
                 "timing": _timing({**args.timing, "finished": time.time()})
                 if args.timing else {},
                 "attachments": args.attachment_records}, indent=2), encoding="utf-8")
            print(f"\nwrote {args.json_out}")
        return 1
    print("\n================ MENAGERIE: PASS ================")
    for name, payload in result["phases"].items():
        print(f"  {name}")
        print(f"      {json.dumps(payload)[:160]}")
    for rec in result["integrity"]:
        print(f"  integrity {rec['segment']}: {rec['verdict']}")
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
