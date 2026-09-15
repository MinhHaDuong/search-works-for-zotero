# Drain does not converge while Zotero syncs files — 2026-09-15, v0.4.16

Ticket: [0795](../../tickets/0795-pause-the-sitter-while-zotero-is-syncing.erg).
Captured from the author's Technical diagnostics panel on padme, Zotero 10.0.2,
sitter v0.4.16 (`sha256 1ee8f0ed33d392b6…`), three libraries, while a bulk file
sync was running.

**This is not the 0793 AR6 plateau.** The comparison is in § Two phenomena
below, and the distinction is what makes this one cheap to reproduce.

## The record ring, verbatim

The ring is bounded at 50; it held 19, so nothing rolled off and the absence of
`drain-end` below is real rather than truncation.

```
19:38:47Z  +  0.0s   cache-load     records=0
19:38:54Z  +  6.7s   dialog-open
19:38:55Z  +  8.3s   switch         enabled=true
19:38:55Z  +  8.3s   sweep-start
19:38:58Z  + 10.4s   announce       phase=census
19:39:09Z  + 22.3s   cache-write    rows=2   (censusComplete)
19:39:10Z  + 22.4s   drain-start    pending=761
19:39:11Z  + 24.3s   announce       phase=draining
19:39:55Z  + 68.3s   heartbeat      pending=44
19:40:55Z  +128.3s   heartbeat      pending=44
19:41:55Z  +188.3s   heartbeat      pending=44
19:42:55Z  +248.3s   heartbeat      pending=44
19:43:55Z  +308.3s   heartbeat      pending=44
19:44:55Z  +368.3s   heartbeat      pending=44
19:45:55Z  +428.3s   heartbeat      pending=44
19:46:55Z  +488.3s   heartbeat      pending=44
19:47:55Z  +548.3s   heartbeat      pending=44
```

Every heartbeat: `id: null`, `phase: "draining"`, `progress: null`,
`elapsedMS: null`, `sinceProgressMS: null`, `pending: 44`.

No `drain-end` in 8 minutes 0 seconds, and the panel was still in this state
when the dump was taken.

## What the two `pending` figures are, because they are not the same quantity

- `drain-start`'s `pending: 761` is `dirty.size` (`scheduler.js:198`) — the
  notification backlog.
- the heartbeat's `pending: 44` is `s.pending.length` (`bootstrap.js:645`) — the
  candidate queue, items the census classified as needing work.

Reading the second as the first is the mistake this session made first, and it
inverts the diagnosis: the 44 is not what the drain is chewing through. It
matches the panel's own "Indexed by an older extractor: 44" exactly, which is
consistent with the candidate queue being the stale-processor set and being
untouched throughout — but nothing here establishes that identification.

## What the state proves about where the pump is

- `bootstrap.js:641` — the heartbeat returns early unless `busy` is true or
  `active` is set. `active` is `null`, so **`busy` is true: `pump()` has been
  executing for the whole 8 minutes.**
- `phase` is `draining`, set at `scheduler.js:197`, so the pump is inside the
  drain loop at `scheduler.js:201-222`.
- `drain-end` (`scheduler.js:225`) never fired, so `while (dirty.size)` never
  emptied `dirty`.

## The mechanism, stated as a candidate and not as a verdict

The drain loop calls `host.unattached()` on **every** iteration
(`scheduler.js:215-218`) — a library-wide query per dirty id, which the loop's
own comment (`scheduler.js:193-195`) already names as "long on its own account".
`invalidate(ids)` (`scheduler.js:129`) refills `dirty` from Zotero item
notifications, which a bulk file sync generates continuously: `storage/` went
from 688 attachment folders at 19:39 to 2 893 at 19:47, about 1 000 files a
minute, under the heaviest DB and disk contention of the session.

So the candidate reading is **a race the drain loses, not a wedge**: it pays a
full-library query per notification while the sync produces notifications faster
than it can retire them. That is consistent with every figure above and with no
`drain-end`, but it is not established.

**The one measurement that settles it, not yet taken:** read
`Zotero.SDT.sitter.state.draining` (which is `dirty.size`, `scheduler.js:220`)
three times a few seconds apart on a live instance in this state. Falling means
the race reading is right and 0795 dissolves the incident. Holding or rising
means something else, and it earns its own ticket. The author was asked for this
while the state was live; if it is not in this file, it was not obtained.

## Two phenomena, not one

| | 0793, AR6, 2026-09-15 | this file |
|---|---|---|
| `phase` | `extracting` | `draining` |
| `id` | 11940 | `null` |
| `progress` | frozen at 90 | `null` |
| `sinceProgressMS` | climbing to 172 724 | `null` |
| stuck | **inside** one extraction | **before** admitting any |
| scale | 10 493 candidates, 3 949 pages | 44 candidates |

The nulls here are not an instrumentation gap: `verification/incidents/0793-2026-09-15-ar6-stall.json`
shows the same heartbeat naming its item and its progress when there is one.
They are what a heartbeat reports when nothing is in extraction. This session
first read them as a missing instrument, which was wrong.

## Not recorded here

The dump's `notIndexed` buckets and their counts. They hold Zotero item keys of
a private library and the 0793 artifact's redaction convention keeps per-bucket
counts only; the counts were not transcribed because the pasted dump was not
saved to a file. `nativeVersions` at capture: `SDT_SCHEMA_VERSION 1.2.0`,
`SDT_PACK_VERSION 1`, processors `pdf 14`, `epub 2`, `snapshot 1`.
