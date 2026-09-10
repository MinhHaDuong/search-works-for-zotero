# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-10. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library — records, notes,
annotations and full text, in every language present — while remaining local by default,
current, bounded and honest about coverage. [README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- Release the SDT pack sitter plugin
- Release the Multilingual test library and questions + grader as public Challenge
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Recent outcomes

- **Sitter NOT releasable (0908):** 30 of 38 mutations silent in `blocked()` and
  `inspect()`. Landed 0730, 0731; filed 0737, 0740, 0741. 0727's two hypotheses refuted,
  still no cause. 0606's residue is 158, not 3 853 (0728).
- **Not indexed panel ordered end to end (0910, #510/#512).** Groups follow the census
  account, libraries follow personal-then-groups-by-name; both were the census walk's
  before. §5.2.7 owns the classes, the admission rule and the order, not the wording (#511).
- **A gate can be red only on the author's machine (0910, #513):** the built `.xpi` is gitignored, so two filesystem-walking guards met it nowhere a runner could.

## Handoff

Start with correctness/privacy acceptance gaps: R10 (0660–0664), R13 (0650–0652), R15
(0654–0657), R22 (0643, 0665), fixture controls 0602, 0623, 0658. The #6012 parity train
(0754 tracker, 0755–0757) is filed and unstarted; [DECISIONS.md](DECISIONS.md) owns
questions awaiting the author.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (ticket 0738).
Requirements: **24 ratified** ([SPEC.md](SPEC.md)).
Tickets: **78 ready, 126 open total** (`erg ready tickets/`); 8 await the author.
In flight: **none** — no open PRs at `cf9d7f1`.
