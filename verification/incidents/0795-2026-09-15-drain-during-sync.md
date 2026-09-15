# The drain starves the sitter while Zotero syncs files — 2026-09-15, v0.4.16

Tickets: [0796](../../tickets/0796-the-drain-loop-starves-reconciliation-and.erg)
owns the defect, [0795](../../tickets/0795-pause-the-sitter-while-zotero-is-syncing.erg)
owns the trigger.
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
  emptied `dirty` — and § The mechanism shows it was never going to.

## The mechanism — measured, and it is starvation, not a lost race

**Superseded reading, kept because it was wrong in a way worth naming.** This
file first proposed "a race the drain loses, not a wedge": the drain retiring
dirty ids slightly slower than the sync produces them. Three live reads of
`state.draining` refuted it. The loop does not merely fall behind; it never
returns control.

`Zotero.SDTPackSitter.state`, read three times on the live instance:

| | `draining` | `phase` | `pending` | `busy` | `active` |
|---|---|---|---|---|---|
| `drain-start`, 19:39:10Z | 761 | draining | — | — | — |
| ~19:57Z | **6495** | draining | 44 | true | null |
| +~1 min | **6543** | draining | 44 | true | null |
| +~1 min | **6573** | draining | 44 | true | null |

`storage/`: 688 attachment folders at 19:39, 6 168 at 19:58. The backlog grew
8.5× while the drain ran. The candidate queue never moved.

The structure that produces this, all in `scheduler.js`:

- the outer loop is at 140; its body is reconciliation (143-176), then the drain
  (196-226), then admission (228+);
- the drain is a nested `while (dirty.size && current())` at 201 with **no
  bound** — it returns to 140 only when `dirty` is empty;
- `invalidate(ids)` (129) refills `dirty` from item notifications, and each drain
  iteration pays a library-wide `host.unattached()` (215-218).

So while notifications outrun the drain:

1. **`refreshQueue()` (99, called only at 176) never re-runs**, so `state.pending`
   is frozen at the last census's snapshot. That is why `pending` reads 44
   throughout — it is a photograph from 19:39, not a live count. Files that have
   arrived since and become indexable never enter the candidate list.
2. **Admission (228+) is never reached**, so `active` stays `null` and nothing is
   ever submitted.
3. `busy` stays true and the heartbeat keeps firing, so nothing reports a fault.

The sitter does no work at all, and cannot resume while `dirty` grows. Split out
as ticket [0796](../../tickets/0796-the-drain-loop-starves-reconciliation-and.erg):
0795 removes the most common trigger, 0796 makes the loop safe.

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
