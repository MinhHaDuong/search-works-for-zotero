# Zotero mailing list post — draft

*For the author to send, in his own name. Nothing here has been sent.*

*Register: a mailing list, read as plain text in clients that render no markup.
A subject line that carries the whole thing on its own, no headings, no bold, no
bullet glyphs, wrapped at 72 columns. The audience skews more technical than
Reddit, so the mechanism gets room — but the caveats still live in the release
notes rather than being recited here.*

*Everything between the cut lines is the message body and is already plain text;
send it as it stands. Replace [release URL] before sending.*

---8<--- subject ---8<---

Experimental add-on: prepare Zotero 10 structured-text caches in the background

---8<--- body ---8<---

I have written an experimental Zotero add-on and I would like a few people
to try it with their eyes open. It is called SDT Pack Sitter.

WHAT IT DOES

Zotero 10 can turn a PDF, EPUB or snapshot into a structured text pack: the
text plus its headings, reading order, and where on the page each piece came
from. Zotero builds a pack when something needs one. This add-on builds them
in advance instead, one attachment at a time, in the background, so the work
is already done the first time anything asks for it.

It also surfaces the state of those caches, which is otherwise hard to see:
what fraction of the library has a current pack, what is being worked on, and
which attachments could not be prepared and why - file missing from disk,
unsupported format, no text in the document, or a record with no file
attached at all.

It builds no index of its own and changes nothing about your search results.
It calls Zotero's own extractor, so extraction quality is exactly what Zotero
would have produced. It opens no network connection of its own.

WHY A PLUGIN AT ALL

I would rather this ended up in Zotero than in anyone's add-ons list. It is a
prototype. The 10.0 Index Statistics rework already gives the full-text index
a coverage bar, per-reason counts and indexing that advances while the pane is
open; this is the same interface for the other index, arrived at
independently. Trying it is how that argument gets evidence.

WHAT I RAN BEFORE POSTING

Installed from the release asset onto my own library, Zotero 10.0.1 on Linux.
Fifteen minutes of ordinary use, during which it indexed about 14% of the
library. Then I restarted Zotero: the add-on was still installed and enabled,
waited out its startup delay, and resumed scanning.

That matters because of the known bug below, and it is one run on one machine
- it says the add-on survived this, not that it survives.

THE THING TO KNOW BEFORE INSTALLING

This add-on has removed itself from Zotero mid-session on my machine:
disabled, then deleted from the profile record and from disk, without being
asked. Repeatedly over one instrumented evening, and once more two days
later. I do not know why. Nothing was lost from the library and Zotero's own
text index was untouched; what I lost was the add-on.

I have not been able to reproduce it deliberately. First installs,
replacement installs, an older build and repeated disable/re-enable cycles
across two machines have all survived, and four explanations I thought
plausible have been tested and ruled out. I am saying so rather than waiting
for a cause, because it seems more useful for people to know than for me to
keep looking alone.

If it happens to you, one thing is worth doing and the order is the whole of
the instruction. BEFORE restarting Zotero, open Tools -> Developer -> Run
JavaScript, evaluate

    JSON.stringify(Zotero.SDTPackSitterJournal.tail(200))

and copy the result somewhere. That object exists only while the Zotero
process is alive, so a restart destroys it, and it is the only record this
failure leaves. Then restart and reinstall. Sending me that output would help
more than anything else.

EVERYTHING ELSE

The remaining limitations - the Linux-only resource throttling, no OCR, the
Tab-navigation gap, what Zotero's update check fetches and how the extractor
compares to others - are in the release notes rather than here, because they
are the sort of thing you want in front of you while deciding, not in a mail
you have to search for later.

WHERE IT IS

[release URL]

Install with Tools -> Add-ons -> gear menu -> Install Add-on From File.

AGPL-3.0, the same licence as Zotero, deliberately: anything worth taking can
go upstream without a licence conversation.

Feedback of any kind is welcome, and reports of it disappearing most of all.

---8<--- end ---8<---
