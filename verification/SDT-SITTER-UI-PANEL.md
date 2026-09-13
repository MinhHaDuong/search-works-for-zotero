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

