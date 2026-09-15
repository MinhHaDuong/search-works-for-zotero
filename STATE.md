# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-15. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library — records, notes,
annotations and full text, in every language present — while remaining local by default,
current, bounded and honest about coverage. [README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- **v0.4.10 is released; the tree is five versions past it at 0.4.15 and awaiting a retag.**
  Acceptance PASS on 0.4.15 against Zotero 10.0.2 (`bench/sitter_acceptance.py`, record in
  `verification/acceptance/`). 0.4.11–0.4.15 carry both Orca defects, the census display fix,
  and 0727's two guards — a tester on v0.4.10 meets all of them.
  **Author's hands only, in order:** GPG-sign the tag, publish the `.xpi`, then ONE commit
  adding BOTH `tag` and `update_link` (half-filled FAILs rule 2).
- Announcement drafts are **out of the repo** (ruled 2026-09-14: outward communications the
  author sends in his own name are not deliverables). A forum draft sits at
  `~/Bureau/sdt-sitter-ANNOUNCEMENT-zotero-forum.md`.
- Release the Multilingual test library and questions + grader as public Challenge.
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
  with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Recent outcomes

- **All three 10.x releases exercised against real documents**, including the 10.0.1 → 10.0.2
  carry-over: the sitter discarded every cached pack and re-prepared at processor 14.
- **Only the reader consumes SDT in 10.0.2** — not search, not full-text. No OCR. From `omni.ja`.
- **0727's mechanism is found, and it is Zotero's.** A Remove is queued, not performed; an
  install of the same id then succeeds and the queued removal finalises on the new copy
  ~3 s later, by id, without rechecking. Witnessed in the host's own `addons.manager` log
  after four occurrences, three watched at 50 ms. Workaround: remove, **quit**, install.
- **Both defects reported upstream** and linked from the release notes:
  [133758](https://forums.zotero.org/discussion/133758/) (the removal race) and
  [133759](https://forums.zotero.org/discussion/133759/) (0787, plugin buttons outside the
  Tab chain — mechanism verified against `zoteroPane.js`, not inferred).
- Toast now announces once per stretch of work, not once per sweep (0788, ruled poor UX).

## Handoff

**0727 and 0787 stay open as upstream matters**, both filed, neither ours to fix. Open here:
0774, 0786, and 0727's guard 2 — warning at startup before the deletion, unbuilt because
whether `pendingOperations & PENDING_UNINSTALL` survives the install on the UI path is
unmeasured, and a check that cannot fire must not ship.
Correctness/privacy gaps unchanged:
R10 (0660–0664), R13 (0650–0652), R15 (0654–0657), R22 (0643, 0665), fixtures 0602, 0623, 0658.
#6012 parity train (0754, 0755–0757) filed, unstarted.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (0738). Requirements: **24 ratified**.
Tickets: run `erg ready tickets/` — 347 total here. No open PRs.
