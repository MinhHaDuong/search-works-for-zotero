# r/zotero post — draft

*For the author to post, in his own name, after the tag is cut and the
fresh-profile install has been run. Nothing here has been posted.*

*Register: Reddit. Short, first person, and self-disclosing in the first
sentence — r/zotero reads anything that opens like a product page as
advertising, and it is right to. No headings, no bold-lead bullets, no ticket
numbers. The warning is near the top rather than in a section near the bottom,
because a reader who stops after three paragraphs must still have met it.*

*One passage is marked for the author to complete or cut. It may not be
published as it stands. Replace `[VERSION]` and `[release URL]` at post time.*

---

**Suggested title:** I wrote an experimental add-on that prepares Zotero 10's
structured-text caches in the background — looking for a few testers

---

I wrote this, so take the enthusiasm with salt. It is called SDT Pack Sitter,
it is experimental, and I have been running it on my own library for a few
weeks.

Zotero 10 can turn a PDF, EPUB or snapshot into a structured text pack — the
text plus headings, reading order, and where on the page each piece came from.
Zotero builds one when something needs it. This add-on builds them ahead of
time instead, one attachment at a time, in the background, so the work is
already done the first time anything asks. It also shows you the state of those
caches, which is otherwise hard to see: how much of the library is current,
what it is working on, and which attachments it could not prepare and why.

It builds no index of its own and changes nothing about your search results. It
uses Zotero's own extractor, so extraction quality is whatever Zotero would
have produced anyway. It opens no network connection of its own.

**The thing to know before you install it.** On my machine this add-on has
removed itself from Zotero mid-session — disabled, then deleted from the
profile and from disk, unasked. It happened several times over one evening when
I had instrumentation running, and once more two days later when I did not. I
do not know why. Nothing was lost from the library and Zotero's own text index
was untouched; what I lost was the add-on. I have not managed to reproduce it
deliberately: fresh installs, replacement installs, an older build and repeated
disable/re-enable cycles on two machines have all survived, and four
explanations I thought likely have been tested and ruled out. I am posting
anyway, because more people knowing seems more useful than me continuing to
look alone.

If it happens to you, one thing is worth doing and the order matters. *Before
restarting Zotero*, open Tools → Developer → Run JavaScript and evaluate

    JSON.stringify(Zotero.SDTPackSitterJournal.tail(200))

then copy the result somewhere. That record exists only while the Zotero
process is alive — restarting destroys it, and it is the only trace this
failure leaves. Then restart and reinstall. Sending me that output would help
more than anything else I can think of.

It tries hard to stay out of the way: one attachment at a time, and only while
Zotero's own extraction worker is idle, there is memory and disk headroom, and
the machine is not already loaded. It re-checks all of that immediately before
each document. Two of those checks read `/proc`, so on macOS and Windows they
are skipped rather than failed — the add-on will still index there, but it will
not hold back when the machine is busy. I have only run it on Linux. If you put
it on another platform, treat it as untested and watch what it does to a
machine you are using for something else.

Zotero 10.0.1 or later, and nothing past Zotero 10. The ceiling is deliberate:
it reaches into parts of Zotero that are not public API, so claiming a version
nobody has tested would be a claim I cannot support. On Zotero 11 expect it to
be left installed and disabled rather than to keep running.

Two more things I would rather say than have found. Because it declares an
update manifest — which Zotero requires at install — Zotero's own update check
fetches that manifest about once a day for as long as it stays installed; one
fixed URL, nothing about your library, and the add-on makes no request itself.
And its window is not qualified accessible: keyboard operation and focus
handling were verified in a real Zotero this week, but nobody has yet heard it
through an actual screen reader, and the layout at enlarged font sizes has not
been looked at.

> **TO BE COMPLETED OR CUT BEFORE POSTING.** One sentence on the fresh-profile
> install actually run from the release asset: Zotero version, operating
> system, and what was observed after thirty minutes of use. If that was not
> run, cut this paragraph rather than soften it.

[release URL] — install with Tools → Add-ons → gear menu → Install Add-on From
File.

Feedback of any kind welcome, and reports of it vanishing most of all.
