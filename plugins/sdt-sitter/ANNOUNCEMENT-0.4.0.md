# SDT Pack Sitter 0.4.0

*Draft of the release text, for the author to send. Nothing here has been
published. The section marked TO BE COMPLETED must be filled in from a run, or
removed, before this goes out.*

---

An experimental Zotero 10 add-on that prepares Zotero's structured-text caches
ahead of time instead of waiting until something asks for them.

## What it does

Zotero 10 can turn a PDF, EPUB or saved web page into a *structured text pack*:
the document's text together with its headings, its reading order, and where on
the page each piece came from. Zotero builds a pack when a consumer needs one,
such as the reader opening an attachment or an indexing pass reaching it.
Building one costs real time on a large document.

The sitter does that work early. It walks the attachments your library can
support, prepares their packs one at a time in the background, and stands aside
whenever Zotero itself wants the extractor. When something does eventually need
a pack, the work is already paid for.

It also makes the state of those caches visible, which Zotero does not otherwise
do. Its window shows how much of the library has a current pack, what it is
working on and how fast it is going, what it is waiting for when it waits (a
busy extractor, low memory, low disk, a loaded machine), and the attachments it
could not prepare, each with its reason: the file is missing from disk, the
format is unsupported, the document was inspected and contains no text, or the
record has no file attached.

It reconciles against your local files, so a file you restore or delete is
noticed rather than assumed.

## What it is not

It builds no search index, and your search results do not change because it ran.
It calls Zotero's own extractor, so it cannot improve extraction quality. It
opens no network connection of its own; one request does happen because the
add-on exists, and that is described below.

It is not finished software. It is an experiment in whether eager background
preparation can run on a working machine without becoming a nuisance, published
so that more than one library can answer the question.

## Being a polite guest

The sitter submits one attachment at a time, and only when all of these hold:

- Zotero's own extraction worker is idle,
- at least 4 GiB of memory is available,
- at least 8 GiB is free on the disk holding the cache,
- the one-minute load average is below the machine's core count.

It re-reads every one of those immediately before submitting, so it never
deliberately queues work behind Zotero's own. When it cannot read one of those
figures it declines to start rather than assuming there is room.

These decide whether to *begin* a document. Zotero's extraction entry point
accepts no cancellation, so a document already handed over runs to completion.
Turning the sitter off stops it admitting anything new and lets the document in
flight finish and save its pack. It does not kill work in progress.

## Turning it on and off

On first activation it asks once whether to prepare packs in the background. The
answer is remembered and the question is not asked again. The same switch is the
first control in the add-on's window, one click, without leaving Zotero.

One thing to know about removing it: the answer to that first-run question
outlives the add-on. If you had preparation switched on, remove the add-on and
install it again later, it resumes preparing without asking. Leaving the switch
off on a removal is decided and not yet built, so this version behaves as
described rather than as intended.

## Which Zotero it runs on

**Zotero 10.0.1 or later, and no Zotero after 10.** The minimum and the maximum
are both declared in the add-on itself.

The ceiling is deliberate. The sitter works through parts of Zotero that carry
no compatibility promise, meaning internal entry points rather than a published
add-on API. Declaring compatibility with a Zotero nobody has run it against
would be a claim about untested code.

So expect this: **when you upgrade to Zotero 11, the sitter will be left
installed and disabled.** It stays visible under Tools → Add-ons, it stops
preparing packs, and nothing is lost, not your library, not your attachments,
and not Zotero's own text index, which the sitter never touches. That is the
intended end of life for this build. A later build may raise the ceiling once
somebody has run it on 11.

## One request the add-on causes

Installing the sitter causes one outbound request, about once a day, for as long
as it stays installed. The add-on is not the thing making it.

The add-on declares an update manifest hosted on GitHub, and *Zotero's* add-on
update check fetches that manifest roughly daily. Declaring one is not optional:
an add-on that declares no update location is refused at install on Zotero 10.

The request is for one fixed URL. Nothing about your library, your items or your
use of Zotero is included. What it necessarily discloses to the other end is
your network address and the fact that this add-on's manifest is being checked.
The sitter itself opens no connection, here or anywhere else.

## What we did not reproduce

Read this before installing. It is why the release is labelled experimental.

### The add-on has disappeared from a live profile, and we cannot say why

On the author's own machine, the add-on has been observed removing itself from
Zotero while Zotero was running: disabled, then deleted from the profile's
record and from disk, without being asked to. It was seen repeatedly over one
instrumented evening on one machine, and once more, uninstrumented, two days
later. **The cause is not established.**

What is known. It happened mid-session, while Zotero was running. The add-on was
still running in memory when it happened: its window still worked and its
activity indicator still moved after its record and its file were already gone,
so Zotero never told it that it was being removed. Nothing was lost from the
library and Zotero's own text index was untouched. What it costs is the tool,
not data.

What was tried and did not reproduce it: deliberate first installs, deliberate
replacement installs, an older build predating the first fix, and repeated
disable-and-re-enable cycles, across two machines. Every one of those arms
survived. Four candidate explanations have been tested and refuted, including
the one the investigation opened on. Two remain untested.

**If it happens to you, do these two things in this order.** First, *before
restarting anything*, open Tools → Developer → Run JavaScript and evaluate:

```js
JSON.stringify(Zotero.SDTPackSitterJournal.tail(200))
```

Copy what comes back and send it with your report. Second, and only then,
restart Zotero and install the add-on again.

The order is the whole of the instruction. That object lives only as long as the
Zotero process, restarting destroys it, and in this particular failure it is the
only record there is. Turning on the add-on's technical-diagnostics switch is
worth doing and also writes a file for an ordinary disable or removal, but it
cannot catch this one, because the add-on is never told.

### The window is not qualified as accessible

The window has had a reduced-motion pass, carries a stable accessible name, and
announces changes of state for screen-reader users. But keyboard-only operation,
focus handling, screen-reader announcement in a real reader, and layout at
enlarged font sizes have not been verified in a running Zotero window, and no
automated test takes those readings. If you depend on any of them, this build
does not claim to serve you.

### Installing from this release, into a fresh profile

> **TO BE COMPLETED BY THE AUTHOR BEFORE THIS ANNOUNCEMENT GOES OUT.**
>
> Fill in from the arm actually run: the Zotero version and the operating
> system; that the install was made into a **fresh profile** from **this
> release's `.xpi` asset URL** rather than from a local file; that Zotero was
> restarted; and what was observed after thirty minutes of ordinary use.
> Record what happened, including anything unexpected, not what was expected.
>
> Leave this section out entirely rather than publish it unfilled. Every
> previous install of this add-on was a file carried by hand, so installing from
> a release asset is a path nothing has exercised.

## Installing

Download the `.xpi` from this release. In Zotero: Tools → Add-ons → the gear
menu → **Install Add-on From File…** → choose the file → restart Zotero when
asked.

Zotero will offer later versions through its own update check.

## Reporting something

Open an issue on this repository. Useful in a report: your Zotero version and
operating system, what the add-on's window said at the time, and, if the add-on
vanished, the journal output described above, read **before** you restart.

The add-on's window has a button that copies a technical report to the
clipboard. It is redacted by design: opaque record identifiers, no document
titles, no file paths.
