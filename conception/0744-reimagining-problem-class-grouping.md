# Reimagining: group unsupported and refused documents by problem class

Date: 2026-09-09
Status: Reimagine pass only — not planned, not implemented, not ruled on
Owner: ticket 0744
Prepared by: Fable, read-only reimagine pass (raid-style Phase 2 Imagine),
launched at the author's request to argue five specific angles the ticket as
filed did not address: reruns, tags instead of a collection, documents with
more than one problem class at once, Zotero's saved searches, and prior art
in comparable systems.

Saved here rather than folded into the ticket body because no ruling has been
taken yet — this is the material a ruling would be made from, not the ruling
itself (`tickets/AGENTS.md`'s decision-records-vs-artifacts distinction).
Intended to be handed to whoever picks the ticket up next, human or agentic,
as the argument behind whatever the ticket says once it is split/ruled on.

Read alongside `tickets/0744-group-unsupported-and-refused-documents.erg`,
which this does not restate.

## What the code actually does today (the ground the ticket stands on)

- `inspect()` (bootstrap.js:1889–1990) is a decision tree with early returns:
  trashed → `excluded`; no host predicate matches → `unsupported`; no file →
  `missing-source`; then the pack is opened and read; and only for a document
  that ends up in the `queued` class does the sniffer run, collapsing a
  byte/label mismatch to `unsupported` and discarding `sniffed.format`. One
  document yields exactly one status, decided by the first gate that fires.
- Re-classification is event-driven plus periodic: `Zotero.Notifier`
  (bootstrap.js:2094) invalidates on item add/modify/trash/delete/refresh and
  file download, the pump re-inspects the dirty set, and a full census runs
  on a reconciliation interval (default one hour, scheduler.js:75). A file
  overwritten in place by an external OCR fires no notifier — Zotero does not
  watch the filesystem — so that document reclassifies at the next hourly
  census (the stat `lastModified` changes, the hash is redone). A change made
  through Zotero (re-saving the attachment, a plugin replacing the file)
  reclassifies within seconds.
- `failed-session` is by ruling gone on restart (0740 log, 11:30Z). It is the
  least stable population in the whole census: every restart empties it and
  the next sweep refills it.
- `pages` is already read from Zotero's own `fulltextItems`
  (bootstrap.js:1916). The same table carries `indexedChars`/`totalChars`,
  which the plugin does not read.

Two consequences follow before any of the five angles, and both bear on
scope.

First, the ticket's third example class, "scanned PDF, no text layer", is one
the census cannot see today. A scan is `%PDF`, so the sniffer passes it; it
is submitted; native SDT either fails (→ `failed-session`, indistinguishable
from the genuine-HTML failure 0740 set aside) or persists a pack with no text
(→ `current`, i.e. counted as indexed). Which of the two happens is
unmeasured. If the second, the largest "will never be useful" population sits
inside `indexed`, and "group the documents the sitter will not index" is the
wrong frame for it. This wants one measurement on the author's library before
the class list is drafted, and `fulltextItems.indexedChars == 0` on a PDF
with `totalPages > 0` is a cheap, read-only discriminator already one query
away.

Second, `missing-source` (367) is, in the author's own ruling in 0740, "an
ordinary fact about a synced library and not a failure of anything." Putting
it under a heading of problems with a remedy ("the file would be indexable
once downloaded") is precisely the implied obligation the tone rule forbids,
and it is the second-largest row. It belongs in the account, not in the
problem grouping, or under a wording that says it is a sync setting and
nothing is wrong.

## 1. Reruns and staleness

A Zotero collection is a static snapshot, and the dialog that offered it is a
live view rebuilt from `observed` on every render. The moment the user OCRs
three documents, the Details layer is right and the collection is wrong, and
nothing tells the user which of its 2,600 members are still in the class. The
cost is not merely inaccuracy; it is the tone. A collection named for a
problem, populated with items, that only ever shrinks by the user's hand, *is*
a backlog. The ticket forbids presenting a count as a backlog and then
proposes to materialize one in the left pane, where it sits unasked,
permanently, outside the Details layer — which the ticket's own third
invariant forbids for anything here. The contradiction is in the data shape,
not the wording, so no wording pass repairs it.

The honest snapshot design at zero engineering is to name the collection as a
snapshot ("… as of 2026-09-09") and let the dialog stay the source of truth.
That is honest but weak: it still leaves furniture. The stronger answer needs
no persistence at all: the offered control is **"show these items in the
library pane"** (`ZoteroPane.selectItems`, per library since a class may span
libraries). A selection is ephemeral, always current at the moment it is
made, and from it the user has every native gesture — Add to Collection, tag,
right-click into an OCR plugin — in Zotero's own words. If he wants a
collection he makes one in two clicks, and the plugin keeps its
never-writes-to-the-library invariant intact, which the ticket itself flags
as "a new capability [that] needs its own look."

## 2. Tags instead of collections

If a write is wanted at all, tags dominate collections on every axis but one.
Gained: per-item visibility with no separate pane object; multi-valued, so no
partition assumption is baked in; Zotero's *automatic* tag type (type 1) is
shown in a distinct colour, can be hidden with the tag selector's "Display
Automatic" toggle, and can be removed in one gesture with "Delete Automatic
Tags in This Library" — native, reversible, user-owned controls that a
collection has no equivalent of. Lost: nothing a collection gives except the
one-click "open the folder" feel, which a tag-selector click replaces.

The costs are real, and they are the same for collections, only louder for
tags because there are N writes instead of one. Tagging 2,600 items bumps
2,600 `dateModified`, syncs 2,600 changes to every device and to every member
of a group library who does not run this plugin and will see a cryptic tag
they did not add; and it fires 2,600 item-modify notifications into the
sitter's own observer (bootstrap.js:2096), which re-inspects each one —
harmless but wasteful, and any write path here must be checked for that
feedback before it ships. Read-only group libraries cannot be written at all,
so the offer must be per-library and conditioned on editability.

The rerun question is where tags stop being free. Re-applying and removing
tags as classification changes is exactly the live behaviour a snapshot
lacks, and it is also an automatic library write on every census, which the
author ruled out in "never automatic." The reconciliation is an opt-in
switch, default off, that the user operates once ("keep the sitter's tags
current"). That is legitimate, but it is a third feature, not a detail of
this one.

## 3. Multiple impossibilities

Classes overlap in truth and not in the data. A scanned page saved as
`text/html` fails the label gate; re-saved as a PDF it becomes a scan without
a text layer; the sitter can only see the second obstacle after the first is
removed, because the sniffer runs inside a branch the first gate never
reaches. So the computed classification is a partition by construction, the
partition names the *first obstacle found*, and a document can move class on
rerun without anyone having made an error. That does not break "one group per
class"; it breaks any *persistent* per-class artifact, which is point 1 again
with a different mechanism. Building a document → set-of-classes model is
speculative today, since no gate order in the code observes two reasons at
once; the honest scope is to label each class as the first obstacle and to
say once, in the layer, that a changed document is re-inspected and may land
elsewhere. Rust's diagnostics split this well: `note:` for what is
established, `help:` for what would change it — which is the ticket's own
action-1 requirement, "what the sitter knows and what it is guessing,"
rendered as two registers.

## 4. Saved searches

A saved search is live only over what Zotero can query, and none of these
classes is expressible in Zotero's search conditions: there is no "declared
type contradicts bytes" and no "full text indexed with zero characters." So a
saved search here is keyed on a plugin-written tag and inherits every cost in
point 2; without maintained tags it is stale while *looking* live, which is
worse than a collection that at least looks static. It adds a second piece of
permanent pane furniture for what a tag-selector click already gives. Not a
primary offer.

## 5. Prior art

The recurring pattern across compilers and linters, ocrmypdf, restic/borg
skip reports, and package resolvers is that the grouped-by-reason report is
the *run's* output, regenerated every run and never persisted as a to-do
list; grouping is by a stable reason ID, each with a one-line "what would
change this," and remedies are indicative (`cargo`'s "consider …", rustc's
`help:`), with apt's imperative "you may want to run …" as the counter-example
to avoid. Where a system does keep a live membership — a spam quarantine,
Mendeley's "Needs Review", Zotero's own Duplicate Items, Unfiled Items and
Retracted Items views — it is a computed view owned by the classifier,
appearing only when non-empty, never a user-curated snapshot. Zotero's item
pane shows "Indexed: No / Partial / Yes" per item, flat and indicative, and
offers no list at all. Nobody in this family ships "create a static folder
from this run's failures," because a snapshot of a classifier's output is
stale the moment the classifier runs again. The strongest structure for this
ticket is therefore: the Details layer *is* the computed view; the only
control is one that turns a group into a live native selection.

## Recommendation: split, and narrow the write

**Amend the core and land it as its own ticket (A).** Carry the reason out of
`inspect()` beside the status — keep `sniffed.format`, and add the
`fulltextItems` character count for PDFs *after* measuring on the author's
library whether scans surface as `failed-session` or as empty `current`
packs. Author rules on the vocabulary. Render per class in the Details layer:
the first obstacle stated, the remedy in the indicative under a separate
"what would change this" register, titles under a bounded cap, and a "show in
library pane" control per class and per library — on demand only, and it
never touches the library. Keep `missing-source` out of the problem framing
per 0740, and label `failed-session` as this-session-only with time as its
remedy. Zero library writes; the plugin's standing invariant is untouched and
the ticket's test plan (red fixture per class, label-contradiction kept apart
from no-extractor) carries over as written.

**Defer the library write to a second ticket (B), blocked by A and by a
ruling.** The ruling is whether the plugin may write into libraries at all,
and into group libraries in particular. If yes, the write is automatic-type
tags, not a collection, offered as a control; a dated collection name is the
fallback only if the author specifically wants a folder. Reconciling tags on
rerun is a separate opt-in switch, not part of B's first cut. Expect A's pane
selection to make B unnecessary — the user can create the collection himself
from the selection — and treat B as filed to record that decision, not to be
built by default.

Two open questions to settle before A is scoped, both measurements rather
than design: how native SDT treats a text-less PDF on the live library, and
how many of the 2,600 `unsupported` are declared image or office types (no
extractor, nothing to say) versus label contradictions (a real remedy) — the
class list should be drawn from those counts, not from the three examples.

## Addendum, same day: a button to copy problematic references to the clipboard

Correction to an earlier draft of this addendum, which misread the author's
point as being about the existing "Copy the log" button specifically ("we
already have a Save log button, actually" was cited as *precedent* for a
working copy-to-clipboard pattern, not as the mechanism to reuse
unmodified). The actual proposal: **add a button that saves the problematic
references themselves to the clipboard** — modelled on the existing pattern,
reading a different source.

This is a clean fit, and it sidesteps most of what makes the in-dialog
rendering hard. The plumbing already exists and is proven: `journal-copy`
(bootstrap.js:1230-1235) shows the shape — a composer function builds a text
block, `copySDTText` (bootstrap.js:1178-1185) writes it to the platform
clipboard, a status line reports success or "clipboard unavailable." A
"Copy problematic references" control would be the same shape reading a
different composer, built from Ticket A's per-class grouping (the census's
`observed` map, carrying the sniffer's verdict instead of collapsing it) —
title, class, and remedy per line, or grouped by class with a heading per
group. Zero library writes, same as every other option this note considers;
this one is not even a *read* from anywhere but the census already held in
memory.

Two things this option gets for free that the in-dialog rendering does not:

- **No bounded-cap decision.** The Details layer needs a title cap because a
  class holding 2,600 items is a wall, not a list, inside a fixed-height
  window. A clipboard export has no such constraint — the whole class can go,
  which is exactly the shape a downstream consumer (a note, a spreadsheet, an
  agentic fixer's context) wants.
- **The tone constraint moves downstream.** "Informational, never directive"
  governs what the *dialog* says while the user is looking at it. Once the
  same data is on the clipboard, the reader decides what to do with it in
  whatever tool they paste it into — the plugin's own obligation not to nag
  is met by definition, because nothing renders inside the plugin's own
  surface. The remedy text should still avoid the imperative mood, if only
  because clipboard content quoted back to the author (a bug report, a
  fixer's prompt) inherits its own author's voice.

This does not replace the account/grouping work Ticket A already describes
— it needs the same class-carrying prerequisite, and the in-dialog rendering
is still worth having so the reader can see the shape of the problem before
deciding to export anything. It is best read as a second, cheap control on
the same data Ticket A computes, not an alternative to computing it.

## Addendum, same day: an API instead of (or beside) any of the above

The author's next question: is the classification "in memory," and could an
API expose it so agents "do what they want with it," rather than the sitter
building any presentation logic — dialog or clipboard — at all?

Half yes on the first part. The coarse status is already live in
`scheduler.js`'s `observed` map — the same source every option above reads.
The problem class specifically is not: `inspect()` computes the sniffer's
verdict and discards it into bare `unsupported` today, so "carry the class
out of `inspect()`" (Ticket A's Action 2) is a prerequisite for an API
export exactly as it is for a dialog or a clipboard button — there is no
path to this feature that skips it.

On the API itself: there is direct precedent, not a green field.
`bench/zotero-fulltext-plugin/bootstrap.js` already registers two endpoints
on Zotero's own local HTTP server (`GET /search-works/fulltext/status`,
`POST /search-works/fulltext/reindex`), loopback-bound and gated by Zotero's
own `Zotero-Allowed-Request` header check — the security question is already
answered by existing, shipped code, not open here. And ticket 0758 (Codex,
filed the same day as this one) is already proposing to grow that same
plugin into "a shared text foundation for Zotero AI tools" — fulltext,
structured-text and chunk views, consumers free to choose their own models,
rankings and interfaces. That is the same philosophy this question is
asking for, currently scoped to document *content* rather than document
*coverage*.

A classification endpoint is the natural sibling: extend the existing
`status?keys=...` response (or add a neighbouring one) to carry problem
class and remedy reason per key, once Ticket A's carrying-through-`inspect()`
step exists. Doing this removes almost the entire hard part of the ticket as
filed — the indicative-not-directive tone design, the bounded list, the
collection/tag write decision — because raw classified data carries no
tone, and an agent consuming it decides what to do through Zotero's own
item/collection/tag APIs, entirely outside the sitter's control.

The one real fork this raises: the endpoint's home. 0758's own text argues
for reusing the existing fulltext-control plugin rather than inventing a
second API surface ("a shipping extension belongs under `plugins/`... any
promotion should preserve its installation identity" — the existing plugin,
not a new one). That argues against bolting an HTTP endpoint onto the sitter
itself, and for treating this as one more view alongside 0758's fulltext/
structured-text/chunk modes on the one shared API — which makes this
addendum a note for 0758's contract review as much as for this ticket, not
a fully separate feature.

Where this leaves three related, non-exclusive options for what "problem
class" ends up connected to: the in-dialog grouping (Ticket A, always
useful so the reader can see the shape of the problem at a glance), the
clipboard button (cheap, zero new infrastructure, ships as soon as Ticket A
lands), and the API view (the most leveraged, since it is one addition to
work 0758 already plans rather than a new surface — but it is 0758's
contract review that should decide the shape, not this ticket unilaterally).
None of the three requires choosing against the others.
