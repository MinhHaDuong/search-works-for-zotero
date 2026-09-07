# STATE — Search Works for Zotero

*Live handoff, under forty lines. Updated 2026-09-07. Ownership: [AGENTS.md](AGENTS.md).*

## North Star

Search should work across a whole scholarly library — records, notes,
annotations and full text, in every language present — while remaining local
by default, current, bounded and honest about coverage. [README.md](README.md)
owns the proposition; [SPEC.md](SPEC.md) owns the promises and design.

## Now through September 21

Feature freeze. Deliver the checkpoint by concentrating on **correctness,
packaging and privacy**, and write the unfinished QA tests for those dimensions,
as promised on the upstream issue tracker. Re-test the durable pause shipped in
upstream v1.15.0 without expanding its acceptance scope. Hold the separate indexer/worker rewrite, oversized-document
segmenter and all other feature work. [SYNC.md](SYNC.md) owns upstream state.

## Recent outcomes

- **PR #359:** re-baselined every standing row on zoteus v1.14.0, including the
  default-off update check, model pooling and caller-path safety.
- **PR #360:** limited re-baselines to measurements affected by the source delta.
- **v1.15.0:** upstream shipped the uninstall procedure and durable pause; the
  source range also moves local embedding inference into a worker thread.

## Handoff

Start with correctness/privacy acceptance gaps: R10 (0660–0664), R13
(0650–0652), R15 (0654–0657), R22 (0643, 0665), and fixture controls 0602,
0623 and 0658. [DECISIONS.md](DECISIONS.md) owns questions awaiting the author.

## Basic state

Reviewed upstream: **v1.15.0** at `037bba8` (ticket 0735).
Requirements: **24 ratified** ([SPEC.md](SPEC.md)).
Tickets: **78 ready, 39 blocked, 8 awaiting author** (`erg ready tickets/`).
In flight: **none**.
