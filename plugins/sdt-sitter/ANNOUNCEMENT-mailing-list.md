# Zotero mailing list post — draft

*For the author to send, in his own name, after the tag is cut and the
fresh-profile install has been run. Nothing here has been sent.*

*Register: a mailing list, read as plain text in clients that render no
markup. So: a subject line that carries the whole thing on its own, no
headings, no bold, no bullet glyphs, wrapped at 72 columns. The audience skews
more technical than a forum thread, so the mechanism gets more room and the
marketing gets none.*

*Everything between the two cut lines below is the message body, and is already
plain text — send it as it stands rather than converting it. One passage is
marked for the author to complete or cut. Replace [VERSION] and [release URL]
before sending.*

---8<--- subject ---8<---

Experimental add-on: prepare Zotero 10 structured-text caches in the background

---8<--- body ---8<---

I have written an experimental Zotero add-on and I would like a few
people to try it with their eyes open. It is called SDT Pack Sitter and
this is its first tagged release.

WHAT IT DOES

Zotero 10 can turn a PDF, EPUB or snapshot into a structured text pack:
the text plus its headings, reading order, and where on the page each
piece came from. Zotero builds a pack when something needs one. This
add-on builds them in advance instead, one attachment at a time, in the
background, so the work is already done the first time anything asks for
it.

It also surfaces the state of those caches, which is otherwise hard to
see: what fraction of the library has a current pack, what is being
worked on, what it is waiting for, and which attachments could not be
prepared and why - file missing from disk, unsupported format, no text
in the document, or a record with no file attached at all.

It builds no index of its own and changes nothing about your search
results. It calls Zotero's own extractor, so extraction quality is
exactly what Zotero would have produced. It opens no network connection
of its own.

HOW IT STAYS OUT OF THE WAY

One attachment at a time, and only while Zotero's own extraction worker
is idle, at least 4 GiB of memory is available, at least 8 GiB is free
on the cache's disk, and the one-minute load average is below the core
count. All of that is re-read immediately before each document rather
than once at startup. Switching it off stops new work and lets the
document in flight finish.

Transient conditions - a full disk, a busy machine - are logged and
retried on a ten-minute cadence rather than raised. The retry interval
is flat rather than exponential on purpose: the check costs
microseconds, so there is nothing to protect by backing off further, and
a full disk is the kind of problem a person fixes in a minute and then
watches for the effect.

LINUX, REALLY

Two of those three resource checks read /proc, which macOS and Windows
do not have. On those platforms they are skipped rather than failed: the
add-on will index, but it will not hold back because the machine is
short of memory or already loaded. The free-disk check still applies
everywhere. I have run this only on Linux, and nothing here takes a
reading on either of the others, so treat those as untested.

VERSIONS

Zotero 10.0.1 or later, and nothing after Zotero 10. The ceiling is
deliberate: the add-on reaches into parts of Zotero that carry no
compatibility promise, so claiming to work on a version nobody has
tested would be a claim I cannot support. On Zotero 11, expect it to be
left installed and disabled - still listed, no longer preparing
anything, nothing removed from your library or from Zotero's own index.

Two Zotero versions have been exercised against real documents: 10.0.1,
and 10.0.2 including the upgrade between them. 10.0.2 changes the
extractor version, and on that upgrade the add-on discarded every cached
answer and prepared the documents again rather than trusting work done
under the older one.

ONE REQUEST IT CAUSES

Because the add-on declares an update manifest, which Zotero requires at
install time, Zotero's own add-on update check fetches that manifest
about once a day for as long as the add-on stays installed. It is one
fixed URL and carries nothing about your library. The add-on makes no
request itself. The requirement is not a design choice: a build
identical but for the removal of update_url is refused at install.

THE THING TO KNOW BEFORE INSTALLING

On my own machine this add-on has removed itself from Zotero
mid-session: disabled, then deleted from the profile record and from
disk, without being asked. It happened repeatedly over one instrumented
evening, and once more, uninstrumented, two days later. I do not know
why. Nothing was lost from the library and Zotero's own text index was
untouched; what I lost was the add-on.

I have not been able to reproduce it deliberately. First installs,
replacement installs, an older build, and repeated disable-and-re-enable
cycles across two machines have all survived, and four explanations I
thought plausible have been tested and ruled out. I am saying so rather
than waiting for a cause, because it seems more useful for people to
know than for me to keep looking alone.

If it happens to you, one thing is worth doing and the order is the
whole of the instruction. BEFORE restarting Zotero, open Tools ->
Developer -> Run JavaScript, evaluate

    JSON.stringify(Zotero.SDTPackSitterJournal.tail(200))

and copy the result somewhere. That object exists only while the Zotero
process is alive, so a restart destroys it, and it is the only record
this failure leaves. Then restart and reinstall. Sending me that output
would help more than anything else.

Be exact about what the add-on's technical-diagnostics switch covers,
because the gap is the unknown itself. With it on, the add-on writes
what it was told to a file in your Zotero data directory when Zotero
TELLS it that it is being disabled or removed. In the disappearance
above it was not told: it was still running, its window usable and its
indicator still moving, after its record and its file had already gone.
Since this release it also checks once a minute whether Zotero still
lists it, and says so in its own window if not - which closes the
notification gap but not the cause.

ALSO HONEST ABOUT

The add-on's window is not qualified accessible. Keyboard operation was
verified in a real Zotero this week - the toolbar control takes focus,
Enter opens the window, Escape closes it - but nobody has yet heard it
through an actual screen reader, the layout at enlarged font sizes has
not been examined, and tab order is unconfirmed.

[TO BE COMPLETED OR CUT BEFORE SENDING. One sentence on the fresh-profile
install actually run from the release asset: Zotero version, operating
system, and what was observed after thirty minutes of use. If that arm
was not run, cut this paragraph rather than soften it.]

WHERE IT IS

[release URL]

Install with Tools -> Add-ons -> gear menu -> Install Add-on From File.

Feedback of any kind is welcome, and reports of it disappearing most of
all.

---8<--- end ---8<---
