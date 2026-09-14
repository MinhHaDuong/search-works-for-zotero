# r/zotero post — draft

*For the author to post, in his own name. Nothing here has been posted.*

*Register: Reddit. Short, first person, self-disclosing in the first sentence —
r/zotero reads anything opening like a product page as advertising, and it is
right to. No headings, no bold-lead bullets, no ticket numbers. The caveats live
in the release notes; this links there rather than reciting them, because a post
that repeats the notes is the notes with a worse title.*

---

**Suggested title:** I wrote an experimental add-on that prepares Zotero 10's
structured-text caches in the background — looking for a few testers

---

I wrote this, so take the enthusiasm with salt.

Zotero 10 can turn a PDF, EPUB or snapshot into a structured text pack — the
text plus headings, reading order, and where on the page each piece came from.
Zotero builds one when something needs it. **SDT Pack Sitter** builds them ahead
of time instead, one attachment at a time, in the background, so the work is
already done the first time anything asks.

It also shows you where you stand, which is otherwise invisible: how much of the
library has a current pack, what it is working on, and which attachments it
could not do and why. On a big library the full pass takes hours, so doing it in
advance is the difference between an answer now and an answer tomorrow.

It builds no index of its own, changes nothing about your search results, and
uses Zotero's own extractor — quality is whatever Zotero would have produced
anyway.

**I would rather this ended up in Zotero than in your add-ons list.** It is a
prototype. Dan built essentially this window for the full-text index in the 10.0
Index Statistics rework; this is the same idea for the other index. Trying it is
how that argument gets evidence.

It is experimental and it has a known bug I cannot yet explain — **please read
the Known bugs section before installing.**

AGPL-3.0, source, release notes and issues:
https://github.com/MinhHaDuong/search-works-for-zotero

Install with Tools → Add-ons → gear menu → Install Add-on From File. Feedback
welcome.
