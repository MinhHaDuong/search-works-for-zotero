#!/usr/bin/env python3
"""Watch one Zotero profile for the sitter's disappearance, and keep the evidence.

Ticket 0727. The sitter has twice vanished from a live profile -- registered,
then DISABLED, then REMOVED, file and record, mid-session, with no Zotero update
and no user action -- and the ticket still has no mechanism. The watcher that
recorded the 2026-09-06 evening was `scratchpad/sitter-watch.sh`, which was
never committed to any branch and is gone; the only versioned watcher since has
been a class inside `bench/sitter_volume_experiment.py`, inseparable from the
driver that spawns its own headless Zotero and installs into it. So nothing
could watch the author's OWN profile while he worked, which is where both
organic occurrences happened. This module is that watcher, and the experiment
driver imports it rather than keeping a second copy.

WHAT IT WATCHES, AND WHY ONLY THIS. `extensions.json` (through
`bench/host_addon_record.py`, the one reader) and the `.xpi`'s presence on disk.
Both are what the host itself writes, neither is debounced in the
present/absent direction, and a line is logged ONLY on change: a quiet log is
"nothing moved", a line is a transition, stamped. The add-on's own reading of
itself is deliberately not consulted -- a plugin being taken away cannot be the
witness to its own removal.

WHAT IT KEEPS WHEN IT FIRES. The signature alone was never enough: the ticket
has needed, all along, the answer to "which event was it" -- a compatibility
disable, an uninstall, or something else -- and the artefacts that answer it are
destroyed within seconds or minutes of the event.

  1. `extensions.json` is copied before the host can overwrite it again.
  2. The add-on's own ring, parked at `Zotero.SDTPackSitterJournal` by
     `shutdown()`, is read over RDP if a debugger port is given. It carries
     Gecko's own shutdown reason, named. It lives only as long as the Zotero
     PROCESS, so it must be read before the restart a user reaches for.
  3. The sitter's death certificate (`sdt-sitter-last-shutdown.json` in the data
     directory, written when the debug pref is on) is copied if present -- the
     copy of (2) that outlives the process.

None of the three is guaranteed: (2) needs a debugger port, (3) needs the pref.
Each is reported as taken or as absent, and an absent one is a finding too.

Usage, against a live profile, unattended:

    python3 bench/sitter_watch.py --profile ~/.zotero/zotero/<profile> \\
        --log ~/sitter-watch.txt

and with the ring read as well, if Zotero was started with a debugger server:

    python3 bench/sitter_watch.py --profile <profile> --log <file> --rdp-port 6000

`--log` is written, not `.log`-suffixed by default, because `.log` is
repo-gitignored (.gitignore:20) and this file's whole purpose is to be committed
as evidence when it finally fires.
"""

import argparse
import contextlib
import json
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from host_addon_record import host_addon_record  # noqa: E402

ADDON_ID = "sdt-pack-sitter@search-works-for-zotero.invalid"
#: The file `writeSDTDeathCertificate` writes into the Zotero data directory.
CERTIFICATE_NAME = "sdt-sitter-last-shutdown.json"
#: Read the ring the add-on parks on the Zotero global at shutdown. Returns a
#: string either way, so a failure comes back as evidence and not as a raise.
READ_PARKED_RING_JS = """
(() => {
  try {
    const ring = Zotero.SDTPackSitterJournal;
    if (!ring) return JSON.stringify({ parked: false });
    return JSON.stringify({ parked: true, records: ring.tail(200) });
  } catch (error) {
    return JSON.stringify({ parked: false, error: String(error) });
  }
})()
"""


def refuse_dot_log(path: Path) -> str:
    """The `.gitignore` trap, refused rather than documented.

    Ticket 0727's log records it firing once already (2026-09-11T16:08Z): the
    arm-5 raw log was written as `run-watch.log`, `.gitignore:20` ignores
    `*.log`, and the file had to be renamed before it could be committed. This
    watcher exists to produce a file worth committing, so the name that cannot
    be committed is refused at the door.
    """
    return (f"{path} ends in .log, which .gitignore:20 ignores -- this log is evidence "
            f"and has to be committable. Use {path.with_suffix('.txt')}.")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Log:
    """Appends timestamped lines to a file and echoes them, flushing each one.

    Flushed per line because the interesting run is the one that is killed, or
    that ends with the machine in a state nobody planned for.
    """

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("a", encoding="utf-8")

    def write(self, line: str) -> None:
        stamped = f"{utc_stamp()} {line}"
        self.handle.write(stamped + "\n")
        self.handle.flush()
        print(stamped, flush=True)

    def close(self) -> None:
        self.handle.close()


def format_state(state: dict, xpi_present: bool, pid=None) -> str:
    """One line describing what the host says right now.

    Kept as a formatted STRING and compared as one: the watcher logs on change,
    and "changed" has to mean "changed in something this line shows".
    """
    if not state.get("read"):
        body = f"record unreadable ({state.get('why')})"
    elif not state.get("present"):
        body = f"record ABSENT (ids present: {len(state.get('ids') or [])})"
    else:
        body = (f"present version={state.get('version')} active={state.get('active')} "
                f"location={state.get('location')}")
    suffix = "" if pid is None else f" pid={pid}"
    return f"watcher {body} xpi={'present' if xpi_present else 'ABSENT'}{suffix}"


class Watcher:
    """Polls `extensions.json` + the `.xpi`'s presence on disk, logs on change.

    Runs on its own thread and its own clock, independent of any action loop:
    an action-adjacent sample describes the write debounce rather than a real
    transition (`extensions.json`'s `active` field is written late -- confirmed
    in ticket 0766 -- while present/absent is not).

    On the present -> absent transition it sets `disappearance` and calls
    `preserve()`, which is where the evidence is taken.
    """

    def __init__(self, profile: Path, addon_id: str, log: Log, get_pid=None,
                 poll_seconds: float = 1.5, evidence_dir: Path = None,
                 data_dir: Path = None, read_ring=None):
        self.profile = profile
        self.addon_id = addon_id
        self.log = log
        self.get_pid = get_pid or (lambda: None)
        self.poll_seconds = poll_seconds
        self.evidence_dir = evidence_dir
        self.data_dir = data_dir
        self.read_ring = read_ring
        self.xpi_path = profile / "extensions" / f"{addon_id}.xpi"
        self.disappearance = threading.Event()
        self._stop = threading.Event()
        self._last_line = None
        self._was_present = False
        self._expected = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    @contextlib.contextmanager
    def expect_absence(self, reason: str):
        """Hold the alert while the caller removes the add-on ON PURPOSE.

        Without this the randomised arms of the volume driver -- which uninstall
        and reinstall deliberately -- would manufacture a reproduction of the
        very defect the watcher exists to catch, and a false reproduction is
        worse than none: it would be investigated, and the investigation would
        end in the driver's own log. The alert line says "with no uninstall
        issued here" and cannot check that claim by itself, so the caller that
        knows says so.

        Narrow on purpose. The window is the gesture, not the cycle, and it is
        logged at both ends so a reader can see exactly what was excused.
        """
        self.log.write(f"watcher absence EXPECTED from here on: {reason}")
        self._expected = reason
        try:
            yield
        finally:
            self._expected = None
            self.log.write(f"watcher absence no longer expected: {reason}")

    def preserve(self) -> None:
        """Take everything that is about to stop existing. Never raises.

        Ordered by how fast each artefact decays: `extensions.json` is rewritten
        by the host within seconds, the parked ring dies with the Zotero
        process, and the certificate survives on disk until the next disable.
        """
        if self.evidence_dir is None:
            self.log.write("watcher evidence NOT taken: no --evidence-dir given")
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.evidence_dir / f"disappearance-{stamp}"
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.log.write(f"watcher evidence FAILED to make {target}: {exc}")
            return

        source = self.profile / "extensions.json"
        try:
            shutil.copy2(source, target / "extensions.json")
            self.log.write(f"watcher evidence took extensions.json -> {target}")
        except OSError as exc:
            self.log.write(f"watcher evidence MISSING extensions.json: {exc}")

        if self.data_dir is not None:
            certificate = self.data_dir / CERTIFICATE_NAME
            try:
                shutil.copy2(certificate, target / CERTIFICATE_NAME)
                self.log.write(f"watcher evidence took {CERTIFICATE_NAME}")
            except OSError as exc:
                self.log.write(
                    f"watcher evidence NO {CERTIFICATE_NAME}: {exc} -- the add-on's debug "
                    f"pref was off, or its own write failed (an unwritable or full data "
                    f"directory: it catches that and journals `certificate-failed` to the "
                    f"debug log), or it never reached its own shutdown at all. The third "
                    f"is the sharpest of the three and the debug log tells them apart.")
        else:
            self.log.write("watcher evidence NO certificate: no --data-dir given")

        if self.read_ring is None:
            self.log.write("watcher evidence NO parked ring: no --rdp-port given")
            return
        try:
            ring = self.read_ring()
            (target / "parked-ring.json").write_text(ring, encoding="utf-8")
            parked = json.loads(ring).get("parked")
            self.log.write(f"watcher evidence took the parked ring (parked={parked})")
        except Exception as exc:  # noqa: BLE001 -- evidence taking must not raise
            self.log.write(f"watcher evidence FAILED to read the parked ring: {exc}")

    def poll_once(self) -> None:
        """One reading, and the decision it leads to. Separate from the loop so
        a test can drive the decision without racing the poll interval -- a
        suite that slept for transitions would be a suite that sometimes
        passes, and this watcher gets one chance at the real event."""
        state = host_addon_record(self.profile, self.addon_id)
        xpi_present = self.xpi_path.exists()
        line = format_state(state, xpi_present, self.get_pid())
        if line == self._last_line:
            return
        self.log.write(line)
        self._last_line = line
        if not state.get("read"):
            # "Could not look" is NOT "looked, and it is gone", and collapsing
            # the two here would undo the whole reason `host_addon_record` is
            # three-valued. It matters in this watcher more than anywhere else:
            # it is meant to run for days across restarts the author performs
            # himself, and a partial `extensions.json` read during one of those
            # is an unreadable, not an absence. Firing on it would spend the
            # alert -- and the evidence taking -- on a non-event, and a watcher
            # that has cried wolf once is a watcher whose next line is doubted.
            # `_was_present` is deliberately NOT updated: a present -> unreadable
            # -> absent sequence still fires on the third reading.
            return
        now_present = bool(state.get("present"))
        if self._was_present and not now_present and self._expected:
            # Asked for, and said so before it happened. Recorded rather than
            # swallowed: a log that hides what it excused cannot be audited.
            self.log.write(
                f"watcher absence observed and EXPECTED ({self._expected}); "
                f"not the signature, no evidence taken"
            )
        elif self._was_present and not now_present:
            self.log.write(
                "watcher ALERT disappearance signature: record went "
                "from present to absent with no uninstall issued here"
            )
            self.preserve()
            self.disappearance.set()
        self._was_present = now_present

    def _run(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.poll_seconds)


def connect_resilient(host: str, port: int, timeout: float, log: Log,
                      attempts: int = 5, connect=None, sleep=time.sleep):
    """Attach to a live Zotero over RDP, retrying with backoff.

    A bare `.connect()` was found unreliable against this host in ticket 0766's
    own runs, which is why every routine call in the volume driver goes through
    this. It lives here rather than there so the ONE call that cannot be
    repeated -- the parked-ring read at a real alert -- gets the same treatment
    as the routine ones rather than a fresh single-shot connect.

    `connect` is injectable so a test can drive the retry without a Zotero.
    """
    if connect is None:
        from zotero_rdp_client import ZoteroRDPClient  # noqa: PLC0415 -- optional

        connect = ZoteroRDPClient.connect
    last = None
    for attempt in range(1, attempts + 1):
        try:
            client = connect(host, port, timeout=timeout)
            client.attach_chrome_target(timeout=timeout)
            return client
        except Exception as exc:  # noqa: BLE001 -- every failure here is retryable
            last = exc
            log.write(f"rdp connect attempt {attempt}/{attempts} failed: {exc}")
            if attempt < attempts:
                # `sleep` is injectable for the same reason `connect` is: a
                # suite that really waited the backoff would be a suite nobody
                # runs, and the backoff is not what these arms are about.
                sleep(min(2 * attempt, 10))
    raise RuntimeError(f"could not attach over RDP after {attempts} attempts: {last}")


def make_ring_reader(port: int, log: Log, connect=None, sleep=time.sleep):
    """A callable that attaches over RDP and reads the parked ring.

    Connected at alert time and not before: this watcher is meant to run for
    days against a profile whose Zotero is restarted whenever its owner feels
    like it, and a connection held across that is a connection that is not there
    when it matters. The cost of connecting late is that the connect itself can
    fail at the one moment it must not, which is what `connect_resilient` is for
    -- a single-shot connect here would throw away the only reading of Gecko's
    own reason over a hiccup, on an event that took six days and two machines to
    see twice.
    """
    def read() -> str:
        client = connect_resilient("127.0.0.1", port, 20.0, log, connect=connect, sleep=sleep)
        try:
            return client.eval_js(READ_PARKED_RING_JS, timeout=20.0)
        finally:
            client.close()
    return read


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, required=True,
                        help="the Zotero PROFILE directory (holds extensions.json)")
    parser.add_argument("--data-dir", type=Path,
                        help="the Zotero DATA directory, where the death certificate is written")
    parser.add_argument("--log", type=Path, required=True,
                        help="transition log; give it a .txt name, .log is repo-gitignored")
    parser.add_argument("--evidence-dir", type=Path,
                        help="where to copy the evidence when the signature fires")
    parser.add_argument("--rdp-port", type=int,
                        help="debugger port of the live Zotero, to read the parked ring")
    parser.add_argument("--addon-id", default=ADDON_ID)
    parser.add_argument("--poll-seconds", type=float, default=1.5)
    parser.add_argument("--max-hours", type=float, default=0.0,
                        help="stop after this long; 0 means run until interrupted")
    args = parser.parse_args(argv)

    if args.log.suffix == ".log":
        print(refuse_dot_log(args.log), file=sys.stderr)
        return 2
    if not (args.profile / "extensions.json").exists():
        print(f"no extensions.json under {args.profile}: is that a Zotero profile?",
              file=sys.stderr)
        return 2

    log = Log(args.log)
    log.write(f"watcher starting on {args.profile} for {args.addon_id}")
    read_ring = make_ring_reader(args.rdp_port, log) if args.rdp_port else None
    watcher = Watcher(args.profile, args.addon_id, log,
                      poll_seconds=args.poll_seconds,
                      evidence_dir=args.evidence_dir,
                      data_dir=args.data_dir, read_ring=read_ring)
    deadline = time.monotonic() + args.max_hours * 3600 if args.max_hours else None
    watcher.start()
    try:
        while not watcher.disappearance.is_set():
            if deadline is not None and time.monotonic() > deadline:
                log.write("watcher stopping: --max-hours reached, no disappearance seen")
                return 0
            time.sleep(1)
        log.write("watcher REPRODUCED -- the evidence above is the finding")
        return 3
    except KeyboardInterrupt:
        log.write("watcher interrupted")
        return 0
    finally:
        watcher.stop()
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
