# SDT sitter UI panel — 2026-09-05

Requested by the author during implementation. Both reviewers inspected the
pre-cache grouped-dialog source (unreleased extension version 0.1.3), not a
screenshot or a live assistive-technology session. Tickets 0684 and 0685 cite
this review; this report is evidence, not a design ruling or merge approval.

## Verdicts, as received

`sitter_ux_review`: **APPROUVÉ AVEC RÉSERVES pour un usage expérimental cette nuit**,
followed by “pas encore une interface de supervision aboutie.”

`sitter_accessibility_review`: **CHANGES REQUESTED pour qualifier l’UI d’accessible ;
pas de blocage fonctionnel démontré pour l’usage visuel à la souris.**

Both reviewers credit the global/document separation, named native progress
bars, system foreground/background colors and separate native fulltext stats.

## Findings and disposition

- UX: elapsed time clipped from all remaining-duration scenarios can yield
  zero while the active job is still running. Addressed in the combined cache
  and finish-clock implementation: overrun makes the finish estimate unknown.
- UX: final `waiting` does not distinguish fully current from incomplete
  coverage; raw English states do not explain what happens next. Built in
  ticket 0686 (0.3.43): at rest the sentence reads the coverage accounting and
  names which of its three states holds -- everything in view indexed, work
  admissible for the next pass, or a pass finished with attachments it cannot
  index -- and both exceptional states can be named at once. "Everything" is
  the identity `current === total` over the scheduler's own classes, not a
  fourth opinion about the library; out-of-scope records are out of the
  denominator and cannot hold a current library short of it. It points rather
  than explains: each obstacle's own reason and remedy already sit, per class,
  in the Not indexed layer. `ready` keeps the bare sentence -- no walk has
  finished, so there is no measurement to report. Eight wordings in
  `tests/sdt_sitter_dialog.mjs`, two scenarios in
  `tests/sdt_sitter_bootstrap.mjs` and three mutants (M37-M39).
- Both: internal item ID alone does not identify a document for the user.
  Follow-up: display title or filename, keep ID as a diagnostic detail.
- Both: detailed global diagnostics precede the active document and increase
  reading burden. Potential viewport overflow is unverified without rendering
  at enlarged font sizes. Follow-up: fold detailed counts and methodology.
- Accessibility: spinner changes the button label; provide a stable accessible
  name and respect reduced-motion preference. Built in ticket 0686: `aria-label`
  now pins the accessible name to the coverage figure alone, and the spinner,
  the census pulse and the completion blink all stop under
  `prefers-reduced-motion: reduce`. One scenario per animation in
  `tests/sdt_sitter_bootstrap.mjs`, each with the motion arm as its positive
  control, and asserted in a real window by the sitter harness probe. Whether a
  screen reader in fact speaks that name is a live-session reading no unit test
  takes.
- Accessibility: announce meaningful state transitions through a small status
  region, not all second-by-second text. Built in ticket 0686 (0.3.42): one
  visually hidden `role="status"` node, `aria-live="polite"`,
  `aria-atomic="true"`, written only when the switch line -- the window's one
  sentence about the machine's state -- has been gone for two seconds. Timing
  the absence and not the replacement is what keeps a machine alternating
  between two states from going unannounced altogether; the first form shipped
  timed contiguity and was reviewed out. Opening the window announces nothing;
  progress, file names and estimates never reach it. Five scenarios in
  `tests/sdt_sitter_bootstrap.mjs` -- the speaking scenario is the positive
  control for the two silence scenarios -- and six mutants (M31-M36) in the
  bootstrap mutation gate. What no headless lane establishes: whether Orca in
  fact speaks any of it, which is ticket 0769's reading.
- Accessibility: verify keyboard access, initial focus, Escape/close and focus
  restoration. Current smoke uses programmatic command dispatch and cannot
  establish those behaviors. Follow-up.
- UX: clarify that native document percent is neither elapsed-time fraction nor
  cache persistence completion. Native ensure plus cache verification already
  gates completion; clearer UI wording remains follow-up.

The isolated smoke establishes rendered width, opaque system colors and dark
preference, wrapping, named group structure, coverage values, native fixture
generation, stats presence and disable cleanup. It does not establish keyboard
navigation, screen-reader announcements, reduced-motion behavior or absence of
overflow at large font sizes. No reviewer was asked to post a forge verdict;
no pull request was opened or merged.

## 2026-09-13 — the keyboard reading, taken at last (ticket 0769, action 1)

Everything above this heading says the keyboard behaviour was not established.
It is now, in a real Zotero 10.0.1 window with the sitter armed over three
Menagerie documents, and it found two defects rather than confirming the panel.

**The panel could not be reached from the keyboard at all.** The toolbar control
is a XUL `toolbarbutton`, not focusable by default, and it carried no
`tabindex`. `button.focus()` left focus on Zotero's search box; adding
`tabindex="0"` moved it to the button on the very next call; the search box took
focus throughout, which is the control ruling out a window that simply refuses
to focus anything. Fixed with that one attribute.

**The panel placed no initial focus.** It opened with `activeElement` still on
`<body>`. It now focuses its first control, the switch row.

Read back from OUTSIDE the process over AT-SPI — the same interface Orca uses,
and a reading the plugin's own `getAttribute('aria-label')` cannot give, because
that asserts what the markup says rather than what the accessibility layer
computed:

| id | role | accessible name | states |
|----|------|-----------------|--------|
| `sdt-pack-sitter-button` | push button | `Index 100 %` | focusable, enabled, showing, visible |
| `sdt-switch` | push button | `Turn indexing off` | |
| `sdt-global-progress` | progress bar | `Overall progress` | |
| `sdt-announcer` | status bar | (empty at rest) | `live: polite`, `atomic: true`, `container-live-role: status` |

The `focusable` state was demonstrated causally, not asserted: with the running
window untouched otherwise, removing `tabindex` live over RDP and re-walking the
tree returned `enabled, showing, visible` and **no `focusable`**; restoring it
brought the state back. Same process, same window, one attribute.

`sdt-announcer` carries exactly the live-region attributes ticket 0686 item (1)
intended, exposed to AT-SPI as a polite atomic status region. An earlier reading
in this session looked at `sdt-status` — the VISIBLE text — found no
`aria-live` on it and briefly took that for a defect. It is not one: the
announcer is a separate visually-hidden node, and the distinction is the whole
reason it exists.

### What is NOT established, and why

**Tab ORDER.** Not a failure — unobservable from here.
`windowUtils.sendKeyEvent` is gone in the Gecko 140 these Zotero 10 builds ship;
`sendNativeKeyEvent` is accepted without error and delivers nothing, because
the window reports `hasFocus === false` on the test display; a dispatched Tab
does not move focus. `verification/probes/sdt_panel_keyboard.js` runs that as a
CONTROL before the assertion depending on it and reports NOT-ESTABLISHED rather
than pass or fail. Each summary is separately shown to accept focus, which is
weaker and is labelled as such. Settling it needs a session with real X focus.

**Whether Orca speaks.** The markup is now known to be right and the tree is
known to expose it, which is a necessary condition and not a sufficient one.
What no reading here establishes is whether Orca in fact utters the transition
sentences, in what words, and at a useful moment.

### The red arm

`run_panel_keyboard.py --break-escape` removes the panel's Escape handling from
a scratch copy of the payload and refuses to run if the removal matched nothing.
With it, the Escape assertion goes red and every other assertion stays green.

Not red-armed, and said rather than glossed: **focus-return**. It passed in the
broken arm too, because focus was already on the button when the panel failed to
close, so that assertion has not been shown capable of failing.

## 2026-09-14 — the Orca pass (ticket 0769, action 2)

Zotero 10.0.1, sitter 0.4.10, on padme: GNOME accessibility bus enabled, Orca
3.x from `/usr/bin/orca` run with `--debug-file`, speech captured rather than
recalled. The author drove the mouse and listened; the session drove state
changes over RDP and read the log.

### What Orca speaks, quoted from its own debug output

    SPEECH OUTPUT: 'Index push button.'
    SPEECH OUTPUT: 'Indexing assistant frame.'
    SPEECH OUTPUT: 'Turn indexing off push button.'
    SPEECH OUTPUT: 'Turn indexing on push button.'
    SPEECH OUTPUT: 'Library: Ma bibliothèque — 0 files indexed.'
    SPEECH OUTPUT: 'Progression frame.'

So the toolbar control, the window, the switch, the panel's coverage sentence
and the end-of-work notice all reach a real screen reader with correct roles and
names. Read separately from OUTSIDE the process over AT-SPI, `sdt-announcer`
reports `live: polite`, `atomic: true`, `container-live-role: status` — the
markup is right too.

### Two defects the pass found, which nothing headless could

**The live region misses the switch-off transition** (ticket 0789). From a
known-empty announcer, both directions:

| transition | visible switch row | hidden `sdt-announcer` |
|---|---|---|
| off → **on** | updates | updates within 2.5 s — correct |
| on → **off** | updates immediately | still "Indexing is on" at 8 s |

Only switch-off is lost. The visible row is right in both directions, which is
why the author, watching the screen, reasonably reported the display as fine.
The asymmetry is the diagnosis: the settle needs a second pass to write, and
switching off stops the renders that would supply it.

**The toggle announces the next action** (ticket 0790). The switch's accessible
name is its action, so clicking it to turn indexing ON makes the label "Turn
indexing off" — and that is what Orca says, at the moment indexing was turned
on. Found by the author listening. Neither the AT-SPI read nor the speech log
flags it: both show a correct name on a correct control, and what is wrong is
what a person concludes from hearing it then. This is the half of ticket 0769
that needed a listener rather than more instrumentation, and it is the one that
justifies the whole pass.

### Not established

Whether the announcements, once 0789 is fixed, are worded usefully enough for a
blind user to follow a long indexing run. One session with one listener does not
settle that.

## 2026-09-16 — the widget changed; the readings above are of a control that is gone

Ticket 0797 replaced `#sdt-switch` with an `<input type="checkbox">` and a bound
`<label>` reading "Pause indexing". Every reading above stands as a record of
what was measured on the dates it names, and none of it describes the shipped
control any more:

- The AT-SPI table's `sdt-switch` row reads `push button` / `Turn indexing off`.
  It is now a check box whose accessible name comes from the bound label and
  whose state comes from `checked`, not from its name.
- The two `SPEECH OUTPUT` lines quoting "Turn indexing off/on push button" are
  of the inverting label that ticket 0790 patched with an `aria-label`. Both the
  label and the workaround are gone; 0790's defect cannot recur, because a
  checkbox's name does not name an action.
- "**The toggle announces the next action**" is therefore closed by removal
  rather than by a fix.

**What is owed, and is NOT claimed here.** The replacement has not been read in a
live window. Two readings belong in this file before ticket 0797's own
verification list is complete, and both need a human at the machine: what Orca
announces for the checkbox, in each of its checked/unchecked and
enabled/disabled combinations; and that the native widget survives a
forced-colours setting, which is one of the reasons the control is a plain
platform checkbox with no stylesheet and no ARIA role. Ticket 0792's rendering
claims were all read from source and none was observed; this pass must not
repeat that, so nothing above has been amended to describe the new control from
its source.
