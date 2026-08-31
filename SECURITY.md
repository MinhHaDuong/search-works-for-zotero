# SECURITY — what this system holds, and where it can leak

## Intro

This document describes what the system stores, where that data can be read,
changed, or sent off the machine, and what the design currently says about each
point. It decides nothing. Where an answer below is a gap, closing it is a new
obligation, and a new obligation is a ruling: `spec/DECISIONS.md` first, then
`spec/REQUIREMENTS.md`. This document only reports the gap.

The scope is local-only. Hosted mode is closed (D2, `spec/REQUIREMENTS.md`) and
nothing here reopens it. See "Out of scope" at the end.

Two words are used throughout. An *asset* is something a user would mind losing
or having read by someone else. A *surface* is a place where an asset can be
read, changed, or leave the machine.

The chain had no such document. Silence reads the same as "considered and found
safe" — to a reviewer, to the upstream maintainer, and to the author in six
months. Ticket 0052 filed this to end the silence, not to assert that anything
is mishandled.

## Assets

**The derived index.** `search-index-v2.sqlite` (`spec/DESIGN.md` §2.2) is not a
set of pointers into the Zotero library. It is a working copy of it. The slabs
table holds the source text itself, compressed, cut on entry boundaries;
passages are references into that text. The design slabs record and own-words
text for the same reason it slabs body text — otherwise a hit could not show
what it found.

So an attacker who reads this one file, without touching Zotero at all,
recovers titles, abstracts, keywords, creators, tags, the text of notes and
annotations (R16), and body-text passages for every attachment the pipeline has
reached, each with its heading path and character offsets. The right way to
think about the index file is as a second copy of the library, not as metadata
about one.

**Vectors.** Once semantic indexing has run, the index also holds a dense
embedding for each passage. Whether those numbers can be turned back into the
words that produced them is not established anywhere in this chain. They are not
stored as compressed text and they are not designed to be reversible, but that
is a design intent, not a proof: published work on embedding inversion has
recovered short passages from vectors alone. This document does not resolve the
question. It lists vectors as an asset rather than assuming they are safe
because they look like numbers.

**Credentials for opt-in providers.** A user who turns on an API embedder
configures a key for it (`spec/DESIGN.md` §2.7 names one, Gemini). The key is
worth whatever unauthorized use of the paying account is worth.

**Query text.** What a user searches for says something about what they are
working on, whether or not the index itself ever leaks.

**Coverage and status.** Less sensitive alone, but it describes the shape of a
library: how large, how current, how much is annotated.

## Surfaces

**The local database file.** One file, WAL mode (`spec/DESIGN.md` §2.2). File
permissions: none yet. Nothing in the chain states the mode the file is created
with, or whether another account on a shared machine can read it. C3
(`spec/CONSTRAINTS.md`) treats the machine as the user's; it does not say the
file is unreadable by anyone else with an account on it.

**Query and status tools.** These are MCP tools. The only transport the design
names is a stdio pipe between the conductor and its worker, with one zoteus per
MCP client (`spec/DESIGN.md` §2.5). No line in the chain says zoteus opens a
network port for these tools, and no line says it never will. This is silence,
reported as silence, not a verified negative.

**Egress to remote providers.** R10 gives the count directly: two opt-in
exfiltration paths, no silent fallback (`spec/DESIGN.md` §2.7). One is the
one-time model-weight download the default local embedder needs, named in
status, degrading to keyword-only and never to an API embedder. The other is
passage text sent to a configured API embedder, which quotes a cost and requires
an explicit go-ahead per index generation. The default path sends nothing.

**Credential storage at rest.** None yet. The chain records one fix — the Gemini
key moves out of the URL query string and into a header (`spec/DESIGN.md` §2.7)
— but not where the key is read from or kept between runs. No file, environment
variable, or OS keychain is named.

**Logs.** None yet. Nothing in the chain says whether queries, passage text, or
errors are written anywhere, and if so where, for how long, or who can read
them.

**Local Zotero traffic.** The pipeline reads items, records, and full text from
Zotero's own local API on the same machine (`spec/DESIGN.md` §2.3, §2.4): the
item and full-text census ticks, the query-path freshness probe, and the single
large fetch for an oversized attachment. None of this leaves the machine and
none of it counts against R10's two paths. It crosses the process boundary
between zoteus and the Zotero application. Whatever access control exists on
Zotero's own local API belongs to Zotero, not to this design.

**This repository.** The one surface that is not the system's. Measuring a real
library produces artifacts about real documents, and this repository is public,
so a measurement record is an egress path with no opt-in and no delete. It ran
that way: committed artifacts named documents from the author's library in
thousands of provenance fields until the ruling of 2026-08-31
(`spec/DECISIONS.md`) confined identification to Zotero item keys and stopped
the two drivers that wrote titles. Names published before that date remain in
the git log by the same ruling, which declines to rewrite history. Two
disclosures the ruling does not reach stay open here: committed artifacts hold
`passage` and `snippet` text drawn from the library, and the benchmark query
sets are the author's own research questions.

## Current answers, gaps included

| Surface | Current answer |
|---|---|
| Database file permissions | None yet |
| Query and status transport | stdio per client (§2.5); no stated network listener, absence not verified |
| Egress to remote providers | Two opt-in paths, both named (§2.7); the default path sends nothing |
| API-embedder credential storage at rest | None yet |
| Logs (queries, passage text, errors) | None yet |
| Local Zotero API traffic | Crosses a process boundary, stays on the machine; Zotero's own surface |
| This repository's committed artifacts | Item keys only, by ruling 2026-08-31; passage text and query sets still open |

Four of the seven rows read "none yet". That is the honest state of the design,
and stating it is this document's purpose. Each is a candidate ruling, not a
defect to fix here.

## Out of scope

Hosted mode is closed. D2 (`spec/REQUIREMENTS.md`) dropped the four privacy
requirements that applied only to it, and `spec/DESIGN.md` §2.7 confirms they
stay dropped: per-tenant contract keying, multi-tenant consent bookkeeping,
encryption-at-rest, and quota arithmetic. That ruling is not reopened here.

This document does not evaluate Zotero's own local API as a security surface,
only the point where this design's pipeline touches it.
