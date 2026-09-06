# SDT sitter census and journal repair

Ticket 0688. Reviewed locally on 2026-09-06.

## Findings

The production scheduler rebuilt the full census on every timer tick after a
sweep returned, including resource-blocked returns. Inspection exceptions were
counted without retaining their messages. The error journal opened in IOUtils
`append` mode, which rejects a missing file. The data directory existed when
inspected; the reported journal error does not establish loss of that directory.

The journal contract is documented in the
[Mozilla IOUtils API](https://searchfox.org/firefox-main/source/dom/chrome-webidl/IOUtils.webidl).
The isolated regression also exercises journal creation in the installed
application, through the production error-reporting path.

The queried system journal contained no suspend/sleep entries after the prior
evening. This does not prove the machine remained awake. The plugin does not
hold a sleep inhibitor. The cause of the historical inspection errors and of
the reported snapshot's native extraction failure remains unknown.

## Change

The scheduler retains its census and pending queue through automatic ticks.
Resource waits preserve the next candidate, which is inspected again before
admission. A finished queue remains idle. Reactivation reconstructs the census;
attachments newly added outside the queue are discovered then. Native packs
remain the source of truth and no active queue is persisted.

Inspection exception details reach the diagnostics panel and journal. Journal
and cache append writes can create a missing file. Cache warnings are displayed.
Native failure messages include ensure's result and the observed pack status.
The manifest uses the author's corrected release version `0.2.2`.

## Validation

`make check` passed. Scheduler regressions cover census reuse, retaining a
partially drained queue through a resource wait, intervening native completion,
and inspection diagnostics while healthy attachments continue.

`bench/results/sdt-sitter-resume-0688/integration.json` records the successful
isolated real-Zotero run and exact source digests. Existing PDF/EPUB extraction,
cache reload, UI and disable checks passed. A synthetic attachment's ensure
response was deliberately forced false to exercise first-error journal creation;
it is not a reproduction or diagnosis of the user's snapshot failure.

The harness used a fresh synthetic profile, host files read-only and networking
unshared. The first attempt could not create a bubblewrap namespace under the
outer sandbox; the approved rerun retained the harness's own isolation.
The author's live profile was not modified or used to run extraction.
