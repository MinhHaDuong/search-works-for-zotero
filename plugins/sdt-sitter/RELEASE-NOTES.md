# SDT pack sitter — release notes

Prepares Zotero 10's structured document text ahead of demand, so that a search
does not wait for extraction. An experiment, offered as one.

**Requires Zotero 10.0.1 or later, 10.x only.** The resource guards described
below are Linux-only.

## One outbound request, and it is not ours

Installing the sitter causes one outbound request, and the plugin is not what
makes it. `manifest.json` declares an update manifest served from this
repository's `main` branch on `raw.githubusercontent.com`, and Zotero's own
add-on update check fetches it about once a day for as long as the add-on stays
installed, at the host cadence owned by
[SPEC.md §6](../../SPEC.md#6-security-considerations) — where the interval, its
provenance and the rest of this surface are recorded. That check is not
optional: ticket 0727 established with a control that a build identical but for
the removal of `update_url` is refused at install ("peut-etre incompatible avec
cette version de Zotero"), so an add-on that declares none cannot be installed
at all. The request is for a fixed URL: nothing about the library is sent, and
the sitter opens no network connection of its own, here or anywhere else. What
the fetch necessarily discloses to the other end is the requesting address and
that this add-on's manifest is being checked; whether the host adds the
installed version to the check has not been read here.

## Unreleased

### Indexing

- Indexing is driven by events rather than by repeated full-library sweeps.
  Attachment and file-download notifications update only what changed.
  Reconciliation runs at startup, on re-enabling, and periodically.
- A pack counts as containing no text only when its own page catalogue reports
  every page fully analysed. A page that fell back to degraded extraction, or a
  catalogue that cannot be read, leaves the answer unknown instead of claiming
  there is nothing there.
- Work interrupted for resources resumes without rescanning the library.
- Missing files stay in Zotero and keep their packs.

### The window

- The "Not indexed" list groups obstacles: unavailable files, unsupported
  formats, failures from this session, and records with no file attached. It
  shows error classes and identifiers, never filesystem paths or raw host
  errors.
- The resting sentence says *which* kind of rest: everything in view indexed,
  attachments waiting for the next pass, or a pass that ended with attachments
  it could not index.
- A status region announces changes of state to screen readers — scanning,
  waiting for resources, an error, indexing switched on or off — and never the
  progress figures. Opening the window announces nothing.
- The notice at the end of indexing now appears **once per stretch of work**
  instead of after every thirty-second pass. A single file added to an
  up-to-date library is still announced as soon as it is done.

### Keyboard

- The toolbar control can be focused and opened with Enter, and the window
  closed with Escape. Opening the window puts focus on the indexing switch.

### Removal and diagnostics

- Removing the add-on turns the indexing switch off rather than leaving it
  unset, so installing again starts stopped — toolbar and window present, one
  click to start, and no repeat of the first-run question. Disabling, quitting
  and upgrading in place leave the switch alone.
- Removing the add-on also deletes its cache file and clears its diagnostics
  preference. A removed add-on leaves nothing behind.
- If Zotero removes the add-on without telling it, the sitter notices within a
  minute and says so in its own window: indexing has stopped, nothing already
  indexed is lost, reinstall to resume. It does not reinstall itself and sends
  nothing anywhere.
- With technical diagnostics on, an ordinary disable or removal writes
  `sdt-sitter-last-shutdown.json` to the Zotero data directory, carrying the
  host's own reason and the last few state changes. Off by default, and off
  means nothing is written.
- Cached timing observations carry a schema number. Observations from an
  earlier build are re-measured rather than trusted — visible once, on first
  use of this build.

## If the add-on disappears from Tools → Add-ons

This has happened, the cause is not known, and the order of these two steps is
the whole of the instruction.

**First, before restarting anything**, open Tools → Developer → Run JavaScript,
evaluate `JSON.stringify(Zotero.SDTPackSitterJournal.tail(200))`, copy the
result and report it.

**Then** restart Zotero and install again.

That record lives only as long as the Zotero process. A restart destroys it,
and in this failure it is the only copy there is.

## Known limitations

- **The add-on has disappeared from a running profile.** Seen repeatedly over
  one instrumented evening and once more two days later, on one machine. The
  cause is not established
  ([0727](../../tickets/0727-the-sitter-uninstalls-itself-update-url.erg)).
  Nothing already indexed is lost when it happens.
- **The window is not qualified accessible.** Whether a screen reader speaks
  the announcements usefully has not been heard; the layout at enlarged font
  sizes has not been examined; and tab order is unconfirmed — the toolbar
  control takes focus, but Zotero routes its own toolbar buttons through a
  keyboard path this add-on is not part of, so being focusable is not yet being
  reachable ([0769](../../tickets/0769-verify-sitter-panel-keyboard-and-screen-r.erg),
  [0787](../../tickets/0787-the-toolbar-control-is-focusable-but-may.erg)).
- **On Zotero 10.0 the add-on installs and then does nothing.** 10.0 is below
  the declared minimum, so Zotero marks it incompatible and disables it: it
  appears in the add-ons list, inert. Upgrade rather than wonder why nothing
  happens.
- **A future major Zotero will set the add-on aside.** The declared ceiling is
  10.x. On such an upgrade, expect it installed and disabled, with nothing lost
  from the library and nothing removed from Zotero's own text index. That is
  deliberate: this add-on works through parts of Zotero that carry no
  compatibility promise.
- **Resource guards are Linux-only.** Free memory, load average and free disk
  are read from `/proc`. On other platforms the memory and load checks are
  skipped and indexing proceeds without them.
- **Indexing that wedges is silent.** The end-of-work notice waits for the work
  to finish, so a job that never finishes produces no notice at all. A notice
  on a timer would make a stuck job look like a working one
  ([0788](../../tickets/0788-one-toast-per-stretch-of-work-and-no-tim.erg)).
  The window keeps showing live progress either way.
- **Only two Zotero versions have been exercised** against real documents:
  10.0.1, and 10.0.2 including the upgrade between them, where the sitter
  discarded every cached answer and prepared the documents again.

---

The rest is written for a Zotero developer rather than for someone installing
the add-on. Nothing below is needed to use the sitter.

- [Design notes](DESIGN-NOTES.md) — what this build is an experiment in: the
  scheduling experiment, the removed controls, the concurrency model it did not
  replace, and why preparation ahead of demand matters.
- [Scheduling report](../../verification/SDT-SITTER-EVENTS.md) — implementation
  and host-mock verification.
- [Launch report](../../verification/SDT-SITTER-LAUNCH.md) — experimental scope
  and operational limits.
- [Lifecycle audit](../../verification/SITTER-LIFECYCLE-AUDIT-2026-09-12.md) —
  including findings not addressed in this release.
