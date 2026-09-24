---
paths:
  - "tickets/**"
---

# Tickets: stamping logs and reading state

Scoped from `AGENTS.md` § Conventions and § Upstream relations. The ticket
store's own rules are `tickets/AGENTS.md`.

- **Stamp ticket logs with `erg log`**, which reads the real clock. A
  hand-typed stamp is how log entries came to name times that had not
  happened, and `bench/check_ticket_logs.py` now fails on one stamped after
  the commit that wrote it. Out-of-order logs are fine and are not checked:
  parallel sessions merge into one log.

## Why the fork is read before filing new code

`AGENTS.md` § Upstream relations states the rule: before filing a ticket that
specifies new code, read the fork's `src/` and `SYNC.md`'s upstream rows. The
code lives in the fork, a separate repository, so no search of *this*
repository can see it, and a null here reads exactly like a real absence.
Ratified 2026-09-03, after two of tracker 0557's children were filed for work
that had already shipped. Both were filed 2026-09-01: 0560 asked for
embedded-TOC extraction, which shipped upstream on 2026-08-29 in v1.10.0 as
`extractPdfOutline`, and 0558 asked for attachment file access, which shipped
in that same release — recorded in `SYNC.md` as issue #29, closed COMPLETED
2026-08-29. Reading either source would have prevented both.

The same session also made the mirror error, and it is worth naming separately
because the remedy differs: seg/1 was reported *unbuilt* when it had been built
and tested the previous day on a fork branch. Nothing was mis-filed there —
ticket 0028 predates the code, correctly — the reading of its state was wrong.
For that direction the fix is to read the ticket's own log, which carried the
branch, the SHA and the measurements throughout.
