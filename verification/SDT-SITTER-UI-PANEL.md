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
  coverage; raw English states do not explain what happens next. Follow-up.
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
  region, not all second-by-second text. Built in ticket 0686 (0.3.41): one
  visually hidden `role="status"` node, `aria-live="polite"`,
  `aria-atomic="true"`, written only when the switch line -- the window's one
  sentence about the machine's state -- changes and holds for two seconds.
  Opening the window announces nothing; progress, file names and estimates
  never reach it. Three scenarios in `tests/sdt_sitter_bootstrap.mjs`, each
  the others' positive control, and four mutants (M31-M34) in the bootstrap
  mutation gate. Whether Orca in fact speaks it is ticket 0769's reading.
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
