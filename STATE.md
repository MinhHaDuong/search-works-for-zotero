# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-11. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library — records, notes,
annotations and full text, in every language present — while remaining local by default,
current, bounded and honest about coverage. [README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- Sitter 0.4.0 tag **deferred** (DECISIONS.md, 2026-09-11; 0764 `Blocked-by: 0727, 0686`):
  0727 needs a named mechanism; 0686 (1),(3) must land; (2) → 0769, a declared limit.
- Release the Multilingual test library and questions + grader as public Challenge
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Recent outcomes

- **Sitter mutation gate live in `check` (0763, #517):** 30/30 and 19/19 mutants caught.
  Five anchors had rotted unrun; 0908's "NOT releasable" figure is retired, un-re-derivable.
- **0727 arm 5, volume experiment (#526): bounded negative, not conclusive.** New tool
  (0766, #523) scripts Zotero's real install path externally — 17 cycles, one process,
  cut short at ~31 min of a planned ~2h/~50-cycle run: zero disappearances. More volume
  than any prior arm, but short of budget; intermittency under full volume still untested.

## Handoff

**Next on 0727**: re-run `bench/sitter_volume_experiment.py` (0766) to the full
~50-cycle/~2h budget — arm 5 stopped at 17. Otherwise correctness/privacy gaps: R10
(0660–0664), R13 (0650–0652), R15 (0654–0657), R22 (0643, 0665), fixtures 0602, 0623,
0658. #6012 parity train (0754, 0755–0757) filed, unstarted; DECISIONS.md owns open questions.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (ticket 0738).
Requirements: **24 ratified** ([SPEC.md](SPEC.md)).
Tickets: **81 ready, 129 open total** (`erg ready tickets/`); 8 await the author.
In flight: **none** — no open PRs at `3bb14fd`.
