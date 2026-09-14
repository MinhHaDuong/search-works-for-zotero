# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-14. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library — records, notes,
annotations and full text, in every language present — while remaining local by default,
current, bounded and honest about coverage. [README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- **The sitter is code-complete for its first tag.** No open PRs, `make check` green on main,
  version 0.4.10, floor lowered to **10.0** (measured, not declared), AGPL-3.0 licence added.
  **Author's hands only, in order:** pick the number, GPG-sign the tag, publish the `.xpi`;
  fresh-profile install from that asset; ONE commit adding BOTH `tag` and `update_link`
  (half-filled FAILs the gate); then announce. `/releases/latest` 404s until the tag, so the
  announcement cannot go out before the asset.
- Announcements drafted for r/zotero and the mailing list; both carry a `TO BE COMPLETED`
  block to fill **from** the run. Framing: a prototype offered upstream, not a tool to adopt.
- Release the Multilingual test library and questions + grader as public Challenge.
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
  with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Recent outcomes

- **All three 10.x releases exercised against real documents**, including the 10.0.1 → 10.0.2
  carry-over: the sitter discarded every cached pack and re-prepared at processor 14.
- **Only the reader consumes SDT in 10.0.2** — not search, not full-text. No OCR. From `omni.ja`.
- **0787 ruled**: the control is focusable but NOT Tab-reachable (Zotero's `actionsMap` is
  private). No workaround; it becomes an upstream report.
- Toast now announces once per stretch of work, not once per sweep (0788, ruled poor UX).

## Handoff

**0727 still has no mechanism** and ships disclosed. Open: 0769 (Orca half), 0774, 0786, 0787.
Correctness/privacy gaps unchanged:
R10 (0660–0664), R13 (0650–0652), R15 (0654–0657), R22 (0643, 0665), fixtures 0602, 0623, 0658.
#6012 parity train (0754, 0755–0757) filed, unstarted.

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (0738). Requirements: **24 ratified**.
Tickets: run `erg ready tickets/` — 344 total here. No open PRs.
