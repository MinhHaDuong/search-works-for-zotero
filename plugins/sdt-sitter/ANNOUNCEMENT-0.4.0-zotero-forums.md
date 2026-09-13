# Zotero forums post — draft

*For the author to post, in his own name, after the tag is cut and the
fresh-profile install has been run. Nothing here has been posted.*

*Register: a Zotero user and developer audience reading a forum thread. This
text carries nothing about how this repository is run, no ticket numbers, and
no reading of anyone else's work. Two passages are marked for the author to
complete or cut; neither may be published as it stands.*

---

**Suggested title:** Experimental add-on: prepare Zotero's structured-text
caches in the background (SDT Pack Sitter 0.4.0)

---

I have been running an experimental add-on on my own library for a few weeks and
I would like a few more people to try it, with their eyes open. It is called SDT
Pack Sitter. This is its first tagged release.

**What it does.** Zotero 10 can turn a PDF, EPUB or snapshot into a structured
text pack: the text plus its headings, reading order, and where on the page each
piece came from. Zotero builds a pack when something needs one. The add-on
builds them in advance instead, one attachment at a time, in the background, so
the work is already done the first time anything asks.

It also shows you the state of those caches, which is otherwise hard to see: how
much of the library has a current pack, what it is working on, what it is
waiting for, and which attachments it could not prepare and why (file missing
from disk, unsupported format, no text in the document, no file attached to the
record).

**What it does not do.** It builds no index of its own and it changes nothing
about your search results. It uses Zotero's own extractor, so extraction quality
is exactly what Zotero would produce anyway. It opens no network connection of
its own.

**It tries to stay out of the way.** One attachment at a time, and only while
Zotero's own extraction worker is idle, at least 4 GiB of memory is available,
at least 8 GiB is free on the cache's disk, and the one-minute load average is
below the core count. It re-reads all of that immediately before starting each
document. Switching it off stops it taking on anything new and lets the document
in flight finish.

**Versions.** Zotero 10.0.1 or later, and nothing after Zotero 10. The ceiling
is deliberate: the add-on reaches into parts of Zotero that are not public API,
so claiming to work on a version nobody has tested it against would be a claim I
cannot support. When you move to Zotero 11, expect the add-on to be left
installed and **disabled** — still listed, no longer preparing anything, nothing
removed from your library or from Zotero's own index. I would rather it be set
aside by a version check than guess.

**One request it causes.** Because the add-on declares an update manifest, which
Zotero requires at install, Zotero's own add-on update check fetches that
manifest about once a day for as long as the add-on stays installed. It is one
fixed URL and carries nothing about your library. The add-on makes no request
itself.

**The thing you should know before installing.** On my own machine the add-on
has removed itself from Zotero mid-session: disabled, then deleted from the
profile record and from disk, without being asked to. It happened repeatedly
over one instrumented evening, and once more, without instrumentation, two days
later. I do not know why. Nothing was lost from the library and Zotero's own
text index was untouched; what I lost was the add-on.

I have not been able to reproduce it deliberately. First installs, replacement
installs, an older build, and repeated disable-and-re-enable cycles across two
machines have all survived. Four explanations I thought plausible have been
tested and ruled out. I am telling you this rather than waiting for a cause,
because it seems more useful for people to know about it than for me to keep
looking alone.

If it happens to you, there is one thing worth doing, and the order matters.
*Before you restart Zotero*, open Tools → Developer → Run JavaScript, evaluate

    JSON.stringify(Zotero.SDTPackSitterJournal.tail(200))

and copy the result somewhere. That object exists only while the Zotero process
is alive, so restarting destroys it, and it is the only record this failure
leaves. Then restart and reinstall. If you send me that output it would help a
lot.

**Also honest about:** the add-on's own window is not qualified as accessible.
It has a reduced-motion pass and announces state changes, but I have not
verified keyboard-only operation, focus handling, screen-reader behaviour in a
real reader, or layout at enlarged font sizes in a running window.

> **TO BE COMPLETED OR CUT BEFORE POSTING.** One sentence on the fresh-profile
> install actually run from the release asset: Zotero version, operating system,
> and what was observed after thirty minutes of use. If the arm was not run, cut
> this paragraph rather than soften it.

**Where it is:** [release URL]

Install with Tools → Add-ons → gear menu → Install Add-on From File.

Feedback of any kind is welcome, and reports of it disappearing most of all.
