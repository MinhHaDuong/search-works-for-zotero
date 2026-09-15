# STATE — Search Works for Zotero

*Live handoff. Updated 2026-09-15 (sitter 0.4.16, root tidy 19:36Z). Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Semantic search should work across a whole Zotero scholarly library — records, notes,
annotations and full text, in every language present — while remaining local by default,
current, bounded and honest about coverage. [README.md](README.md) owns the proposition, [SPEC.md](SPEC.md) the promises and design.

## Current Goals

- **v0.4.10 is released; the tree is six versions past it at 0.4.16 and awaiting a retag.**
  Acceptance PASS covers **0.4.15 only** (`verification/acceptance/0.4.15-2026-09-14.json`, Zotero 10.0.2);
  **0.4.16 is untested** — it names the post-census stretch and bounds the retry that spun there (2e16f199).
  Re-run `bench/sitter_acceptance.py`, or tag 0.4.15. 0.4.11–0.4.16 carry both Orca defects, the census
  display fix, and 0727's two guards. **Author's hands only, in order:** build (`bench/build_sdt_sitter.py`
  now defaults to `plugins/sdt-sitter/`), GPG-sign the tag, publish the `.xpi`, then ONE commit adding BOTH
  `tag` and `update_link` (half-filled FAILs rule 2).
- Release the Multilingual test library and questions + grader as public Challenge.
- Zoteus feature freeze for the September 21 release: correctness, packaging and privacy,
  with QA tests for those. Indexer/worker rewrite and segmenter stay held.

## Recent outcomes

- **A full-library sweep stopped advancing at 90 % on the IPCC AR6 WG1 report** (3 949 pages,
  242 MB) and was ended by hand. Nothing crashed — no dump, no OOM, heartbeats firing
  throughout; the native `Zotero.SDT.ensure()` stopped reporting. Slow tail or wedged worker
  is unestablished, and 0793 measures it. Trace preserved in `verification/incidents/`,
  since `sdt-sitter-last-shutdown.json` is overwritten at every shutdown.

## Handoff

**0727 and 0787 stay open as upstream matters**, both filed, neither ours to fix. Open here:
0774, 0786, and 0727's guard 2 — warning at startup before the deletion, unbuilt because
whether `pendingOperations & PENDING_UNINSTALL` survives the install on the UI path is
unmeasured, and a check that cannot fire must not ship.
Correctness/privacy gaps unchanged:
R10 (0660–0664), R13 (0650–0652), R15 (0654–0657), R22 (0643, 0665), fixtures 0602, 0623, 0658.
#6012 parity train (0754, 0755–0757) filed, unstarted.
Filed today, both unstarted: **0793** (instrument the AR6 plateau — its red step is the
positive control, not the AR6) and **0794** (two documents the menagerie lacks: a *Recueil
de planches* volume, text concentrated in a fifth of its pages, and the 3 666-page Desert
Quartzite draft EIS; Malynes stays, and the ticket says why).

## Basic state

Reviewed upstream: **v1.16.0+1** at `4467663` (0738). Requirements: **24 ratified**.
Tickets: run `erg ready tickets/` — 350 total here. No open PRs.
