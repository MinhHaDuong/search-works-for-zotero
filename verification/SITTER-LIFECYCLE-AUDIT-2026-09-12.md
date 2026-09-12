# SDT pack sitter: the host lifecycle interface — install, remove, update, and surviving a Zotero upgrade or downgrade

*Audit, 2026-09-12. Source-reading only; nothing below was run against a live
Zotero. Payload audited: `plugins/sdt-sitter/` at `cef3797` (manifest version
0.3.43).*

## What this settles, and what it only proposes

Three evidence classes, kept apart on purpose, because this repository has
already paid for the confusion once (ticket 0727: a docs-based reading of
`update_url` stood for two days against a control that refuted it in one
evening).

* **Source-verified.** Read off the payload, its guards and its tests. Cited by
  `file:line`. Findings F1–F9.
* **Host behaviour assumed.** Depends on what Zotero does, from its documented
  Gecko lineage rather than from a reading of its source or a control here.
  Marked *(host-assumed)* and never used to carry a finding on its own.
* **Needs a live arm.** Stated as an experiment with a verdict-carrier, not as
  a conclusion. F10.

The four axes in the title are the add-on's contract with its host. None of
them has a test in `tests/test_sdt_sitter.py` today: the suite holds the id,
the manifest's host, and update.json's version agreement (`:596`, `:610`,
`:628`), and says nothing about what remains after an uninstall, what a
shutdown reason records, or what an upgraded host does to the cache.

## Ranked actions

Ordered by value over cost, not by severity.

1. **F9 — take `reason` in `startup()`** (one line, plus the record). The
   journal can say why it shut down and never why it started. 0727's live
   candidate is cumulative replacement; the discriminator is the install/enable/
   upgrade/downgrade reason on the way *in*.
2. **F10 — give the volume experiment a liveness assertion before spending its
   remaining ~33 cycles.** As driven today it very likely measured host
   bookkeeping of an add-on that never became `alive`.
3. **F1 — decide what an uninstall withdraws.** The indexing consent pref
   survives removal, so a reinstall indexes without asking. Privacy-visible,
   and the September 21 freeze names privacy.
4. **F2 — clean up on uninstall** (cache file, `.tmp`, two prefs) and declare
   the three locations in SPEC. Currently only the debug pref is declared.
5. **F5 — say why the cache emptied after a host upgrade.** One counter, one
   sentence in the window.
6. **F3 — drop both session globals when the reason is uninstall.**
7. **F7 — make the cache's `format` guard real**, or delete it.
8. **F6/F8 — record the two version-range decisions** (update.json lists only
   the tip; `strict_max_version` is `10.*`) where a reader meets them.
9. **F4 — disclose the daily update fetch** in the privacy paragraph.

---

## Install

### F1. The indexing consent survives removal, so a reinstall never asks *(severity: high; cost: low)*

`readSDTSwitch`/`writeSDTSwitch` (`bootstrap.js:774`, `:784`) persist the
answer in `extensions.sdt-pack-sitter.enabled`, and `initialize()` asks only
when the pref reads unanswered (`:2661`). That is the ratified behaviour —
"the prompt is reached at most once per profile" (`:2660`), SPEC §5.2.7's
first-run question — and it is what makes disable/re-enable silent.

Nothing anywhere clears it: `grep -n "Prefs.clear\|clearUserPref"` over the
payload returns nothing, and `uninstall()` is `{}` (`:2724`). *(host-assumed:
Gecko does not clear a plugin's own `extensions.*` branch on uninstall; no
control was run here.)*

Consequence: a profile that answered *yes*, uninstalled the add-on, and later
installs it again starts indexing without asking. The prompt is the consent
record for a background process that reads the whole library; an uninstall is
the plainest withdrawal of that consent a user can perform, and it currently
leaves the answer standing.

This is a decision, not a defect to fix quietly — "ask once per profile" and
"forget on uninstall" are both defensible and they conflict. Recommendation:
clear the pref in `uninstall()` and keep "once per *installation*". The cost is
one extra prompt for a user who removes and reinstalls, which is exactly the
user who should see it.

### F2. `uninstall()` leaves three pieces of durable state, and SPEC declares one *(severity: medium-high; cost: low)*

`install()` and `uninstall()` are both empty (`:2723`, `:2724`). What remains
after a removal:

| State | Written at | Declared in SPEC |
| --- | --- | --- |
| `<dataDir>/sdt-sitter-cache.jsonl` | `bootstrap.js:2289`, `:2326` | no (§5.2.7 names the cache, never its location) |
| `<dataDir>/sdt-sitter-cache.jsonl.tmp` (on a crash mid-write) | `:2326` | no |
| `extensions.sdt-pack-sitter.enabled` | `:784` | no |
| `extensions.sdt-pack-sitter.debug` | read at `:73`; author-created | yes, `SPEC.md:2474` |

R15's uninstall clause (`SPEC.md:603`) binds *targets* — the sitter is not one,
so this is not a requirement violation. It is the same obligation the project
holds targets to, unmet by its own add-on, and the declaration gap is the
larger half: a reader cannot find out from SPEC where the sitter's durable
state lives.

Recommendation, in order: (a) move the cache under a plugin-owned directory
(`<dataDir>/sdt-pack-sitter/cache.jsonl`) so "complete removal" is one
recursive delete rather than a filename list that drifts; (b) remove that
directory and the two prefs in `uninstall()`; (c) declare the directory in
SPEC §5.2.7 beside the debug pref. *(host-assumed: Zotero calls the bootstrap
`uninstall` hook, and awaits it, for a user-initiated removal.)*

### F3. Two session globals outlive an uninstall *(severity: medium; cost: low)*

`shutdown()`'s `finally` republishes `Zotero.SDTPackSitterJournal`
unconditionally (`:2720`), and `Zotero.SDTPackSitterCacheWrite` (`:2352`) is
never deleted at all — `shutdown()` deletes only `Zotero.SDTPackSitter`
(`:2712`).

Both are right for the reason they were built: ticket 0703's disable/re-enable
must not destroy the evidence of what it was recovering from, and the cache
write chain is deliberately shared across scopes so a replacement's first write
cannot interleave with the outgoing build's last (`:2290`).

Neither reason survives an uninstall. After a removal, two Zotero properties
keep the dead sandbox reachable for the rest of the session, and the
diagnostics payload stays copyable to the clipboard for an add-on no longer
installed. `shutdown()` already has the discriminator it needs —
`SHUTDOWN_REASONS[6] === 'uninstall'` (`:97`) — so this is a two-line
narrowing, not a redesign.

### F4. The mandatory update channel is a daily outbound fetch, undisclosed *(severity: medium, privacy; cost: one paragraph)*

`update_url` points at `raw.githubusercontent.com/.../main/plugins/sdt-sitter/update.json`
(`manifest.json:11`), and ticket 0727 established with a control that it is
**required**: the identical build without it is refused at install. So a plugin
whose proposition is "local by default" cannot be installed without the host
contacting GitHub about it on the host's own update cadence
(`extensions.update.interval`, 86400 s per 0727's log), carrying the installed
version and the user's address.

Nothing is wrong with the code. What is missing is the disclosure: neither
`RELEASE-NOTES.md` nor SPEC §5.2.7's privacy paragraph mentions it, and it is
the only network traffic the add-on's existence causes.

---

## Update (of the plugin itself)

### F6. By construction, no hand-delivered build is listed in its own update manifest *(severity: medium; cost: a decision)*

`bench/check_sitter_version.py` rule 2 requires update.json to carry **exactly
one** entry, for the working tree's version. main's manifest therefore lists
the tip and nothing else — while the delivery practice is a hand-carried XPI
built from a *branch* (ticket 0680 carried one to the author's home directory;
`bench/sitter_volume_experiment.py` installed 9.0.0 … 9.17.0 during arm 5).

Every such build is an add-on whose update manifest does not list its installed
version. That is the same family as the state ticket 0727's fix was written to
eliminate — "an add-on whose update manifest lists it with zero versions has no
version the host can find compatible" (`update.json:2`) — re-created on every
branch delivery, and on every tip bump for anyone still running the previous
build.

To be exact about what this does and does not claim: the *mechanism* in 0727's
title is refuted (0.2.15 advertised a compatible version and died on the same
schedule; the timing never fitted a daily check). This finding is about the
state, not the cause. The state is cheap to avoid and the cause is unknown,
which is the whole argument for avoiding it.

Ranked options:

1. **Cumulative list** (recommended). Append rather than replace: every shipped
   version keeps an entry with its own bounds. The guard changes from "exactly
   one entry, equal to the tip" to "contains the tip, versions unique". Cost:
   the guard's rule 2 and its fixtures.
2. **Keep single-entry, state it.** Add to `update.json`'s comment and to the
   guard's docstring that only the tip is listed and that hand-delivered
   branch builds are *deliberately* unlisted. Cost: two sentences. Leaves the
   state in place.
3. **Serve update.json from a tag instead of `main`.** Removes the in-development
   window, keeps the one-entry-per-release shape, and needs a release first —
   which is 0764's business, currently deferred.

### F7. The cache's format guard cannot fire, so a plugin downgrade has no schema check *(severity: low-medium; cost: three lines)*

`createSDTCache` checks `raw?.format === 1` (`scheduler.js:351`), and
`bootstrap.js:2291` hardcodes `format: 1` into the object it hands over. No row
on disk carries a format field — writes serialize `{ versions, ...change }`
(`:2326`) and the read loop validates `row.versions` and `row.key` only
(`:2296`). The guard is satisfied by construction and can never detect a record
shape written by a different build.

The cache is disposable, so the consequence is not data loss; it is silent
misreading. An older build installed over a newer one (a downgrade, which
hand-delivery makes ordinary) reads the newer build's rows as its own. Fix:
write `format` in each row and skip a mismatch exactly as `versions` is
skipped. Or delete the check and say in the comment that the on-disk rows carry
no schema stamp — an inert guard is worse than none, because it reads as
protection.

---

## Surviving a Zotero upgrade or downgrade

### F5. A host point release silently empties the cache and the window never says so *(severity: medium; cost: low)*

The cache is keyed on the host's processor stamps: `versions` is
`resource://zotero/document-worker/metadata.json` (`:2286`), and every row whose
`versions` differs is dropped on load (`:2296`).

Those stamps move on point releases, by this repository's own reading:
`SDT_SCHEMA_VERSION` 1.1.0 → 1.2.0 and the PDF processor stamp 3 → 14 between
the 10.0 build and 10.0.2 — eleven stamps across three point releases
(`RELEASE-NOTES.md:131`). So the ordinary consequence of a Zotero update is a
total cache invalidation and a full re-census, on top of the whole-library
re-MD5 every activation already performs (0727's log, 2026-09-08T07:42Z).

The plugin survives this correctly. What it does not do is explain it:
`emit('cache-load', …)` reports the rows *kept* (`:2306`) and never the rows
dropped for a version mismatch, so the post-upgrade session looks exactly like
a broken one from the user's side — everything done again, no reason given.
Count the skipped rows and say it once in the window ("the host's text
processors changed; earlier observations no longer apply"). This is the
cheapest removal of a user misreading in the whole audit.

A second-order note, cheap to fix while there: the key is
`JSON.stringify(versions)` (`:2302`), i.e. serialization equality, so a
key reorder in the host's own metadata.json with no semantic change discards the
cache. A canonical digest over sorted keys would not.

### F8. `strict_max_version: "10.*"` makes a Zotero 11 upgrade an uninstall-shaped event *(severity: medium; cost: a decision)*

Both the manifest (`manifest.json:10`) and update.json's single entry
(`update.json:11`) cap at `10.*`. On a host upgrade to 11, the installed build
is out of range **and** the update manifest offers no in-range version —
the two conditions together, which is precisely the configuration
`update.json`'s own comment describes as the suspected cause of the add-on
being disabled and then deleted mid-session. A downgrade below 10.0.1 reads the
same way from the other side.

*(host-assumed: what Zotero 11 would do to an out-of-range add-on. No control
exists, and none can until an 11 exists.)*

The cap is defensible: the payload reaches into `Zotero.SDT.ensure`,
`resource://zotero/document-worker/*` and `win.require`, none of which is
public API, so silently claiming compatibility with an unread host is worse
than being disabled by it. What is missing is that the choice is recorded
nowhere a reader meets it, and that the *deletion* risk is a different question
from the *disable* risk. Options, ranked: (1) keep the cap, record the
consequence in RELEASE-NOTES and the ticket trail, and re-test on the first 11
build; (2) keep the manifest cap but let update.json carry a second, wider
entry so the host always finds *some* in-range version; (3) drop
`strict_max_version` — cheapest to write, and it ships an unread-API build to a
host nobody has tested.

### F9. The journal records why the plugin stopped and never why it started *(severity: high, forensic; cost: one line)*

`shutdown(data, reason)` maps and records the reason (`:2690`, `:2714`,
`SHUTDOWN_REASONS` at `:97`, which covers install, uninstall, upgrade and
downgrade). `startup({ rootURI, version })` (`:2204`) does not take the second
argument the host passes, and the `startup` record (`:2259`) carries version,
`rootURI`, `zoteroVersion` and the manifest bounds — never the reason.

So the diagnostics layer built to explain disappearances cannot distinguish, on
the way in, a first install from an enable, an upgrade from a downgrade, or
either from an ordinary app start. 0727's surviving live candidate is
*cumulative rapid replacement*: the count of `reason: upgrade` activations in
one session is the exact quantity that candidate is about, and it is the one
thing the ring does not hold. This is the same class of defect as 0688's
unreadable version (`:2198`) — instrumentation whose one job is to say which
transition happened, not saying it.

Fix: `function startup({ rootURI, version }, reason)`, map it through the same
table (rename it `BOOTSTRAP_REASONS`, adding `1: 'app-startup'`), and put it in
the `startup` record beside the version. *(host-assumed: Zotero passes a reason
to `startup` as it does to `shutdown`. The payload already accepts both numeric
and named forms (`:96`), so the record degrades to `reason-<n>` or `unknown`
rather than breaking if it does not.)*

### F10. Arm 5's negative result is narrower than recorded: the plugin was very likely never alive *(severity: high, methodological; cost: one assertion in the driver)*

`bench/sitter_volume_experiment.py` runs Zotero with `--headless` (`:349`
default true, `:401`), and its watcher samples `extensions.json` and the XPI's
presence on disk only — the verification report states that plainly
(`verification/SDT-SITTER-DISAPPEARANCE-0727.md:85`). Neither the report nor
the ticket log claims the installed builds were *running*.

Read against the payload, they almost certainly were not. `initialize()` awaits
`Zotero.uiReadyPromise` (`:2261`) and then requires a main window:
`const win = Zotero.getMainWindow(); if (!win || typeof Zotero.SDT?.ensure !== 'function') throw`
(`:2282`). Headless, `getMainWindow()` has no `navigator:browser` window to
return, and `win.require` (`:2284`) has no window to call it on. Either
`uiReadyPromise` never settles and `initialize()` stalls before that line, or it
settles and the line throws into `startup()`'s bare
`.catch(error => Zotero.logError(error))` (`:2209`). In both branches `alive`
never becomes true: no census, no cache write, no timers, no prompt, no
toolbar button.

Prior arms knew this and judged liveness by the cache file's compact write
(0727's log, 2026-09-08T07:31Z, citing the unconditional first save). Arm 5
dropped that reading and replaced it with nothing.

What it means: 17 clean cycles are evidence about **Zotero's add-on
bookkeeping under repeated install/disable/enable**, not about the sitter
running under it. Every candidate mechanism that involves anything the plugin
*does* — its timers, the modal first-run prompt, writes into the data
directory, a throw inside `initialize()`, a re-used scope — is outside what
arm 5 could observe. The two organic occurrences were on a GUI Zotero with the
plugin demonstrably running (the author saw a frozen, message-id-labelled
toolbar button).

This bears directly on `STATE.md`'s handoff, which is "re-run
`bench/sitter_volume_experiment.py` to the full ~50-cycle/~2h budget".
Recommendation, before spending that budget:

1. Add a liveness verdict-carrier to each cycle — the cache file's existence
   and mtime, or an RDP `eval` of `!!Zotero.SDTPackSitter`, sampled after the
   enable. **Positive-control it**: a cycle that installs a deliberately inert
   payload must read as not-live, or the assertion is the same
   "all-clear is indistinguishable from could-not-look" trap
   `tickets/AGENTS.md` warns about.
2. If a headless host cannot produce a live plugin — the reading above says it
   cannot — run the remaining budget under `Xvfb`, or state in the report that
   the arm tests host bookkeeping only and re-scope it to that question.

Otherwise the full run costs two hours and answers a question about the host
alone.

---

## What this audit does not cover

* No live Zotero was driven. Everything above is a reading of the payload, its
  guards, its tests and this repository's own recorded observations.
* Zotero's actual handling of an out-of-range add-on, of the bootstrap
  `install`/`uninstall` hooks, and of a plugin's `extensions.*` pref branch on
  removal is taken from its Gecko lineage, not from its source. Each such point
  is marked *(host-assumed)* above; none of them carries a finding alone, and
  F1, F2 and F8 would each be settled in one cycle of the 0766 client plus a
  `prefs.js` read.
* The `10.*` cap cannot be tested until a Zotero 11 exists.
* Nothing here re-opens a refuted arm of 0727. F6 is about a *state* the fix
  was written to avoid, not about the mechanism the log refuted, and F10 is
  about the instrumentation of the next arm, not about a new candidate.
