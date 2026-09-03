# Provenance — the 2026-09-03 acceptance matrix

`MATRIX.md` is the assembled table and carries its own limitations section,
which is authoritative on what the matrix does and does not establish. This
file records where each artifact came from, because a reader cannot tell from
a JSON file which build produced it.

## What produced each column

| artifact | target | how it was driven |
|---|---|---|
| `acceptance-zoteus.json` | zoteus | run by hand, `bench/acceptance/run.py --adapter zoteus`, 2026-09-03 |
| `acceptance-zotero-core-6012.json` | Zotero core PR 6012 | staged and run by a workflow agent |
| `acceptance-zotseek.json` | ZotSeek | staged and run by a workflow agent |
| `acceptance-zotero-mcp.json` | 54yyyu/zotero-mcp | staged from the committed lock file and run by a workflow agent |
| `acceptance-fixtures.json` | none — the instrument itself | `run.py --fixtures`, 16 fixtures x 12 assertions |

Beaver has no column here. Its adapter is ticket 0586's and was in flight in a
separate lane during this run; `bench/results/0586-beaver/` holds its own
artifacts.

## Two caveats that are this file's reason to exist

**The zoteus column was measured against a working checkout, not the reviewed
SHA.** The declaration records `revision: 1.12.0`, read from `package.json`,
which is accurate as a version string and misleading as provenance: the `fork/`
tree it ran against sat at `879b75b` on branch `droplist-df-pruning`, while
`UPSTREAM` names `b05ed69` as the reviewed baseline. Nothing in the artifact
says so, which is why it says so here. This column is therefore NOT a
substitute for `bench/results/smoke-1.12.0/acceptance-zoteus.json`, and it is
not committed as one. A run that could carry the reviewed version needs `fork/`
checked out and built at `b05ed69`.

**Four cells read `not-staged` for a scheduling reason, not a technical one.**
Zotero core 6012 and ZotSeek are host-bound: their R10 and R15-install clauses
walk into a lifecycle block that launches a Zotero desktop host. A parallel
session held the machine's Zotero and its local API port for a full-library
index build throughout this run, so every agent was forbidden to launch one.
The staging those agents did is the expensive half and it is done; those four
cells are a short re-run away, not a rebuild.

## The fixtures file is job-local, and newer than the committed one

`acceptance-fixtures.json` here is 16 fixtures x 12 assertions and includes the
two R22 checks. The repository's standing fail-control matrix,
`bench/results/smoke-1.12.0/acceptance-fixtures.json`, is dated 2026-09-02,
carries 14 x 10, and has no R22 rows at all. Both report an empty
`assertions_never_seen_red`; only this one can speak for the two assertions
that did not exist on 2026-09-02. Refreshing the standing artifact is not this
directory's business and is not done here.
