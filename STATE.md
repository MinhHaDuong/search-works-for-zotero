# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-13. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library — records, notes,
annotations and full text, in every language present — while remaining local by default,
current, bounded and honest about coverage. [README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- Sitter 0.4.0 **ships with the disappearance disclosed** (DECISIONS.md 2026-09-13, superseding
  the 2026-09-11 deferral). An override: 0727 has no named mechanism and stays open. **Author's
  hands only, in order:** build, GPG-sign the tag, publish the `.xpi`; one commit adding BOTH
  `tag` and `update_link` (half-filled FAILs); fresh-profile install from the asset; announce.
- **Zotero 11 incompatible, `10.*` stands** (0777). **0772/0773 ruled and IMPLEMENTED** (PR #544)
  — uninstall writes the switch off only where the first-run question was answered; unanswered stays `null` and asks again.
- Release the Multilingual test library and questions + grader as public Challenge
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Recent outcomes

- **0727 is wider, not narrower.** Arm 5's 17 clean cycles ran headless, where `initialize()`
  never passes its main-window check (0778); and `shutdown()` never runs in the phenomenon, so
  the certificate and the parked ring cannot witness it (0781). 0771/0775/0779 closed.
- **#6012 moved to `4427be9a`** (2026-09-12): queue order is now most-recently-touched first,
  not smallest first. SYNC.md's Zotero-core row supersedes; the pinned readings stand.

## Handoff

**Next on 0727**: give the volume rig a liveness verdict-carrier (0778) BEFORE spending the
rest of the ~2h budget — as driven, those cycles measure host bookkeeping alone. Otherwise
correctness/privacy gaps: R10 (0660–0664), R13 (0650–0652), R15 (0654–0657), R22 (0643, 0665),
fixtures 0602, 0623, 0658. #6012 parity train (0754, 0755–0757) filed, unstarted.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (0738). Requirements: **24 ratified**.
Tickets: run `erg ready tickets/` — 84 ready, 138 open here, three fewer once #538 lands.
In flight: #537 version, #538 closes, #539 notes, #540 drift, #541 announcements; #539 and
#540 are stacked on their predecessors, so merge in number order.
