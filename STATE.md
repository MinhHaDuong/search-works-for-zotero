# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-08. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library
— records, notes, annotations and full text, in every language present —
while remaining local by default, current, bounded and honest about coverage.
[README.md](README.md) owns the proposition;
[SPEC.md](SPEC.md) owns the promises and design.

## Current Goals

- Release the SDT pack sitter plugin
- Release the Multilingual test library and questions + grader as public Challenge 
- Zoteus feature freeze for September 21 release. Concentrate on **correctness, packaging and privacy**,
write QA tests for those dimensions, hold the separate indexer/worker rewrite, oversized-document segmenter.

## Recent outcomes

- **v1.16.0:** upstream merged our PR #60 (the sixteenth, none rejected) and
closed six issues filed from here in one evening. [SYNC.md](SYNC.md) owns upstream state.
- Filed 2 PR, 5 public issues and 6 private security issues upstream
- **Sitter NOT releasable (0908):** 30 of 38 mutations silent in `blocked()`
  and `inspect()`. Landed 0730, 0731; filed 0737, 0740, 0741. 0727's two
  hypotheses refuted, still no cause. 0606's residue is 158, not 3 853 (0728).

## Handoff

Start with correctness/privacy acceptance gaps: R10 (0660–0664), R13
(0650–0652), R15 (0654–0657), R22 (0643, 0665), and fixture controls 0602,
0623 and 0658. [DECISIONS.md](DECISIONS.md) owns questions awaiting the author.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (ticket 0738).
Requirements: **24 ratified** ([SPEC.md](SPEC.md)).
Tickets: **77 ready, 123 open total** (`erg ready tickets/`).
In flight: **none**.
