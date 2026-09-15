# Toggling the switch does not recover the starved sitter — 2026-09-15, v0.4.16

Ticket: [0796](../../tickets/0796-the-drain-loop-starves-reconciliation-and.erg).
Source: `sdt-sitter-last-shutdown.json`, written at the plugin's uninstall
(`"reason": "uninstall"`, 2026-09-15T20:31:54.885Z) on padme, Zotero 10.0.2,
sitter v0.4.16. The ring holds 50 records and was full, so anything before
20:03:07Z had rolled off.

This file answers the question
[0795-2026-09-15-drain-during-sync.md](0795-2026-09-15-drain-during-sync.md)
left open, and **refutes the workaround that file and this session recommended.**

## The ring

```
20:03:56 → 20:07:56   heartbeat  draining  pending 44          (five, frozen)
20:08:56              heartbeat  draining  pending 92
20:09:56 → 20:15:56   heartbeat  draining  pending 149 … 389   (climbing)
20:16:55   switch OFF
20:16:56   sweep-end  switched-off  scanned 16856  completed 0  failed 13749  pending 436
20:16:57   switch ON  → sweep-start → announce census
20:17:57 → 20:19:57   heartbeat  census    pending 436
20:20:27   drain-start  pending 9727
20:20:57   heartbeat  draining  pending 8926
20:21:57   heartbeat  draining  pending 8926
20:22:53   switch OFF
20:22:53   sweep-end  switched-off  scanned 16856  completed 0  failed 5242  pending 8926
20:22:56   switch ON  → sweep-start → announce census
20:23:22   drain-start  pending 9597
20:23:56 → 20:30:56   heartbeat  draining  pending 8926        (eight, frozen)
20:31:54   switch OFF, shutdown reason=uninstall
```

Every heartbeat: `id: null`, `progress: null`, `elapsedMS: null`,
`sinceProgressMS: null`.

## What it establishes

**The toggle works, and does not help.** `stop()` bumps `epoch`
(`scheduler.js:124`) so the drain exits through its `if (!current())` guards, and
`start()` sets `reconciliationPending` (126). Both toggles are followed within
two seconds by `announce phase=census`, so the forced reconciliation is real.

**The census does its job.** Between the two sweeps `failed` falls 13 749 →
5 242 and `pending` rises 436 → 8 926: the attachments whose files arrived during
the sync were reclassified out of `missing-source` (class `failed`) into a queued
status, exactly as `SDT_STATUS_CLASSES` (`scheduler.js:31-33`) predicts.

**And then the drain re-starves, every time.** Each census is followed by a
`drain-start` of ~9 600 dirty ids, after which `pending` freezes and `active`
stays null. Seven minutes on the second attempt, until the uninstall.

**Nothing was ever indexed.** `completed: 0` in both `sweep-end` records.
8 926 admissible candidates sat ready and not one was submitted.

**The sitter does recover on its own when the notification source stops** — the
20:08→20:15 climb from 44 to 389 is `refreshQueue()` running again, which only
happens at `scheduler.js:176`, which is only reachable when the drain empties.
So the starvation is not a permanent wedge; it lasts exactly as long as
notifications outrun the drain. With a library this size the drain cannot get
ahead, because each dirty id costs a library-wide `unattached()`.

## The correction

This session told the author, twice, and told a sister session, that toggling the
switch off and on was the workaround for 0796. **That is measured false.** The
toggle forces a census; it does not get a document indexed. There is no known
workaround — 0796 has to be fixed in the loop.

The error was inference from code reading (`stop()` clears the loop, `start()`
forces reconciliation — both true) without measuring what happens next. The ring
above was available the whole time in the shutdown file the release notes
document, and was not read until the plugin was uninstalled and it nearly rolled
off.

## Counts at shutdown

`notIndexed`, per bucket, keys withheld per the redaction convention of
`0793-2026-09-15-ar6-stall.json` — they are item keys of a private library:

| bucket | count |
|---|---|
| `missing-source-stored` | 5 239 |
| `missing-source-linked` | 3 |
| `no-extractor` | 2 668 |
| `mismatched-type` | 17 |
| `no-attachment` | 2 275 |
| **total** | **10 202** |

`scanned: 16 856` — the library grew past the 13 780 of the earlier census as the
sync continued. `nativeVersions`: `SDT_SCHEMA_VERSION 1.2.0`, `SDT_PACK_VERSION 1`,
processors `pdf 14`, `epub 2`, `snapshot 1`.

## Consequence for the fix

0796's red test should assert admission is reached, not merely that the outer
loop advances: both toggles proved the outer loop can be forced round without a
single `admit`. A bound on the inner drain has to leave enough of each outer
iteration for admission to run.
