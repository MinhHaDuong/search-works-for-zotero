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
```
