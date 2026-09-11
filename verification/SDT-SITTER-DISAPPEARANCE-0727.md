# The sitter's disappearance, recorded rather than recalled (ticket 0727)

Every state change of the add-on's installation on doudou, 2026-09-06/07,
written by `scratchpad/sitter-watch.sh`: the host's own record, whether that
record is active, whether the XPI is on disk, and Zotero's pid. A line is
written ONLY when one of those changes, so the gaps are the finding as much as
the lines are.

Ticket 0688 spent weeks unable to name the cause because every occurrence was
noticed after the fact, with the record and the file already gone. This is the
first time the transitions were captured while they happened.

## What it shows

**Refined 2026-09-07 00:51.** 0.3.1 was installed into pid 1057602, the process
that had held 0.3.0 for forty minutes, and vanished in twenty seconds. So the
survivor was not the process but the FIRST install into it. Every loss tonight
was a replacement into a process that already had this add-on; every survival
was a first install. That is the candidate now, and neither arm has been run
deliberately.


Six install cycles, all inside pid **635164** (up since 20:56), end in
disable-then-delete: active for 20-80 seconds, then `active=False`, then the
record and the XPI both gone. The seventh, into a **fresh** process (pid
1057602, started 00:30:04), went active at 00:30:43 and stayed.

Every failing cycle ran in a process that had already had this add-on installed
and force-removed under it. That is the candidate ticket 0727 now carries, and
it displaces the `update_url` mechanism the ticket was opened on: 0.2.15 shipped
with a compatible version advertised and died exactly like the empty-list
builds before it.

Not a controlled experiment. Both arms happened by accident, which is why the
ticket calls this a candidate and names the two runs that would settle it.

```
# sitter-watch started 2026-09-06T23:42:09+02:00
2026-09-06T23:42:09+02:00  record=absent xpi=absent zotero_pid=635164
2026-09-06T23:49:31+02:00  record=present:0.2.13:active=True xpi=present zotero_pid=635164
2026-09-06T23:49:51+02:00  record=present:0.2.13:active=False xpi=present zotero_pid=635164
2026-09-06T23:54:32+02:00  record=present:0.2.15:active=True xpi=present zotero_pid=635164
2026-09-06T23:54:52+02:00  record=present:0.2.15:active=False xpi=present zotero_pid=635164
2026-09-06T23:55:12+02:00  record=absent xpi=absent zotero_pid=635164
2026-09-07T00:10:57+02:00  record=present:0.2.16:active=True xpi=present zotero_pid=635164
2026-09-07T00:16:59+02:00  record=absent xpi=absent zotero_pid=635164
2026-09-07T00:27:02+02:00  record=present:0.3.0:active=True xpi=present zotero_pid=635164
2026-09-07T00:28:22+02:00  record=present:0.3.0:active=False xpi=present zotero_pid=635164
2026-09-07T00:28:42+02:00  record=absent xpi=absent zotero_pid=635164
2026-09-07T00:30:23+02:00  record=absent xpi=absent zotero_pid=1057602
2026-09-07T00:30:43+02:00  record=present:0.3.0:active=True xpi=present zotero_pid=1057602
2026-09-07T00:50:28+02:00  record=present:0.3.0:active=False xpi=present zotero_pid=1057602
2026-09-07T00:50:48+02:00  record=present:0.3.1:active=True xpi=present zotero_pid=1057602
2026-09-07T00:51:08+02:00  record=absent xpi=absent zotero_pid=1057602
```

## Arm 5 — volume experiment, cut short by the author (2026-09-11)

The candidate the four deliberate arms above never isolated: cumulative
install/replace/disable/enable count in ONE continuously-running process.
Each prior arm tested exactly one transition; the two real occurrences were
both organic, long sessions with several rapid GUI replacements. Ticket 0766
built an external RDP client (`bench/zotero_rdp_client.py`) precisely so this
could be automated instead of needing a human at Tools -> Add-ons for every
cycle; `bench/sitter_volume_experiment.py` (ticket 0727) is the driver.

**This is a BOUNDED negative result, not a completed one.** The run was
planned for ~50 cycles or ~2 hours, whichever came first. The author asked
for it to stop after roughly half an hour, with no time to let it finish. It
was stopped cleanly (current cycle allowed to finish; the driver process does
not install a `SIGTERM` handler, so it exits immediately rather than running
its own cleanup — the headless Zotero subprocess was then terminated by hand,
confirmed gone by PID, and the profile removed) rather than left running or
killed mid-eval. What follows is what 17 cycles said, not what 50 would have.

**Setup.** A dedicated, throwaway profile (never the author's real profile or
library), Zotero 10.0.2, headless, `--start-debugger-server`. One continuous
process throughout, pid 393974, from launch to the manual shutdown below —
every log line carries the same `zotero_pid`. Each cycle: build a
version-bumped, otherwise byte-identical payload (arm 2's own isolation
discipline) from the real `plugins/sdt-sitter/` source into a scratch
`.xpi`, drive the exact `AddonManager.getInstallForFile` +
`installAddonFromAOMWithOptions` sequence a real "Install Add-on From File"
click runs (never `AddonsActor.installTemporaryAddon`), then `disable()`
then `enable()`. A background watcher polled only `extensions.json` + the
`.xpi`'s presence on disk — independent of the action loop's own cadence —
and logged a line only on change, the same grammar the arms above used.

**Result: 17 cycles (1 first install + a 6-replacement rapid-succession
burst mimicking the organic 2026-09-08 recurrence shape more closely than any
prior arm, spaced ~60 s apart, then 10 further replacements spaced ~150 s
apart), over ~31 minutes, zero disappearances, zero RDP anomalies (no
timeout, no reconnect, no eval exception across all 17 install/disable/enable
triples).** The add-on was present and active at every sampled point and
remained so at shutdown. This narrows nothing conclusively: 17 cycles in 31
minutes is real volume no prior arm reached, but it is well short of the
~50-cycle/~2-hour budget this arm was designed for, and the untested part of
the "intermittency under volume" candidate — whatever count or duration it
takes to fire, if it is real — remains untested. Do not read this as "volume
is exonerated"; read it as "the first 17 cycles of a real attempt to test
volume came back clean."

Raw log: `bench/results/sdt-sitter-2026-09-11/run-watch.txt`.

```
2026-09-11T15:33:45Z driver starting: profile=/tmp/zotero-0727-volume/run-profile addon_id=sdt-pack-sitter@search-works-for-zotero.invalid burst_cycles=6 spaced_cycles=43 max_minutes=120.0
2026-09-11T15:33:46Z record=unreadable:/tmp/zotero-0727-volume/run-profile/extensions.json does not exist xpi=absent zotero_pid=393974
2026-09-11T15:33:48Z record=present:9.0.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:34:48Z record=present:9.2.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:35:48Z record=present:9.3.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:36:48Z record=present:9.4.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:37:48Z record=present:9.5.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:38:48Z record=present:9.6.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:39:48Z record=present:9.7.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:42:18Z record=present:9.8.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:44:48Z record=present:9.9.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:47:18Z record=present:9.10.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:49:50Z record=present:9.11.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:52:20Z record=present:9.12.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:54:50Z record=present:9.13.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:57:20Z record=present:9.14.0:active=True xpi=present zotero_pid=393974
2026-09-11T15:59:50Z record=present:9.15.0:active=True xpi=present zotero_pid=393974
2026-09-11T16:02:20Z record=present:9.16.0:active=True xpi=present zotero_pid=393974
2026-09-11T16:04:50Z record=present:9.17.0:active=True xpi=present zotero_pid=393974
```

(Trimmed to one state line per cycle for readability; the install/disable/enable
action lines between each are in the committed raw log.)

**What remains.** Re-run this same driver for the full ~50-cycle/~2-hour
budget when there is time to let it finish or to watch it live. If it
reproduces at any point, that settles the volume candidate as real and the
next question becomes which count or elapsed time it takes; if it completes
the full budget clean, that is real (though still not conclusive) evidence
against volume alone being sufficient, and the remaining candidate from the
2026-09-08 reopening note — build-specific payload differences across the
organic session's five installs — would move to the front.
