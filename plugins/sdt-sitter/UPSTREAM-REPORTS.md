# Two reports for the Zotero forum

*Posted by the author, in his own name, 2026-09-14.*

1. https://forums.zotero.org/discussion/133758/installing-a-plugin-while-its-removal-is-still-pending-deletes-the-new-copy
2. https://forums.zotero.org/discussion/133759/plugin-toolbar-buttons-are-still-outside-the-keyboard-navigation-chain

*Register: forums.zotero.org, where staff read and reply. Short, evidence first,
no plugin promotion — the add-on is how these were found, not what they are
about. Both are reproducible on a stock install with any plugin, so neither
needs the reader to install anything.*

*Searched before drafting (2026-09-14): neither is an open thread. The nearest
matches for the first are symptom-level and answered with "delete
extensions.json and reinstall" — nobody has isolated the mechanism. The second
has a natural parent thread, cited in the draft.*

---8<--- report 1: title ---8<---

Installing a plugin while its removal is still pending deletes the new copy

---8<--- report 1: body ---8<---

Zotero 10.0.2, Linux.

If you remove a plugin and install it again without restarting Zotero in
between, the copy you just installed is deleted a few seconds later. The install
reports success, the plugin loads and runs, and then it disappears — file,
extensions.json entry, and its whole preference branch.

Steps:

1. Tools -> Plugins -> Remove, on any plugin.
2. Without restarting, install the plugin again from a file.
3. Watch it appear, work, and then vanish after a few seconds.

What I measured. Reproduced four times in one hour; three of them watched from
outside the process at 50 ms resolution, which gives the same shape each time:

- Remove creates extensions/staged/<addon-id>/ and extensions.json still names
  the add-on. That is uninstallAddon's aForcePending branch.
- The install rewrites the .xpi, empties and deletes the staged entry, and
  extensions.json returns to naming the add-on. The install genuinely succeeds
  and the pending marker is genuinely cleared.
- 3.3 to 4.7 seconds later the .xpi is deleted, extensions.json loses the entry,
  and half a second after that the add-on's preference branch is cleared.

With extensions.logging.enabled, the add-on manager narrates it. Times are its
own epoch-ms stamps, offset from the first install:

    0.000   Starting install of <id> from file:///.../<addon>.xpi
    0.031   Calling bootstrap method install, then startup
   14.258   Disabling XPIState / Calling bootstrap method shutdown   <- Remove
   17.801   Starting install of <id> from file:///.../<addon>.xpi    <- reinstall
   17.815   Install of ....xpi completed.
   17.818   Calling bootstrap method update, then startup            <- new copy live
   19.271   Calling bootstrap method shutdown
   19.327   Calling bootstrap method uninstall
   19.328   uninstallAddon: flushing jar cache .../<addon>.xpi       <- file destroyed

So the queued removal finalises through the non-pending branch —
bootstrap.uninstall() then installer.uninstallAddon(id) — against the copy that
had replaced it. It appears to complete by add-on id without rechecking that a
newer install now holds that id.

Two things that may narrow it down. It does not need a restart: all four
occurrences happened in one session. And I could not reproduce it by driving
AddonManager directly — getInstallForFile plus installAddonFromAOMWithOptions
after addon.uninstall(true), with the pending state confirmed present
(pendingUninstall true, extensions.pendingOperations true, the staged directory
on disk), survives both the wait and a restart. That path cancels the pending
operation correctly, which suggests whatever finalises the removal is reached
through the Plugins window rather than through the API.

Why it is worth fixing rather than documenting: the failure is silent and the
plugin looks installed while it happens, so the natural reading is that the
plugin removed itself. I spent a fortnight on that reading before measuring it.

The workaround, for anyone who finds this thread: remove, quit Zotero, relaunch,
then install.

---8<--- report 1: end ---8<---

---8<--- report 2: title ---8<---

Plugin toolbar buttons are still outside the keyboard navigation chain

---8<--- report 2: body ---8<---

Following up on "Accessibility: Getting to the toolbar buttons"
(https://forums.zotero.org/discussion/97505/), where in February 2023 dstillman
wrote that "In Zotero 6.0.22, available now, all toolbar buttons are accessible
via the keyboard."

That is true of Zotero's own buttons. A button a plugin adds to the toolbar is
not reachable by Tab, and as far as I can tell there is no supported way for a
plugin to put it there. Setting tabindex="0" on the button is not enough.

Reading chrome/content/zotero/zoteroPane.js: setUpKeyboardNavigation() installs
several keydown listeners, and each builds its own actionsMap as a `let` inside
the callback. moveFocus looks up actionsMap[event.target.id], then falls back
over event.target.classList. Every top-level key in those maps is one of
Zotero's own element ids or a specific Zotero class — zotero-tb-add,
zotero-tb-sync, search-input, tag-selector-list, and so on. There is no generic
"a toolbar button" key, and the maps are not reachable from outside their
closures, so a plugin's only way in would be to impersonate an id that Zotero's
own navigation depends on.

The consequence for a keyboard-only or screen-reader user is that a plugin's
toolbar control can be announced correctly, have a correct role and name, and
still be unreachable without a mouse. I checked the rest with Orca and the
markup side is fine; it is only the Tab order that a plugin cannot enter.

Is there a supported hook I have missed? If not, would you consider one — a
class the maps recognise, or a small registration call — so that a plugin button
can sit in the chain next to the native ones? I am happy to test a patch.

---8<--- report 2: end ---8<---
