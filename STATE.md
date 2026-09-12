# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-12. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library — records, notes,
annotations and full text, in every language present — while remaining local by default,
current, bounded and honest about coverage. [README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- Sitter 0.4.0 tag **deferred** (DECISIONS.md, 2026-09-11; 0764 `Blocked-by: 0727, 0686`):
  0727 needs a named mechanism; 0686 is closed (items (1) and (3) built in 0.3.43);
  its item (2) → 0769, to be declared in RELEASE-NOTES.md by 0764 Action 5.
- Release the Multilingual test library and questions + grader as public Challenge
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Recent outcomes

- **0727 arm 5 (#526): bounded negative, and narrower than recorded.** 17 of ~50 cycles,
  zero disappearances — but the rig runs Zotero headless, where `initialize()` cannot pass
  its main-window requirement, so the sitter it installed very likely never ran (0778).
- **Sitter host-lifecycle audit** (`verification/SITTER-LIFECYCLE-AUDIT-2026-09-12.md`):
  install, remove, update, host upgrade/downgrade. Ten findings; 0771 implements three,
  0772–0779 carry the rest, three of them awaiting a ruling.

## Handoff

**Next on 0727**: give the volume rig a liveness verdict-carrier (0778) BEFORE spending the
rest of the ~2h budget — as driven, those cycles measure host bookkeeping alone. Otherwise correctness/privacy gaps: R10
(0660–0664), R13 (0650–0652), R15 (0654–0657), R22 (0643, 0665), fixtures 0602, 0623,
0658. #6012 parity train (0754, 0755–0757) filed, unstarted; DECISIONS.md owns open questions.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (ticket 0738).
Requirements: **24 ratified** ([SPEC.md](SPEC.md)).
Tickets: **82 ready, 138 open total** (`erg ready tickets/`); 11 await the author.
In flight: #529 (adapter controls), #530 (0727 instrumentation), lifecycle lanes 0771/0775/0779.
