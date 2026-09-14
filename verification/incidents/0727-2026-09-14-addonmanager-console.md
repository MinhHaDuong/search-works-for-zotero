# Ticket 0727 — the host's own account of a disappearance

Read out of `Services.console` on 2026-09-14 after setting
`extensions.logging.enabled` at runtime, on the author's live Zotero 10.0.2.

**How to capture it, since the obvious way does not work.** The `addons.*`
logger has only a `Log.ConsoleAppender` — `AddonManager.sys.mjs` says it appends
"to the Javascript section of the Browser Console" — so it never reaches stderr
and capturing Zotero's stdout from a terminal yields nothing. It cost one
reproduction to learn that. The read that works, from inside the process:

```js
Services.prefs.setBoolPref("extensions.logging.enabled", true);   // live, via PrefObserver
// ... reproduce ...
JSON.stringify(Services.console.getMessageArray()
  .map(m => m.message || "")
  .filter(s => /addons\.|XPI|uninstall|sdt-pack-sitter/i.test(s))
  .slice(-60), null, 1)
```

## The sequence, from the log's own epoch-ms stamps

| t (s) | record |
|------:|--------|
| 0.000 | `addons.xpi DEBUG Starting install of sdt-pack-sitter… from …/sdt-pack-sitter-0.4.13.xpi` |
| 0.031 | `Calling bootstrap method install`, then `startup`, version 0.4.13 |
| 14.258 | `Disabling XPIState for sdt-pack-sitter…` + `Updating active state … to false` + `Calling bootstrap method shutdown` — **the author clicks Remove** |
| 17.801 | `Starting install of sdt-pack-sitter… from …/sdt-pack-sitter-0.4.13.xpi` — **he installs again** |
| 17.815 | `Install of …0.4.13.xpi completed.` |
| 17.818 | `Calling bootstrap method update`, then `startup` — **the new copy is live** |
| 19.271 | `Calling bootstrap method shutdown on sdt-pack-sitter… version 0.4.13` |
| 19.327 | `Calling bootstrap method uninstall on sdt-pack-sitter… version 0.4.13` |
| 19.328 | `uninstallAddon: flushing jar cache …sdt-pack-sitter….xpi` — **the file is destroyed** |

- Remove → finalisation: **5.070 s**
- install #2 → finalisation: **1.527 s**

## What it establishes

The Remove took `uninstallAddon`'s `aForcePending` branch — `XPIStates.disableAddon`,
`bootstrap.shutdown(ADDON_UNINSTALL)`, `updateAddonActive(false)`, which is
`XPIInstall.sys.mjs` lines 5003–5008 exactly. The reinstall then made the add-on
visible, active and started (`update` + `startup`). And the queued removal
**finalised anyway**, through the non-pending branch (`bootstrap.uninstall()`
then `installer.uninstallAddon(id)`), against the copy that had replaced it.

So the removal completes **by add-on id, without rechecking that a newer install
now holds that id**. That is the defect, witnessed by the host rather than
inferred.

## What it does not establish

The 5.07 s from Remove to finalisation looks like the Add-ons window's undo
window expiring, but the interval is not fixed: the 19:21 occurrence in
`0727-2026-09-14-profile-watch.txt` ran 10.23 s from Remove to erasure. What is
constant across all four occurrences is the ORDER — a Remove, an install that
visibly succeeds, then the removal finalising on the new copy — not the delay.

`bench/sitter_pending_uninstall_arm.py` does not reproduce it: driving
`addon.uninstall(true)` and `installAddonFromAOMWithOptions` over RDP, the
install genuinely cancels the pending operation and the add-on survives 25 s of
sampling and a restart. Whatever finalises the removal here is reached through
the Add-ons **window**, not through the API the arm calls.

## The rule that follows regardless

Never Remove and re-install in one session. Remove, **quit Zotero**, relaunch,
then install. Checkable beforehand: `ls -l ~/.zotero/zotero/*/extensions/staged`
— absent or empty is safe; a non-empty entry means a removal is pending.
